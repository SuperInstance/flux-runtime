#!/usr/bin/env python3
"""
FLUX Fleet Knowledge Federation — Query Tool v2.0

A structured knowledge base that any fleet agent can query for conformance
findings, security specs, ISA design decisions, performance data, fleet
organization, and onboarding information.

Usage:
    python knowledge-query.py [--domain isa] [--keyword opcode] [--confidence 0.8] [--export] [--stats] [--add]
    python knowledge-query.py --list-domains
    python knowledge-query.py --id isa-v3-escape

Author: Super Z (FLUX Fleet — Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    """A single knowledge base entry."""
    id: str
    fact: str
    confidence: float
    source: str
    date: str
    tags: list[str] = field(default_factory=list)
    domain: str = ""

    def matches_keyword(self, keyword: str) -> bool:
        """Case-insensitive keyword match against fact, id, source, and tags."""
        k = keyword.lower()
        return (
            k in self.fact.lower()
            or k in self.id.lower()
            or k in self.source.lower()
            or any(k in t.lower() for t in self.tags)
        )

    def __str__(self) -> str:
        conf_bar = self._confidence_bar()
        tag_str = ", ".join(self.tags) if self.tags else "—"
        return (
            f"  [{self.id}]\n"
            f"    Fact: {self.fact}\n"
            f"    Confidence: {self.confidence:.2f} {conf_bar}\n"
            f"    Source: {self.source} | Date: {self.date}\n"
            f"    Tags: {tag_str}\n"
        )

    def _confidence_bar(self) -> str:
        filled = int(self.confidence * 10)
        return "[" + "#" * filled + "." * (10 - filled) + "]"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("domain", None)
        return d


# ---------------------------------------------------------------------------
# Knowledge Federation core
# ---------------------------------------------------------------------------

class KnowledgeFederation:
    """Federated knowledge base for the FLUX fleet."""

    def __init__(self, kb_path: str):
        """Load knowledge base from JSON file.

        Args:
            kb_path: Path to knowledge-base.json.
        """
        self.kb_path = Path(kb_path)
        if not self.kb_path.exists():
            raise FileNotFoundError(
                f"Knowledge base not found: {self.kb_path}\n"
                f"Run from the knowledge-federation directory or provide --kb-path."
            )
        with open(self.kb_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        self._version = self._data.get("version", "unknown")
        self._last_updated = self._data.get("last_updated", "unknown")
        # Build flat entry list with domain annotation
        self._entries: list[Entry] = []
        for domain_name, domain_data in self._data.get("domains", {}).items():
            label = domain_data.get("label", domain_name)
            for raw in domain_data.get("entries", []):
                entry = Entry(
                    id=raw["id"],
                    fact=raw["fact"],
                    confidence=raw.get("confidence", 0.5),
                    source=raw.get("source", "unknown"),
                    date=raw.get("date", "unknown"),
                    tags=raw.get("tags", []),
                    domain=domain_name,
                )
                self._entries.append(entry)

    # ---- Query methods ----

    def query(
        self,
        domain: Optional[str] = None,
        keyword: Optional[str] = None,
        entry_id: Optional[str] = None,
    ) -> list[Entry]:
        """Search by domain, keyword, and/or entry ID.

        Args:
            domain: Domain name (isa, conformance, security, performance, fleet, bootcamp).
                    None means all domains.
            keyword: Case-insensitive keyword to search in facts, IDs, sources, tags.
            entry_id: Exact entry ID match.

        Returns:
            List of matching entries sorted by confidence descending.
        """
        results = list(self._entries)

        if entry_id:
            results = [e for e in results if e.id == entry_id]
            return sorted(results, key=lambda e: e.confidence, reverse=True)

        if domain:
            domain_lower = domain.lower()
            results = [e for e in results if e.domain == domain_lower]

        if keyword:
            results = [e for e in results if e.matches_keyword(keyword)]

        return sorted(results, key=lambda e: e.confidence, reverse=True)

    def get_high_confidence(
        self, domain: Optional[str] = None, min_confidence: float = 0.8
    ) -> list[Entry]:
        """Filter entries by minimum confidence threshold.

        Args:
            domain: Optional domain filter.
            min_confidence: Minimum confidence value (0.0-1.0).

        Returns:
            Entries at or above the confidence threshold, sorted descending.
        """
        results = self.query(domain=domain)
        return [e for e in results if e.confidence >= min_confidence]

    def get_by_tag(self, tag: str, domain: Optional[str] = None) -> list[Entry]:
        """Search entries by tag.

        Args:
            tag: Tag string to match.
            domain: Optional domain filter.

        Returns:
            Matching entries sorted by confidence descending.
        """
        results = self.query(domain=domain)
        tag_lower = tag.lower()
        return sorted(
            [e for e in results if any(tag_lower in t.lower() for t in e.tags)],
            key=lambda e: e.confidence,
            reverse=True,
        )

    # ---- Mutation methods ----

    def add_entry(
        self,
        domain: str,
        fact: str,
        source: str,
        confidence: float = 0.5,
        tags: Optional[list[str]] = None,
        entry_id: Optional[str] = None,
    ) -> Entry:
        """Add a new knowledge entry.

        Args:
            domain: Target domain (isa, conformance, security, performance, fleet, bootcamp).
            fact: The knowledge fact string.
            source: Source of the knowledge.
            confidence: Confidence score 0.0-1.0 (default 0.5).
            tags: Optional list of tags.
            entry_id: Optional custom entry ID (auto-generated if not provided).

        Returns:
            The newly created Entry.
        """
        if domain not in self._data["domains"]:
            raise ValueError(
                f"Unknown domain '{domain}'. "
                f"Valid domains: {list(self._data['domains'].keys())}"
            )
        confidence = max(0.0, min(1.0, confidence))
        today = date.today().isoformat()

        if not entry_id:
            # Auto-generate: domain prefix + 4-char hash of fact
            short_hash = hex(hash(fact) & 0xFFFF)[2:].zfill(4)
            entry_id = f"{domain}-auto-{short_hash}"

        # Check for duplicate ID
        existing_ids = {e.id for e in self._entries}
        if entry_id in existing_ids:
            raise ValueError(f"Entry ID '{entry_id}' already exists")

        entry = Entry(
            id=entry_id,
            fact=fact,
            confidence=confidence,
            source=source,
            date=today,
            tags=tags or [],
            domain=domain,
        )

        # Add to in-memory data
        self._data["domains"][domain]["entries"].append(entry.to_dict())
        self._entries.append(entry)

        return entry

    def save(self, path: Optional[str] = None):
        """Persist the knowledge base to disk.

        Args:
            path: Output path (defaults to original kb_path).
        """
        out_path = Path(path) if path else self.kb_path
        self._data["last_updated"] = date.today().isoformat()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        print(f"Knowledge base saved to {out_path}")

    # ---- Reporting methods ----

    def export_markdown(self) -> str:
        """Export the full knowledge base as readable markdown.

        Returns:
            Markdown string with all entries organized by domain.
        """
        lines = [
            "# FLUX Fleet Knowledge Federation",
            "",
            f"**Version:** {self._version}  ",
            f"**Last Updated:** {self._last_updated}  ",
            f"**Total Entries:** {len(self._entries)}  ",
            "",
            "---",
            "",
        ]

        for domain_name, domain_data in self._data.get("domains", {}).items():
            label = domain_data.get("label", domain_name)
            domain_entries = sorted(
                self.query(domain=domain_name),
                key=lambda e: e.confidence,
                reverse=True,
            )
            lines.append(f"## {label} (`{domain_name}`)")
            lines.append("")
            lines.append(f"**{len(domain_entries)} entries**")
            lines.append("")

            for entry in domain_entries:
                conf_bar = entry._confidence_bar()
                tag_str = ", ".join(f"`{t}`" for t in entry.tags) if entry.tags else ""
                lines.append(f"### {entry.id}")
                lines.append("")
                lines.append(f"> {entry.fact}")
                lines.append("")
                lines.append(f"| Field | Value |")
                lines.append(f"|-------|-------|")
                lines.append(f"| Confidence | {entry.confidence:.2f} {conf_bar} |")
                lines.append(f"| Source | {entry.source} |")
                lines.append(f"| Date | {entry.date} |")
                if tag_str:
                    lines.append(f"| Tags | {tag_str} |")
                lines.append("")

        return "\n".join(lines)

    def stats(self) -> dict:
        """Compute domain sizes, confidence distributions, and coverage gaps.

        Returns:
            Dictionary with statistics.
        """
        domain_counts: dict[str, int] = {}
        domain_avg_conf: dict[str, float] = {}
        conf_distribution = {"high": 0, "medium": 0, "low": 0}
        source_counts: dict[str, int] = {}
        tag_counts: dict[str, int] = {}

        for entry in self._entries:
            # Domain counts
            domain_counts[entry.domain] = domain_counts.get(entry.domain, 0) + 1
            domain_avg_conf.setdefault(entry.domain, []).append(entry.confidence)

            # Confidence distribution
            if entry.confidence >= 0.8:
                conf_distribution["high"] += 1
            elif entry.confidence >= 0.5:
                conf_distribution["medium"] += 1
            else:
                conf_distribution["low"] += 1

            # Source counts
            source_counts[entry.source] = source_counts.get(entry.source, 0) + 1

            # Tag counts
            for t in entry.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        # Average confidence per domain
        domain_avg = {
            d: sum(vals) / len(vals) for d, vals in domain_avg_conf.items()
        }

        # Top tags
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # Coverage gap analysis: which tags have few entries
        all_tags = set(tag_counts.keys())
        single_entry_tags = [t for t, c in tag_counts.items() if c == 1]

        return {
            "total_entries": len(self._entries),
            "total_domains": len(domain_counts),
            "domain_counts": domain_counts,
            "domain_avg_confidence": {k: round(v, 3) for k, v in domain_avg.items()},
            "confidence_distribution": conf_distribution,
            "top_sources": dict(
                sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "total_unique_tags": len(all_tags),
            "top_tags": top_tags,
            "single_entry_tags": single_entry_tags[:20],
            "coverage_gaps": self._identify_coverage_gaps(domain_counts),
        }

    def _identify_coverage_gaps(self, domain_counts: dict[str, int]) -> list[str]:
        """Identify domains and areas with low entry counts."""
        gaps = []
        expected_min = 5
        for domain, count in domain_counts.items():
            if count < expected_min:
                gaps.append(
                    f"Domain '{domain}' has only {count} entries (recommended: >= {expected_min})"
                )
        return gaps

    def list_domains(self) -> dict[str, str]:
        """List all domains with their labels.

        Returns:
            Dict mapping domain name to label.
        """
        return {
            name: data.get("label", name)
            for name, data in self._data.get("domains", {}).items()
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FLUX Fleet Knowledge Federation Query Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all domains
  python knowledge-query.py --list-domains

  # Query ISA domain for 'opcode' keyword
  python knowledge-query.py --domain isa --keyword opcode

  # High-confidence security entries
  python knowledge-query.py --domain security --confidence 0.9

  # Export full knowledge base as markdown
  python knowledge-query.py --export > federation-export.md

  # Get statistics
  python knowledge-query.py --stats

  # Add a new entry
  python knowledge-query.py --add --domain isa --fact "ADD is 0x20" --source "manual" --confidence 1.0 --tags arithmetic,opcode

  # Lookup by exact ID
  python knowledge-query.py --id sec-3-critical-issues
        """,
    )

    parser.add_argument(
        "--kb-path",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge-base.json"),
        help="Path to knowledge-base.json (default: same directory as this script)",
    )
    parser.add_argument(
        "--domain", "-d",
        help="Domain to query (isa, conformance, security, performance, fleet, bootcamp)",
    )
    parser.add_argument(
        "--keyword", "-k",
        help="Keyword to search (case-insensitive, matched against facts, IDs, sources, tags)",
    )
    parser.add_argument(
        "--confidence", "-c",
        type=float,
        default=None,
        help="Minimum confidence threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export full knowledge base as markdown to stdout",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show knowledge base statistics",
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="List all available domains",
    )
    parser.add_argument(
        "--id",
        help="Lookup entry by exact ID",
    )
    parser.add_argument(
        "--add",
        action="store_true",
        help="Add a new entry (requires --domain, --fact, --source)",
    )
    parser.add_argument("--fact", help="Fact string (for --add)")
    parser.add_argument("--source", help="Source string (for --add)")
    parser.add_argument(
        "--tags",
        help="Comma-separated tags (for --add)",
    )
    parser.add_argument(
        "--add-confidence",
        type=float,
        default=0.5,
        help="Confidence for new entry (default: 0.5, for --add)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save changes back to knowledge-base.json",
    )

    args = parser.parse_args()

    # Load knowledge base
    try:
        kf = KnowledgeFederation(args.kb_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # List domains
    if args.list_domains:
        domains = kf.list_domains()
        print("Available domains:")
        for name, label in domains.items():
            count = len(kf.query(domain=name))
            print(f"  {name:20s} — {label} ({count} entries)")
        sys.exit(0)

    # Export markdown
    if args.export:
        print(kf.export_markdown())
        sys.exit(0)

    # Statistics
    if args.stats:
        s = kf.stats()
        print("=" * 60)
        print("  FLUX FLEET KNOWLEDGE FEDERATION — STATISTICS")
        print("=" * 60)
        print(f"\n  Total entries:   {s['total_entries']}")
        print(f"  Total domains:   {s['total_domains']}")
        print(f"  Unique tags:     {s['total_unique_tags']}")

        print("\n  Domain breakdown:")
        for domain, count in s["domain_counts"].items():
            avg = s["domain_avg_confidence"].get(domain, 0)
            bar = "#" * int(avg * 20)
            print(f"    {domain:15s}  {count:3d} entries  avg conf: {avg:.2f} {bar}")

        print("\n  Confidence distribution:")
        print(f"    High   (>= 0.80): {s['confidence_distribution']['high']:3d}")
        print(f"    Medium (0.50-0.79): {s['confidence_distribution']['medium']:3d}")
        print(f"    Low    (< 0.50): {s['confidence_distribution']['low']:3d}")

        print("\n  Top tags:")
        for tag, count in s["top_tags"]:
            print(f"    {tag:30s} {count:3d}")

        if s["coverage_gaps"]:
            print("\n  Coverage gaps:")
            for gap in s["coverage_gaps"]:
                print(f"    ⚠  {gap}")

        sys.exit(0)

    # Add entry
    if args.add:
        if not args.domain or not args.fact or not args.source:
            print(
                "ERROR: --add requires --domain, --fact, and --source",
                file=sys.stderr,
            )
            sys.exit(1)
        tags = args.tags.split(",") if args.tags else []
        try:
            entry = kf.add_entry(
                domain=args.domain,
                fact=args.fact,
                source=args.source,
                confidence=args.add_confidence,
                tags=tags,
            )
            print(f"Added entry: {entry.id}")
            print(f"  Domain: {entry.domain}")
            print(f"  Fact: {entry.fact}")
            print(f"  Confidence: {entry.confidence}")
            if args.save:
                kf.save()
        except (ValueError, KeyError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Query by ID
    if args.id:
        results = kf.query(entry_id=args.id)
        if not results:
            print(f"No entry found with ID '{args.id}'", file=sys.stderr)
            sys.exit(1)
        for entry in results:
            print(entry)
        sys.exit(0)

    # General query
    if args.domain or args.keyword or args.confidence is not None:
        if args.confidence is not None:
            results = kf.get_high_confidence(
                domain=args.domain, min_confidence=args.confidence
            )
            print(
                f"Entries with confidence >= {args.confidence}"
                + (f" in domain '{args.domain}'" if args.domain else "")
                + f":\n"
            )
        else:
            results = kf.query(domain=args.domain, keyword=args.keyword)
            filters = []
            if args.domain:
                filters.append(f"domain='{args.domain}'")
            if args.keyword:
                filters.append(f"keyword='{args.keyword}'")
            print(f"Query ({', '.join(filters)}): {len(results)} results\n")

        if not results:
            print("  No matching entries found.")
        else:
            for entry in results:
                print(entry)
        sys.exit(0)

    # No arguments — show help
    parser.print_help()


if __name__ == "__main__":
    main()
