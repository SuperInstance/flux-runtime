"""FLUX Agent Runtime — orchestrates agents, compilation, and execution.

This package provides:
- ``Agent``              — Runtime agent that owns a VM interpreter
- ``AgentConfig``        — Configuration dataclass for agent creation
- ``AgentRuntime``       — Orchestrates multiple agents: compile, deploy, execute, communicate
"""

from flux.runtime.agent import Agent, AgentConfig
from flux.runtime.agent_runtime import AgentRuntime

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentRuntime",
]
