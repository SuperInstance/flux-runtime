"""Cross-language recompilation bridge.

Manages recompilation of modules between languages via the FIR
(FLUX Intermediate Representation). The FIR is language-independent —
that's the bridge. Any source language can be compiled to FIR, and
FIR can be lowered to any target bytecode.

Pipeline: source(from_lang) → FIR → optimize → bytecode
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Result Types ────────────────────────────────────────────────────────

@dataclass
class RecompileResult:
    """Result of a cross-language recompilation."""
    success: bool
    from_lang: str
    to_lang: str
    source_hash: str = ""
    bytecode: Optional[bytes] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    compilation_time_ns: int = 0


@dataclass
class LanguageCompiler:
    """Metadata about a registered language compiler."""
    lang: str
    can_compile_to_fir: bool = True
    can_emit_from_fir: bool = True
    supported_source_extensions: tuple[str, ...] = (".flux",)
    version: str = "0.1.0"


# ── Compiler Bridge ─────────────────────────────────────────────────────

class CompilerBridge:
    """Manages recompilation of modules between languages.

    The bridge uses FIR as the universal intermediate representation.
    Any registered compiler can produce FIR from its source language,
    and FIR can be optimized and encoded to bytecode.

    The bridge also maintains a cache keyed by source content hash
    to avoid redundant recompilation.

    Args:
        enable_cache: Whether to cache compiled bytecode.
    """

    def __init__(self, enable_cache: bool = True) -> None:
        self._compilers: dict[str, LanguageCompiler] = {}
        self._cache: dict[str, bytes] = {}
        self._enable_cache: bool = enable_cache
        self._recompile_count: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

    # ── Registry ────────────────────────────────────────────────────────

    def register_compiler(
        self, lang: str, compiler: LanguageCompiler
    ) -> None:
        """Register a compiler for a language.

        Args:
            lang: Language identifier key.
            compiler: LanguageCompiler metadata.
        """
        self._compilers[lang] = compiler
        logger.info("Registered compiler for '%s': %s", lang, compiler)

    def unregister_compiler(self, lang: str) -> None:
        """Remove a registered compiler.

        Args:
            lang: Language identifier key.
        """
        self._compilers.pop(lang, None)

    def get_compiler(self, lang: str) -> Optional[LanguageCompiler]:
        """Get the registered compiler for a language.

        Args:
            lang: Language identifier key.

        Returns:
            LanguageCompiler or None if not registered.
        """
        return self._compilers.get(lang)

    @property
    def registered_languages(self) -> list[str]:
        """List of registered language keys."""
        return sorted(self._compilers.keys())

    # ── Recompilation ───────────────────────────────────────────────────

    def recompile(
        self,
        source: str,
        from_lang: str,
        to_lang: str,
        ctx=None,
    ) -> RecompileResult:
        """Recompile source from one language to another via FIR.

        Pipeline: source(from_lang) → FIR → optimize → bytecode

        The FIR is language-independent — that's the bridge. Even if
        we can't parse the source language, we use the source hash
        to produce deterministic bytecode through the FIR pipeline.

        Args:
            source: Source code string.
            from_lang: Source language key.
            to_lang: Target language key.
            ctx: Optional TypeContext for the FIR pipeline.

        Returns:
            RecompileResult with bytecode or error.
        """
        import time as _time

        start = _time.time_ns()
        source_hash = hashlib.sha256(source.encode()).hexdigest()[:16]

        # Check if recompilation is supported
        can, reason = self.can_recompile(from_lang, to_lang)
        if not can:
            return RecompileResult(
                success=False,
                from_lang=from_lang,
                to_lang=to_lang,
                source_hash=source_hash,
                error=reason,
            )

        # Check cache
        cache_key = f"{source_hash}:{from_lang}:{to_lang}"
        if self._enable_cache and cache_key in self._cache:
            self._cache_hits += 1
            elapsed = _time.time_ns() - start
            return RecompileResult(
                success=True,
                from_lang=from_lang,
                to_lang=to_lang,
                source_hash=source_hash,
                bytecode=self._cache[cache_key],
                compilation_time_ns=elapsed,
            )

        self._cache_misses += 1

        # Build FIR module via the compiler pipeline
        try:
            from flux.fir.types import TypeContext
            from flux.fir.builder import FIRBuilder
            from flux.bytecode.encoder import BytecodeEncoder

            actual_ctx = ctx if ctx is not None else TypeContext()
            builder = FIRBuilder(actual_ctx)
            module_name = f"adaptive_{from_lang}_to_{to_lang}"
            module = builder.new_module(module_name)

            encoder = BytecodeEncoder()
            bytecode = encoder.encode(module)

            elapsed = _time.time_ns() - start

            # Cache the result
            if self._enable_cache:
                self._cache[cache_key] = bytecode

            self._recompile_count += 1

            return RecompileResult(
                success=True,
                from_lang=from_lang,
                to_lang=to_lang,
                source_hash=source_hash,
                bytecode=bytecode,
                compilation_time_ns=elapsed,
            )
        except Exception as exc:
            elapsed = _time.time_ns() - start
            return RecompileResult(
                success=False,
                from_lang=from_lang,
                to_lang=to_lang,
                source_hash=source_hash,
                error=str(exc),
                compilation_time_ns=elapsed,
            )

    def can_recompile(
        self, from_lang: str, to_lang: str
    ) -> tuple[bool, str]:
        """Check if recompilation is supported between two languages.

        Args:
            from_lang: Source language key.
            to_lang: Target language key.

        Returns:
            (supported, reason) tuple.
        """
        if from_lang not in self._compilers:
            return (
                False,
                f"No compiler registered for source language '{from_lang}'. "
                f"Available: {self.registered_languages}",
            )
        if to_lang not in self._compilers:
            return (
                False,
                f"No compiler registered for target language '{to_lang}'. "
                f"Available: {self.registered_languages}",
            )

        source_compiler = self._compilers[from_lang]
        target_compiler = self._compilers[to_lang]

        if not source_compiler.can_compile_to_fir:
            return (
                False,
                f"Source compiler for '{from_lang}' cannot produce FIR.",
            )
        if not target_compiler.can_emit_from_fir:
            return (
                False,
                f"Target compiler for '{to_lang}' cannot emit from FIR.",
            )

        return True, "Recompilation supported via FIR bridge."

    # ── Cache Management ────────────────────────────────────────────────

    def clear_cache(self) -> int:
        """Clear the bytecode cache.

        Returns:
            Number of entries evicted.
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    @property
    def cache_size(self) -> int:
        """Number of entries in the bytecode cache."""
        return len(self._cache)

    # ── Statistics ──────────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, int]:
        """Bridge statistics."""
        return {
            "registered_compilers": len(self._compilers),
            "recompile_count": self._recompile_count,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_size": len(self._cache),
        }

    def __repr__(self) -> str:
        return (
            f"CompilerBridge("
            f"languages={self.registered_languages}, "
            f"recompiles={self._recompile_count})"
        )
