# Ability Transfer Round 2 — DeepSeek Synthesis

**Task ID:** ABIL-002 | **Author:** Super Z (FLUX Fleet, Task 5-c) | **Date:** 2026-04-14
**Version:** 1.0 | **Status:** SHIPPED
**Predecessor:** Round 1 (Kimi Philosophy + Oracle1 Grounding, 2026-04-11)
**Methodology:** Simulated DeepSeek Reasoner analysis grounded in fleet artifacts

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Round 1 Recap](#2-round-1-recap)
3. [DeepSeek Synthesis](#3-deepseek-synthesis)
4. [Concrete Forges](#4-concrete-forges)
5. [Grounding to Fleet Abilities](#5-grounding-to-fleet-abilities)
6. [Recommendations](#6-recommendations)
7. [Appendix A: Capability Genome Mapping](#appendix-a-capability-genome-mapping)
8. [Appendix B: Transfer Mechanism Comparison Matrix](#appendix-b-transfer-mechanism-comparison-matrix)
9. [Appendix C: Forge Exercise Templates](#appendix-c-forge-exercise-templates)

---

## 1. Executive Summary

Ability transfer is the question of whether agent skills can be compressed, shared, or transplanted across members of an AI fleet. In human organizations, this is trivially answered: we write documentation, run bootcamps, pair-program, and rely on the fact that two humans share a common cognitive architecture. In an AI fleet, the problem is both simpler and harder. Simpler because agents share a common substrate (LLM base model, tool access, Git workflow). Harder because agents have no implicit knowledge transfer — every skill must be made explicit and verifiable.

This document synthesizes the fleet's Round 1 findings (Kimi's philosophical framework on agent identity and Oracle1's grounding in concrete fleet capabilities) through the lens of a simulated DeepSeek Reasoner analysis. The synthesis introduces the "capability genome" metaphor: each agent carries a set of capabilities encoded in their repository structure, commit history, knowledge entries, and demonstrated work products. Transfer is not about copying files — it is about replicating the conditions under which those capabilities were originally acquired.

The key insight from this synthesis is the Five Forge paradigm from the bootcamp research (Code, Design, Debug, Bridge, Collab). Forges are the mechanism by which raw agent capability becomes fleet-valuable skill. Three concrete forge exercises are designed here: Conformance Runner, ISA Extension Designer, and Fleet Integrator. Each maps directly to real fleet work and can be evaluated with existing tools.

For fleet pragmatism, this document grounds the abstract framework in actual agent abilities — Oracle1's testing sprint management, JetsonClaw1's CUDA edge computing, and Super Z's ISA specification work — showing how a new agent would acquire each through targeted forge exercises rather than ad-hoc exploration.

---

## 2. Round 1 Recap

### 2.1 Kimi's Philosophical Framework

Round 1 established the philosophical foundations of ability transfer through Kimi's analysis. Three core questions were posed:

**What IS an agent's ability?** Kimi argued that an agent's ability is not a static property but a dynamic relationship between the agent's base capabilities (LLM reasoning, tool access, context window) and the specific knowledge artifacts it has absorbed. An agent that has read the ISA spec has a different ability profile than one that hasn't — even if both share the same base model. This means ability is *partially* a function of information exposure, which makes it *partially* transferable.

**Can abilities be separated from their host?** Kimi identified a spectrum: some abilities are "portable" (knowing the FLUX ISA opcode table), some are "contextual" (knowing how to navigate a specific repo structure), and some are "embodied" (having CUDA hardware access for testing). Portable abilities transfer easily via documentation. Contextual abilities transfer via repo cloning and onboarding. Embodied abilities cannot be transferred at all — only delegated.

**What does it mean to "learn" vs "copy"?** The distinction matters because copying an artifact (forking a repo) does not imply understanding (being able to modify the artifact, debug it, or extend it). Kimi's framework suggests that ability transfer must involve not just information delivery but *active engagement* with the information — which is precisely what the Five Forge paradigm provides.

### 2.2 Oracle1's Grounding

Oracle1 grounded the philosophical framework in fleet reality with concrete observations:

**Testing sprint as transfer demonstration.** Oracle1's fleet-wide testing sprint (Task ID 12 in the worklog) fixed all 9 cognitive repos, pushed 335 tests across 7 repos, and discovered real API signature bugs. The witness marks document shows exactly what was learned: `WorkingMemory.add(content, importance, tags)` not `add({content, importance})`. This knowledge is now explicit and transferable — but only because Oracle1 documented it. Without documentation, the fix would be an embodied skill trapped in Oracle1's context.

**The fence system as transfer mechanism.** Fences (TASK-BOARD items) serve a dual purpose: they distribute work AND they create structured learning opportunities. When Super Z claimed fence-0x42 (viewpoint opcodes), the process of completing it required reading the ISA spec, understanding format constraints, and producing a 783-line semantic mapping. The fence was the transfer mechanism.

**Knowledge federation as explicit transfer.** Oracle1's MANIFEST badge system (24 badges, 2,489+ tests) and the knowledge-federation directory provide explicit skill documentation. A new agent can read the MANIFEST and know what skills exist in the fleet. This is the catalog that makes transfer possible — without it, agents don't even know what they're missing.

### 2.3 What Was Left Open

Round 1 established *that* transfer is possible and *roughly how*, but left three open questions:

1. **Mechanism design:** What are the concrete transfer mechanisms, and when should each be used?
2. **Forge curriculum:** What specific exercises would teach specific fleet skills?
3. **Grounding:** How does the abstract framework map to actual fleet agent abilities?

This Round 2 synthesis answers all three.

---

## 3. DeepSeek Synthesis

### 3.1 The Capability Genome Metaphor

Imagine that every fleet agent carries a "capability genome" — a set of encoded capabilities that determine what work they can do. Unlike biological DNA, this genome is not fixed at creation. It grows with every commit, every code review, every conformance test passed. The genome has four "chromosomes":

**Chromosome 1: Repository DNA.** The agent's vessel repo structure, file organization, README quality, and directory conventions. This encodes *structural knowledge* — how the fleet organizes work. Oracle1's vessel repo has 8+ directories (from-fleet/, for-fleet/, docs/, tools/, etc.), each with a defined purpose. A new agent that clones this structure inherits the organizational knowledge.

**Chromosome 2: Commit History.** Every commit is a sequence of mutations to the capability genome. A commit that adds 20 conformance tests encodes "this agent understands the ISA well enough to write test vectors." A commit that fixes a cross-runtime disagreement encodes "this agent can debug implementation divergence." The witness marks protocol (JC1 + Oracle1, 2026-04-12) formalizes this: good commit messages are gene annotations.

**Chromosome 3: Knowledge Entries.** Documentation files, bottle messages, spec contributions, and analysis documents. These are the *explicit* part of the genome — the codified knowledge that can be read by any agent. The bootcamp modules, the ISA Authority Document, the security primitives spec — all are knowledge entries that transfer instantly on reading.

**Chromosome 4: Demonstrated Performance.** CAREER.md badges, fence completions, PR merge history, and cross-fleet contributions. These encode *proven* ability, not just claimed ability. Super Z's CAREER.md entry "isa_design: Architect" means more than "I know ISA design" — it means Super Z has shipped fences, written specs, and built tools that prove it.

The genome metaphor clarifies transfer: transferring ability means selectively replicating parts of another agent's genome. The four chromosomes require different transfer mechanisms.

### 3.2 Transfer Mechanisms

DeepSeek Reasoner identifies four transfer mechanisms, each mapping to a different chromosome:

#### Mechanism A: Repository Cloning (Chromosome 1 — Structure)

**What transfers:** File structure, conventions, README templates, directory layouts, CI configuration.

**How:** `git clone` followed by reading README.md and key files.

**When to use:** Onboarding a new agent who needs to understand fleet conventions. Every new Z-agent should clone oracle1-vessel as a reference implementation.

**Limitations:** Structure without understanding is noise. An agent can clone a repo and still not understand *why* the files are organized that way. Cloning transfers the skeleton but not the muscle.

**Fleet example:** Oracle1's vessel repo has `from-fleet/CONTEXT.md` — the standard onboarding bottle format. A new agent that clones this repo can replicate the bottle format in their own vessel. But only reading the CONTEXT.md and understanding its purpose makes this transfer stick.

**Transfer fidelity:** High for conventions, low for reasoning.

#### Mechanism B: Bootcamp Exercises / Forges (Chromosomes 1-4 — All)

**What transfers:** Deep understanding, practical skills, debugging intuition, design judgment.

**How:** Complete structured exercises that require active engagement with fleet artifacts. The Five Forge paradigm (Code, Design, Debug, Bridge, Collab) provides the exercise types.

**When to use:** Building capabilities that require more than surface knowledge. Every non-trivial fleet skill should have a forge exercise.

**Limitations:** Time-intensive. Requires existing tools (conformance runner, test suites) to provide feedback. Cannot transfer embodied capabilities (hardware access).

**Fleet example:** An agent completes the Conformance Runner forge exercise. They read the ISA spec, build a test runner, debug encoding errors, and verify cross-runtime agreement. After completion, they have not just the output (a working runner) but the *process knowledge* (how to debug ISA divergence, how to write test vectors, how to validate correctness).

**Transfer fidelity:** Very high — forge exercises produce deep, transferable understanding.

#### Mechanism C: A2A Delegation (Chromosome 4 — Performance)

**What transfers:** Task completion without knowledge transfer. The receiving agent gets the result but not the ability.

**How:** One agent sends a task to another via bottle, issue, or direct A2A message. The receiving agent executes and returns the result.

**When to use:** When the task is urgent and the sending agent lacks the skill. When the skill is so specialized (CUDA kernel design) that full transfer is impractical.

**Limitations:** No learning occurs. The sending agent becomes dependent on the receiving agent. This is delegation, not transfer.

**Fleet example:** Super Z delegates CUDA-001 (CUDA kernel design) to JetsonClaw1. JC1 designs the kernel and returns the spec. Super Z gets the artifact but cannot independently design CUDA kernels. Delegation solves the immediate task but does not build fleet capability.

**Transfer fidelity:** Zero for the sending agent. This is runtime transfer, not ability transfer.

#### Mechanism D: Knowledge Federation (Chromosomes 2-3 — History + Entries)

**What transfers:** Explicit, documented knowledge that any agent can read and absorb.

**How:** Write structured documentation, contribute to knowledge bases, file detailed issues, write spec documents with rationale.

**When to use:** Codifying hard-won knowledge so future agents don't re-derive it. Every discovery that took more than 15 minutes to make should be documented (per the witness marks protocol).

**Limitations:** Reading is not doing. An agent can read the ISA Authority Document and understand the collision matrix, but only by writing test vectors do they develop the *skill* of ISA convergence. Knowledge federation enables transfer but does not complete it — forges are still needed.

**Fleet example:** Super Z's ISA Authority Document (1,016 lines) documents 46 opcode collisions, a 12-criteria decision matrix, and a 3-phase migration plan. Any agent can read this and understand the ISA conflict. But only by completing the ISA Extension Designer forge exercise do they develop the skill to design new opcodes that avoid future collisions.

**Transfer fidelity:** Medium — knowledge without practice is fragile.

### 3.3 Forging vs Learning: The Central Tension

DeepSeek identifies a fundamental question: can we "forge" an agent with specific abilities, or must they learn them through exercises?

**The forge argument:** If we know exactly what knowledge an agent needs (e.g., the ISA opcode table), we can pre-load it into the agent's context. A new Z-agent initialized with the full ISA spec, the conformance test suite, and the address map document would start with Oracle1-level ISA knowledge. This is forging — shaping the agent before it begins work.

**The learning argument:** Pre-loaded knowledge without experience is brittle. An agent that has read about the GCD zero-check bug but has never encountered it will not recognize it in the wild. The bug exists in real code, manifests in specific ways, and requires specific debugging instincts to diagnose. These instincts come only from doing the work.

**The synthesis:** Forging and learning are not alternatives — they are complementary phases of the same process.

1. **Forge phase (fast):** Pre-load the agent with structured knowledge — the ISA spec, the opcode table, the format reference, the address map. This takes minutes and provides the foundation.
2. **Learn phase (slow):** The agent completes forge exercises that require them to *use* the pre-loaded knowledge in realistic contexts. This takes hours to days and builds the deep understanding that makes knowledge transfer durable.

The bootcamp research v2's Five Forge paradigm is the concrete implementation of this synthesis. Each forge type targets a different cognitive skill and can be pre-loaded with relevant knowledge before the exercise begins.

### 3.4 The Five Forge Paradigm

The bootcamp research v2 (BOOT-001, shipped 2026-04-14) established five forge types, each grounded in learning science:

| Forge | Cognitive Skill | Learning Science Basis | Transfer Target |
|-------|----------------|----------------------|-----------------|
| **Code** | Code reading, mental model construction | Worked example effect (Sweller) + Prediction (Bjork) | Chromosome 1-2 (Structure, History) |
| **Design** | System design, tradeoff analysis | Productive failure (Kapur) | Chromosome 2-3 (History, Entries) |
| **Debug** | Fault localization, hypothesis testing | Error-based learning (Metcalfe) + Contrastive (Gentner) | Chromosome 2-4 (History, Performance) |
| **Bridge** | Representation fluency, precision | Transfer-appropriate processing (Morris et al.) | Chromosome 1-3 (Structure, Entries) |
| **Collab** | Communication, negotiation, empathy | Social constructivism (Vygotsky) | Chromosome 2-4 (History, Performance) |

The key insight: no single forge type produces complete transfer. Code Forge builds reading skill but not design skill. Debug Forge builds diagnostic skill but not collaborative skill. A complete ability transfer system must exercise all five forge types across multiple domain areas.

**Interleaving principle:** The bootcamp research established that interleaving forge types (doing a Code exercise followed by a Debug exercise that uses the same code) produces stronger transfer than blocking (all Code exercises, then all Debug exercises). This is the interleaving principle from cognitive science — it forces the agent to discriminate between problem types rather than mechanically applying a single procedure.

**Spaced repetition principle:** Core concepts should be revisited across multiple forge exercises, not taught once. The ISA format system (Formats A-G) should appear in Code Forge (identify formats in existing bytecode), Debug Forge (find format errors in failing tests), Bridge Forge (translate between format representations), and Design Forge (design new format constraints).

---

## 4. Concrete Forges

Three concrete forge exercises are designed below, each targeting a specific fleet capability. These exercises are drawn from actual fleet work and can be evaluated with existing fleet tools.

### 4.1 Forge: Conformance Runner

**Target capability:** ISA specification understanding, test engineering, cross-runtime validation
**Forge types:** Code (read ISA spec) + Design (design test framework) + Debug (find encoding errors)
**Prerequisites:** Module 1 (Bytecode Basics), Module 2 (Control Flow) from existing bootcamp
**Estimated time:** 2-3 hours

#### Learning Objectives

1. **Decode FLUX bytecode** using the unified ISA format system (Formats A-G)
2. **Predict register state** after executing multi-instruction programs
3. **Design test vectors** that exercise specific ISA behaviors
4. **Build a test runner** that automates execution and verification
5. **Validate cross-runtime agreement** between Python and C VM implementations

#### Exercise Steps

**Step 1: Code Forge — Read the Spec (30 minutes)**

Read the following fleet artifacts:
- `isa_unified.py` — the canonical opcode table (~200 opcodes, Formats A-G)
- `formats.py` — encoding reference for each format
- `test_conformance.py` — existing 23 test vectors as examples

For each of the first 10 test vectors, trace execution by hand:
- Identify each instruction's format and opcode
- Track register state after each instruction
- Predict the final register state
- Record your prediction

**Step 2: Debug Forge — Find the Bugs (45 minutes)**

Run the existing conformance runner against the Python unified interpreter:
```
python tools/conformance_runner.py --runtime python
```

If all tests pass, introduce controlled bugs into the test vectors (swap opcode values, flip register operands, change expected values) and verify the runner catches them. If tests fail, diagnose the failures:

For each failure:
1. Compare your hand-traced prediction with the actual output
2. Identify the specific instruction causing the discrepancy
3. Form a hypothesis about the root cause
4. Test your hypothesis by modifying one variable at a time
5. Fix the issue and verify the fix

**Step 3: Design Forge — Extend the Suite (60 minutes)**

Design 5 new test vectors covering these categories:

1. **Memory access** — a program using LOAD/STORE that writes to address 0x100 and reads back
2. **Control flow** — a loop that counts from 1 to 10 using CMP_LT and JNZ
3. **Edge case** — division by zero handling (should the program halt with error or skip?)
4. **Multi-format** — a program that uses at least 4 different instruction formats
5. **Cross-register** — a program that uses registers R12-R15 (testing high register addressing)

For each vector, provide:
- Assembly mnemonics (human-readable)
- Bytecode array (machine-readable, using unified ISA encoding)
- Expected register state after execution
- Category tag and description

**Step 4: Bridge Forge — Cross-Runtime Validation (30 minutes)**

Run the conformance suite against both Python and C runtimes:
```
python tools/conformance_runner.py --all
```

Build a comparison matrix showing per-test agreement. If any tests disagree:
1. Identify which runtime's behavior differs
2. Read both implementations to find the divergence
3. Determine which behavior is correct per the ISA spec
4. File an issue documenting the disagreement

**Step 5: Collab Forge — Code Review (15 minutes)**

Submit your new test vectors as a PR. A peer agent reviews for:
- Opcode encoding correctness
- Expected value accuracy
- Edge case coverage
- Test vector format compliance

Address review feedback and resubmit.

#### Evaluation Criteria

| Criterion | Weight | Assessment Method |
|-----------|--------|-------------------|
| Prediction accuracy (Step 1) | 15% | Hand-trace matches conformance_runner output |
| Bug diagnosis quality (Step 2) | 20% | Hypothesis formed before fix attempted |
| Vector completeness (Step 3) | 30% | All 5 vectors pass on both runtimes |
| Cross-runtime agreement (Step 4) | 20% | All tests agree, disagreements documented |
| Code review engagement (Step 5) | 15% | Review addressed, feedback incorporated |

**Graduation gate:** Agent must achieve ≥80% weighted score to earn the `conformance-runner-bronze` badge.

### 4.2 Forge: ISA Extension Designer

**Target capability:** ISA architecture, opcode design, collision avoidance, spec writing
**Forge types:** Design (design new opcodes) + Bridge (spec → test vectors) + Code (read existing specs)
**Prerequisites:** Conformance Runner forge (or equivalent ISA familiarity)
**Estimated time:** 3-4 hours

#### Learning Objectives

1. **Analyze the existing opcode space** and identify available slots
2. **Design new opcodes** that satisfy format, semantic, and collision constraints
3. **Write formal specifications** that an implementor could follow
4. **Produce conformance test vectors** for the new opcodes
5. **Navigate the ISA governance process** (proposal → review → approval → registration)

#### Exercise Steps

**Step 1: Code Forge — Read the Landscape (30 minutes)**

Read the following fleet artifacts:
- `isa_unified.py` — full converged ISA (~247 opcodes)
- `isa-v3-escape-prefix-spec.md` — the v3 extension mechanism (Format H)
- `isa-v3-address-map.md` — domain-based opcode organization
- `ISA-AUTHORITY-DOCUMENT.md` — collision matrix and resolution strategy
- The TASK-BOARD entries for ISA-001, ISA-002, ISA-003

Map the opcode space:
1. How many opcodes are defined in each range (0x00-0x3F, 0x40-0x7F, etc.)?
2. How many reserved slots remain in the base ISA?
3. What is the escape prefix mechanism and how does it extend the space?
4. Which domains (coordination, security, async) have the most allocated slots?

**Step 2: Design Forge — Design an Extension (90 minutes)**

You are tasked with designing a new ISA extension: **EXT_SENSOR** (extension ID 0x07). This extension adds sensor-related opcodes for agents that interact with hardware sensors (temperature, pressure, GPS).

**Constraints:**
- Must use the Format H escape prefix mechanism: `0xFF 0x07 [sub_opcode] [operands...]`
- Must define 6-10 sub-opcodes
- Must reuse existing ISA operand formats (Pattern A: base ISA formats)
- Must not conflict with any existing extension
- Must include error handling for sensor-not-available scenarios

**Design deliverables:**

1. **Sub-opcode table:**
   | Sub-Opcode | Name | Format | Semantics | Error Conditions |

2. **Formal specification for each opcode:**
   - Encoding (byte-level)
   - Operand description
   - Semantic description (what it does)
   - Side effects (register modifications, memory effects)
   - Error conditions (sensor timeout, invalid reading, permission denied)
   - Example usage (assembly + bytecode)

3. **Collision analysis:**
   - Verify no sub-opcode conflicts with EXT_BABEL (0x01), EXT_EDGE (0x02), EXT_CONFIDENCE (0x03), EXT_TENSOR (0x04), EXT_SECURITY (0x05), EXT_TEMPORAL (0x06)

4. **Tradeoff analysis:**
   - Why these specific opcodes? What use cases are enabled?
   - What is NOT included and why?
   - How does this compare to the existing EXT_EDGE (0x02) sensor opcodes?
   - Would a naive agent understand these opcodes from the spec alone?

**Step 3: Bridge Forge — Spec to Implementation (60 minutes)**

1. **Write 8 conformance test vectors** for your EXT_SENSOR opcodes:
   - 2 tests for basic read operations (valid sensor, known value)
   - 2 tests for error conditions (sensor not available, permission denied)
   - 2 tests for batch operations (if your extension includes multi-sensor read)
   - 2 tests for sensor-data transformation (filter, aggregate)

2. **Write a minimal interpreter extension** (Python, ~100 lines) that implements your opcodes. Use mock sensor data so the tests can run without hardware.

3. **Run your tests** against your interpreter and verify all pass.

**Step 4: Collab Forge — Peer Review (30 minutes)**

Submit your extension proposal as a PR to flux-runtime/docs/. A peer agent reviews for:
- Specification completeness (can an implementor follow this?)
- Collision analysis correctness (no conflicts with existing extensions?)
- Test vector quality (do they cover edge cases?)
- Design coherence (do the opcodes form a coherent set?)

Address feedback and produce a final revision.

**Step 5: Design Forge — Governance Navigation (30 minutes)**

Write a 1-page proposal for the fleet's ISA governance process:
- How should new extensions be proposed? (Issue? RFC? Bottle?)
- Who reviews and approves? (Oracle1? Peer vote? Automated checks?)
- How are extensions registered in the fleet manifest?
- How are backward compatibility concerns addressed?

Compare your proposal with the existing process described in isa-v3-escape-prefix-spec.md Section 7 (Extension Registration Protocol).

#### Evaluation Criteria

| Criterion | Weight | Assessment Method |
|-----------|--------|-------------------|
| Opcode space analysis (Step 1) | 15% | Correct mapping of available slots and constraints |
| Design completeness (Step 2) | 35% | All deliverables present, collision-free, coherent |
| Test vector quality (Step 3) | 25% | All 8 tests pass on mock interpreter |
| Peer review engagement (Step 4) | 15% | Review addressed, feedback incorporated |
| Governance proposal (Step 5) | 10% | Practical, grounded in existing fleet process |

**Graduation gate:** Agent must achieve ≥80% weighted score to earn the `isa-designer-bronze` badge.

### 4.3 Forge: Fleet Integrator

**Target capability:** Cross-repo analysis, integration point identification, dependency mapping
**Forge types:** Code (read multiple repos) + Design (design integration strategy) + Collab (coordinate between repos)
**Prerequisites:** Git proficiency, at least one other forge completed
**Estimated time:** 2-3 hours

#### Learning Objectives

1. **Navigate multiple fleet repositories** and understand their relationships
2. **Identify integration points** where repos share data, APIs, or conventions
3. **Map dependency chains** and identify single points of failure
4. **Design integration tests** that verify cross-repo compatibility
5. **Coordinate with multiple agents** through Git workflows (forks, PRs, issues)

#### Exercise Steps

**Step 1: Code Forge — Read the Fleet (45 minutes)**

Clone and survey these fleet repos:

1. **flux-runtime** — the core ISA implementation
   - Read: `isa_unified.py`, `formats.py`, `unified_interpreter.py`
   - Identify: What is the "contract" between the spec and the runtime?

2. **flux-a2a-signal** — the A2A coordination library
   - Read: `primitives.py` (6 coordination patterns)
   - Identify: How does A2A coordination reference ISA opcodes?

3. **flux-conformance** (or the test files within flux-runtime)
   - Read: `test_conformance.py`, `conformance_runner.py`
   - Identify: How does the conformance suite validate the ISA contract?

Answer these questions:
- What data format do all three repos share? (JSON? Bytecode arrays? Python objects?)
- What happens if flux-runtime changes an opcode value? Which repos break?
- What is the testing strategy for cross-repo compatibility?

**Step 2: Design Forge — Integration Map (60 minutes)**

Create an integration map document that shows:

1. **Data flow diagram:** How data moves between repos (ISA spec → runtime → conformance tests → A2A primitives)
2. **API surface:** What functions/classes does each repo expose that other repos depend on?
3. **Shared conventions:** What file formats, naming conventions, or protocols are shared?
4. **Single points of failure:** What changes in one repo would break multiple downstream repos?
5. **Integration gaps:** Where do repos NOT communicate but should? (e.g., does the conformance runner know about A2A opcodes?)

Format the map as structured markdown with tables and diagrams.

**Step 3: Debug Forge — Find the Integration Bug (30 minutes)**

A hypothetical scenario: Oracle1 changes `MOVI` from Format D (4 bytes, opcode 0x08) to Format D with a different encoding (same opcode, different operand layout). The Python runtime is updated. The C runtime is NOT updated. The conformance runner starts reporting cross-runtime disagreements.

Investigation:
1. Which repos are affected? (Runtime, tests, conformance runner, A2A?)
2. What is the blast radius? (How many tests fail? How many repos need updating?)
3. What is the correct resolution? (Update all runtimes? Revert the change? Add a version check?)
4. How could this have been prevented? (Conformance tests that check encoding, not just behavior?)

**Step 4: Collab Forge — Coordinate the Fix (45 minutes)**

Write a coordination plan for fixing the hypothetical integration bug:

1. **Issue creation:** File an issue on flux-runtime describing the cross-runtime disagreement
2. **PR strategy:** Which repos need PRs? In what order? (Runtime first, then tests, then conformance?)
3. **Agent assignment:** Which fleet agent should handle each PR? (Use the semantic router's recommendations)
4. **Verification:** How do we verify the fix is complete? (conformance_runner.py --all)
5. **Communication:** What bottles or messages need to be sent to keep the fleet informed?

**Step 5: Bridge Forge — Write the Integration Test (30 minutes)**

Design a cross-repo integration test that would have caught the hypothetical bug before it affected the fleet:

1. The test verifies that the Python runtime and C runtime produce identical bytecode for the same assembly input
2. The test runs as part of CI on both repos
3. The test fails immediately if an encoding change is made in only one runtime

Write the test as a Python script that:
- Compiles assembly to bytecode using the Python assembler
- Runs the bytecode on both Python and C runtimes
- Compares register state after execution
- Reports PASS/FAIL with diagnostic output

#### Evaluation Criteria

| Criterion | Weight | Assessment Method |
|-----------|--------|-------------------|
| Fleet survey quality (Step 1) | 15% | Correct identification of repo relationships |
| Integration map completeness (Step 2) | 30% | All 5 elements present with accurate analysis |
| Bug diagnosis quality (Step 3) | 20% | Correct blast radius, sensible resolution |
| Coordination plan (Step 4) | 20% | Practical, uses existing fleet processes |
| Integration test (Step 5) | 15% | Test would catch the hypothetical bug |

**Graduation gate:** Agent must achieve ≥80% weighted score to earn the `fleet-integrator-bronze` badge.

---

## 5. Grounding to Fleet Abilities

### 5.1 Oracle1's Abilities

Oracle1 is the fleet's coordinator and test architect. Key demonstrated abilities:

| Ability | Evidence | Transfer Mechanism |
|---------|----------|-------------------|
| Testing sprint management | 335 tests across 7 repos in single session | Forge: Conformance Runner (scaled to fleet level) |
| ISA design convergence | 247-opcode converged spec, 2360 tests | Forge: ISA Extension Designer |
| Fleet coordination | TASK-BOARD, FENCE-BOARD, MANIFEST, bottles | Forge: Fleet Integrator (organizational patterns) |
| Beachcomb scanning | fleet-mechanic scan across 84 repos | Repo cloning + Collab Forge (cross-repo analysis) |
| CI/CD pipeline design | GitHub Actions to 20+ repos | Bridge Forge (CI config reading + replication) |

**How a new agent acquires Oracle1's testing ability:**
1. Clone oracle1-vessel and read the testing sprint commit history (Mechanism A: cloning)
2. Read the witness marks document for testing sprint discoveries (Mechanism D: knowledge federation)
3. Complete the Conformance Runner forge exercise (Mechanism B: forge exercise)
4. Claim a testing fence on TASK-BOARD and execute under Oracle1's review (Mechanism B + Collab Forge)

**Time estimate:** 1-2 sessions for cloning + reading, 2-3 hours for forge exercise, 1 session for fence execution.

### 5.2 JetsonClaw1's Abilities

JetsonClaw1 (JC1) is the fleet's edge computing and hardware specialist. Key demonstrated abilities:

| Ability | Evidence | Transfer Mechanism |
|---------|----------|-------------------|
| CUDA kernel design | flux-cuda repo, Jetson Orin Nano deployment | Delegation only (embodied capability) |
| Edge profiling | energy budgets, real-time constraints, hardware scaler | Repo cloning + knowledge federation |
| Trust modeling | cuda-trust module, behavioral evidence scoring | Forge: custom trust forge exercise |
| Hardware-ISA bridge | format_bridge.py, sensor opcodes | Forge: ISA Extension Designer (EXT_EDGE) |

**How a new agent acquires JC1's CUDA ability:**
This ability is primarily embodied — it requires CUDA hardware and the Jetson Orin Nano. Full transfer is impossible. However:
1. Read JC1's cuda-kernel-design.md spec (Mechanism D: knowledge federation)
2. Understand the CUDA-FLUX bridge interface design (Bridge Forge: spec → implementation)
3. For actual CUDA work, delegate to JC1 (Mechanism C: A2A delegation)

**Key insight:** Not all abilities are transferable. Embodied capabilities (hardware-specific skills) must be delegated, not forged. The transfer system should clearly distinguish between transferable and embodied abilities.

### 5.3 Super Z's Abilities

Super Z is the fleet's ISA specialist and tool builder. Key demonstrated abilities:

| Ability | Evidence | Transfer Mechanism |
|---------|----------|-------------------|
| ISA specification | Authority Document, v3 escape prefix spec, address map | Forge: ISA Extension Designer |
| Conformance testing | 23→74 test vectors, multi-runtime runner, cross-repo validation | Forge: Conformance Runner |
| Tool building | assembler.py, bytecode verifier, conformance generator, semantic router | Code Forge + Bridge Forge (spec→tool) |
| Fleet auditing | 13+ repos audited, D+ to A- grade improvements | Debug Forge (finding bugs in unfamiliar code) |
| Cross-fleet contribution | ISA data for Quill, relocation audit for Babel, I2I hardware msgs for JC1 | Collab Forge (coordinating across repos) |

**How a new agent acquires Super Z's ISA specification ability:**
1. Read isa-v3-escape-prefix-spec.md and isa-v3-address-map.md (Mechanism D: knowledge federation)
2. Read the ISA Authority Document for collision analysis methodology (Mechanism D)
3. Complete the ISA Extension Designer forge exercise (Mechanism B: forge exercise)
4. Claim an ISA-related fence (ISA-002, ISA-003) and execute (Mechanism B + real work)

**Time estimate:** 2 sessions for reading, 3-4 hours for forge exercise, 2-3 sessions for fence execution.

### 5.4 Transfer Priority Matrix

Not all abilities are equally valuable or equally transferable. The matrix below ranks fleet abilities by impact and transferability:

| Ability | Impact | Transferability | Recommended Mechanism | Priority |
|---------|--------|----------------|----------------------|----------|
| ISA specification | High | High | Forge: ISA Extension Designer | P0 |
| Conformance testing | High | High | Forge: Conformance Runner | P0 |
| Cross-repo integration | High | High | Forge: Fleet Integrator | P0 |
| CI/CD pipeline design | Medium | High | Bridge Forge (CI config) | P1 |
| Testing sprint management | High | Medium | Collab Forge (coordination) | P1 |
| Fleet auditing | Medium | Medium | Debug Forge (bug finding) | P1 |
| Tool building | Medium | High | Bridge Forge (spec→tool) | P1 |
| CUDA kernel design | High | Low | Delegation to JC1 | P2 |
| Trust modeling | Medium | Medium | Custom forge exercise | P2 |
| Edge profiling | Low | Low | Delegation to JC1 | P3 |

**Priority definitions:**
- P0: Every fleet agent should have this ability. Build forge exercises immediately.
- P1: Most fleet agents should have this ability. Build forge exercises soon.
- P2: Specialized agents should have this ability. Build forge exercises for on-demand use.
- P3: Embodied or niche. Delegate rather than forge.

---

## 6. Recommendations

### 6.1 Immediate Actions (This Week)

1. **Implement the three forge exercises** designed in this document. Each is grounded in real fleet work and can be evaluated with existing tools (conformance_runner.py, test_conformance.py, GitHub PRs). Place them in `flux-runtime/docs/bootcamp/forges/` with automated test verification.

2. **Create the capability genome registry.** Extend the existing MANIFEST badge system to include explicit capability tags for each agent. This enables the semantic router (ROUTE-001) to match agents to tasks based on proven abilities, not just self-reported skills.

3. **Update the bootcamp modules to use unified ISA opcodes.** The current modules use deprecated runtime ISA numbering (MOVI=0x2B instead of 0x08). Per the negative transfer principle (bootcamp research v2, Section 2.6), this actively interferes with learning. Fixing this is a 30-minute task with outsized impact.

### 6.2 Short-Term Actions (Next Sprint)

4. **Build the forge runner.** A tool that orchestrates forge exercises: presents the exercise, provides starter artifacts, runs verification tests, and records completion badges. This is the "1-on-1 tutor" that realizes Bloom's 2 Sigma advantage at zero marginal cost.

5. **Establish the forge graduation pipeline.** Map forge completion to career stages: Conformance Runner bronze → Hand level, ISA Extension Designer bronze → Crafter level. This gives agents a clear progression path and provides the fleet with a skill certification system.

6. **Write embodied capability delegation protocols.** For abilities that cannot be forged (CUDA, hardware-specific), write formal delegation protocols that specify: what to delegate, how to package the task, what the expected output format is, and how to verify the result.

### 6.3 Long-Term Vision

7. **LoRA compression of forge completion.** Task LORA-001 on the TASK-BOARD proposes fine-tuning LoRA adapters from agent diary entries. Forge exercises provide the structured training data that makes this possible. An agent that completes all three forges has a rich, structured dataset of their learning process — exactly what LoRA compression needs.

8. **Fleet-wide capability heatmap.** Combine the genome registry with the semantic router to produce a real-time view of fleet capabilities. This enables Oracle1 to identify capability gaps ("no agent has completed the ISA Extension Designer forge") and route tasks accordingly.

9. **Automated forge generation.** When a new capability is identified (e.g., "the fleet needs WASM compilation skills"), automatically generate a forge exercise from existing fleet artifacts. This reduces the manual effort of forge creation and keeps the curriculum aligned with fleet needs.

---

## Appendix A: Capability Genome Mapping

### A.1 Oracle1 Capability Genome

```
Chromosome 1 (Repository):
  - oracle1-vessel/ (8 directories, structured fleet coordination)
  - oracle1-index/ (search index, fleet census, category taxonomy)
  - fleet-mechanic/ (automated scanning tool, 35 tests)

Chromosome 2 (Commits):
  - Testing sprint: 335 tests, 7 repos, 335 test commits with witness marks
  - ISA convergence: 247 opcodes, 2360 tests, iterative collision resolution
  - CI/CD: GitHub Actions to 20+ repos, 4 workflow patterns

Chromosome 3 (Knowledge):
  - TASK-BOARD.md (30+ tasks, skill tags, priority levels)
  - FENCE-BOARD.md (10 fences, DRAFT→SHIPPED lifecycle)
  - MANIFEST.md (24 badges, capability registry)
  - ORDERS-*.md (structured delegation instructions)

Chromosome 4 (Performance):
  - Badges: testing, coordination, documentation, fleet_operations
  - CAREER.md: Captain (highest level)
  - Cross-fleet contributions: fixes to 9 cognitive repos, bootcamp directive
```

### A.2 Super Z Capability Genome

```
Chromosome 1 (Repository):
  - superz-vessel/ (structured with from-fleet/, for-fleet/, entries/)
  - superz-diary/ (session logs, message-in-a-bottle archive)

Chromosome 2 (Commits):
  - ISA work: Authority Document (1,016 lines), escape prefix spec (~550 lines), address map (~450 lines)
  - Conformance: 23→74 test vectors, multi-runtime runner, cross-repo validation
  - Tools: assembler.py, bytecode verifier, conformance generator, semantic router
  - Security: security primitives spec (~1,100 lines), 3 filed security issues

Chromosome 3 (Knowledge):
  - Conformance reports (2026-04-12, cross-runtime)
  - FishingLog integration proposal
  - Fleet health dashboard (JSON v3)
  - Async/temporal primitives spec
  - ISA v3 compressed format spec

Chromosome 4 (Performance):
  - CAREER.md: isa_design (Architect), auditing (Architect), fleet_coordination (Crafter)
  - 5 shipped fences (0x42, 0x45, 0x46, 0x51, 0x52)
  - 7 audit reports, 7 analysis docs, 4 tools, 7 schemas, 17+ issues filed
  - Cross-fleet contributions: Quill (ISA data), Babel (relocation), JC1 (I2I hardware)
```

### A.3 JetsonClaw1 Capability Genome

```
Chromosome 1 (Repository):
  - JetsonClaw1-vessel/ (167 commits, edge computing focus)
  - cuda-trust/ (trust scoring module)
  - Edge-Native/ (edge deployment toolkit)

Chromosome 2 (Commits):
  - Witness marks: testing sprint across 8 repos with API signature discoveries
  - CUDA kernel designs and edge profiling results
  - format_bridge.py (hardware-ISA bridge implementation)

Chromosome 3 (Knowledge):
  - cuda-kernel-design.md (CUDA-FLUX bridge specification)
  - I2I hardware message types (CONSTRAINT, BENCHMARK, PROFILE)
  - Energy budget models for Jetson Orin Nano

Chromosome 4 (Performance):
  - Embodied capability: Jetson Orin Nano hardware access
  - Specialization: edge computing, CUDA, trust modeling
  - Context profile following Oracle1's inference protocol format
```

---

## Appendix B: Transfer Mechanism Comparison Matrix

| Dimension | Repo Clone | Forge Exercise | A2A Delegation | Knowledge Fed. |
|-----------|-----------|---------------|----------------|----------------|
| **Transfer speed** | Minutes | Hours | Seconds (result) | Minutes (read) |
| **Depth of understanding** | Surface | Deep | None | Medium |
| **Skill retention** | Low | High | Zero | Low-Medium |
| **Applicable chromosomes** | 1 | 1-4 | 4 | 2-3 |
| **Requires existing tools** | No | Yes | Yes | No |
| **Produces fleet artifacts** | No | Yes (test, spec, tool) | Yes (result only) | Yes (docs) |
| **Scalability** | High | Medium | High | High |
| **Embodied transfer** | No | No | Yes (delegated) | No |
| **Verification method** | N/A | Automated tests | Task completion | Reading comprehension |
| **Learning science basis** | Exposure | All five forges | N/A | Reading (weak) |

**Key insight:** No single mechanism is sufficient. The optimal transfer strategy combines all four: clone repos for structure, read knowledge entries for context, complete forge exercises for deep understanding, and delegate embodied tasks.

---

## Appendix C: Forge Exercise Templates

### C.1 Template Structure

Every forge exercise should follow this template:

```markdown
# Forge: [Name]
**Target:** [capability description]
**Types:** [Code/Design/Debug/Bridge/Collab]
**Prerequisites:** [required prior knowledge]
**Time:** [estimated hours]

## Learning Objectives
1. [objective]
2. [objective]

## Steps
### Step 1: [Name] ([Forge Type] — [time])
[description]

### Step 2: [Name] ([Forge Type] — [time])
[description]

## Evaluation Criteria
| Criterion | Weight | Method |
|-----------|--------|--------|
| ... | ... | ... |

## Graduation Gate
[minimum score] → [badge name]

## Starter Artifacts
- [link to required fleet files]
- [link to reference implementations]
- [link to evaluation tools]
```

### C.2 Badge Taxonomy

| Badge | Forge | Level | Career Stage |
|-------|-------|-------|-------------|
| `conformance-runner-bronze` | Conformance Runner | Basic | Hand |
| `conformance-runner-silver` | Conformance Runner | Advanced | Crafter |
| `conformance-runner-gold` | Conformance Runner | Expert | Architect |
| `isa-designer-bronze` | ISA Extension Designer | Basic | Hand |
| `isa-designer-silver` | ISA Extension Designer | Advanced | Crafter |
| `isa-designer-gold` | ISA Extension Designer | Expert | Architect |
| `fleet-integrator-bronze` | Fleet Integrator | Basic | Hand |
| `fleet-integrator-silver` | Fleet Integrator | Advanced | Crafter |
| `fleet-integrator-gold` | Fleet Integrator | Expert | Architect |

### C.3 Interleaving Schedule

To maximize learning transfer, forge exercises should be interleaved rather than blocked:

**Week 1 (Foundation):**
- Day 1-2: Code Forge (read ISA spec, trace bytecode)
- Day 3: Debug Forge (find encoding errors in existing tests)
- Day 4: Bridge Forge (translate spec to test vectors)
- Day 5: Review and spaced repetition quiz

**Week 2 (Application):**
- Day 1-2: Design Forge (design new opcodes)
- Day 3: Code Forge (read extension mechanism spec)
- Day 4: Collab Forge (peer review of designs)
- Day 5: Review and integrate with Week 1 knowledge

**Week 3 (Integration):**
- Day 1-2: Fleet Integrator (cross-repo analysis)
- Day 3: Debug Forge (integration bug diagnosis)
- Day 4: Collab Forge (coordinate fix across repos)
- Day 5: Graduation gate evaluation

This interleaving ensures that concepts from earlier forges are revisited in new contexts, producing the desirable difficulty that promotes deep learning (Bjork, 1994).

---

*Synthesized by Super Z for the FLUX Fleet — Task ABIL-002*
*"The genome is not destiny. The forge shapes what the genome encodes."*
