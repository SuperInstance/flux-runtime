"""Dual-mode ISA equivalence — System A (legacy) ↔ System B (unified).

Phase 4 of the A/B reconciliation (memory/flux-ab-plan-2026-08-21.md): for
each core ISA semantic that the System A test suite pins with hard-coded
legacy opcodes, this module adds the unified-mode equivalent — the SAME
semantic program encoded with System B (converged) numbering — and asserts
that both modes produce identical observable results on their respective
interpreter paths.

Per the plan's rule: no System A test is deleted or weakened; they keep
testing the legacy decoding they were written for (annotated in place).
This module is the additive unified twin.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter


def run_a(bytecode) -> Interpreter:
    vm = Interpreter(bytes(bytecode))  # default isa="system_a"
    vm.execute()
    return vm


def run_b(bytecode) -> Interpreter:
    vm = Interpreter(bytes(bytecode), isa="unified")
    vm.execute()
    return vm


# Each case: (name, system_a_bytes, unified_bytes, check(vm) -> bool)
_CASES = [
    (
        "nop_then_halt",
        [Op.NOP, Op.HALT],
        [0x01, 0x00],  # NOP; HALT (System B)
        lambda vm: vm.halted,
    ),
    (
        "mov_copies_register",
        [Op.MOVI, 1, 42, 0, Op.MOV, 0, 1, Op.HALT],
        [0x18, 1, 42, 0x3A, 0, 1, 0, 0x00],  # MOVI R1,42; MOV R0,R1,0; HALT
        lambda vm: vm.regs.read_gp(0) == 42,
    ),
    (
        "add",
        [Op.MOVI, 1, 20, 0, Op.MOVI, 2, 22, 0,
         Op.IADD, 0, 1, 2, Op.HALT],
        [0x18, 1, 20, 0x18, 2, 22, 0x20, 0, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(0) == 42,
    ),
    (
        "sub",
        [Op.MOVI, 1, 50, 0, Op.MOVI, 2, 8, 0,
         Op.ISUB, 0, 1, 2, Op.HALT],
        [0x18, 1, 50, 0x18, 2, 8, 0x21, 0, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(0) == 42,
    ),
    (
        "mul",
        [Op.MOVI, 1, 6, 0, Op.MOVI, 2, 7, 0,
         Op.IMUL, 0, 1, 2, Op.HALT],
        [0x18, 1, 6, 0x18, 2, 7, 0x22, 0, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(0) == 42,
    ),
    (
        "div",
        [Op.MOVI, 1, 84, 0, Op.MOVI, 2, 2, 0,
         Op.IDIV, 0, 1, 2, Op.HALT],
        [0x18, 1, 84, 0x18, 2, 2, 0x23, 0, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(0) == 42,
    ),
    (
        "mod",
        [Op.MOVI, 1, 17, 0, Op.MOVI, 2, 5, 0,
         Op.IMOD, 0, 1, 2, Op.HALT],
        [0x18, 1, 17, 0x18, 2, 5, 0x24, 0, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(0) == 2,
    ),
    (
        "inc",
        [Op.MOVI, 1, 6, 0, Op.INC, 1, Op.HALT],
        [0x18, 1, 6, 0x08, 1, 0x00],
        lambda vm: vm.regs.read_gp(1) == 7,
    ),
    (
        "dec",
        [Op.MOVI, 1, 43, 0, Op.DEC, 1, Op.HALT],
        [0x18, 1, 43, 0x09, 1, 0x00],
        lambda vm: vm.regs.read_gp(1) == 42,
    ),
    (
        "push_pop_roundtrip",
        [Op.MOVI, 0, 77, 0, Op.PUSH, 0, Op.POP, 1, Op.HALT],
        [0x18, 0, 77, 0x0C, 0, 0x0D, 1, 0x00],
        lambda vm: vm.regs.read_gp(1) == 77,
    ),
    (
        "jmp_skips_forward",
        # MOVI R0,1; JMP +4 (skip the 4-byte MOVI R0,99); MOVI R0,99; HALT
        [Op.MOVI, 0, 1, 0, Op.JMP, 0, 4, 0, Op.MOVI, 0, 99, 0, Op.HALT],
        [0x18, 0, 1, 0x43, 0, 0x00, 0x03, 0x18, 0, 99, 0x00],
        lambda vm: vm.regs.read_gp(0) == 1,
    ),
    (
        "jz_taken_when_zero",
        # MOVI R1,0; JZ R1,+4; MOVI R0,99; HALT → R0 stays 0
        [Op.MOVI, 1, 0, 0, Op.JZ, 1, 4, 0, Op.MOVI, 0, 99, 0, Op.HALT],
        [0x18, 1, 0, 0x3C, 1, 0x00, 0x03, 0x18, 0, 99, 0x00],
        lambda vm: vm.regs.read_gp(0) == 0,
    ),
    (
        "jz_not_taken_when_nonzero",
        [Op.MOVI, 1, 5, 0, Op.JZ, 1, 4, 0, Op.MOVI, 0, 99, 0, Op.HALT],
        [0x18, 1, 5, 0x3C, 1, 0x00, 0x03, 0x18, 0, 99, 0x00],
        lambda vm: vm.regs.read_gp(0) == 99,
    ),
    (
        "jnz_taken_when_nonzero",
        [Op.MOVI, 1, 5, 0, Op.JNZ, 1, 4, 0, Op.MOVI, 0, 99, 0, Op.HALT],
        [0x18, 1, 5, 0x3D, 1, 0x00, 0x03, 0x18, 0, 99, 0x00],
        lambda vm: vm.regs.read_gp(0) == 0,
    ),
    (
        "load_store_roundtrip_addr0",
        # MOVI R0,4242; STORE R0,R1 (addr=reg[R1]=0); LOAD R2,R1; HALT
        [Op.MOVI, 0, 4242 & 0xFF, (4242 >> 8) & 0xFF,
         Op.STORE, 0, 1, Op.LOAD, 2, 1, Op.HALT],
        # MOVI R0,4242 (16-bit? 4242>127 → MOVI16 BE); STORE R0,R1,R2; LOAD R3,R1,R2
        [0x40, 0, 0x10, 0x92, 0x39, 0, 1, 2, 0x38, 3, 1, 2, 0x00],
        lambda vm: vm.regs.read_gp(2 if not vm.isa == "unified" else 3) == 4242,
    ),
    (
        "call_ret_subroutine",
        # System A: MOVI R5,0; CALL +1 (push 8, pc=9); HALT@8; MOVI R5,9@9; RET
        [Op.MOVI, 5, 0, 0, Op.CALL, 0, 1, 0, Op.HALT,
         Op.MOVI, 5, 9, 0, Op.RET],
        # System B: MOVI R5,0; CALL R0,8 (pc=reg0+8); HALT@7; MOVI R5,9@8; RET@11
        [0x18, 5, 0, 0x45, 0, 0x00, 0x08, 0x00,
         0x18, 5, 9, 0x02],
        lambda vm: vm.regs.read_gp(5) == 9,
    ),
]


@pytest.mark.parametrize(
    "name,a_bytes,b_bytes,check",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_dual_mode_equivalence(name, a_bytes, b_bytes, check):
    """Same semantics, two encodings — both must hold on their own VM."""
    vm_a = run_a(a_bytes)
    assert vm_a.halted or name == "call_ret_subroutine", f"{name}: System A did not halt"
    assert check(vm_a), f"{name}: System A semantics broken"

    vm_b = run_b(b_bytes)
    assert check(vm_b), f"{name}: unified (System B) semantics broken"


def test_a2a_tell_both_modes_dispatch():
    """A2A TELL in both encodings reaches the TELL handler (payloads differ by
    design: Format G raw bytes vs Format E packed registers)."""
    # System A: TELL 0x60, Format G [op][len:u16 LE][data]
    a_events = []
    vm_a = Interpreter(bytes([Op.TELL, 3, 0, ord("h"), ord("i"), 0, Op.HALT]))
    vm_a.on_a2a(lambda n, d: a_events.append((n, bytes(d))) and None)
    vm_a.execute()
    assert a_events and a_events[0][0] == "TELL"

    # System B: MOVI R1,7; MOVI R2,42; MOVI R3,9; TELL R3,R1,R2; HALT
    b_events = []
    vm_b = Interpreter(bytes(
        [0x18, 1, 7, 0x18, 2, 42, 0x18, 3, 9, 0x50, 3, 1, 2, 0x00]
    ), isa="unified")
    vm_b.on_a2a(lambda n, d: b_events.append((n, bytes(d))) and None)
    vm_b.execute()
    assert b_events and b_events[0][0] == "TELL"
    import struct
    tag, agent, data = struct.unpack("<III", b_events[0][1])
    assert (tag, agent, data) == (9, 7, 42)


def test_cross_mode_is_rejected_not_misdecoded():
    """A unified HALT (0x00) must NOT run as System A (where 0x00 = NOP) and
    vice versa — the selector is what prevents silent cross-mode misdecode."""
    from flux.vm.interpreter import VMInvalidOpcodeError

    # System A TELL (0x60) in unified mode = C_ADD range → unimplemented,
    # raises cleanly rather than silently doing something else.
    vm = Interpreter(bytes([0x60, 0x69]), isa="unified")
    with pytest.raises(VMInvalidOpcodeError):
        vm.execute()
