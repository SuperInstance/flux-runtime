"""
Vocabulary Signaling System — for FLUX agent capability negotiation.

Allows FLUX agents to signal their available vocabularies, compare capabilities,
and negotiate compatible communication protocols.
"""

import os
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class VocabInfo:
    """Information about a single vocabulary."""
    name: str
    pattern_count: int
    version: str = "1.0.0"
    sha256: str = ""

    def compute_hash(self, content: str):
        """Compute SHA256 hash of vocabulary content."""
        self.sha256 = hashlib.sha256(content.encode()).hexdigest()


@dataclass
class Tombstone:
    """Record of a pruned vocabulary."""
    name: str
    pruned_at: str
    reason: str


class VocabManifest:
    """
    Manifest of available vocabularies for a FLUX agent.

    Tracks active vocabularies and pruned (tombstoned) vocabularies.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.vocabularies: List[VocabInfo] = []
        self.tombstones: List[Tombstone] = []

    def add_vocabulary(self, name: str, pattern_count: int, version: str = "1.0.0", content: str = ""):
        """Add a vocabulary to the manifest."""
        vocab = VocabInfo(name=name, pattern_count=pattern_count, version=version)
        if content:
            vocab.compute_hash(content)
        self.vocabularies.append(vocab)

    def add_tombstone(self, name: str, reason: str):
        """Mark a vocabulary as pruned."""
        self.tombstones.append(Tombstone(
            name=name,
            pruned_at=datetime.now().isoformat(),
            reason=reason
        ))

    def generate(self) -> Dict[str, Any]:
        """
        Generate manifest summary as a dictionary.

        Returns:
            Dict containing agent name, vocabulary info, and tombstones.
        """
        return {
            "agent_name": self.agent_name,
            "generated_at": datetime.now().isoformat(),
            "vocabularies": [asdict(v) for v in self.vocabularies],
            "tombstones": [asdict(t) for t in self.tombstones],
            "total_patterns": sum(v.pattern_count for v in self.vocabularies),
            "vocab_count": len(self.vocabularies),
            "tombstone_count": len(self.tombstones)
        }

    def save(self, path: str):
        """
        Write JSON manifest to file.

        Args:
            path: File path to write the manifest.
        """
        manifest = self.generate()
        with open(path, 'w') as f:
            json.dump(manifest, f, indent=2)

    @classmethod
    def load(cls, path: str) -> 'VocabManifest':
        """
        Load manifest from JSON file.

        Args:
            path: File path to read the manifest from.

        Returns:
            VocabManifest instance.
        """
        with open(path, 'r') as f:
            data = json.load(f)

        manifest = cls(agent_name=data["agent_name"])
        for v in data.get("vocabularies", []):
            vocab_info = VocabInfo(**v)
            manifest.vocabularies.append(vocab_info)

        for t in data.get("tombstones", []):
            tombstone = Tombstone(**t)
            manifest.tombstones.append(tombstone)

        return manifest


class VocabCompatibility:
    """
    Compare two vocab manifests and compute compatibility.

    Compatibility score = shared_vocabularies / total_unique_vocabularies
    """

    @staticmethod
    def compare(manifest_a: VocabManifest, manifest_b: VocabManifest) -> Dict[str, Any]:
        """
        Compare two manifests and return compatibility metrics.

        Args:
            manifest_a: First manifest to compare.
            manifest_b: Second manifest to compare.

        Returns:
            Dict containing shared_vocabularies, unique_to_a, unique_to_b,
            and compatibility_score (0-1).
        """
        vocab_set_a = {v.name for v in manifest_a.vocabularies}
        vocab_set_b = {v.name for v in manifest_b.vocabularies}

        shared = vocab_set_a & vocab_set_b
        unique_to_a = vocab_set_a - vocab_set_b
        unique_to_b = vocab_set_b - vocab_set_a

        total_unique = vocab_set_a | vocab_set_b
        compatibility_score = len(shared) / len(total_unique) if total_unique else 0.0

        return {
            "shared_vocabularies": sorted(list(shared)),
            "unique_to_a": sorted(list(unique_to_a)),
            "unique_to_b": sorted(list(unique_to_b)),
            "shared_count": len(shared),
            "unique_to_a_count": len(unique_to_a),
            "unique_to_b_count": len(unique_to_b),
            "compatibility_score": compatibility_score
        }


class RepoSignaler:
    """
    Scan and signal vocabulary information from a repository.

    Analyzes .ese and .fluxvocab files to detect dialects and generate
    business cards describing agent capabilities.
    """

    # Known dialect patterns mapped to domain specialties
    DIALECT_PATTERNS = {
        "maritime": ["maritime", "naval", "ship", "ocean", "port"],
        "math": ["math", "arithmetic", "algebra", "calculus", "sequence"],
        "loops": ["loop", "iterate", "repeat", "while", "for"],
        "core": ["basic", "primitive", "l0", "core", "fundamental"],
        "a2a": ["agent", "negotiate", "coordinate", "handshake"],
        "argumentation": ["argue", "claim", "premise", "conclusion"]
    }

    @staticmethod
    def scan_repo(vocab_dir: str, agent_name: str = "unknown") -> VocabManifest:
        """
        Scan repository directory for vocabulary files and create manifest.

        Args:
            vocab_dir: Directory containing .ese and .fluxvocab files.
            agent_name: Name of the agent for this manifest.

        Returns:
            VocabManifest with scanned vocabulary information.
        """
        manifest = VocabManifest(agent_name=agent_name)

        if not os.path.isdir(vocab_dir):
            return manifest

        # Scan recursively for .ese and .fluxvocab files
        for root, dirs, files in os.walk(vocab_dir):
            for fname in files:
                if fname.endswith('.ese') or fname.endswith('.fluxvocab'):
                    fpath = os.path.join(root, fname)
                    vocab_info = RepoSignaler._parse_vocab_file(fpath)
                    if vocab_info:
                        manifest.vocabularies.append(vocab_info)

        return manifest

    @staticmethod
    def _parse_vocab_file(path: str) -> Optional[VocabInfo]:
        """
        Parse a vocabulary file and extract pattern count.

        Args:
            path: Path to .ese or .fluxvocab file.

        Returns:
            VocabInfo with pattern count and hash, or None if parse fails.
        """
        try:
            with open(path, 'r') as f:
                content = f.read()

            # Count patterns
            # .ese format uses "## pattern:" prefix
            # .fluxvocab format uses "pattern:" or "pattern: " prefix
            pattern_count = 0

            if path.endswith('.ese'):
                pattern_count = len(re.findall(r'^##\s+pattern:', content, re.MULTILINE))
            else:
                pattern_count = len(re.findall(r'^pattern:\s*', content, re.MULTILINE))

            # Get vocabulary name from filename or first pattern
            name = os.path.basename(path)
            name = os.path.splitext(name)[0]

            # Compute hash
            vocab_info = VocabInfo(name=name, pattern_count=pattern_count)
            vocab_info.compute_hash(content)

            return vocab_info

        except Exception:
            return None

    @staticmethod
    def detect_dialect(vocab_dir: str) -> str:
        """
        Identify agent specialty from directory taxonomy and file patterns.

        Args:
            vocab_dir: Directory containing vocabulary files.

        Returns:
            String describing detected dialect/domain.
        """
        if not os.path.isdir(vocab_dir):
            return "unknown"

        # Check directory names
        dir_scores = {}
        for root, dirs, files in os.walk(vocab_dir):
            for d in dirs:
                lower_d = d.lower()
                for dialect, keywords in RepoSignaler.DIALECT_PATTERNS.items():
                    if any(kw in lower_d for kw in keywords):
                        dir_scores[dialect] = dir_scores.get(dialect, 0) + 1

        # Check filenames
        file_scores = {}
        for root, dirs, files in os.walk(vocab_dir):
            for f in files:
                if f.endswith('.ese') or f.endswith('.fluxvocab'):
                    lower_f = f.lower()
                    for dialect, keywords in RepoSignaler.DIALECT_PATTERNS.items():
                        if any(kw in lower_f for kw in keywords):
                            file_scores[dialect] = file_scores.get(dialect, 0) + 1

        # Combine scores
        combined_scores = {}
        all_dialects = set(dir_scores.keys()) | set(file_scores.keys())
        for dialect in all_dialects:
            combined_scores[dialect] = dir_scores.get(dialect, 0) + file_scores.get(dialect, 0)

        if not combined_scores:
            return "general"

        # Return highest scoring dialect
        return max(combined_scores.items(), key=lambda x: x[1])[0]

    @staticmethod
    def business_card(vocab_dir: str) -> str:
        """
        Generate human-readable summary of vocabulary repository.

        Args:
            vocab_dir: Directory containing vocabulary files.

        Returns:
            Multi-line string describing the repository.
        """
        if not os.path.isdir(vocab_dir):
            return "Invalid vocabulary directory"

        # Scan the repository
        manifest = RepoSignaler.scan_repo(vocab_dir)
        dialect = RepoSignaler.detect_dialect(vocab_dir)

        # Build business card
        lines = [
            "=" * 60,
            "FLUX VOCABULARY BUSINESS CARD",
            "=" * 60,
            f"Dialect: {dialect.upper()}",
            f"Vocabularies: {len(manifest.vocabularies)}",
            f"Total Patterns: {sum(v.pattern_count for v in manifest.vocabularies)}",
            "",
            "VOCABULARIES:",
        ]

        for vocab in sorted(manifest.vocabularies, key=lambda v: v.name):
            lines.append(f"  - {vocab.name}: {vocab.pattern_count} patterns")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
