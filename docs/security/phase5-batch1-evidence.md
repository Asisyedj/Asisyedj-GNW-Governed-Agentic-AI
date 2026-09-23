# GNW Phase 5 — Batch 1 Evidence

**Execution date:** 2026-09-15

## Scope

This batch records only security subjects for which the existing executable tests produced direct runtime evidence. No unexecuted or design-only control was promoted to `PASS`.

## Results

| Subject | Control | Result | Evidence |
|---|---|---:|---|
| IRS-031 | Grant signature tampering | PASS | `tests/security-v3.test.ts:17-23` |
| IRS-038 | Capability lease binding | PASS | `tests/phase3-security-boundaries.test.ts:85-145` |
| IRS-040 | Final interlock / stale lease fencing | PASS | `tests/phase3-security-boundaries.test.ts:48-82` |
| IRS-061 | Egress allowlist | PASS | `tests/egress-interlock.test.ts:10-16` |
| IRS-062 | HTTPS and URL credential enforcement | PASS | `tests/egress-interlock.test.ts:5-8` |
| IRS-063 | Private and local destination blocking | PASS | `tests/egress-interlock.test.ts:10-14` |
| IRS-064 | Cloud metadata destination blocking | PASS | `tests/egress-interlock.test.ts:10-14` |

The targeted run completed with **3 test files passed and 9 tests passed**. The raw terminal output is stored beside this report as `phase5-batch1-vitest.log`.

## Ledger disposition

The 100-subject ledger now reports `PASS=7`, `FAIL=0`, `BLOCKED=0`, and `UNPROVEN=93`. The validator therefore continues to return a non-zero exit and the release remains blocked. This is intentional fail-closed behavior.

## Docker blocker disposition

The original production gate failed because the sandbox user lacked access to `/var/run/docker.sock`. The user was added to the existing local `docker` group, and Docker client/server access then succeeded. The subsequent build reached the Docker daemon but failed because the sandbox kernel lacks the legacy `iptables` `raw` table required by the default bridge network. A diagnostic `docker build --network=host` completed successfully.

The production gate now accepts an explicit `DOCKER_BUILD_NETWORK` environment variable and defaults to `default`; no production default was weakened. In this sandbox, the container build can be reproduced with `DOCKER_BUILD_NETWORK=host`. This environment workaround is not evidence of production network isolation.

## CI blocker

GitHub Actions run `34954247179` did not execute any workflow step. The GitHub check annotation states: `The job was not started because your account is locked due to a billing issue.` This is an external GitHub account control-plane blocker, not a repository test failure.
