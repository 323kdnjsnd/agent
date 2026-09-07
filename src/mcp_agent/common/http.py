"""Small, dependency-light HTTP helpers with SSRF and response-size guardrails."""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.request
from urllib.parse import urlparse


class HttpError(RuntimeError):
    """Raised when an external request cannot be completed safely."""


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HttpError("only http(s) URLs are supported")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise HttpError("local URLs are not allowed")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise HttpError(f"cannot resolve host: {host}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HttpError("private or reserved network targets are not allowed")
    return url


def fetch_bytes(url: str, *, max_bytes: int | None = None, timeout: float | None = None) -> bytes:
    validate_public_url(url)
    limit = max_bytes or int(os.getenv("MAX_PDF_BYTES", "25000000"))
    request = urllib.request.Request(url, headers={"User-Agent": "mcp-mining-daily/0.1"})
    try:
        with urllib.request.urlopen(
            request, timeout=timeout or float(os.getenv("HTTP_TIMEOUT_SECONDS", "12"))
        ) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > limit:
                raise HttpError("response exceeds configured size limit")
            data = response.read(limit + 1)
    except HttpError:
        raise
    except Exception as exc:
        raise HttpError(str(exc)) from exc
    if len(data) > limit:
        raise HttpError("response exceeds configured size limit")
    return data


def fetch_text(url: str, *, max_bytes: int = 2_000_000) -> str:
    return fetch_bytes(url, max_bytes=max_bytes).decode("utf-8", errors="replace")
