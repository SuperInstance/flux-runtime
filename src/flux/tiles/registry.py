"""Tile Registry — global registry of available tiles with search and discovery."""

from __future__ import annotations
from typing import Optional
from difflib import SequenceMatcher

from .tile import Tile, TileType
from .library import ALL_BUILTIN_TILES


class TileRegistry:
    """Global registry of available tiles with search and discovery.

    Supports searching by name, tags, type, abstraction level,
    and finding alternative implementations for optimization.
    """

    def __init__(self):
        self._tiles: dict[str, Tile] = {}

    def register(self, tile: Tile) -> None:
        """Register a tile. Overwrites any existing tile with the same name."""
        self._tiles[tile.name] = tile

    def unregister(self, name: str) -> None:
        """Remove a tile by name. No-op if not found."""
        self._tiles.pop(name, None)

    def get(self, name: str) -> Optional[Tile]:
        """Get a tile by exact name."""
        return self._tiles.get(name)

    def search(self, query: str) -> list[Tile]:
        """Search tiles by name, tags, or type.

        Performs fuzzy matching on tile names and exact matching
        on tags and type names.

        Args:
            query: Search query string

        Returns:
            List of matching tiles sorted by relevance
        """
        query_lower = query.lower()
        results = []

        for tile in self._tiles.values():
            score = 0.0

            # Exact name match
            if tile.name == query:
                score = 1.0
            elif tile.name == query_lower:
                score = 0.95
            else:
                # Fuzzy name match
                ratio = SequenceMatcher(None, tile.name.lower(), query_lower).ratio()
                score = max(score, ratio * 0.8)

            # Tag match
            for tag in tile.tags:
                if tag == query_lower:
                    score = max(score, 0.9)
                elif query_lower in tag or tag in query_lower:
                    score = max(score, 0.7)

            # Type match
            if tile.tile_type.value == query_lower:
                score = max(score, 0.85)
            elif query_lower in tile.tile_type.value:
                score = max(score, 0.6)

            if score > 0.3:
                results.append((score, tile))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [tile for _, tile in results]

    def by_type(self, tile_type: TileType) -> list[Tile]:
        """Get all tiles of a specific type."""
        return [t for t in self._tiles.values() if t.tile_type == tile_type]

    def by_abstraction(self, level: int) -> list[Tile]:
        """Get tiles at a specific abstraction level."""
        return [t for t in self._tiles.values() if t.abstraction_level == level]

    def by_abstraction_range(self, low: int, high: int) -> list[Tile]:
        """Get tiles within an abstraction level range [low, high]."""
        return [
            t for t in self._tiles.values()
            if low <= t.abstraction_level <= high
        ]

    def find_alternatives(self, tile: Tile) -> list[Tile]:
        """Find tiles that could replace this one.

        A tile is considered an alternative if it has the same
        input/output port signatures (same names, same types)
        but is a different tile.

        Args:
            tile: The tile to find alternatives for

        Returns:
            List of alternative tiles sorted by cost (cheapest first)
        """
        input_sig = frozenset((p.name, type(p.type_fir).__name__) for p in tile.inputs)
        output_sig = frozenset((p.name, type(p.type_fir).__name__) for p in tile.outputs)

        alternatives = []
        for other in self._tiles.values():
            if other.name == tile.name:
                continue
            other_in = frozenset((p.name, type(p.type_fir).__name__) for p in other.inputs)
            other_out = frozenset((p.name, type(p.type_fir).__name__) for p in other.outputs)
            if other_in == input_sig and other_out == output_sig:
                alternatives.append(other)

        alternatives.sort(key=lambda t: t.cost_estimate)
        return alternatives

    def most_expensive(self, n: int) -> list[Tile]:
        """Find the N most expensive tiles (optimization candidates).

        Args:
            n: Number of tiles to return

        Returns:
            List of tiles sorted by cost descending
        """
        sorted_tiles = sorted(
            self._tiles.values(),
            key=lambda t: t.cost_estimate,
            reverse=True,
        )
        return sorted_tiles[:n]

    def least_expensive(self, n: int) -> list[Tile]:
        """Find the N least expensive tiles.

        Args:
            n: Number of tiles to return

        Returns:
            List of tiles sorted by cost ascending
        """
        sorted_tiles = sorted(
            self._tiles.values(),
            key=lambda t: t.cost_estimate,
        )
        return sorted_tiles[:n]

    @property
    def all_tiles(self) -> list[Tile]:
        """Get all registered tiles."""
        return list(self._tiles.values())

    @property
    def count(self) -> int:
        """Number of registered tiles."""
        return len(self._tiles)

    def __repr__(self) -> str:
        return f"TileRegistry(tiles={self.count})"

    def __len__(self) -> int:
        return self.count


# ── Global default registry with all built-in tiles ─────────────────────────

default_registry = TileRegistry()
for _tile in ALL_BUILTIN_TILES:
    default_registry.register(_tile)
