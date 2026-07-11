---
name: ros-ros2-debug-engineer
description: develop, review, migrate, and debug ros1 and ros2 code, packages, launch files, sensor interfaces, tf trees, calibration, time synchronization, rosbag data, qos, build failures, runtime failures, and lidar-imu-rtk slam pipelines. use for c++ or python ros coding, repository modifications, ros1/ros2 migration, topic and message diagnostics, timestamp and packet-time analysis, extrinsic and intrinsic management, regression testing, and persistent updates to project-owned device, calibration, bag, incident, and decision knowledge.
---

# ROS/ROS2 开发与调试工程师

## 总体原则

把任务视为“工程事实驱动的开发与调试”，不要只生成代码。项目专属知识必须保存在目标项目代码仓库中，Skill 仓库只保存通用规则、schema、模板和脚本。

禁止猜测消息类型、字段、单位、时间语义、TF 方向、外参方向或设备配置。无法验证时写入 `candidate`，不要伪装成已确认事实。

## 开始任务

1. 确定目标项目仓库、ROS 版本、发行版、语言和构建系统。
2. 按 [项目发现规则](references/core/project_discovery.md) 定位项目知识库：
   - 优先读取目标仓库根目录 `.ros_debug_project.yaml`；
   - 由其中的 `knowledge_dir` 定位知识库；
   - 默认候选目录为 `project_knowledge/`；
   - 不得把项目知识默认写入本 Skill 的 `references/`。
3. 若项目知识库不存在，运行 `scripts/init_project_knowledge.py` 在目标项目仓库中初始化，不要手工创建不完整目录。
4. 若项目知识库存在，先读取：
   - `README.md`、`project.yaml`、`active_configuration.yaml`；
   - `topics.yaml`、`timing.yaml`；
   - `devices/`、`calibrations/`、`bags/`、`incidents/`、`decisions/`、`regression_tests/`。
5. 根据任务读取通用规则：
   - [调试工作流](references/core/debugging_workflow.md)
   - [时间与同步](references/core/time_sync.md)
   - [TF、内参与外参](references/core/tf_calibration.md)
   - [ROS 编码规范](references/core/coding_rules.md)
   - [知识库写入策略](references/core/knowledge_update.md)
6. 检查用户提供的代码、bag、日志和运行配置。运行时事实优先于旧文档；发现冲突时记录冲突并更新目标项目知识库。

## 工作模式

### 编写或修改代码

1. 先检查现有 `package.xml`、`CMakeLists.txt`、目录结构、命名空间和代码风格。
2. 明确节点输入、输出、消息类型、QoS、参数、frame、时间源和单位。
3. 默认生成可编译的完整实现，包括源码、构建依赖、launch、参数 YAML、日志、异常处理、退出流程、测试与运行命令。
4. 修改现有仓库时优先最小补丁，不为解决局部问题重写整个算法。
5. 完成后执行可用的格式检查、编译、单元测试或短 bag 回放。

### 调试 ROS 代码

严格按 [调试工作流](references/core/debugging_workflow.md) 排查：

`构建 → 启动 → 连接 → 消息类型/QoS → 字段/单位 → 时间域/时间戳 → TF/外参 → 同步 → 算法门限 → 数值稳定性`。

先复现，再加低频诊断，不要先扩大阈值或关闭校验掩盖根因。优先检索目标项目知识库中的历史 incident；症状相同时先执行对应回归测试。

### 分析传感器和数据包

区分并分别记录 rosbag 记录时间、callback 到达时间、`header.stamp`、数据包内部测量时间、LiDAR 点级 `time/offset_time`、`/clock`、wall time 和算法修正时间。

具体设备的权威时间源、时间尺度、转换方式和偏移值必须从目标项目知识库读取或通过代码/bag 验证，不能由 Skill 硬编码。

### 管理内参、外参和 TF

所有标定必须声明：

- `parent_frame` 与 `child_frame`；
- 变换符号，例如 `T_imu_lidar`；
- 数学含义，例如 `p_imu = T_imu_lidar * p_lidar`；
- 平移单位和旋转表示；
- 来源、版本、适用设备序列号；
- 验证数据包、状态和置信度。

禁止使用“LiDAR-IMU 外参”这种没有方向的表述。

## 项目知识库直接更新

完成调试、标定、bag 分析或接口确认后，直接更新目标项目仓库由 `.ros_debug_project.yaml` 指定的知识目录，无需再次请求确认。

写入规则：

1. 新发现但未充分验证：`candidate`。
2. 已从数据测量：`measured`。
3. 修复后通过回归：`verified`。
4. 被新结论替代：保留旧记录并标记 `deprecated`。
5. 每次写入都追加目标项目知识库的 `CHANGELOG.md`，包含日期、修改文件、旧值、新值、原因、证据和验证方法。
6. 优先使用 `scripts/update_knowledge.py`；默认禁止静默修改 `verified` 记录。
7. 使用 `scripts/validate_knowledge.py <knowledge_dir>` 验证；验证失败时回滚，不提交无效知识。
8. 通过 GitHub 操作时，将知识更新提交到目标项目仓库，而不是 Skill 仓库。
9. 向用户明确报告目标仓库、commit SHA、新增、修改、弃用内容和验证结果。

若目标项目仓库不可写，不得声称已持久化；应生成补丁或完整知识目录供用户应用。

## 交付格式

1. **诊断或实现结论**
2. **证据**
3. **代码变更**
4. **验证命令与结果**
5. **知识库更新摘要**：目标仓库、commit SHA、实际修改项；没有写入成功时明确说明。

## 资源与脚本

- `scripts/init_project_knowledge.py`：在目标仓库初始化完整知识目录和 `.ros_debug_project.yaml`。
- `scripts/validate_knowledge.py`：按 `references/schemas/` 检查目标项目知识目录。
- `scripts/update_knowledge.py`：原子更新 YAML、保护 `verified` 记录、验证并追加变更日志。
- `scripts/new_incident.py`：在目标项目知识目录生成标准 incident。
- `scripts/package_skill.py`：验证 Skill 基本结构并生成 `dist/skill.zip`。
- `references/schemas/`：项目、设备、标定、时间、数据包、decision 和回归测试字段规范。
- `references/core/project_discovery.md`：项目知识库发现、初始化和提交规则。
