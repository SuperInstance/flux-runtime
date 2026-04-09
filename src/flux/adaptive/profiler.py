"""Runtime execution profiler for adaptive language selection.

Profiles module execution frequency, timing, and allocation patterns
to classify each module as HEAT/HOT/WARM/COOL/FROZEN. This classification
drives the AdaptiveSelector's language recommendations — like a DJ choosing
between a 909 drum machine (fast, rigid) vs. a live jazz sample (expressive,
flexible) based on what the moment needs.
"""

from __future__ import annotations

import time
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# ── Heat Classification ─────────────────────────────────────────────────

class HeatLevel(IntEnum):
    """Module execution heat classification.

    FROZEN = never called
    COOL   = rarely called — keep expressive language
    WARM   = moderately called — consider optimization
    HOT    = frequently called — should optimize
    HEAT   = critical bottleneck — must be fastest possible
    """
    FROZEN = 0
    COOL = 1
    WARM = 2
    HOT = 3
    HEAT = 4


# ── Profile Data ────────────────────────────────────────────────────────

@dataclass
class ProfileSample:
    """A single recorded execution sample."""
    module_path: str
    start_ns: int = 0
    end_ns: int = 0
    duration_ns: int = 0
    alloc_count: int = 0


@dataclass
class SampleHandle:
    """Opaque handle returned by start_sample() for pairing with end_sample()."""
    module_path: str
    sample_index: int
    start_ns: int = 0


@dataclass
class BottleneckEntry:
    """A single bottleneck identified by the profiler."""
    module_path: str
    call_count: int
    total_time_ns: int
    self_time_ns: int
    avg_time_ns: float
    heat_level: HeatLevel
    recommendation: str


@dataclass
class BottleneckReport:
    """Summary of profiling bottlenecks with recommendations."""
    entries: list[BottleneckEntry] = field(default_factory=list)
    total_modules: int = 0
    total_samples: int = 0
    total_time_ns: int = 0


# ── Profiler ────────────────────────────────────────────────────────────

class AdaptiveProfiler:
    """Profiles module execution to guide language selection.

    Tracks call counts, wall-clock timing, and allocation counts per module.
    Classifies modules by heat level using percentile-based thresholds:
    - HEAT  (top 20%):  critical bottlenecks → fastest language
    - HOT   (next 30%): should optimize → fast compiled language
    - WARM  (next 30%): moderate → balance speed and expressiveness
    - COOL  (bottom 20%): rarely called → maximize expressiveness
    - FROZEN: never called → no opinion

    Args:
        hot_threshold: Percentile cutoff for HEAT (default 0.8 = top 20%).
        warm_threshold: Percentile cutoff for WARM (default 0.5 = top 50%).
    """

    def __init__(
        self,
        hot_threshold: float = 0.8,
        warm_threshold: float = 0.5,
    ) -> None:
        self._call_counts: dict[str, int] = defaultdict(int)
        self._total_time_ns: dict[str, int] = defaultdict(int)
        self._self_time_ns: dict[str, int] = defaultdict(int)
        self._alloc_counts: dict[str, int] = defaultdict(int)
        self._hot_threshold: float = hot_threshold
        self._warm_threshold: float = warm_threshold
        self._samples: list[ProfileSample] = []
        self._sample_counter: int = 0
        self._active_samples: dict[int, SampleHandle] = {}

    # ── Recording ───────────────────────────────────────────────────────

    def start_sample(self, module_path: str) -> SampleHandle:
        """Begin timing a module execution.

        Args:
            module_path: Dot-separated module identifier.

        Returns:
            SampleHandle to pass to end_sample().
        """
        handle = SampleHandle(
            module_path=module_path,
            sample_index=self._sample_counter,
            start_ns=time.time_ns(),
        )
        self._active_samples[handle.sample_index] = handle
        self._sample_counter += 1
        return handle

    def end_sample(self, handle: SampleHandle) -> None:
        """End timing a module execution and record the sample.

        Args:
            handle: The handle returned by start_sample().

        Raises:
            ValueError: If the handle is not recognized.
        """
        if handle.sample_index not in self._active_samples:
            raise ValueError(f"Unknown sample handle: {handle.sample_index}")
        del self._active_samples[handle.sample_index]

        end_ns = time.time_ns()
        duration_ns = max(0, end_ns - handle.start_ns)

        self._call_counts[handle.module_path] += 1
        self._total_time_ns[handle.module_path] += duration_ns
        self._self_time_ns[handle.module_path] += duration_ns
        self._alloc_counts[handle.module_path] += 0  # placeholder

        sample = ProfileSample(
            module_path=handle.module_path,
            start_ns=handle.start_ns,
            end_ns=end_ns,
            duration_ns=duration_ns,
            alloc_count=0,
        )
        self._samples.append(sample)

    def record_call(
        self,
        module_path: str,
        duration_ns: int = 0,
        alloc_count: int = 0,
    ) -> None:
        """Record a module call with optional timing and allocation info.

        This is a lightweight alternative to start_sample/end_sample when
        you already have the timing data.

        Args:
            module_path: Dot-separated module identifier.
            duration_ns: Execution time in nanoseconds.
            alloc_count: Number of allocations during execution.
        """
        self._call_counts[module_path] += 1
        self._total_time_ns[module_path] += duration_ns
        self._self_time_ns[module_path] += duration_ns
        self._alloc_counts[module_path] += alloc_count

        sample = ProfileSample(
            module_path=module_path,
            duration_ns=duration_ns,
            alloc_count=alloc_count,
        )
        self._samples.append(sample)

    # ── Queries ─────────────────────────────────────────────────────────

    def get_heatmap(self) -> dict[str, HeatLevel]:
        """Classify all profiled modules by heat level.

        Uses call-count percentiles to determine thresholds:
        - HEAT:  calls ≥ hot_threshold percentile
        - HOT:   calls ≥ warm_threshold percentile
        - WARM:  calls > 0 but below warm percentile
        - COOL:  calls > 0 but below median
        - FROZEN: never called (not present in profiled data)

        Returns:
            Mapping from module_path to HeatLevel.
        """
        if not self._call_counts:
            return {}

        # Build sorted list of (module, call_count) descending
        ranked = sorted(
            self._call_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        n = len(ranked)

        # hot_threshold=0.8 means "top 20% is HEAT" → heat_count = n*(1-0.8) = n*0.2
        # warm_threshold=0.5 means "top 50% is HOT" → hot_count = n*(1-0.5) = n*0.5
        heat_count = max(1, int(n * (1.0 - self._hot_threshold)))
        hot_count = max(1, int(n * (1.0 - self._warm_threshold)))

        heatmap: dict[str, HeatLevel] = {}
        for i, (mod, count) in enumerate(ranked):
            if i < heat_count:
                heatmap[mod] = HeatLevel.HEAT
            elif i < hot_count:
                heatmap[mod] = HeatLevel.HOT
            elif count > 1:
                heatmap[mod] = HeatLevel.WARM
            else:
                heatmap[mod] = HeatLevel.COOL

        return heatmap

    def get_ranking(self) -> list[tuple[str, float]]:
        """Return modules sorted by execution frequency.

        Each entry is (module_path, weight) where weight is the fraction
        of total calls attributed to this module.

        Returns:
            List of (module_path, weight) sorted by weight descending.
        """
        total_calls = sum(self._call_counts.values())
        if total_calls == 0:
            return []

        ranked = sorted(
            self._call_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(mod, count / total_calls) for mod, count in ranked]

    def get_bottleneck_report(self, top_n: int = 5) -> BottleneckReport:
        """Identify the top N bottlenecks with recommendations.

        Bottlenecks are ranked by total execution time. For each, a
        recommendation is generated based on heat level.

        Args:
            top_n: Maximum number of bottlenecks to report.

        Returns:
            BottleneckReport with entries, totals, and recommendations.
        """
        heatmap = self.get_heatmap()
        total_samples = len(self._samples)
        total_time = sum(self._total_time_ns.values())

        # Sort by total time descending
        ranked = sorted(
            self._total_time_ns.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        entries: list[BottleneckEntry] = []
        for mod, total_ns in ranked[:top_n]:
            calls = self._call_counts[mod]
            self_ns = self._self_time_ns[mod]
            avg_ns = total_ns / calls if calls > 0 else 0.0
            heat = heatmap.get(mod, HeatLevel.FROZEN)
            rec = self._recommendation_for_heat(heat)

            entries.append(BottleneckEntry(
                module_path=mod,
                call_count=calls,
                total_time_ns=total_ns,
                self_time_ns=self_ns,
                avg_time_ns=avg_ns,
                heat_level=heat,
                recommendation=rec,
            ))

        return BottleneckReport(
            entries=entries,
            total_modules=len(self._call_counts),
            total_samples=total_samples,
            total_time_ns=total_time,
        )

    def should_recompile(self, module_path: str) -> tuple[bool, str]:
        """Check if a module should be recompiled in a faster language.

        Args:
            module_path: Dot-separated module identifier.

        Returns:
            (should_recompile, reason) tuple.
        """
        heatmap = self.get_heatmap()
        heat = heatmap.get(module_path, HeatLevel.FROZEN)

        if heat == HeatLevel.FROZEN:
            return False, "Module never called — no data to justify recompilation."
        if heat == HeatLevel.COOL:
            return False, (
                "Module rarely called — expressiveness outweighs speed gains."
            )
        if heat == HeatLevel.WARM:
            return False, (
                "Module moderately called — consider recompilation if "
                "per-call cost is high."
            )
        if heat == HeatLevel.HOT:
            return True, (
                "Module frequently called — recompilation to a compiled "
                "language would improve throughput."
            )
        # HEAT
        return True, (
            "Module is a critical bottleneck — recompile to fastest "
            "available language (C+SIMD or Rust)."
        )

    def estimate_speedup(self, module_path: str, target_lang: str) -> float:
        """Estimate speedup factor if module were rewritten in target_lang.

        Uses empirical speedup ratios based on language characteristics:
        - python → typescript: ~2x
        - python → csharp: ~4x
        - python → c: ~8x
        - python → c_simd: ~16x
        - python → rust: ~10x
        - Current language is always Python for estimation purposes.

        Args:
            module_path: Dot-separated module identifier.
            target_lang: Target language key (e.g. "c", "rust", "typescript").

        Returns:
            Estimated speedup factor (1.0 = no change).
        """
        speedup_factors = {
            "python": 1.0,
            "typescript": 2.0,
            "csharp": 4.0,
            "c": 8.0,
            "c_simd": 16.0,
            "rust": 10.0,
        }
        return speedup_factors.get(target_lang, 1.0)

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def call_counts(self) -> dict[str, int]:
        """Snapshot of current call counts."""
        return dict(self._call_counts)

    @property
    def total_time_ns(self) -> dict[str, int]:
        """Snapshot of total execution times."""
        return dict(self._total_time_ns)

    @property
    def sample_count(self) -> int:
        """Number of recorded samples."""
        return len(self._samples)

    @property
    def module_count(self) -> int:
        """Number of profiled modules."""
        return len(self._call_counts)

    # ── Management ──────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all profiling data."""
        self._call_counts.clear()
        self._total_time_ns.clear()
        self._self_time_ns.clear()
        self._alloc_counts.clear()
        self._samples.clear()
        self._sample_counter = 0
        self._active_samples.clear()

    def get_module_stats(self, module_path: str) -> Optional[dict]:
        """Get detailed stats for a single module.

        Args:
            module_path: Dot-separated module identifier.

        Returns:
            Dict with call_count, total_time_ns, self_time_ns, alloc_count,
            avg_time_ns, or None if never profiled.
        """
        if module_path not in self._call_counts:
            return None
        calls = self._call_counts[module_path]
        total = self._total_time_ns[module_path]
        return {
            "call_count": calls,
            "total_time_ns": total,
            "self_time_ns": self._self_time_ns[module_path],
            "alloc_count": self._alloc_counts[module_path],
            "avg_time_ns": total / calls if calls > 0 else 0.0,
        }

    # ── Internal ────────────────────────────────────────────────────────

    @staticmethod
    def _recommendation_for_heat(heat: HeatLevel) -> str:
        """Generate a human-readable recommendation for a heat level."""
        recommendations = {
            HeatLevel.FROZEN: "No data — module has never been executed.",
            HeatLevel.COOL: "Keep in expressive language (Python). Optimisation unnecessary.",
            HeatLevel.WARM: "Consider TypeScript for moderate speed improvement.",
            HeatLevel.HOT: "Recompile to C# or Rust for significant speedup.",
            HeatLevel.HEAT: "Critical path — recompile to C+SIMD for maximum throughput.",
        }
        return recommendations.get(heat, "Unknown heat level.")

    def __repr__(self) -> str:
        return (
            f"AdaptiveProfiler("
            f"modules={self.module_count}, "
            f"samples={self.sample_count}, "
            f"hot_threshold={self._hot_threshold}, "
            f"warm_threshold={self._warm_threshold})"
        )
