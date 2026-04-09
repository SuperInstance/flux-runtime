"""ModuleNamespace — isolated namespace for module containers."""

from __future__ import annotations
from typing import Any, Optional


class NameNotFoundError(KeyError):
    """Raised when a name cannot be resolved in a namespace chain."""

    pass


class ModuleNamespace:
    """Isolated namespace for a module container.

    Namespaces form a parent–child chain.  ``resolve`` walks up the chain
    to find a binding, while ``bind`` always writes into the local scope.
    """

    __slots__ = ("_bindings", "_parent")

    def __init__(self, parent: Optional[ModuleNamespace] = None) -> None:
        self._bindings: dict[str, Any] = {}
        self._parent = parent

    # ── Mutations ───────────────────────────────────────────────────────

    def bind(self, name: str, value: Any) -> None:
        """Bind *name* to *value* in this (local) scope."""
        self._bindings[name] = value

    def unbind(self, name: str) -> None:
        """Remove *name* from this scope.  Raises KeyError if absent."""
        del self._bindings[name]

    # ── Resolution ──────────────────────────────────────────────────────

    def resolve(self, name: str) -> Any:
        """Look up *name*, walking up the parent chain if needed.

        Raises ``NameNotFoundError`` if the name is not found anywhere.
        """
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.resolve(name)
        raise NameNotFoundError(name)

    def resolve_local(self, name: str) -> Any:
        """Look up *name* in this scope only (no parent walk)."""
        if name in self._bindings:
            return self._bindings[name]
        raise NameNotFoundError(name)

    def contains(self, name: str) -> bool:
        """Return True if *name* is bound in this scope or any parent."""
        if name in self._bindings:
            return True
        if self._parent is not None:
            return self._parent.contains(name)
        return False

    # ── Scoping ─────────────────────────────────────────────────────────

    def child_scope(self) -> ModuleNamespace:
        """Create a new child namespace with *self* as parent."""
        return ModuleNamespace(parent=self)

    # ── Snapshot / Restore ──────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the local bindings dict."""
        return dict(self._bindings)

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Replace all local bindings with *snapshot*."""
        self._bindings = dict(snapshot)

    # ── Introspection ───────────────────────────────────────────────────

    def all_names(self) -> list[str]:
        """Return all locally-bound names (excluding parent scope)."""
        return list(self._bindings.keys())

    def __repr__(self) -> str:
        parent = "None" if self._parent is None else "…"
        return f"ModuleNamespace(bindings={len(self._bindings)}, parent={parent})"
