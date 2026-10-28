---
name: perplexity-bridge
description: Route and orchestrate queries across 84 frontier models via the GNW Perplexity Bridge MCP server, with cryptographic audit trails, fail-safe circuit breaking, and sub-1.5s routing.
---

# GNW Perplexity Frontier Model Bridge

Provides direct, governed access to the multi-model cognitive swarm via the local MCP server running on Python environment `D:\GNW\perplexity-browser-api\.venv\Scripts\python.exe`.

## Capabilities
- **Frontier Reasoning Models**: Claude 3.7 Sonnet Thinking, Claude 4.5 Sonnet, Claude 5 Thinking, GPT-5.4/5.6-sol Thinking, Grok 4.7 Reasoning, Gemini 3.7 Flash Thinking, Kimi K2.6 Thinking.
- **Circuit-Breaker Protected**: Auto-fallback and health check verification before dispatch.
- **Zero-Bypass Governance**: Local stdio transport strictly bounds model execution.

## Tool Routing Reference
Use `call_mcp_tool` with server `perplexity-models`:
- `perplexity_bridge_health`: Verify localhost bridge daemon liveness.
- `perplexity_list_models`: Enumerate the 84 active catalog models.
- `perplexity_ask`: Query specific model with `{"model": "...", "prompt": "...", "system_message": "..."}`.
- `gnw_read_file`, `gnw_write_file`, `gnw_list_files`: Governed workspace file tools.
