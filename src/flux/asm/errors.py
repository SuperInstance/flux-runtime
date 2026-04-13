"""Assembly error types with source location tracking.

Provides structured error messages with file name, line number, column,
and error kind for precise diagnostics during assembly.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class AsmErrorKind(Enum):
    """Category of assembly error."""
    SYNTAX = "syntax error"
    UNKNOWN_OPCODE = "unknown opcode"
    UNKNOWN_REGISTER = "unknown register"
    INVALID_OPERAND = "invalid operand"
    UNDEFINED_LABEL = "undefined label"
    DUPLICATE_LABEL = "duplicate label"
    MISSING_OPERAND = "missing operand"
    TOO_MANY_OPERANDS = "too many operands"
    MACRO_ERROR = "macro error"
    INCLUDE_ERROR = "include error"
    PATCH_ERROR = "patch error"
    LINKER_ERROR = "linker error"
    ELF_ERROR = "ELF header error"
    IO_ERROR = "I/O error"
    INTERNAL = "internal error"
    UNDEFINED_MACRO = "undefined macro"
    DIVISION_BY_ZERO = "division by zero"
    RANGE_ERROR = "value out of range"
    TYPE_MISMATCH = "type mismatch"
    OVERFLOW = "integer overflow"


@dataclass
class SourceLocation:
    """Tracks source file location for error reporting."""
    file: str = "<unknown>"
    line: int = 0
    column: int = 0
    source_line: str = ""

    def __str__(self) -> str:
        loc = f"{self.file}"
        if self.line > 0:
            loc += f":{self.line}"
            if self.column > 0:
                loc += f":{self.column}"
        return loc

    def context_lines(self) -> list[str]:
        """Return lines showing the error context with a caret pointer."""
        lines = []
        if self.source_line:
            lines.append(f"  {self.source_line}")
            if self.column > 0:
                lines.append(f"  {' ' * (self.column - 1)}^")
        return lines


@dataclass
class AsmError(Exception):
    """Structured assembly error with source location.

    Attributes:
        message: Human-readable error description.
        kind: Error category for programmatic handling.
        location: Source file location where the error occurred.
        hints: Optional list of suggestion strings.
    """
    message: str
    kind: AsmErrorKind = AsmErrorKind.SYNTAX
    location: SourceLocation = field(default_factory=SourceLocation)
    hints: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = [f"{self.location}: {self.kind.value}: {self.message}"]
        ctx = self.location.context_lines()
        if ctx:
            parts.extend(ctx)
        for hint in self.hints:
            parts.append(f"  hint: {hint}")
        return "\n".join(parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AsmError):
            return NotImplemented
        return (self.message == other.message
                and self.kind == other.kind
                and self.location.file == other.location.file
                and self.location.line == other.location.line)


def make_error(
    message: str,
    kind: AsmErrorKind = AsmErrorKind.SYNTAX,
    file: str = "<unknown>",
    line: int = 0,
    column: int = 0,
    source_line: str = "",
    hints: Optional[list[str]] = None,
) -> AsmError:
    """Convenience factory for creating AsmError instances."""
    return AsmError(
        message=message,
        kind=kind,
        location=SourceLocation(file=file, line=line, column=column, source_line=source_line),
        hints=hints or [],
    )
