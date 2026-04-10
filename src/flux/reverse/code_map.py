"""Code Mapping Data Structures for FLUX Reverse Engineering.

Provides dataclasses for representing the mapping between source language
constructs and their FLUX FIR equivalents, along with migration plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConstructType(str, Enum):
    """Categories of source language constructs that can map to FLUX."""
    FUNCTION = "function"
    VARIABLE = "variable"
    LOOP = "loop"
    CLASS = "class"
    CALL = "call"
    IO_WRITE = "io_write"
    ERROR_HANDLING = "error_handling"
    IMPORT = "import"
    ASYNC = "async"
    COMPREHENSION = "comprehension"
    DECORATOR = "decorator"
    STRUCT = "struct"
    POINTER = "pointer"
    MEMORY = "memory"
    PREPROCESSOR = "preprocessor"
    UNKNOWN = "unknown"


class Difficulty(str, Enum):
    """Migration difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class CodeMapping:
    """Maps a single source code construct to its FLUX FIR equivalent.

    Attributes:
        original: Original code snippet from source.
        flux_ir: Equivalent FIR/bytecode representation.
        construct_type: Category of the source construct.
        confidence: Mapping confidence (0.0-1.0). 1.0 = exact equivalent.
        notes: Human-readable explanation of the mapping.
        line_number: Optional line number in the original source.
    """
    original: str
    flux_ir: str
    construct_type: str
    confidence: float = 1.0
    notes: str = ""
    line_number: Optional[int] = None

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass
class CodeMap:
    """Complete mapping of a source file to FLUX FIR.

    Attributes:
        source_lang: Language of the source code (e.g., "python", "c").
        source_code: Original source code text.
        mappings: List of individual construct mappings.
        summary: Human-readable summary of the mapping.
    """
    source_lang: str
    source_code: str
    mappings: list[CodeMapping] = field(default_factory=list)
    summary: str = ""

    @property
    def mapping_count(self) -> int:
        """Total number of construct mappings."""
        return len(self.mappings)

    @property
    def avg_confidence(self) -> float:
        """Average mapping confidence across all mappings."""
        if not self.mappings:
            return 0.0
        return sum(m.confidence for m in self.mappings) / len(self.mappings)

    @property
    def construct_types(self) -> set[str]:
        """Set of unique construct types found in the mapping."""
        return {m.construct_type for m in self.mappings}

    def get_mappings_by_type(self, construct_type: str) -> list[CodeMapping]:
        """Filter mappings by construct type."""
        return [m for m in self.mappings if m.construct_type == construct_type]

    def get_low_confidence(self, threshold: float = 0.5) -> list[CodeMapping]:
        """Get mappings with confidence below threshold (need manual review)."""
        return [m for m in self.mappings if m.confidence < threshold]


@dataclass
class MigrationStep:
    """A single step in a migration plan.

    Attributes:
        step_number: Sequential step number.
        description: What this step does.
        original_code: The source code to migrate.
        flux_code: The equivalent FLUX code.
        difficulty: How hard this step is (easy/medium/hard).
        estimated_effort: Human-readable time estimate.
    """
    step_number: int
    description: str
    original_code: str
    flux_code: str
    difficulty: str = Difficulty.EASY
    estimated_effort: str = "5 minutes"

    def __post_init__(self):
        if self.difficulty not in (d.value for d in Difficulty):
            raise ValueError(
                f"difficulty must be one of {[d.value for d in Difficulty]}, "
                f"got {self.difficulty}"
            )


@dataclass
class MigrationPlan:
    """A complete plan for migrating source code to FLUX.

    Attributes:
        source_lang: Language of the source code.
        total_steps: Total number of migration steps.
        steps: Ordered list of migration steps.
        overview: Human-readable overview of the migration.
    """
    source_lang: str
    total_steps: int
    steps: list[MigrationStep] = field(default_factory=list)
    overview: str = ""

    @property
    def easy_steps(self) -> list[MigrationStep]:
        """Steps classified as easy."""
        return [s for s in self.steps if s.difficulty == Difficulty.EASY]

    @property
    def medium_steps(self) -> list[MigrationStep]:
        """Steps classified as medium."""
        return [s for s in self.steps if s.difficulty == Difficulty.MEDIUM]

    @property
    def hard_steps(self) -> list[MigrationStep]:
        """Steps classified as hard."""
        return [s for s in self.steps if s.difficulty == Difficulty.HARD]

    @property
    def estimated_total_effort(self) -> str:
        """Rough total effort estimate based on difficulty counts."""
        easy_count = len(self.easy_steps)
        medium_count = len(self.medium_steps)
        hard_count = len(self.hard_steps)
        minutes = easy_count * 5 + medium_count * 15 + hard_count * 60
        if minutes < 60:
            return f"~{minutes} minutes"
        hours = minutes / 60
        if hours < 8:
            return f"~{hours:.1f} hours"
        days = hours / 8
        return f"~{days:.1f} days"
