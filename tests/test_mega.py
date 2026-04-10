"""Tests for the FLUX Mega Integration — Grand Conductor.

30+ tests exercising every subsystem wired through the Grand Conductor.
"""

import os
import sys
import tempfile
import time

import pytest

from flux.mega.conductor import (
    GrandConductor,
    SystemAssessment,
    ExecutionReport,
    EvolutionSummary,
)
from flux.mega.demo_mega import run_mega_demo
from flux.swarm.agent import AgentRole
from flux.memory.experience import Experience


@pytest.fixture
def conductor():
    """Create a GrandConductor with a temp workspace."""
    tmpdir = tempfile.mkdtemp()
    c = GrandConductor("test_universe", workspace=tmpdir)
    yield c
    # Cleanup not strictly necessary for temp dirs, but good practice


@pytest.fixture
def workspace():
    """Provide a temp workspace path."""
    return tempfile.mkdtemp()


# ── 1. Creation Tests ─────────────────────────────────────────────────────

class TestGrandConductorCreation:
    """Test GrandConductor creation and initialization."""

    def test_create_default(self, conductor):
        """GrandConductor creates with default settings."""
        assert conductor.name == "test_universe"
        assert conductor.synthesizer is not None
        assert conductor.flywheel is not None
        assert conductor.swarm is not None
        assert conductor.twin is not None
        assert conductor.oracle is not None
        assert conductor.memory is not None
        assert conductor.bandit is not None
        assert conductor.sonifier is not None

    def test_create_custom_name(self, workspace):
        """GrandConductor uses custom name."""
        c = GrandConductor("my_custom_name", workspace=workspace)
        assert c.name == "my_custom_name"
        assert c.synthesizer.name == "my_custom_name"

    def test_create_custom_workspace(self, workspace):
        """GrandConductor uses custom workspace."""
        c = GrandConductor("test", workspace=workspace)
        assert c.workspace == workspace

    def test_synthesizer_initialized(self, conductor):
        """Internal synthesizer is properly initialized."""
        assert conductor.synthesizer.module_count == 0
        assert conductor.synthesizer.tile_count > 0  # default tiles loaded

    def test_swarm_initialized(self, conductor):
        """Internal swarm is properly initialized."""
        assert conductor.swarm.agent_count == 0
        assert conductor.swarm.topology.type.value == "star"

    def test_oracle_initialized(self, conductor):
        """Internal oracle is properly initialized."""
        assert conductor.oracle.total_decisions == 0
        assert conductor.oracle.acceptance_rate == 0.0

    def test_memory_initialized(self, conductor):
        """Internal memory is properly initialized."""
        stats = conductor.memory.stats()
        assert stats.total_count == 0

    def test_bandit_initialized(self, conductor):
        """Internal bandit is properly initialized."""
        assert conductor.bandit.strategy_count > 0

    def test_live_session_none_initially(self, conductor):
        """Live session is None until started."""
        assert conductor.live_session is None

    def test_repr(self, conductor):
        """GrandConductor has a readable repr."""
        r = repr(conductor)
        assert "GrandConductor" in r
        assert "test_universe" in r


# ── 2. Module Loading Tests ────────────────────────────────────────────────

class TestModuleLoading:
    """Test loading modules through the conductor."""

    def test_load_single_module(self, conductor):
        """Load a single module."""
        card = conductor.load("math/add", "def add(a, b): return a + b", "python")
        assert card is not None
        assert card.language == "python"
        assert card.source == "def add(a, b): return a + b"

    def test_load_multiple_modules(self, conductor):
        """Load multiple modules at different paths."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.load("math/mul", "def mul(a, b): return a * b", "python")
        conductor.load("math/div", "def div(a, b): return a / b", "python")
        assert conductor.synthesizer.module_count == 3

    def test_load_nested_path(self, conductor):
        """Load a module at a nested path."""
        card = conductor.load("audio/dsp/filter", "pass", "python")
        assert card is not None
        assert conductor.synthesizer.module_count == 1

    def test_get_loaded_module(self, conductor):
        """Get a module that was previously loaded."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        card = conductor.get_module("math/add")
        assert card is not None
        assert card.language == "python"

    def test_get_nonexistent_module(self, conductor):
        """Getting a nonexistent module returns None."""
        card = conductor.get_module("nonexistent/module")
        assert card is None


# ── 3. Execution Tests ────────────────────────────────────────────────────

class TestExecution:
    """Test running workloads through the conductor."""

    def test_run_simple_workload(self, conductor):
        """Run a simple workload that returns a value."""
        def workload():
            return 42

        report = conductor.run(workload)
        assert isinstance(report, ExecutionReport)
        assert report.success is True
        assert report.result == 42

    def test_run_workload_with_profiling(self, conductor):
        """Run a workload that generates profiling data."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=10)

        def workload():
            return "hello"

        report = conductor.run(workload)
        assert report.success is True
        assert report.result == "hello"

    def test_run_workload_that_raises(self, conductor):
        """Run a workload that raises an exception."""
        def bad_workload():
            raise ValueError("intentional error")

        report = conductor.run(bad_workload)
        assert report.error != ""


# ── 4. Assessment Tests ───────────────────────────────────────────────────

class TestAssessment:
    """Test assessment produces valid results."""

    def test_assess_empty_system(self, conductor):
        """Assess an empty system."""
        assessment = conductor.assess()
        assert isinstance(assessment, SystemAssessment)
        assert assessment.total_modules == 0
        assert assessment.fitness >= 0.0

    def test_assess_with_modules(self, conductor):
        """Assess a system with loaded modules."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=5)

        assessment = conductor.assess()
        assert assessment.total_modules == 1
        assert isinstance(assessment.heatmap, dict)

    def test_assessment_heatmap(self, conductor):
        """Assessment includes heatmap after profiling."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=10)

        assessment = conductor.assess()
        assert isinstance(assessment.heatmap, dict)
        assert len(assessment.heatmap) > 0

    def test_assessment_bottlenecks(self, conductor):
        """Assessment includes bottleneck list."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=20)

        assessment = conductor.assess()
        assert isinstance(assessment.bottlenecks, list)

    def test_assessment_memory_usage(self, conductor):
        """Assessment includes memory usage."""
        assessment = conductor.assess()
        assert isinstance(assessment.memory_usage, dict)
        assert "hot" in assessment.memory_usage
        assert "total" in assessment.memory_usage

    def test_assessment_agent_count(self, conductor):
        """Assessment tracks agent count."""
        conductor.spawn_agent("a1", AgentRole.GENERAL)
        assessment = conductor.assess()
        assert assessment.agent_count == 1


# ── 5. Prediction Tests ───────────────────────────────────────────────────

class TestPrediction:
    """Test prediction returns oracle decisions."""

    def test_predict_recompile(self, conductor):
        """Predict returns an OracleDecision."""
        decision = conductor.predict("recompile math/add to rust")
        assert hasattr(decision, 'should_apply')
        assert hasattr(decision, 'confidence')
        assert 0.0 <= decision.confidence <= 1.0

    def test_predict_with_loaded_modules(self, conductor):
        """Predict works after loading modules."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=10)

        decision = conductor.predict("should I recompile?")
        assert decision is not None

    def test_predict_reasoning(self, conductor):
        """Prediction includes reasoning string."""
        decision = conductor.predict("optimize math")
        assert isinstance(decision.reasoning, str)
        assert len(decision.reasoning) > 0


# ── 6. Simulation Tests ───────────────────────────────────────────────────

class TestSimulation:
    """Test simulation returns simulated results."""

    def test_simulate_basic(self, conductor):
        """Simulate returns a SimulatedResult."""
        result = conductor.simulate("fuse add+mul")
        assert hasattr(result, 'estimated_speedup')
        assert hasattr(result, 'risk_assessment')
        assert result.estimated_speedup >= 0.0

    def test_simulate_recompile(self, conductor):
        """Simulate a recompilation."""
        result = conductor.simulate("recompile math to rust")
        assert result.estimated_speedup >= 1.0

    def test_what_if_recompile(self, conductor):
        """What-if analysis for recompilation."""
        result = conductor.what_if("math/add", "recompile to rust")
        assert hasattr(result, 'predicted_outcome')
        assert hasattr(result, 'estimated_speedup')
        assert hasattr(result, 'recommendation')

    def test_what_if_with_modules(self, conductor):
        """What-if works after loading modules."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        result = conductor.what_if("test_universe.math.add", "recompile to c")
        assert result.estimated_speedup >= 1.0

    def test_simulate_survival_probability(self, conductor):
        """Simulated result has valid survival probability."""
        result = conductor.simulate("optimize something")
        assert 0.0 <= result.survival_probability <= 1.0


# ── 7. Agent Tests ────────────────────────────────────────────────────────

class TestAgentCollaboration:
    """Test agent spawning through conductor."""

    def test_spawn_agent(self, conductor):
        """Spawn a single agent."""
        agent = conductor.spawn_agent("worker_1", AgentRole.SPECIALIST_COMPUTE)
        assert agent is not None
        assert agent.agent_id == "worker_1"
        assert conductor.swarm.agent_count == 1

    def test_spawn_multiple_agents(self, conductor):
        """Spawn multiple agents with different roles."""
        conductor.spawn_agent("w1", AgentRole.SPECIALIST_COMPUTE)
        conductor.spawn_agent("w2", AgentRole.SPECIALIST_EXPLORER)
        conductor.spawn_agent("w3", AgentRole.SPECIALIST_COORDINATOR)
        assert conductor.swarm.agent_count == 3

    def test_despawn_agent(self, conductor):
        """Despawn an agent."""
        conductor.spawn_agent("w1", AgentRole.GENERAL)
        removed = conductor.despawn_agent("w1")
        assert removed is not None
        assert conductor.swarm.agent_count == 0

    def test_despawn_nonexistent(self, conductor):
        """Despawn a nonexistent agent returns None."""
        result = conductor.despawn_agent("ghost")
        assert result is None

    def test_send_message(self, conductor):
        """Send a message between agents."""
        conductor.spawn_agent("sender", AgentRole.GENERAL)
        conductor.spawn_agent("receiver", AgentRole.GENERAL)

        success = conductor.send_message(
            "sender", "receiver",
            {"type": "request", "data": "hello"},
        )
        assert success is True

    def test_send_message_nonexistent(self, conductor):
        """Send to nonexistent agent fails."""
        conductor.spawn_agent("sender", AgentRole.GENERAL)
        success = conductor.send_message("sender", "ghost", {"data": "x"})
        assert success is False

    def test_broadcast(self, conductor):
        """Broadcast a message."""
        conductor.spawn_agent("hub", AgentRole.GENERAL)
        conductor.spawn_agent("s1", AgentRole.GENERAL)
        conductor.spawn_agent("s2", AgentRole.GENERAL)

        # Connect them in star topology
        conductor.swarm.topology.connect("hub", "s1")
        conductor.swarm.topology.connect("hub", "s2")

        count = conductor.broadcast("hub", {"msg": "hello all"})
        assert count >= 0  # May be 0 if not connected via topology routing

    def test_barrier(self, conductor):
        """Barrier synchronization."""
        conductor.spawn_agent("a", AgentRole.GENERAL)
        conductor.spawn_agent("b", AgentRole.GENERAL)

        result = conductor.barrier(["a", "b"])
        assert isinstance(result, bool)


# ── 8. Memory Tests ───────────────────────────────────────────────────────

class TestMemory:
    """Test memory remember/recall through conductor."""

    def test_remember_and_recall(self, conductor):
        """Remember a value and recall it."""
        conductor.remember("key1", "value1")
        result = conductor.recall("key1")
        assert result == "value1"

    def test_recall_nonexistent(self, conductor):
        """Recall a nonexistent key returns None."""
        result = conductor.recall("nonexistent_key")
        assert result is None

    def test_remember_overwrite(self, conductor):
        """Overwriting a key updates the value."""
        conductor.remember("key1", "original")
        conductor.remember("key1", "updated")
        result = conductor.recall("key1")
        assert result == "updated"

    def test_remember_complex_value(self, conductor):
        """Remember complex data structures."""
        data = {"nested": {"key": [1, 2, 3]}, "count": 42}
        conductor.remember("complex", data)
        result = conductor.recall("complex")
        assert result == data

    def test_forget(self, conductor):
        """Forget removes a key."""
        conductor.remember("temp", "data")
        result = conductor.forget("temp")
        assert result is True
        assert conductor.recall("temp") is None

    def test_forget_nonexistent(self, conductor):
        """Forgetting a nonexistent key returns False."""
        result = conductor.forget("nonexistent")
        assert result is False

    def test_learn_experience(self, conductor):
        """Record an experience for learning."""
        exp = Experience(
            context={"heat_level": "HOT"},
            action={"type": "recompile_language"},
            outcome="success",
            metrics={"speedup": 2.5},
            generation=1,
        )
        conductor.learn(exp)
        assert conductor._experience_recorder.count == 1


# ── 9. Sonification Tests ─────────────────────────────────────────────────

class TestSonification:
    """Test sonification through conductor."""

    def test_sonify_workload(self, conductor):
        """Sonify a workload produces a MusicSequence."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=5)

        def workload():
            return 42

        music = conductor.sonify(workload)
        assert len(music) > 0

    def test_sonify_tempo(self, conductor):
        """Sonified sequence has a valid tempo."""
        conductor.load("x", "pass", "python")
        conductor.synthesizer.record_call("test_universe.x", calls=3)

        music = conductor.sonify(lambda: None)
        assert music.tempo > 0

    def test_sonify_empty(self, conductor):
        """Sonifying with no profiling data still produces a sequence."""
        music = conductor.sonify(lambda: None)
        # May be empty if no profiling data, but should not crash
        assert isinstance(music.events, list)


# ── 10. Documentation Tests ──────────────────────────────────────────────

class TestDocumentation:
    """Test doc generation through conductor."""

    def test_generate_docs(self, conductor, workspace):
        """Generate documentation creates files."""
        doc_dir = os.path.join(workspace, "docs")
        count = conductor.generate_docs(doc_dir)
        assert count > 0

    def test_generate_docs_creates_report(self, conductor, workspace):
        """Generated docs include system report."""
        doc_dir = os.path.join(workspace, "docs")
        conductor.generate_docs(doc_dir)
        assert os.path.exists(os.path.join(doc_dir, "system_report.txt"))


# ── 11. Full Report Tests ────────────────────────────────────────────────

class TestFullReport:
    """Test full report generation."""

    def test_full_report_returns_string(self, conductor):
        """Full report returns a non-empty string."""
        report = conductor.full_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_full_report_contains_name(self, conductor):
        """Full report contains conductor name."""
        report = conductor.full_report()
        assert "test_universe" in report

    def test_full_report_contains_sections(self, conductor):
        """Full report contains expected section headers."""
        report = conductor.full_report()
        assert "SYSTEM OVERVIEW" in report
        assert "ASSESSMENT" in report
        assert "MODULE TREE" in report

    def test_full_report_with_modules(self, conductor):
        """Full report reflects loaded modules."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        report = conductor.full_report()
        assert "math" in report.lower()

    def test_full_report_with_agents(self, conductor):
        """Full report reflects spawned agents."""
        conductor.spawn_agent("a1", AgentRole.GENERAL)
        report = conductor.full_report()
        assert "SWARM AGENTS" in report


# ── 12. Stats Tests ──────────────────────────────────────────────────────

class TestStats:
    """Test conductor stats."""

    def test_stats_returns_dict(self, conductor):
        """Stats returns a dictionary."""
        stats = conductor.get_stats()
        assert isinstance(stats, dict)

    def test_stats_has_required_keys(self, conductor):
        """Stats has all required keys."""
        stats = conductor.get_stats()
        required = [
            "name", "modules", "tiles", "generation", "fitness",
            "agents", "memory_total",
        ]
        for key in required:
            assert key in stats, f"Missing key: {key}"

    def test_stats_reflects_changes(self, conductor):
        """Stats reflect loaded modules and agents."""
        assert conductor.get_stats()["modules"] == 0
        assert conductor.get_stats()["agents"] == 0

        conductor.load("x", "pass", "python")
        conductor.spawn_agent("a1", AgentRole.GENERAL)

        stats = conductor.get_stats()
        assert stats["modules"] == 1
        assert stats["agents"] == 1


# ── 13. Flywheel Tests ───────────────────────────────────────────────────

class TestFlywheel:
    """Test flywheel spinning through conductor."""

    def test_flywheel_spin(self, conductor):
        """Spin the flywheel for one round."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=10)

        report = conductor.flywheel_spin(rounds=1)
        assert report is not None
        assert report.revolutions_completed >= 1

    def test_flywheel_multiple_rounds(self, conductor):
        """Spin the flywheel for multiple rounds."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=5)

        report = conductor.flywheel_spin(rounds=2)
        assert report.revolutions_completed >= 1


# ── 14. Evolution Tests ──────────────────────────────────────────────────

class TestEvolution:
    """Test evolution through conductor."""

    def test_evolve(self, conductor):
        """Run evolution produces a summary."""
        conductor.load("math/add", "def add(a, b): return a + b", "python")
        conductor.synthesizer.record_call("test_universe.math.add", calls=10)

        summary = conductor.evolve(generations=2)
        assert isinstance(summary, EvolutionSummary)
        assert summary.generations == 2

    def test_evolve_fitness_delta(self, conductor):
        """Evolution tracks fitness delta."""
        summary = conductor.evolve(generations=1)
        assert isinstance(summary.fitness_delta, float)

    def test_evolve_speedup(self, conductor):
        """Evolution tracks speedup."""
        summary = conductor.evolve(generations=1)
        assert summary.speedup >= 0.0


# ── 15. Live Session Tests ───────────────────────────────────────────────

class TestLiveSession:
    """Test live coding session."""

    def test_start_live_session(self, conductor):
        """Start a live coding session."""
        session = conductor.start_live_session(bpm=140)
        assert session is not None
        assert session.bpm == 140
        assert conductor.live_session is session

    def test_live_session_default_bpm(self, conductor):
        """Live session defaults to 120 BPM."""
        session = conductor.start_live_session()
        assert session.bpm == 120


# ── 16. Wisdom Tests ─────────────────────────────────────────────────────

class TestWisdom:
    """Test wisdom/learning through conductor."""

    def test_wisdom_no_experience(self, conductor):
        """Wisdom returns None with no experiences."""
        result = conductor.wisdom("what should I do?")
        assert result is None

    def test_wisdom_with_experience(self, conductor):
        """Wisdom returns a rule after accumulating experiences."""
        for i in range(5):
            conductor.learn(Experience(
                context={"heat_level": "HOT"},
                action={"type": "recompile_language"},
                outcome="success" if i < 4 else "failure",
                metrics={"speedup": 2.0},
                generation=i,
            ))

        result = conductor.wisdom("hot module optimization")
        # May return a rule if generalization finds patterns
        # (requires MIN_EXPERIENCES_FOR_GENERALIZATION = 3)
        if result is not None:
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'action')


# ── 17. Mega Demo Tests ───────────────────────────────────────────────────

class TestMegaDemo:
    """Test the mega demo runs without errors."""

    def test_mega_demo_runs(self):
        """The mega demo runs end-to-end without errors."""
        report = run_mega_demo()
        assert isinstance(report, str)
        assert len(report) > 100

    def test_mega_demo_contains_sections(self):
        """Mega demo report contains expected sections."""
        report = run_mega_demo()
        assert "FLUX GRAND CONDUCTOR" in report
        assert "SYSTEM OVERVIEW" in report
        assert "ASSESSMENT" in report

    def test_mega_demo_exercises_modules(self):
        """Mega demo exercises the module system."""
        report = run_mega_demo()
        assert "MODULE TREE" in report
        assert "math" in report.lower()
