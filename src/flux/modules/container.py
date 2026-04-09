"""ModuleContainer — nestable container for the fractal hot-reload hierarchy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Union

from .granularity import Granularity
from .card import ModuleCard, CompileResult
from .namespace import ModuleNamespace


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class ReloadResult:
    """Outcome of a reload operation."""

    success: bool
    path: str = ""
    granularity: Granularity = Granularity.CARD
    old_checksum: str = ""
    new_checksum: str = ""
    cards_reloaded: int = 0
    containers_reloaded: int = 0
    error: str = ""


# ── ModuleContainer ─────────────────────────────────────────────────────────

class ModuleContainer:
    """A nestable container that holds modules at a specific granularity.

    The container tree mirrors the fractal hierarchy:

        TRAIN → CARRIAGE → LUGGAGE → BAG → POCKET → WALLET → SLOT → [CARDs]
    """

    __slots__ = (
        "granularity",
        "name",
        "parent",
        "children",
        "cards",
        "version",
        "checksum",
        "compiled_bytecode",
        "_prev_checksum",
        "namespace",
    )

    def __init__(
        self,
        name: str,
        granularity: Granularity,
        parent: Optional[ModuleContainer] = None,
    ) -> None:
        self.granularity = granularity
        self.name = name
        self.parent = parent
        self.children: dict[str, ModuleContainer] = {}
        self.cards: dict[str, ModuleCard] = {}
        self.version: int = 0
        self.checksum: str = ""
        self._prev_checksum: str = ""
        self.compiled_bytecode: Optional[bytes] = None
        self.namespace: ModuleNamespace = ModuleNamespace(
            parent=parent.namespace if parent else None
        )
        self.checksum = self.checksum_tree()

    # ── Full path ───────────────────────────────────────────────────────

    @property
    def path(self) -> str:
        """Dot-separated path from root to this container."""
        parts: list[str] = []
        node: Optional[ModuleContainer] = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return ".".join(reversed(parts))

    # ── Children ────────────────────────────────────────────────────────

    def add_child(self, name: str, child_granularity: Granularity) -> ModuleContainer:
        """Create and attach a child container.  Returns the child."""
        child = ModuleContainer(
            name=name,
            granularity=child_granularity,
            parent=self,
        )
        self.children[name] = child
        self._bump_version()
        return child

    def remove_child(self, name: str) -> Optional[ModuleContainer]:
        """Remove a child container by name.  Returns it or None."""
        child = self.children.pop(name, None)
        if child is not None:
            self._bump_version()
        return child

    # ── Cards ───────────────────────────────────────────────────────────

    def load_card(
        self,
        name: str,
        source: str,
        language: str = "python",
    ) -> ModuleCard:
        """Create a card and attach it to this container."""
        card = ModuleCard(name=name, source=source, language=language)
        self.cards[name] = card
        self._bump_version()
        return card

    def reload_card(self, name: str, new_source: str) -> ReloadResult:
        """Replace the source of a card and recompile (no FIR context here)."""
        card = self.cards.get(name)
        if card is None:
            return ReloadResult(success=False, error=f"Card '{name}' not found")
        old_checksum = card.checksum
        card.source = new_source
        card.checksum = card._compute_checksum()
        card.invalidate()
        card.version += 1
        self._bump_version()
        return ReloadResult(
            success=True,
            path=f"{self.path}.{name}",
            granularity=Granularity.CARD,
            old_checksum=old_checksum,
            new_checksum=card.checksum,
            cards_reloaded=1,
        )

    # ── Reload at arbitrary granularity ─────────────────────────────────

    def reload_at(self, path: str, granularity: Granularity) -> ReloadResult:
        """Reload content at *path* at the given granularity level.

        The path is dot-separated, e.g. ``carriage1.luggageA.bag1.cardX``.
        If *path* matches this container's own name, reloads this container.
        """
        # Handle self-reference (path matches this container's name)
        if path == self.name:
            target: Union[ModuleContainer, ModuleCard, None] = self
        else:
            target = self.get_by_path(path)

        if target is None:
            return ReloadResult(
                success=False,
                path=path,
                granularity=granularity,
                error=f"Path '{path}' not found",
            )

        if isinstance(target, ModuleCard):
            # Reloading a card directly — always CARD level
            card = target
            old_checksum = card.checksum
            card.invalidate()
            card.version += 1
            card.checksum = card._compute_checksum()
            self._bump_version()
            return ReloadResult(
                success=True,
                path=path,
                granularity=Granularity.CARD,
                old_checksum=old_checksum,
                new_checksum=card.checksum,
                cards_reloaded=1,
            )

        # target is a ModuleContainer — invalidate its subtree
        container = target
        old_checksum = container.checksum
        cards_reloaded, containers_reloaded = container._invalidate_subtree()
        self._bump_version()
        return ReloadResult(
            success=True,
            path=path,
            granularity=granularity,
            old_checksum=old_checksum,
            new_checksum=container.checksum_tree(),
            cards_reloaded=cards_reloaded,
            containers_reloaded=containers_reloaded,
        )

    def _invalidate_subtree(self) -> tuple[int, int]:
        """Invalidate all cards/containers in this subtree. Returns (cards, containers)."""
        cards_count = 0
        containers_count = 1  # self
        for card in self.cards.values():
            card.invalidate()
            card.version += 1
            cards_count += 1
        for child in self.children.values():
            c_cards, c_conts = child._invalidate_subtree()
            cards_count += c_cards
            containers_count += c_conts
        self.compiled_bytecode = None
        self._bump_version()
        return cards_count, containers_count

    # ── Path resolution ─────────────────────────────────────────────────

    def get_by_path(self, path: str) -> Union[ModuleContainer, ModuleCard, None]:
        """Resolve a dot-separated *path* to a container or card.

        Examples:
            get_by_path("child1")          → child container
            get_by_path("child1.card_a")   → card in child container
            get_by_path("child1.grandchild.card_b")
        """
        parts = path.split(".")
        current: Union[ModuleContainer, ModuleCard, None] = self
        for part in parts:
            if isinstance(current, ModuleContainer):
                # Try child first, then card
                if part in current.children:
                    current = current.children[part]
                elif part in current.cards:
                    current = current.cards[part]
                else:
                    return None
            else:
                return None  # can't descend into a card
        return current

    # ── Checksum ────────────────────────────────────────────────────────

    def checksum_tree(self) -> str:
        """Compute a recursive hash of the entire subtree."""
        h = hashlib.sha256()
        h.update(self.name.encode())
        h.update(str(self.granularity.value).encode())
        # Cards
        for cname in sorted(self.cards.keys()):
            card = self.cards[cname]
            h.update(cname.encode())
            h.update(card.checksum.encode())
        # Children
        for cname in sorted(self.children.keys()):
            child = self.children[cname]
            h.update(child.checksum_tree().encode())
        return h.hexdigest()[:16]

    # ── Stale detection ─────────────────────────────────────────────────

    def find_stale(self) -> list[str]:
        """Find all containers/cards whose checksum differs from their previous snapshot.

        Each container stores ``_prev_checksum``.  Call ``snapshot_checksums()``
        first to record baselines.
        """
        stale: list[str] = []
        self._find_stale_recursive(stale)
        return stale

    def _find_stale_recursive(self, stale: list[str]) -> None:
        current = self.checksum_tree()
        if self._prev_checksum and current != self._prev_checksum:
            stale.append(self.path)
        for cname, card in self.cards.items():
            if card.version > 0:
                stale.append(f"{self.path}.{cname}")
        for child in self.children.values():
            child._find_stale_recursive(stale)

    def snapshot_checksums(self) -> None:
        """Record current checksums as baseline for later stale detection."""
        self._prev_checksum = self.checksum_tree()
        for child in self.children.values():
            child.snapshot_checksums()

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize the container tree for inspection."""
        result: dict = {
            "name": self.name,
            "granularity": self.granularity.name,
            "version": self.version,
            "checksum": self.checksum,
            "children": {
                name: child.to_dict() for name, child in sorted(self.children.items())
            },
            "cards": {
                name: {
                    "language": card.language,
                    "version": card.version,
                    "checksum": card.checksum,
                    "source_len": len(card.source),
                }
                for name, card in sorted(self.cards.items())
            },
        }
        return result

    # ── Internals ───────────────────────────────────────────────────────

    def _bump_version(self) -> None:
        self.version += 1
        self.checksum = self.checksum_tree()

    def __repr__(self) -> str:
        n_children = len(self.children)
        n_cards = len(self.cards)
        return (
            f"ModuleContainer({self.name!r}, {self.granularity.name}, "
            f"children={n_children}, cards={n_cards}, v={self.version})"
        )
