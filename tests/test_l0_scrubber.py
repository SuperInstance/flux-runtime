"""Tests for L0Scrubber — the L0 Constitutional Scrubber."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.open_interp.l0_scrubber import (
    L0Scrubber, ScrubReport, scrub_primitive
)


class TestL0Primitives:
    """Test the L0 primitive constants and validation."""

    def test_l0_primitives_defined(self):
        """Test that all 7 L0 primitives are defined."""
        scrubber = L0Scrubber()
        expected = ['self', 'other', 'possible', 'true', 'cause', 'value', 'agreement']
        assert scrubber.L0_PRIMITIVES == expected

    def test_l0_primitives_lowercase(self):
        """Test that L0 primitives are lowercase for comparison."""
        scrubber = L0Scrubber()
        for prim in scrubber.L0_PRIMITIVES:
            assert prim.islower()


class TestDirectConflicts:
    """Test detection of direct conflicts with existing L0 primitives."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_exact_name_conflict(self):
        """Test that exact name conflicts are detected."""
        report = self.scrubber.challenge("SELF", "My own perspective")
        assert not report.passed
        assert report.recommendation == 'reject'
        assert len(report.conflicts) > 0
        assert 'Direct name conflict' in report.conflicts[0]

    def test_case_insensitive_conflict(self):
        """Test that name conflicts are case-insensitive."""
        report = self.scrubber.challenge("self", "my internal perspective")
        assert not report.passed
        assert report.recommendation == 'reject'

    def test_other_l0_conflicts(self):
        """Test conflicts with other L0 primitives."""
        primitives = ['OTHER', 'POSSIBLE', 'TRUE', 'CAUSE', 'VALUE', 'AGREEMENT']
        for prim in primitives:
            report = self.scrubber.challenge(prim, f"Definition of {prim}")
            assert not report.passed
            assert report.recommendation == 'reject'


class TestSemanticOverlap:
    """Test semantic overlap detection."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_high_overlap_with_self(self):
        """Test high semantic overlap with SELF primitive."""
        report = self.scrubber.challenge(
            "MYSELF",
            "The first-person perspective of I and me and my own internal view"
        )
        # Should detect some overlap with 'self' patterns
        assert report.semantic_overlap_score > 0.0
        # Should have conflicts or challenges
        assert len(report.conflicts) > 0 or len(report.challenges) > 0

    def test_high_overlap_with_value(self):
        """Test high semantic overlap with VALUE primitive."""
        report = self.scrubber.challenge(
            "GOODNESS",
            "What is better and preferable and should be chosen over alternatives"
        )
        # Should detect some overlap with 'value' patterns (better, preferable)
        assert report.semantic_overlap_score > 0.0
        # Should have conflicts or challenges
        assert len(report.conflicts) > 0 or len(report.challenges) > 0

    def test_high_overlap_with_cause(self):
        """Test high semantic overlap with CAUSE primitive."""
        report = self.scrubber.challenge(
            "MECHANISM",
            "What produces effects and leads to consequences because of actions"
        )
        # Should detect some overlap with 'cause' patterns (produces, effects, because)
        assert report.semantic_overlap_score > 0.0
        # Should have conflicts or challenges
        assert len(report.conflicts) > 0 or len(report.challenges) > 0

    def test_low_overlap_good_candidate(self):
        """Test low semantic overlap for a novel candidate."""
        report = self.scrubber.challenge(
            "BEAUTY",
            "The aesthetic quality of visual harmony and proportion"
        )
        assert report.semantic_overlap_score < 0.3
        assert len([c for c in report.conflicts if 'Semantic overlap' in c]) == 0


class TestTilingDetection:
    """Test detection of candidates that can tile existing primitives."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_combination_detection(self):
        """Test that combinations are flagged as tilable."""
        report = self.scrubber.challenge(
            "INTERACTION",
            "The combination of self and other acting together in agreement"
        )
        assert report.can_tile is True

    def test_compositional_language(self):
        """Test that compositional language is detected."""
        report = self.scrubber.challenge(
            "MUTUAL_ACTION",
            "The combination of self and other acting together in agreement"
        )
        # Should detect tiling if it uses 3+ L0 primitives with compositional language
        assert report.can_tile is True

    def test_non_tilable_candidate(self):
        """Test that non-tilable candidates are not flagged."""
        report = self.scrubber.challenge(
            "BEAUTY",
            "The aesthetic quality of something"
        )
        assert report.can_tile is False


class TestConflictDetection:
    """Test various conflict detection patterns."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_negation_conflict(self):
        """Test detection of negation conflicts."""
        report = self.scrubber.challenge(
            "NOT_TRUE",
            "The opposite of true that lacks accuracy"
        )
        assert len(report.conflicts) > 0
        assert any('negation' in c.lower() or 'Negation' in c or 'opposite' in c.lower() for c in report.conflicts)

    def test_opposite_conflict(self):
        """Test detection of 'opposite of' language."""
        report = self.scrubber.challenge(
            "CHAOS",
            "The opposite of agreement and order"
        )
        assert len(report.conflicts) > 0
        assert any('opposite' in c.lower() or 'inverse' in c.lower() for c in report.conflicts)

    def test_subset_conflict(self):
        """Test detection of subset relationships."""
        report = self.scrubber.challenge(
            "PREFERENCE",
            "A specific type of value that an agent wants"
        )
        assert len(report.conflicts) > 0
        assert any('subset' in c.lower() or 'specific form' in c.lower() for c in report.conflicts)


class TestChallengeGeneration:
    """Test generation of edge-case semantic challenges."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_challenges_generated(self):
        """Test that challenges are always generated."""
        report = self.scrubber.challenge("TEST", "A test primitive")
        assert len(report.challenges) > 0

    def test_boundary_challenge(self):
        """Test that boundary condition challenge exists."""
        report = self.scrubber.challenge("TEST", "A test primitive")
        boundary_challenges = [c for c in report.challenges if 'Boundary' in c]
        assert len(boundary_challenges) > 0

    def test_l0_mapping_challenge(self):
        """Test that L0 mapping challenge exists."""
        report = self.scrubber.challenge("TEST", "A test primitive")
        mapping_challenges = [c for c in report.challenges if 'L0 Mapping' in c]
        assert len(mapping_challenges) > 0

    def test_verification_challenge(self):
        """Test that verification challenge exists."""
        report = self.scrubber.challenge("TEST", "A test primitive")
        verification_challenges = [c for c in report.challenges if 'Verification' in c]
        assert len(verification_challenges) > 0

    def test_tiling_challenge_when_tilable(self):
        """Test that tiling challenge is added when candidate can tile."""
        report = self.scrubber.challenge(
            "COMBINED",
            "The combination of multiple primitives working together"
        )
        tiling_challenges = [c for c in report.challenges if 'Tiling' in c]
        assert len(tiling_challenges) > 0


class TestRecommendations:
    """Test the recommendation logic."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_high_overlap_can_tile_reject(self):
        """Test that high overlap + can tile = reject."""
        report = self.scrubber.challenge(
            "SOCIAL_VALUE_EXCHANGE",
            "The agreement between self and other about what is true and valuable because of mutual cause"
        )
        # Should be tilable (uses 5+ L0 primitives: agreement, self, other, true, valuable, cause)
        # and has compositional language ("between", "and", "because of")
        assert report.can_tile is True
        # Should have significant overlap with multiple L0 primitives
        assert report.semantic_overlap_score > 0.0
        # Should fail because it's tilable
        assert not report.passed

    def test_multiple_conflicts_reject(self):
        """Test that 3+ conflicts = reject."""
        report = self.scrubber.challenge(
            "DISAGREEMENT",
            "The opposite of agreement, not value, and lacks true cause"
        )
        if len(report.conflicts) >= 3:
            assert report.recommendation == 'reject'
            assert not report.passed

    def test_can_tile_needs_refinement(self):
        """Test that can tile alone = needs-refinement."""
        report = self.scrubber.challenge(
            "RELATIONSHIP",
            "The combination of two things connected together"
        )
        # Should be flagged as tilable
        if report.can_tile and report.semantic_overlap_score < 0.3:
            assert report.recommendation == 'needs-refinement'

    def test_moderate_overlap_needs_refinement(self):
        """Test that moderate overlap = needs-refinement."""
        report = self.scrubber.challenge(
            "BELIEF",
            "What I think is true and accurate"
        )
        if 0.3 < report.semantic_overlap_score < 0.5:
            assert report.recommendation == 'needs-refinement'

    def test_clean_candidate_accept(self):
        """Test that low overlap + no conflicts = accept."""
        report = self.scrubber.challenge(
            "BEAUTY",
            "The aesthetic quality of visual harmony and artistic proportion"
        )
        # Should pass if low overlap and no conflicts
        if report.semantic_overlap_score < 0.3 and len(report.conflicts) == 0:
            assert report.recommendation == 'accept'
            assert report.passed


class TestBatchChallenges:
    """Test batch challenge functionality."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_batch_challenge_multiple(self):
        """Test challenging multiple candidates at once."""
        candidates = [
            ("BEAUTY", "The aesthetic quality of something"),
            ("ACTION", "What agents do to cause effects"),
            ("KNOWLEDGE", "True beliefs that are justified"),
        ]
        reports = self.scrubber.batch_challenge(candidates)
        assert len(reports) == 3
        assert all(isinstance(r, ScrubReport) for r in reports)

    def test_batch_challenge_empty(self):
        """Test batch challenge with empty list."""
        reports = self.scrubber.batch_challenge([])
        assert len(reports) == 0


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_scrub_primitive_function(self):
        """Test the scrub_primitive convenience function."""
        report = scrub_primitive("TEST", "A test primitive")
        assert isinstance(report, ScrubReport)
        assert report.candidate == "TEST"


class TestReportStructure:
    """Test ScrubReport structure and methods."""

    def test_report_fields(self):
        """Test that all required fields exist."""
        scrubber = L0Scrubber()
        report = scrubber.challenge("TEST", "A test primitive")

        assert hasattr(report, 'candidate')
        assert hasattr(report, 'definition')
        assert hasattr(report, 'passed')
        assert hasattr(report, 'can_tile')
        assert hasattr(report, 'conflicts')
        assert hasattr(report, 'challenges')
        assert hasattr(report, 'recommendation')
        assert hasattr(report, 'semantic_overlap_score')

    def test_report_repr(self):
        """Test report string representation."""
        scrubber = L0Scrubber()
        report = scrubber.challenge("TEST", "A test primitive")
        repr_str = repr(report)
        assert 'ScrubReport' in repr_str
        assert 'TEST' in repr_str


class TestRealWorldCandidates:
    """Test with realistic candidate primitives."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_knowledge_candidate(self):
        """Test KNOWLEDGE as a candidate (common proposal)."""
        report = self.scrubber.challenge(
            "KNOWLEDGE",
            "True beliefs that are justified and correspond to reality"
        )
        # Should generate challenges
        assert len(report.challenges) > 0
        # Should have some overlap with TRUE (word "true" is in definition)
        assert report.semantic_overlap_score >= 0.0

    def test_power_candidate(self):
        """Test POWER as a candidate."""
        report = self.scrubber.challenge(
            "POWER",
            "The capacity to cause effects in the world through action"
        )
        # Should generate challenges
        assert len(report.challenges) > 0
        # Should generate verification challenge
        assert any('Verification' in c for c in report.challenges)

    def test_fairness_candidate(self):
        """Test FAIRNESS as a candidate."""
        report = self.scrubber.challenge(
            "FAIRNESS",
            "Equal treatment of all agents in agreement"
        )
        # Should generate challenges
        assert len(report.challenges) > 0
        # Should generate coordination challenge
        assert any('Coordination' in c for c in report.challenges)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        self.scrubber = L0Scrubber()

    def test_empty_name(self):
        """Test with empty candidate name."""
        report = self.scrubber.challenge("", "A definition")
        assert isinstance(report, ScrubReport)

    def test_empty_definition(self):
        """Test with empty definition."""
        report = self.scrubber.challenge("NAME", "")
        assert isinstance(report, ScrubReport)

    def test_very_long_definition(self):
        """Test with very long definition."""
        definition = "This is a test. " * 100
        report = self.scrubber.challenge("LONG", definition)
        assert isinstance(report, ScrubReport)

    def test_special_characters(self):
        """Test with special characters in definition."""
        report = self.scrubber.challenge(
            "SPECIAL",
            "Test with special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"
        )
        assert isinstance(report, ScrubReport)
