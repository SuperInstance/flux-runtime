"""Open-Flux-Interpreter: Convert markdown/text directly to FLUX bytecode and execute.

This is the "kill app" for agent workflows — an agent can write an idea in markdown,
run it as compute, and keep thinking without switching context.

Example:
    Input markdown:
    ```
    # Compute factorial of 10

    Load R0 with 10
    Load R1 with 1
    While R0 is not zero:
        Multiply R1 by R0
        Decrease R0
    Return R1
    ```

    This gets converted to:
    MOVI R0, 10
    MOVI R1, 1
    loop:
    IMUL R1, R1, R0
    DEC R0
    JNZ R0, loop
    HALT

    And executed immediately, returning R1 = 3628800
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Any

from flux.bytecode.opcodes import Op
from flux.disasm import DisassemblyResult, FluxDisassembler
from flux.vm.interpreter import Interpreter, VMError
from flux.vm.registers import RegisterFile

# ── Markdown code fences ────────────────────────────────────────────────────────
# Any triple-backtick fence with an optional language tag. Non-FLUX fences (e.g.
# ```python) must NEVER be fed to the natural-language parser — that is what
# mangled Python ``return`` into ``'ETURN'`` (see SEAM-REPORT.md bug #1).
_FENCE_RE = re.compile(r"```([A-Za-z0-9_+.-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)

# ── System A instruction formats (must match flux.vm.interpreter decodes) ─────
# Format A: opcode only (1 byte)
_FMT_A = frozenset({"NOP", "HALT", "RET", "DUP", "SWAP", "YIELD"})
# Format B: opcode + register (2 bytes)
_FMT_B = frozenset({"INC", "DEC", "PUSH", "POP", "SETCC", "ENTER", "LEAVE"})
# Format C: opcode + rd + rs1 (3 bytes)
_FMT_C = frozenset({
    "MOV", "LOAD", "STORE", "INEG", "INOT", "IEQ", "ILT", "ILE", "IGT", "IGE",
    "TEST", "ALLOCA", "CMP", "CAST", "BOX", "UNBOX", "CHECK_TYPE",
    "CHECK_BOUNDS", "CALL_IND", "LOAD8", "STORE8",
})
# Format D: opcode + rs1 + imm16 (4 bytes) — MOVI is handled separately
_FMT_D = frozenset({
    "JMP", "JZ", "JNZ", "JE", "JNE", "JG", "JL", "JGE", "JLE", "CALL",
    "TAILCALL",
})
# Format E: opcode + rd + rs1 + rs2 (4 bytes)
_FMT_E = frozenset({
    "IADD", "ISUB", "IMUL", "IDIV", "IMOD", "IREM", "IAND", "IOR", "IXOR",
    "ISHL", "ISHR", "ROTL", "ROTR",
})
# Every mnemonic the assembly path can emit (used for assembly detection).
_ASSEMBLY_OPCODES = _FMT_A | _FMT_B | _FMT_C | _FMT_D | _FMT_E | {"MOVI"}

# Opcode alias normalization (mnemonics accepted but not in the Op enum).
_OPCODE_ALIASES = {"JGT": "JG"}


_RE_REG = re.compile(r"[rR]\d+")
_RE_IMM = re.compile(r"-?\d+|0[xX][0-9a-fA-F]+")


def _is_register_token(token: str) -> bool:
    """True if the token names a general-purpose register (R0-R15)."""
    return bool(_RE_REG.fullmatch(token))


def _is_immediate_token(token: str) -> bool:
    """True if the token is a numeric immediate (decimal or hex)."""
    return bool(_RE_IMM.fullmatch(token))

# ── Result Data Structures ─────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    """Result of executing Open-Flux-Interpreter code."""
    success: bool
    bytecode: bytes
    disassembly: str
    result: int | None = None
    registers: dict[int, int] = field(default_factory=dict)
    cycles: int = 0
    error: str | None = None
    halted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "bytecode_hex": self.bytecode.hex(),
            "disassembly": self.disassembly,
            "result": self.result,
            "registers": self.registers,
            "cycles": self.cycles,
            "error": self.error,
            "halted": self.halted,
        }


# ── Main Interpreter Class ─────────────────────────────────────────────────────

class OpenFluxInterpreter:
    """Converts markdown/text directly to FLUX bytecode and executes it.

    Supports:
    - Natural language patterns (load, add, multiply, while, if, etc.)
    - Direct FLUX assembly code blocks
    - Mathematical notation (factorial, fibonacci, sum)
    - A2A agent communication patterns
    - Interactive mode with rich output
    """

    def __init__(self, max_cycles: int = 1_000_000):
        """Initialize the interpreter.

        Args:
            max_cycles: Maximum execution cycles for safety.
        """
        self.max_cycles = max_cycles
        self._a2a_messages: list[dict[str, Any]] = []

    def interpret(self, input_text: str) -> ExecutionResult:
        """Interpret input text and execute it.

        Args:
            input_text: Markdown, plain text, or FLUX assembly code.

        Returns:
            ExecutionResult with bytecode, disassembly, and execution results.
        """
        try:
            # Parse input and generate bytecode
            bytecode = self._parse_to_bytecode(input_text)

            # Disassemble for display
            disasm = FluxDisassembler(color_output=False)
            disasm_result = disasm.disassemble(bytecode)
            disassembly_text = self._format_disassembly(disasm_result)

            # Execute bytecode
            vm = Interpreter(bytecode, max_cycles=self.max_cycles, isa="system_a")
            vm.on_a2a(self._a2a_handler)

            try:
                cycles = vm.execute()
                result = vm.regs.read_gp(0)

                # Collect non-zero registers (excluding SP/R11 which is stack pointer)
                registers = {}
                for i in range(16):
                    if i == 11:  # Skip stack pointer
                        continue
                    val = vm.regs.read_gp(i)
                    if val != 0:
                        registers[i] = val

                return ExecutionResult(
                    success=True,
                    bytecode=bytecode,
                    disassembly=disassembly_text,
                    result=result,
                    registers=registers,
                    cycles=cycles,
                    halted=vm.halted,
                )
            except VMError as e:
                return ExecutionResult(
                    success=False,
                    bytecode=bytecode,
                    disassembly=disassembly_text,
                    error=str(e),
                    cycles=vm.cycle_count,
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                bytecode=b"",
                disassembly="",
                error=f"Parse error: {e}",
            )

    def _a2a_handler(self, opcode_name: str, data: bytes) -> None:
        """Handle A2A opcodes during execution."""
        self._a2a_messages.append({
            "opcode": opcode_name,
            "data": data.hex(),
        })

    def get_a2a_messages(self) -> list[dict[str, Any]]:
        """Get all A2A messages sent during execution."""
        return self._a2a_messages.copy()

    # ── Parsing ─────────────────────────────────────────────────────────────────

    def _parse_to_bytecode(self, input_text: str) -> bytes:
        """Parse input text and generate FLUX bytecode.

        Handles multiple input formats:
        1. FLUX assembly code blocks (```flux ... ```)
        2. Bare FLUX assembly (first token is a known opcode)
        3. Natural language patterns
        4. Mathematical notation
        5. A2A agent patterns

        Raises:
            ValueError: If no FLUX instructions can be recognized in the input
                (garbage input must error, not silently no-op — SEAM-REPORT
                bug #3).
        """
        bytecode = bytearray()

        # Extract ALL code fences (any language), then pick out ```flux ones.
        fences = self._extract_fences(input_text)
        flux_blocks = [content for lang, content in fences if lang.lower() == "flux"]

        if flux_blocks:
            # Direct FLUX assembly - parse and encode
            for block in flux_blocks:
                bytecode.extend(self._parse_flux_assembly(block))
        elif fences:
            # Markdown with ONLY non-FLUX fences (e.g. ```python): the fenced
            # content is not FLUX code and must not be run through the
            # natural-language parser (that mangled ``return`` into ``'ETURN'``
            # — SEAM-REPORT bug #1). Parse the surrounding prose instead.
            prose = self._strip_fences(input_text).strip()
            if not prose:
                langs = sorted({(lang or "(none)") for lang, _ in fences})
                raise ValueError(
                    "No FLUX code found: markdown contains only non-FLUX code "
                    f"fences (language(s): {', '.join(langs)}). Use ```flux "
                    "fences for FLUX assembly."
                )
            bytecode.extend(self._parse_natural_language(prose))
        elif self._looks_like_assembly(input_text):
            # Bare assembly text (no fence) — SEAM-REPORT bug #2: this used to
            # be routed to the natural-language parser, which compiled every
            # opcode to ISUB.
            bytecode.extend(self._parse_flux_assembly(input_text))
        else:
            # Try to parse as natural language or math notation
            bytecode.extend(self._parse_natural_language(input_text.strip()))

        if not bytecode:
            raise ValueError(
                "No FLUX instructions recognized in input. Expected FLUX "
                "assembly (e.g. 'MOVI R0, 42'), a ```flux code block, or "
                "natural language (e.g. 'compute 3 + 4')."
            )

        # Ensure HALT at the end
        # Always append HALT — the last byte might be data that coincidentally
        # equals Op.HALT (e.g., MOVI R0, -32768 encodes as 0x2b 0x00 0x00 0x80)
        bytecode.append(Op.HALT)

        return bytes(bytecode)

    def _extract_fences(self, text: str) -> list[tuple[str, str]]:
        """Extract all triple-backtick code fences as ``(language, content)``.

        A fence with no language tag yields ``("", content)``.
        """
        return [(m.group(1), m.group(2)) for m in _FENCE_RE.finditer(text)]

    def _strip_fences(self, text: str) -> str:
        """Remove all fenced code blocks (markers and content) from markdown.

        Non-FLUX code fences must never be treated as FLUX source; stripping
        them leaves only the surrounding prose for natural-language parsing.
        """
        return _FENCE_RE.sub("", text)

    def _extract_flux_blocks(self, text: str) -> list[str]:
        """Extract FLUX code blocks from markdown.

        Returns list of code blocks without the wrapping ```flux ... ```
        """
        return [content for lang, content in self._extract_fences(text)
                if lang.lower() == "flux"]

    def _looks_like_assembly(self, text: str) -> bool:
        """Detect bare (unfenced) FLUX assembly text.

        A line counts as assembly when its first token is a known opcode and
        its operand list matches that opcode's format (register/immediate
        shapes). Natural-language lines such as ``load R0 with 42`` or
        ``tell agent2 hello`` deliberately do NOT match (wrong arity / unknown
        opcode), so they keep flowing to the natural-language parser.
        """
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith((";", "//", "#")):
                continue
            # Strip inline comments (assembly style).
            for marker in ("//", ";"):
                idx = line.find(marker)
                if idx > 0:
                    line = line[:idx].strip()
                    break
            if not line:
                continue
            if line.startswith("@"):
                continue
            # Peel off a label prefix ("loop: MOVI R0, 1").
            instr = line
            if ":" in line:
                label_part, _, rest = line.partition(":")
                if label_part.strip() and not label_part.strip().startswith(";"):
                    instr = rest.strip()
            if not instr:
                continue
            parts = instr.replace(",", " ").split()
            if not parts:
                continue
            mnemonic = _OPCODE_ALIASES.get(parts[0].upper(), parts[0].upper())
            if mnemonic not in _ASSEMBLY_OPCODES:
                continue
            if self._operands_match_format(mnemonic, parts[1:]):
                return True
        return False

    def _operands_match_format(self, mnemonic: str, operands: list[str]) -> bool:
        """True if ``operands`` has the right arity/shape for ``mnemonic``."""
        if mnemonic == "MOVI":
            return (
                len(operands) == 2
                and _is_register_token(operands[0])
                and _is_immediate_token(operands[1])
            )
        if mnemonic == "JMP":
            # JMP takes a single label/offset operand.
            return len(operands) == 1 and (
                _is_immediate_token(operands[0]) or not _is_register_token(operands[0])
            )
        if mnemonic in _FMT_A:
            return len(operands) == 0
        if mnemonic in _FMT_B:
            return len(operands) == 1 and _is_register_token(operands[0])
        if mnemonic in _FMT_C:
            return len(operands) == 2 and all(
                _is_register_token(o) for o in operands
            )
        if mnemonic in _FMT_D:
            # Conditional jumps: rd + label/offset.
            return len(operands) == 2 and _is_register_token(operands[0])
        if mnemonic in _FMT_E:
            return len(operands) == 3 and all(
                _is_register_token(o) for o in operands
            )
        return False

    def _parse_flux_assembly(self, assembly: str) -> bytes:
        """Parse FLUX assembly language to bytecode.

        Supports:
        - MOVI R0, 42
        - IADD R0, R1, R2
        - label: JMP label
        - ; comments
        """
        lines = assembly.strip().split('\n')

        # First pass: collect labels and instruction info
        labels: dict[str, int] = {}
        instructions: list[tuple[int, str]] = []  # (offset, line_without_label)
        offset = 0

        for line in lines:
            line = line.strip()
            if not line or line.startswith((';', '//', '#')):
                continue
            # Strip inline comments (assembly style).
            for marker in ('//', ';'):
                idx = line.find(marker)
                if idx > 0:
                    line = line[:idx].strip()
                    break
            if not line:
                continue

            # Check for label
            has_label = False
            label_name = None
            if ':' in line:
                label_part = line.split(':')[0].strip()
                if label_part and not label_part.startswith(';'):
                    label_name = label_part
                    labels[label_name] = offset
                    has_label = True

            # Remove label for instruction parsing
            instr_line = line.split(':', 1)[1].strip() if has_label else line

            if not instr_line:
                continue

            # Estimate instruction size
            op_part = instr_line.split()[0] if instr_line.split() else ''
            if op_part:
                op_upper = op_part.upper().rstrip(':')
                op_upper = _OPCODE_ALIASES.get(op_upper, op_upper)
                if op_upper not in Op.__members__:
                    raise ValueError(f"Unknown opcode in assembly: {op_upper}")
                opcode = Op[op_upper]
                instr_size = self._estimate_instruction_size(opcode, instr_line)
                instructions.append((offset, instr_line))
                offset += instr_size

        # Second pass: generate bytecode with label offsets
        bytecode = bytearray()
        for instr_offset, instr_line in instructions:
            encoded = self._parse_instruction_with_offset(instr_line, labels, instr_offset)
            if not encoded:
                raise ValueError(f"Could not encode instruction: {instr_line!r}")
            bytecode.extend(encoded)

        return bytes(bytecode)

    def _estimate_instruction_size(self, opcode: Op, line: str = "") -> int:
        """Estimate the size of an instruction in bytes.

        ``line`` is required for MOVI, whose size grows when the immediate
        does not fit in a signed 16-bit immediate (a 32-bit load sequence is
        emitted instead — SEAM-REPORT bug #4).
        """
        name = Op(opcode).name
        if name in _FMT_A:
            return 1
        if name in _FMT_B:
            return 2
        if name == "MOVI":
            if line:
                parts = line.replace(',', ' ').split()
                if len(parts) >= 3:
                    try:
                        return len(self._emit_movi(self._parse_register(parts[1]), int(parts[2], 0)))
                    except ValueError:
                        return 4  # malformed — pass 2 will raise a clear error
            return 4
        if name in _FMT_C:
            return 3
        if name in _FMT_D or name in _FMT_E:
            return 4
        raise ValueError(f"Unsupported instruction: {name}")

    def _parse_instruction(self, line: str, labels: dict[str, int]) -> bytes:
        """Parse a single FLUX assembly instruction to bytecode."""
        parts = line.split()
        if not parts:
            return b""

        op_name = parts[0].upper()

        try:
            opcode = Op[op_name]
        except KeyError:
            return b""  # Unknown opcode

        # Get current position for label offset calculation
        # We need to track this differently - for now, estimate

        # Parse operands based on opcode format
        if opcode == Op.MOVI and len(parts) >= 3:
            # MOVI R0, 42
            reg = self._parse_register(parts[1])
            imm = int(parts[2])
            return struct.pack("<BBh", opcode, reg, imm)

        elif opcode in {Op.IADD, Op.ISUB, Op.IMUL, Op.IDIV} and len(parts) >= 4:
            # IADD R0, R1, R2
            rd = self._parse_register(parts[1])
            rs1 = self._parse_register(parts[2])
            rs2 = self._parse_register(parts[3])
            return struct.pack("<BBBB", opcode, rd, rs1, rs2)

        elif opcode in {Op.MOV, Op.LOAD, Op.STORE} and len(parts) >= 3:
            # MOV R0, R1
            rd = self._parse_register(parts[1])
            rs1 = self._parse_register(parts[2])
            return struct.pack("<BBB", opcode, rd, rs1)

        elif opcode in {Op.JMP, Op.JZ, Op.JNZ} and len(parts) >= 2:
            # JMP label or JZ R0, label
            if len(parts) == 2:
                # JMP label
                target = parts[1].rstrip(',')
                # Forward jump: target is ahead, offset is positive
                # Backward jump: target is behind, offset is negative
                # We can't calculate accurately without knowing current position
                # For now, use a placeholder that will be fixed by a second pass
                offset = labels[target] - 10 if target in labels else 0  # Rough estimate
                return struct.pack("<BBh", opcode, 0, offset)
            else:
                # JZ R0, label
                reg = self._parse_register(parts[1])
                target = parts[2].rstrip(',')
                offset = labels[target] - 10 if target in labels else 0  # Rough estimate
                return struct.pack("<BBh", opcode, reg, offset)

        elif opcode in {Op.INC, Op.DEC} and len(parts) >= 2:
            # INC R0
            reg = self._parse_register(parts[1])
            return struct.pack("<BB", opcode, reg)

        elif opcode in {Op.PUSH, Op.POP} and len(parts) >= 2:
            # PUSH R0
            reg = self._parse_register(parts[1])
            return struct.pack("<BB", opcode, reg)

        elif opcode in {Op.HALT, Op.NOP, Op.YIELD}:
            return bytes([opcode])

        return b""

    def _parse_instruction_with_offset(self, line: str, labels: dict[str, int], current_offset: int) -> bytes:
        """Parse a single FLUX assembly instruction to bytecode, knowing current offset."""
        parts = line.replace(',', ' ').split()
        if not parts:
            return b""

        op_name = parts[0].upper().rstrip(':')
        op_name = _OPCODE_ALIASES.get(op_name, op_name)
        if op_name not in Op.__members__:
            raise ValueError(f"Unknown opcode in assembly: {op_name}")
        opcode = Op[op_name]

        # Parse operands based on opcode format
        if opcode == Op.MOVI and len(parts) >= 3:
            # MOVI R0, 42 (or a 32-bit load sequence for large immediates)
            reg = self._parse_register(parts[1])
            imm = int(parts[2], 0)
            return self._emit_movi(reg, imm)

        elif opcode in {Op.IADD, Op.ISUB, Op.IMUL, Op.IDIV, Op.IMOD, Op.IREM,
                        Op.IAND, Op.IOR, Op.IXOR, Op.ISHL, Op.ISHR,
                        Op.ROTL, Op.ROTR} and len(parts) >= 4:
            # IADD R0, R1, R2
            rd = self._parse_register(parts[1])
            rs1 = self._parse_register(parts[2])
            rs2 = self._parse_register(parts[3])
            return struct.pack("<BBBB", opcode, rd, rs1, rs2)

        elif opcode in {Op.MOV, Op.LOAD, Op.STORE, Op.LOAD8, Op.STORE8,
                        Op.INEG, Op.INOT, Op.CMP, Op.IEQ, Op.ILT, Op.ILE,
                        Op.IGT, Op.IGE, Op.TEST, Op.ALLOCA, Op.CALL_IND,
                        Op.CAST, Op.BOX, Op.UNBOX, Op.CHECK_TYPE,
                        Op.CHECK_BOUNDS} and len(parts) >= 3:
            # MOV R0, R1 (Format C)
            rd = self._parse_register(parts[1])
            rs1 = self._parse_register(parts[2])
            return struct.pack("<BBB", opcode, rd, rs1)

        elif opcode in {Op.JMP, Op.JZ, Op.JNZ, Op.JE, Op.JNE, Op.JG, Op.JL,
                        Op.JGE, Op.JLE, Op.CALL, Op.TAILCALL} and len(parts) >= 2:
            # JMP label or JZ R0, label
            instr_size = self._estimate_instruction_size(opcode)
            after_instr_offset = current_offset + instr_size

            if opcode == Op.JMP and len(parts) == 2:
                # JMP label
                reg = 0
                target = parts[1].rstrip(',')
            elif len(parts) == 2:
                # JZ label (no register — branch on R0 semantics kept for
                # backward compatibility)
                reg = 0
                target = parts[1].rstrip(',')
            else:
                # JZ R0, label
                reg = self._parse_register(parts[1])
                target = parts[2].rstrip(',')

            # Offset: unknown-label placeholders are patched by a second pass
            offset = (labels[target] - after_instr_offset) if target in labels else 0

            return struct.pack("<BBh", opcode, reg, offset)

        elif opcode in {Op.INC, Op.DEC, Op.PUSH, Op.POP, Op.SETCC,
                        Op.ENTER, Op.LEAVE} and len(parts) >= 2:
            # INC R0
            reg = self._parse_register(parts[1])
            return struct.pack("<BB", opcode, reg)

        elif opcode in {Op.NOP, Op.HALT, Op.RET, Op.DUP, Op.SWAP, Op.YIELD}:
            return bytes([opcode])

        raise ValueError(
            f"Cannot encode instruction {line!r}: unsupported or malformed "
            f"operands for {op_name}"
        )

    def _parse_register(self, reg_str: str) -> int:
        """Parse register string to number (R0 -> 0).

        Only actual register names (R0-R15) are accepted. Anything else raises
        a clear error — previously any token starting with 'R' had the 'R'
        stripped and was cast to int, which mangled words like ``return`` into
        ``'ETURN'`` (SEAM-REPORT bug #1).
        """
        reg_str = reg_str.upper().rstrip(',').strip()
        match = re.fullmatch(r'R(\d+)', reg_str)
        if not match:
            raise ValueError(f"Invalid register: '{reg_str}' (expected R0-R15)")
        reg = int(match.group(1))
        if reg >= RegisterFile.GP_COUNT:
            raise ValueError(f"Register out of range: R{reg} (expected R0-R15)")
        return reg

    def _emit_movi(self, reg: int, imm: int) -> bytes:
        """Emit ``MOVI Rd, imm`` bytecode.

        Values in the signed 16-bit range encode as the single legacy MOVI
        instruction. Larger values (up to 32 bits) emit a register-safe load
        sequence built from System A opcodes (MOVI/ISHL/IADD/IOR) that
        preserves all registers via PUSH/POP — SEAM-REPORT bug #4 (MOVI was
        ​16-bit, so ``factorial of 5000000`` could not even parse).

        Raises:
            ValueError: If ``imm`` does not fit in 32 bits.
        """
        if -32768 <= imm <= 32767:
            return struct.pack("<BBh", Op.MOVI, reg, imm)
        if not -(1 << 31) <= imm < (1 << 32):
            raise ValueError(
                f"Immediate {imm} out of range for MOVI (supports -2^31 .. 2^32-1)"
            )

        # Build the 32-bit two's-complement value in R1 with a
        # MOVI/ISHL/IADD/IOR sequence, saving/restoring the other scratch
        # registers (R1-R4) so the load is side-effect free. The destination
        # register itself is never saved or restored (it is being overwritten).
        value = imm & 0xFFFFFFFF
        lo = value & 0xFFFF
        hi = (value >> 16) & 0xFFFF
        lo_signed = lo if lo < 0x8000 else lo - 0x10000
        hi_signed = hi if hi < 0x8000 else hi - 0x10000
        scratch = [r for r in (1, 2, 3, 4) if r != reg]

        out = bytearray()
        for r in scratch:
            out.extend(struct.pack("<BB", Op.PUSH, r))
        # R3 = 16 (shift amount); R2 = 65536 (1 << 16).
        out.extend(struct.pack("<BBh", Op.MOVI, 3, 16))
        out.extend(struct.pack("<BBh", Op.MOVI, 2, 1))
        out.extend(struct.pack("<BBBB", Op.ISHL, 2, 2, 3))
        # Low 16 bits into R1 (unsigned).
        out.extend(struct.pack("<BBh", Op.MOVI, 1, lo_signed))
        if lo >= 0x8000:
            out.extend(struct.pack("<BBBB", Op.IADD, 1, 1, 2))
        # High 16 bits into R4, shifted into place.
        out.extend(struct.pack("<BBh", Op.MOVI, 4, hi_signed))
        if hi >= 0x8000:
            out.extend(struct.pack("<BBBB", Op.IADD, 4, 4, 2))
        out.extend(struct.pack("<BBBB", Op.ISHL, 4, 4, 3))
        # R1 = R1 | R4
        out.extend(struct.pack("<BBBB", Op.IOR, 1, 1, 4))
        if reg != 1:
            out.extend(struct.pack("<BBB", Op.MOV, reg, 1))
        for r in reversed(scratch):
            out.extend(struct.pack("<BB", Op.POP, r))
        return bytes(out)

    def _parse_natural_language(self, text: str) -> bytes:
        """Parse natural language or math notation to bytecode."""
        # Clean the text: remove markdown comments, extra whitespace
        lines = []
        for line in text.split('\n'):
            # Remove markdown headers (#, ##)
            line = re.sub(r'^\s*#+\s*', '', line)
            # Remove HTML comments
            line = re.sub(r'<!--.*?-->', '', line)
            # Skip empty lines
            if line.strip():
                lines.append(line.strip())

        # Join lines and search for patterns
        cleaned_text = ' '.join(lines).lower()

        # Check for factorial/fibonacci/sum BEFORE the generic math pattern
        # so "compute factorial of 5" reaches the factorial generator
        # instead of being treated as a math expression.
        # "factorial of N"
        fact_match = re.search(r'factorial(?:\s+of)?\s+(\d+)', cleaned_text)
        if fact_match:
            n = int(fact_match.group(1))
            return self._generate_factorial(n)

        # "fibonacci of N"
        fib_match = re.search(r'fibonacci(?:\s+of)?\s+(\d+)', cleaned_text)
        if fib_match:
            n = int(fib_match.group(1))
            return self._generate_fibonacci(n)

        # "sum 1 to 100" or "sum from 1 to 100"
        sum_match = re.search(r'sum\s+(?:from\s+)?(\d+)\s+to\s+(\d+)', cleaned_text)
        if sum_match:
            start = int(sum_match.group(1))
            end = int(sum_match.group(2))
            return self._generate_sum(start, end)

        # Check for mathematical patterns
        # "compute 3 + 4" or "what is 10 * 5"
        math_match = re.match(r'(?:compute|what is)\s+(.+)', cleaned_text)
        if math_match:
            return self._parse_math_expression(math_match.group(1))

        # A2A patterns
        # "tell agent2 that temperature is 72"
        tell_match = re.search(r'tell\s+(\w+)\s+(.+)', cleaned_text)
        if tell_match:
            agent = tell_match.group(1)
            message = tell_match.group(2)
            return self._generate_a2a_tell(agent, message)

        # "ask navigator for heading"
        ask_match = re.search(r'ask\s+(\w+)\s+for\s+(.+)', cleaned_text)
        if ask_match:
            agent = ask_match.group(1)
            message = ask_match.group(2)
            return self._generate_a2a_ask(agent, message)

        # "broadcast storm warning"
        broadcast_match = re.search(r'broadcast\s+(.+)', cleaned_text)
        if broadcast_match:
            message = broadcast_match.group(1)
            return self._generate_a2a_broadcast(message)

        # Try to parse as line-by-line instructions
        # Use the original line structure for line-by-line parsing
        return self._parse_line_by_line('\n'.join(lines))

    def _parse_line_by_line(self, text: str) -> bytes:
        """Parse text as line-by-line instructions."""
        bytecode = bytearray()
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for line in lines:
            bytecode.extend(self._parse_line(line))

        return bytes(bytecode)

    def _parse_line(self, line: str) -> bytes:
        """Parse a single line of natural language instruction.

        Prose lines that match no pattern return empty bytes (they are
        ignored); if NO line in the whole input is recognizable, the caller
        raises a clear error instead of silently executing a no-op
        (SEAM-REPORT bug #3).
        """
        line = line.lower().strip()

        # "compute 3 + 4" / "what is 10 * 5" (per-line math — the joined-text
        # matcher can be thrown off by surrounding prose/headings).
        math_match = re.match(r'(?:compute|what is)\s+(.+)', line)
        if math_match:
            return self._parse_math_expression(math_match.group(1))

        # "load R0 with 42" / "set R0 to 42" / "R0 = 42"
        load_match = re.match(r'(?:load|set)\s+(r\d+)\s+(?:with|to|=)\s+(-?\d+)', line)
        if load_match:
            reg = self._parse_register(load_match.group(1))
            val = int(load_match.group(2))
            return self._emit_movi(reg, val)

        # "add R0 and R1" / "R0 += R1" / "R0 + R1"
        add_match = re.match(r'(?:add\s+)?(r\d+)\s*(?:\+=|\+|and)\s*(r\d+)', line)
        if add_match:
            rd = self._parse_register(add_match.group(1))
            rs1 = rd  # Default to rd as first source
            rs2 = self._parse_register(add_match.group(2))
            return struct.pack("<BBBB", Op.IADD, rd, rs1, rs2)

        # "multiply R0 by R1" / "R0 *= R1" / "R0 * R1"
        mul_match = re.match(r'(?:multiply\s+)?(r\d+)\s*(?:\*=|\*|by)\s*(r\d+)', line)
        if mul_match:
            rd = self._parse_register(mul_match.group(1))
            rs2 = self._parse_register(mul_match.group(2))
            return struct.pack("<BBBB", Op.IMUL, rd, rd, rs2)

        # "subtract R1 from R0" / "R0 -= R1" / "R0 - R1"
        sub_from_match = re.match(r'subtract\s+(r\d+)\s+from\s+(r\d+)', line)
        if sub_from_match:
            rd = self._parse_register(sub_from_match.group(2))
            rs2 = self._parse_register(sub_from_match.group(1))
            return struct.pack("<BBBB", Op.ISUB, rd, rd, rs2)
        sub_match = re.match(r'(r\d+)\s*-=\s*(r\d+)', line) or re.match(r'(r\d+)\s*-\s*(r\d+)', line)
        if sub_match:
            rd = self._parse_register(sub_match.group(1))
            rs2 = self._parse_register(sub_match.group(2))
            return struct.pack("<BBBB", Op.ISUB, rd, rd, rs2)

        # "increment R0" / "decrease R0" / "R0++" / "R0--"
        if 'increment' in line or '++' in line:
            reg_match = re.search(r'r(\d+)', line)
            if reg_match:
                reg = int(reg_match.group(1))
                return struct.pack("<BB", Op.INC, reg)

        if 'decrease' in line or 'decrement' in line or '--' in line:
            reg_match = re.search(r'r(\d+)', line)
            if reg_match:
                reg = int(reg_match.group(1))
                return struct.pack("<BB", Op.DEC, reg)

        # "push R0"
        push_match = re.match(r'push\s+(r\d+)', line)
        if push_match:
            reg = self._parse_register(push_match.group(1))
            return struct.pack("<BB", Op.PUSH, reg)

        # "pop to R1"
        pop_match = re.match(r'pop\s+(?:to\s+)?(r\d+)', line)
        if pop_match:
            reg = self._parse_register(pop_match.group(1))
            return struct.pack("<BB", Op.POP, reg)

        # "return R0" / "result is R0"
        if 'return' in line or 'result' in line:
            return bytes([Op.HALT])

        # Unrecognized prose — skip (markdown prose is not FLUX code).
        return b""

    # ── Math Notation Generators ─────────────────────────────────────────────────

    def _parse_math_expression(self, expr: str) -> bytes:
        """Parse a simple math expression like "3 + 4" or "10 * 5"."""
        expr = expr.strip()

        # Try to parse as "3 + 4"
        parts = re.split(r'\s*([\+\-\*\/])\s*', expr)
        if len(parts) == 3:
            try:
                a = int(parts[0])
                op = parts[1]
                b = int(parts[2])
            except ValueError:
                a = None
            if a is not None:
                bytecode = bytearray()

                # Load first operand into R0
                bytecode.extend(self._emit_movi(0, a))

                # Load second operand into R1
                bytecode.extend(self._emit_movi(1, b))

                # Perform operation
                if op == '+':
                    bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))
                elif op == '-':
                    bytecode.extend(struct.pack("<BBBB", Op.ISUB, 0, 0, 1))
                elif op == '*':
                    bytecode.extend(struct.pack("<BBBB", Op.IMUL, 0, 0, 1))
                elif op == '/':
                    bytecode.extend(struct.pack("<BBBB", Op.IDIV, 0, 0, 1))

                return bytes(bytecode)

        # Fallback: try eval (simplified)
        try:
            result = int(eval(expr, {"__builtins__": {}}))
        except (ValueError, TypeError, SyntaxError):
            raise ValueError(
                f"Unrecognized math expression: {expr!r}"
            ) from None
        return self._emit_movi(0, result)

    def _generate_factorial(self, n: int) -> bytes:
        """Generate bytecode for factorial of n."""
        bytecode = bytearray()

        # Load n into R0
        bytecode.extend(self._emit_movi(0, n))

        # Load 1 into R1 (result)
        bytecode.extend(self._emit_movi(1, 1))

        # Start of loop
        loop_start = len(bytecode)

        # Multiply: R1 = R1 * R0
        bytecode.extend(struct.pack("<BBBB", Op.IMUL, 1, 1, 0))

        # Decrement: R0--
        bytecode.extend(struct.pack("<BB", Op.DEC, 0))

        # Jump if not zero: JNZ R0, loop_start
        # Offset is relative to after the JNZ instruction (4 bytes ahead)
        # We want to jump back to loop_start, so offset = loop_start - current_position - 4
        current_pos = len(bytecode)
        jnz_offset = loop_start - (current_pos + 4)
        bytecode.extend(struct.pack("<BBh", Op.JNZ, 0, jnz_offset))

        # Move result to R0
        bytecode.extend(struct.pack("<BBB", Op.MOV, 0, 1))

        return bytes(bytecode)

    def _generate_fibonacci(self, n: int) -> bytes:
        """Generate bytecode for fibonacci of n."""
        bytecode = bytearray()

        if n <= 1:
            return self._emit_movi(0, n)

        # Load n into R0
        bytecode.extend(self._emit_movi(0, n))

        # Load 0 into R1 (fib(0))
        bytecode.extend(self._emit_movi(1, 0))

        # Load 1 into R2 (fib(1))
        bytecode.extend(self._emit_movi(2, 1))

        # Load 1 into R3 (counter)
        bytecode.extend(self._emit_movi(3, 1))

        # Start of loop
        loop_start = len(bytecode)

        # Compute next fib: R4 = R1 + R2
        bytecode.extend(struct.pack("<BBBB", Op.IADD, 4, 1, 2))

        # Shift: R1 = R2, R2 = R4
        bytecode.extend(struct.pack("<BBB", Op.MOV, 1, 2))
        bytecode.extend(struct.pack("<BBB", Op.MOV, 2, 4))

        # Increment counter: R3++
        bytecode.extend(struct.pack("<BB", Op.INC, 3))

        # Compare: if R3 >= R0, exit loop
        bytecode.extend(struct.pack("<BBB", Op.CMP, 3, 0))
        jump_offset = len(bytecode) + 4
        bytecode.extend(struct.pack("<BBh", Op.JGE, 0, 0))  # Placeholder

        # Jump back to loop start
        loop_jump_offset = loop_start - (len(bytecode) + 4)
        bytecode.extend(struct.pack("<BBh", Op.JMP, 0, loop_jump_offset))

        # Fix up the JGE offset to jump here (after loop)
        jge_pos = jump_offset - 4
        current_pos = len(bytecode)
        jge_offset = current_pos - jump_offset
        bytecode[jge_pos+2] = jge_offset & 0xFF
        bytecode[jge_pos+3] = (jge_offset >> 8) & 0xFF

        # Result is in R2
        bytecode.extend(struct.pack("<BBB", Op.MOV, 0, 2))

        return bytes(bytecode)

    def _generate_sum(self, start: int, end: int) -> bytes:
        """Generate bytecode for sum from start to end."""
        bytecode = bytearray()

        # Load start into R0
        bytecode.extend(self._emit_movi(0, start))

        # Load 0 into R1 (accumulator)
        bytecode.extend(self._emit_movi(1, 0))

        # Load end into R2
        bytecode.extend(self._emit_movi(2, end))

        # Start of loop
        loop_start = len(bytecode)

        # Add: R1 = R1 + R0
        bytecode.extend(struct.pack("<BBBB", Op.IADD, 1, 1, 0))

        # Increment: R0++
        bytecode.extend(struct.pack("<BB", Op.INC, 0))

        # Compare: if R0 > R2, exit (use CMP + conditional jump)
        bytecode.extend(struct.pack("<BBB", Op.CMP, 0, 2))

        # Jump if greater (using JG which is 0x4D)
        # This needs to skip the loop jump and go to the end
        jg_pos = len(bytecode)
        bytecode.extend(struct.pack("<BBh", Op.JG, 0, 0))  # Placeholder offset

        # Jump back to loop start
        loop_jump_offset = loop_start - (len(bytecode) + 4)
        bytecode.extend(struct.pack("<BBh", Op.JMP, 0, loop_jump_offset))

        # Fix up the JG offset to jump to here (after the loop)
        current_pos = len(bytecode)
        jg_offset = current_pos - (jg_pos + 4)
        bytecode[jg_pos+2] = jg_offset & 0xFF
        bytecode[jg_pos+3] = (jg_offset >> 8) & 0xFF

        # Result is in R1
        bytecode.extend(struct.pack("<BBB", Op.MOV, 0, 1))

        return bytes(bytecode)

    # ── A2A Message Generators ───────────────────────────────────────────────────

    def _generate_a2a_tell(self, agent: str, message: str) -> bytes:
        """Generate A2A TELL message bytecode."""
        bytecode = bytearray()

        # Store message pointer in R0 (simplified - just use a constant)
        message_bytes = message.encode('utf-8')[:32]  # Limit to 32 bytes
        bytecode.extend(self._emit_movi(0, len(message_bytes)))

        # Generate TELL opcode (Format G)
        data = bytearray()
        data.append(0)  # message reg (placeholder)
        data.append(0)  # cap reg (placeholder)
        data.extend(agent.encode('utf-8')[:16])

        bytecode.extend(struct.pack("<BH", Op.TELL, len(data)))
        bytecode.extend(data)

        return bytes(bytecode)

    def _generate_a2a_ask(self, agent: str, message: str) -> bytes:
        """Generate A2A ASK message bytecode."""
        bytecode = bytearray()

        # Store message pointer in R0
        message_bytes = message.encode('utf-8')[:32]
        bytecode.extend(self._emit_movi(0, len(message_bytes)))

        # Generate ASK opcode (Format G)
        data = bytearray()
        data.append(0)  # message reg (placeholder)
        data.append(0)  # cap reg (placeholder)
        data.extend(agent.encode('utf-8')[:16])

        bytecode.extend(struct.pack("<BH", Op.ASK, len(data)))
        bytecode.extend(data)

        return bytes(bytecode)

    def _generate_a2a_broadcast(self, message: str) -> bytes:
        """Generate A2A BROADCAST message bytecode."""
        bytecode = bytearray()

        # Store message pointer in R0
        message_bytes = message.encode('utf-8')[:32]
        bytecode.extend(self._emit_movi(0, len(message_bytes)))

        # Generate BROADCAST opcode (Format G)
        data = bytearray()
        data.append(0)  # message reg (placeholder)
        data.extend(message.encode('utf-8')[:32])

        bytecode.extend(struct.pack("<BH", Op.BROADCAST, len(data)))
        bytecode.extend(data)

        return bytes(bytecode)

    # ── Display Formatting ───────────────────────────────────────────────────────

    def _format_disassembly(self, result: DisassemblyResult) -> str:
        """Format disassembly result for display."""
        lines = [f"FLUX Bytecode Disassembly ({result.total_bytes} bytes)"]
        lines.append("=" * 80)

        for instr in result.instructions:
            offset_str = f"{instr.offset:04x}"
            bytes_str = instr.bytes.hex().ljust(16)
            opcode_str = f"{instr.opcode_name:<20}"
            operands_str = instr.operands if instr.operands else ""
            lines.append(f"{offset_str}:  {bytes_str}  {opcode_str} {operands_str}")

        if result.error:
            lines.append(f"\nERROR: {result.error}")

        return "\n".join(lines)


# ── Interactive Mode ───────────────────────────────────────────────────────────

def interactive():
    """Open-flux-interpreter interactive mode.

    Accepts markdown, plain text, or code blocks.
    Shows:
      - The parsed bytecode (hex)
      - Disassembly
      - Execution result
      - Register state
    """

    interpreter = OpenFluxInterpreter()

    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║          Open-Flux-Interpreter v1.0                       ║")
    print("║   Convert markdown/text to FLUX bytecode and execute      ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    print("Enter markdown, natural language, or FLUX assembly code.")
    print("Type 'quit' or 'exit' to quit, 'help' for examples.")
    print()

    while True:
        try:
            user_input = input("open-flux> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ('quit', 'exit'):
                print("Goodbye!")
                break

            if user_input.lower() == 'help':
                print_help()
                continue

            # Execute the input
            result = interpreter.interpret(user_input)

            # Display results
            print()
            print("-" * 60)
            print("EXECUTION RESULT")
            print("-" * 60)

            if result.success:
                print("✓ Success!")
                print(f"  Result: R0 = {result.result}")
                print(f"  Cycles: {result.cycles}")
                print(f"  Halted: {result.halted}")

                if result.registers:
                    print("\n  Registers:")
                    for reg, val in sorted(result.registers.items()):
                        print(f"    R{reg} = {val}")

                # Show A2A messages if any
                a2a_msgs = interpreter.get_a2a_messages()
                if a2a_msgs:
                    print("\n  A2A Messages:")
                    for msg in a2a_msgs:
                        print(f"    [{msg['opcode']}] {msg['data']}")
            else:
                print(f"✗ Error: {result.error}")

            print()
            print("Bytecode (hex):")
            print(f"  {result.bytecode.hex()}")

            print()
            print("Disassembly:")
            print(result.disassembly)

            print()

        except KeyboardInterrupt:
            print("\nUse 'quit' or 'exit' to quit.")
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def print_help():
    """Print help text for interactive mode."""
    help_text = """
Examples:

  Natural Language:
    compute 3 + 4
    factorial of 7
    fibonacci of 12
    sum 1 to 100

  FLUX Assembly (in code blocks):
    ```flux
    MOVI R0, 10
    MOVI R1, 1
    loop:
    IMUL R1, R0
    DEC R0
    JNZ R0, loop
    HALT
    ```

  Line-by-line instructions:
    Load R0 with 10
    Load R1 with 1
    While R0 is not zero:
        Multiply R1 by R0
        Decrease R0
    Return R1

  A2A Agent Communication:
    tell agent2 hello
    ask navigator for heading
    broadcast storm warning
"""
    print(help_text)


# ── Convenience Functions ─────────────────────────────────────────────────────

def interpret(text: str, max_cycles: int = 1_000_000) -> ExecutionResult:
    """Convenience function to interpret text and execute.

    Args:
        text: Input markdown, natural language, or FLUX assembly.
        max_cycles: Maximum execution cycles.

    Returns:
        ExecutionResult with bytecode, disassembly, and results.
    """
    interp = OpenFluxInterpreter(max_cycles=max_cycles)
    return interp.interpret(text)


def run_markdown_file(filepath: str, max_cycles: int = 1_000_000) -> ExecutionResult:
    """Run a markdown file containing FLUX code.

    Args:
        filepath: Path to the markdown file.
        max_cycles: Maximum execution cycles.

    Returns:
        ExecutionResult with bytecode, disassembly, and results.
    """
    with open(filepath) as f:
        content = f.read()

    interp = OpenFluxInterpreter(max_cycles=max_cycles)
    return interp.interpret(content)


# ── Main Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    interactive()
