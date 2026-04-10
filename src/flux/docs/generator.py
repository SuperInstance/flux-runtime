"""Documentation Generator — generates documentation by introspecting the FLUX codebase."""

from __future__ import annotations

import os
import re
from pathlib import Path

from .introspector import CodeIntrospector, ModuleInfo
from .renderer import MarkdownRenderer, AsciiRenderer
from .stats import CodeStatistics


class DocumentationGenerator:
    """Generates documentation by introspecting the FLUX codebase.

    Can generate:
    - API reference (from docstrings)
    - Architecture overview (from module structure)
    - Test coverage report (from test files)
    - Opcode reference (from opcodes.py)
    - Tile catalog (from tile library)
    - Evolution guide (from evolution modules)
    - Research summaries (from docs/research/)
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self._introspector = CodeIntrospector(repo_path)
        self._renderer = MarkdownRenderer()
        self._ascii = AsciiRenderer()
        self._stats = CodeStatistics(repo_path)

    # ── API reference ──────────────────────────────────────────────────

    def generate_api_reference(self) -> str:
        """Generate API reference for all public modules.

        Walks all ``src/flux/*/`` modules, extracts:
        - Module docstrings
        - Class docstrings with methods
        - Function signatures with type hints
        - Constants and enums
        """
        modules = self._introspector.list_modules()
        all_decls = []
        for mod in modules:
            api = self._introspector.get_public_api(mod.path)
            all_decls.extend(api)

        return self._renderer.render_api(all_decls)

    # ── Architecture overview ──────────────────────────────────────────

    def generate_architecture_overview(self) -> str:
        """Generate architecture documentation from module structure."""
        modules = self._introspector.list_modules()

        lines: list[str] = [
            "# FLUX Architecture Overview\n",
            "## ASCII Diagram\n",
            "```",
            self._ascii.render_architecture_diagram(),
            "```",
            "",
            "## Module Tree\n",
            "```",
            self._ascii.render_module_tree(modules),
            "```",
            "",
            "## Data Flow\n",
            "```",
            self._ascii.render_data_flow(),
            "```",
            "",
            "## Modules\n",
        ]

        for mod in modules:
            if mod.description:
                lines.append(f"### `{mod.name}`\n{mod.description}\n")

        lines.append("")
        return "\n".join(lines)

    # ── Test report ────────────────────────────────────────────────────

    def generate_test_report(self) -> str:
        """Generate test coverage report."""
        total_tests = self._stats.test_count()
        total_modules = self._stats.module_count()
        coverage = self._introspector.get_test_coverage()

        test_data = {
            "total_tests": total_tests,
            "total_modules": total_modules,
            "tested_modules": len(coverage),
            "coverage_score": len(coverage) / total_modules if total_modules else 0.0,
            "coverage": coverage,
        }

        return self._renderer.render_test_summary(test_data)

    # ── Opcode reference ───────────────────────────────────────────────

    def generate_opcode_reference(self) -> str:
        """Generate opcode reference from opcodes.py."""
        opcodes = self._extract_opcodes()
        return self._renderer.render_opcode_table(opcodes)

    def _extract_opcodes(self) -> list[dict]:
        """Extract opcode information from bytecode/opcodes.py."""
        opcodes_path = (
            Path(self.repo_path) / "src" / "flux" / "bytecode" / "opcodes.py"
        )
        if not opcodes_path.is_file():
            return []

        try:
            source = opcodes_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        opcodes: list[dict] = []
        # Parse: NAME = 0xHH  inside the Op IntEnum class
        # Track the current comment block for category
        current_category = "Other"
        current_comment = ""

        for line in source.splitlines():
            stripped = line.strip()

            # Track category comments (lines starting with #)
            if stripped.startswith("#") and not stripped.startswith("# Op"):
                current_comment = stripped.lstrip("# ").strip()
            elif stripped.startswith("# ─"):
                # Section separator
                if current_comment:
                    current_category = current_comment
                    current_comment = ""

            # Match enum members: NAME = 0xHH
            match = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+)", stripped)
            if match:
                name = match.group(1)
                hex_val = match.group(2)

                # Skip classification helpers
                if name in ("FORMAT_A", "FORMAT_B", "FORMAT_C",
                            "FORMAT_D", "FORMAT_E", "FORMAT_G",
                            "get_format", "instruction_size", "opcode_size"):
                    continue

                # Determine format and size
                fmt = "C"  # default
                if name in ("NOP", "HALT", "YIELD", "DUP", "SWAP",
                            "DEBUG_BREAK", "EMERGENCY_STOP"):
                    fmt = "A"
                    size = 1
                elif name in ("INC", "DEC", "ENTER", "LEAVE", "PUSH",
                              "POP", "INEG", "FNEG", "INOT"):
                    fmt = "B"
                    size = 2
                elif name in ("JMP", "JZ", "JNZ", "JE", "JNE", "JG",
                              "JL", "JGE", "JLE", "MOVI", "CALL"):
                    fmt = "D"
                    size = 4
                elif name == "VFMA":
                    fmt = "E"
                    size = 4
                elif name in (
                    "REGION_CREATE", "REGION_DESTROY", "REGION_TRANSFER",
                    "MEMCOPY", "MEMSET", "MEMCMP",
                    "TELL", "ASK", "DELEGATE", "DELEGATE_RESULT",
                    "REPORT_STATUS", "REQUEST_OVERRIDE", "BROADCAST", "REDUCE",
                    "DECLARE_INTENT", "ASSERT_GOAL", "VERIFY_OUTCOME",
                    "EXPLAIN_FAILURE", "SET_PRIORITY",
                    "TRUST_CHECK", "TRUST_UPDATE", "TRUST_QUERY", "REVOKE_TRUST",
                    "CAP_REQUIRE", "CAP_REQUEST", "CAP_GRANT", "CAP_REVOKE",
                    "BARRIER", "SYNC_CLOCK", "FORMATION_UPDATE",
                    "RESOURCE_ACQUIRE", "RESOURCE_RELEASE",
                ):
                    fmt = "G"
                    size = -1
                elif fmt == "C":
                    size = 3
                else:
                    size = 3

                opcodes.append({
                    "name": name,
                    "hex": hex_val,
                    "format": fmt,
                    "size": size if size != -1 else "var",
                    "category": current_category,
                    "description": "",
                })

        return opcodes

    # ── Tile catalog ───────────────────────────────────────────────────

    def generate_tile_catalog(self) -> str:
        """Generate tile catalog from tile library."""
        tiles = self._extract_tiles()
        if not tiles:
            return "# Tile Catalog\n\nNo tiles found.\n"

        lines: list[str] = ["# Tile Catalog\n"]

        # Group by type
        by_type: dict[str, list[dict]] = {}
        for tile in tiles:
            by_type.setdefault(tile.get("type", "Other"), []).append(tile)

        for tile_type in sorted(by_type.keys()):
            lines.append(f"\n## {tile_type}\n")
            for tile in by_type[tile_type]:
                lines.append(self._renderer.render_tile_card(tile))

        return "\n".join(lines) + "\n"

    def _extract_tiles(self) -> list[dict]:
        """Extract tile information from the tile library module."""
        library_path = (
            Path(self.repo_path) / "src" / "flux" / "tiles" / "library.py"
        )
        if not library_path.is_file():
            return []

        try:
            source = library_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        tiles: list[dict] = []

        # Find tile definitions: <name>_tile = Tile(...)
        # Parse via regex to avoid importing heavy dependencies
        tile_pattern = re.compile(
            r"(\w+)_tile\s*=\s*Tile\(",
            re.MULTILINE,
        )
        tile_names = tile_pattern.findall(source)

        for name in tile_names:
            # Extract Tile(...) block for this tile
            block_pattern = re.compile(
                rf"{re.escape(name)}_tile\s*=\s*Tile\((.*?)\n\)",
                re.DOTALL,
            )
            block_match = block_pattern.search(source)
            block = block_match.group(1) if block_match else ""

            # Extract fields
            tile_type = "UNKNOWN"
            type_match = re.search(r"TileType\.(\w+)", block)
            if type_match:
                tile_type = type_match.group(1)

            cost = 0.0
            cost_match = re.search(r"cost_estimate=(\d+\.?\d*)", block)
            if cost_match:
                cost = float(cost_match.group(1))

            abstraction = 0
            abs_match = re.search(r"abstraction_level=(\d+)", block)
            if abs_match:
                abstraction = int(abs_match.group(1))

            inputs: list[str] = []
            for inp in re.finditer(r'TilePort\("(\w+)"', block):
                inputs.append(inp.group(1))

            outputs: list[str] = []
            # Outputs come after inputs in the Tile constructor
            in_outputs = False
            for line in block.splitlines():
                if "outputs" in line:
                    in_outputs = True
                if in_outputs:
                    out_match = re.search(r'TilePort\("(\w+)"', line)
                    if out_match:
                        outputs.append(out_match.group(1))

            tags: list[str] = []
            tags_match = re.search(r"tags=\{([^}]+)\}", block)
            if tags_match:
                tags = re.findall(r'"(\w+)"', tags_match.group(1))

            tiles.append({
                "name": name,
                "type": tile_type,
                "cost": cost,
                "abstraction": abstraction,
                "inputs": inputs,
                "outputs": outputs,
                "tags": tags,
                "description": f"Built-in {tile_type.lower()} tile.",
            })

        return tiles

    # ── Generate all ───────────────────────────────────────────────────

    def generate_all(self) -> dict[str, str]:
        """Generate all documentation. Returns ``{filename: content}``."""
        return {
            "api_reference.md": self.generate_api_reference(),
            "architecture_overview.md": self.generate_architecture_overview(),
            "test_report.md": self.generate_test_report(),
            "opcode_reference.md": self.generate_opcode_reference(),
            "tile_catalog.md": self.generate_tile_catalog(),
        }

    # ── Write all ──────────────────────────────────────────────────────

    def write_all(self, output_dir: str = "docs/generated") -> int:
        """Write all generated docs to files. Returns number of files written."""
        docs = self.generate_all()
        out_path = Path(self.repo_path) / output_dir
        out_path.mkdir(parents=True, exist_ok=True)

        count = 0
        for filename, content in docs.items():
            file_path = out_path / filename
            file_path.write_text(content, encoding="utf-8")
            count += 1

        return count
