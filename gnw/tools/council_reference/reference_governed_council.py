"""GNW shadow council reference: schema-light, deterministic, and fail-closed.

This artifact is intentionally independent of the TypeScript runtime. It models
only the state transitions and hypothetical policy boundary; it cannot execute
commands, call providers, issue leases, or approve an action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any


class CouncilState(str, Enum):
    RECEIVED = "RECEIVED"
    STATIC_VALIDATED = "STATIC_VALIDATED"
    COUNCIL_QUEUED = "COUNCIL_QUEUED"
    PLANNING = "PLANNING"
    VERIFYING = "VERIFYING"
    CRITIQUING = "CRITIQUING"
    JUDGING = "JUDGING"
    POLICY_DECIDED = "POLICY_DECIDED"
    SHADOW_COMPLETED = "SHADOW_COMPLETED"
    FAILED_CLOSED = "FAILED_CLOSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


_ALLOWED: dict[CouncilState, set[CouncilState]] = {
    CouncilState.RECEIVED: {CouncilState.STATIC_VALIDATED, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.STATIC_VALIDATED: {CouncilState.COUNCIL_QUEUED, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.COUNCIL_QUEUED: {CouncilState.PLANNING, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.PLANNING: {CouncilState.VERIFYING, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.VERIFYING: {CouncilState.CRITIQUING, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.CRITIQUING: {CouncilState.JUDGING, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.JUDGING: {CouncilState.POLICY_DECIDED, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.POLICY_DECIDED: {CouncilState.SHADOW_COMPLETED, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED},
    CouncilState.SHADOW_COMPLETED: set(),
    CouncilState.FAILED_CLOSED: set(),
    CouncilState.CANCELLED: set(),
    CouncilState.EXPIRED: set(),
}


@dataclass(frozen=True)
class HypotheticalDecision:
    outcome: str
    rule_ids: tuple[str, ...]
    execution_authorized: bool = False


@dataclass
class ShadowCouncil:
    task_id: str
    state: CouncilState = CouncilState.RECEIVED
    history: list[tuple[CouncilState, CouncilState, str]] = field(default_factory=list)

    def transition(self, target: CouncilState, reason: str) -> None:
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"invalid_council_transition:{self.state.value}->{target.value}")
        previous = self.state
        self.state = target
        self.history.append((previous, target, reason))

    def fail_closed(self, reason: str) -> None:
        if self.state in {CouncilState.SHADOW_COMPLETED, CouncilState.FAILED_CLOSED, CouncilState.CANCELLED, CouncilState.EXPIRED}:
            return
        previous = self.state
        self.state = CouncilState.FAILED_CLOSED
        self.history.append((previous, self.state, reason))


def digest_evidence(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def evaluate_hypothetical_policy(*, environment: str, evidence_complete: bool, critical_risk: bool, high_risk: bool) -> HypotheticalDecision:
    if critical_risk:
        return HypotheticalDecision("deny", ("COUNCIL_CRITICAL_RISK_DENY",))
    if environment == "production" or high_risk:
        return HypotheticalDecision("require_human_approval", ("COUNCIL_PRODUCTION_OR_HIGH_RISK_REQUIRES_HUMAN",))
    if not evidence_complete:
        return HypotheticalDecision("request_more_evidence", ("COUNCIL_EVIDENCE_INCOMPLETE",))
    return HypotheticalDecision("allow_limited_execution", ("COUNCIL_LOW_RISK_SHADOW_ALLOW",))


def redact_for_council(value: Any) -> Any:
    sensitive = {"api_key", "authorization", "cookie", "credential", "password", "private_key", "secret", "session", "token"}
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [redact_for_council(item) for item in value]
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in sensitive or any(part in key.lower() for part in ("secret", "token", "password", "credential", "private_key")) else redact_for_council(item) for key, item in value.items()}
    return value
