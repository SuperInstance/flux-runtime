"""Tests for the FLUX Self-Documentation System.

Covers:
- CodeIntrospector: module listing, public API, dependencies, complexity, coverage
- DocumentationGenerator: API reference, architecture, opcodes, tiles, file writing
- MarkdownRenderer: modules, API, opcode tables, test summaries, TOC
- AsciiRenderer: architecture diagram, module tree, data flow
- CodeStatistics: LOC, test counts, public API size, full report
"""

from __future__ import annotations

import os
import tempfile

import pytest

from flux.docs.introspector import (
    CodeIntrospector,
    ModuleInfo,
    APIDeclaration,
    ComplexityMetrics,
)
from flux.docs.renderer import (
    MarkdownRenderer,
    AsciiRenderer,
)
from flux.docs.stats import CodeStatistics
from flux.docs.generator import DocumentationGenerator


REPO_PATH = os.path.join(os.path.dirname(__file__), "..")


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def introspector():
    return CodeIntrospector(REPO_PATH)


@pytest.fixture
def stats():
    return CodeStatistics(REPO_PATH)


@pytest.fixture
def generator():
    return DocumentationGenerator(REPO_PATH)


@pytest.fixture
def renderer():
    return MarkdownRenderer()


@pytest.fixture
def ascii_renderer():
    return AsciiRenderer()


@pytest.fixture
def sample_module(tmp_path):
    """Create a temporary Python module for introspection tests."""
    mod_file = tmp_path / "sample.py"
    mod_file.write_text('''\
"""Sample module for testing."""

PUBLIC_CONST = 42
_PRIVATE_CONST = 99

class SampleClass:
    """A sample class."""

    def public_method(self, x: int) -> int:
        """Do something."""
        return x * 2

    def _private_method(self):
        pass

def public_function(arg1: str, arg2: int = 0) -> str:
    """A public function."""
    return arg1

def _private_function():
    pass
''', encoding="utf-8")
    return str(mod_file)


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Module Listing
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorModuleListing:
    """Test CodeIntrospector lists all modules."""

    def test_list_modules_returns_list(self, introspector):
        modules = introspector.list_modules()
        assert isinstance(modules, list)

    def test_list_modules_finds_fir(self, introspector):
        modules = introspector.list_modules()
        names = [m.name for m in modules]
        assert any("types" in m.path for m in modules if "fir" in m.path)
        assert len(modules) > 10  # project has many modules

    def test_list_modules_has_path(self, introspector):
        modules = introspector.list_modules()
        for m in modules:
            assert m.path, f"Module {m.name} has no path"
            assert m.path.endswith(".py")

    def test_list_modules_has_loc(self, introspector):
        modules = introspector.list_modules()
        for m in modules:
            assert m.loc >= 0

    def test_list_modules_sorted(self, introspector):
        """Modules should be returned in sorted order."""
        modules = introspector.list_modules()
        paths = [m.path for m in modules]
        assert paths == sorted(paths)


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Public API
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorPublicAPI:
    """Test CodeIntrospector extracts public API."""

    def test_public_api_returns_list(self, sample_module, introspector):
        api = introspector.get_public_api(sample_module)
        assert isinstance(api, list)

    def test_public_api_excludes_private(self, sample_module, introspector):
        api = introspector.get_public_api(sample_module)
        names = [d.name for d in api]
        assert "PUBLIC_CONST" in names
        assert "_PRIVATE_CONST" not in names
        assert "public_function" in names
        assert "_private_function" not in names

    def test_public_api_has_kinds(self, sample_module, introspector):
        api = introspector.get_public_api(sample_module)
        kinds = {d.kind for d in api}
        assert "class" in kinds
        assert "function" in kinds
        assert "enum" in kinds

    def test_public_api_class_has_signature(self, sample_module, introspector):
        api = introspector.get_public_api(sample_module)
        classes = [d for d in api if d.kind == "class"]
        assert len(classes) == 1
        assert "SampleClass" in classes[0].signature

    def test_public_api_function_has_signature(self, sample_module, introspector):
        api = introspector.get_public_api(sample_module)
        funcs = [d for d in api if d.kind == "function"]
        assert len(funcs) >= 1
        func = funcs[0]
        assert "arg1" in func.signature
        assert func.docstring != ""

    def test_public_api_nonexistent_file(self, introspector):
        api = introspector.get_public_api("/nonexistent/path.py")
        assert api == []


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Dependencies
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorDependencies:
    """Test CodeIntrospector computes dependencies."""

    def test_dependencies_returns_list(self, sample_module, introspector):
        deps = introspector.get_dependencies(sample_module)
        assert isinstance(deps, list)

    def test_dependencies_empty_module(self, tmp_path, introspector):
        mod = tmp_path / "empty.py"
        mod.write_text("# just a comment\n", encoding="utf-8")
        deps = introspector.get_dependencies(str(mod))
        assert deps == []

    def test_dependencies_finds_imports(self, tmp_path, introspector):
        mod = tmp_path / "with_imports.py"
        mod.write_text('''
from os import path
import sys
from dataclasses import dataclass
''', encoding="utf-8")
        deps = introspector.get_dependencies(str(mod))
        assert "os" in deps
        assert "sys" in deps
        assert "dataclasses" in deps

    def test_dependencies_fir_module(self, introspector):
        fir_path = os.path.join(REPO_PATH, "src", "flux", "fir", "types.py")
        if os.path.exists(fir_path):
            deps = introspector.get_dependencies(fir_path)
            assert isinstance(deps, list)
            # FIR types module likely has imports
            assert len(deps) > 0


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Complexity
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorComplexity:
    """Test CodeIntrospector computes complexity."""

    def test_complexity_returns_metrics(self, sample_module, introspector):
        metrics = introspector.get_complexity(sample_module)
        assert isinstance(metrics, ComplexityMetrics)

    def test_complexity_loc(self, sample_module, introspector):
        metrics = introspector.get_complexity(sample_module)
        assert metrics.loc > 0

    def test_complexity_function_count(self, sample_module, introspector):
        metrics = introspector.get_complexity(sample_module)
        # sample module has public_function and _private_function
        assert metrics.function_count >= 2

    def test_complexity_class_count(self, sample_module, introspector):
        metrics = introspector.get_complexity(sample_module)
        assert metrics.class_count == 1  # SampleClass

    def test_complexity_cyclomatic(self, sample_module, introspector):
        metrics = introspector.get_complexity(sample_module)
        # Each function has base complexity of 1
        assert metrics.cyclomatic >= 2

    def test_complexity_nonexistent_file(self, introspector):
        metrics = introspector.get_complexity("/nonexistent.py")
        assert metrics.loc == 0
        assert metrics.cyclomatic == 0


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Module Info
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorModuleInfo:
    """Test get_module_info extraction."""

    def test_module_info_fields(self, sample_module, introspector):
        info = introspector.get_module_info(sample_module)
        assert info is not None
        assert info.name == "sample"
        assert "Sample module" in info.description
        assert "SampleClass" in info.classes
        assert "public_function" in info.functions
        assert "PUBLIC_CONST" in info.constants

    def test_module_info_nonexistent(self, introspector):
        info = introspector.get_module_info("/nonexistent/path.py")
        assert info is None


# ═══════════════════════════════════════════════════════════════════════
# CodeIntrospector — Test Coverage
# ═══════════════════════════════════════════════════════════════════════

class TestIntrospectorTestCoverage:
    """Test heuristic test coverage estimation."""

    def test_coverage_returns_dict(self, introspector):
        coverage = introspector.get_test_coverage()
        assert isinstance(coverage, dict)

    def test_coverage_values_in_range(self, introspector):
        coverage = introspector.get_test_coverage()
        for mod, score in coverage.items():
            assert 0.0 <= score <= 1.0, f"{mod}: {score} out of range"


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — API Reference
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorAPIReference:
    """Test DocumentationGenerator generates API reference."""

    def test_api_reference_not_empty(self, generator):
        ref = generator.generate_api_reference()
        assert len(ref) > 0
        assert "# API Reference" in ref

    def test_api_reference_has_classes(self, generator):
        ref = generator.generate_api_reference()
        assert "## Classes" in ref

    def test_api_reference_has_functions(self, generator):
        ref = generator.generate_api_reference()
        assert "## Functions" in ref


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — Architecture Overview
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorArchitecture:
    """Test DocumentationGenerator generates architecture overview."""

    def test_architecture_not_empty(self, generator):
        overview = generator.generate_architecture_overview()
        assert len(overview) > 0

    def test_architecture_has_title(self, generator):
        overview = generator.generate_architecture_overview()
        assert "# FLUX Architecture Overview" in overview

    def test_architecture_has_diagram(self, generator):
        overview = generator.generate_architecture_overview()
        assert "FLUX ARCHITECTURE" in overview

    def test_architecture_has_module_tree(self, generator):
        overview = generator.generate_architecture_overview()
        assert "Module Tree" in overview


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — Opcode Reference
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorOpcodeReference:
    """Test DocumentationGenerator generates opcode reference."""

    def test_opcode_reference_not_empty(self, generator):
        ref = generator.generate_opcode_reference()
        assert len(ref) > 0

    def test_opcode_reference_has_table(self, generator):
        ref = generator.generate_opcode_reference()
        assert "| Opcode |" in ref
        assert "|--------|" in ref

    def test_opcode_reference_has_nop(self, generator):
        ref = generator.generate_opcode_reference()
        assert "NOP" in ref

    def test_opcode_reference_has_halt(self, generator):
        ref = generator.generate_opcode_reference()
        assert "HALT" in ref

    def test_opcode_reference_has_iadd(self, generator):
        ref = generator.generate_opcode_reference()
        assert "IADD" in ref

    def test_opcode_count(self, generator):
        ref = generator.generate_opcode_reference()
        # Count rows (minus header and separator)
        rows = [line for line in ref.splitlines() if line.startswith("| `") or (line.startswith("| ") and "`" in line)]
        assert len(rows) > 50  # should have many opcodes


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — Tile Catalog
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorTileCatalog:
    """Test DocumentationGenerator generates tile catalog."""

    def test_tile_catalog_not_empty(self, generator):
        catalog = generator.generate_tile_catalog()
        assert len(catalog) > 0

    def test_tile_catalog_has_title(self, generator):
        catalog = generator.generate_tile_catalog()
        assert "# Tile Catalog" in catalog

    def test_tile_catalog_has_tiles(self, generator):
        catalog = generator.generate_tile_catalog()
        # Should find some well-known tiles
        assert "map" in catalog.lower()

    def test_tile_catalog_has_categories(self, generator):
        catalog = generator.generate_tile_catalog()
        # Should have category headings
        assert "## COMPUTE" in catalog
        assert "## MEMORY" in catalog
        assert "## CONTROL" in catalog


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — Test Report
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorTestReport:
    """Test DocumentationGenerator generates test report."""

    def test_test_report_not_empty(self, generator):
        report = generator.generate_test_report()
        assert len(report) > 0

    def test_test_report_has_total(self, generator):
        report = generator.generate_test_report()
        assert "Total tests" in report


# ═══════════════════════════════════════════════════════════════════════
# DocumentationGenerator — Generate All & Write
# ═══════════════════════════════════════════════════════════════════════

class TestGeneratorWriteAll:
    """Test DocumentationGenerator writes files."""

    def test_generate_all_returns_dict(self, generator):
        docs = generator.generate_all()
        assert isinstance(docs, dict)

    def test_generate_all_has_all_keys(self, generator):
        docs = generator.generate_all()
        expected = {
            "api_reference.md",
            "architecture_overview.md",
            "test_report.md",
            "opcode_reference.md",
            "tile_catalog.md",
        }
        assert set(docs.keys()) == expected

    def test_write_all_creates_files(self, generator, tmp_path):
        """Write to temp dir and verify files exist."""
        count = generator.write_all(output_dir=str(tmp_path / "docs"))
        assert count == 5
        assert (tmp_path / "docs" / "api_reference.md").exists()
        assert (tmp_path / "docs" / "opcode_reference.md").exists()
        assert (tmp_path / "docs" / "tile_catalog.md").exists()

    def test_write_all_content_valid(self, generator, tmp_path):
        """Written files should have valid markdown content."""
        generator.write_all(output_dir=str(tmp_path / "out"))
        api = (tmp_path / "out" / "api_reference.md").read_text()
        assert "# API Reference" in api


# ═══════════════════════════════════════════════════════════════════════
# MarkdownRenderer
# ═══════════════════════════════════════════════════════════════════════

class TestMarkdownRenderer:
    """Test MarkdownRenderer renders correctly."""

    def test_render_module(self, renderer):
        info = ModuleInfo(
            name="test_mod",
            path="/path/to/test_mod.py",
            description="A test module.",
            classes=["Foo", "Bar"],
            functions=["baz"],
            constants=["VERSION"],
            imports=["os"],
            loc=42,
        )
        result = renderer.render_module(info)
        assert "## Module: `test_mod`" in result
        assert "A test module." in result
        assert "`Foo`" in result
        assert "`baz()`" in result
        assert "`VERSION`" in result
        assert "**LOC:** 42" in result

    def test_render_api_empty(self, renderer):
        result = renderer.render_api([])
        assert "No public declarations" in result

    def test_render_api_with_declarations(self, renderer):
        decls = [
            APIDeclaration(name="MyClass", kind="class", signature="class MyClass",
                           docstring="A class.", module="test"),
            APIDeclaration(name="my_func", kind="function", signature="def my_func()",
                           docstring="A func.", module="test"),
        ]
        result = renderer.render_api(decls)
        assert "## Classes" in result
        assert "## Functions" in result
        assert "MyClass" in result
        assert "my_func" in result

    def test_render_opcode_table(self, renderer):
        opcodes = [
            {"name": "NOP", "hex": "0x00", "format": "A", "size": 1,
             "category": "Control", "description": "No operation"},
            {"name": "IADD", "hex": "0x08", "format": "C", "size": 3,
             "category": "Arithmetic", "description": "Integer add"},
        ]
        result = renderer.render_opcode_table(opcodes)
        assert "| Opcode |" in result
        assert "`NOP`" in result
        assert "`IADD`" in result
        assert "0x00" in result

    def test_render_tile_card(self, renderer):
        tile = {
            "name": "map",
            "type": "COMPUTE",
            "cost": 1.0,
            "abstraction": 6,
            "inputs": ["data"],
            "outputs": ["result"],
            "tags": ["compute", "map"],
        }
        result = renderer.render_tile_card(tile)
        assert "### Tile: `map`" in result
        assert "COMPUTE" in result
        assert "`data`" in result

    def test_render_test_summary(self, renderer):
        test_data = {
            "total_tests": 100,
            "total_modules": 10,
            "tested_modules": 8,
            "coverage_score": 0.8,
            "coverage": {"fir": 1.0, "vm": 0.9},
        }
        result = renderer.render_test_summary(test_data)
        assert "**Total tests:** 100" in result
        assert "fir" in result

    def test_render_toc(self, renderer):
        sections = [
            {"title": "Introduction", "anchor": "introduction", "level": 2},
            {"title": "API Reference", "anchor": "api-reference", "level": 2},
            {"title": "Classes", "anchor": "classes", "level": 3},
        ]
        result = renderer.render_toc(sections)
        assert "[Introduction]" in result
        assert "  - [Classes]" in result  # indented (level 3)


# ═══════════════════════════════════════════════════════════════════════
# AsciiRenderer
# ═══════════════════════════════════════════════════════════════════════

class TestAsciiRenderer:
    """Test AsciiRenderer generates ASCII art."""

    def test_architecture_diagram_not_empty(self, ascii_renderer):
        diagram = ascii_renderer.render_architecture_diagram()
        assert len(diagram) > 0
        assert "FLUX" in diagram

    def test_architecture_diagram_has_boxes(self, ascii_renderer):
        diagram = ascii_renderer.render_architecture_diagram()
        assert "┌" in diagram
        assert "┐" in diagram
        assert "└" in diagram
        assert "┘" in diagram

    def test_architecture_diagram_has_arrows(self, ascii_renderer):
        diagram = ascii_renderer.render_architecture_diagram()
        assert "──▶" in diagram

    def test_module_tree_not_empty(self, ascii_renderer, introspector):
        modules = introspector.list_modules()
        tree = ascii_renderer.render_module_tree(modules)
        assert len(tree) > 0
        assert "flux/" in tree
        assert "├── " in tree or "└── " in tree

    def test_module_tree_has_directories(self, ascii_renderer, introspector):
        modules = introspector.list_modules()
        tree = ascii_renderer.render_module_tree(modules)
        # Should contain at least fir and vm modules
        assert "fir" in tree
        assert "vm" in tree

    def test_data_flow_not_empty(self, ascii_renderer):
        flow = ascii_renderer.render_data_flow()
        assert len(flow) > 0
        assert "Source Code" in flow
        assert "Bytecode" in flow
        assert "VM" in flow


# ═══════════════════════════════════════════════════════════════════════
# CodeStatistics
# ═══════════════════════════════════════════════════════════════════════

class TestCodeStatistics:
    """Test CodeStatistics computes statistics."""

    def test_total_loc_positive(self, stats):
        assert stats.total_loc() > 0

    def test_loc_by_module_returns_dict(self, stats):
        loc = stats.loc_by_module()
        assert isinstance(loc, dict)
        assert len(loc) > 0

    def test_loc_by_module_has_known_modules(self, stats):
        loc = stats.loc_by_module()
        assert "fir" in loc
        assert "vm" in loc

    def test_loc_sum_matches_total(self, stats):
        loc = stats.loc_by_module()
        assert sum(loc.values()) == stats.total_loc()

    def test_test_count_positive(self, stats):
        assert stats.test_count() > 0

    def test_test_count_large(self, stats):
        """Should find 1000+ tests in the project."""
        assert stats.test_count() > 1000

    def test_test_count_by_module_returns_dict(self, stats):
        tests = stats.test_count_by_module()
        assert isinstance(tests, dict)
        assert len(tests) > 0

    def test_public_api_size_positive(self, stats):
        assert stats.public_api_size() > 0

    def test_module_count_positive(self, stats):
        assert stats.module_count() > 0

    def test_module_count_reasonable(self, stats):
        """Should have 15+ modules in the project."""
        assert stats.module_count() >= 15

    def test_complexity_report_returns_dict(self, stats):
        report = stats.complexity_report()
        assert isinstance(report, dict)
        assert len(report) > 0

    def test_complexity_report_has_fir(self, stats):
        report = stats.complexity_report()
        assert "fir" in report
        assert report["fir"].loc > 0

    def test_growth_report(self, stats):
        report = stats.growth_report()
        assert isinstance(report, str)
        assert len(report) > 0
        assert "Growth Report" in report

    def test_full_report(self, stats):
        report = stats.full_report()
        assert isinstance(report, str)
        assert "# FLUX Code Statistics" in report
        assert "Overview" in report
        assert "LOC" in report


# ═══════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════

class TestDataTypes:
    """Test data type constructors and defaults."""

    def test_module_info_defaults(self):
        info = ModuleInfo()
        assert info.name == ""
        assert info.classes == []
        assert info.loc == 0

    def test_api_declaration_defaults(self):
        decl = APIDeclaration()
        assert decl.name == ""
        assert decl.kind == ""

    def test_complexity_metrics_defaults(self):
        metrics = ComplexityMetrics()
        assert metrics.loc == 0
        assert metrics.cyclomatic == 0
        assert metrics.avg_function_length == 0.0

    def test_module_info_custom(self):
        info = ModuleInfo(
            name="test",
            path="/test.py",
            description="desc",
            classes=["C"],
            functions=["f"],
            constants=["X"],
            imports=["os"],
            loc=10,
        )
        assert info.name == "test"
        assert info.loc == 10
