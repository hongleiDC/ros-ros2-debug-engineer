from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class NoeticBranchContractTest(unittest.TestCase):
    def run_script(self, name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        current_env = dict(**__import__("os").environ)
        if env is not None:
            current_env.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
            env=current_env,
        )

    def test_skill_is_explicitly_locked_to_noetic(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: ros-noetic-systems-engineer", text)
        self.assertIn("ROS_VERSION=1", text)
        self.assertIn("ROS_DISTRO=noetic", text)
        for forbidden_default in ["不讨论 DDS/RMW/QoS", "不使用 rosbag2", "不使用 `ros2 ...` CLI"]:
            self.assertIn(forbidden_default, text)

    def test_architecture_reference_uses_ros1_runtime_model(self) -> None:
        text = (ROOT / "references" / "architecture_design.md").read_text(encoding="utf-8")
        for required in [
            "nodelet", "TCPROS", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME",
            "AsyncSpinner", "CallbackQueue", "actionlib", "dynamic_reconfigure", "rosbag1",
        ]:
            self.assertIn(required, text)
        self.assertIn("不要把 ROS 2", text)

    def test_distro_reference_is_noetic_contract_not_ros2_router(self) -> None:
        text = (ROOT / "references" / "distro_compatibility.md").read_text(encoding="utf-8")
        self.assertIn("本分支只服务 ROS 1 Noetic", text)
        self.assertIn("EOL", text)
        self.assertNotIn("Lyrical", text)
        self.assertNotIn("Rolling", text)

    def test_workspace_inspector_recognizes_noetic_constructs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "src" / "demo_pkg"
            (pkg / "src").mkdir(parents=True)
            (pkg / "launch").mkdir()
            (pkg / "cfg").mkdir()
            (pkg / "package.xml").write_text(
                "<package format='2'><name>demo_pkg</name><version>0.1.0</version>"
                "<description>x</description><maintainer email='a@b.com'>a</maintainer><license>MIT</license>"
                "<buildtool_depend>catkin</buildtool_depend><depend>roscpp</depend>"
                "<depend>nodelet</depend><depend>actionlib</depend><depend>dynamic_reconfigure</depend></package>",
                encoding="utf-8",
            )
            (pkg / "CMakeLists.txt").write_text(
                "find_package(catkin REQUIRED COMPONENTS roscpp nodelet actionlib dynamic_reconfigure)\n"
                "catkin_package()\n"
                "add_executable(demo_node src/node.cpp)\n"
                "generate_dynamic_reconfigure_options(cfg/Demo.cfg)\n",
                encoding="utf-8",
            )
            (pkg / "src" / "node.cpp").write_text(
                "ros::NodeHandle nh; actionlib::SimpleActionClient<X> c(\"x\", true); "
                "dynamic_reconfigure::Server<Cfg> server; class N : public nodelet::Nodelet {};",
                encoding="utf-8",
            )
            (pkg / "launch" / "demo.launch").write_text("<launch><node pkg='demo_pkg' type='demo_node' name='demo'/></launch>", encoding="utf-8")
            (pkg / "cfg" / "Demo.cfg").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            result = self.run_script("inspect_workspace.py", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data["target"], {"ros_version": "1", "ros_distro": "noetic"})
            self.assertTrue(data["capabilities"]["catkin"])
            self.assertTrue(data["capabilities"]["actionlib"])
            self.assertTrue(data["capabilities"]["dynamic_reconfigure"])
            self.assertTrue(data["capabilities"]["nodelet"])
            self.assertFalse(data["compatibility"]["foreign_ros2_signals_detected"])
            self.assertIn("src/demo_pkg/launch/demo.launch", data["artifacts"]["launch"])

    def test_workspace_inspector_flags_ros2_as_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "src" / "foreign_pkg"
            (pkg / "src").mkdir(parents=True)
            (pkg / "package.xml").write_text(
                "<package format='3'><name>foreign_pkg</name><version>0.1.0</version>"
                "<description>x</description><maintainer email='a@b.com'>a</maintainer><license>MIT</license>"
                "<buildtool_depend>ament_cmake</buildtool_depend><depend>rclcpp</depend></package>",
                encoding="utf-8",
            )
            (pkg / "CMakeLists.txt").write_text("ament_target_dependencies(foo rclcpp)\n", encoding="utf-8")
            (pkg / "src" / "node.cpp").write_text("rclcpp::Node node(\"x\");\n", encoding="utf-8")
            result = self.run_script("inspect_workspace.py", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertTrue(data["compatibility"]["foreign_ros2_signals_detected"])
            self.assertEqual(data["compatibility"]["decision"], "review_version_mismatch")

    def test_preflight_none_remains_dependency_free(self) -> None:
        result = self.run_script("preflight.py", "--require", "none", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"]["ROS_DISTRO"], "noetic")


if __name__ == "__main__":
    unittest.main()
