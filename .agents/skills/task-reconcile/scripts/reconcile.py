#!/usr/bin/env python3
"""Validate normalized receipts and count outcomes; never contact a business system."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys

STATUSES = ("succeeded", "failed", "pending", "unknown", "cancelled", "expired")
SUCCESS_STAGE = {"message_send": "sent", "moments_schedule": "published",
                 "group_invite": "invitation_sent"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    if not nonempty(value):
        raise ValueError("timestamp must be a nonempty string with timezone")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid timestamp") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp requires timezone")
    return result


def unique_ids(value):
    if not isinstance(value, list) or not value or not all(nonempty(v) for v in value):
        raise ValueError("targets must be a nonempty list of stable IDs")
    if len(value) != len(set(value)):
        raise ValueError("duplicate targets")
    return value


def reconcile(receipt):
    if not isinstance(receipt, dict) or receipt.get("contract_version") != "1.0":
        raise ValueError("unsupported receipt contract")
    if receipt.get("mode") not in ("offline", "simulation", "connected_readonly"):
        raise ValueError("invalid receipt mode")
    for field in ("task_id", "tenant_id", "account_id", "content_version"):
        if not nonempty(receipt.get(field)):
            raise ValueError("missing " + field)
    operation = receipt.get("operation")
    if not nonempty(operation) or operation not in SUCCESS_STAGE:
        raise ValueError("unsupported operation")
    expected = unique_ids(receipt.get("expected_targets"))
    rows = receipt.get("items")
    if not isinstance(rows, list):
        raise ValueError("items must be a list")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not nonempty(row.get("target_id")):
            raise ValueError("invalid result item")
        target = row["target_id"]
        if target not in expected or target in by_id:
            raise ValueError("unexpected or duplicate result target: " + target)
        for field in ("tenant_id", "account_id", "task_id", "content_version", "operation", "mode", "contract_version"):
            if field in row and row[field] != receipt[field]:
                raise ValueError("result context mismatch: " + field)
        status, stage = row.get("status"), row.get("stage")
        if status not in STATUSES:
            raise ValueError("invalid status")
        allowed = ({SUCCESS_STAGE[operation]} if status == "succeeded" else
                   {"accepted", "scheduled", "processing"} if status == "pending" else {status})
        if not nonempty(stage) or stage not in allowed:
            raise ValueError("status/stage mismatch")
        normalized = dict(row)
        if status not in ("pending", "unknown"):
            try:
                timestamp(row.get("verified_at"))
                if not nonempty(row.get("evidence_ref")):
                    raise ValueError("missing evidence")
            except ValueError:
                normalized.update(status="unknown", stage="unknown", reason="terminal_evidence_missing")
        by_id[target] = normalized
    items = [by_id.get(t, {"target_id": t, "status": "unknown", "stage": "unknown",
                           "reason": "result_missing"}) for t in expected]
    counted = Counter(row["status"] for row in items)
    return {**{k: receipt[k] for k in ("contract_version", "mode", "task_id", "tenant_id",
                                      "account_id", "operation", "content_version")},
            "planned": len(expected), "counts": {s: counted[s] for s in STATUSES},
            "evidence_authenticity": "not_checked_by_script", "items": items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        result = reconcile(json.loads(args.receipt.read_text()))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print("Reconciliation stopped: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
