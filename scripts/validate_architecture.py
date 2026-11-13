#!/usr/bin/env python3
"""Validate product catalog, direct role reporting, workflow references and installed files."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / ".agents/skills/private-domain-ops"
DOMAIN_IDS = ["onboarding", "intent", "moments", "chat", "groups", "listing", "review"]
ROLE_IDS = {"super-agent", "operations-agent", "content-agent", "customer-agent", "product-agent", "review-agent"}


def runtime(base=OPS):
    spec = importlib.util.spec_from_file_location("skill_catalog", base / "scripts/catalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(data: dict, names: set[str], base: Path = OPS) -> list[str]:
    problems = []
    def check(condition, message):
        if not condition:
            problems.append(message)
    tree, registry, wf = data["tree"], data["agents"], data["workflows"]
    check(tree.get("schema_version") == "skill-tree/1.0", "unsupported skill-tree version")
    check(registry.get("schema_version") == "agent-registry/1.0", "unsupported agent registry")
    check(wf.get("schema_version") == "workflow-registry/1.0", "unsupported workflow registry")
    domains, nodes, roles, skills = tree["domains"], tree["nodes"], registry["agents"], tree["skills"]
    check([d["id"] for d in domains] == DOMAIN_IDS and [d["order"] for d in domains] == list(range(1, 8)), "seven domains/order differ")
    check(len(roles) == 6 and {r["id"] for r in roles} == ROLE_IDS, "roles must be one root plus five specialists")
    check(registry.get("root_agent") == "super-agent", "wrong root agent")
    check(registry.get("runtime_status") == "role_contract_only", "runtime claims require separate host evidence")
    check(len(skills) == len(names) and {s["id"] for s in skills} == names, "catalog skills differ from installation")
    check(len(nodes) == 28 and len({n["id"] for n in nodes}) == 28, "expected 28 unique capability nodes")
    node_map = {n["id"]: n for n in nodes}
    for d, prefix in zip(DOMAIN_IDS, ("ONB", "INT", "MOM", "CHAT", "GRP", "SKU", "REV")):
        check({n["id"] for n in nodes if n["domain_id"] == d} == {f"{prefix}-{i:02}" for i in range(1, 5)}, f"wrong nodes for {d}")
    for n in nodes:
        check(n["owner_agent"] in ROLE_IDS, f"unknown node owner: {n['id']}")
        check(set(n["skill_refs"]) <= names, f"unknown skill: {n['id']}")
        check(n["method_coverage"] in {"covered", "partial", "planned"}, f"invalid coverage: {n['id']}")
        check(n["live_status"] == "not_verified", f"unverified live claim: {n['id']}")
        check(bool(n["gap"]) and bool(n["acceptance"]), f"missing limits/acceptance: {n['id']}")
        check(n["method_coverage"] == "planned" or bool(n["skill_refs"]), f"method missing skills: {n['id']}")
    for s in skills:
        check(s["primary_domain"] in DOMAIN_IDS and s["owner_agent"] in ROLE_IDS, f"invalid skill mapping: {s['id']}")
        check(s["visibility"] in {"core", "extension"}, f"invalid visibility: {s['id']}")
    role_skill_map = {}
    for role in roles:
        check(role.get("reports_to") == (None if role["id"] == "super-agent" else "super-agent"), f"not a direct report: {role['id']}")
        profile = (base / "references/catalog" / role["profile"]).resolve()
        check(profile.is_relative_to(base.resolve()) and profile.is_file(), f"missing/escaping role profile: {role['id']}")
        check(set(role["skill_refs"]) <= names, f"unknown role skill: {role['id']}")
        for skill in role["skill_refs"]:
            check(skill not in role_skill_map, f"duplicate primary role for {skill}")
            role_skill_map[skill] = role["id"]
    check(role_skill_map == {s["id"]: s["owner_agent"] for s in skills}, "role/skill ownership differs")
    ids = [w["id"] for w in wf["workflows"]]
    check(len(set(ids)) == len(ids), "duplicate workflow")
    for flow in wf["workflows"]:
        steps = {s["id"]: s for s in flow["steps"]}
        check(len(steps) == len(flow["steps"]), f"duplicate step: {flow['id']}")
        check(flow["draft_stop_after"] in steps, f"missing draft stop: {flow['id']}")
        for step in steps.values():
            check(step["assigned_to"] in ROLE_IDS, f"unknown workflow role: {step['id']}")
            check(step["kind"] in {"draft", "readonly", "external"}, f"invalid step kind: {step['id']}")
            check(set(step["depends_on"]) <= set(steps), f"unknown dependency: {step['id']}")
            check(bool(step["skill_refs"]) and set(step["skill_refs"]) <= names, f"unknown workflow skill: {step['id']}")
            check(bool(step["capability_ids"]) and set(step["capability_ids"]) <= set(node_map), f"unknown workflow capability: {step['id']}")
            permitted = {s for n in step["capability_ids"] if n in node_map for s in node_map[n]["skill_refs"]}
            check(set(step["skill_refs"]) <= permitted, f"step skill not mapped to capability: {step['id']}")
        remaining = set(steps)
        resolved = set()
        while remaining:
            ready = {i for i in remaining if set(steps[i]["depends_on"]) <= resolved}
            if not ready:
                problems.append(f"workflow cycle/unresolved dependency: {flow['id']}")
                break
            resolved |= ready
            remaining -= ready
        stop = flow["draft_stop_after"]
        if stop in steps:
            pending, ancestors = [stop], set()
            while pending:
                sid = pending.pop()
                if sid in ancestors or sid not in steps:
                    continue
                ancestors.add(sid)
                pending.extend(steps[sid]["depends_on"])
            check(all(steps[s]["kind"] != "external" for s in ancestors), f"draft path contains external step: {flow['id']}")
    # Installed links may cross skill folders but never depend on repository docs or a developer path.
    skill_root = base.parent.resolve()
    for md in skill_root.rglob("*.md"):
        for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", md.read_text()):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            dest = (md.parent / target.split("#")[0]).resolve()
            check(dest.is_relative_to(skill_root) and dest.exists(), f"installed reference unavailable: {md.name} -> {target}")
    return problems


def main():
    try:
        module = runtime()
        data = module.load(OPS)
        manifest = json.loads((ROOT / "manifest.json").read_text())
        problems = validate(data, {s["name"] for s in manifest["skills"]})
        if data["tree"]["package_version"] != manifest["version"]:
            problems.append("catalog/package version mismatch")
        if manifest.get("product_catalog") != ".agents/skills/private-domain-ops/references/catalog/skill-tree.json":
            problems.append("manifest lacks product catalog discovery path")
        task = json.loads((OPS / "references/examples/first-task.json").read_text())
        result = json.loads((OPS / "references/examples/first-result.json").read_text())
        module.check_result(result, task, data)
        print(f"checked 7 domains, 28 nodes, 6 roles, 3 workflows: {len(problems)} error(s)")
        for p in problems:
            print(p)
        return bool(problems)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Architecture validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
