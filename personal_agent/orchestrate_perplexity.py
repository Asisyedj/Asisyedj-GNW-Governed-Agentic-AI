# orchestrate_perplexity.py
"""Orchestrate multiple Perplexity models without using Antigravity models.

This script:
1. Lists available Perplexity models via the `perplexity_list_models` MCP tool.
2. Spawns a lightweight sub‑agent for each selected model.
3. Sends a common user question to every sub‑agent. Each sub‑agent calls
   `perplexity_ask` (via the MCP bridge) using the model it was assigned.
4. Collects the answers and prints a concise summary.

No Antigravity LLM is used – only the Perplexity bridge tools.
"""

import asyncio
import json
import os
from pathlib import Path

# ----------------------------------------------------------------------
# Helper – thin wrapper around the Perplexity MCP tools
# ----------------------------------------------------------------------
async def call_mcp(server: str, tool: str, args: dict) -> dict:
    """Call a lazy‑loaded MCP tool and return the parsed JSON result.

    The runtime provides the `call_mcp_tool` function as a tool.
    """
    from functions import call_mcp_tool  # injected by the Antigravity runtime
    # The tool returns a dict already (its JSON is parsed for us).
    result = await call_mcp_tool({
        "ServerName": server,
        "ToolName": tool,
        "Arguments": args,
    })
    return result

# ----------------------------------------------------------------------
# Step 1 – discover available Perplexity models
# ----------------------------------------------------------------------
async def list_perplexity_models() -> list[str]:
    resp = await call_mcp("perplexity-models", "perplexity_list_models", {})
    # Expected shape: {"models": ["gpt-4-turbo", "claude-sonnet-3.5", ...]}
    return resp.get("models", [])

# ----------------------------------------------------------------------
# Sub‑agent system prompt – each sub‑agent runs this small loop.
# ----------------------------------------------------------------------
_SUBAGENT_SYSTEM_PROMPT = """You are a lightweight Perplexity worker.
Your job is to answer a single user question using a specific Perplexity model.
The model name will be passed to you in the incoming message JSON under the key `model`.
When you receive a message, call the `perplexity_ask` tool with:
    {\"model\": \"<model-name>\", \"question\": \"<user-question>\"}
and reply with the raw answer string (no extra framing)."""

# ----------------------------------------------------------------------
# Orchestration logic – run in the *parent* agent
# ----------------------------------------------------------------------
async def run_orchestration(user_question: str) -> None:
    # 1️⃣ List models
    all_models = await list_perplexity_models()
    # Choose a few models – adjust this filter as you like.
    desired_models = [m for m in all_models if m.startswith(("gpt-4", "claude-sonnet"))][:3]
    if not desired_models:
        print("❌ No matching Perplexity models found.")
        return

    # 2️⃣ Ask each model directly (concurrently) – no sub‑agents required.
    async def ask_model(model_name: str) -> tuple[str, str]:
        resp = await call_mcp(
            "perplexity-models",
            "perplexity_ask",
            {"model": model_name, "question": user_question},
        )
        # Expected response shape: {"answer": "..."}
        answer = resp.get("answer", "<no answer>")
        return model_name, answer

    # Run all queries in parallel
    results = await asyncio.gather(*(ask_model(m) for m in desired_models))

    # 3️⃣ Print a tidy summary
    print("\n=== Perplexity Multi‑Model Summary ===")
    for model, ans in results:
        print(f"\n--- {model} ---\n{ans.strip()}\n")

# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python orchestrate_perplexity.py \"Your question here\"")
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    asyncio.run(run_orchestration(question))
