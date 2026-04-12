# FLUX Unified ISA — C Reference VM

Standalone C implementation of the converged FLUX ISA for cross-runtime conformance testing. Produces identical results to the Python `unified_interpreter.py` for all 20 conformance test vectors.

## Build

```bash
gcc -O2 -Wall -Wextra -o flux_vm_unified flux_vm_unified.c
```

Requires only `stdio`, `stdlib`, `stdint`, `string` — no external dependencies.

## Run

### From stdin:
```bash
printf '\x18\x00\x2a\x00' | ./flux_vm_unified   # MOVI R0, 42; HALT
```

### From file:
```bash
printf '\x01\x00' > test.bin && ./flux_vm_unified test.bin   # NOP, HALT
```

### Output format:
```
halted=1 crashed=0 cycles=2 stack_depth=0
R0=42 R1=0 R2=0 R3=0 R4=0 R5=0 R6=0 R7=0 R8=0 R9=0 R10=0 R11=0 R12=0 R13=0 R14=0 R15=0
```

### Exit codes:
- `0` — halted normally (no crash)
- `1` — crashed (stack underflow, division by zero, illegal opcode, etc.)

### Trace mode:
```bash
./flux_vm_unified -t test.bin   # prints each instruction as it executes
```

## Run Conformance Tests

```bash
./run_conformance.sh              # compile + run all 20 tests
./run_conformance.sh --skip-build # skip compilation, just run tests
```

Expected output:
```
=== Results ===
  PASSED:  20/23
  FAILED:  0/23
  SKIPPED: 3/23

All tests passed! C VM is ISA-conformant.
```

The 3 skipped tests (GCD, Fibonacci, Sum of Squares) are defined as source descriptions rather than bytecode — they must be hand-assembled and tested separately.

## Architecture

### Instruction Formats

| Format | Size   | Encoding                              |
|--------|--------|---------------------------------------|
| A      | 1 byte | `[op]`                                |
| B      | 2 bytes| `[op][rd]`                            |
| C      | 2 bytes| `[op][imm8]`                          |
| D      | 3 bytes| `[op][rd][imm8]` (sign-extended)      |
| E      | 4 bytes| `[op][rd][rs1][rs2]`                  |
| F      | 4 bytes| `[op][rd][imm16hi][imm16lo]`          |
| G      | 5 bytes| `[op][rd][rs1][imm16hi][imm16lo]`     |

### Opcode Ranges

| Range    | Format | Category                     |
|----------|--------|------------------------------|
| 0x00-0x07| A      | System control               |
| 0x08-0x0F| B      | Single register ops          |
| 0x10-0x17| C      | Immediate only               |
| 0x18-0x1F| D      | Register + imm8              |
| 0x20-0x3F| E      | Arithmetic/logic/memory/ctrl |
| 0x40-0x47| F      | Register + imm16             |
| 0x48-0x4F| G      | Register + register + imm16  |
| 0x50-0x5F| E      | A2A fleet ops (stubbed)      |
| 0x60-0x6F| E/D    | Confidence-aware variants    |
| 0x70+    | Various | Extended (stubbed)          |

### VM State

- **16 general-purpose registers** (int64_t) — R0 through R15
- **16 confidence registers** (int64_t) — parallel per-register confidence tracking
- **Stack** — 4096 entries of int64_t
- **Linear memory** — 64 KB, little-endian int32 read/write
- **Condition flags** — zero and sign flags
- **Cycle budget** — 10M cycles max before forced halt

### Implemented Opcodes (60+)

**System:** HALT, NOP, RET, IRET, BRK, WFI, RESET, SYN
**Register:** INC, DEC, NOT, NEG, PUSH, POP, CONF_LD, CONF_ST
**Immediate:** MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI
**Arithmetic:** ADD, SUB, MUL, DIV, MOD, MIN, MAX
**Logic:** AND, OR, XOR, SHL, SHR
**Compare:** CMP_EQ, CMP_LT, CMP_GT, CMP_NE
**Float:** FADD, FSUB, FMUL, FDIV, FMIN, FMAX, FTOI, ITOF
**Memory:** LOAD, STORE, MOV, SWP
**Control:** JZ, JNZ, JLT, JGT, JMP, JAL, CALL, LOOP, SELECT
**Offset memory:** LOADOFF, STOREOFF, LOADI, STOREI, ENTER, LEAVE
**Confidence:** C_ADD, C_SUB, C_MUL, C_DIV, C_THRESHOLD

## Differences from Python Implementation

| Aspect          | Python                            | C                                   |
|-----------------|-----------------------------------|-------------------------------------|
| Integer width   | Arbitrary precision               | int64_t (64-bit signed)             |
| Memory          | bytearray(65536)                  | uint8_t[65536]                      |
| Stack           | Python list (unbounded)           | int64_t[4096] (fixed capacity)      |
| Division        | int(v1/v2) via float              | v1/v2 (C99 truncation toward zero)  |
| Build system    | No build needed                   | Single-file gcc compilation         |
| Trace output    | To stdout via print()             | To stdout via printf()              |

**Conformance note:** For all 20 test vectors, values fit within 32-bit range, so int64_t and Python arbitrary precision produce identical results. The C VM is a drop-in conformance oracle.

## Files

| File                    | Description                              |
|-------------------------|------------------------------------------|
| `flux_vm_unified.c`     | C VM implementation (~680 lines)         |
| `run_conformance.sh`    | Test runner (20 tests, bash)             |
| `README.md`             | This file                                |

## Cross-Runtime Validation

This C VM serves as Oracle1's Priority #1: a second independent ISA implementation for cross-runtime conformance validation. To validate a new VM implementation:

1. Run all test vectors through both the Python and C VMs
2. Compare register states byte-for-byte
3. Any discrepancy indicates an ISA divergence requiring resolution
