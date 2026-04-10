"""FLUX Migrator — Convert source code to FLUX.MD format.

Supports Python (via ast module), C (via regex), and JavaScript (via regex).
For each source file, produces a structured FLUX.MD document with:
  - ## module: header with filename
  - ## lang: language identifier
  - ### Section: / ### Code: blocks for each discovered function/struct/class
  - Original source preserved in code blocks
  - FIR mapping comments showing how constructs map to FLUX IR
"""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

from flux.migrate.report import MigratedFile, MigrationReport


# ── Language detection ─────────────────────────────────────────────────────────

LANG_EXTENSIONS: dict[str, Set[str]] = {
    "python": {".py", ".pyw"},
    "c": {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"},
    "js": {".js", ".jsx", ".mjs", ".cjs"},
}

ALL_EXTENSIONS: Set[str] = set()
for _exts in LANG_EXTENSIONS.values():
    ALL_EXTENSIONS |= _exts


def detect_language(path: Path, explicit: Optional[str] = None) -> str:
    """Detect source language from file extension or explicit override.

    Args:
        path: File path to examine.
        explicit: Explicit language string ('python', 'c', 'js', 'auto').

    Returns:
        Language string: 'python', 'c', or 'js'.
    """
    if explicit and explicit != "auto":
        return explicit.lower()

    suffix = path.suffix.lower()
    for lang, exts in LANG_EXTENSIONS.items():
        if suffix in exts:
            return lang

    # Default: treat unknown extensions as C
    return "c"


# ── FLUX.MD generation helpers ────────────────────────────────────────────────

def _section_header(title: str) -> str:
    """Return a markdown heading for a FLUX.MD section."""
    return f"### {title}"


def _code_block(language: str, code: str) -> str:
    """Return a fenced code block."""
    return f"```{language}\n{code}\n```"


def _fir_comment(comment: str) -> str:
    """Return a FIR mapping comment line."""
    return f"// FIR: {comment}"


# ── Python migrator ────────────────────────────────────────────────────────────

def _extract_python_imports(tree: ast.AST) -> List[Tuple[str, List[str], bool]]:
    """Extract import statements from Python AST.

    Returns list of (module, names, is_from_import).
    """
    imports: List[Tuple[str, List[str], bool]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            imports.append(("", names, False))
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names]
            imports.append((node.module or "", names, True))
    return imports


def _extract_python_functions(tree: ast.AST) -> List[ast.FunctionDef]:
    """Extract all top-level function definitions."""
    return [
        node for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef)
    ]


def _extract_python_classes(tree: ast.AST) -> List[ast.ClassDef]:
    """Extract all top-level class definitions."""
    return [
        node for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.ClassDef)
    ]


def _get_source_lines(source: str, node: ast.AST) -> str:
    """Get the source lines for a specific AST node."""
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", len(lines))
    return "\n".join(lines[start:end])


def _count_complexity(node: ast.FunctionDef) -> str:
    """Count branches and loops to determine FIR mapping hint."""
    branches = 0
    loops = 0
    calls = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.IfExp)):
            branches += 1
        elif isinstance(child, (ast.For, ast.While)):
            loops += 1
        elif isinstance(child, ast.Call):
            calls += 1

    parts = []
    if branches:
        parts.append(f"{branches} branch(es)")
    if loops:
        parts.append(f"{loops} loop(s)")
    if calls:
        parts.append(f"{calls} call(s)")

    return ", ".join(parts) if parts else "simple"


def _python_param_types(node: ast.FunctionDef) -> List[str]:
    """Extract parameter names and annotation hints."""
    params = []
    for arg in node.args.args:
        name = arg.arg
        if arg.annotation:
            if isinstance(arg.annotation, ast.Name):
                params.append(f"{name}: {arg.annotation.id}")
            elif isinstance(arg.annotation, ast.Subscript):
                params.append(f"{name}: {_ast_to_str(arg.annotation)}")
            else:
                params.append(f"{name}: {_ast_to_str(arg.annotation)}")
        else:
            params.append(name)
    return params


def _ast_to_str(node: ast.AST) -> str:
    """Best-effort AST node to string conversion."""
    try:
        import ast as _ast
        return _ast.unparse(node)
    except Exception:
        return ast.dump(node)


def _migrate_python(source: str, filename: str) -> Tuple[str, int, int, int]:
    """Convert Python source to FLUX.MD format.

    Returns:
        (flux_md_content, function_count, class_count, import_count)
    """
    lines: list[str] = []
    w = lines.append

    module_name = Path(filename).stem

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        # Return the raw source wrapped in a minimal FLUX.MD
        w(f"## module: {module_name}")
        w(f"## lang: python")
        w("")
        w(_section_header("Code"))
        w("")
        w(_code_block("python", source))
        return "\n".join(lines), 0, 0, 0

    # ── Header ─────────────────────────────────────────────────────────────
    w(f"## module: {module_name}")
    w(f"## lang: python")
    w("")

    # ── Imports ────────────────────────────────────────────────────────────
    imports = _extract_python_imports(tree)
    if imports:
        w(_section_header("Imports"))
        w("")
        for module, names, is_from in imports:
            if is_from:
                w(f"from {module} import {', '.join(names)}")
            else:
                w(f"import {', '.join(names)}")
            w(_fir_comment(f"import → FIR ModuleRef({module})"))
            w("")

    # ── Classes ────────────────────────────────────────────────────────────
    classes = _extract_python_classes(tree)
    for cls in classes:
        w(_section_header(f"Class: {cls.name}"))
        bases = []
        for base in cls.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            else:
                bases.append(_ast_to_str(base))
        if bases:
            w(f"Inherits: {', '.join(bases)}")
        w(_fir_comment(f"class → FIR Struct(name={cls.name}, fields=[...])"))
        w("")

        for item in cls.body:
            if isinstance(item, ast.FunctionDef):
                w(_section_header(f"Method: {cls.name}.{item.name}"))
                w("")
                w(_fir_comment(
                    f"method → FIR Func(@{item.name}), "
                    f"params={len(item.args.args)}, "
                    f"{_count_complexity(item)}"
                ))
                w("")
                code = _get_source_lines(source, item)
                w(_code_block("python", code))
                w("")

    # ── Functions ──────────────────────────────────────────────────────────
    functions = _extract_python_functions(tree)
    for func in functions:
        w(_section_header(f"Function: {func.name}"))
        w("")
        params = _python_param_types(func)
        w(f"Signature: {func.name}({', '.join(params)})")
        w(_fir_comment(
            f"func → FIR Func(@{func.name}), "
            f"sig=({', '.join(p.split(':')[-1].strip() or 'i32' for p in params)}), "
            f"{_count_complexity(func)}"
        ))
        w("")
        code = _get_source_lines(source, func)
        w(_code_block("python", code))
        w("")

    # ── Full source ────────────────────────────────────────────────────────
    w(_section_header("Full Source"))
    w("")
    w(_code_block("python", source))

    return "\n".join(lines), len(functions), len(classes), len(imports)


# ── C migrator ─────────────────────────────────────────────────────────────────

# Regex patterns for C parsing
_C_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)
_C_FUNC_RE = re.compile(
    r'^(?:(?:static|inline|extern|const|unsigned|signed|long|short)\s+)*'
    r'(?:void|int|char|float|double|long\s+long|unsigned\s+int|unsigned\s+char|bool|size_t)\s*'
    r'\*?\s*(\w+)\s*\(([^)]*)\)\s*\{?',
    re.MULTILINE,
)
_C_STRUCT_RE = re.compile(
    r'^\s*typedef\s+struct\s*(?:\w*)?\s*\{',
    re.MULTILINE,
)
_C_STRUCT_NAME_RE = re.compile(
    r'\}\s*(\w+)\s*;',
    re.MULTILINE,
)


def _extract_c_includes(source: str) -> List[str]:
    """Extract #include directives."""
    return _C_INCLUDE_RE.findall(source)


def _extract_c_functions(source: str) -> List[Tuple[str, str, int, int]]:
    """Extract C function signatures.

    Returns list of (name, params_str, start_line, brace_count).
    """
    matches = []
    for m in _C_FUNC_RE.finditer(source):
        name = m.group(1)
        # Skip common C keywords that match the pattern
        if name in ("if", "while", "for", "switch", "return", "sizeof", "typedef"):
            continue
        params = m.group(2).strip()
        line_num = source[:m.start()].count("\n") + 1
        matches.append((name, params, line_num, 0))
    return matches


def _extract_c_structs(source: str) -> List[str]:
    """Extract C struct type names."""
    names: List[str] = []
    # Simple approach: find typedef struct ... NAME patterns
    for m in re.finditer(
        r'typedef\s+struct\s*(?:\w*\s*)?\{([^}]*)\}\s*(\w+)\s*;',
        source,
        re.DOTALL,
    ):
        names.append(m.group(2))
    # Also match: struct name { ... };  (no typedef)
    for m in re.finditer(r'struct\s+(\w+)\s*\{', source):
        if m.group(1) not in names:
            names.append(m.group(1))
    return names


def _c_params_to_fir(params_str: str) -> str:
    """Convert C parameter string to FIR type signature."""
    if not params_str or params_str.strip() == "void":
        return "()"
    params = []
    for p in params_str.split(","):
        p = p.strip()
        if not p:
            continue
        # Extract type (last word before param name, or the whole thing)
        tokens = p.split()
        type_str = "i32"  # default
        for tok in tokens:
            if tok in ("int", "short", "long"):
                type_str = "i32"
            elif tok in ("float",):
                type_str = "f32"
            elif tok in ("double",):
                type_str = "f64"
            elif tok in ("char", "unsigned", "signed", "void"):
                type_str = "i32"
            elif tok.startswith("*"):
                type_str = "ptr"
        params.append(type_str)
    return f"({', '.join(params)})"


def _find_c_function_body(source: str, func_name: str, start_pos: int) -> str:
    """Find the body of a C function starting from a position."""
    # Find the opening brace
    brace_pos = source.find("{", start_pos)
    if brace_pos == -1:
        return ""
    depth = 0
    end_pos = brace_pos
    for i in range(brace_pos, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break

    # Get the full function including signature
    line_start = source.rfind("\n", 0, start_pos) + 1
    func_text = source[line_start:end_pos].strip()
    return func_text


def _migrate_c(source: str, filename: str) -> Tuple[str, int, int, int]:
    """Convert C source to FLUX.MD format.

    Returns:
        (flux_md_content, function_count, struct_count, include_count)
    """
    lines: list[str] = []
    w = lines.append

    module_name = Path(filename).stem

    w(f"## module: {module_name}")
    w(f"## lang: c")
    w("")

    # ── Includes ───────────────────────────────────────────────────────────
    includes = _extract_c_includes(source)
    if includes:
        w(_section_header("Includes"))
        w("")
        for inc in includes:
            w(f"#include <{inc}>" if "<" in inc else f'#include "{inc}"')
            w(_fir_comment(f"include → FIR Import({inc})"))
            w("")

    # ── Structs ────────────────────────────────────────────────────────────
    structs = _extract_c_structs(source)
    for struct_name in structs:
        w(_section_header(f"Struct: {struct_name}"))
        w("")
        w(_fir_comment(f"struct → FIR Struct(name={struct_name}, ...fields)"))
        w("")

    # ── Functions ──────────────────────────────────────────────────────────
    functions = _extract_c_functions(source)
    func_count = len(functions)
    for name, params_str, lineno, _ in functions:
        w(_section_header(f"Function: {name}"))
        w("")
        sig = _c_params_to_fir(params_str)
        w(f"Signature: {name}{sig}")
        w(_fir_comment(f"func → FIR Func(@{name}), sig={sig}"))
        w("")

        # Try to find the function body
        pattern = re.compile(r'\b' + re.escape(name) + r'\s*\(')
        match = pattern.search(source)
        if match:
            body = _find_c_function_body(source, name, match.start())
            if body:
                w(_code_block("c", body))
        else:
            w(f"// Function body not extracted for {name}")
        w("")

    # ── Full source ────────────────────────────────────────────────────────
    w(_section_header("Full Source"))
    w("")
    w(_code_block("c", source))

    return "\n".join(lines), func_count, len(structs), len(includes)


# ── JavaScript migrator ───────────────────────────────────────────────────────

_JS_FUNC_RE = re.compile(
    r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
    re.MULTILINE,
)
_JS_ARROW_RE = re.compile(
    r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
    re.MULTILINE,
)
_JS_CLASS_RE = re.compile(
    r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{',
    re.MULTILINE,
)
_JS_IMPORT_RE = re.compile(
    r'import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+[\'"]([^"\']+)[\'"]',
    re.MULTILINE,
)


def _extract_js_imports(source: str) -> List[Tuple[str, str]]:
    """Extract ES module imports. Returns list of (names, module)."""
    imports: List[Tuple[str, str]] = []
    for m in _JS_IMPORT_RE.finditer(source):
        names = m.group(1) or m.group(2) or "*"
        module = m.group(3)
        imports.append((names.strip(), module))
    return imports


def _extract_js_functions(source: str) -> List[Tuple[str, str]]:
    """Extract function declarations and arrow functions."""
    funcs: List[Tuple[str, str]] = []
    for m in _JS_FUNC_RE.finditer(source):
        funcs.append((m.group(1), m.group(2)))
    for m in _JS_ARROW_RE.finditer(source):
        funcs.append((m.group(1), m.group(2)))
    return funcs


def _extract_js_classes(source: str) -> List[Tuple[str, str]]:
    """Extract class declarations. Returns list of (name, parent)."""
    classes: List[Tuple[str, str]] = []
    for m in _JS_CLASS_RE.finditer(source):
        classes.append((m.group(1), m.group(2) or ""))
    return classes


def _migrate_js(source: str, filename: str) -> Tuple[str, int, int, int]:
    """Convert JavaScript source to FLUX.MD format.

    Returns:
        (flux_md_content, function_count, class_count, import_count)
    """
    lines: list[str] = []
    w = lines.append

    module_name = Path(filename).stem

    w(f"## module: {module_name}")
    w(f"## lang: javascript")
    w("")

    # ── Imports ───────────────────────────────────────────────────────────
    imports = _extract_js_imports(source)
    if imports:
        w(_section_header("Imports"))
        w("")
        for names, module in imports:
            w(f"import {{ {names} }} from '{module}'")
            w(_fir_comment(f"import → FIR Import({module})"))
            w("")

    # ── Classes ────────────────────────────────────────────────────────────
    classes = _extract_js_classes(source)
    for name, parent in classes:
        w(_section_header(f"Class: {name}"))
        if parent:
            w(f"Extends: {parent}")
        w(_fir_comment(f"class → FIR Struct(name={name})"))
        w("")

    # ── Functions ──────────────────────────────────────────────────────────
    functions = _extract_js_functions(source)
    func_count = len(functions)
    for name, params_str in functions:
        w(_section_header(f"Function: {name}"))
        w("")
        w(f"Signature: {name}({params_str})")
        w(_fir_comment(f"func → FIR Func(@{name})"))
        w("")

    # ── Full source ────────────────────────────────────────────────────────
    w(_section_header("Full Source"))
    w("")
    w(_code_block("javascript", source))

    return "\n".join(lines), func_count, len(classes), len(imports)


# ── FluxMigrator ───────────────────────────────────────────────────────────────

# Map language to the migrate function
_MIGRATE_FNS = {
    "python": _migrate_python,
    "c": _migrate_c,
    "js": _migrate_js,
}


class FluxMigrator:
    """Migrate source files to FLUX.MD format.

    Supports Python (via AST analysis), C (via regex), and JavaScript (via regex).
    For each source file, produces a structured FLUX.MD document with proper
    headers, sections, code blocks, and FIR IR mapping comments.

    Example::

        migrator = FluxMigrator(output_dir="./flux_output", verbose=True)
        report = migrator.migrate_file(Path("my_module.py"))
        print(report.to_text())
    """

    def __init__(self, output_dir: str = "./flux_output", verbose: bool = False) -> None:
        """Initialize the migrator.

        Args:
            output_dir: Directory to write FLUX.MD output files.
            verbose: If True, print progress information during migration.
        """
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self._lang: Optional[str] = None  # explicit language override

    def with_language(self, lang: str) -> FluxMigrator:
        """Set explicit language override. Returns self for chaining."""
        if lang != "auto":
            self._lang = lang.lower()
        else:
            self._lang = None
        return self

    def migrate_file(self, path: Path) -> MigrationReport:
        """Migrate a single file to FLUX.MD.

        Args:
            path: Path to the source file.

        Returns:
            MigrationReport with stats for this file.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        source = path.read_text(encoding="utf-8", errors="replace")
        language = detect_language(path, self._lang)

        report = MigrationReport(
            input_path=path,
            output_dir=self.output_dir,
        )
        report.start_time = time.time()

        if self.verbose:
            print(f"  [migrate] {path} (lang={language})")

        try:
            migrate_fn = _MIGRATE_FNS.get(language)
            if migrate_fn is None:
                raise ValueError(f"Unsupported language: {language}")

            flux_md, func_count, class_count, import_count = migrate_fn(
                source, path.name
            )

            # Ensure output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Write the FLUX.MD file
            output_name = path.stem + ".FLUX.MD"
            output_path = self.output_dir / output_name
            output_path.write_text(flux_md, encoding="utf-8")

            mf = MigratedFile(
                source_path=path,
                output_path=output_path,
                language=language,
                functions_found=func_count,
                classes_found=class_count,
                structs_found=class_count if language == "c" else 0,
                includes_found=import_count,
                lines_processed=len(source.splitlines()),
                success=True,
            )
            report.files.append(mf)

            if self.verbose:
                print(
                    f"    -> {output_path} "
                    f"({func_count} funcs, {class_count} classes, "
                    f"{len(source.splitlines())} lines)"
                )

        except Exception as exc:
            mf = MigratedFile(
                source_path=path,
                output_path=self.output_dir / (path.stem + ".FLUX.MD"),
                language=language,
                lines_processed=len(source.splitlines()),
                success=False,
                error=str(exc),
            )
            report.files.append(mf)
            if self.verbose:
                print(f"    ERROR: {exc}")

        report.end_time = time.time()
        return report

    def migrate_directory(self, path: Path) -> MigrationReport:
        """Migrate all recognized source files in a directory.

        Args:
            path: Path to the directory to scan.

        Returns:
            MigrationReport with aggregated stats.
        """
        path = Path(path)
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        report = MigrationReport(
            input_path=path,
            output_dir=self.output_dir,
        )
        report.start_time = time.time()

        # Collect all recognized source files
        source_files: List[Path] = []
        for ext in ALL_EXTENSIONS:
            source_files.extend(path.rglob(f"*{ext}"))

        # Sort for deterministic output
        source_files.sort()

        # Filter out common non-source directories
        skip_dirs = {
            "__pycache__", "node_modules", ".git", "venv", ".venv",
            "env", "dist", "build", ".eggs", ".tox", ".mypy_cache",
            ".pytest_cache", ".flux_output", "flux_output",
        }
        filtered: List[Path] = []
        for f in source_files:
            skip = False
            for part in f.parts:
                if part in skip_dirs:
                    skip = True
                    break
            if not skip:
                filtered.append(f)
        source_files = filtered

        if self.verbose:
            print(f"  [migrate] Found {len(source_files)} source file(s) in {path}")

        for source_file in source_files:
            language = detect_language(source_file, self._lang)
            try:
                source = source_file.read_text(encoding="utf-8", errors="replace")
                migrate_fn = _MIGRATE_FNS.get(language)
                if migrate_fn is None:
                    continue

                flux_md, func_count, class_count, import_count = migrate_fn(
                    source, source_file.name
                )

                # Preserve directory structure in output
                rel = source_file.relative_to(path)
                out_rel = rel.parent / (rel.stem + ".FLUX.MD")
                out_path = self.output_dir / out_rel
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(flux_md, encoding="utf-8")

                mf = MigratedFile(
                    source_path=source_file,
                    output_path=out_path,
                    language=language,
                    functions_found=func_count,
                    classes_found=class_count,
                    structs_found=class_count if language == "c" else 0,
                    includes_found=import_count,
                    lines_processed=len(source.splitlines()),
                    success=True,
                )
                report.files.append(mf)

                if self.verbose:
                    print(
                        f"    -> {out_rel} "
                        f"({func_count} funcs, {class_count} classes)"
                    )

            except Exception as exc:
                mf = MigratedFile(
                    source_path=source_file,
                    output_path=self.output_dir / (source_file.stem + ".FLUX.MD"),
                    language=language,
                    lines_processed=0,
                    success=False,
                    error=str(exc),
                )
                report.files.append(mf)
                if self.verbose:
                    print(f"    ERROR ({source_file}): {exc}")

        report.end_time = time.time()
        return report
