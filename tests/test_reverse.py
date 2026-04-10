"""Tests for the FLUX Reverse Engineering Module.

Covers:
- CodeMap data structures
- MigrationPlan data structures
- Python -> FLUX reverse engineering
- C -> FLUX reverse engineering
- FluxReverseEngineer core engine
- File/directory analysis
- FLUX.MD generation
"""

import os
import tempfile
import pytest

from flux.reverse.code_map import (
    CodeMapping,
    CodeMap,
    ConstructType,
    Difficulty,
    MigrationStep,
    MigrationPlan,
)
from flux.reverse.engineer import (
    FluxReverseEngineer,
    UnsupportedLanguageError,
)
from flux.reverse.parsers.python_reverse import PythonReverseEngineer
from flux.reverse.parsers.c_reverse import CReverseEngineer


# ======================================================================
# CodeMapping Tests
# ======================================================================

class TestCodeMapping:
    """Tests for CodeMapping dataclass."""

    def test_create_basic_mapping(self):
        m = CodeMapping(
            original="x = 5",
            flux_ir="STORE 5, x",
            construct_type="variable",
        )
        assert m.original == "x = 5"
        assert m.flux_ir == "STORE 5, x"
        assert m.construct_type == "variable"
        assert m.confidence == 1.0
        assert m.notes == ""
        assert m.line_number is None

    def test_confidence_bounds_valid(self):
        m = CodeMapping(
            original="x = 1",
            flux_ir="STORE 1, x",
            construct_type="variable",
            confidence=0.0,
        )
        assert m.confidence == 0.0

        m2 = CodeMapping(
            original="x = 1",
            flux_ir="STORE 1, x",
            construct_type="variable",
            confidence=1.0,
        )
        assert m2.confidence == 1.0

    def test_confidence_out_of_bounds_raises(self):
        with pytest.raises(ValueError, match="confidence must be"):
            CodeMapping(
                original="x = 1",
                flux_ir="STORE 1, x",
                construct_type="variable",
                confidence=1.5,
            )

    def test_confidence_negative_raises(self):
        with pytest.raises(ValueError, match="confidence must be"):
            CodeMapping(
                original="x = 1",
                flux_ir="STORE 1, x",
                construct_type="variable",
                confidence=-0.1,
            )

    def test_with_line_number(self):
        m = CodeMapping(
            original="def foo():",
            flux_ir="func foo()",
            construct_type=ConstructType.FUNCTION,
            line_number=10,
        )
        assert m.line_number == 10

    def test_with_notes(self):
        m = CodeMapping(
            original="print('hello')",
            flux_ir="IO_WRITE 'hello'",
            construct_type=ConstructType.IO_WRITE,
            notes="print maps to IO_WRITE",
        )
        assert "IO_WRITE" in m.notes


# ======================================================================
# CodeMap Tests
# ======================================================================

class TestCodeMap:
    """Tests for CodeMap dataclass."""

    def test_empty_code_map(self):
        cm = CodeMap(source_lang="python", source_code="")
        assert cm.mapping_count == 0
        assert cm.avg_confidence == 0.0
        assert cm.construct_types == set()
        assert cm.summary == ""

    def test_code_map_with_mappings(self):
        cm = CodeMap(
            source_lang="python",
            source_code="x = 5",
            mappings=[
                CodeMapping("x = 5", "STORE 5, x", "variable", 0.9),
                CodeMapping("y = 3", "STORE 3, y", "variable", 0.8),
            ],
        )
        assert cm.mapping_count == 2
        assert cm.avg_confidence == pytest.approx(0.85)
        assert cm.construct_types == {"variable"}

    def test_get_mappings_by_type(self):
        cm = CodeMap(
            source_lang="python",
            source_code="",
            mappings=[
                CodeMapping("x = 5", "STORE 5, x", ConstructType.VARIABLE),
                CodeMapping("def f()", "func f()", ConstructType.FUNCTION),
                CodeMapping("y = 3", "STORE 3, y", ConstructType.VARIABLE),
            ],
        )
        vars_ = cm.get_mappings_by_type(ConstructType.VARIABLE)
        assert len(vars_) == 2
        funcs = cm.get_mappings_by_type(ConstructType.FUNCTION)
        assert len(funcs) == 1

    def test_get_low_confidence(self):
        cm = CodeMap(
            source_lang="python",
            source_code="",
            mappings=[
                CodeMapping("a", "b", "x", 0.9),
                CodeMapping("c", "d", "x", 0.3),
                CodeMapping("e", "f", "x", 0.7),
            ],
        )
        low = cm.get_low_confidence(0.5)
        assert len(low) == 1
        assert low[0].original == "c"

    def test_multiple_construct_types(self):
        cm = CodeMap(
            source_lang="python",
            source_code="",
            mappings=[
                CodeMapping("def f()", "func f()", ConstructType.FUNCTION),
                CodeMapping("print(x)", "IO_WRITE", ConstructType.IO_WRITE),
                CodeMapping("for i in range(10):", "JMP header", ConstructType.LOOP),
            ],
        )
        assert cm.construct_types == {
            ConstructType.FUNCTION,
            ConstructType.IO_WRITE,
            ConstructType.LOOP,
        }


# ======================================================================
# MigrationStep Tests
# ======================================================================

class TestMigrationStep:
    """Tests for MigrationStep dataclass."""

    def test_create_easy_step(self):
        step = MigrationStep(
            step_number=1,
            description="Convert variable",
            original_code="x = 5",
            flux_code="STORE 5, x",
            difficulty=Difficulty.EASY,
            estimated_effort="5 minutes",
        )
        assert step.step_number == 1
        assert step.difficulty == Difficulty.EASY

    def test_invalid_difficulty_raises(self):
        with pytest.raises(ValueError, match="difficulty must be"):
            MigrationStep(
                step_number=1,
                description="test",
                original_code="x",
                flux_code="y",
                difficulty="impossible",
            )


# ======================================================================
# MigrationPlan Tests
# ======================================================================

class TestMigrationPlan:
    """Tests for MigrationPlan dataclass."""

    def _make_plan(self) -> MigrationPlan:
        return MigrationPlan(
            source_lang="python",
            total_steps=3,
            steps=[
                MigrationStep(1, "Easy step", "x", "y", Difficulty.EASY, "5 minutes"),
                MigrationStep(2, "Medium step", "a", "b", Difficulty.MEDIUM, "15 minutes"),
                MigrationStep(3, "Hard step", "p", "q", Difficulty.HARD, "60 minutes"),
            ],
        )

    def test_step_counts(self):
        plan = self._make_plan()
        assert len(plan.easy_steps) == 1
        assert len(plan.medium_steps) == 1
        assert len(plan.hard_steps) == 1

    def test_estimated_total_effort(self):
        plan = self._make_plan()
        effort = plan.estimated_total_effort
        # 5 + 15 + 60 = 80 minutes = ~1.3 hours
        assert "hours" in effort

    def test_empty_plan(self):
        plan = MigrationPlan(source_lang="python", total_steps=0)
        assert plan.easy_steps == []
        assert plan.medium_steps == []
        assert plan.hard_steps == []
        assert plan.estimated_total_effort == "~0 minutes"

    def test_all_easy_plan(self):
        plan = MigrationPlan(
            source_lang="python",
            total_steps=2,
            steps=[
                MigrationStep(1, "s1", "a", "b", Difficulty.EASY, "5 minutes"),
                MigrationStep(2, "s2", "c", "d", Difficulty.EASY, "5 minutes"),
            ],
        )
        assert plan.estimated_total_effort == "~10 minutes"


# ======================================================================
# Python Reverse Engineer Tests
# ======================================================================

class TestPythonReverseEngineer:
    """Tests for Python-specific reverse engineering."""

    def setup_method(self):
        self.engine = PythonReverseEngineer()

    def test_analyze_simple_function(self):
        source = "def foo():\n    return 42"
        code_map = self.engine.analyze(source)
        assert code_map.source_lang == "python"
        assert code_map.mapping_count > 0
        assert any(m.construct_type == ConstructType.FUNCTION for m in code_map.mappings)

    def test_analyze_function_with_params(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        code_map = self.engine.analyze(source)
        func_maps = code_map.get_mappings_by_type(ConstructType.FUNCTION)
        assert len(func_maps) >= 1
        assert "func add" in func_maps[0].flux_ir

    def test_analyze_class(self):
        source = "class Foo:\n    pass"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.CLASS for m in code_map.mappings)

    def test_analyze_import(self):
        source = "import os\nimport sys"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.IMPORT for m in code_map.mappings)

    def test_analyze_from_import(self):
        source = "from math import sqrt"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.IMPORT for m in code_map.mappings)

    def test_analyze_print(self):
        source = 'print("hello")'
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.IO_WRITE for m in code_map.mappings)

    def test_analyze_loop(self):
        source = "for i in range(10):\n    pass"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.LOOP for m in code_map.mappings)

    def test_analyze_while_loop(self):
        source = "while True:\n    break"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.LOOP for m in code_map.mappings)

    def test_analyze_try_except(self):
        source = "try:\n    x = 1\nexcept:\n    pass"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.ERROR_HANDLING for m in code_map.mappings)

    def test_analyze_async_def(self):
        source = "async def fetch():\n    pass"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.ASYNC for m in code_map.mappings)

    def test_analyze_list_comprehension(self):
        source = "def f():\n    x = [i * 2 for i in range(10)]"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.COMPREHENSION for m in code_map.mappings)

    def test_analyze_decorator(self):
        source = "@timed\ndef foo():\n    pass"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.DECORATOR for m in code_map.mappings)

    def test_migration_plan(self):
        source = "def foo():\n    print('hello')\n    return 42"
        plan = self.engine.migration_plan(source)
        assert plan.source_lang == "python"
        assert plan.total_steps > 0
        assert len(plan.steps) > 0
        assert all(s.step_number > 0 for s in plan.steps)

    def test_invalid_syntax(self):
        source = "def ( :"
        code_map = self.engine.analyze(source)
        assert code_map.mapping_count == 1
        assert code_map.mappings[0].confidence == 0.0

    def test_analyze_variable(self):
        source = "def f():\n    x = 42\n    y = x + 1"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.VARIABLE for m in code_map.mappings)


# ======================================================================
# C Reverse Engineer Tests
# ======================================================================

class TestCReverseEngineer:
    """Tests for C-specific reverse engineering."""

    def setup_method(self):
        self.engine = CReverseEngineer()

    def test_analyze_simple_function(self):
        source = "int main() {\n    return 0;\n}"
        code_map = self.engine.analyze(source)
        assert code_map.source_lang == "c"
        assert code_map.mapping_count > 0
        assert any(m.construct_type == ConstructType.FUNCTION for m in code_map.mappings)

    def test_analyze_struct(self):
        source = "typedef struct {\n    int x;\n    int y;\n} Point;"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.STRUCT for m in code_map.mappings)
        struct_maps = code_map.get_mappings_by_type(ConstructType.STRUCT)
        assert "Point" in struct_maps[0].flux_ir

    def test_analyze_malloc(self):
        source = "void f() {\n    int *p = (int*)malloc(sizeof(int));\n    free(p);\n}"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.MEMORY for m in code_map.mappings)

    def test_analyze_printf(self):
        source = 'void f() {\n    printf("hello %d\\n", 42);\n}'
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.IO_WRITE for m in code_map.mappings)

    def test_analyze_include(self):
        source = '#include <stdio.h>\n#include "mylib.h"'
        code_map = self.engine.analyze(source)
        includes = code_map.get_mappings_by_type(ConstructType.PREPROCESSOR)
        assert len(includes) >= 2

    def test_analyze_pointer(self):
        source = "void f() {\n    int *ptr;\n    double *dptr;\n}"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.POINTER for m in code_map.mappings)

    def test_analyze_for_loop(self):
        source = "void f() {\n    for (int i = 0; i < 10; i++) {\n    }\n}"
        code_map = self.engine.analyze(source)
        assert any(m.construct_type == ConstructType.LOOP for m in code_map.mappings)

    def test_analyze_while_loop(self):
        source = "void f() {\n    while (1) {\n    }\n}"
        code_map = self.engine.analyze(source)
        loops = code_map.get_mappings_by_type(ConstructType.LOOP)
        assert len(loops) >= 1

    def test_analyze_function_with_params(self):
        source = "int add(int a, int b) {\n    return a + b;\n}"
        code_map = self.engine.analyze(source)
        funcs = code_map.get_mappings_by_type(ConstructType.FUNCTION)
        assert len(funcs) >= 1
        assert "func add" in funcs[0].flux_ir

    def test_migration_plan(self):
        source = '#include <stdio.h>\nint main() {\n    printf("hi");\n    return 0;\n}'
        plan = self.engine.migration_plan(source)
        assert plan.source_lang == "c"
        assert plan.total_steps > 0

    def test_empty_source(self):
        code_map = self.engine.analyze("")
        assert code_map.mapping_count == 0

    def test_c_type_to_fir(self):
        assert CReverseEngineer._c_type_to_fir("int") == "i32"
        assert CReverseEngineer._c_type_to_fir("float") == "f32"
        assert CReverseEngineer._c_type_to_fir("double") == "f64"
        assert CReverseEngineer._c_type_to_fir("char") == "i8"
        assert CReverseEngineer._c_type_to_fir("void") == "void"
        assert CReverseEngineer._c_type_to_fir("unknown_t") == "i32"


# ======================================================================
# FluxReverseEngineer Tests (Core Engine)
# ======================================================================

class TestFluxReverseEngineer:
    """Tests for the main FluxReverseEngineer."""

    def setup_method(self):
        self.engineer = FluxReverseEngineer()

    def test_supported_languages(self):
        langs = self.engineer.supported_languages
        assert "python" in langs
        assert "c" in langs

    def test_analyze_python(self):
        code_map = self.engineer.analyze("x = 5", lang="python")
        assert code_map.source_lang == "python"

    def test_analyze_c(self):
        code_map = self.engineer.analyze("int x = 5;", lang="c")
        assert code_map.source_lang == "c"

    def test_unsupported_language_raises(self):
        with pytest.raises(UnsupportedLanguageError, match="Unsupported language"):
            self.engineer.analyze("console.log('hi')", lang="javascript")

    def test_migration_plan_python(self):
        plan = self.engineer.migration_plan("def f(): return 1", lang="python")
        assert plan.source_lang == "python"
        assert plan.total_steps > 0

    def test_migration_plan_c(self):
        plan = self.engineer.migration_plan("int f() { return 1; }", lang="c")
        assert plan.source_lang == "c"
        assert plan.total_steps > 0

    def test_analyze_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("def foo():\n    return 42\n")
            f.flush()
            code_map = self.engineer.analyze_file(f.name)
        os.unlink(f.name)
        assert code_map.source_lang == "python"
        assert code_map.mapping_count > 0

    def test_analyze_c_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".c", delete=False
        ) as f:
            f.write("int main() { return 0; }\n")
            f.flush()
            code_map = self.engineer.analyze_file(f.name)
        os.unlink(f.name)
        assert code_map.source_lang == "c"
        assert code_map.mapping_count > 0

    def test_analyze_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.engineer.analyze_file("/nonexistent/file.py")

    def test_analyze_file_unknown_extension(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xyz", delete=False
        ) as f:
            f.write("whatever\n")
            f.flush()
            with pytest.raises(UnsupportedLanguageError):
                self.engineer.analyze_file(f.name)
        os.unlink(f.name)

    def test_analyze_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "test.py"), "w") as f:
                f.write("def f(): pass\n")
            with open(os.path.join(tmpdir, "test.c"), "w") as f:
                f.write("int f() { return 0; }\n")
            with open(os.path.join(tmpdir, "readme.txt"), "w") as f:
                f.write("not a source file\n")

            results = self.engineer.analyze_directory(tmpdir)
            assert "test.py" in results
            assert "test.c" in results
            assert "readme.txt" not in results

    def test_generate_flux_md_python(self):
        flux_md = self.engineer.generate_flux_md(
            "def foo():\n    return 42", lang="python"
        )
        assert "python" in flux_md.lower() or "Python" in flux_md
        assert "func foo" in flux_md

    def test_generate_flux_md_c(self):
        flux_md = self.engineer.generate_flux_md(
            "int main() { return 0; }", lang="c"
        )
        assert "func main" in flux_md

    def test_case_insensitive_language(self):
        code_map = self.engineer.analyze("x = 1", lang="Python")
        assert code_map.source_lang == "python"

    def test_whitespace_trimmed_language(self):
        code_map = self.engineer.analyze("x = 1", lang="  python  ")
        assert code_map.source_lang == "python"
