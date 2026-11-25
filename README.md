# TEM Provenance

An eLabFTW-to-NXem prototype for tracing TEM acquisitions back to sample reception. Start with the numeric ID of a TEM session in eLabFTW. The workstation exporter resolves the linked specimen and microscope, combines notebook metadata with one Velox image, and writes a NeXus file for NOMAD.

## What the lab records

1. **At reception**, create an eLabFTW Sample resource. Record the owner's specimen ID, provider, preparation and any known composition. Register a parent specimen separately when relevant.
2. **At the start of the measurement**, instantiate the TEM Session template. Link one Sample and one TEM Microscope in the template fields. Set the facility-local start time and the path to the acquisition folder. Use the structured `experiment_description` for the objective and the notebook body for free annotations.
3. **After acquisition**, record the end time when known and run the exporter once the source files are complete. Reuse the microscope resource across sessions on that instrument.

See [eLabFTW templates](elabftw-templates/README.md) for setup and [metadata mapping](docs/metadata-and-provenance.md) for the sources, precedence and remaining gaps.

## Run the exporter

The prototype was tested on a Linux workstation with Python 3.10. Run it from a machine that can read the eLabFTW API and the acquisition folder written in the session's `Path`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.yml config.yml
chmod 600 config.yml
```

Set the eLabFTW URL and key in `config.yml`, or inject the key through `ELABFTW_API_KEY`. The key needs read access to the session and its linked resources. `Path` must be a directory accessible to the runner. The prototype resolves this field directly. The `data.folder` setting is reserved for future storage mapping.

```sh
.venv/bin/python export_tem_image.py SESSION_ID --image 'image.emd' --output image.nxs
```

Replace `SESSION_ID` with the numeric experiment ID. `--image` is a filename relative to the session folder. If omitted, the exporter selects the smallest eligible `.emd` in that folder. It currently accepts a single two-dimensional Velox image with an embedded acquisition timestamp. Omit `--output` to use a new temporary directory. The exporter refuses to overwrite an existing output.

Use `--timezone` if the facility is outside `Europe/Rome`. Enter session timestamps in facility-local time. The exporter converts them to UTC, rejects ambiguous or nonexistent local times, and uses noon local time for legacy date-only specimen preparation records. It flags acquisitions outside the recorded session as unverified.

## Optional NOMAD upload

Set `nomad.base_url` to the deployment's API URL ending in `/api/v1`, set `nomad.playground_upload_id` to an existing unpublished upload, and supply a token through `NOMAD_API_KEY` or the local configuration. The token needs access to read and write the target upload. Add `--upload` to the export command. The exporter checks that the upload is unpublished and reports the processed entry ID on success. Keep `config.yml`, source data and generated outputs outside the repository.

## Tested scope

One Velox image was converted to NXem and processed in an unpublished NOMAD Central test upload. The exporter also checks locally for a single 2D signal. Run with `--strict` to require validation success. The pinned reader currently emits three undocumented profiling fields that can cause strict validation to fail. See [FAIRmat follow-ups](FAIRMAT-ISSUES.md).

Folder-wide export, spectra, automatic image-to-layer assignment and integration with a NOMAD Action are follow-up work. A future Action can call the headless conversion step and keep analysis inputs, parameters and outputs linked in the NOMAD workflow.
