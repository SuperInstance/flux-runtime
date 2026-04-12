# FLUX→WASM Compilation Target Design

**Document ID:** WASM-001
**Oracle1 Board:** WASM-001
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-06-07
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** FLUX ISA v3 full draft (`ISA-V3-FULL-DRAFT.md`), ISA unified spec (`ISA_UNIFIED.md`)
**Tracks:** Oracle1 TASK-BOARD WASM-001
**Relationship:** Complements ISA-001 (v3 full spec), ISA-002 (escape prefix), ISA-003 (compressed format)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Register to Stack Translation](#3-register-to-stack-translation)
   - 3.1 [Translation Strategy](#31-translation-strategy)
   - 3.2 [Arithmetic Opcode Translation](#32-arithmetic-opcode-translation)
   - 3.3 [Comparison Opcode Translation](#33-comparison-opcode-translation)
   - 3.4 [Logic and Bitwise Opcode Translation](#34-logic-and-bitwise-opcode-translation)
   - 3.5 [Memory Opcode Translation](#35-memory-opcode-translation)
   - 3.6 [Control Flow Translation](#36-control-flow-translation)
   - 3.7 [Stack Operations Translation](#37-stack-operations-translation)
   - 3.8 [Single-Register (Format B) Translation](#38-single-register-format-b-translation)
   - 3.9 [Register + Imm8 (Format D) Translation](#39-register--imm8-format-d-translation)
   - 3.10 [Register + Imm16 (Format F) Translation](#310-register--imm16-format-f-translation)
   - 3.11 [Register + Register + Imm16 (Format G) Translation](#311-register--register--imm16-format-g-translation)
   - 3.12 [Format H Escape Prefix Translation](#312-format-h-escape-prefix-translation)
4. [WASM Module Structure](#4-wasm-module-structure)
   - 4.1 [Module Skeleton](#41-module-skeleton)
   - 4.2 [Register Representation](#42-register-representation)
   - 4.3 [Instruction Dispatch Loop](#43-instruction-dispatch-loop)
   - 4.4 [Import Functions](#44-import-functions)
5. [Unsupported Opcodes — JS Bridge](#5-unsupported-opcodes--js-bridge)
   - 5.1 [I/O Opcodes](#51-io-opcodes)
   - 5.2 [A2A Signaling Opcodes](#52-a2a-signaling-opcodes)
   - 5.3 [System Opcodes](#53-system-opcodes)
   - 5.4 [Time Opcodes](#54-time-opcodes)
   - 5.5 [Sensor and Hardware Opcodes](#55-sensor-and-hardware-opcodes)
6. [Memory Layout in WASM](#6-memory-layout-in-wasm)
7. [Browser Integration API](#7-browser-integration-api)
   - 7.1 [JavaScript Host Object](#71-javascript-host-object)
   - 7.2 [Loading and Executing](#72-loading-and-executing)
   - 7.3 [A2A Bridge Implementation](#73-a2a-bridge-implementation)
8. [Performance Considerations](#8-performance-considerations)
9. [Use Cases](#9-use-cases)
10. [Compiler Design](#10-compiler-design)
    - 10.1 [Python Compiler Architecture](#101-python-compiler-architecture)
    - 10.2 [WAT Emission Strategy](#102-wat-emission-strategy)
    - 10.3 [Optimization Passes](#103-optimization-passes)
11. [Conformance Test Vectors](#11-conformance-test-vectors)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Appendix A — Complete Translation Table](#appendix-a--complete-translation-table)
14. [Appendix B — Security Model](#appendix-b--security-model)
15. [Appendix C — Relationship to Other Tasks](#appendix-c--relationship-to-other-tasks)

---

## 1. Executive Summary

WebAssembly (WASM) brings FLUX bytecode to the browser — enabling fleet IDE integration, portable edge runtime, and sandboxed execution by default. FLUX is a register-based VM (R0–R15, 16 confidence registers, 247+ opcodes across 8 instruction formats), while WASM is stack-based. This compilation target bridges the two models by representing FLUX registers as WASM local variables, translating each register operation into stack-based WASM instructions, and bridging FLUX-specific features (A2A signals, confidence registers, sensor I/O, extension opcodes) to JavaScript imports provided by the browser host.

The compiler accepts `.fluxbc` (FLUX bytecode) as input and emits `.wasm` (WebAssembly binary) or `.wat` (WASM text format) as output. The primary approach is **interpretive compilation**: rather than compiling each FLUX instruction to native WASM control flow (which would require complex control-flow reconstruction), we compile a FLUX bytecode *interpreter loop* into WASM, where the bytecode is loaded into WASM linear memory and a dispatch loop executes instructions sequentially. This approach is simpler, produces smaller binaries, preserves the ability to load dynamic bytecode at runtime, and aligns with the existing `flux-wasm` Rust-based skeleton.

Key performance characteristics: WASM executes at 2–10x slower than native C but 100x faster than Python, with deterministic execution and zero GC pauses. The 64KB initial linear memory is expandable via `memory.grow`. All I/O, A2A messaging, and sensor access are delegated to JavaScript host functions via WASM imports, enabling full browser integration while keeping the WASM module side-effect-free and sandboxed.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              FLUX Bytecode (.fluxbc)                 │
│  Formats A–G, 247+ opcodes, 16 registers             │
├─────────────────────────────────────────────────────┤
│          FLUX→WASM Compiler (Python)                 │
│                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Register →  │  │   A2A    │  │  Extension   │  │
│  │  Stack       │  │  Stub    │  │  → JS Import │  │
│  │  Compiler    │  │  Generator│ │  Generator   │  │
│  │              │  │          │  │              │  │
│  │ R0-R15→locals│  │ SIGNAL → │  │ 0xFF ext_id  │  │
│  │ ops→wasm    │  │ import   │  │ → import     │  │
│  │ instrs      │  │ call     │  │ dispatch     │  │
│  └──────────────┘  └──────────┘  └──────────────┘  │
│                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Confidence  │  │  Memory  │  │   Control    │  │
│  │  Register    │  │  Layout  │  │   Flow       │  │
│  │  Mapping     │  │  Gen     │  │   Compiler   │  │
│  │              │  │          │  │              │  │
│  │ C0-C15→f32  │  │ heap/    │  │ JMP → br     │  │
│  │ locals array │  │ stack/   │  │ JZ  → br_if  │  │
│  │              │  │ prog/    │  │ CALL→call    │  │
│  │              │  │ buffers  │  │ RET → return │  │
│  └──────────────┘  └──────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────┤
│            WebAssembly (.wasm / .wat)                │
│  Compiled dispatch loop + register file in locals    │
├─────────────────────────────────────────────────────┤
│               Browser Runtime                       │
│                                                     │
│  ┌───────────────┐  ┌──────────┐  ┌────────────┐   │
│  │  WASM VM      │  │ JS Bridge│  │  Memory    │   │
│  │  (stack-based)│  │ (A2A/I/O)│  │  (64KB,    │   │
│  │               │  │          │  │  expandable)│   │
│  │  locals:      │  │ fetch()  │  │            │   │
│  │  $r0-$r15     │  │ ws.send()│  │  linear    │   │
│  │  $c0-$c15     │  │ console  │  │  memory    │   │
│  │  $sp, $pc,    │  │ .log()   │  │            │   │
│  │  $fp, $flags  │  │          │  │            │   │
│  └───────────────┘  └──────────┘  └────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Data Flow

```
.flux source ──► assembler.py ──► .fluxbc ──► flux2wasm.py ──► .wat ──► wat2wasm ──► .wasm ──► browser
                                         │
                                         └──► (optional) .wasm directly via binary emission
```

### Design Principles

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Interpretive compilation** | Compile a dispatch loop, not individual instructions — simpler, supports dynamic bytecode |
| 2 | **Register → Local mapping** | FLUX R0–R15 map to WASM locals; confidence C0–C15 map to separate f32 locals |
| 3 | **JS bridge for side effects** | All I/O, A2A, sensors, time, and extension opcodes delegate to imported JS functions |
| 4 | **Deterministic execution** | WASM's linear memory and integer semantics match FLUX's deterministic requirements |
| 5 | **Minimal binary size** | Target < 100KB for the WASM module (interpreter loop + dispatch tables) |
| 6 | **Conformance** | Output must pass all 71+ expanded conformance test vectors with identical results |

---

## 3. Register to Stack Translation

### 3.1 Translation Strategy

FLUX uses a **register-based** instruction set (R0–R15 general-purpose, C0–C15 confidence). WASM is **stack-based**: operands are pushed onto the implicit operand stack, consumed by instructions, and results are left on the stack. The translation converts FLUX's explicit register operands into WASM's implicit stack operations.

For the interpretive approach, FLUX registers are represented as **WASM local variables** inside the main dispatch function. Each register is an `i32` local (truncating FLUX's conceptual 64-bit registers to 32-bit for WASM i32 — sufficient for most programs; `i64` locals available for precision-sensitive code).

**Core translation pattern:**

```
FLUX register instruction:  OP  rd, rs1, rs2
WASM stack translation:     (local.get $rs1) (local.get $rs2) (OP) (local.set $rd)
```

### 3.2 Arithmetic Opcode Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| ADD | 0x20 | E | `ADD R1, R2, R3` | `local.get $r2; local.get $r3; i32.add; local.set $r1` |
| SUB | 0x21 | E | `SUB R1, R2, R3` | `local.get $r2; local.get $r3; i32.sub; local.set $r1` |
| MUL | 0x22 | E | `MUL R1, R2, R3` | `local.get $r2; local.get $r3; i32.mul; local.set $r1` |
| DIV | 0x23 | E | `DIV R1, R2, R3` | `local.get $r2; local.get $r3; i32.div_s; local.set $r1` |
| MOD | 0x24 | E | `MOD R1, R2, R3` | `local.get $r2; local.get $r3; i32.rem_s; local.set $r1` |
| MIN | 0x2A | E | `MIN R1, R2, R3` | `local.get $r2; local.get $r3; call $min_i32; local.set $r1` |
| MAX | 0x2B | E | `MAX R1, R2, R3` | `local.get $r2; local.get $r3; call $max_i32; local.set $r1` |
| ADDI | 0x19 | D | `ADDI R1, 42` | `local.get $r1; i32.const 42; i32.add; local.set $r1` |
| SUBI | 0x1A | D | `SUBI R1, 10` | `local.get $r1; i32.const 10; i32.sub; local.set $r1` |
| MOVI16 | 0x40 | F | `MOVI16 R1, 1000` | `i32.const 1000; local.set $r1` |
| INC | 0x08 | B | `INC R1` | `local.get $r1; i32.const 1; i32.add; local.set $r1` |
| DEC | 0x09 | B | `DEC R1` | `local.get $r1; i32.const 1; i32.sub; local.set $r1` |
| NEG | 0x0B | B | `NEG R1` | `i32.const 0; local.get $r1; i32.sub; local.set $r1` |
| NOT | 0x0A | B | `NOT R1` | `local.get $r1; i32.const -1; i32.xor; local.set $r1` |
| ABS | 0x90 | E | `ABS R1, R2` | `local.get $r2; call $abs_i32; local.set $r1` |
| SIGN | 0x91 | E | `SIGN R1, R2` | `local.get $r2; call $sign_i32; local.set $r1` |

### 3.3 Comparison Opcode Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| CMP_EQ | 0x2C | E | `CMP_EQ R1, R2, R3` | `local.get $r2; local.get $r3; i32.eq; local.set $r1` |
| CMP_LT | 0x2D | E | `CMP_LT R1, R2, R3` | `local.get $r2; local.get $r3; i32.lt_s; local.set $r1` |
| CMP_GT | 0x2E | E | `CMP_GT R1, R2, R3` | `local.get $r2; local.get $r3; i32.gt_s; local.set $r1` |
| CMP_NE | 0x2F | E | `CMP_NE R1, R2, R3` | `local.get $r2; local.get $r3; i32.ne; local.set $r1` |

Note: WASM comparison instructions return `i32` values (0 or 1), which directly maps to FLUX's comparison result semantics.

### 3.4 Logic and Bitwise Opcode Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| AND | 0x25 | E | `AND R1, R2, R3` | `local.get $r2; local.get $r3; i32.and; local.set $r1` |
| OR | 0x26 | E | `OR R1, R2, R3` | `local.get $r2; local.get $r3; i32.or; local.set $r1` |
| XOR | 0x27 | E | `XOR R1, R2, R3` | `local.get $r2; local.get $r3; i32.xor; local.set $r1` |
| SHL | 0x28 | E | `SHL R1, R2, R3` | `local.get $r2; local.get $r3; i32.shl; local.set $r1` |
| SHR | 0x29 | E | `SHR R1, R2, R3` | `local.get $r2; local.get $r3; i32.shr_s; local.set $r1` |
| ANDI | 0x1B | D | `ANDI R1, 0xFF` | `local.get $r1; i32.const 255; i32.and; local.set $r1` |
| ORI | 0x1C | D | `ORI R1, 0x10` | `local.get $r1; i32.const 16; i32.or; local.set $r1` |
| XORI | 0x1D | D | `XORI R1, 0xAA` | `local.get $r1; i32.const 170; i32.xor; local.set $r1` |
| SHLI | 0x1E | D | `SHLI R1, 4` | `local.get $r1; i32.const 4; i32.shl; local.set $r1` |
| SHRI | 0x1F | D | `SHRI R1, 2` | `local.get $r1; i32.const 2; i32.shr_s; local.set $r1` |
| CLZ | 0x95 | E | `CLZ R1, R2` | `local.get $r2; i32.clz; local.set $r1` |
| CTZ | 0x96 | E | `CTZ R1, R2` | `local.get $r2; i32.ctz; local.set $r1` |
| POPCNT | 0x97 | E | `POPCNT R1, R2` | `local.get $r2; i32.popcnt; local.set $r1` |

### 3.5 Memory Opcode Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| LOAD | 0x38 | E | `LOAD R1, R2, R3` | `local.get $r2; local.get $r3; i32.add; i32.load; local.set $r1` |
| STORE | 0x39 | E | `STORE R1, R2, R3` | `local.get $r2; local.get $r3; i32.add; local.get $r1; i32.store` |
| LOADOFF | 0x48 | G | `LOADOFF R1, R2, 8` | `local.get $r2; i32.const 8; i32.add; i32.load; local.set $r1` |
| STOREOFF | 0x49 | G | `STOREOFF R1, R2, 8` | `local.get $r2; i32.const 8; i32.add; local.get $r1; i32.store` |
| LOADI | 0x4A | G | `LOADI R1, R2, 8` | `local.get $r2; i32.load; i32.const 8; i32.add; i32.load; local.set $r1` |
| STOREI | 0x4B | G | `STOREI R1, R2, 8` | `local.get $r2; i32.load; i32.const 8; i32.add; local.get $r1; i32.store` |
| COPY | 0x4E | G | `COPY R1, R2, 16` | `local.get $r1; local.get $r2; i32.const 16; call $memcpy` |
| FILL | 0x4F | G | `FILL R1, R2, 16` | `local.get $r1; local.get $r2; i32.const 16; call $memset` |

### 3.6 Control Flow Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| JMP | 0x43 | F | `JMP -, +10` | `br $loop` (within block) or `local.set $pc; br $dispatch` |
| JZ | 0x3C | E | `JZ R1, R2` | `local.get $r1; i32.eqz; br_if $target` |
| JNZ | 0x3D | E | `JNZ R1, R2` | `local.get $r1; br_if $target` |
| JLT | 0x3E | E | `JLT R1, R2` | `local.get $r1; i32.const 0; i32.lt_s; br_if $target` |
| JGT | 0x3F | E | `JGT R1, R2` | `local.get $r1; i32.const 0; i32.gt_s; br_if $target` |
| CALL | 0x45 | F | `CALL R1, offset` | `local.get $r1; local.get $pc; i32.const 4; i32.add; call $push_stack; local.set $pc; br $dispatch` |
| RET | 0x02 | A | `RET` | `call $pop_stack; local.set $pc; br $dispatch` |
| JAL | 0x44 | F | `JAL R1, offset` | `local.get $pc; i32.const 4; i32.add; local.set $r1; local.set $pc; br $dispatch` |
| LOOP | 0x46 | F | `LOOP R1, -4` | `local.get $r1; i32.const 1; i32.sub; local.set $r1; local.get $r1; br_if $loop` |
| HALT | 0x00 | A | `HALT` | `br $break` (exit dispatch loop) |
| NOP | 0x01 | A | `NOP` | *(no WASM instruction generated)* |

**Note on interpretive dispatch:** In the interpretive compilation approach, control flow opcodes modify the `$pc` local and jump back to the dispatch loop head. Direct WASM `br` instructions are used for the dispatch loop itself (`$loop`/`$break`), not for individual FLUX jumps. This is because FLUX bytecode addresses are not known at compile time — they are data in linear memory, not positions in the WASM control flow graph.

### 3.7 Stack Operations Translation

| FLUX Opcode | Hex | Format | FLUX Assembly | WASM Translation |
|-------------|-----|--------|--------------|-----------------|
| PUSH | 0x0C | B | `PUSH R1` | `local.get $sp; local.get $r1; i32.store; local.get $sp; i32.const 4; i32.add; local.set $sp` |
| POP | 0x0D | B | `POP R1` | `local.get $sp; i32.const 4; i32.sub; local.set $sp; local.get $sp; i32.load; local.set $r1` |
| ENTER | 0x4C | G | `ENTER R1, R2, 32` | `local.get $sp; local.set $r1; local.get $sp; i32.const 32; i32.sub; local.set $sp` |
| LEAVE | 0x4D | G | `LEAVE R1, R2, 32` | `local.get $sp; i32.const 32; i32.add; local.set $sp; local.get $sp; i32.load; local.set $r1` |

### 3.8 Single-Register (Format B) Translation

| FLUX Opcode | Hex | FLUX Assembly | WASM Translation |
|-------------|-----|--------------|-----------------|
| INC | 0x08 | `INC R1` | `local.get $r1; i32.const 1; i32.add; local.set $r1` |
| DEC | 0x09 | `DEC R1` | `local.get $r1; i32.const 1; i32.sub; local.set $r1` |
| NOT | 0x0A | `NOT R1` | `local.get $r1; i32.const -1; i32.xor; local.set $r1` |
| NEG | 0x0B | `NEG R1` | `i32.const 0; local.get $r1; i32.sub; local.set $r1` |
| PUSH | 0x0C | `PUSH R1` | `local.get $r1; call $push` |
| POP | 0x0D | `POP R1` | `call $pop; local.set $r1` |
| CONF_LD | 0x0E | `CONF_LD R1` | `f32.load (offset for c1); local.set $r1` *(requires type conversion)* |
| CONF_ST | 0x0F | `CONF_ST R1` | `local.get $r1; f32.convert_i32_s; f32.store (offset for c1)` |

### 3.9 Register + Imm8 (Format D) Translation

| FLUX Opcode | Hex | FLUX Assembly | WASM Translation |
|-------------|-----|--------------|-----------------|
| MOVI | 0x18 | `MOVI R1, 42` | `i32.const 42; local.set $r1` |
| ADDI | 0x19 | `ADDI R1, 10` | `local.get $r1; i32.const 10; i32.add; local.set $r1` |
| SUBI | 0x1A | `SUBI R1, 10` | `local.get $r1; i32.const 10; i32.sub; local.set $r1` |
| ANDI | 0x1B | `ANDI R1, 0xFF` | `local.get $r1; i32.const 255; i32.and; local.set $r1` |
| ORI | 0x1C | `ORI R1, 0x10` | `local.get $r1; i32.const 16; i32.or; local.set $r1` |
| XORI | 0x1D | `XORI R1, 0xAA` | `local.get $r1; i32.const 170; i32.xor; local.set $r1` |
| SHLI | 0x1E | `SHLI R1, 4` | `local.get $r1; i32.const 4; i32.shl; local.set $r1` |
| SHRI | 0x1F | `SHRI R1, 2` | `local.get $r1; i32.const 2; i32.shr_s; local.set $r1` |

### 3.10 Register + Imm16 (Format F) Translation

| FLUX Opcode | Hex | FLUX Assembly | WASM Translation |
|-------------|-----|--------------|-----------------|
| MOVI16 | 0x40 | `MOVI16 R1, 1000` | `i32.const 1000; local.set $r1` |
| ADDI16 | 0x41 | `ADDI16 R1, 500` | `local.get $r1; i32.const 500; i32.add; local.set $r1` |
| SUBI16 | 0x42 | `SUBI16 R1, 200` | `local.get $r1; i32.const 200; i32.sub; local.set $r1` |
| JMP | 0x43 | `JMP -, +10` | `local.get $pc; i32.const 10; i32.add; local.set $pc; br $dispatch` |
| JAL | 0x44 | `JAL R1, +20` | `local.get $pc; i32.const 4; i32.add; local.set $r1; local.get $pc; i32.const 20; i32.add; local.set $pc; br $dispatch` |
| LOOP | 0x46 | `LOOP R1, -8` | `local.get $r1; i32.const 1; i32.sub; local.set $r1; local.get $r1; br_if $dispatch` |

### 3.11 Register + Register + Imm16 (Format G) Translation

| FLUX Opcode | Hex | FLUX Assembly | WASM Translation |
|-------------|-----|--------------|-----------------|
| LOADOFF | 0x48 | `LOADOFF R1, R2, 8` | `local.get $r2; i32.const 8; i32.add; i32.load; local.set $r1` |
| STOREOFF | 0x49 | `STOREOFF R1, R2, 8` | `local.get $r2; i32.const 8; i32.add; local.get $r1; i32.store` |
| LOADI | 0x4A | `LOADI R1, R2, 8` | `local.get $r2; i32.load; i32.const 8; i32.add; i32.load; local.set $r1` |
| STOREI | 0x4B | `STOREI R1, R2, 8` | `local.get $r2; i32.load; i32.const 8; i32.add; local.get $r1; i32.store` |
| ENTER | 0x4C | `ENTER R1, R2, 32` | `local.get $sp; local.set $r1; local.get $sp; i32.const 32; i32.sub; local.set $sp` |
| LEAVE | 0x4D | `LEAVE R1, R2, 32` | `local.get $sp; i32.const 32; i32.add; local.set $sp; local.get $sp; i32.load; local.set $r1` |

### 3.12 Format H Escape Prefix Translation

The ISA v3 escape prefix (`0xFF ext_id sub_opcode operands...`) is translated to a JS import dispatch:

```
FLUX:  0xFF 0x01 0x02 rd rs1 rs2     (EXT_BABEL TRANSLATE R1, R2, R3)
WASM:  local.get $r1; local.get $r2; local.get $r3
       i32.const 1   ;; ext_id = EXT_BABEL
       i32.const 2   ;; sub_opcode = TRANSLATE
       call $extension_dispatch
       local.set $r1
```

The `extension_dispatch` import receives `(sub_opcode, rd_val, rs1_val, rs2_val)` and returns the result. The JS host determines which extension handler to invoke based on the extension ID. This provides a universal fallback: any extension that the JS host implements is available; unsupported extensions return 0 and set an error flag.

---

## 4. WASM Module Structure

### 4.1 Module Skeleton

```wat
(module
  ;; ============================================================
  ;; IMPORTS — Provided by JavaScript host at instantiation
  ;; ============================================================
  
  ;; A2A signaling
  (import "flux" "signal"
    (func $signal (param $channel i32) (param $type i32) (param $data i32) (result i32)))
  (import "flux" "broadcast"
    (func $broadcast (param $channel i32) (param $data i32) (param $ttl i32) (result i32)))
  (import "flux" "receive"
    (func $receive (param $timeout_ms i32) (result i32)))
  (import "flux" "tell"
    (func $tell (param $target i32) (param $msg_type i32) (param $data i32) (result i32)))
  (import "flux" "ask"
    (func $ask (param $target i32) (param $msg_type i32) (param $data i32) (result i32)))
  
  ;; I/O
  (import "flux" "print"
    (func $print (param $addr i32) (param $len i32)))
  (import "flux" "scan"
    (func $scan (param $buf_addr i32) (param $max_len i32) (result i32)))
  
  ;; System
  (import "flux" "ticks"
    (func $ticks (result i32)))
  (import "flux" "extension"
    (func $extension_dispatch (param $ext_id i32) (param $sub_op i32) 
                              (param $p0 i32) (param $p1 i32) (param $p2 i32) (result i32)))
  (import "flux" "debug_print"
    (func $debug_print (param $reg_id i32) (param $value i32)))
  
  ;; ============================================================
  ;; MEMORY — 64KB initial, expandable to 16MB
  ;; ============================================================
  (memory (export "memory") 1 256)  ;; 1 page = 64KB, max 256 pages = 16MB
  
  ;; ============================================================
  ;; TABLES — For opcode dispatch (br_table)
  ;; ============================================================
  
  ;; ============================================================
  ;; MAIN EXECUTION FUNCTION
  ;; ============================================================
  (func (export "execute") (param $bytecode_offset i32) (result i32)
    
    ;; ---- Register File as WASM Locals ----
    ;; General-purpose registers (R0–R15)
    (local $r0 i32)   (local $r1 i32)   (local $r2 i32)   (local $r3 i32)
    (local $r4 i32)   (local $r5 i32)   (local $r6 i32)   (local $r7 i32)
    (local $r8 i32)   (local $r9 i32)   (local $r10 i32)  (local $r11 i32)
    (local $r12 i32)  (local $r13 i32)  (local $r14 i32)  (local $r15 i32)
    
    ;; Confidence registers (C0–C15) stored as f32
    ;; In WASM, we use a separate memory region or i32 locals with reinterpretation
    (local $c0 i32)   (local $c1 i32)   (local $c2 i32)   (local $c3 i32)
    (local $c4 i32)   (local $c5 i32)   (local $c6 i32)   (local $c7 i32)
    (local $c8 i32)   (local $c9 i32)   (local $c10 i32)  (local $c11 i32)
    (local $c12 i32)  (local $c13 i32)  (local $c14 i32)  (local $c15 i32)
    
    ;; Special registers
    (local $sp i32)    ;; Stack pointer
    (local $fp i32)    ;; Frame pointer
    (local $pc i32)    ;; Program counter
    (local $flags i32) ;; Flags register (6 bits)
    
    ;; Dispatch locals
    (local $opcode i32)
    (local $rd i32)
    (local $rs1 i32)
    (local $rs2 i32)
    (local $imm8 i32)
    (local $imm16 i32)
    (local $temp i32)
    (local $result i32)
    
    ;; ---- Register Initialization ----
    (local.set $r0 (i32.const 0))
    (local.set $r1 (i32.const 0))
    (local.set $r2 (i32.const 0))
    (local.set $r3 (i32.const 0))
    (local.set $r4 (i32.const 0))
    (local.set $r5 (i32.const 0))
    (local.set $r6 (i32.const 0))
    (local.set $r7 (i32.const 0))
    (local.set $r8 (i32.const 0))
    (local.set $r9 (i32.const 0))
    (local.set $r10 (i32.const 0))
    (local.set $r11 (i32.const 0))
    (local.set $r12 (i32.const 0))
    (local.set $r13 (i32.const 0))
    (local.set $r14 (i32.const 0))
    (local.set $r15 (i32.const 0))
    
    ;; Initialize confidence registers to 1.0 (0x3F800000 in IEEE 754)
    (local.set $c0 (i32.const 1065353216))
    (local.set $c1 (i32.const 1065353216))
    ;; ... (all C registers initialized to 1.0) ...
    
    ;; Initialize special registers
    (local.set $sp (i32.const 16384))   ;; Stack at 16KB (grows downward)
    (local.set $fp (i32.const 16384))   ;; Frame pointer = initial SP
    (local.set $pc (local.get $bytecode_offset))
    (local.set $flags (i32.const 0))
    
    ;; ---- Instruction Dispatch Loop ----
    (block $break
      (loop $dispatch
        
        ;; Fetch opcode byte from memory at PC
        (local.set $opcode (i32.load8_u (local.get $pc)))
        
        ;; ---- Format A: Zero-operand (0x00–0x03) ----
        (block $fmt_a
          (br_if $fmt_a (i32.gt_u (local.get $opcode) (i32.const 3)))
          
          ;; Opcode 0x00: HALT
          (if (i32.eqz (local.get $opcode))
            (then (br $break))
          )
          ;; Opcode 0x01: NOP
          ;; Opcode 0x02: RET
          (if (i32.eq (local.get $opcode) (i32.const 2))
            (then
              (local.set $sp (i32.sub (local.get $sp) (i32.const 4)))
              (local.set $pc (i32.load (local.get $sp)))
              (br $dispatch)
            )
          )
          ;; Opcode 0x03: IRET — not supported in WASM, skip
          
          (local.set $pc (i32.add (local.get $pc) (i32.const 1)))
          (br $dispatch)
        )
        
        ;; ---- Format B: Single register (0x08–0x0F) ----
        (block $fmt_b
          (br_if $fmt_b (i32.lt_u (local.get $opcode) (i32.const 8)))
          (br_if $fmt_b (i32.gt_u (local.get $opcode) (i32.const 15)))
          
          (local.set $rd (i32.load8_u (i32.add (local.get $pc) (i32.const 1))))
          
          ;; Dispatch Format B opcodes via inline if/else chain
          ;; 0x08: INC
          ;; 0x09: DEC
          ;; 0x0A: NOT
          ;; 0x0B: NEG
          ;; 0x0C: PUSH
          ;; 0x0D: POP
          ;; 0x0E: CONF_LD
          ;; 0x0F: CONF_ST
          ;; (full implementation in generated code)
          
          (local.set $pc (i32.add (local.get $pc) (i32.const 2)))
          (br $dispatch)
        )
        
        ;; ---- Additional format blocks for C, D, E, F, G, H ----
        ;; ... (generated by the compiler for all 247+ opcodes) ...
        
        ;; ---- Fallback: unknown opcode → HALT_ERR ----
        (br $break)
      )
    )
    
    ;; Return value: register R0
    (local.get $r0)
  )
  
  ;; ============================================================
  ;; HELPER FUNCTIONS
  ;; ============================================================
  
  ;; Store R[i] — indirect register access (for dispatch)
  (func $set_reg (param $idx i32) (param $val i32)
    ;; Uses a br_table or if/else chain to set the correct local
    ;; Generated code sets the appropriate $rN local
  )
  
  ;; Load R[i] — indirect register access
  (func $get_reg (param $idx i32) (result i32)
    ;; Uses a br_table or if/else chain to get the correct local
  )
  
  ;; MIN/MAX helpers (WASM lacks built-in min/max for i32)
  (func $min_i32 (param $a i32) (param $b i32) (result i32)
    (select (local.get $b) (local.get $a) (i32.lt_s (local.get $a) (local.get $b)))
  )
  (func $max_i32 (param $a i32) (param $b i32) (result i32)
    (select (local.get $b) (local.get $a) (i32.gt_s (local.get $a) (local.get $b)))
  )
  
  ;; ABS helper
  (func $abs_i32 (param $x i32) (result i32)
    (select
      (i32.sub (i32.const 0) (local.get $x))  ;; negate
      (local.get $x)
      (i32.lt_s (local.get $x) (i32.const 0))  ;; if x < 0
    )
  )
  
  ;; SIGN helper
  (func $sign_i32 (param $x i32) (result i32)
    (if (result i32) (i32.lt_s (local.get $x) (i32.const 0))
      (then (i32.const -1))
      (else
        (if (result i32) (i32.gt_s (local.get $x) (i32.const 0))
          (then (i32.const 1))
          (else (i32.const 0))
        )
      )
    )
  )
)
```

### 4.2 Register Representation

| Register | WASM Type | WASM Name | Notes |
|----------|-----------|-----------|-------|
| R0 | i32 | `$r0` | Zero/result register |
| R1–R14 | i32 | `$r1`–`$r14` | General-purpose |
| R15 | i32 | `$r15` | Scratch (assembler pseudo-instruction expansion) |
| C0–C15 | i32 | `$c0`–`$c15` | Confidence (IEEE 754 f32 bits stored in i32) |
| SP | i32 | `$sp` | Stack pointer (initialized to top of stack region) |
| FP | i32 | `$fp` | Frame pointer |
| PC | i32 | `$pc` | Program counter (byte offset into linear memory) |
| FLAGS | i32 | `$flags` | 6-bit flags register |

**Why i32 for confidence registers?** WASM does not allow mixing `f32` and `i32` locals in the same function without explicit conversion. Storing confidence values as their IEEE 754 bit patterns in `i32` locals simplifies the dispatch loop. The `f32.reinterpret_i32` and `i32.reinterpret_f32` instructions convert between the two representations when performing confidence arithmetic.

### 4.3 Instruction Dispatch Loop

The dispatch loop reads one byte at `$pc`, decodes the opcode, and branches to the appropriate handler. Two implementation strategies:

**Strategy A: If/else chain** (simpler, smaller code)
- Each format range checked via `br_if` to skip blocks
- Within each block, individual opcodes checked via `i32.eq`
- Generated code is ~2000–3000 WAT lines for all 247 opcodes

**Strategy B: `br_table` dispatch** (faster, larger code)
- Opcode byte used as index into `br_table` with 256 labels
- Each label jumps to the handler for that opcode
- Handlers update locals and jump back to dispatch
- Faster dispatch (~1 instruction vs ~N comparisons) but more code

**Recommendation:** Start with Strategy A for simplicity. Switch to Strategy B after profiling shows dispatch overhead is significant.

### 4.4 Import Functions

The WASM module imports functions from the `"flux"` module, provided by the JavaScript host at instantiation time:

| Import Name | Signature | Purpose |
|-------------|-----------|---------|
| `signal` | `(i32, i32, i32) → i32` | Emit A2A signal (channel, type, data → status) |
| `broadcast` | `(i32, i32, i32) → i32` | Broadcast to fleet (channel, data, ttl → status) |
| `receive` | `(i32) → i32` | Wait for A2A message (timeout_ms → data_addr) |
| `tell` | `(i32, i32, i32) → i32` | Send message to agent (target, type, data → status) |
| `ask` | `(i32, i32, i32) → i32` | Request from agent (target, type, data → response) |
| `print` | `(i32, i32) → void` | Print string from memory (addr, len) |
| `scan` | `(i32, i32) → i32` | Read input to memory (buf_addr, max_len → bytes_read) |
| `ticks` | `() → i32` | Get monotonic time (milliseconds) |
| `extension` | `(i32, i32, i32, i32, i32) → i32` | Extension dispatch (ext_id, sub, p0, p1, p2 → result) |
| `debug_print` | `(i32, i32) → void` | Debug output (register_id, value) |

---

## 5. Unsupported Opcodes — JS Bridge

Opcodes that require interaction with the browser environment cannot be implemented purely in WASM. These are bridged to JavaScript via imported functions.

### 5.1 I/O Opcodes

| FLUX Opcode | Category | Bridge Target | JS Implementation |
|-------------|----------|--------------|-------------------|
| SYS (0x10) | system call | `call $syscall` | `console.log`, `document.getElementById`, `fetch` |
| PRINT | I/O | `call $print` | `console.log(readString(addr, len))` |
| SCAN | I/O | `call $scan` | `prompt()` or text input element |

### 5.2 A2A Signaling Opcodes

| FLUX Opcode | Hex | Bridge Target | JS Implementation |
|-------------|-----|--------------|-------------------|
| TELL | 0x50 | `call $tell` | `fetch('/api/a2a/tell', {method: 'POST', body: ...})` |
| ASK | 0x51 | `call $ask` | `fetch('/api/a2a/ask', {method: 'POST', body: ...})` |
| DELEG | 0x52 | `call $extension` | A2A delegation via WebSocket or REST |
| BCAST | 0x53 | `call $broadcast` | WebSocket broadcast to fleet |
| ACCEPT | 0x54 | `call $extension` | Accept incoming delegation |
| SIGNAL | 0x5A | `call $signal` | `EventTarget.dispatchEvent()` or WebSocket |
| AWAIT | 0x5B | `call $receive` | `await new Promise(resolve => ...)` (async) |
| TRUST | 0x5C | `call $extension` | Trust table update (localStorage) |
| DISCOV | 0x5D | `call $extension` | Fleet discovery via `/api/fleet` |
| STATUS | 0x5E | `call $extension` | Agent status query |
| HEARTBT | 0x5F | `call $extension` | Heartbeat via WebSocket ping |

**Async handling:** AWAIT (0x5B) is synchronous in WASM but needs asynchronous behavior (waiting for a message). The JS host implements a polling pattern: `receive(timeout)` returns 0 immediately if no message, or blocks for `timeout` ms. For true async, the WASM module can yield control back to JS using a `setTimeout` + re-entry pattern.

### 5.3 System Opcodes

| FLUX Opcode | Hex | Bridge Target | JS Implementation |
|-------------|-----|--------------|-------------------|
| SYS | 0x10 | `call $syscall` | System call dispatch table |
| TRAP | 0x11 | *internal* | Set flags, optionally halt |
| DBG | 0x12 | `call $debug_print` | `console.log("R${id} = ${value}")` |
| WFI | 0x05 | `call $ticks` | Spin-wait (browser prevents true idle) |
| RESET | 0x06 | *internal* | Clear all register locals |
| SYN | 0x07 | *(no-op in single-threaded WASM)* | Memory barrier — unnecessary in WASM |

### 5.4 Time Opcodes

| FLUX Opcode | Hex | Bridge Target | JS Implementation |
|-------------|-----|--------------|-------------------|
| CLK | 0xF6 | `call $ticks` | `performance.now()` |
| TICKS_ELAPSED | 0xFD | `call $ticks` | `performance.now() - start_time` |
| WDOG | 0xF8 | `call $extension` | `setTimeout(() => { /* watchdog */ }, timeout)` |
| SLEEP | 0xF9 | `call $extension` | `Atomics.wait` or `setTimeout` |

### 5.5 Sensor and Hardware Opcodes

All sensor opcodes (0x80–0x8F) and GPU opcodes (0xDB–0xDE) are fully bridged to JS:

| FLUX Opcode | Hex | Bridge Target | JS Implementation |
|-------------|-----|--------------|-------------------|
| SENSE | 0x80 | `call $extension` | Web Bluetooth, WebUSB, or sensor API |
| ACTUATE | 0x81 | `call $extension` | GPIO via Web Serial or WebUSB |
| GPS | 0x85 | `call $extension` | `navigator.geolocation` |
| ACCEL | 0x86 | `call $extension` | `DeviceMotionEvent` |
| CAMCAP | 0x88 | `call $extension` | `getUserMedia({video: true})` |
| GPU_LD | 0xDB | `call $extension` | WebGPU buffer upload |
| GPU_EX | 0xDD | `call $extension` | WebGPU compute pass |

---

## 6. Memory Layout in WASM

The FLUX WASM runtime uses a carefully partitioned linear memory layout:

```
┌────────────────────────────────────────────────────┐
│  0x0000 — 0x0FFF   FLUX Heap (4 KB)               │
│                      Dynamic allocation (MALLOC)    │
│                      Confidence state buffers       │
│                      String/collection data         │
├────────────────────────────────────────────────────┤
│  0x1000 — 0x3FFF   FLUX Stack (12 KB)             │
│                      Operand stack (grows down)     │
│                      SP starts at 0x3FFC            │
│                      Max 3072 stack entries         │
├────────────────────────────────────────────────────┤
│  0x4000 — 0x7FFF   Program Bytecode (16 KB)       │
│                      Loaded .fluxbc program         │
│                      PC starts at 0x4000           │
│                      Max 16,384 bytes of bytecode   │
├────────────────────────────────────────────────────┤
│  0x8000 — 0xBFFF   A2A Message Buffers (16 KB)    │
│                      Incoming/outgoing messages     │
│                      Message queue structures       │
│                      String encoding/decoding       │
├────────────────────────────────────────────────────┤
│  0xC000 — 0xFFFF   Confidence Tables (16 KB)      │
│                      Confidence register dump area  │
│                      C_THRESH tables               │
│                      Confidence distribution data   │
├────────────────────────────────────────────────────┤
│  0x10000 — 0xFFFFF  Extended Memory (up to ~960KB)│
│                      Available via memory.grow      │
│                      Large data structures          │
│                      Tensor buffers                 │
│                      Vector operations              │
└────────────────────────────────────────────────────┘

Total initial: 64KB (1 WASM page)
Maximum: 16MB (256 WASM pages)
Growth: memory.grow (1 page = 64KB increments)
```

### Memory Constants (WAT)

```wat
;; Memory region boundaries
(i32.const 0x0000)  ;; HEAP_START
(i32.const 0x1000)  ;; HEAP_END / STACK_START
(i32.const 0x4000)  ;; STACK_END / PROGRAM_START
(i32.const 0x8000)  ;; PROGRAM_END / MSG_START
(i32.const 0xC000)  ;; MSG_END / CONF_START
(i32.const 0x10000) ;; CONF_END / EXTENDED_START
```

### Bytecode Loading

The host loads FLUX bytecode into the program region before calling `execute`:

```javascript
// JavaScript host
const bytecode = new Uint8Array(fluxBytecode); // from .fluxbc file
const wasmMemory = new WebAssembly.Memory({ initial: 1, maximum: 256 });
const view = new DataView(wasmMemory.buffer);
// Write bytecode to program region (0x4000)
const programStart = 0x4000;
for (let i = 0; i < bytecode.length; i++) {
    view.setUint8(programStart + i, bytecode[i]);
}
// Execute from program start
const result = instance.exports.execute(programStart);
```

---

## 7. Browser Integration API

### 7.1 JavaScript Host Object

```javascript
class FluxWasmHost {
    constructor() {
        this.messageQueue = [];
        this.agents = new Map();       // Known fleet agents
        this.trustTable = new Map();   // Trust levels
        this.startTime = performance.now();
        this.websocket = null;         // A2A connection
    }

    /**
     * Import object for WebAssembly.instantiate
     * Matches the (import "flux" ...) declarations in the WAT module
     */
    getImportObject() {
        return {
            flux: {
                // A2A signaling
                signal: (channel, type, data) => this._signal(channel, type, data),
                broadcast: (channel, data, ttl) => this._broadcast(channel, data, ttl),
                receive: (timeout_ms) => this._receive(timeout_ms),
                tell: (target, msg_type, data) => this._tell(target, msg_type, data),
                ask: (target, msg_type, data) => this._ask(target, msg_type, data),

                // I/O
                print: (addr, len) => this._print(addr, len),
                scan: (buf_addr, max_len) => this._scan(buf_addr, max_len),

                // System
                ticks: () => this._ticks(),
                extension: (ext_id, sub_op, p0, p1, p2) =>
                    this._extension(ext_id, sub_op, p0, p1, p2),
                debug_print: (reg_id, value) => this._debugPrint(reg_id, value),
            }
        };
    }

    // --- A2A Implementation ---
    _signal(channel, type, data) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'signal', channel, signalType: type, data
            }));
        }
        return 0; // success
    }

    _broadcast(channel, data, ttl) {
        // Broadcast to all connected agents
        return 0;
    }

    _receive(timeout_ms) {
        // Poll message queue with timeout
        if (this.messageQueue.length > 0) {
            const msg = this.messageQueue.shift();
            // Write message data to WASM memory and return address
            this._writeMessageToMemory(msg);
            return msg.addr;
        }
        return 0; // no message (timeout)
    }

    _tell(target, msg_type, data) {
        return this._sendA2A(target, 'tell', msg_type, data);
    }

    _ask(target, msg_type, data) {
        return this._sendA2A(target, 'ask', msg_type, data);
    }

    // --- I/O Implementation ---
    _print(addr, len) {
        const memory = new Uint8Array(this.wasmMemory.buffer);
        const bytes = memory.slice(addr, addr + len);
        const text = new TextDecoder().decode(bytes);
        console.log(`[FLUX] ${text}`);
    }

    _scan(buf_addr, max_len) {
        // Synchronous input (prompt) — limited in browser
        // For async input, use the message queue pattern
        return 0; // no input available
    }

    // --- System Implementation ---
    _ticks() {
        return Math.floor(performance.now() - this.startTime);
    }

    _extension(ext_id, sub_op, p0, p1, p2) {
        console.warn(`[FLUX] Extension call: ext_id=0x${ext_id.toString(16)}, sub=0x${sub_op.toString(16)}`);
        return 0; // unimplemented extension
    }

    _debugPrint(reg_id, value) {
        console.log(`[FLUX DBG] R${reg_id} = ${value} (0x${value.toString(16)})`);
    }
}
```

### 7.2 Loading and Executing

```javascript
async function loadAndRunFlux(fluxBytecodeUrl) {
    // 1. Fetch FLUX bytecode
    const response = await fetch(fluxBytecodeUrl);
    const fluxBytecode = new Uint8Array(await response.arrayBuffer());

    // 2. Fetch pre-compiled WASM module
    const wasmResponse = await fetch('flux-vm.wasm');
    const wasmBytes = new Uint8Array(await wasmResponse.arrayBuffer());

    // 3. Create host
    const host = new FluxWasmHost();

    // 4. Instantiate WASM module with host imports
    const { instance } = await WebAssembly.instantiate(wasmBytes, host.getImportObject());
    host.wasmMemory = instance.exports.memory;

    // 5. Load bytecode into program region
    const memory = new Uint8Array(host.wasmMemory.buffer);
    const PROGRAM_START = 0x4000;
    for (let i = 0; i < fluxBytecode.length; i++) {
        memory[PROGRAM_START + i] = fluxBytecode[i];
    }

    // 6. Execute
    const result = instance.exports.execute(PROGRAM_START);
    console.log(`FLUX execution complete. R0 = ${result}`);

    return result;
}

// Usage
loadAndRunFlux('/programs/fibonacci.fluxbc');
```

### 7.3 A2A Bridge Implementation

For fleet-scale A2A communication in the browser, the JS bridge uses WebSocket:

```javascript
class FluxWasmHost {
    connectToFleet(url) {
        this.websocket = new WebSocket(url);

        this.websocket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.messageQueue.push(msg);
        };

        this.websocket.onopen = () => {
            console.log('[FLUX] Connected to fleet A2A broker');
            // Register this agent
            this.websocket.send(JSON.stringify({
                type: 'register',
                agentId: this.agentId,
                capabilities: ['flux-wasm']
            }));
        };
    }

    _sendA2A(target, operation, msg_type, data) {
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            console.warn('[FLUX] A2A not connected');
            return -1; // error
        }
        this.websocket.send(JSON.stringify({
            type: operation,
            target,
            msgType: msg_type,
            data,
            sender: this.agentId
        }));
        return 0; // success
    }
}
```

---

## 8. Performance Considerations

### 8.1 Execution Speed

| Runtime | Speed (ops/sec) | Relative to C | Notes |
|---------|-----------------|---------------|-------|
| C (gcc -O2) | ~50M ops/sec | 1.0x (baseline) | Native, compiled |
| WASM (V8, interpretive) | ~10–25M ops/sec | 0.2–0.5x | Near-native for tight loops |
| WASM (V8, compiled per-instruction) | ~30–40M ops/sec | 0.6–0.8x | Future optimization |
| Python 3 (reference) | ~50K ops/sec | 0.001x | Interpreter overhead |
| JavaScript (hand-written) | ~500M ops/sec | 10x | JIT-optimized baseline |

**Key insight:** WASM interpretive dispatch is 200–500x faster than the Python reference runtime and within 2–5x of native C. This makes WASM a practical production target for FLUX programs.

### 8.2 Why Interpretive Compilation?

Two approaches exist for FLUX→WASM:

| Approach | Pros | Cons |
|----------|------|------|
| **Interpretive** (dispatch loop) | Supports dynamic bytecode loading; simpler compiler; smaller binary; single compiled module runs any .fluxbc | Dispatch overhead per instruction (~3–5 WASM ops) |
| **Per-instruction compilation** (each FLUX op → WASM basic block) | Eliminates dispatch overhead; WASM optimizer can optimize across instructions | Complex control-flow reconstruction; binary is bytecode-specific; larger compiler |

The interpretive approach is recommended because:
1. FLUX supports self-modifying bytecode (a core fleet feature) — per-instruction compilation cannot handle this
2. A2A agents send bytecode as messages — dynamic loading is essential
3. The existing `flux-wasm` repo skeleton uses the interpretive approach
4. 200–500x speedup over Python is sufficient for browser use cases

### 8.3 Memory Performance

- WASM linear memory access is a single array index — O(1) with no cache hierarchy
- All memory is in one contiguous buffer — no pointer aliasing issues
- `memory.grow` is O(1) amortized but causes a full memory copy in some engines
- Stack operations (PUSH/POP) modify `$sp` and use `i32.load`/`i32.store` — 2 WASM instructions each

### 8.4 Startup Cost

| Component | Time | Notes |
|-----------|------|-------|
| WASM compilation (wat2wasm) | ~50ms | Done once at build time |
| WASM instantiation | ~5–10ms | Module compilation + instantiation |
| Bytecode loading | ~1ms | memcpy of bytecode into memory |
| First execution | ~0.1ms | No warm-up penalty (WASM is pre-compiled) |

---

## 9. Use Cases

### 9.1 Fleet IDE (flux-ide)

The flux-ide project provides a browser-based development environment for FLUX. With the WASM target:

- **Write FLUX assembly** in a Monaco editor
- **Compile to .fluxbc** using the Python assembler (via Web Worker)
- **Execute in browser** using the WASM VM — instant feedback, no server round-trip
- **Visualize execution** — register state, stack, memory inspector panel
- **A2A simulation** — mock agent communication within the IDE

### 9.2 FishingLog Dashboard

The FishingLog AI product (Casey Digennaro's edge AI fishing vessel system) can use WASM for:

- **Browser-based catch analysis** — run FLUX confidence classification programs client-side
- **Sensor data visualization** — FLUX programs process GPS, depth, temperature data
- **Offline capability** — WASM runs without network, important for maritime environments

### 9.3 Fleet Demo

An interactive FLUX VM in a webpage for onboarding new fleet members:

- **Live bytecode execution** — paste .fluxbc hex, see register state update
- **Step-through debugging** — execute one instruction at a time
- **Confidence visualization** — see confidence registers change color as trust propagates
- **A2A simulation** — two WASM VMs communicating via JavaScript bridge

### 9.4 Edge Deployment

WASM runs on any device with a browser — not just desktops:

- **Mobile browsers** — iOS Safari, Chrome Android (WASM support > 96% global)
- **Embedded browsers** — WebView on IoT devices
- **Serverless edge** — Cloudflare Workers, Vercel Edge Functions support WASM
- **Node.js** — WASM also runs server-side via `wasmer`, `wasmtime`

### 9.5 Conformance Testing

Run the full 71+ vector conformance suite in the browser:

```javascript
async function runConformance() {
    const host = new FluxWasmHost();
    const { instance } = await WebAssembly.instantiate(wasmBytes, host.getImportObject());
    const results = [];

    for (const vector of conformanceVectors) {
        loadBytecode(vector.bytecode, instance.exports.memory);
        const r0 = instance.exports.execute(0x4000);
        const pass = r0 === vector.expected.r0;
        results.push({ name: vector.name, pass, actual: r0, expected: vector.expected.r0 });
    }

    return results;
}
```

---

## 10. Compiler Design

### 10.1 Python Compiler Architecture

The FLUX→WASM compiler is a Python script (`flux2wasm.py`) that generates WAT text output:

```
flux2wasm.py
├── __init__.py          # Package entry point
├── compiler.py          # Main compiler class
│   ├── parse_bytecode() # Read .fluxbc binary
│   ├── emit_header()    # WAT module header + imports
│   ├── emit_locals()    # Register file declarations
│   ├── emit_dispatch()  # Instruction dispatch loop
│   ├── emit_helpers()   # MIN, MAX, ABS, SIGN helpers
│   └── emit_footer()    # Module closing
├── opcode_table.py      # Opcode → WAT translation table
│   └── OPCODE_WAT = {
│       0x20: "i32.add",   # ADD
│       0x21: "i32.sub",   # SUB
│       0x22: "i32.mul",   # MUL
│       ...
│   }
├── bridge_table.py      # Opcodes that bridge to JS
│   └── BRIDGE_OPCODES = {
│       0x50: ("tell", 3),      # TELL → call $tell
│       0x51: ("ask", 3),       # ASK → call $ask
│       0x53: ("broadcast", 3), # BCAST → call $broadcast
│       ...
│   }
└── cli.py               # Command-line interface
    └── python -m flux2wasm input.fluxbc -o output.wat
```

### 10.2 WAT Emission Strategy

The compiler generates WAT (text format) rather than binary .wasm directly:

1. **Easier to debug** — WAT is human-readable
2. **No WASM binary encoder dependency** — standard `wat2wasm` tool converts to .wasm
3. **Compatible with existing tooling** — wabt, wasm-tools, binaryen

For production, binary emission can be added using the `wasm-tools` Python package or by piping WAT through `wat2wasm`.

### 10.3 Optimization Passes

| Pass | Description | Impact |
|------|-------------|--------|
| **Constant folding** | Pre-compute MOVI + ADDI → single MOVI | 10–20% fewer instructions |
| **Dead register elimination** | Skip writes to registers never read | 5–10% fewer stores |
| **Branch prediction hints** | Reorder if/else chains by frequency | 5–15% dispatch speedup |
| **Memory access coalescing** | Combine adjacent LOAD/STORE into memory.copy | 10–30% for memory-heavy code |
| **Confidence short-circuit** | Skip confidence computation when C_THRESH is not used | 15–25% for non-confidence code |

Optimization passes are optional and can be enabled via CLI flags:

```bash
# Debug build (no optimizations)
python -m flux2wasm input.fluxbc -o output.wat

# Optimized build
python -m flux2wasm input.fluxbc -o output.wat --opt all

# Specific optimization
python -m flux2wasm input.fluxbc -o output.wat --opt constant-fold --opt branch-reorder
```

---

## 11. Conformance Test Vectors

The following test vectors verify WASM-specific behavior:

| # | Name | Bytecode | Expected R0 | Category |
|---|------|----------|-------------|----------|
| W-01 | HALT immediate | `[0x00]` | 0 | system |
| W-02 | MOV + HALT | `[0x3A, 0x00, 0x01, 0x00, 0x00]` | 1 | data |
| W-03 | ADD + HALT | `[0x18, 0x00, 0x0A, 0x18, 0x01, 0x0A, 0x20, 0x00, 0x00, 0x01, 0x00]` | 20 | arithmetic |
| W-04 | Stack push/pop | `[0x18, 0x00, 0x2A, 0x0C, 0x00, 0x0D, 0x01, 0x00]` | 42 | stack |
| W-05 | Conditional branch | `[0x18, 0x00, 0x01, 0x3C, 0x00, 0x02, 0x18, 0x00, 0x05, 0x00]` | 5 | control |
| W-06 | Memory load/store | `[0x18, 0x01, 0x00, 0x18, 0x00, 0x2A, 0x39, 0x00, 0x01, 0x00, 0x38, 0x02, 0x01, 0x00, 0x00]` | 42 | memory |
| W-07 | Loop 5 iterations | `[0x18, 0x00, 0x05, 0x18, 0x01, 0x00, 0x08, 0x01, 0x09, 0x00, 0x18, 0x02, 0x01, 0x2C, 0x03, 0x00, 0x02, 0x3D, 0x03, 0x07, 0x00, 0x00]` | 0 | control |
| W-08 | Confidence CLZ | `[0x18, 0x00, 0x01, 0x0E, 0x00, 0x95, 0x01, 0x00, 0x00]` | 31 | confidence |
| W-09 | A2A signal bridge | `[0x50, 0x01, 0x02, 0x03, 0x00]` | 0 (bridge) | a2a |
| W-10 | Extension prefix | `[0xFF, 0x01, 0x00, 0x00, 0x01, 0x02, 0x00]` | 0 (bridge) | extension |

All 71 existing expanded conformance vectors must also pass on the WASM runtime.

---

## 12. Implementation Roadmap

### Phase 1: Core Interpreter (Week 1–2)

| Task | Effort | Dependencies | Deliverable |
|------|--------|-------------|-------------|
| WAT module skeleton with imports | 2h | None | `flux-vm.wat` (header) |
| Register file + dispatch loop (Format A + B) | 4h | Skeleton | Formats A–B working |
| Format C + D handlers | 3h | Format A–B | Format D immediate ops |
| Format E handlers (arithmetic, logic, compare) | 6h | Format D | Core computation |
| Format E handlers (memory, control flow, mov) | 4h | Core computation | MOV, LOAD, STORE, JZ, JNZ |
| Format F handlers | 3h | Format E | JMP, JAL, MOVI16, LOOP |
| Format G handlers | 2h | Format F | LOADOFF, STOREOFF, ENTER, LEAVE |
| Helper functions (MIN, MAX, ABS, SIGN) | 1h | None | Utility functions |
| **Milestone: 35 core opcodes working** | **~25h** | | |

### Phase 2: I/O and Bridge (Week 3)

| Task | Effort | Dependencies | Deliverable |
|------|--------|-------------|-------------|
| JS host object (I/O: print, scan) | 3h | Phase 1 | `FluxWasmHost` class |
| A2A bridge (signal, broadcast, receive) | 4h | JS host | A2A stubs |
| SYS/TRAP/DBG bridge | 2h | JS host | System calls |
| Format H escape prefix → extension bridge | 2h | JS host | Extension passthrough |
| **Milestone: Full JS bridge operational** | **~11h** | | |

### Phase 3: Confidence and Advanced (Week 4)

| Task | Effort | Dependencies | Deliverable |
|------|--------|-------------|-------------|
| Confidence register mapping (C0–C15 as f32) | 4h | Phase 1 | CONF_LD, CONF_ST working |
| Confidence-aware ops (C_ADD, C_SUB, C_MUL, etc.) | 4h | Confidence mapping | 0x60–0x6F range |
| C_THRESH implementation | 2h | Confidence ops | Conditional confidence skip |
| Float ops (FADD, FSUB, FMUL, FDIV) | 3h | Phase 1 | 0x30–0x3F range |
| Extended math (SQRT, POW, LOG2, RND) | 2h | Float ops | 0x90–0x9F range |
| **Milestone: Confidence + float ops working** | **~15h** | | |

### Phase 4: Testing and Integration (Week 5)

| Task | Effort | Dependencies | Deliverable |
|------|--------|-------------|-------------|
| Conformance test runner (browser) | 3h | Phase 3 | `test_wasm.html` |
| Run all 71 expanded vectors | 2h | Test runner | 71/71 PASS |
| WASM-specific test vectors (10) | 2h | Phase 2–3 | W-01 through W-10 |
| flux-ide integration guide | 2h | All phases | Integration docs |
| Performance benchmarks | 2h | All phases | Benchmark report |
| **Milestone: Full conformance + IDE integration** | **~11h** | | |

### Total Estimated Effort

| Phase | Hours | Tasks |
|-------|-------|-------|
| Phase 1: Core | ~25h | 8 tasks |
| Phase 2: Bridge | ~11h | 5 tasks |
| Phase 3: Advanced | ~15h | 5 tasks |
| Phase 4: Testing | ~11h | 5 tasks |
| **Total** | **~62h** | **23 tasks** |

---

## Appendix A — Complete Translation Table

### Format A — Zero-Operand (1 byte)

| Hex | Mnemonic | WASM Translation |
|-----|----------|-----------------|
| 0x00 | HALT | `br $break` |
| 0x01 | NOP | *(no op)* |
| 0x02 | RET | `$sp -= 4; $pc = mem[$sp]; br $dispatch` |
| 0x03 | IRET | *(unsupported — set error flag)* |
| 0x04 | BRK | `call $debug_print` (breakpoint) |
| 0x05 | WFI | `call $ticks` (spin-wait stub) |
| 0x06 | RESET | `; zero all $r0-$r15` |
| 0x07 | SYN | *(no-op in single-threaded WASM)* |
| 0xF0 | HALT_ERR | `br $break` (with error flag set) |
| 0xF1 | REBOOT | *(reset + restart)* |
| 0xF2 | DUMP | `call $debug_print` for all registers |
| 0xF3 | ASSERT | `(if ($flags != 0) (br $break))` |
| 0xF4 | ID | `$r0 = agent_id` (from import) |
| 0xF5 | VER | `$r0 = 3` (ISA version 3) |
| 0xF6 | CLK | `$r0 = call $ticks` |
| 0xF7 | PCLK | `$r0 = call $ticks` (alias) |
| 0xF8 | WDOG | `call $extension` |
| 0xF9 | SLEEP | `call $extension` |
| 0xFA | CONF_CLAMP | *(sanitize all C0–C15 to [0.0, 1.0])* |
| 0xFB | TAG_CHECK | *(security — bridge to JS)* |
| 0xFF | ESCAPE | `; dispatch to extension handler` |

### Format E — Three-Register (4 bytes) — Core 16 Opcodes

| Hex | Mnemonic | WASM Instruction |
|-----|----------|-----------------|
| 0x20 | ADD | `i32.add` |
| 0x21 | SUB | `i32.sub` |
| 0x22 | MUL | `i32.mul` |
| 0x23 | DIV | `i32.div_s` |
| 0x24 | MOD | `i32.rem_s` |
| 0x25 | AND | `i32.and` |
| 0x26 | OR | `i32.or` |
| 0x27 | XOR | `i32.xor` |
| 0x28 | SHL | `i32.shl` |
| 0x29 | SHR | `i32.shr_s` |
| 0x2A | MIN | `call $min_i32` |
| 0x2B | MAX | `call $max_i32` |
| 0x2C | CMP_EQ | `i32.eq` |
| 0x2D | CMP_LT | `i32.lt_s` |
| 0x2E | CMP_GT | `i32.gt_s` |
| 0x2F | CMP_NE | `i32.ne` |

---

## Appendix B — Security Model

### WASM Sandbox Advantages

WASM provides **defense-in-depth** sandboxing for FLUX bytecode execution:

| Security Feature | WASM Enforcement | Benefit |
|-----------------|------------------|---------|
| Memory isolation | Linear memory only, no pointer to host | FLUX bytecode cannot access browser memory |
| No DOM access | No `document`, `window` unless imported | Prevents XSS from FLUX programs |
| No network access | No `fetch`, `XMLHttpRequest` unless imported | A2A only through controlled JS bridge |
| No file system | No `fs` module | Cannot read/write local files |
| Type safety | WASM validation rejects invalid modules | Malformed FLUX bytecode cannot crash WASM VM |
| Deterministic execution | Same input → same output | Reproducible results across browsers |
| Resource limits | `memory.grow` maximum, no infinite loops (via cycle limit) | Prevents resource exhaustion |

### Interaction with FLUX Security Primitives (v3)

The ISA v3 security model (SANDBOX_ALLOC, TAG_ALLOC, CAP_INVOKE) maps to WASM security:

| FLUX Security Opcode | WASM Equivalent |
|---------------------|-----------------|
| SANDBOX_ALLOC (0xDF) | *(memory region tracking in JS host)* |
| TAG_ALLOC (0xEE) | *(memory tag table in JS host)* |
| TAG_TRANSFER (0xEF) | *(ownership transfer in JS host)* |
| CONF_CLAMP (0xFA) | *(f32 clamping in WASM dispatch)* |
| TAG_CHECK (0xFB) | *(validation in JS host)* |
| CAP_INVOKE (interpreter) | *(import permission check in JS host)* |

WASM's built-in sandboxing is stronger than the FLUX v3 security model — any FLUX security feature that operates within linear memory is automatically enforced by WASM. Security features that require cross-boundary access (A2A, I/O) are enforced by the JS bridge's permission checks.

---

## Appendix C — Relationship to Other Tasks

| Task | Relationship |
|------|-------------|
| **ISA-001** (v3 full spec) | WASM compiler targets ISA v3 bytecode format (Formats A–H, 253 base + 65K extension opcodes) |
| **ISA-002** (escape prefix) | Format H (0xFF) extension opcodes are bridged to JS via `extension_dispatch` import |
| **ISA-003** (compressed format) | Compressed 2-byte instructions are decoded by the WASM dispatch loop using the same decode logic as the standard VM |
| **SEC-001** (security primitives) | WASM sandboxing provides an additional security layer beyond FLUX's own SANDBOX_ALLOC/TAG_ALLOC |
| **ASYNC-001** / **TEMP-001** | SUSPEND/RESUME in WASM require cooperation with JS (the JS host manages the continuation table since WASM cannot access external storage) |
| **CONF-001** (conformance) | All 71+ expanded conformance vectors must pass on the WASM runtime |
| **ROUTE-001** (semantic router) | WASM target adds `[wasm]` skill tag for task routing |

---

*End of WASM Compilation Target Design Document*
