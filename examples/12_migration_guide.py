#!/usr/bin/env python3
"""FLUX Full Migration Walkthrough.

An interactive script that:
1. Takes a directory of source files (or uses built-in examples)
2. Analyzes each file
3. Produces a MigrationPlan
4. Generates FLUX.MD equivalents
5. Shows the before/after comparison

Run:
    PYTHONPATH=src python3 examples/12_migration_guide.py [directory]

If no directory is given, uses built-in example code.
"""

from __future__ import annotations

import os
import sys
import tempfile

# ── ANSI helpers ────────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def header(text: str) -> None:
    width = 64
    print()
    print(f"{BOLD}{MAGENTA}{'═' * width}{RESET}")
    print(f"{BOLD}{MAGENTA}  {text}{RESET}")
    print(f"{BOLD}{MAGENTA}{'═' * width}{RESET}")


def sub_header(text: str) -> None:
    print()
    print(f"{BOLD}{CYAN}── {text} {'─' * (56 - len(text))}{RESET}")


def info(text: str) -> None:
    print(f"  {GREEN}✓{RESET} {text}")


def warn(text: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {text}")


def error(text: str) -> None:
    print(f"  {RED}✗{RESET} {text}")


def detail(text: str) -> None:
    print(f"    {DIM}{text}{RESET}")


def code_block(lang: str, text: str) -> None:
    print(f"    {YELLOW}```{lang}{RESET}")
    for line in text.strip().split("\n"):
        print(f"    {CYAN}{line}{RESET}")
    print(f"    {YELLOW}```{RESET}")


# ── Built-in example code ──────────────────────────────────────────────────

EXAMPLE_PYTHON_FILE = """# calculator.py - A simple calculator module
import math

class Calculator:
    def __init__(self, precision=2):
        self.precision = precision
        self.history = []

    def add(self, a, b):
        result = a + b
        self.history.append(result)
        print(f"Added: {a} + {b} = {result}")
        return result

    def divide(self, a, b):
        try:
            result = a / b
            self.history.append(result)
            return result
        except ZeroDivisionError:
            print("Cannot divide by zero!")
            return 0

    async def compute_all(self, values):
        results = [v * 2 for v in values]
        return results
"""

EXAMPLE_C_FILE = """#include <stdio.h>
#include <stdlib.h>

typedef struct {
    double x;
    double y;
} Vector2D;

Vector2D* vector_create(double x, double y) {
    Vector2D *v = (Vector2D*)malloc(sizeof(Vector2D));
    v->x = x;
    v->y = y;
    return v;
}

double vector_magnitude(Vector2D *v) {
    double mag = v->x * v->x + v->y * v->y;
    printf("Magnitude: %f\\n", mag);
    return mag;
}

void vector_destroy(Vector2D *v) {
    free(v);
}
"""


# ══════════════════════════════════════════════════════════════════════════
# Migration Guide Pipeline
# ══════════════════════════════════════════════════════════════════════════

def step_1_setup_source() -> str:
    """Step 1: Create temporary directory with example files."""
    header("Step 1: Setup Source Files")

    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
        if os.path.isdir(source_dir):
            info(f"Using directory: {source_dir}")
            return source_dir
        else:
            error(f"Directory not found: {source_dir}")
            sys.exit(1)

    # Create temp directory with built-in examples
    tmpdir = tempfile.mkdtemp(prefix="flux_migration_")
    py_path = os.path.join(tmpdir, "calculator.py")
    c_path = os.path.join(tmpdir, "vector.c")

    with open(py_path, "w") as f:
        f.write(EXAMPLE_PYTHON_FILE)
    with open(c_path, "w") as f:
        f.write(EXAMPLE_C_FILE)

    info(f"Created temporary directory: {tmpdir}")
    info(f"  - calculator.py ({len(EXAMPLE_PYTHON_FILE.splitlines())} lines)")
    info(f"  - vector.c ({len(EXAMPLE_C_FILE.splitlines())} lines)")
    return tmpdir


def step_2_analyze_files(source_dir: str):
    """Step 2: Analyze each file."""
    header("Step 2: Analyze Source Files")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()
    code_maps = engineer.analyze_directory(source_dir)

    for filename, code_map in sorted(code_maps.items()):
        sub_header(f"File: {filename}")
        info(f"Language: {code_map.source_lang}")
        info(f"Constructs found: {code_map.mapping_count}")
        info(f"Construct types: {', '.join(sorted(code_map.construct_types))}")
        info(f"Average confidence: {code_map.avg_confidence:.1%}")

        if code_map.get_low_confidence(0.7):
            warn(f"  Low-confidence mappings: {len(code_map.get_low_confidence(0.7))}")

        for mapping in code_map.mappings:
            detail(f"  {mapping.construct_type:20s} → {mapping.flux_ir.split(chr(10))[0][:50]}")

    return code_maps


def step_3_migration_plan(source_dir: str):
    """Step 3: Produce migration plan."""
    header("Step 3: Migration Plan")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()

    try:
        plan = engineer.full_migration_plan(source_dir)
    except Exception:
        # Fallback: per-file plans
        from flux.reverse import FluxReverseEngineer as FE
        engineer = FE()
        code_maps = engineer.analyze_directory(source_dir)
        all_steps = []
        step_num = 1
        combined_lang = "mixed"
        for filename, code_map in sorted(code_maps.items()):
            file_plan = engineer.migration_plan(code_map.source_code, code_map.source_lang)
            for s in file_plan.steps:
                all_steps.append(s.__class__(
                    step_number=step_num,
                    description=f"[{filename}] {s.description}",
                    original_code=s.original_code,
                    flux_code=s.flux_code,
                    difficulty=s.difficulty,
                    estimated_effort=s.estimated_effort,
                ))
                step_num += 1
            combined_lang = code_map.source_lang
        from flux.reverse.code_map import MigrationPlan
        plan = MigrationPlan(
            source_lang=combined_lang,
            total_steps=len(all_steps),
            steps=all_steps,
            overview=f"Combined plan for {len(code_maps)} files, {len(all_steps)} steps.",
        )

    info(f"Total migration steps: {plan.total_steps}")
    info(f"Easy steps: {len(plan.easy_steps)}")
    info(f"Medium steps: {len(plan.medium_steps)}")
    info(f"Hard steps: {len(plan.hard_steps)}")
    info(f"Estimated total effort: {plan.estimated_total_effort}")

    sub_header("Step-by-Step Plan")
    for step in plan.steps:
        marker = {"easy": f"{GREEN}●{RESET}", "medium": f"{YELLOW}●{RESET}", "hard": f"{MAGENTA}●{RESET}"}
        m = marker.get(step.difficulty, "●")
        detail(f"  {m} Step {step.step_number}: {step.description}")
        detail(f"      Effort: {step.estimated_effort}")

    return plan


def step_4_generate_flux_md(source_dir: str):
    """Step 4: Generate FLUX.MD equivalents."""
    header("Step 4: Generate FLUX.MD Equivalents")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()
    code_maps = engineer.analyze_directory(source_dir)

    for filename, code_map in sorted(code_maps.items()):
        sub_header(f"FLUX.MD for {filename}")

        try:
            flux_md = engineer.generate_flux_md(code_map.source_code, code_map.source_lang)
            lines = flux_md.strip().split("\n")
            # Show first 25 lines
            for line in lines[:25]:
                detail(f"  {line}")
            if len(lines) > 25:
                detail(f"  ... ({len(lines) - 25} more lines)")
            info(f"  Generated {len(lines)} lines of FLUX.MD")

            # Write to file
            flux_md_path = os.path.join(source_dir, filename.replace(
                os.path.splitext(filename)[1], ".flux.md"
            ))
            with open(flux_md_path, "w") as f:
                f.write(flux_md)
            info(f"  Written to: {flux_md_path}")

        except Exception as e:
            error(f"  Failed to generate FLUX.MD: {e}")


def step_5_before_after(source_dir: str):
    """Step 5: Show before/after comparison."""
    header("Step 5: Before/After Comparison")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()
    code_maps = engineer.analyze_directory(source_dir)

    for filename, code_map in sorted(code_maps.items()):
        sub_header(f"{filename}")

        # Show key before→after mappings
        for mapping in code_map.mappings[:5]:
            detail(f"\n  {BOLD}BEFORE{RESET} ({code_map.source_lang}):")
            for line in mapping.original.strip().split("\n")[:3]:
                detail(f"    {DIM}{line}{RESET}")

            detail(f"\n  {BOLD}AFTER{RESET} (FLUX FIR):")
            for line in mapping.flux_ir.strip().split("\n")[:5]:
                detail(f"    {CYAN}{line}{RESET}")

            detail(f"\n  {mapping.notes}")


def step_6_summary(source_dir: str):
    """Step 6: Summary and next steps."""
    header("Step 6: Summary & Next Steps")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()
    code_maps = engineer.analyze_directory(source_dir)

    total_constructs = sum(cm.mapping_count for cm in code_maps.values())
    avg_conf = (
        sum(cm.avg_confidence for cm in code_maps.values()) / len(code_maps)
        if code_maps else 0.0
    )

    print(f"\n  {BOLD}Migration Summary:{RESET}")
    info(f"Files analyzed: {len(code_maps)}")
    info(f"Total constructs mapped: {total_constructs}")
    info(f"Average confidence: {avg_conf:.1%}")

    print(f"\n  {BOLD}Next Steps:{RESET}")
    detail("  1. Review the generated FLUX.MD files for each source file")
    detail("  2. Manually adjust low-confidence mappings")
    detail("  3. Start with easy steps (imports, functions, print)")
    detail("  4. Tackle medium steps (loops, classes, structs)")
    detail("  5. Handle hard steps last (pointers, async)")
    detail("  6. Write tests for each migrated component")
    detail("  7. Use the FLUX pipeline to compile and verify")

    print(f"\n  {BOLD}Resources:{RESET}")
    detail("  - FIR documentation: src/flux/fir/")
    detail("  - Tile system: src/flux/tiles/")
    detail("  - A2A protocol: src/flux/a2a/")
    detail("  - Example scripts: examples/")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print(f"{BOLD}{YELLOW}{'╔' + '═' * 62 + '╗'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  FLUX Migration Guide — Full Walkthrough          {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  From Any Language to FLUX                        {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'╚' + '═' * 62 + '╝'}{RESET}")

    try:
        source_dir = step_1_setup_source()
        code_maps = step_2_analyze_files(source_dir)
        plan = step_3_migration_plan(source_dir)
        step_4_generate_flux_md(source_dir)
        step_5_before_after(source_dir)
        step_6_summary(source_dir)
    except Exception as e:
        error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()

    print()
    print(f"{BOLD}{GREEN}── Migration Guide Complete! ──{RESET}")
    print()
