"""
parser/html_tree_builder.py — Stack-based HTML tree builder (Phase 2).

Consumes tokens from html_tokenizer and produces a DocumentNode whose
children mirror the parsed markup.
"""

from __future__ import annotations

from typing import Iterator, List

from parser.dom import DocumentNode, ElementNode, Node, TextNode
from parser.html_tokenizer import HTMLTokenizer, Token, TokenType, VOID_ELEMENTS


class HTMLTreeBuilder:
    """
    Build a DOM from a token stream using an open-elements stack.

    - START_TAG: create ElementNode under the current node; push it unless
      void or self-closing.
    - TEXT: append TextNode (whitespace-only runs are skipped).
    - END_TAG: pop through mismatches until the tag name matches, or ignore.
    """

    def __init__(self) -> None:
        self.root = DocumentNode()
        self._stack: List[Node] = [self.root]

    @property
    def current(self) -> Node:
        return self._stack[-1]

    def _is_void_or_closed(self, token: Token) -> bool:
        return token.self_closing or token.tag_name in VOID_ELEMENTS

    def handle_start_tag(self, token: Token) -> None:
        el = ElementNode(token.tag_name, dict(token.attributes))
        self.current.append_child(el)
        if not self._is_void_or_closed(token):
            self._stack.append(el)

    def handle_text(self, token: Token) -> None:
        if not token.text.strip():
            return
        self.current.append_child(TextNode(token.text))

    def handle_end_tag(self, token: Token) -> None:
        name = token.tag_name
        # Never pop the document root
        if len(self._stack) <= 1:
            return
        if isinstance(self.current, ElementNode) and self.current.tag_name == name:
            self._stack.pop()
            return
        # Recovery: search for a matching open element below the document
        for i in range(len(self._stack) - 1, 0, -1):
            node = self._stack[i]
            if isinstance(node, ElementNode) and node.tag_name == name:
                self._stack = self._stack[:i]
                return
        # No matching open element — ignore stray end tag

    def handle_token(self, token: Token) -> None:
        if token.type == TokenType.START_TAG:
            self.handle_start_tag(token)
        elif token.type == TokenType.TEXT:
            self.handle_text(token)
        elif token.type == TokenType.END_TAG:
            self.handle_end_tag(token)
        # DOCTYPE, COMMENT: ignored for this phase

    def run(self, tokens: Iterator[Token]) -> DocumentNode:
        for token in tokens:
            if token.type == TokenType.EOF:
                break
            self.handle_token(token)
        return self.root


def build_tree_from_tokens(tokens: Iterator[Token]) -> DocumentNode:
    builder = HTMLTreeBuilder()
    return builder.run(tokens)


def build_tree(html: str) -> DocumentNode:
    tokenizer = HTMLTokenizer(html)
    return build_tree_from_tokens(tokenizer.tokenize())
