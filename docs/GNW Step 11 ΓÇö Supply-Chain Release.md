# GNW Step 11 — Supply-Chain Release

**Status:** Build, lockfile installation, typecheck, tests, security sink scan, and artifact hashing are executable. SBOM, provenance, signature verification, and clean-environment release attestation remain pending.

## Required release bundle

The bundle must contain the source revision, lockfile hash, build-runner identity, dependency audit, secret scan, license result, SBOM in SPDX or CycloneDX format, image digest, provenance statement, signature, verification result, test results, and reviewer approval. Every item must bind to the final artifact digest.

## Gate rule

A production gate must fail when SBOM, provenance, signature, evidence bundle, PostgreSQL evidence, restore evidence, or independent review is missing. Unit tests alone cannot change the release decision to PASS.

## Current evidence

The current candidate passes clean dependency installation, typecheck, 101-test regression, build, and raw-fetch sink scanning. The 100-case adversarial ledger remains UNPROVEN, so release status remains DENY.

**Next step:** Step 12 — independent evidence review.
