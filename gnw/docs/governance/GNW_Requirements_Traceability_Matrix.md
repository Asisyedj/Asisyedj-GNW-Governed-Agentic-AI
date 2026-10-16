# GNW Requirements Traceability Matrix

**Status vocabulary:** `SATISFIED-DESIGN` = specification موجود؛ `EVIDENCE-PENDING` = executable proof باقی؛ `BLOCKED` = release روکنے والا؛ `NOT-APPLICABLE` only with rationale. No row claims deployment.

| Req ID | Requirement / source | Design response | Artifact / owner | Verification | Status / blocker |
|---|---|---|---|---|---|
| REQ-001 | Evidence-backed, non-overclaiming synthesis (master directive §1–2) | FACT/INFERENCE/HYPOTHESIS/DESIGN/UNKNOWN labels | final-report, ledger / research lead | citation audit; conflict review | SATISFIED-DESIGN |
| REQ-002 | Inventory files/repos/tools/constraints (§4) | snapshot inventory + unknown register | final-report §Existing-State / release owner | reproducible manifest | EVIDENCE-PENDING: Git root absent |
| REQ-003 | Separate historical audit, current code, live runtime | evidence classes and timestamp/digest binding | ledger / QA | provenance test | SATISFIED-DESIGN |
| REQ-004 | RQ tree L1–L8 (§5) | RQ-01…RQ-12 table | final-report; backlog B-01 | completeness review | SATISFIED-DESIGN |
| REQ-005 | Source hierarchy/corroboration (§7) | standards → official docs → research; conflict column | ledger / research lead | source review | SATISFIED-DESIGN; fresh fetch not rerun |
| REQ-006 | Claim ledger fields (§8) | Claim ID, source, date, passage, version, conflicts, confidence | evidence-ledger | schema/field audit | SATISFIED-DESIGN |
| REQ-007 | Bias audit and counterarguments (§9) | vendor, benchmark, source-language, evaluator, owner bias register | risk-register §Bias | independent review | EVIDENCE-PENDING |
| REQ-008 | Minimum three architectures (§11) | Minimal, Balanced, Higher-autonomy comparison | architecture-decisions; final-report | ADR review | SATISFIED-DESIGN |
| REQ-009 | Trust boundaries/data flow/state/storage/permissions/approvals | TB-0…TB-9; state machine; schemas | final-report; ADR-002/003 | threat-model + integration tests | EVIDENCE-PENDING |
| REQ-010 | Deterministic alternative considered for each area | deterministic dossier/spine default | architecture-decisions ADR-001 | matched ablation where agent retained | SATISFIED-DESIGN |
| REQ-011 | Agent limited by policy/PEP | model proposal only; no authority minting | gateway spec / security owner | negative authorization tests | BLOCKED: live PEP/gateway unproven |
| REQ-012 | Typed immutable planning/replanning | `plan_revision(n+1)`; freeze committed nodes | workflow schema / platform owner | stale revision/race tests EV-001 | EVIDENCE-PENDING |
| REQ-013 | Completion predicate beyond model done | goal + nodes + evidence + budget + approval + reconciliation | workflow module | EV-018/complete predicate tests | EVIDENCE-PENDING |
| REQ-014 | Provenance/citation verification | claim→span→artifact hash→parser/version graph | evidence service | EV-012; citation benchmark | BLOCKED: corpus/oracle absent |
| REQ-015 | Freshness/revalidation | ETag/Last-Modified, retrieved_at, semantic update flag | retrieval service | stale/304/changed artifact tests | EVIDENCE-PENDING |
| REQ-016 | Durable memory and deletion | canonical revision log + rebuildable index + legal hold | memory service / privacy owner | EV-009, RLS, restore | BLOCKED: current Map only |
| REQ-017 | Tool schema/validation/sandbox | JSON Schema 2020-12 + semantic policy + remote isolation | execution gateway | schema fuzz, sandbox escape | BLOCKED: hostile-code isolation unproven |
| REQ-018 | SSRF/egress defense | IP pin, redirect revalidation, proxy, port policy | egress gateway | EV-006 live lab | BLOCKED: DNS/socket test absent |
| REQ-019 | Least privilege/capability/approval | short lease, digest, nonce, TTL, SoD, consume once | auth/PEP | EV-004/005/015 | BLOCKED: provider/production enforcement |
| REQ-020 | Retry/idempotency/reconciliation | no blind retry ambiguous mutation; fence/outbox | effect service | EV-003/010 | BLOCKED: provider contract unknown |
| REQ-021 | Tenant isolation | DB RLS + application/object/cache/vector/log invariant | platform/privacy | EV-008/016 | BLOCKED: live topology absent |
| REQ-022 | Evaluation independence/calibration | deterministic oracle + independent evaluator + blinded human | eval service | EV-013; frozen holdout | BLOCKED: corpus/targets absent |
| REQ-023 | Prompt injection/red-team | taint/quarantine, tool deny, adaptive corpus | security test suite | EV-007 | EVIDENCE-PENDING; current records historical |
| REQ-024 | Monitoring/heartbeat/DLQ | separate liveness/progress/correctness/authorization signals | ops platform | watchdog/DLQ drills | BLOCKED: runtime/watchdog unproven |
| REQ-025 | Kill switch/cancel/rollback | persisted generation, final sink check, reconciliation | ops/release | EV-011/014 | BLOCKED: distributed drill absent |
| REQ-026 | Controlled improvement | proposal→isolated experiment→review→canary→rollback | release pipeline | G6 and rollback | BLOCKED: provenance/staging/reviewer |
| REQ-027 | Supply-chain/build integrity | signed digest, SBOM, SLSA-style attestation | CI/release | G0 | BLOCKED: Git/image/provenance absent |
| REQ-028 | Privacy/retention/legal hold | classification-to-policy, TTL, tombstone, cryptographic erasure | privacy service | retention/delete audit | BLOCKED: policies/roles unknown |
| REQ-029 | Human understandable control | task card, preview, freshness, escalation, cancel states | UI/ops | usability/intervention study | EVIDENCE-PENDING |
| REQ-030 | Economic/performance measurement | OTel spans; token/tool/storage/reviewer meters; p95/p99 | observability/economics | load/invoice reconciliation | BLOCKED: no benchmark/invoice |
| REQ-031 | Architecture must not imply deployment | explicit caveat on all docs | all artifacts | editorial audit | SATISFIED-DESIGN |
| REQ-032 | Final files exact paths | seven files under final/ | delivery | path/hash check | SATISFIED after generation |

## Acceptance gate mapping

- **G0 provenance:** REQ-002, 003, 027; blocked by canonical signed commit/image/SBOM.
- **G1 function:** REQ-004, 012–015; requires executable state/citation tests.
- **G2 security:** REQ-017–023; blocked by live DNS, sandbox, tenant and provider proof.
- **G3 reliability:** REQ-020, 024–025; blocked by crash/cancel/restore drills.
- **G4 quality:** REQ-014, 022–023; blocked by representative labeled corpus and thresholds.
- **G5 economics:** REQ-030; blocked by measured workload/provider billing.
- **G6 release:** all critical rows with no `BLOCKED/UNPROVEN`, independent authority, canary and rollback.

## Traceability rule
A row becomes release-satisfied only when the artifact digest, environment manifest, test output, reviewer identity and timestamp are bound to the same promotion bundle. A source-level primitive or historical report alone cannot close a runtime requirement.