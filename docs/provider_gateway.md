# GNW provider gateway

This is an optional, separate local service. It does not replace or modify `bridge_daemon.py` or the existing browser-session scraper. It binds to loopback (`127.0.0.1:8010`) and only accepts loopback clients. Provider authentication uses the official Perplexity API key from the server environment variable `PERPLEXITY_API_KEY`; the value is never printed by this module.

Start from the repository root:

```powershell
python -m personal_agent.agent.provider_gateway
```

The gateway has these routes:

- `POST /v1/orchestrator/chat/completions` forwards the OpenAI Chat Completions JSON shape to the official Orchestrator route. Required fields: non-empty `model` and non-empty `messages` array. Streaming is intentionally rejected in this first version.
- `POST /v1/agent` forwards a documented Agent API request to `/v1/agent`. Required fields: non-empty `model` and `input`. Streaming is intentionally rejected in this first version.
- `POST /v1/search` forwards a Search API request to `/search`. Required field: non-empty `query`.
- `POST /v1/custom/dispatch` selects one of the three fixed official routes with `{"route":"orchestrator|agent|search","payload":{...}}`. It accepts no arbitrary upstream URL.
- `POST /v1/computer/plan` accepts exactly `{"model":"...","task":"..."}` and sends a plan-only text request to the fixed official Orchestrator route. It returns `executed: false`, `approval_required: true`, and `untrusted_model_output: true`. This does not control a desktop and is not automatically connected to Perplexity's UI.
- `POST /v1/computer` returns HTTP 501 `computer_control_api_unavailable`. This is an explicit boundary, not desktop automation: no public Perplexity Computer-control API was established in the referenced docs.
- `GET /health` reports local service status only and does not call a provider.

All provider calls are fixed to `https://api.perplexity.ai`; redirects and environment proxies are disabled. No live provider request is sent by the offline tests. Configure and use a valid API key locally before making any intentional paid API request. Orchestrator API access is documented as private preview; access may need to be enabled by Perplexity.

## Example local requests

```powershell
# Orchestrator model call
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/v1/orchestrator/chat/completions `
  -ContentType 'application/json' `
  -Body '{"model":"perplexity/kimi-k3","messages":[{"role":"user","content":"Hello"}]}'

# Agent API call
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/v1/agent `
  -ContentType 'application/json' `
  -Body '{"model":"openai/gpt-5.6-sol","input":"Hello"}'

# Search API call
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/v1/search `
  -ContentType 'application/json' `
  -Body '{"query":"Perplexity API documentation","max_results":3}'
```

These examples send prompts and can incur API charges when used with a valid key. They are documentation only; they were not executed during implementation. Model IDs and access vary by API entitlement and catalog.

## Computer-task text fallback

The new route is a **manual, text-only fallback** for asking an official Perplexity model to propose steps. The task text is sent to Perplexity's hosted API, so do not include passwords, cookies, session tokens, private conversation content, or other data you do not want sent to that provider. A valid API key and an account-enabled model are required; usage may incur API charges. The response is untrusted text for human review, and no desktop/browser action is performed.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/v1/computer/plan `
  -ContentType 'application/json' `
  -Body '{"model":"MODEL_FROM_YOUR_ENABLED_CATALOG","task":"Describe a safe, manual plan to inspect the visible Computer-mode controls. Do not submit prompts or change settings."}'
```

The endpoint forwards to `/orchestrator/v1/chat/completions`; it does not discover or invoke a hidden Computer-mode endpoint. An upstream 503 is returned as a 503, not replaced with a fabricated plan.

## Offline test

From the repository root and with the intended virtual environment active, install the project and test extra:

```powershell
python -m pip install -e ".[test]"
python -m pytest personal_agent\tests\test_provider_gateway.py -q -p no:cacheprovider
```

The tests use `httpx.MockTransport` and do not call Perplexity. The earlier eight-test baseline passed under the system Python. Four tests now cover the Computer-task plan route, but the updated twelve-test suite has not been run in this revision because the local terminal could not initialize (`config home unavailable`); no package installation or live provider request was performed.

## Official references

- [API overview](https://docs.perplexity.ai/)
- [Orchestrator quickstart](https://docs.perplexity.ai/docs/router/quickstart)
- [Agent API quickstart](https://docs.perplexity.ai/docs/agent-api/quickstart)
- [Search API quickstart](https://docs.perplexity.ai/docs/search/quickstart)
