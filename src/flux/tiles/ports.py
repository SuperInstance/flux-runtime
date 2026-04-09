"""Tile Ports — typed connection points on a tile."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..fir.types import FIRType


class PortDirection(Enum):
    """Direction of data flow through a port."""
    INPUT = "input"
    OUTPUT = "output"


@dataclass(frozen=True)
class CoercionInfo:
    """Describes how to convert data between two port types."""
    cost: float  # 0 = identity, higher = more expensive
    from_type_name: str
    to_type_name: str
    method: str  # "trunc", "zext", "sext", "ftrunc", "fext", "bitcast", "none"


@dataclass
class TilePort:
    """A named, typed connection point on a tile."""
    name: str
    direction: PortDirection
    type_fir: FIRType
    shape: Optional[tuple] = None

    def compatible_with(self, other: TilePort) -> bool:
        """Can data flow from this port to the other?

        Requires opposite directions and compatible types.
        """
        if self.direction == other.direction:
            return False
        # Types must have the same Python class (e.g., both IntType)
        return type(self.type_fir) is type(other.type_fir)

    def coerce_to(self, target_type: FIRType) -> CoercionInfo:
        """How to convert data from this port's type to target_type."""
        src = type(self.type_fir).__name__
        dst = type(target_type).__name__

        # Identity
        if self.type_fir == target_type:
            return CoercionInfo(cost=0, from_type_name=src, to_type_name=dst, method="none")

        # Int→Int coercion
        from ..fir.types import IntType
        if isinstance(self.type_fir, IntType) and isinstance(target_type, IntType):
            if self.type_fir.bits > target_type.bits:
                return CoercionInfo(cost=1, from_type_name=src, to_type_name=dst, method="trunc")
            elif self.type_fir.bits < target_type.bits:
                method = "sext" if self.type_fir.signed else "zext"
                return CoercionInfo(cost=1, from_type_name=src, to_type_name=dst, method=method)
            else:
                return CoercionInfo(cost=0, from_type_name=src, to_type_name=dst, method="none")

        # Float→Float coercion
        from ..fir.types import FloatType
        if isinstance(self.type_fir, FloatType) and isinstance(target_type, FloatType):
            if self.type_fir.bits > target_type.bits:
                return CoercionInfo(cost=1, from_type_name=src, to_type_name=dst, method="ftrunc")
            elif self.type_fir.bits < target_type.bits:
                return CoercionInfo(cost=1, from_type_name=src, to_type_name=dst, method="fext")
            else:
                return CoercionInfo(cost=0, from_type_name=src, to_type_name=dst, method="none")

        # Int↔Float is possible but expensive
        if isinstance(self.type_fir, (IntType, FloatType)) and isinstance(target_type, (IntType, FloatType)):
            return CoercionInfo(cost=5, from_type_name=src, to_type_name=dst, method="bitcast")

        # Bitcast as fallback
        return CoercionInfo(cost=10, from_type_name=src, to_type_name=dst, method="bitcast")

    def __repr__(self) -> str:
        shape_str = f", shape={self.shape}" if self.shape else ""
        return f"TilePort({self.name!r}, {self.direction.value}, {self.type_fir}{shape_str})"
