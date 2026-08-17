# Human Analysis Contract

## 目标

让运行结果脱离 AI 也能被工程师独立阅读。项目必须提供固定阅读顺序、问题、证据入口和下一步，而不是只生成一堆图片。

## 默认阅读顺序

```text
1 Overall
→ 2 Estimator / prediction
→ 3 Frontend / matching
→ 4 Observability
→ 5 External fusion
→ 6 Loop / map
→ 7 Runtime
→ Decision
```

不是每个系统都启用所有层。纯 localization 可以没有 loop；没有 GNSS/RTK 的系统可以禁用 fusion。系统设计时在 `analysis/analysis_profile.yaml` 固化启用层和 required 层。

## 人工判断树

### 1. Overall

先回答：系统最终是否退化？从哪里开始？主要是位置、姿态、高度、地图还是 runtime？

如果 Core Evidence 已经满足明确回滚条件，允许直接停止，不强制深入内部状态。

### 2. Estimator / prediction

如果误差增长前 velocity、bias、prediction state 或 propagation residual 已先异常，优先调查 IMU、时间、运动模型、状态传播和初始化；不要先调 matching 参数。

### 3. Frontend / matching

如果 prediction 正常，而 measurement update 后 correction、residual、support 或 convergence 首先异常，转向 correspondence、cost、feature、scan-to-map/visual matching。

### 4. Observability

如果 directional information、Hessian spectrum、condition number 或 degeneracy 与误差增长同步或更早退化，判断几何/运动约束是否不足。不要只凭一个小特征值直接宣称根因。

### 5. External fusion

分别检查 measurement quality/timing、innovation、gate、accept/reject 和 estimator correction，避免把传感器坏数据与融合器响应混为一层。

### 6. Loop / map

对真正有 pose graph、loop closure、submap 或 recursive map feedback 的系统，检查 correction、revisit consistency 和 map consistency。没有这些机制时不生成该层。

### 7. Runtime

精度结论必须和处理时延、阶段耗时、CPU/RSS、queue/backlog 或 realtime factor 一起考虑。不能以不可实时的 candidate 替代 baseline 而不说明代价。

## 静态报告契约

项目级工具应提供：

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
```

生成：

```text
RUN_DIR/report/
├── index.html
└── analysis_summary.json
```

`index.html` 必须：

- 无服务、无数据库、无 AI 即可浏览；
- 按上述阅读顺序组织，而不是按文件生成顺序；
- 显示 normalized metrics；
- 显示 Observation Contract 覆盖情况；
- 每张图写明它回答的问题；
- 缺失证据显式显示，不静默跳过 required 层。

`analysis_summary.json` 用于机器校验人工分析是否具备最低材料，不用于自动代替工程师作最终根因结论。

## 分析完成的含义

`ready_for_human_review: true` 只表示：

- required observation signals 已存在；
- required analysis sections 有可阅读证据；
- 静态报告已生成。

它不表示算法正确，也不表示 candidate 应上线。最终 Decision 仍由人、测试或明确验收判据给出。
