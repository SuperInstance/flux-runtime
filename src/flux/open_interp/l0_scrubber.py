"""
L0 Constitutional Scrubber — Hostile audit agent for vocabulary primitives.

The L0 Constitutional Scrubber challenges any proposed new L0 primitives against
the existing 7 foundational primitives: SELF, OTHER, POSSIBLE, TRUE, CAUSE, VALUE, AGREEMENT.

It acts as a hostile audit agent, testing candidates for:
- Semantic conflicts with existing L0 primitives
- Redundancy (can be expressed as tilings of existing primitives)
- Edge-case failures
- Conceptual clarity

The scrubber prevents vocabulary bloat and maintains the integrity of the L0 layer.
"""

import re
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class ScrubReport:
    """Report from L0 constitutional scrubbing challenge."""
    candidate: str                          # Name of the candidate primitive
    definition: str                          # Definition/description of the candidate
    passed: bool                            # Whether the candidate passed all challenges
    can_tile: bool                          # True if it's just a composition of existing primitives
    conflicts: List[str]                    # List of conflicts with existing primitives
    challenges: List[str]                   # Edge-case semantic challenges generated
    recommendation: str                     # 'accept', 'reject', 'needs-refinement'
    reasoning: str = ""                     # Detailed reasoning for the recommendation
    semantic_overlap_score: float = 0.0     # 0-1 score of semantic overlap with existing primitives

    def __repr__(self) -> str:
        status = "✓" if self.passed else "✗"
        return f"ScrubReport({status} {self.candidate}: {self.recommendation})"


class L0Scrubber:
    """
    Hostile audit agent that challenges proposed L0 primitives.

    The 7 foundational L0 primitives are:
    - SELF: The agent's own perspective/existence
    - OTHER: Entities outside the agent
    - POSSIBLE: Potential states/alternatives
    - TRUE: Factual verification/correspondence
    - CAUSE: Causal relationships/mechanisms
    - VALUE: Valuation/goodness/preference
    - AGREEMENT: Coordination/alignment between agents

    Any candidate primitive must survive challenges against these.
    """

    L0_PRIMITIVES = ['self', 'other', 'possible', 'true', 'cause', 'value', 'agreement']

    # Semantic patterns for each primitive (simplified pattern matching)
    SEMANTIC_PATTERNS = {
        'self': [
            r'\b(I|me|my|myself|agent|this\s+system)\b',
            r'\b(internal|subjective|first-person)\b',
            r'\b(own|personal|individual)\s+(perspective|view|stance)\b'
        ],
        'other': [
            r'\b(you|they|them|external|outside)\b',
            r'\b(second-person|third-person)\b',
            r'\b(separate|distinct\s+entity)\b'
        ],
        'possible': [
            r'\b(might|could|may|potential|alternativ)\w*\b',
            r'\b(modal|hypothetical|counterfactual)\b',
            r'\b(could\s+be|might\s+have|would\s+be)\b'
        ],
        'true': [
            r'\b(fact|verif|correspond|real|actual)\b',
            r'\b(accurate|correct|valid)\b',
            r'\b(truth|false|error|check|verify)\b'
        ],
        'cause': [
            r'\b(because|due\s+to|leads\s+to|result)\b',
            r'\b(causal|mechanism|effect|consequence)\b',
            r'\b(produces|generates|creates|triggers)\b'
        ],
        'value': [
            r'\b(good|bad|better|worse|prefer)\b',
            r'\b(should|ought|moral|ethical)\b',
            r'\b(util|worth|valuable|desirable)\b'
        ],
        'agreement': [
            r'\b(agree|contract|promise|commit)\b',
            r'\b(coordination|alignment|mutual)\b',
            r'\b(joint|shared|collective)\s+(decision|action)\b'
        ]
    }

    def __init__(self):
        """Initialize the L0 scrubber with compiled semantic patterns."""
        self._compiled_patterns = {}
        for prim, patterns in self.SEMANTIC_PATTERNS.items():
            self._compiled_patterns[prim] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def challenge(self, candidate_name: str, candidate_definition: str) -> ScrubReport:
        """
        Challenge a candidate primitive against the L0 constitution.

        Args:
            candidate_name: Name of the proposed primitive
            candidate_definition: Definition/description of the primitive

        Returns:
            ScrubReport with detailed analysis
        """
        candidate_lower = candidate_name.lower().strip()
        definition_lower = candidate_definition.lower()

        # Initialize report
        report = ScrubReport(
            candidate=candidate_name,
            definition=candidate_definition,
            passed=False,
            can_tile=False,
            conflicts=[],
            challenges=[],
            recommendation='reject',
            semantic_overlap_score=0.0
        )

        # Check 1: Direct name conflict with existing primitives
        if candidate_lower in [p.lower() for p in self.L0_PRIMITIVES]:
            report.conflicts.append(
                f"Direct name conflict: '{candidate_name}' is already an L0 primitive"
            )
            report.recommendation = 'reject'
            report.reasoning = "Cannot redefine existing L0 primitives."
            return report

        # Check 2: Semantic overlap with existing primitives
        overlap_analysis = self._check_semantic_overlap(candidate_lower, definition_lower)
        report.semantic_overlap_score = overlap_analysis['score']
        report.conflicts.extend(overlap_analysis['conflicts'])

        # Check 3: Can tile into existing primitives
        can_tile = self._can_tile_into_existing(candidate_lower, definition_lower)
        report.can_tile = can_tile

        # Check 4: Generate edge-case challenges
        challenges = self._generate_challenges(candidate_lower, definition_lower)
        report.challenges = challenges

        # Check 5: Check for conflicts with existing primitives
        additional_conflicts = self._check_conflicts(candidate_name, candidate_definition)
        report.conflicts.extend(additional_conflicts)

        # Make recommendation
        report = self._make_recommendation(report)

        return report

    def _check_semantic_overlap(self, name: str, definition: str) -> dict:
        """Check semantic overlap with existing L0 primitives."""
        overlapping_prims = []
        total_matches = 0
        max_possible_matches = len(self.L0_PRIMITIVES) * 3  # Heuristic

        combined_text = f"{name} {definition}"

        for prim in self.L0_PRIMITIVES:
            matches = 0
            patterns = self._compiled_patterns.get(prim, [])
            for pattern in patterns:
                if pattern.search(combined_text):
                    matches += 1
                    total_matches += 1

            if matches > 0:
                overlapping_prims.append((prim, matches))

        # Calculate overlap score (0-1)
        score = min(total_matches / max_possible_matches, 1.0)

        conflicts = []
        if overlapping_prims:
            for prim, count in overlapping_prims:
                conflicts.append(
                    f"Semantic overlap with L0 primitive '{prim.upper()}' "
                    f"({count} pattern matches)"
                )

        return {'score': score, 'conflicts': conflicts}

    def _can_tile_into_existing(self, name: str, definition: str) -> bool:
        """
        Check if a candidate can be expressed as a composition of existing primitives.

        This is a heuristic check using keyword analysis. A more sophisticated
        version would use actual semantic decomposition.
        """
        # Combined text for analysis
        combined = f"{name} {definition}".lower()

        # Check for compositional patterns that suggest tiling
        tiling_indicators = [
            r'\b(combination|composition|compound)\s+of\b',
            r'\b(both|and|plus)\s+.*\s+(and|plus)\s+',
            r'\b(mixture|blend|fusion)\b',
            r'\b(corresponds?\s+to)\s+.*\s+(combined|joined|merged)\b'
        ]

        for pattern in tiling_indicators:
            if re.search(pattern, combined):
                return True

        # Check if the definition uses multiple L0 primitives in a compositional way
        used_prims = []
        for prim in self.L0_PRIMITIVES:
            if self._compiled_patterns.get(prim):
                for pat in self._compiled_patterns[prim]:
                    if pat.search(combined):
                        used_prims.append(prim)
                        break

        # If it uses 3 or more L0 primitives in a way that suggests composition
        if len(used_prims) >= 3:
            # Check for compositional language
            compositional_words = ['and', 'plus', 'combined', 'together', 'with']
            if any(word in combined for word in compositional_words):
                return True

        return False

    def _check_conflicts(self, name: str, definition: str) -> List[str]:
        """
        Check if the candidate conflicts with existing L0 primitives.

        Conflicts include:
        - Direct negation of an existing primitive
        - Subset relationship (candidate is narrower version of existing)
        - Contradictory definitions
        """
        conflicts = []
        definition_lower = definition.lower()
        name_lower = name.lower()

        # Check for negation patterns
        for prim in self.L0_PRIMITIVES:
            negation_patterns = [
                f'not {prim}',
                f'no {prim}',
                f'without {prim}',
                f'lack of {prim}',
                f'absence of {prim}'
            ]

            for pattern in negation_patterns:
                if pattern in definition_lower:
                    conflicts.append(
                        f"Negation conflict: Candidate appears to negate "
                        f"L0 primitive '{prim.upper()}'"
                    )
                    break

        # Check for "opposite of" language
        opposite_patterns = [
            r'\b(opposite|inverse|reverse)\s+of\b',
            r'\b(antithesis|negation)\s+of\b'
        ]

        for pattern in opposite_patterns:
            if re.search(pattern, definition_lower):
                conflicts.append(
                    "Candidate defined as 'opposite' or 'inverse' of "
                    "existing concept - likely redundant"
                )

        # Check for subset relationships
        subset_patterns = [
            r'\b(type|kind|form|variant)\s+of\b',
            r'\b(subset|subclass)\s+of\b',
            r'\b(specific|particular)\s+(form|instance)\s+of\b'
        ]

        for pattern in subset_patterns:
            if re.search(pattern, definition_lower):
                # Check if it references an L0 primitive
                for prim in self.L0_PRIMITIVES:
                    if prim in definition_lower:
                        conflicts.append(
                            f"Subset relationship: '{name}' appears to be a "
                            f"specific form of L0 primitive '{prim.upper()}'"
                        )

        return conflicts

    def _generate_challenges(self, name: str, definition: str) -> List[str]:
        """
        Generate edge-case semantic challenges for the candidate.

        These are probing questions that test the robustness and clarity
        of the candidate primitive.
        """
        challenges = []
        combined = f"{name}: {definition}"

        # Challenge 1: Boundary conditions
        challenges.append(
            f"Boundary: What is the negation of '{name}'? "
            f"How do you distinguish '{name}' from 'not-{name}'?"
        )

        # Challenge 2: Relationship to existing primitives
        challenges.append(
            f"L0 Mapping: Which of the 7 L0 primitives can express '{name}'? "
            f"If none, why is it foundational?"
        )

        # Challenge 3: Edge cases
        challenges.append(
            f"Edge Case: What happens when '{name}' is applied to itself? "
            f"Is '{name}' reflexive, transitive, symmetric?"
        )

        # Challenge 4: Measurement/verification
        challenges.append(
            f"Verification: How would an agent verify '{name}'? "
            f"What observation distinguishes '{name}' from non-'{name}'?"
        )

        # Challenge 5: Inter-agent consistency
        challenges.append(
            f"Coordination: If two agents disagree on '{name}', "
            f"how would they resolve the disagreement using existing L0 primitives?"
        )

        # Challenge 6: Necessity
        if self._can_tile_into_existing(name, definition):
            challenges.append(
                f"Tiling: '{name}' appears to be expressible as a composition "
                f"of existing primitives. What does it add that cannot be tiled?"
            )

        # Challenge 7: Circular definitions
        challenges.append(
            f"Circularity: Is '{name}' defined in terms of itself? "
            f"Can '{name}' be understood without reference to '{name}'?"
        )

        return challenges

    def _make_recommendation(self, report: ScrubReport) -> ScrubReport:
        """
        Make a recommendation based on the analysis.

        Rules:
        - High semantic overlap (>0.5) and can tile → reject (redundant)
        - Multiple conflicts → needs refinement or reject
        - Can tile but low overlap → needs refinement
        - Low overlap, no conflicts, passes challenges → accept
        """
        score = report.semantic_overlap_score
        num_conflicts = len(report.conflicts)
        can_tile = report.can_tile

        # High overlap and can tile = redundant
        if score > 0.5 and can_tile:
            report.passed = False
            report.recommendation = 'reject'
            report.reasoning = (
                f"High semantic overlap ({score:.2f}) with existing L0 primitives "
                f"and can be tiled from existing primitives. This is redundant."
            )

        # Multiple conflicts
        elif num_conflicts >= 3:
            report.passed = False
            report.recommendation = 'reject'
            report.reasoning = (
                f"Too many conflicts ({num_conflicts}) with existing L0 constitution. "
                f"Fundamental incompatibility."
            )

        # Can tile = needs refinement
        elif can_tile:
            report.passed = False
            report.recommendation = 'needs-refinement'
            report.reasoning = (
                f"Can be expressed as tiling of existing primitives. "
                f"Must show why it cannot be decomposed."
            )

        # Moderate overlap
        elif score > 0.3:
            report.passed = False
            report.recommendation = 'needs-refinement'
            report.reasoning = (
                f"Moderate semantic overlap ({score:.2f}). "
                f"Must clarify distinction from existing primitives."
            )

        # Some conflicts
        elif num_conflicts > 0:
            report.passed = False
            report.recommendation = 'needs-refinement'
            report.reasoning = (
                f"Has {num_conflicts} conflict(s) with existing L0 primitives. "
                f"Must resolve conflicts."
            )

        # Low overlap, no conflicts = accept
        else:
            report.passed = True
            report.recommendation = 'accept'
            report.reasoning = (
                f"Low semantic overlap ({score:.2f}), no conflicts, "
                f"survived all challenges. Ready for L0 consideration."
            )

        return report

    def batch_challenge(self, candidates: List[Tuple[str, str]]) -> List[ScrubReport]:
        """
        Challenge multiple candidate primitives in batch.

        Args:
            candidates: List of (name, definition) tuples

        Returns:
            List of ScrubReport objects
        """
        return [self.challenge(name, defn) for name, defn in candidates]


def scrub_primitive(name: str, definition: str) -> ScrubReport:
    """
    Convenience function to scrub a single primitive.

    Args:
        name: Name of the candidate primitive
        definition: Definition/description

    Returns:
        ScrubReport with analysis results
    """
    scrubber = L0Scrubber()
    return scrubber.challenge(name, definition)


# Example usage and testing
if __name__ == '__main__':
    # Test cases
    test_candidates = [
        ("BEAUTY", "The aesthetic quality of something"),
        ("ACTION", "What agents do to cause effects in the world"),
        ("KNOWLEDGE", "True beliefs that are justified"),
        ("PREFERENCE", "What an agent values or wants"),
        ("SELF", "My own perspective"),  # Direct conflict
        ("TRUST", "Belief that another agent will act in agreement"),
    ]

    scrubber = L0Scrubber()

    print("L0 Constitutional Scrubber - Test Run\n")
    print("=" * 70)

    for name, definition in test_candidates:
        report = scrubber.challenge(name, definition)

        print(f"\nCandidate: {name}")
        print(f"Definition: {definition}")
        print(f"Status: {'✓ PASS' if report.passed else '✗ FAIL'}")
        print(f"Recommendation: {report.recommendation}")
        print(f"Overlap Score: {report.semantic_overlap_score:.2f}")
        print(f"Can Tile: {report.can_tile}")

        if report.conflicts:
            print(f"Conflicts ({len(report.conflicts)}):")
            for conflict in report.conflicts[:3]:
                print(f"  - {conflict}")

        if report.challenges:
            print(f"Sample Challenges:")
            for challenge in report.challenges[:2]:
                print(f"  - {challenge}")

        print(f"Reasoning: {report.reasoning}")
        print("-" * 70)
