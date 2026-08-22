"""FLUX Memory System — persistent memory, experience recording, and meta-learning.

This package provides:
- MemoryStore: Four-tier persistent memory (hot/warm/cold/frozen)
- ExperienceRecorder: Records and generalizes from evolution experiences
- MutationBandit: Multi-armed bandit for strategy selection (Thompson Sampling)
- LearningRateAdapter: Adapts exploration rate based on improvement signals
"""

from .bandit import (
    MutationBandit,
    StrategyStats,
)
from .experience import (
    Experience,
    ExperienceRecorder,
    GeneralizedRule,
)
from .learning import (
    LearningRateAdapter,
    LearningState,
)
from .store import (
    TIER_ORDER,
    MemoryEntry,
    MemoryStats,
    MemoryStore,
)

__all__ = [
    "TIER_ORDER",
    # Experience
    "Experience",
    "ExperienceRecorder",
    "GeneralizedRule",
    # Learning
    "LearningRateAdapter",
    "LearningState",
    "MemoryEntry",
    "MemoryStats",
    # Store
    "MemoryStore",
    # Bandit
    "MutationBandit",
    "StrategyStats",
]
