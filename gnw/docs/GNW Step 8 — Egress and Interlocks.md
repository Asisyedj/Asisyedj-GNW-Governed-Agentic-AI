# GNW Step 8 — Egress and Interlocks

**Status:** GNW-side egress and final interlock controls are implemented and regression-tested. Network-level emergency deny and distributed multi-instance proof remain external infrastructure gates.

## Deep analysis

Application allowlisting alone is insufficient because a hostname can resolve to a private address, DNS can change between validation and connection, a redirect can escape the original destination, and an in-flight request cannot be mathematically cancelled by a database flag. The safe design therefore combines URL validation, DNS resolution checks, pinned connection targeting, manual redirects, bounded responses, a durable interlock, and a final check immediately before the effect.

## Implemented controls

| Threat | GNW control | Result |
|---|---|---|
| Plain HTTP | HTTPS-only URL validation | Tested |
| URL credential smuggling | Username/password rejection | Tested |
| Private/local/metadata targets | Host and resolved-address blocking | Tested in existing and new suites |
| Unapproved host | Exact or explicit subdomain allowlist | Tested |
| DNS rebinding window | Resolve all addresses and reject unsafe results before connection | Implemented |
| Redirect escape | Manual redirect policy | Implemented |
| Oversized response | Byte ceiling and request destruction | Implemented |
| Kill switch race | Durable interlock plus final effect-boundary recheck | Implemented |
| Audit failure | Effect path fails closed through the audit admission sequence | Implemented |

## What this proves

GNW will not admit a new external effect when the persistent kill switch or circuit breaker is active. It will not connect to an unapproved, local, private, metadata, or unsafe resolved destination. The final interlock is re-read after audit admission and immediately before the irreversible effect.

## What this does not prove

The application cannot guarantee cancellation of a request already accepted by an external network. Production therefore still requires a network egress proxy or cloud policy with emergency deny, DNS-aware enforcement, centralized observability, and cross-instance propagation testing.

**Next step:** Step 9 — concurrency and tenant evidence.

## References

[1]: https://owasp.org/www-community/attacks/Server_Side_Request_Forgery_Prevention_Cheat_Sheet "OWASP SSRF Prevention Cheat Sheet"
[2]: https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final "NIST Special Publication 800-57 Part 1 Revision 5"
