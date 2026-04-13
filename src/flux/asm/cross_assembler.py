"""FLUX Cross-Assembler — assembles FLUX bytecode from text with labels, expressions, and multiple output formats.

Supports:
  - Labels (name:)
  - Forward/backward references to labels
  - Arithmetic expressions in operands
  - Comments (; or //)
  - Multiple output formats: binary, hex, JSON, Intel hex
  - Register references (R0-R63 or just 0-63)
  - String constants (e.g., for .ascii, .asciz directives)

Output formats:
  - binary: raw FLUX bytecode bytes
  - hex: space-separated hex bytes (human-readable)
  - json: structured JSON with metadata
  - intel_hex: Intel HEX format (.hex)
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
from typing import Optional, Union

from .opcodes_compat import OPCODE_DEFS, OpcodeDef, parse_register
from .errors import AsmError, AsmErrorKind, SourceLocation
from .macros import MacroPreprocessor


class OutputFormat(Enum):
    """Supported output formats."""
    BINARY = "binary"
    HEX = "hex"
    JSON = "json"
    INTEL_HEX = "intel_hex"
    PYTHON_LIST = "python_list"


@dataclass
class AssemblyResult:
    """Result of assembling a source file."""
    bytecode: bytes
    format: OutputFormat = OutputFormat.BINARY
    symbol_table: dict[str, int] = field(default_factory=dict)
    source_map: list[dict] = field(default_factory=list)
    errors: list[AsmError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_binary(self) -> bytes:
        """Return raw bytecode bytes."""
        return self.bytecode

    def as_hex(self) -> str:
        """Return space-separated hex string."""
        return " ".join(f"{b:02x}" for b in self.bytecode)

    def as_json(self) -> str:
        """Return JSON representation."""
        data = {
            "format": "flux-bytecode",
            "size": len(self.bytecode),
            "bytecode_hex": self.as_hex(),
            "symbols": self.symbol_table,
            "source_map": self.source_map,
        }
        return json.dumps(data, indent=2)

    def as_intel_hex(self) -> str:
        """Return Intel HEX format string."""
        return _to_intel_hex(self.bytecode)

    def as_python_list(self) -> list[int]:
        """Return bytecode as a Python list of integers."""
        return list(self.bytecode)


class CrossAssembler:
    """Assembles FLUX assembly text into bytecode with full feature support.

    Features:
        - Labels and forward references (two-pass assembly)
        - Register operands (R0-R63)
        - Immediate values (decimal, hex 0x, binary 0b)
        - Arithmetic expressions in operands
        - Multiple output formats
        - Data directives (.byte, .word, .ascii, .asciz, .fill)
        - Macro preprocessing via MacroPreprocessor
    """

    def __init__(
        self,
        include_paths: Optional[list[str]] = None,
        defines: Optional[dict[str, str]] = None,
        origin: int = 0,
        preprocess: bool = True,
    ):
        self.include_paths = include_paths or ["."]
        self.defines = defines or {}
        self.origin = origin
        self.preprocess = preprocess
        self.errors: list[AsmError] = []
        self.warnings: list[str] = []

    def assemble(
        self,
        source: str,
        filename: str = "<input>",
        output_format: OutputFormat = OutputFormat.BINARY,
    ) -> AssemblyResult:
        """Assemble source text into bytecode.

        Args:
            source: Assembly source text.
            filename: Source file name for error messages.
            output_format: Desired output format.

        Returns:
            AssemblyResult with bytecode and metadata.
        """
        self.errors = []
        self.warnings = []

        # Preprocess (macros, includes, conditionals)
        if self.preprocess:
            preprocessor = MacroPreprocessor(
                include_paths=self.include_paths,
                defines=self.defines,
            )
            try:
                source = preprocessor.preprocess(source, filename=filename)
            except AsmError as e:
                self.errors.append(e)
                return AssemblyResult(
                    bytecode=b"", format=output_format,
                    errors=self.errors, warnings=self.warnings,
                )
            self.errors.extend(preprocessor.errors)

        # Parse and assemble (two-pass)
        try:
            result = self._two_pass_assemble(source, filename)
        except AsmError as e:
            self.errors.append(e)
            return AssemblyResult(
                bytecode=b"", format=output_format,
                errors=self.errors, warnings=self.warnings,
            )

        result.format = output_format
        result.errors = self.errors
        result.warnings = self.warnings
        return result

    def assemble_file(
        self,
        path: str,
        output_format: OutputFormat = OutputFormat.BINARY,
    ) -> AssemblyResult:
        """Assemble a source file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
        except IOError as e:
            err = AsmError(
                message=f"Cannot read file '{path}': {e}",
                kind=AsmErrorKind.IO_ERROR,
            )
            self.errors.append(err)
            return AssemblyResult(
                bytecode=b"", format=output_format, errors=self.errors,
            )
        return self.assemble(source, filename=path, output_format=output_format)

    def _two_pass_assemble(self, source: str, filename: str) -> AssemblyResult:
        """Two-pass assembly: collect labels, then emit bytecode."""
        lines = source.split("\n")

        # Pass 1: Collect labels and compute addresses
        labels: dict[str, int] = {}
        stripped_lines: list[tuple[int, str, str]] = []  # (line_num, text, raw_line)

        addr = self.origin
        for line_num, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith(";") or stripped.startswith("//"):
                continue

            # Skip # comments but NOT preprocessor directives (#define, #ifdef, etc.)
            if stripped.startswith("#") and not any(
                stripped.startswith(d) for d in (
                    "#define", "#undef", "#ifdef", "#ifndef", "#endif", "#else", "#include"
                )
            ):
                continue

            # Remove inline comments
            for prefix in (";", "//"):
                if prefix in stripped:
                    # Don't strip if inside a string literal
                    idx = stripped.find(prefix)
                    in_str = stripped[:idx].count('"') % 2 == 1
                    if not in_str:
                        stripped = stripped[:idx].strip()
                        break

            if not stripped:
                continue

            # Check for label definition (@label or name:)
            if stripped.endswith(":"):
                label_name = stripped[:-1].strip()
                if label_name in labels:
                    raise AsmError(
                        message=f"Duplicate label: {label_name}",
                        kind=AsmErrorKind.DUPLICATE_LABEL,
                        location=SourceLocation(
                            file=filename, line=line_num,
                            column=1, source_line=raw_line.rstrip(),
                        ),
                    )
                labels[label_name] = addr
                continue

            # Check for @label syntax (alternative label definition)
            if stripped.startswith("@"):
                label_name = stripped[1:].strip()
                # Remove any trailing comment
                for prefix in (";", "//"):
                    if prefix in label_name:
                        label_name = label_name[:label_name.find(prefix)].strip()
                if not label_name:
                    continue
                if label_name in labels:
                    raise AsmError(
                        message=f"Duplicate label: {label_name}",
                        kind=AsmErrorKind.DUPLICATE_LABEL,
                        location=SourceLocation(
                            file=filename, line=line_num,
                            column=1, source_line=raw_line.rstrip(),
                        ),
                    )
                labels[label_name] = addr
                continue

            # Check for data directives
            if stripped.startswith("."):
                size = self._estimate_directive_size(stripped)
                addr += size
                stripped_lines.append((line_num, stripped, raw_line))
                continue

            # Regular instruction — estimate size
            size = self._estimate_instruction_size(stripped, labels)
            addr += size
            stripped_lines.append((line_num, stripped, raw_line))

        # Pass 2: Emit bytecode
        bytecode = bytearray()
        source_map: list[dict] = []

        for line_num, stripped, raw_line in stripped_lines:
            loc = SourceLocation(
                file=filename, line=line_num, column=1, source_line=raw_line.rstrip()
            )
            offset = len(bytecode)

            # Handle directives
            if stripped.startswith("."):
                self._emit_directive(stripped, labels, bytecode, loc)
            else:
                self._emit_instruction(stripped, labels, bytecode, loc)

            if bytecode:
                source_map.append({
                    "offset": offset,
                    "length": len(bytecode) - offset,
                    "file": filename,
                    "line": line_num,
                })

        return AssemblyResult(
            bytecode=bytes(bytecode),
            symbol_table=labels,
            source_map=source_map,
        )

    def _estimate_instruction_size(self, line: str, labels: dict[str, int]) -> int:
        """Estimate the byte size of an instruction."""
        parts = line.replace(",", " ").split()
        if not parts:
            return 0

        mnemonic = parts[0].upper()
        if mnemonic not in OPCODE_DEFS:
            return 1  # unknown, assume 1

        op_def = OPCODE_DEFS[mnemonic]
        return op_def.size

    def _estimate_directive_size(self, line: str) -> int:
        """Estimate the byte size of a directive."""
        parts = line.split(None, 1)
        if not parts:
            return 0
        directive = parts[0].lower()

        if directive == ".byte":
            args = parts[1].split(",") if len(parts) > 1 else []
            return len(args)
        elif directive == ".word":
            args = parts[1].split(",") if len(parts) > 1 else []
            return len(args) * 2
        elif directive == ".dword":
            args = parts[1].split(",") if len(parts) > 1 else []
            return len(args) * 4
        elif directive == ".ascii":
            match = re.search(r'"([^"]*)"', line)
            return len(match.group(1)) if match else 0
        elif directive == ".asciz":
            match = re.search(r'"([^"]*)"', line)
            return (len(match.group(1)) + 1) if match else 1
        elif directive == ".fill":
            args = parts[1].split(",") if len(parts) > 1 else []
            count = self._eval_expr(args[0].strip(), {}) if args else 0
            return max(0, int(count))
        elif directive == ".align":
            args = parts[1].split(",") if len(parts) > 1 else []
            alignment = self._eval_expr(args[0].strip(), {}) if args else 1
            alignment = max(1, int(alignment))
            # We don't know current address here perfectly; approximate
            return 0  # alignment is handled in emit
        elif directive == ".org":
            return 0
        return 0

    def _emit_directive(
        self, line: str, labels: dict[str, int], bytecode: bytearray,
        loc: SourceLocation,
    ) -> None:
        """Emit bytes for a data directive."""
        parts = line.split(None, 1)
        directive = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if directive == ".byte":
            for arg in rest.split(","):
                arg = arg.strip()
                val = self._eval_expr(arg, labels)
                bytecode.append(val & 0xFF)

        elif directive == ".word":
            for arg in rest.split(","):
                arg = arg.strip()
                val = self._eval_expr(arg, labels)
                bytecode.extend(struct.pack("<H", val & 0xFFFF))

        elif directive == ".dword":
            for arg in rest.split(","):
                arg = arg.strip()
                val = self._eval_expr(arg, labels)
                bytecode.extend(struct.pack("<I", val & 0xFFFFFFFF))

        elif directive == ".ascii":
            match = re.search(r'"([^"]*)"', line)
            if match:
                text = self._unescape_string(match.group(1))
                bytecode.extend(text.encode("utf-8"))

        elif directive == ".asciz":
            match = re.search(r'"([^"]*)"', line)
            if match:
                text = self._unescape_string(match.group(1))
                bytecode.extend(text.encode("utf-8"))
                bytecode.append(0x00)  # null terminator

        elif directive == ".fill":
            args = rest.split(",")
            count = self._eval_expr(args[0].strip(), labels) if args else 0
            fill_val = self._eval_expr(args[1].strip(), labels) if len(args) > 1 else 0
            for _ in range(max(0, int(count))):
                bytecode.append(fill_val & 0xFF)

        elif directive == ".align":
            args = rest.split(",")
            alignment = self._eval_expr(args[0].strip(), labels) if args else 1
            alignment = max(1, int(alignment))
            fill_val = self._eval_expr(args[1].strip(), labels) if len(args) > 1 else 0
            current = len(bytecode)
            pad = (-current) % alignment
            for _ in range(pad):
                bytecode.append(fill_val & 0xFF)

        elif directive == ".org":
            addr = self._eval_expr(rest.strip(), labels)
            # Pad to reach target address
            while len(bytecode) < addr:
                bytecode.append(0x00)

    def _emit_instruction(
        self, line: str, labels: dict[str, int], bytecode: bytearray,
        loc: SourceLocation,
    ) -> None:
        """Emit bytes for a single instruction."""
        parts = line.replace(",", " ").split()
        if not parts:
            return

        mnemonic = parts[0].upper()

        if mnemonic not in OPCODE_DEFS:
            raise AsmError(
                message=f"Unknown mnemonic: {mnemonic}",
                kind=AsmErrorKind.UNKNOWN_OPCODE,
                location=loc,
                hints=[f"Did you mean one of: {', '.join(sorted(OPCODE_DEFS.keys())[:10])}?"],
            )

        op_def = OPCODE_DEFS[mnemonic]
        operands = parts[1:]

        if len(operands) < op_def.min_operands:
            raise AsmError(
                message=f"{mnemonic} expects at least {op_def.min_operands} operands, got {len(operands)}",
                kind=AsmErrorKind.MISSING_OPERAND,
                location=loc,
            )

        if len(operands) > op_def.max_operands:
            raise AsmError(
                message=f"{mnemonic} expects at most {op_def.max_operands} operands, got {len(operands)}",
                kind=AsmErrorKind.TOO_MANY_OPERANDS,
                location=loc,
            )

        # Encode based on format
        opcode_byte = op_def.opcode

        if op_def.format == "A":
            # No operands
            bytecode.append(opcode_byte)

        elif op_def.format == "B":
            # One register operand
            reg = parse_register(operands[0], loc)
            bytecode.append(opcode_byte)
            bytecode.append(reg)

        elif op_def.format == "C":
            # Two register operands
            rd = parse_register(operands[0], loc)
            rs1 = parse_register(operands[1], loc)
            bytecode.append(opcode_byte)
            bytecode.append(rd)
            bytecode.append(rs1)

        elif op_def.format == "D":
            # Register + immediate16 (or just immediate16 with default reg 0)
            if len(operands) == 1:
                # JMP-style: just an immediate/label, default register=0
                rs1 = 0
                imm = self._eval_expr(operands[0], labels)
            else:
                rs1 = parse_register(operands[0], loc)
                imm = self._eval_expr(operands[1], labels)
            if imm < -32768 or imm > 65535:
                self.warnings.append(
                    f"{loc}: immediate {imm} truncated to 16-bit"
                )
            bytecode.append(opcode_byte)
            bytecode.append(rs1)
            imm_clamped = max(-32768, min(32767, imm))
            bytecode.extend(struct.pack("<h", imm_clamped))

        elif op_def.format == "E":
            # Three register operands
            rd = parse_register(operands[0], loc)
            rs1 = parse_register(operands[1], loc)
            rs2 = parse_register(operands[2], loc)
            bytecode.append(opcode_byte)
            bytecode.append(rd)
            bytecode.append(rs1)
            bytecode.append(rs2)

        elif op_def.format == "F":
            # Register + 16-bit immediate (unsigned for jumps)
            rd = parse_register(operands[0], loc)
            imm = self._eval_expr(operands[1], labels)
            bytecode.append(opcode_byte)
            bytecode.append(rd)
            bytecode.extend(struct.pack("<H", imm & 0xFFFF))

    def _eval_expr(self, expr: str, labels: dict[str, int]) -> int:
        """Evaluate a constant expression (immediate value or label reference)."""
        expr = expr.strip()

        # Direct hex, binary, decimal
        try:
            return self._parse_int(expr)
        except ValueError:
            pass

        # Label reference
        if expr in labels:
            return labels[expr]

        # Try to evaluate as expression with labels substituted
        try:
            resolved = expr
            for label_name, label_addr in sorted(labels.items(), key=lambda x: -len(x[0])):
                resolved = resolved.replace(label_name, str(label_addr))
            return int(eval(resolved, {"__builtins__": {}}, {}))
        except Exception:
            raise AsmError(
                message=f"Cannot evaluate expression: {expr}",
                kind=AsmErrorKind.INVALID_OPERAND,
            )

    @staticmethod
    def _parse_int(s: str) -> int:
        """Parse an integer literal (decimal, hex, binary)."""
        s = s.strip()
        neg = False
        if s.startswith("-"):
            neg = True
            s = s[1:]

        if s.startswith("0x") or s.startswith("0X"):
            val = int(s, 16)
        elif s.startswith("0b") or s.startswith("0B"):
            val = int(s, 2)
        else:
            val = int(s)

        return -val if neg else val

    @staticmethod
    def _unescape_string(s: str) -> str:
        """Process escape sequences in a string literal."""
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                c = s[i + 1]
                if c == 'n':
                    result.append('\n')
                elif c == 't':
                    result.append('\t')
                elif c == 'r':
                    result.append('\r')
                elif c == '0':
                    result.append('\0')
                elif c == '\\':
                    result.append('\\')
                elif c == '"':
                    result.append('"')
                else:
                    result.append(c)
                i += 2
            else:
                result.append(s[i])
                i += 1
        return "".join(result)


def _to_intel_hex(data: bytes) -> str:
    """Convert raw bytes to Intel HEX format string."""
    lines = []
    addr = 0

    while addr < len(data):
        chunk_size = min(16, len(data) - addr)
        chunk = data[addr:addr + chunk_size]

        # Build record: :LLAAAATT[DD...]CC
        # LL = byte count, AAAA = address, TT = record type (00=data)
        checksum = chunk_size + (addr >> 8) & 0xFF + addr & 0xFF + 0x00
        for b in chunk:
            checksum += b
        checksum = (-checksum) & 0xFF

        record = f":{chunk_size:02X}{addr:04X}00"
        record += "".join(f"{b:02X}" for b in chunk)
        record += f"{checksum:02X}"
        lines.append(record)

        addr += chunk_size

    # End-of-file record
    lines.append(":00000001FF")
    return "\n".join(lines)
