# Release Gates

| Gate | Requirement | Pass condition |
|---|---|---|
| G1 Source/provenance | All declared paths have authoritative bytes | Zero missing and zero unexplained mismatches |
| G2 Governance authority | Independent authority controls context | Machine-verifiable decision before PEP |
| G3 Crypto authorization | Signed grant and trusted issuer | All bindings, expiry and replay tests pass |
| G4 Approval/PEP | Approval is independently validated | No request-to-tool bypass |
| G5 Tool/model permission | Least-privilege gateways | Unknown or unauthorized capability denied |
| G6 Safety interlocks | Budget, kill switch, breaker, cancellation | All negative tests pass |
| G7 Filesystem | Synthetic read-only path gateway | Unsafe namespace and escape denied |
| G8 Audit | Admission before operation | Tamper-evident evidence and fail-closed audit |
| G9 Adversarial | Complete negative matrix | Every required case passes |
| G10 Synthetic E2E | Full governed read-only trace | Reproducible trace with no side effects |
| G11 Independent audit | Separate reviewer checks frozen evidence | No unresolved blocker |
| G12 Production authorization | Explicit human authorization packet | Separate approval; never inferred |

Current original project status remains `DENY / NOT READY / BLOCKED`. This sandbox pack does not pass or alter those gates.
