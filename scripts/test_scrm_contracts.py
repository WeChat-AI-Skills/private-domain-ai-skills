"""Offline SCRM regressions. Synthetic records never prove live authority."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / ".agents/skills/wechat-scrm-operator"


def runtime(base=PACKAGE):
    spec = importlib.util.spec_from_file_location("scrm_records", base / "scripts/scrm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SCRMContractTests(unittest.TestCase):
    def setUp(self):
        self.m = runtime()
        self.registry = self.m.load_registry()
        examples = PACKAGE / "references/examples"
        self.binding = self.m.read_json(examples / "synthetic-binding.json")
        self.call = self.m.read_json(examples / "synthetic-call.json")
        self.result = self.m.read_json(examples / "synthetic-result.json")
        self.origin_call = None
        self.origin_result = None

    def rebind(self):
        subject = self.call["subject"]
        for key in ("binding_id", "binding_revision", "environment", "tenant_id", "account_id"):
            subject[key] = self.binding[key]
        subject.update(self.binding["adapter"])
        subject["binding_digest"] = self.m.input_digest(self.binding)
        subject["input_digest"] = self.m.input_digest(self.call["input"])
        self.call["idempotency_key"] = self.m.operation_fingerprint(subject)
        self.result["subject"] = deepcopy(subject)
        if self.origin_call is not None:
            original = self.origin_call["subject"]
            for field in ("binding_id", "binding_revision", "environment", "tenant_id", "account_id"):
                original[field] = self.binding[field]
            original.update(self.binding["adapter"])
            original["binding_digest"] = self.m.input_digest(self.binding)
            self.origin_call["idempotency_key"] = self.m.operation_fingerprint(original)
            self.origin_result["subject"] = deepcopy(original)

    def check(self):
        return self.m.check_result(self.result, self.call, self.binding, self.registry,
                                   origin_call=self.origin_call, origin_result=self.origin_result)

    def task_query(self):
        old = deepcopy(self.call["subject"])
        self.origin_call = deepcopy(self.call)
        self.origin_result = deepcopy(self.result)
        self.call["subject"].update(call_id="query-call", attempt_id="query-attempt", operation="task_query",
                                    capability_id="task.query", authorization_ref=None)
        self.call["input"] = {"origin_call_id": old["call_id"], "origin_attempt_id": old["attempt_id"],
                              "origin_operation": old["operation"], "platform_ref": "synthetic-platform-task-1"}
        self.call["created_at"] = "2026-11-13T09:02:00Z"
        self.result.update(status="succeeded", stage="queried", next_action="none",
                           observed_at="2026-11-13T09:03:00Z",
                           observation={**self.call["input"], "status": "succeeded", "stage": "published"})
        self.rebind()
        self.call["idempotency_key"] = None

    def test_template_is_valid_but_unknown_is_not_executable_support(self):
        template = self.m.read_json(PACKAGE / "references/examples/binding.example.json")
        result = self.m.check_binding(template)
        self.assertEqual(set(result["availability"].values()), {"unknown"})
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["live_status"], "not_verified")
        self.binding = template
        self.rebind()
        with self.assertRaisesRegex(ValueError, "not declared supported"):
            self.check()

    def test_scheduled_is_progress_and_published_is_distinct(self):
        report = self.check()
        self.assertEqual((report["record_status"], report["record_stage"]), ("accepted", "scheduled"))
        self.result.update(status="succeeded", stage="scheduled")
        with self.assertRaisesRegex(ValueError, "status/stage"):
            self.check()
        self.result.update(stage="published", observed_at="2026-11-13T10:01:00Z", next_action="none")
        self.assertEqual(self.check()["record_stage"], "published")

    def test_success_claim_needs_original_record_and_observation(self):
        for field, value in (("platform_ref", None), ("evidence_refs", [])):
            saved = deepcopy(self.result)
            self.result[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
            self.result = saved

    def test_strict_result_correlation_for_all_frozen_subject_fields(self):
        for field, value in self.call["subject"].items():
            self.result["subject"] = deepcopy(self.call["subject"])
            self.result["subject"][field] = (value + 1) if isinstance(value, int) else "different"
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()

    def test_changed_scope_or_frozen_adapter_rejected_even_with_matching_result(self):
        for field in ("tenant_id", "account_id", "binding_id", "provider_id", "adapter_id", "adapter_version"):
            call = deepcopy(self.call)
            call["subject"][field] = "other"
            result = deepcopy(self.result)
            result["subject"] = deepcopy(call["subject"])
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.m.check_result(result, call, self.binding)

    def test_binding_revision_and_snapshot_are_frozen(self):
        for field, value in (("entry_url", "https://other.example.invalid/"), ("binding_revision", 2)):
            binding = deepcopy(self.binding)
            binding[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "binding"):
                self.m.check_call(self.call, binding)
        binding = deepcopy(self.binding)
        binding["host"]["session_ref"] = "another-session"
        with self.assertRaisesRegex(ValueError, "snapshot"):
            self.m.check_call(self.call, binding)

    def test_input_digest_and_operation_identity_detect_final_content_change(self):
        self.call["input"]["text"] = "Changed final content"
        with self.assertRaisesRegex(ValueError, "digest"):
            self.check()
        self.call["subject"]["input_digest"] = self.m.input_digest(self.call["input"])
        self.result["subject"] = deepcopy(self.call["subject"])
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.check()

    def test_external_references_require_frozen_digest_and_version(self):
        original = deepcopy(self.call)
        for field in ("ref", "sha256", "version"):
            self.call = deepcopy(original)
            del self.call["input"]["media_refs"][0][field]
            self.rebind()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
        self.call = deepcopy(original)
        self.call["input"]["options_ref"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "input digest"):
            self.check()

    def test_retry_keeps_intent_but_new_task_has_distinct_identity(self):
        old_key = self.m.operation_fingerprint(self.call["subject"])
        self.call["subject"].update(call_id="new-attempt-call", attempt_id="attempt-2")
        self.assertEqual(self.m.operation_fingerprint(self.call["subject"]), old_key)
        self.call["subject"]["task_id"] = "separate-explicit-business-task"
        self.assertNotEqual(self.m.operation_fingerprint(self.call["subject"]), old_key)

    def test_late_result_cannot_overwrite_new_attempt(self):
        self.call["subject"]["attempt_id"] = "attempt-2"
        with self.assertRaisesRegex(ValueError, "subject mismatch"):
            self.check()

    def test_old_or_unsupported_contract_version_is_not_reinterpreted(self):
        for target in (self.call, self.result, self.binding):
            old = target["schema_version"]
            target["schema_version"] = "task-card/1.2"
            with self.subTest(target=old), self.assertRaises(ValueError):
                self.check()
            target["schema_version"] = old

    def test_no_support_or_unknown_operation_is_not_assumed(self):
        for state in ("unknown", "unsupported"):
            self.binding["operations"]["moments_schedule"]["availability"] = state
            self.rebind()
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "not declared supported"):
                self.check()
        self.binding["operations"]["invented_api"] = deepcopy(self.binding["operations"]["moments_schedule"])
        with self.assertRaisesRegex(ValueError, "unregistered"):
            self.m.check_binding(self.binding)

    def test_support_claim_needs_declared_observation_but_is_not_authority(self):
        self.binding["operations"]["task_query"]["evidence_ref"] = None
        with self.assertRaisesRegex(ValueError, "observation"):
            self.m.check_binding(self.binding)
        self.binding["operations"]["task_query"]["evidence_ref"] = "synthetic-evidence"
        report = self.m.check_binding(self.binding)
        self.assertEqual(report["authorization"], "not_verified")
        self.assertEqual(report["authenticity"], "not_verified")

    def test_external_write_requires_authorization_reference(self):
        self.call["subject"]["authorization_ref"] = None
        self.result["subject"] = deepcopy(self.call["subject"])
        with self.assertRaisesRegex(ValueError, "authorization reference"):
            self.check()

    def test_url_credentials_scripts_queries_fragments_and_ambiguity_rejected(self):
        for value in ("javascript:alert(1)", "file:///tmp/a", "https://user:password@example.invalid/",
                      "https://example.invalid/?token=secret", "https://example.invalid/#token",
                      "https://example.invalid\\evil", "https://example.invalid/\n", "https://%65xample.invalid/"):
            self.binding["entry_url"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.m.check_binding(self.binding)

    def test_local_http_needs_explicit_deployment_choice(self):
        self.binding["entry_url"] = "http://127.0.0.1:8080/scrm"
        with self.assertRaisesRegex(ValueError, "allow_http"):
            self.m.check_binding(self.binding)
        self.binding["allow_http"] = True
        self.assertEqual(self.m.check_binding(self.binding)["status"], "valid")

    def test_no_secret_or_arbitrary_command_fields_in_binding(self):
        for field in ("password", "cookie", "token", "exec_command", "credentials"):
            binding = deepcopy(self.binding)
            binding[field] = "synthetic-not-a-secret"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unrecognized"):
                self.m.check_binding(binding)

    def test_timezones_order_and_visibility_are_checked(self):
        for bad in ("2026-11-13T10:00:00", "not-time"):
            self.call["input"]["scheduled_at"] = bad
            self.rebind()
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.check()
        self.call["input"]["scheduled_at"] = "2026-11-13T08:00:00Z"
        self.rebind()
        with self.assertRaisesRegex(ValueError, "predates"):
            self.check()
        self.call["input"]["scheduled_at"] = "2026-11-13T10:00:00Z"
        self.call["input"]["visibility"]["target_ids"] = []
        self.rebind()
        with self.assertRaisesRegex(ValueError, "visibility"):
            self.check()

    def test_unknown_after_timeout_requires_query_and_never_retry(self):
        self.result = self.m.read_json(PACKAGE / "references/examples/synthetic-unknown-result.json")
        self.assertFalse(self.check()["retry_allowed"])
        self.result["next_action"] = "none"
        with self.assertRaisesRegex(ValueError, "query original"):
            self.check()
        self.result["next_action"] = "query_original"
        self.result["retry_allowed"] = True
        with self.assertRaises(ValueError):
            self.check()

    def test_failed_submission_does_not_authorize_resubmission(self):
        self.result.update(status="failed", stage="failed", error="synthetic denial", next_action="do_not_retry")
        self.check()
        self.result["next_action"] = "none"
        with self.assertRaisesRegex(ValueError, "resubmission"):
            self.check()

    def test_cancellation_needs_actual_original_record_evidence(self):
        self.result.update(status="cancelled", stage="cancelled", next_action="none")
        self.check()
        self.result["evidence_refs"] = []
        with self.assertRaisesRegex(ValueError, "evidence"):
            self.check()

    def test_query_completion_is_separate_from_business_completion(self):
        self.task_query()
        self.result["observation"].update(status="accepted", stage="scheduled")
        report = self.check()
        self.assertEqual((report["record_status"], report["record_stage"]), ("succeeded", "queried"))
        self.assertEqual(self.result["observation"]["stage"], "scheduled")

    def test_completed_query_with_unknown_business_requires_original_query(self):
        self.task_query()
        self.result["observation"].update(status="unknown", stage="unknown")
        for action in ("none", "do_not_retry"):
            self.result["next_action"] = action
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "unknown result must query original"):
                self.check()
        self.result["next_action"] = "query_original"
        self.assertFalse(self.check()["retry_allowed"])

    def test_completed_query_with_failed_business_retains_failure_actions(self):
        self.task_query()
        self.result["observation"].update(status="failed", stage="failed")
        self.result["next_action"] = "none"
        with self.assertRaisesRegex(ValueError, "failure does not authorize resubmission"):
            self.check()
        for action in ("query_original", "do_not_retry"):
            self.result["next_action"] = action
            with self.subTest(action=action):
                self.assertFalse(self.check()["retry_allowed"])

    def test_do_not_retry_is_not_generally_allowed_for_successful_queries(self):
        self.task_query()
        self.result["next_action"] = "do_not_retry"
        for status, stage in (("accepted", "scheduled"), ("running", "scheduled"),
                              ("succeeded", "published"), ("cancelled", "cancelled")):
            self.result["observation"].update(status=status, stage=stage)
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "unexpected next action"):
                self.check()

    def test_query_preserves_original_call_attempt_and_platform_reference(self):
        self.task_query()
        self.check()
        for field in ("origin_call_id", "origin_attempt_id", "origin_operation", "platform_ref"):
            original = self.result["observation"][field]
            self.result["observation"][field] = "other"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "original submission"):
                self.check()
            self.result["observation"][field] = original
        self.result["platform_ref"] = "another-task"
        with self.assertRaisesRegex(ValueError, "platform reference"):
            self.check()

    def test_query_requires_actual_original_call_and_result(self):
        self.task_query()
        for first, second in ((None, self.origin_result), (self.origin_call, None)):
            with self.subTest(missing_call=first is None), self.assertRaisesRegex(ValueError, "requires explicit origin"):
                self.m.check_result(self.result, self.call, self.binding,
                                    origin_call=first, origin_result=second)

    def test_query_cannot_relabel_another_account_or_platform_record(self):
        self.task_query()
        for field in ("tenant_id", "account_id", "binding_id", "binding_digest", "adapter_id", "object_version"):
            origin_call = deepcopy(self.origin_call)
            origin_result = deepcopy(self.origin_result)
            origin_call["subject"][field] = "another"
            origin_result["subject"] = deepcopy(origin_call["subject"])
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.m.check_result(self.result, self.call, self.binding,
                                    origin_call=origin_call, origin_result=origin_result)
        self.origin_result["platform_ref"] = "different-original-platform-task"
        with self.assertRaisesRegex(ValueError, "original platform"):
            self.check()

    def test_query_has_no_original_observation_when_unknown(self):
        self.task_query()
        self.result.update(status="unknown", stage="unknown", error="synthetic missing task", next_action="query_original")
        with self.assertRaisesRegex(ValueError, "incomplete query"):
            self.check()
        self.result["observation"] = None
        self.check()

    def test_single_friend_count_duplicates_and_delivery_stage(self):
        self.call["subject"].update(operation="message_send", capability_id="messages.send")
        self.call["input"] = {"time_zone":"Asia/Taipei", "scheduled_at":"2026-11-13T10:00:00Z",
                              "target_ids":["friend-test"], "selected_count":1,
                              "message_blocks":[{"type":"text", "content_ref":{
                                  "ref":"synthetic-final-text", "sha256":"a"*64, "version":"v1"}}],
                              "policy_ref":{"ref":"synthetic-contact-policy", "sha256":"b"*64, "version":"v1"}}
        self.rebind()
        self.result.update(status="succeeded", stage="sent", next_action="none")
        self.check()
        self.result["stage"] = "read_by_customer"
        with self.assertRaisesRegex(ValueError, "status/stage"):
            self.check()
        self.result["stage"] = "sent"
        self.call["input"]["selected_count"] = 2
        self.rebind()
        with self.assertRaisesRegex(ValueError, "count"):
            self.check()
        self.call["input"]["target_ids"] = ["friend-test", "friend-test"]
        self.rebind()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()

    def test_same_query_capability_two_synthetic_implementations(self):
        self.task_query()
        # Different raw provider formats normalize to the same operation result.
        raw_a = {"id": "synthetic-platform-task-1", "state": "DONE"}
        raw_b = {"record": {"key": "synthetic-platform-task-1", "state_code": 2}}
        normalized = []
        for adapter_id, raw in (("synthetic-query-a", raw_a), ("synthetic-query-b", raw_b)):
            self.registry["adapters"].append({"adapter_id":adapter_id,"adapter_version":"1.0",
                                               "transport":"synthetic","operation_ids":["task_query", "moments_schedule"]})
            self.binding["adapter"].update(adapter_id=adapter_id, transport="synthetic")
            self.binding["operations"] = {op:self.binding["operations"][op] for op in ("task_query", "moments_schedule")}
            self.rebind()
            self.call["idempotency_key"] = None
            platform_ref = raw["id"] if adapter_id.endswith("a") else raw["record"]["key"]
            done = raw["state"] == "DONE" if adapter_id.endswith("a") else raw["record"]["state_code"] == 2
            self.result["platform_ref"] = platform_ref
            self.result["observation"].update(platform_ref=platform_ref, status="succeeded" if done else "unknown",
                                              stage="published" if done else "unknown")
            self.check()
            normalized.append(deepcopy(self.result["observation"]))
        self.assertEqual(normalized[0], normalized[1])
        # A late result from A is not acceptable for the frozen B call.
        self.result["subject"]["adapter_id"] = "synthetic-query-a"
        with self.assertRaisesRegex(ValueError, "subject mismatch"):
            self.check()

    def test_async_media_fixture_preserves_unknown_cost_and_requires_budget(self):
        self.registry["operations"]["media_generate"] = {
            "capability_id":"media.image.generate","capability_version":"1.0","effect":"external_compute",
            "input_schema":{"type":"object","properties":{"prompt_ref":{"type":"string","minLength":1}},
                            "required":["prompt_ref"],"additionalProperties":False},
            "status_stages":{"accepted":["submitted"],"running":["processing"],"succeeded":["generated"],
                             "failed":["failed"],"unknown":["unknown"],"cancelled":["cancelled"]}}
        self.registry["adapters"].append({"adapter_id":"synthetic-media","adapter_version":"1.0",
                                           "transport":"synthetic","operation_ids":["media_generate"]})
        self.binding["adapter"].update(adapter_id="synthetic-media", transport="synthetic")
        self.binding["operations"] = {"media_generate":{"availability":"supported","checked_at":"2026-11-13T09:00:00Z",
                                                         "evidence_ref":"synthetic-media-fixture"}}
        self.call["subject"].update(operation="media_generate", capability_id="media.image.generate")
        self.call["input"] = {"prompt_ref":"synthetic-public-prompt"}
        self.rebind()
        self.result.update(status="accepted", stage="submitted", usage={"quantity":None,"unit":None,"amount":None,
                                                                          "currency":None,"basis_ref":None})
        with self.assertRaisesRegex(ValueError, "budget"):
            self.check()
        self.call["budget_ref"] = "synthetic-budget-limit"
        self.check()
        self.result.update(status="unknown",stage="unknown",error="synthetic timeout",next_action="query_original")
        self.assertFalse(self.check()["retry_allowed"])
        self.assertIsNone(self.result["usage"]["amount"])
        self.result.update(status="succeeded",stage="generated",error=None,next_action="none")
        with self.assertRaisesRegex(ValueError, "artifact"):
            self.check()
        self.result["artifact_refs"] = ["synthetic-generated-artifact"]
        self.check()

    def test_cli_and_runtime_files_work_in_installed_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            installed = Path(directory) / "wechat-scrm-operator"
            shutil.copytree(PACKAGE, installed)
            script = installed / "scripts/scrm.py"
            examples = installed / "references/examples"
            commands = [["list"], ["check-binding", str(examples / "binding.example.json")],
                        ["check-call",str(examples / "synthetic-call.json"),"--binding",str(examples / "synthetic-binding.json")],
                        ["check-result",str(examples / "synthetic-result.json"),"--call",str(examples / "synthetic-call.json"),
                         "--binding",str(examples / "synthetic-binding.json")],
                        ["check-result",str(examples / "synthetic-query-result.json"),"--call",str(examples / "synthetic-query-call.json"),
                         "--binding",str(examples / "synthetic-binding.json"),"--origin-call",str(examples / "synthetic-call.json"),
                         "--origin-result",str(examples / "synthetic-result.json")]]
            for args in commands:
                proc = subprocess.run([sys.executable, str(script), *args], cwd=directory, text=True, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                report = json.loads(proc.stdout)
                self.assertTrue(report["offline_only"])
                self.assertFalse(report["execution_performed"])

    def test_invalid_file_returns_failure_without_any_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "invalid.json"
            file.write_text('{"schema_version":"scrm-binding/1.0", "password":"synthetic-secret-value"}')
            proc = subprocess.run([sys.executable, str(PACKAGE / "scripts/scrm.py"), "check-binding", str(file)],
                                  text=True, capture_output=True)
            self.assertEqual(proc.returncode, 1)
            self.assertNotIn("synthetic-secret-value", proc.stderr)
            self.assertFalse(json.loads(proc.stderr)["execution_performed"])


if __name__ == "__main__":
    unittest.main()
