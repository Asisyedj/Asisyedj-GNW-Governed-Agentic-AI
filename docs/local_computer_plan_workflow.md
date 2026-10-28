# GNW local Computer-task planner

This is a privacy-oriented fallback when Perplexity Computer mode is unavailable. It uses a **model already installed in local Ollama** to turn a task into a JSON plan. It does not send the task to Perplexity or Ollama Cloud, and it does not click, type, submit, run scripts, or perform computer actions.

Ollama documents a local chat API at `http://localhost:11434/api/chat`, supports JSON Schema through its `format` field, and exposes installed model metadata through `GET /api/tags`. Local API requests do not require authentication. This implementation fixes the target to `127.0.0.1`, disables environment proxies and redirects, checks the model is installed, and blocks names or model metadata marked as cloud/remote. [1] [2] [3] [4]

## Workflow

1. The user calls `POST http://127.0.0.1:8011/v1/plan` with a single task string.
2. The service validates the request, selects only the server-configured `GNW_LOCAL_OLLAMA_MODEL`, checks Ollama's local model list, then requests a schema-constrained plan from the local model.
3. The service validates the returned JSON and labels every step `requires_user_approval: true`. It returns `executed: false` and `approval_required: true` regardless of what the model says.
4. A person reviews the plan. If actual desktop work is needed, the human can relay the approved, bounded step to an authorized local Computer Use tool and pause between UI observations. This Python service is not wired to a desktop-control MCP and cannot perform the work itself.

This is a **local AI planning fallback**, not a drop-in Perplexity Computer clone. It does not provide browser search, image understanding, private Computer APIs, automatic UI control, or live Perplexity results. The quality depends on the local model and hardware.

## Local setup and use

Prerequisites: Ollama is installed and running locally, and a local model is already present in `ollama list`. The service does not download models. Choose an installed local model name; do not select a model tagged as cloud/remote. From the repository root in a Python environment with the project dependencies installed, set the model and start the loopback service:

```powershell
$env:GNW_LOCAL_OLLAMA_MODEL='qwen3:8b'; python -m personal_agent.agent.local_computer_planner
```

The example model name is illustrative only. Replace it with the exact name returned by local `ollama list`. The service listens on `127.0.0.1:8011` and accepts loopback clients only. It does not expose the API to the LAN.

Send one task to the local model:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8011/v1/plan -ContentType 'application/json' -Body '{"task":"Open the Perplexity app and describe the visible Computer-mode controls. Do not send a prompt or change settings."}'
```

A successful response has `status: pending_human_review`, `approval_required: true`, and `executed: false`. The plan is untrusted model output and must be checked before anyone carries it out. Request bodies and model responses are not written to files by this service.

If the configured model is missing, marked as remote/cloud, or Ollama is not running, the route fails closed with a bounded error. It never falls back to the Perplexity provider gateway. The local Ollama API itself has no authentication, so keep Ollama bound to loopback and do not expose this service on a public or LAN interface. [4]

## Test without an Ollama install or model call

The tests use `httpx.MockTransport`; they do not contact local Ollama, Perplexity, or another model. Run them in an environment with the project/test dependencies installed:

```powershell
python -m pytest personal_agent\tests\test_local_computer_planner.py -q -p no:cacheprovider
```

## Files

- `personal_agent/agent/local_computer_planner.py` — loopback-only local planner service.
- `personal_agent/tests/test_local_computer_planner.py` — offline contract and safety tests.
- `personal_agent/agent/provider_gateway.py` — separate official Perplexity API gateway. Its `/v1/computer` remains an explicit HTTP 501; this local planner does not change it.

## References

[1]: https://docs.ollama.com/api/chat "Ollama chat API"
[2]: https://docs.ollama.com/capabilities/structured-outputs "Ollama structured outputs"
[3]: https://docs.ollama.com/api/tags "Ollama model-list API"
[4]: https://docs.ollama.com/api/authentication "Ollama API authentication"
