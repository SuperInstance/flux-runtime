"""C → FLUX Reverse Engineer.

Shows how C code constructs map to FLUX FIR equivalents.
Uses regex-based parsing for a simple C subset (no preprocessor macros, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from flux.reverse.code_map import (
    CodeMapping,
    CodeMap,
    ConstructType,
    Difficulty,
    MigrationStep,
    MigrationPlan,
)


# ── Regex patterns for C construct detection ────────────────────────────────

_RE_STRUCT = re.compile(
    r"^\s*typedef\s+struct\s*(?:\w*)\s*\{(.*?)\}\s*(\w+)\s*;?",
    re.DOTALL,
)

_RE_STRUCT_SIMPLE = re.compile(
    r"^\s*struct\s+(\w+)\s*\{(.*?)\}\s*;?",
    re.DOTALL,
)

_RE_FUNCTION = re.compile(
    r"^\s*([\w][\w\s\*]*?)\s+(\w+)\s*\(([^)]*)\)\s*\{",
    re.DOTALL,
)

_RE_MALLOC = re.compile(r"\bmalloc\s*\(")
_RE_FREE = re.compile(r"\bfree\s*\(")
_RE_CALLOC = re.compile(r"\bcalloc\s*\(")
_REALLOC = re.compile(r"\brealloc\s*\(")

_RE_PRINTF = re.compile(r"\bprintf\s*\(")
_RE_SCANF = re.compile(r"\bscanf\s*\(")

_RE_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)

_RE_POINTER_DECL = re.compile(r"([\w]+)\s*\*\s*(\w+)")
_RE_POINTER_TYPE = re.compile(r"(\w+)\s*\*")

_RE_FOR_LOOP = re.compile(r"^\s*for\s*\(", re.MULTILINE)
_RE_WHILE_LOOP = re.compile(r"^\s*while\s*\(", re.MULTILINE)

_RE_MAIN = re.compile(r"^\s*int\s+main\s*\(", re.MULTILINE)


@dataclass
class _CStructField:
    name: str
    type_name: str
    is_pointer: bool = False


@dataclass
class _DetectedStruct:
    name: str
    fields: list[_CStructField]
    line_number: int


@dataclass
class _DetectedFunction:
    return_type: str
    name: str
    params: str
    line_number: int
    is_main: bool = False


class CReverseEngineer:
    """Analyzes C source code and maps each construct to its FLUX FIR equivalent.

    Supported mappings:
        - int main()       → FIR function
        - struct           → FIR type (StructType)
        - malloc/free      → REGION_CREATE/REGION_DESTROY
        - printf           → IO_WRITE
        - Pointers         → memory regions
        - #include         → module imports
    """

    def analyze(self, source: str) -> CodeMap:
        """Analyze C source code and produce a CodeMap."""
        mappings: list[CodeMapping] = []

        # Detect all constructs
        self._detect_structs(source, mappings)
        self._detect_functions(source, mappings)
        self._detect_malloc_free(source, mappings)
        self._detect_printf(source, mappings)
        self._detect_includes(source, mappings)
        self._detect_pointers(source, mappings)
        self._detect_loops(source, mappings)

        summary = self._generate_summary(mappings)
        return CodeMap(
            source_lang="c",
            source_code=source,
            mappings=mappings,
            summary=summary,
        )

    def migration_plan(self, source: str) -> MigrationPlan:
        """Generate a step-by-step migration plan from C to FLUX."""
        code_map = self.analyze(source)
        steps: list[MigrationStep] = []
        step_num = 1

        type_order = [
            ConstructType.PREPROCESSOR,
            ConstructType.STRUCT,
            ConstructType.POINTER,
            ConstructType.MEMORY,
            ConstructType.FUNCTION,
            ConstructType.CALL,
            ConstructType.IO_WRITE,
            ConstructType.LOOP,
        ]

        seen_originals = set()
        for ctype in type_order:
            for mapping in code_map.mappings:
                if mapping.construct_type == ctype and mapping.original not in seen_originals:
                    seen_originals.add(mapping.original)
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

        overview = (
            f"Migration plan for {len(steps)} C constructs to FLUX. "
            f"Estimated total effort: {self._estimate_total(steps)}."
        )
        return MigrationPlan(
            source_lang="c",
            total_steps=len(steps),
            steps=steps,
            overview=overview,
        )

    # ── Detection methods ──────────────────────────────────────────────

    def _detect_structs(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect struct definitions and map to FIR StructType."""
        lines = source.split("\n")

        for m in _RE_STRUCT.finditer(source):
            fields_str = m.group(1).strip()
            struct_name = m.group(2)
            line_num = source[:m.start()].count("\n") + 1
            self._add_struct_mapping(
                struct_name, fields_str, line_num, lines, mappings
            )

        for m in _RE_STRUCT_SIMPLE.finditer(source):
            fields_str = m.group(2).strip()
            struct_name = m.group(1)
            line_num = source[:m.start()].count("\n") + 1
            self._add_struct_mapping(
                struct_name, fields_str, line_num, lines, mappings
            )

    def _add_struct_mapping(
        self,
        name: str,
        fields_str: str,
        line_num: int,
        lines: list[str],
        mappings: list[CodeMapping],
    ) -> None:
        fields = self._parse_struct_fields(fields_str)
        fir_fields = ", ".join(f"{f.name}: {self._c_type_to_fir(f.type_name)}" for f in fields)

        original_line = lines[line_num - 1] if line_num <= len(lines) else f"struct {name}"

        flux_ir = (
            f"# struct {name} → FIR StructType\n"
            f"struct {name} {{\n"
        )
        for f in fields:
            ptr_str = " (pointer)" if f.is_pointer else ""
            flux_ir += f"  {f.name}: {self._c_type_to_fir(f.type_name)}{ptr_str}\n"
        flux_ir += "}"

        notes = (
            f"C struct '{name}' maps to FIR StructType with {len(fields)} fields. "
            f"Each field becomes a typed member. Pointer fields use FIR RefType."
        )
        mappings.append(CodeMapping(
            original=original_line,
            flux_ir=flux_ir,
            construct_type=ConstructType.STRUCT,
            confidence=0.90,
            notes=notes,
            line_number=line_num,
        ))

    def _detect_functions(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect function definitions and map to FIR functions."""
        lines = source.split("\n")

        for m in _RE_FUNCTION.finditer(source):
            ret_type = m.group(1).strip()
            func_name = m.group(2).strip()
            params = m.group(3).strip()
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else f"{ret_type} {func_name}()"

            is_main = func_name == "main"
            fir_ret = self._c_type_to_fir(ret_type)

            # Parse params
            fir_params = []
            if params:
                for param in params.split(","):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            ptype = self._c_type_to_fir(parts[0])
                            pname = parts[-1].strip("*")
                            fir_params.append(f"{pname}: {ptype}")

            params_str = ", ".join(fir_params) if fir_params else ""

            flux_ir = (
                f"# {ret_type} {func_name}({params}) → FIR function\n"
                f"func {func_name}({params_str}) -> {fir_ret} {{\n"
                f"  entry:\n"
                f"    # Body maps to FIR basic blocks\n"
                f"    RET\n"
                f"}}"
            )
            notes = (
                f"C function '{func_name}' maps to FIR function. "
                f"Return type '{ret_type}' → '{fir_ret}'. "
                f"{'This is main() — entry point maps to FLUX agent entry.' if is_main else 'Parameters become SSA values.'}"
            )
            mappings.append(CodeMapping(
                original=original_line,
                flux_ir=flux_ir,
                construct_type=ConstructType.FUNCTION,
                confidence=0.95,
                notes=notes,
                line_number=line_num,
            ))

    def _detect_malloc_free(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect malloc/free/calloc/realloc and map to REGION operations."""
        lines = source.split("\n")

        # Detect malloc/calloc/realloc
        for m in _RE_MALLOC.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else "malloc(...)"
            flux_ir = (
                f"# malloc() → REGION_CREATE\n"
                f"  REGION_CREATE <size>  →  returns RefType\n"
                f"  # FLUX uses linear region memory model\n"
                f"  # No manual free needed — region is destroyed on scope exit"
            )
            notes = (
                f"C malloc maps to FLUX REGION_CREATE. "
                f"FLUX uses linear memory regions instead of manual malloc/free. "
                f"Memory is automatically freed when the region goes out of scope."
            )
            mappings.append(CodeMapping(
                original=original_line,
                flux_ir=flux_ir,
                construct_type=ConstructType.MEMORY,
                confidence=0.85,
                notes=notes,
                line_number=line_num,
            ))

        for m in _RE_FREE.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else "free(...)"
            flux_ir = (
                f"# free() → REGION_DESTROY\n"
                f"  REGION_DESTROY <ptr>  # or implicit on scope exit\n"
                f"  # In FLUX, regions are automatically managed\n"
                f"  # Explicit REGION_DESTROY only needed for early cleanup"
            )
            notes = (
                f"C free maps to FLUX REGION_DESTROY. "
                f"In most cases, FLUX handles this automatically when "
                f"the memory region goes out of scope."
            )
            mappings.append(CodeMapping(
                original=original_line,
                flux_ir=flux_ir,
                construct_type=ConstructType.MEMORY,
                confidence=0.85,
                notes=notes,
                line_number=line_num,
            ))

    def _detect_printf(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect printf/scanf and map to IO_WRITE."""
        lines = source.split("\n")

        for m in _RE_PRINTF.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else "printf(...)"
            flux_ir = (
                f"# printf() → IO_WRITE\n"
                f"IO_WRITE <format_string>, <args...>"
            )
            notes = (
                f"C printf maps to FLUX IO_WRITE. "
                f"Format strings are handled by the FLUX I/O subsystem."
            )
            mappings.append(CodeMapping(
                original=original_line,
                flux_ir=flux_ir,
                construct_type=ConstructType.IO_WRITE,
                confidence=0.95,
                notes=notes,
                line_number=line_num,
            ))

    def _detect_includes(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect #include directives and map to module imports."""
        for m in _RE_INCLUDE.finditer(source):
            header = m.group(1)
            line_num = source[:m.start()].count("\n") + 1

            is_stdlib = header.startswith("<") or header in (
                "stdio.h", "stdlib.h", "string.h", "math.h", "stdbool.h",
            )

            if is_stdlib:
                flux_ir = (
                    f"# #include <{header}> → FLUX stdlib module\n"
                    f"  # {header} is available via FLUX standard library\n"
                    f"  # stdlib.{header.replace('.h', '')}"
                )
                notes = (
                    f"C #include <{header}> maps to FLUX standard library module. "
                    f"FLUX provides built-in equivalents for common C stdlib functions."
                )
            else:
                flux_ir = (
                    f'# #include "{header}" → FIR module reference\n'
                    f"DELEGATE {header.replace('.h', '').replace('/', '.')}"
                )
                notes = (
                    f'C #include "{header}" maps to FIR module reference via A2A DELEGATE. '
                    f"Cross-module communication uses the A2A protocol."
                )

            mappings.append(CodeMapping(
                original=m.group(0),
                flux_ir=flux_ir,
                construct_type=ConstructType.PREPROCESSOR,
                confidence=0.85,
                notes=notes,
                line_number=line_num,
            ))

    def _detect_pointers(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect pointer declarations and map to memory regions."""
        lines = source.split("\n")

        for i, line in enumerate(lines):
            # Skip lines that are just #include or in strings
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            for m in _RE_POINTER_DECL.finditer(line):
                base_type = m.group(1)
                var_name = m.group(2)
                line_num = i + 1
                flux_ir = (
                    f"# {base_type}* {var_name} → FIR RefType + memory region\n"
                    f"  ALLOCA RefType<{self._c_type_to_fir(base_type)}>  # pointer\n"
                    f"  # Pointer dereference → LOAD/STORE from region"
                )
                notes = (
                    f"C pointer '{base_type}* {var_name}' maps to FIR RefType "
                    f"backed by a memory region. Dereferencing uses LOAD/STORE, "
                    f"pointer arithmetic uses GetElem with offsets."
                )
                mappings.append(CodeMapping(
                    original=stripped,
                    flux_ir=flux_ir,
                    construct_type=ConstructType.POINTER,
                    confidence=0.85,
                    notes=notes,
                    line_number=line_num,
                ))

    def _detect_loops(self, source: str, mappings: list[CodeMapping]) -> None:
        """Detect for/while loops and map to FIR basic blocks."""
        lines = source.split("\n")

        for m in _RE_FOR_LOOP.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else "for (...)"
            flux_ir = (
                f"# for loop → FIR basic blocks + jumps\n"
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
                f"C for loop maps to FIR basic blocks with header/body/exit structure. "
                f"Similar to the Python mapping but with explicit init/update blocks."
            )
            mappings.append(CodeMapping(
                original=original_line,
                flux_ir=flux_ir,
                construct_type=ConstructType.LOOP,
                confidence=0.95,
                notes=notes,
                line_number=line_num,
            ))

        for m in _RE_WHILE_LOOP.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            original_line = lines[line_num - 1] if line_num <= len(lines) else "while (...)"
            if original_line.strip().startswith("while"):
                flux_ir = (
                    f"# while loop → FIR basic blocks + jumps\n"
                    f"  header:\n"
                    f"    BR <cond>, body, exit\n"
                    f"  body:\n"
                    f"    JMP header\n"
                    f"  exit:"
                )
                notes = (
                    f"C while loop maps to FIR basic blocks. "
                    f"Header checks condition, body executes, jumps back."
                )
                mappings.append(CodeMapping(
                    original=original_line,
                    flux_ir=flux_ir,
                    construct_type=ConstructType.LOOP,
                    confidence=0.95,
                    notes=notes,
                    line_number=line_num,
                ))

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_struct_fields(fields_str: str) -> list[_CStructField]:
        """Parse a C struct field list into typed fields."""
        fields: list[_CStructField] = []
        if not fields_str or fields_str.strip() == "":
            return fields

        for line in fields_str.split(";"):
            line = line.strip()
            if not line:
                continue

            # Handle pointer types: int *ptr
            ptr_match = _RE_POINTER_DECL.match(line)
            if ptr_match:
                fields.append(_CStructField(
                    name=ptr_match.group(2),
                    type_name=ptr_match.group(1),
                    is_pointer=True,
                ))
                continue

            # Regular type: int x
            parts = line.split()
            if len(parts) >= 2:
                type_name = parts[0]
                var_name = parts[-1].strip("*")
                is_ptr = "*" in line
                fields.append(_CStructField(
                    name=var_name,
                    type_name=type_name,
                    is_pointer=is_ptr,
                ))

        return fields

    @staticmethod
    def _c_type_to_fir(c_type: str) -> str:
        """Map a C type name to FIR type."""
        type_map = {
            "int": "i32",
            "long": "i64",
            "short": "i16",
            "char": "i8",
            "float": "f32",
            "double": "f64",
            "void": "void",
            "bool": "bool",
            "_Bool": "bool",
            "unsigned": "u32",
            "unsigned int": "u32",
            "size_t": "i64",
        }
        # Normalize
        c_type = c_type.strip().rstrip("*")
        return type_map.get(c_type, "i32")

    @staticmethod
    def _generate_summary(mappings: list[CodeMapping]) -> str:
        if not mappings:
            return "No C constructs found to map."
        types: dict[str, int] = {}
        total_conf = 0.0
        for m in mappings:
            types[m.construct_type] = types.get(m.construct_type, 0) + 1
            total_conf += m.confidence
        avg_conf = total_conf / len(mappings)
        parts = [f"Found {len(mappings)} C constructs:"]
        for ctype, count in sorted(types.items()):
            parts.append(f"  - {ctype}: {count}")
        parts.append(f"Average mapping confidence: {avg_conf:.1%}")
        return "\n".join(parts)

    @staticmethod
    def _estimate_difficulty(construct_type: str) -> tuple[str, str]:
        difficulty_map = {
            ConstructType.FUNCTION: (Difficulty.EASY, "10 minutes"),
            ConstructType.IO_WRITE: (Difficulty.EASY, "5 minutes"),
            ConstructType.PREPROCESSOR: (Difficulty.EASY, "5 minutes"),
            ConstructType.STRUCT: (Difficulty.MEDIUM, "20 minutes"),
            ConstructType.POINTER: (Difficulty.HARD, "30 minutes"),
            ConstructType.MEMORY: (Difficulty.MEDIUM, "20 minutes"),
            ConstructType.CALL: (Difficulty.EASY, "5 minutes"),
            ConstructType.LOOP: (Difficulty.EASY, "10 minutes"),
        }
        return difficulty_map.get(construct_type, (Difficulty.MEDIUM, "15 minutes"))

    @staticmethod
    def _step_description(construct_type: str, original: str) -> str:
        desc_map = {
            ConstructType.FUNCTION: "Convert C function to FIR function",
            ConstructType.IO_WRITE: "Replace printf() with IO_WRITE",
            ConstructType.PREPROCESSOR: "Convert #include to FIR module reference",
            ConstructType.STRUCT: "Convert C struct to FIR StructType",
            ConstructType.POINTER: "Convert pointer to FIR RefType + region",
            ConstructType.MEMORY: "Replace malloc/free with REGION ops",
            ConstructType.CALL: "Convert C function call to FIR CALL",
            ConstructType.LOOP: "Convert loop to FIR basic blocks",
        }
        return desc_map.get(construct_type, "Map construct to FLUX")

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
