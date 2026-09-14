# Acceptance checklist

Run this against a deployed instance before declaring it live. `npm test` covers the same ground automatically (37 assertions across the governance matrix, the audit chain and the HTTP routes); this list verifies the deployment itself.

Set `BASE=https://your-instance` and keep a cookie jar: `curl -c jar -b jar -H 'x-gnw-client: web'`.

## 1. Platform

- [ ] `GET $BASE/api/health` returns `200 {"status":"ok"}`.
- [ ] `GET $BASE/api/ready` returns 200 and `checks.database` is `ok`.
- [ ] The client loads over HTTPS and a deep link such as `/approvals` resolves (SPA fallback works).
- [ ] Response headers include `x-content-type-options`, `x-frame-options` and a content security policy.
- [ ] Boot is refused with a short `SESSION_SECRET`, and on Vercel with a SQLite `DATABASE_URL`.

## 2. Identity and tenancy

- [ ] The first account becomes admin; a second self-registration is refused unless `ALLOW_SELF_REGISTRATION=true`.
- [ ] `GET /api/workspace/summary` without a cookie returns 401.
- [ ] A `POST` without the `x-gnw-client: web` header returns 403 `csrf_header_required`.
- [ ] Ten wrong passwords in a row return 429.
- [ ] A second account cannot read the first account's task (404, not 403 — no existence leak).

## 3. Governed execution

- [ ] A task with research, analysis and QA completes; each specialist shows an `ALLOW` admission in the audit trail.
- [ ] A task classified `restricted` stops at `awaiting_approval` instead of executing.
- [ ] Denials appear in the audit trail with a reason, not just successes.

## 4. Approval and replay

- [ ] A video task produces three distinct artefacts (brief, script, storyboard) and a pending approval.
- [ ] `POST /api/video/submit` **before** approval returns 403 `approval_required`.
- [ ] A different tenant cannot review that approval.
- [ ] A non-admin requester cannot approve their own request (`separation_of_duties`).
- [ ] After approval, the first submit succeeds and the second returns 403 `approval_replay`.
- [ ] A denied approval leaves its job `stopped` and refuses submission.
- [ ] An approval past its expiry refuses submission.

## 5. Safety interlocks

- [ ] A member cannot change the interlocks; an admin can.
- [ ] With the kill switch engaged, a new task returns 423 `safety_interlock`.
- [ ] Restart the process: the kill switch is still engaged (state is in the database, not memory).
- [ ] Clearing the switch restores normal admission.

## 6. Evidence

- [ ] `GET /api/audit/verify` reports `valid: true` after the full workflow above.
- [ ] Edit one audit row directly in the database; verification reports `valid: false` and names the broken row.
- [ ] Restore the row from backup and confirm verification passes again.

## 7. Durability

- [ ] Restart the app: tasks, approvals, audit events and notifications are all still present.
- [ ] Artifacts resolve from the configured store (mounted volume or S3), not from the app's ephemeral filesystem.
- [ ] With Postgres, run two instances behind a load balancer and confirm a replayed approval is refused by the instance that did not perform the first submission.
