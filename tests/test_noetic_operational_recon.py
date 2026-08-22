from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), SCRIPTS / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            "inspect_system_hardware.py", "hardware_candidates",
        ]:
            self.assertIn(required, text)

    def test_rosbag_inspector_normalizes_topic_semantics_without_ros_runtime(self) -> None:
        module = load_script("inspect_rosbag.py")
        info = {
            "path": "sample.bag",
            "duration": 10.0,
            "messages": 100,
            "types": [
                {"type": "sensor_msgs/Imu", "md5": "imu-md5"},
                {"type": "sensor_msgs/PointCloud2", "md5": "cloud-md5"},
            ],
            "topics": [
                {"topic": "/imu/data", "type": "sensor_msgs/Imu", "messages": 50, "connections": 1, "frequency": 5.0},
                {"topic": "/points_raw", "type": "sensor_msgs/PointCloud2", "messages": 20, "connections": 1, "frequency": 2.0},
                {"topic": "/diagnostics", "type": "diagnostic_msgs/DiagnosticArray", "messages": 30, "connections": 1, "frequency": 3.0},
            ],
        }
        normalized = module.normalize_info(info)
        self.assertEqual(normalized["topic_count"], 3)
        self.assertEqual(normalized["topics"][0]["role"], "imu")
        self.assertEqual(normalized["topics"][1]["role"], "lidar")
        self.assertEqual(normalized["topics"][0]["md5"], "imu-md5")
        self.assertAlmostEqual(normalized["topics"][0]["bag_average_hz"], 5.0)
        self.assertEqual(module.classify_topic("/fix", "sensor_msgs/NavSatFix"), "gnss")
        self.assertEqual(module.classify_topic("/camera/image_raw", "sensor_msgs/Image"), "camera")

    def test_hardware_inventory_classifier_is_dependency_free(self) -> None:
        module = load_script("inspect_system_hardware.py")
        self.assertEqual(module.classify_device_path("/dev/ttyUSB0"), "serial")
        self.assertEqual(module.classify_device_path("/dev/serial/by-id/usb-demo"), "serial")
        self.assertEqual(module.classify_device_path("/dev/video0"), "video")
        self.assertEqual(module.interface_role("can0"), "can")
        self.assertEqual(module.interface_role("eth0"), "ethernet")
        self.assertEqual(module.interface_role("wlan0"), "wifi")

    def test_rosbag_reference_requires_topic_semantics_not_only_replay(self) -> None:
        text = (ROOT / "references" / "rosbag.md").read_text(encoding="utf-8")
        for required in [
            "inspect_rosbag.py", "message type + MD5", "callerid", "bag time - header stamp",
            "PointCloud2", "NavSatFix", "bounded sample", "driver/sensor",
        ]:
            self.assertIn(required, text)

    def test_skill_routes_unknown_systems_to_reconnaissance(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for required in [
            "Noetic 命令作战手册", "硬件适配与系统勘察", "inspect_rosbag.py",
            "硬件 → OS 设备 → 驱动/节点 → topic → message → frame → time",
        ]:
            self.assertIn(required, skill)


if __name__ == "__main__":
    unittest.main()
