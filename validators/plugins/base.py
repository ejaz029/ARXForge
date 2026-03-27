from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any


@dataclass(frozen=True)
class ValidatorPlugin:
    id: str
    name: str
    severity: str
    applies_to: str
    schema_version: str
    order: int
    run: Callable[[], dict[str, Any]]

