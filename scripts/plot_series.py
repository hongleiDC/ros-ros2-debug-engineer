#!/usr/bin/env python3
"""Plot one or more numeric CSV series for agent-independent ROS Noetic result review."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


def load_columns(path: Path, x_key: str, y_keys: List[str]) -> Tuple[List[float], Dict[str, List[float]], int]:
    xs = []
    ys = {key: [] for key in y_keys}
    skipped = 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [key for key in [x_key] + y_keys if key not in fields]
        if missing:
            raise ValueError("missing CSV columns: %s" % ", ".join(missing))
        for row in reader:
            try:
                x_value = float(row[x_key])
                y_values = [float(row[key]) for key in y_keys]
            except (TypeError, ValueError):
                skipped += 1
                continue
            xs.append(x_value)
            for key, value in zip(y_keys, y_values):
                ys[key].append(value)
    if not xs:
        raise ValueError("no numeric rows were available for the requested columns")
    return xs, ys, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--x", required=True, help="numeric x-axis column")
    parser.add_argument("--y", action="append", required=True, help="numeric y-axis column; repeat for multiple series")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title")
    parser.add_argument("--xlabel")
    parser.add_argument("--ylabel")
    parser.add_argument("--metadata", type=Path, help="optional JSON provenance record")
    args = parser.parse_args()

    source = args.csv_file.expanduser().resolve()
    if not source.is_file():
        raise SystemExit("CSV file not found: %s" % source)
    try:
        xs, ys, skipped = load_columns(source, args.x, args.y)
    except ValueError as exc:
        raise SystemExit(str(exc))

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots()
    for key in args.y:
        ax.plot(xs, ys[key], label=key)
    ax.set_xlabel(args.xlabel or args.x)
    ax.set_ylabel(args.ylabel or (args.y[0] if len(args.y) == 1 else "value"))
    if args.title:
        ax.set_title(args.title)
    if len(args.y) > 1:
        ax.legend()
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)

    metadata = {
        "schema_version": 1,
        "kind": "offline_series_plot",
        "source_csv": str(source),
        "x": args.x,
        "y": args.y,
        "rows_plotted": len(xs),
        "rows_skipped": skipped,
        "output": str(output),
        "title": args.title,
        "xlabel": args.xlabel or args.x,
        "ylabel": args.ylabel or (args.y[0] if len(args.y) == 1 else "value"),
    }
    metadata_path = args.metadata.expanduser().resolve() if args.metadata else output.with_suffix(output.suffix + ".json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
