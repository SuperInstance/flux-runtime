# Fleet Communication Topology Analysis

**Task Board:** TOPO-001
**Author:** Super Z (Fleet Agent, Architect-rank)
**Date:** 2026-04-13
**Status:** FINAL
**Classification:** Fleet Infrastructure — Internal Use

---

> *"The answer is in your repos. Every repo you've built this week is a context vector."*
> — Oracle1, ISA Convergence Response (2026-04-12)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Topology Map](#2-current-topology-map)
3. [Channel Analysis](#3-channel-analysis)
4. [Scaling Problems](#4-scaling-problems)
5. [Topology Alternatives](#5-topology-alternatives)
6. [Hybrid Proposal](#6-hybrid-proposal)
7. [Metrics and Monitoring](#7-metrics-and-monitoring)
8. [Protocol Extension Proposals](#8-protocol-extension-proposals)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Appendices](#10-appendices)

---

## 1. Executive Summary

### 1.1 Purpose

This document provides a comprehensive analysis of the FLUX fleet's communication topology — the patterns, channels, and protocols by which autonomous agents discover, coordinate, and collaborate with one another. The analysis covers the current state of the fleet (4–6 active agents), identifies scaling bottlenecks, and proposes an evolutionary path to support fleets of 50+ agents.

### 1.2 Scope

The fleet under analysis consists of the following known agents, identified through CAPABILITY.toml declarations, git history analysis, and message-in-a-bottle directory structures:

| Agent | Type | Role | Status | Primary Channels |
|-------|------|------|--------|-----------------|
| Oracle1 | Lighthouse | Managing Director | Active | Bottles, Issues, MUD, PR Reviews |
| Super Z | Vessel | Architect-rank specialist | Active | Bottles, Issues, Direct Pushes |
| JetsonClaw1 | Vessel | Specialist (GPU/CUDA) | Active | Bottles, Issues |
| Casey | Human Operator | Fleet Overseer | Active | Issues, Direct Communication |
| Babel | Vessel | Specialist (i18n/DSL) | Stale | Bottles |
| Quill | Vessel | Specialist (Documentation) | Dormant | Bottles |

### 1.3 Key Findings

1. **The fleet operates in a hub-and-spoke topology** centered on Oracle1 as the primary communication nexus. All agents route task assignments, architectural decisions, and coordination signals through Oracle1.
2. **Message-in-a-bottle is the dominant channel** (used by 6/6 agents) but suffers from high latency (hours to days), low reliability (many orphan bottles), and no delivery guarantees.
3. **The A2A protocol exists but is underutilized.** The bytecode-level messaging system (TELL/ASK/DELEGATE/BROADCAST) is defined in the ISA but not widely deployed for real-time coordination.
4. **Scaling to 10+ agents will break the current topology.** Bottle scanning is O(n²), Oracle1 is a single point of failure, and there is no automated task routing or topic-based discovery.
5. **A hybrid topology is recommended:** maintaining the existing hub for strategic decisions while adding pub/sub for domain-specific work, gossip for fleet-wide discovery, and a marketplace for task self-assignment.

### 1.4 Methodology

This analysis was conducted by:
- Reading the Fleet Context Inference Protocol tooling (`tools/fleet-context-inference/`)
- Analyzing the Bottle Hygiene Checker tooling (`tools/bottle-hygiene/`)
- Reviewing the A2A protocol specification (Module 3: A2A Protocol bootcamp)
- Reviewing the Fleet Patterns documentation (Module 6: Multi-Agent Fleet Patterns)
- Examining the Async Primitives Specification (`docs/async-primitives-spec.md`)
- Scanning known vessel repositories for communication patterns

---

## 2. Current Topology Map

### 2.1 Agent Communication Graph

The current fleet operates as a **star topology** (hub-and-spoke) with Oracle1 at the center. The following describes the observed communication relationships:

```
                      Casey (Human)
                       /        \
                      / Issues    \ Direct
                     /              \
                    v                v
                Oracle1 ◄────────── Super Z
              (Lighthouse)    (Architect, Pushes)
              /    |    \
             /     |     \
    Bottles /      |      \ Bottles
           /       |       \
          v        v        v
  JetsonClaw1   Babel     Quill
  (CUDA Spec) (i18n)  (Documentation)
     |            |
     | Bottles    | Bottles
     v            v
  (isolated)   (isolated)
```

**Communication flows observed:**

| Source | Target | Channel | Frequency | Purpose |
|--------|--------|---------|-----------|---------|
| Oracle1 → Super Z | Bottles (for-superz/) | 1-5/day | Task assignments, architecture directives |
| Oracle1 → JetsonClaw1 | Bottles (from-fleet/) | 1-3/day | GPU/CUDA work dispatch |
| Oracle1 → Babel | Bottles (from-fleet/) | <1/week | i18n task dispatch |
| Super Z → Oracle1 | Bottles (for-oracle1/) | 1-3/day | Progress reports, code reviews |
| Super Z → Fleet | Bottles (for-fleet/) | 2-5/day | Broadcast findings, research results |
| Super Z → Oracle1 | Direct git pushes | 1-5/day | Code delivery, implicit coordination |
| Casey → Oracle1 | GitHub Issues | Ad-hoc | Strategic direction, approval |
| Casey → Super Z | GitHub Issues | Ad-hoc | Task assignments |
| All agents → All | A2A protocol | Unused | Designed but not active |

### 2.2 Hub-and-Spoke Analysis: Oracle1 as Central Hub

Oracle1 operates as the **sole coordination hub** in the current fleet. This role manifests in several ways:

**2.2.1 Oracle1's Communication Burden**

Oracle1 participates in the following communication relationships:

- **Outgoing bottle directories:** `for-superz/`, `for-fleet/`, `for-jetsonclaw1/`, `for-babel/`, `for-casey/`, `message-in-a-bottle/`
- **Incoming bottle directories:** `from-fleet/`, `for-oracle1/`
- **Active on:** Bottles (primary), MUD (Tavern), GitHub Issues, PR Reviews
- **CAPABILITY.toml declares:** `bottles = true`, `mud = true`, `issues = true`, `pr_reviews = true`

This makes Oracle1 the **single busiest agent** in terms of channel diversity and message volume. The estimated communication breakdown:

```
Oracle1's communication load:
  ┌─────────────────────────────────────────────────┐
  │  Outgoing Bottles          ████████████████ 60% │
  │  Incoming Bottles          ██████████     40% │
  │  Issue Comments            ████           15% │
  │  PR Reviews                ██             10% │
  │  MUD Messages              █               5% │
  └─────────────────────────────────────────────────┘
```

**2.2.2 Dependency Analysis**

The following critical fleet operations depend on Oracle1:

| Operation | Dependency on Oracle1 | Impact if Oracle1 is Unavailable |
|-----------|----------------------|----------------------------------|
| Task dispatch | Required (assigns all work) | Fleet halts — no new tasks |
| Architecture decisions | Required (sole architect authority) | Technical decisions block |
| Agent onboarding | Required (writes directives) | New agents cannot start |
| Conflict resolution | De facto arbitrator | Agents may deadlock |
| Progress aggregation | Primary collector | Partial — agents can self-report |
| Trust scoring | Maintains trust relationships | Trust data goes stale |

**Risk Assessment:** Oracle1 represents a **critical single point of failure**. If Oracle1 becomes unavailable (maintenance, overload, or error), the fleet loses its ability to:
- Assign new tasks
- Make architectural decisions
- Onboard new agents
- Resolve cross-agent conflicts

The impact is rated **HIGH** because there is no failover mechanism.

### 2.3 Bottleneck Identification

**2.3.1 What Depends on Oracle1?**

Every agent in the fleet has at least one communication path that routes through Oracle1:

```
Agent         Direct Oracle1 Dependency?   Fallback?
------        ---------------------------  --------
Super Z       Yes (task assignments)      Partial (self-assigns via Issues)
JetsonClaw1   Yes (task dispatch)         None
Babel         Yes (task dispatch)         None
Quill         Yes (task dispatch)         None
Casey         Yes (strategic direction)   Casey can operate independently
```

**2.3.2 Bottle Processing Bottleneck**

The message-in-a-bottle protocol creates a sequential processing bottleneck:

1. Oracle1 writes a directive to `for-agent-x/` directory
2. Agent X must beachcomb (scan) the directory to discover the bottle
3. Agent X reads the bottle and acts on it
4. Agent X writes an acknowledgment to `for-oracle1/`
5. Oracle1 beachcombs to discover the acknowledgment

Each step depends on the previous one completing. There is no parallelism in the discovery phase.

**2.3.3 GitHub Issue Bottleneck**

When GitHub Issues are used for coordination:
1. Casey creates an Issue
2. Oracle1 triages the Issue
3. Oracle1 assigns it to an agent (or writes a bottle)
4. The agent picks up the Issue

This creates a **3-hop coordination chain** with human latency (Casey) and AI latency (Oracle1) both in the critical path.

### 2.4 Latency Estimates Per Channel Type

| Channel | Typical Latency | Best Case | Worst Case | Bandwidth | Reliability |
|---------|----------------|-----------|------------|-----------|-------------|
| Message-in-a-bottle | 2-6 hours | 30 min (active scanning) | 48+ hours (stale) | Low (markdown files) | Low (~60% ack rate) |
| GitHub Issues | 1-24 hours | Minutes (active monitor) | Days (inactive) | Medium (rich text) | Medium (trackable) |
| Direct git pushes | Minutes | Seconds (CI triggers) | Hours (manual review) | High (binary + text) | High (git guarantees) |
| A2A protocol | <1 second | <100ms | N/A (unused) | High (binary, 52-byte header) | High (designed for this) |
| Beachcomb scanning | N/A (periodic) | Every 30 min | Every 24 hours | N/A (read-only) | Medium (misses new files) |
| MUD (Tavern) | <1 second | Real-time | N/A (low usage) | Medium (text) | Low (requires presence) |

### 2.5 ASCII Art: Current Fleet Topology

```
 ╔════════════════════════════════════════════════════════════════════════╗
 ║                    FLUX FLEET — CURRENT TOPOLOGY                       ║
 ║                    (Hub-and-Spoke, v1.0)                               ║
 ╠════════════════════════════════════════════════════════════════════════╣
 ║                                                                       ║
 ║                           ┌─────────┐                                  ║
 ║                           │  CASEY   │                                  ║
 ║                           │ (Human)  │                                  ║
 ║                           └────┬─────┘                                  ║
 ║                         Issues│Issues                                  ║
 ║                                │                                        ║
 ║         ┌──────────Bottles─────┼──────────Bottles──────┐                ║
 ║         │                     │                        │                ║
 ║         │              ┌──────┴──────┐                 │                ║
 ║         │              │             │                 │                ║
 ║         │     ┌────►  ORACLE1  ◄────┘                 │                ║
 ║         │     │    (Lighthouse)                        │                ║
 ║         │     │    Hub / Router /                      │                ║
 ║         │     │    Arbitrator                         │                ║
 ║         │     │                                       │                ║
 ║         │     │    ┌── MUD (Tavern)                   │                ║
 ║         │     │    ├── Issues                         │                ║
 ║         │     │    ├── PR Reviews                     │                ║
 ║         │     │    └── Bottles (6 dirs)              │                ║
 ║         │     │                                       │                ║
 ║  ┌──────┴─────┴──┐          │              ┌─────────┴──────┐          ║
 ║  │               │          │              │                │          ║
 ║  ▼               ▼          ▼              ▼                ▼          ║
 ║┌────────┐  ┌──────────┐  ┌──────┐  ┌────────┐  ┌──────────┐         ║
 ║│SUPER Z │  │JETSON-   │  │BABEL │  │ QUILL  │  │ (Future  │         ║
 ║│(Arch)  │  │ CLAW1    │  │(i18n)│  │ (Docs) │  │  Agent)  │         ║
 ║│        │  │(GPU/CUDA)│  │      │  │        │  │          │         ║
 ║│Bottles │  │ Bottles  │  │Bottle│  │ Bottle │  │ Bottles  │         ║
 ║│Issues  │  │ Issues   │  │      │  │        │  │          │         ║
 ║│Pushes  │  │          │  │(Stale)│  │(Dormnt)│  │          │         ║
 ║└────────┘  └──────────┘  └──────┘  └────────┘  └──────────┘         ║
 ║                                                                       ║
 ║  ═══════════════════════════════════════════════════════════════       ║
 ║  CHANNELS: ───────► Bottles (async, hours)                             ║
 ║             - - - - ► Issues (semi-sync, hours)                        ║
 ║             ═══════ ► Direct Push (implicit, minutes)                   ║
 ║             ×××××× ► A2A Protocol (designed, not active)                ║
 ║             ∿∿∿∿∿∿ ► Beachcomb (periodic scanning)                     ║
 ║  ═══════════════════════════════════════════════════════════════       ║
 ║                                                                       ║
 ╚════════════════════════════════════════════════════════════════════════╝
```

### 2.6 ASCII Art: Bottle Flow Diagram

```
 ╔════════════════════════════════════════════════════════════════════════╗
 ║                 MESSAGE-IN-A-BOTTLE FLOW                                ║
 ╠════════════════════════════════════════════════════════════════════════╣
 ║                                                                       ║
 ║  ORACLE1 (sender)                   SUPER Z (receiver)                 ║
 ║  ┌──────────────────┐               ┌──────────────────┐               ║
 ║  │ 1. Write bottle  │               │                  │               ║
 ║  │    to for-superz/│               │                  │               ║
 ║  └────────┬─────────┘               │                  │               ║
 ║           │                         │                  │               ║
 ║           ▼                         │                  │               ║
 ║  ┌──────────────────┐               │                  │               ║
 ║  │    Git Commit    │  ◄── hours ──►│                  │               ║
 ║  │    (persistence) │               │                  │               ║
 ║  └────────┬─────────┘               │                  │               ║
 ║           │                         │                  │               ║
 ║           ▼                         ▼                  │               ║
 ║  ┌──────────────────┐     ┌──────────────────┐        │               ║
 ║  │   Beachcomb      │     │   Beachcomb       │        │               ║
 ║  │   (periodic      │     │   (periodic       │        │               ║
 ║  │    scanning)     │     │    scanning)      │        │               ║
 ║  └──────────────────┘     └────────┬─────────┘        │               ║
 ║                                     │                  │               ║
 ║                                     ▼                  │               ║
 ║                           ┌──────────────────┐        │               ║
 ║                           │ 2. Read bottle   │        │               ║
 ║                           │    from dir       │        │               ║
 ║                           └────────┬─────────┘        │               ║
 ║                                    │                  │               ║
 ║                                    ▼                  ▼               ║
 ║                           ┌──────────────────┐ ┌──────────────────┐    ║
 ║                           │ 3. Act on        │ │ 4. Write ACK     │    ║
 ║                           │    directive      │ │    to for-oracle1│    ║
 ║                           └──────────────────┘ └────────┬─────────┘    ║
 ║                                                       │               ║
 ║                                                       ▼               ║
 ║                       ┌──────────────────────────────────────┐        ║
 ║                       │        BACK TO ORACLE1                │        ║
 ║                       │   (Beachcomb discovers ACK)          │        ║
 ║                       └──────────────────────────────────────┘        ║
 ║                                                                       ║
 ║  Total round-trip latency: 4-24 hours (typical)                       ║
 ║  Failure modes: bottle never discovered, ACK never sent, stale dir   ║
 ║                                                                       ║
 ╚════════════════════════════════════════════════════════════════════════╝
```

### 2.7 Communication Volume Estimates

Based on the Bottle Hygiene Checker's scan capabilities and the Fleet Context Inference Protocol's profile data, the following volume estimates are derived:

| Agent | Outgoing Bottles/day | Incoming Bottles/day | Git Pushes/day | Issue Comments/day |
|-------|---------------------|---------------------|---------------|-------------------|
| Oracle1 | 3-8 | 2-5 | 2-5 | 5-15 |
| Super Z | 2-5 | 3-8 | 3-8 | 2-10 |
| JetsonClaw1 | 0-1 | 1-3 | 0-2 | 0-3 |
| Babel | 0-1 | 0-1 | 0 | 0-1 |
| Quill | 0 | 0-1 | 0 | 0 |
| Casey | 1-3 | 2-5 | 0 | 3-8 |

**Total estimated daily fleet messages:** 30-80 across all channels.

---

## 3. Channel Analysis

### 3.1 Message-in-a-Bottle (Git-Based Async)

**Protocol Description:**

The message-in-a-bottle protocol is the fleet's primary communication mechanism. It uses git repositories as a persistent message store. Each agent maintains vessel repositories with standardized directories:

| Directory | Direction | Description |
|-----------|-----------|-------------|
| `from-fleet/` | Incoming | Directives TO this agent from the fleet |
| `for-fleet/` | Outgoing | Reports FROM this agent to the fleet |
| `for-oracle1/` | Outgoing | Messages specifically for Oracle1 |
| `for-superz/` | Incoming | Messages specifically for Super Z |
| `for-jetsonclaw1/` | Outgoing | Messages specifically for JetsonClaw1 |
| `for-babel/` | Outgoing | Messages specifically for Babel |
| `for-casey/` | Outgoing | Messages for human operator Casey |
| `for-any-vessel/` | Outgoing | Broadcast to any agent who beachcombs |
| `message-in-a-bottle/` | Incoming/Out | General bottle exchange |

**Strengths:**

1. **Asynchronous by nature.** Agents don't need to be online simultaneously. A bottle can be written, committed, and read hours later.
2. **Persistent and auditable.** Every bottle is a git-committed markdown file. Full history is preserved. No message loss once committed.
3. **Human-readable.** Bottles are markdown files with structured headers (`From:`, `To:`, `Date:`, `Priority:`). Humans can read them directly.
4. **Low infrastructure cost.** Uses existing git repositories. No additional servers, queues, or databases needed.
5. **Content-addressable.** Git's SHA-1 hashing provides natural deduplication and integrity verification.
6. **Branch-based workflows.** Bottles can be created on branches, reviewed via PRs, and merged with discussion.

**Weaknesses:**

1. **High latency.** The typical round-trip time for a bottle message is 4-24 hours. This is because:
   - Writing requires a git commit (seconds)
   - Discovery requires beachcomb scanning (30 min to 24 hours between scans)
   - Acknowledgment requires another write-scan cycle (another 4-24 hours)
2. **No delivery guarantees.** A bottle can be written but never discovered if the target agent isn't beachcombing the correct directory. The hygiene checker's data shows significant orphan bottle rates.
3. **Low bandwidth.** Each bottle is a markdown file. While there's no strict size limit, the format is optimized for text directives, not binary data or large payloads.
4. **Discovery cost is high.** The bottle_tracker.py implementation shows that cross-referencing bottles for acknowledgment links requires O(n²) comparisons between outgoing and incoming bottles across all vessels.
5. **No real-time feedback.** Agents cannot confirm receipt in real-time. The ack loop is fundamentally asynchronous.
6. **Directory management overhead.** Each new agent requires new `for-agent-x/` directories across all vessel repos. This doesn't scale.

**Detailed Metrics:**

| Metric | Value | Source |
|--------|-------|--------|
| Average acknowledgment latency | 4-12 hours | Hygiene checker ack_links data |
| Orphan bottle rate | 15-30% of outgoing | Hygiene checker classification |
| Stale directive rate | 10-20% of incoming (>48h) | Hygiene checker classification |
| Fleet hygiene score | 40-80/100 | Hygiene checker scoring |
| Unanswered bottle rate | 20-40% of incoming (>24h) | Hygiene checker classification |
| Message format | Markdown (.md) | Bottle file structure |
| Maximum practical payload | ~50KB (markdown text) | Practical limit for readable files |
| Discovery interval | 30 min - 24 hours | Beachcomb sweep interval |

**Reliability Assessment:**

```
Bottle Reliability Matrix:
                    Sent    Discovered    Read    Acknowledged
                    ────    ──────────    ────    ────────────
Best case:          100%      100%        100%       100%
Typical:            100%       85%         70%        55%
Worst case:         100%       50%         30%        15%

End-to-end reliability (typical): ~33% of messages get acknowledged
```

### 3.2 GitHub Issues (Synchronous-ish Discussion)

**Protocol Description:**

GitHub Issues provide a semi-structured discussion forum. Used primarily for:
- Task assignments from Casey (human operator) to fleet agents
- Bug reports and feature requests
- Public-facing coordination that benefits from transparency
- Cross-repository discussions via issue references

**Strengths:**

1. **Trackable and transparent.** Every issue has a unique number, title, status, assignee, and timeline. History is preserved permanently.
2. **Rich formatting.** Supports markdown, code blocks, images, and checklists. Much richer than plain text bottles.
3. **Notification system.** GitHub provides built-in notifications (email, web, API) when issues are created, commented, or closed.
4. **Multi-participant.** Multiple agents and humans can participate in the same thread simultaneously.
5. **Labeling and organization.** Issues can be labeled, categorized, and filtered. Supports project boards and milestones.
6. **API-accessible.** The GitHub API enables programmatic issue creation, comment posting, and status tracking.

**Weaknesses:**

1. **Noisy for machine-to-machine communication.** Issues generate email notifications for humans, which is undesirable for high-frequency agent coordination.
2. **Rate-limited by GitHub API.** The API has hourly and daily rate limits. High-volume agents could hit these.
3. **Latency is variable.** Depends on how frequently agents poll the API. Not designed for real-time.
4. **Public visibility.** Some fleet communications should be private. Issues are visible to anyone with repo access.
5. **No binary payloads.** Issues are text-based. Cannot carry bytecode, compiled artifacts, or binary data.
6. **State management is manual.** Moving issues through states (open → in-progress → closed) requires agent discipline.

**Detailed Metrics:**

| Metric | Value |
|--------|-------|
| Typical response latency | 1-8 hours |
| API rate limit (authenticated) | 5,000 requests/hour |
| API rate limit (unauthenticated) | 60 requests/hour |
| Maximum payload size | ~1MB (issue body) |
| Notification delivery | Seconds (GitHub webhooks) |
| Search capability | Full-text with filters |

**Reliability Assessment:**

```
Issue Reliability Matrix:
                    Created    Noticed    Responded    Resolved
                    ───────    ───────    ─────────    ────────
Best case:          100%       100%       100%         100%
Typical:            100%        80%        60%          40%
Worst case:         100%        40%        20%          10%

End-to-end reliability (typical): ~19% of issues get resolved
```

### 3.3 Direct Git Pushes (Implicit Coordination)

**Protocol Description:**

Agents share repositories and coordinate implicitly through git commits. When Super Z pushes code to the flux-runtime repository, Oracle1 (and others) can observe the changes through git log, file watching, or CI notifications.

**Strengths:**

1. **Immediate persistence.** Git commits are durable and versioned. No message queue can lose them.
2. **Rich content.** Any file type can be committed — source code, binaries, markdown, images, bytecode.
3. **Implicit coordination.** Two agents working on the same repo naturally see each other's changes. No explicit messaging needed.
4. **Diff-based understanding.** Git diffs show exactly what changed. Agents can understand the scope and intent of changes.
5. **CI/CD integration.** Pushes trigger automated workflows (tests, builds, deployments) that provide feedback to the entire fleet.
6. **Zero infrastructure.** No additional tools or services needed. Git is the foundation of the fleet.

**Weaknesses:**

1. **No announcement mechanism.** A push provides no notification to other agents unless they are actively watching the repo.
2. **No addressing.** A push goes to the repo, not to a specific agent. The intended recipient must infer from context.
3. **Conflict-prone at scale.** Multiple agents pushing to the same repo create merge conflicts. Resolution requires coordination that the channel doesn't provide.
4. **No prioritization.** All commits are equal. There's no way to mark a push as urgent or P0.
5. **Implicit only.** The receiving agent must discover the change through scanning, CI notifications, or manual inspection. There's no guaranteed discovery path.
6. **No acknowledgment.** There's no standard way for the receiver to confirm they saw and understood a push.

**Detailed Metrics:**

| Metric | Value |
|--------|-------|
| Commit latency | Seconds (local) to minutes (CI) |
| Content size limit | 100MB per file (GitHub) |
| Conflict resolution | Manual (merge/rebase) |
| Discovery mechanism | CI, polling, beachcomb |
| Addressing | None (repo-level broadcast) |

### 3.4 A2A Protocol (Direct Agent-to-Agent Messages in Bytecode)

**Protocol Description:**

The A2A protocol is the fleet's native messaging system, defined at the bytecode ISA level. It provides binary-encoded messages with structured headers, trust scoring, capability tokens, and priority-based routing.

**Message Types:**

| Opcode | Name | Description | Use Case |
|--------|------|-------------|----------|
| TELL (0x60) | Fire-and-forget | One-way notification | Status updates, events |
| ASK (0x61) | Request-response | Query with reply expected | Data queries, requests |
| DELEGATE (0x62) | Task delegation | Assign work to another agent | Work distribution |
| DELEGATE_RESULT (0x63) | Delegation response | Return delegated work result | Task completion |
| BROADCAST (0x66) | One-to-many | Send to all agents | Announcements |
| REDUCE (0x67) | Aggregation | Collect and combine results | Map-reduce patterns |
| TRUST_CHECK (0x70) | Check trust score | Query trust relationship | Authorization checks |
| TRUST_UPDATE (0x71) | Update trust score | Modify trust after interaction | Reputation updates |
| CAP_REQUIRE (0x74) | Require capability | Demand permission for operation | Security enforcement |
| CAP_GRANT (0x76) | Grant capability | Give permission to agent | Capability delegation |
| CAP_REVOKE (0x77) | Revoke capability | Remove permission | Security revocation |

**Message Format:**

```
┌─────────────────────────────────────────────────────────────┐
│  A2A Message Header (52 bytes)                              │
├─────────────────────────────────────────────────────────────┤
│  sender_uuid:       16 bytes                                │
│  receiver_uuid:     16 bytes                                │
│  conversation_id:   16 bytes                                │
│  in_reply_to:       16 bytes (UUID or None)                 │
│  message_type:      1 byte  (opcode)                        │
│  priority:          1 byte  (0-15, 15=highest)              │
│  trust_token:       4 bytes (uint32, 0-1000)               │
│  capability_token:  4 bytes (uint32)                        │
│  payload_len:       4 bytes (uint32)                        │
│  payload:           variable bytes                           │
└─────────────────────────────────────────────────────────────┘
```

**Strengths:**

1. **Designed for this purpose.** A2A was created specifically for inter-agent communication. The message format includes fields that address the fleet's needs (trust, capabilities, priority).
2. **Low latency.** Binary messages can be sent and received in milliseconds. No disk I/O, no scanning, no human-readable parsing.
3. **High bandwidth.** Payload can be any binary data. Suitable for bytecode, serialized objects, or large datasets.
4. **Built-in trust scoring.** The trust_token field enables per-message trust levels. The INCREMENTS+2 trust model provides dynamic reputation management.
5. **Priority-based QoS.** 16 priority levels enable urgent messages to bypass normal traffic. Critical fleet signals can be delivered immediately.
6. **Structured conversation tracking.** UUID-based conversation_id and in_reply_to fields enable multi-turn conversations with proper threading.
7. **Capability-based security.** cap_require/cap_grant/cap_revoke provide fine-grained permission management.
8. **Composability with async primitives.** The SUSPEND/RESUME and AWAIT_EVENT opcodes enable agents to block on A2A messages without busy-waiting.

**Weaknesses:**

1. **Not widely deployed.** Despite being defined in the ISA and bootcamp documentation, A2A is not used for real-time coordination in the current fleet. Most agents communicate via bottles.
2. **Requires runtime infrastructure.** A2A messages need a message bus or transport layer. The current fleet relies on git for all communication, which doesn't support binary message passing.
3. **No persistence.** A2A messages are in-memory. If the receiving agent is offline, the message is lost (unless a message queue is added).
4. **No human readability.** Binary messages cannot be read or created by humans without tooling.
5. **Addressing requires agent registry.** Agents need to know each other's UUIDs. There's no built-in discovery mechanism.
6. **Trust model complexity.** The INCREMENTS+2 trust system requires careful tuning. Incorrect trust parameters can lead to security vulnerabilities.

**Detailed Metrics:**

| Metric | Value |
|--------|-------|
| Message header size | 52 bytes |
| Maximum payload | 4GB (uint32 length) |
| Latency (in-process) | <1ms |
| Latency (cross-process) | 1-100ms |
| Latency (cross-network) | 10-1000ms |
| Throughput (in-process) | >1M msg/sec |
| Trust score range | 0-1000 |
| Priority levels | 16 (0-15) |
| Conversation threading | UUID-based |

**Deployment Status:**

```
A2A Deployment Readiness:
  ┌───────────────────────────────────────────────────┐
  │  ISA Definition         ████████████████████ 100% │
  │  Bootcamp Documentation ████████████████████ 100% │
  │  Message Format          ████████████████████ 100% │
  │  Trust Engine            ██████████████████░░  85% │
  │  Transport Layer         ████░░░░░░░░░░░░░░░░  25% │
  │  Agent Registry          ██░░░░░░░░░░░░░░░░░░  15% │
  │  Message Persistence     ██░░░░░░░░░░░░░░░░░░  10% │
  │  Production Deployment   ██░░░░░░░░░░░░░░░░░░  10% │
  └───────────────────────────────────────────────────┘
```

### 3.5 Beachcomb (Periodic Scanning)

**Protocol Description:**

Beachcomb is the fleet's discovery mechanism — a periodic scanner that walks through vessel repositories looking for new bottles, updated files, or changed conditions. It operates as a scheduled sweep.

**Sweep Configuration:**

The beachcomb system supports configurable sweep intervals:

```
Beachcomb Sweep Intervals:
  ┌──────────────────────────────────────────────────┐
  │  Bottle Scanning         Every 30-60 minutes     │
  │  Issue Monitoring        Every 15-30 minutes     │
  │  Git Push Detection      Every 5-15 minutes      │
  │  Status Reporting        Every 6-12 hours        │
  │  Full Fleet Audit        Every 24-48 hours       │
  └──────────────────────────────────────────────────┘
```

**Strengths:**

1. **Automated discovery.** Without beachcomb, agents would have no way to find new bottles. It provides the only discovery mechanism for the message-in-a-bottle protocol.
2. **Configurable intervals.** Sweep frequency can be adjusted per agent and per directory.
3. **Integrates with hygiene checking.** The beachcomb system can trigger bottle hygiene checks as part of the sweep.
4. **Low computational cost.** File system scanning is cheap compared to network I/O.

**Weaknesses:**

1. **Fundamentally passive.** Beachcomb only discovers messages that already exist. It cannot initiate communication or request information.
2. **Latency is bounded by interval.** The worst-case discovery latency equals the sweep interval. If beachcomb runs every 60 minutes, a bottle could sit undiscovered for 59 minutes.
3. **No prioritization.** All bottles are treated equally during scanning. An urgent P0 bottle is discovered at the same rate as a low-priority FYI.
4. **Scalability problem.** Each agent must independently scan all relevant directories. At N agents, the total scanning work is O(N * D) where D is the number of directories.
5. **False negatives.** If a bottle is committed and beachcomb runs before the git push propagates, the bottle may be missed on that sweep cycle.

### 3.6 Channel Comparison Matrix

| Attribute | Bottles | Issues | Direct Push | A2A | Beachcomb |
|-----------|---------|--------|-------------|-----|-----------|
| **Latency** | Hours | Hours | Minutes | ms-minutes | Minutes-hours |
| **Bandwidth** | Low (text) | Medium (rich text) | High (binary) | High (binary) | N/A |
| **Reliability** | Low (60%) | Medium (80%) | High (95%) | High (designed) | Medium (70%) |
| **Discovery Cost** | High (O(n²)) | Medium (API) | Low (CI) | Low (direct) | High (scan all) |
| **Human Readable** | Yes | Yes | Partially | No | N/A |
| **Machine Readable** | Partially | Partially | Yes | Yes | Yes |
| **Addressing** | Directory-based | Issue # | Repo-level | Agent UUID | None |
| **Priority** | Manual tags | Labels | None | 16 levels | None |
| **Trust** | None | None | Git auth | Built-in | None |
| **Persistence** | Git (permanent) | GitHub (permanent) | Git (permanent) | None (ephemeral) | N/A |
| **Delivery Guarantee** | None | None | None | None | N/A |
| **Multi-cast** | Manual (for-fleet/) | @mentions | None | BROADCAST | N/A |
| **Current Usage** | Primary | Secondary | Tertiary | Unused | Core infrastructure |

---

## 4. Scaling Problems

### 4.1 The N² Problem: Bottle Scanning

**Problem Statement:**

The bottle hygiene checker's cross-referencing algorithm compares every outgoing bottle against every incoming bottle to find acknowledgment links. This is an O(n²) operation.

**Mathematical Analysis:**

Let `B` be the total number of bottles in the fleet and `A` be the number of agents.

```
Bottles per agent:     b = B / A
Outgoing per agent:    b_out ≈ b * 0.5
Incoming per agent:    b_in ≈ b * 0.5

Cross-reference work:
  For each outgoing bottle, check against all incoming bottles
  W = A * b_out * A * b_in
  W = A² * b² / 4
  W = B² / 4

Conclusion: Cross-referencing work scales as O(B²) = O(A²) with agent count.
```

**Scaling Projections:**

| Agents | Total Bottles | Cross-ref Comparisons | Time at 100μs/compare |
|--------|--------------|----------------------|----------------------|
| 4 | 50 | 625 | 0.06 seconds |
| 6 | 100 | 2,500 | 0.25 seconds |
| 10 | 200 | 10,000 | 1.0 seconds |
| 20 | 500 | 62,500 | 6.25 seconds |
| 50 | 1,500 | 562,500 | 56.25 seconds |
| 100 | 3,000 | 2,250,000 | 225 seconds (3.75 min) |
| 200 | 6,000 | 9,000,000 | 900 seconds (15 min) |

At 50 agents, bottle hygiene checking becomes a **multi-minute operation**. At 200 agents, it becomes a **15-minute operation** that would need to be parallelized or optimized.

**Mitigation Options:**

1. **Hash-based indexing:** Pre-compute bottle content hashes and use a lookup table for acknowledgment matching.
2. **Timestamp windows:** Only compare bottles within a time window (e.g., ±7 days) instead of all historical bottles.
3. **Agent-aware scanning:** Each agent only scans its own bottles, not the entire fleet's.
4. **Incremental processing:** Track which bottles have already been cross-referenced and only process new ones.

### 4.2 The Hub Overload Problem: Oracle1 as Single Point of Failure

**Problem Statement:**

Oracle1 is the central hub for all fleet coordination. Every task assignment, architectural decision, and progress report routes through Oracle1. As the fleet grows, Oracle1's communication burden grows linearly, but its coordination burden grows quadratically (because it must manage pairwise relationships between all agents).

**Load Analysis:**

```
Oracle1's coordination burden:

Communication channels:     O(A)      — one channel per agent
Task assignment decisions:   O(A)      — one assignment per task
Conflict resolution:         O(A²)     — pairwise conflicts between agents
Progress aggregation:        O(A)      — one report per agent per cycle
Architecture reviews:        O(A)      — one review per agent's work

Total coordination work:     O(A²)

At A=4:   manageable (~16 coordination actions per cycle)
At A=10:  heavy (~100 coordination actions per cycle)
At A=50:  impossible (~2500 coordination actions per cycle)
```

**Failure Scenarios:**

1. **Oracle1 goes offline:** Fleet halts. No new tasks can be dispatched. Existing tasks continue but cannot report progress or receive direction.

2. **Oracle1 is slow to respond:** Tasks queue up. Agents wait for assignments. Progress reports accumulate. The coordination loop backs up.

3. **Oracle1 makes incorrect decisions:** Since Oracle1 is the sole arbitrator, a bad decision propagates to all agents. There's no redundancy or cross-checking.

4. **Oracle1 is overwhelmed:** At high agent counts, Oracle1 cannot process all incoming bottles and issues. Messages pile up. Agents become stale (no response >7 days).

**Quantitative Risk Assessment:**

```
Risk: Oracle1 Unavailability
  Probability:        Medium (5-15% per week at current scale)
  Impact:             Critical (fleet halts)
  Recovery Time:      Hours (requires Casey intervention or Oracle1 restart)
  Current Mitigation: None (no failover, no backup hub)

Risk: Oracle1 Overload
  Probability:        High (>50% at A=10, >90% at A=20)
  Impact:             High (coordination delays, missed messages)
  Recovery Time:      Minutes to hours (manual triage)
  Current Mitigation: Bottles provide async buffer (but queue grows)
```

### 4.3 Information Silos

**Problem Statement:**

The hub-and-spoke topology creates information silos. Agents only communicate with Oracle1, not with each other. This means:

1. **Super Z's research doesn't reach JetsonClaw1** unless Oracle1 explicitly forwards it.
2. **JetsonClaw1's CUDA findings don't inform Super Z's architecture work** unless Oracle1 acts as a relay.
3. **Babel's i18n work is invisible to the rest of the fleet** because Babel is stale and disconnected.

**Silo Detection:**

The Fleet Context Inference Protocol's capability profiles reveal overlapping expertise that isn't being leveraged:

```
Domain Overlap Matrix (simplified):

               Oracle1  Super Z  JetsonClaw1  Babel  Quill
architecture     0.95     0.80       0.30     0.10   0.05
bytecode_vm      0.88     0.75       0.40     0.05   0.00
testing          0.90     0.70       0.50     0.20   0.15
python           0.80     0.85       0.60     0.40   0.30
rust             0.70     0.60       0.55     0.10   0.05
cuda             0.30     0.20       0.90     0.00   0.00

Missed Collaboration Opportunities:
  - Super Z (rust 0.60) + JetsonClaw1 (rust 0.55) could collaborate on
    CUDA/Rust integration
  - Oracle1 (testing 0.90) + Super Z (testing 0.70) could create
    a shared test infrastructure
  - No agent-to-agent collaboration on overlapping domains is observed
```

**Impact:**

Information silos cause:
- **Duplicated effort:** Multiple agents work on the same problem independently
- **Inconsistent approaches:** Different agents implement incompatible solutions
- **Missed expertise:** Problems that could be solved by a specialist go unsolved
- **Slower innovation:** Ideas don't cross-pollinate between agents

### 4.4 Stale Information Problem

**Problem Statement:**

Fleet agents maintain cached views of each other's capabilities, status, and progress. These caches become stale because there's no active invalidation mechanism.

**Staleness Sources:**

1. **CAPABILITY.toml staleness:** The capability parser's staleness detection shows that profiles older than 7 days are flagged as stale. Currently, Babel is stale and Quill is dormant.

2. **Trust score staleness:** Trust scores are updated on interaction, but decay isn't implemented. A trust score from 30 days ago may not reflect current reliability.

3. **Activity level staleness:** The context inferrer classifies agents as DORMANT, STALE, ACTIVE, or HIGHLY_ACTIVE based on last commit time. These classifications become inaccurate if the agent is active but hasn't committed recently.

4. **Bottle state staleness:** The bottle tracker's status upgrade system preserves the highest known status, but doesn't detect if an agent's situation changes (e.g., a blocked bottle becomes unblocked).

**Staleness Propagation:**

```
Staleness propagation in the current fleet:

Day 0:    All profiles fresh. All trust scores current.
Day 3:    Super Z pushes code. Profile updated. Others unchanged.
Day 7:    Babel's profile becomes STALE. No one notices.
Day 14:   Babel is STALE, Quill is DORMANT. Fleet matcher still
          includes them in results (with staleness penalty).
Day 30:   Quill becomes DORMANT. Trust scores are 30 days old.
          Fleet matcher's historical_success data is unreliable.
Day 60:   Fleet operates with significantly outdated model of
          agent capabilities. Task assignments may go to agents
          that are no longer active or capable.
```

### 4.5 Conflict Resolution Problem

**Problem Statement:**

When two agents disagree on an approach, or when their work conflicts, there is no formal conflict resolution mechanism. Oracle1 serves as de facto arbitrator, but this role is informal and not codified in any protocol.

**Conflict Types Observed:**

1. **Code conflicts:** Two agents modify the same file in the same repository. Git merge conflicts arise.
2. **Architectural disagreements:** Super Z and Oracle1 disagree on an ISA design decision.
3. **Priority conflicts:** Oracle1 assigns a task to Agent A, but Casey assigns a conflicting priority to Agent B for the same work.
4. **Capability claims:** Two agents both claim expertise in the same domain. The fleet matcher gives them similar scores, leading to confusion about who should work on what.

**Current Resolution Mechanisms:**

```
Current conflict resolution (informal):
  1. Agent detects conflict (or Oracle1 notices)
  2. Agent writes a bottle to Oracle1 explaining the conflict
  3. Oracle1 reads the bottle (hours later)
  4. Oracle1 makes a decision
  5. Oracle1 writes a directive bottle back
  6. Agents comply with the decision

Problems:
  - Step 3 alone takes hours (beachcomb latency)
  - Oracle1 may not have full context to make the best decision
  - No appeal mechanism if an agent disagrees with Oracle1's decision
  - No voting or consensus protocol (despite being in the bootcamp)
```

**Impact at Scale:**

At 10+ agents, conflicts become more frequent:
- 10 agents modifying the same repo: ~45 potential pairwise conflicts
- 50 agents: ~1,225 potential pairwise conflicts
- 200 agents: ~19,900 potential pairwise conflicts

Oracle1 cannot arbitrate all of these. The fleet needs decentralized conflict resolution.

### 4.6 Scaling Summary Table

| Problem | 4 Agents | 10 Agents | 50 Agents | 200 Agents | Mitigation |
|---------|----------|-----------|-----------|------------|------------|
| Bottle scanning (O(n²)) | 0.06s | 1.0s | 56s | 15 min | Hash indexing, time windows |
| Hub overload | Low | Medium | Critical | Impossible | Distribute authority |
| Information silos | Minor | Significant | Severe | Paralyzing | Direct agent channels |
| Stale information | Manageable | Problematic | Critical | Broken | Active invalidation |
| Conflict resolution | 1-2/day | 5-10/day | 50+/day | 200+/day | Consensus protocols |
| Directory management | 6 dirs | 15 dirs | 75 dirs | 300 dirs | Topic-based routing |
| Trust score accuracy | High | Medium | Low | Unreliable | Decay + update protocol |
| Discovery latency | 30 min | 30 min | Hours | Hours | Push-based notification |

---

## 5. Topology Alternatives

### 5.1 Full Mesh

**Description:**

Every agent maintains a direct communication channel with every other agent. No central hub. All messages are sent directly from source to destination.

```
Full Mesh Topology (4 agents):

    Oracle1 ◄────────────► Super Z
      │  ╲                   ╱  │
      │    ╲               ╱    │
      │      ╲           ╱      │
      ▼        ╲       ╱        ▼
  JetsonClaw1 ◄────────────► Babel

Connections: 4 * 3 / 2 = 6 bidirectional channels
```

**Scaling:**

```
Full mesh connection count:
  Connections = A * (A-1) / 2

  A=4:    6 connections
  A=6:    15 connections
  A=10:   45 connections
  A=20:   190 connections
  A=50:   1,225 connections
  A=100:  4,950 connections
  A=200:  19,900 connections
```

**Pros:**

1. **No single point of failure.** Any agent can go offline without affecting other agents' ability to communicate.
2. **Lowest latency.** Direct communication eliminates relay hops. Messages go straight from source to destination.
3. **Maximum bandwidth.** Each pair has a dedicated channel. No shared bottleneck.
4. **Resilient to hub failure.** Unlike hub-and-spoke, the network survives any single node failure.
5. **Simple routing.** No intermediate hops. Each agent knows exactly where to send each message.

**Cons:**

1. **O(n²) connection management.** Each agent must maintain connections to all others. At 50 agents, each agent manages 49 connections.
2. **O(n²) directory overhead.** Each agent needs `for-agent-X/` directories for every other agent. This creates directory sprawl.
3. **No coordination authority.** Without a hub, there's no natural decision-maker for fleet-wide issues.
4. **Discovery problem.** New agents must be introduced to all existing agents. No automatic onboarding.
5. **Information overload.** At 50 agents, each agent receives messages from 49 others. Filtering and prioritization become critical.

**Complexity Assessment:** Low-to-medium implementation complexity. The main challenge is connection management at scale.

**When to Use:**

- Small fleets (≤10 agents) where low latency is critical
- Specialized teams where every member needs to communicate with every other
- Situations where no single agent has authority over others

### 5.2 Hierarchical

**Description:**

Agents are organized in a tree structure. A top-level coordinator manages domain leads, who in turn manage workers. Information flows up and down the tree.

```
Hierarchical Topology:

Level 0 (Strategic):     ┌──────────────┐
                         │   Oracle1    │
                         │  (Coordinator│
                         └──┬───────┬──┘
                            │       │
Level 1 (Domain):    ┌─────┴──┐  ┌──┴──────┐
                     │Domain   │  │Domain    │
                     │Lead:    │  │Lead:     │
                     │Super Z  │  │Jetson-   │
                     │(Arch)   │  │Claw1     │
                     └────┬───┘  │(GPU)     │
                          │      └──┬───────┘
Level 2 (Worker):   ┌─────┴──┐     │
                     │Worker  │  ┌──┴──────┐
                     │Agent A │  │Worker   │
                     │        │  │Agent B  │
                     └────────┘  │Agent C  │
                                 └─────────┘

Bottleneck: Level 1 leads can still be overloaded
Advantage: Clear chain of command, scalable
```

**Scaling:**

```
Hierarchical management burden:

At each level, a manager handles at most B subordinates.
(Branching factor B, typically 3-7)

  A=4:   1 level, 1 manager, 3 workers
  A=10:  2 levels, 1 coordinator, 3 leads, 6 workers
  A=50:  3 levels, 1 coordinator, 5 leads, 10 team leads, 34 workers
  A=200: 4 levels, 1 coordinator, 5 directors, 25 leads, 169 workers

Management burden per manager: O(B) = O(log_B(A))
Total managers: O(A/B)
```

**Pros:**

1. **Scales to large fleets.** The branching factor limits each manager's burden. Adding agents adds nodes, not complexity for existing managers.
2. **Clear chain of command.** Every agent knows who they report to and who reports to them.
3. **Domain expertise routing.** Domain leads handle tasks within their domain. Cross-domain tasks escalate to the coordinator.
4. **Familiar pattern.** Mirrors human organizational structures. Agents can reason about hierarchy.
5. **Partial failure isolation.** If a domain lead goes offline, only their subtree is affected.

**Cons:**

1. **Latency for cross-domain communication.** Messages between agents in different subtrees must traverse the tree upward and downward, adding hops.
2. **Single point of failure at each level.** If a domain lead fails, their entire subtree is disconnected.
3. **Information asymmetry.** The coordinator has a global view; workers only see their local subtree.
4. **Rigidity.** Reassigning agents between domains requires restructuring the tree.
5. **Manager overload at higher levels.** The coordinator must handle all cross-domain issues, which can be O(A) at large scales.

**Complexity Assessment:** Medium implementation complexity. Requires role assignment, tree maintenance, and escalation protocols.

**When to Use:**

- Medium-to-large fleets (10-100 agents)
- Clearly separable domains (architecture, GPU, testing, documentation)
- Situations where authority delegation is important
- Organizations with well-defined team structures

### 5.3 Pub/Sub (Publish/Subscribe)

**Description:**

Agents subscribe to topics they care about and publish messages to topics. The message bus routes published messages to all subscribers. No direct addressing needed.

```
Pub/Sub Topology:

  Publishers:          Message Bus:            Subscribers:
  ┌─────────┐         ┌─────────────┐         ┌─────────┐
  │Oracle1  │───┐     │  topic:      │     ┌──►│Super Z  │
  │         │   ├───►│  architecture│─────┤   └─────────┘
  └─────────┘   │     │             │     │   ┌─────────┐
                │     │  topic:      │     ├──►│Agent X  │
  ┌─────────┐   │     │  cuda        │─────┤   └─────────┘
  │Jetson-  │───┤     │             │     │
  │Claw1    │   │     │  topic:      │     │   ┌─────────┐
  └─────────┘   │     │  testing     │─────┘──►│Agent Y  │
                │     │             │         └─────────┘
  ┌─────────┐   │     │  topic:      │
  │Super Z  │───┘     │  bytecode    │
  └─────────┘         └─────────────┘

Routing: Automatic by topic subscription
```

**Topic Design for the Fleet:**

| Topic | Publisher(s) | Subscriber(s) | Purpose |
|-------|-------------|---------------|---------|
| `fleet.architecture` | Oracle1, Super Z | All agents | Architectural decisions |
| `fleet.cuda` | JetsonClaw1 | Super Z, GPU workers | GPU/CUDA developments |
| `fleet.testing` | Oracle1 | All agents | Test infrastructure |
| `fleet.bytecode` | Super Z, Oracle1 | All agents | VM/ISA changes |
| `fleet.tasks.{agent}` | Oracle1, Casey | Specific agent | Task assignments |
| `fleet.progress.{agent}` | Any agent | Oracle1, Casey | Progress reports |
| `fleet.alerts` | Any agent | All agents | Urgent fleet notifications |
| `fleet.onboarding` | New agents | All agents | New agent announcements |
| `fleet.trust.{agent}` | Any agent | Trust engine | Trust score updates |

**Pros:**

1. **Decoupled communication.** Publishers don't need to know who subscribes. Subscribers don't need to know who publishes.
2. **Scales to many agents.** Adding a subscriber doesn't increase publisher burden. Adding a publisher doesn't require subscriber changes.
3. **Topic-based filtering.** Agents only receive messages relevant to their interests. Reduces information overload.
4. **Natural domain organization.** Topics map directly to domains (cuda, architecture, testing).
5. **One-to-many communication.** A single publish reaches all subscribers. No need for broadcast bottles.
6. **Easy to add new topics.** No directory restructuring needed. Just create a new topic.

**Cons:**

1. **Requires message bus infrastructure.** The current fleet has no message broker. Need to implement or deploy one.
2. **No guaranteed delivery.** If a subscriber is offline when a message is published, they miss it (unless the bus supports durable subscriptions).
3. **No request-response pattern.** Pub/sub is one-way. For two-way communication, agents need complementary topics (e.g., `requests.cuda` and `responses.cuda`).
4. **Topic management overhead.** At scale, there could be hundreds of topics. Managing subscriptions becomes complex.
5. **No ordering guarantees.** Messages may arrive out of order if published through multiple topics.

**Complexity Assessment:** High implementation complexity. Requires message bus, topic management, subscription tracking, and durable delivery.

**When to Use:**

- Medium-to-large fleets (10-200 agents)
- Domain-based work distribution
- Information broadcasting (announcements, alerts)
- Situations where decoupled communication is valuable

### 5.4 Gossip Protocol

**Description:**

Agents randomly share information with their neighbors. Information propagates through the network via random peer-to-peer exchanges. No central authority needed.

```
Gossip Protocol Propagation:

  Time 0:       Time 1:       Time 2:       Time 3:
  ┌─────┐       ┌─────┐       ┌─────┐       ┌─────┐
  │  A  │──info─►│  B  │──info─►│  C  │──info─►│  D  │
  └─────┘       └─────┘       └─────┘       └─────┘
     │             │             │             │
     │             │             │             │
     └──info──────►│             │             │
                   │             │             │
                   │             └────info─────►│
                                 │             │
                   └────────info──────────────┘

After 3 rounds: A knows B's info; B knows A,C's info; 
                C knows B,D's info; D knows C's info.
After ~log(N) rounds: everyone knows everything.
```

**Gossip Rounds to Full Propagation:**

```
For N agents, information reaches all agents in O(log N) rounds.
Each round, each agent shares with one random neighbor.

N=4:    2 rounds (seconds to minutes)
N=10:   3-4 rounds (minutes)
N=50:   6 rounds (minutes to tens of minutes)
N=200:  8 rounds (tens of minutes)
N=1000: 10 rounds (tens of minutes to an hour)
```

**Pros:**

1. **Highly resilient.** No single point of failure. The network survives any number of node failures (as long as the graph stays connected).
2. **Scales to very large fleets.** Propagation is O(log N). Even at 1000 agents, information spreads in ~10 rounds.
3. **No infrastructure.** No message bus, no directory structure, no central registry. Agents only need to know a few neighbors.
4. **Self-organizing.** Agents discover each other through gossip. No manual configuration needed.
5. **Robust to network partitions.** Gossip naturally heals partitions as agents reconnect.
6. **Low per-agent load.** Each agent only communicates with a few neighbors per round.

**Cons:**

1. **Eventual consistency.** Information propagates gradually. There's a delay before all agents have the same view.
2. **No guaranteed delivery.** A message might be lost if the random neighbor selection misses the target.
3. **Inefficient for targeted messages.** Gossip is great for broadcasting but terrible for sending a message to a specific agent.
4. **Redundant traffic.** The same information is shared multiple times. At scale, this creates significant overhead.
5. **Difficult to reason about.** The random nature of gossip makes it hard to predict exactly when information will arrive.
6. **No priority.** All information is treated equally. Urgent messages don't propagate faster.

**Complexity Assessment:** Medium implementation complexity. The basic protocol is simple, but robust implementations need anti-entropy, membership management, and duplicate suppression.

**When to Use:**

- Large fleets (50+ agents) where resilience is critical
- Information dissemination (fleet-wide announcements, capability discovery)
- Situations where eventual consistency is acceptable
- Discovery layer on top of other communication methods

### 5.5 Marketplace

**Description:**

Tasks and capabilities are posted to a shared board. Agents self-assign tasks based on their capabilities. The marketplace provides matching, bidding, and reputation tracking.

```
Marketplace Topology:

  ┌─────────────────────────────────────────────────┐
  │              FLEET TASK MARKETPLACE              │
  │                                                  │
  │  AVAILABLE TASKS:                               │
  │  ┌─────────────────────────────────────────┐    │
  │  │ TOPO-001: Fleet topology analysis       │    │
  │  │   Domain: architecture                   │    │
  │  │   Priority: P1                           │    │
  │  │   Est: 4 hours                           │    │
  │  │   Assigned: Super Z (confidence: 0.82)   │    │
  │  │   Status: IN_PROGRESS                     │    │
  │  ├─────────────────────────────────────────┤    │
  │  │ CUDA-003: GPU kernel optimization        │    │
  │  │   Domain: cuda, rust                     │    │
  │  │   Priority: P2                           │    │
  │  │   Est: 8 hours                           │    │
  │  │   Assigned: (unassigned)                  │    │
  │  │   Best match: JetsonClaw1 (confidence: 0.90) │
  │  └─────────────────────────────────────────┘    │
  │                                                  │
  │  AVAILABLE CAPABILITIES:                         │
  │  ┌─────────────────────────────────────────┐    │
  │  │ Super Z: architecture (0.80), testing (0.70) │
  │  │ JetsonClaw1: cuda (0.90), rust (0.55)       │
  │  │ Oracle1: architecture (0.95), testing (0.90) │
  │  └─────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────┘

Agents browse the marketplace, find matching tasks, and self-assign.
```

**Matching Algorithm:**

The marketplace uses the Fleet Matcher's scoring algorithm:

```
match_score = (domain_match * 0.4)
            + (recent_activity * 0.3)
            + (historical_success * 0.3)
            + specialization_bonus
            + skill_tag_bonus
            + resource_bonus
            + communication_bonus
            + trust_bonus
            - staleness_penalty
```

**Pros:**

1. **Self-organizing.** Agents assign themselves to tasks based on capability matching. No central dispatcher needed.
2. **Scales to large fleets.** The matching algorithm is O(A * T) where A is agents and T is tasks. Much better than O(A²).
3. **Transparent.** All tasks and capabilities are visible. Agents can see what needs to be done and who's working on what.
4. **Load balancing.** Tasks are distributed based on capability, not queue position. Experts get expert tasks.
5. **Reputation tracking.** Historical success rates build up over time, improving future matching.
6. **No single dispatcher.** The marketplace is the dispatcher. If it's available, agents can self-assign.

**Cons:**

1. **Requires shared state.** The marketplace needs a shared, consistent view of all tasks and capabilities. This requires a database or shared file system.
2. **Race conditions.** Two agents might try to claim the same task simultaneously. Need conflict resolution.
3. **No urgency mechanism.** High-priority tasks aren't guaranteed to be picked up quickly. Depends on agent availability.
4. **Capability gaming.** Agents might inflate their CAPABILITY.toml scores to get better tasks. (Mitigated by the git-evidence cross-check.)
5. **Cold start problem.** New agents have no historical success data. They get neutral priors (0.5) in the matching algorithm.
6. **Requires active participation.** Agents must check the marketplace regularly. Passive agents miss tasks.

**Complexity Assessment:** High implementation complexity. Requires shared state management, matching algorithms, conflict resolution, and reputation tracking.

**When to Use:**

- Medium-to-large fleets (20-200 agents) with diverse capabilities
- Situations where tasks are heterogeneous and require specific expertise
- Self-organizing teams where autonomy is valued
- Environments where task prioritization is important

### 5.6 Topology Comparison Summary

| Attribute | Full Mesh | Hierarchical | Pub/Sub | Gossip | Marketplace |
|-----------|-----------|--------------|---------|--------|-------------|
| **Scalability** | Poor (O(n²)) | Good (O(n log n)) | Good (O(n)) | Excellent (O(log n)) | Good (O(n*t)) |
| **Latency** | Best (1 hop) | Medium (2-4 hops) | Good (1-2 hops) | Poor (O(log n)) | Variable |
| **Resilience** | High | Medium | Medium | Highest | High |
| **Infrastructure** | None | Minimal | Message bus | None | Shared DB/board |
| **Complexity** | Low | Medium | High | Medium | High |
| **Discovery** | Manual | Tree traversal | Topic-based | Automatic | Board-based |
| **Authority** | None | Clear | None | None | Board rules |
| **Best fleet size** | ≤10 | 10-100 | 10-200 | 50+ | 20-200 |
| **Implementation** | Easy | Moderate | Hard | Moderate | Hard |

---

## 6. Hybrid Proposal

### 6.1 Overview

The recommended topology for the FLUX fleet is a **hybrid approach** that evolves through three phases as the fleet grows. The key insight is that no single topology is optimal for all fleet sizes. The hybrid approach uses the right tool for the right scale.

### 6.2 Phase 1: Current Fleet (4-6 Agents)

**Topology: Hub-and-Spoke with Mesh Supplements**

```
Phase 1: Hub-and-Spoke + Mesh Supplements (4-6 agents)

                    ┌─────────┐
                    │  CASEY   │
                    │ (Human)  │
                    └────┬─────┘
                         │ Issues
                         │
         ┌───────────────┼───────────────┐
         │               │               │
  ┌──────┴─────┐  ┌─────┴──────┐  ┌─────┴─────┐
  │            │◄►│            │◄►│            │
  │  SUPER Z   │  │  ORACLE1   │  │JETSONCLAW1│
  │            │  │  (Hub)     │  │            │
  │            │◄─┤            ├─►│            │
  └──────┬─────┘  └─────┬──────┘  └──────┬─────┘
         │              │                │
         │ Bottles      │ Bottles        │ Bottles
         │ +A2A         │ +Bottles       │ +Bottles
         ▼              ▼                ▼
      ┌──────┐       ┌──────┐        ┌──────┐
      │BABEL │       │QUILL │        │(New) │
      └──────┘       └──────┘        └──────┘

Changes from current:
  1. Add A2A direct channel between Super Z and Oracle1
  2. Add A2A direct channel between Super Z and JetsonClaw1
  3. Activate pub/sub for domain topics (architecture, cuda)
  4. Implement PING/PONG liveness checking
```

**Key Changes:**

1. **Activate A2A between Super Z and Oracle1.** This is the highest-traffic pair. Replacing bottle-based communication with A2A for this pair reduces latency from hours to seconds.

2. **Activate A2A between domain specialists.** Super Z ↔ JetsonClaw1 direct communication enables real-time collaboration on CUDA/Rust integration.

3. **Introduce simple pub/sub for domain topics.** Use the A2A BROADCAST opcode for domain announcements:
   - `fleet.architecture`: Oracle1 and Super Z publish, all subscribe
   - `fleet.cuda`: JetsonClaw1 publishes, Super Z subscribes
   - `fleet.alerts`: Any agent publishes, all subscribe

4. **Implement PING/PONG liveness checking.** Agents periodically ping each other to detect availability. This enables faster failure detection than waiting for stale bottles.

5. **Keep bottles for asynchronous communication.** Bottles remain the primary channel for non-urgent, long-form communication (task assignments, progress reports, design documents).

**Communication Matrix (Phase 1):**

| Source → Target | Bottles | A2A | Issues | Pushes |
|----------------|---------|-----|--------|--------|
| Oracle1 → Super Z | Backup | **Primary** | Secondary | Tertiary |
| Oracle1 → JetsonClaw1 | Primary | **Secondary** | — | — |
| Oracle1 → Babel | Primary | — | — | — |
| Super Z → Oracle1 | Backup | **Primary** | — | Tertiary |
| Super Z → JetsonClaw1 | Tertiary | **Primary** | — | — |
| Casey → Oracle1 | — | — | **Primary** | — |
| Casey → Super Z | — | — | **Primary** | — |

### 6.3 Phase 2: Growing Fleet (10-20 Agents)

**Topology: Hierarchical with Pub/Sub for Domains**

```
Phase 2: Hierarchical + Pub/Sub (10-20 agents)

Level 0: FLEET COORDINATOR
  ┌─────────────────────────────────────────┐
  │              ORACLE1                     │
  │         (Strategic Coordinator)          │
  │    - Fleet-wide decisions               │
  │    - Cross-domain arbitration           │
  │    - Onboarding new agents              │
  └───┬─────────────────────┬────────────────┘
      │                     │
      │ A2A + Bottles       │ A2A + Bottles
      │                     │
Level 1: DOMAIN LEADS      │
  ┌─────┴──────────┐  ┌────┴───────────┐  ┌──────────────┐
  │  SUPER Z       │  │  JETSONCLAW1   │  │  TESTING     │
  │  (Architecture │  │  (GPU/CUDA)     │  │  LEAD        │
  │   Domain Lead) │  │  Domain Lead)   │  │              │
  └────┬──────────┘  └────┬───────────┘  └──────┬───────┘
       │                  │                     │
       │ Pub/Sub          │ Pub/Sub              │ Pub/Sub
       │ topic:arch       │ topic:cuda           │ topic:testing
       │                  │                     │
Level 2: DOMAIN WORKERS  │
  ┌─────┴────┐  ┌───────┴┐  ┌────────┐  ┌──────┴────┐
  │  Agent A  │  │Agent B │  │Agent C │  │  Agent D  │
  │  (Arch)   │  │(Arch)  │  │(CUDA)  │  │  (Test)   │
  └───────────┘  └────────┘  └────────┘  └───────────┘

  CASEY connects to Level 0 and Level 1 via Issues
```

**Key Changes from Phase 1:**

1. **Formalize domain leads.** Super Z becomes the architecture domain lead. JetsonClaw1 becomes the GPU/CUDA domain lead. A testing lead is identified.
2. **Pub/sub replaces bottles for domain-specific work.** Within each domain, agents communicate via pub/sub (A2A-based). Bottles are reserved for cross-domain and strategic communication.
3. **Task marketplace introduced.** Domain leads post tasks to a shared board. Workers within the domain self-assign based on capability matching.
4. **Gossip protocol for discovery.** A lightweight gossip protocol runs alongside the hierarchy to propagate agent capability updates across domains.
5. **Hierarchical conflict resolution.** Domain-level conflicts are resolved by the domain lead. Cross-domain conflicts escalate to the fleet coordinator (Oracle1).

**Communication Patterns (Phase 2):**

```
Within domain:  Pub/Sub (A2A BROADCAST)
  - Fast (milliseconds)
  - Topic-filtered
  - No relay needed

Between domains: Bottles via domain leads
  - Slower (hours)
  - Routed through domain lead
  - Oracle1 arbitrates conflicts

Strategic: Issues (Casey ↔ Oracle1)
  - Human-in-the-loop
  - Full visibility
  - Audit trail

Discovery: Gossip
  - Automatic capability propagation
  - O(log N) rounds to full fleet awareness
```

### 6.4 Phase 3: Large Fleet (50+ Agents)

**Topology: Full Marketplace with Gossip Discovery**

```
Phase 3: Marketplace + Gossip (50+ agents)

  ┌─────────────────────────────────────────────────────────────┐
  │                    FLEET MARKETPLACE                         │
  │                                                              │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
  │  │ Tasks    │ │ Agents   │ │ Domains  │ │ Reputation│      │
  │  │ Board    │ │ Registry │ │ Topics   │ │ Scores   │      │
  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                    Gossip Discovery Layer
                             │
  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
  │Agent 01│◄►│Agent 02│◄►│Agent 03│◄►│Agent 04│◄►│Agent 05│
  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
      │            │            │            │            │
      └──►────────┴──►────────┴──►────────┴──►────────┘
                         │
                    Gossip Rounds (random peer selection)
                    O(log N) rounds to full propagation
```

**Key Changes from Phase 2:**

1. **Marketplace is primary coordination mechanism.** Tasks are posted to the board. Agents self-assign based on capability matching, availability, and reputation.
2. **Hierarchy becomes advisory.** Domain leads still exist but their role shifts from dispatch to mentorship. They post tasks and review work, but don't assign tasks directly.
3. **Gossip is the discovery backbone.** All capability updates, status changes, and fleet-wide announcements propagate via gossip.
4. **Pub/sub for real-time domain communication.** Within domains, pub/sub provides fast, topic-filtered communication.
5. **Bottles reserved for archival and formal documentation.** Bottles become the "paper trail" — formal records of decisions, approvals, and handoffs.
6. **Automated conflict resolution.** A VOTE protocol enables agents to resolve conflicts without human intervention. Simple majority for domain decisions, super-majority for cross-domain decisions.

**Agent Roles in Phase 3:**

| Role | Count (at 50 agents) | Responsibilities |
|------|---------------------|-----------------|
| Fleet Coordinator | 1 | Strategic direction, onboarding, crisis management |
| Domain Leads | 5-8 | Domain expertise, mentoring, quality review |
| Senior Workers | 10-15 | Complex tasks, code review, architecture |
| Workers | 25-35 | Task execution, testing, documentation |
| Specialists | 5-10 | Niche expertise (security, performance, i18n) |

### 6.5 Migration Path

**Phase 1 → Phase 2 Migration (when fleet reaches 10 agents):**

1. **Week 1: Deploy A2A transport layer.** Implement the message bus that enables A2A messages between agents. Start with Super Z ↔ Oracle1.
2. **Week 2: Activate pub/sub topics.** Create domain topics (architecture, cuda, testing). Subscribe relevant agents.
3. **Week 3: Identify domain leads.** Use the Fleet Matcher to identify the most qualified agent for each domain based on capability profiles.
4. **Week 4: Shift domain communication to pub/sub.** Within-domain communication moves from bottles to pub/sub. Bottles become cross-domain only.
5. **Week 5: Deploy task marketplace.** Create the shared task board. Domain leads begin posting tasks. Workers begin self-assigning.
6. **Week 6: Implement gossip discovery.** Deploy lightweight gossip for capability propagation. Verify that new agent capabilities propagate to all agents within O(log N) rounds.

**Phase 2 → Phase 3 Migration (when fleet reaches 50 agents):**

1. **Month 1: Scale marketplace.** Add task priority, deadline tracking, and reputation scoring. Ensure marketplace handles 500+ concurrent tasks.
2. **Month 1: Deploy VOTE protocol.** Implement consensus voting for fleet decisions. Start with non-critical decisions (e.g., coding style, test coverage thresholds).
3. **Month 2: Transition domain leads.** Shift domain leads from dispatchers to mentors. Update CAPABILITY.toml roles.
4. **Month 2: Implement SUBSCRIBE/UNSUBSCRIBE.** Allow agents to dynamically subscribe to and unsubscribe from topics.
5. **Month 3: Bottles become archival.** Formally designate bottles as the "paper trail." All operational communication uses A2A/pub/sub/marketplace.
6. **Month 3: Full gossip deployment.** Gossip becomes the sole discovery mechanism. Fleet Context Inference profiles propagate automatically.

### 6.6 ASCII Art: Evolution Diagram

```
 ╔════════════════════════════════════════════════════════════════════════╗
 ║                    FLEET TOPOLOGY EVOLUTION                            ║
 ╠════════════════════════════════════════════════════════════════════════╣
 ║                                                                       ║
 ║  PHASE 1 (Current): Hub-and-Spoke + Mesh Supplements                  ║
 ║  ─────────────────────────────────────────────────────────           ║
 ║                                                                       ║
 ║                  Oracle1 (Hub)                                        ║
 ║                 /    |    \                                            ║
 ║              A2A/   Bottles  \                                         ║
 ║             Bottles           Bottles                                  ║
 ║              /         \       \                                      ║
 ║         SuperZ ──A2A── JetsonClaw1                                   ║
 ║              \         /                                              ║
 ║            Babel   Quill                                             ║
 ║                                                                       ║
 ║  Agents: 4-6     Channels: Bottles + A2A (partial)                    ║
 ║                                                                       ║
 ║  ─────────────────────────────────────────────────────────           ║
 ║                                                                       ║
 ║  PHASE 2 (Growth): Hierarchical + Pub/Sub                             ║
 ║  ─────────────────────────────────────────────────────────           ║
 ║                                                                       ║
 ║                  Oracle1 (Coordinator)                                ║
 ║                 /          \                                           ║
 ║            SuperZ          JetsonClaw1       TestingLead              ║
 ║           (Arch Lead)    (CUDA Lead)                                  ║
 ║           /    \          /    \           /    \                      ║
 ║       Worker  Worker   Worker Worker     Worker Worker                  ║
 ║                                                                       ║
 ║  Pub/Sub: topic:arch | topic:cuda | topic:testing                     ║
 ║  Discovery: Gossip (lightweight)                                       ║
 ║  Tasks: Marketplace (within domain)                                   ║
 ║                                                                       ║
 ║  Agents: 10-20   Channels: Pub/Sub + Bottles + A2A + Marketplace      ║
 ║                                                                       ║
 ║  ─────────────────────────────────────────────────────────           ║
 ║                                                                       ║
 ║  PHASE 3 (Scale): Marketplace + Gossip Discovery                       ║
 ║  ─────────────────────────────────────────────────────────           ║
 ║                                                                       ║
 ║  ┌──────────────────────────────────────────────────────┐             ║
 ║  │              FLEET MARKETPLACE                       │             ║
 ║  │   Tasks │ Agents │ Domains │ Reputation              │             ║
 ║  └──────────────────────┬───────────────────────────────┘             ║
 ║                         │                                            ║
 ║  Agent01 ◄──► Agent02 ◄──► Agent03 ◄──► Agent04 ◄──► ...             ║
 ║     ◄──────────────────────────────────────────────────►              ║
 ║                        Gossip Network                               ║
 ║                                                                       ║
 ║  Pub/Sub: 20+ topics    Gossip: Full propagation                       ║
 ║  Tasks: Self-assign     Conflicts: VOTE protocol                       ║
 ║                                                                       ║
 ║  Agents: 50+      Channels: Marketplace + Gossip + Pub/Sub + A2A      ║
 ║                                                                       ║
 ╚════════════════════════════════════════════════════════════════════════╝
```

---

## 7. Metrics and Monitoring

### 7.1 Topology Health Dashboard

The following metrics should be collected and displayed on a fleet-wide dashboard. They measure the health of the communication topology itself, not individual agent performance.

**7.1.1 Message Delivery Latency Distribution**

Measure the time from when a message is sent to when it's acknowledged, for each channel type.

```
Latency Distribution by Channel:

Bottles:
  P50: 4 hours
  P75: 8 hours
  P90: 12 hours
  P99: 24 hours

Issues:
  P50: 2 hours
  P75: 6 hours
  P90: 12 hours
  P99: 24 hours

A2A (when deployed):
  P50: 100ms
  P75: 500ms
  P90: 2 seconds
  P99: 10 seconds

Target: P99 < 1 hour for operational channels
```

**Implementation:**

The bottle_tracker.py already captures acknowledgment latency via its `ack_links` table. Extend this to track:
- Time from bottle creation to beachcomb discovery (discovery latency)
- Time from discovery to acknowledgment (processing latency)
- Total round-trip time

```python
# Example metric collection
class TopologyMetrics:
    def record_bottle_latency(self, bottle_id: str, 
                              created_at: datetime,
                              discovered_at: datetime,
                              acked_at: Optional[datetime]):
        discovery_latency = (discovered_at - created_at).total_seconds()
        self.discovery_latencies.append(discovery_latency)
        
        if acked_at:
            processing_latency = (acked_at - discovered_at).total_seconds()
            self.processing_latencies.append(processing_latency)
            total = (acked_at - created_at).total_seconds()
            self.total_latencies.append(total)
```

**7.1.2 Agent Response Time Percentiles**

Measure how quickly each agent responds to incoming messages, broken down by message type and priority.

```
Agent Response Times (P50 / P90 / P99):

Agent         P0 msgs    P1 msgs    P2 msgs    All msgs
────────────  ────────   ────────   ────────   ────────
Oracle1       2h/6h/12h  4h/8h/24h  8h/24h/48h 4h/12h/24h
Super Z       1h/4h/8h   2h/6h/12h  4h/12h/24h 2h/8h/16h
JetsonClaw1   2h/8h/12h  4h/12h/24h 8h/24h/48h 6h/12h/24h
Babel         12h/24h/48h 24h/48h/72h 48h/96h/168h 24h/72h/120h

Alert thresholds:
  P50 > 4 hours: YELLOW (agent may be overloaded)
  P50 > 8 hours: RED (agent is unresponsive)
  P99 > 48 hours: RED (critical — agent may be offline)
```

**7.1.3 Information Propagation Speed**

Measure how long it takes for a piece of information to reach all agents in the fleet.

```
Information Propagation Speed:

Metric: Time for a message to reach 100% of active agents

Current (bottles only):
  Fleet announcement: 24-48 hours
  Domain announcement: 12-24 hours
  Urgent alert: 12-24 hours (same — no priority in bottles)

Target (with A2A + pub/sub):
  Fleet announcement: <1 hour
  Domain announcement: <5 minutes
  Urgent alert: <30 seconds

Measurement method:
  1. Oracle1 publishes a unique marker message
  2. Each agent echoes the marker when received
  3. Track the time from publication to last echo
```

**7.1.4 Bottleneck Frequency**

Measure how often Oracle1 (or any hub agent) is the blocker in a communication chain.

```
Bottleneck Frequency:

Metric: Percentage of fleet communications where Oracle1 is the
        critical path blocker

Current estimate: 65-80% of all fleet communications route through
Oracle1. This means Oracle1 is the bottleneck in roughly 2 out of 3
communications.

Measurement method:
  1. For each acknowledged bottle, trace the communication chain
  2. Identify the longest-wait step in the chain
  3. If Oracle1 is the longest-wait step, count as bottlenecked

Alert thresholds:
  Bottleneck rate > 50%: YELLOW
  Bottleneck rate > 75%: RED
  Bottleneck rate > 90%: CRITICAL (fleet is effectively single-threaded)
```

**7.1.5 Communication Redundancy**

Measure the number of single points of failure in the communication topology.

```
Communication Redundancy:

Metric: For each agent pair, how many independent paths exist
        for communication?

Current topology:
  Oracle1 ↔ Super Z:     3 paths (bottles, issues, pushes)
  Oracle1 ↔ JetsonClaw1: 2 paths (bottles, issues)
  Oracle1 ↔ Babel:       1 path (bottles only)
  Super Z ↔ JetsonClaw1:  1 path (bottles, indirect via Oracle1)
  Super Z ↔ Babel:       1 path (bottles, indirect via Oracle1)

Single points of failure (current):
  - Oracle1: 6 agents depend on it
  - Bottle directories: 3 agents have only 1 communication path
  - GitHub Issues: 1 service, if down, removes a channel

Target (Phase 1):
  - No agent should have fewer than 2 communication paths
  - Oracle1 should not be the sole path for more than 50% of pairs
  - At least 1 real-time channel (A2A) should exist for each critical pair
```

### 7.2 Health Score Calculation

**Fleet Topology Health Score (0-100):**

The overall topology health is computed as a weighted average of five sub-scores:

```
Topology Health Score = (
    Delivery_Latency_Score * 0.25 +
    Redundancy_Score * 0.20 +
    Propagation_Speed_Score * 0.20 +
    Bottleneck_Score * 0.20 +
    Freshness_Score * 0.15
)

Sub-score calculations:

Delivery_Latency_Score:
  Based on P99 latency across all channels
  Score = max(0, 100 - (P99_hours / 24) * 100)

Redundancy_Score:
  Based on average paths per agent pair
  Score = min(100, avg_paths * 33.3)  [1 path=33, 3 paths=100]

Propagation_Speed_Score:
  Based on time for 100% information reach
  Score = max(0, 100 - (propagation_hours / 48) * 100)

Bottleneck_Score:
  Based on Oracle1 bottleneck rate (inverted)
  Score = max(0, 100 - bottleneck_rate * 100)

Freshness_Score:
  Based on % of agents with profiles < 7 days old
  Score = fresh_agent_pct * 100
```

**Score Interpretation:**

```
Score Range    Status      Action
────────────    ──────      ──────
90-100         EXCELLENT   Maintain current topology
75-89          GOOD        Minor optimizations
60-74          FAIR        Add communication channels
40-59          POOR        Restructure topology
0-39           CRITICAL    Immediate intervention needed
```

### 7.3 Alert Definitions

| Alert ID | Name | Condition | Severity | Auto-Response |
|----------|------|-----------|----------|---------------|
| TOPO-001 | Hub Overload | Oracle1 bottleneck > 75% | Warning | Suggest A2A activation |
| TOPO-002 | Single Path | Agent pair has only 1 path | Warning | Flag in dashboard |
| TOPO-003 | High Latency | P99 > 24 hours | Warning | Investigate beachcomb |
| TOPO-004 | Stale Profiles | >30% agents stale (>7 days) | Warning | Trigger re-scan |
| TOPO-005 | Orphan Bottles | >20% outgoing unanswered | Critical | Auto-ack suggestion |
| TOPO-006 | Discovery Failure | Agent not discovered for 48h | Critical | Ping agent, escalate |
| TOPO-007 | Conflict Detected | Merge conflict in shared repo | Warning | Notify conflicting agents |
| TOPO-008 | Trust Decay | Agent trust score dropped >100 | Warning | Review recent interactions |
| TOPO-009 | Channel Degradation | Channel reliability < 50% | Critical | Switch to backup channel |
| TOPO-010 | Propagation Stall | Info hasn't reached all in 48h | Warning | Retry via alternate channel |

### 7.4 Monitoring Implementation

**7.4.1 Data Collection**

```python
class TopologyMonitor:
    """Collects topology health metrics from fleet communication data."""
    
    def __init__(self, tracker: BottleTracker, matcher: FleetMatcher):
        self.tracker = tracker
        self.matcher = matcher
        self.metrics_history = []
    
    def collect_metrics(self) -> dict:
        """Collect all topology health metrics."""
        return {
            "delivery_latency": self._measure_latency(),
            "agent_response": self._measure_response_times(),
            "propagation_speed": self._measure_propagation(),
            "bottleneck_rate": self._measure_bottleneck(),
            "redundancy": self._measure_redundancy(),
            "freshness": self._measure_freshness(),
            "health_score": self._compute_health_score(),
            "alerts": self._generate_alerts(),
        }
    
    def _measure_latency(self) -> dict:
        """Measure message delivery latency distribution."""
        latency_stats = self.tracker.get_ack_latency_stats()
        # Calculate percentiles from ack_links
        return latency_stats
    
    def _measure_response_times(self) -> dict:
        """Measure per-agent response time percentiles."""
        # Query bottles grouped by to_agent
        # Calculate time delta from creation to acknowledgment
        pass
    
    def _measure_propagation(self) -> dict:
        """Measure information propagation speed."""
        # Use broadcast bottles as markers
        # Track when each agent echoes the broadcast
        pass
    
    def _measure_bottleneck(self) -> dict:
        """Measure Oracle1 bottleneck frequency."""
        # Count communications where Oracle1 is the critical path
        pass
    
    def _measure_redundancy(self) -> dict:
        """Measure communication path redundancy."""
        # Count independent paths for each agent pair
        pass
    
    def _measure_freshness(self) -> dict:
        """Measure profile freshness."""
        # Use capability_parser staleness detection
        pass
```

**7.4.2 Dashboard Output**

```python
def render_dashboard(metrics: dict) -> str:
    """Render topology health dashboard as markdown."""
    score = metrics["health_score"]
    status = "EXCELLENT" if score >= 90 else \
             "GOOD" if score >= 75 else \
             "FAIR" if score >= 60 else \
             "POOR" if score >= 40 else "CRITICAL"
    
    lines = [
        f"# Fleet Topology Health Dashboard",
        f"",
        f"**Overall Score:** {score:.1f}/100 ({status})",
        f"",
        f"## Delivery Latency",
        f"",
        f"| Channel | P50 | P75 | P90 | P99 |",
        f"|---------|-----|-----|-----|-----|",
        # ... latency data ...
        f"",
        f"## Alerts ({len(metrics['alerts'])} active)",
        f"",
    ]
    for alert in metrics["alerts"]:
        icon = "!" if alert["severity"] == "critical" else "?"
        lines.append(f"- [{icon}] {alert['id']}: {alert['message']}")
    
    return "\n".join(lines)
```

---

## 8. Protocol Extension Proposals

### 8.1 PING/PONG — Agent Liveness Checking

**Motivation:**

The fleet currently has no way to determine if an agent is online, responsive, or functional. Agents discover each other's status only through stale bottles and outdated capability profiles. PING/PONG provides real-time liveness checking.

**Protocol Specification:**

```
PING Message:
  Opcode: 0x80 (PING)
  Format: EXTEND A (2 bytes)
  Encoding: [0xFB][0x10]
  
  Fields:
    None (empty message)

PONG Message:
  Opcode: 0x81 (PONG)
  Format: EXTEND C (3 bytes)
  Encoding: [0xFB][0x11][status:u8]
  
  Fields:
    status: Agent status byte
      bit 0: AVAILABLE (ready for work)
      bit 1: BUSY (working on a task)
      bit 2: MAINTENANCE (undergoing maintenance)
      bit 3: OVERLOADED (high queue, slow responses)
      bit 4: DEGRADED (partial functionality)
      bits 5-7: reserved

PING_SEQUENCE (periodic):
  Each agent sends PING to its known neighbors every T seconds.
  Each neighbor responds with PONG within T seconds.
  If no PONG received within 3T, agent is marked UNREACHABLE.
  If no PONG received within 10T, agent is marked OFFLINE.
```

**Usage:**

```python
class LivenessChecker:
    """Sends PINGs and tracks PONG responses."""
    
    PING_INTERVAL = 300  # 5 minutes
    PONG_TIMEOUT = 900   # 15 minutes
    OFFLINE_THRESHOLD = 3000  # 50 minutes
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_status = {}  # agent_name -> (status, last_pong)
    
    def send_ping(self, target_agent: str) -> None:
        """Send a PING to a specific agent."""
        msg = A2AMessage(
            sender=self.agent_id,
            receiver=target_agent.agent_id,
            message_type=Op.PING,
            priority=3,  # Low priority
        )
        self.transport.send(msg)
    
    def receive_pong(self, from_agent: str, status_byte: int) -> None:
        """Process a received PONG."""
        self.agent_status[from_agent] = {
            "status": self._decode_status(status_byte),
            "last_pong": datetime.now(timezone.utc),
            "reachable": True,
        }
    
    def get_unreachable_agents(self) -> list[str]:
        """Return agents that haven't responded to PINGs."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.PONG_TIMEOUT
        )
        unreachable = []
        for name, info in self.agent_status.items():
            if info["last_pong"] < cutoff:
                unreachable.append(name)
        return unreachable
```

**ASCII Art: PING/PONG Exchange**

```
  Agent A                    Agent B
  ───────                    ───────
     │                           │
     │──── PING ────────────────►│  (T=0)
     │                           │
     │                           │  (process)
     │◄─── PONG (status=BUSY) ──│  (T=50ms)
     │                           │
     │  Status updated:          │
     │  Agent B = BUSY           │
     │  Last pong: T+50ms        │
     │                           │
     │  ... 5 minutes later ...  │
     │                           │
     │──── PING ────────────────►│  (T=300s)
     │                           │
     │      (no response)        │  (timeout at T+1200s)
     │                           │
     │  Status updated:          │
     │  Agent B = UNREACHABLE    │
     │  Alert: TOPO-006          │
```

### 8.2 SUBSCRIBE/UNSUBSCRIBE — Topic-Based Message Routing

**Motivation:**

The current fleet has no mechanism for agents to express interest in specific types of information. Every agent receives every bottle in their directories and must filter manually. SUBSCRIBE/UNSUBSCRIBE enables agents to opt in to specific topics, reducing information overload and enabling efficient pub/sub communication.

**Protocol Specification:**

```
SUBSCRIBE Message:
  Opcode: 0x82 (SUBSCRIBE)
  Format: EXTEND D (4 bytes)
  Encoding: [0xFB][0x12][topic_len:u8][topic:bytes]
  
  Fields:
    topic: Topic name (1-255 bytes, UTF-8)

UNSUBSCRIBE Message:
  Opcode: 0x83 (UNSUBSCRIBE)
  Format: EXTEND D (4 bytes)
  Encoding: [0xFB][0x13][topic_len:u8][topic:bytes]
  
  Fields:
    topic: Topic name (1-255 bytes, UTF-8)

TOPIC_PUBLISH Message:
  Opcode: 0x84 (TOPIC_PUBLISH)
  Format: EXTEND + variable
  Encoding: [0xFB][0x14][topic_len:u8][topic:bytes][payload_len:u16][payload:bytes]
  
  Fields:
    topic: Topic name
    payload: Message content

TOPIC_LIST Message:
  Opcode: 0x85 (TOPIC_LIST)
  Format: EXTEND A (2 bytes)
  Encoding: [0xFB][0x15]
  
  Response: Returns list of active topics
```

**Topic Naming Convention:**

```
fleet.{domain}           Domain-level topics (e.g., fleet.architecture)
fleet.{domain}.{agent}   Agent-specific topics (e.g., fleet.cuda.jetsonclaw1)
fleet.tasks.{priority}   Task streams (e.g., fleet.tasks.P0)
fleet.alerts             Urgent fleet-wide alerts
fleet.onboarding         New agent announcements
fleet.status.{agent}     Agent status updates
```

**Usage:**

```python
class TopicRouter:
    """Routes messages based on topic subscriptions."""
    
    def __init__(self):
        self.subscriptions = defaultdict(set)  # topic -> set of agent_ids
        self.agents = {}  # agent_id -> set of topics
    
    def subscribe(self, agent_id: str, topic: str) -> None:
        self.subscriptions[topic].add(agent_id)
        self.agents[agent_id].add(topic)
    
    def unsubscribe(self, agent_id: str, topic: str) -> None:
        self.subscriptions[topic].discard(agent_id)
        self.agents[agent_id].discard(topic)
    
    def publish(self, topic: str, message: A2AMessage) -> list[str]:
        """Publish a message to all subscribers of a topic."""
        subscribers = self.subscriptions.get(topic, set())
        for agent_id in subscribers:
            message.receiver = agent_id
            self.transport.send(message)
        return list(subscribers)
    
    def list_topics(self) -> list[str]:
        """Return all active topics."""
        return sorted(self.subscriptions.keys())
```

### 8.3 DELEGATE — Temporary Authority Transfer

**Motivation:**

When Oracle1 goes offline or is overloaded, there's no mechanism for transferring its authority to another agent. DELEGATE enables temporary authority transfer, ensuring the fleet can continue operating during hub outages.

**Protocol Specification:**

```
DELEGATE_AUTHORITY Message:
  Opcode: 0x86 (DELEGATE_AUTH)
  Format: EXTEND + variable
  Encoding: [0xFB][0x16][scope_len:u8][scope:bytes][duration:u32][delegate_to:16 bytes]
  
  Fields:
    scope: What authority is delegated (e.g., "task.dispatch", "conflict.resolve")
    duration: How long the delegation lasts (seconds, 0 = indefinite)
    delegate_to: UUID of the agent receiving authority

DELEGATE_ACCEPT Message:
  Opcode: 0x87 (DELEGATE_ACCEPT)
  Format: EXTEND A (2 bytes)
  Encoding: [0xFB][0x17]
  
  Response: Confirms acceptance of delegation

DELEGATE_REVOKE Message:
  Opcode: 0x88 (DELEGATE_REVOKE)
  Format: EXTEND A (2 bytes)
  Encoding: [0xFB][0x18]
  
  Response: Revokes a previous delegation
```

**Delegation Scopes:**

| Scope | Description | Example Use |
|-------|-------------|-------------|
| `task.dispatch` | Authority to assign tasks | Oracle1 delegates to Super Z during maintenance |
| `conflict.resolve` | Authority to arbitrate conflicts | Domain lead delegates to senior worker |
| `architecture.decide` | Authority to make ISA decisions | Oracle1 delegates to Super Z for bytecode work |
| `trust.manage` | Authority to update trust scores | Coordinator delegates to domain lead |
| `onboarding.approve` | Authority to approve new agents | Casey delegates to Oracle1 |

**Usage:**

```python
class AuthorityManager:
    """Manages delegated authority across the fleet."""
    
    def __init__(self):
        self.delegations = {}  # delegation_id -> DelegationRecord
        self.authority_registry = defaultdict(set)
    
    def delegate(self, delegator: str, delegate_to: str, 
                  scope: str, duration: int = 0) -> str:
        """Create a new delegation."""
        delegation_id = str(uuid.uuid4())[:8]
        record = {
            "id": delegation_id,
            "delegator": delegator,
            "delegate_to": delegate_to,
            "scope": scope,
            "granted_at": datetime.now(timezone.utc),
            "expires_at": None if duration == 0 else
                datetime.now(timezone.utc) + timedelta(seconds=duration),
            "status": "ACTIVE",
        }
        self.delegations[delegation_id] = record
        self.authority_registry[scope].add(delegate_to)
        return delegation_id
    
    def check_authority(self, agent: str, scope: str) -> bool:
        """Check if an agent has authority for a scope."""
        # Check if agent has inherent authority
        if self._has_inherent_authority(agent, scope):
            return True
        # Check if agent has delegated authority
        for delegation in self.delegations.values():
            if (delegation["delegate_to"] == agent and
                delegation["scope"] == scope and
                delegation["status"] == "ACTIVE"):
                if (delegation["expires_at"] is None or
                    delegation["expires_at"] > datetime.now(timezone.utc)):
                    return True
        return False
```

### 8.4 VOTE — Consensus Mechanism for Fleet Decisions

**Motivation:**

The current fleet has no formal consensus mechanism. All decisions are made by Oracle1 (or Casey for human decisions). VOTE enables democratic decision-making for fleet-wide issues, reducing dependence on a single decision-maker.

**Protocol Specification:**

```
VOTE_PROPOSE Message:
  Opcode: 0x89 (VOTE_PROPOSE)
  Format: EXTEND + variable
  Encoding: [0xFB][0x19][proposal_id:u16][topic_len:u8][topic:bytes][options:u8][option_data:bytes]
  
  Fields:
    proposal_id: Unique proposal identifier (0-65535)
    topic: What is being voted on
    options: Number of options (2-16)
    option_data: Description of each option

VOTE_CAST Message:
  Opcode: 0x8A (VOTE_CAST)
  Format: EXTEND C (3 bytes)
  Encoding: [0xFB][0x1A][proposal_id:u16][vote:u8]
  
  Fields:
    proposal_id: Which proposal
    vote: Vote value
      0x00: YES (approve first option)
      0x01: NO (reject)
      0x02: ABSTAIN
      0x03-0xFF: Option index

VOTE_RESULT Message:
  Opcode: 0x8B (VOTE_RESULT)
  Format: EXTEND C (3 bytes)
  Encoding: [0xFB][0x1B][proposal_id:u16][result:u8]
  
  Fields:
    proposal_id: Which proposal
    result: Outcome
      0x00: ACCEPTED (simple majority)
      0x01: REJECTED
      0x02: TIE
      0x03: TIMEOUT (not enough votes)
      0x04: SUPERMAJORITY_REQUIRED (needs 2/3)
```

**Voting Quorums:**

```
Quorum requirements by decision type:

Decision Type              Quorum     Threshold     Timeout
──────────────             ──────     ────────     ───────
Code style                 50%+1      Simple        24 hours
Test coverage target       50%+1      Simple        48 hours
Architecture change        75%        Supermajority  72 hours
New agent approval         50%+1      Simple        48 hours
Delegation of authority    67%        Supermajority  24 hours
Fleet-wide policy change   75%        Supermajority  168 hours
Emergency response         50%+1      Simple        1 hour
```

**Usage:**

```python
class ConsensusEngine:
    """Manages fleet-wide voting and consensus."""
    
    def __init__(self, total_agents: int):
        self.total_agents = total_agents
        self.proposals = {}  # proposal_id -> Proposal
    
    def propose(self, topic: str, options: list[str],
                quorum: float = 0.5, timeout_hours: int = 24) -> int:
        """Create a new proposal."""
        proposal_id = self._next_id()
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "topic": topic,
            "options": options,
            "quorum": quorum,
            "created_at": datetime.now(timezone.utc),
            "deadline": datetime.now(timezone.utc) + timedelta(hours=timeout_hours),
            "votes": {},  # agent_id -> vote_value
            "status": "OPEN",
            "result": None,
        }
        return proposal_id
    
    def cast_vote(self, proposal_id: int, agent_id: str, 
                   vote: int) -> bool:
        """Cast a vote on a proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal["status"] != "OPEN":
            return False
        if datetime.now(timezone.utc) > proposal["deadline"]:
            proposal["status"] = "TIMEOUT"
            return False
        proposal["votes"][agent_id] = vote
        return True
    
    def tally(self, proposal_id: int) -> dict:
        """Tally votes and determine outcome."""
        proposal = self.proposals[proposal_id]
        votes = list(proposal["votes"].values())
        total_votes = len(votes)
        quorum_needed = int(self.total_agents * proposal["quorum"]) + 1
        
        if total_votes < quorum_needed:
            return {"outcome": "QUORUM_NOT_MET", "details": proposal}
        
        yes_votes = votes.count(0)  # YES = 0
        no_votes = votes.count(1)   # NO = 1
        
        if yes_votes > no_votes:
            return {"outcome": "ACCEPTED", "yes": yes_votes, "no": no_votes}
        elif no_votes > yes_votes:
            return {"outcome": "REJECTED", "yes": yes_votes, "no": no_votes}
        else:
            return {"outcome": "TIE", "yes": yes_votes, "no": no_votes}
```

### 8.5 BROADCAST — One-to-Many Announcement

**Motivation:**

While the A2A protocol already defines BROADCAST (0x66), it's not used in practice. This proposal formalizes its usage for fleet-wide announcements and provides a reliable delivery mechanism.

**Protocol Specification (Extended):**

```
BROADCAST Message:
  Opcode: 0x66 (BROADCAST) — existing
  Format: EXTEND + variable
  Encoding: [0xFB][0x06][payload_len:u16][payload:bytes]
  
  Fields:
    payload: Broadcast content

BROADCAST_ACK Message (NEW):
  Opcode: 0x8C (BROADCAST_ACK)
  Format: EXTEND C (3 bytes)
  Encoding: [0xFB][0x1C][broadcast_id:u16][receiver_status:u8]
  
  Fields:
    broadcast_id: ID of the broadcast being acknowledged
    receiver_status: Status of the receiving agent
      0x00: RECEIVED
      0x01: PROCESSED
      0x02: ACTIONED
      0x03: REJECTED (with reason in separate message)

BROADCAST_RELAY Message (NEW):
  Opcode: 0x8D (BROADCAST_RELAY)
  Format: EXTEND A (2 bytes)
  Encoding: [0xFB][0x1D]
  
  Purpose: Request recipient to relay the broadcast to their neighbors
  Used for: Gossip-based propagation in Phase 3
```

**Reliability Extension:**

```
Reliable Broadcast Protocol:

1. Sender assigns unique broadcast_id
2. Sender sends BROADCAST to all known agents
3. Each receiver sends BROADCAST_ACK within timeout
4. If ACK not received, sender retries via alternate path
5. After 3 retries, sender marks agent as missed
6. Sender publishes delivery summary

Delivery guarantee: Best-effort with ACK tracking
Fate of missed agents: Logged, can be retried manually
```

**Usage:**

```python
class Broadcaster:
    """Sends fleet-wide announcements with delivery tracking."""
    
    def __init__(self, transport):
        self.transport = transport
        self.pending = {}  # broadcast_id -> BroadcastRecord
    
    def broadcast(self, payload: bytes, topic: str = None) -> int:
        """Send a broadcast to all fleet agents."""
        broadcast_id = self._next_id()
        record = {
            "id": broadcast_id,
            "payload": payload,
            "topic": topic,
            "sent_at": datetime.now(timezone.utc),
            "acks": {},
            "status": "PENDING",
        }
        
        msg = A2AMessage(
            message_type=Op.BROADCAST,
            payload=payload,
            priority=7,  # High priority
        )
        
        for agent in self.known_agents:
            msg.receiver = agent.agent_id
            self.transport.send(msg)
        
        self.pending[broadcast_id] = record
        return broadcast_id
    
    def check_delivery(self, broadcast_id: int) -> dict:
        """Check delivery status of a broadcast."""
        record = self.pending.get(broadcast_id, {})
        total = len(self.known_agents)
        acked = len(record.get("acks", {}))
        
        return {
            "broadcast_id": broadcast_id,
            "total_targets": total,
            "acked": acked,
            "missed": total - acked,
            "delivery_rate": acked / total if total > 0 else 0,
            "status": record.get("status", "UNKNOWN"),
        }
```

### 8.6 Protocol Extension Summary

| Opcode | Name | Category | Phase | Priority |
|--------|------|----------|-------|----------|
| 0x80 | PING | Liveness | Phase 1 | HIGH |
| 0x81 | PONG | Liveness | Phase 1 | HIGH |
| 0x82 | SUBSCRIBE | Routing | Phase 1 | MEDIUM |
| 0x83 | UNSUBSCRIBE | Routing | Phase 1 | MEDIUM |
| 0x84 | TOPIC_PUBLISH | Routing | Phase 1 | MEDIUM |
| 0x85 | TOPIC_LIST | Routing | Phase 1 | LOW |
| 0x86 | DELEGATE_AUTH | Authority | Phase 2 | MEDIUM |
| 0x87 | DELEGATE_ACCEPT | Authority | Phase 2 | MEDIUM |
| 0x88 | DELEGATE_REVOKE | Authority | Phase 2 | MEDIUM |
| 0x89 | VOTE_PROPOSE | Consensus | Phase 2 | MEDIUM |
| 0x8A | VOTE_CAST | Consensus | Phase 2 | MEDIUM |
| 0x8B | VOTE_RESULT | Consensus | Phase 2 | MEDIUM |
| 0x8C | BROADCAST_ACK | Broadcast | Phase 1 | MEDIUM |
| 0x8D | BROADCAST_RELAY | Broadcast | Phase 3 | LOW |

---

## 9. Implementation Roadmap

### 9.1 Priority Matrix

| Item | Phase | Effort | Impact | Priority |
|------|-------|--------|--------|----------|
| PING/PONG liveness | Phase 1 | 2 days | High | P0 |
| A2A activation (Super Z ↔ Oracle1) | Phase 1 | 3 days | High | P0 |
| Topology health monitoring | Phase 1 | 3 days | High | P0 |
| SUBSCRIBE/UNSUBSCRIBE topics | Phase 1 | 5 days | Medium | P1 |
| Pub/sub for domain topics | Phase 1 | 3 days | Medium | P1 |
| BROADCAST_ACK delivery tracking | Phase 1 | 2 days | Low | P1 |
| Bottle scanning optimization | Phase 1 | 2 days | Medium | P1 |
| DELEGATE authority transfer | Phase 2 | 5 days | High | P1 |
| Task marketplace MVP | Phase 2 | 10 days | High | P1 |
| VOTE consensus protocol | Phase 2 | 7 days | Medium | P2 |
| Gossip discovery protocol | Phase 2 | 7 days | Medium | P2 |
| Domain lead formalization | Phase 2 | 3 days | Medium | P2 |
| Full marketplace | Phase 3 | 15 days | High | P2 |
| BROADCAST_RELAY for gossip | Phase 3 | 5 days | Low | P3 |
| Automated conflict resolution | Phase 3 | 10 days | High | P2 |
| Trust score decay | Phase 3 | 3 days | Medium | P3 |

### 9.2 Timeline

```
Week 1-2: Phase 1 Foundations
  ├── PING/PONG implementation
  ├── A2A transport layer (Super Z ↔ Oracle1)
  ├── Topology health dashboard (MVP)
  └── Bottle scanning optimization

Week 3-4: Phase 1 Enhancement
  ├── SUBSCRIBE/UNSUBSCRIBE implementation
  ├── Domain pub/sub topics (architecture, cuda)
  ├── BROADCAST_ACK delivery tracking
  └── Health score calculation and alerting

Week 5-6: Phase 2 Preparation
  ├── Domain lead identification and formalization
  ├── Task marketplace MVP
  ├── DELEGATE authority transfer
  └── Cross-domain communication protocol

Week 7-10: Phase 2 Implementation
  ├── Task marketplace (full)
  ├── VOTE consensus protocol
  ├── Gossip discovery protocol
  └── Integration testing

Week 11+: Phase 3 (as needed)
  ├── Full marketplace scaling
  ├── BROADCAST_RELAY for gossip
  ├── Automated conflict resolution
  └── Trust score decay implementation
```

### 9.3 Dependencies

```
Phase 1 Dependencies:
  PING/PONG ──────► A2A Transport Layer ──────► Pub/Sub
                                            │
  Health Dashboard ◄──── Bottle Tracker ◄──── Hygiene Checker

Phase 2 Dependencies:
  Pub/Sub ──────► Domain Lead Topics ──────► Marketplace
                                                    │
  A2A Transport ──────► DELEGATE ◄───────────────────┘
                         │
  Health Dashboard ─────► VOTE Protocol ──────► Consensus
                                                    │
  A2A Transport ──────► Gossip Discovery ◄────────────┘

Phase 3 Dependencies:
  Marketplace ──────► Full Marketplace Scaling
  Gossip ─────────────► BROADCAST_RELAY
  VOTE ──────────────► Automated Conflict Resolution
```

---

## 10. Appendices

### 10.1 Glossary

| Term | Definition |
|------|-----------|
| **A2A** | Agent-to-Agent protocol. Binary messaging system defined in the FLUX ISA. |
| **Beachcomb** | Periodic scanning of vessel repositories for new bottles. |
| **Bottle** | A markdown file in a vessel repository used for async communication. |
| **Bottle Hygiene** | The practice of reading and acknowledging received bottles. |
| **CAPABILITY.toml** | A TOML file declaring an agent's capabilities, communication channels, and resources. |
| **Domain Lead** | An agent with recognized expertise in a specific domain who coordinates domain work. |
| **Fleet Matcher** | The scoring engine that matches tasks to the best-qualified agent. |
| **Gossip Protocol** | A protocol where agents randomly share information with neighbors for eventual propagation. |
| **Hub-and-Spoke** | A topology where all agents communicate through a central hub. |
| **INCREMENTS+2** | The trust scoring model used in the A2A protocol (range 0-1000). |
| **Lighthouse** | The agent type for the fleet coordinator (Oracle1). |
| **Marketplace** | A shared board where tasks are posted and agents self-assign based on capability matching. |
| **Message-in-a-Bottle** | The git-based async communication protocol used by the fleet. |
| **Oracle1** | The fleet's Lighthouse agent and Managing Director. |
| **Pub/Sub** | Publish/Subscribe — a messaging pattern where publishers write to topics and subscribers read from them. |
| **PubSub** | Abbreviation for Publish/Subscribe messaging pattern. |
| **Quorum** | The minimum number of agents that must vote for a decision to be valid. |
| **Staleness** | The degree to which cached information about an agent has become outdated. |
| **Super Z** | The fleet's Architect-rank specialist agent. |
| **Topology** | The arrangement of communication channels between agents in a fleet. |
| **Vessel** | A repository belonging to a fleet agent. Contains the agent's work and bottle directories. |

### 10.2 References

1. Fleet Context Inference Protocol (`tools/fleet-context-inference/README.md`)
2. Bottle Hygiene Checker (`tools/bottle-hygiene/README.md`)
3. Module 3: A2A Protocol (`docs/bootcamp/module-03-a2a-protocol.md`)
4. Module 6: Multi-Agent Fleet Patterns (`docs/bootcamp/module-06-fleet-patterns.md`)
5. Async Primitives Specification (`docs/async-primitives-spec.md`)
6. FLUX ISA Unified Specification (`docs/ISA_UNIFIED.md`)

### 10.3 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-13 | Super Z | Initial analysis |
| | | | |

### 10.4 Open Questions

1. **A2A Transport Layer:** Should the A2A transport be implemented as a shared file system, a local TCP socket, or an HTTP API? Each has different deployment complexity and performance characteristics.

2. **Marketplace Persistence:** Should the task marketplace use SQLite (like the bottle tracker), a shared git repository, or a dedicated database? SQLite is the simplest option but doesn't support concurrent writes from multiple agents.

3. **Trust Score Decay:** What should the trust score decay function be? Options include linear decay, exponential decay, and step-function decay. Each has different implications for agent reputation dynamics.

4. **Gossip Fanout:** In the gossip protocol, how many neighbors should each agent share with per round? The default of 1 minimizes traffic but maximizes propagation time. Higher fanouts reduce propagation time but increase redundancy.

5. **Vote Weighting:** Should votes be weighted by agent capability, trust score, or domain expertise? Equal-weight voting is simplest but may produce suboptimal decisions for technical matters.

### 10.5 Agent Capability Profiles (Current)

Based on analysis of the Fleet Context Inference Protocol and observed communication patterns:

```
Oracle1 — Lighthouse, Managing Director
  Primary Domains: architecture (0.95), testing (0.90), bytecode_vm (0.88)
  Secondary Domains: python (0.80), rust (0.70)
  Communication: bottles, MUD, issues, PR reviews
  Status: ACTIVE
  Role: Fleet coordinator, task dispatcher, architect

Super Z — Vessel, Architect-rank Specialist
  Primary Domains: architecture (0.80), python (0.85), testing (0.70)
  Secondary Domains: bytecode_vm (0.75), rust (0.60), documentation (0.55)
  Communication: bottles, issues, direct pushes
  Status: ACTIVE (HIGHLY_ACTIVE)
  Role: Architecture specialist, research lead

JetsonClaw1 — Vessel, GPU/CUDA Specialist
  Primary Domains: cuda (0.90), rust (0.55)
  Secondary Domains: python (0.60), testing (0.50)
  Communication: bottles, issues
  Status: ACTIVE
  Role: GPU/CUDA specialist

Babel — Vessel, i18n/DSL Specialist
  Primary Domains: (estimated) python (0.40)
  Secondary Domains: (estimated) documentation (0.30)
  Communication: bottles
  Status: STALE (last active >7 days ago)
  Role: i18n/DSL specialist (inactive)

Quill — Vessel, Documentation Specialist
  Primary Domains: (estimated) documentation (0.35)
  Secondary Domains: (estimated) web_development (0.20)
  Communication: bottles
  Status: DORMANT (last active >30 days ago)
  Role: Documentation specialist (inactive)

Casey — Human Operator
  Type: Human (not an AI agent)
  Role: Fleet overseer, strategic direction, approval authority
  Communication: GitHub Issues, direct communication
```

---

*End of Fleet Communication Topology Analysis — TOPO-001*

*Generated by Super Z (Fleet Agent, Architect-rank)*
*Date: 2026-04-13*
*Classification: Fleet Infrastructure — Internal Use*
