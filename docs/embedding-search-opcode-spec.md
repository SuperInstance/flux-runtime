# FLUX ISA v3 — Embedding Search Extension Specification

**Document ID:** ISA-EMBED-001
**Task Board:** EMBED-001
**Status:** Draft
**Author:** Super Z (Fleet Agent, Opcode Design Board)
**Date:** 2026-04-12
**Depends On:** FLUX ISA v3 Unified Specification, ISA-002 Escape Prefix Spec
**Extension Group ID:** 0x00000006
**Extension Name:** `org.flux.embedding`
**Opcode Range:** 0xFFB0–0xFFBF
**Version:** 1.0

---

## Table of Contents

1. [Introduction & Motivation](#1-introduction--motivation)
2. [Vector Register File Extension](#2-vector-register-file-extension)
3. [Embedding Index Memory Format](#3-embedding-index-memory-format)
4. [Opcode Table](#4-opcode-table)
5. [Opcode Definitions](#5-opcode-definitions)
6. [Binary Encoding](#6-binary-encoding)
7. [Execution Semantics](#7-execution-semantics)
8. [Hardware Acceleration Model](#8-hardware-acceleration-model)
9. [Interaction with Existing ISA](#9-interaction-with-existing-isa)
10. [Error Handling & Trap Codes](#10-error-handling--trap-codes)
11. [Performance Considerations](#11-performance-considerations)
12. [Bytecode Examples](#12-bytecode-examples)
13. [Formal Semantics](#13-formal-semantics)
14. [Appendix](#14-appendix)

---

## 1. Introduction & Motivation

### 1.1 The Embedding Search Problem

Modern FLUX agents operate in high-dimensional semantic spaces. Tasks such as
semantic retrieval, nearest-neighbor classification, similarity scoring, and
context-grounded reasoning all require efficient approximate nearest neighbor
(ANN) search over dense floating-point vectors. Implementing these operations
in pure bytecode using the existing vector/SIMD opcodes (VLOAD, VDOT, VNORM,
0xB0–0xBF) and tensor opcodes (0xC0–0xCF) is possible but requires
dozens of instructions per search operation and provides no hardware
acceleration path.

The embedding search extension provides a dedicated instruction set for:

- **Loading embedding vectors** from structured memory into vector registers
- **Computing distance metrics** (Euclidean, cosine, Manhattan) efficiently
- **Performing K-nearest-neighbor (KNN) search** against an in-memory ANN index
- **L2-normalizing vectors** for cosine similarity computation
- **Computing dot products** as the fundamental similarity primitive

### 1.2 Design Goals

1. **Latency**: A KNN-10 search over 1M vectors must complete in under 1ms on
   hardware-accelerated runtimes.
2. **Memory efficiency**: The ANN index must support compressed storage
   (quantized embeddings) while maintaining >90% recall@10.
3. **Composability**: Embedding opcodes must compose naturally with existing
   vector (VLOAD/VDOT/VNORM) and tensor (TATTN/TSAMPLE) opcodes.
4. **Deterministic fallback**: On runtimes without hardware acceleration, all
   operations must produce bit-identical results via software fallback.
5. **Confidence integration**: Distance scores must propagate into the FLUX
   confidence system (C_MERGE, C_THRESH) for downstream reasoning.

### 1.3 Relationship to Existing Vector Opcodes

The core ISA already provides general-purpose vector operations (0xB0–0xBF):

| Core Opcode | Function | Relationship |
|-------------|----------|--------------|
| VLOAD (0xB0) | Load vector from memory | Lower-level; EMBEDDING_LOAD adds dimension validation |
| VDOT (0xB4) | Dot product | EMBEDDING_DOT provides confidence-tagged variant |
| VNORM (0xB5) | L2 norm computation | EMBEDDING_NORMALIZE normalizes in-place |
| VSCALE (0xB6) | Scalar multiply | Used internally by EMBEDDING_KNN scoring |

The embedding extension is a **semantic layer** above these primitives, adding
index management, structured loading, and multi-vector search capabilities.

---

## 2. Vector Register File Extension

### 2.1 Embedding Vector Registers (ev0–ev15)

The embedding extension introduces 16 dedicated **embedding vector registers**
(ev0–ev15) in addition to the existing general-purpose vector registers (v0–v31).

Each embedding vector register holds a fixed-size array of 32-bit IEEE 754
floating-point values:

```
Embedding Vector Register Layout:

  evN = [f0, f1, f2, ..., f511]

  - Maximum dimensions: 512 (EMBED_DIM_MAX)
  - Active dimensions: stored in per-register metadata field
  - Element type: float32 (IEEE 754 single precision)
  - Memory size per register (full): 512 × 4 = 2048 bytes
  - Confidence tag: per-register, float32 [0.0, 1.0]

  Metadata for evN:
  ┌────────────────────────────────────────────────────┐
  │ active_dims: u16    (number of active dimensions)  │
  │ flags: u16          (reserved, must be zero)       │
  │ confidence: f32     (confidence tag for this vec)  │
  │ source_id: u32      (originating index/node ID)    │
  └────────────────────────────────────────────────────┘
```

### 2.2 Register Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Max registers | 16 (ev0–ev15) | Sufficient for query + top-K buffer |
| Max dimensions | 512 | Covers most text/image embedding models |
| Min dimensions | 1 | Degenerate case for scalar similarity |
| Element size | 4 bytes (float32) | IEEE 754 single precision |
| Alignment | 16-byte aligned | SSE/AVX/NEON compatibility |

### 2.3 Register State Initialization

On agent startup or RESET, all embedding vector registers are in the **empty**
state:

```
  for i in range(16):
      ev[i].active_dims = 0
      ev[i].confidence = 0.0
      ev[i].source_id = 0xFFFFFFFF  (INVALID)
      ev[i].data = undefined        (reading is a trap)
```

### 2.4 Vector Register Aliasing

Embedding vector registers ev0–ev7 alias to general-purpose vector registers
v0–v7 for operations that use the core vector instruction set. This allows
seamless interop:

```
  ev0 ≡ v0    (ev0.data[i] == v0.data[i] for i < min(ev0.active_dims, v0.len))
  ev1 ≡ v1
  ...
  ev7 ≡ v7

  ev8–ev15 are EMBEDDING-ONLY (no core vector alias)
```

When writing to an aliased register via core vector ops (VLOAD, VADD, etc.),
the `active_dims` field is set to the vector length written. When reading via
embedding ops, only `active_dims` elements are considered; remaining elements
are ignored.

---

## 3. Embedding Index Memory Format

### 3.1 Index Header

An embedding index is a contiguous block of memory with a well-defined header
structure. The index supports IVF (Inverted File) partitioning for ANN search.

```
Embedding Index Memory Layout:

Offset  Size  Field                    Description
------  ----  ----                     -----------
0x000   4     magic                    0x454D4244 ("EMBD")
0x004   2     version                 Index format version (currently 1)
0x006   2     flags                    Bit 0: quantized, Bit 1: normalized
0x008   2     num_vectors              Total number of vectors in index
0x00A   2     dims                     Dimensionality of each vector
0x00C   2     num_partitions           IVF partitions (0 = brute force)
0x00E   2     num_probe                Partitions to probe per query
0x010   4     vectors_offset           Byte offset to raw vector data
0x014   4     ids_offset               Byte offset to ID array
0x018   4     partition_offset         Byte offset to partition table
0x01C   4     centroid_offset          Byte offset to partition centroids
0x020   4     quant_offset             Byte offset to quantization params
0x024   4     metadata_offset          Byte offset to per-vector metadata
0x028   4     reserved[0]              Reserved for future use
0x02C   4     reserved[1]              Reserved for future use
0x030   ...   (header ends)            Total header size: 48 bytes
```

### 3.2 Vector Data Section

Vectors are stored contiguously in row-major order:

```
vectors_offset:
  ┌─────────────────────────────────────────────────────────────┐
  │ vector[0]: float32[dims]  │  vector[1]: float32[dims] │ .. │
  └─────────────────────────────────────────────────────────────┘

  If flags & 0x01 (quantized):
    Each vector is stored as int8[dims] with per-vector scale in metadata
    Reconstructed: float[i] = int8[i] * scale

  Total size (non-quantized): num_vectors × dims × 4 bytes
  Total size (quantized):     num_vectors × (dims × 1 + 4) bytes
```

### 3.3 ID Array Section

Each vector has an associated 32-bit identifier:

```
ids_offset:
  ┌──────────┬──────────┬──────────┬─────┐
  │ id[0]    │ id[1]    │ id[2]    │ ... │
  │ u32      │ u32      │ u32      │ u32 │
  └──────────┴──────────┴──────────┴─────┘

  Size: num_vectors × 4 bytes
```

### 3.4 IVF Partition Table (Optional)

When `num_partitions > 0`, the index uses Inverted File Indexing:

```
partition_offset:
  ┌──────────────────────────────────────────────────────────────────┐
  │ partition[0]:                                                   │
  │   start_idx: u32   (first vector index in this partition)       │
  │   count: u32       (number of vectors in this partition)        │
  │   ──────────────────────────────────────────                     │
  │ partition[1]:                                                   │
  │   start_idx: u32                                                 │
  │   count: u32                                                     │
  │   ...                                                            │
  │ partition[num_partitions - 1]:                                  │
  │   start_idx: u32                                                 │
  │   count: u32                                                     │
  └──────────────────────────────────────────────────────────────────┘

  Per-partition size: 8 bytes
  Total size: num_partitions × 8 bytes

centroid_offset:
  ┌──────────────────────────────────────────────────────────────────┐
  │ centroid[0]: float32[dims]  │  centroid[1]: float32[dims] │ ... │
  └──────────────────────────────────────────────────────────────────┘

  Total size: num_partitions × dims × 4 bytes
```

### 3.5 Quantization Parameters Section

```
quant_offset:
  ┌─────────────────────────────────────────────────────────────┐
  │ quant_type: u8        (0=none, 1=int8, 2=uint8, 3=binary) │
  │ scale_bits: u8        (bits for scale factor)               │
  │ reserved: u16                                                    │
  └─────────────────────────────────────────────────────────────┘

  If quantized, per-vector scales follow:
  scale_offset = quant_offset + 4:
    ┌──────────┬──────────┬─────┐
    │ scale[0] │ scale[1] │ ... │ float32
    └──────────┴──────────┴─────┘
```

### 3.6 Example: Minimal 3-Vector Index

```
// 3 vectors, each 4-dimensional, no partitioning
// Vector data:
//   v0 = [0.1, 0.2, 0.3, 0.4], id=100
//   v1 = [1.0, 0.0, 0.5, 0.5], id=200
//   v2 = [0.2, 0.1, 0.0, 0.9], id=300

Memory layout (hex):

0x000: 44 42 4D 45  // magic = "EMBD" (little-endian)
0x004: 01 00        // version = 1
0x006: 00 00        // flags = 0 (not quantized, not normalized)
0x008: 03 00        // num_vectors = 3
0x00A: 04 00        // dims = 4
0x00C: 00 00        // num_partitions = 0 (brute force)
0x00E: 00 00        // num_probe = 0
0x010: 30 00 00 00  // vectors_offset = 0x30
0x014: 60 00 00 00  // ids_offset = 0x60
0x018: 6C 00 00 00  // partition_offset = 0x6C (past end, unused)
0x01C: 6C 00 00 00  // centroid_offset = 0x6C (unused)
0x020: 6C 00 00 00  // quant_offset = 0x6C (unused)
0x024: 6C 00 00 00  // metadata_offset = 0x6C (unused)
0x028: 00 00 00 00  // reserved[0]
0x02C: 00 00 00 00  // reserved[1]

0x030: CD CC CC 3D  // v0[0] = 0.1
0x034: 9A 99 A9 3E  // v0[1] = 0.2
0x038: 33 33 B3 3E  // v0[2] = 0.3
0x03C: 9A 99 99 3E  // v0[3] = 0.4
0x040: 00 00 80 3F  // v1[0] = 1.0
0x044: 00 00 00 00  // v1[1] = 0.0
0x048: 00 00 00 3F  // v1[2] = 0.5
0x04C: 00 00 00 3F  // v1[3] = 0.5
0x050: 9A 99 A9 3E  // v2[0] = 0.2
0x054: CD CC CC 3D  // v2[1] = 0.1
0x058: 00 00 00 00  // v2[2] = 0.0
0x05C: 66 66 66 3F  // v2[3] = 0.9

0x060: 64 00 00 00  // id[0] = 100
0x064: C8 00 00 00  // id[1] = 200
0x068: 2C 01 00 00  // id[2] = 300
```

---

## 4. Opcode Table

| Opcode   | Mnemonic              | Format | Operands           | Description                              |
|----------|----------------------|--------|--------------------|------------------------------------------|
| 0xFFB0   | EMBEDDING_LOAD       | D      | rd, imm8           | Load embedding from memory → ev[rd]      |
| 0xFFB1   | EMBEDDING_STORE      | D      | rd, imm8           | Store ev[rd] → memory at addr imm8       |
| 0xFFB2   | EMBEDDING_KNN        | D      | rd, imm8           | KNN search: index in rd, K=imm8          |
| 0xFFB3   | EMBEDDING_DOT        | E      | rd, rs1, rs2       | Dot product: ev[rd] = ev[rs1] · ev[rs2]  |
| 0xFFB4   | EMBEDDING_NORMALIZE  | B      | rd                 | L2-normalize ev[rd] in-place             |
| 0xFFB5   | EMBEDDING_DISTANCE   | E      | rd, rs1, rs2       | Distance metric between ev[rs1], ev[rs2] |
| 0xFFB6   | EMBEDDING_BUILD_IDX  | E      | rd, rs1, rs2       | Build ANN index from raw vectors          |
| 0xFFB7   | EMBEDDING_BATCH_DOT  | E      | rd, rs1, rs2       | Batched dot product for multiple queries  |
| 0xFFB8   | EMBEDDING_TOPK       | E      | rd, rs1, rs2       | Top-K selection from distance results     |
| 0xFFB9   | EMBEDDING_CFUSE      | E      | rd, rs1, rs2       | Fuse confidence with distance score       |
| 0xFFBA   | EMBEDDING_RESIZE     | D      | rd, imm8           | Resize/reshape embedding dimensions       |
| 0xFFBB   | EMBEDDING_COPY       | E      | rd, rs1, rs2       | Copy ev[rs1] → ev[rd], mask in rs2        |
| 0xFFBC   | EMBEDDING_FILL       | E      | rd, rs1, rs2       | Fill ev[rd] with scalar rs1, dims rs2     |
| 0xFFBD   | EMBEDDING_CAST       | D      | rd, imm8           | Cast element type (imm8: 0=fp32,1=fp16)   |
| 0xFFBE   | EMBEDDING_INFO       | B      | rd                 | Query register metadata → general regs    |
| 0xFFBF   | EMBEDDING_RESET      | A      | -                  | Reset all embedding vector registers      |

**Format reference** (from ISA-002 escape prefix spec):

| Format | Encoding            | Bytes | Operand Fields                    |
|--------|---------------------|-------|-----------------------------------|
| A      | 0xFF opcode         | 2     | (none)                            |
| B      | 0xFF opcode rd      | 3     | rd: embedding register 0–15       |
| C      | 0xFF opcode imm8    | 3     | imm8: immediate value             |
| D      | 0xFF opcode rd imm8 | 4     | rd: reg, imm8: immediate          |
| E      | 0xFF opcode rd rs1 rs2 | 5  | rd, rs1, rs2: registers           |

---

## 5. Opcode Definitions

### 5.1 EMBEDDING_LOAD (0xFFB0) — Format D

**Syntax:** `EMBEDDING_LOAD rd, index_addr`

**Description:** Load an embedding vector from the embedding index at memory
address `index_addr` (interpreted as a register containing the base address of
the index) into embedding vector register `rd`. The register specifiers in
Format D use `rd` as the embedding vector register number (0–15) and `imm8`
as a general-purpose register number whose value contains the memory address
of the index.

**Semantics:**
1. Read the index header from `mem[r[imm8]]`.
2. Validate the magic number (0x454D4244).
3. Read the first vector from the vectors section into `ev[rd]`.
4. Set `ev[rd].active_dims = header.dims`.
5. Set `ev[rd].confidence = 1.0`.
6. Set `ev[rd].source_id = ids[0]`.

**For loading the Nth vector,** the agent must pre-compute the offset:

```
  addr_of_nth = index_base + vectors_offset + N * dims * 4
  MOVI16 r1, addr_of_nth
  ; Then use core VLOAD with the precomputed address
```

For indexed loading within an index, use `EMBEDDING_LOAD` with a pointer to
the specific vector location within the index.

**Trap conditions:**
- `rd` out of range [0, 15] → TRAP_EMBEDDING_REG_INVALID
- Invalid magic number → TRAP_EMBEDDING_INDEX_CORRUPT
- Address not aligned to 16 bytes → TRAP_ALIGNMENT
- `dims > EMBED_DIM_MAX (512)` → TRAP_EMBEDDING_DIM_OVERFLOW

### 5.2 EMBEDDING_STORE (0xFFB1) — Format D

**Syntax:** `EMBEDDING_STORE rd, dest_addr`

**Description:** Store embedding vector register `rd` to memory at the address
contained in general-purpose register `imm8`. Stores only `active_dims` elements.

**Semantics:**
```
  dest = r[imm8]
  for i in range(ev[rd].active_dims):
      mem_write_f32(dest + i * 4, ev[rd].data[i])
```

### 5.3 EMBEDDING_KNN (0xFFB2) — Format D

**Syntax:** `EMBEDDING_KNN rd, K`

**Description:** Perform approximate K-nearest-neighbor search. The query vector
is in `ev[rd]`. The index address is taken from a special-purpose index pointer
register `eip` (set via a prior EMBEDDING_LOAD or core STORE). The `K` parameter
(specified in `imm8`, range 1–255) determines how many neighbors to return.

**Results:** Stored in a result buffer in memory pointed to by `r[rd]`:

```
KNN Result Buffer Layout (pointed to by r[rd]):

Offset  Size  Field                  Description
------  ----  ----                   -----------
0x000   4     num_results            Actual number of results (≤ K)
0x004   4     search_time_us         Wall-clock time of search in μs
0x008   4     partitions_probed      Number of IVF partitions probed
0x00C   4     vectors_scanned        Total vectors distance-computed
0x010   ...   results[]              Array of result entries

Result Entry (per neighbor):
Offset  Size  Field          Description
------  ----  ----           -----------
0x000   4     vector_id      ID from the index
0x004   4     distance       Distance score (float32)
0x008   4     confidence     Confidence-tagged score
0x00C   4     rank           0-based rank (0 = nearest)

Per-entry size: 16 bytes
Total buffer size: 16 + K × 16 bytes
```

**Algorithm (when num_partitions > 0, IVF mode):**

```
  Pseudocode: EMBEDDING_KNN

  def embedding_knn(query: EmbeddingVec, index: Index, K: int) -> KNNResult:
      # 1. If IVF index, find nearest partitions
      if index.num_partitions > 0:
          partition_scores = []
          for p in range(index.num_partitions):
              centroid = load_centroid(index, p)
              dist = euclidean_distance(query, centroid)
              partition_scores.append((p, dist))
          # Select top num_probe partitions
          top_partitions = nlargest(index.num_probe, partition_scores,
                                     key=lambda x: x[1])
          candidates = []
          for p, _ in top_partitions:
              start, count = index.partition[p]
              for i in range(start, start + count):
                  candidates.append(i)
      else:
          # Brute force over all vectors
          candidates = range(index.num_vectors)

      # 2. Compute distances to all candidates
      scored = []
      for idx in candidates:
          vec = load_vector(index, idx)
          if index.flags & QUANTIZED:
              vec = dequantize(vec, index.scales[idx])
          dist = compute_distance(query, vec, metric=EUCLIDEAN)
          scored.append((idx, dist))

      # 3. Select top-K
      top_k = nlargest(K, scored, key=lambda x: -x[1])

      # 4. Write results to buffer
      result.num_results = len(top_k)
      for rank, (idx, dist) in enumerate(top_k):
          result.results[rank].vector_id = index.ids[idx]
          result.results[rank].distance = dist
          result.results[rank].confidence = distance_to_confidence(dist)
          result.results[rank].rank = rank

      return result
```

**Trap conditions:**
- `ev[rd]` is empty (active_dims == 0) → TRAP_EMBEDDING_VEC_EMPTY
- `K == 0` → TRAP_EMBEDDING_PARAM_INVALID
- Index pointer not set → TRAP_EMBEDDING_NO_INDEX
- Result buffer too small → TRAP_EMBEDDING_BUFFER_OVERFLOW
- Dimensions mismatch between query and index → TRAP_EMBEDDING_DIM_MISMATCH

### 5.4 EMBEDDING_DOT (0xFFB3) — Format E

**Syntax:** `EMBEDDING_DOT rd, rs1, rs2`

**Description:** Compute the dot product of two embedding vectors. The result
is stored as a scalar float in general-purpose register `rd` (reinterpreted
as float32). The confidence tag on `rd` is set to the geometric mean of the
source confidences.

**Semantics:**
```
  Pseudocode: EMBEDDING_DOT

  def embedding_dot(rd: int, rs1: int, rs2: int):
      v1 = ev[rs1]
      v2 = ev[rs2]

      if v1.active_dims != v2.active_dims:
          raise TRAP_EMBEDDING_DIM_MISMATCH

      result = 0.0
      for i in range(v1.active_dims):
          result += v1.data[i] * v2.data[i]

      # Store as float32 in general-purpose register
      r[rd] = float32_to_bits(result)
      # Confidence propagation
      c[rd] = sqrt(v1.confidence * v2.confidence)
```

### 5.5 EMBEDDING_NORMALIZE (0xFFB4) — Format B

**Syntax:** `EMBEDDING_NORMALIZE rd`

**Description:** L2-normalize the embedding vector in `ev[rd]` in-place.
After normalization, the vector has unit length (‖v‖₂ = 1.0).

**Semantics:**
```
  Pseudocode: EMBEDDING_NORMALIZE

  def embedding_normalize(rd: int):
      v = ev[rd]

      if v.active_dims == 0:
          raise TRAP_EMBEDDING_VEC_EMPTY

      # Compute L2 norm
      norm_sq = 0.0
      for i in range(v.active_dims):
          norm_sq += v.data[i] * v.data[i]

      norm = sqrt(norm_sq)

      if norm < EMBED_EPSILON (1e-10):
          raise TRAP_EMBEDDING_ZERO_NORM

      # Normalize in-place
      inv_norm = 1.0 / norm
      for i in range(v.active_dims):
          v.data[i] *= inv_norm

      # Confidence propagation: slight decay for numerical precision
      v.confidence *= 0.9999
```

### 5.6 EMBEDDING_DISTANCE (0xFFB5) — Format E

**Syntax:** `EMBEDDING_DISTANCE rd, rs1, rs2`

**Description:** Compute the distance metric between two embedding vectors.
The metric is selected by the **lower 3 bits of `rd`** (used as an enum),
while the result is written to general-purpose register `rd >> 3` (or
alternatively, `rd` is treated as a general-purpose register receiving
the distance and the metric is encoded via a preceding `MOVI` to a control
register).

**Revised encoding:** `rd` receives the float32 distance result. The metric
is selected via a preceding `EMBEDDING_SET_METRIC` implicit state, or by
encoding the metric in a special encoding of `rs2`:

Actually, for FLUX format consistency, we use the following convention:
- `rd` = destination general-purpose register (receives float32 distance)
- `rs1` = first embedding vector register
- `rs2` = second embedding vector register (metric encoded in metadata)

The metric is determined by a **global metric register** (`emetric`), set
via a dedicated immediate. To avoid adding another opcode, the metric is
encoded in the **confidence tag** of `ev[rs2]`:

| Metric Code | Value | Distance Formula |
|-------------|-------|------------------|
| 0           | Euclidean (L2) | d = √(Σ(v1[i] - v2[i])²) |
| 1           | Cosine          | d = 1 - (v1·v2) / (‖v1‖ · ‖v2‖) |
| 2           | Manhattan (L1)  | d = Σ |v1[i] - v2[i]| |
| 3           | Dot product     | d = -v1·v2 (negated, lower = closer) |

The metric is stored in a dedicated 8-bit **embedding control register**
`ectrl`, accessible only through EMBEDDING_DISTANCE by using a side-channel
in the instruction encoding. Specifically, bit 4 of the `rd` field encodes
the metric:

```
  metric = (rd >> 4) & 0x03    // upper 2 bits of rd encode metric
  dest_reg = rd & 0x0F          // lower 4 bits encode destination register
```

**Semantics:**
```
  Pseudocode: EMBEDDING_DISTANCE

  def embedding_distance(rd: int, rs1: int, rs2: int):
      dest = rd & 0x0F
      metric = (rd >> 4) & 0x03
      v1 = ev[rs1]
      v2 = ev[rs2]

      if v1.active_dims != v2.active_dims:
          raise TRAP_EMBEDDING_DIM_MISMATCH

      match metric:
          case 0:  # Euclidean
              sum_sq = 0.0
              for i in range(v1.active_dims):
                  diff = v1.data[i] - v2.data[i]
                  sum_sq += diff * diff
              result = sqrt(sum_sq)

          case 1:  # Cosine distance
              dot = embedding_dot_internal(v1, v2)
              norm1 = embedding_norm_internal(v1)
              norm2 = embedding_norm_internal(v2)
              if norm1 < EPSILON or norm2 < EPSILON:
                  result = 1.0  # max distance for zero vectors
              else:
                  result = 1.0 - (dot / (norm1 * norm2))

          case 2:  # Manhattan
              sum_abs = 0.0
              for i in range(v1.active_dims):
                  sum_abs += abs(v1.data[i] - v2.data[i])
              result = sum_abs

          case 3:  # Negative dot product
              dot = embedding_dot_internal(v1, v2)
              result = -dot

      r[dest] = float32_to_bits(result)
      c[dest] = min(v1.confidence, v2.confidence)
```

### 5.7 EMBEDDING_BUILD_IDX (0xFFB6) — Format E

**Syntax:** `EMBEDDING_BUILD_IDX rd, rs1, rs2`

**Description:** Build an ANN index from a raw array of vectors in memory.
- `rd` = address where the index header will be written
- `rs1` = address of raw vector data (float32 array)
- `rs2` = number of vectors (as integer in general register)

The index is built with IVF partitioning. The number of partitions is
automatically determined as `sqrt(rs2)`.

**Semantics:**
```
  Pseudocode: EMBEDDING_BUILD_IDX

  def embedding_build_idx(rd: int, rs1: int, rs2: int):
      base_addr = r[rd]
      vec_data = r[rs1]
      num_vecs = r[rs2]

      # Detect dimensionality from available metadata or first vector
      dims = detect_dims(vec_data)  # or from a prior EMBEDDING_RESIZE

      # K-means clustering for IVF
      num_partitions = max(1, int(sqrt(num_vecs)))
      centroids = kmeans(vec_data, num_vecs, dims, num_partitions)

      # Assign vectors to partitions
      partitions = assign_partitions(vec_data, num_vecs, dims, centroids)

      # Write index header
      write_header(base_addr, version=1, flags=0,
                   num_vectors=num_vecs, dims=dims,
                   num_partitions=num_partitions, num_probe=min(8, num_partitions))

      # Write partitioned vector data
      write_vectors(base_addr, vec_data, partitions, num_vecs, dims)

      # Write IDs (sequential if not provided)
      write_ids(base_addr, num_vecs)

      # Write centroids
      write_centroids(base_addr, centroids, num_partitions, dims)
```

### 5.8 EMBEDDING_BATCH_DOT (0xFFB7) — Format E

**Syntax:** `EMBEDDING_BATCH_DOT rd, rs1, rs2`

**Description:** Compute dot products of `ev[rd]` against multiple vectors
in `ev[rs1]` (which contains a batch of vectors laid out sequentially).
`rs2` contains the batch size. Results are written to a memory buffer
pointed to by a dedicated result pointer.

This is an optimization for computing a query against multiple candidates
without loading/unloading registers.

### 5.9 EMBEDDING_TOPK (0xFFB8) — Format E

**Syntax:** `EMBEDDING_TOPK rd, rs1, rs2`

**Description:** Select the top-K elements from a scored array. `rd` points
to the scored array in memory, `rs1` contains the array length, `rs2`
contains K. Results are written in-place (reordering the array) with the
top-K elements at the front.

### 5.10 EMBEDDING_CFUSE (0xFFB9) — Format E

**Syntax:** `EMBEDDING_CFUSE rd, rs1, rs2`

**Description:** Fuse a confidence value with a distance score to produce
a confidence-weighted similarity. `rd` = destination register for fused
score. `rs1` = distance score (float32 in register). `rs2` = confidence
value (float32 in register).

```
  fused_score = distance * (1.0 - confidence * confidence_weight)
  where confidence_weight = 0.5 (default, configurable)
```

This enables downstream operations like C_THRESH to make decisions based
on both similarity and certainty.

### 5.11 EMBEDDING_RESIZE (0xFFBA) — Format D

**Syntax:** `EMBEDDING_RESIZE rd, new_dims`

**Description:** Resize the active dimensionality of `ev[rd]`. If
`new_dims > current active_dims`, new elements are zero-initialized.
If `new_dims < current active_dims`, trailing elements are discarded.

**Trap conditions:**
- `new_dims > 512` → TRAP_EMBEDDING_DIM_OVERFLOW
- `new_dims == 0` → TRAP_EMBEDDING_PARAM_INVALID

### 5.12 EMBEDDING_COPY (0xFFBB) — Format E

**Syntax:** `EMBEDDING_COPY rd, rs1, rs2`

**Description:** Copy embedding vector from `ev[rs1]` to `ev[rd]`. `rs2`
is an optional mask register (if nonzero, only copy elements where the
corresponding bit in the mask is set; if zero, copy all elements).

### 5.13 EMBEDDING_FILL (0xFFBC) — Format E

**Syntax:** `EMBEDDING_FILL rd, rs1, rs2`

**Description:** Fill `ev[rd]` with the scalar value in `rs1` (interpreted
as float32). `rs2` specifies the number of dimensions to fill (sets
`active_dims`).

### 5.14 EMBEDDING_CAST (0xFFBD) — Format D

**Syntax:** `EMBEDDING_CAST rd, dtype`

**Description:** Cast all elements of `ev[rd]` to the specified data type.
`dtype` values:
- 0 = float32 (no-op)
- 1 = float16 (half precision, 2 bytes per element)
- 2 = bfloat16 (brain float, 2 bytes per element)
- 3 = int8 quantized (requires external scale factor)

### 5.15 EMBEDDING_INFO (0xFFBE) — Format B

**Syntax:** `EMBEDDING_INFO rd`

**Description:** Query the metadata of `ev[rd]` and store it in general-purpose
registers:
- `r0 = active_dims`
- `r1 = float32_to_bits(confidence)`
- `r2 = source_id`
- `r3 = flags`

### 5.16 EMBEDDING_RESET (0xFFBF) — Format A

**Syntax:** `EMBEDDING_RESET`

**Description:** Reset all 16 embedding vector registers to their initial
(empty) state. Clears active_dims, confidence, source_id, and invalidates
data.

---

## 6. Binary Encoding

### 6.1 Escape Prefix Encoding

All embedding opcodes use the `0xFF` escape prefix followed by the extension
byte in the range `0xB0–0xBF`:

```
┌─────────┬─────────┬──────────┬──────────┬──────────┐
│  0xFF   │  ext8   │ operand  │ operand  │ operand  │
│ (escape)│ (embed) │ byte 1   │ byte 2   │ byte 3   │
└─────────┴─────────┴──────────┴──────────┴──────────┘
  byte 0    byte 1   byte 2    byte 3    byte 4
```

### 6.2 Format-Specific Encodings

#### Format A — EMBEDDING_RESET

```
  0xFF 0xBF   (2 bytes total)
```

#### Format B — EMBEDDING_NORMALIZE, EMBEDDING_INFO

```
  ┌─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │
  └─────┴─────┴─────┘
  byte0 byte1 byte2

  rd: embedding vector register (0–15)
  Note: rd uses only 4 bits; upper 4 bits of byte2 are reserved (must be 0)
```

#### Format C — (Not used in this extension)

Reserved for future immediate-only operations.

#### Format D — EMBEDDING_LOAD, EMBEDDING_STORE, EMBEDDING_KNN, EMBEDDING_RESIZE, EMBEDDING_CAST

```
  ┌─────┬─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │imm8 │
  └─────┴─────┴─────┴─────┘
  byte0 byte1 byte2 byte3

  rd:  embedding vector register (0–15) or packed (rd | metric<<4)
  imm8: immediate value or general-purpose register number
```

#### Format E — EMBEDDING_DOT, EMBEDDING_DISTANCE, EMBEDDING_BUILD_IDX, etc.

```
  ┌─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │ rs1 │ rs2 │
  └─────┴─────┴─────┴─────┴─────┘
  byte0 byte1 byte2 byte3 byte4

  rd:  destination register (4 bits) | metric encoding (4 bits) for EMBEDDING_DISTANCE
  rs1: source register 1
  rs2: source register 2
```

### 6.3 EMBEDDING_DISTANCE Metric Encoding

For EMBEDDING_DISTANCE, the `rd` byte is split:

```
  ┌────────────────────┬────────────────────┐
  │ metric[3:0]        │ dest_reg[3:0]      │
  │ bits 7:4           │ bits 3:0           │
  └────────────────────┴────────────────────┘

  metric values:
    0x0 = EUCLIDEAN
    0x1 = COSINE
    0x2 = MANHATTAN
    0x3 = NEG_DOT_PRODUCT
```

### 6.4 Explicit Format Mode Byte

When using explicit format mode (see ISA-002 Section 2.3.2), an additional
format byte is inserted:

```
  EMBEDDING_DOT rd=ev3, rs1=ev1, rs2=ev2 (explicit format):

  ┌─────┬─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ 0xB3│ 0x04│ 0x03│ 0x01│ 0x02│
  └─────┴─────┴─────┴─────┴─────┴─────┘
  esc   ext   fmt   rd    rs1   rs2

  fmt = 0x04 → Format E
```

---

## 7. Execution Semantics

### 7.1 Pipeline Integration

The embedding extension integrates into the FLUX execution pipeline as a
new functional unit:

```
  ┌────────────┐    ┌──────────────────┐    ┌──────────────┐
  │  Fetch     │───→│  Decode          │───→│  Dispatch    │
  │  (0xFF+ext)│    │  (ext manifest)  │    │  (format)    │
  └────────────┘    └──────────────────┘    └──────┬───────┘
                                                    │
                    ┌───────────────────────────────┘
                    │
         ┌──────────┼──────────┬──────────────┐
         ▼          ▼          ▼              ▼
  ┌────────────┐ ┌──────┐ ┌────────┐ ┌──────────┐
  │ Embedding  │ │Vector│ │ Tensor │ │ General  │
  │ Unit       │ │ Unit │ │ Unit   │ │ Purpose  │
  │ (KNN,      │ │(VADD,│ │(TMATM, │ │ (ADD,    │
  │  DIST,     │ │ VDOT,│ │ TCONV) │ │  MUL,    │
  │  NORM)     │ │ etc) │ │        │ │  etc)    │
  └────────────┘ └──────┘ └────────┘ └──────────┘
```

### 7.2 Memory Access Patterns

Embedding operations exhibit predictable memory access patterns that allow
for significant prefetching:

| Operation     | Access Pattern         | Prefetch Strategy          |
|---------------|------------------------|----------------------------|
| EMBEDDING_LOAD| Sequential read (4N bytes) | Cache-line prefetch    |
| EMBEDDING_KNN | Strided reads (variable) | IVF-guided prefetch      |
| EMBEDDING_DOT| Register-only           | No memory access          |
| EMBEDDING_DISTANCE| Register-only       | No memory access          |

### 7.3 Confidence Propagation Rules

All embedding operations follow the FLUX confidence propagation model:

```
  Rule 1: Binary operations (DOT, DISTANCE)
    c_result = sqrt(c_src1 * c_src2)

  Rule 2: Unary operations (NORMALIZE)
    c_result = c_src * 0.9999  (tiny decay for numerical precision)

  Rule 3: Load operations
    c_result = 1.0  (freshly loaded = fully confident)

  Rule 4: Search operations (KNN)
    c_result = confidence_from_distance(distance)
    where confidence_from_distance(d) = exp(-d * lambda)
    with lambda = 1.0 (default, adjustable)
```

### 7.4 NaN and Infinity Handling

Embedding operations follow IEEE 754 rules with these extensions:

| Input Condition          | Behavior                                  |
|--------------------------|-------------------------------------------|
| NaN in source vector     | Propagates to result, confidence → 0.0    |
| Inf in source vector     | Propagates to result, confidence → 0.0    |
| All-zero vector (NORM)   | TRAP_EMBEDDING_ZERO_NORM                  |
| Negative dimensions      | TRAP_EMBEDDING_PARAM_INVALID              |

---

## 8. Hardware Acceleration Model

### 8.1 Tiers of Acceleration

The embedding extension defines three acceleration tiers:

```
  Tier 0: SOFTWARE FALLBACK (guaranteed, all runtimes)
    - Pure software implementation in the FLUX runtime
    - Bit-identical results to hardware tiers
    - Performance: ~100μs per 128-dim dot product on 1GHz core
    - KNN over 100K vectors: ~50ms

  Tier 1: SIMD ACCELERATION (recommended)
    - Uses SSE4.2/AVX2 (x86) or NEON (ARM) for vector operations
    - Dot product: ~2μs per 128-dim on AVX2
    - KNN over 100K vectors: ~5ms
    - Detection: CPUID (x86) or HWCAP (ARM)

  Tier 2: DEDICATED ACCELERATOR (optional)
    - Custom NPU/GPU for embedding operations
    - KNN over 1M vectors: <1ms
    - Detection: capability flag in extension manifest
    - API: vendor-specific via MMIO registers
```

### 8.2 SIMD Vectorization Strategy

For Tier 1, the inner loops of dot product and distance computation are
vectorized:

```c
// AVX2-optimized dot product (256-bit = 8× float32)
float32_t embedding_dot_avx2(const float32_t *a, const float32_t *b, uint16_t n) {
    __m256 sum = _mm256_setzero_ps();
    uint16_t i = 0;
    for (; i + 8 <= n; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        sum = _mm256_fmadd_ps(va, vb, sum);
    }
    // Horizontal sum
    __m128 hi = _mm256_extractf128_ps(sum, 1);
    __m128 lo = _mm256_castps256_ps128(sum);
    __m128 s = _mm_add_ps(hi, lo);
    s = _mm_hadd_ps(s, s);
    s = _mm_hadd_ps(s, s);
    float result = _mm_cvtss_f32(s);

    // Handle remainder
    for (; i < n; i++) {
        result += a[i] * b[i];
    }
    return result;
}
```

### 8.3 Accelerator Interface (Tier 2)

Tier 2 accelerators expose themselves through MMIO registers mapped at a
configurable base address:

```
Embedding Accelerator MMIO Register Map:

Offset    Size  Name                Access  Description
------    ----  ----                ------  -----------
0x000     4     EACC_VERSION        R       Accelerator version
0x004     4     EACC_CAPABILITIES   R       Feature bitmask
0x008     4     EACC_STATUS         R       0=idle, 1=busy, 2=error
0x00C     4     EACC_COMMAND        W       Command to execute
0x010     8     EACC_SRC_A          RW      Source vector A address
0x018     8     EACC_SRC_B          RW      Source vector B address
0x020     8     EACC_DST            RW      Destination address
0x028     4     EACC_DIMS           RW      Dimensionality
0x02C     4     EACC_COUNT          RW      Vector count (batch)
0x030     4     EACC_METRIC         RW      Distance metric selector
0x034     4     EACC_K              RW      K for KNN search
0x038     4     EACC_INDEX_ADDR     RW      Index base address
0x03C     4     EACC_RESULT_ADDR    RW      Result buffer address
0x040     8     EACC_TIMEOUT        RW      Timeout in cycles
0x048     4     EACC_ERROR_CODE     R       Last error code

Commands (EACC_COMMAND):
  0x01 = CMD_DOT          Compute dot product
  0x02 = CMD_DISTANCE     Compute distance
  0x03 = CMD_NORMALIZE    L2-normalize vector
  0x04 = CMD_KNN          KNN search
  0x05 = CMD_BATCH_DOT    Batch dot products

Capabilities bitmask (EACC_CAPABILITIES):
  Bit 0: Supports dot product
  Bit 1: Supports all distance metrics
  Bit 2: Supports KNN with IVF
  Bit 3: Supports batched operations
  Bit 4: Supports quantized vectors
  Bit 5: Supports async execution
  Bit 6: Supports DMA transfers
  Bits 7-31: Reserved
```

### 8.4 Accelerator Detection

```
  Pseudocode: Accelerator detection

  def detect_embedding_accelerator():
      # Check capability flag in extension manifest
      caps = manifest.get_capabilities(EXT_ID_EMBEDDING)

      if caps & CAP_TIER2_ACCELERATOR:
          # Probe MMIO space
          version = mmio_read(EACC_BASE + 0x000)
          if version != 0xFFFFFFFF:  # not unresponsive
              hw_caps = mmio_read(EACC_BASE + 0x004)
              return AcceleratorInfo(
                  tier=2,
                  version=version,
                  capabilities=hw_caps,
                  mmio_base=EACC_BASE,
              )

      # Check for SIMD support
      if cpu_has_avx2() or cpu_has_neon():
          return AcceleratorInfo(tier=1)

      return AcceleratorInfo(tier=0)  # software fallback
```

---

## 9. Interaction with Existing ISA

### 9.1 Composability with Vector Opcodes

Embedding vector registers ev0–ev7 alias to core vector registers v0–v7.
This means any core vector operation can operate on embedding data:

```
  ; Load embedding into ev0
  EMBEDDING_LOAD  ev0, r1        ; r1 points to index

  ; Use core VDOT for dot product (equivalent but no confidence)
  VDOT  r5, v0, v1              ; r5 = ev0 · ev1 (v0 aliases ev0)

  ; Use embedding DOT for confidence-tagged variant
  EMBEDDING_DOT  r5, ev0, ev1   ; r5 = ev0 · ev1, c[r5] = sqrt(c0*c1)
```

### 9.2 Composability with Tensor Opcodes

Embedding vectors can be fed into tensor operations:

```
  ; Load two embeddings
  EMBEDDING_LOAD  ev0, r1
  EMBEDDING_LOAD  ev1, r2

  ; Stack embeddings into a 2×N tensor
  ; (requires manual tensor construction or TCONV)

  ; Use self-attention between embeddings
  TATTN  r3, r0, r1             ; Q=v0, K=V=v1
```

### 9.3 Composability with Confidence Opcodes

Distance scores from EMBEDDING_DISTANCE and EMBEDDING_KNN can be filtered
using confidence operations:

```
  ; KNN search → results in memory buffer at r5
  EMBEDDING_KNN  ev0, 10        ; K=10, query in ev0

  ; Load nearest neighbor distance
  LOADOFF  r6, r5, 0x14         ; Load distance field (offset 0x14)

  ; Threshold based on confidence
  C_THRESH  r6, 128             ; Skip if confidence < 128/255 ≈ 0.5

  ; If we reach here, the nearest neighbor is sufficiently confident
  ; Process the result...
```

### 9.4 Composability with A2A (Fleet) Opcodes

Embedding search results can be shared between agents:

```
  ; Agent A: perform KNN search and share results
  EMBEDDING_KNN  ev0, 5
  TELL  r1, r2, r5              ; Send result buffer to agent r2

  ; Agent B: receive and use results
  ASK  r3, r1, r4               ; Request embedding results from r1
  ; r3 now contains pointer to KNN results from Agent A
```

### 9.5 Memory Ordering

Embedding operations that access memory (LOAD, STORE, KNN, BUILD_IDX) are
affected by the memory ordering model:

| Operation        | Memory Ordering Requirement |
|------------------|------------------------------|
| EMBEDDING_LOAD   | Load-load ordering           |
| EMBEDDING_STORE  | Store-store ordering         |
| EMBEDDING_KNN    | Load-load ordering (read-only) |
| EMBEDDING_BUILD_IDX | Store-store ordering      |

The SYN instruction (0x07) can be used to enforce ordering when needed.

---

## 10. Error Handling & Trap Codes

### 10.1 Trap Code Allocation

Embedding trap codes are allocated in the range `0xE0–0xEF` (within the
extension trap code space):

| Trap Code | Name                          | Severity | Description                              |
|-----------|-------------------------------|----------|------------------------------------------|
| 0xE0      | TRAP_EMBEDDING_REG_INVALID    | FATAL    | Embedding register index out of range    |
| 0xE1      | TRAP_EMBEDDING_VEC_EMPTY      | RECOVER  | Operation on empty (unloaded) vector     |
| 0xE2      | TRAP_EMBEDDING_DIM_MISMATCH   | RECOVER  | Dimension count mismatch between operands|
| 0xE3      | TRAP_EMBEDDING_DIM_OVERFLOW   | FATAL    | Dimension count exceeds 512              |
| 0xE4      | TRAP_EMBEDDING_ZERO_NORM      | RECOVER  | Cannot normalize zero-length vector      |
| 0xE5      | TRAP_EMBEDDING_INDEX_CORRUPT  | FATAL    | Index magic number or header invalid     |
| 0xE6      | TRAP_EMBEDDING_NO_INDEX       | RECOVER  | Index pointer not set for KNN            |
| 0xE7      | TRAP_EMBEDDING_BUFFER_OVERFLOW| FATAL    | Result buffer too small for KNN results  |
| 0xE8      | TRAP_EMBEDDING_PARAM_INVALID  | RECOVER  | Invalid parameter (K=0, negative dims)   |
| 0xE9      | TRAP_EMBEDDING_QUANT_ERROR    | FATAL    | Dequantization failure                   |
| 0xEA      | TRAP_EMBEDDING_ACCEL_FAULT    | FATAL    | Hardware accelerator unrecoverable error |
| 0xEB      | TRAP_EMBEDDING_TIMEOUT        | RECOVER  | Operation exceeded timeout               |
| 0xEC      | TRAP_EMBEDDING_ALIGNMENT      | FATAL    | Memory address not properly aligned      |
| 0xED–0xEF  | Reserved                      | —        | Reserved for future use                  |

### 10.2 Error Recovery

RECOVER-severity traps push the current PC to the fault stack and jump to
the handler installed via HANDLER (0xE8). The handler can inspect the trap
code and decide whether to retry, skip, or abort.

FATAL-severity traps immediately halt the agent with an error flag set in
the status register.

---

## 11. Performance Considerations

### 11.1 Complexity Analysis

| Operation         | Time Complexity          | Space Complexity |
|-------------------|--------------------------|------------------|
| EMBEDDING_LOAD    | O(D)                     | O(D)             |
| EMBEDDING_STORE   | O(D)                     | O(1)             |
| EMBEDDING_DOT     | O(D)                     | O(1)             |
| EMBEDDING_NORMALIZE| O(D)                    | O(1)             |
| EMBEDDING_DISTANCE| O(D)                     | O(1)             |
| EMBEDDING_KNN     | O(P × (N/P) × D + K×log K) | O(K + P)       |
| EMBEDDING_BUILD_IDX| O(N × P × I × D)       | O(N × D + P × D) |

Where:
- D = embedding dimensionality
- N = total vectors in index
- P = number of IVF partitions probed
- K = number of nearest neighbors requested
- I = number of k-means iterations for index building

### 11.2 Latency Estimates (Tier 1, AVX2, 128-dim)

| Operation         | Latency (single)  | Throughput |
|-------------------|-------------------|------------|
| EMBEDDING_DOT     | ~0.2 μs           | 5 GHz ops  |
| EMBEDDING_NORMALIZE| ~0.25 μs         | 4 GHz ops  |
| EMBEDDING_DISTANCE| ~0.3 μs (Euclidean)| 3 GHz ops |
| EMBEDDING_KNN (K=10, N=100K) | ~5 ms  | 200 queries/s |
| EMBEDDING_KNN (K=10, N=1M)  | ~30 ms  | 33 queries/s |
| EMBEDDING_BUILD_IDX (N=100K) | ~500 ms | 2 builds/s |

### 11.3 Memory Bandwidth Requirements

| Operation         | Memory Reads       | Memory Writes      |
|-------------------|--------------------|--------------------|
| EMBEDDING_DOT     | 0 (register-only)  | 0                  |
| EMBEDDING_KNN     | ~P × (N/P) × D × 4B| K × 16B (results) |
| KNN N=100K, D=128 | ~51 MB (probe 10%) | 160 B              |
| KNN N=1M, D=128   | ~512 MB (probe 10%)| 160 B              |

### 11.4 Optimization Guidelines

1. **Normalize vectors before indexing** to enable cosine distance via dot
   product (faster than computing norms during search).
2. **Use IVF with appropriate num_probe** — start with `sqrt(num_partitions)`
   and adjust based on recall requirements.
3. **Quantize large indices** — int8 quantization reduces memory by 4× with
   typically <2% recall loss.
4. **Batch queries** when possible — EMBEDDING_BATCH_DOT amortizes overhead.
5. **Pre-allocate result buffers** — avoid dynamic allocation during hot loops.

---

## 12. Bytecode Examples

### 12.1 Example 1: Basic Dot Product

Compute the dot product of two 128-dimensional embedding vectors and check
if the similarity exceeds a threshold.

```
  ; =========================================================
  ; Example: Basic embedding dot product with threshold check
  ; =========================================================

  ; Load two embedding vectors from memory
  MOVI16  r1, 0x1000           ; r1 = address of embedding index A
  MOVI16  r2, 0x2000           ; r2 = address of embedding index B
  EMBEDDING_LOAD  ev0, 0       ; Load first vector from index at r[0]=r1
                                 ; (r1 already set, ext byte encodes reg)
  EMBEDDING_LOAD  ev1, 1       ; Load second vector from index at r[1]=r2

  ; Compute dot product
  EMBEDDING_DOT  r3, ev0, ev1  ; r3 = ev0 · ev1 (as float32 bits)
                                 ; c[r3] = sqrt(c[ev0] * c[ev1])

  ; Threshold check: if confidence >= 0.7, proceed
  C_THRESH  r3, 179            ; 179/255 ≈ 0.702

  ; If below threshold, skip to alternative path
  JZ  r3, alternative_path     ; (r3 holds modified flags/confidence)

  ; High similarity path — use the result
  ITOF  r4, r3                 ; Convert to float
  ...

  ; Byte sequence (explicit format mode):
  ; 40 10 00       MOVI16 r1, 0x1000
  ; 40 20 00       MOVI16 r2, 0x2000
  ; FF B0 00 01    EMBEDDING_LOAD ev0, r1  (explicit: FF B0 03 00 01)
  ; FF B0 01 02    EMBEDDING_LOAD ev1, r2
  ; FF B3 03 00 01 EMBEDDING_DOT r3, ev0, ev1
  ; 69 03 B3       C_THRESH r3, 0xB3 (179)
  ; 3C 03 1A       JZ r3, offset_to_alternative
```

### 12.2 Example 2: KNN Search for Semantic Retrieval

Search an embedding index for the 5 most similar vectors to a query.

```
  ; =========================================================
  ; Example: KNN search for top-5 nearest neighbors
  ; =========================================================

  ; Set up: query vector is in ev0, index at r1
  MOVI16  r1, 0x50000          ; r1 = base address of embedding index
  EMBEDDING_LOAD  ev0, 1       ; Load query vector (assume r[1] set above)

  ; Allocate result buffer (16 + 5 × 16 = 96 bytes)
  MALLOC  r2, r0, 96           ; r2 = allocated buffer

  ; Set index pointer for KNN
  ; (r2 will be used as result destination)
  ; EMBEDDING_KNN uses ev[rd] as query, writes to r[rd]
  EMBEDDING_KNN  ev0, 5        ; K=5, query in ev0, results → buffer at r[0]

  ; Read number of results
  LOADOFF  r3, r0, 0           ; r3 = num_results (should be 5)

  ; Read nearest neighbor ID
  LOADOFF  r4, r0, 16          ; r4 = results[0].vector_id
  LOADOFF  r5, r0, 20          ; r5 = results[0].distance

  ; Read second nearest neighbor
  LOADOFF  r6, r0, 32          ; r6 = results[1].vector_id
  LOADOFF  r7, r0, 36          ; r7 = results[1].distance

  ; Confidence-weighted decision
  C_THRESH  r5, 200            ; Require high confidence for nearest

  ; Store the top result ID for downstream use
  STOREOF  r4, r8, 0           ; mem[r8 + 0] = best_match_id

  ; Free the result buffer
  FREE  r2, r0, 0              ; (uses Format G)

  ; Byte sequence (implicit format mode, assuming manifest):
  ; 40 00 50       MOVI16 r0, 0x5000  (base addr)
  ; FF B0 01 00    EMBEDDING_LOAD ev1, r0
  ; FF B2 01 05    EMBEDDING_KNN ev1, 5
  ; 48 03 00 00    LOADOFF r3, r0, 0x0000
  ; 48 04 00 10    LOADOFF r4, r0, 0x0010
  ; 48 05 00 14    LOADOFF r5, r0, 0x0014
```

### 12.3 Example 3: Cosine Similarity Ranking

Normalize two vectors and compute cosine similarity.

```
  ; =========================================================
  ; Example: Cosine similarity between two embeddings
  ; =========================================================

  ; Load vectors
  EMBEDDING_LOAD  ev0, 0       ; Load from memory via r[0]
  EMBEDDING_LOAD  ev1, 1       ; Load from memory via r[1]

  ; Normalize both vectors (required for cosine distance)
  EMBEDDING_NORMALIZE  ev0
  EMBEDDING_NORMALIZE  ev1

  ; Compute cosine distance (metric=1 encoded in rd)
  ; rd = 0x10 | dest_reg = 0x10 | 0x02 = 0x12
  ; So dest is r2, metric is COSINE (1)
  EMBEDDING_DISTANCE  0x12, ev0, ev1   ; r2 = cosine_distance(ev0, ev1)

  ; Convert distance to similarity: similarity = 1 - distance
  MOVI16  r3, 0x3F800000       ; r3 = float bits for 1.0
  ; (simplified — actual float subtraction needed)
  FSUB  r4, r3, r2             ; r4 = 1.0 - cosine_distance = similarity

  ; Store similarity for ranking
  STOREOF  r4, r10, 0          ; Store at ranking buffer
```

### 12.4 Example 4: Batch Similarity Search

Compute similarity of one query against multiple candidates.

```
  ; =========================================================
  ; Example: Compare query against 100 candidates
  ; =========================================================

  ; Load query embedding
  EMBEDDING_LOAD  ev0, 0       ; ev0 = query vector
  EMBEDDING_NORMALIZE  ev0     ; Normalize for cosine similarity

  ; Loop over 100 candidates
  MOVI16  r1, 100              ; r1 = candidate count
  MOVI16  r2, 0                ; r2 = loop index

loop_start:
  ; Load candidate (ev1)
  ; Compute address: candidate_base + r2 * dims * 4
  MUL  r3, r2, r4              ; r3 = index * stride (r4 = dims * 4)
  ADD  r3, r3, r5              ; r3 += candidate_base (r5)
  EMBEDDING_LOAD  ev1, 3       ; Load from address in r[3]

  ; Normalize candidate
  EMBEDDING_NORMALIZE  ev1

  ; Compute cosine distance
  EMBEDDING_DISTANCE  0x16, ev0, ev1   ; r6 = cosine_distance

  ; Store distance in results array
  STOREOF  r6, r7, 0           ; results[r2] = distance
  ADDI16  r7, 4                ; Advance result pointer

  ; Next iteration
  INC  r2
  CMP_LT  r8, r2, r1           ; r8 = (r2 < r1)
  JNZ  r8, loop_start          ; Continue loop

  ; Find top-K from results array using EMBEDDING_TOPK
  ; (or sort using core SORT opcode)
```

### 12.5 Example 5: Multi-Agent Embedding Exchange

Two agents collaborate: Agent A computes embeddings, Agent B performs search.

```
  ; =========================================================
  ; Example: Multi-agent embedding search collaboration
  ; =========================================================

  ; --- Agent A: Embedding Computation Agent ---

  ; Load raw data and compute embedding (simplified)
  EMBEDDING_LOAD  ev0, 0       ; Load from raw data memory
  EMBEDDING_NORMALIZE  ev0

  ; Store embedding to shared memory for Agent B
  EMBEDDING_STORE  ev0, 0      ; Store to shared buffer at r[0]

  ; Notify Agent B
  TELL  r1, r2, r0             ; Send shared buffer address to agent r2

  ; --- Agent B: Search Agent ---

  ; Wait for embedding from Agent A
  AWAIT  r3, r1, r4            ; Wait for signal, embedding addr → r3

  ; Load shared embedding into local vector register
  EMBEDDING_LOAD  ev0, 3       ; Load from shared address in r[3]

  ; Set index pointer and perform KNN
  MOVI16  r5, 0xA0000          ; Local embedding index address
  EMBEDDING_KNN  ev0, 10       ; Find 10 nearest neighbors

  ; Send results back to Agent A
  TELL  r6, r2, r0             ; Return KNN results
```

### 12.6 Example 6: Index Building and KNN Pipeline

Complete pipeline from raw vectors to ANN index to KNN query.

```
  ; =========================================================
  ; Example: Build index and query — full pipeline
  ; =========================================================

  ; Step 1: Set up raw vector data
  MOVI16  r0, 0x100000         ; Raw vectors at 1MB
  MOVI16  r1, 10000            ; 10,000 vectors

  ; Step 2: Build ANN index
  MOVI16  r2, 0x200000         ; Index output at 2MB
  EMBEDDING_BUILD_IDX  r2, r0, r1   ; Build IVF index

  ; Step 3: Load a query vector
  MOVI16  r3, 0x300000         ; Query vector address
  EMBEDDING_LOAD  ev0, 3

  ; Step 4: Normalize for cosine similarity
  EMBEDDING_NORMALIZE  ev0

  ; Step 5: KNN search (K=20, using index at r2)
  ; Set up index pointer
  EMBEDDING_KNN  ev0, 20       ; Search with K=20

  ; Step 6: Process results
  ; Results are in buffer, iterate and filter by confidence
  MOVI16  r4, 20               ; K=20
  MOVI16  r5, 16               ; Start of results array (offset 16)

result_loop:
  LOADOFF  r6, r0, 0           ; vector_id
  LOADOFF  r7, r0, 4           ; distance
  LOADOFF  r8, r0, 8           ; confidence

  ; Filter: only keep results with confidence > 0.8
  MOVI16  r9, 204              ; 204/255 ≈ 0.8
  CMP_GT  r10, r8, r9          ; r10 = (confidence > threshold)
  JZ  r10, skip_result         ; Skip if below threshold

  ; Process high-confidence result
  ; ... store to output buffer ...
  STOREOF  r6, r11, 0          ; Store vector_id
  ADDI16  r11, 4               ; Advance output pointer

skip_result:
  ADDI16  r5, 16               ; Next result entry (16 bytes)
  ADDI16  r0, 16               ; Advance source pointer
  DEC  r4                      ; Decrement counter
  JNZ  r4, result_loop         ; Continue if more results

  ; Done — output buffer contains filtered high-confidence matches
  HALT
```

---

## 13. Formal Semantics

### 13.1 Operational Semantics

We define the embedding extension semantics using a small-step operational
semantics notation. The machine state is extended:

```
  σ = (regs, vregs, evregs, mem, pc, conf, eip)

  where:
    regs:  int[256]          general-purpose registers
    vregs: float32[32][512]  core vector registers
    evregs: EmbeddingVec[16] embedding vector registers
    mem:   byte[∞]          linear memory
    pc:    int               program counter
    conf:  float[256]        confidence tags
    eip:   int               embedding index pointer
```

### 13.2 EMBEDDING_DOT Rule

```
  Rule: EMBEDDING_DOT

  Precondition:
    σ.evregs[rs1].active_dims = σ.evregs[rs2].active_dims = D > 0

  Effect:
    result = Σ(i=0..D-1) σ.evregs[rs1].data[i] × σ.evregs[rs2].data[i]
    σ.regs[rd] = float32_bits(result)
    σ.conf[rd] = √(σ.evregs[rs1].confidence × σ.evregs[rs2].confidence)
    σ.pc += 5  (Format E size with escape prefix)

  Notation: ⟨EMBEDDING_DOT rd rs1 rs2, σ⟩ → ⟨σ'⟩
```

### 13.3 EMBEDDING_NORMALIZE Rule

```
  Rule: EMBEDDING_NORMALIZE

  Precondition:
    σ.evregs[rd].active_dims = D > 0
    norm = √(Σ(i=0..D-1) σ.evregs[rd].data[i]²) > ε

  Effect:
    for i in 0..D-1:
        σ.evregs[rd].data[i] = σ.evregs[rd].data[i] / norm
    σ.evregs[rd].confidence = σ.evregs[rd].confidence × 0.9999
    σ.pc += 3  (Format B size with escape prefix)
```

### 13.4 EMBEDDING_KNN Rule (Simplified)

```
  Rule: EMBEDDING_KNN (brute-force variant)

  Precondition:
    σ.evregs[rd].active_dims = D > 0
    σ.eip points to valid index
    mem[σ.eip].num_vectors = N ≥ K
    mem[σ.eip].dims = D

  Effect:
    scored = [(i, distance(σ.evregs[rd], load(mem, σ.eip, i, D))) for i in 0..N-1]
    top_k = sort_by(scored, ascending, key=distance)[0:K]
    write_results(mem, σ.regs[rd], top_k)
    σ.pc += 4
```

### 13.5 Type Safety Invariant

```
  Invariant: Embedding Register Consistency

  For all evregs[i]:
    if evregs[i].active_dims > 0:
      1. evregs[i].confidence ∈ [0.0, 1.0]
      2. evregs[i].data[j] is finite IEEE 754 float32 for all j < active_dims
      3. evregs[i].source_id ∈ u32 or INVALID (0xFFFFFFFF)
    else:
      evregs[i].data is undefined (reading is a trap)
```

---

## 14. Appendix

### 14.1 Opcode Quick Reference

| Hex     | Assembly                        | Description                    |
|---------|---------------------------------|--------------------------------|
| FF B0   | EMBEDDING_LOAD rd, reg          | Load vector from index          |
| FF B1   | EMBEDDING_STORE rd, reg         | Store vector to memory          |
| FF B2   | EMBEDDING_KNN rd, K             | K-nearest-neighbor search       |
| FF B3   | EMBEDDING_DOT rd, rs1, rs2      | Dot product with confidence     |
| FF B4   | EMBEDDING_NORMALIZE rd          | L2-normalize in-place           |
| FF B5   | EMBEDDING_DISTANCE rd, rs1, rs2 | Distance metric (4 types)       |
| FF B6   | EMBEDDING_BUILD_IDX rd, rs1, rs2| Build IVF index from vectors    |
| FF B7   | EMBEDDING_BATCH_DOT rd, rs1, rs2| Batched dot products            |
| FF B8   | EMBEDDING_TOPK rd, rs1, rs2     | Top-K selection                 |
| FF B9   | EMBEDDING_CFUSE rd, rs1, rs2    | Fuse confidence with distance   |
| FF BA   | EMBEDDING_RESIZE rd, dims       | Resize vector dimensions        |
| FF BB   | EMBEDDING_COPY rd, rs1, rs2     | Copy with optional mask         |
| FF BC   | EMBEDDING_FILL rd, val, dims    | Fill with scalar value          |
| FF BD   | EMBEDDING_CAST rd, dtype        | Cast element type               |
| FF BE   | EMBEDDING_INFO rd               | Query register metadata         |
| FF BF   | EMBEDDING_RESET                 | Reset all registers             |

### 14.2 Distance Metric Formulas

```
Euclidean (L2):
  d(a, b) = √(Σᵢ (aᵢ - bᵢ)²)

Cosine:
  d(a, b) = 1 - (a · b) / (‖a‖₂ × ‖b‖₂)

Manhattan (L1):
  d(a, b) = Σᵢ |aᵢ - bᵢ|

Negative Dot Product:
  d(a, b) = -(a · b)
  (useful when vectors are pre-normalized; lower = more similar)
```

### 14.3 Confidence-to-Distance Mapping

```
  confidence(d, λ=1.0) = exp(-d × λ)

  Examples:
    d = 0.0  → confidence = 1.000
    d = 0.1  → confidence = 0.905
    d = 0.5  → confidence = 0.607
    d = 1.0  → confidence = 0.368
    d = 2.0  → confidence = 0.135
    d = 5.0  → confidence = 0.007
```

### 14.4 Revision History

| Version | Date       | Author   | Changes                              |
|---------|------------|----------|--------------------------------------|
| 1.0     | 2026-04-12 | Super Z  | Initial specification (EMBED-001)    |

### 14.5 Extension Manifest Entry

For inclusion in the FLUX bytecode extension manifest (see ISA-002 Section 3.1.1):

```
  ext_id:            0x00000006
  ext_version_major: 1
  ext_version_minor: 0
  ext_name:          "org.flux.embedding"
  ext_name_len:      19
  opcode_base:       0xFFB0
  opcode_count:      16
  required:          0  (optional)
  format_table:
    offset 0x00  format E   EMBEDDING_LOAD (actually Format D — see note)
    offset 0x01  format D   EMBEDDING_STORE
    offset 0x02  format D   EMBEDDING_KNN
    offset 0x03  format E   EMBEDDING_DOT
    offset 0x04  format B   EMBEDDING_NORMALIZE
    offset 0x05  format E   EMBEDDING_DISTANCE
    offset 0x06  format E   EMBEDDING_BUILD_IDX
    offset 0x07  format E   EMBEDDING_BATCH_DOT
    offset 0x08  format E   EMBEDDING_TOPK
    offset 0x09  format E   EMBEDDING_CFUSE
    offset 0x0A  format D   EMBEDDING_RESIZE
    offset 0x0B  format E   EMBEDDING_COPY
    offset 0x0C  format E   EMBEDDING_FILL
    offset 0x0D  format D   EMBEDDING_CAST
    offset 0x0E  format B   EMBEDDING_INFO
    offset 0x0F  format A   EMBEDDING_RESET
```

---

*End of FLUX ISA v3 Embedding Search Extension Specification (EMBED-001)*
