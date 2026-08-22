"""FLUX Self-Documentation System — generates documentation by introspecting the codebase."""

from .generator import (
    DocumentationGenerator,
)
from .introspector import (
    APIDeclaration,
    CodeIntrospector,
    ComplexityMetrics,
    ModuleInfo,
)
from .renderer import (
    AsciiRenderer,
    MarkdownRenderer,
)
from .stats import (
    CodeStatistics,
)

__all__ = [
    # Introspection
    "CodeIntrospector",
    "ModuleInfo",
    "APIDeclaration",
    "ComplexityMetrics",
    # Rendering
    "MarkdownRenderer",
    "AsciiRenderer",
    # Statistics
    "CodeStatistics",
    # Generator
    "DocumentationGenerator",
]
