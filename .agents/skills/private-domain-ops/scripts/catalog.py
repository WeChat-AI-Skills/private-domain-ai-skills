#!/usr/bin/env python3
"""Read the installed capability catalog and check file contracts. No network or dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent


def load(base: Path = BASE) -> dict:
    return {key: json.loads((base / "references/catalog" / filename).read_text()) for key, filename in {
        "tree": "skill-tree.json", "agents": "agent-registry.json", "workflows": "workflow-registry.json"
    }.items()}


def lookup(data: dict, kind: str, value: str | None = None) -> dict:
    if kind == "overview":
        return {"package_version": data["tree"]["package_version"], "domains": data["tree"]["domains"],
                "skill_count": len(data["tree"]["skills"]), "runtime_status": data["agents"]["runtime_status"]}
    source, rows = {"domain": ("tree", "domains"), "node": ("tree", "nodes"),
                    "role": ("agents", "agents"), "workflow": ("workflows", "workflows")}[kind]
    entry = next((row for row in data[source][rows] if row["id"] == value), None)
    if entry is None:
        raise ValueError(f"Unknown {kind}: {value}")
    result = dict(entry)
    if kind == "domain":
        result["nodes"] = [n for n in data["tree"]["nodes"] if n["domain_id"] == value]
        result["primary_skills"] = [s for s in data["tree"]["skills"] if s["primary_domain"] == value]
    elif kind == "role":
        result["profile_base"] = str(BASE / "references/catalog")
        result["profile_path"] = str((BASE / "references/catalog" / entry["profile"]).resolve())
    return result


def strings(value, field: str, nonempty: bool = False) -> None:
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"Invalid string list: {field}")
    if len(set(value)) != len(value):
        raise ValueError(f"Duplicate entries: {field}")


def required_text(obj, fields):
    if not isinstance(obj, dict):
        raise ValueError("Expected an object")
    for field in fields:
        if not isinstance(obj.get(field), str) or not obj[field].strip():
            raise ValueError(f"Missing text: {field}")


def check_task(task: dict, data: dict) -> None:
    required_text(task, ["contract_version", "request_id", "task_id", "assigned_by", "assigned_to", "goal"])
    if task["contract_version"] != "task-card/1.0" or task["assigned_by"] != "super-agent":
        raise ValueError("Unsupported task contract or assigner")
    if task["assigned_to"] not in {a["id"] for a in data["agents"]["agents"]}:
        raise ValueError("Unknown assigned role")
    if task.get("execution_mode") not in {"draft", "readonly", "execute"}:
        raise ValueError("Invalid execution_mode")
    if task.get("runtime_mode") not in {"single_agent", "delegated"}:
        raise ValueError("Invalid runtime_mode")
    scope = task.get("scope")
    required_text(scope, ["tenant_id", "account_id"])
    for field in ("customer_ids", "group_ids", "product_ids"):
        strings(scope.get(field), field)
    for field in ("capability_ids", "acceptance"):
        strings(task.get(field), field, nonempty=True)
    strings(task.get("context_refs"), "context_refs")
    nodes = {n["id"]: n for n in data["tree"]["nodes"]}
    if any(n not in nodes for n in task["capability_ids"]):
        raise ValueError("Unknown capability")
    if "skill_refs" in task:
        strings(task["skill_refs"], "skill_refs")
        if not set(task["skill_refs"]) <= {s["id"] for s in data["tree"]["skills"]}:
            raise ValueError("Unknown installed skill in skill_refs")
    if "depends_on" in task:
        strings(task["depends_on"], "depends_on")
        if task["task_id"] in task["depends_on"]:
            raise ValueError("Task cannot depend on itself")
    if task["execution_mode"] == "execute":
        required_text(task, ["action", "content_version", "authorization_ref", "policy_version", "capability_check_ref"])
        if any(nodes[n]["method_coverage"] == "planned" for n in task["capability_ids"]):
            raise ValueError("Planned capability has no executable skill in this package")


def check_result(result: dict, task: dict, data: dict) -> None:
    check_task(task, data)
    required_text(result, ["contract_version", "request_id", "task_id", "agent_id", "recommended_next_step"])
    if result["contract_version"] != "agent-result/1.0":
        raise ValueError("Unsupported result contract")
    for key, expected in (("request_id", task["request_id"]), ("task_id", task["task_id"]),
                          ("agent_id", task["assigned_to"]), ("scope", task["scope"])):
        if result.get(key) != expected:
            raise ValueError(f"Result does not match original task: {key}")
    if result.get("task_state") not in {"prepared", "waiting_dependency", "waiting_authorization", "running", "completed", "blocked", "cancelled"}:
        raise ValueError("Invalid task_state")
    for field in ("artifacts", "evidence_refs", "action_refs", "missing_items", "dependency_requests"):
        strings(result.get(field), field)
    if not isinstance(result.get("requires_human"), bool):
        raise ValueError("requires_human must be a boolean")
    if task["execution_mode"] in {"draft", "readonly"} and result["action_refs"]:
        raise ValueError("Draft/readonly task cannot claim new external actions")
    if result["task_state"] == "completed" and not (result["artifacts"] or result["evidence_refs"]):
        raise ValueError("Completed task needs artifacts or evidence references")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    for kind in ("domain", "node", "role", "workflow"):
        group.add_argument("--" + kind)
    group.add_argument("--check-task", type=Path)
    parser.add_argument("--result", type=Path, help="Check this result against --check-task")
    args = parser.parse_args()
    try:
        data = load()
        if args.result and not args.check_task:
            raise ValueError("--result requires --check-task")
        if args.check_task:
            task = json.loads(args.check_task.read_text())
            check_task(task, data)
            if args.result:
                check_result(json.loads(args.result.read_text()), task, data)
            answer = {"contract_valid": True, "scope": "structure and original-task consistency only; not authorization or live execution"}
        else:
            kind = next((k for k in ("domain", "node", "role", "workflow") if getattr(args, k)), "overview")
            answer = lookup(data, kind, getattr(args, kind, None))
        print(json.dumps(answer, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Catalog check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
