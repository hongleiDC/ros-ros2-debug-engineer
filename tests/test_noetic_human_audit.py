from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class NoeticHumanAuditTest(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_result_bundle_and_native_logger_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_script(
                "result_bundle.py", "init", str(root / "reports"), "EXP-1", "--run-id", "RUN-1"
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            run_dir = root / "reports" / "EXP-1" / "RUN-1"
            self.assertTrue((run_dir / "bags").is_dir())
            manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["ros_evidence"]["bags"], [])

            bag = self.run_script(
                "ros_noetic_run_logger.py", "record", str(run_dir),
                "--topic", "/odom", "--dry-run",
            )
            self.assertEqual(bag.returncode, 0, bag.stderr + bag.stdout)
            self.assertIn("rosbag record", bag.stdout)
            self.assertIn("/diagnostics", bag.stdout)
            self.assertIn("/odom", bag.stdout)

            snapshot = self.run_script(
                "ros_noetic_run_logger.py", "snapshot", str(run_dir), "--dry-run"
            )
            self.assertEqual(snapshot.returncode, 0, snapshot.stderr + snapshot.stdout)
            payload = json.loads(snapshot.stdout)
            command_names = [item[0] for item in payload["commands"]]
            self.assertIn("rosnode", command_names)
            self.assertIn("rostopic", command_names)

            valid = self.run_script("result_bundle.py", "validate", str(run_dir))
            self.assertEqual(valid.returncode, 0, valid.stderr + valid.stdout)

    def test_logger_registers_ros_evidence_in_manifest(self) -> None:
        spec = importlib.util.spec_from_file_location("ros_noetic_run_logger", SCRIPTS / "ros_noetic_run_logger.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "bags").mkdir()
            (run_dir / "manifest.yaml").write_text(
                yaml.safe_dump({"ros_evidence": {"snapshot_manifest": None, "roslaunch_logs": None, "bags": []}}),
                encoding="utf-8",
            )
            bag = run_dir / "bags" / "audit.bag"
            bag.write_bytes(b"bag")
            module.register_evidence(run_dir, "bags", bag)
            manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["ros_evidence"]["bags"], ["bags/audit.bag"])

    def test_generic_series_plot_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "series.csv"
            with source.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["distance_m", "error_m", "runtime_ms"])
                writer.writeheader()
                for index in range(5):
                    writer.writerow({"distance_m": index, "error_m": index * 0.1, "runtime_ms": 20 + index})
            output = root / "plots" / "audit.png"
            result = self.run_script(
                "plot_series.py", str(source),
                "--x", "distance_m",
                "--y", "error_m",
                "--y", "runtime_ms",
                "--output", str(output),
                "--title", "Audit series",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(output.is_file())
            metadata = output.with_suffix(".png.json")
            self.assertTrue(metadata.is_file())
            record = json.loads(metadata.read_text(encoding="utf-8"))
            self.assertEqual(record["rows_plotted"], 5)
            self.assertEqual(record["x"], "distance_m")

    def test_bootstrap_keeps_analysis_contract_and_audit_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            result = self.run_script("bootstrap_analysis_tooling.py", str(project), "--system", "lio")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((project / "analysis" / "analysis_profile.yaml").is_file())
            self.assertTrue((project / "analysis" / "observation_contract.yaml").is_file())
            tools = project / "tools" / "analysis"
            self.assertTrue((tools / "ros_noetic_run_logger.py").is_file())
            self.assertTrue((tools / "plot_series.py").is_file())
            profile = yaml.safe_load((project / "analysis" / "analysis_profile.yaml").read_text(encoding="utf-8"))
            self.assertEqual(profile["system"], "lio")


if __name__ == "__main__":
    unittest.main()
