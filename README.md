# ros-ros2-debug-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-1%20%7C%202-22314E?logo=ros&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

一个面向 ChatGPT 与 Codex 的证据驱动型 ROS 1 / ROS 2 开发、迁移和调试 Skill。它先建立项目事实模型，再处理构建、运行图、QoS、TF、时间同步、标定、rosbag、Lifecycle、Executor 以及 LiDAR–IMU–GNSS/RTK 等问题。

它的核心原则不是“看到代码就猜根因”，而是把事实、假设、公式、代码变量、实验和结论保持在一条可复核的证据链上。

## 为什么使用它

- **证据分级**：静态扫描、构建、运行时、复现和回归结果不会混为一谈。
- **项目感知**：先识别 package、launch、接口、参数、TF、QoS、RMW、bag、CI 和部署边界。
- **目标防漂移**：长任务通过 `GOAL-*`、成功判据、里程碑和 checkpoint 保持主线。
- **公式到代码可追溯**：用 FORM、MAP、REAS、AUD 关联公式、单位、frame、时间基准和代码变量。
- **实验可复用**：记录 commit、依赖、输入、环境、命令和结果，阻止没有新增信息的重复实验。
- **安全优先**：默认只读诊断；修改、持久化、发布和真实硬件操作需要明确授权。
- **发行版感知**：区分稳定发行版、Rolling、ROS 1 EOL、Windows 和 `ros1_bridge` 限制。

## 项目理解等级

| 等级 | 能够证明的内容 | 不能据此声称的内容 |
|---|---|---|
| L0 | 仓库说明与文件列表 | package 关系或实现行为 |
| L1 | 静态 package、源码、launch、接口和配置模型 | 构建成功或真实运行行为 |
| L2 | 在目标环境完成构建 | 运行图、实时性或硬件行为 |
| L3 | 获得足够的运行图、端点、QoS 和参数证据 | 问题已经稳定复现 |
| L4 | 通过日志、bag、仿真或硬件稳定复现 | 修复已经通过回归 |
| L5 | 修复后满足明确回归判据 | 超出测试范围的泛化结论 |

## 适用场景

- ROS 1 遗留系统维护与 ROS 1 → ROS 2 迁移；
- ament/catkin、CMake、Python packaging、接口生成和 overlay 问题；
- DDS discovery、RMW、网络、QoS、Executor、Callback Group；
- Lifecycle、Components、ros2_control、Nav2、MoveIt；
- TF/URDF、内外参、时间戳、时钟域和同步；
- rosbag1/rosbag2 录制、隔离回放、QoS override 和数据回归；
- LiDAR、IMU、GNSS/RTK、SLAM 和状态估计；
- 公式、标定、控制和优化代码的变量映射与逻辑审计。

## 快速开始

### 在 ChatGPT 中使用

安装 Skill 后，可直接使用类似提示：

```text
Use $ros-ros2-debug-engineer to inspect this ROS 2 workspace,
separate verified facts from hypotheses, and propose the smallest diagnostic experiment.
```

```text
使用 $ros-ros2-debug-engineer 检查这个 LiDAR-IMU 项目的时间同步和 TF，
先建立事实模型，不要在没有 bag 或运行时证据时确认根因。
```

### 从源码验证和打包

```bash
git clone https://github.com/hongleiDC/ros-ros2-debug-engineer.git
cd ros-ros2-debug-engineer
python3 -m pip install -r requirements.txt
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

生成的安装包位于 `dist/skill.zip`。

## 工作流概览

1. 选择 `lite`、`standard` 或 `audited` 执行强度。
2. 运行依赖和发行版预检。
3. 建立 L1 静态项目事实模型。
4. 问题涉及运行时后，再采集受限、只读的运行快照。
5. 建立事实、候选假设、反证和缺失证据。
6. 设计成本最低、区分度最高的实验。
7. 用户授权后修改代码或项目知识。
8. 用构建、测试、bag、仿真或硬件证据验证对应成功判据。

完整工作规范见 [SKILL.md](SKILL.md)。

## 主要工具

| 工具 | 用途 |
|---|---|
| `preflight.py` | 检查 Python 模块、Git 和 ROS CLI |
| `inspect_workspace.py` | 生成只读静态事实模型和能力证据 |
| `collect_runtime_snapshot.py` | 分级收集 ROS 运行图、QoS 和参数证据 |
| `goal_guard.py` | 建立目标契约、动作守卫和 checkpoint |
| `experiment_registry.py` | 登记实验、计算指纹、检测重复并记录结果 |
| `init_project_knowledge.py` | 在用户授权后初始化项目知识库 |
| `validate_knowledge.py` | 使用 JSON Schema 验证知识记录 |
| `update_knowledge.py` | 带锁、恢复日志和回滚地更新事实 |
| `register_reasoning_knowledge.py` | 登记 FORM、MAP、REAS 和 AUD 记录 |
| `logic_audit.py` | 审计公式版本、变量语义、单位、frame 和推理链 |
| `package_skill.py` | 校验 Skill 并生成 `skill.zip` |

## 静态事实模型

```bash
python3 scripts/inspect_workspace.py /path/to/workspace --format yaml
```

扫描器将能力区分为：

- `observed`：在源码或配置中找到较强静态证据；
- `candidate`：只找到依赖、通用关键词或弱证据；
- `unknown`：没有足够证据。

`observed` 仍不等于运行时测量。依赖名称或注释不会直接把能力提升为已确认。

## 运行时快照

```bash
python3 scripts/collect_runtime_snapshot.py --ros-version auto --profile basic
python3 scripts/collect_runtime_snapshot.py --ros-version auto --profile communication --detail-limit 20
python3 scripts/collect_runtime_snapshot.py --ros-version auto --profile full --detail-limit 20
```

- `basic`：环境、doctor、node 和 topic 基础图；
- `communication`：增加 service、action 和 topic 端点/QoS 详情；
- `full`：增加 component、lifecycle、node 详情和参数 dump。

输出采用流式有界采集。部分命令成功只表示观察到了部分运行时，不会自动达到 L3。

## 目标、实验与推理知识

复杂任务使用 `goal_guard.py` 保存主目标、成功判据、非目标、约束和里程碑。涉及数学模型或物理变量时，项目知识库可以维护：

- `FORM-*`：公式版本、符号、假设和推导；
- `MAP-*`：公式符号到代码变量、参数和消息字段的映射；
- `REAS-*`：从已知条件到结论的逐步推理；
- `AUD-*`：结构、语义、单位、frame、方向和代码位置审计。

这些记录是可选的长期项目记忆，不会在没有用户授权时自动写入目标仓库。

## 兼容性

- Python 3.10 及以上；
- CI 覆盖 Ubuntu、Windows、Python 3.10 和 3.12；
- 支持 ROS 1 与 ROS 2 项目分析，但命令和 API 必须按目标发行版分流；
- ROS 1 Noetic 已结束官方支持，迁移和 bridge 方案必须明确 EOL 风险；
- Rolling 的新接口不会默认视为稳定发行版通用接口。

具体规则见 [发行版兼容与路由](references/distro_compatibility.md)。

## 安全边界

默认模式是只读 `diagnose`。Skill 不会因为诊断请求自动修改项目、回放 bag、调用控制 service/action、激活控制器或操作真实硬件。请勿在公开 Issue 中提交：

- 设备序列号、证书、密钥或访问令牌；
- 未脱敏的现场日志、地图、点云或客户数据；
- DDS Security keystore、网络拓扑或生产部署凭据。

安全问题请阅读 [SECURITY.md](SECURITY.md)。

## 贡献

欢迎提交问题报告和改进。变更必须保持证据等级、权限边界和跨平台兼容，新增行为需要测试。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 项目结构

```text
.
├── SKILL.md
├── agents/openai.yaml
├── assets/
├── references/
│   └── schemas/
├── scripts/
├── tests/
└── .github/workflows/
```

项目专属 bag、点云、设备信息、标定结果和长期结论不应打包进通用 Skill。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。使用、修改和分发时请遵守许可证中的版权、专利、声明保留和变更标注要求。

## 免责声明

本项目提供工程诊断和开发辅助，不替代真实机器人上的安全评审、领域专家确认或硬件验收。任何控制、运动、标定写入和现场部署都应在隔离环境验证，并由操作者承担最终责任。
