# GNW Backlog — Prioritized Work Items

## P0: Critical — Safety, Secrets, Catastrophic Risks
- [ ] **COMPLETED** Fix bridge health endpoint (/health returns 200 with {"status":"ok"})
- [ ] **COMPLETED** Fix supervisor auth check to distinguish 401/403 from 503 upstream errors
- [ ] **COMPLETED** Supervisor achieves HEALTHY state when bridge is locally healthy
- [ ] Verify DPAPI secret store integrity (bridge-api-key.txt, perplexity-session.dpapi)
- [ ] Audit gnw_secrets.py for cryptographic closure compliance
- [ ] Ensure no secrets in logs, URLs, or snapshots

## P1: Core Correctness — Router, Imports, Memory, Failed Tests
- [ ] **COMPLETED** Bridge daemon starts and serves /health, /v1/models, /v1/chat/completions
- [ ] **COMPLETED** Supervisor monitors bridge process lifecycle correctly
- [ ] Fix model health probes: distinguish upstream 503 from model-specific failure; OPEN — 15/15 live probes still QUARANTINED on 503 (2026-10-26)
- [ ] **COMPLETED** Resolve circuit breaker tripping on transient 503 — verified by 16 passing router/swarm regression tests (2026-10-26)
- [ ] Validate router fallback ordering matches DEFAULT_TASK_ROUTING priority
- [ ] Run full test suite: `pytest personal_agent/tests/ -v`

## P2: Bridge, Verification, Model Health, Monitoring, Recovery
- [ ] Implement model health probe retry with exponential backoff
- [ ] Add health snapshot persistence/load on supervisor restart
- [ ] Add bridge metrics endpoint (/v1/metrics) for Prometheus scraping
- [ ] Implement graceful shutdown on SIGTERM/CTRL_C_EVENT
- [ ] Add supervisor state persistence (JSON) for crash recovery

## P3: Multi-Agent Coordination, Isolated Work, Safe Result Merge
- [ ] Define Antigravity ↔ OpenCode handoff protocol (GNW_OPEN_CODE_HANDOFF.md)
- [ ] Create .opencode/agents/ for specialized roles (researcher, reviewer, tester, security)
- [ ] Implement file-level locking for concurrent agent edits
- [ ] Add cross-agent state sync via GNW_STATE.json

## P4: Security, Adversarial, Data Integrity, Tool Permissions
- [ ] Penetration test BridgeAuthGate (HMAC timing, auth bypass attempts)
- [ ] Verify SSRF protection: no private IP egress from bridge
- [ ] Audit all subprocess calls for shell injection
- [ ] Implement request size limits (4 MiB cap per governance)

## P5: Infrastructure, Observability, Build, Release, Rollback
- [ ] Add GitHub Actions CI for typecheck, test, audit-chain verify
- [ ] Create Dockerfile for bridge daemon (multi-arch)
- [ ] Implement blue/green deployment for bridge updates
- [ ] Add rollback procedure documentation

## P6: Latency, Cost, Resource Metrics
- [ ] Benchmark bridge latency p50/p95/p99 per model
- [ ] Track Perplexity API cost per model per 1M tokens
- [ ] Optimize supervisor check interval (currently 30s)

## P7: Verified Research, Architecture, Documentation, 10-Year Plan
- [ ] Document NVIDIA model integration (Nemotron 3.5 Super VL 120B A12B)
- [ ] Research Nemotron 3.5 Bolt E4B availability
- [ ] Write architecture decision records (ADRs) for key choices
- [ ] Create 10-year technology roadmap aligned with GNW invariants

---

## Dependency Graph
```
P0 (done) → P1 → P2 → P3 → P4 → P5 → P6 → P7
           ↓
    External: Perplexity upstream 503 (blocks P1 model health)
```

## Current Blockers
1. **Perplexity upstream 503** — All model invocations return 503 Service Unavailable. This is an external dependency; bridge and supervisor are functionally correct.
2. **Circuit breaker trips on 503** — Router treats 503 as hard failure, tripping breakers. Needs distinction between auth failure (401/403) and transient upstream (503).
