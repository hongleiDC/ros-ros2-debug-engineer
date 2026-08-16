# 运行结果管理与证据包

## 目录

- [核心原则](#核心原则)
- [何时启用](#何时启用)
- [EXP 与 RUN 分层](#exp-与-run-分层)
- [Result Bundle 契约](#result-bundle-契约)
- [manifestyaml](#manifestyaml)
- [metricsjson](#metricsjson)
- [series-plots-logs 与 report](#series-plots-logs-与-report)
- [执行流程](#执行流程)
- [A/B 比较](#ab-比较)
- [关闭判据](#关闭判据)
- [存储与清理](#存储与清理)

## 核心原则

把“运行结束”和“实验结束”分开。进程退出只说明一次执行结束；只有关键输入可追溯、指标被规范化、必要图形已生成、结论可由保存的证据复核后，才把这次运行作为正式实验结论使用。

不要建设数据库、Web dashboard 或通用实验平台来解决普通 ROS 研究结果管理。优先使用目录、YAML/JSON、CSV 和静态图，保持本地可读、Git 友好和低依赖。

## 何时启用

对以下任务启用 Result Bundle：

- rosbag / rosbag2 回放后的算法验证；
- 定位、SLAM、状态估计、融合、标定精度比较；
- baseline/candidate A/B 实验；
- 性能、时延、抖动、CPU、内存或网络曲线；
- 需要跨会话、跨机器或多人复核的运行结果；
- audit 中依赖连续数值证据的实验。

不要对以下任务强制创建 Result Bundle：

- `micro` 编译错误、参数拼写或单文件逻辑修复；
- 只需确认节点能否启动的短 smoke test；
- 没有连续数值输出且不需要持久复核的普通调试。

## EXP 与 RUN 分层

使用两个不同对象，禁止混用：

- `EXP-*`：描述为什么做、假设、唯一主要变量、成功判据和实验关系。
- `RUN-*`：描述某一次具体执行实际用了什么 commit、数据、配置、命令，并保存这次执行产生的证据。

一个 EXP 可以有多个 RUN，例如 Bag-1、Bag-2-1、Bag-2-2、baseline、candidate、repeat-1。不要为了每个 bag 都复制一个新的实验定义，也不要把多个不同配置的执行混在同一个 RUN 目录。

## Result Bundle 契约

默认目录：

```text
reports/
└── EXP-0024/
    └── RUN-20260804T153012Z-bag2-1-shadow-on/
        ├── manifest.yaml
        ├── metrics.json
        ├── delta_metrics.json        # 仅 A/B 比较时
        ├── series/
        │   ├── trajectory.csv
        │   ├── errors.csv
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
        ├── logs/
        │   ├── stdout.log
        │   └── stderr.log
        └── report.md
```

不要求所有 plots 子目录存在；只创建实际需要的类别。使用 `scripts/result_bundle.py init` 创建骨架，避免每次实验重新发明目录结构。

不要把 `temp_*.csv`、`eval.stdout`、bag、副本 YAML 或随机截图散落在 `reports/` 顶层。顶层只用于 EXP/RUN 组织和少量稳定索引。

## manifest.yaml

把 manifest 当成 RUN 的不可变身份和 provenance 入口。至少记录：

- `schema_version`、`experiment_id`、`run_id`；
- 创建时间；
- Git workspace、branch、commit、dirty 状态；
- 数据集/bag 路径、大小和 SHA-256；
- 配置/参数文件路径和 SHA-256；
- 完整执行命令；
- 可选 `baseline_run`；
- `status` 与 `verdict`；
- 标准 artifact 路径。

条件发生实质变化时创建新的 RUN，不修改旧 manifest 伪装成同一次执行。允许补全运行结束时间、status、verdict 和 artifact 索引，但不要覆盖原始输入身份。

## metrics.json

把所有用于 pass/fail、继续/停止或 A/B 判定的标量统一写入 `metrics.json`。不要要求人从 CSV 或日志中再次手工提取最终数字。

推荐格式：

```json
{
  "schema_version": 1,
  "run_id": "RUN-20260804T153012Z-bag2-1",
  "metrics": {
    "horizontal_rmse_m": {
      "value": 0.31,
      "unit": "m",
      "direction": "lower"
    },
    "runtime_s": {
      "value": 1412.0,
      "unit": "s",
      "direction": "lower"
    }
  }
}
```

规则：

- 指标名使用稳定 snake_case，并把量纲放进名称或 `unit`；
- 需要比较时提供 `direction: lower|higher`；
- 不把大数组塞进 JSON；大数组写入 `series/`；
- 不把未经校准的 proxy 命名成 covariance、accuracy 或 confidence；名称必须反映真实语义；
- 正式结论引用 `metrics.json` 中的字段，而不是聊天中的临时数值。

## series、plots、logs 与 report

`series/` 保存复现图表和进一步分析所需的最小时间序列、轨迹和诊断数据。CSV 首行必须有字段名；时间、frame、距离、单位和坐标系语义必须可确定。对 SLAM 机制诊断优先把已有运行日志离线转换为规范化 `diagnostics.csv`，不要为了画图把 research-only telemetry 直接塞进生产核心路径。

`plots/` 保存由已落盘 series/metrics 重新生成的正式离线图。不要把 RViz 截图作为唯一正式证据；RViz 适合交互诊断，离线图适合复核和 A/B。超过六张图或使用多个类别时维护 `plot_manifest.json`，记录图文件、group、question 和 source。

`logs/` 保存 stdout、stderr、ROS/DDS 日志和必要 profiler 输出。大型原始 bag 不默认复制进 RUN；在 manifest 中记录原路径和 hash，只有用户要求归档时才复制。

`report.md` 只写决策层内容，默认结构：

```text
# EXP / RUN
## Decision
## Evidence
## Remaining risk
```

先写继续、停止、回滚、inconclusive 或需要下一项证据，再引用指标和图。不要把日志全文复制到报告。

## 执行流程

对需要持久化的数值实验按以下顺序执行：

1. 在实验登记中确认 `EXP-*`、假设、基线、主要变量和指标。
2. 在长时间运行前创建 `RUN-*`：

```bash
python3 scripts/result_bundle.py init \
  reports EXP-0024 \
  --label bag2-1-shadow-on \
  --workspace . \
  --dataset-file /data/Bag-2-1.bag \
  --config-file config/rail_lio.yaml \
  --command "roslaunch rail_lio replay.launch bag:=/data/Bag-2-1.bag"
```

3. 把 stdout/stderr 和运行输出直接定向到该 RUN 的 `logs/`、`series/` 或受控 artifact 目录。
4. 运行结束后计算标准指标，写 `metrics.json`。
5. 读取 [结果可视化](result_visualization.md)；SLAM/LIO/VIO/融合读取 [SLAM 结果画像](slam_visualization_profile.md)，从已保存数据生成 Core + 假设驱动图。
6. 如果有 baseline，生成 `delta_metrics.json` 并使用同轴 A/B 图。
7. 图超过六张时维护 `plots/plot_manifest.json`，完成 `report.md`。
8. 对正式实验执行：

```bash
python3 scripts/result_bundle.py validate RUN_DIR --closure
```

9. 只把关键指标和整个 RUN bundle 路径登记回 EXP；不要把几十个 CSV 逐个复制进实验记录。

## A/B 比较

只有满足以下条件时才宣称 baseline/candidate 差异有效：

- 使用同一数据集或明确可比较的数据切片；
- 使用同一时间基准、坐标系、轨迹对齐和误差定义；
- 除唯一主要变量外，其他配置保持一致或明确登记；
- 指标单位一致；
- 图使用相同轴定义和相同裁剪范围。

使用：

```bash
python3 scripts/compare_result_metrics.py \
  BASELINE_RUN/metrics.json \
  CANDIDATE_RUN/metrics.json \
  --output CANDIDATE_RUN/delta_metrics.json
```

`relative_percent` 只表达相对变化，不自动等于统计显著或工程有效。随机性明显时按实验管理规则做独立重复样本。

## 关闭判据

对于算法比较、状态估计、标定、性能或正式验收，如果可视化适用，则一个 RUN 在以下条件满足前不能作为 `decided/verified` 证据：

- manifest 已标记 `status: completed`；
- verdict 不再是 `pending`；
- 至少一个主要判据已经写入 `metrics.json`；
- 正式离线图已经覆盖当前任务所需的证据层；定位/SLAM 按结果画像检查，不以“一张图存在”作为领域闭环；
- 图超过六张时存在可读的 `plot_manifest.json`；
- `report.md` 已经给出决策和剩余风险，没有 TODO；
- 结果能追溯到 commit、数据和配置。

`result_bundle.py validate --closure` 只检查通用结构最小条件；领域证据完整性仍由本 Skill 的结果画像判断。不要把脚本结构校验成功误写成“SLAM 结果已经充分验证”。

如果任务本身没有适用的图形或连续数值证据，在报告中写明例外，不要为了满足流程制造无意义图。

当已有图和指标已经足以支持继续/停止决策时停止增加诊断变量。可视化的目的之一就是压缩分支，而不是创造更多分支。

## 存储与清理

- 原始大 bag 默认只引用和 hash，不重复复制；
- 生成图必须可由 `series/` 和脚本重建；
- 临时文件放入 RUN 内的临时子目录或系统临时目录，实验结束后清理；
- 不提交 `__pycache__`、临时 ROS home、core dump 或重复二进制，除非它们本身是必要故障证据；
- 大型 CSV 如果必须长期保存，记录大小和 SHA-256，并考虑外部 artifact storage，而不是把仓库变成数据湖。
