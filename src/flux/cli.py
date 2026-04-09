"""FLUX CLI — compile and run FLUX.MD files.

Usage::

    # Compile a C source file to bytecode
    flux compile input.c -o output.bin

    # Compile a FLUX.MD document
    flux compile input.md -o output.bin

    # Run bytecode in the VM
    flux run bytecode.bin --cycles 1000000

    # Run the test suite
    flux test
"""

from __future__ import annotations

import sys
import argparse


def main() -> None:
    """Entry point for the ``flux`` command-line tool."""
    parser = argparse.ArgumentParser(
        prog="flux",
        description="FLUX Agent-First Bytecode System",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── flux compile <input> [-o output] [-l lang] ─────────────────────────
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile source code to FLUX bytecode",
    )
    compile_parser.add_argument(
        "input",
        help="Input source file (.c, .py, or .md)",
    )
    compile_parser.add_argument(
        "-o", "--output",
        help="Output bytecode file (default: input with .bin extension)",
    )
    compile_parser.add_argument(
        "-l", "--lang",
        default=None,
        help="Source language: c, python, md (default: inferred from extension)",
    )

    # ── flux run <input> [--cycles N] ──────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run",
        help="Run FLUX bytecode in the VM",
    )
    run_parser.add_argument(
        "input",
        help="Bytecode file to execute",
    )
    run_parser.add_argument(
        "--cycles",
        type=int,
        default=1_000_000,
        help="Maximum execution cycles (default: 1000000)",
    )

    # ── flux test ──────────────────────────────────────────────────────────
    subparsers.add_parser(
        "test",
        help="Run the FLUX test suite",
    )

    args = parser.parse_args()

    # ── Dispatch ───────────────────────────────────────────────────────────

    if args.command == "compile":
        _cmd_compile(args)

    elif args.command == "run":
        _cmd_run(args)

    elif args.command == "test":
        _cmd_test()

    else:
        parser.print_help()
        sys.exit(0)


# ── Subcommands ──────────────────────────────────────────────────────────────


def _infer_lang(filename: str, explicit: str | None) -> str:
    """Infer the language from the file extension, or use explicit override."""
    if explicit:
        return explicit.lower()
    if filename.endswith(".md"):
        return "md"
    if filename.endswith(".c"):
        return "c"
    if filename.endswith(".py"):
        return "python"
    # Default to C
    return "c"


def _default_output(input_path: str) -> str:
    """Generate a default output filename by replacing the extension with .bin."""
    for ext in (".md", ".c", ".py", ".flux"):
        if input_path.endswith(ext):
            return input_path[: -len(ext)] + ".bin"
    return input_path + ".bin"


def _cmd_compile(args: argparse.Namespace) -> None:
    """Handle the ``compile`` subcommand."""
    from flux.compiler.pipeline import FluxCompiler

    with open(args.input, "r") as f:
        source = f.read()

    lang = _infer_lang(args.input, args.lang)

    compiler = FluxCompiler()
    if lang == "md":
        bytecode = compiler.compile_md(source)
    elif lang == "c":
        bytecode = compiler.compile_c(source)
    elif lang == "python":
        bytecode = compiler.compile_python(source)
    else:
        print(f"Error: unknown language: {lang!r}", file=sys.stderr)
        sys.exit(1)

    output = args.output or _default_output(args.input)
    with open(output, "wb") as f:
        f.write(bytecode)

    print(f"Compiled {len(bytecode)} bytes -> {output}")


def _cmd_run(args: argparse.Namespace) -> None:
    """Handle the ``run`` subcommand."""
    from flux.vm.interpreter import Interpreter

    with open(args.input, "rb") as f:
        bytecode = f.read()

    vm = Interpreter(bytecode, max_cycles=args.cycles)
    cycles = vm.execute()
    print(f"Executed in {cycles} cycles. R0={vm.regs.read_gp(0)}")


def _cmd_test() -> None:
    """Handle the ``test`` subcommand."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
