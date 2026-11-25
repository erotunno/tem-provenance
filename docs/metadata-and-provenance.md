# Metadata and provenance

The sample resource is the first record in the chain. The TEM session links it to the reusable microscope record and the acquisition directory. The export operates on the session and follows those explicit links.

| Source | What it contributes | Current NXem export |
| --- | --- | --- |
| eLabFTW Sample | Owner ID, lab identity, parent link, preparation, nominal composition and specimen form | `sample/identifier_owner`, `sample/identifier_sample`, `sample/identifier_parent`, `preparation_date`, `physical_form`, `thickness`, `chemical_formula`, `atom_types` and named sample components where provided |
| eLabFTW TEM Session | Session identity, objective, timing, linked resources and acquisition folder | `identifier_experiment`, `experiment_description`, `start_time` and `end_time` where provided. The exporter adds provenance notes to the description. |
| eLabFTW TEM Microscope | Stable inventory and instrument reference | Resolves the instrument linked to the session for context. The prototype records its reference and title in the provenance notes. Mapping the full inventory is follow-up work. |
| Velox EMD | Source image and embedded acquisition metadata | The stock EM reader provides image data, axes and supported acquisition settings. The source file is opened read-only. |

`identifier_sample` and `identifier_experiment` are persistent eLabFTW `elabid` values. Numeric eLabFTW record IDs serve as API lookup keys. The owner-supplied ID is preserved separately as the NXobject identifier `identifier_owner`. An older blank or `None` owner ID is omitted. A linked parent specimen has its own persistent eLabFTW ID.

## Specimen composition

Use a top-level formula for a single material. For multilayer or composite samples, add text fields named `[component_name]_formula` under **Materials**. Optionally add `[component_name]_space_group` with the same prefix. Each component formula goes into its own NXsample_component. The exporter derives the element list from the formulas and any supplied supplemental elements. A component describes the nominal sample. Image-to-layer attribution requires additional evidence and is a candidate for automation.

## Acquisition association

The session record selects the data folder and provides the time window. When the selected file's embedded timestamp fits that window, the event receives the same specimen ID as the session's sample. If the end time is missing, the test uses the start time and facility-local date. If the acquisition falls outside the window, the conversion flags specimen attribution as unverified and omits the event-level specimen ID. Timestamps are a consistency check on the explicitly linked records.

The prototype writes zero degrees for an unreported stage rotation and records that assumption. Operator free annotations, reception and storage information, and preparation notes remain in eLabFTW. The specimen's acquisition settings come from the source file when available.

## Analysis provenance in NOMAD

The intended Materials Commons workflow collects all acquisition data and associated metadata for a session and uploads the complete dataset to NOMAD. The current single-image pilot tests that same route and publishes no entries. Its optional upload creates a processed entry for one NXem derivative inside an existing unpublished upload. An integration with NOMAD Actions could preserve a reference to the original file and its checksum, record converter and definition versions, and publish a `workflow2` graph that links inputs, steps and outputs. The Action, dashboard, and downstream analyses are outside the current repository.

[FAIRmat NXem definition](https://fairmat-nfdi.github.io/nexus_definitions/classes/applications/NXem.html) · [Standalone EM conversion](https://fairmat-nfdi.github.io/pynxtools-em/tutorial/standalone.html)
