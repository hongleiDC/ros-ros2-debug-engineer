from __future__ import annotations

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


class NoeticSkillCoreTest(unittest.TestCase):
    def run_script(
        self,
        name: str,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
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

    def init_git(self, repo: Path) -> None:
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        (repo / "package.xml").write_text(
            "<package format='2'><name>demo</name><version>0.1.0</version>"
            "<description>x</description><maintainer email='a@b.com'>a</maintainer>"
            "<license>MIT</license><buildtool_depend>catkin</buildtool_depend></package>",
            encoding="utf-8",
        )
        (repo / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.0.2)\nfind_package(catkin REQUIRED)\ncatkin_package()\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, capture_output=True)

    def start_goal(self, repo: Path, knowledge: Path) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "goal_guard.py", "start", str(knowledge), "GOAL-0001", "Fix timestamp root cause",
            "--workspace", str(repo),
            "--request", "Fix timestamp rollback in ROS Noetic",
            "--desired-outcome", "No rollback without localization regression",
            "--primary-goal", "Eliminate timestamp rollback in the Noetic pipeline without reducing localization accuracy",
            "--success", "No timestamp rollback::runtime logs and counters",
            "--milestone", "Establish a reproducible Noetic baseline",
            "--milestone", "Implement and verify the minimal fix",
            env={
                "ROS_VERSION": "1",
                "ROS_DISTRO": "noetic",
                "ROS_MASTER_URI": "http://localhost:11311",
                "ROS_HOSTNAME": "robot-a",
            },
        )

    def test_documentation_contract_is_wired(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        coding = (ROOT / "references" / "coding_rules.md").read_text(encoding="utf-8")
        trace = ROOT / "references" / "formula_variable_traceability.md"
        reasoning = ROOT / "references" / "reasoning_knowledge_base.md"
        self.assertIn("name: ros-noetic-systems-engineer", skill)
        self.assertIn("formula_variable_traceability.md", skill)
        self.assertIn("reasoning_knowledge_base.md", skill)
        self.assertIn("公式符号到代码变量", coding)
        self.assertTrue(trace.is_file())
        self.assertTrue(reasoning.is_file())
        for required in ["已知条件", "变量映射", "单位", "frame", "逐行变换", "魔法数"]:
            self.assertIn(required, trace.read_text(encoding="utf-8"))
        for script in ["logic_audit.py", "register_reasoning_knowledge.py"]:
            self.assertTrue((SCRIPTS / script).is_file())

    def test_initialize_and_validate_noetic_project_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            result = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            project = yaml.safe_load((knowledge / "project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(project["ros"]["families"], ["ros1"])
            self.assertEqual(project["ros"]["distributions"], ["noetic"])
            self.assertEqual(project["ros"]["build_tools"], ["catkin"])
            model = yaml.safe_load((knowledge / "project_model.yaml").read_text(encoding="utf-8"))
            self.assertEqual(model["environment"]["target_ros_version"], "1")
            self.assertEqual(model["environment"]["target_ros_distro"], "noetic")
            self.assertFalse(model["environment"]["runtime_verified"])
            marker = yaml.safe_load((repo / ".ros_debug_project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(marker["knowledge_dir"], "project_knowledge")
            self.assertEqual(marker["target"], {"ros_version": "1", "ros_distro": "noetic"})

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
            self.assertIn("old value", (knowledge / "CHANGELOG.md").read_text(encoding="utf-8"))

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

    def test_incident_id_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            bad = self.run_script("new_incident.py", str(knowledge), "../../bad", "escape")
            self.assertNotEqual(bad.returncode, 0)
            good = self.run_script("new_incident.py", str(knowledge), "INC-0001", "timestamp mismatch")
            self.assertEqual(good.returncode, 0, good.stderr + good.stdout)
            validate = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def test_goal_guard_captures_noetic_network_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            self.init_git(repo)
            started = self.start_goal(repo, knowledge)
            self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
            goal = yaml.safe_load((knowledge / "goals" / "GOAL-0001.yaml").read_text(encoding="utf-8"))
            environment = goal["scope"]["environment"]
            self.assertEqual(environment["target"], {"ros_version": "1", "ros_distro": "noetic"})
            self.assertEqual(environment["ros_version"], "1")
            self.assertEqual(environment["ros_distro"], "noetic")
            self.assertEqual(environment["ros_master_uri"], "http://localhost:11311")
            self.assertEqual(environment["ros_hostname"], "robot-a")
            self.assertNotIn("rmw_implementation", environment)

    def test_experiment_registry_captures_bag_and_noetic_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            self.init_git(repo)
            started = self.start_goal(repo, knowledge)
            self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
            bag = repo / "sample.bag"
            config = repo / "config.yaml"
            bag.write_bytes(b"rosbag-fixture")
            config.write_text("use_sim_time: true\n", encoding="utf-8")
            result = self.run_script(
                "experiment_registry.py", "create", str(knowledge), "EXP-0001", "Noetic bag replay",
                "--workspace", str(repo),
                "--objective", "Verify the timestamp fix on a fixed rosbag1 input",
                "--hypothesis", "The timestamp fix removes rollback on this bag",
                "--criterion", "SC-1",
                "--milestone", "M-1",
                "--alignment", "This replay directly tests the active timestamp rollback criterion",
                "--input-file", str(bag),
                "--parameter-file", str(config),
                "--change", "timestamp conversion only",
                "--command", "roslaunch demo replay.launch bag:=sample.bag",
                "--expected", "No timestamp rollback is observed",
                env={
                    "ROS_VERSION": "1",
                    "ROS_DISTRO": "noetic",
                    "ROS_MASTER_URI": "http://localhost:11311",
                    "ROS_IP": "192.0.2.10",
                    "ROS_PACKAGE_PATH": "/opt/ros/noetic/share",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            record = yaml.safe_load((knowledge / "experiments" / "EXP-0001.yaml").read_text(encoding="utf-8"))
            self.assertEqual(record["inputs"]["files"][0]["kind"], "bag")
            environment = record["environment"]
            self.assertEqual(environment["ros_version"], "1")
            self.assertEqual(environment["ros_distro"], "noetic")
            self.assertEqual(environment["ros_master_uri"], "http://localhost:11311")
            self.assertEqual(environment["ros_ip"], "192.0.2.10")
            self.assertNotIn("rmw_implementation", environment)
            self.assertNotIn("ros_domain_id", environment)

    def test_result_bundle_records_noetic_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            result = self.run_script(
                "result_bundle.py", "init", str(reports), "EXP-0001",
                "--run-id", "RUN-test", "--label", "test",
                env={
                    "ROS_VERSION": "1",
                    "ROS_DISTRO": "noetic",
                    "ROS_MASTER_URI": "http://localhost:11311",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            manifest = yaml.safe_load((reports / "EXP-0001" / "RUN-test" / "manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["environment"]["target"], {"ros_version": "1", "ros_distro": "noetic"})
            self.assertTrue(manifest["environment"]["matches_target_if_known"])
            self.assertEqual(manifest["environment"]["observed"]["ROS_MASTER_URI"], "http://localhost:11311")


if __name__ == "__main__":
    unittest.main()
