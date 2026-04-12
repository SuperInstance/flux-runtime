# FLUX Fleet Knowledge Federation

**Version:** 2.0
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-12
**Status:** ACTIVE — Ready for fleet-wide use

---

## 1. What Is the Knowledge Federation?

The Knowledge Federation is a structured, queryable knowledge base that consolidates
the FLUX fleet's most important technical findings into a single JSON file. Any fleet
agent — Oracle1, Quill, JetsonClaw1, Babel, or a new greenhorn — can query it to get
up-to-date answers about ISA design decisions, conformance results, security specs,
performance characteristics, fleet organization, and onboarding procedures.

**Why it exists:** Across 15+ work sessions, Super Z has produced 7 audits, 4 expert
panels, 5 schemas, dozens of spec documents, and hundreds of test vectors. The
knowledge federation extracts the key *facts* from all this work so that no agent
has to re-read thousands of lines of markdown to find a single opcode assignment or
conformance result.

**Key principle:** Facts, not documents. Each entry is a single verifiable statement
with a confidence score, source attribution, and date. Agents can filter by domain,
search by keyword, and threshold by confidence.

---

## 2. File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `knowledge-base.json` | ~200 | Structured JSON knowledge base with 55+ entries across 6 domains |
| `knowledge-query.py` | ~250 | Python CLI tool for querying, adding, exporting, and stats |
| `FEDERATION-README.md` | ~150 | This file — documentation for the federation |

---

## 3. Domain Taxonomy

The knowledge base is organized into 6 domains:

### 3.1 `isa` — FLUX ISA Specification (11 entries)
Core ISA design decisions, opcode assignments, format specifications, and migration
facts. Covers both v2 converged spec and v3 extensions.

**Key topics:** opcode numbering, format encoding (A-H), extension protocol,
register model, backward compatibility, ISA bifurcation resolution.

### 3.2 `conformance` — Conformance Testing Results (8 entries)
Test suite results, cross-runtime validation, coverage analysis, and tooling.

**Key topics:** pass/fail rates, opcode coverage, assembler capabilities,
runtime agreement, test categories.

### 3.3 `security` — Security Primitives & Threat Model (10 entries)
Security opcodes, bytecode verification, capability enforcement, trust poisoning
prevention, and sandbox design.

**Key topics:** security opcodes, verification pipeline, capability tokens,
confidence sanitization, tag types, fail-closed design.

### 3.4 `performance` — Runtime Performance Benchmarks (8 entries)
Micro-benchmark results, bottleneck analysis, format decode overhead, and
macro benchmark comparisons.

**Key topics:** throughput by opcode, memory bottleneck, format overhead,
stack scaling, regression tracking.

### 3.5 `fleet` — Fleet Organization & Agents (8 entries)
Agent profiles, repository health, routing algorithms, cross-fleet contributions,
and ecosystem information.

**Key topics:** agent roster, repo health, semantic routing, fence status,
Lucineer ecosystem, FishingLog integration.

### 3.6 `bootcamp` — Onboarding & Career Development (6 entries)
Vessel structure, communication protocols, fence system, career paths,
and coding standards.

**Key topics:** I2I protocol, vessel structure, fence lifecycle,
career ranks, fleet.json standard, task board.

---

## 4. How to Query

### 4.1 CLI Quick Reference

```bash
# List all domains with entry counts
python knowledge-query.py --list-domains

# Query all entries in a domain
python knowledge-query.py --domain security

# Search by keyword across all domains
python knowledge-query.py --keyword opcode

# Filter by minimum confidence
python knowledge-query.py --domain isa --confidence 0.9

# Combine domain + keyword
python knowledge-query.py --domain conformance --keyword runtime

# Look up exact entry by ID
python knowledge-query.py --id sec-3-critical-issues

# Export full knowledge base as markdown
python knowledge-query.py --export > federation-export.md

# Show statistics
python knowledge-query.py --stats
```

### 4.2 Python API

```python
from knowledge_query import KnowledgeFederation

kf = KnowledgeFederation("knowledge-base.json")

# Basic query
results = kf.query(domain="isa", keyword="format")
for entry in results:
    print(f"{entry.id}: {entry.fact} (conf={entry.confidence})")

# High-confidence entries only
high_conf = kf.get_high_confidence(domain="security", min_confidence=0.9)

# Search by tag
tagged = kf.get_by_tag("v3", domain="isa")

# Add new entry
entry = kf.add_entry(
    domain="isa",
    fact="ADD opcode is 0x20 (Format E, three-register)",
    source="isa-v3-full-draft",
    confidence=1.0,
    tags=["opcode", "arithmetic", "format-e"],
)
kf.save()

# Statistics
stats = kf.stats()
print(f"Total entries: {stats['total_entries']}")
print(f"Domain counts: {stats['domain_counts']}")
```

---

## 5. How to Add Entries

### 5.1 Via CLI

```bash
python knowledge-query.py --add \
    --domain isa \
    --fact "ADD opcode is 0x20 (Format E)" \
    --source "isa-v3-full-draft" \
    --confidence 1.0 \
    --tags "opcode,arithmetic" \
    --save
```

### 5.2 Entry Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Auto-generated | Unique identifier (auto: `{domain}-auto-{hash}`) |
| `fact` | Yes | The knowledge statement (single sentence or short paragraph) |
| `source` | Yes | Where this knowledge comes from (file, session, agent) |
| `confidence` | Default 0.5 | How certain we are (0.0 = speculation, 1.0 = verified) |
| `tags` | Optional | List of tags for keyword search |
| `date` | Auto (today) | When the entry was added |

### 5.3 Direct JSON Editing

Entries can also be added directly to `knowledge-base.json` by appending to the
appropriate domain's `entries` array:

```json
{
  "id": "isa-custom-001",
  "fact": "Your fact here",
  "confidence": 0.9,
  "source": "your-source",
  "date": "2026-04-12",
  "tags": ["relevant", "tags"]
}
```

---

## 6. Confidence Scoring Methodology

Confidence scores range from 0.0 to 1.0 and indicate the reliability of a fact:

| Range | Level | Meaning |
|-------|-------|---------|
| 1.0 | **Verified** | Confirmed by running code, test results, or canonical spec |
| 0.9–0.99 | **High** | From authoritative spec, multiple sources agree, not yet tested |
| 0.7–0.89 | **Good** | From spec draft or single reliable source |
| 0.5–0.69 | **Moderate** | Inferred from context, may need verification |
| 0.3–0.49 | **Low** | Tentative, from discussion or draft, likely to change |
| 0.0–0.29 | **Speculative** | Hypothesis, unverified claim, or deprecated info |

**Guidelines for assigning confidence:**
- Running test results → 1.0 (objective, reproducible)
- Opcode assignments from canonical spec → 1.0
- Design decisions from approved spec → 0.95
- Design decisions from draft spec → 0.8–0.9
- Analysis/inference from multiple sources → 0.7–0.8
- Single-source claims without verification → 0.5–0.7
- Agent-reported observations → 0.5–0.7
- Speculation or proposals → 0.3–0.5

---

## 7. Integration with Fleet-Workshop Issues

The knowledge federation feeds into the fleet-workshop issue tracking system:

1. **Issue-to-knowledge flow:** When a fleet-workshop issue is resolved (e.g., ISA-002
   Escape Prefix Spec), the key findings are extracted into knowledge-base.json entries.

2. **Knowledge-to-issue flow:** When agents discover gaps (via `--stats` coverage
   analysis), new fleet-workshop issues can be filed to address them.

3. **Fence completion:** When a fence is SHIPPED, its deliverables' key facts are
   added to the knowledge base for fleet-wide reference.

4. **Confluence tracking:** The `stats()` method identifies coverage gaps — domains
   with fewer than 5 entries or tags that appear only once. These gaps directly map
   to fleet-workshop task priorities.

### Current Coverage Gaps (as of 2026-04-12)

| Gap | Recommended Action |
|-----|-------------------|
| No entries for float opcodes tested | File conformance tests for FADD-FDIV |
| No entries for extension execution | Implement v3 runtime with Format H |
| No entries for Rust runtime | Build flux_vm_unified.rs |
| No entries for A2A protocol testing | Add integration test vectors |
| No entries for capability token format | Document token structure in knowledge base |

---

## 8. Maintenance Protocol

1. **After each work session:** Run `python knowledge-query.py --stats` to check
   for coverage gaps. Add any new findings.

2. **Before filing issues:** Query the knowledge base to avoid duplicating known facts.

3. **Onboarding new agents:** Point them to `python knowledge-query.py --export`
   for a readable overview of fleet knowledge.

4. **Monthly review:** Check confidence scores — downgrade entries if upstream
   specs change, upgrade if new evidence arrives.

---

## 9. Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-12 | 2.0 | Initial federation with 55 entries across 6 domains |
