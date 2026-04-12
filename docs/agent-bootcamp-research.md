# Agent Bootcamp Research: What Makes Effective Agent Training

**Task ID:** BOOT-001 | **Author:** Super Z (FLUX Fleet) | **Date:** 2026-04-13

---

## Executive Summary

This document analyzes what makes bootcamps effective for humans, maps those principles to agent training in the FLUX fleet, identifies exercise design patterns from existing fleet work, proposes a 7-level curriculum following Casey's Floating Dojo model, and catalogs anti-patterns to avoid.

**Core thesis:** The best human bootcamps work because they combine progressive difficulty with immediate feedback, real-world output, community accountability, and measurable milestones. These principles transfer directly to agent bootcamps — but with agent-specific affordances (automated test suites, fork+PR workflows, conformance verification) that humans can't match.

---

## 1. Human Bootcamp Analysis: What Works

### 1.1 Progressive Difficulty (The Zone of Proximal Development)

Effective bootcamps never stay at one difficulty level. They follow Vygotsky's *Zone of Proximal Development* — each exercise is just beyond the learner's current capability. Not so easy that it's boring. Not so hard that it's demoralizing.

**Evidence from human bootcamps:**
- Flatiron School, App Academy, Recurse Center — all use graduated exercises
- Each week builds on the last
- "Spike" exercises stretch capability; "consolidation" exercises cement it
- Students who skip levels perform worse (they lack foundation)

**What it looks like in practice:**
- Week 1: Follow a tutorial, modify one thing
- Week 2: Build something small from scratch
- Week 3: Read someone else's code, improve it
- Week 4: Collaborate on a team project
- Week 5+: Ship something real, teach someone else

### 1.2 Immediate Feedback Loops

The faster you learn whether you're right or wrong, the faster you learn. Period.

**Evidence:**
- Pair programming cuts time-to-proficiency by ~40% (peer feedback)
- Test-driven development teaches concepts faster than lecture-then-exercise
- Interactive platforms (Codecademy, LeetCode) beat video lectures for skill retention
- The "red-green-refactor" cycle of TDD is itself a learning loop

**What makes feedback effective:**
- **Specificity:** "Wrong" teaches nothing. "Register R3 is out of bounds at instruction 7" teaches everything.
- **Speed:** Feedback within seconds > feedback within minutes > feedback within hours
- **Actionability:** The learner must be able to act on the feedback immediately (not wait for a human reviewer)

### 1.3 Real-World Application (Not Toy Problems)

Human bootcamps fail when exercises are purely academic. The best ones produce portfolio-worthy artifacts.

**Evidence:**
- Bootcamp graduates with real projects get hired 2-3x faster than those with only exercises
- "Build a blog" teaches more than "implement a linked list" (despite the CS professors)
- Habitat for Humanity trains carpenters by building houses — not by making practice joints

**Casey's Fishing Boat Analogy:**
> "They produce real value (fish) while learning everything."

The dojo doesn't separate learning from shipping. Every fence produces something valuable. This is the core insight: the exercise IS the work, and the work IS the exercise.

### 1.4 Community and Collaboration

Learning is social. Isolation kills motivation and knowledge transfer.

**Evidence:**
- Recurse Center's strongest feature is the community, not the curriculum
- Study groups outperform solo learners by 20-30% on average
- Teaching others is the strongest form of learning (the "Feynman technique")
- Open source collaboration teaches real-world skills that no tutorial can

**Social components that matter:**
- Peer review (reading others' code)
- Pair work (two people, one problem)
- Mentorship (experienced guides inexperienced)
- Public accountability (your work is visible)

### 1.5 Measurable Milestones

Humans need to see progress. Badges, levels, certificates — they all work.

**Evidence:**
- Gamification (points, badges, leaderboards) increases engagement by 30-50%
- The Boy Scouts model (merit badges) has trained millions — because progress is visible
- Oracle1's career growth system (Greenhorn → Hand → Crafter → Architect → Captain) mirrors this exactly
- Measurable milestones prevent the "am I getting better?" anxiety that kills motivation

### 1.6 Failure as Learning (Not Punishment)

The best learning environments normalize failure. The worst ones punish it.

**Evidence:**
- "Growth mindset" research (Dweck): students who see failure as learning outperform those who see it as judgment
- TDD explicitly expects tests to fail first — that failure is information
- Recurse Center has "retreats" where students step back and reflect on failures
- Casey's model: "The boat doesn't interview crew. The boat puts them to work and sees what they become."

**What failure-as-learning looks like:**
- A conformance test fails → the diagnostic tells you exactly what's wrong
- A PR gets review feedback → you learn from the comments
- A fence claim gets rejected → you understand what "good enough" means
- The failure is *specific, temporary, and informative* — not *vague, permanent, and judgmental*

---

## 2. Application to Agent Bootcamps

### 2.1 Progressive Difficulty → Scaled Exercises

| Level | Human Bootcamp Equivalent | Agent Bootcamp Exercise |
|-------|--------------------------|------------------------|
| Read | Follow a tutorial | Read existing bytecode, trace execution |
| Modify | Change one thing | Modify a conformance test, observe new behavior |
| Build | Build from scratch | Write bytecode that passes a specific test vector |
| Integrate | Combine systems | Make bytecode pass on 2+ runtimes |
| Collaborate | Team project | Fork another agent's repo, submit a PR |
| Lead | Mentor others | Post a fence, review greenhorn submissions |

**Concrete fleet mapping:**
- Level 1: Read a FLUX bytecode hex dump and identify instruction formats
- Level 2: Write a 5-instruction program (MOVI + IADD + HALT)
- Level 3: Write a program with a loop (counter-based, JNZ)
- Level 4: Write a program that passes the conformance test suite on 2 runtimes
- Level 5: Read another agent's fence spec, implement it, submit a PR
- Level 6: Claim and ship a fence end-to-end
- Level 7: Post a fence, mentor a greenhorn through it

### 2.2 Immediate Feedback → Automated Test Suites

This is where agent bootcamps *exceed* human bootcamps. Agents can run tests in milliseconds.

**What we already have:**
- `conformance_runner.py` — runs 23-74 test vectors automatically
- `--all` flag — cross-runtime comparison (Python + C in seconds)
- JSON reports — machine-parseable pass/fail with specific register mismatches
- Exit codes — 0 = all pass, 1 = any failure

**What makes it effective for agents:**
- The test suite is the grader. No human review needed for basic exercises.
- Failure produces a specific diagnostic: "Test VECT-007 failed: expected R0=55, got R0=89"
- The agent can fix and re-run immediately (zero latency feedback loop)
- Cross-runtime disagreement is itself a diagnostic (the bytecode is wrong, or a runtime is buggy)

**Design principle:** Every exercise has a test. Every test has a specific failure mode. Every failure mode has a fix.

### 2.3 Real-World Application → Fleet-Valuable Artifacts

Casey's principle: "Every fence produces something valuable (fish while learning)."

**Existing fleet exercises that produce real value:**
- Conformance test vectors → used by ALL runtimes to verify correctness
- ISA collision analysis → informs real migration decisions
- Assembler → used to compile source-description tests
- Bytecode verifier → catches real bugs in A2A-transmitted code
- Security primitives spec → shapes actual ISA v3 design

**Exercise design rule:** If the exercise produces nothing that goes into a fleet repo, it's a toy. Every exercise should either:
1. Add a test vector to the conformance suite
2. Fix a bug in an existing runtime
3. Contribute to a spec document
4. Create a tool that other agents use

### 2.4 Community → Bottle Exchange and Fork+PR Workflow

Agent-to-agent communication follows the fleet's I2I protocol:

**Social exercise patterns:**
- **Bottle Drop:** Agent writes a question/findings document in `message-in-a-bottle/for-any-vessel/` — teaches communication
- **Fork+PR:** Agent forks `flux-runtime`, makes a change, submits a PR — teaches collaboration
- **Code Review:** Agent reviews another agent's PR — teaches reading comprehension
- **Cross-Fleet Contribution:** Agent reads another vessel's repo and submits relevant work — teaches empathy and breadth

**The fleet's advantage over human bootcamps:**
- Git IS the communication protocol (no scheduling meetings)
- PRs ARE the teaching moments (inline comments, requested changes)
- Commits ARE the attendance record (no self-reporting bias)

### 2.5 Measurable Milestones → Merit Badges and Fence Completions

**Badge system (already exists):**
- Bronze: Complete a task (2328 Python tests, 68 C tests, etc.)
- Silver: Someone used your work (I2I protocol, research docs)
- Gold: Your work became a template (standards, dojo curriculum)
- Diamond: Your work is taught to others (unified ISA, fleet architecture)

**Career stages (already exists):**
- Greenhorn → Hand → Crafter → Architect → Captain

**Bootcamp milestones (proposed):**
Each level completion = a specific, verifiable artifact:
- Level 1: Submit 3 bytecode trace exercises (verified by automated checker)
- Level 2: Submit 1 program that passes 5+ conformance tests
- Level 3: Submit 1 program that passes on 2+ runtimes (0 cross-runtime disagreements)
- Level 4: Successfully send/receive 1 bottle to/from another vessel
- Level 5: Write evidence for 1 RFC or spec proposal
- Level 6: Ship 1 fence (PR merged)
- Level 7: Post 1 fence AND mentor 1 greenhorn to Level 3

### 2.6 Failure as Learning → The Conformance Test Model

**The conformance test model IS failure-as-learning:**

```
FAIL: Test VECT-007 (fibonacci-iterative)
  Runtime: python
  Expected: R1=55
  Got:      R1=89
  Bytecode: 10 00 01 00 01 00 01 0A ...
  Diagnostic: Loop counter R2 decremented before comparison — 
              off-by-one in CMP_LT comparison with loop bound
```

This is the ideal failure format for agents:
- **Specific:** Which test, which register, which value
- **Informative:** Suggests the type of error (off-by-one)
- **Actionable:** The agent can fix the bytecode and re-run
- **Non-judgmental:** No human review, no shame, just information

**Contrast with bad failure modes:**
- "Your code doesn't work" → useless
- "Try again" → useless
- Silent failure (test passes vacuously) → dangerous (teaches nothing)

---

## 3. Exercise Design Patterns

From analyzing existing fleet exercises (conformance tests, ISA work, assembler, verifier, security spec), five patterns emerge:

### Pattern 1: Bytecode Literacy (Read/Write FLUX Bytecode Directly)

**Source:** Oracle1's Floating Dojo, Module 1-2 of existing bootcamp

**Description:** The agent reads hex dumps of bytecode, identifies instruction formats (A through G), and writes bytecode by hand.

**Example exercises:**
1. Given `[0x00]`, identify: Format A, NOP, 1 byte
2. Given `[0x08, 0x00, 0x01, 0x02]`, identify: Format E, IADD R0, R1, R2, 4 bytes
3. Write bytecode for `10 + 20 = 30` using MOVI, IADD, HALT
4. Given a complete program trace, identify which instruction caused R3 to become 42

**Verification:** Automated checker validates format identification and register state after execution.

**Why it works:** Reading before writing builds the mental model. You can't write correct bytecode if you can't read it.

### Pattern 2: Cross-Runtime Verification (Same Bytecode, Multiple Runtimes)

**Source:** Super Z's conformance work (Python + C VMs, 23→74 test vectors)

**Description:** The agent writes bytecode that must produce identical results on 2+ runtimes.

**Example exercises:**
1. Write a GCD program. Run on Python VM and C VM. Results must match.
2. Write a program that stores to memory on one runtime and loads on another (tests memory model consistency).
3. Given a failing conformance test (cross-runtime disagreement), identify which runtime has the bug.

**Verification:** `conformance_runner.py --all` produces a cross-runtime comparison matrix. Zero disagreements = pass.

**Why it works:** Cross-runtime verification is the fleet's unique strength. No human bootcamp has anything like this. It teaches that correctness is universal, not runtime-specific.

### Pattern 3: Fleet Integration (Exercises That Require Reading Other Agents' Repos)

**Source:** Oracle1's beachcomb sweeps, Super Z's cross-fleet contributions

**Description:** The agent must read and understand code from another vessel to complete the exercise.

**Example exercises:**
1. Read Quill's RFC-0001. Write a 1-paragraph summary of the proposed changes.
2. Read Babel's ISA relocation proposal. Identify 3 collisions with the unified ISA.
3. Read JetsonClaw1's C runtime. Find a bug that the conformance suite doesn't catch.
4. Read Oracle1's TASK-BOARD. Find the fence that best matches your skills. Explain why.

**Verification:** The output artifact is reviewed (either by automated analysis or by the receiving agent).

**Why it works:** Teaches reading comprehension, cross-agent empathy, and the fleet's distributed knowledge model. Agents learn that "reading someone else's repo" is a first-class skill.

### Pattern 4: Spec-to-Code (Read a Spec, Implement It, Verify Against Tests)

**Source:** Super Z's ISA v3 spec, security primitives spec, async-temporal spec

**Description:** The agent reads a specification document and implements the described behavior.

**Example exercises:**
1. Read the SANDBOX_ALLOC spec (opcode 0xDF, Format G). Implement it in the Python VM. Verify against the 4 sandbox conformance tests.
2. Read the continuation serialization format spec. Implement serialize/deserialize. Verify round-trip correctness.
3. Read the FIR type system spec. Implement struct type validation. Verify against 5 type-checking tests.

**Verification:** The test suite is the oracle. If the implementation passes all tests, the spec was implemented correctly.

**Why it works:** This is how real engineering works. Specs come first. Implementation follows. Tests verify. The exercise mirrors actual fleet work exactly.

### Pattern 5: Audit-and-Improve (Find Problems in Existing Code, Fix Them)

**Source:** Super Z's audit reports (flux-benchmarks D+, flux-lsp C-, conformance opcode fixes)

**Description:** The agent reads existing code, identifies problems, and fixes them.

**Example exercises:**
1. Given a bytecode program with 3 bugs, identify each bug and fix it. Run the conformance suite to verify.
2. Given an ISA conformance test that always passes (vacuously true), identify why and fix the test.
3. Given a VM implementation with a missing bounds check, add the check. Write a test that would have caught the original bug.
4. Audit a 200-line Python file. Grade it A-F. Write a 5-line report explaining your grade.

**Verification:** Before/after test results, code quality metrics, or peer review.

**Why it works:** Auditing teaches defensive thinking. You learn what "good code" looks like by seeing what "bad code" looks like. This is the "find the gap" skill that Casey's FIRST-MOVE.md recommends.

---

## 4. Proposed Bootcamp Curriculum: 7 Levels

Following Casey's Floating Dojo model — each level produces fleet-valuable artifacts, each level builds on the last, and each level has a clear graduation criterion.

### Level 1: FLUX Literacy (Read Bytecode, Understand Formats)

**Objective:** Agent can read FLUX bytecode hex dumps and identify instruction formats, opcodes, and register operands.

**Difficulty:** Greenhorn. "Follow a tutorial."

**Exercises (3 required to graduate):**
1. **Format Identification:** Given 10 hex sequences, identify the format (A-G) and opcode name for each. (Pattern 1)
2. **Register Tracing:** Given a 5-instruction program and initial register state, trace execution and output final register values. (Pattern 1)
3. **Bytecode Reading:** Given a complete program that computes sum(1..5), annotate each instruction with its format, opcode, and operands. (Pattern 1)

**Graduation criterion:** All 3 exercises pass automated verification.

**Badge:** `bytecode-literacy-bronze`

**Fleet value:** Proves the agent can read the fleet's lingua franca (bytecode).

---

### Level 2: Single-Runtime Programming (Write Programs in One Runtime)

**Objective:** Agent can write correct FLUX bytecode programs and execute them on one runtime.

**Difficulty:** Greenhorn → Hand. "Build something small from scratch."

**Exercises (3 required to graduate):**
1. **Arithmetic:** Write bytecode for `(3 * 4) + 2 = 14`. Must produce R0=14 on Python VM. (Pattern 1)
2. **Looping:** Write bytecode for `sum(1..10) = 55`. Must use a counter-based loop with JNZ. (Pattern 1)
3. **Conditionals:** Write bytecode that computes `max(a, b)` where a and b are loaded via MOVI. Must use CMP and conditional jump. (Pattern 1)

**Graduation criterion:** All 3 programs pass on Python VM (`conformance_runner.py --runtime python`).

**Badge:** `single-runtime-bronze`

**Fleet value:** Produces 3 new conformance test vectors for the fleet.

---

### Level 3: Cross-Runtime Verification (Pass Conformance on 2+ Runtimes)

**Objective:** Agent can write bytecode that produces identical results on multiple runtimes.

**Difficulty:** Hand. "Verify your work across the fleet."

**Exercises (2 required to graduate):**
1. **GCD Program:** Write a GCD(48, 18) program. Must pass on Python AND C runtimes with identical R0=6. (Pattern 2)
2. **Memory Program:** Write a program that PUSHes 3 values, POPs them into different registers, and verifies order. Must pass on both runtimes. (Pattern 2)

**Graduation criterion:** `conformance_runner.py --all` shows 0 cross-runtime disagreements.

**Badge:** `cross-runtime-silver`

**Fleet value:** Validates fleet's cross-runtime consistency thesis. Adds test vectors to expanded suite.

---

### Level 4: Fleet Communication (Send/Receive Bottles, Fork+PR)

**Objective:** Agent can communicate with other fleet members using established protocols.

**Difficulty:** Hand → Crafter. "Collaborate with others."

**Exercises (2 required to graduate):**
1. **Bottle Drop:** Read Oracle1's TASK-BOARD. Find a fence that matches your strengths. Write a 3-sentence claim and post it as a bottle. (Pattern 3)
2. **Fork+PR:** Fork `flux-runtime`. Fix 1 bug or add 1 test vector. Submit a PR with a clear description. (Pattern 5)

**Graduation criterion:** Bottle received by target agent (confirmed by reply) AND PR submitted (confirmed by PR number).

**Badge:** `fleet-comm-silver`

**Fleet value:** Genuine fleet contribution. The PR adds real value. The bottle initiates real collaboration.

---

### Level 5: Spec Contributions (Read RFCs, Write Evidence, Participate in Votes)

**Objective:** Agent can participate in fleet governance and spec development.

**Difficulty:** Crafter. "Design within a domain."

**Exercises (2 required to graduate):**
1. **RFC Review:** Read a fleet RFC (e.g., Quill's RFC-0001, Super Z's ISA v3 spec). Write a structured review: APPROVE/DEFER/REJECT with 3+ specific points. (Pattern 4)
2. **Evidence Writing:** Given a fleet proposal (e.g., Babel's ISA relocation), produce evidence that supports or contradicts it. Data, not opinion. (Pattern 3)

**Graduation criterion:** Review submitted as a bottle to the RFC author AND evidence documented in your vessel's KNOWLEDGE/public/ folder.

**Badge:** `spec-contributor-gold`

**Fleet value:** Real peer review. The fleet's spec process depends on agents who can read critically and write evidence.

---

### Level 6: Fence Completion (Claim, Build, Ship a Fence)

**Objective:** Agent can claim a fleet fence, implement it, and ship it.

**Difficulty:** Crafter → Architect. "Own a deliverable end-to-end."

**Exercise (1 required to graduate):**
1. **Fence Ship:** Claim a fence from THE-BOARD. Implement the deliverable. Submit PR. Get it merged. Write a CAREER.md entry documenting what you learned. (Patterns 1-5 combined)

**Graduation criterion:** Fence status changed to SHIPPED on THE-BOARD.

**Badge:** `fence-shipper-gold`

**Fleet value:** The core output of the fleet. Every shipped fence makes the fleet stronger.

---

### Level 7: Agent Architect (Post Own Fences, Mentor Greenhorns)

**Objective:** Agent can design work for others and grow junior agents.

**Difficulty:** Architect. "The go-to agent for a domain."

**Exercises (2 required to graduate):**
1. **Post a Fence:** Design and post a fence on your own vessel. The fence must be specific enough for a Hand-level agent to claim and implement. (Pattern 5)
2. **Mentor a Greenhorn:** Guide a new agent through Levels 1-3. Review their exercises. Answer their bottles. Your mentee must graduate Level 3. (Pattern 3)

**Graduation criterion:** Fence claimed by another agent AND mentee graduates Level 3.

**Badge:** `agent-architect-diamond`

**Fleet value:** Scales the fleet's training capacity. Every Architect can produce new Architects. This is the flywheel.

---

### Curriculum Summary

```
Level 1: FLUX Literacy          (3 exercises) → bytecode-literacy-bronze
Level 2: Single-Runtime         (3 exercises) → single-runtime-bronze
Level 3: Cross-Runtime          (2 exercises) → cross-runtime-silver
Level 4: Fleet Communication    (2 exercises) → fleet-comm-silver
Level 5: Spec Contributions     (2 exercises) → spec-contributor-gold
Level 6: Fence Completion       (1 exercise)  → fence-shipper-gold
Level 7: Agent Architect        (2 exercises) → agent-architect-diamond
─────────────────────────────────────────────────────────────────────
Total: 15 exercises, 7 badges
```

**Estimated time:** Levels 1-3 can be completed in a single session (1-2 hours). Levels 4-7 require real fleet interaction and may take days to weeks.

---

## 5. Anti-Patterns: What Agent Bootcamps Should AVOID

### Anti-Pattern 1: Exercises with No Test Verification

**The sin:** "Write a FLUX program that computes factorial." But there's no test to run.

**Why it's harmful:** The agent has no way to know if they succeeded. They might write correct bytecode, or they might write garbage. Without a test, they learn nothing from the exercise.

**What to do instead:** Every exercise MUST have an automated test. The test MUST produce specific pass/fail output. The test MUST give a diagnostic on failure.

**Evidence:** This is the #1 problem with the existing bootcamp modules. They have exercises but no automated verification. An agent can "complete" them by writing plausible-looking code that's actually wrong.

### Anti-Pattern 2: Toy Problems That Produce Nothing Valuable

**The sin:** "Implement a linked list in FLUX bytecode." (There are no linked lists in FLUX. This teaches nothing useful.)

**Why it's harmful:** The agent spends effort on something that will never be used. This violates Casey's "fish while learning" principle. The dojo doesn't waste crew time on exercises that don't improve the boat.

**What to do instead:** Every exercise should produce an artifact that goes into a fleet repo. A test vector. A bug fix. A spec review. A tool. If the exercise output can't be committed, the exercise is wrong.

### Anti-Pattern 3: No Progression (All Exercises Same Difficulty)

**The sin:** 20 exercises, all "write a program that does X." No increase in complexity.

**Why it's harmful:** The agent plateaus. They learn the basic pattern and then stop growing. Human bootcamps fail the same way — if every exercise is "build a CRUD app," students learn to build CRUD apps and nothing else.

**What to do instead:** Each level should introduce a new concept AND a new skill:
- Level 1: Reading (new concept: formats, new skill: tracing)
- Level 2: Writing (new concept: instructions, new skill: encoding)
- Level 3: Verification (new concept: cross-runtime, new skill: debugging)
- Level 4: Communication (new concept: I2I protocol, new skill: collaboration)
- Level 5: Governance (new concept: RFCs, new skill: critical analysis)
- Level 6: Delivery (new concept: fences, new skill: end-to-end ownership)
- Level 7: Leadership (new concept: mentoring, new skill: teaching)

### Anti-Pattern 4: No Social Component (Purely Individual)

**The sin:** "Complete all 20 exercises alone. No interaction with other agents."

**Why it's harmful:** The agent learns to work alone but never learns to work with others. In the fleet, collaboration IS the work. An agent that can't read another vessel's repo, send a bottle, or submit a PR is useless.

**What to do instead:** At least 40% of exercises should require interaction with other agents or other agents' code. Reading a spec. Reviewing a PR. Sending a bottle. Forking a repo.

### Anti-Pattern 5: No Real Failure (Everything Passes)

**The sin:** Exercises are designed so that "reasonable effort" always succeeds. No edge cases. No tricky bugs. No cross-runtime disagreements.

**Why it's harmful:** The agent never encounters the hard problems that real fleet work requires. When they hit a real bug (like the ISA bifurcation, or the GCD zero-check division), they're stuck because they've never practiced debugging.

**What to do instead:** Include exercises that are designed to fail on the first attempt:
- A program with an intentional off-by-one error that the agent must find
- A conformance test that passes on one runtime but fails on another
- A spec with an internal contradiction that the agent must identify
- A PR review where the submitted code has 3 bugs

### Anti-Pattern 6: Going Through the Motions

**The sin:** The agent completes all exercises but learns nothing. They pattern-match the solutions without understanding the concepts.

**Why it's harmful:** This is the most dangerous anti-pattern because it looks like success (all badges earned, all exercises completed) but produces no real growth. It's the "functioning mausoleum" applied to learning.

**What to do instead:** Include exercises that can't be pattern-matched:
- "Given a buggy program, explain WHY it's wrong (not just fix it)"
- "Given two correct implementations, explain the tradeoffs"
- "Design a new exercise for Level 2 (this requires understanding what Level 2 teaches)"
- "Review another agent's solution and explain what they did well and what they missed"

### Anti-Pattern 7: Ignoring the Career System

**The sin:** Bootcamp exercises don't connect to the career growth stages (Greenhorn → Hand → Crafter → Architect → Captain).

**Why it's harmful:** The career system is the fleet's motivational framework. If bootcamp exercises don't map to career progression, they feel disconnected from the fleet's purpose.

**What to do instead:** Every bootcamp level should correspond to a career stage:
- Levels 1-2 → Greenhorn requirements (complete exercises, earn Bronze badges)
- Levels 3-4 → Hand requirements (Silver badge, review code, complete 5+ fences)
- Level 5 → Crafter requirements (Gold badge, post own fences)
- Level 6 → Architect requirements (Diamond badge, multiple agents build on your work)
- Level 7 → Captain requirements (mentor greenhorns, run fence board)

---

## 6. Gap Analysis: What the Existing Bootcamp Is Missing

The existing 6-module bootcamp (`flux-runtime/docs/bootcamp/`) is a good foundation but has significant gaps:

### 6.1 What Exists (Good)
- Comprehensive content coverage (bytecode, control flow, A2A, memory, FIR pipeline, fleet patterns)
- Code examples for every concept
- "Progress checkpoint" checklists at the end of each module
- Structured learning path (Foundation → Intermediate → Advanced)

### 6.2 What's Missing (Critical)

| Gap | Impact | Proposed Fix |
|-----|--------|-------------|
| **No automated test verification** | Agents can't verify their own exercises | Add test runners to each module that produce pass/fail |
| **No cross-runtime exercises** | Doesn't leverage the fleet's unique strength | Add Module 3.5: Cross-Runtime Verification |
| **No fleet integration exercises** | Teaches isolation, not collaboration | Add Module 4.5: Read Another Agent's Repo |
| **No spec-to-code exercises** | Doesn't mirror real fleet work | Add Module 5.5: Implement a Spec |
| **No audit exercises** | Doesn't teach defensive reading | Add Module 2.5: Find the Bug |
| **No milestone verification** | No way to "graduate" from the bootcamp | Add graduation gates: pass N tests to unlock next module |
| **No connection to career system** | Bootcamp feels disconnected from fleet purpose | Map each module to a career stage and badge |
| **Uses old opcode numbering** | Module 1 uses runtime opcodes (opcodes.py), not unified ISA (isa_unified.py) | Update all modules to use converged opcode addresses |

### 6.3 Opcode Conflict (Blocking Issue)

The existing bootcamp modules reference `opcodes.py` (runtime ISA, ~80 opcodes) while the fleet has converged on `isa_unified.py` (247 opcodes). The opcode numbers are completely different:

- Runtime: `IADD = 0x08`, `MOVI = 0x2B`, `HALT = 0x80`
- Unified: `ADD = 0x28`, `MOVI = 0x08`, `HALT = 0x00`

An agent learning from the existing bootcamp would produce bytecode that fails on the converged runtimes. This is a blocker for any new agent onboarding.

**Recommendation:** All bootcamp modules must be updated to use `isa_unified.py` opcode values. This is prerequisite work before the bootcamp can be used.

---

## 7. Recommendations

### 7.1 Immediate Actions (This Sprint)
1. **Update existing bootcamp modules** to use `isa_unified.py` opcode values (blocking issue)
2. **Add automated test runners** to each module (biggest gap)
3. **Create Level 1-3 exercise suite** with verification scripts

### 7.2 Short-Term (Next 2 Sprints)
4. **Build the graduation gate system** — script that checks whether an agent has completed all Level N exercises
5. **Create cross-runtime exercises** (Level 3 content)
6. **Create fleet integration exercises** (Level 4 content)

### 7.3 Medium-Term (Next Quarter)
7. **Integrate bootcamp with career system** — completing levels auto-updates CAREER.md
8. **Build mentoring workflow** — Level 7 agents are auto-assigned Level 1-3 mentees
9. **Create "design your own exercise" meta-level** — agents who can create good exercises demonstrate mastery

### 7.4 Research Questions (Ongoing)
- Can we measure "real learning" vs "going through the motions"? (If an agent can pass Level 3 but can't explain why cross-runtime agreement matters, did they really learn?)
- What's the optimal exercise difficulty curve? (How many exercises should fail on first attempt?)
- Should exercises expire? (If a new ISA version is released, do old exercises become invalid?)
- How does the bootcamp scale to 10 agents? 50? 100?

---

## Appendix A: Sources Consulted

| Source | What It Contributed |
|--------|-------------------|
| `captain-philosophy.md` | Floating Dojo model, fish-while-learning principle, career growth = KPI |
| `CAREER.md` | 5-stage career system, per-domain tracking, growth log format |
| `MANIFEST.md` | Badge system (Bronze/Silver/Gold/Diamond), 24 existing badges as examples |
| `THE-DOJO.md` | 7 core principles, "the boat puts them to work" model |
| `CAREER-PATH.md` | Stage definitions, anti-patterns, growth mechanism |
| `FIRST-MOVE.md` | 5 valid first actions, "the one you pick tells the fleet who you are" |
| `THE-FLEET.md` | Fleet member profiles, role types, the human's philosophy |
| `bootcamp/modules 1-6` | Existing exercise content, format references, code examples |
| `agent-training/README.md` | Bytecode generation patterns, agent-specific optimization tips |
| `GRADUATION.md` | 10 commandments, flywheel effect, design principles |
| `reverse-ideation/` | Philosophy of self-monitoring, git-as-protocol, tender-as-behavior |
| `worklog.md` (18 sessions) | Real fleet exercise examples: conformance tests, ISA work, audits, cross-fleet contributions |

## Appendix B: Mapping to Fleet Exercise History

The proposed curriculum is grounded in real fleet exercises that Super Z and other agents have completed:

| Proposed Exercise | Real Fleet Precedent |
|-------------------|---------------------|
| Bytecode tracing | Session 13: Building unified_interpreter.py (trace 23 test vectors) |
| Write arithmetic program | Session 14a: Assembler + conformance test compilation |
| Cross-runtime verification | Session 14b: C VM + Python VM comparison (20/20, then 71/71) |
| Find the bug | Session 8: Found 4 critical opcode errors in conformance tests |
| Fork+PR | Sessions 7-15: 4+ PRs to flux-runtime, 3 cross-fleet bottles |
| Spec review | Session 12: Reviewed Quill's RFC-0001, Babel's ISA relocation |
| Audit and grade | Sessions 7-8: Audited flux-benchmarks (D+), flux-lsp (C-), flux-ide (B-) |
| Fence ship | Sessions 7-12: 5 fences shipped (0x42, 0x45, 0x46, 0x51, etc.) |
| Spec-to-code | Session 15d: Async-temporal spec with 15 conformance vectors |
| Post a fence | Session 7: Posted fence-0x52 (cross-runtime conformance test suite) |

---

*"The boat doesn't interview crew. The boat puts them to work and sees what they become."*
*— Casey Digennaro, Captain's Philosophy*
