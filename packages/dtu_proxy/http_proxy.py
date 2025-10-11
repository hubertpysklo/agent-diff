"""HTTP interception utilities for dtu_proxy.

This module implements monkey patches for the popular HTTP clients used by
agent frameworks: ``requests`` and ``httpx``. The patches consult the global
interceptor registry to decide whether outgoing requests need to be rerouted
to the fake service backend.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable

from .emitter import DEFAULT_EMITTER, RequestEmitter, RequestRecord
from .registry import GLOBAL_REGISTRY, HTTPDispatch, InterceptorRegistry, ProxyContext

try:  # Optional dependency
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

try:  # Optional dependency
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _normalize_host(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0].lower()


def _apply_registry_lookup(
    method: str,
    url: str,
    kwargs: dict[str, Any],
    *,
    context: ProxyContext,
    emitter: RequestEmitter,
    registry: InterceptorRegistry,
):
    host = _normalize_host(url)
    interceptor = registry.get_http(host, context=context)
    if interceptor is None:
        dispatch = HTTPDispatch(url=url, kwargs=kwargs)
    else:
        dispatch = interceptor.dispatch(method, url, kwargs, context=context)

    emitter.emit(
        RequestRecord(
            method=method,
            original_url=url,
            proxied_url=dispatch.url,
            kwargs=dispatch.kwargs,
            context={
                "env_id": context.env_id,
                "platform_url": context.platform_url,
                "api_key": context.api_key,
            },
        )
    )
    return dispatch


# ---------------------------------------------------------------------------
# requests patching
# ---------------------------------------------------------------------------


class _RequestsAdapterProxy:
    def __init__(
        self,
        send: Callable[..., Any],
        *,
        context: ProxyContext,
        emitter: RequestEmitter,
        registry: InterceptorRegistry,
    ):
        self._send = send
        self._context = context
        self._emitter = emitter
        self._registry = registry

    def __call__(self, request, **kwargs):
        dispatch = _apply_registry_lookup(
            request.method,
            request.url,
            kwargs,
            context=self._context,
            emitter=self._emitter,
            registry=self._registry,
        )
        if dispatch.response is not None:
            return dispatch.response
        request.url = dispatch.url
        return self._send(request, **dispatch.kwargs)


def patch_requests(
    *,
    context: ProxyContext,
    emitter: RequestEmitter = DEFAULT_EMITTER,
    registry: InterceptorRegistry = GLOBAL_REGISTRY,
) -> Callable[[], None]:
    if requests is None:  # pragma: no cover - optional dependency
        return lambda: None

    session_cls = requests.Session
    original_send = session_cls.send

    def patched_send(self, request, **kwargs):
        bound_send = original_send.__get__(self, session_cls)  # type: ignore[misc]
        proxy = _RequestsAdapterProxy(
            bound_send,
            context=context,
            emitter=emitter,
            registry=registry,
        )
        return proxy(request, **kwargs)

    session_cls.send = patched_send  # type: ignore[assignment]

    def restore():
        session_cls.send = original_send

    return restore


# ---------------------------------------------------------------------------
# httpx patching
# ---------------------------------------------------------------------------


class _HTTPXClientProxy:
    def __init__(
        self,
        send: Callable[..., Any],
        *,
        context: ProxyContext,
        emitter: RequestEmitter,
        registry: InterceptorRegistry,
    ):
        self._send = send
        self._context = context
        self._emitter = emitter
        self._registry = registry

    async def __call__(self, request, **kwargs):
        dispatch = _apply_registry_lookup(
            request.method,
            str(request.url),
            kwargs,
            context=self._context,
            emitter=self._emitter,
            registry=self._registry,
        )
        if dispatch.response is not None:
            return dispatch.response
        request.url = type(request.url)(dispatch.url)
        return await self._send(request, **dispatch.kwargs)


def patch_httpx(
    *,
    context: ProxyContext,
    emitter: RequestEmitter = DEFAULT_EMITTER,
    registry: InterceptorRegistry = GLOBAL_REGISTRY,
) -> Callable[[], None]:
    if httpx is None:  # pragma: no cover
        return lambda: None

    client_cls = httpx.Client
    async_client_cls = httpx.AsyncClient

    original_send = client_cls.send
    original_async_send = async_client_cls.send

    def patched_send(self, request, **kwargs):
        bound_send = original_send.__get__(self, client_cls)  # type: ignore[misc]
        proxy = _RequestsAdapterProxy(
            bound_send,
            context=context,
            emitter=emitter,
            registry=registry,
        )
        return proxy(request, **kwargs)

    async def patched_async_send(self, request, **kwargs):
        bound_send = original_async_send.__get__(self, async_client_cls)  # type: ignore[misc]
        proxy = _HTTPXClientProxy(
            bound_send,
            context=context,
            emitter=emitter,
            registry=registry,
        )
        return await proxy(request, **kwargs)

    client_cls.send = patched_send  # type: ignore[assignment]
    async_client_cls.send = patched_async_send  # type: ignore[assignment]

    def restore():
        client_cls.send = original_send
        async_client_cls.send = original_async_send

    return restore


# ---------------------------------------------------------------------------
# Compound context manager
# ---------------------------------------------------------------------------


@contextmanager
def http_proxy(
    context: ProxyContext,
    *,
    emitter: RequestEmitter = DEFAULT_EMITTER,
    registry: InterceptorRegistry = GLOBAL_REGISTRY,
):
    """Enable HTTP interception within the managed block."""

    revert_requests = patch_requests(
        context=context,
        emitter=emitter,
        registry=registry,
    )
    revert_httpx = patch_httpx(
        context=context,
        emitter=emitter,
        registry=registry,
    )
    try:
        yield
    finally:
        revert_httpx()
        revert_requests()
