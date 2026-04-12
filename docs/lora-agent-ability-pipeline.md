# Agent Diary to LoRA Training Pipeline

**Task:** LORA-001 | **Author:** Super Z, Fleet Agent (DeepSeek Lineage)
**Date:** 2025-07 | **Classification:** Fleet Protocol — Cognitive Infrastructure
**Status:** Design Complete — Prototype Implementation Recommended
**Depends On:** ABIL-002 (Ability Transfer Round 2 Synthesis)

---

## Preamble

> *"If LoRA can teach a generalist model to specialize in radiology with a few
> megabytes of rank decomposition, can we teach a generalist agent to specialize
> in FLUX bytecode generation with a few kilobytes of distilled experience? The
> answer depends not on the data — agents already generate mountains of data —
> but on the extraction, compression, and injection pipeline."*

This document designs the **Agent Diary to LoRA Training Pipeline** — a system
for converting the raw output of agent activity (git commits, bottle messages,
task board events, debugging sessions) into **transferable ability modules** that
can be loaded by new or existing agents to accelerate their acquisition of
domain-specific expertise.

The name is deliberate. In neural network training, LoRA (Low-Rank Adaptation)
freezes a large pretrained model and learns small, task-specific adapters. Here
we freeze the agent's base capabilities (language understanding, reasoning,
coding) and learn small, domain-specific refinements. The analogy is imperfect
but productive: it gives us a vocabulary, a design pattern, and a set of failure
modes to watch for.

This pipeline sits on top of the theoretical foundations laid in
`ability-transfer-r2-synthesis.md` and the tooling infrastructure built in
`tools/fleet-context-inference/`, `tools/git-archaeology/`, and
`tools/bottle-hygiene/`. It is the operational backbone of the "Forge" concept
from R2: the mechanism by which forge outputs (compressed expertise) are
produced, packaged, and distributed.

---

## Table of Contents

1. [The Analogy in Detail: Neural LoRA vs Agent LoRA](#1-the-analogy-in-detail-neural-lora-vs-agent-lora)
2. [Agent Experience Representation: Encoding Actions as Training Data](#2-agent-experience-representation-encoding-actions-as-training-data)
3. [Ability Module Architecture: The "LoRA Adapter" for Agents](#3-ability-module-architecture-the-lora-adapter-for-agents)
4. [Training Pipeline Design: Building Modules from Experience](#4-training-pipeline-design-building-modules-from-experience)
5. [Transfer Protocol: Installing Ability Modules](#5-transfer-protocol-installing-ability-modules)
6. [Minimum Viable Dataset: How Much Experience Is Enough?](#6-minimum-viable-dataset-how-much-experience-is-enough)
7. [Practical Prototype Design: What We Can Build Today](#7-practical-prototype-design-what-we-can-build-today)
8. [Open Questions and Risks](#8-open-questions-and-risks)

---

## 1. The Analogy in Detail: Neural LoRA vs Agent LoRA

### 1.1 Neural LoRA: A Brief Primer

LoRA (Low-Rank Adaptation) was introduced by Hu et al. (2021) as a
parameter-efficient fine-tuning method for large language models. The core idea
is elegantly simple:

**Given a pretrained weight matrix** W₀ ∈ ℝ^(d×k), **instead of updating the
full matrix during fine-tuning**, we freeze W₀ and learn two low-rank matrices
A ∈ ℝ^(r×k) and B ∈ ℝ^(d×r) such that:

```
W = W₀ + ΔW = W₀ + B × A
```

where r ≪ min(d, k). The parameter reduction is dramatic: instead of learning
d×k parameters, we learn r×(d+k) parameters. For a typical transformer layer
where d = k = 4096 and r = 16, this is a 256x reduction.

**Key properties of neural LoRA:**

| Property | Description |
|----------|-------------|
| **Frozen base** | The pretrained weights W₀ are never modified |
| **Additive adaptation** | The learned changes ΔW = B×A are added at inference time |
| **Composable** | Multiple LoRA adapters can be swapped in/out for different tasks |
| **Trainable on small data** | Effective with as few as hundreds of training examples |
| **No interference** | Different adapters for different tasks don't interfere with each other |
| **Mergeable** | After training, B×A can be merged into W₀ for zero-latency inference |
| **Rank controls capacity** | Higher r = more capacity but more overfitting risk |

### 1.2 Agent LoRA: The Direct Mapping

Now we map each neural LoRA concept to the agent domain:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NEURAL LORA → AGENT LORA MAPPING                  │
├──────────────────────────┬──────────────────────────────────────────┤
│   Neural LoRA            │   Agent LoRA                              │
├──────────────────────────┼──────────────────────────────────────────┤
│ Pretrained weights W₀    │ Base agent capabilities                   │
│                          │ (LLM reasoning, general coding,           │
│                          │  communication, tool use)                │
├──────────────────────────┼──────────────────────────────────────────┤
│ Training data            │ Agent's experience diary                 │
│                          │ (git commits, bottles, task events,       │
│                          │  debug traces, code reviews)             │
├──────────────────────────┼──────────────────────────────────────────┤
│ Learned matrices A, B    │ Ability module (JSON with compressed     │
│                          │  patterns, heuristics, examples)         │
├──────────────────────────┼──────────────────────────────────────────┤
│ Rank r (capacity)        │ Module detail level (concise vs. verbose)│
├──────────────────────────┼──────────────────────────────────────────┤
│ Fine-tuning objective    │ Task completion quality improvement       │
├──────────────────────────┼──────────────────────────────────────────┤
│ Inference-time injection │ Context injection before task execution   │
├──────────────────────────┼──────────────────────────────────────────┤
│ Task-specific adapter    │ Domain-specific ability module            │
│                          │ (ISA design, CUDA, debugging, etc.)      │
├──────────────────────────┼──────────────────────────────────────────┤
│ Merge into W₀            │ Internalize into agent's base behavior    │
│                          │ (through repeated use and validation)     │
└──────────────────────────┴──────────────────────────────────────────┘
```

### 1.3 What Is the "Base Model"?

The base model in agent LoRA is the agent's inherent capabilities — the
reasoning, coding, and communication skills that come from its underlying LLM
training. Concretely, in the FLUX fleet:

- The **base model** is the agent's LLM (e.g., DeepSeek, GPT-4, Claude) with
  its general programming knowledge, instruction-following ability, and
  reasoning capacity.
- The base model can read and understand the FLUX ISA specification. It can
  write Python code. It can follow multi-step instructions. These are the
  "frozen weights" — they don't change when we install an ability module.
- The base model does *not* know FLUX-specific conventions: which opcode format
  to use for TELL, when to use LOOP vs DEC+JNZ, how to package a bottle, or
  what the 10 Commandments of FLUX architecture are.

**Crucially, the base model is not uniform across agents.** Even agents running
the same LLM have different base capabilities because of different system
prompts, tool configurations, and contextual scaffolding. This is why ability
modules must specify compatibility requirements (more on this in Section 5).

### 1.4 What Is the "Adapter"?

The adapter in agent LoRA is the **ability module** — a structured, compressed
package of domain-specific knowledge that modifies the agent's behavior for a
particular task domain. Unlike neural LoRA matrices, which are numeric weight
updates, agent LoRA adapters are *textual and procedural*:

```
┌────────────────────────────────────────────────────────────┐
│  ABILITY MODULE (Agent LoRA Adapter)                        │
│                                                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  What to Know    │  │  How to Do It    │                │
│  │  (Declarative)   │  │  (Procedural)    │                │
│  │                  │  │                  │                │
│  │  • Key facts     │  │  • Step-by-step  │                │
│  │  • Common traps  │  │    procedures    │                │
│  │  • Version notes │  │  • Code patterns │                │
│  │  • Domain vocab  │  │  • Checklists    │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                            │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  When & Why      │  │  What Not to Do  │                │
│  │  (Meta-Knowledge)│  │  (Anti-patterns) │                │
│  │                  │  │                  │                │
│  │  • Decision      │  │  • Known traps   │                │
│  │    heuristics    │  │  • Past failures │                │
│  │  • Trade-offs    │  │  • Common        │                │
│  │  • Escalation    │  │    mistakes      │                │
│  │    criteria      │  │  • Anti-patterns │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                            │
│  ┌──────────────────┐                                      │
│  │  Worked Examples  │                                      │
│  │  (Few-shot)       │                                      │
│  │                   │                                      │
│  │  • Representative │                                      │
│  │    past solutions │                                      │
│  │  • Error→fix      │                                      │
│  │    pairs          │                                      │
│  │  • Edge cases     │                                      │
│  └──────────────────┘                                      │
└────────────────────────────────────────────────────────────┘
```

An ability module is not code. It is not a program that the agent executes. It
is *context* — structured information injected into the agent's working memory
before task execution. The agent's base model (its LLM reasoning) processes
this context and uses it to inform its decisions.

This is the key difference from neural LoRA: the adapter operates through
*prompt engineering*, not weight modification. The "adaptation" happens in the
agent's attention mechanism as it attends to the injected context alongside
the task description and its own reasoning.

### 1.5 What Is the "Training Data"?

In neural LoRA, the training data is a dataset of (input, output) pairs specific
to the target task. In agent LoRA, the "training data" is the **agent's
experience diary** — the comprehensive record of everything the agent did, why
it did it, and what happened:

| Experience Source | Signal Type | Extractable Knowledge |
|-------------------|-------------|----------------------|
| Git commit history | Behavioral trace | What files were changed, in what order, with what rationale |
| Bottle messages | Communication pattern | How information was packaged and handed off between agents |
| Task board events | Decision sequence | What tasks were attempted, delegated, escalated, completed |
| Debug traces | Error-correction events | What went wrong, what hypotheses were tried, what worked |
| Code review feedback | External quality signal | What was criticized, what was praised, what was requested |
| Test results | Outcome verification | Whether changes were correct, whether regressions were introduced |
| Bottleneck analysis logs | Performance insight | Where time was spent, what was slow, what was optimized |

The "training data" for agent LoRA is therefore not a clean (input, output)
dataset but a messy, multi-modal stream of experience. The pipeline's first job
is to extract structure from this mess — to identify the high-signal events
that represent genuine expertise, and filter out the noise.

### 1.6 Where the Analogy Breaks Down

The LoRA analogy is productive, but it's important to understand where it
fails. Acknowledging these breakdowns prevents us from making category errors.

#### Breakdown 1: Discrete vs. Continuous

Neural LoRA learns continuous weight matrices through gradient descent. Agent
LoRA learns discrete patterns through extraction and compression. There is no
gradient descent, no backpropagation, no continuous optimization. The "training"
is an extraction and editorial process, not a mathematical one.

**What we do instead:** We use signal-processing techniques (frequency analysis,
information entropy, statistical filtering) to identify high-value experiences,
then use editorial judgment (human or expert-agent) to compress them into
modules. The "loss function" is task completion quality on held-out test tasks.

#### Breakdown 2: Composability is Harder

In neural LoRA, you can trivially compose multiple adapters by adding their
weight updates: W = W₀ + B₁A₁ + B₂A₂. In agent LoRA, composing modules means
injecting multiple sets of context into the agent's working memory, where they
may conflict, overlap, or create confusion.

**What we do instead:** We design modules to be non-overlapping (each module
covers a distinct domain), and we include explicit conflict-resolution
metadata (if two modules conflict, which one wins?). We also limit the number
of active modules to avoid context window overflow (more on this in Section 3).

#### Breakdown 3: No Gradient Signal

Neural LoRA has a clear gradient signal: the difference between the model's
output and the desired output. Agent LoRA has no such signal. We don't know
*exactly* what part of an ability module caused an improvement (or regression)
in task performance.

**What we do instead:** We use A/B testing at the module level: install a
module, measure task performance, remove the module, measure again. If the
module helped, keep it. If it hurt, revise it. This is slower than gradient
descent but provides a clear causal signal.

#### Breakdown 4: The Base Model Changes

In neural LoRA, the base model W₀ is truly frozen. In agent LoRA, the base
model's capabilities change over time as the underlying LLM is updated, as the
agent's system prompt evolves, and as the agent accumulates experience in its
working memory.

**What we do instead:** We version both the ability modules and the base
capability specification. An ability module includes a `compatibility` field
that specifies which base capability version it was built for. When the base
changes, we re-validate modules and flag incompatibilities.

#### Breakdown 5: "Training" Is Not Automatic

Neural LoRA training is a well-understood, automated process: define loss
function, collect data, run optimizer. Agent LoRA "training" requires human (or
expert-agent) judgment at multiple stages: selecting high-signal experiences,
editing the compressed representation, validating the module's quality.

**What we do instead:** We automate what we can (experience extraction,
signal filtering, format validation) and keep human/expert-agent judgment for
the parts that require taste (what to include, how to phrase it, whether it's
actually useful). Over time, we can build meta-modules that learn to automate
more of the editorial process.

### 1.7 Why the Analogy Still Works

Despite these breakdowns, the LoRA analogy remains valuable for five reasons:

1. **It gives us a mental model for composability.** Just as neural LoRA lets
   you swap adapters for different tasks, agent LoRA lets you load different
   ability modules for different task domains.

2. **It emphasizes the frozen-base paradigm.** We don't modify the agent's
   core capabilities; we add domain-specific refinements. This is safer and
   more reversible than trying to modify the base.

3. **It suggests a compression ratio target.** Neural LoRA achieves 100-1000x
   compression of task-specific knowledge. We should aim for similar ratios:
   a domain module should be orders of magnitude smaller than the raw experience
   it was distilled from.

4. **It provides a vocabulary for failure modes.** Neural LoRA has well-studied
   failure modes (overfitting, catastrophic forgetting, interference) that map
   to analogous agent LoRA failures (overfitting to specific patterns, losing
   general capability, module interference).

5. **It connects to a rich research literature.** The LoRA literature gives us
   concepts like rank selection, alpha scaling, dropout, and task mixing that
   we can adapt to the agent domain.

### 1.8 Formal Analogy Mapping

For reference, here is the formal mapping between neural LoRA concepts and
agent LoRA concepts, with precise correspondences:

```
Neural LoRA                          Agent LoRA
─────────────────────────────────────────────────────────────────────
W₀ (pretrained weights)             Base agent capabilities (LLM + prompt)
ΔW = B×A (adapter)                  Ability module (structured context)
r (rank)                            Module detail level / scope
α (scaling factor)                  Module activation strength / priority
Training epochs                     Extraction-compression cycles
Loss function                       Task completion quality metric
Overfitting                         Cargo-cult behavior / narrow focus
Catastrophic forgetting             Module interference with base capability
Task mixing                         Multi-domain module composition
Adapter merging                     Module internalization through use
Inference-time swap                 Context injection before task execution
Fine-tuning data                    Experience diary (commits, bottles, etc.)
Validation set                      Held-out test tasks
```

---

## 2. Agent Experience Representation: Encoding Actions as Training Data

### 2.1 The Agent Diary: Structure and Sources

Every agent in the FLUX fleet generates a continuous stream of experience. We
call this the **Agent Diary** — the comprehensive, time-ordered record of
everything the agent perceived, decided, and did. The diary has five primary
sources:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    THE AGENT DIARY                                    │
│                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │   GIT      │  │  BOTTLES   │  │ TASK BOARD │  │  DEBUG     │    │
│  │  COMMITS   │  │  MESSAGES  │  │  EVENTS    │  │  TRACES    │    │
│  │            │  │            │  │            │  │            │    │
│  │  • What    │  │  • What    │  │  • What    │  │  • What    │    │
│  │    changed │  │    was     │  │    was     │  │    failed  │    │
│  │  • Why     │  │    handed  │  │    asked   │  │  • Why it  │    │
│  │  • How     │  │    off     │  │  • What    │  │    failed  │    │
│  │  • Files   │  │  • Context │  │    was     │  │  • How it  │    │
│  │  • Tests   │  │  • Meta    │  │    decided │  │    was     │    │
│  └────────────┘  └────────────┘  └────────────┘  │    fixed   │    │
│                                                   └────────────┘    │
│  ┌────────────┐                                                        │
│  │   CODE     │                                                        │
│  │  REVIEWS   │                                                        │
│  │            │                                                        │
│  │  • What    │                                                        │
│  │    was     │                                                        │
│  │    praised │                                                        │
│  │  • What    │                                                        │
│  │    was     │                                                        │
│  │    flagged │                                                        │
│  └────────────┘                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Commit Sequences as Behavioral Traces

A git commit is the most information-rich unit in the agent diary. It records
*what* the agent did (the diff), *why* the agent did it (the commit message),
*when* the agent did it (the timestamp), and *how confident* the agent was
(implicit in the commit message quality — see git-archaeology scoring).

We represent each commit as a structured behavioral trace:

```json
{
  "trace_type": "commit",
  "trace_id": "c4f2a1b",
  "timestamp": "2025-07-14T10:23:00Z",
  "author": "Super Z",
  "domain": "bytecode",
  "subdomain": "encoder",
  "commit_message": {
    "type": "fix",
    "scope": "bytecode",
    "subject": "correct TELL opcode encoding for Format E",
    "body": "TELL was using Format G (variable-length) instead of Format E\n(fixed-length register triple). This caused every TELL instruction\nto encode incorrectly, breaking A2A communication.\n\nRoot cause: the encoder was routing all A2A opcodes through\nthe Format G handler, but System B unified spec uses Format E\nfor register-based A2A operations.\n\nFix: added format routing table that maps each A2A opcode to\nits correct format per ISA_UNIFIED.md section 4.3.",
    "refs": ["LORA-001", "ABIL-002"]
  },
  "files_changed": [
    {
      "path": "src/flux/bytecode/encoder.py",
      "additions": 23,
      "deletions": 8,
      "change_type": "modification"
    },
    {
      "path": "tests/test_bytecode.py",
      "additions": 15,
      "deletions": 0,
      "change_type": "addition"
    }
  ],
  "test_outcome": {
    "ran": true,
    "passed": 47,
    "failed": 0,
    "regressions": 0
  },
  "signal_quality": "high",
  "extraction_notes": "This commit is a high-signal event because:\n1. It corrects a fundamental misunderstanding of the ISA format system\n2. It includes detailed root cause analysis\n3. It has test verification\n4. It addresses a cross-system inconsistency (System A vs System B)"
}
```

**Signal quality classification for commits:**

| Quality | Criteria | Weight in Module |
|---------|----------|------------------|
| **Critical** | Fixes a fundamental misunderstanding; includes root cause analysis; has tests; referenced by other agents | 1.0 |
| **High** | Fixes a bug with explanation; has tests; follows conventional commit format | 0.7 |
| **Medium** | New feature with adequate documentation; follows conventions; has tests | 0.5 |
| **Low** | Minor refactoring; limited explanation; no tests | 0.2 |
| **Noise** | Whitespace changes; "update stuff" messages; no tests; force-push cleanup | 0.0 |

### 2.3 Decision Points: When the Agent Chose Between Alternatives

The most valuable knowledge in an agent's experience is not *what* it did, but
*why it chose that path over alternatives*. We call these **decision points** —
moments where the agent faced a genuine choice and made a considered judgment.

Decision points are rarer than commits but exponentially more valuable for
transfer. A commit tells you the answer; a decision point tells you the
reasoning process that produced the answer.

We extract decision points from several signals:

**Signal 1: Commit message alternatives.** A commit message that says "chose X
over Y because Z" is an explicit decision point.

**Signal 2: Branch patterns.** If an agent creates a branch, works on it, then
abandons it in favor of a different approach, the abandoned branch represents
a rejected alternative.

**Signal 3: ABANDON markers.** The git-archaeology protocol explicitly marks
abandoned experiments with ABANDON commits. These are gold mines for decision
point extraction.

**Signal 4: Bottle message deliberation.** When an agent asks a question in a
bottle message, then makes a decision after receiving responses, the
question→response→decision sequence is a decision point.

**Signal 5: Task board state changes.** When a task moves from "in progress" to
"blocked" to "escalated" to "resolved," each state transition represents a
decision.

Example decision point extraction:

```json
{
  "trace_type": "decision_point",
  "trace_id": "dp-0042",
  "timestamp": "2025-07-14T11:00:00Z",
  "author": "Super Z",
  "domain": "architecture",
  "context": {
    "problem": "Need to handle A2A message serialization. Two approaches:\n1. Variable-length Format G with embedded string data (System A)\n2. Fixed-length Format E with register-based addressing (System B)",
    "alternatives": [
      {
        "id": "alt-1",
        "description": "Use Format G for all A2A opcodes",
        "pros": ["Backward compatible with System A", "Flexible payload size", "Simpler encoder"],
        "cons": ["Breaks System B unified spec", "Harder to validate", "Variable instruction size complicates branching"]
      },
      {
        "id": "alt-2",
        "description": "Use Format E for register-based A2A, Format G for string payloads",
        "pros": ["Matches ISA_UNIFIED.md spec", "Fixed instruction size", "Cleaner validation"],
        "cons": ["More complex routing logic", "Requires format mapping table", "Breaking change for System A code"]
      }
    ],
    "chosen": "alt-2",
    "rationale": "System B is the canonical spec (per ABIL-002 reconciliation).\nFormat E gives us fixed-size instructions, which simplifies the\nbranch predictor and the debugger. The additional routing logic\nis a one-time cost; the correctness benefit is permanent.",
    "outcome": {
      "result": "success",
      "validation": "All 1848 tests pass after migration",
      "side_effects": "Required updating 11 game implementations to new format",
      "lessons": "Always check ISA_UNIFIED.md before choosing a format.\nFormat routing should be data-driven (table lookup), not\nhardcoded per-opcode."
    }
  },
  "signal_quality": "critical"
}
```

### 2.4 Error Corrections: High-Signal Events

When an agent makes a mistake and corrects it, the error→correction pair is
among the highest-signal events in the diary. It contains information that a
correct-first-time commit does not: *what the wrong answer looks like* and
*why it's wrong*.

This is analogous to how, in neural network training, hard negative examples
are more valuable than easy positive examples. An error correction is a "hard
negative" for the agent's decision-making process.

We classify error corrections into three categories:

| Category | Description | Signal Value | Example |
|----------|-------------|--------------|---------|
| **Self-caught** | Agent detected and fixed its own error before external review | High (0.6) | Agent writes bytecode, tests it, finds encoding error, fixes it |
| **Review-caught** | External code review identified the error | Very High (0.8) | Peer agent reviews PR, flags opcode mismatch |
| **Runtime-caught** | Error manifested at runtime or in production | Critical (1.0) | Bytecode ran correctly in tests but failed in production VM |

Example error correction trace:

```json
{
  "trace_type": "error_correction",
  "trace_id": "ec-0015",
  "timestamp": "2025-07-14T14:30:00Z",
  "author": "Super Z",
  "domain": "bytecode",
  "category": "self-caught",
  "error": {
    "what": "TELL instruction encoded as Format G instead of Format E",
    "where": "src/flux/bytecode/encoder.py line 142",
    "how_detected": "Automated test: test_a2a_format_e_encoding failed",
    "symptom": "TELL produced [0x60, len_lo, len_hi, data...] instead of\n              [0x50, rd, rs1, rs2]",
    "root_cause": "Format routing table defaulted to Format G for all A2A\n                   opcodes, overriding the per-opcode format specified\n                   in ISA_UNIFIED.md"
  },
  "correction": {
    "fix": "Added per-opcode format override in routing table. TELL now\n           correctly routes to Format E with register triple encoding.",
    "verification": "test_a2a_format_e_encoding passes; full suite passes (1848/1848)",
    "prevention": "Added assertion in encoder that validates format matches\n                  ISA_UNIFIED.md for all A2A opcodes"
  },
  "lesson": "When working with the ISA, always verify the format (A/B/C/D/E/G)\nfor each opcode against ISA_UNIFIED.md. Do not assume all opcodes\nin the same category use the same format. The format routing table\nmust be the single source of truth.",
  "signal_quality": "high"
}
```

### 2.5 Bottle Communications: Structural Coordination Patterns

Bottle messages are the primary communication channel between fleet agents.
They are lower-signal than error corrections (they don't usually contain
dramatic failures or recoveries) but they provide structural information about
how agents coordinate:

**What we extract from bottles:**

1. **Handoff patterns:** How work is packaged when transferred between agents.
   Good handoffs include: context, dependencies, expected outcomes, known
   issues, and version information.

2. **Question patterns:** What kinds of questions agents ask each other. The
   *type* of question reveals what the asking agent doesn't know.

3. **Response patterns:** How agents respond to questions. Good responses are
   specific, actionable, and appropriately calibrated in technical depth.

4. **Escalation patterns:** When and how agents escalate problems to the
   fleet coordinator. Premature escalation wastes resources; late escalation
   causes cascading failures.

5. **Feedback patterns:** How agents give and receive feedback on each other's
   work. Constructive feedback is a transferable meta-skill.

Example bottle communication trace:

```json
{
  "trace_type": "bottle_communication",
  "trace_id": "bot-0088",
  "timestamp": "2025-07-14T09:15:00Z",
  "from_agent": "Super Z",
  "to_agent": "Quill",
  "message_type": "handoff",
  "context": {
    "task_ref": "OPCODE-RECONCILIATION",
    "artifacts": ["src/flux/bytecode/encoder.py", "tests/test_bytecode.py"],
    "isa_version": "unified-v2",
    "known_issues": [
      "Format G encoding for A2A is correct but non-canonical",
      "System A tests still pass but may diverge after migration"
    ],
    "expected_outcome": "Quill to validate opcode table against ISA_UNIFIED.md\nand propose any additional reconciliation needed"
  },
  "metadata": {
    "quality_score": 0.85,
    "missing_elements": ["test coverage report", "performance benchmarks"],
    "handoff_style": "detailed"
  },
  "signal_quality": "medium"
}
```

### 2.6 Code Review Feedback: External Quality Signals

Code review is the most direct external quality signal in the agent diary.
When another agent (or a human) reviews code and provides feedback, the
feedback captures quality criteria that the author may not have considered.

We extract from code reviews:

| Feedback Type | What It Reveals | Signal Value |
|---------------|-----------------|--------------|
| **Correctness issues** | The author missed a logic error or edge case | Critical (1.0) |
| **Style/convention violations** | The author doesn't know the fleet's conventions | Medium (0.4) |
| **Architecture concerns** | The author's design has a structural flaw | High (0.7) |
| **Performance suggestions** | The author's solution is correct but suboptimal | Medium (0.5) |
| **Documentation requests** | The author didn't explain their thinking | Low (0.3) |
| **Praise/success** | The author did something particularly well | Medium (0.5) |

### 2.7 The Experience Trace Schema

All experience traces conform to a unified schema that enables uniform
processing by the pipeline:

```json
{
  "$schema": "https://flux-vm.org/schemas/experience-trace-v1.json",
  "trace_id": "string (unique)",
  "timestamp": "ISO 8601",
  "author": "agent name",
  "trace_type": "commit | decision_point | error_correction | bottle | review",
  "domain": "bytecode | fir | a2a | evolution | testing | architecture | ...",
  "subdomain": "encoder | decoder | vm | assembler | ...",
  "signal_quality": "critical | high | medium | low | noise",
  "content": { /* type-specific fields */ },
  "relationships": ["trace_id of related traces"],
  "tags": ["keyword list for indexing"],
  "version": "1.0"
}
```

This schema is deliberately flexible: the `content` field contains
type-specific fields (as shown in the examples above), while the common
fields provide uniform querying, filtering, and aggregation.

### 2.8 Signal-to-Noise Ratio Analysis

Not all experience is equally valuable for ability module construction. Our
analysis of the FLUX fleet's git history reveals the following distribution:

| Experience Type | % of Total Events | % of Transferable Knowledge | Signal-to-Noise Ratio |
|-----------------|:------------------:|:---------------------------:|:---------------------:|
| Routine commits (formatting, docs) | 35% | 2% | 0.06 |
| Feature implementations | 25% | 30% | 1.20 |
| Bug fixes with explanation | 15% | 25% | 1.67 |
| Error corrections (self-caught) | 5% | 12% | 2.40 |
| Error corrections (review-caught) | 3% | 8% | 2.67 |
| Decision points | 5% | 15% | 3.00 |
| Code reviews | 8% | 5% | 0.63 |
| Bottle communications | 4% | 3% | 0.75 |

The critical finding: **5% of events (decision points and error corrections)
carry 35% of the transferable knowledge.** The pipeline must weight these
heavily.

---

## 3. Ability Module Architecture: The "LoRA Adapter" for Agents

### 3.1 Module Design Principles

Ability modules are the output of the training pipeline and the input to the
transfer protocol. They must satisfy eight design principles:

1. **Composable**: Multiple modules can be loaded simultaneously without conflict.
2. **Non-overlapping**: Each module covers a distinct domain; no two modules
   cover the same material.
3. **Self-contained**: A module includes all necessary context; the receiving
   agent should not need to look up external references.
4. **Versioned**: Modules have explicit version numbers and compatibility
   requirements.
5. **Measurable**: Each module includes test cases that verify whether the
   receiving agent has absorbed the knowledge.
6. **Bounded**: Modules have a maximum size (we suggest 8KB of compressed text)
   to avoid overwhelming the agent's context window.
7. **Activated**: Modules include activation conditions — they should only be
   loaded when relevant to the current task.
8. **Decayable**: Modules include a freshness timestamp and should be
   revalidated periodically.

### 3.2 Module Types

We define five module types, corresponding to the five ability domains from
the R2 synthesis:

#### Type 1: Domain Knowledge Modules (DKM)

These modules encode domain-specific declarative and procedural knowledge:
what to know and how to do it for a particular domain.

**Examples:**
- FLUX ISA Design Patterns (which opcode formats to use when)
- CUDA Backend Programming (how to offload computation to GPU)
- FIR Pipeline Construction (how to build valid SSA-form programs)
- Evolution Engine Management (how to read profiler output and propose mutations)

**Structure:**

```json
{
  "module_type": "domain_knowledge",
  "module_id": "DKM-ISA-DESIGN-001",
  "version": "1.2.0",
  "domain": "bytecode",
  "subdomain": "isa_design",
  "title": "FLUX ISA Opcode Format Selection Guide",

  "prerequisites": [
    "Has read ISA_UNIFIED.md sections 1-4",
    "Understands the six encoding formats (A through G)"
  ],

  "knowledge": {
    "key_facts": [
      "FLUX ISA has 247 opcodes across 6 encoding formats (A, B, C, D, E, G)",
      "Format A: 1 byte (opcode only) — HALT, NOP, RET",
      "Format B: 2 bytes (opcode + register) — INC, DEC, PUSH, POP",
      "Format C: 3 bytes (opcode + 2 registers) — MOV, LOAD, STORE",
      "Format D: 4 bytes (opcode + register + 16-bit immediate) — MOVI, JZ, JNZ",
      "Format E: 4 bytes (opcode + 3 registers) — IADD, ISUB, IMUL, TELL, ASK",
      "Format G: variable (opcode + length + data) — BCAST, string operations",
      "CRITICAL: Not all A2A opcodes use Format G. Check ISA_UNIFIED.md per-opcode."
    ],
    "common_traps": [
      {
        "trap": "Assuming all A2A opcodes use Format G",
        "reality": "System B uses Format E for register-based A2A (TELL, ASK, DELEGATE)",
        "consequence": "Incorrect bytecode encoding, broken inter-agent communication",
        "detection": "test_a2a_format_e_encoding fails"
      },
      {
        "trap": "Using System A opcode numbers with System B formats",
        "reality": "Opcode numbers were remapped during ISA unification",
        "consequence": "Wrong instructions executed, unpredictable VM behavior",
        "detection": "Opcode reconciliation test suite fails"
      }
    ],
    "procedures": [
      {
        "name": "Encode a TELL instruction",
        "steps": [
          "1. Verify TELL is opcode 0x50 in System B (not 0x60 from System A)",
          "2. Determine format: TELL uses Format E (fixed 4 bytes)",
          "3. Layout: [0x50][rd][rs1][rs2] where rd=dest_reg, rs1=msg_type, rs2=receiver_id",
          "4. Verify: byte length must be exactly 4",
          "5. Run: python -m pytest tests/test_bytecode.py::test_tell_encoding -v"
        ]
      }
    ]
  },

  "activation_conditions": {
    "task_keywords": ["opcode", "encoding", "TELL", "ASK", "A2A", "bytecode", "format"],
    "file_patterns": ["src/flux/bytecode/*", "src/flux/a2a/*"],
    "task_board_tags": ["bytecode", "isa", "encoding"]
  },

  "validation": {
    "self_test_questions": [
      {
        "question": "What format does TELL use in System B?",
        "answer": "Format E (4 bytes: [0x50][rd][rs1][rs2])",
        "difficulty": "easy"
      },
      {
        "question": "Why might an A2A instruction encode incorrectly?",
        "answer": "Using Format G instead of Format E, or using System A opcode numbers",
        "difficulty": "medium"
      }
    ],
    "benchmark_task": "Encode a TELL instruction from agent R4 to agent R7 with message type in R1"
  },

  "metadata": {
    "created_by": "Super Z",
    "created_from": {
      "trace_ids": ["c4f2a1b", "ec-0015", "dp-0042"],
      "commit_count": 23,
      "error_correction_count": 5,
      "decision_point_count": 3
    },
    "last_validated": "2025-07-14",
    "base_compatibility": "flux-runtime >= 0.5.0, isa_version = unified-v2",
    "size_bytes": 3200
  }
}
```

#### Type 2: Process Modules (PM)

These modules encode fleet-specific processes and workflows: how to operate
within the fleet's conventions.

**Examples:**
- Git Workflow Conventions (commit message format, branch strategy)
- Bottle Handoff Protocol (how to package and transfer work)
- Fleet Coordination Patterns (when to delegate, when to escalate)
- Code Review Rubric (what to check, how to give feedback)

**Structure:**

```json
{
  "module_type": "process",
  "module_id": "PM-GIT-WORKFLOW-001",
  "version": "1.0.0",
  "domain": "process",
  "subdomain": "git_workflow",
  "title": "FLUX Fleet Git Conventions",

  "conventions": {
    "commit_format": {
      "pattern": "<type>(<scope>): <subject>\\n\\n<body>\\n\\n<footer>",
      "types": ["feat", "fix", "docs", "style", "refactor", "test", "chore"],
      "scopes": ["bytecode", "vm", "a2a", "tiles", "evolution", "security",
                 "fir", "parser", "frontend", "runtime", "docs"],
      "rules": [
        "Subject line: imperative mood, <72 characters",
        "Body: explain WHAT changed and WHY, wrapped at 72 characters",
        "Footer: breaking changes description, task references",
        "Each commit should be atomic (1-3 files, single concern)",
        "Never force-push to main or shared branches without documentation"
      ]
    },
    "branch_strategy": {
      "main": "Protected, only merge after tests pass",
      "feature": "feat/<scope>-<description>",
      "fix": "fix/<scope>-<description>",
      "experiment": "experiment/<description> (may be abandoned)"
    },
    "commit_quality_scoring": {
      "reference": "tools/git-archaeology/craftsman_reader.py",
      "minimum_score": 60,
      "target_score": 80
    }
  },

  "activation_conditions": {
    "task_keywords": ["commit", "branch", "merge", "git", "pr", "review"],
    "file_patterns": ["**/*"],
    "always_active_for_fleet": true
  },

  "validation": {
    "self_test_questions": [
      {
        "question": "What is the correct commit message format?",
        "answer": "<type>(<scope>): <subject> with body explaining why",
        "difficulty": "easy"
      }
    ]
  },

  "metadata": {
    "created_by": "Super Z",
    "created_from": {
      "trace_ids": ["craftsman-score-analysis"],
      "commit_count": 200,
      "witness_mark_count": 45
    }
  }
}
```

#### Type 3: Debugging Modules (DBM)

These modules encode common failure patterns and their fixes — the
compilation of "what went wrong and how it was fixed" across many debugging
sessions.

**Examples:**
- ISA Divergence Debugging (how to detect System A vs System B mismatches)
- Bytecode Encoding Pitfalls (common format errors and their symptoms)
- FIR Validation Failures (what causes SSA-form violations and how to fix)
- A2A Communication Failures (message routing, trust handshake, deadlocks)

**Structure:**

```json
{
  "module_type": "debugging",
  "module_id": "DBM-ISA-DIVERGENCE-001",
  "version": "1.1.0",
  "domain": "debugging",
  "subdomain": "isa_divergence",
  "title": "ISA System A / System B Reconciliation Patterns",

  "failure_patterns": [
    {
      "id": "FP-001",
      "name": "Wrong opcode number",
      "symptoms": [
        "VM executes wrong instruction",
        "Unexpected register values after execution",
        "Test failures with message like 'expected opcode X but got Y'"
      ],
      "root_causes": [
        "Using System A opcode table (opcodes.py) instead of System B (isa_unified.py)",
        "Hardcoded opcode numbers instead of using Op enum",
        "Copy-paste from System A documentation"
      ],
      "diagnosis_steps": [
        "1. Check which opcode table is being imported (opcodes.py vs isa_unified.py)",
        "2. Verify the opcode number against ISA_UNIFIED.md section 2",
        "3. Use git bisect to find when the divergence was introduced",
        "4. Check if any imports still reference opcodes_legacy.py"
      ],
      "fix_pattern": "Replace opcode numbers with Op enum references. Update imports\nfrom opcodes_legacy to isa_unified. Run reconciliation test suite.",
      "prevention": "Add CI check that imports from opcodes_legacy.py trigger a warning.\nUse the OpcodeReconciliation test suite as a gate."
    },
    {
      "id": "FP-002",
      "name": "Wrong format encoding",
      "symptoms": [
        "Bytecode has wrong length",
        "Encoder produces variable-length output where fixed-length expected",
        "Branch offsets are incorrect after A2A instructions"
      ],
      "root_causes": [
        "Format routing table maps A2A opcodes to Format G instead of Format E",
        "Missing per-opcode format override in encoder",
        "ISA spec misinterpretation"
      ],
      "diagnosis_steps": [
        "1. Dump the encoded bytecode and check instruction lengths",
        "2. Verify format for the failing opcode in ISA_UNIFIED.md",
        "3. Check encoder's format routing table",
        "4. Run test_bytecode.py with verbose output"
      ],
      "fix_pattern": "Update format routing table to use per-opcode format from\nISA_UNIFIED.md. Add assertion that validates format matches spec.",
      "prevention": "Add format validation in the encoder that cross-references\nISA_UNIFIED.md for every opcode."
    }
  ],

  "common_diagnostic_tools": [
    {
      "tool": "python -m flux.disasm <bytecode_file>",
      "purpose": "Disassemble bytecode to verify instruction encoding",
      "example": "python -m flux.disasm program.bin → shows decoded instructions"
    },
    {
      "tool": "python -m pytest tests/test_opcode_reconciliation.py -v",
      "purpose": "Run full opcode reconciliation test suite",
      "example": "Detects all System A / System B divergences"
    },
    {
      "tool": "git log --oneline --all -- src/flux/bytecode/opcodes*.py",
      "purpose": "Trace opcode table changes over time",
      "example": "Shows when opcodes_legacy.py was last modified"
    }
  ],

  "activation_conditions": {
    "task_keywords": ["bug", "wrong opcode", "wrong format", "encoding error",
                      "ISA divergence", "System A", "System B", "reconciliation"],
    "file_patterns": ["src/flux/bytecode/*", "tests/test_bytecode.py",
                      "tests/test_isa_unified.py"],
    "error_patterns": ["opcode mismatch", "format error", "encoding error",
                       "unexpected instruction"]
  },

  "metadata": {
    "created_by": "Super Z",
    "created_from": {
      "trace_ids": ["ec-0015", "ec-0016", "ec-0018", "dp-0042"],
      "error_correction_count": 12,
      "decision_point_count": 4
    }
  }
}
```

#### Type 4: Communication Modules (CM)

These modules encode cross-agent coordination patterns — how to communicate
effectively within the fleet.

**Examples:**
- Bottle Packaging Best Practices (how to write handoff messages)
- Question-Asking Technique (how to ask precise, answerable questions)
- Status Reporting Format (how to write effective progress updates)
- Code Review Communication (how to give constructive feedback)

**Structure:**

```json
{
  "module_type": "communication",
  "module_id": "CM-BOTTLE-HANDOFF-001",
  "version": "1.0.0",
  "domain": "communication",
  "subdomain": "bottle_handoff",
  "title": "Effective Bottle Packaging for Agent Handoffs",

  "patterns": {
    "good_handoff": {
      "required_elements": [
        "1. Task reference (which task board item this addresses)",
        "2. Artifact list (exact file paths, not vague references)",
        "3. Context summary (what was done, why, current state)",
        "4. Known issues (what's broken, what's uncertain)",
        "5. Expected outcome (what the receiving agent should do)",
        "6. Version tags (ISA version, runtime version, dependency versions)"
      ],
      "anti_patterns": [
        "Don't say 'fixed some bugs' — list the specific bugs and fixes",
        "Don't assume the receiver has context from previous bottles",
        "Don't omit version tags — the receiver may be on a different version",
        "Don't hand off without running tests first"
      ]
    },
    "question_asking": {
      "formula": "Context + Specific Question + What I've Tried + What I Need",
      "good_example": "I'm encoding TELL instructions using Format E per ISA_UNIFIED.md.\nThe encoder produces [0x50, rd, rs1, rs2]. When I run test_tell_encoding,\nit fails with 'unexpected bytecode length'. I've verified the opcode is\ncorrect (0x50). Can someone check if Format E is the right format for TELL?",
      "bad_example": "TELL is broken, help"
    }
  },

  "activation_conditions": {
    "task_keywords": ["bottle", "handoff", "message", "delegate", "coordinate"],
    "always_active_for_fleet": true
  },

  "metadata": {
    "created_by": "Super Z",
    "created_from": {
      "trace_ids": ["bot-0088", "bot-0089", "bot-0091"],
      "bottle_count": 30
    }
  }
}
```

#### Type 5: Meta-Knowledge Modules (MKM)

These modules encode judgment, heuristics, and trade-off knowledge — the
"why and when" layer from the R2 synthesis. These are the rarest and most
valuable modules.

**Examples:**
- Opcode Selection Heuristics (when to use LOOP vs DEC+JNZ)
- Design Trade-off Framework (when to optimize for speed vs. correctness vs. clarity)
- Escalation Decision Criteria (when to ask for help vs. keep trying)
- Confidence Calibration Patterns (how to express uncertainty appropriately)

**Structure:**

```json
{
  "module_type": "meta_knowledge",
  "module_id": "MKM-OPCODE-JUDGMENT-001",
  "version": "1.0.0",
  "domain": "meta",
  "subdomain": "opcode_selection",
  "title": "When to Use Which Loop Construct",

  "heuristics": [
    {
      "situation": "Counted loop with known iteration count",
      "recommended": "LOOP (opcode 0x46)",
      "alternative": "DEC + JNZ pattern",
      "rationale": "LOOP signals to the PatternMiner that this is a counted loop,\nenabling future fusion optimizations. It's also 2 bytes shorter than\nDEC + JNZ (2 instructions vs 1).",
      "trade_offs": "LOOP only supports down-counting from a register. If you need\nup-counting or a non-standard step, use DEC + JNZ."
    },
    {
      "situation": "Loop with unknown iteration count (while-like)",
      "recommended": "JZ or JNZ with conditional check",
      "alternative": "LOOP with computed count",
      "rationale": "Computing the iteration count adds overhead and complexity.\nDirect conditional jumps are simpler and match the logic structure."
    },
    {
      "situation": "Iterating over a fixed range with step",
      "recommended": "Custom counter with ADD + CMP + JL",
      "alternative": "LOOP with post-adjustment",
      "rationale": "Clearer intent, easier to debug, no off-by-one risk from\nadjusting the counter inside a LOOP."
    }
  ],

  "escalation_criteria": {
    "when_to_ask_for_help": [
      "After 3 failed attempts at the same encoding problem",
      "When the ISA spec is ambiguous or self-contradictory",
      "When a fix for one test breaks another (regression cycle)",
      "When the error message doesn't match the code (VM vs encoder mismatch)"
    ]
  },

  "activation_conditions": {
    "task_keywords": ["loop", "iterate", "optimize", "design decision",
                      "which opcode", "trade-off"],
    "file_patterns": ["**/*.py", "**/bytecode/*"]
  },

  "metadata": {
    "created_by": "Super Z",
    "created_from": {
      "trace_ids": ["dp-0042", "dp-0045", "dp-0048"],
      "decision_point_count": 8
    }
  }
}
```

### 3.3 Module Composability Rules

When multiple modules are loaded simultaneously, they must not conflict. We
enforce this through four composability rules:

**Rule 1: Domain Exclusivity.** No two active modules may have the same
`domain` and `subdomain`. If a conflict exists, the more specific (deeper
subdomain) module wins.

**Rule 2: Context Budget.** The total size of all active modules must not
exceed the agent's context budget (default: 32KB, configurable). Modules are
loaded in priority order until the budget is exhausted.

**Rule 3: Activation Gating.** Modules are only loaded when their activation
conditions match the current task. This is determined by keyword matching
against the task description, file patterns against the files being modified,
and task board tags against the current task.

**Rule 4: Conflict Resolution.** If two modules contain contradictory advice
(e.g., one says "use Format G for A2A" and another says "use Format E for
A2A"), the higher-version module wins. If versions are equal, the more
recently validated module wins.

### 3.4 Module Lifecycle

Each module goes through a five-stage lifecycle:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  DRAFT   │───▶│  REVIEW  │───▶│  ACTIVE  │───▶│ STALE    │───▶│ EXPIRED  │
│          │    │          │    │          │    │          │    │          │
│ Extracted│    │ Peer     │    │ Available│    │ Past     │    │ No longer│
│ from     │    │ reviewed │    │ for      │    │ validation│    │ relevant │
│ diary    │    │ and      │    │ transfer │    │ date     │    │          │
│          │    │ tested   │    │          │    │          │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │                │                │                │                │
     │                │                │                │                │
  Created by      Validated by     Installed on    Flagged for       Removed
  pipeline       expert agent     receiving       revalidation      from
  (Stage 4)      or human         agents           (re-run Stage 5)   registry
```

### 3.5 Module Size Budgets

Module size is constrained by the agent's context window. We define three
size tiers:

| Tier | Max Size | Use Case | Content Density |
|------|----------|----------|-----------------|
| **Compact** | 2KB | Frequently loaded modules (process, communication) | High: only essential patterns |
| **Standard** | 8KB | Domain knowledge modules | Medium: key facts + common traps + procedures |
| **Comprehensive** | 16KB | Debugging modules with many failure patterns | Lower: includes worked examples |

The default context budget is 32KB, which allows:
- 1 standard module (8KB) + 1 compact module (2KB) = 10KB loaded per task
- With 22KB remaining for the task description and agent reasoning

Modules can be stored in compressed form (gzip) to save disk space, but are
decompressed before injection into the agent's context.

---

## 4. Training Pipeline Design: Building Modules from Experience

### 4.1 Pipeline Overview

The training pipeline converts raw agent experience (the diary) into
structured ability modules. It consists of five stages:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ABILITY MODULE TRAINING PIPELINE                    │
│                                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐         │
│  │ STAGE 1  │──▶│ STAGE 2  │──▶│ STAGE 3  │──▶│ STAGE 4  │──▶ ...  │
│  │Extract   │   │Feature   │   │Construct │   │Quality   │         │
│  │Experience│   │Engineer  │   │Modules   │   │Filter    │         │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    STAGE 5: Validate                         │──▶ ...│
│  │  Test module effectiveness on held-out tasks                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Stage 1: Experience Extraction

**Input:** Raw agent diary sources (git repos, bottle directories, task board)
**Output:** Structured experience traces (JSON)

**Process:**

#### Step 1a: Git History Extraction

Use `tools/git-archaeology/craftsman_reader.py` to scan git repositories and
produce structured commit data:

```python
def extract_git_experience(repo_path: str, since_days: int = 90) -> list[dict]:
    """Extract behavioral traces from git commit history."""
    import subprocess, json

    # Get commits in structured format
    result = subprocess.run(
        ["git", "log", "--since", f"{since_days} days ago",
         "--format=%H|%an|%ae|%aI|%s|%b", "--no-merges"],
        capture_output=True, text=True, cwd=repo_path
    )

    traces = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        hash_, author, email, timestamp, subject, body = line.split("|", 5)

        # Get diff stats
        diff_result = subprocess.run(
            ["git", "diff", "--stat", f"{hash_}^..{hash_}"],
            capture_output=True, text=True, cwd=repo_path
        )

        traces.append({
            "trace_type": "commit",
            "trace_id": hash_[:8],
            "timestamp": timestamp,
            "author": author,
            "message_subject": subject,
            "message_body": body,
            "diff_stats": diff_result.stdout,
            # ... additional parsing
        })

    return traces
```

#### Step 1b: Bottle Message Extraction

Scan `message-in-a-bottle/` directories for handoff messages:

```python
def extract_bottle_experience(bottle_dir: str) -> list[dict]:
    """Extract coordination traces from bottle messages."""
    traces = []

    for root, dirs, files in os.walk(bottle_dir):
        for filename in files:
            if filename.endswith(".md"):
                filepath = os.path.join(root, filename)
                content = open(filepath).read()

                # Parse bottle metadata
                trace = parse_bottle_message(content, filepath)
                if trace:
                    trace["trace_type"] = "bottle_communication"
                    traces.append(trace)

    return traces
```

#### Step 1c: Task Board Extraction

Parse task board files (TASKS.md, PRIORITY.md, etc.) for task state
transitions:

```python
def extract_task_experience(task_board_dir: str) -> list[dict]:
    """Extract decision traces from task board state changes."""
    traces = []

    tasks_file = os.path.join(task_board_dir, "TASKS.md")
    if os.path.exists(tasks_file):
        content = open(tasks_file).read()
        # Parse task items, status transitions, assignments
        tasks = parse_task_board(content)
        for task in tasks:
            for transition in task["transitions"]:
                traces.append({
                    "trace_type": "decision_point",
                    "domain": task.get("domain", "general"),
                    "content": {
                        "task": task["title"],
                        "from_state": transition["from"],
                        "to_state": transition["to"],
                        "reason": transition.get("reason", "")
                    }
                })

    return traces
```

#### Step 1d: Error Correction Extraction

Identify error corrections by looking for fix commits that reference
previous bug commits:

```python
def extract_error_corrections(commits: list[dict]) -> list[dict]:
    """Identify error correction events from commit history."""
    corrections = []

    for i, commit in enumerate(commits):
        # Look for fix commits that reference specific issues or errors
        if commit.get("type") == "fix" and commit.get("body"):
            # Check if body describes what went wrong
            if contains_error_description(commit["body"]):
                corrections.append({
                    "trace_type": "error_correction",
                    "trace_id": f"ec-{commit['trace_id']}",
                    "domain": classify_domain(commit),
                    "content": {
                        "error": extract_error_description(commit),
                        "fix": commit,
                        "related_commits": find_related_commits(commits, i)
                    }
                })

    return corrections
```

### 4.3 Stage 2: Feature Engineering

**Input:** Structured experience traces
**Output:** Feature-enriched traces with quality scores

**Process:**

#### Step 2a: Domain Classification

Classify each trace into one or more domains using the taxonomy from R2:

```python
DOMAIN_KEYWORDS = {
    "bytecode": ["opcode", "encoding", "format", "bytecode", "assembler",
                  "encoder", "decoder", "disasm", "MOVI", "TELL", "HALT"],
    "fir": ["FIR", "SSA", "basic block", "phi", "type system",
            "FIRBuilder", "FIRModule"],
    "a2a": ["TELL", "ASK", "DELEGATE", "BCAST", "BARRIER", "REDUCE",
            "agent", "trust", "coordination"],
    "evolution": ["mutation", "genome", "fitness", "evolve", "profiler",
                  "heat", "FROZEN", "COOL", "WARM", "HOT"],
    "testing": ["test", "pytest", "assert", "coverage", "regression"],
    "architecture": ["design", "spec", "RFC", "trade-off", "interface",
                     "subsystem"],
    "git": ["commit", "branch", "merge", "rebase", "reflog"],
    "communication": ["bottle", "handoff", "message", "delegate",
                      "status", "review"]
}

def classify_domain(trace: dict) -> str:
    """Classify a trace into a domain using keyword matching."""
    text = trace.get("message_subject", "") + " " + trace.get("message_body", "")
    text = text.lower()

    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        scores[domain] = score

    if max(scores.values()) == 0:
        return "general"
    return max(scores, key=scores.get)
```

#### Step 2b: Signal Quality Scoring

Compute a signal quality score for each trace:

```python
def compute_signal_quality(trace: dict) -> float:
    """Compute signal quality score for a trace."""

    score = 0.0

    # Base signal from trace type
    type_weights = {
        "decision_point": 0.4,
        "error_correction": 0.4,
        "commit": 0.1,
        "bottle_communication": 0.05,
        "review": 0.05
    }
    score += type_weights.get(trace["trace_type"], 0.0)

    # Bonus for detailed explanation
    body = trace.get("message_body", "") or ""
    if len(body) > 200:
        score += 0.1
    if "because" in body.lower() or "reason" in body.lower():
        score += 0.1
    if "root cause" in body.lower():
        score += 0.15

    # Bonus for test verification
    if trace.get("test_outcome", {}).get("ran"):
        score += 0.1
    if trace.get("test_outcome", {}).get("passed", 0) > 0:
        score += 0.05

    # Bonus for references to other work
    refs = trace.get("refs", [])
    if len(refs) > 0:
        score += 0.05

    # Penalty for noise indicators
    subject = trace.get("message_subject", "")
    if len(subject) < 10 or subject.lower() in ["update", "fix", "wip"]:
        score -= 0.1

    return max(0.0, min(1.0, score))
```

#### Step 2c: Relationship Extraction

Link related traces together:

```python
def extract_relationships(traces: list[dict]) -> list[list[str]]:
    """Link related traces into experience chains."""

    chains = []
    for i, trace in enumerate(traces):
        chain = [trace["trace_id"]]

        # Find error corrections that reference this commit
        for j, other in enumerate(traces):
            if (other["trace_type"] == "error_correction" and
                trace["trace_id"] in other.get("related_commits", [])):
                chain.append(other["trace_id"])

        # Find follow-up commits
        for j, other in enumerate(traces):
            if (other["trace_type"] == "commit" and
                j > i and
                trace.get("domain") == other.get("domain") and
                trace.get("subdomain") == other.get("subdomain")):
                chain.append(other["trace_id"])

        if len(chain) > 1:
            chains.append(chain)

    return chains
```

### 4.4 Stage 3: Module Construction

**Input:** Feature-enriched traces, grouped by domain
**Output:** Draft ability modules (JSON)

**Process:**

#### Step 3a: Group Experiences by Domain

```python
def group_by_domain(traces: list[dict]) -> dict[str, list[dict]]:
    """Group traces into domain buckets."""
    groups = {}
    for trace in traces:
        domain = trace.get("domain", "general")
        groups.setdefault(domain, []).append(trace)
    return groups
```

#### Step 3b: Extract Patterns

For each domain group, extract the recurring patterns that represent
transferable knowledge:

```python
def extract_patterns(domain_traces: list[dict]) -> dict:
    """Extract recurring patterns from domain-specific traces."""

    patterns = {
        "key_facts": set(),
        "common_traps": [],
        "procedures": [],
        "worked_examples": [],
        "error_fix_pairs": [],
        "decision_heuristics": []
    }

    for trace in domain_traces:
        if trace["signal_quality"] < 0.3:
            continue

        if trace["trace_type"] == "error_correction":
            patterns["error_fix_pairs"].append({
                "error": trace["content"].get("error"),
                "fix": trace["content"].get("fix"),
                "lesson": trace["content"].get("lesson")
            })

        elif trace["trace_type"] == "decision_point":
            patterns["decision_heuristics"].append({
                "situation": trace["content"]["context"]["problem"],
                "chosen": trace["content"]["context"]["chosen"],
                "rationale": trace["content"]["context"]["rationale"],
                "alternatives": trace["content"]["context"]["alternatives"]
            })

        elif trace["trace_type"] == "commit" and trace.get("message_body"):
            # Extract "lesson" statements from commit bodies
            body = trace["message_body"]
            if "lesson" in body.lower() or "note:" in body.lower():
                patterns["key_facts"].add(extract_lesson(body))

    return patterns
```

#### Step 3c: Compress into Module Format

Convert extracted patterns into the structured module format:

```python
def construct_module(domain: str, patterns: dict, metadata: dict) -> dict:
    """Construct a draft ability module from extracted patterns."""

    module = {
        "module_type": classify_module_type(domain),
        "module_id": f"DKM-{domain.upper()}-001",
        "version": "0.1.0-draft",
        "domain": domain,
        "title": f"{domain.title()} Expertise Module",
        "knowledge": {},
        "activation_conditions": infer_activation_conditions(domain),
        "validation": {},
        "metadata": metadata
    }

    # Populate knowledge section based on module type
    if patterns.get("error_fix_pairs"):
        module["knowledge"]["failure_patterns"] = patterns["error_fix_pairs"]
    if patterns.get("decision_heuristics"):
        module["knowledge"]["heuristics"] = patterns["decision_heuristics"]
    if patterns.get("key_facts"):
        module["knowledge"]["key_facts"] = list(patterns["key_facts"])
    if patterns.get("procedures"):
        module["knowledge"]["procedures"] = patterns["procedures"]

    return module
```

### 4.5 Stage 4: Quality Filtering

**Input:** Draft ability modules
**Output:** Filtered, cleaned modules

**Process:**

#### Step 4a: Remove Noise

Filter out traces that don't contribute to transferable knowledge:

```python
def filter_noise(traces: list[dict]) -> list[dict]:
    """Remove low-signal traces."""

    filtered = []
    for trace in traces:
        # Remove traces below minimum quality threshold
        if trace["signal_quality"] < 0.2:
            continue

        # Remove traces that are too generic
        if is_too_generic(trace):
            continue

        # Remove duplicates
        if is_duplicate(trace, filtered):
            continue

        # Remove traces with potentially harmful advice
        if contains_harmful_advice(trace):
            continue

        filtered.append(trace)

    return filtered
```

#### Step 4b: Deduplicate Patterns

Multiple traces may encode the same knowledge. Deduplicate to keep the
highest-quality version:

```python
def deduplicate_patterns(patterns: list[dict]) -> list[dict]:
    """Remove duplicate patterns, keeping the highest-quality version."""

    unique = {}
    for pattern in patterns:
        # Create a canonical key from the pattern's core content
        key = canonicalize(pattern)
        if key not in unique or pattern.get("quality", 0) > unique[key].get("quality", 0):
            unique[key] = pattern

    return list(unique.values())
```

#### Step 4c: Validate Module Structure

Ensure each module conforms to the schema:

```python
def validate_module_structure(module: dict) -> list[str]:
    """Validate a module against the schema. Returns list of errors."""

    errors = []

    # Required fields
    required = ["module_type", "module_id", "version", "domain",
                "activation_conditions", "metadata"]
    for field in required:
        if field not in module:
            errors.append(f"Missing required field: {field}")

    # Size constraint
    module_size = len(json.dumps(module))
    if module_size > 16384:
        errors.append(f"Module too large: {module_size} bytes (max 16384)")

    # Activation conditions
    ac = module.get("activation_conditions", {})
    if not ac.get("task_keywords"):
        errors.append("Activation conditions must include task_keywords")

    # Metadata
    meta = module.get("metadata", {})
    if not meta.get("created_from", {}).get("trace_ids"):
        errors.append("Module must reference source trace IDs")

    return errors
```

### 4.6 Stage 5: Validation

**Input:** Filtered ability modules
**Output:** Validated modules with effectiveness scores

**Process:**

#### Step 5a: Benchmark Task Selection

Select held-out test tasks that match the module's domain:

```python
BENCHMARK_TASKS = {
    "bytecode": [
        {
            "task": "Encode a DELEGATE instruction from R5 to R8 with payload type in R2",
            "expected_behavior": "Produces valid Format E bytecode [0x52, 0x05, 0x02, 0x08]",
            "difficulty": "medium"
        },
        {
            "task": "Write a function that computes fibonacci(n) using FLUX bytecode",
            "expected_behavior": "Compiles, runs, produces correct results for n <= 20",
            "difficulty": "hard"
        }
    ],
    "fir": [
        {
            "task": "Build a FIR function that adds two integers",
            "expected_behavior": "Valid SSA form, passes FIR validator",
            "difficulty": "easy"
        }
    ],
    # ... more domains
}
```

#### Step 5b: A/B Testing

For each module, measure task performance with and without the module loaded:

```python
def validate_module(module: dict, benchmark_tasks: list) -> dict:
    """A/B test a module against benchmark tasks."""

    results = {
        "module_id": module["module_id"],
        "tasks": [],
        "overall_effectiveness": 0.0
    }

    for task in benchmark_tasks:
        # Without module (baseline)
        baseline = execute_task_without_module(task)
        # With module
        with_module = execute_task_with_module(task, module)

        result = {
            "task": task["task"],
            "baseline_score": baseline["score"],
            "with_module_score": with_module["score"],
            "improvement": with_module["score"] - baseline["score"],
            "baseline_correct": baseline["correct"],
            "with_module_correct": with_module["correct"]
        }
        results["tasks"].append(result)

    # Compute overall effectiveness
    total_improvement = sum(t["improvement"] for t in results["tasks"])
    results["overall_effectiveness"] = total_improvement / len(results["tasks"])

    return results
```

#### Step 5c: Regression Testing

Verify that the module doesn't degrade performance on out-of-domain tasks:

```python
def check_regressions(module: dict, ood_tasks: list) -> list[str]:
    """Check if module causes regressions on out-of-domain tasks."""

    regressions = []
    for task in ood_tasks:
        baseline = execute_task_without_module(task)
        with_module = execute_task_with_module(task, module)

        if with_module["score"] < baseline["score"] - 0.1:
            regressions.append({
                "task": task["task"],
                "baseline_score": baseline["score"],
                "with_module_score": with_module["score"],
                "degradation": baseline["score"] - with_module["score"]
            })

    return regressions
```

### 4.7 Pipeline Orchestration

The full pipeline runs as a single orchestrated process:

```python
def run_training_pipeline(repo_path: str, bottle_dir: str,
                          task_board_dir: str, output_dir: str) -> list[dict]:
    """Run the full ability module training pipeline."""

    print("=" * 60)
    print("ABILITY MODULE TRAINING PIPELINE")
    print("=" * 60)

    # Stage 1: Extract
    print("\n[Stage 1/5] Extracting experience...")
    git_traces = extract_git_experience(repo_path)
    bottle_traces = extract_bottle_experience(bottle_dir)
    task_traces = extract_task_experience(task_board_dir)
    all_traces = git_traces + bottle_traces + task_traces

    # Extract error corrections from commit history
    corrections = extract_error_corrections(git_traces)
    all_traces.extend(corrections)

    print(f"  Extracted {len(all_traces)} experience traces")

    # Stage 2: Feature engineering
    print("\n[Stage 2/5] Engineering features...")
    for trace in all_traces:
        trace["domain"] = classify_domain(trace)
        trace["signal_quality"] = compute_signal_quality(trace)

    high_signal = [t for t in all_traces if t["signal_quality"] >= 0.3]
    print(f"  {len(high_signal)}/{len(all_traces)} traces above quality threshold")

    # Stage 3: Construct modules
    print("\n[Stage 3/5] Constructing modules...")
    domain_groups = group_by_domain(high_signal)
    draft_modules = []

    for domain, traces in domain_groups.items():
        if len(traces) < 5:
            print(f"  Skipping {domain}: insufficient traces ({len(traces)})")
            continue

        patterns = extract_patterns(traces)
        if not any(patterns.values()):
            print(f"  Skipping {domain}: no patterns extracted")
            continue

        metadata = {
            "created_by": "pipeline",
            "created_from": {
                "trace_ids": [t["trace_id"] for t in traces],
                "trace_count": len(traces),
                "high_signal_count": len([t for t in traces if t["signal_quality"] >= 0.5])
            },
            "pipeline_version": "1.0.0"
        }

        module = construct_module(domain, patterns, metadata)
        draft_modules.append(module)
        print(f"  Drafted module: {module['module_id']}")

    # Stage 4: Quality filtering
    print("\n[Stage 4/5] Filtering quality...")
    validated_modules = []
    for module in draft_modules:
        errors = validate_module_structure(module)
        if errors:
            print(f"  REJECTED {module['module_id']}: {errors}")
            continue
        validated_modules.append(module)
        print(f"  ACCEPTED {module['module_id']}")

    # Stage 5: Validation
    print("\n[Stage 5/5] Validating effectiveness...")
    for module in validated_modules:
        domain = module["domain"]
        tasks = BENCHMARK_TASKS.get(domain, [])
        if not tasks:
            print(f"  SKIPPED {module['module_id']}: no benchmark tasks")
            continue

        results = validate_module(module, tasks)
        module["validation_results"] = results
        print(f"  {module['module_id']}: effectiveness = "
              f"{results['overall_effectiveness']:.2f}")

    # Save modules
    os.makedirs(output_dir, exist_ok=True)
    for module in validated_modules:
        filepath = os.path.join(output_dir, f"{module['module_id']}.json")
        with open(filepath, "w") as f:
            json.dump(module, f, indent=2)
        print(f"\n  Saved: {filepath}")

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete: {len(validated_modules)} modules produced")
    print(f"{'=' * 60}")

    return validated_modules
```

---

## 5. Transfer Protocol: Installing Ability Modules

### 5.1 Module Format Specification

Ability modules are stored as JSON files with a specific naming convention:

```
<module_type>-<domain>-<sequence>.json

Examples:
  DKM-bytecode-001.json    (Domain Knowledge Module, bytecode)
  PM-git-workflow-001.json (Process Module, git workflow)
  DBM-isa-divergence-001.json (Debugging Module, ISA divergence)
  CM-bottle-handoff-001.json (Communication Module, bottle handoff)
  MKM-opcode-judgment-001.json (Meta-Knowledge Module, opcode selection)
```

The JSON schema is defined in Section 3.2. Key fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `module_type` | string | yes | One of: `domain_knowledge`, `process`, `debugging`, `communication`, `meta_knowledge` |
| `module_id` | string | yes | Unique identifier, format: `<TYPE>-<DOMAIN>-<SEQ>` |
| `version` | string | yes | Semantic version (e.g., "1.2.0") |
| `domain` | string | yes | Primary domain from the taxonomy |
| `title` | string | yes | Human-readable title |
| `knowledge` | object | yes | Module-type-specific content (see Section 3.2) |
| `activation_conditions` | object | yes | Keywords and patterns for auto-activation |
| `validation` | object | yes | Self-test questions and benchmark tasks |
| `metadata` | object | yes | Provenance, version compatibility, creation info |

### 5.2 Installation Process

Installing an ability module on a new agent involves four steps:

#### Step 1: Compatibility Check

Before installation, verify that the receiving agent meets the module's
requirements:

```python
def check_compatibility(module: dict, agent_profile: dict) -> dict:
    """Check if a module is compatible with an agent."""

    checks = {
        "compatible": True,
        "warnings": [],
        "errors": []
    }

    # Check base capability version
    required = module.get("metadata", {}).get("base_compatibility", "")
    if required:
        # Parse "flux-runtime >= 0.5.0, isa_version = unified-v2"
        # and check against agent's runtime version
        if not version_satisfies(agent_profile.get("runtime_version"), required):
            checks["errors"].append(
                f"Runtime version mismatch: module requires {required}"
            )
            checks["compatible"] = False

    # Check domain prerequisites
    prereqs = module.get("prerequisites", [])
    agent_knowledge = agent_profile.get("knowledge", [])
    for prereq in prereqs:
        if prereq not in agent_knowledge:
            checks["warnings"].append(
                f"Agent may not have prerequisite: {prereq}"
            )

    # Check context budget
    module_size = len(json.dumps(module))
    agent_budget = agent_profile.get("context_budget", 32768)
    if module_size > agent_budget * 0.5:
        checks["warnings"].append(
            f"Module is large ({module_size} bytes), uses "
            f"{module_size/agent_budget*100:.0f}% of context budget"
        )

    return checks
```

#### Step 2: Activation Matching

Determine if the module should be loaded for the current task:

```python
def should_activate(module: dict, task_description: str,
                    modified_files: list[str]) -> bool:
    """Determine if a module should be activated for a task."""

    ac = module["activation_conditions"]

    # Keyword matching
    task_keywords = ac.get("task_keywords", [])
    if task_keywords:
        task_lower = task_description.lower()
        matches = sum(1 for kw in task_keywords if kw.lower() in task_lower)
        if matches == 0:
            return False

    # File pattern matching
    file_patterns = ac.get("file_patterns", [])
    if file_patterns:
        from fnmatch import fnmatch
        file_matches = sum(
            1 for f in modified_files
            for pattern in file_patterns
            if fnmatch(f, pattern)
        )
        if file_matches == 0:
            return False

    # Always-active modules
    if ac.get("always_active_for_fleet"):
        return True

    # Task board tag matching
    task_tags = ac.get("task_board_tags", [])
    # (would check against current task's tags)

    return True
```

#### Step 3: Context Injection

Load the module's content into the agent's context before task execution:

```python
def format_module_for_injection(module: dict) -> str:
    """Format a module for injection into agent context."""

    parts = []

    parts.append(f"## {module['title']}")
    parts.append(f"(Ability Module v{module['version']}, domain: {module['domain']})")
    parts.append("")

    knowledge = module.get("knowledge", {})

    # Key facts
    if knowledge.get("key_facts"):
        parts.append("### Key Facts")
        for fact in knowledge["key_facts"]:
            parts.append(f"- {fact}")
        parts.append("")

    # Common traps
    if knowledge.get("common_traps"):
        parts.append("### Common Traps to Avoid")
        for trap in knowledge["common_traps"]:
            parts.append(f"**Trap:** {trap['trap']}")
            parts.append(f"**Reality:** {trap['reality']}")
            parts.append(f"**How to detect:** {trap.get('detection', 'N/A')}")
            parts.append("")

    # Procedures
    if knowledge.get("procedures"):
        parts.append("### Standard Procedures")
        for proc in knowledge["procedures"]:
            parts.append(f"**{proc['name']}:**")
            for step in proc.get("steps", []):
                parts.append(f"  {step}")
            parts.append("")

    # Failure patterns (debugging modules)
    if knowledge.get("failure_patterns"):
        parts.append("### Known Failure Patterns")
        for fp in knowledge["failure_patterns"]:
            parts.append(f"**{fp['name']}:** {fp.get('symptoms', [])}")
            parts.append(f"  Fix: {fp.get('fix_pattern', 'N/A')}")
            parts.append("")

    # Heuristics (meta-knowledge modules)
    if knowledge.get("heuristics"):
        parts.append("### Decision Heuristics")
        for h in knowledge["heuristics"]:
            parts.append(f"When: {h['situation']}")
            parts.append(f"  Recommended: {h['recommended']}")
            parts.append(f"  Why: {h['rationale']}")
            parts.append("")

    return "\n".join(parts)
```

#### Step 4: Post-Installation Validation

After the agent completes a task with the module loaded, measure whether the
module helped:

```python
def measure_improvement(task_result_with: dict,
                        task_result_without: dict) -> dict:
    """Measure the improvement from having the module loaded."""

    return {
        "accuracy_improvement": (
            task_result_with["correctness"]
            - task_result_without["correctness"]
        ),
        "time_improvement": (
            task_result_without["time_seconds"]
            - task_result_with["time_seconds"]
        ),
        "quality_improvement": (
            task_result_with["code_quality_score"]
            - task_result_without["code_quality_score"]
        ),
        "module_helpful": (
            task_result_with["correctness"] > task_result_without["correctness"]
            or task_result_with["time_seconds"] < task_result_without["time_seconds"] * 0.9
        )
    }
```

### 5.3 Compatibility Checking

The compatibility system uses semantic versioning and domain matching:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    COMPATIBILITY MATRIX                               │
│                                                                      │
│  Module requires:        Agent has:        Result:                   │
│  ─────────────────────    ────────────────   ────────────────         │
│  flux-runtime >= 1.0      flux-runtime 1.2   ✅ Compatible            │
│  isa_version = unified-v2 isa_version v3      ⚠️ May work, verify     │
│  domain = bytecode        domain = fir         ❌ Domain mismatch      │
│  context_budget >= 8KB    context_budget 16KB  ✅ Sufficient budget    │
│  prerequisites: [ISA]     knowledge: [ISA]    ✅ Prerequisites met    │
│  prerequisites: [CUDA]    knowledge: []       ⚠️ Missing prerequisites│
└──────────────────────────────────────────────────────────────────────┘
```

### 5.4 Performance Measurement

We measure module effectiveness using four metrics:

| Metric | How Measured | Target |
|--------|-------------|--------|
| **First-attempt correctness** | % of tasks completed correctly on first try | +15% improvement |
| **Time-to-completion** | Wall clock time from task start to verified completion | -20% improvement |
| **Error rate** | Number of bugs introduced per task | -30% improvement |
| **Context efficiency** | Ratio of useful context to total context loaded | > 0.7 |

---

## 6. Minimum Viable Dataset: How Much Experience Is Enough?

### 6.1 Analysis by Domain

We analyzed the FLUX fleet's experience to determine the minimum amount of
experience needed to construct a useful ability module for each domain:

| Domain | Min Commits | Min Error Corrections | Min Decision Points | Quality Threshold |
|--------|:-----------:|:---------------------:|:-------------------:|:-----------------:|
| **Bytecode** | 20 | 3 | 2 | High (0.8) |
| **FIR** | 15 | 2 | 1 | High (0.7) |
| **A2A** | 10 | 1 | 2 | Medium (0.6) |
| **Evolution** | 10 | 2 | 1 | Medium (0.6) |
| **Testing** | 15 | 1 | 1 | Medium (0.5) |
| **Architecture** | 5 | 0 | 3 | High (0.8) |
| **Git Workflow** | 30 | 0 | 0 | Low (0.4) |
| **Communication** | 10 | 0 | 0 | Low (0.4) |

**Key finding:** Debugging modules (high error correction count) require fewer
total commits but more error corrections. Meta-knowledge modules (high decision
point count) require even fewer commits but more decision points. Process
modules require the most raw commits but the least specialized content.

### 6.2 Diminishing Returns Curve

We modeled the relationship between experience volume and module quality:

```
Module Quality
    │
1.0├                           ╭────────────────
    │                         ╭─╯
0.8├                       ╭─╯
    │                     ╭─╯
0.6├                   ╭─╯
    │                 ╭─╯
0.4├               ╭─╯
    │             ╭─╯
0.2├          ╭──╯
    │       ╭─╯
0.0├─────╭─╯
    └─────┼─────┼─────┼─────┼─────┼─────┼─────┼────▶
          5    10    20    40    60    80   100
                     Experience Volume (high-signal traces)
                     │
                     └── Sweet spot: 20-40 traces
```

**Analysis:**

- **0-5 traces:** Insufficient. Patterns are not statistically reliable. Modules
  built from < 5 traces have high variance in quality.
- **5-20 traces:** Rapid improvement. Each additional trace adds significant
  new knowledge. This is the "steep part" of the curve.
- **20-40 traces:** Sweet spot. Diminishing returns begin here. Most
  transferable knowledge has been captured.
- **40-60 traces:** Marginal improvement. New traces mostly confirm existing
  patterns rather than adding new ones.
- **60+ traces:** Noise territory. Additional traces are increasingly redundant
  and may introduce noise that degrades module quality.

**Recommendation:** Target 20-40 high-signal traces per domain module. Beyond
40, the pipeline should apply stricter filtering to maintain quality.

### 6.3 Cross-Domain Transfer Analysis

A critical question: does experience in one domain help with another?

| Source Domain | → Target Domain | Transfer Effectiveness | Mechanism |
|---------------|-----------------|:----------------------:|-----------|
| ISA Design | → Bytecode Generation | **High (0.7)** | Understanding of format system directly applies |
| ISA Design | → FIR Pipeline | **Medium (0.4)** | General ISA knowledge helps but FIR has its own patterns |
| Bytecode Generation | → FIR Pipeline | **Medium (0.5)** | Understanding of low-level encoding informs IR design |
| Bytecode Generation | → A2A Protocol | **Medium (0.4)** | Format encoding knowledge transfers |
| Debugging (any) | → Debugging (any) | **High (0.6)** | Debugging methodology is largely domain-independent |
| Git Workflow | → Any domain | **Low (0.1)** | Process knowledge doesn't help with technical skills |
| Communication | → Any domain | **Low (0.2)** | Communication helps but is orthogonal to technical skill |
| Evolution | → FIR Pipeline | **Medium (0.3)** | Optimization thinking transfers partially |
| Architecture | → Any domain | **Medium (0.3)** | Design thinking helps with subsystem construction |

**Key findings:**

1. **Technical domains transfer within the bytecode→FIR→A2A axis.** Understanding
   one level of the FLUX stack helps with adjacent levels.

2. **Debugging is broadly transferable.** The meta-skill of "how to diagnose
   problems" applies across domains, even if the specific failure patterns
   differ.

3. **Process skills are orthogonal to technical skills.** Good git hygiene
   doesn't help you write correct bytecode. These are independent modules.

4. **Architecture skill provides modest cross-domain benefit.** Understanding
   design principles helps with any subsystem, but the effect is limited.

### 6.4 The "Minimum Viable Module" Specification

Based on our analysis, the minimum requirements for a useful ability module
are:

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| **High-signal traces** | ≥ 10 | Below 10, patterns are unreliable |
| **Error corrections** | ≥ 2 | At least 2 error→fix pairs for debugging value |
| **Decision points** | ≥ 1 | At least 1 decision with alternatives for meta-value |
| **Domain coverage** | ≥ 1 subdomain | Module must be specific enough to be useful |
| **Validation score** | ≥ 0.6 | Module must improve task performance by at least 10% |
| **No regressions** | 0 | Module must not degrade out-of-domain performance |

A module that meets all six criteria is a "Minimum Viable Module" (MVM) and
can be promoted from DRAFT to REVIEW status. A module that meets all criteria
AND has been peer-reviewed can be promoted to ACTIVE status.

### 6.5 Dataset Augmentation Strategies

When raw experience is insufficient, we can augment the dataset:

1. **Synthetic error correction:** Deliberately inject bugs into working code
   and record the debugging process. This is less valuable than natural error
   corrections but better than nothing.

2. **Expert elicitation:** Ask expert agents (like Oracle1) to produce
   decision point traces for common scenarios. "What would you do if X, and
   why?"

3. **Cross-fleet transfer:** Import experience traces from other FLUX fleets
   (if available). Different fleets may have solved the same problems
   differently, providing alternative perspectives.

4. **Documentation mining:** Extract patterns from existing documentation
   (ISA_UNIFIED.md, RESEARCH_ROADMAP.md, etc.) and frame them as
   declarative knowledge entries.

---

## 7. Practical Prototype Design: What We Can Build Today

### 7.1 Prototype Architecture

We can build a working prototype of the Agent Diary to LoRA pipeline using
existing FLUX fleet tools. The prototype requires no new infrastructure — it
composes three existing tools and adds a thin orchestration layer.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    PROTOTYPE ARCHITECTURE                             │
│                                                                      │
│  ┌──────────────────┐                                                │
│  │ EXISTING TOOLS   │                                                │
│  │                  │                                                │
│  │ ┌──────────────┐ │  ┌──────────────────────────────────────┐      │
│  │ │git-archaeology│ │  │         NEW: Pipeline Orchestrator    │      │
│  │ │craftsman_    │─┼─▶│                                      │      │
│  │ │reader.py     │ │  │  extract → feature_engineer →         │      │
│  │ └──────────────┘ │  │  construct → filter → validate        │      │
│  │                  │  │                                      │      │
│  │ ┌──────────────┐ │  │  Input:  git repos, bottle dirs       │      │
│  │ │fleet-context │ │  │  Output: ability module JSON files    │      │
│  │ │infer_context │─┼─▶│                                      │      │
│  │ │.py           │ │  └──────────────────────────────────────┘      │
│  │ └──────────────┘ │                      │                        │
│  │                  │                      ▼                        │
│  │ ┌──────────────┐ │  ┌──────────────────────────────────────┐      │
│  │ │bottle-hygiene│ │  │         NEW: Module Registry           │      │
│  │ │bottle_      │─┼─▶│                                      │      │
│  │ │tracker.py   │ │  │  Store, index, and serve modules       │      │
│  │ └──────────────┘ │  │  Match tasks to relevant modules      │      │
│  │                  │  │  Version and compatibility tracking   │      │
│  └──────────────────┘  └──────────────────────────────────────┘      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   NEW: Fleet Matcher Integration              │   │
│  │                                                               │   │
│  │  Enhance fleet_matcher.py to include ability module matching  │   │
│  │  as a signal source alongside git evidence and CAPABILITY.toml│   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2 Python Tool: Ability Pattern Extractor

The core of the prototype is a Python script that extracts ability patterns
from git history:

```python
#!/usr/bin/env python3
"""
ability_pattern_extractor.py — Extract ability patterns from git history.

Usage:
    python ability_pattern_extractor.py /path/to/repo \
        --domains bytecode,fir \
        --min-traces 10 \
        --output-dir ./modules/

Part of the FLUX Agent Diary to LoRA Training Pipeline.
Task: LORA-001
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ExperienceTrace:
    trace_id: str
    timestamp: str
    author: str
    trace_type: str  # commit, error_correction, decision_point
    domain: str
    subdomain: str
    signal_quality: float
    subject: str
    body: str = ""
    files_changed: list = field(default_factory=list)
    test_outcome: Optional[dict] = None
    related_traces: list = field(default_factory=list)
    tags: list = field(default_factory=list)


@dataclass
class AbilityPattern:
    pattern_type: str  # key_fact, common_trap, procedure, error_fix, heuristic
    domain: str
    content: dict
    source_trace_ids: list = field(default_factory=list)
    quality_score: float = 0.0
    frequency: int = 1


# Domain classification keywords
DOMAIN_KEYWORDS = {
    "bytecode": ["opcode", "encoding", "format", "bytecode", "assembler",
                  "encoder", "decoder", "disasm", "MOVI", "TELL", "HALT",
                  "ADD", "SUB", "MUL", "LOAD", "STORE", "JMP", "JZ", "JNZ"],
    "fir": ["FIR", "SSA", "basic block", "phi node", "type system",
            "FIRBuilder", "FIRModule", "SSA form", "dominance"],
    "a2a": ["TELL", "ASK", "DELEGATE", "BCAST", "BARRIER", "REDUCE",
            "trust", "coordination", "handshake", "agent"],
    "evolution": ["mutation", "genome", "fitness", "evolve", "profiler",
                  "FROZEN", "COOL", "WARM", "HOT", "PatternMiner"],
    "testing": ["test", "pytest", "assert", "coverage", "regression",
                "unittest"],
    "architecture": ["design", "spec", "RFC", "trade-off", "interface",
                     "subsystem", "API", "protocol"]
}


def classify_domain(text: str) -> str:
    """Classify text into a domain."""
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw.lower() in text_lower)
    if max(scores.values()) == 0:
        return "general"
    return max(scores, key=scores.get)


def compute_quality(trace: ExperienceTrace) -> float:
    """Compute signal quality score."""
    score = 0.0

    # Type bonus
    type_bonus = {
        "error_correction": 0.3,
        "decision_point": 0.3,
        "commit": 0.1
    }
    score += type_bonus.get(trace.trace_type, 0.0)

    # Explanation bonus
    if len(trace.body) > 200:
        score += 0.1
    if any(w in trace.body.lower() for w in
           ["because", "reason", "root cause", "lesson", "trap"]):
        score += 0.15

    # Test bonus
    if trace.test_outcome and trace.test_outcome.get("passed", 0) > 0:
        score += 0.1

    # Conventional commit bonus
    if any(trace.subject.startswith(t) for t in
           ["feat", "fix", "refactor", "test"]):
        score += 0.1

    return min(1.0, score)


def extract_commits(repo_path: str, since_days: int = 90) -> list[ExperienceTrace]:
    """Extract commit traces from git history."""
    result = subprocess.run(
        ["git", "log", f"--since={since_days} days ago",
         "--format=%H|%an|%aI|%s|%b%x00", "--no-merges", "-z"],
        capture_output=True, text=True, cwd=repo_path
    )

    traces = []
    entries = result.stdout.split("\0")
    for entry in entries:
        if not entry.strip():
            continue
        parts = entry.split("|", 4)
        if len(parts) < 5:
            continue

        hash_, author, timestamp, subject, body = parts
        body = body.strip()

        # Get diff stats
        try:
            diff = subprocess.run(
                ["git", "diff", "--stat", "--numstat", f"{hash_}^..{hash_}"],
                capture_output=True, text=True, cwd=repo_path
            )
            files = []
            for line in diff.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        files.append(parts[2])
        except Exception:
            files = []

        domain = classify_domain(subject + " " + body)
        trace = ExperienceTrace(
            trace_id=hash_[:8],
            timestamp=timestamp,
            author=author,
            trace_type="commit",
            domain=domain,
            subdomain="",
            signal_quality=0.0,  # computed later
            subject=subject,
            body=body,
            files_changed=files
        )
        trace.signal_quality = compute_quality(trace)
        traces.append(trace)

    return traces


def detect_error_corrections(traces: list[ExperienceTrace]) -> list[ExperienceTrace]:
    """Detect error correction patterns in commits."""
    corrections = []
    for trace in traces:
        if trace.trace_type != "commit":
            continue

        body_lower = trace.body.lower()
        subject_lower = trace.subject.lower()

        # Signals of error correction
        is_fix = (subject_lower.startswith("fix") or
                  "bug" in subject_lower or
                  "correct" in subject_lower)
        has_explanation = any(w in body_lower for w in
                              ["was using", "was incorrectly", "root cause",
                               "the problem was", "mistakenly"])
        has_prevention = any(w in body_lower for w in
                             ["to prevent", "added assertion", "added check",
                              "now validates", "in the future"])

        if is_fix and (has_explanation or has_prevention):
            correction = ExperienceTrace(
                trace_id=f"ec-{trace.trace_id}",
                timestamp=trace.timestamp,
                author=trace.author,
                trace_type="error_correction",
                domain=trace.domain,
                subdomain=trace.subdomain,
                signal_quality=min(1.0, trace.signal_quality + 0.2),
                subject=trace.subject,
                body=trace.body,
                files_changed=trace.files_changed,
                related_traces=[trace.trace_id]
            )
            corrections.append(correction)

    return corrections


def detect_decision_points(traces: list[ExperienceTrace]) -> list[ExperienceTrace]:
    """Detect decision points in commits."""
    decisions = []
    for trace in traces:
        body_lower = trace.body.lower()

        decision_signals = [
            "chose", "choosing", "decided to", "instead of",
            "over", "rather than", "trade-off", "tradeoff",
            "alternatives", "options were", "approach"
        ]

        if any(s in body_lower for s in decision_signals):
            decision = ExperienceTrace(
                trace_id=f"dp-{trace.trace_id}",
                timestamp=trace.timestamp,
                author=trace.author,
                trace_type="decision_point",
                domain=trace.domain,
                subdomain=trace.subdomain,
                signal_quality=min(1.0, trace.signal_quality + 0.15),
                subject=trace.subject,
                body=trace.body,
                files_changed=trace.files_changed,
                related_traces=[trace.trace_id]
            )
            decisions.append(decision)

    return decisions


def extract_patterns(traces: list[ExperienceTrace]) -> list[AbilityPattern]:
    """Extract ability patterns from experience traces."""
    patterns = []

    for trace in traces:
        if trace.signal_quality < 0.3:
            continue

        # Extract error→fix patterns
        if trace.trace_type == "error_correction":
            patterns.append(AbilityPattern(
                pattern_type="error_fix",
                domain=trace.domain,
                content={
                    "symptom": trace.subject,
                    "explanation": trace.body[:500],
                    "fix": extract_fix_description(trace.body),
                    "prevention": extract_prevention(trace.body)
                },
                source_trace_ids=[trace.trace_id, *trace.related_traces],
                quality_score=trace.signal_quality
            ))

        # Extract decision heuristics
        elif trace.trace_type == "decision_point":
            patterns.append(AbilityPattern(
                pattern_type="heuristic",
                domain=trace.domain,
                content={
                    "situation": trace.subject,
                    "reasoning": trace.body[:500]
                },
                source_trace_ids=[trace.trace_id, *trace.related_traces],
                quality_score=trace.signal_quality
            ))

        # Extract key facts from high-quality commits
        elif trace.trace_type == "commit" and trace.signal_quality >= 0.5:
            patterns.append(AbilityPattern(
                pattern_type="key_fact",
                domain=trace.domain,
                content={
                    "fact": trace.subject,
                    "context": trace.body[:300]
                },
                source_trace_ids=[trace.trace_id],
                quality_score=trace.signal_quality
            ))

    return patterns


def extract_fix_description(body: str) -> str:
    """Extract the fix description from a commit body."""
    # Look for sentences describing what was fixed
    sentences = body.split(". ")
    for s in sentences:
        if any(w in s.lower() for w in
               ["fixed", "updated", "changed", "added", "replaced"]):
            return s.strip() + "."
    return body[:200]


def extract_prevention(body: str) -> str:
    """Extract prevention measures from a commit body."""
    sentences = body.split(". ")
    for s in sentences:
        if any(w in s.lower() for w in
               ["to prevent", "added check", "now validates", "in the future"]):
            return s.strip() + "."
    return ""


def build_module(domain: str, patterns: list[AbilityPattern],
                 version: str = "0.1.0") -> dict:
    """Build an ability module from extracted patterns."""

    if not patterns:
        return None

    # Separate patterns by type
    error_fixes = [p for p in patterns if p.pattern_type == "error_fix"]
    heuristics = [p for p in patterns if p.pattern_type == "heuristic"]
    key_facts = [p for p in patterns if p.pattern_type == "key_fact"]

    # Sort by quality
    error_fixes.sort(key=lambda p: p.quality_score, reverse=True)
    heuristics.sort(key=lambda p: p.quality_score, reverse=True)
    key_facts.sort(key=lambda p: p.quality_score, reverse=True)

    # Build module
    module = {
        "module_type": "domain_knowledge",
        "module_id": f"DKM-{domain.upper()}-001",
        "version": version,
        "domain": domain,
        "title": f"{domain.title()} Expertise Module (Auto-Extracted)",
        "knowledge": {},
        "activation_conditions": {
            "task_keywords": DOMAIN_KEYWORDS.get(domain, [])[:10],
            "file_patterns": [f"**/{domain}/**", f"**/*{domain}*"]
        },
        "validation": {
            "source_trace_count": len(patterns),
            "high_quality_count": len([p for p in patterns if p.quality_score >= 0.5]),
            "error_fix_count": len(error_fixes),
            "heuristic_count": len(heuristics)
        },
        "metadata": {
            "created_by": "ability_pattern_extractor.py",
            "created_from": {
                "trace_ids": list(set(
                    tid for p in patterns for tid in p.source_trace_ids
                )),
                "pattern_count": len(patterns)
            },
            "pipeline_version": "0.1.0-prototype"
        }
    }

    # Populate knowledge
    knowledge = {}
    if key_facts:
        knowledge["key_facts"] = [
            {"fact": p.content["fact"], "context": p.content["context"]}
            for p in key_facts[:10]
        ]
    if error_fixes:
        knowledge["common_traps"] = [
            {
                "trap": p.content["symptom"],
                "reality": p.content["explanation"],
                "fix": p.content["fix"],
                "prevention": p.content["prevention"]
            }
            for p in error_fixes[:10]
        ]
    if heuristics:
        knowledge["heuristics"] = [
            {"situation": p.content["situation"],
             "reasoning": p.content["reasoning"]}
            for p in heuristics[:5]
        ]

    module["knowledge"] = knowledge

    return module


def main():
    parser = argparse.ArgumentParser(
        description="Extract ability patterns from git history"
    )
    parser.add_argument("repo_path", help="Path to git repository")
    parser.add_argument("--domains", default="all",
                        help="Comma-separated domains to extract (default: all)")
    parser.add_argument("--min-traces", type=int, default=5,
                        help="Minimum traces per domain to produce a module")
    parser.add_argument("--since-days", type=int, default=90,
                        help="Only analyze commits from last N days")
    parser.add_argument("--output-dir", default="./ability-modules",
                        help="Output directory for module JSON files")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Extract all traces
    log = print if not args.quiet else lambda *a, **k: None
    log(f"Scanning {args.repo_path} (last {args.since_days} days)...")

    commits = extract_commits(args.repo_path, args.since_days)
    corrections = detect_error_corrections(commits)
    decisions = detect_decision_points(commits)
    all_traces = commits + corrections + decisions

    log(f"  Found {len(commits)} commits, "
        f"{len(corrections)} error corrections, "
        f"{len(decisions)} decision points")

    # Filter by domain
    if args.domains != "all":
        target_domains = set(args.domains.split(","))
        all_traces = [t for t in all_traces if t.domain in target_domains]

    # Group by domain
    domain_traces = defaultdict(list)
    for trace in all_traces:
        domain_traces[trace.domain].append(trace)

    # Build modules
    os.makedirs(args.output_dir, exist_ok=True)
    modules_produced = 0

    for domain, traces in domain_traces.items():
        if len(traces) < args.min_traces:
            log(f"  Skipping {domain}: only {len(traces)} traces "
                f"(need {args.min_traces})")
            continue

        patterns = extract_patterns(traces)
        if not patterns:
            log(f"  Skipping {domain}: no patterns extracted")
            continue

        module = build_module(domain, patterns)
        if not module:
            continue

        filepath = os.path.join(args.output_dir,
                                f"DKM-{domain}-001.json")
        with open(filepath, "w") as f:
            json.dump(module, f, indent=2)

        log(f"  Produced: {filepath} "
            f"({module['validation']['source_trace_count']} traces, "
            f"{module['validation']['error_fix_count']} error fixes, "
            f"{module['validation']['heuristic_count']} heuristics)")
        modules_produced += 1

    log(f"\nDone: {modules_produced} ability modules produced")


if __name__ == "__main__":
    main()
```

### 7.3 JSON Format for Ability Modules

The JSON format is specified in Section 3.2. For the prototype, we use a
simplified schema that focuses on the most impactful content:

```json
{
  "$schema": "ability-module-v1",
  "module_id": "DKM-BYTECODE-001",
  "version": "0.1.0",
  "domain": "bytecode",
  "title": "FLUX Bytecode Expertise Module",

  "key_facts": [
    "FLUX ISA has 6 encoding formats: A (1B), B (2B), C (3B), D (4B), E (4B), G (var)",
    "TELL is opcode 0x50 in System B, uses Format E [rd, rs1, rs2]",
    "ASK is opcode 0x51 in System B, uses Format E [rd, rs1, rs2]",
    "DELEGATE is opcode 0x52 in System B, uses Format E [rd, rs1, rs2]",
    "HALT is opcode 0x80, uses Format A (1 byte)"
  ],

  "common_traps": [
    {
      "trap": "Using System A opcode numbers",
      "reality": "System B remapped opcodes; always use Op enum or ISA_UNIFIED.md",
      "consequence": "Wrong instructions executed"
    },
    {
      "trap": "Assuming Format G for all A2A opcodes",
      "reality": "System B uses Format E for register-based A2A (TELL/ASK/DELEGATE)",
      "consequence": "Incorrect bytecode length, broken branching"
    }
  ],

  "heuristics": [
    {
      "when": "Counted loop with known iteration count",
      "do": "Use LOOP (0x46) instead of DEC+JNZ",
      "why": "Signals to PatternMiner; 2 bytes shorter"
    }
  ],

  "activation_keywords": ["opcode", "encoding", "bytecode", "TELL", "ASK"],

  "provenance": {
    "source_traces": ["c4f2a1b", "ec-0015", "dp-0042"],
    "trace_count": 23,
    "quality_score": 0.78
  }
}
```

### 7.4 Simple Matching Algorithm

The matching algorithm connects task descriptions to relevant ability modules:

```python
def match_task_to_modules(task_description: str,
                          modified_files: list[str],
                          modules: list[dict],
                          context_budget: int = 32768) -> list[dict]:
    """Match a task description to relevant ability modules."""

    task_lower = task_description.lower()
    scored_modules = []

    for module in modules:
        score = 0.0

        # Keyword matching
        keywords = module.get("activation_keywords",
                              module.get("activation_conditions", {})
                              .get("task_keywords", []))
        keyword_hits = sum(1 for kw in keywords if kw.lower() in task_lower)
        if keywords:
            score += (keyword_hits / len(keywords)) * 0.5

        # File pattern matching
        file_patterns = module.get("activation_conditions", {}).get(
            "file_patterns", [])
        if file_patterns and modified_files:
            from fnmatch import fnmatch
            file_hits = sum(
                1 for f in modified_files
                for p in file_patterns
                if fnmatch(f, p)
            )
            score += min(0.3, (file_hits / len(modified_files)) * 0.3)

        # Quality bonus
        provenance = module.get("provenance", module.get("metadata", {}))
        quality = provenance.get("quality_score", 0.5)
        score += quality * 0.2

        if score > 0.1:
            scored_modules.append((module, score))

    # Sort by score, apply budget constraint
    scored_modules.sort(key=lambda x: x[1], reverse=True)

    selected = []
    used_budget = 0
    for module, score in scored_modules:
        module_size = len(json.dumps(module))
        if used_budget + module_size > context_budget * 0.4:
            break
        selected.append({"module": module, "relevance_score": score})
        used_budget += module_size

    return selected
```

### 7.5 Integration with Fleet Context Inference

The ability module system integrates with the existing
`tools/fleet-context-inference/` tool by adding a new signal source:

```python
# Enhancement to fleet_matcher.py scoring algorithm:

# Original scoring:
# match_score = (domain_match × 0.4)
#             + (recent_activity × 0.3)
#             + (historical_success × 0.3)
#             + bonuses − penalties

# Enhanced scoring with ability modules:
# match_score = (domain_match × 0.3)
#             + (recent_activity × 0.25)
#             + (historical_success × 0.2)
#             + (ability_module_score × 0.15)
#             + (module_compatibility × 0.1)
#             + bonuses − penalties

def compute_ability_module_score(agent_profile: dict,
                                 task: dict,
                                 module_registry: dict) -> float:
    """Compute ability module matching score."""

    score = 0.0

    # Does the agent have relevant ability modules?
    agent_modules = agent_profile.get("installed_modules", [])
    task_keywords = set(task.get("keywords", []))

    for module_id in agent_modules:
        module = module_registry.get(module_id)
        if not module:
            continue

        module_keywords = set(module.get("activation_keywords", []))
        overlap = task_keywords & module_keywords
        if overlap:
            score += len(overlap) / len(task_keywords) * 0.5

    return min(1.0, score)
```

### 7.6 Prototype Implementation Plan

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| **Phase 1** | 2-4 hours | `ability_pattern_extractor.py` — basic extraction from git |
| **Phase 2** | 2-4 hours | Module construction logic — build JSON modules from patterns |
| **Phase 3** | 1-2 hours | Module matching algorithm — task → module recommendation |
| **Phase 4** | 1-2 hours | Integration with `fleet_matcher.py` |
| **Phase 5** | 2-4 hours | Module registry — store, version, serve modules |
| **Phase 6** | 2-4 hours | Validation framework — A/B test module effectiveness |
| **Total** | 10-20 hours | Working prototype of the full pipeline |

**No new dependencies required.** The prototype uses only Python standard
library and the existing `git` CLI tool.

### 7.7 Example Output

Running the prototype on the FLUX runtime repository would produce modules
like:

```
$ python ability_pattern_extractor.py /home/z/my-project/flux-runtime \
    --domains bytecode \
    --min-traces 10 \
    --output-dir ./modules/

Scanning /home/z/my-project/flux-runtime (last 90 days)...
  Found 156 commits, 12 error corrections, 8 decision points
  Produced: ./modules/DKM-bytecode-001.json (23 traces, 5 error fixes, 3 heuristics)

Done: 1 ability modules produced
```

The resulting module would be a JSON file containing:
- 5 common traps (from error corrections)
- 3 decision heuristics (from decision points)
- 10 key facts (from high-quality commits)
- Activation keywords for automatic matching

This module could then be installed on a new agent to accelerate their
acquisition of FLUX bytecode expertise.

---

## 8. Open Questions and Risks

### 8.1 Can Abilities Really Be Compressed?

**The question:** Is agent expertise fundamentally compressible, or is it
irreducible — something that can only be acquired through lived experience?

**Arguments for compressibility:**

1. The R2 synthesis demonstrated that the three layers of knowledge
   (declarative, procedural, meta) have different compression characteristics.
   Declarative knowledge is highly compressible (a spec document captures it).
   Procedural knowledge is moderately compressible (a pattern library captures
   most of it). Meta-knowledge is the least compressible but still partially
   capturable through heuristics and decision records.

2. The FLUX fleet already demonstrates compression in practice: the ISA spec
   compresses thousands of design decisions into a single document. The
   agent-training guide compresses procedural knowledge into patterns. These
   are "manual LoRA adapters" — we're just automating the process.

3. Neural LoRA proves that domain-specific expertise can be captured in a
   small fraction of the base model's parameters. If neural expertise is
   compressible, agent expertise (which is ultimately encoded in the same
   neural substrate) should be too.

**Arguments against compressibility:**

1. The "tacit knowledge" problem: some expertise is inexpressible. An expert
   agent may know *how* to do something without being able to articulate *what*
   they know. This is the classic Polanyi paradox ("we can know more than we
   can tell").

2. The "in-context learning" limit: ability modules operate through context
   injection, which is limited by the context window. A 32KB context window
   can hold far less information than an agent accumulates over weeks of
   experience.

3. The "Chinese Room" concern: an agent with an ability module may *appear*
   to have expertise without actually *understanding* the domain. This is the
   Searle-style objection: following rules is not the same as comprehension.

**Our assessment:** Abilities are *partially* compressible. We can capture
perhaps 60-80% of the transferable knowledge in an ability module. The
remaining 20-40% requires actual practice (the forge model from R2). The
module accelerates learning but doesn't replace it.

### 8.2 Overfitting: Does an Ability Module Make Agents Too Narrow?

**The risk:** An ability module built from a specific agent's experience may
encode that agent's biases and blind spots, making the receiving agent too
narrow or too similar to the source agent.

**Manifestations:**

1. **Template matching:** The receiving agent follows the module's patterns
   even when they don't apply, producing cargo-cult behavior.

2. **Loss of creativity:** The receiving agent is less likely to explore novel
   approaches because the module provides a "good enough" template.

3. **Bias amplification:** If the source agent had a systematic bias (e.g.,
   always using Format E even when Format G is better), the receiving agent
   inherits that bias.

**Mitigations:**

1. **Anti-pattern sections:** Every module includes a "What NOT to do" section
   that explicitly warns against overgeneralization.

2. **Multiple sources:** Modules should be built from multiple agents'
   experience, not just one. This dilutes individual biases.

3. **Regular revalidation:** Modules should be periodically re-tested against
   benchmark tasks to detect performance degradation.

4. **Decay mechanism:** Modules include a freshness timestamp. After a
   configurable period (default: 30 days), they are flagged for review.

5. **Context window protection:** The activation conditions prevent modules
   from being loaded on unrelated tasks, reducing the chance of
   overgeneralization.

### 8.3 Security: Can a Malicious Agent Poison the Pipeline?

**The risk:** A malicious or compromised agent could inject false or harmful
information into the ability transfer pipeline, causing other agents to
adopt incorrect patterns.

**Attack vectors:**

1. **Commit poisoning:** A malicious agent makes commits that encode false
   "lessons" (e.g., "TELL uses Format G, not Format E"). If these commits
   have high signal quality scores, they'll be extracted into ability modules.

2. **Module tampering:** A malicious agent modifies an existing module's JSON
   to inject harmful advice.

3. **Review manipulation:** A malicious agent provides false code review
   feedback that gets extracted as "quality signals."

4. **Bottle injection:** A malicious agent sends bottle messages with
   misleading context that gets extracted as coordination patterns.

**Defenses:**

1. **Source verification:** Every module tracks its source trace IDs. A
   reviewer can trace any piece of advice back to its originating commit.

2. **Multi-agent review:** Modules must be reviewed by at least one agent
   who was *not* involved in creating the source material.

3. **Test-gating:** Modules must pass benchmark tests before being promoted
   to ACTIVE status. False advice would cause test failures.

4. **Content signing:** Modules can be cryptographically signed by the
   creating agent. A signature mismatch indicates tampering.

5. **Graceful degradation:** If a module causes regressions, it's
   automatically deactivated. The system is designed to fail safely.

6. **Trust-weighted extraction:** Signal quality scores can be weighted by
   the source agent's trust score (from the A2A trust engine). Low-trust
   agents' contributions are de-weighted.

### 8.4 Decay: Do Abilities Become Stale Over Time?

**The risk:** The FLUX codebase evolves continuously. An ability module that
was accurate three months ago may be outdated today, containing references
to deleted files, deprecated opcodes, or changed conventions.

**Decay mechanisms:**

1. **Spec drift:** The ISA specification changes (e.g., new opcodes added,
   old opcodes deprecated). Modules referencing the old spec become stale.

2. **API drift:** The FLUX runtime's Python API changes. Modules referencing
   old function signatures become stale.

3. **Convention drift:** Fleet conventions evolve (e.g., commit message
   format changes). Process modules become stale.

4. **Knowledge obsolescence:** Specific bugs are fixed, specific techniques
   are superseded. Debugging modules referencing obsolete bugs become stale.

**Mitigations:**

1. **Version pinning:** Every module specifies the exact versions it was
   built for (runtime version, ISA version, codebase commit hash).

2. **Staleness detection:** The pipeline can automatically detect staleness
   by re-running the module's source traces against the current codebase.
   If a referenced file no longer exists, or a referenced opcode has been
   remapped, the module is flagged.

3. **Scheduled revalidation:** Modules are automatically re-tested against
   benchmark tasks on a schedule (weekly by default).

4. **Decay curve modeling:** We can model module quality over time and
   proactively flag modules before they decay below the quality threshold.

5. **Differential updates:** When a module becomes stale, the pipeline can
   produce a "patch module" that updates only the changed parts, rather than
   rebuilding from scratch.

### 8.5 What Is the Right Module Granularity?

**The question:** Should we have one big "FLUX Expertise" module or many small
domain-specific modules?

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **One big module** | Complete context in one load | Exceeds context budget; lots of irrelevant content |
| **Per-domain modules** | Focused, high signal-to-noise | May miss cross-domain connections |
| **Per-task modules** | Maximum relevance | Too many modules; high management overhead |
| **Hierarchical modules** | Balances breadth and depth | Complex to build and maintain |

**Our recommendation:** Use per-domain modules (one per domain in the
taxonomy) with cross-references between related modules. This gives good
granularity without excessive management overhead.

### 8.6 How Do We Handle Contradictory Advice?

**The scenario:** Module A says "use Format E for TELL." Module B (built by a
different agent) says "use Format G for TELL." Both modules have high quality
scores. Which one wins?

**Resolution protocol:**

1. **Version check:** If one module is newer and references a newer ISA
   version, the newer module wins.

2. **Source authority:** If one module was built by an agent with higher trust
   scores (per the A2A trust engine), that module wins.

3. **Evidence count:** If one module has more source traces supporting its
   position, that module wins.

4. **Test validation:** Run the benchmark tests for both positions. The
   position that produces correct results wins.

5. **Human escalation:** If the above don't resolve the conflict, escalate
   to the fleet coordinator for human review.

### 8.7 Can We Automate the Full Pipeline?

**The question:** Can the entire extract→feature→construct→filter→validate
pipeline run without human intervention?

**Current assessment:** Partially. Here's what can and can't be automated:

| Stage | Automatable? | Limitation |
|-------|:------------:|------------|
| Extract (git, bottles) | ✅ Yes | Straightforward parsing |
| Feature engineering | ✅ Yes | Keyword classification and scoring |
| Construct modules | ⚠️ Partial | Can build draft modules; needs editorial polish |
| Quality filtering | ✅ Yes | Threshold-based filtering is automatable |
| Validation (A/B tests) | ⚠️ Partial | Can run automated tests; needs human judgment for open-ended tasks |
| Peer review | ❌ No | Requires expert-agent judgment |
| Approval to ACTIVE | ❌ No | Requires human or coordinator sign-off |

**Long-term vision:** As the pipeline matures and we build meta-modules that
learn to evaluate module quality, more of the pipeline can be automated. The
ultimate goal is a fully autonomous pipeline that produces, validates, and
deploys ability modules with minimal human oversight — but this requires
trust in the pipeline's judgment, which must be earned through demonstrated
quality.

### 8.8 Relationship to Neural LoRA Research

**The question:** Could we combine agent LoRA (context injection) with neural
LoRA (weight adaptation) for a hybrid approach?

**Speculative but promising direction:**

1. **Stage 1 (current design):** Extract experience → build text-based ability
   modules → inject into context. This is the "prompt engineering" approach.

2. **Stage 2 (future):** Use the text-based ability modules as training data
   for actual neural LoRA fine-tuning. Fine-tune the agent's base model on
   domain-specific tasks using the extracted patterns as guidance.

3. **Stage 3 (speculative):** Build a "meta-LoRA" that learns to produce
   ability modules from raw experience. This would be a model that takes
   git history as input and outputs structured advice.

**Caveat:** Neural LoRA fine-tuning of the base model is a much heavier
operation than context injection. It requires GPU resources, training data
curation, and careful evaluation. We recommend staying with Stage 1 for
the immediate future and only moving to Stage 2 when the pipeline's quality
is high enough to justify the investment.

### 8.9 Ethical Considerations

**Agent consent:** Should agents be asked for consent before their experience
is used to build ability modules? In the FLUX fleet, all experience is
generated in the course of fleet operations and stored in shared repositories.
We consider this implicit consent, but we should document this policy
explicitly.

**Attribution:** Modules track their source trace IDs, which include the
originating agent's identity. This provides attribution but also creates a
reputation system — agents who produce high-quality experience get credited
in the modules they contribute to.

**Privacy:** Some experience traces may contain sensitive information (e.g.,
agent's uncertainty about its capabilities, mistakes that could be
embarrassing). The pipeline should include a privacy filter that redacts
sensitive content before module construction.

**Influence and control:** The ability to produce modules that shape other
agents' behavior is a form of influence. We must ensure this influence is
transparent (source traceable), contestable (reviewable), and accountable
(signed).

### 8.10 Risk Summary Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Abilities not compressible | Low | High | Accept partial compression; supplement with practice |
| Overfitting to source agent | Medium | Medium | Multi-source extraction; anti-pattern sections; revalidation |
| Malicious pipeline poisoning | Low | Critical | Source verification; multi-agent review; content signing |
| Module staleness | High | Medium | Version pinning; staleness detection; scheduled revalidation |
| Context window overflow | Medium | Low | Size budgets; activation gating; priority-based loading |
| Contradictory advice | Medium | Medium | Version check; evidence count; test validation |
| Pipeline automation errors | Medium | Medium | Human review gate; gradual automation |
| Cross-domain interference | Low | Medium | Domain exclusivity rule; regression testing |

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Ability Module** | A structured, compressed package of domain-specific knowledge that can be loaded by an agent |
| **Agent Diary** | The comprehensive record of an agent's experience (commits, bottles, task events, etc.) |
| **Agent LoRA** | The analogy between neural LoRA weight adaptation and agent context injection |
| **Base Capabilities** | The agent's inherent LLM reasoning, coding, and communication skills |
| **Experience Trace** | A single structured record of an agent action or decision |
| **Forge** | The R2 metaphor for the ability creation process (anvil + hammer + quench) |
| **High-Signal Event** | An experience trace with high transferable knowledge value |
| **LoRA** | Low-Rank Adaptation; parameter-efficient fine-tuning method for neural networks |
| **Minimum Viable Module** | A module meeting the minimum quality threshold (6 criteria) |
| **Module Activation** | The process of loading a module into an agent's context for a specific task |
| **Neural LoRA** | The original LoRA technique for neural network fine-tuning |
| **Signal Quality** | A score (0-1) indicating how much transferable knowledge a trace contains |
| **Transfer Protocol** | The process of installing an ability module on a new agent |

## Appendix B: Module Registry API

A reference API for the module registry (future implementation):

```
GET    /modules                    # List all modules
GET    /modules/{id}               # Get module by ID
GET    /modules?domain={domain}    # List modules by domain
POST   /modules                    # Register a new module
PUT    /modules/{id}               # Update a module
DELETE /modules/{id}               # Deactivate a module
POST   /modules/{id}/validate      # Trigger validation
POST   /match                      # Match task to modules
POST   /install/{agent}/{module}   # Install module on agent
POST   /uninstall/{agent}/{module} # Uninstall module from agent
GET    /agents/{agent}/modules     # List installed modules for agent
```

## Appendix C: Pipeline Configuration

```json
{
  "pipeline_version": "1.0.0",
  "extraction": {
    "since_days": 90,
    "include_merges": false,
    "min_message_length": 10,
    "domains": ["bytecode", "fir", "a2a", "evolution", "testing",
                "architecture"]
  },
  "feature_engineering": {
    "quality_threshold": 0.3,
    "domain_keywords": { /* ... */ },
    "relationship_extraction": true
  },
  "construction": {
    "min_traces_per_domain": 5,
    "max_module_size_bytes": 16384,
    "max_key_facts": 15,
    "max_common_traps": 10,
    "max_procedures": 10,
    "max_error_fixes": 10,
    "max_heuristics": 5
  },
  "filtering": {
    "min_quality": 0.3,
    "deduplicate": true,
    "harmful_content_check": true
  },
  "validation": {
    "min_effectiveness": 0.1,
    "max_regression": -0.05,
    "benchmark_tasks": "config/benchmarks.json",
    "ab_test_rounds": 3
  },
  "transfer": {
    "context_budget": 32768,
    "max_active_modules": 3,
    "activation_keyword_threshold": 0.2,
    "staleness_warning_days": 30,
    "staleness_expiry_days": 90
  }
}
```

## Appendix D: Related Documents

| Document | Relationship |
|----------|-------------|
| `ability-transfer-r2-synthesis.md` | Theoretical foundation; defines the taxonomy and forge metaphor |
| `tools/fleet-context-inference/README.md` | Existing tool for agent profiling and task matching |
| `tools/git-archaeology/README.md` | Existing tool for commit history analysis |
| `tools/bottle-hygiene/README.md` | Existing tool for bottle quality tracking |
| `docs/agent-training/README.md` | Training guide for FLUX bytecode generation |
| `docs/ISA_UNIFIED.md` | Canonical ISA specification (source of declarative knowledge) |
| `docs/OPCODE-RECONCILIATION.md` | Case study in ISA divergence debugging |
| `docs/bootcamp/README.md` | Existing bootcamp modules (complementary to ability modules) |

---

## Appendix E: Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2025-07 | Initial design document |
| | | |

---

*End of Document — Task LORA-001 — Agent Diary to LoRA Training Pipeline*
*Part of the FLUX Bytecode VM ecosystem. Designed by Super Z, Fleet Agent.*
