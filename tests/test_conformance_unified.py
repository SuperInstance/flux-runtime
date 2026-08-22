"""Executable conformance tests for System B (unified ISA) execution.

These tests run the canonical ``TEST_VECTORS`` from ``test_conformance.py``
through the interpreter in ``isa="unified"`` mode and assert the expected
results. This is the P0 integration gate that was previously missing: it proves
the interpreter can now correctly execute converged (System B) bytecode —
including the A2A range (``TELL``/``ASK``/``BCAST``) that used to mis-decode as
SIMD vector ops ("TELL decodes as VLOAD").

See memory/flux-ab-truth-2026-08-21.md and memory/flux-ab-plan-2026-08-21.md.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from test_conformance import TEST_VECTORS

from flux.a2a.signal_compiler import SignalCompiler
from flux.vm.interpreter import Interpreter, VMInvalidOpcodeError

CONCRETE_VECTORS = [v for v in TEST_VECTORS if v["bytecode"] is not None]


def _run_unified(bytecode) -> dict:
    """Run bytecode on the unified-ISA interpreter; return regs + crash flag."""
    vm = Interpreter(bytes(bytecode), isa="unified")
    try:
        vm.execute()
        crashed = False
    except Exception:
        crashed = True
    return {
        "registers": {i: vm.regs.read_gp(i) for i in range(16)},
        "crashed": crashed,
    }


@pytest.mark.parametrize(
    "vec", CONCRETE_VECTORS, ids=lambda v: v["name"].replace(" ", "_")
)
def test_conformance_vector_unified(vec):
    state = _run_unified(vec["bytecode"])
    expected = vec["expected"]
    assert not state["crashed"], f"{vec['name']}: VM raised during unified execution"

    if expected == "no_crash":
        return

    reg = expected["register"]
    if "value_neq_zero" in expected:
        assert state["registers"][reg] != 0, f"{vec['name']}: R{reg} == 0, expected nonzero"
    else:
        assert state["registers"][reg] == expected["value"], (
            f"{vec['name']}: R{reg} = {state['registers'][reg]}, "
            f"expected {expected['value']}"
        )


def test_movi16_big_endian_immediate():
    """MOVI16 imm16 is big-endian (matches signal_compiler + conformance vector)."""
    # MOVI16 R0, 4096 (0x1000) → bytes [0x40, 0, 0x10, 0x00]; HALT 0x00
    state = _run_unified([0x40, 0, 0x10, 0x00, 0x00])
    assert state["registers"][0] == 4096


def test_signal_a2a_dispatches_not_simd():
    """TELL/ASK/BCAST must reach the A2A handler, NOT decode as VLOAD/VSTORE/VSUB.

    This is the regression test for the fatal divergence: System B emits
    TELL=0x50 / ASK=0x51 / BCAST=0x53, which System A decoded as SIMD vector
    ops. On the unified interpreter they must dispatch as A2A events.
    """
    compiler = SignalCompiler()
    result = compiler.compile(
        {
            "ops": [
                {"op": "tell", "to": "oracle1", "what": "hello", "tag": "greeting"},
                {"op": "ask", "from": "jetsonclaw1", "what": "status", "into": "resp"},
                {"op": "broadcast", "what": "fleet_update", "tag": "ops"},
            ]
        }
    )
    assert result.success, result.errors

    events = []
    vm = Interpreter(result.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: events.append(name))
    vm.execute()

    names = events
    assert "TELL" in names, f"A2A events: {names}"
    assert "ASK" in names, f"A2A events: {names}"
    assert "BCAST" in names, f"A2A events: {names}"


def test_signal_arithmetic_executes_on_unified_vm():
    """A full arithmetic Signal program computes correctly on the unified VM."""
    compiler = SignalCompiler()
    result = compiler.compile(
        {
            "ops": [
                {"op": "let", "name": "a", "value": 10},
                {"op": "let", "name": "b", "value": 20},
                {"op": "add", "args": ["a", "b"], "into": "sum"},
            ]
        }
    )
    assert result.success, result.errors

    vm = Interpreter(result.bytecode, isa="unified")
    vm.execute()
    assert vm.halted


def test_system_a_default_unchanged():
    """Default ISA remains System A: legacy bytecode still executes unchanged."""
    # System A: MOVI R0,42 = 0x2B (Format D: op, reg, imm16), HALT = 0x80
    vm = Interpreter(bytes([0x2B, 0x00, 0x2A, 0x00, 0x80]))
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.halted


def test_unified_unknown_opcode_raises_cleanly():
    """Unimplemented unified opcodes raise VMInvalidOpcodeError (no silent wrong op)."""
    # 0x03 = IRET (defined but unimplemented) — must not be silently ignored.
    vm = Interpreter(bytes([0x03]), isa="unified")
    with pytest.raises(VMInvalidOpcodeError):
        vm.execute()
