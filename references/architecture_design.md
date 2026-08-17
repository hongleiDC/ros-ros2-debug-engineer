# ROS 系统架构设计

## 目标

设计可实施、可测试、可运维、可演进且**可独立分析**的 ROS 系统。先选择设计规模，避免用整机流程回答一个组件问题。

## 目录

- [一、选择规模](#一选择规模)
- [二、建立约束](#二建立约束)
- [三、设计数据、控制、配置与证据平面](#三设计数据控制配置与证据平面)
- [四、划分代码与运行边界](#四划分代码与运行边界)
- [五、定义接口、所有权与 Observation Contract](#五定义接口所有权与-observation-contract)
- [六、量化 QoS、TF、时间和资源](#六量化-qostf时间和资源)
- [七、并发、生命周期和恢复](#七并发生命周期和恢复)
- [八、现有系统迁移](#八现有系统迁移)
- [九、验证与交付](#九验证与交付)

## 一、选择规模

| 规模 | 适用任务 | 必须交付 |
|---|---|---|
| `component` | 单节点、组件或算法封装 | 职责、输入输出、线程/回调、失败行为、测试 |
| `subsystem` | 定位、感知、建图、控制 | package/node/component、数据流、接口、QoS、TF/时间、恢复、关键 Observation Contract |
| `system` | 整机、多机或分布式 | 子系统全部内容，加资源预算、部署、安全、运维、演进和人工分析路径 |

只完成当前规模必要的设计。用户只问节点边界时，不输出完整整机架构；但对状态估计、SLAM、融合等长期算法，即使只设计 subsystem，也不能省略决定后续可分析性的关键观测契约。

## 二、建立约束

先确认会改变架构的事实：

- 目标、非目标、输入、输出和执行器；
- 数据频率、大小、端到端延迟、抖动和峰值吞吐；
- 精度、可用性、安全和故障容忍；
- CPU/GPU、内存、网络、存储和功耗预算；
- 单机、多机、容器、边缘与云边界；
- ROS 版本、RMW、操作系统、硬件和部署寿命；
- 离线回放、仿真、HIL、认证和兼容要求；
- 是否需要跨会话实验、长期回归和没有 AI 时的人工诊断。

最多询问一个会实质改变方案的关键问题。其他未知条件写成假设，并说明假设变化会影响哪个决策。

## 三、设计数据、控制、配置与证据平面

分开设计四条平面：

1. **数据流**：传感器 → 规范化 → 算法 → 状态/感知结果；
2. **控制流**：命令、模式、任务、反馈、取消和安全停止；
3. **配置流**：参数、标定、地图、模型和版本；
4. **证据流**：Observation Contract → recorder/normalizer → Result Bundle → static report。

```text
Sensors -> Drivers -> Time/Frame normalization -> Preprocessing
        -> Estimation/Perception -> Planning/Control -> Actuators

Configuration -> Orchestrator -> Components
Diagnostics / Evidence <- stable boundaries -> Recorder -> Result Bundle -> Human report
```

连续数据使用 topic；快速幂等请求使用 service；长时、可反馈、可取消任务使用 action。不要用 topic 模拟 RPC，也不要用参数承载动态状态机。

证据流不是运行后临时补的日志。对状态估计、SLAM、LIO、VIO、融合、复杂优化和长期运行算法，读取 [Observation Contract 设计](observation_design.md)，从 failure mode 反推长期稳定观测量。

## 四、划分代码与运行边界

推荐依赖方向：

```text
interfaces
   ↓
algorithm_core      hardware_abstraction
   ↓                        ↓
ros_adapters / nodes / components
   ↓
bringup / deployment / monitoring / analysis_tooling
```

- 算法核心尽量不依赖 `rclcpp`/`rospy`，可离线、可单测；
- ROS 适配层负责消息转换、QoS、TF、参数、lifecycle 和 diagnostics；
- analysis tooling 优先离线消费稳定输出，不反向侵入 production core；
- 接口包不依赖实现包；bringup 不承载业务算法；
- 设备驱动与算法隔离，便于替换硬件和仿真；
- 避免无边界 `common` 包。

用以下因素决定独立进程、node、component 或插件：

| 因素 | 倾向独立进程 | 倾向同进程 component |
|---|---|---|
| 故障隔离/独立重启 | 高 | 低 |
| 大消息和低延迟 | 低 | 高 |
| 不同权限/实时优先级 | 高 | 低 |
| 不同主机/容器/GPU | 高 | 低 |
| 第三方库稳定性差 | 高 | 低 |
| 共享故障域和发布节奏 | 低 | 高 |

插件只用于稳定小接口下替换实现，不把整个 ROS node API 暴露为插件契约。

## 五、定义接口、所有权与 Observation Contract

每个关键 ROS 接口至少记录：

| 字段 | 内容 |
|---|---|
| 名称与类型 | namespace、msg/srv/action |
| 唯一所有者 | 发布者、服务端或动作端 |
| 频率/触发 | 正常值、峰值、超时 |
| 时间语义 | 采样、估计、接收还是发送时刻 |
| frame/单位 | frame_id、坐标约定和 SI 单位 |
| QoS | reliability、durability、history、depth、deadline |
| 失败行为 | 无数据、过期、重连、降级 |
| 版本策略 | 兼容范围和迁移方式 |

同时给出所有权矩阵：

| 资源 | 唯一所有者 | 消费者 | 故障处理 |
|---|---|---|---|
| `map→odom` | localization | navigation | 保持最后有效状态并报警 |
| `/cmd_vel` | motion manager | base controller | 超时 safe stop |
| 标定文件 | calibration manager | drivers/estimator | 版本不匹配拒绝激活 |

每条动态 TF、控制命令入口、配置源和系统状态都必须有唯一所有者和切换协议。

对算法关键边界同时定义 Observation Contract。优先观察层间传递和修正：

```text
sensor → prediction
prediction → measurement update
measurement → gate decision
frontend → backend
local estimate → external fusion
local map → recursive map/loop feedback
processing stage → runtime budget
```

每个信号至少明确 meaning、unit、frame、time basis、source、sampling、validity、required 和 interpretation。不要用未定义语义的 `debug_value_1` 或临时变量替代可维护契约。

## 六、量化 QoS、TF、时间和资源

### 预算表

架构不能只说“低延迟”或“高频”。已知数据时给出：

| 数据流 | 频率 | 单帧大小 | 进程边界副本数 | 带宽 | 延迟预算 |
|---|---:|---:|---:|---:|---:|
| 示例点云 | 10 Hz | 4 MB | 2 | 80 MB/s | 50 ms |

关键路径给出阶段预算：

```text
驱动 3 ms -> 同步 5 ms -> 预处理 15 ms -> 估计 20 ms -> 输出 2 ms
总预算: 45 ms
```

### QoS

按数据语义和失败成本决定，不复制默认配置。高频传感器流通常使用有限队列和低延迟策略；状态、控制、配置根据丢失成本决定可靠性；最后状态类数据按需使用 transient local。跨主机和弱网络必须实测。

### TF

明确固定世界、地图、里程计、机体和传感器 frame；每条动态 TF 的唯一发布者；静态外参来源和版本；变换方向；重定位跳变边界。禁止多个节点竞争同一 transform。

### 时间

明确硬件时钟、系统时钟、ROS time、仿真 `/clock`；时间转换责任；最大乱序、延迟和偏差；缓存、插值、外推和丢弃策略；bag 回放的时钟和速度要求。

Observation Contract 中涉及时间序列时，同样明确 sample/estimate/receive/publish 的时间语义，避免图表把不同时间基准误当因果顺序。

## 七、并发、生命周期和恢复

对关键 callback 标注频率、最坏执行时间、是否阻塞、共享状态和 deadline。设计：

- executor 类型和线程数；
- mutually exclusive / reentrant callback group；
- 高频回调与 I/O、服务、日志隔离；
- 锁顺序、不可变快照、队列上限和 backpressure；
- intra-process、loaned message、内存分配和实时边界。

不要用更多线程掩盖阻塞，也不要在回调中执行不可控同步 I/O。

对驱动、模型/地图加载、估计、控制和硬件接口考虑 lifecycle。明确启动依赖、拒绝激活条件、设备丢失、数据过期、TF 缺失、时间跳变、有限重试、降级、safe stop 和人工恢复。系统 orchestrator 掌握依赖图；节点只报告本地状态。

每个关键边界提供频率、延迟、数据年龄、丢弃、队列、callback 耗时、CPU/内存、健康状态和结构化错误码。需要长期实验的系统，把其中真正用于因果判断的量纳入 Observation Contract，而不是把全部 diagnostics 永久落盘。

## 八、现有系统迁移

Brownfield 重构必须先保护现有行为：

1. 记录现有运行图、接口、部署、性能和结果基线；
2. 标记必须兼容的 topic/service/action、参数、TF、bag、指标和对齐定义；
3. 找出当前故障域、复制热点、循环依赖和不可测试逻辑；
4. 设计目标边界和临时适配层；
5. 按最小可回滚阶段迁移；
6. 每阶段运行相同 bag/仿真/硬件回归，并使用同一 Analysis Contract；
7. 观察期结束后删除旧接口和适配层。

迁移表：

| 阶段 | 变更 | 兼容措施 | 验证 | 回滚点 |
|---|---|---|---|---|
| 1 | 抽离算法核心 | 保留旧 ROS wrapper | 固定输入单测 | 恢复旧库 |
| 2 | 新接口并行 | bridge/dual publish | bag A/B + 固定静态报告 | 切回旧 topic |

不要因为引入新的分析工具而偷偷改变历史指标、轨迹对齐或误差定义。

## 九、验证与交付

使用决策矩阵绑定约束与设计：

| 约束 | 决策 | 原因 | 验证方式 |
|---|---|---|---|
| 点云数据量大 | 预处理进程内组合 | 减少序列化 | tracing 延迟 |
| 驱动不稳定 | 独立进程 | 故障隔离 | 崩溃注入 |
| 控制安全关键 | 独立实时边界 | 权限与时序隔离 | watchdog 测试 |
| 长期 SLAM 回归 | 固定 Observation + Analysis Contract | 无 AI 也能复核 | bag + static report |

验证层级：无 ROS 算法单测 → 消息/参数测试 → component/node 接口测试 → launch/lifecycle 测试 → bag/仿真回归 → 故障注入/硬件验收。

按规模交付，不堆无关章节：

- `component`：职责、接口、线程、错误处理、测试；
- `subsystem`：再加结构图、数据流、QoS、TF/时间、恢复，以及关键 Observation Contract；
- `system`：再加预算、部署拓扑、安全、运维、迁移、演进和 Human Analysis Contract。

对需要长期数值验证的项目，最终设计链应能落到：

```text
Algorithm Contract
→ Observation Contract
→ Result Contract
→ Visualization Contract
→ Human Analysis Contract
```

需要建立项目本地分析能力时使用：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

之后工程师可以直接运行：

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
```

并打开 `RUN_DIR/report/index.html`。读取 [Human Analysis Contract](analysis_contract.md) 与 [结果管理](result_management.md)。
