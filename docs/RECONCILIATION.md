# FLUX ISA A/B Reconciliation — Executed Timeline

**Branch:** `reconcile/isa-unified-interpreter` (PR #28)
**Date:** 2026-08-21
**Status:** COMPLETE — System B (unified) is now the default; System A preserved.

This is the executed-migration record for the FLUX opcode-numbering divergence
originally documented in `docs/OPCODE-RECONCILIATION.md` (Quill, 2026-04-12 —
retained for history and its A↔B mapping appendix). That analysis is **superseded**
by this document.

---

## 1. The two Systems (both preserved, neither deleted)

| | System A (legacy) | System B (canonical) |
|---|---|---|
| Source | `src/flux/bytecode/opcodes.py` (`Op`) | `src/flux/bytecode/isa_unified.py` (`build_unified_isa()`), mirror `opcodes_unified.py` (`UnifiedOp`) |
| Origin | Oracle1's original VM numbering | Converged 3-agent ISA (Oracle1 🔮 + JetsonClaw1 ⚡ + Babel 🌐) |
| Interpreter selection | `Interpreter(isa="system_a")` | `Interpreter(isa="unified")` — **the default since the cutover** |
| A2A encoding | Format G (variable-length string payload) | Format E (fixed 4-byte register triple) |
| imm16 endianness | little-endian | **big-endian** (Formats F/G) |
| Status | Supported, byte-for-byte unchanged | Canonical, default |

**The migration is additive + a default-flip.** System A's table was never
rewritten or deleted; the interpreter gained a parallel System B dispatch and an
`isa` selector. Only the *default* was flipped at the end (Phase 6).

---

## 2. Timeline

| Phase | Commit | What changed | Tests |
|---|---|---|---|
| 1 — interpreter path | `802bead` | Added `opcodes_unified.py` + `_step_unified()` dispatch and the `isa` selector (default still `system_a`); unimplemented unified ops raise cleanly | 2676 |
| 2 — toolchain | `5849eb4` | `SignalCompiler(isa="unified")`; `CrossAssembler(target="system_a"|"unified")` + `UNIFIED_OPCODE_DEFS`; resolved JZ/endianness/A2A spec landmines | 2695 |
| 3 — conformance vectors | `3641715` | `test_conformance.py` made dual-mode executable; compiler-side System B emission executed & asserted; A2A range covered | 2721 |
| 4 — dual-mode tests | `4473413` | `test_dual_mode_equivalence.py` (A↔B equivalence) + legacy-suite annotations (retained-as-is rule) | 2739 |
| 5 — docs | *(this branch)* | `RECONCILIATION.md`, System A/B status notes in `isa_unified.py`/`opcodes.py`/`docs/ISA_UNIFIED.md` | 2739 |
| 6 — cutover | *(this branch)* | **Interpreter default → `unified`**; every System A consumer (tests, retro, CLI/REPL, tracer/profiler/debugger, agent, examples) pins `isa="system_a"` | **2740** |

---

## 3. Pre-existing bugs found & fixed (during reconciliation)

1. **TELL→VLOAD misdecode** (the fatal path): System B `TELL 0x50` was decoded by
   the System A interpreter as `VLOAD`. Root cause of the divergence; fixed by the
   System B dispatch path in Phase 1 (regression-tested in
   `test_conformance_unified.py`).
2. **LOOP back-offset off-by-instruction-size**: `_compile_loop` omitted the `+4`
   in the back-offset, so the body ran once regardless of count. Invisible until a
   VM-executed vector existed; caught by the Phase 3 loop vector, fixed in `3641715`.
3. **BCAST agent-field aliasing**: `rs1=0` pointed at `R0` (which held the tag), so
   the packed agent field leaked the tag id. Now `rs1` is a dedicated never-loaded
   zero register (Phase 3).

## 4. Spec landmines resolved (Phase 2)

1. **JZ/JNZ/JLT/JGT are Format F**, not Format E: `(op, rd, imm16)` big-endian.
   Evidence: `signal_compiler._compile_if` back-patches a BE imm16 (parallel to
   `JMP 0x43`); asm-text vectors use two-operand `JNZ R2, done`.
2. **imm16 = big-endian in System B**: compiler `_emit_format_f`, MOVI16 vector
   `[0x40, rd, 0x10, 0x00]` = 4096, and `formats.py` all agree; the header's old
   "little-endian" claim was corrected.
3. **A2A operand registers now populated**: converged spec (TELL "Send rs2 to agent
   rs1, tag rd"; ASK "resp→rd") requires operand registers to carry values; the
   compiler loads them (names interned via `zlib.crc32 & 0x7FFF`) and the unified
   interpreter writes ASK responses to `rd`.

---

## 4b. A↔B mapping (abridged — full table in `opcodes.py` + `isa_unified.py`)

Key conflicts (System A value → System B value):

| Mnemonic | A | B | | Mnemonic | A | B |
|---|---|---|---|---|--------|---|---|---|
| HALT | 0x80 | 0x00 | | MOV | 0x01 | 0x3A |
| NOP | 0x00 | 0x01 | | LOAD | 0x02 | 0x38 |
| ADD | 0x08 | 0x20 | | STORE | 0x03 | 0x39 |
| MOVI | 0x2B | 0x18 | | PUSH/POP | 0x20/0x21 | 0x0C/0x0D |
| JMP | 0x04 | 0x43 | | JZ/JNZ | 0x05/0x06 | 0x3C/0x3D |
| CALL | 0x07 | 0x45 | | RET | 0x28 | 0x02 |
| TELL/ASK/BCAST | 0x60/0x61/0x66 | 0x50/0x51/0x53 | | VLOAD | 0x50 | 0xB0 |

Both tables are annotated and preserved; **no mapping is ever deleted**.

---

## 5. Test coverage (dual-mode + divergence)

- **`tests/test_dual_mode_equivalence.py`** — for each core semantic pinned by a
  System A hard-coded test, runs the SAME program encoded in System B and asserts
  both modes produce identical observable results (`run_a` vs `run_b`).
- **`tests/test_conformance_unified.py`** — the P0 integration gate: executes every
  concrete `TEST_VECTORS` entry (from `test_conformance.py`) through the unified
  interpreter, including the A2A range, plus `test_cross_mode_is_rejected_not_misdecoded`
  (the divergence test — System A `TELL 0x60` in unified mode raises cleanly rather
  than silently misdecoding, and vice-versa).
- **`tests/test_toolchain_unified.py`** — System B compiler/assembler modes and the
  three landmine resolutions.

Full suite: **2740 passed** (was 2651 on `main` @ `20afa5e`, then 2739 through
Phase 4; Phase 6 adds one default-mode test).

---

## 6. Cutover state

- **Default = System B (unified)** for `Interpreter(...)` and for `SignalCompiler`.
- **System A = selectable** via `Interpreter(isa="system_a")`, `CrossAssembler(target="system_a")`,
  `FluxDebugger(..., isa="system_a")`. All pre-cutover System A bytecode is preserved
  and executes unchanged under legacy mode.
- **Rollback**: `git revert` the Phase 6 commit, or set the interpreter default back
  to `"system_a"` (one line). System A's table was never deleted, so legacy bytecode
  remains executable indefinitely. Pre-cutover state tagged `pre-isa-cutover`.
