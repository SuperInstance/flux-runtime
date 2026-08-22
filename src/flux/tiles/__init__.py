"""FLUX Tiles — composable computation vocabulary.

Tiles are reusable computation patterns that can be:
- Composed — chained, nested, parallelized
- Parameterized — same pattern, different settings
- Instantiated at any abstraction level
- Hot-swapped — replace a slow tile with a fast one
- Self-generated — the system can discover new tiles from hot code patterns
"""

from .graph import TileEdge, TileGraph
from .ports import CoercionInfo, PortDirection, TilePort
from .registry import TileRegistry, default_registry
from .tile import (
    CompositeTile,
    ParallelTile,
    Tile,
    TileInstance,
    TileType,
)

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
