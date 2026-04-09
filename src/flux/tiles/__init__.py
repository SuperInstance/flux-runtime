"""FLUX Tiles — composable computation vocabulary.

Tiles are reusable computation patterns that can be:
- Composed — chained, nested, parallelized
- Parameterized — same pattern, different settings
- Instantiated at any abstraction level
- Hot-swapped — replace a slow tile with a fast one
- Self-generated — the system can discover new tiles from hot code patterns
"""

from .tile import (
    Tile,
    TileType,
    TileInstance,
    CompositeTile,
    ParallelTile,
)
from .ports import TilePort, PortDirection, CoercionInfo
from .graph import TileGraph, TileEdge
from .registry import TileRegistry, default_registry

__all__ = [
    # Core
    "Tile",
    "TileType",
    "TileInstance",
    "CompositeTile",
    "ParallelTile",
    # Ports
    "TilePort",
    "PortDirection",
    "CoercionInfo",
    # Graph
    "TileGraph",
    "TileEdge",
    # Registry
    "TileRegistry",
    "default_registry",
]
