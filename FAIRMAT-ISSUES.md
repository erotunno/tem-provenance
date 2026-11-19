# FAIRmat follow-ups

Issues found while converting a Velox TEM image to NXem and processing it in NOMAD Central. The workstation test used `pynxtools 0.16.0` and `pynxtools-em 0.4.6`. NOMAD Central reported version 2.0.1.

## NXem stage rotation for fixed holders

The Velox file reports a holder type, stage position, and alpha and beta tilts. The event-level `stageID` group in NXem requires a separate `rotation` field. Ask whether rotation should be optional when the holder has no rotation axis and how to represent an inapplicable value. The MatCommon test currently writes 0 degrees for an unreported rotation and records the assumption. [NXem stage definition](https://fairmat-nfdi.github.io/nexus_definitions/classes/applications/NXem.html#nxem-entry-measurement-eventid-instrument-stageid-group) · [Velox reader mapping](https://github.com/FAIRmat-NFDI/pynxtools-em/blob/v0.4.6/src/pynxtools_em/configurations/rsciio_velox_cfg.py)

## Reader profiling fields fail strict validation

The EM reader writes `profiling/architecture`, `profiling/operating_system`, and `profiling/template_filling_elapsed_time`. Strict validation rejects them as undocumented. Align the writer output and the bundled NXem definition so a file created by the reader can pass strict validation with this profiling information. [EM reader profiling code](https://github.com/FAIRmat-NFDI/pynxtools-em/blob/v0.4.6/src/pynxtools_em/utils/profiling.py)

## The ELN reader drops atom types when a formula is supplied

When `eln_data.yaml` supplies both `sample.chemical_formula` and `sample.atom_types`, the stock EM reader can write the formula while omitting `atom_types`, even though the NXem sample group requires it. Preserve explicitly supplied atom types alongside the formula. The MatCommon reader currently supplies the documented elements explicitly. [ELN reader implementation](https://github.com/FAIRmat-NFDI/pynxtools-em/blob/v0.4.6/src/pynxtools_em/parsers/oasis_eln.py) · [NXem atom types](https://fairmat-nfdi.github.io/nexus_definitions/classes/applications/NXem.html#nxem-entry-sampleid-atom-types-field)

## NOMAD skips formula normalization when atom types are present

A file containing both `NXsample/chemical_formula = Fe3Sn2` and `NXsample/atom_types = Fe, Sn` was parsed successfully. The archive preserved both NeXus fields and populated `results.material.elements`. The descriptive, reduced, Hill, and IUPAC formula fields stayed empty. The parser only calls formula normalization when the material section has yet to be initialized. Process the formula even when the element list has already initialized that section. In the film-on-substrate retest, NOMAD preserved Fe3Sn2 at the sample level and Al2O3 in the substrate component. The four formula summaries stayed blank, and the search index counted all four elements. Clarify how the Material summary should handle distinct component formulas. [NeXus parser implementation](https://github.com/FAIRmat-NFDI/pynxtools/blob/v0.16.0/src/pynxtools/nomad/parsers/parser.py)

## NOMAD material display omits the element count

For the same entry, the search API returned `results.material.n_elements = 2`. The processed archive omitted the derived field and the entry view displayed no value. Ask whether the Material section can display the derived count already available to search. [NOMAD material schema](https://github.com/FAIRmat-NFDI/nomad/blob/v2.0.1/nomad/datamodel/results.py)

## Display sample components and identify which are observed

A film-on-substrate image test preserved both formulas as structured NeXus data. NOMAD's Material summary showed the union of elements and provided no component-by-component view. Show component names and formulas separately. Discuss how NXem should associate an acquisition or region of interest with one or more components when the operator knows which layers were observed. The specimen inventory alone cannot establish that association. [NXsample components](https://fairmat-nfdi.github.io/nexus_definitions/classes/base_classes/NXsample.html#nxsample-sample-component-group) · [NXem event data](https://fairmat-nfdi.github.io/nexus_definitions/classes/base_classes/NXem_event_data.html)
