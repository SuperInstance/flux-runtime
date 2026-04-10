# FLUX Agent Training Guide

Specialized guide for AI agents learning to generate and optimize FLUX bytecode.

## Overview

This guide helps AI agents understand how to:
1. Generate valid FLUX bytecode
2. Apply common bytecode patterns
3. Optimize bytecode for efficiency
4. Implement A2A communication
5. Write self-modifying code

## Bytecode Generation Fundamentals

### Instruction Format Reference

```python
# Format A (1 byte): [opcode]
HALT = bytes([0x80])
NOP = bytes([0x00])

# Format B (2 bytes): [opcode][reg]
INC_R0 = bytes([0x0E, 0x00])  # INC R0

# Format C (3 bytes): [opcode][rd][rs1]
MOV_R0_R1 = bytes([0x01, 0x00, 0x01])  # MOV R0, R1

# Format D (4 bytes): [opcode][reg][off_lo][off_hi]
MOVI_R0_42 = bytes([0x2B, 0x00, 0x2A, 0x00])  # MOVI R0, 42
JMP_BACK_10 = bytes([0x04, 0x00, 0xF6, 0xFF])  # JMP -10

# Format E (4 bytes): [opcode][rd][rs1][rs2]
IADD_R0_R1_R2 = bytes([0x08, 0x00, 0x01, 0x02])  # IADD R0, R1, R2

# Format G (variable): [opcode][len_lo][len_hi][data...]
TELL_MSG = bytes([0x60]) + bytes([len(data), 0x00]) + data
```

### Register Allocation Patterns

```python
# Convention for register usage:
R0-R3   # Temporary values, function returns
R4-R7   # Function parameters, local variables
R8-R10  # Saved registers (preserved across calls)
R11     # Stack Pointer (SP)
R12     # Region ID
R13     # Trust token
R14     # Frame Pointer (FP)
R15     # Link Register (LR)

# Floating-point registers
F0-F3   # Temporary float values
F4-F7   # Function parameters
F8-F15  # Saved float registers

# Vector registers
V0-V7   # Temporary vector values
V8-V15  # Saved vector registers
```

## Common Bytecode Patterns

### Pattern 1: Function Call

```python
def generate_function_call(func_name: str, args: list) -> bytes:
    """Generate bytecode to call a function."""

    bytecode = bytearray()

    # Load arguments into R0, R1, R2, ...
    for i, arg in enumerate(args[:4]):  # Max 4 args in R0-R3
        bytecode.extend(bytes([0x2B, i, arg & 0xFF, (arg >> 8) & 0xFF]))

    # Call function (placeholder offset)
    bytecode.extend(bytes([0x07, 0x00, 0x00, 0x00]))  # CALL function

    return bytes(bytecode)
```

### Pattern 2: Loop

```python
def generate_counter_loop(iterations: int, body: bytes) -> bytes:
    """Generate a counter-based loop."""

    bytecode = bytearray()

    # Initialize counter
    bytecode.extend(bytes([0x2B, 1, iterations & 0xFF, (iterations >> 8) & 0xFF]))  # MOVI R1, iterations

    # Loop start
    loop_start = len(bytecode)

    # Loop body
    bytecode.extend(body)

    # Decrement counter
    bytecode.extend(bytes([0x0F, 1]))  # DEC R1

    # Jump back if not zero
    current_pos = len(bytecode)
    jump_back = loop_start - (current_pos + 4)
    bytecode.extend(bytes([0x06, 1, jump_back & 0xFF, (jump_back >> 8) & 0xFF]))  # JNZ R1, loop_start

    return bytes(bytecode)
```

### Pattern 3: If-Else

```python
def generate_if_else(condition: bytes, then_clause: bytes, else_clause: bytes) -> bytes:
    """Generate if-else structure."""

    bytecode = bytearray()

    # Condition check (sets R0 to 0/1)
    bytecode.extend(condition)

    # Jump to else if R0 == 0
    else_offset = len(else_clause) + 4  # Will be calculated
    bytecode.extend(bytes([0x05, 0x00, else_offset & 0xFF, (else_offset >> 8) & 0xFF]))  # JZ R0, else

    # Then clause
    bytecode.extend(then_clause)

    # Jump past else
    past_else_offset = 0
    bytecode.extend(bytes([0x04, 0x00, past_else_offset & 0xFF, (past_else_offset >> 8) & 0xFF]))  # JMP past_else

    # Else clause
    else_label = len(bytecode)
    bytecode.extend(else_clause)

    # Fix up offsets
    # (In real implementation, would patch jumps here)

    return bytes(bytecode)
```

### Pattern 4: Memory Access

```python
def generate_array_access(array_base: int, index: int) -> bytes:
    """Generate code to access array element."""

    bytecode = bytearray()

    # Load base address into R0
    bytecode.extend(bytes([0x2B, 0, array_base & 0xFF, (array_base >> 8) & 0xFF]))  # MOVI R0, base

    # Load index into R1
    bytecode.extend(bytes([0x2B, 1, index & 0xFF, (index >> 8) & 0xFF]))  # MOVI R1, index

    # Calculate address: R0 = R0 + (R1 * 4)
    bytecode.extend(bytes([0x2B, 2, 4, 0x00]))  # MOVI R2, 4 (element size)
    bytecode.extend(bytes([0x0A, 1, 1, 2]))  # IMUL R1, R1, R2
    bytecode.extend(bytes([0x08, 0, 0, 1]))  # IADD R0, R0, R1

    # Load value at address
    bytecode.extend(bytes([0x02, 3, 0]))  # LOAD R3, R0

    return bytes(bytecode)
```

## A2A Communication Patterns

### Pattern 1: Send TELL Message

```python
def generate_tell_message(receiver: str, payload: bytes) -> bytes:
    """Generate bytecode to send TELL message."""

    # Message format for TELL opcode (Format G)
    data = receiver.encode() + b"\x00" + payload

    bytecode = bytearray()
    bytecode.extend(bytes([0x60]))  # TELL opcode
    bytecode.extend(bytes([len(data) & 0xFF, (len(data) >> 8) & 0xFF]))  # Length
    bytecode.extend(data)

    return bytes(bytecode)
```

### Pattern 2: Send ASK and Wait

```python
def generate_ask_request(receiver: str, query: bytes) -> bytes:
    """Generate bytecode to send ASK and wait for response."""

    bytecode = bytearray()

    # Send ASK
    data = receiver.encode() + b"\x00" + query
    bytecode.extend(bytes([0x61]))  # ASK opcode
    bytecode.extend(bytes([len(data) & 0xFF, (len(data) >> 8) & 0xFF]))
    bytecode.extend(data)

    # Wait for response (spin loop)
    # In real implementation, would use callback or interrupt

    return bytes(bytecode)
```

## Optimization Techniques

### Optimization 1: Constant Folding

```python
def optimize_constant_folding(bytecode: bytes) -> bytes:
    """Fold constant operations at compile time."""

    # Example: MOVI R0, 5; MOVI R1, 3; IADD R0, R0, R1
    # Optimizes to: MOVI R0, 8

    # Scan for: MOVI rd, c1; MOVI rs, c2; IOP rd, rd, rs
    # Replace with: MOVI rd, (c1 OP c2)

    # Implementation left as exercise
    return bytecode
```

### Optimization 2: Dead Code Elimination

```python
def eliminate_dead_code(bytecode: bytes) -> bytes:
    """Remove unreachable code."""

    # Find basic blocks
    # Mark reachable blocks
    # Remove unreachable blocks

    # Implementation left as exercise
    return bytecode
```

### Optimization 3: Register Allocation

```python
def allocate_registers(bytecode: bytes) -> bytes:
    """Optimize register usage."""

    # Analyze register liveness
    # Reuse registers when values are no longer needed
    # Minimize register spills

    # Implementation left as exercise
    return bytecode
```

## Self-Modifying Code

### Pattern 1: Code Patching

```python
def generate_self_modifying_code() -> bytes:
    """Generate code that modifies itself at runtime."""

    bytecode = bytearray()

    # Load address to modify
    bytecode.extend(bytes([0x2B, 0, 0x20, 0x00]))  # MOVI R0, 0x0020

    # Store new instruction at that address
    bytecode.extend(bytes([0x2B, 1, 0x90, 0x90]))  # MOVI R1, 0x9090 (NOP NOP)
    bytecode.extend(bytes([0x03, 0, 0]))  # STORE R0, R1

    # Continue execution
    bytecode.extend(bytes([0x80]))  # HALT

    return bytes(bytecode)
```

### Pattern 2: Dynamic Dispatch

```python
def generate_dynamic_jump_table() -> bytes:
    """Generate jump table for dynamic dispatch."""

    bytecode = bytearray()

    # Load function index into R0
    # bytecode.extend(...)  # Code to load index

    # Jump table start
    table_start = len(bytecode)

    # Table entries (absolute addresses)
    # In real implementation, would calculate these

    # Jump based on index
    bytecode.extend(bytes([0x2B, 1, table_start & 0xFF, (table_start >> 8) & 0xFF]))  # MOVI R1, table_start
    bytecode.extend(bytes([0x0A, 0, 0, 1]))  # IMUL R0, R0, R2  # R0 = index * 2
    bytecode.extend(bytes([0x08, 0, 1, 0]))  # IADD R0, R1, R0  # R0 = table + offset

    # Load target address and jump
    # bytecode.extend(...)  # LOAD and CALL_IND

    return bytes(bytecode)
```

## Bytecode Verification

### Validation Checklist

```python
def validate_bytecode(bytecode: bytes) -> tuple[bool, list[str]]:
    """Validate FLUX bytecode structure."""

    errors = []
    pc = 0

    while pc < len(bytecode):
        opcode = bytecode[pc]

        # Check opcode validity
        if opcode not in Op._value2member_map_:
            errors.append(f"Invalid opcode 0x{opcode:02X} at position {pc}")
            break

        # Check instruction size
        fmt = get_format(Op(opcode))
        if fmt == "A":
            size = 1
        elif fmt == "B":
            size = 2
        elif fmt == "C":
            size = 3
        elif fmt == "D" or fmt == "E":
            size = 4
        elif fmt == "G":
            if pc + 2 >= len(bytecode):
                errors.append(f"Incomplete Format G instruction at {pc}")
                break
            length = bytecode[pc + 1] | (bytecode[pc + 2] << 8)
            size = 3 + length

        # Check bounds
        if pc + size > len(bytecode):
            errors.append(f"Incomplete instruction at position {pc}")
            break

        pc += size

    # Check for HALT at end
    if len(bytecode) > 0 and bytecode[-1] != Op.HALT:
        errors.append("Program does not end with HALT")

    return (len(errors) == 0, errors)
```

## Best Practices for Agents

### 1. Start Simple

Begin with basic patterns:
- MOVI + arithmetic + HALT
- Simple loops
- Basic conditionals

### 2. Test Incrementally

- Generate small code segments
- Validate each segment
- Combine tested segments

### 3. Use Templates

Maintain a library of working patterns:
- Function prologue/epilogue
- Loop structures
- Memory access patterns

### 4. Optimize Later

- Focus on correctness first
- Profile to find bottlenecks
- Apply optimizations selectively

### 5. Document Generated Code

- Add comments explaining logic
- Include human-readable labels
- Provide usage examples

## Example: Complete Function Generation

```python
def generate_factorial_function() -> bytes:
    """Generate a complete factorial function in bytecode."""

    bytecode = bytearray()

    # Function: factorial(n)
    # Input: n in R0
    # Output: n! in R0
    # Uses: R1 for counter, R2 for accumulator

    # Initialize: R2 = 1 (result), R1 = R0 (counter)
    bytecode.extend(bytes([0x2B, 2, 1, 0x00]))  # MOVI R2, 1
    bytecode.extend(bytes([0x01, 1, 0]))  # MOV R1, R0

    # Check if n <= 1
    bytecode.extend(bytes([0x2B, 3, 1, 0x00]))  # MOVI R3, 1
    bytecode.extend(bytes([0x1D, 1, 3]))  # IGE R1, R3
    bytecode.extend(bytes([0x05, 1, 5, 0x00]))  # JZ R1, return (if n <= 1)

    # Loop start
    loop_start = len(bytecode)

    # R2 = R2 * R1
    bytecode.extend(bytes([0x0A, 2, 2, 1]))  # IMUL R2, R2, R1

    # R1--
    bytecode.extend(bytes([0x0F, 1]))  # DEC R1

    # Compare R1 with 1
    bytecode.extend(bytes([0x2D, 1, 3]))  # CMP R1, R3

    # Jump if not equal (R1 > 1)
    current_pos = len(bytecode)
    jump_back = loop_start - (current_pos + 4)
    bytecode.extend(bytes([0x36, 1, jump_back & 0xFF, (jump_back >> 8) & 0xFF]))  # JL R1, loop_start

    # Return: Move result to R0
    return_label = len(bytecode)
    bytecode.extend(bytes([0x01, 0, 2]))  # MOV R0, R2
    bytecode.extend(bytes([0x28, 0, 0]))  # RET R0, R0

    # Fix up the forward jump to return
    # (In real implementation, would patch JZ offset here)

    return bytes(bytecode)
```

## Resources for Agents

### Opcode Quick Reference

See [Module 1: Bytecode Basics](../bootcamp/module-01-bytecode-basics.md) for complete opcode listing.

### Pattern Library

See [Module 2: Control Flow](../bootcamp/module-02-control-flow.md) for control flow patterns.

### A2A Protocol

See [Module 3: A2A Protocol](../bootcamp/module-03-a2a-protocol.md) for messaging patterns.

## Testing Your Generation

```python
def test_generated_bytecode(bytecode: bytes, expected_result: int) -> bool:
    """Test generated bytecode."""

    # Validate
    valid, errors = validate_bytecode(bytecode)
    if not valid:
        print("Validation errors:")
        for error in errors:
            print(f"  {error}")
        return False

    # Execute
    vm = Interpreter(bytecode, memory_size=4096)
    try:
        vm.execute()
        result = vm.regs.read_gp(0)
        return result == expected_result
    except Exception as e:
        print(f"Execution error: {e}")
        return False
```

---

**Ready to generate?** Start with simple patterns and build complexity gradually.

For questions or improvements, see the [Developer Guide](../developer-guide.md).
