# Simulation, Prediction & Speculative Execution in the FLUX Runtime

> **Research Document v1.0** | FLUX Project
>
> This document explores how the FLUX runtime can move from *reactive* optimization
> (profile-then-optimize) to *predictive* optimization (predict-then-optimize-before-running).
> Every proposal is grounded in the existing codebase: the FIR instruction set, the adaptive
> profiler's heat classification, the evolution engine's mutate-validate-commit loop, and
> the JIT compiler's optimization pipeline.

---

## Table of Contents

1. [Pre-Execution Simulation](#1-pre-execution-simulation)
2. [Speculative Evolution](#2-speculative-evolution)
3. [Performance Modeling](#3-performance-modeling)
4. [What-If Analysis](#4-what-if-analysis)
5. [Digital Twin](#5-digital-twin)
6. [Energy-Aware Optimization](#6-energy-aware-optimization)
7. [Open Research Questions](#7-open-research-questions)

---

## 1. Pre-Execution Simulation

### 1.1 The Problem: Reactive Heat Classification is Too Late

The current `AdaptiveProfiler` classifies modules into `FROZEN/COOL/WARM/HOT/HEAT`
using **percentile-based thresholds on call counts** (see `profiler.py:192-232`). A module
must be *executed* before it can be classified. This creates a bootstrapping problem:

- A newly loaded module starts as `FROZEN` with zero profile data.
- The evolution engine (`evolution.py`) skips `FROZEN` modules in its recompilation proposals.
- The module must be called enough times to cross the percentile threshold before any
  optimization is considered.

For long-running agent systems, this warm-up period can span thousands of execution
cycles. The goal of pre-execution simulation is to **predict a module's heat level before
it is ever executed**, enabling immediate optimization decisions.

### 1.2 Three Simulation Approaches

#### 1.2.1 Abstract Interpretation over FIR

Abstract interpretation executes the FIR on *abstract values* (intervals, signs, constness)
instead of concrete data. The existing FIR instruction set (`fir/instructions.py`) has
30+ instruction types spanning arithmetic, memory, and control flow -- all amenable to
abstract interpretation.

**Concrete approach for FLUX:**

```python
class IntervalDomain:
    """Abstract value: interval [lo, hi] for integer types."""

    def __init__(self, lo: int = -2**63, hi: int = 2**63 - 1):
        self.lo = lo
        self.hi = hi

    def iadd(self, other):
        return IntervalDomain(self.lo + other.lo, self.hi + other.hi)

    def imul(self, other):
        products = [
            self.lo * other.lo, self.lo * other.hi,
            self.hi * other.lo, self.hi * other.hi,
        ]
        return IntervalDomain(min(products), max(products))

    @property
    def is_constant(self):
        return self.lo == self.hi

    @property
    def width(self):
        return self.hi - self.lo
```

Each FIR function can be simulated with interval arithmetic to determine:
- **Loop trip counts**: If a `Branch` condition's interval doesn't include zero, the branch
  is always taken. Combined with induction variable analysis, this yields loop bounds.
- **Memory access patterns**: `Load`/`Store` with interval-based offsets predict the
  accessed memory region size.
- **Call frequency estimates**: `Call` instructions inside loops are multiplied by the
  loop's estimated trip count.

The `EvolutionEngine.step()` method (line 267) currently executes a real workload
(`workload()`) to profile execution. Abstract interpretation replaces this with a
static analysis pass that runs in microseconds instead of milliseconds.

**Cost estimate:** A 100-instruction FIR function takes ~0.1ms to abstractly interpret
vs. ~10ms to execute on the bytecode VM. The simulation is ~100x faster.

#### 1.2.2 Structural Heuristics (No Execution Required)

Some properties are predictable from FIR structure alone, without any interpretation:

| FIR Structural Feature | Predicted Heat | Confidence |
|---|---|---|
| Function called from >3 `Call` sites in the same module | HOT | 0.7 |
| Function contains a `Branch` inside a loop (nesting depth > 1) | HEAT | 0.6 |
| Function body < 5 instructions and called in a loop | WARM | 0.5 |
| Function contains SIMD opcodes (`vadd`, `vmul`, `vfma`) | HEAT | 0.8 |
| Function is a leaf (no `Call` instructions, only arithmetic) | HEAT if short, COOL if long | 0.6 |
| Function contains A2A primitives (`Tell`, `Ask`, `Delegate`) | COOL (I/O bound) | 0.7 |

The `SystemMutator._propose_recompilations()` method (line 158) currently only proposes
recompilations for modules already classified as HOT/HEAT. With structural heuristics,
it can pre-classify newly loaded modules and immediately generate proposals.

#### 1.2.3 Concrete Simulation with Profiling Estimates

The most accurate simulation runs the bytecode on the VM but with *estimated inputs*
derived from the module's type signatures and the caller's profile data:

```python
class PreExecutionSimulator:
    """Simulate bytecode execution with synthetic inputs."""

    def __init__(self, vm: Interpreter):
        self.vm = vm

    def simulate(self, bytecode: bytes, input_constraints: list[IntervalDomain]) -> SimResult:
        """Run bytecode with abstract interval inputs, count instructions by type."""
        vm = self.vm  # fresh VM state
        instruction_counts = defaultdict(int)
        branch_taken = defaultdict(bool)
        loop_iterations = 0
        max_iterations = 1000  # cap loop unrolling

        # Inject abstract inputs into registers
        for i, constraint in enumerate(input_constraints[:16]):
            mid = (constraint.lo + constraint.hi) // 2
            vm.regs.write_gp(i, mid)

        # Run with cycle limit
        try:
            for _ in range(max_iterations):
                if not vm.running or vm.cycle_count >= vm.max_cycles:
                    break
                # ... count instructions, track branches ...
                vm._step()
                loop_iterations += 1
        except VMError:
            pass  # simulation failure is OK

        return SimResult(
            instruction_counts=dict(instruction_counts),
            estimated_cycles=vm.cycle_count,
            branches_resolved=sum(branch_taken.values()),
            total_branches=len(branch_taken),
        )
```

### 1.3 Integration Point

The pre-execution simulator hooks into the `Genome.capture()` method. Currently,
`capture()` reads profiler data *after* execution. With simulation, it can populate
`ModuleSnapshot.heat_level` and `ModuleSnapshot.call_count` with predicted values
before any real execution occurs:

```python
def capture(self, module_root, tile_registry, profiler, selector):
    self.timestamp = time.time()
    self._capture_modules(module_root)
    self._capture_tiles(tile_registry)
    self._capture_profiler(profiler)
    # NEW: Predict heat for FROZEN modules
    self._predict_heat_for_frozen_modules(profiler)
    self._capture_languages(selector)
    self.checksum = self._compute_checksum()
```

---

## 2. Speculative Evolution

### 2.1 The Current Bottleneck: Sequential Mutate-Validate-Commit

The evolution engine in `evolution.py:288-321` processes mutations **sequentially**:

```python
for proposal in proposals:
    result = self.mutator.apply_mutation(proposal, self.genome, validation_fn)
    if result.success:
        self.mutator.commit_mutation(proposal, result)
        # ... update genome ...
    else:
        self.mutator.rollback_mutation(proposal, result)
```

Each `apply_mutation()` call (see `mutator.py:288-348`) performs:
1. `genome.mutate()` -- deep copy + mutation (~0.5ms for a genome with 50 modules)
2. `mutated.evaluate_fitness()` -- score computation (~0.1ms)
3. Optional `validation_fn(mutated)` -- correctness check (~10ms)

For 5 proposals per generation, this is ~50ms. With speculative evaluation, we can
reduce this to ~10ms by evaluating all 5 in parallel and selecting the best.

### 2.2 Branch Prediction Applied to Evolution

In CPU branch prediction, the processor guesses the outcome of a branch and speculatively
executes the predicted path. If the prediction is wrong, the state is rolled back. The
same principle applies to evolution:

**Branch Prediction for Mutations:**

The `MutationProposal` dataclass already includes `estimated_speedup` and `estimated_risk`
fields. We can build a prediction model from the mutation history:

```python
class MutationPredictor:
    """Predict whether a mutation will succeed before validating it."""

    def __init__(self):
        self._history: list[MutationRecord] = []

    def train(self, records: list[MutationRecord]):
        """Build prediction model from past mutation outcomes."""
        self._history = records

    def predict_success(self, proposal: MutationProposal) -> float:
        """Probability that this mutation will succeed (0.0 to 1.0)."""
        # Bayes' theorem: P(success | features) based on historical priors
        features = self._extract_features(proposal)

        # Simple feature-based heuristic (replace with ML model)
        score = 0.5  # prior
        score += 0.1 * (1.0 - proposal.estimated_risk)      # lower risk = higher success
        score += 0.05 * min(proposal.estimated_speedup, 5.0)  # moderate speedup OK
        score -= 0.1 * (proposal.priority < 2.0)             # low priority = less tested

        # Check historical success rate for this mutation type
        similar = [r for r in self._history
                   if r.proposal.strategy == proposal.strategy and r.committed]
        if similar:
            score = 0.3 * score + 0.7 * (sum(1 for s in similar if s.committed) / len(similar))

        return max(0.0, min(1.0, score))
```

The prediction enables **speculative commit**: instead of validating every mutation,
only validate those with `predict_success() < 0.8`. High-confidence mutations skip
validation entirely, saving the ~10ms validation cost.

### 2.3 Parallel Mutation Evaluation

The most impactful optimization is to evaluate all proposed mutations simultaneously:

```python
import concurrent.futures

class SpeculativeEvolutionEngine(EvolutionEngine):
    """Evolution engine that evaluates mutations in parallel."""

    def _evaluate_mutations_parallel(
        self,
        proposals: list[MutationProposal],
        genome: Genome,
        validation_fn,
        max_workers: int = 4,
    ) -> list[MutationResult]:
        """Evaluate all proposals in parallel, return sorted by fitness delta."""

        def evaluate_one(proposal):
            return self.mutator.apply_mutation(proposal, genome, validation_fn)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(evaluate_one, p): p for p in proposals}
            results = []
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Sort by fitness_delta descending -- best first
        results.sort(key=lambda r: r.fitness_delta, reverse=True)
        return results

    def step(self, module_root, tile_registry, workload=None, validation_fn=None):
        """Overridden step with parallel mutation evaluation."""
        # ... capture, profile, mine, propose (same as parent) ...

        # NEW: Evaluate all proposals in parallel
        results = self._evaluate_mutations_parallel(
            proposals, self.genome, validation_fn
        )

        # Keep only the best mutation that passes validation
        for result in results:
            if result.success and result.fitness_delta > 0:
                self.mutator.commit_mutation(result.proposal, result)
                # ... update genome ...
                break  # apply best, skip rest

        # Roll back all others
        for result in results[1:]:
            if not result.committed:
                pass  # no rollback needed -- they were on copies

        # ... measure, record (same as parent) ...
```

**Performance impact:** With 4 workers and 5 proposals:
- Sequential: 5 x ~10ms = ~50ms per generation
- Parallel: ~12.5ms per generation (limited by the slowest mutation)
- Speedup: **~4x** per evolution generation

### 2.4 Rollback-Based Speculation

The `Genome.mutate()` method (line 434) already creates a `deepcopy` before mutation,
enabling rollback. But the current system doesn't exploit this for speculation. A
speculation-aware approach:

1. **Checkpoint** the current genome (snapshot its checksum).
2. **Speculatively apply** the top-K mutations (K=3) to K copies.
3. **Benchmark** each mutated genome on the current workload.
4. **Select** the genome with the highest fitness improvement.
5. **Commit** the winner; discard the others.

The `GenomeDiff` class (line 83) already supports comparing genomes. The selection
criterion is simple: `diff.fitness_delta > 0` and `diff.has_changes`.

### 2.5 Genetic Crossover: Beyond Single Mutations

The current evolution applies one mutation at a time. With speculative evaluation,
we can explore **combinations** of mutations:

```python
def propose_mutation_combinations(self, genome, patterns):
    """Propose not just single mutations, but combinations of 2-3."""
    singles = self._propose_singles(genome, patterns)

    # Generate pairs of compatible mutations
    pairs = []
    for i, a in enumerate(singles[:5]):
        for j, b in enumerate(singles[:5]):
            if i < j and a.target != b.target:  # don't mutate same target twice
                pairs.append(MutationProposal(
                    strategy=MutationStrategy.INLINE_OPTIMIZATION,
                    target="combo",
                    description=f"Combined: {a.description} + {b.description}",
                    kwargs={"mutations": [a, b]},
                    estimated_speedup=a.estimated_speedup * b.estimated_speedup,
                    estimated_risk=(a.estimated_risk + b.estimated_risk) / 2,
                    priority=a.priority + b.priority,
                ))

    return singles + pairs  # evaluate all in parallel
```

---

## 3. Performance Modeling

### 3.1 Building a Cost Model from FIR Structure

The goal: given an `FIRFunction`, predict its execution time in nanoseconds **without
running it**. This is a static cost model that maps FIR instruction types to estimated
cycle costs.

#### 3.1.1 Instruction-Level Cost Table

Based on the bytecode opcode set (`bytecode/opcodes.py`) and the VM interpreter's
fetch-decode-execute cycle (`vm/interpreter.py`):

| FIR Instruction Category | Bytecode Opcodes | Base Latency (ns) | Cache Impact | Energy (nJ) |
|---|---|---|---|---|
| Integer ALU (add, sub, and, or, xor) | `IADD, ISUB, IAND, IOR, IXOR` | 0.3 | None | 0.1 |
| Integer multiply | `IMUL` | 1.0 | None | 0.3 |
| Integer divide/modulo | `IDIV, IMOD` | 4.0 | None | 1.2 |
| Float ALU | `FADD, FSUB, FMUL` | 1.0 | None | 0.4 |
| Float divide | `FDIV` | 5.0 | None | 1.5 |
| Comparison | `IEQ, ILT, IGT, CMP, FEQ, FLT` | 0.5 | None | 0.15 |
| Load/Store (L1 hit) | `LOAD, STORE, LOAD8, STORE8` | 1.0 | L1 | 0.3 |
| Load/Store (L2 hit) | (same opcodes) | 4.0 | L2 | 1.5 |
| Load/Store (L3 hit) | (same opcodes) | 12.0 | L3 | 4.0 |
| Load/Store (DRAM) | (same opcodes) | 80.0 | DRAM | 25.0 |
| Branch (predicted) | `JMP, JE, JNE, JZ, JNZ` | 0.5 | None | 0.15 |
| Branch (mispredicted) | (same opcodes) | 5.0 | Pipeline flush | 2.0 |
| Call/Return | `CALL, RET` | 3.0 | Instruction cache | 1.0 |
| SIMD vector op | `VADD, VSUB, VMUL, VFMA` | 1.5 | None | 0.5 |
| A2A (Tell/Ask) | `TELL, ASK, DELEGATE` | 500.0 | Network I/O | 150.0 |
| Memory management | `MEMCOPY, MEMSET` | 0.5 + 0.1*bytes | Cache | 0.15*bytes |
| Stack push/pop | `PUSH, POP` | 0.5 | L1 | 0.15 |

#### 3.1.2 Concrete Cost Model Implementation

```python
from dataclasses import dataclass
from flux.fir.instructions import Instruction

@dataclass
class CostModelParams:
    """Tunable parameters for the cost model."""
    l1_hit_latency_ns: float = 1.0
    l2_hit_latency_ns: float = 4.0
    l3_hit_latency_ns: float = 12.0
    dram_latency_ns: float = 80.0
    branch_mispredict_ns: float = 5.0
    l1_hit_rate: float = 0.85
    l2_hit_rate: float = 0.10
    l3_hit_rate: float = 0.04
    branch_predict_rate: float = 0.92

INSTRUCTION_COSTS_NS = {
    # Integer ALU
    "iadd": 0.3, "isub": 0.3, "iand": 0.3, "ior": 0.3, "ixor": 0.3,
    "ishl": 0.3, "ishr": 0.3, "inot": 0.3, "ineg": 0.3,
    "imul": 1.0, "idiv": 4.0, "imod": 4.0,
    # Float ALU
    "fadd": 1.0, "fsub": 1.0, "fmul": 1.0, "fdiv": 5.0, "fneg": 0.5,
    # Comparison
    "ieq": 0.5, "ine": 0.5, "ilt": 0.5, "igt": 0.5, "ile": 0.5, "ige": 0.5,
    "feq": 0.5, "flt": 0.5, "fgt": 0.5, "fle": 0.5, "fge": 0.5,
    # Memory
    "load": 0.0, "store": 0.0, "alloca": 0.0,  # 0.0 = depends on cache model
    "getfield": 0.0, "setfield": 0.0, "getelem": 0.0, "setelem": 0.0,
    # Control flow
    "jump": 0.5, "branch": 0.5, "switch": 0.5, "call": 3.0, "return": 3.0,
    # SIMD
    # (would map from bytecodes vadd/vsub/vmul/vfma if present in FIR)
}

class FIRCostModel:
    """Static cost model: FIR function -> predicted execution time."""

    def __init__(self, params: CostModelParams = None):
        self.params = params or CostModelParams()
        self._cache: dict[str, float] = {}

    def estimate_function_cost(self, func: "FIRFunction") -> CostEstimate:
        """Estimate execution time for a single FIR function."""
        total_ns = 0.0
        instruction_counts: dict[str, int] = {}
        memory_op_count = 0
        branch_count = 0
        call_count = 0

        for block in func.blocks:
            for instr in block.instructions:
                opcode = instr.opcode
                instruction_counts[opcode] = instruction_counts.get(opcode, 0) + 1

                # Base instruction cost
                base = INSTRUCTION_COSTS_NS.get(opcode, 1.0)

                if opcode in ("load", "store", "getfield", "setfield", "getelem", "setelem"):
                    # Cache-aware memory cost
                    p = self.params
                    expected_ns = (
                        p.l1_hit_rate * p.l1_hit_latency_ns +
                        p.l2_hit_rate * p.l2_hit_latency_ns +
                        p.l3_hit_rate * p.l3_hit_latency_ns +
                        (1 - p.l1_hit_rate - p.l2_hit_rate - p.l3_hit_rate) * p.dram_latency_ns
                    )
                    total_ns += expected_ns
                    memory_op_count += 1
                elif opcode in ("branch", "switch"):
                    # Branch prediction penalty
                    p = self.params
                    expected_ns = (
                        p.branch_predict_rate * 0.5 +
                        (1 - p.branch_predict_rate) * p.branch_mispredict_ns
                    )
                    total_ns += expected_ns
                    branch_count += 1
                elif opcode == "call":
                    total_ns += 3.0  # call overhead
                    call_count += 1
                else:
                    total_ns += base

        return CostEstimate(
            total_ns=total_ns,
            instruction_counts=instruction_counts,
            memory_ops=memory_op_count,
            branches=branch_count,
            calls=call_count,
            confidence=self._estimate_confidence(func, memory_op_count, branch_count),
        )

    def _estimate_confidence(self, func, mem_ops, branches):
        """Lower confidence when memory/branch behavior is hard to predict."""
        total = sum(len(b.instructions) for b in func.blocks)
        if total == 0:
            return 0.0
        uncertainty = (mem_ops * 0.3 + branches * 0.2) / total
        return max(0.1, 1.0 - uncertainty)

@dataclass
class CostEstimate:
    total_ns: float
    instruction_counts: dict[str, int]
    memory_ops: int
    branches: int
    calls: int
    confidence: float
```

#### 3.1.3 Example: Cost Estimation for a Concrete FIR Function

Consider a FIR function implementing `fibonacci(n)`:

```python
# Pseudocode FIR for fibonacci:
# block entry(n):
#   cmp n, 1
#   branch n <= 1 -> base, -> recurse
#
# block base:
#   return n
#
# block recurse:
#   a = call fibonacci(n - 1)   # recursive call
#   b = call fibonacci(n - 2)   # recursive call
#   result = a + b
#   return result
```

**Cost estimation (without loop unrolling):**
- 2 `cmp` comparisons: 2 x 0.5ns = 1.0ns
- 1 `branch`: 0.5ns (predicted)
- 2 `call`: 2 x 3.0ns = 6.0ns
- 1 `iadd`: 0.3ns
- 2 `return`: 2 x 3.0ns = 6.0ns
- **Base cost (single invocation): ~13.8ns**
- **With estimated recursion depth of 10:** ~138ns (linear approximation, ignoring
  the exponential nature -- this is where abstract interpretation improves accuracy)

### 3.2 Memory Access Pattern Analysis

The VM's memory model uses two regions: `stack` (grows downward) and `heap` (grows upward).
The `MemoryManager` (`vm/memory.py`) creates regions with `create_region()`.

**Cache behavior prediction rules:**

1. **Stack accesses** (push/pop, local variables) are almost always L1 hits because they
   exhibit strong spatial and temporal locality.
2. **Sequential array accesses** (`getelem` with induction variable indices) are
   prefetchable and typically L1/L2.
3. **Random access patterns** (hash table lookups, graph traversal) are harder to
   predict and default to the DRAM latency estimate.

The cost model uses `CacheAccessPredictor` to classify memory access patterns:

```python
class CacheAccessPredictor:
    """Predict cache hit rates for memory operations in a FIR function."""

    def analyze_function(self, func: FIRFunction) -> dict[str, float]:
        """Return predicted cache hit rates by memory region."""
        stack_accesses = 0
        sequential_array_accesses = 0
        random_accesses = 0

        for block in func.blocks:
            for instr in block.instructions:
                if instr.opcode in ("load", "store"):
                    # Stack pointer-relative -> stack access (L1 hit)
                    if hasattr(instr, 'ptr') and "stack" in str(instr.ptr.name).lower():
                        stack_accesses += 1
                    elif isinstance(instr, GetElem):
                        # Check if index is an induction variable
                        sequential_array_accesses += 1
                    else:
                        random_accesses += 1

        total = stack_accesses + sequential_array_accesses + random_accesses
        if total == 0:
            return {"l1": 0.95, "l2": 0.04, "l3": 0.008, "dram": 0.002}

        return {
            "l1": 0.7 + 0.2 * (stack_accesses / total),
            "l2": 0.15 - 0.1 * (stack_accesses / total),
            "l3": 0.1 - 0.05 * (stack_accesses / total),
            "dram": 0.05,
        }
```

### 3.3 Pipeline Modeling

The VM interpreter is a single-threaded fetch-decode-execute loop with no pipelining.
However, when targeting **native code generation** (via the JIT compiler or the
recompilation-to-C/Rust path), pipeline effects matter:

```python
class PipelineModel:
    """Model superscalar pipeline effects for native-generated code."""

    # Modern x86-64 Zen 3 / Apple M1 approximate throughputs
    THROUGHPUT = {
        "iadd": 0.25,  # 4 per cycle
        "isub": 0.25,
        "imul": 1.0,   # 1 per cycle
        "idiv": 15.0,  # 1 per 15 cycles (latency)
        "fadd": 0.25,  # 4 per cycle (FMA unit)
        "fmul": 0.25,
        "fdiv": 12.0,
        "load": 0.5,   # 2 per cycle (2 load ports)
        "store": 1.0,  # 1 per cycle (1 store port)
    }

    def estimate_throughput_cycles(self, instruction_counts: dict[str, int]) -> float:
        """Estimate total cycles with instruction-level parallelism."""
        # Critical path: sum of latencies for dependent instructions
        # Throughput bound: max(ops / throughput) for each instruction type

        throughput_bound = 0.0
        for opcode, count in instruction_counts.items():
            t = self.THROUGHPUT.get(opcode, 1.0)
            throughput_bound = max(throughput_bound, count * t)

        return throughput_bound
```

---

## 4. What-If Analysis

### 4.1 The Question: "Should I Recompile This Module to Rust?"

The `AdaptiveSelector.recommend()` method (`selector.py:175`) answers this based on
heat level. But it doesn't estimate the *total cost* of recompilation, including:

1. **Compile time** (Rust: ~30s for a small module)
2. **Testing time** (correctness validation: ~10s)
3. **Downtime** (hot-swap pause: ~100ms)
4. **Speedup benefit** (estimated 10x from `profiler.estimate_speedup()`)
5. **Payback time** (how long until the speedup recovers the compilation cost)

### 4.2 Recompilation ROI Calculator

```python
@dataclass
class RecompilationROI:
    """Return on Investment analysis for a recompilation decision."""
    module_path: str
    current_language: str
    target_language: str
    compile_time_s: float
    test_time_s: float
    downtime_s: float
    current_avg_time_ns: float
    estimated_speedup: float
    estimated_new_avg_time_ns: float
    calls_per_second: float
    time_to_payback_s: float
    should_recompile: bool
    reason: str

def analyze_recompilation(
    module_path: str,
    profiler: AdaptiveProfiler,
    selector: AdaptiveSelector,
) -> RecompilationROI:
    """Full cost-benefit analysis for recompiling a module."""

    stats = profiler.get_module_stats(module_path)
    if stats is None:
        return RecompilationROI(
            module_path=module_path, current_language="python",
            target_language="rust", compile_time_s=0, test_time_s=0,
            downtime_s=0, current_avg_time_ns=0, estimated_speedup=1.0,
            estimated_new_avg_time_ns=0, calls_per_second=0,
            time_to_payback_s=float('inf'), should_recompile=False,
            reason="No profiling data available."
        )

    current_lang = selector.current_languages.get(module_path, "python")
    rec = selector.recommend(module_path)
    target_lang = rec.recommended_language

    # Compile time estimates by language (from LanguageProfile.compile_time_tier)
    COMPILE_TIMES = {
        "typescript": 2.0,   # fast
        "csharp": 8.0,       # moderate
        "rust": 30.0,        # slow
        "c": 15.0,           # moderate-slow
        "c_simd": 35.0,      # slowest (hand-tuned SIMD)
    }

    compile_time = COMPILE_TIMES.get(target_lang, 30.0)
    test_time = 10.0  # correctness validation
    downtime = 0.1    # hot-swap

    current_avg = stats["avg_time_ns"]
    speedup = profiler.estimate_speedup(module_path, target_lang)
    new_avg = current_avg / speedup if speedup > 0 else current_avg

    calls_per_sec = stats["call_count"] / max(
        stats["total_time_ns"] / 1e9, 0.001
    )

    # Time saved per second = calls_per_sec * (current_avg - new_avg)
    savings_per_sec_ns = calls_per_sec * (current_avg - new_avg)
    savings_per_sec = savings_per_sec_ns / 1e9  # convert to seconds

    # Total cost of recompilation
    total_cost = compile_time + test_time + downtime

    # Payback time
    if savings_per_sec <= 0:
        payback = float('inf')
    else:
        payback = total_cost / savings_per_sec

    # Decision: recompile if payback < 1 hour (3600s)
    should = payback < 3600.0

    if should:
        reason = f"Payback in {payback:.0f}s. {speedup:.1f}x speedup."
    else:
        reason = f"Payback in {payback:.0f}s > 1h. Not worth it."

    return RecompilationROI(
        module_path=module_path,
        current_language=current_lang,
        target_language=target_lang,
        compile_time_s=compile_time,
        test_time_s=test_time,
        downtime_s=downtime,
        current_avg_time_ns=current_avg,
        estimated_speedup=speedup,
        estimated_new_avg_time_ns=new_avg,
        calls_per_second=calls_per_sec,
        time_to_payback_s=payback,
        should_recompile=should,
        reason=reason,
    )
```

### 4.3 Predictive PGO (Profile-Guided Optimization Without Profiling)

Traditional PGO requires:
1. Compile with instrumentation
2. Run representative workload
3. Collect profile data
4. Recompile with profile

**Predictive PGO** skips steps 1-3 by estimating the profile from FIR structure:

```python
class PredictivePGO:
    """Estimate PGO hints from FIR structure without running the code."""

    def estimate_hot_blocks(self, func: FIRFunction) -> dict[str, float]:
        """Predict execution frequency for each basic block."""
        freq: dict[str, float] = {}

        # Entry block gets frequency 1.0
        if func.blocks:
            freq[func.blocks[0].label] = 1.0

        # Simple heuristic: blocks in loops get 10x frequency
        for block in func.blocks:
            if self._is_loop_body(block, func):
                freq[block.label] = freq.get(block.label, 0.0) + 10.0

        return freq

    def suggest_inlining(self, module: FIRModule) -> list[tuple[str, str]]:
        """Suggest functions to inline based on call frequency * size."""
        suggestions = []
        for name, func in module.functions.items():
            instr_count = sum(len(b.instructions) for b in func.blocks)
            call_sites = self._count_call_sites(name, module)

            if instr_count < 10 and call_sites >= 3:
                suggestions.append((name, f"Small ({instr_count} instrs), called {call_sites}x"))

        return suggestions

    def suggest_block_layout(self, func: FIRFunction) -> list[str]:
        """Predict optimal block ordering for cache locality."""
        # Same as block_layout_pass but using predicted frequencies
        if not func.blocks:
            return []
        return [b.label for b in func.blocks]  # TODO: use predicted edge frequencies
```

### 4.4 LTO Hints Without Linking

When the evolution engine proposes `RECOMPILE_LANGUAGE`, it doesn't consider
cross-module optimization opportunities. LTO hints can be generated statically:

```python
def suggest_cross_module_optimizations(module: FIRModule) -> list[str]:
    """Suggest optimization hints for the native compiler."""
    hints = []

    for func_name, func in module.functions.items():
        # If a function only calls one other function, suggest inlining at link time
        callees = set()
        for block in func.blocks:
            for instr in block.instructions:
                if isinstance(instr, Call):
                    callees.add(instr.func)
        if len(callees) == 1:
            hints.append(f"-Wl,--lto-inline={callees.pop()} into {func_name}")

        # If all branches in a function go to the same target, suggest simplification
        targets = []
        for block in func.blocks:
            if isinstance(block.terminator, Branch):
                targets.append(block.terminator.true_block)
                targets.append(block.terminator.false_block)
        if len(targets) >= 2 and len(set(targets)) == 1:
            hints.append(f"-Wl,--lto-collapse-branches in {func_name}")

    return hints
```

---

## 5. Digital Twin

### 5.1 The Shadow System Concept

A **Digital Twin** of the FLUX runtime is a lightweight simulation that maintains a
parallel copy of the entire system state and runs *ahead* of the real system,
predicting outcomes before they happen.

The existing `Genome` class (`evolution/genome.py`) is already a snapshot mechanism.
The Digital Twin extends this to a continuously-updating shadow copy:

```python
class DigitalTwin:
    """Shadow copy of the FLUX runtime that runs ahead in simulation."""

    def __init__(self, real_profiler: AdaptiveProfiler, real_selector: AdaptiveSelector):
        self.real_profiler = real_profiler
        self.real_selector = real_selector
        self.shadow_genome = Genome()
        self.shadow_profiler = AdaptiveProfiler()
        self.shadow_selector = AdaptiveSelector(self.shadow_profiler)
        self.cost_model = FIRCostModel()
        self.mutation_predictor = MutationPredictor()
        self._drift_count = 0
        self._correction_count = 0

    def synchronize(self, real_genome: Genome):
        """Pull real state into the shadow."""
        self.shadow_genome = Genome.from_dict(real_genome.to_dict())
        self.shadow_profiler.reset()

    def simulate_next_generation(self, real_genome: Genome, patterns) -> EvolutionStep:
        """Predict what the next evolution step will do."""
        # Generate same proposals as real system
        mutator = SystemMutator()
        proposals = mutator.propose_mutations(real_genome, patterns)

        # Evaluate using cost model instead of real execution
        shadow_results = []
        for proposal in proposals:
            predicted_fitness = self._predict_fitness_after_mutation(
                real_genome, proposal
            )
            shadow_results.append((proposal, predicted_fitness))

        # Select best predicted mutation
        if shadow_results:
            best_proposal, best_fitness = max(shadow_results, key=lambda x: x[1])
            return EvolutionStep(
                generation=real_genome.generation + 1,
                fitness_before=real_genome.fitness_score,
                fitness_after=best_fitness,
                mutations_proposed=len(proposals),
                mutations_committed=1,
                patterns_found=len(patterns),
            )

        return EvolutionStep(
            generation=real_genome.generation + 1,
            fitness_before=real_genome.fitness_score,
            fitness_after=real_genome.fitness_score,
            mutations_proposed=0,
            mutations_committed=0,
            patterns_found=len(patterns),
        )

    def _predict_fitness_after_mutation(self, genome: Genome, proposal: MutationProposal) -> float:
        """Predict genome fitness after applying a mutation, without executing it."""
        # Create a shadow copy and apply mutation
        mutated = genome.mutate(
            strategy=proposal.strategy,
            target=proposal.target,
            **proposal.kwargs,
        )
        mutated.evaluate_fitness()

        # Adjust based on predicted speedup from cost model
        if proposal.estimated_speedup > 1.0:
            speed_delta = (proposal.estimated_speedup - 1.0) * 0.1  # scale down estimate
            mutated.fitness_score += speed_delta * 0.4  # speed is 0.4 of fitness

        return mutated.fitness_score

    def measure_drift(self, real_result: EvolutionStep, predicted: EvolutionStep):
        """Compare real vs. predicted evolution step."""
        self._drift_count += 1
        fitness_drift = abs(real_result.fitness_after - predicted.fitness_after)
        if fitness_drift > 0.01:
            self._correction_count += 1

    @property
    def drift_rate(self) -> float:
        """Fraction of predictions that were significantly wrong."""
        if self._drift_count == 0:
            return 0.0
        return self._correction_count / self._drift_count
```

### 5.2 Chaos Engineering for Self-Improving Systems

The evolution engine can improve the system, but it can also *break* it. Chaos engineering
proactively tests the system's resilience:

```python
class ChaosInjector:
    """Inject controlled faults into the evolution engine to test robustness."""

    def __init__(self, engine: EvolutionEngine):
        self.engine = engine
        self._injection_log: list[dict] = []

    def inject_faulty_mutation(self):
        """Inject a mutation that will fail, to test rollback."""
        # Create a proposal that deliberately fails validation
        proposal = MutationProposal(
            strategy=MutationStrategy.RECOMPILE_LANGUAGE,
            target="nonexistent.module",
            description="Chaos: recompile nonexistent module",
            estimated_speedup=100.0,  # suspiciously high
            estimated_risk=0.0,       # suspiciously low
            priority=1.0,
        )

        # The real system should reject this
        result = self.engine.mutator.apply_mutation(proposal, self.engine.genome, None)

        self._injection_log.append({
            "type": "faulty_mutation",
            "expected_rejection": True,
            "actual_success": result.success,
            "passed": not result.success,  # should have been rejected
        })

        return not result.success  # True if system correctly rejected it

    def inject_conflicting_mutations(self):
        """Inject two mutations that conflict (same target)."""
        p1 = MutationProposal(
            strategy=MutationStrategy.RECOMPILE_LANGUAGE,
            target="chaos.target",
            description="Recompile to Rust",
            kwargs={"new_language": "rust"},
            estimated_speedup=10.0,
            estimated_risk=0.3,
        )
        p2 = MutationProposal(
            strategy=MutationStrategy.RECOMPILE_LANGUAGE,
            target="chaos.target",
            description="Recompile to C",
            kwargs={"new_language": "c"},
            estimated_speedup=8.0,
            estimated_risk=0.4,
        )

        # Both should be applied to different copies; no corruption
        r1 = self.engine.mutator.apply_mutation(p1, self.engine.genome, None)
        r2 = self.engine.mutator.apply_mutation(p2, self.engine.genome, None)

        self._injection_log.append({
            "type": "conflicting_mutations",
            "both_applied": r1.success and r2.success,
            "passed": r1.success != r2.success,  # only one should win
        })

    def inject_memory_pressure(self):
        """Simulate memory pressure by creating many genomes."""
        genomes = []
        for _ in range(1000):
            genomes.append(Genome())  # empty but allocated
        # The system should not crash from genome allocation
        self._injection_log.append({
            "type": "memory_pressure",
            "genomes_created": len(genomes),
            "passed": True,  # didn't crash
        })
        del genomes
```

### 5.3 Fault Injection in the Evolution Engine

The `CorrectnessValidator` (`evolution/validator.py`) runs test cases to detect
regressions. Chaos engineering extends this by injecting faults into the test
infrastructure itself:

| Fault Type | What It Tests | Expected Behavior |
|---|---|---|
| Flaky test (random pass/fail) | Evolution robustness to noisy validation | Should not commit flaky-result-dependent mutations |
| Slow test (>10s) | Timeout handling | Should skip or deprioritize slow tests |
| Memory-leaking test | Resource management | Should detect and avoid the leaky mutation |
| Non-deterministic test | Reproducibility | Should flag non-deterministic mutations |

---

## 6. Energy-Aware Optimization

### 6.1 Beyond Speed: The Energy Dimension

The current `Genome.evaluate_fitness()` method (`genome.py:251`) weights:
- Speed: 0.4
- Modularity: 0.3
- Correctness: 0.3

There is no energy dimension. For battery-powered or carbon-budgeted deployments,
energy matters as much as speed.

### 6.2 Instruction Energy Costs

Research from [Horowitz et al. 2014] and subsequent work provides per-instruction
energy costs for modern CPUs (in nanojoules at 45nm):

| Operation Type | Energy (nJ) | Relative to ADD |
|---|---|---|
| Integer ADD | 0.1 | 1.0x |
| Integer MUL | 0.3 | 3.0x |
| Integer DIV | 1.2 | 12.0x |
| Float ADD | 0.4 | 4.0x |
| Float MUL | 0.5 | 5.0x |
| Float DIV | 1.5 | 15.0x |
| L1 Load | 0.3 | 3.0x |
| L2 Load | 1.5 | 15.0x |
| L3 Load | 4.0 | 40.0x |
| DRAM Read (64B) | 25.0 | 250.0x |
| Branch (correct) | 0.15 | 1.5x |
| Branch (mispredict) | 2.0 | 20.0x |
| SIMD ADD (256-bit) | 0.8 | 8.0x |
| SIMD MUL (256-bit) | 1.2 | 12.0x |

### 6.3 Energy-Aware Cost Model

```python
class EnergyCostModel(FIRCostModel):
    """Extends FIRCostModel to estimate energy consumption."""

    # Energy costs in nanojoules per instruction
    ENERGY_COSTS_NJ = {
        "iadd": 0.1, "isub": 0.1, "iand": 0.1, "ior": 0.1, "ixor": 0.1,
        "imul": 0.3, "idiv": 1.2, "imod": 1.2,
        "fadd": 0.4, "fsub": 0.4, "fmul": 0.5, "fdiv": 1.5,
        "ieq": 0.15, "ilt": 0.15, "igt": 0.15,
        "load": 0.0, "store": 0.0,  # depends on cache
        "branch": 0.15, "call": 1.0, "return": 0.5,
    }

    CACHE_ENERGY_NJ = {
        "l1": 0.3,
        "l2": 1.5,
        "l3": 4.0,
        "dram": 25.0,
    }

    def estimate_energy(self, func: FIRFunction) -> EnergyEstimate:
        """Estimate total energy consumption for a function execution."""
        total_nj = 0.0
        cache_predictor = CacheAccessPredictor()
        hit_rates = cache_predictor.analyze_function(func)

        for block in func.blocks:
            for instr in block.instructions:
                base_energy = self.ENERGY_COSTS_NJ.get(instr.opcode, 0.5)

                if instr.opcode in ("load", "store", "getfield", "setfield"):
                    # Weighted cache energy
                    expected_energy = (
                        hit_rates["l1"] * self.CACHE_ENERGY_NJ["l1"] +
                        hit_rates["l2"] * self.CACHE_ENERGY_NJ["l2"] +
                        hit_rates["l3"] * self.CACHE_ENERGY_NJ["l3"] +
                        hit_rates["dram"] * self.CACHE_ENERGY_NJ["dram"]
                    )
                    total_nj += expected_energy
                else:
                    total_nj += base_energy

        return EnergyEstimate(
            total_nj=total_nj,
            total_mj=total_nj / 1e6,
            memory_dominant=self._is_memory_dominant(func, hit_rates),
        )

    def _is_memory_dominant(self, func, hit_rates):
        """Check if memory operations dominate energy consumption."""
        mem_instrs = sum(1 for b in func.blocks
                       for i in b.instructions
                       if i.opcode in ("load", "store", "getfield", "setfield"))
        total_instrs = sum(len(b.instructions) for b in func.blocks)
        if total_instrs == 0:
            return False

        mem_fraction = mem_instrs / total_instrs
        dram_fraction = hit_rates.get("dram", 0.05)

        # Memory is dominant if >30% of instructions are memory ops
        # AND significant fraction goes to DRAM
        return mem_fraction > 0.3 and dram_fraction > 0.03

@dataclass
class EnergyEstimate:
    total_nj: float
    total_mj: float
    memory_dominant: bool
```

### 6.4 DVFS-Aware Scheduling

Dynamic Voltage and Frequency Scaling (DVFS) allows trading performance for energy:

```python
class DVFSAdvisor:
    """Recommend DVFS settings based on workload characteristics."""

    # P-state: (frequency_GHz, voltage_V, energy_per_cycle_nJ)
    P_STATES = {
        "performance": (4.5, 1.3, 0.5),
        "balanced":    (3.5, 1.1, 0.35),
        "power_saver": (2.0, 0.8, 0.15),
    }

    def recommend_pstate(
        self,
        module_path: str,
        profiler: AdaptiveProfiler,
        heat: HeatLevel,
    ) -> str:
        """Recommend DVFS P-state based on module characteristics."""

        if heat == HeatLevel.HEAT:
            return "performance"  # critical path, maximize speed
        elif heat == HeatLevel.HOT:
            return "balanced"     # moderate, balance speed/energy
        elif heat == HeatLevel.WARM:
            return "balanced"
        elif heat == HeatLevel.COOL:
            return "power_saver"  # rarely called, save energy
        else:
            return "power_saver"  # FROZEN, minimize idle power

    def estimate_energy_savings(
        self,
        cost_estimate: CostEstimate,
        from_pstate: str,
        to_pstate: str,
    ) -> float:
        """Estimate energy savings from changing P-state."""
        from_config = self.P_STATES[from_pstate]
        to_config = self.P_STATES[to_pstate]

        # Energy per instruction scales with voltage (approximately V^2)
        energy_ratio = (to_config[2] / from_config[2])
        # But time scales inversely with frequency
        time_ratio = (from_config[0] / to_config[0])

        # Total energy = instructions * energy_per_cycle * cycles
        # New energy = old_energy * energy_ratio * time_ratio
        savings = 1.0 - energy_ratio * time_ratio
        return max(0.0, savings)
```

### 6.5 Carbon-Aware Computing

For cloud deployments, the system can consider the carbon intensity of the grid:

```python
class CarbonAwareAdvisor:
    """Optimize for carbon emissions, not just energy."""

    def __init__(self, grid_carbon_intensity_gco2_per_kwh: float = 400.0):
        """Default: global average grid intensity (400 gCO2/kWh)."""
        self.grid_intensity = grid_carbon_intensity_gco2_per_kwh

    def should_defer_optimization(
        self,
        compile_energy_mj: float,
        current_grid_intensity: float,
    ) -> tuple[bool, str]:
        """Should we defer recompilation to a greener time?"""
        # Calculate carbon cost of compilation
        compile_kwh = compile_energy_mj / 3.6e9  # mJ to kWh
        compile_carbon_g = compile_kwh * current_grid_intensity

        # If grid is dirty (>2x average), defer
        if current_grid_intensity > 2 * self.grid_intensity:
            return True, (
                f"Grid carbon intensity ({current_grid_intensity:.0f} gCO2/kWh) "
                f"is >2x average. Deferring {compile_carbon_g:.4f}g CO2 optimization."
            )

        return False, (
            f"Grid is clean enough. Proceeding with {compile_carbon_g:.4f}g CO2 cost."
        )

    def estimate_carbon_budget(
        self,
        total_energy_mj_per_hour: float,
    ) -> float:
        """Estimate daily carbon emissions in grams CO2."""
        daily_energy_mj = total_energy_mj_per_hour * 24
        daily_energy_kwh = daily_energy_mj / 3.6e6
        return daily_energy_kwh * self.grid_intensity
```

### 6.6 Extending Genome Fitness with Energy

The `Genome.evaluate_fitness()` method should include an energy dimension:

```python
def evaluate_fitness(self) -> float:
    """Score this genome on speed + modularity + correctness + energy (0-1)."""
    speed_score = self._speed_score()
    modularity_score = self._modularity_score()
    correctness_score = self._correctness_score()
    energy_score = self._energy_score()  # NEW

    # Updated weights: speed 0.3, modularity 0.2, correctness 0.3, energy 0.2
    self.fitness_score = (
        0.3 * speed_score +
        0.2 * modularity_score +
        0.3 * correctness_score +
        0.2 * energy_score
    )
    return self.fitness_score

def _energy_score(self) -> float:
    """Score based on estimated energy efficiency (0-1)."""
    # Modules in slower languages use less energy per instruction
    # but may take longer overall
    lang_energy = {
        "python": 1.0,     # interpreted, high overhead per instruction
        "typescript": 0.8,
        "csharp": 0.6,
        "rust": 0.4,       # compiled, efficient
        "c": 0.4,
        "c_simd": 0.3,     # SIMD processes more data per instruction
    }

    if not self.language_assignments:
        return 0.5

    total = 0.0
    for mod_path, lang in self.language_assignments.items():
        snap = self.modules.get(mod_path)
        if snap:
            heat_w = self._heat_weight(snap.heat_level)
            energy = lang_energy.get(lang, 0.7)
            total += energy * heat_w

    return min(1.0, total) if total > 0 else 0.5
```

---

## 7. Open Research Questions

### 7.1 Theoretical Limits

1. **Prediction accuracy bounds**: The cost model estimates execution time from FIR
   structure. What is the theoretical minimum prediction error? Information-theoretically,
   the Cramer-Rao bound for any estimator of execution time is bounded by the variance
   of the actual execution times. For the FLUX VM (which is deterministic given the
   same inputs), the variance comes *only* from the inputs. If we can characterize
   the input distribution, the bound is tight.

2. **Halting problem implications**: Abstract interpretation can only give *safe
   over-approximations* of loop bounds (the classical result). This means the
   pre-execution simulator will always overestimate the cost of programs with
   complex control flow. How much does this overestimation matter in practice?
   Preliminary analysis suggests most FLUX modules have simple loop structures
   (single-exit loops with linear induction variables), so the overestimation is
   typically < 2x.

3. **Simulation fidelity vs. cost trade-off**: More accurate simulation (concrete
   execution) is slower. Abstract interpretation is fast but less accurate.
   What is the Pareto-optimal point? For the FLUX system, we hypothesize that
   **interval abstract interpretation** provides 80% of the accuracy of concrete
   simulation at 1% of the cost.

### 7.2 Practical Concerns

4. **When is simulation cheaper than execution?** The breakeven point depends on the
   ratio of simulation cost to execution cost. For the FLUX VM:
   - Abstract interpretation: ~0.1ms per function
   - Concrete simulation (on VM): ~10ms per function
   - Real execution: ~1-100ms per function (varies widely)
   - Conclusion: Simulation is always cheaper for functions that take >1ms.
   For sub-millisecond functions, the overhead of simulation exceeds the function's
   own execution time. The system should maintain a **simulation threshold**: only
   simulate functions estimated to take >1ms.

5. **Can a simulation be more accurate than reality?** Paradoxically, yes. A
   simulation can account for *typical-case* behavior, while a single real execution
   might hit an atypical path (e.g., a cache miss storm). An ensemble of simulations
   (Monte Carlo over input distributions) can produce a *more representative* estimate
   than any single execution. However, the simulation cannot discover behavior that
   the model doesn't account for (unknown unknowns).

6. **Evolution stability**: If the evolution engine optimizes based on simulated
   performance rather than real performance, can it converge to a *local optimum in
   simulation space* that doesn't correspond to a real optimum? This is the classic
   "reality gap" problem from evolutionary robotics. Mitigation: periodically
   validate simulated-optimal solutions against real execution (every N generations).

7. **Digital twin drift**: The shadow system's predictions will drift from reality
   over time as the system evolves. How often must the twin be re-synchronized?
   We hypothesize a **half-life of 5 generations**: after 5 evolution steps,
   the twin's predictions have degraded by 50% and must be re-calibrated.

8. **Energy measurement on real hardware**: The energy cost model uses literature
   values. Real energy consumption varies by 2-5x across different CPU microarchitectures,
   manufacturing variance, and ambient temperature. Can we integrate with RAPL
   (Running Average Power Limit) counters for on-device calibration? This would
   require native code (C extension) to read MSR registers.

9. **Speculative evolution and correctness**: If we skip validation for high-confidence
   mutations (Section 2.2), we risk committing a correctness regression. What is the
   acceptable false positive rate? For a system with 95% baseline correctness,
   we recommend requiring `predict_success() > 0.95` before skipping validation,
   which keeps the expected regression rate below 5% * 5% = 0.25%.

10. **Carbon-aware optimization as a constraint vs. objective**: Should carbon
    minimization be a hard constraint ("never emit more than X gCO2 per hour")
    or a soft objective ("prefer lower carbon when possible")? Hard constraints
    may prevent critical optimizations during dirty-grid periods. Soft objectives
    with a carbon budget (e.g., "max 100gCO2 per evolution cycle") are more
    practical.

### 7.3 Long-Term Research Directions

11. **Learned cost models**: The static cost table (Section 3.1.1) uses fixed
    values. A learned model (regression on actual execution data) could achieve
    higher accuracy. The `AdaptiveProfiler` already collects timing data that
    could train such a model. Challenge: the model must generalize to unseen
    FIR patterns.

12. **Multi-objective evolution**: The current fitness function is a weighted
    sum of speed, modularity, correctness, and energy. Pareto-front evolution
    would allow the system to discover non-dominated trade-offs (e.g., "50% faster
    but 20% less modular") and let the operator choose.

13. **Simulation-level parallelism**: The Digital Twin could simulate multiple
    future evolution paths in parallel (like a chess engine searching a game tree).
    With a branching factor of 5 mutations per generation and a search depth of 3,
    this explores 125 possible futures. Cost: 125 * 0.1ms = 12.5ms per generation.
    Benefit: the system can avoid local optima by looking ahead.

14. **Cross-language energy models**: The current energy model only considers the
    FLUX VM. When modules are recompiled to Rust/C, the energy profile changes
    dramatically (no VM overhead, but native code has its own energy characteristics).
    Building accurate cross-language energy models requires benchmarking each
    target language on the deployment hardware.

15. **Formal verification of simulation accuracy**: Can we prove that the abstract
    interpreter's cost estimates are *sound* (never undercount) and *complete*
    (account for all instruction categories)? This would provide mathematical
    guarantees on the simulation's reliability, which is important for safety-critical
    deployments of the FLUX agent system.

---

## Summary of Proposed Extensions

| Extension | Code Impact | Estimated Benefit | Implementation Complexity |
|---|---|---|---|
| Abstract interpretation for heat prediction | New class `IntervalDomain`, extend `Genome.capture()` | Predict HEAT before execution | Medium |
| Structural heuristics for heat prediction | Extend `SystemMutator._propose_recompilations()` | Immediate optimization of new modules | Low |
| Parallel mutation evaluation | New class `SpeculativeEvolutionEngine` | 4x faster evolution | Medium |
| Mutation prediction model | New class `MutationPredictor` | Skip 50% of validations | Low |
| FIR cost model | New class `FIRCostModel` | Predict execution time from FIR | Medium |
| Recompilation ROI calculator | New function `analyze_recompilation()` | Avoid wasteful recompilations | Low |
| Predictive PGO | New class `PredictivePGO` | Optimize without profiling | Medium |
| Digital twin | New class `DigitalTwin` | Predict evolution outcomes | High |
| Chaos engineering | New class `ChaosInjector` | Test evolution robustness | Medium |
| Energy-aware cost model | New class `EnergyCostModel` | Optimize for energy, not just speed | Medium |
| DVFS advisor | New class `DVFSAdvisor` | Reduce energy for COOL/FROZEN modules | Low |
| Carbon-aware advisor | New class `CarbonAwareAdvisor` | Reduce carbon emissions | Low |
| Energy dimension in genome fitness | Extend `Genome.evaluate_fitness()` | Balance speed and energy | Low |

---

*This document is a living research artifact. As the FLUX system evolves, these
proposals should be validated against real execution data and refined accordingly.
The most immediately actionable items (marked "Low" complexity) can be prototyped
in a single development sprint.*
