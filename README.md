# FLUX: Fluid Language Universal eXecution

**A Self-Assembling, Self-Improving Runtime — The DJ Booth for Agent Code**

FLUX is not just a compiler or a VM. It's a living system that writes, optimizes, recompiles, and improves its own code — all while running. Think of it as the evolution from orchestra (rigid, top-down) through folk (expressive), jazz (improvisational), rock (powerful), to DJ/rave (layered, adaptive, self-evolving).

## The Philosophy

> **An orchestra** plays from a fixed score — that's a traditional compiler.
> **Folk musicians** change the arrangement every night — that's hot reload.
> **Jazz ensembles** improvise based on what they hear — that's adaptive optimization.
> **Rock bands** push the speakers to the limit — that's the profiler finding bottlenecks.
> **A DJ at a rave** layers samples, reads the room, swaps tracks mid-set, and the system gets better every minute — that's FLUX.

FLUX treats agents as first-class citizens. Agents write structured markdown containing polyglot code blocks — mixing C, Rust, Python, or any language line by line — and the FLUX compiler weaves them into a single optimized, verifiable bytecode. Then the system profiles itself, discovers hot patterns, recompiles bottleneck modules to faster languages, and evolves — all while the music never stops.

## Architecture — The Full Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  SYNTHESIS — FluxSynthesizer (the DJ booth)                    │
│  Wires ALL subsystems: modules, profiler, selector,            │
│  tiles, evolution, hot-reload, system reports                  │
├─────────────────────────────────────────────────────────────────┤
│  MODULES — 8-Level Fractal Hierarchy (TRAIN → CARD)            │
│  Nested containers, atomic hot-reload at any granularity,      │
│  namespace isolation, SHA-256 checksum trees                   │
├──────────────────────────┬──────────────────────────────────────┤
│  ADAPTIVE                │  EVOLUTION                           │
│  Profiler (heat map)     │  Genome (system DNA snapshots)       │
│  Selector (language rec) │  PatternMiner (hot sequence mining)  │
│  CompilerBridge (recomp) │  SystemMutator (proposes changes)    │
│                          │  CorrectnessValidator (no regressions)│
│                          │  EvolutionEngine (the main loop)     │
├──────────────────────────┼──────────────────────────────────────┤
│  TILES — 35 built-in composable computation patterns            │
│  COMPUTE (8): map, reduce, scan, filter, zip, flatmap, sort, unique  │
│  MEMORY (6): gather, scatter, stream, copy, fill, transpose     │
│  CONTROL (6): loop, while, branch, switch, fuse, pipeline      │
│  A2A (6): tell, ask, broadcast, a2a_reduce, a2a_scatter, barrier │
│  EFFECT (3): print, log, state_mut                              │
│  TRANSFORM (6): cast, reshape, pack, unpack, join, split       │
├─────────────────────────────────────────────────────────────────┤
│  L5  Agent Runtime (trust, scheduling, resources)               │
├─────────────────────────────────────────────────────────────────┤
│  L4  A2A Protocol (SEND, ASK, TELL, DELEGATE...)                │
├─────────────────────────────────────────────────────────────────┤
│  L3  FLUX Bytecode (compact binary, 104 opcodes)                │
├─────────────────────────────────────────────────────────────────┤
│  L2  FIR — Flux IR (universal SSA-form IR)                     │
├─────────────────────────────────────────────────────────────────┤
│  L1  Frontend Pass (C/Python/Rust → FIR)                       │
├─────────────────────────────────────────────────────────────────┤
│  L0  FLUX.MD (structured markdown, agent source)                │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

- **Polyglot compilation** — Write in any language, mix freely, compile to a single binary
- **Zero-overhead cross-language calls** — Polyglot ABI with region-qualified pointers
- **Native A2A opcodes** — 32 bytecode instructions for agent-to-agent communication
- **5-tier execution** — Interpreter → Baseline JIT → Optimizing JIT → AOT → Silicon
- **8-level fractal hot-reload** — Swap code at any granularity from TRAIN (whole app) to CARD (single function) without stopping
- **Adaptive language selection** — The profiler listens; the selector chooses: COOL→Python, WARM→TypeScript, HOT→Rust, HEAT→C+SIMD
- **35 composable tiles** — Reusable computation patterns that can be chained, nested, parallelized, and hot-swapped
- **Self-evolution engine** — The system profiles itself, discovers hot patterns, generates improved tiles, recompiles modules, validates correctness, and tracks improvement across generations
- **6-dimension trust engine** — History, capability, latency, consistency, determinism, audit
- **Capability-based security** — Hierarchical tokens, resource limits, hardware sandbox mode
- **Linear region memory** — Ownership-based, zero-GC, zero-fragmentation

## Quick Start

### The Self-Improving Demo (recommended)

```bash
cd flux-repo
PYTHONPATH=src python3 -m flux.synthesis.demo
```

This demonstrates the entire system: loading nested modules, profiling execution, classifying heat levels, running the evolution engine, showing language upgrades, and hot-reloading a card mid-set.

### The Synthesizer API

```python
from flux.synthesis import FluxSynthesizer

synth = FluxSynthesizer("my_app")

# Load modules at different nesting levels
synth.load_module("audio/input", source, language="python")
synth.load_module("audio/dsp/filter", source, language="python")
synth.load_module("audio/dsp/reverb", source, language="python")

# Profile a workload
synth.record_call("my_app.audio.dsp.filter", duration_ns=50000, calls=100)
synth.record_call("my_app.audio.dsp.reverb", duration_ns=80000, calls=100)

# See the heat map: filter is HEAT, reverb is HOT
print(synth.get_heatmap())
# {'my_app.audio.dsp.filter': 'HEAT', 'my_app.audio.dsp.reverb': 'HOT', ...}

# Get language recommendations
for path, rec in synth.get_recommendations().items():
    if rec.should_change:
        print(f"  {path}: {rec.current_language} → {rec.recommended_language}")

# Run self-evolution for 5 generations
report = synth.evolve(generations=5)
print(f"Fitness: {report.initial_fitness:.4f} → {report.final_fitness:.4f}")

# Hot-reload a single card without affecting others
synth.hot_swap("audio/dsp/filter", "def improved_filter(s): return [x*2 for x in s]")

# Generate full system report
print(synth.get_system_report().to_text())
```

### Full Pipeline (FLUX.MD → VM)

```python
from flux.pipeline import FluxPipeline

pipeline = FluxPipeline(optimize=True, execute=False)
result = pipeline.run("""
---
title: My Module
---

```c
int add(int a, int b) {
    return a + b;
}
```
""", lang="md")

print(f"Success: {result.success}")
print(f"Functions: {list(result.module.functions.keys())}")
print(f"Bytecode: {len(result.bytecode)} bytes")
```

### Polyglot Compilation (C + Python)

```python
from flux.pipeline import PolyglotCompiler, PolyglotSource

compiler = PolyglotCompiler()
result = compiler.compile([
    PolyglotSource(lang="c", source="int mul(int a, int b) { return a * b; }"),
    PolyglotSource(lang="python", source="def add(a, b):\n    return a + b\n"),
])
print(f"Functions: {list(result.module.functions.keys())}")
```

### VM Execution

```python
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op

bytecode = bytes([
    Op.MOVI, 0x01, 10, 0x00,
    Op.MOVI, 0x02, 20, 0x00,
    Op.IADD, 0x00, 0x01, 0x02,
    Op.HALT,
])
interp = Interpreter(bytecode)
interp.execute()
print(f"R0 = {interp.regs.read_gp(0)}")  # 30
```

## Layer-by-Layer Breakdown

### Synthesis Layer (`src/flux/synthesis/`)
The top-level integration layer — the DJ booth that wires everything together.

- **FluxSynthesizer**: The main orchestrator — manages modules, profiling, language selection, tile composition, evolution, and hot-reload
- **SystemReport**: Comprehensive text/JSON report generator with 7 sections (overview, hierarchy, heatmap, languages, tiles, evolution, fitness trend)
- **Demo**: Runnable demo showing the system improving itself (`python -m flux.synthesis.demo`)

### Module System (`src/flux/modules/`)
8-level fractal hierarchy with independent hot-reloading at any granularity.

- **TRAIN → CARRIAGE → LUGGAGE → BAG → POCKET → WALLET → SLOT → CARD**
- **ModuleContainer**: Nestable container tree with SHA-256 checksum verification
- **ModuleCard**: Atomic hot-reloadable unit (source + compiled artifacts + version)
- **FractalReloader**: Hot-reload engine with cascade, strategy recommendations, and history
- **ModuleNamespace**: Parent-child scope chains with full isolation

### Adaptive Subsystem (`src/flux/adaptive/`)
Runtime profiling and dynamic language selection — like a DJ reading the room.

- **AdaptiveProfiler**: Classifies modules as FROZEN/COOL/WARM/HOT/HEAT using percentile-based thresholds
- **AdaptiveSelector**: Maps heat to language (COOL→Python, WARM→TypeScript, HOT→Rust, HEAT→C+SIMD) with reload penalty awareness
- **CompilerBridge**: Cross-language recompilation pipeline with SHA-256 content caching

### Tile System (`src/flux/tiles/`)
35 built-in composable computation patterns — the sample library.

- **6 categories**: COMPUTE, MEMORY, CONTROL, A2A, EFFECT, TRANSFORM
- **Tile**: Composable (chain, parallel, nest), parameterizable, FIR-emitting
- **TileGraph**: DAG composition with topological ordering and pattern matching
- **TileRegistry**: Fuzzy search, type filtering, alternative discovery, cost ranking

### Evolution Engine (`src/flux/evolution/`)
The system that builds a better version of itself — the self-improvement loop.

- **Genome**: System DNA snapshots (modules, tiles, languages, profiler data, optimization history)
- **PatternMiner**: Modified Apriori algorithm finds hot execution subsequences
- **SystemMutator**: 7 mutation strategies (RECOMPILE_LANGUAGE, FUSE_PATTERN, REPLACE_TILE, ADD_TILE, MERGE_TILES, SPLIT_TILE, INLINE_OPTIMIZATION)
- **CorrectnessValidator**: Test suite management, baseline capture, regression detection
- **EvolutionEngine**: Capture → Profile → Mine → Propose → Evaluate → Commit → Measure → Repeat

### L0: FLUX.MD Parser (`src/flux/parser/`)
- Structured markdown parser with YAML frontmatter, headings, code blocks, lists
- Code block classification: FluxCodeBlock, DataBlock, NativeBlock
- Agent directive extraction (`## agent:`, `## fn:`)

### L1: Frontend Compilers (`src/flux/frontend/`)
- **C Frontend**: Recursive descent parser → FIR (functions, if/else, while, for, arithmetic, comparison)
- **Python Frontend**: AST-based compiler → FIR (def, if/elif/else, while, for/range, calls, print)

### L2: FIR — Flux IR (`src/flux/fir/`)
- **Types**: 15 immutable types with TypeContext interning
- **Instructions**: 42 instruction types (arithmetic, bitwise, comparison, conversion, memory, control flow, A2A)
- **Blocks**: FIRBlock, FIRFunction, FIRModule with SSA form
- **Builder**: Ergonomic API for constructing FIR
- **Validator**: Structural invariant checking
- **Printer**: Human-readable IR output

### L3: Bytecode (`src/flux/bytecode/`)
- **Opcodes**: 104 opcodes (control flow, integer/float arithmetic, bitwise, comparison, stack, function, memory, type, SIMD, A2A protocol, system)
- **Encoder**: FIRModule → binary bytecode (18-byte header + type table + name pool + function table + code section)
- **Decoder**: Binary bytecode → DecodedModule with full instruction reconstruction
- **Validator**: Structural bytecode verification (register bounds, jump targets, terminators)

### L4: A2A Protocol (`src/flux/protocol/` + `src/flux/a2a/`)
- **Messages**: Typed envelopes (Request, Response, Event, Error) with UUID-based IDs
- **Channels**: DirectChannel (P2P), BroadcastChannel (one-to-many), TopicChannel (pub/sub)
- **Registry**: Capability-based agent routing with heartbeat expiry
- **Negotiation**: 4-step trust handshake (initiate → challenge → respond → accept/reject)
- **Serialization**: BinaryMessageCodec with 60-byte header, batch encode/decode

### L5: Runtime (`src/flux/runtime/`)
- **Agent**: Runtime agent wrapping VM interpreter with register access and lifecycle
- **AgentRuntime**: Orchestrator for multi-agent compilation, execution, and messaging
- **CLI**: compile/run/test subcommands with language inference

### Supporting Subsystems
- **Optimizer** (`src/flux/optimizer/`): ConstantFolding, DCE, InlineFunctions, configurable pipeline
- **JIT Compiler** (`src/flux/jit/`): Inlining, constant folding, LRU cache, execution tracing
- **Type System** (`src/flux/types/`): Bidirectional C/Python/Rust → FIR mapping, generics (TypeVar, Vec<T>, Option<T>)
- **Standard Library** (`src/flux/stdlib/`): Intrinsics, collections, math, strings, agent utilities
- **Security** (`src/flux/security/`): Capability tokens, resource limits, sandbox
- **Hot Reload** (`src/flux/reload/`): BEAM-inspired dual-version loading with rollback

## Test Suite

**907 tests** across 20 test files, all passing:

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_synthesis.py` | 54 | Synthesizer, modules, profiling, heatmap, recommendations, hot-reload, evolution, tiles, reports, full pipeline |
| `test_evolution.py` | 154 | Genome, pattern mining, mutator, validator, evolution engine, integration pipeline |
| `test_tiles.py` | 145 | Tile creation, ports, instantiation, composition, FIR emission, graph, registry, built-in tiles |
| `test_adaptive.py` | 99 | Profiler, heatmap, selector, language profiles, overrides, compiler bridge |
| `test_protocol.py` | 85 | Messages, channels, registry, negotiation, serialization |
| `test_type_unify.py` | 76 | C/Python/Rust types, coercion, unification, generics |
| `test_modules.py` | 72 | Granularity, containers, checksums, cards, reloader, namespace, serialization |
| `test_stdlib.py` | 66 | Intrinsics, collections, math, strings, agents |
| `test_jit.py` | 43 | JIT compiler, cache, tracing, optimization |
| `test_integration.py` | 14 | Full E2E pipeline, polyglot, A2A, VM, protocol, hot reload |
| `test_vm.py` | 25 | Interpreter, registers, memory, opcodes |
| `test_bytecode.py` | 12 | Encoder, decoder, validator, roundtrip |
| `test_parser.py` | 11 | Markdown parsing, AST nodes |
| `test_a2a.py` | 10 | Messages, transport, trust, coordinator |
| `test_security.py` | 6 | Capabilities, expiry, sandbox |
| `test_runtime.py` | 6 | Agent creation, compilation, execution |
| `test_fir.py` | 13 | Types, builder, validator, printer |
| `test_frontends.py` | 8 | C and Python frontend compilation |
| `test_optimizer.py` | 4 | Constant folding, DCE, inlining |
| `test_reload.py` | 3 | Hot loader, versioning, rollback |

## Build & Test

```bash
cd flux-repo

# Run all tests
PYTHONPATH=src python3 -m pytest tests/ -v

# Run synthesis/integration tests
PYTHONPATH=src python3 -m pytest tests/test_synthesis.py -v

# Run the demo
PYTHONPATH=src python3 -m flux.synthesis.demo
```

## File Structure

```
flux-repo/
├── src/flux/
│   ├── __init__.py                     # Package root (v0.1.0)
│   ├── cli.py                         # CLI entry point (compile/run/test)
│   ├── synthesis/                     # SYNTHESIS: Top-level integration layer
│   │   ├── __init__.py               # Exports: FluxSynthesizer, SystemReport
│   │   ├── synthesizer.py            # FluxSynthesizer — the DJ booth
│   │   ├── report.py                 # SystemReport — 7-section report generator
│   │   └── demo.py                   # Runnable demo (python -m flux.synthesis.demo)
│   ├── modules/                       # MODULES: 8-level fractal hierarchy
│   │   ├── granularity.py            # Granularity enum (TRAIN→CARD, 8 levels)
│   │   ├── card.py                   # ModuleCard — atomic hot-reloadable unit
│   │   ├── container.py              # ModuleContainer — nestable container tree
│   │   ├── reloader.py               # FractalReloader — cascade + strategy
│   │   └── namespace.py              # ModuleNamespace — parent-child isolation
│   ├── adaptive/                      # ADAPTIVE: Profiling + language selection
│   │   ├── profiler.py               # AdaptiveProfiler (FROZEN/COOL/WARM/HOT/HEAT)
│   │   ├── selector.py               # AdaptiveSelector (heat → language mapping)
│   │   └── compiler_bridge.py        # CompilerBridge (cross-language recompilation)
│   ├── tiles/                         # TILES: 35 composable computation patterns
│   │   ├── tile.py                   # Tile, TileInstance, CompositeTile, ParallelTile
│   │   ├── ports.py                  # TilePort, PortDirection, type compatibility
│   │   ├── library.py                # 35 built-in tiles across 6 categories
│   │   ├── graph.py                  # TileGraph — DAG composition + FIR compilation
│   │   └── registry.py               # TileRegistry — search, alternatives, ranking
│   ├── evolution/                     # EVOLUTION: Self-improvement engine
│   │   ├── genome.py                 # Genome — system DNA snapshots
│   │   ├── pattern_mining.py         # PatternMiner — hot sequence discovery
│   │   ├── mutator.py                # SystemMutator — 7 mutation strategies
│   │   ├── validator.py              # CorrectnessValidator — regression detection
│   │   └── evolution.py              # EvolutionEngine — the main loop
│   ├── parser/                        # L0: FLUX.MD parser
│   │   ├── nodes.py                  # AST node types (12 dataclasses)
│   │   └── parser.py                 # FluxMDParser class
│   ├── frontend/                      # L1: Language frontends
│   │   ├── c_frontend.py             # C → FIR compiler
│   │   └── python_frontend.py        # Python → FIR compiler
│   ├── fir/                           # L2: Flux IR
│   │   ├── types.py                  # 15 type classes + TypeContext
│   │   ├── values.py                 # SSA Value
│   │   ├── instructions.py           # 42 instruction classes
│   │   ├── blocks.py                 # FIRBlock, FIRFunction, FIRModule
│   │   ├── builder.py                # FIRBuilder
│   │   ├── validator.py              # FIRValidator
│   │   └── printer.py                # print_fir()
│   ├── bytecode/                      # L3: Bytecode
│   │   ├── opcodes.py                # 104-opcode IntEnum
│   │   ├── encoder.py                # FIRModule → bytes
│   │   ├── decoder.py                # bytes → DecodedModule
│   │   └── validator.py              # BytecodeValidator
│   ├── vm/                            # Micro-VM interpreter
│   │   ├── registers.py              # 64-register file (GP/FP/VEC)
│   │   ├── memory.py                 # MemoryRegion + MemoryManager
│   │   └── interpreter.py            # Fetch-decode-execute loop
│   ├── protocol/                      # L4: A2A Protocol
│   │   ├── message.py                # Typed message envelopes
│   │   ├── channel.py                # Direct/Broadcast/Topic channels
│   │   ├── registry.py               # Capability-based agent registry
│   │   ├── negotiation.py            # 4-step trust handshake
│   │   └── serialization.py          # BinaryMessageCodec
│   ├── a2a/                           # A2A primitives
│   │   ├── messages.py               # A2A message types
│   │   ├── transport.py              # Agent transport
│   │   ├── coordinator.py            # Agent coordination
│   │   └── trust.py                  # Trust engine
│   ├── runtime/                       # L5: Agent Runtime
│   │   ├── agent.py                  # Agent (wraps Interpreter)
│   │   └── agent_runtime.py          # AgentRuntime orchestrator
│   ├── optimizer/                     # Optimization passes
│   │   ├── passes.py                 # CF, DCE, Inline passes
│   │   └── pipeline.py               # OptimizationPipeline
│   ├── jit/                           # JIT compiler
│   │   ├── compiler.py               # JITCompiler
│   │   ├── cache.py                  # JITCache (LRU, SHA-256)
│   │   ├── tracing.py                # ExecutionTracer
│   │   └── ir_optimize.py            # IR-level optimizations
│   ├── types/                         # Type system
│   │   ├── unify.py                  # TypeUnifier (C/Python/Rust → FIR)
│   │   ├── compat.py                 # Type compatibility
│   │   └── generic.py                # GenericType, TypeVar, TypeScheme
│   ├── stdlib/                        # Standard library
│   │   ├── intrinsics.py             # print, assert, panic, sizeof, etc.
│   │   ├── collections.py            # List, Map, Set, Queue, Stack
│   │   ├── math.py                   # min, max, abs, clamp, lerp, sqrt
│   │   ├── strings.py                # concat, substring, split, etc.
│   │   └── agents.py                 # AgentRegistry, MessageQueue, Scheduler
│   ├── security/                      # Security
│   │   ├── capabilities.py           # Capability tokens
│   │   ├── resource_limits.py        # Resource monitoring
│   │   └── sandbox.py                # Sandbox lifecycle
│   ├── reload/                        # Hot code reload
│   │   └── hot_loader.py             # BEAM-inspired HotLoader
│   ├── compiler/                      # Unified compiler pipeline
│   │   └── pipeline.py               # FluxCompiler (C/Python/MD → bytecode)
│   └── pipeline/                      # E2E pipeline
│       ├── e2e.py                    # FluxPipeline + PipelineResult
│       ├── polyglot.py               # PolyglotCompiler + PolyglotSource
│       └── debug.py                  # PipelineDebugger + disassembler
├── tests/
│   ├── test_synthesis.py             # 54 tests — Integration layer
│   ├── test_evolution.py             # 154 tests — Evolution engine
│   ├── test_tiles.py                 # 145 tests — Tile system
│   ├── test_adaptive.py              # 99 tests — Adaptive subsystem
│   ├── test_protocol.py              # 85 tests — A2A protocol
│   ├── test_type_unify.py            # 76 tests — Type system
│   ├── test_modules.py               # 72 tests — Module system
│   ├── test_stdlib.py                # 66 tests — Standard library
│   ├── test_jit.py                   # 43 tests — JIT compiler
│   ├── test_integration.py           # 14 tests — E2E pipeline
│   ├── test_vm.py                    # 25 tests — VM interpreter
│   ├── test_bytecode.py              # 12 tests — Bytecode
│   ├── test_parser.py                # 11 tests — Parser
│   ├── test_a2a.py                   # 10 tests — A2A primitives
│   ├── test_security.py              # 6 tests — Security
│   ├── test_runtime.py               # 6 tests — Agent runtime
│   ├── test_fir.py                   # 13 tests — FIR
│   ├── test_frontends.py             # 8 tests — Frontends
│   ├── test_optimizer.py             # 4 tests — Optimizer
│   └── test_reload.py                # 3 tests — Hot reload
├── docs/
│   └── FLUX_Design_Specification.pdf
├── benchmarks/
│   └── benchmarks.py
├── worklog.md
├── README.md
└── LICENSE
```

## How to Extend

### Adding a New Tile

```python
from flux.tiles import Tile, TileType, TilePort, PortDirection
from flux.fir.types import TypeContext

ctx = TypeContext()

my_tile = Tile(
    name="my_custom_fft",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("signal", PortDirection.INPUT, ctx.f32)],
    outputs=[TilePort("spectrum", PortDirection.OUTPUT, ctx.f32)],
    params={"window_size": 1024, "sample_rate": 44100},
    cost_estimate=5.0,
    abstraction_level=4,
)

synth.register_tile(my_tile)
```

### Adding a New Language

```python
from flux.adaptive.selector import LanguageProfile, LANGUAGES

LANGUAGES["go"] = LanguageProfile(
    name="go",
    speed_tier=7,
    expressiveness_tier=7,
    modularity_tier=8,
    compile_time_tier=3,
    hot_reload_support=True,
    simd_support=False,
    memory_safety=True,
)
```

### Adding a New Optimization Pass

```python
from flux.optimizer.passes import OptimizationPass

class MyCustomPass(OptimizationPass):
    def run(self, module):
        # Transform the FIR module
        return changed_count
```

### Adding a New Mutation Strategy

```python
from flux.evolution.genome import MutationStrategy

MutationStrategy.CUSTOM_MUTATION = "custom_mutation"

# Then implement the handler in SystemMutator.propose_mutations()
```

## Documentation

- [FLUX Design Specification (PDF)](docs/FLUX_Design_Specification.pdf) — 24-page comprehensive technical specification

## Synthesis

FLUX integrates the best ideas from:

| Source | Contribution |
|--------|-------------|
| [nexus-runtime](https://github.com/SuperInstance/nexus-runtime) | Intent-to-bytecode pipeline, A2A opcodes, INCREMENTS trust engine, cycle-deterministic VM |
| [mask-locked-inference-chip](https://github.com/Lucineer/mask-locked-inference-chip) | Zero-software-stack philosophy, hardware-enforced security |
| GraalVM Truffle | Polyglot interop, multi-language type system |
| LLVM | SSA IR, optimization passes, JIT/AOT |
| WebAssembly | Compact binary, capability security, streaming compilation |
| BEAM VM (Erlang) | Zero-downtime hot code reload |
| Apache Arrow | Zero-copy cross-language data passing |

## License

MIT
