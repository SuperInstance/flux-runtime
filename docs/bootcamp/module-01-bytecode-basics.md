> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — All opcode values and names now reference the unified ISA from `isa_unified.py`. See `docs/ISA_UNIFIED.md` for the canonical reference.

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

FLUX uses 7 instruction formats (A through G) for compact encoding. All multi-byte formats are little-endian for the immediate fields.

### Format A: 1 byte — Opcode only
```
[opcode]
```
Used for: HALT, NOP, RET, BRK, YIELD, HALT_ERR, DUMP, ASSERT

**Example:** HALT instruction
```python
bytes([0x00])  # HALT (opcode 0x00)
```

### Format B: 2 bytes — Opcode + register
```
[opcode][rd:u8]
```
Used for: INC, DEC, NOT, NEG, PUSH, POP, CONF_LD, CONF_ST

**Example:** Increment R0
```python
struct.pack("<BB", 0x08, 0)  # [0x08][0x00] — INC R0
```

### Format C: 2 bytes — Opcode + immediate
```
[opcode][imm8:u8]
```
Used for: SYS, TRAP, DBG, YIELD, SEMA, CACHE — immediate-only operations

**Example:** System call
```python
struct.pack("<BB", 0x10, 1)  # [0x10][0x01] — SYS 1
```

### Format D: 3 bytes — Opcode + register + signed imm8
```
[opcode][rd:u8][imm8:u8]
```
Used for: MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI

**Example:** Load immediate value 3 into R0
```python
struct.pack("<BBB", 0x18, 0, 3)  # [0x18][0x00][0x03] — MOVI R0, 3
```

> **Note:** imm8 is sign-extended. Values 0–127 are direct; 128–255 become negative. For larger values, use MOVI16 (Format F, imm16).

### Format E: 4 bytes — Opcode + dest + src1 + src2
```
[opcode][rd:u8][rs1:u8][rs2:u8]
```
Used for: ADD, SUB, MUL, DIV, bitwise ops, float ops, MOV, LOAD, STORE, JZ, JNZ, JLT, JGT, CMP_EQ, CMP_LT, CMP_GT, A2A opcodes

**Example:** Add R1 and R2 into R0
```python
struct.pack("<BBBB", 0x20, 0, 1, 2)  # [0x20][0x00][0x01][0x02] — ADD R0, R1, R2
```

**Example:** Move R1 to R0
```python
struct.pack("<BBBB", 0x3A, 0, 1, 0)  # [0x3A][0x00][0x01][0x00] — MOV R0, R1
```

### Format F: 4 bytes — Opcode + register + signed imm16
```
[opcode][rd:u8][imm16_lo:u8][imm16_hi:u8]
```
Used for: JMP, JAL, CALL, MOVI16, ADDI16, SUBI16, LOOP

**Example:** Jump forward 10 bytes
```python
struct.pack("<BBh", 0x43, 0, 10)  # [0x43][0x00][0x0A][0x00] — JMP +10
```

### Format G: 5 bytes — Opcode + rd + rs1 + signed imm16
```
[opcode][rd:u8][rs1:u8][imm16_lo:u8][imm16_hi:u8]
```
Used for: LOADOFF, STOREOFF, COPY, FILL, ENTER, LEAVE, DMA, MMIO, GPU ops

**Example:** Fill memory with a value
```python
struct.pack("<BBBh", 0x4F, 0, 1, 256)  # [0x4F][0x00][0x01][0x00][0x01] — FILL R0, R1, 256
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
- **R15 (LR)** — Link register (return address, also used as scratch for pseudo-instructions)

## Your First FLUX Program

Let's write a program that computes `3 + 4 = 7`:

### Step 1: Plan the instructions

```
1. MOVI R0, 3    ; Load immediate value 3 into R0
2. MOVI R1, 4    ; Load immediate value 4 into R1
3. ADD R0, R0, R1 ; Add R1 to R0, store in R0
4. HALT          ; Stop execution
```

### Step 2: Encode to bytecode

```python
import struct

# Build bytecode step by step
bytecode = b""

# 1. MOVI R0, 3 → Format D: [0x18][0x00][0x03] (3 bytes)
bytecode += struct.pack("<BBB", 0x18, 0, 3)

# 2. MOVI R1, 4 → Format D: [0x18][0x01][0x04] (3 bytes)
bytecode += struct.pack("<BBB", 0x18, 1, 4)

# 3. ADD R0, R0, R1 → Format E: [0x20][0x00][0x00][0x01] (4 bytes)
bytecode += struct.pack("<BBBB", 0x20, 0, 0, 1)

# 4. HALT → Format A: [0x00] (1 byte)
bytecode += bytes([0x00])

print(f"Bytecode ({len(bytecode)} bytes):")
print("  " + " ".join(f"{b:02X}" for b in bytecode))
```

**Output:**
```
Bytecode (11 bytes):
  18 00 03 18 01 04 20 00 00 01 00
```

### Step 3: Execute in the VM

```python
from flux.vm.unified_interpreter import Interpreter

# Create interpreter with 4KB memory
vm = Interpreter(bytecode, memory_size=4096)

# Run until HALT
cycles = vm.execute()

# Read result from R0
result = vm.regs[0]

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

from flux.vm.unified_interpreter import Interpreter

def main():
    # Build bytecode: 3 + 4 = 7
    bytecode = (
        struct.pack("<BBB", 0x18, 0, 3) +     # MOVI R0, 3   (Format D)
        struct.pack("<BBB", 0x18, 1, 4) +     # MOVI R1, 4   (Format D)
        struct.pack("<BBBB", 0x20, 0, 0, 1) + # ADD R0, R0, R1 (Format E)
        bytes([0x00])                          # HALT          (Format A)
    )

    print(f"Bytecode: {' '.join(f'{b:02X}' for b in bytecode)}")

    # Execute
    vm = Interpreter(bytecode, memory_size=4096)
    cycles = vm.execute()
    result = vm.regs[0]

    print(f"✓ Executed in {cycles} cycles")
    print(f"✓ Result: R0 = {result}")

    return result == 7  # Success if result is 7

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

## Arithmetic Operations Reference

### Integer Arithmetic

| Opcode | Hex | Format | Description | Example |
|--------|-----|--------|-------------|---------|
| ADD | 0x20 | E | rd = rs1 + rs2 | `ADD R0, R1, R2` |
| SUB | 0x21 | E | rd = rs1 - rs2 | `SUB R0, R1, R2` |
| MUL | 0x22 | E | rd = rs1 * rs2 | `MUL R0, R1, R2` |
| DIV | 0x23 | E | rd = rs1 / rs2 | `DIV R0, R1, R2` |
| MOD | 0x24 | E | rd = rs1 % rs2 | `MOD R0, R1, R2` |
| NEG | 0x0B | B | rd = -rd | `NEG R0` |
| INC | 0x08 | B | reg++ | `INC R0` |
| DEC | 0x09 | B | reg-- | `DEC R0` |

### Bitwise Operations

| Opcode | Hex | Format | Description | Example |
|--------|-----|--------|-------------|---------|
| AND | 0x25 | E | rd = rs1 & rs2 | `AND R0, R1, R2` |
| OR | 0x26 | E | rd = rs1 \| rs2 | `OR R0, R1, R2` |
| XOR | 0x27 | E | rd = rs1 ^ rs2 | `XOR R0, R1, R2` |
| NOT | 0x0A | B | rd = ~rd | `NOT R0` |
| SHL | 0x28 | E | rd = rs1 << rs2 | `SHL R0, R1, R2` |
| SHR | 0x29 | E | rd = rs1 >> rs2 | `SHR R0, R1, R2` |

## Exercise 1: Compute 3*4+2

**Task:** Write a FLUX program that computes `(3 * 4) + 2` and returns the result in R0.

**Requirements:**
1. Use only MOVI, MUL, and ADD instructions
2. Store the final result in R0
3. End with HALT

**Solution:**

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Compute: (3 * 4) + 2 = 14
bytecode = (
    struct.pack("<BBB", 0x18, 0, 3) +      # MOVI R0, 3
    struct.pack("<BBB", 0x18, 1, 4) +      # MOVI R1, 4
    struct.pack("<BBBB", 0x22, 0, 0, 1) +  # MUL R0, R0, R1  (R0 = 3 * 4 = 12)
    struct.pack("<BBB", 0x18, 1, 2) +      # MOVI R1, 2
    struct.pack("<BBBB", 0x20, 0, 0, 1) +  # ADD R0, R0, R1  (R0 = 12 + 2 = 14)
    bytes([0x00])                           # HALT
)

vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"Result: {result}")  # Result: 14
```

## Exercise 2: Bitwise Operations

**Task:** Write a program that:
1. Loads value 0xFF into R0
2. Loads value 0x0F into R1
3. Computes R0 = R0 & R1 (bitwise AND)
4. Returns result in R0

**Expected Result:** 0x0F (15)

> **Note:** MOVI uses sign-extended imm8, so 0xFF sign-extends to -1 (0xFFFFFFFFFFFFFFFF). Since -1 in two's complement has all bits set, AND with 0x0F (15) correctly yields 15.

**Solution:**

```python
import struct
from flux.vm.unified_interpreter import Interpreter

bytecode = (
    struct.pack("<BBB", 0x18, 0, 0xFF) +   # MOVI R0, 0xFF (sign-extends to -1)
    struct.pack("<BBB", 0x18, 1, 0x0F) +   # MOVI R1, 0x0F
    struct.pack("<BBBB", 0x25, 0, 0, 1) +  # AND R0, R0, R1
    bytes([0x00])                           # HALT
)

vm = Interpreter(bytecode, memory_size=4096)
vm.execute()
result = vm.regs[0]
print(f"Result: 0x{result:02X}")  # Result: 0x0F
```

## Progress Checkpoint

At the end of Module 1, you should be able to:

- ✅ Identify all 7 instruction formats (A through G)
- ✅ Encode simple arithmetic operations to bytecode
- ✅ Understand the register file layout (R0-R15, F0-F15, V0-V15)
- ✅ Write and execute a basic FLUX program
- ✅ Use MOVI, ADD, MUL, and bitwise operations

## Next Steps

**[Module 2: Control Flow](module-02-control-flow.md)** — Learn to implement loops, conditionals, and branching in FLUX bytecode.

---

**Need Help?** See the [ISA Unified Reference](../ISA_UNIFIED.md) for the complete opcode table or [Developer Guide](../developer-guide.md) for architecture details.
