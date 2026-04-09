"""FLUX.MD Parser — stdlib-only (re + dataclasses).

Converts a FLUX Markdown source string into a ``FluxModule`` AST.
"""

from __future__ import annotations

import re
from typing import Any

from .nodes import (
    CodeBlock,
    DataBlock,
    FluxCodeBlock,
    FluxModule,
    FluxTypeError,
    Heading,
    ListItem,
    ListBlock,
    LocatedNode,
    NativeBlock,
    Paragraph,
    SourceSpan,
    AgentDirective,
)

# ---------------------------------------------------------------------------
# Regex patterns (compiled once)
# ---------------------------------------------------------------------------

_RE_FRONTMATTER = re.compile(
    r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL
)

_RE_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})([\w-]*)\s*(.*?)$")

_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")

_RE_ULIST = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_RE_OLIST = re.compile(r"^(\s*)\d+\.\s+(.+)$")

_RE_AGENT_DIRECTIVE = re.compile(
    r"^##\s+(?:agent|fn)\s*[:\s]\s*(.+)$", re.IGNORECASE
)
_RE_AGENT_KIND = re.compile(r"^##\s+(agent|fn)\s*[:\s]", re.IGNORECASE)

# Languages that map to DataBlock
_DATA_LANGS = frozenset({"json", "yaml", "toml", "yml"})

# Language tags that indicate a FLUX code block
_FLUX_LANGS = frozenset({"flux", "flux-type", "flux-type", "fluxfn"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_yaml_frontmatter(text: str) -> dict[str, Any]:
    """Ultra-lightweight YAML-like parser for flat key: value frontmatter.

    Handles:
      - ``key: value``  →  str
      - ``key: 1.0``    →  float
      - ``key: 42``     →  int
      - ``key: true``   →  bool
    Multi-line or nested structures are returned as raw strings.
    """
    result: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        # Coerce simple scalar types
        if val.lower() in ("true", "yes"):
            result[key] = True
        elif val.lower() in ("false", "no"):
            result[key] = False
        else:
            try:
                result[key] = int(val)
            except ValueError:
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val
    return result


def _classify_codeblock(node: CodeBlock) -> CodeBlock:
    """Replace a generic CodeBlock with the correct subclass."""
    lang = node.lang.lower() if node.lang else ""
    if lang in _FLUX_LANGS:
        return FluxCodeBlock(
            span=node.span,
            lang=node.lang,
            content=node.content,
            meta=node.meta,
        )
    if lang in _DATA_LANGS:
        return DataBlock(
            span=node.span,
            lang=node.lang,
            content=node.content,
            meta=node.meta,
        )
    return NativeBlock(
        span=node.span,
        lang=node.lang,
        content=node.content,
        meta=node.meta,
    )


def _parse_agent_args(text: str) -> dict[str, Any]:
    """Parse the free-text after ``## agent:`` or ``## fn:``.

    Examples
    --------
    "cleanup"               → {"name": "cleanup"}
    "hot-path, vectorize"   → {"flags": ["hot-path", "vectorize"]}
    "cross_product(a: Vec4, b: Vec4) -> Vec4"
                            → {"signature": "cross_product(a: Vec4, b: Vec4) -> Vec4"}
    """
    text = text.strip()
    args: dict[str, Any] = {}

    # Detect function signature: contains parentheses or ->
    if "(" in text or "->" in text:
        args["signature"] = text
        # Try to extract function name
        m = re.match(r"(\w+)\s*\(", text)
        if m:
            args["name"] = m.group(1)
    elif "," in text:
        args["flags"] = [s.strip() for s in text.split(",") if s.strip()]
    else:
        args["name"] = text

    return args


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class FluxMDParser:
    """Parse FLUX Markdown into a :class:`FluxModule` AST."""

    def __init__(self) -> None:
        self.errors: list[FluxTypeError] = []

    # -- public API --------------------------------------------------------

    def parse(self, source: str) -> FluxModule:
        """Parse *source* and return a :class:`FluxModule`.

        The returned module's ``children`` list contains fully-classified
        nodes (FluxCodeBlock / DataBlock / NativeBlock instead of raw
        CodeBlock) and extracted AgentDirective nodes.
        """
        self.errors.clear()
        lines = source.split("\n")

        # -- Step 1: extract frontmatter ------------------------------------
        frontmatter: dict[str, Any] = {}
        body_start_line = 0  # 0-indexed line where body begins

        fm_match = _RE_FRONTMATTER.match(source)
        if fm_match:
            raw_fm = fm_match.group(1)
            frontmatter = _parse_yaml_frontmatter(raw_fm)
            # Count how many lines the frontmatter block occupies
            fm_text = source[: fm_match.end()]
            body_start_line = fm_text.count("\n") - 1  # the closing --- line
            # Skip blank line after frontmatter if present
            if body_start_line < len(lines) and lines[body_start_line].strip() == "":
                body_start_line += 1

        # -- Step 2: parse body lines into raw AST nodes -------------------
        raw_children = self._parse_body(lines, body_start_line)

        # -- Step 3: classify CodeBlocks ------------------------------------
        classified = self._classify_nodes(raw_children)

        # -- Step 4: extract agent directives from headings -----------------
        final = self._extract_agent_directives(classified)

        # Build full span
        end_line = len(lines)
        span = SourceSpan(1, end_line, 1, len(lines[-1]) + 1 if lines else 1)

        return FluxModule(frontmatter=frontmatter, children=final, span=span)

    # -- body parser --------------------------------------------------------

    def _parse_body(
        self, lines: list[str], start: int
    ) -> list[LocatedNode]:
        nodes: list[LocatedNode] = []
        i = start
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # Skip blank lines
            if not stripped:
                i += 1
                continue

            # --- Code fence ------------------------------------------------
            fence_match = _RE_FENCE_OPEN.match(line)
            if fence_match:
                node, i = self._parse_code_block(lines, i, fence_match)
                nodes.append(node)
                continue

            # --- Heading ---------------------------------------------------
            head_match = _RE_HEADING.match(line)
            if head_match:
                level = len(head_match.group(1))
                text = head_match.group(2).strip()
                span = self._span(i, 0, i, len(line))
                nodes.append(Heading(level=level, text=text, span=span))
                i += 1
                continue

            # --- List items ------------------------------------------------
            list_match = _RE_ULIST.match(line) or _RE_OLIST.match(line)
            if list_match:
                node, i = self._parse_list(lines, i)
                nodes.append(node)
                continue

            # --- Paragraph (default) ---------------------------------------
            node, i = self._parse_paragraph(lines, i)
            nodes.append(node)

        return nodes

    # -- code block ---------------------------------------------------------

    def _parse_code_block(
        self,
        lines: list[str],
        start: int,
        open_match: re.Match,
    ) -> tuple[CodeBlock, int]:
        fence_char = open_match.group(1)
        lang = open_match.group(2)
        meta = open_match.group(3).strip()

        content_lines: list[str] = []
        i = start + 1
        n = len(lines)

        while i < n:
            if lines[i].strip().startswith(fence_char):
                # Found closing fence
                content = "\n".join(content_lines)
                span = self._span(start, 0, i, len(lines[i]))
                return (
                    CodeBlock(lang=lang, content=content, meta=meta, span=span),
                    i + 1,
                )
            content_lines.append(lines[i])
            i += 1

        # Unterminated fence — treat rest as content
        self.errors.append(
            FluxTypeError(
                message=f"Unterminated code fence starting at line {start + 1}",
                span=self._span(start, 0, n - 1, len(lines[-1]) if lines else 0),
            )
        )
        content = "\n".join(content_lines)
        span = self._span(start, 0, n - 1, len(lines[-1]) if lines else 0)
        return CodeBlock(lang=lang, content=content, meta=meta, span=span), n

    # -- list ---------------------------------------------------------------

    def _parse_list(
        self,
        lines: list[str],
        start: int,
    ) -> tuple[ListBlock, int]:
        first_match = _RE_ULIST.match(lines[start]) or _RE_OLIST.match(lines[start])
        ordered = bool(_RE_OLIST.match(lines[start]))

        items: list[ListItem] = []
        i = start
        n = len(lines)

        while i < n:
            ul_m = _RE_ULIST.match(lines[i])
            ol_m = _RE_OLIST.match(lines[i])
            match = ul_m or ol_m

            if not match:
                # Blank line: only continue if the *same* list type follows
                if lines[i].strip() == "" and i + 1 < n:
                    next_ul = _RE_ULIST.match(lines[i + 1])
                    next_ol = _RE_OLIST.match(lines[i + 1])
                    same_type = (ordered and next_ol) or (not ordered and next_ul)
                    if same_type:
                        i += 1
                        continue
                break

            text = match.group(2).strip()
            indent = len(match.group(1))
            span = self._span(i, indent, i, len(lines[i]))
            items.append(ListItem(text=text, children=[], span=span))
            i += 1

        span = self._span(start, 0, i - 1, len(lines[i - 1]) if i > start else 0)
        return ListBlock(ordered=ordered, items=items, span=span), i

    # -- paragraph ----------------------------------------------------------

    def _parse_paragraph(
        self,
        lines: list[str],
        start: int,
    ) -> tuple[Paragraph, int]:
        text_lines: list[str] = []
        i = start
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # Stop at blank lines or special blocks
            if not stripped:
                break
            if _RE_HEADING.match(line):
                break
            if _RE_FENCE_OPEN.match(line):
                break
            if _RE_ULIST.match(line) or _RE_OLIST.match(line):
                break

            text_lines.append(stripped)
            i += 1

        text = " ".join(text_lines)
        span = self._span(start, 0, i - 1, len(lines[i - 1]) if i > start else 0)
        return Paragraph(text=text, span=span), i

    # -- classification & directive extraction ------------------------------

    def _classify_nodes(self, nodes: list[LocatedNode]) -> list[LocatedNode]:
        out: list[LocatedNode] = []
        for node in nodes:
            if isinstance(node, CodeBlock):
                out.append(_classify_codeblock(node))
            else:
                out.append(node)
        return out

    def _extract_agent_directives(
        self, nodes: list[LocatedNode]
    ) -> list[LocatedNode]:
        """Replace ``## agent:`` / ``## fn:`` headings with AgentDirective.

        The body of the directive is the immediately following node(s)
        (typically a code block).
        """
        out: list[LocatedNode] = []
        i = 0
        while i < len(nodes):
            node = nodes[i]

            if isinstance(node, Heading) and _RE_AGENT_DIRECTIVE.match(
                f"## {node.text}"
            ):
                kind_match = _RE_AGENT_KIND.match(f"## {node.text}")
                kind = kind_match.group(1).lower() if kind_match else "agent"
                # Extract content after the "## agent:" / "## fn " separator
                full_heading = f"## {node.text}"
                content = full_heading[kind_match.end():].strip()
                args = _parse_agent_args(content)
                directive = AgentDirective(
                    name=kind,
                    args=args,
                    body=[],
                    span=node.span,
                )

                # Collect following nodes as body until next heading of same
                # or higher level, or another agent directive, or end
                i += 1
                while i < len(nodes):
                    next_node = nodes[i]
                    if isinstance(next_node, Heading):
                        if _RE_AGENT_DIRECTIVE.match(f"## {next_node.text}"):
                            break
                        if next_node.level <= node.level:
                            break
                    # Collect body nodes
                    if isinstance(next_node, (CodeBlock, FluxCodeBlock, DataBlock, NativeBlock)):
                        directive.body.append(next_node)
                        i += 1
                    elif isinstance(next_node, Paragraph):
                        directive.body.append(next_node)
                        i += 1
                    else:
                        i += 1
                        break

                out.append(directive)
            else:
                out.append(node)
                i += 1

        return out

    # -- span helper --------------------------------------------------------

    @staticmethod
    def _span(
        line_s: int, col_s: int, line_e: int, col_e: int
    ) -> SourceSpan:
        """Build a SourceSpan (1-indexed lines/cols) from 0-indexed inputs."""
        return SourceSpan(
            line_start=line_s + 1,
            line_end=line_e + 1,
            col_start=col_s + 1,
            col_end=col_e + 1,
        )
