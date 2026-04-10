# FLUX Documentation Index

Complete documentation for the FLUX (Fluid Language Universal eXecution) runtime.

## 📚 Documentation Structure

```
docs/
├── bootcamp/                          # Learn FLUX from scratch
│   ├── README.md                      # Bootcamp overview & progression
│   ├── module-01-bytecode-basics.md   # Instruction formats & registers
│   ├── module-02-control-flow.md      # Loops, jumps, conditionals
│   ├── module-03-a2a-protocol.md      # Agent-to-agent messaging
│   ├── module-04-memory-regions.md    # Memory management & stack
│   ├── module-05-fir-pipeline.md      # C → FIR → Bytecode compilation
│   └── module-06-fleet-patterns.md    # Multi-agent coordination
│
├── user-guide.md                      # Complete user reference
├── developer-guide.md                  # Architecture & contribution guide
├── agent-training/README.md            # Guide for AI agents
│
├── research/                           # Research documentation
│   ├── agent_orchestration.md         # Multi-agent orchestration
│   ├── bootstrap_and_meta.md          # Self-bootstrapping systems
│   ├── creative_use_cases.md          # Creative applications
│   ├── memory_and_learning.md         # Memory & learning systems
│   └── simulation_and_prediction.md    # Simulation & prediction
│
└── [existing docs]                    # Original project documentation
    ├── GRADUATION.md
    ├── MIGRATION_GUIDE.md
    ├── REVERSE_ENGINEERING.md
    └── RESEARCH_ROADMAP.md
```

## 🚀 Quick Start

### New to FLUX?
Start with the **[Bootcamp](bootcamp/README.md)** — 6 modules taking you from zero to proficient FLUX developer.

### Want to use FLUX?
See the **[User Guide](user-guide.md)** for installation, CLI reference, and Python API.

### Want to contribute?
Read the **[Developer Guide](developer-guide.md)** for architecture, patterns, and workflow.

### Are you an AI agent?
Check the **[Agent Training Guide](agent-training/README.md)** for bytecode generation patterns.

## 📖 Bootcamp Modules

| Module | Topic | Duration | Exercises |
|--------|-------|----------|-----------|
| [Module 1](bootcamp/module-01-bytecode-basics.md) | Bytecode Basics | 30 min | 2 |
| [Module 2](bootcamp/module-02-control-flow.md) | Control Flow | 45 min | 2 |
| [Module 3](bootcamp/module-03-a2a-protocol.md) | A2A Protocol | 40 min | 1 |
| [Module 4](bootcamp/module-04-memory-regions.md) | Memory Regions | 35 min | 1 |
| [Module 5](bootcamp/module-05-fir-pipeline.md) | FIR Pipeline | 50 min | 1 |
| [Module 6](bootcamp/module-06-fleet-patterns.md) | Fleet Patterns | 45 min | 1 |

**Total Time**: ~4 hours
**Total Exercises**: 8

## 🔑 Key Concepts

### Bytecode Formats
- **Format A** (1 byte): `[opcode]` — HALT, NOP
- **Format B** (2 bytes): `[opcode][reg]` — INC, DEC
- **Format C** (3 bytes): `[opcode][rd][rs1]` — MOV, LOAD
- **Format D** (4 bytes): `[opcode][reg][offset]` — JMP, CALL
- **Format E** (4 bytes): `[opcode][rd][rs1][rs2]` — IADD, IMUL
- **Format G** (variable): `[opcode][len][data...]` — A2A messages

### Register File
- **R0-R15**: General-purpose (R11=SP, R14=FP, R15=LR)
- **F0-F15**: Floating-point registers
- **V0-V15**: SIMD/vector registers (128-bit)

### A2A Protocol
- **TELL**: Fire-and-forget notification
- **ASK**: Request-response pattern
- **DELEGATE**: Task delegation
- **BROADCAST**: One-to-many messaging
- **Trust**: 0-1000 score system

## 📊 Documentation Statistics

| Category | Documents | Total Words | Code Examples |
|----------|-----------|-------------|---------------|
| Bootcamp | 7 | ~15,000 | 50+ |
| Guides | 3 | ~12,000 | 30+ |
| Research | 5 | ~8,000 | 20+ |
| **Total** | **15** | **~35,000** | **100+** |

## 🎯 Learning Paths

### Path 1: FLUX Developer
```
Bootcamp (all 6 modules) → User Guide → Build Application
```

### Path 2: FLUX Contributor
```
Bootcamp (modules 1-3) → Developer Guide → Contribute
```

### Path 3: Agent Systems
```
Bootcamp (modules 3, 6) → Research Docs → Build Fleet
```

### Path 4: AI Agent
```
Agent Training Guide → Generate Bytecode → Optimize
```

## 🔧 Reference Materials

### Opcode Reference
- **Control**: NOP, HALT, JMP, CALL, RET
- **Arithmetic**: IADD, ISUB, IMUL, IDIV, IMOD
- **Bitwise**: IAND, IOR, IXOR, ISHL, ISHR
- **Comparison**: IEQ, ILT, IGT, CMP, TEST
- **Stack**: PUSH, POP, DUP, SWAP, ENTER, LEAVE
- **Memory**: LOAD, STORE, ALLOCA, REGION_CREATE
- **A2A**: TELL, ASK, DELEGATE, BROADCAST

### API Quick Reference

```python
# Core VM
from flux.vm.interpreter import Interpreter
vm = Interpreter(bytecode, memory_size=4096)
vm.execute()

# Register access
vm.regs.read_gp(0)    # Read R0
vm.regs.write_gp(0, 42)  # Write R0

# Memory operations
memory = vm.memory
region = memory.create_region("heap", 65536, "user")
region.write_i32(0, 42)

# A2A messaging
from flux.a2a.messages import A2AMessage
msg = A2AMessage(...)
raw = msg.to_bytes()

# FIR builder
from flux.fir import FIRBuilder, TypeContext
builder = FIRBuilder(TypeContext())
module = builder.new_module("my_module")
```

## 🌟 Features Covered

### ✅ Core Features
- [x] Bytecode encoding/decoding
- [x] VM execution (48K+ ops/sec)
- [x] Register file (64 registers)
- [x] Memory management
- [x] Control flow
- [x] Stack operations

### ✅ Advanced Features
- [x] A2A protocol
- [x] Trust scoring
- [x] Capability security
- [x] FIR intermediate representation
- [x] Multi-language frontend (C, Python)
- [x] Fleet coordination

### ✅ Tools
- [x] CLI (compile, run, debug, test)
- [x] REPL
- [x] Debugger
- [x] Profiler
- [x] Migrator

## 📝 Examples Reference

| Example | Description | Location |
|---------|-------------|----------|
| Hello World | 3 ways to run FLUX | `examples/01_hello_world.py` |
| Polyglot | Mix C and Python | `examples/02_polyglot.py` |
| A2A Agents | Agent communication | `examples/03_a2a_agents.py` |
| Fleet Sim | Multi-agent fleet | `examples/flux_fleet_sim.py` |

## 🤝 Community

### Getting Help
- **GitHub Issues**: [Report bugs](https://github.com/SuperInstance/flux-runtime/issues)
- **Discussions**: [Ask questions](https://github.com/SuperInstance/flux-runtime/discussions)
- **Examples**: See `examples/` directory

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

See [Developer Guide](developer-guide.md) for details.

## 📚 Additional Reading

### Research Papers
- [Agent Orchestration](research/agent_orchestration.md)
- [Memory and Learning](research/memory_and_learning.md)
- [Simulation and Prediction](research/simulation_and_prediction.md)

### Advanced Topics
- [Self-Bootstrapping Systems](research/bootstrap_and_meta.md)
- [Creative Use Cases](research/creative_use_cases.md)

## 🎓 Certification

Complete all 6 bootcamp modules and exercises to earn FLUX Developer certification.

**Requirements**:
- ✅ Complete all modules
- ✅ Pass all exercises
- ✅ Submit a project
- ✅ Community review

## 🚀 Get Started Now

```bash
# Install FLUX
pip install flux-runtime

# Run hello world
flux hello

# Start bootcamp
# Open: docs/bootcamp/README.md
```

---

**FLUX Runtime** — Fluid Language Universal eXecution
*A self-assembling, self-improving runtime that compiles markdown to bytecode.*

[GitHub](https://github.com/SuperInstance/flux-runtime) |
[Bootcamp](bootcamp/README.md) |
[User Guide](user-guide.md) |
[Developer Guide](developer-guide.md)
