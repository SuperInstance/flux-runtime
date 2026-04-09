"""Hot code loader — BEAM-inspired dual-version module loading."""

from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModuleVersion:
    """A versioned bytecode module."""

    version_id: int
    bytecode: bytes
    function_names: list[str]
    timestamp: float
    source_hash: str
    parent_version_id: Optional[int] = None

    @classmethod
    def create(
        cls,
        version_id: int,
        bytecode: bytes,
        function_names: list[str],
        source: str = "",
        parent: Optional[ModuleVersion] = None,
    ) -> ModuleVersion:
        return cls(
            version_id=version_id,
            bytecode=bytecode,
            function_names=list(function_names),
            timestamp=time.time(),
            source_hash=hashlib.sha256(source.encode() if source else b"").hexdigest()[:16],
            parent_version_id=parent.version_id if parent else None,
        )


class HotLoader:
    """BEAM-inspired dual-version hot code loader.

    New versions coexist with old ones until all active calls finish.
    """

    def __init__(self) -> None:
        self._modules: dict[str, list[ModuleVersion]] = {}
        self._active_calls: dict[int, int] = {}
        self._next_version_id = 0

    def load(
        self,
        name: str,
        bytecode: bytes,
        function_names: list[str],
        source: str = "",
    ) -> ModuleVersion:
        """Load a new version. Old version stays for existing calls."""
        if name in self._modules and self._modules[name]:
            parent = self._modules[name][-1]
        else:
            parent = None

        version_id = self._next_version_id
        self._next_version_id += 1
        ver = ModuleVersion.create(version_id, bytecode, function_names, source, parent)

        if name not in self._modules:
            self._modules[name] = []
        self._modules[name].append(ver)

        # Track active calls on previous version
        if parent is not None:
            self._active_calls[parent.version_id] = self._active_calls.get(
                parent.version_id, 0
            )

        return ver

    def get_active(self, name: str) -> ModuleVersion | None:
        """Get the latest version of a module."""
        versions = self._modules.get(name)
        return versions[-1] if versions else None

    def enter_call(self, name: str) -> ModuleVersion:
        """Enter a call — returns the version to use (latest active)."""
        ver = self.get_active(name)
        if ver:
            self._active_calls[ver.version_id] = self._active_calls.get(ver.version_id, 0) + 1
        return ver

    def exit_call(self, version_id: int) -> None:
        """Exit a call, decrement counter. GC old versions."""
        if version_id in self._active_calls:
            self._active_calls[version_id] -= 1

    def rollback(self, name: str) -> ModuleVersion | None:
        """Roll back to the previous version."""
        versions = self._modules.get(name, [])
        if len(versions) < 2:
            return None
        current = versions[-1]
        previous = versions[-2]
        del versions[-1]
        self._active_calls.pop(current.version_id, None)
        return previous

    def get_version_history(self, name: str) -> list[ModuleVersion]:
        return list(self._modules.get(name, []))

    def gc(self, name: str) -> int:
        """Remove old versions with zero active calls. Returns count removed."""
        versions = self._modules.get(name, [])
        if not versions:
            return 0
        # Always keep the latest
        removed = 0
        to_keep = [versions[-1]]
        for ver in versions[:-1]:
            active = self._active_calls.get(ver.version_id, 0)
            if active > 0:
                to_keep.append(ver)
            else:
                removed += 1
                self._active_calls.pop(ver.version_id, None)
        self._modules[name] = to_keep
        return removed
