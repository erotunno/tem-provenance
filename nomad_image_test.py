"""Convert one Velox TEM image from an eLabFTW session for a NOMAD smoke test."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from zoneinfo import ZoneInfo

import h5py
from ase.formula import Formula
from pynxtools.dataconverter.convert import convert

from config import load_config
from ElabFTW.Client import ElabFTWAPI
from NOMAD.Client import NOMADAPI


def utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def facility_time(value, zone):
    local = datetime.fromisoformat(value)
    if local.tzinfo is not None:
        return local.astimezone(timezone.utc)
    candidates = set()
    for fold in (0, 1):
        utc = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            candidates.add(utc)
    if len(candidates) != 1:
        raise ValueError(f"Local time {value!r} is ambiguous or nonexistent in {zone.key}.")
    return candidates.pop()


def values(client, record):
    return {name: field.get("value") for name, field in client.extra_fields(record).items()}


def read_session(session_id):
    with ElabFTWAPI.from_config() as client:
        session = client.get_experiment(session_id)
        fields = values(client, session)
        for name in ("Sample", "Microscope", "Path", "start_time"):
            if not fields.get(name):
                raise ValueError(f"Experiment {session_id} is missing {name}.")
        sample = client.get_item(fields["Sample"])
        microscope = client.get_item(fields["Microscope"])
        specimen = values(client, sample)
        if parent_id := specimen.get("identifier_parent"):
            if str(parent_id) == str(sample["id"]):
                raise ValueError("A specimen cannot be its own parent.")
            parent = client.get_item(parent_id)
            if not parent.get("elabid"):
                raise ValueError(f"Parent sample {parent_id} has no persistent eLabFTW identifier.")
            specimen["identifier_parent"] = parent["elabid"]
        return session, fields, sample, specimen, microscope


def material_components(sample):
    raw = sample.get("metadata")
    metadata = json.loads(raw) if isinstance(raw, str) else raw
    groups = (metadata or {}).get("elabftw", {}).get("extra_fields_groups") or []
    material_ids = {str(group["id"]) for group in groups if group.get("name") == "Materials"}
    fields = ElabFTWAPI.extra_fields(sample)
    components = {}
    space_groups = {}
    for name, field in fields.items():
        if name in {"chemical_formula", "atom_types"} or str(field.get("group_id")) not in material_ids:
            continue
        if field.get("type") != "text":
            raise ValueError(f"Use a text field for material component metadata: {name!r}.")
        value = (field.get("value") or "").strip()
        key = "_".join(name.casefold().split())
        if key.endswith("_space_group"):
            if value:
                space_groups[key.removesuffix("_space_group")] = value
        else:
            key = key.removesuffix("_formula")
            if key in components:
                raise ValueError(f"More than one formula field matches material component {key!r}.")
            components[key] = (field.get("position") or 0, name, value)
    unmatched = space_groups.keys() - components.keys()
    if unmatched:
        names = ", ".join(sorted(unmatched))
        raise ValueError(f"Add matching formula fields in Materials for these space groups: {names}.")
    return [
        (name, formula, space_groups.get(key))
        for key, (_, name, formula) in sorted(components.items(), key=lambda item: item[1])
    ]


def single_velox_image(path):
    with h5py.File(path, "r") as emd:
        images = emd.get("Data/Image")
        if images is None or len(images) != 1:
            return None
        image, = images.values()
        shape = image["Data"].shape
        if len(shape) != 2 and (len(shape) != 3 or shape[-1] != 1):
            return None
        raw = image["Metadata"][:, 0].tobytes().split(b"\0", 1)[0]
        acquisition = json.loads(raw).get("Acquisition", {})
        stamp = acquisition.get("AcquisitionDatetime", {}).get("DateTime")
        return datetime.fromtimestamp(float(stamp), timezone.utc) if stamp else None


def choose_image(folder, requested):
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("The session Path must be an accessible acquisition directory.")
    candidates = [root / requested] if requested else sorted(
        (path for path in root.iterdir() if path.is_file() and path.suffix.lower() == ".emd"),
        key=lambda path: (path.stat().st_size, path.name),
    )
    for candidate in candidates:
        path = candidate.resolve(strict=True)
        if not path.is_relative_to(root) or path.suffix.lower() != ".emd":
            raise ValueError("Choose a Velox .emd file within the session folder.")
        acquired = single_velox_image(path)
        if acquired is not None:
            return path, acquired
    raise ValueError("No single-image Velox .emd with an acquisition timestamp was found.")


def notebook_data(session, fields, sample, specimen, microscope, acquired, zone, *, components=()):
    start = facility_time(fields["start_time"], zone)
    entry = {"experiment_alias": f"MatCommon test: {session['title']}", "start_time": utc_text(start)}
    end = None
    if fields.get("end_time"):
        end = facility_time(fields["end_time"], zone)
        if end < start:
            raise ValueError("The session end precedes the start.")
        entry["end_time"] = utc_text(end)

    notes = [
        f"Workflow test using eLabFTW experiment #{session['id']}, sample resource #{sample['id']}, "
        f"and microscope resource #{microscope['id']} ({microscope['title']}).",
        f"Embedded Velox acquisition timestamp: {utc_text(acquired)}.",
    ]
    if acquired < start or (end is not None and acquired > end) or acquired.astimezone(zone).date() != start.astimezone(zone).date():
        notes.append("The file timestamp is outside the notebook session. Specimen attribution for this image is unverified.")

    sample_data = {"name": sample["title"], "is_simulation": False}
    if formula := specimen.get("chemical_formula"):
        sample_data["chemical_formula"] = formula
    atoms = {value.strip() for value in (specimen.get("atom_types") or "").split(",") if value.strip()}
    formulas = [specimen.get("chemical_formula"), specimen.get("substrate_formula")]
    formulas.extend(formula for _, formula, _ in components)
    for formula in filter(None, formulas):
        try:
            atoms.update(Formula("".join(formula.split())).count())
        except ValueError as error:
            raise ValueError(f"Invalid chemical formula {formula!r} on sample {sample['id']}.") from error
    if atoms:
        sample_data["atom_types"] = ", ".join(sorted(atoms))
    if thickness := specimen.get("thickness"):
        magnitude, unit = thickness.split(maxsplit=1)
        sample_data["thickness"] = {"value": float(magnitude), "unit": unit}
    if prepared := specimen.get("preparation_date"):
        if len(prepared) == 10:
            notes.append(f"Sample preparation: noon local time assumed for the date-only record {prepared}.")
            prepared += "T12:00"
        sample_data["preparation_date"] = utc_text(facility_time(prepared, zone))
    entry["experiment_description"] = " ".join(notes)
    return {"entry": entry, "sample": sample_data}


def verify_image(path):
    images = []
    with h5py.File(path, "r") as nexus:
        entry = nexus["entry1"]
        if entry["definition"].asstr()[()] != "NXem":
            raise ValueError("The converter did not produce an NXem entry.")

        def collect(_, node):
            if isinstance(node, h5py.Group) and node.attrs.get("NX_class") == "NXdata":
                signal = node.attrs.get("signal")
                if signal and isinstance(node.get(signal), h5py.Dataset):
                    images.append(node[signal].shape)

        entry.visititems(collect)
    if len(images) != 1 or len(images[0]) != 2:
        raise ValueError(f"Expected one 2D NeXus image signal, found {images}.")
    return images[0]


def upload_to_playground(path):
    upload_id = load_config()["nomad"].get("playground_upload_id")
    if not upload_id:
        raise ValueError("Set nomad.playground_upload_id in config.yml.")
    with NOMADAPI.from_config() as client:
        project = client.get_upload(upload_id)
        if project.get("published") is not False:
            raise ValueError("The configured NOMAD playground must be unpublished.")
        result = client.add_file(upload_id, path)
        processing = result.get("processing") or {}
        entry = processing.get("entry") or {}
        if not processing.get("entry_id") or entry.get("process_status") != "SUCCESS":
            raise RuntimeError(f"NOMAD stored the file in upload {upload_id}, but the entry was not processed successfully.")
        print(f"NOMAD upload {upload_id}, entry {processing['entry_id']} ({processing.get('parser_name')}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", type=int)
    parser.add_argument("--image", type=Path, help="EMD file relative to the session folder")
    parser.add_argument("--output", type=Path, help="Output .nxs path. Defaults to a new temporary folder.")
    parser.add_argument("--timezone", default="Europe/Rome", help="IANA time zone for eLabFTW session times")
    parser.add_argument("--strict", action="store_true", help="Reject output if NXem validation fails")
    parser.add_argument("--upload", action="store_true", help="Add the result to the configured unpublished NOMAD playground")
    args = parser.parse_args()
    session, fields, sample, specimen, microscope = read_session(args.session_id)
    image, acquired = choose_image(fields["Path"], args.image)
    zone = ZoneInfo(args.timezone)
    components = material_components(sample)
    if any(name == "substrate_formula" for name, _, _ in components):
        # Only use the legacy substrate mapping for fields outside Materials.
        specimen.pop("substrate_formula", None)
    metadata = notebook_data(
        session, fields, sample, specimen, microscope, acquired, zone, components=components
    )
    print(metadata["entry"]["experiment_description"], flush=True)
    default_name = f"matcommon-session-{args.session_id}-image-test.nxs"
    output = args.output or (Path(mkdtemp(prefix="matcommon-image-")) / default_name)
    if output.suffix.lower() != ".nxs":
        raise ValueError("The output needs a .nxs file extension.")
    with TemporaryDirectory(dir=output.parent, prefix=".matcommon-") as scratch:
        scratch = Path(scratch)
        sidecar = scratch / "eln_data.yaml"
        sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        generated = scratch / output.name
        reader = Path(__file__).resolve().with_name("NXem")
        convert(
            (str(image), str(sidecar)), reader=str(reader), nxdl="NXem",
            output=str(generated), fail=args.strict,
            sample_atom_types=metadata["sample"].get("atom_types"),
            substrate_formula=specimen.get("substrate_formula"),
            sample_components=components,
            sample_physical_form=specimen.get("physical_form"),
            sample_support=(specimen.get("Support") or "").strip(),
            sample_parent_identifier=specimen.get("identifier_parent"),
        )
        shape = verify_image(generated)
        # Install the complete result without overwriting a previous conversion.
        output.hardlink_to(generated)
    print(f"Converted {image.name} to {output.resolve()} ({shape[0]} x {shape[1]} pixels).", flush=True)
    if args.upload:
        upload_to_playground(output)


if __name__ == "__main__":
    main()
