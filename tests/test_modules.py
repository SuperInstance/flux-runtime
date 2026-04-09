"""Tests for the nested module system — fractal hot-reload hierarchy."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.modules.granularity import (
    Granularity,
    GranularityMeta,
    get_granularity_meta,
)
from flux.modules.card import ModuleCard, CompileResult
from flux.modules.container import ModuleContainer, ReloadResult
from flux.modules.reloader import FractalReloader, ReloadEvent, GranularityRecommendation
from flux.modules.namespace import ModuleNamespace, NameNotFoundError
from flux.fir.types import TypeContext


# ═══════════════════════════════════════════════════════════════════════════
# Granularity tests
# ═══════════════════════════════════════════════════════════════════════════

def test_granularity_enum_values():
    """Granularity enum has exactly 8 levels, TRAIN=0 to CARD=7."""
    assert len(Granularity) == 8
    assert Granularity.TRAIN.value == 0
    assert Granularity.CARRIAGE.value == 1
    assert Granularity.LUGGAGE.value == 2
    assert Granularity.BAG.value == 3
    assert Granularity.POCKET.value == 4
    assert Granularity.WALLET.value == 5
    assert Granularity.SLOT.value == 6
    assert Granularity.CARD.value == 7
    print("  PASS test_granularity_enum_values")


def test_granularity_reload_cost_ordering():
    """reload_cost decreases as granularity value increases."""
    prev_cost = 999
    for g in Granularity:
        meta = get_granularity_meta(g)
        assert meta.reload_cost <= prev_cost, f"{g.name} cost {meta.reload_cost} > {prev_cost}"
        prev_cost = meta.reload_cost
    print("  PASS test_granularity_reload_cost_ordering")


def test_granularity_isolation_range():
    """isolation values are between 0.0 and 1.0."""
    for g in Granularity:
        meta = get_granularity_meta(g)
        assert 0.0 <= meta.isolation <= 1.0, f"{g.name} isolation={meta.isolation}"
    print("  PASS test_granularity_isolation_range")


def test_granularity_isolation_increases_for_larger():
    """Larger units (TRAIN) should be more isolated than smaller (CARD)."""
    train_iso = get_granularity_meta(Granularity.TRAIN).isolation
    card_iso = get_granularity_meta(Granularity.CARD).isolation
    assert train_iso > card_iso
    print("  PASS test_granularity_isolation_increases_for_larger")


def test_granularity_typical_size_ordering():
    """typical_size min values should decrease from TRAIN to CARD."""
    prev_min = float("inf")
    for g in Granularity:
        meta = get_granularity_meta(g)
        assert meta.typical_size[0] <= prev_min, f"{g.name} min={meta.typical_size[0]} > {prev_min}"
        prev_min = meta.typical_size[0]
    print("  PASS test_granularity_typical_size_ordering")


def test_should_reload_to_same_level():
    """should_reload_to at same level returns True."""
    meta = get_granularity_meta(Granularity.POCKET)
    assert meta.should_reload_to(Granularity.POCKET) is True
    print("  PASS test_should_reload_to_same_level")


def test_should_reload_to_deeper_level():
    """should_reload_to at deeper level returns True."""
    meta = get_granularity_meta(Granularity.BAG)
    assert meta.should_reload_to(Granularity.POCKET) is True
    assert meta.should_reload_to(Granularity.CARD) is True
    print("  PASS test_should_reload_to_deeper_level")


def test_should_reload_to_higher_level():
    """should_reload_to at higher level returns False."""
    meta = get_granularity_meta(Granularity.POCKET)
    assert meta.should_reload_to(Granularity.BAG) is False
    assert meta.should_reload_to(Granularity.TRAIN) is False
    print("  PASS test_should_reload_to_higher_level")


def test_should_reload_to_edge_cases():
    """Edge cases: TRAIN should_reload_to(CARD)=True, CARD should_reload_to(TRAIN)=False."""
    assert get_granularity_meta(Granularity.TRAIN).should_reload_to(Granularity.CARD) is True
    assert get_granularity_meta(Granularity.CARD).should_reload_to(Granularity.TRAIN) is False
    print("  PASS test_should_reload_to_edge_cases")


def test_granularity_meta_repr():
    """GranularityMeta repr is informative."""
    meta = get_granularity_meta(Granularity.BAG)
    r = repr(meta)
    assert "BAG" in r
    assert "cost=" in r
    assert "isolation=" in r
    print("  PASS test_granularity_meta_repr")


# ═══════════════════════════════════════════════════════════════════════════
# Container creation and nesting tests
# ═══════════════════════════════════════════════════════════════════════════

def test_container_creation():
    """Create a root container."""
    root = ModuleContainer("root", Granularity.TRAIN)
    assert root.name == "root"
    assert root.granularity == Granularity.TRAIN
    assert root.parent is None
    assert len(root.children) == 0
    assert len(root.cards) == 0
    assert root.version >= 0
    print("  PASS test_container_creation")


def test_container_path_root():
    """Root container path is just its name."""
    root = ModuleContainer("my_train", Granularity.TRAIN)
    assert root.path == "my_train"
    print("  PASS test_container_path_root")


def test_add_child():
    """add_child creates nested containers."""
    root = ModuleContainer("root", Granularity.TRAIN)
    child = root.add_child("car1", Granularity.CARRIAGE)
    assert child.name == "car1"
    assert child.granularity == Granularity.CARRIAGE
    assert child.parent is root
    assert "car1" in root.children
    print("  PASS test_add_child")


def test_nested_child_path():
    """Nested container path includes all ancestors."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    lug = car.add_child("luggage_a", Granularity.LUGGAGE)
    assert lug.path == "root.car1.luggage_a"
    print("  PASS test_nested_child_path")


def test_deep_nesting():
    """Create full 8-level hierarchy: TRAIN→CARD."""
    root = ModuleContainer("T", Granularity.TRAIN)
    car = root.add_child("C", Granularity.CARRIAGE)
    lug = car.add_child("L", Granularity.LUGGAGE)
    bag = lug.add_child("B", Granularity.BAG)
    pock = bag.add_child("P", Granularity.POCKET)
    wall = pock.add_child("W", Granularity.WALLET)
    slot = wall.add_child("S", Granularity.SLOT)
    assert slot.path == "T.C.L.B.P.W.S"
    assert slot.granularity == Granularity.SLOT
    print("  PASS test_deep_nesting")


def test_load_card():
    """load_card creates a card in the container."""
    root = ModuleContainer("root", Granularity.POCKET)
    card = root.load_card("mycard", "print('hello')", language="python")
    assert card.name == "mycard"
    assert card.source == "print('hello')"
    assert card.language == "python"
    assert "mycard" in root.cards
    assert card.checksum != ""
    print("  PASS test_load_card")


def test_get_by_path_child():
    """get_by_path resolves child containers."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.add_child("car1", Granularity.CARRIAGE)
    result = root.get_by_path("car1")
    assert result is not None
    assert isinstance(result, ModuleContainer)
    assert result.name == "car1"
    print("  PASS test_get_by_path_child")


def test_get_by_path_deep():
    """get_by_path resolves deeply nested paths."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    lug = car.add_child("luggage_a", Granularity.LUGGAGE)
    result = root.get_by_path("car1.luggage_a")
    assert result is not None
    assert isinstance(result, ModuleContainer)
    assert result.name == "luggage_a"
    print("  PASS test_get_by_path_deep")


def test_get_by_path_card():
    """get_by_path resolves a card inside a container."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("card_a", "x = 1")
    result = root.get_by_path("card_a")
    assert result is not None
    assert isinstance(result, ModuleCard)
    assert result.name == "card_a"
    print("  PASS test_get_by_path_card")


def test_get_by_path_deep_card():
    """get_by_path resolves card in nested container."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    car.load_card("c1", "x = 1")
    result = root.get_by_path("car1.c1")
    assert isinstance(result, ModuleCard)
    assert result.name == "c1"
    print("  PASS test_get_by_path_deep_card")


def test_get_by_path_not_found():
    """get_by_path returns None for missing paths."""
    root = ModuleContainer("root", Granularity.TRAIN)
    assert root.get_by_path("nonexistent") is None
    assert root.get_by_path("car1.nonexistent") is None
    print("  PASS test_get_by_path_not_found")


def test_remove_child():
    """remove_child detaches a child container."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.add_child("car1", Granularity.CARRIAGE)
    removed = root.remove_child("car1")
    assert removed is not None
    assert removed.name == "car1"
    assert "car1" not in root.children
    assert root.remove_child("nonexistent") is None
    print("  PASS test_remove_child")


def test_container_repr():
    """Container repr shows key info."""
    root = ModuleContainer("root", Granularity.TRAIN)
    r = repr(root)
    assert "root" in r
    assert "TRAIN" in r
    print("  PASS test_container_repr")


# ═══════════════════════════════════════════════════════════════════════════
# Checksum tree and change detection tests
# ═══════════════════════════════════════════════════════════════════════════

def test_checksum_empty_container():
    """Empty container has a non-empty checksum."""
    root = ModuleContainer("root", Granularity.TRAIN)
    assert len(root.checksum) > 0
    print("  PASS test_checksum_empty_container")


def test_checksum_deterministic():
    """Same structure produces same checksum."""
    root1 = ModuleContainer("root", Granularity.TRAIN)
    root1.add_child("a", Granularity.CARRIAGE)
    root2 = ModuleContainer("root", Granularity.TRAIN)
    root2.add_child("a", Granularity.CARRIAGE)
    assert root1.checksum_tree() == root2.checksum_tree()
    print("  PASS test_checksum_deterministic")


def test_checksum_different_names():
    """Different names produce different checksums."""
    r1 = ModuleContainer("aaa", Granularity.TRAIN)
    r2 = ModuleContainer("bbb", Granularity.TRAIN)
    assert r1.checksum_tree() != r2.checksum_tree()
    print("  PASS test_checksum_different_names")


def test_checksum_includes_cards():
    """Checksum changes when a card is added."""
    root = ModuleContainer("root", Granularity.TRAIN)
    cs_before = root.checksum_tree()
    root.load_card("c1", "x = 1")
    cs_after = root.checksum_tree()
    assert cs_before != cs_after
    print("  PASS test_checksum_includes_cards")


def test_checksum_includes_card_content():
    """Checksum changes when card source changes."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.load_card("c1", "x = 1")
    cs_before = root.checksum_tree()
    root.reload_card("c1", "x = 2")
    cs_after = root.checksum_tree()
    assert cs_before != cs_after
    print("  PASS test_checksum_includes_card_content")


def test_find_stale_no_changes():
    """find_stale returns empty list when nothing changed."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.snapshot_checksums()
    assert root.find_stale() == []
    print("  PASS test_find_stale_no_changes")


def test_find_stale_after_card_change():
    """find_stale detects changed cards."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "x = 1")
    root.snapshot_checksums()
    root.reload_card("c1", "y = 2")
    stale = root.find_stale()
    assert len(stale) > 0
    print("  PASS test_find_stale_after_card_change")


def test_find_stale_across_nested_containers():
    """Stale detection works across nested containers."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    car.load_card("c1", "x = 1")
    root.snapshot_checksums()
    car.reload_card("c1", "x = 999")
    stale = root.find_stale()
    assert len(stale) > 0
    print("  PASS test_find_stale_across_nested_containers")


# ═══════════════════════════════════════════════════════════════════════════
# Card compilation and invalidation tests
# ═══════════════════════════════════════════════════════════════════════════

def test_card_checksum_auto():
    """Card checksum is auto-computed from source."""
    card = ModuleCard("c1", "hello world", language="python")
    assert len(card.checksum) == 16
    print("  PASS test_card_checksum_auto")


def test_card_compile_success():
    """Card compile returns success for supported languages."""
    ctx = TypeContext()
    card = ModuleCard("c1", "x = 1", language="python")
    result = card.compile(ctx)
    assert result.success is True
    assert result.error == ""
    assert result.checksum != ""
    assert result.compile_time_ns >= 0
    assert card.version == 1
    print("  PASS test_card_compile_success")


def test_card_compile_fir_language():
    """Card compile with 'fir' language creates FIR module placeholder."""
    ctx = TypeContext()
    card = ModuleCard("c1", "func foo() {}", language="fir")
    result = card.compile(ctx)
    assert result.success is True
    assert card.compiled_fir is not None
    assert card.compiled_bytecode is not None
    print("  PASS test_card_compile_fir_language")


def test_card_invalidate():
    """Invalidate clears compiled artifacts."""
    ctx = TypeContext()
    card = ModuleCard("c1", "func foo() {}", language="fir")
    card.compile(ctx)
    assert card.compiled_fir is not None
    card.invalidate()
    assert card.compiled_fir is None
    assert card.compiled_bytecode is None
    print("  PASS test_card_invalidate")


def test_card_recompile():
    """Recompile replaces source and recompiles."""
    ctx = TypeContext()
    card = ModuleCard("c1", "x = 1", language="python")
    card.compile(ctx)
    v1 = card.version
    cs1 = card.checksum
    result = card.recompile("x = 42", ctx)
    assert result.success is True
    assert card.source == "x = 42"
    assert card.version > v1
    assert card.checksum != cs1
    print("  PASS test_card_recompile")


def test_card_metadata():
    """Compile stores metadata."""
    ctx = TypeContext()
    card = ModuleCard("c1", "x = 1", language="python")
    card.compile(ctx)
    assert card.metadata["language"] == "python"
    assert "last_compiled" in card.metadata
    print("  PASS test_card_metadata")


def test_reload_card_not_found():
    """Reloading non-existent card returns failure."""
    root = ModuleContainer("root", Granularity.POCKET)
    result = root.reload_card("nonexistent", "new source")
    assert result.success is False
    assert "not found" in result.error
    print("  PASS test_reload_card_not_found")


# ═══════════════════════════════════════════════════════════════════════════
# Reloader tests
# ═══════════════════════════════════════════════════════════════════════════

def test_reloader_creation():
    """FractalReloader can be created with a root container."""
    root = ModuleContainer("root", Granularity.TRAIN)
    reloader = FractalReloader(root)
    assert reloader.root is root
    assert len(reloader.history) == 0
    print("  PASS test_reloader_creation")


def test_reloader_reload_sync_success():
    """Sync reload records history."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "x = 1")
    reloader = FractalReloader(root)
    result = reloader.reload_sync("c1", Granularity.CARD)
    assert result.success is True
    assert result.cards_reloaded == 1
    assert len(reloader.history) == 1
    print("  PASS test_reloader_reload_sync_success")


def test_reloader_reload_not_found():
    """Reloading non-existent path returns failure."""
    root = ModuleContainer("root", Granularity.TRAIN)
    reloader = FractalReloader(root)
    result = reloader.reload_sync("nonexistent", Granularity.CARD)
    assert result.success is False
    assert "not found" in result.error
    print("  PASS test_reloader_reload_not_found")


def test_reload_strategy_single_card():
    """Strategy for single card recommends CARD level."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "x = 1")
    reloader = FractalReloader(root)
    rec = reloader.reload_strategy("c1")
    assert rec.recommended == Granularity.CARD
    assert "single card" in rec.reason.lower() or "cheapest" in rec.reason.lower()
    assert rec.affected_cards == 1
    print("  PASS test_reload_strategy_single_card")


def test_reload_strategy_empty_container():
    """Strategy for empty container recommends its own level."""
    root = ModuleContainer("root", Granularity.BAG)
    reloader = FractalReloader(root)
    rec = reloader.reload_strategy("root")
    assert rec.recommended == Granularity.BAG
    assert "empty" in rec.reason.lower() or "trivial" in rec.reason.lower()
    print("  PASS test_reload_strategy_empty_container")


def test_reload_strategy_few_cards():
    """Strategy for container with few cards recommends container level."""
    root = ModuleContainer("root", Granularity.BAG)
    root.load_card("c1", "a = 1")
    root.load_card("c2", "b = 2")
    root.load_card("c3", "c = 3")
    reloader = FractalReloader(root)
    rec = reloader.reload_strategy("root")
    assert rec.recommended == Granularity.BAG
    assert rec.affected_cards == 3
    print("  PASS test_reload_strategy_few_cards")


def test_reload_strategy_many_cards():
    """Strategy for container with many cards recommends higher granularity."""
    root = ModuleContainer("root", Granularity.BAG)
    for i in range(10):
        root.load_card(f"c{i}", f"x = {i}")
    reloader = FractalReloader(root)
    rec = reloader.reload_strategy("root")
    # Should recommend a higher (coarser) granularity
    assert rec.recommended.value < Granularity.BAG.value
    assert rec.affected_cards == 10
    print("  PASS test_reload_strategy_many_cards")


def test_reload_cascade():
    """Cascade reloads from deepest affected to root."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    lug = car.add_child("luggage_a", Granularity.LUGGAGE)
    lug.load_card("c1", "x = 1")
    reloader = FractalReloader(root)
    results = reloader.reload_cascade("car1.luggage_a")
    assert len(results) >= 2  # at least luggage_a + car1
    for r in results:
        assert r.success is True
    print("  PASS test_reload_cascade")


def test_reload_history_tracking():
    """History records all reloads with timestamps."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "a = 1")
    root.load_card("c2", "b = 2")
    reloader = FractalReloader(root)
    reloader.reload_sync("c1", Granularity.CARD)
    reloader.reload_sync("c2", Granularity.CARD)
    history = reloader.get_reload_history()
    assert len(history) == 2
    # Both events should have valid timestamps
    assert history[0].timestamp > 0
    assert history[1].timestamp > 0
    print("  PASS test_reload_history_tracking")


def test_reload_history_since():
    """get_reload_history(since) filters by timestamp."""
    import time
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "a = 1")
    reloader = FractalReloader(root)
    reloader.reload_sync("c1", Granularity.CARD)
    time.sleep(0.01)
    now = time.time()
    reloader.reload_sync("c1", Granularity.CARD)
    recent = reloader.get_reload_history(since=now)
    assert len(recent) >= 1
    print("  PASS test_reload_history_since")


def test_clear_history():
    """clear_history removes all events."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "a = 1")
    reloader = FractalReloader(root)
    reloader.reload_sync("c1", Granularity.CARD)
    reloader.clear_history()
    assert len(reloader.history) == 0
    print("  PASS test_clear_history")


def test_compute_reload_graph():
    """compute_reload_graph returns the full tree structure."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    car.load_card("c1", "x = 1")
    reloader = FractalReloader(root)
    graph = reloader.compute_reload_graph()
    assert "root" in graph
    assert "root.car1" in graph
    assert graph["root.car1"]["cards"] == ["c1"]
    assert graph["root"]["children"] == ["car1"]
    print("  PASS test_compute_reload_graph")


def test_reload_event_fields():
    """ReloadEvent has all expected fields."""
    event = ReloadEvent(
        timestamp=1000.0,
        path="root.c1",
        granularity=Granularity.CARD,
        success=True,
        cards_reloaded=1,
        containers_reloaded=0,
        elapsed_ns=500,
        error="",
    )
    assert event.timestamp == 1000.0
    assert event.path == "root.c1"
    assert event.granularity == Granularity.CARD
    assert event.success is True
    print("  PASS test_reload_event_fields")


# ═══════════════════════════════════════════════════════════════════════════
# Namespace isolation tests
# ═══════════════════════════════════════════════════════════════════════════

def test_namespace_bind_resolve():
    """Bind and resolve in same scope."""
    ns = ModuleNamespace()
    ns.bind("x", 42)
    assert ns.resolve("x") == 42
    print("  PASS test_namespace_bind_resolve")


def test_namespace_parent_resolution():
    """Resolve walks up to parent scope."""
    parent = ModuleNamespace()
    parent.bind("x", 99)
    child = parent.child_scope()
    assert child.resolve("x") == 99
    print("  PASS test_namespace_parent_resolution")


def test_namespace_child_shadows_parent():
    """Child binding shadows parent."""
    parent = ModuleNamespace()
    parent.bind("x", 99)
    child = parent.child_scope()
    child.bind("x", 1)
    assert child.resolve("x") == 1
    assert parent.resolve("x") == 99  # parent unchanged
    print("  PASS test_namespace_child_shadows_parent")


def test_namespace_isolation():
    """Sibling scopes don't leak."""
    parent = ModuleNamespace()
    parent.bind("shared", "ok")
    child_a = parent.child_scope()
    child_b = parent.child_scope()
    child_a.bind("a_only", 10)
    assert child_a.contains("a_only") is True
    assert child_b.contains("a_only") is False
    assert child_b.resolve("shared") == "ok"  # shared still visible
    print("  PASS test_namespace_isolation")


def test_namespace_not_found_raises():
    """NameNotFoundError raised for missing names."""
    ns = ModuleNamespace()
    try:
        ns.resolve("missing")
        assert False, "Should have raised"
    except NameNotFoundError:
        pass
    print("  PASS test_namespace_not_found_raises")


def test_namespace_resolve_local():
    """resolve_local only checks current scope."""
    parent = ModuleNamespace()
    parent.bind("x", 99)
    child = parent.child_scope()
    try:
        child.resolve_local("x")
        assert False, "Should have raised"
    except NameNotFoundError:
        pass
    print("  PASS test_namespace_resolve_local")


def test_namespace_snapshot_restore():
    """Snapshot and restore preserve bindings."""
    ns = ModuleNamespace()
    ns.bind("a", 1)
    ns.bind("b", 2)
    snap = ns.snapshot()
    ns.bind("c", 3)
    assert len(ns.all_names()) == 3
    ns.restore(snap)
    assert len(ns.all_names()) == 2
    assert "c" not in ns.all_names()
    print("  PASS test_namespace_snapshot_restore")


def test_namespace_unbind():
    """unbind removes a binding."""
    ns = ModuleNamespace()
    ns.bind("x", 42)
    ns.unbind("x")
    assert ns.contains("x") is False
    print("  PASS test_namespace_unbind")


def test_namespace_repr():
    """Namespace repr shows binding count."""
    ns = ModuleNamespace()
    ns.bind("a", 1)
    r = repr(ns)
    assert "1" in r
    print("  PASS test_namespace_repr")


def test_namespace_linked_to_container():
    """Container creates a namespace that inherits from parent."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.namespace.bind("root_var", "hello")
    child = root.add_child("car1", Granularity.CARRIAGE)
    assert child.namespace.resolve("root_var") == "hello"
    print("  PASS test_namespace_linked_to_container")


# ═══════════════════════════════════════════════════════════════════════════
# Serialization tests
# ═══════════════════════════════════════════════════════════════════════════

def test_to_dict_basic():
    """to_dict serializes basic container."""
    root = ModuleContainer("root", Granularity.TRAIN)
    d = root.to_dict()
    assert d["name"] == "root"
    assert d["granularity"] == "TRAIN"
    assert d["version"] >= 0
    assert d["children"] == {}
    assert d["cards"] == {}
    print("  PASS test_to_dict_basic")


def test_to_dict_with_children_and_cards():
    """to_dict serializes nested structure."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    car.load_card("c1", "x = 1")
    d = root.to_dict()
    assert "car1" in d["children"]
    assert d["children"]["car1"]["cards"]["c1"]["language"] == "python"
    assert d["children"]["car1"]["cards"]["c1"]["source_len"] == 5
    print("  PASS test_to_dict_with_children_and_cards")


def test_to_dict_deep():
    """to_dict handles deep nesting."""
    root = ModuleContainer("T", Granularity.TRAIN)
    c = root.add_child("C", Granularity.CARRIAGE)
    l = c.add_child("L", Granularity.LUGGAGE)
    l.load_card("card_a", "hello")
    d = root.to_dict()
    assert "L" in d["children"]["C"]["children"]
    assert "card_a" in d["children"]["C"]["children"]["L"]["cards"]
    print("  PASS test_to_dict_deep")


# ═══════════════════════════════════════════════════════════════════════════
# Integration / edge case tests
# ═══════════════════════════════════════════════════════════════════════════

def test_version_bumps_on_add_child():
    """Version increments when a child is added."""
    root = ModuleContainer("root", Granularity.TRAIN)
    v0 = root.version
    root.add_child("car1", Granularity.CARRIAGE)
    assert root.version > v0
    print("  PASS test_version_bumps_on_add_child")


def test_version_bumps_on_load_card():
    """Version increments when a card is loaded."""
    root = ModuleContainer("root", Granularity.POCKET)
    v0 = root.version
    root.load_card("c1", "x = 1")
    assert root.version > v0
    print("  PASS test_version_bumps_on_load_card")


def test_version_bumps_on_reload_card():
    """Version increments when a card is reloaded."""
    root = ModuleContainer("root", Granularity.POCKET)
    root.load_card("c1", "x = 1")
    v0 = root.version
    root.reload_card("c1", "x = 2")
    assert root.version > v0
    print("  PASS test_version_bumps_on_reload_card")


def test_reload_at_container_level():
    """reload_at on a container invalidates its entire subtree."""
    root = ModuleContainer("root", Granularity.TRAIN)
    car = root.add_child("car1", Granularity.CARRIAGE)
    car.load_card("c1", "x = 1")
    car.load_card("c2", "y = 2")
    result = root.reload_at("car1", Granularity.CARRIAGE)
    assert result.success is True
    assert result.cards_reloaded == 2
    assert result.containers_reloaded >= 1
    print("  PASS test_reload_at_container_level")


def test_multiple_children():
    """Container can have multiple children."""
    root = ModuleContainer("root", Granularity.TRAIN)
    root.add_child("car1", Granularity.CARRIAGE)
    root.add_child("car2", Granularity.CARRIAGE)
    root.add_child("car3", Granularity.CARRIAGE)
    assert len(root.children) == 3
    d = root.to_dict()
    assert len(d["children"]) == 3
    print("  PASS test_multiple_children")


def test_granularity_recommendation_not_found():
    """Strategy for non-existent path returns recommendation with CARD."""
    root = ModuleContainer("root", Granularity.TRAIN)
    reloader = FractalReloader(root)
    rec = reloader.reload_strategy("nonexistent")
    assert rec.recommended == Granularity.CARD
    assert "not found" in rec.reason.lower()
    print("  PASS test_granularity_recommendation_not_found")


def test_reload_result_fields():
    """ReloadResult has all expected fields."""
    result = ReloadResult(
        success=True,
        path="root.c1",
        granularity=Granularity.CARD,
        old_checksum="aaaa",
        new_checksum="bbbb",
        cards_reloaded=1,
        containers_reloaded=0,
        error="",
    )
    assert result.success is True
    assert result.old_checksum == "aaaa"
    assert result.new_checksum == "bbbb"
    print("  PASS test_reload_result_fields")


def test_module_card_version_increments():
    """Card version starts at 0 and increments on compile."""
    ctx = TypeContext()
    card = ModuleCard("c1", "x = 1", language="python")
    assert card.version == 0
    card.compile(ctx)
    assert card.version == 1
    card.recompile("x = 2", ctx)
    assert card.version == 2
    print("  PASS test_module_card_version_increments")


if __name__ == "__main__":
    # ── Granularity ─────────────────────────────────────────────────
    test_granularity_enum_values()
    test_granularity_reload_cost_ordering()
    test_granularity_isolation_range()
    test_granularity_isolation_increases_for_larger()
    test_granularity_typical_size_ordering()
    test_should_reload_to_same_level()
    test_should_reload_to_deeper_level()
    test_should_reload_to_higher_level()
    test_should_reload_to_edge_cases()
    test_granularity_meta_repr()

    # ── Container ───────────────────────────────────────────────────
    test_container_creation()
    test_container_path_root()
    test_add_child()
    test_nested_child_path()
    test_deep_nesting()
    test_load_card()
    test_get_by_path_child()
    test_get_by_path_deep()
    test_get_by_path_card()
    test_get_by_path_deep_card()
    test_get_by_path_not_found()
    test_remove_child()
    test_container_repr()

    # ── Checksum / Stale ────────────────────────────────────────────
    test_checksum_empty_container()
    test_checksum_deterministic()
    test_checksum_different_names()
    test_checksum_includes_cards()
    test_checksum_includes_card_content()
    test_find_stale_no_changes()
    test_find_stale_after_card_change()
    test_find_stale_across_nested_containers()

    # ── Card ────────────────────────────────────────────────────────
    test_card_checksum_auto()
    test_card_compile_success()
    test_card_compile_fir_language()
    test_card_invalidate()
    test_card_recompile()
    test_card_metadata()
    test_reload_card_not_found()

    # ── Reloader ────────────────────────────────────────────────────
    test_reloader_creation()
    test_reloader_reload_sync_success()
    test_reloader_reload_not_found()
    test_reload_strategy_single_card()
    test_reload_strategy_empty_container()
    test_reload_strategy_few_cards()
    test_reload_strategy_many_cards()
    test_reload_cascade()
    test_reload_history_tracking()
    test_reload_history_since()
    test_clear_history()
    test_compute_reload_graph()
    test_reload_event_fields()

    # ── Namespace ───────────────────────────────────────────────────
    test_namespace_bind_resolve()
    test_namespace_parent_resolution()
    test_namespace_child_shadows_parent()
    test_namespace_isolation()
    test_namespace_not_found_raises()
    test_namespace_resolve_local()
    test_namespace_snapshot_restore()
    test_namespace_unbind()
    test_namespace_repr()
    test_namespace_linked_to_container()

    # ── Serialization ───────────────────────────────────────────────
    test_to_dict_basic()
    test_to_dict_with_children_and_cards()
    test_to_dict_deep()

    # ── Integration / edge cases ────────────────────────────────────
    test_version_bumps_on_add_child()
    test_version_bumps_on_load_card()
    test_version_bumps_on_reload_card()
    test_reload_at_container_level()
    test_multiple_children()
    test_granularity_recommendation_not_found()
    test_reload_result_fields()
    test_module_card_version_increments()

    print("\n✓ All module system tests passed!")
