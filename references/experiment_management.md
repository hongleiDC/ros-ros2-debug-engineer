# ROS Noetic 实验登记、去重与复用

## 核心原则

任何会改变参数、代码、依赖、设备、数据、时间配置、外参、queue/transport、launch、TF 来源或运行顺序的验证，都视为一次实验。实验前登记，实验后立即补全结果。不能只在聊天中描述后丢失证据。

“实验标题相似”不能作为去重依据。使用稳定实验指纹比较实际条件：主线 commit、实验 commit、dirty diff、Noetic 环境、catkin overlay、依赖快照、输入 bag 哈希、设备与标定、主要变量、完整命令和执行顺序。

## EXP 与 RUN

- `EXP-*`：保存目标、可证伪假设、唯一主要变量、成功判据、父实验和比较关系；
- `RUN-*`：保存一次实际执行的 commit、`.bag`、配置、命令、metrics、series、plots、logs 和 report。

一个 EXP 可以包含多个 RUN。不要为了每个 bag/repeat 复制一个新 EXP；也不要把不同 bag、不同配置或 baseline/candidate 输出混进同一个 RUN。

## 实验前

1. 读取活动 `GOAL-*`，确认本实验服务的 `primary_goal`、`SC-*`、`M-*`；复杂任务没有活动目标时先建立目标。
2. 读取历史 `project_knowledge/experiments/`，避免重复实验。
3. 明确实验目标、可证伪假设、baseline 和唯一主要变量；涉及公式时记录 `FORM-*` / `MAP-*` / `REAS-*`。
4. 记录主线 branch + immutable commit；只写“main 最新”不合格。
5. 记录实验 branch/commit/dirty diff 指纹。
6. 记录 Noetic 环境：

```text
ROS_VERSION=1
ROS_DISTRO=noetic
rosversion -d=noetic
ROS_MASTER_URI
ROS_IP / ROS_HOSTNAME
Ubuntu / architecture / container image digest
ROS_PACKAGE_PATH / CMAKE_PREFIX_PATH
catkin build method
```

7. 记录依赖：`package.xml`、`CMakeLists.txt`、requirements/lock、`.repos`、Dockerfile、系统库和固件版本。
8. 记录输入：`.bag`、launch、YAML/rosparam、设备、标定、地图/模型及 SHA-256。
9. 记录时间条件：`/use_sim_time`、`rosbag play --clock`、rate、start offset、duration、loop，以及 TF/static TF 来源。
10. 记录完整命令、预期现象、metrics、阈值和安全限制。
11. 使用 `scripts/experiment_registry.py create` 生成指纹并检查重复。
12. 对长时间 bag/算法/标定/状态估计/性能实验，在运行前创建独立 `RUN-*` Result Bundle；micro/debug 不强制创建。

## 允许重复的例外

只有下列情况可用 `--allow-duplicate`，并提供原因：

- 测随机性、抖动、可重复性；
- 上次运行中断或数据损坏；
- 时间、地点、硬件个体、温度或外部环境本身是变量；
- 第三方独立复核；
- 验收/监管要求重复。

“忘记结果”“再跑一次看看”不是合格理由。

## 实验中

- 按登记命令和顺序执行；临时改变主要条件时新建 RUN/EXP。
- 保存 stdout/stderr、roslaunch/driver 日志到 `logs/`。
- 轨迹、误差和连续诊断写入 `series/`；标量写入 `metrics.json`。
- 记录开始时间、异常、退出码和关键 artifact。
- 发现条件与计划不一致时标记 `aborted` 或新建 RUN，不伪装为原计划结果。
- 不在同一实验中同时改 offset、外参、noise、matching weight 等多个无法分离的主要变量。

## 实验后

完成 Result Bundle 后，用 `scripts/experiment_registry.py finish` 写入：

- pass / fail / mixed / error；
- 关键 metric、单位、baseline 比较；
- Result Bundle 路径和必要 SHA-256；
- 主要观察与异常；
- hypothesis: supported / rejected / inconclusive；
- 可复用结论、下一步和不应重复的条件。

完成记录不得原地改成另一套实验条件。条件变化时创建新 EXP/RUN，并用 parent/compare-to/baseline_run 建立关系。

## Noetic A/B 最小闭环

1. baseline/candidate 使用同一 `.bag` 和同一回放窗口；
2. 保持 `/use_sim_time`、`--clock`、rate、TF 来源一致；
3. 保持同一 reference、frame、轨迹对齐和指标定义；
4. 只改变一个主要变量；
5. 生成 `metrics.json`、必要 series/plots、`delta_metrics.json`；
6. 生成人可读 `report/index.html`；
7. `result_bundle.py validate RUN_DIR --closure` 通过后，才认为结果材料闭环。

## 命令示例

```bash
python3 scripts/experiment_registry.py create \
  /path/to/project_knowledge EXP-0001 "IMU time offset sweep" \
  --workspace /path/to/repository \
  --objective "Determine whether a 3 ms offset reduces trajectory error" \
  --hypothesis "A positive 3 ms IMU offset lowers ATE" \
  --criterion SC-1 \
  --milestone M-2 \
  --alignment "This experiment directly tests timestamp correction" \
  --mainline-branch main \
  --input BAG-0004 \
  --input-file data/run04.bag \
  --parameter-file config/slam.yaml \
  --change "imu_time_offset_ms: 0 -> 3" \
  --command "roslaunch my_pkg replay.launch bag:=data/run04.bag" \
  --expected "ATE RMSE decreases without timestamp rollback" \
  --metric "ate_rmse_m:lower:m"
```

运行前切换到 running：

```bash
python3 scripts/experiment_registry.py start \
  /path/to/project_knowledge EXP-0001
```

创建本次 RUN：

```bash
python3 scripts/result_bundle.py init \
  /path/to/reports EXP-0001 \
  --label bag04-offset-3ms \
  --workspace /path/to/repository \
  --dataset-file data/run04.bag \
  --config-file config/slam.yaml \
  --command "roslaunch my_pkg replay.launch bag:=data/run04.bag"
```

完成后：

```bash
python3 scripts/experiment_registry.py finish \
  /path/to/project_knowledge EXP-0001 \
  --status completed \
  --outcome pass \
  --summary "ATE decreased from 0.42 m to 0.31 m" \
  --metric "ate_rmse_m=0.31:m:baseline 0.42 m" \
  --observation "No timestamp rollback was observed" \
  --artifact reports/EXP-0001/RUN-...:"reproducible result bundle" \
  --verdict supported \
  --confidence high \
  --lesson "The offset sign is sensor-to-host positive" \
  --next-action "Promote this case to regression"
```

## 与回归测试和知识库联动

稳定、可重复、有明确判据的实验结果应转成长期 regression test，并引用 `experiment_ids` / `run_id`。一次偶然成功不能直接标为 verified。

公式、单位、frame、方向、时间基准或变量映射被实验否定时，旧知识记录必须降级/弃用；不能只改实验摘要。
