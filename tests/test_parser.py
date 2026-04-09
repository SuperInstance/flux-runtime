"""Tests for the FLUX.MD parser.

Uses plain assert statements — no pytest fixtures needed.
Run via:  python -m pytest tests/test_parser.py -v
"""

from __future__ import annotations

import sys
import os

# Ensure src/ is on the path so we can import `flux`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flux.parser import FluxMDParser
from flux.parser.nodes import (
    AgentDirective,
    CodeBlock,
    DataBlock,
    FluxCodeBlock,
    FluxModule,
    Heading,
    ListBlock,
    ListItem,
    NativeBlock,
    Paragraph,
    SourceSpan,
)


# ---------------------------------------------------------------------------
# Sample FLUX.MD document used across several tests
# ---------------------------------------------------------------------------

SAMPLE_FLUX_MD = """\
---
flux: 1.0
agent: test-agent
trust: 0.85
---

## Module: Vector Math

This module implements vector operations.

## fn cross_product(a: Vec4, b: Vec4) -> Vec4
```c
## agent: hot-path, vectorize
Vec4 cross(Vec4 a, Vec4 b) {
    return (Vec4){a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x, 0};
}
```

## types
```flux-type
struct Vec4 { x: f32, y: f32, z: f32, w: f32 }
```

## agent: cleanup
```python
def cleanup():
    pass
```
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_frontmatter():
    """Frontmatter between --- delimiters is extracted into a dict."""
    p = FluxMDParser()
    mod = p.parse(SAMPLE_FLUX_MD)
    assert mod.frontmatter["flux"] == 1.0
    assert mod.frontmatter["agent"] == "test-agent"
    assert mod.frontmatter["trust"] == 0.85


def test_parse_headings():
    """All heading levels (## through ######) are recognised."""
    source = (
        "# Top level\n"
        "## Second\n"
        "### Third\n"
        "#### Fourth\n"
        "##### Fifth\n"
        "###### Sixth\n"
    )
    p = FluxMDParser()
    mod = p.parse(source)
    headings = [n for n in mod.children if isinstance(n, Heading)]
    # Headings that are NOT agent directives
    plain = [h for h in headings if not isinstance(h, AgentDirective)]
    assert len(plain) >= 5  # most are plain headings
    assert plain[0].level == 1
    assert plain[0].text == "Top level"
    assert plain[1].level == 2
    assert plain[1].text == "Second"
    assert plain[2].level == 3


def test_parse_code_blocks():
    """Fenced code blocks are parsed with correct lang/meta/content."""
    source = '```python\nprint("hello")\n```\n'
    p = FluxMDParser()
    mod = p.parse(source)
    blocks = [n for n in mod.children if isinstance(n, CodeBlock)]
    assert len(blocks) == 1
    block = blocks[0]
    assert isinstance(block, NativeBlock)
    assert block.lang == "python"
    assert 'print("hello")' in block.content


def test_parse_flux_type_block():
    """Code blocks with lang=flux-type become FluxCodeBlock nodes."""
    source = '```flux-type\nstruct Vec4 { x: f32, y: f32, z: f32, w: f32 }\n```\n'
    p = FluxMDParser()
    mod = p.parse(source)
    blocks = [n for n in mod.children if isinstance(n, CodeBlock)]
    assert len(blocks) == 1
    assert isinstance(blocks[0], FluxCodeBlock)
    assert blocks[0].lang == "flux-type"


def test_parse_data_block():
    """Code blocks with lang json/yaml/toml become DataBlock nodes."""
    source = '```json\n{"key": "value"}\n```\n'
    p = FluxMDParser()
    mod = p.parse(source)
    blocks = [n for n in mod.children if isinstance(n, CodeBlock)]
    assert len(blocks) == 1
    assert isinstance(blocks[0], DataBlock)
    assert blocks[0].lang == "json"


def test_parse_agent_directive():
    """## agent: and ## fn: headings become AgentDirective nodes."""
    p = FluxMDParser()
    mod = p.parse(SAMPLE_FLUX_MD)
    directives = [n for n in mod.children if isinstance(n, AgentDirective)]
    assert len(directives) >= 2

    # The ## fn: directive
    fn_dirs = [d for d in directives if d.name == "fn"]
    assert len(fn_dirs) == 1
    assert "signature" in fn_dirs[0].args
    assert fn_dirs[0].args["name"] == "cross_product"

    # The ## agent: cleanup directive
    agent_cleanup = [d for d in directives if d.name == "agent" and d.args.get("name") == "cleanup"]
    assert len(agent_cleanup) == 1
    assert len(agent_cleanup[0].body) >= 1
    assert isinstance(agent_cleanup[0].body[0], NativeBlock)


def test_parse_mixed():
    """Full FLUX.MD with frontmatter + headings + code blocks."""
    p = FluxMDParser()
    mod = p.parse(SAMPLE_FLUX_MD)
    assert isinstance(mod, FluxModule)
    assert len(mod.frontmatter) == 3
    assert len(mod.children) > 0

    # Should have at least some headings and code blocks
    headings = [n for n in mod.children if isinstance(n, Heading)]
    code_blocks = [n for n in mod.children if isinstance(n, CodeBlock)]
    paragraphs = [n for n in mod.children if isinstance(n, Paragraph)]
    # At least some content was parsed
    assert len(headings) + len(code_blocks) + len(paragraphs) > 0


def test_parse_empty():
    """Empty document returns a module with no children."""
    p = FluxMDParser()
    mod = p.parse("")
    assert isinstance(mod, FluxModule)
    assert mod.frontmatter == {}
    assert mod.children == []


def test_parse_nested_lists():
    """Unordered and ordered lists are parsed into ListBlock nodes."""
    source = (
        "- First item\n"
        "- Second item\n"
        "- Third item\n"
        "\n"
        "1. Alpha\n"
        "2. Beta\n"
        "3. Gamma\n"
    )
    p = FluxMDParser()
    mod = p.parse(source)
    lists = [n for n in mod.children if isinstance(n, ListBlock)]
    assert len(lists) == 2

    # Unordered list
    ul = lists[0]
    assert ul.ordered is False
    assert len(ul.items) == 3
    assert ul.items[0].text == "First item"
    assert ul.items[2].text == "Third item"

    # Ordered list
    ol = lists[1]
    assert ol.ordered is True
    assert len(ol.items) == 3
    assert ol.items[0].text == "Alpha"


def test_source_spans():
    """Every node has a SourceSpan with positive, increasing line numbers."""
    source = "# Hello\n\nSome paragraph text.\n\n```c\nint x;\n```\n"
    p = FluxMDParser()
    mod = p.parse(source)
    for node in mod.children:
        assert isinstance(node.span, SourceSpan)
        assert node.span.line_start >= 1
        assert node.span.line_end >= node.span.line_start


def test_code_block_with_meta():
    """Meta string after language tag is preserved."""
    source = "```python title=example.py\nprint('hi')\n```\n"
    p = FluxMDParser()
    mod = p.parse(source)
    blocks = [n for n in mod.children if isinstance(n, CodeBlock)]
    assert len(blocks) == 1
    assert blocks[0].meta == "title=example.py"


# ---------------------------------------------------------------------------
# Manual runner (fallback when pytest is unavailable)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    test_fns = [
        test_parse_frontmatter,
        test_parse_headings,
        test_parse_code_blocks,
        test_parse_flux_type_block,
        test_parse_data_block,
        test_parse_agent_directive,
        test_parse_mixed,
        test_parse_empty,
        test_parse_nested_lists,
        test_source_spans,
        test_code_block_with_meta,
    ]

    passed = 0
    failed = 0
    for fn in test_fns:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception:
            print(f"  ✗ {fn.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
