"""FLUX Bytecode Debugger — Interactive step debugger for FLUX bytecode.

Extends the Interpreter with debugging capabilities:
    - Single-step execution
    - Breakpoints at PC addresses
    - Inspect/modify registers and memory
    - Continue until breakpoint or HALT
    - Watch expressions
    - Backtrace/call stack
    - Interactive REPL mode
    - Tracer integration for full execution recording

Example usage
-------------

Programmatic::

    debugger = FluxDebugger(bytecode)
    debugger.add_breakpoint(0x10)   # Set breakpoint at offset 0x10
    result = debugger.step()         # Execute one instruction
    debugger.continue_exec()         # Run until breakpoint
    print(debugger.inspect_reg(0))   # Check R0

Interactive REPL::

    debugger = FluxDebugger(bytecode)
    debugger.repl()                  # Interactive prompt

With tracing::

    debugger = FluxDebugger(bytecode, enable_trace=True)
    debugger.continue_exec()
    trace_json = debugger.export_trace()
"""

from __future__ import annotations

import struct
import sys
import json
from typing import Optional, List, Dict, Any, Set, Callable, Union
from dataclasses import dataclass, field

from flux.vm.interpreter import (
    Interpreter,
    VMError,
    VMHaltError,
    VMInvalidOpcodeError,
    VMDivisionByZeroError,
)
from flux.bytecode.opcodes import Op, get_format
from flux.disasm import (
    FluxDisassembler,
    DisassembledInstruction,
    get_instruction_color,
    Colors,
)


# ── Debugger data structures ────────────────────────────────────────────────────


@dataclass
class StepResult:
    """Result of a single step operation."""
    success: bool
    instruction: Optional[DisassembledInstruction] = None
    pc_before: int = 0
    pc_after: int = 0
    cycles: int = 0
    halted: bool = False
    error: Optional[str] = None
    breakpoint_hit: bool = False
    register_changes: Dict[str, tuple] = field(default_factory=dict)
    flag_changes: Dict[str, tuple] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "success": self.success,
            "pc_before": self.pc_before,
            "pc_after": self.pc_after,
            "cycles": self.cycles,
            "halted": self.halted,
            "breakpoint_hit": self.breakpoint_hit,
        }
        if self.instruction:
            result["instruction"] = self.instruction.to_dict()
        if self.error:
            result["error"] = self.error
        if self.register_changes:
            result["register_changes"] = {
                k: [old, new] for k, (old, new) in self.register_changes.items()
            }
        if self.flag_changes:
            result["flag_changes"] = {
                k: [old, new] for k, (old, new) in self.flag_changes.items()
            }
        return result


@dataclass
class Breakpoint:
    """A breakpoint at a specific byte offset."""
    offset: int
    enabled: bool = True
    hit_count: int = 0
    condition: Optional[str] = None  # Future: conditional breakpoints


@dataclass
class Watchpoint:
    """A watchpoint for a register (auto-display after each step)."""
    reg_num: int
    name: str = ""  # Optional custom name


# ── Command help for the REPL ──────────────────────────────────────────────────

HELP_TEXT = """
FLUX Debugger Commands
══════════════════════════════════════════════════════════════════════

Execution:
  s, step              Execute one instruction
  c, continue          Run until breakpoint or HALT
  r, run               Alias for continue
  n, next              Step over (like step, but skips CALL bodies)
  q, quit              Exit the debugger
  reset                Reset VM to initial state

Breakpoints:
  b <addr>, break <addr>      Set breakpoint at byte offset (hex or dec)
  bd <addr>                   Disable breakpoint
  be <addr>                   Enable breakpoint
  br <addr>                   Remove breakpoint
  bl, breakpoints             List all breakpoints
  bc                          Clear all breakpoints

Inspection:
  i, info                    Show VM state summary
  regs                       Dump all registers
  reg <n>                    Show register Rn
  set_reg <n> <val>          Set register Rn to val
  flags                      Show condition flags
  mem <addr> [len]           Read memory (hex addr, optional length)
  set_mem <addr> <hex>       Write hex bytes to memory
  stack [n]                  Show top n stack words (default 8)
  bt, backtrace              Show call stack backtrace
  dis [n]                    Disassemble n instructions at PC (default 5)
  dis <addr> [n]             Disassemble at address

Watchpoints:
  watch <reg> [name]         Watch a register
  unwatch <reg>              Remove watchpoint
  watches                    List watchpoints

Tracing:
  trace on                   Enable execution tracing
  trace off                  Disable execution tracing
  trace export [file]        Export trace as JSON
  trace report               Print trace summary

Other:
  h, help                    Show this help
  format                     Show formatted state display

══════════════════════════════════════════════════════════════════════
"""


# ── Main Debugger Class ────────────────────────────────────────────────────────


class FluxDebugger(Interpreter):
    """FLUX bytecode debugger with step, breakpoint, and inspection capabilities.

    Extends the Interpreter class with debugging features while maintaining
    full compatibility with the existing VM execution model.

    Parameters
    ----------
    bytecode:
        Raw bytecode to debug.
    memory_size:
        Memory region size in bytes.
    max_cycles:
        Maximum execution cycles (higher default for debugging).
    enable_trace:
        If True, attach a FluxTracer to record every instruction.

    Example
    -------

    ::

        debugger = FluxDebugger(bytecode)
        debugger.add_breakpoint(0x20)

        while not debugger.halted:
            result = debugger.step()
            print(result)

            if result.breakpoint_hit:
                print(f"R0 = {debugger.inspect_reg(0)}")
    """

    def __init__(
        self,
        bytecode: bytes,
        memory_size: int = 65536,
        max_cycles: int = 100_000,
        enable_trace: bool = False,
    ):
        """Initialize the debugger."""
        code = self._extract_code(bytecode)
        super().__init__(code, memory_size=memory_size, max_cycles=max_cycles)

        # Debugger state
        self._breakpoints: Dict[int, Breakpoint] = {}
        self._watchpoints: List[Watchpoint] = []
        self._disassembler = FluxDisassembler(color_output=False)
        self._original_bytecode = code
        self._call_stack: List[int] = []  # Track return addresses
        self._step_callback: Optional[Callable[[StepResult], None]] = None
        self._pending_bp: Optional[int] = None  # Breakpoint awaiting step-through

        # Tracing support
        self._tracer = None
        self._trace_enabled = enable_trace
        self._trace_entries: List[Dict[str, Any]] = []
        if enable_trace:
            self._init_tracer()

    # ── Execution control ───────────────────────────────────────────────────

    def step(self) -> StepResult:
        """Execute a single instruction and return detailed step info."""
        if self.halted:
            return StepResult(
                success=True,
                halted=True,
                pc_before=self.pc,
                pc_after=self.pc,
                cycles=0,
            )

        pc_before = self.pc
        cycles_before = self.cycle_count

        # Snapshot state before
        regs_before = self.regs.snapshot()
        flags_before = (
            self._flag_zero,
            self._flag_sign,
            self._flag_carry,
            self._flag_overflow,
        )

        # Disassemble the current instruction before executing
        instr = None
        try:
            instr = self._disassembler._disassemble_one(self._original_bytecode, pc_before)
        except Exception as e:
            return StepResult(
                success=False,
                pc_before=pc_before,
                pc_after=pc_before,
                cycles=0,
                error=f"Disassembly error: {e}",
            )

        # Check for breakpoint at this location — stop BEFORE executing
        breakpoint_hit = False
        if pc_before in self._breakpoints:
            bp = self._breakpoints[pc_before]
            if bp.enabled:
                if self._pending_bp != pc_before:
                    # First arrival at this breakpoint — don't execute yet
                    self._pending_bp = pc_before
                    bp.hit_count += 1
                    return StepResult(
                        success=True,
                        instruction=instr,
                        pc_before=pc_before,
                        pc_after=pc_before,
                        cycles=0,
                        halted=self.halted,
                        breakpoint_hit=True,
                    )
                else:
                    # Already stopped here — clear pending and execute through
                    self._pending_bp = None

        # Capture register changes
        def _capture_changes() -> tuple:
            regs_after = self.regs.snapshot()
            reg_changes: Dict[str, tuple] = {}
            for i in range(16):
                old_val = regs_before["gp"][i]
                new_val = regs_after["gp"][i]
                if old_val != new_val:
                    reg_changes[f"R{i}"] = (old_val, new_val)
            for i in range(16):
                old_val = regs_before["fp"][i]
                new_val = regs_after["fp"][i]
                if old_val != new_val:
                    reg_changes[f"F{i}"] = (old_val, new_val)

            flags_after = (
                self._flag_zero,
                self._flag_sign,
                self._flag_carry,
                self._flag_overflow,
            )
            flag_changes: Dict[str, tuple] = {}
            flag_names = ["zero", "sign", "carry", "overflow"]
            for i, (old, new) in enumerate(zip(flags_before, flags_after)):
                if old != new:
                    flag_changes[flag_names[i]] = (old, new)

            return reg_changes, flag_changes

        # Execute one instruction using parent's _step method
        try:
            self._step()
            self.cycle_count += 1
        except VMHaltError:
            self.halted = True
        except VMError as e:
            return StepResult(
                success=False,
                instruction=instr,
                pc_before=pc_before,
                pc_after=self.pc,
                cycles=self.cycle_count - cycles_before,
                halted=self.halted,
                error=str(e),
            )
        except Exception as e:
            return StepResult(
                success=False,
                instruction=instr,
                pc_before=pc_before,
                pc_after=self.pc,
                cycles=self.cycle_count - cycles_before,
                halted=self.halted,
                error=f"Unexpected error: {e}",
            )

        # Capture state changes
        reg_changes, flag_changes = _capture_changes()

        result = StepResult(
            success=True,
            instruction=instr,
            pc_before=pc_before,
            pc_after=self.pc,
            cycles=self.cycle_count - cycles_before,
            halted=self.halted,
            breakpoint_hit=breakpoint_hit,
            register_changes=reg_changes,
            flag_changes=flag_changes,
        )

        # Track call stack for CALL/RET instructions
        if instr and instr.opcode == Op.CALL:
            self._call_stack.append(self.pc)
        elif instr and instr.opcode == Op.RET and self._call_stack:
            self._call_stack.pop()

        # Record trace entry if tracing is enabled
        if self._trace_enabled:
            self._record_trace_entry(result, instr)

        # Call step callback if registered
        if self._step_callback:
            self._step_callback(result)

        return result

    def continue_exec(self) -> StepResult:
        """Continue execution until breakpoint, halt, or error."""
        while not self.halted:
            result = self.step()

            if result.breakpoint_hit:
                return result
            if not result.success:
                return result
            if result.halted:
                return result

        return StepResult(
            success=True,
            halted=True,
            pc_before=self.pc,
            pc_after=self.pc,
            cycles=0,
        )

    def run_to_offset(self, target_offset: int) -> StepResult:
        """Execute until reaching a specific offset or halt."""
        while not self.halted and self.pc != target_offset:
            result = self.step()
            if not result.success or result.halted:
                return result

        return StepResult(
            success=True,
            halted=self.halted,
            pc_before=self.pc,
            pc_after=self.pc,
            cycles=0,
        )

    def reset(self) -> None:
        """Reset the debugger to its initial state."""
        super().reset()
        self._call_stack.clear()
        self._trace_entries.clear()
        self._pending_bp = None
        for bp in self._breakpoints.values():
            bp.hit_count = 0

    # ── Breakpoint management ───────────────────────────────────────────────

    def add_breakpoint(self, offset: int, condition: Optional[str] = None) -> bool:
        """Add a breakpoint at the given byte offset."""
        if offset not in self._breakpoints:
            self._breakpoints[offset] = Breakpoint(offset=offset, condition=condition)
            return True
        return False

    def remove_breakpoint(self, offset: int) -> bool:
        """Remove a breakpoint."""
        if offset in self._breakpoints:
            del self._breakpoints[offset]
            return True
        return False

    def enable_breakpoint(self, offset: int) -> bool:
        """Enable a breakpoint."""
        if offset in self._breakpoints:
            self._breakpoints[offset].enabled = True
            return True
        return False

    def disable_breakpoint(self, offset: int) -> bool:
        """Disable a breakpoint (without removing it)."""
        if offset in self._breakpoints:
            if not self._breakpoints[offset].enabled:
                return False  # Already disabled
            self._breakpoints[offset].enabled = False
            return True
        return False

    def list_breakpoints(self) -> List[Dict[str, Any]]:
        """List all breakpoints with their status."""
        return [
            {
                "offset": bp.offset,
                "offset_hex": f"0x{bp.offset:04X}",
                "enabled": bp.enabled,
                "hit_count": bp.hit_count,
                "condition": bp.condition,
            }
            for bp in sorted(self._breakpoints.values(), key=lambda x: x.offset)
        ]

    def clear_breakpoints(self) -> None:
        """Remove all breakpoints."""
        self._breakpoints.clear()

    # ── Watchpoint management ───────────────────────────────────────────────

    def watch_reg(self, reg_num: int, name: str = "") -> None:
        """Add a watchpoint for a register."""
        self._watchpoints.append(
            Watchpoint(reg_num=reg_num, name=name or f"R{reg_num}")
        )

    def unwatch_reg(self, reg_num: int) -> bool:
        """Remove a watchpoint."""
        for i, wp in enumerate(self._watchpoints):
            if wp.reg_num == reg_num:
                self._watchpoints.pop(i)
                return True
        return False

    def list_watchpoints(self) -> List[str]:
        """List all active watchpoints."""
        return [wp.name for wp in self._watchpoints]

    def clear_watchpoints(self) -> None:
        """Remove all watchpoints."""
        self._watchpoints.clear()

    # ── State inspection ────────────────────────────────────────────────────

    def inspect_reg(self, reg_num: int) -> int:
        """Get the value of a general-purpose register."""
        return self.regs.read_gp(reg_num)

    def inspect_fp_reg(self, reg_num: int) -> float:
        """Get the value of a floating-point register."""
        return self.regs.read_fp(reg_num)

    def set_reg(self, reg_num: int, value: int) -> None:
        """Set the value of a general-purpose register."""
        self.regs.write_gp(reg_num, value)

    def set_fp_reg(self, reg_num: int, value: float) -> None:
        """Set the value of a floating-point register."""
        self.regs.write_fp(reg_num, value)

    def inspect_mem(self, addr: int, length: int = 1) -> bytes:
        """Read bytes from the stack memory region."""
        stack = self.memory.get_region("stack")
        return stack.read(addr, length)

    def write_mem(self, addr: int, data: bytes) -> None:
        """Write bytes to the stack memory region."""
        stack = self.memory.get_region("stack")
        stack.write(addr, data)

    def backtrace(self) -> List[Dict[str, Any]]:
        """Get the current call stack (backtrace)."""
        frames = [{"pc": self.pc, "pc_hex": f"0x{self.pc:04X}", "type": "current"}]
        for i, ret_addr in enumerate(reversed(self._call_stack)):
            frames.append({
                "pc": ret_addr,
                "pc_hex": f"0x{ret_addr:04X}",
                "type": "return",
                "depth": i + 1,
            })
        return frames

    def get_flags(self) -> Dict[str, bool]:
        """Get the current condition flag states."""
        return {
            "zero": self._flag_zero,
            "sign": self._flag_sign,
            "carry": self._flag_carry,
            "overflow": self._flag_overflow,
        }

    def get_register_dump(self) -> Dict[str, int]:
        """Get all general-purpose register values."""
        return {f"R{i}": self.regs.read_gp(i) for i in range(16)}

    def get_stack_snapshot(self, num_words: int = 16) -> List[int]:
        """Get a snapshot of the stack (top N words)."""
        values = []
        stack_region = self.memory.get_region("stack")
        stack_size = stack_region.size

        for i in range(num_words):
            addr = self.regs.sp + i * 4
            if addr < 0 or addr + 4 > stack_size:
                break
            try:
                val = struct.unpack_from("<i", stack_region.data, addr)[0]
                values.append(val)
            except (struct.error, IndexError, OSError):
                break
        return values

    # ── Disassembly integration ─────────────────────────────────────────────

    def disassemble_at(self, offset: int, count: int = 5) -> List[DisassembledInstruction]:
        """Disassemble instructions starting at a given offset."""
        instructions = []
        current_offset = offset

        for _ in range(count):
            if current_offset >= len(self._original_bytecode):
                break
            try:
                instr = self._disassembler._disassemble_one(
                    self._original_bytecode, current_offset
                )
                instructions.append(instr)
                current_offset += instr.size
            except Exception:
                break

        return instructions

    def disassemble_current(self, count: int = 5) -> List[DisassembledInstruction]:
        """Disassemble instructions starting at the current PC."""
        return self.disassemble_at(self.pc, count)

    # ── Tracing ─────────────────────────────────────────────────────────────

    def _init_tracer(self) -> None:
        """Initialise trace recording."""
        self._trace_enabled = True
        self._trace_entries = []

    def _record_trace_entry(self, step_result: StepResult, instr: DisassembledInstruction) -> None:
        """Record a trace entry for the current step."""
        self._trace_entries.append({
            "step": self.cycle_count - 1,
            "pc": step_result.pc_before,
            "opcode": instr.opcode_name,
            "operands": instr.operands,
            "pc_after": step_result.pc_after,
            "register_changes": {
                k: [old, new] for k, (old, new) in step_result.register_changes.items()
            },
            "flag_changes": {
                k: [old, new] for k, (old, new) in step_result.flag_changes.items()
            },
        })

    def enable_trace(self) -> None:
        """Enable execution tracing."""
        self._init_tracer()

    def disable_trace(self) -> None:
        """Disable execution tracing."""
        self._trace_enabled = False

    def export_trace(self, filepath: Optional[str] = None) -> str:
        """Export the trace as JSON.

        Parameters
        ----------
        filepath:
            If provided, write JSON to this file.  Otherwise return the
            JSON string.
        """
        data = {
            "total_steps": len(self._trace_entries),
            "bytecode_size": len(self._original_bytecode),
            "final_state": {
                "pc": self.pc,
                "halted": self.halted,
                "cycle_count": self.cycle_count,
                "registers": self.regs.snapshot(),
                "flags": self.get_flags(),
            },
            "entries": self._trace_entries,
        }
        json_str = json.dumps(data, indent=2, default=str)
        if filepath:
            with open(filepath, "w") as f:
                f.write(json_str)
        return json_str

    def trace_report(self) -> str:
        """Print a brief trace summary."""
        lines = [
            "Trace Summary",
            "─" * 40,
            f"  Total steps traced : {len(self._trace_entries)}",
            f"  Bytecode size      : {len(self._original_bytecode)} bytes",
            f"  Final PC           : 0x{self.pc:04X}",
            f"  Halted             : {self.halted}",
        ]

        if self._trace_entries:
            # Count opcodes
            opcode_counts: Dict[str, int] = {}
            for entry in self._trace_entries:
                op = entry["opcode"]
                opcode_counts[op] = opcode_counts.get(op, 0) + 1

            lines.append(f"\n  Opcode frequency (top 10):")
            for name, cnt in sorted(opcode_counts.items(), key=lambda x: -x[1])[:10]:
                pct = cnt / len(self._trace_entries) * 100
                lines.append(f"    {name:<20} {cnt:>5} ({pct:5.1f}%)")

        return "\n".join(lines)

    # ── Callbacks ───────────────────────────────────────────────────────────

    def on_step(self, callback: Callable[[StepResult], None]) -> None:
        """Register a callback to be called after each step."""
        self._step_callback = callback

    # ── State formatting ────────────────────────────────────────────────────

    def format_state(self) -> str:
        """Format the current VM state for display."""
        lines = []

        # Header
        lines.append(
            f"PC=0x{self.pc:04x} | Cycles={self.cycle_count} | "
            f"Halted={self.halted} | Running={self.running}"
        )

        # Registers
        lines.append("\nRegisters:")
        for i in range(0, 16, 4):
            row = []
            for j in range(4):
                reg_num = i + j
                val = self.regs.read_gp(reg_num)
                suffix = ""
                if reg_num == 11:
                    suffix = " (SP)"
                elif reg_num == 14:
                    suffix = " (FP)"
                elif reg_num == 15:
                    suffix = " (LR)"
                row.append(f"R{reg_num:d}={val:>12,}{suffix}")
            lines.append("  " + "  ".join(row))

        # Flags
        flags = self.get_flags()
        flag_str = " ".join(
            name.upper() for name, val in flags.items() if val
        )
        lines.append(f"\nFlags: {flag_str if flag_str else '(none)'}")

        # Stack
        lines.append("\nStack (top 8 words):")
        stack_vals = self.get_stack_snapshot(8)
        for i, val in enumerate(stack_vals):
            addr = self.regs.sp + i * 4
            lines.append(f"  0x{addr:04x}: {val}")

        # Current instruction
        lines.append("\nCurrent instruction:")
        current_instrs = self.disassemble_current(1)
        if current_instrs:
            instr = current_instrs[0]
            lines.append(
                f"  {instr.offset:04x}: {instr.opcode_name} {instr.operands}"
            )

        # Breakpoints
        if self._breakpoints:
            lines.append("\nBreakpoints:")
            for bp in sorted(self._breakpoints.values(), key=lambda x: x.offset):
                status = "+" if bp.enabled else "-"
                lines.append(
                    f"  {status} 0x{bp.offset:04x} (hit {bp.hit_count} times)"
                )

        # Watchpoints
        if self._watchpoints:
            lines.append("\nWatchpoints:")
            for wp in self._watchpoints:
                val = self.inspect_reg(wp.reg_num)
                lines.append(f"  {wp.name} = {val}")

        return "\n".join(lines)

    # ── Interactive REPL ────────────────────────────────────────────────────

    def repl(self, input_fn: Callable[[str], str] = input, output_fn: Callable[[str], None] = print) -> None:
        """Run the interactive debugger REPL.

        Parameters
        ----------
        input_fn:
            Function to read user input (defaults to ``input()``).
        output_fn:
            Function to display output (defaults to ``print()``).
        """
        output_fn("FLUX Debugger — type 'h' for help, 'q' to quit\n")

        while True:
            try:
                # Show prompt with current PC
                prompt = f"\n(flux 0x{self.pc:04X}) "
                raw = input_fn(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                output_fn("\nExiting debugger.")
                return

            if not raw:
                # Empty input = step
                raw = "s"

            parts = raw.split()
            cmd = parts[0].lower()
            args = parts[1:]

            try:
                if cmd in ("q", "quit", "exit"):
                    output_fn("Exiting debugger.")
                    return

                elif cmd in ("h", "help", "?"):
                    output_fn(HELP_TEXT)

                elif cmd in ("s", "step"):
                    result = self.step()
                    self._print_step(result, output_fn)
                    if result.halted:
                        output_fn("\n⚠ VM HALTED")

                elif cmd in ("c", "continue", "r", "run"):
                    output_fn("Running...")
                    result = self.continue_exec()
                    self._print_step(result, output_fn)
                    if result.halted:
                        output_fn("\n⚠ VM HALTED")
                    elif result.breakpoint_hit:
                        output_fn(f"\n● Breakpoint hit at 0x{result.pc_before:04X}")
                    elif not result.success:
                        output_fn(f"\n✖ Error: {result.error}")

                elif cmd in ("n", "next"):
                    # Step over: if CALL, run until return
                    result = self.step()
                    self._print_step(result, output_fn)
                    if result.instruction and result.instruction.opcode == Op.CALL:
                        output_fn("  (stepping over CALL)")
                        # Run until RET or halt
                        depth = len(self._call_stack)
                        while not self.halted and len(self._call_stack) >= depth:
                            r = self.step()
                            if not r.success or r.halted:
                                break

                elif cmd == "reset":
                    self.reset()
                    output_fn("VM reset to initial state.")

                elif cmd in ("b", "break"):
                    if not args:
                        output_fn("Usage: b <addr>")
                    else:
                        addr = self._parse_addr(args[0])
                        if addr is not None:
                            self.add_breakpoint(addr)
                            output_fn(f"● Breakpoint set at 0x{addr:04X}")

                elif cmd == "bd":
                    if not args:
                        output_fn("Usage: bd <addr>")
                    else:
                        addr = self._parse_addr(args[0])
                        if addr is not None and self.disable_breakpoint(addr):
                            output_fn(f"  Breakpoint disabled at 0x{addr:04X}")

                elif cmd == "be":
                    if not args:
                        output_fn("Usage: be <addr>")
                    else:
                        addr = self._parse_addr(args[0])
                        if addr is not None and self.enable_breakpoint(addr):
                            output_fn(f"  Breakpoint enabled at 0x{addr:04X}")

                elif cmd == "br":
                    if not args:
                        output_fn("Usage: br <addr>")
                    else:
                        addr = self._parse_addr(args[0])
                        if addr is not None and self.remove_breakpoint(addr):
                            output_fn(f"  Breakpoint removed at 0x{addr:04X}")

                elif cmd in ("bl", "breakpoints"):
                    bps = self.list_breakpoints()
                    if not bps:
                        output_fn("  No breakpoints set.")
                    else:
                        for bp in bps:
                            status = "●" if bp["enabled"] else "○"
                            output_fn(
                                f"  {status} 0x{bp['offset']:04X} "
                                f"(hits: {bp['hit_count']})"
                            )

                elif cmd == "bc":
                    self.clear_breakpoints()
                    output_fn("  All breakpoints cleared.")

                elif cmd in ("i", "info"):
                    output_fn(self.format_state())

                elif cmd == "regs":
                    dump = self.get_register_dump()
                    for name, val in dump.items():
                        output_fn(f"  {name} = {val:>12,}  (0x{val & 0xFFFFFFFF:08X})")

                elif cmd == "reg":
                    if not args:
                        output_fn("Usage: reg <n>")
                    else:
                        n = int(args[0])
                        val = self.inspect_reg(n)
                        output_fn(f"  R{n} = {val} (0x{val & 0xFFFFFFFF:08X})")

                elif cmd == "set_reg":
                    if len(args) < 2:
                        output_fn("Usage: set_reg <n> <val>")
                    else:
                        n = int(args[0])
                        val = int(args[1], 0)
                        self.set_reg(n, val)
                        output_fn(f"  R{n} = {val}")

                elif cmd == "flags":
                    flags = self.get_flags()
                    for name, val in flags.items():
                        marker = "●" if val else "○"
                        output_fn(f"  {marker} {name}")

                elif cmd == "mem":
                    if not args:
                        output_fn("Usage: mem <addr> [len]")
                    else:
                        addr = self._parse_addr(args[0])
                        length = int(args[1]) if len(args) > 1 else 16
                        if addr is not None:
                            data = self.inspect_mem(addr, length)
                            hex_str = data.hex()
                            # Format in groups of 2
                            formatted = " ".join(
                                hex_str[i:i+2] for i in range(0, len(hex_str), 2)
                            )
                            output_fn(f"  0x{addr:04X}: {formatted}")

                elif cmd == "set_mem":
                    if len(args) < 2:
                        output_fn("Usage: set_mem <addr> <hex_bytes>")
                    else:
                        addr = self._parse_addr(args[0])
                        hex_data = args[1].replace(" ", "")
                        data = bytes.fromhex(hex_data)
                        if addr is not None:
                            self.write_mem(addr, data)
                            output_fn(f"  Wrote {len(data)} bytes at 0x{addr:04X}")

                elif cmd == "stack":
                    n = int(args[0]) if args else 8
                    vals = self.get_stack_snapshot(n)
                    for i, val in enumerate(vals):
                        addr = self.regs.sp + i * 4
                        output_fn(f"  0x{addr:04x}: {val:>12,}  (0x{val & 0xFFFFFFFF:08X})")

                elif cmd in ("bt", "backtrace"):
                    frames = self.backtrace()
                    if len(frames) <= 1:
                        output_fn("  (no call frames)")
                    else:
                        for frame in frames:
                            depth = frame.get("depth", 0)
                            indent = "  " * (depth + 1)
                            output_fn(f"  {indent}{frame['pc_hex']} ({frame['type']})")

                elif cmd == "dis":
                    if args:
                        addr = self._parse_addr(args[0])
                        count = int(args[1]) if len(args) > 1 else 5
                    else:
                        addr = self.pc
                        count = 5

                    if addr is not None:
                        instrs = self.disassemble_at(addr, count)
                        for instr in instrs:
                            marker = "►" if instr.offset == self.pc else " "
                            bp_mark = "●" if instr.offset in self._breakpoints else " "
                            color = get_instruction_color(instr.opcode)
                            reset = Colors.RESET
                            output_fn(
                                f"  {bp_mark}{marker} {instr.offset:04x}: "
                                f"{color}{instr.opcode_name:<12}{reset} "
                                f"{instr.operands}"
                            )

                elif cmd == "watch":
                    if not args:
                        output_fn("Usage: watch <reg> [name]")
                    else:
                        reg = int(args[0])
                        name = args[1] if len(args) > 1 else ""
                        self.watch_reg(reg, name)
                        output_fn(f"  Watching R{reg}")

                elif cmd == "unwatch":
                    if not args:
                        output_fn("Usage: unwatch <reg>")
                    else:
                        reg = int(args[0])
                        if self.unwatch_reg(reg):
                            output_fn(f"  Removed watch on R{reg}")

                elif cmd == "watches":
                    wps = self.list_watchpoints()
                    if not wps:
                        output_fn("  No watchpoints set.")
                    else:
                        for wp in wps:
                            output_fn(f"  {wp}")

                elif cmd == "trace":
                    if not args:
                        output_fn("Usage: trace on|off|export [file]|report")
                    elif args[0] == "on":
                        self.enable_trace()
                        output_fn("  Tracing enabled.")
                    elif args[0] == "off":
                        self.disable_trace()
                        output_fn("  Tracing disabled.")
                    elif args[0] == "export":
                        filepath = args[1] if len(args) > 1 else None
                        json_str = self.export_trace(filepath)
                        if filepath:
                            output_fn(f"  Trace exported to {filepath}")
                        else:
                            output_fn(json_str)
                    elif args[0] == "report":
                        output_fn(self.trace_report())

                elif cmd == "format":
                    output_fn(self.format_state())

                else:
                    output_fn(f"  Unknown command: {cmd}.  Type 'h' for help.")

            except ValueError as e:
                output_fn(f"  Error: {e}")
            except Exception as e:
                output_fn(f"  Error: {e}")

    def _print_step(self, result: StepResult, output_fn: Callable) -> None:
        """Print a step result in the REPL."""
        if result.instruction:
            instr = result.instruction
            color = get_instruction_color(instr.opcode)
            reset = Colors.RESET
            output_fn(
                f"  {instr.offset:04x}: {color}{instr.opcode_name:<12}{reset} "
                f"{instr.operands}"
            )

        if result.register_changes:
            parts = []
            for name, (old, new) in result.register_changes.items():
                parts.append(f"{name}: {old}→{new}")
            output_fn(f"  Δ {', '.join(parts)}")

        if result.flag_changes:
            parts = []
            for name, (old, new) in result.flag_changes.items():
                parts.append(f"{name}: {old}→{new}")
            output_fn(f"  Δ {', '.join(parts)}")

        if not result.success and result.error:
            output_fn(f"  ✖ {result.error}")

    @staticmethod
    def _parse_addr(s: str) -> Optional[int]:
        """Parse an address string (hex or decimal)."""
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s)
        except ValueError:
            return None

    # ── Utility ─────────────────────────────────────────────────────────────

    def _extract_code(self, bytecode: bytes) -> bytes:
        """Extract the code section from a FLUX binary file."""
        if len(bytecode) >= 18 and bytecode[:4] == b"FLUX":
            code_off = struct.unpack_from("<I", bytecode, 14)[0]
            if 18 <= code_off <= len(bytecode):
                return bytecode[code_off:]
        return bytecode


# ── Convenience functions ─────────────────────────────────────────────────────


def create_debugger(bytecode: bytes, **kwargs) -> FluxDebugger:
    """Create a FluxDebugger instance from bytecode.

    Parameters
    ----------
    bytecode:
        Raw bytecode bytes.
    **kwargs:
        Passed to ``FluxDebugger.__init__``.

    Returns
    -------
    FluxDebugger
        Configured debugger instance.
    """
    return FluxDebugger(bytecode, **kwargs)
