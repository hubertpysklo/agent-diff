"""MCP interception manager."""

from __future__ import annotations

from typing import Dict

from ..registry import GLOBAL_REGISTRY, ProxyContext


class MCPProxy:
    def __init__(self, *, context: ProxyContext):
        self._context = context

    def get_interceptor(self, endpoint: str):
        return GLOBAL_REGISTRY.get_mcp(endpoint, context=self._context)
