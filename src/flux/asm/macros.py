"""Macro preprocessor for FLUX assembly.

Supports:
  #define NAME value
  #define NAME(args) body
  #undef NAME
  #ifdef NAME / #ifndef NAME / #endif
  #include "file.asm"
  .set NAME value
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Optional

from .errors import AsmError, AsmErrorKind, SourceLocation


@dataclass
class MacroDefinition:
    """A preprocessor macro definition."""
    name: str
    body: str
    params: list[str] = field(default_factory=list)  # empty = object-like macro
    is_function_like: bool = False


class MacroPreprocessor:
    """Preprocesses FLUX assembly text handling macros, includes, and conditionals."""

    def __init__(
        self,
        include_paths: Optional[list[str]] = None,
        defines: Optional[dict[str, str]] = None,
    ):
        self.include_paths = include_paths or ["."]
        self.macros: dict[str, MacroDefinition] = {}
        self.errors: list[AsmError] = []

        # Seed with initial defines
        if defines:
            for name, value in defines.items():
                self.macros[name] = MacroDefinition(name=name, body=value)

        # Conditional stack: list of (name_or_None, is_active, was_active)
        # is_active: current block should be emitted
        # was_active: any block in this #ifdef/#endif group was active
        self._cond_stack: list[tuple[Optional[str], bool, bool]] = []
        self._included_files: set[str] = set()  # prevent circular includes

    @property
    def is_active(self) -> bool:
        """Whether the current line should be processed."""
        return all(active for _, active, _ in self._cond_stack)

    def preprocess(self, source: str, filename: str = "<input>") -> str:
        """Preprocess assembly source text.

        Args:
            source: Raw assembly source text.
            filename: Name of the source file for error messages.

        Returns:
            Preprocessed source text.

        Raises:
            AsmError: If preprocessing encounters an error.
        """
        output_lines: list[str] = []
        lines = source.split("\n")

        for line_num, raw_line in enumerate(lines, 1):
            stripped = raw_line.strip()

            # Track source line for error context
            loc = SourceLocation(
                file=filename, line=line_num, column=1, source_line=raw_line.rstrip()
            )

            try:
                # Check for preprocessor directives
                if stripped.startswith("#") or stripped.startswith(".set ") or stripped.startswith(".include "):
                    self._handle_directive(stripped, loc, filename)
                    continue

                # Only emit if in an active conditional block
                if self.is_active:
                    # Expand macros in the line
                    expanded = self._expand_macros(stripped, loc)
                    output_lines.append(expanded)
            except AsmError as e:
                e.location = loc
                self.errors.append(e)
                raise

        if self._cond_stack:
            err = make_error(
                "Unterminated #ifdef/#endif",
                kind=AsmErrorKind.MACRO_ERROR,
                file=filename,
                line=lines.__len__(),
            )
            self.errors.append(err)
            raise err

        return "\n".join(output_lines)

    def _handle_directive(self, line: str, loc: SourceLocation, filename: str) -> None:
        """Handle a single preprocessor directive line."""
        if line.startswith("#ifdef"):
            self._handle_ifdef(line, True, loc)
        elif line.startswith("#ifndef"):
            self._handle_ifdef(line, False, loc)
        elif line.startswith("#endif"):
            self._handle_endif(loc)
        elif line.startswith("#else"):
            self._handle_else(loc)
        elif line.startswith("#undef"):
            self._handle_undef(line, loc)
        elif line.startswith("#define"):
            self._handle_define(line, loc)
        elif line.startswith(".set"):
            self._handle_set(line, loc)
        elif line.startswith(".include"):
            self._handle_include(line, loc, filename)
        # else: ignore unknown directives (like # in comments)

    def _handle_define(self, line: str, loc: SourceLocation) -> None:
        """Process #define directive."""
        # #define NAME value
        # #define NAME(args) body
        rest = line[len("#define"):].strip()

        # Function-like macro: NAME(params) body
        match = re.match(r"(\w+)\(([^)]*)\)\s*(.*)", rest)
        if match:
            name = match.group(1)
            params = [p.strip() for p in match.group(2).split(",") if p.strip()]
            body = match.group(3).strip()
            self.macros[name] = MacroDefinition(
                name=name, body=body, params=params, is_function_like=True
            )
            return

        # Object-like macro: NAME value
        parts = rest.split(None, 1)
        if not parts:
            raise AsmError(
                message="Expected macro name after #define",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )
        name = parts[0]
        body = parts[1] if len(parts) > 1 else ""
        self.macros[name] = MacroDefinition(name=name, body=body)

    def _handle_undef(self, line: str, loc: SourceLocation) -> None:
        """Process #undef directive."""
        rest = line[len("#undef"):].strip()
        name = rest.split()[0] if rest.split() else ""
        if not name:
            raise AsmError(
                message="Expected macro name after #undef",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )
        self.macros.pop(name, None)

    def _handle_ifdef(self, line: str, is_ifdef: bool, loc: SourceLocation) -> None:
        """Process #ifdef or #ifndef directive."""
        rest = line.split(None, 1)
        if len(rest) < 2:
            raise AsmError(
                message="Expected macro name after #ifdef",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )
        name = rest[1].strip()

        if not self.is_active:
            # Parent conditional is inactive, push inactive
            self._cond_stack.append((name, False, False))
            return

        defined = name in self.macros
        is_active = defined if is_ifdef else not defined
        self._cond_stack.append((name, is_active, is_active))

    def _handle_else(self, loc: SourceLocation) -> None:
        """Process #else directive."""
        if not self._cond_stack:
            raise AsmError(
                message="#else without #ifdef",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )

        name, was_active, any_active = self._cond_stack[-1]
        # Check if all parent conditionals are active
        parent_active = all(active for _, active, _ in self._cond_stack[:-1])
        new_active = parent_active and not any_active
        self._cond_stack[-1] = (name, new_active, any_active or new_active)

    def _handle_endif(self, loc: SourceLocation) -> None:
        """Process #endif directive."""
        if not self._cond_stack:
            raise AsmError(
                message="#endif without #ifdef",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )
        self._cond_stack.pop()

    def _handle_set(self, line: str, loc: SourceLocation) -> None:
        """Process .set NAME value directive (alias for #define)."""
        rest = line[len(".set"):].strip()
        parts = rest.split(None, 1)
        if len(parts) < 1:
            raise AsmError(
                message="Expected name after .set",
                kind=AsmErrorKind.MACRO_ERROR,
                location=loc,
            )
        name = parts[0]
        body = parts[1] if len(parts) > 1 else ""
        self.macros[name] = MacroDefinition(name=name, body=body)

    def _handle_include(self, line: str, loc: SourceLocation, current_file: str) -> str:
        """Process .include "file" directive."""
        match = re.search(r'"([^"]+)"', line)
        if not match:
            raise AsmError(
                message='Expected .include "filename"',
                kind=AsmErrorKind.INCLUDE_ERROR,
                location=loc,
            )

        include_name = match.group(1)

        # Resolve path relative to current file or include paths
        if os.path.isabs(include_name):
            resolved = include_name
        else:
            current_dir = os.path.dirname(os.path.abspath(current_file)) if current_file != "<input>" else os.getcwd()
            resolved = os.path.join(current_dir, include_name)

            # Try include paths
            if not os.path.exists(resolved):
                for path in self.include_paths:
                    candidate = os.path.join(path, include_name)
                    if os.path.exists(candidate):
                        resolved = os.path.abspath(candidate)
                        break

        # Check for circular includes
        abs_path = os.path.abspath(resolved)
        if abs_path in self._included_files:
            raise AsmError(
                message=f"Circular include: {include_name}",
                kind=AsmErrorKind.INCLUDE_ERROR,
                location=loc,
            )

        self._included_files.add(abs_path)

        # Read and recursively preprocess the included file
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                included_source = f.read()
        except IOError as e:
            raise AsmError(
                message=f"Cannot include file '{include_name}': {e}",
                kind=AsmErrorKind.INCLUDE_ERROR,
                location=loc,
            ) from e

        return self.preprocess(included_source, filename=resolved)

    def _expand_macros(self, line: str, loc: SourceLocation) -> str:
        """Expand all macros in a line."""
        # First expand function-like macros (with arguments)
        for _ in range(10):  # max iterations to prevent infinite expansion
            new_line = self._expand_function_macros(line, loc)
            if new_line == line:
                break
            line = new_line

        # Then expand object-like macros
        for name, macro in self.macros.items():
            if not macro.is_function_like and name in line:
                # Use word boundary matching to avoid partial replacements
                line = re.sub(r'\b' + re.escape(name) + r'\b', macro.body, line)

        return line

    def _expand_function_macros(self, line: str, loc: SourceLocation) -> str:
        """Expand function-like macros with arguments."""
        for name, macro in self.macros.items():
            if not macro.is_function_like:
                continue
            pattern = re.escape(name) + r'\s*\(([^)]*)\)'
            match = re.search(pattern, line)
            if match:
                args = [a.strip() for a in match.group(1).split(",")]
                if len(args) != len(macro.params):
                    raise AsmError(
                        message=f"Macro '{name}' expects {len(macro.params)} args, got {len(args)}",
                        kind=AsmErrorKind.MACRO_ERROR,
                        location=loc,
                        hints=[f"Definition: {name}({', '.join(macro.params)})"],
                    )
                body = macro.body
                for param, arg in zip(macro.params, args):
                    body = body.replace(param, arg)
                line = line[:match.start()] + body + line[match.end():]
                return line
        return line


def make_error(
    message: str,
    kind: AsmErrorKind = AsmErrorKind.SYNTAX,
    file: str = "<unknown>",
    line: int = 0,
    column: int = 0,
    source_line: str = "",
    hints: Optional[list[str]] = None,
) -> AsmError:
    """Import-compatible convenience factory."""
    from .errors import make_error as _make_error
    return _make_error(message, kind, file, line, column, source_line, hints)
