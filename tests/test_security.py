"""Security module tests."""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.security.capabilities import CapabilityToken, CapabilityRegistry, Permission
from flux.security.resource_limits import ResourceLimits, ResourceMonitor
from flux.security.sandbox import Sandbox, SandboxManager


def test_capability_creation_and_validation():
    t = CapabilityToken.create("agent-1", "memory.heap", Permission.READ | Permission.WRITE)
    assert t.agent_id == "agent-1"
    assert t.resource == "memory.heap"
    assert t.is_valid()
    assert t.has_permission(Permission.READ)
    assert not t.has_permission(Permission.NETWORK)
    print("  PASS test_capability_creation_and_validation")


def test_capability_expiry():
    t = CapabilityToken.create("agent-1", "mem", Permission.READ, ttl_seconds=0.01)
    time.sleep(0.02)
    assert not t.is_valid()
    print("  PASS test_capability_expiry")


def test_capability_derivation():
    parent = CapabilityToken.create("agent-1", "fs", Permission.READ | Permission.WRITE)
    child = parent.derive(Permission.READ, "data")
    assert child.resource == "fs.data"
    assert child.has_permission(Permission.READ)
    assert not child.has_permission(Permission.WRITE)
    print("  PASS test_capability_derivation")


def test_registry_grant_revoke():
    reg = CapabilityRegistry()
    t = reg.grant("agent-1", "io", Permission.READ)
    assert reg.check(t)
    reg.revoke(t)
    assert not reg.check(t)
    print("  PASS test_registry_grant_revoke")


def test_resource_monitor():
    limits = ResourceLimits(max_cycles=100)
    mon = ResourceMonitor(limits)
    assert mon.check("max_cycles", 50)
    assert mon.consume("max_cycles", 50)
    assert not mon.consume("max_cycles", 51)
    mon.release("max_cycles", 50)
    assert mon.check("max_cycles", 51)
    print("  PASS test_resource_monitor")


def test_sandbox_lifecycle():
    mgr = SandboxManager()
    sb = mgr.create_sandbox("a1")
    assert mgr.get_sandbox("a1") is sb
    assert "a1" in mgr.list_sandboxes()
    assert mgr.destroy_sandbox("a1")
    assert "a1" not in mgr.list_sandboxes()
    print("  PASS test_sandbox_lifecycle")


if __name__ == "__main__":
    test_capability_creation_and_validation()
    test_capability_expiry()
    test_capability_derivation()
    test_registry_grant_revoke()
    test_resource_monitor()
    test_sandbox_lifecycle()
    print("All security tests passed!")
