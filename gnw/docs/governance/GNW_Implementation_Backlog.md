# GNW Implementation Backlog

**Backlog type:** implementation-ready work breakdown; no item is reported complete merely because source scaffolding exists. Priority: P0 release blocker, P1 pilot, P2 scale/optional.

## Epic E0 — Evidence and provenance foundation

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-001 | P0 | Produce canonical manifest for RC/pass3/source commit | every path, SHA-256, archive, toolchain, environment and owner recorded; duplicate files marked | Git remote/commit/tag currently unknown |
| B-002 | P0 | Obtain signed build/image/SBOM/provenance | digest chain verifies independently; SLSA-style attestation and reviewer key recorded | no current trust root |
| B-003 | P0 | Reconcile all ledger/test denominators | every PASS/BLOCKED/UNPROVEN record maps to claim/test/version; no silent denominator change | conflicting reports |
| B-004 | P1 | Create evidence schema and migration | JSON/SQL schema enforces required lineage fields and status enum | B-001 |

## Epic E1 — Deterministic workflow and state

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-010 | P1 | Implement PostgreSQL task/state tables | typed states/transitions, `tenant_id`, `plan_revision`, generation, timestamps, owner | DB topology/TLS/RLS decision |
| B-011 | P1 | Implement immutable typed DAG/planner proposal | model can propose only schema-valid nodes; policy rejects scope expansion | schema + policy |
| B-012 | P1 | Implement replan and completion predicate | committed nodes freeze; stale writes reject; `done` conjunction enforced | B-010 |
| B-013 | P1 | Add outbox/inbox and idempotent queue consumer | duplicate deliveries produce one state/effect; serialization failures retry safely | queue choice |
| B-014 | P1 | Add checkpoints, worker leases, watchdog, DLQ | crash/restart/cancel tests pass; liveness separated from correctness | ops ownership |
| B-015 | P1 | Implement reconciliation state machine | ambiguous provider result never blind retries; human queue and status lookup | provider contract |

## Epic E2 — Retrieval and evidence

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-020 | P1 | Allowlisted source discovery/query planner | source identity, robots handling, purpose and query bound recorded | target domains/legal rights unknown |
| B-021 | P1 | Quarantined deterministic fetch/parser | final URL/redirects/headers/hash/retrieval/parser/version/locator stored; limits enforced | egress proxy |
| B-022 | P1 | Claim/evidence graph | claim support/partial/contradicted/unproven separate; provenance edges queryable | B-004 |
| B-023 | P1 | Citation verifier | entailment/completeness/applicability/faithfulness outputs; stale/mutated artifact blocks | labeled corpus/oracle absent |
| B-024 | P2 | Domain freshness policy | TTL and semantic update classification per source/domain; 304 not treated as truth | domain owners |

## Epic E3 — Memory/privacy

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-030 | P0 | Replace process-local Map with canonical revision log | durable revisions, states, tenant/purpose/role, timestamps and legal hold | current implementation is Map |
| B-031 | P0 | Build rebuildable search/vector projections | projection carries source revision/ACL/taint; rebuild from canonical log | B-030 |
| B-032 | P0 | Enforce DB RLS and end-to-end tenant context | owner/BYPASSRLS/global paths tested; zero cross-tenant disclosures | live Postgres topology unknown |
| B-033 | P0 | Implement retention/deletion/export/legal hold | deletion across cache/vector/backups/provider request; PRE/POST/FILT audit | legal role/TTL unknown |
| B-034 | P1 | Redact/minimize audit/telemetry | raw prompt/secret/result excluded by default; restricted forensic vault separate | classification policy |

## Epic E4 — Authorization and tools

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-040 | P0 | JSON Schema 2020-12 registry + semantic validator | unknown fields/paths/destinations rejected; normalized action digest stable | schema governance |
| B-041 | P0 | Capability lease/approval service | short TTL, audience, actor/tenant/task/action binding, nonce atomic consume, revocation | key lifecycle/clock policy |
| B-042 | P0 | Execution Gateway and remote sandbox | non-root, seccomp/cgroup, read-only FS, network policy, output/time limits, no `shell=true` host path | hostile-code isolation unproven |
| B-043 | P0 | Governed egress proxy | resolve-bind, redirect revalidate, metadata/private IP deny, approved ports, DNS race tests | live lab absent |
| B-044 | P0 | Provider effect-fence adapter | idempotency/fence/cancel/status contract tested; ambiguous state reconciles | provider contract unknown |
| B-045 | P1 | Approval UI/task card | action preview, digest, freshness, risk, expiry, cancelability and postcondition visible | operator/usability study |

## Epic E5 — Evaluation and operations

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-050 | P0 | Build frozen Urdu/English GNW corpus | labeled claims/spans/contradictions/adversarial cases and locked holdout | domain reviewers |
| B-051 | P0 | Implement deterministic evaluator and independent judge | version-pinned, blinded, leakage-tested; human calibration report | reviewer authority |
| B-052 | P1 | Add OTel-like per-span metrics and billing tags | token/cache/tool/storage/reviewer/USD and p95/p99 reports | provider billing access |
| B-053 | P0 | Execute EV-001–022 in isolated staging | signed results bound to bundle; failures open risk tickets | staging/CI/container blockers |
| B-054 | P0 | Run backup/restore/kill-switch/rollback drills | no resurrection, no duplicate effect, measured propagation/rollback SLO | production-like infra absent |
| B-055 | P1 | Incident runbook and on-call ownership | roles, escalation, evidence preservation, secret rotation and postmortem template | owner unknown |

## Epic E6 — Controlled improvement and release

| ID | Pri | Work item | Acceptance criteria | Dependencies / blocker |
|---|---|---|---|---|
| B-060 | P0 | Immutable promotion bundle | source/prompt/retrieval/tool/workflow/model/evaluator/config/image/dataset digests | B-002/B-003 |
| B-061 | P0 | Independent security/release review | reviewer is separate, authority/key verified, findings closed | external reviewer pending |
| B-062 | P1 | Shadow experiment and canary controller | proposal cannot self-promote; pause thresholds and rollback tested | B-050–054 |
| B-063 | P2 | Multi-agent/council ablation | quality/safety/cost/latency benefit over single-agent statistically supported | defer until baseline |

## Definition of Done

An item is done only when code/config/schema is versioned, threat model updated, tests executed in declared environment, outputs signed and linked to the same bundle, reviewer/owner recorded, rollback path documented and residual risks accepted. “Source primitive exists”, “report says PASS” or “unit intent exists” is not sufficient.

## Recommended first 10 execution steps

1. Freeze canonical archive/commit manifest and reconcile report denominators. 2. Obtain trusted build/SBOM/provenance. 3. Agree workload, legal role, risk tiers and SLO/cost thresholds. 4. Create Postgres state/evidence schema with RLS. 5. Replace process-local memory for the pilot. 6. Implement typed DAG/replan/completion predicate. 7. Build retrieval provenance/citation ledger. 8. Build isolated gateway and live DNS/sandbox lab. 9. Create frozen bilingual corpus and evaluator. 10. Run staging fault/security/restore drills before any external write.

## References

- JSON Schema: https://json-schema.org/draft/2020-12/json-schema-validation
- OWASP SSRF: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- PostgreSQL RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- SLSA: https://slsa.dev/spec/v1.2/build-provenance
- NIST SSDF: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf
- Google SRE canarying: https://sre.google/workbook/canarying-releases/
- NIST AI RMF: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf