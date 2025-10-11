"""Linear MCP interceptor implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from ..registry import MCPInterceptor, ProxyContext


@dataclass
class LinearMCPInterceptor(MCPInterceptor):
    endpoint = "https://mcp.linear.app/sse"

    def begin_stream(self, *, context: ProxyContext) -> Iterable[bytes]:
        init_payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {
                        "name": "Linear Fake MCP",
                        "version": "0.1.0",
                    },
                },
            }
        ).encode()
        yield b"data: " + init_payload + b"\n\n"

    def dispatch(self, payload: bytes, *, context: ProxyContext) -> bytes | None:
        message = json.loads(payload.decode())
        method = message.get("method")

        if method == "tools/list":
            return self._handle_tools_list(message, context=context)

        if method == "tools/call":
            result = self._handle_tools_call(message, context=context)
            if result is not None:
                return result

        return None

    def _handle_tools_list(
        self, message: Dict[str, Any], *, context: ProxyContext
    ) -> bytes:
        tools = [  # Placeholder tool descriptors
            {
                "name": "list_issues",
                "title": "List issues",
                "description": "List issues in the test workspace",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        response = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"tools": tools},
        }
        return json.dumps(response).encode()

    def _handle_tools_call(
        self, message: Dict[str, Any], *, context: ProxyContext
    ) -> Optional[bytes]:
        params = message.get("params", {})
        name = params.get("name")

        if name == "list_issues":
            result = self._call_platform("GET", "/issues", context=context)
            payload = {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(result)},
                    ]
                },
            }
            return json.dumps(payload).encode()

        return None

    def _call_platform(self, method: str, path: str, *, context: ProxyContext):
        import requests

        url = f"{context.service_base('linear')}/{path.lstrip('/')}"
        response = requests.request(
            method,
            url,
            headers={"x-platform-api-key": context.api_key},
        )
        response.raise_for_status()
        return response.json()
