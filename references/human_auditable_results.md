# Human Auditable ROS Noetic Results

## Goal

The final result must remain usable when the AI agent is unavailable. A ROS engineer should be able to reproduce the evidence, regenerate plots, inspect logs, and judge conclusions from saved artifacts.

## Result structure

Recommended RUN directory:

```text
RUN-xxxx/
├── manifest.yaml
├── metrics.json
├── series/
├── plots/
├── logs/
├── bags/
└── report/
    ├── index.html
    └── analysis_summary.json
```

## Native ROS evidence

Use ROS Noetic native tools as the source of runtime truth:

```text
rosnode
rostopic
rosservice
rosparam
roswtf
rosbag1
roslaunch logs
```

Capture:

- ROS environment;
- node graph;
- topic/service contracts;
- parameters;
- `/tf`, `/tf_static`, `/clock`;
- diagnostics;
- roslaunch/node logs.

## Logging rules

Do not use text logs as a replacement for numeric data.

Use:

```text
rosbag1       high-rate ROS data
series/*.csv  normalized analysis signals
metrics.json  scalar decisions
logs/         execution evidence
plots/        human-readable figures
```

For algorithm diagnostics, publish meaningful ROS topics during execution when possible, then record them with rosbag1.

## Visualization rules

Every figure must answer a question.

Good examples:

- Did trajectory error increase?
- Did IMU propagation fail before correction?
- Did scan matching correction become unstable?
- Did runtime exceed the processing budget?

Avoid plots without interpretation or plots that only prove a script executed.

## Agent-independent workflow

```text
ROS run
 ↓
rosbag1 + logs + metrics
 ↓
offline scripts
 ↓
plots + static HTML report
 ↓
human review
```

The report must not require a database, web service, or AI session.

## Reproducibility

Save:

- git commit and dirty state;
- launch/YAML configuration;
- bag hash;
- calibration version;
- ROS environment;
- commands used;
- metric definitions;
- plot generation scripts.

A result without provenance is an observation, not an engineering baseline.
