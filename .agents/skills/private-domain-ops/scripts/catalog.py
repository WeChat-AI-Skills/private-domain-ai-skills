#!/usr/bin/env python3
"""Read the installed capability catalog and check file contracts. No network or dispatch."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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


PRINCIPLE_FIELDS = {"principles_ref", "risk_level", "fact_ledger_ref", "constraint_ledger_ref",
                    "adversarial_review_ref", "unknowns", "requires_human", "review_mode", "human_approval_ref"}
PRINCIPLES = {"facts", "first_principles", "adversarial_review"}
EVIDENCE_TASK_FIELDS = {"evidence_subject", "executor", "recovery_plan_ref"}


def timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"Missing timestamp: {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid timestamp: {field}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp requires timezone: {field}")
    return parsed


def check_subject(subject, task):
    required_text(subject, ["request_id", "task_id", "execution_mode", "operation", "object_version", "policy_version"])
    for key in ("request_id", "task_id", "scope", "execution_mode"):
        if subject.get(key) != task[key]:
            raise ValueError(f"Evidence subject does not match task: {key}")
    if task["execution_mode"] == "execute":
        for key, field in (("operation", "action"), ("object_version", "content_version"), ("policy_version", "policy_version")):
            if subject[key] != task[field]:
                raise ValueError(f"Evidence subject does not match final action: {field}")


def check_evidence_fields(task):
    if task["contract_version"] != "task-card/1.2":
        if EVIDENCE_TASK_FIELDS & task.keys():
            raise ValueError("Partial evidence migration: 1.2 fields require task-card/1.2; preserve the original legacy card")
        return
    if "evidence_subject" in task:
        check_subject(task["evidence_subject"], task)
    if "executor" in task:
        required_text(task["executor"], ["actor_id", "context_id"])
    if "recovery_plan_ref" in task:
        required_text(task, ["recovery_plan_ref"])


def evidence_requirements(task, result=None, ready=False):
    completed = result is not None and result["task_state"] == "completed"
    actions = result is not None and bool(result["action_refs"])
    l3_execution = task["risk_level"] == "L3" and (ready or actions or (completed and task["execution_mode"] != "draft"))
    required = set()
    if task["review_mode"] == "independent" and (ready or completed or actions):
        required.add("review")
    if l3_execution:
        required.update({"review", "recovery", "approval"})
    return required


def check_evidence(task, bundle, required, at=None):
    """Validate explicitly supplied records only. Never resolve references or grant authority."""
    if task["contract_version"] != "task-card/1.2":
        raise ValueError("Evidence checks require a 1.2 copy; legacy structure validity is not current evidence validation")
    clock = {"clock_mode": "declared_replay" if at is not None else "structure_only",
             "current_evidence_ready": False}
    if bundle is None:
        if required:
            raise ValueError("Missing explicit evidence bundle for this claim")
        return {"status": "not_required", "required_records": [], "authenticity": "not_verified", "authorization": "not_verified", **clock}
    if not isinstance(bundle, dict) or bundle.get("schema_version") != "evidence-bundle/1.0" or not isinstance(bundle.get("records"), list):
        raise ValueError("Invalid evidence-bundle/1.0")
    if at is not None and (at.tzinfo is None or at.utcoffset() is None):
        raise ValueError("Evidence check time requires timezone")
    records = {}
    for record in bundle["records"]:
        required_text(record, ["id", "kind"])
        if record["id"] in records:
            raise ValueError("Duplicate evidence record id")
        if record["kind"] not in {"review", "recovery", "approval"}:
            raise ValueError("Unsupported evidence record kind")
        records[record["id"]] = record
    fields = {"review": "adversarial_review_ref", "recovery": "recovery_plan_ref", "approval": "human_approval_ref"}
    # Validate every supplied, referenced record; unrelated records do not satisfy requirements.
    selected = required | {kind for kind, field in fields.items() if task.get(field) in records}
    if selected:
        check_subject(task.get("evidence_subject"), task)
    for kind in sorted(selected):
        field = fields[kind]
        required_text(task, [field])
        record = records.get(task[field])
        if record is None or record["kind"] != kind:
            raise ValueError(f"Missing or wrong evidence record: {kind}")
        if record.get("subject") != task["evidence_subject"]:
            raise ValueError(f"Evidence record subject mismatch: {kind}")
        if kind == "review":
            required_text(record, ["artifact_ref", "independence_basis", "verdict"])
            required_text(record.get("reviewer"), ["actor_id", "context_id"])
            required_text(task.get("executor"), ["actor_id", "context_id"])
            if task["review_mode"] == "independent":
                if any(record["reviewer"][key] == task["executor"][key] for key in ("actor_id", "context_id")):
                    raise ValueError("Independent review cannot use the same declared actor or context")
            if record["verdict"] not in {"approved", "rejected", "pending"}:
                raise ValueError("Invalid review verdict")
            strings(record.get("unresolved_blockers"), "unresolved_blockers")
            start = timestamp(record.get("reviewed_at"), "reviewed_at")
            end = timestamp(record.get("valid_until"), "valid_until")
            if end <= start:
                raise ValueError("Review validity interval is empty")
            if kind in required and (record["verdict"] != "approved" or record["unresolved_blockers"] or (at is not None and not start <= at < end)):
                raise ValueError("Review is pending, rejected, blocked, future or expired")
        elif kind == "recovery":
            required_text(record, ["reversibility", "rationale", "owner", "authority_boundary", "verification"])
            if record["reversibility"] not in {"reversible", "irreversible", "not_applicable"}:
                raise ValueError("Invalid recovery reversibility")
            strings(record.get("stop_steps"), "stop_steps", nonempty=True)
            strings(record.get("remediation_steps"), "remediation_steps", nonempty=True)
        else:
            required_text(record, ["approved_by", "status", "grant_type", "artifact_ref"])
            if record["status"] not in {"approved", "revoked", "pending"} or record["grant_type"] not in {"single", "batch", "ongoing"}:
                raise ValueError("Invalid approval status or grant_type")
            start = timestamp(record.get("approved_at"), "approved_at")
            end = timestamp(record.get("valid_until"), "valid_until")
            if end <= start:
                raise ValueError("Approval validity interval is empty")
            if kind in required and (record["status"] != "approved" or (at is not None and not start <= at < end)):
                raise ValueError("Approval is pending, revoked, future or expired")
    return {"status": "records_consistent", "required_records": sorted(required), "checked_records": sorted(selected),
            "checked_at": at.isoformat() if at is not None else None, "authenticity": "not_verified", "authorization": "not_verified", **clock}


def check_ready(task, data, evidence_bundle=None):
    """An evidence-profile check, never a dispatch or a real authorization decision."""
    check_task(task, data)
    if task["contract_version"] != "task-card/1.2":
        raise ValueError("Readiness evidence profile requires task-card/1.2")
    if task["execution_mode"] == "draft":
        raise ValueError("Draft completion is preparation, not execution readiness")
    if task["requires_human"] or task["review_mode"] == "pending":
        raise ValueError("Human decision or review is pending")
    if task["risk_level"] == "L3":
        if task["review_mode"] != "independent":
            raise ValueError("L3 evidence readiness requires independent review")
        required_text(task, ["human_approval_ref"])
    profile = check_evidence(task, evidence_bundle, evidence_requirements(task, ready=True), datetime.now(timezone.utc))
    profile.update(clock_mode="current", current_evidence_ready=True)
    return profile


def check_principles(task: dict) -> None:
    # Legacy cards may omit these fields. Partial adoption is not silently ignored.
    if task["contract_version"] == "task-card/1.0" and not (PRINCIPLE_FIELDS & task.keys()):
        return
    required_text(task, ["principles_ref", "risk_level", "fact_ledger_ref", "review_mode"])
    if task["principles_ref"] != "a-volume/1.0" or task["risk_level"] not in {"L0", "L1", "L2", "L3"}:
        raise ValueError("Unsupported principles or risk_level")
    strings(task.get("unknowns"), "unknowns")
    if not isinstance(task.get("requires_human"), bool):
        raise ValueError("Task requires_human must be a boolean")
    if task["review_mode"] not in {"not_required", "self_review", "independent", "pending"}:
        raise ValueError("Invalid review_mode")
    for field in ("constraint_ledger_ref", "adversarial_review_ref", "human_approval_ref"):
        if field in task:
            required_text(task, [field])
    if task["risk_level"] != "L0":
        required_text(task, ["constraint_ledger_ref", "adversarial_review_ref"])
        if task["review_mode"] == "not_required":
            raise ValueError("L1+ requires a review record or pending review")
    if task["execution_mode"] == "execute" and task["risk_level"] in {"L0", "L1"}:
        raise ValueError("External execution requires at least L2 risk assessment")


def check_task(task: dict, data: dict) -> None:
    required_text(task, ["contract_version", "request_id", "task_id", "assigned_by", "assigned_to", "goal"])
    if task["contract_version"] not in {"task-card/1.0", "task-card/1.1", "task-card/1.2"} or task["assigned_by"] != "super-agent":
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
    check_principles(task)
    check_evidence_fields(task)


def check_result(result: dict, task: dict, data: dict, evidence_bundle=None, at=None) -> None:
    check_task(task, data)
    required_text(result, ["contract_version", "request_id", "task_id", "agent_id", "recommended_next_step"])
    expected_version = "agent-result/" + task["contract_version"].split("/")[1]
    if result["contract_version"] != expected_version:
        raise ValueError("Unsupported result contract")
    if task["contract_version"] != "task-card/1.2" and EVIDENCE_TASK_FIELDS & result.keys():
        raise ValueError("Partial evidence migration in legacy result; evidence fields belong on a 1.2 task copy")
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
    extra = {"principles_applied", "unverified", "falsifiers"}
    if task["contract_version"] in {"task-card/1.1", "task-card/1.2"} or extra & result.keys() or "principles_ref" in task:
        for field in extra:
            strings(result.get(field), field)
        if not set(result["principles_applied"]) <= PRINCIPLES:
            raise ValueError("Unknown principles_applied")
        if "principles_ref" not in task:
            raise ValueError("Principles result requires task assessment")
        # Unknown items may be resolved or rephrased; do not infer that an empty list proves resolution.
        if result["task_state"] == "completed" or result["action_refs"]:
            required = {"facts"} if task["risk_level"] == "L0" else PRINCIPLES
            if not required <= set(result["principles_applied"]):
                raise ValueError("Completed work needs applicable principles record")
        # Sensitive reads/exports are not writes, so action_refs can legitimately be empty.
        # Only explicit draft completion remains preparation rather than L3 execution.
        l3_execution = task["risk_level"] == "L3" and (
            bool(result["action_refs"]) or
            (result["task_state"] == "completed" and task["execution_mode"] != "draft"))
        if result["action_refs"] or l3_execution:
            if task["requires_human"] or result["requires_human"] or task["review_mode"] == "pending":
                raise ValueError("Cannot claim execution while review/human decision is pending")
            if l3_execution:
                if task["review_mode"] != "independent":
                    raise ValueError("L3 execution requires independent review")
                required_text(task, ["human_approval_ref"])
    if task["contract_version"] == "task-card/1.2":
        check_evidence(task, evidence_bundle, evidence_requirements(task, result), at)
    elif evidence_bundle is not None:
        raise ValueError("Explicit evidence bundle requires a 1.2 copy of the legacy task")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    for kind in ("domain", "node", "role", "workflow"):
        group.add_argument("--" + kind)
    group.add_argument("--check-task", type=Path)
    parser.add_argument("--result", type=Path, help="Check this result against --check-task")
    parser.add_argument("--evidence-bundle", type=Path, help="Explicit local JSON records; references are never followed")
    parser.add_argument("--check-ready", action="store_true", help="Check current evidence completeness/links; not real permission")
    parser.add_argument("--replay-at", help="Timezone timestamp for historical/synthetic result replay, never current readiness")
    args = parser.parse_args()
    try:
        data = load()
        if (args.result or args.evidence_bundle or args.check_ready or args.replay_at) and not args.check_task:
            raise ValueError("Check options require --check-task")
        if args.check_ready and (args.result or args.replay_at):
            raise ValueError("--check-ready cannot be mixed with result/history replay")
        if args.check_task:
            task = json.loads(args.check_task.read_text())
            if args.evidence_bundle and task.get("contract_version") != "task-card/1.2":
                raise ValueError("Explicit evidence bundle requires a 1.2 copy of the legacy task")
            if args.replay_at and (task.get("contract_version") != "task-card/1.2" or not args.evidence_bundle):
                raise ValueError("--replay-at requires task-card/1.2 and an explicit --evidence-bundle")
            bundle = json.loads(args.evidence_bundle.read_text()) if args.evidence_bundle else None
            at = timestamp(args.replay_at, "replay_at") if args.replay_at else None
            check_task(task, data)
            required = set()
            if args.result:
                result = json.loads(args.result.read_text())
                check_result(result, task, data, bundle, at)
                if task["contract_version"] == "task-card/1.2":
                    required = evidence_requirements(task, result)
            answer = {"contract_valid": True, "scope": "structure and original-task consistency only; not authorization or live execution"}
            if args.check_ready:
                answer["evidence_profile"] = check_ready(task, data, bundle)
            elif task["contract_version"] == "task-card/1.2":
                answer["evidence_profile"] = check_evidence(task, bundle, required, at) if bundle is not None or args.result else {"status": "not_requested"}
            else:
                answer["legacy_notice"] = "Legacy card: not checked against the 1.2 evidence profile; preserve this record, use a reviewed copy for new execution"
            answer["authorization"] = "not_verified"
            if args.replay_at:
                answer["replay_at"] = args.replay_at
                answer["scope"] = "historical/synthetic replay only; not current readiness, authorization or live execution"
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
