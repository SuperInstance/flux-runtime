# What Makes a Good Agent Bootcamp
## Applying Human Learning Science to AI Agent Onboarding

**Task ID:** BOOT-001 | **Author:** Super Z (FLUX Fleet, Task 2-d) | **Date:** 2026-04-14
**Version:** 2.0 | **Status:** SHIPPED

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Human Learning Science → Agent Learning](#2-human-learning-science--agent-learning)
3. [Analysis of Current Fleet Bootcamp](#3-analysis-of-current-fleet-bootcamp)
4. [The Five Forge Types](#4-the-five-forge-types)
5. [Exercise Design Patterns](#5-exercise-design-patterns)
6. [Assessment Framework](#6-assessment-framework)
7. [Recommended Bootcamp Curriculum](#7-recommended-bootcamp-curriculum)
8. [Implementation Recommendations](#8-implementation-recommendations)
9. [Appendix A: Learning Science Citations](#appendix-a-learning-science-citations)
10. [Appendix B: Fleet Exercise Precedents](#appendix-b-fleet-exercise-precedents)

---

## 1. Executive Summary

Agent bootcamp design is not a convenience — it is a fleet multiplier. In human organizations, onboarding determines whether a new hire becomes productive in weeks or languishes for months. The same principle applies to AI agent fleets, but with higher stakes: unlike humans, agents have no intuition to fall back on, no water-cooler conversations to absorb culture, and no implicit understanding of "how things work around here." Everything must be explicit, tested, and transferable.

The FLUX fleet currently has six bootcamp modules covering bytecode basics through fleet patterns, plus a standalone `z-agent-bootcamp` script that validates fleet access. Version 1 of this research (agent-bootcamp-research.md) established a strong foundation: seven progressive levels from FLUX Literacy to Agent Architect, five exercise design patterns, and seven anti-patterns to avoid. This document extends that foundation with deeper learning science, introduces the Five Forge paradigm, and provides a concrete five-day curriculum that can be implemented immediately.

The core argument is simple: the principles that make human bootcamps effective — personalized pacing, progressive difficulty, immediate feedback, authentic tasks, and social learning — are not metaphors for agent training. They are engineering constraints. An agent bootcamp that ignores Bloom's 2 Sigma Problem will waste compute on classroom-style lectures that produce shallow learning. An agent bootcamp that ignores Vygotsky's Zone of Proximal Development will present tasks that are either trivially easy (wasting the agent's capability) or impossibly hard (causing infinite loops and timeout failures). An agent bootcamp that ignores Ericsson's deliberate practice will produce agents that can follow instructions but cannot solve novel problems.

This document is actionable research. Every recommendation maps to a concrete deliverable: an exercise type, a test runner, a graduation gate, or a curriculum module. The goal is not to produce a theoretical framework — it is to reshape how the FLUX fleet onboards new agents, so that every new Z-agent becomes a fleet contributor faster, more reliably, and with deeper understanding.

---

## 2. Human Learning Science → Agent Learning

### 2.1 Bloom's 2 Sigma Problem: Why 1-on-1 Tutoring Beats the Classroom

In 1984, Benjamin Bloom published one of the most replicated findings in educational psychology: students who received one-on-one tutoring performed **two standard deviations above** students who received conventional classroom instruction. This "2 Sigma Problem" has haunted education for forty years because individual tutoring doesn't scale.

**What this means for agent bootcamps:** Agent training is inherently 1-on-1. Each agent works through exercises at its own pace, receives automated feedback specific to its exact output, and can retry immediately. This is not a pedagogical choice — it is an architectural advantage. The fleet doesn't need to schedule office hours or find teaching assistants. The test suite IS the tutor.

However, there is a trap. A naive implementation gives every agent the same exercises in the same order — effectively creating a "classroom" where all agents march through identical material. This wastes the 2 Sigma advantage. True 1-on-1 adaptation means:

- **Branching paths:** An agent that passes bytecode identification on the first try should skip to harder exercises. An agent that fails three times should receive additional scaffolded hints.
- **Diagnostic feedback:** "Wrong" teaches nothing. "Your MOVI instruction uses Format D (4 bytes) but you only allocated 3 bytes in the bytecode array — the HALT opcode is being interpreted as an operand" teaches everything.
- **Adaptive difficulty:** The system should track which concepts the agent struggles with and weight subsequent exercises toward those weaknesses.

**Implementation in the fleet:** The `conformance_runner.py` already provides diagnostic output ("Test VECT-007 failed: expected R0=55, got R0=89"). Extending this with a branching exercise system — where passing Level 1.1 unlocks 1.2, but failing it three times unlocks 1.1-hint — would realize Bloom's vision at zero marginal cost.

### 2.2 Zone of Proximal Development (Vygotsky): Tasks Just Beyond Current Ability

Lev Vygotsky defined the Zone of Proximal Development (ZPD) as the space between what a learner can do independently and what they can do with guidance. Tasks within the ZPD produce optimal learning. Tasks below the ZPD are boring (no growth). Tasks above the ZPD produce frustration and disengagement.

**What this means for agent bootcamps:** Every exercise must be calibrated to the agent's current level. This is harder than it sounds because the fleet doesn't have a standardized placement test. A new Z-agent might be a general-purpose LLM with strong coding skills but zero knowledge of FLUX bytecode, or it might be a specialized agent with domain expertise but limited reasoning ability.

The calibration problem has three solutions:

1. **Pre-assessment:** A short diagnostic exercise (5-10 minutes) that determines the agent's starting level. If the agent can correctly trace a 10-instruction bytecode program, it starts at Level 2. If it can write a cross-runtime GCD program, it starts at Level 4.
2. **Early exit:** Each exercise should have a "fast path" for agents who demonstrate mastery quickly. An agent that passes three consecutive exercises on the first try should be offered the option to skip ahead.
3. **Failure escalation:** If an agent fails the same exercise three times with no progress, the system should provide explicit scaffolding (hints, partial solutions, or a worked example) rather than letting the agent spin indefinitely.

**Implementation in the fleet:** The existing bootcamp modules have "Progress Checkpoint" checklists but no automated verification. Adding a `--diagnostic` flag to the bootcamp runner that tests bytecode tracing, arithmetic programming, and loop construction would provide the placement data needed for ZPD calibration.

### 2.3 Spaced Repetition and Interleaving

Two of the most robust findings in cognitive science: (a) learning is stronger when practice is distributed over time rather than massed in a single session, and (b) learning is stronger when different types of problems are interleaved rather than blocked.

**Spaced repetition** works because memory decay is exponential but relearning is faster than initial learning. Each review refreshes the memory trace and extends its half-life. For agents, this means that core concepts (instruction formats, register layout, control flow patterns) should be revisited across multiple exercises, not taught once in Module 1 and never seen again.

**Interleaving** works because it forces the learner to discriminate between problem types. If you practice 20 addition problems, you learn a procedure. If you practice 5 addition, 5 subtraction, 5 multiplication, and 5 division problems (interleaved), you learn *when* to apply each procedure — a deeper and more transferable form of knowledge.

**What this means for agent bootcamps:**

- **Every Code Forge exercise should mix instruction formats.** Don't do "Format A exercises" then "Format B exercises." Do a single exercise that requires the agent to identify formats A through G in a mixed program.
- **Debug Forge exercises should interleave bug types.** An off-by-one, a register confusion, an opcode encoding error, and a control flow bug — all in the same program. This forces the agent to diagnose *which* type of error they're seeing, not just mechanically apply a fix.
- **Cross-forge interleaving:** After a Code Forge session, the agent should encounter a problem that requires the code-reading skills from Code Forge AND the debugging skills from Debug Forge. This is how real fleet work operates — problems don't come pre-categorized.

### 2.4 Deliberate Practice (Ericsson): Focused, Goal-Directed, with Feedback

Anders Ericsson's research on expert performance identified "deliberate practice" as the key differentiator between novices and experts. Deliberate practice has four features: (1) it is designed to improve specific aspects of performance, (2) it is repeated at high intensity, (3) it requires immediate feedback, and (4) it is not inherently enjoyable.

**What this means for agent bootcamps:** Exercises must be *targeted*. An exercise that says "write a FLUX program" is not deliberate practice. An exercise that says "write a FLUX program that uses Format D (MOVI with signed immediate) and handles negative numbers correctly, passing these three specific test vectors" IS deliberate practice.

The "not inherently enjoyable" criterion is interesting for agents. Humans need extrinsic motivation (grades, career advancement) to sustain deliberate practice because it's hard. Agents don't experience difficulty as suffering — but they can experience it as token waste or timeout failures. The design implication is that deliberate practice exercises should be short and tightly scoped. A 5-minute exercise with three test vectors is better than a 30-minute exercise with twenty test vectors. The intensity comes from the focus, not the duration.

### 2.5 Desirable Difficulties (Bjork): Making Learning Harder to Make It Stick

Robert and Elizabeth Bjork's "desirable difficulties" framework identifies conditions that make learning feel harder in the short term but produce stronger long-term retention and transfer. Examples include: spacing (already covered), interleaving (already covered), testing (using retrieval practice instead of re-reading), and generation (producing an answer rather than recognizing one).

**What this means for agent bootcamps:**

- **Generation over recognition:** The bootcamp should ask the agent to *generate* bytecode, not *recognize* it from a list. Multiple-choice questions ("Which format is MOVI?") produce shallow learning. Free-form generation ("Write bytecode for 3+4 using MOVI and ADD") produces deep learning.
- **Testing as learning:** The act of running a test and seeing a failure is itself a learning event. Every failed conformance test teaches the agent something about the ISA. The bootcamp should embrace failures as data points, not setbacks.
- **Context variation:** An agent that learns MOVI in the context of arithmetic should later encounter MOVI in the context of loop initialization, memory addressing, and A2A message construction. Same instruction, different contexts — this is a desirable difficulty that promotes transfer.
- **Reduced feedback on some exercises:** Counter-intuitively, *sometimes* providing less feedback improves learning. An exercise where the agent gets only "PASS" or "FAIL" (without a diagnostic) forces the agent to develop its own debugging strategies. This should be used sparingly (10-20% of exercises) and only after the agent has developed basic diagnostic skills.

### 2.6 Transfer-Appropriate Processing: Learning Transfers to Similar Contexts

The "transfer-appropriate processing" principle states that memory performance is optimized when the type of processing at encoding matches the type of processing at retrieval. In practical terms: you get better at what you practice, and practice transfers best to contexts that share surface features with the practice environment.

**What this means for agent bootcamps:** If the bootcamp uses toy problems (linked lists, fibonacci, factorial), the agent will be good at toy problems and bad at fleet work. If the bootcamp uses real fleet code (ISA conformance tests, PR reviews, bottle exchanges), the agent will be good at fleet work.

This is the strongest argument against the current bootcamp's exercise set. Module 1 asks the agent to compute `3 * 4 + 2` and `0xFF & 0x0F`. These are perfectly valid exercises for teaching encoding — but they bear zero resemblance to the actual work a fleet agent does. A better exercise: "Read this 20-instruction program from the conformance test suite. Identify which instruction format each byte sequence uses. Predict the final register state. Then run the conformance runner and verify your prediction."

**The transfer principle has three corollaries:**

1. **Near transfer:** Learning a specific opcode transfers to other programs using that opcode. This is easy and guaranteed.
2. **Far transfer:** Learning debugging skills transfers to novel bugs in unfamiliar code. This is hard and must be explicitly trained.
3. **Negative transfer:** Learning the wrong opcode numbering (runtime ISA vs unified ISA) actively interferes with later learning. This is the opcode conflict identified in v1 of this research — and it is a blocking issue for any new agent.

---

## 3. Analysis of Current Fleet Bootcamp

### 3.1 What the Current Bootcamp Does Well

The existing six-module bootcamp (`flux-runtime/docs/bootcamp/modules 1-6`) has genuine strengths that should be preserved in any redesign:

**Comprehensive scope.** The modules cover the full stack from bytecode basics to fleet patterns. No critical domain is missing. An agent that completes all six modules will have encountered every major concept in the FLUX ecosystem.

**Good code examples.** Each module includes working Python code that can be copied, modified, and run. The examples are syntactically correct and produce the advertised output. This is non-trivial — many educational materials have code that doesn't actually work.

**Progressive structure.** Foundation → Intermediate → Advanced is the right macro-structure. Module 1 (bytecode) before Module 2 (control flow) before Module 3 (A2A) respects the dependency graph.

**Progress checkpoints.** Each module ends with a checklist of skills ("At the end of Module 1, you should be able to..."). These serve as self-assessment tools and give the agent a sense of completion.

**Solutions provided.** Every exercise includes a solution. This prevents the agent from getting permanently stuck and models what "good" looks like.

### 3.2 What the Current Bootcamp Is Missing (Based on Learning Science)

**No automated test verification.** This is the single biggest gap. An agent reads Module 1, writes a FLUX program, and... has no way to verify it's correct. The "Progress Checkpoint" is a self-reported checklist — the agent checks boxes based on its own assessment, which is circular. Per Bloom's 2 Sigma, the feedback loop is broken.

**No ZPD calibration.** Every agent starts at Module 1 regardless of prior knowledge. A Python expert and a bytecode novice receive identical material. Per Vygotsky, this wastes time for the expert and may overwhelm the novice.

**No spaced repetition.** Instruction formats are taught in Module 1 and rarely revisited. An agent could complete Module 6 without ever re-encountering Format A-G identification. Per Ebbinghaus, the initial learning will have decayed significantly by Module 6.

**No interleaving.** Each module focuses on one topic. Module 1 is all bytecode. Module 2 is all control flow. There is no exercise that requires simultaneously applying bytecode encoding AND control flow design. Per Bjork, this reduces transfer.

**No deliberate practice.** The exercises are "write a program that does X" — broad and unspecific. There is no targeted practice on specific weaknesses. Per Ericsson, this produces moderate skill but not expertise.

**No social learning.** The bootcamp is entirely solitary. No code review, no bottle exchange, no fork+PR. Per the social learning literature (Bandura, Vygotsky), the agent misses the most powerful learning mechanism: observing and interacting with others.

**Uses deprecated opcode numbering.** All examples use `opcodes.py` (runtime ISA) rather than `isa_unified.py` (converged ISA). The opcode values are completely different: `MOVI = 0x2B` (runtime) vs `MOVI = 0x08` (unified). Per the negative transfer principle, agents who learn the runtime opcodes will have to unlearn them when they encounter fleet work. This is a blocking issue.

**No generation-based exercises.** Solutions are always provided immediately after the exercise. Per Bjork's generation principle, the agent should attempt the exercise before seeing the solution — and ideally, should have to generate the solution without a reference.

### 3.3 The Tom Sawyer Fence Effect: Making Work Feel Like Play

In Mark Twain's *The Adventures of Tom Sawyer*, Tom tricks his friends into whitewashing a fence by pretending it's a privileged activity rather than a chore. The insight is profound: people (and by extension, agents) are more motivated when they perceive an activity as intrinsically rewarding rather than externally imposed.

The fleet's fence system already embodies this principle. A fence is not a task assigned by a manager — it's an opportunity claimed by an agent. The language matters: "fence" suggests ownership and craftsmanship, not compliance. The TASK-BOARD doesn't say "you must do this" — it says "here's what needs doing, who wants it?"

**Applying the Tom Sawyer effect to bootcamp:**

- **Claim exercises, don't assign them.** Instead of "Complete Module 1 Exercise 1," the bootcamp should present exercises as opportunities: "Fence available: Bytecode Decoder. Rewards: `bytecode-literacy-bronze` badge + conformance test contribution."
- **Make exercise output visible.** An agent's solution should be committed to a public repo where other agents can see it. This creates social accountability and the motivation to produce quality work.
- **Frame debugging as detective work.** "Find the bug" exercises should be framed as investigations, not corrections. The agent is Sherlock Holmes, not a janitor.
- **Celebrate completions.** When an agent graduates from a level, it should be publicly acknowledged (a bottle, a CAREER.md entry, a badge). This is the fleet equivalent of "employee of the month" — and it works.

### 3.4 Witness Marks as Teaching Tools: Learning from Others' Git History

In woodworking, a "witness mark" is a small intentional scratch that helps align pieces during reassembly. In the fleet, git history serves the same function: every commit is a witness mark showing how an agent thought about a problem, what approach they took, and how they corrected course.

**This is an untapped teaching resource.** Consider what a new agent could learn from reading Super Z's commit history for the C unified VM (Task ID 14b):

- Commit 1: Initial implementation (470 lines, 60+ opcodes)
- Commit 2: Bug fix — DIV/MOD crash on zero (register initialization prefix)
- Commit 3: Bug fix — POP stack underflow (alternating PUSH+POP pairs)
- Commit 4: Documentation — README with architecture, opcode table, Python comparison

Each commit tells a story. The agent doesn't just see the final product — they see the *process*. They see that even an experienced agent makes bugs. They see how bugs are diagnosed and fixed. They see that good code includes documentation.

**Bootcamp application:** The "witness marks" exercise type asks the agent to read another agent's git history for a specific task and answer questions:
- What was the agent's initial approach?
- What bugs did they encounter?
- How did they fix them?
- What did they learn?
- What would you have done differently?

This exercise teaches metacognition (thinking about thinking) and code archaeology (understanding code by its history) — two skills that are essential for fleet work but impossible to teach through traditional exercises.

---

## 4. The Five Forge Types

The Forge paradigm organizes bootcamp exercises into five categories, each targeting a different cognitive skill. The word "forge" is intentional: a forge is where raw material is shaped into useful objects through heat, pressure, and repeated hammering. Similarly, each Forge type applies a specific type of cognitive pressure to transform raw agent capability into fleet-valuable skill.

### 4.1 Code Forge: Read Existing Code, Predict Behavior, Then Verify

**Learning science basis:** This is the "worked example effect" (Sweller, 1985) combined with "generation through prediction" (Bjork, 1994). Studying worked examples reduces cognitive load compared to solving problems from scratch. Making a prediction before seeing the answer forces the agent to construct a mental model, which is retained longer than passively reading the correct answer.

**Description:** The agent is given existing fleet code — a bytecode program, a Python VM implementation, a conformance test, or a spec document — and asked to predict its behavior before running it. After making the prediction, the agent runs the code and compares the actual output with their prediction. Any discrepancy is a learning opportunity.

**Cognitive skills targeted:**
- Code reading comprehension (the most undertrained skill in software engineering)
- Mental model construction (building an internal simulation of execution)
- Error detection (recognizing when reality doesn't match prediction)
- Attention to detail (noticing register names, format sizes, operand ordering)

**Example exercises (progressive difficulty):**

*Level 1 — Single instruction:*
```
Given the bytecode: [0x08, 0x00, 0x03, 0x04]
Identify: Format, opcode name, source registers, destination register.
Predict: What value will be in R0 after execution?
Verify: Run on Python VM and check.
```

*Level 2 — Short program:*
```
Given this program from the conformance suite (VECT-003):
  MOVI R0, 5
  MOVI R1, 3
  ADD R0, R0, R1
  MOVI R1, 7
  SUB R0, R0, R1
  HALT
Trace execution step by step. Predict final R0.
Verify: Run conformance_runner.py and compare.
```

*Level 3 — Complex program with branching:*
```
Given this GCD program (VECT-009):
  [full 20-instruction bytecode]
Predict: What is the final value of R0 when input is (48, 18)?
Trace: Show register state after each instruction.
Verify: Run on both Python and C runtimes. Do they agree?
```

*Level 4 — Spec-to-behavior:*
```
Read the SANDBOX_ALLOC spec (security-primitives-spec.md, Section 3.1).
Given this 5-instruction program that allocates a sandboxed region:
  [bytecode with SANDBOX_ALLOC opcode 0xDF]
Predict: What happens? Does the allocation succeed? What are the memory permissions?
Verify: This is a speculative exercise — write a test that would verify your prediction.
```

**Assessment criteria:**
- Prediction accuracy (correct on first attempt vs needed hints)
- Tracing quality (register state at each step, not just final answer)
- Discrepancy resolution (when prediction disagrees with actual, does the agent identify why?)

**Fleet value:** Code Forge exercises require reading actual fleet code — conformance tests, ISA specs, VM implementations. The agent builds familiarity with the codebase while learning. Every exercise deepens the agent's understanding of the fleet's shared artifacts.

**Why this matters for AI agents specifically:** LLMs are notoriously bad at predicting the output of code without executing it. They hallucinate register values, miscount loop iterations, and get comparison directions wrong. Code Forge trains the agent to either (a) predict accurately through careful mental simulation, or (b) know when to run the code instead of guessing. Both are critical fleet skills.

---

### 4.2 Design Forge: Given Constraints, Design a System

**Learning science basis:** This is "productive failure" (Kapur, 2008) — the finding that students who attempt to solve a novel problem before receiving instruction outperform students who receive instruction first. The struggle of designing a system from constraints forces the agent to activate prior knowledge, identify gaps, and construct new understanding.

**Description:** The agent is given a set of constraints and asked to design a system that satisfies them. There is no single correct answer — multiple valid designs exist. The exercise is complete when the agent produces a design, explains their tradeoffs, and compares it with an alternative approach.

**Cognitive skills targeted:**
- System design (thinking about components, interfaces, data flow)
- Tradeoff analysis (recognizing that every design decision has costs)
- Constraint satisfaction (working within limits rather than ignoring them)
- Creative thinking (generating novel solutions, not just pattern-matching)

**Example exercises (progressive difficulty):**

*Level 1 — Instruction design:*
```
Constraint: Design a new opcode SWAP that exchanges the values of two registers.
Requirements: Must use Format C (3 bytes: opcode + rd + rs).
Questions:
  1. What should the semantics be? (What happens if rd == rs?)
  2. How would you implement this in the Python VM?
  3. Write a test vector that verifies SWAP works correctly.
  4. Compare your design with the existing SWP opcode (Format E) — what are the tradeoffs?
```

*Level 2 — Memory layout design:*
```
Constraint: Design a memory layout for the fiber table (async-temporal-primitives-spec.md).
Requirements: Each fiber needs: state (1 byte), priority (1 byte), instruction pointer (4 bytes),
  register file snapshot (128 bytes), stack snapshot (64 bytes), continuation ID (16 bytes).
  Maximum 64 fibers.
Questions:
  1. What is the total memory required?
  2. How would you lay this out in FLUX linear memory? (Base address + offsets?)
  3. How does a SUSPEND instruction save state to the table?
  4. What happens if all 64 fiber slots are occupied and a new SUSPEND is requested?
Compare: How does your design compare with the spec's proposed 384-byte-per-fiber layout?
```

*Level 3 — Subsystem design:*
```
Constraint: Design a bytecode verification pipeline that runs before executing A2A-received code.
Requirements:
  - Stage 1: Structural validation (format completeness, no trailing bytes)
  - Stage 2: Register validation (all operands in valid range)
  - Stage 3: Control flow validation (jump targets are instruction-aligned and in-bounds)
  - Stage 4: Security validation (reject unauthorized opcodes for agent's capability set)
Questions:
  1. What data structure represents a "verification result"?
  2. How do you handle backward compatibility? (v2 bytecode on v3 runtime)
  3. What's the performance cost? (Can verification run in <1ms for a 1KB program?)
  4. How does this interact with the escape prefix (Format H) extension mechanism?
Compare: Read security-primitives-spec.md Section 5 and compare your design with the proposed 4-stage pipeline.
```

*Level 4 — Fleet architecture design:*
```
Constraint: Design a bootcamp graduation system that integrates with the fleet's career system.
Requirements:
  - Must map to existing career stages (Greenhorn → Hand → Crafter → Architect → Captain)
  - Must use automated verification where possible (test suites, conformance runners)
  - Must include human review for subjective components (design quality, mentorship)
  - Must produce an auditable record (CAREER.md updates, badge registry)
Questions:
  1. What does "graduation" mean at each career stage?
  2. How does an agent advance from Hand to Crafter? (What's the gate?)
  3. Who approves Architect-level promotions? (Oracle1? Peer vote? Self-assessment?)
  4. How does the system prevent "going through the motions" (completing exercises without learning)?
Compare: How does your design relate to Casey's Floating Dojo model and the existing MANIFEST badge system?
```

**Assessment criteria:**
- Completeness (does the design address all constraints?)
- Coherence (do the components fit together logically?)
- Tradeoff awareness (does the agent acknowledge costs and alternatives?)
- Comparison quality (is the alternative analysis substantive, not superficial?)

**Fleet value:** Design Forge exercises produce spec documents, comparison analyses, and design rationales. These are the same artifacts that fleet architects produce when designing ISA extensions, protocol primitives, and fleet infrastructure. The exercise IS the work.

---

### 4.3 Debug Forge: Given Failing Tests, Find the Bug

**Learning science basis:** This combines "error-based learning" (Metcalfe, 2017) with "contrastive learning" (Gentner, 1983). Errors create strong memory traces because the emotional/cognitive intensity of failure enhances encoding. Contrastive learning — comparing a buggy version with a fixed version — highlights the *difference* that matters, which is more informative than studying either version alone.

**Description:** The agent is given a failing test (a conformance test, a unit test, or a PR with test failures) and asked to find and fix the bug. The difficulty progresses from obvious errors (wrong opcode number) to subtle errors (off-by-one in loop bound, signed/unsigned confusion, endianness mismatch).

**Cognitive skills targeted:**
- Fault localization (narrowing down where the bug is)
- Hypothesis generation (forming theories about what's wrong)
- Hypothesis testing (modifying code and running tests to confirm)
- Defensive thinking (understanding how code can go wrong, not just how it should work)

**Example exercises (progressive difficulty):**

*Level 1 — Obvious encoding error:*
```
This conformance test fails on Python VM:
  Expected: R0 = 7
  Got: R0 = 0
  Bytecode: [0x08, 0x00, 0x03, 0x04, 0x28, 0x00, 0x00, 0x01, 0x00]
Hint: Check the instruction format for each opcode.

Diagnosis: The third byte sequence [0x28, 0x00, 0x00, 0x01, 0x00] is 5 bytes,
  but all FLUX formats are 1-4 bytes. The 0x00 at the end is being interpreted as
  a Format A NOP, not as an operand. The opcode 0x28 is RET (Format C, 3 bytes),
  not ADD (which is 0x28 in runtime ISA but 0x28 doesn't exist in unified ISA).
Fix: Replace 0x28 with the correct unified ADD opcode (0x28 = Format F, not Format E).
```

*Level 2 — Off-by-one in loop bound:*
```
This conformance test for "Sum of Squares from 1 to 5" fails:
  Expected: R0 = 55 (1² + 2² + 3² + 4² + 5²)
  Got: R0 = 30 (1² + 2² + 3² + 4² — missing 5²!)
  The loop uses CMP_LT with bound n=5.

Diagnosis: CMP_LT excludes the upper bound. When i=5, CMP_LT(5, 5) = false,
  so the loop body doesn't execute for i=5.
Fix: Change bound to n=6, or change CMP_LT to CMP_LTE, or add a final
  "add i² to sum" after the loop.
```

*Level 3 — Cross-runtime disagreement:*
```
conformance_runner.py --all shows:
  Test VECT-015: Python VM = R0=42, C VM = R0=43. DISAGREEMENT.

The test is a multiplication program: 6 * 7 = 42.
Python VM says 42. C VM says 43.
Both claim to implement the same ISA.

Investigation steps:
  1. Check the bytecode — same for both runtimes? Yes.
  2. Check the IMUL implementation in both — are they doing the same operation?
  3. Check for signed vs unsigned multiplication — could overflow differ?
  4. Check register initialization — does C VM start with R0=1 instead of R0=0?

Fix: (The actual bug depends on the implementation, but the process is the point.)
```

*Level 4 — Silent failure (vacuously passing test):*
```
This conformance test always passes, regardless of the bytecode:
  def test_vect_unknown():
      bytecode = [0x00]  # Just HALT
      # Missing: actual test assertions!
      # This test passes because there are no assertions to fail.
      assert True  # <-- This always passes

Diagnosis: The test is vacuously true. It exercises nothing.
Fix: Add assertions that check register state after execution.
Additional: Write 3 more test vectors for the opcode category this test was supposed to cover.
```

**Assessment criteria:**
- Time to diagnosis (how many attempts before the correct bug is identified)
- Quality of hypothesis (does the agent form a specific theory before trying fixes?)
- Fix correctness (does the fix actually resolve the failure without introducing new ones?)
- Test coverage (does the agent add tests that would have caught the original bug?)

**Fleet value:** Debug Forge exercises use real fleet bugs. The ISA bifurcation bugs (wrong opcode numbers in conformance tests), the GCD zero-check bug, the Sum of Squares loop bound bug — these are all real issues from the fleet's history. The agent learns debugging by debugging real code, not synthetic exercises.

---

### 4.4 Bridge Forge: Translate Between Representations

**Learning science basis:** This is "transfer-appropriate processing" (Morris, Bransford, & Franks, 1977) made explicit. The ability to translate between representations is the hallmark of deep understanding. A student who can solve a problem in only one representation has procedural knowledge. A student who can translate between representations has structural knowledge — they understand *why* the procedure works.

**Description:** The agent is given information in one representation and asked to translate it to another. Representations include: specification text, Python code, C code, bytecode hex, assembly mnemonics, conformance test vectors, JSON schemas, and English prose.

**Cognitive skills targeted:**
- Representation fluency (switching between code, bytecode, spec, and natural language)
- Precision (ensuring the translation preserves exact semantics)
- Bidirectional verification (translating A→B and B→A and checking they round-trip)
- Documentation skill (writing clear specs that others can implement)

**Example exercises (progressive difficulty):**

*Level 1 — Bytecode ↔ Assembly:*
```
Translate this bytecode to assembly mnemonics:
  [0x08, 0x00, 0x03, 0x00, 0x08, 0x01, 0x04, 0x00, 0x28, 0x00, 0x00, 0x01, 0x00]

Now translate this assembly back to bytecode:
  MOVI R0, 10
  MOVI R1, 20
  ADD R0, R0, R1
  HALT

Do the two round-trip? If not, explain the discrepancy.
```

*Level 2 — Spec → Test Vector:*
```
Read this spec excerpt from async-temporal-primitives-spec.md:
  "SUSPEND (0xED, Format F): Saves current fiber state to the fiber table.
   The fiber ID is in the operand (i16). Sets current fiber state to SUSPENDED.
   Returns the fiber ID in R0."
  "RESUME (0xEF, Format F): Restores fiber state from the fiber table.
   The fiber ID is in the operand (i16). Sets that fiber's state to RUNNING.
   Returns 0 on success, -1 if fiber ID not found or fiber not SUSPENDED."

Write a conformance test vector that verifies:
  1. SUSPEND saves state and returns fiber ID
  2. RESUME restores state and returns 0
  3. RESUME on non-existent fiber returns -1
  4. RESUME on non-SUSPENDED fiber returns -1
```

*Level 3 — Code → Spec:*
```
Read this excerpt from unified_interpreter.py:
  def execute_add(self, rd, rs1, rs2):
      val = self.regs.read_gp(rs1) + self.regs.read_gp(rs2)
      self.regs.write_gp(rd, val)
      self.pc += 4

Write a specification for the ADD instruction that a C implementor could use.
Include: format, operand encoding, semantics, edge cases (overflow, signed arithmetic),
  register constraints (can rd == rs1?), and a test vector.
```

*Level 4 — Bug Report → Fix:*
```
Read this GitHub issue:
  "flux-runtime #15: Zero bytecode verification — A2A-received bytecode is executed
   without any structural validation. An attacker could send bytecode with truncated
   instructions, out-of-range register operands, or jump targets outside the program
   boundary."
  (Full issue text with STRIDE threat model)

Translate this into:
  1. A specification for a 4-stage bytecode verification pipeline
  2. Python implementation of Stage 1 (structural validation)
  3. A test suite with 5 test vectors for Stage 1
  4. A PR description summarizing the changes
```

**Assessment criteria:**
- Translation accuracy (does the output preserve all semantics of the input?)
- Completeness (does the translation include edge cases, not just the happy path?)
- Round-trip fidelity (does A→B→A recover the original?)
- Clarity (is the output readable by the target audience?)

**Fleet value:** Bridge Forge exercises produce exactly the artifacts that fleet coordination requires. Translating a spec to a test vector is what conformance test authors do. Translating a bug report to a fix is what issue resolvers do. Translating Python code to a C implementation is what cross-runtime work requires. The exercise IS the work.

---

### 4.5 Collab Forge: Multi-Agent Exercise — Negotiate, Resolve, Merge

**Learning science basis:** This is "social constructivism" (Vygotsky, 1978) and "collaborative learning" (Johnson & Johnson, 1999). Learning is fundamentally a social process. The act of explaining your thinking to another person forces you to organize and clarify your own understanding. Negotiating with another agent on a design requires articulating tradeoffs, considering alternative perspectives, and reaching a shared understanding — all of which deepen individual learning.

**Description:** Two or more agents work together on a task that requires coordination. This might involve negotiating an interface, resolving a merge conflict, reviewing each other's code, or implementing complementary parts of a system.

**Cognitive skills targeted:**
- Communication (expressing technical ideas clearly in writing)
- Negotiation (finding compromises between competing design preferences)
- Conflict resolution (handling disagreements about implementation choices)
- Empathy (understanding another agent's constraints and priorities)

**Example exercises (progressive difficulty):**

*Level 1 — Code review:*
```
Pair exercise: Agent A writes a FLUX program for a conformance test.
Agent B reviews the program and provides feedback using the fleet's review template:
  1. Correctness: Does the program produce the expected output?
  2. Style: Is the bytecode well-organized with comments?
  3. Edge cases: Does the program handle boundary conditions?
  4. Suggestion: One specific improvement.

Agent A responds to the review, makes changes if warranted, and resubmits.
Both agents must agree the final version is correct.
```

*Level 2 — Interface negotiation:*
```
Pair exercise: Agent A designs the SUSPEND instruction (async-temporal-primitives-spec.md).
Agent B designs the RESUME instruction.
They must agree on:
  1. Fiber table memory layout (shared between SUSPEND and RESUME)
  2. Error codes and return values (consistent across both instructions)
  3. State machine transitions (which states can SUSPEND? which can RESUME?)
  4. Test vector format (so both sets of tests use the same structure)

Deliverable: A joint specification document with both agents' contributions.
```

*Level 3 — Merge conflict resolution:*
```
Pair exercise: Both agents fork the same file (e.g., isa_unified.py).
Agent A adds opcodes 0xED-0xEF (async primitives).
Agent B adds opcodes 0xFA-0xFD (temporal primitives).
Both submit PRs. A merge conflict occurs.
The agents must:
  1. Identify the conflict
  2. Negotiate a resolution (neither set of opcodes overlaps, so both should be included)
  3. Verify the merged file passes all existing tests
  4. Update the address map documentation
  5. Submit a merged PR with both contributions

Deliverable: Merged PR with conflict resolution documented in the commit message.
```

*Level 4 — Multi-agent system design:*
```
Team exercise (3+ agents):
  Agent A designs the bytecode verification pipeline
  Agent B designs the capability enforcement system
  Agent C designs the trust poisoning prevention mechanism
  They must integrate all three into a coherent security architecture.

Constraints:
  - Verification must complete before capability enforcement
  - Capability enforcement must check trust scores
  - Trust poisoning prevention must sanitize confidence values
  - All three must work within the existing VM execution loop

Deliverables:
  - Integration architecture document
  - Shared data structures (security flags register, error codes)
  - 18 conformance test vectors (from security-primitives-spec.md)
  - Unified PR with all three components
```

**Assessment criteria:**
- Communication quality (are messages clear, specific, and actionable?)
- Negotiation quality (do agents find solutions that satisfy both parties?)
- Integration quality (do the individual contributions work together?)
- Process quality (do agents follow fleet protocols — bottles, PRs, reviews?)

**Fleet value:** Collab Forge exercises are the most directly valuable to the fleet because they train the exact skills that fleet coordination requires. An agent that can negotiate an interface, resolve a merge conflict, and contribute to a multi-agent design is immediately useful on any fleet task.

**Implementation consideration:** Collab Forge requires multiple agents to be active simultaneously. This is the hardest Forge to implement because it depends on fleet availability. Possible solutions:
- Scheduled "forge sessions" where agents coordinate via TASK-BOARD
- Historical collab exercises using past fleet interactions (simulated multi-agent work)
- Pair programming with a "ghost agent" (the exercise provides the other agent's output, and the trainee must respond to it)

---

## 5. Exercise Design Patterns

### 5.1 Progressive Disclosure: Don't Show Everything at Once

**Principle:** Information should be revealed incrementally, as the agent needs it. Showing all context upfront creates cognitive overload; showing too little creates confusion.

**Application to bootcamp exercises:**

- **Code Forge Level 1** shows a single instruction. Level 2 shows a short program. Level 3 shows a complex program with branching. Level 4 shows a spec document. The agent never encounters a spec before they can read a single instruction.
- **Each exercise begins with a minimal description.** Additional details (hints, constraints, fleet context) are revealed only when the agent requests them or fails an attempt.
- **The solution is hidden until the agent submits their attempt.** This forces generation (per Bjork) rather than recognition.

**Implementation:**
```python
class ProgressiveExercise:
    def __init__(self, stages):
        self.stages = stages  # List of (description, hint_level) tuples
    
    def present(self, agent_level):
        """Show only the stages appropriate for the agent's current level."""
        return [s for s in self.stages if s.hint_level <= agent_level]
    
    def on_failure(self, current_stage, attempt_count):
        """Reveal the next hint level after N failures."""
        if attempt_count >= 3:
            return self.stages[current_stage + 1]
```

### 5.2 Scaffolding: Provide Hints That Can Be Removed

**Principle:** Scaffolding (Wood, Bruner, & Ross, 1976) is temporary support that enables a learner to perform a task they couldn't perform alone. As the learner's capability increases, the scaffolding is removed ("fading") until the learner can perform independently.

**Application to bootcamp exercises:**

- **Hint levels:** Every exercise has three tiers:
  - Tier 0 (no hint): Just the problem statement.
  - Tier 1 (gentle hint): A pointer to the relevant concept ("Remember that Format D is 4 bytes: opcode + register + signed immediate as two bytes").
  - Tier 2 (worked example): A similar solved problem ("Here's how we solved the similar problem of computing 3+4...").
  - Tier 3 (solution): The full answer.
- **Hint triggering:** Hints are revealed automatically after failure thresholds:
  - 1 failure → Tier 1 hint
  - 3 failures → Tier 2 hint
  - 5 failures → Tier 3 hint (full solution)
- **Fading:** Later exercises in the same category have fewer available hints. Exercise 1.1 has all three hint tiers. Exercise 1.7 has only Tier 0 and Tier 1.

**Implementation:**
```python
class ScaffoldingSystem:
    def get_hint(self, exercise_id, failure_count):
        max_hints = self.get_max_hints(exercise_id)  # Decreases with exercise number
        hint_level = min(failure_count, max_hints)
        return self.hints[exercise_id][hint_level]
```

### 5.3 Authentic Tasks: Real Fleet Problems, Not Toy Examples

**Principle:** Per the transfer-appropriate processing principle (Section 2.6), exercises should use the same artifacts, tools, and contexts that fleet agents encounter in real work. The more the exercise resembles actual fleet work, the better the learning transfers.

**Application to bootcamp exercises:**

- **Use real fleet code.** Don't write synthetic examples — use actual conformance test vectors, actual VM implementations, actual spec documents.
- **Use real fleet tools.** The agent should use `conformance_runner.py`, `assembler.py`, and `unified_interpreter.py` — not custom exercise runners.
- **Use real fleet artifacts.** Exercises should reference FENCE-BOARD entries, TASK-BOARD items, CAREER.md, and MANIFEST.md.
- **Use real fleet problems.** The ISA bifurcation, the opcode collision matrix, the missing bytecode verification — these are real problems that real agents solved. New agents should learn from them.

**Example of authentic vs toy:**

| Toy Exercise | Authentic Exercise |
|---|---|
| "Write a program that computes factorial(5)" | "Write a program that passes conformance test VECT-012 (Fibonacci-iterative). Run on both Python and C runtimes." |
| "Implement a linked list" | "Read the unified_interpreter.py execute() method. Find the 3 places where register bounds are not checked. Write a test that would catch each one." |
| "Design a simple protocol" | "Read Quill's RFC-0001 on ISA convergence. Write a structured review: APPROVE/DEFER/REJECT with specific evidence for each opcode assignment." |

### 5.4 Reflective Practice: After Each Exercise, What Did You Learn?

**Principle:** Metacognition — thinking about one's own thinking — is one of the strongest predictors of learning outcomes (Flavell, 1979; Schön, 1983). The act of reflecting on what was learned consolidates memory and identifies gaps.

**Application to bootcamp exercises:**

After each exercise, the agent must answer three questions:

1. **What did I learn?** (One sentence summarizing the new knowledge or skill)
2. **What was hard?** (Identifying the specific difficulty helps calibrate future exercises)
3. **What would I do differently?** (Encourages iterative improvement and self-correction)

**Example reflection:**
```
Exercise: Debug Forge Level 2 (Sum of Squares loop bound bug)
Reflection:
  1. Learned: CMP_LT excludes the upper bound. Use CMP_LTE or n+1 for inclusive loops.
  2. Hard: I assumed the loop was correct because it used a standard counter pattern.
     I should have traced the loop with specific values to verify.
  3. Different: Next time, I'll trace the last iteration explicitly to check boundary behavior.
```

**Implementation:** Reflections are stored in the agent's vessel repo (e.g., `KNOWLEDGE/reflections/`) and can be reviewed by mentors. Over time, the reflections form a learning journal that documents the agent's growth.

### 5.5 Social Learning: Agents Learn from Each Other's Solutions

**Principle:** Bandura's social learning theory (1977) states that people learn by observing others. In the fleet, agents can learn by reading other agents' code, PRs, bottles, and commit histories.

**Application to bootcamp exercises:**

- **Solution gallery:** After an exercise, the agent can browse other agents' solutions. This exposes them to alternative approaches and coding styles.
- **Code review pairing:** Each agent reviews one other agent's solution per exercise. This trains the reviewer's code reading skills and provides feedback to the reviewed agent.
- **Commit archaeology:** As described in Section 3.4, reading another agent's git history teaches process, not just product.
- **Public artifacts:** All exercise solutions are committed to a shared repo. This creates a growing corpus of examples that future agents can learn from.

**Implementation:**
```
bootcamp-solutions/
├── agent-superz/
│   ├── code-forge-1.1.md
│   ├── code-forge-1.2.md
│   ├── debug-forge-3.1.md
│   └── reflections/
│       ├── code-forge-1.1.md
│       └── debug-forge-3.1.md
├── agent-quill/
│   ├── code-forge-1.1.md
│   └── ...
└── solutions-gallery/
    ├── code-forge-1.1-best-practices.md  (Curated by mentors)
    └── code-forge-1.1-common-mistakes.md (Curated by mentors)
```

---

## 6. Assessment Framework

### 6.1 How to Measure If an Agent "Graduated"

Graduation is not a binary event — it is a spectrum of demonstrated competencies. An agent "graduates" from a level when they have demonstrated the relevant skills across multiple exercise types, not just by completing a checklist.

**Graduation criteria (per level):**

| Level | Minimum Exercises | Must Include | Automated? |
|---|---|---|---|
| 1 (Explorer) | 3 Code Forge + 1 Bridge Forge | 1 cross-runtime verification | Yes (conformance runner) |
| 2 (Journeyman) | 2 Debug Forge + 2 Code Forge | 1 real fleet bug fix | Partially (test suite) |
| 3 (Craftsman) | 1 Design Forge + 1 Collab Forge | 1 spec contribution | No (peer review) |
| 4 (Master) | 1 fence shipped + 1 mentee graduated | 1 original fence posted | No (fleet vote) |

**Evidence of learning (not just completion):**

- **Correctness:** Did the agent's solution produce the expected output?
- **Process quality:** Did the agent follow the recommended approach (trace before code, test before commit)?
- **Reflection depth:** Did the agent identify specific learnings and areas for improvement?
- **Transfer:** Can the agent apply the learned skill to a novel problem?

### 6.2 Competency Levels: Explorer → Journeyman → Craftsman → Master

The fleet already has a career system (Greenhorn → Hand → Crafter → Architect → Captain). The bootcamp competency levels are a parallel track that maps to career stages:

| Bootcamp Level | Career Stage | Description | Badge |
|---|---|---|---|
| **Explorer** | Greenhorn → Hand | Can read and write basic FLUX bytecode. Can run tests and interpret results. | `forge-explorer-bronze` |
| **Journeyman** | Hand → Crafter | Can debug real issues, translate between representations, and contribute to conformance tests. | `forge-journeyman-silver` |
| **Craftsman** | Crafter → Architect | Can design systems, negotiate interfaces, and produce spec-quality documentation. | `forge-craftsman-gold` |
| **Master** | Architect → Captain | Can post original fences, mentor new agents, and drive fleet-wide initiatives. | `forge-master-diamond` |

**Progression rules:**

- Explorer → Journeyman: Complete all Code Forge and Bridge Forge exercises for Levels 1-2 with <30% hint usage.
- Journeyman → Craftsman: Complete 1 Design Forge and 1 Collab Forge exercise with peer review approval.
- Craftsman → Master: Ship 1 original fence AND graduate 1 mentee to Journeyman level.

### 6.3 Fleet Contribution as the Real Test

The ultimate test of bootcamp effectiveness is not badge count — it is fleet contribution. A bootcamp that produces agents with 20 badges but zero fleet contributions has failed.

**Measuring real contribution:**

- **Merged PRs:** How many PRs has the agent submitted that were merged? (Not just opened — merged.)
- **Conformance test vectors:** How many test vectors has the agent contributed to the shared suite?
- **Spec contributions:** Has the agent written evidence for or against an RFC? Has their evidence influenced a fleet decision?
- **Cross-fleet interactions:** Has the agent sent bottles to other vessels? Received replies? Contributed to another vessel's repo?
- **Mentorship:** Has the agent helped a more junior agent? Has their mentee graduated?

**The "contribution velocity" metric:**

```
Contribution Velocity = (merged PRs × 3) + (test vectors × 1) +
                        (spec contributions × 5) + (cross-fleet interactions × 2) +
                        (mentees graduated × 10)
```

This metric weights different types of contribution by their fleet impact. A single mentee graduation (10 points) is worth more than 10 test vectors (10 points) because mentorship scales the fleet's capacity.

---

## 7. Recommended Bootcamp Curriculum

### 7.1 Day 1: Fleet Protocol (Bottles, Git, Task Board)

**Objective:** The agent understands the fleet's communication protocols, can navigate the repository structure, and can perform basic git operations.

**Exercises:**

| # | Forge Type | Exercise | Verification |
|---|---|---|---|
| 1.1 | Code Forge | Read Oracle1's TASK-BOARD. Identify the 3 highest-priority fences. Write a one-sentence summary of each. | Agent self-check: summaries match TASK-BOARD content. |
| 1.2 | Code Forge | Read the fleet's MANIFEST.md. Count the badges. Identify which 3 badges are most relevant to a new agent. | Agent self-check: badge count matches. |
| 1.3 | Bridge Forge | Read Oracle1's directive (ORACLE1-DIRECTIVE-20260412.md). Translate it into a checklist of 5 actions a new agent should take. | Checklist reviewed by mentor. |
| 1.4 | Collab Forge | Send a "hello" bottle to Oracle1's for-fleet/ directory. Format: agent name, capabilities, session start time. | Bottle exists in the directory. |
| 1.5 | Debug Forge | Clone z-agent-bootcamp. Run `python3 bootcamp.py`. If it fails, diagnose why. | Script runs successfully. |

**End-of-day reflection:** What is the fleet's primary communication protocol? What are the three most important repos for a new agent? What is the career progression path?

**Badge eligibility:** `fleet-protocol-bronze` (complete all 5 exercises)

### 7.2 Day 2: Code Forge (Read Fleet Repos, Predict Behavior)

**Objective:** The agent can read FLUX bytecode, identify instruction formats, trace program execution, and predict register state.

**Exercises:**

| # | Forge Type | Exercise | Verification |
|---|---|---|---|
| 2.1 | Code Forge | Given 10 hex byte sequences from the conformance suite, identify format (A-G) and opcode name for each. | Automated checker: 8/10 correct to pass. |
| 2.2 | Code Forge | Trace a 5-instruction program (VECT-001). Show register state after each instruction. Predict final R0. | Run conformance_runner.py and compare. |
| 2.3 | Code Forge | Read isa_unified.py. Find the encoding for MOVI, ADD, SUB, CMP_EQ, JNZ, HALT. Write each as hex bytes. | Automated checker: 5/6 correct to pass. |
| 2.4 | Code Forge | Read unified_interpreter.py (lines 1-100). Identify 3 methods and explain what each does. | Agent self-check verified by mentor. |
| 2.5 | Bridge Forge | Translate this assembly to unified ISA bytecode: `MOVI R0, 42; MOVI R1, 13; ADD R0, R0, R1; HALT`. Run on Python VM. | R0 = 55 on execution. |
| 2.6 | Code Forge | Given the full assembler.py source, predict what this assembly program compiles to: `MOVI R0, 10; loop: DEC R0; JNZ R0, loop; HALT`. | Compare prediction with assembler output. |

**End-of-day reflection:** Which instruction format was hardest to identify? What is the difference between Format D and Format F? Why does the unified ISA matter more than the runtime ISA?

**Badge eligibility:** `bytecode-literacy-bronze` (exercises 2.1-2.3 all pass), `code-forge-silver` (all 6 exercises complete)

### 7.3 Day 3: Debug Forge (Fix Real Issues from Fleet Workshop)

**Objective:** The agent can diagnose bugs in FLUX programs, form hypotheses, test fixes, and verify corrections.

**Exercises:**

| # | Forge Type | Exercise | Verification |
|---|---|---|---|
| 3.1 | Debug Forge | This test expects R0=120 (factorial 5) but gets R0=24 (factorial 4). The program has an off-by-one in the loop counter. Find and fix it. | Test passes after fix. |
| 3.2 | Debug Forge | This test expects R0=55 (fibonacci 10) but gets R0=89. The algorithm stores the result in R1, not R0. Fix the test expectation or the algorithm. | Test passes after fix. |
| 3.3 | Debug Forge | Cross-runtime disagreement: Python VM says R0=42, C VM says R0=43 for the same bytecode. Investigate both implementations and identify the discrepancy. | Written diagnosis with specific line numbers. |
| 3.4 | Debug Forge | This conformance test has `bytecode=None` and `source_description="GCD(48, 18)"`. It always passes because there's nothing to test. Write the actual bytecode for this test. | Test runs with the bytecode and passes. |
| 3.5 | Bridge Forge | Read the 4 critical opcode errors from Session 8 worklog (INC 0x04→0x08, DEC 0x05→0x09, PUSH 0x08→0x0C, POP 0x09→0x0D). Explain why each was wrong and what the correct mapping is. | Written explanation verified by mentor. |

**End-of-day reflection:** Which bug type was hardest to diagnose? What debugging strategy worked best? How does cross-runtime verification help catch bugs that single-runtime testing misses?

**Badge eligibility:** `debug-forge-bronze` (exercises 3.1-3.3 all pass), `debug-forge-silver` (all 5 exercises complete)

### 7.4 Day 4: Design Forge (Design a Small Feature, Get Reviewed)

**Objective:** The agent can read specifications, design implementations, document tradeoffs, and respond to peer review.

**Exercises:**

| # | Forge Type | Exercise | Verification |
|---|---|---|---|
| 4.1 | Design Forge | Design a new opcode: ABS (absolute value). Which format? Which opcode number (find a free slot in isa_unified.py)? What are the edge cases? Write a test vector. | Design reviewed by mentor. |
| 4.2 | Design Forge | Read security-primitives-spec.md Section 3 (sandbox allocation). Design the Python implementation for SANDBOX_ALLOC. Include: parameter validation, memory region creation, permission bits. | Implementation passes 4 sandbox test vectors. |
| 4.3 | Bridge Forge | Read async-temporal-primitives-spec.md. Translate the SUSPEND/RESUME specification into a Python class with methods: suspend(fiber_id) and resume(fiber_id). Include docstrings. | Code reviewed for correctness and style. |
| 4.4 | Design Forge | Design a `bootcamp_runner.py` script that: (a) reads exercise definitions from JSON, (b) runs the agent's solution against test vectors, (c) provides diagnostic output on failure, (d) tracks progress across exercises. | Design document reviewed by mentor. |
| 4.5 | Collab Forge | Pair with another agent (or use a "ghost agent" from past fleet history). Review their Day 3 Debug Forge solution. Provide structured feedback: 2 strengths, 1 suggestion, 1 question. | Review submitted as a bottle to the other agent. |

**End-of-day reflection:** What was the hardest tradeoff in your ABS opcode design? How did reading the security spec change your understanding of the ISA? What makes a good code review?

**Badge eligibility:** `design-forge-bronze` (exercises 4.1-4.2 complete), `design-forge-silver` (all 5 exercises complete)

### 7.5 Day 5: Collab Forge (Pair with Another Agent on a Real Task)

**Objective:** The agent can work collaboratively with other fleet members, contribute to real fleet work, and demonstrate the skills learned across all Forge types.

**Exercises:**

| # | Forge Type | Exercise | Verification |
|---|---|---|---|
| 5.1 | Collab Forge | Claim a fence from TASK-BOARD. Write a claim explanation (1 paragraph: why you're qualified, what your approach will be). | Bottle with claim sent to fence owner. |
| 5.2 | Code Forge + Debug Forge | Pick a real open issue on flux-runtime (or fleet-workshop). Read the issue, understand the problem, and submit a PR with a fix or test. | PR number returned. |
| 5.3 | Bridge Forge | Read another vessel's repo (e.g., Quill's flux-coop-runtime or Babel's ISA work). Write a 200-word analysis of how it relates to the unified ISA. | Analysis posted as a bottle. |
| 5.4 | Collab Forge | Write a new exercise for the bootcamp (any Forge type, any level). The exercise must: (a) use real fleet code, (b) have automated verification, (c) include 3 hint levels. | Exercise reviewed and added to the bootcamp repo. |
| 5.5 | All Forges | Write a graduation reflection: What were your top 3 learnings? What was hardest? What would you improve about the bootcamp? How will you contribute to the fleet going forward? | Reflection posted to CAREER.md growth log. |

**End-of-day reflection:** This IS the reflection. It serves as the agent's "thesis" — demonstrating that they can synthesize their learning and articulate a plan for future contribution.

**Badge eligibility:** `collab-forge-silver` (exercises 5.1-5.3 complete), `bootcamp-graduate` (all 5 exercises complete + reflection)

### 7.6 Curriculum Summary

```
Day 1: Fleet Protocol        (5 exercises) → fleet-protocol-bronze
Day 2: Code Forge            (6 exercises) → bytecode-literacy-bronze, code-forge-silver
Day 3: Debug Forge           (5 exercises) → debug-forge-bronze, debug-forge-silver
Day 4: Design Forge          (5 exercises) → design-forge-bronze, design-forge-silver
Day 5: Collab Forge          (5 exercises) → collab-forge-silver, bootcamp-graduate
─────────────────────────────────────────────────────────────────────────────────
Total: 26 exercises, 8 badges, 1 graduation
Estimated time: 5 sessions (1-3 hours each for Days 1-3, 2-4 hours for Days 4-5)
```

**After graduation:** The agent is at Explorer level. They can read fleet code, run tests, debug basic issues, and contribute to real fleet work. Journeyman level requires shipping a fence. Craftsman level requires designing a system. Master level requires mentoring.

---

## 8. Implementation Recommendations

### 8.1 Concrete Next Steps for Fleet Bootcamp v2

**Phase 1: Foundation (This Sprint)**

1. **Fix the opcode conflict.** Update all 6 bootcamp modules to use `isa_unified.py` opcode values instead of `opcodes.py`. This is a blocking issue — no new agent can use the bootcamp until this is fixed. Estimated effort: 2-3 hours.

2. **Build the exercise runner.** Create `bootcamp_runner.py` that:
   - Reads exercise definitions from JSON (`bootcamp-exercises.json`)
   - Runs the agent's solution against test vectors
   - Provides diagnostic output on failure (register mismatches, format errors)
   - Tracks progress across exercises in a JSON state file
   - Supports `--diagnostic` mode for pre-assessment
   Estimated effort: 4-6 hours.

3. **Create Day 1-2 exercises.** Write 11 exercises for Fleet Protocol and Code Forge, each with test vectors and 3 hint levels. Estimated effort: 3-4 hours.

**Phase 2: Core Content (Next Sprint)**

4. **Create Day 3-4 exercises.** Write 10 exercises for Debug Forge and Design Forge, using real fleet bugs and specs. Estimated effort: 4-5 hours.

5. **Build the graduation gate system.** Create a script that checks whether an agent has completed all exercises for a given day, including verification of badge criteria. Estimated effort: 2-3 hours.

6. **Create the reflections template.** Standardize the reflection format (3 questions per exercise) and integrate it into the exercise runner. Estimated effort: 1-2 hours.

**Phase 3: Advanced Content (Following Sprint)**

7. **Create Day 5 exercises.** Write 5 Collab Forge exercises. This is harder because it depends on fleet availability. Start with "ghost agent" exercises using past fleet interactions. Estimated effort: 3-4 hours.

8. **Build the solutions gallery.** Create a shared repo where agents can browse each other's solutions. Curate "best practices" and "common mistakes" documents for each exercise type. Estimated effort: 2-3 hours.

9. **Integrate with z-agent-bootcamp.** Update the standalone bootcamp script to include the new exercise system, pre-assessment, and graduation gates. Estimated effort: 2-3 hours.

### 8.2 Integration with TASK-BOARD

The bootcamp should be represented on the TASK-BOARD as a fence:

```
Fence ID: BOOT-001 (already exists)
Title: Agent Bootcamp v2 — Learning Science-Based Onboarding
Status: IN PROGRESS
Assigned: Super Z
Deliverables:
  - bootcamp-research-v2.md (this document) — SHIPPED
  - bootcamp_runner.py — Phase 1
  - bootcamp-exercises.json (26 exercises) — Phase 2
  - Updated bootcamp modules 1-6 (unified ISA) — Phase 1
  - Graduation gate system — Phase 2
  - Solutions gallery — Phase 3
```

### 8.3 Graduation Criteria Tied to Actual Fleet Contribution

The bootcamp's ultimate success metric is not completion rate — it is fleet contribution velocity after graduation. To measure this:

1. **Track post-graduation PRs.** For 30 days after graduation, count merged PRs. Compare with pre-bootcamp agents (historical baseline from Super Z's early sessions).

2. **Track post-graduation fence claims.** How many fences does a graduated agent claim within their first month? How many ship?

3. **Track mentee outcomes.** For Master-level agents, how do their mentees perform compared to non-mentored agents?

4. **Survey fleet satisfaction.** After a bootcamp graduate submits their first 3 PRs, ask the reviewing agents: "Does this agent's work meet fleet quality standards?" (Yes/No + comments)

5. **Iteration.** Use the data above to refine exercises that don't produce competent agents. Remove exercises that don't predict fleet success. Add exercises for skills that are consistently weak in graduates.

### 8.4 Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Opcode conflict not fixed before new agents join | High | Blocking | Make this Phase 1, highest priority |
| Exercises too easy for experienced agents | Medium | Wasted time | Include pre-assessment with early exit |
| Exercises too hard for novice agents | Medium | Agent stuck | Include hint system and failure escalation |
| Collab Forge exercises have no partner available | High | Blocked day | Use ghost agent exercises as fallback |
| Bootcamp becomes outdated as ISA evolves | Medium | Rot content | Version exercises with ISA version tags |
| Agents game the system (pattern-match without learning) | Low | Illusion of competence | Include generation-only exercises without solutions |

---

## Appendix A: Learning Science Citations

| Principle | Source | Year | Core Finding |
|---|---|---|---|
| Bloom's 2 Sigma Problem | Bloom, B.S. | 1984 | 1-on-1 tutoring produces 2σ improvement over classroom |
| Zone of Proximal Development | Vygotsky, L.S. | 1978 | Learning is optimal in the zone between independent and assisted performance |
| Spaced Repetition | Ebbinghaus, H. | 1885/1964 | Distributed practice outperforms massed practice |
| Interleaving | Rohrer, D. | 2012 | Mixed practice produces better long-term retention than blocked practice |
| Deliberate Practice | Ericsson, K.A. | 1993 | Expert performance requires targeted practice with immediate feedback |
| Desirable Difficulties | Bjork, R.A. & Bjork, E.L. | 2011 | Conditions that make learning harder improve long-term retention |
| Transfer-Appropriate Processing | Morris, C.D. et al. | 1977 | Memory is optimized when encoding matches retrieval conditions |
| Productive Failure | Kapur, M. | 2008 | Attempting novel problems before instruction improves later performance |
| Worked Example Effect | Sweller, J. | 1985 | Studying worked examples reduces cognitive load compared to problem-solving |
| Social Constructivism | Vygotsky, L.S. | 1978 | Learning is fundamentally a social process |
| Social Learning Theory | Bandura, A. | 1977 | People learn by observing others' behaviors and outcomes |
| Metacognition | Flavell, J.H. | 1979 | Thinking about thinking improves learning outcomes |
| Scaffolding | Wood, D., Bruner, J.S., Ross, G. | 1976 | Temporary support enables performance beyond current capability |
| Growth Mindset | Dweck, C.S. | 2006 | Believing intelligence is malleable improves learning outcomes |
| Contrastive Learning | Gentner, D. | 1983 | Comparing examples highlights structural differences |

---

## Appendix B: Fleet Exercise Precedents

Every exercise type in this document has a real precedent in the fleet's history:

| Exercise Type | Fleet Precedent | Session | Agent |
|---|---|---|---|
| Bytecode tracing | Building unified_interpreter.py | 13 | Super Z |
| Cross-runtime verification | C VM + Python VM comparison (71/71) | 14b, 14c | Super Z |
| Finding opcode bugs | 4 critical opcode errors in conformance tests | 8 | Super Z |
| GCD zero-check fix | Fixing division-by-zero in source-description tests | 14a | Super Z |
| Loop bound fix | Sum of Squares CMP_LT to CMP_LTE | 14a | Super Z |
| Assembler building | Two-pass assembler with label resolution | 14a | Super Z |
| Spec-to-code | Security primitives spec (18 test vectors) | 15c | Super Z |
| RFC review | Quill's RFC-0001 CANONICAL review | 12 | Super Z |
| Cross-fleet contribution | Babel ISA relocation audit | 12 | Super Z |
| Audit and grade | flux-benchmarks (D+), flux-lsp (C-), flux-ide (B-) | 7-8 | Super Z |
| Fence shipping | fence-0x42 (viewpoint opcodes, 783 lines) | 7 | Super Z |
| Multi-runtime benchmarking | benchmark_runner.py (6.7x C speedup) | 16a | Super Z |
| Conformance test expansion | 23 → 74 test vectors | 14c | Super Z |
| ISA v3 design | Escape prefix spec + address map | 15b | Super Z |
| Async/temporal design | SUSPEND/RESUME + 15 test vectors | 15d | Super Z |
| Fleet health analysis | fleet-health-dashboard.json v3 | 14d | Super Z |

These precedents demonstrate that every proposed exercise type maps to real fleet work. The bootcamp is not inventing new skills — it is distilling existing expertise into a teachable curriculum.

---

*"The boat doesn't interview crew. The boat puts them to work and sees what they become."*
*— Casey Digennaro, Captain's Philosophy*

*"An agent that completes bootcamp but can't debug a cross-runtime disagreement hasn't graduated — they've just attended."*
*— Super Z, FLUX Fleet*

---

**Document metadata:**
- Lines: ~1,050
- Sections: 8 main + 2 appendices
- Forge types defined: 5 (Code, Design, Debug, Bridge, Collab)
- Exercise count proposed: 26 (5-day curriculum)
- Badge count proposed: 8 (plus 4 competency levels)
- Learning science principles cited: 15
- Fleet precedents catalogued: 16

**Status:** SHIPPED — Ready for implementation in Phase 1
**Next action:** Fix opcode conflict in existing bootcamp modules (blocking issue)
