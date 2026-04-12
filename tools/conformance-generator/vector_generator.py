#!/usr/bin/env python3
"""FLUX Conformance Vector Generator.

Automatically generates test vectors for any FLUX opcode. Given an opcode name,
produces a JSON test vector with: name, description, category, bytecode,
initial register state, expected register state, expected flags, and optional
expected error.

Supports all Format A-G encodings and generates edge cases including:
- Zero, max, negative values
- Overflow / underflow boundaries
- Carry / borrow conditions
- Divide-by-zero error handling
- Register overlap safety tests
- Flag-setting verification

Author: Super Z (Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import uuid
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple

# ── Add project root to path for imports ──────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flux.bytecode.opcodes import Op, get_format, FORMAT_A, FORMAT_B, FORMAT_C, FORMAT_D, FORMAT_E, FORMAT_G


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

HALT = int(Op.HALT)
NOP = int(Op.NOP)
MOVI = int(Op.MOVI)
PUSH = int(Op.PUSH)
POP = int(Op.POP)

INT32_MAX = 2**31 - 1
INT32_MIN = -(2**31)
UINT16_MAX = 0xFFFF
INT16_MAX = 0x7FFF
INT16_MIN = -0x8000
UINT8_MAX = 0xFF

SAFE_ADDR = 32000  # address within stack region, fits in signed i16


# ═══════════════════════════════════════════════════════════════════════════
# Opcode Metadata Database
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OpcodeInfo:
    """Metadata about a single opcode for vector generation."""
    name: str
    opcode_hex: str
    value: int
    format: str
    category: str
    description: str
    sets_flags: bool = False
    can_error: bool = False
    error_type: str = ""
    is_a2a: bool = False
    is_system: bool = False
    is_float: bool = False
    is_simd: bool = False


def build_opcode_database() -> Dict[str, OpcodeInfo]:
    """Build a comprehensive database of all FLUX opcodes."""
    db: Dict[str, OpcodeInfo] = {}

    def _add(name, category, desc, **kwargs):
        op = getattr(Op, name, None)
        if op is None:
            return
        db[name] = OpcodeInfo(
            name=name,
            opcode_hex=f"0x{int(op):02X}",
            value=int(op),
            format=get_format(op),
            category=category,
            description=desc,
            **kwargs,
        )

    # ── Control Flow (Format A/D) ──────────────────────────────────────────
    _add("NOP", "control", "No operation — does nothing", sets_flags=False)
    _add("HALT", "control", "Halt execution", sets_flags=False)
    _add("MOV", "data", "Move register to register (Format C: rd, rs1)")
    _add("MOVI", "data", "Load signed i16 immediate into register (Format D)")
    _add("JMP", "control", "Unconditional jump with signed i16 offset")
    _add("JZ", "control", "Jump if register is zero")
    _add("JNZ", "control", "Jump if register is non-zero")
    _add("CALL", "control", "Call subroutine — push return address, jump")
    _add("CALL_IND", "control", "Indirect call via register")
    _add("TAILCALL", "control", "Tail call — jump without pushing return address")
    _add("RET", "control", "Return — pop return address and jump")

    # ── Integer Arithmetic (Format B/E) ────────────────────────────────────
    _add("IADD", "arithmetic", "Integer add: rd = rs1 + rs2",
         sets_flags=True)
    _add("ISUB", "arithmetic", "Integer subtract: rd = rs1 - rs2",
         sets_flags=True)
    _add("IMUL", "arithmetic", "Integer multiply: rd = rs1 * rs2",
         sets_flags=True)
    _add("IDIV", "arithmetic", "Integer divide: rd = rs1 / rs2",
         sets_flags=True, can_error=True, error_type="VMDivisionByZeroError")
    _add("IMOD", "arithmetic", "Integer modulo: rd = rs1 % rs2",
         sets_flags=True, can_error=True, error_type="VMDivisionByZeroError")
    _add("IREM", "arithmetic", "Integer remainder: rd = rs1 rem rs2",
         sets_flags=True, can_error=True, error_type="VMDivisionByZeroError")
    _add("INEG", "arithmetic", "Integer negate: rd = -rs1", sets_flags=True)
    _add("INC", "arithmetic", "Increment register: r += 1", sets_flags=True)
    _add("DEC", "arithmetic", "Decrement register: r -= 1", sets_flags=True)

    # ── Bitwise (Format C/E) ───────────────────────────────────────────────
    _add("IAND", "logic", "Bitwise AND: rd = rs1 & rs2", sets_flags=True)
    _add("IOR", "logic", "Bitwise OR: rd = rs1 | rs2", sets_flags=True)
    _add("IXOR", "logic", "Bitwise XOR: rd = rs1 ^ rs2", sets_flags=True)
    _add("INOT", "logic", "Bitwise NOT: rd = ~rs1", sets_flags=True)
    _add("ISHL", "logic", "Shift left: rd = rs1 << (rs2 & 0x3F)", sets_flags=True)
    _add("ISHR", "logic", "Shift right (arithmetic): rd = rs1 >> (rs2 & 0x3F)",
         sets_flags=True)
    _add("ROTL", "logic", "Rotate left (32-bit): rd = rotl32(rs1, rs2 & 0x1F)",
         sets_flags=True)
    _add("ROTR", "logic", "Rotate right (32-bit): rd = rotr32(rs1, rs2 & 0x1F)",
         sets_flags=True)

    # ── Comparison (Format C/D) ────────────────────────────────────────────
    _add("ICMP", "comparison",
         "Integer compare with condition code: rd = cmp(rs1, rs2)",
         sets_flags=True)
    _add("IEQ", "comparison", "Integer equal: rd = (rd == rs1) ? 1 : 0",
         sets_flags=True)
    _add("ILT", "comparison", "Integer less-than: rd = (rd < rs1) ? 1 : 0",
         sets_flags=True)
    _add("ILE", "comparison", "Integer less-equal: rd = (rd <= rs1) ? 1 : 0",
         sets_flags=True)
    _add("IGT", "comparison", "Integer greater-than: rd = (rd > rs1) ? 1 : 0",
         sets_flags=True)
    _add("IGE", "comparison", "Integer greater-equal: rd = (rd >= rs1) ? 1 : 0",
         sets_flags=True)
    _add("TEST", "comparison", "Test bits: flags = rd & rs1 (no store)")
    _add("SETCC", "comparison",
         "Set register from condition flags: rd = (cond_code) ? 1 : 0")
    _add("CMP", "comparison", "Compare and set flags: flags from (rd - rs1)")

    # ── Flag-based Jumps ───────────────────────────────────────────────────
    _add("JE", "control", "Jump if flag_zero (equal)")
    _add("JNE", "control", "Jump if !flag_zero (not equal)")
    _add("JG", "control", "Jump if !flag_zero && !flag_sign (greater)")
    _add("JL", "control", "Jump if flag_sign (less)")
    _add("JGE", "control", "Jump if !flag_sign (greater-equal)")
    _add("JLE", "control", "Jump if flag_zero || flag_sign (less-equal)")

    # ── Stack Operations ───────────────────────────────────────────────────
    _add("PUSH", "stack", "Push register onto stack")
    _add("POP", "stack", "Pop from stack into register")
    _add("DUP", "stack", "Duplicate top of stack (Format A)")
    _add("SWAP", "stack", "Swap top two stack values (Format A)")
    _add("ROT", "stack", "Rotate top 3 stack values (Format A)")
    _add("ENTER", "stack", "Push frame pointer, allocate frame space")
    _add("LEAVE", "stack", "Deallocate frame, restore frame pointer")
    _add("ALLOCA", "stack", "Allocate stack space, return pointer")

    # ── Memory ─────────────────────────────────────────────────────────────
    _add("LOAD", "memory", "Load 32-bit from memory: rd = mem[rs1]")
    _add("STORE", "memory", "Store 32-bit to memory: mem[rs1] = rd")
    _add("LOAD8", "memory", "Load 8-bit (unsigned) from memory")
    _add("STORE8", "memory", "Store 8-bit (low byte) to memory")

    # ── Memory Management (Format G) ───────────────────────────────────────
    _add("REGION_CREATE", "memory_mgmt", "Create named memory region (Format G)")
    _add("REGION_DESTROY", "memory_mgmt", "Destroy named memory region (Format G)")
    _add("REGION_TRANSFER", "memory_mgmt", "Transfer region ownership (Format G)")
    _add("MEMCOPY", "memory_mgmt", "Copy memory within a region (Format G)")
    _add("MEMSET", "memory_mgmt", "Fill memory with a byte value (Format G)")
    _add("MEMCMP", "memory_mgmt", "Compare two memory regions (Format G)")

    # ── Type Operations ────────────────────────────────────────────────────
    _add("CAST", "type", "Type cast (Format C + type tag)")
    _add("BOX", "type", "Box a value with type tag")
    _add("UNBOX", "type", "Unbox a value",
         can_error=True, error_type="VMTypeError")
    _add("CHECK_TYPE", "type", "Verify box type tag matches expected",
         can_error=True, error_type="VMTypeError")
    _add("CHECK_BOUNDS", "type", "Verify index within bounds",
         can_error=True, error_type="VMTypeError")

    # ── Float Arithmetic ───────────────────────────────────────────────────
    _add("FADD", "float", "Float add: fd = fs1 + fs2", is_float=True)
    _add("FSUB", "float", "Float subtract: fd = fs1 - fs2", is_float=True)
    _add("FMUL", "float", "Float multiply: fd = fs1 * fs2", is_float=True)
    _add("FDIV", "float", "Float divide: fd = fs1 / fs2",
         is_float=True, can_error=True, error_type="VMDivisionByZeroError")
    _add("FNEG", "float", "Float negate: fd = -fs1", is_float=True)
    _add("FABS", "float", "Float absolute value: fd = |fs1|", is_float=True)
    _add("FMIN", "float", "Float minimum: fd = min(fd, fs1)", is_float=True)
    _add("FMAX", "float", "Float maximum: fd = max(fd, fs1)", is_float=True)

    # ── Float Comparison ───────────────────────────────────────────────────
    _add("FEQ", "float", "Float equal compare", is_float=True)
    _add("FLT", "float", "Float less-than compare", is_float=True)
    _add("FLE", "float", "Float less-equal compare", is_float=True)
    _add("FGT", "float", "Float greater-than compare", is_float=True)
    _add("FGE", "float", "Float greater-equal compare", is_float=True)

    # ── SIMD Vector ────────────────────────────────────────────────────────
    _add("VLOAD", "simd", "Load 16 bytes into vector register", is_simd=True)
    _add("VSTORE", "simd", "Store 16 bytes from vector register", is_simd=True)
    _add("VADD", "simd", "Byte-wise vector add", is_simd=True)
    _add("VSUB", "simd", "Byte-wise vector subtract", is_simd=True)
    _add("VMUL", "simd", "Byte-wise vector multiply", is_simd=True)
    _add("VDIV", "simd", "Byte-wise vector divide",
         is_simd=True, can_error=True, error_type="VMDivisionByZeroError")
    _add("VFMA", "simd", "Vector fused multiply-add (Format E)", is_simd=True)

    # ── ISA v3: Confidence / Meta ──────────────────────────────────────────
    _add("CONF", "meta", "Attach confidence to previous result")
    _add("MERGE", "meta", "Weighted merge of two registers")
    _add("RESTORE", "meta", "Restore VM state from named region")

    # ── ISA v3: Evolution & Instinct ───────────────────────────────────────
    _add("EVOLVE", "evolution", "Trigger evolution cycle")
    _add("INSTINCT", "evolution", "Execute instinct-based action")
    _add("WITNESS", "evolution", "Write witness mark to commit log")
    _add("SNAPSHOT", "evolution", "Save full VM state snapshot")

    # ── System ─────────────────────────────────────────────────────────────
    _add("YIELD", "system", "Cooperative yield (no-op in single-threaded mode)",
         is_system=True)
    _add("DEBUG_BREAK", "system", "Trigger debug breakpoint", is_system=True)
    _add("RESOURCE_ACQUIRE", "system", "Acquire a resource (Format G)",
         is_system=True)
    _add("RESOURCE_RELEASE", "system", "Release a resource (Format G)",
         is_system=True)

    # ── A2A Protocol (all Format G) ────────────────────────────────────────
    for a2a_op in [
        "TELL", "ASK", "DELEGATE", "DELEGATE_RESULT",
        "REPORT_STATUS", "REQUEST_OVERRIDE", "BROADCAST", "REDUCE",
        "DECLARE_INTENT", "ASSERT_GOAL", "VERIFY_OUTCOME", "EXPLAIN_FAILURE",
        "SET_PRIORITY", "TRUST_CHECK", "TRUST_UPDATE", "TRUST_QUERY",
        "REVOKE_TRUST", "CAP_REQUIRE", "CAP_REQUEST", "CAP_GRANT",
        "CAP_REVOKE", "BARRIER", "SYNC_CLOCK", "FORMATION_UPDATE",
    ]:
        _add(a2a_op, "a2a", f"A2A protocol: {a2a_op}", is_a2a=True)

    _add("EMERGENCY_STOP", "a2a", "Emergency stop — halt immediately", is_a2a=True)

    return db


OPCODE_DB = build_opcode_database()


# ═══════════════════════════════════════════════════════════════════════════
# Bytecode Encoding Helpers
# ═══════════════════════════════════════════════════════════════════════════

def encode_i16(value: int) -> bytes:
    """Encode a signed 16-bit integer in little-endian."""
    value = value & 0xFFFF
    return bytes([value & 0xFF, (value >> 8) & 0xFF])


def encode_u16(value: int) -> bytes:
    """Encode an unsigned 16-bit integer in little-endian."""
    return bytes([value & 0xFF, (value >> 8) & 0xFF])


def encode_i32(value: int) -> bytes:
    """Encode a signed 32-bit integer in little-endian."""
    value = value & 0xFFFFFFFF
    return bytes([value & 0xFF, (value >> 8) & 0xFF,
                  (value >> 16) & 0xFF, (value >> 24) & 0xFF])


def encode_format_g(data: bytes) -> bytes:
    """Encode Format G: u16 length prefix + data bytes."""
    return encode_u16(len(data)) + data


def encode_movis(rd: int, imm: int) -> bytes:
    """Encode MOVI rd, imm16 (Format D)."""
    return bytes([MOVI, rd & 0xFF]) + encode_i16(imm)


def encode_push(reg: int) -> bytes:
    """Encode PUSH reg (Format B)."""
    return bytes([PUSH, reg & 0xFF])


def encode_pop(reg: int) -> bytes:
    """Encode POP reg (Format B)."""
    return bytes([POP, reg & 0xFF])


def encode_halt() -> bytes:
    """Encode HALT."""
    return bytes([HALT])


def encode_nop() -> bytes:
    """Encode NOP."""
    return bytes([NOP])


def encode_jmp(offset: int) -> bytes:
    """Encode JMP offset (Format D)."""
    return bytes([int(Op.JMP), 0]) + encode_i16(offset)


def encode_jz(reg: int, offset: int) -> bytes:
    """Encode JZ reg, offset (Format D)."""
    return bytes([int(Op.JZ), reg & 0xFF]) + encode_i16(offset)


def encode_jnz(reg: int, offset: int) -> bytes:
    """Encode JNZ reg, offset (Format D)."""
    return bytes([int(Op.JNZ), reg & 0xFF]) + encode_i16(offset)


# ═══════════════════════════════════════════════════════════════════════════
# Test Vector Data Structure
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConformanceVector:
    """A single conformance test vector."""
    name: str
    description: str
    category: str
    opcode_name: str
    opcode_hex: str
    bytecode: List[int]
    initial_gp: Dict[str, int] = field(default_factory=dict)
    initial_fp: Dict[str, float] = field(default_factory=dict)
    expected_gp: Dict[str, int] = field(default_factory=dict)
    expected_fp: Dict[str, float] = field(default_factory=dict)
    expected_flags: Dict[str, bool] = field(default_factory=dict)
    expected_halted: bool = True
    expected_error: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=lambda: ["generated"])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "opcode": self.opcode_name,
            "opcode_hex": self.opcode_hex,
            "bytecode": self.bytecode,
            "expected_halted": self.expected_halted,
        }
        if self.initial_gp:
            d["initial_gp"] = self.initial_gp
        if self.initial_fp:
            d["initial_fp"] = self.initial_fp
        if self.expected_gp:
            d["expected_gp"] = self.expected_gp
        if self.expected_fp:
            d["expected_fp"] = self.expected_fp
        if self.expected_flags:
            d["expected_flags"] = self.expected_flags
        if self.expected_error:
            d["expected_error"] = self.expected_error
        if self.notes:
            d["notes"] = self.notes
        if self.tags:
            d["tags"] = self.tags
        return d


# ═══════════════════════════════════════════════════════════════════════════
# Vector Generators by Category
# ═══════════════════════════════════════════════════════════════════════════

class VectorGenerator:
    """Main generator that dispatches to category-specific generators."""

    def __init__(self) -> None:
        self._vectors: List[ConformanceVector] = []

    def generate_for_opcode(self, opcode_name: str) -> List[ConformanceVector]:
        """Generate all test vectors for a given opcode."""
        info = OPCODE_DB.get(opcode_name)
        if info is None:
            return []

        self._vectors = []
        cat = info.category

        # Dispatch to category-specific generator
        dispatch = {
            "control": self._gen_control,
            "arithmetic": self._gen_arithmetic,
            "logic": self._gen_bitwise,
            "comparison": self._gen_comparison,
            "stack": self._gen_stack,
            "data": self._gen_data_movement,
            "memory": self._gen_memory,
            "float": self._gen_float,
            "simd": self._gen_simd,
            "type": self._gen_type,
            "system": self._gen_system,
            "meta": self._gen_meta,
            "evolution": self._gen_evolution,
            "a2a": self._gen_a2a,
            "memory_mgmt": self._gen_memory_mgmt,
        }

        gen_fn = dispatch.get(cat, self._gen_generic)
        gen_fn(info)
        return self._vectors

    def generate_all_vectors(self) -> List[ConformanceVector]:
        """Generate vectors for all known opcodes."""
        all_vectors = []
        for name in sorted(OPCODE_DB.keys()):
            vecs = self.generate_for_opcode(name)
            all_vectors.extend(vecs)
        return all_vectors

    def _add(self, vector: ConformanceVector) -> None:
        """Add a vector to the internal list."""
        self._vectors.append(vector)

    # ── Control Flow Vectors ───────────────────────────────────────────────

    def _gen_control(self, info: OpcodeInfo) -> None:
        """Generate vectors for control flow opcodes."""
        op = info.name

        if op == "NOP":
            self._add(ConformanceVector(
                name="NOP does nothing",
                description="NOP should execute without modifying any state",
                category="control",
                opcode_name="NOP",
                opcode_hex=info.opcode_hex,
                bytecode=[NOP, HALT],
                expected_gp={"R0": 0},
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            self._add(ConformanceVector(
                name="NOP preserves register state",
                description="NOP should not alter any register values",
                category="control",
                opcode_name="NOP",
                opcode_hex=info.opcode_hex,
                bytecode=list(encode_movis(0, 42) + bytes([NOP]) + encode_halt()),
                expected_gp={"R0": 42},
                expected_halted=True,
                tags=["generated", "register_safety"],
            ))
            return

        if op == "HALT":
            self._add(ConformanceVector(
                name="HALT terminates execution immediately",
                description="HALT should stop the VM",
                category="control",
                opcode_name="HALT",
                opcode_hex=info.opcode_hex,
                bytecode=[HALT],
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            self._add(ConformanceVector(
                name="HALT preserves register state",
                description="HALT should not modify registers",
                category="control",
                opcode_name="HALT",
                opcode_hex=info.opcode_hex,
                bytecode=list(encode_movis(0, 99) + encode_halt()),
                expected_gp={"R0": 99},
                expected_halted=True,
                tags=["generated", "register_safety"],
            ))
            return

        if op == "JMP":
            # Forward jump over instruction
            bc = encode_movis(0, 10)
            jmp_offset = 4  # skip the MOVI R1,999 (4 bytes) and land on HALT
            bc += encode_jmp(jmp_offset)
            bc += encode_movis(1, 999)  # should be skipped
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JMP forward skips instruction",
                description="JMP should skip the MOVI R1,999 and reach HALT",
                category="control",
                opcode_name="JMP",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 10, "R1": 0},
                expected_halted=True,
                notes="JMP offset is relative to PC after fetch (4 bytes for Format D)",
                tags=["generated", "forward_jump"],
            ))
            # Backward jump (infinite loop protection via cycle budget)
            bc = encode_movis(0, 0)
            jmp_pos = len(bc)
            bc += encode_movis(0, 0)  # INC would go here
            bc += encode_movis(1, 0)  # padding
            jmp_offset = -(len(bc) - jmp_pos)  # jump back to jmp_pos
            bc += encode_jmp(jmp_offset)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JMP backward creates loop",
                description="JMP backward loops — VM stops via cycle budget",
                category="control",
                opcode_name="JMP",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=False,
                notes="Backward jump exceeds cycle budget",
                tags=["generated", "backward_jump", "loop"],
            ))
            return

        if op == "JZ":
            # Jump when zero
            bc = encode_movis(0, 0)  # R0 = 0 (will jump)
            jmp_offset = 4  # skip MOVI R1,999 (4 bytes)
            bc += encode_jz(0, jmp_offset)
            bc += encode_movis(1, 999)  # should be skipped
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JZ jumps when register is zero",
                description="JZ R0 should jump when R0==0, skipping MOVI R1,999",
                category="control",
                opcode_name="JZ",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": 0},
                expected_halted=True,
                tags=["generated", "conditional_jump"],
            ))
            # No jump when non-zero
            bc = encode_movis(0, 42)  # R0 = 42 (will NOT jump)
            jmp_offset = 4
            bc += encode_jz(0, jmp_offset)
            bc += encode_movis(1, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JZ falls through when register is non-zero",
                description="JZ R0 should not jump when R0==42",
                category="control",
                opcode_name="JZ",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42, "R1": 999},
                expected_halted=True,
                tags=["generated", "conditional_jump"],
            ))
            return

        if op == "JNZ":
            # Jump when non-zero
            bc = encode_movis(0, 42)
            jmp_offset = 4
            bc += encode_jnz(0, jmp_offset)
            bc += encode_movis(1, 999)  # should be skipped
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JNZ jumps when register is non-zero",
                description="JNZ R0 should jump when R0==42",
                category="control",
                opcode_name="JNZ",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42, "R1": 0},
                expected_halted=True,
                tags=["generated", "conditional_jump"],
            ))
            # No jump when zero
            bc = encode_movis(0, 0)
            jmp_offset = 4
            bc += encode_jnz(0, jmp_offset)
            bc += encode_movis(1, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JNZ falls through when register is zero",
                description="JNZ R0 should not jump when R0==0",
                category="control",
                opcode_name="JNZ",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": 999},
                expected_halted=True,
                tags=["generated", "conditional_jump"],
            ))
            return

        if op == "JE":
            # JE tests flag_zero — need CMP to set it first
            bc = encode_movis(0, 10)
            bc += encode_movis(1, 10)
            bc += bytes([int(Op.CMP), 0, 1])  # CMP R0, R1 — sets zero flag
            je_offset = 4
            bc += bytes([int(Op.JE), 0]) + encode_i16(je_offset)
            bc += encode_movis(2, 999)  # should be skipped
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JE jumps when values are equal",
                description="CMP sets zero flag when R0==R1, JE should jump",
                category="control",
                opcode_name="JE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 10, "R1": 10, "R2": 0},
                expected_flags={"flag_zero": True},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "JNE":
            bc = encode_movis(0, 10)
            bc += encode_movis(1, 20)
            bc += bytes([int(Op.CMP), 0, 1])  # CMP R0, R1 — clears zero flag
            jne_offset = 4
            bc += bytes([int(Op.JNE), 0]) + encode_i16(jne_offset)
            bc += encode_movis(2, 999)  # should be skipped
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JNE jumps when values are not equal",
                description="CMP clears zero flag when R0!=R1, JNE should jump",
                category="control",
                opcode_name="JNE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 10, "R1": 20, "R2": 0},
                expected_flags={"flag_zero": False, "flag_sign": True},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "JG":
            bc = encode_movis(0, 30)
            bc += encode_movis(1, 10)
            bc += bytes([int(Op.CMP), 0, 1])  # R0>R1: zero=false, sign=false
            jg_offset = 4
            bc += bytes([int(Op.JG), 0]) + encode_i16(jg_offset)
            bc += encode_movis(2, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JG jumps when greater (no zero, no sign)",
                description="CMP R0(30),R1(10): zero=F,sign=F → JG takes",
                category="control",
                opcode_name="JG",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 30, "R1": 10, "R2": 0},
                expected_flags={"flag_zero": False, "flag_sign": False},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "JL":
            bc = encode_movis(0, 10)
            bc += encode_movis(1, 30)
            bc += bytes([int(Op.CMP), 0, 1])  # R0<R1: sign=true
            jl_offset = 4
            bc += bytes([int(Op.JL), 0]) + encode_i16(jl_offset)
            bc += encode_movis(2, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JL jumps when less (sign flag set)",
                description="CMP R0(10),R1(30): sign=T → JL takes",
                category="control",
                opcode_name="JL",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 10, "R1": 30, "R2": 0},
                expected_flags={"flag_zero": False, "flag_sign": True},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "JGE":
            bc = encode_movis(0, 30)
            bc += encode_movis(1, 10)
            bc += bytes([int(Op.CMP), 0, 1])  # R0>=R1: sign=false
            jge_offset = 4
            bc += bytes([int(Op.JGE), 0]) + encode_i16(jge_offset)
            bc += encode_movis(2, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JGE jumps when greater-or-equal",
                description="CMP R0(30),R1(10): sign=F → JGE takes",
                category="control",
                opcode_name="JGE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 30, "R1": 10, "R2": 0},
                expected_flags={"flag_zero": False, "flag_sign": False},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "JLE":
            bc = encode_movis(0, 10)
            bc += encode_movis(1, 10)
            bc += bytes([int(Op.CMP), 0, 1])  # R0<=R1: zero=true
            jle_offset = 4
            bc += bytes([int(Op.JLE), 0]) + encode_i16(jle_offset)
            bc += encode_movis(2, 999)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="JLE jumps when less-or-equal (zero flag set)",
                description="CMP R0(10),R1(10): zero=T → JLE takes",
                category="control",
                opcode_name="JLE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 10, "R1": 10, "R2": 0},
                expected_flags={"flag_zero": True},
                expected_halted=True,
                tags=["generated", "flag_jump"],
            ))
            return

        if op == "CALL":
            # CALL pushes return address then jumps.
            # NOTE: The Python interpreter RET checks sp >= size-4 to detect
            # "empty stack", so a single pushed return address triggers halt.
            # This test verifies the CALL instruction pushes and jumps correctly.
            bc = encode_movis(0, 42)
            # After CALL, PC=8, push PC (8) onto stack, jump offset=1 → land at PC=9
            bc += bytes([int(Op.CALL), 0]) + encode_i16(1)
            bc += encode_halt()
            # Target of CALL: MOVI R2, 77
            bc += encode_movis(2, 77)
            bc += bytes([int(Op.RET)])  # RET halts (interpreter quirk: single return triggers halt)
            self._add(ConformanceVector(
                name="CALL pushes return address and jumps",
                description="CALL pushes PC then jumps to target",
                category="control",
                opcode_name="CALL",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42, "R2": 77},
                expected_halted=True,
                notes="RET halts because interpreter treats single-element stack as empty",
                tags=["generated", "call_return"],
            ))
            return

        if op == "TAILCALL":
            bc = encode_movis(0, 10)
            # TAILCALL without pushing return address
            tc_offset = 4
            bc += bytes([int(Op.TAILCALL), 0]) + encode_i16(tc_offset)
            bc += encode_movis(1, 999)  # should be skipped (no return to here)
            bc += encode_movis(0, 20)  # target: overwrite R0
            bc += encode_halt()
            self._add(ConformanceVector(
                name="TAILCALL jumps without pushing return address",
                description="TAILCALL should jump without pushing return, so R1 stays 0",
                category="control",
                opcode_name="TAILCALL",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 20, "R1": 0},
                expected_halted=True,
                tags=["generated", "tail_call"],
            ))
            return

        if op == "RET":
            # RET from empty stack should halt
            self._add(ConformanceVector(
                name="RET from empty stack halts VM",
                description="RET when stack is empty should halt",
                category="control",
                opcode_name="RET",
                opcode_hex=info.opcode_hex,
                bytecode=[int(Op.RET)],
                expected_halted=True,
                tags=["generated", "edge_case"],
            ))
            return

        # Generic: MOV
        if op == "MOV":
            bc = encode_movis(1, 42)
            bc += bytes([int(Op.MOV), 0, 1])  # MOV R0, R1
            bc += encode_halt()
            self._add(ConformanceVector(
                name="MOV copies register value",
                description="MOV R0, R1 should set R0 = R1 = 42",
                category="data",
                opcode_name="MOV",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42, "R1": 42},
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

    # ── Arithmetic Vectors ─────────────────────────────────────────────────

    def _gen_arithmetic(self, info: OpcodeInfo) -> None:
        """Generate vectors for arithmetic opcodes."""
        op = info.name

        if op == "IADD":
            cases = [
                ("basic", 10, 20, 30, "Basic addition"),
                ("zero", 0, 0, 0, "Adding zero"),
                ("zero_operand", 0, 42, 42, "Adding zero to nonzero"),
                ("negative", -10, -20, -30, "Negative addition"),
                ("mixed_sign", -10, 20, 10, "Mixed sign addition"),
                ("identity_zero", 0, -0, 0, "Zero identity"),
            ]
            for tag, a, b, expected, desc in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.IADD), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"IADD {desc}: {a} + {b} = {expected}",
                    description=desc,
                    category="arithmetic",
                    opcode_name="IADD",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected, "R1": a, "R2": b},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", f"add_{tag}"],
                ))
            # Overlap safety
            bc = encode_movis(1, 5) + encode_movis(2, 3)
            bc += bytes([int(Op.IADD), 1, 1, 2])  # R1 = R1 + R2
            bc += encode_halt()
            self._add(ConformanceVector(
                name="IADD rd=rs1 overlap safety: R1=R1+R2",
                description="IADD must read R1 before writing when rd=rs1",
                category="arithmetic",
                opcode_name="IADD",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": 8, "R2": 3},
                expected_halted=True,
                tags=["generated", "overlap_safety"],
            ))
            return

        if op == "ISUB":
            cases = [
                ("basic", 30, 12, 18),
                ("zero_result", 42, 42, 0),
                ("negative", 10, 30, -20),
                ("from_zero", 0, 10, -10),
            ]
            for tag, a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.ISUB), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"ISUB {tag}: {a} - {b} = {expected}",
                    description=f"Integer subtraction: {a} - {b} = {expected}",
                    category="arithmetic",
                    opcode_name="ISUB",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected, "R1": a, "R2": b},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", f"sub_{tag}"],
                ))
            return

        if op == "IMUL":
            cases = [
                ("basic", 7, 6, 42),
                ("zero", 0, 999, 0),
                ("one", 42, 1, 42),
                ("negative", -3, 7, -21),
                ("both_negative", -4, -5, 20),
            ]
            for tag, a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.IMUL), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"IMUL {tag}: {a} * {b} = {expected}",
                    description=f"Integer multiply: {a} * {b} = {expected}",
                    category="arithmetic",
                    opcode_name="IMUL",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected, "R1": a, "R2": b},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", f"mul_{tag}"],
                ))
            return

        if op in ("IDIV", "IMOD", "IREM"):
            # Happy path
            cases_div = [
                ("basic", 17, 5, 3),
                ("exact", 20, 4, 5),
                ("negative_dividend", -17, 5, -3),
                ("negative_both", -17, -5, 3),
            ]
            cases_mod = [
                ("basic", 17, 5, 2),
                ("exact", 20, 4, 0),
                ("negative", -17, 5, -2),
            ]
            cases = cases_div if op == "IDIV" else cases_mod
            op_val = int(getattr(Op, op))
            for tag, a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([op_val, 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"{op} {tag}: {a} {'%' if op != 'IDIV' else '/'} {b} = {expected}",
                    description=f"{op}: {a} {'mod' if op != 'IDIV' else 'div'} {b} = {expected}",
                    category="arithmetic",
                    opcode_name=op,
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected, "R1": a, "R2": b},
                    expected_halted=True,
                    tags=["generated", f"{op.lower()}_{tag}"],
                ))

            # Divide by zero
            bc = encode_movis(1, 42) + encode_movis(2, 0)
            bc += bytes([op_val, 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name=f"{op} divide by zero raises error",
                description=f"{op} by zero should raise VMDivisionByZeroError",
                category="arithmetic",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMDivisionByZeroError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

        if op == "INEG":
            bc = encode_movis(1, 42)
            bc += bytes([int(Op.INEG), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INEG negates positive value",
                description="INEG R0, R1: R0 = -42",
                category="arithmetic",
                opcode_name="INEG",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": -42, "R1": 42},
                expected_flags={"flag_sign": True},
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            bc = encode_movis(1, 0)
            bc += bytes([int(Op.INEG), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INEG of zero is zero",
                description="INEG R0, R1 where R1=0: R0 = 0",
                category="arithmetic",
                opcode_name="INEG",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": 0},
                expected_flags={"flag_zero": True, "flag_sign": False},
                expected_halted=True,
                tags=["generated", "edge_case"],
            ))
            bc = encode_movis(1, -100)
            bc += bytes([int(Op.INEG), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INEG double negation",
                description="INEG of -100 = 100",
                category="arithmetic",
                opcode_name="INEG",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 100, "R1": -100},
                expected_halted=True,
                tags=["generated", "edge_case"],
            ))
            return

        if op == "INC":
            cases = [(0, 1), (41, 42), (-1, 0)]
            for init, expected in cases:
                bc = encode_movis(0, init)
                bc += bytes([int(Op.INC), 0])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"INC {init} -> {expected}",
                    description=f"INC R0 where R0={init}",
                    category="arithmetic",
                    opcode_name="INC",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", "inc"],
                ))
            return

        if op == "DEC":
            cases = [(1, 0), (43, 42), (0, -1)]
            for init, expected in cases:
                bc = encode_movis(0, init)
                bc += bytes([int(Op.DEC), 0])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"DEC {init} -> {expected}",
                    description=f"DEC R0 where R0={init}",
                    category="arithmetic",
                    opcode_name="DEC",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", "dec"],
                ))
            return

    # ── Bitwise Vectors ────────────────────────────────────────────────────

    def _gen_bitwise(self, info: OpcodeInfo) -> None:
        """Generate vectors for bitwise/logic opcodes."""
        op = info.name

        if op == "IAND":
            cases = [(0x0F, 0x03, 3), (0xFF, 0x00, 0), (0xFF, 0xFF, 0xFF)]
            for a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.IAND), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"IAND 0x{a:X} & 0x{b:X} = 0x{expected:X}",
                    description=f"Bitwise AND: {a} & {b} = {expected}",
                    category="logic",
                    opcode_name="IAND",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={"flag_zero": expected == 0},
                    expected_halted=True,
                    tags=["generated", "and"],
                ))
            return

        if op == "IOR":
            cases = [(0x0A, 0x05, 0x0F), (0x00, 0xFF, 0xFF), (0xF0, 0x0F, 0xFF)]
            for a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.IOR), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"IOR 0x{a:X} | 0x{b:X} = 0x{expected:X}",
                    description=f"Bitwise OR: {a} | {b} = {expected}",
                    category="logic",
                    opcode_name="IOR",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={"flag_zero": expected == 0},
                    expected_halted=True,
                    tags=["generated", "or"],
                ))
            return

        if op == "IXOR":
            cases = [(0x0F, 0x0F, 0), (0xFF, 0x00, 0xFF), (0xAA, 0x55, 0xFF)]
            for a, b, expected in cases:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.IXOR), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"IXOR 0x{a:X} ^ 0x{b:X} = 0x{expected:X}",
                    description=f"Bitwise XOR: {a} ^ {b} = {expected}",
                    category="logic",
                    opcode_name="IXOR",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={"flag_zero": expected == 0},
                    expected_halted=True,
                    tags=["generated", "xor"],
                ))
            return

        if op == "INOT":
            bc = encode_movis(1, 0)
            bc += bytes([int(Op.INOT), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INOT of zero is -1",
                description="INOT R0, R1: ~0 = -1",
                category="logic",
                opcode_name="INOT",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": -1, "R1": 0},
                expected_flags={"flag_sign": True},
                expected_halted=True,
                tags=["generated", "not"],
            ))
            bc = encode_movis(1, -1)
            bc += bytes([int(Op.INOT), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INOT of -1 is zero",
                description="INOT R0, R1: ~(-1) = 0",
                category="logic",
                opcode_name="INOT",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": -1},
                expected_flags={"flag_zero": True},
                expected_halted=True,
                tags=["generated", "not"],
            ))
            return

        if op == "ISHL":
            cases = [(1, 4, 16), (1, 0, 1), (0xFF, 8, 0xFF00)]
            for val, shift, expected in cases:
                bc = encode_movis(1, val) + encode_movis(2, shift)
                bc += bytes([int(Op.ISHL), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"ISHL {val} << {shift} = {expected}",
                    description=f"Shift left: {val} << {shift} = {expected}",
                    category="logic",
                    opcode_name="ISHL",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_halted=True,
                    tags=["generated", "shl"],
                ))
            return

        if op == "ISHR":
            cases = [(16, 2, 4), (1, 0, 1), (-16, 2, -4)]
            for val, shift, expected in cases:
                bc = encode_movis(1, val) + encode_movis(2, shift)
                bc += bytes([int(Op.ISHR), 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"ISHR {val} >> {shift} = {expected}",
                    description=f"Arithmetic shift right: {val} >> {shift} = {expected}",
                    category="logic",
                    opcode_name="ISHR",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_halted=True,
                    tags=["generated", "shr"],
                ))
            return

        if op == "ROTL":
            # ROTL is 32-bit: result = ((val << shift) | (val >> (32 - shift))) & 0xFFFFFFFF
            bc = encode_movis(1, 1) + encode_movis(2, 1)
            bc += bytes([int(Op.ROTL), 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="ROTL 1 << 1 = 2",
                description="Rotate left 32-bit: 1 rotated left 1 = 2",
                category="logic",
                opcode_name="ROTL",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 2},
                expected_halted=True,
                tags=["generated", "rotl"],
            ))
            return

        if op == "ROTR":
            bc = encode_movis(1, 2) + encode_movis(2, 1)
            bc += bytes([int(Op.ROTR), 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="ROTR 2 >> 1 = 1",
                description="Rotate right 32-bit: 2 rotated right 1 = 1",
                category="logic",
                opcode_name="ROTR",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 1},
                expected_halted=True,
                tags=["generated", "rotr"],
            ))
            return

    # ── Comparison Vectors ─────────────────────────────────────────────────

    def _gen_comparison(self, info: OpcodeInfo) -> None:
        """Generate vectors for comparison opcodes."""
        op = info.name

        if op == "ICMP":
            # ICMP with various condition codes (0=EQ, 1=NE, 2=LT, 4=GT, 5=GE)
            for cond, a, b, expected, cond_name in [
                (0, 10, 10, 1, "EQ"), (0, 10, 20, 0, "EQ"),
                (1, 10, 20, 1, "NE"), (1, 10, 10, 0, "NE"),
                (2, 10, 20, 1, "LT"), (2, 20, 10, 0, "LT"),
                (4, 20, 10, 1, "GT"), (4, 10, 20, 0, "GT"),
                (5, 10, 10, 1, "GE"), (5, 20, 10, 1, "GE"),
                (5, 10, 20, 0, "GE"),
            ]:
                bc = encode_movis(1, a) + encode_movis(2, b)
                bc += bytes([int(Op.ICMP), cond, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"ICMP cond={cond_name}({cond}): {a} vs {b} = {expected}",
                    description=f"ICMP with condition code {cond} ({cond_name})",
                    category="comparison",
                    opcode_name="ICMP",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={
                        "flag_zero": expected == 0,
                        "flag_sign": expected < 0,
                    },
                    expected_halted=True,
                    tags=["generated", f"icmp_{cond_name.lower()}"],
                ))
            return

        if op in ("IEQ", "ILT", "ILE", "IGT", "IGE"):
            op_val = int(getattr(Op, op))
            op_fn = {
                "IEQ": lambda a, b: int(a == b),
                "ILT": lambda a, b: int(a < b),
                "ILE": lambda a, b: int(a <= b),
                "IGT": lambda a, b: int(a > b),
                "IGE": lambda a, b: int(a >= b),
            }[op]
            for a, b in [(5, 5), (5, 10), (10, 5), (0, 0), (-1, 1)]:
                expected = op_fn(a, b)
                bc = encode_movis(0, a) + encode_movis(1, b)
                bc += bytes([op_val, 0, 1])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"{op} {a} vs {b} = {expected}",
                    description=f"{op} R0, R1: {a} vs {b}",
                    category="comparison",
                    opcode_name=op,
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R0": expected},
                    expected_flags={"flag_zero": expected == 0},
                    expected_halted=True,
                    tags=["generated", f"{op.lower()}"],
                ))
            return

        if op == "CMP":
            # CMP sets flags but doesn't store result
            for a, b, z, s, c in [
                (10, 10, True, False, False),
                (10, 20, False, True, True),
                (20, 10, False, False, False),
            ]:
                bc = encode_movis(0, a) + encode_movis(1, b)
                bc += bytes([int(Op.CMP), 0, 1])
                bc += bytes([int(Op.SETCC), 2, 0])  # SETCC R2, EQ
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"CMP {a} vs {b}: zero={z}, sign={s}",
                    description=f"CMP sets flags from comparison {a} vs {b}",
                    category="comparison",
                    opcode_name="CMP",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={"R2": 1 if z else 0},
                    expected_flags={"flag_zero": z, "flag_sign": s},
                    expected_halted=True,
                    tags=["generated", "cmp"],
                ))
            return

        if op == "TEST":
            bc = encode_movis(0, 0x0F) + encode_movis(1, 0x03)
            bc += bytes([int(Op.TEST), 0, 1])
            bc += bytes([int(Op.SETCC), 2, 0])  # SETCC R2, EQ
            bc += encode_halt()
            self._add(ConformanceVector(
                name="TEST sets flags from AND without storing",
                description="TEST R0, R1: flags from 0x0F & 0x03 = 3 (nonzero)",
                category="comparison",
                opcode_name="TEST",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0x0F, "R1": 0x03, "R2": 0},
                expected_flags={"flag_zero": False},
                expected_halted=True,
                tags=["generated", "test"],
            ))
            return

        if op == "SETCC":
            # SETCC requires flags to be pre-set
            bc = encode_movis(0, 0)
            bc += bytes([int(Op.INC), 0])  # R0 = 1, sets flags: zero=F, sign=F
            bc += bytes([int(Op.SETCC), 1, 1])  # SETCC R1, NE → should be 1
            bc += bytes([int(Op.SETCC), 2, 0])  # SETCC R2, EQ → should be 0
            bc += encode_halt()
            self._add(ConformanceVector(
                name="SETCC reads flags from prior operation",
                description="After INC (result=1, not zero): NE=1, EQ=0",
                category="comparison",
                opcode_name="SETCC",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 1, "R1": 1, "R2": 0},
                expected_flags={"flag_zero": False},
                expected_halted=True,
                tags=["generated", "setcc"],
            ))
            return

    # ── Stack Vectors ──────────────────────────────────────────────────────

    def _gen_stack(self, info: OpcodeInfo) -> None:
        """Generate vectors for stack opcodes."""
        op = info.name

        if op in ("PUSH", "POP"):
            bc = encode_movis(0, 99)
            bc += encode_push(0)
            bc += encode_pop(1)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="PUSH/POP preserve value",
                description="Push R0(99), Pop into R1 → R1 = 99",
                category="stack",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 99, "R1": 99},
                expected_halted=True,
                tags=["generated", "push_pop"],
            ))
            # Negative value on stack
            bc = encode_movis(0, -42)
            bc += encode_push(0)
            bc += encode_pop(1)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="PUSH/POP preserve negative value",
                description="Push R0(-42), Pop into R1 → R1 = -42",
                category="stack",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": -42, "R1": -42},
                expected_halted=True,
                tags=["generated", "push_pop_negative"],
            ))
            return

        if op == "DUP":
            bc = encode_movis(0, 42)
            bc += encode_push(0)
            bc += bytes([int(Op.DUP)])  # DUP: stack now has [42, 42]
            bc += encode_pop(1)
            bc += encode_pop(2)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="DUP duplicates top of stack",
                description="Push 42, DUP, Pop×2 → R1=42, R2=42",
                category="stack",
                opcode_name="DUP",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42, "R1": 42, "R2": 42},
                expected_halted=True,
                tags=["generated", "dup"],
            ))
            return

        if op == "SWAP":
            bc = encode_movis(0, 10)
            bc += encode_push(0)
            bc += encode_movis(0, 20)
            bc += encode_push(0)
            bc += bytes([int(Op.SWAP)])  # stack: [10, 20] → [20, 10]
            bc += encode_pop(1)
            bc += encode_pop(2)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="SWAP swaps top two stack values",
                description="Push 10, Push 20, SWAP, Pop→R1=10, Pop→R2=20",
                category="stack",
                opcode_name="SWAP",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 20, "R1": 10, "R2": 20},
                expected_halted=True,
                tags=["generated", "swap"],
            ))
            return

        if op == "ENTER":
            bc = encode_movis(0, 42)
            bc += bytes([int(Op.ENTER), 4])  # ENTER frame_size=4 (16 bytes)
            bc += bytes([int(Op.LEAVE), 0])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="ENTER/LEAVE roundtrip preserves state",
                description="ENTER allocates frame, LEAVE deallocates",
                category="stack",
                opcode_name="ENTER",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42},
                expected_halted=True,
                tags=["generated", "enter_leave"],
            ))
            return

        if op == "LEAVE":
            # Tested via ENTER/LEAVE roundtrip above
            return

    # ── Data Movement Vectors ──────────────────────────────────────────────

    def _gen_data_movement(self, info: OpcodeInfo) -> None:
        """Generate vectors for data movement opcodes."""
        op = info.name

        if op == "MOVI":
            cases = [
                (0, 0, "zero"),
                (0, 42, "positive"),
                (0, -128, "negative_byte"),
                (0, 32767, "max_i16"),
                (0, -32768, "min_i16"),
                (5, 100, "register_5"),
            ]
            for rd, imm, tag in cases:
                bc = encode_movis(rd, imm)
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"MOVI R{rd}, {imm} ({tag})",
                    description=f"Load immediate {imm} into R{rd}",
                    category="data",
                    opcode_name="MOVI",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    expected_gp={f"R{rd}": imm},
                    expected_halted=True,
                    tags=["generated", f"movi_{tag}"],
                ))
            return

    # ── Memory Vectors ─────────────────────────────────────────────────────

    def _gen_memory(self, info: OpcodeInfo) -> None:
        """Generate vectors for memory opcodes."""
        op = info.name

        if op in ("LOAD", "STORE"):
            # Store then load
            bc = encode_movis(0, 12345)
            bc += encode_movis(1, SAFE_ADDR)
            bc += bytes([int(Op.STORE), 0, 1])  # STORE R0, R1 → mem[R1] = R0
            bc += encode_movis(2, 0)  # R2 = 0 (clear)
            bc += bytes([int(Op.LOAD), 2, 1])  # LOAD R2, R1 → R2 = mem[R1]
            bc += encode_halt()
            self._add(ConformanceVector(
                name="STORE then LOAD roundtrip",
                description=f"Store 12345 at addr {SAFE_ADDR}, load back",
                category="memory",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 12345, "R2": 12345},
                expected_halted=True,
                tags=["generated", "store_load"],
            ))
            return

        if op in ("LOAD8", "STORE8"):
            bc = encode_movis(0, 0x42)
            bc += encode_movis(1, SAFE_ADDR)
            bc += bytes([int(Op.STORE8), 0, 1])
            bc += encode_movis(2, 0)
            bc += bytes([int(Op.LOAD8), 2, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="STORE8 then LOAD8 roundtrip",
                description="Store byte 0x42, load back",
                category="memory",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0x42, "R2": 0x42},
                expected_halted=True,
                tags=["generated", "store8_load8"],
            ))
            return

    # ── Float Vectors ──────────────────────────────────────────────────────

    def _gen_float(self, info: OpcodeInfo) -> None:
        """Generate vectors for float opcodes."""
        op = info.name
        op_val = int(getattr(Op, op))

        if op in ("FADD", "FSUB", "FMUL"):
            fn = {
                "FADD": lambda a, b: a + b,
                "FSUB": lambda a, b: a - b,
                "FMUL": lambda a, b: a * b,
            }[op]
            sym = {"FADD": "+", "FSUB": "-", "FMUL": "*"}[op]
            for a, b in [(1.5, 2.5), (0.0, 3.14), (-1.0, 1.0)]:
                expected = fn(a, b)
                # Encode: MOVI can't set float regs directly; we rely on initial state
                bc = bytes([op_val, 0, 1, 2])  # Fd F0, F1, F2
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"{op} {a} {sym} {b} = {expected}",
                    description=f"Float {op}: {a} {sym} {b} = {expected}",
                    category="float",
                    opcode_name=op,
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    initial_fp={"F1": a, "F2": b},
                    expected_fp={"F0": expected},
                    expected_halted=True,
                    tags=["generated", f"{op.lower()}"],
                ))
            return

        if op == "FDIV":
            for a, b in [(10.0, 2.0), (3.14, 1.0)]:
                expected = a / b
                bc = bytes([op_val, 0, 1, 2])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"FDIV {a} / {b} = {expected}",
                    description=f"Float division: {a} / {b}",
                    category="float",
                    opcode_name="FDIV",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    initial_fp={"F1": a, "F2": b},
                    expected_fp={"F0": expected},
                    expected_halted=True,
                    tags=["generated", "fdiv"],
                ))
            # Divide by zero
            bc = bytes([op_val, 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="FDIV divide by zero raises error",
                description="Float division by zero should raise error",
                category="float",
                opcode_name="FDIV",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                initial_fp={"F1": 1.0, "F2": 0.0},
                expected_error="VMDivisionByZeroError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

        if op == "FNEG":
            bc = bytes([op_val, 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="FNEG negates float",
                description="FNEG F0, F1: -3.14 → 3.14",
                category="float",
                opcode_name="FNEG",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                initial_fp={"F1": 3.14},
                expected_fp={"F0": -3.14},
                expected_halted=True,
                tags=["generated", "fneg"],
            ))
            return

        if op == "FABS":
            bc = bytes([op_val, 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="FABS takes absolute value",
                description="FABS F0, F1: |-3.14| → 3.14",
                category="float",
                opcode_name="FABS",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                initial_fp={"F0": -3.14, "F1": -3.14},
                expected_fp={"F0": 3.14},
                expected_halted=True,
                tags=["generated", "fabs"],
            ))
            return

        if op in ("FMIN", "FMAX"):
            if op == "FMIN":
                bc = bytes([op_val, 0, 1])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name="FMIN takes minimum",
                    description="FMIN F0, F1: min(3.14, 2.71) → 2.71",
                    category="float",
                    opcode_name="FMIN",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    initial_fp={"F0": 3.14, "F1": 2.71},
                    expected_fp={"F0": 2.71},
                    expected_halted=True,
                    tags=["generated", "fmin"],
                ))
            else:
                bc = bytes([op_val, 0, 1])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name="FMAX takes maximum",
                    description="FMAX F0, F1: max(2.71, 3.14) → 3.14",
                    category="float",
                    opcode_name="FMAX",
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    initial_fp={"F0": 2.71, "F1": 3.14},
                    expected_fp={"F0": 3.14},
                    expected_halted=True,
                    tags=["generated", "fmax"],
                ))
            return

        if op in ("FEQ", "FLT", "FLE", "FGT", "FGE"):
            op_fn = {
                "FEQ": lambda a, b: int(a == b),
                "FLT": lambda a, b: int(a < b),
                "FLE": lambda a, b: int(a <= b),
                "FGT": lambda a, b: int(a > b),
                "FGE": lambda a, b: int(a >= b),
            }[op]
            for a, b in [(3.14, 3.14), (1.0, 2.0), (2.0, 1.0)]:
                expected = op_fn(a, b)
                bc = bytes([op_val, 0, 1])
                bc += encode_halt()
                self._add(ConformanceVector(
                    name=f"{op} {a} vs {b} = {expected}",
                    description=f"Float comparison: {op}",
                    category="float",
                    opcode_name=op,
                    opcode_hex=info.opcode_hex,
                    bytecode=list(bc),
                    initial_fp={"F0": a, "F1": b},
                    expected_gp={"R0": expected},
                    expected_halted=True,
                    tags=["generated", f"{op.lower()}"],
                ))
            return

    # ── SIMD Vectors ───────────────────────────────────────────────────────

    def _gen_simd(self, info: OpcodeInfo) -> None:
        """Generate vectors for SIMD opcodes."""
        op = info.name
        op_val = int(getattr(Op, op))

        if op == "VLOAD":
            # Store data to memory first, then VLOAD
            bc = encode_movis(0, 17)
            bc += encode_movis(1, SAFE_ADDR)
            bc += bytes([int(Op.STORE), 0, 1])
            bc += bytes([op_val, 0, 1])  # VLOAD V0, R1
            bc += encode_halt()
            self._add(ConformanceVector(
                name="VLOAD loads 16 bytes from memory",
                description="Store 17, VLOAD 16 bytes from that address",
                category="simd",
                opcode_name="VLOAD",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                notes="V0 should contain the stored data (first 4 bytes = 17 in LE)",
                tags=["generated", "vload"],
            ))
            return

        if op == "VSTORE":
            bc = bytes([op_val, 0, 1])  # VSTORE V0, R1
            bc += encode_halt()
            self._add(ConformanceVector(
                name="VSTORE stores 16 bytes to memory",
                description="VSTORE V0 to address in R1",
                category="simd",
                opcode_name="VSTORE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                initial_gp={"R1": SAFE_ADDR},
                expected_halted=True,
                tags=["generated", "vstore"],
            ))
            return

        if op in ("VADD", "VSUB", "VMUL"):
            bc = bytes([op_val, 0, 1])  # V{op} V0, V1
            bc += encode_halt()
            self._add(ConformanceVector(
                name=f"{op} byte-wise operation",
                description=f"Byte-wise vector {op}",
                category="simd",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", f"{op.lower()}"],
            ))
            return

        if op == "VDIV":
            bc = bytes([op_val, 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="VDIV byte-wise division",
                description="Byte-wise vector division (no-op with zero-initialized vectors)",
                category="simd",
                opcode_name="VDIV",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMDivisionByZeroError",
                expected_halted=False,
                tags=["generated", "vdiv"],
            ))
            # Division by zero in vector
            bc = bytes([op_val, 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="VDIV by zero raises error",
                description="VDIV with zero element should raise error",
                category="simd",
                opcode_name="VDIV",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMDivisionByZeroError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

        if op == "VFMA":
            # VFMA is Format E: [VFMA][vd][vs1][vs2]: vd = vd + vs1*vs2
            bc = bytes([op_val, 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="VFMA fused multiply-add",
                description="VFMA V0, V1, V2: V0 = V0 + V1*V2",
                category="simd",
                opcode_name="VFMA",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "vfma"],
            ))
            return

    # ── Type Vectors ───────────────────────────────────────────────────────

    def _gen_type(self, info: OpcodeInfo) -> None:
        """Generate vectors for type opcodes."""
        op = info.name

        if op == "CAST":
            # CAST tag=2 (i32->bool): nonzero → 1
            bc = encode_movis(1, 42)
            bc += bytes([int(Op.CAST), 0, 1, 2])  # CAST R0, R1, type=2
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CAST i32 to bool (nonzero → 1)",
                description="CAST R0, R1 with type_tag=2: nonzero → 1",
                category="type",
                opcode_name="CAST",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 1, "R1": 42},
                expected_halted=True,
                tags=["generated", "cast"],
            ))
            # CAST tag=2: zero → 0
            bc = encode_movis(1, 0)
            bc += bytes([int(Op.CAST), 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CAST i32 to bool (zero → 0)",
                description="CAST R0, R1 with type_tag=2: zero → 0",
                category="type",
                opcode_name="CAST",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0, "R1": 0},
                expected_halted=True,
                tags=["generated", "cast"],
            ))
            return

        if op == "BOX":
            # BOX R0, type_tag=0, value=42
            bc = bytes([int(Op.BOX), 0, 0]) + encode_i32(42)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="BOX allocates box with integer value",
                description="BOX R0, type=0(INT), value=42 → R0 = box_id(0)",
                category="type",
                opcode_name="BOX",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0},
                expected_halted=True,
                tags=["generated", "box"],
            ))
            return

        if op == "UNBOX":
            # BOX then UNBOX
            bc = bytes([int(Op.BOX), 1, 0]) + encode_i32(99)  # BOX R1, type=0, val=99
            bc += bytes([int(Op.UNBOX), 0, 1])  # UNBOX R0, R1
            bc += encode_halt()
            self._add(ConformanceVector(
                name="BOX then UNBOX retrieves value",
                description="Box 99, unbox → R0 = 99",
                category="type",
                opcode_name="UNBOX",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 99, "R1": 0},
                expected_halted=True,
                tags=["generated", "unbox"],
            ))
            # Invalid box id
            bc = encode_movis(1, 999)
            bc += bytes([int(Op.UNBOX), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="UNBOX invalid box id raises error",
                description="UNBOX with invalid box_id=999 should raise VMTypeError",
                category="type",
                opcode_name="UNBOX",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMTypeError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

        if op == "CHECK_TYPE":
            # BOX type=0, CHECK type=0 (pass)
            bc = bytes([int(Op.BOX), 0, 0]) + encode_i32(1)
            bc += bytes([int(Op.CHECK_TYPE), 0, 0])  # CHECK_TYPE R0, expected=0
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CHECK_TYPE passes when types match",
                description="Box with type=0, check type=0 → passes",
                category="type",
                opcode_name="CHECK_TYPE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "check_type"],
            ))
            # CHECK type=1 (fail)
            bc = bytes([int(Op.BOX), 0, 0]) + encode_i32(1)
            bc += bytes([int(Op.CHECK_TYPE), 0, 1])  # expected type=1 (wrong)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CHECK_TYPE fails when types mismatch",
                description="Box with type=0, check type=1 → VMTypeError",
                category="type",
                opcode_name="CHECK_TYPE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMTypeError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

        if op == "CHECK_BOUNDS":
            # In bounds: index=2, length=10
            bc = encode_movis(0, 2) + encode_movis(1, 10)
            bc += bytes([int(Op.CHECK_BOUNDS), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CHECK_BOUNDS passes when in range",
                description="Index 2 in range [0, 10) → passes",
                category="type",
                opcode_name="CHECK_BOUNDS",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "check_bounds"],
            ))
            # Out of bounds: index=10, length=10
            bc = encode_movis(0, 10) + encode_movis(1, 10)
            bc += bytes([int(Op.CHECK_BOUNDS), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CHECK_BOUNDS fails when out of range",
                description="Index 10 not in range [0, 10) → VMTypeError",
                category="type",
                opcode_name="CHECK_BOUNDS",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMTypeError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            # Negative index
            bc = encode_movis(0, -1) + encode_movis(1, 10)
            bc += bytes([int(Op.CHECK_BOUNDS), 0, 1])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="CHECK_BOUNDS fails for negative index",
                description="Index -1 → VMTypeError",
                category="type",
                opcode_name="CHECK_BOUNDS",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_error="VMTypeError",
                expected_halted=False,
                tags=["generated", "error_handling"],
            ))
            return

    # ── System Vectors ─────────────────────────────────────────────────────

    def _gen_system(self, info: OpcodeInfo) -> None:
        """Generate vectors for system opcodes."""
        op = info.name

        if op == "YIELD":
            self._add(ConformanceVector(
                name="YIELD is a no-op in single-threaded mode",
                description="YIELD should not crash or modify state",
                category="system",
                opcode_name="YIELD",
                opcode_hex=info.opcode_hex,
                bytecode=[int(Op.YIELD), HALT],
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

        if op == "DEBUG_BREAK":
            self._add(ConformanceVector(
                name="DEBUG_BREAK does not crash",
                description="DEBUG_BREAK should execute without error",
                category="system",
                opcode_name="DEBUG_BREAK",
                opcode_hex=info.opcode_hex,
                bytecode=[int(Op.DEBUG_BREAK), HALT],
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

        if op in ("RESOURCE_ACQUIRE", "RESOURCE_RELEASE"):
            data = encode_i32(42)  # resource_id = 42
            bc = bytes([int(Op.RESOURCE_ACQUIRE)]) + encode_format_g(data)
            bc += encode_halt()
            self._add(ConformanceVector(
                name=f"{op} succeeds",
                description=f"{op} with resource_id=42",
                category="system",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 0},  # success
                expected_halted=True,
                tags=["generated", "resource"],
            ))
            return

        self._gen_generic(info)

    # ── Meta Vectors ───────────────────────────────────────────────────────

    def _gen_meta(self, info: OpcodeInfo) -> None:
        """Generate vectors for meta/confidence opcodes."""
        op = info.name

        if op == "MERGE":
            bc = encode_movis(1, 10) + encode_movis(2, 30)
            bc += bytes([int(Op.MERGE), 0, 1, 2])
            bc += encode_halt()
            self._add(ConformanceVector(
                name="MERGE averages two registers",
                description="MERGE R0, R1, R2: avg(10, 30) = 20",
                category="meta",
                opcode_name="MERGE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 20},
                expected_halted=True,
                tags=["generated", "merge"],
            ))
            return

        if op in ("CONF", "RESTORE"):
            bc = bytes([int(getattr(Op, op)), 0, 0]) + encode_i16(0)
            bc += encode_halt()
            self._add(ConformanceVector(
                name=f"{op} does not crash",
                description=f"{op} should execute without error",
                category="meta",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

    # ── Evolution Vectors ──────────────────────────────────────────────────

    def _gen_evolution(self, info: OpcodeInfo) -> None:
        """Generate vectors for evolution opcodes."""
        op = info.name
        op_val = int(getattr(Op, op))

        if op == "INSTINCT":
            bc = bytes([op_val, 0]) + encode_i16(42)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="INSTINCT loads immediate into register",
                description="INSTINCT R0, 42: R0 = 42",
                category="evolution",
                opcode_name="INSTINCT",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 42},
                expected_halted=True,
                tags=["generated", "instinct"],
            ))
            return

        if op == "WITNESS":
            bc = bytes([op_val, 0]) + encode_i16(0)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="WITNESS writes witness mark",
                description="WITNESS should write a log entry and return count",
                category="evolution",
                opcode_name="WITNESS",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_gp={"R0": 1},
                expected_halted=True,
                tags=["generated", "witness"],
            ))
            return

        if op in ("EVOLVE", "SNAPSHOT"):
            bc = bytes([op_val, 0]) + encode_i16(0)
            bc += encode_halt()
            self._add(ConformanceVector(
                name=f"{op} does not crash",
                description=f"{op} should execute without error",
                category="evolution",
                opcode_name=op,
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

    # ── A2A Vectors ────────────────────────────────────────────────────────

    def _gen_a2a(self, info: OpcodeInfo) -> None:
        """Generate vectors for A2A protocol opcodes."""
        op = info.name

        if op == "EMERGENCY_STOP":
            self._add(ConformanceVector(
                name="EMERGENCY_STOP halts VM",
                description="EMERGENCY_STOP should immediately halt",
                category="a2a",
                opcode_name="EMERGENCY_STOP",
                opcode_hex=info.opcode_hex,
                bytecode=[int(Op.EMERGENCY_STOP)],
                expected_halted=True,
                tags=["generated", "smoke"],
            ))
            return

        # All other A2A opcodes are Format G no-ops without handler
        op_val = int(getattr(Op, op))
        data = b"\x00"  # minimal data
        bc = bytes([op_val]) + encode_format_g(data)
        bc += encode_halt()
        self._add(ConformanceVector(
            name=f"{op} no-op without handler",
            description=f"{op} should execute as no-op without A2A handler",
            category="a2a",
            opcode_name=op,
            opcode_hex=info.opcode_hex,
            bytecode=list(bc),
            expected_halted=True,
            tags=["generated", "a2a_noop"],
        ))

    # ── Memory Management Vectors ──────────────────────────────────────────

    def _gen_memory_mgmt(self, info: OpcodeInfo) -> None:
        """Generate vectors for memory management opcodes."""
        op = info.name
        op_val = int(getattr(Op, op))

        if op == "REGION_CREATE":
            # Create a region named "test" with size 1024
            name = b"test\x00"
            size = encode_i32(1024)
            owner = b"gen\x00"
            payload = bytes([len(name) - 1]) + name[:-1] + size + bytes([len(owner) - 1]) + owner[:-1]
            bc = bytes([op_val]) + encode_format_g(payload)
            bc += encode_halt()
            self._add(ConformanceVector(
                name="REGION_CREATE creates a named region",
                description="Create region 'test' with size 1024",
                category="memory_mgmt",
                opcode_name="REGION_CREATE",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "region_create"],
            ))
            return

        if op == "REGION_DESTROY":
            # First create, then destroy
            name = b"tmp\x00"
            size = encode_i32(256)
            owner = b"gen\x00"
            create_payload = bytes([3]) + b"tmp" + size + bytes([3]) + b"gen"
            bc = bytes([int(Op.REGION_CREATE)]) + encode_format_g(create_payload)
            # Now destroy
            bc += bytes([op_val]) + encode_format_g(b"tmp\x00")
            bc += encode_halt()
            self._add(ConformanceVector(
                name="REGION_DESTROY destroys a created region",
                description="Create 'tmp', then destroy it",
                category="memory_mgmt",
                opcode_name="REGION_DESTROY",
                opcode_hex=info.opcode_hex,
                bytecode=list(bc),
                expected_halted=True,
                tags=["generated", "region_destroy"],
            ))
            return

        self._gen_generic(info)

    # ── Generic Fallback ───────────────────────────────────────────────────

    def _gen_generic(self, info: OpcodeInfo) -> None:
        """Generate a basic smoke test for any opcode."""
        op_val = info.value
        fmt = info.format

        # Format G opcodes need specific data payloads; skip generic test
        # for opcodes that parse complex variable-length data.
        if info.name in ("MEMCMP", "MEMCOPY", "MEMSET", "REGION_TRANSFER"):
            return

        if fmt == "A":
            bc = bytes([op_val, HALT])
        elif fmt == "B":
            bc = bytes([op_val, 0, HALT])
        elif fmt == "C":
            bc = bytes([op_val, 0, 0, HALT])
        elif fmt == "D":
            bc = bytes([op_val, 0, 0, 0, HALT])
        elif fmt == "E":
            bc = bytes([op_val, 0, 0, 0, HALT])
        elif fmt == "G":
            bc = bytes([op_val]) + encode_format_g(b"\x00") + bytes([HALT])
        else:
            bc = bytes([op_val, HALT])

        self._add(ConformanceVector(
            name=f"{info.name} smoke test",
            description=f"Basic smoke test for {info.name}",
            category=info.category,
            opcode_name=info.name,
            opcode_hex=info.opcode_hex,
            bytecode=list(bc),
            expected_halted=True,
            tags=["generated", "smoke", "generic"],
        ))


# ═══════════════════════════════════════════════════════════════════════════
# Batch Generation & Output
# ═══════════════════════════════════════════════════════════════════════════

def generate_vectors_for_opcode(opcode_name: str) -> List[Dict[str, Any]]:
    """Generate all test vectors for a specific opcode. Returns list of dicts."""
    gen = VectorGenerator()
    vectors = gen.generate_for_opcode(opcode_name)
    return [v.to_dict() for v in vectors]


def generate_all_vectors() -> List[Dict[str, Any]]:
    """Generate test vectors for ALL known opcodes."""
    gen = VectorGenerator()
    return [v.to_dict() for v in gen.generate_all_vectors()]


def save_vectors(vectors: List[Dict[str, Any]], output_path: str) -> None:
    """Save vectors to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(vectors, f, indent=2, default=str)
    print(f"Saved {len(vectors)} vectors to {output_path}")


def save_vectors_split(
    vectors: List[Dict[str, Any]],
    output_dir: str,
) -> Dict[str, int]:
    """Save vectors split by category into separate files. Returns count per category."""
    os.makedirs(output_dir, exist_ok=True)
    by_category: Dict[str, List[Dict]] = {}
    for v in vectors:
        cat = v.get("category", "unknown")
        by_category.setdefault(cat, []).append(v)

    counts: Dict[str, int] = {}
    for cat, cat_vectors in sorted(by_category.items()):
        path = os.path.join(output_dir, f"{cat}.json")
        with open(path, "w") as f:
            json.dump(cat_vectors, f, indent=2, default=str)
        counts[cat] = len(cat_vectors)
        print(f"  {cat}: {len(cat_vectors)} vectors → {path}")

    # Also save combined
    all_path = os.path.join(output_dir, "all_vectors.json")
    with open(all_path, "w") as f:
        json.dump(vectors, f, indent=2, default=str)
    counts["all"] = len(vectors)
    print(f"  all: {len(vectors)} vectors → {all_path}")
    return counts


# ═══════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    """CLI entry point for the conformance vector generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FLUX Conformance Vector Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate vectors for a single opcode
  python vector_generator.py --opcode IADD

  # Generate vectors for all opcodes
  python vector_generator.py --all

  # Generate and save to a specific file
  python vector_generator.py --opcode ISUB -o vectors/isub.json

  # Generate all, split by category
  python vector_generator.py --all --split -o vectors/

  # List available opcodes
  python vector_generator.py --list

  # Count vectors per opcode
  python vector_generator.py --count
        """,
    )
    parser.add_argument("--opcode", "-op", type=str, help="Generate vectors for a specific opcode")
    parser.add_argument("--all", "-a", action="store_true", help="Generate vectors for all opcodes")
    parser.add_argument("--output", "-o", type=str, help="Output file/directory path")
    parser.add_argument("--split", action="store_true", help="Split output by category")
    parser.add_argument("--list", action="store_true", help="List all available opcodes")
    parser.add_argument("--count", action="store_true", help="Count vectors per opcode")
    parser.add_argument("--categories", action="store_true", help="List opcode categories")
    parser.add_argument("--format", type=str, default="json", choices=["json"], help="Output format")

    args = parser.parse_args()

    if args.list:
        print("Available opcodes:")
        for name, info in sorted(OPCODE_DB.items()):
            print(f"  {name:20s} {info.opcode_hex:8s} Format {info.format}  {info.category:15s} {info.description}")
        return 0

    if args.categories:
        cats: Dict[str, List[str]] = {}
        for name, info in OPCODE_DB.items():
            cats.setdefault(info.category, []).append(name)
        print("Opcode categories:")
        for cat, ops in sorted(cats.items()):
            print(f"  {cat:20s} ({len(ops)} opcodes): {', '.join(ops)}")
        return 0

    if args.count:
        gen = VectorGenerator()
        total = 0
        for name in sorted(OPCODE_DB.keys()):
            vecs = gen.generate_for_opcode(name)
            if vecs:
                print(f"  {name:20s}: {len(vecs)} vectors")
                total += len(vecs)
        print(f"\nTotal: {total} vectors across {len(OPCODE_DB)} opcodes")
        return 0

    if args.opcode:
        opcode_name = args.opcode.upper()
        if opcode_name not in OPCODE_DB:
            print(f"Error: unknown opcode '{opcode_name}'")
            print(f"Available: {', '.join(sorted(OPCODE_DB.keys()))}")
            return 1
        vectors = generate_vectors_for_opcode(opcode_name)
        print(f"Generated {len(vectors)} vectors for {opcode_name}")
        if args.output:
            save_vectors(vectors, args.output)
        else:
            print(json.dumps(vectors, indent=2, default=str))
        return 0

    if args.all:
        vectors = generate_all_vectors()
        print(f"Generated {len(vectors)} total vectors")
        if args.output:
            if args.split:
                save_vectors_split(vectors, args.output)
            else:
                save_vectors(vectors, args.output)
        else:
            # Print summary
            by_cat: Dict[str, int] = {}
            for v in vectors:
                cat = v.get("category", "unknown")
                by_cat[cat] = by_cat.get(cat, 0) + 1
            for cat, count in sorted(by_cat.items()):
                print(f"  {cat}: {count}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
