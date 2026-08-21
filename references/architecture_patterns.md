# ROS Noetic 架构决策模式

本文件只用于 ROS 1 Noetic 的边界取舍，不重复完整架构流程。

## 运行边界决策

| 方案 | 适合 | 主要收益 | 主要代价 |
|---|---|---|---|
| 独立 node/process | 驱动、控制、安全监控、不稳定第三方库、独立部署 | 故障与权限隔离、独立重启 | TCPROS 序列化、进程管理、多机网络复杂度 |
| nodelet manager | 图像/点云高频流水线、同团队、同故障域 | 同进程少拷贝/零拷贝、低延迟 | 崩溃共享、线程池/插件设计更难 |
| pluginlib 插件 | 稳定接口下切换算法或设备模型 | 实现可替换、部署灵活 | ABI/API 稳定性要求 |
| 普通 C++/Python 库 | 确定性算法、转换、优化和模型 | 易测试、易复用、低 ROS 耦合 | 需要 ROS wrapper |

默认先将算法做成普通库，再决定是否放入独立 node 或 nodelet。

## 接口选择

| 需求 | 选择 | 不要选择 |
|---|---|---|
| 连续异步数据 | topic | service 轮询 |
| 快速幂等查询/设置 | service | 自定义 request topic |
| 长时、反馈、取消 | actionlib | 长时间阻塞 service |
| 静态版本化配置 | YAML/rosparam | 高频参数更新 |
| 运行时小范围调参 | dynamic_reconfigure | 用参数服务器模拟状态机 |
| 模式与系统状态 | 显式状态机/topic | 多个布尔参数拼接 |
| 健康与故障 | diagnostics/status + 错误码 | 仅自由文本日志 |

## ROS 1 通信决策

Noetic 没有 ROS 2 QoS compatibility。通信契约直接讨论：

- publisher/subscriber `queue_size`；
- TCPROS/UDPROS；
- `tcpNoDelay` / TransportHints；
- latch；
- publisher/subscriber 数量；
- message type / MD5；
- 多机回连地址；
- 应用层丢弃和超时。

高频传感器链优先保证“处理速度 >= 长期平均输入速度”，不要用无限增大 queue 掩盖计算不足。

## 启动与恢复决策

ROS 1 没有 managed lifecycle。需要显式设计：

- roslaunch 启动顺序与 readiness；
- 参数、标定、地图、模型和设备缺失时 fail-fast 还是降级；
- `respawn` 是否安全；
- watchdog / diagnostics / bond / heartbeat；
- 数据过期、TF 缺失、设备断连后的有限重试；
- 控制系统 safe stop 与人工恢复。

“进程存在”与“节点 ready”必须分开定义。

## 多机与部署决策

- 用 namespace 表示机器人或站点实例，不写死前缀；
- 明确 `ROS_MASTER_URI`、`ROS_IP` / `ROS_HOSTNAME`、DNS/hosts 和时钟同步；
- master 注册可见不代表 TCPROS 数据路径可达；
- 原始高带宽数据尽量在采集主机附近处理；
- 控制链路与可视化/记录链路分开评估；
- 容器边界对齐故障/资源边界，不默认一个 node 一个容器；
- 配置、镜像、接口和 rosbag1 数据均带版本/哈希。

## 常见反模式

| 反模式 | 症状 | 修复方向 |
|---|---|---|
| 节点过度拆分 | launch 复杂、TCPROS 复制多、难追踪 | 按故障域、频率、复制成本聚合 |
| 巨型节点 | 驱动、算法、TF、控制耦合 | 抽离算法核心和硬件边界 |
| nodelet 滥用 | 一个插件崩溃拖垮整条链 | 只给大消息/低延迟链使用，共享 manager 前评估故障域 |
| Topic 模拟 RPC | 自定义 ID、超时和并发混乱 | service/actionlib |
| 参数作为动态状态 | 竞争更新、不可追踪 | 显式命令与状态机 |
| 多个 TF 发布者 | frame 跳变、树不稳定 | 唯一所有者和切换协议 |
| 盲目扩大 queue | 延迟持续增长、内存增加 | 找处理瓶颈、定义积压策略和丢弃计数 |
| callback 阻塞 | 卡顿、饥饿、掉帧 | 隔离 I/O、自定义 CallbackQueue、有界工作队列 |
| 全局共享可变状态 | 隐式竞争、不可重放 | 唯一写者、不可变快照、版本号 |
| respawn 风暴 | 节点反复重启且根因被隐藏 | fail-fast、退避、故障计数和人工介入 |

## 快速决策规则

1. 需要独立重启、权限隔离或第三方库不稳定：独立 process。
2. 大消息、高频、同故障域且复制成本明确：考虑 nodelet。
3. 只替换算法实现：pluginlib 或普通库，不新增通信层。
4. 需求不能量化：先给假设和验证计划，不武断选线程数或 queue。
5. 每个架构决定必须能对应某个约束、风险或可测收益。
