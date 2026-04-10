# FLUX Developer Guide

Complete developer reference for contributing to and extending the FLUX runtime.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Adding New Opcodes](#adding-new-opcodes)
4. [Adding Instruction Formats](#adding-instruction-formats)
5. [Extending A2A Protocol](#extending-a2a-protocol)
6. [Building Custom Frontends](#building-custom-frontends)
7. [Testing Patterns](#testing-patterns)
8. [Performance Tuning](#performance-tuning)
9. [Development Workflow](#development-workflow)

## Architecture Overview

FLUX is organized in layers:

```
┌─────────────────────────────────────────────────────────┐
│  TIER 8: SYNTHESIS — FluxSynthesizer                   │
│  Integrates all subsystems                             │
├─────────────────────────────────────────────────────────┤
│  TIER 7: MODULES — Hot-reload system                   │
│  8-level fractal module management                    │
├─────────────────────────────────────────────────────────┤
│  TIER 6A: ADAPTIVE  │  TIER 6B: EVOLUTION             │
│  Profiler + Selector│  Genome + Mutator                │
├─────────────────────────────────────────────────────────┤
│  TIER 5: TILES — 35 composable patterns                │
├─────────────────────────────────────────────────────────┤
│  TIER 4: AGENT RUNTIME — Trust, scheduling, resources  │
├─────────────────────────────────────────────────────────┤
│  TIER 3: A2A PROTOCOL — 32 messaging opcodes           │
├─────────────────────────────────────────────────────────┤
│  TIER 2: SUPPORT — Optimizer, JIT, Types, Stdlib, Sec  │
├─────────────────────────────────────────────────────────┤
│  TIER 1: CORE — Parser → FIR → Bytecode → VM          │
└─────────────────────────────────────────────────────────┘
```

## Project Structure

```
flux-runtime/
├── src/flux/
│   ├── bytecode/          # Bytecode encoding/decoding
│   │   ├── opcodes.py     # Opcode definitions
│   │   ├── encoder.py     # FIR → Bytecode
│   │   ├── decoder.py     # Bytecode → Structured
│   │   └── validator.py   # Bytecode validation
│   ├── vm/                # Virtual Machine
│   │   ├── interpreter.py # Main VM execution
│   │   ├── registers.py   # Register file
│   │   └── memory.py      # Memory manager
│   ├── fir/               # Intermediate Representation
│   │   ├── types.py       # FIR type system
│   │   ├── values.py      # SSA values
│   │   ├── instructions.py# FIR instructions
│   │   ├── blocks.py      # Blocks, functions, modules
│   │   ├── builder.py     # FIR construction API
│   │   ├── validator.py   # FIR validation
│   │   └── printer.py     # FIR pretty-printer
│   ├── a2a/               # Agent-to-Agent protocol
│   │   ├── messages.py    # A2A message format
│   │   ├── transport.py   # Message transport
│   │   ├── trust.py       # Trust engine
│   │   └── coordinator.py # Multi-agent orchestration
│   ├── parser/            # Language parsers
│   ├── pipeline/          # Compilation pipelines
│   ├── jit/               # JIT compilation
│   └── adaptive/          # Adaptive profiling
├── tests/                 # Test suite (1848 tests)
├── examples/              # Example programs
└── tools/                 # Development tools
```

## Adding New Opcodes

### Step 1: Define Opcode

Add to `src/flux/bytecode/opcodes.py`:

```python
class Op(IntEnum):
    # ... existing opcodes ...

    # New opcode in appropriate range
    MY_NEW_OP = 0x9F  # System opcode range: 0x80-0x9F
```

### Step 2: Specify Format

Add to format classification in `opcodes.py`:

```python
# Format classification
FORMAT_C = frozenset({
    # ... existing ...
    Op.MY_NEW_OP,  # Add to appropriate format
})
```

### Step 3: Implement in VM

Add to `src/flux/vm/interpreter.py` in `_step()` method:

```python
def _step(self) -> None:
    """Fetch, decode, and execute one instruction."""
    start_pc = self.pc
    opcode_byte = self._fetch_u8()

    # ... existing cases ...

    # ── Your New Opcode ─────────────────────────────────
    if opcode_byte == Op.MY_NEW_OP:
        # Decode operands based on format
        rd, rs1 = self._decode_operands_C()

        # Execute operation
        result = self.regs.read_gp(rd) + self.regs.read_gp(rs1)
        self.regs.write_gp(rd, result)

        return

    # ... rest of cases ...
```

### Step 4: Add FIR Instruction

Add to `src/flux/fir/instructions.py`:

```python
class MyNewInstruction(Instruction):
    """My new instruction."""

    def __init__(self, retval: Value, operand: Value):
        super().__init__("my_new_op", [retval], [operand])
        self.retval = retval
        self.operand = operand

    def __str__(self) -> str:
        return f"{self.retval} = MY_NEW_OP {self.operand}"
```

### Step 5: Update Encoder

Add encoding logic to `src/flux/bytecode/encoder.py`:

```python
def encode_instruction(self, instr: Instruction) -> bytes:
    """Encode a FIR instruction to bytecode."""
    if isinstance(instr, MyNewInstruction):
        # Encode as Format C
        rd = self.register_map[instr.retval]
        rs1 = self.register_map[instr.operand]
        return bytes([Op.MY_NEW_OP, rd, rs1])
    # ... other cases ...
```

### Step 6: Write Tests

Add to `tests/test_opcodes.py`:

```python
def test_my_new_op():
    """Test MY_NEW_OP opcode."""
    from flux.bytecode.opcodes import Op
    import struct

    # Create bytecode
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 10) +
        struct.pack("<BBh", Op.MOVI, 1, 20) +
        struct.pack("<BBB", Op.MY_NEW_OP, 0, 1) +
        bytes([Op.HALT])
    )

    # Execute
    vm = Interpreter(bytecode, memory_size=4096)
    vm.execute()

    # Verify
    assert vm.regs.read_gp(0) == 30  # 10 + 20
```

## Adding Instruction Formats

### Current Formats

- **Format A** (1 byte): `[opcode]`
- **Format B** (2 bytes): `[opcode][reg]`
- **Format C** (3 bytes): `[opcode][rd][rs1]`
- **Format D** (4 bytes): `[opcode][reg][off_lo][off_hi]`
- **Format E** (4 bytes): `[opcode][rd][rs1][rs2]`
- **Format G** (variable): `[opcode][len_lo][len_hi][data...]`

### Adding Format F (Hypothetical 5-byte format)

1. Update `opcodes.py`:

```python
def get_format(op: Op) -> str:
    """Return the encoding format letter for an opcode."""
    # ... existing cases ...
    if op in FORMAT_F:
        return "F"
    return "C"  # default

def instruction_size(op: Op) -> int:
    """Return the fixed size in bytes for an opcode (or -1 for variable)."""
    fmt = get_format(op)
    return {"A": 1, "B": 2, "C": 3, "D": 4, "E": 4, "F": 5}.get(fmt, -1)
```

2. Add decoder in `interpreter.py`:

```python
def _decode_operands_F(self) -> tuple[int, int, int, int]:
    """Four registers: rd, rs1, rs2, rs3 (Format F)."""
    rd = self._fetch_u8()
    rs1 = self._fetch_u8()
    rs2 = self._fetch_u8()
    rs3 = self._fetch_u8()
    return (rd, rs1, rs2, rs3)
```

3. Update encoder to use Format F.

## Extending A2A Protocol

### Adding New Message Types

1. Add opcode to `opcodes.py`:

```python
class Op(IntEnum):
    # ... existing A2A opcodes ...
    MY_A2A_OP = 0x7C  # Next available A2A opcode
```

2. Add to FORMAT_G set (A2A messages are variable length):

```python
FORMAT_G = frozenset({
    # ... existing ...
    Op.MY_A2A_OP,
})
```

3. Implement handler in `interpreter.py`:

```python
if opcode_byte == Op.MY_A2A_OP:
    data = self._fetch_var_data()
    self._dispatch_a2a("MY_A2A_OP", data)
    return
```

4. Add to messages.py if custom structure needed:

```python
class MyA2AMessage(A2AMessage):
    """Custom A2A message with additional fields."""

    def __init__(self, sender, receiver, custom_field, **kwargs):
        super().__init__(sender, receiver, **kwargs)
        self.custom_field = custom_field
```

### Extending Trust Engine

Add new trust calculation methods to `src/flux/a2a/trust.py`:

```python
class TrustEngine:
    # ... existing methods ...

    def calculate_trust_with_decay(
        self,
        agent_id: UUID,
        interaction: InteractionRecord,
        decay_rate: float = 0.1
    ) -> int:
        """Calculate trust with time-based decay."""
        current_score = self.get_trust_score(agent_id)
        time_delta = time.time() - interaction.timestamp

        # Apply decay
        decayed_score = int(current_score * (1 - decay_rate) ** time_delta)

        # Update with interaction
        return self._update_trust(agent_id, decayed_score, interaction)
```

## Building Custom Frontends

### Frontend Architecture

```
Source Code → Parser → AST → FIR Builder → FIR Module → Bytecode
```

### Example: Lisp Frontend

1. Create parser (`src/flux/parser/lisp_parser.py`):

```python
from flux.parser.parser import Parser
from flux.fir import FIRBuilder, TypeContext

class LispParser(Parser):
    """Parse Lisp-like syntax to FIR."""

    def parse(self, source: str) -> FIRModule:
        """Parse Lisp source code."""
        ctx = TypeContext()
        builder = FIRBuilder(ctx)
        module = builder.new_module("lisp_module")

        # Parse Lisp expressions
        # (defun factorial (n)
        #   (if (<= n 1)
        #       1
        #       (* n (factorial (- n 1)))))

        # Convert to FIR...
        return module
```

2. Integrate with pipeline:

```python
from flux.pipeline.e2e import FluxPipeline

class LispPipeline(FluxPipeline):
    """Pipeline for Lisp compilation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parser = LispParser()

    def run(self, source: str, lang: str = "lisp", **kwargs):
        """Compile Lisp source."""
        if lang != "lisp":
            return super().run(source, lang, **kwargs)

        # Parse Lisp to FIR
        fir_module = self.parser.parse(source)

        # Encode to bytecode
        bytecode = self.encoder.encode(fir_module)

        return PipelineResult(
            success=True,
            bytecode=bytecode,
            # ... other fields ...
        )
```

## Testing Patterns

### Unit Tests

```python
import pytest
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op
import struct

def test_arithmetic():
    """Test integer arithmetic operations."""
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 10) +
        struct.pack("<BBh", Op.MOVI, 1, 20) +
        struct.pack("<BBBB", Op.IADD, 0, 0, 1) +
        bytes([Op.HALT])
    )

    vm = Interpreter(bytecode, memory_size=4096)
    vm.execute()

    assert vm.regs.read_gp(0) == 30

def test_stack_operations():
    """Test stack push/pop."""
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 42) +
        struct.pack("<BB", Op.PUSH, 0) +
        struct.pack("<BB", Op.POP, 1) +
        bytes([Op.HALT])
    )

    vm = Interpreter(bytecode, memory_size=4096)
    vm.execute()

    assert vm.regs.read_gp(0) == 42
    assert vm.regs.read_gp(1) == 42
```

### Integration Tests

```python
def test_full_pipeline():
    """Test complete C to bytecode pipeline."""
    c_code = """
    int add(int a, int b) {
        return a + b;
    }
    """

    pipeline = FluxPipeline(optimize=True)
    result = pipeline.run(c_code, lang="c")

    assert result.success
    assert result.bytecode is not None
    assert len(result.bytecode) > 0
```

### Performance Tests

```python
def test_performance():
    """Test VM performance (ops/sec)."""
    import time

    # Generate test bytecode
    bytecode = bytearray()
    for _ in range(10000):
        bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))
    bytecode.extend(bytes([Op.HALT]))

    vm = Interpreter(bytes(bytecode), memory_size=4096)

    start = time.time()
    vm.execute()
    elapsed = time.time() - start

    ops_per_sec = 10000 / elapsed
    assert ops_per_sec > 10000  # Should be > 10K ops/sec
```

## Performance Tuning

### Optimization Targets

- **ARM**: 48K+ ops/sec
- **x86_64**: 60K+ ops/sec
- **Memory**: < 10MB for typical workload

### Profiling

```python
from flux.adaptive.profiler import Profiler

profiler = Profiler()
profiler.start()

# Run workload
vm.execute()

profiler.stop()
stats = profiler.get_stats()

print(f"Hot opcodes: {stats.hot_opcodes}")
print(f"Cycles per opcode: {stats.cycles_per_opcode}")
```

### Common Optimizations

1. **Opcode dispatch**: Use computed gotos (if supported)
2. **Register access**: Direct list indexing
3. **Memory operations**: Batch reads/writes
4. **JIT compilation**: Hot paths to native code

### JIT Compilation

```python
from flux.jit.compiler import JITCompiler

jit = JITCompiler()

# Compile hot function
jit.compile_function(module, "hot_function")

# Execute compiled code
result = jit.execute("hot_function", args)
```

## Development Workflow

### Setting Up Environment

```bash
# Clone repository
git clone https://github.com/SuperInstance/flux-runtime.git
cd flux-runtime

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/flux --cov-report=html
```

### Code Style

FLUX follows PEP 8 with additional conventions:

```python
# Good
def calculate_fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)

# Avoid
def fib(n):
    # What does this do?
    return fib(n-1)+fib(n-2) if n>1 else n
```

### Commit Guidelines

```
feat: add new opcode for matrix multiplication
fix: correct stack overflow in ENTER instruction
docs: update architecture diagram
test: add tests for A2A protocol
perf: optimize register file access
refactor: clean up FIR instruction hierarchy
```

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Ensure all tests pass (`pytest tests/`)
5. Submit PR with description

## Contributing Areas

### High Priority

- [ ] Additional frontend languages (Rust, Go, TypeScript)
- [ ] SIMD optimization for vector ops
- [ ] WebAssembly backend
- [ ] Debugger UI

### Medium Priority

- [ ] Standard library expansion
- [ ] Memory safety improvements
- [ ] Performance profiling tools
- [ ] Documentation improvements

### Low Priority

- [ ] Alternative VM implementations
- [ ] Experimental features
- [ ] Educational resources

## Resources

- **GitHub**: [https://github.com/SuperInstance/flux-runtime](https://github.com/SuperInstance/flux-runtime)
- **Issues**: [https://github.com/SuperInstance/flux-runtime/issues](https://github.com/SuperInstance/flux-runtime/issues)
- **Discussions**: [https://github.com/SuperInstance/flux-runtime/discussions](https://github.com/SuperInstance/flux-runtime/discussions)

## License

MIT License — See LICENSE file for details.

---

**Ready to contribute?** Start with [good first issues](https://github.com/SuperInstance/flux-runtime/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
