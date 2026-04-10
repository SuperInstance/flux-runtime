#!/usr/bin/env python3
"""FLUX Reverse Engineering — C Demo.

Shows how C code constructs map to FLUX FIR equivalents.

Run:
    PYTHONPATH=src python3 examples/11_reverse_c.py
"""

from __future__ import annotations

# ── ANSI helpers ────────────────────────────────────────────────────────────

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
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


def detail(text: str) -> None:
    print(f"    {DIM}{text}{RESET}")


def code_block(lang: str, text: str) -> None:
    print(f"    {YELLOW}```{lang}{RESET}")
    for line in text.strip().split("\n"):
        print(f"    {CYAN}{line}{RESET}")
    print(f"    {YELLOW}```{RESET}")


# ══════════════════════════════════════════════════════════════════════════
# Example 1: C Struct
# ══════════════════════════════════════════════════════════════════════════

C_STRUCT = '''typedef struct {
    int x;
    int y;
    double weight;
} Point;'''

EXPECTED_STRUCT_FIR = '''# C struct → FIR StructType
struct Point {
  x: i32
  y: i32
  weight: f64
}

# Access: GETFIELD point, "x", 0, i32
# Modify: SETFIELD point, "x", new_value
'''


def demo_struct() -> None:
    header("Example 1: C Struct → FIR StructType")
    detail("How C structs map to FIR typed structures.")

    sub_header("C Source")
    code_block("c", C_STRUCT)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_STRUCT_FIR)

    detail("Key mappings:")
    detail("  typedef struct { ... } Point  →  FIR StructType")
    detail("  int x                        →  field: x, type i32")
    detail("  double weight                →  field: weight, type f64")
    detail("  point.x                      →  GETFIELD point, \"x\", 0, i32")
    detail("  point.x = val                →  SETFIELD point, \"x\", val")


# ══════════════════════════════════════════════════════════════════════════
# Example 2: C Function with Pointers
# ══════════════════════════════════════════════════════════════════════════

C_POINTERS = '''void swap(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}'''

EXPECTED_POINTERS_FIR = '''func swap(a: RefType<i32>, b: RefType<i32>) -> void {
  entry:
    # int *a → FIR RefType<i32> (memory region reference)
    ALLOCA temp        # local variable
    LOAD R0, a         # int temp = *a
    STORE R0, temp
    LOAD R1, b         # *a = *b
    STORE R1, a
    LOAD R2, temp      # *b = temp
    STORE R2, b
    RET
}'''


def demo_pointers() -> None:
    header("Example 2: C Pointers → FIR RefType + Memory Regions")
    detail("How C pointers map to FIR memory region references.")

    sub_header("C Source")
    code_block("c", C_POINTERS)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_POINTERS_FIR)

    detail("Key mappings:")
    detail("  int *a              →  FIR RefType<i32> (typed reference)")
    detail("  *a                  →  LOAD from memory region")
    detail("  *a = val            →  STORE to memory region")
    detail("  int temp = *a       →  ALLOCA + LOAD + STORE sequence")


# ══════════════════════════════════════════════════════════════════════════
# Example 3: malloc/free → Region Memory
# ══════════════════════════════════════════════════════════════════════════

C_MALLOC = '''#include <stdlib.h>
#include <stdio.h>

typedef struct {
    int *data;
    int size;
} Buffer;

Buffer* create_buffer(int size) {
    Buffer *buf = (Buffer*)malloc(sizeof(Buffer));
    buf->data = (int*)malloc(size * sizeof(int));
    buf->size = size;
    return buf;
}

void destroy_buffer(Buffer *buf) {
    free(buf->data);
    free(buf);
}'''

EXPECTED_MALLOC_FIR = '''# #include <stdlib.h> → FLUX stdlib module
# #include <stdio.h> → FLUX stdlib module

struct Buffer {
  data: RefType<i32>    # pointer → FIR RefType
  size: i32
}

func create_buffer(size: i32) -> RefType<Buffer> {
  entry:
    # malloc(sizeof(Buffer)) → REGION_CREATE
    REGION_CREATE sizeof(Buffer)  → buf
    # malloc(size * sizeof(int)) → REGION_CREATE
    ISMUL R0, size, 4            # size * sizeof(int)
    REGION_CREATE R0              → data_region
    SETFIELD buf, "data", data_region
    SETFIELD buf, "size", size
    RET buf
}

func destroy_buffer(buf: RefType<Buffer>) -> void {
  entry:
    # free(buf->data) → implicit REGION_DESTROY
    LOAD data_ptr, buf  # get data field
    REGION_DESTROY data_ptr
    # free(buf) → implicit REGION_DESTROY
    REGION_DESTROY buf
    RET
}

# Note: In FLUX, regions can be auto-destroyed on scope exit.
# Explicit REGION_DESTROY is only needed for early cleanup.
'''


def demo_malloc() -> None:
    header("Example 3: malloc/free → FLUX Region Memory")
    detail("How C manual memory management maps to FLUX regions.")

    sub_header("C Source")
    code_block("c", C_MALLOC)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_MALLOC_FIR)

    detail("Key mappings:")
    detail("  malloc(size)        →  REGION_CREATE size")
    detail("  free(ptr)           →  REGION_DESTROY ptr")
    detail("  ptr->field          →  GETFIELD + LOAD")
    detail("  ptr->field = val    →  SETFIELD + STORE")
    detail("  sizeof(T)           →  compile-time constant")
    detail("  #include <...>      →  FIR module reference")


# ══════════════════════════════════════════════════════════════════════════
# Example 4: Live Reverse Engineering Analysis
# ══════════════════════════════════════════════════════════════════════════

def demo_live_analysis() -> None:
    header("Example 4: Live Reverse Engineering Analysis")
    detail("Run the reverse engineer on C code.")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()

    # Analyze the struct example
    code_map = engineer.analyze(C_STRUCT, lang="c")

    sub_header("Struct Analysis Results")
    info(f"Source language: {code_map.source_lang}")
    info(f"Constructs found: {code_map.mapping_count}")
    info(f"Construct types: {', '.join(sorted(code_map.construct_types))}")
    info(f"Average confidence: {code_map.avg_confidence:.1%}")

    for i, mapping in enumerate(code_map.mappings, 1):
        detail(f"\n  [{i}] {mapping.construct_type} (confidence: {mapping.confidence:.0%})")
        detail(f"      Original: {mapping.original.strip()[:60]}")

    # Analyze the full malloc example
    code_map2 = engineer.analyze(C_MALLOC, lang="c")
    sub_header("Full C File Analysis")
    info(f"Total constructs: {code_map2.mapping_count}")
    info(f"Construct types: {', '.join(sorted(code_map2.construct_types))}")
    info(f"Average confidence: {code_map2.avg_confidence:.1%}")

    sub_header("Migration Plan")
    plan = engineer.migration_plan(C_MALLOC, lang="c")
    info(f"Total steps: {plan.total_steps}")
    info(f"Estimated effort: {plan.estimated_total_effort}")

    for step in plan.steps:
        marker = {"easy": f"{GREEN}●{RESET}", "medium": f"{YELLOW}●{RESET}", "hard": f"{MAGENTA}●{RESET}"}
        m = marker.get(step.difficulty, "●")
        detail(f"  {m} Step {step.step_number}: {step.description} ({step.estimated_effort})")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print(f"{BOLD}{YELLOW}{'╔' + '═' * 62 + '╗'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  FLUX Reverse Engineering — C Demo                {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  How C Code Maps to FLUX FIR                       {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'╚' + '═' * 62 + '╝'}{RESET}")

    demo_struct()
    demo_pointers()
    demo_malloc()

    try:
        demo_live_analysis()
    except Exception as e:
        print(f"  {YELLOW}⚠{RESET} Live analysis error: {e}")

    print()
    print(f"{BOLD}{GREEN}── Done! ──{RESET}")
    print()
