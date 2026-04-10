"""
Tests for the vocabulary argumentation framework.

Covers:
- Simple accept/reject cases
- Mutual defeat (both rejected)
- Chain of support (A supports B supports C)
- Vocab conflict between two agents
"""

import pytest
from flux.open_interp.argumentation import (
    Argument,
    ArgumentationFramework,
    VocabInterpretation,
    VocabArbitration
)


class TestArgument:
    """Test the Argument class."""

    def test_argument_creation(self):
        """Test creating a basic argument."""
        arg = Argument(
            claim="Pattern 'add $a $b' should compile to IADD",
            evidence=["Agent A says so", "Mathematical correctness"],
            confidence=0.9,
            proponent="AgentA"
        )

        assert arg.claim == "Pattern 'add $a $b' should compile to IADD"
        assert len(arg.evidence) == 2
        assert arg.confidence == 0.9
        assert arg.proponent == "AgentA"

    def test_argument_confidence_validation(self):
        """Test that confidence must be between 0 and 1."""
        with pytest.raises(ValueError):
            Argument(claim="test", confidence=1.5)

        with pytest.raises(ValueError):
            Argument(claim="test", confidence=-0.1)

    def test_support_weight(self):
        """Test support weight calculation."""
        arg = Argument(
            claim="test",
            evidence=["evidence1", "evidence2"],
            confidence=0.5
        )
        # 2 pieces of evidence * 0.5 confidence = 1.0
        assert arg.support_weight == 1.0

    def test_objection_weight(self):
        """Test objection weight calculation."""
        arg = Argument(claim="test")

        obj1 = Argument(claim="objection1", confidence=0.3)
        obj2 = Argument(claim="objection2", confidence=0.7)

        arg.add_objection(obj1)
        arg.add_objection(obj2)

        assert arg.objection_weight == 1.0

    def test_add_evidence(self):
        """Test adding evidence to an argument."""
        arg = Argument(claim="test")
        assert len(arg.evidence) == 0

        arg.add_evidence("New evidence")
        assert len(arg.evidence) == 1
        assert "New evidence" in arg.evidence

    def test_add_objection(self):
        """Test adding objections to an argument."""
        arg = Argument(claim="test")
        assert len(arg.objections) == 0

        obj = Argument(claim="you're wrong")
        arg.add_objection(obj)

        assert len(arg.objections) == 1
        assert arg.objections[0].claim == "you're wrong"


class TestArgumentationFramework:
    """Test the ArgumentationFramework class."""

    def test_add_argument(self):
        """Test adding arguments to the framework."""
        fw = ArgumentationFramework()

        arg = Argument(claim="test claim")
        arg_id = fw.add_argument(arg)

        assert arg_id in fw.arguments
        assert fw.arguments[arg_id] == arg
        assert arg_id == "arg_0"

    def test_add_multiple_arguments(self):
        """Test adding multiple arguments gets unique IDs."""
        fw = ArgumentationFramework()

        arg1 = Argument(claim="claim1")
        arg2 = Argument(claim="claim2")
        arg3 = Argument(claim="claim3")

        id1 = fw.add_argument(arg1)
        id2 = fw.add_argument(arg2)
        id3 = fw.add_argument(arg3)

        assert id1 == "arg_0"
        assert id2 == "arg_1"
        assert id3 == "arg_2"

    def test_object_to(self):
        """Test objecting to an existing argument."""
        fw = ArgumentationFramework()

        main_arg = Argument(claim="main claim")
        main_id = fw.add_argument(main_arg)

        objection = Argument(claim="objection", confidence=0.8)
        obj_id = fw.object_to(main_id, objection)

        assert obj_id == "arg_1"
        assert len(main_arg.objections) == 1
        assert main_arg.objections[0].claim == "objection"

    def test_object_to_nonexistent(self):
        """Test objecting to a non-existent argument raises error."""
        fw = ArgumentationFramework()

        objection = Argument(claim="objection")
        with pytest.raises(KeyError):
            fw.object_to("nonexistent", objection)

    def test_support(self):
        """Test supporting an existing argument."""
        fw = ArgumentationFramework()

        main_arg = Argument(claim="main claim")
        main_id = fw.add_argument(main_arg)

        support = Argument(claim="supporting argument")
        support_id = fw.support(main_id, support)

        assert support_id == "arg_1"
        # Support is tracked via evidence
        assert len(main_arg.evidence) == 1
        assert "Supported by" in main_arg.evidence[0]

    def test_support_nonexistent(self):
        """Test supporting a non-existent argument raises error."""
        fw = ArgumentationFramework()

        support = Argument(claim="support")
        with pytest.raises(KeyError):
            fw.support("nonexistent", support)

    def test_evaluate_simple_accept(self):
        """Test simple acceptance: more support than objections."""
        fw = ArgumentationFramework()

        arg = Argument(
            claim="main claim",
            evidence=["ev1", "ev2"],  # 2 pieces of evidence
            confidence=1.0
        )
        fw.add_argument(arg)

        # Add weak objection
        objection = Argument(claim="weak objection", confidence=0.5)
        fw.object_to("arg_0", objection)

        results = fw.evaluate()
        assert results["arg_0"] == "accepted"

    def test_evaluate_simple_reject(self):
        """Test rejection: objections outweigh support by 2:1."""
        fw = ArgumentationFramework()

        arg = Argument(
            claim="main claim",
            evidence=["ev1"],  # 1 piece of evidence, weight = 1
            confidence=1.0
        )
        fw.add_argument(arg)

        # Add strong objections - 3 objections of 1.0 each = 3.0 weight
        # Support = 1, Objections = 3, ratio = 1/3 = 0.33 < 0.5 -> rejected
        obj1 = Argument(claim="strong objection 1", confidence=1.0)
        obj2 = Argument(claim="strong objection 2", confidence=1.0)
        obj3 = Argument(claim="strong objection 3", confidence=1.0)
        fw.object_to("arg_0", obj1)
        fw.object_to("arg_0", obj2)
        fw.object_to("arg_0", obj3)

        results = fw.evaluate()
        assert results["arg_0"] == "rejected"

    def test_evaluate_undecided(self):
        """Test undecided: support and objections are balanced."""
        fw = ArgumentationFramework()

        arg = Argument(
            claim="main claim",
            evidence=["ev1", "ev2"],  # weight = 2
            confidence=1.0
        )
        fw.add_argument(arg)

        # Add objections that roughly balance
        # Support = 2, Objections = 2.5, ratio = 0.8 (undecided: 0.5 < ratio < 1.0)
        obj1 = Argument(claim="objection 1", confidence=1.0)
        obj2 = Argument(claim="objection 2", confidence=1.0)
        obj3 = Argument(claim="objection 3", confidence=0.5)
        fw.object_to("arg_0", obj1)
        fw.object_to("arg_0", obj2)
        fw.object_to("arg_0", obj3)

        results = fw.evaluate()
        assert results["arg_0"] == "undecided"

    def test_evaluate_no_objections_accepted(self):
        """Test that argument with support but no objections is accepted."""
        fw = ArgumentationFramework()

        arg = Argument(
            claim="main claim",
            evidence=["ev1"],
            confidence=1.0
        )
        fw.add_argument(arg)

        results = fw.evaluate()
        assert results["arg_0"] == "accepted"

    def test_evaluate_no_support_no_objections_undecided(self):
        """Test that argument with no support or objections is undecided."""
        fw = ArgumentationFramework()

        arg = Argument(claim="main claim")
        fw.add_argument(arg)

        results = fw.evaluate()
        assert results["arg_0"] == "undecided"

    def test_get_accepted(self):
        """Test getting all accepted arguments."""
        fw = ArgumentationFramework()

        arg1 = Argument(claim="accepted", evidence=["ev1", "ev2"])  # weight = 2
        arg2 = Argument(claim="rejected", evidence=["ev1"])  # weight = 1
        arg3 = Argument(claim="accepted2", evidence=["ev1", "ev2", "ev3"])  # weight = 3

        id1 = fw.add_argument(arg1)
        id2 = fw.add_argument(arg2)
        id3 = fw.add_argument(arg3)

        # Add strong objections to arg2 (3 objections = 3.0 weight vs support of 1)
        # Support = 1, Objections = 3, ratio = 0.33 -> rejected
        obj1 = Argument(claim="objection1", confidence=1.0)
        obj2 = Argument(claim="objection2", confidence=1.0)
        obj3 = Argument(claim="objection3", confidence=1.0)
        fw.object_to(id2, obj1)
        fw.object_to(id2, obj2)
        fw.object_to(id2, obj3)

        accepted = fw.get_accepted()
        assert len(accepted) == 2
        assert id1 in accepted
        assert id3 in accepted

    def test_get_rejected(self):
        """Test getting all rejected arguments."""
        fw = ArgumentationFramework()

        arg = Argument(claim="weak", evidence=["ev1"])  # weight = 1
        fw.add_argument(arg)

        # Overwhelming objections (3 objections vs 1 support)
        # Support = 1, Objections = 3, ratio = 0.33 -> rejected
        obj1 = Argument(claim="strong objection 1", confidence=1.0)
        obj2 = Argument(claim="strong objection 2", confidence=1.0)
        obj3 = Argument(claim="strong objection 3", confidence=1.0)
        fw.object_to("arg_0", obj1)
        fw.object_to("arg_0", obj2)
        fw.object_to("arg_0", obj3)

        rejected = fw.get_rejected()
        assert len(rejected) == 1
        assert "arg_0" in rejected

    def test_mutual_defeat_both_rejected(self):
        """Test mutual defeat: both arguments reject each other."""
        fw = ArgumentationFramework()

        arg1 = Argument(claim="agent1 says X", evidence=["ev1"], confidence=1.0)  # weight = 1
        arg2 = Argument(claim="agent2 says Y", evidence=["ev2"], confidence=1.0)  # weight = 1

        id1 = fw.add_argument(arg1)
        id2 = fw.add_argument(arg2)

        # Each objects to the other with overwhelming strength
        # For arg1: support = 1, objections = 3, ratio = 0.33 -> rejected
        # For arg2: support = 1, objections = 3, ratio = 0.33 -> rejected
        obj1a = Argument(claim="Y is wrong 1", confidence=1.0)
        obj1b = Argument(claim="Y is wrong 2", confidence=1.0)
        obj1c = Argument(claim="Y is wrong 3", confidence=1.0)
        obj2a = Argument(claim="X is wrong 1", confidence=1.0)
        obj2b = Argument(claim="X is wrong 2", confidence=1.0)
        obj2c = Argument(claim="X is wrong 3", confidence=1.0)

        fw.object_to(id1, obj1a)
        fw.object_to(id1, obj1b)
        fw.object_to(id1, obj1c)
        fw.object_to(id2, obj2a)
        fw.object_to(id2, obj2b)
        fw.object_to(id2, obj2c)

        results = fw.evaluate()
        # Both should be rejected (objections outweigh support 3:1)
        assert results[id1] == "rejected"
        assert results[id2] == "rejected"

    def test_chain_of_support(self):
        """Test chain of support: A supports B supports C."""
        fw = ArgumentationFramework()

        # Create three arguments
        arg_a = Argument(claim="A is true", evidence=["base evidence"], confidence=0.9)
        arg_b = Argument(claim="B is true", evidence=["some evidence"], confidence=0.8)
        arg_c = Argument(claim="C is true", evidence=["initial evidence"], confidence=0.7)

        id_a = fw.add_argument(arg_a)
        id_b = fw.add_argument(arg_b)
        id_c = fw.add_argument(arg_c)

        # A supports B, B supports C
        fw.support(id_b, arg_a)  # A supports B
        fw.support(id_c, arg_b)  # B supports C

        # Now C has support from B, which has support from A
        results = fw.evaluate()

        # All should have at least some support now
        assert "arg_1" in fw.arguments["arg_1"].evidence[0] or len(fw.arguments["arg_1"].evidence) > 1
        assert "arg_2" in fw.arguments["arg_2"].evidence[0] or len(fw.arguments["arg_2"].evidence) > 1


class TestVocabInterpretation:
    """Test the VocabInterpretation class."""

    def test_interpretation_creation(self):
        """Test creating a vocabulary interpretation."""
        interp = VocabInterpretation(
            pattern="compute $a + $b",
            bytecode="IADD R0, ${a}, ${b}",
            agent="MathAgent",
            confidence=0.95
        )

        assert interp.pattern == "compute $a + $b"
        assert interp.bytecode == "IADD R0, ${a}, ${b}"
        assert interp.agent == "MathAgent"
        assert interp.confidence == 0.95

    def test_conflicts_with_same_pattern_different_bytecode(self):
        """Test conflict detection: same pattern, different bytecode."""
        interp1 = VocabInterpretation(
            pattern="add $a $b",
            bytecode="IADD R0, R1, R2",
            agent="Agent1"
        )

        interp2 = VocabInterpretation(
            pattern="add $a $b",
            bytecode="MOVI R0, 0\nIADD R0, R1, R2",
            agent="Agent2"
        )

        assert interp1.conflicts_with(interp2)
        assert interp2.conflicts_with(interp1)

    def test_no_conflict_different_pattern(self):
        """Test no conflict: different patterns."""
        interp1 = VocabInterpretation(
            pattern="add $a $b",
            bytecode="IADD R0, R1, R2",
            agent="Agent1"
        )

        interp2 = VocabInterpretation(
            pattern="multiply $a $b",
            bytecode="IMUL R0, R1, R2",
            agent="Agent2"
        )

        assert not interp1.conflicts_with(interp2)

    def test_no_conflict_same_bytecode(self):
        """Test no conflict: same bytecode (agreement)."""
        bytecode = "IADD R0, R1, R2"
        interp1 = VocabInterpretation(
            pattern="add $a $b",
            bytecode=bytecode,
            agent="Agent1"
        )

        interp2 = VocabInterpretation(
            pattern="add $a $b",
            bytecode=bytecode,
            agent="Agent2"
        )

        assert not interp1.conflicts_with(interp2)


class TestVocabArbitration:
    """Test the VocabArbitration class."""

    def test_find_conflicts(self):
        """Test finding conflicts between two sets of interpretations."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(pattern="add $a $b", bytecode="IADD R0, R1, R2", agent="Agent1"),
            VocabInterpretation(pattern="sub $a $b", bytecode="ISUB R0, R1, R2", agent="Agent1"),
            VocabInterpretation(pattern="mul $a $b", bytecode="IMUL R0, R1, R2", agent="Agent1"),
        ]

        agent2_ints = [
            VocabInterpretation(pattern="add $a $b", bytecode="MOVI R0, 0\nIADD R0, R1, R2", agent="Agent2"),
            VocabInterpretation(pattern="sub $a $b", bytecode="ISUB R0, R1, R2", agent="Agent2"),  # Same bytecode
            VocabInterpretation(pattern="div $a $b", bytecode="IDIV R0, R1, R2", agent="Agent2"),
        ]

        conflicts = arb.find_conflicts(agent1_ints, agent2_ints)

        # Should find 1 conflict: "add $a $b" has different bytecode
        assert len(conflicts) == 1
        assert conflicts[0][0].pattern == "add $a $b"
        assert conflicts[0][1].pattern == "add $a $b"

    def test_find_no_conflicts(self):
        """Test when there are no conflicts."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(pattern="add $a $b", bytecode="IADD R0, R1, R2", agent="Agent1"),
        ]

        agent2_ints = [
            VocabInterpretation(pattern="add $a $b", bytecode="IADD R0, R1, R2", agent="Agent2"),
        ]

        conflicts = arb.find_conflicts(agent1_ints, agent2_ints)
        assert len(conflicts) == 0

    def test_create_framework_for_conflict(self):
        """Test creating an argumentation framework for a conflict."""
        arb = VocabArbitration()

        interp1 = VocabInterpretation(
            pattern="add $a $b",
            bytecode="IADD R0, R1, R2",
            agent="Agent1",
            confidence=0.8
        )

        interp2 = VocabInterpretation(
            pattern="add $a $b",
            bytecode="MOVI R0, 0\nIADD R0, R1, R2",
            agent="Agent2",
            confidence=0.9
        )

        fw = arb.create_framework_for_conflict(interp1, interp2)

        assert len(fw.arguments) == 2
        assert any(arg.proponent == "Agent1" for arg in fw.arguments.values())
        assert any(arg.proponent == "Agent2" for arg in fw.arguments.values())

    def test_resolve_single_conflict(self):
        """Test resolving a single conflict."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(
                pattern="add $a $b",
                bytecode="IADD R0, R1, R2",
                agent="Agent1",
                confidence=0.5
            ),
        ]

        agent2_ints = [
            VocabInterpretation(
                pattern="add $a $b",
                bytecode="MOVI R0, 0\nIADD R0, R1, R2",
                agent="Agent2",
                confidence=0.9
            ),
        ]

        result = arb.resolve(agent1_ints, agent2_ints, "Agent1", "Agent2")

        assert len(result['conflicts']) == 1
        assert len(result['resolutions']) == 1
        assert 'add $a $b' in result['resolutions']
        assert 'add $a $b' in result['frameworks']

    def test_resolve_multiple_conflicts(self):
        """Test resolving multiple conflicts."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(pattern="add", bytecode="BYTECODE1", agent="Agent1"),
            VocabInterpretation(pattern="sub", bytecode="BYTECODE2", agent="Agent1"),
            VocabInterpretation(pattern="mul", bytecode="BYTECODE3", agent="Agent1"),
        ]

        agent2_ints = [
            VocabInterpretation(pattern="add", bytecode="BYTECODE1_ALT", agent="Agent2"),
            VocabInterpretation(pattern="sub", bytecode="BYTECODE2", agent="Agent2"),  # No conflict
            VocabInterpretation(pattern="mul", bytecode="BYTECODE3_ALT", agent="Agent2"),
        ]

        result = arb.resolve(agent1_ints, agent2_ints)

        # Should find 2 conflicts (add and mul)
        assert len(result['conflicts']) == 2
        assert len(result['resolutions']) == 2

    def test_resolve_no_conflicts(self):
        """Test resolving when there are no conflicts."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(pattern="add", bytecode="SAME", agent="Agent1"),
        ]

        agent2_ints = [
            VocabInterpretation(pattern="add", bytecode="SAME", agent="Agent2"),
        ]

        result = arb.resolve(agent1_ints, agent2_ints)

        assert len(result['conflicts']) == 0
        assert len(result['resolutions']) == 0

    def test_resolve_with_evidence_and_objections(self):
        """Test resolving a conflict where agents provide evidence and objections."""
        arb = VocabArbitration()

        agent1_ints = [
            VocabInterpretation(
                pattern="add",
                bytecode="BYTECODE1",
                agent="Agent1",
                confidence=0.7
            ),
        ]

        agent2_ints = [
            VocabInterpretation(
                pattern="add",
                bytecode="BYTECODE2",
                agent="Agent2",
                confidence=0.6
            ),
        ]

        result = arb.resolve(agent1_ints, agent2_ints)

        framework = result['frameworks']['add']

        # Add some evidence to agent1's argument
        agent1_arg = [arg for arg in framework.arguments.values() if arg.proponent == "Agent1"][0]
        agent1_arg.add_evidence("Performance benchmark shows BYTECODE1 is faster")

        # Add multiple strong objections to agent2's argument
        agent2_arg = [arg for arg in framework.arguments.values() if arg.proponent == "Agent2"][0]
        objection1 = Argument(
            claim="BYTECODE2 has security vulnerability",
            confidence=1.0
        )
        objection2 = Argument(
            claim="BYTECODE2 is slower",
            confidence=1.0
        )
        objection3 = Argument(
            claim="BYTECODE2 uses more memory",
            confidence=1.0
        )
        agent2_arg.add_objection(objection1)
        agent2_arg.add_objection(objection2)
        agent2_arg.add_objection(objection3)

        # Re-evaluate
        results = framework.evaluate()

        # Agent1 should now have an advantage
        agent1_id = [id for id, arg in framework.arguments.items() if arg.proponent == "Agent1"][0]
        agent2_id = [id for id, arg in framework.arguments.items() if arg.proponent == "Agent2"][0]

        # Agent1 should be accepted (has support + 2 evidence), Agent2 should be rejected
        # Agent1: support = 1 (initial) + 1 (evidence) = 2, objections = 0 -> ratio = inf -> accepted
        # Agent2: support = 1, objections = 3 -> ratio = 0.33 -> rejected
        assert results[agent1_id] == 'accepted'
        assert results[agent2_id] == 'rejected'

    def test_resolve_mutual_defeat(self):
        """Test resolution when both arguments defeat each other."""
        arb = VocabArbitration()

        # Create equal-strength arguments
        agent1_ints = [
            VocabInterpretation(
                pattern="add",
                bytecode="BYTECODE1",
                agent="Agent1",
                confidence=0.5
            ),
        ]

        agent2_ints = [
            VocabInterpretation(
                pattern="add",
                bytecode="BYTECODE2",
                agent="Agent2",
                confidence=0.5
            ),
        ]

        result = arb.resolve(agent1_ints, agent2_ints)

        resolution = result['resolutions']['add']

        # Should result in no clear winner
        assert resolution['winning_agent'] is None
        assert resolution['bytecode'] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
