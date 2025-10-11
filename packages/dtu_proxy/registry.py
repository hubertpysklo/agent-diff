"""Interceptor registry for dtu_proxy.

This module defines the data structures used to register and resolve
interceptors for both standard HTTP traffic and MCP (Managed Control Plane)
event streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional


# ---------------------------------------------------------------------------
# Runtime context primitives
# ---------------------------------------------------------------------------


@dataclass
class ProxyContext:
    """Runtime parameters shared by interceptors during a proxy session."""

    platform_url: str
    api_key: str
    env_id: str

    def service_base(self, service: str) -> str:
        """Return the base URL for a service within the fake platform."""

        platform_url = self.platform_url.rstrip("/")
        return f"{platform_url}/api/env/{self.env_id}/services/{service.strip('/')}"


# ---------------------------------------------------------------------------
# HTTP interception
# ---------------------------------------------------------------------------


@dataclass
class HTTPDispatch:
    """Result of an HTTP interceptor invocation."""

    url: str
    kwargs: dict[str, Any]
    response: Any | None = None


class HTTPInterceptor:
    """Base class for HTTP interceptors.

    Subclasses should override :meth:`dispatch`. Returning a value in
    ``response`` short-circuits the request and the patched transport will
    return it immediately.
    """

    def dispatch(
        self, method: str, url: str, kwargs: dict[str, Any], *, context: ProxyContext
    ) -> HTTPDispatch:
        raise NotImplementedError


HTTPInterceptorFactory = Callable[[ProxyContext], HTTPInterceptor]


@dataclass
class HTTPInterceptorEntry:
    host: str
    factory: HTTPInterceptorFactory


# ---------------------------------------------------------------------------
# MCP interception
# ---------------------------------------------------------------------------


class MCPInterceptor:
    """Base class for MCP interceptors.

    MCP (Managed Control Plane) interactions typically happen over SSE where
    JSON-RPC messages are transported. Interceptors can either emulate the
    entire conversation locally or delegate specific requests to the real MCP
    upstream.
    """

    endpoint: str

    def begin_stream(self, *, context: ProxyContext) -> Iterable[bytes]:
        """Return an iterable that yields SSE payload bytes for the stream."""

        raise NotImplementedError

    def dispatch(self, payload: bytes, *, context: ProxyContext) -> bytes | None:
        """Handle an MCP payload sent by the client.

        Returning ``None`` indicates the interceptor does not consume the
        payload and the upstream MCP should receive it instead.
        """

        raise NotImplementedError


MCPInterceptorFactory = Callable[[ProxyContext], MCPInterceptor]


@dataclass
class MCPInterceptorEntry:
    endpoint: str
    factory: MCPInterceptorFactory


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class InterceptorRegistry:
    """Registry of interceptors addressable by host or endpoint."""

    def __init__(self) -> None:
        self._http_by_host: Dict[str, HTTPInterceptorFactory] = {}
        self._mcp_by_endpoint: Dict[str, MCPInterceptorFactory] = {}

    # HTTP interceptors -----------------------------------------------------

    def register_http(self, host: str, factory: HTTPInterceptorFactory) -> None:
        self._http_by_host[host.lower()] = factory

    def unregister_http(self, host: str) -> None:
        self._http_by_host.pop(host.lower(), None)

    def get_http(
        self, host: str, *, context: ProxyContext
    ) -> Optional[HTTPInterceptor]:
        factory = self._http_by_host.get(host.lower())
        if factory is None:
            return None
        return factory(context)

    # MCP interceptors ------------------------------------------------------

    def register_mcp(self, endpoint: str, factory: MCPInterceptorFactory) -> None:
        self._mcp_by_endpoint[endpoint] = factory

    def unregister_mcp(self, endpoint: str) -> None:
        self._mcp_by_endpoint.pop(endpoint, None)

    def get_mcp(
        self, endpoint: str, *, context: ProxyContext
    ) -> Optional[MCPInterceptor]:
        factory = self._mcp_by_endpoint.get(endpoint)
        if factory is None:
            return None
        return factory(context)


# Global registry instance used by default contexts.
GLOBAL_REGISTRY = InterceptorRegistry()
