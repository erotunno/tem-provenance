"""MatCommon defaults applied after the stock electron microscopy reader."""

import re

from pynxtools_em.reader import EMReader


EVENT_PATH = re.compile(r"/ENTRY\[[^\]]+\]/measurement/eventID\[[^\]]+\](?=/)")
STAGE_FIELD = re.compile(
    r"(/ENTRY\[[^\]]+\])/measurement/eventID\[[^\]]+\]"
    r"/instrument/stageID\[[^\]]+\]/(?:design|tilt1|tilt2|position)"
)


class MatCommonEMReader(EMReader):
    """Add eLabFTW context and the agreed stage rotation default before validation."""

    def read(
        self, template, file_paths, *, sample_atom_types=None, substrate_formula=None,
        sample_components=(), sample_physical_form=None, sample_support=None,
        sample_parent_identifier=None, experiment_identifier=None, sample_identifier=None,
        sample_owner_identifier=None, link_event_to_sample=False, **kwargs
    ):
        data = super().read(template=template, file_paths=file_paths, **kwargs)
        entry = "/ENTRY[entry1]"
        sample = f"{entry}/sampleID[sample]"
        if experiment_identifier:
            data[f"{entry}/identifier_experiment"] = experiment_identifier
        if sample_identifier:
            data[f"{sample}/identifier_sample"] = sample_identifier
            data[f"{sample}/identifier_sample/@type"] = "eLabFTW elabid"
            data[f"{sample}/identifier_sample/@type_custom"] = True
            if link_event_to_sample:
                events = {match.group() for path in data if (match := EVENT_PATH.match(path))}
                for event in events:
                    field = f"{event}/identifier_sample"
                    if not data.get(field):
                        data[field] = sample_identifier
        if sample_owner_identifier:
            data[f"{sample}/identifierNAME[identifier_owner]"] = sample_owner_identifier
            data[f"{sample}/identifierNAME[identifier_owner]/@type"] = "sample owner identifier"
            data[f"{sample}/identifierNAME[identifier_owner]/@type_custom"] = True
        if sample_atom_types:
            data[f"{sample}/atom_types"] = sample_atom_types
        if substrate_formula:
            substrate = f"{sample}/SAMPLE_COMPONENT[substrate]"
            data[f"{substrate}/name"] = "Substrate"
            data[f"{substrate}/chemical_formula"] = substrate_formula
        support = f"{sample}/SAMPLE_COMPONENT[support]"
        if sample_support:
            data[f"{support}/name"] = sample_support
        for index, (field_name, formula, space_group) in enumerate(sample_components, start=1):
            name = field_name.removesuffix("_formula")
            component = support if name == sample_support else f"{sample}/SAMPLE_COMPONENT[component_{index}]"
            data[f"{component}/name"] = name
            if formula:
                data[f"{component}/chemical_formula"] = formula
            if space_group:
                data[f"{component}/space_group"] = space_group
        if sample_physical_form:
            data[f"{sample}/physical_form"] = sample_physical_form
        if sample_parent_identifier:
            data[f"{sample}/identifier_parent"] = sample_parent_identifier
            data[f"{sample}/identifier_parent/@type"] = "eLabFTW elabid"
            data[f"{sample}/identifier_parent/@type_custom"] = True
        stages = {
            (path.rsplit("/", 1)[0], match.group(1))
            for path in data
            if (match := STAGE_FIELD.fullmatch(path))
        }
        defaults = set()
        for stage, entry in stages:
            rotation = f"{stage}/rotation"
            if data.get(rotation) is None:
                data[rotation] = 0.0
                data[f"{rotation}/@units"] = "degree"
                defaults.add(entry)
        for entry in defaults:
            description = f"{entry}/experiment_description"
            note = "Stage rotation assumed to be 0 degrees where the acquisition did not report a value."
            data[description] = " ".join(filter(None, (data.get(description), note)))
        return data


READER = MatCommonEMReader
