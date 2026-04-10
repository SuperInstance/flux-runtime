"""FLUX Schema — formal, machine-readable schemas describing the FLUX architecture.

These schemas allow external tools (and future AI agents) to understand,
extend, and build on the FLUX system.

Modules:
- architecture: System architecture schema (layers, modules, dependencies)
- opcode_schema: Complete bytecode opcode reference (104 opcodes)
- tile_schema: Tile library schema (34 built-in tiles)
- builder_schema: Extension guides and open research questions
"""

from .architecture import (
    FLUX_ARCHITECTURE,
    get_architecture_schema,
    get_layer_by_id,
    get_module_dependencies,
)
from .opcode_schema import (
    get_opcode_schema,
    get_opcodes_by_category,
    get_opcodes_by_format,
)
from .tile_schema import (
    get_tile_library_schema,
    search_tiles,
)
from .builder_schema import (
    FLUX_BUILDER_SCHEMA,
    get_builder_schema,
    get_open_questions,
)

__all__ = [
    # Architecture
    "FLUX_ARCHITECTURE",
    "get_architecture_schema",
    "get_layer_by_id",
    "get_module_dependencies",
    # Opcode
    "get_opcode_schema",
    "get_opcodes_by_category",
    "get_opcodes_by_format",
    # Tile
    "get_tile_library_schema",
    "search_tiles",
    # Builder
    "FLUX_BUILDER_SCHEMA",
    "get_builder_schema",
    "get_open_questions",
]
