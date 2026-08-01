# ros-ros2-systems-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-debug-engineer/actions/workflows/validate-skill.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-1%20%7C%202-22314E?logo=ros&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)

面向 ChatGPT 与 Codex 的 ROS 1 / ROS 2 系统架构设计、开发、迁移和调试 Skill。

当前定位：**ROS/ROS 2 系统工程师**，而不是单纯调试工具。

使用：

```text
$ros-ros2-systems-engineer
```

它提供：

- ROS 系统架构设计；
- package/node/component 划分；
- topic/service/action 接口设计；
- QoS、TF、时间同步、executor、lifecycle 设计；
- ROS 运行时故障定位；
- 低 Token、高信息增益调试流程；
- 高风险任务的可选审计追踪。

## 三种工作模式

### micro

单个编译错误、参数问题、单文件逻辑或概念澄清。

特点：

- 不扫描整个仓库；
- 不加载额外参考文档；
- 不建立复杂记录。

### standard

跨文件、launch、运行图或复现问题。

流程：

```text
最小代码阅读
→ 三个以内关键假设
→ 高信息增益检查
→ 最小修复
→ 验证
```

### architect

用于系统设计和重构。

根据规模输出：

- component：单组件设计；
- subsystem：定位、感知、建图、控制等子系统；
- system：整机、多机或分布式系统。

架构重点：

- 数据流；
- 模块边界；
- 接口契约；
- QoS；
- TF 与时间体系；
- 并发和生命周期；
- 故障恢复；
- 测试和部署。

## audit

仅用于：

- 用户明确要求完整追溯；
- 高风险控制、硬件、标定、状态估计；
- 正式验收或长期多人协作。

此模式才启用：

- GOAL；
- 实验登记；
- FORM/MAP/REAS/AUD；
- 公式和变量追踪。

## 设计原则

- 简单问题简单解决；
- 复杂度必须来自任务，而不是流程；
- 先架构，再代码；
- 先证据，再结论；
- 找到根因后停止扩大范围。

## 验证

```bash
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```
