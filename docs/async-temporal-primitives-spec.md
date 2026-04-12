# FLUX Async & Temporal Primitives Specification

**Task ID:** 15d
**Oracle1 Board:** ASYNC-001 + TEMP-001
**Author:** Super Z (FLUX Fleet)
**Date:** 2026-06-06
**Status:** DRAFT — Pending review

---

## Table of Contents

1. [Overview](#1-overview)
2. [Relationship to Existing Opcodes](#2-relationship-to-existing-opcodes)
3. [Async Primitives (ASYNC-001)](#3-async-primitives-async-001)
   - 3.1 SUSPEND
   - 3.2 RESUME
   - 3.3 YIELD (Existing)
   - 3.4 CONTINUATION_ID
4. [Temporal Primitives (TEMP-001)](#4-temporal-primitives-temp-001)
   - 4.1 DEADLINE_BEFORE
   - 4.2 YIELD_IF_CONTENTION
   - 4.3 PERSIST_CRITICAL_STATE
   - 4.4 TICKS_ELAPSED
5. [Continuation Serialization Format](#5-continuation-serialization-format)
6. [Fiber Design](#6-fiber-design)
   - 6.1 Fiber Architecture
   - 6.2 Fiber Table Layout
   - 6.3 Fiber Scheduler
   - 6.4 Fiber Lifecycle
7. [Opcode Assignment Proposals](#7-opcode-assignment-proposals)
8. [Decoder Changes Required](#8-decoder-changes-required)
9. [Conformance Test Vectors](#9-conformance-test-vectors)
10. [Implementation Priority](#10-implementation-priority)

---

## 1. Overview

This specification defines two families of new VM primitives for the FLUX unified ISA:

| Family | Board ID | Purpose | Primitives |
|--------|----------|---------|------------|
| **Async** | ASYNC-001 | Execution suspension, resumption, and A2A state handoff | SUSPEND, RESUME, YIELD, CONTINUATION_ID |
| **Temporal** | TEMP-001 | Time-bounded execution, contention-aware yielding, state persistence | DEADLINE_BEFORE, YIELD_IF_CONTENTION, PERSIST_CRITICAL_STATE, TICKS_ELAPSED |

### Design Goals

1. **A2A-Native**: Continuations are serializable as JSON for agent-to-agent transmission
2. **Cooperative**: All async operations are voluntary — no preemptive interrupts
3. **Confidence-Aware**: Temporal primitives integrate with the confidence register file
4. **Minimal Encoding**: Single-register operand encoding (Format B) where possible
5. **Fiber-Compatible**: Primitives compose into a lightweight cooperative threading model

### Scope

These primitives operate at the **VM execution level**. They are distinct from the A2A protocol primitives (Branch, Fork, CoIterate, Discuss, Synthesize, Reflect) defined in `flux/a2a/primitives.py`, which operate at the **coordination protocol level**. However, SUSPEND/RESUME provide the mechanism by which protocol-level primitives can serialize and transmit VM state across agents.

---

## 2. Relationship to Existing Opcodes

The converged ISA already contains several related opcodes. The new primitives generalize and extend these:

| Existing Opcode | Hex | Range | New Primitive | Relationship |
|----------------|-----|-------|---------------|--------------|
| YIELD | 0x15 | Format C | *(kept as-is)* | YIELD accepts imm8 cycle count; remains the basic cooperative yield |
| COYIELD | 0xE5 | Format F | SUSPEND | COYIELD saves state and jumps to imm16. SUSPEND saves state to a handle without jumping — more flexible for A2A handoff |
| CORESUM | 0xE6 | Format F | RESUME | CORESUM restores state from an implicit coroutine. RESUME restores from an explicit handle register — enables cross-agent continuation |
| SWITCH | 0xE4 | Format F | *(kept as-is)* | SWITCH performs a full context switch. SUSPEND is a lighter-weight variant that doesn't immediately switch to a specific target |
| CLK | 0xF6 | Format A | TICKS_ELAPSED | CLK writes cycle count to r0 only. TICKS_ELAPSED writes to any destination register |
| WDOG | 0xF8 | Format A | DEADLINE_BEFORE | WDOG kicks a hardware watchdog. DEADLINE_BEFORE sets a configurable software deadline that auto-suspends rather than rebooting |
| SEMA | 0x14 | Format C | YIELD_IF_CONTENTION | SEMA performs semaphore operations. YIELD_IF_CONTENTION is a higher-level check-and-yield pattern for contention avoidance |

### Key Distinctions

- **COYIELD vs SUSPEND**: COYIELD is coroutine-specific (hardcodes save+jump-to-imm16). SUSPEND is handle-based (save to a transferable continuation handle, no mandatory jump target).
- **CORESUM vs RESUME**: CORESUM restores from a coroutine register indexed by rd. RESUME restores from an explicit continuation handle in a register, enabling cross-agent execution transfer.
- **CLK vs TICKS_ELAPSED**: CLK is zero-operand (result always in r0). TICKS_ELAPSED allows the result in any register, enabling composition with confidence checks and deadline comparisons.

---

## 3. Async Primitives (ASYNC-001)

### 3.1 SUSPEND — Save Execution State

**Opcode:** 0xED (proposed)
**Format:** B — `[0xED][handle_reg]` — 2 bytes
**Category:** `async`
**Source:** `converged`

#### Semantics

```
SUSPEND R1    ; R1 = <continuation_handle>
```

1. Serialize the current VM execution state into a **continuation** structure
2. Generate a unique continuation handle (64-bit ID)
3. Store the continuation in the VM's continuation table, keyed by handle
4. Write the continuation handle to `handle_reg`
5. Advance PC by instruction size (the instruction after SUSPEND is the resume point)
6. The VM transitions to a **SUSPENDED** state — the fiber is descheduled

#### Execution State Snapshot

The continuation includes:
- **PC**: Program counter pointing to the instruction *after* SUSPEND
- **Registers (R0–R15)**: All 16 general-purpose registers
- **Confidence Registers (CR0–CR15)**: All 16 confidence registers
- **Stack**: The full operand stack (up to `sp`)
- **Stack Pointer (SP)**: Current stack pointer value
- **Flags**: Zero, negative, carry, overflow flags
- **Deadline**: Current deadline register (if DEADLINE_BEFORE is active)
- **Fiber ID**: The executing fiber's ID
- **Memory Access Pattern**: Which memory regions were modified (for dirty-page tracking)

#### Post-SUSPEND Behavior

- The fiber is removed from the scheduler's ready queue
- If this is the only fiber, the VM enters an idle state
- If other fibers are ready, the scheduler selects the next one
- The continuation remains valid until explicitly freed or the VM shuts down

#### Error Conditions

| Condition | Behavior |
|-----------|----------|
| Continuation table full | Set error flag, R1 = 0, continue execution |
| Handle register out of range | ILLEGAL trap (0xFF) |

#### Example: A2A Handoff Pattern

```
; Agent A: compute partial result, suspend for Agent B to continue
MOVI  R0, 42        ; partial result
SUSPEND R1          ; R1 = continuation handle (continues after this instruction)
TELL  R2, R3, R1    ; send continuation handle to Agent B
HALT                ; Agent A done for now
; --- Agent B receives handle ---
RESUME R1           ; restore state, continue from after SUSPEND
ADD   R0, R0, R8    ; continue computation with Agent B's data
HALT
```

---

### 3.2 RESUME — Restore Execution State

**Opcode:** 0xEE (proposed)
**Format:** B — `[0xEE][handle_reg]` — 2 bytes
**Category:** `async`
**Source:** `converged`

#### Semantics

```
RESUME R1    ; restore VM state from continuation handle in R1
```

1. Read the continuation handle from `handle_reg`
2. Look up the continuation in the VM's continuation table
3. Restore PC, registers, confidence registers, stack, SP, flags, deadline
4. **Exception**: the `handle_reg` itself receives the continuation handle value (preserved), not restored from the snapshot
5. The fiber is placed back on the scheduler's ready queue
6. Execution continues from the saved PC

#### Interaction with Current Fiber

RESUME replaces the **current fiber's** state with the restored state. This is a destructive operation for the current execution context:

- If you need to preserve the current state, SUSPEND first, then RESUME the other continuation
- The current fiber's identity changes to match the restored fiber

#### Error Conditions

| Condition | Behavior |
|-----------|----------|
| Invalid handle (not in table) | Set error flag, continue execution |
| Handle register is 0 | No-op (set error flag) |
| Handle register out of range | ILLEGAL trap (0xFF) |

#### Example: State Round-Trip

```
; Setup
MOVI  R0, 100       ; R0 = 100
MOVI  R1, 200       ; R1 = 200
SUSPEND R2          ; save state, R2 = handle

; Modify state to prove restoration
MOVI  R0, 999       ; R0 = 999 (will be overwritten by RESUME)
MOVI  R1, 888       ; R1 = 888 (will be overwritten by RESUME)

; Restore
RESUME R2           ; restore: R0=100, R1=200, R2=handle (preserved)
; At this point: R0 = 100, R1 = 200, R2 = continuation handle
```

---

### 3.3 YIELD — Cooperative Multitasking (Existing)

**Opcode:** 0x15
**Format:** C — `[0x15][imm8]` — 2 bytes
**Category:** `concurrency`
**Source:** `converged` (existing)

#### Relationship to New Primitives

YIELD remains unchanged. It provides a lightweight cooperative yield for a specified number of cycles. The key differences from SUSPEND:

| Feature | YIELD | SUSPEND |
|---------|-------|---------|
| Operand | imm8 (cycle count) | handle_reg |
| State serialization | No (internal scheduler) | Yes (continuation table) |
| A2A transferable | No | Yes |
| Resume mechanism | Automatic (after imm8 cycles) | Explicit (RESUME) |
| Encoding size | 2 bytes | 2 bytes |

YIELD is the preferred primitive for **same-VM cooperative multitasking**. SUSPEND is for **cross-agent state handoff** or **long-term suspension** where the continuation may be transmitted to another agent.

---

### 3.4 CONTINUATION_ID — Query Current Execution State ID

**Opcode:** 0xEF (proposed)
**Format:** B — `[0xEF][dest_reg]` — 2 bytes
**Category:** `async`
**Source:** `converged`

#### Semantics

```
CONTINUATION_ID R0   ; R0 = unique ID for current execution state
```

1. Generate a unique identifier for the **current** execution point
2. The ID is a hash of: PC + register file hash + stack hash + agent ID
3. Write the 64-bit ID to `dest_reg` (lower 64 bits; upper bits zero for 64-bit register)
4. Does **not** create a full continuation — this is a lightweight fingerprint
5. Useful for: A2A handoff negotiation ("here's my state fingerprint"), checkpointing, deduplication

#### Use Case: A2A Negotiation

```
; Before suspending, announce state to potential collaborators
CONTINUATION_ID R0      ; R0 = state fingerprint
BCAST R1, R2, R0        ; broadcast: "I have this execution state"
; ... wait for ASK responses ...
SUSPEND R3              ; actually suspend and get full handle
TELL  R4, R5, R3        ; send full continuation to chosen agent
```

#### Collision Resistance

The ID uses a 64-bit hash. Collision probability is ~1 in 2^64 for random states, which is sufficient for fleet-scale operations. For stronger guarantees, agents can verify the full continuation after receiving the handle.

---

## 4. Temporal Primitives (TEMP-001)

### 4.1 DEADLINE_BEFORE — Set Execution Deadline

**Opcode:** 0xFA (proposed)
**Format:** B — `[0xFA][ticks_reg]` — 2 bytes
**Category:** `temporal`
**Source:** `converged`

#### Semantics

```
DEADLINE_BEFORE R1    ; auto-suspend if R1 more ticks elapse
```

1. Read the tick count from `ticks_reg` — this is the **budget** in VM cycles
2. Record the **deadline tick** = current_ticks + R1
3. Store the deadline in a VM-global deadline register
4. At each subsequent instruction dispatch, the scheduler checks: `if current_ticks >= deadline_tick: SUSPEND`
5. When deadline triggers, the VM performs an implicit SUSPEND: saves state, generates a handle, deschedules the fiber
6. The implicit SUSPEND handle is stored in a special register (R15 by convention, or a VM-global slot)

#### Interaction with TICKS_ELAPSED

```
MOVI      R1, 1000          ; 1000-tick budget
DEADLINE_BEFORE R1          ; set deadline
; ... computation loop ...
TICKS_ELAPSED R2            ; R2 = elapsed ticks
CMP_LT    R3, R2, R1       ; R3 = (elapsed < budget)?
JZ        R3, .timeout      ; if budget exceeded, handle timeout
```

#### Stacking

Only one deadline is active at a time. Calling DEADLINE_BEFORE replaces the previous deadline. To nest deadlines, use a pattern like:

```
MOVI  R1, 1000
DEADLINE_BEFORE R1    ; outer deadline: 1000 ticks
; ... inner work ...
TICKS_ELAPSED R2
SUB   R3, R1, R2      ; remaining ticks
DEADLINE_BEFORE R3    ; inner deadline: remaining time
```

#### Error Conditions

| Condition | Behavior |
|-----------|----------|
| ticks_reg = 0 | No deadline (remove any active deadline) |
| ticks_reg < 0 | Set as absolute tick value (not relative) |

---

### 4.2 YIELD_IF_CONTENTION — Conditional Yield on Resource Contention

**Opcode:** 0xFB (proposed)
**Format:** B — `[0xFB][resource_id_reg]` — 2 bytes
**Category:** `temporal`
**Source:** `converged`

#### Semantics

```
YIELD_IF_CONTENTION R1    ; yield if resource R1 is contended
```

1. Read the resource identifier from `resource_id_reg`
2. Check the VM's resource contention table for the given resource
3. **If the resource is contended** (another fiber holds it):
   - Perform a YIELD with imm8 = 1 (yield for minimum time)
   - The scheduler may boost the priority of the fiber holding the resource
   - Set the **contention flag** in the flags register
4. **If the resource is free**:
   - Continue execution immediately (no-op)
   - Clear the **contention flag**

#### Resource Identifiers

Resources are identified by integer IDs. Common resource types:

| ID Range | Resource Type |
|----------|--------------|
| 0x0000–0x00FF | Memory regions (256 regions) |
| 0x0100–0x01FF | I/O ports |
| 0x0200–0x02FF | A2A channels |
| 0x0300–0x03FF | Shared data structures |
| 0x0400–0xFFFF | User-defined |

#### Contention Table

The VM maintains a **contention table** tracking which fibers hold which resources:

```
contention_table[resource_id] = {
    "owner": fiber_id | None,
    "waiters": [fiber_id, ...],
    "hold_time": ticks,
}
```

The table is updated by:
- ATOMIC (0xD4): atomically acquires a resource
- CAS (0xD5): compare-and-swap acquires a resource
- YIELD_IF_CONTENTION: adds current fiber to waiters list
- Fiber scheduler: assigns resource to next waiter when owner releases

#### Example: Cooperative Spinlock Replacement

```
.loop:
YIELD_IF_CONTENTION R1     ; R1 = shared memory region ID
; If we get here, resource is free
ATOMIC  R2, R1, 0x0000     ; acquire resource (Format G: ATOMIC)
; ... critical section ...
; Release: write 0 to contention table
MOVI   R3, 0
STORE  R3, R4, R1          ; release (convention: store 0 = free)
```

---

### 4.3 PERSIST_CRITICAL_STATE — Save Registers to Persistent Storage

**Opcode:** 0xFC (proposed)
**Format:** B — `[0xFC][mask_reg]` — 2 bytes
**Category:** `temporal`
**Source:** `converged`

#### Semantics

```
PERSIST_CRITICAL_STATE R1   ; R1 = bitmask of registers to persist
```

1. Read the register mask from `mask_reg` (16-bit bitmask, one bit per register)
2. For each set bit `i` in the mask:
   - Write `R[i]` to a **persistent state slot** in non-volatile VM memory
   - Also write the corresponding confidence register `CR[i]` if it exists
3. The persistent state survives VM shutdown and restart
4. On VM restart, `RESTORE_CRITICAL_STATE` (or automatic restoration) reloads the persisted values

#### Mask Format

```
Bit 0  → R0
Bit 1  → R1
Bit 2  → R2
...
Bit 15 → R15
```

Example: Persist R0, R1, and R5 → mask = 0b00100011 = 0x23

#### Persistent Memory Region

Persisted state is stored in a designated VM memory region:

```
Persistent State Region (at address 0xF000, 128 bytes):
  +0x00: Magic number (0xFLUXPST)
  +0x08: Version (1)
  +0x0C: Mask (which registers are persisted)
  +0x10: R0 value (8 bytes)
  +0x18: R1 value (8 bytes)
  ...
  +0x88: CR0 value (8 bytes, confidence)
  +0x90: CR1 value (8 bytes, confidence)
  ...
  +0xF8: Checksum (CRC32 of above)
```

#### Interaction with SUSPEND

SUSPEND already saves the full register file to the continuation table. PERSIST_CRITICAL_STATE is for a different use case: **surviving VM restart**. Key differences:

| Feature | SUSPEND | PERSIST_CRITICAL_STATE |
|---------|---------|----------------------|
| Scope | Full VM state | Selected registers only |
| Volatility | Lost on VM restart | Survives VM restart |
| Size | Large (full continuation) | Small (register values) |
| Restoration | Explicit RESUME | Automatic on restart |
| A2A transferable | Yes (via handle) | No (local persistent memory) |

#### Example: Graceful Shutdown

```
; Agent is about to shut down — save important results
MOVI  R1, 0x0003          ; mask: persist R0 and R1
PERSIST_CRITICAL_STATE R1
; ... shutdown sequence ...
HALT_ERR                  ; halt with error flag set
```

On restart:
```
; VM auto-restores R0=previous_value, R1=previous_value
MOVI  R2, 0
CMP_NE R3, R0, R2        ; check if R0 was persisted
JZ    R3, .no_state       ; if R0 == 0, no persisted state
; ... continue from persisted state ...
.no_state:
; ... cold start ...
```

---

### 4.4 TICKS_ELAPSED — Query Cycle Count

**Opcode:** 0xFD (proposed)
**Format:** B — `[0xFD][dest_reg]` — 2 bytes
**Category:** `temporal`
**Source:** `converged`

#### Semantics

```
TICKS_ELAPSED R0    ; R0 = number of VM cycles since start (or since last reset)
```

1. Read the VM's cycle counter
2. Write the counter value to `dest_reg`
3. The counter is **monotonically increasing** — it never decreases
4. Counter width: 64-bit (wraps around at 2^64 - 1)
5. The counter counts **dispatched instructions** (not wall-clock time)

#### Relationship to CLK (0xF6)

| Feature | CLK (0xF6) | TICKS_ELAPSED (0xFD) |
|---------|-----------|---------------------|
| Format | A (no operand) | B (dest_reg) |
| Destination | Always R0 | Any register |
| Encoding size | 1 byte | 2 bytes |
| Confidence awareness | No | Yes (also writes to CR[dest]) |

TICKS_ELAPSED is the recommended replacement for CLK in new code. CLK remains for backward compatibility.

#### Confidence Integration

TICKS_ELAPSED also writes a **confidence value** to the corresponding confidence register:

```
TICKS_ELAPSED R5    ; R5 = tick count, CR5 = tick confidence
```

The tick confidence starts at 1.0 and decays:
- 1.0 for the first 10,000 ticks
- Linear decay to 0.5 at 1,000,000 ticks
- Minimum 0.1 after 10,000,000 ticks

This decay models the increasing uncertainty in time-based reasoning for long-running computations. Agents can use C_THRESH to skip operations when temporal confidence is too low.

#### Example: Bounded Computation with Confidence

```
MOVI           R1, 5000       ; budget: 5000 ticks
DEADLINE_BEFORE R1
.compute:
TICKS_ELAPSED  R2              ; check progress
; ... computation ...
C_THRESH       R2, 200         ; if tick confidence < 200/255, skip next
JMP            .compute         ; loop (skipped if confidence too low)
.fallback:
; use approximate result
```

---

## 5. Continuation Serialization Format

Continuations are serialized to JSON for A2A transmission. This enables one agent to suspend its computation, transmit the state to another agent, and have that agent resume the computation.

### 5.1 JSON Schema

```json
{
  "$schema": "flux.continuation/v1",
  "id": "cont_550e8400-e29b-41d4-a716-446655440000",
  "version": 1,
  "created_at": "2026-06-06T12:00:00Z",
  "source_agent": "agent-oracle1",
  "isa_version": "1.0.0",

  "state": {
    "pc": 42,
    "registers": [100, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "confidence": [1.0, 0.95, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "stack": [42, 17, 8],
    "sp": 3,
    "flags": {
      "zero": false,
      "negative": false,
      "carry": true,
      "overflow": false,
      "contention": false
    },
    "deadline_tick": 1042,
    "fiber_id": "fiber_001"
  },

  "memory": {
    "format": "dirty_pages",
    "pages": [
      {
        "base": 0,
        "size": 256,
        "data": "AQIDBA=="
      }
    ]
  },

  "checksum": "a1b2c3d4",
  "size_bytes": 512
}
```

### 5.2 Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID v4 for the continuation |
| `version` | int | Serialization format version |
| `created_at` | string | ISO 8601 timestamp |
| `source_agent` | string | Agent ID that created the continuation |
| `isa_version` | string | ISA version string for compatibility checking |
| `state.pc` | int | Program counter (instruction offset from start of bytecode) |
| `state.registers` | array[int16] | R0 through R15 (16 elements) |
| `state.confidence` | array[float] | CR0 through CR15 (16 elements, 0.0–1.0) |
| `state.stack` | array[int16] | Operand stack contents |
| `state.sp` | int | Stack pointer (number of valid stack entries) |
| `state.flags` | object | CPU flags |
| `state.deadline_tick` | int/null | Active deadline, or null if none |
| `state.fiber_id` | string | Fiber that was executing |
| `memory.format` | string | Memory serialization format |
| `memory.pages` | array | Dirty memory pages (base64-encoded data) |
| `checksum` | string | CRC32 of the serialized JSON (excluding this field) |
| `size_bytes` | int | Approximate size of the continuation |

### 5.3 Memory Serialization Strategies

The `memory.format` field determines how VM memory is included:

| Format | Description | Size | Use Case |
|--------|-------------|------|----------|
| `"none"` | No memory included | Minimal | Computation-only continuations (no memory deps) |
| `"dirty_pages"` | Only modified pages | Small–Medium | Most common — captures only what changed |
| `"full_snapshot"` | Entire 64KB memory | Large | Full VM migration |
| `"referenced"` | Pages referenced by stack/registers | Medium | Balanced approach |

Default: `"dirty_pages"`. The VM tracks dirty pages via a write-notice bitmap.

### 5.4 Compatibility Checking

Before resuming a continuation, the receiving VM checks:

1. **ISA version match**: `isa_version` must be compatible with the receiving VM
2. **Register count**: Must be 16 (R0–R15) and 16 confidence registers
3. **Memory size**: Receiving VM must have at least as much memory as referenced
4. **Checksum**: CRC32 must match (detects corruption in transit)
5. **Bytecode availability**: The original bytecode must be available at the receiving VM

If compatibility fails, RESUME sets the error flag and continues execution without restoring.

### 5.5 Size Estimates

| Component | Approximate Size |
|-----------|-----------------|
| Metadata (id, version, timestamps) | ~200 bytes |
| Registers (16 × int16) | ~100 bytes JSON |
| Confidence (16 × float) | ~200 bytes JSON |
| Stack (typical: 10 entries) | ~80 bytes JSON |
| Memory (dirty pages: 1 page) | ~400 bytes (base64) |
| **Total (minimal)** | **~500–1000 bytes** |
| **Total (full snapshot)** | **~100–200 KB** |

The compact size makes continuations practical for A2A message payloads.

---

## 6. Fiber Design

Fibers are lightweight cooperative threads within a single FLUX VM. They provide the execution context for async and temporal primitives.

### 6.1 Fiber Architecture

```
┌─────────────────────────────────────────────────┐
│                  FLUX VM                        │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Fiber 0  │  │ Fiber 1  │  │ Fiber N  │     │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │     │
│  │ │State │ │  │ │State │ │  │ │State │ │     │
│  │ │ PC   │ │  │ │ PC   │ │  │ │ PC   │ │     │
│  │ │ R0-15│ │  │ │ R0-15│ │  │ │ R0-15│ │     │
│  │ │ CR0-15│ │  │ │ CR0-15│ │  │ │ CR0-15│ │     │
│  │ │ Stack│ │  │ │ Stack│ │  │ │ Stack│ │     │
│  │ │Flags │ │  │ │Flags │ │  │ │Flags │ │     │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │     │
│  │Status:RDY│  │Status:RDY│  │Status:SUS│     │
│  │Prio:  5  │  │Prio:  5  │  │Prio:  3  │     │
│  │Deadline:0│  │Deadline:0│  │Deadline:42│     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │           Fiber Scheduler               │   │
│  │  Ready Queue: [Fiber0, Fiber1, ...]     │   │
│  │  Suspended List: [Fiber2, ...]          │   │
│  │  A2A Pending: [FiberN, ...]             │   │
│  │  Algorithm: Round-Robin + Priority Boost│   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │        Continuation Table               │   │
│  │  handle_0 → {state, memory, metadata}   │   │
│  │  handle_1 → {state, memory, metadata}   │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │       Resource Contention Table         │   │
│  │  resource_id → {owner, waiters, ...}    │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 6.2 Fiber Table Layout

Each fiber occupies a contiguous block in VM memory. The **fiber table** is a data structure (not necessarily in bytecode-addressable memory) managed by the VM runtime.

#### In-Memory Representation (Python)

```python
@dataclass
class Fiber:
    """A single cooperative fiber in the FLUX VM."""
    fiber_id: str              # Unique identifier (UUID or sequential)
    status: str                # READY | RUNNING | SUSPENDED | BLOCKED | COMPLETED
    priority: int              # 0-15, higher = more important
    base_priority: int         # Original priority (before boosts)
    
    # Execution state
    pc: int = 0                # Program counter
    registers: list[int] = field(default_factory=lambda: [0] * 16)
    confidence: list[float] = field(default_factory=lambda: [1.0] * 16)
    stack: list[int] = field(default_factory=list)
    sp: int = 0                # Stack pointer
    flags: dict = field(default_factory=dict)
    
    # Temporal state
    deadline_tick: int = 0     # 0 = no deadline
    ticks_used: int = 0        # Total ticks consumed
    last_run_tick: int = 0     # When this fiber last ran
    
    # Continuation
    continuation_handle: int = 0  # 0 = no associated continuation
    
    # Resource ownership
    held_resources: list[int] = field(default_factory=list)
    waiting_for: int = 0       # Resource ID this fiber is waiting on (0 = none)
```

#### Fiber Table (Array Form)

For C runtime compatibility, fibers can be stored in a flat array:

```
Fiber Table (at memory address 0xE000, max 64 fibers):

Entry Size: 320 bytes per fiber
Total: 64 × 320 = 20,480 bytes

Offset  Size  Field
0x00    4     fiber_id (32-bit)
0x04    1     status (0=READY, 1=RUNNING, 2=SUSPENDED, 3=BLOCKED, 4=COMPLETED)
0x05    1     priority (0-15)
0x06    1     base_priority (0-15)
0x07    1     padding
0x08    8     pc (64-bit)
0x10    128   registers (16 × 8 bytes)
0x90    128   confidence (16 × 8 bytes, IEEE 754 double)
0x110   4     sp (32-bit)
0x114   4     stack_capacity (32-bit)
0x118   1     flags_zero
0x119   1     flags_negative
0x11A   1     flags_carry
0x11B   1     flags_overflow
0x11C   1     flags_contention
0x11D   3     padding
0x120   8     deadline_tick (64-bit)
0x128   8     ticks_used (64-bit)
0x130   8     last_run_tick (64-bit)
0x138   8     continuation_handle (64-bit)
0x140   16    held_resources (8 × 2 bytes)
0x150   2     waiting_for (16-bit resource ID)
0x152   46    padding/reserved
Total: 0x180 = 384 bytes per fiber
```

### 6.3 Fiber Scheduler

The fiber scheduler determines which fiber runs next after a YIELD, SUSPEND, or TICKS check.

#### Algorithm: Round-Robin with Priority Boost

```
function schedule_next(current_fiber, event):
    # 1. Update current fiber state based on event
    if event == SUSPEND:
        current_fiber.status = SUSPENDED
    elif event == YIELD:
        current_fiber.status = READY
        current_fiber.priority = current_fiber.base_priority
    elif event == BLOCKED:
        current_fiber.status = BLOCKED
    
    # 2. Priority boost for A2A responses
    for msg in pending_a2a_messages:
        target_fiber = find_fiber_by_agent(msg.receiver)
        if target_fiber and target_fiber.status == SUSPENDED:
            target_fiber.status = READY
            target_fiber.priority = min(target_fiber.priority + 3, 15)
    
    # 3. Check deadlines
    for fiber in ready_queue + suspended_list:
        if fiber.deadline_tick > 0 and current_tick >= fiber.deadline_tick:
            fiber.status = SUSPENDED  # implicit SUSPEND
            fiber.continuation_handle = generate_handle()
            save_continuation(fiber.continuation_handle, fiber)
    
    # 4. Wake blocked fibers whose resources are free
    for fiber in blocked_list:
        if not is_contended(fiber.waiting_for):
            fiber.status = READY
            fiber.waiting_for = 0
    
    # 5. Select next fiber (round-robin within highest priority)
    ready = [f for f in all_fibers if f.status == READY]
    if not ready:
        return None  # idle
    
    max_priority = max(f.priority for f in ready)
    candidates = [f for f in ready if f.priority == max_priority]
    
    # Round-robin among candidates
    next_fiber = candidates[current_rr_index % len(candidates)]
    current_rr_index += 1
    
    next_fiber.status = RUNNING
    next_fiber.last_run_tick = current_tick
    return next_fiber
```

#### Priority Levels

| Priority | Use Case | Boost Behavior |
|----------|----------|----------------|
| 15 | Interrupt handlers, A2A urgent responses | Maximum — always runs next |
| 12–14 | A2A response fibers | +3 boost on incoming message |
| 8–11 | Normal computation fibers | Standard round-robin |
| 4–7 | Background tasks | Reduced timeslice |
| 0–3 | Idle/maintenance tasks | Only runs when nothing else is ready |

#### A2A Priority Boost

When a TELL, ASK, or SIGNAL message arrives for a SUSPENDED fiber, that fiber receives a **priority boost** of +3 (capped at 15). This ensures A2A responses are handled promptly, preventing deadlocks in request-response patterns.

After the boosted fiber runs, its priority decays back to `base_priority` by -1 per scheduling round.

### 6.4 Fiber Lifecycle

```
                  FORK (0x58)
                     │
                     ▼
    ┌─────────────────────────────────────────┐
    │              CREATED                    │
    └─────────────┬───────────────────────────┘
                  │ (scheduler picks up)
                  ▼
    ┌─────────────────────────────────────────┐
    │              READY                      │◄──────────────┐
    └─────────────┬───────────────────────────┘               │
                  │ (scheduler dispatches)                    │
                  ▼                                           │
    ┌─────────────────────────────────────────┐    YIELD/     │
    │              RUNNING                    │───────────────┘
    └──┬──────────┬──────────┬────────────────┘
       │          │          │
       │ SUSPEND  │ BLOCKED  │ HALT/HALT_ERR
       │          │          │
       ▼          ▼          ▼
  ┌─────────┐ ┌─────────┐ ┌───────────┐
  │SUSPENDED│ │ BLOCKED │ │ COMPLETED │
  └──┬──────┘ └──┬──────┘ └───────────┘
     │ RESUME     │ resource freed
     ▼            │
  (→ READY)  (→ READY)
```

#### State Transitions

| From | To | Trigger | New Primitives Used |
|------|-----|---------|-------------------|
| READY | RUNNING | Scheduler dispatch | — |
| RUNNING | READY | YIELD (0x15) | — |
| RUNNING | SUSPENDED | SUSPEND (0xED) | SUSPEND |
| RUNNING | SUSPENDED | DEADLINE_BEFORE exceeded | DEADLINE_BEFORE |
| RUNNING | READY | YIELD_IF_CONTENTION (no contention) | YIELD_IF_CONTENTION |
| RUNNING | READY | YIELD_IF_CONTENTION (contention, after yield) | YIELD_IF_CONTENTION |
| SUSPENDED | READY | RESUME (0xEE) | RESUME |
| SUSPENDED | READY | A2A message arrives | — (scheduler boost) |
| BLOCKED | READY | Resource freed | YIELD_IF_CONTENTION |
| RUNNING | COMPLETED | HALT (0x00) / HALT_ERR (0xF0) | — |
| ANY | COMPLETED | VM shutdown | — |

---

## 7. Opcode Assignment Proposals

### 7.1 Proposed Assignments

| Hex | Mnemonic | Format | Size | Category | Description |
|-----|----------|--------|------|----------|-------------|
| 0xED | SUSPEND | B | 2 | async | Save VM state to continuation handle |
| 0xEE | RESUME | B | 2 | async | Restore VM state from continuation handle |
| 0xEF | CONTINUATION_ID | B | 2 | async | Query current execution state fingerprint |
| 0xFA | DEADLINE_BEFORE | B | 2 | temporal | Set execution deadline (tick budget) |
| 0xFB | YIELD_IF_CONTENTION | B | 2 | temporal | Yield if resource is contended |
| 0xFC | PERSIST_CRITICAL_STATE | B | 2 | temporal | Save registers to persistent storage |
| 0xFD | TICKS_ELAPSED | B | 2 | temporal | Query cycle count to any register |

### 7.2 Rationale

- **0xED–0xEF**: These were reserved in the Format F range (0xE0–0xEF). We repurpose them as Format B (2 bytes), since they only need a single register operand. The `decode_instruction` function in `formats.py` must be updated to handle this exception.
- **0xFA–0xFD**: These were reserved in the Format A range (0xF0–0xFF). We repurpose them as Format B for the same reason.
- **0xFE**: Left reserved for potential future use (e.g., RESTORE_CRITICAL_STATE as a companion to 0xFC).
- **7 opcodes** use 7 of the 9 previously reserved slots, leaving 2 for future expansion.

### 7.3 Full Opcode Range After Changes

```
0xE0  JMPL         Format F   Long relative jump
0xE1  JALL         Format F   Long jump-and-link
0xE2  CALLL        Format F   Long call
0xE3  TAIL         Format F   Tail call
0xE4  SWITCH       Format F   Context switch
0xE5  COYIELD      Format F   Coroutine yield
0xE6  CORESUM      Format F   Coroutine resume
0xE7  FAULT        Format F   Raise fault
0xE8  HANDLER      Format F   Install fault handler
0xE9  TRACE        Format F   Trace log
0xEA  PROF_ON      Format F   Start profiling
0xEB  PROF_OFF     Format F   End profiling
0xEC  WATCH        Format F   Watchpoint
0xED  SUSPEND      Format B   ★ NEW: Save continuation
0xEE  RESUME       Format B   ★ NEW: Restore continuation
0xEF  CONTINUATION_ID Format B ★ NEW: Query state ID

...

0xF4  ID           Format A   Agent ID
0xF5  VER          Format A   ISA version
0xF6  CLK          Format A   Cycle count → R0
0xF7  PCLK         Format A   Performance counter
0xF8  WDOG         Format A   Watchdog
0xF9  SLEEP        Format A   Low-power sleep
0xFA  DEADLINE_BEFORE Format B ★ NEW: Set deadline
0xFB  YIELD_IF_CONTENTION Format B ★ NEW: Contention yield
0xFC  PERSIST_CRITICAL_STATE Format B ★ NEW: Persist registers
0xFD  TICKS_ELAPSED Format B   ★ NEW: Cycle count → any reg
0xFE  (reserved)   Format A   Reserved for RESTORE_CRITICAL_STATE
0xFF  ILLEGAL      Format A   Illegal instruction
```

---

## 8. Decoder Changes Required

The current `decode_instruction` function in `formats.py` uses a range-based dispatch that falls through to `"unknown"` for opcodes >= 0x70. The new opcodes require:

### 8.1 Updated Decode Logic

```python
def decode_instruction(data: bytes) -> Tuple[int, dict]:
    """Decode an instruction from bytes. Returns (opcode, fields)."""
    if not data:
        raise ValueError("Empty data")
    
    opcode = data[0]
    
    # Existing ranges (0x00-0x6F) — unchanged
    if opcode <= 0x03:
        return opcode, {"format": "A", "size": 1}
    elif opcode <= 0x0F:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode <= 0x17:
        return opcode, {"format": "C", "size": 2, "imm8": data[1]}
    elif opcode <= 0x1F:
        return opcode, {"format": "D", "size": 3, "rd": data[1], "imm8": data[2]}
    elif opcode <= 0x3F:
        return opcode, {"format": "E", "size": 4, "rd": data[1], "rs1": data[2], "rs2": data[3]}
    elif opcode <= 0x47:
        imm16 = (data[2] << 8) | data[3]
        return opcode, {"format": "F", "size": 4, "rd": data[1], "imm16": imm16}
    elif opcode <= 0x4F:
        imm16 = (data[3] << 8) | data[4]
        return opcode, {"format": "G", "size": 5, "rd": data[1], "rs1": data[2], "imm16": imm16}
    elif opcode <= 0x6F:
        return opcode, {"format": "E", "size": 4, "rd": data[1], "rs1": data[2], "rs2": data[3]}
    
    # ★ NEW: Async primitives (0xED-0xEF) — Format B encoding
    elif opcode == 0xED:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode == 0xEE:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode == 0xEF:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    
    # ★ NEW: Temporal primitives (0xFA-0xFD) — Format B encoding
    elif opcode == 0xFA:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode == 0xFB:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode == 0xFC:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    elif opcode == 0xFD:
        return opcode, {"format": "B", "size": 2, "rd": data[1]}
    
    # ★ NEW: Extended ranges (0x70-0xFF) — proper dispatch
    elif opcode <= 0x9F:
        # 0x70-0x9F: Format E (viewpoint, sensor, math, crypto)
        return opcode, {"format": "E", "size": 4, "rd": data[1], "rs1": data[2], "rs2": data[3]}
    elif opcode <= 0xCF:
        # 0xA0-0xAF: mixed D and E; 0xB0-0xCF: Format E
        if opcode <= 0xAF and opcode in (0xA0,):
            return opcode, {"format": "D", "size": 3, "rd": data[1], "imm8": data[2]}
        elif opcode == 0xA4:
            imm16 = (data[3] << 8) | data[4]
            return opcode, {"format": "G", "size": 5, "rd": data[1], "rs1": data[2], "imm16": imm16}
        return opcode, {"format": "E", "size": 4, "rd": data[1], "rs1": data[2], "rs2": data[3]}
    elif opcode <= 0xDF:
        # 0xD0-0xDF: Format G
        imm16 = (data[3] << 8) | data[4]
        return opcode, {"format": "G", "size": 5, "rd": data[1], "rs1": data[2], "imm16": imm16}
    elif opcode <= 0xEC:
        # 0xE0-0xEC: Format F
        imm16 = (data[2] << 8) | data[3]
        return opcode, {"format": "F", "size": 4, "rd": data[1], "imm16": imm16}
    
    # Remaining: 0xFE, 0xFF — Format A
    else:
        return opcode, {"format": "A", "size": 1}
```

### 8.2 OPCODE_FORMAT Mapping Update

The `OPCODE_FORMAT` dict at the bottom of `formats.py` must be extended:

```python
# Async/Temporal (Format B, reusing previously reserved slots)
OPCODE_FORMAT[0xED] = Format.B  # SUSPEND
OPCODE_FORMAT[0xEE] = Format.B  # RESUME
OPCODE_FORMAT[0xEF] = Format.B  # CONTINUATION_ID
OPCODE_FORMAT[0xFA] = Format.B  # DEADLINE_BEFORE
OPCODE_FORMAT[0xFB] = Format.B  # YIELD_IF_CONTENTION
OPCODE_FORMAT[0xFC] = Format.B  # PERSIST_CRITICAL_STATE
OPCODE_FORMAT[0xFD] = Format.B  # TICKS_ELAPSED
```

### 8.3 Encoder Functions

```python
def encode_suspend(handle_reg: int) -> bytes:
    """SUSPEND: [0xED][handle_reg]"""
    return encode_format_b(0xED, handle_reg)

def encode_resume(handle_reg: int) -> bytes:
    """RESUME: [0xEE][handle_reg]"""
    return encode_format_b(0xEE, handle_reg)

def encode_continuation_id(dest_reg: int) -> bytes:
    """CONTINUATION_ID: [0xEF][dest_reg]"""
    return encode_format_b(0xEF, dest_reg)

def encode_deadline_before(ticks_reg: int) -> bytes:
    """DEADLINE_BEFORE: [0xFA][ticks_reg]"""
    return encode_format_b(0xFA, ticks_reg)

def encode_yield_if_contention(resource_reg: int) -> bytes:
    """YIELD_IF_CONTENTION: [0xFB][resource_reg]"""
    return encode_format_b(0xFB, resource_reg)

def encode_persist_critical_state(mask_reg: int) -> bytes:
    """PERSIST_CRITICAL_STATE: [0xFC][mask_reg]"""
    return encode_format_b(0xFC, mask_reg)

def encode_ticks_elapsed(dest_reg: int) -> bytes:
    """TICKS_ELAPSED: [0xFD][dest_reg]"""
    return encode_format_b(0xFD, dest_reg)
```

---

## 9. Conformance Test Vectors

### Vector 1: SUSPEND/RESUME Round-Trip — State Preservation

```python
{
    "name": "suspend_resume_roundtrip",
    "category": "async",
    "description": "SUSPEND saves state, RESUME restores it. R0 and R1 must be preserved.",
    "source": "; Set registers\nMOVI R0, 42\nMOVI R1, 99\n; Suspend\nSUSPEND R2\n; Modify state (these will be overwritten by RESUME)\nMOVI R0, 0\nMOVI R1, 0\n; Resume\nRESUME R2\nHALT",
    "bytecode": [
        0x18, 0x00, 42,     # MOVI R0, 42
        0x18, 0x01, 99,     # MOVI R1, 99
        0xED, 0x02,         # SUSPEND R2
        0x18, 0x00, 0,      # MOVI R0, 0
        0x18, 0x01, 0,      # MOVI R1, 0
        0xEE, 0x02,         # RESUME R2
        0x00                # HALT
    ],
    "expected": {"R0": 42, "R1": 99, "R2_neq": 0},
    "notes": "R2 contains the continuation handle (non-zero). R0 and R1 are restored to pre-suspend values."
}
```

### Vector 2: YIELD — Execution Continues

```python
{
    "name": "yield_continues",
    "category": "async",
    "description": "YIELD for 1 cycle, execution continues and R0 is incremented.",
    "source": "MOVI R0, 10\nYIELD 1\nINC R0\nHALT",
    "bytecode": [
        0x18, 0x00, 10,     # MOVI R0, 10
        0x15, 1,            # YIELD 1
        0x08, 0x00,         # INC R0
        0x00                # HALT
    ],
    "expected": {"R0": 11},
    "notes": "Existing opcode (0x15). Tests that YIELD doesn't corrupt state."
}
```

### Vector 3: DEADLINE_BEFORE — Execution Suspends at Deadline

```python
{
    "name": "deadline_suspends",
    "category": "temporal",
    "description": "Set a tight deadline (2 ticks). After deadline, fiber is auto-suspended.",
    "source": "MOVI R0, 0\nMOVI R1, 2\nDEADLINE_BEFORE R1\n.loop:\nINC R0\nJMP .loop\nHALT",
    "bytecode": [
        0x18, 0x00, 0,      # MOVI R0, 0
        0x18, 0x01, 2,      # MOVI R1, 2
        0xFA, 0x01,         # DEADLINE_BEFORE R1
        0x08, 0x00,         # INC R0
        0x43, 0x00, 0xFF, 0xF9,  # JMP -7 (back to INC R0)
        0x00                # HALT
    ],
    "expected": {"R0_lt": 100, "fiber_status": "SUSPENDED"},
    "notes": "R0 should be small (<100) because the deadline kicks in after 2 ticks. The fiber transitions to SUSPENDED."
}
```

### Vector 4: CONTINUATION_ID — Returns Valid ID

```python
{
    "name": "continuation_id_valid",
    "category": "async",
    "description": "CONTINUATION_ID returns a non-zero unique ID in the destination register.",
    "source": "CONTINUATION_ID R0\nHALT",
    "bytecode": [
        0xEF, 0x00,         # CONTINUATION_ID R0
        0x00                # HALT
    ],
    "expected": {"R0_neq": 0},
    "notes": "R0 must be non-zero. The ID is a hash of PC + registers + stack."
}
```

### Vector 5: CONTINUATION_ID — Deterministic for Same State

```python
{
    "name": "continuation_id_deterministic",
    "category": "async",
    "description": "Two CONTINUATION_ID calls with identical VM state return the same ID.",
    "source": "MOVI R0, 77\nCONTINUATION_ID R1\nCONTINUATION_ID R2\nHALT",
    "bytecode": [
        0x18, 0x00, 77,     # MOVI R0, 77
        0xEF, 0x01,         # CONTINUATION_ID R1
        0xEF, 0x02,         # CONTINUATION_ID R2
        0x00                # HALT
    ],
    "expected": {"R1_eq": "R2"},
    "notes": "R1 and R2 must be equal — same state produces same fingerprint."
}
```

### Vector 6: TICKS_ELAPSED — Monotonically Increasing

```python
{
    "name": "ticks_elapsed_increasing",
    "category": "temporal",
    "description": "TICKS_ELAPSED returns increasing values on successive calls.",
    "source": "TICKS_ELAPSED R0\nINC R1\nINC R1\nTICKS_ELAPSED R2\nHALT",
    "bytecode": [
        0xFD, 0x00,         # TICKS_ELAPSED R0
        0x08, 0x01,         # INC R1
        0x08, 0x01,         # INC R1
        0xFD, 0x02,         # TICKS_ELAPSED R2
        0x00                # HALT
    ],
    "expected": {"R2_gt": "R0"},
    "notes": "R2 > R0 because 2 instructions executed between calls."
}
```

### Vector 7: TICKS_ELAPSED — Non-Zero After Work

```python
{
    "name": "ticks_elapsed_nonzero",
    "category": "temporal",
    "description": "After some work, TICKS_ELAPSED returns a value > 0.",
    "source": "INC R0\nINC R0\nINC R0\nTICKS_ELAPSED R1\nHALT",
    "bytecode": [
        0x08, 0x00,         # INC R0
        0x08, 0x00,         # INC R0
        0x08, 0x00,         # INC R0
        0xFD, 0x01,         # TICKS_ELAPSED R1
        0x00                # HALT
    ],
    "expected": {"R0": 3, "R1_gt": 0},
    "notes": "R1 must be > 0 (at least 4 ticks: 3 INCs + TICKS_ELAPSED itself)."
}
```

### Vector 8: PERSIST_CRITICAL_STATE — Registers Survive

```python
{
    "name": "persist_critical_state_survives",
    "category": "temporal",
    "description": "PERSIST_CRITICAL_STATE saves R0. After simulated shutdown/restart, R0 is restored.",
    "source": "; Before shutdown\nMOVI R0, 55\nMOVI R1, 3\nPERSIST_CRITICAL_STATE R1\n; Simulate shutdown: reset registers\nRESET\n; Verify: if persistent storage works, R0 should still be 55\n; (depends on VM implementation auto-restoring persisted state)",
    "bytecode": [
        0x18, 0x00, 55,     # MOVI R0, 55
        0x18, 0x01, 3,      # MOVI R1, 3 (mask: R0 and R1)
        0xFC, 0x01,         # PERSIST_CRITICAL_STATE R1
        0x06,               # RESET
        0x00                # HALT
    ],
    "expected": {"R0": 55, "R1": 3},
    "notes": "After RESET, R0=55 and R1=3 if persistence works. If not, R0=0, R1=0. This tests the VM's restart restoration mechanism."
}
```

### Vector 9: SUSPEND/RESUME — Confidence Registers Preserved

```python
{
    "name": "suspend_resume_confidence_preserved",
    "category": "async",
    "description": "SUSPEND/RESUME preserves confidence registers alongside general registers.",
    "source": "MOVI R0, 10\n; Set confidence for R0 via C_BOOST (simplified: assume CR0=0.8 after setup)\nSUSPEND R1\n; After restore, CR0 should still be 0.8\nMOVI R0, 0\nRESUME R1\nHALT",
    "bytecode": [
        0x18, 0x00, 10,     # MOVI R0, 10
        # (confidence setup depends on runtime; assume CR0=0.8)
        0xED, 0x01,         # SUSPEND R1
        0x18, 0x00, 0,      # MOVI R0, 0 (will be overwritten)
        0xEE, 0x01,         # RESUME R1
        0x00                # HALT
    ],
    "expected": {"R0": 10, "CR0": 0.8},
    "notes": "Tests that confidence registers are included in the continuation snapshot."
}
```

### Vector 10: SUSPEND — Handle is Non-Zero

```python
{
    "name": "suspend_handle_nonzero",
    "category": "async",
    "description": "SUSPEND always returns a non-zero handle in the destination register.",
    "source": "SUSPEND R0\nHALT",
    "bytecode": [
        0xED, 0x00,         # SUSPEND R0
        0x00                # HALT
    ],
    "expected": {"R0_neq": 0},
    "notes": "The continuation handle must be a valid non-zero identifier."
}
```

### Vector 11: YIELD_IF_CONTENTION — No Contention (No-Op)

```python
{
    "name": "yield_if_contention_no_contention",
    "category": "temporal",
    "description": "YIELD_IF_CONTENTION with a free resource is a no-op. Execution continues normally.",
    "source": "MOVI R0, 0\nMOVI R1, 42\nYIELD_IF_CONTENTION R0\nINC R1\nHALT",
    "bytecode": [
        0x18, 0x00, 0,      # MOVI R0, 0 (resource 0x0000)
        0x18, 0x01, 42,     # MOVI R1, 42
        0xFB, 0x00,         # YIELD_IF_CONTENTION R0
        0x08, 0x01,         # INC R1
        0x00                # HALT
    ],
    "expected": {"R1": 43},
    "notes": "Resource 0x0000 is free, so YIELD_IF_CONTENTION is a no-op. R1 = 42 + 1 = 43."
}
```

### Vector 12: DEADLINE_BEFORE — Zero Clears Deadline

```python
{
    "name": "deadline_zero_clears",
    "category": "temporal",
    "description": "DEADLINE_BEFORE with 0 removes any active deadline.",
    "source": "MOVI R0, 100\nDEADLINE_BEFORE R0\n; Now clear it\nMOVI R0, 0\nDEADLINE_BEFORE R0\n; Run a long loop — should NOT suspend\nMOVI R1, 0\n.loop:\nINC R1\nCMP_LT R2, R1, 200\nJZ R2, .end\nMOVI R15, 0xFFFC\nJZ R1, .loop\n.end:\nHALT",
    "bytecode": [
        0x18, 0x00, 100,    # MOVI R0, 100
        0xFA, 0x00,         # DEADLINE_BEFORE R0
        0x18, 0x00, 0,      # MOVI R0, 0
        0xFA, 0x00,         # DEADLINE_BEFORE R0 (clear)
        0x18, 0x01, 0,      # MOVI R1, 0
        # .loop:
        0x08, 0x01,         # INC R1
        # CMP_LT R2, R1, 200
        0x18, 0x0F, 200,    # MOVI R15, 200
        0x2D, 0x02, 0x01, 0x0F,  # CMP_LT R2, R1, R15
        0x3C, 0x02, 0x0F,   # JZ R2, ...  (pseudo-expanded)
        # JMP .loop
        0x43, 0x00, 0xFF, 0xF2,  # JMP -14 (back to INC R1)
        # .end:
        0x00                # HALT
    ],
    "expected": {"R1": 200, "fiber_status": "COMPLETED"},
    "notes": "With deadline cleared, the loop runs to completion without suspension."
}
```

### Vector 13: Multiple SUSPEND — Different Handles

```python
{
    "name": "multiple_suspend_different_handles",
    "category": "async",
    "description": "Two SUSPEND calls produce different handles.",
    "source": "MOVI R0, 1\nSUSPEND R1\nMOVI R0, 2\nSUSPEND R2\nHALT",
    "bytecode": [
        0x18, 0x00, 1,      # MOVI R0, 1
        0xED, 0x01,         # SUSPEND R1
        0x18, 0x00, 2,      # MOVI R0, 2
        0xED, 0x02,         # SUSPEND R2
        0x00                # HALT
    ],
    "expected": {"R1_neq": 0, "R2_neq": 0, "R1_neq": "R2"},
    "notes": "Both handles must be non-zero and different from each other."
}
```

### Vector 14: RESUME Invalid Handle — Error Flag

```python
{
    "name": "resume_invalid_handle_error",
    "category": "async",
    "description": "RESUME with an invalid handle sets the error flag and continues.",
    "source": "MOVI R0, 99999\nMOVI R1, 42\nRESUME R0\nHALT",
    "bytecode": [
        0x18, 0x00, 0,      # MOVI R0, 0 (invalid handle)
        0x18, 0x01, 42,     # MOVI R1, 42
        0xEE, 0x00,         # RESUME R0 (invalid — handle 0)
        0x00                # HALT
    ],
    "expected": {"R1": 42, "error_flag": true},
    "notes": "R0=0 is an invalid handle. RESUME sets error flag but does not halt. R1 is unchanged."
}
```

### Vector 15: TICKS_ELAPSED — vs CLK Compatibility

```python
{
    "name": "ticks_elapsed_vs_clk",
    "category": "temporal",
    "description": "TICKS_ELAPSED and CLK return compatible values (CLK goes to R0 only).",
    "source": "TICKS_ELAPSED R0\nCLK\nHALT",
    "bytecode": [
        0xFD, 0x00,         # TICKS_ELAPSED R0
        0xF6,               # CLK (R0 = cycle count)
        0x00                # HALT
    ],
    "expected": {"R0_gte": 1},
    "notes": "After TICKS_ELAPSED (1 tick), CLK fires (1 more tick). R0 >= 2. Both should reflect the same counter."
}
```

---

## 10. Implementation Priority

### Phase 1: Core Async (Week 1–2)

| Priority | Task | Dependencies |
|----------|------|-------------|
| P0 | Add 7 opcodes to `isa_unified.py` | None |
| P0 | Update `decode_instruction` in `formats.py` | isa_unified.py |
| P0 | Implement SUSPEND/RESUME in `unified_interpreter.py` | formats.py |
| P1 | Implement CONTINUATION_ID | formats.py |
| P1 | Fiber data structure in VM | SUSPEND/RESUME |
| P1 | Conformance vectors 1, 4, 5, 10, 13, 14 | SUSPEND/RESUME |

### Phase 2: Temporal (Week 2–3)

| Priority | Task | Dependencies |
|----------|------|-------------|
| P0 | Implement TICKS_ELAPSED | None |
| P0 | Implement DEADLINE_BEFORE | TICKS_ELAPSED |
| P1 | Implement YIELD_IF_CONTENTION | Fiber scheduler |
| P1 | Implement PERSIST_CRITICAL_STATE | VM memory model |
| P1 | Conformance vectors 3, 6, 7, 8, 11, 12, 15 | Phase 2 opcodes |

### Phase 3: Fiber Scheduler (Week 3–4)

| Priority | Task | Dependencies |
|----------|------|-------------|
| P0 | Fiber table in VM memory | Fiber data structure |
| P0 | Round-robin scheduler | Fiber table |
| P1 | Priority boost for A2A | A2A message dispatch |
| P1 | Deadline integration with scheduler | DEADLINE_BEFORE |
| P2 | A2A continuation serialization | JSON schema |

### Phase 4: A2A Integration (Week 4–6)

| Priority | Task | Dependencies |
|----------|------|-------------|
| P0 | JSON continuation serialization | SUSPEND/RESUME |
| P0 | Cross-agent RESUME (receive continuation via TELL/ASK) | A2A transport |
| P1 | Compatibility checking | Serialization format |
| P1 | CRC32 checksum verification | Serialization format |
| P2 | Dirty-page memory tracking | VM memory model |

---

## Appendix A: Opcode Quick Reference

```
╔═══════════════════════════════════════════════════════════════════╗
║  ASYNC PRIMITIVES (ASYNC-001)                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  0xED  SUSPEND           B  [0xED][rd]   Save state → handle    ║
║  0xEE  RESUME            B  [0xEE][rd]   Restore state ← handle ║
║  0xEF  CONTINUATION_ID   B  [0xEF][rd]   State fingerprint → rd ║
║  0x15  YIELD             C  [0x15][imm8] Yield for imm8 cycles  ║
╠═══════════════════════════════════════════════════════════════════╣
║  TEMPORAL PRIMITIVES (TEMP-001)                                 ║
╠═══════════════════════════════════════════════════════════════════╣
║  0xFA  DEADLINE_BEFORE   B  [0xFA][rd]   Set tick deadline      ║
║  0xFB  YIELD_IF_CONTEND  B  [0xFB][rd]   Yield if contended     ║
║  0xFC  PERSIST_CRIT_ST   B  [0xFC][rd]   Persist regs by mask   ║
║  0xFD  TICKS_ELAPSED     B  [0xFD][rd]   Cycle count → rd       ║
╠═══════════════════════════════════════════════════════════════════╣
║  RELATED EXISTING OPCODES                                        ║
╠═══════════════════════════════════════════════════════════════════╣
║  0xE5  COYIELD           F  Coroutine yield (specific jump)      ║
║  0xE6  CORESUM           F  Coroutine resume (specific target)  ║
║  0xE4  SWITCH            F  Context switch                      ║
║  0xF6  CLK               A  Cycle count → R0 (legacy)           ║
║  0xF8  WDOG              A  Watchdog timer                      ║
║  0x14  SEMA              C  Semaphore operation                  ║
╚═══════════════════════════════════════════════════════════════════╝
```

## Appendix B: Fiber State Machine

```
CREATED → READY → RUNNING → (SUSPEND|BLOCKED|HALT)
                ↑           ↓
                └── READY ←─┘  (RESUME|resource freed|YIELD)
```

## Appendix C: Continuation Size Benchmarks

| Scenario | Registers | Stack | Memory | Estimated JSON Size |
|----------|-----------|-------|--------|--------------------|
| Minimal (no memory) | 16 | 0 | 0 | ~500 bytes |
| Typical (1 dirty page) | 16 | 5 | 256B | ~1 KB |
| Full snapshot (64KB) | 16 | 20 | 64KB | ~130 KB |
| A2A handoff (2 pages) | 16 | 3 | 512B | ~1.5 KB |

---

*End of specification. This document defines 7 new opcodes (SUSPEND, RESUME, CONTINUATION_ID, DEADLINE_BEFORE, YIELD_IF_CONTENTION, PERSIST_CRITICAL_STATE, TICKS_ELAPSED), 15 conformance test vectors, a complete fiber design, and a continuation serialization format for A2A state handoff.*
