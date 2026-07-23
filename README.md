# ros-ros2-debug-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-1%20%7C%202-22314E?logo=ros&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

面向 ChatGPT 与 Codex 的 ROS 1 / ROS 2 架构设计、开发、迁移和调试 Skill。

v2.1 坚持两个优先级：

1. **架构设计必须具体、量化、可实施**；
2. **简单问题必须走最短路径，避免无意义 Token 消耗**。

默认关闭隐式调用。建议显式使用 `$ros-ros2-debug-engineer`，避免普通 ROS 概念问答自动加载完整 Skill。

## 调试模式

### `micro`

单个编译错误、明显参数问题、单文件逻辑或概念澄清。直接解决，不加载参考文档，不建立假设表和知识库。

### `standard`

跨文件、launch、运行图或复现问题。读取 [快速调试](references/fast_debugging.md)，最多保留三个活动假设，用最小检查定位根因。

### `domain`

证据已经指向 QoS、TF、时间、rosbag、SLAM 等特定领域。在 `standard` 基础上最多再加载一个领域参考文件。

默认交付：根因、证据、修改、验证、剩余风险。

## 架构模式

根据问题规模选择：

| 规模 | 适用范围 | 默认交付 |
|---|---|---|
| `component` | 单节点、组件或算法封装 | 职责、接口、线程、错误处理、测试 |
| `subsystem` | 定位、感知、建图、控制 | 结构、数据流、接口、QoS、TF/时间、恢复 |
| `system` | 整机、多机或分布式系统 | 资源预算、部署、安全、运维、迁移和演进 |

架构设计包括：

- package、算法核心、ROS 适配层、node/component 边界；
- topic/service/action 接口和唯一所有权；
- QoS、TF、时间、executor、callback group 和 lifecycle；
- 数据大小、频率、带宽和关键路径延迟预算；
- 故障隔离、降级、恢复和可观测性；
- Greenfield 实施或 Brownfield 分阶段迁移与回滚。

详细方法：

- [系统架构设计](references/architecture_design.md)
- [架构决策模式](references/architecture_patterns.md)

## 审计模式

`audit` 由风险和请求动作触发，不由“标定、状态估计”等领域名称自动触发。

普通解释、只读检查和局部公式核对仍使用 `debug`。只有用户明确要求完整追溯，或准备修改/部署高风险逻辑且普通验证不足时，才启用 GOAL、实验登记、FORM/MAP/REAS/AUD 和逻辑审计。

## Token 策略

- 不默认扫描整个仓库；
- `micro` 不加载参考文件；
- 初始通常只读一个构建文件、一个配置文件和二至四个核心源码；
- 每轮最多三个假设，每个命令必须有信息增益；
- 不重复背景、目标和工具输出；
- 最多询问一个会改变方案的关键问题；
- 找到根因或完成架构决策后立即停止。

## 使用示例

### 简单问题

```text
使用 $ros-ros2-debug-engineer 解释这个 CMake 错误并给出最小修复。按 micro 调试，不扫描整个仓库。
```

### 子系统架构

```text
使用 $ros-ros2-debug-engineer 为 LiDAR-IMU-GNSS 定位子系统设计架构。
给出数据流、package/node/component、接口、QoS、TF/时间、延迟预算、故障恢复和迁移计划。
```

### 高风险审计

```text
使用 $ros-ros2-debug-engineer 审计即将部署的控制器时间补偿逻辑。
需要公式、变量、单位、frame、代码位置、实验和回归证据。
```

## 工具

| 工具 | 用途 | 默认使用 |
|---|---|---|
| `preflight.py` | 检查 Python、Git 和 ROS CLI | 调用相关工具前 |
| `inspect_workspace.py` | 静态项目模型 | 架构评审或跨 package 问题 |
| `collect_runtime_snapshot.py` | 运行图、QoS 和参数证据 | 静态证据不足时 |
| `goal_guard.py` | 目标契约 | 仅 audit |
| `experiment_registry.py` | 实验登记与去重 | 仅 audit/复杂实验 |
| `logic_audit.py` | 公式、变量和推理审计 | 仅 audit |
| `package_skill.py` | 校验并生成 `skill.zip` | 发布前 |

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

默认只读。修改、持久化、提交、推送、bag 回放和真实硬件操作必须有用户明确授权。不要提交密钥、设备标识或未脱敏的现场数据。

详见 [SECURITY.md](SECURITY.md) 和 [安全与权限](references/safety_and_permissions.md)。

## 许可证

Apache License 2.0，详见 [LICENSE](LICENSE)。
