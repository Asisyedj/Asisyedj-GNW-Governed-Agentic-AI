# GNW Deep Research Implementation — 2026-09-23

## Delivered

The GNW v4 source tree now contains a governed Deep Research workflow with an explicit sequence:

1. Plan creation
2. Clarification questions / explicit assumptions
3. Research prompt rewrite
4. GNW governance admission
5. Background Deep Research request
6. Governed status refresh / polling
7. Provider cancellation
8. Persisted cited report and response metadata
9. Hash-chained audit events

## Provider surface

The implementation targets the OpenAI Responses API Deep Research model configured by `GNW_DEEP_RESEARCH_MODEL`, defaulting to `o3-deep-research`. It can submit web search, optional file search, optional Code Interpreter, and an optional read-only specialized MCP tool. The request uses background execution and a configurable tool-call ceiling.

## GNW controls

- Authenticated task binding is required.
- Purpose and classification are passed through governance admission.
- Research tool capabilities are separate from provider-job/video capabilities.
- External provider execution is fenced and idempotency-keyed at the GNW boundary.
- Status and cancellation use fresh governance admissions.
- Provider and retrieved content are explicitly treated as untrusted data by the research instructions.
- Ambiguous external-start results return `PENDING_RECONCILIATION` instead of blindly retrying.
- Research runs and material transitions are persisted/audited.

## Client

The Workspace UI exposes plan creation, clarification inputs, domain/tool policy, start, live status, report display, and cancel. Server-side gates remain authoritative; the UI cannot bypass them.

## Verification performed

- Static verifier: PASS (`scripts/verify-deep-research.mjs`, 16 checks).
- TypeScript syntax transpilation: PASS for all touched TypeScript/TSX files using TypeScript 5.8.3's `transpileModule`.
- Full Vitest suite: NOT EXECUTED to completion because the supplied archive did not contain a complete `node_modules` tree and dependency installation timed out in the available environment. No full-suite pass is claimed.
- Production provider integration: NOT EXECUTED because it requires a real API key and network access; the implementation is wired for it but was not falsely represented as live-verified.
