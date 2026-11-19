"""Client for the eLabFTW REST API v2."""

from datetime import datetime
from html import escape
from io import BytesIO
import json
from urllib.parse import urlsplit

import requests


class ElabFTWAPI:
    """Read and update eLabFTW records through the API v2."""

    def __init__(self, base_url, api_key, *, timeout=(5, 30)):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("Set elabftw.base_url in config.yml.")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Set elabftw.api_key in config.yml or ELABFTW_API_KEY.")
        base_url = base_url.strip().rstrip("/")
        parts = urlsplit(base_url)
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.query or parts.fragment):
            raise ValueError("Use an eLabFTW server or API v2 URL.")
        self.base_url = base_url.removesuffix("/api/v2")
        self.api_url = self.base_url + "/api/v2"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": api_key.strip(), "Accept": "application/json"})

    @classmethod
    def from_config(cls, path=None):
        from config import load_config

        settings = load_config(path)["elabftw"]
        return cls(settings.get("base_url"), settings.get("api_key"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.session.close()

    def _request(self, method, path, **kwargs):
        response = self.session.request(
            method, self.api_url + path, timeout=self.timeout, allow_redirects=False, **kwargs
        )
        if 200 <= response.status_code < 300:
            return response
        status = response.status_code
        response.close()
        raise requests.HTTPError(f"eLabFTW {method} {path} returned HTTP {status}.", response=response)

    def _json(self, method, path, **kwargs):
        with self._request(method, path, **kwargs) as response:
            return response.json()

    @staticmethod
    def _id(value):
        text = str(value)
        if not text.isascii() or not text.isdecimal() or int(text) < 1:
            raise ValueError("Use a positive numeric eLabFTW record ID.")
        return int(text)

    def _entity_path(self, entity_type, entity_id):
        if entity_type not in ("experiments", "items"):
            raise ValueError("Entity type must be experiments or items.")
        return f"/{entity_type}/{self._id(entity_id)}"

    def get_info(self):
        return self._json("GET", "/info")

    def get_experiments(self, **filters):
        return self._json("GET", "/experiments", params=filters)

    def get_experiment(self, experiment_id):
        return self._json("GET", self._entity_path("experiments", experiment_id))

    def get_items(self, **filters):
        return self._json("GET", "/items", params=filters)

    def get_item(self, item_id):
        return self._json("GET", self._entity_path("items", item_id))

    def get_experiment_templates(self, **filters):
        return self._json("GET", "/experiments_templates", params=filters)

    def get_experiment_template(self, template_id):
        return self._json("GET", f"/experiments_templates/{self._id(template_id)}")

    def list_experiment_templates(self):
        for template in self.get_experiment_templates():
            print(f"ID: {template['id']:>4} | Title: {template['title']}")

    def get_resource_templates(self, **filters):
        return self._json("GET", "/items_types", params=filters)

    def get_resource_template(self, template_id):
        return self._json("GET", f"/items_types/{self._id(template_id)}")

    def create_resource_template(self, data):
        """Create a resource template and return its numeric ID."""
        with self._request("POST", "/items_types", json=self._editable(data)) as response:
            return self._created_id(response)

    def get_experiment_tags(self, experiment_id):
        return self._json("GET", self._entity_path("experiments", experiment_id) + "/tags")

    def get_item_links(self, entity_type, entity_id):
        return self._json("GET", self._entity_path(entity_type, entity_id) + "/items_links")

    def get_experiment_links(self, entity_type, entity_id):
        return self._json("GET", self._entity_path(entity_type, entity_id) + "/experiments_links")

    def get_experiment_uploads(self, experiment_id):
        return self._json("GET", self._entity_path("experiments", experiment_id) + "/uploads")

    def get_experiment_upload(self, experiment_id, upload_id):
        path = self._entity_path("experiments", experiment_id) + f"/uploads/{self._id(upload_id)}"
        return self._json("GET", path, params={"format": "json"})

    def get_apikeys(self):
        return self._json("GET", "/apikeys")

    @staticmethod
    def extra_fields(record):
        """Read the custom field definitions and values from a record."""
        metadata = record.get("metadata")
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata.strip() else None
        if metadata is None:
            return {}
        if not isinstance(metadata, dict):
            raise ValueError("The record metadata must be a JSON object.")
        fields = metadata.get("extra_fields")
        if fields is None:
            return {}
        if not isinstance(fields, dict):
            raise ValueError("The record's extra_fields must be a JSON object.")
        return fields

    @classmethod
    def _created_id(cls, response):
        path = urlsplit(response.headers.get("Location", "")).path.rstrip("/")
        return cls._id(path.rsplit("/", 1)[-1])

    @staticmethod
    def _editable(data):
        """Accept older callers that pass metadata as a serialized JSON object."""
        data = dict(data)
        for key in ("metadata", "metadatamerge"):
            if isinstance(data.get(key), str):
                data[key] = json.loads(data[key])
        return data

    def _create(self, entity_type, data, tags):
        tags = list(tags or [])
        with self._request("POST", f"/{entity_type}", json=self._editable(data)) as response:
            entity_id = self._created_id(response)
        path = self._entity_path(entity_type, entity_id)
        if tags:
            try:
                with self._request("POST", path + "/tags", json={"tags": tags}):
                    pass
            except requests.RequestException as error:
                raise RuntimeError(
                    f"eLabFTW created {path} but failed to add its tags. Review that record before retrying."
                ) from error
        return self._json("GET", path)

    def create_experiment(self, data, tags):
        return self._create("experiments", data, tags)

    def create_item(self, data, tags):
        return self._create("items", data, tags)

    def update_experiment(self, experiment_id, data):
        return self._json("PATCH", self._entity_path("experiments", experiment_id), json=self._editable(data))

    def post_metadata_field(self, experiment_id, field_name, value=""):
        fields = self.extra_fields(self.get_experiment(experiment_id))
        if field_name not in fields:
            raise KeyError(f"Custom field {field_name!r} is missing from experiment {experiment_id}.")
        data = {"metadatamerge": {"extra_fields": {field_name: {"value": value}}}}
        return self.update_experiment(experiment_id, data)

    def post_experiment_upload(self, experiment_id, fig_to_send, filename="image.png", comment=""):
        path = self._entity_path("experiments", experiment_id) + "/uploads"
        with BytesIO() as buffer:
            fig_to_send.savefig(buffer, format="png", dpi=300, bbox_inches="tight")
            buffer.seek(0)
            files = {"file": (filename, buffer, "image/png")}
            with self._request("POST", path, files=files, data={"comment": comment}) as response:
                return self._created_id(response)

    def log(self, experiment_id, figures, parameters):
        images = {}
        for title, figure in figures.items():
            upload_id = self.post_experiment_upload(experiment_id, figure, f"{title}.png")
            upload_data = self.get_experiment_upload(experiment_id, upload_id)
            images[title] = f"app/download.php?f={upload_data['long_name']}&storage=1"
        html = generate_experiment_table(images, parameters)
        updated = self.update_experiment(experiment_id, {"bodyappend": html})
        return {"body": updated["body"]}


def generate_experiment_table(images: dict, parameters: dict, timestamp: datetime = None) -> str:
    """
    Generate an HTML table containing experimental images on the left
    and categorized parameters on the right.

    Parameters
    ----------
    images : dict
        Dictionary mapping image titles (str) to image sources (str).
        The image sources can be URLs or base64-encoded data URIs.

    parameters : dict
        Nested dictionary containing parameter categories, versions, and parameter values.
        Structure:
        {
            "Microscope Status": {
                "module": "Automation",
                "data": {
                    "Accelerating Voltage (kV)": 200,
                    "Gun Vacuum (Pa)": 3e-7
                }
            },
            "Acquisition Conditions": {
                "module": "camera",
                "data": {
                    "Exposure Time (s)": 2.0,
                    "Camera Binning": "2x2"
                }
            }
        }

    timestamp : datetime, optional
        If None, current date & time will be used.
        If provided, must be a datetime object.

    Returns
    -------
    str
        HTML code for the generated table.
    """

    # Use provided timestamp or current time
    if timestamp is None:
        timestamp = datetime.now()

    # Format the timestamp in a readable form
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    # Start HTML with separator
    html = (
        '<div style="margin-top:30px; margin-bottom:10px;">\n'
        '  <hr style="border:1px solid #999;">\n'
        f'  <h4 style="margin:5px 0; font-size:18px; color:#333;">Recorded: {timestamp_str}</h4>\n'
    )

    # Start HTML table
    html += '<table style="width:100%; border-collapse:collapse;" border="1">\n'
    html += "  <tr>\n"

    # Left column: images
    html += '    <td style="width:40%; vertical-align:top; text-align:center;">\n'
    for title, src in images.items():
        html += f'      <div style="margin-bottom:10px;">\n'
        html += f'        <h4>{title}</h4>\n'
        html += f'        <img src="{escape(src)}" alt="{escape(str(title))}" style="max-width:100%; height:auto;">\n'
        html += f'      </div>\n'
    html += "    </td>\n"

    # Right column: parameters grouped by category
    html += '    <td style="width:60%; vertical-align:top;">\n'
    for category, content in parameters.items():
        module = content.get("module", "manual")
        data = content.get("data", {})

        # Category header
        html += f'      <h4 style="background-color:#f0f0f0; padding:5px;">{category} (in: {module})</h4>\n'
        html += f'      <table style="width:100%; border-collapse:collapse;" border="1">\n'

        for param, value in data.items():
            html += (
                f'        <tr>'
                f'<td style="width:35%; font-weight:bold; padding:3px;">{param}</td>'
                f'<td style="padding:3px;">{escape(str(value))}</td>'
                f'</tr>\n'
            )
        html += '      </table>\n'
        html += "      <br>\n"
    html += "    </td>\n"

    html += "  </tr>\n"
    html += "</table>"

    return html