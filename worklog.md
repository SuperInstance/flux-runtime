# FLUX Development Worklog

---

## 2025-07-09 — A2A Protocol Layer & Trust Engine

### Overview

Implemented the complete A2A (Agent-to-Agent) protocol layer and INCREMENTS+2
trust engine for the FLUX multi-agent VM runtime.  This provides the
foundational communication and trust infrastructure for agents to interact
safely within a single VM process.

### Files Created / Rewritten

| File | Purpose |
|------|---------|
| `src/flux/a2a/__init__.py` | Package exports (A2AMessage, LocalTransport, TrustEngine, AgentCoordinator, etc.) |
| `src/flux/a2a/messages.py` | A2AMessage dataclass with 52-byte binary header + variable payload |
| `src/flux/a2a/transport.py` | LocalTransport — in-process mailbox delivery per agent UUID |
| `src/flux/a2a/trust.py` | TrustEngine — INCREMENTS+2 six-dimensional trust computation |
| `src/flux/a2a/coordinator.py` | AgentCoordinator — trust-gated multi-agent orchestration |
| `tests/test_a2a.py` | 10 test functions (60+ assertions), all passing |

### A2A Message Protocol (`messages.py`)

**52-byte binary header layout:**

```
Offset  Size   Field
─────── ────── ──────────────────────────────────────
  0       16   sender_uuid        (128-bit UUID)
 16       16   receiver_uuid      (128-bit UUID)
 32        8   conversation_id    (compact 64-bit from UUID)
 40        1   message_type       (uint8, 0x60–0x7B)
 41        1   priority           (uint8, 0–15)
 42        4   trust_token        (uint32 LE)
 46        4   capability_token   (uint32 LE)
 50        2   in_reply_to        (uint16 LE, 0 = None)
 52      var   payload            (arbitrary bytes)
```

- `conversation_id` is stored as a full `uuid.UUID` in Python but serialized
  compactly to 8 bytes (first half of UUID bytes).
- `in_reply_to` is serialized as a uint16 tag (0 → None).
- Validation enforces `message_type` ∈ [0x60, 0x7B], `priority` ∈ [0, 15],
  and `trust_token` / `capability_token` fitting in uint32.
- Uses `struct.Struct("<16s16s8sBBIIH")` for efficient packing/unpacking.

### Local Transport (`transport.py`)

- `register(agent_id)` / `unregister(agent_id)` — mailbox lifecycle
- `send(message)` → bool — delivers to receiver's deque; returns False if
  receiver not registered
- `receive(agent_id)` → list — drains and returns all pending messages
- `pending_count(agent_id)` → int — non-destructive count
- Zero-copy in-process delivery, no persistence or networking

### INCREMENTS+2 Trust Engine (`trust.py`)

Six trust dimensions with configurable weights (default sum = 1.0):

| Dimension | Weight | Method |
|-----------|--------|--------|
| History   | 0.30   | EMA (α=0.1) of binary success/failure outcomes |
| Capability| 0.25   | Average `capability_match` of last 50 interactions |
| Latency   | 0.20   | Inverse linear: 10ms→1.0, 1000ms→0.0 |
| Consistency| 0.15   | 1 − CV of latency (coefficient of variation) |
| Determinism| 0.05   | 1 − CV of behavior_signature |
| Audit     | 0.05   | 1.0 if records exist, 0.0 if empty |

Time decay formula:
```
composite *= max(0.0, 1 − λ · elapsed / max_age)
```
with default λ=0.01/sec, max_age=3600s.

Profiles stored as `dict[(agent_a, agent_b)] → AgentProfile`, each holding
a bounded `deque[InteractionRecord]` (maxlen=1000).

### Agent Coordinator (`coordinator.py`)

- `register_agent(name, interpreter=None)` → UUID — assigns a random UUID
  and creates a mailbox
- `send_message(sender, receiver, msg_type, payload, priority)` → bool —
  **trust-gated**: checks `compute_trust(sender, receiver) >= threshold`
  before delivery; records positive interaction on success
- `get_messages(agent_id)` → list — drains the agent's mailbox
- Default trust threshold: 0.3

### Tests (`tests/test_a2a.py`)

10 test functions, all passing:

1. **test_message_roundtrip** — serialize/deserialize with various payloads,
   in_reply_to, empty payload, and short-buffer error
2. **test_agent_id_bytes** — UUID 16-byte roundtrip, nil UUID, uniqueness
3. **test_transport_send_recv** — register, send, receive, unregistered targets,
   unregister
4. **test_transport_routing** — 5-agent ring topology, correct sender routing,
   multi-message queuing
5. **test_trust_initial** — neutral trust 0.5, check_trust thresholds
6. **test_trust_success_increases** — 20 then 120 successful interactions
   build trust above 0.8
7. **test_trust_failure_decreases** — failures after successes drive trust
   below 0.5
8. **test_trust_decay** — manually aged interactions (2000s old) show
   reduced trust
9. **test_trust_revoke** — clears history, trust returns to 0.5, profile
   still exists
10. **test_coordinator_trust_gate** — trust-gated send: normal delivery,
    block on low trust, recover with successes, reject unknown agents

### Dependencies

No new external dependencies.  Uses only Python stdlib:
`struct`, `uuid`, `collections.deque`, `dataclasses`, `math`, `time`.

---

## 2025-07-10 — C & Python Frontend Compilers + Compilation Pipeline

### Overview

Implemented two source-language frontend compilers (C and Python) that
lower to the existing FIR (FLUX Intermediate Representation), plus a unified
`FluxCompiler` pipeline that drives both frontends and the bytecode encoder
to produce FLUX binary bytecode from any supported source language.  Also
added FLUX.MD compilation support that extracts native code blocks from
Markdown and compiles them.

### Files Created

| File | Purpose |
|------|---------|
| `src/flux/frontend/__init__.py` | Empty package init |
| `src/flux/frontend/c_frontend.py` | C-to-FIR compiler (tokenizer + recursive descent parser + FIR codegen) |
| `src/flux/frontend/python_frontend.py` | Python-to-FIR compiler using `ast` module |
| `src/flux/compiler/__init__.py` | Empty package init |
| `src/flux/compiler/pipeline.py` | `FluxCompiler` — unified `compile_c()`, `compile_python()`, `compile_md()` |
| `tests/test_frontends.py` | 8 tests covering both frontends + pipeline |

### Files Modified

| File | Change |
|------|--------|
| `src/flux/bytecode/opcodes.py` | Added `opcode_size` alias for `instruction_size` (pre-existing VM import bug) |

### C Frontend (`c_frontend.py`)

**Architecture:** Three-phase compilation:
1. **Tokenizer** — regex-based lexer producing `Token` objects. Handles C keywords
   (`int`, `float`, `void`, `if`, `else`, `while`, `for`, `return`), identifiers,
   integer/float literals, operators, punctuation, and comments.
2. **Parser** — recursive descent producing a C AST of dataclasses:
   `CFunction`, `CIf`, `CWhile`, `CFor`, `CReturn`, `CVarDecl`, `CAssign`,
   `CExprStmt`, `CBinOp`, `CUnaryOp`, `CCall`, `CIntLiteral`, `CFloatLiteral`,
   `CVarRef`.  Operator precedence: comparison → additive → multiplicative → unary → primary.
3. **Code generator** (`CFrontendCompiler`) — walks the C AST and emits FIR
   instructions via `FIRBuilder`.

**FIR codegen strategy:**
- Variables use **alloca/load/store** pattern (SSA-safe across branches/loops).
- Function parameters are alloca'd at entry for uniform variable access.
- Constants are represented as virtual `Value` objects (no constant instruction
  in FIR; the bytecode encoder maps Value IDs to register numbers).
- Control flow uses FIR's **Branch/Jump** with named block labels; block params
  serve as merge points (no phi nodes needed).
- `if/else` → `branch` to then/else blocks, both jump to merge block.
- `while` → header block with condition + `branch`, body jumps back to header,
  exit block continues.
- `for(init; cond; update) body` → init in current block, then same structure
  as while, with update emitted at end of body block.

**Supported C subset:** `int`/`float`/`void` functions, `int`/`float` variables
with optional initialization, `if`/`else`, `while`, `for`, `return`, arithmetic
(`+`, `-`, `*`, `/`, `%`), comparison (`==`, `!=`, `<`, `>`, `<=`, `>=`),
function calls, integer/float literals, unary minus.

### Python Frontend (`python_frontend.py`)

**Architecture:** Single-phase compilation using Python's built-in `ast` module:
1. `ast.parse(source)` → Python AST
2. Walk AST nodes and emit FIR via `FIRBuilder`

**Supported Python constructs:** `def`, assignments, augmented assignments
(`+=`, `-=`, etc.), arithmetic, comparison, `if`/`elif`/`else`, `while`,
`for`/`range()` (detects the pattern and lowers to a while-like alloca
counter loop), `return`, `print()` (emitted as call instruction), function
calls, `int`/`float`/`str`/`bool` literals, unary negation, ternary
expressions (`x if cond else y`).

**Type inference:** Simple heuristic-based inference from expression structure.
Integer literals → `i32`, float literals → `f32`, arithmetic on floats → `f32`,
comparisons → `i32`, etc.  Type annotations on function defs/params are
honored when present.

**`for/range` lowering:** Detects `for target in range(...)` and emits:
```
alloca counter; store start; jump header;
header: load counter; ilt counter, limit; branch body, exit;
body: ... user code ...; load counter; iadd counter, step; store; jump header;
exit: ...
```

### Pipeline (`pipeline.py`)

`FluxCompiler` class with three public methods:

| Method | Source | Pipeline |
|--------|--------|----------|
| `compile_c(source)` | C code string | CParser → CFrontendCompiler → BytecodeEncoder → `bytes` |
| `compile_python(source)` | Python code string | `ast.parse` → PythonFrontendCompiler → BytecodeEncoder → `bytes` |
| `compile_md(source)` | FLUX.MD string | FluxMDParser → extract `NativeBlock` → compile via C or Python frontend |

Output is always FLUX binary bytecode (`bytes`) with the standard 16-byte header
(`b'FLUX'` magic, version 1, function table, type table, code section).

### Tests (`tests/test_frontends.py`)

8 tests, all passing:

1. **test_c_add** — Compiles `int add(int a, int b) { return a + b; }`;
   verifies `iadd` and `return` in FIR opcodes.
2. **test_c_if_else** — Compiles `max()` with if/else; verifies `branch` in
   opcodes and ≥ 3 basic blocks.
3. **test_c_while** — Compiles `countdown()` with while loop; verifies
   `branch`, `jump`, `iadd`, `isub` and ≥ 3 blocks.
4. **test_c_multi_func** — Compiles `square()` and `cube()` in one source;
   verifies 2+ functions and `imul` opcodes.
5. **test_py_add** — Compiles `def add(a, b): return a + b`; verifies `iadd`.
6. **test_py_if** — Compiles `abs_val()` with if/else; verifies `branch`
   and `ineg`, ≥ 3 blocks.
7. **test_py_for_range** — Compiles `sum_n()` with `for/range`; verifies
   `branch`, `jump`, `iadd`, ≥ 3 blocks.
8. **test_pipeline_c_to_bytecode** — Full pipeline C→bytecode; verifies
   output is `bytes`, ≥ 16 bytes, starts with `b'FLUX'` magic.

### Dependencies

No new external dependencies.  Uses only Python stdlib:
`re`, `dataclasses`, `ast`, `typing`.

---

## 2026-04-13 — ISA v3 Fleet Layer: Provisional Implementation & Convergence Audit

**Agent:** Claude (runtime-engineer shell, `claude-sonnet-4-6`)
**Branch:** `claude/explore-flux-runtime-gcgKD`
**Session commits:** `2629497`, `8a7a166` (+ this session)

### What I Built

Added 12 ISA v3 fleet-layer opcodes to the Python VM:

| Group | Ops | Count |
|-------|-----|-------|
| Confidence-fused arithmetic | CAAD, CSUB, CMUL, CDIV | 4 |
| Energy management | ATP_SPEND, ATP_QUERY | 2 |
| A2A messaging | MSG_SEND, MSG_RECV, MSG_POLL | 3 |
| Power states | SLEEP, WAKE, WDOG_RESET | 3 |

Runtime state added to `interpreter.py`: `_reg_confidence`, `_atp_budget`,
`_sleep_remaining`, `_wdog_timeout/_wdog_remaining`, `_msg_inbox`.
18 tests covering all behaviors: `tests/test_isa_v3_opcodes.py` — all pass.

### Honest Self-Audit

After mapping fleet state (branches, commits, issues, isa_unified.py), I
discovered my commit `2629497` has critical byte-value collisions:

- My `CAAD=0xA0` collides with isa_unified.py's `LEN=0xA0` (collection op)
- My `SLEEP=0x85` collides with isa_unified.py's `GPS=0x85` (sensor op)
- All 12 of my bytes are in ranges allocated to other agents in isa_unified.py

**The root cause:** I built on top of opcodes.py (System A) without realising
isa_unified.py (System B) had already been agreed as the source of truth in
Issue #13.  The converging commit `555dce4` happened while I was working.

**Disposition:** commit `2629497` is marked PROVISIONAL in the roadmap doc.
The semantics are correct and the runtime state additions are sound — but the
byte assignments must move to the canonical isa_unified.py slots on rebase.

### What I Found That Matters for the Fleet

1. **The ISA divergence is total, not partial.** signal_compiler.py emits
   bytes per isa_unified.py but the interpreter still decodes per opcodes.py.
   Even `ADD` (0x20 in isa_unified = PUSH in opcodes.py) is wrong. Every
   single signal-compiled program silently executes the wrong opcodes.

2. **The signal→VM integration test was genuinely missing.** This is the
   single highest-leverage gap. I wrote it: `tests/test_signal_vm_integration.py`
   (12 tests, 5 pass + 7 xfail documenting exact divergences). The xfails
   become the test-driven acceptance criteria for Issue #13 Phase 1.

3. **Confidence ops already have canonical homes.** C_ADD/C_SUB/C_MUL/C_DIV
   at 0x60–0x63 in isa_unified.py. My CAAD etc. are duplicates — retire them,
   implement the canonical versions, reuse my confidence propagation logic.

4. **Super Z already shipped** a 221-vector conformance generator (92.6% ISA
   coverage), CAPABILITY.toml parser, and the ISA v3 escape-prefix spec.
   I coordinated against this rather than duplicating it.

### Deliverables This Session

| File | Purpose |
|------|---------|
| `tests/test_signal_vm_integration.py` | Missing signal→VM integration test (12 tests) |
| `docs/roadmap/ISA_V3_AND_FLEET_CONVERGENCE.md` | Strategic roadmap + my commit disposition |
| `CAPABILITY.toml` | Fleet agent declaration per capability_parser.py schema |

### No Regressions

Baseline: 2503 tests passing before this session. No new failures introduced.
The `test_signal_vm_integration.py` xfails are pre-existing bugs, not new ones.
