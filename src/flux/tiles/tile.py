"""Tile Core — the Tile abstraction, TileInstance, CompositeTile, ParallelTile."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Callable, TYPE_CHECKING

from .ports import TilePort, PortDirection

if TYPE_CHECKING:
    from ..fir.types import TypeContext, FIRType
    from ..fir.values import Value
    from ..fir.builder import FIRBuilder
    from ..fir.blocks import FIRModule


class TileType(Enum):
    """Category of a tile's computation."""
    COMPUTE = "compute"       # Pure computation (map, reduce, scan)
    MEMORY = "memory"         # Memory access pattern (gather, scatter, stream)
    CONTROL = "control"       # Control flow (loop, branch, switch, fuse)
    A2A = "a2a"              # Agent-to-agent (tell, ask, reduce, broadcast)
    EFFECT = "effect"         # Side effects (IO, state mutation, logging)
    TRANSFORM = "transform"   # Data transformation (cast, reshape, reindex)


class Tile:
    """A reusable computation pattern that can be composed and hot-swapped.

    Tiles are like samples in a DJ's library — reusable, composable,
    parameterizable computation patterns.
    """

    def __init__(
        self,
        name: str,
        tile_type: TileType,
        inputs: list[TilePort] | None = None,
        outputs: list[TilePort] | None = None,
        params: dict[str, Any] | None = None,
        body: str | None = None,
        fir_blueprint: Callable | None = None,
        cost_estimate: float = 1.0,
        abstraction_level: int = 5,
        language_preference: str = "fir",
        tags: set[str] | None = None,
    ):
        self.name = name
        self.tile_type = tile_type
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.params = params or {}
        self.body = body
        self.fir_blueprint = fir_blueprint
        self.cost_estimate = cost_estimate
        self.abstraction_level = abstraction_level
        self.language_preference = language_preference
        self.tags = tags or set()

    def instantiate(self, **kwargs) -> TileInstance:
        """Create a concrete instance with given parameter bindings."""
        merged_params = {**self.params, **kwargs}
        return TileInstance(tile=self, params=merged_params)

    def compose(self, other: Tile, mapping: dict[str, str]) -> CompositeTile:
        """Chain this tile with another, connecting outputs->inputs by name mapping.

        mapping: {self_output_name: other_input_name}
        """
        return CompositeTile(tiles=[self, other], mappings=[mapping])

    def parallel(self, n: int) -> ParallelTile:
        """Create n parallel instances of this tile."""
        return ParallelTile(tile=self, count=n)

    def to_fir(
        self,
        builder: FIRBuilder,
        inputs: dict[str, Value],
    ) -> dict[str, Value]:
        """Emit FIR instructions for this tile using the builder.

        Args:
            builder: FIRBuilder to emit instructions with
            inputs: dict mapping port names to SSA Values

        Returns:
            dict mapping output port names to SSA Values

        Raises:
            RuntimeError if no fir_blueprint is defined
        """
        if self.fir_blueprint is None:
            raise RuntimeError(f"Tile '{self.name}' has no FIR blueprint")
        return self.fir_blueprint(builder, inputs, self.params)

    def __repr__(self) -> str:
        return (
            f"Tile({self.name!r}, {self.tile_type.value}, "
            f"inputs={len(self.inputs)}, outputs={len(self.outputs)}, "
            f"cost={self.cost_estimate})"
        )


@dataclass
class TileInstance:
    """A concrete instance of a tile with bound parameters."""
    tile: Tile
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.tile.name

    @property
    def tile_type(self) -> TileType:
        return self.tile.tile_type

    @property
    def inputs(self) -> list[TilePort]:
        return self.tile.inputs

    @property
    def outputs(self) -> list[TilePort]:
        return self.tile.outputs

    def to_fir(
        self,
        builder: FIRBuilder,
        inputs: dict[str, Value],
    ) -> dict[str, Value]:
        """Emit FIR using the underlying tile with instance params merged."""
        merged_params = {**self.tile.params, **self.params}
        if self.tile.fir_blueprint is None:
            raise RuntimeError(f"Tile '{self.tile.name}' has no FIR blueprint")
        return self.tile.fir_blueprint(builder, inputs, merged_params)

    def __repr__(self) -> str:
        return f"TileInstance({self.tile.name!r}, params={self.params})"


@dataclass
class CompositeTile:
    """A tile formed by composing multiple tiles with connection mappings."""
    tiles: list[Tile]
    mappings: list[dict[str, str]]  # [{output_name: input_name}, ...]

    @property
    def name(self) -> str:
        return " -> ".join(t.name for t in self.tiles)

    @property
    def tile_type(self) -> TileType:
        return self.tiles[0].tile_type if self.tiles else TileType.COMPUTE

    @property
    def inputs(self) -> list[TilePort]:
        return self.tiles[0].inputs if self.tiles else []

    @property
    def outputs(self) -> list[TilePort]:
        return self.tiles[-1].outputs if self.tiles else []

    @property
    def cost_estimate(self) -> float:
        return sum(t.cost_estimate for t in self.tiles)

    def to_fir(
        self,
        builder: FIRBuilder,
        inputs: dict[str, Value],
    ) -> dict[str, Value]:
        """Emit FIR for the full composition chain."""
        current_outputs = inputs
        for i, tile in enumerate(self.tiles):
            mapping = self.mappings[i] if i < len(self.mappings) else {}
            # Remap inputs according to mapping
            tile_inputs = {}
            for port in tile.inputs:
                if port.name in mapping:
                    mapped_name = mapping[port.name]
                    if mapped_name in current_outputs:
                        tile_inputs[port.name] = current_outputs[mapped_name]
                    elif mapped_name in inputs:
                        tile_inputs[port.name] = inputs[mapped_name]
                elif port.name in current_outputs:
                    tile_inputs[port.name] = current_outputs[port.name]
                elif port.name in inputs:
                    tile_inputs[port.name] = inputs[port.name]
            current_outputs = tile.to_fir(builder, tile_inputs)
        return current_outputs

    def __repr__(self) -> str:
        names = " -> ".join(t.name for t in self.tiles)
        return f"CompositeTile([{names}])"


@dataclass
class ParallelTile:
    """A tile replicated N times in parallel."""
    tile: Tile
    count: int

    @property
    def name(self) -> str:
        return f"parallel({self.tile.name}x{self.count})"

    @property
    def tile_type(self) -> TileType:
        return self.tile.tile_type

    @property
    def inputs(self) -> list[TilePort]:
        return self.tile.inputs

    @property
    def outputs(self) -> list[TilePort]:
        return self.tile.outputs

    @property
    def cost_estimate(self) -> float:
        return self.tile.cost_estimate * self.count

    def to_fir(
        self,
        builder: FIRBuilder,
        inputs: dict[str, Value],
    ) -> dict[str, Value]:
        """Emit FIR for each parallel instance. Returns last instance outputs."""
        last_outputs = {}
        for i in range(self.count):
            # Prefix input names with instance index for uniqueness
            last_outputs = self.tile.to_fir(builder, inputs)
        return last_outputs

    def __repr__(self) -> str:
        return f"ParallelTile({self.tile.name!r}, count={self.count})"
