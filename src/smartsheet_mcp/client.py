"""Minimal Smartsheet REST client (Bearer token)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE = "https://api.smartsheet.com/2.0"


class SmartsheetAPIError(Exception):
    """Smartsheet returned resultCode != 0 or an unexpected HTTP error."""

    def __init__(self, message: str, *, status_code: int | None = None, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _base_url() -> str:
    return os.environ.get("SMARTSHEET_BASE_URL", DEFAULT_BASE).rstrip("/")


def _token() -> str:
    token = os.environ.get("SMARTSHEET_ACCESS_TOKEN")
    if not token:
        raise SmartsheetAPIError(
            "SMARTSHEET_ACCESS_TOKEN is not set. Add it to the MCP server environment.",
        )
    return token


def _check_smartsheet_result(data: dict[str, Any]) -> None:
    rc = data.get("resultCode")
    if rc is not None and rc != 0:
        msg = data.get("message", "Smartsheet API error")
        raise SmartsheetAPIError(msg, payload=data)


class SmartsheetClient:
    """Sync HTTP client for Smartsheet API v2."""

    def __init__(self) -> None:
        self._http = httpx.Client(
            base_url=_base_url(),
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=httpx.Timeout(60.0),
        )

    def close(self) -> None:
        self._http.close()

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> dict[str, Any]:
        """Perform a request and return the parsed JSON object (Smartsheet envelopes)."""
        r = self._http.request(method, path, params=params, json=json_body)
        if r.headers.get("content-type", "").startswith("application/json"):
            data = r.json()
        else:
            data = {"raw": r.text}

        if not isinstance(data, dict):
            raise SmartsheetAPIError(f"Unexpected JSON response type: {type(data).__name__}", status_code=r.status_code)

        if r.status_code >= 400:
            msg = str(data.get("message", r.text or r.reason_phrase))
            raise SmartsheetAPIError(msg, status_code=r.status_code, payload=data)

        _check_smartsheet_result(data)
        return data

    # --- convenience methods ---

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_json("GET", path, params=params)

    def post(self, path: str, *, json_body: Any = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_json("POST", path, params=params, json_body=json_body)

    def put(self, path: str, *, json_body: Any = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_json("PUT", path, params=params, json_body=json_body)

    def delete(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_json("DELETE", path, params=params)


_client: SmartsheetClient | None = None


def get_client() -> SmartsheetClient:
    global _client
    if _client is None:
        _client = SmartsheetClient()
    return _client


def reset_client() -> None:
    """Close and drop the singleton (mainly for tests)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
