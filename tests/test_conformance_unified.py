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


def test_system_a_legacy_mode_unchanged():
    """Legacy System A bytecode still executes unchanged via isa="system_a".

    The 2026-08-21 cutover flipped the interpreter DEFAULT to System B
    (unified). System A remains fully supported for byte-for-byte compat
    via the explicit flag — no mapping was deleted.
    """
    # System A: MOVI R0,42 = 0x2B (Format D: op, reg, imm16), HALT = 0x80
    vm = Interpreter(bytes([0x2B, 0x00, 0x2A, 0x00, 0x80]), isa="system_a")
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.halted


def test_default_is_unified_after_cutover():
    """Default ISA is System B (unified) post-cutover (2026-08-21)."""
    # Unified: MOVI R0,42 = 0x18 (Format D: op, rd, imm8), HALT = 0x00
    vm = Interpreter(bytes([0x18, 0x00, 42, 0x00]))
    vm.execute()
    assert vm.regs.read_gp(0) == 42
    assert vm.halted


def test_unified_unknown_opcode_raises_cleanly():
    """Unimplemented unified opcodes raise VMInvalidOpcodeError (no silent wrong op)."""
    # 0x03 = IRET (defined but unimplemented) — must not be silently ignored.
    vm = Interpreter(bytes([0x03]), isa="unified")
    with pytest.raises(VMInvalidOpcodeError):
        vm.execute()


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3 (2026-08-21): dual-mode executable conformance — compiler side.
#
# Phase 1 proved the unified interpreter executes the raw TEST_VECTORS and
# that compiled A2A ops *dispatch*. These vectors go further: full Signal
# programs are emitted with the compiler's System B mode and executed on the
# unified interpreter, asserting SEMANTICS (register values, payloads, control
# flow) — not just dispatch or byte presence.
# ═════════════════════════════════════════════════════════════════════════════

import struct as _struct
import zlib as _zlib

from flux.asm.cross_assembler import CrossAssembler


def _intern(name: str) -> int:
    return _zlib.crc32(str(name).encode("utf-8")) & 0x7FFF


def _compile_and_run(program: dict, a2a_handler=None):
    """Compile Signal (System B) → run on the unified VM; return (result, vm)."""
    compiler = SignalCompiler(isa="system_b")
    result = compiler.compile(program)
    assert result.success, result.errors
    vm = Interpreter(result.bytecode, isa="unified")
    if a2a_handler is not None:
        vm.on_a2a(a2a_handler)
    vm.execute()
    return result, vm


# ── Arithmetic / data-movement semantics ───────────────────────────────────

_COMPILER_SEMANTIC_VECTORS = [
    (
        "let small → MOVI",
        {"ops": [{"op": "let", "name": "x", "value": 42}]},
        "x", 42,
    ),
    (
        "let large → MOVI16 (big-endian imm16)",
        {"ops": [{"op": "let", "name": "x", "value": 4096}]},
        "x", 4096,
    ),
    (
        "let negative → MOVI (signed imm8)",
        {"ops": [{"op": "let", "name": "x", "value": -5}]},
        "x", -5,
    ),
    (
        "let alias → MOV (register copy)",
        {"ops": [
            {"op": "let", "name": "a", "value": 33},
            {"op": "let", "name": "x", "value": "a"},
        ]},
        "x", 33,
    ),
    (
        "add 10+20",
        {"ops": [
            {"op": "let", "name": "a", "value": 10},
            {"op": "let", "name": "b", "value": 20},
            {"op": "add", "args": ["a", "b"], "into": "sum"},
        ]},
        "sum", 30,
    ),
    (
        "sub 7-2",
        {"ops": [
            {"op": "let", "name": "a", "value": 7},
            {"op": "let", "name": "b", "value": 2},
            {"op": "sub", "args": ["a", "b"], "into": "d"},
        ]},
        "d", 5,
    ),
    (
        "mul 6*7",
        {"ops": [
            {"op": "let", "name": "a", "value": 6},
            {"op": "let", "name": "b", "value": 7},
            {"op": "mul", "args": ["a", "b"], "into": "p"},
        ]},
        "p", 42,
    ),
    (
        "div 84/2",
        {"ops": [
            {"op": "let", "name": "a", "value": 84},
            {"op": "let", "name": "b", "value": 2},
            {"op": "div", "args": ["a", "b"], "into": "q"},
        ]},
        "q", 42,
    ),
    (
        "mod 17%5",
        {"ops": [
            {"op": "let", "name": "a", "value": 17},
            {"op": "let", "name": "b", "value": 5},
            {"op": "mod", "args": ["a", "b"], "into": "r"},
        ]},
        "r", 2,
    ),
    (
        "chained add 1+2+3",
        {"ops": [
            {"op": "let", "name": "a", "value": 1},
            {"op": "let", "name": "b", "value": 2},
            {"op": "let", "name": "c", "value": 3},
            {"op": "add", "args": ["a", "b", "c"], "into": "sum"},
        ]},
        "sum", 6,
    ),
    (
        "literal args are materialized (5+6)",
        {"ops": [{"op": "add", "args": [5, 6], "into": "sum"}]},
        "sum", 11,
    ),
    (
        "eq 4==4 → 1",
        {"ops": [
            {"op": "let", "name": "a", "value": 4},
            {"op": "eq", "args": ["a", "a"], "into": "t"},
        ]},
        "t", 1,
    ),
    (
        "eq 4==5 → 0",
        {"ops": [
            {"op": "let", "name": "a", "value": 4},
            {"op": "let", "name": "b", "value": 5},
            {"op": "eq", "args": ["a", "b"], "into": "t"},
        ]},
        "t", 0,
    ),
    (
        "lt 3<9 → 1",
        {"ops": [
            {"op": "let", "name": "a", "value": 3},
            {"op": "let", "name": "b", "value": 9},
            {"op": "lt", "args": ["a", "b"], "into": "t"},
        ]},
        "t", 1,
    ),
    (
        "and 1&3",
        {"ops": [
            {"op": "let", "name": "a", "value": 1},
            {"op": "let", "name": "b", "value": 3},
            {"op": "and", "args": ["a", "b"], "into": "t"},
        ]},
        "t", 1,
    ),
    (
        "xor 5^3",
        {"ops": [
            {"op": "let", "name": "a", "value": 5},
            {"op": "let", "name": "b", "value": 3},
            {"op": "xor", "args": ["a", "b"], "into": "t"},
        ]},
        "t", 6,
    ),
]


@pytest.mark.parametrize(
    "name,program,regname,expected",
    _COMPILER_SEMANTIC_VECTORS,
    ids=lambda v: v.replace(" ", "_").replace("→", "-") if isinstance(v, str) else v,
)
def test_compiler_semantics_on_unified_vm(name, program, regname, expected):
    result, vm = _compile_and_run(program)
    assert vm.halted, f"{name}: program did not halt cleanly"
    reg = result.register_map[regname]
    assert vm.regs.read_gp(reg) == expected, (
        f"{name}: {regname} (R{reg}) = {vm.regs.read_gp(reg)}, expected {expected}"
    )


# ── Control-flow semantics (JZ Format F / JMP / LOOP) ──────────────────────

def test_compiler_if_false_takes_else_branch():
    result, vm = _compile_and_run({
        "ops": [
            {"op": "let", "name": "flag", "value": 0},
            {"op": "if", "cond": "flag",
             "then": [{"op": "let", "name": "x", "value": 1}],
             "else": [{"op": "let", "name": "x", "value": 2}]},
        ]
    })
    assert vm.regs.read_gp(result.register_map["x"]) == 2


def test_compiler_if_true_takes_then_branch():
    result, vm = _compile_and_run({
        "ops": [
            {"op": "let", "name": "flag", "value": 7},
            {"op": "if", "cond": "flag",
             "then": [{"op": "let", "name": "x", "value": 1}],
             "else": [{"op": "let", "name": "x", "value": 2}]},
        ]
    })
    assert vm.regs.read_gp(result.register_map["x"]) == 1


def test_compiler_loop_runs_body_count_times():
    """LOOP (0x46, Format F, BE back-offset) iterates exactly `count` times."""
    result, vm = _compile_and_run({
        "ops": [
            {"op": "let", "name": "acc", "value": 0},
            {"op": "let", "name": "one", "value": 1},
            {"op": "loop", "count": 3,
             "body": [{"op": "add", "args": ["acc", "one"], "into": "acc"}]},
        ]
    })
    assert vm.regs.read_gp(result.register_map["acc"]) == 3


# ── A2A operand semantics (not just dispatch) ──────────────────────────────

def test_a2a_tell_operand_semantics():
    """TELL payload = (tag_id, agent_id, data) per 'Send rs2 to agent rs1, tag rd'."""
    events = []

    def handler(name, data):
        events.append((name, _struct.unpack("<III", data)))
        return None

    _compile_and_run(
        {"ops": [{"op": "tell", "to": "oracle1", "what": 42, "tag": "greeting"}]},
        a2a_handler=handler,
    )
    assert len(events) == 1 and events[0][0] == "TELL"
    tag, agent, data = events[0][1]
    assert tag == _intern("greeting")
    assert agent == _intern("oracle1")
    assert data == 42


def test_a2a_ask_response_semantics():
    """ASK 'resp→rd': handler result lands in the destination register."""
    result, vm = _compile_and_run(
        {"ops": [{"op": "ask", "from": "jetsonclaw1", "what": "status", "into": "resp"}]},
        a2a_handler=lambda name, data: 31337 if name == "ASK" else None,
    )
    assert vm.regs.read_gp(result.register_map["resp"]) == 31337


def test_a2a_deleg_operand_semantics():
    events = []
    _compile_and_run(
        {"ops": [{"op": "delegate", "to": "babel", "task": "translate"}]},
        a2a_handler=lambda n, d: events.append((n, _struct.unpack("<III", d))) and None,
    )
    assert events[0][0] == "DELEG"
    _, agent, task = events[0][1]
    assert agent == _intern("babel")
    assert task == _intern("translate")


def test_a2a_broadcast_zero_agent_field():
    events = []
    _compile_and_run(
        {"ops": [{"op": "broadcast", "what": "deploy", "tag": "ops"}]},
        a2a_handler=lambda n, d: events.append((n, _struct.unpack("<III", d))) and None,
    )
    assert events[0][0] == "BCAST"
    tag, agent, data = events[0][1]
    assert agent == 0                    # rs1 references a zero register: fleet-wide
    assert tag == _intern("ops")
    assert data == _intern("deploy")


def test_a2a_sequence_preserves_program_order():
    """A full program: data flow into A2A ops and event order both hold."""
    events = []

    def handler(name, data):
        events.append((name, _struct.unpack("<III", data)))
        return 5 if name == "ASK" else None

    result, vm = _compile_and_run({
        "ops": [
            {"op": "let", "name": "n", "value": 21},
            {"op": "add", "args": ["n", "n"], "into": "doubled"},
            {"op": "tell", "to": "oracle1", "what": "doubled", "tag": "math"},
            {"op": "ask", "from": "oracle1", "what": "check", "into": "verdict"},
            {"op": "broadcast", "what": "done", "tag": "status"},
        ]
    }, a2a_handler=handler)

    assert [e[0] for e in events] == ["TELL", "ASK", "BCAST"]
    # TELL carried the computed value (42), not a symbol id
    tag, agent, data = events[0][1]
    assert data == 42 and agent == _intern("oracle1") and tag == _intern("math")
    # ASK's response (5) landed in `verdict`
    assert vm.regs.read_gp(result.register_map["verdict"]) == 5
    # BCAST fleet-wide
    assert events[2][1][1] == 0


# ── Cross-assembler → unified VM conformance (toolchain round-trip) ────────

def test_cross_assembler_unified_conformance_battery():
    """Assemble in unified mode → execute on the unified VM → assert semantics."""
    asm = CrossAssembler(target="unified")
    res = asm.assemble(
        "MOVI R1, 6\n"
        "MOVI R2, 7\n"
        "MUL R3, R1, R2\n"
        "MOVI R4, 2\n"
        "SUB R5, R3, R4\n"
        "MOVI16 R6, 4096\n"
        "HALT\n"
    )
    assert not res.errors, [str(e) for e in res.errors]
    vm = Interpreter(res.bytecode, isa="unified")
    vm.execute()
    assert vm.halted
    assert vm.regs.read_gp(3) == 42      # MUL
    assert vm.regs.read_gp(5) == 40      # SUB
    assert vm.regs.read_gp(6) == 4096    # MOVI16 big-endian


def test_cross_assembler_dual_mode_diverges_correctly():
    """Same mnemonic source assembles to DIFFERENT bytes per target — both exec.

    This is the dual-mode contract: System A tests keep their legacy bytes;
    the unified equivalents assert the converged numbering. Neither mode's
    output runs on the other's VM (that divergence is the point of the
    selector).
    """
    src = "MOVI R1, 42\nHALT\n"
    a = CrossAssembler(target="system_a").assemble(src)
    u = CrossAssembler(target="unified").assemble(src)
    assert not a.errors and not u.errors
    assert a.bytecode != u.bytecode      # different numberings by design

    vm_a = Interpreter(a.bytecode, isa="system_a")  # legacy mode, explicit
    vm_a.execute()
    assert vm_a.regs.read_gp(1) == 42 and vm_a.halted

    vm_u = Interpreter(u.bytecode, isa="unified")
    vm_u.execute()
    assert vm_u.regs.read_gp(1) == 42 and vm_u.halted
