"""
Ghost Vessel Loader — Resurrect tombstoned vocabulary entries.

When vocabulary entries are pruned from an active vocabulary, they are
"tombstoned" — marked as removed but not deleted entirely. The Ghost Vessel
Loader can resurrect these entries as read-only "ghosts" that new agents
can consult for historical context, debugging, or understanding what
previous agents knew.

This enables:
- Archaeology: Understanding what previous generations of agents knew
- Debugging: Seeing what vocabulary was used to generate old outputs
- Learning: New agents can study deprecated vocabulary patterns
- Resurrection: Selectively restoring useful tombstoned entries

Usage:
    from flux.open_interp.ghost_loader import GhostLoader, GhostEntry

    loader = GhostLoader()
    ghosts = loader.load_tombstones("path/to/tombstones.json")

    # Consult ghosts for context
    relevant = loader.consult(ghosts, "compute fibonacci")

    # Resurrect a ghost if needed
    entry = loader.resurrect(ghosts[0], context={'timestamp': 1234567890})
"""

import json
import os
import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


@dataclass
class GhostEntry:
    """
    A tombstoned vocabulary entry.

    Represents a vocabulary entry that was pruned but preserved as a ghost.
    Ghosts are read-only but can be consulted or resurrected.
    """
    name: str                                    # Name of the entry
    pattern: str                                 # Original regex/template pattern
    bytecode_template: str                       # Original bytecode template
    sha256: str                                  # Hash of the original entry
    pruned_reason: str                           # Why it was pruned
    pruned_at: float                             # Timestamp when pruned
    original_name: str = ""                      # Name before pruning
    description: str = ""                        # Original description
    tags: List[str] = field(default_factory=list) # Original tags
    usage_count: int = 0                         # How many times it was used
    last_used: float = 0.0                       # When it was last used

    def __repr__(self) -> str:
        return f"GhostEntry(name='{self.name}', pruned_reason='{self.pruned_reason[:30]}...')"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'GhostEntry':
        """Create from dictionary."""
        return cls(**data)

    def age_days(self) -> float:
        """Get the age of this ghost in days."""
        return (time.time() - self.pruned_at) / (24 * 3600)

    def is_recent(self, days: int = 30) -> bool:
        """Check if this ghost is from the last N days."""
        return self.age_days() <= days


@dataclass
class ResurrectionContext:
    """
    Context for resurrection operations.

    Provides metadata about why and how a ghost is being resurrected.
    """
    timestamp: float = field(default_factory=time.time)
    agent_name: str = ""
    reason: str = ""
    target_vocabulary: str = ""

    def __repr__(self) -> str:
        return f"ResurrectionContext(agent='{self.agent_name}', reason='{self.reason}')"


@dataclass
class VocabEntry:
    """
    A resurrected vocabulary entry.

    This is what you get after consulting a ghost and extracting its information.
    Can be added back to an active vocabulary.
    """
    name: str
    pattern: str
    bytecode_template: str
    result_reg: int = 0
    description: str = ""
    tags: List[str] = field(default_factory=list)
    _ghost_origin: Optional[GhostEntry] = None  # Track where this came from

    def __repr__(self) -> str:
        return f"VocabEntry(name='{self.name}', pattern='{self.pattern[:30]}...')"

    def compile(self):
        """Compile the pattern (if needed)."""
        import re
        parts = re.split(r'(\$\w+)', self.pattern)
        regex_parts = []
        for part in parts:
            if part.startswith('$'):
                name = part[1:]
                regex_parts.append(f'(?P<{name}>\\d+)')
            else:
                regex_parts.append(re.escape(part))
        regex_str = ''.join(regex_parts).strip()
        self._regex = re.compile(regex_str, re.IGNORECASE)

    def match(self, text: str) -> Optional[Dict[str, str]]:
        """Try to match text against this pattern."""
        if not hasattr(self, '_regex'):
            self.compile()
        m = self._regex.search(text)
        if m:
            return {k: v for k, v in m.groupdict().items() if v is not None}
        return None


class GhostLoader:
    """
    Loads and manages tombstoned vocabulary entries as ghosts.

    Ghosts are read-only historical records of vocabulary that was once
    active but has been pruned. They can be consulted for context or
    selectively resurrected.
    """

    def __init__(self):
        """Initialize the ghost loader."""
        self._ghosts: List[GhostEntry] = []
        self._index: Dict[str, List[GhostEntry]] = {}  # name -> ghosts

    def load_tombstones(self, path: str) -> List[GhostEntry]:
        """
        Load tombstoned entries from a file.

        Args:
            path: Path to tombstones file (JSON format)

        Returns:
            List of GhostEntry objects
        """
        if not os.path.exists(path):
            return []

        with open(path, 'r') as f:
            data = json.load(f)

        ghosts = []
        for entry_data in data.get('tombstones', []):
            ghost = GhostEntry.from_dict(entry_data)
            ghosts.append(ghost)

        self._ghosts = ghosts
        self._rebuild_index()

        return ghosts

    def load_tombstones_from_pruning(self, prune_report, vocab) -> List[GhostEntry]:
        """
        Create ghost entries from a pruning report.

        Args:
            prune_report: PruneReport from VocabularyPruner
            vocab: Original vocabulary (before pruning)

        Returns:
            List of GhostEntry objects for removed entries
        """
        now = time.time()
        ghosts = []

        for removed_name in prune_report.removed:
            # Find the entry in the original vocab
            entry = None
            for e in vocab.entries:
                if e.name == removed_name:
                    entry = e
                    break

            if entry:
                # Create hash
                content = f"{entry.pattern}|{entry.bytecode_template}"
                sha256 = hashlib.sha256(content.encode()).hexdigest()

                ghost = GhostEntry(
                    name=entry.name,
                    pattern=entry.pattern,
                    bytecode_template=entry.bytecode_template,
                    sha256=sha256,
                    pruned_reason="Unused - removed during pruning",
                    pruned_at=now,
                    original_name=entry.name,
                    description=getattr(entry, 'description', ''),
                    tags=getattr(entry, 'tags', []),
                    usage_count=0,  # Would come from tracker if available
                    last_used=0.0
                )
                ghosts.append(ghost)

        self._ghosts.extend(ghosts)
        self._rebuild_index()

        return ghosts

    def save_tombstones(self, path: str, ghosts: Optional[List[GhostEntry]] = None):
        """
        Save tombstoned entries to a file.

        Args:
            path: Path to save tombstones file
            ghosts: List of ghosts to save (default: all loaded ghosts)
        """
        if ghosts is None:
            ghosts = self._ghosts

        data = {
            'version': '1.0',
            'timestamp': time.time(),
            'count': len(ghosts),
            'tombstones': [g.to_dict() for g in ghosts]
        }

        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def resurrect(self, ghost: GhostEntry, context: Optional[dict] = None) -> Optional[VocabEntry]:
        """
        Resurrect a ghost as a full vocabulary entry.

        Args:
            ghost: The ghost entry to resurrect
            context: Optional resurrection context metadata

        Returns:
            VocabEntry that can be added to a vocabulary, or None if resurrection fails
        """
        # Validate the ghost
        if not ghost.pattern or not ghost.bytecode_template:
            return None

        # Create the resurrected entry
        entry = VocabEntry(
            name=ghost.original_name or ghost.name,
            pattern=ghost.pattern,
            bytecode_template=ghost.bytecode_template,
            description=ghost.description,
            tags=ghost.tags,
            _ghost_origin=ghost
        )

        return entry

    def consult(self, ghosts: List[GhostEntry], query: str, limit: int = 5) -> List[GhostEntry]:
        """
        Consult ghosts to find entries matching a query.

        Args:
            ghosts: List of ghosts to search
            query: Search query (text)
            limit: Maximum number of results

        Returns:
            List of matching ghosts, sorted by relevance
        """
        query_lower = query.lower()
        scored = []

        for ghost in ghosts:
            score = 0.0

            # Name match
            if query_lower in ghost.name.lower():
                score += 10.0

            # Pattern match
            if query_lower in ghost.pattern.lower():
                score += 5.0

            # Description match
            if query_lower in ghost.description.lower():
                score += 3.0

            # Tag matches
            for tag in ghost.tags:
                if query_lower in tag.lower():
                    score += 2.0

            # Pruned reason match (for debugging)
            if query_lower in ghost.pruned_reason.lower():
                score += 1.0

            if score > 0:
                scored.append((ghost, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [ghost for ghost, score in scored[:limit]]

    def find_by_name(self, name: str) -> List[GhostEntry]:
        """
        Find all ghosts with a given name.

        Args:
            name: Name to search for

        Returns:
            List of ghosts with that name
        """
        return self._index.get(name, [])

    def find_by_hash(self, sha256: str) -> Optional[GhostEntry]:
        """
        Find a ghost by its SHA256 hash.

        Args:
            sha256: Hash to search for

        Returns:
            GhostEntry if found, None otherwise
        """
        for ghost in self._ghosts:
            if ghost.sha256 == sha256:
                return ghost
        return None

    def find_recent(self, days: int = 30) -> List[GhostEntry]:
        """
        Find ghosts pruned within the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of recent ghosts
        """
        return [g for g in self._ghosts if g.is_recent(days)]

    def get_statistics(self) -> dict:
        """
        Get statistics about loaded ghosts.

        Returns:
            Dictionary with statistics
        """
        if not self._ghosts:
            return {
                'total_ghosts': 0,
                'unique_names': 0,
                'avg_age_days': 0,
                'most_recent': None,
                'oldest': None
            }

        now = time.time()
        ages = [(now - g.pruned_at) / (24 * 3600) for g in self._ghosts]

        unique_names = set(g.name for g in self._ghosts)

        most_recent = min(self._ghosts, key=lambda g: g.pruned_at)
        oldest = max(self._ghosts, key=lambda g: g.pruned_at)

        # Count pruned reasons
        reason_counts = {}
        for ghost in self._ghosts:
            reason = ghost.pruned_reason
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        return {
            'total_ghosts': len(self._ghosts),
            'unique_names': len(unique_names),
            'avg_age_days': sum(ages) / len(ages) if ages else 0,
            'most_recent': most_recent.pruned_at,
            'oldest': oldest.pruned_at,
            'pruned_reasons': reason_counts
        }

    def _rebuild_index(self):
        """Rebuild the name index for faster lookups."""
        self._index = {}
        for ghost in self._ghosts:
            name = ghost.name
            if name not in self._index:
                self._index[name] = []
            self._index[name].append(ghost)

    def merge(self, other_ghosts: List[GhostEntry]):
        """
        Merge another list of ghosts into this loader.

        Args:
            other_ghosts: Ghosts to merge
        """
        # Check for duplicates by hash
        existing_hashes = set(g.sha256 for g in self._ghosts)

        for ghost in other_ghosts:
            if ghost.sha256 not in existing_hashes:
                self._ghosts.append(ghost)
                existing_hashes.add(ghost.sha256)

        self._rebuild_index()

    def clear_recent(self, days: int = 90):
        """
        Clear ghosts older than N days.

        Args:
            days: Age threshold in days
        """
        self._ghosts = [g for g in self._ghosts if g.age_days() <= days]
        self._rebuild_index()


def create_tombstone(vocab_entry, reason: str, usage_count: int = 0,
                     last_used: float = 0.0) -> GhostEntry:
    """
    Convenience function to create a tombstone from a vocabulary entry.

    Args:
        vocab_entry: The vocabulary entry to tombstone
        reason: Why it's being tombstoned
        usage_count: How many times it was used
        last_used: When it was last used

    Returns:
        GhostEntry representing the tombstoned entry
    """
    content = f"{vocab_entry.pattern}|{vocab_entry.bytecode_template}"
    sha256 = hashlib.sha256(content.encode()).hexdigest()

    return GhostEntry(
        name=vocab_entry.name,
        pattern=vocab_entry.pattern,
        bytecode_template=vocab_entry.bytecode_template,
        sha256=sha256,
        pruned_reason=reason,
        pruned_at=time.time(),
        original_name=vocab_entry.name,
        description=getattr(vocab_entry, 'description', ''),
        tags=getattr(vocab_entry, 'tags', []),
        usage_count=usage_count,
        last_used=last_used
    )


# Example usage and testing
if __name__ == '__main__':
    # Create some test ghost entries
    now = time.time()

    test_ghosts = [
        GhostEntry(
            name="factorial",
            pattern="factorial of $n",
            bytecode_template="MOVI R0, ${n}\nHALT",
            sha256="abc123",
            pruned_reason="Unused - replaced by recursive implementation",
            pruned_at=now - 10 * 24 * 3600,  # 10 days ago
            description="Compute factorial",
            tags=["math", "recursive"],
            usage_count=42,
            last_used=now - 15 * 24 * 3600
        ),
        GhostEntry(
            name="fibonacci",
            pattern="fibonacci of $n",
            bytecode_template="MOVI R0, ${n}\nHALT",
            sha256="def456",
            pruned_reason="Unused - inefficient implementation",
            pruned_at=now - 5 * 24 * 3600,  # 5 days ago
            description="Compute fibonacci sequence",
            tags=["math", "sequence"],
            usage_count=15,
            last_used=now - 20 * 24 * 3600
        ),
    ]

    # Test the loader
    loader = GhostLoader()
    loader._ghosts = test_ghosts
    loader._rebuild_index()

    print("Ghost Vessel Loader - Test Run\n")
    print("=" * 70)

    # Test consultation
    print("\n1. Consulting ghosts for 'factorial':")
    results = loader.consult(test_ghosts, "factorial")
    for ghost in results:
        print(f"   - {ghost.name}: {ghost.pruned_reason}")

    # Test resurrection
    print("\n2. Resurrecting 'factorial' ghost:")
    entry = loader.resurrect(test_ghosts[0])
    if entry:
        print(f"   ✓ Resurrected: {entry.name}")
        print(f"   Pattern: {entry.pattern}")
        print(f"   From ghost: {entry._ghost_origin.pruned_reason}")

    # Test statistics
    print("\n3. Ghost statistics:")
    stats = loader.get_statistics()
    print(f"   Total ghosts: {stats['total_ghosts']}")
    print(f"   Unique names: {stats['unique_names']}")
    print(f"   Avg age: {stats['avg_age_days']:.1f} days")
    print(f"   Pruned reasons: {stats['pruned_reasons']}")

    # Test find by name
    print("\n4. Finding ghosts by name 'factorial':")
    by_name = loader.find_by_name("factorial")
    for ghost in by_name:
        print(f"   - {ghost.name} (pruned {ghost.age_days():.1f} days ago)")

    # Test save/load
    print("\n5. Testing save/load:")
    test_path = "/tmp/test_tombstones.json"
    loader.save_tombstones(test_path, test_ghosts)
    loaded = loader.load_tombstones(test_path)
    print(f"   ✓ Saved {len(test_ghosts)} ghosts, loaded {len(loaded)} ghosts")

    # Clean up
    if os.path.exists(test_path):
        os.remove(test_path)

    print("\n" + "=" * 70)
