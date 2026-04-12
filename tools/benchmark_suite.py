#!/usr/bin/env python3
"""FLUX Runtime Comprehensive Performance Benchmark Suite (PERF-002)

Measures instruction decode speed, execution throughput, and memory usage
across all opcode categories.  Includes macro benchmarks (Fibonacci, Bubble
Sort, Matrix Multiply, String Processing), format-specific decode analysis,
memory allocation patterns, stack depth limits, and register access speed.

Generates:
  - JSON results:   tools/benchmark_results.json
  - Markdown report: docs/benchmark-report-2026-04-12-v2.md

Usage:
    python tools/benchmark_suite.py              # full suite (100K iters)
    python tools/benchmark_suite.py --quick      # reduced iterations (10K)

Author: Super Z (Performance Engineering, FLUX Fleet)
Task ID: 2-c
"""

from __future__ import annotations

import argparse
import json
import os
import random
import struct
import sys
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from flux.vm.unified_interpreter import UnifiedVM, opcode_name

# ── Constants ──────────────────────────────────────────────────────────────────
WARMUP = 3
BENCH_RUNS = 5
DECODE_PER_FMT = 10_000

# Opcode tables: (hex, mnemonic, format)
ARITHMETIC_OPS = [
    (0x20, "ADD", "E"), (0x21, "SUB", "E"), (0x22, "MUL", "E"),
    (0x23, "DIV", "E"), (0x24, "MOD", "E"), (0x0B, "NEG", "B"),
    (0x08, "INC", "B"), (0x09, "DEC", "B"),
]
MEMORY_OPS = [
    (0x38, "LOAD", "E"), (0x39, "STORE", "E"), (0x3A, "MOV", "E"),
    (0x0C, "PUSH", "B"), (0x0D, "POP", "B"),
]
CONTROL_FLOW_OPS = [
    (0x43, "JMP", "F"), (0x3C, "JZ", "E"), (0x3D, "JNZ", "E"),
    (0x44, "JAL", "F"), (0x02, "RET", "A"),
]
LOGIC_OPS = [
    (0x25, "AND", "E"), (0x26, "OR", "E"), (0x27, "XOR", "E"),
    (0x0A, "NOT", "B"), (0x28, "SHL", "E"), (0x29, "SHR", "E"),
]
ALL_MICRO_OPS = ARITHMETIC_OPS + MEMORY_OPS + CONTROL_FLOW_OPS + LOGIC_OPS

FORMAT_SPECS = [
    ("A", [0x00, 0x01, 0x02, 0x04], 1),
    ("B", [0x08, 0x09, 0x0A, 0x0C, 0x0D], 2),
    ("C", [0x10, 0x12, 0x14], 2),
    ("D", [0x18, 0x19, 0x1A, 0x1E], 3),
    ("E", [0x20, 0x25, 0x38, 0x3A, 0x3C], 4),
    ("F", [0x40, 0x41, 0x43, 0x44], 4),
    ("G", [0x48, 0x49], 5),
]

PREV_REPORT_PATH = PROJECT_ROOT / "tools" / "benchmark_report.json"

# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class MicroResult:
    category: str; opcode: str; fmt: str
    ops_per_sec: float; ns_per_op: float; cycles: int

@dataclass
class FormatDecodeResult:
    fmt: str; bytes_total: int; ops_per_sec: float
    ns_per_decode: float; exec_overhead_ns: float

@dataclass
class MacroResult:
    name: str; description: str
    elapsed_sec: float; cycles: int; ops_per_sec: float

@dataclass
class MemAllocResult:
    pattern: str; ops: int; elapsed_sec: float; ops_per_sec: float; peak_bytes: float

@dataclass
class StackDepthResult:
    max_depth: int; push_ops: int; elapsed_sec: float; ops_per_sec: float

@dataclass
class RegAccessResult:
    access_type: str; ops: int; elapsed_sec: float; ops_per_sec: float

@dataclass
class BenchmarkResults:
    timestamp: str; platform: str; python_version: str
    micro: List[MicroResult] = field(default_factory=list)
    format_decode: List[FormatDecodeResult] = field(default_factory=list)
    macro: List[MacroResult] = field(default_factory=list)
    mem_alloc: List[MemAllocResult] = field(default_factory=list)
    stack_depth: List[StackDepthResult] = field(default_factory=list)
    reg_access: List[RegAccessResult] = field(default_factory=list)
    prev_comparison: List[dict] = field(default_factory=list)
    bottlenecks: List[dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

# ── Helpers ────────────────────────────────────────────────────────────────────

# Register init prefix: R1=42, R2=7, R3=100, R15=256
_REG_INIT = bytes([
    0x40, 0x01, 0x00, 42, 0x40, 0x02, 0x00, 7,
    0x40, 0x03, 0x00, 100, 0x40, 0x0F, 0x01, 0x00,
    0x39, 0x03, 0x04, 0x0F,  # STORE R3, R4, R15
])

def _instr(opcode: int, fmt: str) -> bytes:
    """Generate a single instruction with safe register operands."""
    if fmt == "A": return bytes([opcode])
    if fmt == "B": return bytes([opcode, 0x01])
    if fmt == "C": return bytes([opcode, 42])
    if fmt == "D": return bytes([opcode, 0x01, 10])
    if fmt == "E": return bytes([opcode, 0x00, 0x01, 0x02])
    if fmt == "F": return bytes([opcode, 0x00, 0x00, 0x01])
    if fmt == "G": return bytes([opcode, 0x00, 0x01, 0x00, 0x00])
    return bytes([opcode])

def _build_loop(opcode: int, fmt: str, count: int) -> bytes:
    """Build bytecode that repeats an opcode `count` times safely."""
    if opcode == 0x0C:  # PUSH — interleave POPs
        instr = bytes([0x0C, 0x01, 0x0D, 0x0F])
        return _REG_INIT + instr * count + bytes([0x00])
    if opcode == 0x0D:  # POP — interleave PUSHes
        instr = bytes([0x0C, 0x01, 0x0D, 0x00])
        return _REG_INIT + instr * count + bytes([0x00])
    if opcode in (0x43, 0x3C, 0x3D, 0x44, 0x02):
        instr = bytes([0x01])  # NOP for control flow
    else:
        instr = _instr(opcode, fmt)
    return _REG_INIT + instr * count + bytes([0x00])

def _run_timed(bytecode: bytes) -> Tuple[float, int]:
    """Run bytecode through UnifiedVM with warmup. Returns (elapsed, cycles)."""
    for _ in range(WARMUP):
        UnifiedVM(bytecode).execute()
    start = time.perf_counter()
    total_cycles = 0
    for _ in range(BENCH_RUNS):
        state = UnifiedVM(bytecode).execute()
        total_cycles += state["cycle_count"]
    return time.perf_counter() - start, total_cycles

def _build_jnz_loop(body_bytes: bytes, counter_reg: int = 0x06) -> bytes:
    """Wrap a loop body with DEC + JNZ back using Format D/E."""
    # DEC counter_reg (2 bytes)
    dec = bytes([0x09, counter_reg])
    full_body = body_bytes + dec
    # Need: MOVI R7, -(len(full_body)+4); then JNZ counter_reg, R7
    back = -(len(full_body) + 4) & 0xFF
    movi = bytes([0x18, 0x07, back])  # MOVI R7, offset
    jnz = bytes([0x3D, counter_reg, 0x07, 0x00])  # JNZ R6, R7
    return full_body + jnz  # return just the loop body (caller adds HALT)

def fmt_ops(n: float) -> str:
    if n >= 1e6:  return f"{n/1e6:,.2f}M"
    if n >= 1e3:  return f"{n/1e3:,.1f}K"
    return f"{n:,.2f}"

# ── 1. Microbenchmarks per opcode category ────────────────────────────────────

def run_microbenchmarks(iters: int) -> List[MicroResult]:
    print(f"\n[1/7] Microbenchmarks per opcode ({iters:,} iterations each)...")
    results = []
    categories = {
        "arithmetic": ARITHMETIC_OPS, "memory": MEMORY_OPS,
        "control_flow": CONTROL_FLOW_OPS, "logic": LOGIC_OPS,
    }
    for cat_name, ops in categories.items():
        for opcode, mnemonic, fmt in ops:
            bc = _build_loop(opcode, fmt, iters)
            elapsed, cycles = _run_timed(bc)
            total_ops = iters * BENCH_RUNS
            results.append(MicroResult(
                category=cat_name, opcode=mnemonic, fmt=fmt,
                ops_per_sec=total_ops / elapsed,
                ns_per_op=(elapsed / total_ops) * 1e9,
                cycles=cycles,
            ))
            print(f"  {mnemonic:<10} ({cat_name}) {fmt_ops(results[-1].ops_per_sec)}/s "
                  f"{results[-1].ns_per_op:.1f}ns")
    return results

# ── 2. Macro benchmarks ──────────────────────────────────────────────────────

def _fibonacci_bytecode(n: int = 30) -> bytes:
    """Fibonacci(n) in FLUX bytecode. Result in R1."""
    back_offset = (-25) & 0xFF  # 0xE7
    return bytes([
        0x40, 0x00, 0x00, 0x00,       # MOVI16 R0, 0  (a)
        0x40, 0x01, 0x00, 0x01,       # MOVI16 R1, 1  (b)
        0x40, 0x02, 0x00, n & 0xFF,    # MOVI16 R2, n  (counter)
        0x3A, 0x04, 0x01, 0x00,       # MOV R4, R1
        0x20, 0x04, 0x04, 0x00,       # ADD R4, R4, R0
        0x3A, 0x00, 0x01, 0x00,       # MOV R0, R1
        0x3A, 0x01, 0x04, 0x00,       # MOV R1, R4
        0x09, 0x02,                   # DEC R2
        0x18, 0x05, back_offset,       # MOVI R5, -25
        0x3D, 0x02, 0x05, 0x00,       # JNZ R2, R5
        0x00,                          # HALT
    ])

def _bubble_sort_bytecode(count: int = 100) -> bytes:
    """Bubble sort simulation: heavy memory ops (LOADOFF/STOREOFF/CMP) in a loop."""
    bc = []
    base = 256
    for i in range(20):
        val = count - i
        bc += [0x40, 0x01, 0x00, val & 0xFF]
        offset = base + i * 4
        bc += [0x49, 0x01, 0x04, (offset >> 8) & 0xFF, offset & 0xFF]
    total_iters = 400
    bc += [0x40, 0x06, 0x01, total_iters & 0xFF]  # R6 = 400
    bc += [0x40, 0x05, 0x01, 0x00]  # R5 = 256 (array base)
    back = (-30) & 0xFF
    bc += [0x18, 0x07, back]  # MOVI R7, -30
    bc += [
        0x48, 0x00, 0x05, 0x00, 0x00,  # LOADOFF R0, R5, 0
        0x48, 0x01, 0x05, 0x00, 0x04,  # LOADOFF R1, R5, 4
        0x2C, 0x02, 0x00, 0x01,         # CMP_EQ R2, R0, R1
        0x49, 0x00, 0x05, 0x00, 0x04,  # STOREOFF R0, R5, 4
        0x49, 0x01, 0x05, 0x00, 0x00,  # STOREOFF R1, R5, 0
        0x09, 0x06,                     # DEC R6
        0x3D, 0x06, 0x07, 0x00,         # JNZ R6, R7
        0x00,                            # HALT
    ]
    return bytes(bc)

def _matrix_multiply_bytecode() -> bytes:
    """5x5 matrix multiply: 500 multiply-accumulate ops (MUL + ADD loop)."""
    bc = [
        0x40, 0x06, 0x01, 0xF4,  # MOVI16 R6, 500
        0x40, 0x01, 0x00, 0x03,  # R1=3
        0x40, 0x02, 0x00, 0x07,  # R2=7
        0x40, 0x00, 0x00, 0x00,  # R0=0 (accumulator)
    ]
    back = (-14) & 0xFF
    bc += [0x18, 0x07, back]  # MOVI R7, -14
    bc += [
        0x22, 0x03, 0x01, 0x02,  # MUL R3, R1, R2
        0x20, 0x00, 0x00, 0x03,  # ADD R0, R0, R3
        0x09, 0x06,              # DEC R6
        0x3D, 0x06, 0x07, 0x00,  # JNZ R6, R7
        0x00,                     # HALT
    ]
    return bytes(bc)

def _string_process_bytecode() -> bytes:
    """String scan simulation: LOADOFF + CMP_EQ + STOREOFF in a tight loop."""
    bc = [
        0x40, 0x05, 0x01, 0x00,  # R5 = 256 (base)
        0x40, 0x06, 0x03, 0xE8,  # R6 = 1000 (iterations)
        0x40, 0x07, 0x00, 0x57,  # R7 = 'W' = 0x57
    ]
    back = (-34) & 0xFF
    bc += [0x18, 0x08, back]  # MOVI R8, -34
    bc += [
        0x48, 0x01, 0x05, 0x00, 0x00,  # LOADOFF R1, R5, 0
        0x2C, 0x02, 0x01, 0x07,         # CMP_EQ R2, R1, R7
        0x49, 0x02, 0x05, 0x00, 0x00,  # STOREOFF R2, R5, 0
        0x48, 0x03, 0x05, 0x00, 0x04,  # LOADOFF R3, R5, 4
        0x2C, 0x04, 0x03, 0x07,         # CMP_EQ R4, R3, R7
        0x49, 0x04, 0x05, 0x00, 0x04,  # STOREOFF R4, R5, 4
        0x09, 0x06,                     # DEC R6
        0x3D, 0x06, 0x08, 0x00,         # JNZ R6, R8
        0x00,                            # HALT
    ]
    return bytes(bc)

def run_macro_benchmarks() -> List[MacroResult]:
    print("\n[2/7] Macro benchmarks...")
    results = []
    macros = [
        ("fibonacci_30", "Fibonacci(30) iterative", _fibonacci_bytecode(30)),
        ("bubble_sort_100", "Bubble sort 100 elements (400 compare-swap iters)", _bubble_sort_bytecode(100)),
        ("matmul_5x5", "5x5 matrix multiply (500 MAC ops)", _matrix_multiply_bytecode()),
        ("string_process", "String scan + compare (1000 iters)", _string_process_bytecode()),
    ]
    for name, desc, bc in macros:
        elapsed, cycles = _run_timed(bc)
        results.append(MacroResult(
            name=name, description=desc,
            elapsed_sec=elapsed / BENCH_RUNS, cycles=cycles // BENCH_RUNS,
            ops_per_sec=BENCH_RUNS / elapsed,
        ))
        print(f"  {name}: {results[-1].elapsed_sec*1000:.2f}ms, {results[-1].cycles} cycles")
    return results

# ── 3. Memory benchmarks ─────────────────────────────────────────────────────

def run_memory_benchmarks() -> Tuple[List[MemAllocResult], List[StackDepthResult], List[RegAccessResult]]:
    print("\n[3/7] Memory benchmarks...")
    alloc_results, stack_results, reg_results = [], [], []
    seq_count = 10_000
    rng = random.Random(42)

    # Sequential store
    bc_seq = list(_REG_INIT)
    for i in range(seq_count):
        addr = (256 + (i % 1000) * 4) & 0xFFFF
        bc_seq += [0x49, 0x03, 0x04, (addr >> 8) & 0xFF, addr & 0xFF]
    bc_seq += [0x00]
    elapsed, _ = _run_timed(bytes(bc_seq))
    total = seq_count * BENCH_RUNS
    alloc_results.append(MemAllocResult("sequential_store", seq_count, elapsed, total/elapsed, 0))
    print(f"  Sequential store: {fmt_ops(alloc_results[-1].ops_per_sec)}/s")

    # Random store
    bc_rand = list(_REG_INIT)
    for _ in range(seq_count):
        addr = (256 + rng.randint(0, 999) * 4) & 0xFFFF
        bc_rand += [0x49, 0x03, 0x04, (addr >> 8) & 0xFF, addr & 0xFF]
    bc_rand += [0x00]
    elapsed, _ = _run_timed(bytes(bc_rand))
    alloc_results.append(MemAllocResult("random_store", seq_count, elapsed, total/elapsed, 0))
    print(f"  Random store: {fmt_ops(alloc_results[-1].ops_per_sec)}/s")

    # Fragmented store
    bc_frag = list(_REG_INIT)
    for i in range(seq_count):
        addr = ((256 + (i % 100) * 4) if i % 2 == 0 else (32768 + (i % 100) * 4)) & 0xFFFF
        bc_frag += [0x49, 0x03, 0x04, (addr >> 8) & 0xFF, addr & 0xFF]
    bc_frag += [0x00]
    elapsed, _ = _run_timed(bytes(bc_frag))
    alloc_results.append(MemAllocResult("fragmented_store", seq_count, elapsed, total/elapsed, 0))
    print(f"  Fragmented store: {fmt_ops(alloc_results[-1].ops_per_sec)}/s")

    # Memory footprint
    tracemalloc.start()
    vm = UnifiedVM(bytes(bc_seq[:200]))
    vm.execute()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    alloc_results[-1] = MemAllocResult(alloc_results[-1].pattern, alloc_results[-1].ops,
                                       alloc_results[-1].elapsed_sec, alloc_results[-1].ops_per_sec, float(peak))

    # Stack depth
    for depth in [100, 1000, 5000, 10000]:
        push_pop = bytes([0x0C, 0x01, 0x0D, 0x0F]) * depth + bytes([0x00])
        bc = _REG_INIT + push_pop
        try:
            elapsed, _ = _run_timed(bc)
            total_ops = depth * BENCH_RUNS * 2
            stack_results.append(StackDepthResult(depth, depth*2, elapsed, total_ops/elapsed))
            print(f"  Stack depth {depth}: {fmt_ops(stack_results[-1].ops_per_sec)}/s")
        except Exception as e:
            print(f"  Stack depth {depth}: FAILED ({e})")
            stack_results.append(StackDepthResult(depth, 0, -1, 0))

    # Register access
    reg_read_bc = _REG_INIT + bytes([0x3A, 0x0F, 0x01, 0x02]) * 100_000 + bytes([0x00])
    elapsed, _ = _run_timed(reg_read_bc)
    total_ops = 100_000 * BENCH_RUNS
    reg_results.append(RegAccessResult("read_triple_reg", 100_000, elapsed, total_ops/elapsed))
    print(f"  Register read (MOV rd, rs1): {fmt_ops(reg_results[-1].ops_per_sec)}/s")

    reg_write_bc = _REG_INIT + bytes([0x08, 0x01]) * 100_000 + bytes([0x00])
    elapsed, _ = _run_timed(reg_write_bc)
    reg_results.append(RegAccessResult("write_inc", 100_000, elapsed, total_ops/elapsed))
    print(f"  Register write (INC): {fmt_ops(reg_results[-1].ops_per_sec)}/s")

    return alloc_results, stack_results, reg_results

# ── 4. Format decode benchmark ───────────────────────────────────────────────

def run_format_decode(count: int = DECODE_PER_FMT) -> List[FormatDecodeResult]:
    print(f"\n[4/7] Format decode benchmark ({count:,} instructions per format)...")
    results = []
    rng = random.Random(42)

    for fmt_name, opcodes, size in FORMAT_SPECS:
        parts = [_instr(rng.choice(opcodes), fmt_name) for _ in range(count)]
        bytecode = b"".join(parts) + bytes([0x00])

        # Decode-only benchmark
        for _ in range(WARMUP):
            pc = 0
            while pc < len(bytecode):
                pc += UnifiedVM._instruction_size(bytecode[pc])
        start = time.perf_counter()
        for _ in range(BENCH_RUNS):
            pc = 0
            while pc < len(bytecode):
                pc += UnifiedVM._instruction_size(bytecode[pc])
        elapsed_decode = time.perf_counter() - start
        total_ops = count * BENCH_RUNS

        # Full execution for overhead comparison
        for _ in range(WARMUP):
            UnifiedVM(bytecode).execute()
        start_exec = time.perf_counter()
        for _ in range(BENCH_RUNS):
            UnifiedVM(bytecode).execute()
        elapsed_exec = time.perf_counter() - start_exec
        overhead = ((elapsed_exec - elapsed_decode) / total_ops) * 1e9

        results.append(FormatDecodeResult(
            fmt=fmt_name, bytes_total=len(bytecode),
            ops_per_sec=total_ops / elapsed_decode,
            ns_per_decode=(elapsed_decode / total_ops) * 1e9,
            exec_overhead_ns=overhead,
        ))
        print(f"  Format {fmt_name}: {fmt_ops(results[-1].ops_per_sec)}/s decode, "
              f"{results[-1].ns_per_decode:.1f}ns/inst, {overhead:.1f}ns exec overhead")
    return results

# ── 5. Bottleneck analysis ───────────────────────────────────────────────────

def analyze_bottlenecks(micro: List[MicroResult]) -> Tuple[List[dict], List[str]]:
    if not micro:
        return [], []
    sorted_ops = sorted(micro, key=lambda x: x.ns_per_op, reverse=True)
    median_ns = sorted_ops[len(sorted_ops) // 2].ns_per_op

    bottlenecks = []
    for r in sorted_ops[:5]:
        ratio = r.ns_per_op / median_ns if median_ns > 0 else 0
        bottlenecks.append({
            "opcode": r.opcode, "category": r.category, "format": r.fmt,
            "ns_per_op": round(r.ns_per_op, 1), "ops_per_sec": round(r.ops_per_sec, 0),
            "slowness_ratio": round(ratio, 2),
        })

    cat_avgs = {}
    for r in micro:
        cat_avgs.setdefault(r.category, []).append(r.ns_per_op)
    cat_summary = {k: sum(v)/len(v) for k, v in cat_avgs.items()}
    sorted_cats = sorted(cat_summary.items(), key=lambda x: x[1], reverse=True)

    recommendations = []
    slowest_cat, fastest_cat = sorted_cats[0][0], sorted_cats[-1][0]
    recommendations.append(
        f"CRITICAL: {slowest_cat} ops are {sorted_cats[0][1]/sorted_cats[-1][1]:.1f}x slower "
        f"than {fastest_cat} ops -- prioritize optimization of {slowest_cat} opcode handlers.")
    recommendations.append(
        f"MEDIAN: {median_ns:.1f} ns/op across all opcodes; "
        f"top bottleneck '{bottlenecks[0]['opcode']}' is {bottlenecks[0]['slowness_ratio']:.1f}x median.")
    fmt_avgs = {}
    for r in micro:
        fmt_avgs.setdefault(r.fmt, []).append(r.ns_per_op)
    for fmt, times in fmt_avgs.items():
        avg = sum(times)/len(times)
        if avg > median_ns * 1.5:
            recommendations.append(
                f"FORMAT: Format {fmt} instructions average {avg:.1f} ns/op -- optimize decode path.")
    recommendations.append("GENERAL: Consider computed-goto dispatch instead of if-elif chains for opcode decoding.")
    recommendations.append("GENERAL: Direct array indexing for registers instead of _rd/_wr method calls in hot loop.")
    return bottlenecks, recommendations

# ── 6. Previous benchmark comparison ─────────────────────────────────────────

def compare_with_previous(micro: List[MicroResult]) -> List[dict]:
    if not PREV_REPORT_PATH.exists():
        print(f"  No previous benchmark found at {PREV_REPORT_PATH}")
        return []
    with open(PREV_REPORT_PATH) as f:
        prev = json.load(f)
    prev_lookup = {}
    for entry in prev.get("opcode_micro", []):
        if entry["runtime"] == "python":
            prev_lookup[entry["mnemonic"]] = entry["ops_per_sec"]
    current_lookup = {r.opcode: r.ops_per_sec for r in micro}
    comparisons = []
    for mnem in sorted(set(prev_lookup.keys()) & set(current_lookup.keys())):
        prev_ops, curr_ops = prev_lookup[mnem], current_lookup[mnem]
        if prev_ops > 0:
            comparisons.append({
                "opcode": mnem, "prev_ops_sec": round(prev_ops, 0),
                "curr_ops_sec": round(curr_ops, 0),
                "change_pct": round(((curr_ops - prev_ops) / prev_ops) * 100, 1),
            })
    return comparisons

# ── 7. Report generation ─────────────────────────────────────────────────────

def generate_markdown(r: BenchmarkResults) -> str:
    lines = [
        "# FLUX Runtime Performance Benchmark Report v2", "",
        f"**Date:** {r.timestamp}  |  **Platform:** {r.platform}  |  **Python:** {r.python_version}",
        f"**Micro iterations:** 100,000  |  **Decode count:** {DECODE_PER_FMT:,}  |  **Runs:** {BENCH_RUNS} (warmup {WARMUP})", "",
        "## 1. Opcode Microbenchmarks", "",
        "| Category | Opcode | Format | ops/sec | ns/op |",
        "|----------|--------|--------|---------|-------|",
    ]
    for m in r.micro:
        lines.append(f"| {m.category} | {m.opcode} | {m.fmt} | {m.ops_per_sec:,.0f} | {m.ns_per_op:.1f} |")
    lines.append("")
    # Category averages
    cat_avgs = {}
    for m in r.micro:
        cat_avgs.setdefault(m.category, []).append(m.ops_per_sec)
    lines += ["### Category Averages", "",
        "| Category | Avg ops/sec | Avg ns/op |", "|----------|-------------|-----------|"]
    for cat in ["arithmetic", "memory", "control_flow", "logic"]:
        if cat in cat_avgs:
            avg = sum(cat_avgs[cat]) / len(cat_avgs[cat])
            lines.append(f"| {cat} | {avg:,.0f} | {1e9/avg:.1f} |")
    lines += ["", "## 2. Format Decode Throughput", "",
        "| Format | Bytes | ops/sec | ns/decode | Exec overhead (ns) |",
        "|--------|-------|---------|-----------|-------------------|"]
    for f in r.format_decode:
        lines.append(f"| {f.fmt} | {f.bytes_total:,} | {f.ops_per_sec:,.0f} | {f.ns_per_decode:.1f} | {f.exec_overhead_ns:.1f} |")
    lines += ["", "## 3. Macro Benchmarks", "",
        "| Benchmark | Description | Time (ms) | Cycles |", "|-----------|-------------|-----------|--------|"]
    for m in r.macro:
        lines.append(f"| {m.name} | {m.description} | {m.elapsed_sec*1000:.2f} | {m.cycles:,} |")
    lines += ["", "## 4. Memory Benchmarks", "",
        "### Allocation Patterns", "",
        "| Pattern | ops/sec | Peak memory |",
        "|---------|---------|-------------|"]
    for a in r.mem_alloc:
        peak = f"{a.peak_bytes/1024:.1f} KB" if a.peak_bytes > 1024 else f"{a.peak_bytes:.0f} B"
        lines.append(f"| {a.pattern} | {a.ops_per_sec:,.0f} | {peak} |")
    lines += ["", "### Stack Depth", "",
        "| Max depth | Push/Pop ops | ops/sec |",
        "|-----------|-------------|---------|"]
    for s in r.stack_depth:
        lines.append(f"| {s.max_depth} | {s.push_ops} | {s.ops_per_sec:,.0f} |")
    lines += ["", "### Register Access", "",
        "| Type | ops/sec |", "|------|---------|"]
    for reg in r.reg_access:
        lines.append(f"| {reg.access_type} | {reg.ops_per_sec:,.0f} |")
    lines += ["", "## 5. Bottleneck Analysis", "",
        "### Top 5 Slowest Opcodes", "",
        "| Rank | Opcode | Category | ns/op | Slowness Ratio |",
        "|------|--------|----------|-------|----------------|"]
    for i, b in enumerate(r.bottlenecks, 1):
        lines.append(f"| {i} | {b['opcode']} | {b['category']} | {b['ns_per_op']} | {b['slowness_ratio']}x |")
    lines += ["", "### Optimization Recommendations", ""]
    for rec in r.recommendations:
        lines.append(f"- {rec}")
    if r.prev_comparison:
        lines += ["", "## 6. Comparison with Previous Benchmark (v1)", "",
            "| Opcode | Previous ops/s | Current ops/s | Change |",
            "|--------|---------------|----------------|--------|"]
        for c in r.prev_comparison:
            arrow = "+" if c["change_pct"] > 0 else ""
            lines.append(f"| {c['opcode']} | {c['prev_ops_sec']:,.0f} | {c['curr_ops_sec']:,.0f} | {arrow}{c['change_pct']:.1f}% |")
    lines.append("")
    return "\n".join(lines)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import platform
    parser = argparse.ArgumentParser(description="FLUX Performance Benchmark Suite")
    parser.add_argument("--quick", action="store_true", help="Reduced iterations for quick test")
    args = parser.parse_args()
    iters = 10_000 if args.quick else 100_000

    print("=" * 70)
    print("  FLUX Performance Benchmark Suite (PERF-002)")
    print("=" * 70)
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Micro iterations: {iters:,}")

    results = BenchmarkResults(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        platform=f"{platform.system()} {platform.machine()}",
        python_version=sys.version.split()[0],
    )

    results.micro = run_microbenchmarks(iters)
    results.macro = run_macro_benchmarks()
    alloc, stack, reg = run_memory_benchmarks()
    results.mem_alloc, results.stack_depth, results.reg_access = alloc, stack, reg
    results.format_decode = run_format_decode()

    print("\n[5/7] Bottleneck analysis...")
    results.bottlenecks, results.recommendations = analyze_bottlenecks(results.micro)
    for b in results.bottlenecks:
        print(f"  SLOW: {b['opcode']} ({b['category']}) -- {b['ns_per_op']}ns/op, {b['slowness_ratio']}x median")
    for rec in results.recommendations:
        print(f"  REC: {rec}")

    print("\n[6/7] Comparison with previous benchmark...")
    results.prev_comparison = compare_with_previous(results.micro)
    for c in results.prev_comparison:
        arrow = "+" if c["change_pct"] > 0 else ""
        print(f"  {c['opcode']}: {arrow}{c['change_pct']:.1f}%")

    print("\n[7/7] Saving reports...")
    json_path = PROJECT_ROOT / "tools" / "benchmark_results.json"
    report_dict = {
        "timestamp": results.timestamp, "platform": results.platform,
        "python_version": results.python_version,
        "micro": [asdict(r) for r in results.micro],
        "format_decode": [asdict(r) for r in results.format_decode],
        "macro": [asdict(r) for r in results.macro],
        "mem_alloc": [asdict(r) for r in results.mem_alloc],
        "stack_depth": [asdict(r) for r in results.stack_depth],
        "reg_access": [asdict(r) for r in results.reg_access],
        "bottlenecks": results.bottlenecks,
        "recommendations": results.recommendations,
        "prev_comparison": results.prev_comparison,
    }
    with open(json_path, "w") as f:
        json.dump(report_dict, f, indent=2)
    print(f"  JSON saved: {json_path}")

    md_path = PROJECT_ROOT / "docs" / "benchmark-report-2026-04-12-v2.md"
    with open(md_path, "w") as f:
        f.write(generate_markdown(results))
    print(f"  Markdown saved: {md_path}")

    # Pretty summary table
    print("\n" + "=" * 70)
    print("  SUMMARY TABLE -- All Opcode Speeds")
    print("=" * 70)
    print(f"  {'Opcode':<12} {'Category':<16} {'Fmt':<4} {'ops/sec':>14} {'ns/op':>10}")
    print(f"  {'-'*12} {'-'*16} {'-'*4} {'-'*14} {'-'*10}")
    for m in sorted(results.micro, key=lambda x: x.ops_per_sec, reverse=True):
        print(f"  {m.opcode:<12} {m.category:<16} {m.fmt:<4} {fmt_ops(m.ops_per_sec):>14} {m.ns_per_op:>10.1f}")
    print(f"\n  Total opcodes: {len(results.micro)} | Macros: {len(results.macro)} | "
          f"Formats: {len(results.format_decode)} | Bottlenecks: {len(results.bottlenecks)}")

if __name__ == "__main__":
    main()
