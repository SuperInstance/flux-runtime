"""FractalReloader — the fractal hot-reload engine.

Manages hot-reloading at any granularity level with cascading,
strategy recommendations, and full history tracking.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from .granularity import Granularity, GranularityMeta, get_granularity_meta
from .container import ModuleContainer, ReloadResult


# ── Event / Result types ────────────────────────────────────────────────────

@dataclass
class ReloadEvent:
    """A single reload event in the history log."""

    timestamp: float
    path: str
    granularity: Granularity
    success: bool
    cards_reloaded: int = 0
    containers_reloaded: int = 0
    elapsed_ns: int = 0
    error: str = ""


@dataclass
class GranularityRecommendation:
    """Recommendation for the best reload granularity for a given change."""

    path: str
    recommended: Granularity
    reason: str
    affected_cards: int = 0
    estimated_cost: int = 0


# ── FractalReloader ─────────────────────────────────────────────────────────

class FractalReloader:
    """Manages hot-reloading at any granularity level.

    Given a root ``ModuleContainer``, the reloader can:
    - Watch specific paths for changes (async)
    - Reload at arbitrary granularity levels
    - Cascade reloads across affected levels
    - Recommend optimal reload strategies
    - Track full reload history
    """

    def __init__(self, root: ModuleContainer) -> None:
        self.root = root
        self._watch_map: dict[str, asyncio.Event] = {}
        self._reload_history: list[ReloadEvent] = []

    # ── Watching (async) ────────────────────────────────────────────────

    async def watch(self, path: str) -> None:
        """Monitor *path* for changes.  Sets the event when a change is detected.

        This is a cooperative async primitive — callers ``await`` the event
        which is set when ``notify_change`` is called.
        """
        if path not in self._watch_map:
            self._watch_map[path] = asyncio.Event()

    def notify_change(self, path: str) -> None:
        """Signal that *path* has changed, waking any watchers."""
        event = self._watch_map.get(path)
        if event is not None:
            event.set()
            # Reset for future watches
            event.clear()

    async def wait_for_change(self, path: str, timeout: float = 30.0) -> bool:
        """Wait for a change on *path*.  Returns True if changed, False on timeout."""
        await self.watch(path)
        try:
            await asyncio.wait_for(self._watch_map[path].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ── Reload ──────────────────────────────────────────────────────────

    async def reload(self, path: str, granularity: Granularity) -> ReloadResult:
        """Reload content at *path* at the given granularity.

        Records the event in history and returns a ``ReloadResult``.
        """
        start = time.monotonic_ns()
        result = self.root.reload_at(path, granularity)
        elapsed = time.monotonic_ns() - start

        event = ReloadEvent(
            timestamp=time.time(),
            path=path,
            granularity=granularity,
            success=result.success,
            cards_reloaded=result.cards_reloaded,
            containers_reloaded=result.containers_reloaded,
            elapsed_ns=elapsed,
            error=result.error,
        )
        self._reload_history.append(event)
        return result

    def reload_sync(self, path: str, granularity: Granularity) -> ReloadResult:
        """Synchronous version of ``reload``."""
        start = time.monotonic_ns()
        result = self.root.reload_at(path, granularity)
        elapsed = time.monotonic_ns() - start

        event = ReloadEvent(
            timestamp=time.time(),
            path=path,
            granularity=granularity,
            success=result.success,
            cards_reloaded=result.cards_reloaded,
            containers_reloaded=result.containers_reloaded,
            elapsed_ns=elapsed,
            error=result.error,
        )
        self._reload_history.append(event)
        return result

    # ── Cascade ─────────────────────────────────────────────────────────

    def reload_cascade(self, path: str) -> list[ReloadResult]:
        """Reload all affected levels from the deepest to the root.

        For example, if *path* resolves to a card inside a pocket inside a bag,
        this reloads: CARD → POCKET → BAG (and optionally higher levels).
        """
        results: list[ReloadResult] = []

        # Build the list of all container ancestors from root to target
        parts = path.split(".")
        cumulative_paths: list[tuple[str, Granularity]] = []

        # Always include the root itself
        cumulative_paths.append((self.root.name, self.root.granularity))

        # Walk from root to find the actual container types along the path
        current = self.root
        for i, part in enumerate(parts):
            if isinstance(current, ModuleContainer):
                next_node = current.get_by_path(".".join(parts[:i + 1]))
                if isinstance(next_node, ModuleContainer):
                    cumulative_paths.append((".".join(parts[:i + 1]), next_node.granularity))
                    current = next_node
                else:
                    break

        # Reload from deepest to shallowest
        for rpath, rgran in reversed(cumulative_paths):
            result = self.root.reload_at(rpath, rgran)
            results.append(result)

        return results

    # ── Strategy ────────────────────────────────────────────────────────

    def _resolve_path(self, path: str):
        """Resolve a path, handling the case where it refers to the root itself."""
        if path == self.root.name or path == "":
            return self.root
        return self.root.get_by_path(path)

    def reload_strategy(self, path: str) -> GranularityRecommendation:
        """Analyze what lives at *path* and recommend the optimal reload granularity.

        Strategy:
        - If *path* points to a single card → reload at CARD level (cheapest)
        - If *path* points to a container with few cards → reload at that container's level
        - If entire subtree has many cards → reload at higher granularity
        """
        target = self._resolve_path(path)
        if target is None:
            return GranularityRecommendation(
                path=path,
                recommended=Granularity.CARD,
                reason=f"Path '{path}' not found",
                estimated_cost=0,
            )

        if isinstance(target, type(None)):
            return GranularityRecommendation(
                path=path,
                recommended=Granularity.CARD,
                reason="Target is None",
                estimated_cost=0,
            )

        # Check if it's a card (from card module)
        from .card import ModuleCard

        if isinstance(target, ModuleCard):
            meta = get_granularity_meta(Granularity.CARD)
            return GranularityRecommendation(
                path=path,
                recommended=Granularity.CARD,
                reason="Single card — cheapest reload",
                affected_cards=1,
                estimated_cost=meta.reload_cost,
            )

        # It's a container
        if isinstance(target, ModuleContainer):
            card_count = self._count_cards(target)
            meta = get_granularity_meta(target.granularity)

            if card_count == 0:
                return GranularityRecommendation(
                    path=path,
                    recommended=target.granularity,
                    reason="Empty container — trivial reload",
                    affected_cards=0,
                    estimated_cost=meta.reload_cost,
                )
            elif card_count == 1:
                # Single card — recommend CARD level even if container is higher
                card_meta = get_granularity_meta(Granularity.CARD)
                return GranularityRecommendation(
                    path=path,
                    recommended=Granularity.CARD,
                    reason="Container has only 1 card — reload at CARD level",
                    affected_cards=1,
                    estimated_cost=card_meta.reload_cost,
                )
            elif card_count <= 5:
                return GranularityRecommendation(
                    path=path,
                    recommended=target.granularity,
                    reason=f"Container has {card_count} cards — reload at container level",
                    affected_cards=card_count,
                    estimated_cost=meta.reload_cost,
                )
            else:
                # Many cards — recommend a higher level
                higher_gran = self._suggest_higher_granularity(target.granularity)
                higher_meta = get_granularity_meta(higher_gran)
                return GranularityRecommendation(
                    path=path,
                    recommended=higher_gran,
                    reason=f"Container has {card_count} cards — recommend higher granularity",
                    affected_cards=card_count,
                    estimated_cost=higher_meta.reload_cost,
                )

        # Fallback
        return GranularityRecommendation(
            path=path,
            recommended=Granularity.CARD,
            reason="Unknown target type",
            estimated_cost=1,
        )

    def _count_cards(self, container: ModuleContainer) -> int:
        """Count total cards in a container subtree."""
        count = len(container.cards)
        for child in container.children.values():
            count += self._count_cards(child)
        return count

    @staticmethod
    def _suggest_higher_granularity(current: Granularity) -> Granularity:
        """Suggest a higher (coarser) granularity for bulk reload."""
        # Go one or two levels up depending on current level
        all_levels = list(Granularity)
        idx = all_levels.index(current)
        if idx >= 2:
            return all_levels[idx - 2]
        elif idx >= 1:
            return all_levels[idx - 1]
        return current

    # ── History ─────────────────────────────────────────────────────────

    def get_reload_history(self, since: float = 0.0) -> list[ReloadEvent]:
        """Return reload events since *since* timestamp (epoch seconds)."""
        return [e for e in self._reload_history if e.timestamp >= since]

    def clear_history(self) -> None:
        """Clear all reload history."""
        self._reload_history.clear()

    @property
    def history(self) -> list[ReloadEvent]:
        """All reload events."""
        return list(self._reload_history)

    # ── Dependency graph ────────────────────────────────────────────────

    def compute_reload_graph(self) -> dict:
        """Build a dependency graph of containers and their relationships.

        Returns a dict mapping each container path to its children paths.
        """
        graph: dict[str, dict] = {}

        def _walk(container: ModuleContainer) -> None:
            entry: dict = {
                "granularity": container.granularity.name,
                "version": container.version,
                "checksum": container.checksum,
                "children": sorted(container.children.keys()),
                "cards": sorted(container.cards.keys()),
            }
            graph[container.path] = entry
            for child in container.children.values():
                _walk(child)

        _walk(self.root)
        return graph
