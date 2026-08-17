# Observation Contract 设计

## 目标

把“以后怎么调试、怎么看结果”前移到系统设计阶段。算法不仅要定义输入输出，还要定义能够解释其失败模式的可观察量，使工程师在没有 AI 辅助时也能根据固定证据自行分析。

## 五层设计链

```text
Algorithm Contract
→ Observation Contract
→ Result Contract
→ Visualization Contract
→ Analysis Contract
```

- Algorithm Contract：算法做什么、输入输出、状态、失败模式。
- Observation Contract：失败发生时必须留下哪些可解释信号。
- Result Contract：这些信号如何落盘、命名、带上 provenance。
- Visualization Contract：哪些字段稳定映射成哪些正式图。
- Analysis Contract：人按什么顺序阅读这些图，并据此转向哪个模块。

AI 只帮助建立和维护这些契约，不应成为运行后分析的唯一消费者。

## Observation Contract 必须回答

每个关键观测量至少定义：

| 字段 | 要求 |
|---|---|
| `signal_id` | 稳定 snake_case 名称 |
| `layer` | core / estimator / matching / observability / fusion / loop / runtime |
| `meaning` | 物理或算法语义，不写“debug value” |
| `unit` | SI 或明确 native scale |
| `frame` | map / odom / base / sensor / route tangent 等 |
| `time_basis` | sample / estimate / receive / publish / relative time |
| `source` | 文件与列，或 topic/message field |
| `sampling` | every frame / event / decimated / window summary |
| `validity` | 有效范围、invalid/rejected 语义 |
| `required` | 是否属于该系统人工诊断的最低证据 |
| `interpretation` | 典型异常如何解释，以及不能单独证明什么 |

示例：

```yaml
scan_match_correction_longitudinal_m:
  layer: matching
  meaning: longitudinal translation correction introduced by lidar update
  unit: m
  frame: vehicle_or_route_tangent
  time_basis: lidar_update
  source:
    file: series/diagnostics.csv
    column: scan_match_correction_longitudinal_m
  sampling: every_lidar_update
  required: true
  interpretation:
    sustained_bias: lidar update may be accumulating directional error
    near_zero_with_growing_pose_error: investigate prediction before frontend
```

## 设计规则

1. 从 failure mode 反推信号，不从“代码里有什么变量”反推图。
2. 优先记录层间边界量，例如 prediction→update correction、innovation→gate decision、map feedback correction，而不是大量内部临时变量。
3. 同一物理量的单位、frame、正负号和时间语义在项目内稳定。
4. 诊断量可由已有日志离线派生时，不为可视化侵入生产核心实时路径。
5. 高频大数组默认落盘到受控 series，不进入日志文本。
6. 未校准 proxy 不命名为 covariance、accuracy、confidence 或 information。
7. 观测量如果无法对应一个明确分析问题，默认不进入长期契约。

## 架构设计时的交付

对状态估计、SLAM、LIO、VIO、融合、控制和复杂优化模块，在 subsystem/system 设计中同时交付 Observation Contract。至少覆盖：

- 外部结果质量；
- prediction/state propagation；
- measurement/update；
- 可观测性或约束质量；
- 外部融合；
- map/loop feedback（若存在）；
- runtime/resource（若影响成功判据）。

项目可以使用：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

生成项目级模板，然后只在系统设计阶段定制一次 `analysis/observation_contract.yaml`。后续 RUN 不应重新发明字段语义。
