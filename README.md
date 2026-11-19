# Materials Commons

Materials Commons connects eLabFTW session records with TEM acquisition data. The planned workflow starts with an eLabFTW experiment ID, gathers the associated records and files, converts the measurement to NXem, and prepares it for NOMAD.

## Session conventions

- Create a sample resource when the specimen enters the lab. Create the session experiment when the microscope session begins.
- Link exactly **one sample** and **one TEM microscope resource** to the session. Reuse the existing microscope resource for each session on that instrument.
- Ignore unrelated resource links, such as project records and sample-preparation instruments. If the sample or TEM resource is missing or ambiguous, the exporter should stop and report the problem.
- Use the session’s `Path` field for the folder containing all acquisition files for that session. The workflow needs to resolve that path from the workstation or runner.
- Export after acquisition and file writing are complete. Use eLabFTW for specimen provenance and instrument inventory, and use the acquisition files for the data and per-acquisition settings.

## Session timestamps

eLabFTW stores `start_time` and `end_time` as local date and time values without a UTC offset. Click **Now** at the start and end of the session when the computer running the browser is set to the microscope facility's time zone. If entering a time later or from another time zone, enter the actual facility-local time manually. Leave the end time blank until known.

The converter must interpret these values in the configured facility time zone. Use `Europe/Rome` for the current QEM workflow and apply the offset for the date of the session. Export UTC ISO 8601 timestamps with a `Z` suffix to NXem. For example, `2026-11-19T14:00` in Rome becomes `2026-11-19T13:00:00Z`.

If a daylight-saving transition makes a local time ambiguous or nonexistent, flag it for clarification before converting it.

## Workstation setup

The working copy on the workstation is at `/home/enzo/materialscommon`. It already has a `.venv`. For a fresh checkout, run the following from the project root.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.yml config.yml
chmod 600 config.yml
```

Fill in `elabftw.base_url` and `elabftw.api_key` for eLabFTW reads. You can supply the key through `ELABFTW_API_KEY` instead. Set `data.folder` to the acquisition storage root as seen by the runner when needed. The `nomad` section configures the Oasis connection when it is available. Keep live values in the ignored `config.yml`.

## Read-only client check

Run this from the project root. Use any experiment ID your API key can read.

```sh
.venv/bin/python - <<'PY'
from ElabFTW.Client import ElabFTWAPI

experiment_id = 3
with ElabFTWAPI.from_config() as client:
    experiment = client.get_experiment(experiment_id)
    links = client.get_item_links("experiments", experiment_id)
    print(experiment["id"], experiment["title"])
    print(f"Linked resources: {len(links)}")
PY
```

The eLabFTW client already reads experiments, resources, links, and custom fields. Keep the sample and TEM selection rules in the export workflow. Add client helpers when there is a concrete use for them, such as an iterator if multiple callers need to page through experiments.

## Standalone NXem conversion

Tested on the workstation with `pynxtools==0.16.0` and `pynxtools-em==0.4.6`. Install these into a fresh project environment when testing conversion.

```sh
.venv/bin/python -m pip install 'pynxtools==0.16.0' 'pynxtools-em==0.4.6'
.venv/bin/pynx convert acquisition.emd eln_data.yaml --reader em --nxdl NXem --output session.nxs
.venv/bin/pynx validate session.nxs
```

The EM reader combines the acquisition data and embedded metadata with recognized fields from `eln_data.yaml`. Build that YAML from eLabFTW using keys the EM reader actually maps, such as `entry.start_time`, `entry.end_time`, `sample.name`, `sample.preparation_date`, `sample.atom_types`, and `sample.thickness` with `value` and `unit`. Quote timestamps to keep them as strings. Keep acquisition values such as accelerating voltage with the individual measurement. Use the instrument resource for stable inventory fields and the session notebook for context.

For additional NXem destinations outside the stock YAML mapping, a small project reader can extend the EM reader and add explicit fields before validation and writing. A workstation test confirmed that one NeXus file can contain an image stack and voltage from a public Velox file, synthetic specimen and timing fields from YAML, and an instrument location from a separate JSON source. Use `--fail` for production exports so invalid required fields stop the write. The public test fixture is missing a required stage rotation.

Convert and validate on the workstation, then upload the resulting file through the NOMAD API once Oasis is available. [Standalone EM converter](https://fairmat-nfdi.github.io/pynxtools-em/tutorial/standalone.html) · [ELN field mapping](https://github.com/FAIRmat-NFDI/pynxtools-em/blob/v0.4.6/src/pynxtools_em/configurations/oasis_eln_cfg.py) · [NOMAD API upload](https://fairmat-nfdi.github.io/pynxtools/how-tos/pynxtools/use-with-nomad.html)

## Upload to NOMAD

Set `nomad.base_url` to the Oasis API URL, such as `https://oasis.example.org/api/v1`. Set `nomad.api_key` in `config.yml` or supply the raw bearer token through `NOMAD_API_KEY`. On NOMAD deployments with personal access token scopes, use `uploads:read` and `uploads:write` for this workflow.

Once the NeXus file has passed validation, use the client from the project root.

```python
from NOMAD.Client import NOMADAPI

with NOMADAPI.from_config() as client:
    upload_id = client.create_upload("session.nxs", name="MatCommon TEM session")
    print("NOMAD upload", upload_id)
    upload = client.wait_for_processing(upload_id)
    entries = client.list_entries(upload_id)
    print(upload["process_status"], entries["pagination"]["total"], "entries")
    print("Failed entries", entries.get("processing_failed"))
```

The upload stays unpublished. Save the upload ID as soon as it is returned so processing can be checked again after a timeout. Inspect the entry count and the failed-entry count, since a completed upload can contain entries that failed to parse. Pass `pagination.next_page_after_value` back as `page_after_value` to get the next page. Use `get_entry_archive(entry_id)` to read a processed entry.

[NOMAD API definition](https://nomad-lab.eu/backend/api/v1/extensions/docs) · [NOMAD Python upload guide](https://docs.nomad-lab.eu/howto/manage/program/publish_python.html)
