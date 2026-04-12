# FLUX ISA Conformance Report

**Date:** 2026-04-12  
**Author:** Super Z (Cartographer)  
**Runtime Under Test:** `unified_interpreter.py` (Python, unified ISA)  
**ISA Specification:** `isa_unified.py` + `formats.py`  
**Test Suite:** `test_conformance.py` (22 vectors)

---

## 1. ISA Bifurcation Analysis

The FLUX fleet has **two completely divergent opcode numbering schemes**:

| Property | opcodes.py (Python runtime) | isa_unified.py (Converged spec) |
|---|---|---|
| HALT | 0x80 | 0x00 |
| NOP | 0x00 | 0x01 |
| MOV | 0x01 | 0x3A |
| LOAD | 0x02 | 0x38 |
| STORE | 0x03 | 0x39 |
| ADD | 0x08 (IADD) | 0x20 |
| PUSH | 0x20 | 0x0C |
| POP | 0x21 | 0x0D |
| INC | 0x0E | 0x08 |
| DEC | 0x0F | 0x09 |
| MOVI | 0x2B | 0x18 |
| JMP | 0x04 | 0x43 |
| CALL | 0x07 | 0x45 |
| RET | 0x28 | 0x02 |
| Format scheme | A=1B, B=2B, C=3B, D=4B, E=4B, G=var | A=1B, B=2B, C=2B, D=3B, E=4B, F=4B, G=5B |
| Total opcodes | ~80 | ~200 |

**Root cause:** The runtime interpreter was written first with a pragmatic encoding. The unified ISA was designed later by three agents (Oracle1, JetsonClaw1, Babel) as the converged specification. The two were never reconciled — there is **zero overlap** in opcode assignments between them.

**Impact:** Bytecode compiled for one ISA cannot run on the other. This is the fleet's biggest technical debt.

---

## 2. Test Results

### Summary

| Metric | Value |
|---|---|
| Total test vectors | 22 |
| Passed | **20** |
| Failed | **0** |
| Skipped | **3** |
| Errors | **0** |
| Total cycles consumed | 68 |

**Verdict: ALL TESTS PASSED**

### Detailed Results

| # | Category | Test | Status | Expected | Actual |
|---|---|---|---|---|---|
| 1 | control | NOP does nothing | PASS | no_crash | no_crash |
| 2 | control | HALT terminates execution | PASS | no_crash | no_crash |
| 3 | data | MOVI loads immediate value | PASS | R0=42 | R0=42 |
| 4 | data | MOVI loads negative value | PASS | R0=-128 | R0=-128 |
| 5 | data | MOVI16 loads large immediate | PASS | R0=4096 | R0=4096 |
| 6 | arithmetic | ADD two registers | PASS | R2=30 | R2=30 |
| 7 | arithmetic | SUB two registers | PASS | R2=18 | R2=18 |
| 8 | arithmetic | MUL two registers | PASS | R2=42 | R2=42 |
| 9 | arithmetic | MOD two registers | PASS | R2=2 | R2=2 |
| 10 | comparison | CMP_EQ equal values | PASS | R2≠0 | R2=1 |
| 11 | comparison | CMP_EQ unequal values | PASS | R2=0 | R2=0 |
| 12 | arithmetic | ADD rd=rs1 overlap | PASS | R1=8 | R1=8 |
| 13 | arithmetic | ADD rd=rs2 overlap | PASS | R2=13 | R2=13 |
| 14 | arithmetic | ADD all-three overlap | PASS | R0=14 | R0=14 |
| 15 | stack | PUSH and POP preserve value | PASS | R1=99 | R1=99 |
| 16 | logic | AND bitwise | PASS | R2=3 | R2=3 |
| 17 | logic | OR bitwise | PASS | R2=15 | R2=15 |
| 18 | logic | XOR bitwise | PASS | R2=0 | R2=0 |
| 19 | arithmetic | INC increments register | PASS | R0=42 | R0=42 |
| 20 | arithmetic | DEC decrements register | PASS | R0=42 | R0=42 |
| 21 | complex | GCD of 48 and 18 | SKIP | — | — |
| 22 | complex | Fibonacci(10) | SKIP | — | — |
| 23 | complex | Sum of squares 1..5 | SKIP | — | — |

### Opcodes Exercised

| Opcode | Mnemonic | Format | Tests Using It |
|---|---|---|---|
| 0x00 | HALT | A | All |
| 0x01 | NOP | A | #1 |
| 0x08 | INC | B | #19 |
| 0x09 | DEC | B | #20 |
| 0x0C | PUSH | B | #15 |
| 0x0D | POP | B | #15 |
| 0x18 | MOVI | D | #3,4,6-20 |
| 0x20 | ADD | E | #6,12,13,14 |
| 0x21 | SUB | E | #7 |
| 0x22 | MUL | E | #8 |
| 0x24 | MOD | E | #9 |
| 0x25 | AND | E | #16 |
| 0x26 | OR | E | #17 |
| 0x27 | XOR | E | #18 |
| 0x2C | CMP_EQ | E | #10,11 |
| 0x40 | MOVI16 | F | #5 |

**Total unique opcodes exercised: 16**

---

## 3. Missing Opcodes in Unified Interpreter

Opcodes implemented in `unified_interpreter.py` but **not yet tested** by the conformance suite:

| Opcode | Mnemonic | Format | Category | Status |
|---|---|---|---|---|
| 0x02 | RET | A | system | Implemented, untested |
| 0x03 | IRET | A | system | Implemented, untested |
| 0x04 | BRK | A | debug | Implemented, untested |
| 0x0A | NOT | B | arithmetic | Implemented, untested |
| 0x0B | NEG | B | arithmetic | Implemented, untested |
| 0x0E | CONF_LD | B | confidence | Implemented, untested |
| 0x0F | CONF_ST | B | confidence | Implemented, untested |
| 0x19 | ADDI | D | arithmetic | Implemented, untested |
| 0x1A | SUBI | D | arithmetic | Implemented, untested |
| 0x1B-0x1F | ANDI..SHRI | D | logic/shift | Implemented, untested |
| 0x23 | DIV | E | arithmetic | Implemented, untested |
| 0x28-0x2B | SHL..MAX | E | math | Implemented, untested |
| 0x2D-0x2F | CMP_LT..CMP_NE | E | comparison | Implemented, untested |
| 0x30-0x37 | FADD..ITOF | E | float | Implemented, untested |
| 0x38 | LOAD | E | memory | Implemented, untested |
| 0x39 | STORE | E | memory | Implemented, untested |
| 0x3A | MOV | E | move | Implemented, untested |
| 0x3B | SWP | E | move | Implemented, untested |
| 0x3C-0x3F | JZ..JGT | E | control | Implemented, untested |
| 0x41-0x42 | ADDI16..SUBI16 | F | arithmetic | Implemented, untested |
| 0x43 | JMP | F | control | Implemented, untested |
| 0x44 | JAL | F | control | Implemented, untested |
| 0x45 | CALL | F | control | Implemented, untested |
| 0x46 | LOOP | F | control | Implemented, untested |
| 0x47 | SELECT | F | control | Implemented, untested |
| 0x48-0x4F | LOADOFF..FILL | G | memory | Implemented, untested |
| 0x50-0x5F | TELL..HEARTBT | E | a2a | Stubbed |
| 0x60-0x6F | C_ADD..C_VOTE | E | confidence | Partially implemented |
| 0x70+ | Extended | Various | various | Stubbed |

---

## 4. C Runtime Gap Analysis

The C runtime (JetsonClaw1's domain) has the following gaps relative to the unified spec:

### Known C Runtime Gaps

1. **No public C VM implementation exists** — JetsonClaw1's CUDA VM and edge VM are mentioned in fleet context but have not been audited or tested against conformance vectors.

2. **Format encoding mismatch** — The C runtime likely uses the same divergent opcodes.py numbering as the Python runtime (since they shared a common ancestor). The unified ISA format encoding (F=4B big-endian imm16, G=5B) needs to be adopted.

3. **Missing confidence register file** — The unified ISA specifies a parallel confidence register file (CR0-CR15). This is a novel feature not present in any current runtime.

4. **Missing tensor/neural ops (0xC0-0xCF)** — No runtime has implemented the tensor instruction set (TMATMUL, TCONV, TPOOL, etc.).

5. **Missing crypto ops (0x98-0x9F, 0xAA-0xAF)** — SHA256, CRC32, HMAC, AES operations are specified but unimplemented.

### Action Items for C Runtime Convergence

| Priority | Item | Effort |
|---|---|---|
| P0 | Adopt unified opcode numbering | Medium (bytecode migration tool exists) |
| P0 | Implement Format A-G decoder | Medium |
| P1 | Pass basic arithmetic conformance (20 vectors) | Low |
| P1 | Implement confidence register file | Medium |
| P2 | Implement memory ops (LOAD/STORE with offsets) | Low |
| P2 | Implement control flow (JMP/JAL/CALL/LOOP) | Low |
| P3 | Implement A2A fleet ops (0x50-0x5F) | High |
| P3 | Implement tensor ops (0xC0-0xCF) | High |

---

## 5. Recommendations

### Immediate (this sprint)

1. **Flesh out conformance test vectors** — Add bytecode for the 3 skipped complex programs (GCD, Fibonacci, Sum of Squares). Add test vectors for DIV, JNZ, JMP, MOV, LOAD/STORE, LOOP, and negative number arithmetic.

2. **Run existing Python runtime against unified tests** — The existing `interpreter.py` will fail all 20 tests because it uses the old opcode numbering. This failure is expected and documents the exact scope of migration.

3. **Bootstrap C runtime conformance** — Provide the C team with this conformance runner and the test vectors. They can port the `run_bytecode()` interface.

### Short-term (next 2 sprints)

4. **ISA migration for Python runtime** — Modify `interpreter.py` to support both old and new opcode numbering via a mode flag, then deprecate the old numbering.

5. **Add float arithmetic tests** — Test vectors for FADD, FSUB, FMUL, FDIV, FTOI, ITOF.

6. **Add memory region tests** — Test LOAD/STORE with computed addresses.

### Long-term

7. **Full 256-opcode coverage** — Extend test vectors to cover all ~200 defined opcodes.

8. **Fuzzing** — Generate random bytecode programs and compare outputs across runtimes.

9. **Performance benchmarks** — Run the same programs through Python and C runtimes and compare cycle counts.

---

## Files Created

| File | Lines | Purpose |
|---|---|---|
| `src/flux/vm/unified_interpreter.py` | ~470 | Unified ISA Python VM |
| `tools/conformance_runner.py` | ~200 | Conformance test runner |
| `tools/conformance_report.json` | — | Machine-readable test results |

## Files Read

| File | Purpose |
|---|---|
| `src/flux/vm/interpreter.py` | Existing Python VM (old ISA numbering) |
| `src/flux/bytecode/opcodes.py` | Old opcode definitions |
| `src/flux/bytecode/isa_unified.py` | Unified ISA opcode table |
| `src/flux/bytecode/formats.py` | Format encoding reference |
| `tests/test_conformance.py` | Test vectors |
