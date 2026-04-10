# FLUX User Guide

Complete guide for using the FLUX runtime, from installation to advanced features.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Using the REPL](#using-the-repl)
4. [Using the Debugger](#using-the-debugger)
5. [Running Fleet Simulations](#running-fleet-simulations)
6. [Python API Reference](#python-api-reference)
7. [CLI Commands Reference](#cli-commands-reference)
8. [Language Bindings](#language-bindings)
9. [Troubleshooting](#troubleshooting)

## Installation

### Requirements

- Python 3.10 or higher
- No external dependencies (stdlib only)

### Install via pip

```bash
pip install flux-runtime
```

### Install from Source

```bash
git clone https://github.com/SuperInstance/flux-runtime.git
cd flux-runtime
pip install -e .
```

### Verify Installation

```bash
flux --version
# FLUX Runtime v1.0.0

flux hello
# Should run the hello world demo
```

## Quick Start

### Your First FLUX Program

Create a file `hello.flux`:

```python
# Compute: 3 + 4 = 7
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Build bytecode
bytecode = (
    struct.pack("<BBh", Op.MOVI, 0, 3) +    # MOVI R0, 3
    struct.pack("<BBh", Op.MOVI, 1, 4) +    # MOVI R1, 4
    struct.pack("<BBBB", Op.IADD, 0, 0, 1) + # IADD R0, R0, R1
    bytes([Op.HALT])                        # HALT
)

# Execute
vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
print(f"Result: {vm.regs.read_gp(0)}")
```

Run it:

```bash
python hello.flux
# Result: 7
```

### Compile C to FLUX

Create `add.c`:

```c
int add(int a, int b) {
    return a + b;
}
```

Compile and run:

```bash
flux compile add.c -o add.bin
flux run add.bin
```

## Using the REPL

The FLUX REPL provides an interactive environment for writing and testing bytecode.

### Starting the REPL

```bash
flux repl
```

### REPL Commands

```
FLUX REPL v1.0.0
Type 'help' for available commands

flux> help
Available commands:
  help              Show this help message
  quit              Exit the REPL
  reset             Reset VM state
  dump              Show register and memory state
  disasm [n]        Disassemble last n instructions
  load <file>       Load bytecode from file
  run               Execute bytecode
  step              Execute single instruction
  regs              Show register values
  stack             Show stack contents
  mem <addr> [n]    Show n bytes of memory at addr

flux> MOVI R0, 42
flux> MOVI R1, 10
flux> IADD R0, R0, R1
flux> HALT
flux> run
Executed 4 cycles
flux> regs
R0  = 52
R1  = 10
flux> dump
{
  "pc": 13,
  "cycle_count": 4,
  "registers": {...},
  "flag_zero": false,
  "flag_sign": false
}
flux> quit
```

### REPL Scripting

You can also run REPL scripts:

```bash
flux repl script.fluxrepl
```

Example script file:

```
# Compute factorial
MOVI R0, 1    # result
MOVI R1, 5    # counter
loop:
  IMUL R0, R0, R1
  DEC R1
  JNZ R1, loop
HALT
run
regs
quit
```

## Using the Debugger

The FLUX debugger provides step-by-step execution and inspection.

### Starting the Debugger

```bash
flux debug program.bin
```

### Debugger Commands

```
FLUX Debugger v1.0.0

Loaded program.bin (123 bytes)

(debug) help
Available commands:
  help              Show this help message
  quit              Exit debugger
  run               Run until breakpoint or end
  step              Execute one instruction
  next              Execute one instruction (skip calls)
  continue          Continue execution
  break <addr>      Set breakpoint at address
  delete <n>        Delete breakpoint n
  list              List breakpoints
  regs              Show registers
  flags             Show condition flags
  stack [n]         Show n stack entries
  mem <addr> [n]    Show n bytes at address
  disasm [addr] n   Disassemble n instructions at addr
  info              Show program info

(debug) break 8
Breakpoint 1 at 0x08

(debug) run
Breakpoint 1 hit at PC=0x08

(debug) regs
R0  = 3
R1  = 4

(debug) step

(debug) regs
R0  = 7
R1  = 4

(debug) quit
```

### Conditional Breakpoints

```
(debug) break 0x10 if R0 > 100
Breakpoint 2 at 0x10 (condition: R0 > 100)
```

### Watchpoints

```
(debug) watch R0
Watching register R0

(debug) watch *0x1000
Watching memory address 0x1000
```

## Running Fleet Simulations

FLUX includes a fleet simulator for multi-agent systems.

### Basic Fleet Simulation

```bash
flux fleet --agents 5 --timesteps 100
```

### Custom Fleet Configuration

Create `fleet_config.yaml`:

```yaml
name: "My Fleet"
agents:
  - name: "Navigator"
    bytecode: "navigator.bin"
    type: "navigation"

  - name: "Scout"
    bytecode: "scout.bin"
    type: "reconnaissance"
    count: 3

  - name: "Worker"
    bytecode: "worker.bin"
    type: "processing"
    count: 5

simulation:
  timesteps: 1000
  environment: "ocean"
  metrics:
    - "efficiency"
    - "communication"
    - "resource_usage"
```

Run simulation:

```bash
flux fleet --config fleet_config.yaml
```

### Fleet Simulation Output

```
FLUX Fleet Simulator v1.0.0

=== Initializing Fleet ===
Navigator: uuid-123...
Scout-1: uuid-456...
Scout-2: uuid-789...
Scout-3: uuid-abc...
Worker-1: uuid-def...
Worker-2: uuid-012...
Worker-3: uuid-345...
Worker-4: uuid-678...
Worker-5: uuid-901...

=== Running Simulation ===

Timestep 1/1000:
  Navigator: Heading adjusted 45° → 50°
  Scout-1: Detected resources at (100, 200)
  Worker-1: Processing task 1
  ...

=== Simulation Complete ===

Final Report:
  Duration: 1000 timesteps
  Total Messages: 5234
  Average Trust: 785/1000
  Efficiency: 94.2%
```

## Python API Reference

### Core Classes

#### Interpreter

```python
from flux.vm.interpreter import Interpreter

vm = Interpreter(
    bytecode=bytes([...]),
    memory_size=65536,
    max_cycles=1000000
)

# Execute
cycles = vm.execute()

# Inspect state
result = vm.regs.read_gp(0)
sp = vm.regs.sp
fp = vm.regs.fp

# Reset
vm.reset()
```

#### RegisterFile

```python
from flux.vm.registers import RegisterFile

regs = RegisterFile()

# General-purpose
regs.write_gp(0, 42)
value = regs.read_gp(0)

# Floating-point
regs.write_fp(0, 3.14)
fvalue = regs.read_fp(0)

# Vector
regs.write_vec(0, bytes(range(16)))
vvalue = regs.read_vec(0)

# Special registers
regs.sp = 4096
regs.fp = 4000
regs.lr = 0x100
```

#### MemoryManager

```python
from flux.vm.memory import MemoryManager

memory = MemoryManager()

# Create region
region = memory.create_region("heap", 65536, "user")

# Read/write
region.write_i32(0, 42)
value = region.read_i32(0)

# Destroy region
memory.destroy_region("heap")
```

### A2A Protocol

#### A2AMessage

```python
from flux.a2a.messages import A2AMessage
from flux.bytecode.opcodes import Op
import uuid

msg = A2AMessage(
    sender=uuid.uuid4(),
    receiver=uuid.uuid4(),
    conversation_id=uuid.uuid4(),
    in_reply_to=None,
    message_type=Op.TELL,
    priority=5,
    trust_token=750,
    capability_token=100,
    payload=b"Hello, world!"
)

# Serialize
raw = msg.to_bytes()

# Deserialize
msg2 = A2AMessage.from_bytes(raw)
```

#### TrustEngine

```python
from flux.a2a.trust import TrustEngine, InteractionRecord

trust = TrustEngine()

# Update trust
record = InteractionRecord(
    agent_id=uuid.uuid4(),
    outcome="success",
    timestamp=time.time(),
    operation="data_request"
)
trust.update_trust(record.agent_id, record)

# Query trust
score = trust.get_trust_score(agent_id)
```

### FIR Builder

```python
from flux.fir import TypeContext, FIRBuilder
from flux.fir.types import IntType

ctx = TypeContext()
builder = FIRBuilder(ctx)

# Create module
module = builder.new_module("my_module")

# Create function
i32 = ctx.get_int(32)
func = builder.new_function(
    module,
    "add",
    params=[("a", i32), ("b", i32)],
    returns=[i32]
)

# Create block
entry = builder.new_block(func, "entry")
builder.set_block(entry)

# Add instructions
a, b = func.params[0], func.params[1]
result = builder.iadd(a, b, name="result")
builder.ret([result])
```

### Bytecode Encoder

```python
from flux.bytecode.encoder import BytecodeEncoder

encoder = BytecodeEncoder()
bytecode = encoder.encode(module)

# Save to file
with open("output.bin", "wb") as f:
    f.write(bytecode)
```

## CLI Commands Reference

### flux compile

Compile source code to bytecode.

```bash
flux compile <input> -o <output> [options]

Options:
  -o, --output <file>     Output file
  -O, --optimize         Enable optimizations
  -v, --verbose          Verbose output
  --format <fmt>         Output format (bin, hex, json)
  --target <arch>        Target architecture (x86, arm)

Examples:
  flux compile program.c -o program.bin
  flux compile script.py -o script.bin -O
  flux compile module.md -o module.bin --verbose
```

### flux run

Execute bytecode in the VM.

```bash
flux run <bytecode> [options]

Options:
  -c, --cycles <n>       Cycle budget (default: 10M)
  -m, --memory <size>    Memory size in KB (default: 64)
  -p, --profile          Enable profiling
  -t, --trace            Enable instruction tracing
  -d, --debug            Start in debug mode

Examples:
  flux run program.bin
  flux run program.bin --cycles 1000000
  flux run program.bin --profile --trace
```

### flux test

Run the test suite.

```bash
flux test [options]

Options:
  -v, --verbose          Verbose output
  -k, --keyword <pat>    Run tests matching pattern
  --cov                  Enable coverage report
  --failfast             Stop on first failure

Examples:
  flux test
  flux test -v
  flux test -k "test_a2a"
```

### flux migrate

Migrate existing code to FLUX.

```bash
flux migrate <path> [options]

Options:
  -o, --output-dir <dir> Output directory
  -l, --lang <lang>      Source language
  --recursive            Process directories recursively
  --verbose              Verbose output

Examples:
  flux migrate src/ --output-dir ./flux_output
  flux migrate program.py --lang python
  flux migrate project/ --recursive
```

### flux version

Show version information.

```bash
flux version

# Output:
# FLUX Runtime v1.0.0
# Python 3.10.0
# VM: 64 registers, 100+ opcodes
```

## Language Bindings

### Python

```python
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op

# See Python API Reference above
```

### C (via FFI)

```c
#include "flux.h"

int main() {
    flux_vm *vm = flux_vm_new();
    flux_bytecode *code = flux_compile_c("int x = 42;");
    flux_vm_load(vm, code);
    flux_vm_execute(vm);
    flux_vm_free(vm);
    return 0;
}
```

### Rust (via bindings)

```rust
use flux_runtime::{Interpreter, Opcode};

fn main() {
    let mut vm = Interpreter::new();
    vm.load_bytecode(&[0x2B, 0x00, 0x2A, 0x00, 0x80]);
    vm.execute();
    println!("Result: {}", vm.registers()[0]);
}
```

## Troubleshooting

### Common Issues

#### Import Errors

```bash
# Error: ModuleNotFoundError: No module named 'flux'

# Solution: Install FLUX or set PYTHONPATH
pip install flux-runtime
# OR
export PYTHONPATH=/path/to/flux-runtime/src
```

#### Memory Errors

```bash
# Error: MemoryError: Stack overflow

# Solution: Increase memory size
vm = Interpreter(bytecode, memory_size=131072)  # 128KB
```

#### Cycle Budget Exceeded

```bash
# Error: Cycle budget exceeded

# Solution: Increase max_cycles
vm = Interpreter(bytecode, max_cycles=100000000)
```

### Debug Mode

Enable debug output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
```

### Performance Issues

1. **Profile your code**:
```bash
flux run program.bin --profile
```

2. **Enable optimizations**:
```bash
flux compile program.c -o program.bin -O
```

3. **Check hot paths**:
```python
from flux.adaptive.profiler import Profiler

profiler = Profiler()
profiler.start()
vm.execute()
profiler.stop()
print(profiler.hot_opcodes())
```

## Getting Help

### Documentation

- **Bootcamp**: [docs/bootcamp/README.md](bootcamp/README.md)
- **Developer Guide**: [docs/developer-guide.md](developer-guide.md)
- **Agent Training**: [docs/agent-training/README.md](agent-training/README.md)

### Community

- **GitHub**: [https://github.com/SuperInstance/flux-runtime](https://github.com/SuperInstance/flux-runtime)
- **Issues**: [https://github.com/SuperInstance/flux-runtime/issues](https://github.com/SuperInstance/flux-runtime/issues)
- **Discussions**: [https://github.com/SuperInstance/flux-runtime/discussions](https://github.com/SuperInstance/flux-runtime/discussions)

### Examples

See the `examples/` directory for complete working examples:
- `01_hello_world.py` — Three ways to run FLUX
- `02_polyglot.py` — Mix C and Python
- `03_a2a_agents.py` — Agent communication
- `04_adaptive_profiling.py` — Performance profiling
- `05_tile_composition.py` — Composable patterns
- `06_evolution.py` — Self-improvement engine
- `07_full_synthesis.py` — Complete system

---

**Happy FLUX coding!** 🚀
