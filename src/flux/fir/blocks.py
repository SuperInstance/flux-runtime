"""FIR Blocks, Functions, and Modules — the structural skeleton of a FIR program."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .types import TypeContext, FIRType, FuncType, StructType
from .values import Value
from .instructions import Instruction


@dataclass
class FIRBlock:
    """A basic block in SSA form. The last instruction must be a terminator."""
    label: str
    params: list[tuple[str, FIRType]] = field(default_factory=list)
    instructions: list[Instruction] = field(default_factory=list)

    @property
    def terminator(self) -> Optional[Instruction]:
        """Return the last instruction if it exists, else None."""
        return self.instructions[-1] if self.instructions else None


@dataclass
class FIRFunction:
    """A function composed of one or more basic blocks."""
    name: str
    sig: FuncType
    blocks: list[FIRBlock] = field(default_factory=list)

    @property
    def entry_block(self) -> FIRBlock:
        """The first block is the entry point."""
        return self.blocks[0]


@dataclass
class FIRModule:
    """Top-level container for a FIR program."""
    name: str
    type_ctx: TypeContext
    functions: dict[str, FIRFunction] = field(default_factory=dict)
    structs: dict[str, StructType] = field(default_factory=dict)
    globals: list = field(default_factory=list)  # list of (name, FIRType, initial_value)
