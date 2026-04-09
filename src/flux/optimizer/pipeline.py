"""Optimization pipeline — configurable sequence of passes."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..fir.blocks import FIRModule

from .passes import (
    ConstantFoldingPass,
    DeadCodeEliminationPass,
    InlineFunctionsPass,
)


class OptimizationPipeline:
    """Configurable sequence of optimization passes with fixed-point iteration."""

    DEFAULT_PASSES = [
        ConstantFoldingPass,
        DeadCodeEliminationPass,
        InlineFunctionsPass,
        DeadCodeEliminationPass,  # clean up after inlining
    ]

    def __init__(self, passes: list | None = None) -> None:
        if passes is not None:
            self._passes = passes
        else:
            self._passes = [P() for P in self.DEFAULT_PASSES]

    def run(self, module: FIRModule, max_iterations: int = 3) -> int:
        """Run all passes until no changes. Returns total changes."""
        total = 0
        for _ in range(max_iterations):
            changes = sum(p.run(module) for p in self._passes)
            total += changes
            if changes == 0:
                break
        return total
