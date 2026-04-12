# FLUX Opcode Reconciliation Analysis

**Author:** Quill (Architect-rank, SuperInstance fleet)
**Date:** 2026-04-12
**Status:** CRITICAL — Requires immediate engineering action
**Classification:** ISA Divergence / Cross-component Incompatibility

---

## 1. Executive Summary

The FLUX ecosystem contains **two incompatible opcode numbering schemes** that have diverged to the point where bytecode compiled by the Signal compiler **will not execute correctly** on the Python VM interpreter for any A2A (Agent-to-Agent) operation. This is not a minor drift — it is a **fundamental ISA split** affecting system control, arithmetic, stack, SIMD, A2A protocol, and confidence opcodes.

### The Two Systems

| System | File | Origin | Status |
|--------|------|--------|--------|
| **System A** (Interpreter) | `src/flux/bytecode/opcodes.py` | Oracle1's original VM development | **Live** — used by interpreter, encoder, disassembler, debugger, 11 game implementations, REPL, CLI |
| **System B** (Unified ISA) | `src/flux/bytecode/isa_unified.py` | Converged spec from Oracle1 + JetsonClaw1 + Babel | **Spec-only** — not imported by any runtime code, but hard-coded into signal_compiler.py and conformance tests |

### The Fatal Path

```
Signal JSON  →  signal_compiler.py (uses System B numbers)
     ↓
  bytecode with TELL=0x50
     ↓
  interpreter.py (uses System A numbers)
     ↓
  0x50 decoded as VLOAD (SIMD vector load)  ← WRONG OPCODE
```

**Every A2A message opcode is misinterpreted.** A `TELL` (send message to agent) becomes a `VLOAD` (SIMD vector load). An `ASK` (request from agent) becomes a `VSTORE` (SIMD vector store). A `BCAST` (fleet broadcast) becomes a `VSUB` (vector subtract). The VM will either crash or produce garbage results.

---

## 2. Side-by-Side Comparison of Conflicting Opcodes

### 2.1 Critical System Control Conflicts

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Offset | Impact |
|----------|:----------------------:|:--------------------------:|:------:|--------|
| **HALT** | `0x80` | `0x00` | +0x80 | Compiler emits 0x00, interpreter never halts (decodes as NOP) |
| **NOP** | `0x00` | `0x01` | -0x01 | Interpreter treats 0x01 as MOV; compiler's HALT (0x00) is interpreter's NOP |
| **RET** | `0x28` | `0x02` | +0x38 | Function return completely broken |
| **YIELD** | `0x81` | `0x15` | +0x6C | Concurrency primitive broken |

### 2.2 Register / Stack Operation Conflicts

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Offset | Impact |
|----------|:----------------------:|:--------------------------:|:------:|--------|
| **MOV** | `0x01` | `0x3A` | -0x39 | Data movement broken |
| **LOAD** | `0x02` | `0x38` | -0x36 | Memory load broken |
| **STORE** | `0x03` | `0x39` | -0x36 | Memory store broken |
| **PUSH** | `0x20` | `0x0C` | +0x14 | Stack push broken |
| **POP** | `0x21` | `0x0D` | +0x14 | Stack pop broken |
| **INC** | `0x0E` | `0x08` | +0x06 | Increment broken |
| **DEC** | `0x0F` | `0x09` | +0x06 | Decrement broken |

### 2.3 Arithmetic / Logic Conflicts

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Offset | Impact |
|----------|:----------------------:|:--------------------------:|:------:|--------|
| **ADD** | `0x08` | `0x20` | -0x18 | Integer add broken |
| **SUB** | `0x09` | `0x21` | -0x18 | Integer subtract broken |
| **MUL** | `0x0A` | `0x22` | -0x18 | Integer multiply broken |
| **DIV** | `0x0B` | `0x23` | -0x18 | Integer divide broken |
| **AND** | `0x10` | `0x25` | -0x15 | Bitwise AND broken |
| **OR** | `0x11` | `0x26` | -0x15 | Bitwise OR broken |
| **MOVI** | `0x2B` | `0x18` | +0x13 | Immediate load broken |

### 2.4 A2A Protocol Conflicts (The Fatal Zone)

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Interpreter decodes 0x50-0x5F as |
|----------|:----------------------:|:--------------------------:|:------------------------------|
| **TELL** | `0x60` | `0x50` | `VLOAD` (SIMD vector load) |
| **ASK** | `0x61` | `0x51` | `VSTORE` (SIMD vector store) |
| **DELEGATE** | `0x62` | `0x52` | `VADD` (vector add) |
| **BCAST** | `0x66` | `0x53` | `VSUB` (vector subtract) |
| **ACCEPT** | *(none)* | `0x54` | `VMUL` (vector multiply) |
| **DECLINE** | *(none)* | `0x55` | `VDIV` (vector divide) |
| **REPORT** | `0x64` | `0x56` | `VFMA` (fused multiply-add) |
| **MERGE** | `0x67` | `0x57` | `STORE8` (8-bit store) |
| **FORK** | *(none)* | `0x58` | *(unassigned)* |
| **JOIN** | *(none)* | `0x59` | *(unassigned)* |
| **SIGNAL** | *(none)* | `0x5A` | *(unassigned)* |
| **AWAIT** | *(none)* | `0x5B` | *(unassigned)* |
| **TRUST** | *(none)* | `0x5C` | *(unassigned)* |

### 2.5 Confidence Operation Conflicts

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Interpreter decodes 0x60-0x6F as |
|----------|:----------------------:|:--------------------------:|:------------------------------|
| **C_ADD** | *(none)* | `0x60` | `TELL` (A2A send) |
| **C_SUB** | *(none)* | `0x61` | `ASK` (A2A request) |
| **C_MUL** | *(none)* | `0x62` | `DELEGATE` (A2A delegate) |
| **C_DIV** | *(none)* | `0x63` | `DELEGATE_RESULT` |
| **C_FADD** | *(none)* | `0x64` | `REPORT_STATUS` |
| **C_FSUB** | *(none)* | `0x65` | `REQUEST_OVERRIDE` |
| **C_FMUL** | *(none)* | `0x66` | `BROADCAST` |
| **C_FDIV** | *(none)* | `0x67` | `REDUCE` |
| **C_THRESH** | *(none)* | `0x69` | `ASSERT_GOAL` |

### 2.6 SIMD / Vector Conflicts

| Mnemonic | System A (`opcodes.py`) | System B (`isa_unified.py`) | Offset |
|----------:|:----------------------:|:--------------------------:|:------:|
| **VLOAD** | `0x50` | `0xB0` | -0x60 |
| **VSTORE** | `0x51` | `0xB1` | -0x60 |
| **VADD** | `0x52` | `0xB2` | -0x60 |
| **VMUL** | `0x54` | `0xB3` | -0x5F |
| **VFMA** | `0x56` | *(none — uses VDOT)* | — |

---

## 3. Impact Analysis

### 3.1 Components Using System A (`opcodes.py`) — The Interpreter's World

These files import `from flux.bytecode.opcodes import Op`:

| Component | File(s) | Lines of Code | Risk Level |
|-----------|---------|:---:|:----------:|
| **VM Interpreter** | `src/flux/vm/interpreter.py` | ~1200 | CRITICAL |
| **Bytecode Encoder** | `src/flux/bytecode/encoder.py` | ~445 | CRITICAL |
| **Bytecode Decoder** | `src/flux/bytecode/decoder.py` | ~400 | CRITICAL |
| **Bytecode Init** | `src/flux/bytecode/__init__.py` | ~37 | HIGH |
| **Disassembler** | `src/flux/disasm.py` | ~300 | HIGH |
| **Debugger** | `src/flux/debugger.py` | ~500 | HIGH |
| **Open Interpreter** | `src/flux/open_interpreter.py` | ~200 | HIGH |
| **REPL** | `src/flux/repl.py` | ~250 | MEDIUM |
| **CLI** | `src/flux/cli.py` | ~600 | MEDIUM |
| **Pipeline Debug** | `src/flux/pipeline/debug.py` | ~100 | MEDIUM |
| **Game: Pong** | `src/flux/retro/implementations/pong.py` | ~200 | LOW |
| **Game: Snake** | `src/flux/retro/implementations/snake.py` | ~200 | LOW |
| **Game: Tetris** | `src/flux/retro/implementations/tetris.py` | ~200 | LOW |
| **Game: Tic-tac-toe** | `src/flux/retro/implementations/tic_tac_toe.py` | ~150 | LOW |
| **Game: Mandelbrot** | `src/flux/retro/implementations/mandelbrot.py` | ~200 | LOW |
| **Game: Mastermind** | `src/flux/retro/implementations/mastermind.py` | ~150 | LOW |
| **Game: Lunar Lander** | `src/flux/retro/implementations/lunar_lander.py` | ~150 | LOW |
| **Game: Game of Life** | `src/flux/retro/implementations/game_of_life.py` | ~200 | LOW |
| **Game: Markov Text** | `src/flux/retro/implementations/markov_text.py` | ~200 | LOW |
| **Game: Text Adventure** | `src/flux/retro/implementations/text_adventure.py` | ~200 | LOW |
| **ASM Builder** | `src/flux/retro/implementations/_asm.py` | ~100 | LOW |
| **IR Builder** | `src/flux/retro/implementations/_builder.py` | ~50 | LOW |

**Total: ~5,000+ lines of code depend on System A numbering.**

### 3.2 Components Using System B (`isa_unified.py`) — The Spec's World

| Component | File(s) | How Used |
|-----------|---------|----------|
| **Signal Compiler** | `src/flux/a2a/signal_compiler.py` | Hard-coded hex values matching `isa_unified.py` (0x50=TELL, 0x51=ASK, etc.) |
| **Conformance Tests** | `tests/test_conformance.py` | Hard-coded hex values: HALT=0x00, NOP=0x01, MOVI=0x18, ADD=0x20 |
| **Signal Compiler Tests** | `tests/test_signal_compiler.py` | Asserts `0x50 in result.bytecode` for TELL, `0x53` for BCAST, `0x00` for HALT |
| **ISA Unified Tests** | `tests/test_isa_unified.py` | Tests the `build_unified_isa()` function directly |
| **Documentation** | `docs/ISA_UNIFIED.md` | Canonical opcode table published as the reference spec |

**Import finding:** `isa_unified.py` is **not imported by any runtime source file**. The grep of `src/` for `isa_unified` returned zero matches. Its influence is purely through hard-coded hex values in `signal_compiler.py` and `tests/test_conformance.py`.

### 3.3 The Greenhorn Go/Rust/CUDA VM Implications

The `message-in-a-bottle/TASKS.md` references a **greenhorn-runtime** task for CUDA kernel batch FLUX execution. There is no Go VM in the current repository. However, any future VM implementation targeting the converged ISA spec (`docs/ISA_UNIFIED.md`) will naturally use System B numbering — creating a permanent incompatibility with the Python interpreter unless this is resolved.

---

## 4. Root Cause Analysis

### 4.1 How Did This Happen?

The divergence is the result of **two independent ISA development efforts** that were never synchronized:

**Timeline (reconstructed):**

1. **Phase 1 — Oracle1's VM**: Oracle1 built the original Python VM interpreter (`src/flux/vm/interpreter.py`) and defined opcodes in `opcodes.py`. The numbering followed a pragmatic, organic layout:
   - `0x00` = NOP (natural starting point)
   - `0x08-0x0F` = integer arithmetic
   - `0x50-0x56` = SIMD (allocated early for performance workloads)
   - `0x60-0x7F` = A2A protocol (added as the fleet grew)
   - `0x80` = HALT (placed at a "high" address as a terminator)

2. **Phase 2 — Three-Agent Convergence**: Oracle1, JetsonClaw1, and Babel performed a cross-agent ISA convergence exercise, producing `isa_unified.py`. This reorganized the entire 256-slot opcode space with different design principles:
   - `0x00` = HALT (following RISC-V convention of zero-as-stop)
   - `0x50-0x5F` = A2A (relocated from 0x60+)
   - `0x60-0x6F` = confidence ops (new category)
   - `0xB0-0xBF` = SIMD (moved from 0x50+)
   - Systematic format-based allocation (A=1B through G=5B)

3. **Phase 3 — Signal Compiler**: Babel designed the Signal JSON→bytecode compiler (`signal_compiler.py`) targeting the converged ISA spec. Hard-coded hex values from `isa_unified.py` were embedded directly.

4. **Phase 4 — Conformance Tests**: Super Z (Cartographer) wrote cross-VM conformance tests (`test_conformance.py`) using `isa_unified.py` numbering for test vectors.

5. **Phase 5 — Never the Twain Shall Meet**: Nobody updated `opcodes.py` to match `isa_unified.py`. The interpreter continued using the original numbering. The signal compiler and conformance tests use the new numbering. **The two systems are now live and incompatible.**

### 4.2 Why Wasn't This Caught?

- `isa_unified.py` was treated as documentation/spec, not as an actionable migration target.
- No automated test feeds signal-compiled bytecode into the interpreter and checks results.
- The `test_signal_compiler.py` only checks that specific hex bytes appear in compiled output — it never runs the bytecode.
- The `test_conformance.py` test vectors cannot pass on the current interpreter (e.g., HALT=0x00 would be decoded as NOP=0x00).
- The format encoding differences (System A: Format G variable-length for A2A; System B: Format E fixed 4-byte for A2A) were never reconciled.

### 4.3 Format Encoding Divergence

The two systems disagree not only on **which byte value** corresponds to which mnemonic, but also on **how many bytes the instruction occupies**:

| Opcode | System A Format | System B Format | Byte Count A | Byte Count B |
|--------|:---:|:---:|:---:|:---:|
| TELL | G (variable: opcode + u16 len + data) | E (fixed: opcode + rd + rs1 + rs2) | 5+ bytes | 4 bytes |
| ASK | G (variable) | E (fixed) | 5+ bytes | 4 bytes |
| BROADCAST | G (variable) | E (fixed) | 5+ bytes | 4 bytes |
| HALT | A (1 byte) | A (1 byte) | 1 byte | 1 byte |
| NOP | A (1 byte) | A (1 byte) | 1 byte | 1 byte |
| MOV | C (3 bytes: op + rd + rs1) | E (4 bytes: op + rd + rs1 + rs2) | 3 bytes | 4 bytes |
| MOVI | D (4 bytes: op + reg + i16) | D (3 bytes: op + rd + imm8) | 4 bytes | 3 bytes |

This means even after resolving the opcode byte values, the **operand encoding is fundamentally different**. A2A operations in System A carry variable-length string data (agent names, message payloads); in System B they use fixed register triples. This reflects a design philosophy difference that cannot be resolved by remapping alone.

---

## 5. Proposed Resolution Strategy

### 5.1 Strategic Recommendation

**Migrate System A (`opcodes.py`) to match System B (`isa_unified.py`) as the single source of truth.**

Rationale:
- System B represents the converged consensus of 3 agents and ~247 opcodes.
- System B has a more principled layout with format-based allocation.
- System B includes opcodes that System A lacks (confidence, viewpoint, sensor, tensor).
- System B is the published specification (`docs/ISA_UNIFIED.md`).
- The signal compiler and conformance tests already target System B.
- Any future VM (greenhorn CUDA, external implementations) will reference System B.

### 5.2 Migration Scope

The migration must address **three orthogonal changes**:

1. **Opcode byte values** — remap all hex values in `opcodes.py`
2. **Format encoding** — align the format classification (FORMAT_A/B/C/D/E/G sets)
3. **Interpreter dispatch** — rewrite the `_step()` method to use the new encoding
4. **Encoder alignment** — update `BytecodeEncoder` to emit correct formats
5. **All dependent code** — update every import of `Op` across the codebase

---

## 6. Migration Plan

### Phase 0: Preparation (Risk: LOW)

**Step 0.1** — Create a migration branch and tag the pre-migration state.

```bash
git checkout -b opcode-reconciliation
git tag pre-opcode-reconciliation HEAD
```

**Step 0.2** — Add a `bytecode_version` constant to track which ISA version bytecode targets. This enables future-proofing.

**Step 0.3** — Write a comprehensive test suite that exercises ALL opcodes in `opcodes.py` with their current byte values. This becomes the regression baseline.

### Phase 1: Unify Opcode Values (Risk: HIGH)

**Step 1.1** — Rewrite `src/flux/bytecode/opcodes.py` to use `isa_unified.py` numbering.

Specific changes:

```
OLD (opcodes.py)          NEW (isa_unified.py)
─────────────────         ─────────────────────
HALT  = 0x80         →    HALT  = 0x00
NOP   = 0x00         →    NOP   = 0x01
RET   = 0x28         →    RET   = 0x02
INC   = 0x0E         →    INC   = 0x08
DEC   = 0x0F         →    DEC   = 0x09
NOT   = 0x13         →    NOT   = 0x0A
NEG   = 0x1D         →    NEG   = 0x0B
PUSH  = 0x20         →    PUSH  = 0x0C
POP   = 0x21         →    POP   = 0x0D
MOVI  = 0x2B         →    MOVI  = 0x18
ADD   = 0x08         →    ADD   = 0x20
SUB   = 0x09         →    SUB   = 0x21
MUL   = 0x0A         →    MUL   = 0x22
DIV   = 0x0B         →    DIV   = 0x23
MOV   = 0x01         →    MOV   = 0x3A
LOAD  = 0x02         →    LOAD  = 0x38
STORE = 0x03         →    STORE = 0x39
JZ    = 0x05         →    JZ    = 0x3C
JNZ   = 0x06         →    JNZ   = 0x3D
JMP   = 0x04         →    JMP   = 0x43
CALL  = 0x07         →    CALL  = 0x45
LOOP  = (none)       →    LOOP  = 0x46
TELL  = 0x60         →    TELL  = 0x50
ASK   = 0x61         →    ASK   = 0x51
BCAST = 0x66         →    BCAST = 0x53
VLOAD = 0x50         →    VLOAD = 0xB0
VSTORE= 0x51         →    VSTORE= 0xB1
VADD  = 0x52         →    VADD  = 0xB2
VMUL  = 0x54         →    VMUL  = 0xB3
```

**Step 1.2** — Add all new opcodes from `isa_unified.py` that don't exist in `opcodes.py`:
- Confidence ops: `C_ADD` through `C_VOTE` (0x60-0x6F)
- Viewpoint ops: `V_EVID` through `V_PRAGMA` (0x70-0x7F) — Babel reserved
- Sensor ops: `SENSE` through `CANBUS` (0x80-0x8F) — JetsonClaw1
- Extended math: `ABS`, `SQRT`, `POPCNT`, etc. (0x90-0x9F)
- Collection ops: `LEN`, `CONCAT`, `AT`, etc. (0xA0-0xAF)
- Tensor ops: `TMATMUL`, `TCONV`, `TRELU`, etc. (0xC0-0xCF)
- Memory/IO ops: `DMA_CPY`, `MMIO_R`, `ATOMIC`, etc. (0xD0-0xDF)
- System/debug: `HALT_ERR`, `REBOOT`, `TRACE`, etc. (0xF0-0xFF)

### Phase 2: Update Format Classification (Risk: HIGH)

**Step 2.1** — Realign `FORMAT_A`, `FORMAT_B`, `FORMAT_C`, `FORMAT_D`, `FORMAT_E`, `FORMAT_G` frozensets in `opcodes.py` to match `isa_unified.py` format assignments.

Key differences to reconcile:

| Opcode Category | System A Format | System B Format |
|----------------|:---:|:---:|
| A2A ops (TELL, ASK, ...) | G (variable) | E (fixed 4-byte) |
| MOV | C (3 bytes) | E (4 bytes) |
| LOAD/STORE | C (3 bytes) | E (4 bytes) |
| ENTER/LEAVE | B (2 bytes) | G (5 bytes) |
| JZ/JNZ | D (4 bytes, register + i16) | E (4 bytes, rd + rs1 + rs2) |
| MOVI | D (4 bytes, reg + i16) | D (3 bytes, rd + imm8) |

**Decision required:** Which format encoding should A2A operations use? System A's variable-length Format G allows embedding agent names and message payloads directly in bytecode (string data). System B's fixed Format E uses register triples, requiring agents to be pre-loaded into registers. These are fundamentally different ABIs.

**Recommended approach:** Adopt System B's Format E for A2A (register-based), but add a Format G escape mechanism for future string-literal embedding. The signal compiler already uses register-based encoding.

### Phase 3: Update the Interpreter (Risk: CRITICAL)

**Step 3.1** — Rewrite `src/flux/vm/interpreter.py` `_step()` method.

The interpreter's dispatch currently matches on `Op.NOP`, `Op.HALT`, etc. (which resolve to the integer values from System A). After Phase 1, these will resolve to System B values, so the dispatch logic will automatically use the new numbering.

However, the **operand decoding** must change:

- A2A ops: change from `_fetch_var_data()` (Format G) to `_decode_operands_E()` (Format E)
- MOV: change from `_decode_operands_C()` (3 bytes) to `_decode_operands_E()` (4 bytes)
- LOAD/STORE: change from `_decode_operands_C()` to `_decode_operands_E()`
- JZ/JNZ: change from `_decode_operands_D()` (reg + i16 offset) to register-based branch

### Phase 4: Update the Encoder (Risk: HIGH)

**Step 4.1** — Update `src/flux/bytecode/encoder.py` to emit the new format encoding.

The `_BIN_ARITH` and `_BIN_CMP` mappings already reference `Op.IADD`, `Op.ISUB`, etc. After Phase 1, these will emit the correct new byte values. But the **encoding format** (how many bytes per instruction) must be updated.

**Step 4.2** — Update A2A encoding in the encoder from Format G to Format E.

### Phase 5: Update All Dependent Code (Risk: MEDIUM)

**Step 5.1** — Update all 11 game implementations in `src/flux/retro/implementations/`:
- `_asm.py` — the assembler uses `Op.*` values directly
- `_builder.py` — the IR builder references `Op.*`
- Each game file — may construct bytecode using `Op.*` constants

**Step 5.2** — Update `src/flux/disasm.py` — the disassembler maps byte values to mnemonics via `Op`.

**Step 5.3** — Update `src/flux/debugger.py` — uses `Op` and `get_format()`.

**Step 5.4** — Update `src/flux/repl.py` and `src/flux/cli.py` — reference `Op` for display.

**Step 5.5** — Update `src/flux/open_interpreter.py` — imports `Op`.

**Step 5.6** — Update `src/flux/pipeline/debug.py` — imports `Op` and `get_format`.

### Phase 6: Update Tests (Risk: MEDIUM)

**Step 6.1** — `tests/test_signal_compiler.py` — assertions already check for System B values (0x50 for TELL, etc.). These should pass after Phase 1.

**Step 6.2** — `tests/test_conformance.py` — test vectors use System B values. After the interpreter is updated (Phase 3), these should pass. Note: some test vectors have a THIRD numbering (e.g., INC=0x04, PUSH=0x08) that matches neither System A nor System B and will need correction.

**Step 6.3** — `tests/test_vm.py`, `tests/test_vm_complete.py`, `tests/test_bytecode.py` — these test the interpreter against System A bytecode. All bytecode constants in these tests need updating.

**Step 6.4** — `tests/test_a2a.py` — A2A-specific tests need updating.

### Phase 7: Eliminate Dead Code (Risk: LOW)

**Step 7.1** — After successful migration, `opcodes_legacy.py` can be removed or archived.

**Step 7.2** — `isa_unified.py` can remain as the authoritative spec reference, but `opcodes.py` should become the canonical `IntEnum` that matches it exactly.

---

## 7. Risk Assessment

| Phase | Risk Level | Primary Risk | Mitigation |
|-------|:----------:|-------------|------------|
| **Phase 0** | LOW | None — preparation only | N/A |
| **Phase 1** | HIGH | Silent miscompilation: changing opcode values breaks all existing bytecode | Tag pre-migration state; comprehensive test suite before starting |
| **Phase 2** | HIGH | Format mismatch: wrong operand decoding causes subtle data corruption | Write format-aware round-trip tests (encode→decode→execute) |
| **Phase 3** | CRITICAL | Interpreter crash or infinite loop from format changes | Test each opcode category independently; use cycle-budget limits |
| **Phase 4** | HIGH | Encoder produces wrong bytecode, undetectable without VM execution | Cross-validate: encoder output must round-trip through decoder |
| **Phase 5** | MEDIUM | Game implementations break, retro tests fail | Low priority; games can be fixed after core VM works |
| **Phase 6** | MEDIUM | Test assertions fail, masking real regressions | Update tests in lockstep with code changes; never have code+tests out of sync |
| **Phase 7** | LOW | Accidentally removing still-needed code | Grep for imports before deleting |

### 7.1 Highest-Risk Scenario

The interpreter's `_step()` method contains ~1000 lines of if-chain dispatch. Changing format decoding for MOV, LOAD, STORE, JZ, JNZ simultaneously with changing opcode values creates a combinatorial explosion of failure modes. **Mitigation: make Phase 1 (value changes) and Phase 2/3 (format changes) as separate, independently-testable commits.**

### 7.2 Regression Detection

The following commands should produce identical output before and after migration (once both are on the same ISA):

```bash
# 1. Run VM tests
python -m pytest tests/test_vm.py tests/test_vm_complete.py -v

# 2. Run bytecode tests
python -m pytest tests/test_bytecode.py -v

# 3. Run conformance tests (against updated interpreter)
python -m pytest tests/test_conformance.py -v

# 4. Run signal compiler tests
python -m pytest tests/test_signal_compiler.py -v

# 5. Run end-to-end signal→VM test (NEW — must be written)
python -m pytest tests/test_signal_to_vm.py -v
```

---

## 8. Conformance Test Implications

### 8.1 Current State: Tests Are Unrunnable

The conformance test vectors in `tests/test_conformance.py` use System B numbering but the interpreter uses System A. Running them against the current interpreter produces incorrect results:

| Test | Expected Behavior | Actual Behavior on System A Interpreter |
|------|-------------------|----------------------------------------|
| `HALT (0x00)` | VM stops | Decoded as `NOP` — VM runs past end of bytecode |
| `NOP (0x01)` | No state change | Decoded as `MOV` — reads R1 into R0 |
| `MOVI R0, 42 (0x18)` | R0 = 42 | Decoded as `ICMP` — performs comparison |
| `ADD R2, R0, R1 (0x20)` | R2 = 30 | Decoded as `PUSH` — pushes R0 to stack |
| `PUSH R0 (0x08)` | Push R0 | Decoded as `IADD` — adds two registers |
| `INC R0 (0x04)` | R0 = 42 | Decoded as `JMP` — unconditional jump |

**None of the 13 test vectors with concrete bytecode will pass on the current interpreter.**

### 8.2 Post-Migration State

After migration, all conformance tests should pass. However, the conformance tests contain some internal inconsistencies:

- INC is tested at `0x04`, but both System A and System B place INC elsewhere (System A: `0x0E`, System B: `0x08`). The test comment says `0x04` but the correct value per `isa_unified.py` is `0x08`.
- DEC is tested at `0x05`, similarly incorrect for both systems.
- PUSH is tested at `0x08`, which matches neither system (System A: `0x20`, System B: `0x0C`).

**These test vectors need correction independent of the migration.**

### 8.3 Missing Critical Test

There is **no integration test** that:
1. Compiles a Signal program using `SignalCompiler`
2. Feeds the resulting bytecode into `Interpreter`
3. Verifies execution results

This is the single test that would have caught this divergence immediately. It must be written as part of Phase 0.

---

## 9. Appendix: Complete Opcode Mapping Table

### 9.1 System A → System B Translation

For use during migration. Format: `OLD_VALUE → NEW_VALUE (mnemonic)`

```
System Control:
0x00 → 0x01 (NOP)
0x01 → 0x3A (MOV)
0x02 → 0x38 (LOAD)
0x03 → 0x39 (STORE)
0x04 → 0x43 (JMP)
0x05 → 0x3C (JZ)
0x06 → 0x3D (JNZ)
0x07 → 0x45 (CALL)

Integer Arithmetic:
0x08 → 0x20 (ADD)
0x09 → 0x21 (SUB)
0x0A → 0x22 (MUL)
0x0B → 0x23 (DIV)
0x0C → 0x24 (MOD)
0x0D → 0x0B (NEG)
0x0E → 0x08 (INC)
0x0F → 0x09 (DEC)

Bitwise:
0x10 → 0x25 (AND)
0x11 → 0x26 (OR)
0x12 → 0x27 (XOR)
0x13 → 0x0A (NOT)
0x14 → 0x28 (SHL)
0x15 → 0x29 (SHR)
0x16 → (no direct equivalent — ROTL not in unified)
0x17 → (no direct equivalent — ROTR not in unified)

Comparison:
0x18 → (no direct equivalent — ICMP not in unified; use CMP_EQ etc.)
0x19 → 0x2C (CMP_EQ)
0x1A → 0x2D (CMP_LT)
0x1B → (no equivalent — ILE; use CMP_LT)
0x1C → 0x2E (CMP_GT)
0x1D → (no equivalent — IGE; use CMP_GT)
0x1E → (no equivalent — TEST)
0x1F → (no equivalent — SETCC)

Stack:
0x20 → 0x0C (PUSH)
0x21 → 0x0D (POP)
0x22 → (no equivalent — DUP not in unified)
0x23 → 0x3B (SWP)
0x24 → (no equivalent — ROT not in unified)
0x25 → 0x4C (ENTER)
0x26 → 0x4D (LEAVE)
0x27 → (no equivalent — ALLOCA)

Function:
0x28 → 0x02 (RET)
0x29 → (no equivalent — CALL_IND)
0x2A → 0xE3 (TAILCALL)
0x2B → 0x18 (MOVI)
0x2C → 0x24 (MOD) [duplicate — IREM]
0x2D → (no equivalent — CMP flags-only)
0x2E → (no equivalent — JE)
0x2F → (no equivalent — JNE)

Memory:
0x30 → (no equivalent — REGION_CREATE; use MALLOC)
0x31 → 0xD8 (FREE ≈ REGION_DESTROY)
0x32 → (no equivalent — REGION_TRANSFER)
0x33 → 0xD0 (DMA_CPY ≈ MEMCOPY)
0x34 → 0xD1 (DMA_SET ≈ MEMSET)
0x35 → (no equivalent — MEMCMP)
0x36 → (no equivalent — JL)
0x37 → (no equivalent — JGE)

Type:
0x38 → (no equivalent — CAST; use FTOI/ITOF)
0x39 → (no equivalent — BOX)
0x3A → (no equivalent — UNBOX)
0x3B → (no equivalent — CHECK_TYPE)
0x3C → (no equivalent — CHECK_BOUNDS)

Float:
0x40 → 0x30 (FADD)
0x41 → 0x31 (FSUB)
0x42 → 0x32 (FMUL)
0x43 → 0x33 (FDIV)
0x44 → 0x0B (NEG) [FNEG → use NEG]
0x45 → 0x34 (FMIN)
0x46 → 0x35 (FMAX)
0x47 → (no equivalent — FABS)

Float Comparison:
0x48 → (no equivalent — FEQ; use CMP_EQ on float)
0x49 → (no equivalent — FLT)
0x4A → (no equivalent — FLE)
0x4B → (no equivalent — FGT)
0x4C → (no equivalent — FGE)
0x4D → (no equivalent — JG)
0x4E → (no equivalent — JLE)
0x4F → (no equivalent — LOAD8)

SIMD:
0x50 → 0xB0 (VLOAD)
0x51 → 0xB1 (VSTORE)
0x52 → 0xB2 (VADD)
0x53 → (no equivalent — VSUB)
0x54 → 0xB3 (VMUL)
0x55 → (no equivalent — VDIV)
0x56 → 0xB4 (VDOT ≈ VFMA)
0x57 → (no equivalent — STORE8)

A2A Protocol:
0x60 → 0x50 (TELL)
0x61 → 0x51 (ASK)
0x62 → 0x52 (DELEG)
0x63 → (no equivalent — DELEGATE_RESULT)
0x64 → 0x56 (REPORT)
0x65 → (no equivalent — REQUEST_OVERRIDE)
0x66 → 0x53 (BCAST)
0x67 → 0x57 (MERGE ≈ REDUCE)
0x68 → (no equivalent — DECLARE_INTENT)
0x69 → 0x69 (ASSERT_GOAL ≈ C_THRESH) [coincidental match!]
0x6A → (no equivalent — VERIFY_OUTCOME)
0x6B → (no equivalent — EXPLAIN_FAILURE)
0x6C → (no equivalent — SET_PRIORITY)
0x70 → 0x5C (TRUST_CHECK ≈ TRUST)
0x71 → (no equivalent — TRUST_UPDATE)
0x72 → (no equivalent — TRUST_QUERY)
0x73 → (no equivalent — REVOKE_TRUST)
0x74 → (no equivalent — CAP_REQUIRE)
0x75 → (no equivalent — CAP_REQUEST)
0x76 → (no equivalent — CAP_GRANT)
0x77 → (no equivalent — CAP_REVOKE)
0x78 → (no equivalent — BARRIER)
0x79 → (no equivalent — SYNC_CLOCK)
0x7A → (no equivalent — FORMATION_UPDATE)
0x7B → (no equivalent — EMERGENCY_STOP)

System:
0x80 → 0x00 (HALT)
0x81 → 0x15 (YIELD)
0x82 → (no equivalent — RESOURCE_ACQUIRE)
0x83 → (no equivalent — RESOURCE_RELEASE)
0x84 → 0x04 (DEBUG_BREAK ≈ BRK)
```

### 9.2 Opcodes Only in System B (Need New Interpreter Handlers)

| Range | Count | Category | Priority |
|-------|:---:|----------|:--------:|
| 0x03 IRET | 1 | System | LOW |
| 0x04 BRK | 1 | Debug | MEDIUM |
| 0x05 WFI, 0x06 RESET, 0x07 SYN | 3 | System | LOW |
| 0x0E CONF_LD, 0x0F CONF_ST | 2 | Confidence | MEDIUM |
| 0x10-0x17 SYS, TRAP, DBG, CLF, SEMA, CACHE, STRIPCF | 8 | System/Debug | LOW |
| 0x19-0x1F ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI | 7 | Arithmetic | HIGH |
| 0x2A MIN, 0x2B MAX | 2 | Arithmetic | LOW |
| 0x30-0x37 FADD..FMAX, FTOI, ITOF | 8 | Float | MEDIUM |
| 0x3B SWP | 1 | Move | LOW |
| 0x3E JLT, 0x3F JGT | 2 | Control | MEDIUM |
| 0x40-0x47 MOVI16..SELECT | 8 | Control | HIGH |
| 0x48-0x4F LOADOFF..FILL | 8 | Memory | MEDIUM |
| 0x54 ACCEPT, 0x55 DECLINE | 2 | A2A | MEDIUM |
| 0x58 FORK, 0x59 JOIN | 2 | A2A | HIGH |
| 0x5A SIGNAL, 0x5B AWAIT | 2 | A2A | HIGH |
| 0x5C TRUST, 0x5D DISCOV, 0x5E STATUS, 0x5F HEARTBT | 4 | A2A | MEDIUM |
| 0x60-0x6F C_ADD..C_VOTE | 16 | Confidence | MEDIUM |
| 0x70-0x7F V_EVID..V_PRAGMA | 16 | Viewpoint | LOW |
| 0x80-0x8F SENSE..CANBUS | 16 | Sensor | LOW |
| 0x90-0x9F ABS..FCOS | 16 | Math/Crypto | LOW |
| 0xA0-0xAF LEN..KEYGEN | 16 | Collection/Crypto | LOW |
| 0xB0-0xBF VLOAD..VSELECT | 16 | Vector | MEDIUM |
| 0xC0-0xCF TMATMUL..TQUANT | 16 | Tensor | LOW |
| 0xD0-0xDF DMA_CPY..GPU_SYNC | 16 | Memory/Compute | LOW |
| 0xE0-0xEF JMPL..WATCH | 16 | Control/Debug | MEDIUM |
| 0xF0-0xFF HALT_ERR..ILLEGAL | 16 | System | MEDIUM |

**Total new opcodes requiring interpreter handlers: ~230**

---

## 10. Immediate Action Items

| # | Action | Owner | Priority | ETA |
|---|--------|-------|:--------:|:---:|
| 1 | Write Signal→VM integration test (compile + execute + verify) | Any | P0 | 1 hour |
| 2 | Fix conformance test INC/DEC/PUSH byte values | Any | P0 | 15 min |
| 3 | Create migration branch with pre-migration tag | Any | P0 | 5 min |
| 4 | Write comprehensive opcode regression test suite | Any | P0 | 4 hours |
| 5 | Execute Phase 1: remap opcode values in `opcodes.py` | Architect | P1 | 2 hours |
| 6 | Execute Phase 3: update interpreter dispatch | Architect | P1 | 4 hours |
| 7 | Execute Phase 4: update bytecode encoder | Architect | P1 | 2 hours |
| 8 | Execute Phase 5: update all dependent code | Team | P1 | 4 hours |
| 9 | Execute Phase 6: update all tests | Team | P1 | 3 hours |
| 10 | Run full test suite and verify zero regressions | Any | P0 | 1 hour |

**Estimated total migration effort: ~20 hours of focused engineering work.**

---

## 11. Conclusion

The FLUX ecosystem has an ISA divergence that makes its signal compiler output incompatible with its interpreter. This is not a cosmetic issue — it is a **correctness-critical bug** that silently corrupts the meaning of every A2A bytecode instruction.

The root cause is clear: two independent ISA developments that were never unified at the code level. The fix path is clear: migrate `opcodes.py` to match the converged `isa_unified.py` specification. The risk is manageable with proper testing, branching, and phased execution.

**The most important immediate action is writing the Signal→VM integration test.** This single test would have prevented this divergence from ever reaching production. Every compiler/interpreter pair in the fleet should have this test.
