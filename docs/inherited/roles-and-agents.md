# Agent Roles and Trust Boundaries

All roles below are logical design roles. They are not autonomous permissions, connectors, schedules, or production agents.

| Role | Responsibility | Authority boundary | Required evidence |
|---|---|---|---|
| Governance Orchestrator | Evidence tiers, policy gates, approval packets, safe stop | Cannot self-authorize execution | Policy and audit tests |
| Evidence-First Research Specialist | Collects approved evidence and preserves provenance | Cannot browse blocked sources or grant authority | Source ledger and citations |
| Deep Analysis Specialist | Reconciles records and contradictions | Cannot promote proposals to facts | Reconciliation tests |
| Prompt Engineering Specialist | Creates constrained, injection-resistant prompts | Cannot authorize tools or permissions | Prompt-injection tests |
| Agent Architecture Specialist | Designs components and trust boundaries | Cannot activate components | Architecture review |
| Python/Node Engineering Specialist | Writes disabled interfaces and schemas | Cannot add live integrations without approval | Unit and contract tests |
| Workflow Design Specialist | Drafts inactive manual workflows | Cannot import, activate or execute workflows | Workflow safety scan |
| Knowledge Cataloging Specialist | Maintains metadata and provenance | Cannot expose confidential or credential-risk data | Catalog tests |
| Security Threat Modeling Specialist | Identifies abuse cases and bypasses | Cannot waive controls | Adversarial matrix |
| QA/Evaluation Specialist | Runs local tests and release evidence | Cannot declare production readiness alone | Independent audit |

## Trust rules

1. Model and agent output is untrusted data.
2. Governance is the only authority for identity, tenant, role, purpose, classification, authorization, approval, policy, tool permission, model permission, budget and execution.
3. Every side-effect-capable path must pass a mandatory PEP and governed gateway.
4. Missing, invalid, expired, mismatched or unverifiable context returns `DENY` or `STOP`.
5. A role description is not an implementation, connector, credential or permission.
