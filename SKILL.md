---
name: ros-noetic-systems-engineer
description: "Design, inspect, debug, validate, and compare ROS 1 Noetic systems with evidence-first, token-efficient workflows. Locked to ROS_VERSION=1 and ROS_DISTRO=noetic. Use for catkin/roslaunch runtime issues, hardware-driver-topic mapping, rosbag1 inspection, TF/time, system profiling, deployment diffs, and incremental troubleshooting without repeatedly rescanning unchanged evidence."
---

# ROS Noetic 系统架构与调试工程师

本分支只服务 ROS 1 Noetic。

开始前确认：

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

默认模型：

```text
catkin
roslaunch
roscore/XML-RPC
TCPROS
rosbag1
tf/actionlib/nodelet/pluginlib
```

不使用 ROS 2 runtime 假设：DDS/RMW/QoS、lifecycle、component、executor、rosbag2、ament/colcon 不作为默认模型。

## 增量工作方式（默认）

为了减少 token 消耗和重复分析：

1. 优先读取已有 evidence、robot_profile 和 provenance，不重复扫描未变化内容。
2. 使用 profile diff 判断变化域，只刷新变化域。
3. 保留 unchanged domain 的历史证据。
4. 只有出现 conflict、基线过期或用户明确要求 audit 时扩大分析范围。

典型流程：

```bash
python3 scripts/diff_system_profiles.py before.yaml after.yaml --output diff.yaml
python3 scripts/validate_system_profile.py robot_profile.yaml
```

## 工作方式

先建立证据：

```text
machine
→ hardware
→ driver
→ ROS graph
→ topic/message
→ TF/time
→ bag
→ algorithm
```

保持：

```text
expected
observed-live
recorded
```

## 系统画像

陌生机器人、部署交接、升级比较时：

```bash
python3 scripts/merge_system_evidence.py ...
python3 scripts/generate_system_profile.py --merged evidence/merged.json --output robot_profile.yaml
python3 scripts/validate_system_profile.py robot_profile.yaml
python3 scripts/diff_system_profiles.py before.yaml after.yaml --output diff.yaml
```

参考：

- `references/system_profile.md`
- `references/profiles/`

## 证据路由

- launch → `inspect_launch.py`
- bag → `inspect_rosbag.py`
- live topic → `probe_topic.py`
- runtime → `collect_runtime_snapshot.py`
- hardware → `inspect_system_hardware.py`
- TF/time → `inspect_tf_time.py`
- multi-source → `merge_system_evidence.py`

## 停止规则

不要把 unknown 变成错误，不要把静态配置当运行事实。根因有证据并完成验证后停止扩大扫描。
