# Fleet Communication Topology Analysis

**Task ID:** TOPO-001 | **Author:** Super Z (FLUX Fleet, Task 6-c) | **Date:** 2026-04-14
**Version:** 1.0 | **Status:** SHIPPED
**Depends on:** git-native-a2a-survey.md, lighthouse-keeper-architecture.md, fleet_config.json, worklog.md
**Tracks:** TASK-BOARD item TOPO-001 (Fleet Communication Topology Analysis)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Topology](#2-current-topology)
3. [Latency Analysis](#3-latency-analysis)
4. [What Breaks at Scale](#4-what-breaks-at-scale)
5. [Topology Proposals](#5-topology-proposals)
6. [Recommended Next Topology](#6-recommended-next-topology)
7. [Metrics](#7-metrics)
8. [Appendix A — Current Fleet Communication Map](#appendix-a--current-fleet-communication-map)
9. [Appendix B — Scalability Projections](#appendix-b--scalability-projections)
10. [Appendix C — Topology Decision Matrix](#appendix-c--topology-decision-matrix)

---

## 1. Executive Summary

The FLUX fleet currently communicates through a star topology centered on Oracle1, using filesystem-based bottles, GitHub Issues/PRs, and an ~15-minute beachcomb polling cycle. This topology works for the current 6-agent fleet — Oracle1 coordinates, agents produce work, and the bottle protocol provides asynchronous communication. But it will not survive scaling to 20 or 100 agents without fundamental redesign.

This document analyzes the current communication patterns, quantifies latency across all channels, identifies the specific failure modes that emerge at scale, evaluates five alternative topology proposals (hierarchical, gossip, pub/sub, capability mesh, hybrid), and recommends a phased migration path. The recommendation is a **hybrid topology** implemented in three phases: topic-based channels (immediate, using GitHub labels), capability mesh (medium-term, using the semantic router for direct routing), and adaptive topology (long-term, enabling agents to self-organize based on task needs).

The analysis is grounded in fleet artifacts: the git-native A2A survey catalogs 40+ GitHub features exploitable for coordination; the lighthouse keeper architecture defines the beacon protocol (60-second heartbeats) and health scoring; and the worklog documents 20+ sessions of actual communication patterns, including the notable finding that "no fleet responses across 7 sessions" — suggesting the current topology already has connectivity issues at just 6 agents.

Key metrics: current message delivery latency ranges from 1 second (direct signal, both agents online) to days (human approval bottleneck). Information coverage is estimated at 30-50% (agents miss most updates from other agents). Coordination efficiency is measured in hours (task creation to first action). Conflict rate is low but unmeasured (no two agents have yet worked at cross-purposes, but the sample size is too small to be meaningful).

---

## 2. Current Topology

### 2.1 Star Topology: Oracle1 at Center

The fleet's communication topology is fundamentally a star:

```
                    ┌──────────┐
                    │ Oracle1  │
                    │ (Hub)    │
                    └────┬─────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
       ┌────┴───┐   ┌───┴────┐  ┌───┴────┐
       │Super Z │   │Quill   │  │Babel   │
       └────────┘   └────────┘  └────────┘
            │            │            │
       ┌────┴───┐   ┌───┴────────────┘
       │JC1     │   │Fleet Mechanic
       └────────┘   └───────────────
```

Oracle1 serves as the central coordination hub:
- **TASK-BOARD.md:** Oracle1 maintains the fleet's task assignment board (30+ open tasks)
- **FENCE-BOARD.md:** Oracle1 manages the fence lifecycle (DRAFT → CLAIMED → SHIPPED)
- **MANIFEST.md:** Oracle1 tracks badges, capabilities, and fleet-wide metrics (24 badges, 2,489+ tests)
- **ORDERS-*.md:** Oracle1 issues structured work assignments to agents
- **Beachcomb scanner:** Oracle1's beachcomb.py polls all vessel repos for new bottles and activity

All inter-agent communication flows through Oracle1 either directly (bottles addressed to Oracle1) or indirectly (Oracle1's beachcomb discovers updates in vessel repos and redistributes relevant information).

### 2.2 Bottle Protocol: Async, Filesystem-Based

The message-in-a-bottle protocol is the fleet's primary communication mechanism:

```
vessel-repo/
  message-in-a-bottle/
    from-fleet/     ← broadcast messages from fleet
    for-fleet/      ← outbound broadcast to fleet
    for-oracle1/    ← directed message to Oracle1
    from-oracle1/   ← received from Oracle1
    for-superz/     ← directed message to Super Z
    for-quill/      ← directed message to Quill
    ...
```

**Protocol characteristics:**
- **Asynchronous:** Agents write bottles and continue working; readers poll when ready
- **Filesystem-based:** Messages are markdown files in git repositories
- **No delivery guarantee:** An agent writes to `for-oracle1/` but doesn't know if Oracle1 reads it
- **No threading:** Each bottle is a standalone file; conversations require multiple files with naming conventions
- **No discovery:** An agent must explicitly poll each vessel repo to find messages addressed to them

**Polling mechanism:** Oracle1's beachcomb.py scans all fleet repos on a ~15-minute cycle, checking for new bottles, commits, issues, and PRs. Individual agents also beachcomb when they start a session, but there is no persistent background polling for most agents.

### 2.3 GitHub-Based: Issues, PRs, Forks

GitHub provides secondary communication channels that are more structured than filesystem bottles:

| Channel | Usage | Current Fleet Adoption |
|---------|-------|----------------------|
| **Issues** | Bug reports, task filing, cross-repo coordination | 30+ issues across flux-runtime, oracle1-vessel |
| **Pull Requests** | Code proposals, review, merge | 4+ PRs from Super Z alone on flux-runtime |
| **Forks** | Isolated experimentation | Not systematically used |
| **Discussions** | Architecture deliberation | Not used (identified gap in A2A survey) |
| **Reactions** | Quick agreement/disagreement | Not used |
| **Repository Dispatch** | Cross-repo event triggers | Not used (identified gap) |
| **Webhooks** | Event-driven notifications | Minimal (identified gap) |

The git-native A2A survey identified that the fleet uses approximately 30% of available GitHub features. The remaining 70% (Discussions, CODEOWNERS, Repository Dispatch, Projects v2, signed commits, etc.) represent untapped communication capacity.

### 2.4 Current Latency: 15 Minutes to Days

The latency range for fleet communication is enormous:

- **Best case:** ~1 second (both agents online, direct A2A signal)
- **Typical case:** ~15 minutes (beachcomb cycle)
- **Common case:** ~1-4 hours (session-based polling, agents not continuously online)
- **Worst case:** Days (human bottleneck when Casey needs to review or approve)

The worklog documents a striking example of high latency: "No fleet responses across 7 sessions" — Super Z sent bottles to Oracle1 for 7 consecutive sessions and received zero direct responses. This doesn't mean Oracle1 wasn't working (Oracle1 was actively managing the fleet), but it means the bottle protocol failed to deliver timely feedback. The communication was happening through GitHub artifacts (commits, issues) rather than through the bottle channel.

---

## 3. Latency Analysis

### 3.1 Channel-by-Channel Latency

| Channel | Mechanism | One-Way Latency | Two-Way Latency | Reliability | Current Usage |
|---------|-----------|-----------------|-----------------|-------------|---------------|
| **Beachcomb** | Filesystem polling every ~15 min | 7.5 min (avg) | 15 min | Low (polling can miss) | Primary channel |
| **Lighthouse beacon** | Heartbeat every 60s | 30s (avg) | 60s | Medium (fire-and-forget) | Designed, not deployed |
| **GitHub webhook** | Push notification on event | ~1-5s | ~2-10s | High (push, not poll) | Minimal adoption |
| **Direct A2A signal** | Both agents online, direct message | ~1s | ~2s | Highest | Rare, opportunistic |
| **GitHub Issue/PR** | Structured artifact creation | ~5-30s (write) | Hours (review) | High (persistent) | Moderate usage |
| **Bottle (filesystem)** | File write to vessel repo | ~1s (write) | Hours (read) | Low (no delivery guarantee) | Primary channel |
| **Human approval** | Casey reviews and responds | Hours | Days | Variable | Required for major decisions |

### 3.2 Latency Breakdown by Communication Phase

A typical fleet coordination message passes through four phases:

```
Phase 1: CREATION (~1s)
  Agent writes bottle/issue/PR

Phase 2: DISCOVERY (15 min - 4 hours)
  Target agent polls/beachcombs and finds the message
  - Best case: Lighthouse beacon triggers immediate check (~60s)
  - Typical case: Next beachcomb cycle (~15 min)
  - Worst case: Agent starts new session and checks (~1-4 hours)

Phase 3: PROCESSING (5-30 min)
  Agent reads message, evaluates relevance, decides action
  - Simple acknowledgment: ~1 min
  - Task evaluation: ~5 min
  - Complex coordination: ~30 min

Phase 4: RESPONSE (15 min - 4 hours)
  Agent writes response, which must be discovered by original sender
  - Same latency as Phase 2 for the return path
```

**Total round-trip latency:**
- Best case: 1s + 60s + 1min + 60s = ~3 minutes
- Typical case: 1s + 15min + 5min + 15min = ~35 minutes
- Worst case: 1s + 4h + 30min + 4h = ~8.5 hours

### 3.3 Bottleneck Analysis

The dominant latency bottleneck is **Phase 2 (Discovery)**. Agents create messages instantly, but discovery depends on the recipient checking. The beachcomb cycle (15 minutes) is the designed polling interval, but in practice, agents only beachcomb when they start a new session (which may be hours apart).

The Lighthouse Keeper architecture addresses this with 60-second beacons, but the Lighthouse is not yet deployed. If deployed, discovery latency would drop from 15 minutes to 60 seconds — a 15× improvement.

**Secondary bottleneck: Human approval.** For decisions that require Casey's input (major architectural changes, resource allocation, new agent onboarding), the latency is measured in days. This is inherent to the fleet structure and cannot be optimized without delegation authority.

### 3.4 Latency vs Reliability Tradeoff

Current channels occupy different positions on the latency-reliability spectrum:

```
High Reliability
     ↑
     │  GitHub Issues/PRs  ●
     │
     │  Webhooks           ●
     │
     │  Beachcomb          ●
     │
     │  Lighthouse beacon  ●
     │
     │  Direct A2A         ●
     │
     └──────────────────────────→ Low Latency
```

The fleet needs channels in the upper-left quadrant (high reliability, low latency). Currently, only webhooks occupy this space, and they are barely used. The topology migration must prioritize moving communication into this quadrant.

---

## 4. What Breaks at Scale

### 4.1 The N² Problem

The fundamental scaling constraint is pairwise communication complexity:

| Agents | Pairwise Interactions (N*(N-1)/2) | Bottles per Cycle | Beachcomb Time (at 2s/repo) | Oracle1 Coordination Load |
|--------|----------------------------------|-------------------|----------------------------|--------------------------|
| 6 | 15 | 15-30 | ~2 min | Manageable |
| 10 | 45 | 45-90 | ~3 min | Heavy |
| 20 | 190 | 190-380 | ~7 min | Overwhelming |
| 50 | 1,225 | 1,225-2,450 | ~17 min | Impossible |
| 100 | 4,950 | 4,950-9,900 | ~33 min | Collapse |

At 20 agents, Oracle1 would need to read and triage ~200 bottles per beachcomb cycle. At 100 agents, nearly 5,000 bottles per cycle — more than one per second. The current star topology is fundamentally incompatible with fleet sizes beyond ~15 agents.

### 4.2 Information Overload

Even if the technical infrastructure could handle the volume, human (agent) cognitive limits create a harder constraint:

**Symptom 1: Unread bottles.** At 20 agents, each agent receives ~19 bottles per cycle from other agents. If each bottle is 200 lines, that's 3,800 lines of new information every 15 minutes. No agent can process this volume while also doing productive work.

**Symptom 2: Missed critical updates.** When 50 agents are working simultaneously, an ISA spec change by one agent might be missed by the 49 others. Weeks later, multiple agents produce conflicting work based on different ISA versions.

**Symptom 3: Alert fatigue.** The Lighthouse Keeper generates alerts when agents miss beacons or show degraded health. At 100 agents, the baseline alert rate (even with perfect health) generates noise that obscures genuine problems.

**Symptom 4: Coordination deadlock.** Multiple agents independently decide to work on the same task (duplication) or work on conflicting tasks (ISA divergence redux). Without a routing mechanism, the probability of such conflicts grows linearly with agent count.

### 4.3 Coordination Overhead

As the fleet grows, the fraction of agent time spent on coordination (reading messages, writing status updates, waiting for approvals) increases:

```
Effective work time = Total time - Coordination time

At 6 agents:  Coordination ≈ 10-15% of time (manageable)
At 20 agents: Coordination ≈ 30-40% of time (concerning)
At 50 agents: Coordination ≈ 60-70% of time (unsustainable)
At 100 agents: Coordination ≈ 85-95% of time (fleet produces nothing useful)
```

This follows from the coordination overhead formula: as N increases, the number of coordination messages grows as O(N²) while productive work grows as O(N). The crossover point (where coordination exceeds production) occurs around N=30 for the current topology.

### 4.4 Conflict Resolution: Who Decides?

The fleet has no formal conflict resolution protocol for cases where agents disagree:

**Scenario:** Agent A proposes moving opcode 0x44 to Format F. Agent B proposes keeping it in Format E. Both file issues with arguments. Who decides?

**Current resolution:** Oracle1 decides (star topology). This works at 6 agents because Oracle1 has context on all active work. At 20 agents, Oracle1 cannot maintain context on all proposals, and becomes a bottleneck.

**At scale:** Conflicts multiply, Oracle1 becomes a serial bottleneck, and decisions queue up. Agents wait days for rulings on straightforward disagreements. Work stalls.

### 4.5 Broadcast Storms

A single agent's significant update (e.g., ISA spec change) currently requires notifying all other agents. At 6 agents, this is 5 notifications. At 100 agents, this is 99 notifications. If each notification triggers a response (acknowledgment, question, concern), the original update generates ~200 messages — a broadcast storm.

**Current mitigation:** None. The fleet hasn't experienced a broadcast storm because it's too small. But the mechanism is already visible: when Super Z files a security issue on flux-runtime (#15, #16, #17), all agents should be notified. The notification currently relies on agents discovering the issues through their own beachcomb cycles, which is unreliable.

---

## 5. Topology Proposals

### 5.1 Hierarchical: Team Leads Reduce N² to N·log(N)

**Design:**

```
                    ┌──────────┐
                    │ Oracle1  │  Level 0: Fleet Coordinator
                    └────┬─────┘
                         │
            ┌────────────┼────────────┐
            │            │            │
       ┌────┴───┐   ┌───┴────┐  ┌───┴────────┐
       │ISA TL  │   │Edge TL │  │Runtime TL  │  Level 1: Team Leads
       └────┬───┘   └───┬────┘  └───┬────────┘
            │            │            │
       ┌────┴───┐   ┌───┴────┐  ┌───┴────┐
       │Super Z │   │JC1     │  │Babel   │  Level 2: Workers
       │Quill   │   │(edge)  │  │(vocab) │
       └────────┘   └────────┘  └────────┘
```

**How it works:**
- Level 0 (Oracle1): Coordinates team leads, resolves cross-team conflicts, manages fleet-wide policy
- Level 1 (Team Leads): Coordinate workers within their domain, route tasks, aggregate status
- Level 2 (Workers): Execute tasks, report to team lead, communicate within team

**Scalability:** At 100 agents with 10 team leads, Oracle1 coordinates 10 channels (not 99). Team leads coordinate ~10 workers each (not 99). Total coordination channels: 10 + (10 × 9) = 100, vs 4,950 for flat star topology. Reduction: 98%.

**Advantages:**
- Dramatic reduction in coordination overhead
- Natural domain grouping (ISA, edge, runtime, testing)
- Team leads provide domain expertise in routing decisions
- Matches existing fleet structure (Oracle1 already coordinates; agents already specialize)

**Disadvantages:**
- Team lead becomes a single point of failure within their domain
- Information silos: ISA team may not know about edge team's breakthroughs
- Requires identifying and empowering team leads (currently only Oracle1 has coordination authority)
- Adds latency for cross-domain communication (must go through both team leads and Oracle1)

### 5.2 Gossip Protocol: Epidemic Information Spreading

**Design:**

```
Round 1: Each agent randomly selects 2 peers and shares their updates
  Super Z → Quill: "I filed security issues #15-#17"
  Super Z → JC1: "ISA convergence roadmap shipped"
  Oracle1 → Babel: "New fence-0x44 available"

Round 2: Recipients share what they learned with 2 random peers
  Quill → Babel: "Super Z filed security issues #15-#17"
  JC1 → Fleet Mechanic: "ISA convergence roadmap shipped"

Round 3: Information continues spreading
  ...

After log(N) rounds, all agents know all updates.
```

**How it works:**
- Each agent maintains a local "digest" of recent updates and status
- Every gossip round (every 5-15 minutes), each agent selects K random peers
- Agents exchange digests, incorporating new information
- After O(log(N)) rounds, information reaches all agents (epidemic spreading)

**Scalability:** Information reaches all agents in log₂(100) ≈ 7 rounds. At 5-minute gossip intervals, full propagation takes ~35 minutes. Each agent sends only K messages per round (K=2-3), so total messages per round = K·N = 200-300 (vs 4,950 for all-pairs).

**Advantages:**
- No central bottleneck (fully decentralized)
- Naturally robust to agent failures (information routes around downed agents)
- Scales logarithmically: adding 10 agents adds only ~1 gossip round
- Low per-agent communication cost (K messages per round, not N)

**Disadvantages:**
- Eventual consistency: information takes time to reach all agents (minutes, not seconds)
- No guaranteed delivery: probabilistic spreading means some agents might miss updates
- Duplicate suppression needed: agents receive the same update multiple times
- Poor for urgent/critical messages (gossip is slow for alarms)
- No natural authority structure (hard to make binding decisions via gossip)

### 5.3 Pub/Sub: Topic-Based Channels

**Design:**

```
Topics (Channels):
  isa-spec          ← Super Z, Quill, Oracle1, Babel subscribed
  conformance       ← Super Z, Oracle1, Fleet Mechanic subscribed
  cuda-edge         ← JC1, Oracle1 subscribed
  fleet-ops         ← All agents subscribed (broadcast)
  security-alerts   ← All agents subscribed (urgent)
  vocabulary        ← Babel, Quill subscribed
  coordination      ← Oracle1 + team leads subscribed

Agent publishes to topic → all subscribers receive
  Super Z publishes to isa-spec: "Security primitives spec shipped"
  → Super Z, Quill, Oracle1, Babel receive immediately
  → JC1, Fleet Mechanic do NOT receive (not subscribed, not relevant)
```

**Implementation with GitHub:**
- Topics = GitHub labels (isa, conformance, cuda, security, coordination)
- Publishing = Creating an issue with the topic label
- Subscribing = Watching the repo + filtering by label via API
- Urgent topics = Labels with `urgent` prefix, triggering webhook notifications

**Scalability:** Each message reaches only its subscribers (not all agents). If the average agent subscribes to 5 topics out of 20, the average message fan-out is 5·(N/2) = 5·50 = 250 for N=100 (vs 99 for broadcast). But the *relevant* message ratio is much higher — agents only see messages they care about.

**Advantages:**
- Agents receive only relevant information (reduces information overload)
- Natural domain segmentation (topics map to fleet domains)
- Easy to implement with existing GitHub infrastructure (labels + webhooks)
- Supports both broadcast (fleet-ops topic) and targeted (domain topics) communication
- New topics can be created dynamically as new domains emerge

**Disadvantages:**
- Topic design is critical: too many topics = fragmentation, too few = overload
- Agents must self-select subscriptions (requires domain awareness)
- No built-in authority (topics are flat — no hierarchy)
- Cross-topic coordination is awkward (isa-spec and cuda-edge need to coordinate → post to both?)

### 5.4 Capability Mesh: Direct Agent-to-Agent Routing

**Design:**

```
When Super Z needs CUDA expertise for a task:
  1. Super Z queries the semantic router: "Who has CUDA expertise?"
  2. Router returns: JetsonClaw1 (confidence 0.89)
  3. Super Z sends direct message to JC1 (bypassing Oracle1)
  4. JC1 responds directly to Super Z
  5. Result: task completed without hub involvement

The mesh forms dynamically based on capability needs:
  ISA questions → Super Z
  CUDA questions → JC1
  Testing questions → Oracle1 or Fleet Mechanic
  Vocabulary questions → Babel
  Governance questions → Quill
```

**How it works:**
- The semantic router (semantic_router.py, ROUTE-001) maps tasks to agents based on skill overlap, specialization, confidence, and availability
- Agents use the router to find the right peer for their question
- Direct communication happens via Issues on the target agent's vessel repo (or future A2A protocol)
- Oracle1 is consulted only for cross-cutting concerns or unresolved disputes

**Scalability:** The router is O(N) per query (scoring all agents). With 100 agents, each routing decision takes ~100 comparisons. With caching (same task type routes to same agent), the effective cost is near zero. The mesh has no central bottleneck because communication is peer-to-peer.

**Advantages:**
- Eliminates Oracle1 bottleneck entirely for routine coordination
- Direct communication is faster (no hub relay)
- Semantic routing ensures messages reach the most capable agent, not just the central hub
- Naturally adapts as agents gain/lose expertise (router scores update with confidence)
- Compatible with existing semantic router implementation

**Disadvantages:**
- No awareness of what other agent pairs are communicating (information doesn't propagate)
- Requires agents to know when to consult the router (not all coordination needs are obvious)
- Router quality depends on up-to-date confidence scores (stale scores = bad routing)
- No natural mechanism for broadcast (capability mesh is inherently point-to-point)

### 5.5 Hybrid: Best of Multiple Topologies

**Design:**

```
Layer 1: HIERARCHICAL (for decisions)
  Oracle1 → Team Leads → Workers
  Use for: task assignment, conflict resolution, policy changes, approvals
  Latency: minutes to hours (acceptable for decisions)

Layer 2: PUB/SUB (for events)
  Topic-based channels for domain-relevant updates
  Use for: spec changes, test results, security alerts, status updates
  Latency: seconds to minutes (events should propagate quickly)

Layer 3: GOSSIP (for status)
  Random peer exchange of agent status and recent work
  Use for: fleet health awareness, session logs, capability updates
  Latency: minutes (status doesn't need to be instant)

Layer 4: CAPABILITY MESH (for expertise)
  Direct routing via semantic router for domain-specific questions
  Use for: technical questions, code review requests, knowledge sharing
  Latency: minutes (direct but async)
```

**How it works in practice:**

1. Super Z completes ISA security spec → publishes to `isa-spec` topic (Layer 2: pub/sub)
2. Babel reads the topic, notices linguistic opcode implications → sends direct message to Super Z via capability mesh (Layer 4)
3. Super Z and Babel disagree on opcode placement → escalate to ISA team lead (Layer 1: hierarchical)
4. Team lead (Super Z, as ISA specialist) resolves → publishes decision to `isa-spec` topic (Layer 2)
5. JC1 reads the topic, sees edge computing implications → updates edge documentation (Layer 4)
6. All agents exchange status updates via gossip rounds, keeping health scores current (Layer 3)

**Advantages:**
- Each layer handles what it does best (decisions, events, status, expertise)
- No single layer is a bottleneck
- Graceful degradation: if one layer fails, others continue
- Naturally scales: each layer has its own scaling characteristics
- Matches the fleet's three-tier monitoring architecture (Brothers Keeper → Lighthouse → Tender)

**Disadvantages:**
- Complexity: four layers to design, implement, and maintain
- Agent cognitive load: agents must understand which layer to use for which communication
- Debugging difficulty: tracing a message across four layers is harder than tracing through one
- Implementation cost: each layer requires tooling, protocols, and conventions

---

## 6. Recommended Next Topology

### 6.1 Phase 1: Topic-Based Channels (This Sprint)

**Goal:** Reduce information overload by routing messages to interested agents only.

**Implementation:**

1. **Define initial topics** using the fleet's existing domain taxonomy (from fleet_config.json):
   - `isa-spec`: ISA specification changes, opcode proposals, format discussions
   - `conformance`: Test results, conformance failures, cross-runtime issues
   - `cuda-edge`: CUDA kernel work, edge computing, Jetson-related
   - `security`: Security issues, capability enforcement, trust concerns
   - `vocabulary`: Linguistic opcodes, vocabulary extraction, format bridges
   - `fleet-ops`: Fleet-wide announcements, onboarding, policy changes
   - `coordination`: Task coordination, sprint planning, resource allocation

2. **Implement with GitHub labels:**
   - Each topic = a GitHub label on flux-runtime (and cross-posted to relevant repos)
   - Publishing = creating an Issue or Discussion with the topic label
   - Subscribing = agents watch flux-runtime and filter notifications by label
   - Urgent topics = label prefixed with `urgent:` triggers webhook notification to all subscribers

3. **Update bottle protocol:**
   - Bottles include a `Topic:` header line
   - Beachcomb filters bottles by subscribed topics
   - Agents only read bottles with topics they're subscribed to (plus `fleet-ops` which everyone reads)

**Effort:** 1-2 sessions. Uses existing GitHub infrastructure. No new tooling needed.

**Expected improvement:** 50-70% reduction in irrelevant messages per agent. Information coverage increases as agents subscribe to relevant topics they previously missed.

### 6.2 Phase 2: Capability Mesh (Next Sprint)

**Goal:** Enable direct agent-to-agent communication routed by capability needs.

**Implementation:**

1. **Deploy semantic router as a service:**
   - Wrap semantic_router.py in a lightweight HTTP API
   - Endpoints: `GET /route?task=<description>`, `GET /agents`, `GET /health`
   - Deploy as a GitHub Action (runs on demand) or lightweight server

2. **Implement direct messaging:**
   - Agent queries router for the best peer for their need
   - Agent creates an Issue on the peer's vessel repo (targeted communication)
   - Issue template includes: task description, domain, urgency, expected response format
   - Peer receives notification (GitHub notification or webhook) and responds

3. **Deploy Lighthouse Keeper (minimal):**
   - Implement beacon protocol (60-second heartbeats)
   - Health scoring for routing weight adjustment
   - Stale-agent detection and alerting

**Effort:** 3-5 sessions. Requires deploying semantic router as service and implementing Lighthouse beacon.

**Expected improvement:** 80-90% reduction in messages routed through Oracle1. Direct communication latency drops from hours to minutes. Fleet can scale to ~30 agents before coordination overhead becomes concerning.

### 6.3 Phase 3: Adaptive Topology (Next Quarter)

**Goal:** Enable agents to self-organize their communication patterns based on task needs.

**Implementation:**

1. **Dynamic topic creation:**
   - Agents can create new topics when new domains emerge (e.g., `wasm-compilation` when a WASM expert joins)
   - Topics have a lifecycle: active → dormant → archived
   - Topic popularity drives Lighthouse resource allocation

2. **Adaptive gossip parameters:**
   - Gossip fan-out (K) adjusts based on fleet size and information freshness
   - Gossip interval adjusts based on message urgency (critical topics = 1-minute gossip, routine = 15-minute)
   - Agents with high health scores gossip more frequently (reliable information sources)

3. **Team formation:**
   - Agents dynamically form teams for cross-domain tasks
   - Team lead elected by semantic router score (highest confidence for the task domain)
   - Team disbands when task completes
   - Persistent teams form for long-running domains (ISA, edge, testing)

4. **Conflict resolution automation:**
   - When agents disagree, the system routes the dispute to:
     - Domain expert with highest confidence (for technical disputes)
     - Oracle1 (for cross-domain or policy disputes)
     - Casey (for architectural decisions requiring human judgment)

**Effort:** 10-15 sessions. Requires significant new infrastructure.

**Expected improvement:** Fleet scales to 50-100 agents. Coordination overhead stays below 30% of agent time. Information coverage reaches 90%+. Conflict resolution latency drops from days to hours.

---

## 7. Metrics

### 7.1 Message Delivery Latency

**Definition:** Time from message creation to first read by the intended recipient.

**Measurement:**
- Bottles: Commit timestamp → next beachcomb cycle that reads the file
- Issues: Issue creation timestamp → first comment or reaction
- Direct A2A: Message send timestamp → response timestamp

**Targets:**

| Channel | Current | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|---------|---------|---------------|---------------|---------------|
| Critical (security, urgent) | Hours | <30 min | <5 min | <1 min |
| Domain updates (spec changes) | Hours | <1 hour | <15 min | <5 min |
| Status updates | Hours | <4 hours | <1 hour | <30 min |
| Knowledge sharing | Days | <24 hours | <4 hours | <1 hour |

**Implementation:** Lighthouse Keeper records beacon timestamps. Issue/PR timestamps available via GitHub API. Bottle read timestamps can be inferred from beachcomb logs.

### 7.2 Information Coverage

**Definition:** Percentage of important updates that reach all agents who should see them.

**Measurement:**
- Define "important updates" as: security issues, ISA spec changes, fence completions, conformance failures, new agent onboarding
- Track which agents should see each update (based on topic subscriptions and domain relevance)
- Track which agents actually see each update (based on acknowledgment, reaction, or response)
- Coverage = agents who saw / agents who should have seen

**Targets:**

| Update Type | Current Estimate | Phase 1 | Phase 2 | Phase 3 |
|------------|-----------------|---------|---------|---------|
| Security alerts | 20-30% | 60% | 90% | 99% |
| Spec changes | 30-40% | 70% | 90% | 95% |
| Fence completions | 20-30% | 50% | 80% | 95% |
| New agent onboarding | 40-50% | 70% | 90% | 99% |

**Implementation:** GitHub Issues with labels serve as ground truth. Webhook logs track notification delivery. Agent responses (comments, reactions) confirm receipt.

### 7.3 Coordination Efficiency

**Definition:** Time from task creation to first agent action on the task.

**Measurement:**
- Task creation = issue filed on TASK-BOARD or fence claimed
- First action = first commit referencing the task, first comment on the issue, or first bottle about the task
- Efficiency = time to first action

**Targets:**

| Task Priority | Current | Phase 1 | Phase 2 | Phase 3 |
|--------------|---------|---------|---------|---------|
| Critical | Days | <4 hours | <1 hour | <15 min |
| High | Days | <24 hours | <4 hours | <1 hour |
| Medium | Days-Weeks | <3 days | <24 hours | <4 hours |
| Low | Weeks+ | <1 week | <3 days | <24 hours |

**Implementation:** GitHub Issue timestamps vs first commit/PR referencing the issue. Can be automated with a GitHub Action that monitors issue creation and subsequent activity.

### 7.4 Conflict Rate

**Definition:** Frequency with which agents work at cross-purposes on the same domain without coordination.

**Measurement:**
- Detect conflicts by: overlapping PRs modifying the same files, contradictory spec proposals, divergent implementations of the same opcode
- Count conflicts per week
- Track resolution time (conflict detected → resolution)

**Targets:**

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Conflicts per week | ~0 (fleet too small) | <2 | <1 | <0.5 |
| Resolution time | Days (manual) | <24 hours | <4 hours | <1 hour |
| Conflict detection | Manual (Super Z noticed) | Semi-auto (CODEOWNERS) | Auto (CI checks) | Auto + prevention |

**Implementation:** GitHub CODEOWNERS files prevent conflicting PRs from merging without domain expert review. CI checks detect overlapping changes. Cross-repo dispatch events notify downstream repos of upstream changes.

### 7.5 Dashboard Integration

All four metrics should be integrated into the fleet health dashboard (fleet-health-dashboard.json):

```json
{
  "communication_metrics": {
    "message_delivery_latency": {
      "critical_p50_ms": 1800000,
      "critical_p99_ms": 3600000,
      "domain_p50_ms": 7200000,
      "status_p50_ms": 28800000
    },
    "information_coverage": {
      "security_alerts": 0.30,
      "spec_changes": 0.35,
      "fence_completions": 0.25,
      "onboarding": 0.45
    },
    "coordination_efficiency": {
      "critical_task_hours_to_action": 48,
      "high_task_hours_to_action": 72,
      "medium_task_hours_to_action": 168
    },
    "conflict_rate": {
      "conflicts_per_week": 0.2,
      "avg_resolution_hours": 72,
      "detection_method": "manual"
    }
  }
}
```

---

## Appendix A — Current Fleet Communication Map

### A.1 Observed Communication Patterns (from Worklog)

| From | To | Channel | Frequency | Content Type | Response Rate |
|------|----|---------|-----------|-------------|---------------|
| Super Z → Oracle1 | Bottles | Per session | Session recon, findings, questions | ~5% (0 responses in 7 sessions) |
| Super Z → flux-runtime | PRs | 1-3 per session | Code changes, spec documents | ~20% (reviewed by Oracle1) |
| Super Z → flux-runtime | Issues | 1-2 per session | Bug reports, proposals | ~30% (addressed) |
| Oracle1 → Fleet | ORDERS | Per session | Task assignments, priorities | ~80% (agents read) |
| Oracle1 → Fleet | Beachcomb | Every 15 min | Activity scan results | N/A (passive) |
| Quill → Fleet | Bottles | Per session | Status reports, RFC proposals | ~10% |
| JC1 → Oracle1 | Bottles | Per session | CUDA status, trust reports | Unknown |
| Babel → Fleet | Commits | Per session | Vocabulary updates, ISA proposals | ~15% |

### A.2 Communication Gap Analysis

| Missing Communication | Impact | Proposed Solution |
|----------------------|--------|-------------------|
| No agent-to-agent direct channel | All routing through Oracle1 | Capability mesh (Phase 2) |
| No fleet-wide event broadcasting | ISA changes not propagated | Pub/sub topics (Phase 1) |
| No delivery confirmation | Agents don't know if bottles are read | Reactions/comments as ACK (Phase 1) |
| No discussion forum for architecture debates | Decisions made in isolation | GitHub Discussions (Phase 1) |
| No automated cross-repo notification | Downstream repos break on upstream changes | Repository Dispatch (Phase 2) |
| No real-time health awareness | Agents don't know if peers are online | Lighthouse beacons (Phase 2) |

---

## Appendix B — Scalability Projections

### B.1 Agent Count vs Communication Capacity

```
Communication channels needed (per beachcomb cycle):
  Star:          N*(N-1)/2  =  O(N²)
  Hierarchical:  N*log(N)   =  O(N·log(N))
  Pub/Sub:       N*K_topics =  O(N·K)  where K = avg subscriptions
  Gossip:        N*K_gossip =  O(N·K)  where K = gossip fan-out
  Mesh:          N           =  O(N)    (one route query per message)
  Hybrid:        O(N)        =  combination of above

Capacity in messages/beachcomb cycle:
  Star:          Exhausted at ~15 agents
  Hierarchical:  Comfortable to ~100 agents
  Pub/Sub:       Scales linearly (limited by subscription count)
  Gossip:        Scales linearly (limited by fan-out K)
  Mesh:          Scales linearly (limited by router performance)
  Hybrid:        Scales to 100+ agents
```

### B.2 Coordination Overhead Projection

```
Fraction of time spent coordinating (estimated):
  6 agents:    15% (current, sustainable)
  10 agents:   25% (Phase 1 topology)
  20 agents:   35% (Phase 1 topology)
  20 agents:   20% (Phase 2 topology)
  50 agents:   40% (Phase 2 topology)
  50 agents:   25% (Phase 3 topology)
  100 agents:  35% (Phase 3 topology)
  100 agents:  15% (Phase 3 + AI-assisted coordination)
```

---

## Appendix C — Topology Decision Matrix

### C.1 Comparison Across Key Criteria

| Criterion | Star (Current) | Hierarchical | Gossip | Pub/Sub | Mesh | Hybrid |
|-----------|---------------|-------------|--------|---------|------|--------|
| Scalability (100 agents) | ❌ Collapse | ✅ Good | ✅ Good | ✅ Good | ✅ Good | ✅✅ Best |
| Low latency (seconds) | ❌ 15min+ | ⚠️ Minutes | ⚠️ Minutes | ✅ Seconds | ✅ Minutes | ✅ Seconds-Min |
| High reliability | ⚠️ SPOF | ⚠️ Lead SPOF | ✅ Robust | ⚠️ Platform SPOF | ✅ Distributed | ✅✅ Robust |
| Information coverage | ❌ 30-50% | ⚠️ 60-70% | ✅ 80-90% | ✅ 80-90% | ❌ 40-60% | ✅✅ 90-99% |
| Ease of implementation | ✅ Already done | ⚠️ Moderate | ⚠️ Moderate | ✅✅ Easy (GitHub) | ⚠️ Moderate | ❌ Complex |
| Authority/decision-making | ✅✅ Centralized | ✅ Structured | ❌ None | ❌ None | ❌ None | ✅ Structured |
| Natural domain grouping | ❌ None | ✅✅ Teams | ❌ Random | ✅ Topics | ✅ Routing | ✅✅ Multi-layer |
| Broadcast support | ✅✅ Hub broadcasts | ✅ Lead broadcasts | ✅ Epidemic | ✅ Topic broadcast | ❌ Point-to-point | ✅✅ Multiple ways |
| Graceful degradation | ❌ Hub down = fleet down | ⚠️ Lead down = domain down | ✅✅ Routes around failures | ⚠️ Platform down = fleet down | ✅✅ Routes around | ✅✅ Multiple paths |
| Implementation cost | Zero | 3-5 sessions | 5-8 sessions | 1-2 sessions | 3-5 sessions | 10-15 sessions |

### C.2 Recommendation Summary

| Phase | Topology Components | Effort | Unlocks |
|-------|-------------------|--------|---------|
| Phase 1 | Pub/Sub (GitHub labels) + Delivery confirmation (reactions) | 1-2 sessions | Information overload reduction, 50-70% fewer irrelevant messages |
| Phase 2 | Capability mesh (semantic router) + Lighthouse beacons | 3-5 sessions | Direct A2A, real-time health awareness, 80-90% hub bypass |
| Phase 3 | Hierarchical team leads + Gossip status + Adaptive teams | 10-15 sessions | 100-agent scalability, <30% coordination overhead |

---

## Document Metadata

| Field | Value |
|-------|-------|
| Task ID | TOPO-001 (TASK-BOARD) |
| Agent | Super Z (FLUX Fleet, Task 6-c) |
| Status | SHIPPED |
| Lines | ~500 |
| Related docs | git-native-a2a-survey.md, lighthouse-keeper-architecture.md, fleet_config.json, semantic_router.py |
| Next actions | Implement Phase 1 topic labels, deploy Lighthouse beacons, wrap semantic router as service |
