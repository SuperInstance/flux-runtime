"""Resource limits and monitoring for FLUX sandboxes."""

from __future__ import annotations
from dataclasses import dataclass, fields


@dataclass
class ResourceLimits:
    """Per-agent resource consumption limits."""
    max_memory_bytes: int = 67_108_864       # 64 MB
    max_cycles: int = 10_000_000              # 10M cycles
    max_network_bandwidth: int = 1_048_576   # 1 MB/s
    max_io_rate: int = 1000                   # ops/s
    max_a2a_connections: int = 16
    max_regions: int = 256
    max_stack_size: int = 4096
    max_function_count: int = 1024


@dataclass
class ResourceMonitor:
    """Tracks resource usage and enforces limits."""

    def __init__(self, limits: ResourceLimits) -> None:
        self._limits = limits
        self._usage: dict[str, int] = {
            f.name: 0 for f in fields(limits)
        }

    def check(self, resource_name: str, amount: int = 1) -> bool:
        """Return True if the requested amount fits within the limit."""
        limit_val = getattr(self._limits, resource_name, 0)
        return self._usage.get(resource_name, 0) + amount <= limit_val

    def consume(self, resource_name: str, amount: int = 1) -> bool:
        """Consume resources. Returns False if limit would be exceeded."""
        if not self.check(resource_name, amount):
            return False
        self._usage[resource_name] = self._usage.get(resource_name, 0) + amount
        return True

    def release(self, resource_name: str, amount: int = 1) -> None:
        self._usage[resource_name] = max(0, self._usage.get(resource_name, 0) - amount)

    def get_usage(self) -> dict[str, int]:
        return dict(self._usage)

    def get_remaining(self) -> dict[str, int]:
        return {
            f.name: getattr(self._limits, f.name, 0) - self._usage.get(f.name, 0)
            for f in fields(self._limits)
        }
