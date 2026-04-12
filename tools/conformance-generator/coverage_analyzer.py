#!/usr/bin/env python3
"""FLUX Conformance Coverage Analyzer.

Analyzes existing and generated conformance test vectors for coverage gaps.
Identifies opcodes that have no test vectors, opcodes with only happy-path
tests (no edge cases), and suggests new vectors to fill coverage gaps.
Outputs a detailed coverage report in markdown format.

Usage:
    python coverage_analyzer.py
    python coverage_analyzer.py --vectors-dir vectors/
    python coverage_analyzer.py --output coverage_report.md

Author: Super Z (Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ── Add project root to path for imports ──────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ═══════════════════════════════════════════════════════════════════════════
# Opcode Database (mirrored from vector_generator for standalone use)
# ═══════════════════════════════════════════════════════════════════════════

# Try importing from the project; fall back to inline definitions
try:
    from flux.bytecode.opcodes import Op, get_format
    ALL_OPCODES = {name: {"value": int(op), "format": get_format(op)}
                   for name, op in Op.__members__.items()}
except ImportError:
    # Inline fallback: core opcode definitions
    ALL_OPCODES = {
        "NOP": {"value": 0x00, "format": "A"},
        "MOV": {"value": 0x01, "format": "C"},
        "LOAD": {"value": 0x02, "format": "C"},
        "STORE": {"value": 0x03, "format": "C"},
        "JMP": {"value": 0x04, "format": "D"},
        "JZ": {"value": 0x05, "format": "D"},
        "JNZ": {"value": 0x06, "format": "D"},
        "CALL": {"value": 0x07, "format": "D"},
        "IADD": {"value": 0x08, "format": "E"},
        "ISUB": {"value": 0x09, "format": "E"},
        "IMUL": {"value": 0x0A, "format": "E"},
        "IDIV": {"value": 0x0B, "format": "E"},
        "IMOD": {"value": 0x0C, "format": "E"},
        "INEG": {"value": 0x0D, "format": "C"},
        "INC": {"value": 0x0E, "format": "B"},
        "DEC": {"value": 0x0F, "format": "B"},
        "IAND": {"value": 0x10, "format": "E"},
        "IOR": {"value": 0x11, "format": "E"},
        "IXOR": {"value": 0x12, "format": "E"},
        "INOT": {"value": 0x13, "format": "C"},
        "ISHL": {"value": 0x14, "format": "E"},
        "ISHR": {"value": 0x15, "format": "E"},
        "ROTL": {"value": 0x16, "format": "E"},
        "ROTR": {"value": 0x17, "format": "E"},
        "ICMP": {"value": 0x18, "format": "C"},
        "IEQ": {"value": 0x19, "format": "C"},
        "ILT": {"value": 0x1A, "format": "C"},
        "ILE": {"value": 0x1B, "format": "C"},
        "IGT": {"value": 0x1C, "format": "C"},
        "IGE": {"value": 0x1D, "format": "C"},
        "TEST": {"value": 0x1E, "format": "C"},
        "SETCC": {"value": 0x1F, "format": "B"},
        "PUSH": {"value": 0x20, "format": "B"},
        "POP": {"value": 0x21, "format": "B"},
        "DUP": {"value": 0x22, "format": "A"},
        "SWAP": {"value": 0x23, "format": "A"},
        "ROT": {"value": 0x24, "format": "A"},
        "ENTER": {"value": 0x25, "format": "B"},
        "LEAVE": {"value": 0x26, "format": "B"},
        "ALLOCA": {"value": 0x27, "format": "C"},
        "RET": {"value": 0x28, "format": "A"},
        "CALL_IND": {"value": 0x29, "format": "C"},
        "TAILCALL": {"value": 0x2A, "format": "D"},
        "MOVI": {"value": 0x2B, "format": "D"},
        "IREM": {"value": 0x2C, "format": "E"},
        "CMP": {"value": 0x2D, "format": "C"},
        "JE": {"value": 0x2E, "format": "D"},
        "JNE": {"value": 0x2F, "format": "D"},
        "REGION_CREATE": {"value": 0x30, "format": "G"},
        "REGION_DESTROY": {"value": 0x31, "format": "G"},
        "REGION_TRANSFER": {"value": 0x32, "format": "G"},
        "MEMCOPY": {"value": 0x33, "format": "G"},
        "MEMSET": {"value": 0x34, "format": "G"},
        "MEMCMP": {"value": 0x35, "format": "G"},
        "JL": {"value": 0x36, "format": "D"},
        "JGE": {"value": 0x37, "format": "D"},
        "CAST": {"value": 0x38, "format": "C"},
        "BOX": {"value": 0x39, "format": "C"},
        "UNBOX": {"value": 0x3A, "format": "C"},
        "CHECK_TYPE": {"value": 0x3B, "format": "C"},
        "CHECK_BOUNDS": {"value": 0x3C, "format": "C"},
        "CONF": {"value": 0x3D, "format": "D"},
        "MERGE": {"value": 0x3E, "format": "E"},
        "RESTORE": {"value": 0x3F, "format": "D"},
        "FADD": {"value": 0x40, "format": "E"},
        "FSUB": {"value": 0x41, "format": "E"},
        "FMUL": {"value": 0x42, "format": "E"},
        "FDIV": {"value": 0x43, "format": "E"},
        "FNEG": {"value": 0x44, "format": "C"},
        "FABS": {"value": 0x45, "format": "C"},
        "FMIN": {"value": 0x46, "format": "C"},
        "FMAX": {"value": 0x47, "format": "C"},
        "FEQ": {"value": 0x48, "format": "C"},
        "FLT": {"value": 0x49, "format": "C"},
        "FLE": {"value": 0x4A, "format": "C"},
        "FGT": {"value": 0x4B, "format": "C"},
        "FGE": {"value": 0x4C, "format": "C"},
        "JG": {"value": 0x4D, "format": "D"},
        "JLE": {"value": 0x4E, "format": "D"},
        "LOAD8": {"value": 0x4F, "format": "C"},
        "VLOAD": {"value": 0x50, "format": "C"},
        "VSTORE": {"value": 0x51, "format": "C"},
        "VADD": {"value": 0x52, "format": "C"},
        "VSUB": {"value": 0x53, "format": "C"},
        "VMUL": {"value": 0x54, "format": "C"},
        "VDIV": {"value": 0x55, "format": "C"},
        "VFMA": {"value": 0x56, "format": "E"},
        "STORE8": {"value": 0x57, "format": "C"},
        "HALT": {"value": 0x80, "format": "A"},
        "YIELD": {"value": 0x81, "format": "A"},
        "RESOURCE_ACQUIRE": {"value": 0x82, "format": "G"},
        "RESOURCE_RELEASE": {"value": 0x83, "format": "G"},
        "DEBUG_BREAK": {"value": 0x84, "format": "A"},
        "EVOLVE": {"value": 0x7C, "format": "D"},
        "INSTINCT": {"value": 0x7D, "format": "D"},
        "WITNESS": {"value": 0x7E, "format": "D"},
        "SNAPSHOT": {"value": 0x7F, "format": "D"},
    }

# Opcode categories for reporting
OPCODE_CATEGORIES: Dict[str, List[str]] = {
    "control": ["NOP", "HALT", "JMP", "JZ", "JNZ", "JE", "JNE", "JG", "JL", "JGE", "JLE",
                "CALL", "CALL_IND", "TAILCALL", "RET", "MOV", "MOVI"],
    "arithmetic": ["IADD", "ISUB", "IMUL", "IDIV", "IMOD", "IREM", "INEG", "INC", "DEC"],
    "logic": ["IAND", "IOR", "IXOR", "INOT", "ISHL", "ISHR", "ROTL", "ROTR"],
    "comparison": ["ICMP", "IEQ", "ILT", "ILE", "IGT", "IGE", "TEST", "SETCC", "CMP"],
    "stack": ["PUSH", "POP", "DUP", "SWAP", "ROT", "ENTER", "LEAVE", "ALLOCA"],
    "memory": ["LOAD", "STORE", "LOAD8", "STORE8"],
    "float": ["FADD", "FSUB", "FMUL", "FDIV", "FNEG", "FABS", "FMIN", "FMAX",
              "FEQ", "FLT", "FLE", "FGT", "FGE"],
    "simd": ["VLOAD", "VSTORE", "VADD", "VSUB", "VMUL", "VDIV", "VFMA"],
    "type": ["CAST", "BOX", "UNBOX", "CHECK_TYPE", "CHECK_BOUNDS"],
    "meta": ["CONF", "MERGE", "RESTORE"],
    "evolution": ["EVOLVE", "INSTINCT", "WITNESS", "SNAPSHOT"],
    "system": ["YIELD", "DEBUG_BREAK", "RESOURCE_ACQUIRE", "RESOURCE_RELEASE"],
    "a2a": ["TELL", "ASK", "DELEGATE", "DELEGATE_RESULT", "REPORT_STATUS",
            "REQUEST_OVERRIDE", "BROADCAST", "REDUCE", "DECLARE_INTENT",
            "ASSERT_GOAL", "VERIFY_OUTCOME", "EXPLAIN_FAILURE", "SET_PRIORITY",
            "TRUST_CHECK", "TRUST_UPDATE", "TRUST_QUERY", "REVOKE_TRUST",
            "CAP_REQUIRE", "CAP_REQUEST", "CAP_GRANT", "CAP_REVOKE",
            "BARRIER", "SYNC_CLOCK", "FORMATION_UPDATE", "EMERGENCY_STOP"],
    "memory_mgmt": ["REGION_CREATE", "REGION_DESTROY", "REGION_TRANSFER",
                    "MEMCOPY", "MEMSET", "MEMCMP"],
}

# Build reverse map: opcode_name -> category
OPCODE_TO_CATEGORY: Dict[str, str] = {}
for cat, ops in OPCODE_CATEGORIES.items():
    for op in ops:
        OPCODE_TO_CATEGORY[op] = cat

# Edge case tags to look for
EDGE_CASE_TAGS = {
    "error_handling", "edge_case", "boundary", "overflow", "underflow",
    "divide_by_zero", "negative", "overlap_safety", "register_safety",
    "max_value", "min_value", "zero", "backward_jump",
}


# ═══════════════════════════════════════════════════════════════════════════
# Coverage Analysis Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class OpcodeCoverage:
    """Coverage information for a single opcode."""
    name: str
    category: str
    opcode_hex: str
    total_vectors: int = 0
    smoke_vectors: int = 0
    edge_case_vectors: int = 0
    error_vectors: int = 0
    overlap_vectors: int = 0
    has_zero_test: bool = False
    has_negative_test: bool = False
    has_max_test: bool = False
    has_error_test: bool = False
    has_overlap_test: bool = False
    has_boundary_test: bool = False
    vector_names: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

    @property
    def coverage_level(self) -> str:
        """Rate the coverage level."""
        if self.total_vectors == 0:
            return "NONE"
        if self.edge_case_vectors >= 2 and self.error_vectors >= 1:
            return "FULL"
        if self.edge_case_vectors >= 1:
            return "GOOD"
        if self.total_vectors >= 1:
            return "BASIC"
        return "NONE"

    @property
    def suggestions(self) -> List[str]:
        """Suggest new tests to improve coverage."""
        suggestions = []
        if self.total_vectors == 0:
            suggestions.append(f"Add basic smoke test for {self.name}")
        if not self.has_zero_test:
            suggestions.append(f"Add zero-input test for {self.name}")
        if not self.has_negative_test:
            suggestions.append(f"Add negative-value test for {self.name}")
        if not self.has_max_test:
            suggestions.append(f"Add boundary/max-value test for {self.name}")
        if not self.has_error_test and self.name in ("IDIV", "IMOD", "IREM", "FDIV", "VDIV",
                                                       "UNBOX", "CHECK_TYPE", "CHECK_BOUNDS"):
            suggestions.append(f"Add error handling test for {self.name}")
        if not self.has_overlap_test and self.category in ("arithmetic", "logic"):
            suggestions.append(f"Add register overlap safety test for {self.name}")
        if self.edge_case_vectors == 0 and self.total_vectors > 0:
            suggestions.append(f"Add edge case tests for {self.name}")
        return suggestions


@dataclass
class CoverageReport:
    """Full coverage analysis report."""
    total_opcodes: int = 0
    covered_opcodes: int = 0
    uncovered_opcodes: int = 0
    total_vectors: int = 0
    by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_coverage_level: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    opcode_coverage: Dict[str, OpcodeCoverage] = field(default_factory=dict)
    uncovered_list: List[str] = field(default_factory=list)
    needs_edge_cases: List[str] = field(default_factory=list)
    top_suggestions: List[str] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        if self.total_opcodes == 0:
            return 0.0
        return (self.covered_opcodes / self.total_opcodes) * 100.0


# ═══════════════════════════════════════════════════════════════════════════
# Analyzer
# ═══════════════════════════════════════════════════════════════════════════

class CoverageAnalyzer:
    """Analyzes conformance test vector coverage."""

    def __init__(self) -> None:
        self._vectors: List[Dict[str, Any]] = []

    def load_vectors(self, path: str) -> int:
        """Load vectors from a JSON file or directory of JSON files.
        Returns the number of vectors loaded."""
        count = 0
        if os.path.isdir(path):
            for fname in sorted(os.listdir(path)):
                if fname.endswith(".json"):
                    fpath = os.path.join(path, fname)
                    try:
                        with open(fpath) as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            self._vectors.extend(data)
                            count += len(data)
                        elif isinstance(data, dict):
                            for key in ("vectors", "tests", "test_vectors"):
                                if key in data:
                                    items = data[key]
                                    self._vectors.extend(items)
                                    count += len(items)
                                    break
                    except Exception:
                        pass
        elif os.path.isfile(path):
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                self._vectors.extend(data)
                count = len(data)
        return count

    def load_vectors_from_list(self, vectors: List[Dict[str, Any]]) -> int:
        """Load vectors from an in-memory list."""
        self._vectors.extend(vectors)
        return len(vectors)

    def add_existing_conformance_tests(self) -> int:
        """Load the existing conformance tests from test_conformance.py."""
        test_path = os.path.join(_PROJECT_ROOT, "tests", "test_conformance.py")
        if not os.path.exists(test_path):
            return 0
        try:
            # Parse the Python file to extract TEST_VECTORS
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_conformance", test_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            vectors = getattr(mod, "TEST_VECTORS", [])
            self._vectors.extend(vectors)
            return len(vectors)
        except Exception:
            return 0

    def analyze(self) -> CoverageReport:
        """Perform coverage analysis. Returns a CoverageReport."""
        report = CoverageReport()

        # Initialize coverage for all known opcodes
        all_known_ops = set(ALL_OPCODES.keys())
        # Also add A2A ops
        for ops in OPCODE_CATEGORIES.values():
            all_known_ops.update(ops)

        report.total_opcodes = len(all_known_ops)

        # Index vectors by opcode
        vectors_by_opcode: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for vector in self._vectors:
            opcode = vector.get("opcode", "")
            if opcode:
                vectors_by_opcode[opcode].append(vector)

            # Also try to detect opcode from bytecode
            bytecode = vector.get("bytecode", [])
            if bytecode and not opcode:
                opcode_byte = bytecode[0] if bytecode else None
                if opcode_byte is not None:
                    for name, info in ALL_OPCODES.items():
                        if info["value"] == opcode_byte:
                            vectors_by_opcode[name].append(vector)
                            break

            # Also check from name patterns
            name = vector.get("name", "")
            if name and not opcode:
                for op_name in all_known_ops:
                    if op_name in name.upper():
                        vectors_by_opcode[op_name].append(vector)
                        break

        # Analyze each opcode
        for op_name in sorted(all_known_ops):
            cat = OPCODE_TO_CATEGORY.get(op_name, "unknown")
            op_hex = f"0x{ALL_OPCODES.get(op_name, {}).get('value', 0):02X}"
            vecs = vectors_by_opcode.get(op_name, [])

            coverage = OpcodeCoverage(
                name=op_name,
                category=cat,
                opcode_hex=op_hex,
                total_vectors=len(vecs),
            )

            for vec in vecs:
                coverage.vector_names.append(vec.get("name", "unnamed"))
                tags = set(vec.get("tags", []))
                coverage.tags.update(tags)

                is_smoke = "smoke" in tags
                is_error = "error_handling" in tags or vec.get("expected_error", "")
                is_edge = bool(tags & EDGE_CASE_TAGS)
                is_overlap = "overlap_safety" in tags or "overlap" in tags

                if is_smoke:
                    coverage.smoke_vectors += 1
                if is_error:
                    coverage.error_vectors += 1
                if is_edge:
                    coverage.edge_case_vectors += 1
                if is_overlap:
                    coverage.overlap_vectors += 1

                # Check specific properties
                name_lower = vec.get("name", "").lower()
                desc_lower = vec.get("description", "").lower()
                combined = name_lower + " " + desc_lower

                if "zero" in combined or "0 " in name_lower:
                    coverage.has_zero_test = True
                if "negative" in combined or "neg" in name_lower:
                    coverage.has_negative_test = True
                if "max" in combined or "boundary" in combined or "min" in combined:
                    coverage.has_max_test = True
                if is_error:
                    coverage.has_error_test = True
                if is_overlap:
                    coverage.has_overlap_test = True
                if is_edge or "overflow" in combined or "carry" in combined or "borrow" in combined:
                    coverage.has_boundary_test = True

            report.opcode_coverage[op_name] = coverage
            report.total_vectors += len(vecs)

            if len(vecs) > 0:
                report.covered_opcodes += 1
            else:
                report.uncovered_opcodes += 1
                report.uncovered_list.append(op_name)

            if coverage.coverage_level == "BASIC":
                report.needs_edge_cases.append(op_name)

            report.by_coverage_level[coverage.coverage_level] += 1

        # Category-level aggregation
        for cat, ops in OPCODE_CATEGORIES.items():
            cat_coverages = [report.opcode_coverage[op] for op in ops if op in report.opcode_coverage]
            if not cat_coverages:
                continue
            total_in_cat = len(ops)
            covered_in_cat = sum(1 for c in cat_coverages if c.total_vectors > 0)
            total_vecs_in_cat = sum(c.total_vectors for c in cat_coverages)
            full_in_cat = sum(1 for c in cat_coverages if c.coverage_level == "FULL")

            report.by_category[cat] = {
                "total_opcodes": total_in_cat,
                "covered_opcodes": covered_in_cat,
                "coverage_pct": round(covered_in_cat / total_in_cat * 100, 1) if total_in_cat else 0,
                "total_vectors": total_vecs_in_cat,
                "full_coverage": full_in_cat,
            }

        # Top suggestions (priority: uncovered opcodes first, then needs edge cases)
        suggestions: List[str] = []
        for op in report.uncovered_list:
            cat = OPCODE_TO_CATEGORY.get(op, "unknown")
            suggestions.append(f"CRITICAL: No tests for {op} ({cat})")
        for op in report.needs_edge_cases:
            cov = report.opcode_coverage[op]
            for s in cov.suggestions[:2]:  # Top 2 suggestions per opcode
                suggestions.append(s)
        report.top_suggestions = suggestions[:50]  # Limit to 50

        return report


# ═══════════════════════════════════════════════════════════════════════════
# Report Formatters
# ═══════════════════════════════════════════════════════════════════════════

def format_report_markdown(report: CoverageReport) -> str:
    """Format the coverage report as markdown."""
    lines: List[str] = []

    lines.append("# FLUX Conformance Coverage Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total opcodes | {report.total_opcodes} |")
    lines.append(f"| Covered opcodes | {report.covered_opcodes} |")
    lines.append(f"| Uncovered opcodes | {report.uncovered_opcodes} |")
    lines.append(f"| Coverage | {report.coverage_pct:.1f}% |")
    lines.append(f"| Total vectors | {report.total_vectors} |")
    lines.append("")

    # Coverage levels
    lines.append("## Coverage Levels")
    lines.append("")
    lines.append("| Level | Count | Description |")
    lines.append("|-------|-------|-------------|")
    level_desc = {
        "FULL": "Smoke + edge cases + error handling",
        "GOOD": "Smoke + some edge cases",
        "BASIC": "Smoke test only",
        "NONE": "No test vectors",
    }
    for level in ["FULL", "GOOD", "BASIC", "NONE"]:
        count = report.by_coverage_level.get(level, 0)
        desc = level_desc.get(level, "")
        lines.append(f"| {level} | {count} | {desc} |")
    lines.append("")

    # By category
    lines.append("## Coverage by Category")
    lines.append("")
    lines.append("| Category | Covered | Total | Vectors | Coverage |")
    lines.append("|----------|---------|-------|---------|----------|")
    for cat, info in sorted(report.by_category.items()):
        lines.append(
            f"| {cat} | {info['covered_opcodes']} | {info['total_opcodes']} | "
            f"{info['total_vectors']} | {info['coverage_pct']}% |"
        )
    lines.append("")

    # Uncovered opcodes
    if report.uncovered_list:
        lines.append("## Uncovered Opcodes")
        lines.append("")
        lines.append("These opcodes have **no test vectors at all**:")
        lines.append("")
        for op in report.uncovered_list:
            cat = OPCODE_TO_CATEGORY.get(op, "unknown")
            lines.append(f"- `{op}` ({cat})")
        lines.append("")

    # Needs edge cases
    if report.needs_edge_cases:
        lines.append("## Opcodes Needing Edge Cases")
        lines.append("")
        lines.append("These opcodes have basic tests but lack edge cases:")
        lines.append("")
        for op in report.needs_edge_cases:
            cov = report.opcode_coverage[op]
            lines.append(f"- `{op}` ({cov.total_vectors} vectors, level: {cov.coverage_level})")
        lines.append("")

    # Per-opcode detail table
    lines.append("## Full Opcode Coverage Table")
    lines.append("")
    lines.append("| Opcode | Hex | Category | Vectors | Level |")
    lines.append("|--------|-----|----------|---------|-------|")
    for op_name in sorted(report.opcode_coverage.keys()):
        cov = report.opcode_coverage[op_name]
        level_emoji = {
            "FULL": "✅",
            "GOOD": "🟢",
            "BASIC": "🟡",
            "NONE": "🔴",
        }
        emoji = level_emoji.get(cov.coverage_level, "❓")
        lines.append(
            f"| {op_name} | {cov.opcode_hex} | {cov.category} | "
            f"{cov.total_vectors} | {emoji} {cov.coverage_level} |"
        )
    lines.append("")

    # Top suggestions
    if report.top_suggestions:
        lines.append("## Recommended Actions")
        lines.append("")
        for suggestion in report.top_suggestions:
            lines.append(f"- {suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_report_text(report: CoverageReport) -> str:
    """Format the coverage report as plain text."""
    lines: List[str] = []

    lines.append("=" * 70)
    lines.append("FLUX CONFORMANCE COVERAGE ANALYSIS")
    lines.append("=" * 70)
    lines.append(f"")
    lines.append(f"Total opcodes:   {report.total_opcodes}")
    lines.append(f"Covered:         {report.covered_opcodes}")
    lines.append(f"Uncovered:       {report.uncovered_opcodes}")
    lines.append(f"Coverage:        {report.coverage_pct:.1f}%")
    lines.append(f"Total vectors:   {report.total_vectors}")
    lines.append(f"")

    # Coverage levels
    lines.append("-" * 70)
    lines.append("COVERAGE LEVELS")
    lines.append("-" * 70)
    for level in ["FULL", "GOOD", "BASIC", "NONE"]:
        count = report.by_coverage_level.get(level, 0)
        bar = "█" * count + "░" * (max(0, 10 - count))
        lines.append(f"  {level:8s} {count:3d} {bar}")
    lines.append("")

    # By category
    lines.append("-" * 70)
    lines.append("COVERAGE BY CATEGORY")
    lines.append("-" * 70)
    for cat, info in sorted(report.by_category.items()):
        pct = info["coverage_pct"]
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  {cat:20s} {info['covered_opcodes']:3d}/{info['total_opcodes']:3d} "
                      f"{bar} {pct:5.1f}%")
    lines.append("")

    # Uncovered
    if report.uncovered_list:
        lines.append("-" * 70)
        lines.append(f"UNCOVERED OPCODES ({len(report.uncovered_list)})")
        lines.append("-" * 70)
        for op in report.uncovered_list:
            cat = OPCODE_TO_CATEGORY.get(op, "unknown")
            lines.append(f"  ! {op:20s} ({cat})")
        lines.append("")

    # Suggestions
    if report.top_suggestions:
        lines.append("-" * 70)
        lines.append("TOP SUGGESTIONS")
        lines.append("-" * 70)
        for s in report.top_suggestions[:20]:
            lines.append(f"  -> {s}")
        if len(report.top_suggestions) > 20:
            lines.append(f"  ... and {len(report.top_suggestions) - 20} more")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    """CLI entry point for the coverage analyzer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FLUX Conformance Coverage Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze vectors in a directory
  python coverage_analyzer.py --vectors-dir vectors/

  # Include existing conformance tests
  python coverage_analyzer.py --vectors-dir vectors/ --include-existing

  # Output as markdown
  python coverage_analyzer.py --vectors-dir vectors/ --format markdown

  # Save report
  python coverage_analyzer.py --vectors-dir vectors/ --output coverage.md
        """,
    )
    parser.add_argument("--vectors-dir", "-d", type=str, default=None,
                        help="Directory containing vector JSON files")
    parser.add_argument("--vectors-file", "-f", type=str, default=None,
                        help="Single vector JSON file")
    parser.add_argument("--include-existing", action="store_true",
                        help="Include existing conformance tests from test_conformance.py")
    parser.add_argument("--format", type=str, default="text",
                        choices=["text", "markdown"],
                        help="Output format (default: text)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Save report to file")

    args = parser.parse_args()

    analyzer = CoverageAnalyzer()
    total_loaded = 0

    # Load existing conformance tests
    if args.include_existing:
        n = analyzer.add_existing_conformance_tests()
        print(f"Loaded {n} existing conformance tests")
        total_loaded += n

    # Load from directory
    if args.vectors_dir:
        n = analyzer.load_vectors(args.vectors_dir)
        print(f"Loaded {n} vectors from {args.vectors_dir}")
        total_loaded += n

    # Load from file
    if args.vectors_file:
        n = analyzer.load_vectors(args.vectors_file)
        print(f"Loaded {n} vectors from {args.vectors_file}")
        total_loaded += n

    # Default: try ./vectors/
    if total_loaded == 0 and not args.vectors_dir and not args.vectors_file:
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")
        if os.path.isdir(default_dir):
            n = analyzer.load_vectors(default_dir)
            print(f"Loaded {n} vectors from {default_dir}")
            total_loaded += n

    if total_loaded == 0:
        print("No vectors loaded. Use --vectors-dir or --vectors-file.")
        return 1

    # Analyze
    report = analyzer.analyze()

    # Output
    if args.format == "markdown":
        output = format_report_markdown(report)
    else:
        output = format_report_text(report)

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"\nReport saved to {args.output}")
    else:
        print(f"\n{output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
