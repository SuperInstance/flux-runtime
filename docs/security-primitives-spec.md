# FLUX ISA v4 — Security Primitives Specification

**Task Board:** SEC-001
**Author:** Super Z (Fleet Agent, Architect-rank)
**Date:** 2026-04-12
**Status:** DRAFT — Pending Review
**Depends On:** ISA v3 Unified (Format A–G encoding), Async Primitives (ASYNC-001), Temporal Primitives (TEMP-001)

---

## Table of Contents

1. [Overview and Motivation](#1-overview-and-motivation)
2. [Opcode Summary Table](#2-opcode-summary-table)
3. [Capability Model](#3-capability-model)
4. [Memory Tagging Architecture](#4-memory-tagging-architecture)
5. [Sandbox Isolation Model](#5-sandbox-isolation-model)
6. [Cryptographic Primitives](#6-cryptographic-primitives)
7. [Opcode Specifications](#7-opcode-specifications)
   - 7.1 CAP_INVOKE
   - 7.2 CAP_GRANT
   - 7.3 CAP_REVOKE
   - 7.4 CAP_CHECK
   - 7.5 MEM_TAG
   - 7.6 MEM_CHECK
   - 7.7 SANDBOX_ENTER
   - 7.8 SANDBOX_EXIT
   - 7.9 INTEGRITY_HASH
   - 7.10 SIGN
   - 7.11 VERIFY
8. [Interaction with Existing Opcodes](#8-interaction-with-existing-opcodes)
9. [Error Semantics](#9-error-semantics)
10. [Pseudocode: Execution Engine Integration](#10-pseudocode-execution-engine-integration)
11. [Bytecode Examples](#11-bytecode-examples)
12. [Migration Notes](#12-migration-notes)

---

## 1. Overview and Motivation

### 1.1 Problem Statement

The FLUX VM currently has no ISA-level security primitives. Security enforcement relies on Python-level `Sandbox` and `CapabilityRegistry` classes (in `src/flux/security/`), but these are invisible to the bytecode — there is no way for compiled code to:

- **Invoke functions with reduced capability sets** (principle of least privilege)
- **Tag memory regions** with security levels and enforce access control at load/store time
- **Enter/exit sandboxed execution regions** with verified isolation boundaries
- **Verify code integrity** at runtime via hash or signature checks
- **Enforce non-bypassable access checks** that malicious bytecode cannot circumvent

The existing `HASH` (0xAA), `HMAC` (0xAB), `VERIFY` (0xAC), `ENCRYPT` (0xAD), `DECRYPT` (0xAE), `KEYGEN` (0xAF), and `SHA256` (0x99) opcodes provide raw cryptographic operations, but they lack the policy framework to use them meaningfully for security enforcement.

### 1.2 Design Principles

1. **Hardware-enforced capability checks.** CAP_INVOKE/CAP_CHECK are non-bypassable ISA operations. A runtime without the security extension simply traps on these opcodes.
2. **Memory tagging is orthogonal to data.** Tags are stored in a parallel tag table, not in the data itself. This allows zero-cost tag operations on untagged memory.
3. **Sandbox boundaries are explicit and verified.** SANDBOX_ENTER pushes a security context; SANDBOX_EXIT pops it and verifies no state leakage.
4. **Cryptographic operations use standard algorithms.** SHA-256 for hashing, Ed25519 for signatures. No custom crypto.
5. **Defense in depth.** Multiple independent security mechanisms: capabilities, memory tags, sandboxing, and code integrity. Compromising one does not compromise all.

### 1.3 Relationship to Existing Opcodes

| Existing Opcode | Hex | Relationship |
|----------------|-----|-------------|
| `HASH` | 0xAA | Raw hash. `INTEGRITY_HASH` adds code-region semantics. |
| `HMAC` | 0xAB | Raw HMAC. `SIGN` wraps this with key management. |
| `VERIFY` | 0xAC | Raw signature verification. New `VERIFY` opcode (0xFD) adds policy. |
| `ENCRYPT` / `DECRYPT` | 0xAD / 0xAE | Raw crypto. Security primitives define *when* to use them, not *how*. |
| `KEYGEN` | 0xAF | Raw key generation. `SIGN` manages key lifecycle. |
| `SHA256` | 0x99 | SHA-256 block hash. `INTEGRITY_HASH` uses SHA-256 for code regions. |
| `MPROT` | 0xD9 | Memory protect flags. `MEM_TAG` adds security-level tagging. |
| `CAS` | 0xD5 | Compare-and-swap. Used internally by MEM_TAG for atomic tag updates. |
| `FENCE` | 0xD6 | Memory fence. `SANDBOX_EXIT` implicitly fences. |
| `FORK` (A2A) | 0x58 | Agent spawn. `SANDBOX_ENTER` is lighter-weight, same-VM isolation. |

### 1.4 Relationship to Python-Level Security

The existing Python `Sandbox` class provides:

```python
# src/flux/security/sandbox.py
class Sandbox:
    agent_id: str
    capabilities: CapabilityRegistry
    resources: ResourceMonitor
    trust_level: float
```

The new ISA-level security primitives **expose these concepts to bytecode**:

| Python Concept | ISA Opcode |
|---------------|------------|
| `sandbox.grant_capability()` | `CAP_GRANT` |
| `sandbox.check_permission()` | `CAP_CHECK` |
| `sandbox = SandboxManager.create_sandbox()` | `SANDBOX_ENTER` |
| `SandboxManager.destroy_sandbox()` | `SANDBOX_EXIT` |
| `CapabilityToken` | Capability handle in register |

---

## 2. Opcode Summary Table

All security opcodes use the **EXTEND_SECURITY prefix** (0xFD, Format A). The actual opcode follows as the second byte:

```
  Byte 0: 0xFD (EXTEND_SECURITY)
  Byte 1: sub-opcode (see table below)
  Bytes 2+: operands per sub-format
```

| Sub-Opcode | Mnemonic | Sub-Format | Operands | Size (bytes) | Description |
|-----------|----------|-----------|----------|:------------:|-------------|
| 0x01 | `CAP_INVOKE` | E | rd, rs1, rs2 | 5 | Invoke function with reduced capabilities |
| 0x02 | `CAP_GRANT` | D | rd, imm8_lo, imm8_hi | 4 | Grant capability bitmask to target |
| 0x03 | `CAP_REVOKE` | B | rd | 3 | Revoke all capabilities matching mask in rd |
| 0x04 | `CAP_CHECK` | C | rd, imm8 | 3 | Check if current context has capability imm8, result → rd |
| 0x05 | `MEM_TAG` | D | rd, imm8_lo, imm8_hi | 4 | Tag memory region with security level |
| 0x06 | `MEM_CHECK` | C | rd, imm8 | 3 | Check access rights for address in rd |
| 0x07 | `SANDBOX_ENTER` | C | rd, imm8 | 3 | Enter sandboxed region with capability set |
| 0x08 | `SANDBOX_EXIT` | A | — | 2 | Exit sandbox, verify no state leakage |
| 0x09 | `INTEGRITY_HASH` | E | rd, rs1, rs2 | 5 | SHA-256 hash of code region |
| 0x0A | `SIGN` | E | rd, rs1, rs2 | 5 | Ed25519 sign code region with agent key |
| 0x0B | `VERIFY` | E | rd, rs1, rs2 | 5 | Verify Ed25519 signature on code region |

### Total: 11 opcodes, consuming sub-opcode range 0x01–0x0B

---

## 3. Capability Model

### 3.1 Capability Representation

A capability is a **16-bit bitmask** stored in a general-purpose register:

```
Capability Bitmask (16 bits):

  Bit   Name              Description
  ────  ────────────────  ──────────────────────────────────
  0     CAP_READ           Read memory
  1     CAP_WRITE          Write memory
  2     CAP_EXECUTE        Execute code
  3     CAP_ALLOC          Allocate memory (MALLOC)
  4     CAP_FREE           Free memory (FREE)
  5     CAP_IO_READ        Read I/O devices (GPIO, I2C, SPI)
  6     CAP_IO_WRITE       Write I/O devices (PWM, actuator)
  7     CAP_NETWORK        Network access (A2A TELL/ASK)
  8     CAP_A2A_TELL        Send A2A messages
  9     CAP_A2A_ASK         Request from A2A agents
  10    CAP_A2A_DELEGATE    Delegate tasks to agents
  11    CAP_A2A_BROADCAST   Broadcast to fleet
  12    CAP_ADMIN           Administrative operations
  13    CAP_PERSIST         Persistent storage access
  14    CAP_SENSORS         Sensor read access
  15    CAP_CRYPTO          Cryptographic operations

  Special values:
  0x0000 = no capabilities (DENY ALL)
  0xFFFF = all capabilities (FULL ACCESS)
  0x0007 = READ + WRITE + EXECUTE (basic data access)
```

### 3.2 Capability Context Stack

Each coroutine maintains a **capability context stack** (separate from the call stack):

```
Capability Context Stack:

  Before SANDBOX_ENTER / CAP_INVOKE:
  ┌────────────────────────────────┐
  │ Level 0: CAP_FULL (0xFFFF)    │  ← coroutine's base capabilities
  └────────────────────────────────┘

  After CAP_INVOKE with CAP_READ | CAP_WRITE:
  ┌────────────────────────────────┐
  │ Level 0: CAP_FULL (0xFFFF)    │  ← saved
  │ Level 1: CAP_READ|WRITE (0x03)│  ← active (reduced)
  └────────────────────────────────┘

  Active capabilities = Level 1 (intersection with parent)
```

The **active capability set** is the intersection of all levels in the context stack. This means:
- A child context can only **reduce** capabilities, never increase them.
- Revoking a capability at any level takes effect immediately.
- Restoring a level (on SANDBOX_EXIT or return from CAP_INVOKE) restores the previous set.

### 3.3 Capability Token Handle

When `CAP_GRANT` creates a capability token, it returns a **handle** (32-bit integer) that can be stored in a register:

```
Capability Token Handle (32 bits):

  31    24 23    16 15     8 7      0
  ┌───────┬───────┬───────┬───────┐
  │ MAGIC │ AGENT │ PERMS │ TOKEN │
  │ 0xC1  │ ID    │ (u8)  │ ID    │
  └───────┴───────┴───────┴───────┘

  MAGIC (0xC1): Validates handle integrity
  AGENT_ID (u8): Agent that granted the capability
  PERMS (u8): Permission bitmask (low 8 bits of capability)
  TOKEN_ID (u8): Unique token identifier (0x00–0xFF)
```

### 3.4 Capability Derivation

Capabilities follow a **derivation chain**:

```
Root Agent (full capabilities):
  └── CAP_GRANT worker: CAP_READ|CAP_WRITE|CAP_EXEC (0x07)
       └── CAP_GRANT subworker: CAP_READ (0x01)  ← further reduced
```

A derived capability can never exceed its parent's permissions. The VM enforces this by checking the capability context stack.

---

## 4. Memory Tagging Architecture

### 4.1 Tag Table

Memory tagging uses a **parallel tag table** — one byte per 4-byte word of memory:

```
Tag Table Layout:

  Memory:  [word_0][word_1][word_2][word_3] ... [word_N]
  Tags:    [tag_0][tag_1][tag_2][tag_3] ... [tag_N]

  Each tag is 1 byte, corresponding to 4 bytes of data.
  Tag table size = ceil(memory_size / 4)
```

### 4.2 Security Level Encoding

```
Tag Byte Layout:

  7     6 5     4 3     2 1     0
  ┌─────┬─────┬─────┬─────┐
  │ SYS │ VAL │ CONF│ ACL │
  │     │ ID  │     │     │
  └─────┴─────┴─────┴─────┘

  SYS (1 bit):   1 = system memory (only CAP_ADMIN access)
  VALID (1 bit): 1 = tag is valid/initialized
  CONF (1 bit):  1 = contains confidence-tagged data
  ACL (2 bits):  Access control level:
    00 = PUBLIC  — any code can read/write
    01 = PRIVATE — only owning coroutine can access
    10 = SHARED  — owning coroutine + explicitly granted coroutines
    11 = LOCKED  — read-only after tagging (immutable)
```

### 4.3 Tag Enforcement Rules

| Current ACL | LOAD from target | STORE to target | Notes |
|-------------|-----------------|-----------------|-------|
| PUBLIC | Always allowed | Always allowed | No enforcement |
| PRIVATE | Owner only | Owner only | Checked via coroutine ID |
| SHARED | Owner + granted | Owner only | Read sharing, write exclusion |
| LOCKED | Always allowed | Never allowed | Write-protected |
| SYS | CAP_ADMIN only | CAP_ADMIN only | System memory |

### 4.4 Tag Performance Impact

| Scenario | Overhead | Mitigation |
|----------|----------|------------|
| Untagged memory (default) | 0% | Tags default to 0x00 (PUBLIC) — no check |
| Tagged memory, LOAD | ~2 cycles | Parallel tag lookup in hardware |
| Tagged memory, STORE | ~3 cycles | Tag lookup + ACL check |
| Tag validation failure | ~5 cycles | FAULT trap |
| Bulk tag operation (MEM_TAG) | ~1 cycle/word | Optimized memset-like operation |

### 4.5 Interaction with Existing Memory Opcodes

When security primitives are active, the following memory opcodes are instrumented:

| Opcode | Instrumentation |
|--------|----------------|
| `LOAD` (0x38) | Check tag at target address. If ACL denies READ → FAULT. |
| `STORE` (0x39) | Check tag at target address. If ACL denies WRITE → FAULT. |
| `LOADOFF` (0x48) | Same as LOAD |
| `STOREOFF` (0x49) | Same as STORE |
| `COPY` (0x4E) | Check tags on both source and destination. |
| `FILL` (0x4F) | Check tag on destination. |
| `DMA_CPY` (0xD0) | Check tags on source and destination regions. |
| `LOADI` (0x4A) | Check tag on intermediate and final address. |

Tag checking can be **disabled globally** via a VM configuration flag for performance-critical deployments.

---

## 5. Sandbox Isolation Model

### 5.1 Sandbox Context Structure

When `SANDBOX_ENTER` executes, a sandbox context is pushed:

```
Sandbox Context:

  struct SandboxContext {
      capability_set: u16,          // active capabilities inside sandbox
      memory_base: u32,             // base address of sandbox memory
      memory_size: u32,             // size of sandbox memory
      allowed_regions: list[u32],   // memory regions accessible
      max_cycles: u32,              // cycle budget inside sandbox
      channel_handle: u32,          // communication channel to parent
      parent_context_id: u32,       // parent's context ID
      entry_pc: u32,                // PC to start execution
      exit_pc: u32,                 // PC to return to on exit
  }
```

### 5.2 What's Shared vs Private Inside a Sandbox

| Resource | Shared | Private |
|----------|:------:|:-------:|
| Bytecode (read-only) | Yes | — |
| Heap memory | No (sandboxed) | Yes (own heap region) |
| Stack memory | No (sandboxed) | Yes (own stack region) |
| General-purpose registers | Inherited on entry | Saved on entry, restored on exit |
| Confidence registers | Inherited | Isolated (shadow copy) |
| A2A channels | No | Specific channel only |
| Timers | No | No |
| Persistence (WAL) | No | Yes (own WAL namespace) |
| Capabilities | Reduced set | Only granted capabilities |

### 5.3 Escape Detection

On `SANDBOX_EXIT`, the VM verifies:

1. **Register scan**: Check that no GP registers contain addresses outside the sandbox's allowed memory regions. If found → FAULT (potential data exfiltration).
2. **Stack scan**: Verify the stack does not contain pointers to parent memory.
3. **Capability scan**: Verify the capability context stack has been properly popped (no leftover elevated capabilities).
4. **Channel check**: Verify no unsanctioned data was written to the communication channel (size limit check).

```python
def _sandbox_exit_verify(self, ctx: SandboxContext) -> bool:
    """Returns True if no state leakage detected."""
    for i in range(16):
        val = regs.read_gp(i)
        if ctx.is_sandbox_address(val):
            continue  # pointer within sandbox — OK
        if val < 0x100:  # small integer — OK
            continue
        # Potentially leaked address
        if self._is_heap_or_stack_address(val):
            return False  # LEAKAGE DETECTED
    return True
```

---

## 6. Cryptographic Primitives

### 6.1 Hash Algorithms

| Algorithm | ID | Output Size | Use Case |
|-----------|:--:|:-----------:|----------|
| SHA-256 | 0x01 | 32 bytes | Code integrity, capability tokens |
| SHA-512 | 0x02 | 64 bytes | High-security integrity |
| CRC32 | 0x03 | 4 bytes | Fast checksums, WAL entries |
| BLAKE3 | 0x04 | 32 bytes | High-performance hashing |

### 6.2 Signature Schemes

| Scheme | ID | Key Size | Signature Size | Use Case |
|--------|:--:|:--------:|:--------------:|----------|
| Ed25519 | 0x01 | 32 bytes (private) | 64 bytes | Code signing, capability tokens |
| HMAC-SHA256 | 0x02 | 32 bytes (key) | 32 bytes | Message authentication |
| RSA-2048 | 0x03 | 256 bytes (private) | 256 bytes | Legacy compatibility |

### 6.3 INTEGRITY_HASH Details

`INTEGRITY_HASH` computes a SHA-256 hash over a contiguous region of bytecode:

```
Input:
  rs1 = start offset into bytecode (bytes)
  rs2 = length in bytes (0 = hash to end of bytecode)

Output (written to a special hash register, accessible via HASHRD):
  Hash register: 32 bytes, split across 8 GP registers or one V register

  R[rd]   = hash[0:4]   (first 4 bytes)
  R[rd+1] = hash[4:8]
  R[rd+2] = hash[8:12]
  ...
  R[rd+7] = hash[28:32]
```

### 6.4 SIGN Details

`SIGN` produces an Ed25519 signature over a bytecode region using the agent's private key:

```
Input:
  rs1 = start offset into bytecode
  rs2 = length in bytes

Output (signature in hash register):
  64 bytes split across 16 GP registers (R[rd]..R[rd+15])

Key source: The agent's private key is loaded from a secure key store
            at VM initialization time (not accessible from bytecode).
```

### 6.5 VERIFY Details

`VERIFY` checks an Ed25519 signature against a bytecode region and the agent's public key:

```
Input:
  rs1 = start offset into bytecode (data to verify)
  rs2 = length in bytes

Expected signature: Read from hash register (R[rd]..R[rd+15])

Output:
  R[rd] = 1 (valid), 0 (invalid), -1 (error)

Key source: The expected public key is loaded from a trusted key store
            at VM initialization time.
```

---

## 7. Opcode Specifications

### 7.1 CAP_INVOKE — Invoke with Reduced Capabilities

| Field | Value |
|-------|-------|
| **Mnemonic** | `CAP_INVOKE` |
| **Sub-opcode** | 0x01 |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFD][0x01][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | security/capability |
| **Side Effects** | Pushes capability context, changes active capability set |

#### Semantics

1. `R[rs1]` contains the target PC (function address to call).
2. `R[rs2]` contains the capability bitmask to apply during the call.
3. The current PC (return address) is saved to `R[rd]` (link register behavior).
4. The current capability set is pushed onto the capability context stack.
5. The new active capability set is set to `current_set & R[rs2]` (intersection).
6. PC jumps to `R[rs1]`.
7. On return (RET), the capability context stack is popped, restoring the previous set.

#### Binary Encoding Diagram

```
Byte 0: [0xFD]           ← EXTEND_SECURITY prefix
Byte 1: [0x01]           ← CAP_INVOKE sub-opcode
Byte 2: [rd:u8]          ← link register (return address saved here)
Byte 3: [rs1:u8]         ← target PC register
Byte 4: [rs2:u8]         ← capability bitmask register

Operation: R[rd] = PC; PC = R[rs1]; push_cap(current_caps); caps &= R[rs2]
On RET: pop_cap(); PC = R[rd]
```

#### Pseudocode

```python
def execute_CAP_INVOKE(rd: int, rs1: int, rs2: int) -> None:
    target_pc = regs.read_gp(rs1)
    cap_mask = regs.read_gp(rs2) & 0xFFFF

    # Save return address
    regs.write_gp(rd, vm.pc)

    # Push capability context
    current = current_coroutine()
    current.cap_context_stack.append(current.active_capabilities)

    # Reduce capabilities (intersection)
    new_caps = Capability(current.active_capabilities.value & cap_mask)
    current.active_capabilities = new_caps

    # Jump to target
    vm.pc = target_pc
```

#### Error Conditions

| Error | Condition | Behavior |
|-------|-----------|----------|
| `ERR_CAP_INVALID_MASK` | rs2 has bits outside defined range | FAULT trap with code 0x01 |
| `ERR_CAP_STACK_OVERFLOW` | Capability context stack > 64 deep | FAULT trap with code 0x02 |
| `ERR_CAP_TARGET_INVALID` | Target PC outside bytecode | FAULT trap with code 0x03 |

---

### 7.2 CAP_GRANT — Grant Capabilities

| Field | Value |
|-------|-------|
| **Mnemonic** | `CAP_GRANT` |
| **Sub-opcode** | 0x02 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFD][0x02][rd:u8][imm8_lo:u8][imm8_hi:u8]` |
| **Size** | 4 bytes |
| **Category** | security/capability |
| **Side Effects** | Creates capability token |

#### Semantics

1. `imm16 = (imm8_hi << 8) | imm8_lo` specifies the capability bitmask to grant.
2. The grantor's active capabilities must be a superset of `imm16`. If not → FAULT.
3. A capability token is created and its handle is written to `R[rd]`.
4. The token is registered in the VM's capability registry.
5. The token can be passed to other coroutines via channels or shared memory.

#### Pseudocode

```python
def execute_CAP_GRANT(rd: int, imm8_lo: int, imm8_hi: int) -> None:
    perms = (imm8_hi << 8) | imm8_lo
    current = current_coroutine()

    # Grantor must have the capabilities it's granting
    if (current.active_capabilities.value & perms) != perms:
        raise VMFault(
            f"CAP_GRANT: grantor lacks permissions {perms:#06x}",
            fault_code=0x04,
            pc=vm.pc,
        )

    # Create token
    token = CapabilityToken.create(
        agent_id=current.id,
        resource="*",
        permissions=perms,
        ttl_seconds=3600.0,
    )

    vm.cap_registry.register(token)
    handle = (0xC1 << 24) | (current.id << 16) | (perms & 0xFF) << 8 | token.token_id
    regs.write_gp(rd, handle & 0xFFFFFFFF)
```

---

### 7.3 CAP_REVOKE — Revoke Capabilities

| Field | Value |
|-------|-------|
| **Mnemonic** | `CAP_REVOKE` |
| **Sub-opcode** | 0x03 |
| **Format** | EXTEND + Sub-Format B |
| **Encoding** | `[0xFD][0x03][rd:u8]` |
| **Size** | 3 bytes |
| **Category** | security/capability |
| **Side Effects** | Removes capability token from registry |

#### Semantics

1. Read capability token handle from `R[rd]`.
2. Validate handle magic (0xC1).
3. Only the granting agent (or CAP_ADMIN holder) can revoke.
4. Remove the token from the VM's capability registry.
5. Write result to `R[rd]`: 1 = revoked, 0 = not found, -1 = permission denied.

---

### 7.4 CAP_CHECK — Check Current Capabilities

| Field | Value |
|-------|-------|
| **Mnemonic** | `CAP_CHECK` |
| **Sub-opcode** | 0x04 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFD][0x04][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | security/capability |
| **Side Effects** | None (read-only) |

#### Semantics

1. `imm8` is the capability bit to check (0–15, corresponding to the capability bitmask).
2. Check if the current coroutine's active capabilities include this bit.
3. Write result to `R[rd]`: 1 = has capability, 0 = does not have it.
4. Set condition flags: `flag_zero = (R[rd] == 0)`.

#### Pseudocode

```python
def execute_CAP_CHECK(rd: int, cap_bit: int) -> None:
    if cap_bit > 15:
        raise VMFault("CAP_CHECK: bit out of range", fault_code=0x05, pc=vm.pc)

    current = current_coroutine()
    has_cap = bool(current.active_capabilities.value & (1 << cap_bit))
    regs.write_gp(rd, 1 if has_cap else 0)
    vm._flag_zero = not has_cap
```

---

### 7.5 MEM_TAG — Tag Memory Region

| Field | Value |
|-------|-------|
| **Mnemonic** | `MEM_TAG` |
| **Sub-opcode** | 0x05 |
| **Format** | EXTEND + Sub-Format D |
| **Encoding** | `[0xFD][0x05][rd:u8][imm8_lo:u8][imm8_hi:u8]` |
| **Size** | 4 bytes |
| **Category** | security/memory |
| **Side Effects** | Modifies tag table |

#### Semantics

1. `R[rd]` contains the **memory address** (base of region to tag).
2. `imm8_lo` contains the **tag byte** (security level and ACL bits).
3. `imm8_hi` contains the **region size** in units of 4 bytes (0 = single word, 255 = 1020 bytes).
4. The tag byte is written to the tag table for each word in the region.
5. Only coroutines with `CAP_WRITE` and matching ACL can tag memory.

#### Binary Encoding Diagram

```
Byte 0: [0xFD]           ← EXTEND_SECURITY prefix
Byte 1: [0x05]           ← MEM_TAG sub-opcode
Byte 2: [rd:u8]          ← memory base address register
Byte 3: [imm8_lo:u8]     ← tag byte (security level)
Byte 4: [imm8_hi:u8]     ← region size in 4-byte words

Tag byte encoding:
  bit 7: SYS (system memory)
  bit 6: VALID (tag initialized)
  bit 5: CONF (confidence data)
  bits 4-3: reserved
  bits 2-1: ACL (00=PUBLIC, 01=PRIVATE, 10=SHARED, 11=LOCKED)
  bit 0: reserved
```

#### Pseudocode

```python
def execute_MEM_TAG(rd: int, tag_byte: int, size_words: int) -> None:
    current = current_coroutine()

    # Check CAP_WRITE permission
    if not current.active_capabilities.has(CAP_WRITE):
        raise VMFault("MEM_TAG: CAP_WRITE required", fault_code=0x06, pc=vm.pc)

    base_addr = regs.read_gp(rd)

    for i in range(max(size_words, 1)):
        addr = base_addr + i * 4
        vm.tag_table[addr >> 2] = tag_byte
```

---

### 7.6 MEM_CHECK — Verify Access Rights

| Field | Value |
|-------|-------|
| **Mnemonic** | `MEM_CHECK` |
| **Sub-opcode** | 0x06 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFD][0x06][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | security/memory |
| **Side Effects** | None (read-only, but sets flags) |

#### Semantics

1. `R[rd]` contains the **memory address** to check.
2. `imm8` specifies the **access type**: 0 = READ, 1 = WRITE, 2 = EXECUTE.
3. Read the tag byte at the address.
4. Check if the current coroutine's ID and capabilities allow the requested access.
5. Write result to `R[rd]`: 1 = access allowed, 0 = access denied.
6. Set condition flags: `flag_zero = (R[rd] == 0)`.

#### Access Decision Logic

```python
def _check_mem_access(self, addr: int, access_type: int) -> bool:
    current = current_coroutine()
    tag = vm.tag_table.get(addr >> 2, 0x00)

    # Untagged memory (tag = 0x00) → always allowed
    if tag == 0x00:
        return True

    # System memory → requires CAP_ADMIN
    if tag & 0x80:  # SYS bit
        return current.active_capabilities.has(CAP_ADMIN)

    # Invalid tag → deny
    if not (tag & 0x40):  # VALID bit
        return False

    # Extract ACL
    acl = (tag >> 1) & 0x03

    if acl == 0b00:  # PUBLIC
        return True
    elif acl == 0b01:  # PRIVATE
        return vm.mem_owner_table.get(addr >> 2) == current.id
    elif acl == 0b10:  # SHARED
        if access_type == 0:  # READ
            return (vm.mem_owner_table.get(addr >> 2) == current.id or
                    current.id in vm.mem_shared_table.get(addr >> 2, set()))
        else:  # WRITE
            return vm.mem_owner_table.get(addr >> 2) == current.id
    elif acl == 0b11:  # LOCKED
        return access_type == 0  # READ only

    return False
```

---

### 7.7 SANDBOX_ENTER — Enter Sandboxed Region

| Field | Value |
|-------|-------|
| **Mnemonic** | `SANDBOX_ENTER` |
| **Sub-opcode** | 0x07 |
| **Format** | EXTEND + Sub-Format C |
| **Encoding** | `[0xFD][0x07][rd:u8][imm8:u8]` |
| **Size** | 3 bytes |
| **Category** | security/sandbox |
| **Side Effects** | Creates isolated execution context |

#### Semantics

1. `R[rd]` contains the **sandbox configuration handle** (created via SYS call or previous SANDBOX_ENTER).
2. `imm8` specifies the **capability restriction mask**: the sandbox's capabilities are set to `current & imm8_extended`.
3. Save the current register file, stack pointer, and capability context.
4. Allocate a new heap region for the sandbox.
5. Set up a communication channel between sandbox and parent.
6. Jump to the sandbox's entry point (stored in the configuration handle).

#### Pseudocode

```python
def execute_SANDBOX_ENTER(rd: int, cap_mask_ext: int) -> None:
    config_handle = regs.read_gp(rd)
    config = vm.sandbox_configs.get(config_handle)

    if config is None:
        raise VMFault("SANDBOX_ENTER: invalid config handle", fault_code=0x07, pc=vm.pc)

    current = current_coroutine()

    # Save current state for SANDBOX_EXIT
    ctx = SandboxContext(
        saved_regs=regs.snapshot(),
        saved_sp=regs.sp,
        saved_fp=regs.fp,
        saved_caps=current.active_capabilities,
        saved_pc=vm.pc,
        config=config,
    )
    current.sandbox_stack.append(ctx)

    # Set up sandboxed environment
    sandbox_heap = memory.create_region(
        f"sandbox_{current.id}_{len(current.sandbox_stack)}",
        config.memory_size,
        "sandbox",
    )

    # Reduce capabilities
    new_caps = Capability(current.active_capabilities.value & (cap_mask_ext * 256))
    current.active_capabilities = new_caps

    # Reset registers for sandbox entry
    for i in range(16):
        regs.write_gp(i, 0)
    regs.sp = config.memory_size  # new stack top
    regs.fp = regs.sp

    # Jump to sandbox entry point
    vm.pc = config.entry_pc
```

---

### 7.8 SANDBOX_EXIT — Exit Sandbox

| Field | Value |
|-------|-------|
| **Mnemonic** | `SANDBOX_EXIT` |
| **Sub-opcode** | 0x08 |
| **Format** | EXTEND + Sub-Format A |
| **Encoding** | `[0xFD][0x08]` |
| **Size** | 2 bytes |
| **Category** | security/sandbox |
| **Side Effects** | Restores pre-sandbox state, verifies no leakage |

#### Semantics

1. Verify that the sandbox context stack is non-empty.
2. Run the **escape detection** algorithm (Section 5.3).
3. If escape detected → FAULT with code 0x08 (SANDBOX_ESCAPE).
4. If clean → restore pre-sandbox registers, capabilities, and PC.
5. Destroy the sandbox's heap region.
6. Close the sandbox-parent communication channel.
7. The sandbox's return value (R0 at exit) is preserved and available to the parent.

#### Pseudocode

```python
def execute_SANDBOX_EXIT() -> None:
    current = current_coroutine()

    if not current.sandbox_stack:
        raise VMFault("SANDBOX_EXIT: not in sandbox", fault_code=0x09, pc=vm.pc)

    ctx = current.sandbox_stack[-1]

    # Escape detection
    return_value = regs.read_gp(0)  # preserve sandbox return value

    if not _sandbox_exit_verify(ctx):
        raise VMFault("SANDBOX_EXIT: state leakage detected", fault_code=0x08, pc=vm.pc)

    # Restore state
    current.sandbox_stack.pop()
    regs.restore(ctx.saved_regs)
    regs.sp = ctx.saved_sp
    regs.fp = ctx.saved_fp
    current.active_capabilities = ctx.saved_caps

    # Restore return value from sandbox
    regs.write_gp(0, return_value)

    # Return to pre-sandbox PC
    vm.pc = ctx.saved_pc

    # Destroy sandbox heap
    memory.destroy_region(f"sandbox_{current.id}_{len(current.sandbox_stack) + 1}")

    # Implicit memory fence
    execute_FENCE()
```

---

### 7.9 INTEGRITY_HASH — Hash Code Region

| Field | Value |
|-------|-------|
| **Mnemonic** | `INTEGRITY_HASH` |
| **Sub-opcode** | 0x09 |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFD][0x09][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | security/crypto |
| **Side Effects** | Writes to hash register |

#### Semantics

1. `R[rs1]` = start offset into bytecode (bytes).
2. `R[rs2]` = length in bytes (0 = hash from offset to end of bytecode).
3. Compute SHA-256 of `bytecode[rs1:rs1+rs2]`.
4. Write the 32-byte hash to registers `R[rd]` through `R[rd+7]` (4 bytes each).
5. Requires `CAP_CRYPTO` capability.

#### Pseudocode

```python
def execute_INTEGRITY_HASH(rd: int, rs1: int, rs2: int) -> None:
    current = current_coroutine()
    if not current.active_capabilities.has(CAP_CRYPTO):
        raise VMFault("INTEGRITY_HASH: CAP_CRYPTO required", fault_code=0x0A, pc=vm.pc)

    offset = regs.read_gp(rs1)
    length = regs.read_gp(rs2)
    if length == 0:
        length = len(vm.bytecode) - offset

    data = vm.bytecode[offset:offset + length]
    digest = hashlib.sha256(data).digest()  # 32 bytes

    for i in range(8):
        word = struct.unpack_from('<I', digest, i * 4)[0]
        if rd + i < 16:
            regs.write_gp(rd + i, word)
```

---

### 7.10 SIGN — Sign Code Region

| Field | Value |
|-------|-------|
| **Mnemonic** | `SIGN` |
| **Sub-opcode** | 0x0A |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFD][0x0A][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | security/crypto |
| **Side Effects** | Writes 64-byte signature to registers |

#### Semantics

1. `R[rs1]` = start offset into bytecode.
2. `R[rs2]` = length in bytes.
3. Sign `bytecode[rs1:rs1+rs2]` using the agent's Ed25519 private key.
4. Write the 64-byte signature to `R[rd]` through `R[rd+15]` (4 bytes each).
5. Requires `CAP_CRYPTO` and `CAP_ADMIN` capabilities.

---

### 7.11 VERIFY — Verify Signature

| Field | Value |
|-------|-------|
| **Mnemonic** | `VERIFY` |
| **Sub-opcode** | 0x0B |
| **Format** | EXTEND + Sub-Format E |
| **Encoding** | `[0xFD][0x0B][rd:u8][rs1:u8][rs2:u8]` |
| **Size** | 5 bytes |
| **Category** | security/crypto |
| **Side Effects** | Sets condition flags |

#### Semantics

1. `R[rs1]` = start offset into bytecode.
2. `R[rs2]` = length in bytes.
3. Read the expected 64-byte signature from `R[rd]` through `R[rd+15]`.
4. Verify the signature against `bytecode[rs1:rs1+rs2]` using the agent's Ed25519 public key.
5. Write result to `R[rd]`: 1 = valid, 0 = invalid, -1 = error.
6. Set `flag_zero = (R[rd] == 0)`.
7. Requires `CAP_CRYPTO` capability.

#### Pseudocode

```python
def execute_VERIFY(rd: int, rs1: int, rs2: int) -> None:
    current = current_coroutine()
    if not current.active_capabilities.has(CAP_CRYPTO):
        raise VMFault("VERIFY: CAP_CRYPTO required", fault_code=0x0A, pc=vm.pc)

    # Collect signature from R[rd]..R[rd+15]
    sig_bytes = b""
    for i in range(16):
        if rd + i < 16:
            word = regs.read_gp(rd + i)
            sig_bytes += struct.pack('<I', word & 0xFFFFFFFF)

    offset = regs.read_gp(rs1)
    length = regs.read_gp(rs2)
    data = vm.bytecode[offset:offset + length]

    try:
        public_key = vm.agent_public_key  # loaded at init
        valid = ed25519_verify(public_key, sig_bytes, data)
        regs.write_gp(rd, 1 if valid else 0)
        vm._flag_zero = not valid
    except Exception:
        regs.write_gp(rd, -1)
        vm._flag_zero = False
```

---

## 8. Interaction with Existing Opcodes

### 8.1 CAP_INVOKE vs CALL

| Feature | CALL (0x45) | CAP_INVOKE (0xFD 0x01) |
|---------|-------------|------------------------|
| Purpose | Transfer control | Transfer control + restrict capabilities |
| Capability change | None | Reduces to specified mask |
| Return mechanism | RET (0x02) | RET (0x02) — auto-restores caps |
| Link register | Optional | Always saved to R[rd] |
| Nesting | Call stack | Both call stack + cap context stack |

### 8.2 MEM_TAG vs MPROT (0xD9)

| Feature | MPROT (0xD9) | MEM_TAG (0xFD 0x05) |
|---------|-------------|---------------------|
| Scope | Memory region (flags: R/W/X) | Per-word security level |
| Granularity | Page-level (OS-like) | Word-level (4 bytes) |
| Ownership | No ownership tracking | Per-word ownership + sharing |
| Confidence | No | Confidence data flag |
| Enforcement | Hardware fault | VM-level FAULT trap |

### 8.3 INTEGRITY_HASH vs SHA256 (0x99)

| Feature | SHA256 (0x99) | INTEGRITY_HASH (0xFD 0x09) |
|---------|---------------|---------------------------|
| Input | Message in memory registers | Bytecode region (offset + length) |
| Output | Single register (truncated) | 8 registers (full 256-bit hash) |
| Capability check | None | Requires CAP_CRYPTO |
| Use case | General hashing | Code integrity verification |

### 8.4 SANDBOX_ENTER vs FORK (A2A, 0x58)

| Feature | FORK (A2A) | SANDBOX_ENTER |
|---------|-----------|---------------|
| Isolation | Separate VM (process-level) | Same VM, restricted context |
| Communication | A2A protocol | Shared channel + heap |
| Performance overhead | High | Low |
| State restoration | N/A (separate process) | Automatic on exit |
| Escape detection | N/A | Register + stack scanning |

---

## 9. Error Semantics

### 9.1 Error Classification

| Error Code | Name | Severity | Recovery |
|-----------|------|----------|----------|
| 0x01 | `ERR_CAP_INVALID_MASK` | Fatal | Fix capability bitmask |
| 0x02 | `ERR_CAP_STACK_OVERFLOW` | Fatal | Reduce nesting |
| 0x03 | `ERR_CAP_TARGET_INVALID` | Fatal | Fix target PC |
| 0x04 | `ERR_CAP_INSUFFICIENT` | Recoverable | Acquire capabilities before granting |
| 0x05 | `ERR_CAP_BIT_RANGE` | Fatal | Bit must be 0–15 |
| 0x06 | `ERR_MEM_TAG_NO_WRITE` | Recoverable | Acquire CAP_WRITE |
| 0x07 | `ERR_SANDBOX_INVALID` | Fatal | Fix config handle |
| 0x08 | `ERR_SANDBOX_ESCAPE` | Critical | State leakage detected, sandbox terminated |
| 0x09 | `ERR_SANDBOX_NOT_IN` | Fatal | Not inside a sandbox |
| 0x0A | `ERR_CRYPTO_NO_PERM` | Recoverable | Acquire CAP_CRYPTO |
| 0x0B | `ERR_MEM_ACCESS_DENIED` | Recoverable | Check ACL before access |
| 0x0C | `ERR_VERIFY_INVALID` | Recoverable | Check signature data |
| 0x0D | `ERR_SIGN_NO_KEY` | Fatal | Agent key not loaded |
| 0x0E | `ERR_TAG_TABLE_FULL` | Fatal | Increase tag table size |

### 9.2 FAULT on Security Violation

All security violations raise a `FAULT` (0xE7) with the security error code. The fault handler can:

1. **Log the violation** (DEBUG_BREAK / TRACE).
2. **Reduce capabilities further** (CAP_REVOKE).
3. **Terminate the sandbox** (SANDBOX_EXIT with leakage report).
4. **Halt the VM** (HALT_ERR 0xF0).

```python
# Example fault handler for security violations
SECURITY_FAULT_HANDLER:
    ; R0 = fault code
    ; Check if this is a sandbox escape
    MOVI  R1, 0x08
    CMP_EQ R2, R0, R1
    JNZ   R2, HANDLE_ESCAPE

    ; Other security faults
    MOVI  R0, 0
    HALT_ERR              ; halt with error

HANDLE_ESCAPE:
    ; Log the escape attempt
    MOVI16 R1, "ESC"
    TRACE R0, R1
    ; Force sandbox exit
    SANDBOX_EXIT
    HALT
```

---

## 10. Pseudocode: Execution Engine Integration

### 10.1 Security-Enhanced Interpreter

```python
class SecurityInterpreter(TemporalInterpreter):
    """Extended interpreter with security support."""

    MAX_CAP_STACK_DEPTH = 64
    MAX_SANDBOX_DEPTH = 16

    def __init__(self, bytecode: bytes, agent_key: bytes | None = None, **kwargs):
        super().__init__(bytecode, **kwargs)
        self._cap_registry = CapabilityRegistry()
        self._tag_table: dict[int, int] = {}  # addr_word_index -> tag_byte
        self._mem_owner_table: dict[int, int] = {}  # addr_word_index -> cort_id
        self._mem_shared_table: dict[int, set[int]] = {}  # addr_word_index -> set(cort_ids)
        self._agent_public_key = agent_key
        self._sandbox_configs: dict[int, SandboxConfig] = {}

    def _dispatch_security(self, sub_opcode: int) -> None:
        """Handle EXTEND_SECURITY (0xFD) prefix."""
        if sub_opcode == 0x01:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_cap_invoke(rd, rs1, rs2)
        elif sub_opcode == 0x02:
            rd, imm_lo, imm_hi = self._decode_ext_format_d()
            self._exec_cap_grant(rd, (imm_hi << 8) | imm_lo)
        elif sub_opcode == 0x03:
            (rd,) = self._decode_operands_B()
            self._exec_cap_revoke(rd)
        elif sub_opcode == 0x04:
            (rd,) = self._decode_operands_B()
            cap_bit = self._fetch_u8()
            self._exec_cap_check(rd, cap_bit)
        elif sub_opcode == 0x05:
            rd, tag_byte, size = self._decode_ext_format_d()
            self._exec_mem_tag(rd, tag_byte, size)
        elif sub_opcode == 0x06:
            (rd,) = self._decode_operands_B()
            access_type = self._fetch_u8()
            self._exec_mem_check(rd, access_type)
        elif sub_opcode == 0x07:
            (rd,) = self._decode_operands_B()
            cap_mask = self._fetch_u8()
            self._exec_sandbox_enter(rd, cap_mask)
        elif sub_opcode == 0x08:
            self._exec_sandbox_exit()
        elif sub_opcode == 0x09:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_integrity_hash(rd, rs1, rs2)
        elif sub_opcode == 0x0A:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_sign(rd, rs1, rs2)
        elif sub_opcode == 0x0B:
            rd, rs1, rs2 = self._decode_operands_E()
            self._exec_verify(rd, rs1, rs2)
        else:
            raise VMInvalidOpcodeError(
                f"Unknown security sub-opcode: 0x{sub_opcode:02X}",
                opcode=0xFD,
            )

    def _instrument_load(self, addr: int) -> None:
        """Called before every LOAD to check memory tags."""
        word_idx = addr >> 2
        tag = self._tag_table.get(word_idx, 0x00)
        if tag == 0x00:
            return  # untagged, allow
        if not self._check_mem_access(addr, access_type=0):  # READ
            raise VMFault(
                f"MEM_ACCESS_DENIED: read at 0x{addr:08X} (tag=0x{tag:02X})",
                fault_code=0x0B,
                pc=self.pc,
            )

    def _instrument_store(self, addr: int) -> None:
        """Called before every STORE to check memory tags."""
        word_idx = addr >> 2
        tag = self._tag_table.get(word_idx, 0x00)
        if tag == 0x00:
            return  # untagged, allow
        if not self._check_mem_access(addr, access_type=1):  # WRITE
            raise VMFault(
                f"MEM_ACCESS_DENIED: write at 0x{addr:08X} (tag=0x{tag:02X})",
                fault_code=0x0B,
                pc=self.pc,
            )
```

### 10.2 Capability Context Stack

```python
@dataclass
class CapabilityContext:
    capabilities: int  # 16-bit bitmask
    set_pc: int        # PC where caps were set
    auto_pop: bool = True

class CapabilityStack:
    def __init__(self, max_depth: int = 64):
        self._contexts: list[CapabilityContext] = []
        self._max_depth = max_depth

    @property
    def active(self) -> int:
        """Returns the intersection of all capability sets."""
        if not self._contexts:
            return 0xFFFF  # full access
        result = self._contexts[0].capabilities
        for ctx in self._contexts[1:]:
            result &= ctx.capabilities
        return result

    def push(self, caps: int, pc: int = 0, auto_pop: bool = True) -> None:
        if len(self._contexts) >= self._max_depth:
            raise VMError("CAP_STACK_OVERFLOW")
        self._contexts.append(CapabilityContext(caps, pc, auto_pop))

    def pop(self) -> CapabilityContext | None:
        return self._contexts.pop() if self._contexts else None
```

---

## 11. Bytecode Examples

### Example 1: Capability-Restricted Function Call

```
; Call a function with only READ and WRITE capabilities (no network, no I/O)

; Set up arguments
MOVI  R0, 0x1000       ; data address
MOVI  R1, 100          ; data length

; Invoke process_data with reduced capabilities
; CAP_READ=0x01, CAP_WRITE=0x02 → mask = 0x0003
MOVI  R3, 0x0003       ; capability mask
MOVI  R4, 0x0050       ; target PC (process_data function)
CAP_INVOKE R2, R4, R3  ; R2 = return PC, jump to R4, caps = 0x0003
; Encoding: [0xFD][0x01][0x02][0x04][0x03]

; After CAP_INVOKE returns (via RET):
; R0 = return value from process_data
; Capabilities restored to full
HALT

; --- process_data (at PC 0x0050) ---
; Inside this function, capabilities are READ|WRITE only
; Attempting A2A operations will fail with CAP_ACCESS_DENIED
MOV   R5, R0           ; R5 = data address
MOV   R6, R1           ; R6 = length
; ... process data using only LOAD/STORE ...
MOVI  R0, 1            ; return success
RET                     ; auto-restores capabilities
```

### Example 2: Memory Tagging with Access Control

```
; Tag a sensitive region as PRIVATE, then verify access control

; Tag memory region at 0x2000 (16 words = 64 bytes) as PRIVATE
MOVI  R0, 0x2000       ; base address

; Tag byte: 0b01000010 = VALID(1) | ACL=PRIVATE(01) | CONF(0) | SYS(0)
MOVI  R1, 0x42         ; tag byte: PRIVATE, valid
MEM_TAG R0, 0x42, 16   ; tag 16 words starting at 0x2000
; Encoding: [0xFD][0x05][0x00][0x42][0x10]

; Write data to the tagged region (should succeed — we are the owner)
MOVI  R1, 42
STORE R1, [0x2000]     ; OK — we own this region

; Check access before reading
MOVI  R0, 0x2000
MEM_CHECK R0, 0        ; check READ access (0=READ)
; Encoding: [0xFD][0x06][0x00][0x00]
JZ    R0, ACCESS_DENIED  ; if R0 == 0, access denied

; Lock the region (make read-only)
; Tag byte: 0b01000110 = VALID(1) | ACL=LOCKED(11) | CONF(0) | SYS(0)
MEM_TAG R0, 0x46, 16   ; tag as LOCKED
; Encoding: [0xFD][0x05][0x00][0x46][0x10]

; Try to write to locked region (should fail)
MOVI  R1, 99
STORE R1, [0x2000]     ; FAULT: MEM_ACCESS_DENIED (LOCKED)

ACCESS_DENIED:
MOVI  R0, 0
HALT
```

### Example 3: Sandbox Execution with Isolation

```
; Create a sandbox for untrusted code, execute it, verify cleanup

; Set up sandbox configuration (via SYS call)
MOVI  R0, 4096         ; sandbox heap size
MOVI  R1, 0x0100       ; sandbox entry PC
SYS   0x50             ; SYS_CREATE_SANDBOX(heap_size, entry_pc) → config handle → R0
MOV   R10, R0          ; save config handle

; Enter sandbox with READ|WRITE|EXECUTE only (0x0007)
SANDBOX_ENTER R10, 0x07
; Encoding: [0xFD][0x07][0x0A][0x07]

; --- Inside sandbox ---
; Registers are reset, only R10 (config) might be accessible
; Heap is isolated, capabilities reduced
; ... untrusted code executes here ...
MOVI  R0, 42           ; sandbox return value

; Exit sandbox (triggers escape detection)
SANDBOX_EXIT
; Encoding: [0xFD][0x08]

; --- Back in parent ---
; R0 = 42 (sandbox return value, preserved)
; All other registers restored to pre-sandbox state
; If escape was detected, FAULT would have been raised

MOVI  R1, 42
CMP_EQ R2, R0, R1      ; verify return value
HALT
```

### Example 4: Code Integrity Verification

```
; Hash a code region, verify it matches expected value

; Hash code from offset 0x100 to 0x200 (256 bytes)
MOVI  R1, 0x100        ; start offset
MOVI  R2, 0x100        ; length (256 bytes)
INTEGRITY_HASH R3, R1, R2  ; hash → R3..R10
; Encoding: [0xFD][0x09][0x03][0x01][0x02]

; Compare against expected hash (pre-loaded into R11..R18)
CMP_EQ R4, R3, R11     ; compare first word
JNZ   R4, INTEGRITY_FAIL
CMP_EQ R4, R4_reg, R12 ; compare second word (using R4 temporarily)
; ... (repeat for all 8 words) ...

MOVI  R0, 1            ; integrity OK
HALT

INTEGRITY_FAIL:
; Code has been tampered with!
MOVI  R0, 0
HALT_ERR
```

### Example 5: Sign and Verify Code Region

```
; Sign a code region, then verify the signature

; --- Signing Phase (agent with private key) ---

; Sign code from offset 0x200 to 0x300 (256 bytes)
MOVI  R1, 0x200        ; start offset
MOVI  R2, 0x100        ; length
SIGN R3, R1, R2        ; sign → R3..R18 (64 bytes)
; Encoding: [0xFD][0x0A][0x03][0x01][0x02]

; Save signature to memory for later verification
STORE R3,  [0x4000]
STORE R4,  [0x4004]
; ... save R5..R18 to 0x4008..0x403C ...

; --- Verification Phase (possibly different agent) ---

; Load signature from memory
LOAD  R3,  [0x4000]
LOAD  R4,  [0x4004]
; ... load R5..R18 from 0x4008..0x403C ...

; Verify the signature
MOVI  R1, 0x200        ; same offset
MOVI  R2, 0x100        ; same length
VERIFY R3, R1, R2      ; verify using R3..R18 as expected signature
; Encoding: [0xFD][0x0B][0x03][0x01][0x02]

; R3 = 1 (valid), 0 (invalid), -1 (error)
CMP_EQ R4, R3, 1
JNZ   R4, SIG_INVALID

MOVI  R0, 1            ; signature valid
HALT

SIG_INVALID:
MOVI  R0, 0            ; signature invalid!
HALT_ERR
```

### Example 6: Capability Grant and Check

```
; Grant a restricted capability token, pass to another coroutine,
; which checks its capabilities before performing operations

; --- Parent coroutine ---
; Grant READ capability (bit 0) to a child
MOVI  R0, 0x0001       ; capability mask: READ only
CAP_GRANT R1, 0x01, 0x00  ; grant → handle in R1
; Encoding: [0xFD][0x02][0x01][0x01][0x00]

; Pass handle to child via channel
COROUTINE_SPAWN R2, 30, 0x01  ; spawn child at PC+30
CHANNEL_SEND R3, R1, 0  ; send capability handle to child

; --- Child coroutine (at PC+30) ---
CHANNEL_RECV R3, R1, 0   ; receive capability handle → R1

; Check if we have READ capability
CAP_CHECK R4, 0         ; check bit 0 (CAP_READ)
; Encoding: [0xFD][0x04][0x04][0x00]
JZ    R4, NO_READ       ; no READ capability

; We have READ — proceed
LOAD  R5, [0x1000]      ; read data
HALT

NO_READ:
; No READ capability — request it or fail
MOVI  R0, 0
HALT_ERR
```

---

## 12. Migration Notes

### 12.1 Backward Compatibility

- All existing opcodes (0x00–0xFC) are unchanged.
- The EXTEND_SECURITY prefix (0xFD) was previously `RESERVED_FD`. Code relying on 0xFD causing an ILLEGAL trap will now see it as a valid prefix.
- Existing `HASH`, `HMAC`, `VERIFY`, `ENCRYPT`, `DECRYPT`, `KEYGEN`, `SHA256` opcodes (0x99, 0xAA–0xAF) remain unchanged and do not require capability checks (for backward compatibility). The new security opcodes (`INTEGRITY_HASH`, `SIGN`, `VERIFY`) add capability requirements but do not remove the old ones.

### 12.2 Required Interpreter Changes

1. Add EXTEND_SECURITY dispatch to `_step()`.
2. Add capability context stack to each Coroutine.
3. Add tag table to the VM (can be a sparse dict for memory efficiency).
4. Add sandbox stack to each Coroutine.
5. Instrument LOAD/STORE to check memory tags (optional, can be toggled).
6. Add agent key loading at VM initialization.
7. Integrate capability checks with A2A opcodes (TELL requires CAP_A2A_TELL, etc.).

### 12.3 Required Encoder/Decoder Changes

1. Encoder must emit the 0xFD prefix for security opcodes.
2. Decoder must handle 0xFD as a two-byte prefix.
3. Disassembler must display `CAP_INVOKE R2, R4, R3` instead of `FD 01 02 04 03`.

### 12.4 Interaction with Python-Level Security

The ISA-level security primitives complement (not replace) the existing Python security:

| Python Security | ISA Security | Integration |
|----------------|-------------|-------------|
| `Sandbox.grant_capability()` | `CAP_GRANT` opcode | ISA opcode calls Python method internally |
| `Sandbox.check_permission()` | `CAP_CHECK` opcode | ISA opcode checks Python registry |
| `SandboxManager.create_sandbox()` | `SANDBOX_ENTER` opcode | ISA opcode creates Python Sandbox |
| `CapabilityToken` | Handle in register | Register holds token hash |
| `Permission` flags | 16-bit capability bitmask | Direct mapping (first 16 bits) |

### 12.5 Test Plan

| Test | Description |
|------|-------------|
| `test_cap_invoke_restricts` | Invoke with CAP_READ only, verify A2A fails |
| `test_cap_invoke_restores` | CAP_INVOKE returns, verify caps restored |
| `test_cap_grant_check` | Grant token, pass to coroutine, verify CAP_CHECK passes |
| `test_cap_revoke` | Grant then revoke, verify CAP_CHECK fails |
| `test_mem_tag_private` | Tag region PRIVATE, verify owner can access |
| `test_mem_tag_locked` | Tag region LOCKED, verify write fails |
| `test_mem_check_before_access` | MEM_CHECK returns 0 for denied access |
| `test_sandbox_enter_exit` | Enter sandbox, compute, exit, verify return value |
| `test_sandbox_escape_detected` | Try to leak address, verify FAULT on exit |
| `test_integrity_hash` | Hash bytecode region, verify matches expected |
| `test_sign_verify_roundtrip` | Sign then verify, expect valid |
| `test_verify_tampered` | Tamper with data after signing, verify invalid |
| `test_cap_stack_depth` | Exceed max cap stack depth, verify FAULT |
| `test_untagged_memory_no_overhead` | Verify LOAD/STORE on untagged memory has no FAULT |

---

**End of Security Primitives Specification — SEC-001**
