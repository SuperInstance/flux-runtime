"""FIR Type System — immutable, hashable types with interning via TypeContext."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Base ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FIRType:
    """Base type. All types carry a type_id for fast identity comparison."""
    type_id: int


# ── Primitive types ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IntType(FIRType):
    bits: int
    signed: bool


@dataclass(frozen=True)
class FloatType(FIRType):
    bits: int  # 16, 32, 64


@dataclass(frozen=True)
class BoolType(FIRType):
    pass


@dataclass(frozen=True)
class UnitType(FIRType):
    pass


@dataclass(frozen=True)
class StringType(FIRType):
    pass


# ── Composite types ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RefType(FIRType):
    element: FIRType


@dataclass(frozen=True)
class ArrayType(FIRType):
    element: FIRType
    length: int


@dataclass(frozen=True)
class VectorType(FIRType):
    element: FIRType
    lanes: int  # SIMD, e.g. <4 x f32>


@dataclass(frozen=True)
class FuncType(FIRType):
    params: tuple  # tuple of FIRType
    returns: tuple  # tuple of FIRType


@dataclass(frozen=True)
class StructType(FIRType):
    name: str
    fields: tuple  # tuple of (name, FIRType)


@dataclass(frozen=True)
class EnumType(FIRType):
    name: str
    variants: tuple  # tuple of (name, FIRType | None)


# ── Domain-specific types ──────────────────────────────────────────────────

@dataclass(frozen=True)
class RegionType(FIRType):
    name: str  # memory region qualifier


@dataclass(frozen=True)
class CapabilityType(FIRType):
    permission: str
    resource: str


@dataclass(frozen=True)
class AgentType(FIRType):
    """Represents an agent identifier."""
    pass


@dataclass(frozen=True)
class TrustType(FIRType):
    """Represents a trust level (f32)."""
    pass


# ── Type interning context ─────────────────────────────────────────────────

class TypeContext:
    """Interns types so identity comparison works (same params → same object)."""

    def __init__(self):
        self._types: dict[tuple[type, tuple], FIRType] = {}
        self._next_id: int = 2  # 0 and 1 reserved for class-level shorthands

    def _intern(self, cls: type, key: tuple, **kwargs) -> FIRType:
        entry = (cls, key)
        if entry not in self._types:
            tid = self._next_id
            self._next_id += 1
            self._types[entry] = cls(type_id=tid, **kwargs)
        return self._types[entry]

    # ── Constructors ────────────────────────────────────────────────────

    def get_int(self, bits: int, signed: bool = True) -> IntType:
        return self._intern(IntType, (bits, signed), bits=bits, signed=signed)

    def get_float(self, bits: int) -> FloatType:
        return self._intern(FloatType, (bits,), bits=bits)

    def get_bool(self) -> BoolType:
        return self._intern(BoolType, ())

    def get_unit(self) -> UnitType:
        return self._intern(UnitType, ())

    def get_string(self) -> StringType:
        return self._intern(StringType, ())

    def get_ref(self, element: FIRType) -> RefType:
        return self._intern(RefType, (element,), element=element)

    def get_array(self, element: FIRType, length: int) -> ArrayType:
        return self._intern(ArrayType, (element, length), element=element, length=length)

    def get_vector(self, element: FIRType, lanes: int) -> VectorType:
        return self._intern(VectorType, (element, lanes), element=element, lanes=lanes)

    def get_func(self, params: tuple, returns: tuple) -> FuncType:
        return self._intern(FuncType, (params, returns), params=params, returns=returns)

    def get_struct(self, name: str, fields: tuple) -> StructType:
        return self._intern(StructType, (name, fields), name=name, fields=fields)

    def get_enum(self, name: str, variants: tuple) -> EnumType:
        return self._intern(EnumType, (name, variants), name=name, variants=variants)

    def get_region(self, name: str) -> RegionType:
        return self._intern(RegionType, (name,), name=name)

    def get_capability(self, perm: str, resource: str) -> CapabilityType:
        return self._intern(CapabilityType, (perm, resource), permission=perm, resource=resource)

    def get_agent(self) -> AgentType:
        return self._intern(AgentType, ())

    def get_trust(self) -> TrustType:
        return self._intern(TrustType, ())


# ── Class-level shorthands (canonical singletons) ──────────────────────────

TypeContext.i32 = IntType(type_id=0, bits=32, signed=True)
TypeContext.f32 = FloatType(type_id=1, bits=32)
