"""Utilities for recording intercepted HTTP requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class RequestRecord:
    method: str
    original_url: str
    proxied_url: str
    kwargs: dict[str, Any]
    context: dict[str, Any]


class RequestEmitter(Protocol):
    def emit(self, record: RequestRecord) -> None:  # pragma: no cover - interface
        ...


class NoopEmitter:
    def emit(self, record: RequestRecord) -> None:  # pragma: no cover
        return None


DEFAULT_EMITTER: RequestEmitter = NoopEmitter()
