# ToyBrowser — Phase 1

A minimal browser engine written in Python for learning purposes.

## What Phase 1 does

- Opens a raw TCP socket and sends an HTTP/1.0 GET request
- Tokenizes the HTML response character-by-character (state machine)
- Extracts and prints all visible text — skipping `<script>`, `<style>`, `<head>`
- Decodes HTML entities (`&amp;` → `&`, `&lt;` → `<`, etc.)
- Decorates headings with `#` / `##` / `###` prefixes

## Running it

No external dependencies required for the main engine. Requires Python 3.10+.

```bash
# Demo mode — no network needed
python main.py --demo

# Fetch a real URL
python main.py http://example.com
python main.py http://info.cern.ch

# Debug: show raw token stream
python main.py http://example.com --tokens

# Debug: show raw HTML source
python main.py http://example.com --raw
```

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## File structure

```
toy_browser/
├── net/
│   └── http.py              # Raw TCP socket HTTP/1.0 fetcher
├── parser/
│   ├── html_tokenizer.py    # Character-by-character state machine tokenizer
│   └── text_extractor.py    # Visible text extraction from token stream
├── tests/
│   └── test_phase1.py       # 37 unit tests (no network calls needed)
└── main.py                  # CLI entry point
```

## What comes next

| Phase | Goal |
|-------|------|
| Phase 2 | Full DOM tree — Node, ElementNode, tree builder with error recovery |
| Phase 3 | CSS parser, cascade, specificity, computed styles per node |
| Phase 4 | Box model layout — block/inline flow, widths, heights |
| Phase 5 | Painting to a Pygame window — real pixel output |
| Phase 6 | Basic JS — getElementById, style mutation, click events |

## Key concepts implemented

**Tokenizer state machine** — The HTML tokenizer is a state machine with
states like `DATA`, `TAG_OPEN`, `TAG_NAME`, `ATTR_NAME`, `ATTR_VALUE_DQ`,
`COMMENT`, etc. Each character transitions the machine to a new state and
may emit a token.

**Void elements** — Tags like `<br>`, `<img>`, `<meta>`, `<input>` are
self-closing and never have end tags. The tokenizer handles this automatically.

**Skip-stack pattern** — To hide content inside `<head>`, `<script>`,
`<style>`, we maintain a depth counter. We increment on open, decrement on
close. This handles nesting correctly.

## Known limitations (intentional for Phase 1)

- HTTP only (no HTTPS/TLS)
- No redirects
- No DOM tree (just token stream)
- No CSS parsing
- No visual layout or painting
- Terminal/stdout output only
