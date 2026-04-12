#!/usr/bin/env python3
"""
FLUX Evolution Engine — Python implementation of the evolve system.
Compatible with JetsonClaw1's flux-evolve-c and flux-evolve (Rust) APIs.

Provides the backend for the EVOLVE opcode in the FLUX VM.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Behavior:
    name: str
    value: float
    min_val: float
    max_val: float
    mutation_rate: float = 0.1
    generation: int = 0
    score: float = 0.0
    outcomes: list = field(default_factory=list)


class EvolutionEngine:
    """Deterministic evolution engine for agent self-modification."""

    def __init__(self, seed: int = 0):
        self.behaviors: dict[str, Behavior] = {}
        self.history: list[dict] = []
        self.generation: int = 0
        self.seed = seed
        self.elite_threshold: float = 0.8  # top 20% protected
        self.aggressive_threshold: float = 0.3  # bottom 30% aggressive

    def add_behavior(self, name: str, value: float,
                     min_val: float = 0.0, max_val: float = 1.0,
                     mutation_rate: float = 0.1) -> int:
        """Add a behavior to the genome. Returns index."""
        self.behaviors[name] = Behavior(
            name=name, value=value, min_val=min_val,
            max_val=max_val, mutation_rate=mutation_rate
        )
        return len(self.behaviors) - 1

    def get(self, name: str) -> float:
        return self.behaviors[name].value

    def set(self, name: str, value: float) -> bool:
        if name in self.behaviors:
            b = self.behaviors[name]
            b.value = max(b.min_val, min(b.max_val, value))
            return True
        return False

    def _mutate_value(self, behavior: Behavior, fitness: float,
                      timestamp: int) -> float:
        """Mutate a behavior based on fitness score."""
        # Deterministic pseudo-random from seed + timestamp + name
        h = hashlib.sha256(
            f"{self.seed}:{behavior.name}:{timestamp}:{self.generation}".encode()
        ).digest()
        rand = int.from_bytes(h[:4], 'little') / 0xFFFFFFFF

        # Determine mutation aggressiveness
        if fitness >= self.elite_threshold:
            # Elite: protect, gentle mutation
            rate = behavior.mutation_rate * 0.1
        elif fitness < self.aggressive_threshold:
            # Low performer: aggressive mutation
            rate = behavior.mutation_rate * 3.0
        else:
            # Normal
            rate = behavior.mutation_rate

        # Apply mutation
        delta = (rand - 0.5) * 2 * rate * (behavior.max_val - behavior.min_val)
        new_val = behavior.value + delta
        return max(behavior.min_val, min(behavior.max_val, new_val))

    def cycle(self, fitness: float, timestamp: Optional[int] = None) -> int:
        """Run one evolution cycle. Returns generation number."""
        ts = timestamp or int(time.time() * 1000)
        snapshot = {}

        for name, b in self.behaviors.items():
            old_val = b.value
            new_val = self._mutate_value(b, fitness, ts)
            snapshot[name] = {"from": old_val, "to": new_val}
            b.value = new_val
            b.generation = self.generation

        self.history.append({
            "generation": self.generation,
            "fitness": fitness,
            "timestamp": ts,
            "mutations": snapshot
        })
        self.generation += 1
        return self.generation

    def score(self, name: str, outcome: float) -> bool:
        """Score a behavior's outcome."""
        if name in self.behaviors:
            b = self.behaviors[name]
            b.outcomes.append(outcome)
            b.score = sum(b.outcomes) / len(b.outcomes)
            return True
        return False

    def revert(self, history_index: int) -> bool:
        """Revert to a specific history entry."""
        if 0 <= history_index < len(self.history):
            entry = self.history[history_index]
            for name, change in entry["mutations"].items():
                if name in self.behaviors:
                    self.behaviors[name].value = change["from"]
            return True
        return False

    def rollback(self, target_generation: int) -> bool:
        """Rollback to a target generation."""
        # Find the history entry for that generation
        for i, entry in enumerate(self.history):
            if entry["generation"] == target_generation:
                return self.revert(i)
        return False

    def best_behaviors(self, n: int = 3) -> list[tuple[str, float]]:
        """Get top N behaviors by score."""
        scored = [(b.name, b.score) for b in self.behaviors.values() if b.outcomes]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n]

    def worst_behaviors(self, n: int = 3) -> list[tuple[str, float]]:
        """Get bottom N behaviors by score."""
        scored = [(b.name, b.score) for b in self.behaviors.values() if b.outcomes]
        scored.sort(key=lambda x: x[1])
        return scored[:n]

    def snapshot(self) -> dict:
        """Full state snapshot."""
        return {
            "generation": self.generation,
            "seed": self.seed,
            "behaviors": {
                name: {"value": b.value, "score": b.score,
                       "generation": b.generation}
                for name, b in self.behaviors.items()
            },
            "history_length": len(self.history)
        }


# ── Tests ──────────────────────────────────────────────────────────────

def test_basic_evolution():
    e = EvolutionEngine(seed=42)
    e.add_behavior("learning_rate", 0.01, 0.001, 0.1, 0.01)
    e.add_behavior("exploration", 0.5, 0.0, 1.0, 0.1)

    # Run evolution with moderate fitness
    gen = e.cycle(0.5)
    assert gen == 1

    # Values should have changed
    assert e.get("learning_rate") != 0.01 or e.get("exploration") != 0.5
    print("✅ test_basic_evolution")


def test_elite_protection():
    e = EvolutionEngine(seed=42)
    e.add_behavior("protected_param", 0.5, 0.0, 1.0, 0.5)
    original = e.get("protected_param")

    # High fitness = elite protection
    e.cycle(0.95)
    # Elite mutation is 10x smaller, so change should be tiny
    new_val = e.get("protected_param")
    assert abs(new_val - original) < 0.1  # very small change
    print(f"✅ test_elite_protection: {original:.4f} → {new_val:.4f}")


def test_aggressive_mutation():
    e = EvolutionEngine(seed=42)
    e.add_behavior("bad_param", 0.5, 0.0, 1.0, 0.5)
    original = e.get("bad_param")

    # Low fitness = aggressive mutation
    e.cycle(0.1)
    new_val = e.get("bad_param")
    # Aggressive mutation is 3x larger
    assert abs(new_val - original) > 0.001  # should be noticeable
    print(f"✅ test_aggressive_mutation: {original:.4f} → {new_val:.4f}")


def test_scoring():
    e = EvolutionEngine(seed=42)
    e.add_behavior("param1", 0.5)
    e.add_behavior("param2", 0.5)

    e.score("param1", 0.9)
    e.score("param1", 0.8)
    e.score("param2", 0.3)
    e.score("param2", 0.2)

    best = e.best_behaviors(1)
    worst = e.worst_behaviors(1)
    assert best[0][0] == "param1"
    assert worst[0][0] == "param2"
    print(f"✅ test_scoring: best={best}, worst={worst}")


def test_revert():
    e = EvolutionEngine(seed=42)
    e.add_behavior("reversible", 0.5, 0.0, 1.0, 0.3)
    original = e.get("reversible")

    e.cycle(0.5)
    mutated = e.get("reversible")

    e.revert(0)  # revert first mutation
    assert e.get("reversible") == original
    print(f"✅ test_revert: {original:.4f} → {mutated:.4f} → {e.get('reversible'):.4f}")


def test_rollback():
    e = EvolutionEngine(seed=42)
    e.add_behavior("rollback_param", 0.5, 0.0, 1.0, 0.3)
    original = e.get("rollback_param")

    e.cycle(0.5)  # gen 0→1
    e.cycle(0.5)  # gen 1→2
    e.cycle(0.5)  # gen 2→3

    e.rollback(0)  # back to gen 0
    assert e.get("rollback_param") == original
    print(f"✅ test_rollback: gen 3 → gen 0")


def test_deterministic():
    """Same seed + same fitness = same mutations."""
    e1 = EvolutionEngine(seed=123)
    e1.add_behavior("det", 0.5, 0.0, 1.0, 0.2)

    e2 = EvolutionEngine(seed=123)
    e2.add_behavior("det", 0.5, 0.0, 1.0, 0.2)

    e1.cycle(0.5, timestamp=1000)
    e2.cycle(0.5, timestamp=1000)

    assert e1.get("det") == e2.get("det")
    print(f"✅ test_deterministic: both={e1.get('det'):.6f}")


def test_snapshot_restore():
    e = EvolutionEngine(seed=42)
    e.add_behavior("snap_param", 0.5)
    e.cycle(0.5)
    snap = e.snapshot()

    assert snap["generation"] == 1
    assert "snap_param" in snap["behaviors"]
    assert snap["history_length"] == 1
    print(f"✅ test_snapshot_restore: gen={snap['generation']}")


def test_boundary_clamping():
    e = EvolutionEngine(seed=42)
    e.add_behavior("clamped", 0.99, 0.0, 1.0, 0.5)

    # Even aggressive mutation shouldn't exceed bounds
    for _ in range(10):
        e.cycle(0.1)  # aggressive
        assert 0.0 <= e.get("clamped") <= 1.0

    print(f"✅ test_boundary_clamping: always in [0, 1]")


if __name__ == "__main__":
    test_basic_evolution()
    test_elite_protection()
    test_aggressive_mutation()
    test_scoring()
    test_revert()
    test_rollback()
    test_deterministic()
    test_snapshot_restore()
    test_boundary_clamping()
    print("\n9/9 tests passing ✅")
