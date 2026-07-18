# ROS/ROS2 调试工作流

## 1. 固化条件

记录仓库、branch、commit、工作空间、ROS 发行版、OS、RMW、构建命令、launch 命令、参数、bag 哈希、设备与固件、错误日志和发生时间。一次只改变一个主要变量。

## 2. 建立事实与假设

先列出已观察事实，再列候选假设。每个假设都写出：支持证据、反证、区分实验和通过/失败判据。

## 3. 分层定位

按以下顺序排查，但允许根据证据跳转：

1. **环境与依赖**：ROS 环境是否 source、overlay 顺序、rosdep、系统库、Python 环境、架构和容器。
2. **构建与安装**：消息生成、导出依赖、链接、install 规则、C++ 标准、缓存和 ABI。
3. **启动与进程**：launch include、namespace、remap、参数作用域、进程退出、lifecycle 和 component 加载。
4. **发现与网络**：ROS_DOMAIN_ID、RMW、multicast、防火墙、Docker/VPN、discovery server 和 DDS Security。
5. **接口与 QoS**：消息类型、type hash、publisher/subscriber、reliability、durability、history、depth、deadline 和 liveliness。
6. **executor 与并发**：callback group、线程数、阻塞 callback、同步 service 等待、锁、死锁和 starvation。
7. **数据语义**：字段、单位、坐标轴、NaN、协方差、状态码、饱和、丢包和同周期一致性。
8. **时间与同步**：测量时间、header、bag time、callback、clock domain、offset、漂移、乱序和回退。
9. **TF 与标定**：frame 语义、authority、时间范围、重复发布、方向、单位、URDF 和外参适用范围。
10. **性能与资源**：CPU、内存、网络、序列化、队列、callback 时长、锁竞争和实时性。
11. **算法与数值**：初始化、门限、噪声、退化、可观测性、鲁棒核、条件数和异常输入。

## 4. 最小区分实验

优先设计能排除最多假设、改动最少的实验，例如：

- 用已知兼容 QoS 的临时订阅者区分发现问题和算法问题；
- 固定短 bag 区分现场设备问题和软件问题；
- 禁用一个重复 TF 发布者，而不是修改全部 frame；
- 输出每种丢弃原因计数，而不是单纯扩大队列；
- 比较 header、packet 和 callback 时间分布，而不是只看一帧。

## 5. 最小修复

修复应直接针对已验证机制。避免同时重构、升级依赖和调整算法参数。新增诊断需节流，并能在问题解决后保留低成本可观测性。

## 6. 回归

至少根据任务验证：

- 目标包构建和安装；
- 节点无异常退出；
- 关键端点存在且类型/QoS 正确；
- 参数和 lifecycle 状态符合预期；
- TF 唯一、连通且时间可查询；
- 时间差、频率、丢包和延迟进入判据；
- 历史 incident 不再复现；
- 修复没有引入 CPU、内存、网络或控制安全回归。
