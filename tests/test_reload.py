"""Hot code reload tests."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.reload.hot_loader import ModuleVersion, HotLoader


def test_version_creation():
    v = ModuleVersion.create(0, b"\x01\x02", ["f1", "f2"], source="hello")
    assert v.version_id == 0
    assert v.function_names == ["f1", "f2"]
    assert v.source_hash != ""
    assert v.parent_version_id is None
    print("  PASS test_version_creation")


def test_load_active():
    loader = HotLoader()
    v1 = loader.load("mod1", b"\x01", ["f1"])
    v2 = loader.load("mod1", b"\x02", ["f1"])
    assert loader.get_active("mod1") is v2
    assert loader.get_version_history("mod1") == [v1, v2]
    print("  PASS test_load_active")


def test_dual_version():
    loader = HotLoader()
    v1 = loader.load("mod1", b"\x01", ["f1"])
    loader.enter_call("mod1")  # uses v1
    v2 = loader.load("mod1", b"\x02", ["f1"])
    # v1 still tracked
    assert loader.get_version_history("mod1") == [v1, v2]
    loader.exit_call(v1.version_id)
    loader.gc("mod1")  # v1 has 0 calls now
    assert loader.get_version_history("mod1") == [v2]
    print("  PASS test_dual_version")


def test_rollback():
    loader = HotLoader()
    v1 = loader.load("mod1", b"\x01", ["f1"])
    v2 = loader.load("mod1", b"\x02", ["f1"])
    v3 = loader.load("mod1", b"\x03", ["f1"])
    rolled = loader.rollback("mod1")
    assert rolled is v2
    assert loader.get_active("mod1") is v2
    print("  PASS test_rollback")


if __name__ == "__main__":
    test_version_creation()
    test_load_active()
    test_dual_version()
    test_rollback()
    print("All reload tests passed!")
