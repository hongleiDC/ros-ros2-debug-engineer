# 核心目标契约与防漂移

## 为什么需要目标契约

长时间调试中，Agent 容易把最初目标逐渐替换成局部目标。例如，原目标是“消除时间戳根因并保持定位精度”，调试中却变成“让节点不崩溃”或“让某一次 bag 能跑完”。局部问题可以处理，但不得静默替换核心目标。

目标不能只存在于聊天上下文。复杂任务开始时，必须创建可反复读取的结构化目标记录。

## 何时必须建立目标

满足任一条件即视为复杂任务：

- 将修改代码、参数、launch、依赖或设备配置；
- 需要超过一个实验或验证步骤；
- 涉及多个 package、节点、传感器或故障层级；
- 预计需要多轮工具调用、长日志分析或交接恢复；
- 用户明确要求修复根因、优化系统或完成一个工程结果。

只读、一次性、单命令查询可以不持久化目标，但仍要在回复中明确主目标。

## 目标记录内容

每个 `GOAL-xxxx` 至少包含：

- 用户原始请求与期望结果；
- 一条不可含糊的 `primary_goal`；
- 可验证的成功判据 `SC-*` 及所需证据；
- 明确的非目标，防止范围膨胀；
- 约束、不变量和停止条件；
- 仓库、分支、commit、dirty 差异指纹和作用范围；
- 里程碑 `M-*`、当前状态、阻塞项和唯一下一步；
- 每次检查点、目标修订和最终完成状态。

## 工作循环

### 1. 开始任务

```bash
python3 scripts/goal_guard.py start /path/to/state GOAL-0001 "Fix IMU timestamp root cause" \
  --workspace /path/to/repository \
  --request "定位并修复 IMU 时间异常" \
  --desired-outcome "长时间运行无时间回退且定位精度不下降" \
  --primary-goal "确认并消除 IMU 时间戳回退的根因，同时保持定位精度" \
  --success "连续 30 分钟无 timestamp rollback::运行日志和计数器" \
  --success "ATE 不高于基线 0.35 m::同一 bag 的轨迹评估报告" \
  --non-goal "不通过关闭时间检查掩盖问题" \
  --constraint "保持现有消息接口兼容" \
  --invariant "TF 方向和单位不得改变" \
  --milestone "建立可复现基线" \
  --milestone "区分传感器、驱动和融合层根因" \
  --milestone "最小修复并完成回归"
```

诊断只读模式下，`state` 应位于 Agent 临时工作区，不得为了目标记录修改用户仓库。用户授权持久化后，可使用 `project_knowledge` 作为 state。

### 2. 每次关键动作前重新锚定

在修改代码、改参数、运行实验、回放 bag、切换假设或扩大范围前调用：

```bash
python3 scripts/goal_guard.py guard /path/to/state \
  --criterion SC-1 \
  --milestone M-2 \
  --action "检查驱动时间戳转换函数" \
  --alignment "该函数直接决定是否产生时间回退" \
  --expected-evidence "代码路径和单元测试能够区分转换错误"
```

没有活动目标、成功判据不存在、里程碑不存在或目标已处于 `drifted` 时，守卫必须拒绝继续。

### 3. 高频检查点

以下时机必须 checkpoint：

- 每完成 2 至 3 组工具调用；
- 每次代码修改前后；
- 每次实验前后；
- 一个假设被否定或连续两次失败；
- 用户纠正方向；
- 即将压缩上下文、交接或恢复任务；
- 发现新的旁支问题。

```bash
python3 scripts/goal_guard.py checkpoint /path/to/state \
  --trigger code_change \
  --criterion SC-1 \
  --milestone M-2 \
  --summary "已确认驱动使用设备时钟，但转换中丢失秒回绕" \
  --evidence "src/driver_time.cpp:118-146" \
  --decision "修复回绕处理，不改变融合层阈值" \
  --next-action "增加回绕单元测试并实现最小补丁" \
  --drift-status aligned
```

检查点输出必须再次显示主目标、当前成功判据、当前里程碑和下一步。旁支问题放入 blocker、backlog 或新的 goal，不得自动接管当前任务。

## 目标漂移规则

- 局部错误、编译失败或新告警不等于主目标改变。
- “让测试通过”不是目标，除非测试本身就是用户要求的最终结果。
- 临时 workaround 必须标记为 workaround，不能宣称完成根因修复。
- 若动作无法说明服务于哪个 `SC-*`，默认停止。
- 若发现原目标不可行，标记 `at_risk` 或 `drifted`，向用户说明，不得自行改写目标。
- 只有用户明确授权才能使用 `goal_guard.py revise --user-authorized` 修改目标契约；修订必须保留旧哈希、原因和授权证据。

## 完成条件

`completed` 不等于“代码已写完”。只有成功判据均为 `met` 或经用户授权 `waived`，并且证据已记录，才能正常完成。未满足条件时只能 `paused`、`cancelled`，或显式说明未完成原因。

## 与实验记录联动

新实验必须绑定活动 `GOAL-*`、至少一个 `SC-*`、当前 `M-*` 和对齐理由。实验记录保存目标契约哈希和主目标快照。目标改变后，旧实验仍保留原目标语义，避免后续错误解释实验结果。
