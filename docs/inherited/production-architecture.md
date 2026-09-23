# GNW Governed Agent: Production Architecture Baseline

## Inherited baseline

The supplied architecture pack is the conceptual baseline for this product. Its central rule is that model and agent output is untrusted data, while governance is the only authority allowed to admit an action. The pack contributes the role vocabulary, specialist-agent separation, policy-enforcement point, tool gateway, safety interlocks, approval boundary, and audit sequence.

The current product implements those ideas as a full-stack workspace with authenticated users, tenant-scoped tasks, five constrained specialists, a governance control plane, human approvals, durable task records, external artifact references, and a provider-ready video lifecycle. The orchestrator may propose routing but never directly authorizes a tool or provider operation.

## Trust boundaries

| Boundary | Rule | Evidence in product |
|---|---|---|
| User identity | Every protected procedure receives the authenticated session user | Manus OAuth context and `protectedProcedure` |
| Tenant/workspace | Requests carry a tenant/workspace binding and task ownership is checked before access | Task ownership checks and workspace records |
| Orchestrator | Routing output is advisory and cannot bypass governance | `server/governance.ts` admission before specialist execution |
| Specialist agents | Each specialist has a fixed allow-list of tools and a narrow role prompt | `SPECIALIST_AGENTS` and `AGENT_TOOL_SCOPES` |
| Sensitive action | Restricted/provider actions require a persisted approval and a reviewer decision | `approvals` table and approval queue |
| Artifact bytes | Media and packages are stored externally; task records keep references and hashes | `artifacts` table and `storagePut` |
| Audit | Every admission, denial, result, approval, and safety stop is recorded with a hash link | `audit_events` table |

## Evidence boundaries

The original ZIP contained a synthetic local gateway and tests, not a live commercial agent implementation. It did not prove real identity, cryptography, external provider behavior, browser automation, or production deployment. The GNW product therefore treats its current agent outputs as non-authoritative planning data and keeps live provider submission behind explicit approval and a separate job state. Production claims must be supported by the repository tests, database migration, deployment checks, and live acceptance checklist rather than by the original synthetic tests alone.
