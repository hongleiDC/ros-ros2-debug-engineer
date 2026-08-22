from __future__ import annotations

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class NoeticScriptContractTest(unittest.TestCase):
    def test_experiment_registry_uses_ros1_network_environment(self) -> None:
        text = (ROOT / "scripts" / "experiment_registry.py").read_text(encoding="utf-8")
        for required in [
            "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME", "ROS_PACKAGE_PATH",
            "CMAKE_PREFIX_PATH", "PYTHONPATH", '"bag" if Path(p).suffix.lower() == ".bag"',
        ]:
            self.assertIn(required, text)
        for forbidden in ["RMW_IMPLEMENTATION", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY"]:
            self.assertNotIn(forbidden, text)

    def test_goal_guard_captures_noetic_environment(self) -> None:
        text = (ROOT / "scripts" / "goal_guard.py").read_text(encoding="utf-8")
        for required in [
            '"ros_version": "1"', '"ros_distro": "noetic"', "ROS_MASTER_URI",
            "ROS_IP", "ROS_HOSTNAME", "ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH",
        ]:
            self.assertIn(required, text)
        for forbidden in ["RMW_IMPLEMENTATION", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY"]:
            self.assertNotIn(forbidden, text)

    def test_result_bundle_captures_noetic_target(self) -> None:
        text = (ROOT / "scripts" / "result_bundle.py").read_text(encoding="utf-8")
        for required in ["ROS_MASTER_URI", "ROS_PACKAGE_PATH", '"ros_version": "1"', '"ros_distro": "noetic"', '".bag"']:
            self.assertIn(required, text)
        for forbidden in [".mcap", ".db3", "RMW_IMPLEMENTATION", "ROS_DOMAIN_ID"]:
            self.assertNotIn(forbidden, text)

    def test_project_initializer_declares_noetic_without_claiming_runtime_verification(self) -> None:
        text = (ROOT / "scripts" / "init_project_knowledge.py").read_text(encoding="utf-8")
        for required in ['"families": ["ros1"]', '"distributions": ["noetic"]', '"build_tools": ["catkin"]', '"runtime_verified": False']:
            self.assertIn(required, text)

    def test_project_schema_only_accepts_ros1_noetic(self) -> None:
        schema = yaml.safe_load((ROOT / "references" / "schemas" / "project.schema.yaml").read_text(encoding="utf-8"))
        ros = schema["properties"]["ros"]["properties"]
        self.assertEqual(ros["families"]["items"]["const"], "ros1")
        self.assertEqual(ros["distributions"]["items"]["const"], "noetic")
        self.assertNotIn("ros2", str(schema).lower())

    def test_experiment_schema_uses_noetic_environment_fields(self) -> None:
        schema = yaml.safe_load((ROOT / "references" / "schemas" / "experiment.schema.yaml").read_text(encoding="utf-8"))
        environment = schema["properties"]["environment"]
        required = set(environment["required"])
        properties = set(environment["properties"])
        self.assertTrue({"ros_version", "ros_distro", "ros_master_uri", "operating_system", "architecture"}.issubset(required))
        self.assertTrue({"ros_ip", "ros_hostname", "ros_package_path", "cmake_prefix_path", "pythonpath"}.issubset(properties))
        self.assertNotIn("rmw_implementation", properties)
        self.assertNotIn("ros_domain_id", properties)

    def test_ros2_runtime_reference_is_not_packaged_in_noetic_branch(self) -> None:
        self.assertFalse((ROOT / "references" / "ros2_runtime.md").exists())
        self.assertTrue((ROOT / "references" / "ros1_ros2_migration.md").is_file())


if __name__ == "__main__":
    unittest.main()
