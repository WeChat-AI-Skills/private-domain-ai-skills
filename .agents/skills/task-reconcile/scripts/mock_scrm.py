#!/usr/bin/env python3
"""Local synthetic SCRM fixture. No network, credentials, or real business writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from reconcile import SUCCESS_STAGE, nonempty, reconcile, timestamp, unique_ids


def command_hash(command):
    return hashlib.sha256(json.dumps(command, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class MockSCRM:
    def __init__(self, path):
        self.path = str(path)
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                tenant TEXT, account TEXT, operation TEXT, idem TEXT, digest TEXT,
                command TEXT, receipt TEXT,
                PRIMARY KEY (tenant, account, operation, idem),
                UNIQUE (tenant, account, operation, digest))""")

    def submit(self, command, grant, *, now=None, timeout_after_accept=False):
        if not isinstance(command, dict) or command.get("mode") != "simulation":
            raise ValueError("mock accepts simulation only")
        if command.get("contract_version") != "1.0":
            raise ValueError("unsupported command contract")
        for field in ("task_id", "tenant_id", "account_id", "idempotency_key", "content_version",
                      "policy_version", "authorization_ref"):
            if not nonempty(command.get(field)):
                raise ValueError("missing " + field)
        if not nonempty(command.get("operation")) or command["operation"] not in SUCCESS_STAGE:
            raise ValueError("unsupported operation")
        targets = unique_ids(command.get("targets"))
        unique_ids(command.get("evidence_refs"))
        if not isinstance(command.get("content"), dict) or not command["content"]:
            raise ValueError("missing content")
        digest = command_hash(command)
        if not isinstance(grant, dict) or grant.get("revoked") is not False:
            raise ValueError("missing or revoked grant")
        if (grant.get("grant_id") != command["authorization_ref"] or
                grant.get("authorized_command_hash") != digest):
            raise ValueError("grant scope does not match command")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or timestamp(grant.get("expires_at")) <= now:
            raise ValueError("grant expired or clock lacks timezone")
        key = tuple(command[k] for k in ("tenant_id", "account_id", "operation", "idempotency_key"))
        receipt = {k: command[k] for k in ("contract_version", "mode", "task_id", "tenant_id",
                                          "account_id", "operation", "content_version")}
        stage = "scheduled" if command["operation"] == "moments_schedule" else "accepted"
        receipt.update(expected_targets=targets, items=[{"target_id": t, "status": "pending", "stage": stage}
                                                        for t in targets])
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT digest, receipt FROM tasks WHERE tenant=? AND account=? AND operation=? AND idem=?", key).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError("idempotency key reused with different command")
                return json.loads(existing[1])
            db.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (*key, digest, json.dumps(command), json.dumps(receipt)))
        if timeout_after_accept:
            raise TimeoutError("synthetic timeout after durable acceptance; query original key")
        return receipt

    def query(self, tenant, account, operation, idem):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT receipt FROM tasks WHERE tenant=? AND account=? AND operation=? AND idem=?",
                             (tenant, account, operation, idem)).fetchone()
        return json.loads(row[0]) if row else None

    def set_synthetic_results(self, tenant, account, operation, idem, items):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            key = (tenant, account, operation, idem)
            row = db.execute("SELECT receipt FROM tasks WHERE tenant=? AND account=? AND operation=? AND idem=?", key).fetchone()
            if not row:
                raise ValueError("unknown synthetic task")
            receipt = json.loads(row[0])
            receipt["items"] = items
            reconcile(receipt)
            db.execute("UPDATE tasks SET receipt=? WHERE tenant=? AND account=? AND operation=? AND idem=?",
                       (json.dumps(receipt), *key))

    def submission_count(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]


def fixture():
    command = {"contract_version": "1.0", "mode": "simulation", "task_id": "synthetic-task",
               "tenant_id": "synthetic-tenant", "account_id": "synthetic-account", "operation": "message_send",
               "idempotency_key": "synthetic-key", "targets": ["synthetic-customer-" + str(i) for i in range(10)],
               "content": {"text": "Synthetic test only"}, "content_version": "v1", "policy_version": "v1",
               "authorization_ref": "synthetic-grant", "evidence_refs": ["synthetic-source"]}
    grant = {"grant_id": "synthetic-grant", "authorized_command_hash": command_hash(command),
             "expires_at": "2099-01-01T00:00:00+00:00", "revoked": False}
    return command, grant


def demo():
    with tempfile.TemporaryDirectory(prefix="wechat-skills-simulation-") as directory:
        path = Path(directory) / "synthetic.sqlite"
        command, grant = fixture()
        mock = MockSCRM(path)
        try:
            mock.submit(command, grant, timeout_after_accept=True)
        except TimeoutError:
            pass
        mock = MockSCRM(path)
        key = tuple(command[k] for k in ("tenant_id", "account_id", "operation", "idempotency_key"))
        assert mock.query(*key) is not None
        items = [{"target_id": t, "status": "succeeded" if i < 7 else "failed",
                  "stage": "sent" if i < 7 else "failed", "evidence_ref": "synthetic-event-" + str(i),
                  "verified_at": datetime.now(timezone.utc).isoformat()}
                 for i, t in enumerate(command["targets"][:9])]
        mock.set_synthetic_results(*key, items)
        return {"mode": "simulation", "durable_submissions": mock.submission_count(),
                "result": reconcile(mock.query(*key))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
