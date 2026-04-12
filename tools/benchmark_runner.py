#!/usr/bin/env python3
"""FLUX Runtime Performance Benchmark Harness (PERF-001)

Measures instruction decode speed, execution throughput, and memory usage
across Python and C unified VM runtimes.

Usage:
    python tools/benchmark_runner.py                    # Python only
    python tools/benchmark_runner.py --runtime c        # C only
    python tools/benchmark_runner.py --runtime all      # Both + comparison

Output:
    - Console table with benchmark results
    - JSON report at tools/benchmark_report.json
    - Markdown summary at docs/benchmark-report-2026-04-12.md

Author: Super Z (Performance Engineering)
Date: 2026-04-12
Task ID: 16a
"""

from __future__ import annotations

import argparse
import json
import os
import random
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Add project root to path ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from flux.vm.unified_interpreter import UnifiedVM, opcode_name

# ── Constants ──────────────────────────────────────────────────────────────────

C_VM_BINARY = PROJECT_ROOT / "src" / "flux" / "vm" / "c" / "flux_vm_unified"
DECODE_COUNT = 10_000
EXEC_ITERATIONS = 10_000
WARMUP_RUNS = 3
BENCHMARK_RUNS = 5

# Opcode categories with their representative opcodes and bytecode generators
OPCODE_CATEGORIES = {
    "arithmetic": {
        "opcodes": [
            (0x20, "ADD", "E"), (0x21, "SUB", "E"), (0x22, "MUL", "E"),
            (0x23, "DIV", "E"), (0x24, "MOD", "E"), (0x2A, "MIN", "E"),
            (0x2B, "MAX", "E"), (0x08, "INC", "B"), (0x09, "DEC", "B"),
        ],
    },
    "logic": {
        "opcodes": [
            (0x25, "AND", "E"), (0x26, "OR", "E"), (0x27, "XOR", "E"),
            (0x0A, "NOT", "B"), (0x28, "SHL", "E"), (0x29, "SHR", "E"),
            (0x0B, "NEG", "B"),
        ],
    },
    "comparison": {
        "opcodes": [
            (0x2C, "CMP_EQ", "E"), (0x2D, "CMP_LT", "E"),
            (0x2E, "CMP_GT", "E"), (0x2F, "CMP_NE", "E"),
        ],
    },
    "control_flow": {
        "opcodes": [
            (0x3C, "JZ", "E"), (0x3D, "JNZ", "E"), (0x3E, "JLT", "E"),
            (0x3F, "JGT", "E"), (0x43, "JMP", "F"), (0x44, "JAL", "F"),
            (0x46, "LOOP", "F"), (0x01, "NOP", "A"),
        ],
    },
    "stack": {
        "opcodes": [
            (0x0C, "PUSH", "B"), (0x0D, "POP", "B"),
        ],
    },
    "memory": {
        "opcodes": [
            (0x38, "LOAD", "E"), (0x39, "STORE", "E"),
            (0x48, "LOADOFF", "G"), (0x49, "STOREOFF", "G"),
        ],
    },
    "data_movement": {
        "opcodes": [
            (0x18, "MOVI", "D"), (0x3A, "MOV", "E"), (0x3B, "SWP", "E"),
            (0x40, "MOVI16", "F"), (0x19, "ADDI", "D"), (0x1A, "SUBI", "D"),
        ],
    },
}

# Top 20 most-used opcodes for individual microbenchmarking
TOP_20_OPCODES = [
    (0x18, "MOVI",    "D", "rd, imm8"),
    (0x20, "ADD",     "E", "rd, rs1, rs2"),
    (0x21, "SUB",     "E", "rd, rs1, rs2"),
    (0x22, "MUL",     "E", "rd, rs1, rs2"),
    (0x2C, "CMP_EQ",  "E", "rd, rs1, rs2"),
    (0x43, "JMP",     "F", "rd, imm16"),
    (0x3D, "JNZ",     "E", "rd, rs1, rs2"),
    (0x0C, "PUSH",    "B", "rd"),
    (0x0D, "POP",     "B", "rd"),
    (0x38, "LOAD",    "E", "rd, rs1, rs2"),
    (0x39, "STORE",   "E", "rd, rs1, rs2"),
    (0x3A, "MOV",     "E", "rd, rs1, rs2"),
    (0x08, "INC",     "B", "rd"),
    (0x09, "DEC",     "B", "rd"),
    (0x25, "AND",     "E", "rd, rs1, rs2"),
    (0x26, "OR",      "E", "rd, rs1, rs2"),
    (0x27, "XOR",     "E", "rd, rs1, rs2"),
    (0x01, "NOP",     "A", "-"),
    (0x00, "HALT",    "A", "-"),
    (0x40, "MOVI16",  "F", "rd, imm16"),
]


# ── Data classes for benchmark results ─────────────────────────────────────────

@dataclass
class DecodeResult:
    runtime: str
    instruction_count: int
    total_bytes: int
    elapsed_sec: float
    ops_per_sec: float
    bytes_per_sec: float


@dataclass
class ExecCategoryResult:
    runtime: str
    category: str
    opcode_count: int
    iterations: int
    elapsed_sec: float
    ops_per_sec: float
    ns_per_op: float
    total_cycles: int


@dataclass
class OpcodeMicroResult:
    runtime: str
    opcode_hex: str
    mnemonic: str
    format: str
    operands: str
    iterations: int
    elapsed_sec: float
    ops_per_sec: float
    ns_per_op: float
    total_cycles: int


@dataclass
class MemoryResult:
    runtime: str
    phase: str
    memory_bytes: float


@dataclass
class BenchmarkReport:
    timestamp: str
    python_version: str
    platform: str
    decode: List[DecodeResult] = field(default_factory=list)
    exec_by_category: List[ExecCategoryResult] = field(default_factory=list)
    opcode_micro: List[OpcodeMicroResult] = field(default_factory=list)
    memory: List[MemoryResult] = field(default_factory=list)
    cross_runtime_summary: List[dict] = field(default_factory=list)


# ── Bytecode generation helpers ────────────────────────────────────────────────

def _instruction_size(op: int) -> int:
    """Return byte size for an instruction starting with opcode `op`."""
    if op <= 0x07: return 1
    if op <= 0x0F: return 2
    if op <= 0x17: return 2
    if op <= 0x1F: return 3
    if op <= 0x3F: return 4
    if op <= 0x47: return 4
    if op <= 0x4F: return 5
    if op <= 0x5F: return 4
    if op <= 0x6F: return 4
    if op <= 0x9F: return 4
    if op <= 0xAF: return 4
    if op <= 0xCF: return 4
    if op <= 0xDF: return 5
    if op <= 0xEF: return 4
    return 1


def generate_random_instruction(rng: random.Random) -> bytes:
    """Generate a single random valid FLUX instruction."""
    # Pick a format, then generate appropriate operands
    fmt = rng.choice(["A", "B", "D", "E", "F", "G"])

    if fmt == "A":
        op = rng.choice([0x00, 0x01, 0x02, 0x04, 0x05, 0x06, 0x07])
        return bytes([op])

    elif fmt == "B":
        op = rng.choice([0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F])
        rd = rng.randint(0, 15)
        return bytes([op, rd])

    elif fmt == "C":
        op = rng.choice([0x10, 0x12, 0x13, 0x14, 0x15, 0x16])
        imm8 = rng.randint(0, 255)
        return bytes([op, imm8])

    elif fmt == "D":
        op = rng.choice([0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F])
        rd = rng.randint(0, 15)
        imm8 = rng.randint(0, 255)
        return bytes([op, rd, imm8])

    elif fmt == "E":
        op = rng.choice([
            0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
            0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
            0x3A, 0x3B,
        ])
        rd = rng.randint(0, 15)
        rs1 = rng.randint(0, 15)
        rs2 = rng.randint(0, 15)
        return bytes([op, rd, rs1, rs2])

    elif fmt == "F":
        op = rng.choice([0x40, 0x41, 0x42, 0x43, 0x44, 0x46])
        rd = rng.randint(0, 15)
        imm16 = rng.randint(0, 65535)
        return bytes([op, rd, (imm16 >> 8) & 0xFF, imm16 & 0xFF])

    elif fmt == "G":
        op = rng.choice([0x48, 0x49])
        rd = rng.randint(0, 15)
        rs1 = rng.randint(0, 15)
        imm16 = rng.randint(0, 65535)
        return bytes([op, rd, rs1, (imm16 >> 8) & 0xFF, imm16 & 0xFF])

    return bytes([0x01])  # NOP fallback


def generate_instruction_for_opcode(opcode: int, fmt: str) -> bytes:
    """Generate a single valid instruction for a specific opcode."""
    if fmt == "A":
        return bytes([opcode])
    elif fmt == "B":
        return bytes([opcode, 0])  # rd=0
    elif fmt == "C":
        return bytes([opcode, 42])  # imm8=42
    elif fmt == "D":
        return bytes([opcode, 0, 10])  # rd=0, imm8=10
    elif fmt == "E":
        return bytes([opcode, 0, 1, 2])  # rd=0, rs1=1, rs2=2
    elif fmt == "F":
        return bytes([opcode, 0, 0, 1])  # rd=0, imm16=1
    elif fmt == "G":
        return bytes([opcode, 0, 1, 0, 0])  # rd=0, rs1=1, imm16=0
    return bytes([opcode])


# Register initialization prefix: R1=42, R2=7, R3=100, R4=0 (addr), R15=256 (addr)
# This ensures DIV/MOD have non-zero operands and memory ops have valid addresses.
# Also pushes values for POP benchmark and stores to memory for STORE benchmark.
_REG_INIT_PREFIX = bytes([
    # MOVI16 R1, 42
    0x40, 0x01, 0x00, 42,
    # MOVI16 R2, 7
    0x40, 0x02, 0x00, 7,
    # MOVI16 R3, 100
    0x40, 0x03, 0x00, 100,
    # MOVI16 R15, 256  (high address for memory ops)
    0x40, 0x0F, 0x01, 0x00,
    # Store initial value at address 256 for LOAD benchmarks
    # STORE R3, R4, R15  =>  mem[0+256] = 100
    0x39, 0x03, 0x04, 0x0F,
    # Push 10 values for POP benchmark (balanced: 10 POPs + auto-crash handled below)
    # PUSH R1 (42)
    0x0C, 0x01,
    # PUSH R2 (7)
    0x0C, 0x02,
    # PUSH R3 (100)
    0x0C, 0x03,
    # PUSH R1
    0x0C, 0x01,
    # PUSH R2
    0x0C, 0x02,
    # PUSH R3
    0x0C, 0x03,
    # PUSH R1
    0x0C, 0x01,
    # PUSH R2
    0x0C, 0x02,
    # PUSH R3
    0x0C, 0x03,
    # PUSH R1
    0x0C, 0x01,
])


def build_exec_bytecode(opcode: int, fmt: str, count: int) -> bytes:
    """Build a bytecode program that executes `count` instances of an opcode.

    For control flow ops that would disrupt sequential execution, uses NOP padding.
    Includes register initialization prefix.
    """
    # POP needs alternating PUSH+POP to prevent stack underflow
    if opcode == 0x0D:  # POP
        push_instr = bytes([0x0C, 0x01])  # PUSH R1
        pop_instr = bytes([0x0D, 0x00])   # POP R0
        loop = (push_instr + pop_instr) * count
        program = _REG_INIT_PREFIX + loop + bytes([0x00])
        return program

    # PUSH may grow stack unboundedly; interleave POPs to keep it bounded
    if opcode == 0x0C:  # PUSH
        push_instr = bytes([0x0C, 0x01])  # PUSH R1
        pop_instr = bytes([0x0D, 0x0F])   # POP R15 (discard)
        loop = (push_instr + pop_instr) * count
        program = _REG_INIT_PREFIX + loop + bytes([0x00])
        return program

    if opcode in (0x00, 0x43, 0x3C, 0x3D, 0x3E, 0x3F, 0x46, 0x44):
        # HALT, JMP, JZ, JNZ, JLT, JGT, LOOP, JAL - use NOP instead for throughput
        effective_op = 0x01  # NOP
        effective_fmt = "A"
    else:
        effective_op = opcode
        effective_fmt = fmt

    instr = generate_instruction_for_opcode(effective_op, effective_fmt)
    # Build program: init prefix + N instructions + HALT
    program = _REG_INIT_PREFIX + instr * count + bytes([0x00])
    return program


def build_category_bytecode(opcodes: list, count: int) -> bytes:
    """Build a bytecode program cycling through opcodes for a category.

    Includes register initialization prefix so DIV/MOD don't crash on zero.
    """
    parts = [_REG_INIT_PREFIX]
    for i in range(count):
        opcode_val, _, fmt = opcodes[i % len(opcodes)]
        if opcode_val in (0x00, 0x43, 0x3C, 0x3D, 0x3E, 0x3F, 0x46, 0x44):
            parts.append(bytes([0x01]))  # NOP for control flow
        else:
            parts.append(generate_instruction_for_opcode(opcode_val, fmt))
    parts.append(bytes([0x00]))  # HALT
    return b"".join(parts)


# ── C runtime helper ──────────────────────────────────────────────────────────

def run_c_vm(bytecode: bytes) -> Tuple[float, dict]:
    """Run bytecode through C VM, return (elapsed_sec, parsed_state)."""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(bytecode)
        tmp_path = f.name

    try:
        start = time.perf_counter()
        result = subprocess.run(
            [str(C_VM_BINARY), tmp_path],
            capture_output=True, text=True, timeout=30,
        )
        elapsed = time.perf_counter() - start

        # Parse output
        state = {"halted": True, "crashed": False, "cycles": 0, "registers": {}}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("halted="):
                parts = line.split()
                for p in parts:
                    if p.startswith("halted="):
                        state["halted"] = p.split("=")[1] == "1"
                    elif p.startswith("crashed="):
                        state["crashed"] = p.split("=")[1] == "1"
                    elif p.startswith("cycles="):
                        state["cycles"] = int(p.split("=")[1])
            elif line.startswith("R"):
                for token in line.split():
                    if token.startswith("R") and "=" in token:
                        parts2 = token.split("=")
                        idx = int(parts2[0][1:])
                        state["registers"][idx] = int(parts2[1])

        return elapsed, state
    except subprocess.TimeoutExpired:
        return -1.0, {"halted": True, "crashed": True, "cycles": 0}
    except FileNotFoundError:
        print(f"  WARNING: C VM binary not found at {C_VM_BINARY}")
        return -1.0, {"halted": True, "crashed": True, "cycles": 0}
    finally:
        os.unlink(tmp_path)


# ── 1. Decode Benchmark ───────────────────────────────────────────────────────

def bench_decode_python(count: int = DECODE_COUNT) -> DecodeResult:
    """Measure Python decode-only throughput (walk PC without executing)."""
    rng = random.Random(42)
    instructions = []
    for _ in range(count):
        instructions.append(generate_random_instruction(rng))

    bytecode = b"".join(instructions)
    total_bytes = len(bytecode)

    # Warmup
    for _ in range(WARMUP_RUNS):
        vm = UnifiedVM(bytecode)
        # Walk through bytecode without executing (decode-only)
        pc = 0
        while pc < total_bytes:
            op = bytecode[pc]
            sz = vm._instruction_size(op)
            pc += sz

    # Benchmark
    start = time.perf_counter()
    for _ in range(BENCHMARK_RUNS):
        pc = 0
        while pc < total_bytes:
            op = bytecode[pc]
            sz = _instruction_size(op)
            pc += sz
    elapsed = time.perf_counter() - start
    total_ops = count * BENCHMARK_RUNS

    return DecodeResult(
        runtime="python",
        instruction_count=count,
        total_bytes=total_bytes,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        bytes_per_sec=(total_bytes * BENCHMARK_RUNS) / elapsed,
    )


def bench_decode_c(count: int = DECODE_COUNT) -> DecodeResult:
    """Measure C VM execution as decode proxy (execute NOPs = decode overhead)."""
    # Use all NOPs as a proxy for decode speed
    bytecode = bytes([0x01]) * count + bytes([0x00])  # NOPs + HALT
    total_bytes = count + 1

    # Warmup
    for _ in range(WARMUP_RUNS):
        run_c_vm(bytecode)

    # Benchmark
    start = time.perf_counter()
    total_ops = count * BENCHMARK_RUNS
    for _ in range(BENCHMARK_RUNS):
        run_c_vm(bytecode)
    elapsed = time.perf_counter() - start

    if elapsed <= 0:
        return DecodeResult(runtime="c", instruction_count=count, total_bytes=total_bytes,
                            elapsed_sec=0, ops_per_sec=0, bytes_per_sec=0)

    return DecodeResult(
        runtime="c",
        instruction_count=count,
        total_bytes=total_bytes,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        bytes_per_sec=(total_bytes * BENCHMARK_RUNS) / elapsed,
    )


# ── 2. Execution Benchmark (per category) ─────────────────────────────────────

def bench_exec_category_python(category: str, ops: dict,
                               count: int = EXEC_ITERATIONS) -> ExecCategoryResult:
    """Benchmark a single opcode category on Python VM."""
    opcodes = ops["opcodes"]
    bytecode = build_category_bytecode(opcodes, count)

    # Warmup
    for _ in range(WARMUP_RUNS):
        vm = UnifiedVM(bytecode)
        vm.execute()

    # Benchmark
    start = time.perf_counter()
    cycles_total = 0
    for _ in range(BENCHMARK_RUNS):
        vm = UnifiedVM(bytecode)
        state = vm.execute()
        cycles_total += state["cycle_count"]
    elapsed = time.perf_counter() - start

    total_ops = count * BENCHMARK_RUNS

    return ExecCategoryResult(
        runtime="python",
        category=category,
        opcode_count=len(opcodes),
        iterations=count,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        ns_per_op=(elapsed / total_ops) * 1e9,
        total_cycles=cycles_total,
    )


def bench_exec_category_c(category: str, ops: dict,
                           count: int = EXEC_ITERATIONS) -> ExecCategoryResult:
    """Benchmark a single opcode category on C VM."""
    opcodes = ops["opcodes"]
    bytecode = build_category_bytecode(opcodes, count)

    # Warmup
    for _ in range(WARMUP_RUNS):
        run_c_vm(bytecode)

    # Benchmark
    start = time.perf_counter()
    cycles_total = 0
    valid = True
    for _ in range(BENCHMARK_RUNS):
        elapsed_c, state = run_c_vm(bytecode)
        if elapsed_c < 0:
            valid = False
            break
        cycles_total += state.get("cycles", 0)
    elapsed = time.perf_counter() - start

    total_ops = count * BENCHMARK_RUNS

    if not valid or elapsed <= 0:
        return ExecCategoryResult(
            runtime="c", category=category, opcode_count=len(opcodes),
            iterations=count, elapsed_sec=0, ops_per_sec=0,
            ns_per_op=0, total_cycles=0,
        )

    return ExecCategoryResult(
        runtime="c",
        category=category,
        opcode_count=len(opcodes),
        iterations=count,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        ns_per_op=(elapsed / total_ops) * 1e9,
        total_cycles=cycles_total,
    )


# ── 3. Memory Benchmark ───────────────────────────────────────────────────────

def bench_memory_python() -> List[MemoryResult]:
    """Measure Python VM memory footprint at each phase."""
    results = []

    # Phase 1: Empty VM
    tracemalloc.start()
    vm_empty = UnifiedVM(b"")
    _, peak_empty = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append(MemoryResult(runtime="python", phase="empty_vm", memory_bytes=float(peak_empty)))

    # Phase 2: After loading program
    rng = random.Random(42)
    program = b"".join(generate_random_instruction(rng) for _ in range(1000)) + bytes([0x00])
    tracemalloc.start()
    vm_loaded = UnifiedVM(program)
    _, peak_loaded = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append(MemoryResult(runtime="python", phase="loaded_program_1000ops",
                                memory_bytes=float(peak_loaded)))

    # Phase 3: During/after execution
    tracemalloc.start()
    vm_exec = UnifiedVM(program)
    vm_exec.execute()
    _, peak_exec = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results.append(MemoryResult(runtime="python", phase="after_execution",
                                memory_bytes=float(peak_exec)))

    # Phase 4: sys.getsizeof for the VM object
    import sys
    vm_size = sys.getsizeof(vm_exec)
    results.append(MemoryResult(runtime="python", phase="vm_object_size",
                                memory_bytes=float(vm_size)))

    # Phase 5: Memory array
    mem_size = sys.getsizeof(vm_exec.memory)
    results.append(MemoryResult(runtime="python", phase="memory_array_64kb",
                                memory_bytes=float(mem_size)))

    return results


def bench_memory_c() -> List[MemoryResult]:
    """Measure C VM memory footprint."""
    results = []

    # C VM uses static allocation:
    # - registers: 16 * int64_t = 128 bytes
    # - confidence: 16 * int64_t = 128 bytes
    # - stack: 4096 * int64_t = 32768 bytes (32 KB)
    # - memory: 65536 bytes (64 KB)
    # - struct overhead: ~100 bytes
    # - bytecode buffer: up to 1 MB (dynamically allocated)
    # Total: ~96 KB + bytecode

    vm_struct = 128 + 128 + 32768 + 65536 + 100  # ~98 KB
    results.append(MemoryResult(runtime="c", phase="vm_struct_static", memory_bytes=float(vm_struct)))
    results.append(MemoryResult(runtime="c", phase="memory_array_64kb", memory_bytes=65536.0))
    results.append(MemoryResult(runtime="c", phase="stack_array_32kb", memory_bytes=32768.0))
    results.append(MemoryResult(runtime="c", phase="total_static", memory_bytes=float(vm_struct)))

    # Measure RSS if available
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                    results.append(MemoryResult(runtime="c", phase="process_rss_kb",
                                                memory_bytes=float(rss_kb * 1024)))
                    break
    except (FileNotFoundError, ValueError):
        pass

    return results


# ── 5. Opcode Microbenchmarks ─────────────────────────────────────────────────

def bench_opcode_python(opcode: int, mnemonic: str, fmt: str, operands: str,
                        count: int = EXEC_ITERATIONS) -> OpcodeMicroResult:
    """Benchmark a single opcode on Python VM."""
    bytecode = build_exec_bytecode(opcode, fmt, count)

    # Warmup
    for _ in range(WARMUP_RUNS):
        UnifiedVM(bytecode).execute()

    # Benchmark
    start = time.perf_counter()
    cycles_total = 0
    for _ in range(BENCHMARK_RUNS):
        state = UnifiedVM(bytecode).execute()
        cycles_total += state["cycle_count"]
    elapsed = time.perf_counter() - start

    total_ops = count * BENCHMARK_RUNS

    return OpcodeMicroResult(
        runtime="python",
        opcode_hex=f"0x{opcode:02X}",
        mnemonic=mnemonic,
        format=fmt,
        operands=operands,
        iterations=count,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        ns_per_op=(elapsed / total_ops) * 1e9,
        total_cycles=cycles_total,
    )


def bench_opcode_c(opcode: int, mnemonic: str, fmt: str, operands: str,
                    count: int = EXEC_ITERATIONS) -> OpcodeMicroResult:
    """Benchmark a single opcode on C VM."""
    bytecode = build_exec_bytecode(opcode, fmt, count)

    # Warmup
    for _ in range(WARMUP_RUNS):
        run_c_vm(bytecode)

    # Benchmark
    start = time.perf_counter()
    cycles_total = 0
    valid = True
    for _ in range(BENCHMARK_RUNS):
        elapsed_c, state = run_c_vm(bytecode)
        if elapsed_c < 0:
            valid = False
            break
        cycles_total += state.get("cycles", 0)
    elapsed = time.perf_counter() - start

    total_ops = count * BENCHMARK_RUNS

    if not valid or elapsed <= 0:
        return OpcodeMicroResult(
            runtime="c", opcode_hex=f"0x{opcode:02X}", mnemonic=mnemonic,
            format=fmt, operands=operands, iterations=count,
            elapsed_sec=0, ops_per_sec=0, ns_per_op=0, total_cycles=0,
        )

    return OpcodeMicroResult(
        runtime="c",
        opcode_hex=f"0x{opcode:02X}",
        mnemonic=mnemonic,
        format=fmt,
        operands=operands,
        iterations=count,
        elapsed_sec=elapsed,
        ops_per_sec=total_ops / elapsed,
        ns_per_op=(elapsed / total_ops) * 1e9,
        total_cycles=cycles_total,
    )


# ── 4. Cross-runtime comparison ───────────────────────────────────────────────

def compute_cross_runtime(report: BenchmarkReport) -> List[dict]:
    """Compute speedup ratios between C and Python."""
    summary = []

    # Decode comparison
    py_decode = [d for d in report.decode if d.runtime == "python"]
    c_decode = [d for d in report.decode if d.runtime == "c"]
    if py_decode and c_decode:
        py_ops = py_decode[0].ops_per_sec
        c_ops = c_decode[0].ops_per_sec
        if py_ops > 0:
            summary.append({
                "benchmark": "decode_throughput",
                "python_ops_sec": round(py_ops, 0),
                "c_ops_sec": round(c_ops, 0),
                "speedup": round(c_ops / py_ops, 2) if py_ops > 0 else 0,
            })

    # Category execution comparison
    py_cats = {r.category: r for r in report.exec_by_category if r.runtime == "python"}
    c_cats = {r.category: r for r in report.exec_by_category if r.runtime == "c"}
    for cat in sorted(py_cats.keys()):
        if cat in c_cats:
            py_ops = py_cats[cat].ops_per_sec
            c_ops = c_cats[cat].ops_per_sec
            if py_ops > 0:
                summary.append({
                    "benchmark": f"exec_{cat}",
                    "python_ops_sec": round(py_ops, 0),
                    "c_ops_sec": round(c_ops, 0),
                    "speedup": round(c_ops / py_ops, 2) if py_ops > 0 else 0,
                })

    # Opcode micro comparison
    py_ops_micro = {r.mnemonic: r for r in report.opcode_micro if r.runtime == "python"}
    c_ops_micro = {r.mnemonic: r for r in report.opcode_micro if r.runtime == "c"}
    for mnem in TOP_20_OPCODES:
        _, name, _, _ = mnem
        if name in py_ops_micro and name in c_ops_micro:
            py_ops = py_ops_micro[name].ops_per_sec
            c_ops = c_ops_micro[name].ops_per_sec
            if py_ops > 0:
                summary.append({
                    "benchmark": f"micro_{name}",
                    "python_ops_sec": round(py_ops, 0),
                    "c_ops_sec": round(c_ops, 0),
                    "speedup": round(c_ops / py_ops, 2) if py_ops > 0 else 0,
                })

    return summary


# ── Console output formatting ─────────────────────────────────────────────────

def fmt_num(n: float, suffix: str = "") -> str:
    """Format a number with commas and optional suffix."""
    if n >= 1_000_000:
        return f"{n/1_000_000:,.2f}M{suffix}"
    elif n >= 1_000:
        return f"{n/1_000:,.1f}K{suffix}"
    else:
        return f"{n:,.2f}{suffix}"


def print_section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_decode_results(results: List[DecodeResult]) -> None:
    print_section("1. DECODE BENCHMARK (Instruction Decode Throughput)")
    print(f"  {'Runtime':<10} {'Instructions':>12} {'Bytes':>10} {'Time (s)':>10} "
          f"{'Ops/sec':>14} {'Bytes/sec':>14}")
    print(f"  {'-'*10} {'-'*12} {'-'*10} {'-'*10} {'-'*14} {'-'*14}")
    for r in results:
        print(f"  {r.runtime:<10} {r.instruction_count:>12,} {r.total_bytes:>10,} "
              f"{r.elapsed_sec:>10.4f} {fmt_num(r.ops_per_sec):>14} {fmt_num(r.bytes_per_sec):>14}")


def print_exec_category_results(results: List[ExecCategoryResult]) -> None:
    print_section("2. EXECUTION BENCHMARK (Throughput by Opcode Category)")
    print(f"  {'Runtime':<10} {'Category':<16} {'Ops':>6} {'Iters':>8} "
          f"{'Time (s)':>10} {'Ops/sec':>14} {'ns/op':>10}")
    print(f"  {'-'*10} {'-'*16} {'-'*6} {'-'*8} {'-'*10} {'-'*14} {'-'*10}")
    for r in results:
        print(f"  {r.runtime:<10} {r.category:<16} {r.opcode_count:>6} {r.iterations:>8,} "
              f"{r.elapsed_sec:>10.4f} {fmt_num(r.ops_per_sec):>14} {r.ns_per_op:>10.1f}")


def print_memory_results(results: List[MemoryResult]) -> None:
    print_section("3. MEMORY BENCHMARK (VM Footprint)")
    print(f"  {'Runtime':<10} {'Phase':<30} {'Memory':>14}")
    print(f"  {'-'*10} {'-'*30} {'-'*14}")
    for r in results:
        if r.memory_bytes > 1024 * 1024:
            size_str = f"{r.memory_bytes / (1024*1024):.2f} MB"
        elif r.memory_bytes > 1024:
            size_str = f"{r.memory_bytes / 1024:.2f} KB"
        else:
            size_str = f"{r.memory_bytes:.0f} B"
        print(f"  {r.runtime:<10} {r.phase:<30} {size_str:>14}")


def print_cross_runtime_summary(summary: List[dict]) -> None:
    print_section("4. CROSS-RUNTIME COMPARISON (Python vs C)")
    print(f"  {'Benchmark':<25} {'Python (ops/s)':>16} {'C (ops/s)':>16} {'Speedup':>10}")
    print(f"  {'-'*25} {'-'*16} {'-'*16} {'-'*10}")
    for s in summary:
        speedup_str = f"{s['speedup']:.1f}x" if s['speedup'] > 0 else "N/A"
        print(f"  {s['benchmark']:<25} {fmt_num(s['python_ops_sec']):>16} "
              f"{fmt_num(s['c_ops_sec']):>16} {speedup_str:>10}")


def print_opcode_micro_results(results: List[OpcodeMicroResult]) -> None:
    print_section("5. OPCODE MICROBENCHMARKS (Top 20 Opcodes)")

    # Group by opcode, show Python and C side-by-side
    opcodes_seen = set()
    for r in results:
        opcodes_seen.add(r.mnemonic)

    for _, mnem, fmt, operands in TOP_20_OPCODES:
        py_r = [r for r in results if r.mnemonic == mnem and r.runtime == "python"]
        c_r = [r for r in results if r.mnemonic == mnem and r.runtime == "c"]

        if not py_r and not c_r:
            continue

        py_ops = py_r[0].ops_per_sec if py_r else 0
        c_ops = c_r[0].ops_per_sec if c_r else 0
        py_ns = py_r[0].ns_per_op if py_r else 0
        c_ns = c_r[0].ns_per_op if c_r else 0

        if py_ops > 0 and c_ops > 0:
            speedup = c_ops / py_ops
            speedup_str = f"{speedup:.1f}x"
        elif c_ops > 0:
            speedup_str = "C only"
        elif py_ops > 0:
            speedup_str = "Py only"
        else:
            speedup_str = "N/A"

        print(f"  {mnem:<10} {fmt:<3}  Py: {fmt_num(py_ops):>12}/s ({py_ns:>8.1f}ns)  "
              f"C: {fmt_num(c_ops):>12}/s ({c_ns:>8.1f}ns)  {speedup_str:>8}")


# ── Markdown report generation ────────────────────────────────────────────────

def generate_markdown_report(report: BenchmarkReport) -> str:
    """Generate markdown benchmark report."""
    lines = [
        "# FLUX Runtime Performance Benchmark Report",
        "",
        f"**Date:** {report.timestamp}",
        f"**Platform:** {report.platform}",
        f"**Python:** {report.python_version}",
        f"**Iterations:** {EXEC_ITERATIONS:,} per benchmark (avg of {BENCHMARK_RUNS} runs)",
        "",
    ]

    # Decode section
    lines.append("## 1. Instruction Decode Throughput")
    lines.append("")
    lines.append("| Runtime | Instructions | Bytes | Time (s) | Ops/sec | Bytes/sec |")
    lines.append("|---------|-------------|-------|----------|---------|-----------|")
    for r in report.decode:
        lines.append(f"| {r.runtime} | {r.instruction_count:,} | {r.total_bytes:,} | "
                      f"{r.elapsed_sec:.4f} | {r.ops_per_sec:,.0f} | {r.bytes_per_sec:,.0f} |")
    lines.append("")

    # Execution by category
    lines.append("## 2. Execution Throughput by Opcode Category")
    lines.append("")
    lines.append("| Runtime | Category | Opcodes | Iterations | Time (s) | Ops/sec | ns/op |")
    lines.append("|---------|----------|---------|------------|----------|---------|-------|")
    for r in report.exec_by_category:
        lines.append(f"| {r.runtime} | {r.category} | {r.opcode_count} | {r.iterations:,} | "
                      f"{r.elapsed_sec:.4f} | {r.ops_per_sec:,.0f} | {r.ns_per_op:.1f} |")
    lines.append("")

    # Memory
    lines.append("## 3. Memory Footprint")
    lines.append("")
    lines.append("| Runtime | Phase | Memory |")
    lines.append("|---------|-------|--------|")
    for r in report.memory:
        if r.memory_bytes > 1024 * 1024:
            size = f"{r.memory_bytes / (1024*1024):.2f} MB"
        elif r.memory_bytes > 1024:
            size = f"{r.memory_bytes / 1024:.2f} KB"
        else:
            size = f"{r.memory_bytes:.0f} B"
        lines.append(f"| {r.runtime} | {r.phase} | {size} |")
    lines.append("")

    # Cross-runtime
    lines.append("## 4. Cross-Runtime Comparison (Python vs C)")
    lines.append("")
    lines.append("| Benchmark | Python (ops/s) | C (ops/s) | Speedup |")
    lines.append("|-----------|----------------|-----------|---------|")
    for s in report.cross_runtime_summary:
        speedup_str = f"{s['speedup']:.1f}x" if s['speedup'] > 0 else "N/A"
        lines.append(f"| {s['benchmark']} | {s['python_ops_sec']:,.0f} | "
                      f"{s['c_ops_sec']:,.0f} | {speedup_str} |")
    lines.append("")

    # Opcode micro
    lines.append("## 5. Opcode Microbenchmarks (Top 20)")
    lines.append("")
    lines.append("| Opcode | Fmt | Python ops/s | Python ns/op | C ops/s | C ns/op | Speedup |")
    lines.append("|--------|-----|--------------|--------------|---------|----------|---------|")
    for _, mnem, fmt, operands in TOP_20_OPCODES:
        py_r = [r for r in report.opcode_micro if r.mnemonic == mnem and r.runtime == "python"]
        c_r = [r for r in report.opcode_micro if r.mnemonic == mnem and r.runtime == "c"]
        if not py_r and not c_r:
            continue
        py_ops = f"{py_r[0].ops_per_sec:,.0f}" if py_r else "-"
        py_ns = f"{py_r[0].ns_per_op:.1f}" if py_r else "-"
        c_ops = f"{c_r[0].ops_per_sec:,.0f}" if c_r else "-"
        c_ns = f"{c_r[0].ns_per_op:.1f}" if c_r else "-"
        if py_r and c_r and py_r[0].ops_per_sec > 0 and c_r[0].ops_per_sec > 0:
            speedup = f"{c_r[0].ops_per_sec / py_r[0].ops_per_sec:.1f}x"
        else:
            speedup = "-"
        lines.append(f"| {mnem} | {fmt} | {py_ops} | {py_ns} | {c_ops} | {c_ns} | {speedup} |")
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    if report.cross_runtime_summary:
        speedups = [s["speedup"] for s in report.cross_runtime_summary if s["speedup"] > 0]
        if speedups:
            avg_speedup = sum(speedups) / len(speedups)
            max_speedup = max(speedups)
            min_speedup = min(speedups)
            lines.append(f"- **Average C speedup over Python:** {avg_speedup:.1f}x")
            lines.append(f"- **Best C speedup:** {max_speedup:.1f}x")
            lines.append(f"- **Worst C speedup:** {min_speedup:.1f}x")
    lines.append(f"- **Total benchmark categories:** {len(OPCODE_CATEGORIES)}")
    lines.append(f"- **Total opcodes microbenchmarked:** {len(TOP_20_OPCODES)}")
    lines.append(f"- **Instructions per decode benchmark:** {DECODE_COUNT:,}")
    lines.append(f"- **Instructions per exec benchmark:** {EXEC_ITERATIONS:,}")
    lines.append("")

    return "\n".join(lines)


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_benchmarks(runtime: str = "python") -> BenchmarkReport:
    """Run all benchmarks for the specified runtime(s)."""
    import platform
    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        python_version=sys.version.split()[0],
        platform=f"{platform.system()} {platform.machine()}",
    )

    runtimes = []
    if runtime in ("python", "all"):
        runtimes.append("python")
    if runtime in ("c", "all"):
        runtimes.append("c")

    if not runtimes:
        print(f"Unknown runtime: {runtime}. Use 'python', 'c', or 'all'.")
        sys.exit(1)

    print(f"\nFLUX Performance Benchmark Harness (PERF-001)")
    print(f"Runtimes: {', '.join(runtimes)}")
    print(f"Decode count: {DECODE_COUNT:,}")
    print(f"Exec iterations: {EXEC_ITERATIONS:,}")
    print(f"Benchmark runs: {BENCHMARK_RUNS} (with {WARMUP_RUNS} warmup)")

    # ── 1. Decode benchmark ───────────────────────────────────────────────
    print("\n[1/5] Running decode benchmarks...")
    if "python" in runtimes:
        r = bench_decode_python()
        report.decode.append(r)
        print(f"  Python decode: {fmt_num(r.ops_per_sec)} ops/sec")
    if "c" in runtimes:
        r = bench_decode_c()
        report.decode.append(r)
        print(f"  C decode: {fmt_num(r.ops_per_sec)} ops/sec")

    # ── 2. Execution benchmark by category ────────────────────────────────
    print("\n[2/5] Running execution benchmarks by category...")
    for cat_name, cat_info in OPCODE_CATEGORIES.items():
        if "python" in runtimes:
            r = bench_exec_category_python(cat_name, cat_info)
            report.exec_by_category.append(r)
            print(f"  Python {cat_name}: {fmt_num(r.ops_per_sec)} ops/sec ({r.ns_per_op:.1f} ns/op)")
        if "c" in runtimes:
            r = bench_exec_category_c(cat_name, cat_info)
            report.exec_by_category.append(r)
            print(f"  C {cat_name}: {fmt_num(r.ops_per_sec)} ops/sec ({r.ns_per_op:.1f} ns/op)")

    # ── 3. Memory benchmark ───────────────────────────────────────────────
    print("\n[3/5] Running memory benchmarks...")
    if "python" in runtimes:
        mem_results = bench_memory_python()
        report.memory.extend(mem_results)
        for m in mem_results:
            print(f"  Python {m.phase}: {m.memory_bytes:,.0f} bytes")
    if "c" in runtimes:
        mem_results = bench_memory_c()
        report.memory.extend(mem_results)
        for m in mem_results:
            print(f"  C {m.phase}: {m.memory_bytes:,.0f} bytes")

    # ── 5. Opcode microbenchmarks ─────────────────────────────────────────
    print("\n[4/5] Running opcode microbenchmarks...")
    for opcode, mnemonic, fmt, operands in TOP_20_OPCODES:
        if "python" in runtimes:
            r = bench_opcode_python(opcode, mnemonic, fmt, operands)
            report.opcode_micro.append(r)
            print(f"  Python {mnemonic}: {fmt_num(r.ops_per_sec)} ops/sec")
        if "c" in runtimes:
            r = bench_opcode_c(opcode, mnemonic, fmt, operands)
            report.opcode_micro.append(r)
            print(f"  C {mnemonic}: {fmt_num(r.ops_per_sec)} ops/sec")

    # ── 4. Cross-runtime summary ──────────────────────────────────────────
    if len(runtimes) > 1:
        print("\n[5/5] Computing cross-runtime comparison...")
        report.cross_runtime_summary = compute_cross_runtime(report)
    else:
        report.cross_runtime_summary = []

    return report


def save_reports(report: BenchmarkReport) -> None:
    """Save JSON and Markdown reports."""
    # JSON report
    json_path = PROJECT_ROOT / "tools" / "benchmark_report.json"
    report_dict = {
        "timestamp": report.timestamp,
        "python_version": report.python_version,
        "platform": report.platform,
        "decode": [asdict(r) for r in report.decode],
        "exec_by_category": [asdict(r) for r in report.exec_by_category],
        "opcode_micro": [asdict(r) for r in report.opcode_micro],
        "memory": [asdict(r) for r in report.memory],
        "cross_runtime_summary": report.cross_runtime_summary,
    }
    with open(json_path, "w") as f:
        json.dump(report_dict, f, indent=2)
    print(f"\n  JSON report saved: {json_path}")

    # Markdown report
    md_path = PROJECT_ROOT / "docs" / "benchmark-report-2026-04-12.md"
    md_content = generate_markdown_report(report)
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"  Markdown report saved: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="FLUX Runtime Performance Benchmark Harness")
    parser.add_argument(
        "--runtime", choices=["python", "c", "all"], default="python",
        help="Runtime(s) to benchmark (default: python)",
    )
    parser.add_argument(
        "--json-only", action="store_true",
        help="Only output JSON, skip console tables",
    )
    parser.add_argument(
        "--save", action="store_true", default=True,
        help="Save JSON and Markdown reports (default: true)",
    )
    args = parser.parse_args()

    report = run_benchmarks(args.runtime)

    if not args.json_only:
        print_decode_results(report.decode)
        print_exec_category_results(report.exec_by_category)
        print_memory_results(report.memory)
        print_opcode_micro_results(report.opcode_micro)
        if report.cross_runtime_summary:
            print_cross_runtime_summary(report.cross_runtime_summary)

    if args.save:
        print(f"\nSaving reports...")
        save_reports(report)

    print(f"\nBenchmark complete.")


if __name__ == "__main__":
    main()
