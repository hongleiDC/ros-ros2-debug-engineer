from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class NoeticOperationalReconTest(unittest.TestCase):
    def test_command_reference_covers_runtime_and_bag_inventory(self) -> None:
        text = (ROOT / "references" / "noetic_command_playbook.md").read_text(encoding="utf-8")
        for required in [
            "rospack find", "rosnode info", "rostopic list -v", "rostopic hz", "rostopic bw",
            "rostopic delay", "rosservice info", "rosparam get", "roslaunch --nodes",
            "tf_monitor", "rosbag info -y", "rostopic list -b", "rostopic echo -b",
            "ROS_MASTER_URI", "CMAKE_PREFIX_PATH",
        ]:
            self.assertIn(required, text)

    def test_hardware_reference_maps_physical_device_to_ros_evidence(self) -> None:
        text = (ROOT / "references" / "hardware_adaptation.md").read_text(encoding="utf-8")
        for required in [
            "硬件 → OS 设备 → 驱动/节点 → topic → message → frame → time",
            "lsusb", "/dev/serial/by-id/", "udevadm info", "ip neigh", "PointCloud2",
            "sensor_msgs/Imu", "GNSS / RTK / 双天线", "timedatectl", "changed / unchanged / unknown",
        ]:
            self.assertIn(required, text)

    def test_rosbag_inspector_parser_and_topic_selection_are_dependency_free(self) -> None:
        spec = importlib.util.spec_from_file_location("inspect_rosbag", SCRIPTS / "inspect_rosbag.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = """
path: sample.bag
version: 2.0
duration: 10.0
messages: 100
topics:
  - topic: /imu/data
    type: sensor_msgs/Imu
    messages: 50
    frequency: 5.0
  - topic: /points_raw
    type: sensor_msgs/PointCloud2
    messages: 20
    frequency: 2.0
  - topic: /diagnostics
    type: diagnostic_msgs/DiagnosticArray
    messages: 30
    frequency: 3.0
"""
        info = module.parse_rosbag_info_yaml(fixture)
        index = module.topic_index(info)
        self.assertEqual(len(index), 3)
        selected = module.select_topics(index, [], 2)
        self.assertEqual(selected, ["/imu/data", "/points_raw"])
        self.assertEqual(index[0]["type"], "sensor_msgs/Imu")

    def test_skill_routes_unknown_systems_to_reconnaissance(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for required in [
            "Noetic 命令作战手册", "硬件适配与系统勘察", "inspect_rosbag.py",
            "硬件 → OS 设备 → 驱动/节点 → topic → message → frame → time",
        ]:
            self.assertIn(required, skill)


if __name__ == "__main__":
    unittest.main()
