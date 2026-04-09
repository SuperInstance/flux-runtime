"""MAST AST Node definitions for FLUX.MD.

All nodes carry a SourceSpan for error reporting and source mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    """Tracks a contiguous region of source text."""

    line_start: int
    line_end: int
    col_start: int
    col_end: int

    def __repr__(self) -> str:
        return (
            f"SourceSpan(lines={self.line_start}-{self.line_end}, "
            f"cols={self.col_start}-{self.col_end})"
        )


@dataclass
class LocatedNode:
    """Base class — every AST node has a source span."""

    span: SourceSpan


@dataclass
class FluxModule(LocatedNode):
    """Root node of a parsed FLUX.MD document."""

    frontmatter: dict[str, Any]
    children: list[LocatedNode]


@dataclass
class Heading(LocatedNode):
    """Markdown heading: # through ######."""

    level: int
    text: str


@dataclass
class Paragraph(LocatedNode):
    """Plain text paragraph."""

    text: str


@dataclass
class CodeBlock(LocatedNode):
    """Fenced code block. *meta* is everything after the language tag."""

    lang: str
    content: str
    meta: str


@dataclass
class FluxCodeBlock(CodeBlock):
    """Code block whose lang is ``flux`` (or ``flux-type``)."""


@dataclass
class DataBlock(CodeBlock):
    """Code block whose lang is ``json``, ``yaml``, or ``toml``."""


@dataclass
class NativeBlock(CodeBlock):
    """Code block in any other language (python, c, rust …)."""


@dataclass
class ListBlock(LocatedNode):
    """Ordered or unordered list."""

    ordered: bool
    items: list[ListItem]


@dataclass
class ListItem(LocatedNode):
    """Single item inside a ListBlock."""

    text: str
    children: list[LocatedNode] = field(default_factory=list)


@dataclass
class AgentDirective(LocatedNode):
    """``## agent:`` or ``## fn:`` heading extracted into a directive."""

    name: str
    args: dict[str, Any]
    body: list[LocatedNode] = field(default_factory=list)


@dataclass
class FluxTypeError(LocatedNode):
    """Error node produced when a type / syntax issue is detected."""

    message: str
