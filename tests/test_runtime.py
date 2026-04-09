"""FLUX Runtime End-to-End Tests.

6 tests exercising the full pipeline:
  Agent creation and registration
  C compilation → bytecode → verify structure
  Python compilation → bytecode → verify structure
  Agent register, load, and execute with raw bytecode
  Multi-agent basic orchestration
  FLUX.MD → parse → compile → bytecode verification
"""

import struct
import sys
import os
import traceback

# Ensure the project source root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.bytecode.opcodes import Op
from flux.compiler.pipeline import FluxCompiler
from flux.runtime.agent import Agent, AgentConfig
from flux.runtime.agent_runtime import AgentRuntime
from flux.vm.interpreter import Interpreter


passed = 0
failed = 0


def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}")
        traceback.print_exc()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_code_section(bytecode: bytes) -> bytes:
    """Extract the code section from compiled FLUX bytecode.

    Header layout (18 bytes total):
      offset 0:  magic    (4 bytes, b'FLUX')
      offset 4:  version  (uint16 LE)
      offset 6:  flags    (uint16 LE)
      offset 8:  n_funcs  (uint16 LE)
      offset 10: type_off (uint32 LE)
      offset 14: code_off (uint32 LE)
    """
    code_off = struct.unpack_from("<I", bytecode, 14)[0]
    return bytecode[code_off:]


def _read_n_funcs(bytecode: bytes) -> int:
    """Read the function count from the FLUX bytecode header (offset 8)."""
    return struct.unpack_from("<H", bytecode, 8)[0]


def _make_add_bytecode() -> bytes:
    """Build raw bytecode: MOVI R1,10; MOVI R2,20; IADD R0,R1,R2; HALT.

    R0 = R1 + R2 = 30.
    """
    return bytes([
        Op.MOVI, 0x01, 10, 0x00,     # MOVI R1, 10
        Op.MOVI, 0x02, 20, 0x00,     # MOVI R2, 20
        Op.IADD, 0x00, 0x01, 0x02,    # IADD R0, R1, R2
        Op.HALT,                       # HALT
    ])


def _make_countdown_bytecode() -> bytes:
    """Build raw bytecode: DEC R0; JNZ R0,-6; HALT (countdown loop).

    R0 is decremented to 0.
    """
    return bytes([
        Op.DEC, 0x00,                  # DEC R0
        Op.JNZ, 0x00, 0xFA, 0xFF,     # JNZ R0, -6 -> back to byte 0
        Op.HALT,                       # HALT
    ])


# ────────────────────────────────────────────────────────────────────────────
# Test 1: Agent create and register
# ────────────────────────────────────────────────────────────────────────────


def test_agent_create_and_register():
    """Agent can be created with a config and registered in the runtime."""
    config = AgentConfig(name="test-agent", trust_level=0.8)
    agent = Agent(config)

    # Verify agent properties
    assert agent.id is not None and len(agent.id) == 8
    assert agent.config.name == "test-agent"
    assert agent.config.trust_level == 0.8
    assert agent.bytecode is None
    assert agent.interpreter is None
    assert agent.last_result is None
    assert not agent.is_halted()

    # Register in runtime
    rt = AgentRuntime()
    agent_id = rt.register_agent(config)

    assert agent_id in rt.list_agents()
    retrieved = rt.get_agent(agent_id)
    assert retrieved.config.name == "test-agent"
    assert retrieved.config.trust_level == 0.8


# ────────────────────────────────────────────────────────────────────────────
# Test 2: Compile C and verify bytecode structure
# ────────────────────────────────────────────────────────────────────────────


def test_compile_and_execute_c():
    """Compile C source through the full pipeline and verify bytecode output."""
    source = """
    int add(int a, int b) {
        return a + b;
    }
    """
    compiler = FluxCompiler()
    bytecode = compiler.compile_c(source.strip())

    # Verify bytecode structure
    assert isinstance(bytecode, bytes), "Bytecode should be bytes"
    assert len(bytecode) >= 16, f"Bytecode should be >= 16 bytes, got {len(bytecode)}"
    assert bytecode[:4] == b"FLUX", "Bytecode must start with FLUX magic"

    # Verify header fields (n_funcs at offset 8, uint16 LE)
    n_funcs = _read_n_funcs(bytecode)
    assert n_funcs >= 1, f"Expected >= 1 function, got {n_funcs}"

    # Extract and verify code section contains expected opcodes
    code_section = _extract_code_section(bytecode)
    assert len(code_section) > 0, "Code section should not be empty"

    # The code section should contain IADD (0x08) for the add operation
    assert Op.IADD in code_section, (
        f"Code section should contain IADD opcode (0x08). "
        f"Got bytes: {code_section.hex()}"
    )

    # Verify it can be loaded into an agent
    agent = Agent(AgentConfig(name="c-worker"))
    agent.load_bytecode(bytecode)
    assert agent.bytecode is not None
    assert agent.interpreter is not None
    assert agent.interpreter.bytecode == bytecode


# ────────────────────────────────────────────────────────────────────────────
# Test 3: Compile Python and verify bytecode structure
# ────────────────────────────────────────────────────────────────────────────


def test_compile_and_execute_python():
    """Compile Python source through the full pipeline and verify bytecode output."""
    source = """
def add(a, b):
    return a + b
"""
    compiler = FluxCompiler()
    bytecode = compiler.compile_python(source.strip())

    # Verify bytecode structure
    assert isinstance(bytecode, bytes)
    assert len(bytecode) >= 16
    assert bytecode[:4] == b"FLUX"

    # Verify header (n_funcs at offset 8, uint16 LE)
    n_funcs = _read_n_funcs(bytecode)
    assert n_funcs >= 1

    # Code section should contain IADD
    code_section = _extract_code_section(bytecode)
    assert len(code_section) > 0
    assert Op.IADD in code_section, (
        f"Code section should contain IADD. Got: {code_section.hex()}"
    )

    # Load into agent
    agent = Agent(AgentConfig(name="py-worker"))
    agent.load_bytecode(bytecode)
    assert agent.bytecode is not None


# ────────────────────────────────────────────────────────────────────────────
# Test 4: Agent register, load bytecode, and execute
# ────────────────────────────────────────────────────────────────────────────


def test_agent_register_and_execute():
    """Register an agent, load raw bytecode, execute, and verify result."""
    rt = AgentRuntime()
    agent_id = rt.register_agent(AgentConfig(name="calculator"))

    # Build bytecode: MOVI R1,10; MOVI R2,20; IADD R0,R1,R2; HALT
    bytecode = _make_add_bytecode()

    # Load into agent
    agent = rt.get_agent(agent_id)
    agent.load_bytecode(bytecode)

    # Execute
    cycles = agent.execute()

    # Verify
    assert agent.is_halted(), "Agent should be halted after execution"
    assert cycles >= 1, f"Expected >= 1 cycle, got {cycles}"
    assert agent.get_register(0) == 30, (
        f"R0 should be 30 (10+20), got {agent.get_register(0)}"
    )
    assert agent.last_result == cycles

    # Verify AgentRuntime.execute_agent works too
    agent2_id = rt.register_agent(AgentConfig(name="calc2"))
    agent2 = rt.get_agent(agent2_id)
    agent2.load_bytecode(bytecode)
    cycles2 = rt.execute_agent(agent2_id)
    assert agent2.get_register(0) == 30


# ────────────────────────────────────────────────────────────────────────────
# Test 5: Multi-agent basic
# ────────────────────────────────────────────────────────────────────────────


def test_multi_agent_basic():
    """Create two agents, execute both, verify independent execution."""
    rt = AgentRuntime()

    # Agent 1: addition (R0 = 10 + 20 = 30)
    id1 = rt.register_agent(AgentConfig(name="adder"))
    rt.get_agent(id1).load_bytecode(_make_add_bytecode())

    # Agent 2: countdown (R0 starts at 5, decrements to 0)
    id2 = rt.register_agent(AgentConfig(name="counter"))
    counter = rt.get_agent(id2)
    counter.load_bytecode(_make_countdown_bytecode())
    counter.set_register(0, 5)  # start countdown from 5

    # Execute both
    cycles1 = rt.execute_agent(id1)
    cycles2 = rt.execute_agent(id2)

    # Verify agent 1
    assert rt.get_agent(id1).is_halted()
    assert rt.get_agent(id1).get_register(0) == 30, (
        f"Agent1 R0 should be 30, got {rt.get_agent(id1).get_register(0)}"
    )

    # Verify agent 2
    assert rt.get_agent(id2).is_halted()
    assert rt.get_agent(id2).get_register(0) == 0, (
        f"Agent2 R0 should be 0, got {rt.get_agent(id2).get_register(0)}"
    )

    # Verify they are independent
    assert rt.get_agent(id1).get_register(0) == 30  # unchanged
    assert id1 != id2
    assert len(rt.list_agents()) == 2

    # Test inter-agent messaging
    msg_delivered = rt.send_message(id1, id2, payload=b"hello")
    assert msg_delivered, "Message should be delivered (default trust=0.5 >= 0.3)"


# ────────────────────────────────────────────────────────────────────────────
# Test 6: End-to-end FLUX.MD → bytecode
# ────────────────────────────────────────────────────────────────────────────


def test_end_to_end_md_to_vm():
    """Parse FLUX.MD, compile to bytecode, verify the full pipeline."""
    md_source = """---
title: Test Module
---

# FLUX Test Module

This is a test module with embedded C code.

## Code

```c
int square(int x) {
    return x * x;
}
```

## Notes

Some markdown content here.
"""

    compiler = FluxCompiler()

    # Compile from markdown — extracts the C block and compiles it
    bytecode = compiler.compile_md(md_source)

    # Verify full pipeline output
    assert isinstance(bytecode, bytes)
    assert len(bytecode) >= 16
    assert bytecode[:4] == b"FLUX"

    # Verify function count from header (n_funcs at offset 8)
    n_funcs = _read_n_funcs(bytecode)
    assert n_funcs >= 1, f"Expected >= 1 function, got {n_funcs}"

    # Verify code section has IMUL (for the square operation x*x)
    code_section = _extract_code_section(bytecode)
    assert len(code_section) > 0
    assert Op.IMUL in code_section, (
        f"Code section should contain IMUL for x*x. Got: {code_section.hex()}"
    )

    # Also verify through the AgentRuntime pipeline
    rt = AgentRuntime()
    agent_id = rt.register_agent(AgentConfig(name="md-agent"))

    # compile_and_load returns bytecode and loads it into the agent
    returned_bc = rt.compile_and_load(agent_id, md_source, lang="md")
    assert returned_bc == bytecode
    assert rt.get_agent(agent_id).bytecode is not None
    assert rt.get_agent(agent_id).interpreter is not None

    # Verify the compiler property works
    assert rt.compiler is not None
    assert isinstance(rt.compiler, FluxCompiler)


# ────────────────────────────────────────────────────────────────────────────
# Run all tests
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Runtime End-to-End Test Suite")
    print("=" * 60)

    run_test("test_agent_create_and_register", test_agent_create_and_register)
    run_test("test_compile_and_execute_c", test_compile_and_execute_c)
    run_test("test_compile_and_execute_python", test_compile_and_execute_python)
    run_test("test_agent_register_and_execute", test_agent_register_and_execute)
    run_test("test_multi_agent_basic", test_multi_agent_basic)
    run_test("test_end_to_end_md_to_vm", test_end_to_end_md_to_vm)

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("All runtime tests passed!")
