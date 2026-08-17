# ROS 系统架构设计

## 目标

设计可实施、可测试、可运维、可演进且**可独立分析**的 ROS 系统。先选择设计规模，避免用整机流程回答一个组件问题。

## 一、选择规模

| 规模 | 适用任务 | 必须交付 |
|---|---|---|
| `component` | 单节点、组件或算法封装 | 职责、输入输出、线程/回调、失败行为、测试 |
| `subsystem` | 定位、感知、建图、控制 | package/node/component、数据流、接口、QoS、TF/时间、恢复、关键 Observation Contract |
| `system` | 整机、多机或分布式 | 子系统全部内容，加资源预算、部署、安全、运维、演进和人工分析路径 |

## 二、建立约束

确认目标、非目标、输入输出、数据频率、延迟/抖动、精度/可用性、安全、CPU/GPU/内存/网络/存储、部署拓扑、ROS/RMW/OS/硬件、离线回放/仿真/HIL/兼容要求。最多询问一个会实质改变方案的问题，其余未知条件写成假设。

## 三、设计四条平面

```text
数据流: Sensors → normalize → algorithm → state/result
控制流: command / mode / action / safe stop
配置流: params / calibration / map / model / version
证据流: observation contract → recorder → result bundle → static report
```

证据流不是运行后临时补的日志。对于状态估计、SLAM、融合、复杂优化和控制，读取 [Observation Contract 设计](observation_design.md)，从 failure mode 反推长期可观测信号。

## 四、划分代码与运行边界

推荐：

```text
interfaces
   ↓
algorithm_core      hardware_abstraction
   ↓                        ↓
ros_adapters / nodes / components
   ↓
bringup / deployment / monitoring / analysis tooling
```

算法核心尽量不依赖 ROS；ROS 适配层负责消息、QoS、TF、参数和 lifecycle；analysis tooling 尽量离线消费稳定输出，不反向侵入 production core。

## 五、定义接口与所有权

每个关键接口记录名称/类型、唯一所有者、频率/触发、时间语义、frame/单位、QoS、失败行为和版本策略。每条动态 TF、控制命令入口、配置源和系统状态必须有唯一所有者。

对算法内部关键层间边界，同时定义 Observation Contract：prediction→update、measurement→gate、frontend→backend、loop/map feedback 等边界量优先于任意内部临时变量。

## 六、量化 QoS、TF、时间和资源

给出数据流和关键路径预算；明确 QoS、frame 树和唯一 TF 发布者；明确硬件时钟、系统时钟、ROS time、仿真时钟以及最大乱序/偏差/延迟。关键 callback 标注频率、最坏耗时、是否阻塞和 deadline。

## 七、并发、生命周期和恢复

定义 executor、callback group、锁/队列/backpressure、生命周期、启动依赖、降级、safe stop 和人工恢复。每个关键边界提供频率、延迟、数据年龄、丢弃、队列、callback 耗时、CPU/内存、健康状态和结构化错误码。

## 八、现有系统迁移

先记录现有运行图、接口、部署、性能和结果基线；保护必须兼容的 topic/service/action、参数、TF 和 bag；按最小可回滚阶段迁移；每阶段使用同一输入和同一分析契约做回归。不要因为新工具引入而改变历史指标定义。

## 九、验证与交付

验证层级：无 ROS 算法单测 → 消息/参数 → node/component → launch/lifecycle → bag/仿真 → 故障注入/HIL。

对 subsystem/system，交付不仅包括“代码如何跑”，还包括：

```text
Algorithm Contract
Observation Contract
Result Contract
Visualization Contract
Human Analysis Contract
```

若项目需要长期 bag/算法验证，使用 `bootstrap_analysis_tooling.py` 初始化项目本地分析工具，使 `analyze_run.py RUN_DIR` 可生成不依赖 AI 的静态 `report/index.html`。读取 [Human Analysis Contract](analysis_contract.md) 和 [结果管理](result_management.md)。
