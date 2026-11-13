#!/usr/bin/env python3
"""Offline SCRM record checks. Never connects, authorizes, submits or retries."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent.parent
NOTICE = {
    "offline_only": True,
    "live_status": "not_verified",
    "authorization": "not_verified",
    "authenticity": "not_verified",
    "execution_performed": False,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    """Read only the explicitly selected local file; never resolve references."""
    def invalid(_):
        raise ValueError("non-finite JSON number")
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=invalid)


def timestamp(value):
    require(isinstance(value, str), "timestamp must be a string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    require(result.utcoffset() is not None, "timestamp requires timezone")
    return result


def matches_type(value, kind):
    return {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }.get(kind, False)


def check_shape(value, schema, location="record"):
    """Validate the documented subset used by the bundled JSON schemas.

    Domain and cross-record rules are additionally checked below. This is not
    a general JSON Schema implementation and never loads remote schemas.
    """
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        require(any(matches_type(value, k) for k in kinds), f"{location}: wrong type")
    if "const" in schema:
        require(value == schema["const"] and type(value) is type(schema["const"]), f"{location}: wrong constant")
    if "enum" in schema:
        require(any(value == v and type(value) is type(v) for v in schema["enum"]), f"{location}: unsupported value")
    if value is None:
        return
    if isinstance(value, str):
        if "minLength" in schema:
            require(len(value.strip()) >= schema["minLength"], f"{location}: empty string")
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], value) is not None, f"{location}: invalid format")
        if schema.get("format") == "date-time":
            timestamp(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        require(not isinstance(value, float) or math.isfinite(value), f"{location}: non-finite number")
        if "minimum" in schema:
            require(value >= schema["minimum"], f"{location}: below minimum")
    if isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), f"{location}: missing items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(v, sort_keys=True, ensure_ascii=False, allow_nan=False) for v in value]
            require(len(encoded) == len(set(encoded)), f"{location}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                check_shape(item, schema["items"], f"{location}[{index}]")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        require(required <= value.keys(), f"{location}: missing required fields")
        properties = schema.get("properties", {})
        extras = value.keys() - properties.keys()
        extra_rule = schema.get("additionalProperties", True)
        require(extra_rule is not False or not extras, f"{location}: unrecognized fields")
        for key, item in value.items():
            if key in properties:
                check_shape(item, properties[key], f"{location}.{key}")
            elif isinstance(extra_rule, dict):
                check_shape(item, extra_rule, f"{location}.*")


def schema(name, base=BASE):
    return read_json(base / "references/contracts" / name)


def load_registry(base=BASE):
    registry = read_json(base / "references/capabilities.json")
    require(registry.get("schema_version") == "scrm-capabilities/1.0", "unsupported capability registry")
    require(registry.get("live_status") == "not_verified", "registry may not imply live verification")
    require(isinstance(registry.get("operations"), dict) and registry["operations"], "missing operation registry")
    return registry


def input_digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def operation_fingerprint(subject):
    """Identify this business intent, not an individual UI click or attempt."""
    keys = ("request_id", "task_id", "binding_id", "tenant_id", "account_id", "operation",
            "capability_version", "object_version", "input_digest")
    return input_digest({key: subject[key] for key in keys})


def check_entry_url(value, allow_http):
    require(not any(ord(c) < 33 or c.isspace() for c in value), "entry_url has whitespace/control characters")
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise ValueError("invalid entry_url") from exc
    require(url.scheme in {"https", "http"} and bool(url.hostname), "entry_url must be an HTTP(S) origin/path")
    require(url.scheme == "https" or allow_http is True, "HTTP requires explicit allow_http for this deployment")
    require(url.username is None and url.password is None and not url.query and not url.fragment,
            "entry_url must not contain credentials, query or fragment")
    require("\\" not in value and "%" not in url.netloc, "ambiguous entry_url authority")
    require(port is None or 0 < port <= 65535, "invalid entry_url port")


def check_binding(binding, registry=None, base=BASE):
    registry = registry or load_registry(base)
    check_shape(binding, schema("customer-binding.schema.json", base), "binding")
    check_entry_url(binding["entry_url"], binding["allow_http"])
    adapter = binding["adapter"]
    compatible = [a for a in registry["adapters"] if all(
        adapter[k] == a[k] for k in ("adapter_id", "adapter_version", "transport"))]
    require(bool(compatible), "adapter/version/transport is not registered")
    allowed = set(compatible[0]["operation_ids"])
    require(set(binding["operations"]) <= allowed, "binding contains unregistered adapter operations")
    for operation, declared in binding["operations"].items():
        require(operation in registry["operations"], "binding contains unknown operation")
        if declared["availability"] == "supported":
            require(declared["checked_at"] is not None and declared["evidence_ref"] is not None,
                    "declared support requires observation time and evidence reference")
    return {**NOTICE, "check": "binding_structure", "status": "valid", "availability": {
        op: item["availability"] for op, item in binding["operations"].items()}}


def check_call(call, binding, registry=None, base=BASE, origin_call=None, origin_result=None):
    registry = registry or load_registry(base)
    check_binding(binding, registry, base)
    check_shape(call, schema("capability-call.schema.json", base), "call")
    subject = call["subject"]
    for field in ("binding_id", "binding_revision", "environment", "tenant_id", "account_id"):
        require(subject[field] == binding[field], f"call/binding mismatch: {field}")
    for field in ("provider_id", "adapter_id", "adapter_version", "transport"):
        require(subject[field] == binding["adapter"][field], f"call/binding mismatch: {field}")
    require(subject["binding_digest"] == input_digest(binding), "frozen binding snapshot mismatch")
    operation = subject["operation"]
    require(operation in registry["operations"], "unknown operation")
    spec = registry["operations"][operation]
    require(subject["capability_id"] == spec["capability_id"] and
            subject["capability_version"] == spec["capability_version"], "capability/version mismatch")
    require(binding["operations"].get(operation, {}).get("availability") == "supported",
            "operation is not declared supported in this binding")
    check_shape(call["input"], spec["input_schema"], "call.input")
    require(subject["input_digest"] == input_digest(call["input"]), "input digest mismatch")
    effect = spec["effect"]
    if effect in {"business_write", "external_compute"}:
        require(subject["authorization_ref"] is not None, "external operation needs authorization reference")
        require(call["idempotency_key"] == operation_fingerprint(subject), "operation fingerprint mismatch")
    if effect == "external_compute":
        require(call["budget_ref"] is not None, "external compute requires budget reference")
    if operation == "moments_schedule":
        require(timestamp(call["input"]["scheduled_at"]) >= timestamp(call["created_at"]),
                "scheduled time predates call creation")
        require(call["input"]["time_zone"] == binding["time_zone"], "time zone differs from binding")
        visibility = call["input"]["visibility"]
        require(bool(visibility["target_ids"]) == (visibility["mode"] in {"include", "exclude"}),
                "visibility mode and target list disagree")
    if operation == "message_send":
        require(timestamp(call["input"]["scheduled_at"]) >= timestamp(call["created_at"]),
                "scheduled time predates call creation")
        require(call["input"]["time_zone"] == binding["time_zone"], "time zone differs from binding")
        require(call["input"]["selected_count"] == len(call["input"]["target_ids"]), "target count mismatch")
    if operation == "task_query":
        original = call["input"]
        require(original["origin_operation"] in registry["operations"] and
                original["origin_operation"] != "task_query", "unsupported original operation")
        require(original["origin_call_id"] != subject["call_id"], "query must retain a separate original call id")
        require(origin_call is not None and origin_result is not None,
                "task_query requires explicit origin call and origin result records")
        check_shape(origin_call, schema("capability-call.schema.json", base), "origin_call")
        origin_subject = origin_call["subject"]
        require(origin_subject["operation"] != "task_query", "query origin must be a business submission")
        require(origin_subject["call_id"] == original["origin_call_id"] and
                origin_subject["attempt_id"] == original["origin_attempt_id"] and
                origin_subject["operation"] == original["origin_operation"], "origin call identity mismatch")
        for field in ("environment", "tenant_id", "account_id", "binding_id", "binding_revision", "binding_digest",
                      "provider_id", "adapter_id", "adapter_version", "transport", "object_version"):
            require(origin_subject[field] == subject[field], f"query/origin scope mismatch: {field}")
        # Validate the actual original result against its own original request.
        # Only explicit local records are read; no evidence references are opened.
        check_result(origin_result, origin_call, binding, registry, base)
        require(origin_result["platform_ref"] is not None and
                origin_result["platform_ref"] == original["platform_ref"], "original platform reference mismatch")
        require(timestamp(call["created_at"]) >= timestamp(origin_result["observed_at"]),
                "query predates its original platform observation")
    return {**NOTICE, "check": "call_structure_and_binding", "status": "valid", "operation": operation,
            "note": "Declared support and references are not current authority or live tool evidence."}


def check_stage(status, stage, spec):
    require(status in spec["status_stages"] and stage in spec["status_stages"][status],
            "status/stage is not valid for this operation")


def check_result(result, call, binding, registry=None, base=BASE, origin_call=None, origin_result=None):
    registry = registry or load_registry(base)
    check_call(call, binding, registry, base, origin_call, origin_result)
    check_shape(result, schema("capability-result.schema.json", base), "result")
    require(result["subject"] == call["subject"], "result subject mismatch: call/attempt/scope/frozen input or implementation")
    require(timestamp(result["observed_at"]) >= timestamp(call["created_at"]), "result predates its call")
    operation = call["subject"]["operation"]
    spec = registry["operations"][operation]
    check_stage(result["status"], result["stage"], spec)
    require(result["retry_allowed"] is False, "record checks never authorize a retry")
    if result["status"] in {"accepted", "running", "succeeded", "cancelled"}:
        require(bool(result["evidence_refs"]), "observed progress requires evidence references")
        require(result["platform_ref"] is not None, "observed progress requires original platform record reference")
    if result["status"] in {"unknown", "failed"}:
        require(result["error"] is not None, "unknown or failure requires a reason")
    else:
        require(result["error"] is None, "non-error status cannot retain an error claim")
    if result["status"] == "unknown":
        require(result["next_action"] == "query_original", "unknown result must query original before any new submission")
    elif result["status"] == "failed":
        require(result["next_action"] in {"query_original", "do_not_retry"}, "failure does not authorize resubmission")
    else:
        require(result["next_action"] in {"query_original", "none"}, "unexpected next action")
    if operation == "task_query":
        if result["status"] == "succeeded":
            observation = result["observation"]
            require(isinstance(observation, dict), "successful query needs original-operation observation")
            for field in ("origin_call_id", "origin_attempt_id", "origin_operation", "platform_ref"):
                require(observation[field] == call["input"][field], "query observation must match original submission")
            require(result["platform_ref"] == call["input"]["platform_ref"], "query platform reference mismatch")
            check_stage(observation["status"], observation["stage"], registry["operations"][observation["origin_operation"]])
        else:
            require(result["observation"] is None, "incomplete query cannot claim an original-operation observation")
    else:
        require(result["observation"] is None, "only task_query may include a query observation")
    if result["status"] == "succeeded" and spec["effect"] == "external_compute":
        require(bool(result["artifact_refs"]), "completed generation requires artifact references")
    return {**NOTICE, "check": "result_structure_and_correlation", "status": "valid", "operation": operation,
            "record_status": result["status"], "record_stage": result["stage"],
            "retry_allowed": False, "note": "Correlated records are not proof of source authenticity or customer outcomes."}


def list_capabilities(base=BASE):
    registry = load_registry(base)
    profile = read_json(base / "references/scrm-profile.json")
    require(profile.get("live_status") == "not_verified", "profile may not imply live verification")
    indexed = {item["operation_id"]: item for item in profile["operations"]}
    require(set(indexed) == set(registry["operations"]), "profile/registry operation mismatch")
    for op, spec in registry["operations"].items():
        require(all(indexed[op][key] == spec[key] for key in ("capability_id", "capability_version")),
                "profile/registry capability mismatch")
    return {**NOTICE, "check": "bundled_methods", "profile_id": profile["profile_id"],
            "operations": [{"operation": op, "capability_id": spec["capability_id"],
                            "capability_version": spec["capability_version"], "effect": spec["effect"],
                            "method_status": "guided"} for op, spec in registry["operations"].items()]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List bundled operation methods; no live probing")
    binding = sub.add_parser("check-binding", help="Check an explicit local binding file")
    binding.add_argument("binding")
    call = sub.add_parser("check-call", help="Check an explicit local call against a binding")
    call.add_argument("call")
    call.add_argument("--binding", required=True)
    call.add_argument("--origin-call", help="Required for task_query: explicit local original call")
    call.add_argument("--origin-result", help="Required for task_query: explicit local original platform result")
    result = sub.add_parser("check-result", help="Check an explicit local result against its original call and binding")
    result.add_argument("result")
    result.add_argument("--call", required=True)
    result.add_argument("--binding", required=True)
    result.add_argument("--origin-call", help="Required for task_query: explicit local original call")
    result.add_argument("--origin-result", help="Required for task_query: explicit local original platform result")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            report = list_capabilities()
        elif args.command == "check-binding":
            report = check_binding(read_json(args.binding))
        elif args.command == "check-call":
            report = check_call(read_json(args.call), read_json(args.binding),
                                origin_call=read_json(args.origin_call) if args.origin_call else None,
                                origin_result=read_json(args.origin_result) if args.origin_result else None)
        else:
            report = check_result(read_json(args.result), read_json(args.call), read_json(args.binding),
                                  origin_call=read_json(args.origin_call) if args.origin_call else None,
                                  origin_result=read_json(args.origin_result) if args.origin_result else None)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Schema errors contain field names rather than rejected field contents.
        print(json.dumps({**NOTICE, "status": "invalid", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
