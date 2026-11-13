#!/usr/bin/env python3
"""Validate bundled SCRM contracts and fixtures without accessing a customer system."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / ".agents/skills/wechat-scrm-operator"


def main():
    try:
        spec = importlib.util.spec_from_file_location("scrm_contracts", PACKAGE / "scripts/scrm.py")
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        registry = runtime.load_registry()
        report = runtime.list_capabilities()
        runtime.require(len(report["operations"]) == 3, "unexpected bundled operation count")
        profile = runtime.read_json(PACKAGE / "references/scrm-profile.json")
        runtime.require(profile.get("schema_version") == "scrm-profile/1.0", "unsupported profile")
        runtime.require(profile.get("profile_id") == "supplied-scrm-web", "wrong bundled profile")
        runtime.require(profile.get("supported_deployment_versions") == [], "live deployment claims need separate evidence")
        guides = [profile[key] for key in ("onboarding_guide", "recovery_guide", "record_guide")]
        guides += [operation["guide"] for operation in profile["operations"]]
        for guide in guides:
            target = (PACKAGE / "references" / guide).resolve()
            runtime.require(target.is_relative_to(PACKAGE.resolve()) and target.is_file(), "missing or escaping installed guide")
        for operation in profile["operations"]:
            runtime.require(operation.get("live_status") == "not_verified", "unverified operation claim")
            runtime.require(operation["effect"] == registry["operations"][operation["operation_id"]]["effect"],
                            "profile/contract effect mismatch")
        examples = PACKAGE / "references/examples"
        template = runtime.read_json(examples / "binding.example.json")
        runtime.check_binding(template)
        runtime.require(all(item["availability"] == "unknown" for item in template["operations"].values()),
                        "new-customer template must not claim observed support")
        binding = runtime.read_json(examples / "synthetic-binding.json")
        call = runtime.read_json(examples / "synthetic-call.json")
        runtime.require(binding["environment"] == "synthetic", "example must be synthetic")
        runtime.check_call(call, binding)
        for name in ("synthetic-result.json", "synthetic-unknown-result.json"):
            runtime.check_result(runtime.read_json(examples / name), call, binding)
        runtime.check_result(runtime.read_json(examples / "synthetic-query-result.json"),
                             runtime.read_json(examples / "synthetic-query-call.json"), binding,
                             origin_call=call, origin_result=runtime.read_json(examples / "synthetic-result.json"))
        print("SCRM: 3 bundled guided operations; schemas, installed references and synthetic records valid. Live use not verified.")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"SCRM validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
