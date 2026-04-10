"""
Vocabulary Argumentation Framework — courtroom procedure for agents.

When two agents disagree about vocabulary interpretation, they need formal
objection/sustained mechanics. This provides Dung-style argumentation semantics
for resolving vocabulary conflicts between autonomous agents.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class Argument:
    """An argument in the argumentation framework.

    Represents a claim about vocabulary interpretation with supporting evidence
    and possible objections (counter-arguments).
    """
    claim: str  # The vocabulary interpretation being argued
    evidence: List[str] = field(default_factory=list)  # Supporting reasons
    objections: List['Argument'] = field(default_factory=list)  # Counter-arguments
    confidence: float = 1.0  # 0-1, weight of this argument
    proponent: str = ""  # Agent name making the argument

    def __post_init__(self):
        """Validate confidence is in valid range."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")

    @property
    def support_weight(self) -> float:
        """Total weight of all evidence (simple sum for now)."""
        return len(self.evidence) * self.confidence

    @property
    def objection_weight(self) -> float:
        """Total weight of all objections (recursive)."""
        return sum(obj.confidence for obj in self.objections)

    def add_evidence(self, evidence: str) -> None:
        """Add supporting evidence to this argument."""
        self.evidence.append(evidence)

    def add_objection(self, objection: 'Argument') -> None:
        """Add a counter-argument to this argument."""
        self.objections.append(objection)

    def __repr__(self) -> str:
        return f"Argument(claim='{self.claim[:30]}...', confidence={self.confidence}, proponent='{self.proponent}')"


class ArgumentationFramework:
    """Dung-style argumentation framework for evaluating competing claims.

    Manages a set of arguments with attack relationships (objections) and
    evaluates which arguments are accepted, rejected, or undecided based on
    weighted semantics.
    """

    def __init__(self):
        self.arguments: Dict[str, Argument] = {}
        self._next_id = 0

    def add_argument(self, arg: Argument) -> str:
        """Add an argument to the framework and return its ID."""
        arg_id = f"arg_{self._next_id}"
        self._next_id += 1
        self.arguments[arg_id] = arg
        return arg_id

    def object_to(self, claim_id: str, objection: Argument) -> str:
        """Register an objection to an existing argument.

        Args:
            claim_id: The ID of the argument being objected to
            objection: The counter-argument

        Returns:
            The ID of the newly added objection
        """
        if claim_id not in self.arguments:
            raise KeyError(f"Unknown argument ID: {claim_id}")

        objection_id = self.add_argument(objection)
        self.arguments[claim_id].add_objection(objection)
        return objection_id

    def support(self, claim_id: str, support: Argument) -> str:
        """Register support for an existing argument.

        Note: In Dung semantics, support is handled via the evaluation
        function. This method stores the supporting argument but the
        actual support logic is in evaluate().

        Args:
            claim_id: The ID of the argument being supported
            support: The supporting argument

        Returns:
            The ID of the newly added supporting argument
        """
        if claim_id not in self.arguments:
            raise KeyError(f"Unknown argument ID: {claim_id}")

        support_id = self.add_argument(support)
        # Support is tracked via evidence - add the support claim as evidence
        self.arguments[claim_id].add_evidence(f"Supported by {support_id}: {support.claim}")
        return support_id

    def evaluate(self) -> Dict[str, str]:
        """Evaluate all arguments and determine their status.

        Evaluation rules:
        - An argument is 'accepted' if it has more support than objections
          (by confidence weight)
        - An argument is 'rejected' if objections outweigh support by 2:1
        - Otherwise 'undecided'
        - Defeated arguments can still defeat others (like Dung semantics)

        Returns:
            Dictionary mapping argument IDs to 'accepted', 'rejected', or 'undecided'
        """
        results = {}

        for arg_id, arg in self.arguments.items():
            support_score = arg.support_weight
            objection_score = arg.objection_weight

            # Calculate the ratio
            if objection_score == 0:
                # No objections, accept if there's any support
                status = 'accepted' if support_score > 0 else 'undecided'
            else:
                ratio = support_score / objection_score if objection_score > 0 else float('inf')

                if ratio >= 1.0:
                    status = 'accepted'
                elif ratio <= 0.5:
                    status = 'rejected'
                else:
                    status = 'undecided'

            results[arg_id] = status

        return results

    def get_accepted(self) -> Dict[str, Argument]:
        """Get all accepted arguments."""
        results = self.evaluate()
        return {arg_id: self.arguments[arg_id] for arg_id, status in results.items() if status == 'accepted'}

    def get_rejected(self) -> Dict[str, Argument]:
        """Get all rejected arguments."""
        results = self.evaluate()
        return {arg_id: self.arguments[arg_id] for arg_id, status in results.items() if status == 'rejected'}

    def get_undecided(self) -> Dict[str, Argument]:
        """Get all undecided arguments."""
        results = self.evaluate()
        return {arg_id: self.arguments[arg_id] for arg_id, status in results.items() if status == 'undecided'}

    def __repr__(self) -> str:
        return f"ArgumentationFramework({len(self.arguments)} arguments)"


@dataclass
class VocabInterpretation:
    """A vocabulary interpretation claimed by an agent.

    Represents how an agent interprets a specific pattern, including
    the bytecode they believe should be generated.
    """
    pattern: str  # The vocabulary pattern (e.g., "compute $a + $b")
    bytecode: str  # The bytecode/assembly the agent generates
    agent: str  # Agent name
    confidence: float = 1.0

    def conflicts_with(self, other: 'VocabInterpretation') -> bool:
        """Check if two interpretations conflict (same pattern, different bytecode)."""
        return self.pattern == other.pattern and self.bytecode != other.bytecode

    def __repr__(self) -> str:
        return f"VocabInterpretation(pattern='{self.pattern}', agent='{self.agent}')"


class VocabArbitration:
    """Arbitrator for resolving vocabulary conflicts between agents.

    When two agents disagree about how to interpret a vocabulary pattern,
    this class uses argumentation frameworks to resolve the conflict.
    """

    def __init__(self):
        self.frameworks: Dict[str, ArgumentationFramework] = {}

    def find_conflicts(self,
                      agent1_interpretations: List[VocabInterpretation],
                      agent2_interpretations: List[VocabInterpretation]) -> List[Tuple[VocabInterpretation, VocabInterpretation]]:
        """Find conflicts between two sets of vocabulary interpretations.

        A conflict exists when both agents interpret the same pattern
        but generate different bytecode.

        Returns:
            List of tuples containing conflicting interpretation pairs
        """
        conflicts = []

        # Build lookup by pattern for agent1
        agent1_by_pattern = {interp.pattern: interp for interp in agent1_interpretations}

        for interp2 in agent2_interpretations:
            if interp2.pattern in agent1_by_pattern:
                interp1 = agent1_by_pattern[interp2.pattern]
                if interp1.conflicts_with(interp2):
                    conflicts.append((interp1, interp2))

        return conflicts

    def create_framework_for_conflict(self,
                                     interp1: VocabInterpretation,
                                     interp2: VocabInterpretation) -> ArgumentationFramework:
        """Create an argumentation framework for a single conflict.

        Creates initial arguments representing each agent's interpretation.
        These can then be supported or objected to.
        """
        fw = ArgumentationFramework()

        # Create initial arguments for each interpretation
        arg1 = Argument(
            claim=f"Pattern '{interp1.pattern}' should compile to: {interp1.bytecode}",
            evidence=[f"Agent {interp1.agent} interpretation"],
            confidence=interp1.confidence,
            proponent=interp1.agent
        )

        arg2 = Argument(
            claim=f"Pattern '{interp2.pattern}' should compile to: {interp2.bytecode}",
            evidence=[f"Agent {interp2.agent} interpretation"],
            confidence=interp2.confidence,
            proponent=interp2.agent
        )

        fw.add_argument(arg1)
        fw.add_argument(arg2)

        return fw

    def resolve(self,
                agent1_interpretations: List[VocabInterpretation],
                agent2_interpretations: List[VocabInterpretation],
                agent1_name: str = "Agent1",
                agent2_name: str = "Agent2") -> Dict[str, Any]:
        """Resolve vocabulary conflicts between two agents.

        Args:
            agent1_interpretations: List of vocabulary interpretations from agent 1
            agent2_interpretations: List of vocabulary interpretations from agent 2
            agent1_name: Name of agent 1 (for reporting)
            agent2_name: Name of agent 2 (for reporting)

        Returns:
            Dictionary with:
                - 'conflicts': list of conflict summaries
                - 'resolutions': dict mapping pattern to winning interpretation
                - 'frameworks': dict mapping pattern to ArgumentationFramework
        """
        conflicts = self.find_conflicts(agent1_interpretations, agent2_interpretations)

        conflict_summaries = []
        resolutions = {}
        frameworks = {}

        for interp1, interp2 in conflicts:
            pattern = interp1.pattern
            fw = self.create_framework_for_conflict(interp1, interp2)

            # Evaluate the framework
            results = fw.evaluate()

            # Determine winner
            accepted = fw.get_accepted()

            if len(accepted) == 1:
                # Clear winner
                winner_arg = list(accepted.values())[0]
                winner_name = winner_arg.proponent
                winning_bytecode = interp1.bytecode if winner_name == interp1.agent else interp2.bytecode
                status = f"{winner_name} wins"
            elif len(accepted) == 0:
                # No clear winner - both rejected or undecided
                winner_name = None
                winning_bytecode = None
                status = "No consensus - both interpretations rejected"
            else:
                # Multiple accepted (shouldn't happen with conflict)
                winner_name = None
                winning_bytecode = None
                status = "Multiple accepted - ambiguous"

            conflict_summaries.append({
                'pattern': pattern,
                'agent1_bytecode': interp1.bytecode,
                'agent2_bytecode': interp2.bytecode,
                'status': status
            })

            if winning_bytecode:
                resolutions[pattern] = {
                    'winning_agent': winner_name,
                    'bytecode': winning_bytecode,
                    'rationale': f"Argumentation framework accepted {winner_name}'s interpretation"
                }
            else:
                resolutions[pattern] = {
                    'winning_agent': None,
                    'bytecode': None,
                    'rationale': status
                }

            frameworks[pattern] = fw

        return {
            'conflicts': conflict_summaries,
            'resolutions': resolutions,
            'frameworks': frameworks
        }

    def __repr__(self) -> str:
        return f"VocabArbitration({len(self.frameworks)} frameworks)"
