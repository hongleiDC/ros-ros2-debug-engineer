# 运行结果可视化

## 目录

- [目标](#目标)
- [正式图与交互图](#正式图与交互图)
- [Figure Budget 而不是 Figure Limit](#figure-budget-而不是-figure-limit)
- [定位与 SLAM Core Evidence](#定位与-slam-core-evidence)
- [机制诊断图](#机制诊断图)
- [A/B 画图规则](#ab-画图规则)
- [坐标轴与数据处理规则](#坐标轴与数据处理规则)
- [图表索引](#图表索引)
- [报告使用](#报告使用)
- [停止规则](#停止规则)

## 目标

把大 CSV、日志和诊断量压缩成能直接支持工程决策的图。不要用固定图数代替工程判断；每一张图都必须回答一个明确问题。

优先静态、离线、可重建的 PNG/SVG/PDF。不要默认引入 dashboard 服务、数据库、Plotly server 或浏览器应用。

## 正式图与交互图

区分两类用途：

- RViz/rqt/实时 topic 图：用于运行中探索、定位 frame、topic、地图和局部异常；
- 正式离线图：从落盘 `series/` 和 `metrics.json` 重建，用于报告、A/B、回归和跨会话复核。

不要只凭 RViz 截图宣称算法精度提高。若实时观察是关键发现，把对应数值或状态落盘，再生成可复核图。

## Figure Budget 而不是 Figure Limit

四张图只是定位类实验的最低 Core Evidence，不是完整 SLAM 的上限。使用以下预算控制复杂度：

```text
Core Evidence             4–6
+ 每个活动假设             1–3
+ 性能证据（若相关）       1–2
```

活动假设仍遵守 Skill 的“最多三个”活动假设规则。因此：

- 简单 A/B：常见 5–8 张；
- 单一 SLAM 机制根因分析：常见 8–12 张；
- 完整系统验收：常见 10–15 张。

这些只是经验范围，不是硬上限或 KPI。禁止为了达到数量补图，也禁止因为超过四张就删除能区分机制的证据。

SLAM/LIO/VIO/融合系统读取 [SLAM 结果画像](slam_visualization_profile.md)，按当前问题选择 estimator、matching、observability、fusion、runtime、loop/map 等类别。

## 定位与 SLAM Core Evidence

有 reference 与 estimate 轨迹以及逐样本误差时，Core Evidence 默认 4–6 张。`plot_localization_result.py` 在字段可用时生成：

1. `trajectory_xy.png`
   - reference、baseline、candidate 叠加；
   - 使用同一 ENU/map 坐标语义；
   - 保持等比例坐标轴；
   - 只展示真正参与正式评价的对齐后轨迹。

2. `height_profile.png`
   - reference 与 estimate 的高度随距离变化；
   - 用于区分平面漂移和垂向/坡度问题；
   - 没有可靠高度 reference 时不强制生成。

3. `horizontal_error.png`
   - 横轴优先 reference traveled distance；没有可靠距离时使用相对时间；
   - baseline/candidate 使用同一横轴；
   - 用于回答“误差从哪里开始变坏”。

4. `error_components.png`
   - 绘制 signed lateral、longitudinal、vertical error；
   - 保留零线；
   - 用于区分横向、纵向和高度主导问题。

5. `segment_rmse.png`
   - 固定距离或固定时间窗口计算 RMSE/P95；
   - 同一实验族固定窗口大小；
   - 用于避免全程单个 RMSE 掩盖局部退化。

6. `horizontal_error_cdf.png`
   - 展示误差分布而不是只看均值/RMSE；
   - baseline/candidate 使用同一坐标定义；
   - 用于检查“平均变好但尾部变坏”。

对兼容 `aligned_errors.csv` 字段的结果使用：

```bash
python3 scripts/plot_localization_result.py \
  RUN/series/aligned_errors.csv \
  --output-dir RUN/plots/01_core \
  --manifest RUN/plots/plot_manifest.json \
  --segment-m 100
```

有 baseline 时：

```bash
python3 scripts/plot_localization_result.py \
  CANDIDATE/series/aligned_errors.csv \
  --baseline-csv BASELINE/series/aligned_errors.csv \
  --label candidate \
  --baseline-label baseline \
  --output-dir CANDIDATE/plots/01_core \
  --manifest CANDIDATE/plots/plot_manifest.json
```

## 机制诊断图

Core Evidence 回答“整体好不好、哪里开始坏”；机制图回答“为什么”。不要固定只增加一两张，也不要把所有内部变量都画出来。

对每个活动假设选择 1–3 张能区分该假设与竞争解释的图。例如：

- 强度/扫描匹配：cost vs longitudinal/transverse offset、scan correction、residual、correspondence count；
- 可观测性/退化：方向信息量、最小特征值、条件数、degeneracy flag；
- RTK/GNSS 融合：innovation 与 gate、accept/reject、fix/status、更新修正量；
- 时间同步：offset sweep vs RMSE/score，并标出选择的 offset；
- IMU/状态估计：velocity error、gyro/accel bias、gravity、attitude residual、真实 covariance 或明确命名的 proxy；
- 性能：frame/runtime 分阶段耗时、CPU、RSS、backlog/real-time factor；
- loop/map：loop candidate/accepted、pose-graph correction、revisit residual、map/submap consistency。

对规范化 `series/diagnostics.csv` 可按需要调用：

```bash
python3 scripts/plot_slam_diagnostics.py \
  RUN/series/diagnostics.csv \
  --category estimator \
  --category observability \
  --category matching \
  --output-dir RUN/plots \
  --manifest RUN/plots/plot_manifest.json
```

不传 `--category` 时脚本绘制所有能从已知规范字段识别出的类别，适合完整验收；根因分析应显式选择与当前活动假设相关的类别。

## A/B 画图规则

比较 baseline/candidate 时：

- 使用同一个 reference、对齐方法、时间窗口和裁剪范围；
- 使用相同坐标轴单位与轴限；若自动轴限差异会误导，则显式固定；
- baseline 与 candidate 必须同时出现在最关键的比较图上；
- 不通过不同 smoothing、不同 sample rate 或不同 segment 大小制造视觉优势；
- 若两次运行条件不可比，在图标题或 report 明确标记，不给“提升百分比”结论。

A/B 的机器可读标量差异由 `compare_result_metrics.py` 生成，图用于解释差异发生在哪里和以什么形态发生。

## 坐标轴与数据处理规则

- 每个轴标明物理量和单位；
- 时间统一使用相对时间或明确 epoch；
- 同一根因分析优先让关键图共享 distance/time 横轴，便于读取因果顺序；
- 轨迹对齐方法必须和正式指标一致；
- signed error 不取绝对值冒充方向信息；
- smoothing 只用于展示辅助趋势，原始曲线或 unsmoothed 指标必须保留；
- 丢失、invalid、rejected 样本不能静默删除后当作成功样本；需要时单独显示 invalid/rejection 分布；
- 阈值/gate 存在时把阈值画在同一图上；
- 不用双 Y 轴隐藏尺度问题，除非确有必要并明确标注；
- 不截取“最好看”的片段作为唯一正式证据。

## 图表索引

当图超过六张或使用多个类别时维护 `plots/plot_manifest.json`。每个条目至少包含：

```json
{
  "file": "03_observability/directional_information.png",
  "group": "observability",
  "question": "纵向信息量下降是否与纵向误差增长同时发生？",
  "source": "series/diagnostics.csv"
}
```

索引的作用是把“图片文件”提升成“证据问题”。不要要求人按文件名猜图的用途。

推荐目录：

```text
plots/
├── plot_manifest.json
├── 01_core/
├── 02_estimator/
├── 03_matching/
├── 04_observability/
├── 05_fusion/
├── 06_loop_map/
├── 07_runtime/
└── 08_hypothesis/
```

不要求所有目录都存在，只创建实际使用的类别。

## 报告使用

`report.md` 不需要逐图复述。每张正式图只回答一个问题，并在 Evidence 中引用：

- 哪个指标发生变化；
- 变化在什么位置/时间出现；
- 哪一层先发生异常：prediction、measurement update、map/loop feedback 还是 runtime；
- 图是否支持当前假设；
- 是否已经足够做继续、停止或回滚决策。

对定位/SLAM 任务，先用 Core Evidence 定位现象，再用机制图建立最短因果链。不要把“更多图”本身当成更高质量分析。

## 停止规则

满足以下任一条件时停止扩充图表：

- 当前图已经区分主要假设；
- baseline/candidate 差异的空间或时间结构已经清楚；
- 失败模式已经明确到下一项可执行修改；
- 结果已经表明当前算法方向应暂停或回滚。

如果看完图仍无法做决策，只增加一个最有信息增益的类别、1–3 张机制图或一个新的区分实验；不要一次性把所有可记录变量都画出来。
