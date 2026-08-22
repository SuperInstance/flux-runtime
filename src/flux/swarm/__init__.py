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
    # Message Bus
    "AgentMessage",
    "AgentResult",
    "AgentRole",
    "AgentTask",
    # Deadlock
    "DeadlockDetector",
    "DeadlockReport",
    "DeadlockResolution",
    "DeadlockSeverity",
    # Agent
    "FluxAgent",
    "MessageBus",
    # Swarm
    "Swarm",
    "SwarmEvolutionReport",
    "SwarmReport",
    # Topology
    "SwarmTopology",
    "Topology",
    "TopologyChange",
    "TrustProfile",
]
