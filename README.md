# TEM Provenance

A Materials Commons eLabFTW-to-NXem prototype for tracing TEM acquisitions back to sample reception. Start with the numeric ID of a TEM session in eLabFTW. The workstation exporter resolves the linked specimen and microscope, combines notebook metadata with one Velox image, and writes a NeXus file for NOMAD. The intended workflow uses that same session ID and metadata to collect every acquisition and upload the complete session dataset to NOMAD.

## Run the exporter

Run these commands from the repository folder on a Linux workstation that can access eLabFTW and the acquisition folder in the session's `Path`. The exporter was tested with Python 3.10.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.yml config.yml
chmod 600 config.yml
```

Set the eLabFTW URL and key in `config.yml`, or inject the key through `ELABFTW_API_KEY`. The key needs read access to the session and its linked resources. `Path` must be a directory accessible to the runner. The prototype resolves this field directly. The `data.folder` setting is reserved for future storage mapping.

Copy this block and enter the numeric ID of the **TEM Session experiment** when prompted.

```sh
printf 'eLabFTW session ID: '
read -r session_id
.venv/bin/python export_tem_image.py "$session_id" --output "session-${session_id}.nxs"
```

The command selects the smallest eligible `.emd` in the session folder and writes `session-<ID>.nxs` in the current directory. The exporter currently accepts one two-dimensional Velox image with an embedded acquisition timestamp. To choose a specific file, pass its filename relative to the session folder.

```sh
.venv/bin/python export_tem_image.py "$session_id" --image 'image.emd' --output selected-image.nxs
```

Replace `image.emd` with the filename in the session folder. Omit `--output` to use a new temporary directory. The exporter refuses to overwrite an existing output.

Use `--timezone` if the facility is outside `Europe/Rome`. Enter session timestamps in facility-local time. The exporter converts them to UTC, rejects ambiguous or nonexistent local times, and uses noon local time for legacy date-only specimen preparation records. It flags acquisitions outside the recorded session as unverified.

## Optional NOMAD upload

Set `nomad.base_url` to the deployment's API URL ending in `/api/v1`, set `nomad.playground_upload_id` to an existing unpublished upload, and supply a token through `NOMAD_API_KEY` or the local configuration. The token needs access to read and write the target upload. Run this command after setting `session_id` as shown above.

```sh
.venv/bin/python export_tem_image.py "$session_id" --upload
```

This runs the conversion and adds the resulting file to the configured unpublished upload. The exporter reports the processed entry ID on success. Keep `config.yml`, source data and generated outputs outside the repository.

## What the lab records

1. **At reception**, create an eLabFTW Sample resource. Record the owner's specimen ID, provider, preparation and any known composition. Register a parent specimen separately when relevant.
2. **At the start of the measurement**, instantiate the TEM Session template. Link one Sample and one TEM Microscope in the template fields. Set the facility-local start time and the path to the acquisition folder. Use the structured `experiment_description` for the objective and the notebook body for free annotations.
3. **After acquisition**, record the end time when known and run the exporter once the source files are complete. Reuse the microscope resource across sessions on that instrument.

See [eLabFTW templates](elabftw-templates/README.md) for setup and [metadata mapping](docs/metadata-and-provenance.md) for the sources, precedence and remaining gaps.

## Tested scope

One Velox image was converted to NXem and processed in an unpublished NOMAD Central test upload. The exporter also checks locally for a single 2D signal. Run with `--strict` to require validation success. The pinned reader currently emits three undocumented profiling fields that can cause strict validation to fail. See [FAIRmat follow-ups](FAIRMAT-ISSUES.md).

The full-session workflow will collect all acquisition data and associated metadata from the session folder, including images and spectra, and upload the complete dataset to NOMAD. The single-image test exercises that pipeline on one input. A future NOMAD Action can call the headless conversion step and link analysis inputs, parameters and outputs. Automatic image-to-layer assignment remains a separate follow-up.
