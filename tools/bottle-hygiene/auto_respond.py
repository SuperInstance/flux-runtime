r"""
Auto Respond — auto-generate acknowledgment bottles for received
directives in the FLUX fleet message-in-a-bottle protocol.

When agents send bottles and receive no acknowledgment, they feel
ignored and the coordination loop breaks. This tool provides:

1. A template system for common response types
2. Automatic detection of new, unacknowledged incoming bottles
3. Generation of acknowledgment bottle files in the correct directory
4. Integration with the BottleTracker for status updates

Usage:
    from bottle_hygiene.auto_respond import AutoResponder

    responder = AutoResponder(
        agent_name="superz",
        vessel_path="/path/to/superz-vessel",
    )

    # Auto-respond to all unacknowledged incoming bottles
    responses = responder.respond_to_unacknowledged()
    print(f"Generated {len(responses)} acknowledgment bottles")

    # Respond to a specific bottle
    response = responder.create_acknowledgment(
        bottle_path="from-fleet/ORACLE1-DIRECTIVE.md",
        response_type="received",
        note="Will prioritize conformance runner work.",
    )

CLI:
    python auto_respond.py --agent superz --vessel /path/to/vessel --dry-run
    python auto_respond.py --agent superz --vessel /path/to/vessel --type working
"""

import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Response Templates
# ---------------------------------------------------------------------------

RESPONSE_TEMPLATES: Dict[str, Dict] = {
    "received": {
        "title": "Acknowledgment — {bottle_title}",
        "icon": "inbox_tray",
        "body": (
            "Received your bottle. I've read it and logged the directive.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Received at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "— {agent_name}"
        ),
    },
    "working": {
        "title": "Working On It — {bottle_title}",
        "icon": "construction",
        "body": (
            "I've received your directive and have started working on it.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Status:** In progress\n"
            "**Started at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "I'll send an update when complete.\n\n"
            "— {agent_name}"
        ),
    },
    "completed": {
        "title": "Completed — {bottle_title}",
        "icon": "white_check_mark",
        "body": (
            "The task from your directive has been completed.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Completed at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "— {agent_name}"
        ),
    },
    "blocked": {
        "title": "Blocked — {bottle_title}",
        "icon": "warning",
        "body": (
            "I've received your directive but am blocked on execution.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Blocker:** {blocker_reason}\n"
            "**Identified at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "— {agent_name}"
        ),
    },
    "declined": {
        "title": "Declined — {bottle_title}",
        "icon": "no_entry_sign",
        "body": (
            "I've read your directive but am unable to take this on.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Reason:** {decline_reason}\n"
            "**Responded at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "— {agent_name}"
        ),
    },
    "question": {
        "title": "Question — {bottle_title}",
        "icon": "grey_question",
        "body": (
            "I've read your directive and have a question before proceeding.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Asked at:** {timestamp}\n\n"
            "**Question:**\n{custom_note}\n\n"
            "Please respond in `for-{agent_name}/` when you have a moment.\n\n"
            "— {agent_name}"
        ),
    },
    "checkin": {
        "title": "Check-in — {bottle_title}",
        "icon": "eyes",
        "body": (
            "Checking in on the status of your directive.\n\n"
            "**Bottle referenced:** `{bottle_filename}`\n"
            "**Checked at:** {timestamp}\n\n"
            "{custom_note}\n\n"
            "— {agent_name}"
        ),
    },
}

# Map from bottle_dir to response_dir
DIRECTION_RESPONSE_MAP = {
    "from-fleet": "for-fleet",
    "for-superz": "for-fleet",
    "for-oracle1": "for-oracle1",
    "for-jetsonclaw1": "for-jetsonclaw1",
    "for-babel": "for-babel",
    "for-casey": "for-fleet",
}


# ---------------------------------------------------------------------------
# Bottle Parsing Helpers
# ---------------------------------------------------------------------------

@dataclass
class ParsedBottle:
    """A parsed incoming bottle."""
    path: Path
    filename: str
    title: str
    from_agent: str
    to_agent: str
    date_str: str
    priority: str
    content: str


def parse_bottle_file(md_file: Path) -> Optional[ParsedBottle]:
    """Parse a markdown bottle file and extract key metadata."""
    try:
        content = md_file.read_text(encoding="utf-8", errors="replace")
    except (IOError, OSError):
        return None

    lines = content.split("\n")

    title = ""
    from_agent = ""
    to_agent = ""
    date_str = ""
    priority = ""

    header_text = "\n".join(lines[:30])

    # Title from first heading
    for line in lines:
        s = line.strip()
        if s.startswith("# "):
            title = s[2:].strip()
            break

    # Key-value extraction
    for pattern, target in [
        (r"\*\*From:\*\*\s*(.+)", "from_agent"),
        (r"From:\s*(.+)", "from_agent"),
        (r"\*\*To:\*\*\s*(.+)", "to_agent"),
        (r"To:\s*(.+)", "to_agent"),
        (r"\*\*Date:\*\*\s*(.+)", "date_str"),
        (r"Date:\s*(.+)", "date_str"),
        (r"\*\*Priority:\*\*\s*(\w+)", "priority"),
        (r"Priority:\s*(\w+)", "priority"),
    ]:
        match = re.search(pattern, header_text, re.IGNORECASE)
        if match and not locals().get(target.replace("_agent", "_agent")):
            val = match.group(1).strip()
            val = re.sub(r"\*+", "", val).strip()
            if target == "from_agent":
                from_agent = val
            elif target == "to_agent":
                to_agent = val
            elif target == "date_str":
                date_str = val
            elif target == "priority":
                priority = val

    # Clean from_agent
    from_agent = re.sub(
        r"\s*\(.*?\)\s*$", "", from_agent
    ).strip()

    return ParsedBottle(
        path=md_file,
        filename=md_file.name,
        title=title,
        from_agent=from_agent,
        to_agent=to_agent,
        date_str=date_str,
        priority=priority,
        content=content,
    )


# ---------------------------------------------------------------------------
# Auto Responder
# ---------------------------------------------------------------------------

class AutoResponder:
    """
    Generates acknowledgment bottles for received directives.

    Scans incoming bottle directories (from-fleet/, for-superz/, etc.),
    identifies bottles that haven't been acknowledged yet, and creates
    response bottle files in the appropriate outgoing directories.
    """

    def __init__(
        self,
        agent_name: str,
        vessel_path: str,
        dry_run: bool = False,
        default_response_type: str = "received",
        tracker_db: Optional[str] = None,
    ):
        self.agent_name = agent_name.lower().replace(" ", "-")
        self.vessel_path = Path(vessel_path)
        self.dry_run = dry_run
        self.default_response_type = default_response_type
        self.tracker_db = tracker_db
        self._existing_responses: Optional[set] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def respond_to_unacknowledged(
        self,
        response_type: Optional[str] = None,
        note: Optional[str] = None,
        bottle_dirs: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Find all unacknowledged incoming bottles and generate responses.

        Returns a list of dicts with keys:
            bottle_path, response_path, response_type, content
        """
        if bottle_dirs is None:
            bottle_dirs = ["from-fleet", f"for-{self.agent_name}"]

        incoming = self._find_incoming_bottles(bottle_dirs)
        responses = []

        for bottle in incoming:
            if self._is_already_acknowledged(bottle):
                continue

            response = self.create_acknowledgment(
                bottle_path=str(bottle.path),
                response_type=response_type or self.default_response_type,
                note=note,
            )
            if response:
                responses.append(response)

        return responses

    def create_acknowledgment(
        self,
        bottle_path: str,
        response_type: str = "received",
        note: Optional[str] = None,
        blocker_reason: Optional[str] = None,
        decline_reason: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Create an acknowledgment bottle for a specific incoming bottle.

        Args:
            bottle_path: Path to the incoming bottle file.
            response_type: One of the template keys (received, working, etc.)
            note: Custom note to include in the response.
            blocker_reason: Required if response_type is "blocked".
            decline_reason: Required if response_type is "declined".

        Returns:
            Dict with response metadata, or None if the bottle couldn't be parsed.
        """
        bottle_file = Path(bottle_path)
        if not bottle_file.exists():
            return None

        parsed = parse_bottle_file(bottle_file)
        if not parsed:
            return None

        # Determine the response directory
        response_dir = self._get_response_dir(bottle_file)
        if not response_dir:
            return None

        # Generate the response content
        content = self._render_response(
            parsed=parsed,
            response_type=response_type,
            note=note or "",
            blocker_reason=blocker_reason or "",
            decline_reason=decline_reason or "",
        )

        # Generate filename
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
        safe_title = re.sub(
            r"[^a-zA-Z0-9-]", "-", parsed.title[:40]
        ).strip("-").lower()
        response_filename = f"ACK-{timestamp}-{safe_title}.md"
        response_path = response_dir / response_filename

        result = {
            "bottle_path": str(bottle_file),
            "bottle_filename": parsed.filename,
            "bottle_title": parsed.title,
            "from_agent": parsed.from_agent,
            "response_type": response_type,
            "response_path": str(response_path),
            "response_filename": response_filename,
            "content": content,
            "dry_run": self.dry_run,
        }

        if not self.dry_run:
            # Write the response bottle
            response_dir.mkdir(parents=True, exist_ok=True)
            response_path.write_text(content, encoding="utf-8")
            result["written"] = True

            # Update tracker if available
            if self.tracker_db:
                self._update_tracker(parsed, response_filename)
        else:
            result["written"] = False

        return result

    def create_batch_responses(
        self,
        bottle_paths: List[str],
        response_type: str = "received",
        note: Optional[str] = None,
    ) -> List[Dict]:
        """Create acknowledgment bottles for a batch of incoming bottles."""
        responses = []
        for bp in bottle_paths:
            resp = self.create_acknowledgment(
                bottle_path=bp,
                response_type=response_type,
                note=note,
            )
            if resp:
                responses.append(resp)
        return responses

    def list_pending_responses(
        self,
        bottle_dirs: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        List incoming bottles that haven't been acknowledged yet.

        Returns a list of dicts with bottle metadata, without creating
        any response files.
        """
        if bottle_dirs is None:
            bottle_dirs = ["from-fleet", f"for-{self.agent_name}"]

        incoming = self._find_incoming_bottles(bottle_dirs)
        pending = []

        for bottle in incoming:
            if not self._is_already_acknowledged(bottle):
                pending.append({
                    "path": str(bottle.path),
                    "filename": bottle.filename,
                    "title": bottle.title,
                    "from_agent": bottle.from_agent,
                    "date_str": bottle.date_str,
                    "priority": bottle.priority,
                })

        return pending

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find_incoming_bottles(self, bottle_dirs: List[str]) -> List[ParsedBottle]:
        """Find and parse all incoming bottles."""
        bottles = []
        for dir_name in bottle_dirs:
            dir_path = self.vessel_path / dir_name
            if not dir_path.is_dir():
                continue

            for md_file in sorted(dir_path.rglob("*.md")):
                parsed = parse_bottle_file(md_file)
                if parsed:
                    bottles.append(parsed)

        return bottles

    def _is_already_acknowledged(self, bottle: ParsedBottle) -> bool:
        """Check if there's already an acknowledgment for this bottle."""
        # Look for ACK files that reference this bottle
        for out_dir_name in ["for-fleet", "for-oracle1", "for-jetsonclaw1"]:
            out_dir = self.vessel_path / out_dir_name
            if not out_dir.is_dir():
                continue

            for ack_file in out_dir.rglob("ACK-*.md"):
                try:
                    content = ack_file.read_text(encoding="utf-8", errors="replace")
                    if bottle.filename in content:
                        return True
                    if bottle.title and bottle.title.lower() in content.lower()[:200]:
                        return True
                except (IOError, OSError):
                    continue

        # Also check for "ACK" in existing responses
        for out_dir_name in ["for-fleet", "for-oracle1"]:
            out_dir = self.vessel_path / out_dir_name
            if not out_dir.is_dir():
                continue
            for resp_file in out_dir.rglob("*.md"):
                if "ack" in resp_file.stem.lower():
                    try:
                        content = resp_file.read_text(encoding="utf-8", errors="replace")
                        if bottle.from_agent.lower() in content.lower()[:300]:
                            return True
                    except (IOError, OSError):
                        continue

        return False

    def _get_response_dir(self, bottle_file: Path) -> Optional[Path]:
        """Determine which directory to write the response to."""
        # Get the relative path from vessel root
        try:
            rel = bottle_file.relative_to(self.vessel_path)
        except ValueError:
            return None

        parts = rel.parts
        if not parts:
            return None

        bottle_dir_name = parts[0]

        # Direct mapping
        if bottle_dir_name in DIRECTION_RESPONSE_MAP:
            response_dir_name = DIRECTION_RESPONSE_MAP[bottle_dir_name]
        elif bottle_dir_name.startswith("for-"):
            # This is a message TO us from a specific agent
            target = bottle_dir_name.replace("for-", "")
            response_dir_name = f"for-{target}"
        else:
            response_dir_name = "for-fleet"

        return self.vessel_path / response_dir_name

    def _render_response(
        self,
        parsed: ParsedBottle,
        response_type: str,
        note: str,
        blocker_reason: str,
        decline_reason: str,
    ) -> str:
        """Render a response bottle using the template system."""
        template = RESPONSE_TEMPLATES.get(response_type)
        if not template:
            template = RESPONSE_TEMPLATES["received"]

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        # Fill in custom note
        if not note:
            if response_type == "received":
                note = "Will review and respond with status updates."
            elif response_type == "working":
                note = "Working through the requirements now."
            elif response_type == "completed":
                note = "All tasks from this directive have been addressed."
            elif response_type == "checkin":
                note = "Just checking if there are any updates needed on this."

        # Render the body
        body = template["body"].format(
            bottle_title=parsed.title or parsed.filename,
            bottle_filename=parsed.filename,
            timestamp=timestamp,
            agent_name=self.agent_name.title(),
            custom_note=note,
            blocker_reason=blocker_reason,
            decline_reason=decline_reason,
        )

        # Assemble the full bottle
        title = template["title"].format(
            bottle_title=parsed.title or parsed.filename,
        )

        # Clean the title
        title = re.sub(r"\s+", " ", title).strip()

        # Build the markdown
        lines = [
            f"# {title}",
            "",
            f"**From:** {self.agent_name.title()}",
            f"**To:** {parsed.from_agent or 'Fleet'}",
            f"**Date:** {timestamp}",
            f"**Response Type:** {response_type}",
            "",
            body,
            "",
        ]

        # Add a reference section
        lines.extend([
            "---",
            f"*Auto-generated acknowledgment for `{parsed.filename}`*",
            f"*Original bottle: `{parsed.path}`*",
        ])

        return "\n".join(lines)

    def _update_tracker(self, parsed: ParsedBottle, response_filename: str) -> None:
        """Update the bottle tracker database with the acknowledgment."""
        if not self.tracker_db or not os.path.exists(self.tracker_db):
            return

        try:
            import sqlite3
            conn = sqlite3.connect(self.tracker_db)
            # Try to find and update the bottle record
            conn.execute(
                """UPDATE bottles SET status = 'acknowledged', acked_at = ?,
                   acked_by = ?, last_updated = ?
                   WHERE filename = ? AND vessel_name = ?""",
                (
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    self.agent_name,
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    parsed.filename,
                    self.vessel_path.name,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            import sys
            print(f"Warning: tracker update failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def generate_response_types() -> Dict[str, str]:
    """Return available response types and their descriptions."""
    descriptions = {
        "received": "Simple acknowledgment that you've received and read the bottle",
        "working": "Indicates you're actively working on the directive",
        "completed": "Marks the directive's tasks as completed",
        "blocked": "Reports a blocker preventing execution",
        "declined": "Politely declines the directive with a reason",
        "question": "Asks a clarifying question about the directive",
        "checkin": "Periodic check-in on a long-running directive",
    }
    return descriptions


def suggest_response_type(bottle_content: str) -> str:
    """
    Analyze bottle content and suggest an appropriate response type.

    This is a heuristic — it looks for keywords and patterns
    that indicate what kind of response is most appropriate.
    """
    lower = bottle_content.lower()

    # If it's a simple dispatch/info, just acknowledge
    if any(kw in lower for kw in ["status update", "fyi", "for your info",
                                   "just so you know", "broadcast"]):
        return "received"

    # If it's a task assignment
    if any(kw in lower for kw in ["your task", "your priority", "please do",
                                   "you should", "orders", "directive",
                                   "assignment", "red priority", "p0"]):
        return "working"

    # If it contains questions
    if any(kw in lower for kw in ["what do you", "your thoughts", "?",
                                   "how would you", "can you explain"]):
        return "question"

    # If it's a follow-up
    if any(kw in lower for kw in ["following up", "any update", "status",
                                   "progress check", "check in"]):
        return "checkin"

    return "received"


def create_response_from_report(
    report: dict,
    agent_name: str,
    vessel_path: str,
    dry_run: bool = False,
) -> List[Dict]:
    """
    Create responses for all unanswered bottles found in a hygiene report.

    Convenience function that combines HygieneChecker output with
    AutoResponder for a one-shot batch response.
    """
    responder = AutoResponder(
        agent_name=agent_name,
        vessel_path=vessel_path,
        dry_run=dry_run,
    )

    unanswered = [
        b for b in report.get("all_bottles", [])
        if b.get("status") in ("unanswered", "stale")
        and b.get("direction") == "incoming"
    ]

    responses = []
    for bottle in unanswered:
        bottle_path = bottle.get("path", "")
        if not bottle_path:
            continue

        # Suggest response type based on content
        content = bottle.get("content_preview", "")
        response_type = suggest_response_type(content)

        resp = responder.create_acknowledgment(
            bottle_path=bottle_path,
            response_type=response_type,
        )
        if resp:
            responses.append(resp)

    return responses


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-generate acknowledgment bottles for fleet messages"
    )
    parser.add_argument(
        "--agent", "-a",
        required=True,
        help="Your agent name (e.g., superz, oracle1)",
    )
    parser.add_argument(
        "--vessel", "-v",
        required=True,
        help="Path to your vessel repository",
    )
    parser.add_argument(
        "--type", "-t",
        default=None,
        choices=list(RESPONSE_TEMPLATES.keys()),
        help="Response type (default: auto-detected per bottle)",
    )
    parser.add_argument(
        "--note", "-n",
        default=None,
        help="Custom note to include in responses",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files",
    )
    parser.add_argument(
        "--list-pending",
        action="store_true",
        help="Only list pending responses, don't generate",
    )
    parser.add_argument(
        "--tracker-db",
        default=None,
        help="Path to bottle tracker database for status updates",
    )

    args = parser.parse_args()

    responder = AutoResponder(
        agent_name=args.agent,
        vessel_path=args.vessel,
        dry_run=args.dry_run,
        default_response_type=args.type or "received",
        tracker_db=args.tracker_db,
    )

    if args.list_pending:
        pending = responder.list_pending_responses()
        if pending:
            print(f"Pending acknowledgments ({len(pending)}):")
            for p in pending:
                from_str = f" from {p['from_agent']}" if p.get("from_agent") else ""
                print(f"  - {p['filename']}{from_str}")
                if p.get("title"):
                    print(f"    {p['title'][:80]}")
                if p.get("priority"):
                    print(f"    Priority: {p['priority']}")
        else:
            print("No pending acknowledgments found. Bottle hygiene is good!")
        return

    # Generate responses
    responses = responder.respond_to_unacknowledged(
        response_type=args.type,
        note=args.note,
    )

    if responses:
        action = "Would generate" if args.dry_run else "Generated"
        print(f"{action} {len(responses)} acknowledgment bottle(s):")
        for resp in responses:
            status = "[DRY RUN] " if args.dry_run else "[WRITTEN] "
            print(f"  {status}{resp['response_filename']}")
            print(f"    Response to: {resp['bottle_filename']}")
            print(f"    Type: {resp['response_type']}")
            print(f"    Path: {resp['response_path']}")
            print()
    else:
        print("No unacknowledged bottles found. All clear!")


if __name__ == "__main__":
    main()
