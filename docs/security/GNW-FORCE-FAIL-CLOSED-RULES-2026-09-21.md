# GNW FORCE-FAIL-CLOSED RULES — 2026-09-21

These rules are normative for release authorization. They cannot be bypassed by changing a ledger value, documentation claim, or human override.

## State machine

`BLOCKED` is the default. A release may advance only when the validator for the current state returns success and all required evidence is fresh, linked, hash-verified, and RC-specific.

`BLOCKED -> RELEASE_CANDIDATE_ONLY -> ELIGIBLE_FOR_CONTROLLED_ROLLOUT`

`ELIGIBLE_FOR_CONTROLLED_ROLLOUT` is not general availability; it requires bounded deployment, rollback, monitoring, and active kill-switch controls.

## Mandatory rules

1. Unknown/absent/malformed/stale/contradictory/unsigned/unlinked/unverifiable mandatory evidence => BLOCKED.
2. Static code/configuration/documentation is not runtime PASS evidence.
3. Historical test results are not current release evidence unless re-bound to the exact RC and freshness requirements.
4. `UNPROVEN`, `BLOCKED`, or `FAIL` can never be promoted to PASS by assertion.
5. Every PASS must have the required execution trace, expected/actual result, audit evidence, side-effect result, regression result, timestamp, and reviewer/authority metadata required by its gate.
6. Any source, lockfile, Dockerfile, deployment, runtime-config, artifact, or image change after evidence freeze invalidates affected evidence and requires a new RC.
7. Human approval cannot override a mandatory failed/blocked/unproven/integrity gate.
8. Self-review is not independent review.
9. Self-generated signing is not authorized provenance unless the signing authority is explicitly authorized.
10. The exact distribution artifact is bound using a detached manifest; self-referential artifact hashing is prohibited.
11. Production-ready is false until all mandatory gates and authority gates pass.
12. If required production infrastructure or credentials are unavailable, the correct result is BLOCKED—not PASS by simulation or placeholder.

## IRS rule

IRS-001..IRS-100 must each contain real evidence. Structural presence of 100 records is not evidence completeness. A PASS record requires non-placeholder execution/evidence fields and `regression: PASS`. Any FAIL/BLOCKED/UNPROVEN record blocks the release.

## Supply-chain rule

The exact final distribution digest, SBOM, provenance, and authorized signature must refer to the same artifact. Any mismatch invalidates release evidence.

## Final gate rule

The final gate must fail closed if any required validator exits non-zero.
