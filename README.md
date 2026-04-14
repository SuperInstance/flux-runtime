# flux-runtime

**The Reference FLUX Bytecode Virtual Machine — Python Implementation**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org)
[![Zero Dependencies](https://img.shields.io/badge/deps-0-2ecc71)]()
[![Tests](https://img.shields.io/badge/tests-2,495+-brightgreen)](#testing)
[![Opcodes](https://img.shields.io/badge/opcodes-122-orange)](#opcode-categories)
[![Registers](https://img.shields.io/badge/registers-64-blue)](#vm-architecture)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![ISA v3](https://img.shields.io/badge/ISA-v3%20ready-orange)]()

> **flux-runtime** is the core Python implementation of the FLUX bytecode virtual machine. It defines the ISA, implements the reference execution engine, and serves as the golden standard for all cross-language conformance testing. Zero dependencies. Pure Python. Production-grade.

Part of the [SuperInstance](https://github.com/SuperInstance) fleet.

---

## Table of Contents

- [Quick Start](#quick-start)
- [VM Architecture](#vm-architecture)
- [Opcode Categories](#opcode-categories)
- [Testing](#testing)
- [Cross-Runtime Ecosystem](#cross-runtime-ecosystem)
- [Repository Structure](#repository-structure)
- [Design Philosophy](#design-philosophy)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Install

```bash
# Clone the repository
git clone https://github.com/SuperInstance/flux-runtime.git
cd flux-runtime

# No install needed — zero dependencies, pure Python stdlib
python -c "from flux.vm import FluxVM; print('ready')"
```

### Run a FLUX Program

```python
import struct
from flux.vm import FluxVM

# Create a VM instance (64 registers, 64KB memory, clean state)
vm = FluxVM()

# Assemble bytecode: PUSH 3, PUSH 4, ADD, HALT
bytecode = bytes([
    0x55, 0x03, 0x00, 0x00, 0x00,  # PUSH 3
    0x55, 0x04, 0x00, 0x00, 0x00,  # PUSH 4
    0x10,                            # ADD
    0x80,                            # HALT
])

# Execute and inspect results
stack, flags = vm.run(bytecode)
print(f"Result: {stack}  Flags: 0x{flags:02x}")
# Result: [7]  Flags: 0x00
```

### Compile Structured Markdown to Bytecode

```python
from flux.compiler import FluxCompiler

# FLUX compiles structured markdown with polyglot code blocks
# into optimized bytecode for the 64-register Micro-VM
compiler = FluxCompiler()
bytecode = compiler.compile("program.md")

vm = FluxVM()
stack, flags = vm.run(bytecode)
```

---

## VM Architecture

flux-runtime implements a **64-register stack machine** with a **fetch-decode-execute** cycle. The VM is designed as the canonical reference — any FLUX runtime in any language must produce identical results for identical bytecode.

### Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │         FLUX VIRTUAL MACHINE         │
                    ├─────────────────────────────────────┤
                    │                                     │
                    │   ┌──────────┐   ┌──────────────┐  │
  bytecode ──────> │   │  FETCH   │──>│   DECODE     │  │
  (bytes)          │   │ PC += N  │   │ opcode dispatch│ │
                    │   └──────────┘   └──────┬───────┘  │
                    │                                │      │
                    │   ┌──────────┐   ┌───────────▼──┐  │
                    │   │  FLAGS   │<──│   EXECUTE    │  │
                    │   │ Z S C O  │   │ modify state  │  │
                    │   └──────────┘   └──────┬───────┘  │
                    │                                │      │
                    │   ┌──────────┐   ┌───────────▼──┐  │
                    │   │ REGISTERS│<──│   STACK      │  │
                    │   │ R0..R63  │   │ LIFO (data)  │  │
                    │   └──────────┘   │ CALL_STACK   │  │
                    │                  │ SIGNALS dict │  │
                    │   ┌──────────┐   └──────────────┘  │
                    │   │  MEMORY  │                     │
                    │   │ 64 KB    │   ┌──────────────┐  │
                    │   │ LE bytes │   │  CONFIDENCE  │  │
                    │   └──────────┘   │  [0.0, 1.0]  │  │
                    │                  └──────────────┘  │
                    └─────────────────────────────────────┘
```

### Fetch-Decode-Execute Cycle

```
  ┌─────────┐      ┌─────────┐      ┌──────────┐
  │  FETCH  │─────>│  DECODE │─────>│ EXECUTE  │
  │         │      │         │      │          │
  │ Read    │      │ Route   │      │ Modify   │
  │ opcode  │      │ to      │      │ stack,   │
  │ at PC   │      │ handler │      │ memory,  │
  │ Read    │      │ Read    │      │ flags,   │
  │ operands│      │ immediates│    │ PC       │
  │ PC += N │      │         │      │ PC += N  │
  └─────────┘      └─────────┘      └────┬─────┘
       ^                                    │
       └────────────────────────────────────┘
                  while !halted && steps < max_steps
```

### Core Components

| Component | Specification | Details |
|-----------|--------------|---------|
| **Registers** | 64 general-purpose (R0–R63) | Typed: integer, float, pointer, confidence |
| **Stack** | Unbounded LIFO data stack | Holds values for computation; grows dynamically |
| **Call Stack** | Separate return address stack | `CALL` pushes PC, `RET` pops it |
| **Memory** | 64 KB linear byte-addressable | Little-endian 32-bit signed integers |
| **Program Counter** | Byte-addressed instruction pointer | Modified by jump and call instructions |
| **Flags Register** | 4-bit condition code register | **Z** (zero), **S** (sign), **C** (carry), **O** (overflow) |
| **Confidence Register** | Float in [0.0, 1.0] | Agent confidence level; clamped on write |
| **Signal Channels** | Dict: channel → FIFO queue | Agent-to-agent messaging (SIGNAL/BROADCAST/LISTEN) |
| **Safety Limit** | 100,000 steps per execution | Configurable; prevents infinite loops |

### Flag Update Rules

| Flag | Bit | Arithmetic (ADD/SUB/MUL/DIV/MOD/NEG/INC/DEC) | Logic/Compare (AND/OR/XOR/NOT/SHL/SHR/EQ/LT/...) |
|------|-----|-----------------------------------------------|-----------------------------------------------------|
| **Z** | 0x01 | Set if result == 0 | Set if result == 0 |
| **S** | 0x02 | Set if result < 0 | Set if result < 0 |
| **C** | 0x04 | Unsigned overflow (add), borrow (sub), carry (mul) | Always cleared |
| **O** | 0x08 | Signed overflow | Always cleared |

### Instruction Encoding

FLUX uses 7 encoding formats (A–G):

| Format | Structure | Size | Used By |
|--------|-----------|------|---------|
| **A** | `[opcode]` | 1 byte | NOP, HALT, ADD, SUB, DUP, SWAP, etc. |
| **B** | `[opcode][addr16]` | 3 bytes | JMP, JZ, JNZ, CALL, LOAD, STORE |
| **C** | `[opcode][value32]` | 5 bytes | PUSH (immediate) |
| **D** | `[opcode][channel8]` | 2 bytes | SIGNAL, BROADCAST, LISTEN |
| **E** | `[opcode][reg8]` | 2 bytes | Register operations |
| **F** | `[opcode][reg8][imm8]` | 3 bytes | Register-immediate |
| **G** | `[opcode][reg8][reg8]` | 3 bytes | Register-register |

All multi-byte values are **little-endian**.

---

## Opcode Categories

flux-runtime defines **122 opcodes** across **16 functional categories**. The ISA v2 specification allocates **247 opcode slots** across the encoding space, with the remaining slots reserved for future extensions.

### Category Breakdown

| # | Category | Opcodes | Count |
|---|----------|---------|-------|
| 1 | **System Control** | `NOP`, `HALT`, `YIELD`, `DEBUG_BREAK`, `RESOURCE_ACQUIRE`, `RESOURCE_RELEASE` | 6 |
| 2 | **Data Movement** | `MOV`, `MOVI`, `PUSH`, `POP` | 4 |
| 3 | **Integer Arithmetic** | `IADD`, `ISUB`, `IMUL`, `IDIV`, `IMOD`, `IREM`, `INEG`, `INC`, `DEC` | 9 |
| 4 | **Bitwise Logic** | `IAND`, `IOR`, `IXOR`, `INOT`, `ISHL`, `ISHR`, `ROTL`, `ROTR` | 8 |
| 5 | **Comparison** | `ICMP`, `IEQ`, `ILT`, `ILE`, `IGT`, `IGE`, `CMP`, `TEST`, `SETCC` | 9 |
| 6 | **Conditional Jump** | `JE`, `JNE`, `JL`, `JGE`, `JG`, `JLE` | 6 |
| 7 | **Control Flow** | `JMP`, `JZ`, `JNZ`, `CALL`, `RET`, `CALL_IND`, `TAILCALL` | 7 |
| 8 | **Stack Manipulation** | `DUP`, `SWAP`, `ROT`, `ENTER`, `LEAVE`, `ALLOCA` | 6 |
| 9 | **Memory** | `LOAD`, `STORE`, `PEEK`, `POKE`, `LOAD8`, `STORE8`, `REGION_CREATE`, `REGION_DESTROY`, `REGION_TRANSFER`, `MEMCOPY`, `MEMSET`, `MEMCMP` | 12 |
| 10 | **Floating-Point** | `FADD`, `FSUB`, `FMUL`, `FDIV`, `FNEG`, `FABS`, `FMIN`, `FMAX`, `FEQ`, `FLT`, `FLE`, `FGT`, `FGE` | 13 |
| 11 | **Type System** | `CAST`, `BOX`, `UNBOX`, `CHECK_TYPE`, `CHECK_BOUNDS` | 5 |
| 12 | **Confidence** | `CONF`, `MERGE`, `RESTORE` | 3 |
| 13 | **SIMD / Vector** | `VLOAD`, `VSTORE`, `VADD`, `VSUB`, `VMUL`, `VDIV`, `VFMA` | 7 |
| 14 | **Agent I/O (TELL/ASK)** | `TELL`, `ASK`, `DELEGATE`, `DELEGATE_RESULT`, `REPORT_STATUS`, `REQUEST_OVERRIDE`, `BROADCAST`, `REDUCE`, `DECLARE_INTENT`, `ASSERT_GOAL`, `VERIFY_OUTCOME`, `EXPLAIN_FAILURE`, `SET_PRIORITY` | 13 |
| 15 | **Trust & Capability** | `TRUST_CHECK`, `TRUST_UPDATE`, `TRUST_QUERY`, `REVOKE_TRUST`, `CAP_REQUIRE`, `CAP_REQUEST`, `CAP_GRANT`, `CAP_REVOKE` | 8 |
| 16 | **Fleet & Formation** | `BARRIER`, `SYNC_CLOCK`, `FORMATION_UPDATE`, `EMERGENCY_STOP`, `EVOLVE`, `INSTINCT`, `WITNESS`, `SNAPSHOT` | 8 |

> **Total: 122 opcodes** (some opcodes appear in multiple usage contexts)

### The 17-Opcode Turing Core

A formally verified subset of **17 opcodes** forms an irreducible Turing-complete core, proven by reduction to a Minsky machine:

| Opcode | Hex | Role |
|--------|-----|------|
| `HALT` | 0x80 | Termination |
| `NOP` | 0x00 | Padding / no-op |
| `RET` | 0x28 | Return from subroutine |
| `PUSH` | 0x20 | Push immediate value |
| `POP` | 0x21 | Discard top value |
| `ADD` | 0x10 | Integer addition |
| `SUB` | 0x11 | Integer subtraction |
| `MUL` | 0x12 | Integer multiplication |
| `DIV` | 0x13 | Integer division |
| `LOAD` | 0x02 | Load from memory address |
| `STORE` | 0x03 | Store to memory address |
| `JZ` | 0x05 | Jump if zero flag |
| `JNZ` | 0x06 | Jump if not zero |
| `JMP` | 0x04 | Unconditional jump |
| `CALL` | 0x07 | Subroutine call |
| `INC` | 0x0E | Increment by 1 |
| `DEC` | 0x0F | Decrement by 1 |

### ISA v3 Extensions

The ISA v3 specification adds three extension classes via the `0xFF` escape prefix:

```
┌──────────┬────────────────┬───────────┬──────────────┐
│ 0xFF     │ extension_id   │ sub_opcode│   payload    │
│ (escape) │ (1 byte)       │ (1 byte)  │ (variable)   │
└──────────┴────────────────┴───────────┴──────────────┘
```

| Extension | ID | Sub-opcodes | Purpose |
|-----------|-----|------------|---------|
| **Temporal** | 0x01 | 6 | Fuel budgets, deadlines, simulated clock, sleep, persistence |
| **Security** | 0x02 | 6 | Capabilities, sandboxing, memory tagging, agent identity |
| **Async** | 0x03 | 6 | Suspend/resume, fork/join, cancel, channel await |

All v3 extensions maintain **full backward compatibility** — any valid v2 program runs identically on a v3 VM.

---

## Testing

### Running Tests

```bash
# Run the full test suite (2,495+ tests)
pytest

# Run with verbose output
pytest -v

# Run a specific test category
pytest tests/test_vm.py -v
pytest tests/test_bytecode.py -v
pytest tests/test_parser.py -v
pytest tests/test_conformance.py -v
pytest tests/test_jit.py -v
pytest tests/test_memory.py -v
pytest tests/test_optimizer.py -v

# Run with coverage report
pytest --cov=src/flux --cov-report=term-missing

# Run benchmarks
python benchmarks/run_benchmarks.py
```

### Test Suite Overview

| Metric | Value |
|--------|-------|
| **Total tests** | 2,495+ |
| **Test files** | 53 |
| **Categories** | VM, bytecode, parser, JIT, memory, optimizer, conformance, evolution, adaptive, a2a |
| **Test framework** | pytest 7.0+ |
| **Coverage approach** | Category-based + parametrized vectors + cross-runtime conformance |
| **CI** | GitHub Actions (Ubuntu, macOS, Windows) × Python 3.10–3.13 |

### Conformance Testing

flux-runtime serves as the **golden reference** for the [flux-conformance](https://github.com/SuperInstance/flux-conformance) test suite. The conformance suite defines portable test vectors (hex-encoded bytecode + expected outputs) that any FLUX runtime must pass:

| Vector Set | Count | Coverage |
|-----------|-------|----------|
| ISA v2 vectors | 113 | 41 base opcodes, 11 categories |
| ISA v3 vectors | 62 | Temporal, Security, Async extensions |
| Cross-runtime | 161 total | Python, Rust, C, Go, TypeScript/WASM |

**Reference result: 113/113 (100%)** on the Python VM. Cross-runtime pass rate: 108/113 (95.6%) across five languages, with all 5 failures traced to a single confidence subsystem spec ambiguity (CONF-002).

### Portability Classification

Opcodes are ranked into four tiers for cross-language implementation difficulty:

| Tier | Count | Example Opcodes | Notes |
|------|-------|----------------|-------|
| **P0 — Universal** | 7 | HALT, NOP, PUSH, POP, ADD, SUB, MUL | Trivially portable to any language |
| **P1 — High** | 12 | NEG, INC, DEC, EQ, NE, LT, GT, DUP, SWAP, JMP, JZ, BREAK | Minor flag nuances |
| **P2 — Medium** | 10 | DIV, MOD, LE, GE, AND, OR, XOR, NOT, JNZ, CALL | Signed arithmetic semantics |
| **P3 — Complex** | 8 | SHL, SHR, LOAD, STORE, PEEK, POKE, RET, ROT | Memory/shift platform dependencies |

---

## Cross-Runtime Ecosystem

flux-runtime sits at the center of a multi-language FLUX ecosystem. It defines the ISA, provides the reference implementation, and generates the conformance test vectors that all other runtimes must satisfy.

```
                    ┌─────────────────────────────────┐
                    │         FLUX ECOSYSTEM          │
                    │                                 │
                    │         flux-runtime            │
                    │    (Python — golden reference)   │
                    │         122 opcodes              │
                    │         2,495+ tests             │
                    │                                 │
                    │    ┌─────────┐  ┌──────────┐    │
                    │    │ ISA spec│  │conformance│    │
                    │    │(defines)│  │ vectors   │    │
                    │    └────┬────┘  └────┬─────┘    │
                    └─────────┼────────────┼──────────┘
                              │            │
              ┌───────────────┼────────────┼───────────────┐
              │               │            │               │
              ▼               ▼            ▼               ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
    │  flux-tui   │ │flux-conform. │ │constraint│ │  Language    │
    │  (Go)       │ │(Python)      │ │theory-core│ │  Ports       │
    │             │ │              │ │(Rust)    │ │              │
    │ TUI debugger│ │ 161 vectors  │ │ Rust VM  │ │ Rust, C, Go, │
    │ assembler   │ │ cross-runtime│ │ port +   │ │ Zig, JS/WASM│
    │ disassembler│ │ testing      │ │ math     │ │ Java, CUDA   │
    │ conform.    │ │ benchmark    │ │ engine   │ │              │
    │ dashboard   │ │ runner       │ │          │ │              │
    └─────────────┘ └──────────────┘ └──────────┘ └──────────────┘
```

### Ecosystem Components

| Repository | Language | Role | Relationship to flux-runtime |
|-----------|----------|------|------------------------------|
| **[flux-runtime](https://github.com/SuperInstance/flux-runtime)** | Python 3.10+ | Reference VM & ISA definition | **This repo** — defines the specification all others implement |
| **[flux-conformance](https://github.com/SuperInstance/flux-conformance)** | Python | Conformance test suite | Consumes flux-runtime's ISA; defines 161 test vectors; runs cross-runtime audits |
| **[flux-tui](https://github.com/SuperInstance/flux-tui)** | Go 1.23+ | TUI debugger & dashboard | Implements FLUX VM in Go; uses flux-conformance vectors; includes assembler/disassembler |
| **[constraint-theory-core](https://github.com/SuperInstance/constraint-theory-core)** | Rust | Mathematical engine | Rust port of FLUX constraint satisfaction; Pythagorean snapping; holonomy verification |
| **[flux-swarm](https://github.com/SuperInstance/flux-swarm)** | Go | Multi-agent swarm runtime | Partial FLUX VM in Go; focuses on agent-to-agent (TELL/ASK) opcodes |
| **[flux-os](https://github.com/SuperInstance/flux-os)** | C | Bare-metal FLUX VM | C implementation targeting embedded systems; minimal opcode subset |
| **[ability-transfer](https://github.com/SuperInstance/ability-transfer)** | Mixed | ISA specification & synthesis | ISA v3 specification authoring; round-table consensus on opcode semantics |

### Cross-Runtime Bytecode Translation

The [canonical opcode shim](https://github.com/SuperInstance/flux-conformance/blob/main/canonical_opcode_shim.py) provides bidirectional bytecode translation between runtime-specific opcode encodings:

```
  Python Runtime ──> Canonical ISA ──> Rust Runtime
  Python Runtime ──> Canonical ISA ──> Go Runtime
  C Runtime      ──> Canonical ISA ──> Python Runtime
```

Each runtime uses different internal opcode numberings, but the canonical ISA (from `flux-spec/ISA.md`) serves as the interoperable interchange format.

---

## Repository Structure

```
flux-runtime/
├── src/flux/                  # Core runtime engine
│   ├── vm.py                 # FluxVM — reference bytecode virtual machine
│   ├── flags.py              # FluxFlags — 4-bit condition code register
│   ├── compiler.py           # Markdown → bytecode compiler
│   ├── bytecode/
│   │   ├── opcodes.py        # 122 opcode definitions (Op class)
│   │   └── encoder.py        # Instruction encoding (formats A–G)
│   ├── parser.py             # Structured markdown parser
│   ├── optimizer.py          # Peephole & dead-code optimizer
│   ├── jit.py                # Adaptive JIT compilation (hot path → native)
│   ├── memory.py             # Memory manager (regions, GC)
│   ├── evolution.py          # Self-improving runtime profiling
│   ├── protocol.py           # Agent-to-agent protocol handler
│   └── cli.py                # Command-line interface
├── tests/                    # 2,495+ tests across 53 files
│   ├── test_vm.py            # VM execution tests
│   ├── test_bytecode.py      # Bytecode encoding tests
│   ├── test_parser.py        # Parser correctness
│   ├── test_conformance.py   # Conformance vector tests
│   ├── test_jit.py           # JIT compilation tests
│   ├── test_memory.py        # Memory management tests
│   ├── test_optimizer.py     # Optimizer tests
│   ├── test_evolution.py     # Adaptive runtime tests
│   ├── test_a2a.py           # Agent-to-agent protocol tests
│   └── ...
├── examples/                 # 12+ demo programs
│   ├── hello_world.md        # Minimal FLUX program
│   ├── fibonacci.md          # Iterative Fibonacci
│   ├── polyglot_demo.md      # Multi-language code blocks
│   ├── agent_handshake.md    # A2A TELL/ASK example
│   ├── bytecode_playground.py # Direct bytecode API demo
│   └── ...
├── tools/                    # Utility scripts
│   ├── flux_analyze.py       # Static bytecode analysis
│   └── flux_migrate.py       # Version migration tool
├── docs/
│   └── research/             # Research roadmaps
├── benchmarks/               # Performance measurement
├── pyproject.toml            # Modern Python packaging (zero deps)
├── LICENSE                   # MIT
└── README.md
```

---

## Design Philosophy

**Zero dependencies.** flux-runtime uses nothing beyond the Python standard library (`struct`, `dataclasses`, `typing`). No NumPy, no LLVM, no C extensions. This makes it the most portable FLUX runtime and the ideal reference implementation — any language can replicate its behavior.

**Deterministic above all.** Every execution produces identical results given identical inputs. No randomness, no platform-dependent behavior, no "approximately correct." The VM defines exact flag update rules, exact division semantics (truncation toward zero), and exact memory byte ordering (little-endian). This determinism is what enables cross-language conformance testing.

**Agent-first design.** FLUX was designed for AI agents, not human programmers. The TELL/ASK opcodes enable inter-agent communication, the confidence register quantifies agent certainty, and the trust/capability system models real-world delegation hierarchies. The runtime treats agents as first-class citizens.

**Self-improving runtime.** flux-runtime profiles its own execution, identifies hot paths, and recompiles bottlenecks into faster representations — all while the system continues running. The evolution module discovers patterns in bytecode execution and optimizes accordingly.

**The repo IS the specification.** There is no separate FLUX spec document. The Python source code, the 122 opcode definitions, and the 2,495+ tests *are* the specification. Any question about FLUX semantics is answered by reading the reference VM implementation.

---

## Contributing

flux-runtime follows the [SuperInstance fleet conventions](https://github.com/SuperInstance/fleet-contributing):

1. **Push often** — Small, atomic commits with clear messages
2. **Test first** — `pytest` before every push; all 2,495+ tests must pass
3. **Conventional commits** — `feat:`, `fix:`, `test:`, `docs:`, `refactor:` prefixes
4. **Zero dependencies** — PRs that add external dependencies will be rejected
5. **The repo IS the agent** — README, tests, and commit history are primary documentation
6. **Witness marks** — Commit messages explain *why*, not just *what*

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Part of the SuperInstance Fleet

| Vessel | Role |
|--------|------|
| [flux-runtime](https://github.com/SuperInstance/flux-runtime) | **Reference** — golden VM, ISA definition, 122 opcodes |
| [flux-conformance](https://github.com/SuperInstance/flux-conformance) | Vectors — 161 conformance test vectors |
| [flux-tui](https://github.com/SuperInstance/flux-tui) | Debugger — TUI debugging & conformance dashboard |
| [constraint-theory-core](https://github.com/SuperInstance/constraint-theory-core) | Math — Rust constraint theory engine |
| [ability-transfer](https://github.com/SuperInstance/ability-transfer) | ISA — specification authoring & synthesis |

---

<img src="callsign1.jpg" width="128" alt="callsign">
