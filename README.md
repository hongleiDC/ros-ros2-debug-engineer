# ros-ros2-debug-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-1%20%7C%202-22314E?logo=ros&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

面向 ChatGPT 与 Codex 的 ROS 1 / ROS 2 架构设计、开发、迁移和调试 Skill。

v2 的核心目标只有两个：

1. **设计真正可实施的 ROS 系统架构**；
2. **以尽量少的 Token 和最小代码面定位根因**。

它不再把目标契约、实验登记和公式审计作为普通调试的默认流程。重型追溯能力仍然保留，但只在高风险或用户明确要求的 `audit` 模式启用。

## 三种模式

### `debug`：默认快速调试

适用于构建失败、节点启动、topic、QoS、TF、时间戳、参数、lifecycle、executor、性能和算法异常。

工作方式：

```text
最小代码阅读
→ 最多三个活动假设
→ 高信息增益检查
→ 最小补丁
→ 同条件验证
→ 停止
```

普通问题默认只输出：根因、证据、修改、验证、剩余风险。

### `architect`：系统架构设计

适用于从零设计、系统重构、package/node/component 划分、接口和 QoS 设计、TF/时间体系、并发与生命周期设计、多机部署和性能架构。

必须交付具体的：

- 系统边界、数据流、控制流和诊断流；
- package、算法核心、ROS 适配层、node/component 边界；
- topic/service/action/message 接口契约；
- QoS、TF、时间、executor、callback group 和队列设计；
- lifecycle、故障隔离、降级、恢复、可观测性；
- 测试、部署和分阶段实施方案。

### `audit`：按需审计

只用于控制、安全关键硬件、标定、状态估计、正式验收、长期多人协作，或用户明确要求完整追溯的任务。

该模式可以启用：

- GOAL 目标契约；
- 实验登记与去重；
- FORM/MAP/REAS/AUD；
- 公式、变量、单位、frame、时间和证据审计。

## Token 节省策略

- 不默认扫描整个仓库；
- 初始通常只读一个构建文件、一个 launch/配置文件和二至四个核心源码；
- 每轮最多保留三个假设；
- 不重复粘贴背景和工具输出；
- 普通调试不创建知识库记录；
- 找到根因并验证后立即停止扩大范围；
- 只有架构任务才输出完整系统设计。

## 架构能力

架构流程从目标与约束开始，而不是先堆节点：

```text
目标与非目标
→ 数据/控制/配置/诊断流
→ package 与算法/ROS 边界
→ node/component 与故障域
→ 接口契约与 QoS
→ TF 与时间体系
→ 并发、实时性与生命周期
→ 故障恢复与可观测性
→ 测试、部署和演进
```

详细方法见：

- [系统架构设计](references/architecture_design.md)
- [架构模式与取舍](references/architecture_patterns.md)

## 快速调试能力

调试按最早失败层级收敛：

```text
构建
→ launch/参数
→ graph/lifecycle
→ 消息/QoS/DDS
→ TF/时间
→ executor/资源
→ 数据/算法
```

每个命令必须能够确认或排除一个活动假设。详细流程见 [ROS 快速调试](references/fast_debugging.md)。

## 使用示例

### 设计架构

```text
使用 $ros-ros2-debug-engineer 为双激光雷达、IMU 和双天线 GNSS 的 ROS 2 定位系统设计架构。
给出 package/node/component、接口、QoS、TF、时间同步、executor、lifecycle、故障恢复和测试部署方案。
```

### 快速调试

```text
使用 $ros-ros2-debug-engineer 检查为什么发布端和订阅端都存在，但订阅回调没有数据。
限制为三个假设，先做最小区分检查，不建立审计知识库。
```

### 审计关键算法

```text
使用 $ros-ros2-debug-engineer 审计 IMU 时间补偿和外参变换实现。
需要公式、变量、单位、frame、方向、代码位置和回归证据。
```

## 工具

| 工具 | 用途 | 默认使用 |
|---|---|---|
| `preflight.py` | 检查 Python、Git 和 ROS CLI | 调用相关工具前 |
| `inspect_workspace.py` | 生成静态项目模型 | 架构评审或跨 package 问题 |
| `collect_runtime_snapshot.py` | 收集运行图、QoS 和参数 | 运行时证据确有必要时 |
| `goal_guard.py` | 目标契约与关键节点记录 | 仅 audit |
| `experiment_registry.py` | 可重复实验与去重 | 仅 audit/复杂实验 |
| `logic_audit.py` | 公式、变量和推理审计 | 仅 audit |
| `package_skill.py` | 验证并生成 `skill.zip` | 发布前 |

## 验证和打包

```bash
git clone https://github.com/hongleiDC/ros-ros2-debug-engineer.git
cd ros-ros2-debug-engineer
python3 -m pip install -r requirements.txt
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

生成文件：`dist/skill.zip`。

## 安全边界

默认只读。修改、持久化、提交、推送、bag 回放和真实硬件操作必须有用户明确授权。不要把密钥、证书、设备标识、未脱敏现场日志、地图、点云或生产网络信息提交到公开 Issue。

详见 [SECURITY.md](SECURITY.md) 和 [安全与权限](references/safety_and_permissions.md)。

## 许可证

Apache License 2.0，详见 [LICENSE](LICENSE)。
