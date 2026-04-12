#!/usr/bin/env python3
"""FLUX Conformance Vector Validator.

Validates generated conformance test vectors by running them against the
Python interpreter. Compares expected vs actual results and reports pass/fail
per vector. Supports auto-fix mode where vectors with incorrect expectations
are updated to match the actual interpreter behavior.

Usage:
    python vector_validator.py vectors/arithmetic.json
    python vector_validator.py vectors/all_vectors.json --fix
    python vector_validator.py vectors/ --all

Author: Super Z (Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Add project root to path for imports ──────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from flux.vm.interpreter import (
    Interpreter,
    VMError,
    VMDivisionByZeroError,
    VMTypeError,
    VMStackOverflowError,
    VMInvalidOpcodeError,
)
from flux.vm.registers import RegisterFile


# ═══════════════════════════════════════════════════════════════════════════
# Validation Result Types
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Result of validating a single test vector."""
    vector_name: str
    status: str  # "PASS", "FAIL", "ERROR", "SKIPPED"
    expected_halted: bool = True
    actual_halted: bool = True
    expected_gp: Dict[str, int] = field(default_factory=dict)
    actual_gp: Dict[str, int] = field(default_factory=dict)
    expected_fp: Dict[str, float] = field(default_factory=dict)
    actual_fp: Dict[str, float] = field(default_factory=dict)
    expected_flags: Dict[str, bool] = field(default_factory=dict)
    actual_flags: Dict[str, bool] = field(default_factory=dict)
    expected_error: str = ""
    actual_error: str = ""
    mismatch_details: List[str] = field(default_factory=list)
    cycles: int = 0

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class ValidationSummary:
    """Summary of validation results across all vectors."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_opcode: Dict[str, Dict[str, int]] = field(default_factory=dict)
    by_tag: Dict[str, Dict[str, int]] = field(default_factory=dict)
    total_cycles: int = 0
    wall_time: float = 0.0
    results: List[ValidationResult] = field(default_factory=list)
    auto_fixed: int = 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100.0


# ═══════════════════════════════════════════════════════════════════════════
# VM Runner
# ═══════════════════════════════════════════════════════════════════════════

class VMRunner:
    """Wraps the FLUX interpreter for running test vectors."""

    def __init__(self, memory_size: int = 65536, max_cycles: int = 100_000) -> None:
        self.memory_size = memory_size
        self.max_cycles = max_cycles

    def run(self, vector: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a test vector and return the resulting VM state.

        Returns a dict with:
            - halted: bool
            - registers: dict (gp, fp, vec)
            - flags: dict (zero, sign, carry, overflow)
            - error: str or ""
            - cycles: int
        """
        bytecode = bytes(vector.get("bytecode", []))
        if not bytecode:
            return {
                "halted": False,
                "registers": {"gp": [0] * 16, "fp": [0.0] * 16},
                "flags": {"zero": False, "sign": False, "carry": False, "overflow": False},
                "error": "empty_bytecode",
                "cycles": 0,
            }

        interp = Interpreter(
            bytecode=bytecode,
            memory_size=self.memory_size,
            max_cycles=self.max_cycles,
        )

        # Set initial register state if provided
        initial_gp = vector.get("initial_gp", {})
        initial_fp = vector.get("initial_fp", {})

        if initial_gp:
            for reg_name, value in initial_gp.items():
                reg_idx = self._parse_reg_index(reg_name)
                if reg_idx is not None and 0 <= reg_idx < 16:
                    interp.regs.write_gp(reg_idx, int(value))

        if initial_fp:
            for reg_name, value in initial_fp.items():
                reg_idx = self._parse_reg_index(reg_name, prefix="F")
                if reg_idx is not None and 0 <= reg_idx < 16:
                    interp.regs.write_fp(reg_idx, float(value))

        # Execute
        error = ""
        error_type = ""
        try:
            cycles = interp.execute()
        except VMError as e:
            error = str(e)
            error_type = type(e).__name__
            cycles = interp.cycle_count
        except Exception as e:
            error = str(e)
            error_type = type(e).__name__
            cycles = interp.cycle_count

        # Extract state
        reg_snap = interp.regs.snapshot()
        flags = {
            "zero": interp._flag_zero,
            "sign": interp._flag_sign,
            "carry": interp._flag_carry,
            "overflow": interp._flag_overflow,
        }

        return {
            "halted": interp.halted,
            "registers": reg_snap,
            "flags": flags,
            "error": error,
            "error_type": error_type,
            "cycles": cycles,
        }

    @staticmethod
    def _parse_reg_index(name: str, prefix: str = "R") -> Optional[int]:
        """Parse register name like 'R0', 'R15', 'F3' to index."""
        if not name or not name.startswith(prefix):
            return None
        try:
            idx = int(name[len(prefix):])
            if 0 <= idx < 16:
                return idx
        except ValueError:
            pass
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Vector Validator
# ═══════════════════════════════════════════════════════════════════════════

class VectorValidator:
    """Validates conformance test vectors against the Python interpreter."""

    def __init__(
        self,
        memory_size: int = 65536,
        max_cycles: int = 100_000,
        verbose: bool = False,
    ) -> None:
        self.runner = VMRunner(memory_size=memory_size, max_cycles=max_cycles)
        self.verbose = verbose

    def validate_vector(self, vector: Dict[str, Any]) -> ValidationResult:
        """Validate a single test vector. Returns detailed result."""
        name = vector.get("name", "unnamed")
        bytecode = vector.get("bytecode")

        if bytecode is None:
            return ValidationResult(
                vector_name=name,
                status="SKIPPED",
                mismatch_details=["No bytecode provided"],
            )

        # Run the vector
        state = self.runner.run(vector)

        result = ValidationResult(
            vector_name=name,
            status="PENDING",
            cycles=state["cycles"],
            expected_halted=vector.get("expected_halted", True),
            actual_halted=state["halted"],
            expected_error=vector.get("expected_error", ""),
            actual_error=state.get("error_type", ""),
            expected_gp=vector.get("expected_gp", {}),
            actual_gp={},
            expected_fp=vector.get("expected_fp", {}),
            actual_fp={},
            expected_flags=vector.get("expected_flags", {}),
            actual_flags={
                "flag_zero": state["flags"]["zero"],
                "flag_sign": state["flags"]["sign"],
                "flag_carry": state["flags"]["carry"],
                "flag_overflow": state["flags"]["overflow"],
            },
        )

        mismatches: List[str] = []

        # Check expected error
        expected_err = vector.get("expected_error", "")
        actual_err = state.get("error_type", "")
        if expected_err:
            if expected_err in actual_err or actual_err in expected_err:
                result.status = "PASS"
                return result
            else:
                mismatches.append(
                    f"Error mismatch: expected '{expected_err}', got '{actual_err}'"
                )
                result.mismatch_details = mismatches
                result.status = "FAIL"
                return result

        # If unexpected error occurred
        if actual_err:
            mismatches.append(f"Unexpected error: {state['error']}")
            result.mismatch_details = mismatches
            result.status = "ERROR"
            return result

        # Check halted state
        if vector.get("expected_halted", True) != state["halted"]:
            mismatches.append(
                f"Halted mismatch: expected={vector.get('expected_halted', True)}, "
                f"actual={state['halted']}"
            )

        # Check GP registers
        gp_regs = state["registers"].get("gp", [0] * 16)
        expected_gp = vector.get("expected_gp", {})
        actual_gp_dict: Dict[str, int] = {}
        for reg_name, expected_val in expected_gp.items():
            idx = VMRunner._parse_reg_index(reg_name)
            if idx is not None and 0 <= idx < len(gp_regs):
                actual_val = gp_regs[idx]
                actual_gp_dict[reg_name] = actual_val
                if actual_val != expected_val:
                    mismatches.append(
                        f"{reg_name}: expected={expected_val}, actual={actual_val}"
                    )
        result.actual_gp = actual_gp_dict

        # Check FP registers
        fp_regs = state["registers"].get("fp", [0.0] * 16)
        expected_fp = vector.get("expected_fp", {})
        actual_fp_dict: Dict[str, float] = {}
        for reg_name, expected_val in expected_fp.items():
            idx = VMRunner._parse_reg_index(reg_name, prefix="F")
            if idx is not None and 0 <= idx < len(fp_regs):
                actual_val = fp_regs[idx]
                actual_fp_dict[reg_name] = actual_val
                if isinstance(expected_val, float):
                    if not math.isclose(actual_val, expected_val, rel_tol=1e-6):
                        mismatches.append(
                            f"{reg_name}: expected={expected_val}, actual={actual_val}"
                        )
                elif actual_val != expected_val:
                    mismatches.append(
                        f"{reg_name}: expected={expected_val}, actual={actual_val}"
                    )
        result.actual_fp = actual_fp_dict

        # Check flags
        flag_map = {
            "flag_zero": "zero",
            "flag_sign": "sign",
            "flag_carry": "carry",
            "flag_overflow": "overflow",
        }
        expected_flags = vector.get("expected_flags", {})
        actual_flags_dict: Dict[str, bool] = {}
        for flag_name, expected_val in expected_flags.items():
            state_key = flag_map.get(flag_name, flag_name.replace("flag_", ""))
            actual_val = state["flags"].get(state_key, False)
            actual_flags_dict[flag_name] = actual_val
            if actual_val != expected_val:
                mismatches.append(
                    f"{flag_name}: expected={expected_val}, actual={actual_val}"
                )
        result.actual_flags = actual_flags_dict

        if mismatches:
            result.status = "FAIL"
            result.mismatch_details = mismatches
        else:
            result.status = "PASS"

        return result

    def validate_vectors(self, vectors: List[Dict[str, Any]]) -> ValidationSummary:
        """Validate a list of test vectors. Returns a summary."""
        start_time = time.time()
        summary = ValidationSummary(total=len(vectors))

        for i, vector in enumerate(vectors):
            result = self.validate_vector(vector)
            summary.results.append(result)
            summary.total_cycles += result.cycles

            # Update counts
            if result.status == "PASS":
                summary.passed += 1
            elif result.status == "FAIL":
                summary.failed += 1
            elif result.status == "ERROR":
                summary.errors += 1
            elif result.status == "SKIPPED":
                summary.skipped += 1

            # Track by category
            cat = vector.get("category", "unknown")
            if cat not in summary.by_category:
                summary.by_category[cat] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIPPED": 0}
            summary.by_category[cat][result.status] += 1

            # Track by opcode
            opcode = vector.get("opcode", "unknown")
            if opcode not in summary.by_opcode:
                summary.by_opcode[opcode] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIPPED": 0}
            summary.by_opcode[opcode][result.status] += 1

            # Track by tag
            for tag in vector.get("tags", []):
                if tag not in summary.by_tag:
                    summary.by_tag[tag] = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIPPED": 0}
                summary.by_tag[tag][result.status] += 1

            if self.verbose:
                status_icon = {"PASS": "✓", "FAIL": "✗", "ERROR": "!", "SKIPPED": "-"}
                icon = status_icon.get(result.status, "?")
                print(f"  [{icon}] {i+1:4d}/{len(vectors)}: {result.vector_name}")

        summary.wall_time = time.time() - start_time
        return summary

    def auto_fix_vector(
        self, vector: Dict[str, Any], result: ValidationResult
    ) -> Tuple[Dict[str, Any], bool]:
        """Auto-fix a vector based on actual interpreter results.

        Returns (fixed_vector, was_modified).
        """
        if result.status == "PASS" or result.status == "SKIPPED":
            return vector, False

        modified = False
        fixed = dict(vector)

        # Fix halted state
        if result.status == "ERROR" and result.actual_error:
            # If we got an unexpected error, mark it
            fixed["expected_error"] = result.actual_error
            fixed["expected_halted"] = False
            modified = True
        else:
            # Fix register mismatches
            if result.actual_gp:
                if "expected_gp" not in fixed:
                    fixed["expected_gp"] = {}
                for reg_name, actual_val in result.actual_gp.items():
                    if reg_name in result.expected_gp:
                        if result.expected_gp[reg_name] != actual_val:
                            fixed["expected_gp"][reg_name] = actual_val
                            modified = True

            # Fix flag mismatches
            if result.actual_flags:
                if "expected_flags" not in fixed:
                    fixed["expected_flags"] = {}
                for flag_name, actual_val in result.actual_flags.items():
                    if flag_name in result.expected_flags:
                        if result.expected_flags[flag_name] != actual_val:
                            fixed["expected_flags"][flag_name] = actual_val
                            modified = True

            # Fix halted state
            if result.actual_halted != vector.get("expected_halted", True):
                fixed["expected_halted"] = result.actual_halted
                modified = True

        return fixed, modified

    def validate_and_fix(
        self, vectors: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], ValidationSummary]:
        """Validate vectors and auto-fix any failures.

        Returns (fixed_vectors, summary).
        """
        summary = self.validate_vectors(vectors)
        fixed_vectors = list(vectors)
        fixes_applied = 0

        for i, result in enumerate(summary.results):
            if result.status in ("FAIL", "ERROR"):
                fixed, modified = self.auto_fix_vector(fixed_vectors[i], result)
                if modified:
                    fixed_vectors[i] = fixed
                    fixes_applied += 1

        summary.auto_fixed = fixes_applied
        return fixed_vectors, summary


# ═══════════════════════════════════════════════════════════════════════════
# Report Formatters
# ═══════════════════════════════════════════════════════════════════════════

def format_summary_text(summary: ValidationSummary) -> str:
    """Format a validation summary as human-readable text."""
    lines = []
    lines.append("=" * 70)
    lines.append("FLUX CONFORMANCE VECTOR VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append(f"")
    lines.append(f"Total vectors:  {summary.total}")
    lines.append(f"Passed:         {summary.passed}")
    lines.append(f"Failed:         {summary.failed}")
    lines.append(f"Errors:         {summary.errors}")
    lines.append(f"Skipped:        {summary.skipped}")
    lines.append(f"Pass rate:      {summary.pass_rate:.1f}%")
    lines.append(f"Total cycles:   {summary.total_cycles:,}")
    lines.append(f"Wall time:      {summary.wall_time:.3f}s")
    if summary.auto_fixed:
        lines.append(f"Auto-fixed:     {summary.auto_fixed}")
    lines.append(f"")

    # By category
    if summary.by_category:
        lines.append("-" * 70)
        lines.append("RESULTS BY CATEGORY")
        lines.append("-" * 70)
        for cat, counts in sorted(summary.by_category.items()):
            total_cat = sum(counts.values())
            passed_cat = counts.get("PASS", 0)
            rate = (passed_cat / total_cat * 100) if total_cat > 0 else 0.0
            status = "OK" if rate == 100.0 else "ISSUES"
            lines.append(
                f"  {cat:20s}  {passed_cat:4d}/{total_cat:4d}  "
                f"({rate:5.1f}%)  [{status}]"
            )
        lines.append("")

    # By opcode (only show failures)
    failed_opcodes = {
        op: counts for op, counts in summary.by_opcode.items()
        if counts.get("FAIL", 0) > 0 or counts.get("ERROR", 0) > 0
    }
    if failed_opcodes:
        lines.append("-" * 70)
        lines.append("FAILING OPCODES")
        lines.append("-" * 70)
        for op, counts in sorted(failed_opcodes.items()):
            fail = counts.get("FAIL", 0)
            err = counts.get("ERROR", 0)
            total_op = sum(counts.values())
            lines.append(
                f"  {op:20s}  {fail} fail, {err} error, {total_op} total"
            )
        lines.append("")

    # Detailed failures
    failures = [r for r in summary.results if r.status in ("FAIL", "ERROR")]
    if failures:
        lines.append("-" * 70)
        lines.append("DETAILED FAILURES")
        lines.append("-" * 70)
        for r in failures:
            lines.append(f"  [{r.status}] {r.vector_name}")
            for detail in r.mismatch_details:
                lines.append(f"         {detail}")
        lines.append("")

    lines.append("=" * 70)
    return "\n".join(lines)


def format_summary_json(summary: ValidationSummary) -> str:
    """Format a validation summary as JSON."""
    data = {
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "errors": summary.errors,
        "skipped": summary.skipped,
        "pass_rate": round(summary.pass_rate, 2),
        "total_cycles": summary.total_cycles,
        "wall_time": round(summary.wall_time, 3),
        "auto_fixed": summary.auto_fixed,
        "by_category": summary.by_category,
        "by_opcode": summary.by_opcode,
        "by_tag": summary.by_tag,
        "failures": [
            {
                "name": r.vector_name,
                "status": r.status,
                "details": r.mismatch_details,
                "cycles": r.cycles,
            }
            for r in summary.results if r.status in ("FAIL", "ERROR")
        ],
    }
    return json.dumps(data, indent=2)


def format_summary_markdown(summary: ValidationSummary) -> str:
    """Format a validation summary as markdown."""
    lines = []
    lines.append("# Conformance Validation Report")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total vectors | {summary.total} |")
    lines.append(f"| Passed | {summary.passed} |")
    lines.append(f"| Failed | {summary.failed} |")
    lines.append(f"| Errors | {summary.errors} |")
    lines.append(f"| Pass rate | {summary.pass_rate:.1f}% |")
    lines.append(f"| Wall time | {summary.wall_time:.3f}s |")
    lines.append("")

    if summary.by_category:
        lines.append("## Results by Category")
        lines.append("")
        lines.append("| Category | Pass | Total | Rate |")
        lines.append("|----------|------|-------|------|")
        for cat, counts in sorted(summary.by_category.items()):
            total_cat = sum(counts.values())
            passed_cat = counts.get("PASS", 0)
            rate = (passed_cat / total_cat * 100) if total_cat > 0 else 0.0
            lines.append(f"| {cat} | {passed_cat} | {total_cat} | {rate:.1f}% |")
        lines.append("")

    failures = [r for r in summary.results if r.status in ("FAIL", "ERROR")]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for r in failures:
            lines.append(f"- **[{r.status}]** {r.vector_name}")
            for detail in r.mismatch_details:
                lines.append(f"  - {detail}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# File I/O
# ═══════════════════════════════════════════════════════════════════════════

def load_vectors(path: str) -> List[Dict[str, Any]]:
    """Load test vectors from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        # Could be wrapped in a top-level key
        for key in ("vectors", "tests", "test_vectors"):
            if key in data:
                return data[key]
    raise ValueError(f"Cannot parse vectors from {path}")


def save_vectors(vectors: List[Dict[str, Any]], path: str) -> None:
    """Save vectors to a JSON file."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(vectors, f, indent=2, default=str)
    print(f"Saved {len(vectors)} vectors to {path}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    """CLI entry point for the conformance vector validator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FLUX Conformance Vector Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a single vector file
  python vector_validator.py vectors/arithmetic.json

  # Validate all JSON files in a directory
  python vector_validator.py vectors/ --all

  # Validate and auto-fix failures
  python vector_validator.py vectors/all_vectors.json --fix

  # Output as JSON
  python vector_validator.py vectors/all_vectors.json --format json

  # Verbose output
  python vector_validator.py vectors/all_vectors.json --verbose
        """,
    )
    parser.add_argument("path", type=str, help="Path to vector JSON file or directory")
    parser.add_argument("--all", action="store_true", help="Validate all JSON files in directory")
    parser.add_argument("--fix", action="store_true", help="Auto-fix failing vectors")
    parser.add_argument("--format", "-f", type=str, default="text",
                        choices=["text", "json", "markdown"],
                        help="Output format (default: text)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", type=str, help="Save results to file")
    parser.add_argument("--max-cycles", type=int, default=100_000,
                        help="Max cycles per vector (default: 100000)")

    args = parser.parse_args()

    # Load vectors
    all_vectors: List[Dict[str, Any]] = []
    if os.path.isdir(args.path):
        if args.all:
            for fname in sorted(os.listdir(args.path)):
                if fname.endswith(".json"):
                    fpath = os.path.join(args.path, fname)
                    try:
                        vecs = load_vectors(fpath)
                        all_vectors.extend(vecs)
                        print(f"Loaded {len(vecs)} vectors from {fname}")
                    except Exception as e:
                        print(f"Error loading {fname}: {e}")
        else:
            print(f"Error: {args.path} is a directory. Use --all to validate all files.")
            return 1
    elif os.path.isfile(args.path):
        try:
            all_vectors = load_vectors(args.path)
            print(f"Loaded {len(all_vectors)} vectors from {args.path}")
        except Exception as e:
            print(f"Error loading {args.path}: {e}")
            return 1
    else:
        print(f"Error: path not found: {args.path}")
        return 1

    if not all_vectors:
        print("No vectors to validate.")
        return 1

    # Validate
    validator = VectorValidator(
        max_cycles=args.max_cycles,
        verbose=args.verbose,
    )

    if args.fix:
        fixed_vectors, summary = validator.validate_and_fix(all_vectors)
        if summary.auto_fixed > 0:
            # Save fixed vectors
            output_path = args.output or args.path
            save_vectors(fixed_vectors, output_path)
            print(f"\nAuto-fixed {summary.auto_fixed} vectors. Saved to {output_path}")
    else:
        summary = validator.validate_vectors(all_vectors)

    # Output report
    formatters = {
        "text": format_summary_text,
        "json": format_summary_json,
        "markdown": format_summary_markdown,
    }
    report = formatters[args.format](summary)

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\nReport saved to {args.output}")
    else:
        print(f"\n{report}")

    # Exit code: 0 if all pass, 1 if any failures
    return 0 if summary.failed == 0 and summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
