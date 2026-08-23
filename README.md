# ROS Noetic Systems Engineer

> **Branch:** `ros1-noetic`  
> **Skill:** `ros-noetic-systems-engineer`

This branch is the ROS 1 Noetic-specific edition of the project. It is intentionally scoped to **ROS_VERSION=1** and **ROS_DISTRO=noetic** so debugging, system inspection, hardware adaptation, rosbag analysis, TF/time reasoning, and project memory all use ROS 1 semantics instead of mixing ROS 1 and ROS 2 assumptions.

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

Supported areas include:

- USB and serial devices;
- Ethernet sensors;
- CAN devices;
- LiDAR;
- IMU;
- GNSS/RTK;
- cameras;
- time synchronization.

Reference:

```text
references/hardware_adaptation.md
```

### rosbag1 Analysis

The default workflow is:

```text
inventory first
→ bounded sampling
→ replay only when required
```

Example:

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

Generate:

```bash
python3 scripts/generate_system_profile.py \
  --merged evidence/merged.json \
  --output robot_profile.yaml
```

Validate:

```bash
python3 scripts/validate_system_profile.py robot_profile.yaml
```

Compare deployments:

```bash
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

Versioned profiles:

```bash
python3 scripts/profile_manager.py save \
  --profile robot_profile.yaml \
  --summary session_summary.yaml

python3 scripts/profile_manager.py list
```

Session memory stores only compact verified information:

- known hardware and drivers;
- verified TF/time/calibration information;
- stable assumptions;
- unresolved unknowns;
- last profile version.

Reference:

```text
references/session_memory.md
```

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

## Safety Model

The Skill defaults to read-only analysis.

Operations requiring explicit consideration:

- publishing topics;
- changing parameters;
- calling state-changing services/actions;
- loading/unloading nodelets;
- switching controllers;
- replaying bags into live systems;
- interacting with physical actuators.

## Repository Structure

```text
SKILL.md
agents/openai.yaml
scripts/
references/
references/profiles/
tests/
.github/workflows/
```

`SKILL.md` remains the control plane. Detailed knowledge is stored in references and loaded only when required to reduce context usage.

## Validation

Local validation:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/package_skill.py . dist
```

The packaged Skill should contain reusable resources, not project-specific caches, logs or temporary experiment data.

## Scope

This README describes only the `ros1-noetic` branch.

This branch is not a generic ROS compatibility layer and does not silently fall back to ROS 2 behavior when the environment does not match Noetic.
