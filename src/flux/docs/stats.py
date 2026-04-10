"""Code Statistics — computes code statistics for the FLUX project."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .introspector import CodeIntrospector, ComplexityMetrics


class CodeStatistics:
    """Computes code statistics for the FLUX project.

    Analyzes all Python files under ``src/flux/`` and ``tests/``
    to produce lines-of-code counts, test counts, module counts,
    and complexity reports.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._introspector = CodeIntrospector(repo_path)

    # ── LOC ────────────────────────────────────────────────────────────

    def total_loc(self) -> int:
        """Total lines of Python code in src/flux/."""
        return sum(self.loc_by_module().values())

    def loc_by_module(self) -> dict[str, int]:
        """Lines of code per top-level module directory."""
        flux_dir = Path(self.repo_path) / "src" / "flux"
        if not flux_dir.is_dir():
            return {}

        result: dict[str, int] = {}
        for pkg_dir in sorted(flux_dir.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
                continue
            total = 0
            for py_file in pkg_dir.rglob("*.py"):
                total += _count_lines(py_file)
            if total > 0:
                result[pkg_dir.name] = total
        return result

    # ── Test counts ────────────────────────────────────────────────────

    def test_count(self) -> int:
        """Total number of test functions across all test files."""
        tests_dir = Path(self.repo_path) / "tests"
        if not tests_dir.is_dir():
            return 0

        count = 0
        for test_file in tests_dir.glob("test_*.py"):
            count += self._count_test_functions(test_file)
        return count

    def test_count_by_module(self) -> dict[str, int]:
        """Tests per source module (mapped by test filename convention)."""
        tests_dir = Path(self.repo_path) / "tests"
        if not tests_dir.is_dir():
            return {}

        result: dict[str, int] = {}
        for test_file in sorted(tests_dir.glob("test_*.py")):
            name = test_file.stem  # e.g. "test_parser"
            # Map back to source module
            mod_name = name.replace("test_", "")
            result[mod_name] = self._count_test_functions(test_file)
        return result

    # ── Public API size ────────────────────────────────────────────────

    def public_api_size(self) -> int:
        """Number of public API declarations across all modules."""
        modules = self._introspector.list_modules()
        total = 0
        for mod in modules:
            api = self._introspector.get_public_api(mod.path)
            total += len(api)
        return total

    # ── Module count ───────────────────────────────────────────────────

    def module_count(self) -> int:
        """Number of FLUX sub-packages (directories under src/flux/)."""
        flux_dir = Path(self.repo_path) / "src" / "flux"
        if not flux_dir.is_dir():
            return 0
        return sum(
            1 for d in flux_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
            and d.name != "__pycache__"
        )

    # ── Complexity report ──────────────────────────────────────────────

    def complexity_report(self) -> dict[str, ComplexityMetrics]:
        """Complexity metrics per top-level module."""
        flux_dir = Path(self.repo_path) / "src" / "flux"
        if not flux_dir.is_dir():
            return {}

        result: dict[str, ComplexityMetrics] = {}
        for pkg_dir in sorted(flux_dir.iterdir()):
            if not pkg_dir.is_dir() or pkg_dir.name.startswith("_"):
                continue

            total_metrics = ComplexityMetrics()
            for py_file in pkg_dir.rglob("*.py"):
                m = self._introspector.get_complexity(str(py_file))
                total_metrics.loc += m.loc
                total_metrics.cyclomatic += m.cyclomatic
                total_metrics.function_count += m.function_count
                total_metrics.class_count += m.class_count
                total_metrics.import_count += m.import_count

            if total_metrics.function_count > 0:
                total_metrics.avg_function_length = (
                    total_metrics.loc / total_metrics.function_count
                )
            result[pkg_dir.name] = total_metrics

        return result

    # ── Growth report ──────────────────────────────────────────────────

    def growth_report(self, worklog_path: str | None = None) -> str:
        """Parse git history/worklog and report growth over time.

        Reads task entries from the worklog to extract timestamps
        and test counts for a growth narrative.
        """
        if worklog_path is None:
            worklog_path = str(Path(self.repo_path) / "worklog.md")

        path = Path(worklog_path)
        if not path.is_file():
            return "No worklog found.\n"

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return "Could not read worklog.\n"

        lines: list[str] = ["# FLUX Growth Report\n"]

        # Count tasks
        task_pattern = re.compile(r"^Task ID:\s*(.+)$", re.MULTILINE)
        tasks = task_pattern.findall(content)

        # Count test references
        test_pattern = re.compile(r"(\d+)\s+tests?\s+(?:passing|all\s+passing)", re.IGNORECASE)
        test_matches = test_pattern.findall(content)

        lines.append(f"**Total tasks/iterations:** {len(tasks)}\n")
        if test_matches:
            latest_tests = test_matches[-1] if test_matches else "0"
            lines.append(f"**Latest test count:** {latest_tests}\n")

        lines.append(f"**Current LOC:** {self.total_loc()}\n")
        lines.append(f"**Modules:** {self.module_count()}\n")
        lines.append(f"**Public API:** {self.public_api_size()} declarations\n")

        # Timeline
        lines.append("\n## Iteration Timeline\n")
        lines.append("| # | Task ID | Tests |")
        lines.append("|---|---------|-------|")
        for i, task_id in enumerate(tasks, 1):
            # Find the nearest test count for this task
            lines.append(f"| {i} | `{task_id.strip()}` | — |")

        return "\n".join(lines) + "\n"

    # ── Full report ────────────────────────────────────────────────────

    def full_report(self) -> str:
        """Generate a comprehensive statistics report."""
        lines: list[str] = [
            "# FLUX Code Statistics\n",
            "## Overview\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total LOC | {self.total_loc():,} |",
            f"| Modules | {self.module_count()} |",
            f"| Test count | {self.test_count():,} |",
            f"| Public API | {self.public_api_size()} |",
            "",
        ]

        # LOC by module
        loc = self.loc_by_module()
        if loc:
            lines.append("## Lines of Code by Module\n")
            lines.append("| Module | LOC |")
            lines.append("|--------|-----|")
            for mod, count in sorted(loc.items(), key=lambda x: -x[1]):
                lines.append(f"| `{mod}` | {count:,} |")
            lines.append("")

        # Test count by module
        tests = self.test_count_by_module()
        if tests:
            lines.append("## Tests by Module\n")
            lines.append("| Module | Tests |")
            lines.append("|--------|-------|")
            for mod, count in sorted(tests.items(), key=lambda x: -x[1]):
                lines.append(f"| `{mod}` | {count:,} |")
            lines.append("")

        # Complexity top-5
        complexity = self.complexity_report()
        if complexity:
            lines.append("## Complexity (Top 5 by LOC)\n")
            lines.append("| Module | LOC | Functions | Classes | Cyclomatic |")
            lines.append("|--------|-----|-----------|---------|------------|")
            sorted_complexity = sorted(
                complexity.items(), key=lambda x: -x[1].loc
            )[:5]
            for mod, m in sorted_complexity:
                lines.append(
                    f"| `{mod}` | {m.loc:,} | {m.function_count} "
                    f"| {m.class_count} | {m.cyclomatic} |"
                )
            lines.append("")

        return "\n".join(lines) + "\n"

    # ── Helpers ────────────────────────────────────────────────────────

    def _count_test_functions(self, test_file: Path) -> int:
        """Count test functions in a test file using regex."""
        try:
            source = test_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return 0

        # Match both standalone test_foo and methods inside Test* classes
        count = 0
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("def test_"):
                count += 1
        return count


def _count_lines(py_file: Path) -> int:
    """Count non-empty, non-comment lines in a Python file."""
    try:
        source = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count
