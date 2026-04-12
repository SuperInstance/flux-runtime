# FLUX ISA v4 — Temporal Primitives Specification

**Task Board:** TEMP-001
**Author:** Super Z (Fleet Agent, Architect-rank)
**Date:** 2026-04-12
**Status:** DRAFT — Pending Review
**Depends On:** ISA v3 Unified (Format A–G encoding), Async Primitives (ASYNC-001)

---

## Table of Contents

1. [Overview and Motivation](#1-overview-and-motivation)
2. [Opcode Summary Table](#2-opcode-summary-table)
3. [Time Representation Format](#3-time-representation-format)
4. [Opcode Specifications](#4-opcode-specifications)
   - 4.1 CLOCK_GET
   - 4.2 DEADLINE_SET
   - 4.3 DEADLINE_CHECK
   - 4.4 YIELD_IF_CONTENTION
   - 4.5 PERSIST_CRITICAL_STATE
   - 4.6 RESTORE_CRITICAL_STATE
   - 4.7 TIME_BUDGET
   - 4.8 CLOCK_COMPARE
   - 4.9 DEADLINE_PROPAGATE
   - 4.10 TIMER_CREATE
   - 4.11 TIMER_CHECK
5. [Deadline Propagation Across CALL Boundaries](#5-deadline-propagation-across-call-boundaries)
6. [Persistence Format](#6-persistence-format)
7. [Interaction with Existing Opcodes](#7-interaction-with-existing-opcodes)
8. [Error Semantics](#8-error-semantics)
9. [Pseudocode: Execution Engine Integration](#9-pseudocode-execution-engine-integration)
10. [Bytecode Examples](#10-bytecode-examples)
11. [Migration Notes](#11-migration-notes)

---

## 1. Overview and Motivation

### 1.1 Problem Statement

FLUX agents operate in real-time environments — maritime navigation, sensor fusion, fleet coordination — where **temporal reasoning is not optional, it is correctness-critical**. The existing ISA has no primitives for:

- **Reading wall-clock time** with precision better than cycle count (CLK at 0xF6 returns cycles, not wall time)
- **Setting execution deadlines** that propagate through the call stack
- **Checking deadline compliance** before critical operations
- **Persisting critical state** atomically for crash recovery
- **Managing execution time budgets** with trap-on-exceed semantics
- **Contention-aware yielding** that backs off when contended resources are detected

Without temporal primitives, agents must implement ad-hoc timing loops using cycle counting, which is fragile (cycle rate varies across hardware), imprecise, and does not compose with coroutines or A2A protocol.

### 1.2 Design Principles

1. **Nanosecond precision, 64-bit range.** Time values are 64-bit unsigned integers representing nanoseconds since a configurable epoch.
2. **Deadline propagation is automatic.** When a deadline is set, it applies to all called functions unless explicitly overridden.
3. **Persistence is atomic.** `PERSIST_CRITICAL_STATE` writes state as an all-or-nothing operation using write-ahead logging.
4. **Contention detection is cooperative.** `YIELD_IF_CONTENTION` checks for lock contention or register hot spots and yields if detected.
5. **Time budgets compose with async primitives.** When combined with ASYNC-001, time budgets apply per-coroutine.

### 1.3 Relationship to Existing Opcodes

| Existing Opcode | Hex | Relationship |
|----------------|-----|-------------|
| `CLK` | 0xF6 | Returns cycle count. `CLOCK_GET` returns wall-clock nanoseconds. |
| `PCLK` | 0xF7 | Returns performance counter. Orthogonal to wall time. |
| `YIELD` | 0x15 | Yield for N cycles. `TIME_BUDGET` adds automatic yield-on-exceed. |
| `WDOG` | 0xF8 | Kick watchdog. `DEADLINE_CHECK` is a software analog. |
| `SYN` | 0x07 | Memory barrier. `YIELD_IF_CONTENTION` adds scheduling awareness. |
| `ENTER` / `LEAVE` | 0x25 / 0x26 | Stack frame management. Deadline propagation tracks frame depth. |
| `CALL` | 0x45 | Function call. Deadlines propagate through CALL. |
| `RET` | 0x02 | Function return. Deadline frame is popped. |

---

## 2. Opcode Summary Table

All temporal opcodes use the **EXTEND_TEMPORAL prefix** (0xFC, Format A). The actual opcode follows as the second byte:

```
  Byte 0: 0xFC (EXTEND_TEMPORAL)
  Byte 1: sub-opcode (see table below)
  Bytes 2+: operands per sub-format
```

| Sub-Opcode | Mnemonic | Sub-Format | Operands | Size (bytes) | Description |
|-----------|----------|-----------|----------|:------------:|-------------|
| 0x01 | `CLOCK_GET` | B | rd | 3 | Read wall-clock nanoseconds → R[rd]:R[rd+1] |
| 0x02 | `DEADLINE_SET` | D | rd, imm8_lo, imm8_hi | 4 | Set deadline: now + (imm16 * quantum) |
| 0x03 | `DEADLINE_CHECK` | B | rd | 3 | Check if deadline passed → flag + remaining time in rd |
| 0x04 | `YIELD_IF_CONTENTION` | C | rd, imm8 | 3 | Yield if resource rd is contended (threshold imm8) |
| 0x05 | `PERSIST_CRITICAL_STATE` | C | rd, imm8 | 3 | Persist registers [rd..rd+imm8] to storage |
| 0x06 | `RESTORE_CRITICAL_STATE` | C | rd, imm8 | 3 | Restore registers [rd..rd+imm8] from storage |
| 0x07 | `TIME_BUDGET` | D | rd, imm8_lo, imm8_hi | 4 | Set time budget, trap on exceed (imm16 = microseconds) |
| 0x08 | `CLOCK_COMPARE` | E | rd, rs1, rs2 | 5 | Compare two time values, result → rd (-1/0/1) |
| 0x09 | `DEADLINE_PROPAGATE` | B | rd | 3 | Push current deadline frame, set new child deadline from rd |
| 0x0A | `TIMER_CREATE` | C | rd, imm8 | 3 | Create one-shot timer with delay (R[rd] = delay in μs), handle → rd |
| 0x0B | `TIMER_CHECK` | B | rd | 3 | Check if timer (handle in rd) has fired → R[rd] = 1/0 |

### Total: 11 opcodes, consuming sub-opcode range 0x01–0x0B

---

## 3. Time Representation Format

### 3.1 Internal Time Representation

All temporal values in the FLUX VM are represented as **64-bit unsigned nanosecond timestamps**:

```
64-bit nanosecond value, stored in two consecutive GP registers:

  R[rd]   = low  32 bits (nanoseconds & 0xFFFFFFFF)
  R[rd+1] = high 32 bits (nanoseconds >> 32)

Range: 0 to 18,446,744,073,709.551615 seconds
       ≈ 584,942 years
```

### 3.2 Epoch Reference

The nanosecond counter starts from one of three configurable epochs:

| Epoch Code | Name | Reference | Use Case |
|-----------|------|-----------|----------|
| 0 | `EPOCH_BOOT` | VM boot time (default) | Relative timing, deadlines |
| 1 | `EPOCH_UNIX` | 1970-01-01T00:00:00Z | Interoperability with host systems |
| 2 | `EPOCH_GPS` | 1980-01-06T00:00:00Z | Maritime / GPS-equipped agents |
| 3 | `EPOCH_CUSTOM` | Set via SYS call | Domain-specific epochs |

The epoch is configured at VM creation time and cannot be changed at runtime. All CLOCK_GET and DEADLINE_SET operations reference the same epoch.

### 3.3 Time Quantum

`DEADLINE_SET` uses a 16-bit multiplier against a configurable **time quantum**:

```
deadline_ns = current_time_ns + (imm16 * quantum_ns)

Default quantum: 1 microsecond (1000 ns)
Configurable via: SYS 0x40 (SYS_SET_TIME_QUANTUM, argument in ns)
```

This allows:
- `DEADLINE_SET R0, 0, 100` → deadline in 100 μs from now
- `DEADLINE_SET R0, 0, 1` → deadline in 1 μs from now (minimum practical)
- `DEADLINE_SET R0, 0, 0` → deadline = now (immediate, useful for DEADLINE_CHECK)

### 3.4 Binary Encoding of 64-bit Time in Registers

```
Example: time_ns = 1,500,000,000,000 (25 minutes)

  R[rd]   = 1,500,000,000,000 & 0xFFFFFFFF = 0x15D1B7175 → low 32 bits
  R[rd+1] = 1,500,000,000,000 >> 32        = 0x0000015E → high 32 bits

Reading time:
  time_ns = (R[rd+1] << 32) | R[rd]
```

### 3.5 Special Time Constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `TIME_ZERO` | 0x0000000000000000 | No time / disabled |
| `TIME_INFINITE` | 0xFFFFFFFFFFFFFFFF | Never expires |
| `TIME_IMMEDIATE` | Current time | Deadline is now (already expired) |
| `TIME_MIN_DEADLINE` | 1 μs | Minimum practical deadline |

---

## 4. Opcode Specifications

### 4.1 CLOCK_GET — Read Wall-Clock Time

| Field | Value |
|-------|-------|
| **Mnemonic** | `CLOCK_GET` |
| **Sub-opcode** | 0x01 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFC][0x01][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/read |
| **Side Effects** | None (read-only) |

#### Semantics

1. Read the current wall-clock time in nanoseconds from the VM's time source.
2. Write the low 32 bits to `R[rd]`.
3. Write the high 32 bits to `R[rd+1]` (if rd+1 < 16).
4. The time source is provided by the host environment. If no host clock is available, the VM falls back to cycle-count * estimated_ns_per_cycle.

#### Binary Encoding Diagram

```
Byte 0: [0xFC]           ← EXTEND_TEMPORAL prefix
Byte 1: [0x01]           ← CLOCK_GET sub-opcode
Byte 2: [rd:u8]          ← destination register (0x00–0x0E, must have rd+1 < 16)

Result:
  R[rd]   = clock_ns & 0xFFFFFFFF   (low 32 bits)
  R[rd+1] = (clock_ns >> 32) & 0xFFFFFFFF  (high 32 bits)
```

#### Pseudocode

```python
def execute_CLOCK_GET(rd: int) -> None:
    if rd + 1 >= 16:
        raise VMError("CLOCK_GET: need register pair, rd+1 >= 16")

    now_ns = host_clock.nanoseconds()  # or fallback to cycles * ns_per_cycle

    regs.write_gp(rd, now_ns & 0xFFFFFFFF)
    regs.write_gp(rd + 1, (now_ns >> 32) & 0xFFFFFFFF)
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_REGISTER_PAIR` | rd+1 >= 16 | FAULT trap with code 0x01 |
| `ERR_CLOCK_UNAVAILABLE` | No host clock and no cycle estimate | FAULT trap with code 0x02 |

---

### 4.2 DEADLINE_SET — Set Execution Deadline

| Field | Value |
|-------|-------|
| **Mnemonic** | `DEADLINE_SET` |
| **Sub-opcode** | 0x02 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFC][0x02][rd:u8][imm8_lo:u8][imm8_hi:u8]` |
| **Size** | 4 bytes |
| **Category** | temporal/deadline |
| **Side Effects** | Sets deadline for current coroutine/frame |

#### Semantics

1. Compute the 16-bit multiplier: `multiplier = (imm8_hi << 8) | imm8_lo`.
2. Compute the deadline: `deadline_ns = CLOCK_GET() + (multiplier * quantum_ns)`.
3. Write the deadline to `R[rd]:R[rd+1]` (for inspection by user code).
4. Push the current deadline frame onto the deadline stack.
5. Set the new deadline as the active deadline for the current coroutine.
6. If `multiplier == 0`, the deadline is set to the current time (immediately expired). This is useful for testing deadline-check paths.

#### Deadline Stack Model

```
Deadline Stack (per coroutine, max depth 256):

  Before CALL to foo():
  ┌───────────────────────┐
  │ Frame 0: deadline_0   │  ← set at coroutine start
  │         (e.g., 1s)     │
  └───────────────────────┘

  After DEADLINE_SET inside foo():
  ┌───────────────────────┐
  │ Frame 0: deadline_0   │  ← inherited
  │ Frame 1: deadline_1   │  ← set by foo(), tighter (e.g., 100ms)
  └───────────────────────┘

  Active deadline = Frame 1 (tightest/most recent)
```

#### Binary Encoding Diagram

```
Byte 0: [0xFC]           ← EXTEND_TEMPORAL prefix
Byte 1: [0x02]           ← DEADLINE_SET sub-opcode
Byte 2: [rd:u8]          ← destination for deadline value
Byte 3: [imm8_lo:u8]     ← multiplier low byte
Byte 4: [imm8_hi:u8]     ← multiplier high byte

Multiplier = (imm8_hi << 8) | imm8_lo   → 0..65535
Deadline = now_ns + multiplier * quantum_ns
```

#### Pseudocode

```python
def execute_DEADLINE_SET(rd: int, imm8_lo: int, imm8_hi: int) -> None:
    multiplier = (imm8_hi << 8) | imm8_lo
    now_ns = host_clock.nanoseconds()
    deadline_ns = now_ns + (multiplier * vm.time_quantum_ns)

    # Clamp to TIME_INFINITE if overflow
    if deadline_ns < now_ns and multiplier > 0:
        deadline_ns = TIME_INFINITE

    # Save to register pair
    regs.write_gp(rd, deadline_ns & 0xFFFFFFFF)
    if rd + 1 < 16:
        regs.write_gp(rd + 1, (deadline_ns >> 32) & 0xFFFFFFFF)

    # Push deadline frame
    current = current_coroutine()
    current.deadline_stack.append(deadline_ns)

    if len(current.deadline_stack) > 256:
        raise VMError("DEADLINE_SET: stack overflow (max 256 frames)")
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_DEADLINE_STACK_OVERFLOW` | >256 nested deadline frames | FAULT trap with code 0x03 |
| `ERR_QUANTUM_NOT_SET` | Time quantum is 0 (not configured) | FAULT trap with code 0x04 |

---

### 4.3 DEADLINE_CHECK — Check Deadline Compliance

| Field | Value |
|-------|-------|
| **Mnemonic** | `DEADLINE_CHECK` |
| **Sub-opcode** | 0x03 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFC][0x03][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/deadline |
| **Side Effects** | Sets condition flags, writes remaining time |

#### Semantics

1. Read the current wall-clock time.
2. Compare against the active deadline (top of deadline stack).
3. If `current_time >= deadline`:
   - Set `flag_zero = True` (deadline has passed).
   - Set `flag_sign = True` (indicating over-budget).
   - Write 0 to `R[rd]:R[rd+1]` (no time remaining).
4. If `current_time < deadline`:
   - Set `flag_zero = False`.
   - Set `flag_sign = False`.
   - Write remaining time to `R[rd]:R[rd+1]` (remaining = deadline - current_time).
5. If no deadline is active (stack is empty):
   - Set `flag_zero = True` (no deadline = "passed" by convention).
   - Write `TIME_INFINITE` to `R[rd]:R[rd+1]`.

#### Pseudocode

```python
def execute_DEADLINE_CHECK(rd: int) -> None:
    current = current_coroutine()

    if not current.deadline_stack:
        # No deadline active
        vm._flag_zero = True
        vm._flag_sign = True
        regs.write_gp(rd, 0xFFFFFFFF)
        if rd + 1 < 16:
            regs.write_gp(rd + 1, 0xFFFFFFFF)
        return

    active_deadline = current.deadline_stack[-1]
    now_ns = host_clock.nanoseconds()

    if now_ns >= active_deadline:
        # Deadline exceeded
        vm._flag_zero = True
        vm._flag_sign = True
        regs.write_gp(rd, 0)
        if rd + 1 < 16:
            regs.write_gp(rd + 1, 0)
    else:
        # Time remaining
        remaining = active_deadline - now_ns
        vm._flag_zero = False
        vm._flag_sign = False
        regs.write_gp(rd, remaining & 0xFFFFFFFF)
        if rd + 1 < 16:
            regs.write_gp(rd + 1, (remaining >> 32) & 0xFFFFFFFF)
```

#### Usage Pattern: Guard Critical Section

```
DEADLINE_SET R0, 100, 0    ; 100μs deadline
; --- critical section ---
DEADLINE_CHECK R1           ; check: flag_zero = exceeded?
JZ    R1, DEADLINE_OK       ; R1 != 0 means time remaining
; Deadline exceeded — abort critical section
JMP   TIMEOUT_HANDLER
DEADLINE_OK:
; Continue with remaining time
```

---

### 4.4 YIELD_IF_CONTENTION — Contention-Aware Yield

| Field | Value |
|-------|-------|
| **Mnemonic** | `YIELD_IF_CONTENTION` |
| **Sub-opcode** | 0x04 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFC][0x04][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/contention |
| **Side Effects** | May yield coroutine |

#### Semantics

1. `R[rd]` holds a **resource identifier** (memory address, channel handle, or register number).
2. `imm8` is a **contention threshold**: if N other coroutines are waiting on or accessing this resource, yield.
3. Check the VM's internal contention table for the resource.
4. If contention count >= threshold:
   - Execute `YIELD_ASYNC` (cooperative yield to scheduler).
   - Write the contention count to `R[rd]`.
   - Set `flag_zero = False` (yield occurred).
5. If contention count < threshold:
   - Continue execution.
   - Write the contention count to `R[rd]`.
   - Set `flag_zero = True` (no yield).

#### Contention Detection Sources

| Resource Type | Detection Method |
|---------------|-----------------|
| Memory address | Check if address is in any other coroutine's recent write set |
| Channel handle | Check channel waiters count |
| Register number | Check if register is hot (frequently written by other coroutines on shared heap) |
| Lock/semaphore | Check semaphore wait queue depth |

#### Binary Encoding Diagram

```
Byte 0: [0xFC]           ← EXTEND_TEMPORAL prefix
Byte 1: [0x04]           ← YIELD_IF_CONTENTION sub-opcode
Byte 2: [rd:u8]          ← resource identifier register
Byte 3: [imm8:u8]        ← contention threshold (0 = always yield, 255 = never yield)
```

#### Pseudocode

```python
def execute_YIELD_IF_CONTENTION(rd: int, threshold: int) -> None:
    resource_id = regs.read_gp(rd)
    contention_count = vm.contention_table.get(resource_id, 0)

    if contention_count >= threshold:
        # Yield
        execute_YIELD_ASYNC()
        regs.write_gp(rd, contention_count)
        vm._flag_zero = False
    else:
        # No yield
        regs.write_gp(rd, contention_count)
        vm._flag_zero = True
```

---

### 4.5 PERSIST_CRITICAL_STATE — Atomic State Persistence

| Field | Value |
|-------|-------|
| **Mnemonic** | `PERSIST_CRITICAL_STATE` |
| **Sub-opcode** | 0x05 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFC][0x05][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/persistence |
| **Side Effects** | Writes to persistent storage (WAL) |

#### Semantics

1. `rd` specifies the first register to persist.
2. `imm8` specifies the number of consecutive registers to persist.
3. The registers `[rd, rd+1, ..., rd+imm8-1]` are serialized atomically to a write-ahead log (WAL) in persistent storage.
4. The persistence is **atomic**: either all registers are written, or none are (crash safety).
5. On completion, `R[rd]` contains a **persistence sequence number** (monotonically increasing 32-bit integer).
6. If `rd+imm8-1 >= 16`, only registers up to R15 are persisted.

#### What Gets Saved

For each register in the range:
```
{
  "register_index": rd + i,
  "gp_value": R[rd+i],
  "confidence_value": C[rd+i],  // parallel confidence register
  "timestamp_ns": current_wall_clock,
  "coroutine_id": current_coroutine_id,
  "sequence_number": next_seq++,
  "checksum": crc32(register_data)
}
```

#### WAL Persistence Format

```
WAL Entry (fixed 32 bytes per register):

Offset  Size  Field
0x00    4     Magic: 0x50455253 ("PERS")
0x04    4     Sequence number (u32, big-endian)
0x08    8     Timestamp (nanoseconds, big-endian)
0x10    1     Register index (u8)
0x11    1     Coroutine ID (u8)
0x12    4     GP register value (i32)
0x16    2     Confidence value (u16, fixed-point 8.8)
0x18    4     CRC32 checksum (of bytes 0x04..0x17)
0x1C    4     Reserved (zero)

Total: 32 bytes per register entry
```

#### Pseudocode

```python
def execute_PERSIST_CRITICAL_STATE(rd: int, count: int) -> None:
    current = current_coroutine()
    now_ns = host_clock.nanoseconds()
    seq = vm.persistence_sequence

    entries = []
    for i in range(count):
        reg_idx = rd + i
        if reg_idx >= 16:
            break

        entry = WalEntry(
            magic=0x50455253,
            sequence=seq + i,
            timestamp=now_ns,
            register_index=reg_idx,
            coroutine_id=current.id,
            gp_value=regs.read_gp(reg_idx),
            confidence=confidence_regs[reg_idx],
        )
        entry.checksum = crc32(entry.to_bytes()[:-4])  # CRC of everything except CRC
        entries.append(entry)

    # Atomic write: write all entries, then sync
    persist_storage.write_entries(entries)
    persist_storage.fsync()  # ensure durability

    vm.persistence_sequence = seq + len(entries)
    regs.write_gp(rd, vm.persistence_sequence & 0xFFFFFFFF)
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_PERSIST_STORAGE_FULL` | WAL exceeds capacity | FAULT trap with code 0x05 |
| `ERR_PERSIST_IO_ERROR` | Storage device failure | FAULT trap with code 0x06 |
| `ERR_PERSIST_INVALID_RANGE` | rd >= 16 or count == 0 | FAULT trap with code 0x07 |

---

### 4.6 RESTORE_CRITICAL_STATE — Restore from Persistence

| Field | Value |
|-------|-------|
| **Mnemonic** | `RESTORE_CRITICAL_STATE` |
| **Sub-opcode** | 0x06 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFC][0x06][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/persistence |
| **Side Effects** | Overwrites registers from persisted data |

#### Semantics

1. `rd` specifies the first register to restore.
2. `imm8` specifies the number of consecutive registers to restore.
3. Read the most recent WAL entries for registers `[rd, rd+1, ..., rd+imm8-1]`.
4. Validate each entry's CRC32 checksum.
5. If all checksums pass, overwrite the registers with persisted values.
6. Write the sequence number of the restored state to `R[rd]`.
7. If any checksum fails, do not modify any registers. Set `flag_sign = True` (error).

#### Pseudocode

```python
def execute_RESTORE_CRITICAL_STATE(rd: int, count: int) -> None:
    entries = persist_storage.read_latest(rd, count)

    if entries is None or len(entries) < count:
        vm._flag_sign = True
        regs.write_gp(rd, 0)  # failure
        return

    # Validate all CRCs first
    for entry in entries:
        expected_crc = crc32(entry.to_bytes()[:-4])
        if entry.checksum != expected_crc:
            vm._flag_sign = True
            regs.write_gp(rd, 0)  # failure
            return

    # All valid — apply
    for entry in entries:
        regs.write_gp(entry.register_index, entry.gp_value)
        confidence_regs[entry.register_index] = entry.confidence

    vm._flag_sign = False
    regs.write_gp(rd, entries[0].sequence)
```

---

### 4.7 TIME_BUDGET — Set Execution Time Budget

| Field | Value |
|-------|-------|
| **Mnemonic** | `TIME_BUDGET` |
| **Sub-opcode** | 0x07 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFC][0x07][rd:u8][imm8_lo:u8][imm8_hi:u8]` |
| **Size** | 4 bytes |
| **Category** | temporal/budget |
| **Side Effects** | Installs time-budget trap handler |

#### Semantics

1. The 16-bit value `(imm8_hi << 8) | imm8_lo` specifies the **time budget in microseconds**.
2. A timer is started for the current coroutine.
3. If the budget expires before the coroutine yields/suspends/completes:
   - A `FAULT` (0xE7) is raised with fault code `0x20` (TIME_BUDGET_EXCEEDED).
   - The fault handler receives the remaining over-budget time in `R[rd]:R[rd+1]` as a negative value.
4. If the coroutine completes or yields before the budget expires:
   - The timer is cancelled.
   - The remaining budget is written to `R[rd]:R[rd+1]`.
5. If `imm16 == 0`, the budget is disabled (no trap).
6. If `imm16 == 0xFFFF`, the budget is set to TIME_INFINITE (effectively disabled).

#### Binary Encoding Diagram

```
Byte 0: [0xFC]           ← EXTEND_TEMPORAL prefix
Byte 1: [0x07]           ← TIME_BUDGET sub-opcode
Byte 2: [rd:u8]          ← register for remaining budget
Byte 3: [imm8_lo:u8]     ← budget low byte (μs)
Byte 4: [imm8_hi:u8]     ← budget high byte (μs)

Budget range: 0..65,535 μs (0..65.535 ms)
  0x0000 = disabled
  0xFFFF = infinite
```

#### Interaction with DEADLINE_SET

`TIME_BUDGET` and `DEADLINE_SET` are **orthogonal**:

| Feature | TIME_BUDGET | DEADLINE_SET |
|---------|-------------|--------------|
| Trigger | FAULT trap | flag check |
| Scope | Per coroutine | Per frame (stacked) |
| Precision | Microsecond | Nanosecond (with quantum) |
| Nesting | Single active budget | Stack of deadlines |
| Recovery | Fault handler | User code branch |

Both can be active simultaneously. If the time budget fires first, the FAULT handler can check the deadline and decide whether to extend or abort.

#### Pseudocode

```python
def execute_TIME_BUDGET(rd: int, imm8_lo: int, imm8_hi: int) -> None:
    budget_us = (imm8_hi << 8) | imm8_lo
    current = current_coroutine()

    if budget_us == 0 or budget_us == 0xFFFF:
        current.time_budget = None  # disable
        return

    budget_ns = budget_us * 1000
    current.time_budget_deadline = host_clock.nanoseconds() + budget_ns
    current.time_budget_rd = rd

    # Register with scheduler for budget checking
    scheduler.register_budget_check(current.id)
```

---

### 4.8 CLOCK_COMPARE — Compare Two Time Values

| Field | Value |
|-------|-------|
| **Mnemonic** | `CLOCK_COMPARE` |
| **Sub-opcode** | 0x08 |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFC][0x08][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | temporal/compare |
| **Side Effects** | None |

#### Semantics

1. Read time A from `R[rs1]:R[rs1+1]`.
2. Read time B from `R[rs2]:R[rs2+1]`.
3. Compare: `R[rd] = -1` if A < B, `0` if A == B, `1` if A > B.
4. Set condition flags: `flag_zero = (A == B)`, `flag_sign = (A < B)`.

---

### 4.9 DEADLINE_PROPAGATE — Push Deadline Frame

| Field | Value |
|-------|-------|
| **Mnemonic** | `DEADLINE_PROPAGATE` |
| **Sub-opcode** | 0x09 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFC][0x09][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/deadline |
| **Side Effects** | Modifies deadline stack |

#### Semantics

1. Push the current active deadline onto the deadline stack (save).
2. Read a new deadline value from `R[rd]:R[rd+1]`.
3. Set the new deadline as the active deadline.
4. This is an explicit version of what DEADLINE_SET does automatically.

---

### 4.10 TIMER_CREATE — Create One-Shot Timer

| Field | Value |
|-------|-------|
| **Mnemonic** | `TIMER_CREATE` |
| **Sub-opcode** | 0x0A |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFC][0x0A][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/timer |
| **Side Effects** | Allocates timer resource |

#### Semantics

1. `R[rd]` contains the timer delay in microseconds.
2. `imm8` is the timer type: 0 = one-shot, 1 = repeating.
3. A timer is created with the specified delay.
4. A timer handle is written to `R[rd]` (replacing the delay value).
5. When the timer fires, it generates an `EVT_TIMER` event (event type 0x06 in the async event system).

---

### 4.11 TIMER_CHECK — Check Timer Status

| Field | Value |
|-------|-------|
| **Mnemonic** | `TIMER_CHECK` |
| **Sub-opcode** | 0x0B |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFC][0x0B][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | temporal/timer |
| **Side Effects** | None (read-only) |

#### Semantics

1. Read timer handle from `R[rd]`.
2. Check if the timer has fired.
3. Write result to `R[rd]`: 1 = fired, 0 = not yet fired, -1 = invalid handle.

---

## 5. Deadline Propagation Across CALL Boundaries

### 5.1 Automatic Propagation Rules

When `CALL` (0x45) executes, the current deadline frame is implicitly propagated:

```
Before CALL foo():
  Deadline stack: [deadline_main (1s), deadline_section (100ms)]
  Active: 100ms

After CALL foo() enters:
  Deadline stack: [deadline_main (1s), deadline_section (100ms)]
  Active: 100ms (unchanged — foo inherits the tightest deadline)
```

### 5.2 Manual Override Inside Called Function

```
foo():
  ; foo() inherits 100ms deadline from caller
  ; foo() knows it needs at most 50ms, so it narrows:
  DEADLINE_SET R0, 50, 0    ; new deadline: now + 50μs
  ; Deadline stack: [1s, 100ms, 50μs]
  ; Active: 50μs

  ; ... do work ...

  DEADLINE_CHECK R1
  ; After RET, the 50μs frame is popped:
  ; Deadline stack: [1s, 100ms]
  ; Active: 100ms (restored)
```

### 5.3 Frame Pop on RET

When `RET` (0x02) executes:
1. Pop the most recent deadline frame (if it was pushed by `DEADLINE_SET` inside the function).
2. The previous deadline becomes active again.
3. This ensures deadlines don't leak across function boundaries.

### 5.4 Pseudocode: CALL/RET Integration

```python
# In CALL handler:
def _exec_CALL(self, offset: int) -> None:
    current = current_coroutine()
    # Push return address and frame pointer (existing logic)
    self._stack_push(self.pc)
    # Note: deadline frame is NOT pushed here. DEADLINE_SET pushes explicitly.
    # The called function inherits the current active deadline.
    self.pc += offset

# In RET handler:
def _exec_RET(self) -> None:
    current = current_coroutine()
    # Pop deadline frames pushed inside the returning function
    while current.deadline_stack and current.deadline_stack[-1].auto_pop:
        current.deadline_stack.pop()
    # Restore PC
    addr = self._stack_pop()
    self.pc = addr
```

---

## 6. Persistence Format

### 6.1 Write-Ahead Log (WAL) Structure

```
Persistent Storage Layout:

  Offset 0x0000:  WAL Header (64 bytes)
    0x00: Magic "FLXP" (4 bytes)
    0x04: Version (u16)
    0x06: Epoch type (u8)
    0x07: Reserved (u8)
    0x08: Head sequence number (u32)
    0x0C: Tail sequence number (u32)
    0x10: Total entries (u32)
    0x14: Checksum of header (CRC32)
    0x18: Reserved (48 bytes)

  Offset 0x0040:  WAL Entries (32 bytes each, contiguous)
    Entry 0: sequence=head, 32 bytes
    Entry 1: sequence=head+1, 32 bytes
    ...

  Offset 0x0000 + 64 + N*32:  Free space

  Max WAL size: configurable (default 1 MB = 32,768 entries)
```

### 6.2 WAL Entry Detail

```
WAL Entry (32 bytes):

  Byte  Offset  Field               Encoding
  ────  ──────  ──────────────────  ────────────────
  0-3   0x00    Magic               u32 BE = 0x50455253
  4-7   0x04    Sequence number     u32 BE
  8-15  0x08    Timestamp           u64 BE (nanoseconds)
  16    0x10    Register index      u8
  17    0x11    Coroutine ID        u8
  18-21 0x12    GP value            i32 BE
  22-23 0x16    Confidence value    u16 BE (fixed-point 8.8)
  24-27 0x18    CRC32 checksum      u32 BE
  28-31 0x1C    Reserved            u32 = 0x00000000
```

### 6.3 Atomicity Guarantees

1. **Single-entry atomicity**: Each 32-byte entry is written with a single `fsync()`.
2. **Multi-register atomicity**: `PERSIST_CRITICAL_STATE` with count > 1 writes all entries sequentially with a final `fsync()` after the last entry. If the system crashes mid-write:
   - Entries with valid CRC are recoverable.
   - Entries with invalid CRC are discarded.
   - The sequence number gap indicates missing entries.
3. **Crash recovery**: On restart, the VM scans the WAL from head to tail, validating CRCs. The last valid sequence number becomes the recovery point.

### 6.4 Persistence Performance

| Operation | Latency (typical) | Throughput |
|-----------|------------------|------------|
| Single register persist | ~10 μs (SSD + fsync) | ~100K ops/sec |
| 16 registers persist | ~50 μs (batched fsync) | ~20K ops/sec |
| Restore 16 registers | ~5 μs (read + CRC check) | ~200K ops/sec |
| WAL scan (crash recovery) | ~1 ms per 1K entries | — |

---

## 7. Interaction with Existing Opcodes

### 7.1 CLOCK_GET vs CLK

| Feature | CLK (0xF6) | CLOCK_GET (0xFC 0x01) |
|---------|-----------|----------------------|
| Granularity | Cycles | Nanoseconds |
| Precision | Variable (depends on clock rate) | Nanosecond |
| Format | Single register (32-bit cycles) | Register pair (64-bit ns) |
| Monotonic | Yes (cycle count always increases) | Yes (if host clock is monotonic) |
| Persistence | Lost on VM restart | Survives VM restart (depends on epoch) |

### 7.2 DEADLINE_CHECK vs WDOG

| Feature | WDOG (0xF8) | DEADLINE_CHECK |
|---------|-------------|----------------|
| Mechanism | Hardware watchdog timer | Software time comparison |
| Trigger | Automatic reset on timeout | Manual check (must be polled) |
| Flexibility | Fixed timeout | Per-frame, configurable |
| Recovery | System reset | User-defined handler |
| Composition | Single global timer | Stacked per function |

### 7.3 TIME_BUDGET vs max_cycles

| Feature | max_cycles (constructor) | TIME_BUDGET (0xFC 0x07) |
|---------|-------------------------|------------------------|
| Scope | Entire VM execution | Per coroutine |
| Unit | Cycles | Microseconds |
| Trigger | VM stops | FAULT trap (recoverable) |
| Dynamic | No (fixed at construction) | Yes (can be changed at runtime) |

### 7.4 YIELD_IF_CONTENTION vs SYN (0x07)

| Feature | SYN (memory fence) | YIELD_IF_CONTENTION |
|---------|-------------------|---------------------|
| Purpose | Memory ordering | Scheduling contention avoidance |
| Blocking | No (hardware fence) | Conditional (may yield) |
| Information | None | Returns contention count |
| Scope | Current core/thread | Current coroutine |

---

## 8. Error Semantics

### 8.1 Error Classification

| Error Code | Name | Severity | Recovery |
|-----------|------|----------|----------|
| 0x01 | `ERR_REGISTER_PAIR` | Fatal | Fix rd to be < 15 |
| 0x02 | `ERR_CLOCK_UNAVAILABLE` | Fatal | Configure host clock |
| 0x03 | `ERR_DEADLINE_STACK_OVERFLOW` | Fatal | Reduce nesting depth |
| 0x04 | `ERR_QUANTUM_NOT_SET` | Fatal | Call SYS 0x40 to set quantum |
| 0x05 | `ERR_PERSIST_STORAGE_FULL` | Recoverable | Compact WAL or increase capacity |
| 0x06 | `ERR_PERSIST_IO_ERROR` | Recoverable | Retry after storage recovery |
| 0x07 | `ERR_PERSIST_INVALID_RANGE` | Fatal | Fix rd/count values |
| 0x08 | `ERR_RESTORE_CRC_FAILED` | Recoverable | WAL may be corrupted, use older entries |
| 0x09 | `ERR_RESTORE_NO_DATA` | Recoverable | No persisted data for these registers |
| 0x0A | `ERR_TIMER_INVALID` | Fatal | Timer handle corrupted |
| 0x0B | `ERR_TIMER_TABLE_FULL` | Fatal | Max timers exceeded |
| 0x20 | `TIME_BUDGET_EXCEEDED` | Recoverable | Caught by FAULT handler |

### 8.2 Deadline Interaction with Async Primitives

When temporal primitives are combined with async primitives (ASYNC-001):

1. **SUSPEND preserves deadlines.** When a coroutine suspends, its deadline stack is saved as part of the continuation state. The deadline continues ticking while suspended.
2. **RESUME checks deadlines.** When a coroutine is resumed, `DEADLINE_CHECK` is implicitly called. If the deadline has passed while the coroutine was suspended, a FAULT is raised immediately.
3. **TIME_BUDGET is per-coroutine.** Each coroutine has its own time budget. When a coroutine yields or suspends, its budget timer is paused.
4. **YIELD_IF_CONTENTION uses async scheduling.** The yield uses the async scheduler from ASYNC-001.

---

## 9. Pseudocode: Execution Engine Integration

### 9.1 Time-Enhanced Interpreter

```python
class TemporalInterpreter(AsyncInterpreter):
    """Extended interpreter with temporal support."""

    DEFAULT_TIME_QUANTUM_NS = 1000  # 1 microsecond
    MAX_DEADLINE_DEPTH = 256
    MAX_TIMERS = 256

    def __init__(self, bytecode: bytes, epoch: int = 0, **kwargs):
        super().__init__(bytecode, **kwargs)
        self._time_quantum_ns = self.DEFAULT_TIME_QUANTUM_NS
        self._epoch = epoch
        self._persistence_sequence = 0
        self._persistence_storage = WalStorage()
        self._timers: dict[int, Timer] = {}
        self._timer_counter = 0

    def _dispatch_temporal(self, sub_opcode: int) -> None:
        """Handle EXTEND_TEMPORAL (0xFC) prefix."""
        if sub_opcode == 0x01:
            (rd,) = self._decode_operands_B()
            self._exec_clock_get(rd)
        elif sub_opcode == 0x02:
            rd, imm_lo, imm_hi = self._decode_ext_format_d()
            self._exec_deadline_set(rd, (imm_hi << 8) | imm_lo)
        elif sub_opcode == 0x03:
            (rd,) = self._decode_operands_B()
            self._exec_deadline_check(rd)
        elif sub_opcode == 0x04:
            rd, threshold = self._decode_operands_B()
            imm8 = self._fetch_u8()  # read threshold byte
            self._exec_yield_if_contention(rd, imm8)
        elif sub_opcode == 0x05:
            rd, count = self._decode_operands_B()
            count = self._fetch_u8()
            self._exec_persist_critical_state(rd, count)
        elif sub_opcode == 0x06:
            rd, count = self._decode_operands_B()
            count = self._fetch_u8()
            self._exec_restore_critical_state(rd, count)
        elif sub_opcode == 0x07:
            rd, imm_lo, imm_hi = self._decode_ext_format_d()
            self._exec_time_budget(rd, (imm_hi << 8) | imm_lo)
        elif sub_opcode == 0x08:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_clock_compare(rd, rs1, rs2)
        elif sub_opcode == 0x09:
            (rd,) = self._decode_operands_B()
            self._exec_deadline_propagate(rd)
        elif sub_opcode == 0x0A:
            rd, timer_type = self._decode_operands_B()
            timer_type = self._fetch_u8()
            self._exec_timer_create(rd, timer_type)
        elif sub_opcode == 0x0B:
            (rd,) = self._decode_operands_B()
            self._exec_timer_check(rd)
        else:
            raise VMInvalidOpcodeError(
                f"Unknown temporal sub-opcode: 0x{sub_opcode:02X}",
                opcode=0xFC,
            )

    def _check_time_budget(self) -> None:
        """Called every N cycles to check if budget exceeded."""
        cort = self.current_coroutine()
        if cort and cort.time_budget_deadline is not None:
            now = self._host_clock_ns()
            if now >= cort.time_budget_deadline:
                # Budget exceeded — raise fault
                exceeded = now - cort.time_budget_deadline
                regs.write_gp(cort.time_budget_rd, exceeded & 0xFFFFFFFF)
                raise VMFault(
                    "TIME_BUDGET_EXCEEDED",
                    fault_code=0x20,
                    pc=self.pc,
                )
```

### 9.2 Deadline Stack Data Structure

```python
from dataclasses import dataclass

@dataclass
class DeadlineFrame:
    deadline_ns: int
    auto_pop: bool = True  # automatically popped on RET
    set_pc: int = 0       # PC where DEADLINE_SET was called

class DeadlineStack:
    def __init__(self, max_depth: int = 256):
        self._frames: list[DeadlineFrame] = []
        self._max_depth = max_depth

    @property
    def active_deadline(self) -> int:
        if self._frames:
            return self._frames[-1].deadline_ns
        return TIME_INFINITE

    def push(self, deadline_ns: int, auto_pop: bool = True, pc: int = 0) -> None:
        if len(self._frames) >= self._max_depth:
            raise VMError("DEADLINE_STACK_OVERFLOW")
        self._frames.append(DeadlineFrame(deadline_ns, auto_pop, pc))

    def pop(self) -> DeadlineFrame | None:
        if self._frames:
            return self._frames.pop()
        return None

    def remaining(self, now_ns: int) -> int:
        deadline = self.active_deadline
        if deadline == TIME_INFINITE:
            return TIME_INFINITE
        if now_ns >= deadline:
            return 0
        return deadline - now_ns
```

---

## 10. Bytecode Examples

### Example 1: Basic Time Measurement

```
; Measure execution time of a code section

CLOCK_GET R0            ; start time → R0:R1
; Encoding: [0xFC][0x01][0x00]

; --- code section to measure ---
MOVI  R2, 1000
LOOP:
DEC   R2
JNZ   R2, LOOP
; --- end code section ---

CLOCK_GET R2            ; end time → R2:R3
; Encoding: [0xFC][0x01][0x02]

CLOCK_COMPARE R4, R0, R2  ; R4 = compare(start, end) = -1 (start < end)
; Encoding: [0xFC][0x08][0x04][0x00][0x02]

; R4 = -1 means R0 (start) < R2 (end), as expected
; Actual elapsed = R2:R3 - R0:R1 (requires 64-bit subtraction)
; For simplicity, use low 32 bits only:
SUB   R5, R2, R0       ; R5 ≈ elapsed low bits (may wrap)
HALT
```

### Example 2: Deadline-Guarded Critical Section

```
; Perform a computation with a 500μs deadline

DEADLINE_SET R0, 500, 0   ; deadline = now + 500μs
; Encoding: [0xFC][0x02][0x00][0xF4][0x01]

; Critical computation
MOVI  R1, 100
COMP_LOOP:
DEC   R1
MUL   R2, R1, R1         ; R2 = i²

; Check deadline every iteration
DEADLINE_CHECK R3          ; R3 = remaining time, flag_zero = exceeded?
; Encoding: [0xFC][0x03][0x03]
JZ    R3, TIMEOUT         ; if R3 == 0, deadline exceeded

JNZ   R1, COMP_LOOP      ; continue if R1 != 0

; Success
MOVI  R0, 1               ; R0 = 1 (success)
HALT

TIMEOUT:
MOVI  R0, 0               ; R0 = 0 (timeout)
HALT
; Note: deadline frame auto-popped on HALT/RET
```

### Example 3: Time Budget with FAULT Handler

```
; Set a 10ms time budget, install handler, do work

; Install FAULT handler at PC+20 (relative offset)
MOVI16 R0, 20
HANDLER R0                ; Install fault handler at PC+20
; Encoding: [0xE8][0x00][0x00][0x14]

; Set time budget: 10ms = 10000μs
TIME_BUDGET R1, 0x10, 0x27   ; imm16 = 0x2710 = 10000μs
; Encoding: [0xFC][0x07][0x01][0x10][0x27]

; Work loop
MOVI  R2, 100000
WORK_LOOP:
DEC   R2
; ... intensive computation ...
JNZ   R2, WORK_LOOP

; Budget not exceeded — clean exit
MOVI  R0, 42
HALT

; --- FAULT handler (at offset +20) ---
; R0 contains fault code (0x20 = TIME_BUDGET_EXCEEDED)
; R1 contains remaining over-budget time (negative)
MOV   R3, R0             ; save fault code
MOVI  R4, 0              ; result = timeout
HALT
```

### Example 4: Persist and Restore Critical State

```
; Before a risky operation, persist critical registers

; Save critical computation state
MOVI  R0, 42             ; important result
MOVI  R1, 99             ; another important value
MOVI  R2, 0              ; checksum register

PERSIST_CRITICAL_STATE R0, 3  ; persist R0, R1, R2
; Encoding: [0xFC][0x05][0x00][0x03]
; After: R0 = persistence sequence number

; Store sequence number for later restore
MOV   R10, R0

; --- risky operation that might crash ---
MOVI  R0, 0              ; clear registers (simulate crash)
MOVI  R1, 0
MOVI  R2, 0

; --- crash recovery path ---
RESTORE_CRITICAL_STATE R0, 3  ; restore R0, R1, R2 from WAL
; Encoding: [0xFC][0x06][0x00][0x03]
; After: R0 = original 42, R1 = original 99, R2 = original 0

; Verify restoration
MOVI  R3, 42
CMP_EQ R4, R0, R3        ; R4 = (R0 == 42) ? 1 : 0
HALT
```

### Example 5: Contention-Aware Backoff with Deadlines

```
; A shared counter with contention-aware yielding and deadline

; Set deadline for entire operation
DEADLINE_SET R0, 1000, 0    ; 1000μs = 1ms deadline

; Shared counter at memory address 0x5000
MOVI  R5, 0x5000           ; shared counter address

INCREMENT_LOOP:
; Load current value
LOAD  R6, R5               ; R6 = current counter value

; Check contention on the shared address
YIELD_IF_CONTENTION R5, 2   ; yield if 2+ coroutines accessing 0x5000
; Encoding: [0xFC][0x04][0x05][0x02]
JZ    R5, NO_CONTENTION     ; flag_zero = True means no yield

; We yielded — check deadline
DEADLINE_CHECK R7
JZ    R7, DEADLINE_HIT      ; deadline exceeded after yield

NO_CONTENTION:
; Increment and store
INC   R6
STORE R6, R5

; Check deadline
DEADLINE_CHECK R7
JZ    R7, DEADLINE_HIT

; Continue incrementing
MOVI  R8, 100
DEC   R8
JNZ   R8, INCREMENT_LOOP

MOVI  R0, 1               ; success
HALT

DEADLINE_HIT:
MOVI  R0, 0               ; deadline exceeded
HALT
```

### Example 6: Timer-Based Periodic Check

```
; Create a periodic timer, do work, check timer

; Create repeating timer: 5000μs = 5ms
MOVI  R0, 5000            ; delay in μs
TIMER_CREATE R0, 1         ; type=1 (repeating), handle → R0
; Encoding: [0xFC][0x0A][0x00][0x01]
MOV   R10, R0             ; save timer handle

; Work loop
WORK:
; ... do periodic work ...

; Check if timer fired
TIMER_CHECK R10            ; R10 = 1 (fired), 0 (not yet), -1 (invalid)
; Encoding: [0xFC][0x0B][0x0A]

CMP_EQ R2, R10, 1         ; timer fired?
JNZ   R2, TIMER_NOT_FIRED

; Timer fired — do periodic maintenance
MOVI  R3, 0
PERSIST_CRITICAL_STATE R3, 4  ; persist R3–R6

TIMER_NOT_FIRED:
JMP   WORK                ; continue
```

---

## 11. Migration Notes

### 11.1 Backward Compatibility

- All existing opcodes (0x00–0xFB) are unchanged.
- The EXTEND_TEMPORAL prefix (0xFC) was previously `RESERVED_FC`. Code relying on 0xFC causing an ILLEGAL trap will now see it as a valid prefix.
- Existing CLK (0xF6) and WDOG (0xF8) remain unchanged.

### 11.2 Required Interpreter Changes

1. Add EXTEND_TEMPORAL dispatch to `_step()`.
2. Add deadline stack to Coroutine data structure.
3. Add WAL storage backend (can be file-backed or memory-backed for testing).
4. Add timer table and timer checking to the scheduler.
5. Integrate time budget checking into the main execution loop.
6. Modify CALL/RET to manage deadline frame auto-pop.

### 11.3 Required Encoder/Decoder Changes

1. Encoder must emit the 0xFC prefix for temporal opcodes.
2. Decoder must handle 0xFC as a two-byte prefix.
3. Disassembler must display `CLOCK_GET R0` instead of `FC 01 00`.

### 11.4 Test Plan

| Test | Description |
|------|-------------|
| `test_clock_get_basic` | Read clock, verify 64-bit value is reasonable |
| `test_deadline_set_check` | Set deadline, verify remaining time decreases |
| `test_deadline_expired` | Set deadline for 1μs, busy-wait, verify flag_zero |
| `test_deadline_propagation_call` | Set deadline, CALL function, verify function inherits it |
| `test_deadline_pop_on_ret` | Set deadline inside function, RET, verify old deadline restored |
| `test_time_budget_trap` | Set budget for 10μs, infinite loop, verify FAULT |
| `test_persist_restore_roundtrip` | Persist registers, modify, restore, verify original values |
| `test_persist_crc_validation` | Corrupt WAL entry, verify RESTORE fails gracefully |
| `test_yield_if_contention` | Two coroutines contend on address, verify yield occurs |
| `test_timer_create_fire` | Create 1ms timer, wait via AWAIT_EVENT, verify fires |
| `test_clock_compare` | Compare two known time values, verify -1/0/1 results |

---

**End of Temporal Primitives Specification — TEMP-001**
