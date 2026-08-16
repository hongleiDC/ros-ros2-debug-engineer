#!/usr/bin/env python3
"""Generate formal localization Core Evidence from aligned error CSV data."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_series(path: Path) -> dict[str, list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{path}: missing CSV header")
        rows = list(reader)
    columns: dict[str, list[float]] = {name: [] for name in reader.fieldnames}
    for row in rows:
        for name in columns:
            try:
                value = float(row.get(name, "nan"))
            except (TypeError, ValueError):
                value = float("nan")
            columns[name].append(value)
    return columns


def require(data: dict[str, list[float]], names: tuple[str, ...], path: Path) -> None:
    missing = [name for name in names if name not in data]
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")


def cumulative_distance(xs: list[float], ys: list[float]) -> list[float]:
    out = [0.0]
    for i in range(1, min(len(xs), len(ys))):
        if not all(math.isfinite(v) for v in (xs[i - 1], ys[i - 1], xs[i], ys[i])):
            out.append(out[-1])
        else:
            out.append(out[-1] + math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
    return out


def finite_pairs(x: list[float], y: list[float]) -> tuple[list[float], list[float]]:
    pairs = [(a, b) for a, b in zip(x, y) if math.isfinite(a) and math.isfinite(b)]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def rmse(values: list[float]) -> float:
    vals = [v for v in values if math.isfinite(v)]
    return float("nan") if not vals else math.sqrt(sum(v * v for v in vals) / len(vals))


def segment_rmse(distance: list[float], error: list[float], segment_m: float) -> tuple[list[float], list[float]]:
    if segment_m <= 0:
        raise ValueError("segment_m must be positive")
    pairs = [(d, e) for d, e in zip(distance, error) if math.isfinite(d) and math.isfinite(e)]
    if not pairs:
        return [], []
    max_d = max(d for d, _ in pairs)
    centers: list[float] = []
    values: list[float] = []
    start = 0.0
    while start <= max_d:
        end = start + segment_m
        seg = [e for d, e in pairs if start <= d < end]
        if seg:
            centers.append((start + end) / 2.0)
            values.append(rmse(seg))
        start = end
    return centers, values


def relative_plot_path(plot: Path, manifest: Path) -> str:
    return Path(os.path.relpath(plot.resolve(), manifest.parent.resolve())).as_posix()


def update_plot_manifest(manifest: Path, entries: list[dict[str, str]]) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {"schema_version": 1, "plots": []}
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("plots"), list):
                data = loaded
        except (json.JSONDecodeError, OSError):
            pass
    existing = {
        item.get("file"): item
        for item in data.get("plots", [])
        if isinstance(item, dict) and isinstance(item.get("file"), str)
    }
    for entry in entries:
        existing[entry["file"]] = entry
    data["schema_version"] = 1
    data["plots"] = list(existing.values())
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_trajectory(data: dict[str, list[float]], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path:
    path = out / "trajectory_xy.png"
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(data["rtk_e"], data["rtk_n"], label="reference")
    if baseline:
        ax.plot(baseline["lio_aligned_x"], baseline["lio_aligned_y"], label=baseline_label)
    ax.plot(data["lio_aligned_x"], data["lio_aligned_y"], label=label)
    ax.set_xlabel("East [m]")
    ax.set_ylabel("North [m]")
    ax.set_title("Trajectory XY")
    ax.axis("equal")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_height(data: dict[str, list[float]], distance: list[float], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path | None:
    if "rtk_u" not in data or "lio_aligned_z" not in data:
        return None
    path = out / "height_profile.png"
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x, y = finite_pairs(distance, data["rtk_u"])
    ax.plot(x, y, label="reference")
    if baseline and "lio_aligned_z" in baseline and "rtk_e" in baseline and "rtk_n" in baseline:
        bdist = cumulative_distance(baseline["rtk_e"], baseline["rtk_n"])
        bx, by = finite_pairs(bdist, baseline["lio_aligned_z"])
        ax.plot(bx, by, label=baseline_label)
    x, y = finite_pairs(distance, data["lio_aligned_z"])
    ax.plot(x, y, label=label)
    ax.set_xlabel("Reference distance [m]")
    ax.set_ylabel("Up / aligned Z [m]")
    ax.set_title("Height Profile vs Distance")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_horizontal(data: dict[str, list[float]], distance: list[float], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path:
    path = out / "horizontal_error.png"
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if baseline:
        bdist = cumulative_distance(baseline["rtk_e"], baseline["rtk_n"])
        x, y = finite_pairs(bdist, baseline["err_horizontal"])
        ax.plot(x, y, label=baseline_label)
    x, y = finite_pairs(distance, data["err_horizontal"])
    ax.plot(x, y, label=label)
    ax.set_xlabel("Reference distance [m]")
    ax.set_ylabel("Horizontal error [m]")
    ax.set_title("Horizontal Error vs Distance")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_components(data: dict[str, list[float]], distance: list[float], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path | None:
    available = [(name, text) for name, text in (("err_lateral", "lateral"), ("err_longitudinal", "longitudinal"), ("err_z", "vertical")) if name in data]
    if not available:
        return None
    path = out / "error_components.png"
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, text in available:
        if baseline and name in baseline:
            bdist = cumulative_distance(baseline["rtk_e"], baseline["rtk_n"])
            bx, by = finite_pairs(bdist, baseline[name])
            ax.plot(bx, by, linestyle="--", label=f"{baseline_label} {text}")
        x, y = finite_pairs(distance, data[name])
        ax.plot(x, y, label=f"{label} {text}")
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel("Reference distance [m]")
    ax.set_ylabel("Signed error [m]")
    ax.set_title("Error Components vs Distance")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def save_segment(data: dict[str, list[float]], distance: list[float], out: Path, label: str, segment_m: float, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path:
    path = out / "segment_rmse.png"
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if baseline:
        bdist = cumulative_distance(baseline["rtk_e"], baseline["rtk_n"])
        bx, by = segment_rmse(bdist, baseline["err_horizontal"], segment_m)
        ax.plot(bx, by, marker="o", label=baseline_label)
    x, y = segment_rmse(distance, data["err_horizontal"], segment_m)
    ax.plot(x, y, marker="o", label=label)
    ax.set_xlabel("Reference distance [m]")
    ax.set_ylabel("Horizontal RMSE [m]")
    ax.set_title(f"Segment Horizontal RMSE ({segment_m:g} m bins)")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def cdf(values: list[float]) -> tuple[list[float], list[float]]:
    vals = sorted(v for v in values if math.isfinite(v))
    if not vals:
        return [], []
    return vals, [(index + 1) / len(vals) for index in range(len(vals))]


def save_error_cdf(data: dict[str, list[float]], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> Path:
    path = out / "horizontal_error_cdf.png"
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if baseline:
        bx, by = cdf(baseline["err_horizontal"])
        ax.plot(bx, by, label=baseline_label)
    x, y = cdf(data["err_horizontal"])
    ax.plot(x, y, label=label)
    ax.set_xlabel("Horizontal error [m]")
    ax.set_ylabel("CDF")
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Horizontal Error Distribution")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--label", default="candidate")
    parser.add_argument("--baseline-csv")
    parser.add_argument("--baseline-label", default="baseline")
    parser.add_argument("--segment-m", type=float, default=100.0)
    args = parser.parse_args()

    path = Path(args.input_csv)
    data = read_series(path)
    required = ("rtk_e", "rtk_n", "lio_aligned_x", "lio_aligned_y", "err_horizontal")
    require(data, required, path)
    baseline = None
    if args.baseline_csv:
        bpath = Path(args.baseline_csv)
        baseline = read_series(bpath)
        require(baseline, required, bpath)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = Path(args.manifest) if args.manifest else out / "plot_manifest.json"
    distance = cumulative_distance(data["rtk_e"], data["rtk_n"])
    generated: list[tuple[Path, str]] = []
    generated.append((save_trajectory(data, out, args.label, baseline, args.baseline_label), "Where do estimate and reference trajectories diverge spatially?"))
    height = save_height(data, distance, out, args.label, baseline, args.baseline_label)
    if height:
        generated.append((height, "Does vertical/terrain behavior explain part of the trajectory error?"))
    generated.append((save_horizontal(data, distance, out, args.label, baseline, args.baseline_label), "At what traveled distance does horizontal error begin to grow?"))
    components = save_components(data, distance, out, args.label, baseline, args.baseline_label)
    if components:
        generated.append((components, "Which signed error component dominates: lateral, longitudinal, or vertical?"))
    generated.append((save_segment(data, distance, out, args.label, args.segment_m, baseline, args.baseline_label), "Which route segments dominate the aggregate horizontal error?"))
    generated.append((save_error_cdf(data, out, args.label, baseline, args.baseline_label), "Did the error distribution and tail improve, not only the mean/RMSE?"))

    entries = [
        {
            "file": relative_plot_path(plot, manifest),
            "group": "core",
            "question": question,
            "source": str(path),
        }
        for plot, question in generated
    ]
    update_plot_manifest(manifest, entries)
    print(json.dumps({"output_dir": str(out.resolve()), "generated": [str(p) for p, _ in generated], "manifest": str(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
