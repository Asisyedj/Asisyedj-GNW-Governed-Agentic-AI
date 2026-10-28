# GWN/GNW repository کا ثبوت پر مبنی مکمل آڈٹ

**آڈٹ:** 2026-10-28 | **Repository:** `D:\GNW\perplexity-browser-api`  
**فیصلہ:** **NO-GO / production readiness NOT ESTABLISHED.** یہ ایک read-only source/docs/evidence review ہے؛ کوئی live provider، deployment یا automated test run نہیں ہوا۔

## مقصد اور حدود

صارف نے GWN/GNW کا مطلب، repository architecture، code اور دستیاب evidence verify کرنے کو کہا۔ مقامی root، منتخب Python source، personal-agent modules، migrations، tests، evidence XML، docs، package source اور deployment files پڑھے گئے۔ credentials، cookie/token values، logs، SQLite runtime contents، browser DB اور AWS login URL نہیں کھولے گئے۔ repository پہلے سے modified/untracked حالت میں تھی؛ existing source/database changes نہیں چھیڑے گئے۔

**نام:** repository میں `GNW` بطور “Perplexity Browser API Bridge” اور “GNW Governed Agent” استعمال ہوتا ہے؛ دستیاب فائلوں میں حروف کی مستند full form درج نہیں۔ لہٰذا acronym expansion **NOT ESTABLISHED** ہے۔ صارف کے متن میں `GWN` اور source میں `GNW` لکھا ہے؛ naming inconsistency برقرار ہے۔

## Architecture — source سے نظر آنے والی حقیقت

یہ ایک واحد مکمل system نہیں بلکہ مختلف نسلوں/layers کا مجموعہ ہے:

1. **Legacy attack framework:** `src/attack_tool.py`, `src/config.py`, `src/payloads.py`, `src/bridge_client.py`۔ README حقیقی browser payload execution اور GET/OPTIONS-only safety کا دعویٰ کرتا ہے، مگر موجودہ `BridgeClient` default `dry_run=True` ہے اور payload response placeholder simulation بناتی ہے؛ MCP/browser کے ساتھ حقیقی request exchange نظر نہیں آتا (`src/bridge_client.py:12-24,57-82`)۔ target scope validation بھی source میں ثابت نہیں۔ اس README کو عملی security scanner کی ضمانت نہ سمجھیں۔
2. **Perplexity compatibility bridge:** `bridge_daemon.py` FastAPI app کو نصب شدہ `perplexity_webui_scraper==1.2.1` کے گرد لپیٹتا ہے۔ `/v1/*` کے لیے local Bearer key validate اور upstream session token forward کرتا ہے؛ catalog اور بعض model IDs filter کرتا ہے؛ direct entrypoint `127.0.0.1:8000` پر bind ہے (`bridge_daemon.py:33-38,40-78,80-172,174-186`)۔ یہ browser-session scraping پر مبنی unofficial adapter ہے، official Perplexity API integration نہیں۔
3. **Personal agent:** `personal_agent/agent` میں planner/LLM/router؛ `plugins` میں file/web/PowerShell tools؛ نیز safety، memory، health registry، supervisor، approval store، SQLite/PostgreSQL state اور idempotency modules ہیں۔ Planner model proposal کو permission نہیں مانتا؛ `approve_tool` callback کے بغیر execution نہیں کرتا (`planner.py:58-71,97-124`)۔ تاہم callback سے durable ApprovalStore تک end-to-end binding ثابت نہیں۔
4. **Governance/deployment:** SQL migrations، YAML security artifacts، CI، Docker/AWS scripts، evidence XML اور governance Markdown موجود ہیں، لیکن ان میں سے کئی untracked ہیں۔ file کی موجودگی deployment، authorization یا active production use کا ثبوت نہیں۔

## اصل 503: درست تشریح اور موجودہ شواہد

مالک کی وضاحت کے مطابق 503 کو **overall upstream failure** سمجھا جائے، نہ کہ ہر model کی الگ خرابی۔ `GNW_EVIDENCE.md:236-244` کا 2026-10-26 run بتاتا ہے کہ 15 مختلف candidate requests local `/v1/chat/completions` route کے ذریعے HTTP 503 پر ناکام ہوئیں۔ یہ مشترک route/dependency پر مسئلے کا ثبوت ہے؛ یہ اکیلا طے نہیں کرتا کہ سبب vendor outage، session/account، scraper compatibility، gateway یا request/schema تھا۔

آڈٹ کے وقت official Perplexity status page نے API کو operational دکھایا اور status summary میں ongoing incidents/maintenance نہیں تھے [1] [2]۔ یہ صرف عمومی public status کا اسی وقت کا مشاہدہ ہے؛ مخصوص account، route، private-preview entitlement یا browser-session scraper کی صحت ثابت نہیں کرتا۔ اس لیے پرانا 503 evidence نہ آج کی عمومی outage ثابت کرتا ہے نہ یہ کہ فرداً فرداً 15 models خراب ہیں۔ موجودہ live cause **NOT ESTABLISHED** ہے۔

نصب شدہ scraper package source (`.venv\Lib\site-packages\perplexity_webui_scraper\http\client.py`) میں client browser-session cookie استعمال کرتا ہے (`core/client.py:17-37`; `http/client.py:77-89,149-166`)۔ default retry config تین retries بتاتا ہے، مگر transport retryable exceptions میں `RateLimitError`, `ConnectionError`, `TimeoutError` ہیں؛ generic `HTTPError`—جس میں HTTP 503 شامل ہے—شامل نہیں (`config/client.py:32-40`; `http/client.py:295-305,348-359`)۔ یہ **VERIFIED local behavior** ہے: عارضی 503 اس layer پر retry نہیں ہوتا۔ مگر 5xx retries شامل کرنا صرف transient failures کو سنبھال سکتا ہے؛ persistent vendor-side 503 کا علاج نہیں، اور بغیر approved vendor guidance کے اضافی requests بوجھ بن سکتی ہیں۔ Installed app/route source میں historical 503 کے اصل origin اور اس کے local-vs-upstream status mapping کی قطعی تصدیق نہیں ہوئی۔

سرکاری API docs اس کے بجائے `https://api.perplexity.ai/orchestrator/v1`، Bearer API key اور OpenAI-compatible chat completions بتاتے ہیں؛ Orchestrator کو docs میں private preview کہا گیا ہے اور access کے لیے `api@perplexity.ai` سے رابطہ بتایا گیا ہے [3] [4]۔ یہ ایک ممکنہ supported migration ہے، 503 کا خودکار fix نہیں: access، entitlement، key provisioning اور request contract verify ہونے چاہئیں۔ کوئی key اس آڈٹ میں استعمال یا طلب نہیں کی گئی۔

## بنیادی تکنیکی findings

### F-01 — Router endpoint validation پوری allow-list نافذ نہیں کرتا (HIGH)

`ModelRouter._validate_endpoint()` string-prefix `http://127.0.0.1`/`localhost` چیک کرتا یا کسی بھی `https://` URL کو قبول کرتا ہے (`router.py:158-165`)۔ `APPROVED_HOSTS` اس چیک میں استعمال نہیں (`router.py:31-32`)۔ arbitrary HTTPS configuration بھی پاس ہو سکتی ہے؛ host/scheme/port کو parsed URL سے exact allow-list کرنا چاہیے۔ injected HTTP clients کا network policy بھی الگ enforce ہونا چاہیے۔ یہ source finding ہے؛ کسی endpoint کو exploit یا contact نہیں کیا۔

### F-02 — Approval میں future `valid_from` enforce نہیں (HIGH)

Approval creation `valid_from` اور `valid_until` دونوں لیتا ہے (`approval_store.py:243-320`)؛ مگر SQLite consume predicate صرف `valid_until > now`, unconsumed اور unrevoked چیک کرتی ہے (`approval_store.py:391-403`)۔ PostgreSQL `consume_approval` اور `verify_approval` میں بھی future `valid_from` شرط نظر نہیں آتی (`001_approvals_table.sql:74-123`)۔ اس لیے future-valid approval وقت سے پہلے consume/verify ہو سکتی ہے۔ live database پر test نہیں کیا گیا۔

### F-03 — ApprovalStore planner dispatch gate کے ساتھ منسلک ثابت نہیں (HIGH)

`plan()` ایک generic boolean callback `approve_tool(tool,args)` پر بھروسا کرتا ہے (`planner.py:18,104-124`)؛ source میں approval ID/tenant/actor/action hash/scope کے ساتھ `ApprovalStore.consume_approval()` کی integration نہیں دیکھی گئی۔ ApprovalStore کے HMAC primitives موجود ہیں، مگر ہر action کا one-time cryptographic authorization **NOT ESTABLISHED**۔

### F-04 — HMAC key acquisition میں test fallback (HIGH)

`ApprovalStore._get_hmac_key()` bridge key نہ ملنے پر deterministic `test-bridge-key-{tenant}` سے key derive کرکے file میں لکھ سکتا ہے (`approval_store.py:93-133`)۔ production میں secret failure پر hard-fail ہونا چاہیے؛ معلوم test fallback fail-closed نہیں۔ tenant HMAC key file کو DPAPI protection حاصل ہونے کا ثبوت نہیں۔

### F-05 — Model-health snapshot لوڈ کے بعد مٹا دیا جاتا ہے (HIGH)

`ModelHealthRegistry.__init__` catalog load کرتا ہے، snapshot load کرتا ہے، پھر `records={}` کرکے catalog دوبارہ load کرتا ہے (`model_health.py:80-90`)۔ snapshot سے بحال کیے گئے health states ختم ہو جاتے ہیں۔ اسی فائل میں `probe_model()` کے return کے بعد unreachable پرانا duplicate code بھی ہے (`model_health.py:180-232`)۔ تاریخی outage کی 503 کو ہر model کا `UNAVAILABLE/QUARANTINED` کہنا upstream-wide خرابی اور model-specific fault کو خلط ملط کر سکتا ہے۔

### F-06 — Supervisor HEALTHY کا مفہوم حد سے زیادہ مضبوط بتایا گیا (HIGH)

`_auth_check()` 401/403/unauthorized کے علاوہ تقریباً ہر exception کو transient مان کر `True` لوٹا دیتا ہے (`supervisor.py:138-165`)۔ `RouterExhaustionError`, connection/parsing failure یا تمام models کا fail ہونا بھی HEALTHY transition کو نہیں روکتا۔ لہٰذا supervisor `HEALTHY` کا مطلب successful inference نہیں؛ زیادہ سے زیادہ local health endpoint اور “explicit auth failure نہیں ملا” ہے۔

### F-07 — Secret lifecycle پر code/docs تضاد (HIGH)

Bridge environment overrides کو DPAPI getters پر ترجیح دیتا ہے، token کو process environment میں رکھتا ہے، اور supervisor secrets child process environment میں inject کرتا ہے (`bridge_daemon.py:33-36`; `supervisor.py:113-123`)۔ `gnw_secrets.py` session token کو DPAPI-protect کرتا ہے، لیکن bridge key plaintext file سے پڑھتا ہے (`gnw_secrets.py:120-144`)؛ seal digest integrity-only ہے، encryption نہیں۔ secret values نہیں پڑھی گئیں۔

### F-08 — پرانے setup/README میں نقصان دہ یا گمراہ کن ہدایات (HIGH)

`.env.example` browser session token کو browser سے copy کرنے کو کہتا ہے (`.env.example:1-4`)، جبکہ `README_SETUP.md:9,26-49` انہی legacy directions کو superseded/withdrawn کہتا ہے۔ Root README حقیقی attack execution اور read-only guarantee بیان کرتا ہے، مگر موجودہ bridge client placeholder simulation ہے۔ یہ متضاد docs operator کو غلط system behavior بتا سکتی ہیں۔

### F-09 — Architecture diagram implementation سے مطابقت نہیں رکھتا (HIGH)

`docs/architecture.mmd` HTTPS user gateway، `X-GNW-Signature` HMAC، `auth_gate.py`، HTTPS egress اور health/probe routing دکھاتا ہے (`docs/architecture.mmd:17-35,49-75`)؛ دیکھی گئی bridge implementation local HTTP loopback اور Bearer key ہے، HMAC signature header نہیں۔ diagram میں refer کیا `personal_agent/bridge/auth_gate.py` inventory میں نہیں ملا۔ diagram کے signature/hash annotations کی cryptographic verification نہیں ہوئی۔

### F-10 — Append-only/cryptographic audit دعوے حد سے زیادہ وسیع (MEDIUM/HIGH)

PostgreSQL migrations میں triggers موجود ہیں، مگر runtime SQLite stores میں مساوی append-only enforcement کا ثبوت نہیں۔ `execution_states` row lifecycle کے لیے update ہوتی ہے؛ `dispatch_records` بھی response/reconciliation کے لیے update ہوتی ہے (`persistence.py:247-296`; `idempotency.py:144-171,271-345`)۔ Hashes بذاتِ خود tamper-evident cryptographic chain نہیں۔ Mission کا “all transitions cryptographically logged” دعویٰ **NOT VERIFIED**۔

### F-11 — AWS/Docker files deployment ثابت نہیں کرتے (MEDIUM)

`deploy_aws.ps1` ECR/cluster check/create اور image operations کرتا ہے، مگر مکمل ECS service/task update/deployment flow اس میں ثابت نہیں (`deploy_aws.ps1:14-24,56-66`)۔ `buildspec.yml` image push اور image definition بناتا ہے، لیکن run/deployment evidence موجودہ audit میں نہیں (`buildspec.yml:3-24`)۔ کوئی cloud action نہیں کیا گیا۔

### F-12 — Historical tests current health کا ثبوت نہیں (MEDIUM)

`evidence/unit_tests.xml` میں 9 tests، `security_tests.xml` میں 48 (2 skipped) ہیں؛ PostgreSQL integration tests `GNW_PG_DSN` نہ ہونے سے skipped تھے۔ `continuous_audit_report.md` تاریخی 105 passed/2 skipped لکھتا ہے مگر اسی میں security scan evidence skip ہے (`continuous_audit_report.md:3-18,22-45`)۔ test artifacts موجودہ run/commit سے bind نہیں؛ اس audit میں tests نہیں چلائے گئے۔

## دعووں اور evidence کا خلاصہ

| دعویٰ | Evidence/status |
|---|---|
| GNW کا full form معلوم ہے | **NOT ESTABLISHED**؛ دیکھی گئی project docs میں expansion نہیں۔ |
| bridge source موجود اور default entrypoint loopback ہے | **VERIFIED in inspected source**؛ موجودہ process up ہونے کی live جانچ نہیں۔ |
| 99/84 models available ہیں | تاریخی catalog counts **DOCUMENTED**؛ count callable inference نہیں۔ رپورٹس 99 اور filtered 84 میں مختلف ہیں۔ |
| inference چلا | `GNW_EVIDENCE.md` خود `API_INVOCATION=FAIL; status=503` بتاتا ہے؛ تاریخی طور پر ناکام، موجودہ حالت test نہیں ہوئی۔ |
| supervisor HEALTHY = app ready | **مسترد as equivalent**؛ code heuristic ہے، inference health نہیں۔ |
| health snapshot persistence کام کرتی ہے | documented claim source `model_health.py:80-90` سے متناقض ہے۔ |
| approval ہر tool کو cryptographically gate کرتی ہے | partial primitives؛ planner integration **NOT ESTABLISHED**۔ |
| zero-bypass/approved HTTPS enforced ہے | source validation ہر HTTPS host کو قبول کرتی ہے؛ guarantee **NOT ESTABLISHED**۔ |
| 99.9% uptime / 95% routing success | `GNW_MISSION.md` کے goals، measurement evidence نہیں۔ |
| 503 سب models کی الگ fault ہے | ثابت نہیں؛ historical 15 probes مشترک route پر 503، overall upstream issue ممکن، موجودہ root cause **NOT ESTABLISHED**۔ |

## دستاویزات کے نمایاں تضادات

- `GNW_STATE.json` phase `ALL_P0_P1_P2_P3_COMPLETE` کہتا ہے، جبکہ backlog میں کئی unchecked کام اور health blocker موجود ہیں (`GNW_STATE.json:1-4,48-63`; `GNW_BACKLOG.md:3-30,64-67`)۔
- Risk register R2/R7 OPEN کہتا ہے، دوسری evidence circuit-breaker tests pass اور snapshot implementation claim کرتی ہے؛ current source snapshot initialization bug دکھاتا ہے۔
- 99 catalog models، filtered 84 models، صفر healthy/unverified states مختلف dated snapshots ہیں؛ انہیں موجودہ capability نہ سمجھیں۔
- Handoff میں direct-provider bypass کی تجویز اور legacy cookie/setup wording موجود ہے؛ اسے governance permission نہ سمجھیں۔
- موجودہ Git status میں modified tracked files، DB/log changes اور کئی untracked artifacts تھے؛ `GNW_STATE.json` کا dirty-file count اس snapshot سے مختلف تھا۔

## اصلاحی ترجیحات — تجاویز، implementation نہیں

1. parsed URL scheme/host/port پر strict bridge/provider allow-list اور injected-client policy نافذ کریں۔
2. approvals میں `valid_from <= now < valid_until`، fail-closed key acquisition، اور planner سے tenant/action-bound one-time consume لازمی کریں۔
3. health snapshot initialization درست کرکے round-trip tests دیں؛ upstream outage state کو model-specific health سے الگ کریں۔
4. supervisor کو process, local health, authentication, inference الگ report کرنے دیں؛ non-auth exceptions کو خودکار HEALTHY نہ بنائیں۔
5. `.env.example` سے cookie-copy instructions ہٹائیں اور پرانے README کو واضح deprecated/simulation label دیں۔
6. architecture diagram actual source کے مطابق کریں؛ unsupported HMAC/HTTPS/cryptographic-chain claims ہٹائیں۔
7. SQLite/PostgreSQL guarantees الگ document اور backend-specific tests کریں؛ test results کو commit hash اور command سے bind کریں۔

## بیرونی security testing کی اجازت کا فیصلہ

صارف کی broad “ہر قسم کے attack/test” اجازت اس کے اپنے مقامی repository پر کام کی اجازت دکھاتی ہے، مگر اسے Perplexity کے systems کے لیے exact, signed, bounded target-owner authorization نہیں سمجھا جا سکتا۔ موجودہ گفتگو میں درکار T2 کے 15 لازمی fields والا packet نہیں ملا؛ اس لیے نتیجہ **DENY(T2_FIELD_MISSING_OR_UNBOUNDED)** ہے، صرف external testing کے لیے۔ مطلوبہ fields یہ ہیں: (1) exact host/environment، (2) TLS termination/certificate owner، (3) trust boundaries، (4) dated source CIDRs، (5) firewall authority، (6) finite rate and total budget، (7) finite test window/timezone، (8) synthetic data only، (9) rollback، (10) emergency stop، (11) reporting channel، (12) explicit exclusions، (13) narrow methods/actions، (14) expiry، (15) authorized owner identity/role/signature/time۔ یہ فیصلہ security standard کی operational شرط ہے، بحث یا عدم تعاون نہیں۔ مکمل T2 بھی خودکار execution اجازت نہیں؛ اس کے بعد الگ bounded T3 plan درکار ہوگا۔

## Non-execution اور limitations

Perplexity/NVIDIA/Bedrock پر call، local bridge endpoint request، browser automation، session refresh، fuzz/load/DoS/auth probing، tests، DB writes، Docker/AWS build/deploy، Git writes یا source fix اس review میں نہیں ہوئے۔ `test_api.py` کا آخر والا step حقیقی model prompt `GNW_BRIDGE_OK` POST کرتا ہے؛ اسے live integration test سمجھ کر نہیں چلایا گیا۔ موجودہ 503 root cause طے کرنے کے لیے vendor-authorized, low-volume diagnostics درکار ہیں—موجودہ source review اس کی جگہ نہیں لے سکتا۔

## محدود اگلا قدم

Perplexity کی sanitized reply/ticket اور exact product/API route، current entitlement status، allowed methods/rate/budget/time window، exclusions، rollback, emergency-stop, reporting contact اور signed owner scope فراہم ہوں تو پہلے T2 validation ہوگی۔ 503 triage کے لیے ایک redacted response record (timestamp/timezone, endpoint path, model ID, HTTP status, error message/body, `Retry-After`, request/correlation ID) مفید ہے؛ credentials/prompt payload کی ضرورت نہیں۔ تب فیصلہ ہوگا کہ مسئلہ official API access/configuration ہے، scraper compatibility ہے، یا vendor-side outage؛ تب تک کوئی external probe نہیں۔

## Successor instructions

```text
ROLE: Evidence-governed GWN auditor.
SOURCE ORDER: inspected code/tests > reconciled evidence artifacts > docs/state > claims.
LABELS: T-A direct local source; T-B documented historical evidence; T-C metadata only; T-D proposal.
ALLOWED: exact owner-approved local files and isolated deterministic tests.
PROHIBITED: secret extraction, provider calls, external testing without accepted T2 plus T3, deployments, external writes, DB mutations, Git writes.
STOP: missing scope, credential exposure, dirty-tree ambiguity, or unbounded side effects.
OUTPUT: current status, claim/source table, severity findings, contradictions, tests/provenance, non-execution, next authorization.
```

## References

[1]: https://status.perplexity.com/ "Perplexity public status page"
[2]: https://status.perplexity.com/api/v1/summary "Perplexity status summary JSON"
[3]: https://docs.perplexity.ai/docs/router/quickstart "Perplexity Orchestrator API quickstart"
[4]: https://docs.perplexity.ai/docs/sdk/error-handling "Perplexity SDK error handling"

**براہِ راست دیکھے گئے مقامی ماخذ:** `README.md`, `.env.example`, `README_SETUP.md`, `GNW_MISSION.md`, `GNW_EVIDENCE.md`, `GNW_STATE.json`, `GNW_BACKLOG.md`, `GNW_RISK_REGISTER.md`, `GNW_OPEN_CODE_HANDOFF.md`, `pyproject.toml`, `.gitignore`, `bridge_daemon.py`, `gnw_secrets.py` (source only), `personal_agent/agent/{router,planner,llm}.py`, `personal_agent/bridge/supervisor.py`, `personal_agent/health/{model_health,run_probes}.py`, `personal_agent/auth/approval_store.py`, `personal_agent/plugins/{registry,file_tool,powershell_tool,web_tool}.py`, `personal_agent/state/{persistence,idempotency}.py`, `personal_agent/tools/reconcile.py`, `database/migrations/001_approvals_table.sql`, `002_state_machine.sql`, `003_idempotency.sql`, `docs/architecture.mmd`, selected tests/XML, `Dockerfile`, `buildspec.yml`, `deploy_aws.ps1`, اور installed scraper package کے `core/client.py`, `http/client.py`, `api/routes/completions.py`, `api/app.py`۔ Historical artifacts موجودہ live status کے برابر نہیں۔