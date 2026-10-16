# GNW Evidence Ledger

**Access/inspection date:** 2026-10-17. **Rule:** supplied archives/reports are attributed project evidence, not fresh runtime verification. Identical RC/pass3 files count as one evidence family. Confidence: High/Medium/Low/Unproven.

| Claim ID | Category | Claim statement | Source / type / date | Direct support & version | Corroboration / conflict | Applicability | Confidence / limitation |
|---|---|---|---|---|---|---|---|
| CL-001 | FACT | RC has 1,004 files/231,073,269 bytes; pass3 599/7,743,870; 599 shared, 13 content-different, 405 RC-only, 0 pass3-only. | RC/pass3 ZIP inspection; 2026-10-17 | deterministic archive inventory/hash comparison | no independent archive; reports corroborate | current supplied snapshots | High for archive; not runtime |
| CL-002 | FACT | Selected `src/` 76, `tests/` 28, package manifests/config hashes are identical. | RC/pass3 inspection; 2026-10-17 | SHA-256 comparison | duplicate evidence, not independent | source sameness only | High; does not prove provenance |
| CL-003 | FACT | Git directory/HEAD/branch/signed tag/commit object and ZIP comments absent. | archive inspection; 2026-10-17 | tree/provenance search | no Git metadata | release provenance | High; external repo may exist |
| CL-004 | FACT | Memory backing is process-local `Map`; four tiers and invalidation exist. | snapshot `src/server/tools/memory.ts`; archive | source symbol inspection | both snapshots same; no live rerun | memory prototype | High source fact; durability unknown |
| CL-005 | FACT | Audit has SHA-256 chain, serialization, verification, optional external anchor skeleton. | snapshot audit files/reports | source/report inspection | tamper tests recorded, not rerun | audit integrity | Medium/High; availability/erasure unproven |
| CL-006 | FACT | Health is static process 200; readiness includes report and DB `SELECT 1`. | snapshot app/readiness source | code inspection | no live endpoint call | health semantics | High source fact; deployed config unknown |
| CL-007 | FACT | Capability leases, TTL/action binding, nonce replay, interlock and effect fence with `PENDING_RECONCILIATION` appear in snapshot. | governance/execution source; archive | source symbols | provider-side enforcement absent | authorization/effects | High source fact; operational proof absent |
| CL-008 | FACT | W3C PROV models entities/activities/agents/derivation; RFC 9111 models freshness/revalidation. | W3C PROV-DM/PROV-O; RFC 9111 | direct standards | no conflicting standard | provenance/retrieval | High, but design applicability is inference |
| CL-009 | FACT | Temporal requires deterministic workflow replay and puts nondeterministic calls in Activities; Step Functions supports bounded retry/catch. | official docs | direct documentation | provider semantics vary | orchestration | High for docs; not GNW runtime |
| CL-010 | FACT | OWASP/Microsoft/NIST identify indirect prompt injection, exfiltration, least privilege, SSRF and human approval risks. | official guidance URLs | direct guidance | incidents/research corroborate | agent security | High; controls are not fool-proof |
| CL-011 | FACT | PostgreSQL RLS can default deny but owner/superuser/BYPASSRLS caveats exist; `verify-full` checks hostname. | PostgreSQL docs | direct docs | no conflicting official source | tenant/TLS | High; live topology unknown |
| CL-012 | FACT | Recorded ledgers conflict: `PASS=98/blocked=2`, `91 PASS/2 BLOCKED`, `7 PASS/93 UNPROVEN`, `PASS=0/UNPROVEN=100`. | supplied branch reports | attributed report facts | direct contradiction | release status | High as conflict; denominator unclear |
| CL-013 | INFERENCE | pass3 is curated strict subset, not full repository replacement. | CL-001/002 | logical comparison | 0 pass3-only paths | snapshot interpretation | Medium/High; archive scope assumptions |
| CL-014 | INFERENCE | source sameness cannot transfer build evidence, runtime state or authorization. | CL-002/003/012 | provenance reasoning | differing generated reports | release governance | High reasoning |
| CL-015 | INFERENCE | deterministic outer state + bounded planner is safer default than unconstrained loops. | Temporal/Airflow/Step Functions docs; architecture branch | operational semantics | agent papers show benefits but not safety | GNW design | Medium; GNW benchmark absent |
| CL-016 | INFERENCE | process-local memory cannot prove restart/scale/restore continuity. | CL-004; PostgreSQL/retention guidance | storage mechanism reasoning | no durable schema found | memory governance | High |
| CL-017 | INFERENCE | hash-chain audit is tamper evidence, not erasure/confidentiality/availability. | CL-005; GDPR/NIST guidance | property separation | deletion/retention conflict | privacy/audit | High |
| CL-018 | INFERENCE | heartbeat is liveness, not correctness/authorization; cancellation is not rollback. | Kubernetes/SRE/Temporal docs | semantics | no provider cancel proof | operations | High |
| CL-019 | HYPOTHESIS | typed DAG lowers false completion and improves recovery for GNW tasks. | planning synthesis; ReAct/Temporal docs | plausible mechanism | no GNW ablation | architecture | Low/Medium until measured |
| CL-020 | HYPOTHESIS | canonical revision log + rebuildable index improves deletion/contradiction handling. | memory synthesis; W3C/NIST/OWASP | design rationale | provider/cache surfaces unknown | memory | Medium until tests |
| CL-021 | HYPOTHESIS | single governed agent has better quality/$ than council for GNW. | economics/architecture reports | general cost/quality evidence | hard tasks may benefit from multi-agent | routing | Low until matched benchmark |
| CL-022 | DESIGN DECISION | initial release is read-only; no autonomous external mutation/self-promotion. | master directive + blockers | fail-closed decision | current gate NOT_AUTHORIZED | release | High as selected policy |
| CL-023 | DESIGN DECISION | use Postgres-backed state, immutable plan revisions, outbox/inbox, effect fence/reconciliation. | planning/state branches; PostgreSQL docs | operational pattern | provider exactly-once unknown | durable execution | High design; implementation pending |
| CL-024 | DESIGN DECISION | use claim→span→artifact/version provenance graph and citation support/completeness/faithfulness outputs. | W3C PROV; ALCE/citation research | direct model + synthesis | citation presence insufficient | research | High design |
| CL-025 | DESIGN DECISION | high-impact effects require exact action digest, short lease, human approval, atomic consume, interlock and provider fence. | RFC 6749/9700/9449/7009; OWASP | least privilege/replay standards | provider-side contract absent | permissions | High design |
| CL-026 | DESIGN DECISION | promotion bundle binds source, prompt, retrieval, tool, workflow, model, evaluator, config, image and dataset digests. | NIST SSDF; SLSA; SRE canary | provenance/canary docs | current manifest conflict | release | High design |
| CL-027 | UNKNOWN | canonical Git remote/branch/commit/tag and signed trust root. | archive lacks metadata | absence of evidence | external repo may exist | provenance | Unproven |
| CL-028 | UNKNOWN | live provider behavior, credentials, idempotency/fence/cancel/reconcile and retention. | reports mark unproven | no live call | provider docs not contract | external effects | Unproven |
| CL-029 | UNKNOWN | production DB/RLS/object/cache/vector/queue/log/backups tenant isolation. | snapshot source only | no deployment evidence | `tenant_id` gaps noted | privacy | Unproven |
| CL-030 | UNKNOWN | representative GNW corpus, citation oracle, calibration targets, workload SLO and cost budget. | branch reports | no benchmark | estimates only | evaluation/economics | Unproven |
| CL-031 | UNKNOWN | independent external reviewer authority/key custody and production owner. | release runbook | reviewer pending | owner-signed evidence not independent | governance | Unproven |
| CL-032 | UNKNOWN | hostile-code sandbox, DNS/socket hardening, signed SBOM/image and restore anti-resurrection. | security/infrastructure branches | blockers explicitly listed | static tests insufficient | security/recovery | Unproven |

## Source Register

| Source ID | Source | Type / use |
|---|---|---|
| S-01 | `/home/ubuntu/upload/pasted_content.txt` | master directive; scope/protocol; not external proof |
| S-02 | `/home/ubuntu/projects/gnw-73640542/GNW_RELEASE_CANDIDATE_2026-09-30.zip` | supplied snapshot; archive/source evidence |
| S-03 | `/home/ubuntu/projects/gnw-73640542/GNW_PASS3_CONTINUED_2026-09-30.zip` | supplied snapshot; archive/source evidence |
| S-04 | W3C PROV-DM/PROV-O: https://www.w3.org/TR/prov-dm/ ; https://www.w3.org/TR/prov-o/ | provenance standards |
| S-05 | RFC 9111: https://www.rfc-editor.org/rfc/rfc9111.html | cache freshness/revalidation |
| S-06 | Temporal: https://docs.temporal.io/workflow-definition ; https://docs.temporal.io/workflow-execution | deterministic durable workflows |
| S-07 | OWASP SSRF/Agent: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html ; https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html | tool/authorization controls |
| S-08 | PostgreSQL: https://www.postgresql.org/docs/current/ddl-rowsecurity.html ; https://www.postgresql.org/docs/current/libpq-ssl.html | RLS/TLS |
| S-09 | NIST AI RMF/SSDF: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf ; https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf | lifecycle/release |
| S-10 | SLSA: https://slsa.dev/spec/v1.2/build-provenance | provenance |
| S-11 | NIST CAISI / AgentDojo: https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations ; https://arxiv.org/abs/2406.13352 | hijacking evaluation |
| S-12 | Google SRE: https://sre.google/sre-book/monitoring-distributed-systems/ ; https://sre.google/workbook/canarying-releases/ | monitoring/canary |
| S-13 | GDPR: https://eur-lex.europa.eu/eli/reg/2016/679/oj | privacy obligations |
| S-14 | OpenAI evals / Anthropic evals: https://developers.openai.com/api/docs/guides/evals ; https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | evaluator limitations |

**Access date for web sources:** 2026-10-17 (as recorded by branch research). **Limitation:** this synthesis does not independently re-fetch every source; branch reports document their use. Web citations support general principles, not GNW deployment state.