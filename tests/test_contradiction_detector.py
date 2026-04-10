"""Tests for ContradictionDetector — the vocabulary immune system."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.open_interp.contradiction_detector import (
    ContradictionDetector, ScanReport, Contradiction, Severity
)
from flux.open_interp.vocabulary import Vocabulary, VocabEntry


def _make_entry(name, pattern, result_reg=0, depends=None, bytecode="MOVI R0, 0; HALT"):
    entry = VocabEntry(
        name=name,
        pattern=pattern,
        bytecode_template=bytecode,
        result_reg=result_reg,
        description=f"Test entry {name}",
        tags=["test"],
    )
    entry.depends = depends or []
    return entry


class TestDuplicateDetection:
    def setup_method(self):
        self.detector = ContradictionDetector()
    
    def test_clean_vocab(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("mul", "compute $a * $b"),
            _make_entry("hello", "hello"),
        ]
        report = self.detector.scan(vocab)
        assert report.clean
        assert report.total_entries == 3
    
    def test_duplicate_name(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("add", "addition of $a and $b"),
        ]
        report = self.detector.scan(vocab)
        assert not report.clean
        assert any(i.conflict_type == "duplicate_name" for i in report.issues)
    
    def test_pattern_overlap(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("add2", "compute $x + $y"),
        ]
        report = self.detector.scan(vocab)
        assert any(i.conflict_type == "pattern_overlap" for i in report.issues)


class TestDependencyCycles:
    def setup_method(self):
        self.detector = ContradictionDetector()
    
    def test_self_dependency(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("a", "pattern a", depends=["a"]),
        ]
        report = self.detector.scan(vocab)
        assert any(i.conflict_type == "dependency_cycle" for i in report.issues)
    
    def test_circular_dependency(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("a", "pattern a", depends=["b"]),
            _make_entry("b", "pattern b", depends=["c"]),
            _make_entry("c", "pattern c", depends=["a"]),
        ]
        report = self.detector.scan(vocab)
        assert any(i.conflict_type == "dependency_cycle" for i in report.issues)
    
    def test_no_cycle_valid_deps(self):
        vocab = Vocabulary()
        vocab.entries = [
            _make_entry("base", "base pattern"),
            _make_entry("mid", "mid pattern", depends=["base"]),
            _make_entry("top", "top pattern", depends=["mid"]),
        ]
        report = self.detector.scan(vocab)
        # No dependency cycle issues
        cycle_issues = [i for i in report.issues if i.conflict_type == "dependency_cycle"]
        assert len(cycle_issues) == 0


class TestValidation:
    def setup_method(self):
        self.detector = ContradictionDetector()
        self.vocab = Vocabulary()
        self.vocab.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("mul", "compute $a * $b"),
        ]
    
    def test_valid_new_entry(self):
        entry = _make_entry("div", "compute $a / $b")
        report = self.detector.validate(entry, self.vocab)
        assert report.clean
    
    def test_duplicate_name_rejected(self):
        entry = _make_entry("add", "addition of $a and $b")
        report = self.detector.validate(entry, self.vocab)
        assert any(i.conflict_type == "duplicate_name" for i in report.issues)
    
    def test_missing_dependency_warned(self):
        entry = _make_entry("avg", "average of $a and $b", depends=["nonexistent"])
        report = self.detector.validate(entry, self.vocab)
        assert any(i.conflict_type == "missing_dependency" for i in report.issues)


class TestDiff:
    def setup_method(self):
        self.detector = ContradictionDetector()
        self.before = Vocabulary()
        self.before.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("mul", "compute $a * $b"),
            _make_entry("old", "old pattern"),
        ]
    
    def test_no_changes(self):
        report = self.detector.diff(self.before, self.before)
        # Should find no critical changes
        critical = [i for i in report.issues if i.severity == Severity.CRITICAL]
        assert len(critical) == 0
    
    def test_removed_entry_breaks_dependency(self):
        after = Vocabulary()
        after.entries = [
            _make_entry("add", "compute $a + $b"),
            _make_entry("mul", "compute $a * $b", depends=["old"]),
            # "old" removed
        ]
        report = self.detector.diff(self.before, after)
        assert any(i.conflict_type == "broken_dependency" for i in report.issues)
    
    def test_pattern_change_detected(self):
        after = Vocabulary()
        after.entries = [
            _make_entry("add", "compute $a plus $b"),  # Changed pattern
            _make_entry("mul", "compute $a * $b"),
            _make_entry("old", "old pattern"),
        ]
        report = self.detector.diff(self.before, after)
        assert any(i.conflict_type == "semantic_drift" for i in report.issues)


class TestRealVocab:
    def test_scan_actual_vocabularies(self):
        vocab = Vocabulary()
        vocab.load_folder("vocabularies/core")
        vocab.load_folder("vocabularies/math")
        detector = ContradictionDetector()
        report = detector.scan(vocab)
        print(f"  Scanned {report.total_entries} entries")
        print(f"  Critical: {report.critical_count}, Warnings: {report.warning_count}")
        for issue in report.issues[:5]:
            print(f"  {issue.severity.value}: {issue.entry_a} vs {issue.entry_b} — {issue.description[:60]}")
        # Real vocab should be mostly clean
        assert report.critical_count == 0, f"Found {report.critical_count} critical issues in real vocab"
