# FLUX Quick Start Guide

Get up and running with FLUX in 5 minutes. This guide walks you through
everything you need to go from zero to executing bytecode on the FLUX Micro-VM.

---

## 1. Install FLUX

```bash
cd /home/z/my-project/flux-py

# Create a virtual environment (if not already done)
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .
```

FLUX has **zero external dependencies** — it uses only the Python standard
library (`struct`, `ast`, `re`, `dataclasses`, `uuid`, `collections`).

## 2. Run Hello World

The simplest way to verify FLUX works:

```bash
PYTHONPATH=src python3 examples/01_hello_world.py
```

This runs four demonstrations:
- **Raw bytecode** — hand-encoded `3 + 4 = 7`
- **FIR builder** — SSA IR construction and execution
- **Full pipeline** — C source → FIR → bytecode → VM
- **Bytecode loop** — computing Sum(1..5) = 15

Expected output: register dumps, cycle counts, and disassembly for each approach.

## 3. Compile Your First FLUX.MD

A FLUX.MD file is a markdown document that becomes bytecode. Create one:

```markdown
---
title: My First FLUX Program
---

# Hello from FLUX.MD

This is a real program. The code below gets compiled to bytecode.

```c
int main() {
    return 42;
}
```
```

Save it as `my_program.md` and compile:

```python
from flux.pipeline.e2e import FluxPipeline

pipeline = FluxPipeline()
with open("my_program.md") as f:
    result = pipeline.run(f.read(), lang="md")

print(f"Success: {result.success}")
print(f"Cycles: {result.cycles}")
print(f"Halted: {result.halted}")
print(f"Bytecode: {len(result.bytecode)} bytes")
```

Run it:

```bash
PYTHONPATH=src python3 my_program.py
```

## 4. Run Bytecode Directly

You can also construct and run raw bytecode without any source language:

```python
import struct
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter

# Build: 10 + 20 = 30
code = bytearray()
code.extend(struct.pack("<BBh", Op.MOVI, 0, 10))  # R0 = 10
code.extend(struct.pack("<BBh", Op.MOVI, 1, 20))  # R1 = 20
code.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))  # R0 = R0 + R1
code.extend(bytes([Op.HALT]))  # stop

vm = Interpreter(bytes(code), memory_size=4096)
cycles = vm.execute()
print(f"R0 = {vm.regs.read_gp(0)}")  # Output: R0 = 30
print(f"Cycles: {cycles}")
```

## 5. Disassemble Bytecode

See what your bytecode looks like in human-readable form:

```python
from flux.pipeline.debug import disassemble_bytecode

disasm = disassemble_bytecode(result.bytecode)
print(disasm)
```

Output:
```
FLUX Bytecode v1
  flags: 0x0000
  functions: 1
  type_table_offset: 18
  code_section_offset: 38

Code Section (offset 38):
----------------------------------------
  0026:  halt
```

## 6. Understanding the Architecture

FLUX is a 6-layer stack. Here's what each layer does:

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: FLUX.MD                                       │
│  Markdown documents with embedded code blocks           │
│  Supports: C, Python, JSON, YAML, FLUX IR               │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Parser + FIR Builder                          │
│  YAML frontmatter → headings → code blocks → AST        │
│  FIR: SSA form with typed values, basic blocks          │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Optimizer + Bytecode Encoder                  │
│  Passes: constant fold, DCE, inlining, block layout     │
│  Binary format: FLUX header + type table + code         │
├─────────────────────────────────────────────────────────┤
│  Layer 4: A2A Protocol                                  │
│  Binary messages with trust, capabilities, priority     │
│  Opcodes: TELL, ASK, DELEGATE, BROADCAST                │
├─────────────────────────────────────────────────────────┤
│  Layer 5: FLUX Micro-VM                                 │
│  Fetch-decode-execute interpreter                       │
│  64 registers (16 GP + 16 FP + 16 VEC)                 │
│  100+ opcodes, variable-length encoding                 │
├─────────────────────────────────────────────────────────┤
│  Layer 6: Runtime                                       │
│  Agent orchestration, hot-reload, self-evolution        │
│  Adaptive profiling, tile system, JIT cache             │
└─────────────────────────────────────────────────────────┘
```

### Key Numbers

| Metric | Value |
|--------|-------|
| Opcodes | 100+ |
| Register file | 64 (R0-R15, F0-F15, V0-V15) |
| Instruction formats | 6 (A/B/C/D/E/G) |
| Source languages | C, Python, FLUX.MD |
| Test count | 850+ |
| External deps | 0 |

### Opcode Categories

| Category | Opcodes | Examples |
|----------|---------|---------|
| Control flow | 0x00–0x07 | NOP, JMP, CALL, RET |
| Integer arithmetic | 0x08–0x0F | IADD, ISUB, IMUL, IDIV |
| Bitwise | 0x10–0x17 | IAND, IOR, IXOR, ISHL |
| Comparison | 0x18–0x1F | CMP, IEQ, ILT, IGT |
| Stack | 0x20–0x27 | PUSH, POP, DUP, SWAP |
| Function | 0x28–0x2F | CALL_IND, TAILCALL, MOVI |
| Memory | 0x30–0x37 | REGION_CREATE, MEMCOPY |
| Type | 0x38–0x3F | CAST, BOX, UNBOX |
| Float | 0x40–0x4F | FADD, FSUB, FMUL, FDIV |
| SIMD | 0x50–0x5F | VLOAD, VSTORE, VADD |
| A2A Protocol | 0x60–0x7F | TELL, ASK, DELEGATE |
| System | 0x80–0x9F | HALT, YIELD, DEBUG_BREAK |

## 7. Where to Learn More

### Examples Gallery

| Example | File | Difficulty | Description |
|---------|------|-----------|-------------|
| Hello World | `01_hello_world.py` | Beginner | Three ways to run FLUX programs |
| Polyglot | `02_polyglot.md` | Beginner | Mix C and Python in one document |
| A2A Agents | `03_a2a_agents.py` | Intermediate | Agent communication protocol |
| Adaptive Profiling | `04_adaptive_profiling.py` | Intermediate | Heat classification and language selection |
| Tile Composition | `05_tile_composition.py` | Intermediate | Reusable computation patterns |
| Evolution | `06_evolution.py` | Advanced | Self-improving VM system |
| Full Synthesis | `07_full_synthesis.py` | Advanced | Complete system lifecycle |
| Bytecode Playground | `05_bytecode_playground.py` | Beginner | Interactive REPL |
| Polyglot Add | `02_polyglot_add.md` | Beginner | Polyglot math operations |
| Fibonacci | `03_fibonacci.md` | Beginner | Fibonacci at three levels |
| Agent Handshake | `04_agent_handshake.md` | Intermediate | A2A protocol demo |

### Source Code

```
src/flux/
├── parser/         # FLUX.MD → AST
├── fir/            # SSA intermediate representation
├── frontend/       # C and Python frontends
├── compiler/       # Unified compilation pipeline
├── bytecode/       # Encoder, decoder, validator
├── vm/             # Micro-VM interpreter
├── pipeline/       # End-to-end pipeline + debugger
├── a2a/            # Agent-to-agent protocol
├── runtime/        # Agent runtime + orchestrator
├── adaptive/       # Profiler + language selector
├── tiles/          # Composable computation patterns
├── evolution/      # Self-evolution engine
├── jit/            # JIT compiler + cache
├── modules/        # Hot-reload module system
├── protocol/       # Messages, channels, negotiation
├── stdlib/         # Standard library (math, strings, collections)
└── synthesis/      # The complete FLUX synthesizer
```

### Tests

```bash
# Run all tests
PYTHONPATH=src pytest tests/ -v

# Run specific test suites
PYTHONPATH=src pytest tests/test_vm.py -v       # VM tests
PYTHONPATH=src pytest tests/test_parser.py -v    # Parser tests
PYTHONPATH=src pytest tests/test_bytecode.py -v  # Bytecode tests
PYTHONPATH=src pytest tests/test_runtime.py -v   # Runtime tests
PYTHONPATH=src pytest tests/test_integration.py -v  # E2E tests
```

## 8. Next Steps

1. **Read `hello_world.md`** — The flagship FLUX.MD document
2. **Try the bytecode playground** — `python3 examples/05_bytecode_playground.py`
3. **Explore polyglot compilation** — `02_polyglot_add.md`
4. **Build an agent system** — `03_a2a_agents.py`
5. **Watch the system evolve** — `06_evolution.py`
6. **See everything together** — `07_full_synthesis.py`

Welcome to FLUX!
