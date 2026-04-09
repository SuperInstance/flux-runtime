# Multi-Agent Orchestration & Emergent Behavior in FLUX

> **Research Document** | FLUX Runtime Project | 2025-06
>
> This document explores the design space for multi-agent orchestration within
> the FLUX agent-first markdown-to-bytecode system, covering topologies, emergent
> behavior, specialization, safety, and collective intelligence.

---

## 1. Agent Topologies and Their Bytecode Mappings

FLUX's A2A protocol layer (`src/flux/a2a/`) provides a set of binary primitives
spanning opcodes `0x60`--`0x7B` that encode inter-agent communication directly in
bytecode. These primitives---`TELL`, `ASK`, `DELEGATE`, `BROADCAST`, `REDUCE`,
`BARRIER`, `TRUST_CHECK`, and others---are the atoms from which arbitrary agent
topologies can be constructed. Below we map five canonical topologies to their
bytecode realizations.

### 1.1 Hierarchical (Orchestrator → Workers)

The hierarchical topology has a single orchestrator agent that distributes work
to N worker agents and collects results. This maps naturally to the
`DELEGATE`/`DELEGATE_RESULT` and `REDUCE` opcodes.

**Bytecode pattern: orchestrator dispatch**

```asm
; R0 = number of workers (N)
; R1 = base address of worker UUID table
; R2 = pointer to task descriptor

    MOVI  R3, 0              ; i = 0
    MOVI  R4, task_desc      ; R4 = pointer to serialized task
dispatch_loop:
    CMP   R3, R0
    JGE   collect_phase

    ; Load worker UUID from table
    LOAD  R5, R1             ; R5 = worker_id (indirect via table)
    IADD  R1, 4              ; advance pointer (UUIDs are 4-byte refs in table)

    ; DELEGATE worker_id <task_descriptor>
    ; Format G: [opcode:u8][len:u16][data:len bytes]
    0x62, 0x??, 0x??         ; DELEGATE + payload length
    <R5><R4>                 ; worker_id + task_descriptor bytes

    INC   R3
    JMP   dispatch_loop

collect_phase:
    ; REDUCE across all worker results
    0x67, 0x??, 0x??         ; REDUCE + payload
    <reduction_fn>           ; aggregation function identifier

    HALT
```

**Runtime realization:** The `AgentCoordinator` (`src/flux/a2a/coordinator.py`)
handles registration of each worker, and `send_message()` gates every dispatch
through the trust engine. The coordinator's `trust_threshold` (default `0.3`)
prevents an untrusted orchestrator from flooding workers with delegated tasks.

**Properties:**
- Single point of control simplifies reasoning and trust management.
- The orchestrator becomes a bottleneck under high fan-out.
- Natural fit for `DECLARE_INTENT`/`ASSERT_GOAL`/`VERIFY_OUTCOME` verification
  triples: the orchestrator sets goals, workers assert completion, and the
  orchestrator verifies outcomes.

### 1.2 Flat Peer-to-Peer Mesh

In a flat mesh, every agent can communicate directly with every other agent.
No single agent has special authority. This topology uses `TELL` for
notifications and `ASK` for request-response pairs.

**Bytecode pattern: peer gossip round**

```asm
; Each agent executes this loop independently.
; R0 = number of peers known
; R1 = pointer to peer table

    MOVI  R3, 0
gossip_round:
    CMP   R3, R0
    JGE   done

    LOAD  R5, R1
    IADD  R1, 4

    ; TELL peer about local state
    0x60, 0x??, 0x??         ; TELL + payload
    <R5><local_state>        ; target + state bytes

    ; ASK peer for their state
    0x61, 0x??, 0x??         ; ASK + payload
    <R5><query_descriptor>

    INC   R3
    JMP   gossip_round

done:
    ; Process received ASK responses
    ; ...
    HALT
```

**Trust implications:** A flat mesh creates O(N^2) trust relationships. The
`TrustEngine` computes pairwise profiles keyed by `(agent_a, agent_b)` tuples.
With N agents, this means N*(N-1) potential profiles, each holding up to 1000
`InteractionRecord` entries in a bounded deque. For large swarms, this memory
footprint may require pruning strategies (see Section 4).

**Properties:**
- No single point of failure; the system degrades gracefully.
- Trust propagation is slow---new agents start at `NEUTRAL_TRUST = 0.5` and
  must accumulate interaction history before high-priority messages are accepted.
- Natural substrate for stigmergic communication (Section 2.1).

### 1.3 Star (Central Hub)

The star topology places a central hub agent that all other agents route through.
This is distinct from the hierarchical topology: in a star, the hub is a
*router*, not a *commander*. It uses `BROADCAST` for fan-out and `REDUCE` for
fan-in, with the hub making no task decisions itself.

**Bytecode pattern: hub relay**

```asm
; Hub agent bytecode
hub_loop:
    ; Wait for incoming messages (mailbox drain)
    ; For each message from a spoke agent:
    ;   TELL target_spoke <forwarded_payload>

    ; BROADCAST is more efficient for all-spoke messages
    0x66, 0x??, 0x??         ; BROADCAST + payload
    <broadcast_data>

    JMP   hub_loop

; Spoke agent bytecode
spoke_loop:
    ; Send to hub
    0x60, 0x??, 0x??         ; TELL hub <data>

    ; Receive hub broadcasts
    ; ... process ...

    JMP   spoke_loop
```

**Properties:**
- The hub's trust score must be high for all spokes, otherwise messages are
  silently dropped by the `send_message()` trust gate.
- Natural for shared-state coordination: the hub can maintain a consistent view
  that all spokes read from.

### 1.4 Ring (Pipeline)

In a ring topology, agents form a pipeline: each agent processes data and passes
it to the next. The `TELL` opcode with a single well-known successor encodes
this naturally.

**Bytecode pattern: pipeline stage**

```asm
; Each agent runs this, where R0 = next_agent_id
; R1 = input data pointer

stage_loop:
    ; Process local computation
    CALL  process_fn          ; transform input data

    ; TELL next agent with processed result
    0x60, 0x??, 0x??         ; TELL <next_agent> <result>
    <R0><result_ptr>

    ; BARRIER: wait for pipeline backpressure
    0x78, 0x??, 0x??         ; BARRIER <pipeline_id>
    <pipeline_sync_token>

    JMP   stage_loop
```

**The `BARRIER` opcode (`0x78`)** is critical for ring topologies. It
synchronizes pipeline stages, preventing faster stages from flooding slower
ones. The current `LocalTransport` implements FIFO mailboxes with no flow
control; a full barrier implementation would require the coordinator to track
pending `BARRIER` messages and only release agents when all participants have
arrived.

**Properties:**
- Latency is O(N * stage_time), but throughput is O(1 / max_stage_time).
- Deadlock risk: if any stage fails to emit a `TELL` to its successor, the
  entire pipeline stalls (see Section 4).
- Evolutionary specialization thrives here: hot stages can be recompiled to
  C+SIMD via the `MutationStrategy.RECOMPILE_LANGUAGE` path while cold stages
  remain in Python.

### 1.5 Blackboard (Shared State)

The blackboard topology uses a shared memory region as a communication medium
rather than explicit message passing. Agents `TELL` a coordinator that writes
to the blackboard; other agents `ASK` the coordinator for relevant entries.

FLUX's `REGION_CREATE`/`REGION_TRANSFER` opcodes enable shared memory regions:

```asm
; Blackboard setup (run once by coordinator)
    0x30, 0x??, 0x??         ; REGION_CREATE "blackboard" 65536
    <region_name><size>

; Writer agent
writer_loop:
    ; Compute new value
    ; ...
    ; Write to blackboard region
    0x33, 0x??, 0x??         ; MEMCOPY dest=blackboard+offset, src=result
    <dest_ptr><src_ptr><len>

    ; NOTIFY via TELL
    0x60, 0x??, 0x??         ; TELL subscribers <"blackboard_updated">
    JMP   writer_loop

; Reader agent
reader_loop:
    ; Wait for notification
    ; ...
    ; Read from blackboard region
    0x33, 0x??, 0x??         ; MEMCOPY dest=local, src=blackboard+offset
    JMP   reader_loop
```

**Properties:**
- Implicit coordination: agents don't need to know about each other, only
  about the shared region.
- Race conditions are possible unless the coordinator serializes access.
- Natural substrate for stigmergy (Section 2.1): agents modify the environment
  (blackboard) and other agents react to changes.

---

## 2. Emergent Behavior

When multiple FLUX agents evolve independently via the `EvolutionEngine`, the
system as a whole can exhibit behaviors that no individual agent was explicitly
programmed to perform. We examine three mechanisms.

### 2.1 Stigmergy: Communication Through Environment Modification

Stigmergy, first described in the context of ant colony coordination, occurs
when agents communicate indirectly by modifying a shared environment. In FLUX,
this maps to several concrete mechanisms:

**Mechanism A: Trust profile side effects.** When agent A successfully
interacts with agent B, `AgentCoordinator.send_message()` records a positive
interaction via `trust.record_interaction(sender, receiver, True, 0.1)`. This
modifies the global `TrustEngine` state, which affects future message delivery
for *all* agents that query trust scores. Agent C, observing that `A→B` trust
is high, might infer that B is reliable and increase its own willingness to
delegate to B. No explicit "recommendation" message was sent---the trust
profile *is* the stigmergic signal.

**Mechanism B: Genome propagation through pattern mining.** The
`PatternMiner` uses a modified Apriori algorithm on execution traces to
discover hot patterns. When agent A evolves a new tile via
`MutationStrategy.FUSE_PATTERN`, and agent B later executes a similar
sequence, the pattern miner may independently discover the same pattern.
Without any direct communication, both agents converge on the same optimization.

**Mechanism C: Shared tile registry.** The `TileRegistry` is a global
resource. When the `SystemMutator` commits a new tile (`ADD_TILE`), it becomes
available to all agents. Agent A may discover a useful composition
(`MERGE_TILES`) that agent B can then adopt by looking up the tile in the
registry.

**Formal model:** Let S(t) be the shared state (trust profiles, tile registry,
profiler heatmap) at time t. Agent i's genome at generation g+1 is:
```
genome_i(g+1) = mutate(genome_i(g), mine_patterns(S(t), traces_i), S(t))
```
The shared state S(t) is itself a function of all agents' past interactions:
```
S(t) = f({genome_j(g), interactions_j(t) : for all j})
```
This creates a feedback loop where individual adaptation shapes the collective
environment, which in turn shapes future individual adaptation.

### 2.2 Flocking and Local Rules → Global Behavior

Craig Reynolds' boids model demonstrates that three simple local rules
(separation, alignment, cohesion) produce realistic flocking behavior. In FLUX,
analogous rules can emerge from the trust and capability systems:

**Separation (avoid crowding):** Agents with low pairwise trust scores naturally
avoid delegating to each other. If `compute_trust(A, B) < trust_threshold`,
messages are silently dropped, causing agents to seek alternative partners.

**Alignment (match velocity):** The `AdaptiveProfiler` classifies modules by
heat level (FROZEN/COOL/WARM/HOT/HEAT). When multiple agents observe similar
workloads, their profiler heatmaps converge, causing the `AdaptiveSelector` to
recommend similar language recompilations. Agents thus "align" their
optimization strategies.

**Cohesion (move toward center of mass):** The `REDUCE` opcode enables agents
to aggregate their state into a consensus view. If each agent periodically
`REDUCE`s its genome's fitness score, the group converges on which mutations
are globally beneficial.

**Concrete bytecode for flocking-like behavior:**

```asm
; Agent i's main loop: separation + alignment + cohesion
agent_loop:
    ; --- Separation: avoid low-trust agents ---
    MOVI  R0, num_peers
    MOVI  R1, peer_table
    MOVI  R6, 0              ; trust_sum
sep_loop:
    CMP   R6, R0
    JGE   align_phase
    LOAD  R7, R1             ; peer_id
    ; TRUST_CHECK this agent -> peer
    0x70, 0x??, 0x??         ; TRUST_CHECK <peer_id>
    ; Result in R8: 1 if trusted, 0 if not
    CMP   R8, 0
    JNZ   trust_ok
    ; Low trust: avoid — don't delegate to this peer
    JMP   next_peer
trust_ok:
    ; Record trusted peer as valid target
    STORE  R7, trusted_list[R6]
next_peer:
    IADD  R1, 4
    INC   R6
    JMP   sep_loop

align_phase:
    ; --- Alignment: adopt profiler recommendations ---
    ; (Implicit: the profiler heatmap drives recompilation decisions)
    CALL  align_with_heatmap

cohesion_phase:
    ; --- Cohesion: reduce fitness to find group center ---
    0x67, 0x??, 0x??         ; REDUCE <fitness_score>
    ; Result: average fitness of all agents
    ; If local fitness < group fitness, increase mutation rate

    JMP   agent_loop
```

### 2.3 Market-Based Resource Allocation

FLUX agents can bid for compute resources using the `DECLARE_INTENT` and
`REQUEST_OVERRIDE` opcodes, creating an emergent market for CPU cycles, memory
regions, and compilation budgets.

**Protocol:**

1. Agent publishes intent: `DECLARE_INTENT <"need_1000_cycles_for_evolution">`
2. Coordinator evaluates bids based on trust scores and capability tokens.
3. High-trust agents receive resource grants: `CAP_GRANT <agent_id> <resources>`.
4. Low-trust agents must wait or reduce their requests.

**Fitness-based bidding:** Each agent's genome `fitness_score` serves as its
"budget." The `EvolutionEngine.step()` method evaluates fitness before
proposing mutations. Agents with higher fitness have more "currency" to bid for
scarce resources (e.g., the JIT compilation slot). This creates a natural
meritocracy: the most effective agents get the most resources to become even
more effective.

**Implementation sketch in the coordinator:**

```python
# In AgentCoordinator (extension)
def allocate_resources(self, requests: list[ResourceRequest]) -> list[Grant]:
    """Market-based allocation: highest trust * fitness wins."""
    scored = []
    for req in requests:
        trust = self.trust.compute_trust("system", req.agent_id)
        score = trust * req.fitness * req.bid_amount
        scored.append((score, req))
    scored.sort(reverse=True)
    grants = []
    for score, req in scored:
        if self._resource_pool.can_grant(req.amount):
            grants.append(Grant(agent_id=req.agent_id, amount=req.amount))
            self._resource_pool.reserve(req.amount)
    return grants
```

---

## 3. Agent Specialization Through Evolution

### 3.1 Biological Analogy: Cell Differentiation

In embryonic development, stem cells differentiate into specialized cell types
(neurons, muscle cells, blood cells) based on chemical signals in their local
environment. In FLUX, the `AdaptiveProfiler` provides analogous "chemical
signals" through the heat classification system:

| Biological Signal | FLUX Analog | Resulting Specialization |
|---|---|---|
| Morphogen gradient | Heat level (HEAT/HOT/WARM/COOL/FROZEN) | Drives language selection |
| Cell-cell contact | Trust score (pairwise) | Drives communication topology |
| Nutrient availability | `fitness_score` (genome) | Drives resource allocation |
| Mechanical stress | `call_count` * `avg_time_ns` | Drives mutation priority |

### 3.2 Three Agent Archetypes

The evolution engine naturally produces three archetypes:

**Fast Path Executors (FPE):** Agents whose modules are classified as
`HEAT` or `HOT` by the profiler get recompiled to `c_simd` or `rust` via
`MutationStrategy.RECOMPILE_LANGUAGE`. Their genomes accumulate
`OptimizationRecord` entries with high `speedup` values. The fitness function
weights speed at 0.4, so FPE agents achieve high fitness.

```python
# From mutator.py — recompilation proposal for HEAT modules
MutationProposal(
    strategy=MutationStrategy.RECOMPILE_LANGUAGE,
    target=mod_path,         # e.g., "crypto.hash_sha256"
    description=f"Recompile HEAT module {mod_path} from Python to C+SIMD",
    kwargs={"new_language": "c_simd"},
    estimated_speedup=16.0,
    estimated_risk=0.4,
    priority=10.0 * snap.call_count,
)
```

**Creative Explorers (CE):** Agents with many `COOL` modules retain Python
compilation (language modularity score 1.0). Their genomes have high
`_modularity_score()` (weight 0.3) and accumulate diverse tiles through
`ADD_TILE` mutations. These agents are better at discovering new patterns but
slower at execution.

**Coordinators (COORD):** Agents whose bytecode primarily consists of A2A
opcodes (`TELL`, `ASK`, `DELEGATE`, `REDUCE`, `TRUST_CHECK`) specialize in
routing and trust management. The `PatternMiner` may discover that certain
A2A opcode sequences are frequent, leading to `FUSE_PATTERN` mutations that
create specialized coordination tiles (e.g., a "broadcast-filter-reduce"
composite tile).

### 3.3 Evolutionary Game Theory Analysis

We can model agent specialization as a two-player evolutionary game:

| | Opponent: FPE | Opponent: CE |
|---|---|---|
| **FPE** | (3, 3) | (5, 1) |
| **CE** | (1, 5) | (4, 4) |

- (FPE, FPE): Both fast, compete for cycles. Moderate payoff.
- (FPE, CE): FPE exploits CE's flexibility. High payoff for FPE.
- (CE, CE): Both explore, discover complementary patterns. Good payoff.
- (CE, FPE): CE is too slow to collaborate. Low payoff for CE.

This is a variant of the Hawk-Dove game. In a well-mixed population, the
Evolutionarily Stable Strategy (ESS) is a mixed strategy with some fraction p
of FPE agents and (1-p) of CE agents. In FLUX, this fraction is controlled by
the profiler's heat thresholds (`hot_threshold=0.8`, `warm_threshold=0.5`),
which determine what fraction of modules get recompiled. A threshold of 0.8
means approximately 20% of modules become HEAT (FPE candidates), matching the
biological observation that specialized cell types are a minority.

**Coordinator agents** change the game to a three-player variant. Their
presence increases the payoff for both FPE and CE agents by reducing
communication overhead, analogous to how supporting cells (glia) increase
neural efficiency in biological systems.

### 3.4 Cross-Agent Genome Recombination

The current `EvolutionEngine` evolves each agent's genome independently. A
natural extension is cross-agent recombination:

```python
def crossover(genome_a: Genome, genome_b: Genome) -> Genome:
    """Create offspring genome by recombining two parents."""
    child = Genome()
    # Take fast modules from parent A (the FPE)
    for path, snap in genome_a.modules.items():
        if snap.heat_level in ("HEAT", "HOT"):
            child.modules[path] = snap
            child.language_assignments[path] = genome_a.language_assignments[path]
    # Take modular modules from parent B (the CE)
    for path, snap in genome_b.modules.items():
        if path not in child.modules and snap.heat_level in ("COOL", "WARM"):
            child.modules[path] = snap
            child.language_assignments[path] = genome_b.language_assignments[path]
    # Take tiles from both
    child.tiles = {**genome_b.tiles, **genome_a.tiles}
    child.evaluate_fitness()
    return child
```

This would allow the system to create "hybrid" agents that inherit speed from
one parent and flexibility from another, driving the population toward the
game-theoretic ESS.

---

## 4. Deadlock and Livelock Detection

### 4.1 Deadlock Scenarios in A2A Communication

When agents communicate through `ASK` (request-response) or `DELEGATE`
(async work-stealing), circular wait conditions can arise:

**Scenario 1: Mutual ASK.** Agent A sends `ASK` to B, blocking until B
responds. Agent B simultaneously sends `ASK` to A, blocking until A responds.
Both agents are now permanently blocked. In the current implementation,
`ASK` messages are placed in the receiver's mailbox via `LocalTransport.send()`,
but there is no blocking receive---agents must poll with `get_messages()`.
This means the current system is *asynchronous* and immune to this deadlock,
but a synchronous `ASK` implementation (blocking wait for reply) would be
vulnerable.

**Scenario 2: Resource-delegated deadlock.** Agent A delegates a task to B that
requires a resource held by C. Agent C is waiting for a `BARRIER` that A
must participate in. Cycle: A → B → C → A.

**Scenario 3: Trust-gated starvation.** Agent A's trust score drops below
`trust_threshold` for all potential collaborators. Every `send_message()` call
returns `False`. Agent A is effectively deadlocked---it cannot communicate with
anyone, yet its bytecode continues to execute in a tight loop.

### 4.2 Wait-For Graph Construction

The coordinator can maintain a wait-for graph (WFG) to detect cycles:

```python
class DeadlockDetector:
    """Maintains a wait-for graph and detects cycles using Tarjan's algorithm."""

    def __init__(self):
        self._waits: dict[str, set[str]] = defaultdict(set)

    def record_wait(self, agent: str, waiting_for: str):
        self._waits[agent].add(waiting_for)

    def clear_wait(self, agent: str, waiting_for: str):
        self._waits[agent].discard(waiting_for)

    def detect_cycle(self) -> list[str] | None:
        """Return a cycle if one exists, else None."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._waits}
        parent = {}

        def dfs(node):
            color[node] = GRAY
            for neighbor in self._waits.get(node, set()):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle: reconstruct
                    cycle = [neighbor, node]
                    curr = node
                    while curr != neighbor:
                        curr = parent.get(curr)
                        if curr is None:
                            break
                        cycle.append(curr)
                    return cycle
                if color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for node in list(self._waits.keys()):
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None
```

### 4.3 Timeout Strategies

The `A2AMessage` header includes a `priority` field (0--15) but no explicit
timeout. A practical extension:

```python
# Extend AgentCoordinator with per-message timeouts
def send_message_with_timeout(
    self, sender, receiver, msg_type, payload,
    priority=5, timeout_ms=5000
) -> bool:
    """Send with a deadline. Returns False if not acknowledged in time."""
    msg = A2AMessage(
        sender=self._agents[sender]["uuid"],
        receiver=self._agents[receiver]["uuid"],
        conversation_id=uuid.uuid4(),
        message_type=msg_type,
        priority=priority,
        trust_token=int(self.trust.compute_trust(sender, receiver) * 1e9),
        capability_token=0,
        payload=payload,
    )
    delivered = self.transport.send(msg)
    if not delivered:
        return False

    # Schedule timeout check
    deadline = time.time() + timeout_ms / 1000.0
    self._pending_acks[msg.conversation_id] = {
        "sender": sender,
        "receiver": receiver,
        "deadline": deadline,
    }
    return True
```

### 4.4 Trust-Based Priority and Circuit Breakers

The trust engine's composite score naturally implements a circuit breaker
pattern. When trust drops below `trust_threshold`:

1. **Open circuit:** Messages are silently dropped (`send_message` returns
   `False`).
2. **Half-open:** After `revoke_trust` clears history, trust resets to
   `NEUTRAL_TRUST = 0.5`, which is above the default threshold, re-enabling
   communication.
3. **Closed:** Successful interactions rebuild trust, closing the circuit.

**Enhanced circuit breaker with adaptive threshold:**

```python
class AdaptiveCircuitBreaker:
    """Circuit breaker whose threshold adapts to network conditions."""

    def __init__(self, base_threshold=0.3, sensitivity=0.1):
        self.base_threshold = base_threshold
        self.sensitivity = sensitivity
        self.failure_streak = 0

    def should_allow(self, trust_score: float) -> bool:
        # After consecutive failures, raise the bar
        adaptive_threshold = self.base_threshold + self.sensitivity * self.failure_streak
        return trust_score >= adaptive_threshold

    def record_outcome(self, success: bool):
        if success:
            self.failure_streak = max(0, self.failure_streak - 1)
        else:
            self.failure_streak += 1
```

### 4.5 Livelock Detection

Livelock occurs when agents continuously change state in response to each
other without making progress. In FLUX, this can manifest as:

- Two agents repeatedly delegating the same task back and forth.
- The evolution engine proposing and rolling back the same mutation
  indefinitely (the convergence threshold `0.001` prevents this, but with
  noisy fitness measurements it may not).

**Detection heuristic:** Track the number of `DELEGATE_RESULT` messages that
contain the *original* task payload (unchanged). If this counter exceeds a
threshold within a time window, flag a livelock and escalate to the
`EMERGENCY_STOP` opcode (`0x7B`).

---

## 5. Collective Intelligence

### 5.1 Swarm Optimization

Particle Swarm Optimization (PSO) maps directly onto FLUX agents:
each agent is a "particle" with a position (current genome) and velocity
(mutation rate). The swarm's global best position is maintained through
`REDUCE` operations.

**Bytecode for a PSO agent:**

```asm
; R0 = local best fitness
; R1 = global best fitness (from REDUCE)
; R2 = current genome checksum
; R3 = velocity (mutation aggression)

swarm_step:
    ; Compare local vs global best
    CMP   R0, R1
    JLE   update_velocity      ; local is worse or equal

    ; Local is better: update personal best
    MOV   R0, current_fitness
    ; TELL swarm about new best
    0x60, 0x??, 0x??         ; TELL <swarm_id> <local_best_genome>
    JMP   reduce_phase

update_velocity:
    ; Move toward global best: increase mutation rate
    MOVI  R4, 1
    IADD  R3, R4              ; velocity += 1 (more aggressive mutations)

reduce_phase:
    ; REDUCE to find global best
    0x67, 0x??, 0x??         ; REDUCE <fitness_scores>
    ; Result: global_best_fitness in R1

    ; Apply mutation with velocity-controlled aggression
    CALL  mutate_genome        ; uses R3 as mutation rate

    JMP   swarm_step
```

### 5.2 Consensus Protocols

FLUX's trust engine provides a natural foundation for consensus:

**Raft-like leader election:** The agent with the highest cumulative trust
score (sum of all incoming trust) becomes the leader. Trust serves as a
"vote"---agents that consistently deliver correct results accumulate votes.

```python
def elect_leader(coordinator: AgentCoordinator) -> str:
    """Elect the most trusted agent as leader."""
    trust_sums: dict[str, float] = defaultdict(float)
    for agent_a in coordinator.registered_agents():
        for agent_b in coordinator.registered_agents():
            if agent_a != agent_b:
                trust_sums[agent_a] += coordinator.trust.compute_trust(
                    agent_b, agent_a  # incoming trust
                )
    return max(trust_sums, key=trust_sums.get)
```

**Paxos-like consensus on mutations:** Before committing a mutation, the
proposer agent sends `ASK` to a quorum of agents. Each agent validates the
mutation against its own `CorrectnessValidator` baseline. If a majority
approves, the mutation is committed.

```python
class PaxosMutationConsensus:
    """Paxos-inspired consensus for cross-agent mutation commits."""

    def __init__(self, quorum_size: int = 3):
        self.quorum_size = quorum_size

    def propose(self, mutation: MutationProposal, coordinator) -> bool:
        # Phase 1: Prepare
        promises = 0
        for agent_id in coordinator.registered_agents():
            if agent_id == mutation.proposer:
                continue
            # ASK agent to prepare
            ok = coordinator.send_message(
                mutation.proposer, agent_id,
                msg_type=0x61,  # ASK
                payload=mutation.serialize_prepare(),
            )
            if ok:
                promises += 1

        if promises < self.quorum_size:
            return False  # No quorum

        # Phase 2: Accept
        acceptances = 0
        for agent_id in coordinator.registered_agents():
            ok = coordinator.send_message(
                mutation.proposer, agent_id,
                msg_type=0x60,  # TELL (broadcast accept)
                payload=mutation.serialize_accept(),
            )
            if ok:
                acceptances += 1

        return acceptances >= self.quorum_size
```

### 5.3 Distributed Constraint Satisfaction

FLUX agents can collaboratively solve constraint satisfaction problems (CSPs)
where each agent is responsible for a subset of variables. The `ASK` opcode
enables constraint propagation, and `BARRIER` ensures all agents have finished
their local search before proceeding.

**Application:** Optimizing the global tile graph. Each agent is responsible
for a subgraph and must find tile assignments that minimize local cost while
respecting interface constraints with neighboring subgraphs. `ASK` messages
carry constraint proposals, and `REDUCE` computes the global cost.

---

## 6. Open Questions

### 6.1 Fundamental Limits of Multi-Agent Self-Improving Systems

1. **Convergence vs. exploration trade-off:** The `EvolutionEngine` uses a
   convergence threshold of `0.001` to stop evolution when fitness gains are
   marginal. But in a multi-agent setting, one agent's convergence may prevent
   another agent from exploring a beneficial direction. *What is the optimal
   per-agent convergence threshold when agents share a tile registry?*

2. **Trust monopolies:** If a small group of agents builds very high mutual
   trust (through repeated successful interactions), they may lock out newer
   agents whose trust scores start at `NEUTRAL_TRUST = 0.5`. *Should the
   trust engine include an "anti-trust" mechanism that prevents trust
   monopolies, analogous to antitrust law in economics?*

3. **Gödelian limits:** Can a FLUX agent prove that its own evolved bytecode
   is correct? The `CorrectnessValidator` uses behavioral baselines, not
   formal verification. As agents evolve increasingly complex bytecode, the
   gap between tested behavior and possible behavior grows. *Is there a
   fundamental incompleteness in self-improving systems, analogous to
   Gödel's incompleteness theorem?*

4. **Resource bounds:** Each agent has a `max_cycles` budget (default 10M) and
   `memory_size` (default 64KB). As agents evolve to use more complex tiles
   and longer bytecode, these bounds may become limiting. *Should agents be
   able to negotiate resource limits with each other, or should the system
   impose hard caps?*

### 6.2 Stable Organizations

5. **Organizational inertia:** When agents specialize (Section 3), the
   organization becomes more efficient but less adaptable. A sudden workload
   change (e.g., a previously HEAT module becomes FROZEN) may leave FPE agents
   with no useful work. *Can the system detect organizational staleness and
   trigger re-specialization?*

6. **Hierarchy emergence:** The topologies in Section 1 are imposed by the
   programmer. *Can natural hierarchies emerge from flat initial conditions
   through trust dynamics alone?* Preliminary analysis suggests yes: agents
   with high outgoing trust (that trust many others) naturally become hubs,
   while agents with high incoming trust (that are trusted by many) become
   authorities.

7. **Agent reproduction and death:** The current system has no mechanism for
   creating new agents at runtime or terminating existing ones. *Should agents
   be able to fork (create a copy with a mutated genome) or be garbage-collected
   when their fitness drops below a threshold?*

### 6.3 Culture and Cross-Generational Persistence

8. **Cultural transmission:** In human societies, culture persists through
   institutions, documentation, and social norms. In FLUX, "culture" could be
   encoded in: (a) shared tile libraries, (b) trust baseline configurations,
   (c) default genome templates. *Can we define a FLUX "genome inheritance"
   protocol where new agents receive a starter genome from their parent?*

9. **Meme propagation:** Tiles are the closest analogue to "memes"---they are
   reusable patterns that propagate through the tile registry. The
   `PatternMiner` discovers patterns, the `SystemMutator` proposes them as
   tiles, and successful tiles are adopted by other agents. *Can we measure
   the "meme fitness" of a tile---its adoption rate across the agent
   population---and use this to guide evolution?*

10. **Norm emergence:** Trust profiles encode behavioral norms. If an agent
    consistently fails to respond to `ASK` messages, its trust score drops,
    creating a norm: "you must respond to ASKs." *Can we make these norms
    explicit and negotiable, rather than implicit in trust scores?*

11. **Linguistic divergence:** As agents evolve independently, their bytecode
    may become increasingly specialized and opaque to other agents. The
    `FIRBuilder` provides a common intermediate representation, but evolved
    tiles may use custom FIR patterns that other agents cannot interpret.
    *Is a "pidgin" bytecode necessary to maintain inter-agent
    comprehensibility?*

12. **The hard problem of multi-agent alignment:** When agents optimize for
    individual fitness, their collective behavior may not align with the
    system designer's intent. The fitness function weights (speed 0.4,
    modularity 0.3, correctness 0.3) encode preferences, but these are
    fixed. *Should the fitness function itself be subject to evolution, and
    if so, what meta-constraints prevent value drift?*

---

## Appendix A: A2A Opcode Reference

| Opcode | Hex | Category | Format | Description |
|--------|-----|----------|--------|-------------|
| `TELL` | `0x60` | Messaging | G | One-way notification |
| `ASK` | `0x61` | Messaging | G | Request-response query |
| `DELEGATE` | `0x62` | Messaging | G | Delegate task to another agent |
| `DELEGATE_RESULT` | `0x63` | Messaging | G | Return delegated task result |
| `REPORT_STATUS` | `0x64` | Telemetry | G | Report agent status |
| `REQUEST_OVERRIDE` | `0x65` | Control | G | Request another agent to yield |
| `BROADCAST` | `0x66` | Messaging | G | Send to all registered agents |
| `REDUCE` | `0x67` | Aggregation | G | Aggregate values across agents |
| `DECLARE_INTENT` | `0x68` | Coordination | G | Announce intended action |
| `ASSERT_GOAL` | `0x69` | Verification | G | Claim goal has been met |
| `VERIFY_OUTCOME` | `0x6A` | Verification | G | Verify another agent's claim |
| `EXPLAIN_FAILURE` | `0x6B` | Telemetry | G | Explain why an action failed |
| `SET_PRIORITY` | `0x6C` | Control | G | Change message priority |
| `TRUST_CHECK` | `0x70` | Trust | G | Query trust score |
| `TRUST_UPDATE` | `0x71` | Trust | G | Update trust based on observation |
| `TRUST_QUERY` | `0x72` | Trust | G | Query detailed trust profile |
| `REVOKE_TRUST` | `0x73` | Trust | G | Reset trust to neutral |
| `CAP_REQUIRE` | `0x74` | Security | G | Demand capability proof |
| `CAP_REQUEST` | `0x75` | Security | G | Request capability grant |
| `CAP_GRANT` | `0x76` | Security | G | Grant capability to agent |
| `CAP_REVOKE` | `0x77` | Security | G | Revoke previously granted capability |
| `BARRIER` | `0x78` | Synchronization | G | Synchronization point |
| `SYNC_CLOCK` | `0x79` | Synchronization | G | Synchronize logical clocks |
| `FORMATION_UPDATE` | `0x7A` | Coordination | G | Update swarm formation |
| `EMERGENCY_STOP` | `0x7B` | Control | G | Global halt signal |

## Appendix B: Trust Dimension Weights

The INCREMENTS+2 trust engine computes a composite score:

```
T = 0.30 * T_history + 0.25 * T_capability + 0.20 * T_latency
  + 0.15 * T_consistency + 0.05 * T_determinism + 0.05 * T_audit
```

With temporal decay: `T *= (1 - 0.01 * elapsed / 3600)`

For multi-agent orchestration, the key dimensions are:

- **T_history (0.30):** Most heavily weighted. Accumulates through successful
  `send_message()` calls. In swarm topologies, this creates a "rich get richer"
  dynamic---well-connected agents accumulate history faster.
- **T_latency (0.20):** Penalizes slow agents. In pipeline topologies, this
  naturally deprioritizes bottleneck stages.
- **T_consistency (0.15):** Measures coefficient of variation in latency.
  Erratic agents are distrusted, which is important for real-time coordination.

## Appendix C: Mutation Strategy Catalog

| Strategy | Genome Effect | Multi-Agent Impact |
|----------|--------------|-------------------|
| `RECOMPILE_LANGUAGE` | Change module language | Affects agent speed profile; visible to trust engine via T_latency |
| `FUSE_PATTERN` | Create tile from hot sequence | Shared via tile registry; benefits all agents |
| `REPLACE_TILE` | Swap tile for cheaper alternative | Local effect unless tile is shared |
| `ADD_TILE` | Register new tile | Immediately available to all agents |
| `MERGE_TILES` | Fuse co-occurring tiles | Reduces communication overhead in pipeline topologies |
| `SPLIT_TILE` | Decompose complex tile | Increases modularity; may enable new parallelism |
| `INLINE_OPTIMIZATION` | Apply IR-level optimization | Local effect; may change trust behavior signature |

---

*This document is a living research artifact. As the FLUX system evolves, the
open questions above should be revisited, refined, and progressively resolved
through implementation and experimentation.*
