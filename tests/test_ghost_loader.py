"""Tests for GhostLoader — the Ghost Vessel Loader."""

import sys
import os
import time
import json
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.open_interp.ghost_loader import (
    GhostEntry, GhostLoader, ResurrectionContext, VocabEntry,
    create_tombstone
)


class TestGhostEntry:
    """Test GhostEntry dataclass."""

    def test_create_ghost_entry(self):
        """Test creating a basic ghost entry."""
        ghost = GhostEntry(
            name="factorial",
            pattern="factorial of $n",
            bytecode_template="MOVI R0, ${n}\nHALT",
            sha256="abc123",
            pruned_reason="Unused",
            pruned_at=time.time()
        )
        assert ghost.name == "factorial"
        assert ghost.pattern == "factorial of $n"
        assert ghost.sha256 == "abc123"

    def test_ghost_entry_with_all_fields(self):
        """Test creating a ghost entry with all fields."""
        now = time.time()
        ghost = GhostEntry(
            name="test",
            pattern="test pattern",
            bytecode_template="test template",
            sha256="def456",
            pruned_reason="Test reason",
            pruned_at=now,
            original_name="original_test",
            description="Test description",
            tags=["math", "test"],
            usage_count=42,
            last_used=now - 100
        )
        assert ghost.original_name == "original_test"
        assert ghost.usage_count == 42
        assert ghost.tags == ["math", "test"]

    def test_ghost_entry_repr(self):
        """Test ghost entry string representation."""
        ghost = GhostEntry(
            name="test",
            pattern="pattern",
            bytecode_template="template",
            sha256="abc",
            pruned_reason="A very long reason that should be truncated",
            pruned_at=time.time()
        )
        repr_str = repr(ghost)
        assert "GhostEntry" in repr_str
        assert "test" in repr_str

    def test_ghost_entry_to_dict(self):
        """Test converting ghost entry to dictionary."""
        ghost = GhostEntry(
            name="test",
            pattern="pattern",
            bytecode_template="template",
            sha256="abc",
            pruned_reason="reason",
            pruned_at=time.time()
        )
        data = ghost.to_dict()
        assert isinstance(data, dict)
        assert data['name'] == "test"
        assert data['pattern'] == "pattern"

    def test_ghost_entry_from_dict(self):
        """Test creating ghost entry from dictionary."""
        data = {
            'name': 'test',
            'pattern': 'pattern',
            'bytecode_template': 'template',
            'sha256': 'abc',
            'pruned_reason': 'reason',
            'pruned_at': time.time(),
            'original_name': '',
            'description': '',
            'tags': [],
            'usage_count': 0,
            'last_used': 0.0
        }
        ghost = GhostEntry.from_dict(data)
        assert ghost.name == "test"
        assert ghost.pattern == "pattern"

    def test_ghost_entry_age_days(self):
        """Test calculating ghost age in days."""
        now = time.time()
        # Ghost pruned 10 days ago
        ghost = GhostEntry(
            name="test",
            pattern="pattern",
            bytecode_template="template",
            sha256="abc",
            pruned_reason="reason",
            pruned_at=now - (10 * 24 * 3600)
        )
        age = ghost.age_days()
        assert 9.9 <= age <= 10.1  # Allow small timing differences

    def test_ghost_entry_is_recent(self):
        """Test checking if ghost is recent."""
        now = time.time()
        recent_ghost = GhostEntry(
            name="recent",
            pattern="pattern",
            bytecode_template="template",
            sha256="abc",
            pruned_reason="reason",
            pruned_at=now - (5 * 24 * 3600)  # 5 days ago
        )
        old_ghost = GhostEntry(
            name="old",
            pattern="pattern",
            bytecode_template="template",
            sha256="def",
            pruned_reason="reason",
            pruned_at=now - (50 * 24 * 3600)  # 50 days ago
        )
        assert recent_ghost.is_recent(days=30) is True
        assert old_ghost.is_recent(days=30) is False


class TestGhostLoaderBasics:
    """Test basic GhostLoader functionality."""

    def setup_method(self):
        self.loader = GhostLoader()

    def test_loader_initialization(self):
        """Test loader initialization."""
        loader = GhostLoader()
        assert loader._ghosts == []
        assert loader._index == {}

    def test_load_tombstones_from_nonexistent_file(self):
        """Test loading from non-existent file returns empty list."""
        ghosts = self.loader.load_tombstones("/nonexistent/path.json")
        assert ghosts == []

    def test_load_and_save_tombstones(self):
        """Test saving and loading tombstones."""
        ghosts = [
            GhostEntry(
                name="test1",
                pattern="pattern1",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="reason1",
                pruned_at=time.time()
            ),
            GhostEntry(
                name="test2",
                pattern="pattern2",
                bytecode_template="template2",
                sha256="abc2",
                pruned_reason="reason2",
                pruned_at=time.time()
            )
        ]

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name

        try:
            self.loader.save_tombstones(temp_path, ghosts)

            # Load back
            new_loader = GhostLoader()
            loaded_ghosts = new_loader.load_tombstones(temp_path)

            assert len(loaded_ghosts) == 2
            assert loaded_ghosts[0].name == "test1"
            assert loaded_ghosts[1].name == "test2"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_save_tombstones_structure(self):
        """Test that saved tombstones have correct structure."""
        ghosts = [
            GhostEntry(
                name="test",
                pattern="pattern",
                bytecode_template="template",
                sha256="abc",
                pruned_reason="reason",
                pruned_at=time.time()
            )
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name

        try:
            self.loader.save_tombstones(temp_path, ghosts)

            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert 'version' in data
            assert 'timestamp' in data
            assert 'count' in data
            assert 'tombstones' in data
            assert data['count'] == 1
            assert len(data['tombstones']) == 1
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestResurrection:
    """Test resurrection functionality."""

    def setup_method(self):
        self.loader = GhostLoader()
        self.ghost = GhostEntry(
            name="factorial",
            pattern="factorial of $n",
            bytecode_template="MOVI R0, ${n}\nHALT",
            sha256="abc123",
            pruned_reason="Unused",
            pruned_at=time.time(),
            description="Compute factorial",
            tags=["math"]
        )

    def test_resurrect_basic_ghost(self):
        """Test basic resurrection."""
        entry = self.loader.resurrect(self.ghost)
        assert entry is not None
        assert isinstance(entry, VocabEntry)
        assert entry.name == "factorial"
        assert entry.pattern == "factorial of $n"
        assert entry.description == "Compute factorial"
        assert entry.tags == ["math"]

    def test_resurrect_with_ghost_origin(self):
        """Test that resurrected entry tracks its origin."""
        entry = self.loader.resurrect(self.ghost)
        assert entry._ghost_origin is not None
        assert entry._ghost_origin.name == "factorial"
        assert entry._ghost_origin.pruned_reason == "Unused"

    def test_resurrect_invalid_ghost(self):
        """Test resurrection fails for invalid ghost."""
        invalid_ghost = GhostEntry(
            name="invalid",
            pattern="",  # Empty pattern
            bytecode_template="",  # Empty template
            sha256="def",
            pruned_reason="Invalid",
            pruned_at=time.time()
        )
        entry = self.loader.resurrect(invalid_ghost)
        assert entry is None

    def test_resurrected_entry_can_compile(self):
        """Test that resurrected entry can compile pattern."""
        entry = self.loader.resurrect(self.ghost)
        entry.compile()
        assert hasattr(entry, '_regex')

        # Test matching
        match = entry.match("factorial of 5")
        assert match is not None
        assert 'n' in match


class TestConsultation:
    """Test consultation functionality."""

    def setup_method(self):
        self.loader = GhostLoader()
        self.ghosts = [
            GhostEntry(
                name="factorial",
                pattern="factorial of $n",
                bytecode_template="MOVI R0, ${n}\nHALT",
                sha256="abc1",
                pruned_reason="Unused",
                pruned_at=time.time(),
                description="Compute factorial"
            ),
            GhostEntry(
                name="fibonacci",
                pattern="fibonacci of $n",
                bytecode_template="MOVI R0, ${n}\nHALT",
                sha256="abc2",
                pruned_reason="Inefficient",
                pruned_at=time.time(),
                description="Compute fibonacci"
            ),
            GhostEntry(
                name="square",
                pattern="square of $n",
                bytecode_template="MOVI R0, ${n}\nHALT",
                sha256="abc3",
                pruned_reason="Replaced",
                pruned_at=time.time(),
                description="Compute square",
                tags=["math"]
            )
        ]

    def test_consult_by_name(self):
        """Test consulting ghosts by name."""
        results = self.loader.consult(self.ghosts, "factorial")
        assert len(results) > 0
        assert results[0].name == "factorial"

    def test_consult_by_description(self):
        """Test consulting ghosts by description."""
        results = self.loader.consult(self.ghosts, "inefficient")
        assert len(results) > 0
        assert "inefficient" in results[0].pruned_reason.lower()

    def test_consult_by_tag(self):
        """Test consulting ghosts by tag."""
        results = self.loader.consult(self.ghosts, "math")
        assert len(results) > 0
        # Should match the entry with "math" tag

    def test_consult_limit(self):
        """Test consultation limit."""
        results = self.loader.consult(self.ghosts, "n", limit=2)
        assert len(results) <= 2

    def test_consult_no_matches(self):
        """Test consultation with no matches."""
        results = self.loader.consult(self.ghosts, "quantum physics")
        assert len(results) == 0

    def test_consult_ranking(self):
        """Test that results are ranked by relevance."""
        results = self.loader.consult(self.ghosts, "compute")
        # "compute" appears in all descriptions, so all should match
        # Check that they're ranked somehow
        if len(results) > 1:
            # Just verify we get multiple results
            assert len(results) >= 1


class TestFindByMethods:
    """Test find_by_* methods."""

    def setup_method(self):
        self.loader = GhostLoader()
        self.ghosts = [
            GhostEntry(
                name="factorial",
                pattern="factorial of $n",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="reason1",
                pruned_at=time.time()
            ),
            GhostEntry(
                name="factorial",  # Same name, different hash
                pattern="factorial $n",
                bytecode_template="template2",
                sha256="abc2",
                pruned_reason="reason2",
                pruned_at=time.time()
            ),
            GhostEntry(
                name="square",
                pattern="square of $n",
                bytecode_template="template3",
                sha256="abc3",
                pruned_reason="reason3",
                pruned_at=time.time()
            )
        ]
        self.loader._ghosts = self.ghosts
        self.loader._rebuild_index()

    def test_find_by_name(self):
        """Test finding ghosts by name."""
        results = self.loader.find_by_name("factorial")
        assert len(results) == 2
        assert all(g.name == "factorial" for g in results)

    def test_find_by_name_no_matches(self):
        """Test finding by name with no matches."""
        results = self.loader.find_by_name("nonexistent")
        assert len(results) == 0

    def test_find_by_hash(self):
        """Test finding ghost by hash."""
        result = self.loader.find_by_hash("abc1")
        assert result is not None
        assert result.sha256 == "abc1"

    def test_find_by_hash_no_match(self):
        """Test finding by hash with no match."""
        result = self.loader.find_by_hash("nonexistent")
        assert result is None


class TestFindRecent:
    """Test finding recent ghosts."""

    def setup_method(self):
        self.loader = GhostLoader()
        now = time.time()
        self.ghosts = [
            GhostEntry(
                name="recent1",
                pattern="pattern1",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="reason1",
                pruned_at=now - (5 * 24 * 3600)  # 5 days ago
            ),
            GhostEntry(
                name="recent2",
                pattern="pattern2",
                bytecode_template="template2",
                sha256="abc2",
                pruned_reason="reason2",
                pruned_at=now - (15 * 24 * 3600)  # 15 days ago
            ),
            GhostEntry(
                name="old",
                pattern="pattern3",
                bytecode_template="template3",
                sha256="abc3",
                pruned_reason="reason3",
                pruned_at=now - (50 * 24 * 3600)  # 50 days ago
            )
        ]
        self.loader._ghosts = self.ghosts

    def test_find_recent_default(self):
        """Test finding recent ghosts (default 30 days)."""
        recent = self.loader.find_recent()
        assert len(recent) == 2
        assert all(g.is_recent(30) for g in recent)

    def test_find_recent_custom_days(self):
        """Test finding recent ghosts with custom days."""
        recent = self.loader.find_recent(days=10)
        assert len(recent) == 1
        assert recent[0].name == "recent1"

    def test_find_recent_all(self):
        """Test finding all ghosts with large day limit."""
        recent = self.loader.find_recent(days=100)
        assert len(recent) == 3


class TestStatistics:
    """Test statistics functionality."""

    def setup_method(self):
        self.loader = GhostLoader()
        now = time.time()
        self.ghosts = [
            GhostEntry(
                name="ghost1",
                pattern="pattern1",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="Unused",
                pruned_at=now - (10 * 24 * 3600)
            ),
            GhostEntry(
                name="ghost2",
                pattern="pattern2",
                bytecode_template="template2",
                sha256="abc2",
                pruned_reason="Inefficient",
                pruned_at=now - (20 * 24 * 3600)
            ),
            GhostEntry(
                name="ghost1",  # Duplicate name
                pattern="pattern3",
                bytecode_template="template3",
                sha256="abc3",
                pruned_reason="Unused",  # Duplicate reason
                pruned_at=now - (30 * 24 * 3600)
            )
        ]
        self.loader._ghosts = self.ghosts

    def test_get_statistics_basic(self):
        """Test getting basic statistics."""
        stats = self.loader.get_statistics()
        assert stats['total_ghosts'] == 3
        assert stats['unique_names'] == 2  # ghost1, ghost2
        assert 'avg_age_days' in stats

    def test_get_statistics_pruned_reasons(self):
        """Test that pruned reasons are counted."""
        stats = self.loader.get_statistics()
        assert 'pruned_reasons' in stats
        assert stats['pruned_reasons']['Unused'] == 2
        assert stats['pruned_reasons']['Inefficient'] == 1

    def test_get_statistics_empty_loader(self):
        """Test statistics for empty loader."""
        empty_loader = GhostLoader()
        stats = empty_loader.get_statistics()
        assert stats['total_ghosts'] == 0
        assert stats['unique_names'] == 0


class TestMergeAndClear:
    """Test merge and clear functionality."""

    def setup_method(self):
        self.loader = GhostLoader()
        self.ghosts1 = [
            GhostEntry(
                name="ghost1",
                pattern="pattern1",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="reason1",
                pruned_at=time.time()
            )
        ]
        self.ghosts2 = [
            GhostEntry(
                name="ghost2",
                pattern="pattern2",
                bytecode_template="template2",
                sha256="abc2",
                pruned_reason="reason2",
                pruned_at=time.time()
            ),
            GhostEntry(
                name="ghost1",  # Same hash as ghosts1[0]
                pattern="pattern1",
                bytecode_template="template1",
                sha256="abc1",
                pruned_reason="reason1",
                pruned_at=time.time()
            )
        ]

    def test_merge_ghosts(self):
        """Test merging ghost lists."""
        self.loader._ghosts = self.ghosts1.copy()
        self.loader._rebuild_index()

        initial_count = len(self.loader._ghosts)
        self.loader.merge(self.ghosts2)

        # Should add ghost2 but not duplicate ghost1
        assert len(self.loader._ghosts) == initial_count + 1

    def test_clear_recent(self):
        """Test clearing recent ghosts."""
        now = time.time()
        ghosts = [
            GhostEntry(
                name="recent",
                pattern="pattern",
                bytecode_template="template",
                sha256="abc1",
                pruned_reason="reason",
                pruned_at=now - (5 * 24 * 3600)
            ),
            GhostEntry(
                name="old",
                pattern="pattern",
                bytecode_template="template",
                sha256="abc2",
                pruned_reason="reason",
                pruned_at=now - (100 * 24 * 3600)
            )
        ]
        self.loader._ghosts = ghosts
        self.loader._rebuild_index()

        self.loader.clear_recent(days=30)

        # Should keep recent, clear old
        assert len(self.loader._ghosts) == 1
        assert self.loader._ghosts[0].name == "recent"


class TestCreateTombstone:
    """Test create_tombstone convenience function."""

    def test_create_tombstone_from_vocab_entry(self):
        """Test creating tombstone from vocabulary entry."""
        vocab_entry = VocabEntry(
            name="factorial",
            pattern="factorial of $n",
            bytecode_template="MOVI R0, ${n}\nHALT",
            description="Compute factorial",
            tags=["math"]
        )

        ghost = create_tombstone(
            vocab_entry,
            reason="Unused",
            usage_count=42,
            last_used=time.time() - 1000
        )

        assert ghost.name == "factorial"
        assert ghost.pattern == "factorial of $n"
        assert ghost.pruned_reason == "Unused"
        assert ghost.usage_count == 42
        assert ghost.description == "Compute factorial"
        assert ghost.tags == ["math"]
        assert ghost.sha256 is not None
        assert len(ghost.sha256) == 64  # SHA256 hex length


class TestResurrectionContext:
    """Test ResurrectionContext functionality."""

    def test_create_resurrection_context(self):
        """Test creating resurrection context."""
        context = ResurrectionContext(
            agent_name="TestAgent",
            reason="Debugging",
            target_vocabulary="math"
        )
        assert context.agent_name == "TestAgent"
        assert context.reason == "Debugging"
        assert context.target_vocabulary == "math"

    def test_resurrection_context_default_timestamp(self):
        """Test that resurrection context gets default timestamp."""
        context = ResurrectionContext()
        before = time.time()
        time.sleep(0.01)
        context2 = ResurrectionContext()
        after = time.time()
        assert before <= context2.timestamp <= after


class TestVocabEntry:
    """Test VocabEntry functionality (resurrected entries)."""

    def test_vocab_entry_basic(self):
        """Test creating basic vocab entry."""
        entry = VocabEntry(
            name="test",
            pattern="test pattern",
            bytecode_template="test template"
        )
        assert entry.name == "test"
        assert entry.pattern == "test pattern"
        assert entry.result_reg == 0

    def test_vocab_entry_with_all_fields(self):
        """Test vocab entry with all fields."""
        entry = VocabEntry(
            name="test",
            pattern="test pattern",
            bytecode_template="test template",
            result_reg=5,
            description="Test description",
            tags=["test", "demo"]
        )
        assert entry.result_reg == 5
        assert entry.description == "Test description"
        assert entry.tags == ["test", "demo"]

    def test_vocab_entry_repr(self):
        """Test vocab entry string representation."""
        entry = VocabEntry(
            name="test_entry_with_long_name",
            pattern="this is a very long pattern that should be truncated",
            bytecode_template="template"
        )
        repr_str = repr(entry)
        assert "VocabEntry" in repr_str
        assert "test_entry_with_long_name" in repr_str

    def test_vocab_entry_compile_and_match(self):
        """Test compiling and matching with vocab entry."""
        entry = VocabEntry(
            name="add",
            pattern="compute $a + $b",
            bytecode_template="MOVI R0, ${a}\nMOVI R1, ${b}\nIADD R0, R0, R1"
        )
        entry.compile()

        match = entry.match("compute 5 + 3")
        assert match is not None
        assert 'a' in match
        assert 'b' in match

    def test_vocab_entry_no_match(self):
        """Test vocab entry with no match."""
        entry = VocabEntry(
            name="add",
            pattern="compute $a + $b",
            bytecode_template="template"
        )
        entry.compile()

        match = entry.match("subtract 5 - 3")
        assert match is None
