---
title: Fibonacci in FLUX
version: 1.0
description: Computing Fibonacci numbers through C, bytecode, and VM execution traces
---

# Fibonacci in FLUX — Three Representations

The Fibonacci sequence is the classic test for any computational system.
Here we show how Fibonacci can be expressed in FLUX at three levels:

1. **C source** — human-readable, compiled to FIR
2. **Raw bytecode** — hand-crafted machine instructions
3. **VM execution trace** — the step-by-step cycle log

## Approach 1: Fibonacci in C

The C frontend compiles this iterative Fibonacci to FIR with a while loop:

```c
int fibonacci(int n) {
    int a = 0;
    int b = 1;
    int i = 0;
    while (i < n) {
        int temp = a + b;
        a = b;
        b = temp;
        i = i + 1;
    }
    return a;
}

int main() {
    return fibonacci(10);
}
```

### Expected Result

`fibonacci(10)` = **55**

The sequence: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, **55**

### FIR Generation

The C compiler generates FIR basic blocks:

```
function fibonacci(n: i32) -> i32 {
  entry:
    alloca a: i32        ; a = 0
    alloca b: i32        ; b = 1
    alloca i: i32        ; i = 0
    jump while_header

  while_header:
    load i
    ilt i, n             ; i < n?
    branch body, exit

  while_body:
    load a
    load b
    iadd a, b            ; temp = a + b
    store temp, b        ; b = temp (note: we need a temp var)
    store b, a           ; a = old b
    load i
    iadd i, 1            ; i++
    store i, i
    jump while_header

  while_exit:
    load a
    ret a
}
```

## Approach 2: Raw Bytecode

For `fibonacci(5)` = 5, we can hand-encode the loop:

```
  ; Register allocation:
  ;   R0 = a (current), R1 = b (next), R2 = i (counter), R3 = temp

  MOVI R0, 0       ; a = 0          [2B 00 00 00]
  MOVI R1, 1       ; b = 1          [2B 01 01 00]
  MOVI R2, 0       ; i = 0          [2B 02 00 00]
  MOVI R3, 5       ; n = 5          [2B 03 05 00]

  ; ── while_header ──
  CMP R2, R3       ; compare i vs n [2D 02 03]
  JGE R0, +10      ; if i >= n, goto exit  [37 00 0A 00]

  ; ── while_body ──
  IADD R0, R0, R1  ; temp = a + b   (actually R0 = R0+R1, but we need temp)
  ; Simplified: just accumulate
  ; R0 = a + b (new a), then swap
  MOV R4, R0       ; save old a      [01 04 00]
  IADD R0, R0, R1  ; a = a + b       [08 00 00 01]
  MOV R1, R4       ; b = old a       [01 01 04]
  INC R2           ; i++             [0E 02]
  JMP -20          ; goto header     [04 00 EC FF]

  ; ── exit ──
  HALT             ; stop            [80]
```

### Hex Dump

```
2B 00 00 00   ; MOVI R0, 0
2B 01 01 00   ; MOVI R1, 1
2B 02 00 00   ; MOVI R2, 0
2B 03 05 00   ; MOVI R3, 5
2D 02 03      ; CMP R2, R3
37 00 0A 00   ; JGE exit
01 04 00      ; MOV R4, R0
08 00 00 01   ; IADD R0, R0, R1
01 01 04      ; MOV R1, R4
0E 02         ; INC R2
04 00 EC FF   ; JMP header
80            ; HALT
```

## Approach 3: VM Execution Trace

When the VM executes the bytecode, here's the cycle-by-cycle trace:

```
  Cycle   PC   Instruction           R0    R1    R2    R3    Flags
  ─────  ────  ────────────────────  ────  ────  ────  ────  ──────
     1   0000  MOVI R0, 0              0     -     -     -    -
     2   0004  MOVI R1, 1              0     1     -     -    -
     3   0008  MOVI R2, 0              0     1     0     -    -
     4   000C  MOVI R3, 5              0     1     0     5    -
     5   0010  CMP R2, R3              0     1     0     5    Z=0 S=1
     6   0013  JGE +10                 0     1     0     5    (not taken)
     7   0017  MOV R4, R0              0     1     0     5    (R4=0)
     8   001A  IADD R0, R0, R1         1     1     0     5    Z=0
     9   001E  MOV R1, R4              1     0     0     5    -
    10   0021  INC R2                  1     0     1     5    Z=0
    11   0023  JMP -20                 1     0     1     5    (jump back)
    12   0010  CMP R2, R3              1     0     1     5    Z=0 S=1
    ... (loop continues)
    26   0027  HALT                    5     3     5     5    (done)
```

After 5 iterations: `R0 = 5` (fibonacci(5)).

## Instruction Formats Reference

| Format | Size  | Encoding                              | Example |
|--------|-------|---------------------------------------|---------|
| A      | 1 byte| `[opcode]`                            | HALT    |
| B      | 2 bytes| `[opcode][reg:u8]`                    | INC R2  |
| C      | 3 bytes| `[opcode][rd:u8][rs1:u8]`            | CMP R2, R3 |
| D      | 4 bytes| `[opcode][reg:u8][imm16:i16]`        | MOVI R0, 0 |
| E      | 4 bytes| `[opcode][rd:u8][rs1:u8][rs2:u8]`   | IADD R0, R0, R1 |
| G      | var   | `[opcode][len:u16][data:len bytes]`  | TELL    |

## Try It

```bash
cd /home/z/my-project/flux-py
PYTHONPATH=src python3 -c "
from flux.pipeline.e2e import FluxPipeline
from flux.pipeline.debug import disassemble_bytecode
import pathlib

md = pathlib.Path('examples/03_fibonacci.md').read_text()
pipeline = FluxPipeline()
result = pipeline.run(md, lang='md')

print(f'Success: {result.success}')
print(f'Cycles: {result.cycles}')
print(f'Halted: {result.halted}')
print()
if result.registers:
    print('Register state:')
    for i, v in result.registers.items():
        if v != 0:
            print(f'  R{i} = {v}')
print()
print('Disassembly:')
print(disassemble_bytecode(result.bytecode))
"
```
