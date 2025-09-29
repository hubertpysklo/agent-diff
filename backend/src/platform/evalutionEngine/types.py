from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, Tuple


Scope = Literal["inserts", "updates", "deletes", "any"]

Operator = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "contains",
    "not_contains",
    "starts_with",
    "not_starts_with",
    "ends_with",
    "not_ends_with",
    "is_null",
    "not_null",
]


@dataclass
class ExpectedInsert:
    scope: Literal["inserts"]
    table: str
    where: Mapping[str, Any] | None = None
    count: int | None = None
    min_count: int | None = None
    max_count: int | None = None


@dataclass
class ExpectedUpdate:
    scope: Literal["updates"]
    table: str
    pk: Mapping[str, Any] | None = None
    where_before: Mapping[str, Any] | None = None
    set: Mapping[str, Any] | None = None
    previous: Mapping[str, Any] | None = None
    not_changed: Sequence[str] | None = None
    count: int | None = None
    min_count: int | None = None
    max_count: int | None = None


@dataclass
class ForbiddenChange:
    scope: Scope
    table: str
    where: Mapping[str, Any] | None = None


@dataclass
class InvariantRowcount:
    scope: Literal["any"]
    table: str
    equals: int | None = None
    between: Tuple[int, int] | None = None


Assertion = ExpectedInsert | ExpectedUpdate | ForbiddenChange | InvariantRowcount
