"""Signal compiler → VM interpreter round-trip integration tests.

This test suite validates that bytecode produced by signal_compiler.py
executes *correctly* inside interpreter.py. It catches byte-value divergence
between isa_unified.py (used by the compiler) and opcodes.py (used by the
interpreter) — the exact failure mode documented in docs/OPCODE-RECONCILIATION.md.

Background (see also docs/OPCODE-RECONCILIATION.md):
  signal_compiler.py emits bytes per isa_unified.py (System B).
  interpreter.py currently decodes bytes per opcodes.py (System A).

  Key divergences that these tests document:
    HALT  = 0x00 (isa_unified)  vs  0x80 (opcodes.py)
    TELL  = 0x50 (isa_unified)  vs  0x60 (opcodes.py)
    ASK   = 0x51 (isa_unified)  vs  0x61 (opcodes.py)
    BCAST = 0x53 (isa_unified)  vs  0x66 (opcodes.py)
    C_ADD = 0x60 (isa_unified)  vs  TELL (0x60 in opcodes.py)

These tests are the specification of correct end-to-end behavior. The ones
marked with ``@pytest.mark.xfail`` are expected to fail until ISA convergence
(Issue #13, Phase 1) is complete and the interpreter is wired to isa_unified.py
byte assignments.

To run only this file:
    PYTHONPATH=src python -m pytest tests/test_signal_vm_integration.py -v

To run and see which xfails have been fixed:
    PYTHONPATH=src python -m pytest tests/test_signal_vm_integration.py -v --tb=short
"""

import os
import sys
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.a2a.signal_compiler import SignalCompiler
from flux.vm.interpreter import Interpreter


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compile(ops: list) -> "CompiledSignal":  # noqa: F821
    """Compile a list of Signal ops and return the CompiledSignal object."""
    program = {"program": "test", "lang": "signal", "ops": ops}
    compiler = SignalCompiler()
    return compiler.compile(program)


def _run_collect_a2a(bytecode: bytes) -> list[tuple[str, bytes]]:
    """Run bytecode in Interpreter and return all A2A events."""
    seen: list[tuple[str, bytes]] = []
    vm = Interpreter(bytecode)
    vm.on_a2a(lambda name, data: seen.append((name, data)))
    vm.execute()
    return seen


# ─────────────────────────────────────────────────────────────────────────────
# Static byte-table alignment checks
# (These fail fast with clear messages and don't require execution)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    reason="ISA convergence not yet applied (Issue #13 Phase 1). "
           "Op.TELL must move from 0x60 → 0x50 per isa_unified.py.",
    strict=True,
)
def test_tell_byte_matches_isa_unified():
    """After convergence Op.TELL == 0x50 (isa_unified allocation)."""
    from flux.bytecode.opcodes import Op
    assert Op.TELL == 0x50, (
        f"Op.TELL is {Op.TELL:#04x} but isa_unified.py allocates TELL=0x50. "
        "opcodes.py still uses System A (pre-convergence) numbering."
    )


@pytest.mark.xfail(
    reason="ISA convergence not yet applied (Issue #13 Phase 1). "
           "Op.ASK must move from 0x61 → 0x51 per isa_unified.py.",
    strict=True,
)
def test_ask_byte_matches_isa_unified():
    """After convergence Op.ASK == 0x51 (isa_unified allocation)."""
    from flux.bytecode.opcodes import Op
    assert Op.ASK == 0x51, (
        f"Op.ASK is {Op.ASK:#04x} but isa_unified.py allocates ASK=0x51."
    )


@pytest.mark.xfail(
    reason="ISA convergence not yet applied (Issue #13 Phase 1). "
           "Op.BROADCAST must move from 0x66 → 0x53 per isa_unified.py.",
    strict=True,
)
def test_broadcast_byte_matches_isa_unified():
    """After convergence Op.BROADCAST == 0x53 (isa_unified allocation)."""
    from flux.bytecode.opcodes import Op
    assert Op.BROADCAST == 0x53, (
        f"Op.BROADCAST is {Op.BROADCAST:#04x} but isa_unified.py allocates BCAST=0x53."
    )


@pytest.mark.xfail(
    reason="ISA convergence not yet applied (Issue #13 Phase 1). "
           "Op.HALT must move from 0x80 → 0x00 per isa_unified.py.",
    strict=True,
)
def test_halt_byte_matches_isa_unified():
    """After convergence Op.HALT == 0x00 (isa_unified allocation)."""
    from flux.bytecode.opcodes import Op
    assert Op.HALT == 0x00, (
        f"Op.HALT is {Op.HALT:#04x} but isa_unified.py allocates HALT=0x00. "
        "signal_compiler.py appends 0x00 as the terminal byte; the interpreter "
        "will not stop execution correctly when running compiler output."
    )


def test_a2a_opcode_table_divergence_is_documented():
    """Documents the current divergence between System A and System B.

    This test always passes — it is a living record of which bytes differ.
    Update the divergence_map when convergence is applied.
    """
    from flux.bytecode.opcodes import Op

    # Current state: System A (opcodes.py) values
    system_a = {
        "HALT":      (Op.HALT,      0x80),
        "TELL":      (Op.TELL,      0x60),
        "ASK":       (Op.ASK,       0x61),
        "BROADCAST": (Op.BROADCAST, 0x66),
    }
    # Target state: System B (isa_unified.py) values
    system_b = {
        "HALT":      0x00,
        "TELL":      0x50,
        "ASK":       0x51,
        "BROADCAST": 0x53,
    }

    diverged = {
        name: {"system_a": vals[0], "system_b_actual": vals[1], "isa_unified_target": system_b[name]}
        for name, vals in system_a.items()
        if vals[0] != system_b[name]
    }

    # Always pass — just print the state.
    assert True, f"Divergence table: {diverged}"


# ─────────────────────────────────────────────────────────────────────────────
# Compiler output structure (should pass today)
# ─────────────────────────────────────────────────────────────────────────────

def test_compiler_emits_tell_at_0x50():
    """signal_compiler.py always emits TELL at 0x50 regardless of opcodes.py."""
    result = _compile([
        {"op": "tell", "to": "agent1", "what": "payload"},
    ])
    assert result.success, f"Compile failed: {result.errors}"
    assert 0x50 in result.bytecode, (
        "Signal compiler must emit TELL=0x50 (isa_unified byte). "
        f"Bytecode: {result.bytecode.hex()}"
    )


def test_compiler_emits_halt_at_0x00():
    """signal_compiler.py terminates programs with HALT=0x00 (isa_unified byte)."""
    result = _compile([{"op": "let", "name": "x", "value": 1}])
    assert result.success, f"Compile failed: {result.errors}"
    assert result.bytecode[-1] == 0x00, (
        f"Compiler should append 0x00 (HALT in isa_unified) as the terminal byte. "
        f"Got {result.bytecode[-1]:#04x}. Bytecode: {result.bytecode.hex()}"
    )


def test_compiler_emits_add_at_0x20():
    """signal_compiler.py emits ADD=0x20 — in the safe zone (same in both systems)."""
    result = _compile([
        {"op": "let",  "name": "a", "value": 40},
        {"op": "let",  "name": "b", "value": 2},
        {"op": "add",  "args": ["a", "b"], "into": "c"},
    ])
    assert result.success, f"Compile failed: {result.errors}"
    assert 0x20 in result.bytecode, (
        "Signal compiler must emit ADD=0x20. "
        f"Bytecode: {result.bytecode.hex()}"
    )


def test_compiler_register_map_populated():
    """Compiler tracks named register allocations."""
    result = _compile([
        {"op": "let", "name": "my_var", "value": 42},
    ])
    assert result.success, f"Compile failed: {result.errors}"
    assert "my_var" in result.register_map, (
        f"Register map should contain 'my_var'. Got: {result.register_map}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip execution tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.xfail(
    reason="Signal compiler emits TELL=0x50 but interpreter decodes 0x50 as "
           "VLOAD (System A). Execution crashes or produces wrong result. "
           "Fixes when opcodes.py migrated to isa_unified.py bytes (Issue #13).",
    strict=False,  # Crash = xfail OK; wrong-but-no-crash also acceptable
)
def test_tell_roundtrip_fires_a2a_callback():
    """TELL compiled via signal compiler must fire 'TELL' A2A callback in VM.

    Currently fails because 0x50 is VLOAD in opcodes.py but TELL in isa_unified.py.
    After ISA convergence this test must pass without xfail.
    """
    result = _compile([
        {"op": "tell", "to": "fleet", "what": "status"},
    ])
    assert result.success, f"Compile failed: {result.errors}"

    seen = _run_collect_a2a(result.bytecode)

    assert len(seen) >= 1, "No A2A events fired — TELL was not dispatched"
    assert seen[0][0] == "TELL", (
        f"Expected 'TELL' A2A event, got '{seen[0][0]}'. "
        "The interpreter decoded 0x50 as the wrong opcode."
    )


@pytest.mark.xfail(
    reason="Signal compiler emits ASK=0x51 but interpreter decodes 0x51 as "
           "VSTORE (System A). Fixes when opcodes.py migrated (Issue #13).",
    strict=False,
)
def test_ask_roundtrip_fires_a2a_callback():
    """ASK compiled via signal compiler must fire 'ASK' A2A callback in VM."""
    result = _compile([
        {"op": "ask", "from": "agent1", "what": "status", "into": "resp"},
    ])
    assert result.success, f"Compile failed: {result.errors}"

    seen = _run_collect_a2a(result.bytecode)
    assert any(name == "ASK" for name, _ in seen), (
        f"Expected 'ASK' A2A event. Got: {[name for name, _ in seen]}"
    )


@pytest.mark.xfail(
    reason="ADD=0x20 in isa_unified but PUSH=0x20 in opcodes.py. "
           "MOVI=0x18 in isa_unified but ICMP=0x18 in opcodes.py. "
           "Even basic arithmetic is misinterpreted. Fixes when opcodes.py "
           "is migrated to isa_unified.py bytes (Issue #13).",
    strict=False,
)
def test_arithmetic_add_roundtrip_executes_cleanly():
    """ADD (0x20) compiled by signal compiler must execute as ADD in the VM.

    NOTE: 0x20 = ADD in isa_unified.py but 0x20 = PUSH in opcodes.py.
    The divergence is not limited to A2A opcodes — it affects all ranges.
    Expected to fail until ISA convergence (Issue #13) is complete.
    """
    result = _compile([
        {"op": "let",  "name": "a", "value": 40},
        {"op": "let",  "name": "b", "value": 2},
        {"op": "add",  "args": ["a", "b"], "into": "c"},
    ])
    assert result.success, f"Compile failed: {result.errors}"

    vm = Interpreter(result.bytecode)
    try:
        vm.execute()
    except Exception as exc:
        pytest.fail(
            f"ADD round-trip raised {type(exc).__name__}: {exc}\n"
            f"Bytecode (hex): {result.bytecode.hex()}\n"
            "This confirms the ISA divergence extends to arithmetic range — "
            "not just A2A opcodes."
        )

    # After clean execution, verify register "c" holds 42.
    c_reg = result.register_map.get("c")
    assert c_reg is not None, "Compiler did not allocate register for 'c'"
    assert vm.regs.read_gp(c_reg) == 42, (
        f"Expected reg[{c_reg}] == 42, got {vm.regs.read_gp(c_reg)}"
    )
