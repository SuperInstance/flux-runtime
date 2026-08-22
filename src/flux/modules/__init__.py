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
    # Granularity
    "Granularity",
    "GranularityMeta",
    "get_granularity_meta",
    # Card
    "ModuleCard",
    "CompileResult",
    # Container
    "ModuleContainer",
    "ReloadResult",
    # Reloader
    "FractalReloader",
    "ReloadEvent",
    "GranularityRecommendation",
    # Namespace
    "ModuleNamespace",
    "NameNotFoundError",
]
