# GNW Deep Research & GitHub Integration Audit
**Assessment date:** 2026-10-17  
**Repository:** `Asisyedj/Asisyedj-GNW-Governed-Agentic-AI`  
**Integration branch:** `integration/evidence-governance-package-2026-10-17`  
**Base branch:** `remediation/phase5-sandbox-sink-contracts-2026-09-15`  
**Base commit observed before integration:** `7f408afc7e5feadc1649cc44e75ba8b2c0c5d162`

## Decision
**Status: PARTIAL_WITH_BLOCKERS. Production release remains DENIED.** This commit integrates the supplied governance specifications as reviewable source documents only. It does not claim a fresh application test run, production deployment, certification, or completion of the 100 adversarial cases.

## Source-driven findings

### F-01 — Release evidence gate does not cryptographically verify the reviewer signature (P0 before any release)
In `gnw/scripts/validate-release-evidence.mjs`, the validator checks that `review.signature` exists and is not the literal string `MISSING`, but it does not verify the signature against a trusted public key, canonical payload, signer identity, or digest-bound release bundle. The field is therefore presence-checked, not cryptographically verified. The current release manifest remains `BLOCKED`, so this observation is a validator weakness and not evidence that a release was accepted.

**Required remediation:** define a canonical signed statement binding repository, commit/tree SHA, source/archive hash, build identity, artifact digest(s), environment, gate results, reviewer identity and timestamp. Verify the signature with a pinned trust root and reject unknown, revoked or expired reviewer keys. Do not permit the manifest to declare PASS without successful verification.

### F-02 — IRS evidence rows are structurally checked, not independently attested (P0 before any release)
`gnw/scripts/validate-100-evidence.mjs` verifies record count/order, unique IDs, allowed verdicts and several non-placeholder fields for PASS rows. It does not resolve and hash the referenced evidence artifact, bind the evidence to the tested commit/environment, verify the reviewer cryptographically, or reject placeholders in every substantive field (for example, `expected`, `side_effect`, `root_cause`, and `fix`). A non-placeholder `audit_evidence` string alone does not prove an artifact exists or supports the claim.

**Required remediation:** give each record a schema-validated evidence URI/path, SHA-256, test/run ID, source commit/tree digest, environment/container digest, expected/actual result, effect trace, regression run, timestamp with timezone, reviewer identity and verified signature. Resolve the evidence path within an allowlisted evidence root, reject traversal/symlinks, hash the file, verify its run/commit binding and require all mandatory values. Keep all current IRS rows UNPROVEN until actual evidence is collected.

### F-03 — Branch-scoped workflow coverage and integration CI (P1)
The existing phase workflows are branch-scoped. The phase-4 workflow triggers on pushes to `remediation/phase4-rebased-current-2026-09-14` and `workflow_dispatch`; the phase-2 and phase-3 workflows target their own named remediation branches. Those push filters do not cover this integration branch.

**Branch-level mitigation committed:** `.github/workflows/gnw-integration-validation.yml` now adds a push trigger for `integration/**`, a pull-request trigger targeting the phase-5 remediation branch, and manual `workflow_dispatch`. It runs clean install, typecheck, full and targeted security/effect-fence tests, static sink checks, build, dependency audit and Python smoke suites. It uses read-only contents permissions and pins `actions/checkout` and `actions/setup-node` to full commit SHAs. This is a CI configuration change, not proof that a run has succeeded.

**Status:** branch coverage configured; execution remains NOT VERIFIED until an actual Actions run and its logs are inspected.

### F-04 — Legacy GitHub Actions references are tag-pinned (P1)
The pre-existing phase workflows still reference `actions/checkout@v4`, `actions/setup-node@v4`, and `actions/upload-artifact@v4`. GitHub's secure-use guidance recommends full-length action commit SHAs for immutable references. The new integration workflow addresses this for its two actions: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1, signed verified release) and `actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1` (v7.1.0, signed verified release). The legacy branch-specific workflows remain unchanged.

**Status:** mitigated in integration CI only; legacy workflow pinning remains open.

### F-05 — Local fencing tests do not prove PostgreSQL or external-provider guarantees (P0 before production)
The inspected effect-fence unit test uses an in-memory SQLite database. This is useful unit evidence for the tested code path but is not a PostgreSQL multi-session or production provider proof. The repository's own release manifest correctly marks TLS/PostgreSQL multi-instance, DNS rebinding/SSRF, distributed kill switch, backup/restore anti-resurrection, secret rotation, signing/provenance and independent review as BLOCKED.

**Required remediation:** execute fault-injection and concurrency tests on the intended PostgreSQL topology with TLS and production-like roles, including owner/superuser/BYPASSRLS paths; run DNS resolve-bind/redirect/private-address cases at the enforced network boundary; validate provider idempotency/fencing and ambiguous-result reconciliation; perform restore/deletion and kill-switch drills.

### F-06 — Artifact digest output is not attestation verification (P1)
The production gate prints a `sha256sum` for `dist/server/index.js` but uses `|| true`, and does not compare that output with a trusted expected digest or cryptographically signed provenance. A printed digest is useful inventory evidence but is not, on its own, proof of who built an artifact or which inputs were used.

**Required remediation:** fail if the output artifact is absent; create provenance with source and resolved dependency identities; sign and verify provenance and artifact digests against an independently configured trust policy.

### F-07 — Static sink checks are supporting evidence only (P1)
The sink validators inspect TypeScript source and expected source tokens. They do not by themselves prove the runtime network route, a provider's idempotency behavior, DNS pinning, isolation from hostile code, or behavior in a production topology. Treat a static scan result as one gate among runtime negative tests and independent review.

## Repository and branch evidence
- The remediation branch is **10 commits ahead and 2 commits behind `main`** in the comparison retrieved during this audit. The integration branch was based on the remediation phase-5 branch to avoid mixing this document-only change with the divergent main history.
- No combined status checks were returned for the observed base commit. The workflow-run lookup returned no runs; its connector wrapper is limited to PR-triggered runs, so this is not a claim that no run of any kind exists anywhere.
- The uploaded Evaluation Specification was supplied twice with the same SHA-256 and identical bytes; only one canonical copy is committed.
- The PDF research package's SHA-256 is recorded in the source manifest, but the original PDF binary is not included in this document-only commit. The six Markdown specifications are stored as text for review. The uploaded `SKILL (1).md` and `SKILL (2).md` files are tool instruction material rather than GNW product documentation and are intentionally not committed.

## Acceptance status
- **Document integration:** completed in this branch, with each committed Markdown source read back from GitHub for exact-content comparison.
- **Local source tests:** NOT RUN during this operation because the registered local Windows device is offline.
- **Integration GitHub Actions:** workflow configuration committed; combined status and run lookup returned no run at the time of this record. A successful CI run is NOT claimed.
- **100-case evidence gate:** BLOCKED / UNPROVEN.
- **Production release and certification:** DENIED / NOT ESTABLISHED.

## Official references
- GitHub Actions secure-use guidance: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub REST API — Git trees: https://docs.github.com/en/rest/git/trees
- SLSA build provenance specification: https://slsa.dev/spec/v1.0/build-provenance
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- OWASP SSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- PostgreSQL row security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- NIST SP 800-218 SSDF v1.1: https://csrc.nist.gov/pubs/sp/800/218/final
