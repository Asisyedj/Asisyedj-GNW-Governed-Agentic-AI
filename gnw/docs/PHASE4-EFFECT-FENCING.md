# GNW Phase 4 — External Effect Fencing and Provider Idempotency

1. Signed capability leases carry a durable interlock generation.
2. A unique effect fence is persisted before a provider effect.
3. Only one worker can claim READY → IN_FLIGHT for a generation.
4. Provider requests carry a deterministic tenant-scoped `Idempotency-Key` and GNW fence token.
5. Providers MUST enforce idempotency and monotonic fence acceptance. GNW cannot make a remote provider transactionally atomic from its own database.
6. Ambiguous provider failures become `PENDING_RECONCILIATION`; blind retries are forbidden.
7. Production proof requires a real provider contract/test demonstrating duplicate-idempotency convergence and stale-fence no-effect behavior.
