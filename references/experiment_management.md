# 实验登记、去重与复用

## 目录

- [核心原则](#核心原则)
- [实验前](#实验前)
- [允许重复的例外](#允许重复的例外)
- [实验中](#实验中)
- [实验后](#实验后)
- [与回归测试的关系](#与回归测试的关系)
- [命令](#命令)
- [与推理和公式知识库联动](#与推理和公式知识库联动)

## 核心原则

任何会改变参数、代码、依赖、设备、数据、时间配置、外参、QoS、RMW、launch 或运行顺序的验证，都视为一次实验。实验前登记，实验后立即补全结果。不能只在聊天中描述后忘记写入。

“实验标题相似”不能作为去重依据。使用稳定实验指纹比较实际条件：主线 commit、实验 commit、脏工作区差异、环境、依赖快照、输入文件哈希、设备与标定、变量、命令和执行顺序。

## 实验前

1. 先执行 `goal_guard.py show` 读取活动 `GOAL-*`，确认本实验服务的主目标、`SC-*` 和 `M-*`。没有活动目标时不得创建新实验。
2. 读取 `project_knowledge/experiments/` 中全部历史记录。
3. 明确实验目标、可证伪假设、基线和唯一主要变量；若实验涉及计算，记录公式版本、推导 ID 和变量映射表。
4. 记录主线：主线分支和不可变 commit。仅写 `main`、`master` 或“最新代码”不合格。
5. 记录实验代码：实验分支、commit、工作区是否 dirty；dirty 时保存差异指纹。
6. 记录环境：ROS 版本与发行版、RMW、ROS_DOMAIN_ID、操作系统、架构、容器镜像与 digest。
7. 记录依赖：package.xml、CMakeLists、requirements/lock、repos、Dockerfile 等依赖文件的路径与 SHA-256，以及固件版本。
8. 记录输入：bag、数据集、launch、参数、配置、设备、标定及其 ID 或 SHA-256。
9. 记录完整命令、步骤、预期现象、指标、阈值和安全限制；指标名称必须与公式中的物理量、单位和代码字段一致。
10. 使用 `scripts/experiment_registry.py create` 生成指纹并检查重复。
11. 若存在完全相同指纹，默认停止，不重复运行；语义指纹相同但 commit/主机不同的记录列入 `similar_match_ids`，人工确认是否有新增区分度。

## 允许重复的例外

只有下列情况可以用 `--allow-duplicate` 重复，并必须提供 `--duplicate-reason`：

- 评估随机性、抖动或可重复性，需要独立重复样本；
- 上次实验受中断、设备故障或记录损坏影响；
- 时间、地点、硬件个体或外部环境本身就是待测变量；
- 需要第三方独立复核；
- 监管或验收流程要求重复。

“忘记结果”“不确定是否做过”“再试一次看看”不是合格理由。

## 实验中

- 按记录的命令和顺序执行；临时改变条件时先更新记录或创建新实验。
- 每个计算结果保留代入值、单位、公式编号和中间量，禁止只记录最终数值。
- 不在同一个实验中同时改变多个无法分离的主要变量。
- 记录开始时间、异常、退出码、日志与产物路径。
- 若发现条件与计划不一致，将状态标为 `aborted` 或创建新的 EXP 记录，不伪装为原计划结果。

## 实验后

使用 `scripts/experiment_registry.py finish` 写入：

- pass、fail、mixed 或 error；
- 指标值、单位及相对基线比较；
- 日志、轨迹、地图、报告等产物及 SHA-256；
- 观察结果、失败信息和异常；
- 假设 supported、rejected 或 inconclusive；
- 可复用结论、下一步和不应再重复的条件。

完成记录不得原地改成另一套实验条件。条件变化时创建新 EXP，并通过 parent/compare-to 建立关系。实验完成后立即创建 `goal_guard.py checkpoint --trigger experiment`，把结果是否推进成功判据写回目标进度；实验失败不能让 Agent 自动改换主目标。

## 与回归测试的关系

实验用于探索和比较，回归测试用于长期防止已知问题复发。当某次实验得到稳定、可重复且有明确判据的结果时，将其转化为 `regression_tests/` 记录，并引用 `experiment_ids`。不要把一次偶然成功直接当作 verified 回归。

## 命令

创建并自动捕获 Git、环境和依赖快照：

```bash
python3 scripts/experiment_registry.py create \
  /path/to/project_knowledge EXP-0001 "IMU time offset sweep" \
  --workspace /path/to/repository \
  --objective "Determine whether a 3 ms offset reduces trajectory error" \
  --hypothesis "A positive 3 ms IMU offset lowers ATE" \
  --criterion SC-1 \
  --milestone M-2 \
  --alignment "This experiment directly tests whether timestamp correction satisfies SC-1" \
  --mainline-branch main \
  --input BAG-0004 \
  --input-file data/run04.mcap \
  --parameter-file config/slam.yaml \
  --change "imu_time_offset_ms: 0 -> 3" \
  --command "ros2 launch my_pkg replay.launch.py bag:=data/run04.mcap" \
  --expected "ATE RMSE decreases without new timestamp regressions" \
  --metric "ate_rmse_m:lower:m"
```

执行实际命令前将计划原子切换为 `running` 并记录开始时间：

```bash
python3 scripts/experiment_registry.py start \
  /path/to/project_knowledge EXP-0001
```

只有 `running` 状态可以补全结果：

```bash
python3 scripts/experiment_registry.py finish \
  /path/to/project_knowledge EXP-0001 \
  --status completed \
  --outcome pass \
  --summary "ATE decreased from 0.42 m to 0.31 m" \
  --metric "ate_rmse_m=0.31:m:baseline 0.42 m" \
  --observation "No timestamp rollback was observed" \
  --artifact results/exp-0001/trajectory.csv:"trajectory output" \
  --verdict supported \
  --confidence high \
  --lesson "The offset sign is sensor-to-host positive" \
  --next-action "Promote this case to regression TEST-0007"
```

## 与推理和公式知识库联动

涉及数学模型或公式变量的实验必须记录相关 `FORM-*`、`MAP-*` 和 `REAS-*`。实验前审计这些记录与当前 commit 一致；实验后把中间量、单位、公式版本、推理步骤和结果证据写回知识库。若实验发现公式假设、单位、frame、方向或变量映射错误，必须将旧结论降级或弃用，不能只修改实验摘要。
