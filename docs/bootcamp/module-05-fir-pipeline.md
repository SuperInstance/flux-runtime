> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — This module references the FIR intermediate representation, which feeds into the converged ISA encoder. See `docs/ISA_UNIFIED.md` for the canonical ISA reference.

# Module 5: FIR Pipeline — From C to Bytecode

**Learning Objectives:**
- Understand the FLUX compilation pipeline
- Learn FIR (FLUX Intermediate Representation) structure
- Build FIR programs programmatically
- Compile C code to FLUX bytecode

## Pipeline Overview

The FLUX compilation pipeline transforms high-level code into executable bytecode:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Source     │ -> │  FIR (SSA)  │ -> │  Bytecode   │ -> │     VM      │
│  (C/Python) │    │  IR         │    │  Encoder    │    │  Execution  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                       |                    ^
                       v                    |
                  ┌─────────┐          ┌─────────┐
                  │ Optimizer│          │ Decoder │
                  │ Passes   │          │ (debug) │
                  └─────────┘          └─────────┘
```

### Pipeline Stages

1. **Frontend** — Parse source code to AST
2. **FIR Builder** — Convert AST to FIR (SSA form)
3. **Optimizer** — Apply optimization passes
4. **Encoder** — Encode FIR to binary bytecode (using converged ISA v2 from `isa_unified.py`)
5. **VM** — Execute bytecode on the unified interpreter

## FIR Structure

### FIR Type System

```python
from flux.fir.types import *

# Integer types
i32 = IntType(32)
i64 = IntType(64)

# Float types
f32 = FloatType(32)
f64 = FloatType(64)

# Boolean and Unit
bool_type = BoolType()
unit_type = UnitType()

# String
string_type = StringType()

# Reference types
ref_i32 = RefType(i32)

# Array types
array_i32 = ArrayType(i32, 10)  # [i32; 10]

# Vector types (SIMD)
vec_i32 = VectorType(i32, 4)  # <4 x i32>

# Function types
func_type = FuncType([i32, i32], [i32])  # (i32, i32) -> i32

# Struct types
struct_type = StructType("point", [
    ("x", i32),
    ("y", i32)
])
```

### FIR Values

```python
from flux.fir.values import Value
from flux.fir.types import TypeContext, IntType

ctx = TypeContext()
i32 = ctx.get_int(32)

# Create constant
const_val = Value.constant(i32, 42)

# Create parameter
param_val = Value.parameter(i32, 0, "n")

# Create instruction result
result_val = Value.instruction(i32, 5, "add_result")
```

### FIR Instructions

```python
from flux.fir.instructions import *

# Arithmetic instructions (FIR-level names)
IAdd(retval, op1, op2)     # retval = op1 + op2
ISub(retval, op1, op2)     # retval = op1 - op2
IMul(retval, op1, op2)     # retval = op1 * op2

# Comparison
IEq(retval, op1, op2)      # retval = (op1 == op2)
ILt(retval, op1, op2)      # retval = (op1 < op2)

# Memory
Load(retval, ptr)          # retval = *ptr
Store(ptr, value)          # *ptr = value
Alloca(retval, type)       # retval = alloca type

# Control flow
Jump(target)               # goto target
Branch(cond, true_bb, false_bb)  # if cond goto true_bb else false_bb
Call(retval, func, args)   # retval = func(args)
Return(values)             # return values
```

> **Note:** FIR instruction names (IAdd, ISub, etc.) are at the IR level and are independent of the ISA opcode names (ADD, SUB, etc.). The encoder translates FIR names to converged ISA opcodes automatically.

## Building FIR Programs

### Example 1: Simple Function

```python
from flux.fir import TypeContext, FIRBuilder, FIRModule
from flux.fir.types import IntType
from flux.bytecode.encoder import BytecodeEncoder

# Create type context and builder
ctx = TypeContext()
builder = FIRBuilder(ctx)

# Create module
module = builder.new_module("example_module")

# Create function: int add(int a, int b)
i32 = ctx.get_int(32)
func = builder.new_function(
    module,
    "add",
    params=[("a", i32), ("b", i32)],
    returns=[i32]
)

# Create entry block
entry = builder.new_block(func, "entry")
builder.set_block(entry)

# Get parameters
a = func.params[0]  # Value for parameter 'a'
b = func.params[1]  # Value for parameter 'b'

# Create instruction: result = a + b
result = builder.iadd(a, b, name="result")

# Return result
builder.ret([result])

# Print FIR
from flux.fir.printer import print_fir
print_fir(module)

# Encode to bytecode (encoder uses converged ISA v2)
encoder = BytecodeEncoder()
bytecode = encoder.encode(module)

print(f"\nBytecode size: {len(bytecode)} bytes")
```

### Example 2: Control Flow

```python
# Function: int max(int a, int b)
from flux.fir import FIRBuilder

func = builder.new_function(
    module,
    "max",
    params=[("a", i32), ("b", i32)],
    returns=[i32]
)

# Create blocks
entry = builder.new_block(func, "entry")
then_block = builder.new_block(func, "then")
else_block = builder.new_block(func, "else")
merge_block = builder.new_block(func, "merge")

# Entry block
builder.set_block(entry)
a, b = func.params[0], func.params[1]

# Compare: if a > b
cond = builder.ilt(b, a, name="cond")  # b < a

# Branch based on condition
builder.branch(cond, then_block, else_block)

# Then block (a > b)
builder.set_block(then_block)
builder.jump(merge_block)

# Else block (a <= b)
builder.set_block(else_block)
builder.jump(merge_block)

# Merge block
builder.set_block(merge_block)
# Phi node would be inserted here by optimizer
result = builder.iadd(a, b, name="result")  # Simplified
builder.ret([result])
```

## C Frontend

### Compiling C to FIR

```python
from flux.pipeline.e2e import FluxPipeline

c_code = """
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}
"""

# Create pipeline
pipeline = FluxPipeline(optimize=True, execute=True)

# Compile C to bytecode
result = pipeline.run(c_code, lang="c", module_name="factorial")

if result.success:
    print(f"✓ Compilation successful")
    print(f"  Bytecode size: {len(result.bytecode)} bytes")
    print(f"  Cycles: {result.cycles}")
    print(f"  Halted: {result.halted}")
else:
    print(f"✗ Compilation failed:")
    for err in result.errors:
        print(f"  {err}")
```

### C Language Features Supported

| Feature | Status | Notes |
|---------|--------|-------|
| Basic types | ✅ | int, float, char, bool |
| Arithmetic | ✅ | +, -, *, /, % |
| Comparisons | ✅ | ==, !=, <, >, <=, >= |
| Control flow | ✅ | if/else, while, for |
| Functions | ✅ | Declaration, calls, returns |
| Arrays | ✅ | Fixed-size arrays |
| Structs | ✅ | Simple structs |
| Pointers | 🔄 | Basic pointer operations |

## FIR Optimization Passes

### Available Optimizations

```python
from flux.fir.optimizer import (
    DeadCodeElimination,
    ConstantPropagation,
    InlineFunctions,
    LoopUnroll
)

# Create optimizer
optimizer = FIROptimizer()

# Register passes
optimizer.add_pass(DeadCodeElimination())
optimizer.add_pass(ConstantPropagation())
optimizer.add_pass(InlineFunctions(max_size=10))
optimizer.add_pass(LoopUnroll(factor=4))

# Optimize module
optimized_module = optimizer.optimize(module)

# Compare sizes
print(f"Original: {encoder.encode(module).size()} bytes")
print(f"Optimized: {encoder.encode(optimized_module).size()} bytes")
```

## Exercise: Compile a C Function

**Task:** Write a C function to compute Fibonacci numbers and compile it to FLUX bytecode.

**Requirements:**
- Function signature: `int fib(int n)`
- Use iterative approach (not recursive)
- Compile and execute in VM

**Solution:**

```python
from flux.pipeline.e2e import FluxPipeline

c_code = """
int fib(int n) {
    if (n <= 1) {
        return n;
    }
    int a = 0;
    int b = 1;
    for (int i = 2; i <= n; i++) {
        int temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}
"""

# Compile
pipeline = FluxPipeline(optimize=True, execute=True)
result = pipeline.run(c_code, lang="c", module_name="fib")

if result.success:
    print(f"✓ Compiled successfully")
    print(f"  Bytecode: {len(result.bytecode)} bytes")

    # Test with different inputs
    for n in [0, 1, 5, 10, 15]:
        # Would need to set up VM with input parameter
        # For demo, just show compilation success
        print(f"  Input: {n}")
else:
    print(f"✗ Compilation failed:")
    for err in result.errors:
        print(f"  {err}")
```

## Advanced: Custom FIR Pass

```python
from flux.fir import FIRModule, FIRVisitor

class MyOptimizer(FIRVisitor):
    """Custom FIR optimization pass."""

    def visit_iadd(self, instr):
        """Optimize ADD instructions."""
        # Example: x + 0 -> x
        if isinstance(instr.op2, Value) and instr.op2.is_constant:
            if instr.op2.constant_value == 0:
                # Replace with MOV (encoder maps to MOV opcode 0x3A)
                return MOV(instr.retval, instr.op1)
        return instr

    def optimize(self, module: FIRModule) -> FIRModule:
        """Run optimization pass on module."""
        for func in module.functions.values():
            for block in func.blocks:
                new_instrs = []
                for instr in block.instructions:
                    optimized = self.visit(instr)
                    new_instrs.append(optimized)
                block.instructions = new_instrs
        return module

# Usage
optimizer = MyOptimizer()
optimized_module = optimizer.optimize(module)
```

## Debugging FIR

### Print FIR IR

```python
from flux.fir.printer import print_fir

# Print human-readable FIR
print_fir(module)

# Output example:
# module "example_module"
#   function "add"(a: i32, b: i32) -> i32
#     block "entry":
#       %result = iadd %a, %b
#       ret %result
```

### Validate FIR

```python
from flux.fir.validator import FIRValidator

validator = FIRValidator()
errors = validator.validate(module)

if errors:
    print("FIR validation errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✓ FIR is valid")
```

## Progress Checkpoint

At the end of Module 5, you should be able to:

- ✅ Understand the FLUX compilation pipeline stages
- ✅ Work with FIR types, values, and instructions
- ✅ Build FIR programs programmatically
- ✅ Compile C code to FLUX bytecode
- ✅ Apply optimization passes
- ✅ Debug and validate FIR IR

## Next Steps

**[Module 6: Fleet Patterns](module-06-fleet-patterns.md)** — Learn multi-agent fleet coordination patterns.

---

**Need Help?** See the [FIR Reference](../user-guide.md#fir-intermediate-representation) for complete FIR API documentation.
