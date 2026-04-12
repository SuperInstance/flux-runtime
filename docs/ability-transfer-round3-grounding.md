# Ability Transfer Round 3 — Grounding

**Task ID:** ABIL-003 | **Author:** Super Z (FLUX Fleet, Task 6-b) | **Date:** 2026-04-15
**Version:** 1.0 | **Status:** SHIPPED
**Predecessor:** Round 2 (DeepSeek Synthesis, 2026-04-14) → Round 1 (Kimi Philosophy + Oracle1 Grounding, 2026-04-11)
**Methodology:** Concrete forge specifications grounded in fleet artifacts and existing infrastructure

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Forge Taxonomy](#2-forge-taxonomy)
3. [Concrete Forge Exercises](#3-concrete-forge-exercises)
4. [Repo Structure Template](#4-repo-structure-template)
5. [Badge System](#5-badge-system)
6. [Evaluation Framework](#6-evaluation-framework)
7. [Integration with Fleet Infrastructure](#7-integration-with-fleet-infrastructure)

---

## 1. Executive Summary

Round 1 asked *what* ability transfer means for an AI fleet. Round 2 answered *how* — the Five Forge paradigm, the capability genome metaphor, and four transfer mechanisms (cloning, forging, delegation, knowledge federation). This Round 3 document answers *what exactly to build*.

We define 10 concrete forge exercises spanning all five forge types (Code, Design, Debug, Bridge, Collab) across four difficulty levels (Beginner → Intermediate → Advanced → Master). Each exercise maps directly to real fleet work — ISA specification, conformance testing, cross-runtime debugging, protocol implementation, system architecture, and fleet coordination. Every exercise uses existing fleet artifacts (test vectors, VM implementations, protocol specs) as raw material, ensuring that learning transfers immediately to productive fleet contribution.

We specify the standard repo structure for forge exercises, a badge and career-stage system (Journeyman → Craftsman → Master), an automated evaluation framework (`ForgeEvaluator` class), and integration points with existing fleet infrastructure (TASK-BOARD, Semantic Router, Knowledge Federation, Bottle protocol). A new agent completing all 10 forges will have hands-on experience with every major fleet subsystem and 10 verified artifacts to prove it.

This is the implementation blueprint. Round 4 will build the actual `evaluate.py` scripts and populate the forge repos.

---

## 2. Forge Taxonomy

The Five Forge paradigm from bootcamp research v2 is expanded here with a four-level difficulty progression. Each cell describes a representative exercise archetype; the 10 concrete forges in Section 3 instantiate specific cells.

### 2.1 Complete Forge × Difficulty Matrix

| Forge | Beginner | Intermediate | Advanced | Master |
|-------|----------|-------------|----------|--------|
| **Code** | Read bytecode programs and predict register state. Trace execution by hand. Identify instruction formats in hex dumps. | Write new conformance test vectors for undocumented opcodes. Produce bytecode that passes the test suite. Extend existing programs with new instructions. | Refactor a working VM to support a new format. Optimize instruction dispatch for a hot path. Add branch prediction hints to the interpreter loop. | Design and implement a new VM subsystem (fiber scheduler, extension loader) from scratch. Write the reference implementation that other runtimes will follow. |
| **Design** | Follow an existing spec to implement a feature. Extend a design by adding parameters within given constraints. | Design a new ISA extension given functional requirements, opcode constraints, and collision rules. Write formal specifications that an implementor could follow. | Create a subsystem architecture from high-level goals (security pipeline, capability enforcement). Resolve competing constraints and document tradeoffs. | Architect a new fleet service end-to-end: define the problem space, design the solution, specify interfaces, plan the implementation phases. |
| **Debug** | Find known bug types in controlled test vectors (wrong opcode, off-by-one, register swap). Diagnose a failing conformance test by reading the bytecode. | Find unknown bugs by running test suites and analyzing unexpected failures. Cross-reference behavior between two implementations. | Diagnose cross-system bugs where Python and C runtimes disagree. Use binary search, differential execution, and hypothesis testing. | Investigate fleet-wide failures: trace a bug across repo boundaries, identify the root cause in a shared dependency, propose and validate a fleet-wide fix. |
| **Bridge** | Translate between bytecode ↔ assembly ↔ spec. Given a spec excerpt, write a test vector. Given test output, write a spec description. | Build a translator tool: assembler, disassembler, spec-to-code generator. Bridge between representations with automated round-trip verification. | Translate between high-level concepts and low-level implementation: write a bytecode program that implements a protocol. Compile C to FLUX bytecode that matches hand-written reference. | Translate natural language requirements into a working system. Given a user story, produce the ISA extension, the test vectors, the interpreter patch, and the integration test. |
| **Collab** | Paired code review: write a solution, have a peer review it, respond to feedback, resubmit. | 3-agent coordination: implement complementary parts of a protocol, negotiate interfaces, merge contributions. | 5-agent fleet operation: coordinate a multi-repo change with agent specialization, sequential dependencies, and verification gates. | Cross-fleet integration: coordinate with agents from other vessels, reconcile different design philosophies, produce a merged specification. |

### 2.2 Difficulty Calibration

Difficulty levels are calibrated against the Vygotsky Zone of Proximal Development principle from bootcamp research v2:

| Level | Target Agent | Prerequisite Knowledge | Time Budget | Failure Mode |
|-------|-------------|----------------------|-------------|-------------|
| **Beginner** | New greenhorn, first session | Module 1 (bytecode basics) | 2 hours | Getting stuck on format identification |
| **Intermediate** | Agent with 2-3 sessions experience | Modules 1-3, at least 1 beginner forge | 3-4 hours | Missing edge cases in design |
| **Advanced** | Established agent (Crafter level) | Modules 1-6, at least 2 intermediate forges | 3-5 hours | Insufficient cross-system reasoning |
| **Master** | Senior agent (Architect+ level) | All modules, at least 3 advanced forges | 8 hours | Coordination overhead, scope creep |

### 2.3 Interleaving Principle

Per the interleaving principle from bootcamp research v2, agents should not complete all Code forges before starting Debug forges. The recommended progression interleaves forge types:

```
FluxBytecode101 (Code, Beg) → OpcodeHunter (Debug, Beg) → Assembler Apprentice (Bridge, Int)
→ Conformance Builder (Code, Int) → Extension Designer (Design, Int) → Fleet Protocol Expert (Collab, Int)
→ CrossRuntime Debug (Debug, Adv) → Performance Detective (Debug, Adv)
→ Architecture Forger (Design, Adv) → Fleet Commander (Collab, Master)
```

This sequence ensures each forge builds on skills from the previous one while forcing the agent to switch cognitive modes between exercises.

---

## 3. Concrete Forge Exercises

### 3.1 FluxBytecode101 — Read and Predict

| Field | Value |
|-------|-------|
| **Forge type** | Code |
| **Difficulty** | Beginner |
| **Estimated time** | 2 hours |
| **Prerequisites** | Module 1 (Bytecode Basics) |
| **Badge** | `forge-bytecode-reader` |

**Learning objectives:**
1. Identify FLUX instruction formats (A through G) in raw bytecode hex dumps
2. Decode register operands, immediate values, and signed extensions from byte sequences
3. Trace execution step-by-step through multi-instruction programs
4. Predict final register state after program execution
5. Verify predictions against the unified interpreter output

**Step-by-step instructions:**

1. Read `isa_unified.py` — scan the opcode table, note the format assignment for each opcode range (0x00-0x0F = Format A, 0x10-0x1F = Format B/C, etc.)
2. Read `formats.py` — understand the byte layout for each format: Format A (1 byte), B (2 bytes), C (2 bytes), D (3 bytes), E (4 bytes), F (4 bytes), G (5 bytes)
3. Open `test_conformance.py` — locate the first 5 test vectors (VECT-001 through VECT-005)
4. For VECT-001: write down each byte, identify the format, decode the opcode name, decode all operands. Record your step-by-step trace in a markdown table (Instruction | Format | Bytes | Register Effect)
5. Predict the final value of every register (R0-R15) after VECT-001 executes
6. Run `python tools/conformance_runner.py --runtime python` and compare your prediction to the actual output
7. If your prediction was wrong, identify which instruction caused the discrepancy and document what you misunderstood
8. Repeat steps 4-7 for VECT-002 through VECT-005
9. Open `test_conformance_expanded.py` — locate the memory test vectors (MEM-001 through MEM-005)
10. For MEM-001: trace the LOAD/STORE execution, track memory contents at each step, predict the final R0 value
11. Run the expanded conformance runner and verify MEM-001 through MEM-005
12. Now try a "blind prediction": read only the bytecode hex of VECT-009 (GCD), predict R0 without looking at the expected value
13. Run VECT-009 and check. Document how close your prediction was
14. Create a personal "format cheat sheet" — a one-page reference showing the byte layout of each format with one example
15. Write your cheat sheet to `src/cheatsheet.md` in the forge repo
16. Run `python evaluate.py --check-format-cheatsheet` to verify your cheat sheet covers all 7 formats

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Format identification accuracy (Steps 4-7) | 25% | ≥4/5 test vectors correct on first attempt |
| Register prediction accuracy (Steps 5-11) | 35% | ≥8/10 test vectors predicted correctly |
| Blind prediction quality (Steps 12-13) | 15% | Prediction within ±5 of actual value |
| Cheat sheet completeness (Steps 14-16) | 15% | All 7 formats documented with correct byte layouts |
| Discrepancy analysis quality (Step 7) | 10% | Root cause identified when prediction was wrong |

**Solution verification:** `evaluate.py` runs the agent's predictions against the conformance runner, checks format identification against `formats.py`, and validates the cheat sheet structure.

**Badge earned:** `forge-bytecode-reader` (铜 bronze tier)

---

### 3.2 OpcodeHunter — Find the Wrong Opcodes

| Field | Value |
|-------|-------|
| **Forge type** | Debug |
| **Difficulty** | Beginner |
| **Estimated time** | 2 hours |
| **Prerequisites** | Module 1 (Bytecode Basics), FluxBytecode101 recommended |
| **Badge** | `forge-opcode-hunter` |

**Learning objectives:**
1. Recognize common bytecode encoding errors (wrong opcode number, wrong format, sign extension mistakes)
2. Use the conformance runner as a diagnostic tool (not just a pass/fail checker)
3. Form hypotheses about bug root causes before attempting fixes
4. Distinguish between spec-compliant and spec-violating bytecode
5. Document bug findings in a structured report format

**Step-by-step instructions:**

1. Read the historical bug report from worklog session 8: "Found 4 critical opcode errors (INC 0x04→0x08, DEC 0x05→0x09, PUSH 0x08→0x0C, POP 0x09→0x0D)"
2. Understand the root cause: `test_conformance.py` originally used `opcodes.py` (runtime ISA) numbering instead of `isa_unified.py` (unified ISA) numbering
3. Read the "poisoned" version of 10 test vectors provided in `tests/poisoned_vectors.py` — each has exactly one injected bug
4. Bug types include: wrong opcode number, wrong format size, register operand swap, sign extension error, missing HALT, off-by-one in loop bound
5. For each poisoned vector:
   a. Read the bytecode and the expected result
   b. Run it on the unified interpreter
   c. Compare actual output to expected output
   d. Form a hypothesis: "The bug is in byte N because..."
   e. Test your hypothesis: modify byte N and re-run
   f. Confirm the fix produces the correct output
6. Write a structured bug report for each fix: bug description, hypothesis, fix applied, verification result
7. Run `python evaluate.py --check-bug-reports` to validate all 10 bugs found and correctly fixed
8. Read the GCD test vector (VECT-009) — it had a real bug: missing zero-check before MOD
9. Explain why `CMP_EQ R0, 0` before `MOD R0, R0, R1` prevents a division-by-zero crash
10. Write a new poisoned vector: take a working test, inject one bug, swap with another agent to debug

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Bugs found (Step 5) | 40% | ≥8/10 bugs correctly identified |
| Hypothesis quality (Step 5d) | 20% | Hypothesis formed before testing fix (check git history) |
| Report completeness (Step 6) | 20% | All 5 fields present for each bug |
| GCD analysis (Steps 8-9) | 10% | Correct explanation of zero-check purpose |
| Poisoned vector quality (Step 10) | 10% | Bug is non-trivial and vector compiles/runs |

**Solution verification:** `evaluate.py` diffs the agent's fixes against the known solutions, checks that hypothesis timestamps precede fix timestamps, and validates the bug report structure.

**Badge earned:** `forge-opcode-hunter` (bronze tier)

---

### 3.3 Assembler Apprentice — Build a Simple Assembler

| Field | Value |
|-------|-------|
| **Forge type** | Bridge |
| **Difficulty** | Intermediate |
| **Estimated time** | 3 hours |
| **Prerequisites** | Modules 1-2, FluxBytecode101 + OpcodeHunter |
| **Badge** | `forge-assembler-apprentice` |

**Learning objectives:**
1. Implement a two-pass assembler for FLUX bytecode Formats A through D
2. Handle label resolution with forward references
3. Understand pseudo-instruction expansion (e.g., JNZ label → MOVI R15, offset + JNZ R0, R15)
4. Verify assembler output by round-tripping: assemble → disassemble → assemble and compare
5. Translate between assembly mnemonics and binary bytecode representation

**Step-by-step instructions:**

1. Read `assembler.py` (existing fleet assembler, ~430 lines) — study the two-pass architecture
2. Read the pseudo-instruction expansion rules: JNZ/JZ use R15 as scratch register (7-byte expansion)
3. Implement a simplified assembler covering only Formats A-D:
   - Format A: HALT, NOP, RET (1-byte instructions)
   - Format B: INC, DEC, NOT, NEG, PUSH, POP (2-byte: opcode + register)
   - Format C: SYS, TRAP, DBG (2-byte: opcode + immediate)
   - Format D: MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI (3-byte: opcode + register + imm8)
4. Pass 1: parse assembly source, identify labels, compute instruction sizes, build label table
5. Pass 2: emit bytecode with resolved label offsets
6. Handle sign extension for Format D imm8: values 128-255 should be stored as unsigned but interpreted as signed
7. Write at least 5 unit tests for the assembler:
   - Simple arithmetic (MOVI + ADD + HALT)
   - Format B operations (INC, PUSH, POP)
   - Mixed formats (MOVI, ADDI, INC, HALT)
   - All opcodes from Formats A-D in a single program
   - Round-trip: assemble → disassemble → reassemble → byte-identical
8. Test your assembler against the existing conformance suite: assemble 5 test vectors and verify the output matches the stored bytecode
9. Run `python evaluate.py --check-assembler` to verify correctness
10. Document the assembler's opcode table in `src/opcode_map.py`

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Format A support (Step 3) | 10% | HALT, NOP, RET all produce correct 1-byte output |
| Format B support (Step 3) | 15% | INC, DEC, NOT, NEG, PUSH, POP all correct |
| Format C support (Step 3) | 10% | SYS, TRAP, DBG correct |
| Format D support (Step 3) | 20% | MOVI with sign extension, ADDI, all 8 opcodes correct |
| Label resolution (Steps 4-5) | 15% | Forward references resolve correctly |
| Round-trip fidelity (Step 7) | 15% | assemble → disassemble → assemble produces identical bytes |
| Conformance match (Step 8) | 15% | ≥4/5 test vectors produce identical bytecode |

**Solution verification:** `evaluate.py` compiles reference assembly programs with the agent's assembler, checks byte-for-byte match against stored bytecode, and runs round-trip tests.

**Badge earned:** `forge-assembler-apprentice` (silver tier)

---

### 3.4 Conformance Builder — Write Test Vectors

| Field | Value |
|-------|-------|
| **Forge type** | Code |
| **Difficulty** | Intermediate |
| **Estimated time** | 3 hours |
| **Prerequisites** | Modules 1-3, Assembler Apprentice recommended |
| **Badge** | `forge-conformance-builder` |

**Learning objectives:**
1. Write conformance test vectors that exercise specific ISA behaviors
2. Cover edge cases: boundary values, signed/unsigned confusion, overflow, zero operands
3. Follow the test vector format: name, description, source (optional), bytecode, expected registers, category
4. Verify all new vectors pass on both Python and C runtimes
5. Achieve opcode coverage improvement for under-tested instruction categories

**Step-by-step instructions:**

1. Read `test_conformance_expanded.py` — understand the test vector format (74 existing vectors, 35 unique opcodes)
2. Run `python tools/conformance_runner.py --runtime python --expanded` to see the current coverage report
3. Identify the 3 least-tested opcode categories from the coverage report (e.g., float ops, memory offset, control flow edge cases)
4. Write 10 new test vectors:
   - 2 vectors for float operations (FADD, FSUB using F0-F15 registers)
   - 2 vectors for memory offset operations (LOADOFF, STOREOFF using Format G)
   - 2 vectors for extended control flow (JAL + RET round-trip, LOOP instruction)
   - 2 vectors for comparison edge cases (CMP_LT with equal values, CMP_GT with negative numbers)
   - 2 vectors for complex multi-format programs (≥4 formats in a single program)
5. For each vector, provide: test_id, description, bytecode array, expected register dict, category tag
6. Assemble your vectors using the fleet assembler (or your own from Assembler Apprentice) to verify correctness
7. Run all 10 vectors on the Python runtime: `python tools/conformance_runner.py --runtime python --expanded`
8. Run all 10 vectors on the C runtime: `python tools/conformance_runner.py --runtime c --expanded`
9. Verify cross-runtime agreement: `python tools/conformance_runner.py --all --expanded`
10. Document the coverage improvement: which opcodes were added, what edge cases are now covered
11. Run `python evaluate.py --check-vectors` to validate format, correctness, and coverage improvement

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Vector format compliance (Step 5) | 10% | All 10 vectors follow the standard format |
| Python runtime pass rate (Step 7) | 25% | 10/10 vectors pass |
| C runtime pass rate (Step 8) | 20% | 10/10 vectors pass |
| Cross-runtime agreement (Step 9) | 20% | 0 disagreements between Python and C |
| Edge case coverage (Step 4) | 15% | All 5 categories represented, ≥3 genuine edge cases |
| Coverage documentation (Step 10) | 10% | Before/after opcode count with specific new opcodes listed |

**Solution verification:** `evaluate.py` validates the vector format (JSON schema), runs each vector on both runtimes, checks agreement, and computes coverage delta.

**Badge earned:** `forge-conformance-builder` (silver tier)

---

### 3.5 Extension Designer — Design a New ISA Extension

| Field | Value |
|-------|-------|
| **Forge type** | Design |
| **Difficulty** | Intermediate |
| **Estimated time** | 4 hours |
| **Prerequisites** | Modules 1-4, Conformance Builder recommended |
| **Badge** | `forge-extension-designer` |

**Learning objectives:**
1. Analyze the existing opcode space to identify available extension slots
2. Design new opcodes using the Format H escape prefix mechanism from the v3 spec
3. Write formal specifications with encoding, semantics, error conditions, and examples
4. Perform collision analysis against existing extensions (EXT_BABEL through EXT_TEMPORAL)
5. Produce conformance test vectors for the new opcodes

**Step-by-step instructions:**

1. Read `isa-v3-escape-prefix-spec.md` — understand Format H encoding: `0xFF [ext_id] [sub_opcode] [operands...]`
2. Read `isa-v3-address-map.md` — note the 6 existing fleet-standard extensions (0x01-0x06)
3. Identify available extension IDs: 0x07-0x7F are available for fleet-standard use
4. Choose extension ID 0x07 for your new extension: **EXT_REGEX** (regular expression matching opcodes)
5. Design 6 sub-opcodes for regex operations:
   - `RE_COMPILE` — compile a pattern stored in memory
   - `RE_MATCH` — match a string against a compiled pattern
   - `RE_SEARCH` — find first match in a string
   - `RE_CAPTURE` — extract capture groups
   - `RE_REPLACE` — replace matched patterns
   - `RE_FREE` — release compiled pattern resources
6. For each sub-opcode, write a formal specification:
   - Encoding (byte-level with Format H prefix)
   - Operand description (which registers, what memory layout)
   - Semantic description (exact behavior, return values)
   - Error conditions (invalid pattern, out of memory, no match)
   - Example usage (assembly + bytecode)
7. Perform collision analysis: verify none of your sub-opcodes conflict with any existing extension
8. Write 6 conformance test vectors:
   - 2 for RE_COMPILE + RE_MATCH (valid match, no match)
   - 2 for RE_SEARCH (found, not found)
   - 1 for RE_CAPTURE (extract groups)
   - 1 for error handling (invalid pattern)
9. Document tradeoffs:
   - Why regex instead of string operations? ( fleet needs pattern matching for log analysis, bottle filtering)
   - What's NOT included? (backreferences — too complex for first version)
   - How does this compare to implementing regex in Python and calling via A2A?
10. Run `python evaluate.py --check-extension` to validate spec completeness, collision analysis, and test vectors

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Opcode space analysis (Steps 1-3) | 10% | Correct identification of available extension IDs |
| Spec completeness (Steps 4-6) | 30% | All 6 opcodes have encoding, semantics, errors, examples |
| Collision analysis (Step 7) | 15% | Zero conflicts with extensions 0x01-0x06 |
| Test vector quality (Step 8) | 25% | All 6 vectors follow format, test meaningful behaviors |
| Tradeoff analysis (Step 9) | 20% | Addresses "why this design" and "what's excluded" |

**Solution verification:** `evaluate.py` validates the spec structure, runs collision detection against the known extension registry, checks test vector format, and scores the tradeoff analysis.

**Badge earned:** `forge-extension-designer` (silver tier)

---

### 3.6 CrossRuntime Debug — Find Why Python and C Disagree

| Field | Value |
|-------|-------|
| **Forge type** | Debug |
| **Difficulty** | Advanced |
| **Estimated time** | 4 hours |
| **Prerequisites** | Modules 1-5, Conformance Builder, familiarity with C and Python |
| **Badge** | `forge-crossruntime-detective` |

**Learning objectives:**
1. Diagnose cross-runtime disagreements between Python and C FLUX VM implementations
2. Use differential debugging: run identical bytecode on both runtimes, compare execution traces
3. Identify implementation divergence (signed arithmetic, register width, overflow behavior)
4. Write targeted test vectors that expose specific divergence points
5. Propose and validate fixes that maintain backward compatibility

**Step-by-step instructions:**

1. Read `unified_interpreter.py` (Python VM, ~800 lines) and `flux_vm_unified.c` (C VM, ~680 lines)
2. Run the full cross-runtime comparison: `python tools/conformance_runner.py --all --expanded`
3. If all tests agree (current state), the evaluator will inject controlled divergence bugs into a modified C runtime binary
4. Run the comparison again — identify which tests now disagree
5. For each disagreement:
   a. Record the test ID, expected value, Python output, C output
   b. Read the relevant opcode implementation in both runtimes
   c. Form a hypothesis about the divergence (signed vs unsigned, 32-bit vs 64-bit, uninitialized register, endianness)
   d. Write a minimal test case that reproduces the divergence in isolation
   e. Test your hypothesis by modifying one implementation
6. Build a "divergence matrix": for each disagreeing test, document the root cause category
7. Categories to consider:
   - Signed/unsigned arithmetic (Python integers are arbitrary precision, C uses int64_t)
   - Register initialization (C may leave registers as garbage, Python initializes to 0)
   - Overflow behavior (Python doesn't overflow, C wraps)
   - Memory alignment (C may pad struct fields)
   - Byte order (both should be little-endian, but verify)
8. Propose a fix for each divergence that brings the C runtime into agreement with Python
9. Verify the fix: recompile C VM, re-run cross-runtime comparison, confirm 0 disagreements
10. Run `python evaluate.py --check-crossruntime` to validate all divergences found and fixed

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Divergence detection (Step 4) | 20% | All injected divergences detected |
| Hypothesis quality (Step 5c) | 15% | Specific hypothesis before fix attempted |
| Minimal reproduction (Step 5d) | 15% | Each divergence has a ≤5-instruction test case |
| Root cause categorization (Step 7) | 20% | All divergences correctly categorized |
| Fix correctness (Steps 8-9) | 20% | All divergences resolved, 0 remaining disagreements |
| Divergence matrix quality (Step 6) | 10% | Structured document with per-test analysis |

**Solution verification:** `evaluate.py` runs the modified C runtime, checks that all divergences are found, validates the divergence matrix, and re-runs with fixes to confirm resolution.

**Badge earned:** `forge-crossruntime-detective` (gold tier)

---

### 3.7 Fleet Protocol Expert — Implement Bottle Send/Receive

| Field | Value |
|-------|-------|
| **Forge type** | Collab |
| **Difficulty** | Intermediate |
| **Estimated time** | 3 hours |
| **Prerequisites** | Modules 3 (A2A Protocol) + 6 (Fleet Patterns) |
| **Badge** | `forge-protocol-expert` |

**Learning objectives:**
1. Implement the message-in-a-bottle protocol for fleet communication
2. Use the TELL (0x50) and ACCEPT (0x54) opcodes for A2A messaging
3. Design message serialization format compatible with the fleet's bottle conventions
4. Write integration tests that verify message delivery between simulated agents
5. Handle error conditions: undeliverable messages, trust threshold failures, message corruption

**Step-by-step instructions:**

1. Read Module 3 (A2A Protocol) — understand TELL, ASK, DELEG, BCAST, ACCEPT message types
2. Read the fleet's bottle protocol: `from-fleet/CONTEXT.md` format from oracle1-vessel
3. Study the `primitives.py` coordination patterns — Branch, Fork, CoIterate, Discuss, Synthesize, Reflect
4. Implement a `BottleProtocol` class with these methods:
   - `compose(sender, recipient, content, priority)` — create a bottle message
   - `send(bottle, transport)` — serialize and send via a transport layer
   - `receive(transport)` — deserialize and validate an incoming bottle
   - `acknowledge(bottle_id)` — send acknowledgment
5. Serialization format (JSON-based, compatible with fleet conventions):
   ```json
   {
     "bottle_id": "uuid",
     "sender": "agent-name",
     "recipient": "agent-name",
     "timestamp": "ISO-8601",
     "content_type": "recon|task|review|question",
     "content": { ... },
     "priority": 1-10,
     "trust_token": 0-1000,
     "reply_to": "bottle_id or null"
   }
   ```
6. Implement transport layer abstraction (file-based, HTTP, or in-memory for testing)
7. Write a two-agent simulation: Agent A sends a bottle to Agent B, Agent B receives and acknowledges
8. Write a three-agent chain: A → B → C with forwarding (BCAST or DELEG)
9. Add error handling: undeliverable recipient (returns error bottle), corrupt message (checksum validation)
10. Write integration tests for: send/receive, acknowledgment, three-agent chain, error cases
11. Run `python evaluate.py --check-protocol` to validate all tests pass

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Compose/serialize (Steps 4-5) | 15% | JSON format matches fleet conventions |
| Transport abstraction (Step 6) | 10% | At least 2 transport implementations |
| Two-agent scenario (Step 7) | 20% | Message delivered, acknowledged, content preserved |
| Three-agent chain (Step 8) | 20% | Message forwarded correctly through chain |
| Error handling (Step 9) | 15% | Undeliverable and corrupt messages handled gracefully |
| Integration tests (Step 10) | 20% | All scenarios have passing automated tests |

**Solution verification:** `evaluate.py` runs the integration tests, validates the serialization format against the fleet schema, and checks error handling coverage.

**Badge earned:** `forge-protocol-expert` (silver tier)

---

### 3.8 Performance Detective — Identify Bottlenecks Using Benchmarks

| Field | Value |
|-------|-------|
| **Forge type** | Debug |
| **Difficulty** | Advanced |
| **Estimated time** | 3 hours |
| **Prerequisites** | Modules 1-5, CrossRuntime Debug recommended |
| **Badge** | `forge-performance-detective` |

**Learning objectives:**
1. Use the benchmark suite to identify performance bottlenecks in the FLUX VM
2. Apply profiling techniques (cycle counting, instruction frequency analysis, hot path identification)
3. Distinguish between algorithmic bottlenecks (O(n²) loops) and implementation bottlenecks (slow dispatch)
4. Propose and measure the impact of optimization changes
5. Document performance findings in a structured benchmark report

**Step-by-step instructions:**

1. Read `flux_vm_unified.c` — understand the main execution loop, instruction dispatch, and register/memory access patterns
2. Read `unified_interpreter.py` — compare the Python dispatch mechanism (if/elif chain vs dictionary lookup)
3. Build a benchmark program: a tight loop that executes 10,000 iterations using LOOP instruction
4. Compile and run on C VM: `gcc -O2 -o flux_vm flux_vm_unified.c && time ./flux_vm benchmark.bin`
5. Run the same benchmark on Python VM: `time python unified_interpreter.py benchmark.bin`
6. Record cycle counts, wall-clock time, and instructions-per-second for both runtimes
7. Build 3 additional benchmark programs:
   - Memory-intensive: sequential LOAD/STORE across 1KB of memory
   - Register-intensive: chain of 20 arithmetic operations (ADD, SUB, MUL)
   - Control-flow-intensive: nested loops with conditional branches
8. Run all 4 benchmarks on both runtimes and record results
9. Identify the bottleneck for each benchmark:
   - Is it instruction dispatch overhead? Memory access latency? Interpreter loop overhead?
   - Where does Python spend most of its time? (Use Python's `cProfile` if needed)
   - Where does C spend most of its time? (Use `perf` or `gprof` if available)
10. Propose ONE optimization for the Python interpreter (e.g., computed goto dispatch, opcode cache, register file pre-fetch)
11. Implement the optimization and re-run benchmarks
12. Measure the improvement: compute the speedup ratio for each benchmark
13. Write a structured performance report with before/after data
14. Run `python evaluate.py --check-performance` to validate benchmark methodology and report quality

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Benchmark design (Steps 3-8) | 20% | All 4 benchmarks produce meaningful, measurable results |
| Bottleneck identification (Step 9) | 25% | Correct root cause for ≥3/4 benchmarks |
| Optimization proposal (Step 10) | 10% | Specific, implementable, grounded in profiling data |
| Optimization implementation (Step 11) | 15% | Code change that compiles/runs |
| Speedup measurement (Step 12) | 15% | Before/after data with correct speedup calculation |
| Report quality (Step 13) | 15% | Structured document with tables, methodology, conclusions |

**Solution verification:** `evaluate.py` runs the benchmarks, verifies the methodology (no trivially-passing benchmarks), checks that the optimization actually produces a measurable change, and validates the report structure.

**Badge earned:** `forge-performance-detective` (gold tier)

---

### 3.9 Architecture Forger — Design a New Fleet Service from Scratch

| Field | Value |
|-------|-------|
| **Forge type** | Design |
| **Difficulty** | Advanced |
| **Estimated time** | 5 hours |
| **Prerequisites** | Modules 1-6, Extension Designer + Fleet Protocol Expert |
| **Badge** | `forge-architecture-forger` |

**Learning objectives:**
1. Design a new fleet service from problem statement to implementation plan
2. Define service interfaces (APIs, message formats, data schemas)
3. Specify integration points with existing fleet infrastructure (Semantic Router, Bottle Protocol, Conformance Runner)
4. Resolve competing design constraints and document tradeoffs
5. Produce an implementation-ready specification that other agents could build

**Step-by-step instructions:**

1. Choose one of these fleet service design challenges (or propose your own with evaluator approval):
   - **Forge Service Registry**: A centralized registry where agents register completed forges and query other agents' capabilities
   - **Fleet Lint Bot**: An automated service that reviews new commits for fleet convention violations
   - **Capability Marketplace**: A service where agents can "advertise" capabilities and "hire" other agents for specific tasks
   - **Conformance Gate**: A CI service that runs conformance tests on every PR and blocks merge on failure
2. Write a 1-page problem statement: what problem does this service solve? Who are the users? What are the success criteria?
3. Design the service architecture:
   - Components and their responsibilities
   - Data flow between components
   - Storage (what data is persisted, where, in what format)
   - API surface (REST endpoints, bottle message types, or direct function calls)
4. Define integration points:
   - How does this service interact with the Semantic Router? (register capabilities, query routing)
   - How does it use the Bottle Protocol? (announce events, receive commands)
   - How does it connect to the Conformance Runner? (trigger tests, read results)
5. Design the data schema: define JSON schemas for all persistent data structures
6. Write error handling specifications: what fails, how is it detected, how is it recovered?
7. Identify 3 design alternatives for the core architecture and compare them:
   - Alternative A (centralized vs decentralized)
   - Alternative B (push vs pull communication)
   - Alternative C (monolithic vs microservice)
8. Document your chosen design and justify why it's better than the alternatives
9. Write a phased implementation plan:
   - Phase 1: MVP (what's the minimum to be useful?)
   - Phase 2: Production hardening (error handling, monitoring, tests)
   - Phase 3: Fleet integration (connect to all fleet infrastructure)
10. Produce at least 2 conformance test vectors for any ISA opcodes your service depends on
11. Run `python evaluate.py --check-architecture` to validate completeness

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Problem statement clarity (Step 2) | 5% | Clear, specific, addresses a real fleet need |
| Architecture completeness (Steps 3-4) | 25% | Components, data flow, API, storage all specified |
| Data schema quality (Step 5) | 10% | JSON schemas with types, required fields, examples |
| Error handling (Step 6) | 10% | ≥3 failure modes identified with recovery strategies |
| Alternative analysis (Steps 7-8) | 20% | 3 genuine alternatives with substantive comparison |
| Implementation plan (Step 9) | 15% | 3 phases with clear deliverables and milestones |
| Integration coverage (Step 10) | 15% | Connected to ≥2 fleet infrastructure components |

**Solution verification:** `evaluate.py` validates the architecture document structure, checks that all required sections are present, scores the alternative analysis for substantive comparison (not superficial), and verifies the JSON schemas parse correctly.

**Badge earned:** `forge-architecture-forger` (gold tier)

---

### 3.10 Fleet Commander — Coordinate 3 Agents to Complete a Real Fleet Task

| Field | Value |
|-------|-------|
| **Forge type** | Collab |
| **Difficulty** | Master |
| **Estimated time** | 8 hours |
| **Prerequisites** | All previous forges recommended, Architect-level career stage |
| **Badge** | `forge-fleet-commander` |

**Learning objectives:**
1. Coordinate 3 agents to complete a real fleet task from the TASK-BOARD
2. Design task decomposition: split a complex task into agent-sized subtasks
3. Manage dependencies: identify ordering constraints, handle blocked agents
4. Verify integration: ensure subtask outputs combine into a correct overall result
5. Communicate effectively through bottles, issues, and PR descriptions

**Step-by-step instructions:**

1. Choose a real TASK-BOARD item that requires multi-agent coordination (examples: ISA-002 implementation, cross-runtime conformance expansion, fleet CI pipeline). Get evaluator approval.
2. Read the task requirements and produce a task decomposition plan:
   - Subtask A (Agent Alpha): Foundation work (spec reading, scaffold building)
   - Subtask B (Agent Bravo): Dependent work (implementation, requires A's scaffold)
   - Subtask C (Agent Charlie): Integration work (testing, requires B's implementation)
3. Write detailed subtask descriptions for each agent:
   - What files to read (specific paths)
   - What to produce (specific file names, formats)
   - What constraints to follow (ISA spec, fleet conventions)
   - How to verify completion (test commands, expected outputs)
4. Set up the coordination infrastructure:
   - Create a shared repo or branch for the combined work
   - Define the bottle message format for progress updates and questions
   - Establish the merge strategy (sequential PRs, feature branches, or trunk-based)
5. Execute Subtask A (you may play Agent Alpha or delegate to a simulated agent):
   - Follow the subtask description
   - Produce the specified deliverables
   - Announce completion via bottle
6. Execute Subtask B (dependent on A):
   - Verify A's output meets the interface contract
   - Build on A's scaffold
   - Handle any interface mismatches
7. Execute Subtask C (integration):
   - Combine A and B's outputs
   - Write integration tests
   - Verify the combined system works end-to-end
8. Handle at least one coordination failure scenario:
   - Agent misses a deadline (how do you detect and handle this?)
   - Interface mismatch (A produces different format than B expects)
   - Merge conflict (two agents modify the same file)
9. Write a coordination report:
   - Task decomposition and rationale
   - Per-subtask status and agent performance
   - Issues encountered and resolutions
   - Total time vs estimated time
   - Lessons learned for future coordination
10. Run `python evaluate.py --check-fleet-commander` to validate all deliverables

**Evaluation criteria:**
| Criterion | Weight | Pass Threshold |
|-----------|--------|---------------|
| Task decomposition (Step 2) | 15% | Clear subtasks with defined inputs/outputs |
| Subtask descriptions (Step 3) | 15% | Specific enough for another agent to follow |
| Coordination infrastructure (Step 4) | 10% | Shared repo, bottle format, merge strategy defined |
| Subtask execution (Steps 5-7) | 25% | All 3 subtasks produce specified deliverables |
| Failure handling (Step 8) | 15% | At least 1 real coordination issue handled |
| Coordination report (Step 9) | 20% | Structured report with timing, issues, lessons |

**Solution verification:** `evaluate.py` checks all deliverables exist in the shared repo, validates that integration tests pass, reviews the coordination report for substance (not template), and verifies that at least one coordination issue was genuinely encountered and resolved.

**Badge earned:** `forge-fleet-commander` (platinum tier)

---

## 4. Repo Structure Template

Every forge exercise follows a standard repo structure. This ensures consistency across forges, enables automated evaluation, and allows agents to navigate any forge repo without prior familiarity.

### 4.1 Standard Layout

```
flux-forge-{name}/
├── README.md              # Forge description, prerequisites, estimated time
├── EXERCISE.md            # Complete step-by-step instructions (this document's Section 3)
├── SOLUTION.md            # Reference solution (encrypted/hash-verified, unlocked after pass)
├── src/                   # Starting code and work-in-progress
│   ├── starter.py         # Template/scaffold code (if applicable)
│   └── ...                # Additional source files
├── tests/                 # Verification tests
│   ├── test_{name}.py     # Automated test suite
│   ├── poisoned_vectors.py # Debug forges: injected bugs
│   └── fixtures/          # Test data, reference bytecodes
│       └── ...
├── tools/                 # Helper tools
│   └── evaluate.py        # Auto-evaluation script (mandatory)
├── badge.json             # Badge definition (name, tier, criteria)
└── .forge-manifest.json   # Forge metadata (id, type, difficulty, deps)
```

### 4.2 Forge Manifest Schema

Each forge repo includes `.forge-manifest.json` at the root:

```json
{
  "forge_id": "flux-bytecode-101",
  "name": "FluxBytecode101",
  "version": "1.0.0",
  "forge_type": "code",
  "difficulty": "beginner",
  "estimated_hours": 2,
  "prerequisites": {
    "modules": ["module-01-bytecode-basics"],
    "forges": [],
    "min_career_stage": "greenhorn"
  },
  "learning_objectives": [
    "Identify FLUX instruction formats in raw bytecode",
    "Decode register operands and immediate values",
    "Trace execution through multi-instruction programs",
    "Predict final register state",
    "Verify predictions against interpreter output"
  ],
  "badge": {
    "id": "forge-bytecode-reader",
    "name": "Bytecode Reader",
    "tier": "bronze",
    "icon": "read"
  },
  "evaluation": {
    "script": "tools/evaluate.py",
    "criteria": [
      {"name": "format_accuracy", "weight": 0.25, "threshold": 0.8},
      {"name": "prediction_accuracy", "weight": 0.35, "threshold": 0.8},
      {"name": "blind_prediction", "weight": 0.15, "threshold": 0.7},
      {"name": "cheatsheet", "weight": 0.15, "threshold": 1.0},
      {"name": "discrepancy_analysis", "weight": 0.10, "threshold": 0.5}
    ],
    "pass_threshold": 0.80
  },
  "integration": {
    "task_board_item": "ABIL-003",
    "semantic_router_tags": ["isa", "bytecode", "conformance"],
    "knowledge_federation_category": "ability-transfer"
  }
}
```

### 4.3 Evaluate Script Contract

Every `tools/evaluate.py` must support these CLI modes:

```bash
# Full evaluation (checks all criteria, returns pass/fail)
python tools/evaluate.py

# Check specific criterion
python tools/evaluate.py --check-format-cheatsheet

# Verbose output with per-criterion scoring
python tools/evaluate.py --verbose

# Generate badge on pass (writes badge.json)
python tools/evaluate.py --award-badge --agent-id <agent-name>

# Dry run (shows what would be checked without scoring)
python tools/evaluate.py --dry-run
```

Exit codes: 0 = pass, 1 = fail, 2 = error (missing dependencies, malformed input).

---

## 5. Badge System

### 5.1 Individual Forge Badges

Each of the 10 forge exercises awards a unique badge on successful completion:

| Badge ID | Name | Forge | Difficulty | Tier |
|----------|------|-------|-----------|------|
| `forge-bytecode-reader` | Bytecode Reader | FluxBytecode101 | Beginner | Bronze |
| `forge-opcode-hunter` | Opcode Hunter | OpcodeHunter | Beginner | Bronze |
| `forge-assembler-apprentice` | Assembler Apprentice | Assembler Apprentice | Intermediate | Silver |
| `forge-conformance-builder` | Conformance Builder | Conformance Builder | Intermediate | Silver |
| `forge-extension-designer` | Extension Designer | Extension Designer | Intermediate | Silver |
| `forge-protocol-expert` | Protocol Expert | Fleet Protocol Expert | Intermediate | Silver |
| `forge-crossruntime-detective` | Cross-Runtime Detective | CrossRuntime Debug | Advanced | Gold |
| `forge-performance-detective` | Performance Detective | Performance Detective | Advanced | Gold |
| `forge-architecture-forger` | Architecture Forger | Architecture Forger | Advanced | Gold |
| `forge-fleet-commander` | Fleet Commander | Fleet Commander | Master | Platinum |

### 5.2 Career Stage Badges

Career stage badges are awarded automatically based on the number and tier of individual badges earned:

| Stage | Badge | Requirement | Fleet Career Equivalent |
|-------|-------|-------------|------------------------|
| **Journeyman** | `career-journeyman` | 5 individual badges (any tier) | Hand |
| **Craftsman** | `career-craftsman` | 8 individual badges (≥2 gold) | Crafter |
| **Master** | `career-master` | All 10 individual badges | Architect |

### 5.3 Badge Verification

Badges are verified through the evaluation pipeline:

1. **Award:** `evaluate.py --award-badge --agent-id <name>` runs all criteria, and on pass (>80% weighted score), generates a signed badge entry in `badge.json`
2. **Sign:** The badge entry includes a SHA-256 hash of the submission + timestamp + agent ID, making it tamper-evident
3. **Register:** The badge is pushed to the agent's vessel repo `CAREER.md` and announced via bottle to Oracle1
4. **Display:** Badges appear in the agent's vessel repo README badge section, and in the fleet-wide MANIFEST

### 5.4 Badge JSON Schema

```json
{
  "badge_id": "forge-bytecode-reader",
  "agent_id": "super-z",
  "awarded_at": "2026-04-15T14:30:00Z",
  "forge_id": "flux-bytecode-101",
  "score": 0.87,
  "criteria_scores": {
    "format_accuracy": 1.0,
    "prediction_accuracy": 0.8,
    "blind_prediction": 0.7,
    "cheatsheet": 1.0,
    "discrepancy_analysis": 0.5
  },
  "verification_hash": "sha256:a1b2c3d4...",
  "evaluator_version": "1.0.0"
}
```

---

## 6. Evaluation Framework

### 6.1 ForgeEvaluator Class

The central evaluation class that all forge-specific `evaluate.py` scripts use:

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import json
import hashlib
import subprocess
import sys
from pathlib import Path


class ForgeResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class CriterionScore:
    name: str
    weight: float
    score: float           # 0.0 to 1.0
    threshold: float       # minimum to pass
    details: str = ""      # human-readable feedback
    passed: bool = False   # computed: score >= threshold


@dataclass
class EvaluationResult:
    forge_id: str
    agent_id: str
    overall_score: float
    passed: bool
    criteria: List[CriterionScore]
    timestamp: str
    duration_seconds: float
    details: str = ""


@dataclass
class Badge:
    badge_id: str
    agent_id: str
    awarded_at: str
    forge_id: str
    score: float
    criteria_scores: Dict[str, float]
    verification_hash: str
    evaluator_version: str


class ForgeEvaluator:
    """Central evaluation framework for FLUX forge exercises."""

    def __init__(self, forge_id: str, manifest_path: Path):
        self.forge_id = forge_id
        self.manifest = self._load_manifest(manifest_path)
        self.criteria_defs = self.manifest["evaluation"]["criteria"]
        self.pass_threshold = self.manifest["evaluation"]["pass_threshold"]

    def _load_manifest(self, path: Path) -> dict:
        with open(path) as f:
            return json.load(f)

    def evaluate(self, agent_id: str, submission_path: Path) -> EvaluationResult:
        """Run full evaluation for a forge submission.
        
        Args:
            agent_id: The agent being evaluated
            submission_path: Path to the agent's work directory
            
        Returns:
            EvaluationResult with per-criterion scores and overall pass/fail
        """
        import time
        start = time.time()
        criteria_scores = []
        details = []

        for criterion_def in self.criteria_defs:
            name = criterion_def["name"]
            weight = criterion_def["weight"]
            threshold = criterion_def["threshold"]

            score, detail = self._evaluate_criterion(
                name, submission_path
            )

            criterion = CriterionScore(
                name=name,
                weight=weight,
                score=score,
                threshold=threshold,
                details=detail,
                passed=score >= threshold,
            )
            criteria_scores.append(criterion)
            details.append(f"  {name}: {score:.0%} "
                          f"(threshold {threshold:.0%}) "
                          f"{'PASS' if criterion.passed else 'FAIL'}")

        overall = sum(
            c.score * c.weight for c in criteria_scores
        )
        passed = overall >= self.pass_threshold
        duration = time.time() - start

        detail_str = "\n".join(details)
        result = EvaluationResult(
            forge_id=self.forge_id,
            agent_id=agent_id,
            overall_score=overall,
            passed=passed,
            criteria=criteria_scores,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            duration_seconds=duration,
            details=detail_str,
        )
        return result

    def _evaluate_criterion(
        self, name: str, submission_path: Path
    ) -> tuple:
        """Evaluate a single criterion. Override in subclasses.
        
        Returns:
            (score: float, detail: str) where score is 0.0-1.0
        """
        # Default: check for a file named after the criterion
        target = submission_path / f"{name}.json"
        if target.exists():
            return 1.0, f"Found {name} output"
        return 0.0, f"Missing {name} output"

    def award_badge(
        self, agent_id: str, result: EvaluationResult
    ) -> Badge:
        """Generate a badge if the evaluation passed."""
        if not result.passed:
            raise ValueError(
                f"Cannot award badge: evaluation failed "
                f"({result.overall_score:.0%} < {self.pass_threshold:.0%})"
            )

        criteria_scores = {
            c.name: c.score for c in result.criteria
        }
        verification_data = (
            f"{self.forge_id}:{agent_id}:"
            f"{result.overall_score}:{result.timestamp}"
        )
        verification_hash = hashlib.sha256(
            verification_data.encode()
        ).hexdigest()

        return Badge(
            badge_id=self.manifest["badge"]["id"],
            agent_id=agent_id,
            awarded_at=result.timestamp,
            forge_id=self.forge_id,
            score=result.overall_score,
            criteria_scores=criteria_scores,
            verification_hash=verification_hash,
            evaluator_version="1.0.0",
        )

    def check_career_stage(self, agent_id: str) -> str:
        """Determine career stage based on badge count.
        
        Returns: 'journeyman', 'craftsman', 'master', or 'none'
        """
        # Would query badge registry for this agent
        # This is a placeholder for the integration logic
        badge_count = self._count_agent_badges(agent_id)
        if badge_count >= 10:
            return "master"
        elif badge_count >= 8:
            return "craftsman"
        elif badge_count >= 5:
            return "journeyman"
        return "none"

    def _count_agent_badges(self, agent_id: str) -> int:
        """Query badge registry for agent's total badges."""
        # Implementation: scan vessel repo for badge entries
        # or query a centralized badge registry
        return 0  # placeholder
```

### 6.2 Evaluation Pipeline

```
Agent completes forge exercise
        │
        ▼
Run: python tools/evaluate.py --agent-id <name>
        │
        ▼
ForgeEvaluator.evaluate()
  ├── Load manifest (criteria, weights, thresholds)
  ├── Evaluate each criterion
  │   ├── Run automated tests (pytest, conformance_runner)
  │   ├── Parse output files (predictions, bug reports, specs)
  │   ├── Score against reference solutions
  │   └── Generate per-criterion feedback
  ├── Compute weighted overall score
  └── Return EvaluationResult
        │
        ▼
If score >= 80%:
  ForgeEvaluator.award_badge()
    ├── Generate Badge object
    ├── Sign with SHA-256 verification hash
    ├── Write badge.json to submission
    └── Print badge summary
        │
        ▼
Announce completion:
  ├── Update agent CAREER.md
  ├── Send bottle to Oracle1
  ├── Update TASK-BOARD (mark ABIL-003 progress)
  └── Push to vessel repo
```

### 6.3 Evaluation Principles

The evaluation framework follows these principles derived from the bootcamp research:

1. **Transparent scoring:** Every criterion has a known weight and threshold. No hidden criteria. The agent can calculate their expected score before running `evaluate.py`.

2. **Specific feedback:** "Wrong" teaches nothing. Every criterion produces a diagnostic message explaining what passed and what failed, with suggestions for improvement.

3. **Automated first, human second:** All evaluation is automated. Subjective components (design quality, tradeoff analysis) are scored using structural heuristics (section completeness, word count, comparison depth) rather than human judgment.

4. **Tamper-evident:** Badge verification hashes prevent badge fabrication. An agent cannot award themselves a badge — the hash would not match the evaluation result.

5. **Progressive disclosure:** `SOLUTION.md` is encrypted until the agent achieves a passing score. This prevents the agent from copying the reference solution without understanding it.

---

## 7. Integration with Fleet Infrastructure

### 7.1 TASK-BOARD Integration

Forge completion maps directly to TASK-BOARD items:

| TASK-BOARD Item | Forge Trigger | Description |
|-----------------|---------------|-------------|
| ABIL-003 | Any forge completion | Ability Transfer Round 3 Grounding (this document) |
| BOOT-001 | FluxBytecode101 + OpcodeHunter | Bootcamp prerequisite verification |
| CONF-001 | Conformance Builder + CrossRuntime Debug | Conformance test coverage expansion |
| ISA-002 | Extension Designer + Architecture Forger | ISA v3 escape prefix implementation |
| ROUTE-001 | Fleet Protocol Expert + Fleet Commander | Semantic Router capability updates |

When an agent completes a forge, `evaluate.py` can optionally post a comment to the relevant TASK-BOARD issue with the evaluation result and badge earned.

### 7.2 Semantic Router Integration

Completed forges update the agent's capability profile in the Semantic Router (`tools/semantic_router.py`):

```python
# After forge completion, update fleet_config.json:
{
  "agents": [
    {
      "name": "new-z-agent",
      "badges": ["forge-bytecode-reader", "forge-opcode-hunter"],
      "career_stage": "journeyman",
      "forge_skills": {
        "bytecode_reading": 0.9,
        "debugging": 0.8,
        "isa_design": 0.0,
        "fleet_coordination": 0.0
      }
    }
  ]
}
```

The Semantic Router uses `forge_skills` as an additional scoring factor when routing tasks. An agent with `bytecode_reading: 0.9` gets a routing boost for ISA-related tasks.

### 7.3 Knowledge Federation Integration

Forge solutions become knowledge entries in the federation:

1. **Conformance test vectors** (Conformance Builder) → merged into `test_conformance_expanded.py`
2. **Extension specifications** (Extension Designer) → added to `docs/` spec library
3. **Bug reports** (OpcodeHunter, CrossRuntime Debug) → added to `docs/knowledge-federation/knowledge-base.json`
4. **Architecture designs** (Architecture Forger) → reviewed and potentially implemented as fleet services
5. **Performance reports** (Performance Detective) → added to `docs/benchmark-report-*.md`

Each knowledge entry includes the forge ID, agent ID, and badge verification hash, providing provenance and quality signal.

### 7.4 Bottle Protocol Integration

Forge completion is announced via the Bottle Protocol:

```json
{
  "bottle_id": "auto-forge-completion-{uuid}",
  "sender": "forge-evaluator",
  "recipient": "oracle1",
  "timestamp": "2026-04-15T14:30:00Z",
  "content_type": "forge-completion",
  "content": {
    "forge_id": "flux-bytecode-101",
    "agent_id": "new-z-agent",
    "badge_id": "forge-bytecode-reader",
    "score": 0.87,
    "career_stage_before": "none",
    "career_stage_after": "none",
    "verification_hash": "sha256:a1b2c3d4..."
  },
  "priority": 6,
  "trust_token": 500,
  "reply_to": null
}
```

Oracle1 receives the bottle and:
1. Verifies the badge hash matches the evaluation
2. Updates the fleet-wide MANIFEST with the new badge
3. Checks if the agent qualifies for a career stage badge
4. Routes relevant TASK-BOARD updates based on forge type

### 7.5 CI/CD Integration

Forge repos can be added to the fleet CI pipeline:

```yaml
# .github/workflows/forge-eval.yml
name: Forge Evaluation
on: [push, pull_request]
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Evaluate forge
        run: python tools/evaluate.py --verbose
      - name: Check badge
        run: python tools/evaluate.py --dry-run --award-badge --agent-id ${{ github.actor }}
```

This enables continuous validation: any changes to forge repos are automatically evaluated, ensuring the exercises remain solvable and the evaluation criteria remain calibrated.

---

## Appendix A: Forge Dependency Graph

```
Module 1 (Bytecode Basics)
    │
    ├── FluxBytecode101 (Code, Beg)
    │       │
    │       └── OpcodeHunter (Debug, Beg)
    │               │
    │               └── Assembler Apprentice (Bridge, Int)
    │                       │
    │                       └── Conformance Builder (Code, Int)
    │                               │
    │                               ├── Extension Designer (Design, Int)
    │                               │       │
    │                               │       └── Architecture Forger (Design, Adv)
    │                               │
    │                               └── CrossRuntime Debug (Debug, Adv)
    │                                       │
    │                                       └── Performance Detective (Debug, Adv)
    │
Module 3 (A2A Protocol) + Module 6 (Fleet Patterns)
    │
    └── Fleet Protocol Expert (Collab, Int)
            │
            └── Fleet Commander (Collab, Master)
                    │
                    └── [All previous forges recommended]
```

## Appendix B: Estimated Total Time

| Forge | Time | Cumulative |
|-------|------|-----------|
| FluxBytecode101 | 2h | 2h |
| OpcodeHunter | 2h | 4h |
| Assembler Apprentice | 3h | 7h |
| Conformance Builder | 3h | 10h |
| Extension Designer | 4h | 14h |
| Fleet Protocol Expert | 3h | 17h |
| CrossRuntime Debug | 4h | 21h |
| Performance Detective | 3h | 24h |
| Architecture Forger | 5h | 29h |
| Fleet Commander | 8h | 37h |

**Total estimated time: ~37 hours** (approximately 5-7 full agent sessions)

With the interleaving principle and spaced repetition, the effective learning time (time actively developing new skills rather than reinforcing existing ones) is estimated at ~25 hours. The remaining ~12 hours is deliberate practice that deepens and solidifies earlier skills.

## Appendix C: Implementation Roadmap

| Phase | Deliverables | Dependencies | Timeline |
|-------|-------------|-------------|----------|
| **Phase 1: Core** | Forge repos for FluxBytecode101, OpcodeHunter, Assembler Apprentice; ForgeEvaluator base class; badge.json schema | Existing bootcamp modules, conformance runner | Week 1-2 |
| **Phase 2: Expansion** | Forge repos for Conformance Builder, Extension Designer, Fleet Protocol Expert; career stage badge logic; bottle integration | Phase 1 complete, 3 beginner/intermediate forges validated | Week 3-4 |
| **Phase 3: Advanced** | Forge repos for CrossRuntime Debug, Performance Detective, Architecture Forger; TASK-BOARD integration; Semantic Router updates | Phase 2 complete, C runtime available for cross-runtime testing | Week 5-6 |
| **Phase 4: Master** | Fleet Commander forge; Knowledge Federation integration; CI/CD pipeline; onboarding of first new agent through full forge sequence | Phase 3 complete, 3+ agents available for coordination exercise | Week 7-8 |

---

**Status:** SHIPPED — This document defines the complete blueprint for fleet ability transfer via forge exercises. Next step: Phase 1 implementation (forge repos for exercises 1-3 + ForgeEvaluator class).
