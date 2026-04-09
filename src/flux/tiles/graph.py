"""Tile Graph — directed acyclic graph of connected tile instances."""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from .tile import Tile, TileInstance
from .ports import TilePort

if TYPE_CHECKING:
    from ..fir.types import TypeContext
    from ..fir.values import Value
    from ..fir.builder import FIRBuilder
    from ..fir.blocks import FIRModule, FIRFunction, FIRBlock


@dataclass
class TileEdge:
    """A directed edge connecting an output port to an input port."""
    from_tile: str
    from_port: str
    to_tile: str
    to_port: str

    def __repr__(self) -> str:
        return f"{self.from_tile}.{self.from_port} -> {self.to_tile}.{self.to_port}"


@dataclass
class TileGraph:
    """A directed acyclic graph of connected tile instances."""

    def __init__(self):
        self._nodes: dict[str, TileInstance] = {}
        self._edges: list[TileEdge] = []
        self._in_degree: dict[str, int] = {}
        self._adj: dict[str, list[str]] = {}

    def add_tile(self, name: str, tile: Tile, **params) -> TileInstance:
        """Add a tile instance to the graph.

        Args:
            name: Unique name for this instance in the graph
            tile: The Tile template
            **params: Parameters to bind

        Returns:
            The created TileInstance
        """
        instance = tile.instantiate(**params)
        self._nodes[name] = instance
        self._in_degree[name] = 0
        self._adj[name] = []
        return instance

    def connect(
        self,
        from_tile: str,
        from_port: str,
        to_tile: str,
        to_port: str,
    ) -> None:
        """Connect an output port of one tile to an input port of another.

        Args:
            from_tile: Source tile name
            from_port: Output port name on source
            to_tile: Destination tile name
            to_port: Input port name on destination
        """
        if from_tile not in self._nodes:
            raise ValueError(f"Tile '{from_tile}' not in graph")
        if to_tile not in self._nodes:
            raise ValueError(f"Tile '{to_tile}' not in graph")

        edge = TileEdge(from_tile, from_port, to_tile, to_port)
        self._edges.append(edge)
        if to_tile not in self._in_degree:
            self._in_degree[to_tile] = 0
        self._in_degree[to_tile] += 1
        if from_tile not in self._adj:
            self._adj[from_tile] = []
        self._adj[from_tile].append(to_tile)

    def topological_order(self) -> list[str]:
        """Return tile names in valid execution order (Kahn's algorithm).

        Raises:
            RuntimeError if the graph contains a cycle
        """
        in_deg = dict(self._in_degree)
        queue = deque()
        for name in in_deg:
            if in_deg[name] == 0:
                queue.append(name)

        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in self._adj.get(node, []):
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            raise RuntimeError("Tile graph contains a cycle")
        return order

    def compile(
        self,
        builder: FIRBuilder,
        ctx: TypeContext,
    ) -> FIRModule:
        """Compile the entire tile graph to a FIR module.

        Creates a function for the graph and emits FIR for each tile
        in topological order, wiring connections between them.

        Args:
            builder: FIRBuilder for instruction emission
            ctx: TypeContext for type interning

        Returns:
            A FIRModule containing the compiled graph
        """
        from ..fir.types import UnitType
        from ..fir.values import Value

        module = builder.new_module("tile_graph")
        func = builder.new_function(module, "graph_main", [], [ctx.get_unit()])
        entry = builder.new_block(func, "entry")
        builder.set_block(entry)

        order = self.topological_order()

        # Track output values per tile per port
        tile_outputs: dict[str, dict[str, Value]] = {}

        # Create input values for tiles that have no incoming edges (graph inputs)
        for name in order:
            instance = self._nodes[name]
            tile_inputs: dict[str, Value] = {}

            # Find edges feeding into this tile
            for edge in self._edges:
                if edge.to_tile == name:
                    src_outputs = tile_outputs.get(edge.from_tile, {})
                    if edge.from_port in src_outputs:
                        tile_inputs[edge.to_port] = src_outputs[edge.from_port]

            # Emit FIR for this tile
            if tile_inputs or not instance.inputs:
                try:
                    outputs = instance.to_fir(builder, tile_inputs)
                    tile_outputs[name] = outputs
                except RuntimeError:
                    # Tile has no blueprint — create dummy values
                    tile_outputs[name] = {}

        builder.ret(None)
        return module

    def find_pattern(self, pattern: TileGraph) -> list[dict[str, str]]:
        """Find subgraphs matching a pattern.

        Args:
            pattern: A TileGraph representing the pattern to search for

        Returns:
            List of dicts mapping pattern tile names to graph tile names
        """
        if not pattern._nodes:
            return []

        # Simple pattern matching: check if all pattern tiles exist
        # with the same tile_type
        pattern_types = {
            name: inst.tile_type for name, inst in pattern._nodes.items()
        }
        matches = []

        # For single-node patterns
        if len(pattern._nodes) == 1:
            pat_name = list(pattern._nodes.keys())[0]
            pat_type = list(pattern_types.values())[0]
            for g_name, g_inst in self._nodes.items():
                if g_inst.tile_type == pat_type:
                    matches.append({pat_name: g_name})
            return matches

        # For multi-node patterns, find all pairs/triples with matching types
        from itertools import permutations
        graph_names = list(self._nodes.keys())
        pat_names = list(pattern._nodes.keys())

        for perm in permutations(graph_names, len(pat_names)):
            mapping = dict(zip(pat_names, perm))
            type_match = all(
                self._nodes[mapping[pn]].tile_type == pattern_types[pn]
                for pn in pat_names
            )
            if type_match:
                matches.append(mapping)

        return matches

    def substitute(self, matches: list[dict[str, str]], replacement: Tile) -> None:
        """Replace matched subgraphs with an optimized replacement tile.

        Args:
            matches: List of mappings from pattern names to graph names
            replacement: The replacement tile
        """
        # Collect all tile names to remove
        to_remove = set()
        for match in matches:
            for graph_name in match.values():
                to_remove.add(graph_name)

        # Remove matched tiles and their edges
        for name in to_remove:
            if name in self._nodes:
                del self._nodes[name]
            if name in self._in_degree:
                del self._in_degree[name]
            if name in self._adj:
                del self._adj[name]

        self._edges = [
            e for e in self._edges
            if e.from_tile not in to_remove and e.to_tile not in to_remove
        ]

        # Add replacement tile
        self.add_tile(f"{replacement.name}_opt", replacement)

    def to_dot(self) -> str:
        """Generate Graphviz DOT representation."""
        lines = ["digraph tile_graph {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")
        lines.append("")

        # Nodes
        for name, instance in self._nodes.items():
            label = f"{name}\\n({instance.tile.tile_type.value})"
            lines.append(f'  "{name}" [label="{label}"];')

        lines.append("")

        # Edges
        for edge in self._edges:
            lines.append(
                f'  "{edge.from_tile}" -> "{edge.to_tile}" '
                f'[label="{edge.from_port} -> {edge.to_port}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    @property
    def nodes(self) -> dict[str, TileInstance]:
        """Read-only access to graph nodes."""
        return dict(self._nodes)

    @property
    def edges(self) -> list[TileEdge]:
        """Read-only access to graph edges."""
        return list(self._edges)

    def __repr__(self) -> str:
        return (
            f"TileGraph(nodes={len(self._nodes)}, "
            f"edges={len(self._edges)})"
        )
