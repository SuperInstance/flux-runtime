"""Sandboxed execution environment for FLUX agents."""

from __future__ import annotations
from .capabilities import CapabilityRegistry, Permission
from .resource_limits import ResourceLimits, ResourceMonitor


class Sandbox:
    """Isolated execution sandbox with capability-based security."""

    def __init__(
        self,
        agent_id: str,
        limits: ResourceLimits | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.capabilities = CapabilityRegistry()
        self.resources = ResourceMonitor(limits or ResourceLimits())
        self.trust_level: float = 0.5

    def grant_capability(
        self, resource: str, permissions: int, ttl: float = 3600.0
    ):
        from .capabilities import CapabilityToken
        return self.capabilities.grant(self.agent_id, resource, permissions, ttl)

    def check_permission(self, resource: str, permission: int) -> bool:
        tokens = self.capabilities.list_for_agent(self.agent_id)
        for t in tokens:
            if t.resource == resource and t.has_permission(permission):
                return True
        return False

    def check_resource(self, resource_name: str, amount: int = 1) -> bool:
        return self.resources.check(resource_name, amount)


class SandboxManager:
    """Manages multiple agent sandboxes."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, Sandbox] = {}

    def create_sandbox(self, agent_id: str, limits: ResourceLimits | None = None) -> Sandbox:
        sb = Sandbox(agent_id, limits)
        self._sandboxes[agent_id] = sb
        return sb

    def get_sandbox(self, agent_id: str) -> Sandbox | None:
        return self._sandboxes.get(agent_id)

    def destroy_sandbox(self, agent_id: str) -> bool:
        if agent_id in self._sandboxes:
            del self._sandboxes[agent_id]
            return True
        return False

    def list_sandboxes(self) -> list[str]:
        return list(self._sandboxes.keys())
