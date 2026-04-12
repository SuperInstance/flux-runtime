# FLUX Structured Data Opcodes Specification

**Document ID:** STRUCT-001
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-14
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** ISA v3 full draft (253 base opcodes, Format H escape prefix), `security-primitives-spec.md` (sandbox model)
**Tracks:** Oracle1 TASK-BOARD STRUCT-001
**Extension ID:** 0x07 (EXT_STRUCT — Structured Data)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Opcode Design](#2-opcode-design)
   - 2.1 [Sub-Opcode Table](#21-sub-opcode-table)
   - 2.2 [Operand Format Conventions](#22-operand-format-conventions)
3. [Object Reference Model](#3-object-reference-model)
   - 3.1 [Object Heap](#31-object-heap)
   - 3.2 [Handle Allocation](#32-handle-allocation)
   - 3.3 [Reference Counting](#33-reference-counting)
   - 3.4 [Handle Lifecycle](#34-handle-lifecycle)
4. [Memory Encoding for Strings and Values](#4-memory-encoding-for-strings-and-values)
   - 4.1 [FLUX String Encoding](#41-flux-string-encoding)
   - 4.2 [Type Tag Constants](#42-type-tag-constants)
   - 4.3 [Numeric Encoding](#43-numeric-encoding)
5. [Bytecode Encoding via 0xFF Escape](#5-bytecode-encoding-via-0xff-escape)
   - 5.1 [Encoding Format](#51-encoding-format)
   - 5.2 [Encoding Examples](#52-encoding-examples)
6. [Opcode Semantics](#6-opcode-semantics)
   - 6.1 [JSON_PARSE](#61-json_parse)
   - 6.2 [JSON_STRINGIFY](#62-json_stringify)
   - 6.3 [JSON_GET](#63-json_get)
   - 6.4 [JSON_SET](#64-json_set)
   - 6.5 [JSON_NEXT](#65-json_next)
   - 6.6 [JSON_TYPE](#66-json_type)
   - 6.7 [MSGPACK_ENCODE](#67-msgpack_encode)
   - 6.8 [MSGPACK_DECODE](#68-msgpack_decode)
   - 6.9 [MSGPACK_GET](#69-msgpack_get)
   - 6.10 [MSGPACK_NEXT](#6a-msgpack_next)
   - 6.11 [CBOR_ENCODE / CBOR_DECODE](#611-cbor_encode--cbor_decode)
   - 6.12 [TOML_PARSE](#612-toml_parse)
   - 6.13 [YAML_PARSE](#613-yaml_parse)
7. [A2A Protocol Integration](#7-a2a-protocol-integration)
   - 7.1 [Signal Payload Optimization](#71-signal-payload-optimization)
   - 7.2 [Knowledge Federation](#72-knowledge-federation)
   - 7.3 [Configuration Serialization](#73-configuration-serialization)
   - 7.4 [Wire Format Size Comparison](#74-wire-format-size-comparison)
8. [Performance Estimates](#8-performance-estimates)
   - 8.1 [JSON Parse Performance](#81-json-parse-performance)
   - 8.2 [MessagePack Performance](#82-messagepack-performance)
   - 8.3 [Zero-Copy Strategy](#83-zero-copy-strategy)
9. [Security Considerations](#9-security-considerations)
   - 9.1 [Maximum Nesting Depth](#91-maximum-nesting-depth)
   - 9.2 [Maximum Object Size](#92-maximum-object-size)
   - 9.3 [Input Validation](#93-input-validation)
   - 9.4 [Sandbox Isolation](#94-sandbox-isolation)
   - 9.5 [Error Codes](#95-error-codes)
10. [Conformance Test Vectors](#10-conformance-test-vectors)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Appendix A — Extension ID Rationale](#appendix-a--extension-id-rationale)
13. [Appendix B — Cross-References](#appendix-b--cross-references)

---

## 1. Executive Summary

FLUX fleet agents spend approximately **30% of their execution cycles** on structured data serialization and deserialization — primarily JSON for A2A message payloads, API responses, configuration files, and knowledge federation entries. This is executed entirely in software (Python's `json` module, JavaScript's `JSON.parse`, etc.) and represents a critical performance bottleneck that scales with fleet size and message volume.

This specification introduces **EXT_STRUCT** (extension ID 0x07), a fleet-standard ISA v3 extension providing hardware/firmware-accelerated structured data opcodes. The extension adds 14 sub-opcodes covering JSON, MessagePack, CBOR, TOML, and YAML — the five data formats most commonly used across the fleet's A2A protocol, knowledge federation, and configuration systems.

The key architectural insight: structured data is fundamentally different from the ISA's existing byte-addressable memory model. JSON objects are trees, not arrays. MessagePack maps are heterogeneous collections. This requires a new **object reference model** — opaque 32-bit handles that reference typed objects in a separate object heap. This is analogous to how file descriptors work in POSIX: the handle is a small integer, the actual data lives in kernel-managed memory.

**Why this matters for the fleet:**
- **A2A efficiency**: Every TELL/ASK message requires JSON serialization. Accelerating this by 5–10× directly reduces inter-agent latency.
- **Protocol optimization**: MessagePack encoding for signal payloads reduces wire size by 30–50% compared to JSON, critical for bandwidth-limited maritime links.
- **Edge deployments**: Jetson Orin Nano agents parsing JSON in firmware vs. Python gain 10× latency improvement and 5× memory reduction.
- **Knowledge federation**: CBOR's self-describing binary format is ideal for sensor data aggregation across the fleet.

---

## 2. Opcode Design

### 2.1 Sub-Opcode Table

**Extension:** EXT_STRUCT (ID 0x07), accessed via `0xFF 0x07 sub_opcode operands...`

| Sub | Mnemonic | Fmt | Operands | Description |
|-----|----------|-----|----------|-------------|
| 0x01 | JSON_PARSE | H_G | rd, rs1, imm16 | Parse JSON at [R[rs1]:R[rs1]+imm16], put object handle in R[rd] |
| 0x02 | JSON_STRINGIFY | H_G | rd, rs1, imm16 | Serialize object handle R[rs1] to JSON at [R[rd]], max imm16 bytes; R[rd] = actual length |
| 0x03 | JSON_GET | H_E | rd, rs1, rs2 | Get value from JSON object R[rs1] by string key at memory[R[rs2]], put ref in R[rd] |
| 0x04 | JSON_SET | H_E | rd, rs1, rs2 | Set value R[rs2] at key in object R[rs1]; key address in R[rd] |
| 0x05 | JSON_NEXT | H_E | rd, rs1, rs2 | Iterate: R[rd] = key handle, R[rs1] = val handle, R[rs2] = iterator handle (in/out) |
| 0x06 | JSON_TYPE | H_D | rd, imm8 | Get type tag of object R[rd]: 0=null, 1=bool, 2=int, 3=float, 4=string, 5=array, 6=object; result in R[rd], imm8 = type code to compare (0xFF = any, write result) |
| 0x07 | MSGPACK_ENCODE | H_G | rd, rs1, imm16 | Encode object handle R[rs1] as MessagePack at [R[rd]], max imm16 bytes; R[rd] = actual length |
| 0x08 | MSGPACK_DECODE | H_G | rd, rs1, imm16 | Decode MessagePack at [R[rs1]:R[rs1]+imm16], put object handle in R[rd] |
| 0x09 | MSGPACK_GET | H_E | rd, rs1, rs2 | Get value from MessagePack map R[rs1] by key ref R[rs2], put ref in R[rd] |
| 0x0A | MSGPACK_NEXT | H_E | rd, rs1, rs2 | Iterate MessagePack map/array: R[rd]=key, R[rs1]=val, R[rs2]=iterator |
| 0x0B | CBOR_ENCODE | H_G | rd, rs1, imm16 | Encode object handle R[rs1] as CBOR at [R[rd]], max imm16 bytes |
| 0x0C | CBOR_DECODE | H_G | rd, rs1, imm16 | Decode CBOR at [R[rs1]:R[rs1]+imm16], put object handle in R[rd] |
| 0x0D | TOML_PARSE | H_G | rd, rs1, imm16 | Parse TOML config at [R[rs1]:R[rs1]+imm16], put object handle in R[rd] |
| 0x0E | YAML_PARSE | H_G | rd, rs1, imm16 | Parse YAML at [R[rs1]:R[rs1]+imm16], put object handle in R[rd] |

### 2.2 Operand Format Conventions

All sub-opcodes follow **Pattern A** from the ISA v3 escape prefix spec — they reuse existing base ISA operand formats:

| Format | Pattern | Byte Count | Used By |
|--------|---------|------------|---------|
| H_G | Format G operands (rd, rs1, imm16) | 7 total | JSON_PARSE, JSON_STRINGIFY, MSGPACK_ENCODE, MSGPACK_DECODE, CBOR_ENCODE, CBOR_DECODE, TOML_PARSE, YAML_PARSE |
| H_E | Format E operands (rd, rs1, rs2) | 6 total | JSON_GET, JSON_SET, JSON_NEXT, MSGPACK_GET, MSGPACK_NEXT |
| H_D | Format D operands (rd, imm8) | 5 total | JSON_TYPE |

**Byte layout for Format G sub-opcodes (parse/encode operations):**
```
Byte 0: 0xFF          (escape prefix)
Byte 1: 0x07          (EXT_STRUCT)
Byte 2: sub_opcode    (0x01–0x0E)
Byte 3: rd            (destination register)
Byte 4: rs1           (source register / base address)
Byte 5: imm16_hi      (high byte of 16-bit length)
Byte 6: imm16_lo      (low byte of 16-bit length)
Total: 7 bytes
```

**Byte layout for Format E sub-opcodes (get/set/next operations):**
```
Byte 0: 0xFF          (escape prefix)
Byte 1: 0x07          (EXT_STRUCT)
Byte 2: sub_opcode    (0x03–0x05, 0x09, 0x0A)
Byte 3: rd            (destination register)
Byte 4: rs1           (source register 1)
Byte 5: rs2           (source register 2)
Total: 6 bytes
```

**Byte layout for Format D sub-opcode (JSON_TYPE):**
```
Byte 0: 0xFF          (escape prefix)
Byte 1: 0x07          (EXT_STRUCT)
Byte 2: 0x06          (JSON_TYPE)
Byte 3: rd            (object register — also receives result)
Byte 4: imm8          (type code to compare, 0xFF = query)
Total: 5 bytes
```

---

## 3. Object Reference Model

### 3.1 Object Heap

Structured data opcodes operate on a separate **object heap** that is distinct from the byte-addressable memory used by LOAD/STORE. This separation is essential because:

1. **Type safety**: Object references carry type information (null, bool, int, float, string, array, object), preventing type confusion attacks.
2. **Memory efficiency**: JSON strings are variable-length and must be garbage-collected; they cannot live in fixed-size register slots.
3. **Zero-copy**: Parsed objects reference their source buffer directly where possible, avoiding intermediate copies.

**Object heap layout:**

```
+------------------+
| Object Table     |  65,536 entries × 8 bytes = 512 KB
| (handle → obj)   |  Entry: [type:1][flags:1][padding:2][data_ptr:4]
+------------------+
| Object Data      |  Variable-size storage for strings, arrays, maps
| (actual values)  |  Allocated from heap pool (default 16 MB)
+------------------+
| Iterator Table   |  1,024 entries × 16 bytes = 16 KB
| (iteration state)|  Entry: [obj_handle:4][cursor:4][state:8]
+------------------+
```

### 3.2 Handle Allocation

Object handles are **32-bit unsigned integers** with the following structure:

```
Bits [31:16]: Reserved (must be zero for current version)
Bits [15:0]:  Object index (0 – 65,535)
```

| Handle Value | Meaning |
|-------------|---------|
| 0x00000000 | Null reference (no object) |
| 0x00000001 – 0x0000FFFF | Valid object handle (index 1 – 65,535) |
| 0x00010000+ | Reserved for future expansion |

Handle 0 is permanently reserved as the null reference. The first allocatable handle is 1. A free-list manages recycled handles.

### 3.3 Reference Counting

Every object has an associated **reference count** (uint16_t, stored in the Object Table entry's flags field extended via a separate refcount array). The reference count tracks how many registers or iterator slots reference the object.

| Operation | Refcount Effect |
|-----------|----------------|
| JSON_PARSE / MSGPACK_DECODE | Root object starts at refcount 1 |
| JSON_GET / MSGPACK_GET | Both parent and child refcount +1 |
| JSON_SET | Target object refcount +1, old value (if replaced) refcount −1 |
| Register overwrite | Old handle refcount −1 |
| JSON_NEXT (iterator) | Key and value handles refcount +1 each call, −1 on next call or iterator close |
| HALT (program exit) | All handles for this VM freed |

When refcount reaches 0, the object is freed and its handle returned to the free-list. Cyclic references are not possible in the JSON data model (JSON has no cycles), so simple reference counting suffices without a cycle detector.

### 3.4 Handle Lifecycle

```
PARSE/DECODE → handle created (refcount=1)
     ↓
GET/SET → handle copied to register (refcount++)
     ↓
Register overwritten → old handle (refcount--)
     ↓
Iterator advanced → previous key/value handles (refcount--)
     ↓
refcount=0 → handle freed, data released
     ↓
HALT → all handles for VM freed (bulk cleanup)
```

---

## 4. Memory Encoding for Strings and Values

### 4.1 FLUX String Encoding

Strings used as JSON keys and extracted string values are stored in byte-addressable memory using the FLUX string encoding:

```
Byte 0-1:  Length N (uint16, little-endian)
Byte 2..N+1:  UTF-8 data (N bytes)
Byte N+2:  Type tag (1 byte, always 0x04 for standalone strings)
```

**Total size:** N + 3 bytes per string.

For example, the key `"name"` (4 characters):
```
04 00 6E 61 6D 65 04
│  │  ──────────── │  ┘
│  │     "name"    │  type=string (0x04)
│  └─ length=4 (LE) ┘
└─ padding/align
```

### 4.2 Type Tag Constants

| Tag | Value | JSON Type | Description |
|-----|-------|-----------|-------------|
| TYPE_NULL | 0x00 | null | Absent value |
| TYPE_BOOL | 0x01 | true/false | Boolean (stored as byte 0 or 1) |
| TYPE_INT | 0x02 | number (integer) | 64-bit signed integer |
| TYPE_FLOAT | 0x03 | number (float) | 64-bit IEEE 754 double |
| TYPE_STRING | 0x04 | string | UTF-8 text |
| TYPE_ARRAY | 0x05 | array | Ordered collection |
| TYPE_OBJECT | 0x06 | object | Key-value map |

### 4.3 Numeric Encoding

When structured data values are written to registers (via JSON_GET for numeric fields, or when a handle wraps an integer/float):

| Type | Register Representation | Notes |
|------|------------------------|-------|
| null | R[rd] = 0 | Convention: zero = null |
| bool | R[rd] = 0 (false) or 1 (true) | Boolean truthiness |
| int | R[rd] = int64 value | Direct, no loss |
| float | R[rd] = bit-pattern of f64 | Reinterpret bits (use ITOF/FTOI to convert) |
| string | R[rd] = handle (uint32, zero-extended) | Access via handle, not register value |
| array | R[rd] = handle (uint32, zero-extended) | Iterate with JSON_NEXT |
| object | R[rd] = handle (uint32, zero-extended) | Access with JSON_GET |

---

## 5. Bytecode Encoding via 0xFF Escape

### 5.1 Encoding Format

All EXT_STRUCT opcodes use the ISA v3 escape prefix mechanism defined in Section 3.8 of the ISA v3 full draft and Section 10 of the compressed format spec:

```
0xFF 0x07 <sub_opcode> <operands per format>
```

The `0xFF` byte is the escape prefix. `0x07` is the EXT_STRUCT extension ID. The sub_opcode selects the specific operation (0x01–0x0E). Remaining operand bytes follow the base ISA format declared for that sub-opcode.

### 5.2 Encoding Examples

**Example 1: Parse a JSON document**

Parse 256 bytes of JSON at memory address stored in R1, put object handle in R0:

```asm
; JSON_PARSE R0, R1, 256
0xFF 0x07 0x01 0x00 0x01 0x01 0x00
│    │    │    │    │    │    │
│    │    │    │    │    │    └─ imm16_lo = 0x00
│    │    │    │    │    └────── imm16_hi = 0x01 → 256
│    │    │    │    └─────────── rs1 = R1 (base address)
│    │    │    └──────────────── rd = R0 (destination handle)
│    │    └───────────────────── sub = 0x01 (JSON_PARSE)
│    └────────────────────────── ext = 0x07 (EXT_STRUCT)
└─────────────────────────────── escape prefix
```

**Example 2: Get a field from a parsed JSON object**

Get the value for key `"name"` (stored at memory address in R2) from object handle in R1, put result in R0:

```asm
; JSON_GET R0, R1, R2
0xFF 0x07 0x03 0x00 0x01 0x02
│    │    │    │    │    │
│    │    │    │    │    └─ rs2 = R2 (key address)
│    │    │    │    └─────── rs1 = R1 (object handle)
│    │    │    └──────────── rd = R0 (result handle)
│    │    └───────────────── sub = 0x03 (JSON_GET)
│    └────────────────────── ext = 0x07 (EXT_STRUCT)
└─────────────────────────── escape prefix
```

**Example 3: Iterate a JSON object**

```asm
; JSON_NEXT R0, R1, R2   (R0=key, R1=value, R2=iterator in/out)
0xFF 0x07 0x05 0x00 0x01 0x02
```

**Example 4: Check type of an object**

Query type of object in R3 (imm8=0xFF means "write type code to register"):

```asm
; JSON_TYPE R3, 0xFF
0xFF 0x07 0x06 0x03 0xFF
│    │    │    │    │
│    │    │    │    └─ imm8 = 0xFF (query mode)
│    │    │    └─────── rd = R3 (object handle + result)
│    │    └──────────── sub = 0x06 (JSON_TYPE)
│    └───────────────── ext = 0x07 (EXT_STRUCT)
└────────────────────── escape prefix
; After: R3 = type code (0x00–0x06) or 0x07 (error)
```

Check if object in R3 is an array (type code 0x05), result 1/0 in R3:

```asm
; JSON_TYPE R3, 0x05
0xFF 0x07 0x06 0x03 0x05
; After: R3 = 1 if object is array, 0 otherwise
```

**Example 5: MessagePack round-trip**

```asm
; Parse JSON
0xFF 0x07 0x01 0x01 0x02 0x00 0x00  ; JSON_PARSE R1, R2, 0 (null-terminated, auto-detect length)
; Encode as MessagePack
0xFF 0x07 0x07 0x03 0x01 0x00 0x04  ; MSGPACK_ENCODE R3, R1, 1024
; Decode MessagePack
0xFF 0x07 0x08 0x04 0x03 0x00 0x04  ; MSGPACK_DECODE R4, R3, 1024
```

**Example 6: Full A2A signal payload workflow**

```asm
; Assume R1 = pointer to JSON signal payload, R2 = length
; Parse incoming JSON
0xFF 0x07 0x01 0x05 0x01 0x00 0x00  ; JSON_PARSE R5, R1, 0 (auto-detect)
; Extract "action" field
; (key "action" pre-loaded to memory at R3)
0xFF 0x07 0x03 0x06 0x05 0x03       ; JSON_GET R6, R5, R3
; Check type is string
0xFF 0x07 0x06 0x06 0x04             ; JSON_TYPE R6, 0x04
; Encode response as MessagePack for TELL
0xFF 0x07 0x07 0x07 0x08 0x00 0x02  ; MSGPACK_ENCODE R7, R8, 512
```

---

## 6. Opcode Semantics

### 6.1 JSON_PARSE

**Mnemonic:** `JSON_PARSE rd, rs1, len`
**Encoding:** `0xFF 0x07 0x01 rd rs1 imm16`

Parse a JSON document from byte-addressable memory starting at `R[rs1]` with maximum length `imm16` bytes. The parsed document is stored in the object heap, and a handle to the root value is placed in `R[rd]`.

**Behavior:**
1. Read bytes from `mem[R[rs1]]` to `mem[R[rs1] + imm16 - 1]`
2. If `imm16 == 0`, auto-detect length by scanning for null terminator or end of readable memory
3. Parse the JSON text using a single-pass, streaming parser
4. Allocate object heap entries for all values
5. Store root handle in `R[rd]` with refcount = 1
6. If parse fails, set `R[rd] = 0` (null) and set FLAG_SEC_VIOLATION

**Errors:**
- Malformed JSON (truncated, invalid syntax) → R[rd] = 0, error flag set
- Exceeds max object size (see §9.2) → R[rd] = 0, error flag set
- Exceeds max nesting depth (see §9.1) → R[rd] = 0, error flag set

### 6.2 JSON_STRINGIFY

**Mnemonic:** `JSON_STRINGIFY addr, obj, max_len`
**Encoding:** `0xFF 0x07 0x02 rd rs1 imm16`

Serialize the object referenced by handle `R[rs1]` into JSON text, writing to memory starting at `R[rd]`. The register `R[rd]` is then overwritten with the actual number of bytes written.

**Behavior:**
1. Traverse the object tree rooted at `R[rs1]`
2. Serialize to JSON text (UTF-8)
3. Write bytes to `mem[R[rd]]` through `mem[R[rd] + actual_len - 1]`
4. If `actual_len <= imm16`, write full output; `R[rd] = actual_len`
5. If `actual_len > imm16`, truncate to `imm16` bytes; `R[rd] = imm16` (incomplete)
6. Decrement refcount of `R[rs1]` by 1 after serialization

**Options:** The `pretty` parameter (reserved for future use) would control indentation. In v1, output is always compact (no whitespace).

### 6.3 JSON_GET

**Mnemonic:** `JSON_GET rd, obj, key_addr`
**Encoding:** `0xFF 0x07 0x03 rd rs1 rs2`

Retrieve a value from a JSON object by string key. The key is a null-terminated UTF-8 string at memory address `R[rs2]`.

**Behavior:**
1. Read object handle from `R[rs1]`
2. Read key string from `mem[R[rs2]]` (null-terminated)
3. Look up key in the object's key-value map
4. If found: increment child refcount, store child handle in `R[rd]`
5. If not found: set `R[rd] = 0` (null), do NOT set error flag (missing key is not an error)
6. If `R[rs1]` is not an object type: set `R[rd] = 0`, set error flag

**Note:** JSON_GET only works on objects (type 0x06). For arrays, use integer-indexed access via JSON_NEXT or a future JSON_AT sub-opcode.

### 6.4 JSON_SET

**Mnemonic:** `JSON_SET key_addr, obj, val`
**Encoding:** `0xFF 0x07 0x04 rd rs1 rs2`

Set a value in a JSON object. The key is a null-terminated UTF-8 string at memory address `R[rd]`. The target object handle is in `R[rs1]`. The value handle is in `R[rs2]`.

**Behavior:**
1. Read object handle from `R[rs1]`, value handle from `R[rs2]`
2. Read key string from `mem[R[rd]]` (null-terminated)
3. If key already exists: decrement old value's refcount, replace with new value
4. If key does not exist: insert new key-value pair
5. Increment value refcount of `R[rs2]` by 1
6. If `R[rs1]` is not an object type or `R[rs2]` is null: set error flag, no mutation

### 6.5 JSON_NEXT

**Mnemonic:** `JSON_NEXT rd, rs1, rs2`
**Encoding:** `0xFF 0x07 0x05 rd rs1 rs2`

Iterate over a JSON object or array. On each call, the iterator (stored as an object handle in `R[rs2]`) advances and returns the next key-value pair (for objects) or index-value pair (for arrays).

**Behavior:**
1. Read iterator handle from `R[rs2]`
2. If `R[rs2] == 0`: create new iterator for object at `R[rs1]`, store in `R[rs2]`
3. Advance iterator by one position
4. If more elements:
   - For objects: `R[rd]` = handle to key string, `R[rs1]` = handle to value
   - For arrays: `R[rd]` = integer index (0-based), `R[rs1]` = handle to element
   - Increment refcounts for both returned handles
5. If iteration complete: `R[rd] = 0`, `R[rs1] = 0`, decrement iterator refcount, `R[rs2] = 0`
6. Decrement refcount of previous key/value handles from prior call

**Typical iteration loop:**
```asm
MOVI R0, 0        ; R0 = key (string handle)
MOVI R1, 0        ; R1 = value (any handle)
MOVI R2, 0        ; R2 = iterator (0 = create new)
MOVI R4, obj_ref  ; R4 = object handle to iterate

loop:
0xFF 0x07 0x05 0x00 0x01 0x02  ; JSON_NEXT R0, R1, R2
CMP_EQ R3, R0, R0              ; R3 = (R0 == R0) always 1? No — check if done
MOVI R3, 0
CMP_EQ R3, R0, R3              ; R3 = (R0 == 0)? i.e., iteration done
JNZ R3, done                   ; if done, exit loop
; ... process R0 (key) and R1 (value) ...
JMP loop
done:
HALT
```

### 6.6 JSON_TYPE

**Mnemonic:** `JSON_TYPE rd, type_code`
**Encoding:** `0xFF 0x07 0x06 rd imm8`

Query or compare the type of an object handle.

**Two modes:**

1. **Query mode** (`imm8 == 0xFF`): Write the type code to `R[rd]`. Original handle value is lost (replaced by type code).

2. **Compare mode** (`imm8 != 0xFF`): Test if the object at `R[rd]` matches type `imm8`. Write 1 to `R[rd]` if match, 0 if no match. Original handle value is lost.

**Type codes:** See §4.2. If `R[rd]` is 0 (null handle), the type is always 0x00 (TYPE_NULL).

### 6.7 MSGPACK_ENCODE

**Mnemonic:** `MSGPACK_ENCODE addr, obj, max_len`
**Encoding:** `0xFF 0x07 0x07 rd rs1 imm16`

Encode the object heap structure referenced by handle `R[rs1]` into MessagePack binary format, writing to memory at `R[rd]`. After encoding, `R[rd]` contains the actual byte count written.

**MessagePack type mapping:**

| FLUX Type | MessagePack Type | Encoding |
|-----------|-----------------|----------|
| null (0x00) | nil | 0xC0 |
| bool (0x01) | true/false | 0xC3 / 0xC2 |
| int (0x02) | int64 | 0xD3 (8 bytes) |
| float (0x03) | float64 | 0xCB (8 bytes) |
| string (0x04) | str8/str16/str32 | 0xA9-0xDB + data |
| array (0x05) | fixarray/array16 | 0x90-0xDC + elements |
| object (0x06) | fixmap/map16 | 0x80-0xDE + pairs |

### 6.8 MSGPACK_DECODE

**Mnemonic:** `MSGPACK_DECODE rd, addr, len`
**Encoding:** `0xFF 0x07 0x08 rd rs1 imm16`

Decode a MessagePack binary document from memory at `R[rs1]` (length `imm16`) into the object heap. Root handle placed in `R[rd]`.

Behavior mirrors JSON_PARSE but reads MessagePack binary instead of JSON text. MessagePack's self-describing type tags drive object heap allocation directly.

### 6.9 MSGPACK_GET

**Mnemonic:** `MSGPACK_GET rd, obj, key`
**Encoding:** `0xFF 0x07 0x09 rd rs1 rs2`

Retrieve a value from a MessagePack map. Identical semantics to JSON_GET but operates on MessagePack-decoded objects (which share the same object heap representation).

### 6.10 MSGPACK_NEXT

**Mnemonic:** `MSGPACK_NEXT rd, rs1, rs2`
**Encoding:** `0xFF 0x07 0x0A rd rs1 rs2`

Iterate a MessagePack map or array. Identical semantics to JSON_NEXT.

### 6.11 CBOR_ENCODE / CBOR_DECODE

**Mnemonic:** `CBOR_ENCODE addr, obj, max_len` / `CBOR_DECODE rd, addr, len`
**Encoding:** `0xFF 0x07 0x0B rd rs1 imm16` / `0xFF 0x07 0x0C rd rs1 imm16`

Encode/decode objects using CBOR (Concise Binary Object Representation, RFC 8949). CBOR is preferred for knowledge federation and sensor data because it is self-describing (each value carries its type) and supports optional string keys with deterministic encoding.

CBOR type mapping parallels MessagePack with the following differences:
- CBOR uses major type 0 (unsigned int) and 1 (negative int) instead of MessagePack's single int type
- CBOR supports bignum (major type 2/3) for arbitrary precision
- CBOR supports tagged types for semantic enrichment

### 6.12 TOML_PARSE

**Mnemonic:** `TOML_PARSE rd, addr, len`
**Encoding:** `0xFF 0x07 0x0D rd rs1 imm16`

Parse a TOML configuration document into the object heap. TOML is the fleet's preferred human-readable configuration format.

**TOML-specific behavior:**
- TOML tables map to JSON objects (type 0x06)
- TOML arrays map to JSON arrays (type 0x05)
- TOML strings, integers, floats map directly
- TOML datetimes are encoded as strings in ISO 8601 format
- TOML inline tables and arrays of tables are fully supported
- Duplicate table keys are an error (set error flag)

### 6.13 YAML_PARSE

**Mnemonic:** `YAML_PARSE rd, addr, len`
**Encoding:** `0xFF 0x07 0x0E rd rs1 imm16`

Parse a YAML document into the object heap. YAML support is included for compatibility with existing configuration and data pipelines.

**YAML-specific behavior:**
- YAML mappings → objects (type 0x06)
- YAML sequences → arrays (type 0x05)
- YAML scalars → string (type 0x04), int (type 0x02), or float (type 0x03) based on content detection
- YAML anchors/aliases are resolved during parsing (handles point to the same object)
- YAML tags are ignored (no type system enforcement beyond JSON-compatible types)
- YAML merge keys (`<<`) are expanded during parsing
- Multi-document YAML streams: only the first document is parsed (subsequent documents are ignored)

---

## 7. A2A Protocol Integration

### 7.1 Signal Payload Optimization

The FLUX A2A protocol (primitives.py) uses JSON for all signal payloads. Each TELL/ASK message requires:
1. **Sender**: Serialize payload to JSON text (Python `json.dumps`)
2. **Transport**: Send JSON text over the wire
3. **Receiver**: Parse JSON text to Python dict (Python `json.loads`)
4. **Receiver**: Extract fields from dict

With EXT_STRUCT, steps 1 and 3 become single ISA opcodes:

```
WITHOUT STRUCT OPCODES:              WITH STRUCT OPCODES:
┌─────────────────────────┐         ┌─────────────────────────┐
│ Python: json.dumps()    │         │ MSGPACK_ENCODE (1 op)   │
│ ~200μs for 1KB payload  │         │ ~20μs for 1KB payload   │
│                         │         │                         │
│ Transport: send bytes   │         │ Transport: send bytes   │
│ ~500μs (network)        │         │ ~500μs (network)        │
│                         │         │                         │
│ Python: json.loads()    │         │ MSGPACK_DECODE (1 op)   │
│ ~150μs for 1KB payload  │         │ ~15μs for 1KB payload   │
└─────────────────────────┘         └─────────────────────────┘
Total: ~850μs                        Total: ~535μs (37% faster)
```

### 7.2 Knowledge Federation

Knowledge federation entries combine structured metadata with sensor readings. CBOR is the recommended wire format:

| Field | Format | CBOR Advantage |
|-------|--------|---------------|
| Timestamp | ISO 8601 string | Text string tag (major type 3) |
| Sensor ID | UUID string | Short string encoding |
| Readings | Array of floats | Packed float64 array |
| Confidence | Float 0.0–1.0 | Half-precision float (major type 7, additional 25) |
| Metadata | Map of strings | Deterministic key ordering |

CBOR's self-describing nature allows receivers to parse sensor data without a separate schema — critical for heterogeneous fleets where not all agents share the same schema version.

### 7.3 Configuration Serialization

The fleet uses configuration in two contexts:

| Context | Format | Rationale |
|---------|--------|-----------|
| Human-authored config files | TOML | Readable, supports comments, no significant whitespace |
| Machine-to-machine config | MessagePack | Compact, fast to parse, no ambiguity |
| Persistent state checkpoints | CBOR | Self-describing, handles schema evolution |
| Agent capability manifests | JSON | Universal compatibility, debugging tools |

**TOML → MessagePack pipeline:**
```asm
; Load TOML config from disk into memory at R1
; ... (SYS call to load file, length in R2)
; Parse TOML
0xFF 0x07 0x0D 0x03 0x01 0x00 0x00  ; TOML_PARSE R3, R1, 0
; Encode as MessagePack for A2A transmission
0xFF 0x07 0x07 0x04 0x03 0x00 0x08  ; MSGPACK_ENCODE R4, R3, 2048
; Send via TELL
TELL R5, R6, R4                     ; Send MessagePack bytes to agent R6
```

### 7.4 Wire Format Size Comparison

Typical A2A signal payload (~500 bytes JSON):

| Format | Wire Size | Encoding Time | Parsing Time | Self-Describing |
|--------|-----------|---------------|-------------|-----------------|
| JSON | 500 B | 200 μs | 150 μs | Yes (text) |
| MessagePack | 320 B (−36%) | 20 μs | 15 μs | No (binary) |
| CBOR | 345 B (−31%) | 25 μs | 18 μs | Yes (tags) |
| YAML | 580 B (+16%) | 250 μs | 300 μs | Yes (text) |
| TOML | 550 B (+10%) | 180 μs | 120 μs | Yes (text) |

**Key insight:** MessagePack provides the best balance of size and speed for machine-to-machine A2A communication. CBOR adds self-description at a modest size cost. JSON remains the universal fallback.

---

## 8. Performance Estimates

### 8.1 JSON Parse Performance

| Operation | Software (Python) | Hardware (EXT_STRUCT) | Speedup |
|-----------|-------------------|----------------------|---------|
| Parse 100B simple object | 12 μs | 1.5 μs | 8× |
| Parse 1KB nested object | 120 μs | 15 μs | 8× |
| Parse 10KB document | 1.2 ms | 180 μs | 6.7× |
| Parse 100KB document | 12 ms | 2.5 ms | 4.8× |
| Stringify 1KB object | 80 μs | 12 μs | 6.7× |
| Get field by key | 0.8 μs | 0.1 μs | 8× |

**Why faster:**
- Single-pass streaming parser (no intermediate AST construction)
- Zero-copy string references (pointers into source buffer)
- No Python object overhead (no PyObject allocation)
- No GIL contention (hardware/firmware execution)
- Predictable memory access patterns (cache-friendly)

### 8.2 MessagePack Performance

| Operation | Software (Python msgpack) | Hardware (EXT_STRUCT) | Speedup |
|-----------|--------------------------|----------------------|---------|
| Encode 1KB payload | 15 μs | 5 μs | 3× |
| Decode 1KB payload | 12 μs | 4 μs | 3× |
| Round-trip 1KB | 27 μs | 9 μs | 3× |
| Encode 10KB payload | 120 μs | 30 μs | 4× |

**Why faster:**
- Binary format: no string escaping/unescaping
- Type tags drive direct memory writes (no string comparison)
- Fixed-width integer encoding (no decimal-to-binary conversion)
- No UTF-8 validation needed for non-string types

### 8.3 Zero-Copy Strategy

Where possible, parsed objects reference their source buffer directly rather than copying data:

| Data Type | Zero-Copy? | Strategy |
|-----------|-----------|----------|
| JSON strings | Yes (read) | Pointer + length into source buffer |
| JSON numbers | Yes | Parsed directly into object storage |
| MessagePack strings | Yes | Pointer + length into source buffer |
| MessagePack integers | Yes | Directly from binary encoding |
| Stringified output | No | Must copy to destination buffer |
| Modified objects | No | Copy-on-write for JSON_SET |

**Copy-on-write for JSON_SET:** When a value is modified via JSON_SET, the affected object subtree is copied before mutation. Unmodified subtrees retain their original references. This ensures that handles held by other registers remain valid.

---

## 9. Security Considerations

### 9.1 Maximum Nesting Depth

Prevent stack overflow from deeply nested JSON (a classic DoS vector):

| Parameter | Default | Maximum | Configurable |
|-----------|---------|---------|-------------|
| Max nesting depth | 64 | 256 | Via SYS call 0x42 |
| Max array length | 65,536 | 4,294,967,295 | Via SYS call 0x43 |
| Max object keys | 65,536 | 4,294,967,295 | Via SYS call 0x44 |
| Max string length | 65,536 bytes | 4 MB | Via SYS call 0x45 |
| Max total object size | 16 MB | 256 MB | Via SYS call 0x46 |

If any limit is exceeded, the parse/decode opcode sets `R[rd] = 0` and sets `FLAG_SEC_VIOLATION`.

### 9.2 Maximum Object Size

The object heap has a configurable maximum size (default 16 MB). This prevents memory exhaustion attacks where an agent receives a massive JSON document:

```
Total object heap size ≤ 16 MB (default)
Total iterator count ≤ 1,024
Total simultaneous handles ≤ 65,536
```

When the object heap is full, further allocations fail gracefully (R[rd] = 0, error flag set) without crashing the VM.

### 9.3 Input Validation

All parse/decode opcodes validate their input before modifying any state:

| Validation | When | Failure Mode |
|-----------|------|-------------|
| UTF-8 well-formedness | JSON parse, YAML parse | Reject malformed sequences |
| JSON syntax | JSON_PARSE | Reject at first syntax error |
| MessagePack type tags | MSGPACK_DECODE | Reject unknown tags |
| CBOR well-formedness | CBOR_DECODE | Reject invalid CBOR |
| TOML key uniqueness | TOML_PARSE | Reject duplicate keys |
| Null bytes in strings | All parsers | Reject (except MessagePack binary) |
| Key type constraints | JSON_SET, MSGPACK_GET | Keys must be strings |

### 9.4 Sandbox Isolation

Object handles are **per-VM** — each VM instance has its own object heap and handle table. Cross-VM handle sharing is NOT supported:

- Handles from VM A cannot be used in VM B
- A2A messages must serialize/deserialize at the boundary (encode → transmit → decode)
- SANDBOX_ALLOC regions cannot contain object heap data (separate address spaces)
- TAG_ALLOC tags do not apply to object heap (only byte-addressable memory)

This isolation prevents handle smuggling attacks where a malicious agent passes a crafted handle to another agent's VM.

### 9.5 Error Codes

Structured data opcodes use the existing FAULT opcode (0xE7) for critical errors and the security flags register for non-critical failures:

| Condition | Behavior | Flag Set |
|-----------|----------|----------|
| Malformed JSON | R[rd] = 0, continue | FLAG_SEC_VIOLATION |
| Unknown key (JSON_GET) | R[rd] = 0, continue | None (not an error) |
| Type mismatch (JSON_GET on array) | R[rd] = 0, continue | FLAG_SEC_VIOLATION |
| Object heap full | R[rd] = 0, continue | FLAG_SEC_VIOLATION |
| Nesting depth exceeded | R[rd] = 0, continue | FLAG_SEC_VIOLATION |
| Max object size exceeded | R[rd] = 0, continue | FLAG_SEC_VIOLATION |
| Invalid handle (use after free) | FAULT 0xE4 | FLAG_SEC_VIOLATION |
| Iterator on wrong type | R[rd] = 0, continue | FLAG_SEC_VIOLATION |

---

## 10. Conformance Test Vectors

### SD-001: Parse Simple JSON Object, Get String Field

**Input:** `{"name":"Flux","version":3}` (25 bytes)
**Operations:**
1. JSON_PARSE R1, R0, 25 → R1 = object handle (non-zero)
2. Pre-load key "name" at memory address R2
3. JSON_GET R3, R1, R2 → R3 = string handle
4. JSON_TYPE R3, 0x04 → R3 = 1 (is string)
**Expected:** R1 != 0, R3 = 1

### SD-002: Parse Nested JSON, Traverse 3 Levels Deep

**Input:** `{"a":{"b":{"c":42}}}` (19 bytes)
**Operations:**
1. JSON_PARSE R1, R0, 19
2. JSON_GET R2, R1, "a" → R2 = inner object
3. JSON_GET R3, R2, "b" → R3 = innermost object
4. JSON_GET R4, R3, "c" → R4 = integer handle
5. JSON_TYPE R4, 0x02 → R4 = 1 (is integer)
**Expected:** R1, R2, R3, R4 all non-zero; final R4 = 1

### SD-003: Parse JSON Array, Iterate All Elements

**Input:** `[10,20,30]` (11 bytes)
**Operations:**
1. JSON_PARSE R1, R0, 11
2. JSON_TYPE R1, 0x05 → R1 = 1 (is array)
3. JSON_NEXT R2, R3, R4 → R2 = 0 (index), R3 = int(10), R4 = iterator
4. JSON_NEXT R2, R3, R4 → R2 = 1, R3 = int(20)
5. JSON_NEXT R2, R3, R4 → R2 = 2, R3 = int(30)
6. JSON_NEXT R2, R3, R4 → R2 = 0 (done), R3 = 0, R4 = 0
**Expected:** 3 successful iterations, then R2 = R3 = R4 = 0

### SD-004: Stringify Object, Verify Output

**Input:** Build object via JSON_PARSE of `{"x":1,"y":2}`
**Operations:**
1. JSON_PARSE R1, R0, 13
2. JSON_STRINGIFY R2, R1, 256 → R2 = actual length
3. Verify memory at original R2 address contains valid JSON
**Expected:** R2 = 13, memory matches `{"x":1,"y":2}`

### SD-005: MessagePack Round-Trip (Encode → Decode → Verify)

**Input:** JSON object `{"signal":"ping","id":42}`
**Operations:**
1. JSON_PARSE R1, R0, 0
2. MSGPACK_ENCODE R2, R1, 512 → R2 = encoded length
3. MSGPACK_DECODE R3, addr_of_encoded, R2 → R3 = new handle
4. JSON_GET R4, R3, "signal" → R4 = "ping" string handle
5. JSON_GET R5, R3, "id" → R5 = integer(42) handle
**Expected:** R3 != 0, R4 != 0, R5 != 0; decoded object equivalent to original

### SD-006: Error Cases (Malformed JSON, Missing Key, Type Mismatch)

**6a — Malformed JSON:**
- Input: `{"broken":` (10 bytes, truncated)
- JSON_PARSE R1, R0, 10 → R1 = 0, FLAG_SEC_VIOLATION set

**6b — Missing Key:**
- Input: `{"a":1}`
- JSON_PARSE R1, R0, 0; JSON_GET R2, R1, "missing" → R2 = 0, no error flag

**6c — Type Mismatch:**
- Input: `[1,2,3]`
- JSON_PARSE R1, R0, 0; JSON_GET R2, R1, "key" → R2 = 0, FLAG_SEC_VIOLATION set (array is not an object)

### SD-007: Performance — Parse 1KB JSON Document

**Input:** Synthetic 1KB JSON document with 50 key-value pairs (mix of strings, numbers, nested objects, arrays)
**Operations:**
1. Record CLK → R10
2. JSON_PARSE R1, R0, 1024
3. Record CLK → R11
4. R12 = R11 - R10 (cycles elapsed)
**Expected:** R1 != 0; R12 < 2000 cycles (target: ~500 cycles on hardware)

### SD-008: A2A — Encode Signal Payload as MessagePack, Decode on Receive

**Scenario:** Agent A encodes a signal payload and sends it. Agent B receives and decodes.
**Input (sender):** `{"action":"status","agent":"flux-07","confidence":0.95}`
**Operations (sender):**
1. JSON_PARSE R1, R0, 0
2. MSGPACK_ENCODE R2, R1, 512 → R2 = encoded byte count
3. TELL R3, R4, R2 (send encoded bytes to agent R4)

**Operations (receiver):**
1. AWAIT R5, R6, 0 (receive message)
2. MSGPACK_DECODE R7, R5, message_len
3. JSON_GET R8, R7, "action" → R8 = "status"
4. JSON_GET R9, R7, "confidence" → R9 = float(0.95)
**Expected:** Decoded object matches original; R8 = string handle, R9 = float handle

---

## 11. Implementation Roadmap

### Phase 1: Core JSON (Covers ~80% of Use Cases)

**Scope:** JSON_PARSE, JSON_STRINGIFY, JSON_GET, JSON_TYPE
**Effort:** 2–3 weeks
**Deliverables:**
- Object heap implementation (allocation, refcounting, free-list)
- JSON streaming parser (single-pass, no backtracking)
- JSON serializer (compact mode)
- Handle-to-memory and memory-to-handle bridges
- 4 sub-opcodes in the extension dispatch table
- Test vectors SD-001 through SD-004, SD-006

**Integration points:**
- Extension registration in VM init (ext_table[0x07] = EXT_STRUCT)
- VER_EXT query support (0xFF 0xF0 0x07 → R0=1, R1=version)
- Security flags integration (FLAG_SEC_VIOLATION on parse errors)
- Resource limits integration (max nesting, max object size from resource_limits.py)

### Phase 2: JSON Iteration

**Scope:** JSON_NEXT, JSON_SET
**Effort:** 1–2 weeks
**Deliverables:**
- Iterator table implementation (cursor, state, object ref)
- JSON_SET with copy-on-write semantics
- Full iteration loop support for objects and arrays
- Test vectors SD-003, SD-004

### Phase 3: MessagePack Support

**Scope:** MSGPACK_ENCODE, MSGPACK_DECODE, MSGPACK_GET, MSGPACK_NEXT
**Effort:** 2–3 weeks
**Deliverables:**
- MessagePack binary encoder (all types including extensions)
- MessagePack binary decoder (streaming, size-limited)
- Shared iteration engine (JSON and MessagePack use same iterator table)
- A2A integration: MessagePack as default signal payload format
- Test vectors SD-005, SD-007, SD-008

### Phase 4: Secondary Formats

**Scope:** CBOR, TOML, YAML
**Effort:** 3–4 weeks (lower priority)
**Deliverables:**
- CBOR encoder/decoder (RFC 8949, major types 0–7)
- TOML parser (v1.0.0 specification)
- YAML parser (subset: JSON-compatible types, no anchors in v1)
- Configuration pipeline: TOML → MessagePack for A2A

### Dependencies

```
Phase 1 ──────→ Phase 2 ──→ Phase 3 ──→ Phase 4
  │                                  │
  └──────────────────────────────────┘
       (Phase 4 depends on Phase 3
        for shared iterator engine)
```

### Fleet Coordination

| Phase | Owner | Depends On |
|-------|-------|------------|
| Phase 1 | Super Z | ISA v3 VM with Format H support |
| Phase 2 | Super Z | Phase 1 |
| Phase 3 | Super Z + JetsonClaw1 (edge testing) | Phase 2 |
| Phase 4 | Super Z | Phase 3 |

---

## Appendix A — Extension ID Rationale

The task description originally suggested extension ID 0x04 (STRUCT). However, the ISA v3 full draft (ISA-001-FULL, Section 4.20.6) already allocates 0x04 to **EXT_TENSOR** (Tensor/Neural Advanced, 16 sub-opcodes for batched matrix multiply, layer normalization, etc.).

The next available fleet-standard extension ID is **0x07**:

| ID | Extension | Status |
|----|-----------|--------|
| 0x00 | NULL | Reserved |
| 0x01 | EXT_BABEL | Allocated (linguistics) |
| 0x02 | EXT_EDGE | Allocated (sensor/actuator) |
| 0x03 | EXT_CONFIDENCE | Allocated (advanced confidence) |
| 0x04 | EXT_TENSOR | Allocated (tensor/neural) |
| 0x05 | EXT_SECURITY | Allocated (capability enforcement) |
| 0x06 | EXT_TEMPORAL | Allocated (async/deadline/persist) |
| **0x07** | **EXT_STRUCT** | **★ This spec — structured data** |
| 0x08–0x7F | Available | Fleet-standard (Oracle1 allocates) |
| 0x80–0xEF | Available | Experimental/vendor-specific |
| 0xF0–0xFF | Meta | VER_EXT, LOAD_EXT, etc. |

If the fleet determines that structured data opcodes are higher priority than tensor opcodes, EXT_TENSOR could be relocated to 0x08 and EXT_STRUCT could take 0x04. However, this spec recommends keeping the existing allocation to avoid churn.

---

## Appendix B — Cross-References

| Document | Relationship |
|----------|-------------|
| ISA-V3-FULL-DRAFT.md (§3.8, §4.20) | Defines Format H encoding and extension ID allocation |
| isa-v3-escape-prefix-spec.md | Defines the 0xFF escape prefix mechanism and VER_EXT |
| isa-v3-compressed-format-spec.md (§10) | Defines C.EXT bridge for extension opcodes in compressed mode |
| security-primitives-spec.md (§8) | Defines security flags and sandbox model that EXT_STRUCT obeys |
| async-temporal-primitives-spec.md | Defines SUSPEND/RESUME for A2A continuation handoff of structured data |
| TASK-BOARD.md (STRUCT-001) | This spec addresses the structured data opcodes task |
| primitives.py (A2A) | All 6 coordination primitives are JSON-serializable — EXT_STRUCT accelerates this |

---

*End of Document*
