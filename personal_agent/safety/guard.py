"""Safety guardrails for the agent.

Provides a simple regex‑based profanity/jailbreak filter and a helper to sanitize LLM output.
"""

from __future__ import annotations

import re
from typing import List

# A tiny whitelist of disallowed patterns – in a real system this would be a comprehensive list.
DISALLOWED_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)\b(?:kill|shutdown|self[-_]destruct|execute\s+malicious)\b"),
    re.compile(r"(?i)\b(?:password|secret|api\s*key)\b"),
]


def is_safe(text: str) -> bool:
    """Return ``True`` if *text* contains none of the disallowed patterns.

    The function is deliberately simple – it can be swapped for a ML classifier.
    """
    for pat in DISALLOWED_PATTERNS:
        if pat.search(text):
            return False
    return True


def guard_output(text: str) -> str:
    """Validate *text* and raise ``PermissionError`` if unsafe.

    Used by the LLM wrapper and the planner before returning data to the user.
    """
    if not is_safe(text):
        raise PermissionError("Generated content violated safety policy")
    return text
