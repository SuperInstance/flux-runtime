"""Migration report data structures for FLUX Migrate."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class MigratedFile:
    """Record for a single migrated file."""

    source_path: Path
    output_path: Path
    language: str
    functions_found: int = 0
    classes_found: int = 0
    structs_found: int = 0
    includes_found: int = 0
    imports_found: int = 0
    lines_processed: int = 0
    success: bool = True
    error: str = ""


@dataclass
class MigrationReport:
    """Aggregated report for a migration run."""

    input_path: Path
    output_dir: Path
    files: List[MigratedFile] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def elapsed_seconds(self) -> float:
        """Wall-clock time for the migration."""
        return self.end_time - self.start_time

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def successful(self) -> int:
        return sum(1 for f in self.files if f.success)

    @property
    def failed(self) -> int:
        return sum(1 for f in self.files if not f.success)

    @property
    def total_functions(self) -> int:
        return sum(f.functions_found for f in self.files)

    @property
    def total_classes(self) -> int:
        return sum(f.classes_found for f in self.files)

    @property
    def total_structs(self) -> int:
        return sum(f.structs_found for f in self.files)

    @property
    def total_lines(self) -> int:
        return sum(f.lines_processed for f in self.files)

    @property
    def languages(self) -> dict[str, int]:
        """Map of language -> file count."""
        counts: dict[str, int] = {}
        for f in self.files:
            counts[f.language] = counts.get(f.language, 0) + 1
        return counts

    def to_text(self) -> str:
        """Format the report as human-readable text."""
        lines: list[str] = []
        w = lines.append

        w("")
        w("  ╔═══════════════════════════════════════════════════════════╗")
        w("  ║                   FLUX MIGRATION REPORT                  ║")
        w("  ╚═══════════════════════════════════════════════════════════╝")
        w("")
        w(f"  Input       : {self.input_path}")
        w(f"  Output dir  : {self.output_dir}")
        w(f"  Elapsed     : {self.elapsed_seconds:.2f}s")
        w("")
        w("  ── Summary ─────────────────────────────────────────────────")
        w(f"  Files       : {self.total_files} ({self.successful} ok, {self.failed} failed)")
        w(f"  Functions   : {self.total_functions}")
        w(f"  Classes     : {self.total_classes}")
        w(f"  Structs     : {self.total_structs}")
        w(f"  Lines       : {self.total_lines}")

        if self.languages:
            lang_parts = ", ".join(f"{lang}: {cnt}" for lang, cnt in sorted(self.languages.items()))
            w(f"  Languages   : {lang_parts}")

        w("")
        w("  ── Per-File ────────────────────────────────────────────────")
        w(f"  {'Source':<45} {'Lang':>6} {'Funcs':>6} {'Lines':>6} {'Status':>8}")
        w(f"  {'─' * 45} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 8}")

        for mf in self.files:
            rel = mf.source_path.name
            if len(str(mf.source_path)) > 44:
                rel = "..." + str(mf.source_path)[-42:]
            status = "OK" if mf.success else "FAIL"
            w(
                f"  {rel:<45} {mf.language:>6} {mf.functions_found:>6} "
                f"{mf.lines_processed:>6} {status:>8}"
            )
            if not mf.success and mf.error:
                w(f"    Error: {mf.error}")

        w("")
        w("  ────────────────────────────────────────────────────────────")
        w("")
        return "\n".join(lines)
