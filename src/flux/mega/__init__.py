"""FLUX Mega — the Grand Conductor that wires EVERYTHING together.

The GrandConductor is the single entry point for the entire FLUX system.
It orchestrates all subsystems:

- **Synthesis**: Module management, profiling, language selection, tile composition
- **Evolution**: Self-improvement loop, pattern mining, mutation, validation
- **Flywheel**: Self-reinforcing 6-phase improvement cycles
- **Simulation**: Digital twin, performance prediction, speculative execution, oracle
- **Swarm**: Multi-agent collaboration, topology, deadlock detection
- **Memory**: Four-tier persistent memory, experience recording, meta-learning
- **Creative**: Sonification, live coding, generative art, visualization
- **Pipeline**: End-to-end FLUX.MD → FIR → Bytecode → VM execution
- **Adaptive**: Runtime profiling, adaptive language selection, compiler bridge
- **Tiles**: 34+ composable computation patterns with DAG composition
- **Modules**: 8-level fractal hot-reload hierarchy
- **Cost**: FIR-level static cost estimation
- **Protocol**: Typed message envelopes, channels, registry, negotiation
- **Security**: Sandbox, capabilities, resource limits
"""

from .conductor import (
    GrandConductor,
    SystemAssessment,
    ExecutionReport,
    EvolutionSummary,
)

__all__ = [
    "GrandConductor",
    "SystemAssessment",
    "ExecutionReport",
    "EvolutionSummary",
]
