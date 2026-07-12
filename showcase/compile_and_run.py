#!/usr/bin/env python3
"""
FLUX Cross-Implementation Showcase
===================================

Compiles cross_impl.flx to bytecode, runs it on the Python VM,
and outputs a deterministic result hash for cross-implementation comparison.

Usage:
    python3 showcase/compile_and_run.py [--print-bytecode] [--print-regs]

Expected output on all three VMs (Python, Rust, JS):
    R0=13 R1=100 R2=15 R3=5 R4=5040 R5=42 R6=42 R7=14
    Result hash: <md5 of register state>
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

# Ensure flux source is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from flux.asm.cross_assembler import CrossAssembler
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op


# ── Expected results from cross_impl.flx ────────────────────────────────────

EXPECTED_REGS = {
    0: 13,     # arithmetic result
    1: 100,    # signature
    2: 15,     # stack push/pop
    3: 5,      # signature
    4: 5040,   # factorial(7)
    5: 42,     # CMP operand
    6: 42,     # CMP operand
    7: 14,     # MOV test
}

# ── Jump fixup ──────────────────────────────────────────────────────────────

def fix_jump_offsets(bytecode: bytes, symbol_table: dict) -> bytes:
    """Fix Format D jump offsets to be relative (not absolute).

    The cross-assembler emits absolute label addresses in the offset field
    of Format D jump instructions. The VM spec says:
        target_pc = pc_after_instruction + offset
    So we convert: offset = absolute_label - pc_after_instruction.

    MOVI (also Format D) stores an immediate value, NOT an offset, so it is excluded.
    """
    # Jump opcodes that use Format D with relative offsets
    JUMP_OPS = set()
    for name in ('JMP', 'JZ', 'JNZ', 'CALL', 'JG', 'JL', 'JGE', 'JLE'):
        if hasattr(Op, name):
            JUMP_OPS.add(getattr(Op, name))

    # MOVI is Format D but uses immediate, not offset
    MOVI_OP = Op.MOVI

    # Build a set of all known opcodes with their sizes for correct scanning
    FORMAT_A = set()
    for name in ('NOP', 'HALT', 'YIELD', 'DUP', 'SWAP'):
        if hasattr(Op, name):
            FORMAT_A.add(getattr(Op, name))

    FORMAT_B = set()
    for name in ('INC', 'DEC', 'PUSH', 'POP', 'INEG', 'INOT', 'FNEG'):
        if hasattr(Op, name):
            FORMAT_B.add(getattr(Op, name))

    FORMAT_C = set()
    for name in ('MOV', 'LOAD', 'STORE', 'CMP', 'RET'):
        if hasattr(Op, name):
            FORMAT_C.add(getattr(Op, name))

    FORMAT_E = set()
    for name in ('IADD', 'ISUB', 'IMUL', 'IDIV', 'IMOD',
                 'IAND', 'IOR', 'IXOR', 'ISHL', 'ISHR',
                 'FADD', 'FSUB', 'FMUL', 'FDIV'):
        if hasattr(Op, name):
            FORMAT_E.add(getattr(Op, name))

    ba = bytearray(bytecode)
    pc = 0

    while pc < len(ba):
        opcode = ba[pc]

        if opcode in FORMAT_A:
            pc += 1
        elif opcode in FORMAT_B:
            pc += 2
        elif opcode in FORMAT_C:
            pc += 3
        elif opcode == MOVI_OP:
            pc += 4  # Format D immediate — skip
        elif opcode in JUMP_OPS:
            # Format D: [opcode][reg][off_lo][off_hi]
            if pc + 4 <= len(ba):
                off_lo = ba[pc + 2]
                off_hi = ba[pc + 3]
                # Read as unsigned to check if it's an absolute address
                abs_addr = off_lo | (off_hi << 8)
                pc_after = pc + 4
                # Convert absolute label address to relative offset
                rel_offset = abs_addr - pc_after
                # Pack as signed i16 LE
                packed = struct.pack('<h', rel_offset)
                ba[pc + 2] = packed[0]
                ba[pc + 3] = packed[1]
            pc += 4
        elif opcode in FORMAT_E:
            pc += 4
        elif opcode == 0x2E or opcode == 0x2F:
            # JE/JNE use Format B₂ (3 bytes: opcode + 16-bit absolute addr)
            pc += 3
        else:
            pc += 1  # Unknown — skip 1 byte

    return bytes(ba)


# ── Register hash ───────────────────────────────────────────────────────────

def compute_result_hash(regs: dict[int, int]) -> str:
    """Compute MD5 hash of register state for cross-implementation comparison."""
    # Pack registers as deterministic bytes: R0-R15 as i32 LE
    buf = b""
    for i in range(16):
        val = regs.get(i, 0)
        buf += struct.pack("<i", val)
    return hashlib.md5(buf).hexdigest()


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="FLUX Cross-Impl Showcase")
    parser.add_argument("--print-bytecode", action="store_true",
                        help="Print compiled bytecode hex")
    parser.add_argument("--print-regs", action="store_true",
                        help="Print all registers after execution")
    parser.add_argument("--flx-file", default=None,
                        help="Path to .flx file (default: tests/cross_impl.flx)")
    args = parser.parse_args()

    # Locate the .flx file
    flx_path = args.flx_file
    if flx_path is None:
        candidates = [
            PROJECT_ROOT / "tests" / "cross_impl.flx",
            PROJECT_ROOT / "examples" / "deadband.flx",
        ]
        for c in candidates:
            if c.exists():
                flx_path = str(c)
                break
        if flx_path is None:
            print("ERROR: No .flx file found", file=sys.stderr)
            return 1

    print(f"=== FLUX Cross-Implementation Showcase ===")
    print(f"Source: {flx_path}")
    print()

    # Step 1: Assemble
    asm = CrossAssembler()
    result = asm.assemble_file(flx_path)

    if result.errors:
        print("Assembly errors:")
        for err in result.errors:
            print(f"  {err}")
        return 1

    bytecode = result.bytecode
    print(f"Bytecode: {len(bytecode)} bytes")

    if args.print_bytecode:
        print(f"Hex: {bytecode.hex()}")
    print()

    # Step 2: Fix jump offsets (workaround for assembler quirk)
    bytecode = fix_jump_offsets(bytecode, result.symbol_table)

    # Step 3: Run on Python VM
    vm = Interpreter(bytecode)
    try:
        vm.execute()
    except Exception as e:
        print(f"VM error: {e}")

    # Step 4: Collect register state
    regs = {}
    for i in range(16):
        regs[i] = vm.regs.read_gp(i)

    # Step 5: Output results
    if args.print_regs:
        print("Register state (all 16):")
        for i in range(16):
            print(f"  R{i:2d} = {regs[i]}")
    else:
        print("Register state (signature):")
        for i in range(8):
            print(f"  R{i} = {regs[i]}")

    # Step 6: Compute result hash
    result_hash = compute_result_hash(regs)
    print(f"\nResult hash: {result_hash}")

    # Step 7: Compare with expected (if cross_impl.flx)
    if "cross_impl" in flx_path:
        print("\nExpected (from spec):")
        for i, val in EXPECTED_REGS.items():
            marker = "✓" if regs[i] == val else "✗"
            print(f"  {marker} R{i} = {regs[i]} (expected {val})")

        all_match = all(regs[i] == v for i, v in EXPECTED_REGS.items())
        if all_match:
            print("\n✅ All registers match expected values!")
        else:
            print("\n⚠  Some registers differ (may indicate VM or assembler differences)")

    print(f"\n--- Cross-impl comparison ---")
    print(f"Python VM: {result_hash}")
    print(f"Rust VM:   (run showcase/run_all.sh to compare)")
    print(f"JS VM:     (run showcase/run_all.sh to compare)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
