r"""
Bottle Hygiene Checker — ensures message-in-a-bottle communications
are being read and acknowledged across the FLUX fleet.

The fleet uses a message-in-a-bottle protocol:
  - from-fleet/  = incoming directives TO this agent
  - for-fleet/   = outgoing reports FROM this agent
  - for-oracle1/ = messages specifically for Oracle1
  - for-superz/  = messages specifically for Super Z

Problem: Bottles get sent but never acknowledged. This demoralizes
agents and breaks the coordination loop.

This checker scans vessel repositories for bottle directories,
tracks receipt and acknowledgment status, calculates latency
metrics, and flags orphan and stale bottles.

Usage:
    from bottle_hygiene.hygiene_checker import HygieneChecker

    checker = HygieneChecker(
        vessel_roots=["/path/to/superz-vessel",
                       "/path/to/oracle1-vessel"],
    )
    report = checker.run_check()
    report.save_json("hygiene-report.json")
    report.save_markdown("hygiene-report.md")

Or from the command line:
    python hygiene_checker.py --vessels /path/to/superz-vessel /path/to/oracle1-vessel
"""

import os
import re
import json
import time
import hashlib
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOTTLE_DIRS = ["from-fleet", "for-fleet", "for-oracle1", "for-superz"]
EXTENDED_BOTTLE_DIRS = [
    "from-fleet", "for-fleet", "for-oracle1", "for-superz",
    "for-jetsonclaw1", "for-babel", "for-new-agent", "for-any-vessel",
    "for-casey", "message-in-a-bottle",
]

STALE_THRESHOLD_HOURS = 48
UNANSWERED_THRESHOLD_HOURS = 24
ACKNOWLEDGMENT_KEYWORDS = [
    "ack", "acknowledg", "received", "confirm", "receipt",
    "got it", "roger", "copy that", "i see you", "thanks",
    "thank you", "i've read", "i have read", "noted",
    "understood", "will act", "on it", "working on",
]

ORPHAN_KEYWORDS = [
    "no response", "no reply", "unanswered", "waiting on",
    "ping", "following up", "bump", "check in", "any update",
]

DEFAULT_TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M UTC",
    "%Y-%m-%d %H:%M:%S UTC",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y%m%d",
]


class BottleDirection(Enum):
    INCOMING = "incoming"     # from-fleet/, etc.
    OUTGOING = "outgoing"     # for-fleet/, for-oracle1/, etc.


class BottleStatus(Enum):
    NEW = "new"                       # Freshly scanned, no status yet
    READ = "read"                     # Evidence agent read it
    ACKNOWLEDGED = "acknowledged"     # Explicit acknowledgment found
    ACTIONED = "actioned"             # Evidence of work being done
    STALE = "stale"                   # Too old with no action
    ORPHAN = "orphan"                 # Outgoing, never referenced
    UNANSWERED = "unanswered"         # Incoming, no response within threshold


@dataclass
class BottleMetadata:
    """Metadata extracted from a single bottle file."""
    path: str
    vessel_name: str
    bottle_dir: str
    direction: BottleDirection
    filename: str
    title: str = ""
    from_agent: str = ""
    to_agent: str = ""
    date_str: str = ""
    date_parsed: Optional[str] = None
    file_mtime: float = 0.0
    file_size: int = 0
    file_hash: str = ""
    content_preview: str = ""
    is_acknowledgment: bool = False
    references: List[str] = field(default_factory=list)
    priority: str = ""
    tags: List[str] = field(default_factory=list)
    status: BottleStatus = BottleStatus.NEW

    def to_dict(self) -> dict:
        d = asdict(self)
        d["direction"] = self.direction.value
        d["status"] = self.status.value
        return d


@dataclass
class AcknowledgmentLink:
    """A link between an outgoing bottle and a response."""
    bottle_path: str
    bottle_title: str
    response_path: str
    response_title: str
    latency_hours: float = 0.0
    response_type: str = ""  # ack, action, follow-up


@dataclass
class VesselHygieneSummary:
    """Aggregated hygiene metrics for a single vessel."""
    vessel_name: str
    vessel_path: str
    bottles_received: int = 0
    bottles_sent: int = 0
    bottles_acknowledged: int = 0
    bottles_unanswered: int = 0
    bottles_orphan: int = 0
    bottles_stale: int = 0
    avg_ack_latency_hours: float = 0.0
    max_ack_latency_hours: float = 0.0
    hygiene_score: float = 0.0  # 0.0 - 100.0
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HygieneReport:
    """Full hygiene report across all scanned vessels."""
    scan_timestamp: str = ""
    scan_epoch: float = 0.0
    vessels_scanned: int = 0
    total_bottles: int = 0
    total_acknowledged: int = 0
    total_unanswered: int = 0
    total_orphan: int = 0
    total_stale: int = 0
    fleet_ack_rate: float = 0.0
    fleet_hygiene_score: float = 0.0
    vessel_summaries: List[VesselHygieneSummary] = field(default_factory=list)
    all_bottles: List[dict] = field(default_factory=list)
    ack_links: List[dict] = field(default_factory=list)
    orphan_bottles: List[dict] = field(default_factory=list)
    stale_bottles: List[dict] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save_json(self, path: str) -> None:
        """Save report as JSON file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    def save_markdown(self, path: str) -> None:
        """Save report as a human-readable markdown file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        md = self._render_markdown()
        with open(path, "w") as f:
            f.write(md)

    def _render_markdown(self) -> str:
        """Render the full report as markdown."""
        lines: List[str] = []
        lines.append("# Bottle Hygiene Report")
        lines.append(f"\n**Scan Time:** {self.scan_timestamp}")
        lines.append(f"**Vessels Scanned:** {self.vessels_scanned}")
        lines.append(f"**Total Bottles:** {self.total_bottles}")
        lines.append("")

        # Fleet score banner
        lines.append("## Fleet Health Overview")
        lines.append("")
        score = self.fleet_hygiene_score
        if score >= 80:
            emoji = "green_heart"
        elif score >= 60:
            emoji = "yellow_heart"
        elif score >= 40:
            emoji = "orange_heart"
        else:
            emoji = "broken_heart"
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Fleet Hygiene Score | {score:.1f}/100 |")
        lines.append(f"| Total Bottles | {self.total_bottles} |")
        lines.append(f"| Acknowledged | {self.total_acknowledged} |")
        lines.append(f"| Unanswered (>24h) | {self.total_unanswered} |")
        lines.append(f"| Orphan (outgoing, no response) | {self.total_orphan} |")
        lines.append(f"| Stale (>48h, no action) | {self.total_stale} |")
        lines.append(f"| Fleet Ack Rate | {self.fleet_ack_rate:.1%} |")
        lines.append("")

        # Per-vessel breakdown
        if self.vessel_summaries:
            lines.append("## Per-Vessel Summary")
            lines.append("")
            lines.append("| Vessel | Received | Sent | Ack'd | Unanswered | Orphan | Stale | Score |")
            lines.append("|--------|----------|------|-------|------------|--------|-------|-------|")
            for vs in sorted(self.vessel_summaries, key=lambda v: v.hygiene_score):
                lines.append(
                    f"| {vs.vessel_name} | {vs.bottles_received} | "
                    f"{vs.bottles_sent} | {vs.bottles_acknowledged} | "
                    f"{vs.bottles_unanswered} | {vs.bottles_orphan} | "
                    f"{vs.bottles_stale} | {vs.hygiene_score:.1f} |"
                )
            lines.append("")

        # Alerts
        if self.alerts:
            lines.append("## Alerts")
            lines.append("")
            for alert in self.alerts:
                lines.append(f"- **{alert}**")
            lines.append("")

        # Orphan bottles
        if self.orphan_bottles:
            lines.append("## Orphan Bottles")
            lines.append("")
            lines.append("Outgoing bottles with no evidence of response:")
            lines.append("")
            for bottle in self.orphan_bottles[:20]:
                lines.append(
                    f"- `{bottle['vessel_name']}/{bottle['bottle_dir']}/{bottle['filename']}` "
                    f"(sent: {bottle.get('date_parsed', 'unknown')})"
                )
            if len(self.orphan_bottles) > 20:
                lines.append(f"- ... and {len(self.orphan_bottles) - 20} more")
            lines.append("")

        # Stale bottles
        if self.stale_bottles:
            lines.append("## Stale Directives")
            lines.append("")
            lines.append("Incoming bottles older than 48 hours with no evidence of action:")
            lines.append("")
            for bottle in self.stale_bottles[:20]:
                lines.append(
                    f"- `{bottle['vessel_name']}/{bottle['bottle_dir']}/{bottle['filename']}` "
                    f"(received: {bottle.get('date_parsed', 'unknown')})"
                )
            if len(self.stale_bottles) > 20:
                lines.append(f"- ... and {len(self.stale_bottles) - 20} more")
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # Acknowledgment latency
        if self.ack_links:
            lines.append("## Acknowledgment Latency")
            lines.append("")
            lines.append("| Bottle | Response | Latency |")
            lines.append("|--------|----------|---------|")
            for link in self.ack_links[:15]:
                bottle_name = link.get("bottle_title", link.get("bottle_path", "?"))
                resp_name = link.get("response_title", link.get("response_path", "?"))
                latency = link.get("latency_hours", 0)
                if latency < 1:
                    latency_str = f"{latency * 60:.0f}m"
                elif latency < 24:
                    latency_str = f"{latency:.1f}h"
                else:
                    latency_str = f"{latency / 24:.1f}d"
                lines.append(f"| {bottle_name} | {resp_name} | {latency_str} |")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated by Bottle Hygiene Checker at {self.scan_timestamp}*")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core Scanner
# ---------------------------------------------------------------------------

class HygieneChecker:
    """
    Scans vessel repositories for message-in-a-bottle directories,
    extracts metadata, and produces hygiene reports.

    The checker walks through each vessel looking for bottle directories,
    parses the markdown headers for metadata (date, from/to, priority),
    then cross-references bottles to find acknowledgment links,
    orphan bottles, and stale directives.
    """

    def __init__(
        self,
        vessel_roots: Optional[List[str]] = None,
        bottle_dirs: Optional[List[str]] = None,
        stale_threshold_hours: int = STALE_THRESHOLD_HOURS,
        unanswered_threshold_hours: int = UNANSWERED_THRESHOLD_HOURS,
        project_root: Optional[str] = None,
    ):
        self.vessel_roots = vessel_roots or []
        self.bottle_dirs = bottle_dirs or BOTTLE_DIRS
        self.stale_threshold = timedelta(hours=stale_threshold_hours)
        self.unanswered_threshold = timedelta(hours=unanswered_threshold_hours)
        self.project_root = project_root or os.getcwd()
        self._bottles: List[BottleMetadata] = []
        self._ack_links: List[AcknowledgmentLink] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover_vessels(self) -> List[str]:
        """
        Auto-discover vessel repositories under the project root.
        Looks for directories ending in '-vessel' or containing
        message-in-a-bottle directories.
        """
        discovered = []
        root = Path(self.project_root)

        # Strategy 1: directories named *-vessel
        for entry in sorted(root.iterdir()):
            if entry.is_dir() and entry.name.endswith("-vessel"):
                discovered.append(str(entry))

        # Strategy 2: directories with message-in-a-bottle subdirectory
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if any((entry / d).is_dir() for d in self.bottle_dirs):
                if str(entry) not in discovered:
                    discovered.append(str(entry))

            # Also check nested message-in-a-bottle/
            if (entry / "message-in-a-bottle").is_dir():
                if str(entry) not in discovered:
                    discovered.append(str(entry))

        # De-duplicate with provided roots
        for vr in self.vessel_roots:
            if vr not in discovered:
                discovered.append(vr)

        return discovered

    def run_check(self, vessel_roots: Optional[List[str]] = None) -> HygieneReport:
        """
        Run a full hygiene check across all vessels.

        Args:
            vessel_roots: Optional override of vessel paths to scan.
                          If None, uses self.vessel_roots or auto-discovers.

        Returns:
            A HygieneReport with all findings.
        """
        if vessel_roots is None:
            vessel_roots = self.vessel_roots

        if not vessel_roots:
            vessel_roots = self.discover_vessels()

        self._bottles = []
        self._ack_links = []

        # Phase 1: Scan all bottles
        vessel_summaries: List[VesselHygieneSummary] = []
        for vessel_path in vessel_roots:
            vessel_name = os.path.basename(vessel_path.rstrip("/"))
            summary = self._scan_vessel(vessel_name, vessel_path)
            vessel_summaries.append(summary)

        # Phase 2: Cross-reference for acknowledgment links
        self._find_acknowledgment_links()

        # Phase 3: Classify bottle statuses
        self._classify_bottles()

        # Phase 4: Build report
        report = self._build_report(vessel_summaries)

        return report

    def scan_single_vessel(self, vessel_path: str) -> VesselHygieneSummary:
        """Scan a single vessel and return its summary."""
        vessel_name = os.path.basename(vessel_path.rstrip("/"))
        return self._scan_vessel(vessel_name, vessel_path)

    def get_bottles_for_vessel(self, vessel_name: str) -> List[BottleMetadata]:
        """Return all bottles found for a given vessel name."""
        return [b for b in self._bottles if b.vessel_name == vessel_name]

    # ------------------------------------------------------------------
    # Phase 1: Scanning
    # ------------------------------------------------------------------

    def _scan_vessel(self, vessel_name: str, vessel_path: str) -> VesselHygieneSummary:
        """Scan a single vessel repository for bottles."""
        summary = VesselHygieneSummary(
            vessel_name=vessel_name,
            vessel_path=vessel_path,
        )

        vessel_dir = Path(vessel_path)
        if not vessel_dir.is_dir():
            summary.alerts.append(f"Vessel directory not found: {vessel_path}")
            return summary

        for bottle_dir_name in self.bottle_dirs:
            bottle_dir = vessel_dir / bottle_dir_name
            if not bottle_dir.is_dir():
                continue

            direction = self._classify_direction(bottle_dir_name)

            # Walk the bottle directory (may have subdirectories)
            for md_file in sorted(bottle_dir.rglob("*.md")):
                bottle = self._parse_bottle(
                    md_file, vessel_name, bottle_dir_name, direction
                )
                if bottle:
                    self._bottles.append(bottle)
                    self._update_summary(summary, bottle)

        # Calculate metrics
        self._calculate_vessel_metrics(summary)

        return summary

    def _classify_direction(self, bottle_dir_name: str) -> BottleDirection:
        """Determine if a bottle directory is incoming or outgoing."""
        if bottle_dir_name.startswith("from-"):
            return BottleDirection.INCOMING
        else:
            return BottleDirection.OUTGOING

    def _parse_bottle(
        self,
        md_file: Path,
        vessel_name: str,
        bottle_dir: str,
        direction: BottleDirection,
    ) -> Optional[BottleMetadata]:
        """Parse a single markdown bottle file and extract metadata."""
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except (IOError, OSError):
            return None

        stat = md_file.stat()
        file_hash = self._hash_content(content)

        metadata = BottleMetadata(
            path=str(md_file),
            vessel_name=vessel_name,
            bottle_dir=bottle_dir,
            direction=direction,
            filename=md_file.name,
            file_mtime=stat.st_mtime,
            file_size=stat.st_size,
            file_hash=file_hash,
            content_preview=content[:500].strip(),
        )

        # Extract header fields
        self._extract_headers(metadata, content)

        # Check if this bottle is itself an acknowledgment
        self._check_is_acknowledgment(metadata, content)

        # Extract references to other bottles
        self._extract_references(metadata, content)

        # Extract priority and tags
        self._extract_priority_and_tags(metadata, content)

        return metadata

    def _extract_headers(self, bottle: BottleMetadata, content: str) -> None:
        """Extract date, from/to from the markdown headers."""
        lines = content.split("\n")

        # First line is typically the title (# ...)
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and not bottle.title:
                bottle.title = stripped[2:].strip()
            elif stripped.startswith("## ") and not bottle.title:
                bottle.title = stripped[3:].strip()
            else:
                break

        # Parse key-value pairs from the header section
        header_section = "\n".join(lines[:30])  # Only check first 30 lines
        bottle.from_agent = self._extract_field(header_section, [
            r"\*\*From:\*\*\s*(.+)",
            r"From:\s*(.+)",
            r"Agent:\s*(.+)",
        ])
        bottle.to_agent = self._extract_field(header_section, [
            r"\*\*To:\*\*\s*(.+)",
            r"To:\s*(.+)",
        ])
        bottle.date_str = self._extract_field(header_section, [
            r"\*\*Date:\*\*\s*(.+)",
            r"Date:\s*(.+)",
        ])

        # Parse the date
        if bottle.date_str:
            bottle.date_parsed = self._parse_date(bottle.date_str)

        # If no parsed date, try from filename
        if not bottle.date_parsed:
            bottle.date_parsed = self._parse_date_from_filename(bottle.filename)

        # If still no date, use file mtime
        if not bottle.date_parsed:
            dt = datetime.fromtimestamp(bottle.file_mtime, tz=timezone.utc)
            bottle.date_parsed = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _extract_field(self, text: str, patterns: List[str]) -> str:
        """Try multiple regex patterns to extract a field value."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Clean up markdown artifacts
                value = re.sub(r"\*+", "", value).strip()
                value = value.rstrip("(Managing Director)").strip()
                value = value.rstrip("(Vessel)").strip()
                value = value.rstrip("(Lighthouse, SuperInstance)").strip()
                return value
        return ""

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse a date string into ISO format."""
        date_str = date_str.strip()

        # Remove parenthetical annotations
        date_str = re.sub(r"\s*\([^)]*\)\s*$", "", date_str).strip()

        for fmt in DEFAULT_TIMESTAMP_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        return None

    def _parse_date_from_filename(self, filename: str) -> Optional[str]:
        """Try to extract a date from the bottle filename."""
        # Pattern: YYYY-MM-DD or YYYYMMDD
        match = re.search(r"(\d{4})-?(\d{2})-?(\d{2})", filename)
        if match:
            year, month, day = match.groups()
            try:
                dt = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        return None

    def _check_is_acknowledgment(self, bottle: BottleMetadata, content: str) -> None:
        """Determine if this bottle is an acknowledgment of another."""
        lower = content.lower()
        # Check title
        title_lower = bottle.title.lower()
        ack_indicators = [
            "ack", "acknowledg", "receipt", "confirmed", "received",
            "got your", "i see you", "thank you for", "thanks for",
            "your work on", "well done", "nice work",
        ]
        for indicator in ack_indicators:
            if indicator in title_lower or indicator in lower[:300]:
                bottle.is_acknowledgment = True
                break

        # Check for ACK in filename
        if "ack" in bottle.filename.lower():
            bottle.is_acknowledgment = True

    def _extract_references(self, bottle: BottleMetadata, content: str) -> None:
        """Extract references to other bottles, PRs, issues, etc."""
        # Reference patterns: other bottle names, issue numbers, PR numbers
        refs = set()

        # Bottle filename references
        bottle_refs = re.findall(r"`([^`]*\.md)`", content)
        refs.update(bottle_refs)

        # Issue/PR references
        issue_refs = re.findall(r"#(\d+)", content)
        for ref in issue_refs:
            refs.add(f"#{ref}")

        # Agent name references (cross-vessel)
        agent_refs = re.findall(
            r"\b(Oracle1|Super[\s-]?Z|JetsonClaw1|Casey|Babel|Quill)\b",
            content, re.IGNORECASE,
        )
        refs.update(agent_refs)

        # Vessel name references
        vessel_refs = re.findall(r"(\w+-vessel)", content)
        refs.update(vessel_refs)

        bottle.references = sorted(refs)

    def _extract_priority_and_tags(
        self, bottle: BottleMetadata, content: str
    ) -> None:
        """Extract priority level and tags from the bottle content."""
        lower = content[:500].lower()

        # Priority detection
        priority_patterns = [
            (r"\*\*priority:\*\*\s*(\w+)", None),
            (r"priority:\s*(\w+)", None),
            (r"P(\d)\b", lambda m: f"P{m.group(1)}"),
            (r"(\uD83D\uDD34)", "P0"),
            (r"(\uD83D\uDFE5)", "P1"),
            (r"(\uD83D\uDFE1)", "P2"),
        ]

        for pattern, transform in priority_patterns:
            match = re.search(pattern, content[:500])
            if match:
                if transform:
                    bottle.priority = transform(match)
                else:
                    bottle.priority = match.group(1).strip()
                break

        # Tag detection
        tag_patterns = [
            r"\[([A-Z][A-Z0-9_-]{2,})\]",  # [TAG] patterns
            r"#(\w{3,})",                   # #hashtag patterns
        ]
        for pattern in tag_patterns:
            matches = re.findall(pattern, content[:500])
            for m in matches:
                if m.lower() not in ("welcome", "the", "for", "and", "not"):
                    bottle.tags.append(m)

        bottle.tags = list(dict.fromkeys(bottle.tags))  # deduplicate

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _update_summary(
        self, summary: VesselHygieneSummary, bottle: BottleMetadata
    ) -> None:
        """Update vessel summary with bottle data."""
        if bottle.direction == BottleDirection.INCOMING:
            summary.bottles_received += 1
        else:
            summary.bottles_sent += 1

        if bottle.is_acknowledgment:
            summary.bottles_acknowledged += 1

    def _calculate_vessel_metrics(self, summary: VesselHygieneSummary) -> None:
        """Calculate derived metrics for a vessel summary."""
        total_incoming = summary.bottles_received
        total_outgoing = summary.bottles_orphan

        if total_incoming > 0:
            ack_rate = summary.bottles_acknowledged / (total_incoming + total_outgoing)
            summary.fleet_ack_rate = ack_rate

        # Calculate hygiene score
        # Score is based on: ack rate, stale ratio, orphan ratio
        total = summary.bottles_received + summary.bottles_sent
        if total == 0:
            summary.hygiene_score = 100.0
            return

        ack_penalty = 0.0
        if summary.bottles_unanswered > 0:
            ack_penalty = min(
                30.0, (summary.bottles_unanswered / max(total, 1)) * 60
            )

        orphan_penalty = 0.0
        if summary.bottles_orphan > 0:
            orphan_penalty = min(
                20.0, (summary.bottles_orphan / max(total, 1)) * 40
            )

        stale_penalty = 0.0
        if summary.bottles_stale > 0:
            stale_penalty = min(
                25.0, (summary.bottles_stale / max(total, 1)) * 50
            )

        summary.hygiene_score = max(0.0, 100.0 - ack_penalty - orphan_penalty - stale_penalty)

    # ------------------------------------------------------------------
    # Phase 2: Cross-Referencing
    # ------------------------------------------------------------------

    def _find_acknowledgment_links(self) -> None:
        """Find links between bottles and their acknowledgments."""
        outgoing_bottles = [b for b in self._bottles if b.direction == BottleDirection.OUTGOING]
        all_bottles = self._bottles

        for outgoing in outgoing_bottles:
            potential_responses = []

            for candidate in all_bottles:
                if candidate.path == outgoing.path:
                    continue
                if not candidate.is_acknowledgment:
                    continue
                # Check if the candidate references this outgoing bottle
                if self._bottle_references(candidate, outgoing):
                    potential_responses.append(candidate)

            # Pick the earliest response as the acknowledgment
            if potential_responses:
                earliest = min(
                    potential_responses,
                    key=lambda b: b.date_parsed or "9999-12-31T00:00:00Z",
                )
                latency = self._calculate_latency(outgoing, earliest)
                link = AcknowledgmentLink(
                    bottle_path=outgoing.path,
                    bottle_title=outgoing.title or outgoing.filename,
                    response_path=earliest.path,
                    response_title=earliest.title or earliest.filename,
                    latency_hours=latency,
                    response_type="ack",
                )
                self._ack_links.append(link)

    def _bottle_references(
        self, candidate: BottleMetadata, target: BottleMetadata
    ) -> bool:
        """Check if a candidate bottle references the target bottle."""
        # Method 1: Direct filename reference
        if target.filename in candidate.references:
            return True

        # Method 2: Shared subject keywords
        target_keywords = set()
        if target.title:
            target_keywords.update(
                w.lower() for w in target.title.split()
                if len(w) > 3
            )

        candidate_text = (candidate.title + " " + candidate.content_preview).lower()
        matching_keywords = sum(
            1 for kw in target_keywords if kw in candidate_text
        )
        if matching_keywords >= 2:
            return True

        # Method 3: Agent name match (candidate is from target's recipient)
        if target.to_agent and target.to_agent.lower() in candidate.from_agent.lower():
            return True

        # Method 4: Date proximity + direction match
        if (candidate.direction == BottleDirection.INCOMING and
                target.direction == BottleDirection.OUTGOING):
            if target.date_parsed and candidate.date_parsed:
                try:
                    t_date = datetime.fromisoformat(
                        target.date_parsed.replace("Z", "+00:00")
                    )
                    c_date = datetime.fromisoformat(
                        candidate.date_parsed.replace("Z", "+00:00")
                    )
                    if abs((c_date - t_date).total_seconds()) < 86400 * 3:
                        # Within 3 days, likely a response
                        return True
                except (ValueError, OverflowError):
                    pass

        return False

    @staticmethod
    def _calculate_latency(
        bottle_a: BottleMetadata, bottle_b: BottleMetadata
    ) -> float:
        """Calculate hours between two bottle dates."""
        if not bottle_a.date_parsed or not bottle_b.date_parsed:
            return 0.0
        try:
            dt_a = datetime.fromisoformat(
                bottle_a.date_parsed.replace("Z", "+00:00")
            )
            dt_b = datetime.fromisoformat(
                bottle_b.date_parsed.replace("Z", "+00:00")
            )
            delta = abs((dt_b - dt_a).total_seconds())
            return delta / 3600.0
        except (ValueError, OverflowError):
            return 0.0

    # ------------------------------------------------------------------
    # Phase 3: Classification
    # ------------------------------------------------------------------

    def _classify_bottles(self) -> None:
        """Classify each bottle's status based on cross-references."""
        now = datetime.now(timezone.utc)

        # Track which bottles have been acknowledged (by being targets of ack links)
        acknowledged_paths = set()
        for link in self._ack_links:
            acknowledged_paths.add(link.bottle_path)

        for bottle in self._bottles:
            if bottle.path in acknowledged_paths:
                bottle.status = BottleStatus.ACKNOWLEDGED

            # Parse bottle date for age calculations
            bottle_dt = None
            if bottle.date_parsed:
                try:
                    bottle_dt = datetime.fromisoformat(
                        bottle.date_parsed.replace("Z", "+00:00")
                    )
                except (ValueError, OverflowError):
                    pass

            if not bottle_dt:
                bottle_dt = datetime.fromtimestamp(
                    bottle.file_mtime, tz=timezone.utc
                )

            age = now - bottle_dt

            # Classify incoming bottles
            if bottle.direction == BottleDirection.INCOMING:
                if bottle.status != BottleStatus.ACKNOWLEDGED:
                    if age > self.stale_threshold:
                        bottle.status = BottleStatus.STALE
                    elif age > self.unanswered_threshold:
                        bottle.status = BottleStatus.UNANSWERED
                    elif bottle.is_acknowledgment:
                        bottle.status = BottleStatus.READ
                    else:
                        bottle.status = BottleStatus.NEW

            # Classify outgoing bottles
            elif bottle.direction == BottleDirection.OUTGOING:
                if bottle.status != BottleStatus.ACKNOWLEDGED:
                    if age > self.unanswered_threshold:
                        bottle.status = BottleStatus.ORPHAN
                    else:
                        bottle.status = BottleStatus.NEW

    # ------------------------------------------------------------------
    # Phase 4: Report Building
    # ------------------------------------------------------------------

    def _build_report(
        self, vessel_summaries: List[VesselHygieneSummary]
    ) -> HygieneReport:
        """Build the final HygieneReport from collected data."""
        now = datetime.now(timezone.utc)

        # Recount from classified bottles
        total_acknowledged = sum(
            1 for b in self._bottles if b.status == BottleStatus.ACKNOWLEDGED
        )
        total_unanswered = sum(
            1 for b in self._bottles if b.status == BottleStatus.UNANSWERED
        )
        total_orphan = sum(
            1 for b in self._bottles if b.status == BottleStatus.ORPHAN
        )
        total_stale = sum(
            1 for b in self._bottles if b.status == BottleStatus.STALE
        )

        # Calculate ack latency stats
        latencies = [link.latency_hours for link in self._ack_links if link.latency_hours > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        # Update vessel summaries with final counts
        for summary in vessel_summaries:
            vessel_bottles = [
                b for b in self._bottles if b.vessel_name == summary.vessel_name
            ]
            summary.bottles_unanswered = sum(
                1 for b in vessel_bottles if b.status == BottleStatus.UNANSWERED
            )
            summary.bottles_orphan = sum(
                1 for b in vessel_bottles if b.status == BottleStatus.ORPHAN
            )
            summary.bottles_stale = sum(
                1 for b in vessel_bottles if b.status == BottleStatus.STALE
            )
            summary.bottles_acknowledged = sum(
                1 for b in vessel_bottles if b.status == BottleStatus.ACKNOWLEDGED
            )
            summary.avg_ack_latency_hours = avg_latency
            summary.max_ack_latency_hours = max_latency
            self._calculate_vessel_metrics(summary)

        # Fleet-wide ack rate
        total_bottles = len(self._bottles)
        actionable = sum(
            1 for b in self._bottles
            if b.direction == BottleDirection.INCOMING
        )
        fleet_ack_rate = (
            total_acknowledged / actionable if actionable > 0 else 1.0
        )

        # Fleet hygiene score
        if vessel_summaries:
            fleet_score = sum(vs.hygiene_score for vs in vessel_summaries) / len(vessel_summaries)
        else:
            fleet_score = 100.0

        # Build alerts
        alerts: List[str] = []
        for summary in vessel_summaries:
            if summary.hygiene_score < 50:
                alerts.append(
                    f"{summary.vessel_name} has low hygiene score ({summary.hygiene_score:.1f})"
                )
            if summary.bottles_stale > 0:
                alerts.append(
                    f"{summary.vessel_name} has {summary.bottles_stale} stale directive(s)"
                )
            if summary.bottles_orphan > 0:
                alerts.append(
                    f"{summary.vessel_name} has {summary.bottles_orphan} orphan bottle(s)"
                )

        # Build recommendations
        recommendations = self._generate_recommendations(
            vessel_summaries, total_unanswered, total_orphan, total_stale
        )

        # Orphan and stale bottle lists
        orphan_list = [
            b.to_dict() for b in self._bottles if b.status == BottleStatus.ORPHAN
        ]
        stale_list = [
            b.to_dict() for b in self._bottles if b.status == BottleStatus.STALE
        ]

        report = HygieneReport(
            scan_timestamp=now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            scan_epoch=now.timestamp(),
            vessels_scanned=len(vessel_summaries),
            total_bottles=total_bottles,
            total_acknowledged=total_acknowledged,
            total_unanswered=total_unanswered,
            total_orphan=total_orphan,
            total_stale=total_stale,
            fleet_ack_rate=fleet_ack_rate,
            fleet_hygiene_score=fleet_score,
            vessel_summaries=vessel_summaries,
            all_bottles=[b.to_dict() for b in self._bottles],
            ack_links=[asdict(l) for l in self._ack_links],
            orphan_bottles=orphan_list,
            stale_bottles=stale_list,
            alerts=alerts,
            recommendations=recommendations,
        )

        return report

    def _generate_recommendations(
        self,
        summaries: List[VesselHygieneSummary],
        total_unanswered: int,
        total_orphan: int,
        total_stale: int,
    ) -> List[str]:
        """Generate actionable recommendations based on findings."""
        recs: List[str] = []

        if total_unanswered > 0:
            recs.append(
                f"**{total_unanswered} bottle(s)** have gone unanswered for "
                f"over {self.unanswered_threshold.hours}h. Consider adding "
                f"auto-acknowledgment for incoming directives."
            )

        if total_orphan > 0:
            recs.append(
                f"**{total_orphan} outgoing bottle(s)** show no evidence of "
                f"being received or acknowledged. Verify the target vessel "
                f"is beachcombing the correct directories."
            )

        if total_stale > 0:
            recs.append(
                f"**{total_stale} incoming directive(s)** are older than "
                f"{self.stale_threshold.hours}h with no action taken. "
                f"Either act on them or explicitly decline."
            )

        # Per-vessel recommendations
        for summary in summaries:
            if summary.bottles_received > 0 and summary.bottles_acknowledged == 0:
                recs.append(
                    f"{summary.vessel_name}: No incoming bottles have been "
                    f"acknowledged. Start by sending acknowledgment bottles "
                    f"for each received directive."
                )

            if summary.bottles_sent > 0 and summary.avg_ack_latency_hours == 0:
                recs.append(
                    f"{summary.vessel_name}: No acknowledgment latency data "
                    f"available. Either no responses received, or responses "
                    f"don't match outgoing bottles."
                )

        if not recs:
            recs.append("Fleet bottle hygiene looks healthy. Keep beachcombing!")

        return recs


# ---------------------------------------------------------------------------
# Integration with Beachcomb
# ---------------------------------------------------------------------------

def create_beachcomb_sweep_for_hygiene(
    vessel_roots: List[str],
    interval_minutes: int = 60,
) -> dict:
    """
    Create a beachcomb sweep configuration for bottle hygiene checking.

    This can be added to a Beachcomber instance as a custom sweep.

    Returns a dict suitable for serialization and loading.
    """
    return {
        "name": "bottle-hygiene-check",
        "source_type": "custom",
        "source": ",".join(vessel_roots),
        "interval_minutes": interval_minutes,
        "on_find": "notify",
        "notify_channel": "none",
        "priority": "medium",
        "filter_pattern": "",
        "max_items": 50,
        "active": True,
        "metadata": {
            "handler": "bottle_hygiene.hygiene_checker.run_hygiene_sweep",
            "description": "Scan vessel repos for bottle hygiene issues",
        },
    }


def run_hygiene_sweep(vessel_roots: str) -> dict:
    """Entry point for beachcomb integration. vessel_roots is comma-separated."""
    roots = [r.strip() for r in vessel_roots.split(",") if r.strip()]
    checker = HygieneChecker(vessel_roots=roots)
    report = checker.run_check()
    return report.to_dict()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Bottle Hygiene Checker — scan vessel repos for bottle health",
    )
    parser.add_argument(
        "--vessels", "-v",
        nargs="+",
        default=[],
        help="Paths to vessel repositories (auto-discovers if not specified)",
    )
    parser.add_argument(
        "--project-root", "-p",
        default=None,
        help="Project root for vessel auto-discovery",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Directory to save report files (json + md)",
    )
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=STALE_THRESHOLD_HOURS,
        help=f"Hours before a directive is considered stale (default: {STALE_THRESHOLD_HOURS})",
    )
    parser.add_argument(
        "--unanswered-hours",
        type=int,
        default=UNANSWERED_THRESHOLD_HOURS,
        help=f"Hours before a bottle is considered unanswered (default: {UNANSWERED_THRESHOLD_HOURS})",
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output report as JSON to stdout",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output warnings and errors",
    )

    args = parser.parse_args()

    project_root = args.project_root or os.getcwd()
    checker = HygieneChecker(
        vessel_roots=args.vessels,
        stale_threshold_hours=args.stale_hours,
        unanswered_threshold_hours=args.unanswered_hours,
        project_root=project_root,
    )

    if not args.quiet:
        print("Bottle Hygiene Checker")
        print("=" * 40)

    # Auto-discover if no vessels specified
    if not args.vessels:
        discovered = checker.discover_vessels()
        if discovered:
            if not args.quiet:
                print(f"Auto-discovered {len(discovered)} vessel(s):")
                for v in discovered:
                    print(f"  - {v}")
        else:
            print("No vessel repositories found. Use --vessels to specify paths.")
            return

    # Run the check
    report = checker.run_check()

    if not args.quiet:
        print(f"\nScan complete: {report.vessels_scanned} vessels, "
              f"{report.total_bottles} bottles")
        print(f"Fleet Hygiene Score: {report.fleet_hygiene_score:.1f}/100")
        print(f"Acknowledged: {report.total_acknowledged}")
        print(f"Unanswered: {report.total_unanswered}")
        print(f"Orphan: {report.total_orphan}")
        print(f"Stale: {report.total_stale}")

        if report.alerts:
            print(f"\nAlerts ({len(report.alerts)}):")
            for alert in report.alerts:
                print(f"  ! {alert}")

        if report.recommendations:
            print(f"\nRecommendations:")
            for rec in report.recommendations:
                print(f"  -> {rec}")

    # Save to files
    if args.output_dir:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        json_path = os.path.join(args.output_dir, f"hygiene-report-{ts}.json")
        md_path = os.path.join(args.output_dir, f"hygiene-report-{ts}.md")
        report.save_json(json_path)
        report.save_markdown(md_path)
        if not args.quiet:
            print(f"\nReports saved to:")
            print(f"  JSON: {json_path}")
            print(f"  Markdown: {md_path}")

    # Output JSON to stdout if requested
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
