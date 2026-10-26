# GNW OpenCode Handoff — Session Summary & Next Actions

## Session Metadata
- **Session ID**: ses_e88150ca8ffeRusl8i8kSXNcZa
- **Date**: 2026-10-26
- **Phase**: BRIDGE_SUPERVISOR_OPERATIONAL
- **Agent**: OpenCode (NVIDIA Engineering Partner)
- **Working Directory**: D:\GNW\perplexity-browser-api
- **Git Branch**: master
- **Git Commit**: fc9d350 (HEAD)

---

## Changes Made This Session

### 1. bridge_daemon.py — Added /health Endpoint (CRITICAL FIX)
**File**: `bridge_daemon.py`
**Change**: Modified `BridgeAuthGate` to handle `/health` and `/v1/health` directly, returning `{"status":"ok"}` with HTTP 200.
**Reason**: Supervisor and test_api.py expected a health endpoint that didn't exist in the underlying perplexity_webui_scraper app.
**Verification**: `test_api.py` → `HEALTH_CHECK=PASS; status=200`

### 2. personal_agent/bridge/supervisor.py — Fixed Auth Check Logic (CRITICAL FIX)
**File**: `personal_agent/bridge/supervisor.py`
**Change**: Modified `_auth_check()` to return `True` for upstream 503 errors (transient), only `False` for 401/403/unauthorized errors.
**Reason**: Supervisor was stuck in RECOVERING/AUTH_REQUIRED because Perplexity upstream returns 503. Auth check should verify local bridge key validity, not upstream availability.
**Verification**: Supervisor transitions RECOVERING → HEALTHY within ~24 seconds.

### 3. pyproject.toml — Fixed Package Metadata
**File**: `pyproject.toml`
**Change**: Moved `name`, `version`, `description`, `readme`, `requires-python`, `dependencies` into `[project]` table (was at root level).
**Reason**: `pip install -e .` failed with "missing field `name`" error.
**Verification**: `pip install -e .` succeeds.

---

## Current System State (Verified)

### Bridge Daemon
- **Status**: RUNNING (PID 19704)
- **Port**: 8000 (loopback only: 127.0.0.1)
- **Endpoints**:
  - `GET /health` → 200 {"status":"ok"} ✅
  - `GET /v1/models` → 200 (99 models, requires valid Bearer token) ✅
  - `POST /v1/chat/completions` → 503 Service Unavailable ⚠️ (UPSTREAM ISSUE)
- **Auth**: HMAC-validated Bearer token via `BridgeAuthGate`

### Supervisor
- **State**: HEALTHY
- **Process Monitored**: Bridge PID 19704
- **Check Interval**: 30 seconds
- **Failure Threshold**: 3
- **Recovery Cooldown**: 60 seconds
- **Max Restarts**: 5
- **Restarts This Session**: 1

### Model Health Registry
- **Catalog Models**: 99 total
  - Available: 92
  - Unknown: 5
  - Unavailable: 2
- **Health States** (all unverified due to upstream 503):
  - Healthy: 0
  - Unverified: 92
  - Unknown: 5
  - Unavailable: 2
  - Quarantined: 0
- **Blocker**: Upstream Perplexity 503 prevents live probe verification

### NVIDIA Model Access (OpenCode)
- **Provider**: nvidia (configured and authenticated)
- **Models Available**: 12
- **Key Models**:
  - `nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b` — Nemotron 3.5 Super VL 120B A12B (FREE)
  - `nvidia/minimaxai/minimax-m3.1-flash` — MiniMax-M3.1-Flash (FREE)
  - `nvidia/stepfun-ai/step-5-preview` — Step 5 Preview (FREE)
- **Not Found**: Nemotron 3.5 Bolt E4B (not in current catalog)
- **Free Tier**: Verified — all models show $0 input/output cost

### Git State
- **Modified Files** (4):
  - `personal_agent/agent/llm.py`
  - `personal_agent/agent/planner.py`
  - `personal_agent/memory/sqlite_store.py`
  - `personal_agent/plugins/registry.py`
- **Modified This Session** (3):
  - `bridge_daemon.py`
  - `personal_agent/bridge/supervisor.py`
  - `pyproject.toml`
- **New Governance Files** (6):
  - `GNW_MISSION.md`
  - `GNW_BACKLOG.md`
  - `GNW_STATE.json`
  - `GNW_EVIDENCE.md`
  - `GNW_RISK_REGISTER.md`
  - `GNW_OPEN_CODE_HANDOFF.md`

---

## Outstanding Issues (Requiring Antigravity Action)

### 🔴 CRITICAL: Perplexity Upstream 503 (External Dependency)
**Impact**: All model invocations fail. Bridge and supervisor are functionally correct.
**Evidence**: `test_api.py` shows `API_INVOCATION=FAIL; status=503`
**Action Required**: 
- Antigravity to investigate Perplexity service status
- Check if session token expired (run `refresh_token.py`)
- Consider alternative model providers if prolonged

### 🟠 HIGH: Router Circuit Breaker Trips on 503
**File**: `personal_agent/agent/router.py` — `record_failure()` method
**Issue**: Treats 503 as hard failure, trips circuit breaker after 3 consecutive failures. Models become permanently unavailable until manual reset.
**Fix Needed**: Distinguish transient errors (503, 429, timeout) from auth failures (401, 403). Transient errors should not increment `consecutive_failures` or trip breaker.

### 🟡 MEDIUM: Model Health State Not Persisted
**File**: `personal_agent/health/model_health.py` — `ModelHealthRegistry`
**Issue**: Health state lost on process restart. `health_snapshot.json` written but not loaded.
**Fix Needed**: Add `load_snapshot()` call in `__init__` or `refresh_catalog()`.

### 🟡 MEDIUM: Bridge Port Conflict on Restart
**File**: `personal_agent/bridge/supervisor.py` — `_start_bridge_process()`
**Issue**: Windows TIME_WAIT holds port 8000 after bridge termination. Restart fails with `Errno 10048`.
**Fix Needed**: Add `SO_REUSEADDR` to uvicorn config, or increase restart cooldown, or implement port wait logic.

---

## Next Recommended Actions (Priority Order)

### P1 — Immediate (This Session Continuation)
1. **Fix router circuit breaker for 503** — Modify `record_failure()` in `router.py` to classify errors
2. **Add health snapshot persistence** — Load `health_snapshot.json` on registry init
3. **Run full test suite** — Once upstream recovers: `pytest personal_agent/tests/ -v`

### P2 — Short Term (Next Session)
4. **Add SO_REUSEADDR to bridge** — Prevent port conflicts on restart
5. **Implement supervisor heartbeat** — Write timestamp file for external watchdog
6. **Add NVIDIA model routing** — Integrate Nemotron 3.5 Super VL into `DEFAULT_TASK_ROUTING`

### P3 — Medium Term
7. **Create .opencode/agents/** — Specialized agents for research, review, test, security
8. **Add CI pipeline** — GitHub Actions for typecheck, test, audit-chain verify
9. **Document secret rotation** — DPAPI backup/restore procedure

---

## Handoff Protocol for Antigravity

### Resume Point
```bash
cd D:\GNW\perplexity-browser-api
# Verify bridge still running
python test_api.py
# Check supervisor state
python -c "
import sys; sys.path.insert(0, '.')
from personal_agent.bridge.supervisor import global_bridge_supervisor
print(global_bridge_supervisor.status())
"
```

### If Bridge Down
```bash
# Restart supervisor (will restart bridge)
python -c "
import sys; sys.path.insert(0, '.')
from personal_agent.bridge.supervisor import global_bridge_supervisor, BridgeState
global_bridge_supervisor.stop()
global_bridge_supervisor._state = BridgeState.FAILED
global_bridge_supervisor._failures = 0
global_bridge_supervisor._restart_count = 0
global_bridge_supervisor._process = None
global_bridge_supervisor._stop_event.clear()
global_bridge_supervisor.start()
"
```

### If Upstream 503 Persists
1. Run `python refresh_token.py` to refresh Perplexity session
2. Check Perplexity web UI for service status
3. Consider temporary fallback to NVIDIA models via OpenCode direct (bypass bridge)

### File Ownership (Coordination)
| File | Owner | Notes |
|------|-------|-------|
| `bridge_daemon.py` | OpenCode | Bridge runtime |
| `personal_agent/bridge/supervisor.py` | OpenCode | Supervisor logic |
| `personal_agent/agent/router.py` | OpenCode | Router + circuit breakers |
| `personal_agent/health/model_health.py` | OpenCode | Health registry |
| `personal_agent/health/run_probes.py` | OpenCode | Probe runner |
| `gnw_secrets.py` | Antigravity | DPAPI secret store |
| `refresh_token.py` | Antigravity | Perplexity session refresh |
| `GNW_*.md` | Both | Governance docs (append-only) |

---

## Verification Checklist for Next Session

- [ ] `test_api.py` passes all checks (including API_INVOCATION)
- [ ] Supervisor shows HEALTHY state
- [ ] Model health registry shows ≥5 HEALTHY models
- [ ] Router circuit breakers not tripped on 503
- [ ] NVIDIA Nemotron 3.5 Super VL accessible via OpenCode
- [ ] No secrets in any logs or output files
- [ ] Git status clean (or documented dirty files)

---

## Cryptographic Closure
All evidence in `GNW_EVIDENCE.md` is reproducible via commands shown.
No secrets, tokens, or credentials appear in any governance file.
Append-only invariant maintained: all GNW_*.md files created, none modified after creation.