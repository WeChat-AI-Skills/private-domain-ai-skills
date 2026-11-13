"""Behavioral regression tests against synthetic, isolated receipts and SQLite state."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = Path(__file__).resolve().parents[1] / ".agents/skills/task-reconcile/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
from mock_scrm import MockSCRM, command_hash, fixture
from reconcile import reconcile


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "synthetic.sqlite"
        self.mock = MockSCRM(self.path)
        self.command, self.grant = fixture()
        self.key = tuple(self.command[k] for k in ("tenant_id", "account_id", "operation", "idempotency_key"))

    def tearDown(self):
        self.temp.cleanup()

    def terminal(self, target, status="succeeded", stage="sent"):
        return {"target_id": target, "status": status, "stage": stage,
                "evidence_ref": "synthetic-event", "verified_at": "2026-11-13T10:00:00+08:00"}

    def test_timeout_after_acceptance_survives_restart(self):
        with self.assertRaises(TimeoutError):
            self.mock.submit(self.command, self.grant, timeout_after_accept=True)
        reopened = MockSCRM(self.path)
        self.assertEqual(reopened.query(*self.key)["task_id"], self.command["task_id"])
        reopened.submit(self.command, self.grant)
        self.assertEqual(reopened.submission_count(), 1)

    def test_same_key_concurrent_requests_have_one_submission(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.mock.submit(self.command, self.grant), range(8)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(self.mock.submission_count(), 1)

    def test_same_key_changed_content_rejected_even_with_new_grant(self):
        self.mock.submit(self.command, self.grant)
        changed = copy.deepcopy(self.command)
        changed["content"]["text"] = "different synthetic content"
        self.grant["authorized_command_hash"] = command_hash(changed)
        with self.assertRaisesRegex(ValueError, "different command"):
            self.mock.submit(changed, self.grant)
        self.assertEqual(self.mock.submission_count(), 1)

    def test_grant_scope_binds_tenant_account_target_and_versions(self):
        for field, value in (("tenant_id", "other"), ("account_id", "other"),
                             ("targets", ["extra"]), ("content_version", "v2"),
                             ("policy_version", "v2"), ("idempotency_key", "other")):
            with self.subTest(field=field):
                changed = {**self.command, field: value}
                with self.assertRaisesRegex(ValueError, "scope"):
                    self.mock.submit(changed, self.grant)
        self.assertEqual(self.mock.submission_count(), 0)

    def test_missing_revoked_expired_or_unscoped_grants_rejected(self):
        for grant in (None, {}, {**self.grant, "revoked": True},
                      {**self.grant, "expires_at": "2000-01-01T00:00:00Z"},
                      {**self.grant, "expires_at": "2099-01-01T00:00:00"}):
            with self.subTest(grant=grant):
                with self.assertRaises(ValueError):
                    self.mock.submit(self.command, grant)
        self.assertEqual(self.mock.submission_count(), 0)

    def test_required_evidence_and_simulation_mode(self):
        for field, value in (("evidence_refs", []), ("mode", "connected_write"), ("content", {}),
                             ("authorization_ref", ""), ("targets", ["duplicate", "duplicate"])):
            with self.subTest(field=field):
                changed = {**self.command, field: value}
                grant = {**self.grant, "authorized_command_hash": command_hash(changed)}
                with self.assertRaises(ValueError):
                    self.mock.submit(changed, grant)
        self.assertEqual(self.mock.submission_count(), 0)

    def test_scoped_query_cannot_return_another_tenant_task(self):
        self.mock.submit(self.command, self.grant)
        self.assertIsNone(self.mock.query("other", *self.key[1:]))

    def test_partial_results_count_missing_as_unknown(self):
        receipt = self.mock.submit(self.command, self.grant)
        receipt["items"] = [self.terminal(t) if i < 7 else self.terminal(t, "failed", "failed")
                            for i, t in enumerate(self.command["targets"][:9])]
        result = reconcile(receipt)
        self.assertEqual(result["counts"], {"succeeded": 7, "failed": 2, "pending": 0,
                                           "unknown": 1, "cancelled": 0, "expired": 0})
        self.assertEqual(sum(result["counts"].values()), result["planned"])
        self.assertEqual(result["mode"], "simulation")

    def test_schedule_acceptance_is_not_publication(self):
        self.command["operation"] = "moments_schedule"
        self.grant["authorized_command_hash"] = command_hash(self.command)
        result = reconcile(self.mock.submit(self.command, self.grant))
        self.assertEqual(result["counts"]["pending"], 10)
        self.assertEqual(result["counts"]["succeeded"], 0)
        self.assertTrue(all(i["stage"] == "scheduled" for i in result["items"]))

    def test_invitation_does_not_claim_joined(self):
        self.command["operation"] = "group_invite"
        self.grant["authorized_command_hash"] = command_hash(self.command)
        receipt = self.mock.submit(self.command, self.grant)
        receipt["items"] = [self.terminal(self.command["targets"][0], stage="invitation_sent")]
        self.assertEqual(reconcile(receipt)["counts"]["succeeded"], 1)
        receipt["items"][0]["stage"] = "joined"
        with self.assertRaises(ValueError):
            reconcile(receipt)

    def test_success_without_evidence_downgraded_to_unknown(self):
        receipt = self.mock.submit(self.command, self.grant)
        for field in ("evidence_ref", "verified_at"):
            row = self.terminal(self.command["targets"][0])
            row.pop(field)
            receipt["items"] = [row]
            self.assertEqual(reconcile(receipt)["counts"]["unknown"], 10)

    def test_duplicate_unexpected_or_empty_target_list_rejected(self):
        receipt = self.mock.submit(self.command, self.grant)
        row = self.terminal(self.command["targets"][0])
        for rows in ([row, row], [self.terminal("unexpected")]):
            receipt["items"] = rows
            with self.assertRaises(ValueError):
                reconcile(receipt)
        receipt["items"] = []
        receipt["expected_targets"] = []
        with self.assertRaises(ValueError):
            reconcile(receipt)

    def test_terminal_status_stage_must_agree(self):
        receipt = self.mock.submit(self.command, self.grant)
        receipt["items"] = [self.terminal(self.command["targets"][0], stage="scheduled")]
        with self.assertRaises(ValueError):
            reconcile(receipt)

    def test_conflicting_per_object_context_rejected(self):
        receipt = self.mock.submit(self.command, self.grant)
        for field in ("tenant_id", "account_id", "task_id", "content_version", "operation", "mode", "contract_version"):
            with self.subTest(field=field):
                receipt["items"] = [{**self.terminal(self.command["targets"][0]), field: "other"}]
                with self.assertRaisesRegex(ValueError, "context mismatch"):
                    reconcile(receipt)
                receipt["items"][0][field] = receipt[field]
                self.assertEqual(reconcile(receipt)["counts"]["succeeded"], 1)

    def test_malformed_operation_returns_validation_error(self):
        receipt = self.mock.submit(self.command, self.grant)
        for value in (None, [], {}, "unrecognized"):
            receipt["operation"] = value
            with self.assertRaisesRegex(ValueError, "operation"):
                reconcile(receipt)
            changed = {**self.command, "operation": value}
            with self.assertRaisesRegex(ValueError, "operation"):
                self.mock.submit(changed, self.grant)

    def test_absent_all_results_is_unknown_not_failure(self):
        receipt = self.mock.submit(self.command, self.grant)
        receipt["items"] = []
        self.assertEqual(reconcile(receipt)["counts"]["unknown"], 10)

    def test_cancelled_and_expired_are_distinct_from_failed(self):
        receipt = self.mock.submit(self.command, self.grant)
        receipt["items"] = [self.terminal(t, status=s, stage=s) for t, s in
                            zip(self.command["targets"], ("cancelled", "expired"))]
        counts = reconcile(receipt)["counts"]
        self.assertEqual((counts["cancelled"], counts["expired"], counts["failed"]), (1, 1, 0))


if __name__ == "__main__":
    unittest.main()
