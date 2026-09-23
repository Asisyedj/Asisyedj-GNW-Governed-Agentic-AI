# GNW Phases 9–18 — Runtime Evidence Contract

This file lists prerequisites for converting the fail-closed UNPROVEN gates into
actual evidence. Secrets must be supplied through the deployment/secret manager,
not committed to the repository.

## Phase 9
- TLS-enabled PostgreSQL
- two independently running GNW instances
- isolated test tenants
- observable concurrent requests
- provider sandbox and sandbox-effect telemetry

## Phase 10
- PostgreSQL backup/restore capability
- object-store backup/restore if used
- secret/session/provider/executor credential rotation mechanism
- ability to prove old credentials are rejected

## Phase 11
- reproducible build environment
- lockfile
- SBOM generator
- artifact registry
- signing key held by trusted CI/KMS
- signature verification

## Phase 12
- clean review environment
- independent reviewer identity
- immutable evidence/artifact digests

## Phase 13
- approved pilot scope
- restricted tool policy
- manual external-effect approval
- rollback/on-call procedure

## Phase 14
- applicable management-system scope and certification authority/process

## Phase 15
- production metrics/logging/alerting backend
- on-call and escalation path

## Phase 16
- staging environment matching production dependencies
- deploy and rollback mechanism

## Phase 17
- integrated environment with all Phase 9–16 prerequisites

## Phase 18
- all mandatory evidence green
- final artifact digest
- signed evidence manifest
- independent approval
- immutable evidence bundle
