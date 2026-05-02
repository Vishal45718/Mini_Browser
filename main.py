#!/usr/bin/env python3
"""
main.py — ToyBrowser CLI

Usage:
    python main.py <url>
    python main.py <url> --tokens        # show raw token stream
    python main.py <url> --dom           # show printed DOM tree
    python main.py <url> --raw           # show raw HTML source
    python main.py --demo                # run without network (built-in HTML)

Examples:
    python main.py http://example.com
    python main.py http://info.cern.ch
    python main.py http://example.com --dom
    python main.py --demo
"""

import sys
import textwrap

from net.http import fetch, HTTPError
from parser.html_tokenizer import HTMLTokenizer, TokenType
from parser.html_tree_builder import build_tree
from parser.text_extractor import extract_text


# ---------------------------------------------------------------------------
# Terminal formatting helpers
# ---------------------------------------------------------------------------

BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"

TERMINAL_WIDTH = 80


def hr(char="─", color=DIM):
    print(f"{color}{char * TERMINAL_WIDTH}{RESET}")


def header(title: str):
    hr()
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    hr()


# ---------------------------------------------------------------------------
# Demo HTML (used when running --demo, no network needed)
# ---------------------------------------------------------------------------

DEMO_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>ToyBrowser Demo Page</title>
  <style>
    body { font-family: sans-serif; }
    h1   { color: navy; }
  </style>
</head>
<body>
  <h1>Welcome to ToyBrowser</h1>
  <p>This is a <strong>minimal browser engine</strong> written in Python.</p>

  <h2>Features in Phase 1</h2>
  <ul>
    <li>Raw TCP/HTTP networking</li>
    <li>Character-by-character HTML tokenizer</li>
    <li>Visible text extraction</li>
    <li>HTML entity decoding (&amp;amp; &amp;lt; &amp;gt;)</li>
  </ul>

  <h2>Coming in later phases</h2>
  <ul>
    <li>Full DOM tree (Phase 2)</li>
    <li>CSS parsing &amp; cascade (Phase 3)</li>
    <li>Box model layout (Phase 4)</li>
    <li>Pixel painting with Pygame (Phase 5)</li>
    <li>Basic JavaScript execution (Phase 6)</li>
  </ul>

  <p>Built by an engineering student learning how browsers work.</p>

  <!-- This comment should be invisible in the output -->
  <script>
    // This script content should be hidden too
    alert("you should not see this");
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Display modes
# ---------------------------------------------------------------------------

def display_text(html: str, url: str):
    """Main mode: render visible text to the terminal."""
    text = extract_text(html)

    header(f"ToyBrowser — {url}")
    print()

    # Wrap long lines to terminal width
    for line in text.split("\n"):
        if line.startswith("#"):
            # Headings: print bold, no wrapping
            print(f"{BOLD}{line}{RESET}")
        elif line == "":
            print()
        else:
            for wrapped in textwrap.wrap(line, width=TERMINAL_WIDTH - 2) or [""]:
                print(f"  {wrapped}")

    print()
    hr()
    char_count = len(text)
    line_count = text.count("\n") + 1
    print(f"{DIM}  {line_count} lines, {char_count} characters of visible text{RESET}")
    hr()


def display_tokens(html: str):
    """Debug mode: show the raw token stream."""
    header("Token Stream (debug mode)")
    tokenizer = HTMLTokenizer(html)
    for i, tok in enumerate(tokenizer.tokenize()):
        if tok.type.name == "EOF":
            print(f"\n{DIM}  [{i} tokens total]{RESET}")
            break
        color = {
            "START_TAG": GREEN,
            "END_TAG":   YELLOW,
            "TEXT":      RESET,
            "COMMENT":   DIM,
            "DOCTYPE":   CYAN,
        }.get(tok.type.name, RESET)
        print(f"  {DIM}{i:>4}{RESET}  {color}{tok}{RESET}")


def display_raw(html: str):
    """Show the raw HTML source."""
    header("Raw HTML Source")
    for i, line in enumerate(html.split("\n"), 1):
        print(f"  {DIM}{i:>4}{RESET}  {line}")


def display_dom(html: str):
    """Debug mode: show the DOM tree."""
    header("DOM Tree (Phase 2)")
    dom = build_tree(html)
    dom.dump()


# ---------------------------------------------------------------------------
# HTTP response display
# ---------------------------------------------------------------------------

def display_response_info(response):
    status_color = GREEN if response.status_code == 200 else RED
    print(f"\n{DIM}  HTTP {status_color}{response.status_code} {response.status_text}{RESET}"
          f"  —  {len(response.body):,} bytes\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    # --demo flag: skip network, use built-in HTML
    if "--demo" in args:
        mode = "dom" if "--dom" in args else "tokens" if "--tokens" in args else "raw" if "--raw" in args else "text"
        print(f"\n{CYAN}Running in demo mode (no network required){RESET}\n")
        if mode == "tokens":
            display_tokens(DEMO_HTML)
        elif mode == "dom":
            display_dom(DEMO_HTML)
        elif mode == "raw":
            display_raw(DEMO_HTML)
        else:
            display_text(DEMO_HTML, "demo://local")
        return

    # Require a URL argument
    if not args or args[0].startswith("--"):
        print(__doc__)
        sys.exit(1)

    url = args[0]
    mode = "dom" if "--dom" in args else "tokens" if "--tokens" in args else "raw" if "--raw" in args else "text"

    # Add http:// if missing
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    # Fetch
    print(f"\n{DIM}  Fetching {url} ...{RESET}", end="", flush=True)
    try:
        response = fetch(url)
    except HTTPError as e:
        print(f"\n\n{RED}  Network error: {e}{RESET}\n")
        sys.exit(1)

    print(f" {GREEN}done{RESET}")
    display_response_info(response)

    if mode == "tokens":
        display_tokens(response.body)
    elif mode == "dom":
        display_dom(response.body)
    elif mode == "raw":
        display_raw(response.body)
    else:
        display_text(response.body, url)


if __name__ == "__main__":
    main()
