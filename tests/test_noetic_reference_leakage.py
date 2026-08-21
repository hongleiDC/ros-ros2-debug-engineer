from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NoeticReferenceLeakageTest(unittest.TestCase):
    def test_operational_references_do_not_use_ros2_runtime_commands(self) -> None:
        reference_names = [
            "debugging_workflow.md",
            "coding_rules.md",
            "architecture_patterns.md",
            "safety_and_permissions.md",
            "time_sync.md",
            "tf_calibration.md",
            "lidar_imu_rtk_slam.md",
            "experiment_management.md",
            "result_management.md",
        ]
        forbidden = [
            "ROS_DOMAIN_ID",
            "RMW_IMPLEMENTATION",
            "ros2 launch",
            "ros2 topic",
            "ros2 service",
            "ros2 bag",
            "ament_cmake",
            "rclcpp_components_register_nodes",
            ".launch.py",
            ".mcap",
        ]
        for name in reference_names:
            text = (ROOT / "references" / name).read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(reference=name, token=token):
                    self.assertNotIn(token, text)

    def test_noetic_operational_references_contain_ros1_anchors(self) -> None:
        required_by_file = {
            "debugging_workflow.md": ["catkin", "ROS_MASTER_URI", "TCPROS", "AsyncSpinner"],
            "coding_rules.md": ["catkin_package", "CallbackQueue", "message_runtime"],
            "architecture_patterns.md": ["nodelet", "actionlib", "ROS_HOSTNAME"],
            "safety_and_permissions.md": ["rosbag info", "ROS_MASTER_URI"],
            "time_sync.md": ["/use_sim_time", "rosbag play --clock", "message_filters"],
            "tf_calibration.md": ["tf_monitor", "ros::Time(0)", "/tf_static"],
            "lidar_imu_rtk_slam.md": ["sensor_msgs/PointCloud2", "rosnode info", "rosbag1"],
            "experiment_management.md": ["data/run04.bag", "roslaunch my_pkg replay.launch"],
            "result_management.md": ["rosbag1", "ROS_PACKAGE_PATH", "roslaunch"],
        }
        for name, tokens in required_by_file.items():
            text = (ROOT / "references" / name).read_text(encoding="utf-8")
            for token in tokens:
                with self.subTest(reference=name, token=token):
                    self.assertIn(token, text)

    def test_ros2_terms_are_quarantined_to_explicit_compatibility_contexts(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        inspector = (ROOT / "scripts" / "inspect_workspace.py").read_text(encoding="utf-8")
        migration = (ROOT / "references" / "ros1_ros2_migration.md").read_text(encoding="utf-8")
        self.assertIn("不使用 `ros2 ...` CLI", skill)
        self.assertIn("foreign_ros2_signal", inspector)
        self.assertIn("ROS 1", migration)
        self.assertIn("ROS 2", migration)


if __name__ == "__main__":
    unittest.main()
