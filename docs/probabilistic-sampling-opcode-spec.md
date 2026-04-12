# FLUX ISA v3 — Probabilistic Sampling Extension Specification

**Document ID:** ISA-PROB-001
**Task Board:** PROB-001
**Status:** Draft
**Author:** Super Z (Fleet Agent, Opcode Design Board)
**Date:** 2026-04-12
**Depends On:** FLUX ISA v3 Unified Specification, ISA-002 Escape Prefix Spec
**Extension Group ID:** 0x00000008
**Extension Name:** `org.flux.prob`
**Opcode Range:** 0xFFD0–0xFFDF
**Version:** 1.0

---

## Table of Contents

1. [Introduction & Motivation](#1-introduction--motivation)
2. [Random Number Generator (RNG)](#2-random-number-generator-rng)
3. [Probability Distribution Format](#3-probability-distribution-format)
4. [Opcode Table](#4-opcode-table)
5. [Opcode Definitions](#5-opcode-definitions)
6. [Binary Encoding](#6-binary-encoding)
7. [Execution Semantics](#7-execution-semantics)
8. [Confidence Integration](#8-confidence-integration)
9. [Interaction with Existing ISA](#9-interaction-with-existing-isa)
10. [Error Handling & Trap Codes](#10-error-handling--trap-codes)
11. [Performance Considerations](#11-performance-considerations)
12. [Bytecode Examples](#12-bytecode-examples)
13. [Formal Semantics](#13-formal-semantics)
14. [Security Considerations](#14-security-considerations)
15. [Appendix](#15-appendix)

---

## 1. Introduction & Motivation

### 1.1 The Stochastic Reasoning Problem

FLUX agents operating in uncertain environments must make decisions under
incomplete information. Core agent tasks that require probabilistic reasoning
include:

- **Exploration vs. exploitation**: Balancing known good actions with
  discovering potentially better alternatives.
- **Decision making under uncertainty**: Choosing actions when outcomes
  are probabilistic.
- **Uncertainty quantification**: Estimating and communicating confidence
  in predictions and beliefs.
- **Bayesian updating**: Incorporating new evidence to refine probability
  estimates.
- **Stochastic simulation**: Monte Carlo methods, particle filtering,
  importance sampling.

The core ISA provides a basic `RND` opcode (0x9A, uniform integer in range)
and `SEED` opcode (0x9B). These are insufficient for:

- Sampling from non-uniform distributions (Gaussian, Gumbel, Bernoulli)
- Computing information-theoretic quantities (entropy, KL divergence)
- Bayesian belief updating with proper probability arithmetic
- Reproducible stochastic execution with independent streams

The probabilistic sampling extension provides a comprehensive instruction set
for stochastic agent reasoning.

### 1.2 Design Goals

1. **Statistical correctness**: All sampling algorithms must produce
   statistically valid samples from the declared distributions.
2. **Reproducibility**: The same seed must produce the same sequence across
   all conformant implementations (bit-identical).
3. **Independence**: Multiple sampling streams must be independent
   (no correlation between streams with different seeds).
4. **Performance**: Sampling overhead must be <100ns per sample on modern
   hardware.
5. **Confidence integration**: Probability values must feed naturally into
   the FLUX confidence system.
6. **Composability**: Sampling results must compose with control flow
   (branching), A2A communication, and other extensions.
7. **Security**: RNG state must not leak sensitive information; entropy
   sources must be available for cryptographic seeding.

### 1.3 Relationship to Existing Opcodes

| Core Opcode | Function | Prob Extension Adds |
|-------------|----------|---------------------|
| RND (0x9A)  | Uniform integer [rs1, rs2] | SAMPLE_UNIFORM (float), multiple distributions |
| SEED (0x9B) | Seed PRNG | PROB_SET_SEED (per-stream), entropy input |
| CONF_LD (0x0E) | Load confidence | Direct probability→confidence mapping |
| C_MERGE (0x68) | Merge confidences | PROB_BAYESIAN_UPDATE (proper Bayesian fusion) |

### 1.4 Statistical Distributions Supported

| Distribution | Opcode | Parameters | Primary Use Case |
|-------------|--------|------------|------------------|
| Uniform     | SAMPLE_UNIFORM | a, b (range) | Exploration, random selection |
| Gaussian    | SAMPLE_GAUSSIAN | μ, σ (mean, std) | Noisy observations, perturbation |
| Gumbel      | SAMPLE_GUMBEL | τ (temperature) | Discrete choice, attention |
| Bernoulli   | SAMPLE_BERNOULLI | p (probability) | Binary decisions, dropout |

Supporting primitives:
| Operation | Opcode | Description |
|-----------|--------|-------------|
| Seed RNG | PROB_SET_SEED | Set RNG seed for reproducibility |
| Bayes update | PROB_BAYESIAN_UPDATE | Update probability with evidence |
| Entropy | ENTROPY_CALC | Shannon entropy of a distribution |
| Store/restore | PROB_STORE_DIST | Persist probability distributions |

---

## 2. Random Number Generator (RNG)

### 2.1 Algorithm: xoshiro256**

The probabilistic extension uses **xoshiro256\*\*** as the primary PRNG.
This generator was chosen for:

- **Speed**: ~1 ns per 64-bit result on modern CPUs.
- **Statistical quality**: Passes all TestU01 Big Crush tests.
- **State size**: 256 bits (4 × u64) — large enough to avoid correlation.
- **Reproducibility**: Deterministic given the same seed.
- **Jump-ahead**: O(1) advance for independent streams.

```
xoshiro256** State:

  state[0]: u64    Internal state word 0
  state[1]: u64    Internal state word 1
  state[2]: u64    Internal state word 2
  state[3]: u64    Internal state word 3

  Total state: 32 bytes

  SplitMix64 seeding:
    def seed_to_state(seed: u64) -> u64[4]:
        s = seed
        def splitmix64():
            nonlocal s
            s += 0x9E3779B97F4A7C15
            z = s
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
            z = (z ^ (z >> 27)) * 0x94D049BB133111EB
            return z ^ (z >> 31)
        return [splitmix64(), splitmix64(), splitmix64(), splitmix64()]

  xoshiro256** next():
    result = rotl(state[1] * 5, 7) * 9
    t = state[1] << 17
    state[2] ^= state[0]
    state[3] ^= state[1]
    state[1] ^= state[2]
    state[0] ^= state[3]
    state[2] ^= t
    state[3] = rotl(state[3], 45)
    return result

  rotl(x, k):
    return (x << k) | (x >> (64 - k))
```

### 2.2 RNG State Registers

The extension maintains **4 independent RNG streams**, each with its own
xoshiro256** state:

```
  RNG Stream Registers:

    rng[0]: { state: u64[4], active: bool, stream_id: 0 }
    rng[1]: { state: u64[4], active: bool, stream_id: 1 }
    rng[2]: { state: u64[4], active: bool, stream_id: 2 }
    rng[3]: { state: u64[4], active: bool, stream_id: 3 }

  Default active stream: rng[0]
  Active stream selector: prng_stream: u2 (0–3)

  On RESET:
    for i in range(4):
      rng[i].active = false
      rng[i].state = [0, 0, 0, 0]  (uninitialized; sampling is a trap)
```

### 2.3 Stream Independence

Streams are made independent via the **jump-ahead** function. Each stream
is initialized by seeding stream 0 with the provided seed, then computing
jump states for streams 1–3:

```
  def init_streams(base_seed: u64):
      rng[0].state = seed_to_state(base_seed)
      rng[0].active = true

      # Jump ahead to create independent streams
      state1 = jump(rng[0].state)
      state2 = jump(state1)
      state3 = jump(state2)

      rng[1].state = state1; rng[1].active = true
      rng[2].state = state2; rng[2].active = true
      rng[3].state = state3; rng[3].active = true

  def jump(state: u64[4]) -> u64[4]:
      """Advance xoshiro256** state by 2^128 steps."""
      result = [0, 0, 0, 0]
      def starjump(s, r, matrix):
          for _ in range(4):
              t = s[0] & matrix[0]
              for j in range(1, 4):
                  t ^= rotl(s[0] & matrix[j], j * 17)
              for j in range(4):
                  s[j] ^= t
          return s

      JUMP_MATRIX = [0x180EC6D33CFD4805, 0xDFBE2B75812E6CB0,
                     0xA943A7B85B497A27, 0x1D31B8A3BBB658B1]
      return starjump(state, result, JUMP_MATRIX)
```

### 2.4 Float Conversion

The 64-bit integer output of xoshiro256** is converted to a float64 in
[0.0, 1.0) using the standard technique:

```
  def u64_to_unit_float(raw: u64) -> f64:
      # Take the upper 53 bits (mantissa precision of float64)
      mantissa = raw >> 11  # 53 bits
      # Construct float64 with exponent for [1.0, 2.0) range
      bits = (mantissa | 0x3FF0000000000000) & 0x7FFFFFFFFFFFFFFF
      return bits_to_f64(bits) - 1.0  # Map [1.0, 2.0) → [0.0, 1.0)
```

For float32 output (used by most sampling opcodes):

```
  def u64_to_unit_f32(raw: u64) -> f32:
      # Take upper 24 bits for float32 mantissa
      mantissa = (raw >> 40) & 0x007FFFFF
      bits = mantissa | 0x3F800000  # Exponent for [1.0, 2.0)
      return bits_to_f32(bits) - 1.0
```

### 2.5 Entropy Input

For cryptographic or security-sensitive applications, the RNG can be seeded
from hardware entropy sources:

```
  def seed_from_entropy():
      entropy = collect_hardware_entropy(32)  # 256 bits
      seed = u64_from_bytes(entropy[0:8])
      PROB_SET_SEED(seed)
      # Remaining entropy can seed additional streams
```

The `PROB_SET_SEED` opcode accepts a special seed value `0x0000000000000000`
which triggers automatic entropy-based seeding:

```
  if seed == 0:
      seed = collect_hardware_entropy(8)  # 64 bits from entropy source
```

### 2.6 Seeding from Multiple Sources

The extension supports combining multiple entropy sources via XOR:

```
  def combined_seed(sources: list[u64]) -> u64:
      seed = 0
      for s in sources:
          seed ^= s
      if seed == 0:
          seed = 1  # Avoid zero seed (degenerate state)
      return seed
```

---

## 3. Probability Distribution Format

### 3.1 Discrete Distribution

A discrete probability distribution over N outcomes is stored in memory as:

```
Discrete Distribution Memory Layout:

Offset  Size  Field                  Description
------  ----  ----                   -----------
0x000   4     magic                  0x50524F42 ("PROB")
0x004   2     version               Distribution format version (1)
0x006   2     flags                  Bit 0: normalized, Bit 1: sorted
0x008   4     num_outcomes          Number of discrete outcomes N
0x00C   4     temperature           Sampling temperature (float32)
0x010   ...   outcome_probs[]       Array of float32 probabilities
0x010+N*4 ...  outcome_ids[]         Array of u32 outcome IDs (optional)

  Size: 16 + N × 4 bytes (probabilities only)
  Size: 16 + N × 8 bytes (probabilities + IDs)

  Constraint: Σ outcome_probs[i] = 1.0 (when normalized flag set)
```

### 3.2 Continuous Distribution

A continuous distribution is specified by its type and parameters:

```
Continuous Distribution Memory Layout:

Offset  Size  Field                  Description
------  ----  ----                   -----------
0x000   4     magic                  0x50524F42 ("PROB")
0x004   2     version               1
0x006   2     dist_type              0=uniform, 1=gaussian, 2=gumbel
0x008   4     param_a                First parameter (float32 or int)
0x00C   4     param_b                Second parameter (float32 or int)
0x010   4     param_c                Third parameter (float32, optional)
0x014   4     param_d                Fourth parameter (float32, optional)

  Uniform:  param_a = min, param_b = max
  Gaussian: param_a = mean (μ), param_b = std_dev (σ)
  Gumbel:   param_a = location (μ), param_b = scale (β), param_c = temperature (τ)
```

### 3.3 Distribution Register (pd)

The extension provides a **probability distribution register** `pd` that can
hold a reference to a distribution in memory:

```
  Probability Distribution Register (pd):

    pd.addr: u64          Address of distribution in memory (0 = no distribution)
    pd.type: u8           Distribution type (0=none, 1=discrete, 2=uniform,
                            3=gaussian, 4=gumbel, 5=bernoulli)
    pd.num_outcomes: u32  Number of outcomes (discrete only)
    pd.temperature: f32   Sampling temperature
    pd.confidence: f32    Confidence in this distribution
```

---

## 4. Opcode Table

| Opcode   | Mnemonic               | Format | Operands           | Description                              |
|----------|------------------------|--------|--------------------|------------------------------------------|
| 0xFFD0   | SAMPLE_UNIFORM         | E      | rd, rs1, rs2       | Sample from Uniform(a, b) distribution    |
| 0xFFD1   | SAMPLE_GAUSSIAN        | E      | rd, rs1, rs2       | Sample from Gaussian(μ, σ) distribution   |
| 0xFFD2   | SAMPLE_GUMBEL          | E      | rd, rs1, rs2       | Gumbel-softmax sampling for discrete      |
| 0xFFD3   | SAMPLE_BERNOULLI       | E      | rd, rs1, rs2       | Bernoulli trial with probability p         |
| 0xFFD4   | PROB_SET_SEED          | B      | rd                 | Set RNG seed for reproducibility           |
| 0xFFD5   | PROB_BAYESIAN_UPDATE   | E      | rd, rs1, rs2       | Bayesian update: prior × likelihood       |
| 0xFFD6   | ENTROPY_CALC           | B      | rd                 | Shannon entropy of distribution in pd     |
| 0xFFD7   | PROB_STORE_DIST        | E      | rd, rs1, rs2       | Store/restore distribution from memory     |
| 0xFFD8   | SAMPLE_FROM_DIST       | E      | rd, rs1, rs2       | Sample from loaded distribution in pd      |
| 0xFFD9   | PROB_KL_DIVERGENCE     | E      | rd, rs1, rs2       | KL divergence between two distributions   |
| 0xFFDA   | PROB_NORMALIZE         | B      | rd                 | Normalize distribution to sum to 1.0      |
| 0xFFDB   | PROB_TEMPERATURE       | E      | rd, rs1, rs2       | Apply temperature scaling to distribution  |
| 0xFFDC   | PROB_TOP_P             | E      | rd, rs1, rs2       | Top-p (nucleus) sampling filtering         |
| 0xFFDD   | PROB_TOP_K             | E      | rd, rs1, rs2       | Top-K sampling filtering                   |
| 0xFFDE   | PROB_STREAM            | C      | imm8               | Select active RNG stream (0–3)             |
| 0xFFDF   | PROB_RESET             | A      | -                  | Reset all RNG and distribution state       |

---

## 5. Opcode Definitions

### 5.1 SAMPLE_UNIFORM (0xFFD0) — Format E

**Syntax:** `SAMPLE_UNIFORM rd, rs1, rs2`

**Description:** Draw a single sample from a continuous Uniform(a, b)
distribution. The result is a float32 in [a, b) stored as bits in `rd`.

**Operands:**
- `rd` = destination register (receives float32 bits)
- `rs1` = lower bound `a` (float32 bits in register)
- `rs2` = upper bound `b` (float32 bits in register)

**Semantics:**
```
  Pseudocode: SAMPLE_UNIFORM

  def sample_uniform(rd: int, rs1: int, rs2: int):
      if not rng[prng_stream].active:
          raise TRAP_PROB_UNSEEDED

      a = bits_to_f32(r[rs1])
      b = bits_to_f32(r[rs2])

      if a >= b:
          raise TRAP_PROB_PARAM_INVALID

      # Generate uniform random float in [0, 1)
      u = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))

      # Scale to [a, b)
      result = a + u * (b - a)
      r[rd] = f32_to_bits(result)
      c[rd] = 1.0 / log2(max(b - a, EPSILON))  # wider range = less certain
```

**Confidence assignment:** The confidence of a uniform sample reflects the
precision of the range — a narrower range implies more certainty about
where the sample will fall.

### 5.2 SAMPLE_GAUSSIAN (0xFFD1) — Format E

**Syntax:** `SAMPLE_GAUSSIAN rd, rs1, rs2`

**Description:** Draw a single sample from a Gaussian (normal) distribution
with mean μ and standard deviation σ using the Box-Muller transform.

**Operands:**
- `rd` = destination register (receives float32 bits)
- `rs1` = mean μ (float32 bits)
- `rs2` = standard deviation σ (float32 bits)

**Semantics:**
```
  Pseudocode: SAMPLE_GAUSSIAN

  def sample_gaussian(rd: int, rs1: int, rs2: int):
      if not rng[prng_stream].active:
          raise TRAP_PROB_UNSEEDED

      mu = bits_to_f32(r[rs1])
      sigma = bits_to_f32(r[rs2])

      if sigma < 0:
          raise TRAP_PROB_PARAM_INVALID

      # Box-Muller transform (consumes 2 RNG values)
      u1 = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))
      u2 = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))

      # Avoid log(0)
      u1 = max(u1, EPSILON)

      z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * PI * u2)
      result = mu + sigma * z0

      r[rd] = f32_to_bits(result)
      c[rd] = max(0.01, 1.0 - sigma / abs(mu + EPSILON))
```

**Note:** The Box-Muller transform generates pairs of samples. The second
sample (z1) is discarded. A future version may provide a
`SAMPLE_GAUSSIAN_PAIR` opcode that returns both samples.

**Confidence assignment:** Higher σ (more variance) → lower confidence.
If μ ≈ 0, confidence is capped at a minimum of 0.01.

### 5.3 SAMPLE_GUMBEL (0xFFD2) — Format E

**Syntax:** `SAMPLE_GUMBEL rd, rs1, rs2`

**Description:** Gumbel-softmax sampling for making stochastic choices from
a discrete set. Used for exploration in reinforcement learning and for
differentiable sampling in neural networks.

**Operands:**
- `rd` = destination register (receives index of selected outcome, as u32)
- `rs1` = address of logits array in memory (float32 array)
- `rs2` = number of outcomes N (as integer in register)

**Semantics:**
```
  Pseudocode: SAMPLE_GUMBEL

  def sample_gumbel(rd: int, rs1: int, rs2: int):
      if not rng[prng_stream].active:
          raise TRAP_PROB_UNSEEDED

      logits_addr = r[rs1]
      N = r[rs2]

      if N == 0 or N > GUMBEL_MAX_OUTCOMES (65536):
          raise TRAP_PROB_PARAM_INVALID

      # Step 1: Draw N Gumbel samples
      # Gumbel(0, 1) = -log(-log(U)) where U ~ Uniform(0, 1)
      gumbel_samples = array[f32](N)
      for i in range(N):
          u = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))
          u = max(u, EPSILON)  # Avoid log(0)
          gumbel_samples[i] = -log(-log(u))

      # Step 2: Add Gumbel noise to logits
      perturbed = array[f32](N)
      max_logit = -INFINITY
      for i in range(N):
          logit = mem_read_f32(logits_addr + i * 4)
          perturbed[i] = logit / temperature + gumbel_samples[i]
          max_logit = max(max_logit, perturbed[i])

      # Step 3: Softmax to get probabilities
      probs = array[f32](N)
      sum_exp = 0.0
      for i in range(N):
          probs[i] = exp(perturbed[i] - max_logit)  # Numerical stability
          sum_exp += probs[i]
      for i in range(N):
          probs[i] /= sum_exp

      # Step 4: Sample from categorical distribution (argmax = greedy)
      # Use Gumbel trick: the argmax of perturbed logits IS the sample
      best_idx = 0
      best_val = perturbed[0]
      for i in range(1, N):
          if perturbed[i] > best_val:
              best_val = perturbed[i]
              best_idx = i

      r[rd] = best_idx
      # Confidence = probability of the selected outcome
      c[rd] = probs[best_idx]

      # Store distribution in pd for later entropy/confidence queries
      pd.type = DIST_DISCRETE
      pd.num_outcomes = N
      pd.probs = probs
```

**Temperature control:** The temperature parameter is read from the
distribution register `pd.temperature`. Default temperature is 1.0.
- Temperature → 0: approaches argmax (greedy/deterministic)
- Temperature → ∞: approaches uniform (maximum randomness)
- Temperature = 1.0: standard Gumbel-softmax

### 5.4 SAMPLE_BERNOULLI (0xFFD3) — Format E

**Syntax:** `SAMPLE_BERNOULLI rd, rs1, rs2`

**Description:** Perform a Bernoulli trial — return 1 with probability p,
0 with probability (1-p). Used for binary decisions, dropout masks, and
exploration toggles.

**Operands:**
- `rd` = destination register (receives 0 or 1)
- `rs1` = probability p (float32 bits, range [0.0, 1.0])
- `rs2` = unused (must be 0; reserved for future batch mode)

**Semantics:**
```
  Pseudocode: SAMPLE_BERNOULLI

  def sample_bernoulli(rd: int, rs1: int, rs2: int):
      if not rng[prng_stream].active:
          raise TRAP_PROB_UNSEEDED

      p = bits_to_f32(r[rs1])

      if p < 0.0 or p > 1.0:
          raise TRAP_PROB_PARAM_INVALID

      u = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))

      if u < p:
          r[rd] = 1
      else:
          r[rd] = 0

      # Confidence: high when p is near 0 or 1 (certain outcome)
      # Maximum uncertainty when p = 0.5
      c[rd] = 1.0 - 2.0 * min(p, 1.0 - p)
      # p=0.0 → c=1.0, p=0.5 → c=0.0, p=1.0 → c=1.0
```

### 5.5 PROB_SET_SEED (0xFFD4) — Format B

**Syntax:** `PROB_SET_SEED rd`

**Description:** Set the RNG seed for reproducibility. `rd` contains the
seed value as a 64-bit integer (stored across two registers: `rd` holds
the lower 32 bits, `rd+1` holds the upper 32 bits).

If the combined seed is 0, automatically seed from hardware entropy.

**Semantics:**
```
  Pseudocode: PROB_SET_SEED

  def prob_set_seed(rd: int):
      seed_lo = r[rd]
      seed_hi = r[rd + 1]  # Must not exceed r255
      seed = (u64(seed_hi) << 32) | u64(seed_lo)

      if seed == 0:
          seed = collect_hardware_entropy(8)
          r[rd] = u32(seed & 0xFFFFFFFF)
          r[rd + 1] = u32(seed >> 32)

      # Initialize all 4 streams from the seed
      init_streams(seed)
      prng_stream = 0  # Reset to default stream
```

**Seed combination for multi-agent scenarios:**

```
  ; Combine agent ID + task ID + timestamp for unique seed
  ; Agent A and Agent B use different seeds even for same task
  ID        ; r0 = agent ID (e.g., 42)
  CLK       ; r1 = clock cycle count
  XOR       r2, r0, r1     ; r2 = agent_id ^ clock
  ADD       r3, r2, r4     ; r3 += task_id (r4)
  PROB_SET_SEED r3         ; Seed with combined value
```

### 5.6 PROB_BAYESIAN_UPDATE (0xFFD5) — Format E

**Syntax:** `PROB_BAYESIAN_UPDATE rd, rs1, rs2`

**Description:** Perform a Bayesian update: compute the posterior probability
given a prior and likelihood. Implements Bayes' theorem:

```
  P(H|E) = P(E|H) × P(H) / P(E)
```

**Operands:**
- `rd` = destination register (receives posterior as float32 bits)
- `rs1` = prior P(H) (float32 bits, range [0.0, 1.0])
- `rs2` = likelihood P(E|H) (float32 bits, range [0.0, 1.0])

For the full Bayes update, the marginal likelihood P(E) is computed from
the probability distribution register `pd`:

```
  P(E) = Σ_H P(E|H) × P(H)   (sum over all hypotheses)
```

If `pd` contains a discrete distribution, P(E) is computed by summing
the likelihood × prior over all outcomes. If `pd` is empty (no distribution
loaded), the opcode uses a simplified form:

```
  Simplified: posterior = likelihood × prior
  (assumes P(E) is normalized externally)
```

**Semantics:**
```
  Pseudocode: PROB_BAYESIAN_UPDATE

  def prob_bayesian_update(rd: int, rs1: int, rs2: int):
      prior = bits_to_f32(r[rs1])
      likelihood = bits_to_f32(r[rs2])

      if prior < 0.0 or prior > 1.0:
          raise TRAP_PROB_PARAM_INVALID
      if likelihood < 0.0 or likelihood > 1.0:
          raise TRAP_PROB_PARAM_INVALID

      if pd.type == DIST_DISCRETE and pd.num_outcomes > 0:
          # Full Bayes update with marginal likelihood
          marginal = 0.0
          for i in range(pd.num_outcomes):
              h_i = pd.prior[i]    # Prior for hypothesis i
              l_i = pd.likelihood[i]  # Likelihood for hypothesis i
              marginal += l_i * h_i

          if marginal < EPSILON:
              raise TRAP_PROB_ZERO_MARGINAL

          posterior = likelihood * prior / marginal
      else:
          # Simplified: just multiply
          posterior = likelihood * prior
          # Clamp to [0, 1]
          posterior = min(1.0, max(0.0, posterior))

      r[rd] = f32_to_bits(posterior)

      # Confidence: based on how much the evidence shifts the prior
      # Large shift (prior far from posterior) = lower confidence
      shift = abs(posterior - prior)
      c[rd] = 1.0 - shift  # No shift → full confidence
```

**Multi-hypothesis update (using pd):**

```
  ; Load discrete distribution with priors
  PROB_STORE_DIST  r1, r2, r3    ; Load distribution into pd

  ; Update specific hypothesis with new evidence
  ; rs1 = prior for hypothesis i
  ; rs2 = likelihood P(E|Hi)
  PROB_BAYESIAN_UPDATE  r4, r1, r2   ; r4 = posterior for hypothesis i
```

### 5.7 ENTROPY_CALC (0xFFD6) — Format B

**Syntax:** `ENTROPY_CALC rd`

**Description:** Compute the Shannon entropy of the probability distribution
currently loaded in `pd`. Entropy is defined as:

```
  H(P) = -Σ P(i) × log₂(P(i))
```

Maximum entropy for N outcomes is log₂(N) (uniform distribution).
Minimum entropy is 0 (deterministic distribution).

**Semantics:**
```
  Pseudocode: ENTROPY_CALC

  def entropy_calc(rd: int):
      if pd.type != DIST_DISCRETE:
          raise TRAP_PROB_NO_DISTRIBUTION

      entropy = 0.0
      for i in range(pd.num_outcomes):
          p = pd.probs[i]
          if p > EPSILON:  # Avoid log(0)
              entropy -= p * log2(p)

      r[rd] = f32_to_bits(entropy)
      c[rd] = 1.0  # Entropy computation is exact
```

**Confidence interpretation of entropy:**

```
  normalized_entropy = H(P) / log₂(N)   [range: 0, 1]
  confidence = 1.0 - normalized_entropy

  H=0       → confidence=1.0  (fully certain, deterministic)
  H=log₂(N) → confidence=0.0  (fully uncertain, uniform)
```

### 5.8 PROB_STORE_DIST (0xFFD7) — Format E

**Syntax:** `PROB_STORE_DIST rd, rs1, rs2`

**Description:** Load or store a probability distribution between memory and
the `pd` register.

**Operands (load from memory):**
- `rd` = address of distribution in memory
- `rs1` = 0 (load mode)
- `rs2` = 0 (reserved)

**Operands (store to memory):**
- `rd` = address of destination in memory
- `rs1` = 1 (store mode)
- `rs2` = 0 (reserved)

**Semantics:**
```
  Pseudocode: PROB_STORE_DIST

  def prob_store_dist(rd: int, rs1: int, rs2: int):
      mode = r[rs1]
      addr = r[rd]

      if mode == 0:  # LOAD from memory
          magic = mem_read_u32(addr)
          if magic != 0x50524F42:
              raise TRAP_PROB_DIST_CORRUPT

          version = mem_read_u16(addr + 4)
          flags = mem_read_u16(addr + 6)
          num_outcomes = mem_read_u32(addr + 8)
          temperature = mem_read_f32(addr + 12)

          pd.type = DIST_DISCRETE
          pd.num_outcomes = num_outcomes
          pd.temperature = temperature

          # Load probabilities
          pd.probs = array[f32](num_outcomes)
          for i in range(num_outcomes):
              pd.probs[i] = mem_read_f32(addr + 16 + i * 4)

          # If IDs present, load them too
          if flags & 0x02:
              pd.ids = array[u32](num_outcomes)
              for i in range(num_outcomes):
                  pd.ids[i] = mem_read_u32(addr + 16 + num_outcomes * 4 + i * 4)

      elif mode == 1:  # STORE to memory
          # Ensure destination buffer is large enough
          total_size = 16 + pd.num_outcomes * 4
          if pd.ids:
              total_size += pd.num_outcomes * 4

          mem_write_u32(addr, 0x50524F42)  # magic
          mem_write_u16(addr + 4, 1)       # version
          flags = 0x01  # normalized
          if pd.ids:
              flags |= 0x02
          mem_write_u16(addr + 6, flags)
          mem_write_u32(addr + 8, pd.num_outcomes)
          mem_write_f32(addr + 12, pd.temperature)

          for i in range(pd.num_outcomes):
              mem_write_f32(addr + 16 + i * 4, pd.probs[i])

          if pd.ids:
              for i in range(pd.num_outcomes):
                  mem_write_u32(addr + 16 + pd.num_outcomes * 4 + i * 4,
                               pd.ids[i])
      else:
          raise TRAP_PROB_PARAM_INVALID
```

### 5.9 SAMPLE_FROM_DIST (0xFFD8) — Format E

**Syntax:** `SAMPLE_FROM_DIST rd, rs1, rs2`

**Description:** Sample from the probability distribution currently loaded
in `pd`. Uses inverse CDF sampling for discrete distributions.

**Operands:**
- `rd` = destination register (receives sampled outcome index or value)
- `rs1` = temperature override (0 = use pd.temperature)
- `rs2` = reserved (0)

**Semantics:**
```
  Pseudocode: SAMPLE_FROM_DIST

  def sample_from_dist(rd: int, rs1: int, rs2: int):
      if pd.type != DIST_DISCRETE:
          raise TRAP_PROB_NO_DISTRIBUTION
      if not rng[prng_stream].active:
          raise TRAP_PROB_UNSEEDED

      temp = bits_to_f32(r[rs1]) if r[rs1] != 0 else pd.temperature

      # Apply temperature to probabilities
      N = pd.num_outcomes
      adjusted = array[f32](N)
      if temp != 1.0:
          for i in range(N):
              adjusted[i] = pd.probs[i] ** (1.0 / temp)
          # Renormalize
          total = sum(adjusted)
          for i in range(N):
              adjusted[i] /= total
      else:
          adjusted = pd.probs

      # Inverse CDF sampling
      u = u64_to_unit_f32(xoshiro256_next(rng[prng_stream]))
      cumulative = 0.0
      selected = N - 1  # Default to last outcome
      for i in range(N):
          cumulative += adjusted[i]
          if u < cumulative:
              selected = i
              break

      r[rd] = selected
      c[rd] = adjusted[selected]  # Confidence = probability of selection
```

### 5.10 PROB_KL_DIVERGENCE (0xFFD9) — Format E

**Syntax:** `PROB_KL_DIVERGENCE rd, rs1, rs2`

**Description:** Compute the Kullback-Leibler divergence between the
distribution in `pd` (P) and a distribution in memory at `r[rs2]` (Q):

```
  D_KL(P || Q) = Σ P(i) × log₂(P(i) / Q(i))
```

**Semantics:**
```
  def prob_kl_divergence(rd: int, rs1: int, rs2: int):
      # P from pd, Q from memory at r[rs2]
      q_addr = r[rs2]
      q_probs = load_probs_from_memory(q_addr)

      if pd.num_outcomes != q_probs.len:
          raise TRAP_PROB_DIM_MISMATCH

      kl = 0.0
      for i in range(pd.num_outcomes):
          p_i = pd.probs[i]
          q_i = q_probs[i]
          if p_i > EPSILON and q_i > EPSILON:
              kl += p_i * log2(p_i / q_i)
          elif p_i > EPSILON:
              kl = INFINITY  # Q assigns zero probability to nonzero P

      r[rd] = f32_to_bits(kl)
      c[rd] = 1.0 if kl < INFINITY else 0.0
```

### 5.11 PROB_NORMALIZE (0xFFDA) — Format B

**Syntax:** `PROB_NORMALIZE rd`

**Description:** Normalize the distribution in `pd` so that probabilities sum
to 1.0. Operates in-place on the `pd` register.

**Semantics:**
```
  def prob_normalize(rd: int):
      if pd.type != DIST_DISCRETE:
          raise TRAP_PROB_NO_DISTRIBUTION

      total = sum(pd.probs)
      if total < EPSILON:
          raise TRAP_PROB_ZERO_TOTAL

      for i in range(pd.num_outcomes):
          pd.probs[i] /= total

      # Update confidence based on how much normalization changed values
      r[rd] = f32_to_bits(total)  # Return original sum for diagnostics
      c[rd] = min(1.0, 1.0 / total)  # Close to 1 = was nearly normalized
```

### 5.12 PROB_TEMPERATURE (0xFFDB) — Format E

**Syntax:** `PROB_TEMPERATURE rd, rs1, rs2`

**Description:** Apply temperature scaling to the distribution in `pd`.
Lower temperature → sharper distribution (more peaky). Higher temperature
→ flatter distribution (more uniform).

**Operands:**
- `rd` = destination (0 = apply to pd, nonzero = store result to memory at r[rd])
- `rs1` = temperature value (float32 bits)
- `rs2` = mode: 0 = divide probs by temp, 1 = raise to power 1/temp

**Semantics:**
```
  def prob_temperature(rd: int, rs1: int, rs2: int):
      temp = bits_to_f32(r[rs1])
      mode = r[rs2]

      if temp <= 0:
          raise TRAP_PROB_PARAM_INVALID

      N = pd.num_outcomes
      adjusted = array[f32](N)

      match mode:
          case 0:  # Divide by temperature (logits mode)
              for i in range(N):
                  adjusted[i] = pd.probs[i] / temp

          case 1:  # Raise to power 1/temperature (probabilities mode)
              for i in range(N):
                  adjusted[i] = pd.probs[i] ** (1.0 / temp)

      # Softmax normalization
      max_val = max(adjusted)
      exp_vals = array[f32](N)
      sum_exp = 0.0
      for i in range(N):
          exp_vals[i] = exp(adjusted[i] - max_val)
          sum_exp += exp_vals[i]
      for i in range(N):
          exp_vals[i] /= sum_exp

      pd.probs = exp_vals
      pd.temperature = temp

      if r[rd] != 0:
          # Also store to memory
          store_probs_to_memory(r[rd], exp_vals, N)
```

### 5.13 PROB_TOP_P (0xFFDC) — Format E

**Syntax:** `PROB_TOP_P rd, rs1, rs2`

**Description:** Nucleus (top-p) sampling. Filter the distribution to keep
only the smallest set of outcomes whose cumulative probability exceeds p.
Re-normalize the filtered distribution.

**Operands:**
- `rd` = destination (result stored in pd; also returns filtered count in r[rd])
- `rs1` = threshold p (float32 bits, range [0.0, 1.0])
- `rs2` = mode: 0 = filter in-place, 1 = return filtered indices

**Semantics:**
```
  Pseudocode: PROB_TOP_P

  def prob_top_p(rd: int, rs1: int, rs2: int):
      threshold = bits_to_f32(r[rs1])

      if threshold < 0.0 or threshold > 1.0:
          raise TRAP_PROB_PARAM_INVALID

      # Sort outcomes by probability (descending)
      sorted_indices = argsort(pd.probs, descending=True)
      sorted_probs = pd.probs[sorted_indices]

      # Find nucleus: smallest set with cumulative prob >= threshold
      cumulative = 0.0
      nucleus_size = pd.num_outcomes  # Default: keep all
      for i in range(pd.num_outcomes):
          cumulative += sorted_probs[i]
          if cumulative >= threshold:
              nucleus_size = i + 1
              break

      # Zero out probabilities outside nucleus
      new_probs = array[f32](pd.num_outcomes)
      total = 0.0
      for i in range(nucleus_size):
          idx = sorted_indices[i]
          new_probs[idx] = pd.probs[idx]
          total += pd.probs[idx]

      # Renormalize
      for i in range(pd.num_outcomes):
          new_probs[i] /= total

      pd.probs = new_probs
      r[rd] = nucleus_size
      c[rd] = min(1.0, cumulative)
```

### 5.14 PROB_TOP_K (0xFFDD) — Format E

**Syntax:** `PROB_TOP_K rd, rs1, rs2`

**Description:** Top-K sampling. Keep only the K highest-probability
outcomes and re-normalize.

**Operands:**
- `rd` = destination (returns K, result in pd)
- `rs1` = K (integer in register)
- `rs2` = mode: 0 = filter in-place

**Semantics:**
```
  Pseudocode: PROB_TOP_K

  def prob_top_k(rd: int, rs1: int, rs2: int):
      K = r[rs1]

      if K <= 0 or K > pd.num_outcomes:
          raise TRAP_PROB_PARAM_INVALID

      # Find top-K indices
      sorted_indices = argsort(pd.probs, descending=True)[:K]

      new_probs = array[f32](pd.num_outcomes)  # Zero-initialized
      total = 0.0
      for idx in sorted_indices:
          new_probs[idx] = pd.probs[idx]
          total += pd.probs[idx]

      for i in range(pd.num_outcomes):
          new_probs[i] /= total

      pd.probs = new_probs
      r[rd] = K
      c[rd] = total  # Confidence = total probability mass of top-K
```

### 5.15 PROB_STREAM (0xFFDE) — Format C

**Syntax:** `PROB_STREAM imm8`

**Description:** Select the active RNG stream. Stream index must be 0–3.

```
  prng_stream = imm8 & 0x03

  Trap conditions:
    imm8 > 3 → TRAP_PROB_PARAM_INVALID
    rng[prng_stream].active == false → TRAP_PROB_UNSEEDED
```

### 5.16 PROB_RESET (0xFFDF) — Format A

**Syntax:** `PROB_RESET`

**Description:** Reset all RNG streams and the distribution register to
their initial (unseeded) state. All streams become inactive.

---

## 6. Binary Encoding

### 6.1 Escape Prefix Encoding

All probabilistic opcodes use the `0xFF` escape prefix followed by `0xD0–0xDF`:

```
  0xFF D0 = SAMPLE_UNIFORM
  0xFF D1 = SAMPLE_GAUSSIAN
  0xFF D2 = SAMPLE_GUMBEL
  ...
  0xFF DF = PROB_RESET
```

### 6.2 Format-Specific Encodings

#### Format A — PROB_RESET

```
  ┌─────┬─────┐
  │ 0xFF│ 0xDF│    (2 bytes total)
  └─────┴─────┘
```

#### Format B — PROB_SET_SEED, ENTROPY_CALC, PROB_NORMALIZE

```
  ┌─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │    (3 bytes total)
  └─────┴─────┴─────┘
```

#### Format C — PROB_STREAM

```
  ┌─────┬─────┬─────┐
  │ 0xFF│ ext │imm8 │    (3 bytes total)
  └─────┴─────┴─────┘
  imm8: stream index (0–3)
```

#### Format E — SAMPLE_UNIFORM, SAMPLE_GAUSSIAN, SAMPLE_GUMBEL, etc.

```
  ┌─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ ext │ rd  │ rs1 │ rs2 │    (5 bytes total)
  └─────┴─────┴─────┴─────┴─────┘
```

### 6.3 PROB_SET_SEED 64-bit Encoding

Since PROB_SET_SEED needs a 64-bit seed, it uses two consecutive registers:

```
  PROB_SET_SEED r5:
    seed_lo = r[5]
    seed_hi = r[6]  (implicitly r[rd+1])

  Byte sequence:
  ┌─────┬─────┬─────┐
  │ 0xFF│ 0xD4│ 0x05│    (3 bytes)
  └─────┴─────┴─────┘

  Ensure r5 and r6 contain the full 64-bit seed before calling.
  Trap if rd+1 > 255 (register overflow).
```

### 6.4 Explicit Format Mode Examples

```
  SAMPLE_GAUSSIAN r3, r1, r2 (explicit format):
  ┌─────┬─────┬─────┬─────┬─────┬─────┐
  │ 0xFF│ 0xD1│ 0x04│ 0x03│ 0x01│ 0x02│
  └─────┴─────┴─────┴─────┴─────┴─────┘
  esc   ext   fmt   rd    rs1   rs2

  PROB_STREAM 2 (explicit format):
  ┌─────┬─────┬─────┬─────┐
  │ 0xFF│ 0xDE│ 0x02│ 0x02│
  └─────┴─────┴─────┴─────┘
  esc   ext   fmt   imm8
```

---

## 7. Execution Semantics

### 7.1 Sampling Pipeline

```
  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │ RNG Engine   │───→│ Distribution │───→│ Output       │
  │ xoshiro256** │    │ Transform    │    │ (register +  │
  │ (u64 → f32)  │    │ (uniform →   │    │  confidence) │
  │              │    │  target dist)│    │              │
  └──────────────┘    └──────────────┘    └──────────────┘

  Stream 0 (default):  ──→ xoshiro256** state[0] ──→ samples
  Stream 1 (aux):      ──→ xoshiro256** state[1] ──→ samples
  Stream 2 (aux):      ──→ xoshiro256** state[2] ──→ samples
  Stream 3 (aux):      ──→ xoshiro256** state[3] ──→ samples
```

### 7.2 Distribution Transform Reference

| Distribution | Method              | RNG Values Consumed | Output Range     |
|-------------|---------------------|--------------------|--------------------|
| Uniform(a,b) | Scale + shift       | 1                  | [a, b)            |
| Gaussian(μ,σ) | Box-Muller         | 2                  | (-∞, +∞)          |
| Gumbel(0,1)  | -log(-log(U))      | 1 per outcome      | (-∞, +∞)          |
| Bernoulli(p)  | Threshold compare  | 1                  | {0, 1}            |
| Categorical   | Inverse CDF        | 1                  | {0, ..., N-1}     |

### 7.3 Box-Muller Detail

```
  Input: u1, u2 ~ Uniform(0, 1)
  Output: z0, z1 ~ StandardNormal(0, 1)

  z0 = sqrt(-2 * ln(u1)) * cos(2π * u2)
  z1 = sqrt(-2 * ln(u1)) * sin(2π * u2)

  Scaled: x = μ + σ * z0

  The current implementation discards z1. Future extension:
  SAMPLE_GAUSSIAN_PAIR rd, rs1, rs2  (stores both z0 in rd, z1 in rd+1)
```

### 7.4 Gumbel-Max Trick

The Gumbel-softmax sampling in SAMPLE_GUMBEL uses the Gumbel-max trick:

```
  Given logits [l1, l2, ..., lN] and temperature τ:

  1. Draw Gumbel noise: g_i = -log(-log(u_i)) for each i
  2. Perturb logits: y_i = l_i / τ + g_i
  3. Select: argmax(y)  ← This is a valid sample from softmax(l/τ)

  Equivalent to: sample from softmax(l/τ) without computing the full softmax.
```

---

## 8. Confidence Integration

### 8.1 Probability-to-Confidence Mapping

The probabilistic extension integrates with the FLUX confidence system through
a well-defined mapping:

```
  Direct Mapping:
    probability p ∈ [0, 1]  →  confidence c ∈ [0, 1]
    c = p  (identity mapping for most operations)

  Entropy-Based Mapping:
    H(P) = Shannon entropy of distribution P
    H_max = log₂(N) for N outcomes
    normalized_H = H(P) / H_max
    c = 1.0 - normalized_H

  Sampling-Based Mapping:
    After sampling outcome i from distribution P:
    c = P(i)  (confidence = probability of the sampled outcome)
```

### 8.2 Confidence Propagation in Bayesian Updates

```
  Before Bayesian Update:
    prior: P(H) = 0.3
    confidence: 0.3 (directly from probability)

  After observing evidence with likelihood P(E|H) = 0.8:
    posterior: P(H|E) = 0.8 × 0.3 / P(E) = 0.6
    confidence: 0.6 (directly from posterior)

  Evidence strengthens belief → confidence increases
  Contradictory evidence → confidence decreases
```

### 8.3 Confidence Decay for Repeated Sampling

When the same operation is sampled repeatedly without new evidence,
confidence should gradually decay to reflect accumulated uncertainty:

```
  Repeated sampling from same distribution:
    c_n = c_0 × decay^(n-1)
    where decay = 0.99 (per-sample decay factor)
```

### 8.4 Interaction with Confidence Opcodes

```
  ; Sample from distribution with confidence
  SAMPLE_GUMBEL  r3, r1, r2    ; r3 = outcome, c[r3] = P(outcome)

  ; Threshold: only proceed if confidence > 0.3
  C_THRESH  r3, 77             ; 77/255 ≈ 0.302
  JZ  r3, low_confidence_path

  ; Merge confidence from multiple samples
  ; Sample again for verification
  SAMPLE_FROM_DIST  r4, 0, 0   ; r4 = second sample
  C_MERGE  r5, r3, r4          ; r5 = merged confidence
```

### 8.5 Confidence in Multi-Agent Scenarios

When agents share probabilistic results:

```
  Agent A samples: outcome=3, confidence=0.7
  Agent B samples: outcome=3, confidence=0.5

  Shared result via A2A:
    TELL r1, r2, r3    ; Send (outcome, confidence) to Agent B

  Agent B receives and merges:
    ASK r4, r1, r5     ; Receive result
    C_MERGE r6, r4, r5 ; Merge own confidence with received
```

---

## 9. Interaction with Existing ISA

### 9.1 Composability with Control Flow

Sampling results naturally drive branching:

```
  ; Exploration vs. exploitation decision
  SAMPLE_BERNOULLI  r3, r1, 0  ; r1 = exploration_rate (e.g., 0.1)
  JNZ  r3, explore_path        ; If 1 → explore
  ; If 0 → exploit (use best known action)
  ...
explore_path:
  ; Try a random action
  SAMPLE_UNIFORM  r4, r_min, r_max  ; Random action in range
```

### 9.2 Composability with Existing RND/SEED

The core `RND` (0x9A) and `SEED` (0x9B) opcodes continue to work
independently. They use a separate PRNG instance. The probabilistic
extension provides:

| Feature | Core RND/SEED | Prob Extension |
|---------|---------------|----------------|
| Distribution | Uniform integer only | Uniform, Gaussian, Gumbel, Bernoulli |
| Seed size | 32-bit (via register) | 64-bit (via two registers) |
| Streams | Single stream | 4 independent streams |
| Confidence | None | Automatic confidence tagging |
| Reproducibility | Yes | Yes (xoshiro256\*\*) |

### 9.3 Composability with A2A Fleet Opcodes

Probabilistic decisions can be coordinated across agents:

```
  ; Coordinated exploration: all agents use same seed + agent-specific offset
  ID              ; r0 = agent ID
  MOVI  r1, 42    ; r1 = shared base seed
  ADD  r2, r0, r1 ; r2 = agent-specific seed
  PROB_SET_SEED  r2              ; Seed with agent-specific value

  ; Now all agents make correlated but different random decisions
  SAMPLE_UNIFORM  r3, 0, 100     ; Agent-specific random exploration
```

### 9.4 Composability with Embedding Extension

Probabilistic sampling can guide embedding search:

```
  ; Randomly sample an embedding index for exploration
  SAMPLE_UNIFORM  r3, r_min_idx, r_max_idx  ; Random index
  EMBEDDING_LOAD  ev0, r3                     ; Load random embedding
  EMBEDDING_KNN  ev0, 5                       ; Find neighbors

  ; Or use Gumbel sampling to choose which embedding index to search
  SAMPLE_GUMBEL  r4, logits_addr, num_indices ; Choose index
  EMBEDDING_LOAD  ev0, r4                     ; Load chosen embedding
```

### 9.5 Composability with Graph Extension

Probabilistic graph traversal enables random walks:

```
  ; Random walk on a graph
  GRAPH_LOAD  r1, 0
  GRAPH_SET_CURRENT  r2       ; Start node
  MOVI  r5, 0                ; Step counter

random_walk:
  ; Follow a random edge
  GRAPH_STEP  r3, 0xFFFF, 0xFFFFFFFF  ; Random edge selection

  ; Check if we hit a dead end
  CMP_EQ  r6, r3, 0xFFFF      ; r6 = (r3 == INVALID)
  JNZ  r6, walk_done

  ; Record the visited node
  STOREOF  r3, r10, 0
  ADDI16  r10, 4

  ; Decide whether to continue (geometric distribution)
  SAMPLE_BERNOULLI  r7, r_continue_prob, 0  ; Continue with prob p
  JZ  r7, walk_done

  INC  r5
  JMP  random_walk

walk_done:
  GRAPH_UNLOAD
```

---

## 10. Error Handling & Trap Codes

### 10.1 Trap Code Allocation

Probability trap codes are allocated in the range `0xD0–0xDF`:

| Trap Code | Name                       | Severity | Description                              |
|-----------|----------------------------|----------|------------------------------------------|
| 0xD0      | TRAP_PROB_UNSEEDED         | RECOVER  | RNG stream not seeded before sampling     |
| 0xD1      | TRAP_PROB_PARAM_INVALID    | RECOVER  | Invalid parameter (p outside [0,1], σ<0) |
| 0xD2      | TRAP_PROB_NO_DISTRIBUTION  | RECOVER  | No distribution loaded in pd             |
| 0xD3      | TRAP_PROB_DIST_CORRUPT     | FATAL    | Distribution magic/header invalid         |
| 0xD4      | TRAP_PROB_ZERO_MARGINAL    | RECOVER  | Marginal likelihood is zero               |
| 0xD5      | TRAP_PROB_ZERO_TOTAL       | RECOVER  | Distribution probabilities sum to zero    |
| 0xD6      | TRAP_PROB_DIM_MISMATCH     | RECOVER  | Distribution size mismatch               |
| 0xD7      | TRAP_PROB_OVERFLOW         | RECOVER  | Sampling produced infinity/NaN            |
| 0xD8      | TRAP_PROB_STREAM_INVALID   | RECOVER  | Invalid RNG stream index                  |
| 0xD9      | TRAP_PROB_REG_OVERFLOW     | FATAL    | Register index exceeds r255 (seed pair)   |
| 0xDA–0xDF  | Reserved                   | —        | Reserved for future use                  |

### 10.2 Recovery Strategies

```
  UNSEEDED recovery:
    1. Automatically seed with hardware entropy
    2. Retry the failed sampling instruction
    3. Log warning: "Auto-seeded RNG from entropy source"

  PARAM_INVALID recovery:
    1. Clamp parameters to valid range
    2. Log warning with original and clamped values
    3. Continue execution

  NO_DISTRIBUTION recovery:
    1. Return 0 with confidence 0.0
    2. Agent can check confidence and handle missing distribution
```

---

## 11. Performance Considerations

### 11.1 Latency Estimates

| Operation           | Latency (software) | Latency (hardware-accelerated) |
|---------------------|--------------------|--------------------------------|
| xoshiro256** next   | ~1.5 ns            | ~0.5 ns                        |
| SAMPLE_UNIFORM      | ~5 ns              | ~2 ns                          |
| SAMPLE_GAUSSIAN     | ~15 ns             | ~5 ns                          |
| SAMPLE_GUMBEL (N)   | ~10 + 8N ns       | ~2 + N ns                      |
| SAMPLE_BERNOULLI    | ~5 ns              | ~2 ns                          |
| PROB_SET_SEED       | ~20 ns             | ~5 ns                          |
| ENTROPY_CALC (N)    | ~3N ns             | ~N ns                          |
| PROB_BAYESIAN_UPDATE| ~10 ns             | ~3 ns                          |

### 11.2 RNG Throughput

```
  Single stream:  ~1 GHz samples/second (software)
  4 parallel streams: ~4 GHz samples/second
  Hardware-accelerated: >10 GHz samples/second

  Memory: 4 streams × 32 bytes = 128 bytes total RNG state
```

### 11.3 Statistical Quality

```
  xoshiro256** properties:
  - Period: 2^256 - 1 (virtually infinite for practical purposes)
  - Equidistribution: Passes all TestU01 Big Crush tests
  - Correlation: Zero correlation between streams (jump-ahead guaranteed)
  - Reproducibility: Bit-identical across all conformant implementations

  Box-Muller Gaussian quality:
  - Produces exact pairs of independent standard normal samples
  - No rejection sampling (always produces a valid sample)
  - Slight bias in the tail due to float32 rounding (negligible for agent use)
```

### 11.4 Optimization Guidelines

1. **Seed once, sample many** — PROB_SET_SEED is relatively expensive;
   call it once at agent initialization, not per-sample.
2. **Use independent streams** for parallel operations to avoid
   serialization.
3. **Prefer SAMPLE_BERNOULLI** over SAMPLE_UNIFORM + comparison for
   binary decisions (2× faster).
4. **Batch Gumbel samples** — SAMPLE_GUMBEL with large N amortizes
   the per-sample overhead.
5. **Cache distributions** — use PROB_STORE_DIST to load a distribution
   into pd once, then SAMPLE_FROM_DIST multiple times.

---

## 12. Bytecode Examples

### 12.1 Example 1: Exploration vs. Exploitation

An agent decides whether to explore a new action or exploit the best
known action using an epsilon-greedy strategy.

```
  ; =========================================================
  ; Example: Epsilon-greedy exploration
  ; =========================================================

  ; Initialize RNG with reproducible seed
  MOVI  r0, 42               ; Seed = 42
  MOVI  r1, 0                ; High bits = 0
  PROB_SET_SEED  r0          ; Seed RNG (seed = 0x000000000000002A)

  ; Set exploration rate ε = 0.1 (10% exploration)
  ; float32 bits for 0.1 = 0x3DCCCCCD
  MOVI16  r2, 0x3DCC         ; Low 16 bits
  MOVI16  r3, 0xCCD0         ; High bits (approximate)
  ; Store 0.1 in r2:r3 as float32 — simplified:
  ; Assume r2 already contains float32 bits for 0.1

  ; Bernoulli trial: explore?
  SAMPLE_BERNOULLI  r4, r2, 0  ; r4 = 1 (explore) or 0 (exploit)

  ; Branch based on decision
  JNZ  r4, explore

exploit:
  ; Use best known action
  MOVI  r5, best_action
  JMP  execute_action

explore:
  ; Sample random action from [0, num_actions)
  MOVI  r6, 0                ; min = 0
  MOVI  r7, 10               ; max = 10 (10 possible actions)
  SAMPLE_UNIFORM  r5, r6, r7  ; r5 = random float in [0, 10)

execute_action:
  ; r5 contains the selected action
  ; ... execute and observe reward ...
  HALT

  ; Byte sequence (implicit format):
  ; 18 00 2A       MOVI r0, 42
  ; 18 01 00       MOVI r1, 0
  ; FF D4 00       PROB_SET_SEED r0 (r1 implicitly r0+1)
  ; FF D3 04 02 00 SAMPLE_BERNOULLI r4, r2, r0
  ; 3D 04 explore  JNZ r4, explore_offset
  ; 18 05 XX       MOVI r5, best_action
  ; 43 05 YY       JMP execute_action
```

### 12.2 Example 2: Uncertainty Quantification

Compute entropy of a belief distribution and decide whether more
information is needed.

```
  ; =========================================================
  ; Example: Uncertainty quantification with entropy
  ; =========================================================

  ; Load belief distribution (e.g., 5 hypotheses with probabilities)
  MOVI16  r1, 0x1000         ; Address of distribution
  MOVI  r2, 0                ; Load mode
  PROB_STORE_DIST  r1, r2, 0 ; Load into pd

  ; Compute Shannon entropy
  ENTROPY_CALC  r3            ; r3 = H(P) in bits

  ; Maximum entropy for 5 outcomes = log2(5) ≈ 2.32 bits
  ; Threshold: if H > 2.0, we need more information
  ; float32 bits for 2.0 ≈ 0x40000000
  MOVI16  r4, 0x0000
  MOVI16  r5, 0x4000
  ; Compare: r3 > 2.0?
  ; Use float comparison via core opcodes
  CMP_GT  r6, r3, r5         ; r6 = (entropy > 2.0)
  JNZ  r6, need_more_info

  ; Entropy is low enough — make a decision
  SAMPLE_FROM_DIST  r7, 0, 0 ; Sample from current belief
  ; r7 = selected hypothesis, c[r7] = P(hypothesis)
  C_THRESH  r7, 200           ; Require confidence > 200/255 ≈ 0.78
  JZ  r7, uncertain

  ; High confidence decision
  ; ... proceed with hypothesis r7 ...
  JMP  done

need_more_info:
  ; Request more information from environment
  ; This could be an A2A query to another agent
  ASK  r8, r9, r10            ; Query agent r9 for more data
  ; ... incorporate new evidence ...
  ; (would use PROB_BAYESIAN_UPDATE here)

uncertain:
  ; Low confidence — fall back to safe action
  MOVI  r7, SAFE_ACTION

done:
  HALT
```

### 12.3 Example 3: Bayesian Belief Update

Update a belief distribution as new evidence arrives.

```
  ; =========================================================
  ; Example: Bayesian belief updating over time
  ; =========================================================

  ; Initialize with uniform prior (5 hypotheses, each P = 0.2)
  ; Distribution stored at 0x2000:
  ;   probs = [0.2, 0.2, 0.2, 0.2, 0.2]

  MOVI16  r1, 0x2000
  MOVI  r2, 0
  PROB_STORE_DIST  r1, r2, 0   ; Load uniform prior into pd

  ; Seed RNG
  MOVI  r0, 12345
  MOVI  r1, 0
  PROB_SET_SEED  r0

  ; Observe evidence: P(E|H0)=0.1, P(E|H1)=0.3, P(E|H2)=0.8,
  ;                   P(E|H3)=0.05, P(E|H4)=0.5
  ; Likelihoods stored at 0x3000

  ; Update each hypothesis (simplified Bayesian update)
  ; For hypothesis i: posterior[i] = prior[i] * likelihood[i] / P(E)

  ; Compute P(E) = Σ prior[i] * likelihood[i]
  MOVI  r5, 0                ; r5 = P(E) = 0
  MOVI  r6, 0                ; r6 = loop index
  MOVI  r7, 5                ; r7 = num hypotheses

compute_marginal:
  ; Load prior[i] from pd (simplified: stored at known address)
  LOADOFF  r8, pd_addr, r6_offset  ; prior[i]
  LOADOFF  r9, like_addr, r6_offset ; likelihood[i]
  ; Multiply: r8 * r9
  FMUL  r10, r8, r9           ; r10 = prior[i] * likelihood[i]
  FADD  r5, r5, r10           ; r5 += r10
  INC  r6
  CMP_LT  r11, r6, r7
  JNZ  r11, compute_marginal

  ; r5 now contains P(E)
  ; Update each hypothesis
  MOVI  r6, 0

update_loop:
  LOADOFF  r8, pd_addr, r6_offset  ; prior[i]
  LOADOFF  r9, like_addr, r6_offset ; likelihood[i]
  FMUL  r10, r8, r9                 ; prior * likelihood
  FDIV  r10, r10, r5                ; / P(E) = posterior
  ; Store back to pd
  STOREOF  r10, pd_addr, r6_offset
  INC  r6
  CMP_LT  r11, r6, r7
  JNZ  r11, update_loop

  ; Check entropy after update
  ENTROPY_CALC  r3
  ; r3 = new entropy (should be lower than uniform's log2(5) ≈ 2.32)

  ; Make decision from updated posterior
  SAMPLE_FROM_DIST  r4, 0, 0    ; Sample from updated distribution
  HALT
```

### 12.4 Example 4: Temperature-Scaled Decision Making

Use temperature to control exploration sharpness.

```
  ; =========================================================
  ; Example: Temperature-controlled decision making
  ; =========================================================

  ; Load action-value distribution (logits for 8 actions)
  MOVI16  r1, 0x4000
  MOVI  r2, 0
  PROB_STORE_DIST  r1, r2, 0     ; Load into pd

  ; Decide temperature based on confidence
  ; High confidence → low temperature (greedy)
  ; Low confidence → high temperature (exploratory)
  CONF_LD  r3                     ; r3 = current confidence (0–255)
  ; Map confidence to temperature: T = (255 - conf) / 255 * 2.0
  ; At conf=255: T=0.0 (greedy), conf=0: T=2.0 (very exploratory)
  ; Simplified mapping:
  MOVI  r4, 0x3F000000            ; float32 for 0.5
  ; T = (255 - conf) * 0.5 / 255 ≈ (1 - conf/255) * 0.5
  ; (using integer arithmetic approximation)
  MOVI  r5, 255
  SUB  r6, r5, r3                  ; r6 = 255 - confidence
  ITOF  r7, r6                    ; Convert to float
  FDIV  r7, r7, r5                ; r7 = (255-conf)/255
  FMUL  r7, r7, r4                ; r7 = temperature [0, 0.5]

  ; Apply temperature to distribution
  PROB_TEMPERATURE  0, r7, 1      ; Apply temperature (mode 1: power scaling)

  ; Top-p filtering: keep nucleus with p > 0.9
  ; float32 for 0.9 ≈ 0x3F666666
  MOVI16  r8, 0x6666
  MOVI16  r9, 0x3F66
  PROB_TOP_P  r10, r8, 0          ; Filter to top 90% probability mass

  ; Sample from the filtered distribution
  SAMPLE_FROM_DIST  r11, 0, 0    ; r11 = selected action
  ; c[r11] = probability of selected action

  ; Execute action
  ; ... (action execution code) ...

  HALT
```

### 12.5 Example 5: Monte Carlo Estimation

Estimate π using Monte Carlo sampling.

```
  ; =========================================================
  ; Example: Monte Carlo estimation of π
  ; =========================================================

  ; Seed RNG
  MOVI  r0, 99999
  MOVI  r1, 0
  PROB_SET_SEED  r0

  MOVI  r10, 0               ; r10 = inside_count = 0
  MOVI  r11, 10000           ; r11 = total_samples = 10000
  MOVI  r12, 0               ; r12 = loop counter

  ; Float constants: 1.0 and 4.0
  ; float32 1.0 = 0x3F800000
  ; float32 4.0 = 0x40800000
  MOVI16  r13, 0x0000        ; 1.0 low bits
  MOVI16  r14, 0x3F80        ; 1.0 high bits
  MOVI16  r15, 0x0000        ; 4.0 low bits
  MOVI16  r16, 0x4080        ; 4.0 high bits

mc_loop:
  ; Sample x ~ Uniform(0, 1)
  SAMPLE_UNIFORM  r2, r13, r14  ; r2 = x (as float32 bits)
  ; Note: using full float registers, simplified encoding

  ; Sample y ~ Uniform(0, 1)
  SAMPLE_UNIFORM  r3, r13, r14  ; r3 = y

  ; Check if x² + y² < 1
  FMUL  r4, r2, r2              ; r4 = x²
  FMUL  r5, r3, r3              ; r5 = y²
  FADD  r6, r4, r5              ; r6 = x² + y²

  ; Compare with 1.0
  ; If r6 < 1.0, increment inside_count
  ; (using integer comparison after float-to-int trick or CONF)
  ; Simplified: use core float comparison
  CMP_LT  r7, r6, r13           ; r7 = (x²+y² < 1.0)
  JZ  r7, mc_skip

  INC  r10                      ; inside_count++

mc_skip:
  INC  r12
  CMP_LT  r7, r12, r11          ; r7 = (counter < total)
  JNZ  r7, mc_loop

  ; π ≈ 4 × inside_count / total_samples
  ITOF  r20, r10                ; inside_count as float
  ITOF  r21, r11                ; total as float
  FDIV  r22, r20, r21           ; ratio
  ; Multiply by 4.0
  FMUL  r23, r22, r16           ; r23 = π estimate

  ; r23 now contains the estimated value of π
  HALT
```

### 12.6 Example 6: Multi-Stream Parallel Sampling

Use independent RNG streams for concurrent operations.

```
  ; =========================================================
  ; Example: Independent sampling streams
  ; =========================================================

  ; Seed all streams from a base seed
  MOVI  r0, 77777
  MOVI  r1, 0
  PROB_SET_SEED  r0            ; Seeds all 4 streams

  ; Stream 0: Sample exploration action
  ; Stream 1: Sample noise for perturbation
  ; Stream 2: Sample dropout mask
  ; Stream 3: Sample communication probability

  ; --- Stream 0: Exploration ---
  ; (default stream, no need to switch)
  MOVI  r2, 0                  ; min = 0
  MOVI  r3, 20                 ; max = 20
  SAMPLE_UNIFORM  r4, r2, r3   ; r4 = exploration action (stream 0)

  ; --- Stream 1: Gaussian noise ---
  PROB_STREAM  1               ; Switch to stream 1
  MOVI  r5, 0x0000             ; μ = 0.0 (low bits)
  MOVI  r6, 0x0000             ; μ = 0.0 (high bits)
  ; σ = 0.1, float32 ≈ 0x3DCCCCCD
  MOVI  r7, 0xCCCC
  MOVI  r8, 0x3DCC
  SAMPLE_GAUSSIAN  r9, r5, r7  ; r9 = noise (stream 1)

  ; --- Stream 2: Dropout ---
  PROB_STREAM  2               ; Switch to stream 2
  ; p = 0.5 (50% dropout), float32 ≈ 0x3F000000
  MOVI  r10, 0x0000
  MOVI  r11, 0x3F00
  SAMPLE_BERNOULLI  r12, r10, 0  ; r12 = dropout mask (stream 2)

  ; --- Stream 3: Communication probability ---
  PROB_STREAM  3               ; Switch to stream 3
  ; p = 0.8 (80% send), float32 ≈ 0x3F4CCCCD
  MOVI  r13, 0xCCCC
  MOVI  r14, 0x3F4C
  SAMPLE_BERNOULLI  r15, r13, 0  ; r15 = send decision (stream 3)

  ; Return to default stream
  PROB_STREAM  0

  ; All four samples are statistically independent
  ; and reproducible with the same seed (77777)
  HALT
```

---

## 13. Formal Semantics

### 13.1 Extended Machine State

```
  σ' = (σ, rng, pd)

  where rng = {
      streams: [{
          state: u64[4],    // xoshiro256** state
          active: bool,
      }; 4],
      active_stream: u2,    // 0–3
  }

  pd = {
      addr: u64,
      type: u8,             // 0=none, 1=discrete, ...
      num_outcomes: u32,
      probs: f32[],
      ids: u32[],
      temperature: f32,
      confidence: f32,
  }
```

### 13.2 SAMPLE_UNIFORM Rule

```
  Rule: SAMPLE_UNIFORM

  Precondition:
    rng.streams[active_stream].active = true
    a = bits_to_f32(r[rs1]), b = bits_to_f32(r[rs2])
    a < b

  Effect:
    u = uniform_unit_float(rng.streams[active_stream])
    result = a + u × (b - a)
    r[rd] = f32_to_bits(result)
    σ.pc += 5
```

### 13.3 SAMPLE_BERNOULLI Rule

```
  Rule: SAMPLE_BERNOULLI

  Precondition:
    rng.streams[active_stream].active = true
    p = bits_to_f32(r[rs1])
    0 ≤ p ≤ 1

  Effect:
    u = uniform_unit_float(rng.streams[active_stream])
    r[rd] = 1 if u < p else 0
    c[rd] = 1.0 - 2.0 × min(p, 1.0 - p)
    σ.pc += 5
```

### 13.4 PROB_SET_SEED Rule

```
  Rule: PROB_SET_SEED

  Precondition:
    rd + 1 ≤ 255

  Effect:
    seed = (u64(r[rd+1]) << 32) | u64(r[rd])
    if seed == 0: seed = hardware_entropy()
    for i in 0..3:
        rng.streams[i].state = seed_to_state(jump^i(seed))
        rng.streams[i].active = true
    rng.active_stream = 0
    σ.pc += 3
```

### 13.5 Reproducibility Theorem

```
  Theorem: Deterministic Reproduction

  For any conformant FLUX runtime R1 and R2, and any bytecode program P
  using only probabilistic extension opcodes with a fixed seed s:

    Execute(R1, P, seed=s) = Execute(R2, P, seed=s)

  Where "=" means identical register contents after each instruction,
  including all confidence tags and RNG state.

  Proof sketch:
    1. xoshiro256** is a deterministic PRNG (proven by its construction)
    2. All float conversions use the same algorithm (specified in Section 2.4)
    3. All distribution transforms are deterministic given the same RNG output
    4. No external entropy is introduced after seeding (PROB_RESET aside)
    ∎
```

---

## 14. Security Considerations

### 14.1 RNG Predictability

The xoshiro256** PRNG is **not cryptographically secure**. Given 256 bits
of output, the full state can be recovered. For security-sensitive
applications:

1. **Do not use** the probabilistic extension for cryptographic key
   generation, token generation, or any security-critical randomness.
2. **Use** the core crypto extension (0xFF20–0xFF3F) for cryptographic
   random number generation.
3. **Reseed frequently** if the output must resist prediction — each
   reseed with hardware entropy resets the state.

### 14.2 Seed Exposure

The RNG seed is stored in general-purpose registers, which are accessible
via A2A communication. Agents should not share their RNG state with
untrusted agents.

### 14.3 Timing Side Channels

All sampling operations execute in constant time regardless of the sampled
value (no data-dependent branches in the RNG or transform code). This
prevents timing-based attacks from inferring sampled values.

### 14.4 Distribution Integrity

When loading distributions from memory (PROB_STORE_DIST), the extension
validates the magic number and version. However, it does **not** verify
that probabilities sum to 1.0 (unless the normalized flag is set). Agents
should use PROB_NORMALIZE after loading untrusted distributions.

---

## 15. Appendix

### 15.1 Opcode Quick Reference

| Hex     | Assembly                          | Description                    |
|---------|-----------------------------------|--------------------------------|
| FF D0   | SAMPLE_UNIFORM rd, a, b           | Uniform(a, b) sample           |
| FF D1   | SAMPLE_GAUSSIAN rd, μ, σ          | Gaussian(μ, σ) sample          |
| FF D2   | SAMPLE_GUMBEL rd, logits, N       | Gumbel-softmax discrete choice  |
| FF D3   | SAMPLE_BERNOULLI rd, p, 0         | Bernoulli(p) trial             |
| FF D4   | PROB_SET_SEED rd                  | Set 64-bit RNG seed            |
| FF D5   | PROB_BAYESIAN_UPDATE rd, prior, lik| Bayesian posterior             |
| FF D6   | ENTROPY_CALC rd                   | Shannon entropy H(P)           |
| FF D7   | PROB_STORE_DIST rd, mode, 0       | Load/store distribution         |
| FF D8   | SAMPLE_FROM_DIST rd, temp, 0      | Sample from loaded dist         |
| FF D9   | PROB_KL_DIVERGENCE rd, unused, Q  | KL(P || Q) divergence           |
| FF DA   | PROB_NORMALIZE rd                 | Normalize to sum=1.0           |
| FF DB   | PROB_TEMPERATURE rd, τ, mode      | Temperature scaling             |
| FF DC   | PROB_TOP_P rd, p, mode            | Nucleus (top-p) filtering       |
| FF DD   | PROB_TOP_K rd, K, mode            | Top-K filtering                 |
| FF DE   | PROB_STREAM imm8                   | Select RNG stream (0–3)         |
| FF DF   | PROB_RESET                        | Reset all state                 |

### 15.2 Common Float32 Bit Patterns

| Value | Hex Bits | Notes                       |
|-------|----------|-----------------------------|
| 0.0   | 0x00000000 | Zero                       |
| 0.1   | 0x3DCCCCCD | Approximate                |
| 0.5   | 0x3F000000 | Exact                      |
| 0.8   | 0x3F4CCCCD | Approximate                |
| 0.9   | 0x3F666666 | Approximate                |
| 1.0   | 0x3F800000 | Exact                      |
| 2.0   | 0x40000000 | Exact                      |
| 4.0   | 0x40800000 | Exact                      |
| π     | 0x40490FDB | Approximate                |
| e     | 0x402DF854 | Approximate                |

### 15.3 Shannon Entropy Reference

```
  H(P) = -Σ p(i) × log₂(p(i))

  Maximum entropy (uniform distribution):
    H_max = log₂(N) for N outcomes

  Examples:
    N=2, uniform:  H = log₂(2) = 1.000 bit
    N=2, [0.9,0.1]: H = -0.9×log₂(0.9) - 0.1×log₂(0.1) ≈ 0.469 bits
    N=2, [1.0,0.0]: H = 0.000 bits (deterministic)
    N=10, uniform: H = log₂(10) ≈ 3.322 bits
    N=26, uniform: H = log₂(26) ≈ 4.700 bits
```

### 15.4 KL Divergence Reference

```
  D_KL(P || Q) = Σ P(i) × log₂(P(i) / Q(i))

  Properties:
    D_KL(P || Q) ≥ 0  (always non-negative)
    D_KL(P || Q) = 0  iff P = Q  (zero only for identical distributions)
    D_KL(P || Q) ≠ D_KL(Q || P)  (asymmetric)

  Examples:
    P=[0.5,0.5], Q=[0.5,0.5]:  D_KL = 0.000
    P=[0.9,0.1], Q=[0.5,0.5]:  D_KL ≈ 0.529
    P=[1.0,0.0], Q=[0.5,0.5]:  D_KL = +∞  (Q assigns 0 to nonzero P)
```

### 15.5 Extension Manifest Entry

```
  ext_id:            0x00000008
  ext_version_major: 1
  ext_version_minor: 0
  ext_name:          "org.flux.prob"
  ext_name_len:      13
  opcode_base:       0xFFD0
  opcode_count:      16
  required:          0  (optional)
  format_table:
    offset 0x00  format E   SAMPLE_UNIFORM
    offset 0x01  format E   SAMPLE_GAUSSIAN
    offset 0x02  format E   SAMPLE_GUMBEL
    offset 0x03  format E   SAMPLE_BERNOULLI
    offset 0x04  format B   PROB_SET_SEED
    offset 0x05  format E   PROB_BAYESIAN_UPDATE
    offset 0x06  format B   ENTROPY_CALC
    offset 0x07  format E   PROB_STORE_DIST
    offset 0x08  format E   SAMPLE_FROM_DIST
    offset 0x09  format E   PROB_KL_DIVERGENCE
    offset 0x0A  format B   PROB_NORMALIZE
    offset 0x0B  format E   PROB_TEMPERATURE
    offset 0x0C  format E   PROB_TOP_P
    offset 0x0D  format E   PROB_TOP_K
    offset 0x0E  format C   PROB_STREAM
    offset 0x0F  format A   PROB_RESET
```

### 15.6 Revision History

| Version | Date       | Author   | Changes                              |
|---------|------------|----------|--------------------------------------|
| 1.0     | 2026-04-12 | Super Z  | Initial specification (PROB-001)     |

---

*End of FLUX ISA v3 Probabilistic Sampling Extension Specification (PROB-001)*
