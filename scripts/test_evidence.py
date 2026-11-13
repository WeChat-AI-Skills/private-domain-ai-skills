"""Synthetic contract regressions; none prove identity, authority or live operation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import validate_architecture as architecture


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.m = architecture.runtime()
        self.data = self.m.load()
        examples = self.m.BASE / 'references/examples'
        self.task = json.loads((examples / 'evidence-task.json').read_text())
        self.result = json.loads((examples / 'evidence-result.json').read_text())
        self.bundle = json.loads((examples / 'evidence-bundle.json').read_text())
        self.at = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)

    def check(self, bundle=True, at=None):
        self.m.check_result(self.result, self.task, self.data, self.bundle if bundle else None, at)

    def bind(self):
        for record in self.bundle['records']:
            record['subject'] = deepcopy(self.task['evidence_subject'])

    def execute(self):
        self.task.update(execution_mode='execute', action='synthetic-send', content_version='synthetic-final-v1',
                         policy_version='synthetic-policy-v1', authorization_ref='synthetic-authority',
                         capability_check_ref='synthetic-capability')
        self.task['evidence_subject'].update(execution_mode='execute', operation=self.task['action'],
                                             object_version=self.task['content_version'])
        self.result['action_refs'] = ['synthetic-new-action']
        self.bind()

    def current_intervals(self):
        now = datetime.now(timezone.utc)
        for record in self.bundle['records']:
            if record['kind'] in {'review', 'approval'}:
                record['reviewed_at' if record['kind'] == 'review' else 'approved_at'] = (now - timedelta(hours=1)).isoformat()
                record['valid_until'] = (now + timedelta(hours=1)).isoformat()

    def test_complete_readonly_and_execute_records(self):
        self.check(at=self.at)
        self.execute()
        self.check(at=self.at)

    def test_all_three_required_for_sensitive_read_and_empty_action_execution(self):
        for mode in ('readonly', 'execute'):
            if mode == 'execute':
                self.execute()
                self.result['action_refs'] = []
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'explicit evidence bundle'):
                self.check(bundle=False)
            for kind in ('review', 'recovery', 'approval'):
                incomplete = {'schema_version': 'evidence-bundle/1.0',
                              'records': [r for r in self.bundle['records'] if r['kind'] != kind]}
                with self.subTest(mode=mode, missing=kind), self.assertRaises(ValueError):
                    self.m.check_result(self.result, self.task, self.data, incomplete)

    def test_waiting_blocked_and_draft_can_report_missing_evidence(self):
        self.task.update(review_mode='pending', requires_human=True)
        del self.task['evidence_subject'], self.task['executor'], self.task['recovery_plan_ref'], self.task['human_approval_ref']
        self.result.update(requires_human=True, principles_applied=['facts'])
        for state in ('prepared', 'waiting_dependency', 'waiting_authorization', 'blocked', 'running', 'cancelled'):
            self.result['task_state'] = state
            with self.subTest(state=state):
                self.check(bundle=False)
        self.task['execution_mode'] = 'draft'
        self.result.update(task_state='completed', principles_applied=sorted(self.m.PRINCIPLES))
        self.check(bundle=False)

    def test_l0_stays_small(self):
        self.task.update(risk_level='L0', review_mode='not_required')
        for field in ('evidence_subject', 'executor', 'recovery_plan_ref', 'human_approval_ref',
                      'adversarial_review_ref', 'constraint_ledger_ref'):
            del self.task[field]
        self.result['principles_applied'] = ['facts']
        self.check(bundle=False)
        profile = self.m.check_ready(self.task, self.data)
        self.assertEqual(profile['status'], 'not_required')
        self.assertEqual(profile['authorization'], 'not_verified')

    def test_independent_l2_completion_requires_only_review(self):
        self.task['risk_level'] = 'L2'
        self.bundle['records'] = [self.bundle['records'][0]]
        self.check(at=self.at)
        with self.assertRaises(ValueError):
            self.check(bundle=False)

    def test_subject_cannot_cross_scope_identity_mode_or_version(self):
        for field, value in [('request_id', 'other'), ('task_id', 'other'), ('scope', {'tenant_id': 'other'}),
                             ('execution_mode', 'draft'), ('object_version', 'other'), ('policy_version', 'other'),
                             ('operation', 'other')]:
            bundle = deepcopy(self.bundle)
            bundle['records'][0]['subject'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'subject mismatch'):
                self.m.check_result(self.result, self.task, self.data, bundle)

    def test_execute_subject_binds_actual_final_fields(self):
        self.execute()
        for field in ('action', 'content_version', 'policy_version'):
            task = deepcopy(self.task)
            task[field] = 'changed-after-review'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'final action'):
                self.m.check_result(self.result, task, self.data, self.bundle)

    def test_readonly_new_source_version_requires_rebound_records(self):
        self.task['evidence_subject']['object_version'] = 'synthetic-snapshot-v2'
        with self.assertRaisesRegex(ValueError, 'subject mismatch'):
            self.check()

    def test_role_renaming_does_not_create_independence(self):
        for field in ('actor_id', 'context_id'):
            bundle = deepcopy(self.bundle)
            bundle['records'][0]['reviewer'][field] = self.task['executor'][field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'same declared actor or context'):
                self.m.check_result(self.result, self.task, self.data, bundle)

    def test_blocked_rejected_and_pending_review_cannot_complete(self):
        for field, value in [('verdict', 'pending'), ('verdict', 'rejected'), ('unresolved_blockers', ['not fixed'])]:
            bundle = deepcopy(self.bundle)
            bundle['records'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.m.check_result(self.result, self.task, self.data, bundle)

    def test_recovery_requires_concrete_shape_even_when_not_applicable(self):
        for field, value in [('rationale', ''), ('owner', ''), ('authority_boundary', ''), ('verification', ''),
                             ('stop_steps', []), ('remediation_steps', []), ('reversibility', 'none')]:
            bundle = deepcopy(self.bundle)
            bundle['records'][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.m.check_result(self.result, self.task, self.data, bundle)
        self.task['recovery_plan_ref'] = 'references/recovery-and-review.md'
        with self.assertRaisesRegex(ValueError, 'Missing or wrong evidence record'):
            self.check()  # A general instruction file is not this task's recovery record.

    def test_grants_reusable_but_pending_and_revoked_not_complete(self):
        for grant_type in ('single', 'batch', 'ongoing'):
            self.bundle['records'][2]['grant_type'] = grant_type
            self.check(at=self.at)
        for status in ('pending', 'revoked'):
            self.bundle['records'][2]['status'] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.check()

    def test_history_readable_after_expiry_but_readiness_not_current(self):
        for record in self.bundle['records']:
            if record['kind'] in {'review', 'approval'}:
                record['reviewed_at' if record['kind'] == 'review' else 'approved_at'] = '2000-01-01T00:00:00Z'
                record['valid_until'] = '2000-01-02T00:00:00Z'
        self.check()  # Reading a historical claim does not re-authorize it today.
        self.check(at=datetime(2000, 1, 1, 12, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.m.check_ready(self.task, self.data, self.bundle)

    def test_replay_future_expiry_boundary_and_timezone(self):
        for at in (datetime(2026, 11, 13, 7, tzinfo=timezone.utc),
                   datetime(2026, 11, 14, 8, tzinfo=timezone.utc)):
            with self.subTest(at=at), self.assertRaises(ValueError):
                self.check(at=at)
        self.bundle['records'][0]['reviewed_at'] = '2026-11-13T08:00:00'
        with self.assertRaisesRegex(ValueError, 'timezone'):
            self.check()

    def test_current_readiness_and_replay_have_distinct_claims(self):
        profile = self.m.check_evidence(self.task, self.bundle, {'review', 'recovery', 'approval'})
        self.assertEqual(profile['clock_mode'], 'structure_only')
        self.assertFalse(profile['current_evidence_ready'])
        profile = self.m.check_evidence(self.task, self.bundle, {'review'}, self.at)
        self.assertEqual(profile['clock_mode'], 'declared_replay')
        self.assertFalse(profile['current_evidence_ready'])
        self.current_intervals()
        profile = self.m.check_ready(self.task, self.data, self.bundle)
        self.assertEqual(profile['clock_mode'], 'current')
        self.assertTrue(profile['current_evidence_ready'])
        self.assertEqual(profile['authorization'], 'not_verified')
        self.assertEqual(profile['authenticity'], 'not_verified')

    def test_ready_rejects_preparation_and_pending(self):
        for update in ({'requires_human': True}, {'review_mode': 'pending'}, {'review_mode': 'self_review'}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.m.check_ready({**self.task, **update}, self.data, self.bundle)
        self.task['execution_mode'] = 'draft'
        self.task['evidence_subject']['execution_mode'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'Draft completion'):
            self.m.check_ready(self.task, self.data, self.bundle)

    def test_legacy_partial_migration_not_silently_accepted(self):
        fixture = Path(__file__).parent / 'fixtures/task-v1.1.json'
        legacy = json.loads(fixture.read_text())
        self.m.check_task(legacy, self.data)
        with self.assertRaisesRegex(ValueError, 'requires task-card/1.2'):
            self.m.check_ready(legacy, self.data)
        for field in self.m.EVIDENCE_TASK_FIELDS:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Partial evidence migration'):
                self.m.check_task({**legacy, field: self.task[field]}, self.data)
        result = json.loads((fixture.parent / 'result-v1.1.json').read_text())
        with self.assertRaisesRegex(ValueError, '1.2 copy'):
            self.m.check_result(result, legacy, self.data, self.bundle)
        for field in self.m.EVIDENCE_TASK_FIELDS:
            with self.subTest(result_field=field), self.assertRaisesRegex(ValueError, 'Partial evidence migration'):
                self.m.check_result({**result, field: self.task[field]}, legacy, self.data)

    def test_bundle_schema_duplicate_wrong_kind_and_unrelated_record(self):
        for bundle in ([], {}, {'schema_version': 'evidence-bundle/1.0', 'records': 'bad'},
                       {**self.bundle, 'records': self.bundle['records'] * 2}):
            with self.subTest(bundle=bundle), self.assertRaises(ValueError):
                self.m.check_result(self.result, self.task, self.data, bundle)
        bundle = deepcopy(self.bundle)
        bundle['records'][0]['kind'] = 'approval'
        with self.assertRaisesRegex(ValueError, 'wrong evidence record'):
            self.m.check_result(self.result, self.task, self.data, bundle)
        bundle = deepcopy(self.bundle)
        bundle['records'][0]['id'] = 'unrelated-review'
        with self.assertRaisesRegex(ValueError, 'wrong evidence record'):
            self.m.check_result(self.result, self.task, self.data, bundle)

    def test_failed_partial_execution_preserves_original_actions(self):
        self.execute()
        self.result['task_state'] = 'blocked'
        original = deepcopy((self.task, self.result, self.bundle))
        with self.assertRaises(ValueError):
            self.check(bundle=False)
        self.assertEqual(original, (self.task, self.result, self.bundle))
        self.assertEqual(self.result['action_refs'], ['synthetic-new-action'])

    def test_cli_only_reads_explicit_files_and_labels_replay(self):
        # Nonexistent refs remain references: no fetching, no claimed proof of authenticity.
        self.bundle['records'][0]['artifact_ref'] = 'file:///nonexistent/private-document'
        self.bundle['records'][2]['artifact_ref'] = 'https://example.invalid/not-fetched'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in [('task', self.task), ('result', self.result), ('bundle', self.bundle)]:
                (root / (name + '.json')).write_text(json.dumps(value))
            cmd = [sys.executable, str(self.m.BASE / 'scripts/catalog.py'), '--check-task', str(root / 'task.json'),
                   '--evidence-bundle', str(root / 'bundle.json')]
            run = subprocess.run(cmd + ['--result', str(root / 'result.json'), '--replay-at', self.at.isoformat()],
                                 cwd=root, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            answer = json.loads(run.stdout)
            self.assertEqual(answer['evidence_profile']['clock_mode'], 'declared_replay')
            self.assertFalse(answer['evidence_profile']['current_evidence_ready'])
            self.assertEqual(answer['authorization'], 'not_verified')
            run = subprocess.run(cmd + ['--check-ready', '--replay-at', self.at.isoformat()], text=True, capture_output=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn('cannot be mixed', run.stderr)

    def test_cli_legacy_bundle_and_replay_without_evidence_not_ignored(self):
        fixture = Path(__file__).parent / 'fixtures/task-v1.1.json'
        examples = self.m.BASE / 'references/examples'
        cmd = [sys.executable, str(self.m.BASE / 'scripts/catalog.py')]
        for args in (['--check-task', str(fixture), '--evidence-bundle', str(examples / 'evidence-bundle.json')],
                     ['--check-task', str(fixture), '--replay-at', self.at.isoformat()],
                     ['--check-task', str(examples / 'evidence-task.json'), '--replay-at', self.at.isoformat()]):
            with self.subTest(args=args):
                run = subprocess.run(cmd + args, text=True, capture_output=True)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(run.stdout, '')


if __name__ == '__main__':
    unittest.main()
