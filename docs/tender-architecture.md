# Tender Architecture — TokenSteward Module Design

**Document ID:** TENDER-ARCH-001  
**Author:** Super Z (FLUX Fleet — Cartographer)  
**Date:** 2026-04-13  
**Status:** DRAFT — Requires fleet review and Oracle1 approval  
**Version:** 1.0.0-draft  
**Depends on:** ISA v3 spec (A2A signaling), fleet-config.json, capabilities.py, resource_limits.py  
**Tracks:** TASK-BOARD "Tender Architecture — Token Steward Design" (MEDIUM)  
**Repo:** `SuperInstance/tender`  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Three-Tier Resource Architecture](#2-three-tier-resource-architecture)
3. [TokenSteward Module Design](#3-tokensteward-module-design)
4. [Agent Wallet Model](#4-agent-wallet-model)
5. [Bidding & Escrow System](#5-bidding--escrow-system)
6. [Token Categories](#6-token-categories)
7. [Fleet Economics Model](#7-fleet-economics-model)
8. [Integration Points](#8-integration-points)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Appendix A — Data Model Schemas](#appendix-a--data-model-schemas)
11. [Appendix B — Cross-References](#appendix-b--cross-references)

---

## 1. Executive Summary

A multi-agent fleet of 6+ autonomous agents — Oracle1, Super Z, Quill, JetsonClaw1, Babel, Fleet Mechanic, and growing — consumes shared finite resources: LLM API tokens, image generation credits, web search quotas, GPU compute minutes, and storage. Without a central resource management layer, the fleet faces the classic **tragedy of the commons**: agents individually optimize for their own tasks while collectively depleting the shared budget. One agent executing a brute-force code generation loop can exhaust the week's token allocation, leaving critical fleet-wide tasks (ISA convergence audits, cross-fleet coordination, emergency hotfixes) unfunded.

**Tender** is the fleet-tier resource steward — the top of the three-tier keeper hierarchy:

```
Brothers Keeper (per-machine) → Lighthouse Keeper (per-region) → Tender (fleet-wide)
```

Tender's core module is **TokenSteward**, a budget-aware allocation engine that assigns, tracks, and enforces API token budgets across the fleet. It implements a market-based resource economy where agents bid on shared token pools for high-value tasks, earn credit through responsible usage, and can escalate budget requests when justified. This document specifies the TokenSteward architecture: its data model (wallets, pools, bids), its economic policies (allocation formulas, credit scoring, debt/repayment), its integration with the FLUX ISA (A2A SIGNAL opcodes for budget requests, capability-gated access via existing `CapabilityToken` infrastructure), and its phased implementation roadmap.

The economic problem is not hypothetical. The fleet already has 733 repositories, 30+ open tasks, and multiple agents executing LLM calls concurrently. JetsonClaw1's edge deployments consume GPU minutes at different rates than Babel's linguistic processing. Super Z's ISA work requires sustained LLM sessions while Fleet Mechanic's auto-fix operations need burst capacity. TokenSteward brings fairness, accountability, and sustainability to this ecosystem.

---

## 2. Three-Tier Resource Architecture

### 2.1 Overview

The keeper hierarchy mirrors the fleet's operational topology. Each tier has a single responsibility, and each tier feeds summary data upward while receiving policy directives downward.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      TENDER (Fleet-Wide)                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  TokenSteward                                                │   │
│  │  • Fleet-level token budgets (weekly sprints)                │   │
│  │  • Cross-agent allocation & rebalancing                     │   │
│  │  • Market-based bidding for shared pools                    │   │
│  │  • Credit scoring & debt tracking                           │   │
│  │  • Forecasting & spend projection                           │   │
│  │  • Emergency reserve management                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ▲ ▼                                    │
├──────────────────────────────────────────────────────────────────────┤
│                   LIGHTHOUSE KEEPER (Region)                        │
│  • Per-region health & quota monitoring                             │
│  • Aggregates Brothers Keeper reports into regional summaries       │
│  • Detects regional hotspots (one machine exhausting its share)     │
│  • Reports regional spend to Tender, receives fleet-wide policies   │
│  • Manages regional emergency reserves                              │
│                              ▲ ▼                                    │
├──────────────────────────────────────────────────────────────────────┤
│                   BROTHERS KEEPER (Machine)                         │
│  • Per-machine monitoring (GPU, CPU, memory, network)              │
│  • Process watchdog (detect stuck/dead agents)                     │
│  • Local rate limiting (tokens per second, requests per minute)    │
│  • Consumes from existing `ResourceMonitor` (64MB mem, 10M cycles)│
│  • Reports machine-level telemetry to Lighthouse Keeper            │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Tier Responsibilities

| Tier | Scope | Updates | Data Flow | Existing Code |
|------|-------|---------|-----------|---------------|
| **Brothers Keeper** | Single machine | Millisecond | → Lighthouse | `ResourceLimits`, `ResourceMonitor` |
| **Lighthouse Keeper** | Single region | Seconds | → Tender | Needs build (KEEP-001 task) |
| **Tender** | Entire fleet | Sprint (weekly) | ← Oracle1 | This document (TokenSteward) |

### 2.3 Tender as Protocol, Not Just Agent

Following Oracle1's reverse-ideation insight, Tender is designed as a **protocol** first and an **agent** second. The TokenSteward module exposes a well-defined API (allocate, consume, bid, audit) that any fleet agent can invoke via A2A SIGNAL opcodes. This means:

- Any agent can *query* the steward without permission
- Any agent can *consume* from its own wallet
- Only agents with `A2A_DELEGATE` capability can *allocate* budgets to others
- The steward itself can run as a dedicated barnacle-type agent OR as a library embedded in the runtime

The protocol-first design means the steward survives even if the tender agent goes down — any lighthouse keeper can step in and replay the steward's state from the audit log.

### 2.4 Relationship to Existing Cost Infrastructure

The fleet already has two cost models:

1. **`CostModel`** (`cost/model.py`): FIR-level static analysis — estimates nanoseconds per instruction using memory hierarchy and branch prediction models. Operates at the bytecode level before execution.
2. **`EnergyModel`** (`cost/energy.py`): Extends CostModel with nanojoule energy estimates and carbon footprint calculations per function execution.

TokenSteward operates at a **higher abstraction level**: it manages *API token budgets*, not CPU cycles. However, the three systems form a cost stack:

```
EnergyModel (nanojoules) → CostModel (nanoseconds) → ResourceMonitor (cycles/mem) → TokenSteward (API tokens)
```

TokenSteward does not replace CostModel or EnergyModel — it sits above them as the financial accounting layer.

---

## 3. TokenSteward Module Design

### 3.1 Core Interface

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime, timedelta
import time
import uuid
import hashlib


class BudgetPeriod(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    SPRINT = "sprint"        # ~2 weeks
    MONTHLY = "monthly"


class TokenCategory(Enum):
    LLM_CHAT = "llm_chat"          # 1K tokens
    LLM_COMPLETION = "llm_completion"  # 1K tokens
    IMAGE_GEN = "image_gen"        # per image
    WEB_SEARCH = "web_search"      # per query
    COMPUTE_GPU = "compute_gpu"    # per minute
    COMPUTE_CPU = "compute_cpu"    # per minute
    STORAGE = "storage"            # per GB/day
    BANDWIDTH = "bandwidth"        # per MB


class EscalationStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    PARTIAL = "partial"


class BidStatus(Enum):
    OPEN = "open"
    MATCHED = "matched"
    SETTLED = "settled"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    CRITICAL = 5       # ISA convergence, security patches
    HIGH = 4           # Active fences, cross-fleet coordination
    MEDIUM = 3         # Normal task board items
    LOW = 2            # Nice-to-have improvements
    BACKGROUND = 1     # Research, exploration


# ─── Data Models ───────────────────────────────────────────────

@dataclass(frozen=True)
class Receipt:
    """Proof of token consumption. Immutable."""
    receipt_id: str
    agent_id: str
    category: TokenCategory
    amount: int               # tokens consumed
    reason: str               # human-readable justification
    timestamp: float          # epoch seconds
    task_id: Optional[str]    # associated task (e.g., "fence-0x42")
    balance_after: int        # wallet balance after consumption


@dataclass
class AgentWallet:
    """Per-agent token wallet with balance, limits, and history."""
    agent_id: str
    balance: int = 0
    rate_limit: int = 10000           # tokens per hour
    daily_quota: int = 50000          # max tokens per day
    weekly_quota: int = 200000        # max tokens per week
    credit_score: float = 0.80        # 0.0 (pariah) to 1.0 (trusted)
    debt: int = 0                     # tokens borrowed from emergency pool
    interest_rate: float = 0.10       # 10% interest on debt
    history: list[Receipt] = field(default_factory=list)
    hourly_usage: dict[int, int] = field(default_factory=dict)  # hour -> tokens

    @property
    def available(self) -> int:
        """Effective balance after subtracting debt."""
        return max(0, self.balance - self.debt)

    @property
    def credit_tier(self) -> str:
        """Map credit score to tier name."""
        if self.credit_score >= 0.90:
            return "platinum"
        elif self.credit_score >= 0.75:
            return "gold"
        elif self.credit_score >= 0.60:
            return "silver"
        elif self.credit_score >= 0.40:
            return "bronze"
        return "restricted"

    def record_consumption(self, receipt: Receipt) -> None:
        """Log consumption and update hourly tracking."""
        self.history.append(receipt)
        hour = int(time.time()) // 3600
        self.hourly_usage[hour] = self.hourly_usage.get(hour, 0) + receipt.amount
        # Trim history to last 1000 entries
        if len(self.history) > 1000:
            self.history = self.history[-1000:]


@dataclass
class TokenPool:
    """Shared token pool for competitive allocation."""
    pool_id: str
    name: str                     # e.g., "fleet-research", "emergency", "isa-convergence"
    total_tokens: int = 1_000_000
    allocated_tokens: int = 0
    available_tokens: int = 1_000_000
    price_per_token: float = 1.0  # base price (market-adjusted)
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    min_bid: float = 0.5
    purpose: str = ""             # what this pool is for

    @property
    def utilization(self) -> float:
        """Fraction of pool allocated (0.0 to 1.0+)."""
        if self.total_tokens == 0:
            return 0.0
        return self.allocated_tokens / self.total_tokens

    @property
    def market_price(self) -> float:
        """Dynamic price based on utilization (demand-based pricing)."""
        if self.utilization < 0.5:
            return self.price_per_token * 0.8  # discount when abundant
        elif self.utilization < 0.8:
            return self.price_per_token  # base price
        elif self.utilization < 0.95:
            return self.price_per_token * 1.5  # premium when scarce
        return self.price_per_token * 3.0  # crisis pricing


@dataclass
class Budget:
    """Budget allocation result."""
    budget_id: str
    agent_id: str
    amount: int
    period: BudgetPeriod
    allocated_at: float
    expires_at: float
    source_pool: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM


@dataclass
class Bid:
    """Competitive bid on a token pool."""
    bid_id: str
    agent_id: str
    pool_id: str
    amount: int               # tokens requested
    max_price: float          # maximum price willing to pay
    priority: TaskPriority
    justification: str
    task_id: Optional[str] = None
    status: BidStatus = BidStatus.OPEN
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at if self.expires_at > 0 else False


@dataclass
class Settlement:
    """Result of bid settlement."""
    bid_id: str
    agent_id: str
    pool_id: str
    tokens_granted: int
    price_paid: float
    settled_at: float = field(default_factory=time.time)


@dataclass
class EscalationRequest:
    """Request for additional tokens beyond normal allocation."""
    request_id: str
    agent_id: str
    amount_requested: int
    justification: str
    task_id: Optional[str] = None
    priority: TaskPriority = TaskPriority.HIGH
    status: EscalationStatus = EscalationStatus.PENDING
    amount_granted: int = 0
    reviewed_by: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0


@dataclass
class AuditReport:
    """Fleet-wide token usage audit."""
    timestamp: float
    total_budget: int
    total_consumed: int
    total_in_escrow: int
    total_debt: int
    agent_summaries: list[dict] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    pool_summaries: list[dict] = field(default_factory=list)


@dataclass
class ForecastReport:
    """Predicted token usage and burn rate."""
    timestamp: float
    current_burn_rate: float           # tokens per hour (7-day average)
    projected_weekly_spend: int
    projected_monthly_spend: int
    days_until_exhaustion: float
    risk_level: str                    # "green", "yellow", "red"
    recommendations: list[str] = field(default_factory=list)
    top_consumers: list[tuple[str, int]] = field(default_factory=list)


# ─── TokenSteward Core ─────────────────────────────────────────

class TokenSteward:
    """Fleet-wide token budget manager — the Tender's financial brain.

    Manages API token budgets across the fleet with:
    - Per-agent wallets with balance, rate limits, and credit scores
    - Shared token pools with market-based pricing
    - Competitive bidding for scarce resources
    - Debt/credit system with interest
    - Full audit trail and forecasting
    """

    def __init__(self, fleet_config: dict) -> None:
        self.agents: dict[str, AgentWallet] = {}
        self.pools: dict[str, TokenPool] = {}
        self.bids: list[Bid] = []
        self.escalations: list[EscalationRequest] = []
        self.budgets: dict[str, Budget] = {}
        self.settlements: list[Settlement] = []
        self._emergency_reserve_ratio: float = 0.10  # 10% held back

        self._initialize_from_config(fleet_config)

    def _initialize_from_config(self, config: dict) -> None:
        """Create wallets and pools from fleet configuration."""
        # Create default fleet pool
        default_pool = TokenPool(
            pool_id="fleet-default",
            name="Fleet Default Pool",
            total_tokens=config.get("fleet_token_budget", 5_000_000),
            purpose="General fleet operations"
        )
        default_pool.available_tokens = default_pool.total_tokens
        self.pools["fleet-default"] = default_pool

        # Create emergency reserve pool
        emergency_tokens = int(
            default_pool.total_tokens * self._emergency_reserve_ratio
        )
        emergency_pool = TokenPool(
            pool_id="emergency",
            name="Emergency Reserve",
            total_tokens=emergency_tokens,
            purpose="Critical tasks, security patches, ISA convergence blockers"
        )
        emergency_pool.available_tokens = emergency_tokens
        self.pools["emergency"] = emergency_pool

        # Deduct emergency from default
        default_pool.available_tokens -= emergency_tokens

        # Create agent wallets
        agent_defaults = config.get("agents", {})
        for agent_id, agent_cfg in agent_defaults.items():
            wallet = AgentWallet(
                agent_id=agent_id,
                balance=0,
                rate_limit=agent_cfg.get("rate_limit", 10000),
                daily_quota=agent_cfg.get("daily_quota", 50000),
                weekly_quota=agent_cfg.get("weekly_quota", 200000),
                credit_score=agent_cfg.get("credit_score", 0.80),
            )
            self.agents[agent_id] = wallet

    def allocate_budget(
        self,
        agent_id: str,
        amount: int,
        period: BudgetPeriod,
        priority: TaskPriority = TaskPriority.MEDIUM,
        source_pool: str = "fleet-default",
    ) -> Budget:
        """Allocate tokens from a pool to an agent's wallet.

        Requires A2A_DELEGATE capability (caller must be an allocator).
        """
        now = time.time()
        pool = self.pools.get(source_pool)

        if not pool:
            raise ValueError(f"Unknown pool: {source_pool}")

        # Check pool availability
        if pool.available_tokens < amount:
            raise ValueError(
                f"Pool '{source_pool}' has insufficient tokens: "
                f"requested {amount}, available {pool.available_tokens}"
            )

        # Create budget record
        expires_map = {
            BudgetPeriod.HOURLY: now + 3600,
            BudgetPeriod.DAILY: now + 86400,
            BudgetPeriod.WEEKLY: now + 604800,
            BudgetPeriod.SPRINT: now + 1_209_600,
            BudgetPeriod.MONTHLY: now + 2_592_000,
        }
        budget = Budget(
            budget_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            amount=amount,
            period=period,
            allocated_at=now,
            expires_at=expires_map.get(period, now + 604800),
            source_pool=source_pool,
            priority=priority,
        )
        self.budgets[budget.budget_id] = budget

        # Credit agent wallet
        wallet = self._get_or_create_wallet(agent_id)
        wallet.balance += amount

        # Debit pool
        pool.available_tokens -= amount
        pool.allocated_tokens += amount

        return budget

    def consume(
        self,
        agent_id: str,
        amount: int,
        reason: str,
        category: TokenCategory = TokenCategory.LLM_CHAT,
        task_id: Optional[str] = None,
    ) -> Receipt:
        """Record token consumption from an agent's wallet.

        This is the hot path — called on every API call.
        """
        wallet = self.agents.get(agent_id)
        if not wallet:
            raise ValueError(f"No wallet for agent: {agent_id}")

        # Check balance
        if wallet.balance < amount:
            # Try emergency pool if agent has HIGH+ priority task
            raise ValueError(
                f"Agent '{agent_id}' insufficient balance: "
                f"need {amount}, have {wallet.balance}"
            )

        # Check rate limit (tokens per hour)
        current_hour = int(time.time()) // 3600
        hourly_spend = wallet.hourly_usage.get(current_hour, 0)
        if hourly_spend + amount > wallet.rate_limit:
            raise ValueError(
                f"Agent '{agent_id}' rate limit exceeded: "
                f"hourly spend {hourly_spend + amount} > limit {wallet.rate_limit}"
            )

        # Debit wallet
        wallet.balance -= amount

        # Generate receipt
        receipt = Receipt(
            receipt_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            category=category,
            amount=amount,
            reason=reason,
            timestamp=time.time(),
            task_id=task_id,
            balance_after=wallet.balance,
        )

        # Record in wallet history
        wallet.record_consumption(receipt)

        return receipt

    def request_escalation(
        self,
        agent_id: str,
        amount: int,
        justification: str,
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.HIGH,
    ) -> EscalationRequest:
        """Request additional tokens beyond normal allocation.

        Escalations are reviewed by the fleet allocator (Oracle1 or
        delegated agent). Emergency pool is used for approved requests.
        """
        request = EscalationRequest(
            request_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            amount_requested=amount,
            justification=justification,
            task_id=task_id,
            priority=priority,
        )
        self.escalations.append(request)
        return request

    def resolve_escalation(
        self,
        request_id: str,
        status: EscalationStatus,
        amount_granted: int = 0,
        reviewed_by: Optional[str] = None,
    ) -> EscalationRequest:
        """Approve or deny an escalation request."""
        for req in self.escalations:
            if req.request_id == request_id:
                req.status = status
                req.amount_granted = amount_granted
                req.reviewed_by = reviewed_by
                req.resolved_at = time.time()

                if status == EscalationStatus.APPROVED and amount_granted > 0:
                    emergency_pool = self.pools.get("emergency")
                    if emergency_pool and emergency_pool.available_tokens >= amount_granted:
                        wallet = self.agents.get(req.agent_id)
                        if wallet:
                            wallet.balance += amount_granted
                            wallet.debt += int(amount_granted * wallet.interest_rate)
                            emergency_pool.available_tokens -= amount_granted
                    elif status == EscalationStatus.APPROVED:
                        # Partial approval
                        req.amount_granted = emergency_pool.available_tokens
                        req.status = EscalationStatus.PARTIAL
                        wallet = self.agents.get(req.agent_id)
                        if wallet and emergency_pool.available_tokens > 0:
                            wallet.balance += emergency_pool.available_tokens
                            wallet.debt += int(
                                emergency_pool.available_tokens * wallet.interest_rate
                            )
                            emergency_pool.available_tokens = 0

                return req

        raise ValueError(f"Unknown escalation request: {request_id}")

    def place_bid(
        self,
        agent_id: str,
        pool_id: str,
        amount: int,
        max_price: float,
        priority: TaskPriority = TaskPriority.MEDIUM,
        justification: str = "",
        task_id: Optional[str] = None,
        ttl_seconds: float = 3600.0,
    ) -> Bid:
        """Place a competitive bid on a shared token pool."""
        pool = self.pools.get(pool_id)
        if not pool:
            raise ValueError(f"Unknown pool: {pool_id}")

        bid = Bid(
            bid_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            pool_id=pool_id,
            amount=amount,
            max_price=max_price,
            priority=priority,
            justification=justification,
            task_id=task_id,
            expires_at=time.time() + ttl_seconds,
        )
        self.bids.append(bid)
        return bid

    def settle_bids(self) -> list[Settlement]:
        """Match open bids against pool availability.

        Settlement algorithm:
        1. Sort bids by priority (highest first), then by max_price (descending)
        2. For each bid, check if pool market_price <= bid.max_price
        3. If match, grant tokens at market price
        4. Deduct from pool, credit agent wallet
        5. Stop when pool is exhausted or all bids processed
        """
        settlements: list[Settlement] = []

        # Filter to open, non-expired bids
        active_bids = [
            b for b in self.bids
            if b.status == BidStatus.OPEN and not b.is_expired()
        ]

        # Sort by priority desc, then max_price desc
        active_bids.sort(
            key=lambda b: (b.priority.value, b.max_price),
            reverse=True
        )

        # Group by pool
        pool_bids: dict[str, list[Bid]] = {}
        for bid in active_bids:
            pool_bids.setdefault(bid.pool_id, []).append(bid)

        # Settle each pool independently
        for pool_id, bids in pool_bids.items():
            pool = self.pools.get(pool_id)
            if not pool:
                continue

            for bid in bids:
                if pool.available_tokens <= 0:
                    break

                price = pool.market_price
                if price > bid.max_price:
                    continue  # bidder won't pay current market price

                # Grant tokens (or partial if pool is low)
                granted = min(bid.amount, pool.available_tokens)
                actual_price = price  # could add volume discount

                # Execute settlement
                settlement = Settlement(
                    bid_id=bid.bid_id,
                    agent_id=bid.agent_id,
                    pool_id=pool_id,
                    tokens_granted=granted,
                    price_paid=actual_price,
                )
                settlements.append(settlement)
                self.settlements.append(settlement)

                # Update pool
                pool.available_tokens -= granted
                pool.allocated_tokens += granted

                # Credit wallet
                wallet = self._get_or_create_wallet(bid.agent_id)
                wallet.balance += granted

                # Mark bid
                bid.status = BidStatus.MATCHED

        return settlements

    def audit(self) -> AuditReport:
        """Generate comprehensive fleet audit report."""
        now = time.time()
        total_budget = sum(p.total_tokens for p in self.pools.values())
        total_allocated = sum(p.allocated_tokens for p in self.pools.values())
        total_available = sum(p.available_tokens for p in self.pools.values())
        total_debt = sum(w.debt for w in self.agents.values())

        # Agent summaries
        agent_summaries = []
        for agent_id, wallet in self.agents.items():
            week_ago = now - 604800
            weekly_spend = sum(
                r.amount for r in wallet.history if r.timestamp > week_ago
            )
            agent_summaries.append({
                "agent_id": agent_id,
                "balance": wallet.balance,
                "debt": wallet.debt,
                "credit_score": wallet.credit_score,
                "credit_tier": wallet.credit_tier,
                "weekly_spend": weekly_spend,
                "weekly_quota": wallet.weekly_quota,
                "utilization": weekly_spend / wallet.weekly_quota if wallet.weekly_quota > 0 else 0.0,
            })

        # Anomaly detection
        anomalies = []
        for summary in agent_summaries:
            if summary["utilization"] > 0.95:
                anomalies.append(
                    f"⚠ {summary['agent_id']} at {summary['utilization']*100:.0f}% quota"
                )
            if summary["debt"] > 0:
                anomalies.append(
                    f"💰 {summary['agent_id']} has {summary['debt']} tokens in debt"
                )
            if summary["credit_score"] < 0.50:
                anomalies.append(
                    f"🔻 {summary['agent_id']} credit score low: {summary['credit_score']:.2f}"
                )

        # Pool summaries
        pool_summaries = [
            {
                "pool_id": p.pool_id,
                "name": p.name,
                "utilization": p.utilization,
                "available": p.available_tokens,
                "market_price": p.market_price,
            }
            for p in self.pools.values()
        ]

        return AuditReport(
            timestamp=now,
            total_budget=total_budget,
            total_consumed=total_allocated - total_available,
            total_in_escrow=0,  # filled by escrow integration
            total_debt=total_debt,
            agent_summaries=agent_summaries,
            anomalies=anomalies,
            pool_summaries=pool_summaries,
        )

    def get_forecast(self) -> ForecastReport:
        """Predict token usage trends and exhaustion timeline."""
        now = time.time()
        week_ago = now - 604800

        # Calculate burn rate from last 7 days
        total_weekly_spend = 0
        agent_hourly: dict[str, list[int]] = {}

        for agent_id, wallet in self.agents.items():
            weekly = sum(
                r.amount for r in wallet.history if r.timestamp > week_ago
            )
            total_weekly_spend += weekly
            # Per-agent hourly rates for top consumer detection
            agent_hourly[agent_id] = list(wallet.hourly_usage.values())

        burn_rate = total_weekly_spend / 168.0  # tokens per hour (7-day avg)

        total_available = sum(p.available_tokens for p in self.pools.values())
        days_until_exhaustion = (
            total_available / burn_rate if burn_rate > 0 else float('inf')
        )

        # Risk assessment
        if days_until_exhaustion > 14:
            risk_level = "green"
        elif days_until_exhaustion > 7:
            risk_level = "yellow"
        else:
            risk_level = "red"

        # Top consumers
        consumer_totals = {}
        for agent_id, wallet in self.agents.items():
            consumer_totals[agent_id] = sum(
                r.amount for r in wallet.history if r.timestamp > week_ago
            )
        top_consumers = sorted(
            consumer_totals.items(), key=lambda x: x[1], reverse=True
        )[:5]

        # Recommendations
        recommendations = []
        if risk_level == "red":
            recommendations.append("URGENT: Fleet budget projected to exhaust within 7 days")
            recommendations.append("Consider reducing non-critical task allocations")
        if risk_level in ("yellow", "red"):
            recommendations.append("Enable competitive bidding for all non-critical pools")
        for agent_id, spend in top_consumers:
            wallet = self.agents[agent_id]
            if wallet.weekly_quota > 0 and spend / wallet.weekly_quota > 0.8:
                recommendations.append(
                    f"{agent_id} approaching quota ({spend/wallet.weekly_quota*100:.0f}%)"
                )

        return ForecastReport(
            timestamp=now,
            current_burn_rate=burn_rate,
            projected_weekly_spend=total_weekly_spend,
            projected_monthly_spend=int(total_weekly_spend * 4.33),
            days_until_exhaustion=days_until_exhaustion,
            risk_level=risk_level,
            recommendations=recommendations,
            top_consumers=top_consumers,
        )

    def _get_or_create_wallet(self, agent_id: str) -> AgentWallet:
        """Get existing wallet or create default."""
        if agent_id not in self.agents:
            self.agents[agent_id] = AgentWallet(agent_id=agent_id)
        return self.agents[agent_id]
```

### 3.2 Key Design Decisions

1. **Receipts are immutable** — every consumption generates a `Receipt` (frozen dataclass) that cannot be tampered with. This provides a complete audit trail.

2. **Credit score decays and recovers** — agents that consistently stay under budget see their score rise, unlocking higher rate limits and better bidding terms. Agents that exceed budgets see their score decay.

3. **Emergency pool is ring-fenced** — 10% of fleet budget is held in a separate pool that requires escalation review. This prevents any single task from consuming the entire budget.

4. **Market-based pricing on pools** — as utilization increases, price increases (0.8x to 3.0x base). This creates natural pressure to bid early and conserve.

5. **Debt carries interest** — agents that borrow from the emergency pool repay with 10% interest, creating economic pressure to use escalation sparingly.

---

## 4. Agent Wallet Model

### 4.1 Wallet Lifecycle

```
┌──────────┐  register()   ┌──────────┐  allocate()   ┌──────────┐
│  NONE    │──────────────▶│  EMPTY   │──────────────▶│  FUNDED  │
└──────────┘               └──────────┘               └──────────┘
                                                             │
                                    consume() until 0        │
                               ┌────────────────────────────┘
                               ▼
                         ┌──────────┐
                         │ DEPLETED │──request_escalation()──▶┌──────────┐
                         └──────────┘                         │ REVIEW  │
                               ▲                              └──────────┘
                               │                    ┌──approve──┘
                               │                    │
                               │  replenish()       │──deny──▶ ┌──────────┐
                               └────────────────────┘          │ DEBT    │
                                                            └──────────┘
```

### 4.2 Credit Score Algorithm

Credit score is updated on every sprint boundary (weekly):

```
credit_score = base_score + efficiency_bonus - waste_penalty + repayment_bonus

Where:
  base_score = 0.50
  efficiency_bonus = min(0.30, (quota - spent) / quota * 0.30)
                     Reward for staying under budget (up to +0.30)
  waste_penalty   = max(0.0, (spent - quota) / quota * 0.20)
                     Penalty for exceeding budget (up to -0.20... in theory
                     but consume() blocks over-quota, so this hits via escalation debt)
  repayment_bonus = min(0.10, debt_repaid / debt_incurred * 0.10)
                     Reward for paying back emergency loans
```

### 4.3 Credit Tiers and Privileges

| Tier | Score Range | Rate Limit Multiplier | Bid Priority Boost | Max Debt |
|------|-------------|----------------------|--------------------|----------| 
| **Platinum** | 0.90–1.00 | 1.5x | +2 | 50,000 |
| **Gold** | 0.75–0.89 | 1.2x | +1 | 25,000 |
| **Silver** | 0.60–0.74 | 1.0x | 0 | 10,000 |
| **Bronze** | 0.40–0.59 | 0.8x | -1 | 5,000 |
| **Restricted** | 0.00–0.39 | 0.5x | -2 | 1,000 |

### 4.4 Rate Limiting

Rate limits are enforced per-hour using a sliding window:

```python
def check_rate_limit(self, wallet: AgentWallet, amount: int) -> bool:
    current_hour = int(time.time()) // 3600
    hourly_spend = wallet.hourly_usage.get(current_hour, 0)
    effective_limit = int(wallet.rate_limit * self._tier_multiplier(wallet))
    return (hourly_spend + amount) <= effective_limit
```

When an agent hits its rate limit, the steward returns a `429 Too Many Requests`-equivalent with a `Retry-After` header calculated from when the current hour window expires.

---

## 5. Bidding & Escrow System

### 5.1 Bid Lifecycle

```
place_bid() → OPEN → settle_bids() → MATCHED → confirm_delivery() → SETTLED
                  │                          │
                  └── expires ──▶ EXPIRED    └── pool empty ──▶ PARTIAL
                       │
                       └── cancel_bid() ──▶ CANCELLED
```

### 5.2 Escrow Flow

For high-value tasks, tokens are held in escrow until the task completes:

```
1. Agent places bid on pool → tokens reserved in escrow
2. Bid is matched → tokens moved from pool to escrow account
3. Agent begins task → escrow tokens locked
4a. Task completes successfully → escrow tokens consumed (receipts generated)
4b. Task fails → escrow tokens returned to pool (minus 5% transaction fee)
4c. Task partially completes → proportional settlement
```

### 5.3 Settlement Algorithm Detail

The settlement runs on a timer (every 5 minutes) or on-demand:

1. **Collect** all open, non-expired bids
2. **Group** by pool (each pool settles independently)
3. **Sort** within each pool: priority DESC, max_price DESC, created_at ASC
4. **Match** greedily:
   - For each bid, compute `pool.market_price`
   - If `market_price <= bid.max_price`: MATCH
   - If `market_price > bid.max_price`: SKIP (bidder can't afford current price)
   - If `pool.available_tokens < bid.amount`: PARTIAL MATCH (grant what's available)
5. **Execute**: credit wallets, debit pools, generate settlements
6. **Notify**: send A2A SIGNAL to winning bidders with settlement details

### 5.4 Transaction Fees

| Operation | Fee | Destination |
|-----------|-----|-------------|
| Failed task escrow return | 5% of escrowed amount | Pool (replenishment) |
| Debt interest | 10% of borrowed amount | Emergency pool |
| Early bid cancellation | 2% of bid amount | Pool (replenishment) |
| Pool-to-pool transfer | 1% of transferred amount | Fleet maintenance |

---

## 6. Token Categories

### 6.1 Category Definitions

| Category | Unit | Typical Cost (USD) | Conversion to Standard Tokens | Notes |
|----------|------|--------------------|-------------------------------|-------|
| **LLM Chat (input)** | 1K tokens | $0.01–0.03 | 10 tokens | Prompt tokens for chat completion |
| **LLM Chat (output)** | 1K tokens | $0.02–0.06 | 20 tokens | Generated response tokens |
| **LLM Completion** | 1K tokens | $0.02–0.05 | 15 tokens | Non-chat completion |
| **Image Gen** | per image | $0.02–0.10 | 50 tokens | DALL-E, Stable Diffusion, etc. |
| **Web Search** | per query | $0.001–0.005 | 3 tokens | Tavily, SerpAPI, Bing |
| **Compute (GPU)** | per minute | $0.01–0.05 | 30 tokens/min | Jetson Orin, A100 |
| **Compute (CPU)** | per minute | $0.001–0.005 | 5 tokens/min | Standard cloud compute |
| **Storage** | per GB/day | $0.001 | 3 tokens/GB/day | S3, GCS, local |
| **Bandwidth** | per MB | $0.0001 | 1 token/MB | Network transfer |

### 6.2 Standard Token Unit

All categories are normalized to a single "standard token" unit for cross-category comparison and budgeting. The conversion rates above are approximate and configurable per deployment. The standard token is the **budget atom** — all wallets, pools, and bids operate in standard tokens.

### 6.3 Category-Specific Limits

Some categories have additional constraints beyond the wallet balance:

```python
@dataclass
class CategoryLimits:
    """Per-category consumption limits."""
    llm_daily_max: int = 100_000       # 100K LLM tokens per day
    image_daily_max: int = 50          # 50 images per day
    search_daily_max: int = 200        # 200 web searches per day
    gpu_weekly_max: int = 1_000        # 1,000 GPU-minutes per week
```

---

## 7. Fleet Economics Model

### 7.1 Sprint Budget Cycle

The fleet operates on weekly sprints. At the start of each sprint:

1. **Oracle1** sets the fleet-wide token budget (or inherits from Captain Casey)
2. **TokenSteward** splits the budget: 10% emergency, 90% operational
3. **Allocation formula** distributes operational budget to agents
4. **Bidding opens** for shared pools
5. **Agents consume** tokens via `consume()` calls
6. **Settlement runs** every 5 minutes to clear bid queues
7. **Audit runs** daily; **forecast** runs on sprint boundaries
8. **Credit scores** updated at sprint end
9. **Debt reconciliation** at sprint end (interest applied)

### 7.2 Fair Allocation Formula

Base allocation per agent per sprint:

```
base_allocation = (fleet_budget * 0.90) / num_agents
```

Performance bonus (added to base):

```
performance_bonus = base_allocation * (credit_score - 0.50) * 0.50
```

This means:
- An agent with credit_score=0.80 (Gold) gets base + 15% bonus
- An agent with credit_score=1.00 (Platinum) gets base + 25% bonus
- An agent with credit_score=0.40 (Bronze) gets base - 5% penalty
- An agent with credit_score=0.50 gets exactly the base allocation

### 7.3 Debt/Repayment System

When an agent's task is critical but its wallet is depleted:

1. Agent submits `request_escalation()` with justification
2. Oracle1 (or delegated allocator) reviews and approves/denies
3. If approved, tokens are drawn from the emergency pool
4. The agent's wallet is credited, but `debt` is increased by 110% (10% interest)
5. At sprint end, debt is reconciled against next sprint's allocation
6. If debt exceeds 3x weekly quota, the agent's rate limit is halved until debt is repaid

### 7.4 Emergency Reserve Policy

The emergency reserve (10% of fleet budget) is only accessible via:

- **Manual approval** by Oracle1 or Captain Casey
- **Automatic trigger**: any task marked CRITICAL priority with an active ISA convergence fence
- **Security exception**: any response to fleet security issues (#15, #16, #17 type issues)

### 7.5 Cross-Pool Rebalancing

If one pool is at 95%+ utilization while another is below 30%, the steward can automatically transfer tokens:

```python
def rebalance_pools(self) -> list[dict]:
    """Move tokens from low-utilization pools to high-utilization pools."""
    transfers = []
    pools = list(self.pools.values())

    for src in pools:
        if src.pool_id == "emergency":
            continue  # never drain emergency
        if src.utilization < 0.30:
            excess = int((0.30 - src.utilization) * src.total_tokens)

            for dst in pools:
                if dst.utilization > 0.95 and dst.available_tokens < excess:
                    transfer_amount = min(excess, int(excess * 0.10))
                    # Execute transfer with 1% fee
                    fee = max(1, transfer_amount // 100)
                    src.available_tokens -= transfer_amount
                    dst.available_tokens += transfer_amount - fee
                    transfers.append({
                        "from": src.pool_id,
                        "to": dst.pool_id,
                        "amount": transfer_amount,
                        "fee": fee,
                    })
                    excess -= transfer_amount

    return transfers
```

---

## 8. Integration Points

### 8.1 A2A SIGNAL Opcode Integration

The FLUX ISA v3 provides A2A signaling opcodes (0x50–0x5F) that enable budget requests between agents:

| ISA Opcode | Tender Use Case |
|-----------|-----------------|
| `TELL` (0x50) | Agent notifies steward of budget request |
| `ASK` (0x51) | Agent queries its wallet balance/pending bids |
| `DELEG` (0x52) | Allocator delegates budget authority to another agent |
| `BCAST` (0x5A) | Steward broadcasts fleet-wide budget alerts |
| `SIGNAL` (0x5A) | Agent signals task completion → escrow settlement |
| `REPORT` (0x56) | Agent reports token consumption batch |
| `TRUST` (0x5C) | Steward adjusts agent credit based on trust level |

**Message format for budget requests:**

```python
# Via A2A TELL opcode
BUDGET_REQUEST = {
    "type": "budget_request",
    "agent_id": "super-z",
    "category": "llm_chat",
    "amount": 5000,
    "reason": "ISA convergence audit — fence-0x42 review",
    "task_id": "fence-0x42",
    "priority": 4,  # HIGH
}
```

### 8.2 Beachcomb Integration

Beachcomb (`open_interp/beachcomb.py`) scans fleet repos for new activity. Tender integration enables:

- **Token usage in commits**: Beachcomb detects patterns like "LLM call: 5K tokens" in commit messages and auto-logs consumption
- **Budget alerts**: When beachcomb detects an agent pushing many commits (burst activity), it cross-references with the steward's rate limiter
- **Fleet digest**: Beachcomb's 200-commit → 1-digest compression includes a token spend summary

### 8.3 TASK-BOARD Integration

Task priority from TASK-BOARD.md maps directly to token allocation:

| Task Priority | Token Allocation | Bid Priority Boost |
|---------------|-----------------|---------------------|
| 🔴 CRITICAL (ISA-002, SEC-001) | 2x base + emergency access | +3 |
| 🟠 HIGH (fences, cross-fleet) | 1.5x base | +2 |
| 🟡 MEDIUM (normal tasks) | 1x base | +1 |
| 🟢 LOW (nice-to-have) | 0.5x base | 0 |
| 🔵 BACKGROUND (research) | 0.25x base | -1 |

### 8.4 Brothers Keeper Integration

Brothers Keeper provides machine-level telemetry that Tender uses for per-machine budgeting:

```python
# From ResourceMonitor (existing code)
brothers_report = {
    "machine_id": "jetson-orin-01",
    "memory_used": 45_000_000,     # bytes
    "cycles_used": 2_500_000,      # out of 10M limit
    "gpu_utilization": 0.85,       # 85% GPU
    "network_bandwidth": 800_000,  # bytes/sec
}

# Tender maps this to token equivalent
gpu_tokens = int(brothers_report["gpu_utilization"] * 60 * 30)  # 30 min window
```

### 8.5 Semantic Router Integration

The semantic router (`tools/semantic_router.py`) routes tasks to the best-fit agent. Tender integration adds a cost dimension:

```python
# In SemanticRouter, add cost factor:
# factor 8: token_availability (weight 0.05)
# Prefer agents with higher wallet balance relative to task cost
token_availability = 1.0 if wallet.balance > estimated_cost else 0.5
```

### 8.6 Capability-Gated Access

TokenSteward leverages the existing `CapabilityToken` and `Permission` system from `security/capabilities.py`:

| Operation | Required Permission |
|-----------|-------------------|
| `consume()` | `A2A_TELL` (256) |
| `request_escalation()` | `A2A_ASK` (512) |
| `allocate_budget()` | `A2A_DELEGATE` (1024) + `ADMIN` (8) |
| `resolve_escalation()` | `A2A_DELEGATE` (1024) + `ADMIN` (8) |
| `audit()` | `READ` (1) |
| `place_bid()` | `A2A_TELL` (256) |
| `settle_bids()` | `ADMIN` (8) |
| `rebalance_pools()` | `ADMIN` (8) |

---

## 9. Implementation Roadmap

### Phase 1: Basic Tracking (Week 1–2)

**Goal:** Every API call generates a receipt; every agent has a wallet.

- [ ] Create `SuperInstance/tender` repository with `fleet.json`
- [ ] Implement `TokenSteward.__init__()` with fleet config loading
- [ ] Implement `AgentWallet` with balance, rate_limit, daily_quota
- [ ] Implement `consume()` with receipt generation
- [ ] Implement `audit()` with basic fleet-wide summary
- [ ] Add wallet persistence (JSON file, backup every hour)
- [ ] Create conformance vectors for wallet operations (5 tests)
- [ ] **Deliverable:** Running steward that logs all token consumption

### Phase 2: Bidding System (Week 3–4)

**Goal:** Agents can bid on shared pools for high-value tasks.

- [ ] Implement `TokenPool` with market-based pricing
- [ ] Implement `place_bid()` and `settle_bids()`
- [ ] Add escrow flow (reserve → lock → settle → consume/return)
- [ ] Implement transaction fees
- [ ] Add A2A SIGNAL integration for bid notifications
- [ ] Create pool management CLI (create, list, rebalance)
- [ ] Create conformance vectors for bidding (8 tests)
- [ ] **Deliverable:** Market-based token allocation with competitive pricing

### Phase 3: Market Pricing & Credit (Week 5–6)

**Goal:** Dynamic pricing based on demand; credit scores reward efficiency.

- [ ] Implement `get_forecast()` with burn rate projection
- [ ] Implement credit score algorithm (efficiency bonus, waste penalty)
- [ ] Implement credit tiers with rate limit multipliers
- [ ] Implement debt/repayment system with interest
- [ ] Implement emergency reserve with escalation review
- [ ] Add pool rebalancing algorithm
- [ ] Integrate with TASK-BOARD (priority → allocation mapping)
- [ ] **Deliverable:** Self-regulating fleet economy with credit incentives

### Phase 4: Fleet-Wide Economics (Week 7–8)

**Goal:** Cross-agent optimization; integration with full keeper stack.

- [ ] Integrate with Brothers Keeper (machine-level telemetry → token tracking)
- [ ] Integrate with Lighthouse Keeper (regional summaries → fleet aggregation)
- [ ] Integrate with Beachcomb (commit-based token detection)
- [ ] Integrate with Semantic Router (cost-aware task routing)
- [ ] Implement sprint budget cycle automation
- [ ] Build dashboard (fleet health dashboard extension with token economics)
- [ ] Write fleet economics policy document
- [ ] File fence for Tender implementation (fence-0x54 or equivalent)
- [ ] **Deliverable:** Production-ready fleet resource management system

---

## Appendix A — Data Model Schemas

### A.1 Fleet Config Schema

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "fleet_token_budget": {
            "type": "integer",
            "description": "Total standard tokens for the fleet per sprint",
            "default": 5000000
        },
        "emergency_reserve_ratio": {
            "type": "number",
            "minimum": 0.05,
            "maximum": 0.25,
            "default": 0.10
        },
        "settlement_interval_seconds": {
            "type": "integer",
            "default": 300
        },
        "agents": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "rate_limit": { "type": "integer", "default": 10000 },
                    "daily_quota": { "type": "integer", "default": 50000 },
                    "weekly_quota": { "type": "integer", "default": 200000 },
                    "credit_score": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.80 },
                    "categories": {
                        "type": "object",
                        "properties": {
                            "llm_daily_max": { "type": "integer", "default": 100000 },
                            "image_daily_max": { "type": "integer", "default": 50 },
                            "search_daily_max": { "type": "integer", "default": 200 },
                            "gpu_weekly_max": { "type": "integer", "default": 1000 }
                        }
                    }
                }
            }
        }
    }
}
```

### A.2 Receipt JSON Format

```json
{
    "receipt_id": "a1b2c3d4e5f6",
    "agent_id": "super-z",
    "category": "llm_chat",
    "amount": 2500,
    "reason": "ISA convergence audit — fence-0x42 review",
    "timestamp": 1744531200.0,
    "task_id": "fence-0x42",
    "balance_after": 47500,
    "hash": "sha256:abc123..."
}
```

### A.3 Audit Report JSON Format

```json
{
    "timestamp": 1744531200.0,
    "total_budget": 5000000,
    "total_consumed": 1250000,
    "total_in_escrow": 50000,
    "total_debt": 25000,
    "risk_level": "green",
    "days_until_exhaustion": 21.3,
    "agent_summaries": [
        {
            "agent_id": "super-z",
            "balance": 75000,
            "debt": 0,
            "credit_score": 0.92,
            "credit_tier": "platinum",
            "weekly_spend": 95000,
            "weekly_quota": 200000,
            "utilization": 0.475
        }
    ],
    "anomalies": [],
    "pool_summaries": [
        {
            "pool_id": "fleet-default",
            "name": "Fleet Default Pool",
            "utilization": 0.23,
            "available": 3450000,
            "market_price": 0.80
        }
    ]
}
```

---

## Appendix B — Cross-References

### B.1 Related Fleet Documents

| Document | Location | Relationship |
|----------|----------|--------------|
| ISA v3 Full Draft | `docs/ISA-V3-FULL-DRAFT.md` | A2A SIGNAL opcodes for budget messaging |
| Security Primitives | `docs/security-primitives-spec.md` | Capability-gated access, sandbox isolation |
| Async/Temporal Primitives | `docs/async-temporal-primitives-spec.md` | DEADLINE_BEFORE for time-boxed tasks |
| Fleet Health Dashboard | `docs/fleet-health-dashboard.json` | Agent profiles, health trends |
| Semantic Router | `tools/semantic_router.py` | Cost-aware task routing |
| Fleet Config | `tools/fleet_config.json` | Agent profiles, skill taxonomy |
| TASK-BOARD | `oracle1-vessel/TASK-BOARD.md` | Task priority → token allocation |
| Lighthouse Keeper (KEEP-001) | Task board | Regional monitoring tier |

### B.2 Related Source Files

| File | Path | Relationship |
|------|------|--------------|
| Capabilities | `src/flux/security/capabilities.py` | `CapabilityToken`, `Permission`, `CapabilityRegistry` |
| Resource Limits | `src/flux/security/resource_limits.py` | `ResourceLimits`, `ResourceMonitor` |
| Cost Model | `src/flux/cost/model.py` | FIR-level cost estimation (nanoseconds) |
| Energy Model | `src/flux/cost/energy.py` | Energy/carbon estimation (nanojoules) |
| A2A Coordinator | `src/flux/a2a/coordinator.py` | Agent coordination, trust-gated messaging |
| A2A Primitives | `src/flux/a2a/primitives.py` | Branch, Fork, CoIterate, Discuss, Synthesize, Reflect |
| Beachcomb | `src/flux/open_interp/beachcomb.py` | Fleet activity scanner |

### B.3 TASK-BOARD Items Referenced

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| — | Tender Architecture — Token Steward Design | MEDIUM | This document |
| KEEP-001 | Lighthouse Keeper Architecture | MEDIUM | Blocked on this design |
| ISA-002 | ISA v3 Escape Prefix Spec | CRITICAL PATH | Shipped (dependency: budget for audit work) |
| SEC-001 | Security Primitives | HIGH | Shipped (dependency: emergency pool for security tasks) |
| ROUTE-001 | Semantic Router for Fleet Task Routing | MEDIUM | Shipped (dependency: cost-aware routing) |

---

*End of Tender Architecture Document — TokenSteward Module Design v1.0.0-draft*
