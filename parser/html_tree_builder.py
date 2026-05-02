"""
parser/html_tree_builder.py — Builds a DOM tree from HTML tokens.
"""

from typing import List, Iterator
from parser.html_tokenizer import HTMLTokenizer, Token, TokenType, VOID_ELEMENTS
from dom.node import Node


def build_tree(html: str) -> Node:
    """Parse HTML string into a DOM tree."""
    tokenizer = HTMLTokenizer(html)
    return build_tree_from_tokens(tokenizer.tokenize())


def build_tree_from_tokens(tokens: Iterator[Token]) -> Node:
    """Build a DOM tree from a stream of tokens."""
    document = Node(node_type='document', tag_name='document')
    
    # Open elements stack. Initially contains only the document.
    stack: List[Node] = [document]

    for token in tokens:
        if token.type == TokenType.START_TAG:
            # Create a new element node
            node = Node(
                node_type='element',
                tag_name=token.tag_name,
                attributes=dict(token.attributes)
            )
            
            # Append it to the current open element
            if stack:
                stack[-1].append_child(node)
                
            # If it's not a self-closing/void tag, push it to the stack
            if not token.self_closing and token.tag_name not in VOID_ELEMENTS:
                stack.append(node)
                
        elif token.type == TokenType.END_TAG:
            # Pop elements until we find the matching start tag
            # This is a simplified error recovery
            for i in range(len(stack) - 1, 0, -1):
                if stack[i].tag_name == token.tag_name:
                    # Found it! Pop everything up to and including this element
                    stack = stack[:i]
                    break
                    
        elif token.type == TokenType.TEXT:
            # Ignore completely empty text nodes (just whitespace that shouldn't be rendered)
            # Actually, standard browsers keep them but we might strip pure whitespace for simplicity
            if token.text.strip():
                node = Node(
                    node_type='text',
                    text=token.text
                )
                if stack:
                    stack[-1].append_child(node)
                    
        elif token.type == TokenType.EOF:
            break
            
    return document
