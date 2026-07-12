# FLUX Tracing & Observability

> **See exactly what your agent policy is doing — instruction by instruction.**

FLUX is no longer a black box. The observability layer provides three
complementary tools for making bytecode execution visible, measurable,
and debuggable:

| Tool | Purpose | Granularity |
|------|---------|-------------|
| **Tracer** | Record every instruction with full state snapshots | Per-instruction |
| **Profiler** | Profile opcode frequency, timing, hotspots | Per-opcode / aggregate |
| **Debugger** | Interactive step-through with breakpoints and REPL | Per-instruction, interactive |

---

## Quick Start

```python
from flux.tracer import FluxTracer
from flux.profiler import FluxProfiler
from flux.debugger import FluxDebugger

# ── Trace ──
tracer = FluxTracer()
result = tracer.trace(bytecode)
print(tracer.report())

# ── Profile ──
profiler = FluxProfiler()
profile = profiler.profile(bytecode)
print(profiler.report())

# ── Debug (interactive) ──
debugger = FluxDebugger(bytecode)
debugger.repl()
```

---

## Tracer

### What It Does

The `FluxTracer` hooks into the VM's fetch-decode-execute loop and
records a complete trace of every instruction:

- Program counter before/after
- Opcode and disassembled operand string
- All 64 registers (R0–R15, F0–F15, V0–V15) before and after
- Condition flags (zero, sign, carry, overflow) before and after
- Timestamp (microseconds since trace start)

### API

```python
from flux.tracer import FluxTracer

tracer = FluxTracer(capture_memory=False, max_trace_entries=100_000)

# Run a trace
result = tracer.trace(bytecode, max_steps=10_000)

# Human-readable report
print(tracer.report())

# JSON export
json_str = tracer.to_json()

# Access raw entries
for entry in result.entries:
    print(f"Step {entry.step}: PC=0x{entry.pc:04X} {entry.opcode_name}")
    changes = [
        f"{k}: {v}" for k, v in entry.registers_after.items()
        if entry.registers_before.get(k) != v
    ]
    if changes:
        print(f"  Δ {', '.join(changes)}")
```

### Trace Report Example

```
FLUX Execution Trace
══════════════════════════════════════════════════════════════════════

Summary
────────────────────────────────────────
  Steps executed   : 46
  Cycles consumed  : 46
  Bytecode size    : 99 bytes
  Duration         : 0.523 ms
  Throughput       : 87,954 insn/s
  Halted cleanly   : True

Conservation Ledger
────────────────────────────────────────
Total budget consumed : 46 units
Instructions traced   : 46

By category:
  arithmetic            18 (39.1%)
  control_flow          15 (32.6%)
  stack                  8 (17.4%)
  comparison             5 (10.9%)

Final Register State
────────────────────────────────────────
  R0    = 13
  R1    = 100
  R2    = 15
  R3    = 5
  R4    = 5040
  R5    = 42
  R6    = 42
  R7    = 14

Instruction Trace
────────────────────────────────────────────────────────────────────────────
  Step       PC  Opcode           Operand               Δ Registers
────────────────────────────────────────────────────────────────────────────
     0  0x0000  MOVI             R0, 10                R0: 0→10
     1  0x0004  MOVI             R1, 5                 R1: 0→5
     2  0x0008  IADD             R0, R0, R1            R0: 10→15
     ...
```

---

## Profiler

### What It Does

The `FluxProfiler` runs bytecode and collects:

- **Opcode frequency** — how many times each opcode was executed
- **Per-opcode timing** — min, max, avg, total execution time
- **Category breakdown** — grouped by arithmetic, memory, control flow, etc.
- **Memory access patterns** — read/write counts, region access frequencies
- **Execution hotspots** — most-executed PC addresses
- **Conservation budget** — consumption by category with weights

### Conservation Budget Model

Each instruction category has a conservation cost weight:

| Category | Cost (units) | Examples |
|----------|-------------|----------|
| Arithmetic | 1 | `IADD`, `IMUL`, `INEG` |
| Comparison | 1 | `CMP`, `IEQ`, `ILT` |
| Control flow | 1 | `JMP`, `JNZ`, `CALL`, `RET` |
| Stack | 1 | `PUSH`, `POP`, `DUP`, `SWAP` |
| Memory | 2 | `LOAD`, `STORE`, `MEMCOPY` |
| Type ops | 2 | `CAST`, `BOX`, `UNBOX`, `CHECK_TYPE` |
| SIMD | 4 | `VADD`, `VMUL`, `VFMA` |
| A2A | 5 | `TELL`, `ASK`, `DELEGATE`, `BROADCAST` |
| System | 3 | `RESOURCE_ACQUIRE`, `EMERGENCY_STOP` |

### API

```python
from flux.profiler import FluxProfiler

profiler = FluxProfiler(warmup_steps=0)
profile = profiler.profile(bytecode, max_steps=10_000)

# Human-readable report
print(profiler.report())

# JSON export
json_str = profiler.to_json()

# Access structured data
for op_name, count, pct in profile.hottest_opcodes:
    print(f"{op_name}: {count} times ({pct:.1f}%)")

for hs in profile.hotspots:
    print(f"0x{hs['pc']:04X}: {hs['opcode']} ({hs['execution_count']} executions)")
```

---

## Debugger

### What It Does

The `FluxDebugger` extends the VM `Interpreter` with interactive
debugging.  It supports:

- **Single-step** through bytecode
- **Breakpoints** at any PC address
- **Continue** until breakpoint or HALT
- **Inspect and modify** registers, memory, and flags
- **Watchpoints** for automatic register monitoring
- **Disassembly** integration
- **Call stack backtrace**
- **Trace recording** — enable tracing during debugging
- **Interactive REPL** with commands

### Interactive REPL

```python
from flux.debugger import FluxDebugger

debugger = FluxDebugger(bytecode)
debugger.repl()
```

### REPL Commands

```
Execution:
  s, step              Execute one instruction
  c, continue          Run until breakpoint or HALT
  n, next              Step over (skips CALL bodies)
  q, quit              Exit the debugger
  reset                Reset VM to initial state

Breakpoints:
  b <addr>             Set breakpoint at byte offset
  bd <addr>            Disable breakpoint
  be <addr>            Enable breakpoint
  br <addr>            Remove breakpoint
  bl                   List all breakpoints
  bc                   Clear all breakpoints

Inspection:
  i, info              Show VM state summary
  regs                 Dump all registers
  reg <n>              Show register Rn
  set_reg <n> <val>    Set register Rn
  flags                Show condition flags
  mem <addr> [len]     Read memory
  set_mem <addr> <hex> Write memory
  stack [n]            Show top n stack words
  bt                   Show call stack
  dis [n]              Disassemble n instructions at PC

Tracing:
  trace on             Enable execution tracing
  trace off            Disable tracing
  trace export [file]  Export trace as JSON
  trace report         Print trace summary
```

---

## JSON Trace Schema

The tracer and debugger both export JSON. The canonical schema:

```json
{
  "$schema": "flux-trace/v1",
  "summary": {
    "total_steps": 46,
    "total_cycles": 46,
    "halted": true,
    "error": null,
    "bytecode_size": 99,
    "duration_ms": 0.523,
    "instructions_per_second": 87954.0
  },
  "final_state": {
    "registers": {
      "R0": 13,
      "R1": 100,
      "R2": 15,
      "..."
    },
    "flags": {
      "zero": true,
      "sign": false,
      "carry": false,
      "overflow": false
    },
    "memory_regions": [
      {
        "name": "stack",
        "size": 65536,
        "owner": "system",
        "data_preview": "..."
      }
    ]
  },
  "entries": [
    {
      "step": 0,
      "pc": "0x0000",
      "opcode": "0x2B",
      "opcode_name": "MOVI",
      "operand": "R0, 10",
      "registers_before": {"R0": 0, "R1": 0, "..."},
      "registers_after": {"R0": 10, "R1": 0, "..."},
      "flags_before": {"zero": false, "sign": false, "..."},
      "flags_after": {"zero": false, "sign": false, "..."},
      "timestamp_us": 12.345
    }
  ],
  "conservation_ledger": {
    "total_consumed": 46,
    "entry_count": 46,
    "entries": [
      {
        "step": 0,
        "pc": 0,
        "opcode": "MOVI",
        "category": "arithmetic",
        "cost": 1,
        "cumulative": 1
      }
    ]
  }
}
```

### Schema Versioning

The trace format uses semantic versioning via the `$schema` field:

- `flux-trace/v1` — Initial format (current)
- Breaking changes increment the version number
- New optional fields can be added without version bump

---

## Visualizing Traces

### Text Output

The `report()` methods produce formatted text output suitable for
terminal display or logging:

```python
print(tracer.report())
print(profiler.report())
```

### JSON → Custom Visualisation

Export JSON and feed it into external tools:

```python
import json

trace_data = json.loads(tracer.to_json())

# Build a flame graph of opcode frequencies
opcode_counts = {}
for entry in trace_data["entries"]:
    op = entry["opcode_name"]
    opcode_counts[op] = opcode_counts.get(op, 0) + 1

# Or track register value over time
r0_timeline = [
    entry["registers_after"]["R0"]
    for entry in trace_data["entries"]
]
```

### Integration with the Playground (Future)

Future plans for the FLUX playground include:

1. **Trace viewer** — A web-based timeline showing each instruction,
   with register diffs highlighted

2. **Flame graph** — Visual opcode frequency chart from profiler data

3. **Conservation dashboard** — Budget consumption over time with
   category breakdown

4. **Interactive debug session** — Connect the REPL debugger to a
   web UI for click-to-set breakpoints and visual state inspection

5. **Diff tracing** — Run two versions of a program and diff the
   traces to find behavioural changes

---

## Performance Notes

- **Tracer overhead:** ~3-5x slowdown due to state snapshotting per
  instruction. Use `capture_memory=False` (default) for best performance.

- **Profiler overhead:** ~2x slowdown from per-opcode timing. Use
  `warmup_steps` to skip initial cache/JIT warmup noise.

- **Debugger overhead:** Negligible when not stepping — the debugger
  only adds work during `step()` calls.

- **Memory:** Each trace entry stores ~48 register values + flags + metadata.
  At ~500 bytes per entry, 10,000 steps ≈ 5 MB. Use `max_trace_entries`
  to cap memory.

---

## API Reference

### FluxTracer

| Method | Description |
|--------|-------------|
| `trace(bytecode, max_steps=10000)` | Run bytecode with full tracing |
| `report(result=None)` | Human-readable trace report |
| `to_json(result=None, indent=2)` | JSON export |
| `attach(interpreter)` | Attach to an existing VM interpreter |
| `detach()` | Remove tracing hook |

### FluxProfiler

| Method | Description |
|--------|-------------|
| `profile(bytecode, max_steps=10000)` | Run bytecode with profiling |
| `report(result=None)` | Human-readable profile report |
| `to_json(result=None, indent=2)` | JSON export |

### FluxDebugger

| Method | Description |
|--------|-------------|
| `step()` | Execute one instruction |
| `continue_exec()` | Run until breakpoint or HALT |
| `run_to_offset(offset)` | Run until specific address |
| `repl()` | Interactive REPL |
| `add_breakpoint(offset)` | Set breakpoint |
| `remove_breakpoint(offset)` | Remove breakpoint |
| `inspect_reg(n)` / `set_reg(n, v)` | Register access |
| `inspect_mem(addr, len)` / `write_mem(addr, data)` | Memory access |
| `backtrace()` | Call stack |
| `disassemble_at(offset, count)` | Disassembly |
| `enable_trace()` / `disable_trace()` | Toggle tracing |
| `export_trace(filepath=None)` | Export trace JSON |
| `on_step(callback)` | Register step callback |

---

## Testing

Run the tracer/profiler/debugger tests:

```bash
pytest tests/test_tracer.py -v
```

The test suite uses the `cross_impl.flx` program — the canonical
cross-implementation integration test — and verifies that the tracer
produces the expected register state (R0=13, R1=100, R2=15, R3=5,
R4=5040, R5=42, R6=42, R7=14).
