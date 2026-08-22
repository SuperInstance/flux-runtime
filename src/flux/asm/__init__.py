"""FLUX Cross-Assembler — text assembly to bytecode with macros, includes, and linking.

Provides:
- AsmError: structured error with source location tracking
- MacroPreprocessor: #define, #ifdef, #endif, #undef, #include support
- CrossAssembler: full assembler with labels, expressions, multiple output formats
- FluxLinker: combines multiple object files into executables
- BinaryPatcher: binary patching utilities
- ElfHeader: ELF-like header generation for executables
"""

from .binary_patcher import BinaryPatcher
from .cross_assembler import AssemblyResult, CrossAssembler, OutputFormat
from .elf_header import ElfHeader
from .errors import AsmError, AsmErrorKind
from .linker import FluxLinker, ObjectFile
from .macros import MacroPreprocessor

__all__ = [
    "AsmError",
    "AsmErrorKind",
    "AssemblyResult",
    "BinaryPatcher",
    "CrossAssembler",
    "ElfHeader",
    "FluxLinker",
    "MacroPreprocessor",
    "ObjectFile",
    "OutputFormat",
]
