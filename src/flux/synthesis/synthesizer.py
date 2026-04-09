"""FluxSynthesizer — the complete FLUX system, a self-assembling, self-improving runtime.

This is the DJ at the center of everything:
- Manages nested modules (the vinyl collection)
- Profiles execution (listening to the room)
- Selects languages (choosing the right instrument)
- Composes tiles (layering samples)
- Runs evolution (improving the set over time)
- Hot-reloads at any granularity (swapping tracks mid-set)

Usage:
    synth = FluxSynthesizer("my_app")
    synth.load_module("audio_engine", source, language="python")
    synth.load_module("dsp_filter", source, language="python")
    synth.run_workload(my_audio_pipeline)
    synth.evolve(generations=5)
    # The system just made itself faster
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

from flux.modules.granularity import Granularity
from flux.modules.card import ModuleCard
from flux.modules.container import ModuleContainer, ReloadResult
from flux.modules.reloader import FractalReloader
from flux.modules.namespace import ModuleNamespace
from flux.adaptive.profiler import (
    AdaptiveProfiler,
    HeatLevel,
    BottleneckReport,
)
from flux.adaptive.selector import (
    AdaptiveSelector,
    LanguageRecommendation,
)
from flux.tiles.registry import TileRegistry, default_registry
from flux.evolution.genome import Genome
from flux.evolution.pattern_mining import PatternMiner, ExecutionTrace
from flux.evolution.mutator import SystemMutator
from flux.evolution.validator import CorrectnessValidator
from flux.evolution.evolution import (
    EvolutionEngine,
    EvolutionReport,
    EvolutionRecord,
)


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class WorkloadResult:
    """Result of running a workload through the synthesizer."""

    success: bool = True
    elapsed_ns: int = 0
    module_calls: int = 0
    samples_recorded: int = 0
    error: str = ""
    heatmap: dict[str, str] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_ns / 1_000_000.0


# ── FluxSynthesizer ─────────────────────────────────────────────────────────

class FluxSynthesizer:
    """The complete FLUX system — a self-assembling, self-improving runtime.

    This is the DJ at the center of everything:
    - Manages nested modules (the vinyl collection)
    - Profiles execution (listening to the room)
    - Selects languages (choosing the right instrument)
    - Composes tiles (layering samples)
    - Runs evolution (improving the set over time)
    - Hot-reloads at any granularity (swapping tracks mid-set)

    Usage:
        synth = FluxSynthesizer("my_app")
        synth.load_module("audio/engine", source, language="python")
        synth.load_module("dsp/filter", source, language="python")
        synth.run_workload(my_audio_pipeline)
        synth.evolve(generations=5)
        # The system just made itself faster
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._created_at = time.time()

        # Module hierarchy: 8-level fractal nesting
        self.root = ModuleContainer(name, Granularity.TRAIN)
        self.reloader = FractalReloader(self.root)

        # Adaptive subsystem: profiling + language selection
        self.profiler = AdaptiveProfiler()
        self.selector = AdaptiveSelector(self.profiler)

        # Tile system: 34 built-in tiles + DAG composition
        self.tile_registry = default_registry

        # Evolution engine: self-improvement loop
        self.evolution = EvolutionEngine(
            profiler=self.profiler,
            selector=self.selector,
        )
        self.validator = CorrectnessValidator()
        self.miner = PatternMiner(self.profiler)

        # Internal tracking
        self._module_paths: set[str] = set()
        self._workload_fns: list[Callable[[], None]] = []
        self._evolution_reports: list[EvolutionReport] = []
        self._total_modules_loaded: int = 0

    # ── Module Management ─────────────────────────────────────────────────

    def load_module(
        self,
        path: str,
        source: str,
        language: str = "python",
    ) -> ModuleCard:
        """Load a module at the given nested path.

        The path is slash-separated, e.g. "audio/dsp/filter".
        Creates intermediate containers as needed, each at the next
        granularity level down from TRAIN.

        Args:
            path: Slash-separated module path (e.g. "audio/dsp/filter").
            source: Source code for the module.
            language: Language of the source (default "python").

        Returns:
            The ModuleCard created for the module.
        """
        parts = path.strip("/").split("/")
        if not parts or not parts[0]:
            raise ValueError(f"Invalid module path: {path!r}")

        # Walk/create the container hierarchy
        current = self.root
        all_levels = list(Granularity)
        for i, part in enumerate(parts[:-1]):
            # Each intermediate level goes one granularity deeper
            level_idx = min(i + 1, len(all_levels) - 2)
            gran = all_levels[level_idx]

            if part not in current.children:
                current.add_child(part, gran)

            current = current.children[part]

        # The last part is the card name
        card_name = parts[-1]
        card = current.load_card(card_name, source, language)

        # Track the full dot-path
        full_path = self.root.name + "." + ".".join(parts)
        self._module_paths.add(full_path)
        self._total_modules_loaded += 1

        # Register language with selector
        self.selector._current_languages[full_path] = language

        return card

    def get_module(self, path: str) -> Optional[ModuleCard]:
        """Get a module card by slash-separated path.

        Args:
            path: Slash-separated module path (e.g. "audio/dsp/filter").

        Returns:
            The ModuleCard or None if not found.
        """
        parts = path.strip("/").split("/")
        if not parts:
            return None

        # Navigate containers
        current = self.root
        for part in parts[:-1]:
            if part not in current.children:
                return None
            current = current.children[part]

        return current.cards.get(parts[-1])

    def get_container(self, path: str) -> Optional[ModuleContainer]:
        """Get a container by slash-separated path.

        Args:
            path: Slash-separated path (e.g. "audio/dsp").
                   Empty string returns root.

        Returns:
            The ModuleContainer or None if not found.
        """
        if not path or path == self.root.name:
            return self.root

        parts = path.strip("/").split(".")
        result = self.root.get_by_path(".".join(parts))
        if isinstance(result, ModuleContainer):
            return result
        return None

    @property
    def module_count(self) -> int:
        """Total number of loaded module cards."""
        return self._total_modules_loaded

    @property
    def container_count(self) -> int:
        """Total number of containers (including root)."""
        return self._count_containers(self.root)

    def _count_containers(self, container: ModuleContainer) -> int:
        count = 1
        for child in container.children.values():
            count += self._count_containers(child)
        return count

    # ── Workload Execution ────────────────────────────────────────────────

    def run_workload(self, fn: Callable[[], None]) -> WorkloadResult:
        """Run a workload and profile it.

        The workload function should call modules by their full dot-path.
        The synthesizer instruments the call to capture profiling data.

        Args:
            fn: Callable workload function. May optionally accept the
                synthesizer as its first argument for instrumentation.

        Returns:
            WorkloadResult with profiling data.
        """
        start = time.monotonic_ns()
        module_calls_before = self.profiler.module_count
        samples_before = self.profiler.sample_count

        try:
            # Try calling with self (synthesizer) for instrumentation
            fn()
        except TypeError:
            # If fn doesn't accept arguments, call without
            try:
                fn()
            except Exception as exc:
                elapsed = time.monotonic_ns() - start
                return WorkloadResult(
                    success=False,
                    elapsed_ns=elapsed,
                    error=str(exc),
                )
        except Exception as exc:
            elapsed = time.monotonic_ns() - start
            return WorkloadResult(
                success=False,
                elapsed_ns=elapsed,
                error=str(exc),
            )

        elapsed = time.monotonic_ns() - start

        # Build heatmap string representation
        heatmap = self.profiler.get_heatmap()
        heatmap_str = {k: v.name for k, v in heatmap.items()}

        return WorkloadResult(
            success=True,
            elapsed_ns=elapsed,
            module_calls=self.profiler.module_count - module_calls_before,
            samples_recorded=self.profiler.sample_count - samples_before,
            heatmap=heatmap_str,
        )

    def record_call(
        self,
        module_path: str,
        duration_ns: int = 0,
        calls: int = 1,
    ) -> None:
        """Manually record module execution calls for profiling.

        Args:
            module_path: Dot-separated module identifier.
            duration_ns: Execution time in nanoseconds.
            calls: Number of calls to record.
        """
        for _ in range(calls):
            self.profiler.record_call(module_path, duration_ns=duration_ns)

    # ── Heat Map ──────────────────────────────────────────────────────────

    def get_heatmap(self) -> dict[str, str]:
        """Get current module heat classification.

        Returns:
            Mapping from module_path to heat level name
            (FROZEN/COOL/WARM/HOT/HEAT).
        """
        heatmap = self.profiler.get_heatmap()
        return {k: v.name for k, v in heatmap.items()}

    def get_heatmap_enum(self) -> dict[str, HeatLevel]:
        """Get current module heat classification as enum values."""
        return self.profiler.get_heatmap()

    # ── Language Recommendations ───────────────────────────────────────────

    def get_recommendations(self) -> dict[str, LanguageRecommendation]:
        """Get language recommendations for all profiled modules.

        Returns:
            Mapping from module_path to LanguageRecommendation.
        """
        return self.selector.select_all()

    def get_recommendation(self, module_path: str) -> Optional[LanguageRecommendation]:
        """Get language recommendation for a single module.

        Args:
            module_path: Dot-separated module identifier.

        Returns:
            LanguageRecommendation or None if module not profiled.
        """
        recs = self.get_recommendations()
        return recs.get(module_path)

    # ── Evolution ─────────────────────────────────────────────────────────

    def evolve(
        self,
        generations: int = 5,
        validation_fn: Optional[Callable[[Genome], bool]] = None,
    ) -> EvolutionReport:
        """Run the self-evolution loop.

        The evolution engine will:
        1. Capture the current system genome
        2. Profile workloads to find hot paths
        3. Mine execution patterns
        4. Propose and apply mutations
        5. Validate correctness
        6. Track fitness improvements

        Args:
            generations: Number of evolution cycles to run.
            validation_fn: Optional function that validates system correctness
                           after each mutation. Should return True if valid.

        Returns:
            EvolutionReport with all improvements made.
        """
        # Build workload list from recorded calls if no explicit workloads
        workloads = self._workload_fns
        if not workloads:
            # Create a synthetic workload that exercises profiled modules
            def synthetic_workload() -> None:
                for mod_path, count in self.profiler.call_counts.items():
                    self.profiler.record_call(
                        mod_path,
                        duration_ns=self.profiler.total_time_ns.get(mod_path, 1000) // max(count, 1),
                    )
            workloads = [synthetic_workload]

        report = self.evolution.evolve(
            module_root=self.root,
            tile_registry=self.tile_registry,
            workloads=workloads,
            max_generations=generations,
            validation_fn=validation_fn,
        )

        self._evolution_reports.append(report)
        return report

    def evolve_step(
        self,
        workload: Optional[Callable[[], None]] = None,
        validation_fn: Optional[Callable[[Genome], bool]] = None,
    ) -> EvolutionReport:
        """Run a single evolution step.

        Args:
            workload: Optional workload function to profile.
            validation_fn: Optional correctness validator.

        Returns:
            EvolutionReport for the single step.
        """
        from flux.evolution.evolution import EvolutionReport as ER

        step = self.evolution.step(
            module_root=self.root,
            tile_registry=self.tile_registry,
            workload=workload,
            validation_fn=validation_fn,
        )

        report = ER(
            generations=1,
            initial_fitness=step.fitness_before,
            final_fitness=step.fitness_after,
            records=[step.record] if step.record else [],
        )
        self._evolution_reports.append(report)
        return report

    @property
    def current_fitness(self) -> float:
        """Current genome fitness score."""
        return self.evolution.current_fitness

    @property
    def generation(self) -> int:
        """Current evolution generation number."""
        return self.evolution.generation

    def get_evolution_history(self) -> list[tuple[int, float]]:
        """Get (generation, fitness) pairs for all evolution steps."""
        return self.evolution.get_improvement_history()

    # ── Hot Reload ────────────────────────────────────────────────────────

    def hot_swap(
        self,
        path: str,
        new_source: str,
    ) -> ReloadResult:
        """Hot-swap a module at any granularity.

        Args:
            path: Slash-separated module path (e.g. "audio/dsp/filter").
            new_source: New source code for the module.

        Returns:
            ReloadResult indicating success/failure.
        """
        # Convert slash path to dot path for the reloader
        dot_path = self.root.name + "." + path.replace("/", ".")

        # Navigate to the container holding the card
        parts = path.strip("/").split("/")
        container = self.root
        for part in parts[:-1]:
            if part not in container.children:
                return ReloadResult(
                    success=False,
                    path=dot_path,
                    error=f"Container '{part}' not found in path",
                )
            container = container.children[part]

        card_name = parts[-1]

        # Reload the card
        result = container.reload_card(card_name, new_source)

        # Record the reload in the selector for reload penalty tracking
        if result.success:
            self.selector.record_reload(dot_path)
            self.reloader.notify_change(dot_path)

        return result

    def hot_swap_container(self, path: str) -> ReloadResult:
        """Hot-swap an entire container subtree.

        Args:
            path: Slash-separated path to the container.

        Returns:
            ReloadResult indicating success/failure.
        """
        dot_path = path.replace("/", ".")
        if not dot_path:
            dot_path = self.root.name

        return self.reloader.reload_sync(dot_path, Granularity.CARD)

    # ── Bottleneck Analysis ───────────────────────────────────────────────

    def get_bottleneck_report(self, top_n: int = 5) -> BottleneckReport:
        """Get bottleneck analysis from the profiler.

        Args:
            top_n: Maximum number of bottlenecks to report.

        Returns:
            BottleneckReport with entries, totals, and recommendations.
        """
        return self.profiler.get_bottleneck_report(top_n)

    # ── System Report ─────────────────────────────────────────────────────

    def get_system_report(self):
        """Get a comprehensive report of the entire system state.

        Returns:
            SystemReport instance.
        """
        from .report import SystemReport
        return SystemReport(self)

    # ── Tile Operations ───────────────────────────────────────────────────

    def search_tiles(self, query: str):
        """Search the tile registry.

        Args:
            query: Search query string.

        Returns:
            List of matching Tile objects.
        """
        return self.tile_registry.search(query)

    def get_tile(self, name: str):
        """Get a tile by name from the registry.

        Args:
            name: Exact tile name.

        Returns:
            Tile object or None.
        """
        return self.tile_registry.get(name)

    @property
    def tile_count(self) -> int:
        """Number of registered tiles."""
        return self.tile_registry.count

    def register_tile(self, tile) -> None:
        """Register a custom tile in the registry.

        Args:
            tile: A Tile object to register.
        """
        self.tile_registry.register(tile)

    # ── Hierarchy Serialization ───────────────────────────────────────────

    def get_hierarchy(self) -> dict:
        """Get the full module hierarchy as a dict.

        Returns:
            Nested dict representation of the container tree.
        """
        return self.root.to_dict()

    def get_module_tree(self) -> str:
        """Get a human-readable tree view of the module hierarchy.

        Returns:
            Multi-line string with tree visualization.
        """
        lines: list[str] = []
        self._render_tree(self.root, "", True, lines)
        return "\n".join(lines)

    def _render_tree(
        self,
        container: ModuleContainer,
        prefix: str,
        is_last: bool,
        lines: list[str],
    ) -> None:
        """Recursively render container tree."""
        connector = "└── " if is_last else "├── "
        card_count = len(container.cards)
        child_count = len(container.children)
        label = f"{container.name} [{container.granularity.name}]"
        if card_count:
            label += f" ({card_count} cards)"

        if prefix:
            lines.append(f"{prefix}{connector}{label}")
        else:
            lines.append(label)

        child_prefix = prefix + ("    " if is_last else "│   ")

        # Render cards
        card_names = sorted(container.cards.keys())
        for i, cname in enumerate(card_names):
            card = container.cards[cname]
            is_card_last = (i == len(card_names) - 1) and not container.children
            card_connector = "└── " if is_card_last else "├── "
            card_label = f"{cname} ({card.language})"
            lines.append(f"{child_prefix}{card_connector}{card_label}")

        # Render children
        child_names = sorted(container.children.keys())
        for i, cname in enumerate(child_names):
            child = container.children[cname]
            self._render_tree(child, child_prefix, i == len(child_names) - 1, lines)

    # ── Stats & Info ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Get summary statistics of the synthesizer.

        Returns:
            Dict with key metrics.
        """
        return {
            "name": self.name,
            "modules": self._total_modules_loaded,
            "containers": self.container_count,
            "tiles": self.tile_count,
            "generation": self.generation,
            "fitness": self.current_fitness,
            "profiled_modules": self.profiler.module_count,
            "samples": self.profiler.sample_count,
            "evolution_runs": len(self._evolution_reports),
            "reload_history": len(self.reloader.history),
            "uptime_s": time.time() - self._created_at,
        }

    def __repr__(self) -> str:
        return (
            f"FluxSynthesizer({self.name!r}, "
            f"modules={self._total_modules_loaded}, "
            f"tiles={self.tile_count}, "
            f"gen={self.generation}, "
            f"fitness={self.current_fitness:.4f})"
        )
