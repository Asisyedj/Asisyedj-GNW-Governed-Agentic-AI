# GNW Step 13 — Limited Production Readiness

**Status:** Limited-production operating model defined; launch is not authorized until all P0 evidence gates pass.

## Proposed scope

One region, one approved customer or internal pilot, one supported deployment profile, restricted tools, manual approval for provider effects, conservative budgets, no broad self-registration, no unrestricted code execution, and a rehearsed rollback.

## Required operating metrics

Track blocked unauthorized effects, approval latency, false positives, sandbox violations, replay attempts, restore success, rollback time, authentication abuse, audit failures, provider failures, and interlock activations. Assign on-call ownership and escalation paths before launch.

## Gate

Limited production is allowed only after dependency, identity, sandbox, PostgreSQL, egress, restore, secret rotation, supply-chain, monitoring, rollback, and independent-review gates pass. Current state remains DENY because several external gates are pending.

**Next step:** Step 14 — certification preparation.
