#!/usr/bin/env python3
"""FLUX Conformance Runner — Cross-runtime ISA conformance test executor.

Runs each test vector from the conformance suite through one or more runtimes
(Python, C, Rust) and reports PASS/FAIL/SKIP for each. Outputs a JSON report,
a human-readable summary, and an optional cross-runtime comparison matrix.

Usage:
    python tools/conformance_runner.py
    python tools/conformance_runner.py --expanded
    python tools/conformance_runner.py --runtime python
    python tools/conformance_runner.py --runtime c
    python tools/conformance_runner.py --runtime rust
    python tools/conformance_runner.py --all
    python tools/conformance_runner.py --all --expanded --json-only
    python tools/conformance_runner.py --trace

Author: Super Z (Cartographer)
Date: 2026-04-12
Updated: 2026-04-14 — multi-runtime support (CONF-001)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure the project root is on sys.path so we can import flux packages
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import the test vectors from the conformance test suite
sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from test_conformance import TEST_VECTORS

# Expanded suite available via --expanded flag
EXPANDED_VECTORS = None

# C VM paths
C_VM_SOURCE = PROJECT_ROOT / "src" / "flux" / "vm" / "c" / "flux_vm_unified.c"
C_VM_BINARY = PROJECT_ROOT / "src" / "flux" / "vm" / "c" / "flux_vm_unified"

# Valid runtime names
VALID_RUNTIMES = ("python", "c", "rust")


# ── Result Types ─────────────────────────────────────────────────────────────

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
ERROR = "ERROR"


# ── Vector loading ──────────────────────────────────────────────────────────

def _load_vectors(expanded: bool = False) -> Tuple[list, str]:
    """Load test vectors. Returns (vectors, suite_name)."""
    global EXPANDED_VECTORS
    if expanded:
        if EXPANDED_VECTORS is None:
            from test_conformance_expanded import TEST_VECTORS as _ev
            EXPANDED_VECTORS = _ev
        return EXPANDED_VECTORS, "expanded"
    return TEST_VECTORS, "original"


# ── Test checker (shared across runtimes) ───────────────────────────────────

def check_test(test: dict, state: dict) -> dict:
    """Check a single test vector against the VM state.

    Returns a result dict with status, expected, actual, and reason.
    """
    name = test["name"]
    expected = test["expected"]

    if expected == "no_crash":
        if state.get("crashed", False):
            return {
                "name": name,
                "status": FAIL,
                "category": test.get("category", "unknown"),
                "reason": "VM crashed",
                "expected": "no_crash",
                "actual": "crashed",
            }
        return {
            "name": name,
            "status": PASS,
            "category": test.get("category", "unknown"),
            "reason": None,
            "expected": "no_crash",
            "actual": "no_crash",
        }

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
        "name": name,
        "status": SKIP,
        "category": test.get("category", "unknown"),
        "reason": f"Unknown expected format: {type(expected)}",
        "expected": str(expected),
        "actual": None,
    }


# ── Python Runtime ─────────────────────────────────────────────────────────

def _run_python(test: dict, trace: bool = False) -> dict:
    """Run a single test on the Python unified interpreter."""
    from flux.vm.unified_interpreter import run_bytecode
    state = run_bytecode(test["bytecode"], trace=trace)
    return state


def run_conformance_python(trace: bool = False, expanded: bool = False) -> dict:
    """Run all conformance tests on the Python unified interpreter."""
    vectors, suite_name = _load_vectors(expanded)
    results: List[dict] = []
    passed = failed = skipped = errors = 0
    total_cycles = 0

    for test in vectors:
        name = test["name"]
        category = test.get("category", "unknown")

        if test.get("bytecode") is None:
            results.append({
                "name": name, "status": SKIP, "category": category,
                "reason": "Source description test — needs compiler",
                "expected": None, "actual": None,
            })
            skipped += 1
            continue

        try:
            state = _run_python(test, trace=trace)
            total_cycles += state.get("cycle_count", 0)
            result = check_test(test, state)
            results.append(result)
            if result["status"] == PASS:
                passed += 1
            elif result["status"] == FAIL:
                failed += 1
        except Exception as e:
            results.append({
                "name": name, "status": ERROR, "category": category,
                "reason": str(e),
                "expected": str(test.get("expected")), "actual": None,
            })
            errors += 1

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": "python",
        "runtime_label": "unified_interpreter.py (Python)",
        "isa": "unified (isa_unified.py)",
        "suite": suite_name,
        "summary": {
            "total": len(vectors),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total_cycles": total_cycles,
        },
        "results": results,
    }


# ── C Runtime ───────────────────────────────────────────────────────────────

def _ensure_c_vm() -> Tuple[bool, str]:
    """Ensure the C VM binary exists and is up-to-date.

    Returns (available, error_message).
    """
    gcc = shutil.which("gcc")
    cc = shutil.which("cc")
    if not gcc and not cc:
        return False, "No C compiler found (need gcc or cc)"

    compiler = gcc or cc

    # Check if we need to rebuild
    need_build = False
    if not C_VM_BINARY.exists():
        need_build = True
    elif C_VM_SOURCE.exists():
        source_mtime = C_VM_SOURCE.stat().st_mtime
        binary_mtime = C_VM_BINARY.stat().st_mtime
        if source_mtime > binary_mtime:
            need_build = True

    if need_build:
        if not C_VM_SOURCE.exists():
            return False, f"C VM source not found: {C_VM_SOURCE}"
        try:
            result = subprocess.run(
                [compiler, "-O2", "-Wall", "-Wextra", "-o", str(C_VM_BINARY), str(C_VM_SOURCE)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return False, f"C compilation failed: {result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            return False, "C compilation timed out"
        except Exception as e:
            return False, f"C compilation error: {e}"

    if not os.access(C_VM_BINARY, os.X_OK):
        return False, f"C VM binary not executable: {C_VM_BINARY}"

    return True, ""


def _run_c_vm(bytecode_list: list) -> dict:
    """Run a single test on the C VM. Returns parsed VM state dict."""
    bytecode = bytes(bytecode_list)

    # Write bytecode to temp file (handles null bytes)
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(bytecode)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [str(C_VM_BINARY), tmp_path],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout

        # Parse C VM output format:
        # Line 1: halted=1 crashed=0 cycles=2 stack_depth=0
        # Line 2: R0=0 R1=0 R2=0 ... R15=0
        state: Dict[str, Any] = {
            "registers": {},
            "halted": True,
            "crashed": False,
            "pc": 0,
            "cycle_count": 0,
            "stack_depth": 0,
        }

        lines = output.strip().split("\n")
        if len(lines) >= 1:
            header = lines[0]
            m = re.search(r"halted=(\d)", header)
            if m:
                state["halted"] = bool(int(m.group(1)))
            m = re.search(r"crashed=(\d)", header)
            if m:
                state["crashed"] = bool(int(m.group(1)))
            m = re.search(r"cycles=(\d+)", header)
            if m:
                state["cycle_count"] = int(m.group(1))
            m = re.search(r"stack_depth=(\d+)", header)
            if m:
                state["stack_depth"] = int(m.group(1))

        if len(lines) >= 2:
            reg_line = lines[1]
            for m in re.finditer(r"R(\d+)=(-?\d+)", reg_line):
                reg_idx = int(m.group(1))
                reg_val = int(m.group(2))
                state["registers"][reg_idx] = reg_val

        return state

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_conformance_c(expanded: bool = False) -> dict:
    """Run all conformance tests on the C unified VM."""
    vectors, suite_name = _load_vectors(expanded)
    results: List[dict] = []
    passed = failed = skipped = errors = 0
    total_cycles = 0

    available, err = _ensure_c_vm()
    if not available:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "c",
            "runtime_label": f"flux_vm_unified (C) — UNAVAILABLE",
            "isa": "unified (isa_unified.py)",
            "suite": suite_name,
            "summary": {
                "total": len(vectors),
                "passed": 0,
                "failed": 0,
                "skipped": len(vectors),
                "errors": 0,
                "total_cycles": 0,
                "unavailable_reason": err,
            },
            "results": [],
        }

    for test in vectors:
        name = test["name"]
        category = test.get("category", "unknown")

        if test.get("bytecode") is None:
            results.append({
                "name": name, "status": SKIP, "category": category,
                "reason": "Source description test — needs compiler",
                "expected": None, "actual": None,
            })
            skipped += 1
            continue

        try:
            state = _run_c_vm(test["bytecode"])
            total_cycles += state.get("cycle_count", 0)
            result = check_test(test, state)
            results.append(result)
            if result["status"] == PASS:
                passed += 1
            elif result["status"] == FAIL:
                failed += 1
        except Exception as e:
            results.append({
                "name": name, "status": ERROR, "category": category,
                "reason": str(e),
                "expected": str(test.get("expected")), "actual": None,
            })
            errors += 1

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": "c",
        "runtime_label": "flux_vm_unified (C)",
        "isa": "unified (isa_unified.py)",
        "suite": suite_name,
        "summary": {
            "total": len(vectors),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total_cycles": total_cycles,
        },
        "results": results,
    }


# ── Rust Runtime ────────────────────────────────────────────────────────────

def run_conformance_rust(expanded: bool = False) -> dict:
    """Run all conformance tests on the Rust VM (not yet available)."""
    vectors, suite_name = _load_vectors(expanded)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": "rust",
        "runtime_label": "flux-vm (Rust) — NOT AVAILABLE",
        "isa": "unified (isa_unified.py)",
        "suite": suite_name,
        "summary": {
            "total": len(vectors),
            "passed": 0,
            "failed": 0,
            "skipped": len(vectors),
            "errors": 0,
            "total_cycles": 0,
            "unavailable_reason": "Rust runtime not implemented yet. See flux-rust or flux-coop-runtime repos.",
        },
        "results": [],
    }


# ── Runtime dispatch ────────────────────────────────────────────────────────

RUNTIME_RUNNERS = {
    "python": run_conformance_python,
    "c": run_conformance_c,
    "rust": run_conformance_rust,
}


def run_conformance(runtime: str = "python", trace: bool = False,
                    expanded: bool = False) -> dict:
    """Run conformance tests on the specified runtime.

    Args:
        runtime: One of 'python', 'c', 'rust'.
        trace: Print instruction trace for each test (Python only).
        expanded: Use the expanded 74-vector suite.
    """
    runner = RUNTIME_RUNNERS.get(runtime)
    if runner is None:
        raise ValueError(f"Unknown runtime: {runtime}. Valid: {VALID_RUNTIMES}")

    if runtime == "python":
        return runner(trace=trace, expanded=expanded)
    else:
        return runner(expanded=expanded)


# ── Cross-runtime comparison ───────────────────────────────────────────────

def build_cross_runtime_matrix(reports: Dict[str, dict]) -> dict:
    """Build a cross-runtime comparison matrix from multiple runtime reports.

    Args:
        reports: Dict mapping runtime name to report dict.

    Returns:
        Cross-runtime matrix dict.
    """
    matrix: Dict[str, Dict[str, str]] = {}
    runtimes = list(reports.keys())

    # Gather all test names from all reports
    all_names = set()
    for rt, report in reports.items():
        for r in report.get("results", []):
            all_names.add(r["name"])

    # Build per-test status map
    for name in sorted(all_names):
        matrix[name] = {}
        for rt, report in reports.items():
            for r in report.get("results", []):
                if r["name"] == name:
                    matrix[name][rt] = r["status"]
                    break
            else:
                # Test not in this runtime's results
                matrix[name][rt] = "N/A"

    # Compute agreement
    agreements = 0
    disagreements = 0
    for name, statuses in matrix.items():
        vals = [s for s in statuses.values() if s not in (SKIP, ERROR, "N/A")]
        if len(vals) <= 1:
            continue
        if all(v == vals[0] for v in vals):
            agreements += 1
        else:
            disagreements += 1

    return {
        "runtimes": runtimes,
        "matrix": matrix,
        "summary": {
            "total_tests": len(matrix),
            "agreements": agreements,
            "disagreements": disagreements,
        },
    }


# ── Output formatting ───────────────────────────────────────────────────────

def print_report(report: dict, json_only: bool = False) -> None:
    """Print the conformance report to stdout."""
    if json_only:
        print(json.dumps(report, indent=2))
        return

    summary = report["summary"]
    total = summary["total"]
    runtime_label = report.get("runtime_label", report["runtime"])

    print("=" * 72)
    print("  FLUX Unified ISA Conformance Test Report")
    print(f"  Runtime: {runtime_label}")
    print(f"  ISA:     {report['isa']}")
    print(f"  Date:    {report['timestamp']}")
    print("=" * 72)

    # Check for unavailable runtime
    if "unavailable_reason" in summary:
        print(f"\n  UNAVAILABLE: {summary['unavailable_reason']}")
        print(f"  ({summary['total']} tests skipped)")
        print("=" * 72)
        return

    # Summary bar
    bar_len = 40
    runnable = total - summary["skipped"]
    pass_len = int(bar_len * summary["passed"] / max(runnable, 1))
    fail_len = int(bar_len * summary["failed"] / max(runnable, 1))
    skip_len = bar_len - pass_len - fail_len

    bar = ""
    bar += "\u001b[32m" + "#" * pass_len  # green
    bar += "\u001b[31m" + "#" * fail_len  # red
    bar += "\u001b[33m" + "-" * skip_len  # yellow
    bar += "\u001b[0m"

    print(f"\n  {bar}")
    suite_label = f" [{report.get('suite', 'original')} suite]"
    print(f"  Result: {summary['passed']}/{runnable} passed "
          f"({summary['skipped']} skipped){suite_label}")
    if summary["errors"] > 0:
        print(f"  Errors: {summary['errors']}")
    print(f"  Cycles: {summary['total_cycles']:,}")
    print()

    # Per-test results
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
        print("  VERDICT: ALL TESTS PASSED")
    else:
        print(f"  VERDICT: {summary['failed']} FAILURE(S), {summary['errors']} ERROR(S)")
    print("=" * 72)


def print_cross_runtime_matrix(matrix: dict, json_only: bool = False) -> None:
    """Print the cross-runtime comparison matrix."""
    if json_only:
        print(json.dumps(matrix, indent=2))
        return

    runtimes = matrix["runtimes"]
    m = matrix["matrix"]
    summary = matrix["summary"]

    print()
    print("=" * 72)
    print("  Cross-Runtime Comparison Matrix")
    print("=" * 72)

    # Header
    rt_col_width = 42
    header = f"  {'Test Name':<{rt_col_width}}"
    for rt in runtimes:
        header += f" {rt:>10}"
    print(header)
    print(f"  {'-' * rt_col_width}" + ("-" * 12) * len(runtimes))

    # Rows
    for name, statuses in m.items():
        display_name = name[:rt_col_width - 2] + ".." if len(name) > rt_col_width else name
        row = f"  {display_name:<{rt_col_width}}"
        for rt in runtimes:
            s = statuses.get(rt, "N/A")
            if s == PASS:
                row += f" \u001b[32m{'PASS':>10}\u001b[0m"
            elif s == FAIL:
                row += f" \u001b[31m{'FAIL':>10}\u001b[0m"
            elif s == SKIP:
                row += f" \u001b[33m{'SKIP':>10}\u001b[0m"
            elif s == ERROR:
                row += f" \u001b[35m{'ERR':>10}\u001b[0m"
            else:
                row += f" {'N/A':>10}"
        print(row)

    print(f"  {'-' * rt_col_width}" + ("-" * 12) * len(runtimes))

    # Summary
    print(f"\n  Tests compared: {summary['total_tests']}")
    print(f"  Agreements:     {summary['agreements']}")
    print(f"  Disagreements:  {summary['disagreements']}")

    if summary["disagreements"] == 0 and summary["agreements"] > 0:
        print("\n  VERDICT: ALL RUNTIMES AGREE")
    elif summary["disagreements"] > 0:
        print(f"\n  VERDICT: {summary['disagreements']} RUNTIME DISAGREEMENT(S)")

    print("=" * 72)


def print_multi_runtime_summary(reports: Dict[str, dict], matrix: dict,
                                json_only: bool = False) -> None:
    """Print a summary table for all runtimes."""
    if json_only:
        return  # Already printed per-runtime JSON

    print()
    print("=" * 72)
    print("  Fleet-Wide Conformance Summary")
    print(f"  Date: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)
    print()

    # Per-runtime summary
    for rt_name, report in reports.items():
        s = report["summary"]
        label = report.get("runtime_label", rt_name)
        runnable = s["total"] - s["skipped"]
        if "unavailable_reason" in s:
            print(f"  {rt_name:>10}: UNAVAILABLE — {s['unavailable_reason']}")
        else:
            verdict = "\u001b[32mPASS\u001b[0m" if s["failed"] == 0 and s["errors"] == 0 else "\u001b[31mFAIL\u001b[0m"
            print(f"  {rt_name:>10}: {s['passed']}/{runnable} {verdict}  "
                  f"(skipped={s['skipped']}, cycles={s['total_cycles']:,})")

    # Cross-runtime agreement
    if matrix:
        ms = matrix["summary"]
        print(f"\n  Cross-runtime: {ms['agreements']} agreements, {ms['disagreements']} disagreements")

    print()
    print("=" * 72)


# ── JSON report writing ────────────────────────────────────────────────────

def write_json_report(report: dict, runtime: str, suite: str = "original") -> None:
    """Write a JSON report to the tools directory."""
    if runtime == "python" and suite == "original":
        filename = "conformance_report.json"
    else:
        filename = f"conformance_report_{runtime}_{suite}.json"
    report_path = PROJECT_ROOT / "tools" / filename
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  JSON report written to: {report_path}")
    return report_path


def write_cross_runtime_json(matrix: dict) -> Path:
    """Write cross-runtime matrix JSON."""
    report_path = PROJECT_ROOT / "tools" / "conformance_cross_runtime.json"
    with open(report_path, "w") as f:
        json.dump(matrix, f, indent=2)
    print(f"  Cross-runtime matrix written to: {report_path}")
    return report_path


# ── Entry point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FLUX Conformance Runner — cross-runtime ISA conformance test executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python tools/conformance_runner.py                     # Python, original suite
  python tools/conformance_runner.py --expanded           # Python, 74-vector suite
  python tools/conformance_runner.py --runtime c           # C runtime only
  python tools/conformance_runner.py --all                 # All available runtimes
  python tools/conformance_runner.py --all --expanded      # All runtimes, expanded suite
  python tools/conformance_runner.py --all --json-only     # JSON output for all runtimes
""",
    )
    parser.add_argument(
        "--runtime", choices=VALID_RUNTIMES, default="python",
        help="Runtime to test (default: python)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run against all available runtimes and show cross-runtime comparison",
    )
    parser.add_argument("--trace", action="store_true", help="Print instruction trace (Python only)")
    parser.add_argument("--json-only", action="store_true", help="Output only JSON")
    parser.add_argument("--expanded", action="store_true",
                        help="Run the expanded 74-vector suite instead of the original suite")

    args = parser.parse_args()

    if args.all:
        # Run all available runtimes
        runtimes_to_test = list(VALID_RUNTIMES)
    else:
        runtimes_to_test = [args.runtime]

    all_reports: Dict[str, dict] = {}
    has_failure = False

    for rt in runtimes_to_test:
        if not args.json_only and len(runtimes_to_test) > 1:
            print(f"\n{'#' * 72}")
            print(f"  Running conformance on: {rt}")
            print(f"{'#' * 72}")

        report = run_conformance(runtime=rt, trace=args.trace, expanded=args.expanded)
        all_reports[rt] = report

        print_report(report, json_only=args.json_only)
        write_json_report(report, rt, report.get("suite", "original"))

        s = report["summary"]
        if "unavailable_reason" not in s and (s["failed"] > 0 or s["errors"] > 0):
            has_failure = True

    # Cross-runtime comparison (only if multiple runtimes were tested)
    if len(all_reports) > 1:
        # Only include runtimes that actually produced results
        active_reports = {rt: r for rt, r in all_reports.items()
                          if r.get("results") and "unavailable_reason" not in r["summary"]}

        if len(active_reports) > 1:
            matrix = build_cross_runtime_matrix(active_reports)
            print_cross_runtime_matrix(matrix, json_only=args.json_only)
            write_cross_runtime_json(matrix)
        else:
            print(f"\n  Cross-runtime comparison: only 1 runtime produced results, skipping matrix.")

        print_multi_runtime_summary(all_reports,
                                   matrix if len(active_reports) > 1 else None,
                                   json_only=args.json_only)

    # Exit code
    if has_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
