"""FLUX Execution Tracer — Instruction-level trace recording for FLUX bytecode.

Records every instruction executed by the VM, capturing register state,
flags, and memory snapshots before and after each step.  Produces both
human-readable trace reports and machine-readable JSON for visualisation
tooling.

Design
------

The tracer hooks into the existing ``Interpreter`` via a lightweight
callback protocol.  The VM already supports ``dump_state()`` and
``snapshot()`` on its register file, so the tracer simply calls these
at the right moments.

Usage
-----

::

    from flux.tracer import FluxTracer
    from flux.asm import CrossAssembler

    asm = CrossAssembler()
    result = asm.assemble_source("MOVI R0, 42\\nHALT")
    bytecode = result.bytecode

    tracer = FluxTracer()
    trace = tracer.trace(bytecode)
    print(tracer.report())

Or via the VM directly::

    from flux.vm.interpreter import Interpreter
    from flux.tracer import FluxTracer

    tracer = FluxTracer()
    vm = Interpreter(bytecode)
    vm._tracer = tracer   # attach
    tracer.attach(vm)
    vm.execute()
    print(tracer.report())
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from flux.bytecode.opcodes import Op, get_format, instruction_size
from flux.disasm import FluxDisassembler, DisassembledInstruction


__all__ = [
    "FluxTracer",
    "TraceEntry",
    "TraceResult",
]


# ── Data structures ──────────────────────────────────────────────────────────


class TraceEntry:
    """A single trace entry recording VM state at one instruction."""

    __slots__ = (
        "step",
        "pc",
        "opcode",
        "opcode_name",
        "operand",
        "registers_before",
        "registers_after",
        "flags_before",
        "flags_after",
        "timestamp_us",
    )

    def __init__(
        self,
        step: int,
        pc: int,
        opcode: int,
        opcode_name: str,
        operand: str,
        registers_before: Dict[str, Any],
        registers_after: Dict[str, Any],
        flags_before: Dict[str, bool],
        flags_after: Dict[str, bool],
        timestamp_us: float,
    ) -> None:
        self.step = step
        self.pc = pc
        self.opcode = opcode
        self.opcode_name = opcode_name
        self.operand = operand
        self.registers_before = registers_before
        self.registers_after = registers_after
        self.flags_before = flags_before
        self.flags_after = flags_after
        self.timestamp_us = timestamp_us

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "step": self.step,
            "pc": self.pc,
            "opcode": f"0x{self.opcode:02X}",
            "opcode_name": self.opcode_name,
            "operand": self.operand,
            "registers_before": self.registers_before,
            "registers_after": self.registers_after,
            "flags_before": self.flags_before,
            "flags_after": self.flags_after,
            "timestamp_us": round(self.timestamp_us, 3),
        }

    def __repr__(self) -> str:
        return (
            f"TraceEntry(step={self.step}, pc=0x{self.pc:04X}, "
            f"opcode={self.opcode_name})"
        )


class TraceResult:
    """The complete result of a traced execution."""

    def __init__(self) -> None:
        self.entries: List[TraceEntry] = []
        self.total_cycles: int = 0
        self.halted: bool = False
        self.error: Optional[str] = None
        self.bytecode_size: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.final_registers: Dict[str, Any] = {}
        self.final_flags: Dict[str, bool] = {}
        self.memory_regions: List[Dict[str, Any]] = []

    @property
    def duration_ms(self) -> float:
        """Execution duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000.0

    @property
    def instructions_per_second(self) -> float:
        """Instructions executed per second."""
        elapsed = self.end_time - self.start_time
        if elapsed > 0:
            return len(self.entries) / elapsed
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary": {
                "total_steps": len(self.entries),
                "total_cycles": self.total_cycles,
                "halted": self.halted,
                "error": self.error,
                "bytecode_size": self.bytecode_size,
                "duration_ms": round(self.duration_ms, 3),
                "instructions_per_second": round(self.instructions_per_second, 1),
            },
            "final_state": {
                "registers": self.final_registers,
                "flags": self.final_flags,
                "memory_regions": self.memory_regions,
            },
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize trace to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ── Register / flag helpers ──────────────────────────────────────────────────


def _snapshot_registers(regs) -> Dict[str, Any]:
    """Capture register file state as a flat dict."""
    snap = regs.snapshot()
    gp = snap.get("gp", [])
    fp = snap.get("fp", [])
    result: Dict[str, Any] = {}
    for i, v in enumerate(gp):
        result[f"R{i}"] = v
    for i, v in enumerate(fp):
        result[f"F{i}"] = v
    # Only include non-zero vector registers
    vec = snap.get("vec", [])
    for i, v in enumerate(vec):
        if v is not None:
            result[f"V{i}"] = v.hex() if isinstance(v, (bytes, bytearray)) else str(v)
    return result


def _snapshot_flags(interpreter) -> Dict[str, bool]:
    """Capture condition flags from the interpreter."""
    return {
        "zero": interpreter._flag_zero,
        "sign": interpreter._flag_sign,
        "carry": interpreter._flag_carry,
        "overflow": interpreter._flag_overflow,
    }


def _snapshot_memory(interpreter) -> List[Dict[str, Any]]:
    """Capture memory regions state."""
    regions: List[Dict[str, Any]] = []
    for name, region in interpreter.memory._regions.items():
        # Only capture small regions fully; hash larger ones
        if region.size <= 256:
            data_hex = region.data.hex()
        else:
            # Capture first and last 32 bytes + a hash summary
            head = region.data[:32].hex()
            tail = region.data[-32:].hex()
            data_hex = f"{head}…({region.size}B)…{tail}"
        regions.append({
            "name": name,
            "size": region.size,
            "owner": region.owner,
            "borrowers": list(region.borrowers),
            "data_preview": data_hex,
        })
    return regions


# ── Disassembly helper ───────────────────────────────────────────────────────


def _disassemble_at(bytecode: bytes, pc: int) -> Tuple[str, str]:
    """Disassemble a single instruction at *pc*.

    Returns ``(opcode_name, operand_str)``.
    """
    disasm = FluxDisassembler(color_output=False)
    try:
        result = disasm.disassemble(bytecode[pc:pc + 8])
        if result.instructions:
            instr = result.instructions[0]
            return instr.opcode_name, instr.operands
    except Exception:
        pass
    # Fallback: just show the raw opcode
    if pc < len(bytecode):
        op = bytecode[pc]
        try:
            return Op(op).name, ""
        except ValueError:
            return f"0x{op:02X}", ""
    return "???", ""


# ── Conservation ledger ──────────────────────────────────────────────────────


class ConservationLedger:
    """Tracks conservation-budget consumption over the execution.

    The FLUX conservation model treats each instruction as consuming a
    small amount of "presence budget".  Different opcode categories have
    different weights:

    - Arithmetic / logic:  1 unit
    - Memory access:       2 units
    - Control flow:        1 unit
    - A2A protocol:        5 units
    - System / resource:   3 units
    - SIMD:                4 units
    """
    CATEGORY_WEIGHTS = {
        "arithmetic": 1,
        "comparison": 1,
        "control_flow": 1,
        "stack": 1,
        "memory": 2,
        "type_op": 2,
        "simd": 4,
        "a2a": 5,
        "system": 3,
        # Room interaction categories for PLATO governance logging
        "room_enter": 2,
        "room_exit": 2,
        "protocol_send": 3,
        "protocol_receive": 3,
        "governance_decision": 4,
        "budget_check": 1,
        "budget_request": 2,
    }

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []
        self.total_consumed: int = 0

        self.entries: List[Dict[str, Any]] = []
        self.total_consumed: int = 0

    def record(self, step: int, pc: int, opcode_name: str, category: str) -> None:
        """Record a single instruction's conservation cost."""
        weight = self.CATEGORY_WEIGHTS.get(category, 1)
        self.total_consumed += weight
        self.entries.append({
            "step": step,
            "pc": pc,
            "opcode": opcode_name,
            "category": category,
            "cost": weight,
            "cumulative": self.total_consumed,
        })

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to dictionary."""
        return {
            "total_consumed": self.total_consumed,
            "entry_count": len(self.entries),
            "entries": self.entries,
        }

    def report(self) -> str:
        """Human-readable conservation summary."""
        lines = [
            "Conservation Ledger",
            "═" * 40,
            f"Total budget consumed : {self.total_consumed} units",
            f"Instructions traced   : {len(self.entries)}",
        ]

        # Per-category breakdown
        cat_totals: Dict[str, int] = {}
        for entry in self.entries:
            cat = entry["category"]
            cat_totals[cat] = cat_totals.get(cat, 0) + entry["cost"]

        if cat_totals:
            lines.append("")
            lines.append("By category:")
            for cat, total in sorted(cat_totals.items(), key=lambda x: -x[1]):
                pct = (total / self.total_consumed * 100) if self.total_consumed else 0
                lines.append(f"  {cat:20s} {total:6d} ({pct:5.1f}%)")

        return "\n".join(lines)


def _categorise_opcode(opcode: int) -> str:
    """Categorise an opcode for conservation accounting."""
    try:
        op = Op(opcode)
    except ValueError:
        return "system"

    from flux.disasm import (
        ARITHMETIC_OPS, CONTROL_FLOW_OPS, MEMORY_OPS,
        COMPARISON_OPS, STACK_OPS, TYPE_OPS, SIMD_OPS,
        A2A_OPS, SYSTEM_OPS,
    )

    if op in ARITHMETIC_OPS:
        return "arithmetic"
    if op in COMPARISON_OPS:
        return "comparison"
    if op in CONTROL_FLOW_OPS:
        return "control_flow"
    if op in STACK_OPS:
        return "stack"
    if op in MEMORY_OPS:
        return "memory"
    if op in TYPE_OPS:
        return "type_op"
    if op in SIMD_OPS:
        return "simd"
    if op in A2A_OPS:
        return "a2a"
    if op in SYSTEM_OPS:
        return "system"
    return "system"


# ── Main Tracer ──────────────────────────────────────────────────────────────


class FluxTracer:
    """Traces FLUX bytecode execution for debugging and profiling.

    The tracer wraps the standard ``Interpreter`` and records a complete
    execution trace including register state before/after each instruction,
    condition flags, and memory snapshots.

    Parameters
    ----------
    capture_memory:
        If True, capture memory region state after each instruction.
        Disabled by default for performance — enable for deep debugging.
    max_trace_entries:
        Safety limit on the number of trace entries (default 100 000).

    Example
    -------

    ::

        tracer = FluxTracer()
        result = tracer.trace(bytecode)
        print(tracer.report())

        # Machine-readable JSON
        json_output = result.to_json()
    """

    def __init__(
        self,
        capture_memory: bool = False,
        max_trace_entries: int = 100_000,
    ) -> None:
        self.capture_memory = capture_memory
        self.max_trace_entries = max_trace_entries
        self.ledger = ConservationLedger()
        self._result: Optional[TraceResult] = None

    # ── Attachment ────────────────────────────────────────────────────────

    def attach(self, interpreter) -> None:
        """Attach to an existing Interpreter by monkey-patching ``_step``.

        This wraps the interpreter's ``_step`` method so we can capture
        state before and after each instruction.
        """
        self._interpreter = interpreter
        original_step = interpreter._step

        # Use a mutable container to hold the step counter
        state = {"step": 0}
        tracer = self
        t0 = time.perf_counter()

        def traced_step():
            # Capture before-state
            pc_before = interpreter.pc
            opcode_byte = (
                interpreter.bytecode[pc_before]
                if pc_before < len(interpreter.bytecode)
                else 0
            )
            opcode_name, operand_str = _disassemble_at(
                interpreter.bytecode, pc_before
            )
            regs_before = _snapshot_registers(interpreter.regs)
            flags_before = _snapshot_flags(interpreter)

            # Record conservation ledger entry
            category = _categorise_opcode(opcode_byte)
            tracer.ledger.record(
                step=state["step"],
                pc=pc_before,
                opcode_name=opcode_name,
                category=category,
            )

            # Execute the original step
            original_step()

            # Capture after-state
            regs_after = _snapshot_registers(interpreter.regs)
            flags_after = _snapshot_flags(interpreter)

            timestamp = (time.perf_counter() - t0) * 1_000_000  # microseconds

            entry = TraceEntry(
                step=state["step"],
                pc=pc_before,
                opcode=opcode_byte,
                opcode_name=opcode_name,
                operand=operand_str,
                registers_before=regs_before,
                registers_after=regs_after,
                flags_before=flags_before,
                flags_after=flags_after,
                timestamp_us=timestamp,
            )
            tracer._add_entry(entry)

            state["step"] += 1

        interpreter._step = traced_step

    def detach(self) -> None:
        """Remove the tracing hook (restores original ``_step``)."""
        if hasattr(self, "_interpreter") and hasattr(self, "_original_step"):
            self._interpreter._step = self._original_step

    def _add_entry(self, entry: TraceEntry) -> None:
        """Add an entry to the result, respecting the max limit."""
        if self._result is None:
            self._result = TraceResult()
        if len(self._result.entries) < self.max_trace_entries:
            self._result.entries.append(entry)

    # ── Trace execution ───────────────────────────────────────────────────

    def trace(
        self,
        bytecode: bytes,
        max_steps: int = 10_000,
        memory_size: int = 65536,
    ) -> TraceResult:
        """Run bytecode with full tracing.

        Parameters
        ----------
        bytecode:
            Compiled FLUX bytecode bytes.
        max_steps:
            Maximum number of instructions to execute.
        memory_size:
            Size of default memory regions.

        Returns
        -------
        TraceResult
            The complete trace of the execution.
        """
        from flux.vm.interpreter import Interpreter

        self.ledger = ConservationLedger()
        self._result = TraceResult()
        self._result.bytecode_size = len(bytecode)
        self._result.start_time = time.perf_counter()

        vm = Interpreter(bytecode, memory_size=memory_size)
        vm.max_cycles = max_steps
        self.attach(vm)

        try:
            cycles = vm.execute()
            self._result.total_cycles = cycles
            self._result.halted = vm.halted
        except Exception as exc:
            self._result.error = str(exc)
        finally:
            self._result.end_time = time.perf_counter()
            self._result.final_registers = _snapshot_registers(vm.regs)
            self._result.final_flags = _snapshot_flags(vm)
            self._result.memory_regions = _snapshot_memory(vm)

        return self._result

    # ── Reporting ─────────────────────────────────────────────────────────

    def report(self, result: Optional[TraceResult] = None) -> str:
        """Generate a human-readable trace report.

        Parameters
        ----------
        result:
            A previously obtained ``TraceResult``.  If omitted, the last
            trace produced by :meth:`trace` is used.
        """
        if result is None:
            result = self._result
        if result is None:
            return "No trace available.  Call trace() first."

        lines: List[str] = []
        lines.append("FLUX Execution Trace")
        lines.append("═" * 72)
        lines.append("")

        # Summary
        lines.append("Summary")
        lines.append("─" * 40)
        lines.append(f"  Steps executed   : {len(result.entries)}")
        lines.append(f"  Cycles consumed  : {result.total_cycles}")
        lines.append(f"  Bytecode size    : {result.bytecode_size} bytes")
        lines.append(f"  Duration         : {result.duration_ms:.3f} ms")
        lines.append(f"  Throughput       : {result.instructions_per_second:,.0f} insn/s")
        lines.append(f"  Halted cleanly   : {result.halted}")
        if result.error:
            lines.append(f"  Error            : {result.error}")
        lines.append("")

        # Conservation ledger
        lines.append(self.ledger.report())
        lines.append("")

        # Final register state
        lines.append("Final Register State")
        lines.append("─" * 40)
        for name, val in sorted(result.final_registers.items()):
            if val != 0:  # Only show non-zero registers
                lines.append(f"  {name:5s} = {val}")
        # Show all GP registers even if zero for completeness
        for i in range(16):
            name = f"R{i}"
            val = result.final_registers.get(name, 0)
            lines.append(f"  {name:5s} = {val}")
        lines.append("")

        # Final flags
        lines.append("Final Flags")
        lines.append("─" * 40)
        for name, val in result.final_flags.items():
            lines.append(f"  {name:10s} = {val}")
        lines.append("")

        # Memory regions
        if result.memory_regions:
            lines.append("Memory Regions")
            lines.append("─" * 40)
            for region in result.memory_regions:
                lines.append(
                    f"  {region['name']:12s}  size={region['size']:6d}  "
                    f"owner={region['owner']}"
                )
            lines.append("")

        # Instruction trace (abbreviated for readability)
        max_display = 200
        entries = result.entries
        if len(entries) > max_display:
            lines.append(
                f"Instruction Trace (showing first {max_display} of "
                f"{len(entries)} steps)"
            )
        else:
            lines.append("Instruction Trace")
        lines.append("─" * 72)

        header = (
            f"{'Step':>5}  {'PC':>6}  {'Opcode':<16} {'Operand':<20} "
            f"{'Δ Registers'}"
        )
        lines.append(header)
        lines.append("─" * 72)

        for entry in entries[:max_display]:
            # Detect which registers changed
            changes = []
            for name in entry.registers_after:
                before = entry.registers_before.get(name, 0)
                after = entry.registers_after.get(name, 0)
                if before != after:
                    changes.append(f"{name}: {before}→{after}")

            delta_str = ", ".join(changes[:4])
            if len(changes) > 4:
                delta_str += f" (+{len(changes) - 4} more)"

            lines.append(
                f"{entry.step:>5}  0x{entry.pc:04X}  "
                f"{entry.opcode_name:<16} {entry.operand:<20} "
                f"{delta_str}"
            )

        if len(entries) > max_display:
            lines.append(f"  … {len(entries) - max_display} more steps truncated")

        lines.append("")
        lines.append("═" * 72)

        return "\n".join(lines)

    def to_json(self, result: Optional[TraceResult] = None, indent: int = 2) -> str:
        """Export trace as JSON for tooling.

        Parameters
        ----------
        result:
            A previously obtained ``TraceResult``.  If omitted, the last
            trace is used.
        indent:
            JSON indentation level.
        """
        if result is None:
            result = self._result
        if result is None:
            return json.dumps({"error": "No trace available"})

        data = result.to_dict()
        data["conservation_ledger"] = self.ledger.to_dict()
        return json.dumps(data, indent=indent, default=str)
