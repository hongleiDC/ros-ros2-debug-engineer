from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), SCRIPTS / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoeticDeepOperationsTest(unittest.TestCase):
    def test_specialized_reference_covers_noetic_operational_stacks(self) -> None:
        text = (ROOT / "references" / "noetic_specialized_operations.md").read_text(encoding="utf-8")
        for required in ["dynparam list", "nodelet nodelet list", "rospack plugins --attrib=plugin nodelet", "controller_manager controller_manager list", "sensor_msgs/PointCloud2", "rviz -d", "/gazebo/model_states"]:
            self.assertIn(required, text)

    def test_evidence_workflow_routes_all_primary_artifacts(self) -> None:
        text = (ROOT / "references" / "evidence_intake_workflow.md").read_text(encoding="utf-8")
        for required in ["scripts/inspect_launch.py", "scripts/inspect_rosbag.py", "scripts/probe_topic.py", "scripts/collect_runtime_snapshot.py", "scripts/inspect_system_hardware.py", "expected", "observed-live", "recorded"]:
            self.assertIn(required, text)

    def test_new_operational_references_remain_noetic_scoped(self) -> None:
        forbidden = ["ROS_DOMAIN_ID", "RMW_IMPLEMENTATION", "ROS_LOCALHOST_ONLY", "ros2 launch", "ros2 topic", "ros2 service", "ros2 bag", "ament_cmake", "rclcpp_components_register_nodes", ".launch.py", ".mcap", ".db3"]
        for name in ["noetic_specialized_operations.md", "evidence_intake_workflow.md"]:
            text = (ROOT / "references" / name).read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(reference=name, token=token):
                    self.assertNotIn(token, text)

    def test_launch_inspector_extracts_stack_and_hardware_hints(self) -> None:
        module = load_script("inspect_launch.py")
        xml = '''<launch>
          <arg name="port" default="/dev/serial/by-id/usb-imu"/>
          <node pkg="nodelet" type="nodelet" name="manager" args="manager"/>
          <node pkg="nodelet" type="nodelet" name="filter" args="load pcl_ros/VoxelGrid manager"/>
          <node pkg="controller_manager" type="spawner" name="spawner" args="joint_state_controller"/>
          <node pkg="rviz" type="rviz" name="rviz"/>
          <include file="$(find gazebo_ros)/launch/empty_world.launch"/>
          <param name="serial_port" value="$(arg port)"/>
        </launch>'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "system.launch"
            path.write_text(xml, encoding="utf-8")
            payload = module.inspect_launch(path)
        self.assertEqual(payload["summary"]["nodes"], 4)
        self.assertTrue({"nodelet", "ros_control", "gazebo", "rviz", "pcl"}.issubset(set(payload["stack_hints"])))
        self.assertTrue(any("/dev/serial/by-id/" in hint["value"] for hint in payload["hardware_hints"]))
        self.assertGreaterEqual(len(payload["nodelet_records"]), 2)
        self.assertGreaterEqual(len(payload["controller_records"]), 1)
        self.assertIn("$(find gazebo_ros)", payload["substitutions"])

    def test_topic_probe_builds_only_read_only_rostopic_commands(self) -> None:
        module = load_script("probe_topic.py")
        probes = module.build_probe_commands("/points_raw", 10, True, True)
        names = [name for name, _, _ in probes]
        self.assertEqual(names, ["info", "type", "sample", "hz", "bw", "delay"])
        commands = [command for _, command, _ in probes]
        self.assertIn(["rostopic", "echo", "-n", "1", "--noarr", "/points_raw"], commands)
        for command in commands:
            self.assertEqual(command[0], "rostopic")
            self.assertNotIn("pub", command)
        text = (SCRIPTS / "probe_topic.py").read_text(encoding="utf-8")
        self.assertNotIn("rosservice call", text)
        self.assertNotIn("rostopic pub", text)


if __name__ == "__main__":
    unittest.main()
