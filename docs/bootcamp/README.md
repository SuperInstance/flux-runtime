# FLUX Agent Bootcamp

Welcome to the FLUX Agent Bootcamp — your comprehensive guide to mastering the FLUX runtime from first principles to advanced multi-agent systems.

## Overview

FLUX (Fluid Language Universal eXecution) is a markdown-to-bytecode runtime designed for AI agents. This bootcamp takes you from zero to proficient FLUX developer through hands-on exercises and real-world examples.

## Prerequisites

- Python 3.10 or higher
- Basic programming knowledge
- Familiarity with bytecode concepts (helpful but not required)
- Interest in agent systems and distributed computing

## Installation

```bash
# Install FLUX runtime
pip install flux-runtime

# Or run from source
cd /path/to/flux-runtime
export PYTHONPATH=src
python3 -m flux --help
```

## Bootcamp Modules

### Foundation (Modules 1-2)
**Start here if you're new to FLUX**

- **[Module 1: Bytecode Basics](module-01-bytecode-basics.md)** — Learn FLUX bytecode instruction formats, register file layout, and write your first program
- **[Module 2: Control Flow](module-02-control-flow.md)** — Master jumps, loops, and conditional branching

### Intermediate (Modules 3-4)
**Build on your foundation**

- **[Module 3: A2A Protocol](module-03-a2a-protocol.md)** — Understand agent-to-agent messaging and trust systems
- **[Module 4: Memory Regions](module-04-memory-regions.md)** — Learn linear memory management and stack operations

### Advanced (Modules 5-6)
**Deep dive into FLUX internals**

- **[Module 5: FIR Pipeline](module-05-fir-pipeline.md)** — Explore the C→FIR→Bytecode→VM compilation pipeline
- **[Module 6: Fleet Patterns](module-06-fleet-patterns.md)** — Build multi-agent fleets with coordination patterns

## Learning Path

```
┌─────────────────────────────────────────────────────────────┐
│                    Module 1: Bytecode Basics                │
│  • Instruction formats (A/B/C/D/E/G)                        │
│  • Register file (R0-R15, F0-F15, V0-V15)                  │
│  • First program: MOVI + IADD + HALT                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Module 2: Control Flow                   │
│  • Jumps and branches                                       │
│  • Loop patterns                                            │
│  • Conditional execution                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Module 3: A2A Protocol                   │
│  • Message types (TELL, ASK, DELEGATE, BROADCAST)          │
│  • Trust scoring                                            │
│  • Multi-agent communication                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Module 4: Memory Regions                  │
│  • Linear memory with ownership                             │
│  • Stack operations (PUSH/POP)                              │
│  • Heap management                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Module 5: FIR Pipeline                    │
│  • SSA values and constants                                 │
│  • Building FIR programmatically                           │
│  • C to bytecode compilation                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Module 6: Fleet Patterns                 │
│  • Captain/Worker pattern                                   │
│  • Scout/Reporter pattern                                   │
│  • Consensus and voting                                     │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start Example

Here's your first FLUX program — compute 3 + 4:

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Build bytecode: 3 + 4 = 7
bytecode = (
    struct.pack("<BBh", Op.MOVI, 0, 3) +    # MOVI R0, 3
    struct.pack("<BBh", Op.MOVI, 1, 4) +    # MOVI R1, 4
    struct.pack("<BBBB", Op.IADD, 0, 0, 1) + # IADD R0, R0, R1
    bytes([Op.HALT])                        # HALT
)

# Execute
vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
print(f"Result: R0 = {vm.regs.read_gp(0)}")  # Result: R0 = 7
```

## Progress Tracking

Each module includes:
- **Concept explanations** with diagrams
- **Code examples** you can run
- **Hands-on exercises** with solutions
- **Progress checkpoints** to verify understanding

## Additional Resources

- **[User Guide](../user-guide.md)** — Complete API reference and CLI usage
- **[Developer Guide](../developer-guide.md)** — Architecture and contribution guide
- **[Agent Training Guide](../agent-training/README.md)** — Specialized guide for AI agents

## Community & Support

- GitHub: [https://github.com/SuperInstance/flux-runtime](https://github.com/SuperInstance/flux-runtime)
- Issues: [https://github.com/SuperInstance/flux-runtime/issues](https://github.com/SuperInstance/flux-runtime/issues)

## Bootcamp Goals

After completing all 6 modules, you will be able to:

1. ✅ Write FLUX bytecode programs by hand
2. ✅ Build control flow structures (loops, conditionals)
3. ✅ Implement multi-agent systems with A2A messaging
4. ✅ Manage memory regions and stack operations
5. ✅ Compile C code to FLUX bytecode
6. ✅ Design and deploy agent fleets with coordination patterns

## Certification

Complete all modules and exercises to earn your FLUX Developer certification. Submit your solutions to the FLUX community for review.

---

**Ready to begin?** Start with [Module 1: Bytecode Basics](module-01-bytecode-basics.md)
