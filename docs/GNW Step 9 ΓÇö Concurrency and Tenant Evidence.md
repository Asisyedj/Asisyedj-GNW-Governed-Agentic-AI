# GNW Step 9 — Concurrency and Tenant Evidence

**Status:** Application-level tenant and replay controls are implemented and covered by regression tests. Managed PostgreSQL multi-instance evidence remains pending.

## Analysis

Concurrency is a database property, not merely a unit-test property. GNW therefore treats nonce uniqueness, approval races, audit ordering, budget reservation, interlock reads, and tenant scoping as durable transaction concerns. The existing schema includes unique nonce constraints and the repository keeps tenant-bound reads in the application path.

## Evidence already present

The regression suite covers replay refusal, approval binding, separation of duties, interlock STOP, capability lease binding, memory tenant isolation, and API tenancy. The PostgreSQL concurrency test is deliberately skipped without an explicit `GNW_TEST_POSTGRES_URL`, preventing false certification.

## Required external run

Run two GNW instances against one TLS PostgreSQL service. Execute concurrent nonce claims, approval reviews, provider submissions, audit appends, budget reservations, and tenant reads. Record engine/version, instance identifiers, workers, timestamp, artifact digest, result, and cleanup. Repeat after a clean restore.

**Decision:** code controls accepted; production/certification gate remains pending real multi-instance evidence.

**Next step:** Step 10 — recovery and rotation.
