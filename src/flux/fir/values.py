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
    const_value: int | float | None = None  # For constant materialization

    def is_const(self) -> bool:
        """Check if this value represents a constant."""
        return self.const_value is not None

    def __repr__(self) -> str:
        return f"%{self.name}:{self.type}"
