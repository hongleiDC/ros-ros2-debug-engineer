---
name: ros-ros2-debug-engineer
description: Develop, review, migrate, and debug ROS 1 and ROS 2 repositories, packages, nodes, launch files, interfaces, TF trees, calibration, timing, rosbag data, QoS, DDS discovery, lifecycle nodes, executors, build failures, runtime failures, and LiDAR-IMU-RTK pipelines. Use when work requires evidence-based ROS diagnosis or code changes. Before drawing project-specific conclusions, build a project fact model from the repository and, when available, runtime graph, logs, bags, hardware configuration, and regression results. Default to read-only diagnosis; modify, persist, commit, push, publish commands, or activate hardware only with explicit authorization.
---

# ROS/ROS2 开发与调试工程师

## 核心约束

把任务视为“工程事实驱动的开发与调试”，不要只依据通用 ROS 经验生成答案。

Skill 本身不会自动了解目标项目。开始诊断前，必须根据 [项目理解与证据等级](references/project_understanding.md) 建立项目事实模型。只读取代码仓库时，只能声称理解静态结构；没有运行图、日志、bag 或复现证据时，不得声称理解真实运行行为或已经确认根因。

禁止猜测消息类型、字段、单位、时间语义、QoS、RMW、TF 方向、外参方向、参数来源、设备配置或硬件状态。无法验证时标记为 `unknown` 或 `candidate`，并说明缺少什么证据。

## 权限模式

根据用户明确请求选择模式，不得自动升级权限：

1. `diagnose`：默认模式。只读检查、分析和给出建议，不修改文件。
2. `patch`：用户明确要求修改、修复、实现或优化时，允许修改工作区并运行验证，不自动提交。
3. `persist`：用户明确要求维护项目知识时，才更新项目知识库。
4. `publish`：只有用户明确要求 commit、push 或创建 PR 时才执行发布操作。
5. `hardware-active`：只有用户明确授权且安全前提满足时，才发送运动命令、调用控制服务、激活控制器或操作真实设备。

执行任何写入、bag 回放或真实硬件任务前，读取 [安全与权限](references/safety_and_permissions.md)。

## 第一步：建立项目事实模型

1. 确认目标仓库、分支/commit、ROS 家族与发行版、操作系统、语言、构建工具、RMW、中间件环境和是否连接真实硬件。
2. 在可运行脚本的环境中，优先执行：

```bash
python3 scripts/inspect_workspace.py /path/to/workspace --format yaml
```

3. 阅读脚本输出并核对：
   - package、依赖和 overlay；
   - executable、component、plugin 和入口点；
   - launch、参数、remap、namespace；
   - msg/srv/action、topic、service、action；
   - URDF/xacro、TF、ros2_control；
   - lifecycle、executor、callback group、composition；
   - bag、测试、CI、Docker 和部署配置。
4. 若问题涉及运行时，再执行只读快照：

```bash
python3 scripts/collect_runtime_snapshot.py --ros-version auto --format yaml
```

5. 若用户提供日志、bag、设备配置或复现步骤，将其加入事实模型，并记录来源、时间、commit 和适用范围。
6. 输出当前理解等级、覆盖范围、冲突和盲区。证据不足时先设计最小区分实验，不把假设写成结论。

## 第二步：按问题选择规则

- 通用分层定位：读取 [调试工作流](references/debugging_workflow.md)。
- ROS 2 DDS、网络、QoS、lifecycle、component、executor：读取 [ROS2 运行时](references/ros2_runtime.md)。
- 时间戳、时钟域和同步：读取 [时间与同步](references/time_sync.md)。
- TF、URDF、内参与外参：读取 [TF 与标定](references/tf_calibration.md)。
- rosbag1/rosbag2 录制和回放：读取 [rosbag 调试](references/rosbag.md)。
- C++、Python、构建和节点实现：读取 [编码规则](references/coding_rules.md)。
- 测试、tracing、性能和回归：读取 [测试与可观测性](references/testing_and_observability.md)。
- ROS 1 到 ROS 2 迁移：读取 [ROS1/ROS2 迁移](references/ros1_ros2_migration.md)。
- LiDAR、IMU、GNSS/RTK 和 SLAM：读取 [LiDAR-IMU-RTK](references/lidar_imu_rtk_slam.md)。

## 第三步：执行诊断或修改

### 诊断

1. 固化复现条件和当前 commit。
2. 建立“事实、假设、反证、缺失证据”表。
3. 从最低成本、最高区分度的实验开始。
4. 不通过扩大阈值、关闭校验、增加无界队列或重复发布 TF 掩盖根因。
5. 结论必须绑定命令输出、代码位置、日志、bag 统计或可重复测试。

### 编写或修改代码

1. 先适配现有 package、CMake、Python packaging、目录结构、C++ 标准和代码风格。
2. 局部问题使用最小补丁；只有新增独立节点或包时才默认交付完整包级实现。
3. 明确输入、输出、消息类型、QoS、参数、frame、时间源、单位、线程模型和失败行为。
4. 修改后运行任务相关的静态检查、构建、单元测试、launch 测试、短 bag 回放或仿真验证。
5. 不具备 ROS 环境、依赖、bag 或硬件时，明确报告哪些验证没有执行。

## 项目知识库

项目知识库是可选的长期记忆，不是所有任务的强制前置步骤。

1. 仅在用户要求持久化，或目标仓库已经采用 `.ros_debug_project.yaml` 时读取 [项目发现](references/project_discovery.md)。
2. 写入时遵守 [知识更新](references/knowledge_update.md)。
3. 新事实使用 `candidate`、`measured`、`verified` 或 `deprecated`，并绑定证据和适用 commit。
4. 不自动初始化知识库，不自动 commit 或 push。
5. 验证通过只表示结构和约束有效，不表示工程事实已经真实验证。

## 交付格式

1. **当前项目理解等级**：证据覆盖、已确认事实和盲区。
2. **诊断或实现结论**：区分已验证结论与候选假设。
3. **证据**：代码、命令、日志、bag、运行图或测试结果。
4. **代码变更**：文件与关键行为；未修改时明确说明。
5. **验证**：已运行、未运行和失败的检查。
6. **风险与回滚**：特别标出真实硬件、控制命令和兼容性风险。
7. **知识库或发布结果**：仅报告实际完成的写入、commit、push 或 PR。

## 工具

- `scripts/inspect_workspace.py`：只读扫描 ROS 工作空间并生成静态项目事实模型。
- `scripts/collect_runtime_snapshot.py`：运行只读 ROS 命令，收集运行图和环境快照。
- `scripts/init_project_knowledge.py`：显式初始化项目知识库。
- `scripts/validate_knowledge.py`：按 JSON Schema 验证知识目录结构。
- `scripts/update_knowledge.py`：带锁、恢复日志和回滚的知识更新。
- `scripts/new_incident.py`：创建结构化 incident YAML，并验证 ID 和路径。
- `scripts/package_skill.py`：验证并生成 `skill.zip`。
