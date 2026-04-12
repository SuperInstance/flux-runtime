#!/usr/bin/env python3
"""
Semantic Router for FLUX Fleet Task Routing (ROUTE-001)

Reads agent capability profiles from fleet_config.json and routes TASK-BOARD
items to the best-suited agent using a multi-factor scoring algorithm.

Scoring factors:
  1. Skill overlap        — required_skills ∩ agent.domains (weighted by count)
  2. Specialization match — task description keywords vs agent specializations
  3. Confidence weighting — higher self-assessed confidence → better fit
  4. Availability          — agents with fewer active tasks are preferred
  5. Priority matching     — critical tasks demand high-confidence agents
  6. Recency bonus         — recent relevant commits boost score
  7. Effort calibration    — large tasks get a confidence-gate penalty

Usage:
    python semantic_router.py --task ISA-001
    python semantic_router.py --all
    python semantic_router.py --agents
    python semantic_router.py --report > routing-report.md
    python semantic_router.py --score "ISA-001" "Super Z"
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Default paths ────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path(__file__).parent / "fleet_config.json"

# ── Skill Taxonomy ───────────────────────────────────────────────────────────

LANGUAGES = [
    "python", "c", "rust", "go", "typescript", "zig", "java",
    "cuda", "javascript",
]

DOMAINS = [
    "testing", "security", "design", "research", "infra", "docs", "math",
]

SPECIALIZATIONS = [
    "conformance", "bytecode", "isa-design", "edge", "cloud", "a2a",
    "vocabulary", "multilingual", "cuda-kernels", "fleet-coordination",
    "auditing", "spec-writing", "runtime-architecture", "coordination",
    "hardware", "think-tank", "grammatical-analysis", "babel-lattice",
    "viewpoint-opcodes", "fleet-scanning", "auto-repair", "maintenance",
    "signal-language", "cross-specification-analysis",
]

ALL_TAXONOMY = set(LANGUAGES + DOMAINS + SPECIALIZATIONS)

PRIORITY_WEIGHTS = {
    "critical": 1.5,
    "high": 1.2,
    "medium": 1.0,
    "low": 0.8,
}

EFFORT_WEIGHTS = {
    "small": 1.0,
    "medium": 0.9,
    "large": 0.8,
}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AgentProfile:
    """Capability profile for a fleet agent.

    Attributes:
        name: Agent identifier (e.g. "Super Z").
        vessel_repo: GitHub repo path (e.g. "SuperInstance/superz-vessel").
        domains: List of domain/language skills the agent possesses.
        specializations: Narrow specializations within domains.
        confidence_scores: Self-assessed confidence 0-1 per skill.
        recent_commits: List of recent commit metadata.
        task_history: List of tasks the agent has worked on.
        active_tasks: Number of currently active tasks.
    """
    name: str
    vessel_repo: str = ""
    domains: list[str] = field(default_factory=list)
    specializations: list[str] = field(default_factory=list)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    recent_commits: list[dict] = field(default_factory=list)
    task_history: list[dict] = field(default_factory=list)
    active_tasks: int = 0

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self.task_history if t.get("status") == "completed")

    def confidence_for(self, skill: str) -> float:
        """Get confidence score for a skill, defaulting to 0.0."""
        return self.confidence_scores.get(skill, 0.0)

    def has_skill(self, skill: str) -> bool:
        """Check if agent has a skill in either domains or specializations."""
        return skill.lower() in [d.lower() for d in self.domains] or \
               skill.lower() in [s.lower() for s in self.specializations]

    def specialization_match(self, keyword: str) -> bool:
        """Check if any specialization contains the keyword (case-insensitive)."""
        kw = keyword.lower()
        return any(kw in s.lower() for s in self.specializations)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "vessel_repo": self.vessel_repo,
            "domains": self.domains,
            "specializations": self.specializations,
            "confidence_scores": self.confidence_scores,
            "recent_commits": self.recent_commits,
            "task_history": self.task_history,
            "active_tasks": self.active_tasks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentProfile":
        stats = data.get("stats", {})
        return cls(
            name=data["name"],
            vessel_repo=data.get("vessel_repo", ""),
            domains=data.get("domains", []),
            specializations=data.get("specializations", []),
            confidence_scores=data.get("confidence_scores", {}),
            recent_commits=data.get("recent_commits", []),
            task_history=data.get("task_history", []),
            active_tasks=stats.get("active_tasks", 0),
        )


@dataclass
class FleetTask:
    """A task from the TASK-BOARD that needs routing.

    Attributes:
        task_id: Unique identifier (e.g. "ISA-001").
        title: Human-readable task title.
        description: Full task description.
        required_skills: Skills needed to complete this task.
        priority: Task priority level.
        estimated_effort: Rough effort estimate.
        depends_on: List of task IDs this task depends on.
        source: Where the task came from.
    """
    task_id: str
    title: str
    description: str
    required_skills: list[str] = field(default_factory=list)
    priority: str = "medium"
    estimated_effort: str = "medium"
    depends_on: list[str] = field(default_factory=list)
    source: str = "TASK-BOARD"

    @property
    def priority_weight(self) -> float:
        return PRIORITY_WEIGHTS.get(self.priority.lower(), 1.0)

    @property
    def effort_weight(self) -> float:
        return EFFORT_WEIGHTS.get(self.estimated_effort.lower(), 0.9)

    def all_keywords(self) -> list[str]:
        """Extract keywords from title + description for specialization matching."""
        text = (self.title + " " + self.description).lower()
        # Split on non-alphanumeric, filter short words
        words = re.findall(r"[a-z0-9]+", text)
        return [w for w in words if len(w) >= 3]

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "required_skills": self.required_skills,
            "priority": self.priority,
            "estimated_effort": self.estimated_effort,
            "depends_on": self.depends_on,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FleetTask":
        return cls(
            task_id=data["task_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            required_skills=data.get("required_skills", []),
            priority=data.get("priority", "medium"),
            estimated_effort=data.get("estimated_effort", "medium"),
            depends_on=data.get("depends_on", []),
            source=data.get("source", "TASK-BOARD"),
        )


# ── Scoring Details ──────────────────────────────────────────────────────────

@dataclass
class ScoreBreakdown:
    """Detailed scoring breakdown for transparency."""
    skill_overlap: float = 0.0
    skill_overlap_max: float = 0.0
    specialization_bonus: float = 0.0
    confidence_avg: float = 0.0
    availability_bonus: float = 0.0
    priority_penalty: float = 0.0
    recency_bonus: float = 0.0
    effort_penalty: float = 0.0
    total: float = 0.0

    def to_dict(self) -> dict:
        return {
            "skill_overlap": f"{self.skill_overlap:.3f}/{self.skill_overlap_max:.3f}",
            "specialization_bonus": f"{self.specialization_bonus:.3f}",
            "confidence_avg": f"{self.confidence_avg:.3f}",
            "availability_bonus": f"{self.availability_bonus:.3f}",
            "priority_penalty": f"{self.priority_penalty:.3f}",
            "recency_bonus": f"{self.recency_bonus:.3f}",
            "effort_penalty": f"{self.effort_penalty:.3f}",
            "total": f"{self.total:.3f}",
        }


# ── Router Engine ────────────────────────────────────────────────────────────

class SemanticRouter:
    """Routes fleet tasks to the best-suited agent using multi-factor scoring.

    The scoring algorithm considers seven factors:
      1. Skill overlap        (0.35 weight) — Jaccard-like overlap of required_skills vs domains
      2. Specialization match (0.15 weight) — keyword matching against specializations
      3. Confidence weighting (0.20 weight) — average confidence for matched skills
      4. Availability          (0.10 weight) — inverse of active task count
      5. Priority matching     (0.10 weight) — critical tasks need high-confidence agents
      6. Recency bonus         (0.05 weight) — recent commits in related areas
      7. Effort calibration    (0.05 weight) — large tasks penalize low-confidence agents

    Args:
        fleet_config_path: Path to the fleet configuration JSON file.
    """

    # Scoring weights — sum to 1.0
    W_SKILL = 0.35
    W_SPEC = 0.15
    W_CONFIDENCE = 0.20
    W_AVAILABILITY = 0.10
    W_PRIORITY = 0.10
    W_RECENCY = 0.05
    W_EFFORT = 0.05

    def __init__(self, fleet_config_path: str | Path = DEFAULT_CONFIG_PATH):
        self.config_path = Path(fleet_config_path)
        self.agents: list[AgentProfile] = []
        self.tasks: list[FleetTask] = []
        self._load_config()

    def _load_config(self) -> None:
        """Load agent profiles and task definitions from JSON config."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Fleet config not found: {self.config_path}\n"
                f"Run with --init to create a default config, or specify --config <path>"
            )
        with open(self.config_path) as f:
            data = json.load(f)

        for agent_data in data.get("agents", []):
            self.agents.append(AgentProfile.from_dict(agent_data))

        for task_data in data.get("tasks", []):
            self.tasks.append(FleetTask.from_dict(task_data))

    # ── Core Scoring ─────────────────────────────────────────────────────

    def _score_skill_overlap(
        self, agent: AgentProfile, task: FleetTask
    ) -> tuple[float, float]:
        """Factor 1: Skill overlap between required skills and agent domains.

        Uses weighted overlap: each matched skill contributes proportionally
        to the agent's confidence in that skill.

        Returns:
            (score, max_possible) — both in [0.0, 1.0]
        """
        if not task.required_skills:
            return (0.5, 1.0)  # No skills required → neutral

        agent_skills_lower = {s.lower() for s in agent.domains + agent.specializations}
        matched = 0
        weighted = 0.0

        for skill in task.required_skills:
            if skill.lower() in agent_skills_lower:
                matched += 1
                conf = agent.confidence_for(skill)
                weighted += conf

        total = len(task.required_skills)
        # Base overlap ratio
        overlap_ratio = matched / total if total > 0 else 0.0
        # Confidence-weighted overlap
        weighted_ratio = weighted / total if total > 0 else 0.0
        # Blend: 60% coverage ratio + 40% confidence-weighted
        score = 0.6 * overlap_ratio + 0.4 * weighted_ratio
        return (score, 1.0)

    def _score_specialization(
        self, agent: AgentProfile, task: FleetTask
    ) -> float:
        """Factor 2: Specialization keyword matching.

        Extracts keywords from task title + description and matches against
        agent specializations. More matches → higher score.

        Returns:
            Score in [0.0, 1.0]
        """
        keywords = task.all_keywords()
        if not keywords or not agent.specializations:
            return 0.0

        hits = 0
        for kw in keywords:
            if agent.specialization_match(kw):
                hits += 1
            # Also check if any specialization word appears in keywords
            for spec in agent.specializations:
                for spec_word in spec.lower().split("-"):
                    if len(spec_word) >= 3 and kw == spec_word:
                        hits += 0.5  # Partial match

        max_hits = min(len(agent.specializations), len(keywords))
        if max_hits == 0:
            return 0.0
        return min(1.0, hits / max(max_hits, 1))

    def _score_confidence(
        self, agent: AgentProfile, task: FleetTask
    ) -> float:
        """Factor 3: Average confidence for matched required skills.

        Agents with higher confidence in the required skills score better.
        Agents missing a required skill get zero confidence contribution.

        Returns:
            Average confidence in [0.0, 1.0]
        """
        if not task.required_skills:
            return 0.5

        scores = []
        for skill in task.required_skills:
            if agent.has_skill(skill):
                scores.append(agent.confidence_for(skill))
            else:
                scores.append(0.0)

        return sum(scores) / len(scores)

    def _score_availability(self, agent: AgentProfile) -> float:
        """Factor 4: Availability based on active task count.

        Fewer active tasks → higher availability score.
        Uses logarithmic decay to avoid penalizing 1-2 tasks harshly.

        Returns:
            Availability score in [0.0, 1.0]
        """
        if agent.active_tasks == 0:
            return 1.0
        # Logarithmic decay: 0 tasks=1.0, 1=0.85, 2=0.74, 3=0.66, 5=0.56
        return 1.0 / (1.0 + 0.15 * agent.active_tasks)

    def _score_priority(
        self, agent: AgentProfile, task: FleetTask
    ) -> float:
        """Factor 5: Priority-specific confidence gating.

        Critical tasks demand agents with high average confidence (>0.8).
        If the agent's average confidence falls below the threshold, apply
        a penalty proportional to the gap.

        Returns:
            Score in [0.0, 1.0]
        """
        avg_conf = self._score_confidence(agent, task)

        if task.priority == "critical":
            threshold = 0.80
            if avg_conf >= threshold:
                return 1.0
            gap = threshold - avg_conf
            return max(0.0, 1.0 - gap * 2.0)  # Quadratic penalty
        elif task.priority == "high":
            threshold = 0.65
            if avg_conf >= threshold:
                return 1.0
            gap = threshold - avg_conf
            return max(0.0, 1.0 - gap * 1.5)
        else:
            return 1.0  # No penalty for medium/low priority

    def _score_recency(
        self, agent: AgentProfile, task: FleetTask
    ) -> float:
        """Factor 6: Recency bonus for recent relevant commits.

        Checks if agent's recent commits contain keywords from the task.
        More recent and more relevant commits → higher bonus.

        Returns:
            Recency bonus in [0.0, 1.0]
        """
        if not agent.recent_commits:
            return 0.0

        keywords = task.all_keywords()
        if not keywords:
            return 0.0

        total_bonus = 0.0
        now = datetime.now()

        for i, commit in enumerate(agent.recent_commits[:5]):  # Top 5 commits
            msg = commit.get("message", "").lower()
            # Count keyword matches in commit message
            matches = sum(1 for kw in keywords if kw in msg)
            if matches == 0:
                continue

            # Decay factor: most recent commit gets full weight
            recency = 1.0 - (i * 0.15)  # 1.0, 0.85, 0.70, 0.55, 0.40

            # Parse commit date for additional recency weighting
            date_str = commit.get("date", "")
            try:
                commit_date = datetime.strptime(date_str, "%Y-%m-%d")
                days_ago = (now - commit_date).days
                if days_ago < 7:
                    recency *= 1.2
                elif days_ago < 30:
                    recency *= 1.0
                else:
                    recency *= 0.5
            except (ValueError, TypeError):
                pass

            total_bonus += matches * recency * 0.1

        return min(1.0, total_bonus)

    def _score_effort(
        self, agent: AgentProfile, task: FleetTask
    ) -> float:
        """Factor 7: Effort calibration.

        Large tasks that need skills the agent is less confident in
        receive a penalty. Small tasks are unaffected.

        Returns:
            Score in [0.0, 1.0]
        """
        if task.estimated_effort != "large":
            return 1.0

        avg_conf = self._score_confidence(agent, task)
        if avg_conf >= 0.85:
            return 1.0  # High confidence handles large tasks fine
        elif avg_conf >= 0.6:
            return 0.85
        elif avg_conf >= 0.4:
            return 0.6
        else:
            return 0.3  # Low confidence + large task = risky

    def score_agent_task(
        self, agent: AgentProfile, task: FleetTask
    ) -> tuple[float, ScoreBreakdown]:
        """Compute the overall match score for an agent-task pair.

        The score is a weighted combination of all seven factors.

        Args:
            agent: The agent profile to score.
            task: The task to score against.

        Returns:
            (total_score, breakdown) — score in [0.0, 1.0] with detailed breakdown.
        """
        skill_overlap, skill_max = self._score_skill_overlap(agent, task)
        spec_bonus = self._score_specialization(agent, task)
        confidence = self._score_confidence(agent, task)
        availability = self._score_availability(agent)
        priority_score = self._score_priority(agent, task)
        recency = self._score_recency(agent, task)
        effort = self._score_effort(agent, task)

        total = (
            self.W_SKILL * skill_overlap
            + self.W_SPEC * spec_bonus
            + self.W_CONFIDENCE * confidence
            + self.W_AVAILABILITY * availability
            + self.W_PRIORITY * priority_score
            + self.W_RECENCY * recency
            + self.W_EFFORT * effort
        )

        breakdown = ScoreBreakdown(
            skill_overlap=skill_overlap,
            skill_overlap_max=skill_max,
            specialization_bonus=spec_bonus,
            confidence_avg=confidence,
            availability_bonus=availability,
            priority_penalty=priority_score,
            recency_bonus=recency,
            effort_penalty=effort,
            total=total,
        )
        return (total, breakdown)

    # ── Routing ─────────────────────────────────────────────────────────

    def route_task(
        self, task: FleetTask
    ) -> list[tuple[AgentProfile, float, ScoreBreakdown]]:
        """Route a single task to all agents, ranked by score.

        Args:
            task: The task to route.

        Returns:
            List of (agent, score, breakdown) sorted by score descending.
        """
        scored = []
        for agent in self.agents:
            score, breakdown = self.score_agent_task(agent, task)
            scored.append((agent, score, breakdown))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def route_all(
        self, tasks: Optional[list[FleetTask]] = None
    ) -> dict[str, list[tuple[AgentProfile, float, ScoreBreakdown]]]:
        """Batch route multiple tasks.

        Args:
            tasks: Tasks to route. If None, routes all loaded tasks.

        Returns:
            Dict mapping task_id to ranked (agent, score, breakdown) lists.
        """
        if tasks is None:
            tasks = self.tasks
        return {task.task_id: self.route_task(task) for task in tasks}

    def best_agent(self, task: FleetTask) -> Optional[tuple[AgentProfile, float]]:
        """Get the single best agent for a task.

        Args:
            task: The task to route.

        Returns:
            (agent, score) for the best match, or None if no agents.
        """
        results = self.route_task(task)
        if not results:
            return None
        agent, score, _ = results[0]
        return (agent, score)

    # ── Reports ─────────────────────────────────────────────────────────

    def generate_routing_report(self) -> str:
        """Generate a full markdown routing report for all open tasks.

        Returns:
            Markdown string with routing recommendations.
        """
        lines = [
            "# FLUX Fleet Routing Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Agents:** {len(self.agents)}",
            f"**Tasks:** {len(self.tasks)}",
            "",
        ]

        # Summary table
        lines.append("## Routing Summary")
        lines.append("")
        lines.append("| Task | Priority | Best Agent | Score | 2nd Choice | Score |")
        lines.append("|------|----------|------------|-------|------------|-------|")

        all_routes = self.route_all()

        for task in sorted(self.tasks, key=lambda t: t.priority_weight, reverse=True):
            ranked = all_routes.get(task.task_id, [])
            if len(ranked) >= 1:
                best_name = ranked[0][0].name
                best_score = ranked[0][1]
            else:
                best_name = "—"
                best_score = 0.0
            if len(ranked) >= 2:
                second_name = ranked[1][0].name
                second_score = ranked[1][1]
            else:
                second_name = "—"
                second_score = 0.0

            lines.append(
                f"| [{task.task_id}]({task.task_id}) "
                f"{task.title} "
                f"| {task.priority} "
                f"| {best_name} | {best_score:.3f} "
                f"| {second_name} | {second_score:.3f} |"
            )

        # Per-task details
        lines.append("")
        lines.append("## Detailed Routing")
        lines.append("")

        for task in self.tasks:
            ranked = all_routes.get(task.task_id, [])
            lines.append(f"### {task.task_id}: {task.title}")
            lines.append("")
            lines.append(f"**Priority:** {task.priority} | "
                         f"**Effort:** {task.estimated_effort} | "
                         f"**Skills:** {', '.join(task.required_skills) or 'none'}")
            lines.append("")
            lines.append("> " + task.description[:200])
            lines.append("")

            if ranked:
                lines.append("| Rank | Agent | Score | Skills Match | Conf | Avail |")
                lines.append("|------|-------|-------|-------------|------|-------|")
                for rank, (agent, score, bd) in enumerate(ranked, 1):
                    marker = " **← BEST**" if rank == 1 else ""
                    lines.append(
                        f"| {rank} | {agent.name}{marker} | {score:.3f} | "
                        f"{bd.skill_overlap:.0%} | {bd.confidence_avg:.2f} | "
                        f"{bd.availability_bonus:.2f} |"
                    )
            else:
                lines.append("*No agents available for routing.*")
            lines.append("")

        # Agent utilization summary
        lines.append("## Agent Utilization")
        lines.append("")
        lines.append("| Agent | Active Tasks | Completed | Available | Domains | Specs |")
        lines.append("|-------|-------------|-----------|-----------|---------|-------|")

        for agent in sorted(self.agents, key=lambda a: a.name):
            lines.append(
                f"| {agent.name} | {agent.active_tasks} | {agent.completed_tasks} | "
                f"{self._score_availability(agent):.0%} | "
                f"{len(agent.domains)} | {len(agent.specializations)} |"
            )

        # Unrouted tasks (no skill match)
        unrouted = []
        for task in self.tasks:
            ranked = all_routes.get(task.task_id, [])
            if ranked and ranked[0][1] < 0.3:
                unrouted.append(task)

        if unrouted:
            lines.append("")
            lines.append("## ⚠️ Low-Confidence Routes (score < 0.3)")
            lines.append("")
            for task in unrouted:
                ranked = all_routes.get(task.task_id, [])
                best = ranked[0] if ranked else None
                agent_name = best[0].name if best else "none"
                score = best[1] if best else 0.0
                lines.append(f"- **{task.task_id}** → {agent_name} ({score:.3f}): "
                             f"May need manual assignment or skill gap fill")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by semantic_router.py (ROUTE-001)*")
        return "\n".join(lines)

    def generate_agent_report(self) -> str:
        """Generate a report showing all agent profiles.

        Returns:
            Markdown string with agent capability summaries.
        """
        lines = ["# FLUX Fleet Agent Profiles", ""]

        for agent in sorted(self.agents, key=lambda a: a.name):
            lines.append(f"## {agent.name}")
            lines.append("")
            lines.append(f"- **Repo:** `{agent.vessel_repo}`")
            lines.append(f"- **Domains:** {', '.join(agent.domains)}")
            lines.append(f"- **Specializations:** {', '.join(agent.specializations)}")
            lines.append(f"- **Active Tasks:** {agent.active_tasks}")
            lines.append(f"- **Completed Tasks:** {agent.completed_tasks}")

            # Confidence table
            lines.append("")
            lines.append("| Skill | Confidence |")
            lines.append("|-------|-----------|")
            for skill, conf in sorted(
                agent.confidence_scores.items(), key=lambda x: x[1], reverse=True
            ):
                bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
                lines.append(f"| {skill} | {conf:.2f} {bar} |")

            # Recent commits
            if agent.recent_commits:
                lines.append("")
                lines.append("**Recent Commits:**")
                for commit in agent.recent_commits[:3]:
                    lines.append(
                        f"- `{commit.get('date', '?')}` — {commit.get('message', '?')[:80]}"
                    )
            lines.append("")

        return "\n".join(lines)

    # ── Utilities ───────────────────────────────────────────────────────

    def find_task(self, task_id: str) -> Optional[FleetTask]:
        """Look up a task by its ID (case-insensitive)."""
        task_id_lower = task_id.lower()
        for task in self.tasks:
            if task.task_id.lower() == task_id_lower:
                return task
        return None

    def find_agent(self, name: str) -> Optional[AgentProfile]:
        """Look up an agent by name (case-insensitive)."""
        name_lower = name.lower()
        for agent in self.agents:
            if agent.name.lower() == name_lower:
                return agent
        return None

    @property
    def agent_names(self) -> list[str]:
        return [a.name for a in self.agents]

    @property
    def task_ids(self) -> list[str]:
        return [t.task_id for t in self.tasks]


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FLUX Fleet Semantic Router — routes tasks to best-suited agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python semantic_router.py --task ISA-001
  python semantic_router.py --all
  python semantic_router.py --agents
  python semantic_router.py --report > routing-report.md
  python semantic_router.py --score ISA-001 "Super Z"
        """,
    )
    parser.add_argument(
        "--config", type=str, default=str(DEFAULT_CONFIG_PATH),
        help=f"Path to fleet config JSON (default: {DEFAULT_CONFIG_PATH})",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--task", type=str, metavar="TASK_ID",
        help="Route a specific task by ID (e.g. ISA-001)",
    )
    group.add_argument(
        "--all", action="store_true",
        help="Route all open tasks and show summary",
    )
    group.add_argument(
        "--agents", action="store_true",
        help="Show all agent capability profiles",
    )
    group.add_argument(
        "--report", action="store_true",
        help="Generate full routing report (Markdown)",
    )
    group.add_argument(
        "--score", nargs=2, metavar=("TASK_ID", "AGENT_NAME"),
        help="Show detailed score breakdown for a specific agent-task pair",
    )
    group.add_argument(
        "--init", action="store_true",
        help="Create a default fleet_config.json if missing",
    )

    args = parser.parse_args()

    if args.init:
        if DEFAULT_CONFIG_PATH.exists():
            print(f"Config already exists: {DEFAULT_CONFIG_PATH}")
        else:
            print(f"Creating default config: {DEFAULT_CONFIG_PATH}")
            print("ERROR: --init requires a template. Use the fleet_config.json template.")
        return

    try:
        router = SemanticRouter(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.task:
        task = router.find_task(args.task)
        if not task:
            print(f"Task not found: {args.task}", file=sys.stderr)
            print(f"Available tasks: {', '.join(router.task_ids)}", file=sys.stderr)
            sys.exit(1)

        print(f"Routing: {task.task_id} — {task.title}")
        print(f"Priority: {task.priority} | Effort: {task.estimated_effort}")
        print(f"Required skills: {', '.join(task.required_skills) or 'none'}")
        print()

        ranked = router.route_task(task)
        print(f"{'Rank':<5} {'Agent':<20} {'Score':<8} {'Skill':<7} {'Conf':<6} {'Avail':<6} {'Spec':<6}")
        print("-" * 60)
        for rank, (agent, score, bd) in enumerate(ranked, 1):
            marker = " ←" if rank == 1 else ""
            print(
                f"{rank:<5} {agent.name:<20} {score:<8.3f} "
                f"{bd.skill_overlap:<7.1%} {bd.confidence_avg:<6.2f} "
                f"{bd.availability_bonus:<6.2f} {bd.specialization_bonus:<6.2f}{marker}"
            )

    elif args.all:
        all_routes = router.route_all()
        print(f"Fleet Routing Summary — {len(router.agents)} agents, {len(router.tasks)} tasks")
        print()

        for task in sorted(router.tasks, key=lambda t: t.priority_weight, reverse=True):
            ranked = all_routes.get(task.task_id, [])
            if ranked:
                best_name = ranked[0][0].name
                best_score = ranked[0][1]
                second_name = ranked[1][0].name if len(ranked) >= 2 else "—"
                second_score = ranked[1][1] if len(ranked) >= 2 else 0.0
            else:
                best_name = "—"
                best_score = 0.0
                second_name = "—"
                second_score = 0.0

            p_marker = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(task.priority, "⚪")
            print(f"  {p_marker} {task.task_id:<10} {task.title[:40]:<40} → {best_name} ({best_score:.3f}) | 2nd: {second_name} ({second_score:.3f})")

    elif args.agents:
        print(router.generate_agent_report())

    elif args.report:
        print(router.generate_routing_report())

    elif args.score:
        task_id, agent_name = args.score
        task = router.find_task(task_id)
        agent = router.find_agent(agent_name)

        if not task:
            print(f"Task not found: {task_id}", file=sys.stderr)
            print(f"Available: {', '.join(router.task_ids)}", file=sys.stderr)
            sys.exit(1)
        if not agent:
            print(f"Agent not found: {agent_name}", file=sys.stderr)
            print(f"Available: {', '.join(router.agent_names)}", file=sys.stderr)
            sys.exit(1)

        score, bd = router.score_agent_task(agent, task)
        print(f"Score Breakdown: {agent.name} × {task.task_id}")
        print(f"Task: {task.title}")
        print(f"Required skills: {', '.join(task.required_skills)}")
        print()

        print(f"  {'Factor':<25} {'Weight':<8} {'Raw':<8} {'Weighted':<10}")
        print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*10}")
        print(f"  {'Skill Overlap':<25} {SemanticRouter.W_SKILL:<8.2f} {bd.skill_overlap:<8.3f} {SemanticRouter.W_SKILL * bd.skill_overlap:<10.3f}")
        print(f"  {'Specialization Match':<25} {SemanticRouter.W_SPEC:<8.2f} {bd.specialization_bonus:<8.3f} {SemanticRouter.W_SPEC * bd.specialization_bonus:<10.3f}")
        print(f"  {'Confidence Average':<25} {SemanticRouter.W_CONFIDENCE:<8.2f} {bd.confidence_avg:<8.3f} {SemanticRouter.W_CONFIDENCE * bd.confidence_avg:<10.3f}")
        print(f"  {'Availability':<25} {SemanticRouter.W_AVAILABILITY:<8.2f} {bd.availability_bonus:<8.3f} {SemanticRouter.W_AVAILABILITY * bd.availability_bonus:<10.3f}")
        print(f"  {'Priority Match':<25} {SemanticRouter.W_PRIORITY:<8.2f} {bd.priority_penalty:<8.3f} {SemanticRouter.W_PRIORITY * bd.priority_penalty:<10.3f}")
        print(f"  {'Recency Bonus':<25} {SemanticRouter.W_RECENCY:<8.2f} {bd.recency_bonus:<8.3f} {SemanticRouter.W_RECENCY * bd.recency_bonus:<10.3f}")
        print(f"  {'Effort Calibration':<25} {SemanticRouter.W_EFFORT:<8.2f} {bd.effort_penalty:<8.3f} {SemanticRouter.W_EFFORT * bd.effort_penalty:<10.3f}")
        print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*10}")
        print(f"  {'TOTAL':<25} {'1.00':<8} {'':<8} {score:<10.3f}")


if __name__ == "__main__":
    main()
