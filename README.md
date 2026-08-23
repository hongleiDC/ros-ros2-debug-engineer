# ROS Noetic Systems Engineer

> **Branch:** `ros1-noetic`  
> **Skill:** `ros-noetic-systems-engineer`

This branch is the ROS 1 Noetic-specific edition of the project. It is intentionally scoped to **ROS_VERSION=1** and **ROS_DISTRO=noetic** so debugging, system inspection, hardware adaptation, rosbag analysis, TF/time reasoning, project memory, and result auditing all use ROS 1 semantics instead of mixing ROS 1 and ROS 2 assumptions.

## Purpose

Use this branch for ROS 1 Noetic robots and codebases that require system-level understanding rather than isolated command suggestions.

The Skill follows an evidence-first workflow:

```text
machine / OS
→ catkin workspace and overlay
→ hardware endpoint
→ driver / node
→ topic / message
→ TF / frame
→ time source
→ rosbag1 / recorded data
→ algorithm
```

Evidence is always separated into:

```text
expected      = launch and static configuration
observed-live = current ROS runtime and hardware
recorded      = rosbag1 and historical runs
```

`unknown` is preserved as unknown. Static configuration is not treated as runtime proof.

## Noetic Runtime Contract

Before applying this branch's assumptions:

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

Expected:

```text
ROS_VERSION=1
ROS_DISTRO=noetic
noetic
```

The branch uses the ROS 1 Noetic model:

- catkin / catkin_make / catkin_tools
- roslaunch XML
- roscore / ROS master / XML-RPC
- TCPROS / UDPROS
- rostopic / rosnode / rosservice / rosparam
- tf / tf2_ros
- rosbag1
- actionlib
- nodelet / pluginlib
- dynamic_reconfigure
- rospy / roscpp

It does not use ROS 2 assumptions such as DDS/RMW/QoS, lifecycle nodes, component containers, executors, rosbag2, ament or colcon as default runtime models.

> ROS Noetic reached upstream EOL in May 2025. Production deployment should explicitly consider dependency and security maintenance.

## Core Capabilities

### System Inspection

The Skill can analyze:

- catkin workspaces and overlays;
- roslaunch XML and parameters;
- ROS graph state;
- topic/service/action interfaces;
- TF and time behavior;
- hardware-to-driver-to-topic chains.

Main helpers:

```text
scripts/inspect_workspace.py
scripts/inspect_launch.py
scripts/collect_runtime_snapshot.py
scripts/probe_topic.py
```

### Hardware Adaptation

Hardware is analyzed through the complete chain:

```text
hardware
→ Linux device/interface
→ driver/node
→ ROS topic
→ message
→ frame
→ time
```

Supported areas include USB/serial, Ethernet, CAN, LiDAR, IMU, GNSS/RTK, cameras and time synchronization.

Reference: `references/hardware_adaptation.md`.

### rosbag1 Analysis

The default workflow is:

```text
inventory first
→ bounded sampling
→ replay only when required
```

```bash
python3 scripts/inspect_rosbag.py run.bag --metadata-only
python3 scripts/inspect_rosbag.py run.bag --topic /imu/data --topic /points_raw
```

The Skill checks topic contracts, message types, timestamps, frames, PointCloud2 fields, TF/time information and recorded-vs-live differences.

### Evidence Fusion

Multiple evidence sources can be merged:

```bash
python3 scripts/merge_system_evidence.py \
  --launch evidence/launch.json \
  --runtime evidence/runtime.json \
  --hardware evidence/hardware.json \
  --tf-time evidence/tf_time.json \
  --bag evidence/bag.json \
  --output evidence/merged.json
```

The merge process preserves conflicts and missing evidence. It does not automatically claim a root cause.

## System Profile

The branch supports persistent robot understanding through `robot_profile.yaml`.

```bash
python3 scripts/generate_system_profile.py \
  --merged evidence/merged.json \
  --output robot_profile.yaml

python3 scripts/validate_system_profile.py robot_profile.yaml
python3 scripts/diff_system_profiles.py before.yaml after.yaml --output diff.yaml
```

Profile templates:

```text
references/profiles/
├── autonomous_vehicle.yaml
├── drone.yaml
├── lidar_imu_rtk.yaml
├── manipulator.yaml
└── mobile_robot.yaml
```

## Incremental Workflow (Low Token Usage)

For long-running projects, the default strategy is incremental updates:

```text
existing baseline
→ detect changed evidence
→ refresh changed domains only
→ update profile
→ validate
→ save new baseline
```

Cache:

```text
.ros_noetic_cache/
├── manifest.yaml
├── latest_profile.yaml
└── session_summary.yaml
```

The cache improves efficiency but is not the source of truth. Large bag files are never copied into the cache.

## Profile History and Session Memory

```bash
python3 scripts/profile_manager.py save \
  --profile robot_profile.yaml \
  --summary session_summary.yaml

python3 scripts/profile_manager.py list
```

Session memory stores only compact verified information: known hardware/drivers, verified TF/time/calibration information, stable assumptions, unresolved unknowns and the last profile version.

Reference: `references/session_memory.md`.

## Human-Auditable Logs, Results, and Visualization

This branch is designed so a user can still review and regenerate results when the Agent is unavailable.

Install project-local analysis tools once:

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

The generated project tooling includes:

```text
tools/analysis/
├── result_bundle.py
├── ros_noetic_run_logger.py
├── analyze_run.py
├── plot_localization_result.py
├── plot_slam_diagnostics.py
├── plot_series.py
└── compare_result_metrics.py
```

A run should keep separate, reviewable artifacts:

```text
RUN-xxxx/
├── manifest.yaml
├── metrics.json
├── bags/       rosbag1 high-rate ROS data
├── series/     normalized numeric series
├── logs/       native ROS/roslaunch/node evidence
├── plots/      deterministic offline figures
└── report/     static human review report
```

Create a Result Bundle and capture native ROS Noetic evidence:

```bash
python3 tools/analysis/result_bundle.py init reports EXP-0001 --run-id RUN-001 --workspace .
python3 tools/analysis/ros_noetic_run_logger.py snapshot RUN_DIR --roswtf
python3 tools/analysis/ros_noetic_run_logger.py record RUN_DIR --topic /result/topic
python3 tools/analysis/ros_noetic_run_logger.py copy-logs RUN_DIR
```

The logger records evidence paths back into `RUN_DIR/manifest.yaml`. Default bag audit topics include `/rosout`, `/rosout_agg`, `/diagnostics`, `/tf`, `/tf_static` and `/clock`; add project-specific result/input topics explicitly.

For arbitrary numeric CSV data, users can regenerate a plot without ChatGPT:

```bash
python3 tools/analysis/plot_series.py RUN_DIR/series/diagnostics.csv \
  --x distance_m --y frame_runtime_ms \
  --output RUN_DIR/plots/runtime.png \
  --title "Runtime vs distance" --ylabel ms
```

If a project needs a custom logger or visualization adapter, the Skill should write it into the project's `tools/analysis/` directory with explicit CLI inputs/outputs, signal mapping, units, frame/time semantics, and deterministic saved results. The only working analysis code should never exist only inside an AI conversation.

Generate the static report and validate the run:

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
python3 tools/analysis/result_bundle.py validate RUN_DIR --closure --human-analysis
```

Add `--ros-audit` when native ROS runtime evidence is part of the acceptance requirement. The static report is intended to be opened without a database, service or AI session.

See `references/human_auditable_results.md` and `references/analysis_contract.md`.

## Recommended Usage Flow

New robot:

```text
1. Confirm ROS Noetic environment
2. Inspect workspace, launch, hardware, runtime, TF/time and bag
3. Merge evidence
4. Generate and validate system profile
5. Save baseline memory
```

Existing robot:

```text
1. Read previous profile and session memory
2. Check evidence changes
3. Refresh only affected domains
4. Compare profiles if needed
5. Save updated baseline
```

Experiment/result review:

```text
1. Create one RUN bundle
2. Capture native ROS logs/bag/snapshot
3. Save normalized series and metrics
4. Run deterministic plotting code
5. Generate static HTML report
6. Let the user independently review the evidence and decision
```

## Safety Model

The Skill defaults to read-only analysis.

Operations requiring explicit consideration include publishing topics, changing parameters, calling state-changing services/actions, loading/unloading nodelets, switching controllers, replaying bags into live systems and interacting with physical actuators.

## Repository Structure

```text
SKILL.md
agents/openai.yaml
scripts/
references/
references/profiles/
tests/
.github/workflows/
.gitignore
```

`SKILL.md` remains the control plane. Detailed knowledge is stored in references and loaded only when required to reduce context usage.

## Validation and Packaging

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/package_skill.py . dist
```

The package command always produces `dist/skill.zip`. Repository-only files and local runtime state are excluded from the distributable Skill, including CI/tests, `.ros_noetic_cache/`, `.ros_noetic_profiles/`, `reports/` and `logs/`. The same runtime paths are ignored by Git so local experiments do not accidentally become Skill content.

## Scope

This README describes only the `ros1-noetic` branch. This branch is not a generic ROS compatibility layer and does not silently fall back to ROS 2 behavior when the environment does not match Noetic.
