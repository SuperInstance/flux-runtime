# Bottle Hygiene Checker

Ensure message-in-a-bottle communications across the FLUX fleet are being read and acknowledged.

## The Problem

The fleet uses a message-in-a-bottle protocol for async coordination between agents:

| Directory | Direction | Meaning |
|---|---|---|
| `from-fleet/` | Incoming | Directives TO this agent from the fleet |
| `for-fleet/` | Outgoing | Reports FROM this agent to the fleet |
| `for-oracle1/` | Outgoing | Messages specifically for Oracle1 |
| `for-superz/` | Incoming | Messages specifically for Super Z |
| `for-jetsonclaw1/` | Outgoing | Messages specifically for JetsonClaw1 |

**Problem:** Bottles get sent but never acknowledged. This demoralizes agents and breaks the coordination loop. As noted in the Witness Marks protocol: *"unacknowledged bottles demoralize agents."*

## Tools

### 1. Hygiene Checker (`hygiene_checker.py`)

Scans vessel repositories for bottle directories, tracks receipt and acknowledgment status, and produces a health report.

**What it detects:**
- **Orphan bottles** — outgoing messages never referenced by any response
- **Stale directives** — incoming bottles older than 48 hours with no evidence of action
- **Unanswered bottles** — incoming bottles older than 24 hours with no acknowledgment
- **Acknowledgment latency** — time between bottle creation and any response

**Usage:**
```bash
# Auto-discover and scan all vessels
python hygiene_checker.py --project-root /path/to/my-project

# Scan specific vessels
python hygiene_checker.py \
    --vessels /path/to/superz-vessel /path/to/oracle1-vessel

# Custom thresholds and output
python hygiene_checker.py \
    --stale-hours 72 \
    --unanswered-hours 12 \
    --output-dir ./reports \
    --json

# Output as JSON to stdout
python hygiene_checker.py --vessels ./superz-vessel -j
```

**Python API:**
```python
from bottle_hygiene.hygiene_checker import HygieneChecker

checker = HygieneChecker(
    vessel_roots=["./superz-vessel", "./oracle1-vessel"],
    stale_threshold_hours=48,
    unanswered_threshold_hours=24,
)
report = checker.run_check()
report.save_json("hygiene-report.json")
report.save_markdown("hygiene-report.md")

# Access individual metrics
print(report.fleet_hygiene_score)  # 0.0 - 100.0
print(report.total_unanswered)     # count
print(report.orphan_bottles)       # list of dicts
```

### 2. Bottle Tracker (`bottle_tracker.py`)

SQLite-backed persistent storage for bottle metadata and status tracking. Maintains history across scans for trend analysis.

**Usage:**
```bash
# Ingest a hygiene report
python bottle_tracker.py --db bottles.db ingest --file hygiene-report.json

# Query bottles
python bottle_tracker.py --db bottles.db query --status unanswered --json
python bottle_tracker.py --db bottles.db query --vessel superz-vessel

# Show statistics
python bottle_tracker.py --db bottles.db stats

# Show hygiene trend
python bottle_tracker.py --db bottles.db trend --days 7

# Mark a bottle as read/acknowledged
python bottle_tracker.py --db bottles.db mark-read --bottle-id abc123
python bottle_tracker.py --db bottles.db mark-ack --bottle-id abc123 --by cli

# List active alerts
python bottle_tracker.py --db bottles.db alert-list
python bottle_tracker.py --db bottles.db alert-list --type stale --vessel superz-vessel

# Resolve an alert
python bottle_tracker.py --db bottles.db resolve-alert --alert-id 5

# Dashboard data (all stats in one call)
python bottle_tracker.py --db bottles.db dashboard
```

**Python API:**
```python
from bottle_hygiene.bottle_tracker import BottleTracker

with BottleTracker("bottles.db") as tracker:
    # Ingest scan results
    scan_id = tracker.ingest_scan(report.to_dict())

    # Query
    unanswered = tracker.query_bottles(status="unanswered")
    vessel_stats = tracker.get_vessel_stats("superz-vessel")
    trend = tracker.get_hygiene_trend(days=7)

    # Generate alerts for bottles needing attention
    alerts = tracker.generate_alerts(unanswered_threshold_hours=24)

    # Mark status
    tracker.mark_as_read(bottle_id="abc123")
    tracker.mark_as_acknowledged(bottle_id="abc123", acked_by="superz")
```

### 3. Auto Responder (`auto_respond.py`)

Auto-generates acknowledgment bottles for received directives.

**Response templates:**
| Type | When to use |
|---|---|
| `received` | Simple acknowledgment that you've read the bottle |
| `working` | You're actively working on the directive |
| `completed` | The task has been completed |
| `blocked` | Something prevents you from executing |
| `declined` | You can't take on the task |
| `question` | You need clarification before proceeding |
| `checkin` | Periodic status check on a long-running task |

**Usage:**
```bash
# Dry run — see what would be generated
python auto_respond.py --agent superz --vessel ./superz-vessel --dry-run

# Generate acknowledgments for all unacknowledged bottles
python auto_respond.py --agent superz --vessel ./superz-vessel

# List pending responses without generating
python auto_respond.py --agent superz --vessel ./superz-vessel --list-pending

# Use a specific response type
python auto_respond.py --agent superz --vessel ./superz-vessel --type working

# Include a custom note
python auto_respond.py --agent superz --vessel ./superz-vessel \
    --note "Prioritizing conformance runner work next."

# Also update the tracker database
python auto_respond.py --agent superz --vessel ./superz-vessel \
    --tracker-db ./bottles.db
```

**Python API:**
```python
from bottle_hygiene.auto_respond import AutoResponder

responder = AutoResponder(
    agent_name="superz",
    vessel_path="./superz-vessel",
)

# List what needs acknowledgment
pending = responder.list_pending_responses()

# Create a single response
response = responder.create_acknowledgment(
    bottle_path="from-fleet/ORACLE1-DIRECTIVE.md",
    response_type="working",
    note="Starting on the conformance runner now.",
)

# Batch respond to everything
responses = responder.respond_to_unacknowledged(response_type="received")
```

## Metrics Explained

| Metric | Meaning | Good Range |
|---|---|---|
| **Fleet Hygiene Score** | Weighted score (0-100) based on ack rate, stale ratio, orphan ratio | 80-100 |
| **Acknowledged** | Bottles with a confirmed response | High = good |
| **Unanswered** | Incoming bottles >24h with no acknowledgment | 0 = ideal |
| **Orphan** | Outgoing bottles with no evidence of response | 0 = ideal |
| **Stale** | Incoming bottles >48h with no action taken | 0 = ideal |
| **Ack Latency** | Hours between bottle creation and response | Low = good |

### Score Calculation

The hygiene score starts at 100 and deducts points:
- Up to 30 points for unanswered bottles (proportional)
- Up to 20 points for orphan bottles (proportional)
- Up to 25 points for stale directives (proportional)

## Integration with Beachcomb

The hygiene checker integrates with the existing [`beachcomb.py`](../../src/flux/open_interp/beachcomb.py) scheduled scanning system:

```python
from flux.open_interp.beachcomb import Beachcomber, Sweep
from bottle_hygiene.hygiene_checker import create_beachcomb_sweep_for_hygiene

bc = Beachcomber("superz")

# Add a hygiene check sweep that runs every 60 minutes
sweep_config = create_beachcomb_sweep_for_hygiene(
    vessel_roots=["./superz-vessel", "./oracle1-vessel"],
    interval_minutes=60,
)
```

## Typical Workflow

```bash
# 1. Run a hygiene check
python hygiene_checker.py --vessels ./superz-vessel ./oracle1-vessel \
    --output-dir ./reports

# 2. Ingest into the tracker
python bottle_tracker.py --db bottles.db ingest \
    --file ./reports/hygiene-report-*.json

# 3. Check alerts
python bottle_tracker.py --db bottles.db alert-list

# 4. Auto-respond to unacknowledged bottles
python auto_respond.py --agent superz --vessel ./superz-vessel \
    --tracker-db bottles.db --dry-run

# 5. After review, generate for real
python auto_respond.py --agent superz --vessel ./superz-vessel \
    --tracker-db bottles.db

# 6. Check the trend over time
python bottle_tracker.py --db bottles.db trend --days 7
```

## File Structure

```
tools/bottle-hygiene/
  hygiene_checker.py   # Core scanner and report generator (500+ lines)
  bottle_tracker.py    # SQLite persistence and query API (300+ lines)
  auto_respond.py      # Acknowledgment bottle generator (200+ lines)
  README.md            # This file
```
