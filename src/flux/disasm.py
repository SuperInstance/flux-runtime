"""FLUX Bytecode Disassembler.

A lightweight disassembler that takes raw bytecode bytes and produces
human-readable instruction listings. No VM dependency.

Instruction encoding formats:
    Format A (1 byte):  [opcode]
    Format B (2 bytes): [opcode][reg]
    Format C (3 bytes): [opcode][rd][rs1]
    Format D (4 bytes): [opcode][rs1][off_lo][off_hi]   (signed i16, LE)
    Format E (4 bytes): [opcode][rd][rs1][rs2]
    MOVI   (4 bytes):  [opcode][reg][imm_lo][imm_hi]     (signed i16, LE)
    Format G (variable): [opcode][len:u16][data:len bytes]
"""

from __future__ import annotations

import struct
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field

from flux.bytecode.opcodes import Op, get_format, FORMAT_A, FORMAT_B, FORMAT_C, FORMAT_D, FORMAT_E, FORMAT_G


# ── Color codes for terminal output ─────────────────────────────────────────────

class Colors:
    """ANSI color codes for instruction type categorization."""
    RESET = "\033[0m"
    ARITHMETIC = "\033[92m"      # green
    CONTROL_FLOW = "\033[93m"    # yellow
    MEMORY = "\033[96m"          # cyan
    A2A = "\033[95m"             # magenta
    SYSTEM = "\033[91m"          # red
    STACK = "\033[94m"           # blue
    COMPARISON = "\033[97m"      # white
    TYPE_OP = "\033[38;5;208m"   # orange
    SIMD = "\033[38;5;214m"      # gold


# ── Opcode categorization for color coding ──────────────────────────────────────

ARITHMETIC_OPS = {
    Op.IADD, Op.ISUB, Op.IMUL, Op.IDIV, Op.IMOD, Op.IREM,
    Op.FADD, Op.FSUB, Op.FMUL, Op.FDIV,
    Op.INEG, Op.FNEG, Op.FABS, Op.FMIN, Op.FMAX,
    Op.INC, Op.DEC,
}

CONTROL_FLOW_OPS = {
    Op.JMP, Op.JZ, Op.JNZ, Op.JE, Op.JNE, Op.JG, Op.JL, Op.JGE, Op.JLE,
    Op.CALL, Op.CALL_IND, Op.TAILCALL, Op.RET,
    Op.HALT, Op.NOP, Op.YIELD,
}

MEMORY_OPS = {
    Op.LOAD, Op.STORE, Op.LOAD8, Op.STORE8,
    Op.MEMCOPY, Op.MEMSET, Op.MEMCMP,
    Op.REGION_CREATE, Op.REGION_DESTROY, Op.REGION_TRANSFER,
    Op.ALLOCA,
}

COMPARISON_OPS = {
    Op.ICMP, Op.IEQ, Op.ILT, Op.ILE, Op.IGT, Op.IGE,
    Op.FEQ, Op.FLT, Op.FLE, Op.FGT, Op.FGE,
    Op.CMP, Op.TEST, Op.SETCC,
}

STACK_OPS = {
    Op.PUSH, Op.POP, Op.DUP, Op.SWAP, Op.ROT,
    Op.ENTER, Op.LEAVE,
}

TYPE_OPS = {
    Op.CAST, Op.BOX, Op.UNBOX, Op.CHECK_TYPE, Op.CHECK_BOUNDS,
}

SIMD_OPS = {
    Op.VLOAD, Op.VSTORE, Op.VADD, Op.VSUB, Op.VMUL, Op.VDIV, Op.VFMA,
}

A2A_OPS = {
    Op.TELL, Op.ASK, Op.DELEGATE, Op.DELEGATE_RESULT,
    Op.REPORT_STATUS, Op.REQUEST_OVERRIDE, Op.BROADCAST, Op.REDUCE,
    Op.DECLARE_INTENT, Op.ASSERT_GOAL, Op.VERIFY_OUTCOME,
    Op.EXPLAIN_FAILURE, Op.SET_PRIORITY,
    Op.TRUST_CHECK, Op.TRUST_UPDATE, Op.TRUST_QUERY, Op.REVOKE_TRUST,
    Op.CAP_REQUIRE, Op.CAP_REQUEST, Op.CAP_GRANT, Op.CAP_REVOKE,
    Op.BARRIER, Op.SYNC_CLOCK, Op.FORMATION_UPDATE, Op.EMERGENCY_STOP,
}

SYSTEM_OPS = {
    Op.RESOURCE_ACQUIRE, Op.RESOURCE_RELEASE,
    Op.DEBUG_BREAK,
}


def get_instruction_color(opcode: Op) -> str:
    """Get the color code for an opcode based on its category."""
    if opcode in ARITHMETIC_OPS:
        return Colors.ARITHMETIC
    elif opcode in CONTROL_FLOW_OPS:
        return Colors.CONTROL_FLOW
    elif opcode in MEMORY_OPS:
        return Colors.MEMORY
    elif opcode in COMPARISON_OPS:
        return Colors.COMPARISON
    elif opcode in STACK_OPS:
        return Colors.STACK
    elif opcode in TYPE_OPS:
        return Colors.TYPE_OP
    elif opcode in SIMD_OPS:
        return Colors.SIMD
    elif opcode in A2A_OPS:
        return Colors.A2A
    elif opcode in SYSTEM_OPS:
        return Colors.SYSTEM
    return Colors.RESET


# ── Disassembler data structures ────────────────────────────────────────────────

@dataclass
class DisassembledInstruction:
    """A single disassembled instruction."""
    offset: int                    # Byte offset in the bytecode
    opcode: Op                     # The opcode value
    opcode_name: str               # Human-readable opcode name
    operands: str                  # Formatted operand string
    bytes: bytes                   # Raw instruction bytes
    size: int                      # Instruction size in bytes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "offset": self.offset,
            "opcode": hex(self.opcode),
            "opcode_name": self.opcode_name,
            "operands": self.operands,
            "bytes": self.bytes.hex(),
            "size": self.size,
        }


@dataclass
class DisassemblyResult:
    """Complete disassembly result."""
    instructions: List[DisassembledInstruction] = field(default_factory=list)
    total_bytes: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "instructions": [instr.to_dict() for instr in self.instructions],
            "total_bytes": self.total_bytes,
            "instruction_count": len(self.instructions),
            "error": self.error,
        }


# ── Main Disassembler ───────────────────────────────────────────────────────────

class FluxDisassembler:
    """Disassembles FLUX bytecode bytes into human-readable format.

    Example usage:
        disasm = FluxDisassembler()
        result = disasm.disassemble(bytecode_bytes)
        print(result.to_text())

        # Or JSON output
        print(result.to_json())
    """

    def __init__(self, color_output: bool = True):
        """Initialize the disassembler.

        Args:
            color_output: If True, use ANSI color codes in text output.
        """
        self.color_output = color_output

    def disassemble(self, bytecode: bytes) -> DisassemblyResult:
        """Disassemble FLUX bytecode bytes.

        Args:
            bytecode: Raw bytecode bytes (with or without FLUX header).

        Returns:
            DisassemblyResult containing all disassembled instructions.
        """
        # Extract code section if FLUX header is present
        code = self._extract_code(bytecode)
        result = DisassemblyResult(total_bytes=len(code))

        offset = 0
        while offset < len(code):
            try:
                instr = self._disassemble_one(code, offset)
                result.instructions.append(instr)
                offset += instr.size
            except Exception as e:
                result.error = f"Error at offset {offset}: {e}"
                break

        return result

    def _extract_code(self, bytecode: bytes) -> bytes:
        """Extract the code section from a FLUX binary file.

        Binary layout:
            [Header 18B][Type Table][Name Pool][Function Table][Code Section]

        Header (18 bytes):
            magic:    b'FLUX'         (4 bytes)
            version:  uint16 LE        (2 bytes)
            flags:    uint16 LE        (2 bytes)
            n_funcs:  uint16 LE        (2 bytes)
            type_off: uint32 LE        (4 bytes)
            code_off: uint32 LE        (4 bytes)  ← at offset 14
        """
        if len(bytecode) >= 18 and bytecode[:4] == b"FLUX":
            code_off = struct.unpack_from("<I", bytecode, 14)[0]
            if 18 <= code_off <= len(bytecode):
                return bytecode[code_off:]
        return bytecode

    def _disassemble_one(self, code: bytes, offset: int) -> DisassembledInstruction:
        """Disassemble a single instruction at the given offset."""
        opcode_byte = code[offset]
        try:
            opcode = Op(opcode_byte)
        except ValueError:
            # Unknown opcode - still create a minimal instruction
            return DisassembledInstruction(
                offset=offset,
                opcode=opcode_byte,
                opcode_name=f"UNKNOWN_0x{opcode_byte:02X}",
                operands="",
                bytes=code[offset:offset+1],
                size=1,
            )

        fmt = get_format(opcode)
        instr_bytes, operands = self._decode_operands(code, offset, opcode, fmt)

        return DisassembledInstruction(
            offset=offset,
            opcode=opcode,
            opcode_name=opcode.name,
            operands=operands,
            bytes=instr_bytes,
            size=len(instr_bytes),
        )

    def _decode_operands(self, code: bytes, offset: int, opcode: Op, fmt: str) -> tuple[bytes, str]:
        """Decode instruction operands based on format.

        Returns:
            (raw_bytes, formatted_operand_string)
        """
        if fmt == "A":
            # Format A: 1 byte - opcode only
            return code[offset:offset+1], ""

        elif fmt == "B":
            # Format B: 2 bytes - opcode + reg
            if offset + 1 >= len(code):
                return code[offset:offset+1], "???"
            reg = code[offset + 1]
            return code[offset:offset+2], f"R{reg}"

        elif fmt == "C":
            # Format C: 3 bytes - opcode + rd + rs1
            if offset + 2 >= len(code):
                return code[offset:offset+1], "???"
            rd = code[offset + 1]
            rs1 = code[offset + 2]
            return code[offset:offset+3], f"R{rd}, R{rs1}"

        elif fmt == "D":
            # Format D: 4 bytes - opcode + rs1 + imm16 (signed)
            if offset + 3 >= len(code):
                return code[offset:offset+1], "???"
            rs1 = code[offset + 1]
            imm = struct.unpack_from("<h", code, offset + 2)[0]
            if opcode == Op.MOVI:
                # MOVI special case: reg + imm16 (format B + imm16)
                return code[offset:offset+4], f"R{rs1}, {imm}"
            else:
                # Jump instructions: rs1 (often unused) + offset
                return code[offset:offset+4], f"R{rs1}, {imm:+d} (offset={offset + 4 + imm})"

        elif fmt == "E":
            # Format E: 4 bytes - opcode + rd + rs1 + rs2
            if offset + 3 >= len(code):
                return code[offset:offset+1], "???"
            rd = code[offset + 1]
            rs1 = code[offset + 2]
            rs2 = code[offset + 3]
            return code[offset:offset+4], f"R{rd}, R{rs1}, R{rs2}"

        elif fmt == "G":
            # Format G: variable - opcode + len:u16 + data
            if offset + 2 >= len(code):
                return code[offset:offset+1], "???"
            length = struct.unpack_from("<H", code, offset + 1)[0]
            data_end = offset + 3 + length
            if data_end > len(code):
                data_end = len(code)
            data_bytes = code[offset + 3:data_end]
            instr_bytes = code[offset:data_end]

            # Format data for display
            data_str = self._format_data(opcode, data_bytes)
            return instr_bytes, f"{length}, {data_str}"

        # Default: unknown format
        return code[offset:offset+1], ""

    def _format_data(self, opcode: Op, data: bytes) -> str:
        """Format variable-length data for display."""
        if len(data) <= 8:
            # Show hex for small data
            hex_str = " ".join(f"{b:02x}" for b in data)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
            return f"[{hex_str}] \"{ascii_str}\""
        else:
            # Truncate for larger data
            preview = data[:8]
            hex_str = " ".join(f"{b:02x}" for b in preview)
            return f"[{hex_str}... ({len(data)} bytes total)]"

    def format_instruction(self, instr: DisassembledInstruction) -> str:
        """Format a single disassembled instruction for display."""
        color = get_instruction_color(instr.opcode) if self.color_output else ""

        # Format: OFFSET  BYTES               OPCODE   OPERANDS
        offset_str = f"{instr.offset:04x}"
        bytes_str = instr.bytes.hex().ljust(16)
        opcode_str = f"{color}{instr.opcode_name}{Colors.RESET if self.color_output else ''}"
        operands_str = instr.operands if instr.operands else ""

        return f"{offset_str}:  {bytes_str}  {opcode_str:<20} {operands_str}"

    def format_header(self, total_bytes: int) -> str:
        """Format a header for the disassembly output."""
        return f"FLUX Bytecode Disassembly ({total_bytes} bytes)"
        return f"{'OFFSET':<8}  {'BYTES':<18}  {'OPCODE':<20}  {'OPERANDS'}"


# ── Convenience functions ───────────────────────────────────────────────────────

def disassemble(bytecode: bytes, color_output: bool = True) -> str:
    """Disassemble FLUX bytecode and return formatted text output.

    Args:
        bytecode: Raw bytecode bytes.
        color_output: If True, use ANSI color codes.

    Returns:
        Formatted disassembly text.
    """
    disasm = FluxDisassembler(color_output=color_output)
    result = disasm.disassemble(bytecode)

    lines = [disasm.format_header(result.total_bytes)]
    lines.append("=" * 80)

    for instr in result.instructions:
        lines.append(disasm.format_instruction(instr))

    if result.error:
        lines.append(f"\nERROR: {result.error}")

    return "\n".join(lines)


def disassemble_to_dict(bytecode: bytes) -> Dict[str, Any]:
    """Disassemble FLUX bytecode and return structured data.

    Args:
        bytecode: Raw bytecode bytes.

    Returns:
        Dictionary with disassembly results.
    """
    disasm = FluxDisassembler(color_output=False)
    result = disasm.disassemble(bytecode)
    return result.to_dict()


def disassemble_to_json(bytecode: bytes, indent: int = 2) -> str:
    """Disassemble FLUX bytecode and return JSON string.

    Args:
        bytecode: Raw bytecode bytes.
        indent: JSON indentation level.

    Returns:
        JSON string with disassembly results.
    """
    data = disassemble_to_dict(bytecode)
    return json.dumps(data, indent=indent)


# ── Main entry point for command-line use ───────────────────────────────────────

def main() -> None:
    """Command-line entry point for the disassembler."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Disassemble FLUX bytecode to human-readable format."
    )
    parser.add_argument(
        "input",
        help="Bytecode file to disassemble (.bin)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output JSON instead of formatted text",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes in output",
    )

    args = parser.parse_args()

    with open(args.input, "rb") as f:
        bytecode = f.read()

    if args.json:
        output = disassemble_to_json(bytecode)
    else:
        output = disassemble(bytecode, color_output=not args.no_color)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
