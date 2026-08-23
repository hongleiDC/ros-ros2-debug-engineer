from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), SCRIPTS / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoeticIncrementalPipelineTest(unittest.TestCase):
    def test_profile_diff_uses_current_hardware_keys_and_targeted_plan(self) -> None:
        module = load_script("diff_system_profiles.py")
        before = {
            "hardware": {"observed_device_paths": ["/dev/ttyUSB0"]},
            "topics": [{"name": "/imu/data", "live_type": "sensor_msgs/Imu"}],
            "time": {"expected_use_sim_time": False},
        }
        after = {
            "hardware": {"observed_device_paths": ["/dev/ttyUSB1"]},
            "topics": [{"name": "/imu/data", "live_type": "custom_msgs/Imu"}],
            "time": {"expected_use_sim_time": True},
        }
        result = module.compare(before, after)
        self.assertEqual(result["changed_domains"], ["hardware", "topics", "time"])
        self.assertEqual(result["affected_topics"], ["/imu/data"])
        actions = [item["action"] for item in result["refresh_plan"]]
        self.assertEqual(actions, ["inspect_system_hardware", "probe_topic", "inspect_tf_time"])

    def test_incremental_update_preserves_unsupplied_cached_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            launch = root / "launch.json"
            runtime = root / "runtime.json"
            launch.write_text('{"launch": 1}\n', encoding="utf-8")
            runtime.write_text('{"runtime": 1}\n', encoding="utf-8")
            first = subprocess.run(
                [sys.executable, str(SCRIPTS / "incremental_evidence.py"), "update", "--cache", str(cache), "--launch", str(launch), "--runtime", str(runtime)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            launch.write_text('{"launch": 2}\n', encoding="utf-8")
            second = subprocess.run(
                [sys.executable, str(SCRIPTS / "incremental_evidence.py"), "update", "--cache", str(cache), "--launch", str(launch)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
            manifest = yaml.safe_load((cache / "manifest.yaml").read_text(encoding="utf-8"))
            result = yaml.safe_load(second.stdout)
            self.assertEqual(set(manifest["entries"]), {"launch", "runtime"})
            self.assertEqual(result["preserved_cached_domains"], ["runtime"])

    def test_profile_manager_saves_compact_session_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profile = root / "robot_profile.yaml"
            summary = root / "session_summary.yaml"
            profile.write_text('target:\n  ros_version: "1"\n  ros_distro: noetic\n', encoding="utf-8")
            summary.write_text('known: {}\nunknown: []\n', encoding="utf-8")
            saved = subprocess.run(
                [sys.executable, str(SCRIPTS / "profile_manager.py"), "save", "--profiles", str(profiles), "--profile", str(profile), "--summary", str(summary)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(saved.returncode, 0, saved.stderr + saved.stdout)
            self.assertTrue((profiles / "v0001" / "robot_profile.yaml").is_file())
            self.assertTrue((profiles / "v0001" / "session_summary.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
