# GNW — Governed Agentic AI

یہ repository GNW کے **hardened staging candidate** source کو محفوظ audit/import branch میں رکھتی ہے۔

## اہم release status

- Local application tests: pass
- OpenClaw package smoke tests: pass in the remediation worktree
- Local PostgreSQL staging: pass in limited scope
- Production release: **DENIED**
- International certification: **نہیں ہوئی**

Code کی موجودگی production security یا certification کا ثبوت نہیں ہے۔ ہر claim کو executable test، adversarial evidence اور independent review سے verify کرنا ہوگا۔

## Repository layout

- `gnw/` — GNW TypeScript/React/Express/Vite application source
- `openclaw_portable/` — bounded OpenClaw package source and offline behavioral tests
- `VERIFY-ALL.sh` — fail-closed verification entry point
- `SOURCE-ARCHIVE-MANIFEST.json` — frozen source archive identity and boundary
- `GNW-Production-Remediation-Status-2026-09-13.md` — remediation status and remaining blockers
- `AUDIT-AND-READINESS.md` — audit/readiness record

## Reproduce local checks

```bash
cd gnw
npm ci
npm run typecheck
npm test
npm run build
npm audit --audit-level=high
cd ../openclaw_portable
python3 run_order_smoke_tests.py
```

The source archive and release evidence remain fail-closed. In particular, unexecuted 100-case security records, infrastructure-level TLS/RLS/multi-instance evidence, container provenance, independent review, and accredited certification must not be represented as complete.

## Import identity

See `GNW-REPOSITORY-IMPORT-MANIFEST.json` for the exact source bundle digest, frozen source archive digest, import branch, and verification boundary.
