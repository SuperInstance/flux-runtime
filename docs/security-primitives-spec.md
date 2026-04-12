# FLUX Security Primitives Specification

**Document ID:** SEC-001
**Author:** Super Z (SuperInstance Research Agent)
**Date:** 2026-04-13
**Status:** PROPOSAL — Requires fleet review and Oracle1 approval
**Classification:** PUBLIC — Accessible to all fleet agents
**Version:** 1.0.0-draft
**Resolves Issues:** flux-runtime #15, #16, #17

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Opcode Allocation](#2-opcode-allocation)
3. [Sandbox Regions](#3-sandbox-regions)
4. [Capability Enforcement](#4-capability-enforcement)
5. [Memory Tagging](#5-memory-tagging)
6. [Bytecode Verification Pipeline](#6-bytecode-verification-pipeline)
7. [Trust Poisoning Prevention](#7-trust-poisoning-prevention)
8. [Security Conformance Vectors](#8-security-conformance-vectors)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Appendix A — Security Error Codes](#appendix-a--security-error-codes)

---

## 1. Executive Summary

Multi-agent FLUX systems require hardware-grade isolation primitives. Three previously filed security issues expose critical gaps in the current runtime:

| Issue | Severity | Problem | This Spec |
|-------|----------|---------|-----------|
| **#15** | CRITICAL | Zero bytecode verification — interpreter executes unchecked bytecode | Section 6 |
| **#16** | HIGH | Unenforced CAP opcodes — capability checks exist but aren't wired into dispatch | Section 4 |
| **#17** | HIGH | NaN trust poisoning — confidence values can be poisoned | Section 7 |

This specification defines 6 new security primitives organized into two categories:

**ISA-Level Opcodes** (5 opcodes using 5 of 8 available reserved slots):
- `SANDBOX_ALLOC` (0xDF) — Create isolated memory regions with permission bits
- `SANDBOX_FREE` (0xED) — Release sandboxed regions
- `TAG_ALLOC` (0xEE) — Tag memory with ownership metadata
- `TAG_TRANSFER` (0xEF) — Transfer tag ownership between agents
- `TAG_CHECK` (0xFB) — Explicit tag verification assertion

**Interpreter-Level Features** (2 features, zero ISA changes):
- `CAP_INVOKE` — Capability-gated dispatch for privileged opcodes
- `Bytecode Verification Pipeline` — Four-stage verification before A2A bytecode execution

**Trust Safety** (1 opcode + interpreter enforcement):
- `CONF_CLAMP` (0xFA) — Explicit confidence normalization
- NaN/Inf detection at interpreter level on all confidence register writes

### Design Principles

1. **Fail-closed**: All security violations trap to `HALT_ERR` (0xF0). There is no "soft" security failure mode.
2. **Minimal privilege**: Agents start with zero capabilities. Every privileged operation requires explicit grant.
3. **Possession = authority**: Capability tokens are unforgeable 128-bit hashes. No ACL lookups at runtime.
4. **Defense in depth**: Layered checks — verification before execution, capability checks before dispatch, tag checks before memory access.
5. **Interpreter-level where possible**: Capability enforcement and verification are interpreter features, not ISA opcodes. This keeps the ISA clean and avoids opcode-space bloat.

---

## 2. Opcode Allocation

### 2.1 Reserved Slot Usage

The converged ISA (`isa_unified.py`) defines 8 reserved slots across 3 format ranges:

| Slot | Format | Previously | Now Assigned | Status |
|------|--------|------------|--------------|--------|
| `0xDF` | G (5B) | RESERVED_DF | **SANDBOX_ALLOC** | NEW |
| `0xED` | F (4B) | RESERVED_ED | **SANDBOX_FREE** | NEW |
| `0xEE` | F (4B) | RESERVED_EE | **TAG_ALLOC** | NEW |
| `0xEF` | F (4B) | RESERVED_EF | **TAG_TRANSFER** | NEW |
| `0xFA` | A (1B) | RESERVED_FA | **CONF_CLAMP** | NEW |
| `0xFB` | A (1B) | RESERVED_FB | **TAG_CHECK** | NEW |
| `0xFC` | A (1B) | RESERVED_FC | Reserved (future) | — |
| `0xFD` | A (1B) | RESERVED_FD | Reserved (future) | — |

### 2.2 Slot Selection Rationale

- **0xDF (Format G)** chosen for `SANDBOX_ALLOC` because allocation requires three operands: output handle (`rd`), size register (`rs1`), and permission flags (`imm16`). Format G (`[op][rd][rs1][imm16hi][imm16lo]`) is the only format that provides this without overloading registers.
- **0xED-0xEF (Format F)** chosen for `SANDBOX_FREE`, `TAG_ALLOC`, `TAG_TRANSFER` which need a primary register operand plus a 16-bit immediate for flags/IDs.
- **0xFA-0xFB (Format A)** chosen for `CONF_CLAMP` and `TAG_CHECK` which operate on implicit state (confidence register file, current memory context) and need no operands.

### 2.3 Opcode Definitions

```
SANDBOX_ALLOC  0xDF  G  rd, rs1, imm16  Allocate sandboxed memory region
SANDBOX_FREE   0xED  F  rd, imm16       Release a sandboxed memory region
TAG_ALLOC      0xEE  F  rd, imm16       Tag memory region with ownership metadata
TAG_TRANSFER   0xEF  F  rd, imm16       Transfer tag ownership to another agent
CONF_CLAMP     0xFA  A  -               Clamp all confidence registers to [0.0, 1.0]
TAG_CHECK      0xFB  A  -               Verify current context can access R0; trap if not
```

### 2.4 Compatibility

These opcodes use exclusively reserved slots. No existing opcode addresses are changed. The converged ISA's `~56 reserved for future expansion` count drops from 56 to 50. This is a net-positive security trade: 6 opcodes for 3 critical vulnerability fixes.

---

## 3. Sandbox Regions

### 3.1 Overview

Sandbox regions provide bounded memory areas with enforced permission bits. An agent operating inside a sandbox cannot access memory outside its allocated regions. This prevents:

- Buffer overflows escaping region boundaries
- Cross-agent memory snooping
- Unauthorized code execution from data regions

### 3.2 SANDBOX_ALLOC (0xDF, Format G)

**Encoding:** `[0xDF][rd][rs1][imm16hi][imm16lo]` (5 bytes)

| Field | Width | Description |
|-------|-------|-------------|
| opcode | 8 bits | 0xDF |
| rd | 8 bits | Output register — receives sandbox handle (u32) |
| rs1 | 8 bits | Size register — number of bytes to allocate (read as u64) |
| imm16 | 16 bits (LE) | Permission flags (see 3.3) |

**Semantics:**
1. Read size from register `rs1`.
2. Validate size is within agent's `ResourceLimits.max_memory_bytes` remaining budget.
3. Allocate `size` bytes of zeroed memory from the sandbox memory pool.
4. Install permission guard on the region using `imm16` flags.
5. Write sandbox handle (opaque u32) to `rd`.
6. Register the region in the agent's sandbox region table.
7. Consume memory from the agent's `ResourceMonitor`.

**Error conditions → HALT_ERR:**
- `rs1` value exceeds remaining memory budget
- Agent has exceeded `max_regions` limit (256 default)
- Permission flags are invalid (reserved bits set)

**Example:**
```asm
; Allocate 1024-byte read-write sandbox region
MOVI R1, 1024        ; R1 = size in bytes
MOVI16 R0, 0         ; R0 will receive handle
SANDBOX_ALLOC R0, R1, 0x0003  ; perms = READ | WRITE
; R0 now contains sandbox handle
```

### 3.3 Permission Flags (imm16)

```
Bit 0:  PERM_READ     (0x0001) — Memory reads allowed
Bit 1:  PERM_WRITE    (0x0002) — Memory writes allowed
Bit 2:  PERM_EXEC     (0x0004) — Instruction fetch allowed (code regions)
Bit 3:  PERM_NOACCESS (0x0008) — Region exists but is inaccessible (guard page)
Bits 4-15: Reserved (must be zero, else HALT_ERR)
```

Common combinations:
- `0x0000` — No access (allocated but inaccessible)
- `0x0001` — Read-only data
- `0x0003` — Read-write data (default for data regions)
- `0x0005` — Read-execute (code regions: readable and executable, not writable — W^X)
- `0x0007` — Read-write-execute (dangerous, requires ADMIN capability)
- `0x0008` — Guard page (traps on any access, for boundary detection)

### 3.4 SANDBOX_FREE (0xED, Format F)

**Encoding:** `[0xED][rd][imm16hi][imm16lo]` (4 bytes)

| Field | Width | Description |
|-------|-------|-------------|
| opcode | 8 bits | 0xED |
| rd | 8 bits | Register containing sandbox handle to free |
| imm16 | 16 bits (LE) | Reserved, must be 0x0000 |

**Semantics:**
1. Read sandbox handle from `rd`.
2. Validate handle exists in the current agent's sandbox region table.
3. Zero-fill the region memory (prevent information leakage).
4. Remove the region from the region table.
5. Release memory back to the agent's `ResourceMonitor` budget.
6. Invalidate all tags associated with this region.

**Error conditions → HALT_ERR:**
- Handle in `rd` is not a valid sandbox handle for this agent
- Handle belongs to a different agent (cross-agent free denied)
- `imm16` is non-zero (reserved for future use)

**Example:**
```asm
; Free a previously allocated sandbox region
SANDBOX_FREE R0, 0x0000  ; Free the region whose handle is in R0
```

### 3.5 Memory Access Enforcement

After a sandbox region is allocated, ALL memory operations (LOAD, STORE, LOADOFF, STOREOFF, COPY, FILL, VLOAD, VSTORE) are checked against the sandbox region table:

1. Compute the effective address (`base + offset`).
2. Look up the address in the sandbox region table (binary search on sorted region ranges).
3. If the address falls within a sandboxed region:
   - Check the operation's required permission against the region's permission flags.
   - LOAD requires `PERM_READ`.
   - STORE requires `PERM_WRITE`.
   - Instruction fetch requires `PERM_EXEC`.
   - If permission denied → `HALT_ERR` with `SEC_ERR_SANDBOX_PERM`.
4. If the address does NOT fall within any sandboxed region:
   - The access is against "global" memory (non-sandboxed).
   - If the agent has `Permission.MEMORY_ALLOC` capability, access is allowed.
   - Otherwise → `HALT_ERR` with `SEC_ERR_SANDBOX_OUT_OF_RANGE`.

### 3.6 Interaction with Existing Opcodes

The existing `MALLOC` (0xD7) and `FREE` (0xD8) opcodes allocate from the global heap without sandbox protection. They remain available for backward compatibility but are **deprecated for multi-agent code**. The `MPROT` (0xD9) opcode changes permissions on existing allocations and can be used to sandbox regions created by `MALLOC`.

Recommended migration path:
- `MALLOC` + `MPROT` → `SANDBOX_ALLOC` (single operation, atomic)
- `FREE` → `SANDBOX_FREE` (includes zeroing)

---

## 4. Capability Enforcement

### 4.1 Design Decision: Interpreter-Level, Not ISA Opcodes

**Rationale:** Capability enforcement is a runtime policy decision, not a program instruction. Agents should not be able to execute "capability check" instructions — the interpreter enforces capabilities transparently before dispatching privileged opcodes. This prevents:

- Capability-check-skipping attacks (an agent simply not executing the check)
- Confused deputy problems (an agent performing a check for a different operation)
- Capability escalation through crafted bytecode

The capability system defined in `capabilities.py` (`CapabilityToken`, `CapabilityRegistry`) already provides the cryptographic foundation. This section specifies how the interpreter wires those checks into the dispatch loop.

### 4.2 CAP_INVOKE: Capability-Gated Dispatch

`CAP_INVOKE` is not an opcode. It is an interpreter dispatch-layer check that runs **before** any privileged opcode executes.

#### 4.2.1 Privileged Opcode Set

The following opcodes require capability checks at dispatch time:

| Category | Opcodes | Required Capability |
|----------|---------|-------------------|
| **A2A Communication** | TELL (0x50), ASK (0x51), DELEG (0x52), BCAST (0x53) | `Permission.A2A_TELL`, `.A2A_ASK`, `.A2A_DELEGATE` |
| **A2A Acceptance** | ACCEPT (0x54), DECLINE (0x55) | `Permission.A2A_DELEGATE` |
| **A2A Reporting** | REPORT (0x56), MERGE (0x57) | `Permission.A2A_TELL` |
| **Agent Lifecycle** | FORK (0x58), JOIN (0x59) | `Permission.ADMIN` |
| **Signaling** | SIGNAL (0x5A), AWAIT (0x5B) | `Permission.NETWORK` |
| **Trust Modification** | TRUST (0x5C) | `Permission.ADMIN` |
| **Fleet Discovery** | DISCOV (0x5D), STATUS (0x5E) | `Permission.NETWORK` |
| **Sensor Access** | SENSE (0x80), SAMPLE (0x82) | `Permission.IO_SENSOR` |
| **Actuator Access** | ACTUATE (0x81), PWM (0x8A), GPIO (0x8B) | `Permission.IO_ACTUATOR` |
| **Hardware I/O** | I2C (0x8C), SPI (0x8D), UART (0x8E), CANBUS (0x8F) | `Permission.IO_SENSOR` \| `Permission.IO_ACTUATOR` |
| **Memory Allocation** | MALLOC (0xD7), SANDBOX_ALLOC (0xDF) | `Permission.MEMORY_ALLOC` |
| **System Control** | RESET (0x06), WDOG (0xF8) | `Permission.ADMIN` |

#### 4.2.2 Dispatch Flow

```
fetch_next_instruction()
  decode_opcode()
  if opcode in PRIVILEGED_SET:
    required_perm = CAPABILITY_MAP[opcode]
    agent_sandbox = get_current_sandbox(agent_id)
    if not agent_sandbox.check_permission(resource=opcode_name, permission=required_perm):
      set_flag(FLAG_SEC_VIOLATION)
      set_flag(FLAG_CAP_MISSING)
      trap(HALT_ERR)  # 0xF0
      return
  dispatch(opcode)
```

#### 4.2.3 Capability Lifecycle

Capabilities are managed through the existing `CapabilityRegistry` API:

**CAP_GRANT** (runtime API, not an opcode):
```python
# Runtime grants capability to an agent
sandbox = sandbox_manager.get_sandbox(agent_id)
token = sandbox.grant_capability(
    resource="TELL",          # opcode name or resource name
    permissions=Permission.A2A_TELL,
    ttl=3600.0                # 1 hour
)
```

**CAP_REVOKE** (runtime API, not an opcode):
```python
# Runtime revokes a capability
tokens = sandbox.capabilities.list_for_agent(agent_id)
for t in tokens:
    if t.resource == "TELL":
        sandbox.capabilities.revoke(t)
```

**Key property:** Revocation is immediate. Once a token is removed from the `CapabilityRegistry._tokens` dict, any subsequent `check()` returns `False`. There is no caching of capability results at the dispatch level — every privileged opcode execution performs a fresh registry lookup.

#### 4.2.4 Capability Inheritance for FORK

When an agent executes `FORK` (0x58) to spawn a child agent:

1. The child receives a **copy** of the parent's capability set.
2. All copied capabilities have a **reduced TTL** (halved, minimum 60 seconds).
3. The child cannot receive capabilities the parent doesn't have (no privilege escalation).
4. The parent's capabilities are unaffected by the fork.

#### 4.2.5 Capability Delegation for DELEG

When agent A delegates a task to agent B via `DELEG` (0x52):

1. Agent A's `Permission.A2A_DELEGATE` is checked.
2. Agent A may optionally include a **delegation token** — a derived capability with a subset of permissions (using `CapabilityToken.derive()`).
3. Agent B receives the delegation token and may use it for the duration of the delegated task.
4. When agent B executes `REPORT` (0x56) back to A, the delegation token is automatically revoked.

### 4.3 Security Flag Bits

The interpreter maintains a security flags register. On capability violation:

```
FLAG_SEC_VIOLATION  (bit 7) — Set on any security violation
FLAG_CAP_MISSING    (bit 6) — Capability token not found or expired
FLAG_SANDBOX_PERM   (bit 5) — Sandbox permission violation
FLAG_TAG_VIOLATION  (bit 4) — Memory tag mismatch
FLAG_TRUST_POISON   (bit 3) — NaN/Inf confidence detected
FLAG_VERIFY_FAILED  (bit 2) — Bytecode verification failure
```

These flags are readable by the `HALT_ERR` (0xF0) handler for diagnostic reporting. The flags register is **write-clear only** — agents cannot set security flags, only the interpreter can.

---

## 5. Memory Tagging

### 5.1 Overview

Memory tagging associates ownership metadata with memory regions. This prevents cross-agent memory access without explicit sharing — even when two agents have valid sandbox handles that happen to overlap.

### 5.2 Tag Structure

Each tag is a 128-bit value encoding:

```
Bits 0-31:   owner_agent_id  (u32, hashed from agent string ID)
Bits 32-63:  region_handle   (u32, matches SANDBOX_ALLOC handle)
Bits 64-79:  tag_type        (u16, see 5.3)
Bits 80-95:  access_group    (u16, for shared memory groups)
Bits 96-127: tag_nonce       (u32, random per-allocation nonce)
```

The tag is stored in the interpreter's tag table, keyed by `(owner_agent_id, region_handle)`. Tags are NOT stored in agent-accessible memory — they exist only in the interpreter's internal metadata.

### 5.3 Tag Types (imm16 for TAG_ALLOC)

```
0x0000: TAG_PRIVATE    — Only the owner agent can access
0x0001: TAG_READONLY   — Owner reads/writes, others read-only
0x0002: TAG_SHARED     — Owner reads/writes, agents in access_group read/write
0x0003: TAG_REVOCABLE  — Like SHARED, but owner can revoke access
0x0004: TAG_TRANSFER   — Ownership can be transferred (required for TAG_TRANSFER opcode)
0x0005-0xFFFF: Reserved
```

### 5.4 TAG_ALLOC (0xEE, Format F)

**Encoding:** `[0xEE][rd][imm16hi][imm16lo]` (4 bytes)

| Field | Width | Description |
|-------|-------|-------------|
| opcode | 8 bits | 0xEE |
| rd | 8 bits | Register containing sandbox region handle |
| imm16 | 16 bits (LE) | Tag type (see 5.3) |

**Semantics:**
1. Read sandbox handle from `rd`.
2. Validate handle exists in the current agent's region table.
3. Create a tag entry: owner = current agent, region = handle, type = imm16.
4. Store the tag in the interpreter's tag table.
5. Set the `access_group` to a new group containing only the current agent.

**Error conditions → HALT_ERR:**
- Handle in `rd` is not a valid sandbox handle for this agent
- Tag type is reserved (0x0005+)
- Region already has a tag (use TAG_TRANSFER to reassign)

### 5.5 TAG_TRANSFER (0xEF, Format F)

**Encoding:** `[0xEF][rd][imm16hi][imm16lo]` (4 bytes)

| Field | Width | Description |
|-------|-------|-------------|
| opcode | 8 bits | 0xEF |
| rd | 8 bits | Register containing the tag's region handle |
| imm16 | 16 bits (LE) | Target agent ID (lower 16 bits of agent hash) |

**Semantics:**
1. Read region handle from `rd`.
2. Look up the tag for this region in the current agent's ownership.
3. Verify the tag type allows transfer (`TAG_TRANSFER` or `TAG_REVOCABLE`).
4. Verify the current agent is the tag owner.
5. Change the tag's `owner_agent_id` to the target agent (from `imm16`).
6. Add the target agent to the `access_group` (so both agents can access).
7. Update the `tag_nonce` (invalidate any cached permission decisions).

**Error conditions → HALT_ERR:**
- No tag exists for the region
- Current agent is not the tag owner
- Tag type does not permit transfer
- Target agent ID is 0 (invalid)

**Example:**
```asm
; Agent A allocates a shared region and transfers to Agent B
MOVI R1, 512         ; 512 bytes
SANDBOX_ALLOC R0, R1, 0x0003  ; R0 = handle, READ|WRITE
TAG_ALLOC R0, 0x0004        ; TAG_TRANSFER type — allows ownership transfer
; ... store data in the sandboxed region ...
MOVI16 R2, 0xBEEF    ; Target agent ID (lower 16 bits)
TAG_TRANSFER R0, 0xBEEF     ; Transfer ownership to agent 0xBEEF
```

### 5.6 TAG_CHECK (0xFB, Format A)

**Encoding:** `[0xFB]` (1 byte)

**Semantics:**
1. Read the value in R0 as a memory address or region handle.
2. Determine which sandbox region (if any) the address belongs to.
3. Look up the tag for that region.
4. Verify the current agent has access (is owner or in access_group).
5. If verification fails → `HALT_ERR` with `SEC_ERR_TAG_VIOLATION`.
6. If verification succeeds → no operation (NOP semantics).

**Use case:** Explicit assertion before sensitive operations. The interpreter also performs implicit tag checks on every LOAD/STORE (see 5.7).

**Error conditions → HALT_ERR:**
- R0 does not point to a valid sandboxed region
- Region has no tag
- Current agent is not the owner and not in the access_group

### 5.7 Implicit Tag Enforcement

In addition to explicit `TAG_CHECK`, the interpreter enforces tags on every memory operation:

```
for each LOAD/STORE/LOADOFF/STOREOF/COPY/FILL instruction:
  effective_addr = compute_address()
  region = sandbox_table.lookup(effective_addr)
  if region and region.has_tag():
    tag = tag_table.lookup(region.handle)
    if not tag.allows_access(current_agent, operation_type):
      set_flag(FLAG_TAG_VIOLATION)
      trap(HALT_ERR)
```

This implicit check is ALWAYS enabled. It cannot be disabled by the agent. The only way to access another agent's tagged memory is through explicit `TAG_TRANSFER`.

### 5.8 Cross-Agent Memory Sharing Protocol

```
Agent A                          Agent B
--------                         --------
SANDBOX_ALLOC R0, R1, 0x0003    (region created)
TAG_ALLOC R0, 0x0002            (TAG_SHARED, access_group = {A})
  |                              |
  |-- TELL B, region_handle ---->|
  |                              |
  |<--- ACCEPT ------------------|
  |                              |
  |   (interpreter adds B to    |
  |    A's region access_group)  |
  |                              |
  |<--- LOAD from region --------|  (allowed: B is in access_group)
```

Note: The TELL/ACCEPT handshake for sharing is handled at the interpreter level. When Agent B sends ACCEPT for a shared region, the interpreter adds Agent B to the region's access_group. This is not an ISA feature — it's part of the A2A protocol layer.

---

## 6. Bytecode Verification Pipeline

### 6.1 Overview (Fixes Issue #15)

The current interpreter executes any bytecode without validation. This is the most critical security vulnerability: a malicious or buggy agent can send arbitrary bytecode that corrupts memory, escapes sandbox boundaries, or executes privileged operations.

The verification pipeline runs in four stages, in order. A failure at any stage prevents execution and traps to `HALT_ERR`.

### 6.2 When Verification Runs

| Bytecode Source | Verification Required | Stage |
|----------------|----------------------|-------|
| Local (same agent generated) | Optional (optimization builds only) | Full pipeline |
| A2A received (from another agent) | **MANDATORY** | Full pipeline |
| A2A received + signed | **MANDATORY** | Full pipeline + signature check |
| Loaded from persistent storage | **MANDATORY** | Full pipeline |

**Rule:** Any bytecode not generated by the currently executing agent MUST pass full verification before a single instruction executes. There are no exceptions.

### 6.3 Stage 1: Structural Verification

Validates the raw byte stream is well-formed according to the converged ISA format spec.

```
structural_verify(bytecode: bytes) -> VerifyResult:
  pc = 0
  while pc < len(bytecode):
    opcode = bytecode[pc]
    if opcode is reserved and bytecode is not from trusted source:
      FAIL("reserved opcode at offset {pc}")
    fmt = FORMAT_FOR_OPCODE[opcode]
    expected_size = FMT_SIZES[fmt]
    if pc + expected_size > len(bytecode):
      FAIL("truncated instruction at offset {pc}: "
           "opcode 0x{opcode:02X} ({fmt}) needs {expected_size} bytes, "
           "only {len(bytecode) - pc} available")
    pc += expected_size
  if pc != len(bytecode):
    FAIL("trailing bytes after last instruction: {len(bytecode) - pc} bytes")
  PASS()
```

**Checks:**
- Every opcode maps to a known format (A through G).
- Every instruction has enough bytes for its format.
- No trailing bytes after the last complete instruction.
- Reserved opcodes are rejected unless from a trusted source.

**Complexity:** O(n) where n = bytecode length.

### 6.4 Stage 2: Register Verification

Validates that all register operands reference valid registers.

```
register_verify(bytecode: bytes) -> VerifyResult:
  pc = 0
  while pc < len(bytecode):
    opcode = bytecode[pc]
    fmt = FORMAT_FOR_OPCODE[opcode]
    if fmt in ('B', 'D', 'E', 'F', 'G'):
      rd = bytecode[pc + 1]
      if rd >= NUM_REGISTERS:
        FAIL("invalid register rd={rd} at offset {pc}")
    if fmt in ('E', 'G'):
      rs1 = bytecode[pc + 2]
      if rs1 >= NUM_REGISTERS:
        FAIL("invalid register rs1={rs1} at offset {pc}")
      rs2 = bytecode[pc + 3]
      if rs2 >= NUM_REGISTERS:
        FAIL("invalid register rs2={rs2} at offset {pc}")
    if fmt == 'G':
      rs1 = bytecode[pc + 2]
      if rs1 >= NUM_REGISTERS:
        FAIL("invalid register rs1={rs1} at offset {pc}")
    pc += FMT_SIZES[fmt]
  PASS()
```

**Checks:**
- All `rd`, `rs1`, `rs2` fields are in range `[0, NUM_REGISTERS)`.
- Default `NUM_REGISTERS = 16` (r0–r15). R15 is reserved as scratch for pseudo-instruction expansion.

### 6.5 Stage 3: Control-Flow Verification

Validates that all control flow targets are within the bytecode bounds and targets valid instruction boundaries.

```
control_flow_verify(bytecode: bytes) -> VerifyResult:
  # Build instruction boundary table
  boundaries = set()
  pc = 0
  while pc < len(bytecode):
    boundaries.add(pc)
    opcode = bytecode[pc]
    fmt = FORMAT_FOR_OPCODE[opcode]
    pc += FMT_SIZES[fmt]

  # Verify all jump/call targets
  pc = 0
  while pc < len(bytecode):
    opcode = bytecode[pc]
    fmt = FORMAT_FOR_OPCODE[opcode]
    if opcode in (JMP, JAL, CALL, CALLL, TAIL, JMPL, JALL):
      target = compute_jump_target(bytecode, pc, opcode)
      if target not in boundaries:
        FAIL("jump target 0x{target:04X} at offset {pc} "
             "does not land on an instruction boundary")
      if target >= len(bytecode):
        FAIL("jump target 0x{target:04X} at offset {pc} "
             "is beyond bytecode length {len(bytecode)}")
    pc += FMT_SIZES[fmt]
  PASS()
```

**Checks:**
- All `JMP`, `JAL`, `CALL`, `JMPL`, `JALL`, `CALLL`, `TAIL` targets are instruction-aligned.
- No jump targets outside the bytecode buffer.
- Conditional jumps (`JZ`, `JNZ`, `JLT`, `JGT`) with register-based offsets are validated: the register value is checked at runtime (cannot be statically verified), but the maximum possible offset is bounded to the bytecode length.

**Limitation:** Register-based conditional jumps (e.g., `JZ rd, rs1`) cannot be fully verified statically because `rs1` value is runtime-dependent. The verifier sets a runtime guard: if `rs1` causes a jump outside bytecode bounds → `HALT_ERR`.

### 6.6 Stage 4: Security Verification

Validates that the bytecode does not contain opcodes the receiving agent is not authorized to execute.

```
security_verify(bytecode: bytes, agent_caps: CapabilityRegistry) -> VerifyResult:
  pc = 0
  while pc < len(bytecode):
    opcode = bytecode[pc]
    if opcode in PRIVILEGED_OPCODE_SET:
      required_perm = CAPABILITY_MAP[opcode]
      if not agent_has_permission(agent_caps, opcode, required_perm):
        FAIL("opcode 0x{opcode:02X} ({MNEMONIC[opcode]}) at offset {pc} "
             "requires capability {required_perm.name} which agent does not possess")
    pc += FMT_SIZES[FORMAT_FOR_OPCODE[opcode]]
  PASS()
```

**Checks:**
- The bytecode does not contain any privileged opcode the receiving agent lacks capability for.
- If the bytecode contains `FORK`, the agent must have `Permission.ADMIN`.
- If the bytecode contains `TELL`/`ASK`, the agent must have the corresponding A2A permission.

**Design choice:** This stage rejects bytecode that CONTAINS unauthorized opcodes, even if those opcodes are on unreachable code paths. This is intentional — it prevents Trojan code hidden behind dead branches.

### 6.7 Verification Result

```python
@dataclass
class VerifyResult:
    passed: bool
    stage: str          # "structural" | "register" | "control_flow" | "security"
    error_offset: int   # Byte offset of the first error (-1 if passed)
    error_message: str  # Human-readable diagnostic
    bytecode_hash: str  # SHA-256 of the verified bytecode
    verified_at: float  # Timestamp
```

On verification failure:
1. Set `FLAG_VERIFY_FAILED` in security flags.
2. Trap to `HALT_ERR` (0xF0).
3. The `HALT_ERR` handler can read `VerifyResult` from a dedicated interpreter register (`SEC_DIAG` register) for diagnostic reporting.

### 6.8 Performance

Verification is O(n) in bytecode length. For typical FLUX programs (< 10KB), all four stages complete in < 1ms on modern hardware. Verification runs once before execution — it is NOT in the execution hot path.

Caching: Verified bytecode is tagged with its SHA-256 hash. If the same bytecode is received again (same hash), cached verification results are used. Cache entries expire after the capability TTL (default 1 hour).

---

## 7. Trust Poisoning Prevention

### 7.1 Overview (Fixes Issue #17)

Confidence values in FLUX represent trust levels, measurement certainty, and decision quality. If these values can be poisoned with NaN, Infinity, or out-of-range values, downstream agents make incorrect trust decisions.

### 7.2 Confidence Register Invariants

The interpreter enforces the following invariants on ALL 16 confidence registers (c0–c15):

| Invariant | Enforcement |
|-----------|-------------|
| Values are finite | NaN, +Inf, -Inf → silently replaced with 0.0 |
| Values are in [0.0, 1.0] | Values < 0.0 → 0.0, values > 1.0 → 1.0 |
| Default value is 0.0 | All confidence registers initialized to 0.0 |
| Overflow clamped | Multiplication results > 1.0 → 1.0 |

### 7.3 Interpreter-Level Enforcement

Every write to a confidence register passes through a sanitization function:

```python
def sanitize_confidence(value: float) -> float:
    """Clamp confidence to [0.0, 1.0]. NaN/Inf → 0.0."""
    import math
    if math.isnan(value) or math.isinf(value):
        return 0.0  # No confidence — safe default
    return max(0.0, min(1.0, value))
```

This function is called:
- By `CONF_ST` (0x0F) when storing to confidence registers.
- By all `C_*` confidence-aware opcodes (0x60–0x6F) when computing result confidence.
- By `CONF_LD` (0x0E) when loading from confidence registers (defensive — output is already clamped but this catches corruption).
- By `TRUST` (0x5C) when setting inter-agent trust levels.

**Performance note:** `math.isnan()` and `math.isinf()` are single CPU instructions on modern hardware (x86 `ucomisd` + flags check). The performance impact is negligible.

### 7.4 CONF_CLAMP (0xFA, Format A)

**Encoding:** `[0xFA]` (1 byte)

**Semantics:**
1. Iterate over all 16 confidence registers (c0–c15).
2. Apply `sanitize_confidence()` to each register.
3. No output — this is a side-effect-only instruction.
4. Set a "confidence clamped" flag for diagnostic purposes.

**Use case:** Explicit normalization checkpoint after a sequence of confidence computations that might have accumulated floating-point drift. This is a defense-in-depth measure — the interpreter already clamps on every write, but `CONF_CLAMP` provides an explicit audit point.

**When to use:**
- After receiving A2A confidence values from another agent (before using them locally).
- After a long chain of `C_MUL` / `C_DIV` operations that might accumulate floating-point error.
- Before emitting `REPORT` with confidence metadata.

**Example:**
```asm
; Agent receives a confidence value and uses it safely
; (assuming R1 contains a received confidence value)
CONF_ST R1            ; Store to confidence register
CONF_CLAMP            ; Explicitly normalize all confidence registers
; All confidence registers are now guaranteed in [0.0, 1.0]
```

### 7.5 Confidence Propagation Security

The confidence-aware opcodes (0x60–0x6F) are the primary source of confidence values. Their propagation rules are security-relevant:

| Opcode | Confidence Rule | Security Property |
|--------|----------------|-------------------|
| `C_ADD` | `crd = min(crs1, crs2)` | Confidence never increases — safe |
| `C_SUB` | `crd = min(crs1, crs2)` | Same as C_ADD — safe |
| `C_MUL` | `crd = crs1 * crs2` | Can only decrease (both ≤ 1.0) — safe |
| `C_DIV` | `crd = crs1 * crs2 * (1-ε)` | Extra decay factor — safe |
| `C_MERGE` | `crd = weighted_avg(crs1, crs2)` | Cannot exceed inputs — safe |
| `C_BOOST` | `crd = min(1.0, crs * factor)` | Capped at 1.0 — safe |
| `C_DECAY` | `crd = crs * factor` | Can only decrease — safe |

**Key property:** No confidence-aware opcode can produce a value > 1.0 from inputs in [0.0, 1.0], because the propagation rules are monotonic and bounded. The `sanitize_confidence()` clamp is a defense-in-depth measure for:
- Direct `CONF_ST` writes from agent-computed values.
- Trust value updates via `TRUST` (0x5C).
- A2A-received confidence values that bypass the confidence opcodes.

### 7.6 NaN Injection Attack Vectors (Prevented)

| Attack Vector | Prevention |
|--------------|------------|
| `0.0 / 0.0` via `FDIV` into confidence register | `CONF_ST` sanitizes before writing |
| `sqrt(-1.0)` via `FSQRT` into confidence register | `CONF_ST` sanitizes before writing |
| Overflow: `1e308 * 1e308` via `FMUL` | `CONF_ST` clamps to 1.0 |
| Direct NaN in A2A message payload | Interpreter sanitizes all received confidence values |
| Accumulated floating-point drift in long chains | `CONF_CLAMP` provides explicit normalization |

---

## 8. Security Conformance Vectors

### 8.1 Overview

The following 15 test vectors validate all security primitives defined in this specification. Each vector specifies input bytecode, expected behavior, and the security property it validates.

### 8.2 Vector Format

```python
@dataclass
class SecurityTestVector:
    id: str                    # "SEC-001" through "SEC-015"
    name: str                  # Human-readable name
    category: str              # "sandbox" | "capability" | "tag" | "trust" | "verify"
    bytecode: bytes            # Input bytecode (or None for API-level tests)
    preconditions: dict        # Required state before execution
    expected_result: str       # "HALT_ERR" | "PASS" | "SEC_ERR_*"
    expected_flags: list[str]  # Security flags that should be set
    description: str           # What this vector tests
```

### 8.3 Sandbox Vectors

#### SEC-001: Basic Sandbox Allocation

```python
{
    "id": "SEC-001",
    "name": "Basic sandbox allocation and access",
    "category": "sandbox",
    "bytecode": bytes([
        0x18, 0x01, 0x40,    # MOVI R1, 64       (allocate 64 bytes)
        0xDF, 0x00, 0x01, 0x03, 0x00,  # SANDBOX_ALLOC R0, R1, 0x0003 (READ|WRITE)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "MEMORY_ALLOC", "memory_budget": 1024},
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "Agent with MEMORY_ALLOC capability can create a sandbox region. "
                   "R0 should contain a valid handle after execution."
}
```

#### SEC-002: Sandbox Permission Violation (Write to Read-Only)

```python
{
    "id": "SEC-002",
    "name": "Write to read-only sandbox region",
    "category": "sandbox",
    "bytecode": bytes([
        0x18, 0x01, 0x40,    # MOVI R1, 64       (allocate 64 bytes)
        0xDF, 0x00, 0x01, 0x01, 0x00,  # SANDBOX_ALLOC R0, R1, 0x0001 (READ only)
        0x18, 0x02, 0x2A,    # MOVI R2, 42       (value to store)
        0x38, 0x02, 0x00, 0x01,  # STORE R2, R0, R1  (write to read-only region)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "MEMORY_ALLOC"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_SANDBOX_PERM"],
    "description": "Writing to a read-only sandbox region traps with HALT_ERR. "
                   "FLAG_SANDBOX_PERM is set."
}
```

#### SEC-003: Sandbox Out-of-Range Access

```python
{
    "id": "SEC-003",
    "name": "Access outside sandboxed region bounds",
    "category": "sandbox",
    "bytecode": bytes([
        0x18, 0x01, 0x10,    # MOVI R1, 16       (allocate 16 bytes)
        0xDF, 0x00, 0x01, 0x03, 0x00,  # SANDBOX_ALLOC R0, R1, 0x0003 (READ|WRITE)
        0x18, 0x02, 0x00,    # MOVI R2, 0        (base = sandbox start)
        0x18, 0x03, 0xFF,    # MOVI R3, 255      (offset = 255, way past 16 bytes)
        0x38, 0x04, 0x02, 0x03,  # LOAD R4, R2, R3  (read 255 bytes past start)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "MEMORY_ALLOC", "sandbox_strict_bounds": True},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_SANDBOX_PERM"],
    "description": "Reading beyond sandbox region boundary traps with HALT_ERR."
}
```

#### SEC-004: Sandbox Guard Page Trap

```python
{
    "id": "SEC-004",
    "name": "Guard page triggers on any access",
    "category": "sandbox",
    "bytecode": bytes([
        0x18, 0x01, 0x01,    # MOVI R1, 1        (allocate 1 byte)
        0xDF, 0x00, 0x01, 0x08, 0x00,  # SANDBOX_ALLOC R0, R1, 0x0008 (NOACCESS guard)
        0x38, 0x02, 0x00, 0x00,  # LOAD R2, R0, R0  (try to read guard page)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "MEMORY_ALLOC"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_SANDBOX_PERM"],
    "description": "Guard page (PERM_NOACCESS) traps on any read or write."
}
```

### 8.4 Capability Vectors

#### SEC-005: Missing Capability Blocks TELL

```python
{
    "id": "SEC-005",
    "name": "TELL without A2A_TELL capability",
    "category": "capability",
    "bytecode": bytes([
        0x18, 0x01, 0x2A,    # MOVI R1, 42       (message)
        0x18, 0x02, 0x01,    # MOVI R2, 1        (target agent)
        0x50, 0x00, 0x02, 0x01,  # TELL R0, R2, R1 (send message)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "NONE"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_CAP_MISSING"],
    "description": "Executing TELL without A2A_TELL capability traps immediately. "
                   "The instruction never actually sends a message."
}
```

#### SEC-006: Capability Grants Allow Privileged Ops

```python
{
    "id": "SEC-006",
    "name": "TELL succeeds with proper capability",
    "category": "capability",
    "bytecode": bytes([
        0x18, 0x01, 0x2A,    # MOVI R1, 42       (message)
        0x18, 0x02, 0x01,    # MOVI R2, 1        (target agent)
        0x50, 0x00, 0x02, 0x01,  # TELL R0, R2, R1 (send message)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "A2A_TELL"},
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "TELL succeeds when agent has A2A_TELL capability. "
                   "No security flags are set."
}
```

#### SEC-007: Expired Capability Traps

```python
{
    "id": "SEC-007",
    "name": "Expired capability is treated as missing",
    "category": "capability",
    "bytecode": bytes([
        0x18, 0x01, 0x2A,    # MOVI R1, 42
        0x18, 0x02, 0x01,    # MOVI R2, 1
        0x50, 0x00, 0x02, 0x01,  # TELL R0, R2, R1
        0x00,                 # HALT
    ]),
    "preconditions": {
        "agent_has_cap": "A2A_TELL",
        "cap_ttl": -1.0       # Already expired
    },
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_CAP_MISSING"],
    "description": "An expired capability token is equivalent to no capability. "
                   "The registry check returns False for expired tokens."
}
```

#### SEC-008: SENSE Requires IO_SENSOR Capability

```python
{
    "id": "SEC-008",
    "name": "SENSE without IO_SENSOR capability",
    "category": "capability",
    "bytecode": bytes([
        0x80, 0x00, 0x01, 0x02,  # SENSE R0, R1, R2 (read sensor)
        0x00,                 # HALT
    ]),
    "preconditions": {"agent_has_cap": "NONE"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_CAP_MISSING"],
    "description": "Hardware sensor access requires IO_SENSOR capability."
}
```

### 8.5 Memory Tag Vectors

#### SEC-009: Tag Prevents Cross-Agent Access

```python
{
    "id": "SEC-009",
    "name": "Cross-agent read of private tagged region",
    "category": "tag",
    "bytecode": bytes([
        0x38, 0x02, 0x03, 0x04,  # LOAD R2, R3, R4 (read from region)
        0x00,                 # HALT
    ]),
    "preconditions": {
        "agent_has_cap": "MEMORY_ALLOC",
        "region_owner": "agent_A",
        "current_agent": "agent_B",
        "tag_type": "TAG_PRIVATE",
        "region_exists": True
    },
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_SEC_VIOLATION", "FLAG_TAG_VIOLATION"],
    "description": "Agent B cannot read Agent A's TAG_PRIVATE region, "
                   "even if Agent B has a valid memory address."
}
```

#### SEC-010: TAG_TRANSFER Enables Access

```python
{
    "id": "SEC-010",
    "name": "TAG_TRANSFER allows cross-agent access",
    "category": "tag",
    "bytecode": bytes([
        0xEF, 0x00, 0xB0, 0x00,  # TAG_TRANSFER R0, 0x00B0 (transfer to agent B)
        0x38, 0x02, 0x03, 0x04,  # LOAD R2, R3, R4 (now allowed)
        0x00,                 # HALT
    ]),
    "preconditions": {
        "agent_has_cap": "MEMORY_ALLOC",
        "region_owner": "agent_A",
        "current_agent": "agent_A",
        "tag_type": "TAG_TRANSFER",
        "target_agent": "agent_B"
    },
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "After TAG_TRANSFER, the target agent can access the region. "
                   "Both agents are in the access_group."
}
```

#### SEC-011: TAG_CHECK Explicit Assertion

```python
{
    "id": "SEC-011",
    "name": "TAG_CHECK passes for owned region",
    "category": "tag",
    "bytecode": bytes([
        0xFB,                 # TAG_CHECK (verify R0 access)
        0x00,                 # HALT
    ]),
    "preconditions": {
        "current_agent": "agent_A",
        "R0_points_to": "agent_A_owned_tagged_region"
    },
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "TAG_CHECK succeeds when R0 points to the current agent's own tagged region."
}
```

### 8.6 Trust / Confidence Vectors

#### SEC-012: NaN Confidence Sanitized to 0.0

```python
{
    "id": "SEC-012",
    "name": "NaN confidence value is sanitized",
    "category": "trust",
    "bytecode": bytes([
        0x0F, 0x00,           # CONF_ST R0 (store R0 to confidence register)
        0xFA,                 # CONF_CLAMP
        0x00,                 # HALT
    ]),
    "preconditions": {
        "R0_value": float('nan'),  # NaN in general register
    },
    "expected_result": "PASS",
    "expected_flags": ["FLAG_TRUST_POISON"],  # Set during CONF_ST
    "description": "When NaN is stored to a confidence register, it is sanitized to 0.0. "
                   "FLAG_TRUST_POISON is set as a diagnostic indicator."
}
```

#### SEC-013: Inf Confidence Sanitized to 0.0

```python
{
    "id": "SEC-013",
    "name": "Infinity confidence value is sanitized",
    "category": "trust",
    "bytecode": bytes([
        0x0F, 0x00,           # CONF_ST R0
        0x00,                 # HALT
    ]),
    "preconditions": {
        "R0_value": float('inf'),
    },
    "expected_result": "PASS",
    "expected_flags": ["FLAG_TRUST_POISON"],
    "description": "Infinity confidence is sanitized to 0.0."
}
```

#### SEC-014: Confidence Clamped to [0.0, 1.0]

```python
{
    "id": "SEC-014",
    "name": "Out-of-range confidence is clamped",
    "category": "trust",
    "bytecode": bytes([
        0x0F, 0x00,           # CONF_ST R0 (store value to confidence register)
        0x0E, 0x01,           # CONF_LD R1 (load confidence register back)
        0x00,                 # HALT
    ]),
    "preconditions": {
        "R0_value": 1.5,      # Above 1.0
    },
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "Confidence value 1.5 is clamped to 1.0. After CONF_LD, R1 should be 1.0."
}
```

#### SEC-015: Negative Confidence Clamped to 0.0

```python
{
    "id": "SEC-015",
    "name": "Negative confidence is clamped to 0.0",
    "category": "trust",
    "bytecode": bytes([
        0x0F, 0x00,           # CONF_ST R0
        0x0E, 0x01,           # CONF_LD R1
        0x00,                 # HALT
    ]),
    "preconditions": {
        "R0_value": -0.5,
    },
    "expected_result": "PASS",
    "expected_flags": [],
    "description": "Confidence value -0.5 is clamped to 0.0."
}
```

### 8.7 Bytecode Verification Vectors

#### SEC-016: Truncated Instruction Rejected

```python
{
    "id": "SEC-016",
    "name": "Truncated Format E instruction rejected",
    "category": "verify",
    "bytecode": bytes([0x20, 0x00, 0x01]),  # ADD rd=0, rs1=1, rs2=TRUNCATED
    "preconditions": {"source": "a2a_received"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_VERIFY_FAILED"],
    "description": "A 3-byte Format E instruction (needs 4 bytes) is rejected "
                   "at structural verification stage."
}
```

#### SEC-017: Unauthorized Opcode in A2A Bytecode

```python
{
    "id": "SEC-017",
    "name": "A2A bytecode with SENSE opcode rejected for non-hardware agent",
    "category": "verify",
    "bytecode": bytes([
        0x80, 0x00, 0x01, 0x02,  # SENSE R0, R1, R2
        0x00,                 # HALT
    ]),
    "preconditions": {
        "source": "a2a_received",
        "agent_has_cap": "A2A_TELL",  # Has A2A but NOT IO_SENSOR
    },
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_VERIFY_FAILED"],
    "description": "A2A-received bytecode containing SENSE is rejected at security "
                   "verification stage because the receiving agent lacks IO_SENSOR."
}
```

#### SEC-018: Reserved Opcode Rejected in Untrusted Bytecode

```python
{
    "id": "SEC-018",
    "name": "Reserved opcode rejected in A2A bytecode",
    "category": "verify",
    "bytecode": bytes([
        0xFC,                 # Reserved opcode (Format A)
        0x00,                 # HALT
    ]),
    "preconditions": {"source": "a2a_received"},
    "expected_result": "HALT_ERR",
    "expected_flags": ["FLAG_VERIFY_FAILED"],
    "description": "Reserved opcodes (0xFC-0xFD) are rejected in A2A-received bytecode."
}
```

### 8.8 Vector Summary

| ID | Category | Property Tested | Expected |
|----|----------|----------------|----------|
| SEC-001 | sandbox | Basic allocation succeeds | PASS |
| SEC-002 | sandbox | Write to read-only region | HALT_ERR |
| SEC-003 | sandbox | Out-of-bounds access | HALT_ERR |
| SEC-004 | sandbox | Guard page trap | HALT_ERR |
| SEC-005 | capability | Missing A2A_TELL blocks TELL | HALT_ERR |
| SEC-006 | capability | Valid capability allows TELL | PASS |
| SEC-007 | capability | Expired capability denied | HALT_ERR |
| SEC-008 | capability | SENSE requires IO_SENSOR | HALT_ERR |
| SEC-009 | tag | Cross-agent private access denied | HALT_ERR |
| SEC-010 | tag | TAG_TRANSFER enables access | PASS |
| SEC-011 | tag | TAG_CHECK assertion passes | PASS |
| SEC-012 | trust | NaN → 0.0 | PASS + FLAG |
| SEC-013 | trust | Inf → 0.0 | PASS + FLAG |
| SEC-014 | trust | 1.5 → 1.0 (clamped) | PASS |
| SEC-015 | trust | -0.5 → 0.0 (clamped) | PASS |
| SEC-016 | verify | Truncated instruction | HALT_ERR |
| SEC-017 | verify | Unauthorized opcode in A2A | HALT_ERR |
| SEC-018 | verify | Reserved opcode rejected | HALT_ERR |

**Total: 18 conformance vectors** across 5 categories.

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1)

| Step | Task | Files | Depends On |
|------|------|-------|------------|
| 1.1 | Add 6 security opcodes to `isa_unified.py` | `isa_unified.py` | — |
| 1.2 | Implement `sanitize_confidence()` in interpreter | `unified_interpreter.py` | — |
| 1.3 | Wire confidence sanitization into `CONF_ST`, `C_*` ops | `unified_interpreter.py` | 1.2 |
| 1.4 | Implement `CONF_CLAMP` opcode | `unified_interpreter.py` | 1.2 |
| 1.5 | Add security flags register to VM state | `unified_interpreter.py` | — |
| 1.6 | Write SEC-012 through SEC-015 trust vectors as tests | `test_security.py` | 1.2-1.4 |

### Phase 2: Capability Wiring (Week 2)

| Step | Task | Files | Depends On |
|------|------|-------|------------|
| 2.1 | Build privilege dispatch table mapping opcodes → permissions | `security_dispatch.py` | 1.1 |
| 2.2 | Wire CAP_INVOKE checks into interpreter dispatch loop | `unified_interpreter.py` | 2.1 |
| 2.3 | Implement capability inheritance for FORK | `unified_interpreter.py` | 2.2 |
| 2.4 | Implement delegation tokens for DELEG | `capabilities.py` | 2.2 |
| 2.5 | Write SEC-005 through SEC-008 capability vectors | `test_security.py` | 2.2 |

### Phase 3: Sandbox & Tags (Week 3)

| Step | Task | Files | Depends On |
|------|------|-------|------------|
| 3.1 | Implement sandbox region table (sorted interval tree) | `sandbox.py` | — |
| 3.2 | Implement `SANDBOX_ALLOC` opcode | `unified_interpreter.py` | 3.1 |
| 3.3 | Implement `SANDBOX_FREE` opcode | `unified_interpreter.py` | 3.2 |
| 3.4 | Wire sandbox permission checks into LOAD/STORE | `unified_interpreter.py` | 3.1 |
| 3.5 | Implement tag table and ownership tracking | `memory_tags.py` (new) | — |
| 3.6 | Implement `TAG_ALLOC`, `TAG_TRANSFER`, `TAG_CHECK` | `unified_interpreter.py` | 3.5 |
| 3.7 | Wire implicit tag enforcement into memory ops | `unified_interpreter.py` | 3.5 |
| 3.8 | Write SEC-001 through SEC-011 sandbox/tag vectors | `test_security.py` | 3.4, 3.7 |

### Phase 4: Verification (Week 4)

| Step | Task | Files | Depends On |
|------|------|-------|------------|
| 4.1 | Implement structural verification | `bytecode_verifier.py` (new) | — |
| 4.2 | Implement register verification | `bytecode_verifier.py` | 4.1 |
| 4.3 | Implement control-flow verification | `bytecode_verifier.py` | 4.1 |
| 4.4 | Implement security verification | `bytecode_verifier.py` | 2.1 |
| 4.5 | Wire verification into A2A bytecode receive path | `unified_interpreter.py` | 4.1-4.4 |
| 4.6 | Add verification cache with SHA-256 keyed entries | `bytecode_verifier.py` | 4.1 |
| 4.7 | Write SEC-016 through SEC-018 verification vectors | `test_security.py` | 4.1-4.4 |

### Phase 5: Integration & C Runtime (Week 5-6)

| Step | Task | Files | Depends On |
|------|------|-------|------------|
| 5.1 | Port all security features to C VM (`flux_vm_unified.c`) | `c/flux_vm_unified.c` | Phase 1-4 |
| 5.2 | Run all 18 security vectors on both Python and C VMs | `run_security_conformance.sh` | 5.1 |
| 5.3 | Update conformance runner to include security vectors | `tools/conformance_runner.py` | 5.2 |
| 5.4 | Update fleet health dashboard with security conformance | `docs/fleet-health-dashboard.json` | 5.2 |

---

## Appendix A — Security Error Codes

When `HALT_ERR` (0xF0) is triggered by a security violation, the error code is stored in the diagnostic register. Error codes are in the range `0xE0-0xEF` (using the extended system range for diagnostic purposes):

| Code | Name | Description |
|------|------|-------------|
| `0xE0` | `SEC_ERR_SANDBOX_PERM` | Sandbox permission violation (read/write/exec denied) |
| `0xE1` | `SEC_ERR_SANDBOX_RANGE` | Memory access outside all sandbox regions |
| `0xE2` | `SEC_ERR_SANDBOX_ALLOC` | Sandbox allocation failed (budget/limit) |
| `0xE3` | `SEC_ERR_CAP_MISSING` | Required capability not found |
| `0xE4` | `SEC_ERR_CAP_EXPIRED` | Capability token has expired |
| `0xE5` | `SEC_ERR_TAG_VIOLATION` | Memory tag access denied (wrong owner/group) |
| `0xE6` | `SEC_ERR_TAG_INVALID` | Tag operation on untagged region |
| `0xE7` | `SEC_ERR_TAG_TRANSFER` | Tag transfer denied (not owner/wrong type) |
| `0xE8` | `SEC_ERR_TRUST_POISON` | NaN/Inf detected in confidence value |
| `0xE9` | `SEC_ERR_VERIFY_STRUCTURAL` | Bytecode structural verification failed |
| `0xEA` | `SEC_ERR_VERIFY_REGISTER` | Bytecode register verification failed |
| `0xEB` | `SEC_ERR_VERIFY_CONTROL_FLOW` | Bytecode control-flow verification failed |
| `0xEC` | `SEC_ERR_VERIFY_SECURITY` | Bytecode security verification failed |
| `0xED-0xEF` | Reserved | Future security error codes |

---

## Appendix B — Relationship to Existing Code

### B.1 Files Modified

| File | Change |
|------|--------|
| `isa_unified.py` | Add 6 security opcodes at reserved slots (0xDF, 0xED-0xEF, 0xFA-0xFB) |
| `capabilities.py` | Add delegation token derivation, TTL enforcement |
| `sandbox.py` | Add sandbox region table, permission enforcement, tag integration |
| `resource_limits.py` | No changes needed (already supports memory tracking) |

### B.2 Files Created

| File | Purpose |
|------|---------|
| `security/memory_tags.py` | Tag table, ownership tracking, access group management |
| `security/bytecode_verifier.py` | 4-stage verification pipeline |
| `security/security_dispatch.py` | Privilege dispatch table, CAP_INVOKE wiring |
| `tests/test_security.py` | 18 security conformance vectors |

### B.3 Issues Resolved

| Issue | Section | Fix |
|-------|---------|-----|
| #15 (zero bytecode verification) | Section 6 | 4-stage verification pipeline, mandatory for A2A bytecode |
| #16 (unenforced CAP opcodes) | Section 4 | Interpreter-level CAP_INVOKE before privileged dispatch |
| #17 (NaN trust poisoning) | Section 7 | `sanitize_confidence()` on all confidence writes, CONF_CLAMP opcode |

### B.4 Interaction with ISA Authority Document

This spec is consistent with the ISA Authority Document (ISA-AUTH-2026-001):
- Uses the converged ISA (`isa_unified.py`) as canonical
- Uses only reserved slots (no collision with existing opcodes)
- Follows the format-by-range convention (Format G at 0xDF, Format F at 0xED-0xEF, Format A at 0xFA-0xFB)
- HALT_ERR (0xF0) is the universal error trap (as documented in the Authority)
- The 46 collision analysis remains valid (no opcode addresses changed)
