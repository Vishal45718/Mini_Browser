"""
tests/test_phase1.py — Unit tests for Phase 1 components.

Run with:  python -m unittest discover tests -v
Or:        python -m unittest tests/test_phase1.py -v
"""

import unittest
from parser.dom import DocumentNode, ElementNode, TextNode
from parser.html_tokenizer import HTMLTokenizer, TokenType, Token
from parser.html_tree_builder import build_tree
from parser.text_extractor import extract_text


# ===========================================================================
# Tokenizer tests
# ===========================================================================

def tokens(html: str) -> list[Token]:
    """Helper: tokenize and return all non-EOF tokens."""
    t = HTMLTokenizer(html)
    return [tok for tok in t.tokenize() if tok.type != TokenType.EOF]


class TestTokenizer(unittest.TestCase):

    def test_simple_text(self):
        toks = tokens("hello world")
        self.assertEqual(len(toks), 1)
        self.assertEqual(toks[0].type, TokenType.TEXT)
        self.assertEqual(toks[0].text, "hello world")

    def test_simple_tag(self):
        toks = tokens("<p>hello</p>")
        types = [t.type for t in toks]
        self.assertIn(TokenType.START_TAG, types)
        self.assertIn(TokenType.END_TAG, types)
        self.assertIn(TokenType.TEXT, types)

    def test_start_tag_name(self):
        toks = tokens("<div>")
        self.assertEqual(toks[0].type, TokenType.START_TAG)
        self.assertEqual(toks[0].tag_name, "div")

    def test_end_tag_name(self):
        toks = tokens("</div>")
        self.assertEqual(toks[0].type, TokenType.END_TAG)
        self.assertEqual(toks[0].tag_name, "div")

    def test_tag_attributes_double_quotes(self):
        toks = tokens('<a href="http://example.com" class="link">')
        self.assertEqual(toks[0].attributes["href"], "http://example.com")
        self.assertEqual(toks[0].attributes["class"], "link")

    def test_tag_attributes_single_quotes(self):
        toks = tokens("<img src='photo.jpg'>")
        self.assertEqual(toks[0].attributes["src"], "photo.jpg")

    def test_tag_attributes_unquoted(self):
        toks = tokens("<input type=text>")
        self.assertEqual(toks[0].attributes["type"], "text")

    def test_boolean_attribute(self):
        toks = tokens("<input disabled>")
        self.assertIn("disabled", toks[0].attributes)

    def test_self_closing_slash(self):
        toks = tokens("<br />")
        self.assertTrue(toks[0].self_closing)

    def test_void_element_auto_self_close(self):
        # <br> without slash should still be self-closing
        toks = tokens("<br>")
        self.assertTrue(toks[0].self_closing)

    def test_comment_skipped(self):
        toks = tokens("<!-- this is a comment -->hello")
        comment = [t for t in toks if t.type == TokenType.COMMENT]
        text    = [t for t in toks if t.type == TokenType.TEXT]
        self.assertEqual(len(comment), 1)
        self.assertIn("this is a comment", comment[0].text)
        self.assertTrue(any("hello" in t.text for t in text))

    def test_tag_names_lowercased(self):
        toks = tokens("<DIV></DIV>")
        self.assertEqual(toks[0].tag_name, "div")
        self.assertEqual(toks[1].tag_name, "div")

    def test_attribute_names_lowercased(self):
        toks = tokens('<a HREF="/foo">')
        self.assertIn("href", toks[0].attributes)

    def test_nested_tags(self):
        toks = tokens("<div><p>text</p></div>")
        tag_names = [t.tag_name for t in toks if t.type in (TokenType.START_TAG, TokenType.END_TAG)]
        self.assertEqual(tag_names, ["div", "p", "p", "div"])

    def test_multiple_text_nodes(self):
        toks = tokens("hello <b>world</b> bye")
        texts = [t.text for t in toks if t.type == TokenType.TEXT]
        combined = "".join(texts)
        self.assertIn("hello", combined)
        self.assertIn("world", combined)
        self.assertIn("bye", combined)

    def test_empty_string(self):
        toks = tokens("")
        self.assertTrue(all(t.type == TokenType.EOF for t in toks) or len(toks) == 0)

    def test_unclosed_tag_doesnt_crash(self):
        # Should not raise; just produce whatever tokens it can
        toks = tokens("<div>text with no close tag")
        self.assertTrue(any(t.type == TokenType.TEXT for t in toks))

    def test_lone_lt_treated_as_text(self):
        # A bare '<' not followed by a valid tag name
        toks = tokens("a < b")
        texts = [t.text for t in toks if t.type == TokenType.TEXT]
        combined = "".join(texts)
        self.assertIn("<", combined)


# ===========================================================================
# DOM / tree builder (Phase 2)
# ===========================================================================

class TestDOMTreeBuilder(unittest.TestCase):

    def test_document_root(self):
        root = build_tree("<p>hi</p>")
        self.assertIsInstance(root, DocumentNode)
        self.assertEqual(len(root.children), 1)

    def test_nested_elements(self):
        root = build_tree("<div><span>a</span></div>")
        div = root.children[0]
        self.assertIsInstance(div, ElementNode)
        self.assertEqual(div.tag_name, "div")
        self.assertEqual(len(div.children), 1)
        span = div.children[0]
        self.assertEqual(span.tag_name, "span")
        self.assertIsInstance(span.children[0], TextNode)
        self.assertEqual(span.children[0].content, "a")

    def test_void_not_pushed(self):
        root = build_tree("<p>x<br>y</p>")
        p = root.children[0]
        names = [c.tag_name for c in p.children if isinstance(c, ElementNode)]
        self.assertEqual(names, ["br"])
        texts = [c.content for c in p.children if isinstance(c, TextNode)]
        self.assertEqual(texts, ["x", "y"])

    def test_mismatched_end_closes_inner(self):
        root = build_tree("<div><span></div>after</span>")
        div = next(c for c in root.children if isinstance(c, ElementNode) and c.tag_name == "div")
        self.assertEqual(div.tag_name, "div")
        # `</div>` while span is open pops the stack to #document; remaining text attaches there.
        def all_text(n):
            parts = []
            if isinstance(n, TextNode):
                parts.append(n.content)
            for c in n.children:
                parts.extend(all_text(c))
            return parts
        self.assertIn("after", "".join(all_text(root)))

    def test_parent_pointers(self):
        root = build_tree("<a><b></b></a>")
        a = root.children[0]
        b = a.children[0]
        self.assertIs(b.parent, a)
        self.assertIs(a.parent, root)


# ===========================================================================
# Text extractor tests
# ===========================================================================

class TestTextExtractor(unittest.TestCase):

    def test_plain_text(self):
        result = extract_text("<p>Hello, world!</p>")
        self.assertIn("Hello, world!", result)

    def test_script_hidden(self):
        result = extract_text("<script>alert('secret')</script>visible")
        self.assertNotIn("secret", result)
        self.assertIn("visible", result)

    def test_style_hidden(self):
        result = extract_text("<style>body{color:red}</style>visible")
        self.assertNotIn("color", result)
        self.assertIn("visible", result)

    def test_head_hidden(self):
        result = extract_text("<head><title>Page Title</title></head><body>content</body>")
        self.assertNotIn("Page Title", result)
        self.assertIn("content", result)

    def test_headings_prefixed(self):
        result = extract_text("<h1>Main Title</h1>")
        self.assertTrue(result.startswith("# Main Title"))

    def test_h2_prefix(self):
        result = extract_text("<h2>Sub Title</h2>")
        self.assertTrue(result.startswith("## Sub Title"))

    def test_whitespace_collapsed(self):
        result = extract_text("<p>  hello    world  </p>")
        self.assertNotIn("  ", result)  # no double spaces
        self.assertIn("hello world", result)

    def test_entity_amp(self):
        result = extract_text("<p>cats &amp; dogs</p>")
        self.assertIn("cats & dogs", result)

    def test_entity_lt_gt(self):
        result = extract_text("<p>1 &lt; 2 &gt; 0</p>")
        self.assertIn("1 < 2 > 0", result)

    def test_entity_nbsp(self):
        # &nbsp; should decode to a non-breaking space, which we can detect
        result = extract_text("<p>hello&nbsp;world</p>")
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_full_page(self):
        html = """<!DOCTYPE html>
<html>
<head><title>Test</title><style>body{color:red}</style></head>
<body>
  <h1>Welcome</h1>
  <p>This is a <strong>test</strong> page.</p>
  <ul>
    <li>Item one</li>
    <li>Item two</li>
  </ul>
  <!-- hidden comment -->
  <script>var x = 1;</script>
</body>
</html>"""
        result = extract_text(html)
        self.assertIn("# Welcome", result)
        self.assertIn("This is a test page.", result)
        self.assertIn("Item one", result)
        self.assertIn("Item two", result)
        self.assertNotIn("hidden comment", result)
        self.assertNotIn("var x", result)
        self.assertNotIn("color:red", result)

    def test_empty_html(self):
        result = extract_text("")
        self.assertEqual(result, "")

    def test_nested_block_newlines(self):
        result = extract_text("<div><p>first</p><p>second</p></div>")
        lines = [l for l in result.split("\n") if l.strip()]
        self.assertTrue(any("first" in l for l in lines))
        self.assertTrue(any("second" in l for l in lines))


# ===========================================================================
# HTTP module tests (mocked — no real network calls)
# ===========================================================================

class TestHTTPParser(unittest.TestCase):
    """Test _parse_response without making real network calls."""

    def test_parse_200(self):
        from net.http import _parse_response
        raw = b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n<html>hi</html>"
        resp = _parse_response(raw, "http://example.com")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.status_text, "OK")
        self.assertIn("<html>hi</html>", resp.body)

    def test_parse_headers(self):
        from net.http import _parse_response
        raw = b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nServer: nginx\r\n\r\nbody"
        resp = _parse_response(raw, "http://example.com")
        self.assertEqual(resp.headers["content-type"], "text/html; charset=utf-8")
        self.assertEqual(resp.headers["server"], "nginx")

    def test_parse_404(self):
        from net.http import _parse_response
        raw = b"HTTP/1.0 404 Not Found\r\n\r\nNot found"
        resp = _parse_response(raw, "http://example.com")
        self.assertEqual(resp.status_code, 404)

    def test_charset_extraction(self):
        from net.http import _extract_charset
        self.assertEqual(_extract_charset("text/html; charset=utf-8"), "utf-8")
        self.assertEqual(_extract_charset("text/html; charset=ISO-8859-1"), "ISO-8859-1")
        self.assertEqual(_extract_charset("text/html"), "utf-8")  # default

    def test_invalid_scheme_raises(self):
        from net.http import fetch, HTTPError
        with self.assertRaisesRegex(HTTPError, "Unsupported scheme"):
            fetch("https://example.com")

    def test_bad_url_raises(self):
        from net.http import fetch, HTTPError
        with self.assertRaises(HTTPError):
            fetch("http://")

if __name__ == '__main__':
    unittest.main()
