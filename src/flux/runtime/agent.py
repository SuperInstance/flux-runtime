"""Agent — runtime agent that owns a VM interpreter and can execute bytecode.

Each Agent wraps a :class:`flux.vm.interpreter.Interpreter` instance and
provides a high-level API for loading bytecode, executing it, and inspecting
register state afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import uuid

from flux.vm.interpreter import Interpreter


@dataclass
class AgentConfig:
    """Configuration for creating a new :class:`Agent`.

    Attributes
    ----------
    name : str
        Human-readable agent name.
    trust_level : float
        Initial trust score for this agent (0.0–1.0).
    max_cycles : int
        VM execution cycle budget (default 10 M).
    memory_size : int
        Bytes allocated for each of the stack and heap regions.
    capabilities : list[str]
        Capability tokens this agent possesses.
    """

    name: str
    trust_level: float = 0.5
    max_cycles: int = 10_000_000
    memory_size: int = 65536
    capabilities: list[str] = field(default_factory=list)


class Agent:
    """Runtime agent that owns a VM interpreter and can execute bytecode.

    Usage::

        agent = Agent(AgentConfig(name="worker"))
        agent.load_bytecode(bytecode)
        cycles = agent.execute()
        result = agent.get_register(0)
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.id: str = str(uuid.uuid4())[:8]
        self.bytecode: Optional[bytes] = None
        self.interpreter: Optional[Interpreter] = None
        self.last_result: Optional[int] = None  # cycle count

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def load_bytecode(self, bytecode: bytes) -> None:
        """Load bytecode into the agent's VM.

        Parameters
        ----------
        bytecode :
            Raw FLUX bytecode bytes (with or without the FLUX header).
        """
        self.bytecode = bytecode
        self.interpreter = Interpreter(
            bytecode,
            memory_size=self.config.memory_size,
            max_cycles=self.config.max_cycles,
        )

    def execute(self) -> int:
        """Execute the loaded bytecode. Returns the cycle count.

        Raises
        ------
        RuntimeError
            If no bytecode has been loaded.
        """
        if self.interpreter is None:
            raise RuntimeError("No bytecode loaded — call load_bytecode() first")
        self.last_result = self.interpreter.execute()
        return self.last_result

    # ── Register access ────────────────────────────────────────────────────

    def get_register(self, reg: int) -> int:
        """Read a general-purpose register after execution.

        Parameters
        ----------
        reg : int
            Register index (0–15 for R0–R15).

        Raises
        ------
        RuntimeError
            If no bytecode has been loaded.
        """
        if self.interpreter is None:
            raise RuntimeError("No bytecode loaded — call load_bytecode() first")
        return self.interpreter.regs.read_gp(reg)

    def set_register(self, reg: int, value: int) -> None:
        """Set a register value before execution.

        Parameters
        ----------
        reg : int
            Register index (0–15 for R0–R15).
        value : int
            Value to write.
        """
        if self.interpreter is None:
            raise RuntimeError("No bytecode loaded — call load_bytecode() first")
        self.interpreter.regs.write_gp(reg, value)

    # ── State queries ──────────────────────────────────────────────────────

    def is_halted(self) -> bool:
        """Return ``True`` if the VM has halted (executed a HALT instruction)."""
        return self.interpreter.halted if self.interpreter else False

    def is_running(self) -> bool:
        """Return ``True`` if the VM is currently in the running state."""
        return self.interpreter.running if self.interpreter else False

    def __repr__(self) -> str:
        return (
            f"Agent(id={self.id!r}, name={self.config.name!r}, "
            f"halted={self.is_halted()})"
        )
