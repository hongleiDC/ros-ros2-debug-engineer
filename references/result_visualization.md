# 运行结果可视化

## 目录

- [目标](#目标)
- [正式图与交互图](#正式图与交互图)
- [定位与 SLAM 默认图集](#定位与-slam-默认图集)
- [领域专属图](#领域专属图)
- [A/B 画图规则](#ab-画图规则)
- [坐标轴与数据处理规则](#坐标轴与数据处理规则)
- [报告使用](#报告使用)
- [停止规则](#停止规则)

## 目标

把大 CSV、日志和诊断量压缩成少量能直接支持工程决策的图。不要为了“可视化完整”生成几十张图；每一张图必须回答一个明确问题。

优先静态、离线、可重建的 PNG/SVG/PDF。不要默认引入 dashboard 服务、数据库、Plotly server 或浏览器应用。

## 正式图与交互图

区分两类用途：

- RViz/rqt/实时 topic 图：用于运行中探索、定位 frame、topic、地图和局部异常；
- 正式离线图：从落盘 `series/` 和 `metrics.json` 重建，用于报告、A/B、回归和跨会话复核。

不要只凭 RViz 截图宣称算法精度提高。若实时观察是关键发现，把对应数值或状态落盘，再生成可复核图。

## 定位与 SLAM 默认图集

当有 reference 与 estimate 轨迹以及逐样本误差时，默认生成四张图：

1. `trajectory_xy.png`
   - reference、baseline、candidate 叠加；
   - 使用同一 ENU/map 坐标语义；
   - 保持等比例坐标轴；
   - 只展示真正参与正式评价的对齐后轨迹。

2. `horizontal_error.png`
   - 横轴优先 reference traveled distance；没有可靠距离时使用相对时间；
   - baseline/candidate 使用同一横轴；
   - 用于回答“误差从哪里开始变坏”。

3. `error_components.png`
   - 绘制 signed lateral、longitudinal、vertical error；
   - 保留零线；
   - 用于区分横向、纵向和高度主导问题。

4. `segment_rmse.png`
   - 固定距离或固定时间窗口计算 RMSE/P95；
   - 同一实验族固定窗口大小；
   - 用于避免全程单个 RMSE 掩盖局部退化。

对兼容 `aligned_errors.csv` 字段的结果使用：

```bash
python3 scripts/plot_localization_result.py \
  RUN/series/aligned_errors.csv \
  --output-dir RUN/plots \
  --segment-m 100
```

有 baseline 时：

```bash
python3 scripts/plot_localization_result.py \
  CANDIDATE/series/aligned_errors.csv \
  --baseline-csv BASELINE/series/aligned_errors.csv \
  --label candidate \
  --baseline-label baseline \
  --output-dir CANDIDATE/plots
```

## 领域专属图

只有当实验正在验证一个机制时，再增加一到两张专属图。优先以下形式：

- 强度/扫描匹配：cost vs longitudinal/transverse offset，并标出 accepted minimum、次优 basin 和 reference；
- 可观测性/退化：最小特征值、条件数或有效维数 vs time/distance；
- RTK/GNSS gate：innovation、门限、accept/reject 与 fix/status 同轴；
- 时间同步：offset sweep vs RMSE/score，标出选择的 offset；
- IMU/状态估计：bias、gravity、attitude residual 或 covariance proxy vs time；
- 性能：callback/runtime/CPU/RSS vs time，并叠加目标阈值；
- QoS/通信：message age、drop rate、deadline miss vs time。

不要把一个领域的所有诊断量都画出来。先问“哪一张图能区分当前两个最可能解释”。

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
- 轨迹对齐方法必须和正式指标一致；
- signed error 不取绝对值冒充方向信息；
- smoothing 只用于展示辅助趋势，原始曲线或 unsmoothed 指标必须保留；
- 丢失、invalid、rejected 样本不能静默删除后当作成功样本；需要时单独显示 invalid/rejection 分布；
- 阈值/gate 存在时把阈值画在同一图上；
- 不用双 Y 轴隐藏尺度问题，除非确有必要并明确标注；
- 不截取“最好看”的片段作为唯一正式证据。

## 报告使用

`report.md` 不需要逐图复述。每张正式图只回答一个问题，并在 Evidence 中引用：

- 哪个指标发生变化；
- 变化在什么位置/时间出现；
- 图是否支持当前假设；
- 是否已经足够做继续、停止或回滚决策。

对定位任务，优先给出“全局标量 + 误差随距离 + 分量 + 分段”四层证据，而不是继续添加更多 debug CSV。

## 停止规则

满足以下任一条件时停止扩充图表：

- 当前图已经区分主要假设；
- baseline/candidate 差异的空间或时间结构已经清楚；
- 失败模式已经明确到下一项可执行修改；
- 结果已经表明当前算法方向应暂停或回滚。

如果看完图仍无法做决策，只增加一张最有信息增益的专属图或一个新的区分实验，不一次性增加一整套可视化。
