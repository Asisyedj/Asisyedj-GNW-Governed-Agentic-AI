# GNW Model Council — Source-Only Shadow Mode

## مقصد اور حد

یہ implementation موجودہ GNW governed execution path کے ساتھ ایک **source-only observational council** شامل کرتی ہے۔ Council کسی live action کو authorize نہیں کرتی، capability lease issue نہیں کرتی، executor یا provider کو call نہیں کرتی، اور موجودہ `runTask` کے `ALLOW`, `DENY` یا `STOP` فیصلے کو تبدیل نہیں کرتی۔ Feature flag `GNW_COUNCIL_MODE=disabled` default ہے؛ صرف `GNW_COUNCIL_MODE=shadow` پر council کی hypothetical persistence فعال ہوتی ہے۔

## Council roles

| مرحلہ | کردار | محفوظ output |
| --- | --- | --- |
| `PLANNING` | `planner` | bounded claims، assumptions، risks، missing evidence |
| `VERIFYING` | `verifier` | evidence binding، contract checks، validation gaps |
| `CRITIQUING` | `critic` | adversarial risks، unsafe assumptions، required controls |
| `JUDGING` | `judge` | advisory verdict، dissent summary، evidence gaps |
| `POLICY_DECIDED` | deterministic gate | hypothetical outcome؛ ہمیشہ `executionAuthorized=false` |

تمام outputs Zod schemas اور versioned JSON Schemas سے validate ہوتے ہیں۔ Invalid output یا persistence failure council کو `FAILED_CLOSED` بناتا ہے۔

## State machine

`RECEIVED → STATIC_VALIDATED → COUNCIL_QUEUED → PLANNING → VERIFYING → CRITIQUING → JUDGING → POLICY_DECIDED → SHADOW_COMPLETED`

ہر non-terminal state سے `FAILED_CLOSED`, `CANCELLED` یا `EXPIRED` کی bounded transition ممکن ہے۔ Terminal state سے واپس جانا ممنوع ہے۔ `idempotency_key` پر unique constraint duplicate council task کو replay کے طور پر پہچانتا ہے۔

## Durable storage

نئی tables یہ ہیں: `council_tasks`, `council_findings`, `council_transitions` اور `council_policy_decisions`۔ Findings میں provider، model version، prompt-template digest، output digest اور schema-valid marker محفوظ ہوتے ہیں۔ Task envelope اور sensitive values persistence سے پہلے redaction سے گزرتے ہیں۔ Policy decision table میں database-level `execution_authorized = 0` check موجود ہے۔

## Existing governance سے تعلق

Council صرف existing task admission کے بعد ایک bounded copy/envelope کا shadow record بناتی ہے۔ Actual execution بدستور `governance.ts`, `orchestrator.ts`, `llm.ts`, `execution.ts`, `video.ts` اور capability lease path کے تحت رہتی ہے۔ Council module ان execution modules کو import نہیں کرتا۔ کوئی shadow result active approval، grant، nonce، lease، budget reservation یا provider submission نہیں بناتا۔

## Operational limits

Deterministic source-only runner میں network egress صفر، cost صفر، اور runtime envelope 60 seconds ہے۔ Future model-backed runner کے لیے provider integration الگ governed adapter کے طور پر لانا ہوگا؛ اسے اس shadow implementation کا implicit authority نہیں سمجھا جا سکتا۔ Production promotion کے لیے الگ approval، adversarial evidence، Postgres concurrency، audit verification، secret hygiene، network sandbox، rollback اور observability evidence درکار ہوں گے۔

## Verification

موجودہ baseline کے 85 tests اور typecheck کے بعد council implementation میں 4 council tests شامل ہوئے، جس سے کل 89 TypeScript tests ہوئے۔ Python reference کے 4 tests الگ پاس ہوئے۔ Default-disabled mode میں موجودہ API behavior برقرار رہتا ہے؛ shadow-specific tests in-memory SQLite پر persistence، idempotency، schema failure اور non-authorizing decision ثابت کرتے ہیں۔
