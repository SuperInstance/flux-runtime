"""Tests for the FLUX Schema — formal, machine-readable schemas."""

import json

import pytest

from flux.schema.architecture import (
    FLUX_ARCHITECTURE,
    get_architecture_schema,
    get_layer_by_id,
    get_module_dependencies,
)
from flux.schema.opcode_schema import (
    get_opcode_schema,
    get_opcodes_by_category,
    get_opcodes_by_format,
)
from flux.schema.tile_schema import (
    get_tile_library_schema,
    search_tiles,
)
from flux.schema.builder_schema import (
    FLUX_BUILDER_SCHEMA,
    get_builder_schema,
    get_open_questions,
)


# ══════════════════════════════════════════════════════════════════════════
# Architecture Schema
# ══════════════════════════════════════════════════════════════════════════

class TestArchitectureSchema:
    """Test the system architecture schema is complete and correct."""

    def test_schema_has_name_and_version(self):
        arch = get_architecture_schema()
        assert arch["name"] == "FLUX"
        assert arch["version"] == "2.0"
        assert "description" in arch

    def test_schema_has_layers(self):
        arch = get_architecture_schema()
        assert "layers" in arch
        assert len(arch["layers"]) >= 20

    def test_schema_has_total_counts(self):
        arch = get_architecture_schema()
        assert arch["total_tests"] == 1615
        assert arch["total_modules"] >= 25

    def test_core_layers_present(self):
        """All core pipeline layers must be present."""
        arch = get_architecture_schema()
        layer_ids = {l["id"] for l in arch["layers"]}
        required = [
            "L0_PARSER", "L1_FIR", "L2_BYTECODE", "L3_VM",
            "L2_OPTIMIZER", "L2_JIT", "L3_COMPILER", "L4_PIPELINE",
            "L4_RUNTIME",
        ]
        for lid in required:
            assert lid in layer_ids, f"Missing layer: {lid}"

    def test_extension_layers_present(self):
        """All extension layers must be present."""
        arch = get_architecture_schema()
        layer_ids = {l["id"] for l in arch["layers"]}
        required = [
            "EXT_MODULES", "EXT_ADAPTIVE", "EXT_TILES", "EXT_EVOLUTION",
            "EXT_FLYWHEEL", "EXT_SWARM", "EXT_MEMORY", "EXT_SIMULATION",
            "EXT_CREATIVE", "EXT_SYNTHESIS",
        ]
        for lid in required:
            assert lid in layer_ids, f"Missing extension layer: {lid}"

    def test_each_layer_has_required_fields(self):
        arch = get_architecture_schema()
        required_fields = ["id", "name", "module"]
        for layer in arch["layers"]:
            for field in required_fields:
                assert field in layer, f"Layer {layer['id']} missing field: {field}"

    def test_fir_layer_has_features(self):
        layer = get_layer_by_id("L1_FIR")
        assert layer is not None
        assert "features" in layer
        assert len(layer["features"]) >= 5
        assert any("SSA" in f for f in layer["features"])

    def test_get_layer_by_id_returns_correct_layer(self):
        layer = get_layer_by_id("L0_PARSER")
        assert layer is not None
        assert layer["name"] == "FLUX.MD Parser"
        assert layer["module"] == "flux.parser"

    def test_get_layer_by_id_returns_none_for_unknown(self):
        assert get_layer_by_id("NONEXISTENT_LAYER") is None

    def test_vm_layer_has_test_count(self):
        layer = get_layer_by_id("L3_VM")
        assert layer is not None
        assert "tests" in layer
        assert "108" in layer["tests"]


# ══════════════════════════════════════════════════════════════════════════
# Module Dependencies
# ══════════════════════════════════════════════════════════════════════════

class TestModuleDependencies:
    """Test the module dependency graph."""

    def test_dependency_graph_exists(self):
        deps = get_module_dependencies()
        assert isinstance(deps, dict)
        assert len(deps) >= 20

    def test_parser_has_no_dependencies(self):
        deps = get_module_dependencies()
        assert deps["flux.parser"] == []

    def test_fir_has_no_dependencies(self):
        deps = get_module_dependencies()
        assert deps["flux.fir"] == []

    def test_vm_depends_on_bytecode(self):
        deps = get_module_dependencies()
        assert "flux.bytecode" in deps["flux.vm"]

    def test_pipeline_depends_on_core_layers(self):
        deps = get_module_dependencies()
        pipeline_deps = deps["flux.pipeline"]
        assert "flux.parser" in pipeline_deps
        assert "flux.fir" in pipeline_deps
        assert "flux.bytecode" in pipeline_deps
        assert "flux.vm" in pipeline_deps

    def test_evolution_depends_on_tiles_and_adaptive(self):
        deps = get_module_dependencies()
        evo_deps = deps["flux.evolution"]
        assert "flux.tiles" in evo_deps
        assert "flux.adaptive" in evo_deps

    def test_flywheel_depends_on_evolution(self):
        deps = get_module_dependencies()
        assert "flux.evolution" in deps["flux.flywheel"]

    def test_no_cycles_in_dependency_graph(self):
        """Verify the dependency graph is a DAG (no cycles)."""
        deps = get_module_dependencies()
        visited = set()
        in_stack = set()

        def has_cycle(module: str) -> bool:
            visited.add(module)
            in_stack.add(module)
            for dep in deps.get(module, []):
                if dep in in_stack:
                    return True
                if dep not in visited:
                    if has_cycle(dep):
                        return True
            in_stack.discard(module)
            return False

        for module in deps:
            visited.clear()
            in_stack.clear()
            assert not has_cycle(module), f"Cycle detected involving {module}"

    def test_all_referenced_modules_exist(self):
        """Every dependency must itself be in the graph."""
        deps = get_module_dependencies()
        all_modules = set(deps.keys())
        for module, module_deps in deps.items():
            for dep in module_deps:
                assert dep in all_modules, f"{module} depends on unknown module: {dep}"


# ══════════════════════════════════════════════════════════════════════════
# Opcode Schema
# ══════════════════════════════════════════════════════════════════════════

class TestOpcodeSchema:
    """Test the opcode reference schema."""

    def test_opcode_schema_has_all_opcodes(self):
        schema = get_opcode_schema()
        # Must have at least 80 opcodes (104 canonical minus some gaps)
        assert len(schema) >= 80

    def test_all_opcodes_have_required_fields(self):
        schema = get_opcode_schema()
        required = ["value", "format", "category", "cost_ns", "energy_nj", "description"]
        for name, info in schema.items():
            for field in required:
                assert field in info, f"Opcode {name} missing field: {field}"

    def test_nop_opcode(self):
        schema = get_opcode_schema()
        nop = schema["NOP"]
        assert nop["value"] == 0x00
        assert nop["format"] == "A"
        assert nop["category"] == "control"
        assert nop["cost_ns"] < 1.0

    def test_halt_opcode(self):
        schema = get_opcode_schema()
        halt = schema["HALT"]
        assert halt["value"] == 0x80
        assert halt["format"] == "A"
        assert halt["category"] == "system"

    def test_arithmetic_opcodes_present(self):
        schema = get_opcode_schema()
        for name in ["IADD", "ISUB", "IMUL", "IDIV"]:
            assert name in schema
            assert schema[name]["category"] == "integer_arithmetic"

    def test_float_opcodes_present(self):
        schema = get_opcode_schema()
        for name in ["FADD", "FSUB", "FMUL", "FDIV", "FNEG"]:
            assert name in schema
            assert schema[name]["category"] == "float_arithmetic"

    def test_a2a_opcodes_present(self):
        schema = get_opcode_schema()
        for name in ["TELL", "ASK", "DELEGATE", "BROADCAST", "BARRIER"]:
            assert name in schema
            assert schema[name]["category"] == "a2a_protocol"

    def test_opcode_values_are_unique(self):
        schema = get_opcode_schema()
        values = [info["value"] for info in schema.values()]
        assert len(values) == len(set(values)), "Duplicate opcode values found"

    def test_cost_and_energy_are_positive(self):
        schema = get_opcode_schema()
        for name, info in schema.items():
            assert info["cost_ns"] >= 0, f"{name} has negative cost_ns"
            assert info["energy_nj"] >= 0, f"{name} has negative energy_nj"


# ══════════════════════════════════════════════════════════════════════════
# Opcode Grouping
# ══════════════════════════════════════════════════════════════════════════

class TestOpcodeGrouping:
    """Test opcode grouping by category and format."""

    def test_category_groups_exist(self):
        by_cat = get_opcodes_by_category()
        expected_categories = [
            "control", "integer_arithmetic", "bitwise", "comparison",
            "stack", "function", "memory_management", "type_ops",
            "float_arithmetic", "float_comparison", "simd",
            "a2a_protocol", "system",
        ]
        for cat in expected_categories:
            assert cat in by_cat, f"Missing category: {cat}"

    def test_format_groups_exist(self):
        by_fmt = get_opcodes_by_format()
        for fmt in ["A", "B", "C", "D", "E", "G"]:
            assert fmt in by_fmt, f"Missing format: {fmt}"

    def test_category_grouping_covers_all_opcodes(self):
        schema = get_opcode_schema()
        by_cat = get_opcodes_by_category()
        total_grouped = sum(len(ops) for ops in by_cat.values())
        assert total_grouped == len(schema)

    def test_format_grouping_covers_all_opcodes(self):
        schema = get_opcode_schema()
        by_fmt = get_opcodes_by_format()
        total_grouped = sum(len(ops) for ops in by_fmt.values())
        assert total_grouped == len(schema)

    def test_format_a_opcodes_are_single_byte(self):
        by_fmt = get_opcodes_by_format()
        # Format A = opcode only, no operands.
        # Includes NOP, HALT, YIELD, DUP, SWAP, ROT, DEBUG_BREAK, EMERGENCY_STOP
        known_format_a = {"NOP", "HALT", "YIELD", "DUP", "SWAP", "ROT", "DEBUG_BREAK", "EMERGENCY_STOP"}
        for op in by_fmt["A"]:
            assert op["name"] in known_format_a, f"{op['name']} not in known Format A opcodes"

    def test_a2a_category_has_most_opcodes(self):
        by_cat = get_opcodes_by_category()
        a2a_count = len(by_cat.get("a2a_protocol", []))
        # A2A has 25 opcodes — should be one of the largest groups
        assert a2a_count >= 20

    def test_simd_has_vfma(self):
        by_cat = get_opcodes_by_category()
        simd_names = [op["name"] for op in by_cat.get("simd", [])]
        assert "VFMA" in simd_names
        assert "VADD" in simd_names


# ══════════════════════════════════════════════════════════════════════════
# Tile Library Schema
# ══════════════════════════════════════════════════════════════════════════

class TestTileLibrarySchema:
    """Test the tile library schema."""

    def test_all_34_tiles_present(self):
        schema = get_tile_library_schema()
        # 8 compute + 6 memory + 6 control + 6 a2a + 3 effect + 6 transform = 35
        assert len(schema) >= 34, f"Expected at least 34 tiles, got {len(schema)}"

    def test_compute_tiles_present(self):
        schema = get_tile_library_schema()
        compute_names = ["map", "reduce", "scan", "filter", "zip", "flatmap", "sort", "unique"]
        for name in compute_names:
            assert name in schema, f"Missing compute tile: {name}"
            assert schema[name]["type"] == "COMPUTE"

    def test_memory_tiles_present(self):
        schema = get_tile_library_schema()
        memory_names = ["gather", "scatter", "stream", "copy", "fill", "transpose"]
        for name in memory_names:
            assert name in schema, f"Missing memory tile: {name}"
            assert schema[name]["type"] == "MEMORY"

    def test_control_tiles_present(self):
        schema = get_tile_library_schema()
        control_names = ["loop", "while", "branch", "switch", "fuse", "pipeline"]
        for name in control_names:
            assert name in schema, f"Missing control tile: {name}"
            assert schema[name]["type"] == "CONTROL"

    def test_a2a_tiles_present(self):
        schema = get_tile_library_schema()
        a2a_names = ["tell", "ask", "broadcast", "a2a_reduce", "a2a_scatter", "barrier"]
        for name in a2a_names:
            assert name in schema, f"Missing A2A tile: {name}"
            assert schema[name]["type"] == "A2A"

    def test_effect_tiles_present(self):
        schema = get_tile_library_schema()
        effect_names = ["print_effect", "log_effect", "state_mut"]
        for name in effect_names:
            assert name in schema, f"Missing effect tile: {name}"
            assert schema[name]["type"] == "EFFECT"

    def test_transform_tiles_present(self):
        schema = get_tile_library_schema()
        transform_names = ["cast", "reshape", "pack", "unpack", "join", "split"]
        for name in transform_names:
            assert name in schema, f"Missing transform tile: {name}"
            assert schema[name]["type"] == "TRANSFORM"

    def test_each_tile_has_required_fields(self):
        schema = get_tile_library_schema()
        required = ["name", "type", "inputs", "outputs", "params", "cost", "abstraction", "tags"]
        for name, tile in schema.items():
            for field in required:
                assert field in tile, f"Tile {name} missing field: {field}"

    def test_tile_costs_are_non_negative(self):
        schema = get_tile_library_schema()
        for name, tile in schema.items():
            assert tile["cost"] >= 0, f"Tile {name} has negative cost"

    def test_tile_abstraction_in_range(self):
        schema = get_tile_library_schema()
        for name, tile in schema.items():
            assert 0 <= tile["abstraction"] <= 10, (
                f"Tile {name} abstraction {tile['abstraction']} out of range [0,10]"
            )

    def test_tile_tags_are_non_empty(self):
        schema = get_tile_library_schema()
        for name, tile in schema.items():
            assert len(tile["tags"]) > 0, f"Tile {name} has no tags"


# ══════════════════════════════════════════════════════════════════════════
# Tile Search
# ══════════════════════════════════════════════════════════════════════════

class TestTileSearch:
    """Test tile search functionality."""

    def test_search_by_name(self):
        results = search_tiles("map")
        assert len(results) >= 1
        assert any(t["name"] == "map" for t in results)

    def test_search_by_tag(self):
        results = search_tiles("functional")
        assert len(results) >= 1
        assert all("functional" in t["tags"] for t in results)

    def test_search_by_type(self):
        results = search_tiles("memory")
        assert len(results) >= 1
        assert all(t["type"] in ("MEMORY",) for t in results)

    def test_search_no_results(self):
        results = search_tiles("zzzz_nonexistent_xyz")
        assert len(results) == 0

    def test_search_with_type_filter(self):
        results = search_tiles("a", tile_type="A2A")
        assert all(t["type"] == "A2A" for t in results)

    def test_search_with_abstraction_filter(self):
        results = search_tiles("data", min_abstraction=5, max_abstraction=8)
        for tile in results:
            assert 5 <= tile["abstraction"] <= 8

    def test_search_relevance_ordering(self):
        """Exact name match should rank higher than partial tag match."""
        results = search_tiles("reduce")
        names = [t["name"] for t in results]
        # "reduce" should be first (exact match)
        assert names[0] == "reduce"

    def test_search_case_insensitive(self):
        results_lower = search_tiles("filter")
        results_upper = search_tiles("FILTER")
        assert len(results_lower) == len(results_upper)


# ══════════════════════════════════════════════════════════════════════════
# Builder Schema
# ══════════════════════════════════════════════════════════════════════════

class TestBuilderSchema:
    """Test the builder extension schema."""

    def test_builder_schema_has_all_guides(self):
        schema = get_builder_schema()
        expected_guides = [
            "how_to_add_a_tile",
            "how_to_add_an_opcode",
            "how_to_add_a_language_frontend",
            "how_to_add_an_evolution_strategy",
            "how_to_add_a_module_granularity",
        ]
        for guide in expected_guides:
            assert guide in schema, f"Missing builder guide: {guide}"

    def test_each_guide_has_required_sections(self):
        schema = get_builder_schema()
        required = ["description", "steps", "constraints", "files_to_modify"]
        for name, guide in schema.items():
            for field in required:
                assert field in guide, f"Guide {name} missing field: {field}"

    def test_tile_guide_has_example(self):
        schema = get_builder_schema()
        assert "example" in schema["how_to_add_a_tile"]

    def test_opcode_guide_has_example(self):
        schema = get_builder_schema()
        assert "example" in schema["how_to_add_an_opcode"]

    def test_each_guide_has_multiple_steps(self):
        schema = get_builder_schema()
        for name, guide in schema.items():
            assert len(guide["steps"]) >= 3, f"Guide {name} has too few steps"

    def test_each_guide_has_constraints(self):
        schema = get_builder_schema()
        for name, guide in schema.items():
            assert len(guide["constraints"]) >= 2, f"Guide {name} has too few constraints"


# ══════════════════════════════════════════════════════════════════════════
# Open Questions
# ══════════════════════════════════════════════════════════════════════════

class TestOpenQuestions:
    """Test the open research questions list."""

    def test_has_10_questions(self):
        questions = get_open_questions()
        assert len(questions) == 10

    def test_each_question_has_required_fields(self):
        questions = get_open_questions()
        for q in questions:
            assert "id" in q
            assert "question" in q
            assert "detail" in q
            assert "difficulty" in q
            assert "area" in q

    def test_question_ids_are_unique(self):
        questions = get_open_questions()
        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids))

    def test_question_ids_sequential(self):
        questions = get_open_questions()
        ids = [q["id"] for q in questions]
        for i, qid in enumerate(ids, start=1):
            assert qid == f"Q{i}", f"Expected Q{i}, got {qid}"

    def test_difficulty_values_valid(self):
        questions = get_open_questions()
        valid_difficulties = {"easy", "medium", "hard", "very_hard"}
        for q in questions:
            assert q["difficulty"] in valid_difficulties, (
                f"Q{q['id']} has invalid difficulty: {q['difficulty']}"
            )

    def test_areas_covered(self):
        questions = get_open_questions()
        areas = {q["area"] for q in questions}
        expected_areas = {"theory", "design", "multi_agent", "optimization",
                          "verification", "learning", "bootstrap", "simulation"}
        for area in expected_areas:
            assert area in areas, f"Missing research area: {area}"

    def test_details_are_non_trivial(self):
        questions = get_open_questions()
        for q in questions:
            assert len(q["detail"]) >= 50, f"Q{q['id']} detail is too short"


# ══════════════════════════════════════════════════════════════════════════
# JSON Serialization
# ══════════════════════════════════════════════════════════════════════════

class TestJSONSerialization:
    """Test that all schemas can be serialized to JSON."""

    def test_architecture_serializes_to_json(self):
        arch = get_architecture_schema()
        json_str = json.dumps(arch, indent=2)
        assert "FLUX" in json_str
        assert "layers" in json_str

    def test_opcode_schema_serializes_to_json(self):
        schema = get_opcode_schema()
        json_str = json.dumps(schema, indent=2)
        assert "NOP" in json_str
        assert "IADD" in json_str

    def test_opcode_by_category_serializes_to_json(self):
        by_cat = get_opcodes_by_category()
        json_str = json.dumps(by_cat, indent=2)
        assert "control" in json_str

    def test_tile_schema_serializes_to_json(self):
        schema = get_tile_library_schema()
        json_str = json.dumps(schema, indent=2)
        assert "map" in json_str
        assert "reduce" in json_str

    def test_builder_schema_serializes_to_json(self):
        schema = get_builder_schema()
        json_str = json.dumps(schema, indent=2)
        assert "how_to_add_a_tile" in json_str

    def test_open_questions_serializes_to_json(self):
        questions = get_open_questions()
        json_str = json.dumps(questions, indent=2)
        assert "Q1" in json_str
        assert "Q10" in json_str

    def test_json_roundtrip_architecture(self):
        """Serialize and deserialize architecture without data loss."""
        arch = get_architecture_schema()
        json_str = json.dumps(arch)
        restored = json.loads(json_str)
        assert restored["name"] == arch["name"]
        assert len(restored["layers"]) == len(arch["layers"])

    def test_json_roundtrip_opcodes(self):
        """Serialize and deserialize opcode schema without data loss."""
        schema = get_opcode_schema()
        json_str = json.dumps(schema)
        restored = json.loads(json_str)
        assert len(restored) == len(schema)
        assert restored["IADD"]["value"] == schema["IADD"]["value"]

    def test_json_roundtrip_tiles(self):
        """Serialize and deserialize tile schema without data loss."""
        schema = get_tile_library_schema()
        json_str = json.dumps(schema)
        restored = json.loads(json_str)
        assert len(restored) == len(schema)
        assert restored["map"]["type"] == "COMPUTE"


# ══════════════════════════════════════════════════════════════════════════
# Schema Loading and Querying
# ══════════════════════════════════════════════════════════════════════════

class TestSchemaLoading:
    """Test schemas can be loaded and queried via package imports."""

    def test_import_from_package(self):
        from flux.schema import (
            get_architecture_schema,
            get_opcode_schema,
            get_tile_library_schema,
            get_builder_schema,
            get_open_questions,
        )
        assert callable(get_architecture_schema)
        assert callable(get_opcode_schema)
        assert callable(get_tile_library_schema)
        assert callable(get_builder_schema)
        assert callable(get_open_questions)

    def test_architecture_query_layer(self):
        arch = get_architecture_schema()
        vm_layer = next(l for l in arch["layers"] if l["id"] == "L3_VM")
        assert "Interpreter" in vm_layer["name"]

    def test_opcode_query_expensive(self):
        schema = get_opcode_schema()
        # A2A opcodes should be the most expensive
        max_cost = max(info["cost_ns"] for info in schema.values())
        expensive = [name for name, info in schema.items() if info["cost_ns"] == max_cost]
        assert "REDUCE" in expensive  # A2A reduce is very expensive

    def test_tile_query_most_expensive(self):
        schema = get_tile_library_schema()
        most_expensive = max(schema.values(), key=lambda t: t["cost"])
        assert most_expensive["name"] == "a2a_reduce"
        assert most_expensive["cost"] == 20.0

    def test_tile_query_least_expensive(self):
        schema = get_tile_library_schema()
        # Find tiles with cost > 0 (exclude zero-cost hypothetical)
        with_cost = [t for t in schema.values() if t["cost"] > 0]
        least_expensive = min(with_cost, key=lambda t: t["cost"])
        assert least_expensive["cost"] <= 0.5

    def test_dependency_graph_topological_order_exists(self):
        """Verify a topological ordering of modules is possible (DAG check)."""
        deps = get_module_dependencies()
        order = []
        visited = set()
        temp_visited = set()

        def visit(mod):
            if mod in temp_visited:
                return False  # cycle
            if mod in visited:
                return True
            temp_visited.add(mod)
            for dep in deps.get(mod, []):
                if not visit(dep):
                    return False
            temp_visited.discard(mod)
            visited.add(mod)
            order.append(mod)
            return True

        for mod in deps:
            temp_visited.clear()
            assert visit(mod), f"Cannot topologically sort: cycle involving {mod}"
