r"""
Bottle Tracker — SQLite-backed persistent storage for bottle metadata
and status tracking.

Maintains a database of all bottles across vessels, tracking:
- Read/unread status
- Acknowledgment status and timestamps
- Response links between bottles
- Alert history for unanswered bottles
- Scan history for trend analysis

Provides both a Python API and a CLI for querying bottle status.

Usage:
    from bottle_hygiene.bottle_tracker import BottleTracker

    tracker = BottleTracker("/path/to/bottle-hygiene.db")
    tracker.ingest_scan(report)        # Ingest a HygieneReport
    tracker.mark_as_read("bottle-id")  # Mark a bottle as read
    tracker.mark_as_acknowledged("bottle-id", "response-id")
    alerts = tracker.get_active_alerts()

CLI:
    python bottle_tracker.py --db bottles.db query --status unanswered
    python bottle_tracker.py --db bottles.db mark-read --bottle-id abc123
    python bottle_tracker.py --db bottles.db alert-list
"""

import os
import json
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class BottleRecord:
    """A single bottle record in the database."""
    bottle_id: str
    vessel_name: str
    bottle_dir: str
    direction: str
    filename: str
    title: str = ""
    from_agent: str = ""
    to_agent: str = ""
    date_str: str = ""
    date_parsed: Optional[str] = None
    file_path: str = ""
    file_mtime: float = 0.0
    file_size: int = 0
    file_hash: str = ""
    content_preview: str = ""
    is_acknowledgment: bool = False
    priority: str = ""
    tags: str = ""  # JSON array as string
    # Status tracking
    status: str = "new"  # new, read, acknowledged, actioned, stale, orphan, unanswered
    read_at: Optional[str] = None
    acked_at: Optional[str] = None
    acked_by: Optional[str] = None
    response_bottle_id: Optional[str] = None
    # Metadata
    first_seen: str = ""
    last_updated: str = ""
    scan_id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertRecord:
    """An alert about a bottle hygiene issue."""
    alert_id: int = 0
    bottle_id: str = ""
    vessel_name: str = ""
    alert_type: str = ""  # unanswered, stale, orphan
    severity: str = "warning"  # warning, critical
    message: str = ""
    created_at: str = ""
    resolved_at: Optional[str] = None
    is_active: bool = True


@dataclass
class ScanRecord:
    """A record of a hygiene scan execution."""
    scan_id: int = 0
    scan_timestamp: str = ""
    vessels_scanned: int = 0
    total_bottles: int = 0
    total_acknowledged: int = 0
    total_unanswered: int = 0
    total_orphan: int = 0
    total_stale: int = 0
    fleet_hygiene_score: float = 0.0
    report_json: str = ""


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bottles (
    bottle_id TEXT PRIMARY KEY,
    vessel_name TEXT NOT NULL,
    bottle_dir TEXT NOT NULL,
    direction TEXT NOT NULL,
    filename TEXT NOT NULL,
    title TEXT DEFAULT '',
    from_agent TEXT DEFAULT '',
    to_agent TEXT DEFAULT '',
    date_str TEXT DEFAULT '',
    date_parsed TEXT,
    file_path TEXT DEFAULT '',
    file_mtime REAL DEFAULT 0.0,
    file_size INTEGER DEFAULT 0,
    file_hash TEXT DEFAULT '',
    content_preview TEXT DEFAULT '',
    is_acknowledgment INTEGER DEFAULT 0,
    priority TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    status TEXT DEFAULT 'new',
    read_at TEXT,
    acked_at TEXT,
    acked_by TEXT,
    response_bottle_id TEXT,
    first_seen TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    scan_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_bottles_vessel ON bottles(vessel_name);
CREATE INDEX IF NOT EXISTS idx_bottles_status ON bottles(status);
CREATE INDEX IF NOT EXISTS idx_bottles_direction ON bottles(direction);
CREATE INDEX IF NOT EXISTS idx_bottles_date ON bottles(date_parsed);
CREATE INDEX IF NOT EXISTS idx_bottles_hash ON bottles(file_hash);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bottle_id TEXT NOT NULL,
    vessel_name TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT DEFAULT 'warning',
    message TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (bottle_id) REFERENCES bottles(bottle_id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_vessel ON alerts(vessel_name);

CREATE TABLE IF NOT EXISTS scans (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_timestamp TEXT NOT NULL,
    vessels_scanned INTEGER DEFAULT 0,
    total_bottles INTEGER DEFAULT 0,
    total_acknowledged INTEGER DEFAULT 0,
    total_unanswered INTEGER DEFAULT 0,
    total_orphan INTEGER DEFAULT 0,
    total_stale INTEGER DEFAULT 0,
    fleet_hygiene_score REAL DEFAULT 0.0,
    report_json TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ack_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bottle_id TEXT NOT NULL,
    response_bottle_id TEXT NOT NULL,
    latency_hours REAL DEFAULT 0.0,
    response_type TEXT DEFAULT 'ack',
    created_at TEXT NOT NULL,
    FOREIGN KEY (bottle_id) REFERENCES bottles(bottle_id),
    FOREIGN KEY (response_bottle_id) REFERENCES bottles(response_bottle_id)
);

CREATE INDEX IF NOT EXISTS idx_ack_links_bottle ON ack_links(bottle_id);
"""


# ---------------------------------------------------------------------------
# Bottle Tracker
# ---------------------------------------------------------------------------

class BottleTracker:
    """
    SQLite-backed bottle metadata and status tracker.

    Stores all scanned bottles, tracks their lifecycle
    (new -> read -> acknowledged -> actioned), generates alerts
    when bottles go unanswered, and provides a query API for
    other tools to check bottle status.
    """

    def __init__(self, db_path: str = "bottle-hygiene.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        # Enable WAL mode for better concurrent reads
        self._conn.execute("PRAGMA journal_mode=WAL")

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> 'BottleTracker':
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_scan(self, report: dict) -> int:
        """
        Ingest a HygieneReport (as dict) into the database.

        Returns the scan_id for the ingested scan.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Record the scan
        cursor = self._conn.execute(
            """INSERT INTO scans
               (scan_timestamp, vessels_scanned, total_bottles,
                total_acknowledged, total_unanswered, total_orphan,
                total_stale, fleet_hygiene_score, report_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report.get("scan_timestamp", now),
                report.get("vessels_scanned", 0),
                report.get("total_bottles", 0),
                report.get("total_acknowledged", 0),
                report.get("total_unanswered", 0),
                report.get("total_orphan", 0),
                report.get("total_stale", 0),
                report.get("fleet_hygiene_score", 0.0),
                json.dumps(report, default=str),
            ),
        )
        scan_id = cursor.lastrowid

        # Ingest all bottles
        for bottle_data in report.get("all_bottles", []):
            self._upsert_bottle(bottle_data, scan_id)

        # Ingest acknowledgment links
        for link_data in report.get("ack_links", []):
            self._insert_ack_link(link_data, scan_id)

        self._conn.commit()
        return scan_id

    def _upsert_bottle(self, bottle_data: dict, scan_id: int) -> None:
        """Insert or update a bottle record."""
        bottle_id = self._make_bottle_id(bottle_data)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Check if bottle already exists
        existing = self._conn.execute(
            "SELECT bottle_id, status, read_at, acked_at FROM bottles WHERE bottle_id = ?",
            (bottle_id,),
        ).fetchone()

        status = bottle_data.get("status", "new")

        if existing:
            # Preserve existing read/ack status if the new scan doesn't change it
            read_at = bottle_data.get("read_at") or existing["read_at"]
            acked_at = bottle_data.get("acked_at") or existing["acked_at"]
            acked_by = bottle_data.get("acked_by") or self._conn.execute(
                "SELECT acked_by FROM bottles WHERE bottle_id = ?",
                (bottle_id,),
            ).fetchone()["acked_by"]

            # Upgrade status: new -> read -> acknowledged
            status = self._upgrade_status(existing["status"], status)

            self._conn.execute(
                """UPDATE bottles SET
                    title = ?, from_agent = ?, to_agent = ?,
                    date_str = ?, date_parsed = ?, file_mtime = ?,
                    file_size = ?, file_hash = ?, content_preview = ?,
                    is_acknowledgment = ?, priority = ?, tags = ?,
                    status = ?, read_at = ?, acked_at = ?,
                    response_bottle_id = ?, last_updated = ?, scan_id = ?
                   WHERE bottle_id = ?""",
                (
                    bottle_data.get("title", ""),
                    bottle_data.get("from_agent", ""),
                    bottle_data.get("to_agent", ""),
                    bottle_data.get("date_str", ""),
                    bottle_data.get("date_parsed"),
                    bottle_data.get("file_mtime", 0.0),
                    bottle_data.get("file_size", 0),
                    bottle_data.get("file_hash", ""),
                    bottle_data.get("content_preview", ""),
                    int(bottle_data.get("is_acknowledgment", False)),
                    bottle_data.get("priority", ""),
                    json.dumps(bottle_data.get("tags", [])),
                    status,
                    read_at,
                    acked_at,
                    acked_by,
                    bottle_data.get("response_bottle_id"),
                    now,
                    scan_id,
                    bottle_id,
                ),
            )
        else:
            # New bottle
            self._conn.execute(
                """INSERT INTO bottles
                   (bottle_id, vessel_name, bottle_dir, direction, filename,
                    title, from_agent, to_agent, date_str, date_parsed,
                    file_path, file_mtime, file_size, file_hash,
                    content_preview, is_acknowledgment, priority, tags,
                    status, read_at, acked_at, acked_by,
                    response_bottle_id, first_seen, last_updated, scan_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bottle_id,
                    bottle_data.get("vessel_name", ""),
                    bottle_data.get("bottle_dir", ""),
                    bottle_data.get("direction", ""),
                    bottle_data.get("filename", ""),
                    bottle_data.get("title", ""),
                    bottle_data.get("from_agent", ""),
                    bottle_data.get("to_agent", ""),
                    bottle_data.get("date_str", ""),
                    bottle_data.get("date_parsed"),
                    bottle_data.get("path", ""),
                    bottle_data.get("file_mtime", 0.0),
                    bottle_data.get("file_size", 0),
                    bottle_data.get("file_hash", ""),
                    bottle_data.get("content_preview", ""),
                    int(bottle_data.get("is_acknowledgment", False)),
                    bottle_data.get("priority", ""),
                    json.dumps(bottle_data.get("tags", [])),
                    status,
                    bottle_data.get("read_at"),
                    bottle_data.get("acked_at"),
                    bottle_data.get("acked_by"),
                    bottle_data.get("response_bottle_id"),
                    now,
                    now,
                    scan_id,
                ),
            )

    def _insert_ack_link(self, link_data: dict, scan_id: int) -> None:
        """Insert an acknowledgment link."""
        bottle_id = self._resolve_bottle_id(link_data.get("bottle_path", ""))
        response_id = self._resolve_bottle_id(link_data.get("response_path", ""))

        if not bottle_id or not response_id:
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._conn.execute(
            """INSERT OR IGNORE INTO ack_links
               (bottle_id, response_bottle_id, latency_hours, response_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                bottle_id,
                response_id,
                link_data.get("latency_hours", 0.0),
                link_data.get("response_type", "ack"),
                now,
            ),
        )

    @staticmethod
    def _make_bottle_id(bottle_data: dict) -> str:
        """Generate a unique bottle ID from its metadata."""
        vessel = bottle_data.get("vessel_name", "unknown")
        bdir = bottle_data.get("bottle_dir", "unknown")
        filename = bottle_data.get("filename", "unknown")
        hash_input = f"{vessel}/{bdir}/{filename}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _resolve_bottle_id(self, path: str) -> Optional[str]:
        """Try to find a bottle_id from a file path."""
        if not path:
            return None
        row = self._conn.execute(
            "SELECT bottle_id FROM bottles WHERE file_path = ?",
            (path,),
        ).fetchone()
        if row:
            return row["bottle_id"]
        # Try by filename
        filename = os.path.basename(path)
        row = self._conn.execute(
            "SELECT bottle_id FROM bottles WHERE filename = ? LIMIT 1",
            (filename,),
        ).fetchone()
        return row["bottle_id"] if row else None

    @staticmethod
    def _upgrade_status(existing: str, new_status: str) -> str:
        """
        Status upgrade: once a bottle is read/acked, don't downgrade.

        Priority: acknowledged > actioned > read > new > unanswered > stale > orphan
        """
        hierarchy = {
            "acknowledged": 5,
            "actioned": 4,
            "read": 3,
            "new": 2,
            "unanswered": 1,
            "stale": 0,
            "orphan": 0,
        }
        existing_rank = hierarchy.get(existing, 2)
        new_rank = hierarchy.get(new_status, 2)
        return existing if existing_rank >= new_rank else new_status

    # ------------------------------------------------------------------
    # Status Operations
    # ------------------------------------------------------------------

    def mark_as_read(self, bottle_id: str, reader: str = "system") -> bool:
        """Mark a bottle as read."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self._conn.execute(
            """UPDATE bottles SET status = 'read', read_at = ?,
               last_updated = ? WHERE bottle_id = ? AND status = 'new'""",
            (now, now, bottle_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def mark_as_acknowledged(
        self,
        bottle_id: str,
        response_bottle_id: Optional[str] = None,
        acked_by: str = "system",
    ) -> bool:
        """Mark a bottle as acknowledged."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self._conn.execute(
            """UPDATE bottles SET status = 'acknowledged', acked_at = ?,
               acked_by = ?, response_bottle_id = ?, last_updated = ?
               WHERE bottle_id = ?""",
            (now, acked_by, response_bottle_id, now, bottle_id),
        )
        self._conn.commit()

        if cursor.rowcount > 0 and response_bottle_id:
            # Also mark the response as a read acknowledgment
            self._conn.execute(
                """UPDATE bottles SET status = 'acknowledged', last_updated = ?
                   WHERE bottle_id = ?""",
                (now, response_bottle_id),
            )
            self._conn.commit()

        return cursor.rowcount > 0

    def mark_as_actioned(self, bottle_id: str) -> bool:
        """Mark a bottle as having been acted upon."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self._conn.execute(
            """UPDATE bottles SET status = 'actioned', last_updated = ?
               WHERE bottle_id = ?""",
            (now, bottle_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query_bottles(
        self,
        vessel_name: Optional[str] = None,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Query bottles with optional filters."""
        clauses = []
        params: List[Any] = []

        if vessel_name:
            clauses.append("vessel_name = ?")
            params.append(vessel_name)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if direction:
            clauses.append("direction = ?")
            params.append(direction)

        where = " AND ".join(clauses) if clauses else "1=1"

        rows = self._conn.execute(
            f"SELECT * FROM bottles WHERE {where} "
            f"ORDER BY date_parsed DESC NULLS LAST LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()

        results = []
        for row in rows:
            record = dict(row)
            record["is_acknowledgment"] = bool(record.get("is_acknowledgment"))
            results.append(record)

        return results

    def get_bottle(self, bottle_id: str) -> Optional[Dict]:
        """Get a single bottle by its ID."""
        row = self._conn.execute(
            "SELECT * FROM bottles WHERE bottle_id = ?",
            (bottle_id,),
        ).fetchone()
        if row:
            record = dict(row)
            record["is_acknowledgment"] = bool(record.get("is_acknowledgment"))
            return record
        return None

    def get_bottle_by_path(self, file_path: str) -> Optional[Dict]:
        """Get a bottle by its file path."""
        row = self._conn.execute(
            "SELECT * FROM bottles WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        if row:
            record = dict(row)
            record["is_acknowledgment"] = bool(record.get("is_acknowledgment"))
            return record
        return None

    def get_vessel_stats(self, vessel_name: str) -> Dict:
        """Get aggregated stats for a single vessel."""
        row = self._conn.execute(
            """SELECT
                vessel_name,
                COUNT(*) as total,
                SUM(CASE WHEN direction = 'incoming' THEN 1 ELSE 0 END) as received,
                SUM(CASE WHEN direction = 'outgoing' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) as acked,
                SUM(CASE WHEN status = 'read' THEN 1 ELSE 0 END) as read_count,
                SUM(CASE WHEN status = 'unanswered' THEN 1 ELSE 0 END) as unanswered,
                SUM(CASE WHEN status = 'orphan' THEN 1 ELSE 0 END) as orphan,
                SUM(CASE WHEN status = 'stale' THEN 1 ELSE 0 END) as stale
               FROM bottles WHERE vessel_name = ?
               GROUP BY vessel_name""",
            (vessel_name,),
        ).fetchone()

        if row:
            return dict(row)
        return {}

    def get_all_vessel_stats(self) -> List[Dict]:
        """Get aggregated stats for all vessels."""
        rows = self._conn.execute(
            """SELECT
                vessel_name,
                COUNT(*) as total,
                SUM(CASE WHEN direction = 'incoming' THEN 1 ELSE 0 END) as received,
                SUM(CASE WHEN direction = 'outgoing' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) as acked,
                SUM(CASE WHEN status = 'read' THEN 1 ELSE 0 END) as read_count,
                SUM(CASE WHEN status = 'unanswered' THEN 1 ELSE 0 END) as unanswered,
                SUM(CASE WHEN status = 'orphan' THEN 1 ELSE 0 END) as orphan,
                SUM(CASE WHEN status = 'stale' THEN 1 ELSE 0 END) as stale
               FROM bottles
               GROUP BY vessel_name
               ORDER BY vessel_name"""
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def generate_alerts(self, unanswered_threshold_hours: int = 24) -> List[AlertRecord]:
        """
        Generate alerts for bottles that need attention.

        Creates alerts for:
        - Bottles unanswered for more than the threshold
        - Bottles that are orphan (outgoing with no response)
        - Bottles that are stale (>48h incoming with no action)
        """
        now = datetime.now(timezone.utc)
        alerts: List[AlertRecord] = []

        # Unanswered alerts
        threshold_dt = now - timedelta(hours=unanswered_threshold_hours)
        threshold_str = threshold_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        unanswered = self._conn.execute(
            """SELECT bottle_id, vessel_name, filename, date_parsed, title
               FROM bottles
               WHERE status IN ('new', 'unanswered')
               AND direction = 'incoming'
               AND (date_parsed IS NULL OR date_parsed < ?)""",
            (threshold_str,),
        ).fetchall()

        for row in unanswered:
            age_hours = 0
            if row["date_parsed"]:
                try:
                    dt = datetime.fromisoformat(row["date_parsed"].replace("Z", "+00:00"))
                    age_hours = (now - dt).total_seconds() / 3600
                except (ValueError, OverflowError):
                    pass

            severity = "critical" if age_hours > 48 else "warning"
            message = (
                f"Bottle '{row['filename']}' in {row['vessel_name']} "
                f"has been unanswered for {age_hours:.0f}h"
            )
            alert = self._create_alert(
                bottle_id=row["bottle_id"],
                vessel_name=row["vessel_name"],
                alert_type="unanswered",
                severity=severity,
                message=message,
            )
            alerts.append(alert)

        # Stale alerts
        stale_threshold = now - timedelta(hours=48)
        stale_str = stale_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")

        stale = self._conn.execute(
            """SELECT bottle_id, vessel_name, filename, date_parsed, title
               FROM bottles
               WHERE status = 'stale'
               AND direction = 'incoming'
               AND date_parsed < ?""",
            (stale_str,),
        ).fetchall()

        for row in stale:
            alert = self._create_alert(
                bottle_id=row["bottle_id"],
                vessel_name=row["vessel_name"],
                alert_type="stale",
                severity="critical",
                message=(
                    f"Stale directive '{row['filename']}' in "
                    f"{row['vessel_name']} — over 48h with no action"
                ),
            )
            alerts.append(alert)

        # Orphan alerts
        orphans = self._conn.execute(
            """SELECT bottle_id, vessel_name, filename, date_parsed, title
               FROM bottles
               WHERE status = 'orphan'
               AND direction = 'outgoing' """,
        ).fetchall()

        for row in orphans:
            alert = self._create_alert(
                bottle_id=row["bottle_id"],
                vessel_name=row["vessel_name"],
                alert_type="orphan",
                severity="warning",
                message=(
                    f"Orphan bottle '{row['filename']}' in "
                    f"{row['vessel_name']} — no response detected"
                ),
            )
            alerts.append(alert)

        return alerts

    def _create_alert(
        self,
        bottle_id: str,
        vessel_name: str,
        alert_type: str,
        severity: str,
        message: str,
    ) -> AlertRecord:
        """Create a new alert, avoiding duplicates."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Check for existing active alert of the same type
        existing = self._conn.execute(
            """SELECT alert_id FROM alerts
               WHERE bottle_id = ? AND alert_type = ? AND is_active = 1""",
            (bottle_id, alert_type),
        ).fetchone()

        if existing:
            return AlertRecord(
                alert_id=existing["alert_id"],
                bottle_id=bottle_id,
                vessel_name=vessel_name,
                alert_type=alert_type,
                severity=severity,
                message=message,
                created_at=now,
                is_active=True,
            )

        cursor = self._conn.execute(
            """INSERT INTO alerts
               (bottle_id, vessel_name, alert_type, severity, message, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (bottle_id, vessel_name, alert_type, severity, message, now),
        )
        self._conn.commit()

        return AlertRecord(
            alert_id=cursor.lastrowid,
            bottle_id=bottle_id,
            vessel_name=vessel_name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            created_at=now,
            is_active=True,
        )

    def get_active_alerts(
        self,
        vessel_name: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get all currently active alerts."""
        clauses = ["is_active = 1"]
        params: List[Any] = []

        if vessel_name:
            clauses.append("vessel_name = ?")
            params.append(vessel_name)
        if alert_type:
            clauses.append("alert_type = ?")
            params.append(alert_type)

        where = " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT * FROM alerts WHERE {where} ORDER BY created_at DESC",
            (*params,),
        ).fetchall()

        return [dict(row) for row in rows]

    def resolve_alert(self, alert_id: int) -> bool:
        """Mark an alert as resolved."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor = self._conn.execute(
            "UPDATE alerts SET is_active = 0, resolved_at = ? WHERE alert_id = ?",
            (now, alert_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # History / Trends
    # ------------------------------------------------------------------

    def get_scan_history(self, limit: int = 20) -> List[Dict]:
        """Get recent scan history for trend analysis."""
        rows = self._conn.execute(
            """SELECT scan_id, scan_timestamp, vessels_scanned, total_bottles,
                      total_acknowledged, total_unanswered, total_orphan,
                      total_stale, fleet_hygiene_score
               FROM scans ORDER BY scan_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_hygiene_trend(self, days: int = 7) -> Dict:
        """Get hygiene score trend over the past N days."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        rows = self._conn.execute(
            """SELECT scan_timestamp, fleet_hygiene_score,
                      total_bottles, total_unanswered, total_orphan
               FROM scans
               WHERE scan_timestamp >= ?
               ORDER BY scan_id ASC""",
            (since_str,),
        ).fetchall()

        return {
            "period_days": days,
            "data_points": len(rows),
            "scans": [dict(row) for row in rows],
            "current_score": dict(rows[-1])["fleet_hygiene_score"] if rows else None,
            "trend": "improving" if (
                len(rows) >= 2 and
                dict(rows[-1])["fleet_hygiene_score"] > dict(rows[0])["fleet_hygiene_score"]
            ) else ("declining" if (
                len(rows) >= 2 and
                dict(rows[-1])["fleet_hygiene_score"] < dict(rows[0])["fleet_hygiene_score"]
            ) else "stable"),
        }

    def get_ack_latency_stats(self) -> Dict:
        """Get statistics about acknowledgment latency."""
        row = self._conn.execute(
            """SELECT
                COUNT(*) as link_count,
                AVG(latency_hours) as avg_latency,
                MIN(latency_hours) as min_latency,
                MAX(latency_hours) as max_latency
               FROM ack_links
               WHERE latency_hours > 0"""
        ).fetchone()

        if row and row["link_count"] > 0:
            return {
                "total_links": row["link_count"],
                "avg_latency_hours": round(row["avg_latency"], 1),
                "min_latency_hours": round(row["min_latency"], 1),
                "max_latency_hours": round(row["max_latency"], 1),
            }
        return {"total_links": 0, "avg_latency_hours": 0,
                "min_latency_hours": 0, "max_latency_hours": 0}

    def get_dashboard_data(self) -> Dict:
        """Get all data needed for a dashboard view."""
        return {
            "vessel_stats": self.get_all_vessel_stats(),
            "active_alerts": self.get_active_alerts(),
            "recent_scans": self.get_scan_history(limit=5),
            "ack_latency": self.get_ack_latency_stats(),
            "hygiene_trend": self.get_hygiene_trend(days=7),
            "total_bottles": self._conn.execute(
                "SELECT COUNT(*) as c FROM bottles"
            ).fetchone()["c"],
            "total_alerts": self._conn.execute(
                "SELECT COUNT(*) as c FROM alerts WHERE is_active = 1"
            ).fetchone()["c"],
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bottle Tracker CLI")
    parser.add_argument("--db", default="bottle-hygiene.db", help="Database path")
    sub = parser.add_subparsers(dest="command")

    # query
    q = sub.add_parser("query", help="Query bottles")
    q.add_argument("--vessel", help="Filter by vessel name")
    q.add_argument("--status", help="Filter by status")
    q.add_argument("--direction", help="Filter by direction")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # stats
    sub.add_parser("stats", help="Show vessel statistics")

    # trend
    t = sub.add_parser("trend", help="Show hygiene trend")
    t.add_argument("--days", type=int, default=7)

    # mark-read
    mr = sub.add_parser("mark-read", help="Mark a bottle as read")
    mr.add_argument("--bottle-id", required=True)

    # mark-ack
    ma = sub.add_parser("mark-ack", help="Mark a bottle as acknowledged")
    ma.add_argument("--bottle-id", required=True)
    ma.add_argument("--response-id", help="ID of the response bottle")
    ma.add_argument("--by", default="cli", help="Who is marking it")

    # alerts
    a = sub.add_parser("alert-list", help="List active alerts")
    a.add_argument("--vessel", help="Filter by vessel")
    a.add_argument("--type", help="Filter by alert type")

    # resolve-alert
    ra = sub.add_parser("resolve-alert", help="Resolve an alert")
    ra.add_argument("--alert-id", type=int, required=True)

    # dashboard
    sub.add_parser("dashboard", help="Get dashboard data")

    # ingest
    ing = sub.add_parser("ingest", help="Ingest a JSON report")
    ing.add_argument("--file", required=True, help="Path to JSON report file")

    args = parser.parse_args()

    tracker = BottleTracker(args.db)

    if args.command == "query":
        results = tracker.query_bottles(
            vessel_name=args.vessel,
            status=args.status,
            direction=args.direction,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            for b in results:
                status_icon = {
                    "acknowledged": "[ACK]",
                    "read": "[READ]",
                    "actioned": "[ACT]",
                    "unanswered": "[???]",
                    "stale": "[OLD]",
                    "orphan": "[ORP]",
                    "new": "[NEW]",
                }.get(b["status"], "[???]")
                print(
                    f"  {status_icon} {b['vessel_name']}/{b['bottle_dir']}/{b['filename']}"
                )
                if b.get("title"):
                    print(f"         {b['title'][:80]}")

    elif args.command == "stats":
        stats = tracker.get_all_vessel_stats()
        print(f"{'Vessel':<20} {'Total':>6} {'Recv':>5} {'Sent':>5} {'Ack':>5} {'Unans':>6} {'Orph':>5}")
        print("-" * 70)
        for s in stats:
            print(
                f"{s['vessel_name']:<20} {s['total']:>6} {s['received']:>5} "
                f"{s['sent']:>5} {s['acked']:>5} {s['unanswered']:>6} {s['orphan']:>5}"
            )

    elif args.command == "trend":
        trend = tracker.get_hygiene_trend(days=args.days)
        print(f"Hygiene Trend (last {args.days} days): {trend['trend']}")
        if trend['scans']:
            for s in trend['scans']:
                score = s['fleet_hygiene_score']
                bar = "#" * int(score / 5)
                print(f"  {s['scan_timestamp'][:16]}  {score:5.1f}/100  {bar}")

    elif args.command == "mark-read":
        ok = tracker.mark_as_read(args.bottle_id)
        print(f"{'OK' if ok else 'NOT FOUND'}: marked as read")

    elif args.command == "mark-ack":
        ok = tracker.mark_as_acknowledged(
            args.bottle_id, args.response_id, args.by
        )
        print(f"{'OK' if ok else 'NOT FOUND'}: marked as acknowledged")

    elif args.command == "alert-list":
        alerts = tracker.get_active_alerts(
            vessel_name=args.vessel, alert_type=args.type
        )
        if alerts:
            for a in alerts:
                icon = "!" if a["severity"] == "critical" else "?"
                print(f"  [{icon}] #{a['alert_id']} [{a['alert_type']}] {a['message']}")
        else:
            print("  No active alerts.")

    elif args.command == "resolve-alert":
        ok = tracker.resolve_alert(args.alert_id)
        print(f"{'OK' if ok else 'NOT FOUND'}: alert resolved")

    elif args.command == "dashboard":
        data = tracker.get_dashboard_data()
        print(json.dumps(data, indent=2, default=str))

    elif args.command == "ingest":
        with open(args.file) as f:
            report = json.load(f)
        scan_id = tracker.ingest_scan(report)
        print(f"Ingested scan #{scan_id} with {report.get('total_bottles', 0)} bottles")

    else:
        parser.print_help()

    tracker.close()


if __name__ == "__main__":
    main()
