"""Tests for vocabulary signaling system."""

import sys
sys.path.insert(0, "src")

import os
import json
import tempfile
import shutil
from flux.open_interp.vocab_signal import (
    VocabManifest,
    VocabInfo,
    Tombstone,
    VocabCompatibility,
    RepoSignaler
)


def test_vocab_manifest_creation():
    """Test creating a basic VocabManifest."""
    manifest = VocabManifest(agent_name="test_agent")
    assert manifest.agent_name == "test_agent"
    assert len(manifest.vocabularies) == 0
    assert len(manifest.tombstones) == 0


def test_vocab_manifest_add_vocabulary():
    """Test adding vocabularies to a manifest."""
    manifest = VocabManifest(agent_name="test_agent")

    manifest.add_vocabulary(
        name="basic",
        pattern_count=5,
        version="1.0.0",
        content="test content"
    )

    assert len(manifest.vocabularies) == 1
    assert manifest.vocabularies[0].name == "basic"
    assert manifest.vocabularies[0].pattern_count == 5
    assert manifest.vocabularies[0].version == "1.0.0"
    assert manifest.vocabularies[0].sha256 != ""


def test_vocab_manifest_add_tombstone():
    """Test adding tombstones to a manifest."""
    manifest = VocabManifest(agent_name="test_agent")

    manifest.add_tombstone(
        name="old_vocab",
        reason="deprecated"
    )

    assert len(manifest.tombstones) == 1
    assert manifest.tombstones[0].name == "old_vocab"
    assert manifest.tombstones[0].reason == "deprecated"
    assert manifest.tombstones[0].pruned_at != ""


def test_vocab_manifest_generate():
    """Test generating manifest summary."""
    manifest = VocabManifest(agent_name="test_agent")

    manifest.add_vocabulary("basic", 5, version="1.0.0", content="test")
    manifest.add_vocabulary("math", 3, version="2.0.0", content="math content")
    manifest.add_tombstone("old", "deprecated")

    summary = manifest.generate()

    assert summary["agent_name"] == "test_agent"
    assert summary["vocab_count"] == 2
    assert summary["total_patterns"] == 8
    assert summary["tombstone_count"] == 1
    assert "generated_at" in summary
    assert len(summary["vocabularies"]) == 2
    assert len(summary["tombstones"]) == 1


def test_vocab_manifest_save_and_load():
    """Test saving and loading manifest from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = VocabManifest(agent_name="test_agent")

        manifest.add_vocabulary("basic", 5, version="1.0.0", content="test content")
        manifest.add_tombstone("old", "deprecated")

        # Save
        path = os.path.join(tmpdir, "manifest.json")
        manifest.save(path)

        # Verify file exists
        assert os.path.exists(path)

        # Load
        loaded = VocabManifest.load(path)

        assert loaded.agent_name == "test_agent"
        assert len(loaded.vocabularies) == 1
        assert loaded.vocabularies[0].name == "basic"
        assert len(loaded.tombstones) == 1
        assert loaded.tombstones[0].name == "old"


def test_vocab_info_compute_hash():
    """Test hash computation for vocabulary content."""
    vocab = VocabInfo(name="test", pattern_count=1)
    vocab.compute_hash("test content")

    assert vocab.sha256 != ""
    assert len(vocab.sha256) == 64

    # Same content should produce same hash
    vocab2 = VocabInfo(name="test2", pattern_count=1)
    vocab2.compute_hash("test content")
    assert vocab.sha256 == vocab2.sha256

    # Different content should produce different hash
    vocab3 = VocabInfo(name="test3", pattern_count=1)
    vocab3.compute_hash("different content")
    assert vocab.sha256 != vocab3.sha256


def test_vocab_compatibility_identical():
    """Test compatibility of identical manifests."""
    manifest_a = VocabManifest(agent_name="agent_a")
    manifest_a.add_vocabulary("basic", 5)
    manifest_a.add_vocabulary("math", 3)

    manifest_b = VocabManifest(agent_name="agent_b")
    manifest_b.add_vocabulary("basic", 5)
    manifest_b.add_vocabulary("math", 3)

    result = VocabCompatibility.compare(manifest_a, manifest_b)

    assert result["shared_count"] == 2
    assert result["unique_to_a_count"] == 0
    assert result["unique_to_b_count"] == 0
    assert result["compatibility_score"] == 1.0
    assert set(result["shared_vocabularies"]) == {"basic", "math"}


def test_vocab_compatibility_no_overlap():
    """Test compatibility of completely different manifests."""
    manifest_a = VocabManifest(agent_name="agent_a")
    manifest_a.add_vocabulary("basic", 5)

    manifest_b = VocabManifest(agent_name="agent_b")
    manifest_b.add_vocabulary("math", 3)

    result = VocabCompatibility.compare(manifest_a, manifest_b)

    assert result["shared_count"] == 0
    assert result["unique_to_a_count"] == 1
    assert result["unique_to_b_count"] == 1
    assert result["compatibility_score"] == 0.0
    assert result["unique_to_a"] == ["basic"]
    assert result["unique_to_b"] == ["math"]


def test_vocab_compatibility_partial_overlap():
    """Test compatibility with partial overlap."""
    manifest_a = VocabManifest(agent_name="agent_a")
    manifest_a.add_vocabulary("basic", 5)
    manifest_a.add_vocabulary("math", 3)
    manifest_a.add_vocabulary("custom", 2)

    manifest_b = VocabManifest(agent_name="agent_b")
    manifest_b.add_vocabulary("basic", 5)
    manifest_b.add_vocabulary("math", 3)
    manifest_b.add_vocabulary("special", 4)

    result = VocabCompatibility.compare(manifest_a, manifest_b)

    assert result["shared_count"] == 2
    assert result["unique_to_a_count"] == 1
    assert result["unique_to_b_count"] == 1
    assert result["compatibility_score"] == 0.5
    assert set(result["shared_vocabularies"]) == {"basic", "math"}
    assert result["unique_to_a"] == ["custom"]
    assert result["unique_to_b"] == ["special"]


def test_vocab_compatibility_empty_manifests():
    """Test compatibility when one or both manifests are empty."""
    manifest_a = VocabManifest(agent_name="agent_a")
    manifest_a.add_vocabulary("basic", 5)

    manifest_b = VocabManifest(agent_name="agent_b")

    result = VocabCompatibility.compare(manifest_a, manifest_b)

    assert result["shared_count"] == 0
    assert result["unique_to_a_count"] == 1
    assert result["unique_to_b_count"] == 0
    assert result["compatibility_score"] == 0.0


def test_repo_signaler_invalid_dir():
    """Test RepoSignaler with invalid directory."""
    manifest = RepoSignaler.scan_repo("/nonexistent/path", "test_agent")
    assert manifest.agent_name == "test_agent"
    assert len(manifest.vocabularies) == 0

    dialect = RepoSignaler.detect_dialect("/nonexistent/path")
    assert dialect == "unknown"

    card = RepoSignaler.business_card("/nonexistent/path")
    assert "Invalid" in card


def test_repo_signaler_scan_real_vocab_files():
    """Test RepoSignaler scanning real vocabulary files."""
    # Scan the actual vocabularies directory
    vocab_dir = "vocabularies"

    if not os.path.isdir(vocab_dir):
        return  # Skip if directory doesn't exist

    manifest = RepoSignaler.scan_repo(vocab_dir, "test_agent")

    assert manifest.agent_name == "test_agent"
    assert len(manifest.vocabularies) > 0

    # Check that we found some vocabularies
    vocab_names = [v.name for v in manifest.vocabularies]
    assert any("basic" in name.lower() or "l0" in name.lower() for name in vocab_names)


def test_repo_signaler_parse_ese_file():
    """Test parsing .ese file format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test .ese file
        ese_content = """## pattern: self is $agent_id
## assembly: MOVI R0, ${agent_id}; HALT
## description: Register agent identity.

## pattern: other is $agent_id
## assembly: MOVI R1, ${agent_id}; HALT
## description: Recognize another agent.
"""
        ese_path = os.path.join(tmpdir, "test.ese")
        with open(ese_path, 'w') as f:
            f.write(ese_content)

        vocab_info = RepoSignaler._parse_vocab_file(ese_path)

        assert vocab_info is not None
        assert vocab_info.name == "test"
        assert vocab_info.pattern_count == 2
        assert vocab_info.sha256 != ""


def test_repo_signaler_parse_fluxvocab_file():
    """Test parsing .fluxvocab file format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test .fluxvocab file
        fluxvocab_content = """---
pattern: "load $val into R$reg"
expand: |
    MOVI R${reg}, ${val}
    HALT
result: R0
---
pattern: "what is $a + $b"
expand: |
    MOVI R0, ${a}
    MOVI R1, ${b}
    IADD R0, R0, R1
    HALT
result: R0
"""
        fluxvocab_path = os.path.join(tmpdir, "test.fluxvocab")
        with open(fluxvocab_path, 'w') as f:
            f.write(fluxvocab_content)

        vocab_info = RepoSignaler._parse_vocab_file(fluxvocab_path)

        assert vocab_info is not None
        assert vocab_info.name == "test"
        assert vocab_info.pattern_count == 2
        assert vocab_info.sha256 != ""


def test_repo_signaler_detect_dialect_core():
    """Test dialect detection for core/basic vocabularies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create core vocabularies
        core_dir = os.path.join(tmpdir, "core")
        os.makedirs(core_dir)

        with open(os.path.join(core_dir, "basic.fluxvocab"), 'w') as f:
            f.write("pattern: test\n")

        dialect = RepoSignaler.detect_dialect(tmpdir)
        assert "core" in dialect.lower()


def test_repo_signaler_detect_dialect_math():
    """Test dialect detection for math vocabularies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create math vocabularies
        math_dir = os.path.join(tmpdir, "math")
        os.makedirs(math_dir)

        with open(os.path.join(math_dir, "arithmetic.fluxvocab"), 'w') as f:
            f.write("pattern: test\n")

        dialect = RepoSignaler.detect_dialect(tmpdir)
        assert "math" in dialect.lower()


def test_repo_signaler_business_card():
    """Test business card generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test vocabularies
        with open(os.path.join(tmpdir, "basic.fluxvocab"), 'w') as f:
            f.write('pattern: "test"\n')

        with open(os.path.join(tmpdir, "math.ese"), 'w') as f:
            f.write('## pattern: test\n')

        card = RepoSignaler.business_card(tmpdir)

        assert "FLUX VOCABULARY BUSINESS CARD" in card
        assert "Dialect:" in card
        assert "Vocabularies:" in card
        assert "VOCABULARIES:" in card
        assert "basic" in card or "math" in card


def test_repo_signaler_business_card_empty_dir():
    """Test business card with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        card = RepoSignaler.business_card(tmpdir)

        assert "FLUX VOCABULARY BUSINESS CARD" in card
        assert "Dialect:" in card
        assert "Vocabularies: 0" in card
        assert "Total Patterns: 0" in card


def test_full_workflow():
    """Test complete workflow: scan, save, load, compare."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test vocabulary files
        vocab_dir = os.path.join(tmpdir, "vocabularies")
        os.makedirs(vocab_dir)

        with open(os.path.join(vocab_dir, "basic.fluxvocab"), 'w') as f:
            f.write('pattern: "test1"\n---\npattern: "test2"\n')

        with open(os.path.join(vocab_dir, "math.fluxvocab"), 'w') as f:
            f.write('pattern: "add"\n')

        # Scan repo
        manifest_a = RepoSignaler.scan_repo(vocab_dir, "agent_a")

        # Save and load
        manifest_path = os.path.join(tmpdir, "manifest.json")
        manifest_a.save(manifest_path)
        manifest_b = VocabManifest.load(manifest_path)

        # Compare
        compat = VocabCompatibility.compare(manifest_a, manifest_b)

        assert compat["compatibility_score"] == 1.0
        assert len(compat["shared_vocabularies"]) == 2


def test_tombstone_persistence():
    """Test that tombstones persist through save/load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = VocabManifest(agent_name="test_agent")

        manifest.add_vocabulary("basic", 5)
        manifest.add_tombstone("old_vocab", "deprecated")
        manifest.add_tombstone("another_old", "obsolete")

        path = os.path.join(tmpdir, "manifest.json")
        manifest.save(path)

        loaded = VocabManifest.load(path)

        assert len(loaded.tombstones) == 2
        assert loaded.tombstones[0].name == "old_vocab"
        assert loaded.tombstones[0].reason == "deprecated"
        assert loaded.tombstones[1].name == "another_old"
        assert loaded.tombstones[1].reason == "obsolete"
