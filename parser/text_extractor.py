"""
parser/text_extractor.py — Visible text extraction.

Phase 2: builds a DOM via html_tree_builder, then walks the tree to
produce the same terminal-oriented visible text as Phase 1.

Rules:
  - Skip content inside <script>, <style>, <head>
  - Collapse whitespace (multiple spaces/newlines → single space)
  - Add a newline after block-level tags (div, p, h1-h6, li, br, etc.)
  - Decode basic HTML entities (&amp; &lt; &gt; &nbsp; &#NNN;)
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Iterator, Tuple

from parser.dom import DocumentNode, ElementNode, Node, TextNode
from parser.html_tree_builder import build_tree
from parser.html_tokenizer import VOID_ELEMENTS


# Tags whose content should be completely hidden
HIDDEN_TAGS = {"script", "style", "head", "meta", "link", "noscript"}

# Tags that introduce a visual line break after their content
BLOCK_TAGS = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "blockquote", "pre", "article",
    "section", "header", "footer", "nav", "main", "aside",
    "tr", "td", "th", "dt", "dd", "figure", "figcaption",
    "address", "fieldset", "legend",
}

INLINE_BREAK_TAGS = {"br", "hr"}

# (kind, tag_name) or ("TEXT", "", text)
DomEvent = Tuple[str, str, str]


def extract_text(html: str) -> str:
    """
    Return the visible text content of an HTML string,
    formatted for terminal display.
    """
    root = build_tree(html)
    events = list(_iter_dom_events(root))
    return _render_events(events)


def _iter_dom_events(node: Node) -> Iterator[DomEvent]:
    """Depth-first tag/text stream (like a simplified token list)."""
    if isinstance(node, DocumentNode):
        for ch in node.children:
            yield from _iter_dom_events(ch)
    elif isinstance(node, TextNode):
        yield ("TEXT", "", node.content)
    elif isinstance(node, ElementNode):
        yield ("START", node.tag_name, "")
        for ch in node.children:
            yield from _iter_dom_events(ch)
        yield ("END", node.tag_name, "")
    else:
        for ch in node.children:
            yield from _iter_dom_events(ch)


def _render_events(events: list[DomEvent]) -> str:
    lines: list[str] = []
    current_line: list[str] = []
    skip_stack: int = 0
    heading_level: int = 0

    def flush_line(extra_newline: bool = False) -> None:
        line = _collapse_whitespace("".join(current_line)).strip()
        current_line.clear()
        if line:
            if heading_level:
                prefix = "#" * heading_level + " "
                lines.append(prefix + line)
            else:
                lines.append(line)
        if extra_newline and lines and lines[-1] != "":
            lines.append("")

    for kind, tag, payload in events:
        if kind == "START":
            if tag in HIDDEN_TAGS:
                if current_line:
                    flush_line()
                # Void hidden tags (meta, link) never get an END in the DOM
                if tag not in VOID_ELEMENTS:
                    skip_stack += 1
                continue

            if skip_stack > 0:
                continue

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                flush_line()
                heading_level = int(tag[1])
            elif tag in BLOCK_TAGS:
                flush_line()
            elif tag in INLINE_BREAK_TAGS:
                flush_line(extra_newline=(tag == "hr"))

        elif kind == "END":
            if tag in HIDDEN_TAGS:
                skip_stack = max(0, skip_stack - 1)
                continue

            if skip_stack > 0:
                continue

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                flush_line(extra_newline=True)
                heading_level = 0
            elif tag in BLOCK_TAGS:
                flush_line()

        elif kind == "TEXT":
            if skip_stack > 0:
                continue
            decoded = html_lib.unescape(payload)
            current_line.append(decoded)

    flush_line()

    result_lines: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and prev_blank:
            continue
        result_lines.append(line)
        prev_blank = is_blank

    return "\n".join(result_lines).strip()


def _collapse_whitespace(text: str) -> str:
    """Replace all runs of whitespace with a single space."""
    return re.sub(r"[ \t\r\n]+", " ", text)
