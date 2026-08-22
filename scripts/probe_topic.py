#!/usr/bin/env python3
"""Run a bounded, read-only diagnostic probe for one live ROS 1 Noetic topic."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any

import yaml

MAX_OUTPUT = 100_000


def execute(command: list[str], timeout: float, timeout_is_window: bool = False) -> dict[str, Any]:
    buffers = {"stdout": bytearray(), "stderr": bytearray()}; truncated = {"stdout": False, "stderr": False}
    def drain(stream: Any, name: str) -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk: break
                room = MAX_OUTPUT - len(buffers[name])
                if room > 0: buffers[name].extend(chunk[:room])
                if len(chunk) > room: truncated[name] = True
        finally: stream.close()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return {"command": command, "returncode": None, "stdout": "", "stderr": f"command not found: {command[0]}", "timed_out": False, "window_complete": False, "truncated": False}
    assert process.stdout is not None and process.stderr is not None
    threads = [threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True), threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True)]
    for t in threads: t.start()
    timed_out = False
    try: returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True; process.kill(); returncode = process.wait()
    for t in threads: t.join(timeout=1.0)
    return {"command": command, "returncode": returncode, "stdout": buffers["stdout"].decode("utf-8", errors="replace"), "stderr": buffers["stderr"].decode("utf-8", errors="replace"), "timed_out": timed_out, "window_complete": timed_out and timeout_is_window, "truncated": truncated["stdout"] or truncated["stderr"]}


def build_probe_commands(topic: str, window: int, include_sample: bool, include_rates: bool) -> list[tuple[str, list[str], bool]]:
    probes: list[tuple[str, list[str], bool]] = [("info", ["rostopic", "info", topic], False), ("type", ["rostopic", "type", topic], False)]
    if include_sample: probes.append(("sample", ["rostopic", "echo", "-n", "1", "--noarr", topic], False))
    if include_rates:
        probes.extend([("hz", ["rostopic", "hz", "-w", str(window), topic], True), ("bw", ["rostopic", "bw", "-w", str(window), topic], True), ("delay", ["rostopic", "delay", "-w", str(window), topic], True)])
    return probes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("topic"); p.add_argument("--window", type=int, default=10); p.add_argument("--command-timeout", type=float, default=4.0); p.add_argument("--measurement-seconds", type=float, default=6.0); p.add_argument("--no-sample", action="store_true"); p.add_argument("--no-rates", action="store_true"); p.add_argument("--allow-non-noetic", action="store_true"); p.add_argument("--format", choices=["json", "yaml"], default="json"); p.add_argument("--output", type=Path)
    a = p.parse_args()
    if not a.topic.startswith("/"): raise SystemExit("topic must be an absolute ROS name beginning with /")
    if not 1 <= a.window <= 1000: raise SystemExit("--window must be between 1 and 1000")
    env_version = os.environ.get("ROS_VERSION"); env_distro = os.environ.get("ROS_DISTRO")
    distro_probe = execute(["rosversion", "-d"], a.command_timeout)
    observed_distro = distro_probe["stdout"].strip() if distro_probe["returncode"] == 0 else None
    is_noetic = env_version == "1" and env_distro == "noetic" and observed_distro == "noetic"
    if not is_noetic and not a.allow_non_noetic:
        payload = {"schema_version": 1, "status": "environment_mismatch", "expected": {"ROS_VERSION": "1", "ROS_DISTRO": "noetic", "rosversion_d": "noetic"}, "observed": {"ROS_VERSION": env_version, "ROS_DISTRO": env_distro, "rosversion_d": observed_distro}, "probe": distro_probe}
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if a.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
        if a.output: a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(text, encoding="utf-8")
        else: print(text)
        return 2
    results = {}
    for name, command, is_window in build_probe_commands(a.topic, a.window, not a.no_sample, not a.no_rates):
        results[name] = execute(command, a.measurement_seconds if is_window else a.command_timeout, timeout_is_window=is_window)
    payload = {"schema_version": 1, "status": "measured", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "target": {"ros_version": "1", "ros_distro": "noetic"}, "environment_match": is_noetic, "topic": a.topic, "results": results, "interpretation_rules": ["info/type establish graph and schema facts, not data quality.", "hz/bw/delay are bounded observations and must not be generalized to the whole run.", "delay requires a valid Header timestamp and compatible clock basis.", "--noarr prevents large arrays from flooding sample output.", "A timeout in hz/bw/delay is expected when the bounded measurement window completes; inspect partial stdout."]}
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if a.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
    if a.output: a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(text, encoding="utf-8")
    else: print(text)
    return 0


if __name__ == "__main__": raise SystemExit(main())
