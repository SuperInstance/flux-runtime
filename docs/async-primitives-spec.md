# FLUX ISA v4 — Async Primitives Specification

**Task Board:** ASYNC-001
**Author:** Super Z (Fleet Agent, Architect-rank)
**Date:** 2026-04-12
**Status:** DRAFT — Pending Review
**Depends On:** ISA v3 Unified (Format A–G encoding, opcode space 0x00–0xFF)

---

## Table of Contents

1. [Overview and Motivation](#1-overview-and-motivation)
2. [Opcode Summary Table](#2-opcode-summary-table)
3. [Extension Opcode Encoding](#3-extension-opcode-encoding)
4. [Continuation Handle Format](#4-continuation-handle-format)
5. [Coroutine Memory Model](#5-coroutine-memory-model)
6. [Opcode Specifications](#6-opcode-specifications)
   - 6.1 SUSPEND
   - 6.2 RESUME
   - 6.3 YIELD
   - 6.4 COROUTINE_SPAWN
   - 6.5 AWAIT_EVENT
   - 6.6 CHANNEL_SEND
   - 6.7 CHANNEL_RECV
   - 6.8 CHANNEL_CLOSE
   - 6.9 SELECT_EVENT
7. [Interaction with Existing Opcodes](#7-interaction-with-existing-opcodes)
8. [Error Semantics](#8-error-semantics)
9. [Pseudocode: Execution Engine Integration](#9-pseudocode-execution-engine-integration)
10. [Bytecode Examples](#10-bytecode-examples)
11. [Migration Notes](#11-migration-notes)

---

## 1. Overview and Motivation

### 1.1 Problem Statement

The FLUX bytecode VM currently supports only synchronous, single-threaded execution. The `YIELD` opcode at 0x15 provides basic cooperative multitasking (yield for N cycles), and `COYIELD`/`CORESUM` at 0xE5/0xE6 provide basic coroutine yield/resume. However, the fleet ecosystem requires:

- **First-class coroutines** that can suspend mid-computation and be resumed later
- **Event-driven async I/O** — agents must wait for A2A messages, sensor data, or fleet signals without blocking the entire VM
- **Inter-coroutine communication** via typed channels (producer/consumer patterns)
- **Continuation passing** — save and restore full execution state for cooperative scheduling

### 1.2 Design Principles

1. **Cooperative, not preemptive.** Coroutines explicitly suspend. The scheduler never forcefully deschedules a running coroutine.
2. **Zero-copy shared memory.** Coroutines spawned from the same parent share a memory region by default, with copy-on-write semantics for isolation.
3. **Continuation handles are opaque.** A continuation handle is a 64-bit value that the VM interprets internally. User code treats it as a token.
4. **Channels are typed and bounded.** Each channel has a fixed capacity, element type tag, and ownership semantics.
5. **Composability with existing control flow.** SUSPEND/RESUME compose naturally with CALL/RET, JAL, and ENTER/LEAVE.

### 1.3 Relationship to Existing Opcodes

| Existing Opcode | Hex | Relationship |
|----------------|-----|-------------|
| `YIELD` | 0x15 | Yield for N cycles (cycles-level granularity). New `YIELD` (async) yields to the scheduler. |
| `COYIELD` | 0xE5 | Basic coroutine yield (Format F: save + jump). New `SUSPEND` replaces this with proper continuation semantics. |
| `CORESUM` | 0xE6 | Basic coroutine resume (Format F). New `RESUME` subsumes this. |
| `FORK` | 0x58 | A2A agent spawn. New `COROUTINE_SPAWN` is lighter-weight: same-address-space, no A2A overhead. |
| `JOIN` | 0x59 | A2A agent join. `AWAIT_EVENT` provides same-pattern for coroutine completion. |
| `SIGNAL` | 0x5A | A2A signal emission. Maps to `CHANNEL_SEND` for coroutine-local signaling. |
| `AWAIT` | 0x5B | A2A signal wait. Maps to `CHANNEL_RECV` for coroutine-local waiting. |
| `CALL` / `RET` | 0x45 / 0x02 | Subroutine call/return. SUSPEND/RESUME operate at coroutine level, orthogonal to call stack. |

---

## 2. Opcode Summary Table

All async opcodes use the **EXTEND prefix** (0xFB, Format A). The actual opcode follows as the second byte:

```
  Byte 0: 0xFB (EXTEND_ASYNC)
  Byte 1: sub-opcode (see table below)
  Bytes 2+: operands per sub-format
```

| Sub-Opcode | Mnemonic | Sub-Format | Operands | Size (bytes) | Description |
|-----------|----------|-----------|----------|:------------:|-------------|
| 0x01 | `SUSPEND` | B | rd | 3 | Save state to continuation, write handle → rd |
| 0x02 | `RESUME` | B | rd | 3 | Restore continuation from handle in rd |
| 0x03 | `YIELD_ASYNC` | A | — | 2 | Cooperative yield to scheduler |
| 0x04 | `COROUTINE_SPAWN` | D | rd, imm8 (PC offset), imm8 (flags) | 4 | Spawn coroutine at PC+offset, handle → rd |
| 0x05 | `AWAIT_EVENT` | C | rd, imm8 (event type) | 3 | Block until event type fires, result → rd |
| 0x06 | `CHANNEL_SEND` | E | rd, rs1, rs2 | 5 | Send rs1 on channel rd, timeout rs2 (0=block) |
| 0x07 | `CHANNEL_RECV` | E | rd, rs1, rs2 | 5 | Receive from channel rd → rs1, timeout rs2 |
| 0x08 | `CHANNEL_CLOSE` | B | rd | 3 | Close channel identified by handle in rd |
| 0x09 | `SELECT_EVENT` | D | rd, imm16 (event mask) | 4 | Wait for any event in mask, fired event → rd |
| 0x0A | `COROUTINE_STATUS` | B | rd | 3 | Query status of coroutine handle in rd → flags |
| 0x0B | `COROUTINE_CANCEL` | B | rd | 3 | Cancel coroutine by handle in rd |

### Total: 11 opcodes, consuming sub-opcode range 0x01–0x0B

---

## 3. Extension Opcode Encoding

### 3.1 The EXTEND_ASYNC Prefix

The FLUX ISA reserves 0xFB for async extension. This byte is followed by a sub-opcode byte and additional operands. The full encoding for each sub-format:

```
Sub-Format A (EXTEND + 1 byte = 2 bytes total):
  [0xFB][sub_opcode]

Sub-Format B (EXTEND + 2 bytes = 3 bytes total):
  [0xFB][sub_opcode][rd:u8]

Sub-Format C (EXTEND + 2 bytes = 3 bytes total):
  [0xFB][sub_opcode][rd:u8][imm8:u8]

Sub-Format D (EXTEND + 3 bytes = 4 bytes total):
  [0xFB][sub_opcode][rd:u8][imm8_a:u8][imm8_b:u8]

Sub-Format E (EXTEND + 3 bytes = 4 bytes total):
  [0xFB][sub_opcode][rd:u8][rs1:u8][rs2:u8]
```

### 3.2 Sub-Format Size Table

| Sub-Format | Total Size | Operand Fields |
|-----------|-----------|----------------|
| A | 2 bytes | (none) |
| B | 3 bytes | rd |
| C | 3 bytes | rd, imm8 |
| D | 4 bytes | rd, imm8_a, imm8_b |
| E | 4 bytes | rd, rs1, rs2 |

### 3.3 Binary Encoding Diagram — SUSPEND (Sub-Format B)

```
Bit offset:  7    6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0
Byte 0:     [ 0  1 1 1 1 1 0 1 ]  ← 0xFB (EXTEND_ASYNC)
Byte 1:     [ 0  0 0 0 0 0 0 1 ]  ← 0x01 (SUSPEND sub-opcode)
Byte 2:     [ r  d  r  d  r  d  r  d ]  ← destination register for handle
             ↑ 0x00–0x0F (R0–R15)

Result: continuation_handle → R[rd]
```

### 3.4 Binary Encoding Diagram — COROUTINE_SPAWN (Sub-Format D)

```
Bit offset:  7    6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0
Byte 0:     [ 0  1 1 1 1 1 0 1 ]  [ 0 0 0 0 0 1 0 0 ]  [ p  c  p  c  h  h  h  h ]  [ f  f  f  f  f  f  f  f ]
             ↑ 0xFB (EXTEND)       ↑ 0x04 (SPAWN)       ↑ PC offset (u8)       ↑ flags (u8)

Flags byte:
  bit 0: SHARE_MEMORY (1 = share heap with parent)
  bit 1: SHARE_STACK  (1 = share stack region)
  bit 2: INHERIT_CAPS (1 = inherit parent capabilities)
  bit 3: DETACHED     (1 = coroutine runs independently, handle is fire-and-forget)
  bits 4-7: reserved (must be 0)

Result: coroutine_handle → R[rd]
```

### 3.5 Binary Encoding Diagram — CHANNEL_SEND (Sub-Format E)

```
Bit offset:  7    6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0  |  7 6 5 4 3 2 1 0
Byte 0:     [ 0  1 1 1 1 1 0 1 ]  [ 0 0 0 0 0 1 1 0 ]  [ c  h  c  h  c  h  c  h ]  [ d  d  d  d  d  d  d  d ]
             ↑ 0xFB (EXTEND)       ↑ 0x06 (CH_SEND)     ↑ channel handle        ↑ data value to send

Byte 3 (rs2): timeout in microseconds (0 = block forever, 0xFFFFFFFF = non-blocking poll)
```

---

## 4. Continuation Handle Format

### 4.1 Handle Structure

A continuation handle is a 64-bit opaque value stored in a general-purpose register (pairs R[rd]:R[rd+1] for 64-bit, or single register with 32-bit handle ID). Internally, the VM interprets it as:

```
Bit layout (64-bit, stored as R[rd] = low 32 bits, R[rd+1] = high 32 bits):

  63    56 55    48 47    32 31                0
  ┌───────┬───────┬────────┬──────────────────┐
  │ MAGIC │ CTYPE │ CORTID │     PC_SAVED     │
  │ 0xA5  │ type  │  id    │   saved PC       │
  │ (u8)  │ (u8)  │ (u16)  │     (u32)        │
  └───────┴───────┴────────┴──────────────────┘

MAGIC (0xA5): Constant magic byte, validates handle integrity.
CTYPE (type): Continuation type:
  0x01 = SUSPENDED_COROUTINE
  0x02 = CHANNEL_ENDPOINT
  0x03 = EVENT_SUBSCRIPTION
CORTID (id): Coroutine ID (0x0001–0xFFFF, 0x0000 = invalid).
PC_SAVED: Byte offset into bytecode where execution was suspended.
```

### 4.2 What Gets Saved on SUSPEND

When SUSPEND executes, the VM captures the following state into an internal `CoroutineState` table indexed by CORTID:

| Field | Source | Size | Description |
|-------|--------|------|-------------|
| `pc` | VM program counter | 4 bytes | Byte offset into bytecode |
| `gp_regs[16]` | R0–R15 | 64 bytes | Full general-purpose register file |
| `fp_regs[16]` | F0–F15 | 64 bytes | Floating-point register file |
| `vec_regs[16]` | V0–V15 | 256 bytes | SIMD vector register file |
| `sp` | R11 (SP) | 4 bytes | Stack pointer (duplicated from gp_regs for speed) |
| `fp_reg` | R14 (FP) | 4 bytes | Frame pointer (duplicated) |
| `lr` | R15 (LR) | 4 bytes | Link register (duplicated) |
| `flags` | condition flags | 4 bytes | zero, sign, carry, overflow flags |
| `confidence[16]` | parallel conf regs | 16 bytes | Confidence register file (per C_ADD etc.) |
| `call_depth` | frame stack depth | 4 bytes | Number of frames on the call stack |
| `cycle_count` | VM cycle counter | 8 bytes | Cycle count at suspension |
| `status` | coroutine state enum | 4 bytes | RUNNING, SUSPENDED, COMPLETED, CANCELLED, FAULTED |

**Total per continuation: ~440 bytes**

### 4.3 Stack Handling on SUSPEND

SUSPEND does **not** copy the stack. Instead, the coroutine's stack pointer (R11) is saved as-is. The stack memory region is either:
- **Shared** (default for spawned coroutines): Multiple coroutines reference the same stack region. Each coroutine has its own SP, so they effectively partition the stack.
- **Isolated**: Each coroutine gets its own stack region (created at spawn time).

When a coroutine is spawned with `SHARE_STACK=0`, the VM allocates a new stack region of default size (64 KB). The new coroutine's SP is initialized to the top of this region.

---

## 5. Coroutine Memory Model

### 5.1 Shared vs Isolated State

```
┌─────────────────────────────────────────────────┐
│                 Parent Coroutine                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ GP Regs  │  │ FP Regs  │  │ Stack Region │  │
│  │ R0–R15   │  │ F0–F15   │  │ (private)    │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────┐  ┌──────────────────────────────┐  │
│  │ Heap     │  │ Bytecode Region              │  │
│  │ (shared) │  │ (shared, read-only)          │  │
│  └──────────┘  └──────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ Confidence Register File                   │  │
│  │ (shared, but each coroutine has local      │  │
│  │  shadow copy merged on RESUME)             │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │ share_heap=1
         ▼
┌─────────────────────────────────────────────────┐
│              Child Coroutine                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ GP Regs  │  │ FP Regs  │  │ Stack Region │  │
│  │ (private)│  │ (private)│  │ (private)    │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  ┌──────────┐  ┌──────────────────────────────┐  │
│  │ Heap     │  │ Bytecode Region              │  │
│  │ (shared) │◄─│ (shared, read-only)          │  │
│  └──────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 5.2 Shared Heap Semantics

When `SHARE_MEMORY=1`:
- Both parent and child coroutine reference the same heap memory region.
- No automatic synchronization. Use `CHANNEL_SEND/RECV` or `FENCE` (0x07) for coordination.
- The heap is **not** reference-counted. The parent is responsible for heap lifetime.
- If a child coroutine writes to heap memory that the parent reads, the parent must `AWAIT_EVENT(COROUTINE_SUSPENDED)` or `YIELD_ASYNC` to observe the write (memory ordering).

When `SHARE_MEMORY=0`:
- The child gets a private heap region of the same size as the parent's.
- Data transfer between parent and child requires explicit `CHANNEL_SEND/RECV`.

### 5.3 Bytecode Sharing

All coroutines within the same VM instance share the **same bytecode region** (read-only). This means:
- All coroutines execute from the same compiled bytecode.
- `COROUTINE_SPAWN` takes a PC offset into the shared bytecode where the child begins execution.
- There is no per-coroutine code segment.

### 5.4 Confidence State Propagation

Each coroutine maintains a local confidence register shadow. On SUSPEND:
- The shadow is saved as part of the continuation state.
- If another coroutine modifies shared confidence registers during the suspension, the changes are **not** visible to the suspended coroutine (isolation guarantee).

On RESUME:
- The shadow is restored, overwriting any shared confidence register changes made during suspension.
- This ensures deterministic confidence propagation per coroutine.

---

## 6. Opcode Specifications

### 6.1 SUSPEND — Save Execution State

| Field | Value |
|-------|-------|
| **Mnemonic** | `SUSPEND` |
| **Sub-opcode** | 0x01 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFB][0x01][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | async/control |
| **Side Effects** | Saves coroutine state, changes coroutine status to SUSPENDED |

#### Semantics

1. The current coroutine's full execution state is saved (see Section 4.2).
2. A continuation handle is constructed and written to `R[rd]` (low 32 bits). If rd+1 < 16, high 32 bits go to `R[rd+1]`.
3. The coroutine's status changes from `RUNNING` to `SUSPENDED`.
4. Control returns to the scheduler. The VM's main execution loop picks the next runnable coroutine, or if none, returns control to the host.

#### Pseudocode

```python
def execute_SUSPEND(rd: int) -> None:
    cort = current_coroutine()
    state = capture_state(cort)
    handle = build_continuation_handle(cort.id, cort.pc)
    regs.write_gp(rd, handle & 0xFFFFFFFF)
    if rd + 1 < 16:
        regs.write_gp(rd + 1, (handle >> 32) & 0xFFFFFFFF)
    cort.status = CoroutineStatus.SUSPENDED
    scheduler.remove_runnable(cort.id)
    cort = scheduler.pick_next()
    if cort is None:
        vm.running = False  # all coroutines suspended
        return
    restore_state(cort)
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_DOUBLE_SUSPEND` | Coroutine is already SUSPENDED | FAULT trap (0xE7) with code 0x01 |
| `ERR_COROUTINE_COMPLETED` | Coroutine has already terminated | FAULT trap with code 0x02 |

---

### 6.2 RESUME — Restore Execution State

| Field | Value |
|-------|-------|
| **Mnemonic** | `RESUME` |
| **Sub-opcode** | 0x02 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFB][0x02][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | async/control |
| **Side Effects** | Switches to target coroutine |

#### Semantics

1. Read the continuation handle from `R[rd]` (and `R[rd+1]` if available).
2. Validate the handle: check magic byte (0xA5), check CTYPE is SUSPENDED_COROUTINE.
3. Save the **current** coroutine's state (implicit SUSPEND of caller).
4. Restore the target coroutine's state from the coroutine table.
5. Set target coroutine status to RUNNING.
6. Continue execution at the restored PC.

#### Pseudocode

```python
def execute_RESUME(rd: int) -> None:
    handle_lo = regs.read_gp(rd)
    handle_hi = regs.read_gp(rd + 1) if rd + 1 < 16 else 0
    handle = (handle_hi << 32) | handle_lo

    if (handle >> 56) & 0xFF != 0xA5:
        raise VMError("RESUME: invalid handle magic")

    cort_id = (handle >> 32) & 0xFFFF
    target = coroutine_table.get(cort_id)

    if target is None:
        raise VMError(f"RESUME: no coroutine with id {cort_id}")
    if target.status != CoroutineStatus.SUSPENDED:
        raise VMError(f"RESUME: coroutine {cort_id} not suspended (status={target.status})")

    # Implicit SUSPEND of current coroutine
    current = current_coroutine()
    capture_state(current)
    current.status = CoroutineStatus.SUSPENDED

    # RESUME target
    restore_state(target)
    target.status = CoroutineStatus.RUNNING
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_INVALID_HANDLE` | Magic byte != 0xA5 | FAULT trap with code 0x03 |
| `ERR_RESUME_COMPLETED` | Target coroutine already COMPLETED | FAULT trap with code 0x04 |
| `ERR_RESUME_SELF` | Resuming the currently running coroutine | No-op (ignored) |
| `ERR_RESUME_CANCELLED` | Target coroutine was CANCELLED | FAULT trap with code 0x05 |

---

### 6.3 YIELD_ASYNC — Cooperative Scheduler Yield

| Field | Value |
|-------|-------|
| **Mnemonic** | `YIELD_ASYNC` |
| **Sub-opcode** | 0x03 |
| **Format** | EXTEND + Sub-Format A |
| **Encoding** | `[0xFB][0x03]` |
| **Size** | 2 bytes |
| **Category** | async/scheduler |
| **Side Effects** | Yields timeslice to scheduler |

#### Semantics

1. Increment the current coroutine's yield counter.
2. Add the current coroutine to the **back** of the runnable queue (round-robin).
3. Pick the next runnable coroutine from the **front** of the queue.
4. If no other coroutine is runnable, continue executing the current coroutine (no-op yield).
5. Does **not** save state to a continuation handle. This is a lightweight yield.

#### Pseudocode

```python
def execute_YIELD_ASYNC() -> None:
    current = current_coroutine()
    current.yield_count += 1
    next_cort = scheduler.next_runnable(exclude=current.id)
    if next_cort is None:
        return  # no one else to run, continue
    scheduler.enqueue_runnable(current.id, position="back")
    switch_to(next_cort)
```

#### Distinction from Existing YIELD (0x15)

| Feature | `YIELD` (0x15) | `YIELD_ASYNC` (0xFB 0x03) |
|---------|----------------|---------------------------|
| Format | C (2 bytes) | EXTEND A (2 bytes) |
| Operand | imm8 (yield N cycles) | none |
| Granularity | Cycle-level busy-wait | Coroutine-level context switch |
| State saved | None | Full register file |
| Use case | Delay loops, polling | Cooperative multitasking |

---

### 6.4 COROUTINE_SPAWN — Create New Coroutine

| Field | Value |
|-------|-------|
| **Mnemonic** | `COROUTINE_SPAWN` |
| **Sub-opcode** | 0x04 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFB][0x04][rd:u8][pc_offset:u8][flags:u8]` |
| **Size** | 4 bytes |
| **Category** | async/lifecycle |
| **Side Effects** | Allocates new coroutine, creates stack region |

#### Semantics

1. Allocate a new coroutine ID from the coroutine table.
2. Create a new stack region (unless `SHARE_STACK=1`).
3. Create or share the heap region (based on `SHARE_MEMORY` flag).
4. Initialize the new coroutine's registers to zero.
5. Set the new coroutine's PC to `current.PC + sign_extend(pc_offset)`.
6. If `INHERIT_CAPS=1`, copy the parent's capability set to the child.
7. Write the coroutine handle to `R[rd]`.
8. If `DETACHED=1`, the coroutine is immediately added to the runnable queue and cannot be joined.

#### Flags Encoding

| Bit | Name | Default | Description |
|-----|------|---------|-------------|
| 0 | `SHARE_MEMORY` | 1 | Share heap with parent |
| 1 | `SHARE_STACK` | 0 | Share stack region |
| 2 | `INHERIT_CAPS` | 1 | Inherit parent capabilities |
| 3 | `DETACHED` | 0 | Fire-and-forget mode |
| 4–7 | reserved | 0 | Must be zero |

#### Pseudocode

```python
def execute_COROUTINE_SPAWN(rd: int, pc_offset: int, flags: int) -> None:
    cort_id = coroutine_table.allocate_id()
    cort = Coroutine(
        id=cort_id,
        pc=(vm.pc + sign_extend(pc_offset)) & 0xFFFFFFFF,
        parent_id=current_coroutine().id,
        bytecode=vm.bytecode,  # shared reference
    )

    if flags & 0x02:  # SHARE_STACK
        cort.stack_region = current_coroutine().stack_region
    else:
        cort.stack_region = memory.create_region(
            f"stack_cort_{cort_id}", 65536, "system"
        )
        cort.regs.sp = 65536  # top of new stack

    if flags & 0x01:  # SHARE_MEMORY
        cort.heap_region = current_coroutine().heap_region
    else:
        cort.heap_region = memory.create_region(
            f"heap_cort_{cort_id}", 65536, "system"
        )

    if flags & 0x04:  # INHERIT_CAPS
        cort.capabilities = copy(current_coroutine().capabilities)

    cort.status = CoroutineStatus.READY
    handle = build_continuation_handle(cort_id, cort.pc)
    regs.write_gp(rd, handle & 0xFFFFFFFF)

    if flags & 0x08:  # DETACHED
        scheduler.enqueue_runnable(cort_id)
    else:
        # Parent must RESUME the child to start it
        pass

    coroutine_table[cort_id] = cort
```

---

### 6.5 AWAIT_EVENT — Block Until Event Fires

| Field | Value |
|-------|-------|
| **Mnemonic** | `AWAIT_EVENT` |
| **Sub-opcode** | 0x05 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFB][0x05][rd:u8][event_type:u8]` |
| **Size** | 3 bytes |
| **Category** | async/event |
| **Side Effects** | Suspends coroutine until event |

#### Event Types

| Type | Code | Description | Result in rd |
|------|------|-------------|-------------|
| `EVT_COROUTINE_DONE` | 0x01 | Any child coroutine completed | Child's coroutine ID |
| `EVT_COROUTINE_DONE_SPECIFIC` | 0x02 | Specific coroutine (R[rd] = handle) completed | 1 (success) |
| `EVT_CHANNEL_READY` | 0x03 | Channel has data to receive | Channel handle |
| `EVT_CHANNEL_SPACE` | 0x04 | Channel has space to send | Channel handle |
| `EVT_A2A_MESSAGE` | 0x05 | Incoming A2A message available | Message buffer address |
| `EVT_TIMER` | 0x06 | Timer expired (R[rd] = timer ID) | Timer ID |
| `EVT_SIGNAL_FLEET` | 0x07 | Fleet-wide signal received | Signal ID |
| `EVT_DEADLINE` | 0x08 | Temporal deadline exceeded | Remaining budget (0) |
| `EVT_IO_COMPLETE` | 0x09 | Async I/O operation completed | I/O buffer address |
| `EVT_WAKEUP` | 0x0A | Explicit wakeup via COROUTINE_CANCEL | Canceller's coroutine ID |

#### Pseudocode

```python
def execute_AWAIT_EVENT(rd: int, event_type: int) -> None:
    current = current_coroutine()
    event = EventSubscription(
        coroutine_id=current.id,
        event_type=event_type,
        filter_value=regs.read_gp(rd),  # for SPECIFIC variants
    )
    event_table.register(event)
    current.status = CoroutineStatus.WAITING
    scheduler.remove_runnable(current.id)

    # Try to immediately satisfy from pending events
    pending = event_table.poll(event)
    if pending is not None:
        regs.write_gp(rd, pending.result)
        current.status = CoroutineStatus.RUNNING
        event_table.unregister(event)
    else:
        # Suspend and yield to scheduler
        next_cort = scheduler.pick_next()
        if next_cort is None:
            vm.running = False  # deadlock
            return
        switch_to(next_cort)
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_DEADLOCK` | No runnable coroutines and current is waiting | FAULT trap with code 0x10, sets flag_deadlock |
| `ERR_INVALID_EVENT` | event_type not in valid range | FAULT trap with code 0x06 |

---

### 6.6 CHANNEL_SEND — Send on Channel

| Field | Value |
|-------|-------|
| **Mnemonic** | `CHANNEL_SEND` |
| **Sub-opcode** | 0x06 |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFB][0x06][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | async/channel |
| **Side Effects** | Enqueues value on channel, may wake receiver |

#### Semantics

1. `R[rd]` holds the channel handle.
2. `R[rs1]` holds the value to send (32-bit integer).
3. `R[rs2]` holds the timeout in microseconds (0 = block forever, 0xFFFFFFFF = non-blocking poll).
4. If the channel has space, the value is enqueued.
5. If the channel is full:
   - If timeout > 0: wait until space becomes available or timeout expires.
   - If timeout == 0xFFFFFFFF: return immediately with R[rd] = 0 (failure).
   - If timeout == 0: block indefinitely.
6. If a coroutine is waiting on `AWAIT_EVENT(EVT_CHANNEL_READY)` for this channel, it is woken.

#### Pseudocode

```python
def execute_CHANNEL_SEND(rd: int, rs1: int, rs2: int) -> None:
    ch_handle = regs.read_gp(rd)
    value = regs.read_gp(rs1)
    timeout_us = regs.read_gp(rs2)

    channel = channel_table.get(ch_handle)
    if channel is None:
        raise VMError("CHANNEL_SEND: invalid channel handle")

    if channel.is_closed:
        regs.write_gp(rd, 0)  # failure
        return

    if not channel.is_full():
        channel.enqueue(value)
        regs.write_gp(rd, 1)  # success
        wake_waiters(channel, "RECV")
        return

    # Channel full — handle timeout
    if timeout_us == 0xFFFFFFFF:
        regs.write_gp(rd, 0)  # non-blocking fail
        return

    if timeout_us == 0:
        # Block until space
        current = current_coroutine()
        current.status = CoroutineStatus.WAITING
        channel.waiters_send.append(current.id)
        next_cort = scheduler.pick_next()
        if next_cort:
            switch_to(next_cort)
        else:
            raise VMError("CHANNEL_SEND: deadlock — all coroutines blocked on channels")
    else:
        # Timed wait
        deadline = vm.wall_clock_us + timeout_us
        current = current_coroutine()
        current.status = CoroutineStatus.WAITING_TIMED
        channel.waiters_send.append((current.id, deadline))
        scheduler.register_timer(current.id, deadline)
        next_cort = scheduler.pick_next()
        if next_cort:
            switch_to(next_cort)
```

---

### 6.7 CHANNEL_RECV — Receive from Channel

| Field | Value |
|-------|-------|
| **Mnemonic** | `CHANNEL_RECV` |
| **Sub-opcode** | 0x07 |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFB][0x07][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | async/channel |
| **Side Effects** | Dequeues value from channel, may wake sender |

#### Semantics

1. `R[rd]` holds the channel handle.
2. On success: received value is written to `R[rs1]`, and `R[rd]` = 1 (success).
3. On failure (closed, timeout): `R[rd]` = 0 (failure), `R[rs1]` unchanged.
4. `R[rs2]` holds the timeout in microseconds (same encoding as CHANNEL_SEND).

---

### 6.8 CHANNEL_CLOSE — Close Channel

| Field | Value |
|-------|-------|
| **Mnemonic** | `CHANNEL_CLOSE` |
| **Sub-opcode** | 0x08 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFB][0x08][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | async/channel |
| **Side Effects** | Closes channel, wakes all waiters with failure |

#### Semantics

1. Close the channel identified by the handle in `R[rd]`.
2. All coroutines blocked on CHANNEL_SEND or CHANNEL_RECV for this channel are woken.
3. Woken coroutines receive `R[rd] = 0` (failure) from their send/recv operation.
4. The channel handle becomes invalid.

---

### 6.9 SELECT_EVENT — Multi-Event Wait

| Field | Value |
|-------|-------|
| **Mnemonic** | `SELECT_EVENT` |
| **Sub-opcode** | 0x09 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFB][0x09][rd:u8][event_mask_lo:u8][event_mask_hi:u8]` |
| **Size** | 4 bytes |
| **Category** | async/event |
| **Side Effects** | Blocks until any masked event fires |

#### Semantics

The 16-bit event mask (imm16) specifies which event types to wait for. When any of the masked events fire, the event type code is written to `R[rd]`. This is a multiplexed version of AWAIT_EVENT.

---

### 6.10 COROUTINE_STATUS — Query Coroutine State

| Field | Value |
|-------|-------|
| **Mnemonic** | `COROUTINE_STATUS` |
| **Sub-opcode** | 0x0A |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFB][0x0A][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | async/debug |
| **Side Effects** | None (read-only) |

#### Status Flag Encoding (written to R[rd])

| Bit | Name | Meaning |
|-----|------|---------|
| 0 | `ST_READY` | Coroutine is runnable |
| 1 | `ST_RUNNING` | Coroutine is currently executing |
| 2 | `ST_SUSPENDED` | Coroutine is suspended (has continuation) |
| 3 | `ST_WAITING` | Coroutine is waiting on an event |
| 4 | `ST_COMPLETED` | Coroutine has terminated normally |
| 5 | `ST_CANCELLED` | Coroutine was cancelled |
| 6 | `ST_FAULTED` | Coroutine terminated with a fault |
| 7 | `ST_DETACHED` | Coroutine is in detached mode |

---

### 6.11 COROUTINE_CANCEL — Cancel Coroutine

| Field | Value |
|-------|-------|
| **Mnemonic** | `COROUTINE_CANCEL` |
| **Sub-opcode** | 0x0B |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFB][0x0B][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | async/lifecycle |
| **Side Effects** | Terminates target coroutine, reclaims resources |

#### Semantics

1. Extract coroutine ID from handle in `R[rd]`.
2. If the target is currently RUNNING: set a cancellation flag. The target will observe it on its next scheduling point (SUSPEND, YIELD_ASYNC, or CHANNEL_SEND/RECV).
3. If the target is SUSPENDED/WAITING: immediately mark as CANCELLED and reclaim its stack region (if private).
4. If the target is COMPLETED: no-op.
5. Wake any coroutines waiting on `AWAIT_EVENT(EVT_COROUTINE_DONE)` for the target.

---

## 7. Interaction with Existing Opcodes

### 7.1 SUSPEND/RESUME vs CALL/RET

```
CALL/RET:
  - Operates on the call stack (LIFO)
  - Saves only PC (pushed to stack) and LR (implicit)
  - Fast (single push/pop)
  - Cannot suspend mid-computation across scheduling boundaries

SUSPEND/RESUME:
  - Operates on the coroutine table (arbitrary set)
  - Saves full register file, flags, confidence state
  - Slower (~440 bytes of state)
  - Can suspend at any point, resume later from different code
```

**Composition:** SUSPEND can be called from within a CALL'd function. The saved state includes the call stack depth. When RESUME'd, execution continues inside the CALL'd function.

### 7.2 SUSPEND vs HALT

| Feature | HALT (0x00) | SUSPEND |
|---------|-------------|---------|
| Execution | VM stops entirely | Coroutine suspends, others continue |
| Resumable | No (requires VM reset) | Yes (via RESUME handle) |
| State saved | None | Full continuation |
| Use case | Program termination | Cooperative multitasking |

### 7.3 COROUTINE_SPAWN vs FORK (0x58)

| Feature | FORK (A2A) | COROUTINE_SPAWN |
|---------|-----------|-----------------|
| Scope | Cross-agent (different VMs) | Same VM, same bytecode |
| Communication | A2A protocol (TELL/ASK) | Shared memory + channels |
| Overhead | High (serialization, transport) | Low (register save) |
| Isolation | Full (separate address space) | Configurable (shared/isolated heap) |
| Trust | Requires TRUST setup | Inheritable capabilities |

### 7.4 CHANNEL_SEND/RECV vs TELL/ASK (0x50/0x51)

| Feature | TELL/ASK | CHANNEL_SEND/RECV |
|---------|----------|-------------------|
| Target | Named agent (string) | Channel handle (integer) |
| Transport | A2A message bus | In-process queue |
| Latency | High (serialization) | Low (memory copy) |
| Type safety | None (byte stream) | Channel typed at creation |
| Flow control | None | Bounded capacity |

---

## 8. Error Semantics

### 8.1 Error Classification

| Error Code | Name | Severity | Recovery |
|-----------|------|----------|----------|
| 0x01 | `ERR_DOUBLE_SUSPEND` | Fatal | Cannot resume (undefined state) |
| 0x02 | `ERR_COROUTINE_COMPLETED` | Fatal | Handle is stale |
| 0x03 | `ERR_INVALID_HANDLE` | Fatal | Handle magic check failed |
| 0x04 | `ERR_RESUME_COMPLETED` | Recoverable | Check COROUTINE_STATUS first |
| 0x05 | `ERR_RESUME_CANCELLED` | Recoverable | Spawn new coroutine |
| 0x06 | `ERR_INVALID_EVENT` | Fatal | Fix event type code |
| 0x07 | `ERR_CHANNEL_INVALID` | Fatal | Channel handle corrupted |
| 0x08 | `ERR_CHANNEL_CLOSED` | Recoverable | Check before send/recv |
| 0x09 | `ERR_CHANNEL_TIMEOUT` | Recoverable | Retry or abort |
| 0x0A | `ERR_COROUTINE_TABLE_FULL` | Fatal | Max 65535 coroutines |
| 0x0B | `ERR_STACK_ALLOC_FAILED` | Fatal | Out of memory |
| 0x10 | `ERR_DEADLOCK` | Fatal | All coroutines blocked |
| 0x11 | `ERR_CHANNEL_DEADLOCK` | Fatal | Cycle in channel wait graph |

### 8.2 Deadlock Detection

The VM performs a deadlock check before suspending the current coroutine:

```python
def check_deadlock() -> bool:
    """Returns True if suspending current would deadlock all coroutines."""
    if scheduler.has_runnable():
        return False
    # All coroutines are SUSPENDED or WAITING
    # Check for channel cycles (A waits for B's channel, B waits for A's channel)
    wait_graph = build_wait_graph()
    return has_cycle(wait_graph)
```

### 8.3 Double-Suspend Protection

```python
def execute_SUSPEND(rd: int) -> None:
    cort = current_coroutine()
    if cort.status != CoroutineStatus.RUNNING:
        raise VMFault(
            "DOUBLE_SUSPEND: coroutine not running",
            fault_code=0x01,
            pc=vm.pc,
        )
    # ... normal SUSPEND logic
```

### 8.4 Resume-After-Complete Protection

```python
def execute_RESUME(rd: int) -> None:
    # ... handle validation ...
    target = coroutine_table[cort_id]
    if target.status == CoroutineStatus.COMPLETED:
        raise VMFault(
            "RESUME_COMPLETED: coroutine already terminated",
            fault_code=0x04,
            pc=vm.pc,
        )
    # ... normal RESUME logic
```

---

## 9. Pseudocode: Execution Engine Integration

### 9.1 Modified Main Loop

```python
class AsyncInterpreter(Interpreter):
    """Extended interpreter with coroutine support."""

    MAX_COROUTINES = 65535

    def __init__(self, bytecode: bytes, **kwargs):
        super().__init__(bytecode, **kwargs)
        self._coroutine_table: dict[int, Coroutine] = {}
        self._channel_table: dict[int, Channel] = {}
        self._event_table: EventTable = EventTable()
        self._scheduler = Scheduler()
        self._current_cort_id: int = 0

        # Bootstrap: create main coroutine
        main_cort = Coroutine(id=0, pc=0, bytecode=bytecode)
        main_cort.status = CoroutineStatus.RUNNING
        self._coroutine_table[0] = main_cort

    def execute(self) -> int:
        self.running = True
        while self.running and not self.halted:
            if self.cycle_count >= self.max_cycles:
                break
            cort = self.current_coroutine()
            if cort is None or cort.status != CoroutineStatus.RUNNING:
                # Try to schedule another coroutine
                cort = self._scheduler.pick_next()
                if cort is None:
                    break  # all done or deadlocked
                self.switch_to(cort)
            self._step()
            self.cycle_count += 1
        self.running = False
        return self.cycle_count

    def _dispatch_async(self, sub_opcode: int) -> None:
        """Handle EXTEND_ASYNC (0xFB) prefix."""
        if sub_opcode == 0x01:
            (rd,) = self._decode_operands_B()
            self._exec_suspend(rd)
        elif sub_opcode == 0x02:
            (rd,) = self._decode_operands_B()
            self._exec_resume(rd)
        elif sub_opcode == 0x03:
            self._exec_yield_async()
        elif sub_opcode == 0x04:
            rd, pc_off, flags = self._decode_ext_format_d()
            self._exec_coroutine_spawn(rd, pc_off, flags)
        elif sub_opcode == 0x05:
            rd, event_type = self._decode_operands_B()
            self._exec_await_event(rd, event_type)
        elif sub_opcode == 0x06:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_channel_send(rd, rs1, rs2)
        elif sub_opcode == 0x07:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_channel_recv(rd, rs1, rs2)
        elif sub_opcode == 0x08:
            (rd,) = self._decode_operands_B()
            self._exec_channel_close(rd)
        elif sub_opcode == 0x09:
            rd, mask_lo, mask_hi = self._decode_ext_format_d()
            self._exec_select_event(rd, (mask_hi << 8) | mask_lo)
        elif sub_opcode == 0x0A:
            (rd,) = self._decode_operands_B()
            self._exec_coroutine_status(rd)
        elif sub_opcode == 0x0B:
            (rd,) = self._decode_operands_B()
            self._exec_coroutine_cancel(rd)
        else:
            raise VMInvalidOpcodeError(
                f"Unknown async sub-opcode: 0x{sub_opcode:02X}",
                opcode=0xFB,
            )
```

### 9.2 Channel Implementation

```python
class Channel:
    """Bounded, typed channel for inter-coroutine communication."""

    MAX_CAPACITY = 4096

    def __init__(self, capacity: int, element_type: int = 0):
        self.capacity = min(capacity, self.MAX_CAPACITY)
        self.element_type = element_type  # 0=i32, 1=f32, 2=i64, 3=handle
        self.buffer: collections.deque[int] = collections.deque()
        self.waiters_send: list[tuple[int, int]] = []  # (cort_id, deadline_us)
        self.waiters_recv: list[tuple[int, int]] = []
        self.closed = False
        self.total_sent = 0
        self.total_recv = 0

    def is_full(self) -> bool:
        return len(self.buffer) >= self.capacity

    def is_empty(self) -> bool:
        return len(self.buffer) == 0

    def enqueue(self, value: int) -> None:
        self.buffer.append(value)
        self.total_sent += 1

    def dequeue(self) -> int:
        value = self.buffer.popleft()
        self.total_recv += 1
        return value
```

---

## 10. Bytecode Examples

### Example 1: Basic Suspend and Resume

```
; Coroutine A: compute partial result, suspend, later resume
; R0 = accumulator, R1 = continuation handle

MOVI  R0, 10          ; R0 = 10  (Format D: [0x2B][0x00][0x0A][0x00])
ADDI  R0, R0, 5       ; R0 = 15  (Format D: [0x19][0x00][0x05])
SUSPEND R1            ; Save state, handle → R1  (EXTEND B: [0xFB][0x01][0x01])
; --- coroutine is now suspended, scheduler runs ---
; --- later, another coroutine does RESUME R1 ---
ADDI  R0, R0, 20      ; R0 = 35  (only executes after RESUME)
HALT                  ; (Format A: [0x00])

; Binary: 2B 00 0A 00  19 00 05  FB 01 01  19 00 14  00
;        = MOVI R0,10  ADDI R0,5  SUSPEND R1  ADDI R0,20  HALT
```

### Example 2: Spawn Two Coroutines, Join Both

```
; Main coroutine: spawn worker A and worker B, wait for both

; --- Spawn Worker A at offset +20 from current PC ---
MOVI  R0, 0x03        ; flags = SHARE_MEMORY | INHERIT_CAPS
COROUTINE_SPAWN R2, 20, R0  ; handle → R2, worker starts at PC+20
; Encoding: [0xFB][0x04][0x02][0x14][0x03]

; --- Spawn Worker B at offset +40 from current PC ---
COROUTINE_SPAWN R3, 40, R0  ; handle → R3, worker starts at PC+40
; Encoding: [0xFB][0x04][0x03][0x28][0x03]

; --- Wait for both to complete ---
AWAIT_EVENT R2, 0x01  ; Wait for any child completion
; Encoding: [0xFB][0x05][0x02][0x01]

AWAIT_EVENT R3, 0x01  ; Wait for second child
; Encoding: [0xFB][0x05][0x03][0x01]

; Both done — sum results from shared heap
LOAD  R4, [0x1000]    ; Worker A's result (heap address 0x1000)
LOAD  R5, [0x2000]    ; Worker B's result (heap address 0x2000)
ADD   R0, R4, R5      ; R0 = A_result + B_result
HALT

; --- Worker A (at offset +20) ---
MOVI  R0, 42
STORE R0, [0x1000]    ; Write result to shared heap
HALT                  ; Completes coroutine

; --- Worker B (at offset +40) ---
MOVI  R0, 58
STORE R0, [0x2000]    ; Write result to shared heap
HALT                  ; Completes coroutine
```

### Example 3: Producer-Consumer via Channel

```
; --- Create channel (via syscall) ---
MOVI  R0, 16          ; capacity = 16
SYS   0x20            ; SYS_CREATE_CHANNEL(capacity) → handle in R0
MOV   R1, R0          ; R1 = channel handle (shared between coroutines)

; --- Spawn producer coroutine ---
MOVI  R0, 0x01        ; flags = SHARE_MEMORY
COROUTINE_SPAWN R2, 30, R0  ; producer starts at PC+30

; --- Consumer loop ---
CONSUMER_LOOP:
CHANNEL_RECV R1, R3, R4  ; recv from channel → R3, timeout R4=0 (block)
; Encoding: [0xFB][0x07][0x01][0x03][0x04]
JZ    R1, CONSUMER_DONE  ; if R1==0, channel closed
ADD   R5, R5, R3      ; R5 += received value
JMP   CONSUMER_LOOP    ; repeat

CONSUMER_DONE:
HALT

; --- Producer coroutine (at offset +30) ---
MOVI  R6, 0           ; counter
PRODUCER_LOOP:
MOVI  R4, 0           ; timeout = 0 (block)
CHANNEL_SEND R1, R6, R4  ; send R6 on channel
; Encoding: [0xFB][0x06][0x01][0x06][0x04]
INC   R6
CMP   R6, 10
JLT   PRODUCER_LOOP
CHANNEL_CLOSE R1       ; close channel
; Encoding: [0xFB][0x08][0x01]
HALT
```

### Example 4: Coroutine Cancellation

```
; Spawn a long-running worker, give it 1000 cycles, then cancel

; Spawn worker
MOVI  R0, 0x01
COROUTINE_SPAWN R1, 15, R0  ; worker at PC+15

; Wait 1000 cycles (busy wait with yields)
MOVI  R2, 1000
WAIT_LOOP:
DEC   R2
YIELD_ASYNC              ; yield to let worker run
JNZ   R2, WAIT_LOOP

; Check worker status
COROUTINE_STATUS R1      ; status flags → R1
; Encoding: [0xFB][0x0A][0x01]
ANDI  R1, 0x10          ; check ST_COMPLETED bit (bit 4)
JNZ   R1, WORKER_DONE   ; already finished

; Cancel the worker
COROUTINE_CANCEL R1
; Encoding: [0xFB][0x0B][0x01]

WORKER_DONE:
HALT

; --- Worker (at offset +15) ---
WORKER_LOOP:
MOVI  R0, 0
YIELD_ASYNC
JMP   WORKER_LOOP       ; infinite loop (will be cancelled)
```

### Example 5: Multi-Event Select with Timeout

```
; Wait for either: a message on channel A, a timer, or an A2A signal.
; Use SELECT_EVENT with a timeout mechanism.

; Setup: create timer event
MOVI  R0, 5000         ; 5000 microsecond timeout
SYS   0x30             ; SYS_CREATE_TIMER(R0) → timer_handle → R0
MOV   R10, R0          ; save timer handle

; Build event mask: EVT_CHANNEL_READY (0x03) | EVT_TIMER (0x06) | EVT_A2A_MESSAGE (0x05)
; Mask = 0x03 | 0x06 | 0x05 = 0x07 (but as 16-bit: 0x006B = bits for 0x03, 0x05, 0x06)
MOVI16 R0, 0x006B     ; event mask
; Encoding: [0x40][0x00][0x00][0x6B]

SELECT_EVENT R1, R0     ; wait for any masked event → R1
; Encoding: [0xFB][0x09][0x01][0x6B][0x00]

; Check which event fired
CMP_EQ R2, R1, 0x03    ; channel ready?
JNZ   R2, HANDLE_CHANNEL
CMP_EQ R2, R1, 0x06    ; timer expired?
JNZ   R2, HANDLE_TIMER
CMP_EQ R2, R1, 0x05    ; A2A message?
JNZ   R2, HANDLE_A2A
JMP   UNKNOWN_EVENT

HANDLE_CHANNEL:
CHANNEL_RECV R5, R3, R4  ; receive the message
; ... process message ...
JMP   DONE

HANDLE_TIMER:
; Timeout — cleanup
JMP   DONE

HANDLE_A2A:
; Process A2A message
ASK   R3, R4, R5       ; query another agent
JMP   DONE

DONE:
HALT
```

### Example 6: Ping-Pong Between Two Coroutines

```
; Classic coroutine ping-pong using SUSPEND/RESUME

; Main: spawn ping and pong, link them
COROUTINE_SPAWN R1, 20, 0x01  ; ping coroutine
COROUTINE_SPAWN R2, 35, 0x01  ; pong coroutine

; Start ping by resuming it
RESUME R1                   ; start ping
; Encoding: [0xFB][0x02][0x01]

; Both will alternate via RESUME until counter exhausted
AWAIT_EVENT R0, 0x01       ; wait for any to complete
AWAIT_EVENT R0, 0x01       ; wait for the other
HALT

; --- Ping coroutine (at offset +20) ---
MOVI  R0, 5              ; 5 rounds
PING_LOOP:
DEC   R0
JZ    PING_DONE
MOVI  R5, 1              ; signal: "ping"
CHANNEL_SEND R3, R5, 0    ; send on channel (R3 set by main before resume)
RESUME R2                 ; yield to pong
JMP   PING_LOOP
PING_DONE:
CHANNEL_CLOSE R3
HALT

; --- Pong coroutine (at offset +35) ---
PONG_LOOP:
CHANNEL_RECV R3, R5, 0    ; receive ping
JZ    R3, PONG_DONE       ; channel closed
MOVI  R5, 2              ; signal: "pong"
CHANNEL_SEND R3, R5, 0    ; send response
RESUME R1                 ; yield back to ping
JMP   PONG_LOOP
PONG_DONE:
HALT
```

---

## 11. Migration Notes

### 11.1 Backward Compatibility

- All existing opcodes (0x00–0xFA) are unchanged.
- The EXTEND_ASYNC prefix (0xFB) was previously `RESERVED_FB`. Code that relied on 0xFB causing an ILLEGAL trap will now see it as a valid prefix.
- Existing `YIELD` (0x15) remains unchanged for cycle-level yielding.
- Existing `COYIELD` (0xE5) and `CORESUM` (0xE6) are **not** deprecated but are superseded by the new SUSPEND/RESUME for new code.

### 11.2 Required Interpreter Changes

1. Add EXTEND_ASYNC dispatch to `_step()` method.
2. Add coroutine table, channel table, event table to the Interpreter class.
3. Modify the main `execute()` loop to support coroutine scheduling.
4. Add `_exec_suspend`, `_exec_resume`, `_exec_yield_async`, etc. methods.
5. Add deadlock detection before each SUSPEND/AWAIT.

### 11.3 Required Encoder/Decoder Changes

1. `BytecodeEncoder` must recognize SUSPEND, RESUME, etc. and emit the 0xFB prefix.
2. `BytecodeDecoder` must handle the 2-byte prefix and dispatch to sub-decoders.
3. Disassembler must print `SUSPEND R1` instead of raw `FB 01 01`.

### 11.4 Test Plan

| Test | Description |
|------|-------------|
| `test_suspend_resume_basic` | Suspend and resume a single coroutine, verify register continuity |
| `test_spawn_join` | Spawn two workers, both complete, verify results |
| `test_channel_ping_pong` | Producer sends N values, consumer receives all |
| `test_channel_deadlock` | Two coroutines deadlock on channels, verify FAULT |
| `test_double_suspend` | Attempt to suspend already-suspended coroutine, verify FAULT |
| `test_resume_completed` | Attempt to resume completed coroutine, verify FAULT |
| `test_cancel_running` | Cancel a running coroutine, verify cleanup |
| `test_select_event` | Multi-event wait with timer, verify correct event returned |
| `test_shared_heap` | Parent and child share heap, verify data visibility |
| `test_confidence_isolation` | Verify confidence registers are isolated per coroutine |

---

**End of Async Primitives Specification — ASYNC-001**
