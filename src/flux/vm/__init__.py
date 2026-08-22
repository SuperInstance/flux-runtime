"""FLUX Micro-VM — bytecode interpreter for the FLUX runtime system.

This module implements the execution engine that runs compiled FLUX bytecode
directly on raw bytes. It provides:

- **RegisterFile**: 64-register file (R0-R15 general, F0-F15 float, V0-V15 vector)
- **MemoryManager**: Linear region-based memory with ownership semantics
- **Interpreter**: Fetch-decode-execute loop with cycle budget
- **VM Errors**: Typed exception hierarchy for debugging
"""

from .interpreter import (
    Interpreter,
    VMDivisionByZeroError,
    VMError,
    VMHaltError,
    VMInvalidOpcodeError,
    VMStackOverflowError,
)
from .memory import MemoryManager, MemoryRegion
from .registers import RegisterFile

__all__ = [
    # Interpreter
    "Interpreter",
    "MemoryManager",
    # Memory
    "MemoryRegion",
    # Registers
    "RegisterFile",
    "VMDivisionByZeroError",
    # Errors
    "VMError",
    "VMHaltError",
    "VMInvalidOpcodeError",
    "VMStackOverflowError",
]
