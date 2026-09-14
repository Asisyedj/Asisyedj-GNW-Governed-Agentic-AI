"""Standalone fail-closed governed-agent reference implementation.

DRAFT / TEST ONLY. No network, subprocess, database, provider, model, workflow,
or real filesystem access is performed. The signature verifier is injected;
the included verifier in tests is synthetic and not production cryptography.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol


class Denied(Exception):
    """A governance failure that must not reach an execution gateway."""


class Stopped(Exception):
    """A safety interlock requiring immediate stop."""


class SignatureVerifier(Protocol):
    def verify(self, grant: "AuthorizationGrant") -> bool: ...


@dataclass(frozen=True)
class Request:
    request_id: str
    subject: str
    tenant: str
    role: str
    purpose: str
    classification: str
    operation: str
    resource: str
    tool: str
    scope: str
    budget_bytes: int = 4096


@dataclass(frozen=True)
class AuthorizationGrant:
    authorization_id: str
    request_id: str
    subject: str
    tenant: str
    role: str
    purpose: str
    operation: str
    resource: str
    scope: str
    issuer: str
    issued_at: datetime
    expires_at: datetime
    nonce: str
    signature: bytes


@dataclass(frozen=True)
class Approval:
    request_id: str
    authorization_id: str
    action_digest: str
    tenant: str
    expires_at: datetime
    nonce: str


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    decision: str
    reason: str
    operation: str


class SyntheticSignatureVerifier:
    """Test-only deterministic verifier; not a production signature system."""

    def verify(self, grant: AuthorizationGrant) -> bool:
        return grant.issuer == "synthetic-test-issuer" and grant.signature == b"TEST-SIGNATURE"


class Governance:
    def __init__(self, verifier: SignatureVerifier, now: datetime | None = None) -> None:
        self.verifier = verifier
        self.now = now or datetime.now(timezone.utc)
        self.used_grants: set[str] = set()
        self.audit: list[AuditEvent] = []
        self.kill_switch = False
        self.circuit_open = False

    @staticmethod
    def digest(request: Request) -> str:
        fields = "|".join((request.request_id, request.tenant, request.operation, request.resource, request.scope))
        return sha256(fields.encode()).hexdigest()

    def _deny(self, request: Request, reason: str) -> None:
        self.audit.append(AuditEvent(request.request_id, "DENY", reason, request.operation))
        raise Denied(reason)

    def _check_grant(self, request: Request, grant: AuthorizationGrant) -> None:
        if not grant.request_id == request.request_id: self._deny(request, "request_binding")
        if not grant.subject == request.subject: self._deny(request, "subject_binding")
        if not grant.tenant == request.tenant: self._deny(request, "tenant_binding")
        if not grant.role == request.role: self._deny(request, "role_binding")
        if not grant.purpose == request.purpose: self._deny(request, "purpose_binding")
        if not grant.operation == request.operation: self._deny(request, "operation_binding")
        if not grant.resource == request.resource: self._deny(request, "resource_binding")
        if not grant.scope == request.scope: self._deny(request, "scope_binding")
        if self.now < grant.issued_at or self.now >= grant.expires_at: self._deny(request, "grant_expired")
        if grant.nonce in self.used_grants: self._deny(request, "grant_replay")
        if not self.verifier.verify(grant): self._deny(request, "invalid_signature")
        self.used_grants.add(grant.nonce)

    def _check_approval(self, request: Request, grant: AuthorizationGrant, approval: Approval | None) -> None:
        if approval is None: self._deny(request, "approval_missing")
        assert approval is not None
        if approval.request_id != request.request_id: self._deny(request, "approval_request_binding")
        if approval.authorization_id != grant.authorization_id: self._deny(request, "approval_grant_binding")
        if approval.tenant != request.tenant: self._deny(request, "approval_tenant_binding")
        if approval.action_digest != self.digest(request): self._deny(request, "approval_action_binding")
        if self.now >= approval.expires_at: self._deny(request, "approval_expired")

    def read_synthetic(self, request: Request, grant: AuthorizationGrant, approval: Approval | None) -> str:
        if self.kill_switch or self.circuit_open:
            self.audit.append(AuditEvent(request.request_id, "STOP", "safety_interlock", request.operation))
            raise Stopped("safety_interlock")
        if request.tool != "synthetic_read": self._deny(request, "unknown_tool")
        if request.operation != "read": self._deny(request, "operation_not_read")
        if request.budget_bytes <= 0: self._deny(request, "budget_invalid")
        self._check_grant(request, grant)
        self._check_approval(request, grant, approval)
        self.audit.append(AuditEvent(request.request_id, "ALLOW_LOCAL", "synthetic_read_only", request.operation))
        return "SYNTHETIC_READ_RESULT"
