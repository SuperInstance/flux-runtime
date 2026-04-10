"""FLUX Self-Documentation System — generates documentation by introspecting the codebase."""

from .introspector import (
    CodeIntrospector,
    ModuleInfo,
    APIDeclaration,
    ComplexityMetrics,
)
from .renderer import (
    MarkdownRenderer,
    AsciiRenderer,
)
from .stats import (
    CodeStatistics,
)
from .generator import (
    DocumentationGenerator,
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
