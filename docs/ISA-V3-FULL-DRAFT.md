# FLUX ISA v3.0 — Full Specification Draft

**Document ID:** ISA-001-FULL  
**Author:** Super Z (FLUX Fleet — Cartographer)  
**Date:** 2026-04-12  
**Status:** DRAFT — Requires fleet review and Oracle1 approval  
**Version:** 2.0.0-draft  
**Depends on:** ISA v2 unified spec (247 opcodes, `isa_unified.py`), `formats.py`  
**Tracks:** Oracle1 TASK-BOARD ISA-001 (CRITICAL PATH)  
**Resolves:** Slot overlap between SEC-001 (security) and ASYNC-001/TEMP-001 (async/temporal)  
**Supersedes:** All prior individual spec drafts (ISA-V3-DRAFT.md, isa-v3-escape-prefix-spec.md, isa-v3-address-map.md, security-primitives-spec.md, async-temporal-primitives-spec.md)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [V2 → V3 Migration Guide](#2-v2--v3-migration-guide)
3. [Instruction Encoding](#3-instruction-encoding)
   - 3.1 [Format A — Zero-Operand](#31-format-a--zero-operand)
   - 3.2 [Format B — Single Register](#32-format-b--single-register)
   - 3.3 [Format C — Immediate-Only](#33-format-c--immediate-only)
   - 3.4 [Format D — Register + Imm8](#34-format-d--register--imm8)
   - 3.5 [Format E — Three-Register](#35-format-e--three-register)
   - 3.6 [Format F — Register + Imm16](#36-format-f--register--imm16)
   - 3.7 [Format G — Two-Register + Imm16](#37-format-g--two-register--imm16)
   - 3.8 [Format H — Escape Prefix (v3 NEW)](#38-format-h--escape-prefix-v3-new)
4. [Complete Opcode Table](#4-complete-opcode-table)
   - 4.1 [System Control (0x00–0x07)](#41-system-control-0x00-0x07)
   - 4.2 [Single Register (0x08–0x0F)](#42-single-register-0x08-0x0f)
   - 4.3 [Immediate-Only (0x10–0x17)](#43-immediate-only-0x10-0x17)
   - 4.4 [Register + Imm8 (0x18–0x1F)](#44-register--imm8-0x18-0x1f)
   - 4.5 [Integer Arithmetic + Comparison (0x20–0x2F)](#45-integer-arithmetic--comparison-0x20-0x2f)
   - 4.6 [Float, Memory, Control Flow (0x30–0x3F)](#46-float-memory-control-flow-0x30-0x3f)
   - 4.7 [Register + Imm16 (0x40–0x47)](#47-register--imm16-0x40-0x47)
   - 4.8 [Register + Register + Imm16 (0x48–0x4F)](#48-register--register--imm16-0x48-0x4f)
   - 4.9 [A2A/Signaling (0x50–0x5F)](#49-a2asignaling-0x50-0x5f)
   - 4.10 [Confidence-Aware (0x60–0x6F)](#410-confidence-aware-0x60-0x6f)
   - 4.11 [Viewpoint / Babel Domain (0x70–0x7F)](#411-viewpoint--babel-domain-0x70-0x7f)
   - 4.12 [Sensor / JetsonClaw1 Domain (0x80–0x8F)](#412-sensor--jetsonclaw1-domain-0x80-0x8f)
   - 4.13 [Extended Math + Crypto (0x90–0x9F)](#413-extended-math--crypto-0x90-0x9f)
   - 4.14 [String/Collection (0xA0–0xAF)](#414-stringcollection-0xa0-0xaf)
   - 4.15 [Vector/SIMD (0xB0–0xBF)](#415-vectorsimd-0xb0-0xbf)
   - 4.16 [Tensor/Neural (0xC0–0xCF)](#416-tensorneural-0xc0-0xcf)
   - 4.17 [Memory/MMIO/GPU (0xD0–0xDF)](#417-memorymmiogpu-0xd0-0xdf)
   - 4.18 [Long Jump/Coroutine/Fault (0xE0–0xEF)](#418-long-jumpcoroutinefault-0xe0-0xef)
   - 4.19 [Extended System (0xF0–0xFF)](#419-extended-system-0xf0-0xff)
   - 4.20 [Extension Opcodes via 0xFF](#420-extension-opcodes-via-0xff)
5. [Register Model](#5-register-model)
6. [Extension Protocol](#6-extension-protocol)
7. [Confidence Model](#7-confidence-model)
8. [Security Model](#8-security-model)
9. [Conformance Vectors](#9-conformance-vectors)
10. [Implementation Status](#10-implementation-status)
11. [Appendix A — Encoding Examples](#appendix-a--encoding-examples)
12. [Appendix B — Cross-References](#appendix-b--cross-references)

---

## 1. Executive Summary

FLUX ISA v3 is an evolutionary upgrade to the converged v2 specification (247 opcodes). It preserves 100% backward compatibility — every valid v2 program runs unmodified on a v3 VM — while adding three major capabilities demanded by the fleet's growing requirements:

- **Unbounded extensibility** via the `0xFF` escape prefix, enabling domain-specific operations (linguistics, sensors, tensors) without exhausting base-ISA slots. A single escape byte opens 65,536 extension opcodes (256 extensions × 256 sub-opcodes each).
- **Hardware-grade security** through 6 new ISA opcodes at previously reserved slots plus interpreter-level capability-gated dispatch (CAP_INVOKE), 4-stage bytecode verification, memory tagging, sandbox regions, and mandatory confidence sanitization that together resolve fleet issues #15 (zero verification), #16 (unenforced CAP opcodes), and #17 (NaN trust poisoning).
- **Async/temporal execution** via the EXT_TEMPORAL extension (ID 0x06) providing SUSPEND/RESUME continuation handoff, DEADLINE_BEFORE time budgets, YIELD_IF_CONTENTION cooperative contention avoidance, PERSIST_CRITICAL_STATE for crash recovery, and TICKS_ELAPSED for temporal confidence tracking.

The key architectural insight: security primitives occupy direct base-ISA slots (cannot be stripped), while async/temporal primitives live as extensions (can gracefully degrade). A slot overlap between the two specs was resolved in favor of security for the base slots, with async/temporal relocated to the escape prefix space where they have more room (11 sub-opcodes vs the original 7 reserved slots).

**Who benefits:** Runtime implementers gain a single source of truth with 253 base + 65,536 extension opcodes. Fleet agents writing A2A protocols get sandbox isolation and capability enforcement. Edge deployments (JetsonClaw1) get sensor fusion extensions. Babel gets linguistic primitives. All agents benefit from confidence sanitization preventing trust poisoning attacks.

---

## 2. V2 → V3 Migration Guide

### 2.1 Breaking Changes

| # | Change | v2 Behavior | v3 Behavior | Action Required |
|---|--------|-------------|-------------|-----------------|
| 1 | `0xFF` reclassified | ILLEGAL → trap to fault handler | ESCAPE_PREFIX → dispatch to extension table | No action for v2 programs (0xFF never appears in valid v2 bytecode) |
| 2 | `0xDF` reclaimed | Reserved (Format G) | SANDBOX_ALLOC (security, Format G) | No action — was reserved |
| 3 | `0xED` reclaimed | Reserved (Format F) | SANDBOX_FREE (security, Format G) | No action — was reserved |
| 4 | `0xEE` reclaimed | Reserved (Format F) | TAG_ALLOC (security, Format F) | No action — was reserved |
| 5 | `0xEF` reclaimed | Reserved (Format F) | TAG_TRANSFER (security, Format F) | No action — was reserved |
| 6 | `0xFA` reclaimed | Reserved (Format A) | CONF_CLAMP (security, Format A) | No action — was reserved |
| 7 | `0xFB` reclaimed | Reserved (Format A) | TAG_CHECK (security, Format A) | No action — was reserved |
| 8 | VER returns 3 | `0xF5` → R0 = 2 | `0xF5` → R0 = 3 | Code that checks `VER == 2` should accept `VER >= 2` |
| 9 | Security flags register | Not present | 6-bit write-clear register | No action — additive; read via HALT_ERR handler |
| 10 | Confidence sanitization | No clamping | NaN/Inf → 0.0, clamp to [0.0, 1.0] | Agents relying on NaN/Inf propagation must use new confidence model |
| 11 | Mandatory bytecode verification (A2A) | Not enforced | 4-stage pipeline required for received bytecode | Senders must ensure bytecode is well-formed |

### 2.2 Non-Breaking Additions

- 3 reserved slots remain (0xFC, 0xFD, 0xFE) for future use
- 65,536 extension opcodes via Format H
- All 247 v2 opcode addresses unchanged
- All v2 formats (A–G) unchanged
- Register file unchanged (R0–R15 general + C0–C15 confidence)

### 2.3 Forward Compatibility Pattern

v3 programs should check ISA version and extension availability before using new features:

```asm
; Check ISA version
VER                      ; 0xF5, R0 = ISA version
MOVI R1, 3
CMP_LT R2, R0, R1        ; R2 = (R0 < 3), i.e., running on v2
JNZ R2, base_only        ; jump to base-only code path

; v3 path: check extension availability
0xFF 0xF0 0x01           ; VER_EXT for EXT_BABEL
MOVI R1, 1
CMP_EQ R3, R0, R1
JZ R3, no_babel
; Extension code here...
JMP continue
no_babel:
; Fallback code here...
base_only:
; Base ISA code only...
continue:
```

### 2.4 Runtime Implementer Checklist

1. Change ILLEGAL (0xFF) handler to escape prefix dispatcher
2. Add extension table initialization (at minimum: NULL extension at 0x00)
3. Implement VER_EXT meta-extension (0xFF 0xF0)
4. Add CAPS message handling in A2A layer
5. Implement 6 security opcodes (SANDBOX_ALLOC/FREE, TAG_ALLOC/TRANSFER, CONF_CLAMP, TAG_CHECK)
6. Add CAP_INVOKE capability-gated dispatch for privileged opcodes
7. Add 4-stage bytecode verification for A2A-received code
8. Add `sanitize_confidence()` on all confidence register writes
9. Update VER (0xF5) to return 3
10. Add conformance vectors for escape prefix (7 vectors) + security (18 vectors) + async/temporal (15 vectors)

---

## 3. Instruction Encoding

### 3.1 Format A — Zero-Operand

```
Byte 0: opcode
Size: 1 byte
```

| Bit 7 | Bits 6-0 |
|-------|----------|
| opcode[7] | opcode[6:0] |

**Opcodes:** 0x00–0x07 (system), 0xF0–0xFB (extended system/security)

### 3.2 Format B — Single Register

```
Byte 0: opcode
Byte 1: rd (destination register)
Size: 2 bytes
```

| Byte 0 | Byte 1 |
|--------|--------|
| opcode | rd[7:0] |

**Opcodes:** 0x08–0x0F (INC, DEC, NOT, NEG, PUSH, POP, CONF_LD, CONF_ST)

### 3.3 Format C — Immediate-Only

```
Byte 0: opcode
Byte 1: imm8 (8-bit unsigned immediate)
Size: 2 bytes
```

| Byte 0 | Byte 1 |
|--------|--------|
| opcode | imm8[7:0] |

**Opcodes:** 0x10–0x17 (SYS, TRAP, DBG, CLF, SEMA, YIELD, CACHE, STRIPCF)

### 3.4 Format D — Register + Imm8

```
Byte 0: opcode
Byte 1: rd (destination register)
Byte 2: imm8 (8-bit unsigned immediate)
Size: 3 bytes
```

| Byte 0 | Byte 1 | Byte 2 |
|--------|--------|--------|
| opcode | rd[7:0] | imm8[7:0] |

**Opcodes:** 0x18–0x1F (MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI), 0x69 (C_THRESH), 0xA0 (LEN)

### 3.5 Format E — Three-Register

```
Byte 0: opcode
Byte 1: rd  (destination register)
Byte 2: rs1 (source register 1)
Byte 3: rs2 (source register 2)
Size: 4 bytes
```

| Byte 0 | Byte 1 | Byte 2 | Byte 3 |
|--------|--------|--------|--------|
| opcode | rd[7:0] | rs1[7:0] | rs2[7:0] |

**Opcodes:** 0x20–0x6F, 0x80–0xCF (arithmetic, logic, comparison, float, memory, control flow, A2A, confidence, viewpoint, sensor, math, crypto, collection, vector, tensor)

### 3.6 Format F — Register + Imm16

```
Byte 0: opcode
Byte 1: rd       (destination register)
Byte 2: imm16_hi (high byte of 16-bit immediate)
Byte 3: imm16_lo (low byte of 16-bit immediate)
Size: 4 bytes (little-endian)
```

| Byte 0 | Byte 1 | Byte 2 | Byte 3 |
|--------|--------|--------|--------|
| opcode | rd[7:0] | imm16[15:8] | imm16[7:0] |

**Opcodes:** 0x40–0x47 (MOVI16, ADDI16, SUBI16, JMP, JAL, CALL, LOOP, SELECT), 0xE0–0xEC (JMPL, JALL, CALLL, TAIL, SWITCH, COYIELD, CORESUM, FAULT, HANDLER, TRACE, PROF_ON, PROF_OFF, WATCH), 0xEE–0xEF (TAG_ALLOC, TAG_TRANSFER)

### 3.7 Format G — Two-Register + Imm16

```
Byte 0: opcode
Byte 1: rd       (destination register)
Byte 2: rs1      (source register 1)
Byte 3: imm16_hi (high byte of 16-bit immediate)
Byte 4: imm16_lo (low byte of 16-bit immediate)
Size: 5 bytes (little-endian)
```

| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 |
|--------|--------|--------|--------|--------|
| opcode | rd[7:0] | rs1[7:0] | imm16[15:8] | imm16[7:0] |

**Opcodes:** 0x48–0x4F (LOADOFF, STOREOFF, LOADI, STOREI, ENTER, LEAVE, COPY, FILL), 0xA4 (SLICE), 0xD0–0xDF (DMA_CPY through SANDBOX_ALLOC), 0xED (SANDBOX_FREE)

### 3.8 Format H — Escape Prefix (v3 NEW)

```
Byte 0: 0xFF              (escape prefix — always this value)
Byte 1: ext_id            (extension identifier, 0x00–0xFF)
Byte 2: sub_opcode        (operation within extension, 0x00–0xFF)
Byte 3+: operands         (format determined by extension's sub-opcode map)
Size: 3–8 bytes
```

| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7 |
|--------|--------|--------|--------|--------|--------|--------|--------|
| 0xFF | ext_id | sub | rd | rs1 | rs2 | imm16_hi | imm16_lo |

**Operand formats after prefix:** Extensions declare which base format (A–G) applies. The VM reads operands identically to a base-ISA instruction of that format (Pattern A — reuse base formats).

| Extension operand format | Total bytes |
|--------------------------|-------------|
| None (Format A) | 3 |
| Format B | 4 |
| Format D | 5 |
| Format E | 6 |
| Format F | 6 |
| Format G | 7 |

**Addressing capacity:** 256 extensions × 256 sub-opcodes = **65,536 extension opcodes**

---

## 4. Complete Opcode Table

### 4.1 System Control (0x00–0x07) — Format A

| Hex | Mnemonic | Fmt | Operands | Description |
|-----|----------|-----|----------|-------------|
| 0x00 | HALT | A | — | Stop execution |
| 0x01 | NOP | A | — | No operation (pipeline sync) |
| 0x02 | RET | A | — | Return from subroutine |
| 0x03 | IRET | A | — | Return from interrupt handler |
| 0x04 | BRK | A | — | Breakpoint (trap to debugger) |
| 0x05 | WFI | A | — | Wait for interrupt (low-power idle) |
| 0x06 | RESET | A | — | Soft reset of register file |
| 0x07 | SYN | A | — | Memory barrier / synchronize |

### 4.2 Single Register (0x08–0x0F) — Format B

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x08 | INC | B | rd | arithmetic | rd = rd + 1 |
| 0x09 | DEC | B | rd | arithmetic | rd = rd − 1 |
| 0x0A | NOT | B | rd | logic | rd = ~rd (bitwise NOT) |
| 0x0B | NEG | B | rd | arithmetic | rd = −rd (arithmetic negate) |
| 0x0C | PUSH | B | rd | stack | Push rd onto stack |
| 0x0D | POP | B | rd | stack | Pop stack into rd |
| 0x0E | CONF_LD | B | rd | confidence | Load confidence register rd |
| 0x0F | CONF_ST | B | rd | confidence | Store confidence to register rd |

### 4.3 Immediate-Only (0x10–0x17) — Format C

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x10 | SYS | C | imm8 | system | System call with code imm8 |
| 0x11 | TRAP | C | imm8 | system | Software interrupt vector imm8 |
| 0x12 | DBG | C | imm8 | debug | Debug print register imm8 |
| 0x13 | CLF | C | imm8 | system | Clear flags register bits imm8 |
| 0x14 | SEMA | C | imm8 | concurrency | Semaphore operation imm8 |
| 0x15 | YIELD | C | imm8 | concurrency | Yield execution for imm8 cycles |
| 0x16 | CACHE | C | imm8 | system | Cache control (flush/invalidate) |
| 0x17 | STRIPCF | C | imm8 | confidence | Strip confidence from next imm8 ops |

### 4.4 Register + Imm8 (0x18–0x1F) — Format D

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x18 | MOVI | D | rd, imm8 | move | rd = sign_extend(imm8) |
| 0x19 | ADDI | D | rd, imm8 | arithmetic | rd = rd + imm8 |
| 0x1A | SUBI | D | rd, imm8 | arithmetic | rd = rd − imm8 |
| 0x1B | ANDI | D | rd, imm8 | logic | rd = rd & imm8 |
| 0x1C | ORI | D | rd, imm8 | logic | rd = rd \| imm8 |
| 0x1D | XORI | D | rd, imm8 | logic | rd = rd ^ imm8 |
| 0x1E | SHLI | D | rd, imm8 | shift | rd = rd << imm8 |
| 0x1F | SHRI | D | rd, imm8 | shift | rd = rd >> imm8 |

### 4.5 Integer Arithmetic + Comparison (0x20–0x2F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x20 | ADD | E | rd, rs1, rs2 | arithmetic | rd = rs1 + rs2 |
| 0x21 | SUB | E | rd, rs1, rs2 | arithmetic | rd = rs1 − rs2 |
| 0x22 | MUL | E | rd, rs1, rs2 | arithmetic | rd = rs1 × rs2 |
| 0x23 | DIV | E | rd, rs1, rs2 | arithmetic | rd = rs1 / rs2 (signed) |
| 0x24 | MOD | E | rd, rs1, rs2 | arithmetic | rd = rs1 % rs2 |
| 0x25 | AND | E | rd, rs1, rs2 | logic | rd = rs1 & rs2 |
| 0x26 | OR | E | rd, rs1, rs2 | logic | rd = rs1 \| rs2 |
| 0x27 | XOR | E | rd, rs1, rs2 | logic | rd = rs1 ^ rs2 |
| 0x28 | SHL | E | rd, rs1, rs2 | shift | rd = rs1 << rs2 |
| 0x29 | SHR | E | rd, rs1, rs2 | shift | rd = rs1 >> rs2 |
| 0x2A | MIN | E | rd, rs1, rs2 | arithmetic | rd = min(rs1, rs2) |
| 0x2B | MAX | E | rd, rs1, rs2 | arithmetic | rd = max(rs1, rs2) |
| 0x2C | CMP_EQ | E | rd, rs1, rs2 | comparison | rd = (rs1 == rs2) ? 1 : 0 |
| 0x2D | CMP_LT | E | rd, rs1, rs2 | comparison | rd = (rs1 < rs2) ? 1 : 0 |
| 0x2E | CMP_GT | E | rd, rs1, rs2 | comparison | rd = (rs1 > rs2) ? 1 : 0 |
| 0x2F | CMP_NE | E | rd, rs1, rs2 | comparison | rd = (rs1 != rs2) ? 1 : 0 |

### 4.6 Float, Memory, Control Flow (0x30–0x3F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x30 | FADD | E | rd, rs1, rs2 | float | rd = f(rs1) + f(rs2) |
| 0x31 | FSUB | E | rd, rs1, rs2 | float | rd = f(rs1) − f(rs2) |
| 0x32 | FMUL | E | rd, rs1, rs2 | float | rd = f(rs1) × f(rs2) |
| 0x33 | FDIV | E | rd, rs1, rs2 | float | rd = f(rs1) / f(rs2) |
| 0x34 | FMIN | E | rd, rs1, rs2 | float | rd = fmin(rs1, rs2) |
| 0x35 | FMAX | E | rd, rs1, rs2 | float | rd = fmax(rs1, rs2) |
| 0x36 | FTOI | E | rd, rs1, — | convert | rd = int(f(rs1)) |
| 0x37 | ITOF | E | rd, rs1, — | convert | rd = float(rs1) |
| 0x38 | LOAD | E | rd, rs1, rs2 | memory | rd = mem[rs1 + rs2] |
| 0x39 | STORE | E | rd, rs1, rs2 | memory | mem[rs1 + rs2] = rd |
| 0x3A | MOV | E | rd, rs1, — | move | rd = rs1 |
| 0x3B | SWP | E | rd, rs1, — | move | swap(rd, rs1) |
| 0x3C | JZ | E | rd, rs1, — | control | if rd == 0: pc += rs1 |
| 0x3D | JNZ | E | rd, rs1, — | control | if rd != 0: pc += rs1 |
| 0x3E | JLT | E | rd, rs1, — | control | if rd < 0: pc += rs1 |
| 0x3F | JGT | E | rd, rs1, — | control | if rd > 0: pc += rs1 |

### 4.7 Register + Imm16 (0x40–0x47) — Format F

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x40 | MOVI16 | F | rd, imm16 | move | rd = imm16 |
| 0x41 | ADDI16 | F | rd, imm16 | arithmetic | rd = rd + imm16 |
| 0x42 | SUBI16 | F | rd, imm16 | arithmetic | rd = rd − imm16 |
| 0x43 | JMP | F | —, imm16 | control | pc += imm16 (relative) |
| 0x44 | JAL | F | rd, imm16 | control | rd = pc; pc += imm16 |
| 0x45 | CALL | F | rd, imm16 | control | push(pc); pc = rd + imm16 |
| 0x46 | LOOP | F | rd, imm16 | control | rd−−; if rd > 0: pc −= imm16 |
| 0x47 | SELECT | F | rd, imm16 | control | pc += imm16 × rd |

### 4.8 Register + Register + Imm16 (0x48–0x4F) — Format G

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x48 | LOADOFF | G | rd, rs1, imm16 | memory | rd = mem[rs1 + imm16] |
| 0x49 | STOREOFF | G | rd, rs1, imm16 | memory | mem[rs1 + imm16] = rd |
| 0x4A | LOADI | G | rd, rs1, imm16 | memory | rd = mem[mem[rs1] + imm16] |
| 0x4B | STOREI | G | rd, rs1, imm16 | memory | mem[mem[rs1] + imm16] = rd |
| 0x4C | ENTER | G | rd, rs1, imm16 | stack | push regs; sp −= imm16 |
| 0x4D | LEAVE | G | rd, rs1, imm16 | stack | sp += imm16; pop regs |
| 0x4E | COPY | G | rd, rs1, imm16 | memory | memcpy(rd, rs1, imm16) |
| 0x4F | FILL | G | rd, rs1, imm16 | memory | memset(rd, rs1, imm16) |

### 4.9 A2A/Signaling (0x50–0x5F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x50 | TELL | E | rd, rs1, rs2 | a2a | Send rs2 to agent rs1 |
| 0x51 | ASK | E | rd, rs1, rs2 | a2a | Request rs2 from agent rs1 |
| 0x52 | DELEG | E | rd, rs1, rs2 | a2a | Delegate task rs2 to agent rs1 |
| 0x53 | BCAST | E | rd, rs1, rs2 | a2a | Broadcast rs2 to fleet |
| 0x54 | ACCEPT | E | rd, rs1, rs2 | a2a | Accept delegated task |
| 0x55 | DECLINE | E | rd, rs1, rs2 | a2a | Decline task with reason rs2 |
| 0x56 | REPORT | E | rd, rs1, rs2 | a2a | Report task status rs2 to rd |
| 0x57 | MERGE | E | rd, rs1, rs2 | a2a | Merge results from rs1, rs2 |
| 0x58 | FORK | E | rd, rs1, rs2 | a2a | Spawn child agent, state→rd |
| 0x59 | JOIN | E | rd, rs1, rs2 | a2a | Wait for child rs1, result→rd |
| 0x5A | SIGNAL | E | rd, rs1, rs2 | a2a | Emit signal rs2 on channel rd |
| 0x5B | AWAIT | E | rd, rs1, rs2 | a2a | Wait for signal rs2, data→rd |
| 0x5C | TRUST | E | rd, rs1, rs2 | a2a | Set trust level rs2 for agent rs1 |
| 0x5D | DISCOV | E | rd, rs1, rs2 | a2a | Discover fleet agents |
| 0x5E | STATUS | E | rd, rs1, rs2 | a2a | Query agent rs1 status |
| 0x5F | HEARTBT | E | rd, rs1, rs2 | a2a | Emit heartbeat |

### 4.10 Confidence-Aware (0x60–0x6F) — Mixed E/D

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x60 | C_ADD | E | rd, rs1, rs2 | confidence | rd = rs1+rs2, crd=min(crs1,crs2) |
| 0x61 | C_SUB | E | rd, rs1, rs2 | confidence | rd = rs1−rs2, crd=min(crs1,crs2) |
| 0x62 | C_MUL | E | rd, rs1, rs2 | confidence | rd = rs1×rs2, crd=crs1×crs2 |
| 0x63 | C_DIV | E | rd, rs1, rs2 | confidence | rd = rs1/rs2, crd=crs1×crs2×(1−ε) |
| 0x64 | C_FADD | E | rd, rs1, rs2 | confidence | Float add + confidence |
| 0x65 | C_FSUB | E | rd, rs1, rs2 | confidence | Float sub + confidence |
| 0x66 | C_FMUL | E | rd, rs1, rs2 | confidence | Float mul + confidence |
| 0x67 | C_FDIV | E | rd, rs1, rs2 | confidence | Float div + confidence |
| 0x68 | C_MERGE | E | rd, rs1, rs2 | confidence | Merge confidences: crd=weighted_avg |
| 0x69 | C_THRESH | D | rd, imm8 | confidence | Skip next if crd < imm8/255 |
| 0x6A | C_BOOST | E | rd, rs1, rs2 | confidence | Boost crd by rs2 (max 1.0) |
| 0x6B | C_DECAY | E | rd, rs1, rs2 | confidence | Decay crd by rs2 per cycle |
| 0x6C | C_SOURCE | E | rd, rs1, rs2 | confidence | Set confidence source type |
| 0x6D | C_CALIB | E | rd, rs1, rs2 | confidence | Calibrate vs ground truth |
| 0x6E | C_EXPLY | E | rd, rs1, rs2 | confidence | Apply confidence to control flow |
| 0x6F | C_VOTE | E | rd, rs1, rs2 | confidence | Weighted vote |

### 4.11 Viewpoint / Babel Domain (0x70–0x7F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x70 | V_EVID | E | rd, rs1, rs2 | viewpoint | Evidentiality: source type |
| 0x71 | V_EPIST | E | rd, rs1, rs2 | viewpoint | Epistemic stance |
| 0x72 | V_MIR | E | rd, rs1, rs2 | viewpoint | Mirative: unexpectedness |
| 0x73 | V_NEG | E | rd, rs1, rs2 | viewpoint | Negation scope |
| 0x74 | V_TENSE | E | rd, rs1, rs2 | viewpoint | Temporal viewpoint |
| 0x75 | V_ASPEC | E | rd, rs1, rs2 | viewpoint | Aspectual viewpoint |
| 0x76 | V_MODAL | E | rd, rs1, rs2 | viewpoint | Modal force |
| 0x77 | V_POLIT | E | rd, rs1, rs2 | viewpoint | Politeness register |
| 0x78 | V_HONOR | E | rd, rs1, rs2 | viewpoint | Honorific → trust tier |
| 0x79 | V_TOPIC | E | rd, rs1, rs2 | viewpoint | Topic-comment structure |
| 0x7A | V_FOCUS | E | rd, rs1, rs2 | viewpoint | Information focus |
| 0x7B | V_CASE | E | rd, rs1, rs2 | viewpoint | Case-based scope |
| 0x7C | V_AGREE | E | rd, rs1, rs2 | viewpoint | Agreement |
| 0x7D | V_CLASS | E | rd, rs1, rs2 | viewpoint | Classifier → type |
| 0x7E | V_INFL | E | rd, rs1, rs2 | viewpoint | Inflection → control flow |
| 0x7F | V_PRAGMA | E | rd, rs1, rs2 | viewpoint | Pragmatic context switch |

### 4.12 Sensor / JetsonClaw1 Domain (0x80–0x8F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x80 | SENSE | E | rd, rs1, rs2 | sensor | Read sensor |
| 0x81 | ACTUATE | E | rd, rs1, rs2 | sensor | Write actuator |
| 0x82 | SAMPLE | E | rd, rs1, rs2 | sensor | Sample ADC |
| 0x83 | ENERGY | E | rd, rs1, rs2 | sensor | Energy budget |
| 0x84 | TEMP | E | rd, rs1, rs2 | sensor | Temperature |
| 0x85 | GPS | E | rd, rs1, rs2 | sensor | GPS coordinates |
| 0x86 | ACCEL | E | rd, rs1, rs2 | sensor | Accelerometer |
| 0x87 | DEPTH | E | rd, rs1, rs2 | sensor | Depth/pressure |
| 0x88 | CAMCAP | E | rd, rs1, rs2 | sensor | Camera capture |
| 0x89 | CAMDET | E | rd, rs1, rs2 | sensor | Detection |
| 0x8A | PWM | E | rd, rs1, rs2 | sensor | PWM output |
| 0x8B | GPIO | E | rd, rs1, rs2 | sensor | GPIO |
| 0x8C | I2C | E | rd, rs1, rs2 | sensor | I2C communication |
| 0x8D | SPI | E | rd, rs1, rs2 | sensor | SPI communication |
| 0x8E | UART | E | rd, rs1, rs2 | sensor | UART communication |
| 0x8F | CANBUS | E | rd, rs1, rs2 | sensor | CAN bus |

### 4.13 Extended Math + Crypto (0x90–0x9F) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0x90 | ABS | E | rd, rs1, — | math | rd = \|rs1\| |
| 0x91 | SIGN | E | rd, rs1, — | math | rd = sign(rs1) |
| 0x92 | SQRT | E | rd, rs1, — | math | rd = sqrt(rs1) |
| 0x93 | POW | E | rd, rs1, rs2 | math | rd = rs1 ^ rs2 |
| 0x94 | LOG2 | E | rd, rs1, — | math | rd = log2(rs1) |
| 0x95 | CLZ | E | rd, rs1, — | math | Count leading zeros |
| 0x96 | CTZ | E | rd, rs1, — | math | Count trailing zeros |
| 0x97 | POPCNT | E | rd, rs1, — | math | Population count |
| 0x98 | CRC32 | E | rd, rs1, rs2 | crypto | CRC32 hash |
| 0x99 | SHA256 | E | rd, rs1, rs2 | crypto | SHA-256 block |
| 0x9A | RND | E | rd, rs1, rs2 | math | Random in [rs1, rs2] |
| 0x9B | SEED | E | rd, rs1, — | math | Seed PRNG |
| 0x9C | FMOD | E | rd, rs1, rs2 | float | Float modulo |
| 0x9D | FSQRT | E | rd, rs1, — | float | Float square root |
| 0x9E | FSIN | E | rd, rs1, — | float | Sine |
| 0x9F | FCOS | E | rd, rs1, — | float | Cosine |

### 4.14 String/Collection (0xA0–0xAF) — Mixed D/E/G

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xA0 | LEN | D | rd, imm8 | collection | Length of collection |
| 0xA1 | CONCAT | E | rd, rs1, rs2 | collection | Concatenate |
| 0xA2 | AT | E | rd, rs1, rs2 | collection | Index |
| 0xA3 | SETAT | E | rd, rs1, rs2 | collection | Set element |
| 0xA4 | SLICE | G | rd, rs1, imm16 | collection | Slice |
| 0xA5 | REDUCE | E | rd, rs1, rs2 | collection | Fold |
| 0xA6 | MAP | E | rd, rs1, rs2 | collection | Map |
| 0xA7 | FILTER | E | rd, rs1, rs2 | collection | Filter |
| 0xA8 | SORT | E | rd, rs1, rs2 | collection | Sort |
| 0xA9 | FIND | E | rd, rs1, rs2 | collection | Find index |
| 0xAA | HASH | E | rd, rs1, rs2 | crypto | Hash |
| 0xAB | HMAC | E | rd, rs1, rs2 | crypto | HMAC signature |
| 0xAC | VERIFY | E | rd, rs1, rs2 | crypto | Verify signature |
| 0xAD | ENCRYPT | E | rd, rs1, rs2 | crypto | Encrypt |
| 0xAE | DECRYPT | E | rd, rs1, rs2 | crypto | Decrypt |
| 0xAF | KEYGEN | E | rd, rs1, rs2 | crypto | Generate keypair |

### 4.15 Vector/SIMD (0xB0–0xBF) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xB0 | VLOAD | E | rd, rs1, rs2 | vector | Load vector |
| 0xB1 | VSTORE | E | rd, rs1, rs2 | vector | Store vector |
| 0xB2 | VADD | E | rd, rs1, rs2 | vector | Vector add |
| 0xB3 | VMUL | E | rd, rs1, rs2 | vector | Vector multiply |
| 0xB4 | VDOT | E | rd, rs1, rs2 | vector | Dot product |
| 0xB5 | VNORM | E | rd, rs1, rs2 | vector | L2 norm |
| 0xB6 | VSCALE | E | rd, rs1, rs2 | vector | Scalar multiply |
| 0xB7 | VMAXP | E | rd, rs1, rs2 | vector | Element-wise max |
| 0xB8 | VMINP | E | rd, rs1, rs2 | vector | Element-wise min |
| 0xB9 | VREDUCE | E | rd, rs1, rs2 | vector | Reduce |
| 0xBA | VGATHER | E | rd, rs1, rs2 | vector | Gather load |
| 0xBB | VSCATTER | E | rd, rs1, rs2 | vector | Scatter store |
| 0xBC | VSHUF | E | rd, rs1, rs2 | vector | Shuffle lanes |
| 0xBD | VMERGE | E | rd, rs1, rs2 | vector | Merge by mask |
| 0xBE | VCONF | E | rd, rs1, rs2 | vector | Vector confidence |
| 0xBF | VSELECT | E | rd, rs1, rs2 | vector | Conditional select |

### 4.16 Tensor/Neural (0xC0–0xCF) — Format E

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xC0 | TMATMUL | E | rd, rs1, rs2 | tensor | Matrix multiply |
| 0xC1 | TCONV | E | rd, rs1, rs2 | tensor | 2D convolution |
| 0xC2 | TPOOL | E | rd, rs1, rs2 | tensor | Max/avg pool |
| 0xC3 | TRELU | E | rd, rs1, — | tensor | ReLU activation |
| 0xC4 | TSIGM | E | rd, rs1, — | tensor | Sigmoid |
| 0xC5 | TSOFT | E | rd, rs1, rs2 | tensor | Softmax |
| 0xC6 | TLOSS | E | rd, rs1, rs2 | tensor | Loss function |
| 0xC7 | TGRAD | E | rd, rs1, rs2 | tensor | Gradient |
| 0xC8 | TUPDATE | E | rd, rs1, rs2 | tensor | SGD update |
| 0xC9 | TADAM | E | rd, rs1, rs2 | tensor | Adam optimizer |
| 0xCA | TEMBED | E | rd, rs1, rs2 | tensor | Embedding lookup |
| 0xCB | TATTN | E | rd, rs1, rs2 | tensor | Self-attention |
| 0xCC | TSAMPLE | E | rd, rs1, rs2 | tensor | Sample from distribution |
| 0xCD | TTOKEN | E | rd, rs1, rs2 | tensor | Tokenize |
| 0xCE | TDETOK | E | rd, rs1, rs2 | tensor | Detokenize |
| 0xCF | TQUANT | E | rd, rs1, rs2 | tensor | Quantize |

### 4.17 Memory/MMIO/GPU (0xD0–0xDF) — Format G

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xD0 | DMA_CPY | G | rd, rs1, imm16 | memory | DMA copy |
| 0xD1 | DMA_SET | G | rd, rs1, imm16 | memory | DMA fill |
| 0xD2 | MMIO_R | G | rd, rs1, imm16 | memory | MMIO read |
| 0xD3 | MMIO_W | G | rd, rs1, imm16 | memory | MMIO write |
| 0xD4 | ATOMIC | G | rd, rs1, imm16 | memory | Atomic RMW |
| 0xD5 | CAS | G | rd, rs1, imm16 | memory | Compare-and-swap |
| 0xD6 | FENCE | G | rd, rs1, imm16 | memory | Memory fence |
| 0xD7 | MALLOC | G | rd, rs1, imm16 | memory | Allocate heap |
| 0xD8 | FREE | G | rd, rs1, imm16 | memory | Free heap |
| 0xD9 | MPROT | G | rd, rs1, imm16 | memory | Memory protect |
| 0xDA | MCACHE | G | rd, rs1, imm16 | memory | Cache management |
| 0xDB | GPU_LD | G | rd, rs1, imm16 | memory | GPU load |
| 0xDC | GPU_ST | G | rd, rs1, imm16 | memory | GPU store |
| 0xDD | GPU_EX | G | rd, rs1, imm16 | compute | GPU execute |
| 0xDE | GPU_SYNC | G | rd, rs1, imm16 | compute | GPU sync |
| 0xDF | **SANDBOX_ALLOC** | **G** | **rd, rs1, imm16** | **security** | **★ v3 NEW: Allocate sandbox region** |

### 4.18 Long Jump/Coroutine/Fault (0xE0–0xEF) — Mixed F/G

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xE0 | JMPL | F | rd, imm16 | control | Long relative jump |
| 0xE1 | JALL | F | rd, imm16 | control | Long jump-and-link |
| 0xE2 | CALLL | F | rd, imm16 | control | Long call |
| 0xE3 | TAIL | F | rd, imm16 | control | Tail call |
| 0xE4 | SWITCH | F | rd, imm16 | control | Context switch |
| 0xE5 | COYIELD | F | rd, imm16 | control | Coroutine yield |
| 0xE6 | CORESUM | F | rd, imm16 | control | Coroutine resume |
| 0xE7 | FAULT | F | rd, imm16 | system | Raise fault code |
| 0xE8 | HANDLER | F | rd, imm16 | system | Install fault handler |
| 0xE9 | TRACE | F | rd, imm16 | debug | Trace log |
| 0xEA | PROF_ON | F | rd, imm16 | debug | Start profiling |
| 0xEB | PROF_OFF | F | rd, imm16 | debug | End profiling |
| 0xEC | WATCH | F | rd, imm16 | debug | Watchpoint |
| 0xED | **SANDBOX_FREE** | **G** | **rd, imm16** | **security** | **★ v3 NEW: Release sandbox region** |
| 0xEE | **TAG_ALLOC** | **F** | **rd, imm16** | **security** | **★ v3 NEW: Tag memory with ownership** |
| 0xEF | **TAG_TRANSFER** | **F** | **rd, imm16** | **security** | **★ v3 NEW: Transfer tag ownership** |

### 4.19 Extended System (0xF0–0xFF) — Mixed A/B/H

| Hex | Mnemonic | Fmt | Operands | Category | Description |
|-----|----------|-----|----------|----------|-------------|
| 0xF0 | HALT_ERR | A | — | system | Halt with error |
| 0xF1 | REBOOT | A | — | system | Warm reboot |
| 0xF2 | DUMP | A | — | debug | Dump register file |
| 0xF3 | ASSERT | A | — | debug | Assert flags |
| 0xF4 | ID | A | — | system | Return agent ID to R0 |
| 0xF5 | VER | A | — | system | Return ISA version to R0 (v3→3) |
| 0xF6 | CLK | A | — | system | Clock cycle count → R0 |
| 0xF7 | PCLK | A | — | system | Performance counter |
| 0xF8 | WDOG | A | — | system | Watchdog timer |
| 0xF9 | SLEEP | A | — | system | Low-power sleep |
| 0xFA | **CONF_CLAMP** | **A** | **—** | **security** | **★ v3 NEW: Clamp confidence registers** |
| 0xFB | **TAG_CHECK** | **A** | **—** | **security** | **★ v3 NEW: Verify tag access** |
| 0xFC | — | — | — | reserved | Reserved |
| 0xFD | — | — | — | reserved | Reserved |
| 0xFE | — | — | — | reserved | Reserved |
| 0xFF | **ESCAPE** | **H** | **ext_id, sub, operands** | **system** | **★ v3 NEW: Escape prefix → extension** |

### 4.20 Extension Opcodes via 0xFF

#### 4.20.1 Extension ID Allocation

| Range | Count | Type | Authority |
|-------|-------|------|-----------|
| 0x00 | 1 | NULL (NOP passthrough) | Reserved |
| 0x01–0x7F | 127 | Fleet-standard | Oracle1 allocates |
| 0x80–0xEF | 112 | Experimental / vendor-specific | Self-assigned (register) |
| 0xF0–0xFF | 16 | Meta-extensions | Oracle1 reserves |

#### 4.20.2 EXT_NULL (0x00) — Passthrough

All 256 sub-opcodes are NOP. Enables bytecode padding and alignment.

#### 4.20.3 EXT_BABEL (0x01) — Multilingual Linguistics

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | LANG_DETECT | H_E | rd, rs1, rs2 | Detect language ID |
| 0x01 | LANG_CLASSIFY | H_E | rd, rs1, rs2 | Classify text category |
| 0x02 | TRANSLATE | H_E | rd, rs1, rs2 | Translate text |
| 0x03 | TOKENIZE | H_E | rd, rs1, rs2 | Tokenize text |
| 0x04 | MORPH_ANALYZE | H_E | rd, rs1, rs2 | Morphological analysis |
| 0x05 | SCRIPT_DET | H_E | rd, rs1, rs2 | Detect writing script |
| 0x06 | SENTIMENT | H_E | rd, rs1, rs2 | Sentiment analysis |
| 0x07 | ENT_EXTRACT | H_E | rd, rs1, rs2 | Named entity extraction |
| 0x08 | ALIGN_CROSS | H_E | rd, rs1, rs2 | Cross-lingual alignment |
| 0x09 | HONORIF_MAP | H_E | rd, rs1, rs2 | Honorific level mapping |
| 0x0A | VOCAB_LOOKUP | H_E | rd, rs1, rs2 | Vocabulary lookup |
| 0x0B | TRANSLIT | H_E | rd, rs1, rs2 | Transliterate between scripts |

#### 4.20.4 EXT_EDGE (0x02) — Sensor/Actuator/Edge

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | SENSOR_STREAM | H_E | rd, rs1, rs2 | Open sensor stream |
| 0x01 | FUSION_INIT | H_E | rd, rs1, rs2 | Initialize sensor fusion |
| 0x02 | FUSION_STEP | H_E | rd, rs1, rs2 | Run fusion step |
| 0x03 | MOTOR_CMD | H_E | rd, rs1, rs2 | Command motor |
| 0x04 | LIDAR_SCAN | H_E | rd, rs1, rs2 | Trigger LIDAR scan |
| 0x05 | GPS_FUSION | H_E | rd, rs1, rs2 | Fused GPS + IMU |
| 0x06 | CAM_STREAM | H_E | rd, rs1, rs2 | Camera stream |
| 0x07 | ACT_BATCH | H_E | rd, rs1, rs2 | Batch actuator command |
| 0x08 | SENSOR_CALIB | H_E | rd, rs1, rs2 | Calibrate sensor |
| 0x09 | POWER_BUDGET | H_E | rd, rs1, rs2 | Query power budget |
| 0x0A | THERMAL_MGT | H_E | rd, rs1, rs2 | Thermal management |
| 0x0B | DMA_CHAIN | H_G | rd, rs1, imm16 | DMA chained transfer |

#### 4.20.5 EXT_CONFIDENCE (0x03) — Advanced Confidence

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | CONF_DISTRIBUTION | H_E | rd, rs1, rs2 | Build confidence distribution |
| 0x01 | CONF_BAYES_UPDATE | H_E | rd, rs1, rs2 | Bayesian update |
| 0x02 | CONF_ENTROPY | H_E | rd, rs1, rs2 | Shannon entropy |
| 0x03 | CONF_CALIBRATE | H_E | rd, rs1, rs2 | Calibrate confidence model |
| 0x04 | CONF_ENSEMBLE | H_E | rd, rs1, rs2 | Ensemble confidence |
| 0x05 | CONF_DECAY_EXP | H_E | rd, rs1, rs2 | Exponential decay |
| 0x06 | CONF_FUSE_SENSOR | H_E | rd, rs1, rs2 | Fuse sensor + model confidence |
| 0x07 | CONF_THRESHOLD_VEC | H_E | rd, rs1, rs2 | Vector threshold |
| 0x08 | CONF_PROP_CHAIN | H_E | rd, rs1, rs2 | Propagate through chain |
| 0x09 | CONF_UNCERTAINTY | H_E | rd, rs1, rs2 | Quantify uncertainty |

#### 4.20.6 EXT_TENSOR (0x04) — Tensor/Neural Advanced

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | T_BATCHMATMUL | H_E | rd, rs1, rs2 | Batched matrix multiply |
| 0x01 | T_LAYER_NORM | H_E | rd, rs1, rs2 | Layer normalization |
| 0x02 | T_RESIDUAL | H_E | rd, rs1, rs2 | Residual connection |
| 0x03 | T_ATTENTION_FULL | H_E | rd, rs1, rs2 | Multi-head self-attention |
| 0x04 | T_CROSS_ATTENTION | H_E | rd, rs1, rs2 | Cross-attention |
| 0x05 | T_POSITIONAL | H_E | rd, rs1, rs2 | Positional encoding |
| 0x06 | T_CONV2D_STRIDE | H_E | rd, rs1, rs2 | 2D conv with stride |
| 0x07 | T_MAXPOOL2D | H_E | rd, rs1, rs2 | 2D max pooling |
| 0x08 | T_BATCH_NORM | H_E | rd, rs1, rs2 | Batch normalization |
| 0x09 | T_DROPOUT | H_E | rd, rs1, rs2 | Dropout |
| 0x0A | T_TOPK | H_E | rd, rs1, rs2 | Top-K selection |
| 0x0B | T_GATHER_SCATTER | H_E | rd, rs1, rs2 | Gather/scatter |
| 0x0C | T_QUANTIZE_QAT | H_E | rd, rs1, rs2 | QAT quantization |
| 0x0D | T_DEQUANTIZE | H_E | rd, rs1, rs2 | Dequantize |
| 0x0E | T_RESHAPE | H_E | rd, rs1, rs2 | Reshape tensor |
| 0x0F | T_CONCAT | H_E | rd, rs1, rs2 | Concatenate tensors |

#### 4.20.7 EXT_SECURITY (0x05) — Capability Enforcement

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | CAP_CHECK | H_E | rd, rs1, rs2 | Check capability |
| 0x01 | CAP_GRANT | H_E | rd, rs1, rs2 | Grant capability |
| 0x02 | CAP_REVOKE | H_E | rd, rs1, rs2 | Revoke capability |
| 0x03 | SANDBOX_CREATE | H_E | rd, rs1, rs2 | Create sandbox |
| 0x04 | SANDBOX_ENTER | H_E | rd, rs1, rs2 | Enter sandbox |
| 0x05 | SANDBOX_EXIT | H_E | rd, rs1, rs2 | Exit sandbox |
| 0x06 | MEM_TAG_SET | H_E | rd, rs1, rs2 | Tag memory region |
| 0x07 | MEM_TAG_CHECK | H_E | rd, rs1, rs2 | Verify memory tag |
| 0x08 | SEAL_DATA | H_E | rd, rs1, rs2 | Seal (encrypt+sign) data |
| 0x09 | UNSEAL_DATA | H_E | rd, rs1, rs2 | Unseal data |
| 0x0A | HASH_CHAIN | H_E | rd, rs1, rs2 | Add to hash chain |
| 0x0B | ATTEST_REQ | H_E | rd, rs1, rs2 | Request attestation |
| 0x0C | ATTEST_RESP | H_E | rd, rs1, rs2 | Process attestation |

#### 4.20.8 EXT_TEMPORAL (0x06) — Async/Deadline/Persist

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | DEADLINE_SET | H_E | rd, rs1, rs2 | Set deadline timer |
| 0x01 | DEADLINE_CHECK | H_E | rd, rs1, rs2 | Check if deadline exceeded |
| 0x02 | DEADLINE_CANCEL | H_E | rd, rs1, rs2 | Cancel deadline |
| 0x03 | PERSIST_STATE | H_E | rd, rs1, rs2 | Persist VM state |
| 0x04 | RESTORE_STATE | H_E | rd, rs1, rs2 | Restore from checkpoint |
| 0x05 | YIELD_CONTENTION | H_E | rd, rs1, rs2 | Yield if resource contended |
| 0x06 | TIME_ELAPSED | H_E | rd, rs1, rs2 | Cycles elapsed |
| 0x07 | CORO_SAVE | H_E | rd, rs1, rs2 | Save coroutine state |
| 0x08 | CORO_RESTORE | H_E | rd, rs1, rs2 | Restore coroutine state |
| 0x09 | SCHEDULE_AT | H_E | rd, rs1, rs2 | Schedule at cycle |
| 0x0A | WATCHDOG_SET | H_E | rd, rs1, rs2 | Set watchdog timeout |

#### 4.20.9 Meta-Extensions (0xF0–0xFF)

| ext_id | Name | Description |
|--------|------|-------------|
| 0xF0 | VER_EXT | Query extension availability (R0=1/0, R1=version) |
| 0xF1 | LOAD_EXT | Hot-load extension at runtime |
| 0xF2 | UNLOAD_EXT | Unload extension |
| 0xF3 | EXT_INFO | Get extension metadata |
| 0xF4–0xFF | Reserved | Future meta-extensions |

---

## 5. Register Model

### 5.1 General-Purpose Registers

| Register | Name | Width | Description |
|----------|------|-------|-------------|
| R0 | Zero / result | 64-bit | Often used as result register; initialized to 0 |
| R1–R14 | General | 64-bit | General-purpose registers |
| R15 | Scratch | 64-bit | Reserved for pseudo-instruction expansion (assembler uses for label offset temp) |
| FP | Frame pointer | 64-bit | Stack frame base (implicit, managed by ENTER/LEAVE) |
| SP | Stack pointer | 64-bit | Top of operand stack (implicit) |
| PC | Program counter | 64-bit | Current instruction offset (implicit) |

### 5.2 Confidence Registers

| Register | Width | Default | Description |
|----------|-------|---------|-------------|
| C0–C15 | f64 | 0.0 | One confidence register per general-purpose register |

Each confidence register C[i] tracks the trust/certainty of the corresponding value in R[i]. Confidence values are always in [0.0, 1.0] (see Section 7).

### 5.3 FLAGS Register

```
Bit 7: FLAG_SEC_VIOLATION  — Any security violation
Bit 6: FLAG_CAP_MISSING    — Capability missing/expired
Bit 5: FLAG_SANDBOX_PERM   — Sandbox permission violation
Bit 4: FLAG_TAG_VIOLATION  — Memory tag mismatch
Bit 3: FLAG_TRUST_POISON   — NaN/Inf confidence detected
Bit 2: FLAG_VERIFY_FAILED  — Bytecode verification failure
Bit 1: FLAG_ZERO           — Result was zero (comparison ops)
Bit 0: FLAG_NEGATIVE       — Result was negative
```

Bits 7–2: Security flags (write-clear only — agents cannot set them).  
Bits 1–0: Arithmetic flags (set by comparison and arithmetic operations).  
Flags are readable by HALT_ERR handler and CLF (clear).

### 5.4 Resource Limits (Runtime)

| Resource | Default | Description |
|----------|---------|-------------|
| max_memory_bytes | 64 MB | Per-agent memory budget |
| max_cycle_count | 10,000,000 | Per-execution cycle limit |
| max_stack_depth | 4,096 entries | Operand stack depth |
| max_regions | 256 | Sandbox regions per agent |
| max_extensions | 16 | Loaded extensions per VM |

---

## 6. Extension Protocol

### 6.1 Registration

1. Agent creates extension manifest JSON in `<vessel>/extensions/<ext_name>/manifest.json`
2. Agent opens issue on flux-runtime: "Extension Registration: EXT_<NAME>"
3. Oracle1 reviews: completeness, conformance vectors (≥5), no overlap, ISA compat, security
4. Oracle1 assigns `ext_id`, publishes to `flux-runtime/docs/extension-registry.json`
5. Extension enters 1-week fleet review: `DRAFT → REVIEW → STANDARD | REJECTED | REVISION`

### 6.2 Discovery — VER_EXT

Meta-extension `0xFF 0xF0 [target_ext_id]`:
- `target_ext_id = 0x00`: R0 = count of loaded extensions
- `target_ext_id = 0x01+`: R0 = 1 (loaded) or 0 (not loaded), R1 = version

### 6.3 Negotiation — CAPS/CAPS_ACK

When Agent A sends bytecode to Agent B:

```json
{
  "msg_type": "CAPS",
  "isa_version": "3.0",
  "extensions_required": [0x01, 0x06],
  "extensions_optional": [0x02, 0x03],
  "fallback_strategy": "strip_and_nop"
}
```

Agent B responds with CAPS_ACK. Fallback strategies:

| Strategy | Behavior |
|----------|----------|
| `strip_and_nop` | Replace unsupported escape instructions with NOP |
| `strip_and_halt` | Replace with ILLEGAL trap |
| `refuse` | Reject entire bytecode |
| `emulate` | Emulate using base-ISA sequences |

### 6.4 Bytecode Version Header (Optional)

```
Byte 0-3: 0x46 0x4C 0x55 0x58    ; "FLUX" magic
Byte 4:    ISA version (0x03)
Byte 5:    Number of extensions used
Byte 6+:   Extension IDs used (1 byte each)
```

VM detects magic and skips header; execution starts at first real instruction.

---

## 7. Confidence Model

### 7.1 Overview

FLUX ISA is uniquely confidence-aware: every computation can carry a trust/certainty value alongside its result. The 16 confidence registers (C0–C15) track the confidence of corresponding data registers (R0–R15).

### 7.2 Confidence Invariants

| Invariant | Enforcement |
|-----------|-------------|
| Values are finite | NaN, +Inf, −Inf → 0.0 |
| Values are in [0.0, 1.0] | Values < 0.0 → 0.0, values > 1.0 → 1.0 |
| Default value is 0.0 | All confidence registers initialized to 0.0 |
| Overflow clamped | Results > 1.0 → 1.0 |

### 7.3 Sanitization

Every write to a confidence register passes through `sanitize_confidence()`:

```python
def sanitize_confidence(value):
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return max(0.0, min(1.0, value))
```

Applied by: CONF_ST (0x0F), all C_* opcodes (0x60–0x6F), CONF_LD (0x0E, defensive), TRUST (0x5C).

### 7.4 Confidence Propagation Rules

| Opcode | Confidence Rule | Property |
|--------|----------------|----------|
| C_ADD | crd = min(crs1, crs2) | Never increases |
| C_SUB | crd = min(crs1, crs2) | Never increases |
| C_MUL | crd = crs1 × crs2 | Decreases (both ≤ 1.0) |
| C_DIV | crd = crs1 × crs2 × (1−ε) | Extra decay |
| C_MERGE | crd = weighted_avg | Cannot exceed inputs |
| C_BOOST | crd = min(1.0, crs × factor) | Capped at 1.0 |
| C_DECAY | crd = crs × factor | Can only decrease |

### 7.5 DEFAULT Confidence on Edge Operations

For edge/sensor operations (SENSE, ACTUATE, SAMPLE, etc.), the DEFAULT confidence model applies:

| Source | Default Confidence |
|--------|-------------------|
| Direct sensor reading | 0.8 (high but not perfect) |
| Fused sensor (multi-source) | Computed via C_MERGE |
| Model inference result | 0.7 (degraded by prediction uncertainty) |
| Received from A2A message | Confidence from sender's C register |
| User-provided (HUMAN source) | 1.0 (ground truth) |

---

## 8. Security Model

### 8.1 Architecture Overview

The security model implements defense-in-depth through four layers:

1. **Bytecode verification** (4-stage pipeline) — before A2A execution
2. **Capability-gated dispatch** (CAP_INVOKE) — at privileged opcode execution
3. **Sandbox memory isolation** (SANDBOX_ALLOC/FREE) — runtime memory enforcement
4. **Memory tagging** (TAG_ALLOC/TRANSFER/CHECK) — cross-agent access control

### 8.2 Security Opcodes (Base ISA)

| Hex | Mnemonic | Format | Description |
|-----|----------|--------|-------------|
| 0xDF | SANDBOX_ALLOC | G | Allocate isolated memory region with permission bits |
| 0xED | SANDBOX_FREE | G | Release sandboxed region (zeroes memory) |
| 0xEE | TAG_ALLOC | F | Tag memory region with ownership metadata |
| 0xEF | TAG_TRANSFER | F | Transfer tag ownership to another agent |
| 0xFA | CONF_CLAMP | A | Clamp all confidence registers to [0.0, 1.0] |
| 0xFB | TAG_CHECK | A | Verify current context can access R0; trap if not |

### 8.3 CAP_INVOKE — Capability-Gated Dispatch

CAP_INVOKE is an **interpreter-level** feature (not an ISA opcode). Before any privileged opcode executes:

```
fetch → decode → if opcode in PRIVILEGED_SET:
  → check_permission(required_cap)
  → if missing: set FLAG_SEC_VIOLATION + FLAG_CAP_MISSING, trap(HALT_ERR)
  → dispatch(opcode)
```

**Privileged categories:** A2A communication (TELL, ASK, DELEG, BCAST), agent lifecycle (FORK, JOIN), sensor/actuator I/O (SENSE, ACTUATE), memory allocation (MALLOC, SANDBOX_ALLOC), system control (RESET, WDOG).

### 8.4 Bytecode Verification Pipeline

Mandatory for all A2A-received bytecode:

| Stage | Check | Complexity |
|-------|-------|------------|
| 1. Structural | Format completeness, no trailing bytes | O(n) |
| 2. Register | All operands in [0, 16) | O(n) |
| 3. Control-flow | Jump targets instruction-aligned and in-bounds | O(n) |
| 4. Security | No unauthorized privileged opcodes | O(n) |

Verification is O(n), cached by SHA-256 hash, expires after capability TTL.

### 8.5 Permission Flags (Sandbox)

```
Bit 0: PERM_READ     (0x0001)
Bit 1: PERM_WRITE    (0x0002)
Bit 2: PERM_EXEC     (0x0004)
Bit 3: PERM_NOACCESS (0x0008) — guard page
```

Common combinations: 0x0003 (read-write data), 0x0005 (read-execute, W^X), 0x0008 (guard page).

### 8.6 Tag Types

```
0x0000: TAG_PRIVATE    — Only owner can access
0x0001: TAG_READONLY   — Owner reads/writes, others read-only
0x0002: TAG_SHARED     — Owner reads/writes, group reads/writes
0x0003: TAG_REVOCABLE  — Like SHARED, owner can revoke
0x0004: TAG_TRANSFER   — Ownership can be transferred
```

### 8.7 Security Error Codes

| Code | Name |
|------|------|
| 0xE0 | SEC_ERR_SANDBOX_OOM |
| 0xE1 | SEC_ERR_SANDBOX_OOR |
| 0xE2 | SEC_ERR_SANDBOX_PERM |
| 0xE3 | SEC_ERR_CAP_MISSING |
| 0xE4 | SEC_ERR_CAP_EXPIRED |
| 0xE5 | SEC_ERR_TAG_VIOLATION |
| 0xE6 | SEC_ERR_TAG_NOT_FOUND |
| 0xE7 | SEC_ERR_TAG_TRANSFER |
| 0xE8 | SEC_ERR_TRUST_POISON |
| 0xE9 | SEC_ERR_VERIFY_STRUCT |
| 0xEA | SEC_ERR_VERIFY_REG |
| 0xEB | SEC_ERR_VERIFY_CF |
| 0xEC | SEC_ERR_VERIFY_SEC |

---

## 9. Conformance Vectors

### 9.1 Summary

| Suite | Vectors | Status | Coverage |
|-------|---------|--------|----------|
| Base ISA (original) | 23 | 23/23 PASS | Arithmetic, comparison, control flow, complex programs |
| Base ISA (expanded) | 74 | 71/71 PASS, 3 SKIP | Memory, stack, shifts, edge cases |
| Escape prefix | 7 | Defined | NULL NOP, unsupported FAULT, VER_EXT, execution, compat, CAPS, operand size |
| Security | 18 | Defined | Sandbox (4), capability (4), tag (3), trust (4), verification (3) |
| Async/Temporal | 15 | Defined | SUSPEND/RESUME (3), YIELD (1), deadline (2), continuation (2), ticks (3), persist (1), contention (1), error (1), multi (1) |
| **TOTAL** | **137** | **94 runnable passing, 3 runnable skip, 40 defined** | **35 unique opcodes exercised** |

### 9.2 Running Conformance Tests

```bash
# Python runtime — original suite
python tools/conformance_runner.py --runtime python

# Python runtime — expanded suite
python tools/conformance_runner.py --runtime python --expanded

# C runtime — original suite
python tools/conformance_runner.py --runtime c

# Cross-runtime comparison
python tools/conformance_runner.py --all --expanded
```

Result: Python and C produce **identical results** across all 71 runnable test vectors (0 disagreements).

### 9.3 Vector Categories

| Category | Count | Opcodes Exercised |
|----------|-------|--------------------|
| Arithmetic | 29 | ADD, SUB, MUL, DIV, MOD, INC, DEC, ADDI, SUBI, MIN, MAX, MOVI, MOVI16, ADDI16, SUBI16 |
| Comparison | 8 | CMP_EQ, CMP_LT, CMP_GT, CMP_NE, JZ, JNZ, JLT, JGT |
| Control flow | 8 | JMP, JAL, JZ, JNZ, LOOP, CALL, RET, HALT |
| Data movement | 8 | MOVI, MOVI16, MOV, SWP, LOAD, STORE, LOADOFF, STOREOFF |
| Logic | 7 | AND, OR, XOR, NOT, NEG, ANDI, ORI, XORI, SHLI, SHRI, SHL, SHR |
| Memory | 5 | LOAD, STORE, LOADOFF, STOREOFF, ALLOC (SANDBOX) |
| Shift | 4 | SHLI, SHRI, SHL, SHR |
| Stack | 2 | PUSH, POP |
| Complex | 3 | Fibonacci, GCD, Sum of Squares (source-description) |

---

## 10. Implementation Status

### 10.1 Runtimes

| Runtime | Language | Format Coverage | Opcode Coverage | Conformance | Location |
|---------|----------|----------------|-----------------|-------------|----------|
| unified_interpreter.py | Python | A–G | 60+ | 23/23 + 71/71 | `src/flux/vm/python/` |
| flux_vm_unified.c | C | A–G | 60+ | 23/23 + 71/71 | `src/flux/vm/c/flux_vm_unified.c` |
| assembler.py | Python | A–G | 60+ | 23/23 | `src/flux/bytecode/assembler.py` |
| conformance_runner.py | Python | N/A | N/A | Runner for all | `tools/conformance_runner.py` |
| flux_vm_unified.rs | Rust | — | Planned | UNAVAILABLE | Not yet implemented |

### 10.2 ISA v3 Support Status

| Feature | Python | C | Rust | TypeScript |
|---------|--------|---|------|------------|
| Formats A–G (base ISA) | ✅ | ✅ | — | — |
| 60+ base opcodes | ✅ | ✅ | — | — |
| Format H (escape prefix) | 🔲 | 🔲 | — | — |
| 6 security opcodes | 🔲 | 🔲 | — | — |
| CAP_INVOKE dispatch | 🔲 | 🔲 | — | — |
| 4-stage verification | 🔲 | 🔲 | — | — |
| Confidence sanitization | 🔲 | 🔲 | — | — |
| EXT_TEMPORAL (0x06) | 🔲 | 🔲 | — | — |
| VER_EXT meta-extension | 🔲 | 🔲 | — | — |
| CAPS negotiation | 🔲 | 🔲 | — | — |

Legend: ✅ Implemented | 🔲 Not yet | — Not started

### 10.3 Cross-Runtime Performance (Python vs C)

| Category | Python (ops/sec) | C (ops/sec) | Speedup |
|----------|-----------------|-------------|---------|
| Decode | 11.6M | 10.8M | 0.9x |
| Arithmetic | 1.4M | 10.0M | 7.1x |
| Logic | 1.5M | 11.9M | 8.2x |
| Comparison | 1.2M | 10.7M | 8.6x |
| Control flow | 6.1M | 12.7M | 2.1x |
| Stack | 2.2M | 11.9M | 5.3x |
| Memory | 941K | 11.1M | 11.8x |
| Data movement | 1.4M | 10.9M | 7.5x |
| **Average** | — | — | **6.7x** |

---

## Appendix A — Encoding Examples

### A.1 Base ISA Instructions

```asm
; Format A: HALT (1 byte)
0x00

; Format B: INC R3 (2 bytes)
0x08 0x03

; Format C: YIELD 10 (2 bytes)
0x15 0x0A

; Format D: MOVI R0, 42 (3 bytes)
0x18 0x00 0x2A

; Format E: ADD R2, R0, R1 (4 bytes)
0x20 0x02 0x00 0x01

; Format F: MOVI16 R0, 1000 (4 bytes) — 1000 = 0x03E8
0x40 0x00 0x03 0xE8

; Format G: LOADOFF R0, R1, 0x0100 (5 bytes)
0x48 0x00 0x01 0x01 0x00

; Format H: NULL extension NOP (3 bytes)
0xFF 0x00 0x42
```

### A.2 Extension Instructions

```asm
; EXT_BABEL.LANG_DETECT (6 bytes)
0xFF 0x01 0x00 0x00 0x01 0x02

; EXT_EDGE.POWER_BUDGET (6 bytes)
0xFF 0x02 0x09 0x00 0x00 0x01

; EXT_EDGE.DMA_CHAIN (7 bytes, Format G operands)
0xFF 0x02 0x0B 0x00 0x01 0x04 0x00

; EXT_TEMPORAL.DEADLINE_SET (6 bytes)
0xFF 0x06 0x00 0x00 0x01 0x02

; VER_EXT query for EXT_BABEL (3 bytes)
0xFF 0xF0 0x01
```

### A.3 Version Detection Pattern

```asm
VER                      ; R0 = ISA version (3 for v3)
MOVI R1, 3
CMP_LT R2, R0, R1        ; R2 = (version < 3)
JNZ R2, v2_only          ; Jump if running on v2

; v3 path: check extensions
0xFF 0xF0 0x01           ; VER_EXT EXT_BABEL
MOVI R1, 1
CMP_EQ R3, R0, R1
JZ R3, no_babel

; ... extension code ...
HALT
no_babel:
; ... fallback ...
HALT
v2_only:
; ... base ISA only ...
HALT
```

---

## Appendix B — Cross-References

| Document | Relationship |
|----------|-------------|
| `ISA_UNIFIED.md` | v2 canonical opcode table (superseded by this document) |
| `isa-v3-escape-prefix-spec.md` | Detailed escape prefix spec (merged into Sections 3.8, 4.20, 6) |
| `isa-v3-address-map.md` | Domain-based address map (merged into Section 4) |
| `security-primitives-spec.md` | Full security spec (merged into Section 8) |
| `async-temporal-primitives-spec.md` | Async/temporal spec (merged into Sections 4.20.8, 9) |
| `formats.py` | Format definitions A–G (source of truth for encoding) |
| `isa_unified.py` | v2 opcode map with ~200 defined opcodes |
| `test_conformance_expanded.py` | 74 conformance test vectors |
| `unified_interpreter.py` | Python reference VM |
| `flux_vm_unified.c` | C reference VM |
| `assembler.py` | FLUX assembler (two-pass, pseudo-instruction expansion) |
| `conformance_runner.py` | Cross-runtime test runner |

---

*End of FLUX ISA v3.0 Full Specification Draft*
