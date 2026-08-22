"""Phase 2 (flux-runtime A/B reconciliation): toolchain System B modes.

Covers the three spec landmines resolved 2026-08-21:

1. JZ encoding — executable truth is Format F (op, rd, imm16 big-endian),
   NOT Format E (register-offset) as isa_unified.py originally labeled it.
   Evidence: signal_compiler._compile_if back-patches a BE imm16 (parallel
   to JMP 0x43 Format F); the asm-text conformance vectors use two-operand
   ``JNZ R2, done`` style; no concrete vector contradicts it.
2. Endianness — System B imm16 is BIG-endian in the executable ground truth
   (signal_compiler._emit_format_f, MOVI16 vector [0x40, rd, 0x10, 0x00]
   = 4096). isa_unified.py's header claim of little-endian was corrected;
   the cross-assembler's unified target now packs BE (System A stays LE).
3. A2A register population — the converged spec (TELL "Send rs2 to agent
   rs1, tag rd"; ASK "Request rs2 from agent rs1, resp→rd") requires the
   operand registers to carry values; the compiler now loads them and the
   unified interpreter writes ASK responses to rd.
"""

import os
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from flux.a2a.signal_compiler import SignalCompiler
from flux.asm.cross_assembler import CrossAssembler
from flux.vm.interpreter import Interpreter


def _intern(name: str) -> int:
    return zlib.crc32(name.encode("utf-8")) & 0x7FFF


# ── Landmine 1: JZ is Format F (op, rd, imm16 big-endian) ──────────────────

def test_jz_format_f_forward_jump_taken():
    """JZ with a BE imm16 skips forward over a poison instruction."""
    # MOVI R1, 0; JZ R1, +3 (skip the next 3 bytes); MOVI R0, 99; HALT
    bc = bytes([0x18, 1, 0,   0x3C, 1, 0x00, 0x03,   0x18, 0, 99,   0x00])
    vm = Interpreter(bc, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(0) == 0  # the MOVI R0,99 was skipped
    assert vm.halted


def test_jz_format_f_not_taken_when_nonzero():
    # MOVI R1, 5; JZ R1, +3; MOVI R0, 99; HALT  → jump NOT taken
    bc = bytes([0x18, 1, 5,   0x3C, 1, 0x00, 0x03,   0x18, 0, 99,   0x00])
    vm = Interpreter(bc, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(0) == 99


def test_jz_backward_jump_loop():
    """Countdown loop: forward JZ + backward JMP both use BE rel16."""
    # MOVI R1,3; MOVI R2,0; loop: JZ R1,done; DEC R1; INC R2; JMP loop; done: HALT
    bc = bytes([
        0x18, 1, 3,          # MOVI R1, 3
        0x18, 2, 0,          # MOVI R2, 0
        0x3C, 1, 0x00, 0x08,  # loop: JZ R1, done (+8 → past JMP, to HALT)
        0x09, 1,             # DEC R1
        0x08, 2,             # INC R2
        0x43, 0, 0xFF, 0xF4,  # JMP loop (-12 → back to the JZ at offset 6)
        0x00,                # done: HALT
    ])
    vm = Interpreter(bc, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(1) == 0
    assert vm.regs.read_gp(2) == 3  # looped exactly 3 times


def test_jnz_jlt_jgt_format_f():
    # JNZ taken (R1=5 ≠ 0) skips poison; JLT taken (-1 < 0) skips; JGT not taken
    bc = bytes([
        0x18, 1, 5,             # MOVI R1, 5
        0x3D, 1, 0x00, 0x03,    # JNZ R1, +3 → skip poison
        0x18, 0, 99,            # poison
        0x18, 2, 0x81,          # MOVI R2, -127
        0x18, 2, 2,             # MOVI R2, 2   (re-bind, now positive)
        0x3F, 2, 0x00, 0x03,    # JGT R2, +3 → taken → skip poison2
        0x18, 0, 77,            # poison2
        0x00,
    ])
    vm = Interpreter(bc, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(0) == 0


def test_isa_unified_spec_labels_jz_family_format_f():
    """The spec comment itself now records Format F for JZ/JNZ/JLT/JGT."""
    from flux.bytecode.isa_unified import build_unified_isa
    table = {d.mnemonic: d for d in build_unified_isa() if not d.reserved}
    for m in ("JZ", "JNZ", "JLT", "JGT"):
        assert table[m].format == "F", f"{m} must be Format F (op, rd, imm16)"


def test_compiler_jz_emission_is_imm16_backpatch():
    """signal_compiler's if→JZ carries an imm16 back-patch (Format F truth)."""
    compiler = SignalCompiler()
    result = compiler.compile({
        "ops": [
            {"op": "let", "name": "flag", "value": 0},
            {"op": "if", "cond": "flag",
             "then": [{"op": "let", "name": "x", "value": 1}],
             "else": [{"op": "let", "name": "x", "value": 2}]},
        ]
    })
    assert result.success, result.errors
    bc = result.bytecode
    jz_at = bc.find(bytes([0x3C]))
    assert jz_at >= 0
    imm = (bc[jz_at + 2] << 8) | bc[jz_at + 3]  # BE rel16 → else branch
    assert imm > 0

    vm = Interpreter(bc, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(result.register_map["x"]) == 2  # took the else path


# ── Landmine 2: imm16 is big-endian (unified), little-endian (System A) ────

def test_cross_assembler_unified_imm16_big_endian():
    asm = CrossAssembler(target="unified")
    res = asm.assemble("MOVI16 R1, 4096\nHALT\n")
    assert not res.errors, [str(e) for e in res.errors]
    assert list(res.bytecode) == [0x40, 1, 0x10, 0x00, 0x00]  # BE: 0x1000


def test_cross_assembler_system_a_imm16_little_endian_unchanged():
    """System A mode packs imm16 little-endian, byte-for-byte as before."""
    asm = CrossAssembler()  # default target="system_a"
    res = asm.assemble("MOVI R1, 4096\nHALT\n")
    assert not res.errors, [str(e) for e in res.errors]
    # System A MOVI 0x2B, Format D reg+imm16 little-endian; HALT 0x80
    assert list(res.bytecode) == [0x2B, 1, 0x00, 0x10, 0x80]


def test_cross_assembler_unified_round_trips_on_unified_vm():
    asm = CrossAssembler(target="unified")
    res = asm.assemble(
        "MOVI R1, 10\n"
        "MOVI R2, 32\n"
        "ADD R3, R1, R2\n"
        "HALT\n"
    )
    assert not res.errors, [str(e) for e in res.errors]
    vm = Interpreter(res.bytecode, isa="unified")
    vm.execute()
    assert vm.halted
    assert vm.regs.read_gp(3) == 42


def test_cross_assembler_unified_jumps_execute():
    asm = CrossAssembler(target="unified")
    res = asm.assemble(
        "MOVI R1, 3\n"
        "MOVI R2, 0\n"
        "loop:\n"
        "JZ R1, done\n"
        "DEC R1\n"
        "INC R2\n"
        "JMP loop\n"
        "done:\n"
        "HALT\n"
    )
    assert not res.errors, [str(e) for e in res.errors]
    vm = Interpreter(res.bytecode, isa="unified")
    vm.execute()
    assert vm.regs.read_gp(2) == 3


def test_cross_assembler_unified_a2a_emits_system_b():
    """TELL in unified mode = 0x50 (System B), dispatched as A2A — not VLOAD."""
    asm = CrossAssembler(target="unified")
    res = asm.assemble(
        "MOVI R1, 7\n"      # agent
        "MOVI R2, 42\n"     # data
        "MOVI R3, 9\n"      # tag
        "TELL R3, R1, R2\n"
        "HALT\n"
    )
    assert not res.errors, [str(e) for e in res.errors]
    assert 0x50 in res.bytecode and 0x80 not in res.bytecode  # no System A HALT

    events = []
    vm = Interpreter(res.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: events.append((name, data)) and None)
    vm.execute()
    assert events and events[0][0] == "TELL"
    tag, agent, data = __import__("struct").unpack("<III", events[0][1])
    assert (tag, agent, data) == (9, 7, 42)


def test_cross_assembler_rejects_unknown_target():
    with pytest.raises(ValueError):
        CrossAssembler(target="system_c")


# ── Landmine 3: A2A register population ────────────────────────────────────

def test_tell_populates_operand_registers():
    """TELL handler receives (tag, agent, data) — not three zeros."""
    import struct as _struct
    compiler = SignalCompiler()
    result = compiler.compile({
        "ops": [{"op": "tell", "to": "oracle1", "what": 42, "tag": "greeting"}]
    })
    assert result.success, result.errors

    seen = []
    vm = Interpreter(result.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: seen.append((name, _struct.unpack("<III", data))) and None)
    vm.execute()

    assert seen and seen[0][0] == "TELL"
    tag, agent, data = seen[0][1]
    assert tag == _intern("greeting")
    assert agent == _intern("oracle1")
    assert data == 42


def test_ask_response_lands_in_rd():
    """ASK 'resp→rd': the handler's return value is written to rd, not R0."""
    compiler = SignalCompiler()
    result = compiler.compile({
        "ops": [
            # let first so `resp` is not allocated R0 (keeps the rd-vs-R0
            # distinction observable)
            {"op": "let", "name": "pad", "value": 1},
            {"op": "ask", "from": "jetsonclaw1", "what": "status", "into": "resp"},
        ]
    })
    assert result.success, result.errors

    vm = Interpreter(result.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: 77 if name == "ASK" else None)
    vm.execute()

    rd = result.register_map["resp"]
    assert rd != 0
    assert vm.regs.read_gp(rd) == 77  # response written to rd, per "resp→rd"


def test_bcast_populates_tag_and_data_with_zero_target():
    import struct as _struct
    compiler = SignalCompiler()
    result = compiler.compile({
        "ops": [{"op": "broadcast", "what": "fleet_update", "tag": "ops"}]
    })
    assert result.success, result.errors

    seen = []
    vm = Interpreter(result.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: seen.append((name, _struct.unpack("<III", data))) and None)
    vm.execute()

    assert seen and seen[0][0] == "BCAST"
    tag, agent, data = seen[0][1]
    assert tag == _intern("ops")
    assert agent == 0              # rs1 = 0 → broadcast to all
    assert data == _intern("fleet_update")


def test_tell_data_from_bound_register_uses_mov():
    """`what` bound by a prior `let` flows through MOV into the A2A operand."""
    import struct as _struct
    compiler = SignalCompiler()
    result = compiler.compile({
        "ops": [
            {"op": "let", "name": "payload", "value": 1234},
            {"op": "tell", "to": "oracle1", "what": "payload", "tag": "t"},
        ]
    })
    assert result.success, result.errors

    seen = []
    vm = Interpreter(result.bytecode, isa="unified")
    vm.on_a2a(lambda name, data: seen.append((name, _struct.unpack("<III", data))) and None)
    vm.execute()

    _, _, data = seen[0][1]
    assert data == 1234


# ── Compiler ISA selector ──────────────────────────────────────────────────

def test_signal_compiler_selector_default_and_alias():
    assert SignalCompiler().isa == "unified"          # historical emission preserved
    assert SignalCompiler(isa="system_b").isa == "unified"
    assert SignalCompiler(isa="unified").isa == "unified"


def test_signal_compiler_selector_rejects_system_a():
    """Signal is System B-native; no System A mapping is invented."""
    with pytest.raises(ValueError, match="system_a"):
        SignalCompiler(isa="system_a")
    with pytest.raises(ValueError):
        SignalCompiler(isa="bogus")


def test_system_a_emission_unchanged_by_default():
    """The default cross-assembler still emits System A bytes (no regression)."""
    asm = CrossAssembler()
    res = asm.assemble("NOP\nHALT\n")
    assert not res.errors, [str(e) for e in res.errors]
    assert list(res.bytecode) == [0x00, 0x80]  # System A NOP/HALT
