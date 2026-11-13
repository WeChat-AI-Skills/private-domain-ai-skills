"""Exercise installation failures, update protection and rollback with synthetic files."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_skills as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.target = self.base / "host" / "skills"
        for name in ("one", "two"):
            p = self.root / ".agents/skills" / name
            p.mkdir(parents=True)
            (p / "SKILL.md").write_text("synthetic version 1\n")
        self.set_version("1.0.0")

    def tearDown(self):
        self.temp.cleanup()

    def set_version(self, version):
        (self.root / "manifest.json").write_text(json.dumps({"version": version, "skills": [
            {"name": name, "path": ".agents/skills/" + name} for name in ("one", "two")]}))

    def run_install(self, **kwargs):
        return installer.install(self.root, self.target, **kwargs)

    def test_fresh_idempotent_and_dry_run(self):
        self.run_install(dry_run=True)
        self.assertFalse(self.target.exists())
        self.run_install()
        self.assertTrue(self.run_install()["unchanged"])
        self.assertEqual(installer.hashes(self.root / ".agents/skills/one"), installer.hashes(self.target / "one"))

    def test_unmanaged_conflict_stops_entire_batch(self):
        (self.target / "two").mkdir(parents=True)
        (self.target / "two/SKILL.md").write_text("customer file")
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            self.run_install()
        self.assertFalse((self.target / "one").exists())
        self.assertEqual((self.target / "two/SKILL.md").read_text(), "customer file")

    def test_symlink_preserved(self):
        self.target.mkdir(parents=True)
        (self.target / "one").symlink_to(self.root / ".agents/skills/one", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_install(update=True)
        self.assertTrue((self.target / "one").is_symlink())
        self.assertFalse((self.target / "two").exists())

    def test_modified_copy_preserved(self):
        self.run_install()
        (self.target / "one/SKILL.md").write_text("customer change")
        with self.assertRaisesRegex(ValueError, "modifications"):
            self.run_install(update=True)
        self.assertEqual((self.target / "one/SKILL.md").read_text(), "customer change")

    def test_explicit_update_and_downgrade(self):
        self.run_install()
        self.set_version("1.1.0")
        (self.root / ".agents/skills/one/SKILL.md").write_text("version 2")
        with self.assertRaisesRegex(ValueError, "--update"):
            self.run_install()
        self.run_install(update=True)
        self.assertEqual((self.target / "one/SKILL.md").read_text(), "version 2")
        self.set_version("1.0.0")
        (self.root / ".agents/skills/one/SKILL.md").write_text("synthetic version 1\n")
        self.run_install(update=True)
        self.assertEqual(json.loads((self.target / installer.RECEIPT).read_text())["version"], "1.0.0")

    def test_failure_restores_previous_contents_and_receipt(self):
        self.run_install()
        original = (self.target / installer.RECEIPT).read_bytes()
        self.set_version("1.1.0")
        (self.root / ".agents/skills/one/SKILL.md").write_text("version 2")
        with patch.object(installer.os, "replace", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.run_install(update=True)
        self.assertEqual((self.target / installer.RECEIPT).read_bytes(), original)
        self.assertEqual((self.target / "one/SKILL.md").read_text(), "synthetic version 1\n")
        self.assertFalse((self.target / installer.LOCK).exists())

    def test_busy_lock_and_unrelated_skill(self):
        self.target.mkdir(parents=True)
        (self.target / "unrelated").mkdir()
        (self.target / installer.LOCK).mkdir()
        with self.assertRaisesRegex(ValueError, "lock"):
            self.run_install()
        (self.target / installer.LOCK).rmdir()
        self.run_install()
        self.assertTrue((self.target / "unrelated").is_dir())

    def test_customer_change_during_staging_is_preserved(self):
        self.run_install()
        self.set_version("1.1.0")
        copytree = installer.shutil.copytree

        def change_after_copy(*args, **kwargs):
            result = copytree(*args, **kwargs)
            (self.target / "one/SKILL.md").write_text("customer change during update")
            return result

        with patch.object(installer.shutil, "copytree", side_effect=change_after_copy):
            with self.assertRaisesRegex(ValueError, "modifications"):
                self.run_install(update=True)
        self.assertEqual((self.target / "one/SKILL.md").read_text(), "customer change during update")
        self.assertEqual(json.loads((self.target / installer.RECEIPT).read_text())["version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
