# FLUX: Fluid Language Universal eXecution

**Agent-First Markdown-to-Bytecode System with Polyglot A2A Runtime**

FLUX redefines how autonomous AI agents produce, share, and execute code. It treats agents as first-class citizens and humans as optional abstractions. Agents write structured markdown containing polyglot code blocks — mixing C, Rust, Python, or any language line by line — and the FLUX compiler weaves them into a single optimized, verifiable bytecode with zero-overhead cross-language calls and native A2A communication primitives baked into the instruction set.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  L5  Agent Runtime (trust, scheduling, resources)   │
├─────────────────────────────────────────────────────┤
│  L4  A2A Protocol (SEND, ASK, TELL, DELEGATE...)    │
├─────────────────────────────────────────────────────┤
│  L3  FLUX Bytecode (compact binary, 104 opcodes)    │
├─────────────────────────────────────────────────────┤
│  L2  FIR — Flux IR (universal SSA-form IR)          │
├─────────────────────────────────────────────────────┤
│  L1  Frontend Pass (C/Python/Rust → FIR)            │
├─────────────────────────────────────────────────────┤
│  L0  FLUX.MD (structured markdown, agent source)    │
└─────────────────────────────────────────────────────┘
```

## Key Features

- **Polyglot compilation** — Write in any language, mix freely, compile to a single binary
- **Zero-overhead cross-language calls** — Polyglot ABI with region-qualified pointers
- **Native A2A opcodes** — 32 bytecode instructions for agent-to-agent communication
- **5-tier execution** — Interpreter → Baseline JIT → Optimizing JIT → AOT → Silicon
- **Hot code reload** — BEAM-inspired dual-version model with cross-language state migration
- **6-dimension trust engine** — History, capability, latency, consistency, determinism, audit
- **Capability-based security** — Hierarchical tokens, resource limits, hardware sandbox mode
- **Linear region memory** — Ownership-based, zero-GC, zero-fragmentation

## Quick Start

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

### Debug Pipeline

```python
from flux.pipeline import PipelineDebugger

debugger = PipelineDebugger()
report = debugger.run_pipeline("int square(int x) { return x * x; }", lang="c")
print(debugger.summary(report))
```

### Direct Compilation

```python
from flux.compiler.pipeline import FluxCompiler

compiler = FluxCompiler()
bytecode_c = compiler.compile_c("int add(int a, int b) { return a + b; }")
bytecode_py = compiler.compile_python("def add(a, b):\n    return a + b\n")
bytecode_md = compiler.compile_md("```c\nint main() { return 42; }\n```")
```

### VM Execution

```python
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op

# Build: MOVI R1,10; MOVI R2,20; IADD R0,R1,R2; HALT
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

### L0: FLUX.MD Parser (`src/flux/parser/`)
- Structured markdown parser with YAML frontmatter, headings, code blocks, lists
- Code block classification: FluxCodeBlock, DataBlock, NativeBlock
- Agent directive extraction (`## agent:`, `## fn:`)

### L1: Frontend Compilers (`src/flux/frontend/`)
- **C Frontend**: Recursive descent parser → FIR (functions, if/else, while, for, arithmetic, comparison)
- **Python Frontend**: AST-based compiler → FIR (def, if/elif/else, while, for/range, calls, print)

### L2: FIR — Flux IR (`src/flux/fir/`)
- **Types**: 15 immutable types with TypeContext interning (IntType, FloatType, BoolType, UnitType, StringType, RefType, ArrayType, VectorType, FuncType, StructType, EnumType, RegionType, CapabilityType, AgentType, TrustType)
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

### L4: A2A Protocol (`src/flux/protocol/`)
- **Messages**: Typed envelopes (Request, Response, Event, Error) with UUID-based IDs
- **Channels**: DirectChannel (P2P), BroadcastChannel (one-to-many), TopicChannel (pub/sub)
- **Registry**: Capability-based agent routing with heartbeat expiry
- **Negotiation**: 4-step trust handshake (initiate → challenge → respond → accept/reject)
- **Serialization**: BinaryMessageCodec with 60-byte header, batch encode/decode

### L5: Runtime (`src/flux/runtime/`)
- **Agent**: Runtime agent wrapping VM interpreter with register access and lifecycle
- **AgentRuntime**: Orchestrator for multi-agent compilation, execution, and messaging
- **CLI**: compile/run/test subcommands with language inference

### Optimizer (`src/flux/optimizer/`)
- ConstantFoldingPass, DeadCodeEliminationPass, InlineFunctionsPass
- Configurable OptimizationPipeline with fixed-point iteration

### JIT Compiler (`src/flux/jit/`)
- Function inlining, constant folding/propagation, dead code elimination
- JITCache with LRU eviction and SHA-256 keyed entries
- ExecutionTracer with block/call/edge profiling and hot path detection

### Type System (`src/flux/types/`)
- **TypeUnifier**: Bidirectional C/Python/Rust → FIR mapping, cross-language coercion costs, type unification (LUB)
- **Generic Types**: TypeVar, GenericType (Vec<T>, Map<K,V>, Option<T>), TypeScheme (∀ quantification)

### Standard Library (`src/flux/stdlib/`)
- **Intrinsics**: print, assert, panic, sizeof, alignof, type_of
- **Collections**: List, Map, Set, Queue, Stack with FIR struct layouts
- **Math**: min, max, abs, clamp, lerp, sqrt
- **Strings**: concat, substring, split, join, length, format
- **Agents**: AgentRegistry, MessageQueue, TaskScheduler

### Security (`src/flux/security/`)
- Capability tokens with expiry and derivation
- Resource monitoring and limits
- Sandbox lifecycle management

### Hot Reload (`src/flux/reload/`)
- BEAM-inspired dual-version loading
- Active call tracking with automatic GC
- Rollback support

### Pipeline (`src/flux/pipeline/`)
- **FluxPipeline**: End-to-end FLUX.MD → Parser → FIR → Optimizer → Bytecode → VM
- **PolyglotCompiler**: Multi-language compilation to unified bytecode with type unification
- **PipelineDebugger**: Step-by-step tracing, FIR pretty-printing, bytecode disassembly

## Test Suite

**383 tests** across 15 test files, all passing:

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_fir.py` | 13 | Types, builder, validator, printer |
| `test_parser.py` | 11 | Markdown parsing, AST nodes |
| `test_vm.py` | 25 | Interpreter, registers, memory, opcodes |
| `test_bytecode.py` | 12 | Encoder, decoder, validator, roundtrip |
| `test_a2a.py` | 10 | Messages, transport, trust, coordinator |
| `test_frontends.py` | 8 | C and Python frontend compilation |
| `test_optimizer.py` | 4 | Constant folding, DCE, inlining |
| `test_runtime.py` | 6 | Agent creation, compilation, execution |
| `test_stdlib.py` | 66 | Intrinsics, collections, math, strings, agents |
| `test_protocol.py` | 85 | Messages, channels, registry, negotiation, serialization |
| `test_jit.py` | 43 | JIT compiler, cache, tracing, optimization |
| `test_type_unify.py` | 76 | C/Python/Rust types, coercion, unification, generics |
| `test_security.py` | 6 | Capabilities, expiry, sandbox |
| `test_reload.py` | 3 | Hot loader, versioning, rollback |
| `test_integration.py` | 14 | Full E2E pipeline, polyglot, A2A, VM, protocol, hot reload |

## Build & Test

```bash
cd flux-repo

# Run all tests
python3 -m pytest tests/ -v

# Run integration tests only
python3 -m pytest tests/test_integration.py -v

# Run specific test file
python3 -m pytest tests/test_bytecode.py -v
```

## File Structure

```
flux-repo/
├── src/flux/
│   ├── __init__.py                 # Package root (v0.1.0)
│   ├── cli.py                     # CLI entry point (compile/run/test)
│   ├── parser/                    # L0: FLUX.MD parser
│   │   ├── nodes.py              # AST node types (12 dataclasses)
│   │   └── parser.py             # FluxMDParser class
│   ├── frontend/                  # L1: Language frontends
│   │   ├── c_frontend.py         # C → FIR compiler
│   │   └── python_frontend.py    # Python → FIR compiler
│   ├── fir/                       # L2: Flux IR
│   │   ├── types.py              # 15 type classes + TypeContext
│   │   ├── values.py             # SSA Value
│   │   ├── instructions.py       # 42 instruction classes
│   │   ├── blocks.py             # FIRBlock, FIRFunction, FIRModule
│   │   ├── builder.py            # FIRBuilder
│   │   ├── validator.py          # FIRValidator
│   │   └── printer.py            # print_fir()
│   ├── bytecode/                  # L3: Bytecode
│   │   ├── opcodes.py            # 104-opcode IntEnum
│   │   ├── encoder.py            # FIRModule → bytes
│   │   ├── decoder.py            # bytes → DecodedModule
│   │   └── validator.py          # BytecodeValidator
│   ├── vm/                        # Micro-VM interpreter
│   │   ├── registers.py          # 64-register file (GP/FP/VEC)
│   │   ├── memory.py             # MemoryRegion + MemoryManager
│   │   └── interpreter.py        # Fetch-decode-execute loop
│   ├── protocol/                  # L4: A2A Protocol
│   │   ├── message.py            # Typed message envelopes
│   │   ├── channel.py            # Direct/Broadcast/Topic channels
│   │   ├── registry.py           # Capability-based agent registry
│   │   ├── negotiation.py        # 4-step trust handshake
│   │   └── serialization.py      # BinaryMessageCodec
│   ├── a2a/                       # A2A primitives
│   │   ├── messages.py           # A2A message types
│   │   ├── transport.py          # Agent transport
│   │   ├── coordinator.py        # Agent coordination
│   │   └── trust.py              # Trust engine
│   ├── runtime/                   # L5: Agent Runtime
│   │   ├── agent.py              # Agent (wraps Interpreter)
│   │   └── agent_runtime.py      # AgentRuntime orchestrator
│   ├── optimizer/                 # Optimization passes
│   │   ├── passes.py             # CF, DCE, Inline passes
│   │   └── pipeline.py           # OptimizationPipeline
│   ├── jit/                       # JIT compiler
│   │   ├── compiler.py           # JITCompiler
│   │   ├── cache.py              # JITCache (LRU, SHA-256)
│   │   ├── tracing.py            # ExecutionTracer
│   │   └── ir_optimize.py        # IR-level optimizations
│   ├── types/                     # Type system
│   │   ├── unify.py              # TypeUnifier (C/Python/Rust → FIR)
│   │   ├── compat.py             # Type compatibility
│   │   └── generic.py            # GenericType, TypeVar, TypeScheme
│   ├── stdlib/                    # Standard library
│   │   ├── intrinsics.py         # print, assert, panic, sizeof, etc.
│   │   ├── collections.py        # List, Map, Set, Queue, Stack
│   │   ├── math.py               # min, max, abs, clamp, lerp, sqrt
│   │   ├── strings.py            # concat, substring, split, etc.
│   │   └── agents.py             # AgentRegistry, MessageQueue, Scheduler
│   ├── security/                  # Security
│   │   ├── capabilities.py       # Capability tokens
│   │   ├── resource_limits.py    # Resource monitoring
│   │   └── sandbox.py            # Sandbox lifecycle
│   ├── reload/                    # Hot code reload
│   │   └── hot_loader.py         # BEAM-inspired HotLoader
│   ├── compiler/                  # Unified compiler pipeline
│   │   └── pipeline.py           # FluxCompiler (C/Python/MD → bytecode)
│   └── pipeline/                  # E2E pipeline (this round)
│       ├── e2e.py                # FluxPipeline + PipelineResult
│       ├── polyglot.py           # PolyglotCompiler + PolyglotSource
│       └── debug.py              # PipelineDebugger + disassembler
├── tests/
│   ├── test_fir.py               # 13 tests
│   ├── test_parser.py            # 11 tests
│   ├── test_vm.py                # 25 tests
│   ├── test_bytecode.py          # 12 tests
│   ├── test_a2a.py               # 10 tests
│   ├── test_frontends.py         # 8 tests
│   ├── test_optimizer.py         # 4 tests
│   ├── test_runtime.py           # 6 tests
│   ├── test_stdlib.py            # 66 tests
│   ├── test_protocol.py          # 85 tests
│   ├── test_jit.py               # 43 tests
│   ├── test_type_unify.py        # 76 tests
│   ├── test_security.py          # 6 tests
│   ├── test_reload.py            # 3 tests
│   └── test_integration.py       # 14 tests
├── docs/
│   └── FLUX_Design_Specification.pdf
├── benchmarks/
│   └── benchmarks.py
├── worklog.md
├── README.md
└── LICENSE
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
