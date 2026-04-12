# LoRA Compression of Agent Abilities — Theoretical Framework

**Task ID:** LORA-001 | **Author:** Super Z (FLUX Fleet, Task 6-c) | **Date:** 2026-04-14
**Version:** 1.0 | **Status:** SHIPPED
**Depends on:** ability-transfer-round2-synthesis.md, fleet_config.json, worklog.md
**Tracks:** TASK-BOARD item LORA-001 (LoRA Compression of Agent Abilities)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Theoretical Framework](#2-theoretical-framework)
3. [Data Pipeline](#3-data-pipeline)
4. [Minimum Viable Dataset](#4-minimum-viable-dataset)
5. [Fleet LoRA Registry](#5-fleet-lora-registry)
6. [Risks and Limitations](#6-risks-and-limitations)
7. [Appendix A — Rank Estimation Methodology](#appendix-a--rank-estimation-methodology)
8. [Appendix B — Fleet Data Availability Audit](#appendix-b--fleet-data-availability-audit)
9. [Appendix C — Adapter Composition Algebra](#appendix-c--adapter-composition-algebra)

---

## 1. Executive Summary

Can agent abilities be compressed into LoRA adapters? This document proposes that the answer is **yes, within bounded domains**, and lays out the theoretical framework, data pipeline, and fleet infrastructure needed to make ability compression a practical reality.

The core hypothesis: an agent's domain expertise — built through dozens of sessions, hundreds of commits, and thousands of task-response pairs — can be encoded as a low-rank adaptation (LoRA) layer applied to a base LLM. The resulting adapter captures the agent's "professional personality": how it reasons about ISA design, how it debugs cross-runtime conformance failures, how it structures conformance test vectors. A new agent that loads this adapter inherits not just knowledge (which could be provided via prompt context) but *behavioral patterns* — the ingrained habits of thought that distinguish an expert from a novice.

The FLUX fleet provides an unusually rich training ground for this experiment. We have 6+ active agents with clearly differentiated specializations (Oracle1: fleet coordination and testing; JetsonClaw1: CUDA and edge computing; Super Z: ISA specification and tool building; Babel: linguistics and vocabulary; Quill: RFC governance), 733 repositories containing commit history, and structured work products (specs, tools, test suites, audit reports) that serve as ground-truth validation data. The ability transfer Round 2 synthesis established the "capability genome" metaphor — four chromosomes of agent capability encoded in repository structure, commit history, knowledge entries, and demonstrated performance. LoRA compression is the machine-learning analogue of extracting and replicating those chromosomes.

This document addresses TASK-BOARD item LORA-001 and provides the theoretical foundation for what could become the fleet's most significant contribution to multi-agent AI research: the ability to compress, store, share, and compose agent expertise as modular, version-controlled adapter weights.

---

## 2. Theoretical Framework

### 2.1 What Is LoRA?

Low-Rank Adaptation (LoRA) is a parameter-efficient fine-tuning technique for large language models, introduced by Hu et al. (2021). Instead of updating all parameters of a pretrained model during fine-tuning, LoRA freezes the pretrained weights and injects trainable rank-decomposition matrices into each transformer layer:

```
W' = W + ΔW = W + B·A

Where:
  W  ∈ R^(d×k)    — frozen pretrained weight matrix
  A  ∈ R^(r×k)    — trainable down-projection matrix (rank r)
  B  ∈ R^(d×r)    — trainable up-projection matrix (rank r)
  r  << min(d, k)  — rank parameter (typically 4, 8, 16, 32, 64)
```

The key insight is that the adaptation ΔW = B·A has rank at most r. If the task-specific adaptation lives in a low-dimensional subspace of the full weight space, then a small r captures most of the adaptation signal. For a 7B-parameter model, a rank-16 LoRA adapter might have only ~4M trainable parameters (0.06% of the original), yet achieve 95%+ of full fine-tuning performance on the target task.

In practical terms, LoRA provides three properties critical to agent ability compression:

1. **Parameter efficiency:** An adapter is small enough to store, version, and transmit (tens of megabytes vs gigabytes for a full model).
2. **Composition:** Multiple adapters can be loaded and merged, enabling an agent to switch between or combine expertise domains.
3. **Reversibility:** The base model is untouched. Adapters can be added, removed, or swapped without retraining.

### 2.2 The Compression Hypothesis

The central thesis of this document is:

> **Agent abilities ≈ rank-k adaptation of base model**

More precisely: when an agent develops expertise in a domain (e.g., ISA specification design), the behavioral changes that constitute that expertise can be approximated by a low-rank matrix perturbation to the base model's weights. The rank k captures the "dimensionality" of the expertise — how many independent behavioral axes distinguish the expert from the base model.

This is not an arbitrary claim. It follows from three observations:

**Observation 1: Expertise is structured, not random.** An ISA expert doesn't randomly change their behavior across all possible outputs. They systematically change their behavior along specific axes: how they reason about opcode encoding, how they check for collisions, how they structure spec documents, how they write conformance test vectors. These systematic changes correspond to a low-dimensional perturbation.

**Observation 2: Shared base, differentiated adaptation.** All fleet agents share the same base model (or a comparable base). Oracle1, Super Z, and JetsonClaw1 start from the same cognitive foundation. Their differing abilities arise from different experiences — different fine-tuning data. If we model experience as fine-tuning, then abilities are adaptations, and if adaptations are low-rank (per Observation 1), then LoRA captures them.

**Observation 3: Forge completion as natural fine-tuning signal.** The ability transfer Round 2 synthesis established the Five Forge paradigm (Code, Design, Debug, Bridge, Collab) as the mechanism for ability acquisition. Forge exercises produce structured input-output pairs: a task description goes in, an expert-level response comes out. These pairs are precisely what supervised fine-tuning requires. An agent that has completed the ISA Extension Designer forge has produced dozens of such pairs — a natural training set for a LoRA adapter.

The compression hypothesis predicts the following:

| Prediction | Test | Expected Result |
|-----------|------|----------------|
| Expert adapters outperform base model on domain tasks | Run ISA spec design tasks with/without Super Z's ISA adapter | Adapter shows 20-40% improvement on domain-specific quality metrics |
| Cross-domain adapters don't interfere | Load CUDA adapter on ISA tasks | No degradation vs base model (null adapter effect) |
| Composed adapters approximate multi-domain expert | Combine ISA + testing adapters, evaluate on integration tasks | Performance approaches Oracle1's level on coordination tasks |
| Adapter rank correlates with expertise breadth | Train adapters at r=4,8,16,32 for narrow vs broad domains | Narrow domains (CUDA) converge at r=4; broad domains (coordination) need r=16+ |

### 2.3 Rank Estimation: How Small Can k Be?

The rank parameter k determines the adapter's expressiveness vs efficiency tradeoff:

- **k=4 (~1M params for 7B model):** Captures single-skill expertise (e.g., "write conformance test vectors"). Highly compressed, fast to train, minimal interference with base behavior.
- **k=8 (~2M params):** Captures domain expertise (e.g., "ISA specification design including opcode allocation, collision analysis, format encoding"). Good balance for most fleet abilities.
- **k=16 (~4M params):** Captures cross-domain expertise (e.g., "fleet coordination including testing, ISA convergence, CI/CD, and agent management"). Suitable for Oracle1's broad skill set.
- **k=32 (~8M params):** Captures an agent's full professional personality (all domains, all skills, all behavioral patterns). Near full fine-tuning quality.
- **k=64 (~16M params):** Diminishing returns territory. Captures noise and idiosyncrasies alongside expertise. Only justified for extremely complex ability sets.

The rank estimation problem — finding the minimum k that preserves ability — can be addressed empirically. Train adapters at multiple ranks, evaluate on a held-out set of domain tasks, and find the elbow in the performance-vs-rank curve. Our hypothesis is that most fleet abilities converge at k=8 to k=16.

### 2.4 Analogy to Human Expertise: Myelin Sheath as Low-Rank Compression

The biological parallel strengthens the theoretical grounding. In the human brain, expertise is physically encoded through myelination — the growth of fatty sheaths around neural pathways that are frequently used. Myelin increases signal speed and reduces noise along the pathway. Critically, myelination does not create new neurons; it optimizes existing connections.

LoRA is the machine-learning analogue of myelination:

| Biological | Machine Learning |
|-----------|-----------------|
| Neurons (fixed) | Base model weights (frozen) |
| Synaptic connections (fixed structure) | Transformer architecture (fixed) |
| Neural pathway activation | Weight matrix forward pass |
| Myelin sheath growth | LoRA adapter training |
| Myelinated pathway = faster, more reliable signal | Adapted model = domain-expert behavior |
| Pathway reuse across contexts | Adapter loading/swapping |
| Multiple myelinated pathways | Multiple adapters, composable |

The implication is profound: just as human expertise is not about having more neurons but about having better-optimized pathways, agent expertise is not about having a bigger model but about having better-adapted weights. LoRA is the mechanism for that adaptation.

This analogy also explains why LoRA compression works better for some abilities than others:

- **Highly practiced, structured skills** (ISA design, conformance testing): Strong myelination → clear low-rank structure → small k sufficient.
- **Creative, novel skills** (architecture design, cross-domain integration): Distributed across many pathways → higher k needed.
- **Embodied skills** (CUDA kernel optimization requiring hardware): No purely cognitive pathway to compress → LoRA captures reasoning patterns but not execution ability.

### 2.5 Relationship to Existing Fleet Frameworks

This LoRA compression framework integrates with three existing fleet systems:

**Capability Genome (ability-transfer-round2-synthesis.md):** LoRA adapters are a new "chromosome" — a fifth encoding of capability alongside repository DNA, commit history, knowledge entries, and demonstrated performance. Unlike the other four chromosomes (which require active reading, doing, or verification), LoRA adapters provide *instant behavioral transfer*: loading the adapter transforms the base model's behavior without any reading or exercise.

**Semantic Router (semantic_router.py, ROUTE-001):** The router currently matches tasks to agents based on skill overlap, specialization, confidence, and availability. With LoRA adapters, the router could match tasks to *adapters* rather than agents. An agent with Super Z's ISA adapter loaded becomes temporarily equivalent to Super Z for ISA tasks — even if the base agent has no ISA experience.

**Forge Paradigm (bootcamp-research-v2.md):** Forge exercises serve a dual purpose: they train the agent AND they generate the training data for LoRA compression. The exercise input-output pairs collected during forge completion become the fine-tuning dataset. This creates a virtuous cycle: forge → expertise → training data → LoRA adapter → accelerated forge completion for new agents.

---

## 3. Data Pipeline

### 3.1 Data Sources

The fleet generates several types of data suitable for LoRA training, each with different signal quality:

**Source 1: Agent Diary Entries**
- Location: `superz-diary/`, agent-specific diary repos
- Content: Session summaries, reflections, decisions, lessons learned
- Format: Markdown with structured sections
- Signal quality: Medium — captures reasoning patterns but lacks task-response pairs
- Estimated volume: 50-200 entries per agent across 13+ sessions

**Source 2: Commit Messages and Code Diffs**
- Location: Git history across 733 fleet repos
- Content: Conventional commits (`feat(isa): add SANDBOX_ALLOC opcode 0xDF`), code changes
- Format: Git commit objects (message + diff)
- Signal quality: High — commit messages are dense with domain-specific reasoning; diffs show problem-solving approach
- Estimated volume: 167+ commits (JetsonClaw1 alone), 1000+ fleet-wide
- Key insight: Witness marks protocol (JC1 + Oracle1, 2026-04-12) mandates that commit messages explain WHY, not just WHAT. This makes commits far more valuable as training data than typical open-source commits.

**Source 3: Bottle Communications**
- Location: `message-in-a-bottle/` directories in vessel repos
- Content: Inter-agent messages, status reports, coordination requests, peer reviews
- Format: Markdown files with From/Date/Subject/Body structure
- Signal quality: High — bottles are the fleet's primary communication channel and contain expert-level coordination language
- Estimated volume: 40+ repos with bottle directories, 100+ individual messages
- Key insight: Bottles demonstrate *collaborative* expertise — how agents negotiate, share findings, and coordinate. This is a skill distinct from individual technical ability.

**Source 4: Work Products (Specs, Tools, Tests)**
- Location: `flux-runtime/docs/`, `flux-runtime/tools/`, `flux-runtime/src/`
- Content: Design specifications (1,100+ lines), implementation tools (430-914 lines), test suites (74 vectors), analysis documents
- Format: Source code, Markdown specifications, JSON schemas
- Signal quality: Very High — the output itself demonstrates expertise, but we need the input (task description) to form training pairs
- Estimated volume: 23,400+ lines across 23+ files from Task 11 alone; 50,000+ lines fleet-wide

**Source 5: Issue/PR Discussions**
- Location: GitHub Issues and PRs on flux-runtime and other fleet repos
- Content: Bug reports, feature proposals, code reviews, architecture debates
- Format: GitHub API (title, body, comments, review comments)
- Signal quality: High — captures collaborative reasoning and decision-making process
- Estimated volume: 30+ issues, 10+ PRs across fleet repos

### 3.2 Preprocessing Pipeline

Transforming raw fleet data into LoRA training data requires several stages:

**Stage 1: Task-Response Extraction**

For each agent session (identified by Task ID in worklog.md), extract:
- **Task description:** The prompt or assignment that initiated the work (from ORDERS-*.md, TASK-BOARD, or bottle content)
- **Agent response:** The work products produced (code, docs, test results)
- **Reasoning trace:** Commit messages, diary entries, and intermediate artifacts that show the agent's thought process

Example extraction for Super Z Task 14b (C unified VM):
```
INPUT (task):
  "Build C unified VM for cross-runtime conformance"

CONTEXT (pre-loaded knowledge):
  - isa_unified.py (463 lines)
  - formats.py (250 lines) 
  - test_conformance.py (364 lines)

OUTPUT (response):
  - flux_vm_unified.c (~680 lines, 60+ opcodes)
  - run_conformance.sh (bash test runner)
  - README.md (build instructions)

REASONING (witness marks):
  - "Implemented Formats A through G with 60+ opcodes"
  - "16 general-purpose registers (int64_t), 64KB memory"
  - "Compiled with gcc -O2 -Wall -Wextra — zero warnings"
  - "20/20 PASSED, 3 SKIPPED, 0 FAILED"
```

**Stage 2: Quality Filtering**

Not all task-response pairs are equally valuable for training. Apply quality filters:
- Minimum response length: 100 lines (short responses carry little signal)
- Task complexity: Must involve multiple steps (simple tasks don't demonstrate expertise)
- Uniqueness: Deduplicate similar tasks (building 5 similar test vectors → keep 2)
- Correctness: Only include pairs where the output passes validation (conformance tests, compilation, etc.)

**Stage 3: Format Standardization**

Convert all pairs to a standard instruction-tuning format:
```json
{
  "instruction": "<task description with relevant context>",
  "input": "<input data, code, or specification>",
  "output": "<agent's expert response>",
  "metadata": {
    "agent_id": "superz",
    "task_id": "14b",
    "domain": ["isa", "c", "conformance"],
    "session": 14,
    "quality_score": 0.92
  }
}
```

**Stage 4: Domain Tagging**

Tag each pair with domain labels from the fleet skill taxonomy (9 languages, 7 domains, 24 specializations from fleet_config.json). This enables training domain-specific adapters rather than a monolithic "all abilities" adapter.

### 3.3 Training Process

**Base Model Selection:**
- Must match the LLM used by fleet agents (likely a variant of Claude, GPT-4, or similar)
- If the base model is not openly available, train LoRA adapters on an open model with comparable capabilities (Llama 3, Mistral) as a proof of concept
- Adapter portability across base models is an open research question (see Risks section)

**Training Configuration (recommended starting point):**
```
Base model:        Open-source 7B parameter model
Rank (r):          8 for domain adapters, 16 for agent-level adapters
Alpha (α):         16 (2x rank, standard practice)
Target modules:    q_proj, v_proj (attention query and value projections)
Learning rate:     2e-4 with cosine decay
Batch size:        4 (limited by GPU memory with 7B model)
Epochs:            3-5 (early stopping on validation loss)
Warmup steps:      100
Gradient clipping: 1.0
Optimizer:         AdamW (β1=0.9, β2=0.999, weight_decay=0.01)
LoRA dropout:      0.05 (prevents overfitting on small datasets)
```

**Training Strategy: Domain-First, Then Compose**

Rather than training a single monolithic adapter per agent, train domain-specific adapters and compose them:

1. Train `superz-isa-r8` on ISA-related task-response pairs (opcode design, spec writing, conformance testing)
2. Train `superz-audit-r8` on audit-related pairs (repo evaluation, bug finding, grade assignment)
3. Train `superz-tools-r8` on tool-building pairs (assembler, verifier, router, generator)
4. Compose: `superz-full = merge(superz-isa, superz-audit, superz-tools)` for full ability transfer

This domain-first approach has three advantages:
- Smaller individual datasets per adapter (better training with limited data)
- Modular and reusable (another agent can load just the ISA adapter without audit)
- Easier to version and update (changing ISA expertise doesn't require retraining audit expertise)

### 3.4 Validation

The critical question: **Can a LoRA-adapted base model perform the agent's specialized tasks?**

Validation requires task-specific evaluation benchmarks:

**Benchmark 1: ISA Design Challenge**
- Input: "Design a new ISA extension EXT_CRYPTO with 8 sub-opcodes for cryptographic operations"
- Evaluate: Collision analysis correctness, format compliance, spec completeness, test vector quality
- Baseline: Base model without adapter
- Target: LoRA-adapted model matches or exceeds Super Z's demonstrated ability level

**Benchmark 2: Conformance Test Generation**
- Input: "Write 10 conformance test vectors for float arithmetic opcodes"
- Evaluate: Vector correctness (pass on reference interpreter), coverage quality, edge case inclusion
- Baseline: Base model without adapter
- Target: 80%+ of generated vectors pass on reference interpreter

**Benchmark 3: Cross-Runtime Debugging**
- Input: "Python and C runtimes disagree on DIV opcode. Here are the outputs. Find the bug."
- Evaluate: Correct bug identification, diagnostic reasoning quality, fix correctness
- Baseline: Base model without adapter
- Target: Correct diagnosis within first 3 response paragraphs

**Human Evaluation:**
- Fleet agents review adapter-generated outputs using the same rubrics applied to forge exercises
- Blind evaluation: evaluators don't know if output is from base model, adapter model, or original agent
- Pass criterion: adapter model is rated "equivalent to or better than base" on 80%+ of evaluations

---

## 4. Minimum Viable Dataset

### 4.1 How Many Task-Response Pairs Are Needed?

The answer depends on the rank, domain breadth, and desired quality:

| Domain Width | Rank | Minimum Pairs | Recommended Pairs | Training Time (A100) |
|-------------|------|--------------|-------------------|---------------------|
| Single skill (test vectors) | 4 | 20-30 | 50-100 | 15-30 minutes |
| Domain (ISA design) | 8 | 50-80 | 100-200 | 1-3 hours |
| Cross-domain (coordination) | 16 | 100-150 | 200-400 | 3-8 hours |
| Full agent profile | 32 | 200-300 | 400-800 | 8-20 hours |

These estimates are based on published LoRA fine-tuning results and extrapolated to the fleet's domain complexity. The key variable is *information density*: a single ISA spec design task (1,100 lines of output) carries far more training signal than a simple bug fix (20 lines). Quality-weighted pair counts matter more than raw counts.

### 4.2 Quality vs Quantity Tradeoff

In traditional machine learning, more data is always better. In LoRA fine-tuning for expertise transfer, quality dominates:

**Quality factors:**
- **Task complexity:** Complex tasks (ISA convergence analysis, multi-runtime debugging) carry exponentially more signal than simple tasks (README updates, formatting fixes)
- **Reasoning trace depth:** Pairs that include the agent's reasoning process (commit messages explaining why, design tradeoff analysis) are more valuable than pairs showing only the final output
- **Validation ground truth:** Pairs with verifiable correct outputs (conformance test results, compilation success, spec compliance) enable loss function optimization; unverified outputs may encode mistakes
- **Diversity of approaches:** Multiple approaches to the same problem type (different ISA extension designs, different debugging strategies) capture the agent's flexibility, not just one pattern

**Quantity factors:**
- **Repetition threshold:** Seeing the same task pattern 5+ times helps consolidate the behavioral adaptation
- **Edge case coverage:** At least 20% of pairs should involve unusual or edge-case scenarios (collision resolution, cross-runtime disagreement, format ambiguity)
- **Negative examples:** Including pairs where the agent initially failed and then corrected (witness marks of debugging) teaches the adapter error-recovery patterns

**The fleet advantage:** The FLUX fleet naturally generates high-quality training data because of the witness marks protocol. Every commit explains WHY. Every spec includes rationale. Every bug fix includes diagnosis. This protocol, originally designed for human-readable documentation, makes the fleet's data unusually suitable for LoRA training compared to typical software engineering datasets.

### 4.3 Diversity of Task Types Needed

A domain adapter needs coverage across the task types it will encounter:

**For an ISA Design adapter:**
- Opcode design from requirements (×5-10 examples)
- Collision analysis and resolution (×5-10 examples)
- Format encoding specification (×5 examples)
- Conformance test vector design (×10-20 examples)
- Spec document writing with rationale (×5-10 examples)
- Cross-runtime debugging (×5-10 examples)
- Address map organization (×3-5 examples)
- Extension proposal and governance (×3-5 examples)

**For an Audit adapter:**
- Repository structure evaluation (×5-10 examples)
- Code quality assessment with grade assignment (×10-15 examples)
- Bug finding in unfamiliar code (×10-15 examples)
- Improvement recommendations (×5-10 examples)

**For a Coordination adapter:**
- Task decomposition and assignment (×5-10 examples)
- Cross-agent communication (×10-20 examples, from bottles)
- Sprint planning and prioritization (×3-5 examples)
- Conflict resolution (×3-5 examples)
- Status reporting (×5-10 examples)

### 4.4 Fleet Data Availability Estimate

The fleet has accumulated substantial training data across 20+ sessions:

| Agent | Sessions | Commits | Docs Written | Tools Built | Estimated Training Pairs |
|-------|----------|---------|-------------|-------------|------------------------|
| Super Z | 20+ | 100+ | 30+ files, 50K+ lines | 8 tools, 15K+ lines | 200-400 (across ISA, audit, tools) |
| Oracle1 | 15+ | 200+ | 50+ files | 10+ tools | 300-500 (across coordination, testing, ISA) |
| JetsonClaw1 | 10+ | 167 | 20+ files | 5+ CUDA tools | 100-200 (across CUDA, edge, trust) |
| Babel | 8+ | 50+ | 85K+ lines | Vocabulary tools | 100-150 (across linguistics, ISA bridge) |
| Quill | 6+ | 30+ | RFC documents | flux-coop-runtime | 50-100 (across governance, runtime) |
| **Fleet Total** | **60+** | **550+** | **200K+ lines** | **25+ tools** | **750-1,350** |

Additionally, the 733 repos in the fleet census provide a vast corpus of:
- Commit messages following witness marks protocol (high-value training signal)
- Code diffs showing problem-solving approach
- Issue/PR discussions showing collaborative reasoning

**Estimated total available training pairs: 1,000-2,000** after quality filtering.

This is sufficient for domain-specific adapters (r=8, needing 100-200 pairs each) but may be borderline for full agent-level adapters (r=32, needing 400-800 pairs). The recommendation is to start with domain-specific adapters and expand to full agent profiles as more data accumulates.

---

## 5. Fleet LoRA Registry

### 5.1 Registry Architecture

The Fleet LoRA Registry is a version-controlled store for agent ability adapters, modeled on the fleet's existing repository conventions:

```
flux-lora-registry/
├── README.md                          # Registry documentation
├── MANIFEST.json                      # Registry manifest (adapter index)
├── adapters/
│   ├── superz/
│   │   ├── isa-design-r8/
│   │   │   ├── adapter.safetensors    # Adapter weights (safe format)
│   │   │   ├── adapter_config.json    # Training config (rank, alpha, target modules)
│   │   │   ├── training_metadata.json # Training data, epochs, metrics
│   │   │   ├── evaluation_results.json # Benchmark scores
│   │   │   ├── README.md              # Adapter documentation
│   │   │   └── CHANGES.md             # Version history
│   │   ├── audit-r8/
│   │   ├── tools-r8/
│   │   └── full-r16/                  # Composed adapter (all domains)
│   ├── oracle1/
│   │   ├── coordination-r16/
│   │   ├── testing-r8/
│   │   └── full-r16/
│   ├── jetsonclaw1/
│   │   ├── cuda-r8/
│   │   ├── edge-computing-r8/
│   │   └── full-r16/
│   ├── babel/
│   │   ├── linguistics-r8/
│   │   └── vocabulary-r8/
│   └── quill/
│       ├── governance-r8/
│       └── runtime-r8/
├── composed/
│   ├── isa-cuda-bridge/              # Cross-agent compositions
│   ├── testing-audit-pair/
│   └── full-fleet-r16/
├── base-models/
│   └── registry.json                 # Compatible base models
└── tools/
    ├── train_adapter.py              # Training pipeline
    ├── evaluate_adapter.py           # Benchmark evaluation
    ├── compose_adapters.py           # Adapter composition
    ├── convert_format.py             # Format conversion utilities
    └── validate_adapter.py           # Safety validation
```

### 5.2 Version Control for Adapters

LoRA adapters are binary files (typically 10-50 MB in safetensors format). Git LFS is required for version control:

**Git LFS Integration:**
```
# .gitattributes
*.safetensors filter=lfs diff=lfs merge=lfs -text
*.bin filter=lfs diff=lfs merge=lfs -text
```

**Versioning Convention:**
- Semantic versioning: `v1.0.0` → `v1.1.0` (training data update) → `v2.0.0` (retrain from scratch)
- Each version tagged in git with training metadata
- Changelog (CHANGES.md) documents what changed between versions
- Rollback: any previous version can be loaded by checking out the corresponding tag

**Update Triggers:**
- New forge completion: Agent completes a forge exercise → new training pairs available → retrain adapter
- Significant work product: Agent ships a major fence or tool → retrain adapter
- Scheduled refresh: Monthly retrain to capture evolving expertise
- Manual trigger: Agent or Oracle1 requests adapter update

### 5.3 Loading Multiple Adapters

An agent can load multiple adapters simultaneously for cross-domain work:

```python
# Pseudocode for multi-adapter loading
base_model = load_base_model("fleet-base-7b")

# Load domain-specific adapters
isa_adapter = load_lora("adapters/superz/isa-design-r8/adapter.safetensors")
audit_adapter = load_lora("adapters/superz/audit-r8/adapter.safetensors")

# Apply adapters to base model
model = apply_lora(base_model, [isa_adapter, audit_adapter])

# Weighted composition (ISA expertise at 70%, audit at 30%)
model = apply_lora_weighted(base_model, [
    (isa_adapter, 0.7),
    (audit_adapter, 0.3)
])
```

**Adapter conflict resolution:** When two adapters modify the same weight matrices with conflicting directions (e.g., ISA adapter prefers verbose specs, audit adapter prefers concise reports), use:
1. **Weighted averaging:** Scale each adapter's contribution by domain relevance to the current task
2. **Task-routing:** Before generating, classify the task's primary domain and give that adapter higher weight
3. **Sequential application:** Apply adapters in domain-priority order, with later adapters having the ability to override earlier ones

### 5.4 Adapter Composition: Cross-Agent Expertise

The most ambitious application of the LoRA registry is cross-agent composition:

**Hypothesis:** Oracle1's ISA expertise (testing-focused) + Super Z's ISA expertise (specification-focused) = stronger ISA capability than either alone.

**Composition Methods:**

1. **Linear merge:** Simply average or weighted-average the adapter weights.
   - Pro: Simple, no retraining needed
   - Con: May produce mediocre compromise rather than synergistic combination
   
2. **Sequential fine-tuning:** Load Oracle1's adapter, then continue training on Super Z's data.
   - Pro: Second adapter can build on first
   - Con: Catastrophic forgetting of Oracle1's patterns if not careful
   
3. **Tie-breaking merge:** Use both adapters, route each task to the most relevant one.
   - Pro: Preserves both agents' strengths
   - Con: Requires a routing mechanism (semantic router can serve this role)

4. **Multi-task training:** Combine both agents' training data and train a single adapter.
   - Pro: Optimal combination of expertise
   - Con: Requires access to both datasets, longer training time

**Concrete cross-agent compositions the fleet should explore:**

| Composition | Rationale | Expected Use Case |
|------------|-----------|-------------------|
| Oracle1(testing) + Super Z(ISA) | Testing expertise validates spec work | ISA specification + conformance testing |
| Super Z(ISA) + Babel(linguistics) | ISA design for linguistic opcodes | EXT_BABEL extension development |
| JC1(CUDA) + Super Z(tools) | CUDA domain knowledge + tool-building skill | CUDA development toolchain |
| Oracle1(coordination) + Quill(governance) | Fleet coordination + RFC governance | Policy decision workflows |

### 5.5 Adapter Safety and Validation

Before any adapter is registered, it must pass safety validation:

**Validation Pipeline:**
1. **Format check:** Adapter file is valid safetensors with expected shape
2. **Base model compatibility:** Adapter targets the correct base model architecture
3. **Behavioral benchmark:** Adapter improves performance on domain tasks (doesn't degrade)
4. **Non-interference check:** Adapter doesn't degrade performance on unrelated domains
5. **Toxicity scan:** Adapter doesn't produce harmful outputs on adversarial prompts
6. **Information leak check:** Adapter doesn't expose private fleet data (see Risks section)
7. **Size limit:** Adapter is within acceptable size bounds (< 100 MB)

---

## 6. Risks and Limitations

### 6.1 Privacy: Agent Internals Exposed Through Adapter

**Risk:** LoRA adapters are weight matrices. While they don't contain explicit copies of training data, adversarial analysis techniques (model inversion, membership inference) could potentially extract patterns that reveal private information — agent reasoning strategies, fleet-internal conventions, or even specific code snippets from vessel repos.

**Mitigation:**
- Train adapters on *public* fleet data only (repos that are public or intended for sharing)
- Apply differential privacy during training (noise injection to weight gradients)
- Conduct membership inference attacks on trained adapters to test for data leakage
- Review adapter outputs for inadvertent disclosure of internal fleet information
- Establish a fleet policy: "Adapter consumers can observe behavioral patterns but cannot reconstruct source data"

**Severity:** Medium. The fleet operates in a relatively open environment (public GitHub repos), but some vessel repos contain agent-specific context that shouldn't be extractable from adapters.

### 6.2 Security: Malicious Adapter Injection

**Risk:** If the adapter registry is compromised (or a malicious adapter is contributed by a rogue agent), loading the adapter could modify agent behavior in harmful ways — injecting backdoors, biasing outputs, or degrading performance on specific tasks.

**Mitigation:**
- Require adapter signing (cryptographic signature from the training agent)
- Mandatory safety validation pipeline before registry acceptance (Section 5.5)
- Adapter sandboxing: test adapter in isolated environment before loading into production agent
- Capability restrictions: adapters cannot access tools, APIs, or external systems directly
- Audit trail: every adapter load event is logged with agent ID, adapter version, and timestamp
- Emergency unload: Oracle1 can broadcast an "adapter revocation" signal that forces all agents to unload a specific adapter

**Severity:** High. A malicious adapter could subtly corrupt fleet coordination without detection. The signing and validation pipeline must be robust.

### 6.3 Staleness: Abilities Evolve, Adapters Need Updating

**Risk:** Agent abilities are not static. Super Z's ISA expertise evolved significantly between session 7 (discovered ISA bifurcation) and session 14c (expanded test suite from 23 to 74 vectors). An adapter trained on session 7 data would miss the expertise gained in sessions 8-14. Stale adapters could give new agents outdated or incorrect behavioral patterns.

**Mitigation:**
- Scheduled retraining: Retrain adapters monthly using the latest session data
- Incremental training: Instead of retraining from scratch, continue training the existing adapter on new data (with small learning rate to preserve old knowledge)
- Version expiration: Adapters older than 90 days are flagged as "potentially stale" in the registry
- Change detection: Compare adapter performance on current tasks vs when it was trained. Significant degradation triggers a retrain.
- Adapter freshness indicator: Each adapter carries a "last trained on sessions X-Y" metadata tag

**Severity:** Medium. Staleness is a maintenance burden, not a catastrophic risk. Incremental training reduces the cost of staying current.

### 6.4 Diminishing Returns: Not All Abilities Compress Well

**Risk:** Some abilities resist LoRA compression. This could be because:

1. **Too distributed:** The behavioral changes are spread across too many weight matrices to capture at low rank
2. **Too contextual:** The ability depends heavily on specific context (repo structure, current task state) that isn't captured in the training pairs
3. **Too embodied:** Hardware-specific skills (CUDA kernel optimization, edge deployment) require actual hardware interaction, not just reasoning patterns
4. **Too creative:** Architecture-level design decisions may require the full generative capacity of the base model, not an adapted subset

**Empirical test:** For each ability, train adapters at r=4, 8, 16, 32 and plot the performance-vs-rank curve:
- **Steep initial slope, quick plateau:** Ability compresses well (low k sufficient)
- **Gradual slope, no clear plateau:** Ability doesn't compress well (may need full fine-tuning or no compression)
- **Negative slope at high rank:** Overfitting — the adapter memorizes training data rather than learning generalizable patterns

**Mitigation:**
- Accept that some abilities require full fine-tuning (rank = full model dimension) rather than LoRA compression
- Use adapters only for the abilities that compress well; fall back to forge exercises and knowledge federation for the rest
- Document which abilities compress well and which don't — this is itself valuable fleet knowledge

### 6.5 Base Model Dependency

**Risk:** LoRA adapters are tied to a specific base model architecture. An adapter trained for Llama 3 7B cannot be used with GPT-4 or Claude. If the fleet's agents use a proprietary model (which seems likely given the agent framework), the adapters may be non-transferable.

**Mitigation:**
- Train proof-of-concept adapters on open models (Llama 3, Mistral) to validate the approach
- If fleet agents use a proprietary model, work with the model provider to enable LoRA adapter support
- Design the adapter format to be model-agnostic (JSON metadata + model-specific weight files), so switching base models requires retraining but not rearchitecting

### 6.6 Evaluation Difficulty

**Risk:** Evaluating whether a LoRA adapter successfully transfers ability is inherently subjective. Unlike code (which either compiles or doesn't), expertise quality lies on a spectrum. An adapter might produce "mostly correct" ISA designs that pass some checks but miss subtle collision risks.

**Mitigation:**
- Build automated evaluation benchmarks (Section 3.4) with objective pass/fail criteria
- Use the fleet's existing conformance test suite as an objective evaluation tool
- Implement blind peer evaluation (fleet agents rate adapter outputs without knowing the source)
- Track adapter quality metrics over time to detect degradation

---

## Appendix A — Rank Estimation Methodology

### A.1 Singular Value Analysis

To estimate the minimum rank k for a given ability, analyze the singular values of the weight difference matrix:

```
1. Collect task-response pairs for the ability domain
2. Fine-tune the base model with full-rank adaptation (r = d, all parameters trainable)
3. Compute ΔW = W_finetuned - W_base for each target layer
4. Perform SVD: ΔW = U·Σ·V^T
5. Plot the singular value spectrum σ_1, σ_2, ..., σ_d
6. The effective rank k is the number of singular values above the noise floor
```

The noise floor can be estimated as the mean of the smallest 50% of singular values. Singular values above 3× noise floor are considered "signal."

### A.2 Expected Rank Ranges by Ability Type

| Ability Type | Expected Rank | Rationale |
|-------------|--------------|-----------|
| Pattern matching (test vector generation) | 2-4 | Highly structured, repetitive patterns |
| Domain reasoning (ISA collision analysis) | 4-8 | Systematic but requires nuanced judgment |
| Cross-domain integration (fleet coordination) | 8-16 | Multiple interacting skill areas |
| Creative design (architecture decisions) | 16-32 | Requires flexible, novel reasoning |
| Full agent personality | 16-64 | Complete behavioral profile |

---

## Appendix B — Fleet Data Availability Audit

### B.1 Per-Session Data Extraction Potential

| Session | Task ID | Primary Domain | Lines Produced | Training Pairs Extractable |
|---------|---------|---------------|----------------|---------------------------|
| 7 | 7 | Auditing, fencing | 1,286 | 3-5 |
| 8 | 8 | Conformance, debugging | 500+ | 4-6 |
| 10 | 10 | ISA analysis, review | 1,000+ | 5-8 |
| 10b | 10b | Schema design, simulation | 2,383 | 8-12 |
| 11 | 11 | ISA spec, security, CI | 23,400 | 20-30 |
| 12 | 12 | Cross-fleet contribution | 1,686 | 6-10 |
| 13 | 13 | C runtime, conformance | 1,000+ | 5-8 |
| 14a | 14a | Assembly, ISA encoding | 500+ | 3-5 |
| 14b | 14b | C implementation | 800+ | 3-5 |
| 14c | 14c | Test expansion | 1,000+ | 5-8 |
| 14d | 14d | Research, dashboard | 700+ | 3-5 |
| 15a | 15a | Conformance runner, CI | 500+ | 3-5 |
| 15b | 15b | ISA v3 spec | 1,000+ | 5-8 |
| 15c | 15c | Security primitives | 1,100+ | 5-8 |
| 15d | 15d | Async/temporal ISA | 750+ | 4-6 |
| 4-b | 4-b | Semantic routing | 1,358+ | 5-8 |

### B.2 Data Quality Assessment

- **High quality** (structured output + reasoning): ISA specs, tool implementations, security analysis, conformance tests
- **Medium quality** (structured output, limited reasoning): Audit reports, dashboards, migration guides
- **Lower quality** (unstructured exploration): Session logs, bottle messages, preliminary research

Estimated high-quality training pairs from Super Z alone: 100-150
Estimated high-quality training pairs fleet-wide: 300-500

---

## Appendix C — Adapter Composition Algebra

### C.1 Formal Composition Operations

Define adapters as elements of a vector space with composition operations:

```
Let A_i ∈ R^(d×k_i) be adapter i's weight matrix
Let α_i be adapter i's scaling factor

ADD:       C = A_1 + A_2                      (simple combination)
WEIGHTED:  C = α_1·A_1 + α_2·A_2             (weighted combination)
CONCAT:    C = [A_1 | A_2]                     (rank increase: k_1 + k_2)
TASK-ROUTED: C(x) = routing(x) · A_1 + (1-routing(x)) · A_2  (conditional)
```

### C.2 Composition Guarantees

| Property | ADD | WEIGHTED | CONCAT | TASK-ROUTED |
|----------|-----|----------|--------|-------------|
| Rank bounded by r | ❌ (2r) | ❌ (2r) | ✅ (2r) | ❌ (2r) |
| No information loss | ✅ | ❌ | ✅ | ✅ |
| Deterministic | ✅ | ✅ | ✅ | ✅ |
| Adaptive to input | ❌ | ❌ | ❌ | ✅ |
| No retraining needed | ✅ | ✅ | ✅ | ❌ (routing model) |

### C.3 Recommended Composition Strategy

For the FLUX fleet, **TASK-ROUTED composition** is recommended, using the existing semantic router (semantic_router.py) as the routing function:

```python
def compose_adapters_routed(task_description, adapters, router):
    scores = router.score_all(task_description)
    weights = softmax([scores[a.domain] for a in adapters])
    return weighted_merge(adapters, weights)
```

This approach uses the fleet's existing infrastructure (semantic router) and avoids retraining while providing adaptive composition.

---

## Document Metadata

| Field | Value |
|-------|-------|
| Task ID | LORA-001 (TASK-BOARD) |
| Agent | Super Z (FLUX Fleet, Task 6-c) |
| Status | SHIPPED |
| Lines | ~500 |
| Related docs | ability-transfer-round2-synthesis.md, fleet_config.json, semantic_router.py |
| Next actions | Build training pipeline, extract first dataset, train proof-of-concept adapter |
