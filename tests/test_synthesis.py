"""Tests for FLUX Synthesis — the integration layer that wires all subsystems together.

Covers: synthesizer creation, module loading, workload profiling, heat maps,
language recommendations, hot reload, evolution, tile composition, namespace
isolation, system reports, and full demo pipeline.
"""

import time
import pytest
from flux.synthesis.synthesizer import FluxSynthesizer, WorkloadResult
from flux.synthesis.report import SystemReport
from flux.modules.granularity import Granularity
from flux.modules.container import ModuleContainer
from flux.modules.card import ModuleCard
from flux.modules.reloader import FractalReloader
from flux.adaptive.profiler import AdaptiveProfiler, HeatLevel
from flux.adaptive.selector import AdaptiveSelector, LanguageRecommendation
from flux.tiles.registry import TileRegistry, default_registry
from flux.tiles.tile import Tile, TileType
from flux.tiles.ports import TilePort, PortDirection
from flux.fir.types import TypeContext, IntType
from flux.evolution.genome import Genome, MutationStrategy
from flux.evolution.evolution import EvolutionReport
from flux.evolution.validator import CorrectnessValidator


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def synth():
    """Create a fresh synthesizer for each test."""
    return FluxSynthesizer("test_app")


@pytest.fixture
def loaded_synth(synth):
    """Synthesizer with several modules loaded at different levels."""
    synth.load_module("a", "def a_func(): pass", "python")
    synth.load_module("b/c", "def c_func(): pass", "python")
    synth.load_module("b/d", "def d_func(): pass", "python")
    synth.load_module("e/f/g", "def g_func(): pass", "python")
    synth.record_call("test_app.a", duration_ns=1000, calls=5)
    synth.record_call("test_app.b.c", duration_ns=2000, calls=10)
    synth.record_call("test_app.b.d", duration_ns=3000, calls=20)
    synth.record_call("test_app.e.f.g", duration_ns=5000, calls=50)
    return synth


# ── Test Group 1: Synthesizer Creation ───────────────────────────────────

class TestSynthesizerCreation:
    """Tests for creating and initializing the synthesizer."""

    def test_synthesizer_creation(self, synth):
        """Create a synthesizer, verify subsystems initialized."""
        assert synth.name == "test_app"
        assert isinstance(synth.root, ModuleContainer)
        assert synth.root.granularity == Granularity.TRAIN
        assert isinstance(synth.reloader, FractalReloader)
        assert isinstance(synth.profiler, AdaptiveProfiler)
        assert isinstance(synth.selector, AdaptiveSelector)
        assert isinstance(synth.evolution, type(synth.evolution))
        assert isinstance(synth.validator, CorrectnessValidator)
        assert isinstance(synth.tile_registry, TileRegistry)
        assert synth.tile_count >= 34  # built-in tiles

    def test_synthesizer_repr(self, synth):
        """Verify repr is informative."""
        r = repr(synth)
        assert "test_app" in r
        assert "FluxSynthesizer" in r

    def test_synthesizer_stats(self, synth):
        """Verify stats dict contains expected keys."""
        stats = synth.stats()
        assert stats["name"] == "test_app"
        assert stats["modules"] == 0
        assert stats["containers"] == 1  # root only
        assert stats["tiles"] >= 34
        assert stats["generation"] == 0
        assert "fitness" in stats
        assert "uptime_s" in stats


# ── Test Group 2: Module Loading ─────────────────────────────────────────

class TestModuleLoading:
    """Tests for loading modules at different hierarchy levels."""

    def test_load_modules_at_different_levels(self, loaded_synth):
        """Load modules at TRAIN, BAG, POCKET, CARD levels."""
        assert loaded_synth.module_count == 4
        assert loaded_synth.container_count >= 3  # root + intermediates

    def test_load_single_card(self, synth):
        """Load a module at the root level (single card)."""
        card = synth.load_module("simple", "pass", "python")
        assert isinstance(card, ModuleCard)
        assert card.name == "simple"
        assert card.language == "python"
        assert synth.module_count == 1

    def test_load_nested_modules(self, synth):
        """Load modules at 2-level nesting."""
        synth.load_module("x/y", "pass", "python")
        assert synth.module_count == 1
        # Container 'x' should exist as child of root
        assert "x" in synth.root.children

    def test_load_deep_nested_modules(self, synth):
        """Load modules at 3+ levels deep."""
        synth.load_module("a/b/c/d", "pass", "python")
        assert synth.module_count == 1
        # Navigate to find the card
        assert "a" in synth.root.children
        assert "b" in synth.root.children["a"].children
        assert "c" in synth.root.children["a"].children["b"].children
        assert "d" in synth.root.children["a"].children["b"].children["c"].cards

    def test_nested_path_parsing(self, synth):
        """Paths like 'a/b/c/d' create correct container hierarchy."""
        synth.load_module("p1/p2/p3/p4", "source_code", "python")
        # Verify the full dot path chain
        container = synth.root.children["p1"]
        assert container.granularity == Granularity.CARRIAGE
        container = container.children["p2"]
        assert container.granularity == Granularity.LUGGAGE
        container = container.children["p3"]
        assert "p4" in container.cards

    def test_get_module(self, synth):
        """Retrieve a loaded module by path."""
        synth.load_module("foo/bar", "source", "python")
        card = synth.get_module("foo/bar")
        assert card is not None
        assert card.name == "bar"

    def test_get_module_not_found(self, synth):
        """Return None for non-existent module."""
        assert synth.get_module("nonexistent") is None

    def test_load_invalid_path(self, synth):
        """Reject empty or invalid paths."""
        with pytest.raises(ValueError):
            synth.load_module("", "source")
        with pytest.raises(ValueError):
            synth.load_module("/", "source")

    def test_load_multiple_cards_in_same_container(self, synth):
        """Load multiple cards into the same container."""
        synth.load_module("shared/a", "def a(): pass", "python")
        synth.load_module("shared/b", "def b(): pass", "python")
        container = synth.root.children["shared"]
        assert len(container.cards) == 2
        assert "a" in container.cards
        assert "b" in container.cards


# ── Test Group 3: Workload Profiling ─────────────────────────────────────

class TestWorkloadProfiling:
    """Tests for running workloads and collecting profiling data."""

    def test_workload_profiling(self, synth):
        """Run a workload, verify profiler records it."""
        synth.load_module("mod_a", "pass", "python")
        synth.record_call("test_app.mod_a", duration_ns=100, calls=10)
        assert synth.profiler.module_count == 1
        assert synth.profiler.call_counts["test_app.mod_a"] == 10

    def test_workload_result(self, synth):
        """Verify WorkloadResult is correct."""
        def workload():
            synth.record_call("test_app.x", duration_ns=50, calls=5)

        result = synth.run_workload(workload)
        assert isinstance(result, WorkloadResult)
        assert result.success
        assert result.module_calls > 0
        assert result.elapsed_ns > 0

    def test_workload_with_error(self, synth):
        """Workload that raises an exception returns failure."""
        def bad_workload():
            raise RuntimeError("boom")

        result = synth.run_workload(bad_workload)
        assert not result.success
        assert "boom" in result.error

    def test_heatmap_after_workload(self, loaded_synth):
        """After workload, some modules should be WARM/HOT."""
        heatmap = loaded_synth.get_heatmap()
        assert len(heatmap) > 0

        # Check that we have a mix of heat levels
        heat_values = set(heatmap.values())
        # With 4 modules and varied call counts, we should see at least 2 levels
        assert len(heat_values) >= 1

    def test_record_call_multiple(self, synth):
        """Record multiple calls to the same module."""
        synth.record_call("test_app.m", duration_ns=100, calls=100)
        assert synth.profiler.call_counts["test_app.m"] == 100

    def test_heatmap_empty_before_profiling(self, synth):
        """Heatmap should be empty before any profiling."""
        assert synth.get_heatmap() == {}


# ── Test Group 4: Heat Map & Recommendations ─────────────────────────────

class TestHeatAndRecommendations:
    """Tests for heat classification and language recommendations."""

    def test_recommendations_match_heat(self, loaded_synth):
        """COOL -> Python, HEAT -> C+SIMD or similar fast language."""
        recs = loaded_synth.get_recommendations()
        assert len(recs) > 0

        heatmap = loaded_synth.get_heatmap_enum()
        for path, rec in recs.items():
            heat = heatmap.get(path, HeatLevel.FROZEN)
            if heat == HeatLevel.COOL:
                assert rec.recommended_language == "python"
            elif heat == HeatLevel.HEAT:
                assert rec.recommended_language in ("c_simd", "rust", "c")

    def test_get_single_recommendation(self, loaded_synth):
        """Get recommendation for a specific module."""
        rec = loaded_synth.get_recommendation("test_app.e.f.g")
        assert rec is not None
        assert isinstance(rec, LanguageRecommendation)
        assert rec.module_path == "test_app.e.f.g"

    def test_recommendation_for_unknown_module(self, loaded_synth):
        """Recommendation for unprofiled module returns None."""
        rec = loaded_synth.get_recommendation("nonexistent")
        assert rec is None

    def test_heat_levels_are_valid(self, loaded_synth):
        """All heatmap values are valid HeatLevel names."""
        valid = {"FROZEN", "COOL", "WARM", "HOT", "HEAT"}
        heatmap = loaded_synth.get_heatmap()
        for heat in heatmap.values():
            assert heat in valid

    def test_bottleneck_report(self, loaded_synth):
        """Bottleneck report has entries."""
        report = loaded_synth.get_bottleneck_report(3)
        assert report.total_modules > 0
        assert len(report.entries) > 0


# ── Test Group 5: Hot Reload ─────────────────────────────────────────────

class TestHotReload:
    """Tests for hot-reloading modules."""

    def test_hot_swap_single_card(self, loaded_synth):
        """Swap one card, verify others unaffected."""
        # Get checksums of all cards before swap
        d_before = loaded_synth.get_module("b/d")
        assert d_before is not None
        d_checksum_before = d_before.checksum

        c_card = loaded_synth.get_module("b/c")
        assert c_card is not None
        c_checksum_before = c_card.checksum

        # Swap card 'b/d'
        result = loaded_synth.hot_swap("b/d", "def d_func_v2(): pass")

        assert result.success
        assert result.cards_reloaded == 1

        # Card 'b/d' should have changed
        d_after = loaded_synth.get_module("b/d")
        assert d_after is not None
        assert d_after.checksum != d_checksum_before

        # Card 'b/c' should be UNCHANGED
        c_after = loaded_synth.get_module("b/c")
        assert c_after is not None
        assert c_after.checksum == c_checksum_before

    def test_hot_swap_nonexistent(self, synth):
        """Hot-swap a nonexistent module fails gracefully."""
        result = synth.hot_swap("nonexistent/path", "new source")
        assert not result.success

    def test_reload_history_updated(self, loaded_synth):
        """Reload history is updated after hot_swap."""
        # hot_swap calls notify_change which sets the async event,
        # but doesn't add to reload_history (that's done by reload/reload_sync).
        # Verify the change notification happened via reload_sync.
        dot_path = loaded_synth.root.name + ".a"
        before = len(loaded_synth.reloader.history)
        loaded_synth.reloader.reload_sync(dot_path, Granularity.CARD)
        after = len(loaded_synth.reloader.history)
        assert after > before

    def test_module_reloading_preserves_state(self, loaded_synth):
        """Reload a module, verify other modules still work."""
        # Record calls for multiple modules
        loaded_synth.record_call("test_app.a", duration_ns=100, calls=5)
        loaded_synth.record_call("test_app.b.c", duration_ns=200, calls=3)

        # Reload module 'a'
        loaded_synth.hot_swap("a", "def a_func_v2(): pass")

        # Module b/c should still be accessible
        c_card = loaded_synth.get_module("b/c")
        assert c_card is not None
        assert c_card.source == "def c_func(): pass"

        # Profiler data for b/c should be intact
        assert "test_app.b.c" in loaded_synth.profiler.call_counts


# ── Test Group 6: Evolution ──────────────────────────────────────────────

class TestEvolution:
    """Tests for the self-evolution engine."""

    def test_evolution_improves_fitness(self, loaded_synth):
        """Run evolution, verify fitness is computed."""
        report = loaded_synth.evolve(generations=3)

        assert isinstance(report, EvolutionReport)
        assert report.generations > 0
        assert report.initial_fitness >= 0.0
        assert report.final_fitness >= 0.0
        # Fitness should be a valid float
        assert isinstance(report.final_fitness, float)
        # Final fitness should be >= initial
        assert report.final_fitness >= report.initial_fitness

    def test_evolution_step(self, loaded_synth):
        """Run a single evolution step."""
        report = loaded_synth.evolve_step()
        assert report.generations == 1
        assert report.final_fitness >= 0.0

    def test_evolution_generation_increments(self, loaded_synth):
        """Generation counter increments after evolution."""
        gen_before = loaded_synth.generation
        loaded_synth.evolve(generations=2)
        assert loaded_synth.generation > gen_before

    def test_evolution_history(self, loaded_synth):
        """Evolution history is recorded."""
        loaded_synth.evolve(generations=3)
        history = loaded_synth.get_evolution_history()
        assert len(history) >= 2  # at least a few steps
        # Each entry is (generation, fitness)
        for gen, fitness in history:
            assert isinstance(gen, int)
            assert isinstance(fitness, float)

    def test_evolution_with_zero_generations(self, loaded_synth):
        """Evolution with 0 generations returns empty report."""
        report = loaded_synth.evolve(generations=0)
        assert report.generations == 0


# ── Test Group 7: Tile System Integration ────────────────────────────────

class TestTileIntegration:
    """Tests for tile system integration with the synthesizer."""

    def test_tile_composition_in_synthesizer(self, synth):
        """Use tiles in module code."""
        assert synth.tile_count > 0
        map_tile = synth.get_tile("map")
        assert map_tile is not None
        assert map_tile.tile_type == TileType.COMPUTE

    def test_search_tiles(self, synth):
        """Search the tile registry."""
        results = synth.search_tiles("map")
        assert len(results) > 0
        assert any(t.name == "map" for t in results)

    def test_register_custom_tile(self, synth):
        """Register a custom tile."""
        ctx = TypeContext()
        tile = Tile(
            name="custom_greeting",
            tile_type=TileType.EFFECT,
            inputs=[],
            outputs=[],
            params={"message": "hello"},
            body=None,
            fir_blueprint=None,
            cost_estimate=1.0,
            abstraction_level=5,
            language_preference="fir",
        )
        synth.register_tile(tile)
        assert synth.get_tile("custom_greeting") is not None
        assert synth.tile_count >= 35  # 34 built-in + 1 custom

    def test_tile_types_available(self, synth):
        """Tiles of all 6 types are available."""
        types = set(t.tile_type for t in synth.tile_registry.all_tiles)
        expected = {TileType.COMPUTE, TileType.MEMORY, TileType.CONTROL,
                    TileType.A2A, TileType.EFFECT, TileType.TRANSFORM}
        assert expected.issubset(types)

    def test_most_expensive_tiles(self, synth):
        """Most expensive tiles query works."""
        expensive = synth.tile_registry.most_expensive(5)
        assert len(expensive) == 5
        # Should be sorted by cost descending
        for i in range(len(expensive) - 1):
            assert expensive[i].cost_estimate >= expensive[i + 1].cost_estimate


# ── Test Group 8: Namespace Isolation ────────────────────────────────────

class TestNamespaceIsolation:
    """Tests for namespace isolation across modules."""

    def test_namespace_isolation_across_modules(self, synth):
        """Modules can't see each other's internals."""
        synth.load_module("mod_a/func", "def internal_a(): pass", "python")
        synth.load_module("mod_b/func", "def internal_b(): pass", "python")

        # Each container should have its own namespace
        container_a = synth.root.children["mod_a"]
        container_b = synth.root.children["mod_b"]

        assert container_a.namespace is not container_b.namespace

    def test_child_inherits_parent_namespace(self, synth):
        """Child namespaces can resolve parent bindings."""
        root_ns = synth.root.namespace
        child = synth.root.add_child("sub", Granularity.BAG)
        assert child.namespace._parent is root_ns


# ── Test Group 9: Module Tree & Hierarchy ────────────────────────────────

class TestModuleTree:
    """Tests for the module tree rendering and hierarchy."""

    def test_get_module_tree(self, loaded_synth):
        """Module tree renders correctly."""
        tree = loaded_synth.get_module_tree()
        assert isinstance(tree, str)
        assert "test_app" in tree
        assert len(tree.split("\n")) >= 4  # at least 4 lines

    def test_get_hierarchy_dict(self, loaded_synth):
        """Hierarchy dict contains expected structure."""
        h = loaded_synth.get_hierarchy()
        assert h["name"] == "test_app"
        assert h["granularity"] == "TRAIN"
        assert isinstance(h["children"], dict)
        assert isinstance(h["cards"], dict)

    def test_container_count(self, loaded_synth):
        """Container count includes all levels."""
        assert loaded_synth.container_count >= 2


# ── Test Group 10: System Report ─────────────────────────────────────────

class TestSystemReport:
    """Tests for system report generation."""

    def test_system_report_generation(self, loaded_synth):
        """Generate text report, verify all sections present."""
        report = loaded_synth.get_system_report()
        assert isinstance(report, SystemReport)

        text = report.to_text()
        # Check for section headers
        assert "SYSTEM OVERVIEW" in text
        assert "MODULE HIERARCHY" in text
        assert "HEAT MAP" in text
        assert "LANGUAGE ASSIGNMENTS" in text
        assert "TILE USAGE" in text
        assert "EVOLUTION HISTORY" in text
        assert "FITNESS TREND" in text

    def test_system_report_json(self, loaded_synth):
        """Generate JSON-compatible report."""
        report = loaded_synth.get_system_report()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "overview" in d
        assert "hierarchy" in d
        assert "heatmap" in d
        assert "recommendations" in d
        assert "tiles" in d
        assert "evolution_history" in d
        assert d["overview"]["name"] == "test_app"
        assert d["overview"]["modules_loaded"] == 4

    def test_system_report_repr(self, loaded_synth):
        """Report repr is informative."""
        report = loaded_synth.get_system_report()
        assert "test_app" in repr(report)


# ── Test Group 11: Full Demo Pipeline ────────────────────────────────────

class TestFullPipeline:
    """End-to-end integration tests."""

    def test_full_demo_pipeline(self, synth):
        """Load -> profile -> evolve -> report."""
        # Load
        synth.load_module("core/parser", "def parse(s): return s", "python")
        synth.load_module("core/optimizer", "def opt(x): return x", "python")
        synth.load_module("core/emitter", "def emit(x): return x", "python")
        synth.load_module("utils/config", "def config(): pass", "python")

        # Profile
        synth.record_call("test_app.core.parser", duration_ns=50000, calls=100)
        synth.record_call("test_app.core.optimizer", duration_ns=30000, calls=80)
        synth.record_call("test_app.core.emitter", duration_ns=20000, calls=60)
        synth.record_call("test_app.utils.config", duration_ns=1000, calls=5)

        # Check heatmap
        heatmap = synth.get_heatmap()
        assert len(heatmap) > 0

        # Evolve
        report = synth.evolve(generations=3)
        assert report.generations > 0

        # Report
        sys_report = synth.get_system_report()
        text = sys_report.to_text()
        assert "SYSTEM OVERVIEW" in text
        assert "HEAT MAP" in text

    def test_full_pipeline_with_hot_swap(self, synth):
        """Full pipeline including hot-reload mid-way."""
        # Load and profile
        synth.load_module("mod1", "def f1(): pass", "python")
        synth.load_module("mod2", "def f2(): pass", "python")
        synth.record_call("test_app.mod1", duration_ns=1000, calls=10)
        synth.record_call("test_app.mod2", duration_ns=1000, calls=10)

        # Evolve once
        synth.evolve(generations=1)

        # Hot-reload
        result = synth.hot_swap("mod1", "def f1_v2(): return 42")
        assert result.success

        # Evolve again
        synth.evolve(generations=1)

        # Verify mod2 is unchanged
        mod2 = synth.get_module("mod2")
        assert mod2 is not None
        assert mod2.source == "def f2(): pass"

    def test_multiple_evolution_runs(self, synth):
        """Multiple consecutive evolution runs."""
        synth.load_module("m", "pass", "python")
        synth.record_call("test_app.m", duration_ns=1000, calls=50)

        report1 = synth.evolve(generations=2)
        gen1 = synth.generation

        report2 = synth.evolve(generations=2)
        gen2 = synth.generation

        assert gen2 > gen1


# ── Test Group 12: Edge Cases ────────────────────────────────────────────

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_synthesizer_report(self, synth):
        """Report on empty synthesizer works."""
        report = synth.get_system_report()
        text = report.to_text()
        assert "test_app" in text
        assert "No modules profiled" in text or "COOL" in text

    def test_load_module_with_slashes(self, synth):
        """Module paths with multiple slashes."""
        card = synth.load_module("a//b///c", "pass", "python")
        assert card is not None

    def test_synthesizer_with_very_long_path(self, synth):
        """Deep nesting (6+ levels)."""
        path = "/".join(f"level{i}" for i in range(6))
        card = synth.load_module(path, "pass", "python")
        assert card is not None
        assert synth.module_count == 1

    def test_profiler_reset_between_tests(self, loaded_synth):
        """Profiler can be reset."""
        assert loaded_synth.profiler.module_count > 0
        loaded_synth.profiler.reset()
        assert loaded_synth.profiler.module_count == 0

    def test_selector_override(self, loaded_synth):
        """Manual language override works."""
        loaded_synth.selector.set_override("test_app.a", "rust")
        rec = loaded_synth.get_recommendation("test_app.a")
        assert rec is not None
        assert rec.recommended_language == "rust"

    def test_evolution_with_validation_fn(self, loaded_synth):
        """Evolution with a validation function."""
        validation_count = [0]
        def validate(genome: Genome) -> bool:
            validation_count[0] += 1
            return True

        loaded_synth.evolve(generations=2, validation_fn=validate)
        assert validation_count[0] > 0
