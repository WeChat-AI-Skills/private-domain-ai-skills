"""Check meaningful catalog/contract failures and the actual installed bundle."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import build_catalog_docs
import install_skills
import validate_architecture as architecture

ROOT = architecture.ROOT
OPS = architecture.OPS


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.module = architecture.runtime()
        self.data = self.module.load(OPS)
        self.names = {s["name"] for s in json.loads((ROOT / "manifest.json").read_text())["skills"]}
        self.task = json.loads((OPS / "references/examples/first-task.json").read_text())
        self.result = json.loads((OPS / "references/examples/first-result.json").read_text())

    def errors(self):
        return architecture.validate(self.data, self.names)

    def test_current_catalog_and_sample_contracts(self):
        self.assertEqual(self.errors(), [])
        self.module.check_result(self.result, self.task, self.data)

    def test_intermediate_manager_is_rejected(self):
        self.data["agents"]["agents"][2]["reports_to"] = "operations-agent"
        self.assertTrue(any("direct report" in p for p in self.errors()))

    def test_unknown_skill_cannot_appear_as_installed(self):
        self.data["tree"]["nodes"][0]["skill_refs"].append("missing-skill")
        self.assertTrue(any("unknown skill" in p for p in self.errors()))

    def test_missing_role_profile(self):
        self.data["agents"]["agents"][1]["profile"] = "../agents/missing.md"
        self.assertTrue(any("role profile" in p for p in self.errors()))

    def test_missing_required_workflows_rejected(self):
        original = deepcopy(self.data["workflows"]["workflows"])
        for removed in ({"customer-followup"}, {"group-invite"}, {"customer-followup", "group-invite"}):
            self.data["workflows"]["workflows"] = [w for w in original if w["id"] not in removed]
            with self.subTest(removed=removed):
                self.assertTrue(any("workflow set differs" in p and all(i in p for i in removed) for p in self.errors()))

    def test_workflow_cycle_rejected(self):
        self.data["workflows"]["workflows"][0]["steps"][0]["depends_on"] = ["review"]
        self.assertTrue(any("cycle" in p for p in self.errors()))

    def test_draft_path_cannot_require_write(self):
        self.data["workflows"]["workflows"][0]["steps"][0]["kind"] = "external"
        self.assertTrue(any("draft path" in p for p in self.errors()))

    def test_unmapped_workflow_skill_rejected(self):
        self.data["workflows"]["workflows"][0]["steps"][0]["skill_refs"] = ["sales-review"]
        self.assertTrue(any("not mapped" in p for p in self.errors()))

    def test_listing_query_exposes_gap(self):
        domain = self.module.lookup(self.data, "domain", "listing")
        self.assertEqual(len(domain["nodes"]), 4)
        self.assertTrue(all(n["method_coverage"] == "planned" and not n["skill_refs"] for n in domain["nodes"]))
        self.assertEqual(self.module.lookup(self.data, "role", "product-agent")["skill_refs"], [])

    def test_unknown_lookup_errors(self):
        with self.assertRaises(ValueError):
            self.module.lookup(self.data, "node", "SKU-99")

    def test_cross_tenant_or_task_result_rejected(self):
        for field, value in (("scope", {**self.task["scope"], "tenant_id": "another-tenant"}),
                             ("scope", {**self.task["scope"], "account_id": "another-account"}),
                             ("task_id", "another-task"), ("agent_id", "product-agent")):
            result = deepcopy(self.result)
            result[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "does not match"):
                self.module.check_result(result, self.task, self.data)

    def test_draft_and_readonly_cannot_claim_new_actions(self):
        self.result["action_refs"] = ["synthetic-write"]
        for mode in ("draft", "readonly"):
            self.task["execution_mode"] = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "cannot claim"):
                self.module.check_result(self.result, self.task, self.data)

    def test_execute_requires_action_authority_and_tool_fields(self):
        self.task["execution_mode"] = "execute"
        with self.assertRaisesRegex(ValueError, "Missing text"):
            self.module.check_task(self.task, self.data)
        self.task.update(action="moments.submit", content_version="synthetic-v1", authorization_ref="synthetic-grant",
                         policy_version="synthetic-policy", capability_check_ref="synthetic-environment", risk_level="L2")
        self.module.check_task(self.task, self.data)
        # Presence of fields passes structure only, not real authorization.
        self.task["capability_ids"] = ["SKU-04"]
        with self.assertRaisesRegex(ValueError, "Planned capability"):
            self.module.check_task(self.task, self.data)

    def test_completed_without_any_delivery_rejected(self):
        self.result["artifacts"] = []
        self.result["evidence_refs"] = []
        with self.assertRaisesRegex(ValueError, "needs artifacts"):
            self.module.check_result(self.result, self.task, self.data)

    def test_optional_skill_and_dependency_fields(self):
        for update in ({"skill_refs": ["product-listing"]}, {"skill_refs": "moments-calendar"},
                       {"depends_on": [self.task["task_id"]]}, {"depends_on": 17},
                       {"skill_refs": ["moments-calendar", "moments-calendar"]}):
            task = {**self.task, **update}
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.module.check_task(task, self.data)
            with self.subTest(result_update=update), self.assertRaises(ValueError):
                self.module.check_result(self.result, task, self.data)
        self.module.check_task({**self.task, "skill_refs": ["moments-calendar"], "depends_on": ["synthetic-prior-task"]}, self.data)

    def test_generated_docs_follow_catalog(self):
        for relative, expected in build_catalog_docs.outputs().items():
            self.assertEqual((ROOT / relative).read_text(), expected, relative)

    def test_fresh_installed_copy_contains_runnable_catalog_and_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills"
            install_skills.install(ROOT, target)
            installed = target / "private-domain-ops"
            module = architecture.runtime(installed)
            data = module.load(installed)
            self.assertEqual(architecture.validate(data, self.names, installed), [])
            for name in self.names:
                self.assertEqual(install_skills.hashes(target / name), install_skills.hashes(ROOT / ".agents/skills" / name))
            process = subprocess.run([sys.executable, str(installed / "scripts/catalog.py"), "--node", "MOM-03"],
                                     cwd=tmp, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["live_status"], "not_verified")
            for cwd in (tmp, installed):
                process = subprocess.run([sys.executable, str(installed / "scripts/catalog.py"), "--role", "content-agent"],
                                         cwd=cwd, capture_output=True, text=True)
                self.assertEqual(process.returncode, 0, process.stderr)
                role = json.loads(process.stdout)
                self.assertEqual(Path(role["profile_path"]).read_bytes(), (installed / "references/agents/content-agent.md").read_bytes())
                self.assertEqual((Path(role["profile_base"]) / role["profile"]).resolve(), Path(role["profile_path"]))
            # A lost resource must be caught in the installation, not hidden by the source checkout.
            (installed / "references/agents/content-agent.md").unlink()
            self.assertTrue(any("role profile" in p for p in architecture.validate(data, self.names, installed)))


if __name__ == "__main__":
    unittest.main()
