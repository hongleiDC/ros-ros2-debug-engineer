from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), SCRIPTS / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoeticSystemEvidenceTest(unittest.TestCase):
    def test_tf_time_semantics(self):
        module = load_script("inspect_tf_time.py")
        summary = module.summarize_time_semantics(True, ["/tf", "/clock"], False)
        self.assertEqual(summary["ros_time_mode"], "sim")
        self.assertTrue(summary["clock_topic_present"])
        self.assertTrue(any("not synchronized" in x for x in summary["warnings"]))

    def test_merge_conflicts_are_preserved(self):
        module = load_script("merge_system_evidence.py")
        launch = {"target":{"ros_version":"1","ros_distro":"noetic"},"summary":{"packages":[]},"nodes":[],"params":[{"name":"/use_sim_time","value":"true"}],"hardware_hints":[{"value":"/dev/ttyUSB0"}]}
        bag = {"topics":[{"topic":"/imu/data","type":"sensor_msgs/Imu"}]}
        runtime = {"commands":[{"command":["rostopic","list"],"returncode":0,"stdout":"/imu/data\n"},{"command":["rosnode","list"],"returncode":0,"stdout":""},{"command":["rosservice","list"],"returncode":0,"stdout":""}]}
        probe = {"topic":"/imu/data","results":{"type":{"returncode":0,"stdout":"other/Imu"}}}
        tf = {"summary":{"use_sim_time":False}}
        result = module.merge_evidence([launch],[bag],[runtime],[],[tf],[probe])
        self.assertEqual(result["status"], "conflict")
        self.assertTrue(result["conflicts"])

    def test_missing_sources_are_unknown(self):
        module = load_script("merge_system_evidence.py")
        result = module.merge_evidence([],[],[],[],[],[])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["unknowns"])


if __name__ == "__main__":
    unittest.main()
