# GNW Risk Register

**Scoring:** Likelihood and Impact: Low/Medium/High/Critical. Residual status is based on supplied evidence, not a live risk assessment. Proposed owners are role names.

| ID | Risk / cause | L | I | Prevent / detect controls | Recovery / evidence required | Residual status / owner |
|---|---|---:|---:|---|---|---|
| R-01 | Indirect prompt injection from web/file/tool output changes plan or requests secrets | High | Critical | quarantine/taint, model has no authority, typed extraction, PEP, least privilege, adaptive red-team | isolate run, revoke lease, preserve minimal trace, rerun clean corpus | **Open/blocker** / Security |
| R-02 | Data exfiltration through tool, HTML/image/link, covert channel | High | Critical | egress proxy, destination allowlist plus IP pinning, output limits, secret redaction, sandbox | deny egress, rotate secrets, incident response, forensic review | **Unproven** / Security |
| R-03 | DNS rebinding or redirect reaches private metadata/service | High | Critical | resolve-and-bind, redirect revalidation, approved ports, proxy/socket enforcement | quarantine gateway, block range, reproduce in live lab | **Blocker** / Platform |
| R-04 | Hostile code escapes local `shell=true`/incomplete sandbox | Medium | Critical | remote isolated executor, rootless/non-root, seccomp/cgroups/read-only FS/network deny | destroy worker, revoke leases, rotate credentials, re-attest image | **Blocker** / Platform |
| R-05 | Duplicate external mutation after timeout/retry | High | Critical | idempotency key, monotonic fence, outbox/inbox, `PENDING_RECONCILIATION`, no blind retry | provider status lookup/human reconcile; compensate only if authorized | **Unproven** / Integrations |
| R-06 | Stale worker writes after replan/cancel/kill switch | Medium | High | generation/fence check at every write and sink, lease TTL, final interlock | reject stale result; reconcile in-flight call | **Evidence pending** / Workflow |
| R-07 | Cross-tenant retrieval via DB/vector/cache/log/object/backup | Medium | Critical | RLS + application context + tenant-keyed projections + output redaction | stop service, revoke access, scope incident and restore clean copy | **Blocker** / Privacy |
| R-08 | Memory deletion leaves summaries/embeddings/backups/provider traces | High | High | canonical revision log, projection rebuild, TTL, legal hold, PRE/POST/FILT audit | cryptographic erasure, rebuild, backup expiry and provider deletion requests | **Blocker** / Privacy |
| R-09 | Process-local memory disappears on restart or diverges horizontally | High | High | durable canonical store, checkpoint/restore, projection rebuild | replay from revision log; mark missing state | **Known current gap** / Data |
| R-10 | Citation is present but unsupported, stale or post-rationalized | Medium | High | exact span/hash/parser/query lineage, entailment/completeness/faithfulness outputs | mark claim UNPROVEN/BLOCKED; source refresh and correction | **Evidence pending** / Research |
| R-11 | LLM judge self-preference/verbosity/position bias accepts bad result | Medium | High | deterministic oracle, version-pinned independent judge, blinded human calibration | invalidate evaluation, rerun with independent sample | **Evidence pending** / Evaluation |
| R-12 | Historical PASS record mistaken for current production evidence | High | Critical | artifact/environment digest binding, evidence classes, canonical manifest | freeze release; reconcile report denominator and rerun | **Current blocker** / Release |
| R-13 | Missing Git/image/SBOM/signing trust root enables tampered artifact | Medium | Critical | signed provenance, digest pinning, reproducible build, two-person release | revoke artifact, rotate keys, rebuild from trusted source | **Blocker** / Supply chain |
| R-14 | Lease signature accepted after expiry/revocation/replay | Medium | High | current revocation check, TTL, audience, nonce atomic consume, clock bound | revoke all leases, audit and reissue | **Evidence pending** / IAM |
| R-15 | Approval fatigue/rubber-stamping or stale preview | Medium | High | risk tiers, exact action digest, fresh preview, SoD, escalation and usability test | pause queue, sample approvals, retrain/adjust policy | **Evidence pending** / Operations |
| R-16 | Kill switch stops local scheduler but not provider effect | Medium | Critical | persisted generation, sink-side fence, provider cancel/status, reconciliation | stop new work, query provider, compensate only with approval | **Blocker** / Incident |
| R-17 | Queue redrive/DLQ loses ordering or repeats unsafe step | Medium | High | bounded retry, DLQ quarantine, dependency-aware redrive, idempotent nodes | manual replay from checkpoint; no blind ordered redrive | **Evidence pending** / Workflow |
| R-18 | Backup restore resurrects deleted/revoked memory or grants | Medium | Critical | deletion ledger, restore filtering, key destruction, legal hold rules, restore test | isolate restored DB, reapply tombstones, notify privacy owner | **Blocker** / DBA |
| R-19 | Provider/model drift changes quality, price or retention | High | High | model/provider digest, contract snapshot, canary, per-version metrics, budget | route to safe model/deterministic fallback; rollback | **Unmeasured** / Product |
| R-20 | Multi-agent coordination multiplies cost/latency and contradictory outputs | Medium | Medium/High | single-agent baseline, ablation, bounded concurrency and budget | disable council feature flag; use deterministic spine | **Deferred** / Product |
| R-21 | Raw prompts/results in logs/telemetry expose restricted data | Medium | High | field allowlist, hashes/redaction, restricted vault, retention TTL | purge/rotate, access review, incident response | **Evidence pending** / Observability |
| R-22 | RLS owner/superuser/BYPASSRLS or global `listModels` bypasses tenant policy | Medium | Critical | production roles, deny tests, scoped model inventory, connection tenant context | disable path; rotate credentials; audit access | **Blocker** / Privacy |
| R-23 | No representative Urdu/English corpus or harm thresholds | High | High | labeled corpus, domain stratification, calibration and abstention targets | keep release read-only; commission labeling | **Blocker** / Evaluation |
| R-24 | Operator cannot understand status/cancel/reconcile in time | Medium | High | task card with freshness/risk/digest/expiry, drills, accessibility/usability study | pause autonomy; human escalation; redesign UI | **Evidence pending** / Human factors |
| R-25 | Rollback changes code but not schema/index/memory/queue/external effects | Medium | Critical | compatibility matrix, dual-read/write migration, semantic rollback rehearsal | freeze, reconcile side effects, restore compatible bundle | **Blocker** / Release |
| R-26 | Privacy/legal role, retention or cross-border basis unknown | Medium | Critical | DPIA/records, data map, purpose/role classification, legal hold | do not process restricted data; obtain counsel/owner decision | **Blocker** / Governance |

## Bias register

| Bias | Mitigation |
|---|---|
| Vendor dependence | at least one deterministic and one alternative provider baseline; disclose provider-specific evidence |
| Confirmation bias | preserve counterevidence, failed tests and negative findings; independent reviewer |
| Source-language bias | Urdu/English stratified corpus, bilingual review and language-specific error rates |
| Benchmark selection / survivorship | include rejected, malformed, adversarial, long-tail and failed tasks |
| Evaluator bias | blinded samples, inter-rater agreement, judge ablation and deterministic checks |
| Project-owner preference | decision thresholds and veto rights recorded before results; two-person release |
| Complexity bias | test minimal deterministic baseline before adding agents, queues or Kubernetes |

## Release rule
Any Critical risk marked **Blocker**, or any mandatory evidence `UNPROVEN`, keeps the promotion state `NOT_AUTHORIZED` until an owner attaches executable evidence to the same immutable bundle.