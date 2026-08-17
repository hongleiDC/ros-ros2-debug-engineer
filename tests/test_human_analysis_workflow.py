from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class HumanAnalysisWorkflowTest(unittest.TestCase):
    def run_script(self, path: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(path), *args], text=True, capture_output=True, check=False, cwd=str(cwd) if cwd else None)

    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, float]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_project_local_tooling_generates_human_report_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            boot = self.run_script(SCRIPTS / "bootstrap_analysis_tooling.py", str(project), "--system", "lio")
            self.assertEqual(boot.returncode, 0, boot.stderr + boot.stdout)
            self.assertTrue((project / "analysis" / "analysis_profile.yaml").is_file())
            self.assertTrue((project / "analysis" / "observation_contract.yaml").is_file())
            tools = project / "tools" / "analysis"
            for name in ("analyze_run.py", "plot_localization_result.py", "plot_slam_diagnostics.py", "result_bundle.py"):
                self.assertTrue((tools / name).is_file())

            init = self.run_script(
                tools / "result_bundle.py", "init", str(project / "reports"), "EXP-0001",
                "--run-id", "RUN-test", "--label", "test", cwd=project,
            )
            self.assertEqual(init.returncode, 0, init.stderr + init.stdout)
            run_dir = project / "reports" / "EXP-0001" / "RUN-test"

            aligned_rows = []
            diagnostics_rows = []
            for i in range(40):
                e = float(i) * 2.0
                n = float(i) * 0.2
                aligned_rows.append({
                    "rtk_e": e,
                    "rtk_n": n,
                    "rtk_u": 0.0,
                    "lio_aligned_x": e + 0.01 * i,
                    "lio_aligned_y": n + 0.005 * i,
                    "lio_aligned_z": 0.0,
                    "err_horizontal": 0.012 * i,
                    "err_lateral": 0.005 * i,
                    "err_longitudinal": 0.01 * i,
                    "err_z": 0.0,
                })
                diagnostics_rows.append({
                    "distance_m": e,
                    "velocity_error_longitudinal_mps": 0.001 * i,
                    "scan_match_correction_longitudinal_m": -0.002 * i,
                    "longitudinal_information": 10.0 - 0.05 * i,
                    "frame_runtime_ms": 20.0 + 0.1 * i,
                })
            self.write_csv(run_dir / "series" / "aligned_errors.csv", list(aligned_rows[0]), aligned_rows)
            self.write_csv(run_dir / "series" / "diagnostics.csv", list(diagnostics_rows[0]), diagnostics_rows)

            manifest_path = run_dir / "manifest.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "completed"
            manifest["verdict"] = "keep"
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            (run_dir / "metrics.json").write_text(json.dumps({"schema_version": 1, "run_id": "RUN-test", "metrics": {"horizontal_rmse_m": {"value": 0.25, "unit": "m", "direction": "lower"}}}, indent=2), encoding="utf-8")
            (run_dir / "report.md").write_text("# Decision\n\nKeep the run for review.\n\n# Evidence\n\nThe normalized metric and static evidence report are available for independent inspection.\n\n# Remaining risk\n\nNo additional risk is asserted by this unit test.\n", encoding="utf-8")

            analyzed = self.run_script(tools / "analyze_run.py", str(run_dir), "--strict", cwd=project)
            self.assertEqual(analyzed.returncode, 0, analyzed.stderr + analyzed.stdout)
            summary = json.loads((run_dir / "report" / "analysis_summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["ready_for_human_review"])
            self.assertTrue((run_dir / "report" / "index.html").is_file())
            self.assertGreaterEqual(summary["plot_count"], 8)

            validated = self.run_script(tools / "result_bundle.py", "validate", str(run_dir), "--closure", "--human-analysis", cwd=project)
            self.assertEqual(validated.returncode, 0, validated.stderr + validated.stdout)


if __name__ == "__main__":
    unittest.main()
