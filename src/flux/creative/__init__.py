"""FLUX Creative — sonification, generative art, live coding, and visualization.

Creative expression tiles for the FLUX runtime. Turns code into music,
data into patterns, and performance into art.

Modules:
- sonification: Code-to-music mapping (opcodes → notes, heat → dynamics)
- generative: Generative art tiles (L-Systems, cellular automata, fractals, RD)
- live: Live coding session management with undo/redo and tempo sync
- visualization: ASCII and colored text visualizations of tile graphs and traces
"""

from .generative import (
    CellularAutomatonTile,
    FractalTile,
    LSystemTile,
    ReactionDiffusionTile,
)
from .live import (
    BeatResult,
    ChangeRecord,
    LiveCodingSession,
    PerformanceState,
    Recording,
    VersionRecord,
)
from .sonification import (
    ExecutionEvent,
    MusicEvent,
    MusicSequence,
    Sonifier,
)
from .visualization import (
    ExecutionVisualizer,
    TileGraphVisualizer,
)

__all__ = [
    "BeatResult",
    "CellularAutomatonTile",
    "ChangeRecord",
    "ExecutionEvent",
    "ExecutionVisualizer",
    "FractalTile",
    # Generative
    "LSystemTile",
    # Live
    "LiveCodingSession",
    "MusicEvent",
    "MusicSequence",
    "PerformanceState",
    "ReactionDiffusionTile",
    "Recording",
    # Sonification
    "Sonifier",
    # Visualization
    "TileGraphVisualizer",
    "VersionRecord",
]
