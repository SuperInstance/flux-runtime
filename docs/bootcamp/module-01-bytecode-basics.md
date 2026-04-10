# Module 1: FLUX Bytecode Basics

**Learning Objectives:**
- Understand FLUX bytecode structure and instruction formats
- Learn the register file layout (GP, FP, SIMD)
- Write and execute your first FLUX program
- Master basic arithmetic operations

## What is FLUX Bytecode?

FLUX bytecode is a compact binary instruction format for the FLUX Micro-VM. It's designed for:
- **AI agents** — First-class support for agent communication
- **Zero dependencies** — Runs on pure Python 3.10+
- **High performance** — 48K+ ops/sec on ARM
- **Polyglot compilation** — C, Python, Rust → same bytecode

## Instruction Encoding Formats

FLUX uses 6 instruction formats (A/B/C/D/E/G) for compact encoding:

### Format A: 1 byte — Opcode only
```
[opcode]
```
Used for: NOP, HALT, DUP, SWAP, EMERGENCY_STOP

**Example:** HALT instruction
```python
bytes([Op.HALT])  # [0x80]
```

### Format B: 2 bytes — Opcode + register
```
[opcode][reg:u8]
```
Used for: INC, DEC, ENTER, LEAVE, PUSH, POP, INEG, FNEG, INOT

**Example:** Increment R0
```python
struct.pack("<BB", Op.INC, 0)  # [0x0E][0x00]
```

### Format C: 3 bytes — Opcode + destination + source
```
[opcode][rd:u8][rs1:u8]
```
Used for: MOV, LOAD, STORE, CMP, most comparison ops

**Example:** Move R1 to R0
```python
struct.pack("<BBB", Op.MOV, 0, 1)  # [0x01][0x00][0x01]
```

### Format D: 4 bytes — Opcode + register + signed offset
```
[opcode][reg:u8][offset_lo:u8][offset_hi:u8]
```
Used for: JMP, JZ, JNZ, conditional jumps, MOVI, CALL

**Example:** Jump forward 10 instructions
```python
struct.pack("<BBh", Op.JMP, 0, 10)  # [0x04][0x00][0x0A][0x00]
```

### Format E: 4 bytes — Opcode + dest + src1 + src2
```
[opcode][rd:u8][rs1:u8][rs2:u8]
```
Used for: IADD, ISUB, IMUL, IDIV, bitwise ops, float ops

**Example:** Add R1 and R2 into R0
```python
struct.pack("<BBBB", Op.IADD, 0, 1, 2)  # [0x08][0x00][0x01][0x02]
```

### Format G: Variable length — Opcode + length + data
```
[opcode][len_lo:u8][len_hi:u8][data:len bytes]
```
Used for: A2A messages, memory operations, system calls

**Example:** Create memory region
```python
name = b"heap\0"
size = struct.pack("<I", 65536)
data = name + size
struct.pack("<BH", Op.REGION_CREATE, len(data)) + data
```

## Register File Layout

The FLUX VM has **64 registers** organized in three banks:

```
┌─────────────────────────────────────────────────────────┐
│  General-Purpose (R0-R15)          Floating-Point (F0-F15)  │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┐    ┌───┬───┬───┬───┐ │
│  │R0 │R1 │R2 │...│R10│R11│R14│R15│    │F0 │F1 │...│F15│ │
│  │   │   │   │   │   │SP │FP │LR │    │   │   │   │   │ │
│  └───┴───┴───┴───┴───┴───┴───┴───┘    └───┴───┴───┴───┘ │
│                                                         │
│  SIMD/Vector (V0-V15) — 128-bit each                   │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┐                     │
│  │V0 │V1 │V2 │...│V13│V14│V15│                      │
│  │16 bytes each                                       │
│  └───┴───┴───┴───┴───┴───┴───┴───┘                     │
└─────────────────────────────────────────────────────────┘
```

### Special Register Aliases
- **R11 (SP)** — Stack pointer
- **R14 (FP)** — Frame pointer
- **R15 (LR)** — Link register (return address)
- **R12** — Region ID (ABI convention)
- **R13** — Trust token (ABI convention)

## Your First FLUX Program

Let's write a program that computes `3 + 4 = 7`:

### Step 1: Plan the instructions

```
1. MOVI R0, 3    ; Load immediate value 3 into R0
2. MOVI R1, 4    ; Load immediate value 4 into R1
3. IADD R0,R0,R1 ; Add R1 to R0, store in R0
4. HALT          ; Stop execution
```

### Step 2: Encode to bytecode

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Build bytecode step by step
bytecode = b""

# 1. MOVI R0, 3 → Format D: [0x2B][0x00][0x03][0x00]
bytecode += struct.pack("<BBh", Op.MOVI, 0, 3)

# 2. MOVI R1, 4 → Format D: [0x2B][0x01][0x04][0x00]
bytecode += struct.pack("<BBh", Op.MOVI, 1, 4)

# 3. IADD R0, R0, R1 → Format E: [0x08][0x00][0x00][0x01]
bytecode += struct.pack("<BBBB", Op.IADD, 0, 0, 1)

# 4. HALT → Format A: [0x80]
bytecode += bytes([Op.HALT])

print(f"Bytecode ({len(bytecode)} bytes):")
print("  " + " ".join(f"{b:02X}" for b in bytecode))
```

**Output:**
```
Bytecode (13 bytes):
  2B 00 03 00 2B 01 04 00 08 00 00 01 80
```

### Step 3: Execute in the VM

```python
# Create interpreter with 4KB memory
vm = Interpreter(bytecode, memory_size=4096)

# Run until HALT
cycles = vm.execute()

# Read result from R0
result = vm.regs.read_gp(0)

print(f"Cycles: {cycles}")
print(f"Result: R0 = {result}")
```

**Output:**
```
Cycles: 4
Result: R0 = 7
```

## Complete Working Example

```python
#!/usr/bin/env python3
"""FLUX Hello World — Compute 3 + 4"""

import struct
import sys
import os

# Add FLUX source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter

def main():
    # Build bytecode: 3 + 4 = 7
    bytecode = (
        struct.pack("<BBh", Op.MOVI, 0, 3) +     # MOVI R0, 3
        struct.pack("<BBh", Op.MOVI, 1, 4) +     # MOVI R1, 4
        struct.pack("<BBBB", Op.IADD, 0, 0, 1) +  # IADD R0, R0, R1
        bytes([Op.HALT])                          # HALT
    )

    print(f"Bytecode: {' '.join(f'{b:02X}' for b in bytecode)}")

    # Execute
    vm = Interpreter(bytecode, memory_size=4096)
    cycles = vm.execute()
    result = vm.regs.read_gp(0)

    print(f"✓ Executed in {cycles} cycles")
    print(f"✓ Result: R0 = {result}")

    return result == 7  # Success if result is 7

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

## Arithmetic Operations Reference

### Integer Arithmetic

| Opcode | Format | Description | Example |
|--------|--------|-------------|---------|
| IADD | E | rd = rs1 + rs2 | `IADD R0, R1, R2` |
| ISUB | E | rd = rs1 - rs2 | `ISUB R0, R1, R2` |
| IMUL | E | rd = rs1 * rs2 | `IMUL R0, R1, R2` |
| IDIV | E | rd = rs1 / rs2 | `IDIV R0, R1, R2` |
| IMOD | E | rd = rs1 % rs2 | `IMOD R0, R1, R2` |
| INEG | C | rd = -rs1 | `INEG R0, R1` |
| INC | B | reg++ | `INC R0` |
| DEC | B | reg-- | `DEC R0` |

### Bitwise Operations

| Opcode | Format | Description | Example |
|--------|--------|-------------|---------|
| IAND | E | rd = rs1 & rs2 | `IAND R0, R1, R2` |
| IOR | E | rd = rs1 \| rs2 | `IOR R0, R1, R2` |
| IXOR | E | rd = rs1 ^ rs2 | `IXOR R0, R1, R2` |
| INOT | C | rd = ~rs1 | `INOT R0, R1` |
| ISHL | E | rd = rs1 << rs2 | `ISHL R0, R1, R2` |
| ISHR | E | rd = rs1 >> rs2 | `ISHR R0, R1, R2` |

## Exercise 1: Compute 3*4+2

**Task:** Write a FLUX program that computes `(3 * 4) + 2` and returns the result in R0.

**Requirements:**
1. Use only MOVI, IMUL, and IADD instructions
2. Store the final result in R0
3. End with HALT

**Solution:**

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Compute: (3 * 4) + 2 = 14
bytecode = (
    struct.pack("<BBh", Op.MOVI, 0, 3) +      # MOVI R0, 3
    struct.pack("<BBh", Op.MOVI, 1, 4) +      # MOVI R1, 4
    struct.pack("<BBBB", Op.IMUL, 0, 0, 1) +   # IMUL R0, R0, R1  (R0 = 3 * 4 = 12)
    struct.pack("<BBh", Op.MOVI, 1, 2) +      # MOVI R1, 2
    struct.pack("<BBBB", Op.IADD, 0, 0, 1) +   # IADD R0, R0, R1  (R0 = 12 + 2 = 14)
    bytes([Op.HALT])
)

vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"Result: {result}")  # Result: 14
```

## Exercise 2: Bitwise Operations

**Task:** Write a program that:
1. Loads value 0xFF into R0
2. Loads value 0x0F into R1
3. Computes R0 = R0 & R1 (bitwise AND)
4. Returns result in R0

**Expected Result:** 0x0F (15)

**Solution:**

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

bytecode = (
    struct.pack("<BBh", Op.MOVI, 0, 0xFF) +    # MOVI R0, 0xFF
    struct.pack("<BBh", Op.MOVI, 1, 0x0F) +    # MOVI R1, 0x0F
    struct.pack("<BBBB", Op.IAND, 0, 0, 1) +   # IAND R0, R0, R1
    bytes([Op.HALT])
)

vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)
print(f"Result: 0x{result:02X}")  # Result: 0x0F
```

## Progress Checkpoint

At the end of Module 1, you should be able to:

- ✅ Identify all 6 instruction formats (A/B/C/D/E/G)
- ✅ Encode simple arithmetic operations to bytecode
- ✅ Understand the register file layout (R0-R15, F0-F15, V0-V15)
- ✅ Write and execute a basic FLUX program
- ✅ Use MOVI, IADD, IMUL, and bitwise operations

## Next Steps

**[Module 2: Control Flow](module-02-control-flow.md)** — Learn to implement loops, conditionals, and branching in FLUX bytecode.

---

**Need Help?** See the [User Guide](../user-guide.md) for complete API reference or [Developer Guide](../developer-guide.md) for architecture details.
