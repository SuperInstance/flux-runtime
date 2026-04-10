"""FLUX Reverse Engineering Module.

Shows how existing code in any language maps to FLUX's paradigm.
This is for visitors who want to understand how to take their
existing projects and think about them in FLUX terms.

Public API:
    - FluxReverseEngineer: Main entry point for reverse engineering
    - CodeMap: Complete mapping of source to FLUX FIR
    - MigrationPlan: Step-by-step migration plan
"""

from .engineer import FluxReverseEngineer, UnsupportedLanguageError
from .code_map import (
    CodeMapping,
    CodeMap,
    ConstructType,
    Difficulty,
    MigrationStep,
    MigrationPlan,
)

__all__ = [
    "FluxReverseEngineer",
    "CodeMap",
    "MigrationPlan",
    "CodeMapping",
    "MigrationStep",
    "ConstructType",
    "Difficulty",
    "UnsupportedLanguageError",
]
