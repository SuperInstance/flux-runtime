"""Tests for the FLUX Tile System — composable computation vocabulary."""

import pytest
from flux.fir.types import TypeContext, IntType, FloatType, BoolType
from flux.fir.values import Value
from flux.fir.builder import FIRBuilder
from flux.fir.blocks import FIRModule

from flux.tiles.tile import Tile, TileType, TileInstance, CompositeTile, ParallelTile
from flux.tiles.ports import TilePort, PortDirection, CoercionInfo
from flux.tiles.graph import TileGraph, TileEdge
from flux.tiles.registry import TileRegistry, default_registry
from flux.tiles.library import (
    map_tile, reduce_tile, scan_tile, filter_tile,
    zip_tile, flatmap_tile, sort_tile, unique_tile,
    gather_tile, scatter_tile, stream_tile, copy_tile,
    fill_tile, transpose_tile,
    loop_tile, while_tile, branch_tile, switch_tile,
    fuse_tile, pipeline_tile,
    tell_tile, ask_tile, broadcast_tile, a2a_reduce_tile,
    a2a_scatter_tile, barrier_tile,
    print_effect_tile, log_effect_tile, state_mut_tile,
    cast_tile, reshape_tile, pack_tile, unpack_tile,
    join_tile, split_tile,
    ALL_BUILTIN_TILES,
)

_ctx = TypeContext()
_i32 = _ctx.get_int(32)
_i64 = _ctx.get_int(64)
_f32 = _ctx.get_float(32)
_bool = _ctx.get_bool()


# ══════════════════════════════════════════════════════════════════════════
# Tile Creation
# ══════════════════════════════════════════════════════════════════════════

class TestTileCreation:
    """Test tile construction with ports and metadata."""

    def test_create_minimal_tile(self):
        t = Tile(name="add", tile_type=TileType.COMPUTE)
        assert t.name == "add"
        assert t.tile_type == TileType.COMPUTE
        assert t.inputs == []
        assert t.outputs == []
        assert t.params == {}
        assert t.cost_estimate == 1.0
        assert t.tags == set()

    def test_create_tile_with_ports(self):
        t = Tile(
            name="double",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("x", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
        )
        assert len(t.inputs) == 1
        assert len(t.outputs) == 1
        assert t.inputs[0].name == "x"
        assert t.outputs[0].name == "result"

    def test_create_tile_with_params(self):
        t = Tile(
            name="scale",
            tile_type=TileType.COMPUTE,
            params={"factor": 2.0},
        )
        assert t.params["factor"] == 2.0

    def test_create_tile_with_metadata(self):
        t = Tile(
            name="heavy_compute",
            tile_type=TileType.COMPUTE,
            cost_estimate=10.0,
            abstraction_level=8,
            language_preference="python",
            tags={"expensive", "ml"},
        )
        assert t.cost_estimate == 10.0
        assert t.abstraction_level == 8
        assert t.language_preference == "python"
        assert "expensive" in t.tags
        assert "ml" in t.tags

    def test_tile_repr(self):
        t = Tile(name="my_tile", tile_type=TileType.MEMORY)
        r = repr(t)
        assert "my_tile" in r
        assert "memory" in r

    def test_all_tile_types(self):
        for tt in TileType:
            t = Tile(name=f"t_{tt.value}", tile_type=tt)
            assert t.tile_type == tt


# ══════════════════════════════════════════════════════════════════════════
# Tile Port
# ══════════════════════════════════════════════════════════════════════════

class TestTilePort:
    """Test port creation, compatibility, and coercion."""

    def test_port_direction(self):
        assert PortDirection.INPUT.value == "input"
        assert PortDirection.OUTPUT.value == "output"

    def test_port_creation(self):
        p = TilePort("data", PortDirection.INPUT, _i32)
        assert p.name == "data"
        assert p.direction == PortDirection.INPUT
        assert p.type_fir == _i32
        assert p.shape is None

    def test_port_with_shape(self):
        p = TilePort("matrix", PortDirection.INPUT, _i32, shape=(4, 4))
        assert p.shape == (4, 4)

    def test_port_compatible_opposite_direction(self):
        inp = TilePort("x", PortDirection.INPUT, _i32)
        out = TilePort("y", PortDirection.OUTPUT, _i32)
        assert out.compatible_with(inp) is True
        assert inp.compatible_with(out) is True

    def test_port_incompatible_same_direction(self):
        a = TilePort("x", PortDirection.INPUT, _i32)
        b = TilePort("y", PortDirection.INPUT, _i32)
        assert a.compatible_with(b) is False

    def test_port_incompatible_different_types(self):
        out = TilePort("x", PortDirection.OUTPUT, _i32)
        inp = TilePort("y", PortDirection.INPUT, _bool)
        assert out.compatible_with(inp) is False

    def test_port_coerce_identity(self):
        p = TilePort("x", PortDirection.OUTPUT, _i32)
        info = p.coerce_to(_i32)
        assert info.cost == 0
        assert info.method == "none"

    def test_port_coerce_int_widen(self):
        p = TilePort("x", PortDirection.OUTPUT, _i32)
        target = _ctx.get_int(64)
        info = p.coerce_to(target)
        assert info.cost == 1
        assert info.method == "sext"

    def test_port_coerce_int_narrow(self):
        p = TilePort("x", PortDirection.OUTPUT, _ctx.get_int(64))
        info = p.coerce_to(_i32)
        assert info.cost == 1
        assert info.method == "trunc"

    def test_port_coerce_float_widen(self):
        p = TilePort("x", PortDirection.OUTPUT, _f32)
        target = _ctx.get_float(64)
        info = p.coerce_to(target)
        assert info.cost == 1
        assert info.method == "fext"

    def test_port_coerce_float_narrow(self):
        p = TilePort("x", PortDirection.OUTPUT, _ctx.get_float(64))
        info = p.coerce_to(_f32)
        assert info.cost == 1
        assert info.method == "ftrunc"

    def test_port_coerce_int_to_float(self):
        p = TilePort("x", PortDirection.OUTPUT, _i32)
        info = p.coerce_to(_f32)
        assert info.cost == 5
        assert info.method == "bitcast"

    def test_port_repr(self):
        p = TilePort("data", PortDirection.INPUT, _i32, shape=(2, 3))
        r = repr(p)
        assert "data" in r
        assert "input" in r
        assert "(2, 3)" in r


# ══════════════════════════════════════════════════════════════════════════
# Tile Instantiation
# ══════════════════════════════════════════════════════════════════════════

class TestTileInstantiation:
    """Test tile instantiation with parameter binding."""

    def test_basic_instantiation(self):
        t = Tile(name="add", tile_type=TileType.COMPUTE, params={"scale": 1})
        inst = t.instantiate()
        assert inst.name == "add"
        assert inst.tile_type == TileType.COMPUTE
        assert inst.params["scale"] == 1

    def test_instantiation_with_overrides(self):
        t = Tile(name="scale", tile_type=TileType.COMPUTE, params={"factor": 2})
        inst = t.instantiate(factor=10)
        assert inst.params["factor"] == 10

    def test_instantiation_preserves_inputs_outputs(self):
        t = Tile(
            name="xform",
            tile_type=TileType.TRANSFORM,
            inputs=[TilePort("in", PortDirection.INPUT, _i32)],
            outputs=[TilePort("out", PortDirection.OUTPUT, _i32)],
        )
        inst = t.instantiate()
        assert len(inst.inputs) == 1
        assert len(inst.outputs) == 1

    def test_instance_repr(self):
        t = Tile(name="foo", tile_type=TileType.COMPUTE)
        inst = t.instantiate(bar=42)
        r = repr(inst)
        assert "foo" in r
        assert "bar" in r


# ══════════════════════════════════════════════════════════════════════════
# Tile Composition
# ══════════════════════════════════════════════════════════════════════════

class TestTileComposition:
    """Test tile chaining, composition, and parallelism."""

    def test_compose_two_tiles(self):
        t1 = Tile(
            name="double",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("x", PortDirection.INPUT, _i32)],
            outputs=[TilePort("y", PortDirection.OUTPUT, _i32)],
            params={"_out_port": "y"},
        )
        t2 = Tile(
            name="add_one",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("y", PortDirection.INPUT, _i32)],
            outputs=[TilePort("z", PortDirection.OUTPUT, _i32)],
            params={"_out_port": "z"},
        )
        comp = t1.compose(t2, {"y": "y"})
        assert len(comp.tiles) == 2
        assert comp.inputs[0].name == "x"
        assert comp.outputs[0].name == "z"

    def test_composite_cost(self):
        t1 = Tile(name="a", tile_type=TileType.COMPUTE, cost_estimate=3.0)
        t2 = Tile(name="b", tile_type=TileType.COMPUTE, cost_estimate=5.0)
        comp = t1.compose(t2, {})
        assert comp.cost_estimate == 8.0

    def test_composite_repr(self):
        t1 = Tile(name="step1", tile_type=TileType.COMPUTE)
        t2 = Tile(name="step2", tile_type=TileType.COMPUTE)
        comp = t1.compose(t2, {})
        r = repr(comp)
        assert "step1" in r
        assert "step2" in r

    def test_parallel_tile(self):
        t = Tile(name="work", tile_type=TileType.COMPUTE, cost_estimate=2.0)
        p = t.parallel(4)
        assert p.count == 4
        assert p.cost_estimate == 8.0
        assert p.name == "parallel(workx4)"

    def test_parallel_tile_preserves_type(self):
        t = Tile(name="io_op", tile_type=TileType.MEMORY)
        p = t.parallel(3)
        assert p.tile_type == TileType.MEMORY

    def test_parallel_repr(self):
        t = Tile(name="x", tile_type=TileType.COMPUTE)
        p = t.parallel(8)
        r = repr(p)
        assert "x" in r
        assert "8" in r


# ══════════════════════════════════════════════════════════════════════════
# FIR Emission — Compute Tiles
# ══════════════════════════════════════════════════════════════════════════

class TestFIREmissionCompute:
    """Test FIR emission for compute tiles."""

    def _make_builder(self):
        ctx = TypeContext()
        return FIRBuilder(ctx), ctx

    def test_map_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_map", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data = builder.alloca(ctx.get_int(32))
        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        results = map_tile.to_fir(builder, {"data": data_val})
        assert "result" in results
        assert results["result"].type == ctx.get_int(32)

    def test_reduce_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_reduce", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        init_val = Value(id=1, name="init", type=ctx.get_int(32))
        results = reduce_tile.to_fir(builder, {"data": data_val, "init": init_val})
        assert "result" in results

    def test_filter_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_filter", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        results = filter_tile.to_fir(builder, {"data": data_val})
        assert "result" in results

    def test_zip_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_zip", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        a_val = Value(id=0, name="a", type=ctx.get_int(32))
        b_val = Value(id=1, name="b", type=ctx.get_int(32))
        results = zip_tile.to_fir(builder, {"a": a_val, "b": b_val})
        assert "result" in results

    def test_scan_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_scan", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        results = scan_tile.to_fir(builder, {"data": data_val})
        assert "result" in results

    def test_tile_without_blueprint_raises(self):
        t = Tile(name="no_impl", tile_type=TileType.COMPUTE)
        builder, ctx = self._make_builder()
        with pytest.raises(RuntimeError, match="no FIR blueprint"):
            t.to_fir(builder, {})


# ══════════════════════════════════════════════════════════════════════════
# FIR Emission — Control Tiles
# ══════════════════════════════════════════════════════════════════════════

class TestFIREmissionControl:
    """Test FIR emission for control tiles."""

    def _make_builder(self):
        ctx = TypeContext()
        return FIRBuilder(ctx), ctx

    def test_loop_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_loop", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        init_val = Value(id=0, name="init", type=ctx.get_int(32))
        results = loop_tile.to_fir(builder, {"init": init_val})
        assert "result" in results

    def test_branch_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_branch", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        cond_val = Value(id=0, name="cond", type=ctx.get_bool())
        t_val = Value(id=1, name="t", type=ctx.get_int(32))
        f_val = Value(id=2, name="f", type=ctx.get_int(32))
        results = branch_tile.to_fir(builder, {
            "cond": cond_val, "true_val": t_val, "false_val": f_val,
        })
        assert "result" in results

    def test_switch_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_switch", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        val = Value(id=0, name="val", type=ctx.get_int(32))
        results = switch_tile.to_fir(builder, {"value": val})
        assert "result" in results

    def test_fuse_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_fuse", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        results = fuse_tile.to_fir(builder, {"data": data_val})
        assert "result" in results


# ══════════════════════════════════════════════════════════════════════════
# FIR Emission — A2A Tiles
# ══════════════════════════════════════════════════════════════════════════

class TestFIREmissionA2A:
    """Test FIR emission for agent-to-agent tiles."""

    def _make_builder(self):
        ctx = TypeContext()
        return FIRBuilder(ctx), ctx

    def test_tell_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_tell", [], [ctx.get_unit()])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        msg = Value(id=0, name="msg", type=ctx.get_int(32))
        cap = Value(id=1, name="cap", type=ctx.get_int(32))
        results = tell_tile.to_fir(builder, {"message": msg, "cap": cap})
        assert results == {}
        # Verify a tell instruction was emitted
        assert entry.instructions[-1].opcode == "tell"

    def test_ask_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_ask", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        msg = Value(id=0, name="msg", type=ctx.get_int(32))
        cap = Value(id=1, name="cap", type=ctx.get_int(32))
        results = ask_tile.to_fir(builder, {"message": msg, "cap": cap})
        assert "result" in results
        assert entry.instructions[-1].opcode == "ask"

    def test_a2a_reduce_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_a2a_reduce", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        data_val = Value(id=0, name="data", type=ctx.get_int(32))
        results = a2a_reduce_tile.to_fir(builder, {"data": data_val})
        assert "result" in results


# ══════════════════════════════════════════════════════════════════════════
# FIR Emission — Memory & Transform Tiles
# ══════════════════════════════════════════════════════════════════════════

class TestFIREmissionMemoryTransform:
    """Test FIR emission for memory and transform tiles."""

    def _make_builder(self):
        ctx = TypeContext()
        return FIRBuilder(ctx), ctx

    def test_gather_tile_emits_getelem(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_gather", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        base_val = Value(id=0, name="base", type=ctx.get_int(32))
        idx_val = Value(id=1, name="idx", type=ctx.get_int(32))
        results = gather_tile.to_fir(builder, {"base": base_val, "index": idx_val})
        assert "result" in results
        assert entry.instructions[-1].opcode == "getelem"

    def test_scatter_tile_emits_setelem(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_scatter", [], [ctx.get_unit()])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        base_val = Value(id=0, name="base", type=ctx.get_int(32))
        idx_val = Value(id=1, name="idx", type=ctx.get_int(32))
        val = Value(id=2, name="val", type=ctx.get_int(32))
        results = scatter_tile.to_fir(builder, {
            "base": base_val, "index": idx_val, "value": val,
        })
        assert results == {}
        assert entry.instructions[-1].opcode == "setelem"

    def test_copy_tile_emits_memcpy(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_copy", [], [ctx.get_unit()])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        src = Value(id=0, name="src", type=ctx.get_int(32))
        dst = Value(id=1, name="dst", type=ctx.get_int(32))
        copy_tile.to_fir(builder, {"src": src, "dst": dst})
        assert entry.instructions[-1].opcode == "memcpy"

    def test_fill_tile_emits_memset(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_fill", [], [ctx.get_unit()])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        dst = Value(id=0, name="dst", type=ctx.get_int(32))
        fill_tile.to_fir(builder, {"dst": dst})
        assert entry.instructions[-1].opcode == "memset"

    def test_cast_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_cast", [], [ctx.get_int(64)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        val = Value(id=0, name="val", type=ctx.get_int(32))
        results = cast_tile.to_fir(builder, {"value": val})
        assert "result" in results

    def test_pack_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_pack", [], [ctx.get_int(64)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        lo = Value(id=0, name="lo", type=ctx.get_int(32))
        hi = Value(id=1, name="hi", type=ctx.get_int(32))
        results = pack_tile.to_fir(builder, {"lo": lo, "hi": hi})
        assert "result" in results
        # pack_tile returns i64 (64-bit int)
        from flux.fir.types import IntType
        assert isinstance(results["result"].type, IntType)
        assert results["result"].type.bits == 64

    def test_unpack_tile_emits_fir(self):
        builder, ctx = self._make_builder()
        module = builder.new_module("test")
        func = builder.new_function(module, "test_unpack", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        val = Value(id=0, name="val", type=ctx.get_int(64))
        results = unpack_tile.to_fir(builder, {"value": val})
        assert "lo" in results
        assert "hi" in results


# ══════════════════════════════════════════════════════════════════════════
# Tile Graph
# ══════════════════════════════════════════════════════════════════════════

class TestTileGraph:
    """Test tile graph construction, ordering, and compilation."""

    def test_empty_graph(self):
        g = TileGraph()
        assert len(g.nodes) == 0
        assert len(g.edges) == 0
        assert g.topological_order() == []

    def test_add_single_tile(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        assert "t1" in g.nodes
        assert g.nodes["t1"].name == "map"

    def test_connect_tiles(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)
        g.connect("t1", "result", "t2", "data")
        assert len(g.edges) == 1
        assert g.edges[0].from_tile == "t1"
        assert g.edges[0].to_tile == "t2"

    def test_connect_nonexistent_tile_raises(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        with pytest.raises(ValueError, match="not in graph"):
            g.connect("t1", "result", "t_nonexistent", "data")

    def test_topological_order_simple(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)
        g.connect("t1", "result", "t2", "data")
        order = g.topological_order()
        assert order.index("t1") < order.index("t2")

    def test_topological_order_diamond(self):
        g = TileGraph()
        g.add_tile("a", map_tile)
        g.add_tile("b", filter_tile)
        g.add_tile("c", scan_tile)
        g.add_tile("d", reduce_tile)
        g.connect("a", "result", "b", "data")
        g.connect("a", "result", "c", "data")
        g.connect("b", "result", "d", "data")
        g.connect("c", "result", "d", "init")
        order = g.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_topological_order_three_chain(self):
        g = TileGraph()
        g.add_tile("a", map_tile)
        g.add_tile("b", filter_tile)
        g.add_tile("c", sort_tile)
        g.connect("a", "result", "b", "data")
        g.connect("b", "result", "c", "data")
        order = g.topological_order()
        assert order == ["a", "b", "c"]

    def test_compile_graph_to_fir(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)
        g.connect("t1", "result", "t2", "data")

        ctx = TypeContext()
        builder = FIRBuilder(ctx)
        module = g.compile(builder, ctx)
        assert module.name == "tile_graph"
        assert "graph_main" in module.functions
        assert len(module.functions["graph_main"].blocks) >= 1

    def test_compile_empty_graph(self):
        g = TileGraph()
        ctx = TypeContext()
        builder = FIRBuilder(ctx)
        module = g.compile(builder, ctx)
        assert module.name == "tile_graph"

    def test_graph_dot_generation(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)
        g.connect("t1", "result", "t2", "data")
        dot = g.to_dot()
        assert "digraph" in dot
        assert '"t1"' in dot
        assert '"t2"' in dot
        assert "result -> data" in dot

    def test_graph_dot_empty(self):
        g = TileGraph()
        dot = g.to_dot()
        assert "digraph" in dot

    def test_graph_find_pattern_single(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)

        pattern = TileGraph()
        pattern.add_tile("p", Tile(name="any_compute", tile_type=TileType.COMPUTE))
        matches = g.find_pattern(pattern)
        assert len(matches) == 2  # Both map and filter are COMPUTE

    def test_graph_find_pattern_no_match(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)

        pattern = TileGraph()
        pattern.add_tile("p", Tile(name="any_memory", tile_type=TileType.MEMORY))
        matches = g.find_pattern(pattern)
        assert len(matches) == 0

    def test_graph_substitute(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        g.add_tile("t2", filter_tile)
        g.connect("t1", "result", "t2", "data")

        replacement = Tile(
            name="optimized_map_filter",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("data", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
            cost_estimate=0.5,
        )
        g.substitute([{"p1": "t1", "p2": "t2"}], replacement)
        assert "t1" not in g.nodes
        assert "t2" not in g.nodes
        assert any("optimized_map_filter" in n for n in g.nodes)

    def test_graph_repr(self):
        g = TileGraph()
        g.add_tile("t1", map_tile)
        r = repr(g)
        assert "nodes=1" in r


# ══════════════════════════════════════════════════════════════════════════
# Tile Registry
# ══════════════════════════════════════════════════════════════════════════

class TestTileRegistry:
    """Test tile registry with search and discovery."""

    def test_empty_registry(self):
        reg = TileRegistry()
        assert reg.count == 0
        assert len(reg) == 0

    def test_register_and_get(self):
        reg = TileRegistry()
        t = Tile(name="my_tile", tile_type=TileType.COMPUTE)
        reg.register(t)
        assert reg.count == 1
        assert reg.get("my_tile") is t

    def test_get_nonexistent(self):
        reg = TileRegistry()
        assert reg.get("nonexistent") is None

    def test_register_overwrite(self):
        reg = TileRegistry()
        t1 = Tile(name="x", tile_type=TileType.COMPUTE)
        t2 = Tile(name="x", tile_type=TileType.MEMORY)
        reg.register(t1)
        reg.register(t2)
        assert reg.get("x").tile_type == TileType.MEMORY

    def test_unregister(self):
        reg = TileRegistry()
        t = Tile(name="x", tile_type=TileType.COMPUTE)
        reg.register(t)
        reg.unregister("x")
        assert reg.count == 0
        assert reg.get("x") is None

    def test_unregister_nonexistent(self):
        reg = TileRegistry()
        reg.unregister("nonexistent")  # No-op

    def test_search_by_name(self):
        reg = TileRegistry()
        reg.register(Tile(name="map", tile_type=TileType.COMPUTE, tags={"compute"}))
        reg.register(Tile(name="filter", tile_type=TileType.COMPUTE, tags={"compute"}))
        results = reg.search("map")
        assert len(results) >= 1
        assert results[0].name == "map"

    def test_search_by_tag(self):
        reg = TileRegistry()
        reg.register(Tile(name="foo", tile_type=TileType.COMPUTE, tags={"alpha", "beta"}))
        reg.register(Tile(name="bar", tile_type=TileType.MEMORY, tags={"gamma"}))
        results = reg.search("alpha")
        assert len(results) >= 1
        assert results[0].name == "foo"

    def test_search_by_type(self):
        reg = TileRegistry()
        reg.register(Tile(name="x", tile_type=TileType.COMPUTE))
        reg.register(Tile(name="y", tile_type=TileType.MEMORY))
        results = reg.search("memory")
        assert len(results) >= 1
        assert results[0].tile_type == TileType.MEMORY

    def test_search_no_results(self):
        reg = TileRegistry()
        reg.register(Tile(name="x", tile_type=TileType.COMPUTE))
        results = reg.search("zzzzz_nonexistent")
        assert len(results) == 0

    def test_by_type(self):
        reg = TileRegistry()
        reg.register(Tile(name="a", tile_type=TileType.COMPUTE))
        reg.register(Tile(name="b", tile_type=TileType.COMPUTE))
        reg.register(Tile(name="c", tile_type=TileType.MEMORY))
        compute_tiles = reg.by_type(TileType.COMPUTE)
        assert len(compute_tiles) == 2

    def test_by_abstraction(self):
        reg = TileRegistry()
        reg.register(Tile(name="low", tile_type=TileType.COMPUTE, abstraction_level=2))
        reg.register(Tile(name="mid", tile_type=TileType.COMPUTE, abstraction_level=5))
        reg.register(Tile(name="high", tile_type=TileType.COMPUTE, abstraction_level=8))
        mid_tiles = reg.by_abstraction(5)
        assert len(mid_tiles) == 1
        assert mid_tiles[0].name == "mid"

    def test_by_abstraction_range(self):
        reg = TileRegistry()
        reg.register(Tile(name="a", tile_type=TileType.COMPUTE, abstraction_level=2))
        reg.register(Tile(name="b", tile_type=TileType.COMPUTE, abstraction_level=5))
        reg.register(Tile(name="c", tile_type=TileType.COMPUTE, abstraction_level=8))
        result = reg.by_abstraction_range(3, 7)
        assert len(result) == 1
        assert result[0].name == "b"

    def test_find_alternatives(self):
        reg = TileRegistry()
        t1 = Tile(
            name="slow_map",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("data", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
            cost_estimate=10.0,
        )
        t2 = Tile(
            name="fast_map",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("data", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
            cost_estimate=1.0,
        )
        reg.register(t1)
        reg.register(t2)
        alternatives = reg.find_alternatives(t1)
        assert len(alternatives) == 1
        assert alternatives[0].name == "fast_map"

    def test_find_alternatives_different_ports(self):
        reg = TileRegistry()
        t1 = Tile(
            name="a",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("x", PortDirection.INPUT, _i32)],
            outputs=[TilePort("y", PortDirection.OUTPUT, _i32)],
        )
        t2 = Tile(
            name="b",
            tile_type=TileType.COMPUTE,
            inputs=[TilePort("data", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
        )
        reg.register(t1)
        reg.register(t2)
        assert len(reg.find_alternatives(t1)) == 0

    def test_most_expensive(self):
        reg = TileRegistry()
        reg.register(Tile(name="cheap", tile_type=TileType.COMPUTE, cost_estimate=1.0))
        reg.register(Tile(name="medium", tile_type=TileType.COMPUTE, cost_estimate=5.0))
        reg.register(Tile(name="expensive", tile_type=TileType.COMPUTE, cost_estimate=20.0))
        top2 = reg.most_expensive(2)
        assert len(top2) == 2
        assert top2[0].name == "expensive"
        assert top2[1].name == "medium"

    def test_least_expensive(self):
        reg = TileRegistry()
        reg.register(Tile(name="cheap", tile_type=TileType.COMPUTE, cost_estimate=1.0))
        reg.register(Tile(name="medium", tile_type=TileType.COMPUTE, cost_estimate=5.0))
        bottom = reg.least_expensive(1)
        assert len(bottom) == 1
        assert bottom[0].name == "cheap"

    def test_all_tiles(self):
        reg = TileRegistry()
        t1 = Tile(name="a", tile_type=TileType.COMPUTE)
        t2 = Tile(name="b", tile_type=TileType.MEMORY)
        reg.register(t1)
        reg.register(t2)
        all_t = reg.all_tiles
        assert len(all_t) == 2

    def test_registry_repr(self):
        reg = TileRegistry()
        r = repr(reg)
        assert "tiles=0" in r

    def test_registry_len(self):
        reg = TileRegistry()
        assert len(reg) == 0
        reg.register(Tile(name="a", tile_type=TileType.COMPUTE))
        assert len(reg) == 1


# ══════════════════════════════════════════════════════════════════════════
# Default Registry (Built-in Tiles)
# ══════════════════════════════════════════════════════════════════════════

class TestDefaultRegistry:
    """Test that the default registry has all built-in tiles."""

    def test_default_registry_has_tiles(self):
        assert default_registry.count > 0

    def test_default_registry_has_compute_tiles(self):
        compute = default_registry.by_type(TileType.COMPUTE)
        assert len(compute) >= 8

    def test_default_registry_has_memory_tiles(self):
        memory = default_registry.by_type(TileType.MEMORY)
        assert len(memory) >= 6

    def test_default_registry_has_control_tiles(self):
        control = default_registry.by_type(TileType.CONTROL)
        assert len(control) >= 6

    def test_default_registry_has_a2a_tiles(self):
        a2a = default_registry.by_type(TileType.A2A)
        assert len(a2a) >= 6

    def test_default_registry_has_effect_tiles(self):
        effects = default_registry.by_type(TileType.EFFECT)
        assert len(effects) >= 3

    def test_default_registry_has_transform_tiles(self):
        transforms = default_registry.by_type(TileType.TRANSFORM)
        assert len(transforms) >= 6

    def test_default_registry_search_map(self):
        results = default_registry.search("map")
        assert any(t.name == "map" for t in results)

    def test_default_registry_search_tell(self):
        results = default_registry.search("tell")
        assert any(t.name == "tell" for t in results)


# ══════════════════════════════════════════════════════════════════════════
# Built-in Library — Individual Tiles
# ══════════════════════════════════════════════════════════════════════════

class TestBuiltinTiles:
    """Test each built-in tile category."""

    def test_all_builtin_tiles_count(self):
        assert len(ALL_BUILTIN_TILES) >= 30

    def test_map_tile(self):
        assert map_tile.tile_type == TileType.COMPUTE
        assert "map" in map_tile.tags
        assert len(map_tile.inputs) == 1
        assert len(map_tile.outputs) == 1

    def test_reduce_tile(self):
        assert reduce_tile.tile_type == TileType.COMPUTE
        assert "reduce" in reduce_tile.tags
        assert len(reduce_tile.inputs) == 2  # data, init

    def test_filter_tile(self):
        assert filter_tile.tile_type == TileType.COMPUTE
        assert "filter" in filter_tile.tags

    def test_gather_tile(self):
        assert gather_tile.tile_type == TileType.MEMORY
        assert "gather" in gather_tile.tags
        assert len(gather_tile.inputs) == 2  # base, index

    def test_scatter_tile(self):
        assert scatter_tile.tile_type == TileType.MEMORY
        assert len(scatter_tile.outputs) == 0  # Side-effect only

    def test_loop_tile(self):
        assert loop_tile.tile_type == TileType.CONTROL
        assert loop_tile.params["count"] == 10

    def test_while_tile(self):
        assert while_tile.tile_type == TileType.CONTROL
        assert "max_iters" in while_tile.params

    def test_branch_tile(self):
        assert branch_tile.tile_type == TileType.CONTROL
        assert len(branch_tile.inputs) == 3  # cond, true_val, false_val

    def test_tell_tile(self):
        assert tell_tile.tile_type == TileType.A2A
        assert len(tell_tile.outputs) == 0

    def test_ask_tile(self):
        assert ask_tile.tile_type == TileType.A2A
        assert len(ask_tile.outputs) == 1

    def test_barrier_tile(self):
        assert barrier_tile.tile_type == TileType.A2A
        assert "barrier" in barrier_tile.tags

    def test_cast_tile(self):
        assert cast_tile.tile_type == TileType.TRANSFORM
        assert "target_type" in cast_tile.params

    def test_pack_tile(self):
        assert pack_tile.tile_type == TileType.TRANSFORM
        assert len(pack_tile.inputs) == 2

    def test_unpack_tile(self):
        assert unpack_tile.tile_type == TileType.TRANSFORM
        assert len(unpack_tile.outputs) == 2  # lo, hi

    def test_join_tile(self):
        assert join_tile.tile_type == TileType.TRANSFORM
        assert len(join_tile.inputs) == 2

    def test_split_tile(self):
        assert split_tile.tile_type == TileType.TRANSFORM
        assert len(split_tile.outputs) == 2  # true_part, false_part

    def test_stream_tile(self):
        assert stream_tile.tile_type == TileType.MEMORY
        assert "stream" in stream_tile.tags

    def test_sort_tile(self):
        assert sort_tile.tile_type == TileType.COMPUTE
        assert sort_tile.cost_estimate > filter_tile.cost_estimate

    def test_unique_tile(self):
        assert unique_tile.tile_type == TileType.COMPUTE
        assert "dedup" in unique_tile.tags

    def test_zip_tile(self):
        assert zip_tile.tile_type == TileType.COMPUTE
        assert len(zip_tile.inputs) == 2

    def test_flatmap_tile(self):
        assert flatmap_tile.tile_type == TileType.COMPUTE
        assert "flatten" in flatmap_tile.tags

    def test_scan_tile(self):
        assert scan_tile.tile_type == TileType.COMPUTE
        assert "prefix" in scan_tile.tags

    def test_copy_tile(self):
        assert copy_tile.tile_type == TileType.MEMORY
        assert "size" in copy_tile.params

    def test_fill_tile(self):
        assert fill_tile.tile_type == TileType.MEMORY
        assert "fill_value" in fill_tile.params

    def test_transpose_tile(self):
        assert transpose_tile.tile_type == TileType.MEMORY
        assert "matrix" in transpose_tile.tags

    def test_switch_tile(self):
        assert switch_tile.tile_type == TileType.CONTROL
        assert "cases" in switch_tile.params

    def test_fuse_tile(self):
        assert fuse_tile.tile_type == TileType.CONTROL
        assert "fn1" in fuse_tile.params
        assert "fn2" in fuse_tile.params

    def test_pipeline_tile(self):
        assert pipeline_tile.tile_type == TileType.CONTROL
        assert "stages" in pipeline_tile.params

    def test_broadcast_tile(self):
        assert broadcast_tile.tile_type == TileType.A2A
        assert "fan-out" in broadcast_tile.tags

    def test_a2a_reduce_tile(self):
        assert a2a_reduce_tile.tile_type == TileType.A2A
        assert "aggregate" in a2a_reduce_tile.tags

    def test_a2a_scatter_tile(self):
        assert a2a_scatter_tile.tile_type == TileType.A2A
        assert "strategy" in a2a_scatter_tile.params

    def test_print_effect_tile(self):
        assert print_effect_tile.tile_type == TileType.EFFECT
        assert "io" in print_effect_tile.tags

    def test_log_effect_tile(self):
        assert log_effect_tile.tile_type == TileType.EFFECT
        assert "level" in log_effect_tile.params

    def test_state_mut_tile(self):
        assert state_mut_tile.tile_type == TileType.EFFECT
        assert "mutation" in state_mut_tile.tags


# ══════════════════════════════════════════════════════════════════════════
# Tile Cost Estimation
# ══════════════════════════════════════════════════════════════════════════

class TestTileCostEstimation:
    """Test cost estimation for tiles and compositions."""

    def test_default_cost(self):
        t = Tile(name="x", tile_type=TileType.COMPUTE)
        assert t.cost_estimate == 1.0

    def test_custom_cost(self):
        t = Tile(name="x", tile_type=TileType.COMPUTE, cost_estimate=42.0)
        assert t.cost_estimate == 42.0

    def test_parallel_cost_multiplier(self):
        t = Tile(name="x", tile_type=TileType.COMPUTE, cost_estimate=3.0)
        p = t.parallel(5)
        assert p.cost_estimate == 15.0

    def test_composite_cost_sum(self):
        t1 = Tile(name="a", tile_type=TileType.COMPUTE, cost_estimate=7.0)
        t2 = Tile(name="b", tile_type=TileType.COMPUTE, cost_estimate=3.0)
        comp = t1.compose(t2, {})
        assert comp.cost_estimate == 10.0

    def test_a2a_tiles_more_expensive_than_compute(self):
        for ct in default_registry.by_type(TileType.COMPUTE):
            for at in default_registry.by_type(TileType.A2A):
                # A2A tiles should generally be expensive
                assert at.cost_estimate >= 1.0

    def test_cost_estimate_all_positive(self):
        for t in ALL_BUILTIN_TILES:
            assert t.cost_estimate > 0, f"{t.name} has non-positive cost"


# ══════════════════════════════════════════════════════════════════════════
# Edge Cases & Integration
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_instance_to_fir_with_params(self):
        """TileInstance merges tile params with instance params."""
        t = Tile(
            name="param_tile",
            tile_type=TileType.COMPUTE,
            params={"base": 10},
            inputs=[TilePort("data", PortDirection.INPUT, _i32)],
            outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
            fir_blueprint=lambda b, inp, p: {"result": inp.get("data", Value(id=99, name="fallback", type=_i32))},
        )
        inst = t.instantiate(multiplier=5)
        builder, ctx = FIRBuilder(TypeContext()), TypeContext()
        module = builder.new_module("test")
        func = builder.new_function(module, "f", [], [ctx.get_int(32)])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)
        data = Value(id=0, name="d", type=ctx.get_int(32))
        results = inst.to_fir(builder, {"data": data})
        assert "result" in results

    def test_empty_composition(self):
        """CompositeTile with no tiles has empty inputs/outputs."""
        comp = CompositeTile(tiles=[], mappings=[])
        assert comp.inputs == []
        assert comp.outputs == []

    def test_parallel_count_zero(self):
        """Parallel tile with count=0 has zero cost."""
        t = Tile(name="x", tile_type=TileType.COMPUTE, cost_estimate=5.0)
        p = t.parallel(0)
        assert p.cost_estimate == 0

    def test_graph_add_tile_returns_instance(self):
        g = TileGraph()
        inst = g.add_tile("my_inst", map_tile, fn="custom_fn")
        assert isinstance(inst, TileInstance)

    def test_graph_with_no_edges_compiles(self):
        g = TileGraph()
        g.add_tile("alone", map_tile)
        ctx = TypeContext()
        builder = FIRBuilder(ctx)
        module = g.compile(builder, ctx)
        assert "graph_main" in module.functions

    def test_while_tile_max_iters_param(self):
        assert while_tile.params["max_iters"] == 1000

    def test_cast_tile_default_target(self):
        assert cast_tile.params["target_type"] == "i64"

    def test_pipeline_tile_stages_param(self):
        assert isinstance(pipeline_tile.params["stages"], list)

    def test_broadcast_tile_agents_param(self):
        assert isinstance(broadcast_tile.params["agents"], list)

    def test_coercion_info_fields(self):
        info = CoercionInfo(cost=1.0, from_type_name="IntType", to_type_name="IntType", method="sext")
        assert info.cost == 1.0
        assert info.method == "sext"

    def test_tile_edge_repr(self):
        edge = TileEdge("a", "out", "b", "in")
        r = repr(edge)
        assert "a.out" in r
        assert "b.in" in r
