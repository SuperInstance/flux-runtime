"""
Tests for A2A Protocol Primitives.

WHY: These primitives are adopted from flux-a2a-prototype into flux-runtime.
Tests verify that the adoption preserved the essential behavior:
  1. JSON round-trip (to_dict → from_dict produces identical object)
  2. Schema versioning ($schema field present on all primitives)
  3. Confidence clamping (values clamped to 0.0-1.0)
  4. Default values (all fields have sensible defaults)
  5. Registry lookup (parse_primitive correctly dispatches by op name)

These tests are deliberately simple — they test data structure integrity,
not runtime behavior. Runtime behavior will be tested when the primitives
are integrated with the SignalCompiler (Phase 1b).
"""

import json
import pytest
from flux.a2a.primitives import (
    BranchPrimitive, BranchBody,
    ForkPrimitive, ForkInherit, ForkMutation,
    CoIteratePrimitive,
    DiscussPrimitive, Participant,
    SynthesizePrimitive, SynthesisSource,
    ReflectPrimitive,
    parse_primitive, PRIMITIVE_REGISTRY,
)


# ===========================================================================
# Helper
# ===========================================================================

def round_trip(prim) -> dict:
    """Serialize to dict, deserialize, return result."""
    return prim.__class__.from_dict(prim.to_dict())


# ===========================================================================
# Branch Tests
# ===========================================================================

class TestBranchPrimitive:
    def test_default_values(self):
        b = BranchPrimitive()
        assert b.strategy == "parallel"
        assert b.branches == []
        assert b.confidence == 1.0
        assert b.id != ""  # auto-generated UUID

    def test_confidence_clamped_high(self):
        b = BranchPrimitive(confidence=1.5)
        assert b.confidence == 1.0

    def test_confidence_clamped_low(self):
        b = BranchPrimitive(confidence=-0.5)
        assert b.confidence == 0.0

    def test_json_round_trip(self):
        original = BranchPrimitive(
            strategy="competitive",
            branches=[
                BranchBody(label="fast", weight=0.8, body=[{"op": "tell", "to": "a"}]),
                BranchBody(label="slow", body=[{"op": "ask", "from": "b"}]),
            ],
            merge_strategy="vote",
        )
        recovered = round_trip(original)
        assert recovered.strategy == "competitive"
        assert len(recovered.branches) == 2
        assert recovered.branches[0].label == "fast"
        assert recovered.branches[0].weight == 0.8
        assert recovered.branches[0].body == [{"op": "tell", "to": "a"}]
        assert recovered.branches[1].body == [{"op": "ask", "from": "b"}]
        assert recovered.merge_strategy == "vote"

    def test_schema_version_in_dict(self):
        b = BranchPrimitive()
        d = b.to_dict()
        assert d["$schema"] == "flux.a2a.branch/v1"
        assert d["op"] == "branch"

    def test_dict_construction(self):
        data = {
            "op": "branch",
            "strategy": "parallel",
            "branches": [{"label": "A", "body": []}],
            "merge": {"strategy": "consensus", "timeout_ms": 10000},
        }
        b = BranchPrimitive.from_dict(data)
        assert b.strategy == "parallel"
        assert len(b.branches) == 1
        assert b.merge_strategy == "consensus"
        assert b.merge_timeout_ms == 10000

    def test_branch_body_weight_clamped(self):
        bb = BranchBody(weight=2.0)
        assert bb.weight == 1.0


# ===========================================================================
# Fork Tests
# ===========================================================================

class TestForkPrimitive:
    def test_default_values(self):
        f = ForkPrimitive()
        assert f.on_complete == "merge"
        assert f.conflict_mode == "negotiate"
        assert f.mutations == []
        assert f.inherit.context is True
        assert f.inherit.trust_graph is False

    def test_json_round_trip(self):
        original = ForkPrimitive(
            inherit=ForkInherit(state=["x", "y"], trust_graph=True),
            mutations=[ForkMutation(type="strategy", changes={"risk": "high"})],
            on_complete="collect",
        )
        recovered = round_trip(original)
        assert recovered.inherit.state == ["x", "y"]
        assert recovered.inherit.trust_graph is True
        assert len(recovered.mutations) == 1
        assert recovered.mutations[0].type == "strategy"
        assert recovered.mutations[0].changes == {"risk": "high"}
        assert recovered.on_complete == "collect"

    def test_schema_version(self):
        f = ForkPrimitive()
        assert f.to_dict()["$schema"] == "flux.a2a.fork/v1"


# ===========================================================================
# CoIterate Tests
# ===========================================================================

class TestCoIteratePrimitive:
    def test_default_values(self):
        c = CoIteratePrimitive()
        assert c.agents == []
        assert c.shared_state_mode == "merge"
        assert c.convergence_threshold == 0.95

    def test_json_round_trip(self):
        original = CoIteratePrimitive(
            agents=["oracle1", "superz"],
            shared_state_mode="partitioned",
            convergence_metric="confidence_delta",
            convergence_threshold=0.99,
        )
        recovered = round_trip(original)
        assert recovered.agents == ["oracle1", "superz"]
        assert recovered.shared_state_mode == "partitioned"
        assert recovered.convergence_metric == "confidence_delta"
        assert recovered.convergence_threshold == 0.99

    def test_schema_version(self):
        c = CoIteratePrimitive()
        assert c.to_dict()["$schema"] == "flux.a2a.co_iterate/v1"


# ===========================================================================
# Discuss Tests
# ===========================================================================

class TestDiscussPrimitive:
    def test_default_values(self):
        d = DiscussPrimitive()
        assert d.format == "peer_review"
        assert d.turn_order == "round_robin"
        assert d.until_condition == "consensus"
        assert d.max_rounds == 5

    def test_json_round_trip(self):
        original = DiscussPrimitive(
            format="debate",
            topic="Binary vs JSON messages",
            participants=[
                Participant(agent="oracle1", stance="pro", role="moderator"),
                Participant(agent="superz", stance="neutral"),
            ],
            max_rounds=10,
        )
        recovered = round_trip(original)
        assert recovered.format == "debate"
        assert recovered.topic == "Binary vs JSON messages"
        assert len(recovered.participants) == 2
        assert recovered.participants[0].agent == "oracle1"
        assert recovered.participants[0].stance == "pro"
        assert recovered.participants[0].role == "moderator"
        assert recovered.participants[1].stance == "neutral"
        assert recovered.max_rounds == 10

    def test_schema_version(self):
        d = DiscussPrimitive(topic="test")
        assert d.to_dict()["$schema"] == "flux.a2a.discuss/v1"

    def test_participant_from_dict(self):
        p = Participant.from_dict({"agent": "test", "stance": "con", "role": "devil"})
        assert p.agent == "test"
        assert p.stance == "con"
        assert p.role == "devil"


# ===========================================================================
# Synthesize Tests
# ===========================================================================

class TestSynthesizePrimitive:
    def test_default_values(self):
        s = SynthesizePrimitive()
        assert s.method == "map_reduce"
        assert s.output_type == "decision"
        assert s.confidence_mode == "propagate"

    def test_json_round_trip(self):
        original = SynthesizePrimitive(
            method="ensemble",
            sources=[
                SynthesisSource(type="branch_result", ref="exploration"),
                SynthesisSource(type="external", ref="human_feedback"),
            ],
            output_type="summary",
        )
        recovered = round_trip(original)
        assert recovered.method == "ensemble"
        assert len(recovered.sources) == 2
        assert recovered.sources[0].type == "branch_result"
        assert recovered.sources[1].ref == "human_feedback"
        assert recovered.output_type == "summary"

    def test_schema_version(self):
        s = SynthesizePrimitive()
        assert s.to_dict()["$schema"] == "flux.a2a.synthesize/v1"


# ===========================================================================
# Reflect Tests
# ===========================================================================

class TestReflectPrimitive:
    def test_default_values(self):
        r = ReflectPrimitive()
        assert r.target == "strategy"
        assert r.method == "introspection"
        assert r.output == "adjustment"

    def test_json_round_trip(self):
        original = ReflectPrimitive(
            target="progress",
            method="benchmark",
            output="question",
            confidence=0.7,
        )
        recovered = round_trip(original)
        assert recovered.target == "progress"
        assert recovered.method == "benchmark"
        assert recovered.output == "question"
        assert recovered.confidence == 0.7

    def test_schema_version(self):
        r = ReflectPrimitive()
        assert r.to_dict()["$schema"] == "flux.a2a.reflect/v1"


# ===========================================================================
# Registry Tests
# ===========================================================================

class TestRegistry:
    def test_all_primitives_registered(self):
        assert len(PRIMITIVE_REGISTRY) == 6
        assert "branch" in PRIMITIVE_REGISTRY
        assert "fork" in PRIMITIVE_REGISTRY
        assert "co_iterate" in PRIMITIVE_REGISTRY
        assert "discuss" in PRIMITIVE_REGISTRY
        assert "synthesize" in PRIMITIVE_REGISTRY
        assert "reflect" in PRIMITIVE_REGISTRY

    def test_parse_branch(self):
        result = parse_primitive({"op": "branch", "branches": []})
        assert isinstance(result, BranchPrimitive)

    def test_parse_fork(self):
        result = parse_primitive({"op": "fork"})
        assert isinstance(result, ForkPrimitive)

    def test_parse_co_iterate(self):
        result = parse_primitive({"op": "co_iterate", "agents": ["a"]})
        assert isinstance(result, CoIteratePrimitive)

    def test_parse_discuss(self):
        result = parse_primitive({"op": "discuss", "topic": "test"})
        assert isinstance(result, DiscussPrimitive)

    def test_parse_synthesize(self):
        result = parse_primitive({"op": "synthesize", "sources": []})
        assert isinstance(result, SynthesizePrimitive)

    def test_parse_reflect(self):
        result = parse_primitive({"op": "reflect"})
        assert isinstance(result, ReflectPrimitive)

    def test_parse_unknown_returns_none(self):
        result = parse_primitive({"op": "let", "name": "x", "value": 1})
        assert result is None

    def test_parse_no_op_returns_none(self):
        result = parse_primitive({"not": "an op"})
        assert result is None
