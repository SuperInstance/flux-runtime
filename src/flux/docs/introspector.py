"""Code Introspection — extracts structure from Python source files using AST."""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ComplexityMetrics:
    """Complexity metrics for a module or function."""

    loc: int = 0
    cyclomatic: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0
    avg_function_length: float = 0.0


@dataclass
class ModuleInfo:
    """Metadata about a Python module."""

    name: str = ""
    path: str = ""
    description: str = ""  # from docstring
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    loc: int = 0


@dataclass
class APIDeclaration:
    """A public API declaration in a module."""

    name: str = ""
    kind: str = ""  # "class", "function", "constant", "enum"
    signature: str = ""
    docstring: str = ""
    module: str = ""


class CodeIntrospector:
    """Introspects Python source files to extract structure.

    Uses the ``ast`` module for primary analysis and falls back to
    regex / heuristic parsing where AST alone is insufficient.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    # ── Module listing ─────────────────────────────────────────────────

    def list_modules(self) -> list[ModuleInfo]:
        """List all FLUX modules with metadata.

        Walks ``src/flux/*/`` directories and returns a :class:`ModuleInfo`
        for every ``.py`` file found.
        """
        modules: list[ModuleInfo] = []
        flux_dir = Path(self.repo_path) / "src" / "flux"
        if not flux_dir.is_dir():
            return modules

        for py_file in sorted(flux_dir.rglob("*.py")):
            rel = py_file.relative_to(flux_dir)
            info = self.get_module_info(str(py_file))
            if info is not None:
                modules.append(info)
        return modules

    # ── Per-module info ────────────────────────────────────────────────

    def get_module_info(self, module_path: str) -> Optional[ModuleInfo]:
        """Get detailed info about a single module file."""
        path = Path(module_path)
        if not path.is_file():
            return None

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

        tree = ast.parse(source, filename=str(path))

        name = path.stem
        description = ast.get_docstring(tree) or ""
        classes: list[str] = []
        functions: list[str] = []
        constants: list[str] = []
        imports: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        constants.append(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if not node.target.id.startswith("_"):
                    constants.append(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(self._import_name(node))

        # Also pick up top-level variables assigned with all-caps heuristic
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper() and target.id not in constants:
                        constants.append(target.id)

        loc = _count_loc(source)

        return ModuleInfo(
            name=name,
            path=str(path),
            description=description,
            classes=classes,
            functions=functions,
            constants=constants,
            imports=imports,
            loc=loc,
        )

    # ── Public API ─────────────────────────────────────────────────────

    def get_public_api(self, module_path: str) -> list[APIDeclaration]:
        """Get all public declarations (no leading underscore)."""
        info = self.get_module_info(module_path)
        if info is None:
            return []

        declarations: list[APIDeclaration] = []

        # Re-parse to get signatures + docstrings
        try:
            source = Path(module_path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            # Fall back to info-level data
            for cls_name in info.classes:
                declarations.append(APIDeclaration(
                    name=cls_name, kind="class", module=info.name,
                ))
            for fn_name in info.functions:
                declarations.append(APIDeclaration(
                    name=fn_name, kind="function", module=info.name,
                ))
            for const_name in info.constants:
                declarations.append(APIDeclaration(
                    name=const_name, kind="constant", module=info.name,
                ))
            return declarations

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                bases = ", ".join(
                    _ast_name(base) for base in node.bases
                )
                sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                doc = ast.get_docstring(node) or ""
                declarations.append(APIDeclaration(
                    name=node.name, kind="class", signature=sig,
                    docstring=doc, module=info.name,
                ))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                args = _signature_from_func(node)
                prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                sig = f"{prefix}{node.name}({args})"
                doc = ast.get_docstring(node) or ""
                kind = "function"
                # Detect enums
                declarations.append(APIDeclaration(
                    name=node.name, kind=kind, signature=sig,
                    docstring=doc, module=info.name,
                ))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        kind = "enum" if _looks_like_enum(node) else "constant"
                        declarations.append(APIDeclaration(
                            name=target.id, kind=kind, module=info.name,
                        ))

        return declarations

    # ── Dependencies ───────────────────────────────────────────────────

    def get_dependencies(self, module_path: str) -> list[str]:
        """Extract import dependencies from a module.

        Returns a list of dotted module names that the file imports.
        """
        try:
            source = Path(module_path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            return []

        deps: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    deps.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.append(node.module)
        return deps

    # ── Complexity ─────────────────────────────────────────────────────

    def get_complexity(self, module_path: str) -> ComplexityMetrics:
        """Compute complexity metrics: LOC, cyclomatic complexity, etc."""
        try:
            source = Path(module_path).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(module_path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            return ComplexityMetrics()

        loc = _count_loc(source)
        func_lengths: list[int] = []
        total_cyclo = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_lengths.append(
                    node.end_lineno - node.lineno + 1 if node.end_lineno else 1
                )
                total_cyclo += _cyclomatic_complexity(node)

        func_count = len(func_lengths)
        class_count = sum(
            1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
        )
        import_count = sum(
            1 for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom))
        )
        avg_len = sum(func_lengths) / len(func_lengths) if func_lengths else 0.0

        return ComplexityMetrics(
            loc=loc,
            cyclomatic=total_cyclo,
            function_count=func_count,
            class_count=class_count,
            import_count=import_count,
            avg_function_length=avg_len,
        )

    # ── Test coverage (heuristic) ──────────────────────────────────────

    def get_test_coverage(self) -> dict[str, float]:
        """Map modules to heuristic test coverage.

        Coverage is estimated by counting how many test files reference
        each source module. Returns a dict mapping module name to a
        coverage score in [0.0, 1.0].
        """
        tests_dir = Path(self.repo_path) / "tests"
        if not tests_dir.is_dir():
            return {}

        # Count references per module
        module_refs: dict[str, int] = {}
        module_names = self._module_names()

        for test_file in tests_dir.glob("test_*.py"):
            try:
                source = test_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for mod_name in module_names:
                # Count occurrences of import pattern
                pattern = re.compile(
                    rf"(?:from\s+flux\.{re.escape(mod_name)}|import\s+flux\.{re.escape(mod_name)})"
                )
                matches = pattern.findall(source)
                if matches:
                    module_refs[mod_name] = module_refs.get(mod_name, 0) + len(matches)

        if not module_refs:
            return {}

        max_refs = max(module_refs.values()) if module_refs else 1
        return {
            name: min(refs / max_refs, 1.0)
            for name, refs in module_refs.items()
            if refs > 0
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _import_name(self, node: ast.Import | ast.ImportFrom) -> str:
        if isinstance(node, ast.Import):
            return node.names[0].name if node.names else ""
        return node.module or ""

    def _module_names(self) -> list[str]:
        """Get top-level module directory names under src/flux/."""
        flux_dir = Path(self.repo_path) / "src" / "flux"
        if not flux_dir.is_dir():
            return []
        return sorted(
            d.name for d in flux_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_")
            and d.name != "__pycache__"
        )


# ── Module-level helpers ──────────────────────────────────────────────


def _count_loc(source: str) -> int:
    """Count non-empty, non-comment lines."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _ast_name(node: ast.expr) -> str:
    """Best-effort extraction of a name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_ast_name(node.value)}.{node.attr}"
    return repr(node)


def _signature_from_func(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a simple argument signature string."""
    parts: list[str] = []
    for arg in node.args.args:
        s = arg.arg
        if arg.annotation:
            s += f": {_ast_name(arg.annotation)}"
        parts.append(s)
    if node.args.vararg:
        parts.append(f"*{node.args.vararg.arg}")
    if node.args.kwonlyargs:
        for arg in node.args.kwonlyargs:
            s = arg.arg
            if arg.annotation:
                s += f": {_ast_name(arg.annotation)}"
            parts.append(s)
    if node.args.kwarg:
        parts.append(f"**{node.args.kwarg.arg}")
    return ", ".join(parts)


def _looks_like_enum(node: ast.Assign) -> bool:
    """Heuristic: does this assignment look like an enum constant?"""
    return isinstance(node.value, (ast.Constant, ast.Call))


def _cyclomatic_complexity(node: ast.AST) -> int:
    """Compute cyclomatic complexity for a single function node."""
    complexity = 1  # base
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, (ast.BoolOp,)):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.IfExp):  # ternary
            complexity += 1
        elif isinstance(child, ast.comprehension):
            complexity += 1
        # and/or in boolean ops already handled above
    return complexity
