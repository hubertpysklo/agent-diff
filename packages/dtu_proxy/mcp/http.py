"""HTTP client wrapper for MCP passthrough."""

from __future__ import annotations

import requests


def forward_request(method: str, url: str, **kwargs):
    response = requests.request(method, url, **kwargs)
    response.raise_for_status()
    return response
