"""FLUX Unified ISA Python VM — Conformance Interpreter.

Implements the converged opcode numbering from isa_unified.py / formats.py.
This is the reference Python VM for cross-runtime conformance testing.

Instruction encoding formats (from formats.py):

    Format A (1 byte):  [op]
    Format B (2 bytes): [op][rd]
    Format C (2 bytes): [op][imm8]
    Format D (3 bytes): [op][rd][imm8]           (sign-extended)
    Format E (4 bytes): [op][rd][rs1][rs2]
    Format F (4 bytes): [op][rd][imm16hi][imm16lo]
    Format G (5 bytes): [op][rd][rs1][imm16hi][imm16lo]

Opcode ranges (dispatch by opcode byte):
    0x00-0x03  Format A  System control
    0x04-0x07  Format A  Interrupt/control
    0x08-0x0F  Format B  Single register ops
    0x10-0x17  Format C  Immediate only
    0x18-0x1F  Format D  Register + imm8
    0x20-0x3F  Format E  Integer/float/memory/control (3-reg)
    0x40-0x47  Format F  Register + imm16
    0x48-0x4F  Format G  Register + register + imm16
    0x50-0x6F  Format E  A2A / confidence variants
    0x70+      Various   Extended (stubbed as no-ops)

Author: Super Z (Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple


# ── Unified ISA Opcode Constants ────────────────────────────────────────────

# Format A — System Control (0x00-0x03)
HALT  = 0x00
NOP   = 0x01
RET   = 0x02
IRET  = 0x03

# Format A — Interrupt/Debug (0x04-0x07)
BRK   = 0x04
WFI   = 0x05
RESET = 0x06
SYN   = 0x07

# Format B — Single Register (0x08-0x0F)
INC       = 0x08
DEC       = 0x09
NOT       = 0x0A
NEG       = 0x0B
PUSH      = 0x0C
POP       = 0x0D
CONF_LD   = 0x0E
CONF_ST   = 0x0F

# Format C — Immediate Only (0x10-0x17)
SYS       = 0x10
TRAP      = 0x11
DBG       = 0x12
CLF       = 0x13
SEMA      = 0x14
YIELD     = 0x15
CACHE     = 0x16
STRIPCF   = 0x17

# Format D — Register + imm8 (0x18-0x1F)
MOVI  = 0x18
ADDI  = 0x19
SUBI  = 0x1A
ANDI  = 0x1B
ORI   = 0x1C
XORI  = 0x1D
SHLI  = 0x1E
SHRI  = 0x1F

# Format E — Integer Arithmetic (0x20-0x2F)
ADD     = 0x20
SUB     = 0x21
MUL     = 0x22
DIV     = 0x23
MOD     = 0x24
AND     = 0x25
OR      = 0x26
XOR     = 0x27
SHL     = 0x28
SHR     = 0x29
MIN     = 0x2A
MAX     = 0x2B
CMP_EQ  = 0x2C
CMP_LT  = 0x2D
CMP_GT  = 0x2E
CMP_NE  = 0x2F

# Format E — Float / Memory / Control (0x30-0x3F)
FADD   = 0x30
FSUB   = 0x31
FMUL   = 0x32
FDIV   = 0x33
FMIN   = 0x34
FMAX   = 0x35
FTOI   = 0x36
ITOF   = 0x37
LOAD   = 0x38
STORE  = 0x39
MOV    = 0x3A
SWP    = 0x3B
JZ_E   = 0x3C
JNZ_E  = 0x3D
JLT    = 0x3E
JGT    = 0x3F

# Format F — Register + imm16 (0x40-0x47)
MOVI16  = 0x40
ADDI16  = 0x41
SUBI16  = 0x42
JMP     = 0x43
JAL     = 0x44
CALL_F  = 0x45
LOOP    = 0x46
SELECT  = 0x47

# Format G — Register + register + imm16 (0x48-0x4F)
LOADOFF  = 0x48
STOREOFF = 0x49
LOADI    = 0x4A
STOREI   = 0x4B
ENTER_G  = 0x4C
LEAVE_G  = 0x4D
COPY_G   = 0x4E
FILL_G   = 0x4F


# ── Opcode name lookup ──────────────────────────────────────────────────────

_OPCODE_NAMES: Dict[int, str] = {
    0x00: "HALT", 0x01: "NOP", 0x02: "RET", 0x03: "IRET",
    0x04: "BRK", 0x05: "WFI", 0x06: "RESET", 0x07: "SYN",
    0x08: "INC", 0x09: "DEC", 0x0A: "NOT", 0x0B: "NEG",
    0x0C: "PUSH", 0x0D: "POP", 0x0E: "CONF_LD", 0x0F: "CONF_ST",
    0x10: "SYS", 0x11: "TRAP", 0x12: "DBG", 0x13: "CLF",
    0x14: "SEMA", 0x15: "YIELD", 0x16: "CACHE", 0x17: "STRIPCF",
    0x18: "MOVI", 0x19: "ADDI", 0x1A: "SUBI", 0x1B: "ANDI",
    0x1C: "ORI", 0x1D: "XORI", 0x1E: "SHLI", 0x1F: "SHRI",
    0x20: "ADD", 0x21: "SUB", 0x22: "MUL", 0x23: "DIV",
    0x24: "MOD", 0x25: "AND", 0x26: "OR", 0x27: "XOR",
    0x28: "SHL", 0x29: "SHR", 0x2A: "MIN", 0x2B: "MAX",
    0x2C: "CMP_EQ", 0x2D: "CMP_LT", 0x2E: "CMP_GT", 0x2F: "CMP_NE",
    0x30: "FADD", 0x31: "FSUB", 0x32: "FMUL", 0x33: "FDIV",
    0x34: "FMIN", 0x35: "FMAX", 0x36: "FTOI", 0x37: "ITOF",
    0x38: "LOAD", 0x39: "STORE", 0x3A: "MOV", 0x3B: "SWP",
    0x3C: "JZ", 0x3D: "JNZ", 0x3E: "JLT", 0x3F: "JGT",
    0x40: "MOVI16", 0x41: "ADDI16", 0x42: "SUBI16", 0x43: "JMP",
    0x44: "JAL", 0x45: "CALL", 0x46: "LOOP", 0x47: "SELECT",
    0x48: "LOADOFF", 0x49: "STOREOFF", 0x4A: "LOADI", 0x4B: "STOREI",
    0x4C: "ENTER", 0x4D: "LEAVE", 0x4E: "COPY", 0x4F: "FILL",
    0xF0: "HALT_ERR", 0xFF: "ILLEGAL",
}


def opcode_name(op: int) -> str:
    """Return mnemonic for an opcode byte."""
    return _OPCODE_NAMES.get(op, f"UNKNOWN_0x{op:02X}")


# ── VM Interpreter ──────────────────────────────────────────────────────────


class UnifiedVM:
    """FLUX Unified ISA interpreter.

    Parameters
    ----------
    bytecode:
        Raw bytecode bytes to execute.
    memory_size:
        Size of the linear memory in bytes.
    max_cycles:
        Cycle budget before forced halt.
    trace:
        If True, print each instruction as it executes.
    """

    MAX_CYCLES = 10_000_000

    def __init__(
        self,
        bytecode: bytes,
        memory_size: int = 65536,
        max_cycles: int = MAX_CYCLES,
        trace: bool = False,
    ) -> None:
        self.bytecode = bytecode
        self.pc = 0
        self.cycle_count = 0
        self.max_cycles = max_cycles
        self.halted = False
        self.crashed = False
        self.trace = trace

        # Register file R0-R15
        self.registers = [0] * 16

        # Confidence register file (parallel, per-register)
        self.confidence = [0] * 16

        # Stack (simple Python list, grows upward)
        self.stack: List[int] = []

        # Linear memory
        self.memory = bytearray(memory_size)

        # Condition flags
        self.flag_zero = False
        self.flag_sign = False

    # ── Register helpers ───────────────────────────────────────────────────

    def _rd(self, idx: int) -> int:
        """Read register."""
        return self.registers[idx & 0xF]

    def _wr(self, idx: int, val: int) -> None:
        """Write register."""
        self.registers[idx & 0xF] = val

    # ── Fetch helpers ──────────────────────────────────────────────────────

    def _fetch_u8(self) -> int:
        b = self.bytecode[self.pc]
        self.pc += 1
        return b

    def _fetch_i8(self) -> int:
        b = self._fetch_u8()
        return b if b < 128 else b - 256

    def _fetch_u16_be(self) -> int:
        """Fetch u16 big-endian (Format F/G use hi,lo order)."""
        hi = self._fetch_u8()
        lo = self._fetch_u8()
        return (hi << 8) | lo

    def _fetch_i16_be(self) -> int:
        """Fetch i16 big-endian."""
        val = self._fetch_u16_be()
        return val if val < 0x8000 else val - 0x10000

    # ── Stack helpers ──────────────────────────────────────────────────────

    def _push(self, val: int) -> None:
        self.stack.append(val)

    def _pop(self) -> int:
        if not self.stack:
            self.crashed = True
            self.halted = True
            raise RuntimeError("Stack underflow")
        return self.stack.pop()

    # ── Flags ──────────────────────────────────────────────────────────────

    def _set_flags(self, result: int) -> None:
        self.flag_zero = (result == 0)
        self.flag_sign = (result < 0)

    # ── Memory helpers ─────────────────────────────────────────────────────

    def _mem_read_i32(self, addr: int) -> int:
        addr = addr & 0xFFFF
        b = self.memory[addr:addr + 4]
        return struct.unpack_from('<i', b, 0)[0]

    def _mem_write_i32(self, addr: int, val: int) -> None:
        addr = addr & 0xFFFF
        data = struct.pack('<i', val & 0xFFFFFFFF)
        self.memory[addr:addr + 4] = data

    # ── Main loop ──────────────────────────────────────────────────────────

    def execute(self) -> dict:
        """Run until HALT, crash, or cycle budget exceeded.

        Returns a dict with register state and metadata for conformance.
        """
        try:
            while not self.halted and self.cycle_count < self.max_cycles:
                self._step()
                self.cycle_count += 1
        except Exception as e:
            self.crashed = True
            self.halted = True
            if self.trace:
                print(f"  [CRASH] {e}")

        return self.snapshot()

    def snapshot(self) -> dict:
        """Return VM state for conformance checking."""
        return {
            "registers": {i: self.registers[i] for i in range(16)},
            "confidence": {i: self.confidence[i] for i in range(16)},
            "pc": self.pc,
            "cycle_count": self.cycle_count,
            "halted": self.halted,
            "crashed": self.crashed,
            "stack_depth": len(self.stack),
        }

    # ── Single-step ────────────────────────────────────────────────────────

    def _step(self) -> None:
        start_pc = self.pc
        op = self._fetch_u8()

        if self.trace:
            name = opcode_name(op)
            print(f"  [{start_pc:04X}] {name} (0x{op:02X})")

        # ── Format A: System Control (0x00-0x03) ───────────────────────────
        if op == HALT:
            self.halted = True
            return

        if op == NOP:
            return

        if op == RET:
            if self.stack:
                self.pc = self._pop()
            else:
                self.halted = True
            return

        if op == IRET:
            # Interrupt return — stub: halt
            self.halted = True
            return

        # ── Format A: Interrupt/Debug (0x04-0x07) ─────────────────────────
        if op == BRK:
            self.halted = True
            return

        if op in (WFI, RESET, SYN):
            # Stub: no-op
            return

        # ── Format B: Single Register (0x08-0x0F) ─────────────────────────
        if 0x08 <= op <= 0x0F:
            rd = self._fetch_u8()
            if op == INC:
                val = self._rd(rd) + 1
                self._wr(rd, val)
                self._set_flags(val)
            elif op == DEC:
                val = self._rd(rd) - 1
                self._wr(rd, val)
                self._set_flags(val)
            elif op == NOT:
                val = ~self._rd(rd)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == NEG:
                val = -self._rd(rd)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == PUSH:
                self._push(self._rd(rd))
            elif op == POP:
                self._wr(rd, self._pop())
            elif op == CONF_LD:
                self._wr(rd, self.confidence[rd & 0xF])
            elif op == CONF_ST:
                self.confidence[rd & 0xF] = self._rd(rd)
            return

        # ── Format C: Immediate Only (0x10-0x17) ──────────────────────────
        if 0x10 <= op <= 0x17:
            imm8 = self._fetch_u8()
            # All Format C ops are system/debug — stub as no-ops
            if op == RESET:
                self.registers = [0] * 16
            return

        # ── Format D: Register + imm8 (0x18-0x1F) ─────────────────────────
        if 0x18 <= op <= 0x1F:
            rd = self._fetch_u8()
            imm = self._fetch_i8()  # sign-extended

            if op == MOVI:
                self._wr(rd, imm)
            elif op == ADDI:
                val = self._rd(rd) + imm
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SUBI:
                val = self._rd(rd) - imm
                self._wr(rd, val)
                self._set_flags(val)
            elif op == ANDI:
                val = self._rd(rd) & (imm & 0xFF)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == ORI:
                val = self._rd(rd) | (imm & 0xFF)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == XORI:
                val = self._rd(rd) ^ (imm & 0xFF)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SHLI:
                val = self._rd(rd) << (imm & 0x1F)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SHRI:
                val = self._rd(rd) >> (imm & 0x1F)
                self._wr(rd, val)
                self._set_flags(val)
            return

        # ── Format E: 3-register (0x20-0x3F) ──────────────────────────────
        if 0x20 <= op <= 0x3F:
            rd = self._fetch_u8()
            rs1 = self._fetch_u8()
            rs2 = self._fetch_u8()
            v1 = self._rd(rs1)
            v2 = self._rd(rs2)

            if op == ADD:
                val = v1 + v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SUB:
                val = v1 - v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == MUL:
                val = v1 * v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == DIV:
                if v2 == 0:
                    self.crashed = True
                    self.halted = True
                    return
                # Truncate toward zero (Python-style)
                val = int(v1 / v2)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == MOD:
                if v2 == 0:
                    self.crashed = True
                    self.halted = True
                    return
                val = v1 - int(v1 / v2) * v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == AND:
                val = v1 & v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == OR:
                val = v1 | v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == XOR:
                val = v1 ^ v2
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SHL:
                val = v1 << (v2 & 0x1F)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SHR:
                val = v1 >> (v2 & 0x1F)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == MIN:
                val = min(v1, v2)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == MAX:
                val = max(v1, v2)
                self._wr(rd, val)
                self._set_flags(val)
            elif op == CMP_EQ:
                val = 1 if v1 == v2 else 0
                self._wr(rd, val)
                self._set_flags(val)
            elif op == CMP_LT:
                val = 1 if v1 < v2 else 0
                self._wr(rd, val)
                self._set_flags(val)
            elif op == CMP_GT:
                val = 1 if v1 > v2 else 0
                self._wr(rd, val)
                self._set_flags(val)
            elif op == CMP_NE:
                val = 1 if v1 != v2 else 0
                self._wr(rd, val)
                self._set_flags(val)
            elif op == FADD:
                val = int(struct.unpack('<f', struct.pack('<f', float(v1) + float(v2)))[0])
                self._wr(rd, val)
            elif op == FSUB:
                val = int(struct.unpack('<f', struct.pack('<f', float(v1) - float(v2)))[0])
                self._wr(rd, val)
            elif op == FMUL:
                val = int(struct.unpack('<f', struct.pack('<f', float(v1) * float(v2)))[0])
                self._wr(rd, val)
            elif op == FDIV:
                if v2 == 0:
                    self.crashed = True
                    self.halted = True
                    return
                val = int(struct.unpack('<f', struct.pack('<f', float(v1) / float(v2)))[0])
                self._wr(rd, val)
            elif op == FMIN:
                val = int(struct.unpack('<f', struct.pack('<f', min(float(v1), float(v2))))[0])
                self._wr(rd, val)
            elif op == FMAX:
                val = int(struct.unpack('<f', struct.pack('<f', max(float(v1), float(v2))))[0])
                self._wr(rd, val)
            elif op == FTOI:
                self._wr(rd, int(struct.unpack('<f', struct.pack('<f', float(v1)))[0]))
            elif op == ITOF:
                val = int(struct.unpack('<f', struct.pack('<f', float(v1)))[0])
                self._wr(rd, val)
            elif op == LOAD:
                # rd = mem[rs1 + rs2]
                addr = (v1 + v2) & 0xFFFF
                self._wr(rd, self._mem_read_i32(addr))
            elif op == STORE:
                # mem[rs1 + rs2] = rd
                addr = (v1 + v2) & 0xFFFF
                self._mem_write_i32(addr, self._rd(rd))
            elif op == MOV:
                # rd = rs1 (rs2 ignored)
                self._wr(rd, v1)
            elif op == SWP:
                # swap rd and rs1
                tmp = self._rd(rd)
                self._wr(rd, v1)
                self._wr(rs1, tmp)
            elif op == JZ_E:
                # if rd == 0: pc += rs1
                if self._rd(rd) == 0:
                    self.pc += v1
            elif op == JNZ_E:
                # if rd != 0: pc += rs1
                if self._rd(rd) != 0:
                    self.pc += v1
            elif op == JLT:
                # if rd < 0: pc += rs1
                if self._rd(rd) < 0:
                    self.pc += v1
            elif op == JGT:
                # if rd > 0: pc += rs1
                if self._rd(rd) > 0:
                    self.pc += v1
            return

        # ── Format F: Register + imm16 (0x40-0x47) ────────────────────────
        if 0x40 <= op <= 0x47:
            rd = self._fetch_u8()
            imm16 = self._fetch_u16_be()

            if op == MOVI16:
                # Store as signed i16
                self._wr(rd, imm16 if imm16 < 0x8000 else imm16 - 0x10000)
            elif op == ADDI16:
                val = self._rd(rd) + imm16
                self._wr(rd, val)
                self._set_flags(val)
            elif op == SUBI16:
                val = self._rd(rd) - imm16
                self._wr(rd, val)
                self._set_flags(val)
            elif op == JMP:
                # Relative jump: pc += imm16
                self.pc += imm16 if imm16 < 0x8000 else imm16 - 0x10000
            elif op == JAL:
                # rd = pc; pc += imm16
                self._wr(rd, self.pc)
                self.pc += imm16 if imm16 < 0x8000 else imm16 - 0x10000
            elif op == CALL_F:
                # push(pc); pc = rd + imm16
                self._push(self.pc)
                signed_imm = imm16 if imm16 < 0x8000 else imm16 - 0x10000
                self.pc = self._rd(rd) + signed_imm
            elif op == LOOP:
                # rd--; if rd > 0: pc -= imm16
                val = self._rd(rd) - 1
                self._wr(rd, val)
                if val > 0:
                    self.pc -= imm16
            elif op == SELECT:
                # pc += imm16 * rd
                signed_imm = imm16 if imm16 < 0x8000 else imm16 - 0x10000
                self.pc += signed_imm * self._rd(rd)
            return

        # ── Format G: Register + register + imm16 (0x48-0x4F) ─────────────
        if 0x48 <= op <= 0x4F:
            rd = self._fetch_u8()
            rs1 = self._fetch_u8()
            imm16 = self._fetch_u16_be()
            signed_imm = imm16 if imm16 < 0x8000 else imm16 - 0x10000
            base = self._rd(rs1)

            if op == LOADOFF:
                # rd = mem[rs1 + imm16]
                addr = (base + signed_imm) & 0xFFFF
                self._wr(rd, self._mem_read_i32(addr))
            elif op == STOREOFF:
                # mem[rs1 + imm16] = rd
                addr = (base + signed_imm) & 0xFFFF
                self._mem_write_i32(addr, self._rd(rd))
            elif op == LOADI:
                # rd = mem[mem[rs1] + imm16]
                inner_addr = base & 0xFFFF
                outer_addr = (self._mem_read_i32(inner_addr) + signed_imm) & 0xFFFF
                self._wr(rd, self._mem_read_i32(outer_addr))
            elif op == STOREI:
                # mem[mem[rs1] + imm16] = rd
                inner_addr = base & 0xFFFF
                outer_addr = (self._mem_read_i32(inner_addr) + signed_imm) & 0xFFFF
                self._mem_write_i32(outer_addr, self._rd(rd))
            elif op == ENTER_G:
                # push regs; sp -= imm16; rd = old_sp
                self._push(self._rd(rd))
                self._wr(rd, len(self.stack))
                self._wr(14, len(self.stack) + signed_imm)  # R14 as pseudo-SP
            elif op == LEAVE_G:
                # sp += imm16; pop regs; rd = ret
                self._wr(rd, self._pop())
            elif op == COPY_G:
                # memcpy(rd, rs1, imm16) — stub
                pass
            elif op == FILL_G:
                # memset(rd, rs1, imm16) — stub
                pass
            return

        # ── Format E: A2A Fleet Ops (0x50-0x5F) ──────────────────────────
        if 0x50 <= op <= 0x5F:
            rd = self._fetch_u8()
            rs1 = self._fetch_u8()
            rs2 = self._fetch_u8()
            # Stub: all A2A ops are no-ops in conformance VM
            return

        # ── Format E: Confidence-aware variants (0x60-0x6F) ───────────────
        if 0x60 <= op <= 0x69:
            # CONF_THRESHOLD (0x69) is Format D: [0x69][rd][imm8]
            if op == 0x69:
                rd = self._fetch_u8()
                imm8 = self._fetch_u8()
                # if confidence[rd] < imm8: skip next instruction
                if self.confidence[rd & 0xF] < imm8:
                    # Skip next instruction — need to determine its size
                    next_op = self.bytecode[self.pc]
                    skip = self._instruction_size(next_op)
                    self.pc += skip
                return

            # All other CONF_ ops are Format E
            rd = self._fetch_u8()
            rs1 = self._fetch_u8()
            rs2 = self._fetch_u8()
            v1 = self._rd(rs1)
            v2 = self._rd(rs2)
            c1 = self.confidence[rs1 & 0xF]
            c2 = self.confidence[rs2 & 0xF]

            if op == 0x60:  # C_ADD
                self._wr(rd, v1 + v2)
                self.confidence[rd & 0xF] = min(c1, c2)
            elif op == 0x61:  # C_SUB
                self._wr(rd, v1 - v2)
                self.confidence[rd & 0xF] = min(c1, c2)
            elif op == 0x62:  # C_MUL
                self._wr(rd, v1 * v2)
                self.confidence[rd & 0xF] = c1 * c2
            elif op == 0x63:  # C_DIV
                if v2 != 0:
                    self._wr(rd, int(v1 / v2))
                    self.confidence[rd & 0xF] = c1 * c2
            elif op >= 0x6A:
                # 0x6A-0x6F: Format E stubs
                pass
            return

        if 0x6A <= op <= 0x6F:
            # Format E confidence stubs
            rd = self._fetch_u8()
            rs1 = self._fetch_u8()
            rs2 = self._fetch_u8()
            return

        # ── Extended opcodes (0x70+) — stub as Format A no-ops ────────────
        if op >= 0x70:
            # Most extended opcodes are Format E (4 bytes), some Format A
            # We need to consume the right number of bytes
            if 0x70 <= op <= 0x9F:
                # Format E: consume 3 more bytes
                self._fetch_u8()
                self._fetch_u8()
                self._fetch_u8()
            elif 0xA0 <= op <= 0xAF:
                # Format D or E (mixed): consume 2 or 3 more bytes
                if op in (0xA0,):
                    # Format D: consume 2 more bytes
                    self._fetch_u8()
                    self._fetch_u8()
                else:
                    # Format E: consume 3 more bytes
                    self._fetch_u8()
                    self._fetch_u8()
                    self._fetch_u8()
            elif 0xB0 <= op <= 0xCF:
                # Format E: consume 3 more bytes
                self._fetch_u8()
                self._fetch_u8()
                self._fetch_u8()
            elif 0xD0 <= op <= 0xDF:
                # Format G: consume 4 more bytes
                self._fetch_u8()
                self._fetch_u8()
                self._fetch_u8()
                self._fetch_u8()
            elif 0xE0 <= op <= 0xEF:
                # Format F: consume 3 more bytes
                self._fetch_u8()
                self._fetch_u8()
                self._fetch_u8()
            # 0xF0-0xFF: Format A, no extra bytes to consume
            return

        # Unknown opcode
        self.crashed = True
        self.halted = True

    @staticmethod
    def _instruction_size(op: int) -> int:
        """Return the size in bytes for an instruction starting with opcode `op`."""
        if op <= 0x07:
            return 1  # Format A
        elif op <= 0x0F:
            return 2  # Format B
        elif op <= 0x17:
            return 2  # Format C
        elif op <= 0x1F:
            return 3  # Format D
        elif op <= 0x3F:
            return 4  # Format E
        elif op <= 0x47:
            return 4  # Format F
        elif op <= 0x4F:
            return 5  # Format G
        elif op <= 0x69:
            return 4  # Format E (CONF_ variants)
        elif op == 0x69:
            return 3  # Format D (CONF_THRESHOLD)
        elif op <= 0x9F:
            return 4  # Format E (extended)
        elif op <= 0xCF:
            return 4  # Format E (SIMD/tensor)
        elif op <= 0xDF:
            return 5  # Format G (MMIO/GPU)
        elif op <= 0xEF:
            return 4  # Format F (long jumps)
        else:
            return 1  # Format A (0xF0-0xFF)


# ── Convenience runner for conformance tests ─────────────────────────────────

def run_bytecode(bytecode_list: list, trace: bool = False) -> dict:
    """Run a bytecode list through the unified VM and return state.

    This is the runner_fn interface expected by test_conformance.run_conformance_tests().

    Args:
        bytecode_list: List of ints representing the bytecode program.
        trace: If True, print instruction trace.

    Returns:
        dict with 'registers', 'crashed', and other state fields.
    """
    bytecode = bytes(bytecode_list)
    vm = UnifiedVM(bytecode, trace=trace)
    state = vm.execute()
    state["registers"] = {i: state["registers"][i] for i in range(16)}
    return state
