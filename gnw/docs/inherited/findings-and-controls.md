# Findings and Control Matrix

## Current known project findings

| Finding | Status | Evidence boundary |
|---|---|---|
| Manifest declares 156 paths | VERIFIED local fact | Existing local manifest |
| 138 paths unavailable in approved local sources | VERIFIED local reconciliation | Prior exact path scan |
| 6 archive-only checksum mismatches | VERIFIED local fact | Prior byte-level SHA-256 comparison |
| 12 repository files checksum-match | VERIFIED local fact | Prior SHA-256 comparison |
| Partial baseline tests pass 11/11 | TESTED local subset | Prior unittest output |
| Full package is complete | NOT ESTABLISHED | Missing source and mismatch blockers |
| Production readiness | NOT PRODUCTION READY | No full source, E2E or production evidence |

## Control matrix

| Control | Sandbox status | Production claim |
|---|---|---|
| Trusted identity | BLOCKED | Not proven |
| Tenant binding | BLOCKED | Not proven |
| Role binding | BLOCKED | Not proven |
| Purpose/classification | PARTIAL | Not proven |
| Signed AuthorizationGrant | NOT IMPLEMENTED | Not proven |
| Asymmetric signature verification | NOT IMPLEMENTED | Not proven |
| Approval validation | PARTIAL | Not proven |
| PEP | PARTIAL scaffold | Not proven |
| Tool permission | PARTIAL scaffold | Not proven |
| Model permission | PARTIAL scaffold | Not proven |
| Budget/limits | PARTIAL | Not proven |
| Kill switch | TESTED synthetic | Not production proven |
| Circuit breaker | TESTED synthetic | Not production proven |
| Replay/expiry | TESTED synthetic | Not production proven |
| Audit admission | BLOCKED | Not proven |
| Immutable audit | BLOCKED | Not proven |
| Windows filesystem gateway | BLOCKED | Real C:\ prohibited |
| Prompt-injection resistance | BLOCKED | Not proven |
| External integrations | BLOCKED | No live calls |

## Blocking interpretation

This pack improves the local reference design but does not repair the original incomplete artifact. Missing sources remain missing. No generated file is authoritative for the original project.
