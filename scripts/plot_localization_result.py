#!/usr/bin/env python3
"""Generate a compact formal localization plot set from aligned error CSV data."""
from __future__ import annotations

import argparse
import csv
import math
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


def save_trajectory(data: dict[str, list[float]], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> None:
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
    fig.savefig(out / "trajectory_xy.png", dpi=160)
    plt.close(fig)


def save_horizontal(data: dict[str, list[float]], distance: list[float], out: Path, label: str, baseline: dict[str, list[float]] | None, baseline_label: str) -> None:
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
    fig.savefig(out / "horizontal_error.png", dpi=160)
    plt.close(fig)


def save_components(data: dict[str, list[float]], distance: list[float], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    plotted = False
    for name, label in (("err_lateral", "lateral"), ("err_longitudinal", "longitudinal"), ("err_z", "vertical")):
        if name in data:
            x, y = finite_pairs(distance, data[name])
            ax.plot(x, y, label=label)
            plotted = True
    ax.axhline(0.0, linewidth=0.8)
    ax.set_xlabel("Reference distance [m]")
    ax.set_ylabel("Signed error [m]")
    ax.set_title("Error Components vs Distance")
    ax.grid(True, alpha=0.25)
    if plotted:
        ax.legend()
    fig.tight_layout()
    fig.savefig(out / "error_components.png", dpi=160)
    plt.close(fig)


def save_segment(data: dict[str, list[float]], distance: list[float], out: Path, label: str, segment_m: float, baseline: dict[str, list[float]] | None, baseline_label: str) -> None:
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
    fig.savefig(out / "segment_rmse.png", dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv")
    parser.add_argument("--output-dir", required=True)
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
    distance = cumulative_distance(data["rtk_e"], data["rtk_n"])
    save_trajectory(data, out, args.label, baseline, args.baseline_label)
    save_horizontal(data, distance, out, args.label, baseline, args.baseline_label)
    save_components(data, distance, out)
    save_segment(data, distance, out, args.label, args.segment_m, baseline, args.baseline_label)
    print(out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
