"""FIR SSA Values — each value is defined by exactly one instruction."""

from __future__ import annotations
from dataclasses import dataclass, field

from .types import FIRType


@dataclass
class Value:
    """An SSA value defined by a single instruction."""
    id: int
    name: str  # human-readable name like "x", "tmp1"
    type: FIRType

    def __repr__(self) -> str:
        return f"%{self.name}:{self.type}"
