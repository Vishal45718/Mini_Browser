"""
parser/html_tokenizer.py — Character-by-character HTML tokenizer.

This is a *simplified* state machine — not the full HTML5 spec (which has
72 states), but enough to correctly tokenize well-formed HTML and recover
gracefully from common errors.

States implemented:
  DATA           — reading regular text content
  TAG_OPEN       — just saw '<'
  TAG_NAME       — reading a tag name after '<'
  END_TAG_OPEN   — just saw '</'
  ATTR_NAME      — reading an attribute name
  ATTR_BEFORE_EQ — saw attr name, waiting for '='
  ATTR_VALUE_SQ  — reading attr value in single quotes
  ATTR_VALUE_DQ  — reading attr value in double quotes
  ATTR_VALUE_UQ  — reading unquoted attr value
  SELF_CLOSE     — just saw '/' in a tag (self-closing)
  COMMENT        — inside <!-- ... -->
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator


# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------

class TokenType(Enum):
    DOCTYPE    = auto()
    START_TAG  = auto()
    END_TAG    = auto()
    TEXT       = auto()
    COMMENT    = auto()
    EOF        = auto()


@dataclass
class Token:
    type: TokenType
    tag_name: str = ""
    attributes: dict = field(default_factory=dict)
    text: str = ""
    self_closing: bool = False

    def __repr__(self):
        if self.type == TokenType.TEXT:
            return f"Text({self.text!r})"
        if self.type in (TokenType.START_TAG, TokenType.END_TAG):
            attrs = " ".join(f'{k}="{v}"' for k, v in self.attributes.items())
            close = "/" if self.self_closing else ""
            kind = "" if self.type == TokenType.START_TAG else "/"
            return f"<{kind}{self.tag_name} {attrs}{close}>".strip()
        return f"{self.type.name}"


# ---------------------------------------------------------------------------
# Void elements (self-closing — no end tag expected)
# ---------------------------------------------------------------------------

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class State(Enum):
    DATA           = auto()
    TAG_OPEN       = auto()
    TAG_NAME       = auto()
    END_TAG_OPEN   = auto()
    END_TAG_NAME   = auto()
    BEFORE_ATTR    = auto()
    ATTR_NAME      = auto()
    ATTR_BEFORE_EQ = auto()
    BEFORE_ATTR_VAL= auto()
    ATTR_VALUE_DQ  = auto()
    ATTR_VALUE_SQ  = auto()
    ATTR_VALUE_UQ  = auto()
    AFTER_ATTR_UQ  = auto()
    SELF_CLOSE     = auto()
    COMMENT_START  = auto()
    COMMENT        = auto()
    COMMENT_END_D1 = auto()  # saw first '-'
    COMMENT_END_D2 = auto()  # saw '--'
    DOCTYPE        = auto()


class HTMLTokenizer:
    """
    Tokenize an HTML string into a stream of Token objects.

    Usage:
        tokenizer = HTMLTokenizer(html_string)
        for token in tokenizer.tokenize():
            print(token)
    """

    def __init__(self, html: str):
        self.html = html
        self.pos = 0
        self.state = State.DATA

        # Accumulators — built up character by character
        self._tag_name = ""
        self._is_end_tag = False
        self._self_closing = False
        self._attrs: dict = {}
        self._cur_attr_name = ""
        self._cur_attr_val = ""
        self._text_buf = ""
        self._comment_buf = ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def tokenize(self) -> Iterator[Token]:
        """Yield tokens one by one until EOF."""
        while self.pos <= len(self.html):
            ch = self.html[self.pos] if self.pos < len(self.html) else None

            result = self._process(ch)
            if result is not None:
                # A single character can emit at most one token; but
                # _process may return a list for flush situations.
                if isinstance(result, list):
                    yield from result
                else:
                    yield result

            self.pos += 1

        # Flush any remaining text buffer
        if self._text_buf.strip():
            yield Token(TokenType.TEXT, text=self._text_buf)

        yield Token(TokenType.EOF)

    # ------------------------------------------------------------------
    # Internal state machine
    # ------------------------------------------------------------------

    def _process(self, ch):
        """
        Feed one character into the state machine.
        Returns a Token (or list of Tokens) if one is ready, else None.
        """
        s = self.state

        # ---- DATA: reading plain text ----
        if s == State.DATA:
            if ch is None:
                return None
            if ch == "<":
                text_tok = self._flush_text()
                self.state = State.TAG_OPEN
                return text_tok
            else:
                self._text_buf += ch
                return None

        # ---- TAG_OPEN: saw '<' ----
        elif s == State.TAG_OPEN:
            if ch == "/":
                self.state = State.END_TAG_OPEN
                self._is_end_tag = True
            elif ch == "!":
                # Could be comment <!-- or DOCTYPE <!
                self.state = State.COMMENT_START
            elif ch is not None and (ch.isalpha() or ch == "_"):
                self._tag_name = ch.lower()
                self._is_end_tag = False
                self._self_closing = False
                self._attrs = {}
                self.state = State.TAG_NAME
            else:
                # Bare '<' that isn't a tag — treat as text
                self._text_buf += "<"
                if ch:
                    self._text_buf += ch
                self.state = State.DATA
            return None

        # ---- TAG_NAME: reading tag name ----
        elif s == State.TAG_NAME:
            if ch is None or ch == ">":
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            elif ch == "/":
                self._self_closing = True
                self.state = State.SELF_CLOSE
            elif ch.isspace():
                self.state = State.BEFORE_ATTR
            else:
                self._tag_name += ch.lower()
            return None

        # ---- END_TAG_OPEN: saw '</' ----
        elif s == State.END_TAG_OPEN:
            if ch is not None and (ch.isalpha() or ch == "_"):
                self._tag_name = ch.lower()
                self.state = State.END_TAG_NAME
            else:
                self.state = State.DATA
            return None

        # ---- END_TAG_NAME ----
        elif s == State.END_TAG_NAME:
            if ch == ">":
                tok = Token(TokenType.END_TAG, tag_name=self._tag_name)
                self._tag_name = ""
                self.state = State.DATA
                return tok
            elif ch is None or ch.isspace():
                self.state = State.BEFORE_ATTR  # whitespace before '>'
            else:
                self._tag_name += ch.lower()
            return None

        # ---- BEFORE_ATTR: whitespace between tag name and attrs ----
        elif s == State.BEFORE_ATTR:
            if ch == ">":
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            elif ch == "/":
                self._self_closing = True
                self.state = State.SELF_CLOSE
            elif ch is not None and not ch.isspace():
                self._cur_attr_name = ch.lower()
                self._cur_attr_val = ""
                self.state = State.ATTR_NAME
            return None

        # ---- ATTR_NAME ----
        elif s == State.ATTR_NAME:
            if ch == "=":
                self.state = State.BEFORE_ATTR_VAL
            elif ch == ">":
                # Boolean attribute (no value)
                self._attrs[self._cur_attr_name] = ""
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            elif ch is None or ch.isspace():
                self._attrs[self._cur_attr_name] = ""
                self.state = State.ATTR_BEFORE_EQ
            elif ch == "/":
                self._attrs[self._cur_attr_name] = ""
                self._self_closing = True
                self.state = State.SELF_CLOSE
            else:
                self._cur_attr_name += ch.lower()
            return None

        # ---- ATTR_BEFORE_EQ: after attr name, looking for '=' ----
        elif s == State.ATTR_BEFORE_EQ:
            if ch == "=":
                self.state = State.BEFORE_ATTR_VAL
            elif ch == ">":
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            elif ch is not None and not ch.isspace():
                # New attribute started without = on previous one
                self._cur_attr_name = ch.lower()
                self.state = State.ATTR_NAME
            return None

        # ---- BEFORE_ATTR_VAL: after '=', looking for quote or value ----
        elif s == State.BEFORE_ATTR_VAL:
            if ch == '"':
                self._cur_attr_val = ""
                self.state = State.ATTR_VALUE_DQ
            elif ch == "'":
                self._cur_attr_val = ""
                self.state = State.ATTR_VALUE_SQ
            elif ch == ">":
                self._attrs[self._cur_attr_name] = ""
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            elif ch is not None and not ch.isspace():
                self._cur_attr_val = ch
                self.state = State.ATTR_VALUE_UQ
            return None

        # ---- ATTR_VALUE_DQ: inside double-quoted attr value ----
        elif s == State.ATTR_VALUE_DQ:
            if ch == '"':
                self._attrs[self._cur_attr_name] = self._cur_attr_val
                self.state = State.BEFORE_ATTR
            elif ch is None:
                self._attrs[self._cur_attr_name] = self._cur_attr_val
            else:
                self._cur_attr_val += ch
            return None

        # ---- ATTR_VALUE_SQ: inside single-quoted attr value ----
        elif s == State.ATTR_VALUE_SQ:
            if ch == "'":
                self._attrs[self._cur_attr_name] = self._cur_attr_val
                self.state = State.BEFORE_ATTR
            elif ch is None:
                self._attrs[self._cur_attr_name] = self._cur_attr_val
            else:
                self._cur_attr_val += ch
            return None

        # ---- ATTR_VALUE_UQ: unquoted attr value ----
        elif s == State.ATTR_VALUE_UQ:
            if ch is None or ch.isspace():
                self._attrs[self._cur_attr_name] = self._cur_attr_val
                self.state = State.BEFORE_ATTR
            elif ch == ">":
                self._attrs[self._cur_attr_name] = self._cur_attr_val
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            else:
                self._cur_attr_val += ch
            return None

        # ---- SELF_CLOSE: saw '/' inside tag ----
        elif s == State.SELF_CLOSE:
            if ch == ">":
                self._self_closing = True
                tok = self._emit_tag()
                self.state = State.DATA
                return tok
            else:
                self.state = State.BEFORE_ATTR
            return None

        # ---- COMMENT_START: saw '<!' ----
        elif s == State.COMMENT_START:
            # Expect '--' for comment, 'D' for DOCTYPE
            if ch == "-":
                self.state = State.COMMENT  # will look for '-->'
                self._comment_buf = ""
            elif ch is not None and ch.upper() == "D":
                self.state = State.DOCTYPE
            else:
                self.state = State.DATA
            return None

        # ---- COMMENT: inside <!-- ... --> ----
        elif s == State.COMMENT:
            if ch == "-":
                self.state = State.COMMENT_END_D1
            elif ch is None:
                self.state = State.DATA
            else:
                self._comment_buf += ch
            return None

        elif s == State.COMMENT_END_D1:
            if ch == "-":
                self.state = State.COMMENT_END_D2
            else:
                self._comment_buf += "-"
                if ch:
                    self._comment_buf += ch
                self.state = State.COMMENT
            return None

        elif s == State.COMMENT_END_D2:
            if ch == ">":
                tok = Token(TokenType.COMMENT, text=self._comment_buf)
                self._comment_buf = ""
                self.state = State.DATA
                return tok
            else:
                self._comment_buf += "--"
                if ch:
                    self._comment_buf += ch
                self.state = State.COMMENT
            return None

        # ---- DOCTYPE: skip until '>' ----
        elif s == State.DOCTYPE:
            if ch == ">" or ch is None:
                self.state = State.DATA
            return None

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _flush_text(self):
        """Return a TEXT token if buffer is non-empty, else None."""
        text = self._text_buf
        self._text_buf = ""
        if text:
            return Token(TokenType.TEXT, text=text)
        return None

    def _emit_tag(self) -> Token:
        """Construct and return a START_TAG or END_TAG token."""
        if self._is_end_tag:
            tok = Token(TokenType.END_TAG, tag_name=self._tag_name)
        else:
            # Void elements are always self-closing regardless of syntax
            is_void = self._tag_name in VOID_ELEMENTS
            tok = Token(
                type=TokenType.START_TAG,
                tag_name=self._tag_name,
                attributes=dict(self._attrs),
                self_closing=self._self_closing or is_void,
            )

        # Reset accumulators
        self._tag_name = ""
        self._is_end_tag = False
        self._self_closing = False
        self._attrs = {}
        self._cur_attr_name = ""
        self._cur_attr_val = ""
        return tok
