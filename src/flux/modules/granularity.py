"""Granularity levels for the fractal hot-reload hierarchy.

Each level represents a different scale of module containment:
  TRAIN (0)   → CARRIAGE (1) → LUGGAGE (2) → BAG (3) →
  POCKET (4)  → WALLET (5)   → SLOT (6)    → CARD (7)
"""

from __future__ import annotations
from enum import Enum


class Granularity(Enum):
    """Hierarchical granularity levels for hot-reloadable units.

    Lower values = larger containers = slower reload.
    Higher values = smaller units = faster reload.
    """

    TRAIN = 0       # Largest — full library, slowest reload
    CARRIAGE = 1    # Sub-library section
    LUGGAGE = 2     # Feature group
    BAG = 3         # Component cluster
    POCKET = 4      # Single component
    WALLET = 5      # Organized sub-component
    SLOT = 6        # Named position
    CARD = 7        # Atomic unit — fastest hot-reload


class GranularityMeta:
    """Metadata describing the properties of a granularity level.

    Attributes:
        granularity: The granularity level this metadata describes.
        reload_cost: Relative cost of reloading at this level (1–100).
                     Lower = cheaper (CARD = 1), higher = expensive (TRAIN = 100).
        isolation: How independent units at this level are from siblings.
                   0.0 = fully coupled, 1.0 = fully isolated.
        typical_size: Expected byte range for content at this level (min, max).
    """

    __slots__ = ("granularity", "reload_cost", "isolation", "typical_size")

    def __init__(
        self,
        granularity: Granularity,
        reload_cost: int,
        isolation: float,
        typical_size: tuple[int, int],
    ) -> None:
        self.granularity = granularity
        self.reload_cost = reload_cost
        self.isolation = isolation
        self.typical_size = typical_size

    def should_reload_to(self, target: Granularity) -> bool:
        """Can we reload at *target* granularity without disrupting higher levels?

        A reload at *target* is safe when the target is at the same level
        or deeper (higher number) than this level.  Reloading a CARD inside
        a POCKET does not require reloading the POCKET itself.
        """
        return target.value >= self.granularity.value

    def __repr__(self) -> str:
        return (
            f"GranularityMeta({self.granularity.name}, "
            f"cost={self.reload_cost}, isolation={self.isolation:.1f}, "
            f"size={self.typical_size})"
        )


# ── Lookup table ────────────────────────────────────────────────────────────

_GRANULARITY_TABLE: dict[Granularity, GranularityMeta] = {
    Granularity.TRAIN: GranularityMeta(
        granularity=Granularity.TRAIN,
        reload_cost=100,
        isolation=1.0,
        typical_size=(1_000_000, 100_000_000),
    ),
    Granularity.CARRIAGE: GranularityMeta(
        granularity=Granularity.CARRIAGE,
        reload_cost=70,
        isolation=0.9,
        typical_size=(100_000, 10_000_000),
    ),
    Granularity.LUGGAGE: GranularityMeta(
        granularity=Granularity.LUGGAGE,
        reload_cost=50,
        isolation=0.8,
        typical_size=(10_000, 1_000_000),
    ),
    Granularity.BAG: GranularityMeta(
        granularity=Granularity.BAG,
        reload_cost=30,
        isolation=0.7,
        typical_size=(1_000, 100_000),
    ),
    Granularity.POCKET: GranularityMeta(
        granularity=Granularity.POCKET,
        reload_cost=20,
        isolation=0.6,
        typical_size=(500, 50_000),
    ),
    Granularity.WALLET: GranularityMeta(
        granularity=Granularity.WALLET,
        reload_cost=10,
        isolation=0.5,
        typical_size=(100, 10_000),
    ),
    Granularity.SLOT: GranularityMeta(
        granularity=Granularity.SLOT,
        reload_cost=5,
        isolation=0.3,
        typical_size=(10, 5_000),
    ),
    Granularity.CARD: GranularityMeta(
        granularity=Granularity.CARD,
        reload_cost=1,
        isolation=0.1,
        typical_size=(1, 1_000),
    ),
}


def get_granularity_meta(granularity: Granularity) -> GranularityMeta:
    """Return the metadata associated with *granularity*."""
    return _GRANULARITY_TABLE[granularity]
