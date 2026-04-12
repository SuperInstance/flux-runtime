> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — All opcode values and names now reference the unified ISA from `isa_unified.py`. See `docs/ISA_UNIFIED.md` for the canonical reference.

# Module 2: Control Flow in FLUX Bytecode

**Learning Objectives:**
- Master unconditional and conditional jumps
- Implement loop patterns (counter-based, condition-based)
- Use comparison instructions
- Build structured control flow (if/else, while, for)

## Jump Instructions Overview

FLUX provides several jump instructions for control flow:

### Unconditional Jumps

| Opcode | Hex | Format | Description |
|--------|-----|--------|-------------|
| JMP | 0x43 | F | Relative jump: `pc += imm16` |
| JAL | 0x44 | F | Jump-and-link: `rd = pc; pc += imm16` |
| CALL | 0x45 | F | Call: `push(pc); pc = rd + imm16` |
| RET | 0x02 | A | Return from subroutine (pop PC from stack) |
| TAIL | 0xE3 | F | Tail call: `pop frame; pc = rd + imm16` |

### Conditional Jumps (test register value)

| Opcode | Hex | Format | Description |
|--------|-----|--------|-------------|
| JZ | 0x3C | E | Jump if `rd == 0`: `pc += rs1` |
| JNZ | 0x3D | E | Jump if `rd != 0`: `pc += rs1` |
| JLT | 0x3E | E | Jump if `rd < 0`: `pc += rs1` |
| JGT | 0x3F | E | Jump if `rd > 0`: `pc += rs1` |

> **Important:** Conditional jumps in the converged ISA use a **register** for the offset (not an immediate). Use R15 as scratch to load the offset before branching:
> ```
> MOVI R15, offset    ; Load jump target offset into scratch register
> JNZ  rd, R15        ; Branch if rd != 0
> ```

## Comparison Instructions

### Direct Comparison Instructions (write result to register)

```
CMP_EQ rd, rs1, rs2   ; rd = (rs1 == rs2) ? 1 : 0
CMP_LT rd, rs1, rs2   ; rd = (rs1 < rs2) ? 1 : 0
CMP_GT rd, rs1, rs2   ; rd = (rs1 > rs2) ? 1 : 0
CMP_NE rd, rs1, rs2   ; rd = (rs1 != rs2) ? 1 : 0
```

### Branching Pattern

Combine comparison with conditional jump:

```python
# Pattern: if R0 == R1, jump to target
struct.pack("<BBBB", 0x2C, 2, 0, 1)      # CMP_EQ R2, R0, R1  (R2 = 1 if equal, 0 if not)
struct.pack("<BBB", 0x18, 15, offset)     # MOVI R15, offset
struct.pack("<BBBB", 0x3D, 2, 15, 0)     # JNZ R2, R15         (jump if R2 != 0, i.e., equal)
```

## Loop Patterns

### Pattern 1: Counter-Based Loop

Sum numbers from 1 to 5:

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Algorithm:
# R0 = 0        ; sum accumulator
# R1 = 5        ; counter
# loop:
#   R0 += R1
#   R1 -= 1
#   if R1 != 0: goto loop
# HALT

bytecode = bytearray()

# Initialize
bytecode.extend(struct.pack("<BBB", 0x18, 0, 0))  # MOVI R0, 0 (sum)
bytecode.extend(struct.pack("<BBB", 0x18, 1, 5))  # MOVI R1, 5 (counter)

# Loop start
loop_start = len(bytecode)

# Loop body
bytecode.extend(struct.pack("<BBBB", 0x20, 0, 0, 1))  # ADD R0, R0, R1
bytecode.extend(struct.pack("<BB", 0x09, 1))           # DEC R1

# Conditional jump back (pseudo-instruction: JNZ R1, loop_start)
current_pos = len(bytecode)
# MOVI R15, offset (3 bytes) + JNZ R1, R15 (4 bytes) = 7 bytes total
jump_back_offset = loop_start - (current_pos + 7)
bytecode.extend(struct.pack("<BBB", 0x18, 15, jump_back_offset & 0xFF))  # MOVI R15, offset
bytecode.extend(struct.pack("<BBBB", 0x3D, 1, 15, 0))  # JNZ R1, R15

# End
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"Sum(1..5) = {result}")  # Sum(1..5) = 15
```

### Pattern 2: While Loop (Condition-Based)

Find first power of 2 >= 100:

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Algorithm:
# R0 = 1        ; current value
# loop:
#   if R0 >= 100: goto end
#   R0 *= 2
#   goto loop
# end:
# HALT

bytecode = bytearray()

# Initialize
bytecode.extend(struct.pack("<BBB", 0x18, 0, 1))  # MOVI R0, 1

# Loop start
loop_start = len(bytecode)

# Check condition: is R0 >= 100?
bytecode.extend(struct.pack("<BBB", 0x18, 1, 100))  # MOVI R1, 100
# CMP_LT R2, R0, R1 → R2 = 1 if R0 < 100, 0 if R0 >= 100
bytecode.extend(struct.pack("<BBBB", 0x2D, 2, 0, 1))  # CMP_LT R2, R0, R1

# Jump to end if R0 >= 100 (R2 == 0)
end_pos = len(bytecode)
bytecode.extend(struct.pack("<BBB", 0x18, 15, 0))    # MOVI R15, placeholder
bytecode.extend(struct.pack("<BBBB", 0x3C, 2, 15, 0))  # JZ R2, R15 (jump if R2==0 → R0>=100)

# Loop body: double R0
bytecode.extend(struct.pack("<BBB", 0x18, 1, 2))      # MOVI R1, 2
bytecode.extend(struct.pack("<BBBB", 0x22, 0, 0, 1))  # MUL R0, R0, R1

# Jump back to loop start
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 4)  # JMP is 4 bytes
bytecode.extend(struct.pack("<BBh", 0x43, 0, jump_back_offset))  # JMP loop_start

# End label
end_label = len(bytecode)

# Fix up the JZ offset
je_offset = end_label - (end_pos + 7)  # 7 bytes for MOVI+JZ
bytecode[end_pos+2] = je_offset & 0xFF

# Halt
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"First power of 2 >= 100: {result}")  # First power of 2 >= 100: 128
```

## Conditional Branching

### If-Else Pattern

Implement: if R0 > 5 then R0 = 10 else R0 = 20

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Assume R0 contains input value
bytecode = bytearray()

# Setup: load test value
bytecode.extend(struct.pack("<BBB", 0x18, 0, 7))  # MOVI R0, 7 (test value)

# Compare: R0 > 5?
bytecode.extend(struct.pack("<BBB", 0x18, 1, 5))  # MOVI R1, 5
# CMP_GT R2, R0, R1 → R2 = 1 if R0 > R1
bytecode.extend(struct.pack("<BBBB", 0x2E, 2, 0, 1))  # CMP_GT R2, R0, R1

# Branch to else if NOT greater (R2 == 0)
else_pos = len(bytecode)
bytecode.extend(struct.pack("<BBB", 0x18, 15, 0))    # MOVI R15, placeholder
bytecode.extend(struct.pack("<BBBB", 0x3C, 2, 15, 0))  # JZ R2, R15 (jump if not greater)

# Then branch: R0 = 10
bytecode.extend(struct.pack("<BBB", 0x18, 0, 10))  # MOVI R0, 10
bytecode.extend(struct.pack("<BBh", 0x43, 0, 3))    # JMP past else (3 bytes = MOVI + HALT)

# Else branch: R0 = 20
else_label = len(bytecode)
else_offset = else_label - (else_pos + 7)  # 7 bytes for MOVI+JZ
bytecode[else_pos+2] = else_offset & 0xFF
bytecode.extend(struct.pack("<BBB", 0x18, 0, 20))  # MOVI R0, 20

# Halt
bytecode.extend(bytes([0x00]))

# Execute with different inputs
for test_val in [3, 7, 10]:
    # Modify the initial MOVI (immediate at byte offset 2)
    bytecode[2] = test_val & 0xFF

    vm = Interpreter(bytes(bytecode), memory_size=4096)
    vm.execute()
    result = vm.regs[0]
    print(f"Input: {test_val:2d} → Output: {result}")
```

**Output:**
```
Input:  3 → Output: 20
Input:  7 → Output: 10
Input: 10 → Output: 10
```

## Function Calls

### CALL and RET Pattern

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Simple function call example
bytecode = bytearray()

# Main program
bytecode.extend(struct.pack("<BBB", 0x18, 0, 5))   # MOVI R0, 5 (parameter)
bytecode.extend(struct.pack("<BBB", 0x18, 1, 3))   # MOVI R1, 3 (parameter)

# Call function: CALL R15, func_addr
# R15 = 0 (register file initialized to 0, untouched so far)
# CALL does: push(PC); pc = R15 + imm16 = 0 + func_addr
call_pos = len(bytecode)
bytecode.extend(struct.pack("<BBh", 0x45, 15, 0))   # CALL R15, func_addr (placeholder)

# After call
bytecode.extend(bytes([0x00]))                     # HALT

# Function: add R0 and R1, return in R0
func_start = len(bytecode)
bytecode.extend(struct.pack("<BBBB", 0x20, 0, 0, 1))  # ADD R0, R0, R1
bytecode.extend(bytes([0x02]))                       # RET (pop return address, jump)

# Fix up CALL target (absolute address since R15 = 0)
bytecode[call_pos+2:call_pos+4] = struct.pack("<h", func_start)

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"Function result: {result}")  # Function result: 8
```

## Exercise 1: Factorial

**Task:** Write a FLUX program that computes factorial(5) = 120.

**Requirements:**
- Use a counter-based loop
- Result should be in R0
- Use MUL for multiplication

**Solution:**

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Compute: 5! = 5 * 4 * 3 * 2 * 1 = 120
bytecode = bytearray()

# Initialize
bytecode.extend(struct.pack("<BBB", 0x18, 0, 1))  # MOVI R0, 1 (result)
bytecode.extend(struct.pack("<BBB", 0x18, 1, 5))  # MOVI R1, 5 (counter)

# Loop start
loop_start = len(bytecode)

# Loop body: R0 *= R1
bytecode.extend(struct.pack("<BBBB", 0x22, 0, 0, 1))  # MUL R0, R0, R1
bytecode.extend(struct.pack("<BB", 0x09, 1))           # DEC R1

# Loop condition: if R1 != 0, continue
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 7)  # MOVI(3) + JNZ(4) = 7
bytecode.extend(struct.pack("<BBB", 0x18, 15, jump_back_offset & 0xFF))  # MOVI R15, offset
bytecode.extend(struct.pack("<BBBB", 0x3D, 1, 15, 0))  # JNZ R1, R15

# End
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"5! = {result}")  # 5! = 120
```

## Exercise 2: Fibonacci Sequence

**Task:** Write a FLUX program that computes the 10th Fibonacci number.

**Requirements:**
- Use iterative approach (not recursive)
- F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)
- Result in R1

**Solution:**

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Compute F(10) = 55
bytecode = bytearray()

# Initialize: R0 = 0 (current), R1 = 1 (next), R2 = 10 (counter)
bytecode.extend(struct.pack("<BBB", 0x18, 0, 0))   # MOVI R0, 0 (F(n))
bytecode.extend(struct.pack("<BBB", 0x18, 1, 1))   # MOVI R1, 1 (F(n+1))
bytecode.extend(struct.pack("<BBB", 0x18, 2, 10))  # MOVI R2, 10 (iterations)

# Loop start
loop_start = len(bytecode)

# Fibonacci: R3 = R0 + R1, R0 = R1, R1 = R3, R2--
bytecode.extend(struct.pack("<BBBB", 0x20, 3, 0, 1))  # ADD R3, R0, R1
bytecode.extend(struct.pack("<BBBB", 0x3A, 0, 1, 0))  # MOV R0, R1
bytecode.extend(struct.pack("<BBBB", 0x3A, 1, 3, 0))  # MOV R1, R3
bytecode.extend(struct.pack("<BB", 0x09, 2))           # DEC R2

# Loop condition
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 7)  # MOVI(3) + JNZ(4) = 7
bytecode.extend(struct.pack("<BBB", 0x18, 15, jump_back_offset & 0xFF))  # MOVI R15, offset
bytecode.extend(struct.pack("<BBBB", 0x3D, 2, 15, 0))  # JNZ R2, R15

# End
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[1]
print(f"F(10) = {result}")  # F(10) = 55
```

## Advanced: Nested Loops

Compute multiplication using repeated addition:

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Compute: 6 * 7 = 42 using nested loops
# Outer loop: count from 0 to 6
# Inner loop: add 7, 6 times

bytecode = bytearray()

# Initialize: R0 = 0 (result), R1 = 6 (outer counter), R2 = 7 (value to add)
bytecode.extend(struct.pack("<BBB", 0x18, 0, 0))   # MOVI R0, 0
bytecode.extend(struct.pack("<BBB", 0x18, 1, 6))   # MOVI R1, 6
bytecode.extend(struct.pack("<BBB", 0x18, 2, 7))   # MOVI R2, 7

# Outer loop start
outer_loop = len(bytecode)

# Inner loop: R3 = R2, inner counter
bytecode.extend(struct.pack("<BBB", 0x18, 3, 7))   # MOVI R3, 7

# Inner loop start
inner_loop = len(bytecode)

# Add R2 to R0, decrement R3
bytecode.extend(struct.pack("<BBBB", 0x20, 0, 0, 2))  # ADD R0, R0, R2
bytecode.extend(struct.pack("<BB", 0x09, 3))           # DEC R3

# Inner loop condition
current_pos = len(bytecode)
jump_back_offset = inner_loop - (current_pos + 7)  # MOVI(3) + JNZ(4) = 7
bytecode.extend(struct.pack("<BBB", 0x18, 15, jump_back_offset & 0xFF))  # MOVI R15, offset
bytecode.extend(struct.pack("<BBBB", 0x3D, 3, 15, 0))  # JNZ R3, R15

# Outer loop decrement
bytecode.extend(struct.pack("<BB", 0x09, 1))  # DEC R1

# Outer loop condition
current_pos = len(bytecode)
jump_back_offset = outer_loop - (current_pos + 7)  # MOVI(3) + JNZ(4) = 7
bytecode.extend(struct.pack("<BBB", 0x18, 15, jump_back_offset & 0xFF))  # MOVI R15, offset
bytecode.extend(struct.pack("<BBBB", 0x3D, 1, 15, 0))  # JNZ R1, R15

# End
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"6 * 7 = {result}")  # 6 * 7 = 42
```

## Progress Checkpoint

At the end of Module 2, you should be able to:

- ✅ Use JMP (Format F) for unconditional jumps
- ✅ Implement counter-based loops with JNZ (pseudo-instruction: MOVI R15 + JNZ)
- ✅ Use CMP_EQ, CMP_LT, CMP_GT for comparisons
- ✅ Build if-else structures using comparison + conditional jump
- ✅ Create function calls with CALL/RET
- ✅ Implement nested loops

## Next Steps

**[Module 3: A2A Protocol](module-03-a2a-protocol.md)** — Learn agent-to-agent messaging and multi-agent communication.

---

**Need Help?** See the [ISA Unified Reference](../ISA_UNIFIED.md) for complete opcode table or check the examples in the main repository.
