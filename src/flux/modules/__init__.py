"""FLUX Nested Module System — Fractal Hot-Reload Hierarchy.

Provides hierarchical module containers at 8 granularity levels (TRAIN→CARD)
with independent hot-reloading, namespace isolation, and dependency tracking.
"""

from .granularity import (
    Granularity,
    GranularityMeta,
    get_granularity_meta,
)
from .card import (
    ModuleCard,
    CompileResult,
)
from .container import (
    ModuleContainer,
    ReloadResult,
)
from .reloader import (
    FractalReloader,
    ReloadEvent,
    GranularityRecommendation,
)
from .namespace import (
    ModuleNamespace,
    NameNotFoundError,
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
