from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class SkillTest(unittest.TestCase):
    def run_script(self, name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        current_env = os.environ.copy()
        if env:
            current_env.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
            env=current_env,
        )

    def init_project(self, tmp: str) -> tuple[Path, Path]:
        repo = Path(tmp) / "project"
        result = self.run_script("init_project_knowledge.py", str(repo), "--project-id", "example_project")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return repo, repo / "project_knowledge"

    def test_initialize_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            result = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            marker = yaml.safe_load((repo / ".ros_debug_project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(marker["knowledge_dir"], "project_knowledge")
            self.assertTrue((knowledge / "project_model.yaml").is_file())

    def test_workspace_inspection_builds_l1_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            package = root / "src" / "demo_pkg"
            (package / "src").mkdir(parents=True)
            (package / "launch").mkdir()
            (package / "msg").mkdir()
            (package / "package.xml").write_text("""<package format="3">
<name>demo_pkg</name><version>0.1.0</version><description>x</description>
<maintainer email="a@b.com">a</maintainer><license>MIT</license>
<buildtool_depend>ament_cmake</buildtool_depend><depend>rclcpp</depend>
<export><build_type>ament_cmake</build_type></export></package>""", encoding="utf-8")
            (package / "CMakeLists.txt").write_text(
                "add_executable(demo_node src/node.cpp)\nrclcpp_components_register_nodes(demo_component \"demo::Node\")\n",
                encoding="utf-8",
            )
            (package / "src" / "node.cpp").write_text(
                "rclcpp_lifecycle::LifecycleNode n; auto g=create_callback_group(); // sensor_msgs::msg::Imu tf2",
                encoding="utf-8",
            )
            (package / "launch" / "demo.launch.py").write_text("# launch", encoding="utf-8")
            (package / "msg" / "Status.msg").write_text("bool ok", encoding="utf-8")
            result = self.run_script("inspect_workspace.py", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data["coverage"]["understanding_level"], "L1")
            self.assertEqual(data["packages"][0]["name"], "demo_pkg")
            self.assertIn("demo_node", data["packages"][0]["executables"])
            self.assertTrue(data["capabilities"]["lifecycle"])
            self.assertTrue(data["capabilities"]["callback_groups"])
            self.assertTrue(data["artifacts"]["interfaces"])

    def test_runtime_snapshot_gracefully_handles_missing_ros(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": tmp, "ROS_VERSION": ""}
            result = self.run_script("collect_runtime_snapshot.py", "--ros-version", "auto", env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data["ros_version"], "unknown")
            self.assertEqual(data["coverage"]["successful_commands"], 0)

    def test_update_records_old_new_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.use_sim_time", "true", "--status", "measured",
                "--reason", "test", "--evidence", "unit test",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = yaml.safe_load((knowledge / "active_configuration.yaml").read_text(encoding="utf-8"))
            self.assertTrue(data["configuration"]["use_sim_time"])
            changelog = (knowledge / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("old value", changelog)
            self.assertFalse((knowledge / ".knowledge-transaction.json").exists())

    def test_verified_record_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            path = knowledge / "active_configuration.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["status"] = "verified"
            path.write_text(yaml.safe_dump(data), encoding="utf-8")
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.value", "1", "--status", "verified",
                "--reason", "test", "--evidence", "unit test",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verified", result.stderr + result.stdout)

    def test_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            target = knowledge / "topics.yaml"
            original = target.read_text(encoding="utf-8")
            target.write_text("broken: true\n", encoding="utf-8")
            changelog = knowledge / "CHANGELOG.md"
            old_log = changelog.read_text(encoding="utf-8")
            journal = {
                "target_relative": "topics.yaml",
                "target_existed": True,
                "target_old": base64.b64encode(original.encode()).decode(),
                "changelog_existed": True,
                "changelog_old": base64.b64encode(old_log.encode()).decode(),
            }
            (knowledge / ".knowledge-transaction.json").write_text(json.dumps(journal), encoding="utf-8")
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.test", "true", "--status", "candidate",
                "--reason", "recover", "--evidence", "journal", "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertFalse((knowledge / ".knowledge-transaction.json").exists())

    def test_incident_id_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            bad = self.run_script("new_incident.py", str(knowledge), "../../bad", "escape")
            self.assertNotEqual(bad.returncode, 0)
            good = self.run_script("new_incident.py", str(knowledge), "INC-0001", "timestamp mismatch")
            self.assertEqual(good.returncode, 0, good.stderr + good.stdout)
            incident = next((knowledge / "incidents").glob("*.yaml"))
            data = yaml.safe_load(incident.read_text(encoding="utf-8"))
            self.assertEqual(data["incident_id"], "INC-0001")
            validate = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def test_invalid_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            (knowledge / "devices" / "bad.yaml").write_text(
                yaml.safe_dump({"schema_version": 1, "device_id": "bad", "status": "verified"}),
                encoding="utf-8",
            )
            result = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manufacturer", result.stdout)

    def test_package_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script("package_skill.py", str(ROOT), tmp)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((Path(tmp) / "skill.zip").is_file())


if __name__ == "__main__":
    unittest.main()
