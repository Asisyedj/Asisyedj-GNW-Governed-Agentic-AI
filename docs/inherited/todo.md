# Project TODO

- [x] Establish production data model for tenants, memberships, tasks, messages, agent runs, approvals, audit events, video jobs, and artifact references
- [x] Preserve the supplied governed-agent architecture as the design baseline and document evidence boundaries
- [x] Implement authenticated conversational workspace with task submission and response history
- [x] Implement five constrained specialist agents: Research, Analysis, Engineering, QA, and Video Producer
- [x] Implement untrusted orchestrator boundary with governance-only action authorization
- [x] Implement fail-closed policy gateway binding identity, tenant, role, purpose, classification, operation, resource, tool scope, expiry, nonce, and budgets
- [x] Implement explicit denied-action responses and structured denial reasons
- [x] Implement human approval queue for sensitive actions
- [x] Implement kill switch and circuit-breaker controls
- [x] Implement replay protection for grants, approvals, and task actions
- [x] Implement tamper-evident timestamped audit trail for admissions, approvals, decisions, results, and safety stops
- [x] Implement task workspace with agent selection, execution status, approval queue, results, and audit history
- [x] Implement approved video workflow: brief, script, storyboard, provider-ready job, durable status, and completion handling
- [x] Store video inputs and media artifacts through controlled external storage references, never application filesystem bytes
- [x] Implement owner notifications for completed video jobs, approval requests, and safety interlocks
- [x] Build high-contrast cyberpunk UI with black background, neon pink/cyan accents, HUD lines, corner brackets, and responsive accessibility
- [x] Add server-side environment validation and safe failure behavior
- [x] Add health/readiness checks and production error handling
- [x] Add Vitest coverage for governance, approvals, replay protection, audit integrity, video workflow, and notification paths
- [x] Add deployment configuration and live acceptance-test checklist for Vercel
- [ ] Run local checks, browser verification, and production acceptance tests
- [ ] Configure required external secrets and provider integrations without committing credentials
- [ ] Deploy the release to Vercel and record the live URL and test evidence

## Production hardening follow-ups identified during review

- [ ] Document the inherited architecture baseline and evidence boundaries in a project file
- [ ] Persist kill-switch and circuit-breaker state in the database and use it in governance checks
- [ ] Persist and consume durable nonce records for grant, approval, and task-action replay protection
- [ ] Create approval records for every sensitive or restricted action and enforce approval before provider submission
- [ ] Persist and display audit history and per-agent execution status in the workspace
- [ ] Separate video brief, script, and storyboard outputs and implement provider submission/completion lifecycle states
- [ ] Register video workflow artifacts through controlled external storage references and notify on completion
- [ ] Wire production environment validation into startup and the Vercel serverless entrypoint
- [ ] Add router-level tests for approvals, video workflow, notifications, and audit persistence
- [ ] Add an explicit Vercel/live acceptance-test checklist file
