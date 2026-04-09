"""Adaptive language selection engine.

Selects the optimal target language for each module based on real-time
profiling data. The selector balances three competing axes:

  Speed           — how fast the compiled code runs
  Expressiveness  — how easy it is to write and modify
  Modularity      — how well it composes with other modules

The tradeoff mirrors a DJ choosing between a 909 drum machine (fast, rigid)
vs. a live jazz sample (expressive, flexible) based on what the moment needs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .profiler import AdaptiveProfiler, HeatLevel


# ── Language Profiles ───────────────────────────────────────────────────

@dataclass(frozen=True)
class LanguageProfile:
    """Metadata about a target language.

    Attributes:
        name: Language identifier key.
        speed_tier: Execution speed (0=slowest, 10=fastest).
        expressiveness_tier: Ease of writing/maintaining (0=least, 10=most).
        modularity_tier: How well it composes (0=least, 10=most).
        compile_time_tier: Compile speed (0=fastest, 10=slowest).
        hot_reload_support: Whether the language supports hot reloading.
        simd_support: Whether the language supports SIMD intrinsics.
        memory_safety: Whether the language provides memory safety (GC/Rust borrow checker).
    """
    name: str
    speed_tier: int = 5
    expressiveness_tier: int = 5
    modularity_tier: int = 5
    compile_time_tier: int = 5
    hot_reload_support: bool = True
    simd_support: bool = False
    memory_safety: bool = True


# Predefined language profiles — ordered by speed tier
LANGUAGES: dict[str, LanguageProfile] = {
    "python": LanguageProfile(
        name="python",
        speed_tier=3,
        expressiveness_tier=10,
        modularity_tier=9,
        compile_time_tier=0,
        hot_reload_support=True,
        simd_support=False,
        memory_safety=True,
    ),
    "typescript": LanguageProfile(
        name="typescript",
        speed_tier=5,
        expressiveness_tier=8,
        modularity_tier=8,
        compile_time_tier=2,
        hot_reload_support=True,
        simd_support=False,
        memory_safety=True,
    ),
    "csharp": LanguageProfile(
        name="csharp",
        speed_tier=7,
        expressiveness_tier=6,
        modularity_tier=7,
        compile_time_tier=5,
        hot_reload_support=False,
        simd_support=False,
        memory_safety=True,
    ),
    "rust": LanguageProfile(
        name="rust",
        speed_tier=9,
        expressiveness_tier=5,
        modularity_tier=8,
        compile_time_tier=8,
        hot_reload_support=False,
        simd_support=True,
        memory_safety=True,
    ),
    "c": LanguageProfile(
        name="c",
        speed_tier=9,
        expressiveness_tier=3,
        modularity_tier=5,
        compile_time_tier=7,
        hot_reload_support=False,
        simd_support=True,
        memory_safety=False,
    ),
    "c_simd": LanguageProfile(
        name="c_simd",
        speed_tier=10,
        expressiveness_tier=2,
        modularity_tier=3,
        compile_time_tier=9,
        hot_reload_support=False,
        simd_support=True,
        memory_safety=False,
    ),
}


# ── Selection Events ────────────────────────────────────────────────────

@dataclass
class SelectionEvent:
    """Record of a language selection decision."""
    module_path: str
    old_language: Optional[str]
    new_language: str
    heat_level: HeatLevel
    reason: str
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class LanguageRecommendation:
    """Recommended language for a module."""
    module_path: str
    recommended_language: str
    current_language: Optional[str]
    heat_level: HeatLevel
    speed_score: float
    expressiveness_score: float
    modularity_score: float
    reason: str
    estimated_speedup: float = 1.0
    should_change: bool = False


# ── Selector ────────────────────────────────────────────────────────────

class AdaptiveSelector:
    """Selects optimal language for each module based on profiling data.

    Algorithm for each module:
      1. Check manual overrides (take precedence)
      2. Get heat level from profiler
      3. FROZEN → keep current language
      4. COOL   → maximize expressiveness (Python)
      5. WARM   → balance speed and expressiveness (TypeScript)
      6. HOT    → lean toward speed (C# or Rust)
      7. HEAT   → maximize speed (C+SIMD)
      8. Adjust for reload frequency (penalize slow-compile languages)
      9. Adjust for module complexity (penalize low-expressiveness)

    Args:
        profiler: The AdaptiveProfiler providing execution data.
    """

    def __init__(self, profiler: AdaptiveProfiler) -> None:
        self.profiler = profiler
        self._current_languages: dict[str, str] = {}
        self._overrides: dict[str, str] = {}
        self._selection_log: list[SelectionEvent] = []
        self._reload_counts: dict[str, int] = {}

    # ── Core Selection ──────────────────────────────────────────────────

    def recommend(self, module_path: str) -> LanguageRecommendation:
        """Recommend the best language for a module based on profiling.

        Args:
            module_path: Dot-separated module identifier.

        Returns:
            LanguageRecommendation with scores and reasoning.
        """
        # 1. Manual override
        if module_path in self._overrides:
            lang = self._overrides[module_path]
            current = self._current_languages.get(module_path)
            heatmap = self.profiler.get_heatmap()
            heat = heatmap.get(module_path, HeatLevel.FROZEN)
            profile = LANGUAGES[lang]
            return LanguageRecommendation(
                module_path=module_path,
                recommended_language=lang,
                current_language=current,
                heat_level=heat,
                speed_score=profile.speed_tier / 10.0,
                expressiveness_score=profile.expressiveness_tier / 10.0,
                modularity_score=profile.modularity_tier / 10.0,
                reason="Manual override applied.",
            )

        # 2. Get heat level
        heatmap = self.profiler.get_heatmap()
        heat = heatmap.get(module_path, HeatLevel.FROZEN)
        current = self._current_languages.get(module_path, "python")

        # 3. Select based on heat
        if heat == HeatLevel.FROZEN:
            lang = "python"
            reason = "Module never called — default to Python for maximum expressiveness."
        elif heat == HeatLevel.COOL:
            lang = "python"
            reason = "Rarely called — keep in Python for expressiveness and modularity."
        elif heat == HeatLevel.WARM:
            lang = self._select_warm(module_path)
            reason = f"Moderately called — {lang} balances speed and expressiveness."
        elif heat == HeatLevel.HOT:
            lang = self._select_hot(module_path)
            reason = f"Frequently called — {lang} provides significant speed improvement."
        else:  # HEAT
            lang = self._select_heat(module_path)
            reason = f"Critical bottleneck — {lang} maximizes throughput."

        profile = LANGUAGES[lang]
        estimated_speedup = self.profiler.estimate_speedup(module_path, lang)
        should_change = lang != current

        return LanguageRecommendation(
            module_path=module_path,
            recommended_language=lang,
            current_language=current,
            heat_level=heat,
            speed_score=profile.speed_tier / 10.0,
            expressiveness_score=profile.expressiveness_tier / 10.0,
            modularity_score=profile.modularity_tier / 10.0,
            reason=reason,
            estimated_speedup=estimated_speedup,
            should_change=should_change,
        )

    def select_all(self) -> dict[str, LanguageRecommendation]:
        """Recommend languages for all profiled modules.

        Returns:
            Mapping from module_path to LanguageRecommendation.
        """
        heatmap = self.profiler.get_heatmap()
        results: dict[str, LanguageRecommendation] = {}
        for mod in heatmap:
            results[mod] = self.recommend(mod)
        # Also include modules with overrides that may not be in heatmap
        for mod in self._overrides:
            if mod not in results:
                results[mod] = self.recommend(mod)
        return results

    def apply_recommendation(
        self, module_path: str, lang: str
    ) -> None:
        """Record that a module has been recompiled to a new language.

        Args:
            module_path: Dot-separated module identifier.
            lang: Target language key.

        Raises:
            ValueError: If lang is not a known language.
        """
        if lang not in LANGUAGES:
            raise ValueError(
                f"Unknown language: {lang}. "
                f"Available: {sorted(LANGUAGES.keys())}"
            )

        old_lang = self._current_languages.get(module_path)
        heatmap = self.profiler.get_heatmap()
        heat = heatmap.get(module_path, HeatLevel.FROZEN)

        self._current_languages[module_path] = lang

        event = SelectionEvent(
            module_path=module_path,
            old_language=old_lang,
            new_language=lang,
            heat_level=heat,
            reason="Recommendation applied.",
        )
        self._selection_log.append(event)

    # ── Overrides ───────────────────────────────────────────────────────

    def set_override(self, module_path: str, lang: str) -> None:
        """Set a manual language override for a module.

        Args:
            module_path: Dot-separated module identifier.
            lang: Target language key.

        Raises:
            ValueError: If lang is not a known language.
        """
        if lang not in LANGUAGES:
            raise ValueError(
                f"Unknown language: {lang}. "
                f"Available: {sorted(LANGUAGES.keys())}"
            )
        self._overrides[module_path] = lang

    def clear_override(self, module_path: str) -> None:
        """Remove a manual language override.

        Args:
            module_path: Dot-separated module identifier.
        """
        self._overrides.pop(module_path, None)

    # ── Analysis ────────────────────────────────────────────────────────

    def get_bandwidth_allocation(self) -> dict[str, float]:
        """Compute what fraction of total execution time each module consumes.

        Returns:
            Mapping from module_path to fraction of total time (0.0 to 1.0).
        """
        total_times = self.profiler.total_time_ns
        total = sum(total_times.values())
        if total == 0:
            return {}

        return {
            mod: t / total
            for mod, t in total_times.items()
        }

    def get_modularity_score(self) -> float:
        """Compute overall system modularity score (0.0 to 1.0).

        Higher = more modular (more Python-like modules).
        Score is the weighted average of modularity_tier across all
        assigned modules, weighted by their bandwidth allocation.
        """
        bandwidth = self.get_bandwidth_allocation()
        if not bandwidth:
            return 0.5  # neutral default

        score = 0.0
        for mod, weight in bandwidth.items():
            lang = self._current_languages.get(mod, "python")
            profile = LANGUAGES.get(lang)
            if profile:
                score += weight * (profile.modularity_tier / 10.0)

        return score

    def get_selection_log(self) -> list[SelectionEvent]:
        """Get the history of all selection decisions.

        Returns:
            List of SelectionEvent records.
        """
        return list(self._selection_log)

    def record_reload(self, module_path: str) -> None:
        """Record that a module was hot-reloaded.

        Used to penalize slow-compile languages for frequently-reloaded modules.

        Args:
            module_path: Dot-separated module identifier.
        """
        self._reload_counts[module_path] = (
            self._reload_counts.get(module_path, 0) + 1
        )

    @property
    def reload_counts(self) -> dict[str, int]:
        """Snapshot of reload counts."""
        return dict(self._reload_counts)

    @property
    def overrides(self) -> dict[str, str]:
        """Snapshot of manual overrides."""
        return dict(self._overrides)

    @property
    def current_languages(self) -> dict[str, str]:
        """Snapshot of current language assignments."""
        return dict(self._current_languages)

    # ── Internal Selection Helpers ──────────────────────────────────────

    def _select_warm(self, module_path: str) -> str:
        """Select language for WARM modules.

        Balance speed and expressiveness. Prefer TypeScript, but
        if the module is frequently reloaded, stay with Python.
        """
        reloads = self._reload_counts.get(module_path, 0)
        if reloads > 5:
            # Frequently reloaded — keep Python
            return "python"
        return "typescript"

    def _select_hot(self, module_path: str) -> str:
        """Select language for HOT modules.

        Lean toward speed. Use Rust if memory safety matters,
        otherwise C# for faster compile times.
        """
        reloads = self._reload_counts.get(module_path, 0)
        if reloads > 10:
            # Very frequently reloaded — C# compiles faster
            return "csharp"
        return "rust"

    def _select_heat(self, module_path: str) -> str:
        """Select language for HEAT modules.

        Maximize speed. Use C+SIMD for raw throughput.
        Rust is the alternative if memory safety is required.
        """
        return "c_simd"

    def __repr__(self) -> str:
        return (
            f"AdaptiveSelector("
            f"modules={len(self._current_languages)}, "
            f"overrides={len(self._overrides)}, "
            f"decisions={len(self._selection_log)})"
        )
