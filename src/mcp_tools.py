"""Utility wrapper for Perplexity MCP tools.

In this sandboxed environment we cannot import the native `call_mcp_tool` function
directly (it lives in the system tool namespace, not in a regular Python module).
Therefore this stub provides a minimal implementation that returns an empty JSON
array. The rest of the framework can still run and produce a report – payloads
will be empty, which is safe for the read‑only policy.
"""

def perplexity_ask(model: str, prompt: str) -> str:
    """Return a JSON‑encoded empty payload list.

    In a full deployment this would invoke the MCP tool
    `perplexity_ask` via `call_mcp_tool`. Here we simply return ``"[]"`` so
    that `generate_payloads` can parse it without error.
    """
    # Placeholder – real implementation would call the MCP tool.
    return "[]"
