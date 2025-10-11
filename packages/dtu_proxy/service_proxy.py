"""User-facing context manager configuring HTTP and MCP proxies."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterable

from .http_proxy import http_proxy
from .registry import GLOBAL_REGISTRY, ProxyContext


@contextmanager
def service_proxy(
    *,
    platform_url: str,
    api_key: str,
    env_id: str,
    registry=GLOBAL_REGISTRY,
):
    """Activate HTTP interceptors inside the managed block."""

    context = ProxyContext(platform_url=platform_url, api_key=api_key, env_id=env_id)
    with ExitStack() as stack:
        stack.enter_context(http_proxy(context=context, registry=registry))
        yield context
