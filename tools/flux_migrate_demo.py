#!/usr/bin/env python3
"""FLUX Migrate Demo — Demonstrates migrating a sample Python project to FLUX.MD.

Creates a temporary directory with sample Python files, runs the FluxMigrator
on them, and shows the generated FLUX.MD files and migration report.

Usage:
    python tools/flux_migrate_demo.py
    PYTHONPATH=src python tools/flux_migrate_demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Sample Python Files ─────────────────────────────────────────────────────


CALCULATOR_PY = '''"""A simple calculator module."""

import math
from typing import List, Optional


def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Division by zero")
    return a / b


def factorial(n: int) -> int:
    """Compute factorial of n iteratively."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


class Calculator:
    """A simple calculator that maintains state."""

    def __init__(self):
        self.history: List[str] = []
        self.last_result: float = 0.0

    def compute(self, operation: str, a: float, b: float) -> float:
        """Perform a computation and log it."""
        ops = {
            "+": add,
            "-": subtract,
            "*": multiply,
            "/": divide,
        }
        if operation not in ops:
            raise ValueError(f"Unknown operation: {operation}")

        result = ops[operation](a, b)
        self.last_result = result
        self.history.append(f"{a} {operation} {b} = {result}")
        return result

    def get_history(self) -> List[str]:
        """Return the computation history."""
        return self.history.copy()

    def clear_history(self):
        """Clear computation history."""
        self.history.clear()
'''


UTILS_PY = '''"""Utility functions for data processing."""

import json
from typing import Any, Dict, List


def flatten(nested: List) -> List:
    """Flatten a nested list."""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def unique(items: List) -> List:
    """Return unique items preserving order."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def chunk_list(items: List, size: int) -> List[List]:
    """Split a list into chunks of the given size."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def merge_dicts(*dicts: Dict) -> Dict:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def count_by(items: List, key_fn=None) -> Dict:
    """Count occurrences of items or keyed values."""
    counts = {}
    for item in items:
        key = key_fn(item) if key_fn else item
        counts[key] = counts.get(key, 0) + 1
    return counts
'''


MATH_HELPER_C = '''/* math_helper.c — Simple C math utilities */

#include <stdio.h>
#include <math.h>

int clamp_int(int value, int min_val, int max_val) {
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

double lerp(double a, double b, double t) {
    return a + (b - a) * t;
}

int abs_int(int x) {
    return x < 0 ? -x : x;
}

int max_of_three(int a, int b, int c) {
    int max = a;
    if (b > max) max = b;
    if (c > max) max = c;
    return max;
}

typedef struct {
    int x;
    int y;
} Point;

Point point_add(Point a, Point b) {
    Point result;
    result.x = a.x + b.x;
    result.y = a.y + b.y;
    return result;
}
'''


# ── Main Demo ─────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the migration demo."""
    from flux.migrate import FluxMigrator

    # Header
    print()
    print("  ╔═══════════════════════════════════════════════════════════╗")
    print("  ║              FLUX MIGRATE DEMO v1.0                      ║")
    print("  ║    Demonstrating Python → FLUX.MD migration              ║")
    print("  ╚═══════════════════════════════════════════════════════════╝")
    print()

    # Create temp directory with sample files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write sample files
        (tmp / "calculator.py").write_text(CALCULATOR_PY, encoding="utf-8")
        (tmp / "utils.py").write_text(UTILS_PY, encoding="utf-8")
        (tmp / "math_helper.c").write_text(MATH_HELPER_C, encoding="utf-8")

        print(f"  Created sample project in: {tmp}")
        print(f"    - calculator.py  (6 functions, 1 class)")
        print(f"    - utils.py        (5 functions)")
        print(f"    - math_helper.c   (3 functions, 1 struct)")
        print()

        # Run migrator
        output_dir = tmp / "flux_output"
        migrator = FluxMigrator(output_dir=str(output_dir), verbose=True)

        print("  ── Running migration ──────────────────────────────────────")
        print()

        report = migrator.migrate_directory(tmp)

        # Print report
        print(report.to_text())

        # Show generated FLUX.MD content
        print("  ── Generated FLUX.MD Files ────────────────────────────────")
        print()

        for mf in report.files:
            if mf.success and mf.output_path.exists():
                content = mf.output_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                print(f"  ┌─── {mf.output_path.name} ({len(lines)} lines) ────")
                # Show first 20 lines
                for line in lines[:20]:
                    print(f"  │ {line}")
                if len(lines) > 20:
                    print(f"  │ ... ({len(lines) - 20} more lines)")
                print(f"  └{'─' * 50}")
                print()

    print("  Demo complete! The generated FLUX.MD files are ready for")
    print("  the FLUX pipeline: Parser → FIR → Bytecode → VM execution.")
    print()


if __name__ == "__main__":
    main()
