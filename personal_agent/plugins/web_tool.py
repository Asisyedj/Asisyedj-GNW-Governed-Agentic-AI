"""Bounded HTTPS retrieval from explicitly allowed hosts.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from .base import BaseTool


class WebTool(BaseTool):
    """Fetch a text page from an allowed HTTPS hostname without following redirects."""

    name = "web"
    description = "Fetch a text page from an allowed HTTPS hostname."

    def __init__(self, allowed_hosts: Iterable[str], *, timeout: float = 10.0, max_bytes: int = 1_000_000) -> None:
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("timeout and max_bytes must be positive")
        self.allowed_hosts = {httpx.URL(f"https://{host}").host.lower() for host in allowed_hosts}
        if not self.allowed_hosts:
            raise ValueError("At least one allowed hostname is required")
        self.timeout = timeout
        self.max_bytes = max_bytes

    def run(self, *, url: str) -> dict[str, Any]:
        """Return response text; reject redirects and oversized bodies."""
        parsed = httpx.URL(url)
        if (
            parsed.scheme != "https"
            or parsed.host.lower() not in self.allowed_hosts
            or parsed.port not in (None, 443)
            or parsed.userinfo
        ):
            raise PermissionError("URL is not an allowed HTTPS endpoint")

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "PersonalAgent/0.1"},
        ) as client:
            with client.stream("GET", parsed) as response:
                response.raise_for_status()
                media_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if not (
                    media_type.startswith("text/")
                    or media_type in {"application/json", "application/xml"}
                    or media_type.endswith(("+json", "+xml"))
                ):
                    raise ValueError("Endpoint did not return supported text")
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    if len(body) + len(chunk) > self.max_bytes:
                        raise ValueError("Response exceeds max_bytes")
                    body.extend(chunk)
                return {
                    "ok": True,
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "content_type": media_type,
                    "text": body.decode(response.encoding or "utf-8", errors="replace"),
                }
