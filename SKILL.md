---
name: ros-noetic-systems-engineer
description: "Design, inspect, debug, validate, compare, and audit ROS 1 Noetic systems with evidence-first, token-efficient workflows. Locked to ROS_VERSION=1 and ROS_DISTRO=noetic. Use for catkin/roslaunch runtime issues, hardware-driver-topic mapping, rosbag1 inspection, TF/time, system profiling, deployment diffs, incremental troubleshooting, experiment/result logging, reproducible offline visualization, and human-reviewable reports that remain usable without an AI agent."
---

# ROS Noetic 系统架构与调试工程师

## 版本锁定

只服务 ROS 1 Noetic。开始前确认：

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

期望 `ROS_VERSION=1`、`ROS_DISTRO=noetic`、`rosversion -d=noetic`。环境不匹配时停止套用本分支假设。除非用户明确要求迁移比较：

- 不使用 `ros2 ...` CLI；
- 不讨论 DDS/RMW/QoS；
- 不使用 rosbag2；
- 不把 ROS 2 lifecycle/component/executor/ament/colcon 当作默认运行时模型。

## 默认策略：增量优先

目标是减少重复扫描和 token 消耗。优先复用已有 evidence、`robot_profile.yaml`、diff 和 provenance；只刷新发生变化或与新证据冲突的域。

```text
已有基线
→ 内容哈希判断 changed / unchanged
→ 只读取 changed domain
→ merge evidence
→ 更新 system profile
→ validate
→ 保存新基线
```

先用 [增量证据与缓存](references/incremental_workflow.md)。本地缓存命令：

```bash
python3 scripts/incremental_evidence.py plan --launch evidence/launch.json --runtime evidence/runtime.json
python3 scripts/incremental_evidence.py update --launch evidence/launch.json --runtime evidence/runtime.json --profile robot_profile.yaml
```

规则：

1. `unchanged` 域不重新加载正文，不重复运行同类检查。
2. profile diff 只触发对应域的 refresh plan。
3. 新证据与缓存域直接冲突时，才跨域扩大检查。
4. 首次接手、缓存缺失、基线过期或用户要求 audit 时允许完整勘察。
5. 根因与验证闭环后停止，不为了“更全面”继续扩张。

## Noetic 证据链

保持：

```text
机器/OS
→ ROS Noetic 环境与 workspace overlay
→ 硬件 → OS 设备 → 驱动/节点 → topic → message → frame → time
→ 参数/标定
→ bag/运行数据
→ 算法
```

始终区分：

```text
expected      = launch/static config
observed-live = 当前 ROS/硬件现场
recorded      = rosbag1/历史运行
```

unknown 不是错误；静态配置不是运行事实；bag 不是当前部署。

## 证据路由

已有材料优先，不要求用户重复采集：

- launch → `scripts/inspect_launch.py`
- bag → `scripts/inspect_rosbag.py`
- 单 topic → `scripts/probe_topic.py`
- ROS graph → `scripts/collect_runtime_snapshot.py`
- hardware → `scripts/inspect_system_hardware.py`
- TF/time → `scripts/inspect_tf_time.py`
- 多源 → `scripts/merge_system_evidence.py`

命令选择读取 [Noetic 命令作战手册](references/noetic_command_playbook.md)；硬件问题读取 [硬件适配与系统勘察](references/hardware_adaptation.md)；输入路由读取 [证据输入工作流](references/evidence_intake_workflow.md)。

## 系统画像与部署变化

陌生机器人、交接、升级和换传感器时读取 [系统画像](references/system_profile.md)：

```bash
python3 scripts/merge_system_evidence.py ... --output evidence/merged.json
python3 scripts/generate_system_profile.py --merged evidence/merged.json --output robot_profile.yaml
python3 scripts/validate_system_profile.py robot_profile.yaml
python3 scripts/diff_system_profiles.py before.yaml after.yaml --output diff.yaml
```

领域模板在 `references/profiles/`。只在项目类型匹配时读取对应 YAML，不一次加载全部模板。

## 人工可审计结果与离线复核

用户要求实验结果、长期算法评估、日志、数据保存、可视化、A/B 比较或结果审查时，读取 [人工可审计结果](references/human_auditable_results.md) 和 [Human Analysis Contract](references/analysis_contract.md)。不要只在聊天中给结论或临时代码。

优先把可复核工具安装到项目：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

运行时优先使用 ROS Noetic 原生证据：

```bash
python3 tools/analysis/result_bundle.py init reports EXP-0001 --run-id RUN-001 --workspace .
python3 tools/analysis/ros_noetic_run_logger.py snapshot RUN_DIR --roswtf
python3 tools/analysis/ros_noetic_run_logger.py record RUN_DIR --topic /result/topic
python3 tools/analysis/ros_noetic_run_logger.py copy-logs RUN_DIR
```

保存职责固定为：`bags/` 保存 rosbag1 高频结构化数据；`series/` 保存归一化连续变量；`metrics.json` 保存标量结果；`logs/` 保存命令、stdout/stderr、roslaunch/node 日志和运行快照；`plots/` 保存可重复生成的图；`report/` 保存静态人工报告。

现有输出不匹配分析契约时，编写项目本地 adapter，而不是把转换逻辑只留在对话中。adapter 放到 `tools/analysis/`，要求 CLI 输入/输出、明确 topic/字段、单位、frame、方向与时间语义，并能在没有 Agent 时独立运行。普通 CSV 可先用：

```bash
python3 tools/analysis/plot_series.py RUN_DIR/series/data.csv \
  --x distance_m --y error_m \
  --output RUN_DIR/plots/error.png
```

完成后生成并验证人工报告：

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
python3 tools/analysis/result_bundle.py validate RUN_DIR --closure --human-analysis
```

如果验收要求必须包含原生 ROS 运行证据，再加 `--ros-audit`。`ready_for_human_review` 只代表材料可审，不代替人的最终结论。

涉及多次实验、baseline/candidate、去重或长期结论时再读取 [实验管理](references/experiment_management.md)，不要为简单调试强制创建完整实验体系。

## 调试与专用栈

默认只读，最多保持三个活动假设。优先 `list/info/type/hz/bw/delay/少量 echo`，再考虑写参数、发布、service/action、bag replay 或硬件动作。

- 基础运行时 → [Noetic 运行时模型](references/noetic_runtime.md)
- actionlib/nodelet/pluginlib/dynamic_reconfigure/ros_control/PCL/RViz/Gazebo → [Noetic 专用运行栈](references/noetic_specialized_operations.md)
- TF/外参 → [TF 与标定](references/tf_calibration.md)
- PPS/PTP/NTP/ROS time → [时间同步](references/time_sync.md)
- rosbag1 → [rosbag](references/rosbag.md)
- SLAM/LIO/VIO → [LiDAR-IMU-RTK](references/lidar_imu_rtk_slam.md)

涉及状态修改先读取 [安全与权限](references/safety_and_permissions.md)。

## 审计模式

普通调试不要加载完整审计材料。只有用户明确要求完整追溯或高风险变更时，按需读取：

- [公式与变量追溯](references/formula_variable_traceability.md)
- [推理知识库](references/reasoning_knowledge_base.md)
- [测试与可观测性](references/testing_and_observability.md)

## 停止条件

得到能解释关键现象的根因并在同条件验证通过后停止。系统画像已覆盖当前变化域时停止无差别扫描；缓存显示域未变化时不重新读取该域。结果任务在用户可独立运行记录、绘图和静态报告流程且关键 provenance 已保存时停止继续堆功能。
