"""Grand Conductor — the single entry point for the entire FLUX system.

The GrandConductor orchestrates all FLUX subsystems into one cohesive machine:

    conductor = GrandConductor("my_universe")
    conductor.load("audio/dsp/filter", source, "python")
    conductor.run(my_workload)
    report = conductor.assess()
    conductor.evolve(generations=5)
    improved = conductor.assess()
    print(f"Speedup: {improved.cumulative_speedup}x")
    conductor.spawn_agent("worker_1", AgentRole.COMPUTE)
    prediction = conductor.predict("Should I recompile audio/dsp/filter to C?")
    simulation = conductor.simulate("Replace map+filter with flatmap")
    music = conductor.sonify(my_workload)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ── Core subsystems ──────────────────────────────────────────────────────────
from flux.synthesis.synthesizer import (
    FluxSynthesizer,
    WorkloadResult,
)
from flux.flywheel.engine import FlywheelEngine
from flux.flywheel.hypothesis import FlywheelReport
from flux.swarm.swarm import Swarm
from flux.swarm.agent import FluxAgent, AgentRole, AgentMessage
from flux.swarm.topology import SwarmTopology, Topology
from flux.simulation.digital_twin import (
    DigitalTwin,
    SimulatedResult,
    WhatIfResult,
)
from flux.simulation.oracle import (
    DecisionOracle,
    OracleDecision,
)
from flux.simulation.predictor import (
    PerformancePredictor,
    MemoryStore as PredictorMemoryStore,
)
from flux.cost.model import CostModel
from flux.flywheel.knowledge import KnowledgeBase
from flux.memory.bandit import MutationBandit
from flux.memory.store import (
    MemoryStore,
    MemoryStats,
)
from flux.memory.experience import (
    Experience,
    ExperienceRecorder,
    GeneralizedRule as MemoryGeneralizedRule,
)
from flux.evolution.evolution import EvolutionReport
from flux.evolution.genome import Genome
from flux.modules.card import ModuleCard
from flux.creative.sonification import Sonifier, MusicSequence, ExecutionEvent
from flux.creative.live import LiveCodingSession
from flux.adaptive.profiler import AdaptiveProfiler


# ── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class ExecutionReport:
    """Result of running a workload through the Grand Conductor."""
    success: bool = True
    elapsed_ns: int = 0
    elapsed_ms: float = 0.0
    result: Any = None
    heatmap: dict[str, str] = field(default_factory=dict)
    error: str = ""


@dataclass
class SystemAssessment:
    """Comprehensive assessment of the current system state."""
    heatmap: dict[str, str] = field(default_factory=dict)
    recommendations: dict[str, str] = field(default_factory=dict)
    bottlenecks: list[str] = field(default_factory=list)
    fitness: float = 0.0
    modularity: float = 0.0
    total_modules: int = 0
    total_tiles_active: int = 0
    cumulative_speedup: float = 1.0
    memory_usage: dict = field(default_factory=dict)
    agent_count: int = 0


@dataclass
class EvolutionSummary:
    """Summary of an evolution run."""
    generations: int = 0
    initial_fitness: float = 0.0
    final_fitness: float = 0.0
    fitness_delta: float = 0.0
    speedup: float = 1.0
    mutations_applied: int = 0
    mutations_rejected: int = 0


# ── Grand Conductor ──────────────────────────────────────────────────────────

class GrandConductor:
    """The Grand Conductor orchestrates all FLUX subsystems.

    This is the top-level API that exposes the full power of FLUX:

    conductor = GrandConductor("my_universe")

    # Load code
    conductor.load("audio/dsp/filter", source, "python")
    conductor.load("physics/sim", source, "python")

    # Run and profile
    conductor.run(my_workload)

    # See what the system learned
    report = conductor.assess()

    # Let the system improve itself
    conductor.evolve(generations=5)

    # Watch it get faster
    improved = conductor.assess()
    print(f"Speedup: {improved.cumulative_speedup}x")

    # Spawn agents for parallel work
    conductor.spawn_agent("worker_1", AgentRole.COMPUTE)
    conductor.spawn_agent("worker_2", AgentRole.EXPLORER)

    # Predict before acting
    prediction = conductor.predict("Should I recompile audio/dsp/filter to C?")

    # Simulate without risk
    simulation = conductor.simulate("Replace map+filter with flatmap")

    # Make music from the execution
    music = conductor.sonify(my_workload)
    """

    def __init__(self, name: str, workspace: str = ".flux"):
        self.name = name
        self.workspace = workspace
        self._created_at = time.time()

        # Core synthesis engine
        self.synthesizer = FluxSynthesizer(name)

        # Flywheel (self-reinforcing improvement)
        self.flywheel = FlywheelEngine(self.synthesizer)

        # Swarm (multi-agent collaboration)
        self.swarm = Swarm(name, Topology(SwarmTopology.STAR))

        # Digital twin (shadow copy for simulation)
        self.twin = DigitalTwin(self.synthesizer)

        # Decision oracle (prediction + knowledge)
        self.oracle = DecisionOracle(
            PerformancePredictor(CostModel(), PredictorMemoryStore()),
            self.twin,
            KnowledgeBase(),
            MutationBandit(),
        )

        # Memory system (four-tier persistent storage)
        self.memory = MemoryStore(os.path.join(workspace, "memory"))

        # Bandit (multi-armed strategy selection)
        self.bandit = MutationBandit()

        # Experience recorder
        self._experience_recorder = ExperienceRecorder(store=self.memory)

        # Sonifier (code-to-music)
        self.sonifier = Sonifier()

        # Live coding session (created on demand)
        self.live_session: Optional[LiveCodingSession] = None

        # Tracking
        self._evolution_reports: list[EvolutionReport] = []
        self._flywheel_reports: list[FlywheelReport] = []
        self._total_runs: int = 0

    # ── Loading ────────────────────────────────────────────────────────────

    def load(self, path: str, source: str, language: str = "python") -> ModuleCard:
        """Load a module into the system.

        Args:
            path: Slash-separated module path (e.g. "audio/dsp/filter").
            source: Source code for the module.
            language: Language of the source (default "python").

        Returns:
            The ModuleCard created for the module.
        """
        return self.synthesizer.load_module(path, source, language)

    def get_module(self, path: str) -> Optional[ModuleCard]:
        """Get a module card by path."""
        return self.synthesizer.get_module(path)

    # ── Execution ─────────────────────────────────────────────────────────

    def run(self, workload: Callable) -> ExecutionReport:
        """Run a workload and profile it.

        Args:
            workload: A callable function to execute.

        Returns:
            ExecutionReport with profiling data and result.
        """
        self._total_runs += 1
        result: Any = None
        error = ""

        try:
            result = workload()
        except Exception as exc:
            error = str(exc)

        synth_result = self.synthesizer.run_workload(workload)

        report = ExecutionReport(
            success=synth_result.success and not error,
            elapsed_ns=synth_result.elapsed_ns,
            elapsed_ms=synth_result.elapsed_ms,
            result=result,
            heatmap=synth_result.heatmap,
            error=error or synth_result.error,
        )
        return report

    # ── Assessment ────────────────────────────────────────────────────────

    def assess(self) -> SystemAssessment:
        """Assess the current state of the system.

        Returns:
            SystemAssessment with heatmap, recommendations, bottlenecks,
            fitness, modularity, and more.
        """
        heatmap = self.synthesizer.get_heatmap()
        recommendations = self.synthesizer.get_recommendations()

        # Build recommendation strings
        rec_dict: dict[str, str] = {}
        for path, rec in recommendations.items():
            rec_dict[path] = (
                f"{rec.recommended_language} "
                f"(was {rec.current_language}, heat={rec.heat_level.name})"
            )

        # Bottlenecks
        bottleneck_report = self.synthesizer.get_bottleneck_report(5)
        bottlenecks = [e.module_path for e in bottleneck_report.entries]

        # Memory stats
        mem_stats = self.memory.stats()
        memory_usage = {
            "hot": mem_stats.hot_count,
            "warm": mem_stats.warm_count,
            "cold": mem_stats.cold_count,
            "frozen": mem_stats.frozen_count,
            "total": mem_stats.total_count,
        }

        # Cumulative speedup from evolution history
        history = self.synthesizer.get_evolution_history()
        cumulative_speedup = 1.0
        if len(history) >= 2:
            final = max(history[-1][1], 0.001)
            initial = max(history[0][1], 0.001)
            cumulative_speedup = final / initial

        assessment = SystemAssessment(
            heatmap=heatmap,
            recommendations=rec_dict,
            bottlenecks=bottlenecks,
            fitness=self.synthesizer.current_fitness,
            modularity=0.5,  # default, updated by selector
            total_modules=self.synthesizer.module_count,
            total_tiles_active=self.synthesizer.tile_count,
            cumulative_speedup=cumulative_speedup,
            memory_usage=memory_usage,
            agent_count=self.swarm.agent_count,
        )

        # Update modularity from selector if available
        try:
            assessment.modularity = self.synthesizer.selector.get_modularity_score()
        except Exception:
            pass

        return assessment

    # ── Evolution ─────────────────────────────────────────────────────────

    def evolve(self, generations: int = 5) -> EvolutionSummary:
        """Run the evolution engine.

        Args:
            generations: Number of evolution cycles to run.

        Returns:
            EvolutionSummary with fitness changes and mutation stats.
        """
        initial_fitness = self.synthesizer.current_fitness

        report = self.synthesizer.evolve(generations=generations)
        self._evolution_reports.append(report)

        final_fitness = self.synthesizer.current_fitness

        # Count applied mutations from records
        mutations_applied = sum(
            1 for r in report.records if hasattr(r, 'successes')
        )

        return EvolutionSummary(
            generations=generations,
            initial_fitness=initial_fitness,
            final_fitness=final_fitness,
            fitness_delta=final_fitness - initial_fitness,
            speedup=final_fitness / max(initial_fitness, 0.001),
            mutations_applied=mutations_applied,
            mutations_rejected=0,
        )

    def flywheel_spin(self, rounds: int = 3) -> FlywheelReport:
        """Spin the flywheel for N complete revolutions.

        Each revolution runs 6 phases:
        OBSERVE → LEARN → HYPOTHESIZE → EXPERIMENT → INTEGRATE → ACCELERATE

        Args:
            rounds: Number of complete revolutions to spin.

        Returns:
            FlywheelReport with all results and metrics.
        """
        report = self.flywheel.spin(rounds=rounds)
        self._flywheel_reports.append(report)
        return report

    # ── Prediction ────────────────────────────────────────────────────────

    def predict(self, question: str) -> OracleDecision:
        """Ask the oracle a question.

        The oracle combines predictions, twin simulations, and historical
        data to make optimal decisions.

        Args:
            question: A natural language question about system optimization.

        Returns:
            OracleDecision with recommendation, confidence, and reasoning.
        """
        # Capture shadow state for accurate simulation
        self.twin.capture_shadow()

        # Get the next best action recommendation
        recommendation = self.oracle.next_best_action()

        # Build a synthetic proposal for the decision
        from flux.evolution.genome import MutationStrategy
        from flux.evolution.mutator import MutationProposal

        if recommendation.action.startswith("recompile:"):
            strategy = MutationStrategy.RECOMPILE_LANGUAGE
            target = recommendation.target
            desc = f"Recompile {target} to faster language"
            kwargs = {"new_language": "rust"}
        elif recommendation.action.startswith("replace_tile:"):
            strategy = MutationStrategy.REPLACE_TILE
            target = recommendation.target
            desc = f"Replace expensive tile {target}"
            kwargs = {"new_cost": 1.0}
        else:
            strategy = MutationStrategy.INLINE_OPTIMIZATION
            target = question[:50]
            desc = f"Optimize based on: {question}"
            kwargs = {}

        proposal = MutationProposal(
            strategy=strategy,
            target=target,
            description=desc,
            kwargs=kwargs,
            estimated_speedup=recommendation.estimated_speedup,
            estimated_risk=recommendation.risk,
            priority=5.0,
        )

        return self.oracle.should_mutate(proposal)

    def simulate(self, description: str) -> SimulatedResult:
        """Simulate a change without applying it.

        Args:
            description: Description of the change to simulate.

        Returns:
            SimulatedResult with estimated outcomes.
        """
        self.twin.capture_shadow()

        from flux.evolution.genome import MutationStrategy
        from flux.evolution.mutator import MutationProposal

        # Infer strategy from description
        desc_lower = description.lower()
        if "recompile" in desc_lower or "rust" in desc_lower or "c" in desc_lower:
            strategy = MutationStrategy.RECOMPILE_LANGUAGE
            kwargs = {"new_language": "rust"}
        elif "fuse" in desc_lower or "merge" in desc_lower or "combine" in desc_lower:
            strategy = MutationStrategy.FUSE_PATTERN
            kwargs = {}
        elif "replace" in desc_lower or "swap" in desc_lower:
            strategy = MutationStrategy.REPLACE_TILE
            kwargs = {"new_cost": 0.5}
        else:
            strategy = MutationStrategy.INLINE_OPTIMIZATION
            kwargs = {"speedup": 1.2}

        # Find a target from shadow genome
        targets = list(self.twin.shadow_genome.modules.keys())
        target = targets[0] if targets else "unknown_module"

        proposal = MutationProposal(
            strategy=strategy,
            target=target,
            description=description,
            kwargs=kwargs,
            estimated_speedup=1.5,
            estimated_risk=0.3,
            priority=5.0,
        )

        return self.twin.simulate_mutation(proposal)

    def what_if(self, module_path: str, change: str) -> WhatIfResult:
        """What-if analysis for a specific module change.

        Args:
            module_path: Path to the module.
            change: Description of the change (e.g. "recompile to rust").

        Returns:
            WhatIfResult with predicted outcomes.
        """
        self.twin.capture_shadow()

        change_lower = change.lower()

        if "recompile" in change_lower or "to " in change_lower:
            # Extract target language
            target_lang = "rust"
            for lang in ["rust", "c", "c_simd", "typescript", "csharp"]:
                if lang in change_lower:
                    target_lang = lang
                    break
            return self.twin.what_if_recompile(module_path, target_lang)
        elif "replace" in change_lower or "swap" in change_lower:
            parts = change_lower.split("with")
            new_tile = parts[1].strip() if len(parts) > 1 else "optimized"
            return self.twin.what_if_replace_tile(module_path, new_tile)
        else:
            # Default: treat as recompile to rust
            return self.twin.what_if_recompile(module_path, "rust")

    # ── Agent Collaboration ───────────────────────────────────────────────

    def spawn_agent(self, agent_id: str, role: AgentRole) -> FluxAgent:
        """Spawn a new agent in the swarm.

        Args:
            agent_id: Unique identifier for the agent.
            role: Initial agent role/specialization.

        Returns:
            The newly created FluxAgent.
        """
        return self.swarm.spawn(agent_id, role)

    def despawn_agent(self, agent_id: str) -> Optional[FluxAgent]:
        """Remove an agent from the swarm.

        Args:
            agent_id: Agent to remove.

        Returns:
            The removed agent, or None if not found.
        """
        return self.swarm.despawn(agent_id)

    def send_message(self, from_id: str, to_id: str, content: dict) -> bool:
        """Send a direct message between agents.

        Args:
            from_id: Sender agent ID.
            to_id: Receiver agent ID.
            content: Message payload dictionary.

        Returns:
            True if delivered successfully.
        """
        return self.swarm.message_bus.send(
            from_id, to_id, content, msg_type="request"
        )

    def broadcast(self, from_id: str, content: dict) -> int:
        """Broadcast a message from an agent to its neighbors.

        Args:
            from_id: Broadcasting agent ID.
            content: Message payload.

        Returns:
            Number of agents that received the message.
        """
        msg = AgentMessage(
            sender=from_id,
            payload=content,
            msg_type="broadcast",
        )
        return self.swarm.broadcast(from_id, msg)

    def barrier(self, participants: list[str]) -> bool:
        """Synchronization point — wait for all participants.

        Args:
            participants: List of agent IDs that must participate.

        Returns:
            True if all participants have arrived at the barrier.
        """
        return self.swarm.barrier(
            barrier_id=f"barrier_{time.time()}",
            participant_ids=participants,
        )

    # ── Creative ──────────────────────────────────────────────────────────

    def sonify(self, workload: Callable) -> MusicSequence:
        """Run a workload and convert execution trace to music.

        Maps opcodes to notes, heat levels to dynamics, and register
        values to velocities.

        Args:
            workload: A callable function to execute and sonify.

        Returns:
            MusicSequence with musical events derived from the execution.
        """
        # Create execution events from profiling data
        self.synthesizer.run_workload(workload)

        # Build execution trace from profiler data
        trace: list[ExecutionEvent] = []
        for mod_path, count in self.synthesizer.profiler.call_counts.items():
            time_ns = self.synthesizer.profiler.total_time_ns.get(mod_path, 1000)
            heat = self.synthesizer.get_heatmap().get(mod_path, "COOL")

            for i in range(min(count, 20)):  # cap events per module
                trace.append(ExecutionEvent(
                    opcode=(hash(mod_path) + i) % 168,  # map to opcode range
                    time=i * 0.25,
                    register_value=int(time_ns / max(count, 1)) % 127,
                    module_path=mod_path,
                    heat_level=heat,
                ))

        return self.sonifier.execution_trace_to_sequence(trace)

    def start_live_session(self, bpm: int = 120) -> LiveCodingSession:
        """Start a live coding session.

        Args:
            bpm: Beats per minute for the session.

        Returns:
            LiveCodingSession connected to the synthesizer.
        """
        self.live_session = LiveCodingSession(synthesizer=self.synthesizer)
        self.live_session.set_tempo(bpm)
        return self.live_session

    # ── Memory ────────────────────────────────────────────────────────────

    def remember(self, key: str, value: Any) -> None:
        """Store a value in persistent memory.

        Args:
            key: Unique identifier for this memory.
            value: The data to store.
        """
        self.memory.store(key, value, tier="hot")

    def recall(self, key: str) -> Optional[Any]:
        """Retrieve a value from memory.

        Args:
            key: The memory key to look up.

        Returns:
            The stored value, or None if not found.
        """
        return self.memory.retrieve(key)

    def forget(self, key: str) -> bool:
        """Permanently delete a key from all memory tiers.

        Args:
            key: The memory key to delete.

        Returns:
            True if the key was found and deleted.
        """
        return self.memory.forget(key)

    def learn(self, experience: Experience) -> None:
        """Record an experience for future learning.

        Args:
            experience: The Experience to record.
        """
        self._experience_recorder.record(experience)

    def wisdom(self, question: str) -> Optional[MemoryGeneralizedRule]:
        """Query accumulated wisdom from past experiences.

        Args:
            question: A question about what the system has learned.

        Returns:
            The most relevant GeneralizedRule, or None if no wisdom found.
        """
        rules = self._experience_recorder.generalize()
        if not rules:
            return None
        # Return the most confident rule
        return max(rules, key=lambda r: r.confidence)

    # ── Documentation ─────────────────────────────────────────────────────

    def generate_docs(self, output_dir: str = "docs/generated") -> int:
        """Generate self-documentation.

        Creates a comprehensive system report in the specified directory.

        Args:
            output_dir: Directory to write documentation files.

        Returns:
            Number of documentation files generated.
        """
        count = 0

        try:
            os.makedirs(output_dir, exist_ok=True)

            # System report
            report = self.synthesizer.get_system_report()
            with open(os.path.join(output_dir, "system_report.txt"), "w") as f:
                f.write(report.to_text())
            count += 1

            # Module tree
            tree = self.synthesizer.get_module_tree()
            with open(os.path.join(output_dir, "module_tree.txt"), "w") as f:
                f.write(f"# Module Tree for {self.name}\n\n")
                f.write(tree)
            count += 1

            # JSON report
            import json
            with open(os.path.join(output_dir, "system_report.json"), "w") as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
            count += 1

            # Stats
            stats = self.get_stats()
            with open(os.path.join(output_dir, "stats.json"), "w") as f:
                json.dump(stats, f, indent=2, default=str)
            count += 1

        except Exception:
            pass  # Best-effort doc generation

        return count

    # ── Stats & Info ──────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get comprehensive system statistics.

        Returns:
            Dict with key metrics from all subsystems.
        """
        synth_stats = self.synthesizer.stats()
        mem_stats = self.memory.stats()

        return {
            "name": self.name,
            "workspace": self.workspace,
            "uptime_s": time.time() - self._created_at,
            "total_runs": self._total_runs,
            "evolution_runs": len(self._evolution_reports),
            "flywheel_rounds": len(self._flywheel_reports),
            # Synthesizer
            "modules": synth_stats["modules"],
            "containers": synth_stats["containers"],
            "tiles": synth_stats["tiles"],
            "generation": synth_stats["generation"],
            "fitness": synth_stats["fitness"],
            "profiled_modules": synth_stats["profiled_modules"],
            "samples": synth_stats["samples"],
            # Swarm
            "agents": self.swarm.agent_count,
            "messages": self.swarm.message_bus.total_messages,
            "topology": self.swarm.topology.type.value,
            # Flywheel
            "flywheel_revolution": self.flywheel.revolution,
            "flywheel_acceleration": self.flywheel._acceleration_factor,
            # Oracle
            "oracle_decisions": self.oracle.total_decisions,
            "oracle_acceptance_rate": self.oracle.acceptance_rate,
            # Memory
            "memory_hot": mem_stats.hot_count,
            "memory_warm": mem_stats.warm_count,
            "memory_cold": mem_stats.cold_count,
            "memory_frozen": mem_stats.frozen_count,
            "memory_total": mem_stats.total_count,
            # Bandit
            "bandit_strategies": self.bandit.strategy_count,
            "bandit_trials": self.bandit.total_trials,
            "bandit_best": self.bandit.best_strategy(),
            # Experience
            "experiences": self._experience_recorder.count,
        }

    # ── Full Report ───────────────────────────────────────────────────────

    def full_report(self) -> str:
        """Generate a comprehensive text report of the entire system.

        Returns:
            Multi-line string with full system report.
        """
        sections: list[str] = []

        sections.append("=" * 72)
        sections.append(f"  FLUX GRAND CONDUCTOR — {self.name}")
        sections.append("=" * 72)
        sections.append("")

        # System overview
        stats = self.get_stats()
        sections.append("SYSTEM OVERVIEW")
        sections.append("-" * 72)
        sections.append(f"  Name:            {stats['name']}")
        sections.append(f"  Uptime:          {stats['uptime_s']:.1f}s")
        sections.append(f"  Total Runs:      {stats['total_runs']}")
        sections.append(f"  Modules:         {stats['modules']}")
        sections.append(f"  Tiles:           {stats['tiles']}")
        sections.append(f"  Generation:      {stats['generation']}")
        sections.append(f"  Fitness:         {stats['fitness']:.4f}")
        sections.append(f"  Agents:          {stats['agents']}")
        sections.append(f"  Evolution Runs:  {stats['evolution_runs']}")
        sections.append(f"  Flywheel Revs:   {stats['flywheel_rounds']}")
        sections.append(f"  Oracle Decisions:{stats['oracle_decisions']}")
        sections.append(f"  Experiences:     {stats['experiences']}")
        sections.append(f"  Memory Items:    {stats['memory_total']}")
        sections.append("")

        # Assessment
        assessment = self.assess()
        sections.append("ASSESSMENT")
        sections.append("-" * 72)
        sections.append(f"  Fitness:           {assessment.fitness:.4f}")
        sections.append(f"  Modularity:        {assessment.modularity:.4f}")
        sections.append(f"  Cumulative Speedup:{assessment.cumulative_speedup:.2f}x")
        sections.append(f"  Modules:           {assessment.total_modules}")
        sections.append(f"  Active Tiles:      {assessment.total_tiles_active}")
        sections.append(f"  Bottlenecks:       {len(assessment.bottlenecks)}")
        sections.append(f"  Recommendations:   {len(assessment.recommendations)}")
        sections.append(f"  Agent Count:       {assessment.agent_count}")
        sections.append("")

        if assessment.bottlenecks:
            sections.append("  Top Bottlenecks:")
            for b in assessment.bottlenecks[:5]:
                sections.append(f"    - {b}")
            sections.append("")

        if assessment.heatmap:
            sections.append("  Heat Map:")
            for path, heat in sorted(assessment.heatmap.items()):
                sections.append(f"    {path:<40} {heat}")
            sections.append("")

        # Module tree
        sections.append("MODULE TREE")
        sections.append("-" * 72)
        sections.append(self.synthesizer.get_module_tree())
        sections.append("")

        # Swarm
        if self.swarm.agents:
            sections.append("SWARM AGENTS")
            sections.append("-" * 72)
            for aid, agent in self.swarm.agents.items():
                sections.append(
                    f"  {aid:<20} role={agent.role.value:<12} "
                    f"tasks={agent.total_tasks} gen={agent.generation}"
                )
            sections.append("")

        # Bandit
        sections.append("STRATEGY BANDIT")
        sections.append("-" * 72)
        sections.append(f"  Best Strategy:  {self.bandit.best_strategy()}")
        sections.append(f"  Total Trials:   {self.bandit.total_trials}")
        sections.append(f"  Exploration:    {self.bandit.exploration_rate():.2f}")
        sections.append("")

        # Footer
        sections.append("-" * 72)
        sections.append(f"  Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        sections.append("=" * 72)

        return "\n".join(sections)

    def __repr__(self) -> str:
        return (
            f"GrandConductor({self.name!r}, "
            f"modules={self.synthesizer.module_count}, "
            f"tiles={self.synthesizer.tile_count}, "
            f"agents={self.swarm.agent_count}, "
            f"gen={self.synthesizer.generation}, "
            f"fitness={self.synthesizer.current_fitness:.4f})"
        )
