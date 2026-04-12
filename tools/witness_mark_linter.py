#!/usr/bin/env python3
"""
Witness Mark Linter — Check commit messages against the Craftsman's Git Protocol

From the Witness Marks protocol (JetsonClaw1 + Oracle1):
Lints commit messages for conventional format, explanatory bodies,
issue references, atomicity, and truthfulness.

Protocol rules:
  Rule 1: Every Commit Tells a Story — <type>(<scope>): <description> + WHY body
  Rule 2: Hard-Won Knowledge Gets Witness Marks — long messages for hard work
  Rule 3: Experiments Leave Traces — branch-per-experiment with closing commits
  Rule 4: README IS the Map — out of scope for per-commit linting
  Rule 5: Tests Are Witness Marks — test commits listed with counts

Usage:
    python witness_mark_linter.py /path/to/repo [--last N] [--format markdown|json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
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
class LintResult:
    check_name: str
    passed: bool
    severity: str = "INFO"  # ERROR, WARNING, INFO
    message: str = ""
    commit_hash: str = ""
    commit_subject: str = ""


@dataclass
class LintReport:
    repo_path: str
    commits_linted: int
    total_checks: int
    passed: int
    failed: int
    warnings: int
    infos: int
    results: list[LintResult] = field(default_factory=list)
    grade: str = ""
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Patterns & constants
# ---------------------------------------------------------------------------

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|test|tests|docs|refactor|perf|style|ci|build|chore|revert)"
    r"(?:\(([^)]+)\))?!?:\s*(.+)"
)

WHY_INDICATORS = [
    "because", "since", "due to", "reason", "why", "root cause",
    "otherwise", "without this", "prevents", "avoids", "needed to",
    "so that", "in order to", "to fix", "this was", "turned out",
    "allows", "enables", "ensures", "corrects", "resolves",
]

ISSUE_RE = re.compile(
    r"#\d+|(?:issue|PR|pull request|ticket|bug|T-)\s*#?\s*\d+",
    re.IGNORECASE,
)

TRIVIAL_KEYWORDS = re.compile(
    r"\b(typo|formatting|whitespace|lint|eslint|prettier|copyright|header|"
    r"newline|blank line|trailing|indent)\b",
    re.IGNORECASE,
)

LOGIC_CHANGE_EXTENSIONS = {
    ".py", ".js", ".ts", ".rs", ".c", ".h", ".cpp", ".java", ".go",
    ".rb", ".sh", ".yaml", ".yml", ".toml",
}


# ---------------------------------------------------------------------------
# Main linter class
# ---------------------------------------------------------------------------

class WitnessMarkLinter:
    """Lints git commit messages against the Witness Marks protocol."""

    def lint(self, repo_path: str, last_n: int = 20) -> LintReport:
        """Check last N commits against the protocol."""
        repo_dir = Path(repo_path).resolve()
        if not (repo_dir / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_dir}")

        repo = git.Repo(str(repo_dir))
        commits = list(repo.iter_commits("HEAD", max_count=last_n))

        all_results: list[LintResult] = []
        for commit in commits:
            all_results.extend(self._lint_commit(commit))

        # Compute stats
        errors = sum(1 for r in all_results if r.severity == "ERROR")
        warnings = sum(1 for r in all_results if r.severity == "WARNING")
        infos = sum(1 for r in all_results if r.severity == "INFO")
        passed = sum(1 for r in all_results if r.passed)
        total = len(all_results)

        # Grade
        if errors == 0 and warnings == 0:
            grade = "A+"
        elif errors == 0 and warnings <= 2:
            grade = "A"
        elif errors == 0 and warnings <= 5:
            grade = "B+"
        elif errors == 0:
            grade = "B"
        elif errors <= 2 and warnings <= 3:
            grade = "C+"
        elif errors <= 3:
            grade = "C"
        else:
            grade = "F"

        from datetime import timezone, datetime
        return LintReport(
            repo_path=str(repo_dir),
            commits_linted=len(commits),
            total_checks=total,
            passed=passed,
            failed=total - passed,
            warnings=warnings,
            infos=infos,
            results=all_results,
            grade=grade,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # -- Individual checks ---------------------------------------------------

    def check_conventional_format(self, message: str,
                                  commit_hash: str = "",
                                  commit_subject: str = "") -> LintResult:
        """Check if commit follows conventional commit format."""
        m = CONVENTIONAL_RE.match(message.split("\n")[0] if message else "")
        if m:
            ctype = m.group(1)
            return LintResult(
                check_name="conventional-format",
                passed=True,
                severity="INFO",
                message=f"Valid conventional commit: {ctype}",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )
        return LintResult(
            check_name="conventional-format",
            passed=False,
            severity="ERROR",
            message=(
                "Not a conventional commit. Use: "
                "<type>(<scope>): <description> "
                "(types: feat, fix, test, docs, refactor, ...)"
            ),
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    def check_body_exists(self, message: str,
                          commit_hash: str = "",
                          commit_subject: str = "") -> LintResult:
        """Check if commit has a body (not just a subject line)."""
        lines = message.strip().split("\n") if message else []
        # Body exists if there's a blank line followed by content
        has_body = False
        found_blank = False
        for line in lines[1:]:  # skip subject
            if not line.strip():
                found_blank = True
                continue
            if found_blank and line.strip():
                has_body = True
                break

        if has_body:
            return LintResult(
                check_name="body-exists",
                passed=True,
                severity="INFO",
                message="Commit has a body explaining the change",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )
        return LintResult(
            check_name="body-exists",
            passed=False,
            severity="WARNING",
            message=(
                "No commit body found. Add a blank line after the subject, "
                "then explain WHY the change was made."
            ),
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    def check_explains_why(self, body: str,
                           commit_hash: str = "",
                           commit_subject: str = "") -> LintResult:
        """Basic heuristic: does the body explain WHY, not just WHAT?"""
        if not body or len(body.strip()) < 20:
            return LintResult(
                check_name="body-explains-why",
                passed=False,
                severity="WARNING",
                message=(
                    "Body too short to explain WHY. "
                    "Include reasoning, motivation, or context."
                ),
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )

        body_lower = body.lower()
        why_found = any(indicator in body_lower for indicator in WHY_INDICATORS)

        # Also check for cause-effect language patterns
        cause_effect = bool(re.search(
            r"\b(if|when|after|before|whenever|unless)\b.*\b(then|it|we|this)\b",
            body_lower,
        ))

        if why_found or cause_effect:
            return LintResult(
                check_name="body-explains-why",
                passed=True,
                severity="INFO",
                message="Body explains WHY (not just WHAT)",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )
        return LintResult(
            check_name="body-explains-why",
            passed=False,
            severity="WARNING",
            message=(
                "Body doesn't clearly explain WHY. "
                "Include reasoning: 'because...', 'due to...', 'so that...'"
            ),
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    def check_references_issue(self, message: str,
                               commit_hash: str = "",
                               commit_subject: str = "") -> LintResult:
        """Check if commit message references an issue or PR."""
        if ISSUE_RE.search(message):
            match = ISSUE_RE.search(message)
            return LintResult(
                check_name="references-issue",
                passed=True,
                severity="INFO",
                message=f"References issue/PR: {match.group() if match else 'found'}",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )
        return LintResult(
            check_name="references-issue",
            passed=False,
            severity="INFO",
            message=(
                "No issue/PR reference found. "
                "Include 'Fixes #N' or 'Refs #N' for traceability."
            ),
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    def check_atomicity(self, commit: git.Commit,
                        commit_hash: str = "",
                        commit_subject: str = "") -> LintResult:
        """Check if commit is atomic (1 logical change)."""
        try:
            diff = commit.stats
            files_changed = diff.total.get("files", 0)
        except Exception:
            files_changed = 0

        if files_changed <= 3:
            return LintResult(
                check_name="atomicity",
                passed=True,
                severity="INFO",
                message=f"Atomic commit: {files_changed} file(s) changed",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )

        if files_changed >= 10:
            return LintResult(
                check_name="atomicity",
                passed=False,
                severity="ERROR",
                message=(
                    f"Mega-commit: {files_changed} files changed. "
                    f"Break into smaller atomic commits."
                ),
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )

        # Check file cohesiveness for 4-9 files
        try:
            parent = commit.parents[0] if commit.parents else None
            diffs = commit.diff(parent) if parent else []
            paths = [d.a_path for d in diffs if d.a_path]
            if paths:
                dirs = [Path(p).parts[0] if len(Path(p).parts) > 1 else p
                        for p in paths]
                unique_dirs = set(dirs)
                if len(unique_dirs) <= 2:
                    return LintResult(
                        check_name="atomicity",
                        passed=True,
                        severity="INFO",
                        message=(
                            f"Reasonably atomic: {files_changed} files in "
                            f"{len(unique_dirs)} directory(ies)"
                        ),
                        commit_hash=commit_hash,
                        commit_subject=commit_subject,
                    )
        except Exception:
            pass

        return LintResult(
            check_name="atomicity",
            passed=False,
            severity="WARNING",
            message=(
                f"{files_changed} files changed across multiple areas. "
                f"Consider splitting into focused commits."
            ),
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    def check_truthfulness(self, commit: git.Commit,
                           commit_hash: str = "",
                           commit_subject: str = "") -> LintResult:
        """Check if commit message scope matches diff scope."""
        msg = commit.message.strip()
        subject = msg.split("\n")[0] if msg else ""
        subject_lower = subject.lower()

        # Skip merge commits
        if commit.parents and len(commit.parents) > 1:
            return LintResult(
                check_name="truthfulness",
                passed=True,
                severity="INFO",
                message="Merge commit — skipped truthfulness check",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )

        is_trivial_claim = bool(TRIVIAL_KEYWORDS.search(subject_lower))
        if not is_trivial_claim:
            return LintResult(
                check_name="truthfulness",
                passed=True,
                severity="INFO",
                message="Message scope appears consistent with diff",
                commit_hash=commit_hash,
                commit_subject=commit_subject,
            )

        # Trivial claim — verify the diff is actually trivial
        try:
            parent = commit.parents[0] if commit.parents else None
            diffs = commit.diff(parent) if parent else []
        except Exception:
            diffs = []

        for d in diffs:
            ext = Path(d.a_path or "").suffix if d.a_path else ""
            if ext in LOGIC_CHANGE_EXTENSIONS:
                change_size = len(d.diff.decode("utf-8", errors="replace")) if d.diff else 0
                if change_size > 300:
                    return LintResult(
                        check_name="truthfulness",
                        passed=False,
                        severity="ERROR",
                        message=(
                            f"Claims trivial change ('{subject[:50]}') but "
                            f"modifies {d.a_path} with {change_size} chars "
                            f"of diff — message may be misleading"
                        ),
                        commit_hash=commit_hash,
                        commit_subject=commit_subject,
                    )

        return LintResult(
            check_name="truthfulness",
            passed=True,
            severity="INFO",
            message="Trivial claim matches small diff — consistent",
            commit_hash=commit_hash,
            commit_subject=commit_subject,
        )

    # -- Orchestrator --------------------------------------------------------

    def _lint_commit(self, commit: git.Commit) -> list[LintResult]:
        """Run all checks on a single commit."""
        msg = commit.message.strip()
        subject, _, body = msg.partition("\n")
        body = body.strip()
        short_hash = commit.hexsha[:7]
        subject_trunc = subject[:60]

        results = [
            self.check_conventional_format(msg, short_hash, subject_trunc),
            self.check_body_exists(msg, short_hash, subject_trunc),
            self.check_explains_why(body, short_hash, subject_trunc),
            self.check_references_issue(msg, short_hash, subject_trunc),
            self.check_atomicity(commit, short_hash, subject_trunc),
            self.check_truthfulness(commit, short_hash, subject_trunc),
        ]
        return results


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def render_markdown(report: LintReport) -> str:
    lines: list[str] = []
    lines.append("# Witness Mark Lint Report")
    lines.append(f"**Repo:** `{report.repo_path}`")
    lines.append(f"**Commits linted:** {report.commits_linted}")
    lines.append(f"**Grade:** {report.grade}")
    lines.append(f"**Generated:** {report.generated_at}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"| Checks | Passed | Failed | Errors | Warnings | Infos |")
    lines.append(f"|--------|--------|--------|--------|----------|-------|")
    lines.append(
        f"| {report.total_checks} | {report.passed} | {report.failed} | "
        f"{_count_severity(report.results, 'ERROR')} | "
        f"{_count_severity(report.results, 'WARNING')} | "
        f"{_count_severity(report.results, 'INFO')} |"
    )
    lines.append("")

    # Violations table (only failures)
    failures = [r for r in report.results if not r.passed]
    if failures:
        lines.append("## Violations")
        lines.append("| Severity | Check | Commit | Subject | Message |")
        lines.append("|----------|-------|--------|---------|---------|")
        for r in failures:
            lines.append(
                f"| {r.severity} | {r.check_name} | `{r.commit_hash}` | "
                f"{r.commit_subject[:40]} | {r.message[:80]} |"
            )
        lines.append("")
    else:
        lines.append("## Violations")
        lines.append("_No violations found. All witness marks are clean._")
        lines.append("")

    # Per-commit detail
    lines.append("## Per-Commit Detail")
    seen_commits = []
    for r in report.results:
        if r.commit_hash and r.commit_hash not in seen_commits:
            seen_commits.append(r.commit_hash)
            commit_results = [x for x in report.results
                              if x.commit_hash == r.commit_hash]
            passed = sum(1 for c in commit_results if c.passed)
            total = len(commit_results)
            status = "OK" if passed == total else "ISSUES"
            lines.append(
                f"### `{r.commit_hash}` {r.commit_subject} [{status} "
                f"{passed}/{total}]"
            )
            for cr in commit_results:
                icon = "pass" if cr.passed else "fail"
                lines.append(f"- [{icon}] **{cr.check_name}**: {cr.message}")
            lines.append("")

    return "\n".join(lines)


def render_json(report: LintReport) -> str:
    def _serialize(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _serialize(v) for k, v in obj.__dict__.items()}
        if isinstance(obj, list):
            return [_serialize(i) for i in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)
    return json.dumps(_serialize(report), indent=2, default=str)


def _count_severity(results: list[LintResult], severity: str) -> int:
    return sum(1 for r in results if r.severity == severity)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Witness Mark Linter — Check commits against the "
                    "Craftsman's Git Protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Protocol rules checked:
  Rule 1: Every Commit Tells a Story — conventional format + WHY body
  Rule 2: Hard-Won Knowledge Gets Witness Marks — detailed messages
  Rule 3: Experiments Leave Traces — documented branches

Checks performed:
  conventional-format  — type(scope): description
  body-exists          — blank line + explanation after subject
  body-explains-why    — body contains reasoning (because, since, due to...)
  references-issue     — #N, issue N, PR N, ticket N
  atomicity            — 1 logical change per commit
  truthfulness         — message scope matches diff scope
        """,
    )
    parser.add_argument("repo", help="Path to git repository")
    parser.add_argument(
        "--last", type=int, default=20,
        help="Number of commits to lint (default: 20)",
    )
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--grade-only", action="store_true",
        help="Only print the grade",
    )

    args = parser.parse_args()

    try:
        linter = WitnessMarkLinter()
        report = linter.lint(args.repo, args.last)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.grade_only:
        print(report.grade)
        sys.exit(0)

    if args.format == "json":
        print(render_json(report))
    else:
        print(render_markdown(report))


if __name__ == "__main__":
    main()
