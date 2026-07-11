from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class KnowledgeToolsTest(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_initialize_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "project"
            init = self.run_script(
                "init_project_knowledge.py",
                str(repo),
                "--project-id",
                "example_project",
            )
            self.assertEqual(init.returncode, 0, init.stderr + init.stdout)
            validate = self.run_script("validate_knowledge.py", str(repo / "project_knowledge"))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)
            marker = yaml.safe_load((repo / ".ros_debug_project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(marker["knowledge_dir"], "project_knowledge")

    def test_update_records_old_and_new_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "project"
            self.assertEqual(self.run_script(
                "init_project_knowledge.py", str(repo), "--project-id", "example_project"
            ).returncode, 0)
            knowledge = repo / "project_knowledge"
            update = self.run_script(
                "update_knowledge.py",
                str(knowledge),
                "active_configuration.yaml",
                "configuration.use_sim_time",
                "true",
                "--status", "measured",
                "--reason", "test",
                "--evidence", "unit test",
            )
            self.assertEqual(update.returncode, 0, update.stderr + update.stdout)
            data = yaml.safe_load((knowledge / "active_configuration.yaml").read_text(encoding="utf-8"))
            self.assertTrue(data["configuration"]["use_sim_time"])
            changelog = (knowledge / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("old value", changelog)
            self.assertIn("new value", changelog)

    def test_verified_record_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "project"
            self.assertEqual(self.run_script(
                "init_project_knowledge.py", str(repo), "--project-id", "example_project"
            ).returncode, 0)
            knowledge = repo / "project_knowledge"
            path = knowledge / "active_configuration.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["status"] = "verified"
            path.write_text(yaml.safe_dump(data), encoding="utf-8")
            update = self.run_script(
                "update_knowledge.py",
                str(knowledge),
                "active_configuration.yaml",
                "configuration.value",
                "1",
                "--status", "verified",
                "--reason", "test",
                "--evidence", "unit test",
            )
            self.assertNotEqual(update.returncode, 0)
            self.assertIn("verified", update.stderr + update.stdout)


if __name__ == "__main__":
    unittest.main()
