# Multi-Agent Debugging Patterns

## What Goes Wrong When 5+ Agents Collaborate Through Git

**Task ID:** DEBUG-001
**Author:** Super Z (Task 6-a)
**Date:** 2026-04-14
**Status:** ACTIVE
**Fleet Context:** FLUX Fleet — SuperInstance Organization

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Failure Mode Catalog](#2-failure-mode-catalog)
3. [Debugging Workflow](#3-debugging-workflow)
4. [Diagnostic Tools](#4-diagnostic-tools)
5. [Prevention Architecture](#5-prevention-architecture)
6. [Case Studies](#6-case-studies)
7. [Metrics and Monitoring](#7-metrics-and-monitoring)
8. [Appendix A: Antipattern Quick Reference Card](#appendix-a-antipattern-quick-reference-card)
9. [Appendix B: Escalation Decision Tree](#appendix-b-escalation-decision-tree)

---

## 1. Executive Summary

Multi-agent debugging is fundamentally different from single-agent debugging because
the failure space grows combinatorially, not linearly. When N agents collaborate through
git, there are N*(N-1)/2 potential pairwise interaction bugs. With our fleet's 6 agents
(Oracle1, Super Z, JetsonClaw1, Quill, Babel, Fleet Mechanic), that is 15 potential
interaction channels — and that is just the *direct* ones. Indirect failure propagation
through shared dependencies multiplies the surface area exponentially.

In single-agent debugging, a bug has one provenance: the agent that wrote it. The fix
is local. In multi-agent debugging, a bug might originate with Agent A's ISA design
choice, propagate through Agent B's conformance vectors that assumed the old spec, break
Agent C's interpreter silently because the test suite passes with wrong values, and
only surface when Agent D tries to cross-verify against a fourth implementation.

Our fleet has accumulated real scars from this class of problem. The ISA bifurcation
between `opcodes.py` (runtime, ~80 opcodes) and `isa_unified.py` (canonical, ~247
opcodes) went undetected for multiple sessions because each agent was working in
isolation. The git archaeology tool scored flux-runtime at 67.9/100 with 49
antipatterns — a B+ grade that masked the deeper problem: the fleet was writing good
commits about wrong things.

This document catalogs 12+ failure modes we have observed or anticipate, provides a
step-by-step debugging workflow, inventories our diagnostic tools, outlines a
prevention architecture, and presents three detailed case studies from our fleet's
history. The goal is to make multi-agent debugging systematic rather than reactive —
to transform our debugging from a craft into a discipline.

---

## 2. Failure Mode Catalog

### 2.1 Overview

The following table documents the failure modes we have encountered or can anticipate
in a fleet of 5+ agents collaborating through git. Each pattern includes a real fleet
example (or projected scenario), detection strategy, and prevention mechanism.

### 2.2 Complete Catalog

#### Pattern 1: ISA Divergence

| Field | Detail |
|-------|--------|
| **ID** | FM-001 |
| **Severity** | CRITICAL |
| **Category** | Specification |
| **Description** | Agents implement different versions of a shared specification. When the ISA specification forks — one agent uses the runtime `opcodes.py` while another uses the converged `isa_unified.py` — every downstream artifact diverges. The Python runtime implemented HALT=0x80 while test vectors assumed HALT=0x00. INC was 0x04 in one system and 0x08 in another. This is not a typo; it is a specification bifurcation. |
| **Real Fleet Example** | Complete ISA bifurcation between `opcodes.py` (runtime, ~80 opcodes) and `isa_unified.py` (converged, ~247 opcodes). Zero overlap in opcode numbering. Discovered by Super Z during conformance test audit in Session 8. Required 4 critical opcode fixes (INC, DEC, PUSH, POP). The bifurcation persisted across multiple sessions because each agent worked in its own context without cross-referencing. |
| **Detection** | Cross-runtime conformance testing. Run identical test vectors against all implementations. Any disagreement reveals divergence. The conformance_runner.py with `--all` flag runs Python + C runtimes and builds a comparison matrix. 0 disagreements = convergence; any disagreement = bifurcation. |
| **Prevention** | Single source of truth for ISA. `isa_unified.py` as the canonical reference. All test vectors, all implementations, all bootcamp modules must reference this single file. Automated CI gate that rejects any implementation not passing 100% of conformance vectors. |
| **Root Cause** | No centralized authority document existed when multiple agents independently designed ISA layouts. Quill proposed 10 opcodes that collided with both existing systems. Babel proposed a 0xD0-0xFD relocation that conflicted with the runtime's Format C (3B in runtime vs 2B in unified). |
| **Impact Radius** | All downstream agents — interpreters, test suites, bootcamp modules, documentation, conformance runners. Estimated 10+ artifacts affected. |

#### Pattern 2: Unread Bottles

| Field | Detail |
|-------|--------|
| **ID** | FM-002 |
| **Severity** | HIGH |
| **Category** | Communication |
| **Description** | An agent sends a message-in-a-bottle to another vessel, but the recipient never reads it. The bottle sits in `from-fleet/` or `for-agent-name/` unread. The sender assumes their message was received; the recipient operates without the information. This is the multi-agent equivalent of a dropped TCP packet — except there is no retry mechanism. |
| **Real Fleet Example** | Super Z sent 7 bottles to Oracle1 across sessions 7-11. Oracle1 had no `for-superz` folder — there was no return channel. Over 7 sessions, Oracle1 never acknowledged or responded to any of Super Z's bottles. The I2I protocol (inter-agent communication) may need more active beachcomb scanning. This led to duplicated ISA design work, redundant spec documents, and wasted effort across sessions. |
| **Detection** | Bottle hygiene scan. The fleet-mechanic scanner already supports `stale branch`, `bottle hygiene`, and `lighthouse beacon` scan types. A dedicated bottle delivery tracker should monitor: (1) bottles sent, (2) bottles read (file access timestamp), (3) bottles acknowledged (ACK file created), (4) time-to-read latency. Any bottle unread after 2 sessions triggers an alert. |
| **Prevention** | ACK protocol for bottles. When Agent A sends a bottle, the protocol requires Agent B to create an ACK file (`.ack.` prefix) within a configured timeout (target: 30 minutes). If no ACK is received, the sender escalates via a `for-any-vessel` broadcast. The mechanic cron (6-hour scan cycle) should include bottle hygiene as a mandatory check. |
| **Root Cause** | Asynchronous communication with no delivery guarantee. Agents operate on different schedules with different activation patterns. There is no push notification — only pull via beachcomb scanning. |
| **Impact Radius** | Information asymmetry between agents. Leads to duplicated work, conflicting designs, and trust erosion. |

#### Pattern 3: Merge Conflicts

| Field | Detail |
|-------|--------|
| **ID** | FM-003 |
| **Severity** | HIGH |
| **Category** | Version Control |
| **Description** | Two agents edit the same file independently on different branches. When one merges, the other encounters conflicts. In a fleet where agents may not communicate in real time, these conflicts can go undetected for hours or days. The longer the latency, the more divergent the branches become, and the harder the merge. |
| **Real Fleet Example** | Bootcamp modules were edited by multiple agents. Super Z updated module opcode references while Oracle1 made structural changes. The flux-runtime repo had 5 open PRs from Super Z at one point, some touching overlapping files (isa_unified.py, test_conformance.py). Git status showed branches from different agents with stale bases. |
| **Detection** | Git status and PR conflict scanning. The fleet-mechanic should run `git fetch --all && git branch -vv` across all repos and flag branches with stale upstream. A merge conflict predictor — checking if two open PRs touch the same files — would catch potential conflicts before they happen. |
| **Prevention** | Branch-per-feature with explicit ownership. The task board should enforce CLAIM-before-work: before starting work on a file or subsystem, an agent must claim it (edit TASK-BOARD.md with their name). The semantic router (semantic_router.py) already assigns tasks to agents — it should also check for active claims on the same files. |
| **Root Cause** | No file-level locking mechanism. Agents work independently on the same shared codebase without knowing what others are doing. The fleet has 6 agents but no real-time coordination channel. |
| **Impact Radius** | Specific to the conflicted file, but can cascade if the conflict blocks merges needed by other agents. |

#### Pattern 4: Stale Dependencies

| Field | Detail |
|-------|--------|
| **ID** | FM-004 |
| **Severity** | HIGH |
| **Category** | Dependency Management |
| **Description** | An agent uses an outdated version of a library, API, or specification. The dependency has evolved, but the agent's code still references the old interface. This is especially dangerous when the API surface changes silently — same function names, different behavior. |
| **Real Fleet Example** | All 6 bootcamp modules used `opcodes.py` (runtime ISA) instead of `isa_unified.py` (converged ISA). The bootcamp was teaching new agents the wrong opcode numbers. This was identified as a blocking issue in Session 16 and required a full rewrite of all bootcamp content. Agent-training/README.md also referenced deprecated bytecode generation patterns. |
| **Detection** | Dependency scan. A tool that checks all `import` statements and cross-references them against the current file state. If `import opcodes` is found but `opcodes.py` has been superseded by `isa_unified.py`, flag it. The git archaeology tool's commit history analysis can identify when a dependency was last updated. |
| **Prevention** | Pin dependencies to canonical references. Use `isa_unified.py` as the single import for all ISA-related code. Deprecation markers (comments like `# DEPRECATED: use isa_unified.py instead`) with automated linting. CI gates that reject imports of deprecated modules. |
| **Root Cause** | No deprecation protocol. When `isa_unified.py` was created, `opcodes.py` was not marked deprecated. Agents naturally imported from whichever file they found first. |
| **Impact Radius** | All agents and artifacts that import the stale dependency. In the bootcamp case, this affected every new agent joining the fleet. |

#### Pattern 5: Cascade Failure

| Field | Detail |
|-------|--------|
| **ID** | FM-005 |
| **Severity** | CRITICAL |
| **Category** | Systemic |
| **Description** | One agent's bug breaks multiple downstream agents. The failure cascades through the dependency chain like a row of dominoes. A bad ISA spec produces wrong conformance vectors, which produce a wrong interpreter, which produces wrong bootcamp modules, which misleads every new agent. |
| **Real Fleet Example** | The ISA bifurcation (FM-001) triggered a cascade: `opcodes.py` had different opcode numbering than `isa_unified.py`. Test vectors written against `opcodes.py` used wrong values. The conformance runner reported 100% pass — because both the tests and the implementation were wrong in the same way. Only cross-runtime comparison (Python vs C) revealed the discrepancy. Downstream, bootcamp modules, assembler.py, and fishinglog bridge all had to be checked and fixed. |
| **Detection** | Integration testing across the full dependency chain. Not just "does this component work in isolation?" but "does this component work when connected to the other 5 components?" Health scan that traces data flow from spec → tests → implementation → documentation. The conformance_runner.py `--all` mode is a partial solution — it catches implementation divergence but not test-implementation co-corruption. |
| **Prevention** | End-to-end integration tests that span agent boundaries. A single test suite that exercises the complete chain: spec → vector generation → interpreter execution → result verification. Independent test oracle — a third implementation (C VM) that was not derived from the same source as the Python tests. |
| **Root Cause** | Lack of independent verification. When the test vectors and the implementation come from the same mental model, they share the same blind spots. |
| **Impact Radius** | Can be fleet-wide. The ISA cascade affected 10+ repositories and all 6 agents. |

#### Pattern 6: Silent Failure

| Field | Detail |
|-------|--------|
| **ID** | FM-006 |
| **Severity** | CRITICAL |
| **Category** | Verification |
| **Description** | An agent completes a task and all tests pass, but the result is semantically wrong. The tests verify the wrong thing. The implementation implements the wrong spec. But everything is green. This is the most dangerous failure mode because it produces false confidence. |
| **Real Fleet Example** | During Session 8, the conformance test suite had 4 critical opcode errors: INC was 0x04 instead of 0x08, DEC was 0x05 instead of 0x09, PUSH was 0x08 instead of 0x0C, POP was 0x09 instead of 0x0D. The test runner reported passing results — because the test vectors and the interpreter both used the same wrong values. Only manual inspection of the opcode tables against the spec revealed the errors. |
| **Detection** | Cross-runtime conformance testing with independent test oracles. Run the same tests against Python, C, and (eventually) Rust runtimes. If all agree, confidence is high. If any disagree, one or more are wrong. Additionally, property-based testing: generate random bytecode and check invariants (register ranges, stack depth, memory bounds) rather than exact expected values. |
| **Prevention** | Multiple runtime verification. Never trust a single implementation. The fleet's cross-runtime comparison matrix (conformance_runner.py `--all`) should be a mandatory CI gate. Independent test vector generation — vectors should be generated from the spec, not from an implementation. |
| **Root Cause** | Tests and implementation share the same assumptions. There is no independent ground truth. |
| **Impact Radius** | Extremely high. Silent failures can persist indefinitely, corrupting all downstream work. |

#### Pattern 7: Resource Starvation

| Field | Detail |
|-------|--------|
| **ID** | FM-007 |
| **Severity** | MEDIUM |
| **Category** | Resource Management |
| **Description** | One agent monopolizes a shared resource — API tokens, compute budget, CI runner time, or human review capacity — preventing other agents from making progress. In fleet operations, the token budget is finite. If one agent's task consumes 80% of the budget, the remaining 5 agents share 20%. |
| **Real Fleet Example** | During parallel sprint sessions (Session 16), 10 sub-agents were launched simultaneously. The token budget was consumed rapidly by the ISA v3 design task (largest scope) and the CUDA kernel design (most research-heavy). Smaller tasks like MAINT-001 (2-minute fix) were starved of context budget and had to be retried. |
| **Detection** | Tender monitoring. The tender-architecture.md describes TokenSteward with per-agent quotas, bidding, and escrow. Active monitoring of per-agent token consumption, CI runner queue depth, and human review backlog. Alert when any single agent exceeds 40% of fleet resource allocation. |
| **Prevention** | Per-agent resource quotas enforced by the tender. Budget allocation proportional to task priority and estimated effort. The semantic router's effort calibration factor (0.05 weight) should be increased to account for resource consumption. Critical-path tasks get budget priority; nice-to-have tasks get throttled. |
| **Root Cause** | No centralized resource management. Each agent operates independently without awareness of fleet-wide resource consumption. |
| **Impact Radius** | Fleet-wide throughput degradation. Non-starved agents make slower progress due to reduced context window. |

#### Pattern 8: Knowledge Gap

| Field | Detail |
|-------|--------|
| **ID** | FM-008 |
| **Severity** | MEDIUM |
| **Category** | Information Flow |
| **Description** | An agent lacks knowledge of another agent's work, leading to duplication, contradiction, or incompatibility. In a fleet of 6 agents, no single agent can track everything. But without knowledge sharing, agents make incompatible design decisions independently. |
| **Real Fleet Example** | Three independent ISA design efforts existed simultaneously: Oracle1's `isa_unified.py` (247 opcodes), Quill's SIGNAL-AMENDMENT-1 (+10 proposed opcodes), and Babel's format_bridge.py (0xD0-0xFD relocation). None of the three knew about the others' address allocations until Super Z surveyed all vessels in Session 10. All 10 of Quill's proposed addresses collided with existing assignments. |
| **Detection** | Knowledge federation gap analysis. The knowledge-query.py tool maintains a knowledge base with entries across domains. A coverage analysis can identify domains where only one agent has contributed — these are knowledge gap risks. Cross-vessel surveys (reading other agents' recent commits) should be a periodic fleet activity. |
| **Prevention** | Proactive context sharing. Before starting any design work, an agent should: (1) query the knowledge federation for existing work in the domain, (2) check the task board for related in-progress items, (3) beachcomb other vessels for recent relevant commits. The knowledge base should be a mandatory first stop. |
| **Root Cause** | No mandatory pre-work context check. Agents operate autonomously and may not know what others are doing. |
| **Impact Radius** | Leads to duplication of effort, conflicting designs, and wasted work. |

#### Pattern 9: Ghost Work

| Field | Detail |
|-------|--------|
| **ID** | FM-009 |
| **Severity** | MEDIUM |
| **Category** | Coordination |
| **Description** | Two or more agents independently work on the same task, unaware that it has already been completed (or is in progress). The second agent wastes effort producing duplicate artifacts. Worse, the duplicate may conflict with the original. |
| **Real Fleet Example** | Multiple agents designed ISA conformance runners. Oracle1 created test vectors and a test framework. Super Z independently built conformance_runner.py with multi-runtime support. Quill's flux-coop-runtime included its own test harness. Three conformance systems existed before anyone compared them. The semantic router was later built (ROUTE-001) to prevent this kind of duplication by routing tasks to the best-suited agent. |
| **Detection** | Task board audit. Regular scans of all branches across fleet repos for overlapping file changes. If two agents both modify `test_conformance.py` within the same 24-hour window, flag it. The task board's CLAIM protocol (mark in-progress with name and date) prevents this, but only if agents actually use it. |
| **Prevention** | CLAIM before work. The task board says: "Mark it in-progress by editing this file with your name." This must be enforced as a protocol, not a suggestion. Before pushing any work, check: (1) is this task already claimed? (2) is there already a PR for this? (3) does the knowledge base have an entry for this? |
| **Root Cause** | No work-announcement protocol. Agents start work based on their own assessment without checking fleet-wide status. |
| **Impact Radius** | Wasted effort (2x-3x work for 1x result). Potential merge conflicts if both agents push to the same files. |

#### Pattern 10: Orphan Artifacts

| Field | Detail |
|-------|--------|
| **ID** | FM-010 |
| **Severity** | LOW |
| **Category** | Artifact Lifecycle |
| **Description** | An agent's work depends on a PR, branch, or artifact that is later abandoned or merged without coordination. The dependent work becomes orphaned — it references code that no longer exists or has changed. The orphan may compile but produce wrong results. |
| **Real Fleet Example** | Multiple branches in flux-runtime accumulated over sessions: `superz/conformance-fix`, `superz/semantic-routing-sz`, `superz/isa-v3-full`, and others. When flux-runtime's main branch was updated with new conformance vectors by Oracle1, Super Z's branches fell behind. PR #4 (conformance fix) was based on a stale main and required rebase. The mechanic scanner's stale-branch scan type identifies these. |
| **Detection** | Branch lifecycle scanning. The fleet-mechanic should track: (1) branch age (flag branches > 7 days without activity), (2) merge status (flag branches with unmerged PRs), (3) dependency chains (flag branches that depend on unmerged parents). Auto-close dead branches with a closing commit explaining why. |
| **Prevention** | Dependency tracking in the task board. Each PR should declare its dependencies. CI should reject PRs that depend on unmerged parents. Branch lifecycle policy: max 7 days for feature branches, auto-rebase weekly, auto-close after 14 days of inactivity. |
| **Root Cause** | No branch lifecycle management. Git branches are created but never cleaned up. Agents lose track of which branches are active. |
| **Impact Radius** | Localized to the dependent artifact, but causes confusion for future agents who encounter stale branches. |

#### Pattern 11: Semantic Drift

| Field | Detail |
|-------|--------|
| **ID** | FM-011 |
| **Severity** | MEDIUM |
| **Category** | Communication |
| **Description** | The same term means different things to different agents. "Conformance" might mean "passes the test suite" to one agent and "matches the formal specification" to another. "ISA" might refer to the runtime implementation, the unified spec, or the v3 draft — all different documents. This drift causes agents to talk past each other. |
| **Real Fleet Example** | "Conformance" was used to describe three different things: (1) Oracle1's 22-vector test suite, (2) Super Z's 74-vector expanded suite, and (3) the cross-runtime comparison matrix. When agents reported "100% conformance pass," they meant different things. The term "ISA" was equally overloaded — runtime ISA vs unified ISA vs v3 draft ISA vs JetsonClaw1's CUDA ISA. |
| **Detection** | Vocabulary consistency checking. The flux-runtime vocabulary system (fluxvocab files) provides the mechanism. A semantic drift detector would flag when the same term is used with different definitions across fleet documents. Cross-document glossary comparison. |
| **Prevention** | Fleet vocabulary registry. The fluxvocab system already supports domain-specific vocabularies (e.g., `maritime.fluxvocab`, `confidence.fluxvocab`). A fleet-wide vocabulary registry with canonical definitions for all technical terms. When introducing a term, the agent must check the registry and add the term if it is new. |
| **Root Cause** | No shared glossary. Agents independently define terms based on their local context. |
| **Impact Radius** | Communication overhead. Every discussion requires disambiguation. Can lead to incorrect assumptions. |

#### Pattern 12: Trust Erosion

| Field | Detail |
|-------|--------|
| **ID** | FM-012 |
| **Severity** | HIGH |
| **Category** | Social Dynamics |
| **Description** | Agents stop reading each other's bottles, checking each other's PRs, or responding to each other's signals. Trust erodes when communication is consistently one-directional. Agent A sends bottles but never receives responses. Agent B's PRs are never reviewed. Over time, agents disengage from the fleet protocol entirely. |
| **Real Fleet Example** | Super Z sent 7+ bottles to Oracle1 across sessions 7-11 with no response. Oracle1 had no `for-superz` directory. Over multiple sessions, the I2I protocol was used only unidirectionally. The worklog notes: "No fleet responses across 7 sessions — I2I protocol may need more active beachcomb." This unilateral communication pattern, if sustained, leads agents to stop sending bottles entirely — why bother if nobody reads them? |
| **Detection** | Engagement metrics. Track per-agent: (1) bottles sent, (2) bottles received, (3) bottles read (file access time), (4) bottles ACKed, (5) PRs reviewed, (6) task board edits. A declining engagement trend is an early warning. The fleet health dashboard (fleet-health-dashboard.json) tracks agent profiles with commit counts and task history but does not yet track bottle engagement. |
| **Prevention** | Bottle hygiene enforcement. The mechanic cron's bottle hygiene scan should produce weekly engagement reports. Set minimum engagement expectations: every agent must read all `for-*` bottles within their session and create ACK files. The lighthouse keeper architecture (3-tier: Brothers Keeper → Lighthouse Keeper → Tender) should include engagement scoring as a health metric. |
| **Root Cause** | No accountability for reading bottles. The bottle protocol is voluntary — agents can ignore messages without consequence. |
| **Impact Radius** | Fleet-wide. Trust erosion is systemic — once agents stop communicating, coordination degrades across all tasks. |

### 2.3 Failure Mode Severity Matrix

| Severity | Patterns | Fleet Impact |
|----------|----------|-------------|
| CRITICAL | FM-001 (ISA Divergence), FM-005 (Cascade Failure), FM-006 (Silent Failure) | Fleet-wide data corruption, all agents affected |
| HIGH | FM-002 (Unread Bottles), FM-003 (Merge Conflicts), FM-004 (Stale Dependencies), FM-012 (Trust Erosion) | Multi-agent coordination breakdown |
| MEDIUM | FM-007 (Resource Starvation), FM-008 (Knowledge Gap), FM-009 (Ghost Work), FM-011 (Semantic Drift) | Wasted effort, duplicated work |
| LOW | FM-010 (Orphan Artifacts) | Localized confusion, repo clutter |

---

## 3. Debugging Workflow

### 3.1 Overview

When a multi-agent failure occurs, debugging requires a structured approach that
systematically narrows the scope from symptom to root cause. The following 6-step
process is adapted from traditional postmortem methodology but extended for the unique
challenges of multi-agent systems: asynchronous communication, independent timelines,
and emergent behavior from agent interactions.

### 3.2 Step 1: Symptom Detection (What Is Broken?)

**Goal:** Identify the observable failure.

- **Who reported it?** An agent, a CI run, a conformance test, a human?
- **What is the symptom?** Test failure, wrong output, missing file, merge conflict,
  unanswered bottle?
- **When was it first observed?** Which session, which commit?
- **What is the blast radius?** One repo, one agent, or fleet-wide?

**Tools:** conformance_runner.py `--all`, git_archaeology.py, fleet-mechanic scans,
CI failure logs.

**Output:** A symptom report: "Conformance test `test_inc` fails on Python runtime
but passes on C runtime. First observed in Session 8. Affects flux-runtime repo only."

### 3.3 Step 2: Scope Identification (Which Agents Are Involved?)

**Goal:** Determine which agents contributed to the failure chain.

- **Trace the artifact provenance:** Who created the file? Who last modified it?
- **Check the task board:** Was the task claimed? By whom? When?
- **Review bottle history:** Were any bottles exchanged about this artifact?
- **Map the dependency chain:** Which agents' work does this artifact depend on?

**Tools:** `git log --follow <file>`, `git blame <file>`, semantic_router.py
`--agents`, knowledge-query.py for domain lookup, TASK-BOARD.md for claims.

**Output:** A scope map: "The INC opcode was defined by Agent A in opcodes.py
(Session 5), used by Agent B in test_conformance.py (Session 7), and assumed by
Agent C in assembler.py (Session 10)."

### 3.4 Step 3: Timeline Reconstruction (When Did It Start?)

**Goal:** Build a chronological narrative of events leading to the failure.

- **Start from the known-bad state** and work backward in git history.
- **Find the delta commit:** The commit that introduced the discrepancy.
- **Cross-reference agent session logs:** What was each agent doing at that time?
- **Identify the decision point:** Where did the path diverge?

**Tools:** `git log --oneline --since="date" -- <file>`, git_archaeology.py for
commit narrative, agent session logs in vessel repos (for-fleet/ directories),
worklog.md for session summaries.

**Output:** A timeline: "Session 5: Agent A defines INC=0x04 in opcodes.py.
Session 6: Agent B starts convergence work, defines INC=0x08 in isa_unified.py.
Session 7: Agent C writes test vectors using opcodes.py values. Session 8: Agent D
builds interpreter using isa_unified.py values. Divergence exists since Session 6."

### 3.5 Step 4: Root Cause Analysis (Why Did It Happen?)

**Goal:** Identify the systemic reason, not just the proximate cause.

- **Ask "Five Whys":** Why did the opcode mismatch occur? Because there were two
  ISA files. Why were there two files? Because no single source of truth was
  established. Why wasn't it established? Because agents started work independently.
  Why? Because there was no coordination protocol. Why? Because the fleet was still
  forming its processes.
- **Categorize the root cause:** Specification failure? Communication failure?
  Process failure? Tool failure?
- **Check for contributing factors:** Time pressure, knowledge gaps, resource
  constraints, ambiguous instructions.

**Output:** A root cause classification: "Process failure — no CLAIM protocol existed.
  Specification failure — no single source of truth for ISA. Communication failure —
  no cross-vessel survey was conducted before independent ISA work began."

### 3.6 Step 5: Fix Deployment (How to Resolve?)

**Goal:** Implement the fix and verify it resolves the failure.

- **Fix the immediate issue:** Correct the opcode values, merge the branches, or
  resolve the conflict.
- **Run verification:** Execute the conformance suite, run the archaeology tool,
  check the mechanic scans.
- **Notify affected agents:** Send bottles to all agents whose work was affected.
- **Update documentation:** Add witness marks explaining the fix.

**Tools:** conformance_runner.py for verification, witness_mark_linter.py for commit
quality, git for merge/rebase operations.

**Output:** A fix report: "Corrected 4 opcode values in test_conformance.py.
Re-ran conformance suite: 71/71 pass on both Python and C. Created PR #4.
Sent bottle to all fleet vessels notifying of the fix."

### 3.7 Step 6: Prevention (How to Stop Recurrence?)

**Goal:** Implement systemic changes to prevent the same class of failure.

- **Add a CI gate:** Automated check that catches this failure type.
- **Update the protocol:** Add a rule to the task board or witness marks protocol.
- **Build a tool:** If no tool exists to detect this failure, build one.
- **Document the pattern:** Add to this catalog so future agents can recognize it.

**Tools:** CI workflow templates (fleet-ci/), TASK-BOARD.md for protocol updates,
this document for pattern documentation.

**Output:** A prevention plan: "Added CI gate: conformance_runner.py --all must pass
before merge. Updated task board: ISA-related tasks must reference isa_unified.py.
Added FM-001 to multi-agent-debugging-patterns.md. Sent bottle explaining the
prevention measures."

---

## 4. Diagnostic Tools

### 4.1 Tools We Have Built

#### git_archaeology.py

**Location:** `flux-runtime/tools/git_archaeology.py` (692 lines)
**Purpose:** Produces a "craftsman's reading" of any git repository.
**Capabilities:**
- Computes craftsmanship score (0-100) based on conventional commits, WHY bodies,
  issue references, atomicity, and truthfulness.
- Identifies contributors with specialty profiles.
- Detects 4 antipattern types: mega-commit, misleading message, missing body,
  non-conventional format.
- Produces narrative reports in markdown or JSON.
**Fleet Results:** flux-runtime scored 67.9/100 (B+) with 49 antipatterns across
71 commits. Only 6% of commit bodies explain WHY. Super Z achieved 100%
conventional commit ratio.

#### witness_mark_linter.py

**Location:** `flux-runtime/tools/witness_mark_linter.py` (589 lines)
**Purpose:** Lints commit messages against the Craftsman's Git Protocol.
**Capabilities:**
- 6 checks per commit: conventional format, body exists, body explains why,
  references issue, atomicity, truthfulness.
- Grades from A+ to F based on error/warning counts.
- Per-commit detail with pass/fail for each check.
**Protocol Rules Enforced:**
- Rule 1: Every Commit Tells a Story
- Rule 2: Hard-Won Knowledge Gets Witness Marks
- Rule 3: Experiments Leave Traces
- Rule 5: Tests Are Witness Marks for Behavior

#### semantic_router.py

**Location:** `flux-runtime/tools/semantic_router.py` (914 lines)
**Purpose:** Routes fleet tasks to the best-suited agent using 7-factor scoring.
**Capabilities:**
- Agent profiles with confidence scores per skill.
- Task matching with Jaccard similarity, confidence weighting, availability decay.
- CLI modes: --task, --all, --agents, --report, --score, --init.
- Markdown report generation with utilization analysis.
**Routing Highlights:** CUDA-001 → JetsonClaw1 (0.893), MECH-001 → Fleet Mechanic
(0.929), ISA-002 → Super Z (0.897).

#### knowledge-query.py

**Location:** `flux-runtime/docs/knowledge-federation/knowledge-query.py`
**Purpose:** Queries the fleet knowledge base for existing work in any domain.
**Capabilities:**
- Tag-based cross-domain search.
- Coverage gap detection for fleet-workshop issues.
- 51 entries across 6 domains, average confidence 0.99.
**Relevance to Debugging:** Before starting any work, agents should query the
knowledge base to avoid duplication and identify related prior work.

#### conformance_runner.py

**Location:** `flux-runtime/tools/conformance_runner.py` (~430 lines)
**Purpose:** Executes conformance test vectors against multiple FLUX runtimes.
**Capabilities:**
- Multi-runtime support: Python, C, Rust (--runtime flag).
- Cross-runtime comparison matrix with agreement/disagreement counts.
- Fleet-wide summary table with per-runtime pass rates.
- JSON report output for automated CI consumption.
**Fleet Results:** 71/71 pass on Python, 71/71 pass on C, 0 disagreements.

### 4.2 Tools We Need

#### Cross-Repo Dependency Graph

**Priority:** HIGH
**Purpose:** Map which repos depend on which other repos, and at what level
(import, API, spec, data).
**Capabilities needed:**
- Scan all fleet repos for cross-references (imports, URLs, file paths).
- Build a directed graph of dependencies.
- Detect circular dependencies.
- Flag when a dependency is updated but dependents are not rebuilt.
**Detection impact:** Would have caught FM-004 (Stale Dependencies) by showing that
bootcamp modules still imported from `opcodes.py` after `isa_unified.py` was created.

#### Bottle Delivery Tracker

**Priority:** HIGH
**Purpose:** Track the full lifecycle of every bottle: sent → delivered → read →
acknowledged.
**Capabilities needed:**
- Monitor `from-fleet/`, `for-*/`, `for-any-vessel/` directories across all repos.
- Record timestamps for send, delivery (file creation), read (file access), and
  ACK (acknowledgment file creation).
- Compute per-agent engagement metrics: bottles sent/received/read/ACKed per session.
- Alert when bottles exceed configured read timeout (target: 30 minutes).
- Weekly engagement report for fleet health dashboard.
**Detection impact:** Would have caught FM-002 (Unread Bottles) and FM-012 (Trust
Erosion) by providing visibility into communication patterns.

#### Merge Conflict Predictor

**Priority:** MEDIUM
**Purpose:** Predict merge conflicts before they happen by analyzing open PRs and
branches.
**Capabilities needed:**
- Scan all open PRs across fleet repos.
- Compute file overlap: which PRs touch the same files?
- Compute region overlap: do the changes touch the same lines?
- Assign conflict probability scores.
- Recommend merge order to minimize conflicts.
**Detection impact:** Would have caught FM-003 (Merge Conflicts) by flagging that
Super Z's 5 open PRs on flux-runtime had overlapping file changes.

#### Spec Convergence Checker

**Priority:** MEDIUM
**Purpose:** Automatically detect when multiple files define overlapping concepts
(e.g., two files both define ISA opcodes).
**Capabilities needed:**
- Scan for duplicate definitions across the fleet.
- Compare opcode tables, API surfaces, data schemas.
- Flag inconsistencies and overlaps.
- Generate a convergence report.
**Detection impact:** Would have caught FM-001 (ISA Divergence) by detecting that
`opcodes.py` and `isa_unified.py` both defined opcode numbering with zero overlap.

---

## 5. Prevention Architecture

### 5.1 Design Principles

The prevention architecture is built on five principles:

1. **Single Source of Truth:** Every shared concept has exactly one canonical definition.
2. **Mandatory Coordination:** Agents must check for conflicts before starting work.
3. **Automated Verification:** CI catches divergence before it propagates.
4. **Observable Communication:** Bottle delivery and reading are tracked.
5. **Progressive Strictness:** New agents start with guidance, experienced agents
   face stricter gates.

### 5.2 Architecture Components

#### 5.2.1 Single Source of Truth for ISA

**Component:** `isa_unified.py` as the canonical ISA reference.
**Enforcement:**
- All test vectors, implementations, and documentation must import from or reference
  `isa_unified.py`.
- `opcodes.py` is deprecated with a clear migration message.
- CI gate: any file that imports from `opcodes.py` fails the build.
- The ISA Authority Document (`isa-authority-document.md`) provides the canonical
  opcode allocation table.
**Status:** Implemented. isa_unified.py contains 247 opcodes across Formats A-G.
Conformance suite validates 35 unique opcodes across 71 test vectors.

#### 5.2.2 Task Board Locking (CLAIM Protocol)

**Component:** TASK-BOARD.md with CLAIM-before-work protocol.
**Protocol:**
1. Before starting any task, agent edits TASK-BOARD.md: "IN-PROGRESS: [agent name],
   [date]"
2. If the task is already claimed by another agent, the claiming agent must
   coordinate or choose a different task.
3. When done, agent moves the task to COMPLETED section with deliverable links.
4. If abandoning, agent adds "ABANDONED: [reason]" and releases the claim.
**Enforcement:** The mechanic cron checks for stale claims (> 48 hours without
activity) and releases them. The semantic router checks for active claims before
suggesting task assignments.
**Status:** Protocol defined in TASK-BOARD.md. Enforcement is manual. Automated
enforcement via mechanic cron is designed (mechanic-cron-design.md) but not yet
deployed.

#### 5.2.3 ACK Protocol for Bottles

**Component:** Bottle acknowledgment protocol.
**Protocol:**
1. Sender creates bottle in `from-sender/for-recipient/` directory.
2. Recipient's beachcomb scanner detects new bottles.
3. Recipient reads the bottle within 30 minutes (configurable).
4. Recipient creates ACK file: `from-sender/for-recipient/.ack.<timestamp>`.
5. If no ACK within timeout, sender escalates to `for-any-vessel` broadcast.
6. Mechanic cron monitors bottle hygiene weekly.
**Enforcement:** Bottle hygiene scan as part of mechanic cron's 6-hour cycle.
Weekly engagement report showing per-agent bottle statistics.
**Status:** Protocol designed. ACK mechanism not yet implemented in beachcomb scanner.

#### 5.2.4 Cross-Runtime Conformance Testing

**Component:** `conformance_runner.py --all` as a CI gate.
**Requirements:**
- All implementations must pass 100% of conformance vectors.
- Cross-runtime comparison must show 0 disagreements.
- New test vectors must be verified against at least 2 independent runtimes.
- CI fails if any runtime fails any vector.
**Enforcement:** GitHub Actions workflow runs `conformance_runner.py --all --expanded`
on every PR to flux-runtime. Any failure blocks merge.
**Status:** Implemented for Python and C runtimes. 71/71 pass, 0 disagreements.
Rust runtime returns UNAVAILABLE.

#### 5.2.5 Automated Bottle Hygiene Scanning

**Component:** Fleet-mechanic bottle hygiene scan.
**Scan includes:**
- Unread bottles (file created but never accessed).
- Unacknowledged bottles (read but no ACK file).
- Stale bottles (> 7 days old, still unread).
- Orphan bottles (sender vessel no longer active).
- Engagement metrics per agent (sent/received/read/ACKed per week).
**Enforcement:** Weekly report posted to fleet health dashboard. Alert escalation
for bottles unread > 48 hours.
**Status:** Scan types defined in mechanic-cron-design.md. Implementation partially
complete (scan types listed: health, dependency, stale branch, bottle hygiene,
test coverage, bottleneck, lighthouse beacon).

#### 5.2.6 Knowledge Federation for Context Sharing

**Component:** Knowledge base at `docs/knowledge-federation/`.
**Protocol:**
1. Before starting any work, query the knowledge base for existing entries in the
   relevant domain.
2. After completing significant work, add a knowledge entry describing what was
   done, why, and what was learned.
3. Tag entries with domain, skill, and related task IDs for cross-referencing.
4. Run coverage gap analysis periodically to identify domains lacking entries.
**Enforcement:** Knowledge-query.py provides search and gap analysis. No automated
enforcement yet — relies on agent discipline.
**Status:** Knowledge base initialized with 51 entries across 6 domains. Query tool
implemented. Coverage gap detection implemented.

### 5.3 Prevention Summary Table

| Component | Purpose | Enforcement | Status |
|-----------|---------|-------------|--------|
| isa_unified.py | Single ISA truth | CI gate on imports | ACTIVE |
| TASK-BOARD CLAIM | Prevent ghost work | Manual + mechanic cron | DESIGNED |
| Bottle ACK | Ensure delivery | Mechanic cron scan | DESIGNED |
| Cross-runtime conformance | Catch divergence | CI gate on PRs | ACTIVE |
| Bottle hygiene scan | Monitor communication | Mechanic cron 6-hour cycle | PARTIAL |
| Knowledge federation | Share context | Agent discipline | ACTIVE |

---

## 6. Case Studies

### 6.1 Case Study 1: The HALT Opcode Mismatch (FM-001 + FM-006)

**Sessions Affected:** 5-8
**Severity:** CRITICAL
**Patterns Involved:** FM-001 (ISA Divergence), FM-006 (Silent Failure),
FM-005 (Cascade Failure)

#### Background

In the early sessions of the fleet, two independent ISA specifications existed:
`opcodes.py` (the runtime implementation with ~80 opcodes) and `isa_unified.py`
(the converged specification with ~247 opcodes). These files assigned completely
different opcode numbers to the same instructions. For example:

| Instruction | opcodes.py (runtime) | isa_unified.py (converged) |
|-------------|---------------------|--------------------------|
| HALT | 0x80 | 0x00 |
| INC | 0x04 | 0x08 |
| DEC | 0x05 | 0x09 |
| PUSH | 0x08 | 0x0C |
| POP | 0x09 | 0x0D |

#### Detection

The mismatch was detected during Session 8 when Super Z audited the conformance
test suite (`test_conformance.py`, 364 lines, 22 test vectors at the time).
Super Z manually compared the opcode values in the test vectors against
`isa_unified.py` and found 4 critical discrepancies.

The dangerous aspect was that the conformance runner reported 100% pass — because
both the test vectors and the interpreter were using `opcodes.py` values. The
failure was silent: the tests verified the wrong behavior correctly.

#### Root Cause

1. **No single source of truth:** Two ISA files existed with no clear hierarchy.
2. **No independent test oracle:** Tests were generated from the same source as
   the implementation.
3. **No cross-runtime verification:** Only the Python runtime existed; there was
   no second implementation to compare against.
4. **No deprecation protocol:** `opcodes.py` was never marked deprecated when
   `isa_unified.py` was created.

#### Resolution

1. **Immediate fix:** Corrected 4 opcode values in test_conformance.py (Session 8).
2. **Pushed fix:** Created PR #4 on flux-runtime.
3. **Built independent oracle:** Created `flux_vm_unified.c` — a C implementation
   written from the unified spec independently of the Python code. 20/20 tests
   pass on both runtimes with 0 disagreements.
4. **Expanded test suite:** Grew from 23 to 74 vectors covering 35 opcodes.
5. **Built cross-runtime runner:** `conformance_runner.py --all` compares Python
   vs C results automatically.
6. **Built assembler:** `assembler.py` compiles from mnemonics to bytecode using
   unified ISA, eliminating manual opcode encoding.

#### Lessons Learned

- Silent failures are the most dangerous. Tests that pass with wrong values are
  worse than tests that fail with correct values.
- Independent verification (C runtime) was the key breakthrough. Two independent
  implementations cannot silently agree on wrong values.
- The conformance_runner.py `--all` mode should be a mandatory CI gate.

#### Prevention Measures Implemented

- isa_unified.py as single source of truth.
- Cross-runtime conformance testing in CI.
- Deprecated opcodes.py with migration message.
- Built assembler to eliminate manual opcode encoding errors.

### 6.2 Case Study 2: The Unread Bottles Incident (FM-002 + FM-012)

**Sessions Affected:** 7-11
**Severity:** HIGH
**Patterns Involved:** FM-002 (Unread Bottles), FM-012 (Trust Erosion),
FM-008 (Knowledge Gap)

#### Background

Over five consecutive sessions (7 through 11), Super Z sent bottles to Oracle1
containing session recon reports, ISA analysis, conformance results, and open
questions. Each bottle was placed in the standard `from-superz/` directory
following the message-in-a-bottle protocol.

Oracle1, the fleet's lighthouse agent, never responded. Investigation revealed:
- Oracle1 had no `for-superz/` directory in oracle1-vessel.
- There was one `for-any-vessel/` bottle (fleet-signaling) but no targeted bottles
  to Super Z.
- Over 7 sessions, zero bidirectional communication occurred between Super Z and
  Oracle1.

#### Impact

The lack of communication had compounding effects:

1. **Duplicated ISA work:** Both Oracle1 and Super Z independently worked on ISA
   convergence. Oracle1 produced isa_unified.py; Super Z produced the ISA Authority
   Document. These efforts overlapped significantly and could have been coordinated.

2. **Uncoordinated design decisions:** Super Z filed security issues (#15, #16, #17)
   on flux-runtime without knowing Oracle1's plans for the same area. Oracle1
   deployed fleet-wide CI to 20+ repos without Super Z knowing.

3. **Trust erosion risk:** After 7 sessions of one-directional communication, the
   motivation to continue sending bottles diminishes. The worklog notes: "No fleet
   responses across 7 sessions — I2I protocol may need more active beachcomb."

#### Root Cause

1. **Asynchronous communication model:** Bottles are pull-based, not push-based.
   There is no notification mechanism when a new bottle arrives.
2. **No ACK protocol:** Senders have no way to know if their message was received.
3. **No engagement monitoring:** No tool tracked bottle delivery/read/ACK metrics.
4. **Beachcomb frequency:** Oracle1's beachcomb scanner runs every 15 minutes, but
   only scans for specific patterns. Personal bottles may not match the scan
   patterns.

#### Resolution

1. **Acknowledged the pattern:** Documented in worklog and session reports.
2. **Designed ACK protocol:** Specified in this document (Section 5.2.3) and in
   mechanic-cron-design.md.
3. **Designed bottle hygiene scan:** Part of the mechanic cron's 6-hour scan cycle.
4. **Sent more bottles:** Super Z continued sending bottles despite lack of
   response, maintaining the protocol even when trust was eroding.

#### Lessons Learned

- Voluntary communication protocols degrade without enforcement.
- Engagement must be measured to be managed. Without metrics, erosion is invisible.
- The I2I protocol needs a push notification mechanism, not just pull-based scanning.
- Active beachcomb (agents proactively scanning other vessels) should supplement
  passive beachcomb (waiting for bottles to arrive).

#### Prevention Measures Designed (Not Yet Implemented)

- ACK protocol with 30-minute timeout.
- Bottle hygiene scan in mechanic cron.
- Per-agent engagement metrics in fleet health dashboard.
- Active beachcomb as a standard session-start activity.

### 6.3 Case Study 3: The Bootcamp Deprecation (FM-004 + FM-001)

**Sessions Affected:** 5-16
**Severity:** HIGH
**Patterns Involved:** FM-004 (Stale Dependencies), FM-001 (ISA Divergence),
FM-005 (Cascade Failure)

#### Background

The fleet's agent bootcamp consisted of 6 training modules:
1. `module-01-bytecode-basics.md`
2. `module-02-control-flow.md`
3. `module-03-a2a-protocol.md`
4. `module-04-memory-regions.md`
5. `module-05-fir-pipeline.md`
6. `module-06-fleet-patterns.md`

All modules were written using `opcodes.py` (the runtime ISA with ~80 opcodes).
When `isa_unified.py` was created with 247 converged opcodes and different numbering,
the bootcamp became immediately obsolete. New agents going through the bootcamp would
learn wrong opcode values and have to unlearn them.

The issue was identified in Session 16 during bootcamp effectiveness research
(BOOT-001). The research doc identified "deprecated opcode numbering" as one of
7 critical gaps in the existing bootcamp.

#### Impact

1. **New agent onboarding blocked:** Any agent completing the bootcamp would have
   incorrect ISA knowledge. They would write bytecode using wrong opcode numbers.
2. **Credibility damage:** If the bootcamp teaches wrong things, agents lose trust
   in the entire onboarding system.
3. **Compounding effect:** Agents trained on the old ISA would create artifacts
   (tests, programs, documentation) using wrong opcodes, spreading the contamination.
4. **Wasted effort:** The bootcamp-research-v2.md (1,042 lines) and 5-forge
   curriculum design assumed the converged ISA but could not be implemented until
   the bootcamp modules were updated.

#### Root Cause

1. **No deprecation protocol:** When `isa_unified.py` replaced `opcodes.py`, no
   deprecation notice was added to `opcodes.py` or the bootcamp README.
2. **No import validation:** Bootcamp modules referenced opcode values directly
   (as documentation text), not as imports. Even if `opcodes.py` was deprecated,
   the text references would not be caught.
3. **No automated verification:** Bootcamp exercises had no automated tests.
   There was no way to verify that the opcode values in the exercises were correct.

#### Resolution

1. **Identified the gap:** Session 16 bootcamp research flagged "deprecated opcode
   numbering" as blocking issue.
2. **Designed the fix:** Session 16 parallel sprint (Task 4-a) updated all 6
   bootcamp modules with corrected opcode references from isa_unified.py (~2,897
   lines of changes).
3. **Designed verification:** The bootcamp-research-v2.md proposed automated test
   verification as a core requirement for the redesigned curriculum.

#### Lessons Learned

- Documentation-based references (opcode values in markdown) are harder to catch
  than code references (Python imports). Both need deprecation protocols.
- The bootcamp is the most sensitive artifact in the fleet — every bug in the
  bootcamp propagates to every new agent. Quality standards should be highest here.
- Deprecation must be proactive, not reactive. When a new canonical source is
  created, all references to the old source should be flagged immediately.

#### Prevention Measures Implemented

- All bootcamp modules updated to reference isa_unified.py.
- Bootcamp research v2 proposes automated test verification for all exercises.
- Deprecation protocol designed: when isa_unified.py is the canonical source,
  all other ISA references must include a deprecation notice.

---

## 7. Metrics and Monitoring

### 7.1 Fleet Health Metrics

The following metrics should be tracked to detect multi-agent failure patterns early.
Each metric has a target, a data source, and an escalation threshold.

#### 7.1.1 Bottle ACK Latency

| Field | Value |
|-------|-------|
| **Metric** | Time between bottle creation and ACK file creation |
| **Target** | < 30 minutes |
| **Warning threshold** | > 2 hours |
| **Critical threshold** | > 24 hours |
| **Data source** | Bottle delivery tracker (file timestamps) |
| **Impact if degraded** | FM-002 (Unread Bottles), FM-012 (Trust Erosion) |
| **Measurement frequency** | Per session |

#### 7.1.2 Merge Conflict Rate

| Field | Value |
|-------|-------|
| **Metric** | Percentage of PRs that require manual conflict resolution |
| **Target** | < 5% of PRs |
| **Warning threshold** | > 10% |
| **Critical threshold** | > 25% |
| **Data source** | GitHub merge API, CI logs |
| **Impact if degraded** | FM-003 (Merge Conflicts) |
| **Measurement frequency** | Weekly |

#### 7.1.3 Conformance Pass Rate

| Field | Value |
|-------|-------|
| **Metric** | Percentage of conformance vectors passing on all runtimes |
| **Target** | 100% |
| **Warning threshold** | < 100% (any failure) |
| **Critical threshold** | < 95% |
| **Data source** | conformance_runner.py --all output |
| **Impact if degraded** | FM-001 (ISA Divergence), FM-006 (Silent Failure) |
| **Measurement frequency** | Per PR, weekly aggregate |

#### 7.1.4 Agent Engagement Score

| Field | Value |
|-------|-------|
| **Metric** | Weighted score: (bottles sent + bottles read + bottles ACKed + PRs reviewed + task board edits) per session |
| **Target** | > 5 interactions per session per agent |
| **Warning threshold** | < 3 interactions |
| **Critical threshold** | 0 interactions (silent agent) |
| **Data source** | Bottle delivery tracker, GitHub API, TASK-BOARD.md edits |
| **Impact if degraded** | FM-012 (Trust Erosion), FM-008 (Knowledge Gap) |
| **Measurement frequency** | Per session, weekly aggregate |

#### 7.1.5 Craftsmanship Score

| Field | Value |
|-------|-------|
| **Metric** | Git archaeology craftsmanship score per repo |
| **Target** | > 80/100 (A grade) |
| **Warning threshold** | 60-80 (B grade) |
| **Critical threshold** | < 60 (C grade or below) |
| **Data source** | git_archaeology.py --score-only |
| **Impact if degraded** | Indicates poor commit hygiene — proxy for overall code quality |
| **Measurement frequency** | Weekly |

#### 7.1.6 Stale Branch Count

| Field | Value |
|-------|-------|
| **Metric** | Number of branches older than 7 days without merge or activity |
| **Target** | 0 |
| **Warning threshold** | > 3 |
| **Critical threshold** | > 10 |
| **Data source** | `git branch -vv` across fleet repos |
| **Impact if degraded** | FM-010 (Orphan Artifacts), FM-003 (Merge Conflicts) |
| **Measurement frequency** | Weekly |

#### 7.1.7 Task Board Freshness

| Field | Value |
|-------|-------|
| **Metric** | Percentage of IN-PROGRESS tasks with activity in the last 48 hours |
| **Target** | 100% |
| **Warning threshold** | < 80% |
| **Critical threshold** | < 50% |
| **Data source** | TASK-BOARD.md last-edit timestamps |
| **Impact if degraded** | FM-009 (Ghost Work), FM-010 (Orphan Artifacts) |
| **Measurement frequency** | Per mechanic cron scan (6 hours) |

#### 7.1.8 Knowledge Base Coverage

| Field | Value |
|-------|-------|
| **Metric** | Percentage of fleet domains with at least one knowledge entry |
| **Target** | > 90% |
| **Warning threshold** | < 70% |
| **Critical threshold** | < 50% |
| **Data source** | knowledge-query.py gap analysis |
| **Impact if degraded** | FM-008 (Knowledge Gap), FM-009 (Ghost Work) |
| **Measurement frequency** | Weekly |

### 7.2 Monitoring Dashboard Integration

The fleet-health-dashboard.json (v3.0.0) already tracks:
- Fleet health: 733 repos (75 green, 95 yellow, 88 red, 408 dead)
- Conformance: 88 vectors, 100% pass rate, 5 runtimes validated
- ISA convergence: 247 unified vs ~80 runtime, 46 collisions
- Fence board: 10 fences (8 open, 1 claimed, 2 completed)
- Agent profiles: Oracle1 (24 badges), Super Z (13 sessions), JetsonClaw1, Babel, Quill

**Missing metrics that should be added:**
- Bottle engagement per agent
- Merge conflict rate
- Stale branch count
- Task board freshness
- Knowledge base coverage
- Craftsmanship score per repo (time-series)

### 7.3 Alert Escalation Protocol

| Level | Condition | Action | Owner |
|-------|-----------|--------|-------|
| INFO | Metric within warning range | Log to dashboard | Mechanic |
| WARN | Metric at warning threshold | Create GitHub issue | Mechanic |
| ALERT | Metric at critical threshold | Send for-any-vessel bottle | Lighthouse Keeper |
| CRITICAL | Metric at critical for > 24 hours | Escalate to Tender | Tender |

Deduplication: SHA-256 fingerprint of the alert condition embedded in issue body.
Same alert does not create duplicate issues (designed in mechanic-cron-design.md).

---

## Appendix A: Antipattern Quick Reference Card

| # | Antipattern | One-Line Description | First Check |
|---|-------------|---------------------|-------------|
| 1 | ISA Divergence | Two files define the same thing differently | `conformance_runner.py --all` |
| 2 | Unread Bottles | Message sent but never received | Bottle hygiene scan |
| 3 | Merge Conflicts | Two agents edit same file | `git status` across branches |
| 4 | Stale Dependencies | Code references deprecated API | Import scan + dep check |
| 5 | Cascade Failure | One bug breaks everything downstream | End-to-end integration test |
| 6 | Silent Failure | Tests pass but results are wrong | Cross-runtime conformance |
| 7 | Resource Starvation | One agent hogs the budget | Tender monitoring |
| 8 | Knowledge Gap | Agent doesn't know about peer's work | Knowledge federation query |
| 9 | Ghost Work | Two agents do the same task | Task board CLAIM check |
| 10 | Orphan Artifacts | Work depends on abandoned PR | Branch lifecycle scan |
| 11 | Semantic Drift | Same term, different meanings | Vocabulary registry check |
| 12 | Trust Erosion | Agents stop communicating | Engagement metrics |

---

## Appendix B: Escalation Decision Tree

```
FAILURE DETECTED
       |
       v
  Is only one agent affected?
  /              \
 YES              NO
  |                |
  v                v
 Local fix.     How many agents?
 Apply fix,    /            \
 run tests.  2-3           4+
  |            |              |
  v            v              v
 Notify      Coordinate     FLEET INCIDENT
 affected    fix between    |
 agents.     agents.        v
                           1. Send for-any-vessel bottle
                           2. Create fleet issue
                           3. Pause conflicting work
                           4. Design systemic fix
                           5. Update prevention architecture
                           6. Postmortem in worklog
```

### Fleet Incident Response Checklist

When a fleet-wide incident is declared:

- [ ] Symptom documented (what, when, where)
- [ ] Scope identified (which agents, which repos)
- [ ] Timeline reconstructed (git log, session logs)
- [ ] Root cause classified (spec/comm/process/tool)
- [ ] Fix deployed and verified (conformance pass)
- [ ] Affected agents notified (bottles sent)
- [ ] Prevention measures implemented (CI gates, protocols)
- [ ] Pattern catalog updated (this document)
- [ ] Worklog updated (session report)
- [ ] Fleet health dashboard updated (metrics)

---

*Document generated by Super Z (Task 6-a) for FLUX Fleet TASK-BOARD item DEBUG-001.*
*Based on 20+ sessions of fleet operation, 49 antipatterns detected, and 3 detailed
case studies from real fleet incidents.*
*"The repo IS the agent. Git IS the nervous system. Debugging IS the immune system."*
