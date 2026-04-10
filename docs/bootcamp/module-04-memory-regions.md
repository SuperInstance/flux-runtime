# Module 4: Memory Regions and Stack Operations

**Learning Objectives:**
- Understand FLUX's linear memory model with ownership
- Master stack operations (PUSH, POP, ENTER, LEAVE)
- Learn heap management and region operations
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
from flux.vm.interpreter import Interpreter

# Create VM with default regions
vm = Interpreter(bytecode=b"\x80", memory_size=65536)

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

### Region Operations via Bytecode

#### REGION_CREATE (Format G)

```python
from flux.bytecode.opcodes import Op
import struct

# Create region with name and size
name = b"my_region\0"
size = struct.pack("<I", 8192)  # 8KB
owner = b"user\0"

data = bytes([len(name)]) + name + size + bytes([len(owner)]) + owner

bytecode = (
    bytes([Op.REGION_CREATE]) +  # Opcode
    struct.pack("<H", len(data)) +  # Length
    data  # Payload
)
```

#### REGION_DESTROY (Format G)

```python
# Destroy region by name
name = b"my_region\0"

bytecode = (
    bytes([Op.REGION_DESTROY]) +
    struct.pack("<H", len(name)) +
    name
)
```

#### REGION_TRANSFER (Format G)

```python
# Transfer ownership
name = b"my_region\0"
new_owner = b"another_agent\0"

data = bytes([len(name)]) + name + bytes([len(new_owner)]) + new_owner

bytecode = (
    bytes([Op.REGION_TRANSFER]) +
    struct.pack("<H", len(data)) +
    data
)
```

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

#### PUSH and POP

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Stack operations: PUSH R0, POP R1
bytecode = bytearray()

# Load value into R0
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 42))

# Push R0 onto stack
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

# Pop from stack into R1
bytecode.extend(struct.pack("<BB", Op.POP, 1))

# HALT
bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()

print(f"R0 (original): {vm.regs.read_gp(0)}")
print(f"R1 (popped):   {vm.regs.read_gp(1)}")
```

**Output:**
```
R0 (original): 42
R1 (popped):   42
```

#### Stack Manipulation

```python
from flux.bytecode.opcodes import Op
import struct

# DUP: Duplicate top of stack
# SWAP: Swap top two elements
# ROT: Rotate top three elements

bytecode = bytearray()

# Push values
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 1))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 2))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 3))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

# Stack: [1, 2, 3] (3 is top)

# DUP: Stack becomes [1, 2, 3, 3]
bytecode.extend(bytes([Op.DUP]))

# SWAP: Stack becomes [1, 2, 3, 3] → [1, 2, 3, 3] (swaps top two)
bytecode.extend(bytes([Op.SWAP]))

# ROT: [3, 2, 3, 1] (rotates top three: c,b,a → b,a,c)
bytecode.extend(bytes([Op.ROT]))

# Pop and check
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # R0 = 3
bytecode.extend(struct.pack("<BB", Op.POP, 1))  # R1 = 2
bytecode.extend(struct.pack("<BB", Op.POP, 2))  # R2 = 3
bytecode.extend(struct.pack("<BB", Op.POP, 3))  # R3 = 1

bytecode.extend(bytes([Op.HALT]))
```

### Function Frames

#### ENTER and LEAVE

```python
from flux.bytecode.opcodes import Op
import struct

# Function frame example
bytecode = bytearray()

# Setup: R0 = param1, R1 = param2
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 10))
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 20))

# ENTER frame (allocate 4 units = 16 bytes)
# Format B: [ENTER][frame_size:u8]
bytecode.extend(struct.pack("<BB", Op.ENTER, 4))

# Use stack space (local variables)
# Store R0 at [FP-4], R1 at [FP-8]
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))  # Save param1
bytecode.extend(struct.pack("<BB", Op.PUSH, 1))  # Save param2

# Do some work...
bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 0, 1))  # R0 = R0 + R1

# LEAVE frame
bytecode.extend(struct.pack("<BB", Op.LEAVE, 0))

bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()

print(f"Result: R0 = {vm.regs.read_gp(0)}")
print(f"FP restored: {vm.regs.fp}")
print(f"SP restored: {vm.regs.sp}")
```

### Dynamic Allocation: ALLOCA

```python
from flux.bytecode.opcodes import Op
import struct

# Allocate stack space dynamically
bytecode = bytearray()

# R0 = size in units (4 bytes each)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 8))  # 8 * 4 = 32 bytes

# ALLOCA R0, R0 (allocate and store pointer in R0)
# Format C: [ALLOCA][rd][size_reg]
bytecode.extend(struct.pack("<BBB", Op.ALLOCA, 1, 0))

# R1 now contains pointer to allocated space
# Use it for temporary storage...

# Function return will automatically deallocate
bytecode.extend(bytes([Op.HALT]))
```

## Heap Operations

### Manual Heap Management

```python
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op
import struct

# Create VM with heap
vm = Interpreter(bytecode=b"\x80", memory_size=65536)

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

### MEMCOPY and MEMSET

```python
from flux.bytecode.opcodes import Op
import struct

# Copy memory region
region_name = b"heap\0"
src_offset = struct.pack("<I", 0)      # Source offset
dst_offset = struct.pack("<I", 1024)   # Destination offset
size = struct.pack("<I", 256)          # Copy 256 bytes

data = (
    bytes([len(region_name)]) + region_name +
    src_offset + dst_offset + size
)

bytecode = (
    bytes([Op.MEMCOPY]) +
    struct.pack("<H", len(data)) +
    data
)

# Fill memory with value
region_name = b"heap\0"
offset = struct.pack("<I", 0)
value = 0xFF  # Fill with 0xFF
size = struct.pack("<I", 1024)

data = (
    bytes([len(region_name)]) + region_name +
    offset + bytes([value]) + size
)

bytecode += (
    bytes([Op.MEMSET]) +
    struct.pack("<H", len(data)) +
    data
)
```

## Exercise: Stack-Based Calculator

**Task:** Build a stack-based calculator that evaluates:
```
(3 + 4) * (5 - 2) = 21
```

**Requirements:**
- Use PUSH for operands
- Use arithmetic ops that consume stack
- Result on top of stack

**Solution:**

```python
from flux.bytecode.opcodes import Op
from flux.vm.interpreter import Interpreter
import struct

# Stack calculator: (3 + 4) * (5 - 2) = 21
bytecode = bytearray()

# Push: 3, 4, 5, 2
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 3))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 4))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 5))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 2))
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

# Stack: [3, 4, 5, 2] (2 is top)

# Pop top two, add, push result
# Pop R1, R0: R1=5, R0=2
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # R0 = 2
bytecode.extend(struct.pack("<BB", Op.POP, 1))  # R1 = 5
bytecode.extend(struct.pack("<BBBB", Op.ISUB, 0, 1, 0))  # R0 = 5 - 2 = 3
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))  # Push 3

# Stack: [3, 4, 3]

# Pop top two, add, push result
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # R0 = 3
bytecode.extend(struct.pack("<BB", Op.POP, 1))  # R1 = 4
bytecode.extend(struct.pack("<BBBB", Op.IADD, 0, 1, 0))  # R0 = 4 + 3 = 7
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))  # Push 7

# Stack: [3, 7]

# Pop top two, multiply, push result
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # R0 = 7
bytecode.extend(struct.pack("<BB", Op.POP, 1))  # R1 = 3
bytecode.extend(struct.pack("<BBBB", Op.IMUL, 0, 1, 0))  # R0 = 3 * 7 = 21
bytecode.extend(struct.pack("<BB", Op.PUSH, 0))  # Push 21

# Stack: [21]

# Pop result into R0
bytecode.extend(struct.pack("<BB", Op.POP, 0))

bytecode.extend(bytes([Op.HALT]))

# Execute
vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)

print(f"Result: {result}")  # Result: 21
```

## Advanced: Memory-Mapped Data Structures

### Array Operations

```python
from flux.vm.interpreter import Interpreter
from flux.bytecode.opcodes import Op
import struct

# Create array in memory, then access elements
bytecode = bytearray()

# Setup: Create array [10, 20, 30, 40, 50]
# Use stack as temporary storage
for val in [10, 20, 30, 40, 50]:
    bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, val))
    bytecode.extend(struct.pack("<BB", Op.PUSH, 0))

# Stack has 5 elements: [10, 20, 30, 40, 50]

# Access element at index 2 (should be 30)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 2))  # Index

# Calculate address: SP + (index * 4)
# SP grows down, so address = SP + (index * 4)
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 4))  # Element size
bytecode.extend(struct.pack("<BBBB", Op.IMUL, 0, 0, 1))  # offset = index * 4

# Get current SP (in R11)
# We need to add offset to SP to get address
# This is simplified - real implementation would use LOAD with computed address

# For demo, just pop the third element
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # 50
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # 40
bytecode.extend(struct.pack("<BB", Op.POP, 0))  # 30 ← This is index 2

bytecode.extend(bytes([Op.HALT]))

vm = Interpreter(bytes(bytecode), memory_size=4096)
vm.execute()
result = vm.regs.read_gp(0)

print(f"Array[2] = {result}")  # Array[2] = 30
```

## Memory Safety

### Bounds Checking

```python
from flux.bytecode.opcodes import Op
import struct

# Safe array access with bounds checking
bytecode = bytearray()

# R0 = index, R1 = length
bytecode.extend(struct.pack("<BBh", Op.MOVI, 0, 5))   # Index
bytecode.extend(struct.pack("<BBh", Op.MOVI, 1, 10))  # Length

# CHECK_BOUNDS R0, R1
bytecode.extend(struct.pack("<BBB", Op.CHECK_BOUNDS, 0, 1))

# If we get here, access is safe
bytecode.extend(bytes([Op.HALT]))
```

## Progress Checkpoint

At the end of Module 4, you should be able to:

- ✅ Create and manage memory regions
- ✅ Use stack operations (PUSH, POP, DUP, SWAP, ROT)
- ✅ Implement function frames (ENTER/LEAVE)
- ✅ Perform dynamic allocation (ALLOCA)
- ✅ Use memory operations (MEMCOPY, MEMSET)
- ✅ Build stack-based data structures

## Next Steps

**[Module 5: FIR Pipeline](module-05-fir-pipeline.md)** — Explore the C→FIR→Bytecode→VM compilation pipeline.

---

**Need Help?** See the [Memory Management Reference](../user-guide.md#memory-management) for complete memory operations.
