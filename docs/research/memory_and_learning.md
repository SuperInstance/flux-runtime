# Persistent Memory, Learning & Generalization

**FLUX Research Memo #003** | Persistent Memory, Experience Generalization, Meta-Learning, and Strategic Forgetting for the FLUX Self-Evolution Runtime

**Status:** Research & Design | **Date:** 2025-07-14 | **Audience:** Core contributors

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Cross-Session Memory Architecture](#2-cross-session-memory-architecture)
3. [Experience Generalization](#3-experience-generalization)
4. [Learned Tile Library](#4-learned-tile-library)
5. [Meta-Learning: Learning to Learn Better](#5-meta-learning-learning-to-learn-better)
6. [Strategic Forgetting](#6-strategic-forgetting)
7. [Open Research Questions](#7-open-research-questions)

---

## 1. Executive Summary

FLUX already possesses the foundational machinery for a self-improving runtime: a **Genome** that snapshots the full system state (modules, tiles, language assignments, profiler data), an **EvolutionEngine** that runs a 9-step improvement cycle (capture, profile, mine, propose, evaluate, commit, measure, record, repeat), a **PatternMiner** that discovers hot execution subsequences using a modified Apriori algorithm, and a **SystemMutator** that applies and validates mutations with rollback safety.

However, all of this state is currently **ephemeral**. When the Python process exits, every discovered pattern, every successful mutation, every learned tile is lost. This document designs the architecture for making FLUX's learning persistent, generalizable, and self-optimizing -- turning it from a system that *can* evolve within a session into one that *accumulates wisdom across sessions*.

The core insight is that FLUX's evolution artifacts can be categorized into four tiers of persistence:

| Tier | Artifact | Volatility | Serialization Strategy |
|------|----------|------------|----------------------|
| **Hot** | Profiler call counts, active traces | Milliseconds to seconds | In-memory only, never serialized |
| **Warm** | Genome snapshots, evolution history, mutation records | Session-lifetime | Append-only WAL (write-ahead log), flushed periodically |
| **Cold** | Discovered patterns, learned tile definitions, generalization rules | Days to months | Structured database (SQLite), versioned exports |
| **Frozen** | Proven optimization rules, domain vocabularies, cross-system tile libraries | Permanent | Git-versioned JSON/YAML, importable packages |

---

## 2. Cross-Session Memory Architecture

### 2.1 Current State Analysis

The `Genome` class (`src/flux/evolution/genome.py`) already implements `to_dict()` / `from_dict()` serialization -- but these are never called outside of tests. The genome captures:

- **ModuleSnapshots**: path, granularity, language, version, checksum, heat_level, call_count, total_time_ns
- **TileSnapshots**: name, tile_type, input/output counts, cost_estimate, abstraction_level, language_preference, tags, param_count
- **LanguageAssignments**: `{module_path: language}` mapping
- **ProfilerSnapshot**: module_count, sample_count, heatmap, ranking, total_time_ns
- **OptimizationHistory**: list of OptimizationRecord with generation, mutation_type, target, description, success, speedup, timestamp
- **Fitness metadata**: fitness_score, generation, checksum

The `EvolutionEngine` stores `EvolutionRecord` objects in `self._history`, and the `SystemMutator` stores `MutationRecord` objects in `self._mutations_applied` / `self._mutations_failed`. Neither is serialized. The `PatternMiner` stores traces in `self._trace_log` and patterns in `self._patterns`, both purely in-memory.

### 2.2 Proposed Persistent Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FLUX Memory System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐   ┌──────────────────┐                    │
│  │   HOT LAYER      │   │   WARM LAYER     │                    │
│  │   (in-memory)    │──▶│   (WAL + SQLite) │                    │
│  │                  │   │                  │                    │
│  │  • Profiler      │   │  • Genome chain  │                    │
│  │    counters      │   │  • Evolution     │                    │
│  │  • Active traces │   │    records       │                    │
│  │  • Mutation      │   │  • Mutation      │                    │
│  │    proposals     │   │    records       │                    │
│  │  • JIT cache     │   │  • Pattern       │                    │
│  │                  │   │    log           │                    │
│  └──────────────────┘   └───────┬──────────┘                    │
│                                  │                               │
│  ┌───────────────────────────────▼──────────────────────────┐    │
│  │                   COLD LAYER (SQLite + filesystem)        │    │
│  │                                                          │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐  │    │
│  │  │ genomes      │ │ patterns     │ │ learned_tiles    │  │    │
│  │  │ table        │ │ table        │ │ table            │  │    │
│  │  │              │ │              │ │                  │  │    │
│  │  │ gen_id PK    │ │ pattern_id   │ │ tile_id PK       │  │    │
│  │  │ checkpoint   │ │ PK           │ │ name             │  │    │
│  │  │ (JSON blob)  │ │ sequence     │ │ tile_type        │  │    │
│  │  │ fitness      │ │ (JSON arr)   │ │ cost_estimate    │  │    │
│  │  │ generation   │ │ frequency    │ │ abstraction_lvl  │  │    │
│  │  │ timestamp    │ │ speedup      │ │ source_modules   │  │    │
│  │  │ checksum     │ │ confidence   │ │ fir_blueprint    │  │    │
│  │  └──────────────┘ │ domain_tag   │ │ tags (JSON)      │  │    │
│  │                   │ avg_dur_ns   │ │ created_at       │  │    │
│  │  ┌──────────────┐ │ provenance  │ │ usage_count      │  │    │
│  │  │ evolution    │ └──────────────┘ │ success_rate     │  │    │
│  │  │ history      │                  └──────────────────┘  │    │
│  │  │              │ ┌──────────────────────────────────┐   │    │
│  │  │ record_id PK │ │ generalization_rules              │   │    │
│  │  │ gen_id FK    │ │                                    │   │    │
│  │  │ fitness_bef  │ │ rule_id PK                        │   │    │
│  │  │ fitness_aft  │ │ pattern_sig (abstracted)          │   │    │
│  │  │ mutations_n  │ │ concrete_applications (JSON arr)  │   │    │
│  │  │ success_rate │ │ success_rate                      │   │    │
│  │  │ elapsed_ns   │ │ applicability_scope              │   │    │
│  │  │ timestamp    │ │ confidence                       │   │    │
│  │  └──────────────┘ │ created_at                        │   │    │
│  │                   └──────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   FROZEN LAYER (versioned files)         │    │
│  │                                                          │    │
│  │  ~/.flux/                                                │    │
│  │  ├── genomes/           # Git-versioned genome snapshots │    │
│  │  │   ├── v001.json      # Genome at generation 1        │    │
│  │  │   ├── v042.json      # Genome at generation 42       │    │
│  │  │   └── LATEST.json    # Symlink to latest             │    │
│  │  ├── tiles/             # Learned tile library           │    │
│  │  │   ├── evolved/       # Auto-discovered tiles          │    │
│  │  │   │   ├── flatmap_filter.json                        │    │
│  │  │   │   └── map_reduce_fused.json                      │    │
│  │  │   └── imported/      # Cross-system imports           │    │
│  │  │       └── vendor_data_pipeline.json                  │    │
│  │  ├── generalizations/   # Proven optimization rules      │    │
│  │  │   ├── fuse_map_filter.rule                           │    │
│  │  │   └── recompile_heat_c_simd.rule                      │    │
│  │  └── meta/              # Meta-learning state            │    │
│  │       ├── strategy_performance.json                      │    │
│  │       └── hyperparams.json                               │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Concrete Data Structures

#### MemoryStore: The Unified Persistence Interface

```python
@dataclass
class MemoryConfig:
    """Configuration for the FLUX memory system."""
    wal_path: str = "~/.flux/wal.log"
    db_path: str = "~/.flux/flux_memory.db"
    frozen_path: str = "~/.flux"
    flush_interval_secs: float = 5.0
    max_genomes_in_db: int = 1000
    max_patterns_in_db: int = 10000
    checkpoint_every_n_generations: int = 10
    enable_git_versioning: bool = False

class MemoryStore:
    """Unified persistent memory for FLUX evolution artifacts.

    Manages three layers:
    - HOT: In-memory caches (profiler, traces, JIT)
    - WARM: SQLite database (genomes, patterns, mutations)
    - FROZEN: Filesystem exports (versioned snapshots, tile libraries)

    Design principle: write-heavy workloads go to the WAL (append-only),
    read-heavy workloads query SQLite directly. Frozen layer is for
    human-inspectable exports and cross-system sharing.
    """

    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or MemoryConfig()
        self._db: sqlite3.Connection | None = None
        self._wal_buffer: list[bytes] = []
        self._flush_timer: threading.Timer | None = None
        self._dirty: set[str] = set()  # dirty table names

    # ── WAL Operations ──────────────────────────────────────────
    def _wal_append(self, table: str, operation: str, data: dict) -> None:
        """Append an operation to the write-ahead log."""
        entry = json.dumps({
            "ts": time.time_ns(),
            "table": table,
            "op": operation,  # "INSERT", "UPDATE", "DELETE"
            "data": data,
        }).encode("utf-8")
        self._wal_buffer.append(struct.pack("<I", len(entry)) + entry)
        if len(self._wal_buffer) >= 100:
            self._flush_wal()

    def _flush_wal(self) -> None:
        """Flush WAL buffer to disk."""
        if not self._wal_buffer:
            return
        with open(self.config.wal_path, "ab") as f:
            for entry in self._wal_buffer:
                f.write(entry)
        self._wal_buffer.clear()

    # ── Genome Persistence ──────────────────────────────────────
    def save_genome(self, genome: Genome) -> int:
        """Save a genome snapshot. Returns genome_id."""
        self._ensure_schema()
        data = genome.to_dict()
        cursor = self._db.execute("""
            INSERT INTO genomes (checksum, generation, fitness_score,
                                 snapshot_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            genome.checksum,
            genome.generation,
            genome.fitness_score,
            json.dumps(data),
            time.time(),
        ))
        self._db.commit()
        self._wal_append("genomes", "INSERT", {
            "gen_id": cursor.lastrowid,
            "checksum": genome.checksum,
            "generation": genome.generation,
        })
        return cursor.lastrowid

    def load_latest_genome(self) -> Genome | None:
        """Load the most recent genome from the database."""
        self._ensure_schema()
        row = self._db.execute("""
            SELECT snapshot_json FROM genomes
            ORDER BY generation DESC LIMIT 1
        """).fetchone()
        if row:
            return Genome.from_dict(json.loads(row[0]))
        return None

    def get_genome_lineage(self, genome_id: int) -> list[Genome]:
        """Get the full lineage of genomes leading to this one."""
        # ... query ancestors by generation ordering
        pass

    # ── Pattern Persistence ─────────────────────────────────────
    def save_patterns(self, patterns: list[DiscoveredPattern]) -> int:
        """Batch-save discovered patterns."""
        self._ensure_schema()
        count = 0
        for p in patterns:
            self._db.execute("""
                INSERT OR REPLACE INTO patterns
                    (sequence_hash, sequence, frequency, total_occurrences,
                     avg_duration_ns, estimated_speedup, confidence,
                     domain_tag, provenance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                hashlib.sha256(str(p.sequence).encode()).hexdigest()[:16],
                json.dumps(p.sequence),
                p.frequency,
                p.total_occurrences,
                p.avg_duration_ns,
                p.estimated_speedup,
                p.confidence,
                self._infer_domain(p.sequence),
                "evolution",
            ))
            count += 1
        self._db.commit()
        return count

    # ── Learned Tile Persistence ────────────────────────────────
    def save_learned_tile(self, tile: TileSnapshot,
                          source_pattern: DiscoveredPattern,
                          fir_blueprint: str) -> int:
        """Save a tile that was learned from pattern mining."""
        self._ensure_schema()
        cursor = self._db.execute("""
            INSERT INTO learned_tiles
                (name, tile_type, cost_estimate, abstraction_level,
                 source_modules, fir_blueprint, tags,
                 usage_count, success_rate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1.0, ?)
        """, (
            tile.name,
            tile.tile_type,
            tile.cost_estimate,
            tile.abstraction_level,
            json.dumps(list(source_pattern.sequence)),
            fir_blueprint,
            json.dumps(list(tile.tags)),
            time.time(),
        ))
        self._db.commit()
        return cursor.lastrowid

    def load_learned_tiles(self) -> list[dict]:
        """Load all learned tiles for registration at startup."""
        self._ensure_schema()
        rows = self._db.execute("""
            SELECT name, tile_type, cost_estimate, abstraction_level,
                   source_modules, fir_blueprint, tags,
                   usage_count, success_rate
            FROM learned_tiles
            WHERE success_rate >= 0.5
            ORDER BY usage_count DESC
        """).fetchall()
        return [
            {
                "name": r[0], "tile_type": r[1],
                "cost_estimate": r[2], "abstraction_level": r[3],
                "source_modules": json.loads(r[4]),
                "fir_blueprint": r[5], "tags": json.loads(r[6]),
                "usage_count": r[7], "success_rate": r[8],
            }
            for r in rows
        ]
```

#### Schema Definition

```sql
-- FLUX Persistent Memory Schema (SQLite)

CREATE TABLE IF NOT EXISTS genomes (
    genome_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    checksum      TEXT NOT NULL,
    generation    INTEGER NOT NULL,
    fitness_score REAL NOT NULL DEFAULT 0.0,
    snapshot_json TEXT NOT NULL,           -- full Genome.to_dict() JSON
    timestamp     REAL NOT NULL,           -- Unix epoch seconds
    parent_id     INTEGER REFERENCES genomes(genome_id),
    UNIQUE(checksum, generation)
);
CREATE INDEX idx_genomes_gen ON genomes(generation);
CREATE INDEX idx_genomes_fit ON genomes(fitness_score DESC);

CREATE TABLE IF NOT EXISTS evolution_history (
    record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    genome_id       INTEGER REFERENCES genomes(genome_id),
    generation      INTEGER NOT NULL,
    fitness_before  REAL NOT NULL,
    fitness_after   REAL NOT NULL,
    fitness_delta   REAL NOT NULL,
    mutations_proposed INTEGER DEFAULT 0,
    mutations_committed INTEGER DEFAULT 0,
    mutations_failed   INTEGER DEFAULT 0,
    patterns_found     INTEGER DEFAULT 0,
    elapsed_ns         INTEGER DEFAULT 0,
    timestamp     REAL NOT NULL
);
CREATE INDEX idx_evo_gen ON evolution_history(generation);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_hash    TEXT NOT NULL UNIQUE,   -- SHA-256 of sequence
    sequence         TEXT NOT NULL,           -- JSON array of module paths
    frequency        INTEGER NOT NULL DEFAULT 0,
    total_occurrences INTEGER DEFAULT 0,
    avg_duration_ns  REAL DEFAULT 0.0,
    estimated_speedup REAL DEFAULT 1.0,
    confidence       REAL DEFAULT 0.0,
    domain_tag       TEXT DEFAULT '',         -- 'compute', 'a2a', 'control', etc.
    provenance       TEXT DEFAULT 'evolution', -- 'evolution', 'manual', 'imported'
    first_seen       REAL NOT NULL,
    last_seen        REAL NOT NULL
);
CREATE INDEX idx_pat_freq ON patterns(frequency DESC);
CREATE INDEX idx_pat_domain ON patterns(domain_tag);

CREATE TABLE IF NOT EXISTS learned_tiles (
    tile_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    tile_type        TEXT NOT NULL,
    cost_estimate    REAL NOT NULL DEFAULT 1.0,
    abstraction_level INTEGER DEFAULT 5,
    source_modules   TEXT,                    -- JSON array
    fir_blueprint    TEXT,                    -- FIR code template
    tags             TEXT DEFAULT '[]',       -- JSON array
    usage_count      INTEGER DEFAULT 0,
    success_count    INTEGER DEFAULT 0,
    failure_count    INTEGER DEFAULT 0,
    success_rate     REAL GENERATED ALWAYS AS (
        CASE WHEN (success_count + failure_count) > 0
             THEN CAST(success_count AS REAL) / (success_count + failure_count)
             ELSE 1.0 END
    ) STORED,
    created_at       REAL NOT NULL,
    last_used_at     REAL
);
CREATE INDEX idx_tiles_usage ON learned_tiles(usage_count DESC);

CREATE TABLE IF NOT EXISTS generalization_rules (
    rule_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_signature   TEXT NOT NULL,       -- Abstracted pattern form
    concrete_instances  TEXT NOT NULL,       -- JSON: list of {sequence, result}
    total_applications INTEGER DEFAULT 0,
    success_count       INTEGER DEFAULT 0,
    success_rate        REAL DEFAULT 0.0,
    applicability_scope TEXT DEFAULT '*',    -- Glob pattern for module paths
    confidence          REAL DEFAULT 0.0,
    created_at          REAL NOT NULL,
    last_applied_at     REAL
);

CREATE TABLE IF NOT EXISTS meta_state (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,                   -- JSON-serialized
    updated_at REAL NOT NULL
);
```

### 2.4 What Gets Serialized and Why

| Data | Serialized? | Format | Rationale |
|------|:-----------:|--------|-----------|
| Genome snapshot | Yes | JSON blob in SQLite | Full system state for rollback lineage |
| Evolution records | Yes | Structured rows | Historical analysis, convergence tracking |
| Profiler call counts | No | -- | Too volatile; reconstructed by running workloads |
| Active execution traces | No | -- | Session-specific; patterns are extracted before flush |
| Discovered patterns | Yes | Structured rows | Cross-session pattern matching |
| Learned tile definitions | Yes | Structured rows + JSON files | Core persistent vocabulary |
| JIT cache | No | -- | Reconstructible from FIR; too architecture-specific |
| Language assignments | Yes | Inside genome snapshot | Persistent optimization decisions |
| Mutation proposals | Partially | Only committed ones | Failed proposals are noise; only record successes/failures |
| Validation baselines | Yes | JSON | Prevents regression across sessions |

### 2.5 Startup Recovery Sequence

```python
class MemoryStore:
    def recover_session(self) -> SessionState:
        """Recover state from persistent memory on startup.

        1. Load latest genome → set as current Genome
        2. Load all learned tiles → register in TileRegistry
        3. Load generalization rules → prime the PatternMiner
        4. Load meta-learning state → configure EvolutionEngine
        5. Replay any uncommitted WAL entries
        """
        state = SessionState()

        # Step 1: Restore genome
        latest = self.load_latest_genome()
        if latest:
            state.genome = latest
            state.generation = latest.generation

        # Step 2: Restore learned tile library
        learned_tiles = self.load_learned_tiles()
        for tile_data in learned_tiles:
            state.learned_tiles.append(tile_data)

        # Step 3: Restore generalization rules
        rules = self.load_generalization_rules()
        state.generalizations = rules

        # Step 4: Restore meta-learning state
        meta = self.load_meta_state()
        state.mutation_strategy_weights = meta.get(
            "mutation_strategy_weights", {}
        )
        state.exploration_rate = meta.get("exploration_rate", 0.3)

        # Step 5: Replay WAL
        self._replay_wal()

        return state

    def _replay_wal(self) -> None:
        """Replay any uncommitted WAL entries into SQLite."""
        # Read WAL entries that haven't been checkpointed
        # Apply them in order to the database
        # Truncate the WAL
        pass
```

---

## 3. Experience Generalization

### 3.1 The Generalization Problem

The current `PatternMiner` discovers concrete patterns: specific sequences of specific module paths (e.g., `["data_pipeline.map", "data_pipeline.filter"]`). But the evolution engine has no mechanism to say: *"The last three times I fused a map+filter into a flatmap, I got a 1.4x speedup. I should try that pattern everywhere I see map followed by filter, regardless of the specific module names."*

This is the core generalization gap. We need to move from concrete pattern matching to **abstract pattern matching**.

### 3.2 Abstract Pattern Signatures

The key idea is to extract a *structural signature* from each discovered pattern that abstracts away specific module names while preserving the semantic structure:

```python
@dataclass
class AbstractPatternSignature:
    """An abstracted version of a concrete execution pattern.

    Instead of ["data_pipeline.map", "data_pipeline.filter", "data_pipeline.reduce"],
    this captures: [MAP, FILTER, REDUCE] with structural metadata.

    The abstraction works by:
    1. Extracting the tile_type from each module's name (suffix matching)
    2. Replacing specific module paths with their type category
    3. Recording the structural relationships (sequential, parallel, nested)
    4. Preserving cardinality hints (was this map over a list? a scalar?)
    """
    type_sequence: tuple[str, ...]     # e.g., ("COMPUTE:map", "COMPUTE:filter", "COMPUTE:reduce")
    type_fingerprint: str              # SHA-256 hash of type_sequence for fast lookup
    min_length: int
    max_length: int                    # same if fixed-length
    structural_hints: dict[str, Any]   # {"has_predicate": True, "is_chained": True}
    domain_hint: str                   # "compute", "memory", "a2a", "mixed"

    @classmethod
    def from_concrete_pattern(
        cls, pattern: DiscoveredPattern, tile_registry: TileRegistry
    ) -> AbstractPatternSignature:
        """Abstract a concrete pattern into its structural signature."""
        abstracted = []
        domain_counts: dict[str, int] = {}

        for module_path in pattern.sequence:
            # Extract the operation type from the module path
            # Convention: module_path ends with the operation name
            op_name = module_path.rsplit(".", 1)[-1].lower()

            # Try to match against known tile types
            matching_tiles = tile_registry.search(op_name)
            if matching_tiles:
                tile = matching_tiles[0]
                type_label = f"{tile.tile_type.value}:{op_name}"
                domain_counts[tile.tile_type.value] = (
                    domain_counts.get(tile.tile_type.value, 0) + 1
                )
            else:
                # Infer from naming convention
                if "loop" in op_name or "iter" in op_name:
                    type_label = f"CONTROL:{op_name}"
                    domain_counts["control"] = domain_counts.get("control", 0) + 1
                elif "load" in op_name or "store" in op_name or "mem" in op_name:
                    type_label = f"MEMORY:{op_name}"
                    domain_counts["memory"] = domain_counts.get("memory", 0) + 1
                elif "send" in op_name or "recv" in op_name or "tell" in op_name:
                    type_label = f"A2A:{op_name}"
                    domain_counts["a2a"] = domain_counts.get("a2a", 0) + 1
                else:
                    type_label = f"COMPUTE:{op_name}"
                    domain_counts["compute"] = domain_counts.get("compute", 0) + 1

            abstracted.append(type_label)

        type_seq = tuple(abstracted)
        domain_hint = max(domain_counts, key=domain_counts.get) if domain_counts else "compute"

        structural_hints = {
            "has_predicate": any("filter" in t for t in type_seq),
            "is_chained": len(type_seq) >= 2,
            "has_reduction": any("reduce" in t or "fold" in t for t in type_seq),
            "has_agent_comm": any("tell" in t or "ask" in t for t in type_seq),
        }

        return cls(
            type_sequence=type_seq,
            type_fingerprint=hashlib.sha256(
                str(type_seq).encode()
            ).hexdigest()[:16],
            min_length=len(type_seq),
            max_length=len(type_seq),
            structural_hints=structural_hints,
            domain_hint=domain_hint,
        )
```

### 3.3 Generalization Rule Lifecycle

A generalization rule passes through four stages:

```
  OBSERVATION          HYPOTHESIS             RULE                 LAW
  ────────────  ─────▶  ───────────  ─────▶  ─────  ─────▶  ─────
  "map+filter      "Any map+filter     Rule stored    Rule proven
   was faster        should try         in DB,        across N
   in workload X"    flatmap"           applied to     workloads,
                      (1 confirmation)  new workloads  auto-applied
```

```python
@dataclass
class GeneralizationRule:
    """A rule that generalizes a successful optimization.

    Rules capture: "When I see pattern X (abstractly), applying
    optimization Y yields speedup Z with confidence W."
    """
    rule_id: int
    abstract_signature: AbstractPatternSignature
    optimization_type: str           # "FUSE_PATTERN", "RECOMPILE_LANGUAGE", etc.
    optimization_params: dict        # Parameters for the optimization
    concrete_evidence: list[dict]    # [{sequence: [...], speedup: 1.4, workload: "X"}]
    total_applications: int = 0
    success_count: int = 0
    confidence: float = 0.0          # Bayesian confidence: Beta(success, fail+1)
    applicability_scope: str = "*"   # Glob pattern for applicable module paths
    created_at: float = 0.0
    last_applied_at: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_applications == 0:
            return 0.0
        return self.success_count / self.total_applications

    def should_auto_apply(self, min_confidence: float = 0.8,
                          min_applications: int = 3) -> bool:
        """Determine if this rule should be auto-applied without validation."""
        return (self.confidence >= min_confidence
                and self.total_applications >= min_applications
                and self.success_rate >= 0.7)

    def matches_pattern(self, concrete_sequence: tuple[str, ...],
                        tile_registry: TileRegistry) -> bool:
        """Check if a concrete execution pattern matches this rule."""
        candidate_sig = AbstractPatternSignature.from_concrete_pattern(
            DiscoveredPattern(sequence=concrete_sequence),
            tile_registry,
        )
        return candidate_sig.type_fingerprint == self.abstract_signature.type_fingerprint

    def update_confidence(self, success: bool) -> None:
        """Update Bayesian confidence after a new observation.

        Uses Beta-Binomial conjugate update:
        Prior: Beta(alpha=1, beta=1) (uniform)
        Posterior: Beta(alpha + successes, beta + failures)
        Confidence = posterior probability that true rate > 0.5
        """
        # Simplified: running average with momentum
        alpha = self.success_count + 1  # prior
        beta = (self.total_applications - self.success_count) + 1
        # P(p > 0.5) for Beta(alpha, beta)
        import math
        self.confidence = 1.0 - 0.5 * math.betainc(alpha, beta, 0.5, 1.0) / math.beta(alpha, beta)
```

### 3.4 Case-Based Reasoning for Tile Selection

When the evolution engine encounters a new workload, it can query the generalization database for similar past experiences:

```python
class CaseMemory:
    """Case-based reasoning for applying past optimization experiences.

    Each 'case' is a (workload_signature, optimization_applied, outcome) triple.
    New workloads are matched against past cases using structural similarity.
    """

    def __init__(self, memory_store: MemoryStore):
        self._store = memory_store
        self._cases: list[OptimizationCase] = []

    def record_case(self, case: OptimizationCase) -> None:
        """Record a new optimization case."""
        self._cases.append(case)
        # Persist to database
        self._store.save_generalization_rule(case.to_rule())

    def find_similar_cases(
        self,
        current_sequence: tuple[str, ...],
        top_k: int = 5,
    ) -> list[tuple[OptimizationCase, float]]:
        """Find the most similar past optimization cases.

        Uses a combination of:
        1. Structural edit distance on abstract signatures
        2. Domain overlap score
        3. Temporal recency bonus
        """
        tile_registry = default_registry  # from tiles.registry
        current_sig = AbstractPatternSignature.from_concrete_pattern(
            DiscoveredPattern(sequence=current_sequence), tile_registry
        )

        scored: list[tuple[OptimizationCase, float]] = []
        for case in self._cases:
            similarity = self._compute_similarity(current_sig, case.signature)
            if similarity > 0.3:  # minimum threshold
                scored.append((case, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _compute_similarity(
        self, a: AbstractPatternSignature, b: AbstractPatternSignature
    ) -> float:
        """Compute similarity between two abstract pattern signatures.

        Components:
        - Type sequence overlap (0.4 weight): Jaccard similarity on type sets
        - Domain match (0.3 weight): same domain = 1.0, related = 0.5
        - Structural hint overlap (0.3 weight): fraction of matching hints
        """
        # Type overlap
        set_a = set(a.type_sequence)
        set_b = set(b.type_sequence)
        if not set_a or not set_b:
            type_sim = 0.0
        else:
            type_sim = len(set_a & set_b) / len(set_a | set_b)

        # Domain match
        domain_sim = 1.0 if a.domain_hint == b.domain_hint else 0.3

        # Structural hint overlap
        hints_a = set(a.structural_hints.values())
        hints_b = set(b.structural_hints.values())
        struct_sim = len(hints_a & hints_b) / max(len(hints_a | hints_b), 1)

        return 0.4 * type_sim + 0.3 * domain_sim + 0.3 * struct_sim
```

### 3.5 Transfer Learning Between Workloads

The most powerful form of generalization is transferring knowledge from one workload domain to another:

```python
class TransferLearner:
    """Transfers optimization knowledge between workload domains.

    Example: If fusing map+filter works for numerical data pipelines,
    it likely works for string processing pipelines too -- because the
    structural pattern is the same even though the data types differ.
    """

    def propose_transfers(
        self, source_domain: str, target_domain: str
    ) -> list[MutationProposal]:
        """Propose optimizations from source_domain that haven't been
        tried in target_domain yet."""
        rules = self._store.get_rules_by_domain(source_domain)
        proposals = []
        for rule in rules:
            if rule.success_rate < 0.6:
                continue  # don't transfer uncertain rules
            # Create a proposal adapted for the target domain
            proposals.append(MutationProposal(
                strategy=MutationStrategy(rule.optimization_type),
                target=f"[transfer:{source_domain}->{target_domain}]",
                description=(
                    f"Transfer optimization from {source_domain}: "
                    f"{rule.abstract_signature.type_sequence}"
                ),
                kwargs=rule.optimization_params,
                estimated_speedup=rule.success_rate * 1.2,  # conservative estimate
                estimated_risk=0.3,  # moderate risk for transfers
                priority=rule.confidence * 5.0,
            ))
        return proposals
```

---

## 4. Learned Tile Library

### 4.1 Current Tile Landscape

FLUX ships with **34 built-in tiles** across 6 categories:

| Category | Count | Examples |
|----------|:-----:|----------|
| COMPUTE | 8 | map, reduce, scan, filter, zip, flatmap, sort, unique |
| MEMORY | 6 | gather, scatter, stream, copy, fill, transpose |
| CONTROL | 6 | loop, while, branch, switch, fuse, pipeline |
| A2A | 6 | tell, ask, broadcast, a2a_reduce, a2a_scatter, barrier |
| EFFECT | 3 | print_effect, log_effect, state_mut |
| TRANSFORM | 5 | cast, reshape, pack, unpack, join, split |

Each tile has: name, TileType, input/output ports with FIR types, a FIR blueprint (callable), cost_estimate, abstraction_level (2-8), language_preference, and tags.

### 4.2 Organizing the Learned Tile Library

As the system evolves, it creates new tiles from discovered patterns. Over time, this "learned vocabulary" grows. The organizational challenge is threefold:

#### By Abstraction Level (Taxonomic)

```python
class TileLibrary:
    """Organizes learned tiles into a browsable, queryable library.

    Tiles are organized along four axes:
    1. Abstraction level (2=primitive → 8=high-level effect)
    2. Domain category (compute, memory, control, a2a, effect, transform)
    3. Usage frequency (how often the tile is actually invoked)
    4. Provenance (builtin, evolved, imported, manual)
    """

    def __init__(self):
        self._by_level: dict[int, list[TileEntry]] = defaultdict(list)
        self._by_domain: dict[str, list[TileEntry]] = defaultdict(list)
        self._by_provenance: dict[str, list[TileEntry]] = defaultdict(list)
        self._by_usage: list[TileEntry] = []  # sorted by usage_count

    def register_learned_tile(
        self,
        name: str,
        tile_type: TileType,
        cost_estimate: float,
        abstraction_level: int,
        source_pattern: tuple[str, ...],
        fir_blueprint: str,
        tags: set[str],
    ) -> TileEntry:
        """Register a newly evolved tile."""
        entry = TileEntry(
            name=name,
            tile_type=tile_type,
            cost_estimate=cost_estimate,
            abstraction_level=abstraction_level,
            source_pattern=source_pattern,
            fir_blueprint=fir_blueprint,
            tags=tags,
            provenance="evolved",
            created_at=time.time(),
            usage_count=0,
            success_count=0,
        )
        self._by_level[abstraction_level].append(entry)
        self._by_domain[tile_type.value].append(entry)
        self._by_provenance["evolved"].append(entry)
        self._by_usage.append(entry)
        return entry

    def get_tiles_for_level(self, level: int) -> list[TileEntry]:
        """Get all tiles at a specific abstraction level."""
        return self._by_level.get(level, [])
```

#### By Domain (Ontological)

Domains should overlap. A tile like `evolved_map_filter` is both `COMPUTE` (it transforms data) and conceptually part of a "data pipeline" domain. The tagging system already supports this via the `tags: set[str]` field, but we need a richer ontology:

```python
TILE_ONTOLOGY = {
    "data_pipeline": {
        "parent": None,
        "children": ["transform", "filter", "aggregate"],
        "typical_patterns": ["map", "filter", "reduce", "flatmap", "sort"],
    },
    "numeric_compute": {
        "parent": "data_pipeline",
        "children": ["simd_ops", "vectorized"],
        "typical_patterns": ["gather", "scatter", "reduce", "scan"],
    },
    "agent_coordination": {
        "parent": None,
        "children": ["messaging", "synchronization", "distribution"],
        "typical_patterns": ["tell", "ask", "broadcast", "barrier", "a2a_reduce"],
    },
    "control_flow": {
        "parent": None,
        "children": ["iteration", "branching", "fusion"],
        "typical_patterns": ["loop", "while", "branch", "switch", "fuse", "pipeline"],
    },
}
```

#### By Frequency (Recency-Weighted)

Tiles should be ranked by a recency-weighted usage score, not raw count:

```python
def compute_tile_relevance(
    usage_count: int,
    last_used_at: float,
    current_time: float,
    half_life_days: float = 30.0,
) -> float:
    """Compute exponential-decay relevance score for a tile.

    Tiles used recently get higher scores than tiles used long ago,
    even if the old tiles have more total uses.

    Score = usage_count * 2^(-age / half_life)

    A half_life of 30 days means a tile used 30 days ago is worth
    half as much as one used today.
    """
    age_days = (current_time - last_used_at) / 86400.0
    decay = 2.0 ** (-age_days / half_life_days)
    return usage_count * decay
```

### 4.3 Pruning Obsolete Tiles

Tiles become obsolete when:
1. Their success_rate drops below a threshold (e.g., < 0.3)
2. They haven't been used in N sessions
3. A strictly better alternative exists (same signature, lower cost)

```python
class TilePruner:
    """Identifies and removes obsolete tiles from the library.

    Pruning policy:
    - Hard prune: success_rate < 0.2 AND usage_count > 5 (tried and failed)
    - Soft prune: not used in 90 days (archived, not deleted)
    - Merge prune: duplicate signature with higher-cost version
    - Domain prune: all source modules removed from current genome
    """

    def find_prunable(self, library: TileLibrary,
                      min_success_rate: float = 0.2,
                      max_stale_days: float = 90.0) -> list[TileEntry]:
        """Return tiles recommended for pruning."""
        now = time.time()
        candidates = []

        for tile in library.all_tiles():
            score = 0.0

            # Failed tiles
            if tile.success_rate < min_success_rate and tile.usage_count > 5:
                score += 1.0

            # Stale tiles
            if tile.last_used_at and (now - tile.last_used_at) > max_stale_days * 86400:
                score += 0.8

            # Duplicate tiles (same abstract signature, higher cost)
            duplicates = library.find_similar(tile)
            for dup in duplicates:
                if dup.cost_estimate < tile.cost_estimate:
                    score += 0.6
                    break

            # Orphaned tiles (source modules no longer exist)
            if tile.provenance == "evolved" and self._is_orphaned(tile):
                score += 0.5

            if score > 0.5:
                candidates.append((tile, score))

        return [t for t, s in sorted(candidates, key=lambda x: x[1], reverse=True)]
```

### 4.4 Merging Similar Tiles

```python
class TileMerger:
    """Merges tiles that are structurally similar into unified tiles.

    Two tiles are mergeable if:
    1. They have compatible port signatures (superset/subset relationship)
    2. Their FIR blueprints have similar structure
    3. They share at least 50% of their tags

    The merged tile:
    - Has the lower cost_estimate of the two
    - Has the union of both tag sets
    - Has a combined FIR blueprint that handles both cases
    """

    def find_merge_candidates(self, library: TileLibrary) -> list[tuple[TileEntry, TileEntry]]:
        """Find pairs of tiles that could be merged."""
        candidates = []
        tiles = library.all_tiles()

        for i, a in enumerate(tiles):
            for b in tiles[i+1:]:
                if self._can_merge(a, b):
                    candidates.append((a, b))
        return candidates

    def _can_merge(self, a: TileEntry, b: TileEntry) -> bool:
        """Check if two tiles can be merged."""
        # Same tile type
        if a.tile_type != b.tile_type:
            return False

        # Overlapping tags
        tag_overlap = len(a.tags & b.tags) / max(len(a.tags | b.tags), 1)
        if tag_overlap < 0.5:
            return False

        # Compatible abstraction levels (within 2 levels)
        if abs(a.abstraction_level - b.abstraction_level) > 2:
            return False

        return True
```

### 4.5 Export/Import Format

Learned tile libraries should be exportable as versioned, inspectable packages:

```json
{
  "flux_tile_library": {
    "version": "2.0",
    "exported_at": "2025-07-14T10:30:00Z",
    "source_genome_checksum": "a1b2c3d4",
    "tiles": [
      {
        "name": "evolved_map_filter_flatmap",
        "tile_type": "compute",
        "description": "Fused map+filter into a single flatmap pass. Discovered from 47 occurrences across data_pipeline workloads.",
        "cost_estimate": 1.2,
        "abstraction_level": 7,
        "source_pattern": ["map", "filter"],
        "tags": ["compute", "map", "filter", "flatmap", "fused", "evolved"],
        "usage_stats": {
          "total_uses": 342,
          "success_count": 298,
          "failure_count": 44,
          "avg_speedup": 1.37,
          "first_used": "2025-06-01T00:00:00Z",
          "last_used": "2025-07-14T10:00:00Z"
        },
        "fir_blueprint": "/* Generated FIR for fused map+filter */\nfun $data -> flatmap(fn, predicate)",
        "required_capabilities": []
      }
    ],
    "generalization_rules": [
      {
        "signature": ["COMPUTE:map", "COMPUTE:filter"],
        "optimization": "FUSE_PATTERN",
        "confidence": 0.92,
        "evidence_count": 47
      }
    ]
  }
}
```

---

## 5. Meta-Learning: Learning to Learn Better

### 5.1 The Meta-Learning Opportunity

The FLUX EvolutionEngine has several hyperparameters that are currently hardcoded:

| Parameter | Current Value | Location | Effect |
|-----------|:------------:|----------|--------|
| `max_mutations_per_step` | 5 | SystemMutator | How many mutations to try per generation |
| `min_speedup_threshold` | 1.05 | SystemMutator | Minimum speedup to accept |
| `max_risk_tolerance` | 0.8 | SystemMutator | Maximum risk for proposals |
| `max_generations` | 100 | EvolutionEngine | Safety limit on evolution cycles |
| `convergence_threshold` | 0.001 | EvolutionEngine | Stop if fitness delta < threshold |
| `hot_threshold` | 0.8 | AdaptiveProfiler | Percentile cutoff for HEAT |
| `warm_threshold` | 0.5 | AdaptiveProfiler | Percentile cutoff for WARM |

These parameters control the **exploration vs. exploitation** tradeoff. Meta-learning means the system adjusts these parameters based on what has worked in past sessions.

### 5.2 Multi-Armed Bandit for Mutation Strategy Selection

The `MutationStrategy` enum defines 7 strategies: RECOMPILE_LANGUAGE, FUSE_PATTERN, REPLACE_TILE, ADD_TILE, MERGE_TILES, SPLIT_TILE, INLINE_OPTIMIZATION. Currently, the mutator proposes all applicable strategies every step. A bandit approach would allocate effort to the most promising strategies:

```python
class MutationBandit:
    """Multi-armed bandit for mutation strategy selection.

    Each mutation strategy is an 'arm' of the bandit.
    Pulling an arm = attempting that mutation type.
    Reward = fitness_delta from the mutation result.

    Uses Thompson Sampling for exploration-exploitation balance:
    - Each arm has a Beta(successes+1, failures+1) posterior
    - Sample from each posterior, pick the arm with highest sample
    - This naturally balances exploration (uncertain arms get high variance samples)
      with exploitation (successful arms get high mean samples)
    """

    def __init__(self):
        self._arms: dict[MutationStrategy, BetaPosterior] = {}
        self._total_pulls: int = 0
        for strategy in MutationStrategy:
            self._arms[strategy] = BetaPosterior(alpha=1.0, beta=1.0)

    def select_strategy(self) -> MutationStrategy:
        """Select a mutation strategy using Thompson Sampling."""
        best_strategy = None
        best_sample = -1.0

        for strategy, posterior in self._arms.items():
            sample = posterior.sample()
            if sample > best_sample:
                best_sample = sample
                best_strategy = strategy

        return best_strategy

    def update(self, strategy: MutationStrategy, reward: float) -> None:
        """Update the bandit after observing a reward."""
        self._total_pulls += 1
        self._arms[strategy].update(reward > 0)  # binary reward

    def get_strategy_weights(self) -> dict[str, float]:
        """Get current estimated win rates for each strategy."""
        return {
            s.value: self._arms[s].mean()
            for s in MutationStrategy
        }

@dataclass
class BetaPosterior:
    """Beta distribution posterior for a Bernoulli bandit arm."""
    alpha: float  # success + 1 (prior)
    beta: float   # failure + 1 (prior)

    def sample(self) -> float:
        """Draw a sample from the Beta distribution."""
        import random
        return random.betavariate(self.alpha, self.beta)

    def mean(self) -> float:
        """Expected value of the Beta distribution."""
        return self.alpha / (self.alpha + self.beta)

    def update(self, success: bool) -> None:
        """Update posterior after a Bernoulli observation."""
        if success:
            self.alpha += 1.0
        else:
            self.beta += 1.0

    @property
    def confidence_interval_95(self) -> tuple[float, float]:
        """Approximate 95% credible interval."""
        from math import betainv
        # Lower = betainv(0.025, alpha, beta)
        # Upper = betainv(0.975, alpha, beta)
        m = self.mean()
        se = (self.alpha * self.beta /
              ((self.alpha + self.beta)**2 * (self.alpha + self.beta + 1))) ** 0.5
        return (max(0, m - 1.96 * se), min(1, m + 1.96 * se))
```

### 5.3 Adaptive Exploration Rate

The exploration rate should decrease as the system converges but increase when a major change is detected:

```python
class AdaptiveExploration:
    """Manages the exploration-exploitation balance over time.

    Exploration rate (epsilon) controls:
    - 0.0: Pure exploitation (always use best-known strategy)
    - 1.0: Pure exploration (always try random strategies)

    Adaptation rules:
    1. Start high (0.3) → decrease as confidence grows
    2. Spike on fitness plateau (system might be in local optimum)
    3. Spike on genome change (new territory to explore)
    4. Decay rate depends on success rate (faster decay = more confident)
    """

    def __init__(self, initial_epsilon: float = 0.3,
                 min_epsilon: float = 0.05,
                 decay_rate: float = 0.95):
        self.epsilon = initial_epsilon
        self.min_epsilon = min_epsilon
        self.base_decay = decay_rate
        self._plateau_count: int = 0
        self._last_fitness: float = 0.0

    def should_explore(self) -> bool:
        """Decide whether to explore or exploit."""
        import random
        return random.random() < self.epsilon

    def update(self, fitness_delta: float, genome_changed: bool) -> float:
        """Update exploration rate based on recent outcomes."""
        # Detect plateau
        if abs(fitness_delta) < 0.001:
            self._plateau_count += 1
        else:
            self._plateau_count = 0

        # Spike on plateau (escape local optimum)
        if self._plateau_count >= 3:
            self.epsilon = min(1.0, self.epsilon + 0.2)
            self._plateau_count = 0
        # Spike on genome change
        elif genome_changed:
            self.epsilon = min(1.0, self.epsilon + 0.15)
        # Normal decay
        else:
            # Decay faster when fitness is improving (gaining confidence)
            decay = self.base_decay ** (1.0 if fitness_delta > 0 else 0.5)
            self.epsilon = max(self.min_epsilon, self.epsilon * decay)

        self._last_fitness += fitness_delta
        return self.epsilon
```

### 5.4 Bayesian Optimization for Hyperparameter Tuning

For the higher-level hyperparameters (profiler thresholds, convergence criteria), use Bayesian optimization with a Gaussian Process surrogate:

```python
class MetaOptimizer:
    """Bayesian optimizer for FLUX evolution hyperparameters.

    Optimizes: hot_threshold, warm_threshold, convergence_threshold,
    max_mutations_per_step, min_speedup_threshold

    Uses a simple Gaussian Process (or could use scikit-optimize):
    - Objective: final_fitness_score after N generations
    - Parameters: bounded hyperparameters
    - Acquisition: Expected Improvement (EI)
    """

    PARAM_BOUNDS = {
        "hot_threshold": (0.6, 0.95),
        "warm_threshold": (0.3, 0.7),
        "convergence_threshold": (0.0001, 0.01),
        "max_mutations_per_step": (1, 10),
        "min_speedup_threshold": (1.01, 1.2),
    }

    def __init__(self):
        self._observations: list[dict] = []  # {params: {...}, fitness: float}

    def suggest(self) -> dict[str, float]:
        """Suggest the next hyperparameter configuration to try.

        Uses Expected Improvement acquisition on a GP surrogate.
        Falls back to random search with < 3 observations.
        """
        if len(self._observations) < 3:
            return self._random_suggest()
        return self._bayesian_suggest()

    def observe(self, params: dict, fitness: float) -> None:
        """Record an observation."""
        self._observations.append({"params": params, "fitness": fitness})

    def best_params(self) -> dict[str, float]:
        """Return the best-observed hyperparameter configuration."""
        if not self._observations:
            return {k: v[0] for k, v in self.PARAM_BOUNDS.items()}
        best = max(self._observations, key=lambda o: o["fitness"])
        return best["params"]

    def _random_suggest(self) -> dict[str, float]:
        """Random parameter suggestion."""
        import random
        return {
            k: random.uniform(lo, hi)
            for k, (lo, hi) in self.PARAM_BOUNDS.items()
        }

    def _bayesian_suggest(self) -> dict[str, float]:
        """Bayesian optimization suggestion (simplified GP).

        For production, use GPy, scikit-optimize, or optuna.
        This implements a simplified version:
        1. Fit a simple surrogate (kernel smoothing)
        2. Maximize Expected Improvement
        """
        # Simplified: weighted average of top-K observations
        # with noise injection proportional to uncertainty
        top_k = min(5, len(self._observations))
        sorted_obs = sorted(
            self._observations,
            key=lambda o: o["fitness"],
            reverse=True,
        )[:top_k]

        result = {}
        for param_name, (lo, hi) in self.PARAM_BOUNDS.items():
            values = [o["params"][param_name] for o in sorted_obs]
            # Weighted average favoring better observations
            weights = [o["fitness"] + 1.0 for o in sorted_obs]
            total_w = sum(weights)
            weighted_mean = sum(v * w for v, w in zip(values, weights)) / total_w

            # Add noise proportional to parameter range and observation count
            # More observations = less noise (more certain)
            noise_scale = (hi - lo) * 0.1 / (1.0 + len(self._observations) * 0.1)
            import random
            suggested = weighted_mean + random.gauss(0, noise_scale)
            result[param_name] = max(lo, min(hi, suggested))

        return result
```

---

## 6. Strategic Forgetting

### 6.1 Why Forgetting Matters

A system that never forgets will eventually drown in its own history. The PatternMiner's `_subsequence_cache` already has a `max_trace_length` (10,000) with FIFO eviction. The JITCache uses LRU eviction. But the evolution engine's history and learned tiles have no forgetting policy.

Forgetting serves three purposes:
1. **Memory efficiency**: Prevent unbounded growth of history databases
2. **Adaptability**: Old optimization strategies may become counterproductive as the workload changes
3. **Noise reduction**: Failed experiments from early sessions shouldn't pollute current decision-making

### 6.2 The Ebbinghaus Model for Code Tiles

Apply the Ebbinghaus forgetting curve to learned tile relevance:

```
Relevance(t) = R_0 * e^(-t / S)

Where:
  R_0  = initial relevance (proportional to confidence at creation)
  t    = time since last successful use
  S    = stability factor (tiles with more uses have higher stability)

Stability increases with each successful use:
  S_n = S_{n-1} * 1.5
```

```python
class EbbinghausDecay:
    """Applies the Ebbinghaus forgetting curve to tile relevance.

    Tiles that are frequently used and successful have high stability
    (they're 'well-learned') and decay slowly. Rarely-used tiles decay
    faster and may eventually be forgotten (archived).
    """

    def __init__(self, base_half_life_days: float = 30.0,
                 stability_growth: float = 1.5):
        self.base_half_life = base_half_life_days * 86400.0  # in seconds
        self.stability_growth = stability_growth

    def compute_relevance(
        self,
        tile: TileEntry,
        current_time: float,
    ) -> float:
        """Compute current relevance score for a tile."""
        if tile.last_used_at is None or tile.last_used_at == 0:
            return 0.0

        age = current_time - tile.last_used_at
        stability = self.base_half_life * (self.stability_growth ** tile.usage_count)
        relevance = math.exp(-age / stability)

        # Boost for recent success
        if tile.success_count > 0:
            success_bonus = min(1.0, tile.success_count / (tile.success_count + tile.failure_count))
            relevance *= (0.5 + 0.5 * success_bonus)

        return relevance

    def should_forget(self, tile: TileEntry, current_time: float,
                      threshold: float = 0.01) -> bool:
        """Check if a tile should be forgotten (archived)."""
        return self.compute_relevance(tile, current_time) < threshold
```

### 6.3 Cache Eviction Policies for Genomes

Genomes consume significant storage (each is a full system snapshot in JSON). The eviction policy should balance:

```python
class GenomeEvictionPolicy:
    """Policy for evicting old genome snapshots from the database.

    Keeps genomes that are:
    1. The latest (always keep last N)
    2. Fitness peaks (local maxima in the fitness landscape)
    3. Checkpoints at regular intervals (every N generations)
    4. Ancestors of the current genome (for rollback lineage)

    Evicts genomes that are:
    1. Old fitness valleys
    2. Intermediate steps between checkpoints
    3. From sessions > 90 days ago (configurable)
    """

    def __init__(self, keep_latest_n: int = 10,
                 keep_peaks: int = 20,
                 checkpoint_interval: int = 10,
                 max_age_days: float = 90.0):
        self.keep_latest_n = keep_latest_n
        self.keep_peaks = keep_peaks
        self.checkpoint_interval = checkpoint_interval
        self.max_age_days = max_age_days

    def select_for_eviction(self, genomes: list[dict]) -> list[int]:
        """Return genome_ids to evict."""
        if len(genomes) <= self.keep_latest_n:
            return []

        now = time.time()
        protected = set()
        evictable = []

        # Protect latest N
        sorted_by_gen = sorted(genomes, key=lambda g: g["generation"], reverse=True)
        for g in sorted_by_gen[:self.keep_latest_n]:
            protected.add(g["genome_id"])

        # Protect fitness peaks
        sorted_by_fit = sorted(genomes, key=lambda g: g["fitness_score"], reverse=True)
        for g in sorted_by_fit[:self.keep_peaks]:
            protected.add(g["genome_id"])

        # Protect checkpoints
        for g in genomes:
            if g["generation"] % self.checkpoint_interval == 0:
                protected.add(g["genome_id"])

        # Protect recent genomes
        for g in genomes:
            if (now - g["timestamp"]) < self.max_age_days * 86400:
                protected.add(g["genome_id"])

        # Everything else is evictable
        for g in genomes:
            if g["genome_id"] not in protected:
                evictable.append(g["genome_id"])

        return evictable
```

### 6.4 Staleness Detection

A learned optimization becomes *stale* when the underlying code or workload has changed enough that the optimization no longer applies:

```python
class StalenessDetector:
    """Detects when learned optimizations have become stale.

    Staleness indicators:
    1. Source modules no longer exist in the current genome
    2. Source modules have changed checksums
    3. The optimization's success_rate has been declining
    4. The workload profile has shifted (new dominant patterns)
    """

    def check_tile_staleness(
        self, tile: TileEntry, current_genome: Genome
    ) -> tuple[bool, str]:
        """Check if a learned tile is stale.

        Returns (is_stale, reason).
        """
        if tile.provenance != "evolved" or not tile.source_pattern:
            return False, ""

        # Check if source modules still exist
        for module_path in tile.source_pattern:
            if module_path not in current_genome.modules:
                return True, f"Source module '{module_path}' no longer exists"

            # Check if module has changed
            current_checksum = current_genome.modules[module_path].checksum
            if hasattr(tile, 'source_checksums'):
                if module_path in tile.source_checksums:
                    if tile.source_checksums[module_path] != current_checksum:
                        return True, (
                            f"Source module '{module_path}' has changed "
                            f"(was {tile.source_checksums[module_path][:8]}, "
                            f"now {current_checksum[:8]})"
                        )

        # Check declining success rate
        if tile.usage_count > 10:
            recent_rate = (tile.success_count / tile.usage_count)
            if hasattr(tile, 'initial_success_rate'):
                if recent_rate < tile.initial_success_rate * 0.5:
                    return True, (
                        f"Success rate declined from "
                        f"{tile.initial_success_rate:.1%} to {recent_rate:.1%}"
                    )

        return False, ""

    def check_rule_staleness(
        self, rule: GeneralizationRule, recent_patterns: list[DiscoveredPattern]
    ) -> tuple[bool, str]:
        """Check if a generalization rule is still relevant."""
        # If the rule's pattern hasn't been seen in recent patterns
        matches = sum(
            1 for p in recent_patterns
            if rule.abstract_signature.type_fingerprint in
            hashlib.sha256(str(p.sequence).encode()).hexdigest()
        )

        if matches == 0 and len(recent_patterns) > 50:
            return True, "Pattern no longer appears in recent workloads"

        return False, ""
```

### 6.5 Graceful Degradation

When a learned tile or rule is detected as stale, the system should degrade gracefully rather than failing:

```python
class GracefulDegradation:
    """Manages graceful degradation of stale learned artifacts.

    Degradation levels:
    1. WARN: Log staleness, continue using (mild staleness)
    2. DEMOTE: Reduce priority, don't auto-apply (moderate staleness)
    3. QUARANTINE: Stop using, but keep for reference (high staleness)
    4. ARCHIVE: Remove from active library, export to archive (confirmed stale)
    5. DELETE: Permanently remove (quarantined > 30 days)
    """

    def handle_stale_tile(self, tile: TileEntry, staleness_reason: str) -> str:
        """Handle a stale tile. Returns the action taken."""
        age_days = (time.time() - tile.created_at) / 86400.0

        if age_days < 7:
            # Too new to be confidently stale
            return "WARN"

        if tile.success_rate > 0.5:
            # Still working, just degraded
            return "DEMOTE"

        if tile.success_rate < 0.3 and age_days > 30:
            return "QUARANTINE"

        if tile.success_rate < 0.1 and age_days > 60:
            return "ARCHIVE"

        return "WARN"
```

---

## 7. Open Research Questions

### 7.1 Theoretical Framework

**Q1: What is the formal model for a system that learns to compile better?**

FLUX sits at the intersection of program optimization (compilers), online learning (bandits), and evolutionary computation. A unified formal model would treat:
- The genome as a point in a high-dimensional configuration space
- Mutations as neighborhood operators (cf. local search in combinatorial optimization)
- Fitness as a noisy objective function (workloads are non-deterministic)
- The tile library as a growing vocabulary (cf. grammar induction in program synthesis)

Is there a PAC-learning framework for self-optimizing compilers? Can we prove convergence bounds?

**Q2: How do you measure "code understanding"?**

Fitness is currently `0.4 * speed + 0.3 * modularity + 0.3 * correctness`. But these are proxy measures. What does it mean for a compiler to "understand" code? Candidates:
- **Prediction accuracy**: Can the system predict the performance of code it hasn't seen?
- **Transfer ratio**: What fraction of learned optimizations transfer to new workloads?
- **Compression ratio**: Can the tile library be compressed without losing optimization power? (Analogous to the Minimum Description Length principle -- if the system truly understands the patterns, it should be able to describe them compactly.)

**Q3: Can a system develop programming intuition?**

Human programmers develop "intuition" -- a rapid, non-deliberative sense that certain patterns are right or wrong. For FLUX, this might manifest as:
- **Immediate pattern recognition**: Recognizing that a pattern is "similar to something I've seen before" without explicit matching (embedding-based similarity)
- **Risk intuition**: A learned sense that "mutations of this type tend to fail for these kinds of modules" without explicit rule lookup
- **Creative leaps**: Proposing mutations that have no direct precedent but combine elements of multiple past experiences (analogical reasoning)

### 7.2 Practical Open Questions

**Q4: How do we handle conflicting generalizations?**

If Rule A says "always fuse map+filter" and Rule B says "never fuse map+filter when the predicate is complex," which wins? We need:
- A priority/precedence system for rules
- A conflict detection mechanism
- A resolution strategy (most evidence wins, most recent wins, domain-specific wins)

**Q5: What is the right unit of forgetting?**

Should we forget individual tiles? Entire generalization rules? Whole evolution sessions? The answer affects the granularity of the memory system and the efficiency of the forgetting policy.

**Q6: How do we handle distribution shift?**

When the workload profile changes dramatically (e.g., from data processing to agent coordination), most learned optimizations become irrelevant. The system needs:
- **Workload domain detection**: Classifying the current workload into a domain
- **Domain-aware memory**: Organizing learned artifacts by domain
- **Cross-domain transfer**: Selectively applying knowledge from related domains

**Q7: What is the privacy model for learned tiles?**

If FLUX is deployed in a multi-tenant environment, learned tiles from one user's workload should not leak information about that workload to another user. This requires:
- Tile sanitization: removing identifiable source module paths
- Differential privacy: adding noise to tile statistics
- Tile provenance tracking: knowing which workloads contributed to a tile

**Q8: How does the system bootstrap from zero knowledge?**

The first session has no learned tiles, no generalization rules, no meta-learning state. The system must rely entirely on its 34 built-in tiles and the generic evolution loop. How many sessions are needed before the system becomes measurably better than a naive compiler? What's the learning curve?

**Q9: Can the system learn negative knowledge?**

"Knowing what NOT to do" is as important as knowing what to do. Can FLUX learn:
- "Never fuse map+filter when the data size is < 100 elements" (overhead exceeds benefit)
- "Never recompile to C for modules with < 10 calls" (compile time exceeds runtime savings)
- "This tile pattern always causes validation failures for workload type X"

This would require tracking *negative* mutation outcomes with the same rigor as positive ones, and generating "anti-rules" that prevent wasteful exploration.

**Q10: What is the computational budget for meta-learning?**

Meta-learning itself consumes resources. Bayesian optimization, Thompson Sampling, and case-based reasoning all have computational overhead. At what point does the cost of learning exceed the benefit of the learned optimizations? Is there a theoretical optimal stopping criterion for meta-learning?

---

## Appendix A: Implementation Priority

| Phase | Feature | Effort | Impact |
|-------|---------|:------:|:------:|
| **P0** | Genome serialization to SQLite | 2 days | Unlocks all cross-session memory |
| **P0** | Learned tile persistence | 1 day | Core value: tiles survive restarts |
| **P1** | Generalization rule framework | 3 days | Transfer learning between workloads |
| **P1** | Ebbinghaus decay for tiles | 1 day | Prevents library bloat |
| **P2** | Thompson Sampling for mutations | 2 days | Smarter mutation selection |
| **P2** | Tile library export/import | 2 days | Cross-system knowledge sharing |
| **P3** | Meta-optimizer (Bayesian hyperparams) | 3 days | Self-tuning evolution engine |
| **P3** | Staleness detection | 1 day | Robustness as workloads evolve |
| **P4** | Tile merging/pruning | 2 days | Library hygiene at scale |
| **P4** | Domain-aware memory | 3 days | Handle workload distribution shift |

---

## Appendix B: References

- Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). "Finite-time Analysis of the Multiarmed Bandit Problem." *Machine Learning*.
- Ebbinghaus, H. (1885/1964). "Memory: A Contribution to Experimental Psychology."
- Kohavi, R., & Longbotham, R. (2017). "Online Controlled Experiments and A/B Testing." *Encyclopedia of Machine Learning*.
- Snoek, J., Larochelle, H., & Adams, R. P. (2012). "Practical Bayesian Optimization of Machine Learning Algorithms." *NeurIPS*.
- transfer learning: Pan, S. J., & Yang, Q. (2010). "A Survey on Transfer Learning." *IEEE TKDE*.
- BEAM VM hot code loading: Armstrong, J. (2007). *Programming Erlang: Software for a Concurrent World*.
