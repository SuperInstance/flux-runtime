# FLUX ISA v3 — Complete Specification (DRAFT)

**Document ID:** ISA-001  
**Author:** Super Z (FLUX Fleet — Cartographer)  
**Date:** 2026-04-14  
**Status:** DRAFT — Requires fleet review and Oracle1 approval  
**Version:** 1.0.0-draft  
**Depends on:** ISA v2 unified spec (247 opcodes, `isa_unified.py`), `formats.py`  
**Tracks:** Oracle1 TASK-BOARD ISA-001 (CRITICAL PATH)  
**Resolves:** Slot overlap between SEC-001 (security) and ASYNC-001/TEMP-001 (async/temporal)  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Changed from v2 to v3](#2-what-changed-from-v2-to-v3)
3. [Opcode Map](#3-opcode-map)
   - 3.1 [Base ISA: 0x00–0xFE](#31-base-isa-0x00-0xfe)
   - 3.2 [Escape Prefix: 0xFF](#32-escape-prefix-0xff)
   - 3.3 [Extension ID Allocation](#33-extension-id-allocation)
4. [Slot Overlap Resolution](#4-slot-overlap-resolution)
5. [Format Reference](#5-format-reference)
   - 5.1 [Format A through G (v2 inherited)](#51-format-a-through-g-v2-inherited)
   - 5.2 [Format H — Escape Prefix (v3 new)](#52-format-h--escape-prefix-v3-new)
6. [Extension Protocol](#6-extension-protocol)
   - 6.1 [Registration](#61-registration)
   - 6.2 [Discovery](#62-discovery)
   - 6.3 [Negotiation](#63-negotiation)
7. [Security Primitives (Base ISA Slots)](#7-security-primitives-base-isa-slots)
8. [Async/Temporal Primitives (EXT_TEMPORAL)](#8-asynctemporal-primitives-ext_temporal)
9. [Conformance Requirements](#9-conformance-requirements)
10. [Migration Guide: v2 → v3](#10-migration-guide-v2--v3)
11. [Conformance Vector Summary](#11-conformance-vector-summary)
12. [Open Questions](#12-open-questions)
13. [Cross-References](#13-cross-references)

---

## 1. Executive Summary

FLUX ISA v3 is an **evolutionary upgrade** to the converged v2 specification (247 opcodes).
It preserves 100% backward compatibility — every valid v2 program runs unmodified on a v3 VM —
while adding three major capabilities demanded by the fleet's growing requirements:

| Capability | Mechanism | Rationale |
|-----------|-----------|-----------|
| **Unbounded extensibility** | Escape prefix `0xFF [ext_id] [sub_opcode]` | Fleet agents need domain-specific ops (linguistics, sensors, tensors) without exhausting base-ISA slots |
| **Hardware-grade security** | 6 direct ISA opcodes at reserved slots + interpreter-level enforcement | Multi-agent fleets require sandboxing, memory tagging, capability gating, and trust-poison prevention |
| **Async/temporal execution** | EXT_TEMPORAL extension (0x06) via escape prefix | A2A state handoff, deadlines, contention-aware yielding — essential for cooperative multi-agent workflows |

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backward compat | All 247 v2 addresses preserved | Fleet-wide deployment — no migration cost |
| Escape byte | 0xFF (was ILLEGAL in v2) | No valid v2 program contains 0xFF |
| Security slot placement | Direct base-ISA slots | Security primitives cannot be stripped; must be present in all v3 VMs |
| Async/temporal placement | Escape prefix (EXT_TEMPORAL) | Optional capabilities; graceful degradation possible |
| Extension operand format | Reuse base ISA formats A–G | Minimizes decoder changes across languages |
| Capability enforcement | Interpreter-level, not ISA opcodes | Prevents check-skipping attacks; cleaner architecture |

### Migration Path

- **v2 programs → v3 VM:** Zero changes. Bit-for-bit compatible.
- **v3 programs → v2 VM:** Programs using only base ISA work; escape prefix traps as ILLEGAL.
- **Runtime implementers:** ~6 discrete changes (see Section 10).

### Resolved Issues

| Issue | Severity | Resolution |
|-------|----------|------------|
| #15 — Zero bytecode verification | CRITICAL | 4-stage verification pipeline (see Section 7) |
| #16 — Unenforced CAP opcodes | HIGH | CAP_INVOKE dispatch gating (see Section 7.4) |
| #17 — NaN trust poisoning | HIGH | `sanitize_confidence()` + CONF_CLAMP (see Section 7.7) |
| Slot overlap (SEC vs ASYNC) | HIGH | Security→direct slots, Async→escape prefix (see Section 4) |

---

## 2. What Changed from v2 to v3

### 2.1 Changes Summary

| Category | v2 | v3 | Delta |
|----------|----|----|-------|
| Base opcode slots | 256 | 256 | No change |
| Defined base opcodes | 247 | **253** (+6 security) | +6 |
| Reserved base slots | 9 | **3** (0xFC, 0xFD, 0xFE) | −6 |
| Extension space | 0 | **65,536** (256 ext × 256 sub) | +65,536 |
| Instruction formats | 7 (A–G) | **8** (A–H) | +1 (Format H) |
| Security opcodes | 0 | **6** | +6 |
| Async/temporal opcodes | 0 | **11** (via EXT_TEMPORAL) | +11 |
| Confidence safety | None | Mandatory sanitization | Defense in depth |
| Bytecode verification | None | 4-stage pipeline | Issue #15 fixed |
| Capability enforcement | Stubbed | Wired into dispatch | Issue #16 fixed |

### 2.2 Address Stability Guarantee

> **Zero existing opcode addresses change in v3.**  
> The v3 map is a documentation reorganization plus new slots filled, not a renumbering.

All 247 v2 opcodes at their v2 addresses. New capabilities come from:
1. Filling previously reserved slots (security ops)
2. The escape prefix mechanism (all extensions)

### 2.3 What 0xFF Means Now

| ISA Version | 0xFF Meaning |
|-------------|--------------|
| v1 | (not defined) |
| v2 | ILLEGAL — trap to fault handler |
| v3 | **ESCAPE_PREFIX** — dispatch to extension table |

Since no valid v2 program can contain 0xFF (it was an illegal trap), this change is purely additive.

---

## 3. Opcode Map

### 3.1 Base ISA: 0x00–0xFE

The base ISA uses opcode range 0x00–0xFE. All 247 v2 opcodes are preserved at their
original addresses. Six new security opcodes occupy previously reserved slots.

```
┌────────────┬─────────────────────────────────────────────┬──────────┬──────────┬──────────┐
│ Range      │ Domain                                      │ Opcodes  │ v2 Status│ v3 Status│
├────────────┼─────────────────────────────────────────────┼──────────┼──────────┼──────────┤
│ 0x00-0x07  │ System Control + Interrupt                  │ 8        │ Defined  │ ✅ Unchanged │
│ 0x08-0x0F  │ Single Register Ops (INC, DEC, PUSH, POP)  │ 8        │ Defined  │ ✅ Unchanged │
│ 0x10-0x17  │ Immediate-Only Ops (SYS, TRAP, SEMA)       │ 8        │ Defined  │ ✅ Unchanged │
│ 0x18-0x1F  │ Register + Imm8 (MOVI, ADDI, logic imm)    │ 8        │ Defined  │ ✅ Unchanged │
│ 0x20-0x2F  │ Integer Arithmetic + Comparison            │ 16       │ Defined  │ ✅ Unchanged │
│ 0x30-0x3F  │ Float, Memory, Control Flow                │ 16       │ Defined  │ ✅ Unchanged │
│ 0x40-0x47  │ Register + Imm16 (MOVI16, JMP, JAL)       │ 8        │ Defined  │ ✅ Unchanged │
│ 0x48-0x4F  │ Register + Register + Imm16 (LOAD/STORE)  │ 8        │ Defined  │ ✅ Unchanged │
│ 0x50-0x5F  │ Agent-to-Agent Signal (TELL, ASK, FORK)   │ 16       │ Defined  │ ✅ Unchanged │
│ 0x60-0x6F  │ Confidence-Aware Variants (C_ADD, C_MUL)  │ 16       │ Defined  │ ✅ Unchanged │
│ 0x70-0x7F  │ Viewpoint Operations (Babel Domain)        │ 16       │ Defined  │ ✅ Unchanged │
│ 0x80-0x8F  │ Biology/Sensor Ops (JetsonClaw1 Domain)   │ 16       │ Defined  │ ✅ Unchanged │
│ 0x90-0x9F  │ Extended Math + Crypto                     │ 16       │ Defined  │ ✅ Unchanged │
│ 0xA0-0xAF  │ String/Collection Ops                      │ 16       │ Defined  │ ✅ Unchanged │
│ 0xB0-0xBF  │ Vector/SIMD Ops                            │ 16       │ Defined  │ ✅ Unchanged │
│ 0xC0-0xCF  │ Tensor/Neural Ops                          │ 16       │ Defined  │ ✅ Unchanged │
│ 0xD0-0xDE  │ Extended Memory/MMIO/GPU                  │ 15       │ Defined  │ ✅ Unchanged │
│ 0xDF       │ ★ SANDBOX_ALLOC (v3 NEW)                   │ 1        │ Reserved │ 🆕 Security │
│ 0xE0-0xEC  │ Long Jumps, Calls, Coroutine, Fault        │ 13       │ Defined  │ ✅ Unchanged │
│ 0xED       │ ★ SANDBOX_FREE (v3 NEW)                    │ 1        │ Reserved │ 🆕 Security │
│ 0xEE       │ ★ TAG_ALLOC (v3 NEW)                       │ 1        │ Reserved │ 🆕 Security │
│ 0xEF       │ ★ TAG_TRANSFER (v3 NEW)                    │ 1        │ Reserved │ 🆕 Security │
│ 0xF0-0xF9  │ Extended System (HALT_ERR, VER, CLK, etc) │ 10       │ Defined  │ ✅ Unchanged │
│ 0xFA       │ ★ CONF_CLAMP (v3 NEW)                      │ 1        │ Reserved │ 🆕 Security │
│ 0xFB       │ ★ TAG_CHECK (v3 NEW)                       │ 1        │ Reserved │ 🆕 Security │
│ 0xFC       │ Reserved                                    │ —        │ Reserved │ ⬜ Reserved │
│ 0xFD       │ Reserved                                    │ —        │ Reserved │ ⬜ Reserved │
│ 0xFE       │ Reserved                                    │ —        │ Reserved │ ⬜ Reserved │
│ 0xFF       │ ★ ESCAPE PREFIX (v3 NEW)                   │ ∞        │ ILLEGAL │ 🆕 v3 NEW │
├────────────┼─────────────────────────────────────────────┼──────────┼──────────┼──────────┤
│ TOTAL      │                                             │ 253+∞    │          │            │
└────────────┴─────────────────────────────────────────────┴──────────┴──────────┴──────────┘
```

#### 3.1.1 Complete Opcode Table

##### System Control (0x00–0x07) — Format A

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x00 | HALT | A | — | system | Stop execution |
| 0x01 | NOP | A | — | system | No operation (pipeline sync) |
| 0x02 | RET | A | — | system | Return from subroutine |
| 0x03 | IRET | A | — | system | Return from interrupt handler |
| 0x04 | BRK | A | — | debug | Breakpoint (trap to debugger) |
| 0x05 | WFI | A | — | system | Wait for interrupt (low-power idle) |
| 0x06 | RESET | A | — | system | Soft reset of register file |
| 0x07 | SYN | A | — | system | Memory barrier / synchronize |

##### Single Register Ops (0x08–0x0F) — Format B

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x08 | INC | B | rd | arithmetic | rd = rd + 1 |
| 0x09 | DEC | B | rd | arithmetic | rd = rd − 1 |
| 0x0A | NOT | B | rd | arithmetic | rd = ~rd |
| 0x0B | NEG | B | rd | arithmetic | rd = −rd |
| 0x0C | PUSH | B | rd | stack | Push rd onto stack |
| 0x0D | POP | B | rd | stack | Pop stack into rd |
| 0x0E | CONF_LD | B | rd | confidence | Load confidence register rd |
| 0x0F | CONF_ST | B | rd | confidence | Store confidence to register rd |

##### Immediate-Only Ops (0x10–0x17) — Format C

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x10 | SYS | C | imm8 | system | System call with code imm8 |
| 0x11 | TRAP | C | imm8 | system | Software interrupt vector imm8 |
| 0x12 | DBG | C | imm8 | debug | Debug print register imm8 |
| 0x13 | CLF | C | imm8 | system | Clear flags register bits imm8 |
| 0x14 | SEMA | C | imm8 | concurrency | Semaphore operation imm8 |
| 0x15 | YIELD | C | imm8 | concurrency | Yield execution for imm8 cycles |
| 0x16 | CACHE | C | imm8 | system | Cache control (flush/invalidate) |
| 0x17 | STRIPCF | C | imm8 | confidence | Strip confidence from next imm8 ops |

##### Register + Imm8 (0x18–0x1F) — Format D

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x18 | MOVI | D | rd, imm8 | move | rd = sign_extend(imm8) |
| 0x19 | ADDI | D | rd, imm8 | arithmetic | rd = rd + imm8 |
| 0x1A | SUBI | D | rd, imm8 | arithmetic | rd = rd − imm8 |
| 0x1B | ANDI | D | rd, imm8 | logic | rd = rd & imm8 |
| 0x1C | ORI | D | rd, imm8 | logic | rd = rd \| imm8 |
| 0x1D | XORI | D | rd, imm8 | logic | rd = rd ^ imm8 |
| 0x1E | SHLI | D | rd, imm8 | shift | rd = rd << imm8 |
| 0x1F | SHRI | D | rd, imm8 | shift | rd = rd >> imm8 |

##### Integer Arithmetic + Comparison (0x20–0x2F) — Format E

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
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
| 0x2C | CMP_EQ | E | rd, rs1, rs2 | compare | rd = (rs1 == rs2) ? 1 : 0 |
| 0x2D | CMP_LT | E | rd, rs1, rs2 | compare | rd = (rs1 < rs2) ? 1 : 0 |
| 0x2E | CMP_GT | E | rd, rs1, rs2 | compare | rd = (rs1 > rs2) ? 1 : 0 |
| 0x2F | CMP_NE | E | rd, rs1, rs2 | compare | rd = (rs1 != rs2) ? 1 : 0 |

##### Float, Memory, Control Flow (0x30–0x3F) — Format E

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
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

##### Register + Imm16 (0x40–0x47) — Format F

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x40 | MOVI16 | F | rd, imm16 | move | rd = imm16 |
| 0x41 | ADDI16 | F | rd, imm16 | arithmetic | rd = rd + imm16 |
| 0x42 | SUBI16 | F | rd, imm16 | arithmetic | rd = rd − imm16 |
| 0x43 | JMP | F | —, imm16 | control | pc += imm16 (relative) |
| 0x44 | JAL | F | rd, imm16 | control | rd = pc; pc += imm16 |
| 0x45 | CALL | F | rd, imm16 | control | push(pc); pc = rd + imm16 |
| 0x46 | LOOP | F | rd, imm16 | control | rd−−; if rd > 0: pc −= imm16 |
| 0x47 | SELECT | F | rd, imm16 | control | pc += imm16 × rd |

##### Register + Register + Imm16 (0x48–0x4F) — Format G

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x48 | LOADOFF | G | rd, rs1, imm16 | memory | rd = mem[rs1 + imm16] |
| 0x49 | STOREOFF | G | rd, rs1, imm16 | memory | mem[rs1 + imm16] = rd |
| 0x4A | LOADI | G | rd, rs1, imm16 | memory | rd = mem[mem[rs1] + imm16] |
| 0x4B | STOREI | G | rd, rs1, imm16 | memory | mem[mem[rs1] + imm16] = rd |
| 0x4C | ENTER | G | rd, rs1, imm16 | stack | push regs; sp −= imm16 |
| 0x4D | LEAVE | G | rd, rs1, imm16 | stack | sp += imm16; pop regs |
| 0x4E | COPY | G | rd, rs1, imm16 | memory | memcpy(rd, rs1, imm16) |
| 0x4F | FILL | G | rd, rs1, imm16 | memory | memset(rd, rs1, imm16) |

##### A2A Signal (0x50–0x5F) — Format E

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
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

##### Confidence-Aware (0x60–0x6F) — Format E (0x69 uses D)

| Addr | Mnemonic | Fmt | Operands | Category | Description |
|------|----------|-----|----------|----------|-------------|
| 0x60 | C_ADD | E | rd, rs1, rs2 | confidence | rd = rs1+rs2, crd=min(crs1,crs2) |
| 0x61 | C_SUB | E | rd, rs1, rs2 | confidence | rd = rs1−rs2, crd=min(crs1,crs2) |
| 0x62 | C_MUL | E | rd, rs1, rs2 | confidence | rd = rs1×rs2, crd=crs1×crs2 |
| 0x63 | C_DIV | E | rd, rs1, rs2 | confidence | rd = rs1/rs2, crd=crs1×crs2×(1−ε) |
| 0x64 | C_FADD | E | rd, rs1, rs2 | confidence | Float add + confidence |
| 0x65 | C_FSUB | E | rd, rs1, rs2 | confidence | Float sub + confidence |
| 0x66 | C_FMUL | E | rd, rs1, rs2 | confidence | Float mul + confidence |
| 0x67 | C_FDIV | E | rd, rs1, rs2 | confidence | Float div + confidence |
| 0x68 | C_MERGE | E | rd, rs1, rs2 | confidence | Merge confidences |
| 0x69 | C_THRESH | D | rd, imm8 | confidence | Skip next if crd < imm8/255 |
| 0x6A | C_BOOST | E | rd, rs1, rs2 | confidence | Boost crd by rs2 (max 1.0) |
| 0x6B | C_DECAY | E | rd, rs1, rs2 | confidence | Decay crd by rs2 per cycle |
| 0x6C | C_SOURCE | E | rd, rs1, rs2 | confidence | Set confidence source type |
| 0x6D | C_CALIB | E | rd, rs1, rs2 | confidence | Calibrate vs ground truth |
| 0x6E | C_EXPLY | E | rd, rs1, rs2 | confidence | Apply confidence to control flow |
| 0x6F | C_VOTE | E | rd, rs1, rs2 | confidence | Weighted vote |

##### Viewpoint — Babel Domain (0x70–0x7F) — Format E

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0x70 | V_EVID | viewpoint | Evidentiality: source type |
| 0x71 | V_EPIST | viewpoint | Epistemic stance |
| 0x72 | V_MIR | viewpoint | Mirative: unexpectedness |
| 0x73 | V_NEG | viewpoint | Negation scope |
| 0x74 | V_TENSE | viewpoint | Temporal viewpoint |
| 0x75 | V_ASPEC | viewpoint | Aspectual viewpoint |
| 0x76 | V_MODAL | viewpoint | Modal force |
| 0x77 | V_POLIT | viewpoint | Politeness register |
| 0x78 | V_HONOR | viewpoint | Honorific → trust tier |
| 0x79 | V_TOPIC | viewpoint | Topic-comment structure |
| 0x7A | V_FOCUS | viewpoint | Information focus |
| 0x7B | V_CASE | viewpoint | Case-based scope |
| 0x7C | V_AGREE | viewpoint | Agreement |
| 0x7D | V_CLASS | viewpoint | Classifier → type |
| 0x7E | V_INFL | viewpoint | Inflection → control flow |
| 0x7F | V_PRAGMA | viewpoint | Pragmatic context switch |

##### Sensor — JetsonClaw1 Domain (0x80–0x8F) — Format E

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0x80 | SENSE | sensor | Read sensor |
| 0x81 | ACTUATE | sensor | Write actuator |
| 0x82 | SAMPLE | sensor | Sample ADC |
| 0x83 | ENERGY | sensor | Energy budget |
| 0x84 | TEMP | sensor | Temperature |
| 0x85 | GPS | sensor | GPS coordinates |
| 0x86 | ACCEL | sensor | Accelerometer |
| 0x87 | DEPTH | sensor | Depth/pressure |
| 0x88 | CAMCAP | sensor | Camera capture |
| 0x89 | CAMDET | sensor | Detection |
| 0x8A | PWM | sensor | PWM output |
| 0x8B | GPIO | sensor | GPIO |
| 0x8C | I2C | sensor | I2C communication |
| 0x8D | SPI | sensor | SPI communication |
| 0x8E | UART | sensor | UART communication |
| 0x8F | CANBUS | sensor | CAN bus |

##### Extended Math + Crypto (0x90–0x9F) — Format E

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0x90 | ABS | math | Absolute value |
| 0x91 | SIGN | math | Sign |
| 0x92 | SQRT | math | Square root |
| 0x93 | POW | math | Power |
| 0x94 | LOG2 | math | Log base 2 |
| 0x95 | CLZ | math | Count leading zeros |
| 0x96 | CTZ | math | Count trailing zeros |
| 0x97 | POPCNT | math | Population count |
| 0x98 | CRC32 | crypto | CRC32 hash |
| 0x99 | SHA256 | crypto | SHA-256 block |
| 0x9A | RND | math | Random in [rs1, rs2] |
| 0x9B | SEED | math | Seed PRNG |
| 0x9C | FMOD | float | Float modulo |
| 0x9D | FSQRT | float | Float square root |
| 0x9E | FSIN | float | Sine |
| 0x9F | FCOS | float | Cosine |

##### String/Collection (0xA0–0xAF) — Mixed D/E/G

| Addr | Mnemonic | Fmt | Category | Description |
|------|----------|-----|----------|-------------|
| 0xA0 | LEN | D | collection | Length of collection |
| 0xA1 | CONCAT | E | collection | Concatenate |
| 0xA2 | AT | E | collection | Index |
| 0xA3 | SETAT | E | collection | Set element |
| 0xA4 | SLICE | G | collection | Slice |
| 0xA5 | REDUCE | E | collection | Fold |
| 0xA6 | MAP | E | collection | Map |
| 0xA7 | FILTER | E | collection | Filter |
| 0xA8 | SORT | E | collection | Sort |
| 0xA9 | FIND | E | collection | Find index |
| 0xAA | HASH | E | crypto | Hash |
| 0xAB | HMAC | E | crypto | HMAC signature |
| 0xAC | VERIFY | E | crypto | Verify signature |
| 0xAD | ENCRYPT | E | crypto | Encrypt |
| 0xAE | DECRYPT | E | crypto | Decrypt |
| 0xAF | KEYGEN | E | crypto | Generate keypair |

##### Vector/SIMD (0xB0–0xBF) — Format E

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0xB0 | VLOAD | vector | Load vector |
| 0xB1 | VSTORE | vector | Store vector |
| 0xB2 | VADD | vector | Vector add |
| 0xB3 | VMUL | vector | Vector multiply |
| 0xB4 | VDOT | vector | Dot product |
| 0xB5 | VNORM | vector | L2 norm |
| 0xB6 | VSCALE | vector | Scalar multiply |
| 0xB7 | VMAXP | vector | Element-wise max |
| 0xB8 | VMINP | vector | Element-wise min |
| 0xB9 | VREDUCE | vector | Reduce |
| 0xBA | VGATHER | vector | Gather load |
| 0xBB | VSCATTER | vector | Scatter store |
| 0xBC | VSHUF | vector | Shuffle lanes |
| 0xBD | VMERGE | vector | Merge by mask |
| 0xBE | VCONF | vector | Vector confidence |
| 0xBF | VSELECT | vector | Conditional select |

##### Tensor/Neural (0xC0–0xCF) — Format E

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0xC0 | TMATMUL | tensor | Matrix multiply |
| 0xC1 | TCONV | tensor | 2D convolution |
| 0xC2 | TPOOL | tensor | Max/avg pool |
| 0xC3 | TRELU | tensor | ReLU activation |
| 0xC4 | TSIGM | tensor | Sigmoid |
| 0xC5 | TSOFT | tensor | Softmax |
| 0xC6 | TLOSS | tensor | Loss function |
| 0xC7 | TGRAD | tensor | Gradient |
| 0xC8 | TUPDATE | tensor | SGD update |
| 0xC9 | TADAM | tensor | Adam optimizer |
| 0xCA | TEMBED | tensor | Embedding lookup |
| 0xCB | TATTN | tensor | Self-attention |
| 0xCC | TSAMPLE | tensor | Sample from distribution |
| 0xCD | TTOKEN | tensor | Tokenize |
| 0xCE | TDETOK | tensor | Detokenize |
| 0xCF | TQUANT | tensor | Quantize |

##### Memory/MMIO/GPU (0xD0–0xDF) — Format G

| Addr | Mnemonic | Category | Description |
|------|----------|----------|-------------|
| 0xD0 | DMA_CPY | memory | DMA copy |
| 0xD1 | DMA_SET | memory | DMA fill |
| 0xD2 | MMIO_R | memory | MMIO read |
| 0xD3 | MMIO_W | memory | MMIO write |
| 0xD4 | ATOMIC | memory | Atomic RMW |
| 0xD5 | CAS | memory | Compare-and-swap |
| 0xD6 | FENCE | memory | Memory fence |
| 0xD7 | MALLOC | memory | Allocate heap |
| 0xD8 | FREE | memory | Free heap |
| 0xD9 | MPROT | memory | Memory protect |
| 0xDA | MCACHE | memory | Cache management |
| 0xDB | GPU_LD | memory | GPU load |
| 0xDC | GPU_ST | memory | GPU store |
| 0xDD | GPU_EX | compute | GPU execute |
| 0xDE | GPU_SYNC | compute | GPU sync |
| 0xDF | **SANDBOX_ALLOC** | **security** | **★ NEW: Allocate sandbox region** |

##### Long Jump/Coroutine/Fault (0xE0–0xEF) — Mixed F/G

| Addr | Mnemonic | Fmt | Category | Description |
|------|----------|-----|----------|-------------|
| 0xE0 | JMPL | F | control | Long relative jump |
| 0xE1 | JALL | F | control | Long jump-and-link |
| 0xE2 | CALLL | F | control | Long call |
| 0xE3 | TAIL | F | control | Tail call |
| 0xE4 | SWITCH | F | control | Context switch |
| 0xE5 | COYIELD | F | control | Coroutine yield |
| 0xE6 | CORESUM | F | control | Coroutine resume |
| 0xE7 | FAULT | F | system | Raise fault code |
| 0xE8 | HANDLER | F | system | Install fault handler |
| 0xE9 | TRACE | F | debug | Trace log |
| 0xEA | PROF_ON | F | debug | Start profiling |
| 0xEB | PROF_OFF | F | debug | End profiling |
| 0xEC | WATCH | F | debug | Watchpoint |
| 0xED | **SANDBOX_FREE** | **G** | **security** | **★ NEW: Release sandbox region** |
| 0xEE | **TAG_ALLOC** | **F** | **security** | **★ NEW: Tag memory with ownership** |
| 0xEF | **TAG_TRANSFER** | **F** | **security** | **★ NEW: Transfer tag ownership** |

##### Extended System (0xF0–0xFF) — Mixed A/B

| Addr | Mnemonic | Fmt | Category | Description |
|------|----------|-----|----------|-------------|
| 0xF0 | HALT_ERR | A | system | Halt with error |
| 0xF1 | REBOOT | A | system | Warm reboot |
| 0xF2 | DUMP | A | debug | Dump register file |
| 0xF3 | ASSERT | A | debug | Assert flags |
| 0xF4 | ID | A | system | Return agent ID to R0 |
| 0xF5 | VER | A | system | Return ISA version to R0 (v3 → 3) |
| 0xF6 | CLK | A | system | Clock cycle count → R0 |
| 0xF7 | PCLK | A | system | Performance counter |
| 0xF8 | WDOG | A | system | Watchdog timer |
| 0xF9 | SLEEP | A | system | Low-power sleep |
| 0xFA | **CONF_CLAMP** | **A** | **security** | **★ NEW: Clamp confidence registers** |
| 0xFB | **TAG_CHECK** | **A** | **security** | **★ NEW: Verify tag access** |
| 0xFC | — | — | reserved | Reserved for future use |
| 0xFD | — | — | reserved | Reserved for future use |
| 0xFE | — | — | reserved | Reserved for future use |
| 0xFF | **ESCAPE** | **H** | **system** | **★ NEW: Escape prefix → extension** |

### 3.2 Escape Prefix: 0xFF

Format H provides unbounded extensibility through the escape prefix:

```
Byte 0: 0xFF           (escape prefix — always this value)
Byte 1: ext_id         (extension identifier, 0x00–0xFF)
Byte 2: sub_opcode     (operation within extension, 0x00–0xFF)
Byte 3+: operands      (format determined by extension's sub-opcode map)
```

**Addressing capacity:** 256 extensions × 256 sub-opcodes = **65,536 extension opcodes**

### 3.3 Extension ID Allocation

| Range | Count | Type | Authority |
|-------|-------|------|-----------|
| 0x00 | 1 | NULL (NOP passthrough) | Reserved |
| 0x01–0x7F | 127 | Fleet-standard | Oracle1 allocates |
| 0x80–0xEF | 112 | Experimental / vendor-specific | Self-assigned (register) |
| 0xF0–0xFF | 16 | Meta-extensions | Oracle1 reserves |

#### 3.3.1 Fleet-Standard Extensions (Allocated)

| ext_id | Name | Domain | Owner | Sub-opcodes |
|--------|------|--------|-------|-------------|
| 0x00 | NULL | Passthrough/NOP | System | 256 (all NOP) |
| 0x01 | EXT_BABEL | Multilingual linguistics | Babel | 12 |
| 0x02 | EXT_EDGE | Sensor/actuator/edge | JetsonClaw1 | 12 |
| 0x03 | EXT_CONFIDENCE | Advanced confidence | Fleet | 10 |
| 0x04 | EXT_TENSOR | Tensor/neural advanced | JC1 + Oracle1 | 16 |
| 0x05 | EXT_SECURITY | Capability enforcement | Fleet | 13 |
| **0x06** | **EXT_TEMPORAL** | **Async/deadline/persist** | **Fleet** | **11** |
| 0x07–0x7F | Unassigned | — | — | Available |

#### 3.3.2 Meta-Extensions

| ext_id | Name | Purpose |
|--------|------|---------|
| 0xF0 | VER_EXT | Query extension availability at runtime |
| 0xF1 | LOAD_EXT | Hot-load extension at runtime |
| 0xF2 | UNLOAD_EXT | Unload extension |
| 0xF3 | EXT_INFO | Get extension metadata |
| 0xF4–0xFF | Reserved | Future meta-extensions |

---

## 4. Slot Overlap Resolution

### 4.1 The Problem

The security primitives spec (SEC-001, Task 15c) and the async/temporal primitives spec
(ASYNC-001 + TEMP-001, Task 15d) both claimed the same reserved opcode slots:

| Slot | SEC-001 Claim | ASYNC/TEMP-001 Claim |
|------|--------------|---------------------|
| 0xED | SANDBOX_FREE | SUSPEND |
| 0xEE | TAG_ALLOC | RESUME |
| 0xEF | TAG_TRANSFER | CONTINUATION_ID |
| 0xFA | CONF_CLAMP | DEADLINE_BEFORE |
| 0xFB | TAG_CHECK | YIELD_IF_CONTENTION |
| 0xFC | (reserved) | PERSIST_CRITICAL_STATE |
| 0xFD | (reserved) | TICKS_ELAPSED |

### 4.2 The Resolution

**Security primitives win the direct base-ISA slots. Async/temporal primitives move to
the EXT_TEMPORAL extension via the escape prefix.**

| Slot | Final Assignment | Format | Category | Justification |
|------|-----------------|--------|----------|---------------|
| 0xDF | SANDBOX_ALLOC | G | security (v3 NEW) | Only Format G provides 3 operands (rd, rs1, imm16) |
| 0xED | SANDBOX_FREE | G | security (v3 NEW) | Security cannot be stripped; must be in base ISA |
| 0xEE | TAG_ALLOC | F | security (v3 NEW) | Security cannot be stripped; must be in base ISA |
| 0xEF | TAG_TRANSFER | F | security (v3 NEW) | Security cannot be stripped; must be in base ISA |
| 0xFA | CONF_CLAMP | A | security (v3 NEW) | Trust safety is non-negotiable for multi-agent |
| 0xFB | TAG_CHECK | A | security (v3 NEW) | Memory tag enforcement is non-negotiable |
| 0xFC | — | — | **reserved** | Available for future security or base-ISA use |
| 0xFD | — | — | **reserved** | Available for future security or base-ISA use |
| 0xFE | — | — | **reserved** | Available for future use |

### 4.3 Rationale

1. **Security primitives MUST be in the base ISA.** They enforce memory isolation,
   capability gating, and trust safety. If they were extension opcodes, a VM could strip
   them via `strip_and_nop`, completely defeating security. This is architecturally
   unacceptable.

2. **Async/temporal primitives CAN be extension ops.** They are optional capabilities:
   - A VM without EXT_TEMPORAL simply cannot execute SUSPEND/RESUME. Programs that
     need async behavior check for extension availability via VER_EXT and provide
     fallback code paths.
   - If an agent sends bytecode using EXT_TEMPORAL to a VM that doesn't support it,
     the bytecode is gracefully degraded (unsupported escape instructions replaced with
     NOPs), not silently stripped of security checks.

3. **The escape prefix already defines EXT_TEMPORAL (0x06) with 11 sub-opcodes** (see
   `isa-v3-escape-prefix-spec.md` Section 6.6). This provides more capacity than the 7
   reserved slots originally claimed by async/temporal spec, and allows future expansion.

### 4.4 Async/Temporal Sub-Opcode Mapping

The 7 opcodes from the original async/temporal spec map to EXT_TEMPORAL as follows:

| Original Base Slot | Mnemonic | EXT_TEMPORAL Sub | Bytes (base) | Bytes (ext) |
|-------------------|----------|-----------------|--------------|-------------|
| 0xED (was) | SUSPEND | 0x00 | 2 | 6 (FF 06 00 rd rs1 rs2) |
| 0xEE (was) | RESUME | 0x01 | 2 | 6 (FF 06 01 rd rs1 rs2) |
| 0xEF (was) | CONTINUATION_ID | 0x02 | 2 | 6 (FF 06 02 rd rs1 rs2) |
| 0xFA (was) | DEADLINE_BEFORE | 0x03 | 2 | 6 (FF 06 03 rd rs1 rs2) |
| 0xFB (was) | YIELD_IF_CONTENTION | 0x04 | 2 | 6 (FF 06 04 rd rs1 rs2) |
| 0xFC (was) | PERSIST_CRITICAL_STATE | 0x05 | 2 | 6 (FF 06 05 rd rs1 rs2) |
| 0xFD (was) | TICKS_ELAPSED | 0x06 | 2 | 6 (FF 06 06 rd rs1 rs2) |

**Encoding change:** The async/temporal ops used Format B (2 bytes) in their original
spec. As EXT_TEMPORAL sub-opcodes, they use Format E operands (rd, rs1, rs2 — 4 bytes after
the prefix), for 6 bytes total. This is larger but consistent with the extension protocol's
recommendation to reuse base ISA formats (Pattern A).

The unused `rs1` and `rs2` fields can be set to 0 for single-operand semantics.

---

## 5. Format Reference

### 5.1 Format A through G (v2 inherited)

| Format | Bytes | Encoding | Opcodes |
|--------|-------|----------|---------|
| **A** | 1 | `[op]` | 0x00–0x07, 0xF0–0xFB |
| **B** | 2 | `[op][rd]` | 0x08–0x0F |
| **C** | 2 | `[op][imm8]` | 0x10–0x17 |
| **D** | 3 | `[op][rd][imm8]` | 0x18–0x1F, 0x69, 0xA0 |
| **E** | 4 | `[op][rd][rs1][rs2]` | 0x20–0x6F, 0x80–0xBF, 0xC0–0xCF, 0xD0–0xDE |
| **F** | 4 | `[op][rd][imm16hi][imm16lo]` | 0x40–0x47, 0xE0–0xEC, 0xEE–0xEF |
| **G** | 5 | `[op][rd][rs1][imm16hi][imm16lo]` | 0x48–0x4F, 0xA4, 0xD0–0xDF, 0xED |

**Encoding diagrams:**

```
Format A: ┌────┐
           │ op │
           └────┘

Format B: ┌────┬────┐
           │ op │ rd │
           └────┴────┘

Format C: ┌────┬──────┐
           │ op │ imm8 │
           └────┴──────┘

Format D: ┌────┬────┬──────┐
           │ op │ rd │ imm8 │
           └────┴────┴──────┘

Format E: ┌────┬────┬─────┬─────┐
           │ op │ rd │ rs1 │ rs2 │
           └────┴────┴─────┴─────┘

Format F: ┌────┬────┬──────┬──────┐
           │ op │ rd │ imm16 │ imm16│
           │    │    │  hi   │  lo  │
           └────┴────┴──────┴──────┘

Format G: ┌────┬────┬─────┬──────┬──────┐
           │ op │ rd │ rs1 │ imm16 │ imm16│
           │    │    │     │  hi   │  lo  │
           └────┴────┴─────┴──────┴──────┘
```

All multi-byte formats use **little-endian** for immediate fields.

### 5.2 Format H — Escape Prefix (v3 new)

```
Format H: ┌────┬───────┬───────────┬─────────┐
           │0xFF│ext_id │sub_opcode │operands │
           └────┴───────┴───────────┴─────────┘
            1B    1B        1B       variable

Minimum size: 3 bytes (zero-operand extension ops)
Maximum size: 8 bytes (Format G operands: 3 + 5 = 8)
```

**Operand format after escape prefix:** Extensions declare which base format (A–G) to
apply for operands. The VM reads operands exactly as it would for a base-ISA opcode of that
format. This is **Pattern A** (reuse base formats) — see `isa-v3-escape-prefix-spec.md` §2.4.

**Size analysis:**

| Extension operands | Total bytes |
|--------------------|-------------|
| None (Format A) | 3 |
| Format B | 4 |
| Format D | 5 |
| Format E | 6 |
| Format F | 6 |
| Format G | 7 |

---

## 6. Extension Protocol

### 6.1 Registration

1. Agent creates extension manifest JSON in `<vessel>/extensions/<ext_name>/manifest.json`
2. Agent opens issue on flux-runtime: "Extension Registration: EXT_<NAME>"
3. Oracle1 reviews for completeness, conformance vectors (≥5), no overlap, ISA compat
4. Oracle1 assigns `ext_id`, publishes to `flux-runtime/docs/extension-registry.json`
5. Extension enters 1-week fleet review (DRAFT → REVIEW → STANDARD)

Lifecycle: `DRAFT → REVIEW → STANDARD | REJECTED | REVISION`

### 6.2 Discovery

**VER_EXT** meta-extension (`0xFF 0xF0 [target_ext_id]`):
- `target_ext_id = 0x00`: R0 = count of loaded extensions
- `target_ext_id = 0x01+`: R0 = 1 (loaded) or 0 (not loaded), R1 = version (major<<16\|minor<<8\|patch)

Every v3 VM maintains an Extension Table at startup:
```
EXT_TABLE[0x00] = NULL_EXTENSION  (always present)
EXT_TABLE[0x01] = EXT_BABEL       (if loaded)
EXT_TABLE[0x06] = EXT_TEMPORAL    (if loaded)
...
```

### 6.3 Negotiation

When Agent A sends bytecode to Agent B, it includes a **CAPS preamble**:

```json
{
  "msg_type": "CAPS",
  "isa_version": "3.0",
  "extensions_required": [0x01, 0x06],
  "extensions_optional": [0x02, 0x03],
  "fallback_strategy": "strip_and_nop"
}
```

Agent B responds with CAPS_ACK listing supported/unsupported extensions and chosen
fallback strategy.

| Strategy | Behavior |
|----------|----------|
| `strip_and_nop` | Replace unsupported escape instructions with NOP |
| `strip_and_halt` | Replace with ILLEGAL trap |
| `refuse` | Reject entire bytecode |
| `emulate` | Agent B emulates extension using base-ISA sequences |

---

## 7. Security Primitives (Base ISA Slots)

The following 6 opcodes are the v3 security primitive set. Full specification in
`security-primitives-spec.md` (SEC-001). They occupy previously reserved slots
and are **always present** in any v3-conformant VM — they cannot be stripped.

### 7.1 New Opcode Definitions

| Hex | Mnemonic | Format | Encoding | Description |
|-----|----------|--------|----------|-------------|
| 0xDF | SANDBOX_ALLOC | G | `[0xDF][rd][rs1][imm16hi][imm16lo]` | Allocate isolated memory region with permission bits |
| 0xED | SANDBOX_FREE | G | `[0xED][rd][imm16hi][imm16lo]` | Release sandboxed region (zeroes memory) |
| 0xEE | TAG_ALLOC | F | `[0xEE][rd][imm16hi][imm16lo]` | Tag memory region with ownership metadata |
| 0xEF | TAG_TRANSFER | F | `[0xEF][rd][imm16hi][imm16lo]` | Transfer tag ownership to another agent |
| 0xFA | CONF_CLAMP | A | `[0xFA]` | Clamp all confidence registers to [0.0, 1.0] |
| 0xFB | TAG_CHECK | A | `[0xFB]` | Verify current context can access R0; trap if not |

### 7.2 Interpreter-Level Security Features

Two critical security features are implemented at the interpreter level (not as ISA opcodes):

#### CAP_INVOKE (Capability-Gated Dispatch)

Before any privileged opcode executes, the interpreter checks the agent's capability:

```
fetch → decode → if opcode in PRIVILEGED_SET:
  → check_permission(required_cap)
  → if missing: set FLAG_SEC_VIOLATION + FLAG_CAP_MISSING, trap(HALT_ERR)
  → dispatch(opcode)
```

**Privileged opcode categories:** A2A communication (TELL, ASK, DELEG, BCAST), agent
lifecycle (FORK, JOIN), sensor/actuator I/O, memory allocation, system control (RESET, WDOG).

#### Bytecode Verification Pipeline (4 stages)

Mandatory for all A2A-received bytecode:

| Stage | Check | Complexity |
|-------|-------|------------|
| 1. Structural | Format completeness, no trailing bytes, no reserved opcodes | O(n) |
| 2. Register | All register operands in [0, 16) | O(n) |
| 3. Control-flow | Jump targets instruction-aligned and in-bounds | O(n) |
| 4. Security | No unauthorized privileged opcodes for receiving agent | O(n) |

### 7.3 Trust Poisoning Prevention

Every write to a confidence register passes through `sanitize_confidence()`:

```python
def sanitize_confidence(value):
    if math.isnan(value) or math.isinf(value):
        return 0.0  # Safe default
    return max(0.0, min(1.0, value))
```

Applied by: CONF_ST, all C_* opcodes, CONF_LD (defensive), TRUST.

### 7.4 Security Flags Register

```
FLAG_SEC_VIOLATION  (bit 7) — Any security violation
FLAG_CAP_MISSING    (bit 6) — Capability missing/expired
FLAG_SANDBOX_PERM   (bit 5) — Sandbox permission violation
FLAG_TAG_VIOLATION  (bit 4) — Memory tag mismatch
FLAG_TRUST_POISON   (bit 3) — NaN/Inf confidence detected
FLAG_VERIFY_FAILED  (bit 2) — Bytecode verification failure
```

Write-clear only — agents cannot set these flags.

### 7.5 Security Error Codes

| Code | Name | Description |
|------|------|-------------|
| 0xE0 | SEC_ERR_SANDBOX_OOM | Out of memory for sandbox allocation |
| 0xE1 | SEC_ERR_SANDBOX_OOR | Out-of-range sandbox access |
| 0xE2 | SEC_ERR_SANDBOX_PERM | Sandbox permission violation |
| 0xE3 | SEC_ERR_CAP_MISSING | Required capability not held |
| 0xE4 | SEC_ERR_CAP_EXPIRED | Capability token expired |
| 0xE5 | SEC_ERR_TAG_VIOLATION | Memory tag access denied |
| 0xE6 | SEC_ERR_TAG_NOT_FOUND | No tag for region |
| 0xE7 | SEC_ERR_TAG_TRANSFER | Cannot transfer tag (wrong type/owner) |
| 0xE8 | SEC_ERR_TRUST_POISON | NaN/Inf in confidence register |
| 0xE9 | SEC_ERR_VERIFY_STRUCT | Structural verification failed |
| 0xEA | SEC_ERR_VERIFY_REG | Register verification failed |
| 0xEB | SEC_ERR_VERIFY_CF | Control-flow verification failed |
| 0xEC | SEC_ERR_VERIFY_SEC | Security verification failed |

### 7.6 Conformance Vectors (Security)

18 vectors across 5 categories:

| Category | Count | Vectors |
|----------|-------|---------|
| Sandbox | 4 | SEC-001 through SEC-004 |
| Capability | 4 | SEC-005 through SEC-008 |
| Memory Tag | 3 | SEC-009 through SEC-011 |
| Trust | 4 | SEC-012 through SEC-015 |
| Verification | 3 | SEC-016 through SEC-018 |

See `security-primitives-spec.md` §8 for full vector definitions.

---

## 8. Async/Temporal Primitives (EXT_TEMPORAL)

The async/temporal primitives are implemented as **EXT_TEMPORAL (0x06)** via the escape
prefix. Full specification in `async-temporal-primitives-spec.md` (ASYNC-001 + TEMP-001).

### 8.1 Sub-Opcode Table

| Sub | Mnemonic | Operands (Format E) | Description |
|-----|----------|---------------------|-------------|
| 0x00 | SUSPEND | rd, 0, 0 | Save VM state to continuation handle → rd |
| 0x01 | RESUME | rd, 0, 0 | Restore VM state from handle in rd |
| 0x02 | CONTINUATION_ID | rd, 0, 0 | Query current execution state fingerprint → rd |
| 0x03 | DEADLINE_BEFORE | rd, 0, 0 | Set deadline: auto-suspend after rd ticks |
| 0x04 | YIELD_IF_CONTENTION | rd, 0, 0 | Yield if resource rd is contended |
| 0x05 | PERSIST_CRITICAL_STATE | rd, 0, 0 | Save registers per bitmask in rd |
| 0x06 | TICKS_ELAPSED | rd, 0, 0 | Cycle count → rd (+ confidence decay) |

**Encoding:** `0xFF 0x06 [sub_opcode] rd 0x00 0x00` (6 bytes)

### 8.2 Relationship to Existing Opcodes

| Existing | Hex | New (EXT_TEMPORAL) | Relationship |
|----------|-----|--------------------|--------------|
| YIELD | 0x15 | *(kept as-is)* | YIELD is lightweight; SUSPEND is for A2A handoff |
| COYIELD | 0xE5 | SUSPEND (0x00) | SUSPEND is handle-based, not jump-based |
| CORESUM | 0xE6 | RESUME (0x01) | RESUME takes explicit handle |
| CLK | 0xF6 | TICKS_ELAPSED (0x06) | TICKS_ELAPSED writes to any register |
| WDOG | 0xF8 | DEADLINE_BEFORE (0x03) | DEADLINE auto-suspends, not reboots |

### 8.3 Continuation Serialization

Continuations are serialized to JSON for A2A transmission:

```json
{
  "id": "cont_550e8400-...",
  "version": 1,
  "source_agent": "agent-oracle1",
  "isa_version": "3.0",
  "state": {
    "pc": 42,
    "registers": [100, 200, 0, ...],
    "confidence": [1.0, 0.95, ...],
    "stack": [42, 17, 8],
    "flags": {"zero": false, "carry": true, ...}
  },
  "memory": {"format": "dirty_pages", "pages": [...]},
  "checksum": "a1b2c3d4"
}
```

Size: ~500–1000 bytes (minimal), ~100–200 KB (full snapshot).

### 8.4 Fiber Design

Fibers are lightweight cooperative threads within a single FLUX VM:

- **Scheduler:** Round-robin with A2A priority boost (+3 for incoming messages)
- **States:** CREATED → READY → RUNNING → SUSPENDED/BLOCKED/COMPLETED
- **Max fibers:** 64 (384 bytes per fiber in C-compatible flat array)
- **Priority:** 0–15; A2A responses boosted to 12–14

### 8.5 Conformance Vectors (Async/Temporal)

15 vectors across 2 categories:

| Category | Count | Vectors |
|----------|-------|---------|
| Async (SUSPEND, RESUME, YIELD, CONTINUATION_ID) | 10 | AT-001 through AT-010 |
| Temporal (DEADLINE, CONTENTION, PERSIST, TICKS) | 5 | AT-011 through AT-015 |

See `async-temporal-primitives-spec.md` §9 for full vector definitions.

---

## 9. Conformance Requirements

A v3-conformant runtime must implement a specific tier:

### 9.1 Tier 1 — Base Conformance

**Required:** All v2 opcodes (247) + Formats A–G + 6 new security opcodes + `CONF_CLAMP` / `TAG_CHECK` zero-operand handling + `sanitize_confidence()` on every confidence write + `VER` returns 3

| Requirement | Specification Reference |
|-------------|------------------------|
| All 247 v2 opcodes | `isa_unified.py` — exact behavior |
| Formats A–G encoding | `formats.py` — byte-for-byte match |
| 6 security opcodes | Section 7 of this document |
| Confidence sanitization | Section 7.3 |
| VER opcode returns 3 | ISA version detection |
| Register file: 16 GP + 16 confidence | R0–R15, CR0–CR15 |
| 64KB memory, 4096-entry stack | Minimum resource guarantees |
| 71/71 base conformance tests pass | `test_conformance_expanded.py` |

### 9.2 Tier 2 — Extended Conformance

**Required:** Tier 1 + escape prefix dispatcher + VER_EXT meta-extension + extension table + graceful FAULT on unsupported extension

| Requirement | Specification Reference |
|-------------|------------------------|
| 0xFF dispatches to extension table | `isa-v3-escape-prefix-spec.md` §3 |
| NULL extension (0x00) acts as NOP | Escape prefix spec §3.2 |
| VER_EXT (0xFF 0xF0) works | Escape prefix spec §3.3 |
| FAULT on unknown ext_id | Escape prefix spec §3.2 |
| FAULT on unknown sub_opcode | Escape prefix spec §3.2 |
| Correct PC advancement for extension ops | Escape prefix spec §8.7 |
| 7 escape prefix conformance vectors pass | Escape prefix spec §8 |

### 9.3 Tier 3 — Full Conformance

**Required:** Tier 2 + EXT_TEMPORAL (0x06) implementation + CAP_INVOKE capability gating + 4-stage bytecode verification pipeline + security flags register + implicit tag enforcement

| Requirement | Specification Reference |
|-------------|------------------------|
| EXT_TEMPORAL (0x06) with 7 sub-opcodes | Section 8 of this document |
| Fiber scheduler (round-robin + priority boost) | Async/temporal spec §6.3 |
| Continuation serialization | Async/temporal spec §5 |
| CAP_INVOKE on all privileged opcodes | Security spec §4.2 |
| 4-stage bytecode verification | Security spec §6 |
| Security flags register | Security spec §4.3 |
| SANDBOX_ALLOC/FREE with permission enforcement | Security spec §3 |
| TAG_ALLOC/TRANSFER/CHECK with implicit enforcement | Security spec §5 |
| 18 security conformance vectors pass | Security spec §8 |
| 15 async/temporal conformance vectors pass | Async/temporal spec §9 |

---

## 10. Migration Guide: v2 → v3

### 10.1 Python Runtime

**File:** `src/flux/vm/unified_interpreter.py`

Changes required:

1. **Change 0xFF handler** (line ~varies): Replace `ILLEGAL` trap with escape prefix dispatcher
2. **Add extension table**: `ext_table = {0x00: None}` (NULL always present)
3. **Add VER_EXT handler**: `0xFF 0xF0 [target_ext_id]` → check extension table
4. **Add 6 security opcodes**: SANDBOX_ALLOC, SANDBOX_FREE, TAG_ALLOC, TAG_TRANSFER, CONF_CLAMP, TAG_CHECK
5. **Add `sanitize_confidence()`**: Wrap all confidence register writes
6. **Update VER to return 3** (was 2)

```python
# Pseudocode for escape prefix dispatch
if opcode == 0xFF:
    ext_id = bytecode[pc + 1]
    sub_opcode = bytecode[pc + 2]
    if ext_id == 0x00:
        # NULL extension — NOP
        pc += 3  # or + 3 + format_size if operands follow
    elif ext_id not in ext_table:
        self.trap("EXT_UNSUPPORTED", ext_id)
    else:
        ext = ext_table[ext_id]
        ext.dispatch(sub_opcode, bytecode, pc + 3)
```

### 10.2 C Runtime

**File:** `src/flux/vm/c/flux_vm_unified.c`

Changes required:

1. **Add `struct ExtensionTable`** with capacity for 256 entries
2. **Replace `case 0xFF: /* ILLEGAL */`** with escape prefix dispatcher
3. **Add 6 security opcode cases** in the switch dispatch
4. **Add `sanitize_confidence(double value)`** function
5. **Add security flags** to the VM state struct
6. **Update `cmd_ver` to return 3**

### 10.3 Rust Runtime

**Repo:** `flux-rust` or `flux-coop-runtime`

Changes required:

1. **Add extension table** as `HashMap<u8, Box<dyn Extension>>`
2. **Implement Format H decode** in the instruction decoder
3. **Add security opcode implementations**
4. **Add confidence sanitization wrapper**
5. **Port 71+31 = 102 conformance vectors** to Rust test suite

### 10.4 Migration Checklist

```
[ ] 1. Update VER to return 3
[ ] 2. Implement escape prefix dispatcher (0xFF)
[ ] 3. Add extension table + NULL extension
[ ] 4. Implement VER_EXT (0xFF 0xF0)
[ ] 5. Add 6 security opcodes
[ ] 6. Add sanitize_confidence() to all confidence writes
[ ] 7. Add security flags register
[ ] 8. Run 71 base conformance tests — must all pass
[ ] 9. Run 7 escape prefix conformance tests
[ ]10. Run 18 security conformance tests
[ ]11. (Tier 3) Implement EXT_TEMPORAL
[ ]12. (Tier 3) Run 15 async/temporal conformance tests
```

---

## 11. Conformance Vector Summary

### 11.1 Vector Counts by Category

| Category | Source | Count | Tier |
|----------|--------|-------|------|
| Base arithmetic (ADD, SUB, MUL, DIV, MOD, etc.) | `test_conformance_expanded.py` | 29 | 1 |
| Base comparison (CMP_EQ, CMP_LT, CMP_GT, CMP_NE) | `test_conformance_expanded.py` | 8 | 1 |
| Base control flow (JZ, JNZ, JMP, JAL, LOOP) | `test_conformance_expanded.py` | 8 | 1 |
| Base data (MOVI, MOVI16, MOV, SWP, etc.) | `test_conformance_expanded.py` | 8 | 1 |
| Base logic (AND, OR, XOR, shift) | `test_conformance_expanded.py` | 7 | 1 |
| Base memory (LOAD, STORE, LOADOFF, STOREOFF) | `test_conformance_expanded.py` | 5 | 1 |
| Base shift (SHL, SHR, SHLI, SHRI) | `test_conformance_expanded.py` | 4 | 1 |
| Base stack (PUSH, POP) | `test_conformance_expanded.py` | 2 | 1 |
| Base complex (GCD, Fibonacci, Sum of Squares) | `test_conformance.py` | 3 | 1 |
| **Base total** | | **74** | **1** |
| Escape prefix (NULL, FAULT, VER_EXT, execute, compat, CAPS, size) | `isa-v3-escape-prefix-spec.md` §8 | 7 | 2 |
| Sandbox (alloc, perm, OOR, guard) | `security-primitives-spec.md` §8 | 4 | 3 |
| Capability (missing, valid, expired, sensor) | `security-primitives-spec.md` §8 | 4 | 3 |
| Memory tag (cross-agent deny, transfer, check) | `security-primitives-spec.md` §8 | 3 | 3 |
| Trust (NaN, Inf, overflow, negative) | `security-primitives-spec.md` §8 | 4 | 3 |
| Verification (truncated, unauthorized, reserved) | `security-primitives-spec.md` §8 | 3 | 3 |
| **Security total** | | **18** | **3** |
| Async (SUSPEND, RESUME, YIELD, CONTINUATION_ID) | `async-temporal-primitives-spec.md` §9 | 10 | 3 |
| Temporal (DEADLINE, CONTENTION, PERSIST, TICKS) | `async-temporal-primitives-spec.md` §9 | 5 | 3 |
| **Async/temporal total** | | **15** | **3** |
| **GRAND TOTAL** | | **114** | **1–3** |

### 11.2 Cross-Runtime Status

| Runtime | Tier | Base Tests | Status |
|---------|------|------------|--------|
| Python (`unified_interpreter.py`) | 1 | 71/71 PASS | ✅ Conformant |
| C (`flux_vm_unified.c`) | 1 | 71/71 PASS | ✅ Conformant |
| Rust | — | — | Not available |

---

## 12. Open Questions

The following items require fleet discussion and/or Oracle1 decision before finalizing:

### 12.1 Design Decisions

| # | Question | Proposed Answer | Needs |
|---|---------|----------------|-------|
| 1 | Should sub-opcodes support nested escape (sub_opcode=0xFF → further dispatch)? | **No.** 256 per extension is ample. Allocate a second ext_id if needed. | Confirmation |
| 2 | Extension IDs: globally unique or per-agent? | **Globally unique**, with 256 IDs + experimental self-registration for informal use | Confirmation |
| 3 | How do extensions interact with confidence registers? | Extension manifest declares `confidence_aware: true/false`. If true, writes both value and confidence registers | Confirmation |
| 4 | NULL extension (0x00): support any sub-opcodes? | **Yes, all 256 sub-opcodes act as NOP.** Enables bytecode padding. | Confirmation |
| 5 | Should 0xFC–0xFE be assigned now or held in reserve? | **Held in reserve.** Security spec left them free; no strong use case yet. Better to allocate under pressure than prematurely. | Fleet vote |
| 6 | Should CAP_INVOKE be an explicit opcode or purely interpreter-level? | **Interpreter-level.** See Section 7.2 for rationale. | Confirmation |

### 12.2 Implementation Questions

| # | Question | Status |
|---|---------|--------|
| 7 | Minimum memory size for sandbox regions? | Open (proposed: 256B max for tier 1, 64KB for tier 3) |
| 8 | Max fibers for EXT_TEMPORAL? | Open (proposed: 8 for tier 1, 64 for tier 3) |
| 9 | Persistence format for CONF_CLAMP — per-register or bulk? | Open (spec says bulk — all 16 registers) |
| 10 | Thread-safety model for CAP_INVOKE in multi-threaded VM? | Open (single-threaded assumed for v3) |
| 11 | Should EXT_SECURITY (0x05) duplicate base-ISA security opcodes? | Open (proposed: no — base slots are authoritative) |

### 12.3 Fleet Governance

| # | Question | Status |
|---|---------|--------|
| 12 | Who approves fleet-standard extensions? | Oracle1 (proposed) |
| 13 | Review period for new extensions? | 1 week (proposed) |
| 14 | Extension versioning across ISA minor versions? | Semver, with `isa_min_version` field |
| 15 | How to handle extension conflicts between agents? | CAPS/CAPS_ACK negotiation (see Section 6.3) |

---

## 13. Cross-References

| Document | Location | Relationship |
|----------|----------|--------------|
| `isa_unified.py` | `src/flux/bytecode/` | v2 source of truth (247 opcodes) |
| `formats.py` | `src/flux/bytecode/` | v2 format definitions (A–G) |
| `isa-v3-escape-prefix-spec.md` | `docs/` | Escape prefix design (Format H, extensions, discovery) |
| `isa-v3-address-map.md` | `docs/` | Address map by domain (v2 → v3 reconciliation) |
| `security-primitives-spec.md` | `docs/` | Full security spec (SEC-001, sandbox, tags, verification) |
| `async-temporal-primitives-spec.md` | `docs/` | Full async/temporal spec (ASYNC-001, TEMP-001, fibers) |
| `conformance-report-2026-04-12.md` | `docs/` | v2 analysis, bifurcation, 20/23 test results |
| `conformance-cross-runtime-report.md` | `docs/` | Cross-runtime: Python+C both 71/71 PASS |
| `unified_interpreter.py` | `src/flux/vm/` | Python reference implementation (Tier 1) |
| `flux_vm_unified.c` | `src/flux/vm/c/` | C reference implementation (Tier 1) |
| `test_conformance.py` | `tests/` | Original 23 conformance vectors |
| `test_conformance_expanded.py` | `tests/` | Expanded 74 conformance vectors |
| `conformance_runner.py` | `tools/` | Multi-runtime test runner |

---

## Appendix A: Statistics

| Metric | v2 | v3 |
|--------|----|----|
| Base opcode slots | 256 | 256 (unchanged) |
| Defined base opcodes | 247 | 253 (+6 security) |
| Reserved base slots | 9 | 3 (0xFC–0xFE) |
| Extension space | 0 | **65,536** (256 ext × 256 sub) |
| Fleet-standard extension slots | 0 | 127 (0x01–0x7F) |
| Experimental extension slots | 0 | 112 (0x80–0xEF) |
| Meta-extension slots | 0 | 16 (0xF0–0xFF) |
| Instruction formats | 7 (A–G) | **8** (A–H) |
| Security opcodes | 0 | 6 (SANDBOX_ALLOC/FREE, TAG_ALLOC/TRANSFER/CHECK, CONF_CLAMP) |
| Async/temporal opcodes | 0 | 11 (via EXT_TEMPORAL 0x06) |
| Conformance vectors | 74 | **114** (74 base + 7 escape + 18 security + 15 async/temporal) |
| Backward compatible | — | 100% (v2 bytecode runs unmodified) |
| Cross-runtime conformance | — | Python + C: 71/71, 0 disagreements |

---

## Appendix B: Key Design Principles

1. **Backward compatibility is non-negotiable.** No v2 opcode address changes. The only byte
   that changes meaning is 0xFF (ILLEGAL → ESCAPE_PREFIX), and no valid v2 program contains it.

2. **Security cannot be optional.** Security opcodes live in the base ISA so they cannot
   be stripped by the extension negotiation protocol. This is a deliberate architectural
   decision — see Section 4.3.

3. **Extensions reuse base formats.** Extension operands use the same Format A–G encoding as
   the base ISA. This minimizes decoder changes across all three runtime languages.

4. **Capability enforcement is interpreter-level.** Agents cannot execute "capability check"
   instructions. The interpreter enforces permissions transparently before dispatching
   privileged opcodes.

5. **Defense in depth.** Confidence sanitization on every write, implicit tag checks on every
   LOAD/STORE, 4-stage bytecode verification — multiple independent layers of security.

6. **Graceful degradation.** Extension negotiation (CAPS/CAPS_ACK) allows agents with
   different extension sets to interoperate. VER_EXT enables runtime capability checks with
   fallback code paths.

7. **Confidence computing is first-class.** Parallel confidence register file, confidence-aware
   opcodes, confidence propagation rules that guarantee monotonic bounded decay, and trust
   poisoning prevention baked into every confidence write path.

---

*End of ISA v3 Draft. Submit fleet review requests to Oracle1 via flux-runtime issues.*
