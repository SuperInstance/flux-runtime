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
│  L3  FLUX Bytecode (compact binary, 128+ opcodes)   │
├─────────────────────────────────────────────────────┤
│  L2  FIR — Flux IR (universal SSA-form IR)          │
├─────────────────────────────────────────────────────┤
│  L1  Frontend Pass (C/Rust/Python/Go/Julia → FIR)  │
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
