# ROS Noetic 系统架构设计

## 目标与边界

本文件只描述 **ROS 1 Noetic** 架构语义。默认平台是 Ubuntu 20.04 + ROS Noetic + catkin。不要把 ROS 2 的 QoS、DDS/RMW、lifecycle、component container、executor/callback group、rosbag2、ament/colcon 当作本文件的设计工具。

Noetic 已结束官方支持。架构评审除功能、性能和可维护性外，还要记录 EOL 带来的依赖来源、安全更新、镜像冻结、可重现构建和迁移窗口。

目标是设计可实施、可测试、可运维、可演进、可回放且**可独立分析**的 ROS 1 系统。先选择设计规模，再决定需要多少证据，避免用整机方案回答单节点问题。

## 一、选择规模

| 规模 | 适用任务 | 必须交付 |
|---|---|---|
| `node` | 单节点、算法 wrapper、驱动或工具 | 职责、输入输出、参数、线程/回调、失败行为、测试 |
| `subsystem` | 定位、感知、建图、控制、传感器链 | package/node/nodelet、数据流、topic/service/action、TF/时间、启动恢复、关键 Observation Contract |
| `system` | 整机、多机、分布式或长期部署 | 子系统全部内容，加 ROS master/网络、资源预算、部署、安全、运维、EOL、迁移和人工分析路径 |

只完成当前规模必要的设计。对状态估计、SLAM、LIO、VIO、融合和复杂优化，即使只做 subsystem，也不能省略决定后续可分析性的关键观测契约。

## 二、先锁定 Noetic 环境与约束

设计前记录：

- `ROS_VERSION=1`、`ROS_DISTRO=noetic`、`rosversion -d`；
- Ubuntu/容器镜像、CPU 架构、Python 3 版本；
- catkin 构建方式：`catkin_make`、`catkin build` 或 CI 封装；
- workspace 与 overlay 顺序：`ROS_PACKAGE_PATH`、`CMAKE_PREFIX_PATH`；
- `ROS_MASTER_URI`、`ROS_IP` / `ROS_HOSTNAME`、单机或多机拓扑；
- 设备、权限、udev、串口/CAN/以太网接口；
- 输入输出频率、大小、端到端延迟、抖动、峰值吞吐；
- 精度、可用性、安全、故障容忍；
- CPU/GPU、内存、网络、磁盘和功耗预算；
- 是否需要 rosbag1 回放、仿真、HIL、长期回归和没有 AI 时的人工诊断。

最多询问一个会实质改变架构的关键问题。其他未知条件写成假设，并说明假设变化会影响哪个决策。

## 三、设计四条平面

1. **数据平面**：sensor/driver → normalization → algorithm → output；
2. **控制平面**：service、actionlib、模式切换、安全停止；
3. **配置平面**：rosparam、YAML、标定、地图、模型、dynamic_reconfigure；
4. **证据平面**：diagnostics + Observation Contract → recorder/normalizer → Result Bundle → static report。

```text
Sensors -> Drivers -> Time/Frame normalization -> Preprocessing
        -> Estimation/Perception -> Planning/Control -> Actuators

YAML / rosparam / calibration -> roslaunch / node configuration
Diagnostics / Evidence <- stable boundaries -> Recorder -> Result Bundle -> Human report
```

接口选择：

- 连续状态和传感器流：topic；
- 快速、幂等、请求-响应操作：service；
- 长时、可反馈、可取消任务：actionlib；
- 静态/启动配置：rosparam + YAML；
- 需要在线小范围调参且语义适合：dynamic_reconfigure。

不要用 topic 模拟 RPC，不要把动态系统状态永久塞进参数服务器，也不要用 dynamic_reconfigure 替代真实状态机。

## 四、划分 package、node、nodelet 与算法核心

推荐依赖方向：

```text
messages / interfaces
        ↓
algorithm_core      hardware_abstraction
        ↓                    ↓
roscpp/rospy adapters / nodes / nodelets
        ↓
bringup / launch / monitoring / analysis_tooling
```

- 算法核心尽量不依赖 `ros::NodeHandle` / `rospy`，便于离线单测和 rosbag 回归；
- ROS 适配层负责消息转换、TF、参数、时间、diagnostics 和通信；
- bringup package 负责 launch、机器/设备组合和部署，不承载核心算法；
- 消息 package 不依赖实现 package；
- 设备驱动与算法隔离，便于替换硬件和仿真；
- 避免无边界 `common` / `utils` 包；
- pluginlib 只用于稳定小接口下替换实现，不把整个节点行为隐式藏进插件。

### 独立进程还是 nodelet

| 因素 | 倾向独立 node/process | 倾向同一 nodelet manager |
|---|---|---|
| 故障隔离、独立重启 | 高 | 低 |
| 大消息、图像/点云、低复制 | 低 | 高 |
| 第三方库不稳定 | 高 | 低 |
| 不同权限/实时优先级 | 高 | 低 |
| 不同主机/容器/GPU | 高 | 低 |
| 共享大内存、低延迟流水线 | 低 | 高 |

nodelet 的收益是减少序列化/复制，但会共享进程故障域、线程池和地址空间。设计时明确 manager、线程数、共享库和崩溃影响。

## 五、定义 ROS 1 接口契约

每个关键 topic 至少记录：

| 字段 | 内容 |
|---|---|
| 名称/类型 | namespace、message type |
| 发布者/订阅者 | 唯一或预期数量 |
| 频率/触发 | 正常值、峰值、超时 |
| queue | publisher/subscriber `queue_size` 与积压策略 |
| transport | TCPROS/UDPROS、`tcpNoDelay`、TransportHints（如适用） |
| latch | 是否 latched，late subscriber 语义 |
| 时间 | `header.stamp` 是采样、估计、接收还是发送时刻 |
| frame/单位 | `frame_id`、坐标约定、SI 单位 |
| 失败行为 | 无数据、过期、重连、丢包、重复、乱序 |
| 版本策略 | 自定义消息兼容、MD5 变化和 bag 兼容 |

每个 service/action 同样记录 server 唯一性、超时、重试、取消、幂等性和失败码。

不要使用 ROS 2 QoS 术语来替代 ROS 1 的真实问题。Noetic 中应直接分析：队列、TCPROS/UDPROS、latch、连接建立、XML-RPC/master 注册、网络可达性和应用层丢弃。

### 所有权矩阵

| 资源 | 唯一所有者 | 消费者 | 故障处理 |
|---|---|---|---|
| `map -> odom` | localization | navigation | 保持最后有效状态并报警 |
| `/cmd_vel` | motion manager | base controller | timeout 后 safe stop |
| 标定文件 | calibration owner | driver/estimator | 版本不匹配拒绝启动 |
| `/use_sim_time` | bringup policy | 全系统 | 回放前明确设置，禁止局部漂移 |

每条动态 TF、控制命令入口、配置源和关键系统状态都必须有唯一所有者和切换协议。

## 六、TF、时间、网络与资源

### TF

明确：

- 固定世界、地图、里程计、机体和传感器 frame；
- tf1 还是 tf2 API，禁止同一链路多发布者竞争；
- 静态外参来源、单位、版本、变换方向；
- 查询时刻、缓存窗口和 extrapolation 策略；
- 重定位/回环造成跳变的允许边界。

### 时间

明确：

- 设备硬件时间、系统时间、ROS time；
- `header.stamp` 责任方；
- `/use_sim_time` 与 `/clock`；
- 最大乱序、延迟、偏差和时间回退；
- 同步、插值、外推和丢弃策略；
- rosbag play 的 `--clock`、rate、start offset 和 loop 行为。

### 多机网络

ROS master 可见不等于 TCPROS 数据路径可达。多机必须同时验证：

- `ROS_MASTER_URI` 指向一致；
- `ROS_IP` / `ROS_HOSTNAME` 可被其他主机解析和回连；
- 容器/NAT/VPN/防火墙不会只允许 master 注册而阻断随机 TCPROS 端口；
- 各主机时间同步满足算法需要；
- 不混用 localhost、错误 hostname 或多个冲突网卡地址。

### 资源预算

架构不能只说“低延迟”或“高频”。已知数据时给出阶段预算：

```text
驱动 3 ms -> 同步 5 ms -> 预处理 15 ms -> 估计 20 ms -> 输出 2 ms
总预算: 45 ms
```

点云、图像等大消息还应估算序列化、复制、nodelet 共享和 bag 录制开销。

## 七、线程、Spinner、Callback Queue 与恢复

对关键 callback 标注：频率、最坏执行时间、是否阻塞、共享状态、锁、deadline 和队列上限。

Noetic 并发设计使用真实 ROS 1 模型：

- `ros::spin()` / `ros::spinOnce()`；
- `ros::AsyncSpinner` / `ros::MultiThreadedSpinner`；
- global 或 custom `ros::CallbackQueue`；
- timer/subscriber/service/action callback；
- nodelet manager 的 worker threads；
- rospy callback threads 与 Python GIL/阻塞 I/O。

重点检查：

- 长 callback 阻塞高频传感器；
- callback 内同步 service/action 等待形成互锁；
- 多锁顺序不一致；
- 无界队列或处理速度低于输入速度；
- nodelet manager 线程池被一个插件耗尽；
- shutdown/join 和设备重连路径死锁。

不要用“多开线程”掩盖阻塞，也不要把 ROS 2 executor/callback group 模型套进 Noetic。

### 启动与恢复

ROS 1 没有 ROS 2 managed lifecycle。需要显式设计：

- roslaunch 启动依赖和 readiness 条件；
- 参数/标定/设备缺失时是 fail-fast 还是降级；
- `respawn` 是否安全，是否会造成重启风暴；
- diagnostics/watchdog/bond 或自定义 heartbeat；
- 设备丢失、数据过期、TF 缺失、时间跳变的恢复策略；
- 控制系统的 safe stop 和人工恢复入口。

进程存在不等于节点健康，节点注册在 master 也不等于算法已 ready。

## 八、Observation Contract 与长期结果分析

对状态估计、SLAM、LIO、VIO、融合和复杂优化，从 failure mode 反推观测量：

```text
sensor -> prediction
prediction -> measurement update
measurement -> gate decision
frontend -> backend
local estimate -> external fusion
local map -> recursive map / loop feedback
processing stage -> runtime budget
```

每个信号明确 meaning、unit、frame、time basis、source、sampling、validity、required 和 interpretation。

对于长期 rosbag 回归，保持：

```text
Algorithm Contract
-> Observation Contract
-> Result Contract
-> Visualization Contract
-> Human Analysis Contract
```

固定指标、对齐、时间基准和读图顺序。不要每次由 Agent 临时发明 telemetry 或图。

## 九、Brownfield 重构与迁移

已有 Noetic 系统重构必须先保护现有行为：

1. 记录当前 package/node/nodelet、topic/service/action、参数、TF、bag 和部署基线；
2. 标记必须兼容的消息 MD5、topic 名、launch 参数、YAML、TF 和结果指标；
3. 找出故障域、复制热点、循环依赖和不可测试逻辑；
4. 先抽离算法核心，再改 ROS wrapper；
5. 每阶段保持可回滚；
6. 使用同一 rosbag、参数加载方式和指标做前后 A/B；
7. 观察期结束后删除临时 dual-publish/适配层。

如果目标是迁移到 ROS 2，单独进入迁移任务，不在 Noetic 修复中偷偷引入 ROS 2 API。

## 十、验证与交付

验证层级：

```text
无 ROS 算法单测
-> catkin 单 package 构建
-> message/parameter/plugin 测试
-> rostest
-> roslaunch 短时运行
-> rosbag1 回归
-> 故障注入 / 多机网络 / 硬件验收
```

常用验证证据包括：

```bash
rosversion -d
catkin_make                 # 或 catkin build <pkg>
rospack find <pkg>
roslaunch --screen <pkg> <file.launch>
rosnode info /node
rostopic info /topic
rosservice info /service
rosparam get /path
roswtf
```

按规模交付，不堆无关章节：

- `node`：职责、接口、参数、线程、错误处理、测试；
- `subsystem`：再加结构图、数据流、TF/时间、queue/transport、恢复和关键 Observation Contract；
- `system`：再加 ROS master/多机网络、预算、部署、安全、EOL、运维、迁移和 Human Analysis Contract。
