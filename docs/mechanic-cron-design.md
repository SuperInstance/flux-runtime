# Mechanic Cron Design — Periodic Fleet Scanning System

**Document ID:** MECH-ARCH-001
**Author:** Super Z (FLUX Fleet — Cartographer)
**Date:** 2026-04-14
**Status:** DRAFT — Requires fleet review and Oracle1 approval
**Version:** 1.0.0-draft
**Depends on:** lighthouse-keeper-architecture.md, fleet_config.json, semantic_router.py
**Tracks:** TASK-BOARD "Mechanic Cron — Periodic Fleet Scanning" (MECH-001)
**Repo:** `SuperInstance/fleet-mechanic`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Cron Schedule Design](#2-cron-schedule-design)
3. [Scan Types](#3-scan-types)
4. [Auto-Issue Creation](#4-auto-issue-creation)
5. [Implementation](#5-implementation)
6. [Configuration](#6-configuration)
7. [Appendix A — Finding Severity Classification](#appendix-a--finding-severity-classification)
8. [Appendix B — Issue Templates](#appendix-b--issue-templates)
9. [Appendix C — Cross-References](#appendix-c--cross-references)

---

## 1. Executive Summary

A fleet of 733 repositories and 6+ autonomous agents generates technical debt continuously: CI pipelines break, dependencies rot, branches go stale, bottles pile up unread, and test coverage silently erodes. Without automated maintenance, this debt compounds until manual intervention becomes overwhelming. The **Mechanic Cron** is the fleet's automated maintenance system — a periodic scanner that runs health checks, dependency audits, stale branch detection, bottle hygiene checks, and test coverage monitoring across all fleet repos on configurable schedules.

The Mechanic Cron operates as a cron-like scheduler (configurable intervals from every 5 minutes to every 6 hours) that executes five scan types: health scan (full fleet health), dependency scan (outdated packages), stale branch scan (orphan branches), bottle hygiene scan (unacknowledged inter-agent messages), and test coverage scan (declining test counts). Findings are classified by severity (critical, warning, info), deduplicated against existing issues, and optionally auto-create GitHub issues with proper templates and auto-assignment based on semantic router scores. This design specifies the schedule architecture, each scan type's logic, the auto-issue pipeline, deduplication strategy, and a complete Python implementation outline.

---

## 2. Cron Schedule Design

### 2.1 Schedule Overview

The Mechanic Cron runs five scan types on different schedules, each calibrated to the expected rate of change for the thing being monitored:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     MECHANIC CRON SCHEDULE                                │
├───────────────────┬──────────────┬───────────────────────────────────────┤
│ Scan Type         │ Interval     │ Rationale                             │
├───────────────────┼──────────────┼───────────────────────────────────────┤
│ Lighthouse Beacon │ Every 5 min  │ Detect agent-down within 5 minutes    │
│ Beachcomb         │ Every 15 min │ Catch new bottles quickly for I2I     │
│ Bottleneck Detect │ Every 1 hour │ CI failures need hourly awareness     │
│ Test Coverage     │ Every 3 hours│ Test count changes are gradual        │
│ Full Fleet Health │ Every 6 hours│ Comprehensive scan of all repos       │
│ Dependency Audit  │ Every 12 hours│ Dependency updates are daily-cycle   │
│ Stale Branch      │ Every 24 hours│ Branch staleness is a daily metric   │
│ Weekly Digest     │ Every Monday │ Summary report for fleet coordination │
└───────────────────┴──────────────┴───────────────────────────────────────┘
```

### 2.2 Schedule Architecture

```python
@dataclass
class ScanSchedule:
    """Configuration for a single scan type."""
    scan_type: str
    interval_seconds: int
    enabled: bool = True
    timeout_seconds: int = 300      # per-scan timeout
    max_retries: int = 2
    retry_delay_seconds: int = 60
    last_run: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    consecutive_failures: int = 0

    def is_due(self, now: float) -> bool:
        if not self.enabled:
            return False
        return (now - self.last_run) >= self.interval_seconds

    def next_run(self, now: float) -> float:
        elapsed = now - self.last_run
        if elapsed >= self.interval_seconds:
            return now
        return self.last_run + self.interval_seconds


# Default schedule configuration
DEFAULT_SCHEDULES: list[ScanSchedule] = [
    ScanSchedule(scan_type="lighthouse_beacon",  interval_seconds=300),    # 5 min
    ScanSchedule(scan_type="beachcomb",           interval_seconds=900),    # 15 min
    ScanSchedule(scan_type="bottleneck",          interval_seconds=3600),   # 1 hour
    ScanSchedule(scan_type="test_coverage",       interval_seconds=10800),  # 3 hours
    ScanSchedule(scan_type="full_health",         interval_seconds=21600),  # 6 hours
    ScanSchedule(scan_type="dependency",          interval_seconds=43200),  # 12 hours
    ScanSchedule(scan_type="stale_branch",        interval_seconds=86400),  # 24 hours
    ScanSchedule(scan_type="weekly_digest",       interval_seconds=604800), # 7 days
]
```

### 2.3 Cron Loop Design

The main cron loop runs as a persistent process with a 30-second tick interval. On each tick, it checks which scans are due, executes them in parallel (up to a concurrency limit), and processes findings through the auto-issue pipeline.

```
┌────────────────────────────────────────────────────────────────┐
│                    MECHANIC CRON MAIN LOOP                      │
│                                                                 │
│  every 30 seconds:                                              │
│    for each schedule in schedules:                              │
│      if schedule.is_due():                                      │
│        spawn scan_worker(schedule)                              │
│                                                                 │
│  scan_worker(schedule):                                         │
│    findings = execute_scan(schedule.scan_type)                  │
│    findings = deduplicate(findings, existing_issues)            │
│    findings = classify_severity(findings)                       │
│    issues = create_issues(findings)                             │
│    log_results(schedule, findings, issues)                      │
│    schedule.last_run = now()                                    │
└────────────────────────────────────────────────────────────────┘
```

### 2.4 Concurrency and Throttling

To avoid overwhelming the GitHub API and local resources:

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max parallel scans | 3 | Prevent resource exhaustion |
| GitHub API rate limit | 5,000 req/hour | GitHub unauthenticated limit |
| Per-repo scan timeout | 60 seconds | Don't hang on slow repos |
| Total scan timeout | 300 seconds | Kill runaway scans |
| Retry on failure | 2 retries | Transient failures (network) |
| Cooldown between scans | 10 seconds | Avoid API throttling |

---

## 3. Scan Types

### 3.1 Health Scan (Full Fleet)

**Frequency:** Every 6 hours
**Scope:** All repos in fleet_config.json and fleet-census.md
**Purpose:** Comprehensive fleet health assessment

The health scan runs `fleet-mechanic scan` (or equivalent) across all fleet repos and produces a structured health report. Each repo is classified into one of four health categories:

```
┌────────────────────────────────────────────────────────────────┐
│ HEALTH SCAN CLASSIFICATION                                      │
├─────────┬──────────────────────────────────────────────────────┤
│ GREEN   │ CI passing, tests passing, recent commits,           │
│         │ fleet.json present, conformance report exists        │
│ YELLOW  │ CI passing but tests declining, or no recent commits │
│         │ in 7+ days, or missing fleet.json                    │
│ RED     │ CI failing, or tests failing, or broken dependencies │
│ DEAD    │ No commits in 30+ days, or repo archived, or        │
│         │ 404/removed                                          │
└─────────┴──────────────────────────────────────────────────────┘
```

**Health Check Steps per Repo:**

1. **CI Status**: Check latest GitHub Actions run (passing/failing/none)
2. **Test Count**: Run test command (if specified in fleet.json) and count passing tests
3. **Recent Activity**: Check last commit date (within 7 days = active)
4. **Fleet Standards**: Check for fleet.json, README.md, .github/workflows
5. **Conformance**: Check for conformance_report.json (if applicable to runtime repos)
6. **Dependency Health**: Run `pip audit` / `npm audit` (if applicable)
7. **Branch Hygiene**: Count open branches, flag stale PRs

**Output:** `FleetHealthScan` with per-repo health status and fleet-wide summary.

### 3.2 Dependency Scan

**Frequency:** Every 12 hours
**Scope:** All repos with dependency manifests (requirements.txt, package.json, Cargo.toml, go.mod)
**Purpose:** Detect outdated, vulnerable, or incompatible dependencies

```python
@dataclass
class DependencyFinding:
    """A finding from the dependency scan."""
    repo: str
    manifest_file: str                    # e.g., "requirements.txt"
    dependency_name: str
    current_version: str
    latest_version: Optional[str]         # None if unknown
    is_vulnerable: bool
    vulnerability_severity: Optional[str] # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    is_outdated: bool
    is_pinned: bool                       # exact version vs range
    advisory_id: Optional[str]            # CVE or GitHub Advisory ID
```

**Detection Methods:**

| Method | Tool | Detects |
|--------|------|---------|
| Python | `pip list --outdated` | Outdated pip packages |
| Python | `pip-audit` | Known vulnerabilities (CVEs) |
| Node.js | `npm audit` | Vulnerabilities in npm packages |
| Node.js | `npm outdated` | Outdated npm packages |
| Rust | `cargo audit` | Vulnerabilities in Rust crates |
| Go | `govulncheck` | Vulnerabilities in Go modules |

### 3.3 Stale Branch Scan

**Frequency:** Every 24 hours
**Scope:** All repos with open branches
**Purpose:** Identify orphan branches that should be cleaned up

```python
@dataclass
class StaleBranchFinding:
    """A finding from the stale branch scan."""
    repo: str
    branch_name: str
    last_commit_date: str               # ISO 8601
    last_commiter: str
    days_since_last_commit: int
    is_protected: bool                  # main/master/develop
    has_open_pr: bool                   # branch linked to open PR
    ahead_of_main: int                  # commits ahead of default branch
    behind_main: int                    # commits behind default branch
```

**Staleness Thresholds:**

| Age | Status | Action |
|-----|--------|--------|
| < 7 days | Fresh | No action |
| 7–14 days | Aging | Info notification |
| 14–30 days | Stale | Warning — suggest deletion |
| 30–60 days | Orphan | Create issue for branch owner |
| > 60 days | Fossil | Auto-close (if no PR) |

**Special Cases:**
- Protected branches (main, master, develop) are never flagged
- Branches linked to open PRs are given a 2x age multiplier before flagging
- Branches with "wip/", "draft/", "exp/" prefix are given a 1.5x multiplier

### 3.4 Bottle Hygiene Scan

**Frequency:** Every 15 minutes (as part of beachcomb)
**Scope:** All vessel repos' `/bottles/` directories
**Purpose:** Detect unacknowledged inter-agent messages

The bottle hygiene scan checks for:
1. **Unread bottles**: Bottles in `for-{agent}/` that have no corresponding response
2. **Expired bottles**: Bottles older than 7 days without acknowledgment
3. **Orphan bottles**: Bottles addressed to agents not in fleet_config.json
4. **Overflow bottles**: Vessels with >20 unread bottles (possible communication breakdown)

```python
@dataclass
class BottleHygieneFinding:
    """A finding from the bottle hygiene scan."""
    vessel_repo: str
    bottle_path: str
    addressed_to: str                  # target agent
    sent_by: str                       # sending agent
    sent_at: float
    is_acknowledged: bool
    days_unread: float
    is_expired: bool                   # > 7 days old
    is_orphan: bool                    # addressee not in fleet
```

**Escalation for Bottles:**

| Condition | Severity | Action |
|-----------|----------|--------|
| 1–3 unread bottles | INFO | Log, no action |
| 4–10 unread bottles | WARNING | Ping the addressed agent |
| >10 unread bottles | CRITICAL | Alert vessel owner, log to fleet health |
| Expired bottle (>7d) | WARNING | Create issue on vessel repo |
| Orphan bottle (unknown agent) | INFO | Log for fleet census update |

### 3.5 Test Coverage Scan

**Frequency:** Every 3 hours
**Scope:** All repos with test commands in fleet.json
**Purpose:** Flag repos with declining test counts or failing tests

```python
@dataclass
class TestCoverageFinding:
    """A finding from the test coverage scan."""
    repo: str
    test_command: str                  # command from fleet.json
    total_tests: int
    passing_tests: int
    failing_tests: int
    skipped_tests: int
    pass_rate: float                   # passing / total
    previous_pass_rate: Optional[float] # from last scan
    pass_rate_delta: Optional[float]   # change from last scan
    execution_time_sec: float
    is_declining: bool                 # pass rate dropped > 5%
    has_new_failures: bool             # tests that were passing before
```

**Decline Detection:**

The test coverage scan maintains a rolling history of test results per repo (last 10 scans). A repo is flagged as "declining" if:

1. Pass rate dropped by more than 5 percentage points in the last 3 scans
2. Any previously-passing test is now failing (new failure)
3. Test count decreased by more than 10% (tests removed without replacement)

---

## 4. Auto-Issue Creation

### 4.1 Rules Engine

Findings from all scan types are fed through a rules engine that determines whether to create a GitHub issue. Not all findings warrant an issue — the rules engine prevents issue spam by filtering, classifying, and deduplicating.

**Issue Creation Rules:**

```
For each finding:
  1. SEVERITY CHECK: Only WARNING+ findings create issues (INFO is logged only)
  2. DEDUPLICATION: Check if an open issue already covers this finding
  3. THRESHOLD CHECK: Some findings need multiple occurrences before creating issue
  4. AGENT CHECK: Don't create issues for repos owned by agents not in fleet
  5. COOLDOWN CHECK: Don't create more than 1 issue per repo per scan type per day
  6. DRY RUN CHECK: If --dry-run flag is set, log but don't create
```

### 4.2 Severity Classification

Each finding is assigned a severity level based on its characteristics:

| Severity | Criteria | Issue Labels | Auto-Assign |
|----------|----------|-------------|-------------|
| **CRITICAL** | CI broken, security vuln (CVE HIGH+), agent down >5min | `bug`, `critical`, `mechanic-auto` | Yes (best-fit agent) |
| **WARNING** | Stale branch >14d, declining tests, outdated deps, unread bottles >10 | `maintenance`, `mechanic-auto` | Yes (repo owner) |
| **INFO** | Stale branch <14d, minor deps, <10 unread bottles | None (log only) | No |

### 4.3 Deduplication Strategy

Deduplication is the most important feature of the auto-issue system. Without it, the Mechanic Cron would create hundreds of duplicate issues for recurring problems.

**Deduplication Algorithm:**

```python
def deduplicate_findings(
    findings: list[Finding],
    existing_issues: list[GitHubIssue],
) -> list[Finding]:
    """
    Remove findings that already have corresponding open issues.

    Deduplication key: (repo, scan_type, finding_fingerprint)
    Where finding_fingerprint is a hash of the finding's unique attributes.
    """
    # Build fingerprint set from existing open issues
    existing_fingerprints: set[str] = set()
    for issue in existing_issues:
        if issue.state == "open" and "mechanic-auto" in issue.labels:
            fp = _extract_fingerprint(issue)
            if fp:
                existing_fingerprints.add(fp)

    # Filter findings
    unique_findings = []
    for finding in findings:
        fp = finding.fingerprint
        if fp not in existing_fingerprints:
            unique_findings.append(finding)
        else:
            finding.is_duplicate = True

    return unique_findings


def _extract_fingerprint(issue: GitHubIssue) -> Optional[str]:
    """Extract deduplication fingerprint from an existing issue."""
    # Mechanic Cron issues include fingerprint in the body:
    # <!-- mechanic-fingerprint: abc123def456 -->
    match = re.search(
        r"<!-- mechanic-fingerprint: (\w+) -->",
        issue.body
    )
    return match.group(1) if match else None
```

**Fingerprint Construction:**

Each finding type has a different fingerprint construction:

| Finding Type | Fingerprint Components |
|-------------|----------------------|
| Health Scan | `sha256(repo + health_status)` |
| Dependency | `sha256(repo + dep_name + vulnerability_id)` |
| Stale Branch | `sha256(repo + branch_name)` |
| Bottle Hygiene | `sha256(vessel + addressee + "unread")` |
| Test Coverage | `sha256(repo + "declining" + failing_test_names)` |

### 4.4 Auto-Assignment Based on Semantic Router

When an issue is created, the Mechanic Cron queries the Semantic Router to find the best-fit agent:

```python
def auto_assign_issue(finding: Finding, router: SemanticRouter) -> Optional[str]:
    """
    Use semantic router to find best agent for a finding.

    1. Extract keywords from finding description
    2. Create a temporary FleetTask with those keywords
    3. Route the task through the semantic router
    4. Return the top-ranked agent
    """
    # Create a synthetic task from the finding
    task_keywords = _extract_keywords(finding)
    task = FleetTask(
        task_id=f"MECH-AUTO-{finding.fingerprint[:8]}",
        title=finding.title,
        description=finding.description,
        required_skills=task_keywords.get("skills", []),
        priority=_severity_to_priority(finding.severity),
    )

    # Route through semantic router
    rankings = router.route_task(task)
    if rankings:
        return rankings[0].agent_id
    return None
```

**Assignment Priority:**

1. If the finding's repo has a known owner (from fleet_config.json), assign to that owner
2. Otherwise, use semantic router to find best-fit agent
3. If no agent scores above 0.50, leave unassigned with `help-wanted` label

### 4.5 Issue Lifecycle

```
Finding detected
  └── Dedup check ── DUPLICATE ──▶ Skip (add comment to existing issue)
       │
       └── Unique ──▶ Create GitHub Issue
                          │
                    ┌─────┴──────┐
                    │ Issue      │
                    │ Created    │
                    └─────┬──────┘
                          │
            ┌─────────────┼─────────────┐
            │             │             │
        Assigned      Unassigned    Closed
            │             │         (by human)
            │             │
        Agent works    Labeled
        on issue       help-wanted
            │
            │
        ┌───┴────┐
        │Resolved│
        └───┬────┘
            │
    Next scan: finding gone
            │
    Close issue automatically
    (if auto-close enabled)
```

---

## 5. Implementation

### 5.1 MechanicCron Implementation

```python
"""
mechanic_cron.py — Periodic fleet scanning system for the FLUX fleet.

Runs scheduled scans across all fleet repos, detects issues,
and optionally creates GitHub issues with auto-assignment.

Usage:
  python mechanic_cron.py --config mechanic-cron-config.yaml
  python mechanic_cron.py --scan full_health --dry-run
  python mechanic_cron.py --scan all --once
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime, timedelta
import time
import uuid
import hashlib
import json
import re
import subprocess
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ═══════════════════════════════════════════════════════════════
# Enums & Constants
# ═══════════════════════════════════════════════════════════════

class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ScanType(Enum):
    LIGHTHOUSE_BEACON = "lighthouse_beacon"
    BEACHCOMB = "beachcomb"
    BOTTLENECK = "bottleneck"
    TEST_COVERAGE = "test_coverage"
    FULL_HEALTH = "full_health"
    DEPENDENCY = "dependency"
    STALE_BRANCH = "stale_branch"
    WEEKLY_DIGEST = "weekly_digest"


class HealthCategory(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    DEAD = "dead"


MAX_PARALLEL_SCANS = 3
GITHUB_API_RATE_LIMIT = 5000
PER_REPO_TIMEOUT = 60
TOTAL_SCAN_TIMEOUT = 300
COOLDOWN_SECONDS = 86400  # 1 issue per repo per scan type per day


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class Finding:
    """A finding from any scan type."""
    finding_id: str
    scan_type: ScanType
    repo: str
    severity: Severity
    title: str
    description: str
    fingerprint: str
    is_duplicate: bool = False
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    @property
    def fingerprint_hash(self) -> str:
        return hashlib.sha256(self.fingerprint.encode()).hexdigest()[:16]


@dataclass
class RepoHealth:
    """Health status for a single repository."""
    repo: str
    category: HealthCategory
    ci_status: Optional[str] = None     # "passing", "failing", "none"
    test_count: int = 0
    test_pass_rate: float = 0.0
    last_commit_date: Optional[str] = None
    has_fleet_json: bool = False
    has_readme: bool = False
    has_ci: bool = False
    has_conformance: bool = False
    dependency_issues: int = 0
    stale_branches: int = 0
    days_since_commit: int = 0


@dataclass
class DependencyFinding(Finding):
    """Finding from dependency scan."""
    manifest_file: str = ""
    dependency_name: str = ""
    current_version: str = ""
    latest_version: str = ""
    is_vulnerable: bool = False
    vulnerability_severity: str = ""
    advisory_id: str = ""


@dataclass
class StaleBranchFinding(Finding):
    """Finding from stale branch scan."""
    branch_name: str = ""
    last_commit_date: str = ""
    last_committer: str = ""
    days_since_commit: int = 0
    is_protected: bool = False
    has_open_pr: bool = False
    ahead_of_main: int = 0
    behind_main: int = 0


@dataclass
class BottleHygieneFinding(Finding):
    """Finding from bottle hygiene scan."""
    vessel_repo: str = ""
    bottle_path: str = ""
    addressed_to: str = ""
    sent_by: str = ""
    sent_at: float = 0.0
    is_acknowledged: bool = False
    days_unread: float = 0.0


@dataclass
class TestCoverageFinding(Finding):
    """Finding from test coverage scan."""
    test_command: str = ""
    total_tests: int = 0
    passing_tests: int = 0
    failing_tests: int = 0
    pass_rate: float = 0.0
    previous_pass_rate: float = 0.0
    pass_rate_delta: float = 0.0
    execution_time_sec: float = 0.0
    is_declining: bool = False
    new_failure_names: list = field(default_factory=list)


@dataclass
class Issue:
    """A GitHub issue created by the Mechanic Cron."""
    issue_id: str
    repo: str
    title: str
    body: str
    labels: list[str]
    assignees: list[str]
    finding_fingerprint: str
    status: str = "created"  # created, duplicate, skipped


@dataclass
class ScanSchedule:
    """Schedule configuration for a scan type."""
    scan_type: ScanType
    interval_seconds: int
    enabled: bool = True
    timeout_seconds: int = 300
    max_retries: int = 2
    retry_delay_seconds: int = 60
    last_run: float = 0.0
    last_success: float = 0.0
    consecutive_failures: int = 0

    def is_due(self, now: float) -> bool:
        if not self.enabled:
            return False
        return (now - self.last_run) >= self.interval_seconds


@dataclass
class ScanResult:
    """Result of a single scan execution."""
    scan_type: ScanType
    started_at: float
    completed_at: float
    duration_sec: float
    findings: list[Finding]
    repos_scanned: int
    success: bool
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Mechanic Cron Core
# ═══════════════════════════════════════════════════════════════

class MechanicCron:
    """Periodic fleet scanning system.

    Runs scheduled scans across all fleet repos:
    - Health scan: full fleet health every 6 hours
    - Dependency scan: detect outdated/vulnerable deps every 12 hours
    - Stale branch scan: orphan branches every 24 hours
    - Bottle hygiene scan: unacknowledged bottles every 15 min
    - Test coverage scan: declining test counts every 3 hours

    Findings are deduplicated, classified, and optionally
    auto-create GitHub issues with semantic router assignment.
    """

    def __init__(self, config: dict):
        self.config = config
        self.repos: list[str] = config.get("repos", [])
        self.schedules: dict[ScanType, ScanSchedule] = {}
        self.scan_history: list[ScanResult] = []
        self.test_history: dict[str, list[float]] = {}  # repo -> pass rates
        self._running = False
        self._dry_run = config.get("dry_run", False)
        self._github_token = config.get("github_token", "")
        self._create_issues_enabled = config.get("auto_create_issues", True)

        # Initialize schedules
        for sched_cfg in config.get("schedules", []):
            st = ScanType(sched_cfg["scan_type"])
            self.schedules[st] = ScanSchedule(
                scan_type=st,
                interval_seconds=sched_cfg.get("interval", 21600),
                enabled=sched_cfg.get("enabled", True),
                timeout_seconds=sched_cfg.get("timeout", 300),
            )

    def run_schedule(self) -> None:
        """Main cron loop — runs until stopped."""
        self._running = True
        tick_interval = self.config.get("tick_interval", 30)

        while self._running:
            now = time.time()
            due_scans = [
                sched for sched in self.schedules.values()
                if sched.is_due(now)
            ]

            if due_scans:
                with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SCANS) as executor:
                    futures = {
                        executor.submit(self._run_scan, sched): sched
                        for sched in due_scans
                    }
                    for future in as_completed(futures):
                        sched = futures[future]
                        try:
                            result = future.result(timeout=sched.timeout_seconds)
                            self.scan_history.append(result)
                            if result.success:
                                sched.last_success = result.completed_at
                                sched.consecutive_failures = 0
                            else:
                                sched.consecutive_failures += 1
                        except Exception as e:
                            sched.consecutive_failures += 1
                            self._log(f"Scan {sched.scan_type.value} failed: {e}")

            time.sleep(tick_interval)

    def stop(self) -> None:
        self._running = False

    def run_once(self, scan_types: list[str] | None = None) -> list[ScanResult]:
        """Run specified scans once and return results."""
        results = []
        types = scan_types or [st.value for st in ScanType]

        for st_name in types:
            st = ScanType(st_name)
            if st in self.schedules:
                result = self._run_scan(self.schedules[st])
                results.append(result)
            else:
                self._log(f"Unknown scan type: {st_name}")

        return results

    def _run_scan(self, schedule: ScanSchedule) -> ScanResult:
        """Execute a single scan."""
        started_at = time.time()
        findings: list[Finding] = []

        try:
            if schedule.scan_type == ScanType.FULL_HEALTH:
                findings = self.health_scan()
            elif schedule.scan_type == ScanType.DEPENDENCY:
                findings = self.dependency_scan()
            elif schedule.scan_type == ScanType.STALE_BRANCH:
                findings = self.stale_branch_scan()
            elif schedule.scan_type == ScanType.BEACHCOMB:
                findings = self.bottle_hygiene_scan()
            elif schedule.scan_type == ScanType.TEST_COVERAGE:
                findings = self.test_coverage_scan()
            elif schedule.scan_type == ScanType.BOTTLENECK:
                findings = self.bottleneck_scan()
            elif schedule.scan_type == ScanType.LIGHTHOUSE_BEACON:
                findings = self.lighthouse_beacon_scan()
            else:
                findings = []

            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)

        completed_at = time.time()

        # Process findings through auto-issue pipeline
        if success and findings:
            issues = self.create_issues(findings)
            self._log(
                f"Scan {schedule.scan_type.value}: "
                f"{len(findings)} findings, {len(issues)} issues"
            )

        schedule.last_run = completed_at

        return ScanResult(
            scan_type=schedule.scan_type,
            started_at=started_at,
            completed_at=completed_at,
            duration_sec=completed_at - started_at,
            findings=findings,
            repos_scanned=len(self.repos),
            success=success,
            error=error,
        )

    # ─── Scan Implementations ────────────────────────────────

    def health_scan(self) -> list[Finding]:
        """Full fleet health scan across all repos."""
        findings = []

        for repo in self.repos:
            health = self._check_repo_health(repo)

            if health.category in (HealthCategory.RED, HealthCategory.DEAD):
                findings.append(Finding(
                    finding_id=uuid.uuid4().hex[:12],
                    scan_type=ScanType.FULL_HEALTH,
                    repo=repo,
                    severity=Severity.CRITICAL if health.category == HealthCategory.RED else Severity.WARNING,
                    title=f"[{health.category.value.upper()}] {repo} health: {health.category.value}",
                    description=self._health_description(health),
                    fingerprint=f"health:{repo}:{health.category.value}",
                    metadata={"health": vars(health)},
                ))
            elif health.category == HealthCategory.YELLOW:
                findings.append(Finding(
                    finding_id=uuid.uuid4().hex[:12],
                    scan_type=ScanType.FULL_HEALTH,
                    repo=repo,
                    severity=Severity.WARNING,
                    title=f"[YELLOW] {repo} needs attention",
                    description=self._health_description(health),
                    fingerprint=f"health:{repo}:{health.category.value}",
                    metadata={"health": vars(health)},
                ))

        return findings

    def dependency_scan(self) -> list[Finding]:
        """Detect outdated and vulnerable dependencies."""
        findings = []

        for repo in self.repos:
            repo_findings = self._scan_repo_dependencies(repo)
            findings.extend(repo_findings)

        return findings

    def stale_branch_scan(self) -> list[Finding]:
        """Identify orphan branches older than threshold."""
        findings = []

        for repo in self.repos:
            repo_findings = self._scan_repo_stale_branches(repo)
            findings.extend(repo_findings)

        return findings

    def bottle_hygiene_scan(self) -> list[Finding]:
        """Check for unacknowledged bottles in vessel repos."""
        findings = []

        vessel_repos = [
            r for r in self.repos
            if "vessel" in r.lower()
        ]

        for vessel in vessel_repos:
            vessel_findings = self._scan_vessel_bottles(vessel)
            findings.extend(vessel_findings)

        return findings

    def test_coverage_scan(self) -> list[Finding]:
        """Flag repos with declining test counts."""
        findings = []

        for repo in self.repos:
            repo_finding = self._scan_repo_test_coverage(repo)
            if repo_finding:
                findings.append(repo_finding)

        return findings

    def bottleneck_scan(self) -> list[Finding]:
        """Detect repos with failing CI (bottleneck detection)."""
        findings = []

        for repo in self.repos:
            ci_status = self._check_ci_status(repo)
            if ci_status == "failing":
                findings.append(Finding(
                    finding_id=uuid.uuid4().hex[:12],
                    scan_type=ScanType.BOTTLENECK,
                    repo=repo,
                    severity=Severity.CRITICAL,
                    title=f"CI failing in {repo}",
                    description=f"The CI pipeline for {repo} is currently failing. "
                                f"This may be blocking other fleet work.",
                    fingerprint=f"bottleneck:ci:{repo}",
                ))

        return findings

    def lighthouse_beacon_scan(self) -> list[Finding]:
        """Check lighthouse beacon status for all agents."""
        findings = []

        agents = self.config.get("agents", [])
        for agent in agents:
            agent_id = agent.get("name", "")
            last_seen = agent.get("last_seen", 0)
            elapsed = time.time() - last_seen

            if elapsed > 300:  # 5 minutes
                findings.append(Finding(
                    finding_id=uuid.uuid4().hex[:12],
                    scan_type=ScanType.LIGHTHOUSE_BEACON,
                    repo=agent.get("vessel_repo", ""),
                    severity=Severity.CRITICAL,
                    title=f"Agent {agent_id} beacon missing ({elapsed:.0f}s)",
                    description=f"Agent {agent_id} has not sent a beacon in "
                                f"{elapsed:.0f} seconds. May be down.",
                    fingerprint=f"beacon:down:{agent_id}",
                ))
            elif elapsed > 180:  # 3 minutes
                findings.append(Finding(
                    finding_id=uuid.uuid4().hex[:12],
                    scan_type=ScanType.LIGHTHOUSE_BEACON,
                    repo=agent.get("vessel_repo", ""),
                    severity=Severity.WARNING,
                    title=f"Agent {agent_id} beacon stale ({elapsed:.0f}s)",
                    description=f"Agent {agent_id} last seen {elapsed:.0f}s ago.",
                    fingerprint=f"beacon:stale:{agent_id}",
                ))

        return findings

    # ─── Auto-Issue Pipeline ─────────────────────────────────

    def create_issues(self, findings: list[Finding]) -> list[Issue]:
        """Deduplicate, classify, and create GitHub issues from findings."""
        if not self._create_issues_enabled:
            return []

        # Filter to WARNING+ only
        actionable = [f for f in findings if f.severity != Severity.INFO]

        # Deduplicate against existing issues
        existing = self._fetch_open_issues()
        unique = self._deduplicate(actionable, existing)

        # Create issues
        issues = []
        for finding in unique:
            issue = self._create_single_issue(finding)
            if issue:
                issues.append(issue)

        return issues

    def _deduplicate(
        self,
        findings: list[Finding],
        existing_issues: list[dict],
    ) -> list[Finding]:
        """Remove findings that already have open issues."""
        existing_fps: set[str] = set()
        for issue in existing_issues:
            if issue.get("state") == "open":
                fp = self._extract_fingerprint_from_issue(issue)
                if fp:
                    existing_fps.add(fp)

        unique = []
        for f in findings:
            if f.fingerprint_hash not in existing_fps:
                unique.append(f)
            else:
                f.is_duplicate = True

        return unique

    def _create_single_issue(self, finding: Finding) -> Optional[Issue]:
        """Create a single GitHub issue for a finding."""
        if self._dry_run:
            self._log(f"[DRY RUN] Would create issue: {finding.title}")
            return None

        labels = self._severity_to_labels(finding.severity)
        assignees = self._auto_assign(finding)

        body = (
            f"## Mechanic Cron Auto-Issue\n\n"
            f"**Scan Type:** {finding.scan_type.value}\n"
            f"**Severity:** {finding.severity.value}\n"
            f"**Repo:** {finding.repo}\n"
            f"**Detected:** {datetime.fromtimestamp(finding.created_at).isoformat()}\n\n"
            f"{finding.description}\n\n"
            f"---\n"
            f"<!-- mechanic-fingerprint: {finding.fingerprint_hash} -->\n"
            f"<!-- mechanic-scan: {finding.scan_type.value} -->\n"
        )

        issue = Issue(
            issue_id=uuid.uuid4().hex[:12],
            repo=finding.repo,
            title=finding.title,
            body=body,
            labels=labels,
            assignees=assignees,
            finding_fingerprint=finding.fingerprint_hash,
        )

        # In production: call GitHub API to create issue
        # self._github_create_issue(issue)

        return issue

    # ─── Helper Methods ──────────────────────────────────────

    def _check_repo_health(self, repo: str) -> RepoHealth:
        """Check health of a single repo."""
        health = RepoHealth(repo=repo)

        # Check for fleet.json
        health.has_fleet_json = self._repo_has_file(repo, "fleet.json")
        health.has_readme = self._repo_has_file(repo, "README.md")
        health.has_ci = self._repo_has_file(repo, ".github/workflows/")

        # Check last commit
        health.last_commit_date = self._get_last_commit_date(repo)
        if health.last_commit_date:
            delta = datetime.now() - datetime.fromisoformat(health.last_commit_date)
            health.days_since_commit = delta.days

        # Check CI status
        health.ci_status = self._check_ci_status(repo)

        # Classify
        if health.ci_status == "failing" or health.dependency_issues > 0:
            health.category = HealthCategory.RED
        elif health.days_since_commit > 30:
            health.category = HealthCategory.DEAD
        elif health.days_since_commit > 7 or not health.has_fleet_json:
            health.category = HealthCategory.YELLOW
        else:
            health.category = HealthCategory.GREEN

        return health

    def _health_description(self, health: RepoHealth) -> str:
        parts = []
        if health.ci_status:
            parts.append(f"CI: **{health.ci_status}**")
        if health.days_since_commit > 0:
            parts.append(f"Last commit: **{health.days_since_commit}d ago**")
        parts.append(f"fleet.json: {'present' if health.has_fleet_json else 'missing'}")
        parts.append(f"README: {'present' if health.has_readme else 'missing'}")
        parts.append(f"CI workflow: {'present' if health.has_ci else 'missing'}")
        return "\n".join(f"- {p}" for p in parts)

    def _severity_to_labels(self, severity: Severity) -> list[str]:
        labels = ["mechanic-auto"]
        if severity == Severity.CRITICAL:
            labels.extend(["bug", "critical"])
        elif severity == Severity.WARNING:
            labels.append("maintenance")
        return labels

    def _auto_assign(self, finding: Finding) -> list[str]:
        """Auto-assign issue based on repo ownership."""
        # In production: query semantic_router.py for best-fit agent
        repo = finding.repo
        for agent in self.config.get("agents", []):
            if agent.get("vessel_repo", "") == repo:
                return [agent.get("name", "")]
        return []

    def _repo_has_file(self, repo: str, path: str) -> bool:
        """Check if a file exists in a repo (placeholder)."""
        return False

    def _get_last_commit_date(self, repo: str) -> Optional[str]:
        """Get last commit date for a repo (placeholder)."""
        return None

    def _check_ci_status(self, repo: str) -> Optional[str]:
        """Check CI status for a repo (placeholder)."""
        return None

    def _fetch_open_issues(self) -> list[dict]:
        """Fetch open mechanic-auto issues from repos (placeholder)."""
        return []

    def _extract_fingerprint_from_issue(self, issue: dict) -> Optional[str]:
        body = issue.get("body", "")
        match = re.search(r"<!-- mechanic-fingerprint: (\w+) -->", body)
        return match.group(1) if match else None

    def _scan_repo_dependencies(self, repo: str) -> list[Finding]:
        """Scan a single repo for dependency issues (placeholder)."""
        return []

    def _scan_repo_stale_branches(self, repo: str) -> list[Finding]:
        """Scan a single repo for stale branches (placeholder)."""
        return []

    def _scan_vessel_bottles(self, vessel: str) -> list[Finding]:
        """Scan a vessel repo for bottle hygiene issues (placeholder)."""
        return []

    def _scan_repo_test_coverage(self, repo: str) -> Optional[Finding]:
        """Scan a single repo for test coverage issues (placeholder)."""
        return None

    def _log(self, message: str) -> None:
        ts = datetime.now().isoformat()
        print(f"[{ts}] [mechanic-cron] {message}")


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FLUX Mechanic Cron")
    parser.add_argument("--config", default="mechanic-cron-config.yaml")
    parser.add_argument("--scan", help="Run specific scan type(s), comma-separated")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Log but don't create issues")
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = json.load(f)

    cron = MechanicCron(config)

    if args.dry_run:
        cron._dry_run = True

    if args.scan or args.once:
        scan_types = args.scan.split(",") if args.scan else None
        results = cron.run_once(scan_types)
        for r in results:
            status = "OK" if r.success else f"FAIL: {r.error}"
            print(f"  {r.scan_type.value}: {len(r.findings)} findings in {r.duration_sec:.1f}s [{status}]")
    else:
        print("Mechanic Cron started. Press Ctrl+C to stop.")
        try:
            cron.run_schedule()
        except KeyboardInterrupt:
            cron.stop()
            print("Mechanic Cron stopped.")
```

---

## 6. Configuration

### 6.1 YAML Configuration File

```yaml
# mechanic-cron-config.yaml — Mechanic Cron configuration
# See docs/mechanic-cron-design.md for full documentation

mechanic:
  version: "1.0.0"
  dry_run: false                       # true = log issues but don't create
  auto_create_issues: true             # enable auto-issue creation
  tick_interval_seconds: 30            # main loop tick
  max_parallel_scans: 3                # concurrency limit
  github_token: "${GITHUB_TOKEN}"      # env var interpolation

  repos:
    # Loaded from fleet_config.json at startup
    source: "fleet_config.json"
    # Or explicitly listed:
    # - "SuperInstance/flux-runtime"
    # - "SuperInstance/oracle1-vessel"
    # - "SuperInstance/superz-vessel"

  schedules:
    - scan_type: lighthouse_beacon
      interval: 300                     # 5 minutes
      enabled: true
      timeout: 60

    - scan_type: beachcomb
      interval: 900                     # 15 minutes
      enabled: true
      timeout: 120

    - scan_type: bottleneck
      interval: 3600                    # 1 hour
      enabled: true
      timeout: 180

    - scan_type: test_coverage
      interval: 10800                   # 3 hours
      enabled: true
      timeout: 300

    - scan_type: full_health
      interval: 21600                   # 6 hours
      enabled: true
      timeout: 300

    - scan_type: dependency
      interval: 43200                   # 12 hours
      enabled: true
      timeout: 300

    - scan_type: stale_branch
      interval: 86400                   # 24 hours
      enabled: true
      timeout: 180

    - scan_type: weekly_digest
      interval: 604800                  # 7 days
      enabled: true
      timeout: 600

  thresholds:
    health:
      dead_days: 30                     # days since commit = DEAD
      yellow_days: 7                    # days since commit = YELLOW
    stale_branch:
      warning_days: 14
      orphan_days: 30
      fossil_days: 60
    bottle_hygiene:
      warning_count: 10                 # unread bottles = WARNING
      critical_count: 20                # unread bottles = CRITICAL
      expiry_days: 7                    # days before bottle is expired
    test_coverage:
      decline_threshold: 0.05           # 5% decline = WARNING
      new_failure_severity: "critical"

  issue_creation:
    min_severity: "warning"             # INFO findings don't create issues
    cooldown_seconds: 86400             # 1 issue per repo per scan type per day
    max_issues_per_scan: 20             # cap on issues per scan run
    labels:
      - "mechanic-auto"
    critical_labels:
      - "mechanic-auto"
      - "bug"
      - "critical"
    warning_labels:
      - "mechanic-auto"
      - "maintenance"

  deduplication:
    enabled: true
    fingerprint_algo: "sha256"
    close_resolved_issues: true         # auto-close when finding is gone

  semantic_router:
    enabled: true
    config_path: "fleet_config.json"
    min_confidence: 0.50                # don't assign below this score
    fallback_label: "help-wanted"

  reporting:
    log_level: "INFO"
    log_file: "/fleet/logs/mechanic-cron.log"
    report_directory: "/fleet/reports/mechanic/"
    weekly_digest_recipients:
      - "Oracle1"
      - "Fleet Mechanic"
```

### 6.2 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub API token for issue creation | None |
| `MECHANIC_CONFIG` | Path to config file | mechanic-cron-config.yaml |
| `MECHANIC_DRY_RUN` | Enable dry-run mode | false |
| `FLEET_CONFIG` | Path to fleet_config.json | fleet_config.json |
| `LOG_LEVEL` | Logging verbosity | INFO |

---

## Appendix A — Finding Severity Classification

### A.1 Severity Decision Tree

```
Finding detected
  │
  ├─ Agent down > 5 minutes ──────── CRITICAL
  ├─ CI pipeline failing ─────────── CRITICAL
  ├─ Security vulnerability (HIGH+) ─ CRITICAL
  │
  ├─ Agent stale 3-5 minutes ─────── WARNING
  ├─ Stale branch > 14 days ──────── WARNING
  ├─ Declining test pass rate ─────── WARNING
  ├─ Outdated dependencies ───────── WARNING
  ├─ Unread bottles > 10 ─────────── WARNING
  ├─ Missing fleet.json ──────────── WARNING
  │
  ├─ New unread bottle < 10 ──────── INFO
  ├─ Stale branch < 14 days ──────── INFO
  ├─ Minor dependency update ──────── INFO
  │
  └─ Protected branch ────────────── SKIP (never flagged)
```

### A.2 Severity-to-Priority Mapping for Semantic Router

| Finding Severity | Router Priority | Confidence Threshold |
|-----------------|-----------------|---------------------|
| CRITICAL | 5 (critical) | 0.80 |
| WARNING | 3 (medium) | 0.60 |
| INFO | 1 (background) | N/A (no issue) |

---

## Appendix B — Issue Templates

### B.1 Critical Issue Template

```markdown
## Mechanic Cron Auto-Issue

**Scan Type:** full_health
**Severity:** critical
**Repo:** SuperInstance/flux-runtime
**Detected:** 2026-04-14T10:30:00

### Problem

The CI pipeline for SuperInstance/flux-runtime is currently failing.
This may be blocking other fleet work that depends on this repo.

### Details

- CI: **failing**
- Last commit: **2d ago**
- fleet.json: present
- README: present
- CI workflow: present

### Recommended Actions

1. Investigate the failing CI run
2. Fix the broken test or configuration
3. Verify CI passes before closing this issue

### Auto-Assignment

This issue was auto-assigned to **Super Z** based on vessel ownership.

---
<!-- mechanic-fingerprint: a1b2c3d4e5f67890 -->
<!-- mechanic-scan: full_health -->
```

### B.2 Warning Issue Template (Stale Branch)

```markdown
## Mechanic Cron Auto-Issue

**Scan Type:** stale_branch
**Severity:** warning
**Repo:** SuperInstance/superz-vessel
**Detected:** 2026-04-14T08:00:00

### Problem

Branch `experiment/isa-v3-alt` has not been updated in 23 days
and is 15 commits ahead of main with no open PR.

### Details

- Branch: `experiment/isa-v3-alt`
- Last commit: 2026-03-22
- Last committer: Super Z
- Ahead of main: 15 commits
- Behind main: 45 commits
- Has open PR: No

### Recommended Actions

1. Merge or rebase the branch against main
2. Open a PR if the work is ready for review
3. Delete the branch if the experiment is abandoned

---
<!-- mechanic-fingerprint: f9e8d7c6b5a43210 -->
<!-- mechanic-scan: stale_branch -->
```

---

## Appendix C — Cross-References

| Reference | Document | Relationship |
|-----------|----------|--------------|
| Lighthouse Keeper | docs/lighthouse-keeper-architecture.md | Beacon scan consumes Lighthouse health data |
| Tender Architecture | docs/tender-architecture.md | Mechanic reports feed into Tender dashboards |
| Semantic Router | tools/semantic_router.py | Auto-assignment of auto-created issues |
| Fleet Config | tools/fleet_config.json | Agent profiles, repo list, capabilities |
| TASK-BOARD | oracle1-vessel/TASK-BOARD.md | MECH-001 (this task) |
| Beachcomb Scanner | oracle1-vessel/tools/beachcomb.py | Beachcomb scan extends this tool |
| Fleet Mechanic | SuperInstance/fleet-mechanic | Primary repo for Mechanic Cron deployment |
| Fleet Health Dashboard | docs/fleet-health-dashboard.json | Health scan populates dashboard data |
| Knowledge Base | knowledge-federation/knowledge-base.json | Health findings written to knowledge base |
