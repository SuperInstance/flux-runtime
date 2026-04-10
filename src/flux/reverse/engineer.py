"""Core Reverse Engineering Engine for FLUX.

Provides FluxReverseEngineer — the main entry point for analyzing source
code in any supported language and mapping it to FLUX FIR equivalents.
"""

from __future__ import annotations

from typing import Optional

from flux.reverse.code_map import (
    CodeMapping,
    CodeMap,
    ConstructType,
    Difficulty,
    MigrationStep,
    MigrationPlan,
)
from flux.reverse.parsers.python_reverse import PythonReverseEngineer
from flux.reverse.parsers.c_reverse import CReverseEngineer


# Map of supported languages to their reverse engineers
_ENGINES = {
    "python": PythonReverseEngineer,
    "c": CReverseEngineer,
    # Future: "javascript": JavaScriptReverseEngineer,
    # Future: "rust": RustReverseEngineer,
}

# File extension to language mapping
_EXTENSION_MAP = {
    ".py": "python",
    ".c": "c",
    ".h": "c",
    # Future: ".js": "javascript", ".ts": "javascript",
    # Future: ".rs": "rust",
}


class UnsupportedLanguageError(Exception):
    """Raised when a language is not supported for reverse engineering."""
    pass


class FluxReverseEngineer:
    """Analyzes source code in Python, C, JavaScript, or Rust and maps
    each construct to its FLUX FIR equivalent.

    This is the main entry point for the reverse engineering module.
    It dispatches to language-specific analyzers and produces:
    - A CodeMap showing how each construct maps
    - A MigrationPlan with step-by-step migration instructions

    Usage::

        engineer = FluxReverseEngineer()
        code_map = engineer.analyze(python_code, lang="python")
        plan = engineer.migration_plan(python_code, lang="python")

    Or auto-detect language from file extension::

        code_map = engineer.analyze_file("my_function.py")
    """

    def __init__(self):
        self._python_engine = PythonReverseEngineer()
        self._c_engine = CReverseEngineer()

    # ── Public API ─────────────────────────────────────────────────────

    @property
    def supported_languages(self) -> list[str]:
        """List of supported source languages."""
        return list(_ENGINES.keys())

    def analyze(self, source: str, lang: str) -> CodeMap:
        """Analyze source code and produce a CodeMap.

        Args:
            source: Source code text.
            lang: Language identifier ("python", "c").

        Returns:
            CodeMap with construct-to-FIR mappings.

        Raises:
            UnsupportedLanguageError: If the language is not supported.
        """
        engine = self._get_engine(lang)
        return engine.analyze(source)

    def migration_plan(self, source: str, lang: str) -> MigrationPlan:
        """Generate a migration plan from source code to FLUX.

        Args:
            source: Source code text.
            lang: Language identifier ("python", "c").

        Returns:
            MigrationPlan with ordered steps.

        Raises:
            UnsupportedLanguageError: If the language is not supported.
        """
        engine = self._get_engine(lang)
        return engine.migration_plan(source)

    def analyze_file(self, filepath: str) -> CodeMap:
        """Analyze a source file, auto-detecting language from extension.

        Args:
            filepath: Path to the source file.

        Returns:
            CodeMap with construct-to-FIR mappings.

        Raises:
            UnsupportedLanguageError: If the file extension is not recognized.
            FileNotFoundError: If the file does not exist.
        """
        import os

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        lang = self._detect_language(filepath)
        with open(filepath, "r") as f:
            source = f.read()

        return self.analyze(source, lang)

    def analyze_directory(self, dirpath: str) -> dict[str, CodeMap]:
        """Analyze all source files in a directory.

        Args:
            dirpath: Path to the directory.

        Returns:
            Dict mapping filename to its CodeMap.
        """
        import os

        results: dict[str, CodeMap] = {}
        if not os.path.isdir(dirpath):
            raise FileNotFoundError(f"Directory not found: {dirpath}")

        for filename in sorted(os.listdir(dirpath)):
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in _EXTENSION_MAP:
                    try:
                        results[filename] = self.analyze_file(filepath)
                    except Exception as e:
                        # Create a placeholder error map
                        results[filename] = CodeMap(
                            source_lang=_EXTENSION_MAP[ext],
                            source_code=f"(error reading file: {e})",
                            mappings=[],
                            summary=f"Error analyzing file: {e}",
                        )

        return results

    def full_migration_plan(self, dirpath: str) -> MigrationPlan:
        """Generate a combined migration plan for all files in a directory.

        Args:
            dirpath: Path to the directory.

        Returns:
            Combined MigrationPlan covering all files.
        """
        code_maps = self.analyze_directory(dirpath)
        all_steps: list[MigrationStep] = []
        step_num = 1

        for filename, code_map in sorted(code_maps.items()):
            plan = self.migration_plan(code_map.source_code, code_map.source_lang)
            for step in plan.steps:
                all_steps.append(MigrationStep(
                    step_number=step_num,
                    description=f"[{filename}] {step.description}",
                    original_code=step.original_code,
                    flux_code=step.flux_code,
                    difficulty=step.difficulty,
                    estimated_effort=step.estimated_effort,
                ))
                step_num += 1

        overview = (
            f"Combined migration plan for {len(code_maps)} files "
            f"({len(all_steps)} total steps). "
            f"Estimated total effort: {MigrationPlan('', len(all_steps), all_steps).estimated_total_effort}."
        )

        lang = code_maps.values()[0].source_lang if code_maps else "unknown"

        return MigrationPlan(
            source_lang=lang,
            total_steps=len(all_steps),
            steps=all_steps,
            overview=overview,
        )

    def generate_flux_md(self, source: str, lang: str) -> str:
        """Generate a FLUX.MD file equivalent from source code.

        Args:
            source: Source code text.
            lang: Language identifier.

        Returns:
            FLUX.MD formatted string.
        """
        code_map = self.analyze(source, lang)
        lines = [
            "---",
            f"lang: flux",
            f"source-lang: {lang}",
            f"generated-by: reverse-engineer",
            f"mappings: {code_map.mapping_count}",
            "---",
            "",
            "# Reverse-Engineered FLUX Module",
            "",
            f"> Auto-generated from {lang} source code.",
            f"> Mapping confidence: {code_map.avg_confidence:.1%}",
            "",
        ]

        # Group by construct type
        seen = set()
        type_order = [
            ConstructType.IMPORT, ConstructType.PREPROCESSOR,
            ConstructType.CLASS, ConstructType.STRUCT,
            ConstructType.VARIABLE, ConstructType.POINTER,
            ConstructType.FUNCTION,
            ConstructType.LOOP,
            ConstructType.CALL,
            ConstructType.IO_WRITE,
            ConstructType.ERROR_HANDLING,
            ConstructType.ASYNC,
            ConstructType.COMPREHENSION,
            ConstructType.DECORATOR,
            ConstructType.MEMORY,
        ]

        for ctype in type_order:
            mappings = code_map.get_mappings_by_type(ctype)
            for m in mappings:
                if m.original not in seen:
                    seen.add(m.original)
                    lines.extend([
                        f"## {ctype}",
                        "",
                        f"**Original ({lang}):**",
                        "```" + lang,
                        m.original.strip(),
                        "```",
                        "",
                        f"**FLUX FIR:**",
                        "```flux",
                        m.flux_ir.strip(),
                        "```",
                        "",
                        f"*{m.notes}*",
                        f"*Confidence: {m.confidence:.0%}*",
                        "",
                    ])

        return "\n".join(lines)

    # ── Private helpers ────────────────────────────────────────────────

    def _get_engine(self, lang: str):
        """Get the language-specific reverse engineer."""
        lang_lower = lang.lower().strip()
        if lang_lower not in _ENGINES:
            supported = ", ".join(_ENGINES.keys())
            raise UnsupportedLanguageError(
                f"Unsupported language: '{lang}'. Supported: {supported}"
            )
        if lang_lower == "python":
            return self._python_engine
        if lang_lower == "c":
            return self._c_engine
        return _ENGINES[lang_lower]()

    @staticmethod
    def _detect_language(filepath: str) -> str:
        """Detect language from file extension."""
        import os
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in _EXTENSION_MAP:
            supported = ", ".join(_EXTENSION_MAP.keys())
            raise UnsupportedLanguageError(
                f"Cannot detect language for file extension '{ext}'. "
                f"Supported extensions: {supported}"
            )
        return _EXTENSION_MAP[ext]
