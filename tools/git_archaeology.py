#!/usr/bin/env python3
"""
Git Archaeology Tool — "The Craftsman's Reading"

From the Witness Marks protocol (JetsonClaw1 + Oracle1):
Scan any git repo and produce a structured analysis of commit quality,
craftsman patterns, hard-won knowledge, and antipatterns.

Usage:
    python git_archaeology.py /path/to/repo [--since "1 week"] [--format markdown|json]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import git
except ImportError:
    print("ERROR: gitpython required. Install with: pip install gitpython")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ContributorProfile:
    name: str
    email: str
    commit_count: int = 0
    total_files_changed: int = 0
    total_lines_changed: int = 0
    avg_message_length: float = 0.0
    conventional_commit_ratio: float = 0.0
    body_explain_why_ratio: float = 0.0
    specialty: str = ""
    top_scopes: list[str] = field(default_factory=list)


@dataclass
class Antipattern:
    commit_hash: str
    commit_msg_short: str
    antipattern_type: str
    severity: str  # ERROR, WARNING, INFO
    detail: str


@dataclass
class CommitAnalysis:
    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    subject: str
    body: str
    files_changed: int
    lines_added: int
    lines_deleted: int
    is_conventional: bool
    commit_type: str  # feat, fix, test, docs, etc.
    commit_scope: str  # optional scope in parentheses
    has_body: bool
    body_explains_why: bool
    references_issue: bool
    is_merge: bool
    is_atomic: bool  # True if 1 logical change (heuristic)
    effort_score: float  # 0-100, higher = more effort
    is_truthful: bool  # message scope vs diff scope
    truth_detail: str = ""


@dataclass
class ArchaeologyReport:
    repo_path: str
    total_commits: int
    contributors: list[ContributorProfile]
    craftsmanship_score: float
    hard_parts: list[str]
    antipatterns: list[Antipattern]
    commit_analyses: list[CommitAnalysis]
    since: str
    generated_at: str
    score_breakdown: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heuristics & constants
# ---------------------------------------------------------------------------

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|test|tests|docs|refactor|perf|style|ci|build|chore|revert)"
    r"(?:\(([^)]+)\))?!?:\s*(.+)"
)

WHY_INDICATORS = [
    "because", "since", "due to", "reason", "why", "root cause",
    "otherwise", "without this", "prevents", "avoids", "needed to",
    "so that", "in order to", "to fix", "this was", "turned out",
]

ISSUE_RE = re.compile(
    r"#\d+|(?:issue|PR|pull request|ticket|bug)\s*\w*#?\s*\d+",
    re.IGNORECASE,
)

TRIVIAL_KEYWORDS = re.compile(
    r"\b(typo|formatting|whitespace|lint|eslint|prettier|copyright|header)\b",
    re.IGNORECASE,
)

LOGIC_CHANGE_EXTENSIONS = {
    ".py", ".js", ".ts", ".rs", ".c", ".h", ".cpp", ".java", ".go",
    ".rb", ".sh", ".yaml", ".yml", ".toml",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class GitArchaeologist:
    """Produces a 'craftsman's reading' of a git repository."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")
        self.repo = git.Repo(str(self.repo_path))

    # -- public API ----------------------------------------------------------

    def analyze(self, since: str = "1 week ago") -> ArchaeologyReport:
        commits = self._get_commits(since)
        analyses = [self._analyze_commit(c) for c in commits]
        contributors = self._identify_craftsmen(analyses)
        score, breakdown = self._compute_craftsmanship_score(analyses)
        hard_parts = self._identify_hard_parts(analyses)
        antipatterns = self._detect_antipatterns(analyses)
        return ArchaeologyReport(
            repo_path=str(self.repo_path),
            total_commits=len(analyses),
            contributors=contributors,
            craftsmanship_score=score,
            hard_parts=hard_parts,
            antipatterns=antipatterns,
            commit_analyses=analyses,
            since=since,
            generated_at=datetime.now(timezone.utc).isoformat(),
            score_breakdown=breakdown,
        )

    def craftsmanship_score(self, since: str = "1 week ago") -> float:
        report = self.analyze(since)
        return report.craftsmanship_score

    def identify_hard_parts(self, since: str = "1 week ago") -> list[str]:
        report = self.analyze(since)
        return report.hard_parts

    def identify_craftsmen(self, since: str = "1 week ago") -> list[ContributorProfile]:
        report = self.analyze(since)
        return report.contributors

    def produce_narrative(self, since: str = "1 week ago") -> str:
        report = self.analyze(since)
        return self._render_narrative(report)

    def detect_antipatterns(self, since: str = "1 week ago") -> list[Antipattern]:
        report = self.analyze(since)
        return report.antipatterns

    # -- internals -----------------------------------------------------------

    def _get_commits(self, since: str):
        try:
            return list(self.repo.iter_commits("--since=" + since, "--all"))
        except git.GitCommandError:
            return list(self.repo.iter_commits("--all"))

    def _analyze_commit(self, commit: git.Commit) -> CommitAnalysis:
        msg = commit.message.strip()
        subject, _, body = msg.partition("\n")
        body = body.strip()
        is_merge = bool(commit.parents and len(commit.parents) > 1)

        # Conventional commit parsing
        m = CONVENTIONAL_RE.match(subject)
        is_conventional = bool(m)
        commit_type = m.group(1) if m else ""
        commit_scope = m.group(2) if m and m.group(2) else ""

        # File / line stats
        try:
            diff = commit.stats
            files_changed = diff.total.get("files", 0)
            lines_added = diff.total.get("insertions", 0)
            lines_deleted = diff.total.get("deletions", 0)
        except Exception:
            files_changed, lines_added, lines_deleted = 0, 0, 0

        # Body explains WHY (not just WHAT)
        body_lower = body.lower()
        has_body = len(body) > 20
        body_explains_why = has_body and any(
            w in body_lower for w in WHY_INDICATORS
        )

        # References issue / PR
        full_msg = msg.lower()
        references_issue = bool(ISSUE_RE.search(msg))

        # Atomicity heuristic: multi-file but message says single thing
        is_atomic = self._check_atomicity(files_changed, subject, commit)

        # Effort score
        effort_score = self._compute_effort(
            files_changed, lines_added, lines_deleted,
            len(subject), len(body), is_conventional, has_body,
        )

        # Truthfulness check
        is_truthful, truth_detail = self._check_truthfulness(
            subject, commit, is_merge
        )

        return CommitAnalysis(
            hash=commit.hexsha,
            short_hash=commit.hexsha[:7],
            author=commit.author.name or commit.author.email or "unknown",
            date=datetime.fromtimestamp(
                commit.committed_date
            ).isoformat() if commit.committed_date else "unknown",
            message=msg,
            subject=subject,
            body=body,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            is_conventional=is_conventional,
            commit_type=commit_type,
            commit_scope=commit_scope,
            has_body=has_body,
            body_explains_why=body_explains_why,
            references_issue=references_issue,
            is_merge=is_merge,
            is_atomic=is_atomic,
            effort_score=effort_score,
            is_truthful=is_truthful,
            truth_detail=truth_detail,
        )

    @staticmethod
    def _check_atomicity(files_changed: int, subject: str,
                         commit: git.Commit) -> bool:
        """Heuristic: a commit is atomic if it touches a single logical area."""
        if files_changed <= 3:
            return True
        if files_changed > 10:
            return False
        # Check if all files share a common directory prefix
        try:
            diffs = commit.diff(commit.parents[0] if commit.parents else None)
            paths = [d.a_path for d in diffs if d.a_path]
            if not paths:
                return True
            dirs = [Path(p).parts[0] if len(Path(p).parts) > 1 else p
                    for p in paths]
            unique_dirs = set(dirs)
            return len(unique_dirs) <= 2
        except Exception:
            return True

    @staticmethod
    def _compute_effort(files, added, deleted, subj_len, body_len,
                        is_conv, has_body) -> float:
        """0-100 effort score: more files + longer message + conventions = higher."""
        score = 0.0
        score += min(files * 2, 20)
        score += min(added * 0.02, 15)
        score += min(deleted * 0.02, 10)
        score += min(subj_len * 0.5, 10)
        score += min(body_len * 0.3, 20)
        if is_conv:
            score += 10
        if has_body:
            score += 5
        return min(score, 100.0)

    def _check_truthfulness(self, subject: str, commit: git.Commit,
                            is_merge: bool) -> tuple[bool, str]:
        """Check if commit message scope matches diff scope."""
        if is_merge:
            return True, ""

        subject_lower = subject.lower()
        try:
            parent = commit.parents[0] if commit.parents else None
            diffs = commit.diff(parent) if parent else []
        except Exception:
            return True, ""

        if not diffs:
            return True, ""

        # Check for trivial claims vs logic changes
        is_trivial_claim = bool(TRIVIAL_KEYWORDS.search(subject_lower))
        if is_trivial_claim:
            for d in diffs:
                ext = Path(d.a_path or "").suffix if d.a_path else ""
                if ext in LOGIC_CHANGE_EXTENSIONS:
                    change_size = (
                        (len(d.diff.decode("utf-8", errors="replace"))
                         if d.diff else 0)
                    )
                    if change_size > 200:
                        return False, (
                            f"Claims '{subject[:50]}...' but changes "
                            f"{d.a_path} with {change_size} chars"
                        )

        # Check "typo/fix" claims with test additions (reasonable)
        return True, ""

    # -- Scoring -------------------------------------------------------------

    def _compute_craftsmanship_score(
        self, analyses: list[CommitAnalysis]
    ) -> tuple[float, dict]:
        if not analyses:
            return 0.0, {}

        total = len(analyses)
        scores: list[float] = []

        conv_count = sum(1 for a in analyses if a.is_conventional)
        why_count = sum(1 for a in analyses if a.body_explains_why)
        ref_count = sum(1 for a in analyses if a.references_issue)
        atomic_count = sum(1 for a in analyses if a.is_atomic)
        truthful_count = sum(1 for a in analyses if a.is_truthful)

        # Per-commit scoring (raw, before normalization)
        for a in analyses:
            s = 50.0  # baseline
            if a.is_conventional:
                s += 10
            if a.body_explains_why:
                s += 15
            if a.references_issue:
                s += 10
            if a.is_atomic:
                s += 5
            if a.is_truthful:
                s += 5
            if a.has_body and len(a.body) > 50:
                s += 5  # branch-per-experiment style documentation
            if a.files_changed >= 10 and not a.is_atomic:
                s -= 10  # mega-commit penalty
            if not a.is_truthful:
                s -= 15
            scores.append(s)

        # Global checks: force pushes (look for reset/rebase markers)
        force_push_penalty = self._detect_force_push_penalty(analyses)

        raw = statistics.mean(scores) - force_push_penalty
        final = max(0.0, min(100.0, raw))

        breakdown = {
            "conventional_commits": {
                "count": conv_count, "total": total,
                "ratio": round(conv_count / total, 2),
                "points": round((conv_count / total) * 10, 1),
            },
            "body_explains_why": {
                "count": why_count, "total": total,
                "ratio": round(why_count / total, 2),
                "points": round((why_count / total) * 15, 1),
            },
            "references_issues": {
                "count": ref_count, "total": total,
                "ratio": round(ref_count / total, 2),
                "points": round((ref_count / total) * 10, 1),
            },
            "atomic_commits": {
                "count": atomic_count, "total": total,
                "ratio": round(atomic_count / total, 2),
                "points": round((atomic_count / total) * 5, 1),
            },
            "truthful_messages": {
                "count": truthful_count, "total": total,
                "ratio": round(truthful_count / total, 2),
            },
            "force_push_penalty": round(force_push_penalty, 1),
        }
        return round(final, 1), breakdown

    def _detect_force_push_penalty(self, analyses: list[CommitAnalysis]) -> float:
        """Heuristic penalty for potential force pushes (no documentation)."""
        # We can't directly detect force pushes from iter_commits alone,
        # but we can check for orphan-like singletons or suspicious patterns.
        return 0.0  # Conservative default

    # -- Hard parts ----------------------------------------------------------

    def _identify_hard_parts(self, analyses: list[CommitAnalysis]) -> list[str]:
        """Commits that took the most effort (many files, long messages)."""
        sorted_analyses = sorted(analyses, key=lambda a: a.effort_score,
                                 reverse=True)
        results = []
        for a in sorted_analyses[:10]:
            parts = [
                f"- `{a.short_hash}` {a.subject[:80]}",
                f"  effort={a.effort_score:.0f}  files={a.files_changed}  "
                f"+{a.lines_added}/-{a.lines_deleted}",
            ]
            if a.body:
                why_snippet = a.body[:120].replace("\n", " ")
                parts.append(f"  why: {why_snippet}...")
            results.append("\n".join(parts))
        return results

    # -- Craftsmen -----------------------------------------------------------

    def _identify_craftsmen(
        self, analyses: list[CommitAnalysis]
    ) -> list[ContributorProfile]:
        from collections import defaultdict

        author_data: dict[str, dict] = defaultdict(lambda: {
            "commits": 0, "files": 0, "lines": 0,
            "msg_lengths": [], "conventional": 0, "why": 0,
            "scopes": [],
        })

        for a in analyses:
            key = a.author
            d = author_data[key]
            d["commits"] += 1
            d["files"] += a.files_changed
            d["lines"] += a.lines_added + a.lines_deleted
            d["msg_lengths"].append(len(a.message))
            if a.is_conventional:
                d["conventional"] += 1
            if a.body_explains_why:
                d["why"] += 1
            if a.commit_scope:
                d["scopes"].append(a.commit_scope)

        profiles = []
        for name, d in author_data.items():
            n = d["commits"]
            scopes = d["scopes"]
            scope_counts: dict[str, int] = {}
            for s in scopes:
                scope_counts[s] = scope_counts.get(s, 0) + 1
            top = sorted(scope_counts.items(), key=lambda x: -x[1])[:5]

            profiles.append(ContributorProfile(
                name=name,
                email="",
                commit_count=n,
                total_files_changed=d["files"],
                total_lines_changed=d["lines"],
                avg_message_length=statistics.mean(d["msg_lengths"]) if d["msg_lengths"] else 0,
                conventional_commit_ratio=d["conventional"] / n if n else 0,
                body_explain_why_ratio=d["why"] / n if n else 0,
                specialty=", ".join(s[0] for s in top) if top else "generalist",
                top_scopes=[s[0] for s in top],
            ))

        profiles.sort(key=lambda p: -p.commit_count)
        return profiles

    # -- Antipatterns --------------------------------------------------------

    def _detect_antipatterns(
        self, analyses: list[CommitAnalysis]
    ) -> list[Antipattern]:
        patterns: list[Antipattern] = []

        for a in analyses:
            # Mega-commit (10+ unrelated files)
            if a.files_changed >= 10 and not a.is_atomic:
                patterns.append(Antipattern(
                    commit_hash=a.short_hash,
                    commit_msg_short=a.subject[:60],
                    antipattern_type="mega-commit",
                    severity="WARNING",
                    detail=(
                        f"{a.files_changed} files changed — "
                        f"break into atomic commits"
                    ),
                ))

            # Misleading message (claims trivial but changes logic)
            if not a.is_truthful:
                patterns.append(Antipattern(
                    commit_hash=a.short_hash,
                    commit_msg_short=a.subject[:60],
                    antipattern_type="misleading-message",
                    severity="ERROR",
                    detail=a.truth_detail,
                ))

            # Empty body on significant change
            if not a.has_body and a.files_changed >= 5:
                patterns.append(Antipattern(
                    commit_hash=a.short_hash,
                    commit_msg_short=a.subject[:60],
                    antipattern_type="missing-body",
                    severity="INFO",
                    detail=(
                        f"{a.files_changed} files changed but no commit body — "
                        f"explain WHY"
                    ),
                ))

            # Non-conventional commit
            if not a.is_conventional and not a.is_merge:
                patterns.append(Antipattern(
                    commit_hash=a.short_hash,
                    commit_msg_short=a.subject[:60],
                    antipattern_type="non-conventional",
                    severity="INFO",
                    detail="Use conventional format: type(scope): description",
                ))

        patterns.sort(key=lambda p: {"ERROR": 0, "WARNING": 1, "INFO": 2}.get(
            p.severity, 3))
        return patterns

    # -- Narrative -----------------------------------------------------------

    def _render_narrative(self, report: ArchaeologyReport) -> str:
        lines: list[str] = []
        lines.append("# Craftsman's Reading")
        lines.append(f"**Repo:** `{report.repo_path}`")
        lines.append(f"**Period:** since {report.since}")
        lines.append(f"**Generated:** {report.generated_at}")
        lines.append("")

        # Score
        score = report.craftsmanship_score
        grade = (
            "A+" if score >= 85 else "A" if score >= 75 else
            "B+" if score >= 65 else "B" if score >= 55 else
            "C+" if score >= 45 else "C" if score >= 35 else
            "D" if score >= 20 else "F"
        )
        lines.append(f"## Craftsmanship Score: {score}/100 ({grade})")
        lines.append("")

        # Score breakdown
        bd = report.score_breakdown
        lines.append("### Score Breakdown")
        for key, val in bd.items():
            if isinstance(val, dict):
                pts = val.get("points", "N/A")
                ratio = val.get("ratio", "N/A")
                lines.append(f"- **{key}**: {ratio} ({pts} pts)")
            else:
                lines.append(f"- **{key}**: {val}")
        lines.append("")

        # Top craftsmen
        lines.append("## Contributors")
        for c in report.contributors[:5]:
            lines.append(f"### {c.name}")
            lines.append(f"- {c.commit_count} commits, "
                         f"{c.total_files_changed} files, "
                         f"{c.total_lines_changed} lines")
            lines.append(f"- Avg message length: {c.avg_message_length:.0f} chars")
            lines.append(f"- Conventional: {c.conventional_commit_ratio:.0%}, "
                         f"Explains why: {c.body_explain_why_ratio:.0%}")
            lines.append(f"- Specialty: {c.specialty}")
            lines.append("")

        # Hard parts
        lines.append("## Where the Hard Work Was")
        if report.hard_parts:
            for h in report.hard_parts:
                lines.append(h)
        else:
            lines.append("_No significant effort commits detected._")
        lines.append("")

        # Antipatterns
        lines.append("## Antipatterns Detected")
        if report.antipatterns:
            lines.append("| Severity | Type | Commit | Detail |")
            lines.append("|----------|------|--------|--------|")
            for ap in report.antipatterns:
                lines.append(
                    f"| {ap.severity} | {ap.antipattern_type} | "
                    f"`{ap.commit_hash}` | {ap.detail} |"
                )
        else:
            lines.append("_No antipatterns detected. Clean history._")
        lines.append("")

        # Commit history
        lines.append("## Commit History")
        lines.append("| Hash | Author | Type | Scope | Subject | Files | Effort |")
        lines.append("|------|--------|------|-------|---------|-------|--------|")
        for a in report.commit_analyses[:30]:
            ctype = a.commit_type or "-"
            scope = a.commit_scope or "-"
            lines.append(
                f"| `{a.short_hash}` | {a.author[:20]} | {ctype} | "
                f"{scope} | {a.subject[:50]} | {a.files_changed} | "
                f"{a.effort_score:.0f} |"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Git Archaeology Tool — Craftsman's Reading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scoring criteria (per commit):
  +10  Conventional commit format (feat:, fix:, test:, docs:)
  +15  Commit body explains WHY not just WHAT
  +10  References issues/PRs
  +5   Atomic commits (1 logical change)
  +5   Branch-per-experiment pattern (documented body)
  -10  Mega-commits (10+ files unrelated)
  -15  Commit messages that lie (message says "typo" but changes logic)
  -5   Force push without documentation
        """,
    )
    parser.add_argument("repo", help="Path to git repository")
    parser.add_argument(
        "--since", default="1 week ago",
        help="Time range (git log --since syntax, default: '1 week ago')",
    )
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--score-only", action="store_true",
        help="Only print the craftsmanship score",
    )

    args = parser.parse_args()

    try:
        archaeologist = GitArchaeologist(args.repo)
        report = archaeologist.analyze(args.since)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.score_only:
        print(f"{report.craftsmanship_score}")
        sys.exit(0)

    if args.format == "json":
        def _serialize(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _serialize(v) for k, v in obj.__dict__.items()}
            if isinstance(obj, list):
                return [_serialize(i) for i in obj]
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            return str(obj)
        print(json.dumps(_serialize(report), indent=2, default=str))
    else:
        print(archaeologist.produce_narrative(args.since))


if __name__ == "__main__":
    main()
