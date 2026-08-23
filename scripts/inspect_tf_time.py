#!/usr/bin/env python3
"""Collect bounded, read-only TF and time evidence for ROS 1 Noetic."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any

import yaml

MAX_OUTPUT = 100_000
ENV_KEYS = ("ROS_VERSION", "ROS_DISTRO", "ROS_MASTER_URI", "ROS_IP", "ROS_HOSTNAME")


def execute(command: list[str], timeout: float, timeout_is_window: bool = False) -> dict[str, Any]:
    if shutil.which(command[0]) is None:
        return {"command": command, "returncode": None, "stdout": "", "stderr": "command not found", "timed_out": False, "window_complete": False, "truncated": False}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return {"command": command, "returncode": None, "stdout": "", "stderr": str(exc), "timed_out": False, "window_complete": False, "truncated": False}
    assert process.stdout is not None and process.stderr is not None

    def drain(stream: Any, name: str) -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                room = MAX_OUTPUT - len(buffers[name])
                if room > 0:
                    buffers[name].extend(chunk[:room])
                if len(chunk) > room:
                    truncated[name] = True
        finally:
            stream.close()

    threads = [
        threading.Thread(target=drain, args=(process.stdout, "stdout"), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, "stderr"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
    for thread in threads:
        thread.join(timeout=1.0)
    return {
        "command": command,
        "returncode": returncode,
        "stdout": buffers["stdout"].decode("utf-8", errors="replace"),
        "stderr": buffers["stderr"].decode("utf-8", errors="replace"),
        "timed_out": timed_out,
        "window_complete": timed_out and timeout_is_window,
        "truncated": truncated["stdout"] or truncated["stderr"],
    }


def parse_bool(text: str) -> bool | None:
    value = text.strip().lower()
    if value in {"true", "1", "yes", "on"}:
        return True
    if value in {"false", "0", "no", "off"}:
        return False
    return None


def listed_topics(result: dict[str, Any]) -> list[str]:
    if result.get("returncode") != 0:
        return []
    return [line.strip() for line in result.get("stdout", "").splitlines() if line.strip().startswith("/")]


def summarize_time_semantics(use_sim_time: bool | None, topics: list[str], ntp_synced: bool | None) -> dict[str, Any]:
    has_clock = "/clock" in topics
    has_tf = "/tf" in topics
    has_tf_static = "/tf_static" in topics
    mode = "sim" if use_sim_time is True else "wall" if use_sim_time is False else "unknown"
    warnings: list[str] = []
    if use_sim_time is True and not has_clock:
        warnings.append("/use_sim_time is true but /clock is not visible; ROS time may be stalled.")
    if use_sim_time is False and has_clock:
        warnings.append("/clock is visible while /use_sim_time is false; nodes still use wall time unless configured otherwise.")
    if not has_tf and not has_tf_static:
        warnings.append("Neither /tf nor /tf_static is visible in the current topic inventory.")
    if ntp_synced is False:
        warnings.append("Host time synchronization reports not synchronized; cross-machine header delay and TF timing require caution.")
    return {
        "ros_time_mode": mode,
        "use_sim_time": use_sim_time,
        "clock_topic_present": has_clock,
        "tf_topic_present": has_tf,
        "tf_static_topic_present": has_tf_static,
        "host_ntp_synchronized": ntp_synced,
        "warnings": warnings,
    }


def parse_ntp_synced(result: dict[str, Any]) -> bool | None:
    if result.get("returncode") != 0:
        return None
    for line in result.get("stdout", "").splitlines():
        if line.startswith("NTPSynchronized="):
            return parse_bool(line.split("=", 1)[1])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", help="Optional parent frame for a bounded tf_echo sample.")
    parser.add_argument("--child", help="Optional child frame for a bounded tf_echo sample.")
    parser.add_argument("--topic", action="append", default=[], help="Header-bearing topic to inspect for delay/stamp evidence; repeat as needed.")
    parser.add_argument("--measurement-seconds", type=float, default=5.0)
    parser.add_argument("--command-timeout", type=float, default=4.0)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--allow-non-noetic", action="store_true")
    parser.add_argument("--format", choices=["json", "yaml"], default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if (args.parent is None) != (args.child is None):
        raise SystemExit("--parent and --child must be supplied together")
    if args.measurement_seconds <= 0 or args.command_timeout <= 0:
        raise SystemExit("timeouts must be positive")
    if not 1 <= args.window <= 1000:
        raise SystemExit("--window must be between 1 and 1000")
    for topic in args.topic:
        if not topic.startswith("/"):
            raise SystemExit(f"topic must be an absolute ROS name: {topic}")

    distro_probe = execute(["rosversion", "-d"], args.command_timeout)
    observed_distro = distro_probe["stdout"].strip() if distro_probe.get("returncode") == 0 else None
    is_noetic = os.environ.get("ROS_VERSION") == "1" and os.environ.get("ROS_DISTRO") == "noetic" and observed_distro == "noetic"
    if not is_noetic and not args.allow_non_noetic:
        payload = {
            "schema_version": 1,
            "status": "environment_mismatch",
            "expected": {"ROS_VERSION": "1", "ROS_DISTRO": "noetic", "rosversion_d": "noetic"},
            "observed": {"ROS_VERSION": os.environ.get("ROS_VERSION"), "ROS_DISTRO": os.environ.get("ROS_DISTRO"), "rosversion_d": observed_distro},
            "probe": distro_probe,
        }
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text)
        return 2

    topic_list = execute(["rostopic", "list"], args.command_timeout)
    topics = listed_topics(topic_list)
    sim_param = execute(["rosparam", "get", "/use_sim_time"], args.command_timeout)
    use_sim_time = parse_bool(sim_param["stdout"]) if sim_param.get("returncode") == 0 else None
    timedatectl = execute(["timedatectl", "show", "-p", "NTPSynchronized", "-p", "NTP", "-p", "Timezone"], args.command_timeout)
    ntp_synced = parse_ntp_synced(timedatectl)

    ros_topic_checks: dict[str, Any] = {"inventory": topic_list, "use_sim_time": sim_param}
    for name in ("/tf", "/tf_static", "/clock"):
        if name in topics:
            ros_topic_checks[f"info:{name}"] = execute(["rostopic", "info", name], args.command_timeout)
    if "/clock" in topics:
        ros_topic_checks["sample:/clock"] = execute(["rostopic", "echo", "-n", "1", "/clock"], args.command_timeout)
        ros_topic_checks["hz:/clock"] = execute(["rostopic", "hz", "-w", str(args.window), "/clock"], args.measurement_seconds, timeout_is_window=True)
    if "/tf" in topics:
        ros_topic_checks["hz:/tf"] = execute(["rostopic", "hz", "-w", str(args.window), "/tf"], args.measurement_seconds, timeout_is_window=True)

    tf_monitor = execute(["rosrun", "tf", "tf_monitor"], args.measurement_seconds, timeout_is_window=True)
    frame_pair = None
    if args.parent and args.child:
        frame_pair = execute(["rosrun", "tf", "tf_echo", args.parent, args.child], args.measurement_seconds, timeout_is_window=True)

    sensor_topics: dict[str, Any] = {}
    for topic in args.topic:
        sensor_topics[topic] = {
            "sample": execute(["rostopic", "echo", "-n", "1", "--noarr", topic], args.command_timeout),
            "delay": execute(["rostopic", "delay", "-w", str(args.window), topic], args.measurement_seconds, timeout_is_window=True),
        }

    system_time = {
        "timedatectl": timedatectl,
        "chrony_tracking": execute(["chronyc", "tracking"], args.command_timeout),
        "chrony_sources": execute(["chronyc", "sources", "-n"], args.command_timeout),
        "ntpq": execute(["ntpq", "-pn"], args.command_timeout),
    }
    semantics = summarize_time_semantics(use_sim_time, topics, ntp_synced)
    payload = {
        "schema_version": 1,
        "evidence_kind": "tf_time",
        "status": "measured",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": {"ros_version": "1", "ros_distro": "noetic"},
        "environment_match": is_noetic,
        "environment": {key: os.environ.get(key) for key in ENV_KEYS if os.environ.get(key) is not None},
        "summary": semantics,
        "ros": ros_topic_checks,
        "tf_monitor": tf_monitor,
        "frame_pair": {"parent": args.parent, "child": args.child, "probe": frame_pair} if frame_pair else None,
        "sensor_topics": sensor_topics,
        "system_time": system_time,
        "interpretation_rules": [
            "TF existence, freshness, authority and transform value are separate claims.",
            "A bounded tf_monitor/tf_echo window is not a long-duration stability guarantee.",
            "rostopic delay requires a valid Header stamp and a compatible clock basis.",
            "NTP/chrony status describes host time; sensor PPS/PTP/device clocks require their own evidence.",
            "When /use_sim_time is true, /clock availability and reset/loop behavior become part of the runtime contract.",
        ],
    }
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False) if args.format == "yaml" else json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
