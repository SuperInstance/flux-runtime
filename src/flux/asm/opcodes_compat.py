"""Opcode definitions for the cross-assembler.

Maps mnemonic names to their bytecode encodings, formats, and operand counts.
Uses the authoritative opcodes from flux.bytecode.opcodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .errors import AsmError, AsmErrorKind


@dataclass
class OpcodeDef:
    """Definition of a single opcode for the assembler."""
    mnemonic: str
    opcode: int
    format: str  # A, B, C, D, E, F, G
    size: int  # fixed byte size (-1 for variable)
    min_operands: int = 0
    max_operands: int = 0
    description: str = ""


def parse_register(s: str, loc: Optional[object] = None) -> int:
    """Parse a register name like 'R0', 'R15', 'r3', or bare number -> int."""
    s = s.strip()
    if s.upper().startswith("R"):
        try:
            val = int(s[1:])
        except ValueError:
            raise AsmError(
                message=f"Invalid register: {s}",
                kind=AsmErrorKind.UNKNOWN_REGISTER,
            )
    else:
        try:
            val = int(s)
        except ValueError:
            raise AsmError(
                message=f"Invalid register: {s}",
                kind=AsmErrorKind.UNKNOWN_REGISTER,
            )
    if not (0 <= val <= 63):
        raise AsmError(
            message=f"Register {val} out of range (0-63)",
            kind=AsmErrorKind.RANGE_ERROR,
        )
    return val


# Master opcode table — aligned with flux.bytecode.opcodes.Op
# Format sizes match the encoding spec:
#   A: 1 byte  [op]
#   B: 2 bytes [op][rd]
#   C: 3 bytes [op][rd][rs1]
#   D: 4 bytes [op][rd][imm16:i16]
#   E: 4 bytes [op][rd][rs1][rs2]
#   F: 4 bytes [op][rd][imm16:u16] (unsigned 16-bit)
#   G: variable [op][len:u16][data]

OPCODE_DEFS: dict[str, OpcodeDef] = {}

# ── Control flow ─────────────────────────────────────────────────────────────
_OPCODES_LIST = [
    # Control flow
    OpcodeDef("NOP", 0x00, "A", 1, 0, 0, "No operation"),
    OpcodeDef("MOV", 0x01, "C", 3, 2, 2, "Move register"),
    OpcodeDef("LOAD", 0x02, "C", 3, 2, 2, "Load from memory"),
    OpcodeDef("STORE", 0x03, "C", 3, 2, 2, "Store to memory"),
    OpcodeDef("JMP", 0x04, "D", 4, 1, 2, "Jump (reg or label offset)"),
    OpcodeDef("JZ", 0x05, "D", 4, 2, 2, "Jump if zero"),
    OpcodeDef("JNZ", 0x06, "D", 4, 2, 2, "Jump if not zero"),
    OpcodeDef("CALL", 0x07, "D", 4, 2, 2, "Call function"),

    # Integer arithmetic
    OpcodeDef("IADD", 0x08, "E", 4, 3, 3, "Integer add"),
    OpcodeDef("ISUB", 0x09, "E", 4, 3, 3, "Integer subtract"),
    OpcodeDef("IMUL", 0x0A, "E", 4, 3, 3, "Integer multiply"),
    OpcodeDef("IDIV", 0x0B, "E", 4, 3, 3, "Integer divide"),
    OpcodeDef("IMOD", 0x0C, "E", 4, 3, 3, "Integer modulo"),
    OpcodeDef("IREM", 0x2C, "E", 4, 3, 3, "Integer remainder"),
    OpcodeDef("INEG", 0x0D, "B", 2, 1, 1, "Integer negate"),
    OpcodeDef("INC", 0x0E, "B", 2, 1, 1, "Increment register"),
    OpcodeDef("DEC", 0x0F, "B", 2, 1, 1, "Decrement register"),

    # Bitwise
    OpcodeDef("IAND", 0x10, "E", 4, 3, 3, "Bitwise AND"),
    OpcodeDef("IOR", 0x11, "E", 4, 3, 3, "Bitwise OR"),
    OpcodeDef("IXOR", 0x12, "E", 4, 3, 3, "Bitwise XOR"),
    OpcodeDef("INOT", 0x13, "B", 2, 1, 1, "Bitwise NOT"),
    OpcodeDef("ISHL", 0x14, "E", 4, 3, 3, "Shift left"),
    OpcodeDef("ISHR", 0x15, "E", 4, 3, 3, "Shift right"),
    OpcodeDef("ROTL", 0x16, "E", 4, 3, 3, "Rotate left"),
    OpcodeDef("ROTR", 0x17, "E", 4, 3, 3, "Rotate right"),

    # Comparison
    OpcodeDef("ICMP", 0x18, "E", 4, 3, 3, "Integer compare"),
    OpcodeDef("IEQ", 0x19, "E", 4, 3, 3, "Integer equal"),
    OpcodeDef("ILT", 0x1A, "E", 4, 3, 3, "Integer less than"),
    OpcodeDef("ILE", 0x1B, "E", 4, 3, 3, "Integer less or equal"),
    OpcodeDef("IGT", 0x1C, "E", 4, 3, 3, "Integer greater than"),
    OpcodeDef("IGE", 0x1D, "E", 4, 3, 3, "Integer greater or equal"),
    OpcodeDef("TEST", 0x1E, "E", 4, 2, 2, "Test register"),
    OpcodeDef("SETCC", 0x1F, "E", 4, 2, 2, "Set condition code"),

    # Stack ops
    OpcodeDef("PUSH", 0x20, "B", 2, 1, 1, "Push register"),
    OpcodeDef("POP", 0x21, "B", 2, 1, 1, "Pop register"),
    OpcodeDef("DUP", 0x22, "A", 1, 0, 0, "Duplicate top of stack"),
    OpcodeDef("SWAP", 0x23, "A", 1, 0, 0, "Swap top two stack entries"),
    OpcodeDef("ROT", 0x24, "A", 1, 0, 0, "Rotate stack"),
    OpcodeDef("ENTER", 0x25, "B", 2, 1, 1, "Enter frame"),
    OpcodeDef("LEAVE", 0x26, "B", 2, 1, 1, "Leave frame"),
    OpcodeDef("ALLOCA", 0x27, "B", 2, 1, 1, "Allocate stack"),

    # Function ops
    OpcodeDef("RET", 0x28, "C", 3, 0, 2, "Return"),
    OpcodeDef("CALL_IND", 0x29, "C", 3, 2, 2, "Indirect call"),
    OpcodeDef("TAILCALL", 0x2A, "C", 3, 2, 2, "Tail call"),
    OpcodeDef("MOVI", 0x2B, "D", 4, 2, 2, "Move immediate (16-bit signed)"),
    OpcodeDef("CMP", 0x2D, "C", 3, 2, 2, "Compare"),
    OpcodeDef("JE", 0x2E, "D", 4, 2, 2, "Jump if equal"),
    OpcodeDef("JNE", 0x2F, "D", 4, 2, 2, "Jump if not equal"),

    # Memory management
    OpcodeDef("REGION_CREATE", 0x30, "A", 1, 0, 0, "Create memory region"),
    OpcodeDef("REGION_DESTROY", 0x31, "A", 1, 0, 0, "Destroy memory region"),
    OpcodeDef("REGION_TRANSFER", 0x32, "A", 1, 0, 0, "Transfer memory region"),
    OpcodeDef("MEMCOPY", 0x33, "E", 4, 3, 3, "Copy memory"),
    OpcodeDef("MEMSET", 0x34, "E", 4, 3, 3, "Set memory"),
    OpcodeDef("MEMCMP", 0x35, "E", 4, 3, 3, "Compare memory"),
    OpcodeDef("JL", 0x36, "D", 4, 2, 2, "Jump if less"),
    OpcodeDef("JGE", 0x37, "D", 4, 2, 2, "Jump if greater or equal"),

    # Type ops
    OpcodeDef("CAST", 0x38, "C", 3, 2, 2, "Cast type"),
    OpcodeDef("BOX", 0x39, "B", 2, 1, 1, "Box value"),
    OpcodeDef("UNBOX", 0x3A, "B", 2, 1, 1, "Unbox value"),
    OpcodeDef("CHECK_TYPE", 0x3B, "C", 3, 2, 2, "Check type"),
    OpcodeDef("CHECK_BOUNDS", 0x3C, "C", 3, 2, 2, "Check bounds"),

    # Meta
    OpcodeDef("CONF", 0x3D, "B", 2, 1, 1, "Attach confidence"),
    OpcodeDef("MERGE", 0x3E, "E", 4, 3, 3, "Weighted merge"),
    OpcodeDef("RESTORE", 0x3F, "B", 2, 1, 1, "Restore VM state"),

    # Float arithmetic
    OpcodeDef("FADD", 0x40, "E", 4, 3, 3, "Float add"),
    OpcodeDef("FSUB", 0x41, "E", 4, 3, 3, "Float subtract"),
    OpcodeDef("FMUL", 0x42, "E", 4, 3, 3, "Float multiply"),
    OpcodeDef("FDIV", 0x43, "E", 4, 3, 3, "Float divide"),
    OpcodeDef("FNEG", 0x44, "B", 2, 1, 1, "Float negate"),
    OpcodeDef("FABS", 0x45, "B", 2, 1, 1, "Float absolute"),
    OpcodeDef("FMIN", 0x46, "E", 4, 3, 3, "Float minimum"),
    OpcodeDef("FMAX", 0x47, "E", 4, 3, 3, "Float maximum"),

    # Float comparison
    OpcodeDef("FEQ", 0x48, "E", 4, 3, 3, "Float equal"),
    OpcodeDef("FLT", 0x49, "E", 4, 3, 3, "Float less than"),
    OpcodeDef("FLE", 0x4A, "E", 4, 3, 3, "Float less or equal"),
    OpcodeDef("FGT", 0x4B, "E", 4, 3, 3, "Float greater than"),
    OpcodeDef("FGE", 0x4C, "E", 4, 3, 3, "Float greater or equal"),
    OpcodeDef("JG", 0x4D, "D", 4, 2, 2, "Jump if greater"),
    OpcodeDef("JLE", 0x4E, "D", 4, 2, 2, "Jump if less or equal"),
    OpcodeDef("LOAD8", 0x4F, "C", 3, 2, 2, "Load 8-bit"),
    OpcodeDef("STORE8", 0x57, "C", 3, 2, 2, "Store 8-bit"),

    # SIMD
    OpcodeDef("VLOAD", 0x50, "C", 3, 2, 2, "Vector load"),
    OpcodeDef("VSTORE", 0x51, "C", 3, 2, 2, "Vector store"),
    OpcodeDef("VADD", 0x52, "E", 4, 3, 3, "Vector add"),
    OpcodeDef("VSUB", 0x53, "E", 4, 3, 3, "Vector subtract"),
    OpcodeDef("VMUL", 0x54, "E", 4, 3, 3, "Vector multiply"),
    OpcodeDef("VDIV", 0x55, "E", 4, 3, 3, "Vector divide"),
    OpcodeDef("VFMA", 0x56, "E", 4, 3, 3, "Vector fused multiply-add"),

    # A2A protocol
    OpcodeDef("TELL", 0x60, "A", 1, 0, 0, "A2A tell"),
    OpcodeDef("ASK", 0x61, "A", 1, 0, 0, "A2A ask"),
    OpcodeDef("DELEGATE", 0x62, "A", 1, 0, 0, "A2A delegate"),
    OpcodeDef("DELEGATE_RESULT", 0x63, "A", 1, 0, 0, "A2A delegate result"),
    OpcodeDef("REPORT_STATUS", 0x64, "A", 1, 0, 0, "A2A report status"),
    OpcodeDef("REQUEST_OVERRIDE", 0x65, "A", 1, 0, 0, "A2A request override"),
    OpcodeDef("BROADCAST", 0x66, "A", 1, 0, 0, "A2A broadcast"),
    OpcodeDef("REDUCE", 0x67, "A", 1, 0, 0, "A2A reduce"),
    OpcodeDef("DECLARE_INTENT", 0x68, "A", 1, 0, 0, "A2A declare intent"),
    OpcodeDef("ASSERT_GOAL", 0x69, "A", 1, 0, 0, "A2A assert goal"),
    OpcodeDef("VERIFY_OUTCOME", 0x6A, "A", 1, 0, 0, "A2A verify outcome"),
    OpcodeDef("EXPLAIN_FAILURE", 0x6B, "A", 1, 0, 0, "A2A explain failure"),
    OpcodeDef("SET_PRIORITY", 0x6C, "A", 1, 0, 0, "A2A set priority"),

    # Trust & capabilities
    OpcodeDef("TRUST_CHECK", 0x70, "A", 1, 0, 0, "Trust check"),
    OpcodeDef("TRUST_UPDATE", 0x71, "A", 1, 0, 0, "Trust update"),
    OpcodeDef("TRUST_QUERY", 0x72, "A", 1, 0, 0, "Trust query"),
    OpcodeDef("REVOKE_TRUST", 0x73, "A", 1, 0, 0, "Revoke trust"),
    OpcodeDef("CAP_REQUIRE", 0x74, "A", 1, 0, 0, "Capability require"),
    OpcodeDef("CAP_REQUEST", 0x75, "A", 1, 0, 0, "Capability request"),
    OpcodeDef("CAP_GRANT", 0x76, "A", 1, 0, 0, "Capability grant"),
    OpcodeDef("CAP_REVOKE", 0x77, "A", 1, 0, 0, "Capability revoke"),
    OpcodeDef("BARRIER", 0x78, "A", 1, 0, 0, "Barrier sync"),
    OpcodeDef("SYNC_CLOCK", 0x79, "A", 1, 0, 0, "Sync clock"),
    OpcodeDef("FORMATION_UPDATE", 0x7A, "A", 1, 0, 0, "Formation update"),
    OpcodeDef("EMERGENCY_STOP", 0x7B, "A", 1, 0, 0, "Emergency stop"),

    # Evolution & instinct
    OpcodeDef("EVOLVE", 0x7C, "A", 1, 0, 0, "Trigger evolution cycle"),
    OpcodeDef("INSTINCT", 0x7D, "A", 1, 0, 0, "Execute instinct action"),
    OpcodeDef("WITNESS", 0x7E, "A", 1, 0, 0, "Write witness mark"),
    OpcodeDef("SNAPSHOT", 0x7F, "A", 1, 0, 0, "Save VM state"),

    # System
    OpcodeDef("HALT", 0x80, "A", 1, 0, 0, "Halt execution"),
    OpcodeDef("YIELD", 0x81, "A", 1, 0, 0, "Yield execution"),
    OpcodeDef("RESOURCE_ACQUIRE", 0x82, "A", 1, 0, 0, "Acquire resource"),
    OpcodeDef("RESOURCE_RELEASE", 0x83, "A", 1, 0, 0, "Release resource"),
    OpcodeDef("DEBUG_BREAK", 0x84, "A", 1, 0, 0, "Debug breakpoint"),
]

for _op in _OPCODES_LIST:
    OPCODE_DEFS[_op.mnemonic] = _op

# Aliases for compatibility
_OPCODE_ALIASES = {
    "NEG": "INEG",
    "NOT": "INOT",
    "ADD": "IADD",
    "SUB": "ISUB",
    "MUL": "IMUL",
    "DIV": "IDIV",
    "MOD": "IMOD",
    "AND": "IAND",
    "OR": "IOR",
    "XOR": "IXOR",
    "SHL": "ISHL",
    "SHR": "ISHR",
    "CMP_EQ": "IEQ",
    "CMP_LT": "ILT",
    "CMP_GT": "IGT",
    "CMP_NE": "ICMP",
    "BEQ": "JE",
    "BNE": "JNE",
    "BLT": "JL",
    "BGE": "JGE",
    "BGT": "JG",
    "BLE": "JLE",
}

for alias, target in _OPCODE_ALIASES.items():
    if target in OPCODE_DEFS:
        OPCODE_DEFS[alias] = OPCODE_DEFS[target]
