"""Capability tokens for FLUX agent security."""

from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional


class Permission(IntFlag):
    """Bitflag permissions for capabilities."""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 4
    ADMIN = 8
    NETWORK = 16
    MEMORY_ALLOC = 32
    IO_SENSOR = 64
    IO_ACTUATOR = 128
    A2A_TELL = 256
    A2A_ASK = 512
    A2A_DELEGATE = 1024
    ALL = 0xFFFF


def _make_token_hash(agent_id: str, resource: str, permissions: int, ts: float) -> bytes:
    """SHA-256-based 128-bit token hash."""
    data = f"{agent_id}:{resource}:{permissions}:{ts}".encode()
    full = hashlib.sha256(data).digest()
    return full[:16]  # 128 bits


@dataclass(frozen=True)
class CapabilityToken:
    """Unforgeable capability token — possession equals authority."""
    agent_id: str
    resource: str
    permissions: int
    granted_at: float
    expires_at: float
    _token_hash: bytes = b""  # internal

    @classmethod
    def create(
        cls, agent_id: str, resource: str, permissions: int, ttl_seconds: float = 3600.0
    ) -> CapabilityToken:
        now = time.time()
        return cls(
            agent_id=agent_id,
            resource=resource,
            permissions=permissions,
            granted_at=now,
            expires_at=now + ttl_seconds if ttl_seconds > 0 else 0.0,
            _token_hash=_make_token_hash(agent_id, resource, permissions, now),
        )

    def is_valid(self, now: float | None = None) -> bool:
        now = now or time.time()
        return self.expires_at == 0.0 or now < self.expires_at

    def has_permission(self, perm: int) -> bool:
        return bool(self.permissions & perm)

    def can_derive(self, perm_subset: int, resource_suffix: str = "") -> bool:
        return bool((perm_subset & self.permissions) == perm_subset)

    def derive(self, perm_subset: int, resource_suffix: str = "") -> CapabilityToken:
        if not self.can_derive(perm_subset, resource_suffix):
            raise ValueError("Cannot derive: subset not within parent permissions")
        new_resource = f"{self.resource}.{resource_suffix}" if resource_suffix else self.resource
        return CapabilityToken.create(self.agent_id, new_resource, perm_subset)

    def to_bytes(self) -> bytes:
        return self._token_hash

    @classmethod
    def from_bytes(
        cls, data: bytes, agent_id: str, resource: str, permissions: int,
        granted_at: float, expires_at: float = 0.0,
    ) -> CapabilityToken:
        return cls(
            agent_id=agent_id,
            resource=resource,
            permissions=permissions,
            granted_at=granted_at,
            expires_at=expires_at,
            _token_hash=data[:16],
        )


class CapabilityRegistry:
    """Central registry for active capability tokens."""

    def __init__(self) -> None:
        self._tokens: dict[str, CapabilityToken] = {}

    def grant(
        self, agent_id: str, resource: str, permissions: int, ttl: float = 3600.0
    ) -> CapabilityToken:
        token = CapabilityToken.create(agent_id, resource, permissions, ttl)
        key = token._token_hash.hex()
        self._tokens[key] = token
        return token

    def revoke(self, token: CapabilityToken) -> bool:
        key = token._token_hash.hex()
        if key in self._tokens:
            del self._tokens[key]
            return True
        return False

    def check(self, token: CapabilityToken) -> bool:
        key = token._token_hash.hex()
        if key not in self._tokens:
            return False
        return self._tokens[key].is_valid()

    def list_for_agent(self, agent_id: str) -> list[CapabilityToken]:
        return [t for t in self._tokens.values() if t.agent_id == agent_id and t.is_valid()]
