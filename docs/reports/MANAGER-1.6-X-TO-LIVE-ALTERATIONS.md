# Manager 1.6.x → Live GNW Alterations Report

**تاریخ:** 12 ستمبر 2026  
**Scope:** available production archive، extracted 1.6.x-style baseline، current `/home/ubuntu/gnw` source، اور source-only council implementation.

## Comparison basis

`GNW-Governed-Agent-v4-Production.zip` کا SHA-256 `6c52998d2214acc1cebca4e2e870b74072f4d0b89ee635a39bd46f263b70a04f` ہے۔ Archive extraction اور `gnw-extract-old-1789122209` کے درمیان non-generated source comparison میں کوئی فرق نہیں ملا۔ Pre-council current source نے baseline کے بعد hardened security changes، current runtime files اور documentation updates رکھے؛ pre-council diff کا SHA-256 `e8ca52a7cef0732eba52abcb25979111b90af1e3a40fa952866332d5fa8dbb6d` محفوظ کیا گیا۔ Pre-council snapshot `/home/ubuntu/gnw-pre-council-20260912` میں 120 sanitized files ہیں۔

## Live alterations already present before this council work

موجودہ Live source میں baseline کے مقابلے میں درج ذیل اہم hardening موجود تھی: signed Ed25519 grants اور trusted issuer verification؛ durable sessions؛ atomic audit-chain append؛ exact action/content digests؛ aggregate task budget reservations؛ final kill-switch/circuit-breaker recheck؛ HTTPS، egress allowlisting اور private/local destination blocking؛ storage key containment اور byte ceilings؛ durable executor boundary؛ admin-only audit verification؛ approval separation-of-duties؛ اور adversarial security/regression tests۔ Existing baseline test suite نے pre-change **85/85 tests** اور strict TypeScript typecheck پاس کیے۔

یہ رپورٹ اس بات کا دعویٰ نہیں کرتی کہ production certification مکمل ہو گئی ہے۔ Existing project documentation کے مطابق Postgres concurrency، provider/network sandboxing، backups/restore، secret rotation، dependency scanning اور adversarial release evidence الگ gates ہیں۔

## اس turn میں شامل council alterations

| File/area | تبدیلی | live authority پر اثر |
| --- | --- | --- |
| `src/server/council/schemas.ts` | Strict envelope، finding، judge اور policy decision contracts؛ schema version `1.0.0` | صرف validation؛ authority نہیں |
| `src/server/council/store.ts` | SQLite/Postgres state machine، idempotency، transition log، finding/decision persistence | council records only |
| `src/server/council/policy-gate.ts` | deterministic hypothetical policy outcomes | database check سے ہمیشہ `execution_authorized=0` |
| `src/server/council/orchestrator.ts` | planner/verifier/critic/judge shadow sequence؛ deterministic no-network runner | executor، provider، lease، approval اور nonce paths سے الگ |
| `src/server/council/redaction.ts` | sensitive key/value redaction | stored shadow evidence میں secret exposure کم |
| `src/server/db/schema.ts` | چار council tables اور constraints | active schema میں additive tables |
| `src/server/env.ts`, `.env.example` | `GNW_COUNCIL_MODE=disabled|shadow`؛ default disabled | opt-in only |
| `src/server/orchestrator.ts` | task creation کے بعد observational hook | existing task result اور authorization unchanged |
| `tools/council_reference/` | independent Python state-machine/reference tests | runtime authority نہیں |
| `tests/council.test.ts` | persistence، idempotency، invalid output، redaction checks | regression evidence |

## Verification result

Council implementation کے بعد TypeScript typecheck پاس، **89/89 TypeScript tests پاس**، اور Python reference کے **4/4 tests پاس** ہوئے۔ Council tests نے `SHADOW_COMPLETED`، duplicate idempotency، invalid role output پر `FAILED_CLOSED`، redaction، اور `executionAuthorized=false` ثابت کیا۔

## Live safety statement

Implementation میں deployment command، service restart، migration against live production database، executor call، provider call، external write، approval review، capability issuance یا authorization escalation نہیں کی گئی۔ Live containers کا صرف read-only status snapshot لیا گیا: `deploy-app-1`, `deploy-executor-1`, `deploy-db-1`, اور `deploy-objectstore-1` healthy/running تھے۔

## Remaining certification gaps

Shadow mode کو production execution policy کا متبادل نہیں سمجھا جا سکتا۔ Live enablement سے پہلے council-specific threat model، independent schema fuzzing، Postgres lock/concurrency tests، retention policy، operator dashboards، alerting، signed model/provider adapter، prompt-injection isolation، cost ceilings، rollback rehearsal اور explicit governance review درکار ہیں۔
