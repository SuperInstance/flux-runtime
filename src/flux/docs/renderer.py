"""Documentation Renderers — Markdown and ASCII art output."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .introspector import ModuleInfo, APIDeclaration


class MarkdownRenderer:
    """Renders documentation to markdown format."""

    # ── Module ─────────────────────────────────────────────────────────

    def render_module(self, info: ModuleInfo) -> str:
        """Render a module's documentation."""
        lines: list[str] = []
        lines.append(f"## Module: `{info.name}`\n")
        if info.description:
            lines.append(f"{info.description}\n")
        lines.append(f"**Path:** `{info.path}`  ")
        lines.append(f"**LOC:** {info.loc}  ")
        lines.append(f"**Classes:** {len(info.classes)}  ")
        lines.append(f"**Functions:** {len(info.functions)}  ")
        lines.append(f"**Constants:** {len(info.constants)}\n")

        if info.classes:
            lines.append("### Classes\n")
            for cls in info.classes:
                lines.append(f"- `{cls}`")
            lines.append("")

        if info.functions:
            lines.append("### Functions\n")
            for fn in info.functions:
                lines.append(f"- `{fn}()`")
            lines.append("")

        if info.constants:
            lines.append("### Constants\n")
            for const in info.constants:
                lines.append(f"- `{const}`")
            lines.append("")

        if info.imports:
            lines.append("### Dependencies\n")
            for imp in info.imports:
                lines.append(f"- `{imp}`")
            lines.append("")

        return "\n".join(lines)

    # ── API reference ──────────────────────────────────────────────────

    def render_api(self, declarations: list[APIDeclaration]) -> str:
        """Render API reference for a list of declarations."""
        if not declarations:
            return "# API Reference\n\nNo public declarations found.\n"

        lines: list[str] = ["# API Reference\n"]

        # Group by kind
        by_kind: dict[str, list[APIDeclaration]] = {}
        for decl in declarations:
            by_kind.setdefault(decl.kind, []).append(decl)

        for kind in ["class", "function", "constant", "enum"]:
            items = by_kind.get(kind, [])
            if not items:
                continue
            if kind == "class":
                title = "Classes"
            elif kind == "function":
                title = "Functions"
            elif kind == "constant":
                title = "Constants"
            else:
                title = kind.capitalize() + "s"
            lines.append(f"## {title}\n")
            for decl in items:
                lines.append(f"### `{decl.name}`\n")
                if decl.signature:
                    lines.append(f"```python\n{decl.signature}\n```\n")
                if decl.docstring:
                    lines.append(f"{decl.docstring}\n")
                lines.append(f"*Module: `{decl.module}`*\n")

        return "\n".join(lines)

    # ── Opcode table ───────────────────────────────────────────────────

    def render_opcode_table(self, opcodes: list[dict]) -> str:
        """Render opcode reference as a markdown table."""
        lines: list[str] = [
            "# Opcode Reference\n",
            "| Opcode | Hex | Format | Size | Category | Description |",
            "|--------|-----|--------|------|----------|-------------|",
        ]
        for op in opcodes:
            name = op.get("name", "?")
            hex_val = op.get("hex", "0x??")
            fmt = op.get("format", "?")
            size = op.get("size", "?")
            category = op.get("category", "?")
            desc = op.get("description", "")
            lines.append(f"| `{name}` | `{hex_val}` | {fmt} | {size} | {category} | {desc} |")

        return "\n".join(lines) + "\n"

    # ── Tile card ──────────────────────────────────────────────────────

    def render_tile_card(self, tile: dict) -> str:
        """Render a tile as a documentation card."""
        name = tile.get("name", "unknown")
        tile_type = tile.get("type", "?")
        cost = tile.get("cost", 0)
        abstraction = tile.get("abstraction", 0)
        inputs = tile.get("inputs", [])
        outputs = tile.get("outputs", [])
        tags = tile.get("tags", [])
        description = tile.get("description", "")

        lines: list[str] = [
            f"### Tile: `{name}`\n",
            f"- **Type:** {tile_type}",
            f"- **Cost:** {cost}",
            f"- **Abstraction Level:** {abstraction}",
        ]

        if inputs:
            lines.append(f"- **Inputs:** {', '.join(f'`{i}`' for i in inputs)}")
        if outputs:
            lines.append(f"- **Outputs:** {', '.join(f'`{o}`' for o in outputs)}")
        if tags:
            lines.append(f"- **Tags:** {', '.join(f'`{t}`' for t in tags)}")
        if description:
            lines.append(f"\n{description}")

        return "\n".join(lines) + "\n"

    # ── Test summary ───────────────────────────────────────────────────

    def render_test_summary(self, test_data: dict) -> str:
        """Render test coverage summary."""
        lines: list[str] = [
            "# Test Coverage Summary\n",
            f"**Total tests:** {test_data.get('total_tests', 0)}",
            f"**Total modules:** {test_data.get('total_modules', 0)}",
            f"**Modules with tests:** {test_data.get('tested_modules', 0)}",
            f"**Coverage score:** {test_data.get('coverage_score', 0):.1%}",
            "",
        ]

        coverage = test_data.get("coverage", {})
        if coverage:
            lines.append("## Module Coverage\n")
            lines.append("| Module | Coverage |")
            lines.append("|--------|----------|")
            for mod, score in sorted(coverage.items()):
                bar_len = int(score * 20)
                bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
                lines.append(f"| `{mod}` | {bar} {score:.0%} |")

        return "\n".join(lines) + "\n"

    # ── Table of contents ──────────────────────────────────────────────

    def render_toc(self, sections: list[dict]) -> str:
        """Render table of contents from a list of {title, anchor} dicts."""
        lines: list[str] = ["# Table of Contents\n"]
        for section in sections:
            title = section.get("title", "")
            anchor = section.get("anchor", title.lower().replace(" ", "-"))
            level = section.get("level", 2)
            indent = "  " * (level - 2)
            lines.append(f"{indent}- [{title}](#{anchor})")
        return "\n".join(lines) + "\n"


class AsciiRenderer:
    """Renders documentation as ASCII art for terminal display."""

    # ── Architecture diagram ───────────────────────────────────────────

    def render_architecture_diagram(self) -> str:
        """ASCII art architecture diagram of the FLUX system."""
        return """\
┌─────────────────────────────────────────────────────────────────┐
│                     FLUX ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐ │
│  │  FLUX.MD    │───▶│   Parser     │───▶│    FIR Builder    │ │
│  │  (Source)   │    │  (L0 Layer)  │    │   (Intermediate)  │ │
│  └─────────────┘    └──────────────┘    └────────┬──────────┘ │
│                                                    │            │
│  ┌─────────────┐    ┌──────────────┐              │            │
│  │  C / Python │───▶│  Frontends   │──────────────┤            │
│  │  (Native)   │    │  (Polyglot)  │              ▼            │
│  └─────────────┘    └──────────────┘    ┌──────────────────┐  │
│                                         │    Optimizer     │  │
│  ┌─────────────┐                        │   (Passes)      │  │
│  │   Tiles     │───▶ Tile Graph ──────▶│                  │  │
│  │ (Composable)│      Compilation      └────────┬─────────┘  │
│  └─────────────┘                                  │            │
│                                                    ▼            │
│                                         ┌──────────────────┐  │
│                                         │  Bytecode Encoder│  │
│                                         │  (Binary Format) │  │
│                                         └────────┬─────────┘  │
│                                                  │            │
│  ┌─────────────┐    ┌──────────────┐             │            │
│  │   A2A       │◀──│   Protocol   │             ▼            │
│  │ (Agent Comms)│   │  (Messages)  │    ┌──────────────────┐  │
│  └─────────────┘    └──────────────┘    │   Micro-VM       │  │
│                                         │  (Interpreter)   │  │
│  ┌─────────────┐                        └──────────────────┘  │
│  │  Evolution  │        ┌──────────────┐                     │
│  │  Engine     │◀──────▶│  Flywheel    │                     │
│  │ (Self-Opt)  │        │  (Improvement│                     │
│  └─────────────┘        │   Loop)      │                     │
│                          └──────────────┘                     │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Supporting: Adaptive | Modules | JIT | Stdlib | Swarm │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
"""

    # ── Module tree ────────────────────────────────────────────────────

    def render_module_tree(self, modules: list[ModuleInfo]) -> str:
        """ASCII art module dependency tree."""
        # Build a simple tree from module names grouped by directory
        dirs: dict[str, list[str]] = {}
        for mod in modules:
            p = Path(mod.path)
            # Walk up to find 'src/flux/<pkg>'
            parts = p.parts
            try:
                flux_idx = parts.index('flux')
                if flux_idx + 1 < len(parts):
                    pkg = parts[flux_idx + 1]
                    if pkg != '__pycache__':
                        dirs.setdefault(pkg, []).append(mod.name)
            except ValueError:
                pass

        lines: list[str] = ["flux/", "├── __init__.py"]
        sorted_dirs = sorted(dirs.keys())
        for i, pkg in enumerate(sorted_dirs):
            is_last = i == len(sorted_dirs) - 1
            connector = "└── " if is_last else "├── "
            files = sorted(set(dirs[pkg]))
            lines.append(f"{connector}{pkg}/")
            for j, fname in enumerate(files):
                is_last_file = j == len(files) - 1
                prefix = "    " if is_last else "│   "
                file_connector = "└── " if is_last_file else "├── "
                lines.append(f"{prefix}{file_connector}{fname}.py")

        return "\n".join(lines)

    # ── Data flow ─────────────────────────────────────────────────────

    def render_data_flow(self) -> str:
        """ASCII art data flow diagram."""
        return """\
  Source Code          Compilation Pipeline           Execution
  ───────────          ─────────────────────           ─────────

  FLUX.MD ─────┐
               │
  C Source ────┼──▶ Parser ──▶ FIR ──▶ Optimizer ──▶ Bytecode ──▶ VM
               │              │                        │
  Python ──────┘              │                        ▼
                              │                    Agent Runtime
                              ▼                        │
                        Type Unifier ──────────────────┘
                              │
                              ▼
                        Tile Graph ──▶ FIR Module
"""
