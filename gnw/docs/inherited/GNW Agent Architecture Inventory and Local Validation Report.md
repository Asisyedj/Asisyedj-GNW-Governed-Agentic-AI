# GNW Agent Architecture Inventory and Local Validation Report

**Status:** `DENY / NOT READY / BLOCKED` for production or external integration claims.

**Scope:** This report covers only the locally available project material at `/home/ubuntu/projects/gnw-3daeef70` and the contents of `wnoa-agent-architecture-complete-pack.zip`. It does not inspect real Windows paths, remote destinations, external services, credentials, provider accounts, or production deployments.

## 1. Executive conclusion

The current project folder contains **one ZIP archive** and no additional extracted source tree. The archive is a coherent draft sandbox pack containing a small Python governance reference implementation, its unit tests, five Markdown design documents, five Mermaid diagram sources, and five rendered PNG diagrams.

The pack provides a **generic governed multi-agent architecture pattern**. It does not contain an implementation of Manus, Q*, Perplexity Computer, OpenAI Operator, a browser computer-use agent, or any other named commercial agent. A name scan found only generic terms such as `Research Agent`, `Analysis Agent`, `Engineering Agent`, and `QA Agent`.

The strongest local evidence is the synthetic Python gateway and its **13 passing unit tests**. This proves only that the supplied local test cases pass against the supplied synthetic code. It does not prove real identity, real cryptography, production authorization, Windows filesystem safety, external-provider behavior, deployment safety, or integration with any agent product.

A material evidence inconsistency exists inside the pack. `docs/findings-and-controls.md` reports a 156-path manifest, 138 unavailable paths, six checksum mismatches, and twelve checksum matches, but the current archive contains 21 members and no manifest or source evidence for those prior reconciliation claims. Those statements are therefore treated as stale or unverified context, not as current authoritative inventory facts.

## 2. What is physically present

The project directory contains:

| Path | Local fact |
|---|---|
| `wnoa-agent-architecture-complete-pack.zip` | ZIP archive; integrity test passed with no errors |
| No extracted `src/`, `tests/`, `docs/`, or `diagrams/` directories | The directories exist only inside the archive in the current project folder |
| No Dart-named folder or Dart source file | No `.dart` files were present in the archive listing |

The archive contains **21 members**: 16 text/source files, five PNG renders, and directory entries. After extraction, Python generated two `__pycache__` files during testing; those are test artifacts, not archive members.

### Complete archive member inventory

| Archive member | Size | Type | Purpose |
|---|---:|---|---|
| `README.md` | 2,391 bytes | Markdown | Scope, status, run command, and file map |
| `src/governed.py` | 5,238 bytes | Python | Fail-closed synthetic governance and read gateway |
| `tests/test_governed.py` | 3,857 bytes | Python | 13 local unit tests |
| `docs/roles-and-agents.md` | 2,158 bytes | Markdown | Logical roles and trust boundaries |
| `docs/findings-and-controls.md` | 2,041 bytes | Markdown | Findings and control status matrix |
| `docs/adversarial-test-matrix.md` | 1,871 bytes | Markdown | 36 negative-test expectations |
| `docs/release-gates.md` | 1,364 bytes | Markdown | Twelve release gates |
| `diagrams/01-system-context.mmd` | 402 bytes | Mermaid | System context |
| `diagrams/02-governance-authority.mmd` | 442 bytes | Mermaid | Authority chain |
| `diagrams/03-multi-agent-trust.mmd` | 395 bytes | Mermaid | Multi-agent trust propagation |
| `diagrams/04-execution-gateway.mmd` | 410 bytes | Mermaid | Gateway and blocked capabilities |
| `diagrams/05-audit-sequence.mmd` | 517 bytes | Mermaid | Pre-action and result audit sequence |
| `diagrams/01-system-context.png` | 159,070 bytes | PNG | Rendered system context diagram |
| `diagrams/02-governance-authority.png` | 28,896 bytes | PNG | Rendered governance diagram |
| `diagrams/03-multi-agent-trust.png` | 171,720 bytes | PNG | Rendered multi-agent diagram |
| `diagrams/04-execution-gateway.png` | 125,991 bytes | PNG | Rendered gateway diagram |
| `diagrams/05-audit-sequence.png` | 109,723 bytes | PNG | Rendered audit sequence diagram |

The text files contain **451 lines** in total: 136 lines of implementation, 78 lines of tests, 132 lines of documentation, and 53 lines of Mermaid source.

## 3. Architecture represented by the pack

The architecture is organized around a central rule: **model and agent output is untrusted data; governance is the only authority**.

### 3.1 Request and governance context

`src/governed.py` defines a `Request` record with the required context fields: request ID, subject, tenant, role, purpose, classification, operation, resource, tool, scope, and a byte budget. This corresponds to the project instruction that missing or unverifiable context must fail closed.

The implementation does not independently validate that every string is non-empty or that the subject is a real trusted identity. The field exists in the data model and is used for binding checks, but real identity verification is not implemented.

### 3.2 Authorization grant

`AuthorizationGrant` carries request binding, subject, tenant, role, purpose, operation, resource, scope, issuer, issue time, expiry time, nonce, and signature. `Governance._check_grant` checks the bindings, time window, replay set, and injected verifier.

The included `SyntheticSignatureVerifier` accepts exactly the issuer `synthetic-test-issuer` and the bytes `TEST-SIGNATURE`. This is deliberately a deterministic test stub. It is **not asymmetric cryptography, not a trust store, and not a production signature verifier**.

### 3.3 Approval binding

`Approval` is bound to the request ID, authorization ID, tenant, action digest, expiry, and a nonce. The implementation validates request, grant, tenant, digest, and expiry. The approval nonce is stored but is not replay-tracked in the current code. Approval issuer or approver identity is also not represented.

### 3.4 Policy enforcement and gateway

`Governance.read_synthetic` is the only execution-like entry point. It checks the kill switch and circuit breaker, permits only the `synthetic_read` tool, permits only the `read` operation, requires a positive byte budget, validates the grant and approval, appends an audit event, and returns the fixed value `SYNTHETIC_READ_RESULT`.

The code contains no filesystem read. The resource string `synthetic://fixture` is only test data. Therefore the implementation is safer than a real filesystem gateway, but it also does not prove Windows path, junction, symlink, reparse-point, UNC, device-path, or remote-destination handling.

### 3.5 Audit design

The code appends `AuditEvent` objects to an in-memory Python list. It records request ID, decision, reason, and operation. The diagrams and documents propose pre-action admission followed by a controlled result event, but the current Python implementation records one allow or deny event and does not implement an immutable ledger, durable storage, tamper evidence, or unavailable-ledger fail-closed behavior.

### 3.6 Multi-agent trust model

The multi-agent diagram shows an untrusted orchestrator coordinating research, analysis, engineering, and QA agents. It routes their context through a signed context envelope, governance authority, a mandatory PEP, and a tool gateway. The role document explicitly states that these are logical design roles, not permissions, connectors, schedules, credentials, or production agents.

The pack therefore models **agent coordination and trust boundaries**, not autonomous agents with working model calls, memory, browser control, tools, connectors, schedules, or provider integrations.

## 4. File-by-file findings

### `README.md`

This is the pack-level scope and status document. It explicitly labels the pack `DRAFT / TEST ONLY / NOT DEPLOYED`, lists eleven architecture families, gives the local unittest command, and states that local tests do not prove production integration. It is consistent with the fail-closed project instructions except for the separate stale claims found in the findings matrix.

### `src/governed.py`

This is the only executable production-like source file. It defines three data records (`Request`, `AuthorizationGrant`, and `Approval`), one audit record, two exception classes, a verifier protocol, a synthetic verifier, and a `Governance` class. It implements binding checks, time checks, nonce replay prevention for grants, approval checks, a tool/operation allow-list, budget positivity, kill switch, circuit breaker, audit append, and a fixed synthetic read result.

Important limitations are explicit in its module docstring: no network, subprocess, database, provider, model, workflow, or real filesystem access; injected signature verification; and test-only verification.

### `tests/test_governed.py`

The test suite has 13 cases. It covers one positive synthetic read and denial or stop behavior for missing approval, invalid signature, wrong tenant, wrong scope, expired grant, grant replay, wrong approval digest, unknown tool, write operation, invalid budget, kill switch, and circuit breaker.

It does not cover all 36 adversarial matrix rows. It does not test identity validation, classification mismatch, untrusted issuer as a separate case, future grants, approval replay, approval identity, audit unavailability, path traversal, reparse points, remote destinations, prompt injection, tool poisoning, context-envelope loss, or external capability attempts.

### `docs/roles-and-agents.md`

This document defines ten logical roles: Governance Orchestrator, Evidence-First Research Specialist, Deep Analysis Specialist, Prompt Engineering Specialist, Agent Architecture Specialist, Python/Node Engineering Specialist, Workflow Design Specialist, Knowledge Cataloging Specialist, Security Threat Modeling Specialist, and QA/Evaluation Specialist. Each role has a responsibility, an authority boundary, and required evidence.

It correctly prevents role descriptions from becoming permissions and states that models and agents are untrusted.

### `docs/findings-and-controls.md`

This document contains a useful control matrix, but its prior-manifest and checksum claims cannot be reconciled to the currently supplied archive. Its current control statuses are mostly conservative: identity, tenant, role, audit, immutable audit, Windows filesystem, prompt-injection resistance, and external integrations are marked blocked; cryptography is marked not implemented; and synthetic interlocks are marked tested.

### `docs/adversarial-test-matrix.md`

This lists 36 expected negative cases, including missing or forged identity, tenant and role mismatch, grant and approval failures, unauthorized tools and models, generated shell/network/database commands, budget limits, safety interlocks, audit failure, unsafe filesystem namespaces, prompt injection, tool poisoning, context loss, and workflow/provider attempts. It is a test plan, not evidence that all cases have been executed.

### `docs/release-gates.md`

This defines 12 gates: source/provenance, governance authority, cryptographic authorization, approval/PEP, tool/model permission, safety interlocks, filesystem, audit, adversarial tests, synthetic E2E, independent audit, and production authorization. The document explicitly leaves the project at `DENY / NOT READY / BLOCKED`.

### `diagrams/*.mmd` and `diagrams/*.png`

The five Mermaid sources and five PNG renders represent the same generic design in visual form. They show: request intake to governance and PEP; identity-to-grant authority flow; untrusted orchestrator and specialist agents; audit admission before the gateway; and explicit denial of network, database, shell, workflow, webhook, provider, and cloud capabilities.

The PNGs are valid readable PNG files. They are documentation artifacts, not executable controls.

## 5. Relationship to Manus, Q*, Perplexity Computer, and similar agents

No named product implementation is present in the supplied material.

| Named system or category | Evidence found in this folder | Correct conclusion |
|---|---|---|
| Manus | No product-specific source, API, connector, browser session, or implementation | Not present as an implementation; only generic governed-agent concepts are present |
| Q* | No reference found | Not present |
| Perplexity Computer | No reference, browser automation, or provider integration found | Not present |
| OpenAI Operator or similar computer-use agent | No reference or computer-use implementation found | Not present |
| Generic research/analysis/engineering/QA agents | Present in the logical role and Mermaid diagrams | Design labels only; no autonomous runtime is implemented |

The correct architectural comparison is therefore at the **pattern level**, not at the product-implementation level. The pack contains governance, PEP, trust-boundary, tool-gateway, audit, and multi-agent delegation patterns that could be used to constrain an agent system. It does not establish how any named product actually implements its internal architecture.

## 6. Validation performed

The supplied ZIP passed `unzip -t` with no archive errors. The extracted pack passed the supplied test command:

```text
Ran 13 tests in 0.001s
OK
```

A conservative static scan found no executable imports or calls for network, subprocess, database, provider, workflow, or filesystem mutation capabilities. Textual mentions of those capabilities occur in safety documentation and denial tests, which is expected.

The archive members were hashed with SHA-256 during inspection. Those hashes identify the inspected local bytes only; they do not establish provenance or authenticity.

## 7. Evidence classification

| Claim | Classification | Basis |
|---|---|---|
| The ZIP is present in the shared project folder | Local fact | Directory listing |
| The ZIP is structurally readable | Tested local fact | `unzip -t` |
| The pack has a synthetic governed gateway | Implemented local scaffold | `src/governed.py` |
| The included 13 tests pass | Tested local fact | `unittest` output |
| The code uses production cryptography | False / not supported | Synthetic fixed verifier is used |
| The code validates real identity | Not implemented | No identity authority or verifier exists |
| The code protects a real Windows filesystem | Not implemented | No filesystem access exists |
| Named Manus/Q*/Perplexity Computer architecture is present | Not established | No product-specific source or integration found |
| The full original project is complete | Not established | Current archive and stale matrix claims conflict |
| Production readiness | Denied | Required evidence and gates are missing |

## 8. Required next evidence before any readiness claim

The next safe work should remain local and synthetic. It should add authoritative provenance for every declared file, reconcile or remove the stale 156-path claims, and expand tests to the untested adversarial matrix rows. It should also model approval replay, classification enforcement, future grants, explicit audit-admission failure, context-envelope verification, and capability allow-lists without enabling live side effects.

Real cryptography, real identity, production filesystem controls, external providers, browser automation, network access, workflow execution, and deployment authorization must remain blocked until separately designed, independently reviewed, explicitly authorized, and supported by admissible evidence. A product name or role label must never be treated as proof of any of those controls.

## References

[1]: file:///home/ubuntu/projects/gnw-3daeef70/wnoa-agent-architecture-complete-pack.zip "Inspected local architecture archive"

[2]: file:///tmp/gnw-architecture-pack/src/governed.py "Inspected synthetic governed gateway source"

[3]: file:///tmp/gnw-architecture-pack/tests/test_governed.py "Inspected local unit tests"

[4]: file:///tmp/gnw-architecture-pack/docs/adversarial-test-matrix.md "Inspected adversarial test matrix"

[5]: file:///tmp/gnw-architecture-pack/docs/release-gates.md "Inspected release gates"

[6]: file:///tmp/gnw-architecture-pack/diagrams/03-multi-agent-trust.mmd "Inspected multi-agent trust diagram source"

[7]: file:///tmp/gnw-architecture-pack/docs/findings-and-controls.md "Inspected findings and controls matrix"


## 9. Shortcut audit

The approved archive was checked for common shortcut and link formats, including `.lnk`, `.url`, `.desktop`, `.webloc`, `.shortcut`, `.pif`, `.scf`, `.library-ms`, `.website`, and `.appref-ms`. No matching shortcut file was present.

The text contents were also checked for shortcut indicators such as `.lnk`, `.url`, `.desktop`, `shell:`, Start Menu, taskbar, target path, and working-directory references. No shortcut reference was found.

Therefore, for the approved archive only:

| Check | Result | Evidence status |
|---|---|---|
| Shortcut file members | None found | Verified local archive fact |
| Shortcut-like text references | None found | Verified local content scan |
| Hidden Computer Point shortcuts | Not audited | Blocked because the original Windows filesystem was not accessed |

This result must not be generalized to the original Computer Point folder. It applies only to the approved archive inspected in this project.
