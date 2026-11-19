"""Load the workstation configuration and optional environment credentials."""

import os
from pathlib import Path

import yaml


CONFIG_PATH = Path(__file__).resolve().with_name("config.yml")


def load_config(path=None):
    path = CONFIG_PATH if path is None else Path(path)
    with path.open(encoding="utf-8") as stream:
        settings = yaml.safe_load(stream)
    if not isinstance(settings, dict):
        raise ValueError("The master configuration must be a YAML mapping.")
    for section, env_key in (
        ("elabftw", "ELABFTW_API_KEY"),
        ("nomad", "NOMAD_API_KEY"),
        ("data", None),
    ):
        values = settings.get(section)
        if not isinstance(values, dict):
            raise ValueError(f"Expected a {section!r} mapping in {path.name}.")
        if env_key and (key := os.environ.get(env_key)):
            values["api_key"] = key
    return settings
