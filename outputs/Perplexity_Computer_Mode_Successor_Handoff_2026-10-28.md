# Perplexity Computer Mode — successor handoff

**تیاری:** 2026-10-28، تقریباً 05:31 PKT  
**Workspace:** `D:\GNW\perplexity-browser-api`  
**مقصد:** اگلا AI agent Perplexity Computer-mode مسئلے کی محفوظ، evidence-first تشخیص جاری رکھے۔ یہ handoff **root cause ثابت نہیں کرتا** اور کسی live API call یا Computer-control integration کی اجازت نہیں دیتا۔

## مختصر صورتِ حال

صارف کا مقصد ہے کہ Perplexity app کے Computer mode میں prompt کس model/API route کو جاتا ہے، method/path کیا ہے، اور `GPT-5.4 unavailable` مسئلے کا قابلِ اعتماد متبادل کیا ہے، یہ معلوم کیا جائے۔ صارف کے مطابق ایک مخصوص active session کے chat/edit input سے ہی Computer feature چلتا ہے؛ دیگر جگہوں سے Computer feature نہیں چلتا۔ یہ user report ہے، آزادانہ طور پر reproduce نہیں ہوا۔

**اہم نتیجہ:** اصل Computer request کا HTTP method، hostname/path، response status، API model ID، request body یا اس کا TCP connection سے تعلق **NOT ESTABLISHED** ہے۔ پچھلے capture نے صرف process-linked TCP endpoints اور port 443 ریکارڈ کیے۔ دو بعد کے UI observations میں target window minimized تھی یا Computer Use snapshot timeout ہوا۔ آخری کامیاب visible frame میں Computer mode منتخب، `Type a command…` input، اور `GPT-5.4 unavailable` label نظر آیا۔ یہ UI signal ہے، backend model یا 503 root cause کی تصدیق نہیں۔

## Evidence register

| دعویٰ/مشاہدہ | ماخذ | درجہ | حیثیت اور حد |
|---|---|---|---|
| 60-second window میں Perplexity process tree سے آٹھ remote IP:443 endpoints دیکھے گئے۔ | `outputs/Perplexity_Desktop_Metadata_Capture_2026-10-28.md` | T-A | مقامی TCP metadata براہِ راست ریکارڈ ہوا؛ TLS اندرونی مواد نہیں دیکھا گیا۔ |
| Capture سے method، URL path، hostname، model ID یا prompt-to-connection correlation نہیں نکلا۔ | وہی capture report | T-A | واضح non-claim؛ یہ data capture کے دائرے سے باہر تھا۔ |
| ایک successful screen frame میں Computer mode، `Type a command…` اور `GPT-5.4 unavailable` دکھا۔ | Computer Use observation، 2026-10-28 تقریباً 05:16 PKT | T-C | visible UI signal؛ underlying API response/model entitlement نہیں دیکھا۔ |
| بعد میں user نے app restore کرنے کی اطلاع دی، مگر اس کے بعد read-only observation timeout ہوا۔ | user message اور Computer Use result، تقریباً 05:24–05:26 PKT | T-C/T-A | user report محفوظ ہے؛ موجودہ live window state دوبارہ establish نہیں ہوئی۔ |
| GNW میں الگ official-API gateway شامل ہوا۔ | `personal_agent/agent/provider_gateway.py`, `docs/provider_gateway.md`, `pyproject.toml` | T-A | source براہِ راست موجود ہے؛ service start یا provider call نہیں ہوا۔ |
| نئے gateway کے آٹھ unit tests کامیاب ہوئے۔ | `python -m pytest personal_agent\tests\test_provider_gateway.py -q -p no:cacheprovider` کا local result | T-A | `8 passed in 18.32s`; system Python میں `httpx`, FastAPI اور pytest موجود تھے؛ project `.venv` میں `httpx` اور pytest نہیں تھے۔ Tests `MockTransport` استعمال کرتے ہیں۔ |
| Historical GNW evidence میں 2026-10-26 کو 15 model probes نے HTTP 503 دکھایا۔ | `GNW_Full_Repository_Audit_2026-10-28.md`, lines 88–95 | T-B | پرانا route-level signal؛ موجودہ outage، Computer mode یا مخصوص model کی root cause نہیں۔ |
| Computer mode کا اصل protocol عوامی docs میں نہیں ملا۔ | نیچے دیے گئے official API docs کا review | External official-doc review | دستیاب public docs میں documented Computer desktop-control endpoint نہیں ملا؛ یہ دعویٰ نہیں کہ private/vendor interface ہرگز موجود نہیں۔ |
| “صرف ایک session/chat field سے Computer چلتا ہے، باقی جگہوں سے نہیں” | صارف کی وضاحت | T-C | owner-reported symptom؛ reproduce/test نہیں ہوا۔ |

### پچھلے TCP capture کا عین data

Capture window **04:48:49–04:49:49 PKT** (2026-10-27 23:48:49–23:49:49 UTC) تھا۔ تمام remote ports 443 تھے۔ مشاہدہ شدہ endpoints:

- PID 4824 — `104.18.27.48:443`
- PID 12212 — `3.233.158.112:443`, `3.233.158.24:443`, `3.233.158.26:443`
- PID 15824 — `104.18.27.48:443`, `142.251.106.105:443`, `142.251.106.99:443`, `192.178.211.105:443`

ان IPs کے لیے hostname/provider attribution نہیں کیا گیا۔ انہیں Computer request، Perplexity API، یا کسی خاص model سے منسوب نہ کریں۔ مکمل timestamps/sample counts capture report میں ہیں۔

## اس دور میں کیا بنایا گیا

`personal_agent/agent/provider_gateway.py` ایک الگ loopback-only FastAPI service ہے؛ یہ پرانے `bridge_daemon.py` یا browser-session scraper کو بدلتا نہیں۔ Local routes:

- `POST /v1/orchestrator/chat/completions` → official upstream `https://api.perplexity.ai/orchestrator/v1/chat/completions`
- `POST /v1/agent` → `https://api.perplexity.ai/v1/agent`
- `POST /v1/search` → `https://api.perplexity.ai/search`
- `POST /v1/custom/dispatch` → صرف اوپر کے تین documented routes میں انتخاب؛ arbitrary URL قبول نہیں کرتا۔
- `POST /v1/computer` → HTTP 501 `computer_control_api_unavailable`; یہ جان بوجھ کر stub ہے، Computer automation نہیں۔

Service code loopback پر `127.0.0.1:8010` bind کرتا ہے، `PERPLEXITY_API_KEY` server-side environment سے لیتا ہے، redirects اور environment proxies بند کرتا ہے، اور input میں upstream URL قبول نہیں کرتا۔ API key فراہم، محفوظ، پرنٹ یا استعمال نہیں کی گئی۔ Service start نہیں ہوا۔

موجودہ local changes صرف یہ ہیں: `pyproject.toml` میں direct runtime dependencies اور `test` extra؛ نئے `personal_agent/agent/provider_gateway.py`, `personal_agent/tests/test_provider_gateway.py`, اور `docs/provider_gateway.md`۔ Existing bridge/router files اس change میں نہیں چھیڑی گئیں۔ کوئی Git commit نہیں ہوا۔

## موجودہ “unavailable” علامت اور ممکنہ متبادل

`GPT-5.4 unavailable` صرف اس ایک visible frame پر نظر آیا۔ یہ خود سے یہ ثابت نہیں کرتا کہ API model route 503 دے رہا ہے؛ ممکنہ وجوہات میں UI/model catalog یا entitlement، feature capability، app/backend failure، یا stale selector شامل ہو سکتے ہیں۔ ان میں سے کوئی وجہ diagnose نہیں ہوئی۔

Official Agent API quickstart میں `POST /v1/agent` اور `openai/gpt-5.6-sol` ایک example ہیں [1]۔ یہ documented **text/agent API example** ہے، Perplexity Computer desktop actions کا ثابت شدہ replacement نہیں، اور صارف کے account میں entitlement/live availability کی تصدیق نہیں۔ Orchestrator docs اسے private preview کہتے ہیں [2]؛ Search API raw ranked results دیتا ہے، generated Computer task نہیں [3]۔ کوئی live test نہیں ہوا۔

## ماحول اور governance caveats

- Git worktree پہلے سے dirty تھا: modified logs/source/runtime DB files اور کئی untracked artifacts موجود تھے۔ مکمل snapshot موجودہ GWN audit میں ہے۔ کسی successor کو پہلے `git status --short` دیکھنا اور پہلے سے dirty files overwrite نہ کرنا چاہیے۔ Credential-adjacent artifacts، logs، secrets، browser storage، cookies، tokens اور session data نہ پڑھیں/نہ ظاہر کریں۔
- Perplexity/NVIDIA/Bedrock پر کوئی call، local bridge inference request، browser/DevTools request، TLS interception، certificate install، fuzz/load/auth probe، attack، DB write، Docker/AWS deploy، external write یا Git commit نہیں کیا گیا۔
- Perplexity کے اپنے infrastructure پر security testing کے لیے broad owner-level user consent کافی نہیں؛ سابق audit میں bounded signed target-owner T2 scope نہ ہونے کی وجہ سے `DENY(T2_FIELD_MISSING_OR_UNBOUNDED)` درج ہے۔ کوئی external test/probe نہ کریں۔
- UI inspection کے لیے محدود takeover منظور ہوا تھا، مگر مسلسل/automatic input monitoring کی منظوری یا capability نہیں ہے۔ صارف ہر مرحلے پر pause کرے، تب snapshot لیں۔ پچھلے Computer Use calls میں app minimized یا tool timeout ہوا؛ access barrier کو بار بار force یا bypass نہ کریں۔

## اگلے agent کے لیے کام کی ترتیب

1. اس handoff اور مکمل GWN audit کو پہلے پڑھیں۔ Existing dirty worktree، gateway code اور evidence report preserve کریں؛ کوئی bridge/source rollback نہ کریں۔
2. صارف سے کہیں کہ Perplexity app خود foreground میں لائے، Computer mode کی screen پر رکے، اور صرف ایک harmless test step کے لیے explicit go-ahead دے۔ ہر action سے پہلے screen visible/paused ہونے کی تصدیق کریں۔ Snapshot failures پر retries کی قطار نہ لگائیں۔
3. اگر app کا **عام، supported DevTools/Network inspector** دستیاب ہو اور user ابھی اجازت دے تو صرف اس ایک نئی request کے یہ fields دیکھیں: HTTP method، hostname/path، timestamp/timezone، status، اور model identifier۔ Authorization، Cookie، session token، request/response body یا دوسری conversations copy/export نہ کریں۔ Inspector disabled ہو تو OS/app security bypass، MITM proxy، custom certificate، memory scraping یا private endpoint reverse engineering نہ کریں؛ vendor support سے sanitized trace طلب کریں۔
4. Model picker اگر visible ہو تو Computer mode کے اندر دکھائی جانے والی available alternatives صرف observe کریں۔ Model تبدیل کرکے provider request نہ بھیجیں جب تک user اس exact test اور ممکنہ billing کی الگ منظوری نہ دے۔ `openai/gpt-5.6-sol` صرف documented Agent API example ہے، Computer-mode fix نہیں۔
5. اگر صارف کا مقصد صرف model text response ہو تو documented `/v1/agent` route پر bounded test الگ مجاز ہو سکتا ہے؛ پہلے API key configuration/access اور ممکنہ charge کی منظوری لیں۔ API key chat، file، log یا command output میں نہ لیں۔ Orchestrator access private preview ہے۔
6. 503 کے لیے sanitized error record مانگیں: timestamp/timezone، public endpoint path، model ID، HTTP status، redacted error text، `Retry-After`، request/correlation ID۔ Prompt body اور credentials کی ضرورت نہیں۔ Historical 503 کو current status نہ سمجھیں۔
7. Source change سے پہلے explicit local scope، dirty status اور acceptance checks لکھیں۔ Offline tests isolated رکھیں۔ Live provider/network tests، installs، deployment، account changes یا Git writes کے لیے الگ explicit authorization لیں۔

## AI-readable continuation block

```text
ROLE: Evidence-governed successor investigating the user-reported Perplexity Computer-mode model-unavailable/503 symptom and the separate GNW gateway.
OBJECTIVE: Establish, if observable via supported UI/docs, only the last request's method, host/path, status, timestamp and model ID; distinguish Computer UI failure from official API route behavior.
SOURCE ORDER: direct local code/test/capture > reconciled audit > official public docs > visible UI metadata > user report > hypothesis.
LABELS: T-A direct local evidence; T-B historical/reconciled evidence; T-C UI metadata or user-reported symptom; T-D proposal. Keep UNKNOWN/NOT ESTABLISHED when direct evidence is absent.
ALLOWED: read listed local files, review official public docs, paused UI snapshots under current user consent, deterministic offline tests with mocks, narrowly scoped new local files if authorized.
PROHIBITED: secrets/cookies/tokens/session storage, arbitrary MITM/decryption/cert installation, private app protocol emulation, external probing/attacks, unrestricted capture, live provider calls without exact approval, deployments, DB mutations, Git writes.
STOP: app control timeout or access barrier; missing user pause; credential exposure; dirty-tree ambiguity; paid/live API action without exact approval; request for bypass.
OUTPUT: facts with provenance, observed UI state, unknowns, 503 evidence, changes/tests, non-execution, exact next authorization needed.
```

## Local source files

- `outputs/GWN_Full_Repository_Audit_2026-10-28.md` — full repository/security audit and historic 503 discussion.
- `outputs/Perplexity_Desktop_Metadata_Capture_2026-10-28.md` — exact limited capture results and limitations.
- `personal_agent/agent/provider_gateway.py` — new loopback gateway.
- `personal_agent/tests/test_provider_gateway.py` — eight offline mocked tests.
- `docs/provider_gateway.md` — local route usage and setup notes.
- `pyproject.toml` — dependency changes for the new gateway and test extra.

## References

[1]: https://docs.perplexity.ai/docs/agent-api/quickstart "Perplexity Agent API quickstart"
[2]: https://docs.perplexity.ai/docs/router/routing-and-reliability "Perplexity Orchestrator routing and reliability"
[3]: https://docs.perplexity.ai/docs/search/quickstart "Perplexity Search API quickstart"
[4]: https://status.perplexity.com/ "Perplexity public status page"
