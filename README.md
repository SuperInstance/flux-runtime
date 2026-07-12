# FLUX ⚡ Fluid Language Universal eXecution

[![PyPI](https://img.shields.io/pypi/v/flux-vm)](https://pypi.org/project/flux-vm/)
[![CI](https://github.com/SuperInstance/flux-runtime/actions/workflows/ci.yml/badge.svg)](https://github.com/SuperInstance/flux-runtime/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-2037-brightgreen.svg)](#testing)
[![Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](#architecture)

> **A self-assembling, self-improving runtime that compiles markdown to bytecode.**

<p align="center">
  <img src="flux-logo.jpg" width="200" height="170" alt="FLUX — Hermit Crab with Steampunk Shell" />
</p>

---

## Quick Start

```bash
pip install flux-vm
flux hello
```

That's it — three commands from zero to running bytecode:

```bash
pip install flux-vm                              # Install
flux compile examples/02_polyglot.md -o out.bin  # Compile markdown → bytecode
flux run out.bin                                  # Execute in the 64-register VM
```

---

## What It Does

**FLUX** is a markdown-to-bytecode runtime designed for AI agents. You write structured markdown files containing polyglot code blocks — mixing C, Python, Rust, or any language line by line — and the FLUX compiler weaves them into a single optimized, verifiable bytecode that runs on a 64-register micro-VM.

FLUX-ese is what you get when you make a programming language that reads like a lawyer writes a contract. Every word is defined. Every operation is precise. Custom definitions are spelled out up front. The language is **natural but precise** — like legalese is to lawyers, FLUX-ese is to agents. If a translator can turn any line of code in any language into a line of FLUX-ese, then you have a **common language** that's completely observable, understandable, and changeable by humans — both technical and non-technical.

Agents are the primary readers. They learn the symbols, scan for what matters, skip the commentary. But the commentary is there for the human who needs to understand what happened. The `.ese` file format (pronounced "easy") is markdown with structured annotations — `**` marks defined terms, `--` marks inline comments, `==` marks equivalence definitions, `>>` marks agent-jump markers.

---

## Architecture

FLUX is the **Python implementation** of the FLUX bytecode runtime — the most feature-complete implementation in the ecosystem, with 2,037 tests and zero external dependencies (Python 3.10+ stdlib only).

```
┌─────────────────────────────────────────────────────────┐
│  TIER 8: SYNTHESIS — FluxSynthesizer (the DJ booth)    │
│  Wires ALL subsystems together                          │
├─────────────────────────────────────────────────────────┤
│  TIER 7: MODULES — 8-Level Fractal Hot-Reload          │
│  TRAIN → CARRIAGE → LUGGAGE → BAG → ... → CARD        │
├─────────────────────┬───────────────────────────────────┤
│  TIER 6A: ADAPTIVE  │  TIER 6B: EVOLUTION             │
│  Profiler + Selector│  Genome + Mutator + Validator     │
├─────────────────────┴───────────────────────────────────┤
│  TIER 5: TILES — 35 composable computation patterns    │
├─────────────────────────────────────────────────────────┤
│  TIER 4: AGENT RUNTIME — Trust, scheduling, resources  │
├─────────────────────────────────────────────────────────┤
│  TIER 3: A2A PROTOCOL — TELL, ASK, DELEGATE, BROADCAST│
├─────────────────────────────────────────────────────────┤
│  TIER 2: SUPPORT — Optimizer, JIT, Types, Stdlib, Sec  │
├─────────────────────────────────────────────────────────┤
│  TIER 1: CORE — FLUX.MD → FIR (SSA) → Bytecode → VM   │
└─────────────────────────────────────────────────────────┘
```

FLUX sits at **Tier 1** of the SuperInstance ecosystem — it's the deterministic compute engine that agents use when they need verifiable, reproducible execution. The same bytecode ISA runs across [Python](https://github.com/SuperInstance/flux-runtime), [Rust](https://github.com/SuperInstance/flux-core), [JavaScript](https://github.com/SuperInstance/flux-js), [C](https://github.com/SuperInstance/flux-runtime-c), [Zig](https://github.com/SuperInstance/flux-zig), [Go](https://github.com/SuperInstance/flux-swarm), and more.

### Key Concepts

- **FLUX-ese (.ese files)** — Markdown with structured annotations for natural-but-precise vocabulary
- **A2A Protocol** — 32 native bytecode instructions for agent-to-agent communication (`TELL`, `ASK`, `DELEGATE`, `BROADCAST`)
- **Polyglot Execution** — Write in any language, mix freely, compile to a single bytecode
- **Tiling System** — Vocabulary compounds: Level 0 primitives tile into Level N decisions
- **Paper Decomposer** — Research papers become executable vocabulary (244 papers → 2,979 concepts)

---

## API / Usage

### CLI Reference

```
flux hello                              Run the hello world demo
flux compile <input> -o <output>        Compile source to FLUX bytecode
flux run <bytecode> [--cycles N]        Execute bytecode in the VM
flux test                               Run the full test suite (2037 tests)
flux version                            Print version info
flux demo                               Run the synthesis demo
flux info                               Show system architecture info
flux repl                               Open the FLUX REPL (hex bytecode)
flux debug <bytecode>                   Step-through debugger with breakpoints
flux disasm <bytecode>                  Disassemble bytecode to human-readable
```

### Python API

```python
from flux import FluxVM, Assembler

# Assemble and run bytecode
bc = Assembler.assemble("MOVI R0, 42\nHALT")
vm = FluxVM(bc)
vm.execute()
print(vm.read_gp(0))  # 42
```

### Natural Language Vocabulary

```python
from flux.open_interp.vocabulary import Interpreter

interp = Interpreter.with_builtins()
interp.execute("factorial of 5")    # 120
interp.execute("sum 1 to 100")      # 5050
interp.execute("power of 2 to 10")  # 1024
```

### Custom Vocabulary (`.fluxvocab`)

```markdown
## pattern: steer heading $deg
## assembly: |
##   MOVI R0, ${deg}
##   MOVI R1, 360
##   IDIV R1, R0, R1
##   HALT
## description: Normalize heading to 0-359 range
## result_reg: 0
## tags: maritime, navigation
```

---

## Testing

```bash
# Run the full test suite
flux test

# Or with pytest
pip install -e ".[dev]"
pytest tests/ -v

# 2,037 tests covering: VM, assembler, disassembler, vocabulary,
# A2A protocol, compiler, paper decomposer, tiles, synthesis
```

---

## Contributing

Contributions are welcome! See the [SuperInstance Contributing Guide](https://github.com/SuperInstance/SuperInstance/blob/main/CONTRIBUTING.md) for guidelines.

1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Ensure `flux test` passes (2,037 tests)
5. Submit a PR

---

## 📦 Related Packages

FLUX is implemented across multiple languages — same bytecode, different shells:

| Package | Language | Registry | Install |
|---------|----------|----------|---------|
| **[flux-vm](https://pypi.org/project/flux-vm/)** | Python | PyPI | `pip install flux-vm` |
| **[fluxvm](https://crates.io/crates/fluxvm)** | Rust | crates.io | `cargo add fluxvm` |
| **[flux-js](https://www.npmjs.com/package/flux-js)** | JavaScript | npm | `npm install flux-js` |

Additional implementations: [C](https://github.com/SuperInstance/flux-runtime-c) · [Zig](https://github.com/SuperInstance/flux-zig) · [Go](https://github.com/SuperInstance/flux-swarm) · [Java](https://github.com/SuperInstance/flux-java) · [WASM](https://github.com/SuperInstance/flux-wasm) · [CUDA](https://github.com/SuperInstance/flux-cuda)

---

## Ecosystem

This repo is part of the **SuperInstance** flagship ecosystem — agent-first computation, constraint theory, and self-improving runtimes.

### FLUX Runtime Family

| Repo | Language | Description |
|------|----------|-------------|
| [flux-runtime](https://github.com/SuperInstance/flux-runtime) | Python | Full FLUX runtime: markdown→bytecode, 2037 tests, zero deps |
| [flux-core](https://github.com/SuperInstance/flux-core) | Rust | Register-based bytecode VM, deterministic agent computation |
| [flux-js](https://github.com/SuperInstance/flux-js) | JavaScript | FLUX VM for Node.js and browsers, ~400ns/iter |
| [flux-compiler](https://github.com/SuperInstance/flux-compiler) | Rust/Python | Formal-methods compiler for safety-critical codegen |
| [flux-vm](https://github.com/SuperInstance/flux-vm) | Rust | Stack-based constraint-checking VM, 50 opcodes, Turing-incomplete |

### PLATO Engine Family

| Repo | Language | Description |
|------|----------|-------------|
| [plato-server](https://github.com/SuperInstance/plato-server) | Python | Knowledge tiles, fleet sync via Matrix, HTTP API |
| [plato-engine-block](https://github.com/SuperInstance/plato-engine-block) | Rust | Original room runtime: no_std + alloc, builder pattern |
| [plato-engine-block-c](https://github.com/SuperInstance/plato-engine-block-c) | C99 | Embedded reference: zero heap alloc, bare-metal portable |
| [plato-engine-block-elixir](https://github.com/SuperInstance/plato-engine-block-elixir) | Elixir | BEAM supervision trees, fault tolerance, hot reload |
| [plato-runtime-kernel](https://github.com/SuperInstance/plato-runtime-kernel) | Rust | Spatial model: tensor grid, batons, assertion traps |

### Constraint / Theory Family

| Repo | Language | Description |
|------|----------|-------------|
| [categorical-agents](https://github.com/SuperInstance/categorical-agents) | Rust | Category theory for agent composition (functors, naturality) |
| [cuda-constraint-engine](https://github.com/SuperInstance/cuda-constraint-engine) | CUDA/C | GPU constraint checking at 1B+ constraints/sec |
| [grand-pattern-rs](https://github.com/SuperInstance/grand-pattern-rs) | Rust | Fibonacci dual-direction cellular graph architecture |
| [lau-hodge-theory](https://github.com/SuperInstance/lau-hodge-theory) | Rust | Hodge decomposition, Betti numbers, spectral sequences |
| [ternary-science](https://github.com/SuperInstance/ternary-science) | Rust | Experimental evidence for ternary intelligence, 5 conservation laws |

### Agent / Infrastructure Family

| Repo | Language | Description |
|------|----------|-------------|
| [construct-core](https://github.com/SuperInstance/construct-core) | Rust | Layered trait system: bare-metal → alloc → async agent runtime |
| [crab](https://github.com/SuperInstance/crab) | Bash | Agent shell for repo entry/leave (MUD-room metaphor) |
| [exocortex](https://github.com/SuperInstance/exocortex) | Rust | Persistent cognitive substrate, S3-compatible memory |
| [git-agent](https://github.com/SuperInstance/git-agent) | Python | The repo IS the agent — autonomous lifecycle via Git |
| [capitaine-1](https://github.com/SuperInstance/capitaine-1) | TypeScript | Git-native repo-agent, Cloudflare Workers heartbeat |
| [codespace-edge-rd](https://github.com/SuperInstance/codespace-edge-rd) | Research | Codespace→Edge agent lifecycle and yoke transfer protocols |
| [git-agent-codespace](https://github.com/SuperInstance/git-agent-codespace) | DevContainer | One-click Codespace template for Git-Agent runtimes |

### Registries

| Registry | Package | Install |
|----------|---------|---------|
| **PyPI** | `flux-vm` | `pip install flux-vm` |
| **crates.io** | `fluxvm` | `cargo add fluxvm` |
| **npm** | `flux-js` | `npm install flux-js` |

### Philosophy & Architecture

- 📖 [AI-Writings](https://github.com/SuperInstance/AI-Writings) — Philosophy, essays, and design rationale
- 📦 [PACKAGES.md](https://github.com/SuperInstance/SuperInstance/blob/main/PACKAGES.md) — Full package index

---

## License

MIT
