#!/usr/bin/env python3
"""Create and validate a compact, reproducible ROS experiment result bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

REQUIRED_DIRS = ("series", "plots", "logs")
REQUIRED_FILES = ("manifest.yaml", "metrics.json", "report.md")
PLOT_SUFFIXES = {".png", ".svg", ".pdf"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip()).strip("-").lower()
    return value[:48] or "run"


def run_git(workspace: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(workspace), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def git_info(workspace: Path | None) -> dict[str, object]:
    if workspace is None:
        return {"workspace": None, "branch": None, "commit": None, "dirty": None}
    commit = run_git(workspace, "rev-parse", "HEAD")
    branch = run_git(workspace, "rev-parse", "--abbrev-ref", "HEAD")
    status = run_git(workspace, "status", "--porcelain")
    return {"workspace": str(workspace.resolve()), "branch": branch, "commit": commit, "dirty": None if status is None else bool(status)}


def file_records(paths: Iterable[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        record: dict[str, object] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            record["size_bytes"] = path.stat().st_size
            record["sha256"] = sha256_file(path)
        records.append(record)
    return records


def atomic_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def build_run_id(label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{stamp}-{slug(label)}"


def init_bundle(args: argparse.Namespace) -> int:
    reports_root = Path(args.reports_root).expanduser().resolve()
    run_id = args.run_id or build_run_id(args.label or args.experiment_id)
    run_dir = reports_root / args.experiment_id / run_id
    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        raise SystemExit(f"refusing to overwrite non-empty run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_DIRS:
        (run_dir / name).mkdir(exist_ok=True)
    (run_dir / "report").mkdir(exist_ok=True)

    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else None
    manifest = {
        "schema_version": 1,
        "experiment_id": args.experiment_id,
        "run_id": run_id,
        "created_utc": utc_now(),
        "label": args.label,
        "git": git_info(workspace),
        "inputs": {"datasets": file_records(args.dataset_file), "configs": file_records(args.config_file)},
        "command": args.command,
        "baseline_run": args.baseline_run,
        "status": "planned",
        "verdict": "pending",
        "artifacts": {
            "metrics": "metrics.json",
            "series_dir": "series",
            "plots_dir": "plots",
            "logs_dir": "logs",
            "report": "report.md",
            "human_report": "report/index.html",
            "analysis_summary": "report/analysis_summary.json",
        },
    }
    atomic_text(run_dir / "manifest.yaml", yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    metrics = {"schema_version": 1, "run_id": run_id, "metrics": {}}
    atomic_text(run_dir / "metrics.json", json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    report = (
        f"# {args.experiment_id} / {run_id}\n\n"
        "## Decision\n\nTODO: state the decision first.\n\n"
        "## Evidence\n\nTODO: cite metrics and plots that support the decision.\n\n"
        "## Remaining risk\n\nTODO: record only unresolved risks that affect the next decision.\n"
    )
    atomic_text(run_dir / "report.md", report)
    print(run_dir)
    return 0


def validate_bundle(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not run_dir.is_dir():
        errors.append(f"missing run directory: {run_dir}")
    for name in REQUIRED_DIRS:
        if not (run_dir / name).is_dir():
            errors.append(f"missing directory: {name}/")
    for name in REQUIRED_FILES:
        if not (run_dir / name).is_file():
            errors.append(f"missing file: {name}")

    manifest: dict[str, object] = {}
    metrics: dict[str, object] = {}
    manifest_path = run_dir / "manifest.yaml"
    metrics_path = run_dir / "metrics.json"
    report_path = run_dir / "report.md"
    if manifest_path.is_file():
        try:
            loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = loaded
            else:
                errors.append("manifest.yaml must contain a mapping")
        except yaml.YAMLError as exc:
            errors.append(f"invalid manifest.yaml: {exc}")
    if metrics_path.is_file():
        try:
            loaded = json.loads(metrics_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metrics = loaded
            else:
                errors.append("metrics.json must contain an object")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid metrics.json: {exc}")

    for key in ("schema_version", "experiment_id", "run_id", "status", "verdict", "artifacts"):
        if key not in manifest:
            errors.append(f"manifest.yaml missing key: {key}")
    if manifest.get("run_id") and metrics.get("run_id") and manifest.get("run_id") != metrics.get("run_id"):
        errors.append("run_id differs between manifest.yaml and metrics.json")
    metric_map = metrics.get("metrics") if isinstance(metrics, dict) else None
    if metric_map is not None and not isinstance(metric_map, dict):
        errors.append("metrics.json metrics must be an object")

    if args.closure:
        if manifest.get("status") != "completed":
            errors.append("closure requires manifest status: completed")
        if manifest.get("verdict") in (None, "", "pending"):
            errors.append("closure requires a non-pending verdict")
        if not isinstance(metric_map, dict) or not metric_map:
            errors.append("closure requires at least one normalized metric")
        plot_dir = run_dir / "plots"
        plots = [path for path in plot_dir.rglob("*") if path.is_file() and path.suffix.lower() in PLOT_SUFFIXES] if plot_dir.is_dir() else []
        if not plots:
            errors.append("closure requires at least one formal offline plot")
        if report_path.is_file():
            report = report_path.read_text(encoding="utf-8")
            if "TODO:" in report:
                errors.append("closure requires report.md TODO items to be resolved")
            if len(report.strip()) < 80:
                errors.append("closure requires a substantive report.md")

    if args.human_analysis:
        index_path = run_dir / "report" / "index.html"
        summary_path = run_dir / "report" / "analysis_summary.json"
        if not index_path.is_file():
            errors.append("human-analysis validation requires report/index.html")
        if not summary_path.is_file():
            errors.append("human-analysis validation requires report/analysis_summary.json")
        else:
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                if not isinstance(summary, dict) or summary.get("ready_for_human_review") is not True:
                    errors.append("human-analysis validation requires ready_for_human_review: true")
            except json.JSONDecodeError as exc:
                errors.append(f"invalid report/analysis_summary.json: {exc}")

    for path in run_dir.iterdir() if run_dir.is_dir() else []:
        if path.is_file() and path.suffix.lower() in {".csv", ".log", ".bag", ".db3", ".mcap"}:
            warnings.append(f"top-level raw artifact should live under series/ or logs/: {path.name}")

    result = {"run_dir": str(run_dir), "valid": not errors, "errors": errors, "warnings": warnings}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)
    init = sub.add_parser("init", help="create a new result bundle")
    init.add_argument("reports_root")
    init.add_argument("experiment_id")
    init.add_argument("--run-id")
    init.add_argument("--label")
    init.add_argument("--workspace")
    init.add_argument("--dataset-file", action="append", default=[])
    init.add_argument("--config-file", action="append", default=[])
    init.add_argument("--command")
    init.add_argument("--baseline-run")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=init_bundle)
    validate = sub.add_parser("validate", help="validate an existing result bundle")
    validate.add_argument("run_dir")
    validate.add_argument("--closure", action="store_true")
    validate.add_argument("--human-analysis", action="store_true", help="also require a ready static human analysis report")
    validate.set_defaults(func=validate_bundle)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
