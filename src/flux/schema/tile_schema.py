"""Tile Library Schema — machine-readable schema for all 34 built-in tiles."""

from __future__ import annotations
from typing import Any, Optional


# Complete tile library schema derived from flux/tiles/library.py
_TILES: list[dict[str, Any]] = [
    # ════════════════════════════════════════════════════════════════════
    # COMPUTE TILES (8)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "map",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn", "type": "str", "default": "_map_fn"},
        ],
        "cost": 1.0,
        "abstraction": 6,
        "tags": ["compute", "map", "functional", "element-wise"],
    },
    {
        "name": "reduce",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
            {"name": "init", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn", "type": "str", "default": "_reduce_fn"},
            {"name": "op", "type": "str", "default": "add"},
        ],
        "cost": 2.0,
        "abstraction": 6,
        "tags": ["compute", "reduce", "fold", "aggregate"],
    },
    {
        "name": "scan",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn", "type": "str", "default": "_scan_fn"},
            {"name": "op", "type": "str", "default": "add"},
            {"name": "inclusive", "type": "bool", "default": True},
        ],
        "cost": 2.0,
        "abstraction": 6,
        "tags": ["compute", "scan", "prefix", "cumulative"],
    },
    {
        "name": "filter",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "predicate", "type": "str", "default": "_filter_pred"},
        ],
        "cost": 1.5,
        "abstraction": 6,
        "tags": ["compute", "filter", "predicate"],
    },
    {
        "name": "zip",
        "type": "COMPUTE",
        "inputs": [
            {"name": "a", "type": "i32", "direction": "input"},
            {"name": "b", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn", "type": "str", "default": "_zip_fn"},
        ],
        "cost": 1.0,
        "abstraction": 6,
        "tags": ["compute", "zip", "combine", "element-wise"],
    },
    {
        "name": "flatmap",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn", "type": "str", "default": "_flatmap_fn"},
        ],
        "cost": 1.5,
        "abstraction": 7,
        "tags": ["compute", "flatmap", "map", "flatten"],
    },
    {
        "name": "sort",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "comparator", "type": "str", "default": "_sort_cmp"},
            {"name": "order", "type": "str", "default": "asc"},
        ],
        "cost": 5.0,
        "abstraction": 6,
        "tags": ["compute", "sort", "ordering"],
    },
    {
        "name": "unique",
        "type": "COMPUTE",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [],
        "cost": 3.0,
        "abstraction": 6,
        "tags": ["compute", "unique", "dedup", "set"],
    },

    # ════════════════════════════════════════════════════════════════════
    # MEMORY TILES (6)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "gather",
        "type": "MEMORY",
        "inputs": [
            {"name": "base", "type": "i32", "direction": "input"},
            {"name": "index", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [],
        "cost": 1.0,
        "abstraction": 3,
        "tags": ["memory", "gather", "random-access", "read"],
    },
    {
        "name": "scatter",
        "type": "MEMORY",
        "inputs": [
            {"name": "base", "type": "i32", "direction": "input"},
            {"name": "index", "type": "i32", "direction": "input"},
            {"name": "value", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [],
        "cost": 1.0,
        "abstraction": 3,
        "tags": ["memory", "scatter", "random-access", "write"],
    },
    {
        "name": "stream",
        "type": "MEMORY",
        "inputs": [
            {"name": "base", "type": "i32", "direction": "input"},
            {"name": "offset", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "base_offset", "type": "int", "default": 0},
            {"name": "direction", "type": "str", "default": "read"},
        ],
        "cost": 0.5,
        "abstraction": 3,
        "tags": ["memory", "stream", "sequential", "io"],
    },
    {
        "name": "copy",
        "type": "MEMORY",
        "inputs": [
            {"name": "src", "type": "i32", "direction": "input"},
            {"name": "dst", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "size", "type": "int", "default": 64},
        ],
        "cost": 2.0,
        "abstraction": 2,
        "tags": ["memory", "copy", "bulk", "memcpy"],
    },
    {
        "name": "fill",
        "type": "MEMORY",
        "inputs": [
            {"name": "dst", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "fill_value", "type": "int", "default": 0},
            {"name": "size", "type": "int", "default": 64},
        ],
        "cost": 2.0,
        "abstraction": 2,
        "tags": ["memory", "fill", "memset", "initialize"],
    },
    {
        "name": "transpose",
        "type": "MEMORY",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "rows", "type": "int", "default": 0},
            {"name": "cols", "type": "int", "default": 0},
        ],
        "cost": 4.0,
        "abstraction": 4,
        "tags": ["memory", "transpose", "matrix", "layout"],
    },

    # ════════════════════════════════════════════════════════════════════
    # CONTROL TILES (6)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "loop",
        "type": "CONTROL",
        "inputs": [
            {"name": "init", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "count", "type": "int", "default": 10},
            {"name": "body", "type": "str", "default": "_loop_body"},
        ],
        "cost": 3.0,
        "abstraction": 4,
        "tags": ["control", "loop", "iteration", "fixed-count"],
    },
    {
        "name": "while",
        "type": "CONTROL",
        "inputs": [
            {"name": "init", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "cond", "type": "str", "default": "_while_cond"},
            {"name": "body", "type": "str", "default": "_while_body"},
            {"name": "max_iters", "type": "int", "default": 1000},
        ],
        "cost": 4.0,
        "abstraction": 4,
        "tags": ["control", "while", "loop", "condition"],
    },
    {
        "name": "branch",
        "type": "CONTROL",
        "inputs": [
            {"name": "cond", "type": "bool", "direction": "input"},
            {"name": "true_val", "type": "i32", "direction": "input"},
            {"name": "false_val", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [],
        "cost": 1.0,
        "abstraction": 4,
        "tags": ["control", "branch", "conditional", "if-else"],
    },
    {
        "name": "switch",
        "type": "CONTROL",
        "inputs": [
            {"name": "value", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "cases", "type": "dict", "default": {}},
            {"name": "default", "type": "str", "default": "_switch_default"},
        ],
        "cost": 1.5,
        "abstraction": 4,
        "tags": ["control", "switch", "dispatch", "multi-way"],
    },
    {
        "name": "fuse",
        "type": "CONTROL",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "fn1", "type": "str", "default": "_fuse_fn1"},
            {"name": "fn2", "type": "str", "default": "_fuse_fn2"},
        ],
        "cost": 2.5,
        "abstraction": 5,
        "tags": ["control", "fuse", "optimization", "loop-fusion"],
    },
    {
        "name": "pipeline",
        "type": "CONTROL",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "stages", "type": "list", "default": ["_pipe_s1"]},
        ],
        "cost": 3.0,
        "abstraction": 5,
        "tags": ["control", "pipeline", "software-pipelining", "optimization"],
    },

    # ════════════════════════════════════════════════════════════════════
    # A2A TILES (6)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "tell",
        "type": "A2A",
        "inputs": [
            {"name": "message", "type": "i32", "direction": "input"},
            {"name": "cap", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "target", "type": "str", "default": "_default_agent"},
        ],
        "cost": 5.0,
        "abstraction": 7,
        "tags": ["a2a", "tell", "send", "message", "fire-and-forget"],
    },
    {
        "name": "ask",
        "type": "A2A",
        "inputs": [
            {"name": "message", "type": "i32", "direction": "input"},
            {"name": "cap", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "target", "type": "str", "default": "_default_agent"},
        ],
        "cost": 10.0,
        "abstraction": 7,
        "tags": ["a2a", "ask", "request", "response", "rpc"],
    },
    {
        "name": "broadcast",
        "type": "A2A",
        "inputs": [
            {"name": "message", "type": "i32", "direction": "input"},
            {"name": "cap", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "agents", "type": "list", "default": []},
        ],
        "cost": 15.0,
        "abstraction": 7,
        "tags": ["a2a", "broadcast", "send-all", "fan-out"],
    },
    {
        "name": "a2a_reduce",
        "type": "A2A",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "op", "type": "str", "default": "sum"},
            {"name": "agents", "type": "list", "default": []},
        ],
        "cost": 20.0,
        "abstraction": 7,
        "tags": ["a2a", "reduce", "collect", "gather", "aggregate"],
    },
    {
        "name": "a2a_scatter",
        "type": "A2A",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "agents", "type": "list", "default": []},
            {"name": "strategy", "type": "str", "default": "round-robin"},
        ],
        "cost": 10.0,
        "abstraction": 7,
        "tags": ["a2a", "scatter", "distribute", "fan-out", "work-stealing"],
    },
    {
        "name": "barrier",
        "type": "A2A",
        "inputs": [
            {"name": "cap", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "participants", "type": "int", "default": 2},
        ],
        "cost": 8.0,
        "abstraction": 7,
        "tags": ["a2a", "barrier", "sync", "synchronization", "wait"],
    },

    # ════════════════════════════════════════════════════════════════════
    # EFFECT TILES (3)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "print_effect",
        "type": "EFFECT",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "format", "type": "str", "default": "%d"},
        ],
        "cost": 3.0,
        "abstraction": 8,
        "tags": ["effect", "print", "io", "output", "logging"],
    },
    {
        "name": "log_effect",
        "type": "EFFECT",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [
            {"name": "level", "type": "str", "default": "info"},
            {"name": "target", "type": "str", "default": "stdout"},
        ],
        "cost": 2.0,
        "abstraction": 8,
        "tags": ["effect", "log", "io", "logging", "debug"],
    },
    {
        "name": "state_mut",
        "type": "EFFECT",
        "inputs": [
            {"name": "state", "type": "i32", "direction": "input"},
            {"name": "value", "type": "i32", "direction": "input"},
        ],
        "outputs": [],
        "params": [],
        "cost": 1.0,
        "abstraction": 5,
        "tags": ["effect", "state", "mutation", "write"],
    },

    # ════════════════════════════════════════════════════════════════════
    # TRANSFORM TILES (6)
    # ════════════════════════════════════════════════════════════════════
    {
        "name": "cast",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "value", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "target_type", "type": "str", "default": "i64"},
        ],
        "cost": 0.5,
        "abstraction": 3,
        "tags": ["transform", "cast", "convert", "type"],
    },
    {
        "name": "reshape",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "from_shape", "type": "tuple", "default": ()},
            {"name": "to_shape", "type": "tuple", "default": ()},
        ],
        "cost": 1.0,
        "abstraction": 4,
        "tags": ["transform", "reshape", "shape", "layout"],
    },
    {
        "name": "pack",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "lo", "type": "i32", "direction": "input"},
            {"name": "hi", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i64", "direction": "output"},
        ],
        "params": [
            {"name": "from_bits", "type": "int", "default": 32},
            {"name": "to_bits", "type": "int", "default": 64},
        ],
        "cost": 0.5,
        "abstraction": 3,
        "tags": ["transform", "pack", "combine", "widen"],
    },
    {
        "name": "unpack",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "value", "type": "i64", "direction": "input"},
        ],
        "outputs": [
            {"name": "lo", "type": "i32", "direction": "output"},
            {"name": "hi", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "from_bits", "type": "int", "default": 64},
            {"name": "to_bits", "type": "int", "default": 32},
        ],
        "cost": 0.5,
        "abstraction": 3,
        "tags": ["transform", "unpack", "split", "narrow"],
    },
    {
        "name": "join",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "a", "type": "i32", "direction": "input"},
            {"name": "b", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "result", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "strategy", "type": "str", "default": "concat"},
        ],
        "cost": 2.0,
        "abstraction": 5,
        "tags": ["transform", "join", "combine", "merge", "concat"],
    },
    {
        "name": "split",
        "type": "TRANSFORM",
        "inputs": [
            {"name": "data", "type": "i32", "direction": "input"},
        ],
        "outputs": [
            {"name": "true_part", "type": "i32", "direction": "output"},
            {"name": "false_part", "type": "i32", "direction": "output"},
        ],
        "params": [
            {"name": "predicate", "type": "str", "default": "_split_pred"},
        ],
        "cost": 2.0,
        "abstraction": 5,
        "tags": ["transform", "split", "partition", "filter"],
    },
]


def get_tile_library_schema() -> dict[str, dict[str, Any]]:
    """Complete schema of all available tiles.

    Returns:
        Dict mapping tile name -> full tile metadata.
    """
    return {tile["name"]: tile for tile in _TILES}


def search_tiles(
    query: str,
    tile_type: Optional[str] = None,
    min_abstraction: int = 0,
    max_abstraction: int = 10,
) -> list[dict[str, Any]]:
    """Search the tile library by query string, type, and abstraction range.

    Args:
        query: Free-text search (matched against name, tags, type).
        tile_type: Optional type filter (e.g., 'COMPUTE', 'A2A').
        min_abstraction: Minimum abstraction level (inclusive).
        max_abstraction: Maximum abstraction level (inclusive).

    Returns:
        List of matching tile dicts, sorted by relevance.
    """
    query_lower = query.lower()
    results = []

    for tile in _TILES:
        # Type filter
        if tile_type and tile["type"] != tile_type.upper():
            continue

        # Abstraction filter
        if not (min_abstraction <= tile["abstraction"] <= max_abstraction):
            continue

        # Text search
        searchable = " ".join([
            tile["name"],
            tile["type"],
            *tile["tags"],
        ]).lower()

        if query_lower in searchable:
            # Relevance: exact name match gets higher score
            score = 0
            if query_lower == tile["name"].lower():
                score = 10
            elif query_lower in tile["name"].lower():
                score = 5
            for tag in tile["tags"]:
                if query_lower in tag.lower():
                    score += 2
            results.append((score, tile))

    # Sort by relevance (highest first)
    results.sort(key=lambda x: x[0], reverse=True)
    return [tile for _, tile in results]
