"""
net/http.py — Raw HTTP/1.0 fetcher over a plain TCP socket.

No external dependencies. Teaches you exactly what a browser sends
and receives at the wire level.
"""

import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urljoin


@dataclass
class HTTPResponse:
    status_code: int
    status_text: str
    headers: dict
    body: str
    url: str


class HTTPError(Exception):
    pass


def fetch(url: str, timeout: float = 10.0, max_redirects: int = 5) -> HTTPResponse:
    """
    Fetch a URL over a raw TCP socket using HTTP/1.0.
    Follows redirects up to max_redirects times.

    Returns an HTTPResponse with the decoded body.
    Raises HTTPError on network or protocol failures.
    """
    if max_redirects < 0:
        raise HTTPError("Too many redirects")

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    if scheme not in ("http", ""):
        raise HTTPError(
            f"Unsupported scheme '{scheme}'. "
            "This engine only supports plain HTTP for now."
        )

    host = parsed.hostname or ""
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    if not host:
        raise HTTPError(f"Could not parse host from URL: {url!r}")

    # ------------------------------------------------------------------
    # Open a raw TCP socket and send an HTTP/1.0 GET request.
    # HTTP/1.0 is simpler than 1.1: no chunked encoding, no keep-alive.
    # ------------------------------------------------------------------
    raw_request = (
        f"GET {path} HTTP/1.0\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: ToyBrowser/0.1 (educational)\r\n"
        f"Accept: text/html\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError as e:
        raise HTTPError(f"Could not connect to {host}:{port} — {e}") from e

    try:
        sock.sendall(raw_request.encode("utf-8"))

        # Read the full response into memory.
        # Real browsers stream this; we buffer for simplicity.
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError as e:
        raise HTTPError(f"Socket error while reading response — {e}") from e
    finally:
        sock.close()

    raw_response = b"".join(chunks)

    response = _parse_response(raw_response, url)

    # Handle redirects (301, 302, 303, 307, 308)
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("location")
        if location:
            # Resolve relative redirect URLs against the current URL
            next_url = urljoin(url, location)
            return fetch(next_url, timeout, max_redirects - 1)

    return response


def _parse_response(raw: bytes, url: str) -> HTTPResponse:
    """
    Split raw HTTP response bytes into status line, headers, and body.

    HTTP responses look like:
        HTTP/1.0 200 OK\r\n
        Content-Type: text/html\r\n
        \r\n
        <html>...</html>
    """
    # Headers and body are separated by a blank line (\r\n\r\n).
    if b"\r\n\r\n" in raw:
        header_section, body_bytes = raw.split(b"\r\n\r\n", 1)
    elif b"\n\n" in raw:
        # Some servers use bare \n instead of \r\n (non-compliant but common).
        header_section, body_bytes = raw.split(b"\n\n", 1)
    else:
        raise HTTPError("Could not find header/body separator in response.")

    # Decode headers as ASCII (they must be ASCII per spec).
    try:
        header_text = header_section.decode("ascii", errors="replace")
    except Exception as e:
        raise HTTPError(f"Failed to decode response headers: {e}") from e

    lines = header_text.split("\n")
    status_line = lines[0].strip()

    # Parse: HTTP/1.0 200 OK
    parts = status_line.split(" ", 2)
    if len(parts) < 2:
        raise HTTPError(f"Malformed status line: {status_line!r}")

    try:
        status_code = int(parts[1])
    except ValueError:
        raise HTTPError(f"Non-integer status code: {parts[1]!r}")

    status_text = parts[2] if len(parts) > 2 else ""

    # Parse headers into a dict (lowercase keys for easy lookup).
    headers = {}
    for line in lines[1:]:
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()

    # Decode body. Try charset from Content-Type, fall back to utf-8.
    charset = _extract_charset(headers.get("content-type", ""))
    try:
        body = body_bytes.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        body = body_bytes.decode("utf-8", errors="replace")

    return HTTPResponse(
        status_code=status_code,
        status_text=status_text,
        headers=headers,
        body=body,
        url=url,
    )


def _extract_charset(content_type: str) -> str:
    """
    Extract charset from a Content-Type header value.
    e.g. 'text/html; charset=utf-8' → 'utf-8'
    """
    for part in content_type.split(";"):
        part = part.strip()
        if part.lower().startswith("charset="):
            return part[8:].strip().strip('"')
    return "utf-8"
