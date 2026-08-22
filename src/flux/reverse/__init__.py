"""FLUX Reverse Engineering Module.

Shows how existing code in any language maps to FLUX's paradigm.
This is for visitors who want to understand how to take their
existing projects and think about them in FLUX terms.

Public API:
    - FluxReverseEngineer: Main entry point for reverse engineering
    - CodeMap: Complete mapping of source to FLUX FIR
    - MigrationPlan: Step-by-step migration plan
"""

from .code_map import (
    CodeMap,
    CodeMapping,
    ConstructType,
    Difficulty,
    MigrationPlan,
    MigrationStep,
)
from .engineer import FluxReverseEngineer, UnsupportedLanguageError

__all__ = [
    "CodeMap",
    "CodeMapping",
    "ConstructType",
    "Difficulty",
    "FluxReverseEngineer",
    "MigrationPlan",
    "MigrationStep",
    "UnsupportedLanguageError",
]
