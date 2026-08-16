# ros-ros2-systems-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-systems-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-systems-engineer/actions/workflows/validate-skill.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-1%20%7C%202-22314E?logo=ros&logoColor=white)
![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)
![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)

面向 ChatGPT 与 Codex 的 ROS 1 / ROS 2 系统架构设计、开发、迁移、调试和运行结果分析 Skill。

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
- bag/算法/标定/性能实验的统一结果保存；
- baseline/candidate 指标比较与正式离线可视化；
- SLAM/LIO/VIO 的 Core Evidence + 假设驱动机制图；
- 高风险任务的可选审计追踪。

## 三种工作模式

### micro

单个编译错误、参数问题、单文件逻辑或概念澄清。

特点：不扫描整个仓库、不加载额外参考文档、不建立复杂记录或结果包。

### standard

跨文件、launch、运行图或复现问题：

```text
最小代码阅读
→ 三个以内关键假设
→ 高信息增益检查
→ 最小修复
→ 验证
```

### architect

用于系统设计和重构。根据规模输出 component、subsystem 或 system 级方案，覆盖数据流、模块边界、接口契约、QoS、TF/时间、并发、生命周期、故障恢复、测试和部署。

## 运行结果闭环

只要任务依赖 bag 回放、轨迹误差、状态估计、标定、性能或 A/B 数值结果，就把一次具体执行视为一个 `RUN-*`，而不是继续向 `reports/` 顶层堆散乱文件。

```text
reports/
└── EXP-0024/
    └── RUN-20260804T153012Z-bag2-1/
        ├── manifest.yaml
        ├── metrics.json
        ├── series/
        ├── plots/
        │   ├── plot_manifest.json
        │   ├── 01_core/
        │   ├── 02_estimator/
        │   ├── 03_matching/
        │   ├── 04_observability/
        │   ├── 05_fusion/
        │   ├── 06_loop_map/
        │   └── 07_runtime/
        ├── logs/
        └── report.md
```

SLAM 的四张图只是最低 Core Evidence，不是上限：Core 一般 4–6 张，每个活动假设再选择 1–3 张机制图；完整 SLAM 验收出现 8–15 张有明确问题的图很正常，但数量不是 KPI。

辅助工具：

```bash
python3 scripts/result_bundle.py init reports EXP-0024 --label bag2-1 --workspace .
python3 scripts/plot_localization_result.py RUN/series/aligned_errors.csv \
  --output-dir RUN/plots/01_core --manifest RUN/plots/plot_manifest.json
python3 scripts/plot_slam_diagnostics.py RUN/series/diagnostics.csv \
  --category estimator --category observability --category matching \
  --output-dir RUN/plots --manifest RUN/plots/plot_manifest.json
python3 scripts/compare_result_metrics.py BASE/metrics.json RUN/metrics.json --output RUN/delta_metrics.json
python3 scripts/result_bundle.py validate RUN --closure
```

原则：机器可读指标 + 足够的原始时间序列 + 少量 Core 图 + 按活动假设选择的机制图。不要用 dashboard、数据库、几十个无问题定义的图替代工程判断。

## audit

仅用于用户明确要求完整追溯、高风险控制/硬件/标定/状态估计，以及正式验收或长期多人协作。此模式才默认启用 GOAL、实验登记、FORM/MAP/REAS/AUD 与长期知识记录。

## 设计原则

- 简单问题简单解决；
- 复杂度必须来自任务，而不是流程；
- 先架构，再代码；
- 先证据，再结论；
- 运行结束不等于实验结束，结果可复核后才闭环；
- 图数不是质量指标，信息增益才是；
- 找到根因或得到明确实验判据后停止扩大范围。

## 验证

```bash
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```
