"""FLUX Cross-Assembler — text assembly to bytecode with macros, includes, and linking.

Provides:
- AsmError: structured error with source location tracking
- MacroPreprocessor: #define, #ifdef, #endif, #undef, #include support
- CrossAssembler: full assembler with labels, expressions, multiple output formats
- FluxLinker: combines multiple object files into executables
- BinaryPatcher: binary patching utilities
- ElfHeader: ELF-like header generation for executables
"""

from .errors import AsmError, AsmErrorKind
from .macros import MacroPreprocessor
from .cross_assembler import CrossAssembler, OutputFormat, AssemblyResult
from .linker import FluxLinker, ObjectFile
from .binary_patcher import BinaryPatcher
from .elf_header import ElfHeader

__all__ = [
    "AsmError",
    "AsmErrorKind",
    "MacroPreprocessor",
    "CrossAssembler",
    "OutputFormat",
    "AssemblyResult",
    "FluxLinker",
    "ObjectFile",
    "BinaryPatcher",
    "ElfHeader",
]
