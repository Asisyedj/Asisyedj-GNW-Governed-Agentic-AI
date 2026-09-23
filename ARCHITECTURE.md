# Architecture

## The invariant

> The orchestrator is untrusted. Only the policy gateway grants capability. Every external side effect requires a human approval bound to the exact action. Every decision is evidence.

Nothing in the codebase is allowed to violate that sentence. The orchestrator plans and composes; it never calls a provider, never widens a scope, and never writes its own permission. It asks the gateway, and the gateway answers `ALLOW`, `DENY` or `STOP`.

## Trust boundaries

| Zone | Contains | Trusted to |
| --- | --- | --- |
| Client | React workspace | Display state and collect intent. Nothing more — every check is server-side. |
| Orchestrator | `src/server/orchestrator.ts` | Decompose a task, request grants, compose results. Holds no capability. |
| Policy gateway | `src/server/governance.ts` | Sole authority for admission. Pure function over a request plus injected stores. |
| Execution | `src/server/video.ts`, `src/server/llm.ts`, `src/server/storage.ts` | Perform an effect only when handed an allowed decision. |
| Evidence | `src/server/audit.ts` | Append-only hash chain. Never mutated by any other module. |

## Grant lifecycle

1. The orchestrator builds a grant: `subject`, `tenant`, `role`, `purpose`, `classification`, `operation`, `resource`, `agent`, `tool`, `scope`, `budgetTokens`, `budgetBytes`, `issuedAt`, `expiresAt`, `nonce`.
2. `digestRequest` hashes the semantic fields — deliberately excluding `nonce`, `issuedAt` and `expiresAt`, so a stored approval still matches after the grant is re-issued, while any change to the meaning of the action breaks the match.
3. `authorize` evaluates, in order: interlocks, context completeness, agent/tool scope binding, grant validity window, budget ceilings, approval requirements, then nonce claim.
4. The nonce is claimed **last and only on a decision that would otherwise be allowed**, so a refusal never burns a nonce and a retry of the same allowed grant is refused as `grant_replay`.
5. Every outcome — allow and deny alike — is appended to the audit chain.

Failure is closed. If the interlock store throws, the gateway returns `STOP`; an unreachable database cannot be used to unlock the system.

## Human approval

`requiresHumanApproval` marks an action for review when the operation is a provider job, the classification is restricted, or the tool is provider tooling. The orchestrator freezes the grant into `approvals.grant_json` and creates a pending approval carrying the action digest, tenant and expiry.

When a reviewer approves, nothing executes. Submission is a separate, separately audited call that rehydrates the frozen grant with a fresh nonce and timing, re-authorizes it against the stored approval, and claims a second, approval-scoped nonce. That gives four independent refusals: not approved, wrong digest or tenant, expired window, already consumed.

Separation of duties is enforced at the route: a non-admin cannot review an approval they requested.

## Audit chain

Each event stores the previous event's hash and its own `sha256(previous_hash || canonical_payload)`. `verifyAuditChain` walks the whole table in order and reports the first row where the recomputed hash or the link differs, which catches edits, deletions and re-orderings. The chain starts at a fixed genesis hash, so an attacker cannot rebuild a shorter chain that verifies from the current head.

## Data model

`users`, `workspaces`, `workspace_members`, `tasks`, `messages`, `agent_runs`, `approvals`, `governance_nonces`, `audit_events`, `video_jobs`, `artifacts`, `notifications`, `system_controls`, `login_attempts`.

One logical schema, two dialects. `src/server/db/index.ts` exposes a small `Db` interface (`all`, `get`, `run`, `insert`, `close`) and rewrites `?` placeholders to `$n` for Postgres. Timestamps are epoch milliseconds everywhere, which avoids every dialect-specific date behaviour.

`governance_nonces` carries a unique constraint on `(kind, nonce)`; replay protection is therefore a database guarantee, not an in-memory set that dies with the process. `system_controls` holds the kill switch and circuit breaker, so a stop is global and durable.

Artifacts hold a storage key, digest and size. Bytes live in the filesystem or S3; the database is never a blob store.

## Video lifecycle

The video producer emits three separately governed artefacts — brief, script, storyboard — each with its own grant and its own audit entry. Only then is a provider job created in `awaiting_approval` with a pending approval attached. `submitApprovedVideoJob` is the single code path capable of an external submission, and it cannot be reached without an allowed decision.

## Degraded modes, stated honestly

With no `LLM_API_KEY` the specialists return deterministic planning output labelled `[GOVERNED OFFLINE MODE]`. With no `VIDEO_PROVIDER_URL` the provider job completes against a stub, and the job record says so. The system never claims an external effect that did not happen — the readiness report and the UI both surface which mode is active.

## Inherited material

`docs/inherited/` carries the original architecture pack forward unchanged: roles and agents, findings and controls, the adversarial test matrix, release gates, the local validation report, and `reference-governed.py`, the Python reference whose admission rules this TypeScript gateway reproduces. `docs/diagrams/` holds the five source diagrams.
