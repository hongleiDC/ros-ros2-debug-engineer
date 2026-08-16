#!/usr/bin/env python3
"""Compare two normalized result-bundle metrics.json files."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("metrics"), dict):
        raise ValueError(f"{path}: expected an object with a metrics mapping")
    return data


def normalize_metric(name: str, raw: object) -> dict[str, object]:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return {"name": name, "value": float(raw), "unit": None, "direction": None}
    if not isinstance(raw, dict):
        raise ValueError(f"metric {name}: expected number or object")
    value = raw.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"metric {name}: value must be a finite number")
    return {
        "name": name,
        "value": float(value),
        "unit": raw.get("unit"),
        "direction": raw.get("direction"),
    }


def compare(baseline: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    bmetrics = baseline["metrics"]
    cmetrics = candidate["metrics"]
    assert isinstance(bmetrics, dict) and isinstance(cmetrics, dict)
    rows: dict[str, object] = {}
    for name in sorted(set(bmetrics) & set(cmetrics)):
        base = normalize_metric(name, bmetrics[name])
        cand = normalize_metric(name, cmetrics[name])
        if base["unit"] and cand["unit"] and base["unit"] != cand["unit"]:
            raise ValueError(f"metric {name}: unit mismatch {base['unit']!r} vs {cand['unit']!r}")
        b = float(base["value"])
        c = float(cand["value"])
        delta = c - b
        relative_percent = None if b == 0.0 else delta / abs(b) * 100.0
        direction = cand["direction"] or base["direction"]
        improved = None
        if direction == "lower":
            improved = c < b
        elif direction == "higher":
            improved = c > b
        rows[name] = {
            "baseline": b,
            "candidate": c,
            "unit": cand["unit"] or base["unit"],
            "direction": direction,
            "delta": delta,
            "relative_percent": relative_percent,
            "improved": improved,
        }
    return {
        "schema_version": 1,
        "baseline_run": baseline.get("run_id"),
        "candidate_run": candidate.get("run_id"),
        "metrics": rows,
        "only_in_baseline": sorted(set(bmetrics) - set(cmetrics)),
        "only_in_candidate": sorted(set(cmetrics) - set(bmetrics)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", default="delta_metrics.json")
    args = parser.parse_args()
    baseline = load(Path(args.baseline))
    candidate = load(Path(args.candidate))
    result = compare(baseline, candidate)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
