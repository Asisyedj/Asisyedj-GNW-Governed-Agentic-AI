"""GNW governed agent state package.

Exposes the idempotency / dispatch-record store used for exactly-once
provider dispatch and post-hoc reconciliation.
"""

from .idempotency import (
    CrossTenantConflictError,
    IdempotencyError,
    IdempotencyStore,
    canonical_args_hash,
    canonicalize_args,
    generate_action_id,
    generate_idempotency_key,
    get_idempotency_store,
    global_idempotency_store,
    hash_response,
)

__all__ = [
    "IdempotencyStore",
    "IdempotencyError",
    "CrossTenantConflictError",
    "canonicalize_args",
    "canonical_args_hash",
    "generate_action_id",
    "generate_idempotency_key",
    "hash_response",
    "get_idempotency_store",
    "global_idempotency_store",
]
