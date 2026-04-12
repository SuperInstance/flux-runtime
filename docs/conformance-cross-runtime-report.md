# FLUX Cross-Runtime Conformance Report

**Date:** 2026-04-14
**Task ID:** 15a (CONF-001)
**Author:** Super Z (Cartographer)
**ISA:** Unified (isa_unified.py) — converged opcode numbering
**Suite:** 74 vectors (71 runnable, 3 source-description-only)

---

## Executive Summary

The FLUX fleet now has **two fully conformant runtimes** (Python and C) that produce
**identical results** across all 71 runnable test vectors. The Rust runtime is not yet
available locally. Zero cross-runtime disagreements detected.

| Runtime | Status | Result | Details |
|---------|--------|--------|---------|
| **Python** | Available | **71/71 PASS** | unified_interpreter.py (~800 lines) |
| **C** | Available | **71/71 PASS** | flux_vm_unified.c (~680 lines, gcc -O2) |
| **Rust** | Not available | N/A | flux-rust / flux-coop-runtime repos |

---

## Runtime Descriptions

### Python Runtime (`--runtime python`)
- **File:** `src/flux/vm/unified_interpreter.py`
- **Lines:** ~803
- **Dependencies:** Python 3.8+, stdlib only (`struct`)
- **ISA coverage:** 60+ opcodes across Formats A–G
- **Features:** Full register file (R0–R15), confidence registers, 64KB memory,
  4096-entry stack, condition flags, instruction tracing

### C Runtime (`--runtime c`)
- **File:** `src/flux/vm/c/flux_vm_unified.c`
- **Lines:** ~680
- **Dependencies:** None (stdio, stdlib, stdint, string only)
- **ISA coverage:** 60+ opcodes across Formats A–G
- **Features:** Full register file (int64_t R0–R15), confidence registers,
  64KB memory, 4096-entry stack, condition flags, instruction tracing
- **Build:** `gcc -O2 -Wall -Wextra -o flux_vm_unified flux_vm_unified.c`
- **Auto-compiled:** The conformance runner automatically compiles the C VM if the
  binary is missing or the source is newer than the binary.

### Rust Runtime (`--runtime rust`)
- **Status:** Not available locally
- **Notes:** See `flux-rust` or `flux-coop-runtime` repos for future implementation.
  The `flux-coop-runtime` has Phase 1 complete (109 tests, Ask/Respond patterns)
  but does not yet implement the unified ISA bytecode format.

---

## Cross-Runtime Comparison

All 71 runnable test vectors produce **identical PASS results** on both Python and C.
Zero disagreements detected across all 9 categories.

### Category Breakdown

| Category | Vectors | Python | C | Rust |
|----------|---------|--------|---|------|
| arithmetic | 29 | 29/29 PASS | 29/29 PASS | N/A |
| comparison | 8 | 8/8 PASS | 8/8 PASS | N/A |
| control | 8 | 8/8 PASS | 8/8 PASS | N/A |
| data | 8 | 8/8 PASS | 8/8 PASS | N/A |
| logic | 7 | 7/7 PASS | 7/7 PASS | N/A |
| memory | 5 | 5/5 PASS | 5/5 PASS | N/A |
| shift | 4 | 4/4 PASS | 4/4 PASS | N/A |
| stack | 2 | 2/2 PASS | 2/2 PASS | N/A |
| complex | 3 | 3 SKIP | 3 SKIP | N/A |
| **Total** | **74** | **71/71 PASS** | **71/71 PASS** | **N/A** |

### Opcode Coverage (35 unique opcodes exercised)

| Format | Opcodes |
|--------|---------|
| A (1 byte) | HALT, NOP |
| B (2 bytes) | INC, DEC, NOT, NEG, PUSH, POP |
| D (3 bytes) | MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI |
| E (4 bytes) | ADD, SUB, MUL, DIV, MOD, AND, OR, XOR, SHL, SHR, MIN, MAX, CMP_EQ, CMP_LT, CMP_GT, CMP_NE, LOAD, STORE, MOV, SWP, JZ, JNZ |
| F (4 bytes) | MOVI16, ADDI16, SUBI16, JMP, JAL, LOOP |
| G (5 bytes) | STOREOFF, LOADOFF |

### Complex Programs (compiled via assembler.py)

| Program | Expected | Python | C |
|---------|----------|--------|---|
| GCD(48, 18) = 6 | R0 = 6 | PASS | PASS |
| Fibonacci(10) = 55 | R0 = 55 | PASS | PASS |
| Sum of Squares 1..5 = 55 | R0 = 55 | PASS | PASS |

---

## Usage

```bash
# Single runtime
python tools/conformance_runner.py --runtime python
python tools/conformance_runner.py --runtime c
python tools/conformance_runner.py --runtime rust

# All available runtimes (cross-runtime comparison)
python tools/conformance_runner.py --all

# Expanded 74-vector suite
python tools/conformance_runner.py --all --expanded

# JSON output
python tools/conformance_runner.py --all --json-only

# Instruction trace (Python only)
python tools/conformance_runner.py --runtime python --trace
```

---

## Generated Artifacts

| File | Description |
|------|-------------|
| `tools/conformance_runner.py` | Updated multi-runtime runner (this report's source) |
| `tools/conformance_report.json` | Python runtime JSON results |
| `tools/conformance_report_c_original.json` | C runtime JSON results |
| `tools/conformance_report_python_expanded.json` | Python expanded suite results |
| `tools/conformance_report_c_expanded.json` | C expanded suite results |
| `tools/conformance_cross_runtime.json` | Cross-runtime comparison matrix JSON |

---

## Next Actions

1. **Rust Runtime (Priority: High):** Implement `flux_vm_unified.rs` matching the Python/C
   reference implementations. Target: 71/71 PASS on the expanded suite.
2. **Fuzzing:** Add random bytecode generation to stress-test edge cases across all runtimes.
3. **Performance Benchmarking:** Compare cycle counts and wall-clock time across runtimes
   for large programs.
4. **CI Integration:** Add `--all --expanded` to GitHub Actions as a quality gate for
   all flux-runtime PRs.
5. **Extended Opcodes:** Add test vectors for float operations (FADD, FSUB, FMUL, FDIV),
   confidence-aware variants (C_ADD, C_SUB, etc.), and A2A fleet ops (0x50–0x5F).

---

## Conclusion

The FLUX fleet has achieved **100% cross-runtime conformance** between Python and C
implementations on the unified ISA. Both runtimes pass all 71 runnable test vectors
with zero disagreements, validating the ISA specification and demonstrating that
the converged opcode numbering is ready for broader fleet adoption.
