# SLAM / LIO / VIO 结果画像

## 目的

定义一个**系统级、长期稳定**的 SLAM 结果画像，使每次 RUN 自动产生同一种证据结构，工程师即使没有 AI 也能按固定顺序判断哪一层首先异常。

该画像在项目设计阶段固化到 `analysis/observation_contract.yaml` 与 `analysis/analysis_profile.yaml`。运行时不是让 Agent 再决定“今天画哪几张”。

## 证据层级

### L0 Core accuracy

回答最终表现和退化位置：

- trajectory XY/3D；
- height/orientation profile（适用时）；
- position/horizontal error vs distance/time；
- signed lateral/longitudinal/vertical 与姿态误差；
- segment RMSE/P95 或 drift-per-distance；
- error CDF/tail distribution。

### L1 Estimator / prediction

回答误差是否在 measurement update 之前已经出现：

- estimated/reference velocity 与 velocity error；
- gyro/accel bias；
- gravity/attitude residual；
- prediction-to-update correction；
- 真正 covariance 或明确命名的 proxy。

### L2 Frontend / matching

回答 scan/visual update 是否引入或放大误差：

- translation/yaw correction；
- residual/cost；
- correspondence/effective feature count；
- convergence/optimization iterations。

### L3 Observability / degeneracy

回答约束是否在对应方向失效：

- longitudinal/lateral/yaw information；
- Hessian/JTJ eigenvalues；
- condition number；
- degeneracy flag/effective dimension。

必须与外部误差共享或可对应到同一 time/distance 轴，不能只看“最小特征值很小”就宣称根因。

### L4 Fusion

外部定位参与时：

- innovation/residual 与 gate；
- accept/reject；
- fix/status/quality；
- measurement age/delay；
- measurement update correction。

必须区分 measurement quality/timing 和 estimator response。

### L5 Loop / map

真正包含 loop closure、pose graph、submap 或 recursive map feedback 时：

- loop candidate/accepted；
- loop/pose graph correction；
- loop residual；
- revisit alignment error；
- submap/map consistency。

纯 odometry/localization 不要求这一层。

### L6 Runtime

长期算法应根据成功判据固定：

- frame total runtime；
- matching/optimization/map update 等阶段耗时；
- CPU/RSS；
- queue/backlog/realtime factor/deadline miss。

精度和 runtime 一起验收。

## Observation Contract 字段

项目不必拥有所有字段，只声明系统实际需要的稳定字段。常用规范列包括：

```text
distance_m / reference_distance_m / relative_time_s / timestamp
velocity_error_longitudinal_mps
velocity_error_lateral_mps
gyro_bias_*_rad_s
accel_bias_*_mps2
scan_match_correction_longitudinal_m
scan_match_correction_lateral_m
scan_match_correction_yaw_deg
scan_match_residual_m
correspondence_count
optimization_iterations
longitudinal_information
lateral_information
yaw_information
hessian_min_eigenvalue
hessian_condition_number
rtk_innovation_m
rtk_gate_m
rtk_accepted
measurement_age_ms
loop_correction_m
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

每个字段必须在 Observation Contract 中定义 unit、frame、time basis、source、required 和 interpretation。字段没有可靠物理语义时先修正契约，不急着画图。

## 典型固定画像

### LIO / RTK localization

通常固定：Core + estimator + matching + observability + runtime；如果 RTK 是在线融合输入，则 fusion 也应启用并根据系统目标设为 required。

### 完整 SLAM

通常固定：Core + estimator + matching + observability + loop/map + runtime；有外部 aiding 再加入 fusion。

### 纯 localization 回归

可以只保留 Core + 与该系统真实 failure mode 相关的一两个稳定层，不强行复制完整 SLAM 画像。

图数只用于检查 profile 是否异常膨胀；不是每次运行的任务量目标。

## 纵向漂移的人类阅读链

纵向漂移是一个 Analysis Contract 示例，而不是临时 Agent 提示词：

```text
trajectory / horizontal error
→ signed longitudinal vs lateral error
→ longitudinal velocity/prediction evidence
→ scan-to-map longitudinal correction
→ longitudinal observability
→ map feedback / loop correction（若存在）
→ runtime side effect
```

解释顺序：

- prediction/velocity 先异常：优先 IMU、时间、bias、运动模型；
- prediction 正常而 update 后偏离：优先 matching/frontend；
- directional information 更早下降：考虑几何可观测性；
- local estimate 正常而 map/loop 后跳变：调查 recursive map/pose graph feedback；
- RTK innovation/gate 先异常：先分离 measurement/timing 与 estimator response。

这条阅读路径应出现在静态 `report/index.html` 的 section 顺序和 guidance 中，使人工无需 AI 也能走完。

## 无真值场景

没有 RTK/mocap/ground truth 时，不伪造 absolute accuracy。可固定使用：RPE/drift per distance、loop/revisit consistency、repeated-route closure、map/submap consistency、sensor innovation consistency、partial surveyed constraints。

报告必须把 self-consistency 和 absolute accuracy 分开。

## 特殊研究图

cost sweep、oracle、intensity basin、特殊 perturbation 等研究图属于 `08_hypothesis/`。它们默认不进入长期 SLAM profile。只有多次证明对常规诊断有稳定价值后，才升级为长期 Observation/Visualization Contract。

## 停止条件

- 系统 profile 已覆盖关键 failure layers：停止扩默认图；
- required signal 缺失：补 Observation Contract 对应的数据源；
- 固定报告已经定位 earliest abnormal layer：下一步做区分实验或最小修复；
- 固定报告仍不能区分：设计一个高信息量实验，不把所有 estimator 变量接入长期日志。
