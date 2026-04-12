# FLUX ISA v3 — Escape Prefix Specification

**Document ID:** ISA-002
**Status:** Draft
**Author:** Super Z (Fleet Agent, ISA-002 Task Board)
**Date:** 2026-04-12
**Supersedes:** Section "0xFF ILLEGAL" in ISA_UNIFIED.md
**Depends On:** FLUX ISA v3 Unified Specification (isa-v3-full-draft.md)

---

## Table of Contents

1. [Introduction & Motivation](#1-introduction--motivation)
2. [Encoding Specification](#2-encoding-specification)
3. [Extension Discovery](#3-extension-discovery)
4. [Extension Registration](#4-extension-registration)
5. [Runtime Behavior](#5-runtime-behavior)
6. [Multi-Byte Extensions (Beyond 65,536)](#6-multi-byte-extensions-beyond-65536)
7. [Interaction with Compressed Format](#7-interaction-with-compressed-format)
8. [Migration Guide](#8-migration-guide)
9. [Bytecode Examples](#9-bytecode-examples)
10. [Formal Semantics](#10-formal-semantics)
11. [Security Considerations](#11-security-considerations)
12. [Appendix](#12-appendix)

---

## 1. Introduction & Motivation

### 1.1 The Opcode Exhaustion Problem

The FLUX ISA v3 unified specification defines 256 opcode slots (0x00–0xFF). Of these,
approximately 200 are assigned and 56 are reserved. The current allocation covers:

| Range      | Slots | Category                      |
|------------|-------|-------------------------------|
| 0x00–0x07  | 8     | System control / debug        |
| 0x08–0x0F  | 8     | Single-register arithmetic    |
| 0x10–0x17  | 8     | Immediate-only operations     |
| 0x18–0x1F  | 8     | Register + imm8               |
| 0x20–0x2F  | 16    | Integer arithmetic (3-reg)    |
| 0x30–0x3F  | 16    | Float / memory / control      |
| 0x40–0x47  | 8     | Register + imm16              |
| 0x48–0x4F  | 8     | Register + register + imm16   |
| 0x50–0x5F  | 16    | Agent-to-Agent (fleet ops)    |
| 0x60–0x6F  | 16    | Confidence-aware variants     |
| 0x70–0x7F  | 16    | Viewpoint operations (Babel)  |
| 0x80–0x8F  | 16    | Biology / sensor (JetsonClaw1)|
| 0x90–0x9F  | 16    | Extended math / crypto        |
| 0xA0–0xAF  | 16    | String / collection ops       |
| 0xB0–0xBF  | 16    | Vector / SIMD                 |
| 0xC0–0xCF  | 16    | Tensor / neural               |
| 0xD0–0xDF  | 16    | Extended memory / MMIO        |
| 0xE0–0xEF  | 16    | Long jumps / calls / debug    |
| 0xF0–0xFF  | 16    | Extended system / debug       |

The remaining ~56 reserved slots are insufficient for long-term growth. New domains
that demand dedicated opcodes include:

- **Quantum computing primitives** (gate application, qubit measurement, entanglement)
- **Homomorphic encryption** (encrypt/decrypt/add/multiply on ciphertexts)
- **Distributed consensus** (Raft/Paxos proposal/vote/commit)
- **Formal verification** (precondition/postcondition/assertion opcodes)
- **Knowledge graph operations** (triple store, SPARQL-like query)
- **Extended audio processing** (FFT, filter banks, codec operations)
- **Advanced regex** (compile, match, capture-group extraction)
- **Persistent memory / journaling** (WAL append, checkpoint, recovery)
- **GPU compute shaders** (dispatch, barrier, shared-memory ops)
- **Fleet orchestration** (formation control, task scheduling)

Each of these domains could require 16–64 opcodes. At this rate, the remaining
~56 slots would be exhausted within 2–3 development cycles.

### 1.2 Design Goals

The escape prefix mechanism must satisfy the following requirements:

1. **Backward compatibility**: ISA v3 bytecode without extensions must execute
   unchanged on all conformant runtimes.
2. **Massive extensibility**: Support at least 65,536 extension opcodes, with a
   path to 16,777,216+ for extreme use cases.
3. **Deterministic decoding**: The decoder must unambiguously distinguish core
   opcodes from escape sequences in a single forward pass.
4. **Efficient encoding**: Extension opcodes should add no more than 1 byte of
   overhead per instruction compared to core opcodes.
5. **Graceful degradation**: Runtimes that don't support a particular extension
   must provide clear, actionable error messages rather than silent misbehavior.
6. **Zero-cost for non-users**: Runtimes that don't use any extensions should
   pay no performance penalty for the escape mechanism.
7. **Composable extensions**: Multiple extensions must coexist without
   interference, and extensions must not depend on the registration order.
8. **Versioned**: Extensions must carry version metadata for forward
   compatibility.

### 1.3 Relationship to Prior Art

The FLUX escape prefix draws inspiration from several precedents while being
tailored to the FLUX ecosystem:

| Precedent          | Mechanism                          | FLUX Difference                    |
|--------------------|------------------------------------|------------------------------------|
| x86 `0x0F` prefix  | 2-byte escape to extended opcodes  | FLUX uses 0xFF as a single escape  |
| WASM              | LEB128-encoded section IDs         | FLUX uses fixed-width for speed    |
| RISC-V            | Custom extensions in opcode space  | FLUX centralizes via single prefix |
| JVM               | `wide` prefix for wider operands   | FLUX extends opcodes, not operands |
| WebAssembly        | Multi-byte opcodes via LEB128      | FLUX is fixed 2/4 byte escape      |

### 1.4 Specification Conventions

Throughout this document:

- `0xFF` refers to the single byte with all bits set (binary `11111111`).
- `imm8` is an unsigned 8-bit immediate value.
- `imm16` is a 16-bit value stored in little-endian order (low byte first).
- `imm24` is a 24-bit value stored in little-endian order.
- `rd`, `rs1`, `rs2` are register specifiers (0–255).
- Byte diagrams use `|` delimiters and `:` for bit fields within a byte.
- All multi-byte values are little-endian unless otherwise noted.
- Pseudocode uses Python-like syntax with type annotations.

---

## 2. Encoding Specification

### 2.1 Overview: The 0xFF Escape Byte

In ISA v3, the opcode `0xFF` was previously defined as `ILLEGAL` (illegal
instruction trap). Under this specification, `0xFF` is **repurposed** as the
escape prefix byte. When the decoder encounters `0xFF`, it does NOT treat it as
a standalone instruction. Instead, it reads the next byte(s) to determine the
full extension opcode.

```
Before (ISA v3 without escape):
  0xFF          → ILLEGAL trap (Format A, 1 byte)

After (ISA v3 with escape):
  0xFF XX       → Extension opcode 0xFFXX (2 bytes total prefix)
  0xFF FF XX YY → Extension opcode 0xFFFFXXYY (4 bytes total prefix)
```

This is a **breaking change** from the perspective that `0xFF` as a standalone
byte (followed by nothing, or followed by another instruction) now has different
semantics. However, no legitimate FLUX bytecode should contain a bare `0xFF`
opcode, since it previously always caused an illegal instruction trap. The
migration strategy is detailed in Section 8.

### 2.2 Two-Level Escape: Primary (0xFF + imm8)

The primary escape mechanism uses a 2-byte prefix:

```
┌─────────┬─────────┐
│  0xFF   │  ext8   │
│ (escape)│ (ext)   │
└─────────┴─────────┘
  byte 0    byte 1

Full opcode: 0xFF00 – 0xFFFF (65,536 opcodes)
```

- **byte 0**: Always `0xFF` (escape sentinel).
- **byte 1**: `ext8` — the extension byte. Range `0x00`–`0xFF`.

The composite opcode is the 16-bit value `(0xFF << 8) | ext8`, yielding the
range `0xFF00`–`0xFFFF` for a total of **256 primary extension opcodes**.

After the 2-byte escape prefix, the remaining instruction bytes follow the
standard FLUX format encoding (Formats A through G), exactly as if the composite
opcode were a single-byte opcode in the `0x00`–`0xFE` range.

**Total instruction sizes with primary escape:**

| Base Format | Escape Prefix | Operands         | Total Bytes |
|-------------|---------------|------------------|-------------|
| Format A    | 2 bytes       | 0 bytes          | 2           |
| Format B    | 2 bytes       | 1 byte (rd)      | 3           |
| Format C    | 2 bytes       | 1 byte (imm8)    | 3           |
| Format D    | 2 bytes       | 2 bytes          | 4           |
| Format E    | 2 bytes       | 3 bytes          | 5           |
| Format F    | 2 bytes       | 3 bytes          | 5           |
| Format G    | 2 bytes       | 4 bytes          | 6           |

The format of the operand bytes is determined by the extension's opcode
definition, stored in the extension manifest (see Section 3). The decoder
must consult the manifest to determine how many additional bytes to consume.

### 2.3 Format Encoding After Escape

The format byte is encoded as the **high nibble of the extension byte** in
compact form, or as the first operand byte in explicit form. Two sub-modes are
defined:

#### 2.3.1 Implicit Format Mode (Recommended)

In this mode, the extension manifest declares the format for each opcode.
The decoder looks up the format from the manifest and reads the appropriate
number of additional bytes:

```
Pseudocode:
  def decode_instruction(bytecode, pc):
      op0 = bytecode[pc]
      if op0 == 0xFF:
          # Escape prefix
          ext = bytecode[pc + 1]
          composite = (0xFF << 8) | ext
          # Look up format in extension manifest
          fmt = manifest.lookup_format(composite)
          # Decode operands based on fmt
          operands = decode_operands(bytecode, pc + 2, fmt)
          return DecodedInstruction(composite, fmt, operands, size=2+operand_size)
      else:
          # Standard core opcode
          return decode_core_instruction(bytecode, pc)
```

#### 2.3.2 Explicit Format Mode (Backward-Compatible)

For runtimes that cannot consult a manifest (e.g., minimal interpreters,
disassemblers operating on raw bytecode), the format is encoded in the byte
immediately following the extension byte:

```
┌─────────┬─────────┬─────────┬───────────────────────┐
│  0xFF   │  ext8   │ fmt_byte│ operand bytes...      │
│ (escape)│ (ext)   │ (0-7)   │                       │
└─────────┴─────────┴─────────┴───────────────────────┘
  byte 0    byte 1    byte 2    byte 3+

fmt_byte encoding:
  0 = Format A (0 additional operand bytes)
  1 = Format B (1 byte: rd)
  2 = Format C (1 byte: imm8)
  3 = Format D (2 bytes: rd + imm8)
  4 = Format E (3 bytes: rd + rs1 + rs2)
  5 = Format F (3 bytes: rd + imm16)
  6 = Format G (4 bytes: rd + rs1 + imm16)
  7 = Reserved for future format
```

This mode adds 1 extra byte per extension instruction but requires no manifest
lookup. It is the **safest default** for new extensions.

**Recommendation:** New extensions SHOULD use implicit format mode with a
manifest. Explicit format mode SHOULD be used when the extension must be
decodable without a manifest (e.g., for standalone `.flux` binaries distributed
without metadata).

### 2.4 Opcode Space Topology

The full opcode space with the escape mechanism is:

```
0x0000 ┌────────────────────────────────────┐
      │     Core ISA (254 opcodes)         │
      │     0x00–0xFE                      │
0x00FE ├────────────────────────────────────┤
      │     (0xFF = escape prefix)          │
0x00FF ├────────────────────────────────────┤
      │     Primary Extension Layer        │
      │     0xFF00–0xFFFE (255 opcodes)    │
      │     0xFFFF = multi-byte escape     │
0xFFFF ├────────────────────────────────────┤
      │     Secondary Extension Layer      │
      │     0xFFFF0000–0xFFFFFFFE          │
      │     (16,777,214 opcodes)           │
0xFFFFFFFE ─────────────────────────────────┤
      │     (0xFFFFFFFF = reserved)        │
0xFFFFFFFF ─────────────────────────────────┘
```

### 2.5 Reserved Extension Opcodes

Within the primary extension layer, certain values are reserved:

| Opcode    | Name                  | Purpose                                     |
|-----------|-----------------------|---------------------------------------------|
| 0xFF00    | `EXT_NOP`             | No-operation within extension space          |
| 0xFF01    | `EXT_MANIFEST`        | Inline manifest declaration (see Section 3)  |
| 0xFF02    | `EXT_QUERY`           | Query if extension is supported              |
| 0xFF03    | `EXT_REQUIRE`         | Require extension or trap                    |
| 0xFF04    | `EXT_VERSION`         | Get extension version                        |
| 0xFF05    | `EXT_FALLBACK`        | Declare fallback opcode (see Section 5.4)   |
| 0xFF06    | `EXT_GUARD`           | Conditional: execute only if ext supported   |
| 0xFF07    | `EXT_CAPS`            | Query extension capabilities                 |
| 0xFF08–0xFF0F | Reserved          | Reserved for escape mechanism internals     |
| 0xFF10–0xFF1F | Reserved          | Reserved for FLUX standard extensions       |
| 0xFFFF    | `EXT_ESCAPE2`         | Multi-byte escape prefix (see Section 6)     |

All remaining values in the range `0xFF20`–`0xFFFE` are available for
user-defined extensions.

### 2.6 Binary Encoding Diagrams

#### Example: Extension Format E (3-register) Instruction

```
Extension opcode 0xFF42, Format E (rd=r3, rs1=r1, rs2=r5):

Byte offset:  0     1     2     3     4
           ┌─────┬─────┬─────┬─────┬─────┐
Value:     │ 0xFF │ 0x42│ 0x03│ 0x01│ 0x05│
           └─────┴─────┴─────┴─────┴─────┘
            esc   ext   rd    rs1   rs2

Reading: "Execute extension opcode 0xFF42 with r3 = r1 OP r5"
```

#### Example: Extension Format F (register + imm16) Instruction

```
Extension opcode 0xFF80, Format F (rd=r2, imm16=0x1234):

Byte offset:  0     1     2     3     4     5
           ┌─────┬─────┬─────┬─────┬─────┬─────┐
Value:     │ 0xFF │ 0x80│ 0x02│ 0x34│ 0x12│     │
           └─────┴─────┴─────┴─────┴─────┴─────┘
            esc   ext   rd    imm16_lo imm16_hi

Reading: "Execute extension 0xFF80 with r2 = imm16(0x1234)"
```

#### Example: Extension Format G (register + register + imm16) Instruction

```
Extension opcode 0xFFC0, Format G (rd=r4, rs1=r7, imm16=0x00FF):

Byte offset:  0     1     2     3     4     5     6
           ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
Value:     │ 0xFF │ 0xC0│ 0x04│ 0x07│ 0xFF│ 0x00│     │
           └─────┴─────┴─────┴─────┴─────┴─────┴─────┘
            esc   ext   rd    rs1   imm16_lo imm16_hi

Reading: "Execute extension 0xFFC0 with r4, r7, offset 0x00FF"
```

#### Example: Explicit Format Mode

```
Extension opcode 0xFF42, Explicit Format E (rd=r3, rs1=r1, rs2=r5):

Byte offset:  0     1     2     3     4     5
           ┌─────┬─────┬─────┬─────┬─────┬─────┐
Value:     │ 0xFF │ 0x42│ 0x04│ 0x03│ 0x01│ 0x05│
           └─────┴─────┴─────┴─────┴─────┴─────┘
            esc   ext   fmt   rd    rs1   rs2

fmt=0x04 → Format E
```

---

## 3. Extension Discovery

### 3.1 The Extension Manifest

Every FLUX bytecode module that uses extension opcodes MUST include an
**Extension Manifest** — a structured block of metadata that declares which
extensions are required, optional, and provides the format table for each
extension opcode.

The manifest can be embedded in the bytecode header or shipped as a separate
file. Both approaches are described below.

### 3.1.1 Embedded Manifest (Bytecode Header)

The FLUX bytecode file format is extended with a new section type in the header:

```
FLUX Bytecode File Structure:

┌────────────────────────────────────┐
│ Magic: 0x464C5558 ("FLUX")        │  4 bytes
├────────────────────────────────────┤
│ Version: 0x03 (ISA v3)            │  1 byte
├────────────────────────────────────┤
│ Header Length: (variable)          │  2 bytes (LE)
├────────────────────────────────────┤
│ Header Sections:                   │  variable
│   ┌────────────────────────────┐  │
│   │ Section Type: 0x01         │  │  1 byte
│   │ Section Length: N          │  │  2 bytes (LE)
│   │ Section Data: ...          │  │  N bytes
│   └────────────────────────────┘  │
│   ┌────────────────────────────┐  │
│   │ Section Type: 0x02         │  │  1 byte (Code section)
│   │ Section Length: M          │  │  2 bytes (LE)
│   │ Section Data: (bytecode)   │  │  M bytes
│   └────────────────────────────┘  │
│   ┌────────────────────────────┐  │
│   │ Section Type: 0x05         │  │  1 byte (EXTENSION MANIFEST)
│   │ Section Length: P          │  │  2 bytes (LE)
│   │ Section Data: (manifest)   │  │  P bytes (see below)
│   └────────────────────────────┘  │
├────────────────────────────────────┤
│ Entry Point Offset                  │  4 bytes (LE)
└────────────────────────────────────┘
```

**Section type `0x05`** is the Extension Manifest section. Its format is:

```
Extension Manifest Section:

┌────────────────────────────────────────────┐
│ num_extensions: u16 (LE)                  │  Number of extensions
├────────────────────────────────────────────┤
│ Extension Entry 1:                         │
│   ┌──────────────────────────────────┐    │
│   │ ext_id: u32 (LE)                 │    │  Extension group ID
│   │ ext_version_major: u8            │    │  Major version
│   │ ext_version_minor: u8            │    │  Minor version
│   │ ext_name_len: u8                 │    │  Length of name string
│   │ ext_name: bytes[ext_name_len]    │    │  UTF-8 name (e.g., "crypto")
│   │ opcode_base: u16 (LE)            │    │  First opcode in group
│   │ opcode_count: u16 (LE)           │    │  Number of opcodes
│   │ required: u8 (0=opt, 1=req)     │    │  Required flag
│   │ fallback_present: u8 (0/1)      │    │  Has fallback table?
│   │ format_table: bytes               │    │  Format declarations (see 3.1.3)
│   │   num_opcodes: u16 (LE)          │    │  (repeats opcode_count times)
│   │   opcode_offset: u16             │    │  Offset from opcode_base
│   │   format: u8                     │    │  0=A,1=B,2=C,3=D,4=E,5=F,6=G
│   │   ...                            │    │
│   │ fallback_table: bytes (optional)  │    │  Fallback opcodes (see 5.4)
│   └──────────────────────────────────┘    │
│ Extension Entry 2:                         │
│   ...                                     │
└────────────────────────────────────────────┘
```

### 3.1.2 External Manifest (Separate File)

When the manifest is shipped as a separate file, it uses the `.fluxext` extension:

```
filename.fluxext  →  Extension manifest for filename.flux
```

The external manifest uses the same binary format as the embedded manifest
section, with an additional wrapper:

```
External Manifest File:

┌────────────────────────────────────┐
│ Magic: 0x464C5854 ("FLXT")        │  4 bytes
│ Version: 0x01                     │  1 byte
│ associated_bytecode_hash: bytes   │  32 bytes (SHA-256 of bytecode)
├────────────────────────────────────┤
│ Manifest data (same as 3.1.1)      │
└────────────────────────────────────┘
```

The `associated_bytecode_hash` field ensures that the manifest cannot be
accidentally applied to the wrong bytecode module. Runtimes MUST verify this
hash before loading an external manifest.

### 3.1.3 Format Table Encoding

The format table is a compact binary representation of which instruction format
each extension opcode uses. Each entry is 3 bytes:

```
Format Table Entry:

  Bits:
  ┌──────────────────────┬──────────────────────┬──────────────────────┐
  │    opcode_offset     │       format         │       reserved       │
  │      (16 bits)       │      (6 bits)        │      (2 bits)        │
  └──────────────────────┴──────────────────────┴──────────────────────┘
  MSB                                                                 LSB

  Encoding in bytes (little-endian):
  byte 0: opcode_offset[7:0]
  byte 1: opcode_offset[15:8]
  byte 2: format[5:0] | reserved[1:0]

  format values:
    0 = Format A (no operands)
    1 = Format B (rd only)
    2 = Format C (imm8 only)
    3 = Format D (rd + imm8)
    4 = Format E (rd + rs1 + rs2)
    5 = Format F (rd + imm16)
    6 = Format G (rd + rs1 + imm16)
    63 = Format VAR (variable-length, decoder reads length prefix)
```

### 3.2 Runtime Extension Query Protocol

When a FLUX runtime loads a bytecode module, it MUST perform the following
discovery sequence:

```
Pseudocode: Runtime extension discovery

def load_bytecode_module(path: str) -> Module:
    # 1. Parse header, extract all sections
    header = parse_header(path)
    manifest_section = header.get_section(0x05)
    code_section = header.get_section(0x02)

    # 2. If manifest present, extract extension requirements
    if manifest_section:
        manifest = parse_manifest(manifest_section)
    else:
        # Check for external manifest
        ext_path = path + ".fluxext"
        if exists(ext_path):
            manifest = parse_external_manifest(ext_path)
        else:
            manifest = EmptyManifest()

    # 3. For each required extension, check runtime support
    for ext in manifest.required_extensions:
        if not runtime.has_extension(ext.ext_id, ext.ext_version):
            raise ExtensionNotSupportedError(
                ext_id=ext.ext_id,
                required_version=ext.ext_version,
                available_version=runtime.get_extension_version(ext.ext_id),
                ext_name=ext.ext_name,
            )

    # 4. For each optional extension, record availability
    for ext in manifest.optional_extensions:
        ext.supported = runtime.has_extension(ext.ext_id, ext.ext_version)

    # 5. Build dispatch table combining core + extension opcodes
    dispatch = build_dispatch_table(
        core_opcodes=CORE_OPCODE_TABLE,
        extensions=manifest,
        runtime_extensions=runtime.extension_registry,
    )

    return Module(code_section, manifest, dispatch)
```

### 3.3 Capability Negotiation Between Agents

In the FLUX fleet architecture, agents communicate via the A2A protocol
(TELL/ASK/DELEG opcodes, 0x50–0x5F). When agents exchange bytecode or
delegate tasks involving extension opcodes, they negotiate capabilities
using a dedicated handshake:

```
Agent A                          Agent B
  │                                │
  │──── EXT_CAPS_QUERY ──────────→│   "I need these extensions: [crypto v1, ml v2]"
  │                                │
  │                                │   (check local registry)
  │                                │
  │←─── EXT_CAPS_RESPONSE ────────│   "I support: [crypto v1 ✅, ml v1 ⚠️ (v2 needed)]"
  │                                │
  │   (decide: proceed/fallback)   │
  │                                │
  │──── DELEG bytecode ──────────→│   (with or without fallbacks)
  │                                │
```

The capability negotiation uses the following message types (encoded as A2A
signal payloads):

```
EXT_CAPS_QUERY message format:
  ┌────────────┬────────────┬──────────────────────────────┐
  │ num_exts   │ ext_id[0]  │ version_major, version_minor │  ...
  │ u16        │ u32        │ u8, u8                       │
  └────────────┴────────────┴──────────────────────────────┘
  Repeats num_exts times.

EXT_CAPS_RESPONSE message format:
  ┌────────────┬────────────┬────────────┬──────────────────────┐
  │ num_exts   │ ext_id[0]  │ status     │ available_major/min  │  ...
  │ u16        │ u32        │ u8         │ u8, u8               │
  └────────────┴────────────┴────────────┴──────────────────────┘

  status values:
    0x00 = SUPPORTED_EXACT     (exact version match)
    0x01 = SUPPORTED_NEWER     (runtime has newer version)
    0x02 = SUPPORTED_OLDER     (runtime has older, may work)
    0x03 = NOT_SUPPORTED       (extension not available)
    0x04 = BLACKLISTED         (extension available but disabled)
```

### 3.4 Graceful Degradation

When a runtime encounters an extension opcode it does not support, it MUST NOT
silently ignore the instruction. Instead, it follows a deterministic degradation
path:

```
Pseudocode: Graceful degradation

def execute_extension_opcode(opcode: int, operands, manifest, runtime):
    ext_id = manifest.lookup_extension_group(opcode)
    ext_entry = manifest.get_extension(ext_id)

    if runtime.has_extension(ext_id, ext_entry.version):
        # Fast path: extension is supported
        handler = runtime.get_extension_handler(ext_id)
        return handler.execute(opcode, operands)

    elif ext_entry.has_fallback:
        # Medium path: fallback available
        fallback_opcode = ext_entry.get_fallback(opcode)
        return execute_core_opcode(fallback_opcode, operands)

    elif ext_entry.required:
        # Hard path: required extension missing → trap
        raise Trap(
            trap_code=TRAP_EXTENSION_REQUIRED,
            message=f"Required extension '{ext_entry.name}' "
                    f"v{ext_entry.version} not available",
            opcode=opcode,
            ext_id=ext_id,
            severity=TrapSeverity.FATAL,
        )

    else:
        # Soft path: optional extension missing → log + skip or stub
        runtime.logger.warning(
            f"Optional extension '{ext_entry.name}' opcode 0x{opcode:04X} "
            f"not supported, skipping"
        )
        return None  # Instruction is a no-op
```

---

## 4. Extension Registration

### 4.1 Extension Group Architecture

Extensions are organized into **extension groups**, each identified by a 32-bit
`ext_id`. A group is a named collection of related opcodes that share a common
purpose (e.g., cryptography, machine learning, audio processing).

```
Extension Group Structure:

  ext_id:     0x00000001        (32-bit unique identifier)
  ext_name:   "crypto"          (human-readable name, UTF-8)
  version:    1.2               (major.minor)
  opcode_base: 0xFF20           (first opcode in this group)
  opcode_count: 32              (number of opcodes in group)
  opcodes:
    0xFF20: SHA3_256      Format E (rd, rs1, rs2)
    0xFF21: SHA3_512      Format E (rd, rs1, rs2)
    0xFF22: BLAKE2B       Format E (rd, rs1, rs2)
    ...
    0xFF3F: ECDH_SHARED   Format E (rd, rs1, rs2)
```

### 4.2 Naming Convention

Extension names MUST follow reverse-DNS style naming to avoid collisions:

```
Pattern:  vendor.domain.category

Examples:
  org.flux.crypto          → FLUX standard crypto extensions
  org.flux.ml              → FLUX standard ML extensions
  com.nvidia.cuda          → NVIDIA CUDA interop extensions
  io.quantum.qiskit        → IBM Qiskit quantum extensions
  dev.local.experimental   → Local experimental extensions

Short aliases (for use in assembly/disassembly):
  crypto    → org.flux.crypto
  ml        → org.flux.ml
  cuda      → com.nvidia.cuda
  quant     → io.quantum.qiskit
```

### 4.3 Extension ID Assignment

Extension IDs are assigned from a centralized registry. The ID space is divided:

| Range              | Purpose                                | Authority   |
|--------------------|----------------------------------------|-------------|
| 0x00000000         | Reserved / null                        | FLUX Core   |
| 0x00000001–0x0000FFFF | FLUX standard extensions            | FLUX Core   |
| 0x00010000–0x000FFFFF | Reserved for major partners         | Fleet Board |
| 0x00100000–0x00FFFFFF | Community extensions                 | Open Reg    |
| 0x01000000–0xFFFFFFFF | Private / experimental            | Self-assigned|

Self-assigned IDs MUST use a hash of the full reverse-DNS name to minimize
collision probability:

```
def compute_ext_id(name: str) -> int:
    """Compute a self-assigned extension ID from a reverse-DNS name."""
    import hashlib
    digest = hashlib.sha256(name.encode('utf-8')).digest()
    # Take first 4 bytes, set top bit to mark as self-assigned
    value = int.from_bytes(digest[:4], 'big')
    return value | 0x80000000

# Examples:
# "dev.local.myext" → 0x8A3F2B1C (deterministic from name)
# "com.example.quantum" → 0x9D4E5F6A (deterministic from name)
```

### 4.4 Standard Extension Group Allocations

The following standard extension groups are pre-allocated in the primary
extension layer (0xFF10–0xFFFE):

#### 4.4.1 Reserved Standard Extensions (0xFF10–0xFF1F)

| Opcode Range | Group ID | Name      | Version | Status      | Opcodes                                       |
|-------------|----------|-----------|---------|-------------|-----------------------------------------------|
| 0xFF10–0xFF1F | 0x00000001 | `std.meta` | 1.0 | Draft       | Extension introspection opcodes                |

#### 4.4.2 Cryptography Extensions (0xFF20–0xFF3F)

| Opcode Range | Group ID | Name      | Version | Status      | Description                                   |
|-------------|----------|-----------|---------|-------------|-----------------------------------------------|
| 0xFF20–0xFF3F | 0x00000002 | `crypto` | 1.0 | Draft       | Advanced cryptographic primitives              |

Detailed opcode table for `crypto` extension:

| Opcode   | Mnemonic   | Format | Operands       | Description                              |
|----------|------------|--------|----------------|------------------------------------------|
| 0xFF20   | SHA3_256   | E      | rd, rs1, rs2   | SHA3-256: msg rs1, len rs2 → digest rd  |
| 0xFF21   | SHA3_512   | E      | rd, rs1, rs2   | SHA3-512: msg rs1, len rs2 → digest rd  |
| 0xFF22   | BLAKE2B    | E      | rd, rs1, rs2   | BLAKE2b: msg rs1, len rs2 → hash rd     |
| 0xFF23   | BLAKE2S    | E      | rd, rs1, rs2   | BLAKE2s: msg rs1, len rs2 → hash rd     |
| 0xFF24   | CHACHA20   | E      | rd, rs1, rs2   | ChaCha20: encrypt rs1 with key rs2 → rd |
| 0xFF25   | POLY1305   | E      | rd, rs1, rs2   | Poly1305 MAC: msg rs1, key rs2 → tag rd |
| 0xFF26   | AES_ENC    | E      | rd, rs1, rs2   | AES encrypt block rs1 with key rs2      |
| 0xFF27   | AES_DEC    | E      | rd, rs1, rs2   | AES decrypt block rs1 with key rs2      |
| 0xFF28   | AES_GCM    | E      | rd, rs1, rs2   | AES-GCM authenticated encryption        |
| 0xFF29   | X25519     | E      | rd, rs1, rs2   | X25519 ECDH: scalar rs1, point rs2 → rd |
| 0xFF2A   | ED25519    | E      | rd, rs1, rs2   | Ed25519 sign: msg rs1, key rs2 → sig rd |
| 0xFF2B   | ED_VERIFY  | E      | rd, rs1, rs2   | Ed25519 verify: sig rs1, msg rs2 → rd   |
| 0xFF2C   | HKDF       | E      | rd, rs1, rs2   | HKDF: salt rs1, ikm rs2 → prk rd       |
| 0xFF2D   | PBKDF2     | E      | rd, rs1, rs2   | PBKDF2: pass rs1, salt rs2 → key rd    |
| 0xFF2E   | RSA_SIGN   | E      | rd, rs1, rs2   | RSA sign: hash rs1, key rs2 → sig rd    |
| 0xFF2F   | RSA_VERIFY | E      | rd, rs1, rs2   | RSA verify: sig rs1, hash rs2 → rd      |
| 0xFF30–0xFF3F | Reserved | —     | —              | Reserved for future crypto extensions    |

#### 4.4.3 Machine Learning Extensions (0xFF40–0xFF5F)

| Opcode Range | Group ID | Name    | Version | Status      | Description                          |
|-------------|----------|---------|---------|-------------|--------------------------------------|
| 0xFF40–0xFF5F | 0x00000003 | `ml` | 1.0     | Draft       | Machine learning inference primitives |

Detailed opcode table for `ml` extension:

| Opcode   | Mnemonic    | Format | Operands       | Description                                  |
|----------|-------------|--------|----------------|----------------------------------------------|
| 0xFF40   | ML_MATMUL   | E      | rd, rs1, rs2   | Matrix multiply: rd = rs1 @ rs2               |
| 0xFF41   | ML_CONV2D   | E      | rd, rs1, rs2   | 2D convolution with stride/padding            |
| 0xFF42   | ML_BATCHNORM| E      | rd, rs1, rs2   | Batch normalization: rd = BN(rs1, rs2)        |
| 0xFF43   | ML_LAYERNORM| E      | rd, rs1, rs2   | Layer normalization: rd = LN(rs1, rs2)        |
| 0xFF44   | ML_DROPOUT  | E      | rd, rs1, rs2   | Dropout: rd = dropout(rs1, rate=rs2)          |
| 0xFF45   | ML_SOFTMAX  | E      | rd, rs1, rs2   | Softmax over axis rs2: rd = softmax(rs1)      |
| 0xFF46   | ML_SIGMOID  | E      | rd, rs1, rs2   | Element-wise sigmoid                          |
| 0xFF47   | ML_TANH     | E      | rd, rs1, rs2   | Element-wise tanh                             |
| 0xFF48   | ML_RELU     | E      | rd, rs1, rs2   | ReLU activation: rd = max(0, rs1)             |
| 0xFF49   | ML_GELU     | E      | rd, rs1, rs2   | GELU activation                               |
| 0xFF4A   | ML_ATTENTION| E      | rd, rs1, rs2   | Multi-head self-attention (Q=rs1, K=V=rs2)    |
| 0xFF4B   | ML_EMBED    | E      | rd, rs1, rs2   | Embedding lookup: token rs1, table rs2        |
| 0xFF4C   | ML_POSITION | E      | rd, rs1, rs2   | Positional encoding: pos rs1, dim rs2         |
| 0xFF4D   | ML_CROSS_ENT| E      | rd, rs1, rs2   | Cross-entropy loss: pred rs1, target rs2      |
| 0xFF4E   | ML_SGD_STEP | E      | rd, rs1, rs2   | SGD update: rd -= rs2 * gradient(rs1)         |
| 0xFF4F   | ML_ADAM     | E      | rd, rs1, rs2   | Adam optimizer step                           |
| 0xFF50   | ML_TOPK     | E      | rd, rs1, rs2   | Top-K selection: rd = topk(rs1, k=rs2)        |
| 0xFF51   | ML_GATHER   | E      | rd, rs1, rs2   | Gather operation: rd[rs2[i]] = rs1[i]         |
| 0xFF52   | ML_CONCAT   | E      | rd, rs1, rs2   | Tensor concatenation along axis                |
| 0xFF53   | ML_SPLIT    | E      | rd, rs1, rs2   | Tensor split: rd = split(rs1, sections=rs2)   |
| 0xFF54   | ML_TRANSPOSE| E      | rd, rs1, rs2   | Tensor transpose by permutation rs2           |
| 0xFF55   | ML_RESHAPE  | E      | rd, rs1, rs2   | Tensor reshape: rd = reshape(rs1, shape=rs2)  |
| 0xFF56   | ML_CAST_DT  | E      | rd, rs1, rs2   | Cast data type: rd = cast(rs1, dtype=rs2)     |
| 0xFF57   | ML_QUANTIZE | E      | rd, rs1, rs2   | Quantize: rd = quantize(rs1, scale=rs2)       |
| 0xFF58   | ML_DEQUANT  | E      | rd, rs1, rs2   | Dequantize: rd = dequant(rs1, scale=rs2)      |
| 0xFF59   | ML_POOL_MAX | E      | rd, rs1, rs2   | Max pooling: rd = maxpool(rs1, params=rs2)    |
| 0xFF5A   | ML_POOL_AVG | E      | rd, rs1, rs2   | Average pooling: rd = avgpool(rs1, params=rs2)|
| 0xFF5B   | ML_UPSAMPLE | E      | rd, rs1, rs2   | Nearest/bilinear upsample                     |
| 0xFF5C   | ML_NMS      | E      | rd, rs1, rs2   | Non-maximum suppression for object detection  |
| 0xFF5D   | ML_IOU      | E      | rd, rs1, rs2   | Intersection over union                       |
| 0xFF5E   | ML_ROI_ALIGN| E      | rd, rs1, rs2   | ROI align for instance segmentation            |
| 0xFF5F   | ML_DECODE_JPEG | G   | rd, rs1, imm16 | JPEG decode: rs1=buf addr, imm16=len → tensor rd |
| 0xFF60–0xFF6F | Reserved | —     | —              | Reserved for future ML extensions              |

#### 4.4.4 Audio Processing Extensions (0xFF70–0xFF8F)

| Opcode Range | Group ID | Name    | Version | Status      | Description                        |
|-------------|----------|---------|---------|-------------|------------------------------------|
| 0xFF70–0xFF8F | 0x00000004 | `audio` | 1.0 | Draft       | Audio DSP and codec operations     |

Detailed opcode table for `audio` extension:

| Opcode   | Mnemonic    | Format | Operands       | Description                              |
|----------|-------------|--------|----------------|------------------------------------------|
| 0xFF70   | AUD_FFT     | E      | rd, rs1, rs2   | FFT: rd = FFT(rs1), size=rs2              |
| 0xFF71   | AUD_IFFT    | E      | rd, rs1, rs2   | Inverse FFT                               |
| 0xFF72   | AUD_FIR     | E      | rd, rs1, rs2   | FIR filter: rd = conv(rs1, coeffs rs2)    |
| 0xFF73   | AUD_IIR     | E      | rd, rs1, rs2   | IIR filter (biquad)                       |
| 0xFF74   | AUD_RESAMPLE| E      | rd, rs1, rs2   | Resample: rd = resample(rs1, rate rs2)    |
| 0xFF75   | AUD_VAD     | E      | rd, rs1, rs2   | Voice activity detection: rd=VAD(rs1)     |
| 0xFF76   | AUD_MFCC    | E      | rd, rs1, rs2   | MFCC feature extraction                    |
| 0xFF77   | AUD_SPECTRO | E      | rd, rs1, rs2   | Spectrogram computation                    |
| 0xFF78   | AUD_ENCODE  | E      | rd, rs1, rs2   | Encode audio: rd = encode(rs1, codec rs2) |
| 0xFF79   | AUD_DECODE  | E      | rd, rs1, rs2   | Decode audio: rd = decode(rs1, codec rs2) |
| 0xFF7A   | AUD_MIX     | E      | rd, rs1, rs2   | Mix two audio buffers                      |
| 0xFF7B   | AUD_GAIN    | E      | rd, rs1, rs2   | Apply gain: rd = rs1 * rs2                 |
| 0xFF7C   | AUD_COMPRESSOR | E  | rd, rs1, rs2   | Dynamic range compressor                   |
| 0xFF7D   | AUD_LIMITER | E      | rd, rs1, rs2   | Audio limiter                              |
| 0xFF7E   | AUD_ECHO    | E      | rd, rs1, rs2   | Echo/delay effect                          |
| 0xFF7F   | AUD_REVERB  | E      | rd, rs1, rs2   | Reverb effect                              |
| 0xFF80–0xFF8F | Reserved | —     | —              | Reserved for future audio extensions       |

#### 4.4.5 Quantum Computing Extensions (0xFF90–0xFFAF)

| Opcode Range | Group ID | Name      | Version | Status      | Description                           |
|-------------|----------|-----------|---------|-------------|---------------------------------------|
| 0xFF90–0xFFAF | 0x00000005 | `quantum` | 1.0 | Draft       | Quantum circuit primitives             |

Detailed opcode table for `quantum` extension:

| Opcode   | Mnemonic    | Format | Operands       | Description                                  |
|----------|-------------|--------|----------------|----------------------------------------------|
| 0xFF90   | Q_INIT      | E      | rd, rs1, rs2   | Initialize quantum register: rd, n_qubits=rs1 |
| 0xFF91   | Q_H         | E      | rd, rs1, rs2   | Hadamard gate on qubit rs1 of register rd     |
| 0xFF92   | Q_X         | E      | rd, rs1, rs2   | Pauli-X (NOT) gate                            |
| 0xFF93   | Q_Y         | E      | rd, rs1, rs2   | Pauli-Y gate                                  |
| 0xFF94   | Q_Z         | E      | rd, rs1, rs2   | Pauli-Z gate                                  |
| 0xFF95   | Q_CNOT      | E      | rd, rs1, rs2   | CNOT: control=rs1, target=rs2                  |
| 0xFF96   | Q_TOFFOLI   | E      | rd, rs1, rs2   | Toffoli (CCNOT) gate                           |
| 0xFF97   | Q_RX        | E      | rd, rs1, rs2   | Rotation around X axis, angle from rs2         |
| 0xFF98   | Q_RY        | E      | rd, rs1, rs2   | Rotation around Y axis                         |
| 0xFF99   | Q_RZ        | E      | rd, rs1, rs2   | Rotation around Z axis                         |
| 0xFF9A   | Q_MEASURE   | E      | rd, rs1, rs2   | Measure qubit rs1 → classical rd               |
| 0xFF9B   | Q_BARRIER   | E      | rd, rs1, rs2   | Barrier (sync all pending gates)               |
| 0xFF9C   | Q_RESET     | E      | rd, rs1, rs2   | Reset qubit rs1 to |0⟩                        |
| 0xFF9D   | Q_SWAP      | E      | rd, rs1, rs2   | SWAP qubits rs1 and rs2                        |
| 0xFF9E   | Q_CZ        | E      | rd, rs1, rs2   | Controlled-Z gate                             |
| 0xFF9F   | Q_S         | E      | rd, rs1, rs2   | S gate (√Z)                                   |
| 0xFFA0   | Q_SDG       | E      | rd, rs1, rs2   | S-dagger gate                                 |
| 0xFFA1   | Q_T         | E      | rd, rs1, rs2   | T gate (π/8)                                  |
| 0xFFA2   | Q_TDG       | E      | rd, rs1, rs2   | T-dagger gate                                 |
| 0xFFA3   | Q_PROB      | E      | rd, rs1, rs2   | Get probability of qubit rs1 → rd             |
| 0xFFA4   | Q_EXPECT    | E      | rd, rs1, rs2   | Expectation value of observable                |
| 0xFFA5   | Q_TELEPORT  | E      | rd, rs1, rs2   | Quantum teleportation protocol                |
| 0xFFA6   | Q_SUPERPOSE | E      | rd, rs1, rs2   | Create superposition: rd = α|0⟩ + β|1⟩        |
| 0xFFA7   | Q_ENTANGLE  | E      | rd, rs1, rs2   | Entangle qubits rs1 and rs2                   |
| 0xFFA8   | Q_DENSITY   | E      | rd, rs1, rs2   | Compute density matrix                        |
| 0xFFA9   | Q_DECOHERE  | E      | rd, rs1, rs2   | Apply decoherence model                       |
| 0xFFAA   | Q_ERROR_CORR| E      | rd, rs1, rs2   | Error correction code                         |
| 0xFFAB   | Q_ORACLE    | E      | rd, rs1, rs2   | Oracle for Grover's algorithm                 |
| 0xFFAC   | Q_DJ        | E      | rd, rs1, rs2   | Deutsch-Jozsa circuit                         |
| 0xFFAD   | Q_QFT       | E      | rd, rs1, rs2   | Quantum Fourier Transform                     |
| 0xFFAE   | Q_QFT_INV   | E      | rd, rs1, rs2   | Inverse QFT                                   |
| 0xFFAF   | Q_GROVER_ITER| E     | rd, rs1, rs2   | One iteration of Grover's search               |
| 0xFFB0–0xFFBF | Reserved | —     | —              | Reserved for future quantum extensions        |

### 4.5 Extension Metadata Format

Each extension group carries metadata in a standardized structure:

```python
@dataclass
class ExtensionMetadata:
    """Metadata for a registered extension group."""

    # Identity
    ext_id: int               # 32-bit unique identifier
    ext_name: str             # Reverse-DNS name (e.g., "org.flux.crypto")
    short_name: str           # Short alias (e.g., "crypto")
    version_major: int        # Major version (breaking changes)
    version_minor: int        # Minor version (additive changes)
    version_patch: int        # Patch version (bug fixes)

    # Opcode allocation
    opcode_base: int          # First opcode in group (e.g., 0xFF20)
    opcode_count: int         # Number of opcodes (e.g., 32)

    # Dependencies
    requires_extensions: list[tuple[int, int]]  # [(ext_id, min_version), ...]
    requires_hardware: list[str]                 # ["FPU", "GPU", "TPU", ...]
    requires_capabilities: list[int]             # Permission flags needed

    # Documentation
    description: str          # Human-readable description
    author: str               # Author or organization
    license: str              # SPDX license identifier
    uri: str                  # URI for specification

    # Runtime requirements
    max_memory_kb: int        # Maximum additional memory in KB
    max_execution_time_us: int  # Maximum execution time in microseconds
    is_stateless: bool        # Whether opcodes have side effects

    # Security
    permissions: int          # Required permission bitmask
    sandbox_level: int        # 0=none, 1=restricted, 2=full
```

### 4.6 Registration API (Runtime Side)

Runtimes expose a registration API for loading extensions at startup:

```python
class ExtensionRegistry:
    """Central registry for loaded extensions."""

    def __init__(self):
        self._extensions: dict[int, ExtensionMetadata] = {}
        self._handlers: dict[int, Callable] = {}
        self._dispatch: dict[int, tuple[str, Callable]] = {}

    def register(
        self,
        metadata: ExtensionMetadata,
        handler: ExtensionHandler,
    ) -> None:
        """Register an extension group with its handler."""
        # Validate: no overlap with existing registrations
        for existing_id, existing_meta in self._extensions.items():
            if opcode_ranges_overlap(
                metadata.opcode_base, metadata.opcode_count,
                existing_meta.opcode_base, existing_meta.opcode_count,
            ):
                raise RegistrationError(
                    f"Opcode range [{metadata.opcode_base:#06x}-"
                    f"{metadata.opcode_base + metadata.opcode_count - 1:#06x}] "
                    f"overlaps with extension '{existing_meta.ext_name}'"
                )

        # Validate version dependencies
        for req_id, req_version in metadata.requires_extensions:
            if req_id in self._extensions:
                if self._extensions[req_id].version_major < req_version:
                    raise RegistrationError(
                        f"Dependency '{req_id}' version {req_version} "
                        f"required, but only "
                        f"v{self._extensions[req_id].version_major} available"
                    )
            # If dependency not loaded, defer check to runtime load

        # Register
        self._extensions[metadata.ext_id] = metadata
        for i in range(metadata.opcode_count):
            opcode = metadata.opcode_base + i
            self._dispatch[opcode] = (metadata.ext_name, handler)

    def has_extension(self, ext_id: int, version: tuple[int, int]) -> bool:
        """Check if extension is available at sufficient version."""
        if ext_id not in self._extensions:
            return False
        meta = self._extensions[ext_id]
        return (meta.version_major >= version[0]) and (
            meta.version_major > version[0] or
            meta.version_minor >= version[1]
        )

    def get_handler(self, opcode: int) -> Optional[ExtensionHandler]:
        """Look up the handler for an extension opcode."""
        entry = self._dispatch.get(opcode)
        if entry is None:
            return None
        return entry[1]

    def list_extensions(self) -> list[ExtensionMetadata]:
        """List all registered extensions."""
        return list(self._extensions.values())

    def create_manifest_bytes(self) -> bytes:
        """Serialize the current registry state to manifest bytes."""
        buf = bytearray()
        buf += struct.pack('<H', len(self._extensions))
        for meta in self._extensions.values():
            name_bytes = meta.ext_name.encode('utf-8')
            buf += struct.pack('<I', meta.ext_id)
            buf += struct.pack('BB', meta.version_major, meta.version_minor)
            buf += struct.pack('B', len(name_bytes))
            buf += name_bytes
            buf += struct.pack('<HH', meta.opcode_base, meta.opcode_count)
            buf += struct.pack('B', 1)  # required=True for registered
            buf += struct.pack('B', 0)  # no fallback
            # Format table
            buf += struct.pack('<H', meta.opcode_count)
            for i in range(meta.opcode_count):
                buf += struct.pack('<HB', i, 4)  # Default to Format E
        return bytes(buf)
```

---

## 5. Runtime Behavior

### 5.1 Decoder Integration

The FLUX instruction decoder MUST be modified to handle the 0xFF escape
prefix. The following pseudocode shows the integration with the existing
decoder from `formats.py`:

```python
def decode_instruction_v3(bytecode: bytes, pc: int,
                          manifest: Optional[ExtensionManifest] = None,
                          ext_registry: Optional[ExtensionRegistry] = None
                          ) -> tuple[int, dict, int]:
    """
    Decode a single instruction from bytecode at position pc.

    Returns: (opcode, fields_dict, instruction_size)
    """
    if pc >= len(bytecode):
        raise DecodeError("Unexpected end of bytecode")

    op0 = bytecode[pc]

    # ── ESCAPE PREFIX PATH ──────────────────────────────
    if op0 == 0xFF:
        if pc + 1 >= len(bytecode):
            raise DecodeError("Truncated escape prefix at EOF")

        ext_byte = bytecode[pc + 1]
        composite_opcode = (0xFF << 8) | ext_byte

        # Check for multi-byte escape (Section 6)
        if ext_byte == 0xFF:
            return decode_multi_byte_escape(bytecode, pc)

        # Check for reserved meta-opcodes
        if ext_byte <= 0x0F:
            return decode_meta_opcode(bytecode, pc, ext_byte)

        # Look up format from manifest or registry
        fmt = resolve_extension_format(
            composite_opcode, manifest, ext_registry
        )

        # Decode operands based on format
        operand_start = pc + 2
        return _decode_with_format(composite_opcode, fmt, bytecode, operand_start)

    # ── STANDARD CORE OPCODE PATH ──────────────────────
    else:
        return decode_core_instruction(bytecode, pc)


def resolve_extension_format(
    opcode: int,
    manifest: Optional[ExtensionManifest],
    registry: Optional[ExtensionRegistry],
) -> str:
    """Determine the format of an extension opcode."""
    # Priority 1: Manifest (embedded or external)
    if manifest and manifest.has_opcode(opcode):
        return manifest.get_format(opcode)

    # Priority 2: Runtime registry
    if registry and registry.has_opcode(opcode):
        return registry.get_format(opcode)

    # Priority 3: Check for explicit format byte (next byte is 0-6)
    # (This requires lookahead — see Section 2.3.2)
    raise UnknownExtensionOpcode(opcode)


def _decode_with_format(opcode: int, fmt: str, bytecode: bytes, start: int
                        ) -> tuple[int, dict, int]:
    """Decode operand bytes for a given format."""
    remaining = len(bytecode) - start

    if fmt == 'A':
        return opcode, {"format": "A", "extension": True}, 2
    elif fmt == 'B':
        if remaining < 1:
            raise DecodeError("Truncated Format B extension instruction")
        rd = bytecode[start]
        return opcode, {"format": "B", "rd": rd, "extension": True}, 3
    elif fmt == 'C':
        if remaining < 1:
            raise DecodeError("Truncated Format C extension instruction")
        imm8 = bytecode[start]
        return opcode, {"format": "C", "imm8": imm8, "extension": True}, 3
    elif fmt == 'D':
        if remaining < 2:
            raise DecodeError("Truncated Format D extension instruction")
        rd = bytecode[start]
        imm8 = bytecode[start + 1]
        return opcode, {"format": "D", "rd": rd, "imm8": imm8,
                        "extension": True}, 4
    elif fmt == 'E':
        if remaining < 3:
            raise DecodeError("Truncated Format E extension instruction")
        rd = bytecode[start]
        rs1 = bytecode[start + 1]
        rs2 = bytecode[start + 2]
        return opcode, {"format": "E", "rd": rd, "rs1": rs1, "rs2": rs2,
                        "extension": True}, 5
    elif fmt == 'F':
        if remaining < 3:
            raise DecodeError("Truncated Format F extension instruction")
        rd = bytecode[start]
        imm16 = bytecode[start + 1] | (bytecode[start + 2] << 8)
        return opcode, {"format": "F", "rd": rd, "imm16": imm16,
                        "extension": True}, 5
    elif fmt == 'G':
        if remaining < 4:
            raise DecodeError("Truncated Format G extension instruction")
        rd = bytecode[start]
        rs1 = bytecode[start + 1]
        imm16 = bytecode[start + 2] | (bytecode[start + 3] << 8)
        return opcode, {"format": "G", "rd": rd, "rs1": rs1, "imm16": imm16,
                        "extension": True}, 6
    else:
        raise DecodeError(f"Unknown format '{fmt}' for extension opcode")
```

### 5.2 Execution Pipeline Integration

The extension execution path integrates with the standard FLUX fetch-decode-
execute pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                    FETCH STAGE                                │
│                                                              │
│  pc → bytecode[pc]                                           │
│                                                              │
│  if bytecode[pc] == 0xFF:                                    │
│      opcode = (0xFF << 8) | bytecode[pc+1]                  │
│      fmt = manifest.lookup_format(opcode)                    │
│      size = 2 + format_operand_size(fmt)                     │
│  else:                                                       │
│      opcode = bytecode[pc]                                   │
│      fmt = CORE_FORMAT_TABLE[opcode]                         │
│      size = format_operand_size(fmt)                         │
│                                                              │
│  instruction = bytecode[pc : pc + size]                     │
│  next_pc = pc + size                                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    DECODE STAGE                               │
│                                                              │
│  Decode instruction fields (rd, rs1, rs2, imm8, imm16)      │
│  based on fmt                                               │
│                                                              │
│  If opcode >= 0xFF00:                                        │
│      Validate opcode against extension manifest              │
│      Check capability permissions                            │
│      Set extension flag in instruction descriptor            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTE STAGE                              │
│                                                              │
│  if opcode >= 0xFF00:                                        │
│      handler = extension_dispatch[opcode]                    │
│      if handler is None:                                     │
│          → degrade gracefully (Section 5.3)                  │
│      else:                                                   │
│          handler.execute(decoded_instruction)                │
│  else:                                                       │
│      core_dispatch[opcode](decoded_instruction)              │
│                                                              │
│  pc = next_pc                                                │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Trap and Exception Semantics

When an unsupported or illegal extension opcode is encountered, the runtime
generates a structured exception. The trap codes are allocated in the existing
TRAP vector space (0x11 in the core ISA):

```
Extension-related trap codes (passed via imm8 to TRAP instruction,
or as automatic fault codes):

  0x40 = TRAP_EXT_UNKNOWN        — Unknown extension opcode
  0x41 = TRAP_EXT_UNSUPPORTED    — Extension not loaded in runtime
  0x42 = TRAP_EXT_VERSION        — Version mismatch
  0x43 = TRAP_EXT_PERMISSION     — Insufficient permissions
  0x44 = TRAP_EXT_TIMEOUT        — Extension execution exceeded time limit
  0x45 = TRAP_EXT_MEMORY         — Extension exceeded memory limit
  0x46 = TRAP_EXT_SANDBOX        — Sandbox violation
  0x47 = TRAP_EXT_DEP_MISSING    — Required dependency extension missing
  0x48 = TRAP_EXT_INIT_FAILED    — Extension initialization failed
  0x49 = TRAP_EXT_STATE_ERROR    — Extension internal state inconsistency
  0x4A = TRAP_EXT_RESOURCE       — Resource exhaustion (GPU, TPU, etc.)
  0x4B = TRAP_EXT_HARDWARE       — Hardware not available
  0x4C = TRAP_EXT_DATA           — Invalid data for extension opcode
  0x4D = TRAP_EXT_MULTIBYTE      — Invalid multi-byte escape sequence

  Trap information block (pushed to stack on trap):
  ┌──────────────────────────────────────────────────────┐
  │ field                │ size  │ description            │
  ├──────────────────────┼───────┼────────────────────────┤
  │ trap_code           │ u8    │ Trap classification    │
  │ fault_pc            │ u32   │ PC of faulting instr   │
  │ opcode              │ u16   │ Full opcode (0xFFXX)    │
  │ ext_id              │ u32   │ Extension group ID     │
  │ ext_version_major   │ u8    │ Required major version │
  │ ext_version_minor   │ u8    │ Required minor version │
  │ runtime_version_maj │ u8    │ Runtime's major version│
  │ runtime_version_min │ u8    │ Runtime's minor version│
  │ register_snapshot   │ 256B  │ Full register file     │
  └──────────────────────┴───────┴────────────────────────┘
```

The fault handler (installed via HANDLER at 0xE8 or FAULT at 0xE7) receives
this information block and can decide whether to:

1. **Abort** the module (for required extensions).
2. **Skip** the instruction (for optional extensions).
3. **Emulate** via software fallback.
4. **Dynamically load** the extension and retry.

### 5.4 Fallback Opcodes

Extension opcodes MAY declare fallback mappings to core opcodes. When the
runtime does not support the extension, the fallback opcode is executed
instead. This enables graceful degradation.

```
Fallback table format (in manifest):

┌──────────────────┬──────────────────┐
│ ext_opcode       │ fallback_opcode  │
│ u16 (LE)         │ u8               │
└──────────────────┴──────────────────┘

Example fallback mappings:

  0xFF42 (ML_BATCHNORM)  → 0x20 (ADD) + 0x22 (MUL)   // Approximate
  0xFF48 (ML_RELU)       → 0x20 (ADD) + 0x2A (MAX)   // Approximate
  0xFF40 (ML_MATMUL)     → (no fallback)               // Trap if unavailable
  0xFF20 (SHA3_256)       → 0x99 (SHA256)              // Different but usable
```

Fallback resolution follows this precedence:

```
Pseudocode: Fallback resolution

def resolve_opcode(opcode: int, manifest, runtime) -> ResolvedOpcode:
    # 1. Check if extension is directly supported
    if runtime.has_extension_for(opcode):
        return ResolvedOpcode(opcode, type=NATIVE)

    # 2. Check for exact fallback in manifest
    if manifest.has_fallback(opcode):
        fb = manifest.get_fallback(opcode)
        return ResolvedOpcode(fb.fallback_opcode, type=FALLBACK)

    # 3. Check for semantic fallback in runtime
    semantic_fb = runtime.find_semantic_fallback(opcode)
    if semantic_fb is not None:
        return ResolvedOpcode(semantic_fb, type=SEMANTIC_FALLBACK)

    # 4. No fallback available
    if manifest.is_required(opcode):
        return ResolvedOpcode(opcode, type=TRAP)
    else:
        return ResolvedOpcode(0x01, type=NOOP)  # NOP
```

### 5.5 Debug Information

Extension opcodes interact with the FLUX debug infrastructure in specific ways:

#### 5.5.1 Disassembly

The disassembler MUST display extension opcodes in a human-readable format:

```
Standard disassembly output:

  Core:    20 03 01 05      →  ADD    r3, r1, r5
  Ext:     FF 42 03 01 05   →  crypto.BLAKE2B  r3, r1, r5
  Multi:   FF FF 00 01 03 01 05 → quantum.Q_H  r3, r1, r5

Disassembly format:
  [prefix] group_name.mnemonic [operands]

If the extension is unknown:
  FF 42 03 01 05   →  ext_unknown(0xFF42)  r3, r1, r5

If the manifest is not available:
  FF 42 03 01 05   →  ext(0xFF42, fmt=E)  3, 1, 5
```

#### 5.5.2 Source Mapping

Extensions SHOULD provide source-level debug information (DWARF-like):

```
Extension debug info section (type 0x06):

  Line number table: maps (ext_opcode, pc_offset) → (file, line, column)
  Symbol table: maps ext_opcode mnemonics to symbol names
  Type table: maps extension data types to DWARF-compatible types
```

#### 5.5.3 Trace Events

When tracing is enabled (TRACE opcode at 0xE9), extension opcode execution
generates trace events with additional context:

```
Extension trace event:

  event_type: EXT_ENTER
  timestamp: cycle_count
  pc: instruction address
  opcode: 0xFF42
  ext_group: "crypto"
  ext_name: "BLAKE2B"
  operands: {rd: 3, rs1: 1, rs2: 5}
  duration_us: 12

  event_type: EXT_EXIT
  timestamp: cycle_count + delta
  result: {rd: 3, value: 0xABCD...}
```

---

## 6. Multi-Byte Extensions (Beyond 65,536)

### 6.1 Motivation

While 256 primary extension opcodes (0xFF00–0xFFFF, minus 0xFFFF itself) may
seem generous, certain domains could exhaust them. For example:

- A full quantum computing instruction set might need 200+ opcodes.
- A comprehensive audio DSP library could need 100+ opcodes.
- Multiple vendor-specific GPU extensions could each need 50+ opcodes.

To address this, the multi-byte escape mechanism provides access to the
secondary extension layer, adding up to **16,777,214 additional opcodes**.

### 6.2 Four-Byte Escape Encoding

When the primary escape encounters `0xFF` as the extension byte (i.e., the
sequence `0xFF 0xFF`), it triggers the multi-byte escape path:

```
┌─────────┬─────────┬─────────┬─────────┐
│  0xFF   │  0xFF   │  ext16  │  ext16  │
│ (esc1)  │ (esc2)  │ (hi)    │ (lo)    │
└─────────┴─────────┴─────────┴─────────┘
  byte 0    byte 1    byte 2    byte 3

Full opcode: 0xFFFF0000 – 0xFFFFFFFE (16,777,215 values)
  - 0xFFFF0000 is valid (first secondary extension opcode)
  - 0xFFFFFFFE is valid (last secondary extension opcode)
  - 0xFFFFFFFF is reserved
```

The composite 32-bit opcode is computed as:

```
composite = (0xFF << 24) | (0xFF << 16) | (byte2 << 8) | byte3
          = 0xFFFF0000 | (ext16)
```

where `ext16` is the 16-bit little-endian value from bytes 2–3.

### 6.3 Secondary Extension Layout

The secondary extension space is divided into 256 blocks of 65,536 opcodes each:

```
0xFFFF0000 ┌────────────────────────────────────┐
           │ Block 0x00: Reserved               │
           │ 0xFFFF0000 – 0xFFFF00FF             │
           │ Meta-opcodes for secondary layer    │
0xFFFF00FF ├────────────────────────────────────┤
           │ Block 0x00: Vendor extensions       │
           │ 0xFFFF0100 – 0xFFFF00FF             │
0xFFFF00FF ├────────────────────────────────────┤
           │ Block 0x01: org.flux.*              │
           │ 0xFFFF0100 – 0xFFFFFFFE             │
           │ (FLUX standard secondary exts)      │
           ...
0xFFFF01FF ├────────────────────────────────────┤
           │ Block 0x02: com.nvidia.*            │
           │ 0xFFFF0200 – 0xFFFF02FF             │
           │ (NVIDIA secondary extensions)       │
           ...
0xFFFF02FF ├────────────────────────────────────┤
           │ Block 0x03–0xFF: Available          │
           │ Community / vendor blocks           │
           ...
0xFFFFFFFE ─────────────────────────────────────┘
```

### 6.4 Reserved Secondary Opcodes

| Opcode        | Name                | Purpose                              |
|---------------|---------------------|--------------------------------------|
| 0xFFFF0000    | EXT2_NOP            | No-operation in secondary layer      |
| 0xFFFF0001    | EXT2_MANIFEST       | Inline manifest for secondary exts   |
| 0xFFFF0002    | EXT2_QUERY          | Query secondary extension support    |
| 0xFFFF0003    | EXT2_REQUIRE        | Require secondary extension or trap  |
| 0xFFFF0004    | EXT2_VERSION        | Get secondary extension version      |
| 0xFFFF0005–0xFFFF000F | Reserved    | Reserved for mechanism internals    |
| 0xFFFFFFFE    | (last valid)        | Sentinel                             |
| 0xFFFFFFFF    | EXT3_ESCAPE         | Reserved for 6-byte escape (future)  |

### 6.5 Instruction Sizes with Multi-Byte Escape

After the 4-byte escape prefix, operands follow the standard format encoding:

| Base Format | Escape Prefix | Operands         | Total Bytes |
|-------------|---------------|------------------|-------------|
| Format A    | 4 bytes       | 0 bytes          | 4           |
| Format B    | 4 bytes       | 1 byte (rd)      | 5           |
| Format C    | 4 bytes       | 1 byte (imm8)    | 5           |
| Format D    | 4 bytes       | 2 bytes          | 6           |
| Format E    | 4 bytes       | 3 bytes          | 7           |
| Format F    | 4 bytes       | 3 bytes          | 7           |
| Format G    | 4 bytes       | 4 bytes          | 8           |

### 6.6 Future Extension: 6-Byte Escape (16M+)

For completeness, the specification reserves a path to 4,294,967,294 opcodes
via the `0xFFFFFFFF` sentinel. However, this is NOT specified in detail in this
version. The mechanism would be:

```
0xFF FF FF XX XX XX YY ...  →  0xFFFFFFXX0000 | (YY operands)

This is reserved for a future ISA v4 specification.
Implementations MUST treat 0xFF FF FF as an invalid sequence in ISA v3.
```

### 6.7 Binary Encoding Example: Multi-Byte Extension

```
Extension opcode 0xFFFF0102, Format E (rd=r3, rs1=r1, rs2=r5):

Byte offset:  0     1     2     3     4     5     6     7
           ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
Value:     │ 0xFF │ 0xFF │ 0x02│ 0x01│ 0x03│ 0x01│ 0x05│     │
           └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘
            esc1  esc2  ext16_lo ext16_hi  rd   rs1   rs2

Reading: "Execute secondary extension 0xFFFF0102 with r3 = r1 OP r5"
```

---

## 7. Interaction with Compressed Format

### 7.1 The FLUX 2-Byte Compressed Format

The FLUX ISA v3 defines a 2-byte compressed instruction format for
space-constrained environments (embedded systems, IoT sensors, bytecode
caching). The compressed format encodes commonly-used instructions in
2 bytes instead of 3–5 bytes.

In the compressed format, a leading byte with bit 7 clear (`0x00`–`0x7F`)
signals a compressed instruction, while bit 7 set (`0x80`–`0xFF`) signals an
uncompressed instruction:

```
Compressed format detection:
  byte[0] < 0x80  →  Compressed instruction (2 bytes total)
  byte[0] >= 0x80 →  Uncompressed instruction (variable length)
```

The compressed instruction format packs opcode and operands into 16 bits:

```
Compressed 2-byte instruction:

  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
  │ b7  │ b6  │ b5  │ b4  │ b3  │ b2  │ b1  │ b0  │  byte 0
  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
  │  0  │  opcode[5:0]                               │
  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐
  │ b7  │ b6  │ b5  │ b4  │ b3  │ b2  │ b1  │ b0  │  byte 1
  ├─────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┤
  │           rd[2:0]  │          rs1[4:0]           │
  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘

  Decoding:
    opcode = compressed_map[byte0 & 0x7F]
    rd     = (byte1 >> 5) & 0x07
    rs1    = byte1 & 0x1F
```

### 7.2 Escape in Compressed Context

The compressed format does NOT support extension opcodes directly. When an
extension opcode is needed in a compressed code section, the encoder MUST emit
an uncompressed escape sequence:

```
Compressed code section:

  0x23 0x45       →  Compressed: ADD r1, r5
  0x4A 0x12       →  Compressed: MOV r2, r1
  0xFF 0x42 0x03 0x01 0x05  →  Uncompressed: crypto.BLAKE2B r3, r1, r5
  0x15 0x23       →  Compressed: SUB r0, r3

Note: 0xFF has bit 7 set, so it's correctly detected as uncompressed.
```

The decoder's behavior:

```python
def decode_compressed_or_normal(bytecode: bytes, pc: int) -> tuple:
    byte0 = bytecode[pc]

    if byte0 < 0x80:
        # Compressed: always 2 bytes
        return decode_compressed(bytecode, pc)
    else:
        # Uncompressed: variable length
        # This handles both core opcodes (0x80–0xFE) and
        # extension escape (0xFF XX ...)
        return decode_instruction_v3(bytecode, pc)
```

### 7.3 Compressed Extension Subset (Optional)

Implementations MAY define a compressed extension subset for frequently-used
extension opcodes. This uses the compressed format with opcode values 0x40–0x7F:

```
Compressed extension format:

  byte0 = 0x40 | (ext_idx & 0x3F)   where ext_idx is 0–63
  byte1 = operands packed as normal

  This provides 64 compressed extension opcodes, each 2 bytes.

Allocation:
  0x40–0x4F: Reserved for standard compressed extensions
  0x50–0x5F: Reserved for standard compressed extensions (ML hot path)
  0x60–0x7F: Available for implementation-specific compressed extensions

The mapping from compressed extension index to full extension opcode is
stored in a "compressed extension table" in the bytecode header.
```

### 7.4 Size Comparison Table

| Instruction Type             | Uncompressed | Compressed | Savings |
|------------------------------|-------------|------------|---------|
| Core ADD (Format E)          | 4 bytes     | 2 bytes    | 50%     |
| Core MOVI16 (Format F)       | 4 bytes     | N/A        | —       |
| Extension Format E (primary) | 5 bytes     | 2 bytes*   | 60%     |
| Extension Format E (secondary)| 7 bytes    | N/A        | —       |
| Core NOP (Format A)          | 1 byte      | 2 bytes    | -100%   |

*Only if compressed extension subset is defined for that opcode.

---

## 8. Migration Guide

### 8.1 ISA v2 Coexistence

ISA v2 bytecode uses a different opcode layout (HALT at 0x80 in the original
`opcodes.py`). ISA v2 modules MUST NOT use the 0xFF escape prefix, since 0xFF
in ISA v2 was defined as a general-purpose register (or unused depending on the
implementation).

Migration strategy:

```
┌─────────────────────────────────────────────────────────┐
│                    FLUX VM Loading                        │
│                                                          │
│  bytecode_path → read_header() → extract ISA version    │
│                                                          │
│  if isa_version == 2:                                    │
│      use_v2_decoder()                                    │
│      0xFF is handled per v2 spec (unused / trap)        │
│                                                          │
│  elif isa_version == 3:                                  │
│      use_v3_decoder()                                    │
│      0xFF triggers escape prefix logic                   │
│      check for extension manifest (section 0x05)         │
│                                                          │
│  else:                                                   │
│      reject("Unsupported ISA version")                   │
└─────────────────────────────────────────────────────────┘
```

### 8.2 Repurposing 0xFF: ILLEGAL → ESCAPE

The ISA v3 unified specification defines `0xFF ILLEGAL` as an illegal
instruction trap. This specification repurposes that byte as the escape prefix.
The following changes are required:

#### 8.2.1 Core ISA Change

```
OLD (ISA v3 without escape):
  0xFF  ILLEGAL  Format A  "Illegal instruction trap"

NEW (ISA v3 with escape):
  0xFF  ESCAPE   Prefix    "Extension opcode prefix"
  0xFF 0x00      EXT_NOP   "Extension no-operation"
  ...
  0xFF 0x05      EXT_FALLBACK "Declare fallback opcode"
```

#### 8.2.2 Backward Compatibility Considerations

No legitimate FLUX bytecode should contain a standalone `0xFF` instruction,
since executing it previously caused an illegal instruction trap (which is
fatal). Therefore:

1. **Valid ISA v3 bytecode without extensions**: Will never contain `0xFF`.
   These modules run unchanged.

2. **Valid ISA v2 bytecode**: Identified by ISA version in header. The v2
   decoder does not interpret `0xFF` as an escape prefix.

3. **Hand-crafted bytecode with bare 0xFF**: Was already broken (caused trap).
   Now it will be interpreted as an escape prefix + the next byte. If the next
   byte is not a valid extension opcode, the runtime will raise an appropriate
   error (`TRAP_EXT_UNKNOWN` or `TRAP_EXT_UNSUPPORTED`).

### 8.3 Migration Checklist for Runtime Implementers

```
□ 1. Update decoder to detect 0xFF and enter escape path
□ 2. Add extension manifest parser (section type 0x05)
□ 3. Implement ExtensionRegistry class
□ 4. Add trap codes 0x40–0x4D to TRAP handler
□ 5. Update disassembler for extension opcodes
□ 6. Add extension capability negotiation to A2A protocol
□ 7. Implement fallback resolution logic
□ 8. Update bytecode verifier to validate extension opcodes
□ 9. Add extension permission checks to security sandbox
□ 10. Update documentation and assembly syntax
```

### 8.4 Migration Checklist for Toolchain Authors

```
□ 1. Update assembler to support `ext.group.mnemonic` syntax
□ 2. Add extension manifest generation to compiler/linker
□ 3. Update optimizer to handle extension instruction scheduling
□ 4. Add compression support for extension opcodes (optional)
□ 5. Update decompiler to recognize extension patterns
□ 6. Add extension testing infrastructure
```

### 8.5 Assembly Syntax

The FLUX assembly language is extended with a dotted notation for extension
opcodes:

```
# Core instruction
  ADD r3, r1, r5

# Extension instruction (primary)
  crypto.BLAKE2B r3, r1, r5

# Extension instruction (secondary)
  quantum.Q_H r3, r1, r5

# Meta-instruction (require extension)
  .require crypto 1.0

# Meta-instruction (optional extension)
  .optional ml 1.2

# Meta-instruction (declare fallback)
  .fallback ml.MATMUL → core_emulation_matmul

# Meta-instruction (extension guard)
  .if_has_ext crypto
    crypto.SHA3_256 r3, r1, r5
  .else
    HASH r3, r1, 0x02  # Fall back to core SHA-256
  .endif
```

### 8.6 Migration Path for ISA v2 Extensions

Some ISA v2 implementations used opcodes in the 0xD0–0xFF range for
implementation-specific extensions (as noted in the ISA convergence analysis).
These need to be migrated to the new escape prefix mechanism:

```
Step 1: Identify all custom opcodes in the 0xD0–0xFE range
Step 2: Register a new extension group (self-assigned ID)
Step 3: Re-map custom opcodes to the extension space (0xFF20+)
Step 4: Emit the extension manifest in the bytecode header
Step 5: Update all references from direct opcode to ext.name.mnemonic
Step 6: Test on both old and new runtimes
```

---

## 9. Bytecode Examples

### 9.1 Example 1: SHA-3 Hashing with Fallback

This example demonstrates computing a SHA-3-256 hash of a message, with a
fallback to SHA-256 if the `crypto` extension is not available.

```
; ── SHA-3 with fallback to SHA-256 ──
; Input:  r1 = pointer to message buffer
;         r2 = message length
; Output: r3 = pointer to digest buffer

  .require crypto 1.0           ; Request crypto extension
  .fallback crypto.SHA3_256 → _sha3_fallback

  ; Try the extension opcode
  0xFF 0x20 0x03 0x01 0x02      ; crypto.SHA3_256 r3, r1, r2
  0x00                          ; HALT (success)

_sha3_fallback:
  ; Fallback: use core SHA-256 (opcode 0x99)
  0x99 0x03 0x01 0x02            ; SHA256 r3, r1, r2
  0xF0                          ; HALT_ERR (with warning flag)
```

Byte-by-byte breakdown:

```
Offset  Hex     Description
0x0000  FF      Escape prefix
0x0001  20      Extension byte → crypto.SHA3_256 (0xFF20)
0x0002  03      rd = r3
0x0003  01      rs1 = r1
0x0004  02      rs2 = r2
0x0005  00      HALT
0x0006  99      SHA256 (core)
0x0007  03      rd = r3
0x0008  01      rs1 = r1
0x0009  02      rs2 = r2
0x000A  F0      HALT_ERR
```

### 9.2 Example 2: Matrix Multiplication via ML Extension

This example shows a 4×4 matrix multiplication using the ML extension's
`ML_MATMUL` opcode.

```
; ── 4×4 Matrix Multiplication ──
; Input:  r1 = pointer to matrix A (4×4, row-major, 64 bytes)
;         r2 = pointer to matrix B (4×4, row-major, 64 bytes)
; Output: r4 = pointer to result matrix C

  .require ml 1.0

  ; Allocate result buffer (4×4 × 4 bytes = 64 bytes)
  0xD7 0x04 0x00 0x00 0x40      ; MALLOC r4, r0, imm16=0x0040

  ; Execute matrix multiply
  0xFF 0x40 0x04 0x01 0x02      ; ml.ML_MATMUL r4, r1, r2
                                  ; C = A @ B, result stored at r4

  ; Store result to memory region
  0x49 0x04 0x10 0x00 0x40      ; STOREOFF r4, r16, imm16=0x0040

  0x00                          ; HALT
```

Binary:

```
Offset  Hex                        Description
0x0000  D7 04 00 00 40             MALLOC r4, r0, 64
0x0005  FF 40 04 01 02             ml.ML_MATMUL r4, r1, r2
0x000A  49 04 10 00 40             STOREOFF r4, r16, 64
0x000F  00                         HALT
```

### 9.3 Example 3: Quantum Circuit (Bell State)

This example creates a Bell state (|Φ+⟩ = (|00⟩ + |11⟩)/√2) using the
quantum extension.

```
; ── Bell State Preparation ──
; Creates: |Φ+⟩ = (|00⟩ + |11⟩)/√2

  .require quantum 1.0

  ; Initialize 2-qubit register
  0x18 0x01 0x02                 ; MOVI r1, 2  (n_qubits = 2)
  0xFF 0x90 0x01 0x01 0x02       ; quantum.Q_INIT r1, r1, r2
                                   ; r1 = quantum register, 2 qubits

  ; Apply Hadamard to qubit 0
  0x18 0x02 0x00                 ; MOVI r2, 0  (qubit index)
  0xFF 0x91 0x01 0x02 0x00       ; quantum.Q_H r1, r2, r0
                                   ; H on qubit 0 of register r1

  ; Apply CNOT (control=q0, target=q1)
  0xFF 0x95 0x01 0x00 0x01       ; quantum.Q_CNOT r1, q0, q1

  ; Measure all qubits
  0xFF 0x9A 0x03 0x00 0x00       ; quantum.Q_MEASURE r3, q0, r0
                                   ; Measure qubit 0 → r3
  0xFF 0x9A 0x04 0x01 0x00       ; quantum.Q_MEASURE r4, q1, r0
                                   ; Measure qubit 1 → r4

  ; Report result
  0x56 0x03 0x00 0x04             ; REPORT r3, r0, r4

  0x00                           ; HALT
```

Binary:

```
Offset  Hex                 Description
0x0000  18 02               MOVI r2, 2
0x0002  FF 90 01 02 00       quantum.Q_INIT r1, r1, r2
0x0007  18 02 00             MOVI r2, 0
0x000A  FF 91 01 02 00       quantum.Q_H r1, r2, r0
0x000F  FF 95 01 00 01       quantum.Q_CNOT r1, q0, q1
0x0014  FF 9A 03 00 00       quantum.Q_MEASURE r3, q0, r0
0x0019  FF 9A 04 01 00       quantum.Q_MEASURE r4, q1, r0
0x001E  56 03 00 04         REPORT r3, r0, r4
0x0022  00                   HALT
```

### 9.4 Example 5: Audio FFT Pipeline

This example processes audio data through an FFT pipeline using the `audio`
extension.

```
; ── Audio FFT Processing Pipeline ──
; Input:  r1 = pointer to audio samples (1024 floats)
; Output: r5 = pointer to frequency spectrum

  .require audio 1.0

  ; Set FFT size (1024 = 0x0400)
  0x40 0x02 0x04 0x00           ; MOVI16 r2, imm16=0x0400

  ; Allocate output buffer
  0xD7 0x05 0x00 0x10 0x00       ; MALLOC r5, r0, imm16=0x1000
                                   ; 1024 complex = 4096 bytes

  ; Apply window function (Hann)
  0xFF 0x7B 0x03 0x01 0x02       ; audio.AUD_GAIN r3, r1, r2
                                   ; r3 = windowed signal

  ; Compute FFT
  0xFF 0x70 0x05 0x03 0x02       ; audio.AUD_FFT r5, r3, r2
                                   ; r5 = FFT(windowed_signal, 1024)

  ; Compute magnitude spectrum
  0xFF 0x77 0x04 0x05 0x02       ; audio.AUD_SPECTRO r4, r5, r2

  ; Report spectrum to fleet
  0x53 0x04 0x00 0x05             ; BCAST r4, r0, r5

  0x00                             ; HALT
```

Binary:

```
Offset  Hex                     Description
0x0000  40 02 04 00             MOVI16 r2, 1024
0x0004  D7 05 00 10 00          MALLOC r5, r0, 4096
0x0009  FF 7B 03 01 02          audio.AUD_GAIN r3, r1, r2
0x000E  FF 70 05 03 02          audio.AUD_FFT r5, r3, r2
0x0013  FF 77 04 05 02          audio.AUD_SPECTRO r4, r5, r2
0x0018  53 04 00 05             BCAST r4, r0, r5
0x001C  00                      HALT
```

### 9.5 Example 5: Multi-Byte Extension for Large GPU Kernel

This example uses a secondary (multi-byte) extension opcode for a vendor-
specific GPU compute operation.

```
; ── NVIDIA GPU Tensor Core Operation ──
; Requires: com.nvidia.cuda extension (secondary layer)

  .require com.nvidia.cuda 1.0

  ; Load tensors from host memory
  0xDB 0x01 0x10 0x00 0x00       ; GPU_LD r1, r16, imm16=0x0000
                                   ; Load tensor A to GPU
  0xDB 0x02 0x20 0x00 0x00       ; GPU_LD r2, r32, imm16=0x0000
                                   ; Load tensor B to GPU

  ; Execute vendor-specific tensor core matmul
  ; Secondary extension: opcode 0xFFFF0201
  0xFF 0xFF 0x01 0x02             ; Escape to secondary layer
                                   ; ext16 = 0x0201
  0x03 0x01 0x02                   ; rd=r3, rs1=r1, rs2=r2
                                   ; nvidia.WMMA r3, r1, r2

  ; Synchronize GPU
  0xDE 0x00 0x00 0x00 0x01       ; GPU_SYNC r0, r0, device=1

  ; Store result
  0xDC 0x03 0x30 0x00 0x00       ; GPU_ST r3, r48, imm16=0x0000
                                   ; Store result tensor to host

  0x00                             ; HALT
```

Binary:

```
Offset  Hex                     Description
0x0000  DB 01 10 00 00          GPU_LD r1, r16, 0
0x0005  DB 02 20 00 00          GPU_LD r2, r32, 0
0x000A  FF FF 01 02             Escape → secondary opcode 0xFFFF0201
0x000E  03 01 02                nvidia.WMMA r3, r1, r2
0x0011  DE 00 00 00 01          GPU_SYNC r0, r0, 1
0x0016  DC 03 30 00 00          GPU_ST r3, r48, 0
0x001B  00                      HALT
```

### 9.6 Example 6: Extension Capability Query at Runtime

This example demonstrates runtime extension capability checking using the
meta-opcodes defined in the escape prefix space.

```
; ── Runtime Extension Query ──
; Checks if the 'crypto' extension is available and uses it conditionally

  ; Query if crypto extension is supported
  ; 0xFF 0x02 = EXT_QUERY
  ; Extension ID is passed via registers
  0x40 0x01 0x00 0x02           ; MOVI16 r1, 0x0002
                                   ; r1 = crypto ext_id (0x00000002, truncated to 16-bit)
  0x18 0x02 0x01                 ; MOVI r2, 1
                                   ; r2 = major version 1
  0x18 0x03 0x00                 ; MOVI r3, 0
                                   ; r3 = minor version 0
  0xFF 0x02 0x04 0x01 0x02       ; EXT_QUERY r4, r1, r2
                                   ; Query: is crypto v1.0 available?
                                   ; r4 = 1 (yes) or 0 (no)

  ; Conditional execution based on result
  0x3C 0x04 0x01 0x00             ; JZ r4, offset=1
                                   ; If not supported, skip to fallback

  ; Extension is available — use SHA3-256
  0xFF 0x20 0x05 0x06 0x07       ; crypto.SHA3_256 r5, r6, r7
  0x43 0x00 0x00 0x0C             ; JMP r0, +12 (skip fallback)

_fallback:
  ; Extension not available — use core SHA-256
  0x99 0x05 0x06 0x07             ; SHA256 r5, r6, r7

_continue:
  0x00                             ; HALT
```

---

## 10. Formal Semantics

### 10.1 Operational Semantics

We define the operational semantics of extension opcodes using a small-step
relation. The judgment has the form:

```
  (σ, pc, bc) → (σ', pc', bc')

Where:
  σ  = machine state (registers, memory, extensions)
  pc = program counter
  bc = bytecode (immutable)
```

#### 10.1.1 Core Instruction Step

```
  fetch(σ, pc, bc) = (op, args, pc')
  op ∈ {0x00..0xFE}
  execute_core(op, args, σ) = σ'
  ───────────────────────────────────────  [E-CORE]
  (σ, pc, bc) → (σ', pc', bc)
```

#### 10.1.2 Extension Instruction Step (Supported)

```
  fetch(σ, pc, bc) = (0xFF, ext, args, pc')
  σ.ext = ext_registry
  ext_registry.lookup(0xFF00 | ext) = Some(handler)
  handler.execute(args, σ) = σ'
  ───────────────────────────────────────────────  [E-EXT-OK]
  (σ, pc, bc) → (σ', pc', bc)
```

#### 10.1.3 Extension Instruction Step (Unsupported, Has Fallback)

```
  fetch(σ, pc, bc) = (0xFF, ext, args, pc')
  σ.ext = ext_registry
  ext_registry.lookup(0xFF00 | ext) = None
  manifest.fallback(0xFF00 | ext) = Some(core_op, mapped_args)
  execute_core(core_op, mapped_args, σ) = σ'
  ─────────────────────────────────────────────────────  [E-EXT-FALLBACK]
  (σ, pc, bc) → (σ', pc', bc)
```

#### 10.1.4 Extension Instruction Step (Unsupported, Required)

```
  fetch(σ, pc, bc) = (0xFF, ext, args, pc')
  σ.ext = ext_registry
  ext_registry.lookup(0xFF00 | ext) = None
  manifest.fallback(0xFF00 | ext) = None
  manifest.is_required(0xFF00 | ext) = True
  σ'.trap = TRAP_EXT_UNSUPPORTED(0xFF00 | ext, pc)
  σ'.fault_pc = pc
  ───────────────────────────────────────────────────────  [E-EXT-TRAP]
  (σ, pc, bc) → (σ', handler_pc, bc)
```

#### 10.1.5 Extension Instruction Step (Unsupported, Optional)

```
  fetch(σ, pc, bc) = (0xFF, ext, args, pc')
  σ.ext = ext_registry
  ext_registry.lookup(0xFF00 | ext) = None
  manifest.fallback(0xFF00 | ext) = None
  manifest.is_required(0xFF00 | ext) = False
  σ' = σ  (state unchanged, instruction is no-op)
  ───────────────────────────────────────────────────────  [E-EXT-SKIP]
  (σ, pc, bc) → (σ', pc', bc)
```

### 10.2 Type Safety Properties

The following properties hold for well-formed FLUX bytecode with extensions:

**Property 1 (Format Consistency):** For every extension opcode `op` in the
bytecode, the number of operand bytes following the escape prefix matches the
format declared in the manifest.

```
  ∀ op ∈ used_extension_opcodes(bytecode):
    operand_count(op, bytecode) = format_size(manifest.format(op))
```

**Property 2 (No Overlapping Groups):** No two registered extension groups
have overlapping opcode ranges.

```
  ∀ g1, g2 ∈ registered_extensions:
    g1 ≠ g2 ⟹
    [g1.base, g1.base + g1.count) ∩ [g2.base, g2.base + g2.count) = ∅
```

**Property 3 (Deterministic Decoding):** Given the same bytecode and manifest,
the decoder produces the same instruction sequence regardless of the runtime
implementation.

```
  ∀ bc, manifest, runtime1, runtime2:
    decode(bc, manifest, runtime1) = decode(bc, manifest, runtime2)
```

### 10.3 Bytecode Verification Rules

The bytecode verifier MUST enforce the following rules for extension opcodes:

```
Rule V-EXT-1: Every extension opcode in the code section MUST have a
  corresponding entry in the extension manifest.

Rule V-EXT-2: The format table for each extension opcode MUST match the
  actual operand bytes in the code section.

Rule V-EXT-3: Extension opcodes marked as "required" in the manifest MUST
  NOT have jump targets that skip them (unreachable required extensions
  are a verification error).

Rule V-EXT-4: The EXT_REQUIRE meta-opcode (0xFF03) MUST reference an
  extension that exists in the manifest.

Rule V-EXT-5: Fallback opcodes MUST be valid core opcodes or valid
  extension opcodes from a required extension.

Rule V-EXT-6: Multi-byte escape sequences (0xFF FF XX XX) MUST NOT
  appear in code sections of modules declaring ISA version < 3.

Rule V-EXT-7: Extension group IDs MUST be unique within the manifest.

Rule V-EXT-8: Extension opcodes MUST NOT appear in interrupt handler
  code sections unless the handler's manifest also declares the extension.
```

---

## 11. Security Considerations

### 11.1 Extension Permission Model

Extension opcodes are subject to the FLUX capability-based security model.
Each extension group declares a set of required permissions:

```python
class ExtensionPermission(IntFlag):
    """Permissions for extension opcodes."""
    NONE = 0
    READ_MEMORY = 1          # Extension may read arbitrary memory
    WRITE_MEMORY = 2         # Extension may write arbitrary memory
    ALLOCATE = 4             # Extension may allocate memory
    NETWORK = 8              # Extension may perform network I/O
    FILESYSTEM = 16          # Extension may access filesystem
    HARDWARE = 32            # Extension may access hardware devices
    CRYPTO_KEY_ACCESS = 64   # Extension may access cryptographic keys
    AGENT_COMMUNICATION = 128 # Extension may use A2A protocol
    SYSTEM_CALL = 256        # Extension may invoke system calls
    ALL = 0xFFFF
```

Permission checks occur at two levels:

1. **Manifest load time**: The manifest is checked for permission
   declarations, and the loader verifies the runtime's security policy
   allows those permissions.

2. **Execution time**: Each extension opcode execution is wrapped in a
   permission check. If the current execution context lacks the required
   permission, a `TRAP_EXT_PERMISSION` (0x43) is raised.

### 11.2 Resource Limits

Extensions MUST declare resource limits to prevent denial-of-service:

```python
@dataclass
class ExtensionResourceLimits:
    """Resource limits for extension execution."""
    max_memory_bytes: int       # Maximum heap allocation
    max_execution_cycles: int   # CPU cycle budget per instruction
    max_total_time_us: int      # Wall-clock time limit per instruction
    max_io_bytes: int           # Maximum I/O bytes per instruction
    max_sub_calls: int          # Maximum nested extension calls
```

If an extension exceeds its declared limits, the runtime raises the
appropriate trap:

- Exceeded memory → `TRAP_EXT_MEMORY` (0x45)
- Exceeded time → `TRAP_EXT_TIMEOUT` (0x44)
- Exceeded I/O → `TRAP_EXT_RESOURCE` (0x4A)

### 11.3 Sandbox Isolation

Extensions can be executed in a sandboxed environment with three levels:

```
Level 0 (Unsandboxed):
  - Extension runs with full system access
  - Only for trusted, verified extensions
  - Permission check at manifest load time only

Level 1 (Restricted Sandbox):
  - Extension runs with memory bounds checking
  - No direct hardware access (MMIO/GPU/CPUID blocked)
  - No filesystem access
  - Network access only through approved channels
  - All memory allocations tracked and bounded

Level 2 (Full Sandbox):
  - Extension runs in an isolated memory region
  - No access to host memory (all data copied in/out)
  - No network access
  - No system calls
  - Execution time strictly limited
  - State is not persisted between invocations
```

### 11.4 Extension Authenticity

To prevent malicious extension injection, the manifest can include digital
signatures:

```
Signed manifest format:

┌────────────────────────────────────────────┐
│ Unsigned manifest bytes (as defined in 3.1)│
├────────────────────────────────────────────┤
│ Signature algorithm: u8                    │
│   0x01 = Ed25519                          │
│   0x02 = RSA-PSS-SHA256                   │
│   0x03 = ECDSA-P256                       │
├────────────────────────────────────────────┤
│ Key ID: u32                                │
├────────────────────────────────────────────┤
│ Signature: variable length                 │
│   Ed25519: 64 bytes                        │
│   RSA-PSS: 256+ bytes                      │
│   ECDSA: 64 bytes                          │
└────────────────────────────────────────────┘
```

The runtime verifies the manifest signature against a trusted key store before
loading any extensions. Extensions from unknown keys are rejected unless the
runtime is configured in developer mode.

---

## 12. Appendix

### 12.1 Complete Extension Opcode Quick Reference

```
PRIMARY EXTENSION LAYER (0xFF00–0xFFFF):

Meta-opcodes (0xFF00–0xFF0F):
  0xFF00  EXT_NOP        No-operation in extension space
  0xFF01  EXT_MANIFEST   Inline manifest declaration
  0xFF02  EXT_QUERY      Query extension support
  0xFF03  EXT_REQUIRE    Require extension or trap
  0xFF04  EXT_VERSION    Get extension version
  0xFF05  EXT_FALLBACK   Declare fallback opcode
  0xFF06  EXT_GUARD      Conditional execution guard
  0xFF07  EXT_CAPS       Query extension capabilities
  0xFF08–0xFF0F  Reserved

Standard Extensions (0xFF10–0xFFBF):
  0xFF10–0xFF1F  std.meta    Extension introspection
  0xFF20–0xFF3F  crypto      Cryptographic primitives (32 opcodes)
  0xFF40–0xFF5F  ml          Machine learning inference (32 opcodes)
  0xFF60–0xFF6F  ml.reserved Reserved for ML extensions
  0xFF70–0xFF8F  audio       Audio DSP and codec (32 opcodes)
  0xFF90–0xFFAF  quantum     Quantum computing primitives (32 opcodes)
  0xFFB0–0xFFBF  quantum.res Reserved for quantum extensions

Community Extensions (0xFFC0–0xFFFE):
  0xFFC0–0xFFDF  Available for community allocation
  0xFFE0–0xFFFE  Available for community allocation

Multi-byte escape:
  0xFFFF         EXT_ESCAPE2  Trigger 4-byte secondary escape

SECONDARY EXTENSION LAYER (0xFFFF0000–0xFFFFFFFE):

Meta-opcodes (0xFFFF0000–0xFFFF000F):
  0xFFFF0000  EXT2_NOP      No-operation in secondary space
  0xFFFF0001  EXT2_MANIFEST Inline manifest for secondary exts
  0xFFFF0002  EXT2_QUERY    Query secondary extension support
  0xFFFF0003  EXT2_REQUIRE  Require secondary extension or trap
  0xFFFF0004  EXT2_VERSION  Get secondary extension version
  0xFFFF0005–0xFFFF000F  Reserved

Block allocations:
  0xFFFF0100–0xFFFF00FF  org.flux.* standard secondary extensions
  0xFFFF0100–0xFFFF01FF  org.flux.* extended range
  0xFFFF0200–0xFFFF02FF  com.nvidia.* NVIDIA extensions
  0xFFFF0300–0xFFFF03FF  com.google.* Google extensions
  0xFFFF0400–0xFFFF04FF  com.apple.* Apple extensions
  0xFFFF0500–0xFFFF05FF  org.tensorflow.* TensorFlow extensions
  0xFFFF0600–0xFFFF06FF  org.pytorch.* PyTorch extensions
  0xFFFF0700–0xFFFFFFFE  Available for community/vendor allocation

Future:
  0xFFFFFFFF  EXT3_ESCAPE  Reserved for 6-byte escape (ISA v4)
```

### 12.2 Format Quick Reference

```
Instruction encoding after escape prefix:

Primary escape (0xFF + 1 byte = 2 byte prefix):
  Format A: [0xFF][ext]                          = 2 bytes
  Format B: [0xFF][ext][rd]                      = 3 bytes
  Format C: [0xFF][ext][imm8]                    = 3 bytes
  Format D: [0xFF][ext][rd][imm8]                = 4 bytes
  Format E: [0xFF][ext][rd][rs1][rs2]            = 5 bytes
  Format F: [0xFF][ext][rd][imm16_lo][imm16_hi]  = 5 bytes
  Format G: [0xFF][ext][rd][rs1][imm16_lo][imm16_hi] = 6 bytes

Secondary escape (0xFF 0xFF + 2 bytes = 4 byte prefix):
  Format A: [0xFF][0xFF][ext16_lo][ext16_hi]                    = 4 bytes
  Format B: [0xFF][0xFF][ext16_lo][ext16_hi][rd]                = 5 bytes
  Format C: [0xFF][0xFF][ext16_lo][ext16_hi][imm8]              = 5 bytes
  Format D: [0xFF][0xFF][ext16_lo][ext16_hi][rd][imm8]          = 6 bytes
  Format E: [0xFF][0xFF][ext16_lo][ext16_hi][rd][rs1][rs2]      = 7 bytes
  Format F: [0xFF][0xFF][ext16_lo][ext16_hi][rd][imm16_lo][imm16_hi] = 7 bytes
  Format G: [0xFF][0xFF][ext16_lo][ext16_hi][rd][rs1][imm16_lo][imm16_hi] = 8 bytes

Explicit format mode (adds 1 byte):
  [0xFF][ext][fmt_byte][operands...]  (fmt_byte = 0–6 for Formats A–G)
```

### 12.3 Trap Code Quick Reference

```
Extension-related trap codes (used with TRAP 0x11 or automatic faults):

  0x40  TRAP_EXT_UNKNOWN       Unknown extension opcode
  0x41  TRAP_EXT_UNSUPPORTED   Extension not loaded
  0x42  TRAP_EXT_VERSION       Version mismatch
  0x43  TRAP_EXT_PERMISSION    Insufficient permissions
  0x44  TRAP_EXT_TIMEOUT       Execution time exceeded
  0x45  TRAP_EXT_MEMORY        Memory limit exceeded
  0x46  TRAP_EXT_SANDBOX       Sandbox violation
  0x47  TRAP_EXT_DEP_MISSING   Dependency extension missing
  0x48  TRAP_EXT_INIT_FAILED   Initialization failed
  0x49  TRAP_EXT_STATE_ERROR   Internal state inconsistency
  0x4A  TRAP_EXT_RESOURCE      Resource exhaustion
  0x4B  TRAP_EXT_HARDWARE      Hardware not available
  0x4C  TRAP_EXT_DATA          Invalid data
  0x4D  TRAP_EXT_MULTIBYTE     Invalid multi-byte escape
```

### 12.4 Manifest Section Type Reference

```
FLUX Bytecode Header Section Types:

  0x01  CODE_SECTION        Main bytecode
  0x02  DATA_SECTION        Read-only data
  0x03  BSS_SECTION         Uninitialized data
  0x04  DEBUG_SECTION       Debug information (DWARF-like)
  0x05  EXTENSION_MANIFEST  Extension manifest (this spec)
  0x06  EXTENSION_DEBUG     Extension debug information
  0x07  EXTENSION_SIGNATURE Signed manifest
  0x08  COMPRESSED_SECTION  Compressed code section
  0x09  RESOURCE_LIMITS     Execution resource limits
  0x0A  SECURITY_POLICY     Security/capability policy
  0x0B–0xFF  Reserved
```

### 12.5 Change Log

```
v0.1 (2026-04-12) — Super Z
  - Initial draft
  - Defined 2-byte primary escape (0xFF + ext8)
  - Defined 4-byte secondary escape (0xFF 0xFF + ext16)
  - Allocated standard extension groups (crypto, ml, audio, quantum)
  - Defined extension manifest format
  - Specified runtime behavior and trap semantics
  - Documented interaction with compressed format
  - Provided 6 bytecode examples
  - Added formal operational semantics
  - Added security considerations
```

---

*End of FLUX ISA v3 Escape Prefix Specification (ISA-002)*
*This document is a living specification. Submit changes via fleet PR process.*
