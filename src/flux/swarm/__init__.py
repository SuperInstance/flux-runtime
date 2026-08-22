"""FLUX Swarm — multi-agent collaboration layer on top of A2A primitives.

This package provides:
- ``agent``       — FluxAgent, AgentRole, TrustProfile, AgentTask/Result
- ``topology``    — SwarmTopology, Topology (5 canonical layouts + BFS routing)
- ``swarm``       — Swarm orchestrator (spawn, broadcast, barrier, evolve)
- ``deadlock``    — DeadlockDetector (wait-for graph + livelock detection)
- ``message_bus`` — MessageBus (direct, pub/sub, topic-based routing)
"""

from .agent import (
    AgentResult,
    AgentRole,
    AgentTask,
    FluxAgent,
    TrustProfile,
)
from .deadlock import (
    DeadlockDetector,
    DeadlockReport,
    DeadlockResolution,
    DeadlockSeverity,
)
from .message_bus import (
    AgentMessage,
    MessageBus,
)
from .swarm import (
    Swarm,
    SwarmEvolutionReport,
    SwarmReport,
    TopologyChange,
)
from .topology import (
    SwarmTopology,
    Topology,
)

__all__ = [
    # Agent
    "FluxAgent",
    "AgentRole",
    "AgentTask",
    "AgentResult",
    "TrustProfile",
    # Topology
    "SwarmTopology",
    "Topology",
    # Swarm
    "Swarm",
    "SwarmReport",
    "SwarmEvolutionReport",
    "TopologyChange",
    # Deadlock
    "DeadlockDetector",
    "DeadlockReport",
    "DeadlockResolution",
    "DeadlockSeverity",
    # Message Bus
    "AgentMessage",
    "MessageBus",
]
