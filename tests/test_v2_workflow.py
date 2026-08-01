from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class V2WorkflowTest(unittest.TestCase):
    def test_new_skill_name_is_used_consistently(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: ros-ros2-systems-engineer", skill)
        agent = yaml.safe_load((ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        self.assertIn("$ros-ros2-systems-engineer", agent["interface"]["default_prompt"])

    def test_package_excludes_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            (root / "agents").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A sufficiently detailed demo skill description for validation.\n---\n",
                encoding="utf-8",
            )
            (root / "agents" / "openai.yaml").write_text(
                "interface:\n  display_name: Demo\n  short_description: Demo\n  default_prompt: Use $demo.\n",
                encoding="utf-8",
            )
            (root / "run.log").write_text("temporary", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "package_skill.py"), str(root), str(Path(tmp) / "dist")],
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with zipfile.ZipFile(Path(tmp) / "dist" / "skill.zip") as archive:
                self.assertNotIn("run.log", archive.namelist())


if __name__ == "__main__":
    unittest.main()
