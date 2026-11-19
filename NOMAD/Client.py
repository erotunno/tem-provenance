"""Minimal client for NOMAD's uploads and processed entries API."""

import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests


class NOMADProcessingError(RuntimeError):
    """NOMAD finished processing an upload with a failure."""

    def __init__(self, upload_id, upload):
        self.upload = upload
        message = upload.get("last_status_message") or "See the upload's processing errors."
        super().__init__(f"NOMAD processing failed for {upload_id}: {message}")


class NOMADAPI:
    """Create unpublished NOMAD uploads and inspect their results."""

    def __init__(self, base_url, api_key=None):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("Set nomad.base_url in config.yml to the deployment's API URL.")
        base_url = base_url.strip().rstrip("/")
        parts = urlsplit(base_url)
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.query or parts.fragment):
            raise ValueError("Use a NOMAD deployment URL or an API URL ending in /api/v1.")
        self.api_url = base_url if base_url.endswith("/api/v1") else base_url + "/api/v1"
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("The NOMAD API key must be a string.")
        if api_key and (token := api_key.strip()):
            self.session.headers["Authorization"] = f"Bearer {token}"

    @classmethod
    def from_config(cls, path=None):
        from config import load_config

        settings = load_config(path)["nomad"]
        return cls(settings.get("base_url"), settings.get("api_key"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.session.close()

    def _json(self, method, path, *, timeout=(5, 30), **kwargs):
        with self.session.request(
            method, self.api_url + path, timeout=timeout, allow_redirects=False, **kwargs
        ) as response:
            if not 200 <= response.status_code < 300:
                raise requests.HTTPError(
                    f"NOMAD {method} {path} returned HTTP {response.status_code}.",
                    response=response,
                )
            return response.json()

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
            raise ValueError("Use a valid NOMAD upload or entry ID.")
        return value

    def get_info(self):
        return self._json("GET", "/info")

    def create_upload(self, file_path=None, *, name=None, timeout=(5, 600)):
        """Create an unpublished upload, optionally streaming a file or archive."""
        if "Authorization" not in self.session.headers:
            raise ValueError("Set nomad.api_key in config.yml or NOMAD_API_KEY.")
        params = {"upload_name": name, "publish_directly": "false"}
        if file_path is None:
            result = self._json("POST", "/uploads", params=params, timeout=timeout)
        else:
            path = Path(file_path)
            params["file_name"] = path.name
            with path.open("rb") as stream:
                result = self._json(
                    "POST", "/uploads", params=params, data=stream,
                    headers={"Content-Type": "application/octet-stream"}, timeout=timeout,
                )
        upload_id = result.get("upload_id") or (result.get("data") or {}).get("upload_id")
        if not upload_id:
            raise RuntimeError("NOMAD accepted the upload but did not return an upload ID.")
        return self._id(upload_id)

    def add_file(self, upload_id, file_path, *, timeout=(5, 600)):
        """Add one file to an existing upload, waiting for processing."""
        if "Authorization" not in self.session.headers:
            raise ValueError("Set nomad.api_key in config.yml or NOMAD_API_KEY.")
        path = Path(file_path)
        params = {"file_name": path.name, "overwrite_if_exists": "false", "wait_for_processing": "true"}
        with path.open("rb") as stream:
            return self._json(
                "PUT", f"/uploads/{self._id(upload_id)}/raw/", params=params, data=stream,
                headers={"Content-Type": "application/octet-stream"}, timeout=timeout,
            )

    def list_uploads(self, **filters):
        """Read a page of accessible uploads with its pagination information."""
        return self._json("GET", "/uploads", params=filters)

    def get_upload(self, upload_id, *, timeout=(5, 30)):
        return self._json("GET", f"/uploads/{self._id(upload_id)}", timeout=timeout)["data"]

    def wait_for_processing(self, upload_id, *, timeout=600, interval=2):
        """Return a successfully processed upload or raise with its upload ID."""
        if not 0 < interval < float("inf") or not 0 < timeout < float("inf"):
            raise ValueError("Use finite, positive processing timeout and poll interval values.")
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            upload = self.get_upload(upload_id, timeout=(min(5, remaining), min(30, remaining)))
            status = upload.get("process_status")
            if not upload["process_running"]:
                if status == "SUCCESS":
                    return upload
                if status in {"FAILURE", "DELETED"}:
                    raise NOMADProcessingError(upload_id, upload)
            time.sleep(max(0, min(interval, deadline - time.monotonic())))
        raise TimeoutError(f"NOMAD processing did not finish in {timeout:g}s for upload {upload_id}.")

    def list_entries(self, upload_id, **pagination):
        """Read an upload's entry page, including counts of successes and failures."""
        return self._json("GET", f"/uploads/{self._id(upload_id)}/entries", params=pagination)

    def get_entry_archive(self, entry_id):
        """Read the processed archive for a NOMAD entry."""
        return self._json("GET", f"/entries/{self._id(entry_id)}/archive")["data"]["archive"]
