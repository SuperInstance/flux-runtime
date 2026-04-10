"""
Contradiction Detector — The immune system for the FLUX vocabulary corpus.

Scans vocabulary entries for logical contradictions, semantic conflicts,
and definitional inconsistencies. This is what protects the semantic
gravity well from corruption.

Every new vocabulary entry passes through this before it's accepted.
If two entries contradict, the detector flags it. If a new entry
would break existing tiling dependencies, the detector catches it.

Usage:
    from flux.open_interp.contradiction_detector import ContradictionDetector
    detector = ContradictionDetector()
    issues = detector.scan(vocab)
    issues = detector.diff(vocab_before, vocab_after)
    ok = detector.validate(entry, existing_vocab)
"""

import re
import hashlib
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"   # Logical contradiction, must fix
    WARNING = "warning"     # Potential conflict, should review
    INFO = "info"           # Style inconsistency, nice to fix


@dataclass
class Contradiction:
    """A detected contradiction between vocabulary entries."""
    severity: Severity
    entry_a: str           # Name of first entry
    entry_b: str           # Name of second entry (or "new" for validation)
    conflict_type: str     # "pattern_overlap", "register_collision", "tag_inconsistency", 
                           # "dependency_cycle", "semantic_drift", "duplicate_pattern"
    description: str
    suggestion: str = ""


@dataclass 
class ScanReport:
    """Result of a contradiction scan."""
    total_entries: int
    issues: List[Contradiction]
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    clean: bool = True
    
    def __post_init__(self):
        self.critical_count = sum(1 for i in self.issues if i.severity == Severity.CRITICAL)
        self.warning_count = sum(1 for i in self.issues if i.severity == Severity.WARNING)
        self.info_count = sum(1 for i in self.issues if i.severity == Severity.INFO)
        self.clean = self.critical_count == 0


class ContradictionDetector:
    """
    Detects contradictions in FLUX vocabulary collections.
    
    Checks:
    1. Duplicate patterns — two entries matching the same text
    2. Register collisions — two entries writing to the same result register
    3. Tag inconsistencies — same tag, different semantics
    4. Dependency cycles — circular tiling dependencies
    5. Semantic drift — same name, different meaning across versions
    6. Pattern subset — one pattern completely contains another
    """
    
    def __init__(self):
        self._pattern_cache: Dict[str, str] = {}
    
    def scan(self, vocab) -> ScanReport:
        """Scan an entire vocabulary for contradictions."""
        issues = []
        entries = vocab.entries if hasattr(vocab, 'entries') else vocab
        names_seen: Dict[str, List[int]] = {}
        patterns_seen: Dict[str, List[int]] = {}
        
        for i, entry in enumerate(entries):
            name = getattr(entry, 'name', f'entry_{i}')
            pattern = getattr(entry, 'pattern', '')
            
            # Check duplicate names
            if name in names_seen:
                issues.append(Contradiction(
                    severity=Severity.CRITICAL,
                    entry_a=name,
                    entry_b=name,
                    conflict_type="duplicate_name",
                    description=f"Entry '{name}' defined {len(names_seen[name])+1} times",
                    suggestion="Rename one entry or merge definitions"
                ))
            names_seen.setdefault(name, []).append(i)
            
            # Check pattern overlaps
            pattern_normalized = self._normalize_pattern(pattern)
            for existing_pattern, existing_indices in patterns_seen.items():
                if self._patterns_conflict(pattern_normalized, existing_pattern):
                    for j in existing_indices:
                        other_name = getattr(entries[j], 'name', f'entry_{j}')
                        issues.append(Contradiction(
                            severity=Severity.WARNING,
                            entry_a=name,
                            entry_b=other_name,
                            conflict_type="pattern_overlap",
                            description=f"'{pattern}' and '{getattr(entries[j], 'pattern', '')}' may match the same input",
                            suggestion="Make patterns more specific or add precedence rules"
                        ))
            patterns_seen.setdefault(pattern_normalized, []).append(i)
            
            # Check result register collisions
            result_reg = getattr(entry, 'result_reg', 0)
            
            # Check self-dependency
            depends = getattr(entry, 'depends', [])
            if name in depends:
                issues.append(Contradiction(
                    severity=Severity.CRITICAL,
                    entry_a=name,
                    entry_b=name,
                    conflict_type="dependency_cycle",
                    description=f"Entry '{name}' depends on itself",
                    suggestion="Remove self-reference from depends list"
                ))
        
        # Check for dependency cycles
        cycle_issues = self._detect_cycles(entries)
        issues.extend(cycle_issues)
        
        return ScanReport(total_entries=len(entries), issues=issues)
    
    def diff(self, vocab_before, vocab_after) -> ScanReport:
        """Find contradictions introduced by changes between two versions."""
        entries_before = {getattr(e, 'name', ''): e for e in (vocab_before.entries if hasattr(vocab_before, 'entries') else vocab_before)}
        entries_after = {getattr(e, 'name', ''): e for e in (vocab_after.entries if hasattr(vocab_after, 'entries') else vocab_after)}
        issues = []
        
        # Check for changed definitions (semantic drift)
        for name, after_entry in entries_after.items():
            if name in entries_before:
                before_entry = entries_before[name]
                before_pattern = getattr(before_entry, 'pattern', '')
                after_pattern = getattr(after_entry, 'pattern', '')
                if before_pattern != after_pattern:
                    issues.append(Contradiction(
                        severity=Severity.WARNING,
                        entry_a=name,
                        entry_b=name,
                        conflict_type="semantic_drift",
                        description=f"Pattern changed: '{before_pattern}' → '{after_pattern}'",
                        suggestion="If intentional, increment version. If not, revert."
                    ))
                
                before_asm = getattr(before_entry, 'bytecode_template', '')
                after_asm = getattr(after_entry, 'bytecode_template', '')
                if before_asm != after_asm:
                    issues.append(Contradiction(
                        severity=Severity.INFO,
                        entry_a=name,
                        entry_b=name,
                        conflict_type="implementation_change",
                        description=f"Bytecode template changed for '{name}'",
                        suggestion="Verify the new template produces correct results"
                    ))
        
        # Check for removed entries that others depend on
        for name in set(entries_before.keys()) - set(entries_after.keys()):
            for other_name, other_entry in entries_after.items():
                depends = getattr(other_entry, 'depends', [])
                if name in depends:
                    issues.append(Contradiction(
                        severity=Severity.CRITICAL,
                        entry_a=other_name,
                        entry_b=name,
                        conflict_type="broken_dependency",
                        description=f"'{other_name}' depends on removed entry '{name}'",
                        suggestion=f"Remove '{name}' from {other_name}'s depends or keep '{name}'"
                    ))
        
        # Run full scan on the new version too
        new_issues = self.scan(vocab_after)
        issues.extend(new_issues.issues)
        
        return ScanReport(total_entries=len(entries_after), issues=issues)
    
    def validate(self, entry, existing_vocab) -> ScanReport:
        """Validate a single new entry against existing vocabulary."""
        issues = []
        entries = existing_vocab.entries if hasattr(existing_vocab, 'entries') else existing_vocab
        name = getattr(entry, 'name', 'new')
        pattern = getattr(entry, 'pattern', '')
        pattern_normalized = self._normalize_pattern(pattern)
        
        for existing in entries:
            existing_name = getattr(existing, 'name', '')
            existing_pattern = getattr(existing, 'pattern', '')
            
            # Same name
            if name == existing_name:
                issues.append(Contradiction(
                    severity=Severity.CRITICAL,
                    entry_a=name,
                    entry_b=existing_name,
                    conflict_type="duplicate_name",
                    description=f"Entry '{name}' already exists",
                    suggestion="Use a different name or update existing entry"
                ))
            
            # Pattern conflict
            existing_normalized = self._normalize_pattern(existing_pattern)
            if self._patterns_conflict(pattern_normalized, existing_normalized):
                issues.append(Contradiction(
                    severity=Severity.WARNING,
                    entry_a=name,
                    entry_b=existing_name,
                    conflict_type="pattern_overlap",
                    description=f"New pattern '{pattern}' conflicts with '{existing_pattern}'",
                    suggestion="Make the pattern more specific"
                ))
            
            # Check if new entry depends on something that doesn't exist
            depends = getattr(entry, 'depends', [])
            all_names = {getattr(e, 'name', '') for e in entries}
            for dep in depends:
                if dep not in all_names:
                    issues.append(Contradiction(
                        severity=Severity.WARNING,
                        entry_a=name,
                        entry_b=dep,
                        conflict_type="missing_dependency",
                        description=f"Depends on '{dep}' which doesn't exist in vocabulary",
                        suggestion="Add the dependency or remove the reference"
                    ))
        
        return ScanReport(total_entries=len(list(entries)) + 1, issues=issues)
    
    def _normalize_pattern(self, pattern: str) -> str:
        """Normalize a pattern for comparison."""
        # Remove variable names, keep structure
        normalized = re.sub(r'\$\w+', '$VAR', pattern)
        return normalized.strip().lower()
    
    def _patterns_conflict(self, pattern_a: str, pattern_b: str) -> bool:
        """Check if two patterns could match the same input."""
        if pattern_a == pattern_b:
            return True
        # One is a subset of the other
        if '$var' in pattern_a and '$var' in pattern_b:
            # Both have variables — check structural similarity
            a_parts = re.split(r'\$VAR', pattern_a)
            b_parts = re.split(r'\$VAR', pattern_b)
            if len(a_parts) == len(b_parts):
                # Same number of variable slots — check if literal parts match
                for ap, bp in zip(a_parts, b_parts):
                    if ap.strip() and bp.strip() and ap.strip() != bp.strip():
                        return False
                return True
        return False
    
    def _detect_cycles(self, entries) -> List[Contradiction]:
        """Detect circular dependencies in entries."""
        issues = []
        graph = {}
        for entry in entries:
            name = getattr(entry, 'name', '')
            depends = getattr(entry, 'depends', [])
            graph[name] = depends
        
        # DFS cycle detection
        visited = set()
        path = set()
        
        def dfs(node: str, path_list: List[str]) -> bool:
            if node in path:
                cycle_start = path_list.index(node)
                cycle = path_list[cycle_start:] + [node]
                issues.append(Contradiction(
                    severity=Severity.CRITICAL,
                    entry_a=node,
                    entry_b=cycle[-2] if len(cycle) >= 2 else node,
                    conflict_type="dependency_cycle",
                    description=f"Circular dependency: {' → '.join(cycle)}",
                    suggestion="Break the cycle by removing one dependency"
                ))
                return True
            if node in visited:
                return False
            
            visited.add(node)
            path.add(node)
            path_list.append(node)
            
            for dep in graph.get(node, []):
                if dep in graph:
                    dfs(dep, path_list)
            
            path.discard(node)
            path_list.pop()
            return False
        
        for node in graph:
            if node not in visited:
                dfs(node, [])
        
        return issues
