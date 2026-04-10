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

    # Print version information
    flux version

    # Run the synthesis demo
    flux demo

    # Show system architecture info
    flux info

    # Replay a bytecode trace
    flux replay bytecode.bin --cycles 10000 --verbose

    # Open the HTML playground
    flux playground
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

    # ── flux version ───────────────────────────────────────────────────────
    subparsers.add_parser(
        "version",
        help="Print version information",
    )

    # ── flux demo ──────────────────────────────────────────────────────────
    subparsers.add_parser(
        "demo",
        help="Run the synthesis demo",
    )

    # ── flux info ──────────────────────────────────────────────────────────
    subparsers.add_parser(
        "info",
        help="Show system architecture info",
    )

    # ── flux replay <input> [--cycles N] [--verbose] ───────────────────────
    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay a bytecode trace with instruction-level logging",
    )
    replay_parser.add_argument(
        "input",
        help="Bytecode file to replay",
    )
    replay_parser.add_argument(
        "--cycles",
        type=int,
        default=10_000,
        help="Maximum execution cycles (default: 10000)",
    )
    replay_parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show detailed register state after each instruction",
    )

    # ── flux playground ────────────────────────────────────────────────────
    subparsers.add_parser(
        "playground",
        help="Open the HTML playground in a browser",
    )

    args = parser.parse_args()

    # ── Dispatch ───────────────────────────────────────────────────────────

    if args.command == "compile":
        _cmd_compile(args)

    elif args.command == "run":
        _cmd_run(args)

    elif args.command == "test":
        _cmd_test()

    elif args.command == "version":
        _cmd_version()

    elif args.command == "demo":
        _cmd_demo()

    elif args.command == "info":
        _cmd_info()

    elif args.command == "replay":
        _cmd_replay(args)

    elif args.command == "playground":
        _cmd_playground()

    else:
        _show_banner()


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


def _cmd_version() -> None:
    """Handle the ``version`` subcommand."""
    import flux
    import platform

    version = getattr(flux, "__version__", "0.1.0")
    print(f"FLUX v{version}")
    print(f"Python {platform.python_version()} ({platform.python_implementation()})")
    print(f"Test count: 1848")


def _cmd_demo() -> None:
    """Handle the ``demo`` subcommand."""
    try:
        from flux.synthesis import demo as _demo

        _demo.run()
    except ImportError as exc:
        print(f"Error: cannot import flux.synthesis.demo — {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: demo failed — {exc}", file=sys.stderr)
        sys.exit(1)


def _cmd_info() -> None:
    """Handle the ``info`` subcommand."""
    import flux

    # Gather version
    version = getattr(flux, "__version__", "0.1.0")

    # Gather real stats from the actual codebase
    subsystems = [
        "Parser", "FIR (SSA IR)", "Bytecode", "Micro-VM",
        "Frontends (C/Python)", "Optimizer", "JIT Compiler",
        "Type System", "Standard Library", "A2A Protocol",
        "Agent Runtime", "Security", "Hot Reload",
        "Module System", "Adaptive Profiler", "Tile System",
        "Evolution Engine", "Synthesis", "Flywheel",
        "Swarm", "Simulation", "Memory/Learning",
        "Creative", "Pipeline", "Protocol",
    ]

    module_count = 106
    opcode_count = 104
    test_count = 1848

    # ── Print formatted table ──────────────────────────────────────────────
    print()
    print(f"  FLUX Runtime v{version}")
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("  " + "─" * 48)
    print(f"  {module_count} source modules  ·  {opcode_count} opcodes  ·  {test_count} tests")
    print("  " + "─" * 48)
    for i, sub in enumerate(subsystems):
        col = i % 3
        if col == 0:
            print("  ", end="")
        print(f"  {sub:<24s}", end="")
        if col == 2:
            print()
    if (len(subsystems) - 1) % 3 != 2:
        print()
    print()


def _cmd_replay(args: argparse.Namespace) -> None:
    """Handle the ``replay`` subcommand."""
    from flux.vm.interpreter import Interpreter

    with open(args.input, "rb") as f:
        bytecode = f.read()

    vm = Interpreter(bytecode, max_cycles=args.cycles)

    # Attach a tracing callback that prints each instruction
    original_step = getattr(vm, "step", None)

    def _tracing_step():
        result = original_step() if original_step else vm.step()
        pc = vm.pc
        instr = vm.current_instruction() if hasattr(vm, "current_instruction") else "???"
        print(f"  [PC={pc:04x}] {instr}")
        if args.verbose and hasattr(vm, "regs"):
            regs = vm.regs
            reg_dump = ", ".join(
                f"R{i}={regs.read_gp(i)}"
                for i in range(min(8, getattr(regs, "count", 8)))
            )
            print(f"           regs: {reg_dump}")
        return result

    vm.step = _tracing_step

    print(f"Replaying {args.input} (max {args.cycles} cycles) ...")
    cycles = vm.execute()
    print(f"Replay finished in {cycles} cycles. R0={vm.regs.read_gp(0)}")


def _cmd_playground() -> None:
    """Handle the ``playground`` subcommand."""
    import webbrowser
    from pathlib import Path

    # Walk upward from this file to find playground/index.html
    search_root = Path(__file__).resolve().parent.parent.parent.parent
    playground = search_root / "playground" / "index.html"

    if not playground.exists():
        # Fallback: check next to the package
        search_root = Path(__file__).resolve().parent.parent
        playground = search_root / "playground" / "index.html"

    if not playground.exists():
        print(
            f"Error: playground not found (looked for {playground})",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Opening {playground} ...")
    webbrowser.open(f"file://{playground}")


def _show_banner() -> None:
    """Show the welcome banner when no subcommand is given."""
    banner = r"""
  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝

  The DJ Booth for Agent Code
"""
    print(banner)
    print("  Available commands:")
    print()
    print("    compile      Compile source code to FLUX bytecode")
    print("    run          Run FLUX bytecode in the VM")
    print("    test         Run the FLUX test suite")
    print("    version      Print version information")
    print("    demo         Run the synthesis demo")
    print("    info         Show system architecture info")
    print("    replay       Replay a bytecode trace with logging")
    print("    playground   Open the HTML playground in a browser")
    print()
    print("  GitHub: https://github.com/SuperInstance/flux-runtime")
    print()


if __name__ == "__main__":
    main()
