# Compiler Bootstrapping & Meta-Compilation in FLUX

**Research Document — Author: FLUX Research Agent**
**Date: 2025-07-09**
**Scope: Self-hosting, polyglot runtimes, incremental compilation, self-evolving bytecode**

---

## 0. Executive Summary

FLUX is a Python-based agent-first markdown-to-bytecode system. Its compilation
pipeline reads structured markdown (FLUX.MD), parses it into a tree of AST nodes,
lowers through a type-rich SSA intermediate representation (FIR), optimizes, and
emits a binary bytecode format that executes on a custom 64-register micro-VM.
The system also carries a self-evolution engine, a fractal module/container
hierarchy, a tile-based computation library, adaptive language selection, and an
agent-to-agent coordination layer.

This document investigates **five interlocking research questions** about FLUX's
future architecture — from bootstrapping the compiler in its own language, to
the theoretical limits of self-improving systems.

---

## 1. Compiler Bootstrap Path: "FLUX in FLUX"

### 1.1 The Current Compilation Chain

FLUX's pipeline, as implemented in `src/flux/pipeline/e2e.py::FluxPipeline`,
chains these stages:

```
FLUX.MD  -->  Parser (re-based)  -->  AST (LocatedNode tree)
    -->  Frontend (C or Python)  -->  FIRModule (SSA)
    -->  Optimizer passes  -->  BytecodeEncoder  -->  bytes
    -->  Interpreter (fetch-decode-execute VM)  -->  result
```

The FIR is the pivotal data structure.  Every frontend produces a `FIRModule`,
every optimization pass transforms a `FIRModule`, and the `BytecodeEncoder`
linearises a `FIRModule` into the binary format described in
`src/flux/bytecode/encoder.py`:

```
[Header 18B][Type Table][Name Pool][Function Table][Code Section]
```

The bytecode VM (`src/flux/vm/interpreter.py::Interpreter`) runs directly on
these bytes with a register file of 16 GP + 16 FP + 16 SIMD registers, a
downward-growing stack, and capability-based memory regions.

### 1.2 What "Self-Hosting" Means for FLUX

A self-hosted compiler would be a FLUX.MD document whose embedded code blocks,
when compiled through the pipeline, produce bytecode that *itself* can parse
FLUX.MD and emit FLUX bytecode.  Concretely, we need bytecode that can:

1. **Parse markdown** — recognise fenced code blocks, headings, frontmatter.
2. **Build FIR** — construct `FIRModule` objects with `FIRFunction`,
   `FIRBlock`, and typed `Value` nodes.
3. **Run optimisation passes** — constant folding, dead code elimination,
   inlining.
4. **Emit bytecode** — produce valid FLUX binary format.

This is a four-stage bootstrap chain:

```
Stage 0: Python FLUX (current) — trusted base
Stage 1: Write the FIR builder as FLUX.MD  -->  bytecode
Stage 2: Write the parser as FIR  -->  bytecode (parsed by Stage 1)
Stage 3: Write the optimiser as FIR  -->  bytecode (optimises Stage 2 output)
Stage 4: Write the encoder as FIR  -->  bytecode (encodes Stage 3 output)
```

### 1.3 Minimum Feature Set for Self-Hosting

Analysing the source, the following FIR capabilities are **required** for the
compiler to compile itself:

| Category | FIR Instructions Needed | Purpose |
|---|---|---|
| **Arithmetic** | `iadd`, `isub`, `imul`, `idiv`, `imod` | Source position arithmetic, checksums |
| **Comparison** | `ilt`, `igt`, `ieq`, `ine` | Regex-like matching, string comparison |
| **Bitwise** | `iand`, `ior`, `ixor`, `ishl`, `ishr` | Parsing flags, bitmask manipulation |
| **Memory** | `alloca`, `load`, `store`, `getelem`, `setelem` | String buffers, AST node storage |
| **Control** | `jump`, `branch`, `switch`, `call`, `return` | Loops, conditionals, recursion |
| **Conversion** | `zext`, `sext`, `trunc` | Width coercion for checksum hashing |
| **A2A** | `tell`, `ask` | Agent-based parallel compilation |

The VM currently implements a **subset** of this: the interpreter handles
integer and float arithmetic, comparison, bitwise ops, stack manipulation,
control flow, and memory load/store.  Notably missing from the *VM* (though
present in the FIR and opcode tables) are:

- `getfield` / `setfield` (struct field access — encoded but no VM handler)
- `getelem` / `setelem` (array element access — encoded but no VM handler)
- `memcpy` / `memset` (bulk memory — opcodes exist, no VM handler)
- A2A opcodes (`TELL`, `ASK`, `DELEGATE`, etc. — opcodes defined, no VM handler)
- SIMD vector ops (`VLOAD`, `VSTORE`, `VADD`, `VFMA` — opcodes defined, no VM handler)
- String operations (no native string type in the VM at all)

**Bootstrap gap analysis**: Before FLUX can self-host, the VM interpreter must
implement struct access, array indexing, bulk memory operations, and ideally
some form of string primitive.  The FIR already has all the necessary types
(`StructType`, `ArrayType`, `StringType`); the gap is purely in the execution
layer.

### 1.4 A Concrete Bootstrap Sketch

Here is what a Stage 1 bootstrap would look like — the FIR builder expressed
as a FLUX.MD document:

```markdown
---
name: flux_stage1
stage: bootstrap
version: 1
---

## fn: new_module(name: str) -> Module

```c
// This C function, compiled to FIR via CFrontendCompiler,
// constructs the in-VM representation of a FIRModule.
// It uses alloca + store to lay out the struct in memory,
// then returns a pointer to it.
Module new_module(const char* name) {
    Module m;
    m.name = name;
    m.functions = create_map();
    m.structs = create_map();
    return m;
}
```

## fn: emit_iadd(block: BlockRef, lhs: ValueRef, rhs: ValueRef) -> ValueRef

```c
ValueRef emit_iadd(BlockRef block, ValueRef lhs, ValueRef rhs) {
    Instruction instr;
    instr.opcode = OPCODE_IADD;
    instr.lhs = lhs;
    instr.rhs = rhs;
    block_append(block, instr);
    return make_value(next_id(), "add_result", lhs.type);
}
```
```

The key insight: **Stage 0 (Python) compiles Stage 1**.  Stage 1's bytecode
can then be fed to a C frontend to parse and compile Stage 2 source.  By
Stage 3, the system is compiling its own optimisation passes, and by Stage 4,
it emits its own bytecode.  At that point, the Python implementation is
optional.

### 1.5 The Trust Problem

Bootstrap introduces a fundamental trust question: how do we verify that the
self-hosted compiler produces *identical* bytecode to the Python reference?
This requires:

1. **Fixed-point verification**: compile the compiler with itself N times and
   check that `bytecode_N == bytecode_{N+1}` (similar to GHC's bootstrapping
   process).
2. **FIR round-trip**: encode FIR to bytecode, decode back, and verify
   structural equality (`BytecodeDecoder` + `FIRValidator`).
3. **Semantic equivalence**: run both the Python-compiled and self-compiled
   versions on the same test suite (907 existing tests provide a strong basis).

---

## 2. Multi-Language Runtime: The Polyglot Vision

### 2.1 Current State: FIR as the Lingua Franca

FLUX's `PolyglotCompiler` (`src/flux/pipeline/polyglot.py`) already compiles
mixed-language sources into a unified FIR module.  The `TypeUnifier` resolves
types across language boundaries.  The `CompilerBridge`
(`src/flux/adaptive/compiler_bridge.py`) manages cross-language recompilation
through the FIR pivot:

```
Python source --> PythonFrontendCompiler --> FIR --> BytecodeEncoder --> FLUX bytecode
C source      --> CFrontendCompiler      --> FIR --> BytecodeEncoder --> FLUX bytecode
```

The `AdaptiveSelector` (`src/flux/adaptive/selector.py`) profiles execution
and recommends language changes per module, using a heat-based algorithm:

| Heat Level | Recommendation | Rationale |
|---|---|---|
| FROZEN | Python | Never called — maximise expressiveness |
| COOL | Python | Rarely called — not worth compilation cost |
| WARM | TypeScript | Moderate — balance speed vs. compile time |
| HOT | Rust | Frequent — memory-safe speed |
| HEAT | C+SIMD | Bottleneck — raw throughput |

### 2.2 The Polyglot Runtime Architecture

For FLUX to hot-swap between Python/C/Rust implementations per module, the
runtime needs:

**Layer 1: FIR as universal contract.**  Every module, regardless of its
compiled language, presents the same FIR-level interface.  A function compiled
from C and a function compiled from Rust that share the same `FuncType`
signature are interchangeable at the FIR level.

**Layer 2: Language-specific backends.**  Each backend lowers FIR to its
native form:

```python
# Pseudocode for the backend registry
BACKENDS = {
    "python": PythonBackend,    # FIR --> CPython bytecode / eval()
    "c":      CBackend,         # FIR --> C source --> clang --> .so
    "rust":   RustBackend,      # FIR --> Rust source --> cargo --> .so
    "c_simd": CSIMDBackend,     # FIR --> C with intrinsics --> clang -O3 -mavx2
}
```

**Layer 3: FFI trampoline layer.**  When a Python-compiled module calls a
Rust-compiled module, the call crosses the FFI boundary.  The trampoline must:

1. Marshal arguments from the caller's ABI to the callee's ABI.
2. Execute the call.
3. Marshal the return value back.

For the FLUX VM's register-based calling convention (R0-R7 for args, R0 for
return value), the trampoline is relatively simple:

```c
// Trampoline: called from VM (C ABI) into a Rust-compiled module
// Arguments arrive in R0-R7, return value goes into R0
typedef int32_t (*flux_fn_ptr)(int32_t r0, int32_t r1, int32_t r2,
                                int32_t r3, int32_t r4, int32_t r5,
                                int32_t r6, int32_t r7);

int32_t call_rust_module(flux_fn_ptr rust_fn, int32_t* registers) {
    return rust_fn(registers[0], registers[1], registers[2],
                   registers[3], registers[4], registers[5],
                   registers[6], registers[7]);
}
```

### 2.3 Calling Conventions and ABI Boundaries

The FLUX register file (`src/flux/vm/registers.py`) defines a 64-register
ABI with special-purpose registers:

| Register | Alias | Purpose |
|---|---|---|
| R0-R7 | (args) | Function arguments |
| R0 | (return) | Function return value |
| R11 | SP | Stack pointer |
| R12 | Region ID | Memory region qualifier |
| R13 | Trust token | A2A trust level |
| R14 | FP | Frame pointer |
| R15 | LR | Link register (return address) |

When crossing language boundaries, we need ABI shims:

- **VM -> Python**: The Python backend exposes each FIR function as a Python
  callable.  The VM calls into Python via `ctypes` or the CPython C API,
  marshalling register values to Python objects.
- **VM -> C/Rust**: Compiled shared libraries export C-callable functions.
  The VM resolves function symbols at load time and calls through function
  pointers.  The register layout maps naturally to the System V AMD64 ABI
  (RDI, RSI, RDX, RCX, R8, R9 for the first 6 args).
- **Python -> C/Rust**: Direct `ctypes.cfunc` or `cffi` calls.  Type
  marshalling uses the `TypeUnifier` to ensure FFI-compatible types.
- **C <-> Rust**: The `extern "C"` convention.  FIR types map to C types
  (`IntType(32, True)` -> `int32_t`, `FloatType(64)` -> `double`).

### 2.4 Memory Safety Across Boundaries

The VM's `MemoryManager` uses capability-based regions with ownership
semantics.  When code crosses into a native language, two approaches exist:

1. **Shared-region FFI**: The native code receives a pointer into the VM's
   memory region.  The region's ownership/borrower list gates access.  This is
   fast but requires the native code to respect FLUX's memory discipline.

2. **Copy-in/copy-out**: Arguments are serialised into native memory, the
   native function runs, and results are serialised back.  This is safe but
   adds overhead proportional to data size.

The `CapabilityType` and `RegionType` in the FIR type system provide the
theoretical foundation for capability-safe FFI, but the current VM does not
enforce region boundaries at runtime.  Enforcing them would require adding
bounds checks to every `load`/`store` instruction in the interpreter.

---

## 3. Incremental Compilation: The Fractal Module Tree

### 3.1 The Module Hierarchy

FLUX organises code into a fractal container hierarchy
(`src/flux/modules/container.py`):

```
TRAIN -> CARRIAGE -> LUGGAGE -> BAG -> POCKET -> WALLET -> SLOT -> [CARDs]
```

Each `ModuleContainer` holds child containers and `ModuleCard` instances.
A `ModuleCard` is the atomic unit of hot-reloadable code — it holds source
text, a language tag, and caches compiled FIR and bytecode.

### 3.2 Checksum-Based Stale Detection

The container tree uses recursive SHA-256 checksums for change detection:

```python
def checksum_tree(self) -> str:
    h = hashlib.sha256()
    h.update(self.name.encode())
    for cname in sorted(self.cards.keys()):
        h.update(cname.encode())
        h.update(self.cards[cname].checksum.encode())
    for cname in sorted(self.children.keys()):
        h.update(self.children[cname].checksum_tree().encode())
    return h.hexdigest()[:16]
```

When a card's source changes, its checksum changes, which bubbles up through
the container tree.  The `find_stale()` method compares current checksums
against previously snapshot baselines to identify exactly what changed.

### 3.3 Recompilation Propagation

When one card changes, the question is: how far up the container tree does
recompilation need to propagate?  The answer depends on the dependency
structure:

**Case 1 — Pure leaf change**: A card at the bottom of the tree changes, and
no other card imports its exported symbols.  Only that card needs
recompilation.  The parent container's version bumps, but no other card's
bytecode is invalidated.

**Case 2 — Interface change**: A card changes its exported interface (e.g.,
function signature changes).  All cards in the same container that call the
changed function must be recompiled.  Whether sibling containers need
recompilation depends on whether they import from this container.

**Case 3 — Type change**: A card changes a struct definition that is used by
other cards.  This requires recompilation of all dependents, potentially
across container boundaries.

The current implementation invalidates the **entire subtree** on reload
(`_invalidate_subtree()` clears all compiled artifacts), which is correct but
conservative.  Fine-grained incremental compilation would require:

### 3.4 Fine-Grained Dependency Tracking

To avoid over-invalidation, FLUX needs a dependency graph:

```python
@dataclass
class DependencyEdge:
    source: str      # card/container path that defines something
    target: str      # card/container path that uses it
    kind: str        # "call", "type_use", "import", "struct_field"
    symbol: str      # the specific symbol being depended on
```

The dependency graph is built during FIR construction.  Each `Call`
instruction records which function it calls.  Each `Load`/`Store` through a
struct records which struct type it accesses.  When a card is recompiled:

1. Compute the set of **changed symbols** (diff the old and new FIR exports).
2. Query the dependency graph for all cards that use any changed symbol.
3. Recompile only those cards.
4. Recompute checksums up the container tree.
5. Re-encode bytecode only for the containers whose cards changed.

The `HotLoader` (`src/flux/reload/hot_loader.py`) already implements
BEAM-inspired dual-version loading: new bytecode versions coexist with old
versions until all active calls complete.  Combined with dependency tracking,
this gives us incremental hot-reload with zero downtime.

### 3.5 Incremental Bytecode Generation

The `BytecodeEncoder` currently re-encodes the entire module.  For
incremental updates, we can:

1. **Cache per-function bytecode**.  Each `FIRFunction` maps to a contiguous
   code section.  The function table records `(name_offset, entry_offset,
   code_size)` triples.  When only one function changes, re-encode only that
   function and patch the function table entry.

2. **Patch in-place**.  If the new function's bytecode is the same size as
   the old, we can overwrite the bytes in place without changing any offsets.
   If the size differs, we need to relocate subsequent functions — this is
   the same problem as incremental linking.

3. **Versioned code segments**.  Each function gets a version counter.
  The function table entry includes the version.  The VM resolves function
  calls through the table, so stale callers automatically get the new version
  on next call (after a memory barrier).

---

## 4. Self-Optimizing Bytecode

### 4.1 The Current Bytecode Format

FLUX bytecode is a linear, little-endian binary format with six instruction
encoding formats (A through G):

```
Format A (1B):  [opcode]
Format B (2B):  [opcode][reg:u8]
Format C (3B):  [opcode][rd:u8][rs1:u8]
Format D (4B):  [opcode][reg:u8][imm16:i16]
Format E (4B):  [opcode][rd:u8][rs1:u8][rs2:u8]
Format G (var): [opcode][len:u16][data:len bytes]
```

The opcode space is organised by category:

| Range | Category | Count |
|---|---|---|
| 0x00-0x07 | Control flow | 8 |
| 0x08-0x0F | Integer arithmetic | 8 |
| 0x10-0x17 | Bitwise | 8 |
| 0x18-0x1F | Comparison | 8 |
| 0x20-0x27 | Stack ops | 8 |
| 0x28-0x2F | Function ops | 8 |
| 0x30-0x37 | Memory management | 8 |
| 0x38-0x3F | Type ops | 8 |
| 0x40-0x4F | Float arithmetic + comparison | 16 |
| 0x50-0x5F | SIMD vector ops | 16 |
| 0x60-0x7F | A2A protocol | 28 |
| 0x80-0x9F | System | 4 |

Total defined: ~128 opcodes, with significant gaps (e.g., 0xA0-0xFF unused).

### 4.2 Versioned Instruction Sets

For the bytecode format to evolve, we need **version negotiation** between the
encoder and the VM.  The header already has a `version: uint16` field
(currently always 1) and a `flags: uint16` field (currently always 0).

A versioned instruction set protocol would work as follows:

```python
# Encoder side:
HEADER_VERSION = 2  # Introduces new opcodes
HEADER_FLAGS = 0x0001  # Bit 0: "extended memory ops present"

# VM side:
def negotiate_capabilities(self, header_version, header_flags):
    if header_version > self.max_supported_version:
        raise VMError(f"Bytecode version {header_version} not supported")
    if header_flags & 0x0001 and not self.has_extended_memory:
        raise VMError("Extended memory ops required but not available")
```

New opcodes can be added in the unused 0xA0-0xFF range.  The `flags` field
enables feature gating: if a bytecode module uses `GETFIELD` (0xA0, proposed),
the flags field signals this to the VM, which can either execute or reject.

### 4.3 Capability-Based Opcode Discovery

The current `BytecodeDecoder` treats unknown opcodes as NOPs:

```python
except ValueError:
    # Unknown opcode — treat as NOP-sized (1 byte)
    return DecodedInstruction(opcode=Op.NOP, operands=[raw_op], ...), offset + 1
```

A more robust approach is **capability discovery**:

1. The bytecode header includes a **capability bitmap** (e.g., a 32-byte
   bitfield where bit N indicates that opcode 0x80+N is used).
2. The VM checks its supported capability set against the bytecode's
   requirements before execution begins.
3. If a required capability is missing, the VM can either: (a) raise an
   error, or (b) call a **capability provider** — a registered handler that
   implements the missing opcode in software.

```python
class CapabilityProvider:
    """Provides implementations for opcodes not natively supported."""
    def __init__(self):
        self._handlers: dict[int, Callable] = {}

    def register(self, opcode: int, handler: Callable):
        self._handlers[opcode] = handler

    def try_handle(self, opcode: int, operands, vm_state) -> bool:
        handler = self._handlers.get(opcode)
        if handler:
            handler(operands, vm_state)
            return True
        return False
```

This enables a form of **runtime code patching**: a module can be compiled
against a newer opcode set, and an older VM can still execute it by loading
capability providers at runtime.

### 4.4 Runtime Code Patching

The self-evolution engine (`src/flux/evolution/evolution.py`) already
mutates the system's configuration (language assignments, tile compositions,
optimisation settings).  The next step is **bytecode-level mutation**:

1. **Opcode substitution**: Replace a sequence of bytecodes with an equivalent
   but faster sequence.  E.g., replace `MOVI R0, 0; IADD R1, R0, R2` with
   `MOV R1, R2` (constant folding applied at the bytecode level).

2. **Hot-patching**: The `HotLoader` already supports dual-version loading.
   A code-patching evolution step would:
   - Decode the current bytecode (`BytecodeDecoder`).
   - Apply the mutation at the FIR level (optimisation passes).
   - Re-encode (`BytecodeEncoder`).
   - Load the new version via `HotLoader.load()`.
   - Active calls on the old version continue; new calls use the patched version.

3. **Opcode extension**: If the evolution engine discovers that a new
   operation pattern is common (via `PatternMiner`), it can propose a new
   dedicated opcode.  The VM registers a `CapabilityProvider` for it, and
   future compilations emit the new opcode directly.

### 4.5 Self-Evolution's Current Reach and Limits

The `EvolutionEngine` currently mutates:

- **Language assignments** (`MutationStrategy.RECOMPILE_LANGUAGE`): changes a
  module's target language based on profiling heat.
- **Tile compositions** (`FUSE_PATTERN`, `MERGE_TILES`, `REPLACE_TILE`):
  rearranges the tile graph based on pattern mining.
- **Inline optimisation** (`INLINE_OPTIMIZATION`): proposes inlining for
  small, frequently-called functions.

What it **cannot yet** mutate:

- The FIR instruction set itself (no mechanism to add/remove FIR opcodes).
- The bytecode encoding format (hard-coded in `BytecodeEncoder`).
- The VM's execution semantics (hard-coded in `Interpreter._step()`).
- The optimisation pass pipeline (hard-coded in `OptimizationPipeline`).

Moving any of these into the mutable genome would be a significant step
toward true self-hosting, but also introduces the risk of **compilation
oscillation** — the system keeps mutating itself in a way that prevents
convergence.

---

## 5. Open Questions for Future Researchers

### 5.1 Engineering Problems (Solvable With Sufficient Effort)

**Q1: What is the minimum VM surface needed for self-hosting?**

The FIR already has struct access, array indexing, and string types.  The VM
needs handlers for `GETFIELD`, `SETFIELD`, `GETELEM`, `SETELEM`, `MEMCPY`,
`MEMSET`, and a basic string primitive (concat, compare, slice).  Estimate:
~500-800 lines of additional interpreter code.  This is purely an
engineering task.

**Q2: How do we verify bootstrap fixed-point convergence?**

The process is: compile the compiler with itself N times and check
`bytecode(N) == bytecode(N+1)`.  This requires (a) deterministic FIR
construction (no hash-map iteration order dependence), (b) deterministic
register allocation, and (c) deterministic encoding.  The current codebase
has some non-determinism (e.g., `dict` iteration in `FIRBuilder`) that would
need to be eliminated.

**Q3: What is the recompilation cost model for the polyglot runtime?**

The `AdaptiveSelector` uses heuristic heat levels with hardcoded language
profiles.  A rigorous cost model would account for: compilation time (C
compiles ~7x slower than Python), execution speedup (C runs ~30x faster for
compute-bound code), hot-reload frequency (recompiling C code on every change
is expensive), and memory overhead (JIT-compiled native code is ~10x larger
than bytecode).  Building this model requires benchmarking the actual
FLUX VM against native code on representative workloads.

**Q4: How does the FIR encode higher-order functions and closures?**

The current `Call` instruction takes a function name (string), not a function
value.  First-class functions would require a `CallIndirect` instruction that
takes a register containing a function pointer.  Closures require capturing
the environment — this can be done by bundling the function pointer with a
pointer to a heap-allocated environment struct.  The FIR's `FuncType` already
exists; the gap is in making functions first-class values.

### 5.2 Research Problems (Require Novel Ideas)

**Q5: Can the evolution engine safely modify its own optimisation passes?**

This is a **meta-optimisation** problem.  If the engine proposes a new
optimisation pass, how do we verify that it:
- Always preserves program semantics (correctness)?
- Never makes any program slower (monotonicity)?
- Terminates (doesn't loop forever trying to optimise)?

This is related to the **superoptimisation** problem (Schkufza et al., 2013)
and is widely regarded as hard.  Formal verification of optimisation passes
is an active research area.  A practical approach might be: generate
candidate passes, test them against the 907-test suite, and only accept passes
that never increase execution time on any test.

**Q6: What are the theoretical limits of self-improvement?**

Godel's incompleteness theorems imply that no sufficiently powerful system
can prove all true statements about itself.  Applied to FLUX: the system
cannot guarantee that its self-optimisations are correct without an external
oracle.  The `CorrectnessValidator` (`src/flux/evolution/validator.py`) uses
behavioural testing (capture baseline outputs, compare after mutation), which
is sound but incomplete — it can miss edge cases not covered by the test
suite.

This connects to the broader question of **AI safety in self-modifying
systems**.  FLUX's capability-based security model (`CapabilityType`,
`CapRequire` instruction) provides a foundation, but a self-modifying system
could theoretically grant itself capabilities it shouldn't have.  Formal
verification of the capability system under self-modification is an open
problem.

**Q7: How does incremental compilation interact with the self-evolution
engine?**

If the evolution engine changes a module's language (Python -> Rust), and
simultaneously a developer edits the module's source, we have a concurrent
modification problem.  The `HotLoader`'s versioning system handles this for
bytecode, but the evolution engine operates at a higher level (language
assignments, tile compositions).  We need a **transactional evolution**
mechanism that either commits all changes atomically or rolls back.

**Q8: Can the FIR representation itself evolve?**

Currently, the FIR instruction set is defined in Python
(`src/flux/fir/instructions.py`).  If FLUX were self-hosted, the FIR would
need to be defined *in FLUX* — a recursive definition.  This raises the
question: can the FIR represent its own instruction set?  The FIR has
`StructType` for named fields and `EnumType` for variants, so yes — the FIR
instruction set could be represented as FIR data.  But *interpreting* that
data to drive compilation requires a level of metaprogramming that the
current FIR does not support (no type-level computation, no macros, no
dependent types).

**Q9: What is the computational complexity of the tile composition search?**

The tile library (`src/flux/tiles/`) allows arbitrary composition of tiles
into `CompositeTile` and `ParallelTile` structures.  Finding the optimal tile
composition for a given computation is a search problem.  The evolution
engine uses greedy heuristics (propose fusions for hot patterns, replace
expensive tiles).  Whether this converges to a global optimum, and how fast,
depends on the structure of the tile composition lattice — which is not yet
well-characterised.

**Q10: How do we reconcile determinism with adaptive optimisation?**

The `AdaptiveSelector` makes non-deterministic decisions (different profiling
runs may produce different heat maps, leading to different language
assignments).  But the `Genome` is serialisable and reproducible.  If two
FLUX instances start from the same genome and run the same workloads, do they
converge to the same configuration?  This is an empirical question that
depends on the stochasticity of the profiling, pattern mining, and mutation
selection algorithms.  Formal convergence guarantees would require analysis
of the evolution engine as a stochastic optimisation process — similar to
convergence proofs for genetic algorithms.

---

## 6. Conclusion

FLUX's architecture — FIR-centric with a clean separation between parsing,
optimisation, and code generation — is well-suited for bootstrapping.  The
primary engineering gaps are:

1. **VM completeness**: implement struct, array, string, and A2A opcodes.
2. **Self-hosting FIR spec**: write the FIR builder/parser/encoder as FLUX.MD.
3. **Incremental dependency tracking**: build a symbol-level dependency graph.
4. **Polyglot FFI layer**: implement ABI shims for Python/C/Rust interop.
5. **Versioned bytecode**: add capability negotiation to the header format.

The research gaps are deeper:

- Safe self-modification of optimisation passes.
- Formal verification of capability security under evolution.
- Convergence guarantees for adaptive compilation.
- Metaprogramming in the FIR (self-representing instruction sets).

FLUX sits at an unusual intersection: it is both a **compilation toolchain**
and a **self-evolving agent runtime**.  Making it fully self-hosted would make
it one of the few systems that compiles, optimises, and evolves its own
implementation — a significant milestone in meta-compilation.

---

## Appendix A: Key Source Files Reference

| File | Purpose |
|---|---|
| `src/flux/fir/instructions.py` | All FIR instruction types (42 opcodes) |
| `src/flux/fir/builder.py` | FIR construction API (FIRBuilder) |
| `src/flux/fir/types.py` | Type system with 15 types + TypeContext interning |
| `src/flux/fir/blocks.py` | FIRModule, FIRFunction, FIRBlock |
| `src/flux/fir/validator.py` | Structural FIR validation |
| `src/flux/bytecode/opcodes.py` | 128 bytecode opcodes, 6 encoding formats |
| `src/flux/bytecode/encoder.py` | FIRModule -> FLUX binary bytecode |
| `src/flux/bytecode/decoder.py` | FLUX binary bytecode -> structured representation |
| `src/flux/vm/interpreter.py` | Fetch-decode-execute VM (~40 opcode handlers) |
| `src/flux/vm/registers.py` | 64-register file (16 GP + 16 FP + 16 SIMD) |
| `src/flux/vm/memory.py` | Capability-based linear memory regions |
| `src/flux/compiler/pipeline.py` | Multi-language compilation dispatcher |
| `src/flux/pipeline/e2e.py` | End-to-end pipeline (source -> execution) |
| `src/flux/pipeline/polyglot.py` | Mixed-language compilation with type unification |
| `src/flux/parser/parser.py` | FLUX.MD parser (re-based, no external deps) |
| `src/flux/parser/nodes.py` | AST node types (FluxModule, AgentDirective, etc.) |
| `src/flux/evolution/evolution.py` | Self-evolution loop (capture -> mutate -> commit) |
| `src/flux/evolution/genome.py` | System state snapshot (modules, tiles, profiler) |
| `src/flux/evolution/mutator.py` | Mutation proposal and evaluation |
| `src/flux/modules/container.py` | Fractal module hierarchy with checksum trees |
| `src/flux/modules/card.py` | Atomic hot-reloadable unit |
| `src/flux/adaptive/selector.py` | Heat-based language selection |
| `src/flux/adaptive/compiler_bridge.py` | Cross-language recompilation via FIR |
| `src/flux/reload/hot_loader.py` | BEAM-inspired dual-version loading |
| `src/flux/jit/compiler.py` | JIT compilation with register allocation |
| `src/flux/tiles/tile.py` | Tile, CompositeTile, ParallelTile |
| `src/flux/runtime/agent_runtime.py` | Agent orchestration (compile, execute, message) |
