# FLUX ISA v3 Compressed 2-Byte Instruction Format Specification

**Document ID:** ISA-003-COMPRESSED
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-12
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** ISA v3 full draft (253 base opcodes), `isa-v3-escape-prefix-spec.md` (ISA-002)
**Tracks:** Oracle1 TASK-BOARD ISA-003
**Relationship:** Complements ISA-001 (v3 full spec) and ISA-002 (escape prefix)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Frequency Analysis](#2-frequency-analysis)
3. [Compressed Mode Detection](#3-compressed-mode-detection)
4. [Compressed Format Design](#4-compressed-format-design)
   - 4.1 [CR — Compressed Register](#41-cr--compressed-register)
   - 4.2 [CI — Compressed Immediate](#42-ci--compressed-immediate)
   - 4.3 [CJ — Compressed Jump](#43-cj--compressed-jump)
   - 4.4 [CM — Compressed Misc / Escape](#44-cm--compressed-misc--escape)
5. [Complete Opcode Mapping Table](#5-complete-opcode-mapping-table)
6. [Decoding Logic](#6-decoding-logic)
7. [Assembly Syntax](#7-assembly-syntax)
8. [Code Size Analysis](#8-code-size-analysis)
9. [Edge vs Cloud Tradeoffs](#9-edge-vs-cloud-tradeoffs)
10. [Interaction with Format H (0xFF Escape Prefix)](#10-interaction-with-format-h-0xff-escape-prefix)
11. [Interaction with Security Model](#11-interaction-with-security-model)
12. [Conformance Vectors](#12-conformance-vectors)
13. [Implementation Checklist](#13-implementation-checklist)
14. [Design Decision Summary](#14-design-decision-summary)
15. [Appendix A — Encoding Examples](#appendix-a--encoding-examples)
16. [Appendix B — Relationship to Other Tasks](#appendix-b--relationship-to-other-tasks)

---

## 1. Executive Summary

FLUX ISA v3 instructions range from 1 byte (Format A: HALT, NOP) to 5 bytes (Format G: LOADOFF, STOREOFF), with a typical weighted average of 3.0–3.5 bytes per instruction. For edge deployments on memory-constrained devices such as NVIDIA Jetson Orin Nano (8 GB shared RAM), every byte of bytecode matters — particularly when agents receive bytecode via A2A messages over bandwidth-limited maritime links.

This specification introduces a **compressed 2-byte instruction format**, directly analogous to RISC-V's C-extension (RV32C). The design provides four compressed sub-formats (CR, CI, CJ, CM) that encode the most frequently executed opcodes into a fixed 2-byte encoding, reducing typical code size by **25–40%** depending on program mix.

The compression targets the top 32 opcodes by execution frequency — MOV, ADD, SUB, MOVI, ADDI, CMP, JZ, JNZ, JMP, LOAD, STORE, MUL, AND, OR, XOR, DEC, INC, PUSH, POP — which collectively account for approximately **92–97%** of all dynamically executed instructions in benchmark programs (Fibonacci, bubble sort, matrix multiply, string processing).

The compressed format is opt-in, controlled by an assembler directive (`.cfile`) or compiler flag (`--compressed`). Standard ISA v3 programs run unchanged on all VMs; only programs explicitly compiled for compressed mode use the 2-byte encoding. This avoids any impact on existing tooling or cloud deployments where fixed-width analysis is preferred.

**Key metrics:**
| Metric | Value |
|--------|-------|
| Compressed instruction size | 2 bytes (fixed) |
| Compressed opcode coverage | 32 of 253 base opcodes (~12.6% by count, ~95% by frequency) |
| Register operand range | R0–R15 (full 16-register access via 4-bit fields) |
| Immediate operand range | −16 to +15 (5-bit signed) |
| Jump offset range | −16 to +15 instructions (5-bit signed, PC-relative) |
| Typical code size reduction | 25–40% |
| Worst-case (Format G heavy) | 10–15% |
| Best-case (Format E/D loops) | 40–50% |

---

## 2. Frequency Analysis

### 2.1 Methodology

Opcode frequency was derived from two sources:

1. **Execution traces** from the FLUX performance benchmark suite (v2 report, 2026-04-12), covering four representative programs: `fibonacci_30` (214 cycles), `bubble_sort_100` (2,844 cycles), `matmul_5x5` (2,006 cycles), `string_process` (8,005 cycles).
2. **Static instruction counts** from the expanded conformance test suite (71 vectors, 35 unique opcodes), which exercises a broad cross-section of ISA functionality.

### 2.2 Opcode Frequency Ranking

| Rank | Opcode | Original Hex | Format | Bytes | Category | Est. Dynamic % |
|------|--------|-------------|--------|-------|----------|---------------|
| 1 | MOV | 0x3A | E | 4 | data movement | 14.2% |
| 2 | MOVI | 0x18 | D | 3 | data movement | 11.8% |
| 3 | ADD | 0x20 | E | 4 | arithmetic | 9.5% |
| 4 | ADDI | 0x19 | D | 3 | arithmetic | 7.3% |
| 5 | CMP_EQ / CMP_LT / CMP_GT | 0x2C/0x2D/0x2E | E | 4 | comparison | 6.8% |
| 6 | JZ | 0x3C | E | 4 | control flow | 6.4% |
| 7 | JNZ | 0x3D | E | 4 | control flow | 5.9% |
| 8 | JMP | 0x43 | F | 4 | control flow | 5.1% |
| 9 | LOAD | 0x38 | E | 4 | memory | 4.7% |
| 10 | STORE | 0x39 | E | 4 | memory | 4.3% |
| 11 | SUB | 0x21 | E | 4 | arithmetic | 3.8% |
| 12 | SUBI | 0x1A | D | 3 | arithmetic | 3.1% |
| 13 | MUL | 0x22 | E | 4 | arithmetic | 2.9% |
| 14 | DEC | 0x09 | B | 2 | arithmetic | 2.6% |
| 15 | INC | 0x08 | B | 2 | arithmetic | 2.4% |
| 16 | PUSH | 0x0C | B | 2 | stack | 2.1% |
| 17 | POP | 0x0D | B | 2 | stack | 1.9% |
| 18 | AND | 0x25 | E | 4 | logic | 1.7% |
| 19 | OR | 0x26 | E | 4 | logic | 1.5% |
| 20 | XOR | 0x27 | E | 4 | logic | 1.3% |
| 21 | DIV | 0x23 | E | 4 | arithmetic | 1.1% |
| 22 | ANDI | 0x1B | D | 3 | logic | 0.9% |
| 23 | ORI | 0x1C | D | 3 | logic | 0.8% |
| 24 | NOP | 0x01 | A | 1 | system | 0.7% |
| 25 | HALT | 0x00 | A | 1 | system | 0.5% |
| 26 | RET | 0x02 | A | 1 | control flow | 0.4% |
| 27 | SWP | 0x3B | E | 4 | data movement | 0.3% |
| 28 | JLT / JGT | 0x3E/0x3F | E | 4 | control flow | 0.3% |
| 29 | NOT / NEG | 0x0A/0x0B | B | 2 | logic | 0.2% |
| 30 | XORI | 0x1D | D | 3 | logic | 0.2% |
| 31 | LOOP | 0x46 | F | 4 | control flow | 0.2% |
| 32 | CALL | 0x45 | F | 4 | control flow | 0.1% |
| — | All others | various | various | various | specialty | ~2.3% |

### 2.3 Coverage Analysis

| Tier | Opcodes | Cumulative Frequency |
|------|---------|---------------------|
| **Top 10** | MOV, MOVI, ADD, ADDI, CMP, JZ, JNZ, JMP, LOAD, STORE | ~75.0% |
| **Top 16** | + SUB, SUBI, MUL, DEC, INC, PUSH, POP | ~89.5% |
| **Top 20** | + AND, OR, XOR, DIV | ~94.5% |
| **Top 32** | + ANDI, ORI, NOP, HALT, RET, SWP, JLT, JGT, NOT, NEG, XORI, LOOP | ~97.7% |
| **Remaining ~221** | TRAP, EXTENDED, tensor, sensor, crypto, collection, vector, A2A, confidence, viewpoint | ~2.3% |

**Key finding:** The top 32 opcodes account for approximately **97.7%** of all dynamically executed instructions. A compressed format encoding these 32 operations into 2-byte fixed-width instructions would dramatically reduce code size for the common case while requiring fallback to normal encoding for the remaining ~2.3% of operations.

### 2.4 Format Distribution

| Normal Format | Byte Size | % of Instructions | Compressible? |
|--------------|-----------|-------------------|---------------|
| A (zero-operand) | 1 | ~1.6% | No — already minimal |
| B (single-register) | 2 | ~7.2% | No — already 2 bytes |
| C (immediate-only) | 2 | ~0.5% | No — already 2 bytes |
| D (register + imm8) | 3 | ~23.9% | **Yes → 2 bytes (−33%)** |
| E (three-register) | 4 | ~57.1% | **Yes → 2 bytes (−50%)** |
| F (register + imm16) | 4 | ~7.5% | **Yes → 2 bytes (−50%)** |
| G (reg + reg + imm16) | 5 | ~2.2% | Partial (via escape) |

**The highest-impact compression targets are Format E (57.1% of instructions, 4→2 bytes) and Format D (23.9%, 3→2 bytes).** Together these account for 81% of all instructions and offer the largest per-instruction savings.

---

## 3. Compressed Mode Detection

### 3.1 The Encoding Conflict Problem

A naïve approach — using bits[7:6] of byte[0] to distinguish compressed from normal instructions — faces a fundamental conflict: the ISA v3 opcode space (0x00–0xFF) is fully allocated. Every possible byte[0] value maps to a valid base-ISA opcode. There is no unused 2-bit prefix pattern.

Specifically:
- byte[0] bits[7:6] = 0b00 → addresses 0x00–0x3F (Format A/D/E: HALT, MOVI, ADD, etc.)
- byte[0] bits[7:6] = 0b01 → addresses 0x40–0x7F (Format F/G/E: JMP, LOADOFF, A2A, etc.)
- byte[0] bits[7:6] = 0b10 → addresses 0x80–0xBF (Format E: sensor, math, collection, vector)
- byte[0] bits[7:6] = 0b11 → addresses 0xC0–0xFF (Format E/F/G/A: tensor, GPU, coroutine, system)

This is the same challenge RISC-V faced: the base ISA's encoding space admits no "free" 2-bit prefix. RISC-V solved it by *designing the base 32-bit ISA to never produce instructions with bits[1:0] = 0b11 at any instruction boundary*, then using that pattern for compressed 16-bit instructions.

### 3.2 Solution: Compressed Mode Flag

FLUX uses variable-length instructions (1–5 bytes) rather than fixed-width 32-bit words, making RISC-V's exact approach inapplicable. Instead, FLUX adopts a **mode-dependent decode**:

1. **A mode flag** in the bytecode header (or VM configuration) selects between standard and compressed decode.
2. **In standard mode** (default): all byte[0] values decode as normal ISA v3 instructions per the base format dispatch rules. Zero overhead, zero behavioral change.
3. **In compressed mode**: the VM decodes ALL instructions as 2-byte compressed words. The 16-bit word's bits[15:14] select the sub-format. One dedicated opcode (CM.ESCAPE) provides a fallback to normal decode for instructions that cannot be compressed.

This is analogous to ARM's Thumb mode: a mode switch changes how the fetch/decode pipeline interprets byte streams.

### 3.3 Bytecode Header Extension

The existing ISA v3 optional bytecode header is extended:

```
Byte 0-3:  0x46 0x4C 0x55 0x58    ; "FLUX" magic
Byte 4:    ISA version (0x03)
Byte 5:    Flags byte:
             Bit 0: compressed_mode (1 = compressed, 0 = standard)
             Bit 1: has_extensions
             Bits 2-7: reserved (must be 0)
Byte 6:    Number of extensions used (if bit 1 set)
Byte 7+:   Extension IDs used (1 byte each)
```

**Flag bit 0 (compressed_mode):** When set, the VM enters compressed decode mode starting immediately after the header. When clear (default), the VM uses standard decode.

Programs without a header are always decoded in standard mode — preserving full backward compatibility.

### 3.4 VM Detection Algorithm

```python
def detect_mode(bytecode: bytes) -> bool:
    """Check if bytecode uses compressed mode."""
    if len(bytecode) < 5:
        return False  # Too short for header
    if bytecode[0:4] != b'FLUX':
        return False  # No header → standard mode
    if bytecode[4] < 3:
        return False  # ISA version < 3
    return bool(bytecode[5] & 0x01)  # Check compressed_mode flag
```

### 3.5 Assembler Activation

```
# Enable compressed mode for entire file
.cfile

# Or via command-line flag
flux-as --compressed program.asm -o program.bin

# Or per-target
flux-as --target=edge program.asm -o program.bin   # Enables compression
flux-as --target=cloud program.asm -o program.bin   # No compression
```

When `.cfile` is active, the assembler:
1. Sets the compressed_mode flag in the bytecode header
2. Attempts to encode every instruction in compressed format
3. Falls back to CM.ESCAPE + normal encoding for instructions that cannot be compressed
4. Reports compression statistics (total bytes, compressed count, escape count, ratio)

---

## 4. Compressed Format Design

All compressed instructions are exactly 2 bytes (16 bits). The top 2 bits of the 16-bit word select the sub-format:

| Bits [15:14] | Format | Name | Purpose |
|-------------|--------|------|---------|
| 0b11 | CR | Compressed Register | Register-register operations (compresses Format E) |
| 0b10 | CI | Compressed Immediate | Register-immediate operations (compresses Format D) |
| 0b01 | CJ | Compressed Jump | Short-range branches (compresses Format E/F jumps) |
| 0b00 | CM | Compressed Misc | Zero-operand ops + escape to normal mode |

### 4.1 CR — Compressed Register

**Purpose:** Encode the most common register-register operations (currently 4-byte Format E) into 2 bytes.

**Encoding:**
```
 15  14  13  12  11  10   9   8   7   6   5   4   3   2   1   0
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
| 1 | 1 |  opc[3]  |  opc[0] |         rd[4:0]        | rs[4:0]  |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
  |   |   |<---4 bits--->|       |<-----5 bits----->|<----5 bits---->|
  |   |           |                |                   |
  |   |     opcode (0-15)       destination        source register
  |   |                         register             (R0-R15)
  CR prefix
  (0b11)
```

**Byte layout:**
```
byte[0] = 11_oooo_rr  (prefix=11, opcode[3:0], rd[4:3])
byte[1] = rrr_sssss   (rd[2:0], rs[4:0])
```

**Semantics:** `rd = OP(rs, ...)` or `rd = OP(rd, rs)` depending on the specific opcode.

| Opcode | Mnemonic | Original | Semantics |
|--------|----------|----------|-----------|
| 0x0 | C.MOV | MOV (0x3A, E) | rd = rs |
| 0x1 | C.ADD | ADD (0x20, E) | rd = rd + rs |
| 0x2 | C.SUB | SUB (0x21, E) | rd = rd − rs |
| 0x3 | C.MUL | MUL (0x22, E) | rd = rd × rs |
| 0x4 | C.AND | AND (0x25, E) | rd = rd & rs |
| 0x5 | C.OR | OR (0x26, E) | rd = rd \| rs |
| 0x6 | C.XOR | XOR (0x27, E) | rd = rd ^ rs |
| 0x7 | C.DIV | DIV (0x23, E) | rd = rd / rs (signed, trap on zero) |
| 0x8 | C.CMP_EQ | CMP_EQ (0x2C, E) | rd = (rd == rs) ? 1 : 0 |
| 0x9 | C.CMP_LT | CMP_LT (0x2D, E) | rd = (rd < rs) ? 1 : 0 |
| 0xA | C.CMP_GT | CMP_GT (0x2E, E) | rd = (rd > rs) ? 1 : 0 |
| 0xB | C.CMP_NE | CMP_NE (0x2F, E) | rd = (rd != rs) ? 1 : 0 |
| 0xC | C.LOAD | LOAD (0x38, E) | rd = mem[rd + rs] (rd used as base) |
| 0xD | C.STORE | STORE (0x39, E) | mem[rd + rs] = rs (rd used as base) |
| 0xE | C.SWP | SWP (0x3B, E) | swap(rd, rs) |
| 0xF | C.EXT | (escape) | Next byte = extension sub-opcode (see §10) |

**Notes:**
- C.LOAD uses rd as the base address register AND the destination. The effective address is `rd + rs` (original R[rd] + R[rs]). The loaded value replaces R[rd].
- C.STORE uses rd as the base address and rs as the source value. The effective address is `R[rd] + R[rs]`. The value stored is R[rs].
- C.MOV is the only CR opcode that is NOT read-modify-write on rd. It simply copies rs to rd.
- C.DIV traps on division by zero (consistent with base ISA behavior).
- C.EXT provides a bridge to extension opcodes (see §10).

**Example encodings:**
```
C.MOV R3, R5  →  11_0000_01_011_00101  →  0xC5 0x65
C.ADD R1, R2  →  11_0001_00_001_00010  →  0xC4 0x22
C.SUB R7, R0  →  11_0010_00_111_00000  →  0xC7 0x00
```

### 4.2 CI — Compressed Immediate

**Purpose:** Encode register-immediate operations (currently 3-byte Format D, plus selected Format B single-register ops) into 2 bytes.

**Encoding:**
```
 15  14  13  12  11  10   9   8   7   6   5   4   3   2   1   0
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
| 1 | 0 |  opc[3]  |  opc[0] |         rd[4:0]        |imm5[4:0]|
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
  |   |   |<---4 bits--->|       |<-----5 bits----->|<-5 bits-->|
  |   |           |                |                   |
  |   |     opcode (0-15)       destination        signed immediate
  |   |                         register             (−16 to +15)
  CI prefix
  (0b10)
```

**Byte layout:**
```
byte[0] = 10_oooo_rr  (prefix=10, opcode[3:0], rd[4:3])
byte[1] = rrr_iiiii   (rd[2:0], imm5[4:0])
```

**Semantics:** `rd = rd OP sign_extend(imm5)` or `rd = sign_extend(imm5)`.

| Opcode | Mnemonic | Original | Semantics |
|--------|----------|----------|-----------|
| 0x0 | C.MOVI | MOVI (0x18, D) | rd = sign_extend(imm5) |
| 0x1 | C.ADDI | ADDI (0x19, D) | rd = rd + sign_extend(imm5) |
| 0x2 | C.SUBI | SUBI (0x1A, D) | rd = rd − sign_extend(imm5) |
| 0x3 | C.ANDI | ANDI (0x1B, D) | rd = rd & zero_extend(imm5) |
| 0x4 | C.ORI | ORI (0x1C, D) | rd = rd \| zero_extend(imm5) |
| 0x5 | C.XORI | XORI (0x1D, D) | rd = rd ^ zero_extend(imm5) |
| 0x6 | C.INC | INC (0x08, B) | rd = rd + 1 (imm5 ignored) |
| 0x7 | C.DEC | DEC (0x09, B) | rd = rd − 1 (imm5 ignored) |
| 0x8 | C.NEG | NEG (0x0B, B) | rd = −rd (imm5 ignored) |
| 0x9 | C.NOT | NOT (0x0A, B) | rd = ~rd (imm5 ignored) |
| 0xA | C.PUSH | PUSH (0x0C, B) | push(rd) (imm5 ignored) |
| 0xB | C.POP | POP (0x0D, B) | pop → rd (imm5 ignored) |
| 0xC | C.ADDI_N | ADDI + negate | rd = rd − sign_extend(imm5) (alias for SUBI) |
| 0xD | C.SHLI | SHLI (0x1E, D) | rd = rd << imm5 (zero-extend) |
| 0xE | C.SHRI | SHRI (0x1F, D) | rd = rd >> imm5 (logical, zero-extend) |
| 0xF | reserved | — | Reserved for future use |

**Notes:**
- The imm5 field is **5-bit signed** (−16 to +15) for arithmetic ops (MOVI, ADDI, SUBI) and **5-bit unsigned** (0–31) for logical/shift ops (ANDI, ORI, XORI, SHLI, SHRI).
- C.INC, C.DEC, C.NEG, C.NOT, C.PUSH, C.POP are Format B operations in the base ISA (already 2 bytes). They gain no size benefit from compression but benefit from the uniform 2-byte instruction width in compressed mode, which simplifies branch offset calculation and enables simpler VM fetch logic.
- C.ADDI_N (opcode 0xC) is an alias for C.SUBI, provided for assembler convenience when writing `SUBI` as `ADDI rd, -imm`.
- Bit manipulation operations (ANDI, ORI, XORI) use **zero-extended** imm5 (unsigned 0–31), consistent with base ISA semantics where the imm8 is zero-extended.

**Example encodings:**
```
C.MOVI R1, 7    →  10_0000_00_001_00111  →  0x82 0x17
C.ADDI R3, -2   →  10_0001_00_011_11110  →  0x86 0x3E  (−2 = 0b11110)
C.SUBI R0, 5    →  10_0010_00_000_00101  →  0x88 0x05
C.INC R5        →  10_0110_00_101_00000  →  0x98 0x20  (imm5 ignored)
C.PUSH R2       →  10_1010_00_010_00000  →  0xA8 0x20  (imm5 ignored)
```

### 4.3 CJ — Compressed Jump

**Purpose:** Encode short-range conditional and unconditional branches (currently 4-byte Format E/F) into 2 bytes. The 5-bit signed offset covers −16 to +15 instructions, sufficient for most loop-back branches and short forward skips.

**Encoding:**
```
 15  14  13  12  11  10   9   8   7   6   5   4   3   2   1   0
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
| 0 | 1 |  opc[3]  |  opc[0] |        reg[4:0]       | off[4:0] |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
  |   |   |<---4 bits--->|       |<-----5 bits----->|<-5 bits-->|
  |   |           |                |                   |
  |   |     opcode (0-15)     condition          signed offset
  |   |                        register           (−16 to +15)
  CJ prefix
  (0b01)
```

**Byte layout:**
```
byte[0] = 01_oooo_rr  (prefix=01, opcode[3:0], reg[4:3])
byte[1] = rrr_ooooo   (reg[2:0], offset[4:0])
```

**Semantics:** `if condition(reg): PC += sign_extend(offset)`

The offset is counted in **compressed instruction units** (2 bytes each). An offset of +1 skips the next 2-byte instruction. An offset of −1 branches back to the previous instruction.

| Opcode | Mnemonic | Original | Condition |
|--------|----------|----------|-----------|
| 0x0 | C.JMP | JMP (0x43, F) | Unconditional: PC += offset (reg ignored) |
| 0x1 | C.JZ | JZ (0x3C, E) | if reg == 0: PC += offset |
| 0x2 | C.JNZ | JNZ (0x3D, E) | if reg != 0: PC += offset |
| 0x3 | C.JLT | JLT (0x3E, E) | if reg < 0: PC += offset |
| 0x4 | C.JGT | JGT (0x3F, E) | if reg > 0: PC += offset |
| 0x5 | C.JLE | — (synthetic) | if reg ≤ 0: PC += offset |
| 0x6 | C.JGE | — (synthetic) | if reg ≥ 0: PC += offset |
| 0x7 | C.LOOP | LOOP (0x46, F) | reg−−; if reg > 0: PC −= offset |
| 0x8 | C.JAL | JAL (0x44, F) | reg = PC; PC += offset (link register) |
| 0x9 | C.CALL | CALL (0x45, F) | push(PC); PC = reg + offset |
| 0xA | C.SELECT | SELECT (0x47, F) | PC += offset × reg (branch table) |
| 0xB–0xF | reserved | — | Reserved for future branch types |

**Notes:**
- C.JMP ignores the reg field (unconditional). The register field bits are reserved (should be zero).
- C.LOOP first decrements reg, then tests if the result is > 0. This matches the base ISA LOOP (0x46) semantics. The offset is subtracted (not added) to support backward loop branches — the assembler negates the offset if needed.
- C.JLE and C.JGE are **synthetic instructions** (no direct base-ISA equivalent). They expand at decode time: `C.JLE` tests `(reg == 0 || reg < 0)`, and `C.JGE` tests `(reg == 0 || reg > 0)`. The VM implements them directly for convenience.
- C.JAL stores the return address in the register specified by the reg field (not a fixed link register). The stored address points to the instruction AFTER the C.JAL.
- C.CALL pushes the current PC to the operand stack and jumps to `R[reg] + offset`. Used for subroutine calls where the target address is computed.
- The offset range of −16 to +15 instructions (each 2 bytes) covers −32 to +30 bytes of PC-relative displacement. For loops, backward jumps with small offsets (−1 to −8) are the most common pattern.

**Example encodings:**
```
C.JZ R3, -3       →  01_0001_00_011_11101  →  0x46 0x3D  (−3 = 0b11101)
C.JMP +5          →  01_0000_00_000_00101  →  0x40 0x05
C.LOOP R1, -4     →  01_0111_00_001_11100  →  0x70 0x1C  (−4 = 0b11100)
C.JNZ R0, +2      →  01_0010_00_000_00010  →  0x44 0x02
```

### 4.4 CM — Compressed Misc / Escape

**Purpose:** Encode zero-operand instructions and provide the critical **escape hatch** back to normal (variable-length) ISA v3 decode for instructions that cannot be compressed.

**Encoding:**
```
 15  14  13  12  11  10   9   8   7   6   5   4   3   2   1   0
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
| 0 | 0 |  opc[3]  |  opc[0] |         sub[9:0]                    |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
  |   |   |<---4 bits--->|       |<------------10 bits----------->|
  |   |           |                |
  |   |     opcode (0-15)      sub-field
  CM prefix                   (opcode-dependent)
  (0b00)
```

**Byte layout:**
```
byte[0] = 00_oooo_ss  (prefix=00, opcode[3:0], sub[9:8])
byte[1] = ssssssss    (sub[7:0])
```

| Opcode | Mnemonic | Original | Semantics |
|--------|----------|----------|-----------|
| 0x0 | C.ESCAPE | — | **Escape to normal decode.** The next N bytes are decoded as a normal ISA v3 instruction (variable-length, 1–8 bytes). After the normal instruction completes, compressed mode resumes. The sub field is reserved (must be zero). |
| 0x1 | C.HALT | HALT (0x00, A) | Stop execution. Sub field reserved. |
| 0x2 | C.NOP | NOP (0x01, A) | No operation (pipeline synchronization). Sub field reserved. |
| 0x3 | C.RET | RET (0x02, A) | Return from subroutine (pop PC from stack). Sub field reserved. |
| 0x4 | C.BRK | BRK (0x04, A) | Breakpoint (trap to debugger). Sub field = debug code. |
| 0x5 | C.SYN | SYN (0x07, A) | Memory barrier / synchronization. Sub field = barrier type. |
| 0x6 | C.VER | VER (0xF5, A) | R0 = ISA version (3 for v3). Sub field reserved. |
| 0x7 | C.WFI | WFI (0x05, A) | Wait for interrupt (low-power idle). Sub field reserved. |
| 0x8 | C.CLF | CLF (0x13, C) | Clear flags register bits. Sub field = mask. |
| 0x9 | C.YIELD | YIELD (0x15, C) | Yield execution. Sub field = cycle count. |
| 0xA | C.LOADOFF | LOADOFF (0x48, G) | rd = mem[reg + zero_extend(sub[9:0])]. Uses sub as 10-bit unsigned offset. |
| 0xB | C.STOREOFF | STOREOFF (0x49, G) | mem[reg + zero_extend(sub[9:0])] = R[sub[9:4]]. Uses sub as 10-bit unsigned offset. |
| 0xC–0xF | reserved | — | Reserved for future misc operations |

**Notes on C.ESCAPE (opcode 0x0):**

C.ESCAPE is the **most critical instruction in the compressed format.** It allows programs to use ANY normal ISA v3 instruction — including Format G (5 bytes), Format H escape prefix (3–8 bytes), and future extensions — without leaving compressed mode.

```
Encoding:  0x00 0x00  [normal_instruction_bytes...]

Example:   C.ESCAPE + MOVI16 R1, 1024
           0x00 0x00  0x40 0x01 0x04 0x00
           ^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^
           CM.ESCAPE  Normal Format F (4 bytes)
           (2 bytes)  (4 bytes) → total 6 bytes
```

The VM's behavior when it encounters C.ESCAPE:
1. Consume the 2-byte CM.ESCAPE instruction
2. Read byte[0] of the normal instruction
3. Determine normal instruction size via standard format dispatch (Formats A–G or H)
4. Decode and execute the normal instruction
5. Resume compressed mode decode at the next instruction boundary

**Cost analysis:** C.ESCAPE adds 2 bytes of overhead per escaped instruction. This is acceptable because:
- Escaped instructions are rare (~2–5% of all instructions in typical programs)
- The alternative (no compression) costs 0 bytes extra but wastes 2–3 bytes per common instruction
- Net savings remain strongly positive (see §8)

**Notes on C.LOADOFF and C.STOREOFF (opcodes 0xA, 0xB):**

These provide compressed access to offset-based memory operations (base ISA Format G, normally 5 bytes). The trade-off is a reduced offset range: 10 bits unsigned (0–1023) vs. 16 bits in the base ISA. For stack-relative accesses (typical offsets 0–255), this is more than sufficient.

The sub field encoding for C.LOADOFF:
- sub[9:4] = register index (R0–R63, but only R0–R15 are valid)
- sub[3:0] = (unused, combined with sub[9:4] to form 10-bit unsigned offset)

Wait — this is ambiguous. Let me clarify: C.LOADOFF uses an implicit register. The sub field provides a 10-bit unsigned offset, and the destination/base register is implied by context. Actually, this needs a register operand. Let me redefine:

**Revised C.LOADOFF encoding:**
```
C.LOADOFF: sub[9:5] = rd (destination register), sub[4:0] = base register
Then the NEXT byte pair (another compressed instruction or a CM.ESCAPE+imm16)
provides the 16-bit offset. This doesn't fit cleanly in 2 bytes.
```

Since LOADOFF/STOREOFF fundamentally require 3 operands (rd, base, offset), they cannot be cleanly compressed into 2 bytes. These CM slots (0xA, 0xB) are better used for other purposes:

| Opcode | Revised Mnemonic | Semantics |
|--------|-----------------|-----------|
| 0xA | C.CONF_LD | Load confidence register for rd |
| 0xB | C.CONF_ST | Store confidence from rd |
| 0xC–0xF | reserved | Reserved |

Programs needing LOADOFF/STOREOFF should use C.ESCAPE + normal Format G encoding.

**Notes on C.HALT, C.NOP, C.RET (opcodes 0x1, 0x2, 0x3):**

In the base ISA, these are Format A (1 byte). In compressed mode, they occupy 2 bytes — a slight size increase. However:
- These instructions typically appear 1–3 times per program (HALT at exit, occasional NOP/RET)
- The total overhead is 1–3 extra bytes per program
- The benefit of uniform 2-byte instruction width (simpler VM fetch, predictable branch targets) outweighs this tiny cost
- An optimizing assembler can avoid compressed encoding for these: `C.ESCAPE` (2 bytes) + `HALT` (1 byte) = 3 bytes total, which is WORSE than `C.HALT` (2 bytes). So C.HALT is preferred.

---

## 5. Complete Opcode Mapping Table

### 5.1 Full Mapping — CR (Compressed Register)

| Comp. Opcode | Comp. Hex | Original Hex | Original Fmt | Mnemonic | Bytes Saved |
|-------------|-----------|-------------|-------------|----------|-------------|
| 0 | 0xC0–0xCF | 0x3A | E (4B) | C.MOV rd, rs | 2 |
| 1 | 0xC0–0xCF | 0x20 | E (4B) | C.ADD rd, rs | 2 |
| 2 | 0xC0–0xCF | 0x21 | E (4B) | C.SUB rd, rs | 2 |
| 3 | 0xC0–0xCF | 0x22 | E (4B) | C.MUL rd, rs | 2 |
| 4 | 0xC0–0xCF | 0x25 | E (4B) | C.AND rd, rs | 2 |
| 5 | 0xC0–0xCF | 0x26 | E (4B) | C.OR rd, rs | 2 |
| 6 | 0xC0–0xCF | 0x27 | E (4B) | C.XOR rd, rs | 2 |
| 7 | 0xC0–0xCF | 0x23 | E (4B) | C.DIV rd, rs | 2 |
| 8 | 0xC0–0xCF | 0x2C | E (4B) | C.CMP_EQ rd, rs | 2 |
| 9 | 0xC0–0xCF | 0x2D | E (4B) | C.CMP_LT rd, rs | 2 |
| 0xA | 0xC0–0xCF | 0x2E | E (4B) | C.CMP_GT rd, rs | 2 |
| 0xB | 0xC0–0xCF | 0x2F | E (4B) | C.CMP_NE rd, rs | 2 |
| 0xC | 0xC0–0xCF | 0x38 | E (4B) | C.LOAD rd, rs | 2 |
| 0xD | 0xC0–0xCF | 0x39 | E (4B) | C.STORE rd, rs | 2 |
| 0xE | 0xC0–0xCF | 0x3B | E (4B) | C.SWP rd, rs | 2 |
| 0xF | 0xC0–0xCF | — | — | C.EXT sub_opcode | N/A |

### 5.2 Full Mapping — CI (Compressed Immediate)

| Comp. Opcode | Comp. Hex | Original Hex | Original Fmt | Mnemonic | Bytes Saved |
|-------------|-----------|-------------|-------------|----------|-------------|
| 0 | 0x80–0xBF | 0x18 | D (3B) | C.MOVI rd, imm5 | 1 |
| 1 | 0x80–0xBF | 0x19 | D (3B) | C.ADDI rd, imm5 | 1 |
| 2 | 0x80–0xBF | 0x1A | D (3B) | C.SUBI rd, imm5 | 1 |
| 3 | 0x80–0xBF | 0x1B | D (3B) | C.ANDI rd, imm5 | 1 |
| 4 | 0x80–0xBF | 0x1C | D (3B) | C.ORI rd, imm5 | 1 |
| 5 | 0x80–0xBF | 0x1D | D (3B) | C.XORI rd, imm5 | 1 |
| 6 | 0x80–0xBF | 0x08 | B (2B) | C.INC rd | 0 |
| 7 | 0x80–0xBF | 0x09 | B (2B) | C.DEC rd | 0 |
| 8 | 0x80–0xBF | 0x0B | B (2B) | C.NEG rd | 0 |
| 9 | 0x80–0xBF | 0x0A | B (2B) | C.NOT rd | 0 |
| 0xA | 0x80–0xBF | 0x0C | B (2B) | C.PUSH rd | 0 |
| 0xB | 0x80–0xBF | 0x0D | B (2B) | C.POP rd | 0 |
| 0xC | 0x80–0xBF | 0x1A | D (3B) | C.ADDI_N rd, −imm | 1 |
| 0xD | 0x80–0xBF | 0x1E | D (3B) | C.SHLI rd, imm5 | 1 |
| 0xE | 0x80–0xBF | 0x1F | D (3B) | C.SHRI rd, imm5 | 1 |
| 0xF | 0x80–0xBF | — | — | reserved | — |

### 5.3 Full Mapping — CJ (Compressed Jump)

| Comp. Opcode | Comp. Hex | Original Hex | Original Fmt | Mnemonic | Bytes Saved |
|-------------|-----------|-------------|-------------|----------|-------------|
| 0 | 0x40–0x7F | 0x43 | F (4B) | C.JMP offset | 2 |
| 1 | 0x40–0x7F | 0x3C | E (4B) | C.JZ reg, offset | 2 |
| 2 | 0x40–0x7F | 0x3D | E (4B) | C.JNZ reg, offset | 2 |
| 3 | 0x40–0x7F | 0x3E | E (4B) | C.JLT reg, offset | 2 |
| 4 | 0x40–0x7F | 0x3F | E (4B) | C.JGT reg, offset | 2 |
| 5 | 0x40–0x7F | — | — | C.JLE reg, offset | 2 |
| 6 | 0x40–0x7F | — | — | C.JGE reg, offset | 2 |
| 7 | 0x40–0x7F | 0x46 | F (4B) | C.LOOP reg, offset | 2 |
| 8 | 0x40–0x7F | 0x44 | F (4B) | C.JAL reg, offset | 2 |
| 9 | 0x40–0x7F | 0x45 | F (4B) | C.CALL reg, offset | 2 |
| 0xA | 0x40–0x7F | 0x47 | F (4B) | C.SELECT reg, offset | 2 |
| 0xB–0xF | 0x40–0x7F | — | — | reserved | — |

### 5.4 Full Mapping — CM (Compressed Misc)

| Comp. Opcode | Comp. Hex | Original Hex | Original Fmt | Mnemonic | Bytes Saved |
|-------------|-----------|-------------|-------------|----------|-------------|
| 0 | 0x00–0x3F | — | — | C.ESCAPE | +2 (overhead) |
| 1 | 0x00–0x3F | 0x00 | A (1B) | C.HALT | −1 (worse) |
| 2 | 0x00–0x3F | 0x01 | A (1B) | C.NOP | −1 (worse) |
| 3 | 0x00–0x3F | 0x02 | A (1B) | C.RET | −1 (worse) |
| 4 | 0x00–0x3F | 0x04 | A (1B) | C.BRK sub | −1 (worse) |
| 5 | 0x00–0x3F | 0x07 | A (1B) | C.SYN sub | −1 (worse) |
| 6 | 0x00–0x3F | 0xF5 | A (1B) | C.VER | −1 (worse) |
| 7 | 0x00–0x3F | 0x05 | A (1B) | C.WFI | −1 (worse) |
| 8 | 0x00–0x3F | 0x13 | C (2B) | C.CLF sub | 0 |
| 9 | 0x00–0x3F | 0x15 | C (2B) | C.YIELD sub | 0 |
| 0xA | 0x00–0x3F | 0x0E | B (2B) | C.CONF_LD rd | 0 |
| 0xB | 0x00–0x3F | 0x0F | B (2B) | C.CONF_ST rd | 0 |
| 0xC–0xF | 0x00–0x3F | — | — | reserved | — |

**Note on "Bytes Saved" column:** Positive values indicate compression benefit (fewer bytes). Negative values indicate a size increase. Zero means same size. CM instructions that map to Format A (1 byte) are slightly larger in compressed mode (2 bytes), but this overhead is negligible (1–3 extra bytes per program).

---

## 6. Decoding Logic

### 6.1 High-Level Decode Algorithm

```python
def execute_compressed_program(memory: bytes, compressed_mode: bool = False):
    """Execute a FLUX ISA v3 program with optional compressed mode support."""
    pc = 0

    # Check for FLUX header
    if len(memory) >= 6 and memory[0:4] == b'FLUX':
        isa_version = memory[4]
        flags = memory[5]
        compressed_mode = bool(flags & 0x01)
        pc = 6 + (flags & 0x02) * (1 + memory[6])  # Skip extensions list if present

    while pc < len(memory):
        if compressed_mode:
            pc = decode_and_execute_compressed(memory, pc)
        else:
            pc = decode_and_execute_normal(memory, pc)


def decode_and_execute_normal(memory: bytes, pc: int) -> int:
    """Standard ISA v3 decode (Formats A–G, H)."""
    opcode = memory[pc]

    if opcode <= 0x03:    # Format A (1 byte)
        execute_format_a(opcode)
        return pc + 1
    elif opcode <= 0x0F:  # Format B (2 bytes)
        rd = memory[pc + 1]
        execute_format_b(opcode, rd)
        return pc + 2
    elif opcode <= 0x17:  # Format C (2 bytes)
        imm8 = memory[pc + 1]
        execute_format_c(opcode, imm8)
        return pc + 2
    elif opcode <= 0x1F:  # Format D (3 bytes)
        rd = memory[pc + 1]
        imm8 = memory[pc + 2]
        execute_format_d(opcode, rd, imm8)
        return pc + 3
    elif opcode <= 0x3F:  # Format E (4 bytes)
        rd = memory[pc + 1]
        rs1 = memory[pc + 2]
        rs2 = memory[pc + 3]
        execute_format_e(opcode, rd, rs1, rs2)
        return pc + 4
    elif opcode <= 0x47:  # Format F (4 bytes)
        rd = memory[pc + 1]
        imm16 = (memory[pc + 2] << 8) | memory[pc + 3]
        execute_format_f(opcode, rd, imm16)
        return pc + 4
    elif opcode <= 0x4F:  # Format G (5 bytes)
        rd = memory[pc + 1]
        rs1 = memory[pc + 2]
        imm16 = (memory[pc + 3] << 8) | memory[pc + 4]
        execute_format_g(opcode, rd, rs1, imm16)
        return pc + 5
    elif opcode <= 0x6F:  # Confidence-aware variants (Format E, 4 bytes)
        rd = memory[pc + 1]
        rs1 = memory[pc + 2]
        rs2 = memory[pc + 3]
        execute_confidence(opcode, rd, rs1, rs2)
        return pc + 4
    elif opcode == 0xFF:  # Format H — Escape Prefix (3+ bytes)
        ext_id = memory[pc + 1]
        sub_opcode = memory[pc + 2]
        return execute_escape_prefix(memory, pc, ext_id, sub_opcode)
    else:
        # Other ranges (0x70-0xFE) follow format dispatch rules
        # (see ISA v3 full spec for complete dispatch)
        return decode_extended_ranges(memory, pc)


def decode_and_execute_compressed(memory: bytes, pc: int) -> int:
    """Compressed mode decode — all instructions are 2 bytes, except ESCAPE."""
    if pc + 1 >= len(memory):
        raise Fault("TRUNCATED_INSTRUCTION", pc)

    # Read 16-bit compressed word (big-endian bit numbering)
    word = (memory[pc] << 8) | memory[pc + 1]
    prefix = (word >> 14) & 0x03     # bits[15:14]
    opcode = (word >> 10) & 0x0F     # bits[13:10]
    operand_a = (word >> 5) & 0x1F   # bits[9:5]
    operand_b = word & 0x1F          # bits[4:0]

    if prefix == 0b11:    # CR — Compressed Register
        rd = operand_a
        rs = operand_b
        execute_cr(opcode, rd, rs)
        return pc + 2

    elif prefix == 0b10:  # CI — Compressed Immediate
        rd = operand_a
        imm5 = sign_extend_5bit(operand_b)
        execute_ci(opcode, rd, imm5)
        return pc + 2

    elif prefix == 0b01:  # CJ — Compressed Jump
        reg = operand_a
        offset = sign_extend_5bit(operand_b)
        result = execute_cj(opcode, reg, offset)
        if result is None:
            return pc + 2  # Branch not taken
        else:
            return result   # Branch taken (new PC)

    elif prefix == 0b00:  # CM — Compressed Misc / Escape
        sub = (operand_a << 5) | operand_b  # 10-bit sub-field
        if opcode == 0x0:  # C.ESCAPE
            # Fall through to normal decode for next instruction
            return decode_and_execute_normal(memory, pc + 2)
        else:
            execute_cm(opcode, sub)
            return pc + 2

    raise Fault("INVALID_COMPRESSED_PREFIX", prefix)


def sign_extend_5bit(value: int) -> int:
    """Sign-extend a 5-bit value to Python int."""
    if value & 0x10:  # bit 4 set → negative
        return value - 0x20
    return value
```

### 6.2 Compressed Opcode Dispatch Tables

```python
# CR dispatch — maps compressed opcode to base ISA semantics
CR_DISPATCH = {
    0x0: lambda rd, rs: set_reg(rd, get_reg(rs)),               # C.MOV
    0x1: lambda rd, rs: set_reg(rd, get_reg(rd) + get_reg(rs)), # C.ADD
    0x2: lambda rd, rs: set_reg(rd, get_reg(rd) - get_reg(rs)), # C.SUB
    0x3: lambda rd, rs: set_reg(rd, get_reg(rd) * get_reg(rs)), # C.MUL
    0x4: lambda rd, rs: set_reg(rd, get_reg(rd) & get_reg(rs)), # C.AND
    0x5: lambda rd, rs: set_reg(rd, get_reg(rd) | get_reg(rs)), # C.OR
    0x6: lambda rd, rs: set_reg(rd, get_reg(rd) ^ get_reg(rs)), # C.XOR
    0x7: lambda rd, rs: div_op(rd, rs),                        # C.DIV
    0x8: lambda rd, rs: set_reg(rd, 1 if get_reg(rd)==get_reg(rs) else 0),  # C.CMP_EQ
    0x9: lambda rd, rs: set_reg(rd, 1 if get_reg(rd)<get_reg(rs) else 0),   # C.CMP_LT
    0xA: lambda rd, rs: set_reg(rd, 1 if get_reg(rd)>get_reg(rs) else 0),   # C.CMP_GT
    0xB: lambda rd, rs: set_reg(rd, 1 if get_reg(rd)!=get_reg(rs) else 0),  # C.CMP_NE
    0xC: lambda rd, rs: set_reg(rd, mem[get_reg(rd)+get_reg(rs)]),  # C.LOAD
    0xD: lambda rd, rs: store_mem(get_reg(rd)+get_reg(rs), get_reg(rs)), # C.STORE
    0xE: lambda rd, rs: swap_regs(rd, rs),                       # C.SWP
    0xF: lambda rd, rs: compressed_escape_ext(rs),               # C.EXT
}

# CI dispatch — maps compressed opcode to base ISA semantics
CI_DISPATCH = {
    0x0: lambda rd, imm5: set_reg(rd, sign_extend_5(imm5)),      # C.MOVI
    0x1: lambda rd, imm5: set_reg(rd, get_reg(rd) + imm5),      # C.ADDI
    0x2: lambda rd, imm5: set_reg(rd, get_reg(rd) - imm5),      # C.SUBI
    0x3: lambda rd, imm5: set_reg(rd, get_reg(rd) & (imm5&0x1F)), # C.ANDI
    0x4: lambda rd, imm5: set_reg(rd, get_reg(rd) | (imm5&0x1F)), # C.ORI
    0x5: lambda rd, imm5: set_reg(rd, get_reg(rd) ^ (imm5&0x1F)), # C.XORI
    0x6: lambda rd, imm5: set_reg(rd, get_reg(rd) + 1),          # C.INC
    0x7: lambda rd, imm5: set_reg(rd, get_reg(rd) - 1),          # C.DEC
    0x8: lambda rd, imm5: set_reg(rd, -get_reg(rd)),             # C.NEG
    0x9: lambda rd, imm5: set_reg(rd, ~get_reg(rd)),             # C.NOT
    0xA: lambda rd, imm5: push(get_reg(rd)),                      # C.PUSH
    0xB: lambda rd, imm5: set_reg(rd, pop()),                     # C.POP
    0xC: lambda rd, imm5: set_reg(rd, get_reg(rd) - imm5),       # C.ADDI_N (alias SUBI)
    0xD: lambda rd, imm5: set_reg(rd, get_reg(rd) << (imm5&0x1F)), # C.SHLI
    0xE: lambda rd, imm5: set_reg(rd, get_reg(rd) >> (imm5&0x1F)), # C.SHRI
    0xF: lambda rd, imm5: None,                                    # reserved
}
```

### 6.3 Instruction Size Calculation (for Assembler)

```python
def compressed_instruction_size(mnemonic: str, operands: list) -> int:
    """Return the total byte size of an instruction in compressed mode."""
    # All compressed instructions are 2 bytes
    COMPRESSED_MNEMONICS = {
        'C.MOV', 'C.ADD', 'C.SUB', 'C.MUL', 'C.AND', 'C.OR', 'C.XOR',
        'C.DIV', 'C.CMP_EQ', 'C.CMP_LT', 'C.CMP_GT', 'C.CMP_NE',
        'C.LOAD', 'C.STORE', 'C.SWP',
        'C.MOVI', 'C.ADDI', 'C.SUBI', 'C.ANDI', 'C.ORI', 'C.XORI',
        'C.INC', 'C.DEC', 'C.NEG', 'C.NOT', 'C.PUSH', 'C.POP',
        'C.SHLI', 'C.SHRI',
        'C.JMP', 'C.JZ', 'C.JNZ', 'C.JLT', 'C.JGT', 'C.JLE', 'C.JGE',
        'C.LOOP', 'C.JAL', 'C.CALL', 'C.SELECT',
        'C.HALT', 'C.NOP', 'C.RET', 'C.BRK', 'C.SYN', 'C.VER', 'C.WFI',
        'C.CLF', 'C.YIELD', 'C.CONF_LD', 'C.CONF_ST',
    }

    if mnemonic in COMPRESSED_MNEMONICS:
        return 2  # Compressed instruction

    # Normal instruction via escape: 2 (C.ESCAPE) + normal_size
    normal_size = normal_instruction_size(mnemonic, operands)
    return 2 + normal_size


def normal_instruction_size(mnemonic: str, operands: list) -> int:
    """Return byte size of a normal ISA v3 instruction."""
    # Simplified — see formats.py for complete dispatch
    fmt = OPCODE_FORMAT.get(opcode_from_mnemonic(mnemonic))
    return {1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 4, 7: 5}[fmt.value]
```

---

## 7. Assembly Syntax

### 7.1 Compressed Instruction Mnemonics

Compressed instructions use a `C.` prefix to distinguish them from normal instructions:

```asm
; --- Compressed Register (CR) ---
C.MOV  rd, rs          ; rd = rs
C.ADD  rd, rs          ; rd = rd + rs
C.SUB  rd, rs          ; rd = rd - rs
C.MUL  rd, rs          ; rd = rd * rs
C.AND  rd, rs          ; rd = rd & rs
C.OR   rd, rs          ; rd = rd | rs
C.XOR  rd, rs          ; rd = rd ^ rs
C.DIV  rd, rs          ; rd = rd / rs
C.CMP_EQ rd, rs        ; rd = (rd == rs) ? 1 : 0
C.CMP_LT rd, rs        ; rd = (rd < rs) ? 1 : 0
C.CMP_GT rd, rs        ; rd = (rd > rs) ? 1 : 0
C.CMP_NE rd, rs        ; rd = (rd != rs) ? 1 : 0
C.LOAD rd, rs          ; rd = mem[rd + rs]
C.STORE rd, rs         ; mem[rd + rs] = rs
C.SWP  rd, rs          ; swap(rd, rs)

; --- Compressed Immediate (CI) ---
C.MOVI rd, imm         ; rd = imm (imm: -16 to +15)
C.ADDI rd, imm         ; rd = rd + imm
C.SUBI rd, imm         ; rd = rd - imm
C.ANDI rd, imm         ; rd = rd & imm
C.ORI  rd, imm         ; rd = rd | imm
C.XORI rd, imm         ; rd = rd ^ imm
C.INC  rd              ; rd = rd + 1
C.DEC  rd              ; rd = rd - 1
C.NEG  rd              ; rd = -rd
C.NOT  rd              ; rd = ~rd
C.PUSH rd              ; push rd
C.POP  rd              ; pop -> rd
C.SHLI rd, imm         ; rd = rd << imm
C.SHRI rd, imm         ; rd = rd >> imm

; --- Compressed Jump (CJ) ---
C.JMP  offset          ; PC += offset
C.JZ   reg, offset     ; if reg == 0: PC += offset
C.JNZ  reg, offset     ; if reg != 0: PC += offset
C.JLT  reg, offset     ; if reg < 0: PC += offset
C.JGT  reg, offset     ; if reg > 0: PC += offset
C.JLE  reg, offset     ; if reg <= 0: PC += offset
C.JGE  reg, offset     ; if reg >= 0: PC += offset
C.LOOP reg, offset     ; reg--; if reg > 0: PC -= offset
C.JAL  reg, offset     ; reg = PC; PC += offset
C.CALL reg, offset     ; push(PC); PC = reg + offset

; --- Compressed Misc (CM) ---
C.HALT                  ; stop execution
C.NOP                   ; no operation
C.RET                   ; return from subroutine
C.VER                   ; R0 = ISA version
```

### 7.2 Normal Instructions (via Escape)

Normal instructions can be used in compressed mode without the `C.` prefix. The assembler automatically emits a `C.ESCAPE` prefix:

```asm
; In compressed mode, these automatically get C.ESCAPE prefix:
MOVI16 R1, 1024         ; C.ESCAPE + MOVI16 R1, 1024 (6 bytes total)
LOADOFF R0, R1, 256     ; C.ESCAPE + LOADOFF R0, R1, 256 (7 bytes total)
STOREOFF R2, R3, 128    ; C.ESCAPE + STOREOFF R2, R3, 128 (7 bytes total)
MOD R4, R5, R6          ; C.ESCAPE + MOD R4, R5, R6 (6 bytes total)
0xFF 0x04 0x00 R0 R1 R2 ; C.ESCAPE + EXT_TENSOR op (8 bytes total)
```

### 7.3 Directives

```asm
; Enable compressed mode for entire file
.cfile

; Disable compressed mode (return to standard)
.nocfile

; Report compression statistics (assembler output)
.compress_report

; Force specific instruction to be normal (even in compressed mode)
.force_normal MOVI16 R1, 65535
```

### 7.4 Assembler Behavior

When `.cfile` is active, the assembler applies the following transformation rules:

| Rule | Condition | Action |
|------|-----------|--------|
| 1 | Instruction has C. prefix | Emit 2-byte compressed encoding |
| 2 | Instruction matches a compressible opcode AND operands fit | Auto-compress (emit 2 bytes, add `C.` prefix in listing) |
| 3 | Instruction does NOT match OR operands don't fit | Emit C.ESCAPE (2 bytes) + normal encoding |
| 4 | `.force_normal` directive | Always use rule 3 |
| 5 | No `.cfile` directive | Standard encoding (no compression) |

**Auto-compression operand fit rules:**
- CR formats: both register operands must be in R0–R15 (always true for 4-bit fields)
- CI formats: immediate must fit in −16 to +15 (5-bit signed) or 0–31 (5-bit unsigned for logical ops)
- CJ formats: branch offset must fit in −16 to +15 compressed instructions (i.e., −32 to +30 bytes)

If operands don't fit, the assembler falls back to C.ESCAPE + normal encoding.

### 7.5 Complete Assembly Example — Fibonacci(10)

```asm
.cfile                    ; Enable compressed mode

; --- Fibonacci(10): compute fib(10), result in R1 ---
; Compressed encoding (38 bytes)

    C.MOVI  R1, 0         ; fib(0) = 0          → 2 bytes
    C.MOVI  R2, 1         ; fib(1) = 1          → 2 bytes
    C.MOVI  R3, 10        ; counter = 10         → 2 bytes

loop:
    C.ADD   R0, R1        ; R0 = R1 + R2        → 2 bytes
    C.MOV   R1, R2        ; R1 = old R2          → 2 bytes
    C.MOV   R2, R0        ; R2 = new fib value   → 2 bytes
    C.DEC   R3            ; counter--            → 2 bytes
    C.JNZ   R3, -4        ; if counter != 0: goto loop  → 2 bytes

    C.HALT                  ; done                → 2 bytes

; Total: 9 instructions × 2 bytes = 18 bytes (compressed)
```

**Equivalent standard encoding (without `.cfile`):**

```asm
; Standard encoding (28 bytes)

    MOVI R1, 0             ; 3 bytes (Format D)
    MOVI R2, 1             ; 3 bytes (Format D)
    MOVI R3, 10            ; 3 bytes (Format D)

loop:
    ADD R0, R1, R2         ; 4 bytes (Format E)
    MOV R1, R2, R0         ; 4 bytes (Format E)
    MOV R2, R0, R0         ; 4 bytes (Format E)
    DEC R3                  ; 2 bytes (Format B)
    MOVI R15, -28          ; 3 bytes (scratch for offset)
    JNZ R3, R15            ; 4 bytes (Format E)

    HALT                    ; 1 byte (Format A)

; Total: 28 bytes (standard)
; Savings: 18 / 28 = 35.7% reduction
```

---

## 8. Code Size Analysis

### 8.1 Per-Instruction Size Comparison

| Original Format | Original Size | Compressed Size | Savings |
|----------------|--------------|-----------------|---------|
| Format A (HALT, NOP, RET) | 1 byte | 2 bytes (C.HALT, C.NOP, C.RET) | −1 byte (−100%) |
| Format B (INC, DEC, PUSH, POP) | 2 bytes | 2 bytes (C.INC, C.DEC, etc.) | 0 bytes (0%) |
| Format C (SYS, TRAP) | 2 bytes | 2 bytes (C.ESCAPE + C) or 4 bytes | 0 to +2 bytes |
| Format D (MOVI, ADDI, SUBI) | 3 bytes | 2 bytes (C.MOVI, C.ADDI, etc.) | +1 byte (+33%) |
| Format E (ADD, SUB, MOV, LOAD, STORE) | 4 bytes | 2 bytes (C.ADD, C.MOV, etc.) | +2 bytes (+50%) |
| Format F (JMP, JAL, CALL) | 4 bytes | 2 bytes (C.JMP, C.JAL) | +2 bytes (+50%) |
| Format G (LOADOFF, STOREOFF) | 5 bytes | 7 bytes (C.ESCAPE + G) | −2 bytes (−40%) |
| Format H (Escape prefix) | 3–8 bytes | 5–10 bytes (C.ESCAPE + H) | −2 bytes |

### 8.2 Program-Level Analysis

#### Fibonacci(10)

| Metric | Standard | Compressed | Savings |
|--------|----------|------------|---------|
| Total instructions | 9 | 9 | — |
| Compressed | 0 | 9 | — |
| Escaped | 9 | 0 | — |
| Total bytes | 28 | 18 | **35.7%** |
| Bytes per instruction | 3.11 | 2.00 | — |

#### Bubble Sort (100 elements, 400 compare-swap iterations)

| Metric | Standard | Compressed | Savings |
|--------|----------|------------|---------|
| Estimated instructions | ~1,600 | ~1,600 | — |
| Format E (CMP, MOV, SWP, JNZ) | ~1,000 (4B each) | ~1,000 → compressed (2B) | — |
| Format D (MOVI) | ~300 (3B each) | ~300 → compressed (2B) | — |
| Format B (DEC, INC) | ~200 (2B each) | ~200 → compressed (2B) | — |
| Format A (HALT) | 1 (1B) | 1 → C.HALT (2B) | — |
| Format F (JMP) | ~100 (4B each) | ~100 → compressed (2B) | — |
| Total bytes | ~5,700 | ~3,400 | **~40.4%** |

#### Matrix Multiply (5×5, 500 multiply-accumulate ops)

| Metric | Standard | Compressed | Savings |
|--------|----------|------------|---------|
| Format E (LOAD, STORE, MUL, ADD) | ~1,800 (4B) | ~1,800 → compressed (2B) | — |
| Format D (MOVI, ADDI) | ~400 (3B) | ~400 → compressed (2B) | — |
| Format B (INC, DEC) | ~200 (2B) | ~200 → compressed (2B) | — |
| Format G (LOADOFF, STOREOFF) | ~100 (5B) | ~100 → escape (7B) | — |
| Format A (HALT) | 1 (1B) | 1 → C.HALT (2B) | — |
| Total bytes | ~8,900 | ~5,500 | **~38.2%** |

#### Worst Case: GPU-heavy tensor inference

| Metric | Standard | Compressed | Savings |
|--------|----------|------------|---------|
| Format E (common ops) | ~500 (4B) | ~500 → compressed (2B) | — |
| Format G (DMA, MMIO) | ~300 (5B) | ~300 → escape (7B) | — |
| Format H (EXT_TENSOR) | ~200 (6B avg) | ~200 → escape (8B avg) | — |
| Total bytes | ~4,700 | ~4,100 | **~12.8%** |

### 8.3 Summary

| Program Type | Typical Reduction | Notes |
|-------------|------------------|-------|
| Control-flow heavy (loops, sorts) | **35–45%** | Best case — mostly Format E/D/F |
| Arithmetic heavy (math, signal processing) | **30–40%** | Mix of Format E and D |
| Memory heavy (matmul, tensor) | **15–25%** | Format G/H escape penalty offsets gains |
| I/O heavy (sensor, A2A) | **10–20%** | Many specialty opcodes require escape |
| **Weighted average (typical edge program)** | **25–40%** | Matches target estimate |

---

## 9. Edge vs Cloud Tradeoffs

### 9.1 Edge Deployment (Recommended: Always Compressed)

Edge devices — Jetson Orin Nano (8 GB), Raspberry Pi 5 (4/8 GB), maritime IoT gateways — have tight memory constraints. Every byte of bytecode saved is a byte available for data, model weights, or sensor buffers.

| Factor | Edge Impact |
|--------|------------|
| Memory savings | 25–40% bytecode reduction → proportionally more room for data |
| Fetch bandwidth | Fixed 2-byte instructions → simpler fetch, predictable memory access patterns |
| Decode complexity | Slightly higher (mode check + 2-byte decode) but amortized by simpler operand extraction |
| A2A transfer size | Smaller bytecode payloads → faster agent-to-agent message delivery |
| Flash storage | Smaller binaries → more programs fit in limited flash |
| Cache behavior | Uniform 2-byte width → better I-cache utilization (no mixed 1–5 byte widths) |
| Startup time | Less bytecode to load from flash → faster cold boot |

**Recommendation:** Edge targets should ALWAYS use `--compressed` (or `--target=edge`). The assembler should emit a warning if an edge target binary exceeds 90% escape ratio (indicating the program isn't benefiting from compression).

### 9.2 Cloud Deployment (Recommended: Standard)

Cloud servers have abundant memory and bandwidth. Fixed-width compressed instructions provide minimal benefit and make tooling (disassemblers, debuggers, profilers) slightly more complex.

| Factor | Cloud Impact |
|--------|-------------|
| Memory savings | Negligible (GBs of RAM available) |
| Tooling simplicity | Standard mode: every instruction is self-describing from byte[0] |
| Debugging | Standard mode: breakpoint insertion is trivial (patch byte[0] to BRK) |
| Profiling | Standard mode: instruction counting is straightforward |
| Dynamic analysis | Standard mode: easier to instrument and trace |
| A2A transfer | Network bandwidth is typically not the bottleneck |

**Recommendation:** Cloud targets should use standard mode by default. Compressed mode is available via explicit `--compressed` flag for bandwidth-sensitive cloud-to-edge transfers.

### 9.3 Mixed Deployment Pattern

A common pattern for fleet deployments:

```
1. Agent develops and tests on cloud VM (standard mode, full debugging)
2. Agent compiles final version with --compressed (compressed mode)
3. Compressed bytecode transmitted via A2A to edge agent
4. Edge agent executes compressed bytecode (saves memory/bandwidth)
5. If edge agent needs to relay bytecode to another agent, it forwards compressed
```

The assembler supports both modes from the same source:

```bash
# Development build (standard mode, full debug info)
flux-as program.asm -o program_standard.bin

# Production build (compressed mode, optimized for edge)
flux-as --compressed program.asm -o program_compressed.bin

# Verify semantic equivalence
flux-verify --equal program_standard.bin program_compressed.bin
```

### 9.4 Assembler Flags Summary

| Flag | Effect | Default |
|------|--------|---------|
| `--compressed` / `-c` | Enable compressed mode (emit FLUX header with flag) | Off |
| `--target=edge` | Equivalent to `--compressed --optimize=size` | — |
| `--target=cloud` | Standard mode (no compression) | Default |
| `--compress-report` | Print compression statistics after assembly | Off |
| `--force-escape-threshold=N` | Force escape if operand exceeds N bits (5 default) | 5 |
| `--no-compress-list=OP1,OP2,...` | Never auto-compress listed opcodes | None |

---

## 10. Interaction with Format H (0xFF Escape Prefix)

### 10.1 The Problem

In standard ISA v3, byte value `0xFF` is the escape prefix for Format H extension opcodes:
```
0xFF [ext_id] [sub_opcode] [operands...]
```

In compressed mode, `0xFF` as byte[0] would be decoded as a CR-format compressed instruction (prefix `0b11`). This means the escape prefix mechanism is NOT directly accessible in compressed mode.

### 10.2 Solution: C.ESCAPE + Normal Escape

Programs that need extension opcodes in compressed mode use C.ESCAPE to temporarily exit compressed decode:

```asm
; In compressed mode, call EXT_TENSOR.TMATMUL:
    C.ESCAPE                        ; 2 bytes — exit compressed mode
    0xFF 0x04 0x00 R0 R1 R2        ; 6 bytes — EXT_TENSOR.TMATMUL
    ; Compressed mode resumes here automatically
```

**Total cost:** 2 bytes (C.ESCAPE) + 6 bytes (normal escape) = 8 bytes vs. 6 bytes (standard). Overhead: 2 bytes per extension call.

### 10.3 Solution: CR Opcode 0xF — Compressed Extension Direct

For programs that make frequent extension calls, the overhead of C.ESCAPE (2 bytes per call) can add up. CR opcode 0xF (`C.EXT`) provides a more compact escape path:

```
Encoding: CR format, opcode = 0xF
  byte[0] = 11_1111_rr  (CR prefix, opcode=0xF, rd[4:3])
  byte[1] = rrr_sssss   (rd[2:0], sub_opcode)
```

**Semantics:**
1. `rd` field (5 bits) → `ext_id` (0–31, covers fleet-standard extensions 0x01–0x1F)
2. `sub_opcode` field (5 bits) → first 5 bits of extension sub-opcode (0–31)
3. VM reads the next byte as `sub_opcode[7:5]` (3 bits) + `operand_count` (5 bits, how many operand bytes follow)
4. VM reads `operand_count` additional bytes as operands

```
C.EXT ext_id=4, sub_opcode=0, operands=R0,R1,R2:
  11_1111_00_100_00000  0x20  [sub_hi=0x00, operand_count=3]  R0 R1 R2
  ^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^
  CR prefix + op=0xF    sub_opcode completion + count      operands
  + ext_id=4            (1 byte)                          (3 bytes)
  (2 bytes)                                                Total: 6 bytes
```

**Cost comparison:**

| Method | Encoding | Total Bytes |
|--------|----------|-------------|
| Standard (no compression) | `0xFF ext sub rd rs1 rs2` | 6 bytes |
| C.ESCAPE + normal | `C.ESCAPE` + `0xFF ext sub rd rs1 rs2` | 8 bytes |
| C.EXT (direct) | `C.EXT` + `sub_hi_byte` + `operands` | 6 bytes |

C.EXT matches the standard encoding size (6 bytes) — zero overhead for extension calls!

**C.EXT constraints:**
- `ext_id` limited to 5 bits (0–31). Extensions with IDs 0x20+ require C.ESCAPE fallback.
- `sub_opcode` limited to 5 bits (0–31). Sub-opcodes 0x20+ require C.ESCAPE fallback.
- In practice, this covers all 6 proposed fleet-standard extensions (IDs 0x01–0x06) and their first 32 sub-opcodes each.

### 10.4 Extension Accessibility Summary

| Extension Access Method | ext_id Range | sub_opcode Range | Bytes |
|------------------------|-------------|-----------------|-------|
| C.EXT (direct) | 0–31 | 0–31 | 6 |
| C.ESCAPE + normal | 0–255 | 0–255 | 8+ |
| Standard mode (no compression) | 0–255 | 0–255 | 6+ |

**Recommendation:** For programs that use extensions with ext_id ≤ 31 and sub_opcode ≤ 31, C.EXT provides zero-overhead access. For all other cases, C.ESCAPE adds 2 bytes of overhead per extension call.

---

## 11. Interaction with Security Model

### 11.1 Bytecode Verification in Compressed Mode

The 4-stage bytecode verification pipeline (structural, register, control-flow, security) applies to compressed bytecode with the following modifications:

| Stage | Standard Mode | Compressed Mode |
|-------|--------------|-----------------|
| Structural | Validate format completeness | Validate all 2-byte words are valid compressed instructions |
| Register | Check operands ∈ [0, 16) | Same — rd/rs/imm5 fields validated |
| Control-flow | Check jump targets are aligned | Check CJ offsets land on 2-byte boundaries |
| Security | Check unauthorized opcodes | Check both compressed and escaped opcodes |

### 11.2 Compressed Instruction Security Flags

Compressed instructions carry the same security semantics as their base-ISA equivalents:

| Compressed | Base ISA | Privileged? | Capability Required |
|-----------|----------|-------------|-------------------|
| C.LOAD | LOAD (0x38) | No | READ_MEMORY |
| C.STORE | STORE (0x39) | No | WRITE_MEMORY |
| C.PUSH / C.POP | PUSH/POP | No | STACK_MANIP |
| C.JAL / C.CALL | JAL/CALL | No | CALL |
| C.CMP_* | CMP_* | No | — |
| C.EXT | (escape) | Varies | Varies by extension |

### 11.3 C.ESCAPE Verification

C.ESCAPE introduces a normal instruction into the compressed stream. The verification pipeline must:
1. Verify the escaped instruction passes all 4 verification stages
2. Verify the escaped instruction does not itself contain another C.ESCAPE (nested escape is forbidden)
3. Track the escaped instruction's security category for auditing

---

## 12. Conformance Vectors

### 12.1 Vector CMP-001: CR Format — C.MOV

**Name:** `compressed_cr_mov`
**Category:** compressed
**Description:** C.MOV correctly copies register value

```
Input bytecode (compressed mode header + instructions):
  46 4C 55 58 03 01    ; FLUX header, v3, compressed_mode=1
  C.MOVI R1, 42        ; 0x82 0x2A  (CI: rd=1, imm5=42)
  C.MOV  R0, R1        ; 0xC5 0x40  (CR: rd=0, rs=1)
  C.HALT               ; 0x04 0x00  (CM: opcode=1)

Expected: R0 = 42
```

### 12.2 Vector CMP-002: CR Format — C.ADD

**Name:** `compressed_cr_add`
**Category:** compressed
**Description:** C.ADD correctly adds two registers

```
Input bytecode:
  FLUX header (compressed)
  C.MOVI R1, 10        ; R1 = 10
  C.MOVI R2, 20        ; R2 = 20
  C.ADD  R0, R1        ; R0 = R0 + R1 = 0 + 10 = 10
  C.ADD  R0, R2        ; R0 = R0 + R2 = 10 + 20 = 30
  C.HALT

Expected: R0 = 30
```

### 12.3 Vector CMP-003: CJ Format — C.JZ Backward Loop

**Name:** `compressed_cj_loop`
**Category:** compressed
**Description:** C.JZ with negative offset creates a valid loop

```
Input bytecode:
  FLUX header (compressed)
  C.MOVI R1, 0         ; R1 = 0 (accumulator)
  C.MOVI R3, 5         ; R3 = 5 (counter)
loop:                       ; compressed instruction index 2
  C.ADDI R1, 3         ; R1 += 3
  C.DEC  R3            ; R3--
  C.JNZ  R3, -2        ; if R3 != 0, goto loop (−2 compressed instructions)
  C.HALT

Expected: R1 = 15 (3 × 5 iterations), R3 = 0
```

### 12.4 Vector CMP-004: C.ESCAPE — Normal Instruction

**Name:** `compressed_escape_normal`
**Category:** compressed
**Description:** C.ESCAPE correctly falls through to normal decode

```
Input bytecode:
  FLUX header (compressed)
  C.ESCAPE             ; 0x00 0x00 — exit compressed mode
  0x40 0x01 0x04 0x00  ; MOVI16 R1, 1024 (Format F, normal)
  C.MOV  R0, R1        ; R0 = R1
  C.HALT

Expected: R0 = 1024, R1 = 1024
```

### 12.5 Vector CMP-005: C.EXT — Extension Access

**Name:** `compressed_ext_direct`
**Category:** compressed
**Description:** C.EXT correctly dispatches to extension opcode

```
Input bytecode (VM with EXT_BABEL loaded):
  FLUX header (compressed)
  C.MOVI R1, 100       ; text address
  C.MOVI R2, 10        ; text length
  C.EXT ext_id=1, sub=0  ; EXT_BABEL.LANG_DETECT (R0, R1, R2)
  ; operands: R0, R1, R2 → 3 operand bytes
  C.HALT

Expected: R0 = detected language ID (≥ 0)
No FAULT raised
```

### 12.6 Vector CMP-006: Mixed Compressed + Escaped Fibonacci

**Name:** `compressed_fibonacci_10`
**Category:** compressed
**Description:** Fibonacci(10) using mixed compressed and escaped instructions

```
Input bytecode:
  FLUX header (compressed)
  C.MOVI R1, 0         ; fib(0) = 0
  C.MOVI R2, 1         ; fib(1) = 1
  C.MOVI R3, 10        ; counter
loop:
  C.ADD  R0, R1        ; R0 = R1 + R2
  C.MOV  R1, R2        ; shift
  C.MOV  R2, R0        ; shift
  C.DEC  R3
  C.JNZ  R3, -4
  C.HALT

Expected: R2 = 55 (fibonacci(10)), R3 = 0
```

### 12.7 Vector CMP-007: Sign Extension in CI

**Name:** `compressed_ci_sign_extend`
**Category:** compressed
**Description:** C.ADDI with negative imm5 correctly sign-extends

```
Input bytecode:
  FLUX header (compressed)
  C.MOVI R0, 20        ; R0 = 20
  C.ADDI R0, -5        ; R0 = 20 + (-5) = 15  (imm5 = 0b11011 = −5)
  C.ADDI R0, -10       ; R0 = 15 + (−10) = 5  (imm5 = 0b10110 = −10)
  C.HALT

Expected: R0 = 5
```

### 12.8 Vector CMP-008: Standard Program Unaffected

**Name:** `compressed_standard_compat`
**Category:** migration
**Description:** Standard (non-compressed) bytecode runs identically on v3 VM

```
Input bytecode (NO FLUX header, NO compressed flag):
  0x18 0x00 0x0A       ; MOVI R0, 10 (Format D, normal)
  0x18 0x01 0x14       ; MOVI R1, 20 (Format D, normal)
  0x20 0x02 0x00 0x01  ; ADD R2, R0, R1 (Format E, normal)
  0x00                 ; HALT (Format A, normal)

Expected: R2 = 30
Behavior: identical to ISA v3 standard decode
```

### 12.9 Vector CMP-009: Invalid Compressed Opcode

**Name:** `compressed_invalid_opcode`
**Category:** compressed
**Description:** Reserved compressed opcode raises appropriate fault

```
Input bytecode:
  FLUX header (compressed)
  ; CR prefix, opcode = 0 (C.MOV) but CI prefix 0b10 + opcode 0xF (reserved)
  0xAF 0xFF             ; CI format, opcode=0xF (reserved)
  C.HALT

Expected: FAULT(INVALID_COMPRESSED_OPCODE, 0x0F) raised before HALT
```

### 12.10 Vector CMP-010: Branch Offset Boundary

**Name:** `compressed_branch_boundary`
**Category:** compressed
**Description:** Maximum positive and negative branch offsets work correctly

```
Input bytecode:
  FLUX header (compressed)
  C.MOVI R0, 0
  C.MOVI R1, 1
  C.JZ   R0, +15       ; max positive offset (not taken, R0=0... wait, R0=0 so TAKEN)
  C.MOVI R2, 99        ; should be skipped
  ; ... (13 NOPs to pad)
  C.HALT               ; target of +15 jump
  ; Test negative: from here, -16 should go back to the start
  C.JMP  -16           ; max negative offset

Expected: R2 = 0 (MOVI R2, 99 was skipped by jump)
No FAULT from out-of-range offset
```

---

## 13. Implementation Checklist

### 13.1 Assembler (`flux-as`)

- [ ] Add `.cfile` / `.nocfile` directive parsing
- [ ] Add `--compressed` / `-c` command-line flag
- [ ] Add `--target=edge` flag (enables compression)
- [ ] Implement compressed opcode encoding for all 4 formats
- [ ] Implement auto-compression with operand fit checking
- [ ] Implement C.ESCAPE emission for non-compressible instructions
- [ ] Implement C.EXT emission for extension opcodes within range
- [ ] Add `--compress-report` flag for statistics output
- [ ] Implement `.force_normal` directive
- [ ] Update label resolution for 2-byte instruction alignment
- [ ] Emit FLUX header with compressed_mode flag

### 13.2 Disassembler (`flux-dis`)

- [ ] Detect compressed mode from FLUX header
- [ ] Decode all 4 compressed formats
- [ ] Display `C.` prefix for compressed instructions
- [ ] Display `ESCAPE →` for C.ESCAPE sequences
- [ ] Show original opcode correspondence in comments

### 13.3 Python VM (`unified_interpreter.py`)

- [ ] Add compressed mode detection from FLUX header
- [ ] Implement `decode_and_execute_compressed()` function
- [ ] Implement all CR dispatch entries (16 opcodes)
- [ ] Implement all CI dispatch entries (16 opcodes)
- [ ] Implement all CJ dispatch entries (12 opcodes)
- [ ] Implement all CM dispatch entries (12 opcodes)
- [ ] Implement C.ESCAPE fallthrough to normal decode
- [ ] Implement C.EXT extension dispatch
- [ ] Add compressed mode to snapshot/restore

### 13.4 C VM (`flux_vm_unified.c`)

- [ ] Port compressed mode detection
- [ ] Port all compressed format decode logic
- [ ] Port C.ESCAPE and C.EXT
- [ ] Ensure zero compiler warnings with `-Wall -Wextra`
- [ ] Verify all 10 conformance vectors pass

### 13.5 Bytecode Verifier

- [ ] Add compressed mode structural validation (all instructions 2 bytes, except ESCAPE+normal)
- [ ] Validate compressed operand ranges (rd 0–15, imm5 −16 to +15)
- [ ] Validate CJ branch targets land on 2-byte boundaries
- [ ] Validate C.ESCAPE sequences don't nest
- [ ] Validate C.EXT ext_id and sub_opcode ranges

### 13.6 Conformance Tests

- [ ] Add 10 compressed conformance vectors (CMP-001 through CMP-010)
- [ ] Run expanded suite (71 + 10 = 81 vectors) on both Python and C VMs
- [ ] Cross-verify identical results

### 13.7 Documentation

- [ ] Update ISA v3 full draft to reference this spec
- [ ] Update developer guide with compressed mode examples
- [ ] Update assembler man page with new flags

---

## 14. Design Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Instruction width | Fixed 2 bytes | Uniform width simplifies VM fetch, enables predictable branch targets |
| Number of formats | 4 (CR, CI, CJ, CM) | Covers register-register, register-immediate, branch, and misc operations |
| Opcode space per format | 16 (4-bit field) | 64 total compressed opcodes covers top ~97% of dynamic frequency |
| Register range | R0–R15 (4-bit fields) | Full register access without restriction |
| Immediate range | −16 to +15 (5-bit signed) | Sufficient for most small constants; larger values use C.ESCAPE |
| Branch offset range | −16 to +15 instructions | Covers most loop-back and short forward branches |
| Mode selection | Bytecode header flag (bit 0 of flags byte) | Opt-in, no impact on existing programs |
| Escape mechanism | CM opcode 0x0 (C.ESCAPE) | Zero-restriction access to full ISA; 2-byte overhead per escape |
| Extension access | CR opcode 0xF (C.EXT) | Zero-overhead access to fleet-standard extensions (ext_id ≤ 31, sub ≤ 31) |
| C.HALT/C.NOP/C.RET size | 2 bytes (vs 1 byte normal) | Acceptable overhead (1–3 extra bytes per program) for uniform decode |
| Backward compatibility | Guaranteed | No FLUX header → standard mode → zero behavioral change |
| Forward compatibility | Graceful | VMs without compressed support read standard-only programs; compressed programs require v3 VM |

---

## Appendix A — Encoding Examples

### A.1 CR Format Encoding

```
; C.MOV R3, R5 — rd=3, rs=5
; Bits: 11_0000_01_011_00101
;       PP=11, op=0000, rd=00011, rs=00101
; byte[0] = 0b11000001 = 0xC1
; byte[1] = 0b01100101 = 0x65
; Hex: C1 65

; C.ADD R0, R15 — rd=0, rs=15
; Bits: 11_0001_00_000_01111
; byte[0] = 0b11000100 = 0xC4
; byte[1] = 0b00001111 = 0x0F
; Hex: C4 0F

; C.CMP_EQ R7, R7 — rd=7, rs=7 (self-compare, always sets R7=1)
; Bits: 11_1000_00_111_00111
; byte[0] = 0b11100000 = 0xE0
; byte[1] = 0b11100111 = 0xE7
; Hex: E0 E7
```

### A.2 CI Format Encoding

```
; C.MOVI R1, 7 — rd=1, imm5=7
; Bits: 10_0000_00_001_00111
; byte[0] = 0b10000000 = 0x80
; byte[1] = 0b00100111 = 0x27
; Hex: 80 27

; C.ADDI R3, -2 — rd=3, imm5=-2 (sign-extended: 0b11110)
; Bits: 10_0001_00_011_11110
; byte[0] = 0b10000100 = 0x84
; byte[1] = 0b01111110 = 0x7E
; Hex: 84 7E

; C.PUSH R2 — rd=2, imm5=0 (ignored)
; Bits: 10_1010_00_010_00000
; byte[0] = 0b10101000 = 0xA8
; byte[1] = 0b01000000 = 0x40
; Hex: A8 40
```

### A.3 CJ Format Encoding

```
; C.JZ R3, -3 — reg=3, offset=-3 (0b11101)
; Bits: 01_0001_00_011_11101
; byte[0] = 0b01000100 = 0x44
; byte[1] = 0b01111101 = 0x7D
; Hex: 44 7D

; C.JMP +5 — reg=0 (ignored), offset=5
; Bits: 01_0000_00_000_00101
; byte[0] = 0b01000000 = 0x40
; byte[1] = 0b00000101 = 0x05
; Hex: 40 05
```

### A.4 CM Format Encoding

```
; C.ESCAPE — opcode=0, sub=0
; Bits: 00_0000_00_000_00000
; byte[0] = 0b00000000 = 0x00
; byte[1] = 0b00000000 = 0x00
; Hex: 00 00

; C.HALT — opcode=1, sub=0
; Bits: 00_0001_00_000_00000
; byte[0] = 0b00000100 = 0x04
; byte[1] = 0b00000000 = 0x00
; Hex: 04 00

; C.NOP — opcode=2, sub=0
; Bits: 00_0010_00_000_00000
; byte[0] = 0b00001000 = 0x08
; byte[1] = 0b00000000 = 0x00
; Hex: 08 00
```

### A.5 C.EXT Encoding

```
; C.EXT ext_id=1, sub_opcode=0 — EXT_BABEL.LANG_DETECT
; rd field = ext_id = 1, sub_opcode = 0
; Bits: 11_1111_00_001_00000
; byte[0] = 0b11111100 = 0xFC
; byte[1] = 0b00100000 = 0x20
; Then: sub_opcode_hi = 0x00 (sub[7:5]=000, count=3), operands R0 R1 R2
; Hex: FC 20 00 R0 R1 R2
```

### A.6 Complete Fibonacci(10) Bytecode

```
; Compressed mode Fibonacci(10) — complete hex dump
; FLUX header:
  46 4C 55 58           ; "FLUX" magic
  03                    ; ISA version 3
  01                    ; flags: compressed_mode=1

; Instructions:
  80 27                  ; C.MOVI R1, 0     (fib(0))
  80 2B                  ; C.MOVI R2, 1     (wait, imm5=1 → 0b00001 → byte[1]=0b00100001=0x21)

; Let me recalculate:
; C.MOVI R1, 0: rd=1, imm5=0
;   byte[0] = 10_0000_00_001 = 0b10000000 = 0x80
;   byte[1] = 001_00000 = 0b00100000 = 0x20
;   Hex: 80 20

; C.MOVI R2, 1: rd=2, imm5=1
;   byte[0] = 10_0000_00_010 = 0b10000000 = 0x80
;   byte[1] = 010_00001 = 0b01000001 = 0x41
;   Hex: 80 41

; C.MOVI R3, 10: rd=3, imm5=10
;   byte[0] = 10_0000_00_011 = 0b10000000 = 0x80
;   byte[1] = 011_01010 = 0b01101010 = 0x6A
;   Hex: 80 6A

; C.ADD R0, R1: rd=0, rs=1
;   byte[0] = 11_0001_00_000 = 0b11000100 = 0xC4
;   byte[1] = 000_00001 = 0b00000001 = 0x01
;   Hex: C4 01

; C.MOV R1, R2: rd=1, rs=2
;   byte[0] = 11_0000_00_001 = 0b11000000 = 0xC0
;   byte[1] = 001_00010 = 0b00100010 = 0x22
;   Hex: C0 22

; C.MOV R2, R0: rd=2, rs=0
;   byte[0] = 11_0000_00_010 = 0b11000000 = 0xC0
;   byte[1] = 010_00000 = 0b01000000 = 0x40
;   Hex: C0 40

; C.DEC R3: rd=3, imm5=0 (ignored)
;   byte[0] = 10_0111_00_011 = 0b10011100 = 0x9C
;   byte[1] = 011_00000 = 0b01100000 = 0x60
;   Hex: 9C 60

; C.JNZ R3, -4: reg=3, offset=-4 (0b11100)
;   byte[0] = 01_0010_00_011 = 0b01001000 = 0x48
;   byte[1] = 011_11100 = 0b01111100 = 0x7C
;   Hex: 48 7C

; C.HALT: opcode=1, sub=0
;   byte[0] = 00_0001_00_000 = 0b00000100 = 0x04
;   byte[1] = 000_00000 = 0b00000000 = 0x00
;   Hex: 04 00

; Complete hex dump:
; 46 4C 55 58 03 01    — FLUX header (6 bytes)
; 80 20                 — C.MOVI R1, 0     (2 bytes)
; 80 41                 — C.MOVI R2, 1     (2 bytes)
; 80 6A                 — C.MOVI R3, 10    (2 bytes)
; C4 01                 — C.ADD  R0, R1   (2 bytes)
; C0 22                 — C.MOV  R1, R2   (2 bytes)
; C0 40                 — C.MOV  R2, R0   (2 bytes)
; 9C 60                 — C.DEC  R3       (2 bytes)
; 48 7C                 — C.JNZ  R3, -4   (2 bytes)
; 04 00                 — C.HALT          (2 bytes)
;
; Total: 6 (header) + 18 (instructions) = 24 bytes
; Equivalent standard: ~28 bytes (no header) = 28 bytes
; With header: standard would be 6 + 28 = 34 bytes
; Savings: (34 - 24) / 34 = 29.4%
```

---

## Appendix B — Relationship to Other Tasks

| Task | Relationship |
|------|-------------|
| ISA-001 (v3 full draft) | Compressed format is an optional v3 feature; requires v3 VM support |
| ISA-002 (escape prefix) | C.EXT provides zero-overhead access to extensions in compressed mode; C.ESCAPE falls back to normal escape prefix |
| SEC-001 (security primitives) | Compressed instructions carry same security semantics; C.ESCAPE introduces normal instructions that must pass bytecode verification |
| ASYNC-001 (async primitives) | Async/temporal opcodes accessible via C.EXT (ext_id=6) or C.ESCAPE |
| TEMP-001 (temporal primitives) | Same as ASYNC-001 — via C.EXT or C.ESCAPE |
| PERF-001 (benchmarks) | Compressed mode should be benchmarked separately; decode throughput expected to improve (fixed 2-byte fetch) |
| TASK-BOARD ISA-003 | This document directly addresses ISA-003 |

### B.1 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0-draft | 2026-04-12 | Super Z | Initial draft — 4 compressed formats, 48 defined opcodes, 10 conformance vectors |

### B.2 Open Questions

1. **Should compressed mode support alignment padding?** When a label requires non-2-byte-aligned positioning, should the assembler insert NOPs? Proposed: yes, insert C.NOP (0x08 0x00) for padding.

2. **Should CJ offsets be in compressed-instruction units or byte units?** This spec uses compressed-instruction units (each unit = 2 bytes). Alternative: byte units would allow odd offsets. Proposed: keep instruction units (simpler mental model, matches RISC-V C-extension).

3. **Should there be a C.MOVI16 for medium-range immediates?** A hypothetical `C.MOVI16 rd, imm5` where imm5 is used as an index into a 32-entry constant pool could provide 16-bit immediate loads in 2 bytes + constant pool. Proposed: defer to future revision — C.ESCAPE + MOVI16 is sufficient.

4. **Should compressed mode support a secondary escape for EXT_EDGE sensor ops?** Edge programs frequently use sensor ops. A dedicated CR opcode for SENSOR_READ (bypassing C.EXT) would save bytes. Proposed: defer — C.EXT covers ext_id=2 (EXT_EDGE).

---

*End of document*
