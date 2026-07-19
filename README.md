# ros-ros2-debug-engineer

用于开发、审查、迁移和调试 ROS 1 / ROS 2 项目的 ChatGPT Skill。

## 这版解决的核心问题

这个 Skill **不会因为看到仓库就声称已经了解项目**。它把项目理解划分为证据等级：

- L0：只知道仓库说明和文件列表；
- L1：完成 package、源码、launch、参数、接口、URDF 等静态模型；
- L2：在目标环境成功构建；
- L3：获得 node/topic/service/action、QoS、Lifecycle、TF 和参数运行时快照；
- L4：用日志、bag、仿真或硬件稳定复现；
- L5：修复后通过明确回归。

只读取代码时，它只能说“理解静态结构”，不能说“理解真实运行行为”或“根因已经确认”。

## 长任务不会遗忘核心目标

复杂调试开始时，使用 `goal_guard.py` 建立结构化目标契约。目标契约保存用户原始请求、单一主目标、可验证成功判据、非目标、约束、里程碑、当前证据和唯一下一步。

```bash
python3 scripts/goal_guard.py start /path/to/goal-state GOAL-0001 "Fix timestamp root cause" \
  --workspace /path/to/project \
  --request "修复 IMU 时间回退" \
  --desired-outcome "长期运行无回退且精度不下降" \
  --primary-goal "消除 IMU 时间戳回退根因，同时保持定位精度" \
  --success "连续运行无回退::运行日志和计数器" \
  --success "ATE 不高于基线::同一 bag 评估报告" \
  --milestone "建立可复现基线"
```

每次代码修改、参数调整或实验前，必须调用 `goal_guard.py guard`，明确动作关联的 `SC-*` 和 `M-*`。每完成 2 至 3 组工具调用、发生失败、用户纠正或任务恢复时，必须 checkpoint 并重新显示主目标。目标只能在用户明确授权后修订，旧目标哈希会保留。


## 公式与变量不允许失联

涉及时间同步、坐标变换、滤波、标定、误差传播、优化和指标计算时，必须保存完整推导链，并维护数学符号到代码变量、配置参数和消息字段的映射。关键变量名必须表达物理意义、单位和 frame，例如 `time_offset_s`、`angular_velocity_rad_s`、`T_map_base`，不能随意使用 `tmp`、`val` 或含义不明的 `x1`。

## 主要能力

- ROS 1 遗留项目和 ROS 2 项目的 C++ / Python 开发与调试；
- package、依赖、overlay、CMake、ament/catkin 和接口生成；
- launch、参数、namespace、remap、Lifecycle 和 Components；
- DDS discovery、RMW、网络、QoS、Executor 和 Callback Group；
- TF、URDF、内参、外参、时间戳和时钟同步；
- rosbag1 / rosbag2 录制、分析、隔离回放和回归；
- LiDAR、IMU、GNSS/RTK 与 SLAM 数据链路；
- ROS 1 到 ROS 2 迁移；
- tracing、性能、单元测试、launch 集成和数据回归；
- 核心目标契约、检查点和防漂移守卫；
- 实验台账、实验指纹和重复实验阻止；
- 可选的项目知识库和审计更新。


## 推理与公式代码知识库

采用项目知识库后，公式相关代码会维护四类可审计记录：

- `FORM-*`：公式版本、符号、假设、坐标/时间约定和逐步推导；
- `MAP-*`：数学符号到代码变量、配置参数、消息字段和状态索引的严格映射；
- `REAS-*`：从已知条件到结论的逐步推理链；
- `AUD-*`：代码 identifier、单位、frame、方向、公式版本和推理完整性审计。

```bash
python3 scripts/logic_audit.py project_knowledge \
  --workspace . \
  --audit-id AUD-0001 \
  --write-report \
  --strict-warnings
```

审计可以发现映射断裂、变量语义冲突、明显的单位后缀错误、缺失单位转换、过期代码位置、推理跳步和“未验证前提却宣称结论 verified”等问题。审计通过不等于数学模型已被真实数据证明，仍需手算、单元测试、bag、仿真或硬件回归。

## 安全模式

默认是只读 `diagnose`。权限不会自动升级：

- `diagnose`：只读分析；
- `patch`：用户明确要求修改时，允许工作区补丁；
- `persist`：用户明确要求时，更新项目知识；
- `publish`：用户明确要求时，才 commit、push 或创建 PR；
- `hardware-active`：用户明确授权并满足安全条件时，才发送命令或激活真实硬件。

bag 回放默认使用白名单和隔离环境，避免把控制 topic 回放到现场机器人。

## 安装与打包

```bash
git clone https://github.com/hongleiDC/ros-ros2-debug-engineer.git
cd ros-ros2-debug-engineer
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

产物固定为：

```text
dist/skill.zip
```

## 建立项目事实模型

### 静态扫描

```bash
python3 scripts/inspect_workspace.py /path/to/workspace --format yaml
```

输出包括：

- Git branch、commit 和 dirty 状态；
- package、format、build type、依赖和语言；
- executable、component、launch、参数和自定义接口；
- URDF/xacro、plugin、Docker、systemd/udev、测试和 bag；
- Lifecycle、Callback Group、ros2_control、Nav2、MoveIt、TF、LiDAR、IMU 和 GNSS 线索；
- 当前理解等级和无法确认的内容。

扫描结果是索引，不是运行时证明。

### 运行时只读快照

```bash
python3 scripts/collect_runtime_snapshot.py --ros-version auto --format yaml
```

它只运行有超时的只读命令，不 publish、不 echo 数据、不调用 service/action，也不改变参数。

## 项目知识库

知识库是可选能力，不是每个任务都必须创建。

只有用户明确要求时初始化：

```bash
python3 scripts/init_project_knowledge.py \
  /path/to/target-project \
  --project-id my_robot
```

创建：

```text
<target-project>/
├── .ros_debug_project.yaml
└── project_knowledge/
    ├── README.md
    ├── project.yaml
    ├── project_model.yaml
    ├── active_configuration.yaml
    ├── topics.yaml
    ├── timing.yaml
    ├── CHANGELOG.md
    ├── devices/
    ├── calibrations/
    ├── bags/
    ├── incidents/
    ├── decisions/
    ├── goals/
    ├── experiments/
    ├── formulas/
    ├── variable_mappings/
    ├── reasoning_chains/
    ├── audits/
    └── regression_tests/
```

验证使用正式 JSON Schema：

```bash
python3 scripts/validate_knowledge.py /path/to/project_knowledge
```

注意：结构验证通过不代表设备参数、外参或根因已经真实验证。

更新示例：

```bash
python3 scripts/update_knowledge.py \
  /path/to/project_knowledge \
  active_configuration.yaml \
  configuration.use_sim_time \
  true \
  --status measured \
  --reason "bag replay configuration" \
  --evidence "launch file and runtime parameter"
```

更新工具具有文件锁、未完成事务恢复、JSON Schema 验证、verified 保护和失败回滚。

创建 incident：

```bash
python3 scripts/new_incident.py \
  /path/to/project_knowledge \
  INC-0006 \
  "rtk timestamp mismatch"
```

## Skill 目录

```text
SKILL.md
agents/openai.yaml
references/*.md
references/schemas/*.yaml
scripts/*.py
tests/*.py
```

具体项目的 bag、点云、设备序列号、标定和长期结论不应打包进 Skill。
