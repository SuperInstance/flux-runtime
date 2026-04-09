"""AgentRuntime — orchestrates multiple agents: compile, deploy, execute, communicate.

The :class:`AgentRuntime` is the top-level entry point for the FLUX system.
It manages a pool of :class:`Agent` instances, provides compilation services
via :class:`FluxCompiler`, and wires up agent-to-agent messaging through
the :class:`AgentCoordinator`.

Typical usage::

    rt = AgentRuntime()
    agent_id = rt.register_agent(AgentConfig(name="worker"))
    rt.compile_and_load(agent_id, "int main() { return 42; }", lang="c")
    cycles = rt.execute_agent(agent_id)
    result = rt.get_agent(agent_id).get_register(0)
"""

from __future__ import annotations

from typing import Optional

from flux.a2a.coordinator import AgentCoordinator
from flux.compiler.pipeline import FluxCompiler
from flux.runtime.agent import Agent, AgentConfig


class AgentRuntime:
    """Orchestrates multiple agents: compile, deploy, execute, communicate.

    Parameters
    ----------
    trust_threshold : float
        Minimum trust score for inter-agent messages (default 0.3).
    """

    def __init__(self, trust_threshold: float = 0.3) -> None:
        self._agents: dict[str, Agent] = {}
        self._coordinator = AgentCoordinator(trust_threshold=trust_threshold)
        self._compiler = FluxCompiler()

    # ── Agent management ───────────────────────────────────────────────────

    def register_agent(self, config: AgentConfig) -> str:
        """Register a new agent and return its runtime ID.

        The agent is also registered with the A2A coordinator for
        potential inter-agent messaging.

        Parameters
        ----------
        config :
            Agent configuration (name, trust level, etc.).

        Returns
        -------
        str
            The short 8-char UUID agent ID.
        """
        agent = Agent(config)
        self._agents[agent.id] = agent
        # Register with the A2A coordinator for messaging
        self._coordinator.register_agent(agent.id, interpreter=None)
        return agent.id

    def get_agent(self, agent_id: str) -> Agent:
        """Retrieve an agent by its ID.

        Raises
        ------
        KeyError
            If no agent with the given ID exists.
        """
        if agent_id not in self._agents:
            raise KeyError(f"Unknown agent: {agent_id}")
        return self._agents[agent_id]

    def list_agents(self) -> list[str]:
        """Return a list of all registered agent IDs."""
        return list(self._agents.keys())

    # ── Compilation & execution ────────────────────────────────────────────

    def compile_and_load(
        self,
        agent_id: str,
        source: str,
        lang: str = "c",
    ) -> bytes:
        """Compile source code and load the resulting bytecode into an agent.

        Parameters
        ----------
        agent_id : str
            Target agent ID.
        source : str
            Source code to compile.
        lang : str
            Source language — ``"c"``, ``"python"``, or ``"md"``.

        Returns
        -------
        bytes
            The compiled bytecode.

        Raises
        ------
        KeyError
            If the agent ID is unknown.
        ValueError
            If the language is not supported.
        """
        agent = self.get_agent(agent_id)

        if lang == "c":
            bytecode = self._compiler.compile_c(source)
        elif lang == "python":
            bytecode = self._compiler.compile_python(source)
        elif lang == "md":
            bytecode = self._compiler.compile_md(source)
        else:
            raise ValueError(
                f"Unsupported language: {lang!r}. "
                f"Supported: 'c', 'python', 'md'"
            )

        agent.load_bytecode(bytecode)
        return bytecode

    def execute_agent(self, agent_id: str) -> int:
        """Execute the bytecode loaded in the specified agent.

        Parameters
        ----------
        agent_id : str
            Target agent ID.

        Returns
        -------
        int
            Number of cycles consumed.

        Raises
        ------
        RuntimeError
            If the agent has no bytecode loaded.
        """
        return self.get_agent(agent_id).execute()

    # ── Inter-agent communication ──────────────────────────────────────────

    def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        payload: bytes,
        msg_type: int = 0x60,
    ) -> bool:
        """Send an A2A message from one agent to another.

        The message delivery is gated by the trust engine — if the trust
        score between sender and receiver is below the configured threshold,
        the message is silently dropped.

        Parameters
        ----------
        sender_id : str
            Sending agent ID.
        receiver_id : str
            Receiving agent ID.
        payload : bytes
            Message payload.
        msg_type : int
            A2A message type byte (default 0x60 = TELL).

        Returns
        -------
        bool
            ``True`` if the message was delivered, ``False`` otherwise.
        """
        return self._coordinator.send_message(
            sender=sender_id,
            receiver=receiver_id,
            msg_type=msg_type,
            payload=payload,
        )

    def get_messages(self, agent_id: str) -> list:
        """Drain the mailbox for the specified agent.

        Returns
        -------
        list[A2AMessage]
            All pending messages for the agent.
        """
        return self._coordinator.get_messages(agent_id)

    # ── Convenience ────────────────────────────────────────────────────────

    @property
    def compiler(self) -> FluxCompiler:
        """Direct access to the underlying :class:`FluxCompiler`."""
        return self._compiler

    @property
    def coordinator(self) -> AgentCoordinator:
        """Direct access to the underlying :class:`AgentCoordinator`."""
        return self._coordinator
