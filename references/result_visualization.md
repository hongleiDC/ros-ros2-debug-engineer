# 运行结果可视化

## 目标

把运行数据转换成稳定、可重建、可由工程师独立阅读的正式证据。可视化不是 Agent 每次运行后的自由发挥，而是项目设计时固定下来的 Visualization Contract。

## 两类图

- RViz/rqt/实时 topic：运行中探索和局部调试；
- 正式离线图：由 `series/` 和 `metrics.json` 重建，用于报告、A/B、回归和跨会话复核。

不要只凭 RViz 截图宣称精度改善。关键实时观察需要落成规范 series 后再进入正式图。

## 固定 Core + 稳定系统画像

定位/SLAM 有 reference 与逐样本误差时，Core Evidence 通常包括 4–6 个稳定视图：

- `trajectory_xy.png`
- `height_profile.png`（有可靠高度 reference 时）
- `horizontal_error.png`
- `error_components.png`
- `segment_rmse.png`
- `horizontal_error_cdf.png`

这些图回答“整体是否退化、从哪里开始、哪个误差分量主导、是否存在尾部/局部退化”。Core 集合在项目级 profile 中固定，不应每次 RUN 重新讨论。

SLAM/LIO/VIO 的 estimator、matching、observability、fusion、loop/map、runtime 视图同样优先在 `analysis/analysis_profile.yaml` 中按系统架构固定启用，而不是由 Agent 每次选择。

## Figure Budget 的正确用法

“4–6 Core、完整 SLAM 常见 8–15 张”只是设计 profile 时的复杂度检查，不是每个 RUN 的临时预算，也不是 KPI。

如果一个长期 profile 需要 30 张图才能理解，优先检查是否：

- failure mode 没有被分层；
- 一个图没有明确 question；
- 同义 telemetry 重复；
- 图承担了本应由 normalized metric 完成的判断。

反过来，如果 10–15 张图覆盖系统不同关键层并形成稳定阅读路径，不要为了“少图”删掉必要证据。

## 项目级 Analysis Profile

系统设计阶段固化：

```yaml
sections:
  - id: overall
    groups: [core]
    required: true
  - id: estimator
    groups: [estimator]
    required: true
  - id: matching
    groups: [matching]
    required: true
  - id: observability
    groups: [observability]
    required: true
  - id: fusion
    groups: [fusion]
    required: false
  - id: runtime
    groups: [runtime]
    required: true
```

每个 section 还应定义 `question` 和 `guidance`。这样人打开 static report 时知道先看什么、图回答什么，而不需要 AI 解释文件名。

## A/B 规则

baseline/candidate 必须使用：同一 reference、对齐方法、时间窗口、裁剪范围、物理单位、segment 规则、smoothing/sample policy 和关键轴限。

最关键的 A/B 图应把 baseline/candidate 放在同一坐标语义中。若条件不可比，在报告显式标记，不给“提升百分比”结论。

## 数据与坐标规则

- 每个轴标明物理量和单位；
- 时间统一为明确的 relative/epoch 语义；
- 关键因果图尽量共享同一 distance/time 横轴；
- signed error 不取绝对值冒充方向信息；
- smoothing 只能辅助展示，原始数据/unsmoothed metric 必须保留；
- invalid/rejected 样本不能静默删除后当成功样本；
- gate/threshold 存在时与观测量同图；
- 不用不同采样/裁剪制造视觉优势；
- 不截取最好看片段作为唯一正式证据。

## plot_manifest.json

每张正式图至少声明：

```json
{
  "file": "04_observability/directional_information.png",
  "group": "observability",
  "question": "Does longitudinal information loss precede longitudinal error growth?",
  "source": "series/diagnostics.csv"
}
```

`analyze_run.py` 使用 group 按 Analysis Contract 组织静态 HTML。文件名只是存储细节，question 才是阅读入口。

## 特殊研究假设

长期 profile 不应随着每个实验不断扩张。如果一次性研究需要 cost sweep、oracle、特殊 perturbation 等专属图，可放 `plots/08_hypothesis/`，并在 plot manifest 中标注 question/source。

只有当该证据经过多次实验确认成为长期维护需求时，才升级进入 Observation/Visualization Contract。不要因为一次研究就永久增加生产 telemetry。

## 停止规则

- 固定 profile 已覆盖系统的关键 failure layers：停止增加默认图；
- 某次实验已有证据足以做继续/停止决策：停止增加临时 hypothesis 图；
- required evidence 缺失：补数据契约，不通过 Agent 推测绕过；
- 看完固定报告仍无法区分假设：设计一个高信息量实验，而不是把所有内部变量都画出来。
