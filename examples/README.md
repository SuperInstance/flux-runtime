# FLUX Examples

Runnable FLUX assembly programs that demonstrate the VM's instruction set.
Each `.flx` file is a complete, commented program you can assemble and execute
on any FLUX VM implementation (Python, Rust, JavaScript).

## Quick Start

```bash
# Assemble and run any example
PYTHONPATH=src python3 -c "
from flux.asm.cross_assembler import CrossAssembler, OutputFormat
from flux.vm.interpreter import Interpreter

# Read the example
source = open('examples/hello.flx').read()

# Assemble
assembler = CrossAssembler()
result = assembler.assemble(source, output_format=OutputFormat.BINARY)

# Execute
vm = Interpreter(result.bytecode)
vm.execute()

# Check results
for i in range(8):
    print(f'  R{i} = {vm.regs.read_gp(i)}')
"
```

## Examples

| File | What It Teaches | Key Opcodes |
|------|----------------|-------------|
| [`hello.flx`](hello.flx) | Minimal program. Store a value in R0 and HALT. | `MOVI`, `HALT` |
| [`fibonacci.flx`](fibonacci.flx) | First 10 Fibonacci numbers via a counting loop. | `IADD`, `MOV`, `CMP`, `JL`, `INC` |
| [`factorial.flx`](factorial.flx) | Compute 7! = 5040 with a decrementing loop. | `IMUL`, `DEC`, `JNZ` |
| [`stack_demo.flx`](stack_demo.flx) | Push 5 values, pop them back. LIFO ordering. | `PUSH`, `POP` |
| [`memory_demo.flx`](memory_demo.flx) | Store to and load from memory addresses 0–4. | `STORE`, `LOAD` |
| [`deadband.flx`](deadband.flx) | Thermostat deadband controller — the canonical PLATO/FLUX use case. | `CMP`, `JG`, `JL`, `STORE`, `LOAD` |
| [`counter.flx`](counter.flx) | Up-counter from 0 to 100. Simplest meaningful loop. | `INC`, `CMP`, `JL` |
| [`register_math.flx`](register_math.flx) | All five arithmetic ops with distinct operands. | `IADD`, `ISUB`, `IMUL`, `IDIV`, `IMOD` |

## How FLUX Programs Work

FLUX is a **register machine** — programs communicate results through registers,
not through an output stream. After a program runs, you inspect the register
file to see what it computed.

### Conventions

- **R0** is the conventional return value (like `main()` returning an int in C).
- **HALT** stops the VM. Every program must end with HALT.
- The **stack region** provides both stack space (via PUSH/POP) and general
  memory (via LOAD/STORE at low addresses).

### Instruction Formats

| Format | Size | Layout | Example |
|--------|------|--------|---------|
| A | 1 byte | `[opcode]` | `HALT` |
| B | 2 bytes | `[opcode][reg]` | `INC R0` |
| C | 3 bytes | `[opcode][rd][rs1]` | `MOV R7, R0` |
| D | 4 bytes | `[opcode][reg][imm16]` | `MOVI R0, 42` |
| E | 4 bytes | `[opcode][rd][rs1][rs2]` | `IADD R0, R0, R1` |

### Cross-Implementation Compatibility

All examples use only opcodes verified to work identically across the three
FLUX VM implementations (Python, Rust, JavaScript). The instruction subset is:

- **System:** `NOP`, `HALT`
- **Move:** `MOV`, `MOVI`
- **Arithmetic:** `IADD`, `ISUB`, `IMUL`, `IDIV`, `IMOD`, `INC`, `DEC`
- **Stack:** `PUSH`, `POP`
- **Memory:** `LOAD`, `STORE`
- **Comparison:** `CMP` (sets zero/sign flags)
- **Control flow:** `JMP`, `JZ`, `JNZ`, `JE`, `JNE`, `JG`, `JL`, `JGE`, `JLE`

## License

Same as the flux-runtime repository (MIT).
