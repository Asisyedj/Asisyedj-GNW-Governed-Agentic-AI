# GNW Implemented Governed Evidence Plan

## Implemented in this candidate

The candidate now includes a versioned `GNW.ActionEnvelope.v1` with canonical serialization, parameter digest, provenance fields, risk/policy/budget/nonce context, action digest generation, Ed25519 signing and verification, and approval-to-action digest matching.

Audit proof generation now retrieves all task events without the previous 500-event cap, reports explicit completeness, uses domain-separated Merkle node hashing, supports optional Ed25519-signed proof bundles, and exposes offline bundle verification with separate chain, Merkle, completeness and signature results. The `npm run gnw:verify -- proof.gnwproof [issuer-public-key.pem]` command performs the offline checks.

Capability lease verification now supports expected-audience binding at the external-effect boundary. Persisted single-use lease consumption remains atomic in the database.

MCP security utilities now cover canonical HTTPS resource URIs, resource/audience matching, narrow scopes, exact redirect URI registration, S256 PKCE challenge generation and protected-resource metadata validation. These are validation primitives; a production MCP adapter must still implement the full transport flow and issuer/token validation.

Controlled pilot definitions cover governed code changes, restricted-data research and provider-side submission. The metric evaluator requires zero unauthorized external effects, zero cross-tenant violations, complete evidence and complete replay blocking before a pilot passes.

## Remaining production blockers

This candidate is not a production certification. Real OIDC verification, hostile-code isolation evidence, PostgreSQL/RLS and multi-instance adversarial tests, full MCP transport integration, DNS-rebinding/redirect testing against a live executor, backup/restore anti-resurrection, secret rotation, SBOM/provenance/signing of the release artifact, reproducible build, and independent review remain release gates.

## Verification commands

```bash
npm run typecheck
npm test
npm run build
npm run gnw:verify -- proof.gnwproof issuer-public-key.pem
```

The offline verifier returns `VALID`, `INCOMPLETE` or `INVALID` rather than treating partial evidence as valid proof.
