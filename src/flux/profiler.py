"""FLUX Execution Profiler — Opcode frequency, timing, and hotspot analysis.

Counts opcode frequency, measures execution time per opcode type, tracks
memory access patterns, reports hottest instructions, and tracks
conservation budget consumption over time.

Usage
-----

::

    from flux.profiler import FluxProfiler

    profiler = FluxProfiler()
    profile = profiler.profile(bytecode)
    print(profiler.report())

JSON export for tooling integration::

    json_str = profiler.to_json()
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from flux.bytecode.opcodes import Op, get_format
from flux.disasm import (
    ARITHMETIC_OPS,
    CONTROL_FLOW_OPS,
    MEMORY_OPS,
    COMPARISON_OPS,
    STACK_OPS,
    TYPE_OPS,
    SIMD_OPS,
    A2A_OPS,
    SYSTEM_OPS,
)
from flux.tracer import (
    FluxTracer,
    TraceResult,
    _categorise_opcode,
    _disassemble_at,
    _snapshot_registers,
    _snapshot_flags,
    _snapshot_memory,
)


__all__ = ["FluxProfiler", "ProfileResult"]


# ── Profile result ───────────────────────────────────────────────────────────


@dataclass
class OpcodeStats:
    """Statistics for a single opcode."""
    opcode: int
    opcode_name: str
    count: int = 0
    total_time_us: float = 0.0
    min_time_us: float = float("inf")
    max_time_us: float = 0.0

    @property
    def avg_time_us(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_time_us / self.count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opcode": f"0x{self.opcode:02X}",
            "opcode_name": self.opcode_name,
            "count": self.count,
            "total_time_us": round(self.total_time_us, 3),
            "avg_time_us": round(self.avg_time_us, 3),
            "min_time_us": round(self.min_time_us, 3) if self.min_time_us != float("inf") else 0.0,
            "max_time_us": round(self.max_time_us, 3),
        }


@dataclass
class MemoryAccessPattern:
    """Tracks memory access patterns."""
    reads: int = 0
    writes: int = 0
    regions_accessed: Counter = field(default_factory=Counter)
    addresses_read: Counter = field(default_factory=Counter)
    addresses_written: Counter = field(default_factory=Counter)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_reads": self.reads,
            "total_writes": self.writes,
            "regions_accessed": dict(self.regions_accessed),
            "hot_read_addresses": dict(self.addresses_read.most_common(20)),
            "hot_write_addresses": dict(self.addresses_written.most_common(20)),
        }


class ProfileResult:
    """Complete profiling result."""

    def __init__(self) -> None:
        self.opcode_stats: Dict[int, OpcodeStats] = {}
        self.category_stats: Dict[str, OpcodeStats] = {}
        self.memory_patterns = MemoryAccessPattern()
        self.total_instructions: int = 0
        self.total_time_us: float = 0.0
        self.total_cycles: int = 0
        self.halted: bool = False
        self.error: Optional[str] = None
        self.bytecode_size: int = 0
        self.conservation_consumed: int = 0
        self.conservation_by_category: Dict[str, int] = {}
        self.register_lifetimes: Dict[str, List[Tuple[int, int]]] = {}
        self.hotspots: List[Dict[str, Any]] = []

    @property
    def hottest_opcodes(self) -> List[Tuple[str, int, float]]:
        """Return top-10 hottest opcodes by count.

        Returns list of ``(opcode_name, count, percentage)`` tuples.
        """
        sorted_ops = sorted(
            self.opcode_stats.values(),
            key=lambda s: s.count,
            reverse=True,
        )
        total = self.total_instructions or 1
        return [
            (s.opcode_name, s.count, s.count / total * 100)
            for s in sorted_ops[:10]
        ]

    @property
    def slowest_opcodes(self) -> List[Tuple[str, float, int]]:
        """Return top-10 slowest opcodes by total time.

        Returns list of ``(opcode_name, total_time_us, count)`` tuples.
        """
        sorted_ops = sorted(
            self.opcode_stats.values(),
            key=lambda s: s.total_time_us,
            reverse=True,
        )
        return [
            (s.opcode_name, s.total_time_us, s.count)
            for s in sorted_ops[:10]
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialisation."""
        return {
            "summary": {
                "total_instructions": self.total_instructions,
                "total_cycles": self.total_cycles,
                "total_time_us": round(self.total_time_us, 3),
                "bytecode_size": self.bytecode_size,
                "halted": self.halted,
                "error": self.error,
                "conservation_consumed": self.conservation_consumed,
                "unique_opcodes": len(self.opcode_stats),
            },
            "opcode_stats": [
                s.to_dict() for s in
                sorted(self.opcode_stats.values(), key=lambda x: x.count, reverse=True)
            ],
            "category_stats": {
                cat: stats.to_dict()
                for cat, stats in self.category_stats.items()
            },
            "hottest_opcodes": [
                {"name": name, "count": cnt, "percentage": round(pct, 2)}
                for name, cnt, pct in self.hottest_opcodes
            ],
            "slowest_opcodes": [
                {"name": name, "total_time_us": round(t, 3), "count": cnt}
                for name, t, cnt in self.slowest_opcodes
            ],
            "memory_patterns": self.memory_patterns.to_dict(),
            "conservation_by_category": self.conservation_by_category,
            "hotspots": self.hotspots,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize profile to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ── Memory access tracking ───────────────────────────────────────────────────

# Opcodes that read from memory
_MEMORY_READ_OPS = {Op.LOAD, Op.LOAD8, Op.POP, Op.MEMCOPY, Op.MEMCMP}
# Opcodes that write to memory
_MEMORY_WRITE_OPS = {Op.STORE, Op.STORE8, Op.PUSH, Op.MEMSET, Op.MEMCOPY}


# ── Main Profiler ────────────────────────────────────────────────────────────


class FluxProfiler:
    """Profiles FLUX bytecode execution.

    Wraps the VM ``Interpreter`` to collect per-opcode timing, frequency,
    and memory access statistics.  Produces a detailed profile report
    suitable for optimisation analysis.

    Parameters
    ----------
    warmup_steps:
        Number of initial steps to skip when calculating timing statistics
        (reduces JIT/cache warmup noise).  Default: 0.

    Example
    -------

    ::

        profiler = FluxProfiler()
        result = profiler.profile(bytecode)
        print(profiler.report(result))
    """

    def __init__(self, warmup_steps: int = 0) -> None:
        self.warmup_steps = warmup_steps
        self._result: Optional[ProfileResult] = None

    def profile(
        self,
        bytecode: bytes,
        max_steps: int = 10_000,
        memory_size: int = 65536,
    ) -> ProfileResult:
        """Run bytecode with full profiling.

        Parameters
        ----------
        bytecode:
            Compiled FLUX bytecode bytes.
        max_steps:
            Maximum instructions to execute.
        memory_size:
            Size of default memory regions.

        Returns
        -------
        ProfileResult
            Complete profiling data.
        """
        from flux.vm.interpreter import Interpreter

        result = ProfileResult()
        result.bytecode_size = len(bytecode)
        self._result = result

        vm = Interpreter(bytecode, memory_size=memory_size)
        vm.max_cycles = max_steps

        # Tracking state
        opcode_counter: Counter = Counter()
        opcode_times: Dict[int, List[float]] = defaultdict(list)
        category_counter: Counter = Counter()
        category_times: Dict[str, List[float]] = defaultdict(list)
        step_count = 0
        conservation_total = 0
        conservation_by_cat: Dict[str, int] = defaultdict(int)

        # Conservation weights
        from flux.tracer import ConservationLedger
        cat_weights = ConservationLedger.CATEGORY_WEIGHTS

        original_step = vm._step

        def profiled_step():
            nonlocal step_count, conservation_total

            pc_before = vm.pc
            opcode_byte = (
                bytecode[pc_before]
                if pc_before < len(bytecode)
                else 0
            )

            category = _categorise_opcode(opcode_byte)

            # Track memory access patterns
            try:
                op = Op(opcode_byte)
                if op in _MEMORY_READ_OPS:
                    result.memory_patterns.reads += 1
                    # Try to determine which region
                    try:
                        result.memory_patterns.regions_accessed["stack"] += 1
                    except Exception:
                        pass
                elif op in _MEMORY_WRITE_OPS:
                    result.memory_patterns.writes += 1
                    try:
                        result.memory_patterns.regions_accessed["stack"] += 1
                    except Exception:
                        pass
            except (ValueError, Exception):
                pass

            # Conservation tracking
            weight = cat_weights.get(category, 1)
            conservation_total += weight
            conservation_by_cat[category] += weight

            # Time the execution
            t0 = time.perf_counter()
            original_step()
            elapsed_us = (time.perf_counter() - t0) * 1_000_000

            step_count += 1
            opcode_counter[opcode_byte] += 1
            category_counter[category] += 1

            if step_count > self.warmup_steps:
                opcode_times[opcode_byte].append(elapsed_us)
                category_times[category].append(elapsed_us)

        vm._step = profiled_step

        t_start = time.perf_counter()
        try:
            cycles = vm.execute()
            result.total_cycles = cycles
            result.halted = vm.halted
        except Exception as exc:
            result.error = str(exc)
        t_end = time.perf_counter()

        result.total_instructions = step_count
        result.total_time_us = (t_end - t_start) * 1_000_000
        result.conservation_consumed = conservation_total
        result.conservation_by_category = dict(conservation_by_cat)

        # Build per-opcode stats
        for opcode_byte, times_list in opcode_times.items():
            try:
                op_name = Op(opcode_byte).name
            except ValueError:
                op_name = f"0x{opcode_byte:02X}"

            stats = OpcodeStats(
                opcode=opcode_byte,
                opcode_name=op_name,
                count=opcode_counter[opcode_byte],
                total_time_us=sum(times_list),
                min_time_us=min(times_list) if times_list else 0,
                max_time_us=max(times_list) if times_list else 0,
            )
            result.opcode_stats[opcode_byte] = stats

        # Build per-category stats
        for cat, times_list in category_times.items():
            stats = OpcodeStats(
                opcode=0,
                opcode_name=cat,
                count=category_counter[cat],
                total_time_us=sum(times_list),
                min_time_us=min(times_list) if times_list else 0,
                max_time_us=max(times_list) if times_list else 0,
            )
            result.category_stats[cat] = stats

        # Identify hotspots (PC addresses executed most frequently)
        pc_counter: Counter = Counter()
        # Re-run a quick trace to get PC frequencies
        # (We could track during profiling, but we keep it clean)
        tracer = FluxTracer()
        trace = tracer.trace(bytecode, max_steps=max_steps, memory_size=memory_size)
        for entry in trace.entries:
            pc_counter[entry.pc] += 1

        for pc, cnt in pc_counter.most_common(10):
            op_name, operand = _disassemble_at(bytecode, pc)
            result.hotspots.append({
                "pc": pc,
                "pc_hex": f"0x{pc:04X}",
                "opcode": op_name,
                "operand": operand,
                "execution_count": cnt,
                "percentage": round(cnt / max(step_count, 1) * 100, 2),
            })

        return result

    # ── Reporting ─────────────────────────────────────────────────────────

    def report(self, result: Optional[ProfileResult] = None) -> str:
        """Generate a human-readable profile report.

        Parameters
        ----------
        result:
            A previously obtained ``ProfileResult``.  If omitted, the last
            profile is used.
        """
        if result is None:
            result = self._result
        if result is None:
            return "No profile available.  Call profile() first."

        lines: List[str] = []
        lines.append("FLUX Execution Profile")
        lines.append("═" * 72)
        lines.append("")

        # Summary
        lines.append("Summary")
        lines.append("─" * 40)
        lines.append(f"  Instructions executed : {result.total_instructions:,}")
        lines.append(f"  Cycles consumed      : {result.total_cycles:,}")
        lines.append(f"  Total time           : {result.total_time_us:.1f} µs "
                      f"({result.total_time_us / 1000:.3f} ms)")
        lines.append(f"  Bytecode size        : {result.bytecode_size} bytes")
        lines.append(f"  Unique opcodes       : {len(result.opcode_stats)}")
        lines.append(f"  Halted cleanly       : {result.halted}")
        if result.error:
            lines.append(f"  Error                : {result.error}")
        avg_time = (
            result.total_time_us / result.total_instructions
            if result.total_instructions
            else 0
        )
        lines.append(f"  Avg time/instruction : {avg_time:.3f} µs")
        lines.append(f"  Conservation budget  : {result.conservation_consumed} units")
        lines.append("")

        # Hottest opcodes
        lines.append("Hottest Opcodes (by frequency)")
        lines.append("─" * 40)
        if result.hottest_opcodes:
            lines.append(f"  {'Opcode':<20} {'Count':>8} {'%':>7}")
            lines.append(f"  {'─' * 20} {'─' * 8} {'─' * 7}")
            for name, cnt, pct in result.hottest_opcodes:
                lines.append(f"  {name:<20} {cnt:>8} {pct:>6.1f}%")
        else:
            lines.append("  (no data)")
        lines.append("")

        # Slowest opcodes
        lines.append("Slowest Opcodes (by total time)")
        lines.append("─" * 40)
        if result.slowest_opcodes:
            lines.append(f"  {'Opcode':<20} {'Total µs':>10} {'Count':>8}")
            lines.append(f"  {'─' * 20} {'─' * 10} {'─' * 8}")
            for name, t, cnt in result.slowest_opcodes:
                lines.append(f"  {name:<20} {t:>10.1f} {cnt:>8}")
        else:
            lines.append("  (no data)")
        lines.append("")

        # Category breakdown
        lines.append("Category Breakdown")
        lines.append("─" * 40)
        if result.category_stats:
            lines.append(
                f"  {'Category':<20} {'Count':>8} {'Total µs':>10} "
                f"{'Avg µs':>8} {'Budget':>7}"
            )
            lines.append(f"  {'─' * 20} {'─' * 8} {'─' * 10} {'─' * 8} {'─' * 7}")
            for cat in sorted(
                result.category_stats.keys(),
                key=lambda c: result.category_stats[c].count,
                reverse=True,
            ):
                stats = result.category_stats[cat]
                budget = result.conservation_by_category.get(cat, 0)
                lines.append(
                    f"  {cat:<20} {stats.count:>8} "
                    f"{stats.total_time_us:>10.1f} "
                    f"{stats.avg_time_us:>8.3f} {budget:>7}"
                )
        lines.append("")

        # Conservation budget
        lines.append("Conservation Budget Consumption")
        lines.append("─" * 40)
        total_budget = result.conservation_consumed
        for cat, consumed in sorted(
            result.conservation_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            pct = (consumed / total_budget * 100) if total_budget else 0
            bar = "█" * int(pct / 2)
            lines.append(f"  {cat:<20} {consumed:>6} ({pct:5.1f}%) {bar}")
        lines.append(f"  {'─' * 20}")
        lines.append(f"  {'TOTAL':<20} {total_budget:>6}")
        lines.append("")

        # Memory access patterns
        lines.append("Memory Access Patterns")
        lines.append("─" * 40)
        mp = result.memory_patterns
        lines.append(f"  Total reads  : {mp.reads}")
        lines.append(f"  Total writes : {mp.writes}")
        if mp.regions_accessed:
            lines.append(f"  Regions accessed:")
            for region, cnt in mp.regions_accessed.most_common():
                lines.append(f"    {region}: {cnt}")
        lines.append("")

        # Hotspots (PC addresses)
        lines.append("Execution Hotspots (most-executed PC addresses)")
        lines.append("─" * 40)
        if result.hotspots:
            lines.append(
                f"  {'PC':>8} {'Opcode':<16} {'Operand':<20} "
                f"{'Execs':>6} {'%':>6}"
            )
            lines.append(f"  {'─' * 8} {'─' * 16} {'─' * 20} {'─' * 6} {'─' * 6}")
            for hs in result.hotspots:
                lines.append(
                    f"  {hs['pc_hex']:>8} {hs['opcode']:<16} "
                    f"{hs['operand']:<20} {hs['execution_count']:>6} "
                    f"{hs['percentage']:>5.1f}%"
                )
        else:
            lines.append("  (no hotspot data)")
        lines.append("")

        lines.append("═" * 72)
        return "\n".join(lines)

    def to_json(self, result: Optional[ProfileResult] = None, indent: int = 2) -> str:
        """Export profile as JSON for tooling."""
        if result is None:
            result = self._result
        if result is None:
            return json.dumps({"error": "No profile available"})
        return result.to_json(indent=indent)
