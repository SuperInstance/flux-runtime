# FLUX ISA v3 — Graph Traversal Extension Specification

**Document ID:** ISA-GRAPH-001
**Task Board:** GRAPH-001
**Status:** Draft
**Author:** Super Z (Fleet Agent, Opcode Design Board)
**Date:** 2026-04-12
**Depends On:** FLUX ISA v3 Unified Specification, ISA-002 Escape Prefix Spec
**Extension Group ID:** 0x00000007
**Extension Name:** `org.flux.graph`
**Opcode Range:** 0xFFC0–0xFFCF
**Version:** 1.0

---

## Table of Contents

1. [Introduction & Motivation](#1-introduction--motivation)
2. [Graph Memory Format](#2-graph-memory-format)
3. [Graph State Machine](#3-graph-state-machine)
4. [Opcode Table](#4-opcode-table)
5. [Opcode Definitions](#5-opcode-definitions)
6. [Binary Encoding](#6-binary-encoding)
7. [Execution Semantics](#7-execution-semantics)
8. [Pattern Matching & Query](#8-pattern-matching--query)
9. [Node/Edge Attribute Storage](#9-nodeedge-attribute-storage)
10. [Interaction with Existing ISA](#10-interaction-with-existing-isa)
11. [Error Handling & Trap Codes](#11-error-handling--trap-codes)
12. [Performance Considerations](#12-performance-considerations)
13. [Bytecode Examples](#13-bytecode-examples)
14. [Formal Semantics](#14-formal-semantics)
15. [Appendix](#15-appendix)

---

## 1. Introduction & Motivation

### 1.1 The Graph Traversal Problem

FLUX agents frequently operate over relational structures: social networks,
knowledge graphs, dependency trees, organizational hierarchies, and semantic
networks. These structures are naturally represented as graphs, and common
agent tasks require efficient traversal:

- **Social graph analysis**: Find mutual friends, compute shortest paths,
  detect communities, traverse relationship chains.
- **Knowledge graph navigation**: Follow entity relationships, answer
  multi-hop queries, discover implicit connections.
- **Dependency resolution**: Topological sort, cycle detection, transitive
  closure computation, critical path analysis.
- **Routing**: Shortest path, minimum spanning tree, flow optimization.

Implementing graph traversal in pure FLUX bytecode requires manual pointer
chasing, queue/stack management, and visited-set tracking — error-prone and
verbose. The graph traversal extension provides dedicated instructions for
loading, traversing, and querying graph structures.

### 1.2 Design Goals

1. **Expressiveness**: Support BFS, DFS, and pattern-match queries over
   arbitrary directed/undirected graphs.
2. **Memory efficiency**: Use CSR (Compressed Sparse Row) as the primary
   format for compact in-memory representation.
3. **Composability**: Graph traversal results integrate with the confidence
   system and A2A fleet operations.
4. **Deterministic ordering**: Traversal order is fully deterministic
   (sorted by edge weight or insertion order).
5. **Incremental exploration**: Agents can pause and resume traversals,
   enabling interactive exploration.
6. **Attribute support**: Nodes and edges carry typed attributes accessible
   during traversal.

### 1.3 Relationship to Existing Opcodes

| Core Capability | Core Opcodes | Graph Extension Adds |
|-----------------|-------------|----------------------|
| Pointer chasing | LOAD, LOADI, LOADOFF | GRAPH_STEP (single hop) |
| Queue management | PUSH, POP (stack only) | GRAPH_BFS_* (implicit queue) |
| Stack management | PUSH, POP | GRAPH_DFS_* (implicit stack) |
| Comparison | CMP_EQ, CMP_LT | GRAPH_QUERY (pattern match) |
| Memory layout | MALLOC, FREE | GRAPH_LOAD (structured parse) |

---

## 2. Graph Memory Format

### 2.1 Graph Header

A graph is stored in memory as a contiguous block with a fixed header:

```
Graph Memory Layout:

Offset  Size  Field                    Description
------  ----  ----                     -----------
0x000   4     magic                    0x47524150 ("GRAF") or 0x47524146 ("GRAF")
0x004   2     version                 Format version (currently 1)
0x006   2     flags                    Bit 0: directed, Bit 1: weighted,
                                        Bit 2: has_node_attrs, Bit 3: has_edge_attrs
0x008   4     num_nodes               Total number of nodes (max 2^32 - 1)
0x00C   4     num_edges               Total number of directed edges
0x010   4     node_offset             Byte offset to node ID table
0x014   4     edge_dst_offset         Byte offset to edge destination array (CSR)
0x018   4     edge_src_offset         Byte offset to edge source array (CSR reverse)
0x01C   4     edge_weight_offset      Byte offset to edge weight array (if weighted)
0x020   4     node_attr_offset        Byte offset to node attribute section
0x024   4     edge_attr_offset        Byte offset to edge attribute section
0x028   4     csr_index_offset        Byte offset to CSR index array
0x02C   4     name_table_offset       Byte offset to string name table
0x030   4     node_id_width           Bytes per node ID (1, 2, 4, or 8)
0x034   4     max_degree              Maximum out-degree of any node
0x038   4     reserved[0]
0x03C   4     reserved[1]
0x040   ...   (header ends)           Total header size: 64 bytes
```

### 2.2 CSR (Compressed Sparse Row) Format

The primary graph representation uses CSR for efficient edge iteration:

```
CSR Data Structures:

1. Node ID Table (at node_offset):
   ┌──────────┬──────────┬─────┐
   │ node[0]  │ node[1]  │ ... │ node_id[num_nodes - 1]
   │ (NID bytes)│ (NID bytes)│     │
   └──────────┴──────────┴─────┘
   Size: num_nodes × node_id_width bytes
   Nodes are indexed 0..num_nodes-1 internally; this table maps
   internal index → external node ID.

2. CSR Index Array (at csr_index_offset):
   ┌─────────────────────────────────────────────────┐
   │ index[0] │ index[1] │ ... │ index[num_nodes]   │
   │ u32      │ u32      │     │ u32                │
   └─────────────────────────────────────────────────┘
   Size: (num_nodes + 1) × 4 bytes
   index[i] = starting position of node i's edges in dst[] array
   index[i+1] - index[i] = out-degree of node i
   index[num_nodes] = num_edges (sentinel)

3. Edge Destination Array (at edge_dst_offset):
   ┌─────────────────────────────────────────────────┐
   │ dst[0] │ dst[1] │ dst[2] │ ... │ dst[num_edges-1]│
   │ NID     │ NID    │ NID    │     │ NID             │
   └─────────────────────────────────────────────────┘
   Size: num_edges × node_id_width bytes
   Edges for node i are at dst[index[i] .. index[i+1]-1]

4. Edge Weight Array (at edge_weight_offset, if weighted):
   ┌─────────────────────────────────────────────────┐
   │ weight[0] │ weight[1] │ ... │ weight[num_edges-1]│
   │ float32   │ float32   │     │ float32            │
   └─────────────────────────────────────────────────┘
   Size: num_edges × 4 bytes
```

### 2.3 Adjacency List Alternative

For graphs that are frequently modified, an adjacency list format is supported:

```
Adjacency List Node Entry:

Offset  Size  Field                    Description
------  ----  ----                     -----------
0x000   NID   node_id                  External node ID
0x00N   4     num_neighbors            Number of adjacent nodes
0x00N+4 4     neighbor_table_offset   Offset to neighbor array
0x00N+8 4     attribute_offset         Offset to node attributes (if any)
0x00N+C 4     next_node_offset         Offset to next node entry (linked list)

Adjacency List Neighbor Entry:

Offset  Size  Field                    Description
------  ----  ----                     -----------
0x000   NID   neighbor_id              Adjacent node ID
0x00N   4     weight                   Edge weight (float32, if weighted)
0x00N+4 4     attribute_offset         Edge attribute offset (if any)
```

**The GRAPH_LOAD instruction auto-detects the format based on the magic
number and flags field.**

### 2.4 Memory Layout Example: Social Graph

```
// 4-node directed social graph:
//   Alice (0) → Bob (1), Carol (2)
//   Bob (1) → Dave (3)
//   Carol (2) → Alice (0), Dave (3)
//   Dave (3) → (no outgoing edges)

// CSR representation:
//   Nodes: [0=Alice, 1=Bob, 2=Carol, 3=Dave]
//   Edges: [1, 2, 3, 0, 3]  (ordered by source node)
//   CSR index: [0, 2, 3, 5, 5]

Memory layout (hex):

0x000: 50 41 52 47  // magic = "GRAF" (LE)
0x004: 01 00        // version = 1
0x006: 01 00        // flags = 0x01 (directed, not weighted)
0x008: 04 00 00 00  // num_nodes = 4
0x00C: 05 00 00 00  // num_edges = 5
0x010: 40 00 00 00  // node_offset = 0x40
0x014: 54 00 00 00  // edge_dst_offset = 0x54
0x018: 68 00 00 00  // edge_src_offset = 0x68
0x01C: 7C 00 00 00  // edge_weight_offset = 0x7C (unused, not weighted)
0x020: 7C 00 00 00  // node_attr_offset = 0x7C (unused)
0x024: 7C 00 00 00  // edge_attr_offset = 0x7C (unused)
0x028: 80 00 00 00  // csr_index_offset = 0x80
0x02C: 98 00 00 00  // name_table_offset = 0x98
0x030: 04 00 00 00  // node_id_width = 4 bytes
0x034: 02 00 00 00  // max_degree = 2
0x038: 00 00 00 00  // reserved[0]
0x03C: 00 00 00 00  // reserved[1]

0x040: 00 00 00 00  // node_id[0] = 0 (Alice)
0x044: 01 00 00 00  // node_id[1] = 1 (Bob)
0x048: 02 00 00 00  // node_id[2] = 2 (Carol)
0x04C: 03 00 00 00  // node_id[3] = 3 (Dave)

0x050: 00 00 00 00  // padding to align

0x054: 01 00 00 00  // dst[0] = 1 (Alice → Bob)
0x058: 02 00 00 00  // dst[1] = 2 (Alice → Carol)
0x05C: 03 00 00 00  // dst[2] = 3 (Bob → Dave)
0x060: 00 00 00 00  // dst[3] = 0 (Carol → Alice)
0x064: 03 00 00 00  // dst[4] = 3 (Carol → Dave)

0x068: 00 00 00 00  // reverse index placeholder
0x06C: ...
0x070: ...
0x074: ...
0x078: ...

0x080: 00 00 00 00  // csr_index[0] = 0  (Alice edges start at 0)
0x084: 02 00 00 00  // csr_index[1] = 2  (Bob edges start at 2)
0x088: 03 00 00 00  // csr_index[2] = 3  (Carol edges start at 3)
0x08C: 05 00 00 00  // csr_index[3] = 5  (Dave edges start at 5)
0x090: 05 00 00 00  // csr_index[4] = 5  (sentinel = num_edges)

0x094: 00 00 00 00  // padding

0x098: 41 6C 69 63 65 00  // "Alice\0"
0x09F: 42 6F 62 00         // "Bob\0"
0x0A3: 43 61 72 6F 6C 00  // "Carol\0"
0x0A9: 44 61 76 65 00      // "Dave\0"
```

---

## 3. Graph State Machine

### 3.1 Graph Context Registers

The graph extension maintains a set of implicit state registers that track
the current traversal context:

```
Graph Context State:

  gctx.graph_addr: u64     Base address of loaded graph (0 = no graph)
  gctx.current_node: NID   Current node during traversal
  gctx.current_edge_idx: u32  Index into current node's edge list
  gctx.bfs_queue: Queue[NID]  BFS frontier queue
  gctx.bfs_visited: Set[NID]  BFS visited set
  gctx.dfs_stack: Stack[(NID, u32)]  DFS stack (node, next_edge_idx)
  gctx.dfs_visited: Set[NID]  DFS visited set
  gctx.query_state: QueryState  Pattern match query state
  gctx.traversal_depth: u32  Current traversal depth
  gctx.traversal_mode: u8   0=none, 1=step, 2=bfs, 3=dfs
  gctx.iter_count: u64      Total nodes/edges iterated
```

### 3.2 Traversal Modes

The graph extension supports three traversal modes:

```
Mode 0: INACTIVE
  No traversal in progress. Graph may be loaded but not being traversed.

Mode 1: STEP MODE
  Single-edge traversal. GRAPH_STEP advances one edge from the current node.
  The agent maintains full control over the traversal path.

Mode 2: BFS MODE
  Breadth-first search. GRAPH_BFS_INIT starts a search from a source node.
  GRAPH_BFS_NEXT returns nodes in BFS order. The queue and visited set are
  managed internally.

Mode 3: DFS MODE
  Depth-first search. GRAPH_DFS_INIT starts a search from a source node.
  GRAPH_DFS_NEXT returns nodes in DFS order. The stack and visited set are
  managed internally.
```

### 3.3 Mode Transitions

```
  ┌──────────┐  GRAPH_LOAD    ┌──────────┐
  │ INACTIVE │───────────────→│ INACTIVE │ (graph loaded, no traversal)
  └──────────┘                └──────────┘
       │                           │
       │ GRAPH_STEP                │ GRAPH_BFS_INIT / GRAPH_DFS_INIT
       ▼                           ▼
  ┌──────────┐               ┌──────────┐  ┌──────────┐
  │  STEP    │               │   BFS    │  │   DFS    │
  └──────────┘               └──────────┘  └──────────┘
       │                           │              │
       │ (any init)                │ (complete)    │ (complete)
       ▼                           ▼              ▼
  ┌──────────┐               ┌──────────────────────────┐
  │  BFS/DFS │──────────────→│       INACTIVE            │
  └──────────┘               └──────────────────────────┘
```

---

## 4. Opcode Table

| Opcode   | Mnemonic              | Format | Operands           | Description                              |
|----------|----------------------|--------|--------------------|------------------------------------------|
| 0xFFC0   | GRAPH_LOAD           | D      | rd, imm8           | Load graph structure from memory         |
| 0xFFC1   | GRAPH_UNLOAD         | A      | -                  | Release graph context, free state        |
| 0xFFC2   | GRAPH_STEP           | E      | rd, rs1, rs2       | Traverse one edge from current node      |
| 0xFFC3   | GRAPH_BFS_INIT       | B      | rd                 | Initialize BFS from node in rd           |
| 0xFFC4   | GRAPH_BFS_NEXT       | A      | -                  | Get next node in BFS order → r0          |
| 0xFFC5   | GRAPH_DFS_INIT       | B      | rd                 | Initialize DFS from node in rd           |
| 0xFFC6   | GRAPH_DFS_NEXT       | A      | -                  | Get next node in DFS order → r0          |
| 0xFFC7   | GRAPH_QUERY          | D      | rd, imm8           | Pattern-match query on graph             |
| 0xFFC8   | GRAPH_NODE_ATTR      | E      | rd, rs1, rs2       | Get node attribute → rd                  |
| 0xFFC9   | GRAPH_EDGE_ATTR      | E      | rd, rs1, rs2       | Get edge attribute → rd                  |
| 0xFFCA   | GRAPH_DEGREE         | E      | rd, rs1, rs2       | Get in/out/total degree → rd             |
| 0xFFCB   | GRAPH_PATH           | E      | rd, rs1, rs2       | Shortest path between two nodes          |
| 0xFFCC   | GRAPH_NEIGHBORS      | E      | rd, rs1, rs2       | Get all neighbors of a node              |
| 0xFFCD   | GRAPH_SET_CURRENT    | B      | rd                 | Set current traversal node               |
| 0xFFCE   | GRAPH_INFO           | A      | -                  | Query graph metadata → general registers  |
| 0xFFCF   | GRAPH_RESET          | A      | -                  | Reset graph traversal state              |

---

## 5. Opcode Definitions

### 5.1 GRAPH_LOAD (0xFFC0) — Format D

**Syntax:** `GRAPH_LOAD rd, graph_format`

**Description:** Load a graph structure from memory into the graph context.
`rd` is a general-purpose register containing the base address of the graph
in memory. `imm8` encodes the expected format:
- 0 = Auto-detect (magic number)
- 1 = CSR format
- 2 = Adjacency list format

**Semantics:**
```
  Pseudocode: GRAPH_LOAD

  def graph_load(rd: int, graph_format: int):
      base_addr = r[rd]

      # Validate magic number
      magic = mem_read_u32(base_addr + 0x000)
      if magic != 0x47524146:  # "GRAF"
          raise TRAP_GRAPH_CORRUPT

      # Parse header
      version = mem_read_u16(base_addr + 0x004)
      if version != 1:
          raise TRAP_GRAPH_VERSION

      flags = mem_read_u16(base_addr + 0x006)
      num_nodes = mem_read_u32(base_addr + 0x008)
      num_edges = mem_read_u32(base_addr + 0x00C)

      # Store graph context
      gctx.graph_addr = base_addr
      gctx.flags = flags
      gctx.num_nodes = num_nodes
      gctx.num_edges = num_edges
      gctx.node_id_width = mem_read_u32(base_addr + 0x030)
      gctx.max_degree = mem_read_u32(base_addr + 0x034)

      # Reset traversal state
      gctx.traversal_mode = MODE_INACTIVE
      gctx.current_node = INVALID_NID
      gctx.bfs_queue.clear()
      gctx.dfs_stack.clear()
      gctx.bfs_visited.clear()
      gctx.dfs_visited.clear()

      # Store graph info in general registers
      r0 = num_nodes
      r1 = num_edges
      c[r0] = 1.0  # freshly loaded = confident
```

**Trap conditions:**
- Invalid magic number → TRAP_GRAPH_CORRUPT
- Unsupported version → TRAP_GRAPH_VERSION
- Address not 8-byte aligned → TRAP_ALIGNMENT
- Graph already loaded → TRAP_GRAPH_ALREADY_LOADED

### 5.2 GRAPH_UNLOAD (0xFFC1) — Format A

**Syntax:** `GRAPH_UNLOAD`

**Description:** Release the current graph context. Clears all traversal state,
frees internal data structures (visited sets, queues, stacks). Does not free
the underlying graph memory (that is the agent's responsibility via FREE).

**Semantics:**
```
  def graph_unload():
      gctx.graph_addr = 0
      gctx.traversal_mode = MODE_INACTIVE
      gctx.bfs_queue.clear()
      gctx.dfs_stack.clear()
      gctx.bfs_visited.clear()
      gctx.dfs_visited.clear()
      gctx.query_state = None
```

### 5.3 GRAPH_STEP (0xFFC2) — Format E

**Syntax:** `GRAPH_STEP rd, rs1, rs2`

**Description:** Traverse one edge from the current node (or from the node
specified in `rs1`). Returns the destination node ID in `rd`, and optionally
selects a specific edge via `rs2`.

**Operands:**
- `rd` = destination register for the reached node ID
- `rs1` = source node (NID in register; if 0xFFFFFFFF, use gctx.current_node)
- `rs2` = edge selector:
  - If `rs2 == 0`: follow the first unvisited edge (sorted by weight/ID)
  - If `rs2 > 0`: follow the (rs2-1)th edge from the source node (0-indexed)
  - If `rs2 == 0xFFFFFFFF`: follow a random edge (uniform random)

**Semantics:**
```
  Pseudocode: GRAPH_STEP

  def graph_step(rd: int, rs1: int, rs2: int):
      if gctx.graph_addr == 0:
          raise TRAP_GRAPH_NOT_LOADED

      source = r[rs1] if r[rs1] != 0xFFFFFFFF else gctx.current_node
      edge_sel = r[rs2]

      # Look up source node's internal index
      src_idx = node_id_to_internal_index(source)
      if src_idx == INVALID:
          raise TRAP_GRAPH_NODE_NOT_FOUND

      # Get edge range from CSR index
      edge_start = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                                 src_idx * 4)
      edge_end = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                               (src_idx + 1) * 4)
      degree = edge_end - edge_start

      if degree == 0:
          # No outgoing edges
          r[rd] = 0xFFFFFFFF  # INVALID_NID
          c[rd] = 0.0
          gctx.traversal_mode = MODE_INACTIVE
          return

      # Select edge
      match edge_sel:
          case 0:
              # First unvisited
              for i in range(edge_start, edge_end):
                  dst = read_node_id(gctx.graph_addr + gctx.edge_dst_offset +
                                     i * gctx.node_id_width)
                  if dst not in gctx.step_visited:
                      selected_edge = i
                      break
              else:
                  r[rd] = 0xFFFFFFFF
                  return

          case 0xFFFFFFFF:
              # Random edge
              selected_edge = edge_start + random_int(0, degree - 1)

          default:
              # Specific edge index
              idx = edge_sel - 1  # 1-based to 0-based
              if idx >= degree:
                  raise TRAP_GRAPH_EDGE_OUT_OF_RANGE
              selected_edge = edge_start + idx

      # Read destination
      dst = read_node_id(gctx.graph_addr + gctx.edge_dst_offset +
                         selected_edge * gctx.node_id_width)

      # Update state
      r[rd] = dst
      gctx.current_node = dst
      gctx.traversal_mode = MODE_STEP
      gctx.step_visited.add(dst)
      gctx.iter_count += 1

      # Confidence: based on edge weight if weighted
      if gctx.flags & FLAG_WEIGHTED:
          weight = mem_read_f32(gctx.graph_addr + gctx.edge_weight_offset +
                                selected_edge * 4)
          c[rd] = min(1.0, weight)  # higher weight = more confident
      else:
          c[rd] = 1.0

      # Update traversal depth
      gctx.traversal_depth += 1
```

### 5.4 GRAPH_BFS_INIT (0xFFC3) — Format B

**Syntax:** `GRAPH_BFS_INIT rd`

**Description:** Initialize a breadth-first search starting from the node
whose ID is in general-purpose register `rd`.

**Semantics:**
```
  Pseudocode: GRAPH_BFS_INIT

  def graph_bfs_init(rd: int):
      if gctx.graph_addr == 0:
          raise TRAP_GRAPH_NOT_LOADED

      source = r[rd]
      src_idx = node_id_to_internal_index(source)
      if src_idx == INVALID:
          raise TRAP_GRAPH_NODE_NOT_FOUND

      # Clear previous state
      gctx.bfs_queue = Queue()
      gctx.bfs_visited = Set()
      gctx.traversal_depth = 0
      gctx.iter_count = 0

      # Initialize BFS
      gctx.bfs_queue.enqueue(source)
      gctx.bfs_visited.add(source)
      gctx.current_node = source
      gctx.traversal_mode = MODE_BFS
```

### 5.5 GRAPH_BFS_NEXT (0xFFC4) — Format A

**Syntax:** `GRAPH_BFS_NEXT`

**Description:** Dequeue the next node in BFS order. Returns the node ID in
`r0`. Returns `0xFFFFFFFF` (INVALID_NID) when the BFS is complete.

**Semantics:**
```
  Pseudocode: GRAPH_BFS_NEXT

  def graph_bfs_next():
      if gctx.traversal_mode != MODE_BFS:
          raise TRAP_GRAPH_INVALID_MODE

      if gctx.bfs_queue.is_empty():
          r0 = 0xFFFFFFFF  # BFS complete
          c[r0] = 0.0
          gctx.traversal_mode = MODE_INACTIVE
          return

      current = gctx.bfs_queue.dequeue()
      gctx.current_node = current
      gctx.iter_count += 1

      # Enqueue unvisited neighbors
      src_idx = node_id_to_internal_index(current)
      edge_start = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                                 src_idx * 4)
      edge_end = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                               (src_idx + 1) * 4)

      for i in range(edge_start, edge_end):
          dst = read_node_id(gctx.graph_addr + gctx.edge_dst_offset +
                             i * gctx.node_id_width)
          if dst not in gctx.bfs_visited:
              gctx.bfs_visited.add(dst)
              gctx.bfs_queue.enqueue(dst)

      r0 = current
      c[r0] = 1.0

      # Depth tracking: BFS depth = number of times queue was empty + 1
      # (simplified; actual implementation tracks depth per level)
```

### 5.6 GRAPH_DFS_INIT (0xFFC5) — Format B

**Syntax:** `GRAPH_DFS_INIT rd`

**Description:** Initialize a depth-first search starting from the node
whose ID is in general-purpose register `rd`.

**Semantics:**
```
  Pseudocode: GRAPH_DFS_INIT

  def graph_dfs_init(rd: int):
      if gctx.graph_addr == 0:
          raise TRAP_GRAPH_NOT_LOADED

      source = r[rd]
      src_idx = node_id_to_internal_index(source)
      if src_idx == INVALID:
          raise TRAP_GRAPH_NODE_NOT_FOUND

      # Clear previous state
      gctx.dfs_stack = Stack()
      gctx.dfs_visited = Set()
      gctx.traversal_depth = 0
      gctx.iter_count = 0

      # Initialize DFS
      gctx.dfs_stack.push((source, 0))  # (node, next_edge_index)
      gctx.dfs_visited.add(source)
      gctx.current_node = source
      gctx.traversal_mode = MODE_DFS
```

### 5.7 GRAPH_DFS_NEXT (0xFFC6) — Format A

**Syntax:** `GRAPH_DFS_NEXT`

**Description:** Get the next node in DFS order. Returns the node ID in `r0`.
Returns `0xFFFFFFFF` (INVALID_NID) when the DFS is complete.

**Semantics:**
```
  Pseudocode: GRAPH_DFS_NEXT

  def graph_dfs_next():
      if gctx.traversal_mode != MODE_DFS:
          raise TRAP_GRAPH_INVALID_MODE

      if gctx.dfs_stack.is_empty():
          r0 = 0xFFFFFFFF  # DFS complete
          c[r0] = 0.0
          gctx.traversal_mode = MODE_INACTIVE
          return

      current, next_edge = gctx.dfs_stack.peek()
      gctx.current_node = current

      # Try to find next unvisited neighbor
      src_idx = node_id_to_internal_index(current)
      edge_start = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                                 src_idx * 4)
      edge_end = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                               (src_idx + 1) * 4)

      found_child = False
      for i in range(next_edge, edge_end):
          dst = read_node_id(gctx.graph_addr + gctx.edge_dst_offset +
                             i * gctx.node_id_width)
          if dst not in gctx.dfs_visited:
              gctx.dfs_visited.add(dst)
              gctx.dfs_stack.update_top((current, i + 1))
              gctx.dfs_stack.push((dst, 0))
              gctx.traversal_depth += 1
              gctx.iter_count += 1
              r0 = dst
              c[r0] = 1.0
              found_child = True
              break

      if not found_child:
          # Backtrack: pop current node
          gctx.dfs_stack.pop()
          gctx.traversal_depth -= 1
          gctx.iter_count += 1
          r0 = current  # Return current (now being backtracked from)
          # Note: In some implementations, backtracked nodes get confidence decay
          c[r0] = 0.5  # Reduced confidence for backtracked nodes
```

### 5.8 GRAPH_QUERY (0xFFC7) — Format D

**Syntax:** `GRAPH_QUERY rd, pattern_id`

**Description:** Execute a pattern-match query on the graph. `rd` is a
general-purpose register pointing to a query descriptor in memory. `imm8`
encodes the query type:
- 0 = Path query: find path from A to B
- 1 = Neighborhood query: all nodes within K hops
- 2 = Pattern query: match a graph pattern
- 3 = Reachability: can A reach B?

**Query Descriptor Memory Layout:**

```
Path Query (type=0):
  ┌──────────┬──────────┬──────────┬──────────┐
  │ source   │ target   │ max_depth│ algorithm│
  │ NID      │ NID      │ u32      │ u8       │
  └──────────┴──────────┴──────────┴──────────┘
  algorithm: 0=BFS (shortest), 1=DFS (any), 2=Dijkstra (weighted)
  Size: node_id_width * 2 + 4 + 1 bytes

Neighborhood Query (type=1):
  ┌──────────┬──────────┐
  │ center   │ radius   │
  │ NID      │ u32      │
  └──────────┴──────────┘
  Size: node_id_width + 4 bytes

Pattern Query (type=2):
  ┌──────────┬──────────┬──────────┐
  │ pattern_addr │ result_addr │ max_results │
  │ u64          │ u64          │ u32          │
  └──────────┴──────────┴──────────┘
  pattern_addr: address of pattern description (see Section 8)
  Size: 8 + 8 + 4 bytes

Reachability Query (type=3):
  ┌──────────┬──────────┐
  │ source   │ target   │
  │ NID      │ NID      │
  └──────────┴──────────┘
  Result: r0 = 1 (reachable) or 0 (not reachable)
  Size: node_id_width * 2 bytes
```

**Semantics:**
```
  Pseudocode: GRAPH_QUERY

  def graph_query(rd: int, query_type: int):
      query_addr = r[rd]

      match query_type:
          case 0:  # Path query
              source = read_nid(query_addr)
              target = read_nid(query_addr + node_id_width)
              max_depth = mem_read_u32(query_addr + node_id_width * 2)
              algorithm = mem_read_u8(query_addr + node_id_width * 2 + 4)

              if algorithm == 2 and gctx.flags & FLAG_WEIGHTED:
                  path = dijkstra(source, target, max_depth)
              elif algorithm == 1:
                  path = dfs_path(source, target, max_depth)
              else:
                  path = bfs_shortest_path(source, target, max_depth)

              # Write path to result buffer
              write_path_result(r0, path)

          case 1:  # Neighborhood
              center = read_nid(query_addr)
              radius = mem_read_u32(query_addr + node_id_width)
              neighbors = bfs_neighborhood(center, radius)
              write_neighbors_result(r0, neighbors)

          case 2:  # Pattern match
              pattern_addr = mem_read_u64(query_addr)
              result_addr = mem_read_u64(query_addr + 8)
              max_results = mem_read_u32(query_addr + 16)
              matches = pattern_match(pattern_addr, max_results)
              write_pattern_results(result_addr, matches)

          case 3:  # Reachability
              source = read_nid(query_addr)
              target = read_nid(query_addr + node_id_width)
              reachable = bfs_reachable(source, target)
              r0 = 1 if reachable else 0
              c[r0] = 1.0
```

### 5.9 GRAPH_NODE_ATTR (0xFFC8) — Format E

**Syntax:** `GRAPH_NODE_ATTR rd, rs1, rs2`

**Description:** Retrieve a node attribute. `rs1` contains the node ID.
`rs2` contains the attribute key (a small integer index into the node's
attribute table). The attribute value is written to `rd`.

**Semantics:**
```
  def graph_node_attr(rd: int, rs1: int, rs2: int):
      node_id = r[rs1]
      attr_key = r[rs2]

      if gctx.graph_addr == 0:
          raise TRAP_GRAPH_NOT_LOADED

      # Locate node attribute table
      attr_offset = gctx.node_attr_offset
      if attr_offset == gctx.graph_addr:  # unused sentinel
          r[rd] = 0
          c[rd] = 0.0
          return

      # Navigate to node's attributes
      node_idx = node_id_to_internal_index(node_id)
      node_attr_base = gctx.graph_addr + attr_offset
      node_attr_entry = node_attr_base + node_idx * NODE_ATTR_ENTRY_SIZE

      # Read attribute by key
      num_attrs = mem_read_u16(node_attr_entry)
      for i in range(num_attrs):
          key = mem_read_u16(node_attr_entry + 2 + i * ATTR_ENTRY_SIZE)
          if key == attr_key:
              value = mem_read_u32(node_attr_entry + 2 + i * ATTR_ENTRY_SIZE + 2)
              r[rd] = value
              c[rd] = 1.0
              return

      r[rd] = 0  # Attribute not found
      c[rd] = 0.0
```

### 5.10 GRAPH_EDGE_ATTR (0xFFC9) — Format E

**Syntax:** `GRAPH_EDGE_ATTR rd, rs1, rs2`

**Description:** Retrieve an edge attribute for the edge from `gctx.current_node`
to the node in `rs1`. `rs2` contains the attribute key. The attribute value
is written to `rd`.

### 5.11 GRAPH_DEGREE (0xFFCA) — Format E

**Syntax:** `GRAPH_DEGREE rd, rs1, rs2`

**Description:** Compute the degree of a node. `rs1` = node ID. `rs2`
selects the degree type:
- 0 = out-degree
- 1 = in-degree (requires reverse CSR index)
- 2 = total degree (in + out)

**Semantics:**
```
  def graph_degree(rd: int, rs1: int, rs2: int):
      node_id = r[rs1]
      degree_type = r[rs2]
      node_idx = node_id_to_internal_index(node_id)

      match degree_type:
          case 0:  # Out-degree
              start = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                                   node_idx * 4)
              end = mem_read_u32(gctx.graph_addr + gctx.csr_index_offset +
                                 (node_idx + 1) * 4)
              r[rd] = end - start

          case 1:  # In-degree
              start = mem_read_u32(gctx.graph_addr + gctx.edge_src_offset +
                                   node_idx * 4)
              end = mem_read_u32(gctx.graph_addr + gctx.edge_src_offset +
                                 (node_idx + 1) * 4)
              r[rd] = end - start

          case 2:  # Total
              out_d = (out_degree calculation as above)
              in_d = (in_degree calculation as above)
              r[rd] = out_d + in_d

      c[rd] = 1.0
```

### 5.12 GRAPH_PATH (0xFFCB) — Format E

**Syntax:** `GRAPH_PATH rd, rs1, rs2`

**Description:** Compute shortest path between two nodes. `rs1` = source node
ID, `rs2` = target node ID. Result is written to a buffer pointed to by `r[rd]`.

**Result buffer layout:**
```
Offset  Size  Field              Description
------  ----  ----               -----------
0x000   4     path_length        Number of nodes in path
0x004   4     total_weight        Sum of edge weights (float32 bits)
0x008   ...   path_nodes[]       Array of node IDs
```

### 5.13 GRAPH_NEIGHBORS (0xFFCC) — Format E

**Syntax:** `GRAPH_NEIGHBORS rd, rs1, rs2`

**Description:** Get all neighbors of a node. `rs1` = node ID. `rs2` =
pointer to output buffer. The neighbor list is written to the buffer:
```
  neighbor_count: u32
  neighbors[]: NID[neighbor_count]
```

### 5.14 GRAPH_SET_CURRENT (0xFFCD) — Format B

**Syntax:** `GRAPH_SET_CURRENT rd`

**Description:** Set the current traversal node to the ID in `rd`.
Does not affect any active BFS/DFS traversal (use with STEP mode).

### 5.15 GRAPH_INFO (0xFFCE) — Format A

**Syntax:** `GRAPH_INFO`

**Description:** Query graph metadata. Writes to general-purpose registers:
- `r0 = num_nodes`
- `r1 = num_edges`
- `r2 = flags`
- `r3 = max_degree`
- `r4 = traversal_mode`
- `r5 = current_node`
- `r6 = traversal_depth`
- `r7 = iter_count`

### 5.16 GRAPH_RESET (0xFFCF) — Format A

**Syntax:** `GRAPH_RESET`

**Description:** Reset traversal state without unloading the graph. Clears
BFS/DFS queues, visited sets, and resets current node. The graph remains
loaded and can be traversed again.

---

## 6. Binary Encoding

### 6.1 Escape Prefix Encoding

All graph opcodes use the `0xFF` escape prefix followed by `0xC0–0xCF`:

```
  0xFF C0 = GRAPH_LOAD
  0xFF C1 = GRAPH_UNLOAD
  0xFF C2 = GRAPH_STEP
  ...
  0xFF CF = GRAPH_RESET
```

### 6.2 Format-Specific Encodings

#### Format A — GRAPH_UNLOAD, GRAPH_BFS_NEXT, GRAPH_DFS_NEXT, GRAPH_INFO, GRAPH_RESET

```
  ┌─────┬─────┐
  │ 0xFF│ ext │    (2 bytes total)
  └─────┴─────┘
```

#### Format B — GRAPH_BFS_INIT, GRAPH_DFS_INIT, GRAPH_SET_CURRENT

```
  ┌─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │    (3 bytes total)
  └─────┴─────┴─────┘
```

#### Format D — GRAPH_LOAD, GRAPH_QUERY

```
  ┌─────┬─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │imm8 │    (4 bytes total)
  └─────┴─────┴─────┴─────┘
```

#### Format E — GRAPH_STEP, GRAPH_NODE_ATTR, GRAPH_EDGE_ATTR, GRAPH_DEGREE, etc.

```
  ┌─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │ rs1 │ rs2 │    (5 bytes total)
  └─────┴─────┴─────┴─────┴─────┘
```

### 6.3 GRAPH_QUERY Type Encoding

The query type is encoded in the `imm8` field of Format D:

```
  imm8 bit layout for GRAPH_QUERY:
  ┌──────────────────────┬──────────────────────┐
  │ query_type[3:0]      │ options[3:0]         │
  │ bits 7:4             │ bits 3:0             │
  └──────────────────────┴──────────────────────┘

  query_type:
    0 = PATH
    1 = NEIGHBORHOOD
    2 = PATTERN
    3 = REACHABILITY

  options (query-specific):
    PATH:        bit 0 = return_full_path (1=yes, 0=length only)
    NEIGHBORHOOD: (reserved)
    PATTERN:     bit 0 = ordered (1=ordered match, 0=unordered)
    REACHABILITY: bit 0 = bidirectional (1=yes, 0=directed only)
```

### 6.4 Explicit Format Mode Examples

```
  GRAPH_BFS_INIT r5 (explicit format):
  ┌─────┬─────┬─────┬─────┐
  │ 0xFF│ 0xC3│ 0x01│ 0x05│
  └─────┴─────┴─────┴─────┘
  esc   ext   fmt   rd

  GRAPH_STEP r3, r1, r2 (explicit format):
  ┌─────┬─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ 0xC2│ 0x04│ 0x03│ 0x01│ 0x02│
  └─────┴─────┴─────┴─────┴─────┴─────┘
  esc   ext   fmt   rd    rs1   rs2
```

---

## 7. Execution Semantics

### 7.1 BFS Traversal Flow

```
  Agent Code                    Graph State                  Output
  ──────────                    ───────────                  ──────
  GRAPH_LOAD r1, 0             gctx.graph_addr = r1         r0=N, r1=E
  GRAPH_BFS_INIT r2            queue=[r2], visited={r2}      -
  GRAPH_BFS_NEXT               queue=[neighbors], visited+  r0=node1
  ; process node1...           -
  GRAPH_BFS_NEXT               queue updated, visited+      r0=node2
  ; process node2...           -
  ...                          -
  GRAPH_BFS_NEXT               queue empty                  r0=0xFFFFFFFF
  ; BFS complete               mode=INACTIVE                -
```

### 7.2 DFS Traversal Flow

```
  Agent Code                    Graph State                  Output
  ──────────                    ───────────                  ──────
  GRAPH_LOAD r1, 0             gctx.graph_addr = r1         -
  GRAPH_DFS_INIT r2            stack=[(r2,0)], visited={r2}  -
  GRAPH_DFS_NEXT               stack push child, depth++    r0=child1
  GRAPH_DFS_NEXT               stack push grandchild         r0=grandchild
  GRAPH_DFS_NEXT               backtrack, pop, depth--       r0=child1
  GRAPH_DFS_NEXT               push child2                   r0=child2
  ...                          -
  GRAPH_DFS_NEXT               stack empty                  r0=0xFFFFFFFF
```

### 7.3 Step Mode Flow

```
  Agent Code                         Graph State              Output
  ──────────                         ───────────              ──────
  GRAPH_LOAD r1, 0                  gctx loaded              -
  GRAPH_SET_CURRENT r2              current=r2               -
  GRAPH_STEP r3, 0xFFFF, 0          follow first edge        r3=neighbor1
  GRAPH_STEP r4, 0xFFFF, 0          follow next unvisited    r4=neighbor2
  GRAPH_STEP r5, 0xFFFF, 0xFFFFFFFF follow random edge      r5=random_nbr
  ; At dead end...                   no unvisited edges       r6=0xFFFFFFFF
```

### 7.4 Confidence During Traversal

```
  Confidence Assignment Rules:

  1. BFS_NEXT:  c[r0] = 1.0 (all BFS nodes equally confident)
  2. DFS_NEXT:  c[r0] = 1.0 (forward), 0.5 (backtrack)
  3. STEP:      c[rd] = 1.0 (unweighted), edge_weight (weighted)
  4. QUERY:     c[r0] = 1.0 (exact match), 0.7 (approximate)
  5. PATH:      c[rd] = exp(-path_length * 0.1) (longer paths = less confident)
  6. DEGREE:    c[rd] = 1.0 (exact computation)
```

---

## 8. Pattern Matching & Query

### 8.1 Graph Pattern Description

Pattern queries use a compact pattern description format in memory:

```
Pattern Description Layout:

  num_constraints: u16     Number of constraint triples
  constraints[]:            Array of constraint entries

  Constraint Entry:
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    │ src_var  │ edge_type│ dst_var  │ op       │ value    │
    │ u8       │ u16      │ u8       │ u8       │ u32      │
    └──────────┴──────────┴──────────┴──────────┴──────────┘
    Size: 8 bytes per constraint

  src_var/dst_var: Variable bindings (0–15, or 0xFF for literal)
  edge_type: Edge type ID (or 0xFFFF for any edge)
  op: Comparison operator for value constraint
      0 = EQ, 1 = NE, 2 = LT, 3 = GT, 4 = LE, 5 = GE, 6 = NONE
  value: Comparison value (for attribute filtering)
```

### 8.2 Example Pattern: "Friends of Friends"

Find all people who are friends of my friends:

```
  Constraint 1: (ME) --friend--> (FRIEND)
  Constraint 2: (FRIEND) --friend--> (FOF)

  Pattern description:
    num_constraints = 2
    constraint[0] = {src=0, edge=1("friend"), dst=1, op=NONE, val=0}
    constraint[1] = {src=1, edge=1("friend"), dst=2, op=NONE, val=0}

  Where: 0=ME (bound to query source), 1=FRIEND, 2=FOF
```

### 8.3 Pattern Matching Algorithm

```
  Pseudocode: Pattern matching

  def pattern_match(pattern_addr: int, max_results: int) -> list[Binding]:
      constraints = parse_pattern(pattern_addr)
      results = []

      # Start with all possible bindings for the first variable
      initial_bindings = [{constraints[0].src_var: n} for n in range(num_nodes)]

      # Propagate constraints
      queue = deque(initial_bindings)
      while queue and len(results) < max_results:
          binding = queue.popleft()

          for constraint in constraints:
              if not is_satisfied(binding, constraint):
                  break
          else:
              # All constraints satisfied
              results.append(binding)
              continue

          # Extend binding with neighbors
          last_var = get_last_unbound(constraints, binding)
          if last_var is not None:
              neighbors = get_neighbors(binding[get_source_var(last_var)])
              for n in neighbors:
                  new_binding = dict(binding)
                  new_binding[last_var] = n
                  queue.append(new_binding)

      return results
```

---

## 9. Node/Edge Attribute Storage

### 9.1 Attribute Table Format

Node and edge attributes are stored in compact attribute tables:

```
Node Attribute Table Entry (per node):

  ┌──────────────────────────────────────────────────────┐
  │ num_attrs: u16                                       │
  │ attr[0]: ┌───────────┬────────────────────────────┐  │
  │          │ key: u16  │ value: u32 (or inline data) │  │
  │          └───────────┴────────────────────────────┘  │
  │ attr[1]: ┌───────────┬────────────────────────────┐  │
  │          │ key: u16  │ value: u32                 │  │
  │          └───────────┴────────────────────────────┘  │
  │ ...                                                   │
  └──────────────────────────────────────────────────────┘

  Per-entry size: 2 + num_attrs × 6 bytes
```

### 9.2 Predefined Attribute Keys

| Key | Name              | Type    | Description                              |
|-----|-------------------|---------|------------------------------------------|
| 0   | ATTR_NONE         | —       | No attribute / placeholder                |
| 1   | ATTR_NAME         | str_ref | Node/edge name (string table offset)     |
| 2   | ATTR_TYPE         | u32     | Node/edge type identifier                |
| 3   | ATTR_WEIGHT       | f32     | Edge weight (if not in separate array)   |
| 4   | ATTR_LABEL        | u32     | Classification label                     |
| 5   | ATTR_TIMESTAMP    | u64     | Creation/modification timestamp          |
| 6   | ATTR_CONFIDENCE   | f32     | Source confidence for this entity        |
| 7   | ATTR_FLAGS        | u32     | Bitfield of boolean properties           |
| 8   | ATTR_EMBEDDING    | u64     | Pointer to embedding vector (if linked)  |
| 9   | ATTR_COUNT        | u32     | Generic count/statistic                  |
| 10  | ATTR_SCORE        | f32     | Computed score/ranking                   |
| 11–255 | Reserved/User   | varies  | User-defined attributes                  |

### 9.3 String Table

String attributes (names, labels) use an offset into the name table:

```
Name Table (at name_table_offset):

  ┌──────────────────────────────────────────────────────────┐
  │ string[0]: null-terminated UTF-8                        │
  │ string[1]: null-terminated UTF-8                        │
  │ ...                                                      │
  └──────────────────────────────────────────────────────────┘

  String attribute value = offset from name_table_offset start
  Example: ATTR_NAME value = 0x00 → first string in table
```

---

## 10. Interaction with Existing ISA

### 10.1 Composability with A2A Opcodes

Graph traversal results can be shared between agents for distributed
graph analysis:

```
  ; Agent A: traverse a subgraph and share results
  GRAPH_LOAD  r1, 0
  GRAPH_BFS_INIT  r2
  ; ... collect nodes into a buffer ...

  ; Send buffer to Agent B for further analysis
  TELL  r3, r4, r5             ; Send traversal results to agent r4

  ; Agent B: receive graph context
  ASK  r6, r3, r7              ; Request graph data from agent r3
  GRAPH_LOAD  r6, 0            ; Load received graph
```

### 10.2 Composability with Confidence Opcodes

Graph traversal confidence feeds into the confidence system:

```
  GRAPH_STEP  r3, r1, r2       ; r3 = neighbor, c[r3] set by edge weight
  C_THRESH  r3, 200            ; Skip low-confidence edges
  JZ  r3, skip_edge            ; Branch based on confidence
```

### 10.3 Composability with Embedding Extension

Node attributes can include embedding pointers, enabling combined
graph + vector search:

```
  ; Get node's embedding attribute
  GRAPH_NODE_ATTR  r3, r1, 8    ; r3 = ATTR_EMBEDDING pointer

  ; Load the embedding
  EMBEDDING_LOAD  ev0, 3        ; ev0 = node's embedding vector

  ; Search for similar nodes
  EMBEDDING_KNN  ev0, 10        ; Find 10 most similar embeddings
```

### 10.4 Composability with Memory Opcodes

Graph data can be manipulated using core memory operations:

```
  ; Allocate graph memory
  MALLOC  r1, r0, GRAPH_SIZE    ; r1 = graph buffer

  ; Build graph header
  MOVI16  r2, 0x47524146        ; Magic "GRAF"
  STOREOF  r2, r1, 0            ; Write magic to header
  ; ... fill in rest of header ...

  ; Load and traverse
  GRAPH_LOAD  r1, 0
```

### 10.5 Memory Ordering

| Operation          | Memory Ordering Requirement  |
|--------------------|------------------------------|
| GRAPH_LOAD         | Load-load ordering           |
| GRAPH_STEP         | Load-load ordering           |
| GRAPH_BFS_NEXT     | Load-load ordering (read-only)|
| GRAPH_QUERY        | Load-load ordering           |
| GRAPH_NODE_ATTR    | Load ordering                |

---

## 11. Error Handling & Trap Codes

### 11.1 Trap Code Allocation

Graph trap codes are allocated in the range `0xF0–0xFF`:

| Trap Code | Name                       | Severity | Description                              |
|-----------|----------------------------|----------|------------------------------------------|
| 0xF0      | TRAP_GRAPH_NOT_LOADED      | RECOVER  | No graph loaded in context               |
| 0xF1      | TRAP_GRAPH_CORRUPT         | FATAL    | Invalid magic or header checksum         |
| 0xF2      | TRAP_GRAPH_VERSION         | FATAL    | Unsupported graph format version         |
| 0xF3      | TRAP_GRAPH_NODE_NOT_FOUND  | RECOVER  | Referenced node does not exist           |
| 0xF4      | TRAP_GRAPH_EDGE_OUT_OF_RANGE| RECOVER | Edge index exceeds node degree           |
| 0xF5      | TRAP_GRAPH_INVALID_MODE    | RECOVER  | Operation invalid for current traversal  |
| 0xF6      | TRAP_GRAPH_ALREADY_LOADED  | RECOVER  | Cannot load graph without UNLOAD first   |
| 0xF7      | TRAP_GRAPH_QUERY_FAILED    | RECOVER  | Pattern query failed or timed out        |
| 0xF8      | TRAP_GRAPH_DEPTH_EXCEEDED  | RECOVER  | Traversal exceeded max depth             |
| 0xF9      | TRAP_GRAPH_ATTR_NOT_FOUND  | RECOVER  | Requested attribute does not exist       |
| 0xFA      | TRAP_GRAPH_CYCLE_DETECTED  | RECOVER  | Cycle found in DAG-only operation        |
| 0xFB–0xFF  | Reserved                   | —        | Reserved for future use                  |

---

## 12. Performance Considerations

### 12.1 Complexity Analysis

| Operation          | Time Complexity           | Space Complexity     |
|--------------------|---------------------------|----------------------|
| GRAPH_LOAD         | O(1)                      | O(1)                 |
| GRAPH_STEP         | O(degree)                 | O(1)                 |
| GRAPH_BFS_INIT     | O(1)                      | O(1)                 |
| GRAPH_BFS_NEXT     | O(degree) amortized       | O(V) for visited set |
| GRAPH_DFS_INIT     | O(1)                      | O(1)                 |
| GRAPH_DFS_NEXT     | O(degree) amortized       | O(V) for visited set |
| GRAPH_QUERY (path) | O(V + E)                  | O(V) for BFS         |
| GRAPH_QUERY (pat)  | O(V^k) worst case         | O(results)           |
| GRAPH_DEGREE       | O(1)                      | O(1)                 |
| GRAPH_NODE_ATTR    | O(attrs)                  | O(1)                 |

### 12.2 CSR Access Performance

CSR format provides O(1) degree lookup and efficient edge iteration:

```
  Edge iteration for node i:
    start = csr_index[i]
    end = csr_index[i + 1]
    for j in range(start, end):
        neighbor = edge_dst[j]
    # Total: degree(i) iterations

  Memory accesses per edge iteration: 2 reads (csr_index + edge_dst)
  Cache-friendly: edges for node i are contiguous in memory
```

### 12.3 Optimization Guidelines

1. **Use CSR format** for static graphs — best cache locality and O(1) operations.
2. **Use adjacency list** only for frequently modified graphs.
3. **Limit BFS/DFS depth** to prevent unbounded traversal on large graphs.
4. **Batch GRAPH_NODE_ATTR** calls when fetching multiple attributes.
5. **Pre-compute reverse CSR index** if in-degree queries are frequent.
6. **Use GRAPH_QUERY with BFS algorithm** for shortest paths (unweighted).

---

## 13. Bytecode Examples

### 13.1 Example 1: Social Graph — Friends-of-Friends

Find all friends-of-friends of a given user in a social network.

```
  ; =========================================================
  ; Example: Friends-of-friends in a social graph
  ; =========================================================

  ; Load social graph from memory
  MOVI16  r1, 0x100000         ; Graph base address
  GRAPH_LOAD  r1, 0            ; Auto-detect format (CSR)

  ; Set starting user (Alice = node 0)
  MOVI  r2, 0                  ; r2 = Alice's node ID
  GRAPH_BFS_INIT  r2           ; Start BFS from Alice

  ; BFS level 0 = Alice herself, level 1 = friends
  GRAPH_BFS_NEXT               ; r0 = Alice (level 0)
  ; Store Alice's ID
  STOREOF  r0, r10, 0          ; output[0] = Alice

  ; Get friends (level 1)
  GRAPH_BFS_NEXT               ; r0 = first friend (Bob)
  STOREOF  r0, r10, 4          ; output[1] = Bob
  GRAPH_BFS_NEXT               ; r0 = second friend (Carol)
  STOREOF  r0, r10, 8          ; output[2] = Carol

  ; Get friends-of-friends (level 2)
  GRAPH_BFS_NEXT               ; r0 = Dave (friend of Bob)
  STOREOF  r0, r10, 12         ; output[3] = Dave
  GRAPH_BFS_NEXT               ; r0 = Alice (friend of Carol, but visited)
  ; Alice is already visited, so BFS skips re-enqueuing her
  ; But she was already in queue before being visited
  GRAPH_BFS_NEXT               ; r0 = Dave (friend of Carol, but visited)

  ; Check if BFS is done
  GRAPH_BFS_NEXT               ; r0 = 0xFFFFFFFF (INVALID_NID)
  JNZ  r0, done                ; If not invalid, continue
  ; BFS complete — output contains Alice, friends, FoFs

done:
  GRAPH_UNLOAD
  HALT

  ; Byte sequence:
  ; 40 00 00 10    MOVI16 r0, 0x1000
  ; FF C0 00 00    GRAPH_LOAD r0, format=0
  ; 18 02 00       MOVI r2, 0
  ; FF C3 02       GRAPH_BFS_INIT r2
  ; FF C4          GRAPH_BFS_NEXT
  ; 49 00 0A 0000  STOREOF r0, r10, 0x0000
  ; FF C4          GRAPH_BFS_NEXT
  ; 49 00 0A 0004  STOREOF r0, r10, 0x0004
  ; ...
```

### 13.2 Example 2: Knowledge Graph — Multi-hop Query

Follow a chain of relationships in a knowledge graph: Person → WorksAt → Company → LocatedIn → City.

```
  ; =========================================================
  ; Example: Multi-hop knowledge graph traversal
  ; =========================================================

  ; Load knowledge graph
  MOVI16  r1, 0x200000
  GRAPH_LOAD  r1, 0

  ; Start from a person node
  MOVI  r2, 42                 ; Person ID = 42

  ; Hop 1: Person → WorksAt → Company
  GRAPH_SET_CURRENT  r2
  ; Step to company via "works_at" edge (assume edge type encoded in edge index)
  GRAPH_STEP  r3, 0xFFFF, 1    ; r3 = company node (1st edge)

  ; Hop 2: Company → LocatedIn → City
  GRAPH_SET_CURRENT  r3
  GRAPH_STEP  r4, 0xFFFF, 1    ; r4 = city node (1st edge)

  ; Get city name attribute
  MOVI  r5, 1                  ; ATTR_NAME = 1
  GRAPH_NODE_ATTR  r6, r4, r5  ; r6 = name string offset

  ; Use the city name for downstream processing
  ; r6 now contains the string table offset for the city name
  LOADOFF  r7, r1, r6          ; r7 = actual string bytes (simplified)

  GRAPH_UNLOAD
  HALT
```

### 13.3 Example 3: Dependency Graph — Cycle Detection

Detect cycles in a software dependency graph using DFS.

```
  ; =========================================================
  ; Example: Cycle detection in dependency graph
  ; =========================================================

  ; Load dependency graph
  MOVI16  r1, 0x300000
  GRAPH_LOAD  r1, 0

  ; Check graph info
  GRAPH_INFO                    ; r0 = num_nodes

  ; DFS from each unvisited node
  MOVI  r5, 0                  ; r5 = starting node index

outer_loop:
  ; Check if we've visited all nodes
  CMP_LT  r6, r5, r0           ; r6 = (r5 < num_nodes)
  JZ  r6, no_cycles            ; If r5 >= num_nodes, done

  ; Initialize DFS from node r5
  GRAPH_RESET                  ; Clear visited sets
  GRAPH_DFS_INIT  r5

dfs_loop:
  GRAPH_DFS_NEXT               ; r0 = next DFS node
  CMP_EQ  r6, r0, 0xFFFF       ; r6 = (r0 == INVALID)
  JNZ  r6, no_cycle_found      ; DFS complete, no cycle from r5

  ; Check depth — if depth > num_nodes, there's a cycle
  GRAPH_INFO
  CMP_GT  r6, r7, r0           ; r6 = (depth > num_nodes)
  JNZ  r6, cycle_found         ; Cycle detected!

  JMP  dfs_loop

no_cycle_found:
  INC  r5                      ; Try next starting node
  JMP  outer_loop

no_cycles:
  MOVI  r10, 0                 ; No cycles found
  HALT

cycle_found:
  MOVI  r10, 1                 ; Cycle detected
  ; r7 contains the traversal depth where cycle was found
  HALT
```

### 13.4 Example 3: Dependency Graph — Topological Sort

Compute a topological ordering of a DAG.

```
  ; =========================================================
  ; Example: Topological sort of a DAG
  ; =========================================================

  MOVI16  r1, 0x300000         ; DAG base address
  GRAPH_LOAD  r1, 0
  GRAPH_INFO                    ; r0 = num_nodes

  ; Initialize BFS from all zero-in-degree nodes
  ; (In practice, use a dedicated topo-sort query)
  ; Simplified: use BFS and collect order

  MOVI  r8, 0                  ; r8 = output index
  MOVI  r9, 0                  ; r9 = current node

topo_loop:
  ; Find a node with zero unvisited in-neighbors
  ; (simplified: just do BFS from node 0)
  CMP_LT  r6, r9, r0           ; r9 < num_nodes?
  JZ  r6, topo_done            ; Done

  GRAPH_DFS_INIT  r9           ; DFS from current node

dfs_collect:
  GRAPH_DFS_NEXT               ; r0 = next node
  CMP_EQ  r6, r0, 0xFFFF
  JNZ  r6, topo_next_start     ; DFS done

  ; Store node in output array
  STOREOF  r0, r10, 0          ; output[r8] = r0
  ADDI16  r10, 4               ; Advance output pointer
  INC  r8

  JMP  dfs_collect

topo_next_start:
  INC  r9
  JMP  topo_loop

topo_done:
  ; r8 = number of nodes in topological order
  GRAPH_UNLOAD
  HALT
```

### 13.5 Example 4: Shortest Path Query

Find the shortest path between two nodes using the query opcode.

```
  ; =========================================================
  ; Example: Shortest path between two nodes
  ; =========================================================

  ; Load graph
  MOVI16  r1, 0x400000
  GRAPH_LOAD  r1, 0

  ; Set up path query descriptor
  MALLOC  r2, r0, 20           ; Allocate query descriptor

  ; Write query: source=10, target=50, max_depth=100, algo=BFS
  MOVI  r3, 10                 ; Source node
  STOREOF  r3, r2, 0           ; query.source = 10
  MOVI  r3, 50                 ; Target node
  STOREOF  r3, r2, 4           ; query.target = 50
  MOVI16  r3, 100              ; Max depth
  STOREOF  r3, r2, 8           ; query.max_depth = 100
  MOVI  r3, 0                  ; Algorithm = BFS shortest
  STOREOF  r3, r2, 12          ; query.algorithm = 0

  ; Execute path query
  ; GRAPH_QUERY with query_type=0 (PATH), options=1 (full path)
  GRAPH_QUERY  r2, 0x10        ; type=0, options=1 (return full path)

  ; Read result
  ; r0 points to result buffer (set by GRAPH_QUERY)
  LOADOFF  r3, r0, 0           ; r3 = path_length
  LOADOFF  r4, r0, 4           ; r4 = total_weight

  ; Iterate path nodes
  MOVI  r5, 8                  ; Start of path_nodes array
  MOVI  r6, 0                  ; Index

path_print:
  CMP_LT  r7, r6, r3           ; r6 < path_length?
  JZ  r7, path_done

  LOADOFF  r8, r0, r5          ; r8 = path_nodes[r6]
  ; ... process node r8 ...

  ADDI16  r5, 4                ; Advance to next path node
  INC  r6
  JMP  path_print

path_done:
  ; Check confidence of path (decreases with length)
  C_THRESH  r4, 100            ; Check if path weight is acceptable
  JZ  r4, no_path              ; Path too long/heavy

  GRAPH_UNLOAD
  HALT
```

### 13.6 Example 5: Community Detection (Simple)

Find all nodes reachable within 2 hops (community/neighborhood).

```
  ; =========================================================
  ; Example: Neighborhood/community detection
  ; =========================================================

  MOVI16  r1, 0x500000
  GRAPH_LOAD  r1, 0

  ; Set up neighborhood query
  MALLOC  r2, r0, 8            ; Query descriptor
  MOVI  r3, 100                ; Center node
  STOREOF  r3, r2, 0           ; query.center = 100
  MOVI16  r3, 2                ; Radius = 2 hops
  STOREOF  r3, r2, 4           ; query.radius = 2

  ; Execute neighborhood query (type=1)
  GRAPH_QUERY  r2, 0x10        ; type=1 (NEIGHBORHOOD)

  ; r0 = pointer to neighbor results
  LOADOFF  r3, r0, 0           ; r3 = neighbor_count
  ; neighbors[] follow at offset 4

  MOVI  r4, 4                  ; Start of neighbor array
  MOVI  r5, 0                  ; Index

neighbor_loop:
  CMP_LT  r6, r5, r3
  JZ  r6, neighbors_done

  LOADOFF  r7, r0, r4          ; r7 = neighbor_id
  ; Process neighbor...

  ADDI16  r4, 4
  INC  r5
  JMP  neighbor_loop

neighbors_done:
  GRAPH_UNLOAD
  HALT
```

---

## 14. Formal Semantics

### 14.1 Extended Machine State

```
  σ' = (σ, gctx)

  where gctx = {
      graph_addr: u64,
      current_node: NID,
      traversal_mode: {INACTIVE, STEP, BFS, DFS},
      bfs_queue: Queue[NID],
      bfs_visited: Set[NID],
      dfs_stack: Stack[(NID, u32)],
      dfs_visited: Set[NID],
      traversal_depth: u32,
      iter_count: u64,
  }
```

### 14.2 GRAPH_STEP Rule

```
  Rule: GRAPH_STEP

  Precondition:
    gctx.graph_addr ≠ 0
    source = r[rs1] (or gctx.current_node if r[rs1] = INVALID)
    source exists in graph
    degree(source) > 0

  Effect:
    if rs2 == RANDOM_EDGE:
        edge = random_choice(edges(source))
    elif rs2 == FIRST_UNVISITED:
        edge = first(e ∈ edges(source) | dest(e) ∉ visited)
    else:
        edge = edges(source)[rs2 - 1]

    r[rd] = dest(edge)
    gctx.current_node = dest(edge)
    gctx.traversal_depth += 1
    gctx.iter_count += 1
    σ.pc += 5
```

### 14.3 GRAPH_BFS_NEXT Rule

```
  Rule: GRAPH_BFS_NEXT (non-empty queue)

  Precondition:
    gctx.traversal_mode = BFS
    |gctx.bfs_queue| > 0

  Effect:
    current = gctx.bfs_queue.dequeue()
    gctx.current_node = current

    for each neighbor n of current:
        if n ∉ gctx.bfs_visited:
            gctx.bfs_visited.add(n)
            gctx.bfs_queue.enqueue(n)

    r0 = current
    c[r0] = 1.0
    gctx.iter_count += 1
    σ.pc += 2
```

### 14.4 Invariant: Traversal Consistency

```
  Invariant: BFS Visited Set Consistency

  During MODE_BFS:
    ∀ node n ∈ gctx.bfs_visited:
      n was dequeued from gctx.bfs_queue OR
      n is currently in gctx.bfs_queue

  Invariant: DFS Stack Consistency

  During MODE_DFS:
    ∀ (node, idx) ∈ gctx.dfs_stack:
      node ∈ gctx.dfs_visited
      idx ≤ degree(node)
    gctx.dfs_stack is non-empty ⟹ MODE_DFS
    gctx.dfs_stack is empty ⟹ MODE_INACTIVE
```

---

## 15. Appendix

### 15.1 Opcode Quick Reference

| Hex     | Assembly                     | Description                    |
|---------|------------------------------|--------------------------------|
| FF C0   | GRAPH_LOAD rd, fmt           | Load graph from memory         |
| FF C1   | GRAPH_UNLOAD                 | Release graph context          |
| FF C2   | GRAPH_STEP rd, src, edge     | Traverse one edge              |
| FF C3   | GRAPH_BFS_INIT rd            | Initialize BFS                 |
| FF C4   | GRAPH_BFS_NEXT               | Next BFS node → r0             |
| FF C5   | GRAPH_DFS_INIT rd            | Initialize DFS                 |
| FF C6   | GRAPH_DFS_NEXT               | Next DFS node → r0             |
| FF C7   | GRAPH_QUERY rd, type         | Pattern-match query            |
| FF C8   | GRAPH_NODE_ATTR rd, node, key| Get node attribute             |
| FF C9   | GRAPH_EDGE_ATTR rd, dst, key | Get edge attribute             |
| FF CA   | GRAPH_DEGREE rd, node, type  | Compute degree                 |
| FF CB   | GRAPH_PATH rd, src, dst      | Shortest path                  |
| FF CC   | GRAPH_NEIGHBORS rd, node, buf| Get all neighbors              |
| FF CD   | GRAPH_SET_CURRENT rd         | Set current node               |
| FF CE   | GRAPH_INFO                   | Query graph metadata           |
| FF CF   | GRAPH_RESET                  | Reset traversal state          |

### 15.2 Graph Format Flags

| Bit | Name          | Description                    |
|-----|---------------|--------------------------------|
| 0   | DIRECTED      | Graph has directed edges       |
| 1   | WEIGHTED      | Edges have float32 weights     |
| 2   | NODE_ATTRS    | Nodes have attribute tables    |
| 3   | EDGE_ATTRS    | Edges have attribute tables    |
| 4   | SORTED        | Edges sorted by destination ID |
| 5   | NORMALIZED    | CSR index pre-computed         |
| 6–15| Reserved      | Reserved for future use        |

### 15.3 Extension Manifest Entry

```
  ext_id:            0x00000007
  ext_version_major: 1
  ext_version_minor: 0
  ext_name:          "org.flux.graph"
  ext_name_len:      15
  opcode_base:       0xFFC0
  opcode_count:      16
  required:          0  (optional)
  format_table:
    offset 0x00  format D   GRAPH_LOAD
    offset 0x01  format A   GRAPH_UNLOAD
    offset 0x02  format E   GRAPH_STEP
    offset 0x03  format B   GRAPH_BFS_INIT
    offset 0x04  format A   GRAPH_BFS_NEXT
    offset 0x05  format B   GRAPH_DFS_INIT
    offset 0x06  format A   GRAPH_DFS_NEXT
    offset 0x07  format D   GRAPH_QUERY
    offset 0x08  format E   GRAPH_NODE_ATTR
    offset 0x09  format E   GRAPH_EDGE_ATTR
    offset 0x0A  format E   GRAPH_DEGREE
    offset 0x0B  format E   GRAPH_PATH
    offset 0x0C  format E   GRAPH_NEIGHBORS
    offset 0x0D  format B   GRAPH_SET_CURRENT
    offset 0x0E  format A   GRAPH_INFO
    offset 0x0F  format A   GRAPH_RESET
```

### 15.4 Revision History

| Version | Date       | Author   | Changes                              |
|---------|------------|----------|--------------------------------------|
| 1.0     | 2026-04-12 | Super Z  | Initial specification (GRAPH-001)    |

---

*End of FLUX ISA v3 Graph Traversal Extension Specification (GRAPH-001)*
