#!/usr/bin/env python3
"""FLUX Bytecode Playground — An interactive REPL for exploring the FLUX VM.

Enter simple expressions like:
    3 + 4
    10 * 6 + 2
    2 * (3 + 4)
    100 - 37

Commands:
    :help       — Show this help
    :regs       — Show register state
    :reset      — Reset the VM
    :quit       — Exit the playground
    :asm        — Show last disassembly
    :hex        — Show last hex dump
    :trace      — Toggle step-by-step tracing
    :fib N      — Run fibonacci(N) as bytecode
    :c CODE     — Compile C code and execute
    :py CODE    — Compile Python code and execute

Run:
    PYTHONPATH=src python3 examples/05_bytecode_playground.py
"""

from __future__ import annotations

import struct
import sys
import re

# ── ANSI helpers ─────────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner() -> None:
    print()
    print(f"{BOLD}{MAGENTA}{'╔' + '═' * 60 + '╗'}{RESET}")
    print(f"{BOLD}{MAGENTA}{'║'}  FLUX Bytecode Playground — Interactive REPL         {'║'}{RESET}")
    print(f"{BOLD}{MAGENTA}{'║'}  Type expressions to compile, execute, and explore    {'║'}{RESET}")
    print(f"{BOLD}{MAGENTA}{'║'}  :help for commands, :quit to exit                   {'║'}{RESET}")
    print(f"{BOLD}{MAGENTA}{'╚' + '═' * 60 + '╝'}{RESET}")
    print()


def prompt() -> str:
    try:
        return input(f"{BOLD}{CYAN}flux> {RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ":quit"


# ── Expression Compiler ──────────────────────────────────────────────────────

# Simple recursive descent parser for arithmetic expressions.
# Supports: +, -, *, /, %, (, ), integer literals.

class ExprParser:
    """Parse simple arithmetic expressions into bytecode."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.code = bytearray()
        self._errors: list[str] = []
        self._next_reg = 0

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def _peek(self) -> str:
        self._skip_ws()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _advance(self) -> str:
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def _number(self) -> int:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        return int(self.text[start:self.pos])

    def _alloc_reg(self) -> int:
        r = self._next_reg
        self._next_reg += 1
        return r

    def _emit(self, *bytes_) -> None:
        for b in bytes_:
            if isinstance(b, str):
                self.code.append(ord(b))
            else:
                self.code.append(b & 0xFF)

    def parse(self) -> bytearray | None:
        """Parse the expression and return bytecode, or None on error."""
        try:
            result_reg = self._parse_expr()
            # Copy result to R0
            from flux.bytecode.opcodes import Op
            if result_reg != 0:
                self._emit(Op.MOV, 0, result_reg)
            self._emit(Op.HALT)
            return self.code
        except Exception as e:
            self._errors.append(str(e))
            return None

    def _parse_expr(self) -> int:
        """Parse additive expression: term (('+' | '-') term)*"""
        left = self._parse_term()
        while self._peek() in ("+", "-"):
            op = self._advance()
            right = self._parse_term()
            from flux.bytecode.opcodes import Op
            result = self._alloc_reg()
            if op == "+":
                self._emit(Op.IADD, result, left, right)
            else:
                self._emit(Op.ISUB, result, left, right)
            left = result
        return left

    def _parse_term(self) -> int:
        """Parse multiplicative expression: unary (('*' | '/' | '%') unary)*"""
        left = self._parse_unary()
        while self._peek() in ("*", "/", "%"):
            op = self._advance()
            right = self._parse_unary()
            from flux.bytecode.opcodes import Op
            result = self._alloc_reg()
            if op == "*":
                self._emit(Op.IMUL, result, left, right)
            elif op == "/":
                self._emit(Op.IDIV, result, left, right)
            else:
                self._emit(Op.IMOD, result, left, right)
            left = result
        return left

    def _parse_unary(self) -> int:
        """Parse unary expression: '-'? primary"""
        if self._peek() == "-":
            self._advance()
            operand = self._parse_primary()
            from flux.bytecode.opcodes import Op
            result = self._alloc_reg()
            self._emit(Op.INEG, result, operand)
            return result
        return self._parse_primary()

    def _parse_primary(self) -> int:
        """Parse primary: number | '(' expr ')'"""
        if self._peek() == "(":
            self._advance()
            result = self._parse_expr()
            if self._peek() == ")":
                self._advance()
            return result
        # Must be a number
        n = self._number()
        from flux.bytecode.opcodes import Op
        reg = self._alloc_reg()
        # MOVI reg, value
        if -32768 <= n <= 32767:
            self._emit(Op.MOVI, reg, n & 0xFF, (n >> 8) & 0xFF)
        else:
            # For large numbers, use MOV after MOVI for high bits (simplified)
            self._emit(Op.MOVI, reg, n & 0xFFFF)
        return reg


# ── Hex Dump ─────────────────────────────────────────────────────────────────

def hex_dump(data: bytes, bytes_per_line: int = 16) -> str:
    """Pretty hex dump."""
    lines = []
    for offset in range(0, len(data), bytes_per_line):
        chunk = data[offset:offset + bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "." for b in chunk
        )
        lines.append(f"  {offset:04x}  {hex_part:<{bytes_per_line * 3}}  |{ascii_part}|")
    return "\n".join(lines)


# ── Disassembly ──────────────────────────────────────────────────────────────

def simple_disasm(code: bytes) -> str:
    """Lightweight disassembly for raw code section (no header)."""
    from flux.bytecode.opcodes import Op, get_format

    lines = []
    offset = 0
    while offset < len(code):
        raw = code[offset]
        try:
            op = Op(raw)
        except ValueError:
            lines.append(f"  {offset:04x}:  .byte 0x{raw:02X}")
            offset += 1
            continue

        fmt = get_format(op)
        name = op.name

        if fmt == "A":
            lines.append(f"  {offset:04x}:  {name}")
            offset += 1
        elif fmt == "B":
            if offset + 1 < len(code):
                reg = code[offset + 1]
                lines.append(f"  {offset:04x}:  {name} R{reg}")
                offset += 2
            else:
                lines.append(f"  {offset:04x}:  {name} <truncated>")
                offset += 1
        elif fmt == "C":
            if offset + 2 < len(code):
                rd = code[offset + 1]
                rs1 = code[offset + 2]
                lines.append(f"  {offset:04x}:  {name} R{rd}, R{rs1}")
                offset += 3
            else:
                lines.append(f"  {offset:04x}:  {name} <truncated>")
                offset += 1
        elif fmt == "D":
            if offset + 3 < len(code):
                reg = code[offset + 1]
                imm = struct.unpack_from("<h", code, offset + 2)[0]
                lines.append(f"  {offset:04x}:  {name} R{reg}, {imm}")
                offset += 4
            else:
                lines.append(f"  {offset:04x}:  {name} <truncated>")
                offset += 1
        elif fmt == "E":
            if offset + 3 < len(code):
                rd = code[offset + 1]
                rs1 = code[offset + 2]
                rs2 = code[offset + 3]
                lines.append(f"  {offset:04x}:  {name} R{rd}, R{rs1}, R{rs2}")
                offset += 4
            else:
                lines.append(f"  {offset:04x}:  {name} <truncated>")
                offset += 1
        else:
            lines.append(f"  {offset:04x}:  {name}")
            offset += 1

    return "\n".join(lines)


# ── Stepping VM ──────────────────────────────────────────────────────────────

class StepInterpreter:
    """A thin wrapper around Interpreter that can step one instruction at a time."""

    def __init__(self, bytecode: bytes):
        self.bytecode = bytecode
        self.trace_log: list[str] = []

    def run(self, trace: bool = False) -> int:
        """Execute bytecode, optionally with step tracing."""
        from flux.vm.interpreter import Interpreter

        interp = Interpreter(self.bytecode, memory_size=4096)
        self.trace_log.clear()

        if trace:
            interp.running = True
            while interp.running and interp.cycle_count < interp.max_cycles:
                start_pc = interp.pc
                # Capture pre-state
                r0 = interp.regs.read_gp(0)
                interp._step()
                interp.cycle_count += 1
                # Capture post-state
                r0_after = interp.regs.read_gp(0)
                self.trace_log.append(
                    f"  cycle={interp.cycle_count:>5}  pc={start_pc:04x}  "
                    f"R0: {r0:>12} → {r0_after:>12}"
                )
        else:
            interp.execute()

        return interp


# ── Fibonacci Bytecode ───────────────────────────────────────────────────────

def fibonacci_bytecode(n: int) -> bytes:
    """Generate bytecode for fibonacci(n) using a loop."""
    from flux.bytecode.opcodes import Op

    code = bytearray()
    # R0 = a (starts at 0), R1 = b (starts at 1), R2 = i (counter), R3 = n
    code.extend(struct.pack("<BBh", Op.MOVI, 0, 0))    # a = 0
    code.extend(struct.pack("<BBh", Op.MOVI, 1, 1))    # b = 1
    code.extend(struct.pack("<BBh", Op.MOVI, 2, 0))    # i = 0
    code.extend(struct.pack("<BBh", Op.MOVI, 3, n))    # n = N

    # while_header: CMP R2, R3; JGE exit
    cmp_start = len(code)                              # remember CMP position
    code.extend(bytes([Op.CMP, 2, 3]))                  # CMP R2, R3 (3 bytes)

    jge_start = len(code)                              # JGE opcode position
    code.extend(bytes([Op.JGE, 0, 0, 0]))              # placeholder (4 bytes)
    jge_imm_pos = jge_start + 2                        # imm16 within JGE
    jge_after_pc = jge_start + 4                       # PC after JGE fetched

    # while_body:
    # temp = a + b → R4 = R0 + R1
    code.extend(bytes([Op.IADD, 4, 0, 1]))
    # a = old b → R0 = R1
    code.extend(bytes([Op.MOV, 0, 1]))
    # b = temp → R1 = R4
    code.extend(bytes([Op.MOV, 1, 4]))
    # i++ → INC R2
    code.extend(bytes([Op.INC, 2]))
    # JMP back to CMP
    jmp_start = len(code)
    after_jmp_pc = jmp_start + 4
    loop_back = cmp_start - after_jmp_pc               # relative to PC after JMP
    code.extend(struct.pack("<BBh", Op.JMP, 0, loop_back))

    # Patch JGE offset to jump to HALT (position len(code))
    exit_pos = len(code)
    exit_offset = exit_pos - jge_after_pc
    struct.pack_into("<h", code, jge_imm_pos, exit_offset)

    # exit: HALT
    code.extend(bytes([Op.HALT]))

    return bytes(code)


# ── Register Display ─────────────────────────────────────────────────────────

def show_registers(interp) -> None:
    """Display non-zero registers."""
    from flux.bytecode.opcodes import Op
    print(f"\n  {BOLD}{YELLOW}Register File:{RESET}")
    print(f"  {'R0 (result)':<20} = {interp.regs.read_gp(0)}")

    specials = {11: "SP", 14: "FP", 15: "LR"}
    any_nonzero = False
    for i in range(16):
        val = interp.regs.read_gp(i)
        if val != 0:
            tag = f"  ({specials[i]})" if i in specials else ""
            print(f"  R{i:<2}{tag:<8} = {val}")
            any_nonzero = True
    if not any_nonzero:
        print(f"  {DIM}(all registers zero){RESET}")


# ── Main REPL Loop ──────────────────────────────────────────────────────────

def main() -> None:
    from flux.bytecode.opcodes import Op
    from flux.pipeline.e2e import FluxPipeline
    from flux.pipeline.debug import disassemble_bytecode

    banner()

    last_bytecode: bytes | None = None
    last_interp = None
    trace_mode = False
    expr_count = 0

    print(f"  {GREEN}Ready.{RESET} Type an arithmetic expression or :help for commands.")
    print(f"  Examples: {DIM}3 + 4{RESET}, {DIM}10 * 6 + 2{RESET}, {DIM}:fib 10{RESET}, {DIM}:c int main() { return 42; }{RESET}")
    print()

    while True:
        line = prompt()

        if not line:
            continue

        # Commands
        if line == ":quit" or line == ":q":
            print(f"\n  {GREEN}Goodbye!{RESET}\n")
            break

        elif line == ":help" or line == ":h":
            print(f"\n  {BOLD}{YELLOW}FLUX Bytecode Playground Commands:{RESET}")
            print(f"  {'─' * 50}")
            print(f"  {CYAN}Expression{RESET}         Enter math: 3 + 4, 10 * 6 + 2")
            print(f"  {CYAN}:help{RESET}              Show this help")
            print(f"  {CYAN}:regs{RESET}              Show register state")
            print(f"  {CYAN}:reset{RESET}             Reset the VM")
            print(f"  {CYAN}:asm{RESET}               Disassemble last bytecode")
            print(f"  {CYAN}:hex{RESET}               Hex dump last bytecode")
            print(f"  {CYAN}:trace{RESET}             Toggle step-by-step tracing")
            print(f"  {CYAN}:fib N{RESET}             Run fibonacci(N)")
            print(f"  {CYAN}:c CODE{RESET}           Compile C code")
            print(f"  {CYAN}:py CODE{RESET}          Compile Python code")
            print(f"  {CYAN}:quit{RESET}              Exit")
            print()

        elif line == ":regs":
            if last_interp:
                show_registers(last_interp)
            else:
                print(f"  {DIM}No execution yet. Enter an expression first.{RESET}")
            print()

        elif line == ":reset":
            last_bytecode = None
            last_interp = None
            expr_count = 0
            print(f"  {GREEN}VM reset.{RESET}\n")

        elif line == ":asm":
            if last_bytecode:
                print(f"\n  {BOLD}{YELLOW}Disassembly:{RESET}")
                if len(last_bytecode) >= 18 and last_bytecode[:4] == b"FLUX":
                    print(disassemble_bytecode(last_bytecode))
                else:
                    print(simple_disasm(last_bytecode))
                print()
            else:
                print(f"  {DIM}No bytecode yet. Enter an expression first.{RESET}\n")

        elif line == ":hex":
            if last_bytecode:
                print(f"\n  {BOLD}{YELLOW}Hex Dump ({len(last_bytecode)} bytes):{RESET}")
                print(hex_dump(last_bytecode))
                print()
            else:
                print(f"  {DIM}No bytecode yet. Enter an expression first.{RESET}\n")

        elif line == ":trace":
            trace_mode = not trace_mode
            status = f"{GREEN}ON{RESET}" if trace_mode else f"{RED}OFF{RESET}"
            print(f"  Step tracing: {status}\n")

        elif line.startswith(":fib"):
            parts = line.split()
            if len(parts) < 2:
                print(f"  {RED}Usage: :fib N{RESET}\n")
                continue
            try:
                n = int(parts[1])
            except ValueError:
                print(f"  {RED}Invalid number: {parts[1]}{RESET}\n")
                continue

            print(f"\n  {BOLD}{MAGENTA}Fibonacci({n}){RESET}")
            print(f"  {'─' * 50}")

            bc = fibonacci_bytecode(n)
            last_bytecode = bc
            expr_count += 1

            # Show bytecode
            print(f"  {DIM}Bytecode ({len(bc)} bytes):{RESET}")
            print(f"  {' '.join(f'{b:02X}' for b in bc)}")

            # Show disassembly
            print(f"\n  {DIM}Disassembly:{RESET}")
            print(simple_disasm(bc))

            # Execute
            stepper = StepInterpreter(bc)
            last_interp = stepper.run(trace=trace_mode)

            # Show trace if enabled
            if trace_mode and stepper.trace_log:
                print(f"\n  {DIM}Execution trace (last 10 steps):{RESET}")
                for line_ in stepper.trace_log[-10:]:
                    print(line_)

            # Show result
            result = last_interp.regs.read_gp(0)
            print(f"\n  {GREEN}fibonacci({n}) = {result}{RESET}")
            print()

        elif line.startswith(":c "):
            c_code = line[3:].strip()
            if not c_code:
                print(f"  {RED}Usage: :c <C code>{RESET}\n")
                continue

            print(f"\n  {BOLD}{MAGENTA}Compiling C{RESET}")
            print(f"  {DIM}Source: {c_code[:60]}{'...' if len(c_code) > 60 else ''}{RESET}")

            try:
                pipeline = FluxPipeline(execute=True)
                result = pipeline.run(c_code, lang="c", module_name="playground")
                last_bytecode = result.bytecode
                last_interp = None

                print(f"  {GREEN}Compiled: {len(result.bytecode)} bytes bytecode{RESET}")
                print(f"  Cycles: {result.cycles}")
                if result.registers:
                    nonzero = {k: v for k, v in result.registers.items() if v != 0}
                    if nonzero:
                        print(f"  Non-zero registers: {nonzero}")
                if result.errors:
                    print(f"  {RED}Errors: {result.errors}{RESET}")
            except Exception as e:
                print(f"  {RED}Error: {e}{RESET}")
            print()

        elif line.startswith(":py "):
            py_code = line[4:].strip()
            if not py_code:
                print(f"  {RED}Usage: :py <Python code>{RESET}\n")
                continue

            print(f"\n  {BOLD}{MAGENTA}Compiling Python{RESET}")
            print(f"  {DIM}Source: {py_code[:60]}{'...' if len(py_code) > 60 else ''}{RESET}")

            try:
                pipeline = FluxPipeline(execute=True)
                result = pipeline.run(py_code, lang="python", module_name="playground")
                last_bytecode = result.bytecode
                last_interp = None

                print(f"  {GREEN}Compiled: {len(result.bytecode)} bytes bytecode{RESET}")
                print(f"  Cycles: {result.cycles}")
                if result.registers:
                    nonzero = {k: v for k, v in result.registers.items() if v != 0}
                    if nonzero:
                        print(f"  Non-zero registers: {nonzero}")
                if result.errors:
                    print(f"  {RED}Errors: {result.errors}{RESET}")
            except Exception as e:
                print(f"  {RED}Error: {e}{RESET}")
            print()

        else:
            # Try to parse as arithmetic expression
            expr_count += 1
            print(f"\n  {BOLD}{MAGENTA}Expression #{expr_count}: {line}{RESET}")
            print(f"  {'─' * 50}")

            try:
                parser = ExprParser(line)
                bc = parser.parse()

                if bc is None:
                    print(f"  {RED}Parse error: {parser._errors}{RESET}\n")
                    continue

                last_bytecode = bc

                # Show hex dump
                print(f"  {DIM}Bytecode ({len(bc)} bytes):{RESET}")
                print(f"  {' '.join(f'{b:02X}' for b in bc)}")

                # Show disassembly
                print(f"\n  {DIM}Disassembly:{RESET}")
                print(simple_disasm(bc))

                # Execute
                stepper = StepInterpreter(bc)
                last_interp = stepper.run(trace=trace_mode)

                # Show trace if enabled
                if trace_mode and stepper.trace_log:
                    print(f"\n  {DIM}Execution trace:{RESET}")
                    # Show all steps for short programs, last 15 for long ones
                    show_steps = stepper.trace_log if len(stepper.trace_log) <= 15 else stepper.trace_log[-15:]
                    for tline in show_steps:
                        print(tline)
                    if len(stepper.trace_log) > 15:
                        print(f"  {DIM}... ({len(stepper.trace_log) - 15} more steps) {RESET}")

                # Show result
                result = last_interp.regs.read_gp(0)
                print(f"\n  {GREEN}Result: R0 = {result}{RESET}")
                print(f"  {DIM}({line} = {result}){RESET}")
                print()

            except Exception as e:
                print(f"  {RED}Error: {e}{RESET}")
                print(f"  {DIM}Tip: Use simple expressions like '3 + 4' or '10 * 6'{RESET}\n")


if __name__ == "__main__":
    main()
