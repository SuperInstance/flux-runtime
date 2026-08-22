"""FLUX Nested Module System — Fractal Hot-Reload Hierarchy.

Provides hierarchical module containers at 8 granularity levels (TRAIN→CARD)
with independent hot-reloading, namespace isolation, and dependency tracking.
"""

from .card import (
    CompileResult,
    ModuleCard,
)
from .container import (
    ModuleContainer,
    ReloadResult,
)
from .granularity import (
    Granularity,
    GranularityMeta,
    get_granularity_meta,
)
from .namespace import (
    ModuleNamespace,
    NameNotFoundError,
)
from .reloader import (
    FractalReloader,
    GranularityRecommendation,
    ReloadEvent,
)

__all__ = [
    "CompileResult",
    # Reloader
    "FractalReloader",
    # Granularity
    "Granularity",
    "GranularityMeta",
    "GranularityRecommendation",
    # Card
    "ModuleCard",
    # Container
    "ModuleContainer",
    # Namespace
    "ModuleNamespace",
    "NameNotFoundError",
    "ReloadEvent",
    "ReloadResult",
    "get_granularity_meta",
]
