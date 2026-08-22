"""FLUX Evolution Engine — the system that builds a better version of itself.

The evolution engine ties together:
- Genome (system DNA snapshots)
- Pattern Mining (hot pattern discovery from execution traces)
- System Mutator (proposing and applying improvements)
- Correctness Validator (ensuring mutations don't break things)
- Evolution Engine (the main loop orchestrating everything)
"""

from .evolution import (
    EvolutionEngine,
    EvolutionRecord,
    EvolutionReport,
    EvolutionStep,
)
from .genome import (
    Genome,
    GenomeDiff,
    ModuleSnapshot,
    MutationStrategy,
    OptimizationRecord,
    ProfilerSnapshot,
    TileSnapshot,
)
from .mutator import (
    MutationProposal,
    MutationRecord,
    MutationResult,
    SystemMutator,
)
from .pattern_mining import (
    DiscoveredPattern,
    ExecutionTrace,
    PatternMiner,
    TileSuggestion,
)
from .validator import (
    CorrectnessValidator,
    RegressionReport,
    TestCase,
    TestResult,
    ValidationResult,
)

__all__ = [
    # Validator
    "CorrectnessValidator",
    "DiscoveredPattern",
    # Engine
    "EvolutionEngine",
    "EvolutionRecord",
    "EvolutionReport",
    "EvolutionStep",
    "ExecutionTrace",
    # Genome
    "Genome",
    "GenomeDiff",
    "ModuleSnapshot",
    "MutationProposal",
    "MutationRecord",
    "MutationResult",
    "MutationStrategy",
    "OptimizationRecord",
    # Pattern Mining
    "PatternMiner",
    "ProfilerSnapshot",
    "RegressionReport",
    # Mutator
    "SystemMutator",
    "TestCase",
    "TestResult",
    "TileSnapshot",
    "TileSuggestion",
    "ValidationResult",
]
