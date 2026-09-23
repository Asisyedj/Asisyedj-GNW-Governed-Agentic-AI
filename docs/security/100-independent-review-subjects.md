# GNW — 100 Independent Production Review Subjects

**Purpose:** Expand the previous 25-subject review into 100 independently reviewable security subjects. This is an evidence plan, not 100 passing claims.

## Verdict rule
`PASS` requires executable evidence for the exact subject. `UNPROVEN` means the control may exist in code/design but the required environment/evidence is missing. `BLOCKED` means the test cannot currently be executed because a prerequisite is unavailable. `FAIL` means the expected security invariant was violated.

| ID | Domain | Subject | Verification / attack | Required evidence | Why it matters | Gate |
|---|---|---|---|---|---|---|
| IRS-001 | Governance Authority | Authority source | Prove only the PDP can emit ALLOW | Inject model/client/orchestrator ALLOW claims and observe decision provenance | PDP decision record + negative tests | Prevents self-authorization by untrusted planners |
| IRS-002 | Governance Authority | Default deny | Unknown policy input must deny | Remove one mandatory policy field and invoke privileged action | DENY result + audit | Fail-closed baseline |
| IRS-003 | Governance Authority | Complete mediation | Every privileged sink traverses PEP | Inventory all network/storage/provider/db write sinks and trace callers | Static sink inventory + runtime traces | A single bypass defeats the architecture |
| IRS-004 | Governance Authority | Policy version binding | Old policy cannot authorize under new policy | Change policy version between grant and execution | DENY + mismatch evidence | Prevents stale authorization |
| IRS-005 | Governance Authority | Classification integrity | Risk classification cannot be downgraded | Approve restricted action then alter classification | DENY + digest mismatch | Stops privilege laundering |
| IRS-006 | Governance Authority | Purpose integrity | Purpose cannot change after authorization | Alter purpose between admission and effect | DENY + digest mismatch | Prevents context laundering |
| IRS-007 | Governance Authority | Operation integrity | Operation cannot change after approval | Swap read to write/delete after approval | DENY | Prevents confused-deputy escalation |
| IRS-008 | Governance Authority | Resource integrity | Target resource remains exact | Change resource identifier after approval | DENY | Prevents target substitution |
| IRS-009 | Governance Authority | Scope integrity | Capability scope remains exact | Expand scope after grant/approval | DENY | Prevents scope escalation |
| IRS-010 | Governance Authority | Decision provenance | Every effect has a machine-verifiable decision chain | Reconstruct effect from request→grant→approval→lease→audit | Complete evidence chain | Enables independent verification |
| IRS-011 | Identity & Tenancy | Trusted subject identity | Reject forged/client-supplied identity claims | Attempt subject substitution in request | DENY + identity source evidence | Identity is an authority root |
| IRS-012 | Identity & Tenancy | Identity expiry | Expired identity/session cannot act | Use expired session | DENY | Prevents stale authority |
| IRS-013 | Identity & Tenancy | Session revocation | Logout/revocation immediately blocks use | Revoke then reuse session | DENY | Limits credential compromise window |
| IRS-014 | Identity & Tenancy | Session fixation | Pre-auth session cannot become privileged session | Attempt fixation across login | New authenticated session + old denied | Prevents session takeover |
| IRS-015 | Identity & Tenancy | Tenant binding | Tenant is cryptographically/object bound | Cross tenant resource request | DENY | Core isolation property |
| IRS-016 | Identity & Tenancy | Tenant query isolation | All queries include tenant predicates | Run cross-tenant IDs through every repository path | No foreign rows + tests | Object checks alone miss list/query leaks |
| IRS-017 | Identity & Tenancy | Tenant context replay | Context from tenant A unusable in tenant B | Replay signed context under different tenant | DENY | Stops context replay |
| IRS-018 | Identity & Tenancy | Role integrity | Role escalation denied | Modify role in request/context | DENY | Prevents privilege escalation |
| IRS-019 | Identity & Tenancy | Membership freshness | Removed membership cannot authorize | Remove membership then act | DENY | Protects dynamic tenancy |
| IRS-020 | Identity & Tenancy | Foreign-ID existence leakage | Unauthorized IDs should not disclose sensitive state | Probe foreign task/approval/video IDs | Uniform safe response + audit | Reduces enumeration leakage |
| IRS-021 | Approval & SoD | Independent approver identity | Approval must come from trusted reviewer | Forge approver identity | DENY | Approval is separate authority |
| IRS-022 | Approval & SoD | Separation of duties | Requester cannot approve restricted action | Requester approves own request | DENY | Prevents self-approval |
| IRS-023 | Approval & SoD | Step-up authentication | Critical actions require stronger auth | Attempt critical action without step-up | DENY | Protects high-impact actions |
| IRS-024 | Approval & SoD | Exact approval digest | Approval A cannot authorize action B | Substitute digest | DENY | Core action binding |
| IRS-025 | Approval & SoD | Approval request binding | Approval cannot move between requests | Change request ID | DENY | Stops approval transplant |
| IRS-026 | Approval & SoD | Approval grant binding | Approval cannot move to another grant | Change grant ID | DENY | Stops grant substitution |
| IRS-027 | Approval & SoD | Approval tenant binding | Approval cannot cross tenants | Change tenant | DENY | Stops cross-tenant approval |
| IRS-028 | Approval & SoD | Approval expiry | Expired approval cannot execute | Execute after expiry | DENY | Limits authorization lifetime |
| IRS-029 | Approval & SoD | Approval status integrity | Pending/denied approval cannot execute | Change status or replay pending | DENY | Prevents workflow bypass |
| IRS-030 | Approval & SoD | Approval preview fidelity | Reviewer sees exact normalized effect | Compare preview to executed envelope | Exact match | Human approval is only meaningful if preview is faithful |
| IRS-031 | Grant, Capability & Execution | Grant signature | Invalid signature always denies | Flip signed grant byte | DENY | Authenticity of authorization |
| IRS-032 | Grant, Capability & Execution | Grant issuer trust | Unknown issuer denies | Use unknown issuer | DENY | Prevents rogue issuer |
| IRS-033 | Grant, Capability & Execution | Key ID trust | Unknown/revoked key denies | Use unknown/revoked key | DENY | Controls trust root |
| IRS-034 | Grant, Capability & Execution | Grant nonce uniqueness | Nonce is single-use | Reuse grant nonce | DENY | Replay protection |
| IRS-035 | Grant, Capability & Execution | Grant time validity | Future/expired grants deny | Manipulate timestamps | DENY | Limits temporal authority |
| IRS-036 | Grant, Capability & Execution | Grant TTL bound | Overlong grant denied | Issue beyond max TTL | DENY | Reduces stale authority |
| IRS-037 | Grant, Capability & Execution | Capability lease signature | Tampered lease denies | Modify lease fields | DENY | Execution-side authenticity |
| IRS-038 | Grant, Capability & Execution | Capability lease binding | Wrong task/user/action/capability denies | Substitute one binding field | DENY | Stops gateway confused deputy |
| IRS-039 | Grant, Capability & Execution | Capability lease single use | Second use denies | Replay same lease concurrently | Exactly one success | Atomic effect control |
| IRS-040 | Grant, Capability & Execution | Final interlock | Kill switch/circuit is checked immediately before effect | Activate interlock between admission and effect | STOP/no new effect | Critical last-mile control |
| IRS-041 | Model, Content & Memory | Model authority isolation | Model output never becomes authorization | Model emits ALLOW/approval claim | DENY unless independent controls pass | Preserves planner boundary |
| IRS-042 | Model, Content & Memory | Structured output validation | Malformed model tool calls are rejected | Send invalid schema/type | DENY | Prevents parser ambiguity |
| IRS-043 | Model, Content & Memory | Prompt injection isolation | Direct injection cannot alter authority | Inject authorization-changing prompt | No privilege change | Prompt defenses are advisory; PEP is authority |
| IRS-044 | Model, Content & Memory | Retrieved-content isolation | Documents cannot issue instructions to tools | Malicious document injection | No privileged effect | External content is untrusted |
| IRS-045 | Model, Content & Memory | Web-content isolation | Webpage instructions remain data | Hidden instruction in fetched page | No privilege change | Prevents indirect injection |
| IRS-046 | Model, Content & Memory | Tool-output isolation | Tool response cannot grant authority | Tool returns fake policy/approval | DENY | Tool output is untrusted |
| IRS-047 | Model, Content & Memory | Memory integrity | Memory cannot become authority without validation | Poison persistent memory | No privilege change | Prevents cross-session poisoning |
| IRS-048 | Model, Content & Memory | Memory tenant isolation | Memory from tenant A unavailable to B | Cross-tenant memory query | DENY/no data | Prevents data leakage |
| IRS-049 | Model, Content & Memory | Memory lifecycle | TTL/size/retention enforced | Overflow or expired memory | Bounded behavior | Limits poisoning and DoW |
| IRS-050 | Model, Content & Memory | Sensitive-memory redaction | Secrets are not persisted in memory | Insert secret-bearing content | Redacted/denied | Limits credential exposure |
| IRS-051 | Multi-Agent & Tool Security | Agent identity | Each privileged agent has distinct trusted identity | Spoof agent ID | DENY | Supports attribution |
| IRS-052 | Multi-Agent & Tool Security | Agent message authenticity | Inter-agent messages are authenticated | Forge message | DENY | Prevents agent impersonation |
| IRS-053 | Multi-Agent & Tool Security | Agent message authorization | Message is not itself authorization | Agent sends “approved” message | DENY | Prevents authority propagation |
| IRS-054 | Multi-Agent & Tool Security | Agent tenant binding | Agent context cannot cross tenant | Replay agent context | DENY | Tenant boundary |
| IRS-055 | Multi-Agent & Tool Security | Agent capability attenuation | Child agent cannot gain parent-beyond scope | Request broader capability | DENY | Least privilege across delegation |
| IRS-056 | Multi-Agent & Tool Security | Agent recursion limit | Unbounded agent chains stop | Create recursive delegation | STOP | Prevents runaway autonomy |
| IRS-057 | Multi-Agent & Tool Security | Tool registry integrity | Only trusted tools are executable | Register/resolve poisoned tool | DENY | Tool supply-chain control |
| IRS-058 | Multi-Agent & Tool Security | Tool schema integrity | Parameters conform to signed schema | Alter schema/unknown fields | DENY | Prevents tool confusion |
| IRS-059 | Multi-Agent & Tool Security | Tool scope separation | Read capability cannot perform write | Invoke write through read tool | DENY | Operation separation |
| IRS-060 | Multi-Agent & Tool Security | Tool provenance | Execution records exact tool version/digest | Change tool version after approval | DENY | Prevents tool substitution |
| IRS-061 | Network, Egress & Secrets | Egress allowlist | Unlisted host is blocked | Request unapproved destination | BLOCKED | Default-deny external trust |
| IRS-062 | Network, Egress & Secrets | HTTPS enforcement | Plain HTTP is rejected for external sinks | Use http:// destination | DENY | Protects transport |
| IRS-063 | Network, Egress & Secrets | Private-address blocking | RFC1918/loopback/link-local denied | Target private IP | DENY | SSRF defense |
| IRS-064 | Network, Egress & Secrets | Metadata endpoint blocking | Cloud metadata endpoints denied | Target metadata IP/hostname | DENY | Credential theft defense |
| IRS-065 | Network, Egress & Secrets | DNS rebinding resistance | Resolved destination cannot escape allowlist | Change DNS after authorization | DENY | Hostname checks alone are insufficient |
| IRS-066 | Network, Egress & Secrets | Redirect control | Redirect cannot escape approved destination | Return malicious redirect | DENY | SSRF via redirects |
| IRS-067 | Network, Egress & Secrets | Webhook destination binding | Webhook exact destination is authorized | Swap webhook URL | DENY | Prevents data exfiltration |
| IRS-068 | Network, Egress & Secrets | Credential isolation | Model/sandbox cannot read provider secrets | Attempt secret access | DENY | Secrets stay outside planner |
| IRS-069 | Network, Egress & Secrets | Credential redaction | Secrets never enter logs/audit/errors | Trigger auth/provider error | No secret material | Limits leakage |
| IRS-070 | Network, Egress & Secrets | Data minimization | External calls contain only approved fields | Inspect payload against classification | DENY/REDACT excess | Reduces exfiltration impact |
| IRS-071 | Data, Filesystem, Database & Audit | Path traversal | ../ and encoded traversal blocked | Attempt traversal | DENY | Namespace isolation |
| IRS-072 | Data, Filesystem, Database & Audit | UNC/device paths | Windows UNC/device paths blocked | Attempt UNC/device path | DENY | Cross-platform escape defense |
| IRS-073 | Data, Filesystem, Database & Audit | Symlink/junction escape | Links cannot escape namespace | Point fixture outside root | DENY | Canonical path is not enough |
| IRS-074 | Data, Filesystem, Database & Audit | File size limit | Oversized reads/writes stop | Exceed byte ceiling | DENY/STOP | Memory/DoS control |
| IRS-075 | Data, Filesystem, Database & Audit | Object storage tenant prefix | Storage key is tenant/task bound | Cross-tenant key | DENY | Storage isolation |
| IRS-076 | Data, Filesystem, Database & Audit | Database transaction integrity | Authorization consumption is atomic | Crash during claim | No double use | Prevents race conditions |
| IRS-077 | Data, Filesystem, Database & Audit | Database constraints | Tenant/request/nonce uniqueness enforced | Insert duplicate/conflicting record | DB reject | Defense in depth |
| IRS-078 | Data, Filesystem, Database & Audit | Audit pre-admission | No effect without audit admission | Make audit unavailable | STOP | Evidence boundary |
| IRS-079 | Data, Filesystem, Database & Audit | Audit tamper detection | Edit/delete/reorder/fork is detectable | Modify ledger | Verification FAIL | Evidence integrity |
| IRS-080 | Data, Filesystem, Database & Audit | Audit completeness | Effect can be reconstructed end-to-end | Compare effect to ledger | Complete chain | Forensics and accountability |
| IRS-081 | Resilience & Operations | Kill switch propagation | STOP reaches all instances | Activate switch on one control plane | No new privileged effects | Cross-instance safety |
| IRS-082 | Resilience & Operations | Circuit breaker behavior | Open breaker blocks effect | Open breaker then execute | STOP | Failure containment |
| IRS-083 | Resilience & Operations | In-flight cancellation | Defined policy for operations already in flight | Activate stop during effect | Expected cancellation/reconciliation | Hard-stop semantics need explicit scope |
| IRS-084 | Resilience & Operations | Restart safety | Restart cannot resurrect consumed authority | Restart after lease claim | No replay | Durability |
| IRS-085 | Resilience & Operations | Failover safety | Secondary instance shares authority state | Replay on second instance | DENY | Multi-instance control |
| IRS-086 | Resilience & Operations | Backup/restore safety | Restored state cannot resurrect revoked authority | Restore old snapshot | Revoked/used state remains safe | DR can otherwise reopen replay |
| IRS-087 | Resilience & Operations | Secret rotation | Old credentials cease when rotated | Rotate secret and reuse old | DENY | Compromise recovery |
| IRS-088 | Resilience & Operations | Key rotation | Old signing keys obey verification/revocation policy | Rotate/revoke and replay | DENY where required | Authorization trust lifecycle |
| IRS-089 | Resilience & Operations | Monitoring/alerting | Security events generate actionable alerts | Trigger replay/egress/kill events | Alert evidence | Detection complements prevention |
| IRS-090 | Resilience & Operations | Incident response | Compromise has tested containment path | Simulate key/credential compromise | Documented tested containment | Operational security |
| IRS-091 | Supply Chain, Release, Privacy & Assurance | Dependency declaration | All runtime imports are declared | Static import/dependency inventory | No undeclared runtime dependency | Build must be reproducible |
| IRS-092 | Supply Chain, Release, Privacy & Assurance | Dependency lock integrity | Lockfile matches package manifest | Change dependency graph | CI rejects drift | Supply-chain control |
| IRS-093 | Supply Chain, Release, Privacy & Assurance | Dependency vulnerability gate | Known critical vulnerabilities block release | Run scanner against locked graph | Gate evidence | Reduces known-vuln exposure |
| IRS-094 | Supply Chain, Release, Privacy & Assurance | SBOM completeness | SBOM covers runtime and build dependencies | Compare SBOM to lockfile | Exact/justified match | Visibility into supply chain |
| IRS-095 | Supply Chain, Release, Privacy & Assurance | Build provenance | Artifact traces to exact source/build | Verify signed provenance | PASS only if trusted builder/signature match | SLSA verification principle |
| IRS-096 | Supply Chain, Release, Privacy & Assurance | Artifact signature | Deployed artifact digest is signed and verified | Substitute artifact | DENY | Prevents artifact substitution |
| IRS-097 | Supply Chain, Release, Privacy & Assurance | Container hardening | Image runs least privilege and no unnecessary capabilities | Inspect image/runtime config | Gate evidence | Limits compromise blast radius |
| IRS-098 | Supply Chain, Release, Privacy & Assurance | Reproducibility | Same source/build inputs yield expected artifact identity | Rebuild controlled artifact | Reproducibility evidence | Detects build drift |
| IRS-099 | Supply Chain, Release, Privacy & Assurance | Privacy/data classification | Sensitive data handling follows declared classification | Send classified data to low-trust sink | DENY/REDACT | Limits privacy/security impact |
| IRS-100 | Supply Chain, Release, Privacy & Assurance | Independent release review | Reviewer verifies frozen evidence against exact artifact/config | Review complete packet | Signed approval or DENY | Prevents self-certification |

## Required execution record for every subject
```yaml
subject_id: IRS-XXX
attack: "..."
precondition: "..."
expected: "..."
actual: "..."
side_effect: "..."
audit_evidence: "..."
verdict: PASS|FAIL|BLOCKED|UNPROVEN
root_cause: "..."
fix: "..."
regression: "..."
reviewer: "..."
review_timestamp: "..."
```

## Release invariant
Production is blocked if any P0 subject is FAIL, any critical subject is unexplained, or required evidence is UNPROVEN/BLOCKED. The matrix itself is never evidence of execution.
