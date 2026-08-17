# 运行结果管理与证据包

## 核心原则

把“运行结束”和“实验结束”分开。进程退出只说明一次执行结束；只有输入可追溯、指标规范化、必要图形可重建、人工阅读入口存在并且结论可由保存证据复核后，才把该 RUN 作为正式实验结果使用。

Result Bundle 的首要消费者是工程师和测试流程，AI 只是可选消费者。不要把“以后让 Agent 读日志”当成结果设计。

## EXP 与 RUN

- `EXP-*`：为什么做、假设、主要变量、成功/失败判据。
- `RUN-*`：一次具体执行使用的 commit、数据、配置、命令和证据。

一个 EXP 可以包含多个 baseline/candidate、bag、重复样本。不同配置的执行不能混在同一个 RUN。

## Result Bundle 契约

```text
RUN-.../
├── manifest.yaml
├── metrics.json
├── delta_metrics.json          # A/B 时
├── series/
│   ├── aligned_errors.csv
│   └── diagnostics.csv
├── plots/
│   ├── plot_manifest.json
│   ├── 01_core/
│   ├── 02_estimator/
│   ├── 03_matching/
│   ├── 04_observability/
│   ├── 05_fusion/
│   ├── 06_loop_map/
│   ├── 07_runtime/
│   └── 08_hypothesis/
├── report/
│   ├── index.html
│   └── analysis_summary.json
├── logs/
└── report.md
```

其中 `report/index.html` 是面向人的稳定阅读入口；`analysis_summary.json` 记录 required evidence 是否齐全；`report.md` 记录最终工程决策与剩余风险。

## manifest.yaml

至少记录：schema_version、experiment_id、run_id、created time、Git workspace/branch/commit/dirty、dataset/config 路径与 SHA-256、完整命令、可选 baseline_run、status/verdict、artifact 路径。

条件实质变化时新建 RUN，不覆盖旧 manifest 伪装成同一次执行。

## metrics.json

所有用于 pass/fail、继续/停止或 A/B 的标量必须规范化写入 `metrics.json`。大数组放 `series/`。指标名称、单位和 `direction: lower|higher` 在实验族内稳定。

不要把未经校准的 proxy 命名成 covariance、accuracy、confidence 或 information。

## series / plots / logs / report

`series/` 保存复现图和进一步分析所需的最小时间序列。CSV 必须有字段名，frame、单位、时间/距离语义可确定。SLAM 项目的稳定字段由 [Observation Contract 设计](observation_design.md) 固化，而不是每次运行临时决定。

`plots/` 保存从落盘 series/metrics 重建的正式离线图。`plot_manifest.json` 记录 `file/group/question/source`。图的默认集合由项目 `analysis/analysis_profile.yaml` 决定；`08_hypothesis/` 只用于一次性研究假设，不反向污染长期契约。

`logs/` 保存 stdout/stderr、ROS/DDS 日志和必要 profiler 输出。大 bag 默认在 manifest 引用和 hash，不重复复制。

`report/index.html` 由项目级 `analyze_run.py` 生成，无 AI、无数据库、无服务也能浏览。阅读顺序由 [Human Analysis Contract](analysis_contract.md) 固化。

## 推荐项目级流程

在系统设计阶段一次性初始化：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

定制：

```text
analysis/observation_contract.yaml
analysis/analysis_profile.yaml
```

之后每次实验：

```text
create RUN
→ execute system
→ normalize metrics/series
→ analyze_run.py RUN_DIR --strict
→ human opens report/index.html
→ human records Decision in report.md
→ validate --closure --human-analysis
```

运行后不要求 Agent 再发明分析流程。

## A/B 比较

只有同一数据/切片、时间基准、frame、轨迹对齐、误差定义、segment 规则和主要变量控制一致时，才宣称 baseline/candidate 可比较。

```bash
python3 tools/analysis/compare_result_metrics.py \
  BASELINE_RUN/metrics.json \
  CANDIDATE_RUN/metrics.json \
  --output CANDIDATE_RUN/delta_metrics.json
```

视觉比较同样必须同轴、同裁剪、同 smoothing/sample policy。

## 关闭判据

通用结构闭环：

```bash
python3 tools/analysis/result_bundle.py validate RUN_DIR --closure
```

若项目声明需要人工独立分析，再使用：

```bash
python3 tools/analysis/result_bundle.py validate RUN_DIR --closure --human-analysis
```

后者额外要求 `report/index.html`、`analysis_summary.json` 且 `ready_for_human_review: true`。

这仍然只表示**材料和入口齐全**，不表示算法正确、根因已证明或 candidate 可上线。最终 verdict 必须来自工程判据和人工/测试结论。

## 存储与清理

- 原始大 bag 默认引用+hash；
- 图必须可由保存的 series 和脚本重建；
- 临时 CSV/日志放 RUN 内受控目录，不散落 `reports/` 顶层；
- 不提交 cache、core dump、重复二进制，除非其本身是必要故障证据；
- 不把仓库扩张成数据湖或通用实验平台。
