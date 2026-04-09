"""FLUX Optimizer Module — FIR optimization passes and pipeline."""

from .passes import (
    OptimizationPass,
    ConstantFoldingPass,
    DeadCodeEliminationPass,
    InlineFunctionsPass,
)
from .pipeline import OptimizationPipeline

__all__ = [
    "OptimizationPass",
    "ConstantFoldingPass",
    "DeadCodeEliminationPass",
    "InlineFunctionsPass",
    "OptimizationPipeline",
]
