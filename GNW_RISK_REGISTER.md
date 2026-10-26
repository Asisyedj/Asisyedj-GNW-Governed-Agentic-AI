# GNW Risk Register — Perplexity Browser API Bridge

## Risk Scoring
- **Impact**: 1=Low, 2=Medium, 3=High, 4=Critical
- **Likelihood**: 1=Rare, 2=Unlikely, 3=Possible, 4=Likely, 5=Almost Certain
- **Score** = Impact × Likelihood (max 20)
- **Mitigation Status**: OPEN / MITIGATING / MITIGATED / ACCEPTED

---

## Risks

### R1: Perplexity Upstream Service Unavailable (503)
- **Impact**: 4 (Critical — all model invocations fail)
- **Likelihood**: 5 (Almost Certain — currently occurring)
- **Score**: 20
- **Status**: OPEN
- **Description**: All `/v1/chat/completions` requests return HTTP 503 Service Unavailable. Bridge and supervisor are functionally correct but cannot complete inference.
- **Mitigation**:
  - [ ] Monitor Perplexity status page / support channels
  - [ ] Implement local model fallback (Ollama, llama.cpp) for critical paths
  - [ ] Add circuit breaker distinction: 503 ≠ auth failure (partially done in supervisor)
  - [ ] Router circuit breaker should not trip on 503 (PENDING)
- **Owner**: Antigravity (external dependency)
- **Detection**: test_api.py API_INVOCATION=FAIL; supervisor auth check logs

### R2: Router Circuit Breaker Trips on Transient 503
- **Impact**: 3 (High — models permanently quarantined until manual reset)
- **Likelihood**: 4 (Likely — occurs on every probe attempt)
- **Score**: 12
- **Status**: OPEN
- **Description**: `ModelRouter.record_failure()` treats all exceptions equally. 503 increments consecutive_failures, tripping breaker to OPEN after 3 failures. No automatic recovery for 503.
- **Mitigation**:
  - [ ] Modify `record_failure()` to accept error classification
  - [ ] Add `is_transient_error(exc)` helper (503, 429, timeout)
  - [ ] Transient errors should not increment consecutive_failures or trip breaker
  - [ ] Add recovery timeout for transient errors separate from auth failures
- **Owner**: OpenCode (this session)
- **Detection**: Circuit breaker logs show "TRIPPED to OPEN after 3 consecutive failures (error: Server error '503')"

### R3: Bridge Process Port Conflict on Restart
- **Impact**: 2 (Medium — supervisor restart fails, requires manual intervention)
- **Likelihood**: 3 (Possible — observed during testing)
- **Score**: 6
- **Status**: MITIGATING
- **Description**: When supervisor restarts bridge, old process holds port 8000 during TIME_WAIT. New process fails with `Errno 10048`. Lock file logic reuses PID but port bind fails.
- **Mitigation**:
  - [ ] Add `SO_REUSEADDR` socket option to uvicorn config
  - [ ] Increase supervisor restart cooldown (currently 60s)
  - [ ] Implement graceful shutdown with port release wait
  - [ ] Add port conflict detection and retry logic in `_start_bridge_process`
- **Owner**: OpenCode
- **Detection**: Supervisor logs show "error while attempting to bind on address ('127.0.0.1', 8000): [winerror 10048]"

### R4: DPAPI Secret Store Corruption / Loss
- **Impact**: 4 (Critical — bridge cannot start without secrets)
- **Likelihood**: 2 (Unlikely — Windows DPAPI is robust)
- **Score**: 8
- **Status**: MITIGATED
- **Description**: Bridge keys stored in DPAPI. If user profile corrupted or machine changed, secrets unrecoverable.
- **Mitigation**:
  - [x] Document secret backup procedure (export to encrypted file)
  - [x] `gnw_secrets.py` provides clear error messages on failure
  - [ ] Implement secret rotation workflow
- **Owner**: Antigravity
- **Detection**: `get_bridge_key()` / `get_session_token()` raise clear exceptions

### R5: SSRF / Private IP Egress from Bridge
- **Impact**: 4 (Critical — violates GNW Invariant #5)
- **Likelihood**: 1 (Rare — bridge binds to 127.0.0.1 only)
- **Score**: 4
- **Status**: MITIGATED
- **Description**: Bridge daemon binds explicitly to `127.0.0.1:8000`. No external network access configured.
- **Mitigation**:
  - [x] `uvicorn.run(app, host="127.0.0.1", port=8000)` — loopback only
  - [x] `BridgeAuthGate` only processes `/v1/*` paths with valid HMAC
  - [x] No outbound HTTP client in bridge daemon
- **Owner**: OpenCode
- **Detection**: Code review confirms loopback binding

### R6: Secrets in Logs / URLs / Snapshots
- **Impact**: 4 (Critical — violates GNW Invariant #5)
- **Likelihood**: 2 (Unlikely — code review shows no logging of secrets)
- **Score**: 8
- **Status**: MITIGATED
- **Description**: Bridge key and session token must never appear in logs, URLs, query strings, or health snapshots.
- **Mitigation**:
  - [x] Supervisor logs only state transitions, PIDs, counts
  - [x] Health snapshots contain only model IDs, latency, error strings (no tokens)
  - [x] test_api.py prints only status codes and counts
  - [ ] Add automated secret scanning to CI
- **Owner**: OpenCode
- **Detection**: Manual review of all log outputs in GNW_EVIDENCE.md

### R7: Model Health Registry State Loss on Restart
- **Impact**: 2 (Medium — probes must re-run, but catalog reloads)
- **Likelihood**: 4 (Likely — in-memory only, no persistence)
- **Score**: 8
- **Status**: OPEN
- **Description**: `ModelHealthRegistry` stores state in memory. Supervisor restart or process crash loses all probe results. `health_snapshot.json` written but not loaded on startup.
- **Mitigation**:
  - [ ] Implement `load_snapshot()` in `ModelHealthRegistry.__init__`
  - [ ] Add atomic write + rename for snapshot durability
  - [ ] Consider SQLite persistence for audit trail
- **Owner**: OpenCode
- **Detection**: Fresh Python process shows 0 healthy models despite prior probes

### R8: NVIDIA Free Tier Rate Limits / Quota Exhaustion
- **Impact**: 3 (High — blocks research/model access)
- **Likelihood**: 3 (Possible — free tier has unknown limits)
- **Score**: 9
- **Status**: OPEN
- **Description**: NVIDIA models via OpenCode are free but undocumented rate limits. No quota monitoring implemented.
- **Mitigation**:
  - [ ] Implement request counting per model per time window
  - [ ] Add 429 handling with exponential backoff
  - [ ] Document observed limits in GNW_EVIDENCE.md
- **Owner**: OpenCode
- **Detection**: HTTP 429 responses from OpenCode provider

### R9: Cross-Agent File Conflict (Antigravity ↔ OpenCode)
- **Impact**: 3 (High — lost work, corrupted state)
- **Likelihood**: 2 (Unlikely — with proper coordination)
- **Score**: 6
- **Status**: MITIGATING
- **Description**: Two agents editing same files simultaneously. GNW governance requires file-level coordination.
- **Mitigation**:
  - [x] GNW_STATE.json tracks current phase and ownership
  - [x] GNW_OPEN_CODE_HANDOFF.md documents handoff protocol
  - [ ] Implement file lock protocol (`.gnw.lck` files)
  - [ ] Define edit zones per agent in BACKLOG
- **Owner**: Both agents
- **Detection**: Git status shows concurrent modifications

### R10: Supervisor Background Thread Silent Death
- **Impact**: 3 (High — monitoring stops without alert)
- **Likelihood**: 2 (Unlikely — daemon thread, but exceptions caught)
- **Score**: 6
- **Status**: MITIGATED
- **Description**: Supervisor `_run()` loop catches all exceptions and logs them. Thread is daemon=True.
- **Mitigation**:
  - [x] Exception handler logs full traceback
  - [x] Thread is daemon (exits with process)
  - [ ] Add heartbeat file write for external watchdog
  - [ ] Add `is_alive()` check in status() for external monitoring
- **Owner**: OpenCode
- **Detection**: Status shows stale timestamp, no state transitions

---

## Risk Summary

| Risk ID | Title | Score | Status |
|---------|-------|-------|--------|
| R1 | Perplexity Upstream 503 | 20 | OPEN |
| R2 | Circuit Breaker on 503 | 12 | OPEN |
| R3 | Port Conflict on Restart | 6 | MITIGATING |
| R4 | DPAPI Secret Loss | 8 | MITIGATED |
| R5 | SSRF / Private IP Egress | 4 | MITIGATED |
| R6 | Secrets in Logs | 8 | MITIGATED |
| R7 | Health State Loss on Restart | 8 | OPEN |
| R8 | NVIDIA Rate Limits | 9 | OPEN |
| R9 | Cross-Agent Conflict | 6 | MITIGATING |
| R10 | Supervisor Thread Death | 6 | MITIGATED |

**Top 3 Risks Requiring Action:**
1. R1 — External dependency (monitor, escalate to Antigravity)
2. R2 — Router fix needed (code change in this repo)
3. R8 — Quota monitoring (observability gap)

---

## Risk Acceptance Decisions

- **R1 (Perplexity 503)**: ACCEPTED as external dependency. Bridge/supervisor are functionally correct. Monitoring in place.
- **R5, R6 (Security)**: MITIGATED by design (loopback binding, no secret logging). Continuous verification required.
- **R4 (DPAPI)**: MITIGATED by Windows platform guarantee. Backup procedure documented separately.