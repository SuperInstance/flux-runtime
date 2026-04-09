"""ModuleCard — the atomic hot-reloadable unit."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, Any

from flux.fir.types import TypeContext
from flux.fir.blocks import FIRModule


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class CompileResult:
    """Outcome of compiling a ModuleCard."""

    success: bool
    error: str = ""
    compile_time_ns: int = 0
    checksum: str = ""


# ── ModuleCard ──────────────────────────────────────────────────────────────

@dataclass
class ModuleCard:
    """Atomic unit of code/data — the smallest hot-reloadable entity.

    A card holds source code in a specific language and caches compiled
    artifacts (FIR and bytecode) for fast execution.
    """

    name: str
    source: str
    language: str  # "python", "c", "fir", "bytecode"
    compiled_fir: Optional[FIRModule] = field(default=None, repr=False)
    compiled_bytecode: Optional[bytes] = field(default=None, repr=False)
    version: int = field(default=0)
    checksum: str = field(default="")
    metadata: dict = field(default_factory=dict)
    compilation_time_ns: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    # ── Checksum ────────────────────────────────────────────────────────

    def _compute_checksum(self) -> str:
        return hashlib.sha256(self.source.encode()).hexdigest()[:16]

    # ── Compilation ─────────────────────────────────────────────────────

    def compile(self, ctx: TypeContext) -> CompileResult:
        """Compile source to FIR (and optionally bytecode).

        For non-standard languages (python, c) this records metadata
        but does not perform real compilation.  For "fir" language the
        source is stored directly as bytecode stubs.
        """
        start = time.monotonic_ns()

        try:
            # Record language metadata
            self.metadata["language"] = self.language
            self.metadata["last_compiled"] = time.time()

            if self.language == "fir":
                # FIR-as-text: store a minimal FIR module as a placeholder
                self.compiled_fir = FIRModule(
                    name=self.name, type_ctx=ctx
                )
                self.compiled_bytecode = b"\x00" * 16  # minimal placeholder
            elif self.language in ("python", "c", "bytecode"):
                # These languages go through the full pipeline externally.
                # Here we just record that compilation was "accepted".
                self.compiled_fir = None
                self.compiled_bytecode = None

            self.version += 1
            self.checksum = self._compute_checksum()
            elapsed = time.monotonic_ns() - start
            self.compilation_time_ns = elapsed

            return CompileResult(
                success=True,
                compile_time_ns=elapsed,
                checksum=self.checksum,
            )
        except Exception as exc:
            elapsed = time.monotonic_ns() - start
            self.compilation_time_ns = elapsed
            return CompileResult(
                success=False,
                error=str(exc),
                compile_time_ns=elapsed,
            )

    # ── Recompilation ───────────────────────────────────────────────────

    def recompile(self, new_source: str, ctx: TypeContext) -> CompileResult:
        """Replace source and recompile."""
        self.source = new_source
        self.checksum = self._compute_checksum()
        self.invalidate()
        return self.compile(ctx)

    # ── Invalidation ────────────────────────────────────────────────────

    def invalidate(self) -> None:
        """Clear cached compiled artifacts."""
        self.compiled_fir = None
        self.compiled_bytecode = None
        self.metadata.pop("last_compiled", None)
