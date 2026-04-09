"""Adaptive Language Selector + Profiler — dynamic language selection based on runtime profiling.

The adaptive subsystem dynamically chooses the best language for each module
based on real-time profiling, balancing speed vs. modularity vs. expressiveness.

  Hot path (bottleneck)  → recompile to C with SIMD
  Warm path              → TypeScript → C#
  Cool path              → keep Python (more expressive, more modular)

Usage:
    from flux.adaptive import AdaptiveProfiler, AdaptiveSelector, CompilerBridge

    profiler = AdaptiveProfiler()
    # ... record execution samples ...
    selector = AdaptiveSelector(profiler)
    rec = selector.recommend("my_module")
    print(rec.recommended_language)  # e.g. "c_simd"
"""

from .profiler import (
    AdaptiveProfiler,
    HeatLevel,
    ProfileSample,
    SampleHandle,
    BottleneckEntry,
    BottleneckReport,
)
from .selector import (
    LanguageProfile,
    LANGUAGES,
    AdaptiveSelector,
    SelectionEvent,
    LanguageRecommendation,
)
from .compiler_bridge import (
    CompilerBridge,
    LanguageCompiler,
    RecompileResult,
)

__all__ = [
    # Profiler
    "AdaptiveProfiler",
    "HeatLevel",
    "ProfileSample",
    "SampleHandle",
    "BottleneckEntry",
    "BottleneckReport",
    # Selector
    "LanguageProfile",
    "LANGUAGES",
    "AdaptiveSelector",
    "SelectionEvent",
    "LanguageRecommendation",
    # Compiler Bridge
    "CompilerBridge",
    "LanguageCompiler",
    "RecompileResult",
]
