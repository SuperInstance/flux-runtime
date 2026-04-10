---
title: Polyglot Signal Processor
version: 1.0
description: Mixing C and Python in a single FLUX.MD document with A2A agent concepts
---

# Polyglot Addition — C for Speed, Python for Glue

This FLUX.MD demonstrates the **polyglot** nature of FLUX: mixing multiple
languages in a single markdown document. Each code block is extracted by the
parser, classified by its language tag, and compiled through the appropriate
frontend.

## The Concept

In real-world systems, different parts of a program have different needs:

- **Hot inner loops** → compiled C for maximum speed (8x faster than Python)
- **Orchestration logic** → Python for expressiveness and rapid iteration
- **Agent communication** → A2A protocol for inter-agent coordination

FLUX.MD lets you write all of these in one document.

## Fast Math (C)

The C frontend handles the performance-critical computation. Here, a simple
multiply function that would be a hot path in a real signal processor:

```c
int multiply(int a, int b) {
    return a * b;
}

int square(int x) {
    return x * x;
}

int main() {
    int x = 7;
    int y = 6;
    int result = multiply(x, y) + square(x);
    return result;
}
```

### C Frontend Details

The C compiler pipeline:

1. **Tokenizer** — regex-based lexer: identifiers, literals, keywords, operators
2. **Parser** — recursive descent producing a C AST
3. **Code generator** — walks the C AST, emits FIR via `FIRBuilder`

Supported C subset:
- Types: `int`, `float`, `void`
- Control flow: `if`/`else`, `while`, `for`, `return`
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Functions with parameters and return values

## Glue Logic (Python)

The Python frontend handles the orchestration. Python is more expressive
for data pipelines and control flow:

```python
def process_batch(data):
    result = 0
    for i in range(10):
        result = result + data
    return result

def main():
    result = process_batch(5)
    return result
```

### Python Frontend Details

The Python compiler uses Python's built-in `ast` module:

1. `ast.parse(source)` → Python AST
2. Walk AST nodes, emit FIR via `FIRBuilder`
3. Type inference heuristics (int literals → i32, float → f32)

Supported Python subset:
- `def` with parameters and return
- `if`/`elif`/`else`, `while`, `for`/`range()`
- `print()` as a built-in call
- Arithmetic, comparison, augmented assignment (`+=`)

## Integration — The A2A Concept

In a full FLUX system, agents communicate through the **A2A protocol**.
Imagine:

```
Agent A (C Math Engine)     Agent B (Python Orchestrator)
    |                              |
    |-- TELL: compute(x=7, y=6) ->|
    |                              |
    |<- ASK: here's the result ---|
    |                              |
    |-- DELEGATE: transform() --->|
    |                              |
    |<- REPORT_STATUS: done ------|
```

The A2A protocol opcodes (0x60–0x7B) enable this:

| Opcode  | Name              | Purpose |
|---------|-------------------|---------|
| 0x60    | TELL              | One-way message (fire and forget) |
| 0x61    | ASK               | Request-reply message |
| 0x62    | DELEGATE          | Delegate work to another agent |
| 0x66    | BROADCAST         | Send to all agents |
| 0x70    | TRUST_CHECK       | Verify trust score |
| 0x74    | CAP_REQUIRE       | Require a capability |

## Compiled Output

When this document is compiled, the **first code block** (C) is extracted and
compiled. In a full polyglot pipeline, all blocks would be compiled into a
unified FIR module with cross-language type unification.

The output bytecode contains:
- `IMUL` instructions for multiplication
- `IADD` instructions for addition
- `RET` instruction for function return

## Try It

```bash
cd /home/z/my-project/flux-py
PYTHONPATH=src python3 -c "
from flux.pipeline.e2e import FluxPipeline
from flux.pipeline.debug import disassemble_bytecode
import pathlib

md = pathlib.Path('examples/02_polyglot_add.md').read_text()
pipeline = FluxPipeline()
result = pipeline.run(md, lang='md')

print(f'Success: {result.success}')
print(f'Cycles: {result.cycles}')
print(f'Bytecode: {len(result.bytecode)} bytes')
print()
print('Disassembly:')
print(disassemble_bytecode(result.bytecode))
"
```
