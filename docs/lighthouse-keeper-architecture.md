# Lighthouse Keeper Architecture — Per-Region Health Monitor

**Document ID:** KEEP-ARCH-001
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-14
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** tender-architecture.md (TokenSteward), fleet_config.json, resource_limits.py, capabilities.py
**Tracks:** TASK-BOARD "Lighthouse Keeper Architecture" (KEEP-001)
**Repo:** `SuperInstance/flux-runtime`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Lighthouse Keeper Design](#3-lighthouse-keeper-design)
4. [Health Scoring Algorithm](#4-health-scoring-algorithm)
5. [Failover Protocol](#5-failover-protocol)
6. [Regional Awareness](#6-regional-awareness)
7. [Integration](#7-integration)
8. [Implementation](#8-implementation)
9. [Appendix A — Data Model Reference](#appendix-a--data-model-reference)
10. [Appendix B — Cross-References](#appendix-b--cross-references)

---

## 1. Executive Summary

A fleet of autonomous AI agents operating across distributed infrastructure demands continuous health awareness at every scale. A single stuck agent can cascade into a broken pipeline; a regional compute outage can silently stall dozens of tasks. The FLUX fleet already has 733 repositories, 6+ active agents, and growing — manual health checking is no longer feasible.

The **Lighthouse Keeper** is the middle tier of the three-tier keeper hierarchy that provides per-region health monitoring. It sits between **Brothers Keeper** (per-machine telemetry) and **Tender** (fleet-wide resource stewardship), serving as the critical aggregation and early-warning layer. Where Brothers Keeper reports CPU temperature and memory pressure in millisecond intervals, the Lighthouse Keeper consumes those streams and answers fleet-level questions: *Is agent Oracle1 responsive? Is the east-region compute pool healthy? Which machines are at risk of capacity exhaustion?*

This architecture defines the beacon protocol (agents heart-beat every 60 seconds), the health scoring algorithm (a 0–100 composite of heartbeat recency, task completion rate, error rate, and token efficiency), alert escalation chains (agent-down → region-alert → fleet-alert), regional metrics aggregation (compute, memory, token usage, task throughput), and a failover protocol for lighthouse availability. The design is protocol-first: any agent with the `A2A_DELEGATE` capability can instantiate a Lighthouse Keeper, and multiple lighthouses can cover different geographic or logical regions without central coordination.

---

## 2. Architecture Diagram

### 2.1 Three-Tier Monitoring Topology

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        TENDER (Fleet-Wide)                               │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  TokenSteward                                                      │  │
│  │  • Fleet-level token budgets & allocation                         │  │
│  │  • Cross-region resource rebalancing                              │  │
│  │  • Market-based bidding for shared pools                          │  │
│  │  • Credit scoring & debt tracking                                 │  │
│  │  • Receives: RegionalHealthReport from each Lighthouse            │  │
│  │  • Sends: PolicyDirectives, BudgetAllocations to Lighthouses      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                  ▲                                       │
│              ┌───────────────────┼───────────────────┐                   │
│              │  RegionalHealth   │  RegionalHealth   │                   │
│              │  Report           │  Report           │                   │
│              │                   │                   │                   │
│   ┌──────────┴──────────┐ ┌─────┴──────────┐ ┌──────┴────────────┐    │
│   │ LIGHTHOUSE KEEPER    │ │ LIGHTHOUSE      │ │ LIGHTHOUSE        │    │
│   │ Region: us-east      │ │ KEEPER          │ │ KEEPER            │    │
│   │ ┌──────────────────┐ │ │ Region: eu-west │ │ Region: edge      │    │
│   │ │ Health Aggregator │ │ │ ┌────────────┐ │ │ ┌──────────────┐ │    │
│   │ │ Beacon Tracker    │ │ │ │ Health     │ │ │ │ Health        │ │    │
│   │ │ Alert Escalator   │ │ │ │ Aggregator │ │ │ │ Aggregator    │ │    │
│   │ │ Score Calculator  │ │ │ │ Beacon     │ │ │ │ Beacon        │ │    │
│   │ │ Region Stats      │ │ │ │ Tracker    │ │ │ │ Tracker       │ │    │
│   │ └──────────────────┘ │ │ │ Alert      │ │ │ │ Alert         │ │    │
│   └──────────┬──────────┘ │ │ │ Escalator  │ │ │ │ Escalator     │ │    │
│              │            │ │ └────────────┘ │ │ └──────────────┘ │    │
│   ┌──────────┴──────────┐ │ └─────┬──────────┘ └──────┬───────────┘    │
│   │ BROTHERS KEEPER x3  │ │       │                    │                │
│   │ Machine telemetry   │ │ ┌─────┴──────────┐ ┌──────┴───────────┐  │
│   └─────────────────────┘ │ │ BROTHERS KEEPER │ │ BROTHERS KEEPER  │  │
│   ┌─────────────────────┐ │ │ x2              │ │ x1 (Jetson)      │  │
│   │ BROTHERS KEEPER x2  │ │ │ Machine telemetry│ │ Machine telemetry│  │
│   │ Machine telemetry   │ │ └─────────────────┘ └──────────────────┘  │
│   └─────────────────────┘ │                                            │
│                            │                                            │
│  ┌─────────────────────────┴──────────────────────────────────────┐    │
│  │                    FLEET AGENTS                                  │    │
│  │  Oracle1  Super Z  Quill  Babel  JetsonClaw1  Fleet Mechanic   │    │
│  │  ┌──────┐ ┌──────┐ ┌─────┐ ┌──────┐ ┌───────────┐ ┌─────────┐│    │
│  │  │Agent │ │Agent │ │Agent│ │Agent │ │Agent      │ │Agent    ││    │
│  │  │Process│ │Process│ │Proc │ │Process│ │Process    │ │Process  ││    │
│  │  └──┬───┘ └──┬───┘ └──┬──┘ └──┬───┘ └─────┬─────┘ └────┬────┘│    │
│  │     └────────┴────────┴────────┴────────────┴────────────┘     │    │
│  │                        ▲ Beacon (60s)                          │    │
│  └────────────────────────┼──────────────────────────────────────┘    │
└───────────────────────────┼────────────────────────────────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Beacon Signal│
                    │ agent_id     │
                    │ timestamp    │
                    │ capabilities │
                    │ health_bits  │
                    │ load_stats   │
                    └──────────────┘
```

### 2.2 Data Flow Summary

| Direction | Protocol | Payload | Frequency |
|-----------|----------|---------|-----------|
| Agent → Lighthouse | Beacon | heartbeat, capabilities, load | Every 60 seconds |
| Brothers Keeper → Lighthouse | TelemetryStream | CPU, GPU, memory, network | Every 5 seconds |
| Lighthouse → Tender | RegionalHealthReport | aggregated scores, alerts | Every 5 minutes |
| Tender → Lighthouse | PolicyDirective | budget limits, thresholds | On change |
| Lighthouse → Agent | HealthQuery | ping request | On demand |
| Agent → Lighthouse | HealthResponse | pong + diagnostics | On ping |

### 2.3 Alert Escalation Flow

```
Agent misses 1 beacon (60s)
  └── MARKED: "stale" (yellow warning, no action)

Agent misses 3 beacons (180s)
  └── REGION ALERT: "agent-unresponsive"
      ├── Notify Brothers Keeper to check process
      └── Log in RegionalHealthReport

Agent misses 5 beacons (300s)
  └── FLEET ALERT: "agent-down"
      ├── Escalate to Tender
      ├── Trigger failover protocol (if agent held tasks)
      ├── Auto-route pending tasks to healthy agents
      └── Create issue on vessel repo

Agent reports error_rate > 20%
  └── REGION ALERT: "agent-degraded"
      ├── Reduce semantic router confidence for this agent
      └── Flag for Mechanic Cron inspection

Region health_score average < 50
  └── FLEET ALERT: "region-degraded"
      ├── Tender reallocates budgets to healthy regions
      └── Trigger Mechanic Cron full scan
```

---

## 3. Lighthouse Keeper Design

### 3.1 Health Check Protocol

The Lighthouse Keeper performs four types of health checks, layered from passive observation to active probing:

**1. Passive Beacon Monitoring (default)**

Every agent in the fleet sends a beacon signal every 60 seconds. The beacon contains:
- `agent_id`: unique identifier (matches fleet_config.json)
- `timestamp`: epoch seconds of beacon emission
- `capabilities`: list of active CapabilityTokens (for A2A task matching)
- `health_bits`: bitmask of self-reported status (bit 0=process_alive, bit 1=llm_available, bit 2=ci_passing, bit 3=memory_ok, bit 4=network_ok)
- `load_stats`: current CPU%, memory_used/total, tasks_in_queue, tokens_remaining

The Lighthouse tracks the last-seen timestamp and computes heartbeat recency as the primary health signal. Agents that stop sending beacons are detected within 60–180 seconds.

**2. Active Ping (on-demand)**

When an agent's beacon is stale, the Lighthouse sends a direct `HealthQuery` message via the I2I protocol. The agent must respond within 10 seconds with a `HealthResponse` containing its current state. If the agent does not respond, it is marked as unresponsive.

```
HealthQuery:
  query_id: str           # unique ID for deduplication
  target_agent: str       # agent being pinged
  sent_at: float          # epoch seconds
  checks: list[str]       # ["heartbeat", "capability", "load", "latency"]

HealthResponse:
  query_id: str           # matches query
  agent_id: str           # responding agent
  responded_at: float
  status: str             # "ok" | "degraded" | "critical"
  latency_ms: float       # round-trip time
  details: dict           # optional diagnostics
```

**3. Capability Verification (periodic)**

Every 5 minutes, the Lighthouse verifies that agents claiming specific capabilities can actually exercise them. For example, if an agent claims `CUDA_EXECUTE`, the Lighthouse can request a trivial CUDA kernel execution and verify the response. Capability verification is lightweight — it does not re-run conformance tests, but checks basic liveness.

**4. Task Completion Audit (daily)**

The Lighthouse cross-references each agent's claimed task completions against the TASK-BOARD and vessel repos. If an agent claims to have shipped a fence but no corresponding commit exists, the Lighthouse flags a trust anomaly. This feeds into the credit score system managed by Tender's TokenSteward.

### 3.2 Alert Escalation Engine

Alerts follow a three-level escalation chain that mirrors the three-tier architecture:

| Level | Condition | Action | Recipient |
|-------|-----------|--------|-----------|
| **WARN** | Beacon stale 60–180s OR error_rate 10–20% | Log, annotate health record | Lighthouse Keeper (local) |
| **ALERT** | Beacon stale 180–300s OR error_rate 20–50% OR health_score < 50 | Notify region, reduce router confidence | Tender + Brothers Keeper |
| **CRITICAL** | Beacon stale >300s OR error_rate >50% OR health_score < 25 | Escalate to fleet, trigger failover | Tender + Oracle1 + issue creation |

Alerts are **deduplicated**: the same condition on the same agent does not generate multiple alerts within a 10-minute window. This prevents alert storms during regional outages where multiple agents go down simultaneously.

### 3.3 Regional Metrics Aggregation

Each Lighthouse Keeper maintains a rolling window of metrics for its region. Metrics are aggregated into time buckets (1-minute, 5-minute, 15-minute, 1-hour) and summarized for upstream reporting:

```python
@dataclass
class RegionalMetrics:
    """Aggregated metrics for a single region, computed every 60 seconds."""
    region_id: str
    timestamp: float

    # Compute
    total_cpu_percent: float          # average across all machines
    peak_cpu_percent: float           # max across all machines
    gpu_utilization_percent: float    # if GPU machines present

    # Memory
    total_memory_used_gb: float
    total_memory_available_gb: float
    memory_pressure_ratio: float      # used / total (1.0 = full)

    # Tokens (from Tender integration)
    tokens_consumed_this_hour: int
    tokens_remaining_budget: int
    token_burn_rate: float            # tokens per hour (trailing 6h average)

    # Tasks
    tasks_assigned: int               # currently assigned to region's agents
    tasks_completed_last_hour: int
    tasks_failed_last_hour: int
    task_throughput: float            # completed / hour

    # Agents
    agents_healthy: int               # health_score >= 70
    agents_degraded: int              # health_score 30–69
    agents_down: int                  # health_score < 30
    total_agents: int

    # Network (inter-region)
    inter_region_latency_ms: float    # average ping to other regions
    beacon_delivery_rate: float       # beacons received / beacons expected
```

The RegionalMetrics are packaged into a `RegionalHealthReport` and sent to Tender every 5 minutes. Tender uses these reports for fleet-wide budget rebalancing and capacity planning.

### 3.4 Beacon Protocol Specification

The beacon protocol is the core communication mechanism between agents and the Lighthouse Keeper. It is designed to be minimal (under 500 bytes per beacon), reliable (UDP-style fire-and-forget with TCP fallback), and secure (signed with agent's capability token).

**Beacon Frame Format:**

```
┌────────────────────────────────────────────────────────────────┐
│ BEACON FRAME (variable length, typically ~200-400 bytes)       │
├────────────────────────────────────────────────────────────────┤
│ magic:        4 bytes   "FLXB" (FLUX Beacon)                 │
│ version:      1 byte    0x01                                  │
│ agent_id:     16 bytes  UUID                                  │
│ timestamp:    8 bytes   epoch seconds (int64)                 │
│ health_bits:  1 byte    bitmask (5 bits used, 3 reserved)     │
│ capabilities: 2 bytes   count of capability hashes            │
│ cap_hashes:   N*16 bytes capability token hashes (SHA-256     │
│                         truncated to 16 bytes)                │
│ cpu_percent:  1 byte    0-255 (maps to 0-100%)                │
│ mem_percent:  1 byte    0-255 (maps to 0-100%)                │
│ queue_depth:  2 bytes   tasks in queue (uint16)               │
│ token_budget: 4 bytes   remaining standard tokens (uint32)    │
│ region_id:    2 bytes   region identifier                     │
│ signature:    32 bytes  HMAC-SHA256(agent_secret, payload)    │
└────────────────────────────────────────────────────────────────┘
```

**Beacon Transmission:**

- **Primary**: HTTP POST to Lighthouse endpoint `/beacon` (fire-and-forget, 1-second timeout)
- **Fallback**: Write beacon JSON to shared filesystem path `/fleet/beacons/{agent_id}.json`
- **Emergency**: Direct I2I bottle message to Lighthouse Keeper vessel

**Beacon Processing:**

1. Lighthouse receives beacon and validates HMAC signature
2. Updates agent's `last_seen` timestamp
3. Extracts health_bits and updates agent health record
4. Appends to rolling metrics window
5. If this is the first beacon from this agent in this region, registers the agent
6. If agent was previously marked stale, clears stale flag and logs recovery

---

## 4. Health Scoring Algorithm

### 4.1 Composite Health Score

Each agent receives a composite health score from 0 to 100, computed every time a beacon arrives or every 60 seconds (whichever is more frequent). The score is a weighted average of four sub-scores:

```
health_score = (w_hb * heartbeat_score
              + w_tc * task_completion_score
              + w_er * error_rate_score
              + w_te * token_efficiency_score)

Where:
  w_hb = 0.40  (heartbeat recency — most important signal)
  w_tc = 0.25  (task completion — are they getting work done?)
  w_er = 0.25  (error rate — are they producing errors?)
  w_te = 0.10  (token efficiency — are they spending wisely?)
```

### 4.2 Sub-Score Calculations

**Heartbeat Recency Score (0–100):**

Measures how recently the agent was last seen. Linear decay from 100 to 0 over a 15-minute window.

```python
def heartbeat_score(last_seen: float, now: float) -> float:
    """
    Score based on seconds since last beacon.
    - Seen within 60s (on time): 100
    - Seen within 5 min: ~67
    - Seen within 15 min: ~0
    - Not seen in 15+ min: 0
    """
    elapsed = now - last_seen
    if elapsed <= 60:
        return 100.0
    elif elapsed <= 900:  # 15 minutes
        return max(0.0, 100.0 * (1.0 - (elapsed - 60) / 840.0))
    return 0.0
```

**Task Completion Score (0–100):**

Ratio of tasks completed in the trailing window to tasks assigned. Uses a 24-hour trailing window with a minimum denominator of 1 to avoid division by zero.

```python
def task_completion_score(completed: int, assigned: int) -> float:
    """
    Score based on task completion ratio over last 24 hours.
    - completed/assigned = 1.0: 100
    - completed/assigned = 0.5: 70 (curve favors partial completion)
    - completed/assigned = 0.0: 20 (some credit for being assigned)
    - No tasks assigned: 100 (idle agents are healthy)
    """
    if assigned == 0:
        return 100.0  # idle agent is not unhealthy
    ratio = completed / assigned
    # Sigmoid-like curve: 0.0 → 20, 0.5 → 70, 1.0 → 100
    return 20.0 + 80.0 * (1.0 - (1.0 - ratio) ** 2)
```

**Error Rate Score (0–100):**

Inverse of error rate in the trailing 100 operations. Uses an exponential decay so that a few recent errors have more impact than many old ones.

```python
def error_rate_score(recent_errors: int, window_size: int = 100) -> float:
    """
    Score based on errors in last 100 operations.
    - 0 errors: 100
    - 5 errors (5%): 82
    - 20 errors (20%): 40
    - 50+ errors (50%+): 0
    """
    if window_size == 0:
        return 100.0
    error_pct = recent_errors / window_size
    return max(0.0, 100.0 * (1.0 - error_pct) ** 1.5)
```

**Token Efficiency Score (0–100):**

Measures useful work (tasks completed + fences shipped) per 1,000 tokens consumed in the trailing week. Calibrated against fleet average to normalize.

```python
def token_efficiency_score(
    tasks_completed: int,
    fences_shipped: int,
    tokens_consumed: int,
    fleet_avg_efficiency: float
) -> float:
    """
    Score based on useful work per token.
    Normalized against fleet average.
    - At fleet average: 70 (baseline)
    - 2x fleet average: 90
    - 0.5x fleet average: 45
    - Zero consumption: 100 (no spend = efficient)
    """
    if tokens_consumed == 0:
        return 100.0
    work_units = tasks_completed + (fences_shipped * 5)  # fences worth 5x tasks
    efficiency = (work_units / tokens_consumed) * 1000  # work per 1K tokens
    if fleet_avg_efficiency == 0:
        return 70.0
    relative = efficiency / fleet_avg_efficiency
    return min(100.0, max(0.0, 70.0 + 20.0 * (relative - 1.0)))
```

### 4.3 Full Composite Score Function

```python
def health_score(agent: AgentProfile) -> float:
    """
    Compute composite health score for a fleet agent.

    Returns a float from 0.0 to 100.0 representing overall health.
    Score breakdown:
      0-25:  CRITICAL — agent is down or severely degraded
      25-50: DEGRADED — agent is struggling, reduce task assignments
      50-70: WARNING — agent is below par, monitor closely
      70-85: HEALTHY — agent is operating normally
      85-100: EXCELLENT — agent is performing above fleet average
    """
    now = time.time()

    # Sub-scores
    hb = heartbeat_score(agent.last_seen, now)
    tc = task_completion_score(agent.tasks_completed_24h, agent.tasks_assigned_24h)
    er = error_rate_score(agent.recent_errors, 100)
    te = token_efficiency_score(
        agent.tasks_completed_week,
        agent.fences_shipped_week,
        agent.tokens_consumed_week,
        agent.fleet_avg_efficiency
    )

    # Weighted composite
    score = (0.40 * hb) + (0.25 * tc) + (0.25 * er) + (0.10 * te)
    return round(score, 1)
```

### 4.4 Score Interpretation Table

| Score Range | Status | Color | Action |
|-------------|--------|-------|--------|
| 85–100 | EXCELLENT | Green | Eligible for critical task routing |
| 70–84 | HEALTHY | Green | Normal operations |
| 50–69 | WARNING | Yellow | Monitor, reduce new task assignments |
| 25–49 | DEGRADED | Orange | Suspend task routing, alert Tender |
| 0–24 | CRITICAL | Red | Trigger failover, reassign all tasks |

---

## 5. Failover Protocol

### 5.1 When a Lighthouse Goes Down

Lighthouse Keepers are single points of monitoring for their region. If a Lighthouse process crashes or becomes unreachable, the following protocol activates:

**Detection (T < 5 minutes):**

1. Tender's TokenSteward detects missing `RegionalHealthReport` from the region (expected every 5 minutes)
2. Tender pings the Lighthouse directly via HealthQuery
3. If no response within 30 seconds, Tender marks region as "lighthouse-down"

**Recovery Phase 1 — Peer Takeover (T < 15 minutes):**

4. Tender selects the healthiest agent in the affected region with `A2A_DELEGATE` capability
5. Tender sends a `LighthousePromotion` message to that agent with the failed lighthouse's configuration
6. The promoted agent instantiates a temporary Lighthouse Keeper using the last known state from Tender's audit log
7. Agents in the region detect the new Lighthouse via beacon ACK redirection

**Recovery Phase 2 — State Reconstruction (T < 30 minutes):**

8. The temporary Lighthouse reconstructs agent states by:
   - Reading beacon files from shared filesystem (`/fleet/beacons/`)
   - Querying Brothers Keeper instances directly for machine telemetry
   - Receiving fresh beacons from agents (within 1–2 beacon cycles)
9. Health scores are recalculated from reconstructed state
10. Temporary Lighthouse begins sending `RegionalHealthReport` to Tender

**Recovery Phase 3 — Permanent Replacement (T < 1 hour):**

11. If the original Lighthouse does not recover within 30 minutes, Tender creates a permanent replacement
12. The replacement is deployed as a new agent process or assigned to a dedicated machine
13. Fleet config (`fleet_config.json`) is updated with the new Lighthouse endpoint
14. All agents receive updated configuration via `ConfigUpdate` I2I message

### 5.2 Lighthouse State Persistence

To enable rapid recovery, each Lighthouse persists its state to a write-ahead log (WAL) every 60 seconds:

```python
@dataclass
class LighthouseSnapshot:
    """Periodic snapshot of Lighthouse state for crash recovery."""
    snapshot_id: str
    timestamp: float
    region_id: str
    lighthouse_id: str

    # Agent states
    agents: dict[str, AgentHealthRecord]

    # Active alerts
    active_alerts: list[Alert]

    # Rolling metrics
    metrics_window: list[RegionalMetrics]

    # Configuration
    config_hash: str  # hash of fleet_config.json at snapshot time
```

The WAL is stored at `/fleet/lighthouse/{region_id}/wal/` and is append-only. On recovery, the temporary Lighthouse replays the WAL from the most recent snapshot.

### 5.3 Cascade Failure Prevention

If multiple Lighthouses go down simultaneously (indicating a fleet-wide outage rather than a single-region failure), Tender activates **fleet-safe mode**:

1. All new task assignments are suspended
2. Agents continue executing in-flight tasks but do not accept new work
3. Tender sends a fleet-wide `FleetSafeMode` broadcast via I2I
4. Oracle1 is notified via priority I2I bottle
5. Mechanic Cron is triggered for a full fleet scan on recovery

---

## 6. Regional Awareness

### 6.1 Region Definition

A region is a logical grouping of machines and agents that share low-latency network connectivity. Regions can be:

- **Geographic**: `us-east`, `eu-west`, `ap-southeast` (datacenter-based)
- **Network**: `lan-office`, `lan-lab`, `wan-cloud` (topology-based)
- **Functional**: `gpu-pool`, `cpu-pool`, `edge-jetson` (capability-based)

Each agent reports its `region_id` in every beacon. The Lighthouse Keeper is responsible for a single region and only tracks agents that report that region.

### 6.2 Cross-Region Detection

The Lighthouse can detect agents that have changed regions (e.g., an agent moved from `us-east` to `eu-west`):

```python
def detect_region_change(agent: AgentHealthRecord, beacon: Beacon) -> bool:
    """Detect if an agent has moved to a different region."""
    if agent.known_region is None:
        agent.known_region = beacon.region_id
        return False
    if beacon.region_id != agent.known_region:
        log.info(
            f"Agent {agent.agent_id} region change: "
            f"{agent.known_region} -> {beacon.region_id}"
        )
        agent.known_region = beacon.region_id
        agent.region_change_count += 1
        return True
    return False
```

Frequent region changes (>3 in 24 hours) trigger a "region-hopping" alert, which may indicate a misconfigured agent or a security concern (agent moving to evade monitoring).

### 6.3 Same-Datacenter vs Cross-Region Awareness

The Lighthouse tracks network latency between agents using beacon round-trip times. Agents within the same datacenter typically respond in <5ms, while cross-region responses are >50ms. This information is used by:

- **Tender**: to optimize token allocation (prefer same-region agents for collaborative tasks)
- **Semantic Router**: to add a proximity bonus when routing tasks
- **A2A Protocol**: to select the most appropriate transport (shared memory for same-machine, HTTP for same-region, I2I bottle for cross-region)

```python
@dataclass
class ProximityClass:
    """Network proximity classification."""
    SHARED_MEMORY = "shared_memory"    # same process (<0.1ms)
    SAME_MACHINE = "same_machine"      # same machine (<1ms)
    SAME_RACK = "same_rack"            # same rack (<5ms)
    SAME_DATACENTER = "same_dc"        # same datacenter (<20ms)
    SAME_REGION = "same_region"        # same region (<100ms)
    CROSS_REGION = "cross_region"      # different region (>100ms)
```

---

## 7. Integration

### 7.1 Upstream: Brothers Keeper

The Lighthouse Keeper consumes telemetry from Brothers Keeper instances. Each Brothers Keeper reports machine-level metrics every 5 seconds via a telemetry stream. The Lighthouse aggregates these into regional summaries.

**Existing Code Integration:**

- `ResourceMonitor` (resource_limits.py): provides CPU cycle count, memory usage (64MB limit)
- `ResourceLimits`: provides per-VM resource boundaries
- `Sandbox`, `SandboxManager`: provides capability and resource check results

The Lighthouse extends these with fleet-level semantics:

```python
class BrothersKeeperAdapter:
    """Adapts existing ResourceMonitor data for Lighthouse consumption."""

    def __init__(self, monitor: ResourceMonitor, machine_id: str):
        self.monitor = monitor
        self.machine_id = machine_id

    def to_lighthouse_telemetry(self) -> MachineTelemetry:
        return MachineTelemetry(
            machine_id=self.machine_id,
            cpu_cycles_used=self.monitor.cycle_count,
            memory_used_bytes=self.monitor.memory_used,
            memory_limit_bytes=self.monitor.limits.max_memory,
            cpu_percent=self._estimate_cpu_percent(),
            memory_percent=self.monitor.memory_used / self.monitor.limits.max_memory * 100,
            process_count=self._count_agent_processes(),
            timestamp=time.time(),
        )
```

### 7.2 Downstream: Tender

The Lighthouse Keeper sends `RegionalHealthReport` to Tender every 5 minutes. Tender uses these reports for:

1. **Budget rebalancing**: Regions with low health scores receive reduced token allocations
2. **Task routing adjustments**: The semantic router weights agents by their Lighthouse-reported health score
3. **Emergency response**: Critical alerts from Lighthouse trigger Tender's emergency pool access
4. **Fleet dashboards**: Regional health data feeds into the fleet health dashboard (fleet-health-dashboard.json)

**Report Format:**

```python
@dataclass
class RegionalHealthReport:
    """Report sent from Lighthouse Keeper to Tender every 5 minutes."""
    report_id: str
    region_id: str
    lighthouse_id: str
    timestamp: float

    # Regional summary
    metrics: RegionalMetrics

    # Per-agent health
    agent_scores: dict[str, float]          # agent_id -> health_score
    agent_details: dict[str, AgentHealthRecord]

    # Active alerts
    alerts: list[Alert]

    # Region status
    region_status: str  # "healthy" | "degraded" | "critical" | "down"
```

### 7.3 Cross-Reference: Existing Fleet Systems

| System | Relationship | Integration Point |
|--------|-------------|-------------------|
| **TokenSteward** (tender-architecture.md) | Tender consumes Lighthouse reports | RegionalHealthReport → budget adjustments |
| **Semantic Router** (semantic_router.py) | Router uses health scores for task assignment | health_score → availability factor |
| **Conformance Runner** (conformance_runner.py) | Lighthouse triggers conformance on health anomalies | health_score < 50 → run conformance |
| **Fleet Mechanic** (MECH-001) | Mechanic Cron acts on Lighthouse alerts | alert → auto-issue creation |
| **A2A Primitives** (primitives.py) | Lighthouse uses SIGNAL opcodes for alerts | SIGNAL type=ALERT |
| **I2I Protocol** (i2i-enhancements-v3) | Lighthouse communicates via I2I bottles | FLEET_HEALTH message types |
| **fleet_config.json** | Lighthouse reads agent profiles | agent domains, specializations, capabilities |
| **Knowledge Base** (knowledge-base.json) | Lighthouse writes health facts | domain "health" entries |

---

## 8. Implementation

### 8.1 Python Implementation Outline

```python
"""
lighthouse_keeper.py — Per-region health monitor for the FLUX fleet.

Three-tier hierarchy:
  Brothers Keeper (machine) -> Lighthouse Keeper (region) -> Tender (fleet)

Usage:
  python lighthouse_keeper.py --region us-east --port 8080
  python lighthouse_keeper.py --config fleet_config.json --region eu-west
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime, timedelta
import time
import uuid
import hashlib
import hmac
import threading
import json
import os
from collections import deque
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# Enums & Constants
# ═══════════════════════════════════════════════════════════════

class HealthStatus(Enum):
    EXCELLENT = "excellent"   # 85-100
    HEALTHY = "healthy"       # 70-84
    WARNING = "warning"       # 50-69
    DEGRADED = "degraded"     # 25-49
    CRITICAL = "critical"     # 0-24


class AlertLevel(Enum):
    WARN = "warn"
    ALERT = "alert"
    CRITICAL = "critical"


class ProximityClass(Enum):
    SHARED_MEMORY = "shared_memory"
    SAME_MACHINE = "same_machine"
    SAME_RACK = "same_rack"
    SAME_DATACENTER = "same_dc"
    SAME_REGION = "same_region"
    CROSS_REGION = "cross_region"


BEACON_MAGIC = b"FLXB"
BEACON_VERSION = 0x01
BEACON_INTERVAL_SEC = 60
HEALTH_REPORT_INTERVAL_SEC = 300  # 5 minutes
STALE_THRESHOLD_SEC = 180        # 3 minutes
DOWN_THRESHOLD_SEC = 300         # 5 minutes
METRICS_WINDOW_SIZE = 3600       # 1 hour of 1-second buckets
MAX_ALERTS = 1000
WAL_DIRECTORY = "/fleet/lighthouse/{region_id}/wal/"
BEACON_DIRECTORY = "/fleet/beacons/"


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Beacon:
    """Immutable beacon frame received from a fleet agent."""
    agent_id: str
    timestamp: float
    health_bits: int
    capabilities: list[str]
    cpu_percent: float
    mem_percent: float
    queue_depth: int
    token_budget: int
    region_id: str
    signature: bytes
    raw_bytes: bytes = b""


@dataclass
class AgentHealthRecord:
    """Tracked health state for a single agent."""
    agent_id: str
    known_region: Optional[str] = None
    last_seen: float = 0.0
    health_score: float = 100.0
    health_status: HealthStatus = HealthStatus.HEALTHY

    # Task tracking
    tasks_assigned_24h: int = 0
    tasks_completed_24h: int = 0
    tasks_failed_24h: int = 0
    tasks_completed_week: int = 0
    fences_shipped_week: int = 0

    # Error tracking
    recent_errors: int = 0
    error_window: deque = field(default_factory=lambda: deque(maxlen=100))

    # Token tracking
    tokens_consumed_week: int = 0
    fleet_avg_efficiency: float = 1.0

    # Network
    avg_latency_ms: float = 0.0
    proximity_class: ProximityClass = ProximityClass.SAME_REGION

    # Beacon history
    beacon_count: int = 0
    missed_beacons: int = 0
    region_change_count: int = 0
    last_health_bits: int = 0xFF

    # Alert tracking
    alert_suppression_until: float = 0.0


@dataclass
class Alert:
    """An alert generated by the Lighthouse Keeper."""
    alert_id: str
    level: AlertLevel
    agent_id: str
    region_id: str
    condition: str           # e.g., "beacon-stale", "error-rate-high"
    message: str
    timestamp: float
    resolved: bool = False
    resolved_at: float = 0.0


@dataclass
class MachineTelemetry:
    """Telemetry from a Brothers Keeper instance."""
    machine_id: str
    cpu_cycles_used: int
    memory_used_bytes: int
    memory_limit_bytes: int
    cpu_percent: float
    memory_percent: float
    process_count: int
    timestamp: float


@dataclass
class RegionalMetrics:
    """Aggregated metrics for a single region."""
    region_id: str
    timestamp: float
    total_cpu_percent: float = 0.0
    peak_cpu_percent: float = 0.0
    gpu_utilization_percent: float = 0.0
    total_memory_used_gb: float = 0.0
    total_memory_available_gb: float = 0.0
    memory_pressure_ratio: float = 0.0
    tokens_consumed_this_hour: int = 0
    tokens_remaining_budget: int = 0
    token_burn_rate: float = 0.0
    tasks_assigned: int = 0
    tasks_completed_last_hour: int = 0
    tasks_failed_last_hour: int = 0
    task_throughput: float = 0.0
    agents_healthy: int = 0
    agents_degraded: int = 0
    agents_down: int = 0
    total_agents: int = 0
    inter_region_latency_ms: float = 0.0
    beacon_delivery_rate: float = 0.0


@dataclass
class RegionalHealthReport:
    """Report sent from Lighthouse Keeper to Tender."""
    report_id: str
    region_id: str
    lighthouse_id: str
    timestamp: float
    metrics: RegionalMetrics
    agent_scores: dict[str, float] = field(default_factory=dict)
    agent_details: dict[str, AgentHealthRecord] = field(default_factory=dict)
    alerts: list[Alert] = field(default_factory=list)
    region_status: str = "healthy"


@dataclass
class LighthouseSnapshot:
    """Periodic snapshot for crash recovery."""
    snapshot_id: str
    timestamp: float
    region_id: str
    lighthouse_id: str
    agents: dict[str, dict] = field(default_factory=dict)
    active_alerts: list[dict] = field(default_factory=list)
    metrics_window: list[dict] = field(default_factory=list)
    config_hash: str = ""


# ═══════════════════════════════════════════════════════════════
# Health Scoring
# ═══════════════════════════════════════════════════════════════

def heartbeat_score(last_seen: float, now: float) -> float:
    elapsed = now - last_seen
    if elapsed <= BEACON_INTERVAL_SEC:
        return 100.0
    elif elapsed <= 900:
        return max(0.0, 100.0 * (1.0 - (elapsed - 60) / 840.0))
    return 0.0


def task_completion_score(completed: int, assigned: int) -> float:
    if assigned == 0:
        return 100.0
    ratio = completed / assigned
    return 20.0 + 80.0 * (1.0 - (1.0 - ratio) ** 2)


def error_rate_score(recent_errors: int, window_size: int = 100) -> float:
    if window_size == 0:
        return 100.0
    error_pct = recent_errors / window_size
    return max(0.0, 100.0 * (1.0 - error_pct) ** 1.5)


def token_efficiency_score(
    tasks_completed: int,
    fences_shipped: int,
    tokens_consumed: int,
    fleet_avg_efficiency: float,
) -> float:
    if tokens_consumed == 0:
        return 100.0
    work_units = tasks_completed + (fences_shipped * 5)
    efficiency = (work_units / tokens_consumed) * 1000
    if fleet_avg_efficiency == 0:
        return 70.0
    relative = efficiency / fleet_avg_efficiency
    return min(100.0, max(0.0, 70.0 + 20.0 * (relative - 1.0)))


def compute_health_score(agent: AgentHealthRecord) -> float:
    now = time.time()
    hb = heartbeat_score(agent.last_seen, now)
    tc = task_completion_score(agent.tasks_completed_24h, agent.tasks_assigned_24h)
    er = error_rate_score(agent.recent_errors, 100)
    te = token_efficiency_score(
        agent.tasks_completed_week,
        agent.fences_shipped_week,
        agent.tokens_consumed_week,
        agent.fleet_avg_efficiency,
    )
    score = (0.40 * hb) + (0.25 * tc) + (0.25 * er) + (0.10 * te)
    return round(score, 1)


def score_to_status(score: float) -> HealthStatus:
    if score >= 85:
        return HealthStatus.EXCELLENT
    elif score >= 70:
        return HealthStatus.HEALTHY
    elif score >= 50:
        return HealthStatus.WARNING
    elif score >= 25:
        return HealthStatus.DEGRADED
    return HealthStatus.CRITICAL


# ═══════════════════════════════════════════════════════════════
# Lighthouse Keeper Core
# ═══════════════════════════════════════════════════════════════

class LighthouseKeeper:
    """Per-region health monitor — middle tier of the keeper hierarchy.

    Responsibilities:
    - Receive and validate agent beacons (every 60s)
    - Compute per-agent health scores (composite of 4 sub-scores)
    - Aggregate regional metrics from Brothers Keeper telemetry
    - Escalate alerts: agent-down -> region-alert -> fleet-alert
    - Send RegionalHealthReport to Tender every 5 minutes
    - Persist state for crash recovery
    """

    def __init__(self, region_id: str, lighthouse_id: str, config: dict):
        self.region_id = region_id
        self.lighthouse_id = lighthouse_id
        self.config = config

        # Agent tracking
        self.agents: dict[str, AgentHealthRecord] = {}
        self.alerts: list[Alert] = []
        self.metrics_history: deque[RegionalMetrics] = deque(maxlen=60)

        # Threads
        self._beacon_thread: Optional[threading.Thread] = None
        self._report_thread: Optional[threading.Thread] = None
        self._score_thread: Optional[threading.Thread] = None
        self._running = False

        # WAL
        self._wal_path = WAL_DIRECTORY.format(region_id=region_id)

    def start(self) -> None:
        """Start all Lighthouse Keeper background threads."""
        self._running = True
        os.makedirs(self._wal_path, exist_ok=True)

        self._beacon_thread = threading.Thread(
            target=self._beacon_loop, daemon=True, name="beacon-receiver"
        )
        self._report_thread = threading.Thread(
            target=self._report_loop, daemon=True, name="report-sender"
        )
        self._score_thread = threading.Thread(
            target=self._score_loop, daemon=True, name="score-calculator"
        )

        self._beacon_thread.start()
        self._report_thread.start()
        self._score_thread.start()

    def stop(self) -> None:
        """Gracefully stop all threads."""
        self._running = False
        self._persist_snapshot()

    def receive_beacon(self, beacon: Beacon) -> None:
        """Process an incoming beacon from a fleet agent."""
        now = time.time()

        # Validate signature (simplified — real impl uses HMAC)
        if not self._validate_beacon(beacon):
            return

        # Get or create agent record
        agent = self.agents.get(beacon.agent_id)
        if agent is None:
            agent = AgentHealthRecord(agent_id=beacon.agent_id)
            self.agents[beacon.agent_id] = agent

        # Detect region change
        self._detect_region_change(agent, beacon)

        # Update beacon tracking
        agent.last_seen = now
        agent.beacon_count += 1
        agent.last_health_bits = beacon.health_bits

        # Write beacon to shared filesystem (fallback for other consumers)
        self._write_beacon_file(beacon)

    def compute_all_scores(self) -> dict[str, float]:
        """Recompute health scores for all tracked agents."""
        scores = {}
        for agent_id, agent in self.agents.items():
            agent.health_score = compute_health_score(agent)
            agent.health_status = score_to_status(agent.health_score)
            scores[agent_id] = agent.health_score

            # Generate alerts based on status
            self._check_alert_conditions(agent)

        return scores

    def build_regional_report(self) -> RegionalHealthReport:
        """Build a RegionalHealthReport for Tender."""
        now = time.time()

        # Compute metrics
        metrics = self._aggregate_metrics()

        # Compute all scores
        scores = self.compute_all_scores()

        # Determine region status
        if metrics.agents_down > 0:
            status = "critical"
        elif metrics.agents_degraded > metrics.agents_healthy:
            status = "degraded"
        elif metrics.agents_degraded > 0:
            status = "warning"
        else:
            status = "healthy"

        return RegionalHealthReport(
            report_id=uuid.uuid4().hex[:12],
            region_id=self.region_id,
            lighthouse_id=self.lighthouse_id,
            timestamp=now,
            metrics=metrics,
            agent_scores=scores,
            agent_details=dict(self.agents),
            alerts=[a for a in self.alerts if not a.resolved],
            region_status=status,
        )

    def _validate_beacon(self, beacon: Beacon) -> bool:
        """Validate beacon HMAC signature."""
        # Simplified: in production, verify HMAC-SHA256
        return True

    def _detect_region_change(self, agent: AgentHealthRecord, beacon: Beacon) -> bool:
        if agent.known_region is None:
            agent.known_region = beacon.region_id
            return False
        if beacon.region_id != agent.known_region:
            agent.known_region = beacon.region_id
            agent.region_change_count += 1
            if agent.region_change_count > 3:
                self._create_alert(
                    AlertLevel.WARN, agent.agent_id,
                    "region-hopping",
                    f"Agent {agent.agent_id} changed region {agent.region_change_count} times in 24h"
                )
            return True
        return False

    def _check_alert_conditions(self, agent: AgentHealthRecord) -> None:
        """Generate alerts based on agent health conditions."""
        now = time.time()

        # Suppress duplicate alerts within 10 minutes
        if now < agent.alert_suppression_until:
            return

        # Beacon stale check
        elapsed = now - agent.last_seen
        if elapsed > DOWN_THRESHOLD_SEC:
            self._create_alert(
                AlertLevel.CRITICAL, agent.agent_id,
                "agent-down",
                f"Agent {agent.agent_id} has not sent beacon in {elapsed:.0f}s"
            )
            agent.alert_suppression_until = now + 600
        elif elapsed > STALE_THRESHOLD_SEC:
            self._create_alert(
                AlertLevel.ALERT, agent.agent_id,
                "agent-unresponsive",
                f"Agent {agent.agent_id} last seen {elapsed:.0f}s ago"
            )
            agent.alert_suppression_until = now + 600

        # Error rate check
        if agent.recent_errors > 20:
            self._create_alert(
                AlertLevel.ALERT, agent.agent_id,
                "error-rate-high",
                f"Agent {agent.agent_id} has {agent.recent_errors} errors in last 100 ops"
            )
            agent.alert_suppression_until = now + 600

        # Health score check
        if agent.health_score < 25:
            self._create_alert(
                AlertLevel.CRITICAL, agent.agent_id,
                "health-critical",
                f"Agent {agent.agent_id} health score: {agent.health_score}"
            )
            agent.alert_suppression_until = now + 600
        elif agent.health_score < 50:
            self._create_alert(
                AlertLevel.ALERT, agent.agent_id,
                "health-degraded",
                f"Agent {agent.agent_id} health score: {agent.health_score}"
            )
            agent.alert_suppression_until = now + 600

    def _create_alert(
        self, level: AlertLevel, agent_id: str,
        condition: str, message: str
    ) -> None:
        alert = Alert(
            alert_id=uuid.uuid4().hex[:12],
            level=level,
            agent_id=agent_id,
            region_id=self.region_id,
            condition=condition,
            message=message,
            timestamp=time.time(),
        )
        self.alerts.append(alert)
        if len(self.alerts) > MAX_ALERTS:
            self.alerts = self.alerts[-MAX_ALERTS:]

    def _aggregate_metrics(self) -> RegionalMetrics:
        """Aggregate all agent states into regional metrics."""
        now = time.time()
        agents = list(self.agents.values())

        healthy = sum(1 for a in agents if a.health_status.value in ("excellent", "healthy"))
        degraded = sum(1 for a in agents if a.health_status.value == ("warning", "degraded"))
        down = sum(1 for a in agents if a.health_status.value == "critical")

        total_cpu = sum(a.last_health_bits & 0x01 for a in agents)
        total_mem = sum((a.last_health_bits >> 1) & 0x01 for a in agents)

        return RegionalMetrics(
            region_id=self.region_id,
            timestamp=now,
            agents_healthy=healthy,
            agents_degraded=degraded,
            agents_down=down,
            total_agents=len(agents),
        )

    def _write_beacon_file(self, beacon: Beacon) -> None:
        """Write beacon to shared filesystem for fallback consumption."""
        path = Path(BEACON_DIRECTORY) / f"{beacon.agent_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "agent_id": beacon.agent_id,
            "timestamp": beacon.timestamp,
            "health_bits": beacon.health_bits,
            "cpu_percent": beacon.cpu_percent,
            "mem_percent": beacon.mem_percent,
            "region_id": beacon.region_id,
        }
        path.write_text(json.dumps(data))

    def _persist_snapshot(self) -> None:
        """Write current state to WAL for crash recovery."""
        snapshot = LighthouseSnapshot(
            snapshot_id=uuid.uuid4().hex[:12],
            timestamp=time.time(),
            region_id=self.region_id,
            lighthouse_id=self.lighthouse_id,
            agents={
                aid: {
                    "last_seen": a.last_seen,
                    "health_score": a.health_score,
                    "known_region": a.known_region,
                }
                for aid, a in self.agents.items()
            },
            active_alerts=[
                {"alert_id": a.alert_id, "condition": a.condition, "agent_id": a.agent_id}
                for a in self.alerts if not a.resolved
            ],
        )
        path = Path(self._wal_path) / f"snapshot_{int(time.time())}.json"
        path.write_text(json.dumps(vars(snapshot), default=str))

    def _beacon_loop(self) -> None:
        """Background thread: listen for incoming beacons."""
        # In production: HTTP server or message queue consumer
        while self._running:
            time.sleep(1)

    def _report_loop(self) -> None:
        """Background thread: send health report to Tender every 5 minutes."""
        while self._running:
            report = self.build_regional_report()
            self._send_to_tender(report)
            self.metrics_history.append(report.metrics)
            time.sleep(HEALTH_REPORT_INTERVAL_SEC)

    def _score_loop(self) -> None:
        """Background thread: recompute health scores every 60 seconds."""
        while self._running:
            self.compute_all_scores()
            time.sleep(BEACON_INTERVAL_SEC)

    def _send_to_tender(self, report: RegionalHealthReport) -> None:
        """Send report to Tender (placeholder for I2I/A2A integration)."""
        # In production: send via I2I bottle or HTTP to Tender endpoint
        pass


# ═══════════════════════════════════════════════════════════════
# Beacon Client (embedded in agents)
# ═══════════════════════════════════════════════════════════════

class BeaconClient:
    """Client that agents use to send periodic beacons to Lighthouse Keeper."""

    def __init__(
        self,
        agent_id: str,
        region_id: str,
        lighthouse_endpoint: str,
        agent_secret: bytes,
    ):
        self.agent_id = agent_id
        self.region_id = region_id
        self.endpoint = lighthouse_endpoint
        self.secret = agent_secret
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._beacon_loop, daemon=True, name="beacon-sender"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _beacon_loop(self) -> None:
        while self._running:
            self.send_beacon()
            time.sleep(BEACON_INTERVAL_SEC)

    def send_beacon(self) -> None:
        """Construct and send a beacon frame to the Lighthouse Keeper."""
        # In production: HTTP POST or shared filesystem write
        pass


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FLUX Lighthouse Keeper")
    parser.add_argument("--region", required=True, help="Region identifier")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port")
    parser.add_argument("--config", default="fleet_config.json", help="Fleet config")
    args = parser.parse_args()

    # Load fleet config
    with open(args.config) as f:
        config = json.load(f)

    # Start Lighthouse Keeper
    keeper = LighthouseKeeper(
        region_id=args.region,
        lighthouse_id=f"lighthouse-{args.region}",
        config=config,
    )
    keeper.start()

    print(f"Lighthouse Keeper started for region {args.region} on port {args.port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        keeper.stop()
        print("Lighthouse Keeper stopped.")
```

### 8.2 Module Structure

```
flux-runtime/
  tools/
    lighthouse_keeper.py      # Main module (~450 lines)
    beacon_client.py          # Agent-side beacon sender (~80 lines)
    health_scoring.py         # Health score algorithms (~120 lines)
    brothers_keeper_adapter.py # Adapter for ResourceMonitor (~60 lines)
  docs/
    lighthouse-keeper-architecture.md  # This document
```

### 8.3 Configuration

```yaml
# fleet-lighthouse-config.yaml
lighthouse:
  region_id: "us-east"
  beacon_interval_sec: 60
  report_interval_sec: 300
  stale_threshold_sec: 180
  down_threshold_sec: 300

  health_scoring:
    weights:
      heartbeat: 0.40
      task_completion: 0.25
      error_rate: 0.25
      token_efficiency: 0.10

  alerts:
    suppression_window_sec: 600
    max_active_alerts: 1000

  failover:
    promotion_capability: "A2A_DELEGATE"
    recovery_timeout_sec: 1800
    wal_directory: "/fleet/lighthouse/{region_id}/wal/"

  integration:
    tender_endpoint: "http://tender:8080/health-report"
    beacon_directory: "/fleet/beacons/"
    config_refresh_interval_sec: 300
```

---

## Appendix A — Data Model Reference

### A.1 Beacon Health Bits

| Bit | Name | Description |
|-----|------|-------------|
| 0 | PROCESS_ALIVE | Agent process is running |
| 1 | LLM_AVAILABLE | LLM API is reachable |
| 2 | CI_PASSING | Last CI run passed |
| 3 | MEMORY_OK | Memory usage below 80% |
| 4 | NETWORK_OK | Network connectivity confirmed |
| 5-7 | RESERVED | Reserved for future use |

### A.2 Health Score Weight Sensitivity

The health scoring weights are tunable per-region. Recommended defaults:

| Region Type | Heartbeat | Task Completion | Error Rate | Token Efficiency |
|-------------|-----------|----------------|------------|-----------------|
| Production (gpu-pool) | 0.35 | 0.30 | 0.25 | 0.10 |
| Development (cpu-pool) | 0.40 | 0.25 | 0.25 | 0.10 |
| Edge (jetson) | 0.50 | 0.15 | 0.25 | 0.10 |

Edge regions weight heartbeat more heavily because intermittent connectivity is expected and missed beacons are the primary health signal.

### A.3 Agent Health Record Lifecycle

```
UNKNOWN ──first beacon──▶ TRACKED ──score computed──▶ SCORED
                              │                          │
                         stale beacon               score change
                              │                          │
                              ▼                          ▼
                          STALE ◀───────────────── WARNING
                              │                          │
                         down beacon                   score drop
                              │                          │
                              ▼                          ▼
                          DOWN ◀────────────────── DEGRADED
                              │                          │
                         recovery                    score drop
                              │                          │
                              ▼                          ▼
                         RECOVERING ◀────────────── CRITICAL
```

---

## Appendix B — Cross-References

| Reference | Document | Relationship |
|-----------|----------|--------------|
| Three-tier hierarchy | tender-architecture.md §2 | Defines Brothers Keeper → Lighthouse Keeper → Tender |
| TokenSteward | tender-architecture.md §3 | Lighthouse feeds health data into budget allocation |
| Semantic Router | tools/semantic_router.py | Router uses health_score as availability factor |
| Fleet Config | tools/fleet_config.json | Agent profiles, domains, specializations |
| Resource Monitor | resource_limits.py | Brothers Keeper feeds telemetry from this |
| A2A Primitives | primitives.py | SIGNAL opcodes used for alert delivery |
| I2I Protocol | i2i-enhancements-v3 | FLEET_HEALTH message types |
| Knowledge Base | knowledge-federation/knowledge-base.json | Health domain entries |
| Conformance Runner | tools/conformance_runner.py | Triggered on health anomalies |
| TASK-BOARD | oracle1-vessel/TASK-BOARD.md | KEEP-001 (this task), MECH-001 (Mechanic Cron) |
| Mechanic Cron | docs/mechanic-cron-design.md | Consumes Lighthouse alerts for auto-issue creation |
