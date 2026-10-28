"""Reconciliation CLI for ambiguous provider dispatches.

Usage:
    python -m personal_agent.tools.reconcile list
    python -m personal_agent.tools.reconcile mark <action_id> succeeded|failed|retry

`list`   shows dispatches that were sent to a provider but never received a
         definitive response (stuck in 'dispatched' with no provider_request_id).
`mark`   lets an operator close out one of those actions:
             succeeded - the provider actually performed the work
             failed    - the provider did not perform the work (safe to retry later)
             retry     - re-open the dispatch for another attempt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

from personal_agent.state.idempotency import (
    DEFAULT_TENANT_ID,
    IdempotencyStore,
)

# Reconciliation actions accepted by the CLI
VALID_ACTIONS = ("succeeded", "failed", "retry")


def _format_ts(value: Optional[float]) -> str:
    """Render an epoch-seconds timestamp, or '-' when unset."""
    if value is None:
        return "-"
    import datetime as _dt

    return _dt.datetime.fromtimestamp(value, tz=_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m personal_agent.tools.reconcile",
        description="List and reconcile ambiguous provider dispatch records.",
    )
    parser.add_argument(
        "--db",
        default=None,
        metavar="PATH",
        help="SQLite dispatch record database (default: personal_agent/data/idempotency.db)",
    )
    parser.add_argument(
        "--tenant",
        default=None,
        metavar="TENANT_ID",
        help=f"Tenant UUID for strict row isolation (default: {DEFAULT_TENANT_ID})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human-readable table",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Show ambiguous actions dispatched but never answered")
    p_list.add_argument(
        "--older-than",
        type=int,
        default=5,
        metavar="MINUTES",
        help="Only show actions whose last attempt is older than MINUTES (default: 5)",
    )
    p_list.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    p_mark = sub.add_parser("mark", help="Reconcile a single ambiguous action")
    p_mark.add_argument("action_id", help="The action_id of the dispatch record")
    p_mark.add_argument(
        "action",
        choices=VALID_ACTIONS,
        help="succeeded = provider did the work; failed = it did not; retry = re-send",
    )
    p_mark.add_argument(
        "--operator",
        default=None,
        metavar="OPERATOR_ID",
        help="Operator UUID recorded as reconciled_by (default: $GNW_OPERATOR_ID)",
    )
    p_mark.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    return parser


def _make_store(args: argparse.Namespace) -> IdempotencyStore:
    tenant = args.tenant or os.getenv("GNW_TENANT_ID", DEFAULT_TENANT_ID)
    # Validate format early so typos fail closed rather than silently isolating rows.
    uuid.UUID(str(tenant))
    return IdempotencyStore(db_path=args.db, tenant_id=tenant)


def _cmd_list(args: argparse.Namespace, store: IdempotencyStore) -> int:
    records: List[Dict[str, Any]] = store.get_ambiguous_actions(older_than_minutes=args.older_than)

    if args.json:
        print(json.dumps(records, indent=2, sort_keys=True))
        return 0

    if not records:
        print(f"No ambiguous actions older than {args.older_than} minute(s) for tenant {store.tenant_id}.")
        return 0

    headers = ("action_id", "component", "status", "attempts", "last_attempt", "requirement_id")
    rows = [
        (
            r["action_id"],
            r["component"],
            r["status"],
            str(r["attempts"]),
            _format_ts(r["last_attempt_at"]),
            r["requirement_id"],
        )
        for r in records
    ]

    widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
    print(f"Ambiguous actions for tenant {store.tenant_id} (older than {args.older_than}m): {len(records)}")
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))
    print()
    print("Resolve with: python -m personal_agent.tools.reconcile mark <action_id> succeeded|failed|retry")
    return 0


def _cmd_mark(args: argparse.Namespace, store: IdempotencyStore) -> int:
    operator_id = args.operator or os.getenv("GNW_OPERATOR_ID")
    if not operator_id:
        print(
            "error: no operator id supplied; pass --operator UUID or set GNW_OPERATOR_ID",
            file=sys.stderr,
        )
        return 2
    try:
        uuid.UUID(str(operator_id))
    except ValueError:
        print(f"error: invalid operator UUID: {operator_id!r}", file=sys.stderr)
        return 2

    try:
        ok = store.reconcile(
            action_id=args.action_id,
            action=args.action,
            operator_id=operator_id,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not ok:
        print(
            f"error: no dispatch record for action_id {args.action_id} "
            f"in tenant {store.tenant_id}",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps({"action_id": args.action_id, "reconciled": args.action}, indent=2))
    else:
        print(f"Reconciled {args.action_id} as {args.action} (operator {operator_id}).")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    store = _make_store(args)
    if args.command == "list":
        return _cmd_list(args, store)
    if args.command == "mark":
        return _cmd_mark(args, store)

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
