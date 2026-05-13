"""
parser/dom.py — DOM node hierarchy for the toy HTML parser.

Phase 2: a small class tree (document, elements, text) with parent/child
links and a terminal tree dumper for debugging.
"""

from __future__ import annotations

from abc import ABC
from typing import Dict, List, Optional


class Node(ABC):
    """Base DOM node: parent pointer and ordered children."""

    __slots__ = ("parent", "children")

    def __init__(self) -> None:
        self.parent: Optional[Node] = None
        self.children: List[Node] = []

    def append_child(self, child: Node) -> None:
        child.parent = self
        self.children.append(child)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class DocumentNode(Node):
    """Synthetic root that wraps the whole parse result (like #document)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "DocumentNode()"


class ElementNode(Node):
    __slots__ = ("tag_name", "attributes")

    def __init__(self, tag_name: str, attributes: Optional[Dict[str, str]] = None) -> None:
        super().__init__()
        self.tag_name = tag_name
        self.attributes: Dict[str, str] = dict(attributes) if attributes else {}

    def __repr__(self) -> str:
        attrs = ", ".join(f"{k!r}: {v!r}" for k, v in sorted(self.attributes.items()))
        inner = f"{self.tag_name!r}"
        if attrs:
            inner += f", {{{attrs}}}"
        return f"ElementNode({inner})"


class TextNode(Node):
    __slots__ = ("content",)

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def __repr__(self) -> str:
        if len(self.content) > 40:
            return f"TextNode({self.content[:37]!r}...)"
        return f"TextNode({self.content!r})"


def dump_tree(node: Node, indent: int = 0) -> None:
    """Print an indented outline of the DOM to stdout."""
    pad = "  " * indent
    if isinstance(node, DocumentNode):
        print(f"{pad}#document")
        for ch in node.children:
            dump_tree(ch, indent + 1)
    elif isinstance(node, ElementNode):
        attr_str = "".join(f' {k}="{v}"' for k, v in node.attributes.items())
        print(f"{pad}<{node.tag_name}{attr_str}>")
        for ch in node.children:
            dump_tree(ch, indent + 1)
    elif isinstance(node, TextNode):
        preview = node.content.replace("\n", "\\n")
        if len(preview) > 72:
            preview = preview[:69] + "..."
        print(f"{pad}#text {preview!r}")
    else:
        print(f"{pad}{node!r}")
        for ch in node.children:
            dump_tree(ch, indent + 1)
