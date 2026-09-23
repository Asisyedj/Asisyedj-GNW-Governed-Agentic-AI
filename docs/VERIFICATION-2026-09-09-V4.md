# GNW v4 Verification — 2026-09-09

**Decision: CONTROLLED STAGING / RELEASE BLOCKED**

## Evidence

| Gate | Result |
|---|---|
| Server syntax/transpile | PASS — 18 files, 0 failures |
| Capability lease signature | PASS |
| Capability substitution rejection | PASS |
| Capability expiry rejection | PASS |
| Audit exact-reason hashing | PASS |
| LLM/provider/webhook execution-boundary routing | Implemented; full runtime untested |
| Provider poll governance | Implemented; live provider untested |
| Artifact storage governance | Implemented; full runtime untested |
| IPv6/private destination hardening | Implemented; live DNS/egress untested |
| npm install | BLOCKED — registry unavailable |
| Vitest suite | BLOCKED — Vitest unavailable without install |
| Typecheck | BLOCKED — local type packages unavailable |
| Build | BLOCKED — Vite/esbuild unavailable |
| Migration | BLOCKED — tsx unavailable |
| Docker | BLOCKED — Docker unavailable |
| S3 dependency | BLOCKED — `@aws-sdk/client-s3` not declared and registry unavailable |
| Postgres multi-instance | UNPROVEN |
| KMS/HSM | UNPROVEN |
| Real egress/provider integration | UNPROVEN |
| Backup/restore | UNPROVEN |

## Release rule

Production remains **DENY** until all P0/P1 gates have executable evidence and no security-critical blocker is unresolved.
