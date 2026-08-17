#!/usr/bin/env python3
"""Generate a static, human-readable analysis report for one result bundle."""
from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
import sys
from pathlib import Path

import yaml


DEFAULT_PROFILE = {
    "schema_version": 1,
    "title": "SLAM Run Analysis",
    "diagnostics": {"categories": ["estimator", "matching", "observability", "fusion", "loop", "runtime"]},
    "sections": [
        {"id": "overall", "title": "1. Overall", "groups": ["core"], "required": True, "question": "Is the global trajectory quality acceptable, and where does it start to degrade?", "guidance": "Inspect trajectory, error vs distance, signed components, segment error, and tail distribution first."},
        {"id": "estimator", "title": "2. Estimator / prediction", "groups": ["estimator"], "required": False, "question": "Does prediction state or bias become abnormal before pose error grows?", "guidance": "If yes, prioritize IMU propagation, velocity, bias, timing, and state modeling before frontend tuning."},
        {"id": "matching", "title": "3. Frontend / matching", "groups": ["matching"], "required": False, "question": "Does the measurement update inject the error or lose matching support?", "guidance": "Compare correction, residual, support count, and convergence around the first degraded segment."},
        {"id": "observability", "title": "4. Observability", "groups": ["observability"], "required": False, "question": "Does directional information or conditioning collapse before the corresponding error grows?", "guidance": "Use the same time or distance axis as the error plots whenever possible."},
        {"id": "fusion", "title": "5. External fusion", "groups": ["fusion"], "required": False, "question": "Does GNSS/RTK quality, timing, gating, or acceptance explain the estimator response?", "guidance": "Separate measurement quality from estimator reaction."},
        {"id": "loop", "title": "6. Loop / map", "groups": ["loop"], "required": False, "question": "Do loop closures or map feedback correct drift or introduce inconsistency?", "guidance": "Use loop correction, revisit error, and map consistency only when the system actually contains these mechanisms."},
        {"id": "runtime", "title": "7. Runtime", "groups": ["runtime"], "required": False, "question": "Does the candidate lose real-time margin or increase resource cost?", "guidance": "Check total and stage runtime together with accuracy, not as a separate afterthought."},
    ],
}


def load_yaml(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def discover_profile(run_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidates = [Path.cwd() / "analysis" / "analysis_profile.yaml"]
    for parent in (run_dir, *run_dir.parents):
        candidates.append(parent / "analysis" / "analysis_profile.yaml")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def find_series(run_dir: Path, candidates: list[str]) -> Path | None:
    for relative in candidates:
        path = run_dir / relative
        if path.is_file():
            return path
    return None


def run_tool(script: Path, args: list[str]) -> tuple[bool, str]:
    if not script.is_file():
        return False, f"missing analysis tool: {script}"
    result = subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        return False, detail
    return True, result.stdout.strip()


def selected_categories(profile: dict[str, object]) -> list[str]:
    diagnostics = profile.get("diagnostics")
    if isinstance(diagnostics, dict) and isinstance(diagnostics.get("categories"), list):
        return [str(item) for item in diagnostics["categories"]]
    groups: list[str] = []
    sections = profile.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict) or section.get("enabled") is False:
                continue
            for group in section.get("groups", []) if isinstance(section.get("groups"), list) else []:
                name = str(group)
                if name != "core" and name not in groups:
                    groups.append(name)
    return groups


def generate_plots(run_dir: Path, profile: dict[str, object], baseline_run: Path | None) -> list[str]:
    warnings: list[str] = []
    tools = Path(__file__).resolve().parent
    plots = run_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    plot_manifest = plots / "plot_manifest.json"

    core_cfg = profile.get("core") if isinstance(profile.get("core"), dict) else {}
    candidates = core_cfg.get("csv_candidates") if isinstance(core_cfg, dict) else None
    if not isinstance(candidates, list):
        candidates = ["series/aligned_errors.csv", "series/errors.csv"]
    core_csv = find_series(run_dir, [str(item) for item in candidates])
    if core_csv:
        args = [str(core_csv), "--output-dir", str(plots / "01_core"), "--manifest", str(plot_manifest)]
        if baseline_run:
            baseline_csv = find_series(baseline_run, [str(item) for item in candidates])
            if baseline_csv:
                args += ["--baseline-csv", str(baseline_csv), "--baseline-label", "baseline"]
            else:
                warnings.append("baseline run has no compatible aligned error CSV")
        ok, detail = run_tool(tools / "plot_localization_result.py", args)
        if not ok:
            warnings.append(f"core plotting failed: {detail}")
    else:
        warnings.append("no aligned error CSV found; Core Evidence was not generated")

    diagnostics_cfg = profile.get("diagnostics") if isinstance(profile.get("diagnostics"), dict) else {}
    diagnostics_file = diagnostics_cfg.get("file", "series/diagnostics.csv") if isinstance(diagnostics_cfg, dict) else "series/diagnostics.csv"
    diagnostics_csv = run_dir / str(diagnostics_file)
    if diagnostics_csv.is_file():
        args = [str(diagnostics_csv), "--output-dir", str(plots), "--manifest", str(plot_manifest)]
        for category in selected_categories(profile):
            args += ["--category", category]
        ok, detail = run_tool(tools / "plot_slam_diagnostics.py", args)
        if not ok:
            warnings.append(f"diagnostic plotting failed: {detail}")
    else:
        warnings.append(f"no diagnostics CSV found at {diagnostics_file}")
    return warnings


def csv_headers(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            return set(next(reader))
        except StopIteration:
            return set()


def resolve_observation_contract(profile: dict[str, object], profile_path: Path | None) -> Path | None:
    raw = profile.get("observation_contract")
    if isinstance(raw, str):
        path = Path(raw)
        if not path.is_absolute() and profile_path:
            path = profile_path.parent / path
        path = path.expanduser().resolve()
        return path if path.is_file() else None
    if profile_path:
        candidate = profile_path.parent / "observation_contract.yaml"
        if candidate.is_file():
            return candidate.resolve()
    return None


def signal_coverage(run_dir: Path, contract_path: Path | None) -> list[dict[str, object]]:
    if contract_path is None:
        return []
    contract = load_yaml(contract_path)
    signals = contract.get("signals")
    if not isinstance(signals, dict):
        return []
    header_cache: dict[Path, set[str]] = {}
    rows: list[dict[str, object]] = []
    for signal_id, raw in signals.items():
        if not isinstance(raw, dict):
            continue
        source = raw.get("source")
        available = False
        source_text = ""
        if isinstance(source, dict):
            relative = source.get("file")
            column = source.get("column")
            if isinstance(relative, str) and isinstance(column, str):
                path = run_dir / relative
                source_text = f"{relative}:{column}"
                if path.is_file():
                    if path not in header_cache:
                        header_cache[path] = csv_headers(path)
                    available = column in header_cache[path]
        rows.append(
            {
                "signal_id": str(signal_id),
                "required": bool(raw.get("required", False)),
                "available": available,
                "source": source_text,
                "meaning": str(raw.get("meaning", "")),
                "unit": str(raw.get("unit", "")),
                "frame": str(raw.get("frame", "")),
                "layer": str(raw.get("layer", "")),
            }
        )
    return rows


def load_plot_entries(run_dir: Path) -> list[dict[str, object]]:
    path = run_dir / "plots" / "plot_manifest.json"
    if not path.is_file():
        return []
    data = load_json(path)
    plots = data.get("plots")
    return [item for item in plots if isinstance(item, dict)] if isinstance(plots, list) else []


def metric_rows(metrics: dict[str, object]) -> list[tuple[str, str, str]]:
    raw = metrics.get("metrics")
    if not isinstance(raw, dict):
        return []
    rows: list[tuple[str, str, str]] = []
    for name, value in raw.items():
        if isinstance(value, dict):
            rows.append((str(name), str(value.get("value", "")), str(value.get("unit", ""))))
        else:
            rows.append((str(name), str(value), ""))
    return rows


def render_html(
    run_dir: Path,
    profile: dict[str, object],
    manifest: dict[str, object],
    metrics: dict[str, object],
    plots: list[dict[str, object]],
    signals: list[dict[str, object]],
    warnings: list[str],
    ready: bool,
) -> str:
    title = str(profile.get("title", "Run Analysis"))
    run_id = str(manifest.get("run_id", run_dir.name))
    status = "READY FOR HUMAN REVIEW" if ready else "EVIDENCE INCOMPLETE"
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)} - {html.escape(run_id)}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:1280px;margin:32px auto;padding:0 20px;line-height:1.45}h1,h2{margin-top:1.4em}.status{padding:12px;border:1px solid #999;border-radius:8px;font-weight:700}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px}.card{border:1px solid #ddd;border-radius:10px;padding:12px}.card img{width:100%;height:auto}.muted{color:#666}.missing{border-left:4px solid #999;padding-left:12px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:7px;text-align:left}code{background:#f4f4f4;padding:2px 4px}</style></head><body>",
        f"<h1>{html.escape(title)}</h1><p><code>{html.escape(run_id)}</code></p>",
        f"<div class='status'>{html.escape(status)}</div>",
    ]
    git = manifest.get("git")
    if isinstance(git, dict):
        parts.append(f"<p class='muted'>commit: {html.escape(str(git.get('commit', '')))} | branch: {html.escape(str(git.get('branch', '')))}</p>")

    parts.append("<h2>Metrics</h2><table><tr><th>Metric</th><th>Value</th><th>Unit</th></tr>")
    for name, value, unit in metric_rows(metrics):
        parts.append(f"<tr><td>{html.escape(name)}</td><td>{html.escape(value)}</td><td>{html.escape(unit)}</td></tr>")
    parts.append("</table>")

    if warnings:
        parts.append("<h2>Coverage warnings</h2><ul>")
        for warning in warnings:
            parts.append(f"<li>{html.escape(warning)}</li>")
        parts.append("</ul>")

    if signals:
        parts.append("<h2>Observation contract coverage</h2><table><tr><th>Signal</th><th>Layer</th><th>Required</th><th>Available</th><th>Source</th><th>Meaning</th></tr>")
        for signal in signals:
            parts.append(
                "<tr>"
                f"<td>{html.escape(str(signal['signal_id']))}</td>"
                f"<td>{html.escape(str(signal['layer']))}</td>"
                f"<td>{'yes' if signal['required'] else 'no'}</td>"
                f"<td>{'yes' if signal['available'] else 'no'}</td>"
                f"<td>{html.escape(str(signal['source']))}</td>"
                f"<td>{html.escape(str(signal['meaning']))}</td>"
                "</tr>"
            )
        parts.append("</table>")

    sections = profile.get("sections")
    if not isinstance(sections, list):
        sections = DEFAULT_PROFILE["sections"]
    for section in sections:
        if not isinstance(section, dict) or section.get("enabled") is False:
            continue
        groups = {str(item) for item in section.get("groups", [])} if isinstance(section.get("groups"), list) else set()
        selected = [item for item in plots if str(item.get("group", "")) in groups]
        parts.append(f"<h2>{html.escape(str(section.get('title', section.get('id', 'Section'))))}</h2>")
        parts.append(f"<p><strong>Question:</strong> {html.escape(str(section.get('question', '')))}</p>")
        guidance = str(section.get("guidance", ""))
        if guidance:
            parts.append(f"<p class='muted'>{html.escape(guidance)}</p>")
        if not selected:
            parts.append("<p class='missing'>No evidence plot is available for this section.</p>")
            continue
        parts.append("<div class='grid'>")
        for item in selected:
            file_name = str(item.get("file", ""))
            question = str(item.get("question", ""))
            src = "../plots/" + file_name
            parts.append("<figure class='card'>")
            parts.append(f"<img src='{html.escape(src)}' alt='{html.escape(question)}'>")
            parts.append(f"<figcaption><strong>{html.escape(question)}</strong><br><span class='muted'>{html.escape(file_name)}</span></figcaption>")
            parts.append("</figure>")
        parts.append("</div>")

    parts.append("<h2>Decision</h2><p>Use the reading order above to identify the earliest abnormal layer, then record the engineering decision in <code>../report.md</code>. The static report is designed to remain usable without an AI assistant.</p>")
    parts.append("</body></html>")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--profile")
    parser.add_argument("--baseline-run")
    parser.add_argument("--no-generate-plots", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail if required observation signals or required analysis sections are missing")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"missing run directory: {run_dir}")
    profile_path = discover_profile(run_dir, args.profile)
    profile = load_yaml(profile_path) if profile_path else dict(DEFAULT_PROFILE)
    baseline_run = Path(args.baseline_run).expanduser().resolve() if args.baseline_run else None

    warnings: list[str] = []
    if not args.no_generate_plots:
        warnings.extend(generate_plots(run_dir, profile, baseline_run))

    manifest_path = run_dir / "manifest.yaml"
    metrics_path = run_dir / "metrics.json"
    manifest = load_yaml(manifest_path) if manifest_path.is_file() else {"run_id": run_dir.name}
    metrics = load_json(metrics_path) if metrics_path.is_file() else {"metrics": {}}
    plots = load_plot_entries(run_dir)
    contract_path = resolve_observation_contract(profile, profile_path)
    signals = signal_coverage(run_dir, contract_path)

    missing_required_signals = [str(item["signal_id"]) for item in signals if item["required"] and not item["available"]]
    missing_required_sections: list[str] = []
    sections = profile.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict) or section.get("enabled") is False or not bool(section.get("required", False)):
                continue
            groups = {str(item) for item in section.get("groups", [])} if isinstance(section.get("groups"), list) else set()
            if not any(str(plot.get("group", "")) in groups for plot in plots):
                missing_required_sections.append(str(section.get("id", "section")))
    ready = not missing_required_signals and not missing_required_sections

    report_dir = run_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": 1,
        "run_id": manifest.get("run_id", run_dir.name),
        "profile": str(profile_path) if profile_path else "builtin-default",
        "observation_contract": str(contract_path) if contract_path else None,
        "ready_for_human_review": ready,
        "missing_required_signals": missing_required_signals,
        "missing_required_sections": missing_required_sections,
        "plot_count": len(plots),
        "warnings": warnings,
    }
    (report_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (report_dir / "index.html").write_text(render_html(run_dir, profile, manifest, metrics, plots, signals, warnings, ready), encoding="utf-8")
    print(json.dumps({**summary, "index_html": str((report_dir / 'index.html').resolve())}, indent=2, ensure_ascii=False))
    return 0 if ready or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
