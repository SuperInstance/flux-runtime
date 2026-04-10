#!/usr/bin/env python3
"""FLUX Reverse Engineering — Python Demo.

Shows how Python functions map to FLUX FIR equivalents.

Run:
    PYTHONPATH=src python3 examples/10_reverse_python.py
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
# Example 1: Fibonacci — Function + Recursion
# ══════════════════════════════════════════════════════════════════════════

PYTHON_FIBONACCI = '''def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)'''

EXPECTED_FIBONACCI_FIR = '''func fibonacci(n: i32) -> i32 {
  entry:
    ICMP n, 1, LE       →  if n <= 1
    BR <cond>, base, recurse
  base:
    MOV R0, n            →  return n
    RET
  recurse:
    TELL fibonacci, n-1  →  delegate to recursive call
    TELL fibonacci, n-2
    IADD R0, R1, R2      →  sum results
    RET
}'''


def demo_fibonacci() -> None:
    header("Example 1: Fibonacci — Function + Recursion")
    detail("How a Python recursive function maps to FLUX FIR.")

    sub_header("Python Source")
    code_block("python", PYTHON_FIBONACCI)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_FIBONACCI_FIR)

    detail("Key mappings:")
    detail("  def fibonacci(n)  →  FIR function with SSA parameter 'n'")
    detail("  if n <= 1         →  ICMP + BRANCH (two basic blocks)")
    detail("  return n          →  MOV + RET in base case block")
    detail("  fibonacci(n-1)    →  recursive CALL (or A2A TELL)")
    detail("  a + b             →  IADD instruction")


# ══════════════════════════════════════════════════════════════════════════
# Example 2: Loop + Variable
# ══════════════════════════════════════════════════════════════════════════

PYTHON_LOOP = '''def sum_to_n(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total'''

EXPECTED_LOOP_FIR = '''func sum_to_n(n: i32) -> i32 {
  entry:
    ALLOCA total         # stack slot for total
    STORE 0, total
    MOVI R0, 0           # loop counter i = 0
    JMP header
  header:
    ILT R0, n            # i < n+1 ?
    IADD R1, R0, 1       # n+1
    ILE R0, R1
    BR <cond>, body, exit
  body:
    LOAD R2, total       # total += i
    IADD R2, R2, R0
    STORE R2, total
    INC R0               # i++
    JMP header
  exit:
    LOAD R0, total       # return total
    RET
}'''


def demo_loop() -> None:
    header("Example 2: Loop + Variable")
    detail("How Python loops map to FIR basic blocks + jumps.")

    sub_header("Python Source")
    code_block("python", PYTHON_LOOP)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_LOOP_FIR)

    detail("Key mappings:")
    detail("  total = 0         →  ALLOCA + STORE (SSA variable)")
    detail("  for i in range() →  header/body/exit block structure")
    detail("  total += i        →  LOAD + IADD + STORE sequence")
    detail("  JMP header        →  loop back edge")


# ══════════════════════════════════════════════════════════════════════════
# Example 3: Class + Async + Try/Except
# ══════════════════════════════════════════════════════════════════════════

PYTHON_CLASS = '''
import asyncio

class DataProcessor:
    def __init__(self, name):
        self.name = name

    async def process(self, data):
        try:
            result = [x * 2 for x in data]
            print(f"Processing {len(result)} items")
            return result
        except Exception as e:
            print(f"Error: {e}")
            return []'''

EXPECTED_CLASS_FIR = '''# import asyncio → FIR module reference
DELEGATE asyncio

# class DataProcessor → FIR module
module DataProcessor {
  # self.name → struct field
  struct DataProcessor {
    name: str
  }

  func __init__(self: DataProcessor, name: str) -> void {
    entry:
      SETFIELD self, "name", name
      RET
  }

  # async def process → A2A TELL/ASK pattern
  func process(self: DataProcessor, data: [i32]) -> [i32] {
    entry:
      # try → BARRIER
      BARRIER try_block, error_handler
    try_block:
      # [x * 2 for x in data] → SIMD vector ops
      VLOAD data
      VSHL <lanes>  # x * 2 via left shift
      VSTORE result
      # print → IO_WRITE
      IO_WRITE "Processing N items"
      RET result
    error_handler:
      IO_WRITE "Error: ..."
      MOVI R0, 0
      RET []
  }
}'''


def demo_class() -> None:
    header("Example 3: Class + Async + Try/Except + Comprehension")
    detail("How a complex Python class maps to FLUX FIR.")

    sub_header("Python Source")
    code_block("python", PYTHON_CLASS)

    sub_header("FLUX FIR Equivalent")
    code_block("flux", EXPECTED_CLASS_FIR)

    detail("Key mappings:")
    detail("  class DataProcessor  →  FIR module")
    detail("  __init__             →  constructor function")
    detail("  async def process    →  A2A TELL/ASK pattern")
    detail("  [x * 2 for x in ...]→  SIMD VLOAD/VSHL/VSTORE")
    detail("  print()              →  IO_WRITE")
    detail("  try/except           →  A2A BARRIER")
    detail("  import asyncio       →  DELEGATE module ref")


# ══════════════════════════════════════════════════════════════════════════
# Example 4: Live Reverse Engineering Analysis
# ══════════════════════════════════════════════════════════════════════════

def demo_live_analysis() -> None:
    header("Example 4: Live Reverse Engineering Analysis")
    detail("Run the reverse engineer on the fibonacci example.")

    from flux.reverse import FluxReverseEngineer

    engineer = FluxReverseEngineer()
    code_map = engineer.analyze(PYTHON_FIBONACCI, lang="python")

    sub_header("Analysis Results")
    info(f"Source language: {code_map.source_lang}")
    info(f"Constructs found: {code_map.mapping_count}")
    info(f"Construct types: {', '.join(sorted(code_map.construct_types))}")
    info(f"Average confidence: {code_map.avg_confidence:.1%}")

    sub_header("Detailed Mappings")
    for i, mapping in enumerate(code_map.mappings, 1):
        detail(f"\n  [{i}] {mapping.construct_type} (confidence: {mapping.confidence:.0%})")
        detail(f"      Original: {mapping.original.strip()[:60]}")
        detail(f"      {mapping.notes[:80]}...")

    sub_header("Migration Plan")
    plan = engineer.migration_plan(PYTHON_FIBONACCI, lang="python")
    info(f"Total steps: {plan.total_steps}")
    info(f"Easy: {len(plan.easy_steps)}, Medium: {len(plan.medium_steps)}, Hard: {len(plan.hard_steps)}")
    info(f"Estimated effort: {plan.estimated_total_effort}")

    for step in plan.steps:
        marker = {"easy": f"{GREEN}●{RESET}", "medium": f"{YELLOW}●{RESET}", "hard": f"{MAGENTA}●{RESET}"}
        m = marker.get(step.difficulty, "●")
        detail(f"  {m} Step {step.step_number}: {step.description} ({step.estimated_effort})")

    sub_header("Generated FLUX.MD")
    flux_md = engineer.generate_flux_md(PYTHON_FIBONACCI, lang="python")
    for line in flux_md.strip().split("\n")[:20]:
        detail(f"  {line}")
    if len(flux_md.strip().split("\n")) > 20:
        detail("  ...")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print(f"{BOLD}{YELLOW}{'╔' + '═' * 62 + '╗'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  FLUX Reverse Engineering — Python Demo          {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'║'}  How Python Code Maps to FLUX FIR                {'║'}{RESET}")
    print(f"{BOLD}{YELLOW}{'╚' + '═' * 62 + '╝'}{RESET}")

    demo_fibonacci()
    demo_loop()
    demo_class()

    try:
        demo_live_analysis()
    except Exception as e:
        print(f"  {YELLOW}⚠{RESET} Live analysis error: {e}")

    print()
    print(f"{BOLD}{GREEN}── Done! ──{RESET}")
    print()
