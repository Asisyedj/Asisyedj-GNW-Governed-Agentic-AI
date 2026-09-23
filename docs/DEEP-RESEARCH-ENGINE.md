# GNW Deep Research Engine

## Scope

This module adds an OpenAI Deep Research-compatible, read-only research workflow to GNW. It is deliberately bounded by GNW governance rather than bypassing it.

## Mandatory sequence

`PLAN -> CLARIFICATION/ASSUMPTIONS -> PROMPT REWRITE -> GOVERNANCE ADMISSION -> BACKGROUND RESEARCH -> STATUS/POLL -> CITED REPORT -> AUDIT`

A research run cannot start without a persisted plan (`runId`). Tool calls are bounded by `GNW_DEEP_RESEARCH_MAX_TOOL_CALLS`; vector stores are limited to two, matching the current documented Deep Research API constraints.

## API

### Create plan

```http
POST /api/tasks/:taskId/deep-research/plan
X-GNW-Client: web
Content-Type: application/json

{"useModelRewrite":true}
```

### Start research

```http
POST /api/tasks/:taskId/deep-research/start
X-GNW-Client: web
Content-Type: application/json

{
  "runId": 123,
  "allowedDomains": ["nist.gov", "owasp.org"],
  "vectorStoreIds": ["vs_..."],
  "useCodeInterpreter": true,
  "useMcp": false,
  "maxToolCalls": 20,
  "clarificationAnswers": {
    "timeframe": "2026 only"
  }
}
```

### Cancel

```http
POST /api/tasks/:taskId/deep-research/:runId/cancel
```

Cancellation is itself governed and uses the provider Responses cancel endpoint.

### Refresh / retrieve

```http
GET /api/tasks/:taskId/deep-research/:runId
```

The GET route is also a governed status read. It re-reads the provider state when the background response is still queued/in progress.

## Environment

- `GNW_DEEP_RESEARCH_BASE_URL` optional; defaults to `LLM_BASE_URL` or OpenAI `/v1`
- `GNW_DEEP_RESEARCH_API_KEY` optional; defaults to `LLM_API_KEY`
- `GNW_DEEP_RESEARCH_MODEL` default: `o3-deep-research`
- `GNW_DEEP_RESEARCH_MAX_TOOL_CALLS` default: `50`
- `GNW_DEEP_RESEARCH_TIMEOUT_MS` default: `3600000`
- `GNW_DEEP_RESEARCH_USE_CODE_INTERPRETER` default: `true`
- `GNW_DEEP_RESEARCH_ALLOWED_DOMAINS` optional comma-separated GNW domain allowlist
- `GNW_DEEP_RESEARCH_MCP_URL` optional trusted remote MCP endpoint
- `GNW_DEEP_RESEARCH_MCP_LABEL` optional trusted MCP label

The Deep Research endpoint uses `GNW_DEEP_RESEARCH_BASE_URL` and `GNW_DEEP_RESEARCH_API_KEY` when provided, otherwise it falls back to `LLM_BASE_URL` and `LLM_API_KEY`. Production egress must include the configured provider host in `GNW_ALLOWED_EGRESS_HOSTS`.

## Security properties

- Research is bound to the authenticated task, tenant, identity, purpose and classification.
- Web/file/MCP content is treated as untrusted data by the research instructions.
- Research has no provider-job capability and no write-capable external tool.
- Start is fenced/idempotent at the GNW boundary.
- Status reads require a fresh governance grant and a final interlock check.
- Provider response metadata and the final report are persisted to the research run; material transitions are appended to the existing hash-chained audit log.
- The engine fails closed on missing provider configuration, governance denial, interlock activation, invalid vector stores, invalid domain policy, or pending ambiguous external start.

## Current API alignment

The implementation follows the current OpenAI Deep Research Responses API pattern: `o3-deep-research`, `background: true`, `reasoning.summary: "auto"`, web search, optional file search, optional Code Interpreter, optional specialized read-only MCP, and `max_tool_calls`. See the official Deep Research guide and Web Search guide before changing request shapes.


## Client workflow

The Workspace UI exposes the same sequence as explicit controls: create plan, review clarification questions, configure domain/tool policy, admit/start, poll governed status, inspect the final report, and cancel an active run. No client action can skip the server-side plan or governance gates.

## Validation status

The repository includes `tests/deep-research.test.ts` plus the source-level verifier `scripts/verify-deep-research.mjs`. In the provided build environment on 2026-09-23, TypeScript syntax transpilation passed for all touched TypeScript files. A full Vitest run could not be completed because the uploaded archive did not include `node_modules` and dependency installation timed out; this is an environment limitation, not a passing-test claim.
