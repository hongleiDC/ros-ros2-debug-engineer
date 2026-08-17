# ros-ros2-systems-engineer

[![Validate Skill](https://github.com/hongleiDC/ros-ros2-systems-engineer/actions/workflows/validate-skill.yml/badge.svg?branch=main)](https://github.com/hongleiDC/ros-ros2-systems-engineer/actions/workflows/validate-skill.yml)

ROS 1 / ROS 2 系统架构、调试、验证与**可独立分析设计** Skill。

核心定位已经从“Agent 帮你多做实验分析”调整为：**Agent 在设计阶段把系统做成天然可观察、可复核、没有 AI 也能被工程师分析。**

```text
Algorithm Contract
→ Observation Contract
→ Result Contract
→ Visualization Contract
→ Human Analysis Contract
```

对定位、SLAM、LIO、VIO、融合等长期算法项目，推荐一次性初始化项目本地分析能力：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

它会安装：

```text
PROJECT_ROOT/
├── analysis/
│   ├── observation_contract.yaml
│   ├── analysis_profile.yaml
│   └── README.md
└── tools/analysis/
    ├── analyze_run.py
    ├── result_bundle.py
    ├── plot_localization_result.py
    ├── plot_slam_diagnostics.py
    ├── compare_result_metrics.py
    └── requirements.txt
```

系统设计阶段只需把 Observation Contract 和 Analysis Profile 定制正确。之后每次 RUN 使用固定入口：

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
```

生成：

```text
RUN_DIR/report/
├── index.html
└── analysis_summary.json
```

工程师直接打开 `index.html`，按固定顺序阅读：Overall → Estimator → Frontend → Observability → Fusion → Loop/Map → Runtime → Decision。无需 ChatGPT、数据库或 Web 服务。

Result Bundle 仍保存 `manifest.yaml`、`metrics.json`、`series/`、`plots/`、`logs/` 和 `report.md`；静态 report 是其中面向人的正式阅读入口。

设计原则：

- 简单问题简单解决；
- 先设计 failure mode，再设计 observation；
- 观测量的单位、frame、时间语义和解释长期稳定；
- 图由项目契约稳定生成，而不是每次由 Agent 临时发明；
- AI 是结果包的一个消费者，不是唯一分析器；
- `ready_for_human_review` 只表示证据齐全，不代表算法正确；
- 找到足够支持工程决策的证据后停止扩张 telemetry。

验证：

```bash
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```
