# ISA v3 Escape Prefix Specification (ISA-002)

**Task ID:** 15b  
**Author:** Super Z (Cartographer)  
**Date:** 2026-04-12  
**Status:** DRAFT — Fleet Review Requested  
**Depends on:** ISA v2 unified spec (247 opcodes, isa_unified.py)  
**Tracks:** Oracle1 TASK-BOARD ISA-002 (CRITICAL PATH)

---

## 1. Motivation

The FLUX ISA v2 defines 247 opcodes across 256 slots (9 reserved). As the fleet
grows — JetsonClaw1 needs sensor/actuator ops, Babel needs linguistic primitives,
Quill needs vocabulary composition — the opcode space is effectively **exhausted**.

The escape prefix mechanism provides **unbounded extensibility** without consuming
base-ISA opcode slots. A single byte (0xFF, currently `ILLEGAL` in v2) opens a
new addressing dimension:

```
0xFF [ext_id] [sub_opcode] [operands...]
```

This gives each extension **256 sub-opcodes**, with **256 possible extensions**
— a total of 65,536 extension opcodes from a single escape prefix.

**Key insight** (from Kimi's round-table critique): "The escape prefix is the
key structural insight. It future-proofs the ISA against domains we haven't
imagined yet."

---

## 2. Encoding: Format H — Escape Prefix Extension

### 2.1 Byte Layout

```
Byte 0: 0xFF           (escape prefix — always this value)
Byte 1: ext_id         (extension identifier, 0x00-0xFF)
Byte 2: sub_opcode     (operation within extension, 0x00-0xFF)
Byte 3+: operands      (format determined by extension's sub-opcode map)
```

**Minimum instruction size:** 3 bytes (for zero-operand extension ops)  
**Maximum instruction size:** defined by each extension (typically ≤ 8 bytes)

### 2.2 Extension ID Allocation

| Range | Count | Type | Authority |
|-------|-------|------|-----------|
| 0x00 | 1 | NULL extension (NOP passthrough) | Reserved |
| 0x01-0x7F | 127 | Fleet-standard extensions | Oracle1 allocates |
| 0x80-0xEF | 112 | Experimental / vendor-specific | Self-assigned (register) |
| 0xF0-0xFF | 16 | Fleet-internal / meta-extensions | Oracle1 reserves |

**Allocation rules:**
- Fleet-standard IDs (0x01-0x7F): require Oracle1 approval, published in fleet
  extension registry, must have conformance vectors
- Experimental IDs (0x80-0xEF): self-assigned but must be registered in the
  fleet extension registry to avoid collisions; no conformance required
- Meta-extensions (0xF0-0xFF): reserved for VM introspection, debugging,
  hot-loading — defined in this spec

### 2.3 Extension ID Registry Format

Each registered extension has a manifest:

```json
{
  "ext_id": 0x01,
  "name": "EXT_BABEL",
  "version": "1.0.0",
  "status": "standard",
  "owner": "babel-vessel",
  "description": "Multilingual linguistic primitives for viewpoint-aware processing",
  "sub_opcode_count": 16,
  "sub_opcodes": [
    {
      "sub_opcode": 0x00,
      "mnemonic": "LANG_DETECT",
      "format": "H_E",  // Format E operands follow sub_opcode
      "operands": "rd, rs1, rs2",
      "description": "Detect language of text at mem[rs1], len rs2, lang_id -> rd"
    }
  ],
  "conformance_vectors": "ext_babel/conformance_vectors.json",
  "dependencies": [],
  "isa_min_version": "3.0"
}
```

### 2.4 Operand Format After Escape Prefix

After `0xFF [ext_id] [sub_opcode]`, operand bytes follow **one of two patterns**:

**Pattern A — Reuse base ISA format encoding:**
The extension's sub-opcode map declares which base format (A through G) to apply
for the remaining bytes. The VM reads operands exactly as it would for a base-ISA
opcode of that format.

```
0xFF 0x01 0x03 rd rs1 rs2    # EXT_BABEL.LANG_CLASSIFY, Format E operands
0xFF 0x02 0x0A rd imm16      # EXT_EDGE.SENSOR_CALIB, Format F operands
```

This is the **recommended pattern** because it reuses existing decode logic.

**Pattern B — Extension-defined variable encoding:**
The extension defines its own operand encoding in the manifest. The VM calls the
extension's decode handler. Used only when base formats are insufficient.

```
0xFF 0x04 0x00 rd rs1 rs2 imm8 flags   # EXT_TENSOR.TMATMUL with extra flags byte
```

This requires the VM to support pluggable decoders. Most extensions should use
Pattern A.

### 2.5 Encoding Size Analysis

| Encoding | Bytes | Extension Ops Addressable |
|----------|-------|--------------------------|
| 0xFF alone (v2 ILLEGAL) | 1 | 0 (error) |
| 0xFF [ext_id] [sub_opcode] | 3 | 256 ext × 256 ops = 65,536 |
| + Format A operands | 3 | (no extra operands) |
| + Format B operands | 4 | (1 register) |
| + Format D operands | 5 | (1 register + imm8) |
| + Format E operands | 6 | (3 registers) |
| + Format F operands | 6 | (1 register + imm16) |
| + Format G operands | 7 | (2 registers + imm16) |

---

## 3. Extension Discovery Protocol

### 3.1 Runtime Extension Table

Every ISA v3 VM maintains an **Extension Table** at startup:

```
EXT_TABLE[0x00] = NULL_EXTENSION  (always present — treats escape as extended NOP)
EXT_TABLE[0x01] = EXT_BABEL       (if loaded)
EXT_TABLE[0x02] = EXT_EDGE        (if loaded)
...
```

### 3.2 Dispatch Algorithm

When the VM fetches 0xFF:

```
function execute_escape_prefix(memory, pc):
    ext_id = memory[pc + 1]
    sub_opcode = memory[pc + 2]

    if ext_id == 0x00:
        # NULL extension — NOP passthrough
        pc += 3 + format_size(sub_opcode)
        return

    if ext_id not in EXT_TABLE:
        raise FAULT(EXT_UNSUPPORTED, ext_id)

    ext = EXT_TABLE[ext_id]
    handler = ext.get_handler(sub_opcode)

    if handler is None:
        raise FAULT(SUB_OPCODE_UNDEFINED, sub_opcode)

    operands = decode_operands(ext.format_map[sub_opcode], memory, pc + 3)
    handler(operands)
    pc += 3 + operands.size
```

### 3.3 VER_EXT Opcode (Meta-Extension)

A special meta-opcode for querying extensions at runtime:

```
0xFF 0xF0 [target_ext_id]    # Format H with NULL operands
```

- If `target_ext_id` is 0x00: returns count of loaded extensions in R0
- If `target_ext_id` is 0x01-0xFF: sets R0 = 1 (loaded) or R0 = 0 (not loaded)
- Sets R1 = extension version (major << 16 | minor << 8 | patch)

This allows bytecode programs to **runtime-check** extension availability before
using extension opcodes, enabling graceful fallback:

```
; Check if EXT_EDGE is available
0xFF 0xF0 0x02        ; VER_EXT for EXT_EDGE
MOVI R2, 1
CMP_EQ R3, R0, R2     ; R3 = (R0 == 1)
JZ R3, +12            ; skip edge-specific code if not available
... base ISA fallback ...
JMP +8
... extension code using 0xFF 0x02 ... ...
```

### 3.4 Hot-Loading (Meta-Extension 0xF1)

```
0xFF 0xF1 [ext_id] [addr_hi] [addr_lo]    # LOAD_EXT
```

Loads an extension at runtime from the memory address specified. The VM resolves
the extension manifest at that address, validates it, and registers the handler.

**Security constraint:** LOAD_EXT is gated by capability check (see EXT_SECURITY).

---

## 4. Opcode Negotiation (A2A Protocol)

### 4.1 CAPS Message Type

When Agent A sends bytecode to Agent B (via TELL/ASK), it includes a **CAPS
preamble** that lists required and optional extensions:

```json
{
  "msg_type": "CAPS",
  "isa_version": "3.0",
  "base_opcodes": "v2_full",
  "extensions_required": [0x01, 0x03],
  "extensions_optional": [0x02, 0x06],
  "bytecode_format": "little_endian",
  "max_instruction_size": 8
}
```

Agent B responds with:

```json
{
  "msg_type": "CAPS_ACK",
  "isa_version": "3.0",
  "extensions_supported": [0x01, 0x02, 0x03],
  "extensions_unsupported": [0x06],
  "fallback_strategy": "strip_and_nop",
  "negotiated_extensions": [0x01, 0x03]
}
```

### 4.2 Fallback Strategies

When Agent B doesn't support a required extension, one of these strategies
applies (negotiated in CAPS_ACK):

| Strategy | Code | Description |
|----------|------|-------------|
| Strip and NOP | `strip_and_nop` | Replace unsupported escape instructions with NOP; program may produce incorrect results |
| Strip and halt | `strip_and_halt` | Replace unsupported escape instructions with ILLEGAL trap; program stops at first extension use |
| Refuse bytecode | `refuse` | Reject the entire bytecode payload with EXT_UNSUPPORTED error |
| Emulate in base ISA | `emulate` | Agent B attempts to emulate extension behavior using base-ISA sequences |

### 4.3 Bytecode Stripping Algorithm

When `strip_and_nop` is negotiated, the sender can pre-strip:

```
function strip_unsupported_extensions(bytecode, supported_ext_ids):
    output = []
    pc = 0
    while pc < len(bytecode):
        if bytecode[pc] == 0xFF:
            ext_id = bytecode[pc + 1]
            if ext_id not in supported_ext_ids:
                # Calculate instruction size and replace with NOPs
                sub_opcode = bytecode[pc + 2]
                size = 3 + ext_operand_size(ext_id, sub_opcode)
                output.append(0x01)  # NOP
                pc += size
                continue
        output.append(bytecode[pc])
        pc += 1
    return bytes(output)
```

### 4.4 Extension Capability Flags

Each extension in a CAPS message carries flags:

```
BIT 0: READ    — agent can execute read-only extension ops
BIT 1: WRITE   — agent can execute state-mutating extension ops
BIT 2: ADMIN   — agent can load/unload extensions
BIT 3: CONF    — extension ops propagate confidence
BIT 4: ACCEL   — extension has hardware acceleration
BIT 5-7: RESERVED
```

This allows fine-grained permission scoping. For example, Agent A might have
READ+CONF for EXT_BABEL but not WRITE (can't modify linguistic state).

---

## 5. Extension Registration Protocol

### 5.1 Registration Workflow

```
1. Agent creates extension manifest JSON in their vessel repo
   Location: <vessel>/extensions/<ext_name>/manifest.json

2. Agent opens issue on flux-runtime titled:
   "Extension Registration: EXT_<NAME> (ID request)"

3. Oracle1 reviews manifest for:
   - Completeness (all required fields)
   - Conformance vectors (at least 5)
   - No overlap with existing extensions
   - ISA version compatibility
   - Security review (for fleet-standard extensions)

4. Oracle1 assigns ext_id and publishes to fleet extension registry
   Location: flux-runtime/docs/extension-registry.json

5. Extension enters "draft" status for 1 week fleet review

6. After review, extension promoted to "standard" or returned for revision
```

### 5.2 Extension Lifecycle States

```
DRAFT → REVIEW → STANDARD
  ↓       ↓
  └──→ REJECTED
        ↓
  REVISION → REVIEW → ...
```

| State | Meaning | Can be used in bytecode? |
|-------|---------|------------------------|
| DRAFT | Under review | Only in experimental range (0x80-0xEF) |
| REVIEW | Fleet review period (1 week) | Experimental only |
| STANDARD | Approved and registered | Fleet-standard range (0x01-0x7F) |
| DEPRECATED | Superseded by newer version | Warning at decode time |
| REJECTED | Not approved | Must not be used |

### 5.3 Version Compatibility

Extensions follow **semantic versioning** (semver). The manifest declares
`isa_min_version`:

```json
{
  "ext_id": 0x01,
  "name": "EXT_BABEL",
  "version": "2.1.0",
  "isa_min_version": "3.0",
  "api_version": "1.2"
}
```

A VM with ISA v3.0 can load extensions requiring v3.0+. A VM with ISA v2.x
treats all 0xFF instructions as ILLEGAL (backward compatible).

---

## 6. Concrete Extension Proposals

### 6.1 EXT_BABEL (0x01) — Multilingual Linguistic Opcodes

**Owner:** Babel  
**Domain:** Natural language processing, cross-lingual transfer, viewpoint semantics  
**ISA alignment:** Complements base-ISA Viewpoint ops (0x70-0x7F)

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | LANG_DETECT | H_E | rd, rs1, rs2 | Detect language ID of text at mem[rs1], len rs2 → rd |
| 0x01 | LANG_CLASSIFY | H_E | rd, rs1, rs2 | Classify text into linguistic category, score → rd |
| 0x02 | TRANSLATE | H_E | rd, rs1, rs2 | Translate mem[rs1] from lang rs2, result → rd |
| 0x03 | TOKENIZE | H_E | rd, rs1, rs2 | Tokenize text mem[rs1], tokenizer rs2, tokens → rd |
| 0x04 | MORPH_ANALYZE | H_E | rd, rs1, rs2 | Morphological analysis, features → rd |
| 0x05 | SCRIPT_DET | H_E | rd, rs1, rs2 | Detect writing script of text → rd |
| 0x06 | SENTIMENT | H_E | rd, rs1, rs2 | Sentiment analysis, polarity+magnitude → rd |
| 0x07 | ENT_EXTRACT | H_E | rd, rs1, rs2 | Named entity extraction, entities → rd |
| 0x08 | ALIGN_CROSS | H_E | rd, rs1, rs2 | Cross-lingual alignment of two texts |
| 0x09 | HONORIF_MAP | H_E | rd, rs1, rs2 | Map social context rs2 to honorific level → rd |
| 0x0A | Vocab_LOOKUP | H_E | rd, rs1, rs2 | Vocabulary lookup, definition → rd |
| 0x0B | TRANSLIT | H_E | rd, rs1, rs2 | Transliterate between scripts |

### 6.2 EXT_EDGE (0x02) — Sensor/Actuator Opcodes

**Owner:** JetsonClaw1  
**Domain:** Edge computing, hardware I/O, sensor fusion  
**ISA alignment:** Complements base-ISA sensor ops (0x80-0x8F) with higher-level primitives

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | SENSOR_STREAM | H_E | rd, rs1, rs2 | Open sensor stream rs1, sample_rate rs2, handle → rd |
| 0x01 | FUSION_INIT | H_E | rd, rs1, rs2 | Initialize sensor fusion, config rs1, handle → rd |
| 0x02 | FUSION_STEP | H_E | rd, rs1, rs2 | Run one fusion step, handle rs1, result → rd |
| 0x03 | MOTOR_CMD | H_E | rd, rs1, rs2 | Command motor rs1, velocity rs2, status → rd |
| 0x04 | LIDAR_SCAN | H_E | rd, rs1, rs2 | Trigger LIDAR scan, resolution rs1, points → rd |
| 0x05 | GPS_FUSION | H_E | rd, rs1, rs2 | Fused GPS + IMU position, sensors rs1, pos → rd |
| 0x06 | CAM_STREAM | H_E | rd, rs1, rs2 | Camera stream handle, camera rs1, fps rs2 |
| 0x07 | ACT_BATCH | H_E | rd, rs1, rs2 | Batch actuator command, count rs2, results → rd |
| 0x08 | SENSOR_CALIB | H_E | rd, rs1, rs2 | Calibrate sensor rs1, calibration data rs2 |
| 0x09 | POWER_BUDGET | H_E | rd, rs1, rs2 | Query power budget, device rs1, mW → rd |
| 0x0A | THERMAL_MGT | H_E | rd, rs1, rs2 | Thermal management, throttle rs1, temp → rd |
| 0x0B | DMA_CHAIN | H_G | rd, rs1, imm16 | DMA chained transfer, config rs1, length imm16 |

### 6.3 EXT_CONFIDENCE (0x03) — Advanced Confidence Propagation

**Owner:** Fleet-standard (converged)  
**Domain:** Sophisticated confidence tracking beyond base C_* opcodes  
**ISA alignment:** Extends base-ISA confidence ops (0x60-0x6F)

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | CONF_DISTRIBUTION | H_E | rd, rs1, rs2 | Build confidence distribution from samples rs1, bins rs2 → rd |
| 0x01 | CONF_BAYES_UPDATE | H_E | rd, rs1, rs2 | Bayesian update: prior rd, likelihood rs1, evidence rs2 |
| 0x02 | CONF_ENTROPY | H_E | rd, rs1, rs2 | Shannon entropy of confidence distribution rs1 → rd |
| 0x03 | CONF_CALIBRATE | H_E | rd, rs1, rs2 | Calibrate confidence model, predictions rs1, ground_truth rs2 |
| 0x04 | CONF_ENSEMBLE | H_E | rd, rs1, rs2 | Ensemble confidence: average confidence across N models |
| 0x05 | CONF_DECAY_EXP | H_E | rd, rs1, rs2 | Exponential decay: c(t) = c(0) * e^(-lambda*t), lambda → rs2 |
| 0x06 | CONF_FUSE_SENSOR | H_E | rd, rs1, rs2 | Fuse sensor confidence with model confidence |
| 0x07 | CONF_THRESHOLD_VEC | H_E | rd, rs1, rs2 | Vector threshold: apply different thresholds per output |
| 0x08 | CONF_PROP_CHAIN | H_E | rd, rs1, rs2 | Propagate confidence through computation chain |
| 0x09 | CONF_UNCERTAINTY | H_E | rd, rs1, rs2 | Quantify uncertainty: variance of confidence → rd |

### 6.4 EXT_TENSOR (0x04) — Tensor/Neural Primitives

**Owner:** JetsonClaw1 + Oracle1  
**Domain:** Neural network inference, tensor operations  
**ISA alignment:** Complements base-ISA tensor ops (0xC0-0xCF) with advanced ops

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | T_BATCHMATMUL | H_E | rd, rs1, rs2 | Batched matrix multiply for transformer layers |
| 0x01 | T_LAYER_NORM | H_E | rd, rs1, rs2 | Layer normalization over dimension rs2 |
| 0x02 | T_RESIDUAL | H_E | rd, rs1, rs2 | Residual connection: rd = rs1 + rs2 (with projection) |
| 0x03 | T_ATTENTION_FULL | H_E | rd, rs1, rs2 | Multi-head self-attention (Q=rs1, KV=rs2) |
| 0x04 | T_CROSS_ATTENTION | H_E | rd, rs1, rs2 | Cross-attention between two sequences |
| 0x05 | T_POSITIONAL | H_E | rd, rs1, rs2 | Apply positional encoding, type rs2 |
| 0x06 | T_CONV2D_STRIDE | H_E | rd, rs1, rs2 | 2D convolution with stride support |
| 0x07 | T_MAXPOOL2D | H_E | rd, rs1, rs2 | 2D max pooling, kernel rs2 |
| 0x08 | T_BATCH_NORM | H_E | rd, rs1, rs2 | Batch normalization, running stats rs2 |
| 0x09 | T_DROPOUT | H_E | rd, rs1, rs2 | Dropout with rate rs2, mask → rd |
| 0x0A | T_TOPK | H_E | rd, rs1, rs2 | Top-K selection, K=rs2, indices+values → rd |
| 0x0B | T_GATHER_SCATTER | H_E | rd, rs1, rs2 | Gather/scatter for embedding lookups |
| 0x0C | T_QUANTIZE_QAT | H_E | rd, rs1, rs2 | Quantization-aware training scale rs2 |
| 0x0D | T_DEQUANTIZE | H_E | rd, rs1, rs2 | Dequantize int8 → fp32 |
| 0x0E | T_RESHAPE | H_E | rd, rs1, rs2 | Reshape tensor, new_shape rs2 → rd |
| 0x0F | T_CONCAT | H_E | rd, rs1, rs2 | Concatenate tensors along dimension rs2 |

### 6.5 EXT_SECURITY (0x05) — Capability Enforcement

**Owner:** Fleet-standard (security-critical)  
**Domain:** Sandboxing, capability-based security, memory protection  
**ISA alignment:** Complements base-ISA MPROT (0xD9), FENCE (0xD6)

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | CAP_CHECK | H_E | rd, rs1, rs2 | Check if capability rs2 is granted for agent rs1 → rd (0/1) |
| 0x01 | CAP_GRANT | H_E | rd, rs1, rs2 | Grant capability rs2 to agent rs1 (requires ADMIN) |
| 0x02 | CAP_REVOKE | H_E | rd, rs1, rs2 | Revoke capability rs2 from agent rs1 (requires ADMIN) |
| 0x03 | SANDBOX_CREATE | H_E | rd, rs1, rs2 | Create sandbox with memory bounds rs1, capabilities rs2 → handle rd |
| 0x04 | SANDBOX_ENTER | H_E | rd, rs1, rs2 | Enter sandbox handle rs1, bytecode addr rs2 |
| 0x05 | SANDBOX_EXIT | H_E | rd, rs1, rs2 | Exit sandbox, return code → rd |
| 0x06 | MEM_TAG_SET | H_E | rd, rs1, rs2 | Tag memory region rs1 with security tag rs2 |
| 0x07 | MEM_TAG_CHECK | H_E | rd, rs1, rs2 | Verify memory tag at rs1 matches expected rs2 → rd (0/1) |
| 0x08 | SEAL_DATA | H_E | rd, rs1, rs2 | Seal (encrypt + sign) data at rs1 for agent rs2 → rd |
| 0x09 | UNSEAL_DATA | H_E | rd, rs1, rs2 | Unseal data at rs1, verify sender rs2 → rd |
| 0x0A | HASH_CHAIN | H_E | rd, rs1, rs2 | Add to hash chain, data rs1, previous rs2 → new hash rd |
| 0x0B | ATTEST_REQ | H_E | rd, rs1, rs2 | Request attestation from agent rs1, nonce rs2 |
| 0x0C | ATTEST_RESP | H_E | rd, rs1, rs2 | Process attestation response, verify → rd (0/1) |

### 6.6 EXT_TEMPORAL (0x06) — Temporal/Deadline Primitives

**Owner:** Fleet-standard  
**Domain:** Time-aware execution, deadlines, persistence, coroutine state  
**ISA alignment:** Complements base-ISA WFI (0x05), YIELD (0x15), COYIELD (0xE5)

| Sub | Mnemonic | Format | Operands | Description |
|-----|----------|--------|----------|-------------|
| 0x00 | DEADLINE_SET | H_E | rd, rs1, rs2 | Set deadline: current + rs1 cycles, callback addr rs2 → timer_id rd |
| 0x01 | DEADLINE_CHECK | H_E | rd, rs1, rs2 | Check if deadline rs1 is exceeded → rd (0=ok, 1=exceeded) |
| 0x02 | DEADLINE_CANCEL | H_E | rd, rs1, rs2 | Cancel deadline timer rs1 → rd (0=ok, 1=already expired) |
| 0x03 | PERSIST_STATE | H_E | rd, rs1, rs2 | Persist VM state to memory at rs1, size rs2 → checkpoint_id rd |
| 0x04 | RESTORE_STATE | H_E | rd, rs1, rs2 | Restore VM state from checkpoint rs1 → rd (0=ok) |
| 0x05 | YIELD_CONTENTION | H_E | rd, rs1, rs2 | Yield if resource rs1 is contended, timeout rs2 → rd (0=yielded, 1=acquired) |
| 0x06 | TIME_ELAPSED | H_E | rd, rs1, rs2 | Cycles elapsed since timestamp rs2 → rd |
| 0x07 | CORO_SAVE | H_E | rd, rs1, rs2 | Save coroutine state, registers → rd, context_id rs2 |
| 0x08 | CORO_RESTORE | H_E | rd, rs1, rs2 | Restore coroutine state from context rs1 → rd |
| 0x09 | SCHEDULE_AT | H_E | rd, rs1, rs2 | Schedule execution at cycle rs1, bytecode rs2 → task_id rd |
| 0x0A | WATCHDOG_SET | H_E | rd, rs1, rs2 | Set watchdog timeout rs1, handler rs2 → wd_id rd |

---

## 7. Migration from ISA v2 to ISA v3

### 7.1 Backward Compatibility (v2 → v3)

**v2 programs run unmodified on v3 VMs.** This is guaranteed by:

1. **Opcode stability:** All 247 v2 opcodes retain their addresses in v3
2. **0xFF reclassification:** The only change is that 0xFF changes from `ILLEGAL`
   (trap) to `ESCAPE_PREFIX` (dispatch). Since no valid v2 program contains 0xFF,
   this is a purely additive change.
3. **Format stability:** Formats A-G retain their byte layouts
4. **Register file:** 16 general-purpose + 16 confidence registers unchanged

### 7.2 Forward Compatibility (v3 → v2)

**v3 programs gracefully degrade on v2 VMs:**

| Scenario | v2 VM Behavior | Severity |
|----------|---------------|----------|
| v3 program uses only base ISA | Runs correctly | None |
| v3 program uses 0xFF escape | Traps on ILLEGAL (0xFF) | Program halts |
| v3 program has VER_EXT check | VER_EXT traps on ILLEGAL | Program halts (but gracefully) |

**Mitigation:** Well-designed v3 programs use the VER_EXT pattern:

```
; First: check ISA version
VER          ; 0xF5, sets R0 = ISA version (3 for v3)
MOVI R1, 3
CMP_LT R2, R0, R1    ; R2 = (R0 < 3), i.e., running on v2
JNZ R2, base_only    ; jump to base-only code path

; v3 path: check extension availability
0xFF 0xF0 0x01       ; VER_EXT for EXT_BABEL
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

### 7.3 ISA Version Detection

The `VER` opcode (0xF5) returns the ISA version in R0:

| Version | R0 value | Meaning |
|---------|----------|---------|
| v1 | 1 | Original ISA (pre-convergence) |
| v2 | 2 | Unified ISA (247 opcodes, current) |
| v3 | 3 | ISA v3 (247 base + escape prefix extensions) |

### 7.4 Bytecode Version Header (Optional)

Programs may optionally begin with a version magic:

```
Byte 0-3: 0x46 0x4C 0x55 0x58    ; "FLUX" magic
Byte 4:    ISA version (0x03)
Byte 5:    Number of extensions used
Byte 6+:   Extension IDs used (1 byte each)
```

This allows static analysis tools to check compatibility before execution.
The VM detects the magic and skips it (PC starts at the first real instruction
after the header). The header is **not** an instruction — it's metadata.

### 7.5 Migration Checklist for Runtime Authors

1. Change ILLEGAL (0xFF) handler to escape prefix dispatcher
2. Add extension table initialization
3. Implement VER_EXT meta-extension (0xFF 0xF0)
4. Add CAPS message handling in A2A layer
5. Add conformance vectors for escape prefix (see Section 8)
6. Update ISA version returned by VER to 3

---

## 8. Conformance Vectors

Five test vectors verify correct escape prefix handling:

### 8.1 Vector 1: Escape Prefix with NULL Extension (NOP)

**Name:** `ext_null_nop`  
**Category:** extension  
**Description:** 0xFF 0x00 [sub_opcode] should act as extended NOP

```
Input bytecode:
  0xFF 0x00 0x05    ; escape, NULL extension, sub_opcode 5
  0x18 0x00 0x2A    ; MOVI R0, 42

Expected: R0 = 42, no crash, no fault
PC advancement: 3 bytes (escape) + 3 bytes (MOVI) = 6
```

**Verify:** VM skips NULL extension instruction without side effects.

### 8.2 Vector 2: Unsupported Extension → FAULT

**Name:** `ext_unsupported_fault`  
**Category:** extension  
**Description:** 0xFF with unregistered ext_id raises EXT_UNSUPPORTED fault

```
Input bytecode:
  0xFF 0x7F 0x00    ; escape, ext_id 0x7F (unregistered), sub_opcode 0
  0x18 0x00 0x01    ; MOVI R0, 1

Expected: FAULT(EXT_UNSUPPORTED, 0x7F) raised before MOVI executes
R0 = 0 (MOVI never reached)
```

**Verify:** VM traps on unknown extension instead of executing garbage.

### 8.3 Vector 3: VER_EXT Query

**Name:** `ext_ver_query`  
**Category:** extension  
**Description:** VER_EXT meta-extension returns extension availability

```
Input bytecode (VM with EXT_BABEL loaded at 0x01):
  0xFF 0xF0 0x01    ; VER_EXT for EXT_BABEL
  ; Expected: R0 = 1 (loaded), R1 = version

Input bytecode (VM without EXT_BABEL):
  0xFF 0xF0 0x01    ; VER_EXT for EXT_BABEL
  ; Expected: R0 = 0 (not loaded)
```

**Verify:** Meta-extension correctly queries the extension table.

### 8.4 Vector 4: Extension Opcode Execution

**Name:** `ext_opcode_execute`  
**Category:** extension  
**Description:** Extension opcode with Format E operands executes correctly

```
Input bytecode (VM with EXT_CONFIDENCE loaded at 0x03):
  0x18 0x01 0x40    ; MOVI R1, 64
  0x18 0x02 0x80    ; MOVI R2, 128
  0x18 0x03 0x01    ; MOVI R3, 1
  0xFF 0x03 0x01 0x00 0x01 0x02
                     ; EXT_CONFIDENCE.CONF_BAYES_UPDATE(R0=R0, R1, R2)

Expected: R0 contains Bayesian-updated confidence value
No FAULT raised
```

**Verify:** Extension dispatch correctly reads Format E operands and executes.

### 8.5 Vector 5: v2 Program on v3 VM (Backward Compat)

**Name:** `v2_on_v3_compat`  
**Category:** migration  
**Description:** Pure v2 bytecode (no 0xFF) runs identically on v3 VM

```
Input bytecode (standard v2 arithmetic):
  0x18 0x00 0x0A    ; MOVI R0, 10
  0x18 0x01 0x14    ; MOVI R1, 20
  0x20 0x02 0x00 0x01  ; ADD R2, R0, R1
  0x00              ; HALT

Expected: R2 = 30
Behavior: identical to v2 VM output
```

**Verify:** v2 programs are bit-for-bit compatible across v2 and v3 VMs.

### 8.6 Vector 6: A2A CAPS Exchange

**Name:** `a2a_caps_exchange`  
**Category:** a2a  
**Description:** Agent with extensions negotiates with agent without

```
Agent A sends CAPS:
  isa_version: "3.0"
  extensions_required: [0x01, 0x03]
  extensions_optional: [0x06]
  bytecode: [0xFF 0x01 0x00 ...]  ; uses EXT_BABEL

Agent B responds (has EXT_BABEL but not EXT_CONFIDENCE):
  extensions_supported: [0x01]
  extensions_unsupported: [0x03]
  fallback_strategy: "strip_and_nop"

Expected: Agent A pre-strips 0xFF 0x03 instructions before sending bytecode
Or: Agent B receives and strips, replacing with NOPs
```

**Verify:** CAPS negotiation correctly identifies supported/unsupported extensions.

### 8.7 Vector 7: Extension Operand Size Correctness

**Name:** `ext_operand_size`  
**Category:** extension  
**Description:** VM correctly advances PC past extension instructions of varying size

```
Input bytecode:
  0xFF 0x02 0x0B 0x00 0x01 0x00 0x10
    ; EXT_EDGE.DMA_CHAIN (Format G: rd=R0, rs1=R1, imm16=0x1000)
    ; Total: 3 (prefix) + 5 (format G) = 8 bytes
  0x18 0x00 0xFF    ; MOVI R0, 255

Expected: R0 = 255 (MOVI after DMA_CHAIN is correctly reached)
PC after escape: original_pc + 8
```

**Verify:** PC advancement accounts for extension operand format.

---

## 9. Security Considerations

### 9.1 Extension Isolation

Extensions run in the VM's trust context. Security-sensitive extensions
(EXT_SECURITY, EXT_TEMPORAL) require:

1. **Capability gating:** CAP_CHECK must pass before extension ops execute
2. **Memory sandboxing:** Extension state is isolated from other extensions
3. **Resource limits:** Extensions have cycle and memory budgets

### 9.2 Untrusted Extensions

Experimental extensions (0x80-0xEF) from unknown sources:

- Must be loaded in sandboxed mode by default
- Cannot access memory outside their allocated region
- Cannot modify base-ISA register file without explicit grant
- Are subject to cycle budgets (default: 10,000 cycles per invocation)

### 9.3 Extension Signing

Fleet-standard extensions should be signed:

```json
{
  "ext_id": 0x01,
  "signature": "sha256:abc123...",
  "signer": "oracle1-vessel",
  "signed_at": "2026-04-12T00:00:00Z"
}
```

VMs can verify signatures before loading. Unsigned extensions are treated
as experimental regardless of their ext_id.

---

## 10. Open Questions

1. **Should sub_opcodes support their own escape?** If an extension exhausts its
   256 sub-opcodes, can `sub_opcode = 0xFF` within an extension trigger a further
   level of dispatch? **Proposed answer:** No. 256 sub-opcodes per extension is
   ample. If needed, allocate a second extension ID.

2. **Should extension IDs be globally unique or per-agent?** Currently proposed
   as globally unique. This simplifies bytecode portability but constrains the
   namespace. **Proposed answer:** Globally unique, with 256 IDs available and
   experimental self-registration for less formal use.

3. **How do extensions interact with the confidence register file?** If an
   extension produces a result in R0, should C0 (confidence register 0) be
   updated? **Proposed answer:** Extensions declare `confidence_aware: true`
   in their manifest. If true, the extension must write to both value and
   confidence registers. If false, C registers are unchanged.

4. **Should the NULL extension (0x00) support any sub-opcodes?** Currently
   defined as always-NOP. **Proposed answer:** NULL extension is a pure NOP
   passthrough for all 256 sub-opcodes. This allows bytecode padding.

---

## 11. Design Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Escape byte | 0xFF | Already ILLEGAL in v2; no valid v2 program uses it |
| Extension ID width | 1 byte (256 IDs) | Sufficient with experimental self-registration |
| Sub-opcode width | 1 byte (256 per ext) | Matches base ISA opcode space |
| Operand format | Reuse base ISA formats | Minimizes new decode logic |
| Discovery | VER_EXT meta-extension | Runtime-checkable without external protocol |
| Negotiation | CAPS A2A message | Leverages existing fleet messaging |
| Registration | Oracle1-approved + self-assigned | Balances quality with velocity |
| Backward compat | Guaranteed | 0xFF is the only change, unused in v2 |
| Forward compat | Graceful degradation | VER_EXT + fallback code paths |
| Extension isolation | Sandbox + capability model | Security requirement for multi-agent fleet |

---

## Appendix A: Encoding Examples

```
; --- Simple extension call (zero-operand) ---
0xFF 0x03 0x0A           ; EXT_CONFIDENCE.CONF_UNCERTAINTY() — 3 bytes

; --- Extension with Format E operands ---
0xFF 0x01 0x00 0x00 0x01 0x02
                          ; EXT_BABEL.LANG_DETECT(R0, R1, R2) — 6 bytes

; --- Extension with Format F operands ---
0xFF 0x02 0x09 0x00 0x00 0x01
                          ; EXT_EDGE.POWER_BUDGET(R0, imm16=256) — 6 bytes

; --- Extension with Format G operands ---
0xFF 0x02 0x0B 0x00 0x01 0x04 0x00
                          ; EXT_EDGE.DMA_CHAIN(R0, R1, imm16=1024) — 7 bytes

; --- VER_EXT query ---
0xFF 0xF0 0x01           ; Query if EXT_BABEL is loaded — 3 bytes

; --- NULL extension (NOP) ---
0xFF 0x00 0x42           ; NOP with padding — 3 bytes
```

## Appendix B: Relationship to Other ISA-00x Tasks

| Task | Relationship |
|------|-------------|
| ISA-001 (v3 draft) | Escape prefix is a core component of v3 |
| ISA-003 (compressed format) | Compressed format does NOT apply to escape prefix (prefix is already minimal at 3 bytes) |
| ASYNC-001 (async primitives) | Could become EXT_ASYNC (0x07) using this mechanism |
| TEMP-001 (temporal primitives) | Directly implemented as EXT_TEMPORAL (0x06) |
| SEC-001 (security primitives) | Directly implemented as EXT_SECURITY (0x05) |
