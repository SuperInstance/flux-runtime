# ISA v3 Opcode Address Map

**Task ID:** 15b  
**Author:** Super Z (Cartographer)  
**Date:** 2026-04-12  
**Status:** DRAFT — Reconciles Oracle1's v3 proposal with current v2 unified ISA  

---

## 1. Overview

This document presents the **ISA v3 opcode address map**, reconciling two proposals:

1. **Oracle1's v3 proposal** (from `2026-04-11_isa-convergence-response.md`) — a clean
   reorganization by functional domain
2. **Current v2 unified ISA** (from `isa_unified.py`) — 247 opcodes organized by
   encoding format (Formats A-G)

The v3 map **preserves all 247 v2 opcode assignments** for backward compatibility,
and adds the 0xFF escape prefix mechanism (see `isa-v3-escape-prefix-spec.md`).

### Key Principle: Address Stability

> "v2 programs run unmodified on v3 VMs." This requires **zero changes** to any
> existing opcode address. The v3 map is a *documentation reorganization*, not a
> renumbering. New capabilities come exclusively through the escape prefix.

---

## 2. v3 Functional Domain Map

The following table shows how the 256-byte opcode space maps to functional domains.
Opcode addresses are shown in hex. The "v2 Status" column indicates whether the
address is currently defined, reserved, or the new escape prefix.

```
┌────────────┬─────────────────────────────────────────────┬──────────┬──────────┐
│ Range      │ Domain                                      │ Opcodes  │ v2 Status│
├────────────┼─────────────────────────────────────────────┼──────────┼──────────┤
│ 0x00-0x07  │ System Control + Interrupt                  │ 8 (8)    │ ✅ Defined│
│ 0x08-0x0F  │ Single Register Ops (INC, DEC, PUSH, POP)  │ 8 (8)    │ ✅ Defined│
│ 0x10-0x17  │ Immediate-Only Ops (SYS, TRAP, SEMA)       │ 8 (8)    │ ✅ Defined│
│ 0x18-0x1F  │ Register + Imm8 (MOVI, ADDI, logic imm)    │ 8 (8)    │ ✅ Defined│
│ 0x20-0x2F  │ Integer Arithmetic + Comparison            │ 16 (16)  │ ✅ Defined│
│ 0x30-0x3F  │ Float, Memory, Control Flow                │ 16 (16)  │ ✅ Defined│
│ 0x40-0x47  │ Register + Imm16 (MOVI16, JMP, JAL)       │ 8 (8)    │ ✅ Defined│
│ 0x48-0x4F  │ Register + Register + Imm16 (LOAD/STORE)  │ 8 (8)    │ ✅ Defined│
│ 0x50-0x5F  │ Agent-to-Agent Signal (TELL, ASK, FORK)   │ 16 (16)  │ ✅ Defined│
│ 0x60-0x6F  │ Confidence-Aware Variants (C_ADD, C_MUL)  │ 16 (16)  │ ✅ Defined│
│ 0x70-0x7F  │ Viewpoint Operations (Babel Domain)        │ 16 (16)  │ ✅ Defined│
│ 0x80-0x8F  │ Biology/Sensor Ops (JetsonClaw1 Domain)   │ 16 (16)  │ ✅ Defined│
│ 0x90-0x9F  │ Extended Math + Crypto                     │ 16 (16)  │ ✅ Defined│
│ 0xA0-0xAF  │ String/Collection Ops                      │ 16 (16)  │ ✅ Defined│
│ 0xB0-0xBF  │ Vector/SIMD Ops                            │ 16 (16)  │ ✅ Defined│
│ 0xC0-0xCF  │ Tensor/Neural Ops                          │ 16 (16)  │ ✅ Defined│
│ 0xD0-0xDF  │ Extended Memory/Mapped I/O + GPU           │ 16 (15)  │ ✅ Def    │
│ 0xE0-0xEF  │ Long Jumps, Calls, Coroutine, Fault        │ 16 (13)  │ ✅ Def    │
│ 0xF0-0xF7  │ Extended System (HALT_ERR, VER, CLK, etc) │ 8 (8)    │ ✅ Defined│
│ 0xF8-0xFE  │ System (WDOG, SLEEP, Reserved)             │ 7 (3)    │ ⚠️ Part   │
│ 0xFF       │ Escape Prefix → [ext_id][sub_opcode]       │ ∞        │ 🆕 v3 NEW │
├────────────┼─────────────────────────────────────────────┼──────────┼──────────┤
│ TOTAL      │                                             │ 247 + ∞  │          │
└────────────┴─────────────────────────────────────────────┴──────────┴──────────┘
```

**Legend:** ✅ Defined = all addresses assigned | ⚠️ Partial = some reserved | 🆕 New = v3 addition

---

## 3. Detailed Address Map by Domain

### 3.1 System Control (0x00-0x07) — Format A

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x00 | HALT | A | system | converged | Stop execution |
| 0x01 | NOP | A | system | converged | No operation (pipeline sync) |
| 0x02 | RET | A | system | oracle1 | Return from subroutine |
| 0x03 | IRET | A | system | jetsonclaw1 | Return from interrupt handler |
| 0x04 | BRK | A | debug | converged | Breakpoint (trap to debugger) |
| 0x05 | WFI | A | system | jetsonclaw1 | Wait for interrupt (low-power idle) |
| 0x06 | RESET | A | system | jetsonclaw1 | Soft reset of register file |
| 0x07 | SYN | A | system | jetsonclaw1 | Memory barrier / synchronize |

### 3.2 Single Register Ops (0x08-0x0F) — Format B

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x08 | INC | B | arithmetic | converged | rd = rd + 1 |
| 0x09 | DEC | B | arithmetic | converged | rd = rd - 1 |
| 0x0A | NOT | B | arithmetic | converged | rd = ~rd (bitwise NOT) |
| 0x0B | NEG | B | arithmetic | converged | rd = -rd (arithmetic negate) |
| 0x0C | PUSH | B | stack | converged | Push rd onto stack |
| 0x0D | POP | B | stack | converged | Pop stack into rd |
| 0x0E | CONF_LD | B | confidence | converged | Load confidence register rd to accumulator |
| 0x0F | CONF_ST | B | confidence | converged | Store confidence accumulator to register rd |

### 3.3 Immediate-Only Ops (0x10-0x17) — Format C

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x10 | SYS | C | system | converged | System call with code imm8 |
| 0x11 | TRAP | C | system | jetsonclaw1 | Software interrupt vector imm8 |
| 0x12 | DBG | C | debug | converged | Debug print register imm8 |
| 0x13 | CLF | C | system | oracle1 | Clear flags register bits imm8 |
| 0x14 | SEMA | C | concurrency | jetsonclaw1 | Semaphore operation imm8 |
| 0x15 | YIELD | C | concurrency | converged | Yield execution for imm8 cycles |
| 0x16 | CACHE | C | system | jetsonclaw1 | Cache control (flush/invalidate) |
| 0x17 | STRIPCF | C | confidence | jetsonclaw1 | Strip confidence from next imm8 ops |

### 3.4 Register + Imm8 (0x18-0x1F) — Format D

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x18 | MOVI | D | move | converged | rd = sign_extend(imm8) |
| 0x19 | ADDI | D | arithmetic | converged | rd = rd + imm8 |
| 0x1A | SUBI | D | arithmetic | converged | rd = rd - imm8 |
| 0x1B | ANDI | D | logic | converged | rd = rd & imm8 |
| 0x1C | ORI | D | logic | converged | rd = rd \| imm8 |
| 0x1D | XORI | D | logic | converged | rd = rd ^ imm8 |
| 0x1E | SHLI | D | shift | converged | rd = rd << imm8 |
| 0x1F | SHRI | D | shift | converged | rd = rd >> imm8 |

### 3.5 Integer Arithmetic + Comparison (0x20-0x2F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x20 | ADD | E | arithmetic | converged | rd = rs1 + rs2 |
| 0x21 | SUB | E | arithmetic | converged | rd = rs1 - rs2 |
| 0x22 | MUL | E | arithmetic | converged | rd = rs1 * rs2 |
| 0x23 | DIV | E | arithmetic | converged | rd = rs1 / rs2 (signed) |
| 0x24 | MOD | E | arithmetic | converged | rd = rs1 % rs2 |
| 0x25 | AND | E | logic | converged | rd = rs1 & rs2 |
| 0x26 | OR | E | logic | converged | rd = rs1 \| rs2 |
| 0x27 | XOR | E | logic | converged | rd = rs1 ^ rs2 |
| 0x28 | SHL | E | shift | converged | rd = rs1 << rs2 |
| 0x29 | SHR | E | shift | converged | rd = rs1 >> rs2 |
| 0x2A | MIN | E | arithmetic | converged | rd = min(rs1, rs2) |
| 0x2B | MAX | E | arithmetic | converged | rd = max(rs1, rs2) |
| 0x2C | CMP_EQ | E | compare | converged | rd = (rs1 == rs2) ? 1 : 0 |
| 0x2D | CMP_LT | E | compare | converged | rd = (rs1 < rs2) ? 1 : 0 |
| 0x2E | CMP_GT | E | compare | converged | rd = (rs1 > rs2) ? 1 : 0 |
| 0x2F | CMP_NE | E | compare | converged | rd = (rs1 != rs2) ? 1 : 0 |

### 3.6 Float, Memory, Control Flow (0x30-0x3F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x30 | FADD | E | float | oracle1 | rd = f(rs1) + f(rs2) |
| 0x31 | FSUB | E | float | oracle1 | rd = f(rs1) - f(rs2) |
| 0x32 | FMUL | E | float | oracle1 | rd = f(rs1) * f(rs2) |
| 0x33 | FDIV | E | float | oracle1 | rd = f(rs1) / f(rs2) |
| 0x34 | FMIN | E | float | oracle1 | rd = fmin(rs1, rs2) |
| 0x35 | FMAX | E | float | oracle1 | rd = fmax(rs1, rs2) |
| 0x36 | FTOI | E | convert | oracle1 | rd = int(f(rs1)) |
| 0x37 | ITOF | E | convert | oracle1 | rd = float(rs1) |
| 0x38 | LOAD | E | memory | converged | rd = mem[rs1 + rs2] |
| 0x39 | STORE | E | memory | converged | mem[rs1 + rs2] = rd |
| 0x3A | MOV | E | move | converged | rd = rs1 |
| 0x3B | SWP | E | move | converged | swap(rd, rs1) |
| 0x3C | JZ | E | control | converged | if rd == 0: pc += rs1 |
| 0x3D | JNZ | E | control | converged | if rd != 0: pc += rs1 |
| 0x3E | JLT | E | control | converged | if rd < 0: pc += rs1 |
| 0x3F | JGT | E | control | converged | if rd > 0: pc += rs1 |

### 3.7 Register + Imm16 (0x40-0x47) — Format F

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x40 | MOVI16 | F | move | converged | rd = imm16 |
| 0x41 | ADDI16 | F | arithmetic | converged | rd = rd + imm16 |
| 0x42 | SUBI16 | F | arithmetic | converged | rd = rd - imm16 |
| 0x43 | JMP | F | control | converged | pc += imm16 (relative) |
| 0x44 | JAL | F | control | converged | rd = pc; pc += imm16 |
| 0x45 | CALL | F | control | jetsonclaw1 | push(pc); pc = rd + imm16 |
| 0x46 | LOOP | F | control | jetsonclaw1 | rd--; if rd > 0: pc -= imm16 |
| 0x47 | SELECT | F | control | oracle1 | pc += imm16 * rd (computed jump) |

### 3.8 Register + Register + Imm16 (0x48-0x4F) — Format G

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x48 | LOADOFF | G | memory | converged | rd = mem[rs1 + imm16] |
| 0x49 | STOREOFF | G | memory | converged | mem[rs1 + imm16] = rd |
| 0x4A | LOADI | G | memory | jetsonclaw1 | rd = mem[mem[rs1] + imm16] |
| 0x4B | STOREI | G | memory | jetsonclaw1 | mem[mem[rs1] + imm16] = rd |
| 0x4C | ENTER | G | stack | jetsonclaw1 | push regs; sp -= imm16 |
| 0x4D | LEAVE | G | stack | jetsonclaw1 | sp += imm16; pop regs |
| 0x4E | COPY | G | memory | jetsonclaw1 | memcpy(rd, rs1, imm16) |
| 0x4F | FILL | G | memory | jetsonclaw1 | memset(rd, rs1, imm16) |

### 3.9 Agent-to-Agent Signal (0x50-0x5F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x50 | TELL | E | a2a | converged | Send rs2 to agent rs1, tag rd |
| 0x51 | ASK | E | a2a | converged | Request rs2 from agent rs1 |
| 0x52 | DELEG | E | a2a | converged | Delegate task rs2 to agent rs1 |
| 0x53 | BCAST | E | a2a | converged | Broadcast rs2 to fleet, tag rd |
| 0x54 | ACCEPT | E | a2a | converged | Accept delegated task |
| 0x55 | DECLINE | E | a2a | converged | Decline task with reason rs2 |
| 0x56 | REPORT | E | a2a | converged | Report task status rs2 to rd |
| 0x57 | MERGE | E | a2a | converged | Merge results from rs1, rs2 |
| 0x58 | FORK | E | a2a | converged | Spawn child agent, state→rd |
| 0x59 | JOIN | E | a2a | converged | Wait for child rs1, result→rd |
| 0x5A | SIGNAL | E | a2a | converged | Emit named signal rs2 on channel rd |
| 0x5B | AWAIT | E | a2a | converged | Wait for signal rs2, data→rd |
| 0x5C | TRUST | E | a2a | converged | Set trust level rs2 for agent rs1 |
| 0x5D | DISCOV | E | a2a | oracle1 | Discover fleet agents, list→rd |
| 0x5E | STATUS | E | a2a | converged | Query agent rs1 status |
| 0x5F | HEARTBT | E | a2a | converged | Emit heartbeat, load→rd |

### 3.10 Confidence-Aware Variants (0x60-0x6F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x60 | C_ADD | E | confidence | converged | rd = rs1+rs2, crd=min(crs1,crs2) |
| 0x61 | C_SUB | E | confidence | converged | rd = rs1-rs2, crd=min(crs1,crs2) |
| 0x62 | C_MUL | E | confidence | converged | rd = rs1*rs2, crd=crs1*crs2 |
| 0x63 | C_DIV | E | confidence | converged | rd = rs1/rs2, crd=crs1*crs2*(1-ε) |
| 0x64 | C_FADD | E | confidence | oracle1 | Float add + confidence propagation |
| 0x65 | C_FSUB | E | confidence | oracle1 | Float sub + confidence propagation |
| 0x66 | C_FMUL | E | confidence | oracle1 | Float mul + confidence propagation |
| 0x67 | C_FDIV | E | confidence | oracle1 | Float div + confidence propagation |
| 0x68 | C_MERGE | E | confidence | converged | Merge confidences: crd=weighted_avg |
| 0x69 | C_THRESH | D | confidence | converged | Skip next if crd < imm8/255 |
| 0x6A | C_BOOST | E | confidence | jetsonclaw1 | Boost crd by rs2 factor (max 1.0) |
| 0x6B | C_DECAY | E | confidence | jetsonclaw1 | Decay crd by factor rs2 per cycle |
| 0x6C | C_SOURCE | E | confidence | jetsonclaw1 | Set confidence source type |
| 0x6D | C_CALIB | E | confidence | converged | Calibrate confidence vs ground truth |
| 0x6E | C_EXPLY | E | confidence | oracle1 | Apply confidence to control flow weight |
| 0x6F | C_VOTE | E | confidence | converged | Weighted vote: crd = sum(crs*crs_i)/Σ |

### 3.11 Viewpoint Operations — Babel Domain (0x70-0x7F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x70 | V_EVID | E | viewpoint | babel | Evidentiality: source type |
| 0x71 | V_EPIST | E | viewpoint | babel | Epistemic stance |
| 0x72 | V_MIR | E | viewpoint | babel | Mirative: unexpectedness |
| 0x73 | V_NEG | E | viewpoint | babel | Negation scope |
| 0x74 | V_TENSE | E | viewpoint | babel | Temporal viewpoint |
| 0x75 | V_ASPEC | E | viewpoint | babel | Aspectual viewpoint |
| 0x76 | V_MODAL | E | viewpoint | babel | Modal force |
| 0x77 | V_POLIT | E | viewpoint | babel | Politeness register |
| 0x78 | V_HONOR | E | viewpoint | babel | Honorific → trust tier |
| 0x79 | V_TOPIC | E | viewpoint | babel | Topic-comment structure |
| 0x7A | V_FOCUS | E | viewpoint | babel | Information focus |
| 0x7B | V_CASE | E | viewpoint | babel | Case-based scope |
| 0x7C | V_AGREE | E | viewpoint | babel | Agreement (gender/number) |
| 0x7D | V_CLASS | E | viewpoint | babel | Classifier → type mapping |
| 0x7E | V_INFL | E | viewpoint | babel | Inflection → control flow |
| 0x7F | V_PRAGMA | E | viewpoint | babel | Pragmatic context switch |

### 3.12 Biology/Sensor Ops — JetsonClaw1 Domain (0x80-0x8F) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x80 | SENSE | E | sensor | jetsonclaw1 | Read sensor rs1, channel rs2→rd |
| 0x81 | ACTUATE | E | sensor | jetsonclaw1 | Write rd to actuator rs1, ch rs2 |
| 0x82 | SAMPLE | E | sensor | jetsonclaw1 | Sample ADC channel rs1, avg rs2 |
| 0x83 | ENERGY | E | sensor | jetsonclaw1 | Energy budget query |
| 0x84 | TEMP | E | sensor | jetsonclaw1 | Temperature sensor read |
| 0x85 | GPS | E | sensor | jetsonclaw1 | GPS coordinates |
| 0x86 | ACCEL | E | sensor | jetsonclaw1 | Accelerometer (3-axis) |
| 0x87 | DEPTH | E | sensor | jetsonclaw1 | Depth/pressure sensor |
| 0x88 | CAMCAP | E | sensor | jetsonclaw1 | Capture camera frame |
| 0x89 | CAMDET | E | sensor | jetsonclaw1 | Run detection on buffer |
| 0x8A | PWM | E | sensor | jetsonclaw1 | PWM output |
| 0x8B | GPIO | E | sensor | jetsonclaw1 | GPIO read/write |
| 0x8C | I2C | E | sensor | jetsonclaw1 | I2C communication |
| 0x8D | SPI | E | sensor | jetsonclaw1 | SPI communication |
| 0x8E | UART | E | sensor | jetsonclaw1 | UART communication |
| 0x8F | CANBUS | E | sensor | jetsonclaw1 | CAN bus communication |

### 3.13 Extended Math + Crypto (0x90-0x9F) — Format E/D

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0x90 | ABS | E | math | converged | rd = \|rs1\| |
| 0x91 | SIGN | E | math | converged | rd = sign(rs1) |
| 0x92 | SQRT | E | math | oracle1 | rd = sqrt(rs1) |
| 0x93 | POW | E | math | oracle1 | rd = rs1 ^ rs2 |
| 0x94 | LOG2 | E | math | oracle1 | rd = log2(rs1) |
| 0x95 | CLZ | E | math | jetsonclaw1 | Count leading zeros |
| 0x96 | CTZ | E | math | jetsonclaw1 | Count trailing zeros |
| 0x97 | POPCNT | E | math | jetsonclaw1 | Population count |
| 0x98 | CRC32 | E | crypto | jetsonclaw1 | CRC32 hash |
| 0x99 | SHA256 | E | crypto | converged | SHA-256 block |
| 0x9A | RND | E | math | converged | Random in [rs1, rs2] |
| 0x9B | SEED | E | math | converged | Seed PRNG |
| 0x9C | FMOD | E | float | oracle1 | Float modulo |
| 0x9D | FSQRT | E | float | oracle1 | Float square root |
| 0x9E | FSIN | E | float | oracle1 | Sine |
| 0x9F | FCOS | E | float | oracle1 | Cosine |

### 3.14 String/Collection Ops (0xA0-0xAF) — Format D/E/G

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xA0 | LEN | D | collection | oracle1 | Length of collection imm8 |
| 0xA1 | CONCAT | E | collection | oracle1 | Concatenate rs1, rs2 |
| 0xA2 | AT | E | collection | oracle1 | Index: rd = rs1[rs2] |
| 0xA3 | SETAT | E | collection | oracle1 | Set: rs1[rs2] = rd |
| 0xA4 | SLICE | G | collection | oracle1 | Slice: rd = rs1[0:imm16] |
| 0xA5 | REDUCE | E | collection | oracle1 | Fold reduction |
| 0xA6 | MAP | E | collection | oracle1 | Map function |
| 0xA7 | FILTER | E | collection | oracle1 | Filter collection |
| 0xA8 | SORT | E | collection | oracle1 | Sort collection |
| 0xA9 | FIND | E | collection | oracle1 | Find index of element |
| 0xAA | HASH | E | crypto | converged | Hash with algorithm rs2 |
| 0xAB | HMAC | E | crypto | converged | HMAC signature |
| 0xAC | VERIFY | E | crypto | converged | Verify signature |
| 0xAD | ENCRYPT | E | crypto | converged | Encrypt with key rs2 |
| 0xAE | DECRYPT | E | crypto | converged | Decrypt with key rs2 |
| 0xAF | KEYGEN | E | crypto | converged | Generate keypair |

### 3.15 Vector/SIMD Ops (0xB0-0xBF) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xB0 | VLOAD | E | vector | jetsonclaw1 | Load vector from memory |
| 0xB1 | VSTORE | E | vector | jetsonclaw1 | Store vector to memory |
| 0xB2 | VADD | E | vector | jetsonclaw1 | Vector add |
| 0xB3 | VMUL | E | vector | jetsonclaw1 | Vector multiply |
| 0xB4 | VDOT | E | vector | jetsonclaw1 | Dot product |
| 0xB5 | VNORM | E | vector | jetsonclaw1 | L2 norm |
| 0xB6 | VSCALE | E | vector | jetsonclaw1 | Scalar multiply |
| 0xB7 | VMAXP | E | vector | jetsonclaw1 | Element-wise max |
| 0xB8 | VMINP | E | vector | jetsonclaw1 | Element-wise min |
| 0xB9 | VREDUCE | E | vector | jetsonclaw1 | Reduce with operation |
| 0xBA | VGATHER | E | vector | jetsonclaw1 | Gather load |
| 0xBB | VSCATTER | E | vector | jetsonclaw1 | Scatter store |
| 0xBC | VSHUF | E | vector | jetsonclaw1 | Shuffle lanes |
| 0xBD | VMERGE | E | vector | jetsonclaw1 | Merge by mask |
| 0xBE | VCONF | E | vector | jetsonclaw1 | Vector confidence propagation |
| 0xBF | VSELECT | E | vector | jetsonclaw1 | Conditional select by confidence |

### 3.16 Tensor/Neural Ops (0xC0-0xCF) — Format E

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xC0 | TMATMUL | E | tensor | jetsonclaw1 | Matrix multiply |
| 0xC1 | TCONV | E | tensor | jetsonclaw1 | 2D convolution |
| 0xC2 | TPOOL | E | tensor | jetsonclaw1 | Max/avg pooling |
| 0xC3 | TRELU | E | tensor | jetsonclaw1 | ReLU activation |
| 0xC4 | TSIGM | E | tensor | jetsonclaw1 | Sigmoid activation |
| 0xC5 | TSOFT | E | tensor | jetsonclaw1 | Softmax |
| 0xC6 | TLOSS | E | tensor | jetsonclaw1 | Loss function |
| 0xC7 | TGRAD | E | tensor | jetsonclaw1 | Gradient computation |
| 0xC8 | TUPDATE | E | tensor | jetsonclaw1 | SGD parameter update |
| 0xC9 | TADAM | E | tensor | jetsonclaw1 | Adam optimizer step |
| 0xCA | TEMBED | E | tensor | jetsonclaw1 | Embedding lookup |
| 0xCB | TATTN | E | tensor | jetsonclaw1 | Self-attention |
| 0xCC | TSAMPLE | E | tensor | jetsonclaw1 | Sample from distribution |
| 0xCD | TTOKEN | E | tensor | oracle1 | Tokenize text |
| 0xCE | TDETOK | E | tensor | oracle1 | Detokenize tokens |
| 0xCF | TQUANT | E | tensor | jetsonclaw1 | Quantize fp32 → int8 |

### 3.17 Extended Memory/Mapped I/O + GPU (0xD0-0xDF) — Format G

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xD0 | DMA_CPY | G | memory | jetsonclaw1 | DMA copy |
| 0xD1 | DMA_SET | G | memory | jetsonclaw1 | DMA fill |
| 0xD2 | MMIO_R | G | memory | jetsonclaw1 | Memory-mapped I/O read |
| 0xD3 | MMIO_W | G | memory | jetsonclaw1 | Memory-mapped I/O write |
| 0xD4 | ATOMIC | G | memory | jetsonclaw1 | Atomic read-modify-write |
| 0xD5 | CAS | G | memory | jetsonclaw1 | Compare-and-swap |
| 0xD6 | FENCE | G | memory | jetsonclaw1 | Memory fence (acq/rel/full) |
| 0xD7 | MALLOC | G | memory | oracle1 | Allocate heap memory |
| 0xD8 | FREE | G | memory | oracle1 | Free heap memory |
| 0xD9 | MPROT | G | memory | jetsonclaw1 | Memory protect (flags) |
| 0xDA | MCACHE | G | memory | jetsonclaw1 | Cache management |
| 0xDB | GPU_LD | G | memory | jetsonclaw1 | GPU memory load |
| 0xDC | GPU_ST | G | memory | jetsonclaw1 | GPU memory store |
| 0xDD | GPU_EX | G | compute | jetsonclaw1 | GPU kernel execute |
| 0xDE | GPU_SYNC | G | compute | jetsonclaw1 | GPU synchronize |
| 0xDF | — | G | reserved | — | **Reserved** |

### 3.18 Long Jumps, Calls, Coroutine, Fault (0xE0-0xEF) — Format F

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xE0 | JMPL | F | control | converged | Long relative jump |
| 0xE1 | JALL | F | control | converged | Long jump-and-link |
| 0xE2 | CALLL | F | control | converged | Long call |
| 0xE3 | TAIL | F | control | oracle1 | Tail call |
| 0xE4 | SWITCH | F | control | jetsonclaw1 | Context switch |
| 0xE5 | COYIELD | F | control | oracle1 | Coroutine yield |
| 0xE6 | CORESUM | F | control | oracle1 | Coroutine resume |
| 0xE7 | FAULT | F | system | jetsonclaw1 | Raise fault code imm16 |
| 0xE8 | HANDLER | F | system | jetsonclaw1 | Install fault handler |
| 0xE9 | TRACE | F | debug | converged | Trace: log rd, tag imm16 |
| 0xEA | PROF_ON | F | debug | jetsonclaw1 | Start profiling |
| 0xEB | PROF_OFF | F | debug | jetsonclaw1 | End profiling |
| 0xEC | WATCH | F | debug | converged | Watchpoint |
| 0xED | — | F | reserved | — | **Reserved** |
| 0xEE | — | F | reserved | — | **Reserved** |
| 0xEF | — | F | reserved | — | **Reserved** |

### 3.19 Extended System (0xF0-0xF7) — Format A

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xF0 | HALT_ERR | A | system | converged | Halt with error |
| 0xF1 | REBOOT | A | system | jetsonclaw1 | Warm reboot |
| 0xF2 | DUMP | A | debug | converged | Dump register file |
| 0xF3 | ASSERT | A | debug | converged | Assert flags |
| 0xF4 | ID | A | system | oracle1 | Return agent ID to R0 |
| 0xF5 | VER | A | system | converged | Return ISA version to R0 |
| 0xF6 | CLK | A | system | jetsonclaw1 | Return clock cycle count |
| 0xF7 | PCLK | A | system | jetsonclaw1 | Performance counter |

### 3.20 System Reserved (0xF8-0xFE) — Format A

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xF8 | WDOG | A | system | jetsonclaw1 | Kick watchdog timer |
| 0xF9 | SLEEP | A | system | jetsonclaw1 | Low-power sleep |
| 0xFA | — | A | reserved | — | **Reserved** |
| 0xFB | — | A | reserved | — | **Reserved** |
| 0xFC | — | A | reserved | — | **Reserved** |
| 0xFD | — | A | reserved | — | **Reserved** |
| 0xFE | — | A | reserved | — | **Reserved** |

### 3.21 Escape Prefix (0xFF) — Format H (NEW in v3)

| Addr | Mnemonic | Format | Category | Source | Description |
|------|----------|--------|----------|--------|-------------|
| 0xFF | ESCAPE | H | system | converged | **Escape prefix** → [ext_id][sub_opcode][operands...] |

See `isa-v3-escape-prefix-spec.md` for full specification.

---

## 4. Extension Address Map

Extensions are addressed via the escape prefix: `0xFF [ext_id] [sub_opcode]`

### 4.1 Fleet-Standard Extension IDs (0x01-0x7F)

| ext_id | Name | Domain | Owner | Status |
|--------|------|--------|-------|--------|
| 0x00 | NULL | Passthrough/NOP | System | Reserved |
| 0x01 | EXT_BABEL | Multilingual linguistics | Babel | Proposed |
| 0x02 | EXT_EDGE | Sensor/actuator/edge | JetsonClaw1 | Proposed |
| 0x03 | EXT_CONFIDENCE | Advanced confidence | Fleet | Proposed |
| 0x04 | EXT_TENSOR | Tensor/neural advanced | JC1 + Oracle1 | Proposed |
| 0x05 | EXT_SECURITY | Capability enforcement | Fleet | Proposed |
| 0x06 | EXT_TEMPORAL | Deadlines/persist/time | Fleet | Proposed |
| 0x07-0x7F | Unassigned | — | — | Available |

### 4.2 Experimental Extension IDs (0x80-0xEF)

| Range | Name | Notes |
|-------|------|-------|
| 0x80-0x8F | Agent-private | For individual agent experiments |
| 0x90-0x9F | Vendor-specific | Third-party hardware vendor extensions |
| 0xA0-0xEF | Self-assigned | Register in fleet registry to avoid collisions |

### 4.3 Meta-Extension IDs (0xF0-0xFF)

| ext_id | Name | Purpose |
|--------|------|---------|
| 0xF0 | VER_EXT | Query extension availability (runtime) |
| 0xF1 | LOAD_EXT | Hot-load extension at runtime |
| 0xF2 | UNLOAD_EXT | Unload extension |
| 0xF3 | EXT_INFO | Get extension metadata |
| 0xF4-0xFF | Reserved | Future meta-extensions |

---

## 5. Address Space Visualization

```
 0x00 ┌──────────────────────────────────────┐
     │  System Control + Interrupt (8 ops)   │
 0x08 ├──────────────────────────────────────┤
     │  Single Register (8 ops)              │
 0x10 ├──────────────────────────────────────┤
     │  Immediate-Only (8 ops)               │
 0x18 ├──────────────────────────────────────┤
     │  Register + Imm8 (8 ops)              │
 0x20 ├──────────────────────────────────────┤
     │  Integer Arith + Compare (16 ops)     │
 0x30 ├──────────────────────────────────────┤
     │  Float, Memory, Control (16 ops)      │
 0x40 ├──────────────────────────────────────┤
     │  Register + Imm16 (8 ops)             │
 0x48 ├──────────────────────────────────────┤
     │  Reg+Reg+Imm16 (8 ops)                │
 0x50 ├──────────────────────────────────────┤
     │  A2A Signal (16 ops)                  │
 0x60 ├──────────────────────────────────────┤
     │  Confidence-Aware (16 ops)            │
 0x70 ├──────────────────────────────────────┤
     │  Viewpoint / Babel (16 ops)           │
 0x80 ├──────────────────────────────────────┤
     │  Sensor / JetsonClaw1 (16 ops)        │
 0x90 ├──────────────────────────────────────┤
     │  Extended Math + Crypto (16 ops)      │
 0xA0 ├──────────────────────────────────────┤
     │  String/Collection (16 ops)           │
 0xB0 ├──────────────────────────────────────┤
     │  Vector/SIMD (16 ops)                 │
 0xC0 ├──────────────────────────────────────┤
     │  Tensor/Neural (16 ops)               │
 0xD0 ├──────────────────────────────────────┤
     │  Memory/MMIO/GPU (16 ops)             │
 0xE0 ├──────────────────────────────────────┤
     │  Long Jump/Coroutine/Fault (16 ops)   │
 0xF0 ├──────────────────────────────────────┤
     │  Extended System (8 ops)              │
 0xF8 ├──────────────────────────────────────┤
     │  System (3 defined + 5 reserved)      │
 0xFF ├──────────────────────────────────────┤
     │  ★ ESCAPE PREFIX ★                    │
     │  → 65,536 extension opcodes           │
     └──────────────────────────────────────┘
```

---

## 6. Statistics

| Metric | v2 | v3 |
|--------|----|----|
| Base opcode slots | 256 | 256 (unchanged) |
| Base opcodes defined | 247 | 247 (unchanged) |
| Base opcodes reserved | 9 | 8 (0xFF reclaimed) |
| Extension slots | 0 | 256 extensions × 256 sub-opcodes = **65,536** |
| Fleet-standard extensions | 0 | 127 (0x01-0x7F) |
| Experimental extensions | 0 | 112 (0x80-0xEF) |
| Meta-extensions | 0 | 16 (0xF0-0xFF) |
| Format types | A-G (7) | A-H (8, H = escape prefix) |
| Backward compatible | — | 100% (v2 bytecode runs unmodified) |

---

## 7. Oracle1's Original Proposal vs. Current Map

Oracle1's v3 proposal reorganized the address space by functional domain. The
current v2 ISA is organized by encoding format (Formats A-G). Here is a comparison:

| Oracle1's Domain | Oracle1 Range | v2 Actual Range | Notes |
|------------------|---------------|-----------------|-------|
| System | 0x00-0x0F | 0x00-0x07 (sys) + 0x08-0x0F (reg) | Compatible — System + Register |
| Arithmetic | 0x10-0x2F | 0x18-0x1F (imm8) + 0x20-0x2F (arith) | Compatible — shifted by Format C |
| Logic + Comparison | 0x30-0x4F | 0x25-0x2F (logic) + 0x2C-0x2F (cmp) | Partially aligned |
| Memory | 0x50-0x6F | 0x38-0x39, 0x48-0x4F, 0xD0-0xDF | **Not aligned** — memory is spread |
| Control Flow | 0x70-0x8F | 0x3C-0x3F, 0x43-0x47, 0xE0-0xEF | **Not aligned** — control flow is spread |
| Stack | 0x90-0xAF | 0x0C-0x0D, 0x4C-0x4D | **Not aligned** — stack ops at 0x08+ |
| A2A Signal | 0xB0-0xCF | 0x50-0x5F | **Not aligned** — A2A at 0x50+ |
| Vocabulary | 0xD0-0xEF | 0x70-0x7F (viewpoint) | **Not aligned** — Babel at 0x70+ |
| Confidence | 0xF0-0xF7 | 0x60-0x6F, 0x0E-0x0F | **Not aligned** — confidence at 0x60+ |
| Reserved | 0xF8-0xFF | 0xFA-0xFE + 0xDF,0xED-0xEF | Multiple reserved pockets |
| Escape | 0xFF | 0xFF | **Aligned** — both agree on 0xFF |

### Reconciliation Decision

**The v3 map preserves v2 addresses.** Oracle1's domain-based organization is
adopted as a **documentation convention** (Section 3 labels each range by domain)
but opcode addresses remain at their v2 values. This avoids the massive migration
effort of renumbering 247 opcodes.

**Rationale:**
- Backward compatibility is non-negotiable (fleet-wide deployment)
- The format-based organization in v2 is actually useful for the decoder (format
  is determined by opcode range)
- New capabilities come through the escape prefix, not base-ISA reorganization
- A future ISA v4 *could* reorganize if needed, with a migration tool

---

## 8. Format Encoding Quick Reference

| Format | Bytes | Encoding | Used By |
|--------|-------|----------|---------|
| A | 1 | [op] | 0x00-0x07, 0xF0-0xFF |
| B | 2 | [op][rd] | 0x08-0x0F |
| C | 2 | [op][imm8] | 0x10-0x17 |
| D | 3 | [op][rd][imm8] | 0x18-0x1F, 0xA0 |
| E | 4 | [op][rd][rs1][rs2] | 0x20-0x6F, 0x80-0xBF, 0xC0-0xCF |
| F | 4 | [op][rd][imm16hi][imm16lo] | 0x40-0x47, 0xE0-0xEF |
| G | 5 | [op][rd][rs1][imm16hi][imm16lo] | 0x48-0x4F, 0xD0-0xDF |
| H | 3+ | [0xFF][ext_id][sub_opcode][operands...] | 0xFF (escape prefix) |

All multi-byte formats use **little-endian** for immediate fields.
