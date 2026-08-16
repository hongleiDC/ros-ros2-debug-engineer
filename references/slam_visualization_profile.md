# SLAM / LIO / VIO 结果画像

## 目录

- [目的](#目的)
- [先回答四个问题](#先回答四个问题)
- [证据层级](#证据层级)
- [图表类别](#图表类别)
- [典型实验画像](#典型实验画像)
- [无真值场景](#无真值场景)
- [diagnosticscsv 规范字段](#diagnosticscsv-规范字段)
- [目录与报告顺序](#目录与报告顺序)
- [停止条件](#停止条件)

## 目的

SLAM 系统的“结果好不好”不能只由一条轨迹和一个 RMSE 判断。完整分析需要把外部误差、估计器状态、匹配质量、可观测性、融合、闭环/地图反馈和实时性能串成因果链。

四张 Core 图是最低证据，不是上限。复杂 SLAM 任务使用“固定核心 + 假设驱动机制图”，而不是“固定四张”或“全变量可视化”。

## 先回答四个问题

每次选择图前先明确：

1. **What**：最终退化是什么？位置、姿态、地图、速度、尺度、闭环还是实时性？
2. **Where/When**：从哪一段距离、时间、场景或状态开始？
3. **Which layer first**：prediction、scan/visual update、fusion、map feedback、loop closure 或 runtime 哪层先异常？
4. **Why**：当前活动假设中的哪一个能解释该顺序？

图表必须服务于这四个问题。不能回答问题的图默认不生成。

## 证据层级

按层级选择，不按固定数量选择：

- **L0 Core，4–6 张**：轨迹、总误差、误差分量、分段、分布、高度/姿态中适用的最小集合。
- **L1 Estimator/Frontend，每个活动假设 1–3 张**：prediction vs update、velocity、bias、matching residual/correction、feature/correspondence。
- **L2 Observability/Fusion，每个活动假设 1–3 张**：方向信息量、Hessian、innovation/gate、measurement status。
- **L3 Map/Loop，按系统启用**：revisit、submap/map consistency、loop candidate/accepted、pose-graph correction。
- **L4 Runtime，1–2+ 张**：只有当算法增加复杂度、出现 backlog 或实时性本身是成功判据时启用。

典型完整 RUN 常见 8–15 张正式图，但不把 8 或 15 作为流程门槛。

## 图表类别

### Core accuracy

优先：

- trajectory XY / 3D；
- height 或 orientation profile；
- horizontal/position error vs distance/time；
- signed lateral/longitudinal/vertical 与 roll/pitch/yaw error；
- segment RMSE/P95 或 drift-per-distance；
- error CDF / tail distribution。

### Estimator state

当怀疑 IMU prediction、速度或状态传播时：

- estimated vs reference velocity；
- velocity error，尤其车辆前向/横向分量；
- gyro/accel bias；
- gravity/attitude residual；
- prediction-to-update correction magnitude；
- covariance，或明确标注为 proxy 的 uncertainty 指标。

不要把未标定 heuristic sigma 命名为 covariance。

### Scan / visual matching

当怀疑前端匹配时：

- scan/feature residual；
- translation/yaw update correction；
- correspondence / effective feature count；
- optimization iterations / convergence status；
- cost profile vs perturbation，在验证局部 basin、强度或方向搜索时使用。

### Observability / degeneracy

当怀疑几何退化或方向不可观测时：

- longitudinal/lateral/yaw directional information；
- Hessian/JTJ eigenvalues；
- condition number；
- degeneracy flag 或 effective dimension；
- 与误差增长共享 distance/time 横轴。

不要只画“最小特征值很小”，同时检查它是否在误差增长之前或同时变化。

### Fusion / RTK / GNSS

当外部定位参与估计时：

- innovation/residual 与 gate；
- accept/reject；
- fix/status/quality；
- measurement age / publish delay；
- measurement update correction；
- 有 lever arm/time offset 时单独验证它们，不把 re-entry jump 全部归因于 estimator。

### Loop / map

真正的 SLAM 而非纯 odometry 还应按问题检查：

- loop candidate score 与 accepted/rejected；
- loop 前后 pose graph correction；
- loop residual；
- revisit alignment error；
- submap overlap/consistency；
- map deformation、duplicate structure 或长期弯曲的可量化 proxy。

只有地图点数本身通常不能证明地图质量。

### Runtime

算法或诊断逻辑增加计算量时：

- frame total runtime；
- scan matching / optimization / map update 分阶段 runtime；
- CPU、RSS；
- queue/backlog、real-time factor 或 deadline miss。

性能图与精度图一起看，避免“精度提高 1%，runtime 增加 40%”被遗漏。

## 典型实验画像

### 简单 baseline/candidate 精度回归

建议 5–8 张：Core 4–6 + 关键 orientation/velocity 或 runtime 1–2。目的只是判断 candidate 是否整体更好，不深入所有内部状态。

### 纵向漂移根因

建议围绕同一 distance 轴形成因果链：

```text
trajectory / horizontal error
→ longitudinal vs lateral error
→ prediction longitudinal increment or velocity error
→ scan-to-map longitudinal correction
→ longitudinal observability
→ map feedback / fixed-map comparison
```

常见 8–12 张。若 prediction 阶段已经先偏离，就不要继续大量扩展 intensity/matching 图；若 prediction 正常而 update 后偏离，再集中看 matching 与 observability。

### RTK 融合问题

Core + innovation/gate + fix/status + timing/age + update correction + relevant bias/velocity，常见 8–12 张。必须区分 RTK measurement quality、时间/lever arm、gate 和 estimator response。

### 完整 SLAM 验收

Core + estimator + matching + observability + fusion（若有）+ loop/map + runtime，常见 10–15 张。只有系统确实包含对应机制时才启用该类别。

## 无真值场景

没有 RTK/mocap/ground truth 时，不伪造绝对 accuracy 结论。可使用：

- Relative Pose Error / drift per distance；
- loop/revisit consistency；
- repeated-route closure error；
- map/submap consistency；
- sensor innovation consistency；
- simulation or partial reference segments；
- known landmarks / surveyed constraints。

报告必须把“self-consistency”与“absolute accuracy”分开。

## diagnostics.csv 规范字段

`plot_slam_diagnostics.py` 对以下规范字段按存在性生成图；项目不必输出全部字段。优先复用现有日志转换成这些字段，不要为了画图侵入生产核心算法。

通用横轴字段，按优先级：

- `distance_m`
- `reference_distance_m`
- `relative_time_s`
- `timestamp`

常用字段示例：

```text
velocity_x_mps
velocity_y_mps
velocity_z_mps
velocity_longitudinal_mps
velocity_lateral_mps
reference_velocity_longitudinal_mps
velocity_error_longitudinal_mps
velocity_error_lateral_mps

gyro_bias_x_rad_s
gyro_bias_y_rad_s
gyro_bias_z_rad_s
accel_bias_x_mps2
accel_bias_y_mps2
accel_bias_z_mps2

scan_match_correction_longitudinal_m
scan_match_correction_lateral_m
scan_match_correction_vertical_m
scan_match_correction_yaw_deg
scan_match_residual_m
correspondence_count
optimization_iterations

longitudinal_information
lateral_information
yaw_information
hessian_min_eigenvalue
hessian_max_eigenvalue
hessian_condition_number
degeneracy_flag

rtk_innovation_m
gnss_innovation_m
rtk_gate_m
gnss_gate_m
rtk_accepted
gnss_accepted
measurement_age_ms

loop_correction_m
loop_correction_yaw_deg
loop_residual_m
loop_accepted
revisit_error_m

frame_runtime_ms
scan_match_runtime_ms
optimization_runtime_ms
map_update_runtime_ms
cpu_percent
rss_mb
```

字段没有可靠物理含义、单位或 frame 时先修正数据契约，不要急着画图。

## 目录与报告顺序

推荐：

```text
plots/
├── plot_manifest.json
├── 01_core/
├── 02_estimator/
├── 03_matching/
├── 04_observability/
├── 05_fusion/
├── 06_loop_map/
├── 07_runtime/
└── 08_hypothesis/
```

报告阅读顺序保持：**现象 → 首个异常层 → 机制证据 → 性能代价 → Decision**。不要按脚本执行顺序或文件生成时间写报告。

如果多张机制图需要比较因果顺序，尽量共享同一 distance/time 横轴，并在报告中引用 `plot_manifest.json` 的 question。

## 停止条件

- Core 已经证明 candidate 失败并达到回滚条件：停止，不为了完整性继续画内部状态。
- 一类机制图已经排除一个活动假设：删除/降级该假设，不继续给它增加图。
- 已经确定最早异常层：下一步优先设计区分实验或最小修复，不继续横向增加 telemetry。
- 三个活动假设仍无法区分：新增一个高信息量实验，而不是把所有 estimator 字段都接入日志。
