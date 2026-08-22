"""FLUX Optimizer Module — FIR optimization passes and pipeline."""

from .passes import (
    ConstantFoldingPass,
    DeadCodeEliminationPass,
    InlineFunctionsPass,
    OptimizationPass,
)
from .pipeline import OptimizationPipeline

__all__ = [
    "ConstantFoldingPass",
    "DeadCodeEliminationPass",
    "InlineFunctionsPass",
    "OptimizationPass",
    "OptimizationPipeline",
]
