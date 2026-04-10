# Module 2: Control Flow in FLUX Bytecode

**Learning Objectives:**
- Master unconditional and conditional jumps
- Implement loop patterns (counter-based, condition-based)
- Use comparison instructions and condition flags
- Build structured control flow (if/else, while, for)

## Jump Instructions Overview

FLUX provides several jump instructions for control flow:

### Unconditional Jumps

| Opcode | Format | Description |
|--------|--------|-------------|
| JMP | D | Unconditional jump |
| CALL | D | Push return address, then jump |
| RET | C | Pop return address, jump back |
| TAILCALL | D | Jump without pushing return address |

### Conditional Jumps (based on register value)

| Opcode | Format | Description |
|--------|--------|-------------|
| JZ | D | Jump if register == 0 |
| JNZ | D | Jump if register != 0 |

### Conditional Jumps (based on flags)

| Opcode | Format | Condition |
|--------|--------|-----------|
| JE | D | Jump if equal (zero flag set) |
| JNE | D | Jump if not equal |
| JG | D | Jump if greater (not zero & not sign) |
| JL | D | Jump if less (sign flag set) |
| JGE | D | Jump if greater or equal |
| JLE | D | Jump if less or equal |

## Comparison Instructions

Before using conditional jumps, you need to set condition flags:

### CMP Instruction

```
CMP rd, rs1    ; Flags = (rd - rs1)
```

Sets flags based on subtraction:
- **Zero flag**: Set if rd == rs1
- **Sign flag**: Set if rd < rs1
- **Carry flag**: Set if rd < rs1 (unsigned)
- **Overflow flag**: Set if signed overflow

### Direct Comparison Instructions

```
IEQ rd, rs1    ; rd = (rd == rs1) ? 1 : 0
ILT rd, rs1    ; rd = (rd < rs1) ? 1 : 0
IGT rd, rs1    ; rd = (rd > rs1) ? 1 : 0
ILE rd, rs1    ; rd = (rd <= rs1) ? 1 : 0
IGE rd, rs1    ; rd = (rd >= rs1) ? 1 : 0
```

## Loop Patterns

### Pattern 1: Counter-Based Loop

Sum numbers from 1 to 5:

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

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
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 0))  # MOVI R0, 0 (sum)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 5))  # MOVI R1, 5 (counter)

# Loop start
loop_start = len(bytecode)

# Loop body
bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))  # IADD R0, R0, R1
bytecode.extend(struct.pack("<BB", Op.DEC, 1))           # DEC R1

# Conditional jump back
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 4)  # +4 for JNZ instruction size
bytecode.extend(struct.pack("<BBh", Op.JNZ, 1, jump_back_offset))  # JNZ R1, loop_start

# End
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"Sum(1..5) = {result}")  # Sum(1..5) = 15
```

### Pattern 2: While Loop (Condition-Based)

Find first power of 2 >= 100:

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

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
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 1))  # MOVI R0, 1

# Loop start
loop_start = len(bytecode)

# Check condition
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 100))  # MOVI R1, 100
bytecode.extend(struct.pack("<BBB", Op.IGE, 0, 1))     # IGE R0, R1

# Jump to end if R0 >= 100
end_offset = 8  # Will be calculated
je_pos = len(bytecode)
bytecode.extend(struct.pack("<BBh", Op.JE, 0, 0))  # JE R0, end (placeholder)

# Loop body: double R0
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 2))      # MOVI R1, 2
bytecode.extend(struct.pack("<BBBB", Op.IMUL, 0, 0, 1))  # IMUL R0, R0, R1

# Jump back to loop start
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 4)
bytecode.extend(struct.pack("<BBh", Op.JMP, 0, jump_back_offset))  # JMP loop_start

# End label
end_label = len(bytecode)

# Fix up the JE offset
je_offset = end_label - (je_pos + 4)
bytecode[je_pos+2:je_pos+4] = struct.pack("<h", je_offset)

# Halt
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"First power of 2 >= 100: {result}")  # First power of 2 >= 100: 128
```

## Conditional Branching

### If-Else Pattern

Implement: if R0 > 5 then R0 = 10 else R0 = 20

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Assume R0 contains input value
bytecode = bytearray()

# Setup: load test value
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 7))  # MOVI R0, 7 (test value)

# Compare: R0 > 5?
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 5))  # MOVI R1, 5
bytecode.extend(struct.pack("<BBB", Op.IGT, 0, 1))   # IGT R0, R1

# Branch to else if not greater
else_pos = len(bytecode)
bytecode.extend(struct.pack("<BBh", Op.JE, 0, 0))    # JE R0, else (placeholder)

# Then branch: R0 = 10
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 10))  # MOVI R0, 10
bytecode.extend(struct.pack("<BBh", Op.JMP, 0, 3))    # JMP past else

# Else branch: R0 = 20
else_label = len(bytecode)
else_offset = else_label - (else_pos + 4)
bytecode[else_pos+2:else_pos+4] = struct.pack("<h", else_offset)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 20))  # MOVI R0, 20

# Halt
bytecode.extend(bytes([Op.HALT]))

# Execute with different inputs
for test_val in [3, 7, 10]:
    # Modify the initial MOVI
    bytecode[2:4] = struct.pack("<h", test_val)

    vm = Interpreter(bytes(bytecode), memory_size=4096)
    vm.execute()
    result = vm.regs.read_gp(0)
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
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Simple function call example
bytecode = bytearray()

# Main program
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 5))   # MOVI R0, 5 (parameter)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 3))   # MOVI R1, 3 (parameter)

# Call function
call_pos = len(bytecode)
bytecode.extend(struct.pack("<BBh", Op.CALL, 0, 8))   # CALL function (offset 8)

# After call
bytecode.extend(bytes([Op.HALT]))                     # HALT

# Function: add R0 and R1, return in R0
func_start = len(bytecode)
bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))  # IADD R0, R0, R1
bytecode.extend(struct.pack("<BBB", Op.RET, 0, 0))       # RET R0, R0

# Fix up CALL offset
call_offset = func_start - (call_pos + 4)
bytecode[call_pos+2:call_pos+4] = struct.pack("<h", call_offset)

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"Function result: {result}")  # Function result: 8
```

## Exercise 1: Factorial

**Task:** Write a FLUX program that computes factorial(5) = 120.

**Requirements:**
- Use a counter-based loop
- Result should be in R0
- Use IMUL for multiplication

**Solution:**

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Compute: 5! = 5 * 4 * 3 * 2 * 1 = 120
bytecode = bytearray()

# Initialize
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 1))  # MOVI R0, 1 (result)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 5))  # MOVI R1, 5 (counter)

# Loop start
loop_start = len(bytecode)

# Loop body: R0 *= R1
bytecode.extend(struct.pack("<BBBB", Op.IMUL, 0, 0, 1))  # IMUL R0, R0, R1
bytecode.extend(struct.pack("<BB", Op.DEC, 1))           # DEC R1

# Loop condition: if R1 != 0, continue
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 4)
bytecode.extend(struct.pack("<BBh", Op.JNZ, 1, jump_back_offset))  # JNZ R1, loop_start

# End
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"5! = {result}")  # 5! = 120
```

## Exercise 2: Fibonacci Sequence

**Task:** Write a FLUX program that computes the 10th Fibonacci number.

**Requirements:**
- Use iterative approach (not recursive)
- F(0) = 0, F(1) = 1, F(n) = F(n-1) + F(n-2)
- Result in R0

**Solution:**

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Compute F(10) = 55
bytecode = bytearray()

# Initialize: R0 = 0 (current), R1 = 1 (next), R2 = 10 (counter)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 0))   # MOVI R0, 0 (F(n))
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 1))   # MOVI R1, 1 (F(n+1))
bytecode.extend(struct.pack("<BBh", Op.MOVI, 2, 10))  # MOVI R2, 10 (iterations)

# Loop start
loop_start = len(bytecode)

# Fibonacci: R3 = R0 + R1, R0 = R1, R1 = R3, R2--
bytecode.extend(struct.pack("<BBBB", Op.IADD, 3, 0, 1))  # IADD R3, R0, R1
bytecode.extend(struct.pack("<BBB", Op.MOV, 0, 1))       # MOV R0, R1
bytecode.extend(struct.pack("<BBB", Op.MOV, 1, 3))       # MOV R1, R3
bytecode.extend(struct.pack("<BB", Op.DEC, 2))           # DEC R2

# Loop condition
current_pos = len(bytecode)
jump_back_offset = loop_start - (current_pos + 4)
bytecode.extend(struct.pack("<BBh", Op.JNZ, 2, jump_back_offset))  # JNZ R2, loop_start

# End
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"F(10) = {result}")  # F(10) = 55
```

## Advanced: Nested Loops

Compute multiplication using repeated addition:

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Compute: 6 * 7 = 42 using nested loops
# Outer loop: count from 0 to 6
# Inner loop: add 7, 6 times

bytecode = bytearray()

# Initialize: R0 = 0 (result), R1 = 6 (outer counter), R2 = 7 (value to add)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 0))   # MOVI R0, 0
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 6))   # MOVI R1, 6
bytecode.extend(struct.pack("<BBh", Op.MOVI, 2, 7))   # MOVI R2, 7

# Outer loop start
outer_loop = len(bytecode)

# Inner loop: R3 = R2, inner counter
bytecode.extend(struct.pack("<BBh", Op.MOVI, 3, 7))   # MOVI R3, 7

# Inner loop start
inner_loop = len(bytecode)

# Add R2 to R0, decrement R3
bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 2))  # IADD R0, R0, R2
bytecode.extend(struct.pack("<BB", Op.DEC, 3))           # DEC R3

# Inner loop condition
current_pos = len(bytecode)
jump_back_offset = inner_loop - (current_pos + 4)
bytecode.extend(struct.pack("<BBh", Op.JNZ, 3, jump_back_offset))  # JNZ R3, inner_loop

# Outer loop decrement
bytecode.extend(struct.pack("<BB", Op.DEC, 1))  # DEC R1

# Outer loop condition
current_pos = len(bytecode)
jump_back_offset = outer_loop - (current_pos + 4)
bytecode.extend(struct.pack("<BBh", Op.JNZ, 1, jump_back_offset))  # JNZ R1, outer_loop

# End
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"6 * 7 = {result}")  # 6 * 7 = 42
```

## Progress Checkpoint

At the end of Module 2, you should be able to:

- ✅ Use JMP, JZ, JNZ for unconditional and conditional jumps
- ✅ Implement counter-based loops with JNZ
- ✅ Use CMP and conditional jumps (JE, JNE, JG, JL, JGE, JLE)
- ✅ Build if-else structures
- ✅ Create function calls with CALL/RET
- ✅ Implement nested loops

## Next Steps

**[Module 3: A2A Protocol](module-03-a2a-protocol.md)** — Learn agent-to-agent messaging and multi-agent communication.

---

**Need Help?** See the [User Guide](../user-guide.md) for complete opcode reference or check the examples in the main repository.
