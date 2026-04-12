"""FLUX Assembler — Compiles FLUX assembly source into unified ISA bytecodes.

Supports:
- Labels (e.g., loop:, done:)
- All unified ISA opcodes (Formats A through G)
- Register operands (R0-R15)
- Immediate operands (decimal, hex 0x prefix, negative)
- Label references in jump instructions (JMP, JNZ, JZ, JLT, JGT)
- Comments (; to end of line)
- Pseudo-instruction expansion for conditional jumps with labels

Encoding reference (from formats.py):
  Format A: 1 byte  [op]
  Format B: 2 bytes [op][rd]
  Format C: 2 bytes [op][imm8]
  Format D: 3 bytes [op][rd][imm8]  (imm8 sign-extended)
  Format E: 4 bytes [op][rd][rs1][rs2]
  Format F: 4 bytes [op][rd][imm16hi][imm16lo]
  Format G: 5 bytes [op][rd][rs1][imm16hi][imm16lo]

Conditional jump expansion (JNZ/JZ/JLT/JGT reg, label):
  Since Format E jumps use a register for the offset (not an immediate),
  the assembler expands: JNZ Rd, label  -->  MOVI R15, <offset>; JNZ Rd, R15
  This uses R15 as a scratch register for the offset. Total: 7 bytes.

Author: Super Z (Assembler)
Date: 2026-04-12
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union


class AssemblyError(Exception):
    """Raised when assembly source has errors."""
    pass


# ── Opcode Tables (authoritative: isa_unified.py / formats.py) ────────────────

# Format A (1 byte) — System Control
OPCODES_A: Dict[str, int] = {
    "HALT": 0x00, "NOP": 0x01, "RET": 0x02, "IRET": 0x03,
    "BRK": 0x04, "WFI": 0x05, "RESET": 0x06, "SYN": 0x07,
    "HALT_ERR": 0xF0, "REBOOT": 0xF1, "DUMP": 0xF2, "ASSERT": 0xF3,
    "ID": 0xF4, "VER": 0xF5, "CLK": 0xF6, "PCLK": 0xF7,
    "WDOG": 0xF8, "SLEEP": 0xF9, "ILLEGAL": 0xFF,
}

# Format B (2 bytes) — Single Register
OPCODES_B: Dict[str, int] = {
    "INC": 0x08, "DEC": 0x09, "NOT": 0x0A, "NEG": 0x0B,
    "PUSH": 0x0C, "POP": 0x0D, "CONF_LD": 0x0E, "CONF_ST": 0x0F,
}

# Format C (2 bytes) — Immediate Only
OPCODES_C: Dict[str, int] = {
    "SYS": 0x10, "TRAP": 0x11, "DBG": 0x12, "CLF": 0x13,
    "SEMA": 0x14, "YIELD": 0x15, "CACHE": 0x16, "STRIPCF": 0x17,
}

# Format D (3 bytes) — Register + imm8
OPCODES_D: Dict[str, int] = {
    "MOVI": 0x18, "ADDI": 0x19, "SUBI": 0x1A, "ANDI": 0x1B,
    "ORI": 0x1C, "XORI": 0x1D, "SHLI": 0x1E, "SHRI": 0x1F,
    "C_THRESH": 0x69,
}

# Format E (4 bytes) — 3-register (2-register ops use rs2=0)
OPCODES_E: Dict[str, int] = {
    "ADD": 0x20, "SUB": 0x21, "MUL": 0x22, "DIV": 0x23,
    "MOD": 0x24, "AND": 0x25, "OR": 0x26, "XOR": 0x27,
    "SHL": 0x28, "SHR": 0x29, "MIN": 0x2A, "MAX": 0x2B,
    "CMP_EQ": 0x2C, "CMP_LT": 0x2D, "CMP_GT": 0x2E, "CMP_NE": 0x2F,
    "FADD": 0x30, "FSUB": 0x31, "FMUL": 0x32, "FDIV": 0x33,
    "FMIN": 0x34, "FMAX": 0x35, "FTOI": 0x36, "ITOF": 0x37,
    "LOAD": 0x38, "STORE": 0x39, "MOV": 0x3A, "SWP": 0x3B,
    "JZ": 0x3C, "JNZ": 0x3D, "JLT": 0x3E, "JGT": 0x3F,
    "C_ADD": 0x60, "C_SUB": 0x61, "C_MUL": 0x62, "C_DIV": 0x63,
    "C_FADD": 0x64, "C_FSUB": 0x65, "C_FMUL": 0x66, "C_FDIV": 0x67,
    "C_MERGE": 0x68,
}

# Format F (4 bytes) — Register + imm16
OPCODES_F: Dict[str, int] = {
    "MOVI16": 0x40, "ADDI16": 0x41, "SUBI16": 0x42,
    "JMP": 0x43, "JAL": 0x44, "CALL": 0x45,
    "LOOP": 0x46, "SELECT": 0x47,
    "JMPL": 0xE0, "JALL": 0xE1, "CALLL": 0xE2,
    "TAIL": 0xE3, "TRACE": 0xE9,
}

# Format G (5 bytes) — Register + register + imm16
OPCODES_G: Dict[str, int] = {
    "LOADOFF": 0x48, "STOREOFF": 0x49, "LOADI": 0x4A, "STOREI": 0x4B,
    "ENTER": 0x4C, "LEAVE": 0x4D, "COPY": 0x4E, "FILL": 0x4F,
    "DMA_CPY": 0xD0, "DMA_SET": 0xD1, "MMIO_R": 0xD2, "MMIO_W": 0xD3,
    "ATOMIC": 0xD4, "CAS": 0xD5, "FENCE": 0xD6,
}

# Complete mnemonic -> (opcode, format_name) mapping
ALL_OPCODES: Dict[str, Tuple[int, str]] = {}
for _mnem, _op in OPCODES_A.items():
    ALL_OPCODES[_mnem] = (_op, "A")
for _mnem, _op in OPCODES_B.items():
    ALL_OPCODES[_mnem] = (_op, "B")
for _mnem, _op in OPCODES_C.items():
    ALL_OPCODES[_mnem] = (_op, "C")
for _mnem, _op in OPCODES_D.items():
    ALL_OPCODES[_mnem] = (_op, "D")
for _mnem, _op in OPCODES_E.items():
    ALL_OPCODES[_mnem] = (_op, "E")
for _mnem, _op in OPCODES_F.items():
    ALL_OPCODES[_mnem] = (_op, "F")
for _mnem, _op in OPCODES_G.items():
    ALL_OPCODES[_mnem] = (_op, "G")

# Scratch register used for conditional jump offset expansion
SCRATCH_REG = 15

# Conditional jump mnemonics that expand to MOVI + Jcc when target is a label
CONDITIONAL_JUMPS = {"JZ", "JNZ", "JLT", "JGT"}

# Opcodes that take a label for an unconditional jump (Format F)
UNCONDITIONAL_JUMPS = {"JMP", "JAL", "JMPL", "JALL", "CALLL", "TAIL", "TRACE"}


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class Operand:
    """An operand in an assembly instruction."""
    kind: str  # 'reg', 'imm', 'label'
    value: Union[int, str]  # register number, immediate value, or label name


@dataclass
class ParsedInstruction:
    """A parsed assembly line (label + optional instruction)."""
    label: Optional[str] = None  # label defined on this line (before instruction)
    mnemonic: Optional[str] = None
    operands: List[Operand] = field(default_factory=list)
    source_line: int = 0


# ── Parser ────────────────────────────────────────────────────────────────────


def _parse_register(token: str) -> int:
    """Parse a register name like R0, R15, r5 into a register number."""
    token = token.strip().upper()
    if token.startswith("R") and len(token) >= 2:
        try:
            num = int(token[1:])
            if 0 <= num <= 15:
                return num
        except ValueError:
            pass
    raise AssemblyError(f"Invalid register: {token!r}")


def _parse_immediate(token: str) -> int:
    """Parse an immediate value (decimal, hex 0x, or negative)."""
    token = token.strip()
    try:
        if token.startswith(("0x", "0X")):
            return int(token, 16)
        elif token.startswith("-0x") or token.startswith("-0X"):
            return -int(token[1:], 16)
        else:
            return int(token)
    except ValueError:
        raise AssemblyError(f"Invalid immediate: {token!r}")


def _parse_operand(token: str) -> Operand:
    """Parse a single operand into a register, immediate, or label reference."""
    token = token.strip()
    if not token:
        raise AssemblyError("Empty operand")

    # Check for register (R0-R15)
    upper = token.upper()
    if upper.startswith("R") and len(upper) >= 2 and upper[1:].isdigit():
        return Operand(kind="reg", value=_parse_register(token))

    # Check for immediate (starts with digit, or negative sign, or 0x)
    if token[0].isdigit() or token[0] == "-" or token.startswith(("0x", "0X")):
        return Operand(kind="imm", value=_parse_immediate(token))

    # Otherwise it's a label reference
    return Operand(kind="label", value=token)


def _tokenize_operands(operand_str: str) -> List[str]:
    """Split comma-separated operands, respecting whitespace."""
    parts = operand_str.split(",")
    return [p.strip() for p in parts if p.strip()]


# ── Assembler ─────────────────────────────────────────────────────────────────


class FluxAssembler:
    """Two-pass FLUX assembler for the unified ISA.

    Pass 1: Parse all lines, compute instruction sizes, record label addresses.
    Pass 2: Emit bytecode with all label offsets resolved.
    """

    def __init__(self) -> None:
        self.labels: Dict[str, int] = {}  # label_name -> byte address
        self.instructions: List[ParsedInstruction] = []
        self.errors: List[str] = []

    def assemble(self, source: str) -> List[int]:
        """Assemble FLUX source code into a bytecode list.

        Args:
            source: Assembly source code string.

        Returns:
            List of ints (byte values 0-255) representing the program.

        Raises:
            AssemblyError: If the source has syntax or semantic errors.
        """
        self.labels = {}
        self.instructions = []
        self.errors = []

        lines = self._strip_comments(source)
        parsed = self._parse_lines(lines)
        self.instructions = parsed

        # Pass 1: compute instruction sizes and label addresses
        self._compute_labels()

        if self.errors:
            raise AssemblyError("; ".join(self.errors))

        # Pass 2: emit bytecode with resolved labels
        bytecode = self._emit_bytecode()

        if self.errors:
            raise AssemblyError("; ".join(self.errors))

        return bytecode

    @staticmethod
    def _strip_comments(source: str) -> List[Tuple[str, int]]:
        """Remove comments and blank lines. Returns (stripped_line, line_number) pairs."""
        result = []
        for lineno, line in enumerate(source.split("\n"), 1):
            # Remove ; comments (but not inside strings — we don't have strings)
            comment_pos = line.find(";")
            if comment_pos >= 0:
                line = line[:comment_pos]
            line = line.strip()
            if line:
                result.append((line, lineno))
        return result

    def _parse_lines(self, lines: List[Tuple[str, int]]) -> List[ParsedInstruction]:
        """Parse each line into a ParsedInstruction."""
        instructions = []
        for text, lineno in lines:
            inst = self._parse_line(text, lineno)
            if inst is not None:
                instructions.append(inst)
        return instructions

    def _parse_line(self, text: str, lineno: int) -> Optional[ParsedInstruction]:
        """Parse a single line of assembly."""
        label = None
        rest = text

        # Check for label (ends with :)
        if ":" in text:
            colon_pos = text.index(":")
            label_candidate = text[:colon_pos].strip()
            rest = text[colon_pos + 1:].strip()
            if label_candidate and label_candidate.replace("_", "").isalnum():
                label = label_candidate
            else:
                self.errors.append(f"Line {lineno}: Invalid label name: {label_candidate!r}")

        # If no instruction after label, return label-only entry
        if not rest:
            return ParsedInstruction(label=label, source_line=lineno)

        # Parse mnemonic and operands
        parts = rest.split(None, 1)  # split on first whitespace
        mnemonic = parts[0].strip().upper()
        operand_str = parts[1].strip() if len(parts) > 1 else ""

        # Tokenize operands
        operands = []
        if operand_str:
            tokens = _tokenize_operands(operand_str)
            for tok in tokens:
                operands.append(_parse_operand(tok))

        return ParsedInstruction(
            label=label,
            mnemonic=mnemonic,
            operands=operands,
            source_line=lineno,
        )

    def _instruction_size(self, inst: ParsedInstruction) -> int:
        """Compute the byte size of a parsed instruction (for pass 1).

        Accounts for pseudo-instruction expansion of conditional jumps with labels.
        """
        if inst.mnemonic is None:
            return 0  # label-only line

        mnemonic = inst.mnemonic

        # Check for pseudo-instruction expansion: JNZ/JZ/JLT/JGT reg, label
        if mnemonic in CONDITIONAL_JUMPS and len(inst.operands) >= 2:
            if inst.operands[1].kind == "label":
                # Expands to: MOVI R15, offset (3 bytes) + Jcc Rd, R15 (4 bytes) = 7 bytes
                return 7

        # Check for JMP with label (Format F, 4 bytes)
        if mnemonic in UNCONDITIONAL_JUMPS and len(inst.operands) >= 1:
            # JMP always takes 4 bytes regardless of operand type
            return 4

        # Lookup format size from opcode table
        if mnemonic not in ALL_OPCODES:
            self.errors.append(
                f"Line {inst.source_line}: Unknown mnemonic: {mnemonic!r}"
            )
            return 0

        _, fmt = ALL_OPCODES[mnemonic]
        size_map = {"A": 1, "B": 2, "C": 2, "D": 3, "E": 4, "F": 4, "G": 5}
        return size_map.get(fmt, 1)

    def _compute_labels(self) -> None:
        """Pass 1: Assign byte addresses to all labels."""
        address = 0
        for inst in self.instructions:
            if inst.label is not None:
                if inst.label in self.labels:
                    self.errors.append(f"Duplicate label: {inst.label!r}")
                else:
                    self.labels[inst.label] = address
            address += self._instruction_size(inst)

    def _emit_bytecode(self) -> List[int]:
        """Pass 2: Emit bytecode with all label offsets resolved."""
        bytecode: List[int] = []
        current_address = 0

        for inst in self.instructions:
            if inst.mnemonic is None:
                continue  # label-only line

            mnemonic = inst.mnemonic
            operands = inst.operands

            # ── Pseudo-instruction: conditional jump with label ──────────
            if mnemonic in CONDITIONAL_JUMPS and len(operands) >= 2:
                if operands[1].kind == "label":
                    self._emit_conditional_jump_label(
                        bytecode, inst, current_address
                    )
                    current_address += 7
                    continue

            # ── Pseudo-instruction: JMP/JAL/etc with label ──────────────
            if mnemonic in UNCONDITIONAL_JUMPS:
                self._emit_unconditional_jump(bytecode, inst, current_address)
                current_address += 4
                continue

            # ── Standard instruction emission ────────────────────────────
            if mnemonic not in ALL_OPCODES:
                self.errors.append(
                    f"Line {inst.source_line}: Unknown mnemonic: {mnemonic!r}"
                )
                continue

            opcode, fmt = ALL_OPCODES[mnemonic]
            emitted = self._encode_standard(opcode, fmt, operands, inst.source_line)
            bytecode.extend(emitted)
            current_address += len(emitted)

        return bytecode

    def _emit_conditional_jump_label(
        self,
        bytecode: List[int],
        inst: ParsedInstruction,
        inst_address: int,
    ) -> None:
        """Expand Jcc Rd, label  -->  MOVI R15, offset; Jcc Rd, R15.

        The offset is computed from after the expanded Jcc instruction
        (i.e., from inst_address + 7) to the target label.
        """
        mnemonic = inst.mnemonic
        cond_reg = inst.operands[0]
        label_name = inst.operands[1].value

        if cond_reg.kind != "reg":
            self.errors.append(
                f"Line {inst.source_line}: {mnemonic} requires register as first operand, "
                f"got {cond_reg.kind}"
            )
            return

        if label_name not in self.labels:
            self.errors.append(
                f"Line {inst.source_line}: Undefined label: {label_name!r}"
            )
            return

        target_addr = self.labels[label_name]
        # After the expanded 7-byte sequence, PC = inst_address + 7
        pc_after = inst_address + 7
        offset = target_addr - pc_after

        # Check i8 range
        if offset < -128 or offset > 127:
            self.errors.append(
                f"Line {inst.source_line}: Conditional jump offset {offset} "
                f"exceeds i8 range [-128, 127]. Label: {label_name!r}"
            )
            return

        # Encode MOVI R15, offset (Format D: [0x18][R15][offset_i8])
        bytecode.extend(encode_format_d(0x18, SCRATCH_REG, offset))

        # Encode Jcc Rd, R15, 0 (Format E: [op][rd][rs1][rs2=0])
        jcc_opcode = ALL_OPCODES[mnemonic][0]
        bytecode.extend(encode_format_e(jcc_opcode, cond_reg.value, SCRATCH_REG, 0))

    def _emit_unconditional_jump(
        self,
        bytecode: List[int],
        inst: ParsedInstruction,
        inst_address: int,
    ) -> None:
        """Emit JMP/JAL/etc with label or immediate offset (Format F)."""
        mnemonic = inst.mnemonic
        opcode = ALL_OPCODES[mnemonic][0]

        if len(inst.operands) == 0:
            self.errors.append(
                f"Line {inst.source_line}: {mnemonic} requires an operand"
            )
            return

        operand = inst.operands[0]

        if operand.kind == "label":
            if operand.value not in self.labels:
                self.errors.append(
                    f"Line {inst.source_line}: Undefined label: {operand.value!r}"
                )
                return
            target_addr = self.labels[operand.value]
            # After the 4-byte JMP, PC = inst_address + 4
            pc_after = inst_address + 4
            offset = target_addr - pc_after

            # Check i16 range
            if offset < -32768 or offset > 32767:
                self.errors.append(
                    f"Line {inst.source_line}: Jump offset {offset} "
                    f"exceeds i16 range. Label: {operand.value!r}"
                )
                return

            # Format F: [op][rd=0][imm16hi][imm16lo]
            rd = 0
            if len(inst.operands) >= 2 and inst.operands[1].kind == "reg":
                rd = inst.operands[1].value
            bytecode.extend(encode_format_f(opcode, rd, offset))
        else:
            # Immediate offset (unusual but supported)
            offset = operand.value if operand.kind == "imm" else 0
            rd = 0
            if len(inst.operands) >= 2 and inst.operands[1].kind == "reg":
                rd = inst.operands[1].value
            bytecode.extend(encode_format_f(opcode, rd, offset))

    def _encode_standard(
        self,
        opcode: int,
        fmt: str,
        operands: List[Operand],
        lineno: int,
    ) -> List[int]:
        """Encode a standard (non-pseudo-instruction) based on its format."""
        if fmt == "A":
            return [opcode]

        elif fmt == "B":
            # [op][rd]
            if len(operands) < 1 or operands[0].kind != "reg":
                self.errors.append(
                    f"Line {lineno}: {fmt}-format instruction requires register operand"
                )
                return [opcode, 0]
            return encode_format_b(opcode, operands[0].value)

        elif fmt == "C":
            # [op][imm8]
            if len(operands) < 1:
                self.errors.append(
                    f"Line {lineno}: C-format instruction requires immediate operand"
                )
                return [opcode, 0]
            val = operands[0].value if operands[0].kind == "imm" else 0
            return encode_format_c(opcode, val & 0xFF)

        elif fmt == "D":
            # [op][rd][imm8]
            if len(operands) < 2:
                self.errors.append(
                    f"Line {lineno}: D-format instruction requires rd, imm8"
                )
                return [opcode, 0, 0]
            if operands[0].kind != "reg":
                self.errors.append(
                    f"Line {lineno}: D-format first operand must be register"
                )
                return [opcode, 0, 0]
            rd = operands[0].value
            imm = operands[1].value if operands[1].kind == "imm" else 0
            return encode_format_d(opcode, rd, imm)

        elif fmt == "E":
            # [op][rd][rs1][rs2]
            rd = 0
            rs1 = 0
            rs2 = 0

            if len(operands) >= 1:
                if operands[0].kind == "reg":
                    rd = operands[0].value
                else:
                    self.errors.append(
                        f"Line {lineno}: E-format first operand must be register"
                    )
            if len(operands) >= 2:
                if operands[1].kind == "reg":
                    rs1 = operands[1].value
                elif operands[1].kind == "imm":
                    rs1 = operands[1].value & 0xFF
                else:
                    self.errors.append(
                        f"Line {lineno}: E-format second operand must be register or immediate"
                    )
            if len(operands) >= 3:
                if operands[2].kind == "reg":
                    rs2 = operands[2].value
                elif operands[2].kind == "imm":
                    rs2 = operands[2].value & 0xFF

            return encode_format_e(opcode, rd, rs1, rs2)

        elif fmt == "F":
            # [op][rd][imm16hi][imm16lo]
            rd = 0
            imm16 = 0

            if len(operands) >= 1 and operands[0].kind == "reg":
                rd = operands[0].value
            elif len(operands) >= 1 and operands[1] if len(operands) >= 2 else None:
                pass  # handled below

            # For F-format: first operand is rd, second is imm16
            if len(operands) >= 1:
                if operands[0].kind == "reg":
                    rd = operands[0].value
                    if len(operands) >= 2 and operands[1].kind == "imm":
                        imm16 = operands[1].value
                elif operands[0].kind == "imm":
                    imm16 = operands[0].value

            return encode_format_f(opcode, rd, imm16)

        elif fmt == "G":
            # [op][rd][rs1][imm16hi][imm16lo]
            rd = 0
            rs1 = 0
            imm16 = 0

            if len(operands) >= 1 and operands[0].kind == "reg":
                rd = operands[0].value
            if len(operands) >= 2 and operands[1].kind == "reg":
                rs1 = operands[1].value
            if len(operands) >= 3 and operands[2].kind == "imm":
                imm16 = operands[2].value

            return encode_format_g(opcode, rd, rs1, imm16)

        else:
            self.errors.append(f"Line {lineno}: Unknown format: {fmt!r}")
            return [opcode]

    def disassemble(self, bytecode: List[int]) -> str:
        """Disassemble bytecode back to assembly text (for debugging).

        Args:
            bytecode: List of byte values.

        Returns:
            Human-readable assembly text.
        """
        lines = []
        i = 0
        while i < len(bytecode):
            op = bytecode[i]
            name = self._opcode_name(op)

            if op <= 0x07 or op >= 0xF0:
                lines.append(f"  {i:04d}: {name}")
                i += 1
            elif op <= 0x0F:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                lines.append(f"  {i:04d}: {name} R{rd}")
                i += 2
            elif op <= 0x17:
                imm = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                lines.append(f"  {i:04d}: {name} {imm}")
                i += 2
            elif op <= 0x1F:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                imm = bytecode[i + 2] if i + 2 < len(bytecode) else 0
                if imm >= 128:
                    imm -= 256
                lines.append(f"  {i:04d}: {name} R{rd}, {imm}")
                i += 3
            elif op <= 0x3F:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                rs1 = bytecode[i + 2] if i + 2 < len(bytecode) else 0
                rs2 = bytecode[i + 3] if i + 3 < len(bytecode) else 0
                lines.append(f"  {i:04d}: {name} R{rd}, R{rs1}, R{rs2}")
                i += 4
            elif op <= 0x47:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                hi = bytecode[i + 2] if i + 2 < len(bytecode) else 0
                lo = bytecode[i + 3] if i + 3 < len(bytecode) else 0
                imm16 = (hi << 8) | lo
                if imm16 >= 0x8000:
                    imm16 -= 0x10000
                lines.append(f"  {i:04d}: {name} R{rd}, {imm16}")
                i += 4
            elif op <= 0x4F:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                rs1 = bytecode[i + 2] if i + 2 < len(bytecode) else 0
                hi = bytecode[i + 3] if i + 3 < len(bytecode) else 0
                lo = bytecode[i + 4] if i + 4 < len(bytecode) else 0
                imm16 = (hi << 8) | lo
                if imm16 >= 0x8000:
                    imm16 -= 0x10000
                lines.append(f"  {i:04d}: {name} R{rd}, R{rs1}, {imm16}")
                i += 5
            elif op <= 0x6F:
                rd = bytecode[i + 1] if i + 1 < len(bytecode) else 0
                rs1 = bytecode[i + 2] if i + 2 < len(bytecode) else 0
                rs2 = bytecode[i + 3] if i + 3 < len(bytecode) else 0
                lines.append(f"  {i:04d}: {name} R{rd}, R{rs1}, R{rs2}")
                i += 4
            else:
                lines.append(f"  {i:04d}: {name}")
                i += 1

        return "\n".join(lines)

    @staticmethod
    def _opcode_name(op: int) -> str:
        """Look up the mnemonic for an opcode byte."""
        for name, (code, _) in ALL_OPCODES.items():
            if code == op:
                return name
        return f"UNKNOWN_0x{op:02X}"


# ── Encoding helpers (matching formats.py exactly) ─────────────────────────────


def encode_format_a(opcode: int) -> List[int]:
    """Format A: [op] — 1 byte."""
    return [opcode & 0xFF]


def encode_format_b(opcode: int, rd: int) -> List[int]:
    """Format B: [op][rd] — 2 bytes."""
    return [opcode & 0xFF, rd & 0xFF]


def encode_format_c(opcode: int, imm8: int) -> List[int]:
    """Format C: [op][imm8] — 2 bytes."""
    return [opcode & 0xFF, imm8 & 0xFF]


def encode_format_d(opcode: int, rd: int, imm8: int) -> List[int]:
    """Format D: [op][rd][imm8] — 3 bytes.

    imm8 is sign-extended by the interpreter. The raw byte stored is the
    two's-complement representation of the signed value.
    """
    if imm8 < 0:
        imm8 = imm8 + 256
    return [opcode & 0xFF, rd & 0xFF, imm8 & 0xFF]


def encode_format_e(opcode: int, rd: int, rs1: int, rs2: int) -> List[int]:
    """Format E: [op][rd][rs1][rs2] — 4 bytes."""
    return [opcode & 0xFF, rd & 0xFF, rs1 & 0xFF, rs2 & 0xFF]


def encode_format_f(opcode: int, rd: int, imm16: int) -> List[int]:
    """Format F: [op][rd][imm16hi][imm16lo] — 4 bytes.

    imm16 is stored big-endian. Signed values are stored as two's complement.
    """
    if imm16 < 0:
        imm16 = imm16 + 0x10000
    return [
        opcode & 0xFF,
        rd & 0xFF,
        (imm16 >> 8) & 0xFF,
        imm16 & 0xFF,
    ]


def encode_format_g(opcode: int, rd: int, rs1: int, imm16: int) -> List[int]:
    """Format G: [op][rd][rs1][imm16hi][imm16lo] — 5 bytes."""
    if imm16 < 0:
        imm16 = imm16 + 0x10000
    return [
        opcode & 0xFF,
        rd & 0xFF,
        rs1 & 0xFF,
        (imm16 >> 8) & 0xFF,
        imm16 & 0xFF,
    ]


# ── Convenience API ───────────────────────────────────────────────────────────


def assemble(source: str) -> List[int]:
    """Convenience function: assemble FLUX source into bytecode list.

    Args:
        source: Assembly source code string.

    Returns:
        List of ints (byte values 0-255).

    Raises:
        AssemblyError: On syntax or semantic errors.
    """
    asm = FluxAssembler()
    return asm.assemble(source)


def disassemble(bytecode: List[int]) -> str:
    """Convenience function: disassemble bytecode back to text.

    Args:
        bytecode: List of byte values.

    Returns:
        Human-readable assembly text.
    """
    asm = FluxAssembler()
    return asm.disassemble(bytecode)
