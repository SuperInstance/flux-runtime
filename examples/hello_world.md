---
title: FLUX.MD Hello World
version: 1.0
author: FLUX Team
description: The flagship example — markdown that becomes bytecode
---

# FLUX.MD Hello World

Welcome to FLUX — a system where **markdown documents become executable bytecode**.
This file is a living program: the text you're reading is documentation, and the
code blocks below are compilable source that gets turned into FLUX bytecode
and run on the Micro-VM.

## What is FLUX.MD?

FLUX.MD is a literate programming format. It combines:

- **Human-readable documentation** (what you're reading now)
- **Executable code blocks** in C, Python, or native FLUX IR
- **Data blocks** in JSON/YAML for configuration
- **Agent directives** for multi-agent coordination

The compiler extracts the code blocks, runs them through the appropriate
frontend (C compiler, Python compiler), lowers to FIR (FLUX Intermediate
Representation), optimizes, and emits bytecode for the FLUX Micro-VM.

## Architecture: The 6-Layer Stack

```
  Layer 1: FLUX.MD (this file)
      ↓  Parser extracts NativeBlocks
  Layer 2: FIR Builder (SSA IR)
      ↓  Optimizer passes
  Layer 3: Bytecode Encoder
      ↓  Binary output
  Layer 4: A2A Protocol (agent communication)
      ↓  Trust engine + message routing
  Layer 5: FLUX Micro-VM (fetch-decode-execute)
      ↓  Register file + memory regions
  Layer 6: Runtime (agents, hot-reload, evolution)
```

## Our First Program: Adding Two Numbers

The simplest FLUX program adds two numbers. Here it is in C:

```c
int add(int a, int b) {
    return a + b;
}

int main() {
    int result = add(10, 20);
    return result;
}
```

When this FLUX.MD file is compiled, the parser extracts the C code block,
compiles it through the C frontend (tokenizer → recursive descent parser →
FIR codegen), and emits bytecode. The VM executes it and `R0` contains `30`.

### What happens under the hood?

1. **Parser**: `FluxMDParser.parse(source)` → `FluxModule` AST
2. **Extract**: Finds the `NativeBlock` with `lang="c"`
3. **Compile**: `CFrontendCompiler.compile(c_source)` → `FIRModule`
4. **Optimize**: Constant folding, dead code elimination
5. **Encode**: `BytecodeEncoder.encode(module)` → `bytes` (FLUX binary)
6. **Execute**: `Interpreter(code_section).execute()` → register state

## The Same Program in Python

FLUX is polyglot — you can write in Python too:

```python
def add(a, b):
    return a + b

def main():
    result = add(10, 20)
    return result
```

Both the C and Python versions compile to the same FIR intermediate
representation and produce equivalent bytecode.

## Bytecode Format

The compiled output is a binary file with this structure:

```
Offset  Size   Field
  0       4    Magic: b'FLUX'
  4       2    Version (uint16 LE)
  6       2    Flags (uint16 LE)
  8       2    Function count (uint16 LE)
 10       4    Type table offset (uint32 LE)
 14       4    Code section offset (uint32 LE)
 ...     ...   Type table → Name pool → Function table → Code section
```

## The VM Register File

The FLUX Micro-VM has 64 registers organized into three banks:

| Bank | Registers | Purpose |
|------|-----------|---------|
| GP   | R0–R15    | General-purpose integer arithmetic |
| FP   | F0–F15    | Floating-point operations |
| VEC  | V0–V15    | SIMD vector operations |

Special registers: SP (R11), FP (R14), LR (R15).

## Opcode Highlights

FLUX has 100+ opcodes across 12 categories:

- **Control flow**: `NOP`, `HALT`, `JMP`, `JZ`, `JNZ`, `CALL`, `RET`
- **Integer arithmetic**: `IADD`, `ISUB`, `IMUL`, `IDIV`, `IMOD`
- **Bitwise**: `IAND`, `IOR`, `IXOR`, `ISHL`, `ISHR`
- **Comparison**: `CMP`, `IEQ`, `ILT`, `IGT`, `ILE`, `IGE`
- **Stack**: `PUSH`, `POP`, `DUP`, `SWAP`, `ENTER`, `LEAVE`
- **Float**: `FADD`, `FSUB`, `FMUL`, `FDIV`, `FNEG`
- **SIMD**: `VLOAD`, `VSTORE`, `VADD`, `VSUB`, `VMUL`
- **A2A Protocol**: `TELL`, `ASK`, `DELEGATE`, `BROADCAST`
- **Trust**: `TRUST_CHECK`, `TRUST_UPDATE`, `CAP_REQUIRE`
- **System**: `HALT`, `YIELD`, `DEBUG_BREAK`

## Try It Yourself

Compile this file and run it:

```bash
cd /home/z/my-project/flux-py
source .venv/bin/activate
PYTHONPATH=src python3 -c "
from flux.pipeline.e2e import FluxPipeline
pipeline = FluxPipeline()
result = pipeline.run(open('examples/hello_world.md').read(), lang='md')
print(f'Cycles: {result.cycles}, Halted: {result.halted}')
"
```

## What's Next?

- `QUICKSTART.md` — Step-by-step getting started guide
- `02_polyglot_add.md` — Mixing C and Python in one document
- `03_fibonacci.md` — Fibonacci with bytecode traces
- `04_agent_handshake.md` — Agent-to-agent communication
- `05_bytecode_playground.py` — Interactive REPL
