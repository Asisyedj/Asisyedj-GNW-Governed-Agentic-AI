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

**Branch-level mitigation committed:** `.github/workflows/gnw-integration-validation.yml` now adds a push trigger for `integration/**`, a pull-request trigger targeting the phase-5 remediation branch, and manual `workflow_dispatch`. It runs clean install, typecheck, full and targeted security/effect-fence tests, static sink checks, build, dependency audit, release-gate regression checks and Python smoke suites. It uses read-only contents permissions and pins `actions/checkout` and `actions/setup-node` to full commit SHAs. Source-only path filters avoid running code CI for docs-only edits.

**Observed runs:** early CI runs failed on a false-negative scanner pattern; the scanner was aligned to `executeFencedExternal()` and a follow-up regex escaping defect was corrected. On run `38968494285`, all 122 full-suite tests, 30 targeted tests, typecheck, static sink scan, sink contract check and build passed; dependency audit then correctly failed on 1 high and 3 critical advisories. The dependency remediation run `38969502631` subsequently passed the no-force lockfile remediation, dependency audit, typecheck, full and targeted tests, sink checks, build, Python council tests and all seven OpenClaw offline package test files, and then committed the remediated lockfile as commit `db2d4600c2ec18b170e330df89fbf4abfcea00b2`. A separate integration run started in parallel before that lockfile commit (`38969502670`) still failed its dependency audit against the old lockfile. A PR-triggered validation run on the current lockfile commit is required to provide a final green status for the exact final head.

**Status:** one bounded dependency-remediation workflow is PASS; the regular integration workflow on the final head remains pending.

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
- The integration branch was based on phase-5 remediation commit `7f408afc7e5feadc1649cc44e75ba8b2c0c5d162` to avoid mixing this change with the divergent `main` history. The branch head at the end of this audit is `db2d4600c2ec18b170e330df89fbf4abfcea00b2`. `main` has not been changed or merged.
- The uploaded Evaluation Specification was supplied twice with the same SHA-256 and identical bytes; only one canonical copy is committed.
- The PDF research package's SHA-256 is recorded in the source manifest, but the original PDF binary is not included in this document-only commit. The six Markdown specifications are stored as text for review. The uploaded `SKILL (1).md` and `SKILL (2).md` files are tool instruction material rather than GNW product documentation and are intentionally not committed.

## Fresh integration evidence (2026-10-17)
- Current branch lockfile GitHub blob SHA: `0c432f05d131d1219f1ece2ee18ba22382b81033`; SHA-256: `247fa8285f3931ecd2ffb438702dcd30e01a2de28394126b088d9a3d7745f57b`.
- Remediated transitive versions read back from the committed lockfile: `proxy-addr@2.0.8`, `shell-quote@1.12.0`, `source-map-js@1.2.2`, `concurrently@9.2.5`. `gnw/package.json` is unchanged.
- [Dependency remediation run](https://github.com/Asisyedj/Asisyedj-GNW-Governed-Agentic-AI/actions/runs/38969502631) finished successfully. It recorded a clean install, `npm audit --audit-level=high`, TypeScript typecheck, 122 passing application tests, 30 passing targeted security/effect-fence tests, passing static and external sink gates, build, Python council tests, and the seven-package offline test runner. The commit step wrote the lockfile separately to the integration branch.
- [Integration CI run on the pre-remediation checkout](https://github.com/Asisyedj/Asisyedj-GNW-Governed-Agentic-AI/actions/runs/38969502670) failed at dependency audit because it checked out the branch before the lockfile promotion landed; do not treat that run as validation of the current lockfile.
- The PR-triggered integration CI run on the final head must pass before calling branch validation complete. The local Windows device remained offline, so no local user-device test was run.

## Acceptance status
- **Source-document integration:** PASS; all six canonical Markdown files were fetched back and compared byte-for-byte against uploaded sources.
- **CI workflow integration:** CONFIGURED; action refs are pinned to verified full SHAs with read-only permissions in the test workflow.
- **Dependency remediation candidate:** PASS in isolated GitHub Actions; lockfile fix now committed on the integration branch.
- **Final-head integration CI:** PENDING PR-triggered validation.
- **100-case evidence gate and cryptographic release attestation:** BLOCKED / UNPROVEN.
- **Production release and certification:** DENIED / NOT ESTABLISHED.

## Official references
- GitHub Actions secure-use guidance: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub REST API — Git trees: https://docs.github.com/en/rest/git/trees
- SLSA build provenance specification: https://slsa.dev/spec/v1.0/build-provenance
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- OWASP SSRF Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- PostgreSQL row security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- NIST SP 800-218 SSDF v1.1: https://csrc.nist.gov/pubs/sp/800/218/final
