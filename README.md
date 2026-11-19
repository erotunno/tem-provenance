# Materials Commons

Materials Commons connects eLabFTW session records with TEM acquisition data. The planned workflow starts with an eLabFTW experiment ID, gathers the associated records and files, converts the measurement to NXem, and prepares it for NOMAD.

## Session conventions

- Create a sample resource when the specimen enters the lab. Create the session experiment when the microscope session begins.
- Link exactly **one sample** and **one TEM microscope resource** to the session. Reuse the existing microscope resource for each session on that instrument.
- Ignore unrelated resource links, such as project records and sample-preparation instruments. If the sample or TEM resource is missing or ambiguous, the exporter should stop and report the problem.
- Use the session’s `Path` field for the folder containing all acquisition files for that session. The workflow needs to resolve that path from the workstation or runner.
- Export after acquisition and file writing are complete. Use eLabFTW for specimen provenance and instrument inventory, and use the acquisition files for the data and per-acquisition settings.

## Workstation setup

The working copy on the workstation is at `/home/enzo/materialscommon`. It already has a `.venv`. For a fresh checkout, run the following from the project root.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n config.example.yml config.yml
chmod 600 config.yml
```

Fill in `elabftw.base_url` and `elabftw.api_key` for eLabFTW reads. You can supply the key through `ELABFTW_API_KEY` instead. Set `data.folder` to the acquisition storage root as seen by the runner when needed. The `nomad` section is reserved for the future Oasis connection. Keep live values in the ignored `config.yml`.

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
