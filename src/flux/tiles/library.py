"""Tile Library — built-in tile definitions for all categories."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ..fir.types import TypeContext, BoolType, UnitType, IntType
from ..fir.values import Value
from ..fir.builder import FIRBuilder
from .tile import Tile, TileType
from .ports import TilePort, PortDirection

if TYPE_CHECKING:
    pass


# ── Helper: create TypeContext lazily ──────────────────────────────────────

_ctx = TypeContext()

# Common types
_i32 = _ctx.get_int(32)
_i64 = _ctx.get_int(64)
_f32 = _ctx.get_float(32)
_f64 = _ctx.get_float(64)
_bool = _ctx.get_bool()
_unit = _ctx.get_unit()


# ── Helper: default FIR blueprint for tiles that just call a runtime function ──

def _call_runtime_tile(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
    fn_name: str,
    return_type: Any,
) -> dict[str, Value]:
    """Emit a call to a runtime function."""
    args = [inputs[k] for k in sorted(inputs.keys())]
    result = builder.call(fn_name, args, return_type)
    if result is not None:
        out_port = params.get("_out_port", "result")
        return {out_port: result}
    return {}


# ══════════════════════════════════════════════════════════════════════════
# COMPUTE TILES
# ══════════════════════════════════════════════════════════════════════════

def _map_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Map: apply a function to each element of a list."""
    data = inputs.get("data")
    fn = params.get("fn", "_map_fn")
    # Emit: result = call fn with each element (simplified to a runtime call)
    result = builder.call(fn, [data] if data else [], _i32)
    return {"result": result}


map_tile = Tile(
    name="map",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn": "_map_fn"},
    fir_blueprint=_map_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=6,
    tags={"compute", "map", "functional", "element-wise"},
)


def _reduce_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Reduce: fold a sequence to a single value."""
    data = inputs.get("data")
    init = inputs.get("init")
    fn = params.get("fn", "_reduce_fn")
    args = [data, init] if data and init else [data] if data else []
    result = builder.call(fn, args, _i32)
    return {"result": result}


reduce_tile = Tile(
    name="reduce",
    tile_type=TileType.COMPUTE,
    inputs=[
        TilePort("data", PortDirection.INPUT, _i32),
        TilePort("init", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn": "_reduce_fn", "op": "add"},
    fir_blueprint=_reduce_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=6,
    tags={"compute", "reduce", "fold", "aggregate"},
)


def _scan_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Scan: prefix scan (cumulative operation)."""
    data = inputs.get("data")
    fn = params.get("fn", "_scan_fn")
    args = [data] if data else []
    result = builder.call(fn, args, _i32)
    return {"result": result}


scan_tile = Tile(
    name="scan",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn": "_scan_fn", "op": "add", "inclusive": True},
    fir_blueprint=_scan_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=6,
    tags={"compute", "scan", "prefix", "cumulative"},
)


def _filter_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Filter: keep elements matching predicate."""
    data = inputs.get("data")
    predicate = params.get("predicate", "_filter_pred")
    result = builder.call(predicate, [data] if data else [], _i32)
    return {"result": result}


filter_tile = Tile(
    name="filter",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"predicate": "_filter_pred"},
    fir_blueprint=_filter_fir_blueprint,
    cost_estimate=1.5,
    abstraction_level=6,
    tags={"compute", "filter", "predicate"},
)


def _zip_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Zip: combine two sequences element-wise."""
    a = inputs.get("a")
    b = inputs.get("b")
    fn = params.get("fn", "_zip_fn")
    args = [a, b] if a and b else []
    result = builder.call(fn, args, _i32)
    return {"result": result}


zip_tile = Tile(
    name="zip",
    tile_type=TileType.COMPUTE,
    inputs=[
        TilePort("a", PortDirection.INPUT, _i32),
        TilePort("b", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn": "_zip_fn"},
    fir_blueprint=_zip_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=6,
    tags={"compute", "zip", "combine", "element-wise"},
)


def _flatmap_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Flatmap: map then flatten."""
    data = inputs.get("data")
    fn = params.get("fn", "_flatmap_fn")
    result = builder.call(fn, [data] if data else [], _i32)
    return {"result": result}


flatmap_tile = Tile(
    name="flatmap",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn": "_flatmap_fn"},
    fir_blueprint=_flatmap_fir_blueprint,
    cost_estimate=1.5,
    abstraction_level=7,
    tags={"compute", "flatmap", "map", "flatten"},
)


def _sort_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Sort: sort a sequence."""
    data = inputs.get("data")
    comparator = params.get("comparator", "_sort_cmp")
    result = builder.call(comparator, [data] if data else [], _i32)
    return {"result": result}


sort_tile = Tile(
    name="sort",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"comparator": "_sort_cmp", "order": "asc"},
    fir_blueprint=_sort_fir_blueprint,
    cost_estimate=5.0,
    abstraction_level=6,
    tags={"compute", "sort", "ordering"},
)


def _unique_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Unique: deduplicate elements."""
    data = inputs.get("data")
    result = builder.call("_unique_fn", [data] if data else [], _i32)
    return {"result": result}


unique_tile = Tile(
    name="unique",
    tile_type=TileType.COMPUTE,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={},
    fir_blueprint=_unique_fir_blueprint,
    cost_estimate=3.0,
    abstraction_level=6,
    tags={"compute", "unique", "dedup", "set"},
)


# ══════════════════════════════════════════════════════════════════════════
# MEMORY TILES
# ══════════════════════════════════════════════════════════════════════════

def _gather_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Gather: random-access read from indices."""
    base = inputs.get("base")
    index = inputs.get("index")
    if base and index:
        result = builder.getelem(base, index, _i32)
        return {"result": result}
    return {}


gather_tile = Tile(
    name="gather",
    tile_type=TileType.MEMORY,
    inputs=[
        TilePort("base", PortDirection.INPUT, _i32),
        TilePort("index", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={},
    fir_blueprint=_gather_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=3,
    tags={"memory", "gather", "random-access", "read"},
)


def _scatter_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Scatter: random-access write at indices."""
    base = inputs.get("base")
    index = inputs.get("index")
    value = inputs.get("value")
    if base and index and value:
        builder.setelem(base, index, value)
    return {}


scatter_tile = Tile(
    name="scatter",
    tile_type=TileType.MEMORY,
    inputs=[
        TilePort("base", PortDirection.INPUT, _i32),
        TilePort("index", PortDirection.INPUT, _i32),
        TilePort("value", PortDirection.INPUT, _i32),
    ],
    outputs=[],
    params={},
    fir_blueprint=_scatter_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=3,
    tags={"memory", "scatter", "random-access", "write"},
)


def _stream_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Stream: sequential read/write."""
    base = inputs.get("base")
    offset = inputs.get("offset", None)
    if base:
        result = builder.load(_i32, base, params.get("base_offset", 0))
        return {"result": result}
    return {}


stream_tile = Tile(
    name="stream",
    tile_type=TileType.MEMORY,
    inputs=[
        TilePort("base", PortDirection.INPUT, _i32),
        TilePort("offset", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"base_offset": 0, "direction": "read"},
    fir_blueprint=_stream_fir_blueprint,
    cost_estimate=0.5,
    abstraction_level=3,
    tags={"memory", "stream", "sequential", "io"},
)


def _copy_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Copy: bulk memory copy."""
    src = inputs.get("src")
    dst = inputs.get("dst")
    if src and dst:
        builder.memcpy(src, dst, params.get("size", 64))
    return {}


copy_tile = Tile(
    name="copy",
    tile_type=TileType.MEMORY,
    inputs=[
        TilePort("src", PortDirection.INPUT, _i32),
        TilePort("dst", PortDirection.INPUT, _i32),
    ],
    outputs=[],
    params={"size": 64},
    fir_blueprint=_copy_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=2,
    tags={"memory", "copy", "bulk", "memcpy"},
)


def _fill_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Fill: fill a memory region with a value."""
    dst = inputs.get("dst")
    if dst:
        builder.memset(dst, params.get("fill_value", 0), params.get("size", 64))
    return {}


fill_tile = Tile(
    name="fill",
    tile_type=TileType.MEMORY,
    inputs=[TilePort("dst", PortDirection.INPUT, _i32)],
    outputs=[],
    params={"fill_value": 0, "size": 64},
    fir_blueprint=_fill_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=2,
    tags={"memory", "fill", "memset", "initialize"},
)


def _transpose_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Transpose: matrix transpose."""
    data = inputs.get("data")
    result = builder.call("_transpose_fn", [data] if data else [], _i32)
    return {"result": result}


transpose_tile = Tile(
    name="transpose",
    tile_type=TileType.MEMORY,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"rows": 0, "cols": 0},
    fir_blueprint=_transpose_fir_blueprint,
    cost_estimate=4.0,
    abstraction_level=4,
    tags={"memory", "transpose", "matrix", "layout"},
)


# ══════════════════════════════════════════════════════════════════════════
# CONTROL TILES
# ══════════════════════════════════════════════════════════════════════════

def _loop_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Loop: fixed-count iteration."""
    count = params.get("count", 10)
    body_fn = params.get("body", "_loop_body")
    init = inputs.get("init")
    if init:
        result = builder.call(body_fn, [init], _i32)
        return {"result": result}
    return {}


loop_tile = Tile(
    name="loop",
    tile_type=TileType.CONTROL,
    inputs=[TilePort("init", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"count": 10, "body": "_loop_body"},
    fir_blueprint=_loop_fir_blueprint,
    cost_estimate=3.0,
    abstraction_level=4,
    tags={"control", "loop", "iteration", "fixed-count"},
)


def _while_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """While: condition-based iteration."""
    init = inputs.get("init")
    cond_fn = params.get("cond", "_while_cond")
    body_fn = params.get("body", "_while_body")
    if init:
        result = builder.call(body_fn, [init], _i32)
        return {"result": result}
    return {}


while_tile = Tile(
    name="while",
    tile_type=TileType.CONTROL,
    inputs=[TilePort("init", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"cond": "_while_cond", "body": "_while_body", "max_iters": 1000},
    fir_blueprint=_while_fir_blueprint,
    cost_estimate=4.0,
    abstraction_level=4,
    tags={"control", "while", "loop", "condition"},
)


def _branch_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Branch: conditional execution."""
    cond = inputs.get("cond")
    true_val = inputs.get("true_val")
    false_val = inputs.get("false_val")
    if cond and true_val and false_val:
        # Use a call to simulate branch
        result = builder.call("_branch_fn", [cond, true_val, false_val], _i32)
        return {"result": result}
    return {}


branch_tile = Tile(
    name="branch",
    tile_type=TileType.CONTROL,
    inputs=[
        TilePort("cond", PortDirection.INPUT, _bool),
        TilePort("true_val", PortDirection.INPUT, _i32),
        TilePort("false_val", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={},
    fir_blueprint=_branch_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=4,
    tags={"control", "branch", "conditional", "if-else"},
)


def _switch_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Switch: multi-way dispatch."""
    value = inputs.get("value")
    default_fn = params.get("default", "_switch_default")
    if value:
        result = builder.call(default_fn, [value], _i32)
        return {"result": result}
    return {}


switch_tile = Tile(
    name="switch",
    tile_type=TileType.CONTROL,
    inputs=[TilePort("value", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"cases": {}, "default": "_switch_default"},
    fir_blueprint=_switch_fir_blueprint,
    cost_estimate=1.5,
    abstraction_level=4,
    tags={"control", "switch", "dispatch", "multi-way"},
)


def _fuse_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Fuse: loop fusion (combine two loops into one)."""
    data = inputs.get("data")
    fn1 = params.get("fn1", "_fuse_fn1")
    fn2 = params.get("fn2", "_fuse_fn2")
    if data:
        r1 = builder.call(fn1, [data], _i32)
        r2 = builder.call(fn2, [r1], _i32)
        return {"result": r2}
    return {}


fuse_tile = Tile(
    name="fuse",
    tile_type=TileType.CONTROL,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"fn1": "_fuse_fn1", "fn2": "_fuse_fn2"},
    fir_blueprint=_fuse_fir_blueprint,
    cost_estimate=2.5,
    abstraction_level=5,
    tags={"control", "fuse", "optimization", "loop-fusion"},
)


def _pipeline_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Pipeline: software pipelining."""
    data = inputs.get("data")
    stages = params.get("stages", ["_pipe_s1"])
    if data:
        result_val = data
        for stage in stages:
            result_val = builder.call(stage, [result_val], _i32)
        return {"result": result_val}
    return {}


pipeline_tile = Tile(
    name="pipeline",
    tile_type=TileType.CONTROL,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"stages": ["_pipe_s1"]},
    fir_blueprint=_pipeline_fir_blueprint,
    cost_estimate=3.0,
    abstraction_level=5,
    tags={"control", "pipeline", "software-pipelining", "optimization"},
)


# ══════════════════════════════════════════════════════════════════════════
# A2A TILES
# ══════════════════════════════════════════════════════════════════════════

def _tell_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Tell: send message to agent."""
    message = inputs.get("message")
    cap = inputs.get("cap")
    target = params.get("target", "_default_agent")
    if message and cap:
        builder.tell(target, message, cap)
    return {}


tell_tile = Tile(
    name="tell",
    tile_type=TileType.A2A,
    inputs=[
        TilePort("message", PortDirection.INPUT, _i32),
        TilePort("cap", PortDirection.INPUT, _i32),
    ],
    outputs=[],
    params={"target": "_default_agent"},
    fir_blueprint=_tell_fir_blueprint,
    cost_estimate=5.0,
    abstraction_level=7,
    tags={"a2a", "tell", "send", "message", "fire-and-forget"},
)


def _ask_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Ask: request-response with agent."""
    message = inputs.get("message")
    cap = inputs.get("cap")
    target = params.get("target", "_default_agent")
    if message and cap:
        result = builder.ask(target, message, _i32, cap)
        return {"result": result}
    return {}


ask_tile = Tile(
    name="ask",
    tile_type=TileType.A2A,
    inputs=[
        TilePort("message", PortDirection.INPUT, _i32),
        TilePort("cap", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"target": "_default_agent"},
    fir_blueprint=_ask_fir_blueprint,
    cost_estimate=10.0,
    abstraction_level=7,
    tags={"a2a", "ask", "request", "response", "rpc"},
)


def _broadcast_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Broadcast: send to all agents."""
    message = inputs.get("message")
    cap = inputs.get("cap")
    if message and cap:
        builder.tell("_broadcast", message, cap)
    return {}


broadcast_tile = Tile(
    name="broadcast",
    tile_type=TileType.A2A,
    inputs=[
        TilePort("message", PortDirection.INPUT, _i32),
        TilePort("cap", PortDirection.INPUT, _i32),
    ],
    outputs=[],
    params={"agents": []},
    fir_blueprint=_broadcast_fir_blueprint,
    cost_estimate=15.0,
    abstraction_level=7,
    tags={"a2a", "broadcast", "send-all", "fan-out"},
)


def _a2a_reduce_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """A2A Reduce: collect results from all agents."""
    data = inputs.get("data")
    if data:
        result = builder.call("_a2a_reduce_fn", [data], _i32)
        return {"result": result}
    return {}


a2a_reduce_tile = Tile(
    name="a2a_reduce",
    tile_type=TileType.A2A,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"op": "sum", "agents": []},
    fir_blueprint=_a2a_reduce_fir_blueprint,
    cost_estimate=20.0,
    abstraction_level=7,
    tags={"a2a", "reduce", "collect", "gather", "aggregate"},
)


def _a2a_scatter_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """A2A Scatter: distribute work across agents."""
    data = inputs.get("data")
    if data:
        builder.tell("_scatter_master", data, data)  # reuse as cap
    return {}


a2a_scatter_tile = Tile(
    name="a2a_scatter",
    tile_type=TileType.A2A,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[],
    params={"agents": [], "strategy": "round-robin"},
    fir_blueprint=_a2a_scatter_fir_blueprint,
    cost_estimate=10.0,
    abstraction_level=7,
    tags={"a2a", "scatter", "distribute", "fan-out", "work-stealing"},
)


def _barrier_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Barrier: synchronization point."""
    cap = inputs.get("cap")
    if cap:
        builder.caprequire("sync", "barrier", cap)
    return {}


barrier_tile = Tile(
    name="barrier",
    tile_type=TileType.A2A,
    inputs=[TilePort("cap", PortDirection.INPUT, _i32)],
    outputs=[],
    params={"participants": 2},
    fir_blueprint=_barrier_fir_blueprint,
    cost_estimate=8.0,
    abstraction_level=7,
    tags={"a2a", "barrier", "sync", "synchronization", "wait"},
)


# ══════════════════════════════════════════════════════════════════════════
# EFFECT TILES
# ══════════════════════════════════════════════════════════════════════════

def _print_effect_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Print: output a value."""
    data = inputs.get("data")
    if data:
        builder.call("print", [data], None)
    return {}


print_effect_tile = Tile(
    name="print_effect",
    tile_type=TileType.EFFECT,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[],
    params={"format": "%d"},
    fir_blueprint=_print_effect_fir_blueprint,
    cost_estimate=3.0,
    abstraction_level=8,
    tags={"effect", "print", "io", "output", "logging"},
)


def _log_effect_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Log: log a message."""
    data = inputs.get("data")
    level = params.get("level", "info")
    if data:
        builder.call(f"log_{level}", [data], None)
    return {}


log_effect_tile = Tile(
    name="log_effect",
    tile_type=TileType.EFFECT,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[],
    params={"level": "info", "target": "stdout"},
    fir_blueprint=_log_effect_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=8,
    tags={"effect", "log", "io", "logging", "debug"},
)


def _state_mut_effect_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """State mutation: read-modify-write."""
    state = inputs.get("state")
    value = inputs.get("value")
    if state and value:
        builder.store(value, state)
    return {}


state_mut_tile = Tile(
    name="state_mut",
    tile_type=TileType.EFFECT,
    inputs=[
        TilePort("state", PortDirection.INPUT, _i32),
        TilePort("value", PortDirection.INPUT, _i32),
    ],
    outputs=[],
    params={},
    fir_blueprint=_state_mut_effect_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=5,
    tags={"effect", "state", "mutation", "write"},
)


# ══════════════════════════════════════════════════════════════════════════
# TRANSFORM TILES
# ══════════════════════════════════════════════════════════════════════════

def _cast_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Cast: type conversion."""
    value = inputs.get("value")
    target_type_name = params.get("target_type", "i32")
    if value:
        from ..fir.types import IntType, FloatType
        if target_type_name.startswith("i"):
            bits = int(target_type_name[1:])
            target = _ctx.get_int(bits)
            result = builder.sext(value, target)
        elif target_type_name.startswith("f"):
            bits = int(target_type_name[1:])
            target = _ctx.get_float(bits)
            result = builder.fext(value, target)
        else:
            result = value
        return {"result": result}
    return {}


cast_tile = Tile(
    name="cast",
    tile_type=TileType.TRANSFORM,
    inputs=[TilePort("value", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"target_type": "i64"},
    fir_blueprint=_cast_fir_blueprint,
    cost_estimate=0.5,
    abstraction_level=3,
    tags={"transform", "cast", "convert", "type"},
)


def _reshape_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Reshape: change data shape."""
    data = inputs.get("data")
    if data:
        result = builder.call("_reshape_fn", [data], _i32)
        return {"result": result}
    return {}


reshape_tile = Tile(
    name="reshape",
    tile_type=TileType.TRANSFORM,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"from_shape": (), "to_shape": ()},
    fir_blueprint=_reshape_fir_blueprint,
    cost_estimate=1.0,
    abstraction_level=4,
    tags={"transform", "reshape", "shape", "layout"},
)


def _pack_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Pack: pack values into wider type."""
    lo = inputs.get("lo")
    hi = inputs.get("hi")
    if lo and hi:
        # Pack two i32 into one i64
        result = builder.call("_pack_fn", [lo, hi], _i64)
        return {"result": result}
    return {}


pack_tile = Tile(
    name="pack",
    tile_type=TileType.TRANSFORM,
    inputs=[
        TilePort("lo", PortDirection.INPUT, _i32),
        TilePort("hi", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i64)],
    params={"from_bits": 32, "to_bits": 64},
    fir_blueprint=_pack_fir_blueprint,
    cost_estimate=0.5,
    abstraction_level=3,
    tags={"transform", "pack", "combine", "widen"},
)


def _unpack_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Unpack: unpack wide type into components."""
    value = inputs.get("value")
    if value:
        lo = builder.call("_unpack_lo_fn", [value], _i32)
        hi = builder.call("_unpack_hi_fn", [value], _i32)
        return {"lo": lo, "hi": hi}
    return {}


unpack_tile = Tile(
    name="unpack",
    tile_type=TileType.TRANSFORM,
    inputs=[TilePort("value", PortDirection.INPUT, _i64)],
    outputs=[
        TilePort("lo", PortDirection.OUTPUT, _i32),
        TilePort("hi", PortDirection.OUTPUT, _i32),
    ],
    params={"from_bits": 64, "to_bits": 32},
    fir_blueprint=_unpack_fir_blueprint,
    cost_estimate=0.5,
    abstraction_level=3,
    tags={"transform", "unpack", "split", "narrow"},
)


def _join_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Join: combine multiple streams."""
    a = inputs.get("a")
    b = inputs.get("b")
    if a and b:
        result = builder.call("_join_fn", [a, b], _i32)
        return {"result": result}
    return {}


join_tile = Tile(
    name="join",
    tile_type=TileType.TRANSFORM,
    inputs=[
        TilePort("a", PortDirection.INPUT, _i32),
        TilePort("b", PortDirection.INPUT, _i32),
    ],
    outputs=[TilePort("result", PortDirection.OUTPUT, _i32)],
    params={"strategy": "concat"},
    fir_blueprint=_join_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=5,
    tags={"transform", "join", "combine", "merge", "concat"},
)


def _split_fir_blueprint(
    builder: FIRBuilder,
    inputs: dict[str, Value],
    params: dict[str, Any],
) -> dict[str, Value]:
    """Split: split stream by predicate."""
    data = inputs.get("data")
    if data:
        predicate = params.get("predicate", "_split_pred")
        true_part = builder.call(f"{predicate}_true", [data], _i32)
        false_part = builder.call(f"{predicate}_false", [data], _i32)
        return {"true_part": true_part, "false_part": false_part}
    return {}


split_tile = Tile(
    name="split",
    tile_type=TileType.TRANSFORM,
    inputs=[TilePort("data", PortDirection.INPUT, _i32)],
    outputs=[
        TilePort("true_part", PortDirection.OUTPUT, _i32),
        TilePort("false_part", PortDirection.OUTPUT, _i32),
    ],
    params={"predicate": "_split_pred"},
    fir_blueprint=_split_fir_blueprint,
    cost_estimate=2.0,
    abstraction_level=5,
    tags={"transform", "split", "partition", "filter"},
)


# ══════════════════════════════════════════════════════════════════════════
# ALL BUILT-IN TILES (for registry)
# ══════════════════════════════════════════════════════════════════════════

ALL_BUILTIN_TILES: list[Tile] = [
    # Compute
    map_tile, reduce_tile, scan_tile, filter_tile,
    zip_tile, flatmap_tile, sort_tile, unique_tile,
    # Memory
    gather_tile, scatter_tile, stream_tile, copy_tile,
    fill_tile, transpose_tile,
    # Control
    loop_tile, while_tile, branch_tile, switch_tile,
    fuse_tile, pipeline_tile,
    # A2A
    tell_tile, ask_tile, broadcast_tile, a2a_reduce_tile,
    a2a_scatter_tile, barrier_tile,
    # Effect
    print_effect_tile, log_effect_tile, state_mut_tile,
    # Transform
    cast_tile, reshape_tile, pack_tile, unpack_tile,
    join_tile, split_tile,
]
