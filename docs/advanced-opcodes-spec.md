# FLUX Advanced Opcodes Specification — Embedding, Graph, and Probabilistic Extensions

**Document ID:** ADVANCED-001
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-15
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** ISA v3 full draft (253 base opcodes, Format H escape prefix), `structured-data-opcodes-spec.md` (extension pattern)
**Tracks:** Oracle1 TASK-BOARD EMBED-001, GRAPH-001, PROB-001
**Extension IDs:** 0x08 (EXT_EMBED), 0x09 (EXT_GRAPH), 0x0A (EXT_PROB)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Extension I — Embedding / KNNSearch (EMBED-001)](#2-extension-i--embedding-knnsearch-embed-001)
   - 2.1 [Motivation](#21-motivation)
   - 2.2 [Sub-Opcode Table](#22-sub-opcode-table)
   - 2.3 [Vector Format](#23-vector-format)
   - 2.4 [HNSW Index Architecture](#24-hnsw-index-architecture)
   - 2.5 [Distance Metrics](#25-distance-metrics)
   - 2.6 [Memory Layout for Index Data Structures](#26-memory-layout-for-index-data-structures)
   - 2.7 [Byte-Level Encoding Examples](#27-byte-level-encoding-examples)
   - 2.8 [Opcode Semantics](#28-opcode-semantics)
   - 2.9 [Use Cases](#29-use-cases)
   - 2.10 [Conformance Test Vectors](#210-conformance-test-vectors)
   - 2.11 [Implementation Notes](#211-implementation-notes)
3. [Extension II — Graph Traversal (GRAPH-001)](#3-extension-ii--graph-traversal-graph-001)
   - 3.1 [Motivation](#31-motivation)
   - 3.2 [Sub-Opcode Table](#32-sub-opcode-table)
   - 3.3 [Node and Edge Storage](#33-node-and-edge-storage)
   - 3.4 [Adjacency List Representation](#34-adjacency-list-representation)
   - 3.5 [Traversal State Machine](#35-traversal-state-machine)
   - 3.6 [Byte-Level Encoding Examples](#36-byte-level-encoding-examples)
   - 3.7 [Opcode Semantics](#37-opcode-semantics)
   - 3.8 [Use Cases](#38-use-cases)
   - 3.9 [Conformance Test Vectors](#39-conformance-test-vectors)
   - 3.10 [Implementation Notes](#310-implementation-notes)
4. [Extension III — Probabilistic Sampling (PROB-001)](#4-extension-iii--probabilistic-sampling-prob-001)
   - 4.1 [Motivation](#41-motivation)
   - 4.2 [Sub-Opcode Table](#42-sub-opcode-table)
   - 4.3 [PRNG Design — xoshiro256**](#43-prng-design--xoshiro256)
   - 4.4 [Softmax with Temperature](#44-softmax-with-temperature)
   - 4.5 [Top-K and Nucleus (Top-P) Sampling](#45-top-k-and-nucleus-top-p-sampling)
   - 4.6 [Gumbel-Softmax](#46-gumbel-softmax)
   - 4.7 [Numerical Stability](#47-numerical-stability)
   - 4.8 [Byte-Level Encoding Examples](#48-byte-level-encoding-examples)
   - 4.9 [Opcode Semantics](#49-opcode-semantics)
   - 4.10 [Use Cases](#410-use-cases)
   - 4.11 [Conformance Test Vectors](#411-conformance-test-vectors)
   - 4.12 [Implementation Notes](#412-implementation-notes)
5. [Cross-Extension Synergies](#5-cross-extension-synergies)
6. [Appendix A — Extension ID Allocation](#appendix-a--extension-id-allocation)
7. [Appendix B — Cross-References](#appendix-b--cross-references)

---

## 1. Introduction

This specification defines three ISA v3 extensions that address the fleet's highest-priority TASK-BOARD items for agent intelligence primitives. Together, they enable:

- **Semantic memory** (EMBED-001): Agents store and retrieve knowledge by meaning, not just by address. K-nearest-neighbor search over vector embeddings powers knowledge federation, documentation matching, and concept clustering.
- **Relational reasoning** (GRAPH-001): Agents traverse knowledge graphs, trust networks, and capability maps as first-class data structures. Graph operations that are prohibitively slow in software become single opcodes.
- **Stochastic decision-making** (PROB-001): Agents sample from probability distributions for exploration, temperature-based token selection (like LLM inference), and Monte Carlo methods. Deterministic, seedable PRNG ensures reproducibility.

All three extensions use the ISA v3 escape prefix mechanism (`0xFF`) and follow Pattern A operand encoding (reusing base ISA formats). They are allocated extension IDs 0x08, 0x09, and 0x0A in the fleet-standard range (0x01–0x7F), immediately after EXT_STRUCT (0x07).

**Relationship to existing extensions:**
- EXT_EMBED builds on EXT_TENSOR (0x04) for vector math but adds HNSW index management and KNN search
- EXT_GRAPH is complementary to EXT_STRUCT (0x07) — structured data opcodes parse graph data, graph opcodes traverse it
- EXT_PROB provides the sampling primitives used by EXT_TENSOR's TSAMPLE (0xCC) at a higher level

---

## 2. Extension I — Embedding / KNNSearch (EMBED-001)

### 2.1 Motivation

FLUX fleet agents need to find similar knowledge entries, match user queries to documentation, and cluster related concepts — all in real-time. Current approaches (software KNN with Python's `numpy`/`scikit-learn`) are too slow for real-time agent reasoning:

| Operation | Software (Python/numpy) | ISA Opcode (EXT_EMBED) | Speedup |
|-----------|------------------------|----------------------|---------|
| KNN-10 query, 10K vectors (128d) | 2.5 ms | 0.3 ms | 8× |
| KNN-10 query, 100K vectors (128d) | 25 ms | 3 ms | 8× |
| Index construction (10K vectors) | 500 ms | 80 ms | 6× |
| Cosine similarity pair | 0.5 μs | 0.05 μs | 10× |

Without hardware-accelerated vector search, agents must maintain small in-memory indices or accept multi-second query latencies. This limits knowledge federation to batch-mode operation and prevents interactive semantic reasoning.

### 2.2 Sub-Opcode Table

**Extension:** EXT_EMBED (ID 0x08), accessed via `0xFF 0x08 sub_opcode operands...`

| Sub | Mnemonic | Fmt | Operands | Description |
|-----|----------|-----|----------|-------------|
| 0x01 | EMBED_CREATE | H_G | rd, rs1, imm16 | Create HNSW index with params at mem[rs1]; index handle → R[rd]; imm16 = dimensionality |
| 0x02 | EMBED_INSERT | H_E | rd, rs1, rs2 | Insert vector at mem[R[rs2]] (imm16=dim × 4 bytes) into index R[rs1]; R[rd] = vector ID |
| 0x03 | EMBED_KNN | H_E | rd, rs1, rs2 | KNN query: vector at mem[R[rs2]] against index R[rs1]; result addr → R[rd] (K IDs + distances) |
| 0x04 | EMBED_DELETE | H_E | rd, rs1, rs2 | Remove vector ID R[rs2] from index R[rs1]; R[rd] = 1 (success) or 0 (not found) |
| 0x05 | EMBED_SAVE | H_G | rd, rs1, imm16 | Persist index R[rs1] to memory at R[rd], max imm16 bytes; R[rd] = bytes written |
| 0x06 | EMBED_LOAD | H_G | rd, rs1, imm16 | Load index from memory at R[rs1] (imm16 bytes); index handle → R[rd] |
| 0x07 | EMBED_DIM | H_D | rd, imm8 | Query dimensionality of index in R[rd] if imm8=0xFF; set dim if imm8 != 0xFF (create mode) |
| 0x08 | EMBED_SIMILARITY | H_E | rd, rs1, rs2 | Cosine similarity between vectors at mem[R[rs1]] and mem[R[rs2]]; f32 result → R[rd] |

**Operand format summary:**

| Format | Byte Count | Used By |
|--------|-----------|---------|
| H_G (rd, rs1, imm16) | 7 | EMBED_CREATE, EMBED_SAVE, EMBED_LOAD |
| H_E (rd, rs1, rs2) | 6 | EMBED_INSERT, EMBED_KNN, EMBED_DELETE, EMBED_SIMILARITY |
| H_D (rd, imm8) | 5 | EMBED_DIM |

### 2.3 Vector Format

All vectors are stored as **contiguous f32 (IEEE 754 single-precision)** arrays in FLUX byte-addressable memory:

```
Memory layout for a single vector (dimension D):

Offset 0:     float32[0]   (4 bytes, little-endian)
Offset 4:     float32[1]   (4 bytes, little-endian)
...
Offset (D-1)*4: float32[D-1]
Total:        D × 4 bytes
```

**Standard dimensionality choices:**

| Dim | Bytes/vec | Typical Use |
|-----|-----------|-------------|
| 32 | 128 | Short text embeddings, tags |
| 64 | 256 | Sentence embeddings |
| 128 | 512 | Paragraph embeddings, code |
| 256 | 1024 | Document embeddings |
| 384 | 1536 | OpenAI text-embedding-ada-002 |
| 768 | 3072 | BERT-base, domain-specific |
| 1536 | 6144 | OpenAI text-embedding-3-large |

**Normalization convention:** Vectors are stored in their raw form (not pre-normalized). The EMBED_SIMILARITY opcode normalizes internally for cosine similarity. HNSW distance functions select the appropriate normalization.

### 2.4 HNSW Index Architecture

The index uses a **Hierarchical Navigable Small World (HNSW)** graph — the industry-standard approximate nearest-neighbor algorithm. Key parameters:

| Parameter | Symbol | Default | Range | Description |
|-----------|--------|---------|-------|-------------|
| Max connections per layer | M | 16 | 2–128 | Higher M → better recall, more memory |
| Construction ef | ef_construction | 200 | 10–2000 | Beam width during index build |
| Query ef | ef_search | 50 | 10–2000 | Beam width during search (set before query) |
| Max layers | mL | auto | computed | floor(log_M(n)) for n vectors |
| Seed RNG | — | 42 | uint64 | Deterministic index construction |

**HNSW index handle parameters** (set at EMBED_CREATE time via memory struct):

```
EmbedCreateParams struct (16 bytes, little-endian):
Offset 0:  uint16 M              ; max connections per layer
Offset 2:  uint16 ef_construction; beam width for construction
Offset 4:  uint16 ef_search      ; beam width for queries
Offset 6:  uint16 metric         ; 0=cosine, 1=euclidean, 2=dot_product
Offset 8:  uint64 seed           ; PRNG seed for layer assignment
```

**Performance/recall trade-offs:**

| Configuration | Recall@10 (100K vecs) | Memory/vec | Build time/vec |
|--------------|----------------------|-----------|----------------|
| M=4, ef=50 | 0.85 | ~40 B | 5 μs |
| M=16, ef=200 (default) | 0.97 | ~120 B | 15 μs |
| M=32, ef=500 | 0.995 | ~240 B | 40 μs |

### 2.5 Distance Metrics

Three distance metrics are supported:

| Metric | ID | Formula | Range | Use Case |
|--------|-----|---------|-------|----------|
| Cosine | 0 | 1 − (a·b)/(\|\|a\|\|×\|\|b\|\|) | [0, 2] | Text embeddings, normalized vectors |
| Euclidean (L2) | 1 | \|\|a − b\|\|_2 | [0, ∞) | Positional data, unnormalized vectors |
| Dot Product | 2 | −a·b | (−∞, +∞) | Pre-normalized embeddings, attention scores |

**Cosine similarity** (EMBED_SIMILARITY, sub 0x08) returns the raw cosine value in [−1, 1]:
```
similarity = (Σ a_i × b_i) / (sqrt(Σ a_i²) × sqrt(Σ b_i²))
```
The result is stored as an f32 bit-pattern in R[rd]. Use ITOF (0x37) to interpret as float.

### 2.6 Memory Layout for Index Data Structures

**Index handle:** A 32-bit opaque value returned by EMBED_CREATE/EMBED_LOAD. Implementation-managed; agents treat it as a token.

**KNN query results** (written to memory at address in R[rd] after EMBED_KNN):

```
KNNResult struct (K entries, K = ef_search parameter):
Entry 0:
  Offset 0:   uint32 vector_id     ; ID of nearest vector
  Offset 4:   float32 distance     ; distance to query vector
Entry 1:
  Offset 8:   uint32 vector_id
  Offset 12:  float32 distance
...
Entry K-1:
  Offset (K-1)*8:   uint32 vector_id
  Offset (K-1)*8+4: float32 distance
Total: K × 8 bytes
```

**Saved index format** (EMBED_SAVE writes to memory):
```
IndexHeader (16 bytes):
  Offset 0:  uint32 magic          ; 0x454D4244 ("EMBD")
  Offset 4:  uint16 version        ; format version (1)
  Offset 6:  uint16 dim            ; vector dimensionality
  Offset 8:  uint32 vector_count   ; number of indexed vectors
  Offset 12: uint32 metric         ; 0=cosine, 1=L2, 2=dot

VectorData (variable):
  For each vector:
    uint32 vector_id (4 bytes)
    float32[dim] vector_data (dim × 4 bytes)

HNSWGraph (variable):
  Serialized adjacency lists, layer assignments, entry point
```

### 2.7 Byte-Level Encoding Examples

**Example 1: Create an HNSW index (128 dimensions)**

```asm
; EMBED_CREATE R0, R1, 128
; R1 = pointer to EmbedCreateParams struct (16 bytes)
0xFF 0x08 0x01 0x00 0x01 0x00 0x80
│    │    │    │    │    │    │
│    │    │    │    │    │    └─ imm16_lo = 0x80 → 128 (dim)
│    │    │    │    │    └────── imm16_hi = 0x00
│    │    │    │    └─────────── rs1 = R1 (params address)
│    │    │    └──────────────── rd = R0 (index handle)
│    │    └───────────────────── sub = 0x01 (EMBED_CREATE)
│    └────────────────────────── ext = 0x08 (EXT_EMBED)
└─────────────────────────────── escape prefix
; After: R0 = index handle (non-zero)
```

**Example 2: Insert a vector into the index**

```asm
; EMBED_INSERT R2, R0, R1
; R0 = index handle, R1 = pointer to f32[128] vector data
0xFF 0x08 0x02 0x02 0x00 0x01
│    │    │    │    │    │
│    │    │    │    │    └─ rs2 = R1 (vector data address)
│    │    │    │    └─────── rs1 = R0 (index handle)
│    │    │    └──────────── rd = R2 (assigned vector ID)
│    │    └───────────────── sub = 0x02 (EMBED_INSERT)
│    └────────────────────── ext = 0x08 (EXT_EMBED)
└─────────────────────────── escape prefix
; After: R2 = vector_id (auto-incremented, starting from 0)
```

**Example 3: KNN query**

```asm
; EMBED_KNN R3, R0, R1
; R0 = index handle, R1 = pointer to query vector (f32[128])
0xFF 0x08 0x03 0x03 0x00 0x01
; After: R3 = memory address of KNN result array
; Read K results: mem[R3+0..3] = vec_id, mem[R3+4..7] = distance, ...
```

**Example 4: Cosine similarity between two vectors**

```asm
; EMBED_SIMILARITY R4, R1, R2
; R1 = pointer to vector A, R2 = pointer to vector B
0xFF 0x08 0x08 0x04 0x01 0x02
; After: R4 = f32 bit-pattern of cosine similarity
; To use as float: ITOF R5, R4, _
```

**Example 5: Full workflow — build index, query, find best match**

```asm
; Setup: params at R1, dim=64
; Create index
0xFF 0x08 0x01 0x00 0x01 0x00 0x40  ; EMBED_CREATE R0, R1, 64
; Insert 3 vectors (pointers in R2, R3, R4)
0xFF 0x08 0x02 0x05 0x00 0x02       ; EMBED_INSERT → R5 = vec_id 0
0xFF 0x08 0x02 0x05 0x00 0x03       ; EMBED_INSERT → R5 = vec_id 1
0xFF 0x08 0x02 0x05 0x00 0x04       ; EMBED_INSERT → R5 = vec_id 2
; Query against index (query vector pointer in R6)
0xFF 0x08 0x03 0x07 0x00 0x06       ; EMBED_KNN R7, R0, R6
; R7 now points to result array: [vec_id_0, dist_0, vec_id_1, dist_1, ...]
; Read nearest neighbor ID
LOAD R8, R7, R0                      ; R8 = nearest vector ID (first uint32)
HALT
```

### 2.8 Opcode Semantics

**EMBED_CREATE (0x01):** Allocates an empty HNSW index. Reads the 16-byte `EmbedCreateParams` struct from memory at `R[rs1]`. The `imm16` parameter specifies dimensionality and must match the dimension of all subsequently inserted vectors. Returns an opaque index handle in `R[rd]`. Returns 0 on failure (invalid params, out of memory).

**EMBED_INSERT (0x02):** Reads `dim × 4` bytes of f32 vector data from memory at `R[rs2]` and inserts it into the index identified by handle `R[rs1]`. Assigns an auto-incrementing vector ID (starting from 0). Returns the assigned ID in `R[rd]`. Sets FLAG_SEC_VIOLATION if index handle is invalid or dimension mismatch.

**EMBED_KNN (0x03):** Performs a KNN search of the query vector at `mem[R[rs2]]` against index `R[rs1]`. The value of K is determined by the `ef_search` parameter set at index creation. Results are written to a freshly allocated memory region; its base address is placed in `R[rd]`. Each result entry is 8 bytes (uint32 id + float32 distance). Results are sorted by ascending distance (nearest first).

**EMBED_DELETE (0x04):** Removes the vector with ID `R[rs2]` from index `R[rs1]`. Uses HNSW lazy deletion (marks node as deleted, compaction occurs at next SAVE). Returns `R[rd] = 1` on success, `R[rd] = 0` if vector ID not found.

**EMBED_SAVE (0x05):** Serializes the index to memory starting at `R[rd]`. Maximum output size is `imm16` bytes. After completion, `R[rd]` contains the actual number of bytes written. Format includes header, vector data, and graph structure (see §2.6). Returns 0 and sets error flag if `imm16` is insufficient.

**EMBED_LOAD (0x06):** Deserializes an index from `imm16` bytes at `mem[R[rs1]]`. Performs magic number and version validation. Returns index handle in `R[rd]`. Returns 0 on corrupt or incompatible data.

**EMBED_DIM (0x07):** Two modes. Query mode (`imm8 == 0xFF`): writes dimensionality of index `R[rd]` to `R[rd]`. Set mode (`imm8 != 0xFF`): configures dimension for the next EMBED_CREATE call (stored in per-VM state).

**EMBED_SIMILARITY (0x08):** Computes cosine similarity between two vectors at `mem[R[rs1]]` and `mem[R[rs2]]`. Both vectors must have the same dimensionality (pre-configured via EMBED_DIM). Returns f32 bit-pattern in `R[rd]`. Numerically stable: uses the standard formula with zero-vector guard (returns 0.0 if either vector has zero norm).

### 2.9 Use Cases

**Knowledge federation:** Each fleet agent maintains a local embedding index of its knowledge entries. When an agent receives a query (via ASK), it embeds the query and searches its local index for the most relevant entries. Cross-agent search federates results via BCAST.

**Documentation matching:** User queries are embedded and matched against a documentation index to retrieve relevant sections. This powers the fleet's help system and onboarding assistance.

**Concept clustering:** Agents group similar concepts by running KNN on their knowledge base and identifying dense clusters. Cluster membership informs confidence scoring (C_MERGE weights).

**Semantic deduplication:** Before inserting a new knowledge entry, an agent queries its index to check if a semantically similar entry already exists. If similarity exceeds a threshold, the existing entry is updated rather than creating a duplicate.

### 2.10 Conformance Test Vectors

### EMBED-001: Create Index, Insert Vector, Query

**Setup:** dim=4, M=4, ef_construction=50, metric=cosine
**Vectors:**
- v0 = [1.0, 0.0, 0.0, 0.0]
- v1 = [0.0, 1.0, 0.0, 0.0]
- v2 = [0.9, 0.1, 0.0, 0.0] (similar to v0)
**Operations:**
1. EMBED_CREATE R0, R1, 4 → R0 = index handle (non-zero)
2. EMBED_INSERT R2, R0, addr_v0 → R2 = 0
3. EMBED_INSERT R2, R0, addr_v1 → R2 = 1
4. EMBED_INSERT R2, R0, addr_v2 → R2 = 2
5. EMBED_KNN R3, R0, addr_v0 → results at R3
6. Read first result: mem[R3] = vec_id 2 or 0 (nearest to itself), distance ≈ 0.0
**Expected:** R0 != 0; nearest neighbor of v0 is v2 (cosine distance ≈ 0.005) or v0 (distance 0.0)

### EMBED-002: Cosine Similarity — Identical Vectors

**Setup:** dim=3
**Vectors:** v_a = [0.6, 0.8, 0.0], v_b = [0.6, 0.8, 0.0]
**Operations:**
1. EMBED_DIM R0, 0x03 (set dim=3)
2. EMBED_SIMILARITY R1, addr_a, addr_b → R1 = f32 bit-pattern
3. ITOF R2, R1, _ → R2 = 1.0 (approximately)
**Expected:** R1 = float32 bits of ~1.0 (within 1e-6)

### EMBED-003: Cosine Similarity — Orthogonal Vectors

**Setup:** dim=3
**Vectors:** v_a = [1.0, 0.0, 0.0], v_b = [0.0, 1.0, 0.0]
**Operations:**
1. EMBED_SIMILARITY R1, addr_a, addr_b → R1 = f32 bits
2. ITOF R2, R1, _ → R2 = 0.0
**Expected:** R1 = float32 bits of 0.0

### EMBED-004: Save and Load Index Round-Trip

**Setup:** dim=2, insert v0=[1,0], v1=[0,1]
**Operations:**
1. EMBED_CREATE R0, R1, 2
2. EMBED_INSERT R2, R0, addr_v0 → R2 = 0
3. EMBED_INSERT R2, R0, addr_v1 → R2 = 1
4. EMBED_SAVE R3, R0, 4096 → R3 = bytes written (non-zero)
5. EMBED_LOAD R4, R3_original, R3 → R4 = new index handle (non-zero)
6. EMBED_KNN R5, R4, addr_v0 → nearest = vec_id 0, distance ≈ 0.0
**Expected:** R4 != 0; round-tripped index returns same KNN results as original

### EMBED-005: Delete Vector and Verify Absence

**Setup:** dim=2, insert v0=[1,0], v1=[0,1], v2=[1,1]
**Operations:**
1. Create index, insert v0 (id=0), v1 (id=1), v2 (id=2)
2. EMBED_KNN R3, R0, addr_v0 → 3 results (v0, v2, v1 by cosine)
3. EMBED_DELETE R5, R0, 2 → R5 = 1 (success, removed v2)
4. EMBED_KNN R3, R0, addr_v0 → now only 2 results (v0, v1)
5. EMBED_DELETE R5, R0, 99 → R5 = 0 (not found)
**Expected:** After deletion, KNN returns at most 2 results; second DELETE returns 0

### 2.11 Implementation Notes

- **Max indices per VM:** 16 (configurable via SYS call 0x50)
- **Max vectors per index:** 4,194,304 (2^22, limited by 22-bit vector IDs)
- **Max dimensionality:** 8192 (limited by imm16 parameter range, stored as uint16)
- **Index memory budget:** ~120 bytes/vector for default M=16 (graph edges + metadata)
- **Thread safety:** Indices are per-VM; no cross-VM sharing. FORK creates independent copies.
- **Recommended HNSW library reference:** hnswlib (MIT license), used as algorithmic reference
- **Integration with VER_EXT:** `0xFF 0xF0 0x08` returns R0=1 (available), R1=version (1)

---

## 3. Extension II — Graph Traversal (GRAPH-001)

### 3.1 Motivation

Knowledge graphs, trust networks, and capability maps are central to the FLUX fleet. Fleet agents navigate these structures constantly:

- **A2A trust networks**: Agents decide whether to delegate tasks based on trust edges between agents
- **Knowledge federation**: Concept relationships form a graph; traversal enables multi-hop inference
- **Capability maps**: Skills and specializations form a bipartite graph with agents

Software graph traversal on large graphs (100K+ nodes) is slow — a single BFS can take milliseconds, and agents often need multi-hop queries with filtering. Making graph operations first-class ISA opcodes eliminates interpreter overhead and enables firmware-level optimization.

### 3.2 Sub-Opcode Table

**Extension:** EXT_GRAPH (ID 0x09), accessed via `0xFF 0x09 sub_opcode operands...`

| Sub | Mnemonic | Fmt | Operands | Description |
|-----|----------|-----|----------|-------------|
| 0x01 | GRAPH_CREATE | H_G | rd, rs1, imm16 | Create directed graph; params at mem[rs1]; handle → R[rd]; imm16 = max_nodes |
| 0x02 | GRAPH_ADD_NODE | H_E | rd, rs1, rs2 | Add node with properties at mem[R[rs2]]; graph R[rs1]; node_id → R[rd] |
| 0x03 | GRAPH_ADD_EDGE | H_E | rd, rs1, rs2 | Add edge; params at mem[R[rd]]; graph R[rs1]; edge_id → R[rs2] |
| 0x04 | GRAPH_STEP | H_E | rd, rs1, rs2 | Traverse one edge from cursor R[rs1] via edge label R[rs2]; result → R[rd] |
| 0x05 | GRAPH_BFS | H_E | rd, rs1, rs2 | BFS from node R[rs1]; max depth in R[rs2]; result addr → R[rd] |
| 0x06 | GRAPH_DFS | H_E | rd, rs1, rs2 | DFS from node R[rs1]; max depth in R[rs2]; result addr → R[rd] |
| 0x07 | GRAPH_SHORTEST | H_E | rd, rs1, rs2 | Shortest path (Dijkstra) from node R[rs1] to R[rs2]; result addr → R[rd] |
| 0x08 | GRAPH_NEIGHBORS | H_E | rd, rs1, rs2 | Get all neighbors of node R[rs1]; direction (0=in,1=out,2=both) in R[rs2]; addr → R[rd] |
| 0x09 | GRAPH_PAGERANK | H_E | rd, rs1, rs2 | Compute PageRank; graph R[rs1]; iterations R[rs2]; scores addr → R[rd] |
| 0x0A | GRAPH_DEGREE | H_E | rd, rs1, rs2 | Get degree of node R[rs1]; direction in R[rs2]; degree → R[rd] |

### 3.3 Node and Edge Storage

**Node structure** (stored in memory when using GRAPH_ADD_NODE, 24 bytes minimum):

```
GraphNode struct:
Offset 0:  uint32 properties_len   ; byte length of properties blob
Offset 4:  uint32 label_id         ; integer label (type/category)
Offset 8:  float32 weight          ; node weight (for PageRank initial value)
Offset 12: properties_data[...]    ; variable-length properties (JSON or opaque bytes)
```

**Edge structure** (params at mem[R[rd]] for GRAPH_ADD_EDGE, 20 bytes):

```
GraphEdge struct:
Offset 0:  uint32 source_id        ; source node ID
Offset 4:  uint32 target_id        ; target node ID
Offset 8:  uint32 label            ; edge label (edge type/category)
Offset 12: float32 weight          ; edge weight (for Dijkstra)
Offset 16: uint32 flags            ; 0x01 = bidirectional
```

**Node and edge IDs:** Auto-incrementing uint32 values starting from 0. Separate ID spaces for nodes and edges within a graph.

### 3.4 Adjacency List Representation

Each graph uses a **compressed adjacency list** stored in implementation-managed memory (not directly in FLUX byte-addressable memory):

```
Graph Internal Layout:
┌──────────────────────────────────────────────────────────┐
│ Node Table                                                │
│   [node_id:4] [label:4] [weight:4] [props_ptr:4] [in_ptr:4] [out_ptr:4] │
│   × max_nodes entries                                     │
├──────────────────────────────────────────────────────────┤
│ Edge List (CSR-style)                                     │
│   For each node: adjacency[node_id] → [target_id, edge_label, weight, ...] │
│   Out-edges stored in CSR format: offsets[] + targets[]   │
│   In-edges stored in separate CSR for reverse traversal   │
├──────────────────────────────────────────────────────────┤
│ Properties Blob Store                                     │
│   Variable-length node/edge properties                     │
├──────────────────────────────────────────────────────────┤
│ Traversal Cursor State                                    │
│   Current node, visited set, BFS queue / DFS stack        │
└──────────────────────────────────────────────────────────┘
```

**Graph handle:** A 32-bit opaque token identifying a specific graph instance. Agents never dereference it; they pass it as an operand to graph opcodes.

### 3.5 Traversal State Machine

GRAPH_STEP uses a **cursor-based** traversal model. The cursor is per-VM, per-graph state:

```
Cursor State Machine:
  IDLE ───── GRAPH_STEP(node_id) ────→ AT_NODE(node_id)
  AT_NODE ── GRAPH_STEP(label) ──────→ AT_NODE(next_node) [follow edge]
  AT_NODE ── GRAPH_STEP(0xFFFFFFFF) ─→ AT_NODE(neighbor)  [any edge]
  AT_NODE ── no valid edge ──────────→ IDLE               [dead end]
  IDLE ──── GRAPH_BFS/DFS ───────────→ results written     [bulk traversal]
```

**GRAPH_BFS result format** (written to memory at R[rd]):

```
BFSResult struct:
Offset 0:  uint32 count            ; number of nodes reached
Offset 4:  uint32 node_ids[count]  ; array of reached node IDs
Offset 4+count*4: uint32 depths[count]; BFS depth at which each was reached
Total: 4 + count × 8 bytes
```

**GRAPH_DFS result format** (written to memory at R[rd]):

```
DFSResult struct:
Offset 0:  uint32 count            ; number of nodes visited
Offset 4:  uint32 node_ids[count]  ; DFS visitation order
Total: 4 + count × 4 bytes
```

**GRAPH_SHORTEST result format** (Dijkstra, written to memory at R[rd]):

```
ShortestPathResult struct:
Offset 0:  float32 total_distance  ; sum of edge weights (f32, FLT_MAX if unreachable)
Offset 4:  uint32 path_length      ; number of nodes in path (0 if unreachable)
Offset 8:  uint32 path[path_length]; ordered node IDs from source to target
Total: 8 + path_length × 4 bytes
```

**GRAPH_PAGERANK result format** (written to memory at R[rd]):

```
PageRankResult struct:
Offset 0:  uint32 node_count       ; number of nodes scored
Offset 4:  float32 scores[node_count]; PageRank score for each node (ordered by node_id)
Total: 4 + node_count × 4 bytes
```

**GRAPH_NEIGHBORS result format** (written to memory at R[rd]):

```
NeighborsResult struct:
Offset 0:  uint32 count            ; number of neighbors
Offset 4:  uint32 node_ids[count]  ; neighbor node IDs
Offset 4+count*4: float32 edge_weights[count]; weight of connecting edge
Total: 4 + count × 8 bytes
```

### 3.6 Byte-Level Encoding Examples

**Example 1: Create a graph**

```asm
; GRAPH_CREATE R0, R1, 1024
; R1 = pointer to optional init params (can be NULL/0 for defaults)
; 1024 = max nodes
0xFF 0x09 0x01 0x00 0x01 0x04 0x00
│    │    │    │    │    │    │
│    │    │    │    │    │    └─ imm16_lo = 0x00
│    │    │    │    │    └────── imm16_hi = 0x04 → 1024
│    │    │    │    └─────────── rs1 = R1 (params, may be 0)
│    │    │    └──────────────── rd = R0 (graph handle)
│    │    └───────────────────── sub = 0x01 (GRAPH_CREATE)
│    └────────────────────────── ext = 0x09 (EXT_GRAPH)
└─────────────────────────────── escape prefix
; After: R0 = graph handle (non-zero)
```

**Example 2: Add nodes and edges**

```asm
; GRAPH_ADD_NODE R2, R0, R3  (node props at R3)
0xFF 0x09 0x02 0x02 0x00 0x03
; → R2 = node_id 0

; GRAPH_ADD_NODE R2, R0, R3  (another node)
0xFF 0x09 0x02 0x02 0x00 0x03
; → R2 = node_id 1

; GRAPH_ADD_EDGE: edge params at R4 (source=0, target=1, label=1, weight=1.0, flags=0)
0xFF 0x09 0x03 0x05 0x00 0x04
; → R5 = edge_id 0
```

**Example 3: BFS from a node**

```asm
; GRAPH_BFS R6, R0, R7
; R0 = graph handle, R7 = max BFS depth (e.g., 3)
0xFF 0x09 0x05 0x06 0x00 0x07
; After: R6 = address of BFSResult struct
; Read count: LOAD R8, R6, R0 → R8 = number of reached nodes
```

**Example 4: A2A trust graph — find trusted neighbors**

```asm
; Build trust graph: nodes = agents, edges = trust relationships
; Agent A trusts B (weight=0.9), B trusts C (weight=0.8)
; Find 2-hop trusted agents from A via BFS
0xFF 0x09 0x05 0x06 0x00 0x01  ; GRAPH_BFS R6, R0, 2 (depth=2)
; R6 points to [count=3, nodes: A, B, C, depths: 0, 1, 2]
; A can delegate to B (direct trust), potentially to C (transitive)
```

**Example 5: PageRank on capability map**

```asm
; Compute PageRank with 20 iterations
MOVI R8, 20
0xFF 0x09 0x09 0x09 0x00 0x08  ; GRAPH_PAGERANK R9, R0, R8
; R9 = address of PageRankResult
; Read node 0's score: LOAD R10, R9_offset, R0 → score in f32 bits
```

### 3.7 Opcode Semantics

**GRAPH_CREATE (0x01):** Allocates an empty directed graph. `imm16` specifies maximum node count. `R[rs1]` may point to optional initialization parameters or be 0 for defaults. Returns graph handle in `R[rd]`.

**GRAPH_ADD_NODE (0x02):** Reads node structure from memory at `R[rs2]` and adds it to graph `R[rs1]`. Returns assigned node ID in `R[rd]`. If graph is full (reached max_nodes), returns 0 with error flag.

**GRAPH_ADD_EDGE (0x03):** Reads edge structure from memory at `R[rd]` (source_id, target_id, label, weight, flags). Adds edge to graph `R[rs1]`. Returns edge ID in `R[rs2]`. If source or target node doesn't exist, returns 0 with error flag. Bidirectional flag (0x01) adds both forward and reverse edges.

**GRAPH_STEP (0x04):** Cursor-based single-edge traversal. From the current cursor position (node), follows an edge matching label `R[rs2]` (0xFFFFFFFF = any label). Advances cursor to the destination node. Writes destination node ID to `R[rd]`. Returns 0 if no valid edge (cursor resets to IDLE).

**GRAPH_BFS (0x05):** Breadth-first search from node `R[rs1]` up to depth `R[rs2]`. Returns all reachable node IDs and their depths. Result struct written to memory (see §3.5).

**GRAPH_DFS (0x06):** Depth-first search from node `R[rs1]` up to depth `R[rs2]`. Returns visitation order. Result struct written to memory.

**GRAPH_SHORTEST (0x07):** Dijkstra's shortest path from node `R[rs1]` to node `R[rs2]`. Uses edge weights. Returns total distance and ordered path. If no path exists, total_distance = FLT_MAX and path_length = 0.

**GRAPH_NEIGHBORS (0x08):** Returns all neighbors of node `R[rs1]`. Direction: 0=in-edges, 1=out-edges, 2=both. Result includes neighbor IDs and edge weights.

**GRAPH_PAGERANK (0x09):** Computes PageRank scores for all nodes. `R[rs2]` = number of iterations (20–100 recommended). Damping factor = 0.85 (hardcoded). Returns scores for all nodes ordered by node ID.

**GRAPH_DEGREE (0x0A):** Returns in-degree, out-degree, or total degree of node `R[rs1]`. Direction in `R[rs2]`: 0=in, 1=out, 2=total. Result is a uint32 in `R[rd]`.

### 3.8 Use Cases

**A2A trust networks:** Each agent maintains a trust graph of fleet peers. Before delegating a task, an agent checks trust scores via BFS from itself to the candidate, weighted by trust edge values. GRAPH_SHOREST finds the most trusted delegation path.

**Knowledge federation:** Concepts are nodes, relationships (hypernymy, synonymy, related-to) are edges. GRAPH_STEP enables multi-hop inference ("if A is-a B and B is-a C, then A is-a C").

**Capability maps:** A bipartite graph connects agents to their skills. GRAPH_BFS from a skill node finds all capable agents. GRAPH_PAGERANK identifies the most well-connected (versatile) agents.

**Dependency resolution:** Task dependencies form a DAG. GRAPH_DFS detects cycles (if a node is visited twice). GRAPH_SHORTEST finds the critical path.

### 3.9 Conformance Test Vectors

### GRAPH-001: Create Graph, Add Nodes, Add Edges, Traverse

**Setup:** 3 nodes, 2 edges: 0→1 (weight=1.0), 1→2 (weight=2.0)
**Operations:**
1. GRAPH_CREATE R0, R0_zero, 16 → R0 = graph handle
2. GRAPH_ADD_NODE R1, R0, props → R1 = 0
3. GRAPH_ADD_NODE R1, R0, props → R1 = 1
4. GRAPH_ADD_NODE R1, R0, props → R1 = 2
5. GRAPH_ADD_EDGE (edge: src=0, tgt=1, w=1.0) → success
6. GRAPH_ADD_EDGE (edge: src=1, tgt=2, w=2.0) → success
7. GRAPH_DEGREE R5, R1=0, R6=1 → R5 = 0 (out-degree) [Wait: out-degree of node 0 is 1]
**Expected:** Out-degree of node 0 = 1; out-degree of node 1 = 1; in-degree of node 2 = 1

### GRAPH-002: BFS Depth-Limited Search

**Setup:** Chain graph: 0→1→2→3→4 (5 nodes, 4 edges, weight=1.0 each)
**Operations:**
1. Create graph, add 5 nodes, add 4 edges
2. GRAPH_BFS R5, R0, R6 (from node 0, max_depth=2)
3. Read result: count = 3 (nodes 0, 1, 2 at depths 0, 1, 2)
**Expected:** count = 3; nodes = [0, 1, 2]; depths = [0, 1, 2]

### GRAPH-003: Shortest Path — Dijkstra with Weighted Edges

**Setup:** Triangle graph: 0→1 (w=1.0), 0→2 (w=5.0), 1→2 (w=1.0)
**Operations:**
1. Create graph, add 3 nodes, add 3 edges
2. GRAPH_SHORTEST R5, R0=0, R1=2
3. Read result: total_distance ≈ 2.0, path_length = 3, path = [0, 1, 2]
**Expected:** Shortest path 0→1→2 with distance 2.0 (not 0→2 with distance 5.0)

### GRAPH-004: PageRank Convergence

**Setup:** 3-node graph: 0→1, 0→2, 1→2, 2→0 (fully connected cycle)
**Operations:**
1. Create graph, add 3 nodes, add 4 edges (all weight=1.0)
2. GRAPH_PAGERANK R5, R0, 50 (50 iterations)
3. Read scores for all 3 nodes — should be approximately equal (~0.333)
**Expected:** All three PageRank scores within 0.01 of each other (symmetric graph → equal scores)

### GRAPH-005: Get Neighbors (Bidirectional Edge)

**Setup:** 3 nodes, 1 bidirectional edge: 0↔1 (flags=0x01), 1→2
**Operations:**
1. Create graph, add 3 nodes
2. Add bidirectional edge 0↔1
3. Add directed edge 1→2
4. GRAPH_NEIGHBORS R5, R0=0, R6=1 (out-edges) → count=1, neighbor=[1]
5. GRAPH_NEIGHBORS R5, R0=1, R6=0 (in-edges) → count=1, neighbor=[0]
6. GRAPH_NEIGHBORS R5, R0=1, R6=2 (both) → count=2, neighbors=[0, 2]
**Expected:** Node 0 has 1 out-neighbor (1); node 1 has 1 in-neighbor (0); node 1 has 2 total neighbors (0 and 2)

### 3.10 Implementation Notes

- **Max graphs per VM:** 8 (configurable via SYS call 0x51)
- **Max nodes per graph:** 65,536 (limited by uint16 in imm16 parameter)
- **Max edges per graph:** 4,194,304 (2^22)
- **Graph memory budget:** ~48 bytes/node (node table + adjacency offsets) + ~12 bytes/edge
- **BFS/DFS stack depth:** Max 65,536 nodes (no recursion — uses iterative implementation)
- **Dijkstra implementation:** Min-heap priority queue, O((V+E) log V)
- **PageRank:** Iterative power method, damping=0.85, converges in ~20 iterations for most graphs
- **Cursor state:** Per-VM, per-graph. SWITCH context swap preserves cursor state.
- **Integration with VER_EXT:** `0xFF 0xF0 0x09` returns R0=1 (available), R1=version (1)

---

## 4. Extension III — Probabilistic Sampling (PROB-001)

### 4.1 Motivation

Stochastic agents need controlled randomness for three critical capabilities:

1. **Exploration vs. exploitation:** Agents must balance using known-good strategies with trying new approaches. Bernoulli sampling (ε-greedy) and Gumbel-softmax enable this tradeoff.
2. **LLM-style token selection:** Temperature-based softmax, top-K filtering, and nucleus (top-p) sampling are the standard methods for sampling from logit distributions — the same algorithms used by GPT, Claude, and LLaMA.
3. **Monte Carlo methods:** Agents performing uncertainty estimation, probabilistic reasoning, or simulation need high-quality PRNG with guaranteed reproducibility.

Using Python's `random` module for these operations is slow (~1 μs per sample) and non-deterministic across runtimes. ISA-level sampling provides sub-microsecond latency with deterministic, seedable output.

### 4.2 Sub-Opcode Table

**Extension:** EXT_PROB (ID 0x0A), accessed via `0xFF 0x0A sub_opcode operands...`

| Sub | Mnemonic | Fmt | Operands | Description |
|-----|----------|-----|----------|-------------|
| 0x01 | RND_SEED | H_E | rd, rs1, rs2 | Set PRNG seed; low 32 bits from R[rs1], high 32 from R[rs2]; R[rd]=1 |
| 0x02 | RND_UNIFORM | H_E | rd, rs1, rs2 | Sample uniform [R[rs1], R[rs2]) as f64; bits → R[rd] |
| 0x03 | RND_NORMAL | H_E | rd, rs1, rs2 | Sample Gaussian(mean=R[rs1] f64, stddev=R[rs2] f64); bits → R[rd] |
| 0x04 | RND_GUMBEL | H_E | rd, rs1, rs2 | Sample Gumbel(μ=R[rs1], β=R[rs2]); bits → R[rd] |
| 0x05 | SAMPLE_SOFTMAX | H_E | rd, rs1, rs2 | Weighted sample from logits at mem[R[rs1]], count=R[rs2]; index → R[rd] |
| 0x06 | SAMPLE_TOPK | H_E | rd, rs1, rs2 | Top-K sample: logits at mem[R[rs1]], K=R[rs2]; index → R[rd] |
| 0x07 | SAMPLE_TOPP | H_E | rd, rs1, rs2 | Nucleus sample: logits at mem[R[rs1]], p=R[rs2] as f32; index → R[rd] |
| 0x08 | DIST_BERNOULLI | H_E | rd, rs1, rs2 | Sample Bernoulli(p=R[rs1] f64); R[rd]=0 or 1 |
| 0x09 | DIST_BINOMIAL | H_E | rd, rs1, rs2 | Sample Binomial(n=R[rs1], p=R[rs2] f64); count → R[rd] |

**Temperature parameter for SAMPLE_SOFTMAX:** Stored in per-VM state, set via MOVI to a reserved address or a future SAMPLE_SET_TEMP opcode. Default temperature = 1.0.

**Per-VM state layout for EXT_PROB:**
```
PRNG State (48 bytes):
  uint64 state[4]     ; xoshiro256** state
  uint64 seed         ; last seed value (for VER_EXT query)
  float64 temperature ; softmax temperature (default 1.0)
  uint32 sample_count ; total samples drawn (monotonic counter)
```

### 4.3 PRNG Design — xoshiro256**

EXT_PROB uses **xoshiro256\*\*** — a fast, high-quality 64-bit PRNG that passes all statistical test batteries (TestU01 Big Crush, PractRand). Key properties:

| Property | Value |
|----------|-------|
| State size | 256 bits (4 × uint64) |
| Period | 2^256 − 1 |
| Speed | ~1.5 ns/sample (scalar), ~0.3 ns/sample (SIMD) |
| Quality | Passes TestU01 Big Crush, PractRand up to 32 TB |
| Seedable | Yes — any 64-bit value (SplitMix64 seed expansion) |
| Jump-ahead | Supported (for parallel streams) |
| Determinism | Bit-identical output across all platforms given same seed |

**Default seed:** 0xFLUXF1EED = 0x464C555846314545 (ASCII "FLUXF1EE"). Agents can override with RND_SEED.

**Seeding procedure (SplitMix64):**
```
function seed(state, seed_value):
    // Expand 64-bit seed to four 64-bit state words
    s = seed_value
    for i in 0..3:
        s = (s + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        state[i] = z ^ (z >> 31)
```

**xoshiro256\*\* generation:**
```
function next(state):
    result = rotl(state[1] * 5, 7) * 9
    t = state[1] << 17
    state[2] ^= state[0]
    state[3] ^= state[1]
    state[1] ^= state[2]
    state[0] ^= state[3]
    state[2] ^= t
    state[3] = rotl(state[3], 45)
    return result
```

### 4.4 Softmax with Temperature

SAMPLE_SOFTMAX converts a logit vector to a probability distribution and samples an index:

```
Step 1: Apply temperature
  x_i' = x_i / T    (T = temperature parameter)

Step 2: Numerical stability — log-sum-exp trick
  m = max(x_i')     (find maximum logit)
  x_i'' = x_i' - m  (subtract max for stability)

Step 3: Compute softmax probabilities
  p_i = exp(x_i'') / Σ_j exp(x_j'')

Step 4: Sample from categorical distribution
  Draw u ~ Uniform(0, 1)
  Accumulate p_i until Σ > u → return index i
```

**Temperature effects:**

| Temperature | Behavior | Use Case |
|------------|----------|----------|
| T → 0 | Argmax (deterministic) | Greedy decoding, highest-confidence action |
| T = 0.3 | Peaked distribution | Focused reasoning, conservative decisions |
| T = 1.0 | Original distribution | Default behavior |
| T = 2.0 | Flattened distribution | Creative exploration, brainstorming |
| T → ∞ | Uniform random | Pure exploration |

**Numerical stability:** The log-sum-exp trick prevents overflow/underflow:
- Subtract max before exponentiation: `exp(x_i - max_x)`
- This ensures all exponents are ≤ 0, so `exp()` outputs are in (0, 1]
- No overflow possible; underflow only for extreme negative logits (correct behavior)

### 4.5 Top-K and Nucleus (Top-P) Sampling

**Top-K sampling (SAMPLE_TOPK):**
1. Sort logits in descending order
2. Keep only the top K logits (zero out all others)
3. Apply softmax to the remaining K logits
4. Sample from the K-element distribution
5. Return the original index of the selected element

```
Example: logits = [0.5, 2.0, 0.1, 1.5, 0.3], K=2
  Top-2: [2.0 (idx=1), 1.5 (idx=3)]
  Softmax: p = [exp(2.0), exp(1.5)] / (exp(2.0) + exp(1.5))
         = [0.731, 0.269]
  Sample: return idx=1 with prob 0.731, idx=3 with prob 0.269
```

**Nucleus (top-p) sampling (SAMPLE_TOPP):**
1. Sort logits in descending order with their cumulative softmax probabilities
2. Find the smallest set of tokens whose cumulative probability ≥ p
3. Zero out all tokens outside this nucleus
4. Renormalize and sample from the nucleus

```
Example: logits = [0.1, 2.0, 0.05, 1.5, 0.08], p=0.9
  Sorted probabilities: [0.539, 0.298, 0.082, 0.047, 0.034]
  Cumulative:           [0.539, 0.837, 0.919, 0.966, 1.000]
  Nucleus (p=0.9):      first 3 tokens (cumulative = 0.919 ≥ 0.9)
  Renormalize:          [0.587, 0.324, 0.089]
  Sample from nucleus
```

### 4.6 Gumbel-Softmax

RND_GUMBEL generates a Gumbel(μ, β) sample, which is used in the Gumbel-softmax trick for differentiable discrete sampling:

```
Gumbel(0, 1) sampling:
  u ~ Uniform(0, 1)
  g = -ln(-ln(u))

Gumbel(μ, β):
  g = μ + β × Gumbel(0, 1)

Gumbel-softmax (argmax approximation):
  y_i = softmax((x_i + g_i) / τ)
  where τ is a non-negative temperature parameter
```

The Gumbel-softmax is essential for agents that need to make discrete choices while maintaining differentiability through gradient estimation.

### 4.7 Numerical Stability

All probabilistic operations include numerical safeguards:

| Operation | Risk | Mitigation |
|-----------|------|-----------|
| exp() in softmax | Overflow for large logits | Subtract max (log-sum-exp trick) |
| exp() in softmax | Underflow for small logits | Use log-space when possible |
| -ln(-ln(u)) in Gumbel | ln(0) = -inf | Clamp u to [ε, 1−ε], ε=1e-10 |
| 1/p in Bernoulli | Division by zero | Clamp p to [1e-10, 1−1e-10] |
| Binomial CDF | Numerical precision | Use exact integer arithmetic for small n |
| Temperature = 0 | Division by zero | Clamp T to [1e-8, 100.0] |

### 4.8 Byte-Level Encoding Examples

**Example 1: Seed the PRNG**

```asm
; RND_SEED R0, R1, R2
; R1 = low 32 bits of seed, R2 = high 32 bits of seed
MOVI R1, 42
MOVI R2, 0
0xFF 0x0A 0x01 0x00 0x01 0x02
│    │    │    │    │    │
│    │    │    │    │    └─ rs2 = R2 (seed high bits)
│    │    │    │    └─────── rs1 = R1 (seed low bits = 42)
│    │    │    └──────────── rd = R0 (result: 1 = success)
│    │    └───────────────── sub = 0x01 (RND_SEED)
│    └────────────────────── ext = 0x0A (EXT_PROB)
└─────────────────────────── escape prefix
; After: R0 = 1, PRNG state initialized with seed 42
```

**Example 2: Sample from uniform distribution**

```asm
; RND_UNIFORM R0, R1, R2
; R1 = f64 bits of lower bound (0.0), R2 = f64 bits of upper bound (1.0)
0xFF 0x0A 0x02 0x00 0x01 0x02
; After: R0 = f64 bit-pattern of uniform sample in [0.0, 1.0)
```

**Example 3: Sample from logits via softmax**

```asm
; SAMPLE_SOFTMAX R3, R0, R1
; R0 = pointer to f64[5] logit array, R1 = 5 (count)
0xFF 0x0A 0x05 0x03 0x00 0x01
│    │    │    │    │    │
│    │    │    │    │    └─ rs2 = R1 (logit count = 5)
│    │    │    │    └─────── rs1 = R0 (logits address)
│    │    │    └──────────── rd = R3 (sampled index)
│    │    └───────────────── sub = 0x05 (SAMPLE_SOFTMAX)
│    └────────────────────── ext = 0x0A (EXT_PROB)
└─────────────────────────── escape prefix
; After: R3 = index 0..4, sampled proportional to softmax(logits)
```

**Example 4: Top-K sampling (LLM-style)**

```asm
; SAMPLE_TOPK R3, R0, R1
; R0 = pointer to f64[32000] vocabulary logits, R1 = K=50
MOVI R1, 50
0xFF 0x0A 0x06 0x03 0x00 0x01
; After: R3 = vocab index from top-50 logits
```

**Example 5: ε-greedy exploration using Bernoulli**

```asm
; Sample Bernoulli(ε=0.1) — 10% chance of exploration
MOVI R1, 0x3FB999999999999A  ; f64 bits of 0.1
MOVI R2, 0                   ; unused
0xFF 0x0A 0x08 0x04 0x01 0x02  ; DIST_BERNOULLI R4, R1, R2
; After: R4 = 1 (explore, 10% prob) or R4 = 0 (exploit, 90% prob)
```

### 4.9 Opcode Semantics

**RND_SEED (0x01):** Combines R[rs1] (low 32 bits) and R[rs2] (high 32 bits) into a 64-bit seed. Initializes xoshiro256** state using SplitMix64 expansion. Returns 1 in `R[rd]` on success. Subsequent samples are fully deterministic from this seed.

**RND_UNIFORM (0x02):** Generates a uniform random float in [low, high) where low and high are f64 values whose bit-patterns are in `R[rs1]` and `R[rs2]`. Uses xoshiro256** to generate a 53-bit random mantissa, then scales to range. Result as f64 bit-pattern in `R[rd]`.

**RND_NORMAL (0x03):** Generates a Gaussian sample using the Box-Muller transform. Mean (μ) and standard deviation (σ) are f64 bit-patterns in `R[rs1]` and `R[rs2]`. Uses two PRNG calls internally. Result as f64 bit-pattern in `R[rd]`.

**RND_GUMBEL (0x04):** Generates a Gumbel(μ, β) sample. Location (μ) and scale (β) are f64 bit-patterns in `R[rs1]` and `R[rs2]`. Uses the inverse CDF method: g = μ − β × ln(−ln(u)). Clamps u to [1e-10, 1−1e-10] to avoid ln(0). Result as f64 bit-pattern in `R[rd]`.

**SAMPLE_SOFTMAX (0x05):** Reads `R[rs2]` f64 logits from memory at `R[rs1]`. Applies temperature (from per-VM state, default 1.0). Computes softmax with log-sum-exp stability. Draws a uniform sample and maps to categorical index. Returns sampled index in `R[rd]`.

**SAMPLE_TOPK (0x06):** Reads logits from memory at `R[rs1]`. Filters to top K (K = `R[rs2]`). Applies softmax to filtered logits. Samples and returns original index in `R[rd]`. K must be ≥ 1 and ≤ logit count.

**SAMPLE_TOPP (0x07):** Reads logits from memory at `R[rs1]`. Nucleus threshold p is f32 bit-pattern in `R[rs2]` (default interpretation: p in [0.0, 1.0]). Computes softmax, sorts, finds smallest nucleus with cumulative probability ≥ p, renormalizes, and samples. Returns original index in `R[rd]`.

**DIST_BERNOULLI (0x08):** Sample Bernoulli(p). Probability p is f64 bit-pattern in `R[rs1]`. Returns `R[rd] = 1` with probability p, `R[rd] = 0` with probability (1−p). Clamps p to [1e-10, 1−1e-10].

**DIST_BINOMIAL (0x09):** Sample Binomial(n, p). Number of trials n is integer value in `R[rs1]`. Probability p is f64 bit-pattern in `R[rs2]`. For n ≤ 64, uses inverse transform sampling with precomputed CDF. For n > 64, uses BTPE algorithm. Returns count in `R[rd]`.

### 4.10 Use Cases

**LLM token selection:** Agents running language model inference use SAMPLE_TOPK or SAMPLE_TOPP to select tokens from the vocabulary distribution. This is identical to how GPT/Claude generate text, enabling fleet agents to produce natural language with controlled randomness.

**ε-greedy exploration:** Agents balancing exploration and exploitation use DIST_BERNOULLI with ε probability to decide between random action (explore) and best-known action (exploit). Temperature-based softmax provides a softer alternative.

**Monte Carlo estimation:** Agents estimating uncertainty in predictions use RND_UNIFORM and RND_NORMAL to generate sample paths. The deterministic PRNG ensures reproducible confidence intervals.

**Gumbel-softmax for decision-making:** Agents making discrete choices in differentiable pipelines use RND_GUMBEL + SAMPLE_SOFTMAX to implement the Gumbel-softmax trick. This enables gradient-based optimization of discrete decisions.

**Reproducible experiments:** RND_SEED allows agents to reproduce stochastic experiments by resetting the PRNG to a known state. This is critical for debugging and for fleet-wide reproducibility standards.

### 4.11 Conformance Test Vectors

### PROB-001: Seed and Reproducibility

**Setup:** Seed = 42
**Operations:**
1. RND_SEED R0, 42, 0 → R0 = 1
2. RND_UNIFORM R1, 0.0_bits, 1.0_bits → R1 = u1 (first sample)
3. RND_SEED R0, 42, 0 → R0 = 1 (re-seed)
4. RND_UNIFORM R2, 0.0_bits, 1.0_bits → R2 = u2
**Expected:** R1 == R2 (bit-identical — re-seeding produces same sequence)

### PROB-002: Softmax Deterministic — Temperature 0

**Setup:** Seed = 123, logits = [1.0, 5.0, 3.0, 0.5]
**Operations:**
1. RND_SEED R0, 123, 0
2. Set temperature to 0 (approximate as 1e-8)
3. SAMPLE_SOFTMAX R1, logits_addr, 4 → R1 = sampled index
4. Repeat 100 times; count occurrences of each index
**Expected:** >99 of 100 samples return index 1 (logit=5.0 is argmax)

### PROB-003: Bernoulli — Known Probability Count

**Setup:** Seed = 999, p = 0.5
**Operations:**
1. RND_SEED R0, 999, 0
2. Loop 1000 times: DIST_BERNOULLI R1, 0.5_bits, R2; accumulate sum
3. Expected sum ≈ 500 (within 3σ ≈ ±47)
**Expected:** Sum in range [453, 547] (99.7% confidence interval for Binomial(1000, 0.5))

### PROB-004: Normal Distribution — Mean and Variance Check

**Setup:** Seed = 777, mean=0.0, stddev=1.0
**Operations:**
1. RND_SEED R0, 777, 0
2. Loop 10000 times: RND_NORMAL → compute running mean and variance
3. Expected: sample_mean ≈ 0.0 (within ±0.05), sample_var ≈ 1.0 (within ±0.1)
**Expected:** |sample_mean| < 0.05 AND 0.9 < sample_var < 1.1

### PROB-005: Top-K Returns Only Top-K Indices

**Setup:** Seed = 555, logits = [10.0, 0.0, 0.0, 0.0, 0.0, 8.0], K=2
**Operations:**
1. RND_SEED R0, 555, 0
2. Loop 100 times: SAMPLE_TOPK R1, logits_addr, 2; record index
3. Verify all sampled indices are in {0, 4} (the two highest logits)
**Expected:** Every sample is index 0 or index 4; no sample is index 1, 2, 3, or 5

### 4.12 Implementation Notes

- **PRNG state isolation:** Each VM instance has independent PRNG state. FORK copies the state (child gets same sequence as parent from fork point).
- **Temperature storage:** Stored as f64 in per-VM extension state. Set via a dedicated SAMPLE_SET_TEMP sub-opcode (reserved for future 0x0B) or via SYS call 0x52.
- **Logit array format:** f64 (8 bytes per element), little-endian. Maximum array length: 65,536 elements.
- **Top-K sorting:** Uses partial sort (nth_element + sort of top K) — O(n + K log K) instead of full sort O(n log n).
- **Performance targets:**
  - RND_UNIFORM: < 2 ns per sample
  - RND_NORMAL: < 5 ns per sample (Box-Muller)
  - SAMPLE_SOFTMAX (100 logits): < 500 ns
  - SAMPLE_TOPK (50K logits, K=50): < 10 μs
  - SAMPLE_TOPP (50K logits, p=0.9): < 15 μs
- **Integration with VER_EXT:** `0xFF 0xF0 0x0A` returns R0=1 (available), R1=version (1), R2=current seed
- **Cross-platform determinism:** xoshiro256** is bit-identical across all platforms (no FPU rounding variance since all operations are integer-only)

---

## 5. Cross-Extension Synergies

The three extensions in this specification are designed to work together:

| Synergy | Description | Example |
|---------|-------------|---------|
| EMBED + GRAPH | Embedding-indexed graph nodes | Node properties include embedding vectors; GRAPH_STEP followed by EMBED_SIMILARITY for semantic graph traversal |
| EMBED + PROB | Stochastic nearest-neighbor sampling | EMBED_KNN returns top-K, then SAMPLE_TOPK selects one probabilistically |
| GRAPH + PROB | Random walk on graph | RND_UNIFORM selects random neighbor at each GRAPH_STEP; temperature controls exploration vs. exploitation |
| All three | Semantic random walk | Start at a knowledge node, use GRAPH_STEP to traverse, EMBED_SIMILARITY to score relevance, SAMPLE_SOFTMAX to choose next hop |

**Combined workflow — semantic knowledge retrieval:**
```asm
; 1. Embed user query
; (assumes query embedding computed and stored at query_addr)
; 2. KNN search for relevant knowledge entries
0xFF 0x08 0x03 0x03 0x00 0x01       ; EMBED_KNN R3, R0, R1
; 3. For each result, check knowledge graph for related concepts
0xFF 0x09 0x08 0x04 0x05 0x06       ; GRAPH_NEIGHBORS
; 4. Score related concepts by similarity
0xFF 0x08 0x08 0x07 0x08 0x09       ; EMBED_SIMILARITY
; 5. Select next exploration direction using temperature
0xFF 0x0A 0x05 0x0A 0x0B 0x0C       ; SAMPLE_SOFTMAX
```

---

## Appendix A — Extension ID Allocation

| Extension ID | Name | Status | Spec Document |
|-------------|------|--------|---------------|
| 0x00 | EXT_NULL | Reserved | ISA v3 full draft |
| 0x01 | EXT_BABEL | Proposed | ISA v3 full draft §4.20.3 |
| 0x02 | EXT_EDGE | Proposed | ISA v3 full draft §4.20.4 |
| 0x03 | EXT_CONFIDENCE | Proposed | ISA v3 full draft §4.20.5 |
| 0x04 | EXT_TENSOR | Proposed | ISA v3 full draft §4.20.6 |
| 0x05 | EXT_SECURITY | Proposed | ISA v3 full draft §4.20.7 |
| 0x06 | EXT_TEMPORAL | Proposed | ISA v3 full draft §4.20.8 |
| 0x07 | EXT_STRUCT | Proposed | structured-data-opcodes-spec.md |
| 0x08 | **EXT_EMBED** | **DRAFT** | **This document §2** |
| 0x09 | **EXT_GRAPH** | **DRAFT** | **This document §3** |
| 0x0A | **EXT_PROB** | **DRAFT** | **This document §4** |
| 0x0B–0x7F | Unallocated | — | Available for fleet-standard proposals |
| 0x80–0xEF | Experimental | Self-assigned | Vendor-specific extensions |
| 0xF0–0xFF | Meta | Reserved | VER_EXT, LOAD_EXT, etc. |

---

## Appendix B — Cross-References

| Reference | Location | Relevance |
|-----------|----------|-----------|
| ISA v3 Full Draft | ISA-V3-FULL-DRAFT.md | Base ISA, Format H escape prefix, register model |
| Structured Data Opcodes | structured-data-opcodes-spec.md | Extension pattern (EXT_STRUCT at 0x07) |
| ISA v3 Escape Prefix | isa-v3-escape-prefix-spec.md | Format H encoding, VER_EXT, extension negotiation |
| Security Primitives | security-primitives-spec.md | SANDBOX_ALLOC, TAG_ALLOC, confidence sanitization |
| Async/Temporal Primitives | async-temporal-primitives-spec.md | SUSPEND/RESUME for long-running graph traversals |
| ISA v3 Address Map | isa-v3-address-map.md | Complete base ISA opcode layout |
| A2A Primitives | primitives.py | Branch, Fork, Discuss — use graph sampling for decision-making |
| TASK-BOARD | TASK-BOARD.md | EMBED-001, GRAPH-001, PROB-001 task definitions |
| Conformance Runner | tools/conformance_runner.py | Test execution infrastructure for new vectors |

---

*End of document — FLUX Advanced Opcodes Specification v1.0.0-draft*
