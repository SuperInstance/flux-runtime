#!/usr/bin/env python3
"""FLUX Expanded Conformance Runner — Executes all 68 test vectors.

Runs each test vector from test_conformance_expanded.py through the
unified interpreter and reports PASS/FAIL/SKIP with details.

Usage:
    python tests/run_expanded_conformance.py
    python tests/run_expanded_conformance.py --trace
    python tests/run_expanded_conformance.py --json-only

Author: Super Z (Cartographer)
Date: 2026-04-12
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from flux.vm.unified_interpreter import run_bytecode, opcode_name
from test_conformance_expanded import TEST_VECTORS

# ── Result Types ─────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
ERROR = "ERROR"


def check_test(test: dict, state: dict) -> dict:
    """Check a single test vector against the VM state.

    Supports:
    - "no_crash": VM must not crash
    - {"register": N, "value": V}: specific register must equal V
    - {"register": N, "value_neq_zero": True}: register must be non-zero
    - {"registers": {N: V, ...}}: multiple registers must match

    Returns a result dict with status, expected, actual, and reason.
    """
    name = test["name"]
    expected = test["expected"]

    if expected == "no_crash":
        if state.get("crashed", False):
            return {
                "name": name, "status": FAIL,
                "category": test.get("category", "unknown"),
                "reason": "VM crashed",
                "expected": "no_crash", "actual": "crashed",
            }
        return {
            "name": name, "status": PASS,
            "category": test.get("category", "unknown"),
            "reason": None, "expected": "no_crash", "actual": "no_crash",
        }

    # Multi-register check
    if isinstance(expected, dict) and "registers" in expected:
        regs_expected = expected["registers"]
        all_match = True
        mismatches = []
        for reg, exp_val in regs_expected.items():
            actual_val = state.get("registers", {}).get(reg, None)
            if actual_val != exp_val:
                all_match = False
                mismatches.append(f"R{reg}={actual_val}, expected {exp_val}")

        if all_match:
            return {
                "name": name, "status": PASS,
                "category": test.get("category", "unknown"),
                "reason": None,
                "expected": {f"R{k}": v for k, v in regs_expected.items()},
                "actual": {f"R{k}": state.get("registers", {}).get(k) for k in regs_expected},
            }
        else:
            return {
                "name": name, "status": FAIL,
                "category": test.get("category", "unknown"),
                "reason": "; ".join(mismatches),
                "expected": {f"R{k}": v for k, v in regs_expected.items()},
                "actual": {f"R{k}": state.get("registers", {}).get(k) for k in regs_expected},
            }

    # Single-register check (backward compatible)
    if isinstance(expected, dict) and "register" in expected:
        reg = expected["register"]
        actual_val = state.get("registers", {}).get(reg, None)
        result_entry = {
            "name": name,
            "category": test.get("category", "unknown"),
        }

        if "value_neq_zero" in expected:
            if actual_val is not None and actual_val != 0:
                result_entry["status"] = PASS
                result_entry["reason"] = None
            else:
                result_entry["status"] = FAIL
                result_entry["reason"] = f"R{reg}={actual_val}, expected nonzero"
            result_entry["expected"] = "nonzero"
            result_entry["actual"] = actual_val
        else:
            exp_val = expected["value"]
            if actual_val == exp_val:
                result_entry["status"] = PASS
                result_entry["reason"] = None
            else:
                result_entry["status"] = FAIL
                result_entry["reason"] = f"R{reg}={actual_val}, expected {exp_val}"
            result_entry["expected"] = exp_val
            result_entry["actual"] = actual_val

        return result_entry

    # Unknown expected format
    return {
        "name": name, "status": SKIP,
        "category": test.get("category", "unknown"),
        "reason": f"Unknown expected format: {type(expected)}",
        "expected": str(expected), "actual": None,
    }


# ── Main runner ─────────────────────────────────────────────────────────────

def run_expanded_conformance(trace: bool = False) -> dict:
    """Run all expanded conformance tests and return the full report."""
    results: List[dict] = []
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    total_cycles = 0

    # Category tracking
    categories: Dict[str, Dict[str, int]] = {}

    for test in TEST_VECTORS:
        name = test["name"]
        category = test.get("category", "unknown")

        if category not in categories:
            categories[category] = {"passed": 0, "failed": 0, "skipped": 0}

        # Skip tests with no bytecode
        if test.get("bytecode") is None:
            results.append({
                "name": name, "status": SKIP, "category": category,
                "reason": "Source description test — needs compiler",
                "expected": None, "actual": None,
            })
            skipped += 1
            categories[category]["skipped"] += 1
            continue

        try:
            state = run_bytecode(test["bytecode"], trace=trace)
            total_cycles += state.get("cycle_count", 0)
            result = check_test(test, state)
            results.append(result)

            if result["status"] == PASS:
                passed += 1
                categories[category]["passed"] += 1
            elif result["status"] == FAIL:
                failed += 1
                categories[category]["failed"] += 1

        except Exception as e:
            results.append({
                "name": name, "status": ERROR, "category": category,
                "reason": str(e),
                "expected": str(test.get("expected")), "actual": None,
            })
            errors += 1

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": "unified_interpreter.py (Python)",
        "isa": "unified (isa_unified.py)",
        "suite": "expanded",
        "summary": {
            "total": len(TEST_VECTORS),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total_cycles": total_cycles,
        },
        "categories": categories,
        "results": results,
    }

    return report


# ── Output formatting ───────────────────────────────────────────────────────

def print_report(report: dict, json_only: bool = False) -> None:
    """Print the conformance report to stdout."""
    if json_only:
        print(json.dumps(report, indent=2))
        return

    summary = report["summary"]
    total = summary["total"]

    print("=" * 72)
    print("  FLUX Expanded Conformance Test Report")
    print(f"  Suite:   {report['suite']}")
    print(f"  Runtime: {report['runtime']}")
    print(f"  ISA:     {report['isa']}")
    print(f"  Date:    {report['timestamp']}")
    print("=" * 72)

    # Summary bar
    bar_len = 40
    runnable = total - summary["skipped"]
    pass_len = int(bar_len * summary["passed"] / max(runnable, 1)) if runnable > 0 else 0
    fail_len = int(bar_len * summary["failed"] / max(runnable, 1)) if runnable > 0 else 0
    skip_len = bar_len - pass_len - fail_len

    bar = ""
    bar += "\u001b[32m" + "#" * pass_len
    bar += "\u001b[31m" + "#" * fail_len
    bar += "\u001b[33m" + "-" * skip_len
    bar += "\u001b[0m"

    print(f"\n  {bar}")
    print(f"  Result: {summary['passed']}/{runnable} passed "
          f"({summary['skipped']} source-only skipped)")
    if summary["errors"] > 0:
        print(f"  Errors: {summary['errors']}")
    print(f"  Cycles: {summary['total_cycles']:,}")

    # Category breakdown
    print("\n  Category Breakdown:")
    print(f"  {'Category':<15} {'PASS':>5} {'FAIL':>5} {'SKIP':>5}")
    print(f"  {'-'*15} {'-'*5} {'-'*5} {'-'*5}")
    for cat, counts in sorted(report["categories"].items()):
        row_total = counts["passed"] + counts["failed"] + counts["skipped"]
        print(f"  {cat:<15} {counts['passed']:>5} {counts['failed']:>5} {counts['skipped']:>5}")

    # Per-test results
    print()
    for r in report["results"]:
        status = r["status"]
        name = r["name"]

        if status == PASS:
            marker = "\u001b[32m  PASS\u001b[0m"
        elif status == FAIL:
            marker = f"\u001b[31m  FAIL\u001b[0m  ({r.get('reason', '')})"
        elif status == SKIP:
            marker = f"\u001b[33m  SKIP\u001b[0m  ({r.get('reason', '')})"
        else:
            marker = f"\u001b[35m ERROR\u001b[0m  ({r.get('reason', '')})"

        cat = r.get("category", "?")
        print(f"  [{cat:>12}] {name}")
        print(f"  {marker}")

        if status in (PASS, FAIL) and r.get("actual") is not None:
            exp = r.get("expected", "?")
            act = r["actual"]
            print(f"         expected={exp}, actual={act}")
        print()

    # Final verdict
    print("=" * 72)
    if summary["failed"] == 0 and summary["errors"] == 0:
        print(f"  VERDICT: ALL {runnable} RUNNABLE TESTS PASSED")
    else:
        print(f"  VERDICT: {summary['failed']} FAILURE(S), {summary['errors']} ERROR(S)")
    print("=" * 72)

    # Write JSON report
    report_path = PROJECT_ROOT / "tools" / "conformance_report_expanded.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  JSON report written to: {report_path}")


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FLUX Expanded Conformance Runner")
    parser.add_argument("--trace", action="store_true", help="Print instruction trace")
    parser.add_argument("--json-only", action="store_true", help="Output only JSON")
    args = parser.parse_args()

    report = run_expanded_conformance(trace=args.trace)
    print_report(report, json_only=args.json_only)

    if report["summary"]["failed"] > 0 or report["summary"]["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
