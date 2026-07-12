# FLUX Tutorial: From Zero to First Program

**FLUX** is a register-based bytecode VM for running agent logic deterministically.
This tutorial takes you from installation to writing a real agent controller in under 30 minutes.

---

## Table of Contents

1. [What is FLUX?](#1-what-is-flux)
2. [Install](#2-install)
3. [Your First Program](#3-your-first-program)
4. [Arithmetic and Loops](#4-arithmetic-and-loops)
5. [Memory and Stack](#5-memory-and-stack)
6. [Building a Real Agent: The Deadband Controller](#6-building-a-real-agent-the-deadband-controller)
7. [Compiling and Running](#7-compiling-and-running)
8. [Cross-Implementation Compatibility](#8-cross-implementation-compatibility)
9. [Next Steps](#9-next-steps)

---

## 1. What is FLUX?

FLUX (Fluid Language Universal eXecution) is a **bytecode VM for running agent logic deterministically**.

Think of it as a CPU for AI decisions. Instead of paying for an LLM call every time your agent needs to decide something — "should I turn on the AC?", "is this message urgent?", "which branch should I take?" — you compile the decision policy to FLUX bytecode and run it for **microseconds**, not seconds.

### The Problem FLUX Solves

Modern AI agents burn tokens on decisions that are fundamentally deterministic. A thermostat doesn't need a language model to decide that 80° is too hot. A routing agent doesn't need GPT to check if a number is above a threshold. But you still want these decisions:

- **Auditable** — every step is traceable, no stochastic black boxes
- **Portable** — the same bytecode runs on Python, Rust, and JavaScript
- **Fast** — microseconds, not API round-trips
- **Free** — no per-execution cost after compilation

### How It Works

```
Decision policy (FLUX assembly) → Assembler → Bytecode (.bin) → VM execution
```

You write FLUX assembly (`.flx` files), compile it to compact bytecode, then execute on any FLUX VM. The VM is a register machine with 16 general-purpose registers, arithmetic, memory, stack, and conditional jumps — enough to express any deterministic decision logic.

### Where FLUX Fits in Your Stack

| Layer | Tool | Speed | Cost |
|-------|------|-------|------|
| Complex reasoning, language | LLM (GPT, Claude) | Seconds | $ per call |
| Deterministic policies, rules | **FLUX** | Microseconds | Free |
| Raw computation | Your app code | Varies | Free |

FLUX doesn't replace LLMs — it handles the layer of decisions that shouldn't need one.

---

## 2. Install

```bash
pip install flux-vm
```

Verify the install:

```bash
flux --version
```

You should see something like `flux-vm 0.1.0`. That's it — you're ready.

> **Prerequisites:** Python 3.9+. The package includes the assembler, VM, and CLI tools.

---

## 3. Your First Program

Let's start with the simplest possible FLUX program — the equivalent of "Hello, World":

```asm
;; hello.flx — The minimal FLUX program

    MOVI R0, 42          ;; R0 = 42 (the answer)
    HALT                 ;; stop execution
```

That's it. Two instructions. Let's break it down.

### Registers: Your Variables

FLUX has **16 general-purpose registers**, named `R0` through `R15`. Think of them as 16 variables that are always integers. There are no named variables in FLUX assembly — you work directly with registers.

By convention, **R0 is the return value** — like `main()` returning an int in C. When the program finishes, you inspect the registers to see what it computed.

### MOVI: Move Immediate

```asm
MOVI R0, 42
```

`MOVI` (Move Immediate) puts a constant value into a register. Here, it sets `R0` to `42`. The instruction is 4 bytes: 1 for the opcode, 1 for the register, 2 for the signed 16-bit immediate.

### HALT: Stop

```asm
HALT
```

`HALT` stops the VM. Every FLUX program must end with `HALT`. Without it, the VM will run off the end of your bytecode and crash.

### Running It

```bash
flux run examples/hello.flx
```

Output:

```
R0 = 42
Cycles: 2
```

After `HALT`, you read `R0` to get the result. That's how all FLUX programs communicate — through registers, not through an output stream. There is no `PRINT` instruction. The host environment inspects the register file after execution.

### Instruction Formats at a Glance

FLUX uses variable-length instructions. Here's what you'll encounter:

| Format | Size | Example | Used By |
|--------|------|---------|---------|
| A | 1 byte | `HALT` | Opcodes with no operands |
| B | 2 bytes | `INC R0` | Opcode + one register |
| C | 3 bytes | `MOV R7, R0` | Opcode + two registers |
| D | 4 bytes | `MOVI R0, 42` | Opcode + register + 16-bit immediate |
| E | 4 bytes | `IADD R0, R0, R1` | Opcode + three registers |

You don't need to memorize these — the assembler handles encoding. But understanding the shapes helps you reason about program size.

---

## 4. Arithmetic and Loops

Real programs compute things. Let's look at the Fibonacci sequence — a classic loop that demonstrates arithmetic, register management, and conditional jumps.

```asm
;; fibonacci.flx — First 10 Fibonacci Numbers
;;
;; Register allocation:
;;   R0 = a (current fib value)
;;   R1 = b (next fib value)
;;   R2 = i (loop counter)
;;   R3 = n (limit = 10)

    MOVI R0, 0           ;; a = fib(0) = 0
    MOVI R1, 1           ;; b = fib(1) = 1
    MOVI R2, 0           ;; i = 0
    MOVI R3, 10          ;; n = 10

fib_loop:
    ;; Compute: new_a = b, new_b = old_a + old_b
    MOV  R5, R1          ;; R5 = b (save it)
    IADD R1, R0, R1      ;; R1 = a + b (new b)
    MOV  R0, R5          ;; R0 = old b (new a)

    INC  R2              ;; i++
    CMP  R2, R3          ;; compare i with n
    JL   fib_loop        ;; if i < n, loop again

    HALT
;; R0 = 55 (fib(10))
```

### Arithmetic Opcodes

| Opcode | Format | Action | Example |
|--------|--------|--------|---------|
| `IADD` | E | `rd = rs1 + rs2` | `IADD R0, R0, R1` |
| `ISUB` | E | `rd = rs1 - rs2` | `ISUB R0, R0, R1` |
| `IMUL` | E | `rd = rs1 * rs2` | `IMUL R0, R0, R1` |
| `IDIV` | E | `rd = rs1 / rs2` | `IDIV R0, R0, R1` |
| `IMOD` | E | `rd = rs1 % rs2` | `IMOD R0, R0, R1` |
| `INC`  | B | `reg = reg + 1` | `INC R2` |
| `DEC`  | B | `reg = reg - 1` | `DEC R2` |

All arithmetic is **integer** (32-bit signed). For floating-point, use the `FADD`, `FSUB`, `FMUL`, `FDIV` opcodes with `F0`–`F15` registers.

### Labels and Jumps

```asm
fib_loop:               ;; ← label marks a position in code
    ...
    JL   fib_loop       ;; ← jump to label if "less than"
```

**Labels** are named positions in your code. The assembler converts them to byte offsets. You use them with jump instructions:

| Opcode | Condition | When to use |
|--------|-----------|-------------|
| `JMP`  | Unconditional | Always jump |
| `JZ`   | Zero flag set | After CMP where values are equal |
| `JNZ`  | Zero flag not set | After CMP where values differ |
| `JE`   | Equal | Same as JZ |
| `JNE`  | Not equal | Same as JNZ |
| `JG`   | Greater | `rs1 > rs2` |
| `JL`   | Less | `rs1 < rs2` |
| `JGE`  | Greater or equal | `rs1 >= rs2` |
| `JLE`  | Less or equal | `rs1 <= rs2` |

### How CMP Works

```asm
CMP R2, R3    ;; compares R2 with R3, sets zero/sign flags
JL  fib_loop  ;; jumps if R2 < R3
```

`CMP` subtracts the second operand from the first (internally) and sets flags. It doesn't modify registers — it just sets up the conditions that jump instructions check. This is exactly how x86 and ARM work.

### How Loops Work in FLUX Assembly

FLUX has no `for` or `while` keywords. Loops are built from three pieces:

1. **A label** marking the top of the loop body
2. **A counter** (usually in a register)
3. **A conditional jump** at the bottom that goes back to the label

```
    MOVI R2, 0           ;; init counter
loop:                     ;; ← label
    ...                  ;; loop body
    INC  R2              ;; counter++
    CMP  R2, R3          ;; counter < limit?
    JL   loop            ;; if yes, go back to loop
```

This pattern: **init → label → body → increment → compare → conditional jump** — is the backbone of all FLUX loops. You'll see it everywhere.

---

## 5. Memory and Stack

Registers are fast but limited (only 16). For larger data — lookup tables, sensor readings, action histories — FLUX provides two storage mechanisms: **memory** and the **stack**.

### Memory: LOAD and STORE

FLUX memory is a flat array of integer cells, addressed by number. You write with `STORE` and read with `LOAD`.

```asm
;; memory_demo.flx — Store and load values

    ;; --- Store phase ---
    MOVI R0, 10          ;; value = 10
    MOVI R1, 0           ;; address = 0
    STORE R0, R1         ;; mem[0] = 10

    MOVI R0, 20
    MOVI R1, 1
    STORE R0, R1         ;; mem[1] = 20

    MOVI R0, 30
    MOVI R1, 2
    STORE R0, R1         ;; mem[2] = 30

    ;; --- Load phase ---
    MOVI R1, 0
    LOAD R2, R1          ;; R2 = mem[0] = 10

    MOVI R1, 2
    LOAD R0, R1          ;; R0 = mem[2] = 30

    HALT
```

**STORE R0, R1** means: write the value of register R0 into memory at the address held in R1.
**LOAD R2, R1** means: read memory at the address held in R1 and put the result in R2.

Think of memory as a numbered shelf: `STORE` puts something on a shelf, `LOAD` takes it off. The address is always a register, not a literal — this lets you compute addresses at runtime (essential for arrays and tables).

#### Memory Layout

```
Address:  0    1    2    3    4    5   ...
        [ 10 | 20 | 30 |  . |  . |  . | ... ]
```

Memory is shared with the stack region. Low addresses (0–N) are general-purpose storage; the stack grows from the top of the region downward. In practice, keep your data at addresses you manage explicitly and let PUSH/POP use the high end.

### The Stack: PUSH and POP

The stack is a **LIFO** (Last In, First Out) structure. You push values on, pop them off. The last thing you push is the first thing you pop.

```asm
;; stack_demo.flx — LIFO operations

    MOVI R0, 100
    MOVI R1, 200
    MOVI R2, 300

    PUSH R0              ;; stack: [100]
    PUSH R1              ;; stack: [100, 200]
    PUSH R2              ;; stack: [100, 200, 300]

    ;; Clear registers to prove POP restores them
    MOVI R0, 0
    MOVI R1, 0
    MOVI R2, 0

    POP R2               ;; R2 = 300 (last pushed, first popped)
    POP R1               ;; R1 = 200
    POP R0               ;; R0 = 100

    HALT
;; R0=100, R1=200, R2=300 — fully restored
```

#### When to Use the Stack vs Memory

| Use Memory (LOAD/STORE) when... | Use the Stack (PUSH/POP) when... |
|---|---|
| You need random access by address | You need temporary scratch space |
| You're building lookup tables | You're saving/restoring registers |
| Data has a fixed layout | Data is transient (function-call style) |
| You want to persist values across loop iterations | You want LIFO ordering |

The stack is perfect for "save these values, do something, restore them." Memory is better for structured data that needs to be addressable.

---

## 6. Building a Real Agent: The Deadband Controller

Time for the canonical FLUX use case: a **thermostat deadband controller**. This is the kind of deterministic agent logic that doesn't need an LLM — it just needs fast, auditable rules.

### The Problem

You have a thermostat. The rules are simple:

- If temperature > 75°F → turn on **cooling**
- If temperature < 65°F → turn on **heating**
- If 65°F ≤ temperature ≤ 75°F → **do nothing** (this gap is the "deadband")

The deadband prevents rapid cycling — you don't want the AC flipping on and off every second when the temperature hovers at exactly 75°.

### The FLUX Solution

```asm
;; deadband.flx — Thermostat Deadband Controller
;;
;; Register allocation:
;;   R0 = current temperature (input)
;;   R1 = output action (0=idle, 1=cool, 2=heat)
;;   R2 = loop counter
;;   R3 = upper bound (75)
;;   R4 = lower bound (65)
;;   R5 = 10 (iteration count)
;;
;; Memory layout:
;;   mem[0..9] = temperature readings: 70,78,60,72,66,80,64,70,76,68

    ;; --- Initialize constants ---
    MOVI R3, 75          ;; upper threshold
    MOVI R4, 65          ;; lower threshold
    MOVI R5, 10          ;; iteration count
    MOVI R2, 0           ;; counter = 0

    ;; --- Seed memory with test temperatures ---
    MOVI R0, 70
    MOVI R6, 0
    STORE R0, R6         ;; mem[0] = 70

    MOVI R0, 78
    MOVI R6, 1
    STORE R0, R6         ;; mem[1] = 78

    MOVI R0, 60
    MOVI R6, 2
    STORE R0, R6         ;; mem[2] = 60

    ;; ... (remaining temperatures stored similarly)

    ;; --- Main control loop ---
loop_start:
    LOAD R0, R2          ;; R0 = temperature from mem[counter]

    CMP  R0, R3          ;; compare temp with upper bound (75)
    JG   temp_above      ;; if temp > 75 → cool

    CMP  R0, R4          ;; compare temp with lower bound (65)
    JL   temp_below      ;; if temp < 65 → heat

    MOVI R1, 0           ;; action = IDLE
    JMP  next_iter

temp_above:
    MOVI R1, 1           ;; action = COOL
    JMP  next_iter

temp_below:
    MOVI R1, 2           ;; action = HEAT

next_iter:
    MOV  R6, R2          ;; R6 = counter
    IADD R6, R6, R5      ;; R6 = counter + 10
    STORE R1, R6         ;; mem[counter+10] = action

    INC  R2              ;; counter++
    CMP  R2, R5          ;; counter == 10?
    JL   loop_start      ;; if counter < 10, loop

    HALT
```

### Walking Through the Logic

**Step 1: Initialize** — Load the thresholds (75, 65) and iteration count (10) into registers. Zero the counter.

**Step 2: Seed Data** — Store simulated temperature readings into `mem[0..9]`. In a production system, these would come from a sensor or message queue.

**Step 3: The Control Loop** — For each temperature reading:

```
LOAD R0, R2          ;; 1. SENSE: read temperature from memory
CMP  R0, R3          ;; 2. DECIDE: compare against thresholds
JG   temp_above      ;;    → branch based on comparison
...
MOVI R1, 0/1/2       ;; 3. ACT: set the action code
STORE R1, R6         ;; 4. STORE: save action for the host to read
```

This is the **sense → decide → act** loop — the fundamental pattern of all agent logic:

```
       ┌──────────────────────────┐
       │                          │
  SENSE │  READ INPUT (LOAD)       │
       │         ↓                │
  DECIDE│  COMPARE (CMP)           │
       │         ↓                │
       │  BRANCH (JG/JL/JMP)      │
       │         ↓                │
  ACT   │  WRITE OUTPUT (STORE)    │
       │         ↓                │
       │  ADVANCE (INC + JL)       │
       └──────────────────────────┘
```

### Expected Results

| Input | Temperature | Action | Meaning |
|-------|-------------|--------|---------|
| mem[0] | 70°F | 0 | Idle (within deadband) |
| mem[1] | 78°F | 1 | Cool (above 75°) |
| mem[2] | 60°F | 2 | Heat (below 65°) |
| mem[3] | 72°F | 0 | Idle (within deadband) |
| mem[4] | 68°F | 0 | Idle (within deadband) |

Actions are stored at `mem[10..14]` for the host to read after execution.

### Why This Matters

This pattern — sense input, compare against thresholds, emit action — generalizes far beyond thermostats:

- **Alert routing:** severity > 8 → page on-call, severity > 5 → Slack, else → log
- **Rate limiting:** requests > 1000/min → throttle, else → allow
- **Content filtering:** toxicity score > 0.8 → block, > 0.3 → flag, else → publish
- **Trading:** spread > threshold → execute, else → hold

Any decision that follows rules can be compiled to FLUX. The bytecode runs in microseconds, costs nothing per execution, and is fully deterministic and auditable.

---

## 7. Compiling and Running

### Assemble to Bytecode

```bash
flux compile my_program.flx -o program.bin
```

This converts your `.flx` assembly into compact FLUX bytecode. The `.bin` file is portable — it contains no implementation-specific data.

### Run Bytecode

```bash
flux run program.bin
```

The VM loads the bytecode, executes it, and prints the register state after `HALT`.

### One-Step (Compile + Run)

```bash
flux run my_program.flx
```

The CLI detects the `.flx` extension, assembles in memory, and runs directly.

### Programmatic API (Python)

```python
from flux.asm.cross_assembler import CrossAssembler, OutputFormat
from flux.vm.interpreter import Interpreter

source = open("deadband.flx").read()

assembler = CrossAssembler()
result = assembler.assemble(source, output_format=OutputFormat.BINARY)

vm = Interpreter(result.bytecode)
vm.execute()

print(f"R0 = {vm.regs.read_gp(0)}")   # last temperature
print(f"R1 = {vm.regs.read_gp(1)}")   # last action
print(f"Cycles: {vm.cycles}")
```

This is how a host application embeds FLUX — assemble, execute, inspect registers. The host decides what the register values mean (temperature, action code, severity level, etc.).

---

## 8. Cross-Implementation Compatibility

FLUX bytecode is portable across three reference implementations:

| Implementation | Language | Repository |
|---|---|---|
| flux-runtime | Python | `SuperInstance/flux-runtime` |
| flux-core | Rust | `SuperInstance/flux-core` |
| flux-js | JavaScript | `SuperInstance/flux-js` |

### Test It Yourself

```bash
# Compile once
flux compile deadband.flx -o deadband.bin

# Run on Python VM
python3 -c "
from flux.vm.interpreter import Interpreter
vm = Interpreter(open('deadband.bin','rb').read())
vm.execute()
print('Python:', vm.regs.read_gp(1))
"

# Run on Rust VM
fluxvm run deadband.bin

# Run on JS VM
node -e "
const { VM } = require('flux-js');
const vm = new VM(fs.readFileSync('deadband.bin'));
vm.execute();
console.log('JS:', vm.regs[1]);
"
```

All three produce **identical register state**. The bytecode spec guarantees this — every opcode in the shared subset has the same semantics across all implementations.

### What "Cross-Compatible" Means in Practice

- **Assemble on one platform, deploy on another.** Compile on your dev machine (Python), run in production (Rust).
- **Share bytecode artifacts.** Your `.bin` files are deployment artifacts, checked into CI/CD, not regenerated per runtime.
- **Test once, trust everywhere.** If a `.bin` passes your Python test suite, it will behave identically in the Rust or JS runtime.

---

## 9. Next Steps

You now know enough FLUX to write and run real agent logic. Here's where to go deeper:

### Read the Spec

- **[FLUX_BYTECODE_SPEC.md](https://github.com/SuperInstance/AI-Writings/blob/main/FLUX_BYTECODE_SPEC.md)** — Full opcode table, encoding details, flag semantics, and edge cases. This is the canonical reference.

### Try the Playground

- **[FLUX Playground](https://superinstance.github.io/flux-js/playground/)** — Write, assemble, and execute FLUX in your browser. Great for experimenting with snippets without installing anything.

### Browse More Examples

The `examples/` directory in flux-runtime has complete runnable programs:

| File | Teaches |
|------|---------|
| `hello.flx` | Minimal program (MOVI, HALT) |
| `fibonacci.flx` | Loops and arithmetic |
| `factorial.flx` | Decrementing loops with JNZ |
| `deadband.flx` | Real agent controller |
| `counter.flx` | Simplest meaningful loop |
| `stack_demo.flx` | PUSH/POP and LIFO |
| `memory_demo.flx` | LOAD/STORE and memory layout |
| `register_math.flx` | All five arithmetic operations |

### Read the Theory

- **[AI-Writings](https://github.com/SuperInstance/AI-Writings)** — Essays on conservation laws in computation, why deterministic agent layers matter, and the design principles behind FLUX.

### Join In

- File issues in any SuperInstance repository
- Propose new opcodes via the bytecode spec repo
- Share your `.flx` programs — the community is small but growing

---

**That's FLUX.** A tiny VM with a big idea: not every decision needs a language model. Some just need a CPU.

Write your policies, compile them, run them for free.
