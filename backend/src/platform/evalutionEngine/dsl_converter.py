from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


IdentifiersValues = Literal[
    "table",
    "column",
    "row",
]

Operators = Literal["inserts", "updates", "deletes"]

Comparators = Literal[
    "eq",
    "gt",
    "lt",
    "in",
    "not in",
    "contains",
    "not contains",
    "starts with",
    "not starts with",
    "ends with",
    "not ends with",
    "is",
    "inserts",
    "updates",
    "deletes",
    "any",
    "and",
    "or",
]


@dataclass
class DSL:
    where: str
