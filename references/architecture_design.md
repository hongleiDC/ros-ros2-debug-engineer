# ROS 系统架构设计

## 目标

设计可以实施、测试、运维和演进的 ROS 系统，而不是只画节点框图。架构必须同时处理数据流、时间、坐标、并发、故障、部署和验证。

## 目录

- [一、建立系统约束](#一建立系统约束)
- [二、设计数据与控制平面](#二设计数据与控制平面)
- [三、划分 package 与代码边界](#三划分-package-与代码边界)
- [四、决定 node 与 component 边界](#四决定-node-与-component-边界)
- [五、定义接口契约](#五定义接口契约)
- [六、设计 QoS、TF 与时间](#六设计-qostf-与时间)
- [七、设计并发与实时性](#七设计并发与实时性)
- [八、生命周期与故障恢复](#八生命周期与故障恢复)
- [九、可观测性、测试与部署](#九可观测性测试与部署)
- [十、交付模板](#十交付模板)

## 一、建立系统约束

先写清楚：

- 任务目标和不做什么；
- 输入设备、上游系统、输出和执行器；
- 频率、端到端延迟、抖动、吞吐和数据规模；
- 精度、可用性、安全和故障容忍；
- CPU/GPU/内存/网络预算；
- 单机、多机、容器、边缘与云边界；
- ROS 版本、RMW、操作系统和部署寿命；
- 是否需要离线回放、仿真、硬件在环或认证。

如果约束未知，明确假设及其对架构的影响。不要在不知道频率和延迟目标时武断选择 executor 或 QoS。

## 二、设计数据与控制平面

分别设计四条流：

1. **主数据流**：传感器到状态、地图、感知或控制输出；
2. **控制流**：命令、模式切换、任务执行和安全停止；
3. **配置流**：参数、标定、地图、模型和版本；
4. **诊断流**：健康状态、延迟、丢包、资源和故障事件。

示例：

```text
Sensors -> Drivers -> Time/Frame normalization -> Preprocessing
        -> Estimation/Perception -> Planning/Control -> Actuators

Configuration -> Lifecycle orchestration -> Components
Diagnostics <- every boundary -> Monitoring/Recorder
```

高频数据不要通过 service；长时任务不要用阻塞 service；需要反馈和取消的任务使用 action。

## 三、划分 package 与代码边界

优先使用稳定依赖方向：

```text
interfaces
   ↓
algorithm_core      hardware_abstraction
   ↓                        ↓
ros_adapters / nodes / components
   ↓
bringup / deployment / monitoring
```

推荐原则：

- 算法核心尽量不依赖 `rclcpp`/`rospy`，可用普通单元测试和离线数据调用；
- 消息转换、QoS、TF、参数和 lifecycle 放在 ROS 适配层；
- 自定义 msg/srv/action 集中在接口包，避免循环依赖；
- bringup 只负责编排，不承载业务算法；
- 硬件驱动与算法依赖反向隔离，便于仿真和替换设备；
- 公共工具包必须有清晰职责，避免形成无边界 `common` 包。

一个典型目录：

```text
robot_interfaces/
sensor_drivers/
sensor_preprocessing_core/
sensor_preprocessing_ros/
localization_core/
localization_ros/
planning_core/
planning_ros/
system_bringup/
system_monitoring/
system_tools/
```

## 四、决定 node 与 component 边界

使用以下问题决定边界：

- 是否必须独立重启或故障隔离；
- 是否属于不同安全权限或生命周期；
- 是否部署在不同主机/GPU/容器；
- 是否需要不同实时优先级；
- 数据量是否大到需要进程内零拷贝；
- 是否由不同团队独立发布；
- 崩溃是否允许影响同一进程内其他组件。

选择建议：

- 高频大数据且同一故障域：考虑 component composition 和 intra-process；
- 设备驱动、控制器、安全监控：通常保持独立进程；
- 可替换算法：使用稳定接口和插件边界；
- 不要把每个函数变成节点，也不要把整个机器人做成一个节点。

## 五、定义接口契约

每个关键接口记录：

| 字段 | 内容 |
|---|---|
| 名称 | namespace 和稳定命名 |
| 类型 | 标准或自定义 msg/srv/action |
| 所有者 | 唯一发布/服务责任组件 |
| 频率/触发 | 正常、峰值和超时 |
| 时间语义 | stamp 对应采样、估计还是发送时刻 |
| frame/单位 | frame_id、坐标约定和 SI 单位 |
| QoS | reliability、durability、history、depth、deadline |
| 失败行为 | 无数据、过期、降级和重连 |
| 版本策略 | 兼容性和迁移方式 |

避免通过 topic 名隐式编码模式。模式切换使用显式状态或服务/action，并定义并发请求行为。

## 六、设计 QoS、TF 与时间

### QoS

- 传感器高频流通常优先低延迟和有限队列；
- 状态、控制和配置根据丢失成本决定可靠性；
- 静态/最后状态类数据根据需求使用 transient local；
- 为 deadline、liveliness 和 lifespan 定义可观测行为；
- 跨主机和弱网络必须实测，不照抄默认 QoS。

### TF

明确：

- 固定世界、地图、里程计、机体和传感器 frame；
- 每条动态 TF 的唯一发布者；
- 静态外参的来源和版本；
- 变换方向、树结构和重定位时的跳变边界；
- 不允许两个节点竞争发布同一 transform。

### 时间

明确：

- 硬件时钟、系统时钟、ROS time 和仿真 clock；
- 驱动如何转换硬件时间；
- 最大允许乱序、延迟和时钟偏差；
- 插值、外推、缓存和丢弃策略；
- bag 回放是否需要 `/clock` 和确定性速度。

## 七、设计并发与实时性

对每个 callback 标注：频率、最坏执行时间、是否阻塞、共享状态和 deadline。

设计内容：

- executor 类型和线程数；
- mutually exclusive / reentrant callback group；
- 高频回调与低频 I/O、服务和日志隔离；
- 锁顺序、无锁队列或消息快照策略；
- backpressure、队列上限和丢弃策略；
- 内存分配、消息复制、loaned message 和 intra-process；
- 实时线程与非实时线程的边界。

不要用更多线程掩盖阻塞设计，也不要在回调中执行不可控的同步 I/O。

## 八、生命周期与故障恢复

对驱动、核心估计、控制和关键资源节点考虑 lifecycle：

```text
unconfigured -> inactive -> active
                      ↓       ↓
                     error <- failure
```

定义：

- 配置和激活的依赖顺序；
- 参数或标定无效时是否拒绝激活；
- 设备丢失、数据过期、TF 缺失和时间跳变时的行为；
- 自动重连、有限重试、降级、safe stop 和人工恢复；
- orchestration 由谁负责，避免每个节点自行猜测系统状态。

## 九、可观测性、测试与部署

每个关键边界至少提供：

- 输入/输出频率、延迟、年龄和丢弃计数；
- 队列积压、callback 耗时、CPU 和内存；
- lifecycle、设备和依赖健康状态；
- 可关联的日志字段和故障码；
- 必要的 tracing 和 bag 录制点。

测试层级：

1. 无 ROS 算法单元测试；
2. 消息转换和参数测试；
3. component/node 接口测试；
4. launch 与 lifecycle 测试；
5. bag/仿真回归；
6. 故障注入和硬件验收。

部署方案说明容器/进程边界、CPU affinity、权限、配置版本、日志轮转、启动顺序和回滚。

## 十、交付模板

架构答复按以下结构输出：

1. **约束与关键取舍**；
2. **推荐架构图或数据流**；
3. **package/node/component 结构**；
4. **接口、QoS、TF 与时间设计**；
5. **并发、生命周期和故障恢复**；
6. **测试、部署和分阶段实施**；
7. **尚需确认的少量关键问题**。

不要只给抽象原则。至少提供一份适用于目标系统的具体接口表、目录结构或组件图。
