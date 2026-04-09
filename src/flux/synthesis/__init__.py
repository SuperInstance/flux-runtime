"""FLUX Synthesis — the top-level integration layer that wires ALL subsystems together.

This is the DJ booth: the synthesizer manages nested modules (vinyl collection),
profiles execution (listening to the room), selects languages (choosing instruments),
composes tiles (layering samples), runs evolution (improving the set over time),
and hot-reloads at any granularity (swapping tracks mid-set).

Usage:
    from flux.synthesis import FluxSynthesizer

    synth = FluxSynthesizer("my_app")
    synth.load_module("audio/engine", source, language="python")
    synth.run_workload(my_pipeline)
    synth.evolve(generations=5)
    report = synth.get_system_report()
"""

from .synthesizer import (
    FluxSynthesizer,
    WorkloadResult,
)
from .report import (
    SystemReport,
)

__all__ = [
    "FluxSynthesizer",
    "WorkloadResult",
    "SystemReport",
]
