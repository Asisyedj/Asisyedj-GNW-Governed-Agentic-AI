# GNW Architecture Decisions (ADRs)

**Decision status:** design decisions only; implementation/deployment not performed.

## ADR-001 — Deterministic spine with bounded agent proposal

- **Problem:** free-running agents can loop, overreach, misreport completion and complicate replay.
- **Context:** Temporal/Airflow/Step Functions document explicit durable state/retry semantics; ReAct/multi-agent research shows capability gains but not authorization or production safety. GNW reports lack workload ablation.
- **Options:** A deterministic dossier; B deterministic workflow + bounded single agent; C multi-agent council.
- **Evidence:** https://docs.temporal.io/workflow-definition ، https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html ، https://arxiv.org/abs/2210.03629 ۔
- **Decision:** choose B; use A for fixed release/compliance dossiers; defer C.
- **Trade-offs:** B adds model uncertainty and evaluator cost but preserves control; A may underperform on open-ended retrieval; C adds repeated context, coordination and authority surface.
- **Rejected alternative:** C as default.
- **Validation plan:** matched A/B/C benchmark on citation quality, false completion, injection resistance, p95 and cost.
- **Revisit trigger:** measured bottleneck plus statistically meaningful safety/quality gain within budget.

## ADR-002 — PostgreSQL-backed durable state machine

- **Problem:** process-local state, duplicate delivery, stale workers and crash recovery.
- **Context:** current memory is `Map`; snapshot has in-memory invariants and effect-fence skeleton; PostgreSQL provides transactions/RLS but deployment is absent.
- **Options:** in-memory; custom Postgres queue/state; Temporal-class durable workflow.
- **Decision:** Postgres canonical task/evidence/effect state with outbox/inbox and typed plan revisions; adopt Temporal-class engine if measured duration/fan-out justifies.
- **Trade-offs:** operational DB complexity vs replay/audit/recovery; exactly-once external effects still require provider fence.
- **Validation:** EV-001, 002, 003, 010, 011; serialization failure retry; restore drill.
- **Revisit:** sustained fan-out/duration, recovery SLO failure or operations burden.

## ADR-003 — Typed immutable plan revisions

- **Problem:** model-generated plans become authority; replanning can overwrite committed work.
- **Decision:** `plan_revision(n+1)` immutable; committed nodes freeze; stale revision/fence writes reject; scope/budget/capability expansion requires approval.
- **Trade-offs:** more records and reconciliation; safer audit and replay.
- **Validation:** stale-plan race, cancel/replan, completion predicate tests.
- **Revisit:** none without evidence; schema may evolve compatibly.

## ADR-004 — Claim-to-evidence provenance graph

- **Problem:** bibliography/citation presence does not prove support or freshness.
- **Evidence:** W3C PROV-DM/PROV-O, RFC 9111, ALCE/citation-faithfulness research: https://www.w3.org/TR/prov-dm/ ، https://www.w3.org/TR/prov-o/ ، https://www.rfc-editor.org/rfc/rfc9111.html ۔
- **Decision:** bind claim to exact source artifact hash, locator/span, final URL/redirects, headers, retrieval time, parser/version, query/run and representation version; output support, completeness, applicability, provenance and faithfulness separately.
- **Trade-offs:** storage/parser complexity; enables audit and correction.
- **Validation:** source mutation, parser disagreement, stale 304, contradiction and citation holdout tests.
- **Revisit:** domain-specific semantic freshness or legal retention changes.

## ADR-005 — Canonical memory log plus rebuildable projection

- **Problem:** current process-local Map does not provide durable continuity or end-to-end erasure.
- **Decision:** relational append-only revision log with `ACTIVE/REVOKED/SUPERSEDED/DELETED/LEGAL_HOLD`; vector/search index is rebuildable projection; authorization checked before retrieval.
- **Trade-offs:** reindex/retention work; lower accidental resurrection risk than unmanaged vector-only memory.
- **Validation:** EV-008/009/016; paired PRE/POST/FILT forgetting audit; backup restore anti-resurrection.
- **Revisit:** scale/index SLA or legal requirements.

## ADR-006 — Authorization-first Execution Gateway

- **Problem:** prompt/model output and tool responses are untrusted; local lease alone cannot control provider effects.
- **Evidence:** OWASP SSRF/agent guidance, RFC 9700/9449, JSON Schema 2020-12: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html ، https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html ۔
- **Decision:** schema + semantic validation, tenant/actor/task/action/destination binding, short signed lease, explicit approval for high risk, atomic consume, final interlock, proxy/sandbox, idempotency/fence and reconciliation.
- **Trade-offs:** latency and false denies; blocks unauthorized effects.
- **Validation:** EV-004–007, 011; provider staging contract.
- **Revisit:** provider contract/API changes or measured false-deny burden.

## ADR-007 — `PENDING_RECONCILIATION` over blind retry

- **Problem:** timeout/partition can follow a committed external mutation.
- **Decision:** ambiguous effects become pending; query status/ledger or human reconcile; never blind retry mutation without proven idempotency.
- **Evidence:** AWS Builders’ Library and Stripe idempotency guidance: https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ ، https://docs.stripe.com/api/idempotent_requests ۔
- **Trade-offs:** slower recovery/manual queue; prevents duplicate effects.
- **Validation:** delayed response, lost response, provider status mismatch.
- **Revisit:** provider gives independently verified monotonic fence/idempotency semantics.

## ADR-008 — Layered independent evaluation

- **Problem:** LLM judge self-preference/verbosity/position bias; self-review is not independent assurance.
- **Decision:** deterministic invariants + frozen holdout + version-pinned independent evaluator + blinded human calibration; model judge advisory only.
- **Evidence:** NIST AI RMF, Anthropic eval guidance, Zheng et al.; https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf ۔
- **Trade-offs:** reviewer cost and slower release; lower false confidence.
- **Validation:** EV-013, evaluator-bug and leakage tests, inter-rater agreement.
- **Revisit:** calibrated evidence across workload/model changes.

## ADR-009 — Proposal-only controlled improvement

- **Problem:** self-modification can bypass regression/security/release governance.
- **Decision:** immutable bundle proposal → isolated experiment → regression/security → independent review → canary → per-version monitor → rollback. Agent cannot self-promote or mint authority.
- **Evidence:** NIST SSDF, SLSA, Google SRE canary/rollback: https://slsa.dev/spec/v1.2/build-provenance ، https://sre.google/workbook/canarying-releases/ ۔
- **Trade-offs:** slower iteration; auditable reversible change.
- **Validation:** provenance, holdout, canary and semantic rollback drills.
- **Revisit:** only with external authority and measured process maturity.

## ADR-010 — Hybrid controlled topology, not Kubernetes by default

- **Problem:** deployment must balance privacy, egress, scale and operational burden.
- **Options:** local/rootless service; public cloud; bounded hybrid; Kubernetes.
- **Decision:** start rootless restricted service + managed/dedicated Postgres/object store where approved; use private egress proxy and isolated provider path. Introduce Kubernetes only for measured multi-worker/autoscale/rollout need.
- **Trade-offs:** hybrid networking complexity; avoids premature distributed blast radius.
- **Validation:** TLS/RLS, backup/PITR, network egress, image digest, failover, kill-switch.
- **Revisit:** concurrency/SLO/HA evidence.