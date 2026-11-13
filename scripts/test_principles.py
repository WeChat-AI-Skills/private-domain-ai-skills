"""Contract regressions, not a substitute for realistic Agent behavior or live review."""
from copy import deepcopy
import json
import unittest
import validate_architecture as architecture


class PrinciplesTests(unittest.TestCase):
    def setUp(self):
        self.m = architecture.runtime()
        self.data = self.m.load()
        folder = architecture.OPS / 'references/examples'
        self.task = json.loads((folder / 'first-task.json').read_text())
        self.result = json.loads((folder / 'first-result.json').read_text())

    def check(self):
        self.m.check_result(self.result, self.task, self.data)

    def execute(self, risk='L3'):
        self.task.update(execution_mode='execute', risk_level=risk, action='invite',
                         content_version='synthetic-v1', authorization_ref='synthetic-ongoing-grant',
                         policy_version='synthetic-policy', capability_check_ref='synthetic-capability')
        self.result['action_refs'] = ['synthetic-new-action']

    def test_new_sample_and_compact_shared_ledger(self):
        self.check()
        for field in ('fact_ledger_ref', 'constraint_ledger_ref', 'adversarial_review_ref'):
            self.task[field] = 'synthetic-one-short-record'
        self.check()

    def test_legacy_pair_still_readable_without_claiming_new_principles(self):
        self.task = {k: v for k, v in self.task.items() if k not in self.m.PRINCIPLE_FIELDS}
        self.task['contract_version'] = 'task-card/1.0'
        self.result['contract_version'] = 'agent-result/1.0'
        for k in ('principles_applied', 'unverified', 'falsifiers'):
            del self.result[k]
        self.check()
        self.task['risk_level'] = 'L3'
        with self.assertRaises(ValueError):
            self.check()  # Partial metadata cannot be silently ignored.

    def test_mismatched_versions_rejected(self):
        self.result['contract_version'] = 'agent-result/1.0'
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_or_missing_task_metadata_rejected(self):
        for key, value in [('risk_level', 'L9'), ('principles_ref', 'not-a-volume'), ('unknowns', 'none'),
                           ('requires_human', 'false'), ('review_mode', 'approved'), ('fact_ledger_ref', ''),
                           ('constraint_ledger_ref', ''), ('adversarial_review_ref', ''), ('human_approval_ref', '')]:
            task = deepcopy(self.task);task[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.m.check_task(task, self.data)

    def test_l0_can_use_only_facts(self):
        self.task.update(risk_level='L0', execution_mode='readonly', review_mode='not_required')
        del self.task['constraint_ledger_ref'];del self.task['adversarial_review_ref']
        self.result.update(principles_applied=['facts'], falsifiers=[])
        self.check()

    def test_sensitive_readonly_may_be_l3_and_blocked(self):
        self.task.update(risk_level='L3', execution_mode='readonly', review_mode='pending', requires_human=True)
        self.result.update(task_state='waiting_authorization', requires_human=True, principles_applied=['facts'])
        self.check()  # Risk is not mechanically derived from readonly.

    def test_cannot_label_execute_as_low_risk(self):
        for risk in ('L0', 'L1'):
            self.execute(risk)
            with self.subTest(risk=risk), self.assertRaises(ValueError):
                self.check()

    def test_l3_self_review_cannot_claim_new_action(self):
        self.execute()
        self.task['human_approval_ref'] = 'synthetic-approved-batch'
        with self.assertRaisesRegex(ValueError, 'independent'):
            self.check()

    def test_l3_independent_review_without_signoff_cannot_claim_action(self):
        self.execute();self.task['review_mode'] = 'independent'
        with self.assertRaisesRegex(ValueError, 'human_approval_ref'):
            self.check()

    def test_l3_existing_signoff_can_be_reused(self):
        self.execute();self.task.update(review_mode='independent', human_approval_ref='synthetic-valid-ongoing-signoff')
        self.check()  # Presence/consistency only, not authentication of the record.

    def test_pending_review_or_human_cannot_claim_action(self):
        self.execute('L2')
        for which, field, value in [('task', 'review_mode', 'pending'), ('task', 'requires_human', True),
                                    ('result', 'requires_human', True)]:
            task, result = deepcopy(self.task), deepcopy(self.result)
            (task if which == 'task' else result)[field] = value
            with self.subTest(which=which, field=field), self.assertRaises(ValueError):
                self.m.check_result(result, task, self.data)

    def test_result_claims_and_unknowns_are_typed(self):
        for key, value in [('principles_applied', ['all']), ('unverified', False), ('falsifiers', 'none'),
                           ('principles_applied', ['facts', 'facts']), ('principles_applied', ['facts'])]:
            result = {**self.result, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.m.check_result(result, self.task, self.data)


if __name__ == '__main__':
    unittest.main()
