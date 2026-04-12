> **Updated 2026-04-12: Aligned with converged FLUX ISA v2** — All opcode values and names now reference the unified ISA from `isa_unified.py`. Notable changes: PUSH/POP are now 0x0C/0x0D, ENTER/LEAVE are Format G (5 bytes), MEMCOPY→COPY, MEMSET→FILL, REGION ops replaced by MALLOC/FREE. See `docs/ISA_UNIFIED.md` for the canonical reference.

# Module 4: Memory Regions and Stack Operations

**Learning Objectives:**
- Understand FLUX's linear memory model with ownership
- Master stack operations (PUSH, POP, ENTER, LEAVE)
- Learn heap management and allocation
- Build memory-efficient programs

## Memory Architecture Overview

FLUX uses a **capability-based linear memory model**:

```
┌─────────────────────────────────────────────────────────┐
│  FLUX Memory Manager                                    │
├─────────────────────────────────────────────────────────┤
│  Region Name    Size    Owner     Permissions           │
│  ────────────   ────    ──────    ────────────────────  │
│  "stack"        64KB    "system"   read/write           │
│  "heap"         64KB    "user"     read/write           │
│  "data"         32KB    "user"     read/write           │
│  "code"         16KB    "system"   read/execute         │
│  ...            ...     ...       ...                   │
└─────────────────────────────────────────────────────────┘
```

### Memory Region Properties

Each region has:
- **Name** — String identifier for addressing
- **Size** — Byte capacity (fixed after creation)
- **Owner** — Agent ID that owns the region
- **Borrowers** — List of agents with read-only access

## Creating and Managing Regions

### Region Creation

```python
from flux.vm.unified_interpreter import Interpreter

# Create VM with default regions (HALT = 0x00 in converged ISA)
vm = Interpreter(bytecode=b"\x00", memory_size=65536)

# Access memory manager
memory = vm.memory

# Create custom region
region = memory.create_region(
    name="buffer",
    size=4096,
    owner="user_agent"
)

print(f"Region: {region.name}, Size: {region.size}, Owner: {region.owner}")
```

### Allocation via Bytecode (MALLOC / FREE)

The converged ISA provides MALLOC and FREE for dynamic memory allocation (Format G):

```python
import struct

# MALLOC R0, R1, size — Allocate size bytes, handle→R0
# (R1 is unused/reserved, size is imm16)
bytecode = (
    struct.pack("<BBBh", 0xD7, 0, 0, 8192)  # MALLOC R0, R1, 8192 (allocate 8KB)
    bytes([0x00])                             # HALT
)

# FREE R0, R1, 0 — Free allocation at R0
bytecode = (
    struct.pack("<BBBh", 0xD8, 0, 0, 0)     # FREE R0, R1, 0
    bytes([0x00])                             # HALT
)
```

> **Note:** The old REGION_CREATE, REGION_DESTROY, and REGION_TRANSFER opcodes are deprecated in the converged ISA. Use MALLOC (0xD7) and FREE (0xD8) instead.

## Stack Operations

### Stack Layout

```
┌─────────────────────────────────────────────────────────┐
│  Stack Region (grows downward)                          │
│  ─────────────────────────────────────────────────────  │
│  High Addresses                                         │
│     │                                                   │
│     ├─ [saved FP]                                       │
│     ├─ [local vars]                                     │
│     ├─ [saved registers]                                │
│     ├─ [return address]                                 │
│     │                                                   │
│     └─ SP (Stack Pointer) ← R11                        │
│                                                          │
│  Low Addresses                                          │
└─────────────────────────────────────────────────────────┘
```

### Basic Stack Operations

#### PUSH and POP (Format B, 2 bytes)

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Stack operations: PUSH R0, POP R1
bytecode = bytearray()

# Load value into R0
bytecode.extend(struct.pack("<BBB", 0x18, 0, 42))   # MOVI R0, 42 (Format D)

# Push R0 onto stack (PUSH = 0x0C, Format B)
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0

# Pop from stack into R1 (POP = 0x0D, Format B)
bytecode.extend(struct.pack("<BB", 0x0D, 1))        # POP R1

# HALT
bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()

print(f"R0 (original): {vm.regs[0]}")
print(f"R1 (popped):   {vm.regs[1]}")
```

**Output:**
```
R0 (original): 42
R1 (popped):   42
```

#### Stack Manipulation with SWP

```python
import struct

# SWP (0x3B, Format E): swap(rd, rs1)
# Push values, then swap top two via registers

bytecode = bytearray()

# Push values
bytecode.extend(struct.pack("<BBB", 0x18, 0, 1))    # MOVI R0, 1
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0
bytecode.extend(struct.pack("<BBB", 0x18, 0, 2))    # MOVI R0, 2
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0

# Stack: [1, 2] (2 is top)

# Pop into R0 and R1
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (R0 = 2)
bytecode.extend(struct.pack("<BB", 0x0D, 1))        # POP R1  (R1 = 1)

# Swap them
bytecode.extend(struct.pack("<BBBB", 0x3B, 0, 1, 0))  # SWP R0, R1

# Push back in new order
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (was R1 = 1)
bytecode.extend(struct.pack("<BB", 0x0C, 1))        # PUSH R1 (was R0 = 2)

# Stack: [1, 2] → after swap: [2, 1]

# Pop and verify
bytecode.extend(struct.pack("<BB", 0x0D, 2))        # POP R2 (should be 1)
bytecode.extend(struct.pack("<BB", 0x0D, 3))        # POP R3 (should be 2)

bytecode.extend(bytes([0x00]))                       # HALT
```

> **Note:** The old DUP and ROT opcodes are not in the converged ISA. Use PUSH/POP with MOV to duplicate values, or SWP to exchange values between registers.

### Function Frames

#### ENTER and LEAVE (Format G, 5 bytes)

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Function frame example
bytecode = bytearray()

# Setup: R0 = param1, R1 = param2
bytecode.extend(struct.pack("<BBB", 0x18, 0, 10))   # MOVI R0, 10
bytecode.extend(struct.pack("<BBB", 0x18, 1, 20))   # MOVI R1, 20

# ENTER frame (Format G): push regs; sp -= imm16; rd=old_sp
# ENTER R14 (FP), R1, 16 — save frame pointer, allocate 16 bytes
bytecode.extend(struct.pack("<BBBh", 0x4C, 14, 0, 16))  # ENTER R14, R1, 16

# Use stack space (local variables)
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (save param1)
bytecode.extend(struct.pack("<BB", 0x0C, 1))        # PUSH R1 (save param2)

# Do some work...
bytecode.extend(struct.pack("<BBBB", 0x20, 0, 0, 1))  # ADD R0, R0, R1

# LEAVE frame (Format G): sp += imm16; pop regs; rd=ret
bytecode.extend(struct.pack("<BBBh", 0x4D, 14, 0, 16))  # LEAVE R14, R1, 16

bytecode.extend(bytes([0x00]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()

print(f"Result: R0 = {vm.regs[0]}")
print(f"FP restored: {vm.regs[14]}")
```

## Heap Operations

### Manual Heap Management

```python
from flux.vm.unified_interpreter import Interpreter

# Create VM with heap (HALT = 0x00 in converged ISA)
vm = Interpreter(bytecode=b"\x00", memory_size=65536)

# Access heap region
heap = vm.memory.get_region("heap")

# Manual allocation: simple bump pointer
heap_ptr = 0
allocation_size = 32

if heap_ptr + allocation_size <= heap.size:
    allocated_addr = heap_ptr
    heap_ptr += allocation_size

    # Write data
    heap.write_i32(allocated_addr, 42)
    value = heap.read_i32(allocated_addr)

    print(f"Allocated at {allocated_addr}, value: {value}")
```

### COPY and FILL (Format G, 5 bytes)

```python
import struct

# COPY R0, R1, 256 — Copy 256 bytes from R1 to R0 (memcpy)
bytecode = (
    struct.pack("<BBBh", 0x4E, 0, 1, 256)  # COPY R0, R1, 256
    bytes([0x00])
)

# FILL R0, R1, 1024 — Fill 1024 bytes at R0 with value in R1 (memset)
bytecode = (
    struct.pack("<BBBh", 0x4F, 0, 1, 1024)  # FILL R0, R1, 1024
    bytes([0x00])
)
```

> **Note:** The old MEMCOPY and MEMSET opcodes are now COPY (0x4E) and FILL (0x4F) in the converged ISA. They use register operands (Format G) instead of variable-length serialized data.

## Exercise: Stack-Based Calculator

**Task:** Build a stack-based calculator that evaluates:
```
(3 + 4) * (5 - 2) = 21
```

**Requirements:**
- Use PUSH for operands
- Use arithmetic ops with registers
- Result in R0

**Solution:**

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Stack calculator: (3 + 4) * (5 - 2) = 21
bytecode = bytearray()

# Push: 3, 4, 5, 2
bytecode.extend(struct.pack("<BBB", 0x18, 0, 3))
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (3)

bytecode.extend(struct.pack("<BBB", 0x18, 0, 4))
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (4)

bytecode.extend(struct.pack("<BBB", 0x18, 0, 5))
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (5)

bytecode.extend(struct.pack("<BBB", 0x18, 0, 2))
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (2)

# Stack: [3, 4, 5, 2] (2 is top)

# Pop top two, subtract: 5 - 2 = 3
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (R0 = 2)
bytecode.extend(struct.pack("<BB", 0x0D, 1))        # POP R1  (R1 = 5)
bytecode.extend(struct.pack("<BBBB", 0x21, 0, 1, 0))  # SUB R0, R1, R0 (R0 = 5 - 2 = 3)
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (3)

# Stack: [3, 4, 3]

# Pop top two, add: 4 + 3 = 7
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (R0 = 3)
bytecode.extend(struct.pack("<BB", 0x0D, 1))        # POP R1  (R1 = 4)
bytecode.extend(struct.pack("<BBBB", 0x20, 0, 1, 0))  # ADD R0, R1, R0 (R0 = 4 + 3 = 7)
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (7)

# Stack: [3, 7]

# Pop top two, multiply: 3 * 7 = 21
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (R0 = 7)
bytecode.extend(struct.pack("<BB", 0x0D, 1))        # POP R1  (R1 = 3)
bytecode.extend(struct.pack("<BBBB", 0x22, 0, 1, 0))  # MUL R0, R1, R0 (R0 = 3 * 7 = 21)
bytecode.extend(struct.pack("<BB", 0x0C, 0))        # PUSH R0 (21)

# Stack: [21]

# Pop result into R0
bytecode.extend(struct.pack("<BB", 0x0D, 0))

bytecode.extend(bytes([0x00]))                       # HALT

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]

print(f"Result: {result}")  # Result: 21
```

## Advanced: Memory-Mapped Data Structures

### Array Operations

```python
import struct
from flux.vm.unified_interpreter import Interpreter

# Create array in memory, then access elements
bytecode = bytearray()

# Setup: Create array [10, 20, 30, 40, 50]
# Use stack as temporary storage
for val in [10, 20, 30, 40, 50]:
    bytecode.extend(struct.pack("<BBB", 0x18, 0, val))
    bytecode.extend(struct.pack("<BB", 0x0C, 0))    # PUSH R0

# Stack has 5 elements: [10, 20, 30, 40, 50]

# For demo, pop the third element
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (50)
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (40)
bytecode.extend(struct.pack("<BB", 0x0D, 0))        # POP R0  (30) ← This is index 2

bytecode.extend(bytes([0x00]))

vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs[0]

print(f"Array[2] = {result}")  # Array[2] = 30
```

## Memory Safety

### Bounds Checking

In the converged ISA, bounds checking is performed at the **interpreter level** rather than via a dedicated opcode. The unified VM enforces memory region boundaries on every LOAD/STORE operation.

```python
import struct

# Safe array access — the VM automatically checks bounds
bytecode = bytearray()

# R0 = index, R1 = base address
bytecode.extend(struct.pack("<BBB", 0x18, 0, 5))    # MOVI R0, 5 (index)
bytecode.extend(struct.pack("<BBB", 0x18, 1, 256))  # MOVI R1, 256 (base address)

# LOADOFF R2, R1, 20 — Load from mem[R1 + 20] (Format G, 5 bytes)
# The VM validates that R1 + 20 is within the memory region
bytecode.extend(struct.pack("<BBBh", 0x48, 2, 1, 20))  # LOADOFF R2, R1, 20

bytecode.extend(bytes([0x00]))
```

> **Note:** The old CHECK_BOUNDS opcode is not in the converged ISA. Bounds checking is handled automatically by the VM's memory subsystem on every memory access operation.

## Progress Checkpoint

At the end of Module 4, you should be able to:

- ✅ Use MALLOC (0xD7) and FREE (0xD8) for dynamic allocation
- ✅ Use stack operations PUSH (0x0C), POP (0x0D)
- ✅ Use SWP (0x3B) for value exchange
- ✅ Implement function frames with ENTER (0x4C) / LEAVE (0x4D)
- ✅ Use COPY (0x4E) and FILL (0x4F) for bulk memory operations
- ✅ Build stack-based data structures

## Next Steps

**[Module 5: FIR Pipeline](module-05-fir-pipeline.md)** — Explore the C→FIR→Bytecode→VM compilation pipeline.

---

**Need Help?** See the [ISA Unified Reference](../ISA_UNIFIED.md) for complete opcode table.
