"""Python → FLUX Reverse Engineer.

Shows how Python code constructs map to FLUX FIR equivalents.
Uses the ast module to introspectively analyze Python source.
"""

from __future__ import annotations

import ast
from typing import Optional

from flux.reverse.code_map import (
    CodeMapping,
    CodeMap,
    ConstructType,
    Difficulty,
    MigrationStep,
    MigrationPlan,
)


class PythonReverseEngineer:
    """Analyzes Python source code and maps each construct to its FLUX FIR equivalent.

    Supported mappings:
        - def func()        → FIR function
        - for/while         → FIR basic blocks + jumps
        - class             → FIR module
        - import            → FIR module reference or A2A DELEGATE
        - async def         → A2A TELL/ASK pattern
        - print()           → IO_WRITE
        - try/except        → A2A BARRIER
        - list comprehensions → SIMD vector ops
        - decorators        → tile composition
    """

    def __init__(self):
        self._line_offset: int = 0

    # ── Public API ─────────────────────────────────────────────────────

    def analyze(self, source: str) -> CodeMap:
        """Analyze Python source code and produce a CodeMap."""
        self._line_offset = 0
        mappings: list[CodeMapping] = []

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            mappings.append(CodeMapping(
                original=source,
                flux_ir="/* PARSE ERROR */",
                construct_type=ConstructType.UNKNOWN,
                confidence=0.0,
                notes=f"Failed to parse: {e}",
            ))
            return CodeMap(
                source_lang="python",
                source_code=source,
                mappings=mappings,
                summary="Parse error — cannot map constructs.",
            )

        for node in ast.iter_child_nodes(tree):
            self._visit_node(node, mappings, source)

        summary = self._generate_summary(mappings)
        return CodeMap(
            source_lang="python",
            source_code=source,
            mappings=mappings,
            summary=summary,
        )

    def migration_plan(self, source: str) -> MigrationPlan:
        """Generate a step-by-step migration plan from Python to FLUX."""
        code_map = self.analyze(source)
        steps: list[MigrationStep] = []
        step_num = 1

        # Group mappings by construct type for ordered migration
        type_order = [
            ConstructType.IMPORT,
            ConstructType.CLASS,
            ConstructType.VARIABLE,
            ConstructType.FUNCTION,
            ConstructType.CALL,
            ConstructType.LOOP,
            ConstructType.IO_WRITE,
            ConstructType.ERROR_HANDLING,
            ConstructType.ASYNC,
            ConstructType.COMPREHENSION,
            ConstructType.DECORATOR,
        ]

        seen = set()
        for ctype in type_order:
            for mapping in code_map.mappings:
                if mapping.construct_type == ctype and mapping.original not in seen:
                    seen.add(mapping.original)
                    difficulty, effort = self._estimate_difficulty(ctype)
                    steps.append(MigrationStep(
                        step_number=step_num,
                        description=self._step_description(ctype, mapping.original),
                        original_code=mapping.original.strip(),
                        flux_code=mapping.flux_ir.strip(),
                        difficulty=difficulty,
                        estimated_effort=effort,
                    ))
                    step_num += 1

        # Handle any remaining unknown types
        for mapping in code_map.mappings:
            if mapping.original not in seen:
                seen.add(mapping.original)
                steps.append(MigrationStep(
                    step_number=step_num,
                    description=f"Map unknown construct",
                    original_code=mapping.original.strip(),
                    flux_code=mapping.flux_ir.strip(),
                    difficulty=Difficulty.MEDIUM,
                    estimated_effort="15 minutes",
                ))
                step_num += 1

        overview = (
            f"Migration plan for {len(steps)} Python constructs to FLUX. "
            f"Estimated total effort: {self._estimate_total(steps)}."
        )
        return MigrationPlan(
            source_lang="python",
            total_steps=len(steps),
            steps=steps,
            overview=overview,
        )

    # ── AST Visitor ────────────────────────────────────────────────────

    def _visit_node(
        self,
        node: ast.AST,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        """Dispatch to the appropriate visitor for an AST node."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._visit_function(node, mappings, source)
        elif isinstance(node, ast.ClassDef):
            self._visit_class(node, mappings, source)
        elif isinstance(node, ast.Import):
            self._visit_import(node, mappings, source)
        elif isinstance(node, ast.ImportFrom):
            self._visit_import_from(node, mappings, source)
        elif isinstance(node, ast.Assign):
            self._visit_assignment(node, mappings, source)
        elif isinstance(node, (ast.For, ast.While)):
            self._visit_loop(node, mappings, source)
        elif isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call):
                self._visit_call_expr(node.value, mappings, source)
        elif isinstance(node, ast.Try):
            self._visit_try(node, mappings, source)
        elif isinstance(node, ast.If):
            self._visit_if(node, mappings, source)

        # Recurse into children for nested constructs
        for child in ast.iter_child_nodes(node):
            if child not in (node,) and not isinstance(child, (
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef
            )):
                self._visit_node(child, mappings, source)

    # ── Function ───────────────────────────────────────────────────────

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        is_async = isinstance(node, ast.AsyncFunctionDef)
        params = ", ".join(
            f"{a.arg}: {self._annotation_str(a.annotation)}"
            for a in node.args.args
        )
        ret_ann = self._annotation_str(node.returns) if node.returns else "None"

        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else "def ..."

        if is_async:
            flux_ir = (
                f"# async {node.name} → A2A TELL/ASK pattern\n"
                f"func {node.name}({params}) -> {ret_ann} {{\n"
                f"  entry:\n"
                f"    # Receives TELL messages from other agents\n"
                f"    # Processes async work via DELEGATE\n"
                f"    RET\n"
                f"}}"
            )
            construct = ConstructType.ASYNC
            notes = (
                f"Python async def maps to FLUX A2A TELL/ASK pattern. "
                f"The function becomes an agent that can receive TELL messages "
                f"and respond with ASK results."
            )
        else:
            flux_ir = (
                f"func {node.name}({params}) -> {ret_ann} {{\n"
                f"  entry:\n"
                f"    # Parameters are SSA values on entry\n"
                f"    RET\n"
                f"}}"
            )
            construct = ConstructType.FUNCTION
            notes = (
                f"Python def maps directly to a FIR function. "
                f"Parameters become SSA values, body becomes basic blocks."
            )

        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=construct,
            confidence=0.95,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

        # Visit nested constructs inside the function body
        for child_node in ast.iter_child_nodes(node):
            if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # Skip nested function defs (top-level only)
            if isinstance(child_node, ast.Expr) and isinstance(child_node.value, ast.Call):
                self._visit_call_expr(child_node.value, mappings, source)
            elif isinstance(child_node, ast.For):
                self._visit_loop(child_node, mappings, source)
            elif isinstance(child_node, ast.While):
                self._visit_loop(child_node, mappings, source)
            elif isinstance(child_node, ast.Try):
                self._visit_try(child_node, mappings, source)
            elif isinstance(child_node, ast.Assign):
                self._visit_assignment(child_node, mappings, source)
            elif isinstance(child_node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self._visit_comprehension(child_node, mappings, source)

        # Check for decorators
        for decorator in node.decorator_list:
            self._visit_decorator(decorator, node.name, mappings, source)

    # ── Class ──────────────────────────────────────────────────────────

    def _visit_class(
        self,
        node: ast.ClassDef,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        bases = ", ".join(
            b.id if isinstance(b, ast.Name) else "..."
            for b in node.bases
        )
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else f"class {node.name}"

        flux_ir = (
            f"# class {node.name}({bases}) → FIR module\n"
            f"module {node.name} {{\n"
            f"  # Instance fields → struct type\n"
            f"  # Methods → FIR functions\n"
            f"  # __init__ → constructor function\n"
            f"}}"
        )
        notes = (
            f"Python class maps to a FIR module. Instance fields become "
            f"struct members, methods become FIR functions. "
            f"__init__ becomes a constructor. Class inheritance maps to "
            f"module composition via A2A DELEGATE."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.CLASS,
            confidence=0.85,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Import ─────────────────────────────────────────────────────────

    def _visit_import(
        self,
        node: ast.Import,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        names = ", ".join(a.name for a in node.names)
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else f"import {names}"

        flux_ir_lines = [f"# import {names} → FIR module references"]
        for alias in node.names:
            flux_ir_lines.append(
                f"DELEGATE {alias.name}  # module reference via A2A"
            )
        flux_ir = "\n".join(flux_ir_lines)

        notes = (
            f"Python import maps to FIR module reference. "
            f"For cross-module communication, this becomes an A2A DELEGATE."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.IMPORT,
            confidence=0.90,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    def _visit_import_from(
        self,
        node: ast.ImportFrom,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        module = node.module or "(relative)"
        names = ", ".join(a.name for a in node.names)
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else f"from {module} import {names}"

        flux_ir = (
            f"# from {module} import {names}\n"
            f"DELEGATE {module}\n"
            f"# Use: CALL {module}::<function>"
        )
        notes = (
            f"Python 'from X import Y' maps to FIR module reference + function call. "
            f"DELEGATE establishes the module connection, CALL invokes the function."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.IMPORT,
            confidence=0.90,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Variable / Assignment ──────────────────────────────────────────

    def _visit_assignment(
        self,
        node: ast.Assign,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        # Check if the value is a comprehension
        if isinstance(node.value, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            self._visit_comprehension(node.value, mappings, source)
            return

        targets_str = ", ".join(
            t.id if isinstance(t, ast.Name) else "..."
            for t in node.targets
        )
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else f"{targets_str} = ..."

        flux_ir = (
            f"# {original.strip()} → FIR SSA value\n"
            f"ALLOCA {targets_str}  # stack slot for variable\n"
            f"STORE <value>, {targets_str}"
        )
        notes = (
            f"Python variable assignment maps to FIR ALLOCA + STORE. "
            f"In SSA form, each assignment creates a new immutable value. "
            f"Variables are stored on the stack via ALLOCA."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.VARIABLE,
            confidence=0.90,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Loop ───────────────────────────────────────────────────────────

    def _visit_loop(
        self,
        node: ast.For | ast.While,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        is_for = isinstance(node, ast.For)
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else ("for ..." if is_for else "while ...")

        flux_ir = (
            f"# {'for' if is_for else 'while'} loop → FIR basic blocks + jumps\n"
            f"  entry:\n"
            f"    JMP header\n"
            f"  header:\n"
            f"    # condition check\n"
            f"    BR <cond>, body, exit\n"
            f"  body:\n"
            f"    # loop body\n"
            f"    JMP header\n"
            f"  exit:"
        )
        notes = (
            f"Python {'for' if is_for else 'while'} loop maps to FIR basic blocks "
            f"with header/body/exit structure. The condition creates a BRANCH, "
            f"the body ends with a JMP back to the header."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.LOOP,
            confidence=0.95,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Call Expression ────────────────────────────────────────────────

    def _visit_call_expr(
        self,
        node: ast.Call,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        func_name = node.func.id if isinstance(node.func, ast.Name) else "..."
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else f"{func_name}(...)"
        original = original.strip()

        # Handle print() specially
        if func_name == "print":
            flux_ir = (
                f"# print({', '.join('...' for _ in node.args)}) → IO_WRITE\n"
                f"IO_WRITE <args...>  # FLUX I/O operation"
            )
            notes = (
                f"Python print() maps to FLUX IO_WRITE. "
                f"Output goes through the FLUX I/O subsystem."
            )
            construct = ConstructType.IO_WRITE
        else:
            args = ", ".join("..." for _ in node.args)
            flux_ir = (
                f"# {func_name}({args}) → FIR call\n"
                f"CALL {func_name}, [{args}]"
            )
            notes = (
                f"Python function call maps to FIR CALL instruction. "
                f"For cross-agent calls, this could be TELL or ASK."
            )
            construct = ConstructType.CALL

        # Avoid duplicating if we already have this exact line
        if not any(
            m.original.strip() == original and m.construct_type == construct
            for m in mappings
        ):
            mappings.append(CodeMapping(
                original=original,
                flux_ir=flux_ir,
                construct_type=construct,
                confidence=0.90,
                notes=notes,
                line_number=line + 1 if line is not None else None,
            ))

    # ── Try/Except ─────────────────────────────────────────────────────

    def _visit_try(
        self,
        node: ast.Try,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else "try:"

        handlers = ", ".join(
            h.type.id if isinstance(h.type, ast.Name) else "..."
            for h in node.handlers
        )

        flux_ir = (
            f"# try/except → A2A BARRIER pattern\n"
            f"  entry:\n"
            f"    BARRIER try_block, error_handler\n"
            f"  try_block:\n"
            f"    # try body\n"
            f"    JMP after\n"
            f"  error_handler:\n"
            f"    # except {handlers}\n"
            f"  after:"
        )
        notes = (
            f"Python try/except maps to FLUX A2A BARRIER pattern. "
            f"BARRIER creates a synchronization point that catches errors. "
            f"Handlers become error recovery blocks."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.ERROR_HANDLING,
            confidence=0.80,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── If ─────────────────────────────────────────────────────────────

    def _visit_if(
        self,
        node: ast.If,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else "if ..."

        flux_ir = (
            f"# if/else → FIR BRANCH\n"
            f"  entry:\n"
            f"    BR <cond>, then_block, else_block\n"
            f"  then_block:\n"
            f"    # then body\n"
            f"    JMP merge\n"
            f"  else_block:\n"
            f"    # else body\n"
            f"    JMP merge\n"
            f"  merge:"
        )
        notes = (
            f"Python if/else maps to FIR BRANCH instruction. "
            f"Each branch becomes a basic block, merging at the end."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.FUNCTION,  # Control flow within function
            confidence=0.95,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Comprehension ──────────────────────────────────────────────────

    def _visit_comprehension(
        self,
        node: ast.expr,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        comp_type = type(node).__name__
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = self._get_source_line(source, line) if line is not None else "[...]"

        if isinstance(node, ast.ListComp):
            flux_ir = (
                f"# list comprehension → SIMD vector ops\n"
                f"  # [expr for x in iter] maps to:\n"
                f"  VLOAD <iter_data>  # load into vector registers\n"
                f"  VMAP <expr>        # apply expression to each lane\n"
                f"  VSTORE <result>    # store results"
            )
        elif isinstance(node, ast.DictComp):
            flux_ir = (
                f"# dict comprehension → map tile\n"
                f"  # {{k:v for ...}} maps to:\n"
                f"  TILE map(input_keys, input_values) -> result_map"
            )
        else:
            flux_ir = (
                f"# {comp_type} → vector/map operation\n"
                f"  VMAP <expr>  # apply to each element"
            )

        notes = (
            f"Python {comp_type} maps to SIMD vector operations in FLUX. "
            f"List comprehensions become parallel VMAP operations, "
            f"leveraging FLUX's SIMD lanes for data-parallel processing."
        )
        mappings.append(CodeMapping(
            original=original,
            flux_ir=flux_ir,
            construct_type=ConstructType.COMPREHENSION,
            confidence=0.75,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Decorator ──────────────────────────────────────────────────────

    def _visit_decorator(
        self,
        node: ast.expr,
        func_name: str,
        mappings: list[CodeMapping],
        source: str,
    ) -> None:
        dec_name = node.id if isinstance(node, ast.Name) else "..."
        line = node.lineno - 1 if hasattr(node, "lineno") else None
        original = f"@{dec_name}"
        original_line = self._get_source_line(source, line) if line is not None else original

        flux_ir = (
            f"# @{dec_name} → tile composition\n"
            f"  # Decorator wraps {func_name} as a composable tile\n"
            f"  TILE {dec_name}(func={func_name})\n"
            f"  # Can be chained: TILE A(TILE B(func))"
        )
        notes = (
            f"Python decorator @{dec_name} maps to FLUX tile composition. "
            f"Decorators are composable transformation patterns — "
            f"each decorator is a tile that wraps the function."
        )
        mappings.append(CodeMapping(
            original=original_line,
            flux_ir=flux_ir,
            construct_type=ConstructType.DECORATOR,
            confidence=0.70,
            notes=notes,
            line_number=line + 1 if line is not None else None,
        ))

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _annotation_str(annotation: Optional[ast.expr]) -> str:
        if annotation is None:
            return "i32"
        if isinstance(annotation, ast.Name):
            type_map = {
                "int": "i32",
                "float": "f32",
                "bool": "bool",
                "str": "str",
                "None": "void",
            }
            return type_map.get(annotation.id, annotation.id)
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value
        return "i32"

    @staticmethod
    def _get_source_line(source: str, line_index: int) -> str:
        lines = source.split("\n")
        if 0 <= line_index < len(lines):
            return lines[line_index]
        return ""

    @staticmethod
    def _generate_summary(mappings: list[CodeMapping]) -> str:
        if not mappings:
            return "No Python constructs found to map."
        types = {}
        total_conf = 0.0
        for m in mappings:
            types[m.construct_type] = types.get(m.construct_type, 0) + 1
            total_conf += m.confidence
        avg_conf = total_conf / len(mappings)
        parts = [f"Found {len(mappings)} Python constructs:"]
        for ctype, count in sorted(types.items()):
            parts.append(f"  - {ctype}: {count}")
        parts.append(f"Average mapping confidence: {avg_conf:.1%}")
        return "\n".join(parts)

    @staticmethod
    def _estimate_difficulty(construct_type: str) -> tuple[str, str]:
        difficulty_map = {
            ConstructType.VARIABLE: (Difficulty.EASY, "5 minutes"),
            ConstructType.FUNCTION: (Difficulty.EASY, "10 minutes"),
            ConstructType.IO_WRITE: (Difficulty.EASY, "5 minutes"),
            ConstructType.IMPORT: (Difficulty.EASY, "5 minutes"),
            ConstructType.CALL: (Difficulty.EASY, "5 minutes"),
            ConstructType.LOOP: (Difficulty.MEDIUM, "15 minutes"),
            ConstructType.CLASS: (Difficulty.MEDIUM, "30 minutes"),
            ConstructType.ERROR_HANDLING: (Difficulty.MEDIUM, "20 minutes"),
            ConstructType.ASYNC: (Difficulty.HARD, "45 minutes"),
            ConstructType.COMPREHENSION: (Difficulty.MEDIUM, "20 minutes"),
            ConstructType.DECORATOR: (Difficulty.MEDIUM, "20 minutes"),
        }
        return difficulty_map.get(construct_type, (Difficulty.MEDIUM, "15 minutes"))

    @staticmethod
    def _step_description(construct_type: str, original: str) -> str:
        desc_map = {
            ConstructType.VARIABLE: f"Convert variable assignment to FIR SSA",
            ConstructType.FUNCTION: f"Convert function to FIR function",
            ConstructType.IO_WRITE: f"Replace print() with IO_WRITE",
            ConstructType.IMPORT: f"Convert import to FIR module reference",
            ConstructType.CALL: f"Convert function call to FIR CALL",
            ConstructType.LOOP: f"Convert loop to FIR basic blocks + jumps",
            ConstructType.CLASS: f"Convert class to FIR module",
            ConstructType.ERROR_HANDLING: f"Convert try/except to A2A BARRIER",
            ConstructType.ASYNC: f"Convert async def to A2A TELL/ASK pattern",
            ConstructType.COMPREHENSION: f"Convert comprehension to SIMD ops",
            ConstructType.DECORATOR: f"Convert decorator to tile composition",
        }
        return desc_map.get(construct_type, f"Map construct to FLUX")

    @staticmethod
    def _estimate_total(steps: list[MigrationStep]) -> str:
        minutes = sum(
            {"5 minutes": 5, "10 minutes": 10, "15 minutes": 15,
             "20 minutes": 20, "30 minutes": 30, "45 minutes": 45,
             "60 minutes": 60}.get(s.estimated_effort, 15)
            for s in steps
        )
        if minutes < 60:
            return f"~{minutes} minutes"
        return f"~{minutes / 60:.1f} hours"
