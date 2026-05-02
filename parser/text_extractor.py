"""
parser/text_extractor.py — Visible text extraction from a token stream.

Phase 1 goal: given an HTML string, print all the text a user would
see if the page were rendered. This is the simplest possible "render".

Rules:
  - Skip content inside <script>, <style>, <head>
  - Collapse whitespace (multiple spaces/newlines → single space)
  - Add a newline after block-level tags (div, p, h1-h6, li, br, etc.)
  - Decode basic HTML entities (&amp; &lt; &gt; &nbsp; &#NNN;)
"""

import re
import html as html_lib
from typing import Iterator

from parser.html_tokenizer import HTMLTokenizer, TokenType, Token


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


def extract_text(html: str) -> str:
    """
    Return the visible text content of an HTML string,
    formatted for terminal display.
    """
    tokenizer = HTMLTokenizer(html)
    tokens = list(tokenizer.tokenize())
    return _render_tokens(tokens)


def _render_tokens(tokens: list[Token]) -> str:
    lines: list[str] = []
    current_line: list[str] = []
    skip_stack: int = 0          # depth of hidden tags we're inside
    heading_level: int = 0       # non-zero when inside h1-h6

    def flush_line(extra_newline=False):
        """Append accumulated text as a line, then reset."""
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

    for tok in tokens:
        if tok.type == TokenType.EOF:
            break

        if tok.type == TokenType.START_TAG:
            tag = tok.tag_name

            # Enter a hidden zone.
            # Void/self-closing elements (meta, link, br…) have no end tag,
            # so don't increment the stack — there's nothing to pop.
            if tag in HIDDEN_TAGS:
                if current_line:
                    flush_line()
                if not tok.self_closing:
                    skip_stack += 1
                continue

            if skip_stack > 0:
                continue

            # Track heading level for prefix decoration
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                flush_line()
                heading_level = int(tag[1])
            elif tag in BLOCK_TAGS:
                flush_line()
            elif tag in INLINE_BREAK_TAGS:
                flush_line(extra_newline=(tag == "hr"))

        elif tok.type == TokenType.END_TAG:
            tag = tok.tag_name

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

        elif tok.type == TokenType.TEXT:
            if skip_stack > 0:
                continue
            # Decode HTML entities (&amp; → &, &#160; → nbsp, etc.)
            decoded = html_lib.unescape(tok.text)
            current_line.append(decoded)

    # Flush anything remaining
    flush_line()

    # Join lines, remove runs of blank lines (max one blank line in a row)
    result_lines = []
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
