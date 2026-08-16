from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ResultVisualizationTest(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def write_csv(self, path: Path, fieldnames: list[str], rows: list[dict[str, float]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_localization_core_generates_six_plots_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "series" / "aligned_errors.csv"
            rows = []
            for i in range(40):
                rtk_e = float(i) * 2.0
                rtk_n = float(i) * 0.25
                rtk_u = float(i) * 0.02
                longitudinal = 0.01 * i
                lateral = 0.02 * (i % 5)
                vertical = 0.005 * i
                rows.append(
                    {
                        "rtk_e": rtk_e,
                        "rtk_n": rtk_n,
                        "rtk_u": rtk_u,
                        "lio_aligned_x": rtk_e + longitudinal,
                        "lio_aligned_y": rtk_n + lateral,
                        "lio_aligned_z": rtk_u + vertical,
                        "err_horizontal": (longitudinal * longitudinal + lateral * lateral) ** 0.5,
                        "err_lateral": lateral,
                        "err_longitudinal": longitudinal,
                        "err_z": vertical,
                    }
                )
            self.write_csv(source, list(rows[0]), rows)
            plots = root / "plots"
            core = plots / "01_core"
            manifest = plots / "plot_manifest.json"
            result = self.run_script(
                "plot_localization_result.py",
                str(source),
                "--output-dir", str(core),
                "--manifest", str(manifest),
                "--segment-m", "20",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            expected = {
                "trajectory_xy.png",
                "height_profile.png",
                "horizontal_error.png",
                "error_components.png",
                "segment_rmse.png",
                "horizontal_error_cdf.png",
            }
            self.assertEqual({path.name for path in core.glob("*.png")}, expected)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(len(data["plots"]), 6)
            self.assertTrue(all(item["group"] == "core" for item in data["plots"]))
            self.assertTrue(all(item["question"] for item in data["plots"]))

    def test_slam_diagnostics_generates_selected_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "series" / "diagnostics.csv"
            rows = []
            for i in range(50):
                rows.append(
                    {
                        "distance_m": float(i) * 3.0,
                        "velocity_longitudinal_mps": 8.0 + 0.01 * i,
                        "reference_velocity_longitudinal_mps": 8.0,
                        "velocity_error_longitudinal_mps": 0.01 * i,
                        "gyro_bias_x_rad_s": 0.0001 * i,
                        "accel_bias_x_mps2": 0.001 * i,
                        "scan_match_correction_longitudinal_m": -0.01 * i,
                        "scan_match_residual_m": 0.1 + 0.001 * i,
                        "correspondence_count": 120.0 - i,
                        "longitudinal_information": 10.0 - 0.1 * i,
                        "lateral_information": 20.0,
                        "yaw_information": 15.0,
                        "hessian_min_eigenvalue": 0.5 - 0.005 * i,
                        "hessian_condition_number": 10.0 + i,
                        "rtk_innovation_m": 0.2 + 0.01 * i,
                        "rtk_gate_m": 1.0,
                        "rtk_accepted": 1.0 if i < 35 else 0.0,
                        "frame_runtime_ms": 30.0 + 0.1 * i,
                        "scan_match_runtime_ms": 12.0 + 0.05 * i,
                        "map_update_runtime_ms": 4.0,
                        "cpu_percent": 55.0 + 0.2 * i,
                        "rss_mb": 600.0 + i,
                    }
                )
            self.write_csv(source, list(rows[0]), rows)
            plots = root / "plots"
            manifest = plots / "plot_manifest.json"
            result = self.run_script(
                "plot_slam_diagnostics.py",
                str(source),
                "--category", "estimator",
                "--category", "matching",
                "--category", "observability",
                "--category", "fusion",
                "--category", "runtime",
                "--output-dir", str(plots),
                "--manifest", str(manifest),
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            for relative in (
                "02_estimator/velocity_error.png",
                "03_matching/translation_correction.png",
                "04_observability/directional_information.png",
                "05_fusion/innovation_gate.png",
                "07_runtime/stage_runtime.png",
            ):
                self.assertTrue((plots / relative).is_file(), relative)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            groups = {item["group"] for item in data["plots"]}
            self.assertTrue({"estimator", "matching", "observability", "fusion", "runtime"}.issubset(groups))
            self.assertGreaterEqual(len(data["plots"]), 10)


if __name__ == "__main__":
    unittest.main()
