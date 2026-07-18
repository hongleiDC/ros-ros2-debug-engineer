# ROS2 运行时

## DDS 与发现

检查并记录：

- `ROS_DOMAIN_ID`、`RMW_IMPLEMENTATION`、`ROS_LOCALHOST_ONLY`；
- Fast DDS、Cyclone DDS 或其他 RMW 的配置文件；
- multicast、网卡选择、IPv4/IPv6、防火墙、VPN、Docker network；
- discovery server、DDS Router 和跨主机时钟；
- DDS Security enclave、证书和权限文件是否一致。

同机可见不代表跨机可见；CLI 可见不代表目标进程使用相同环境。记录启动进程实际继承的环境。

## QoS

不要只检查 reliability。比较完整 QoS：history、depth、reliability、durability、deadline、lifespan、liveliness 和 lease duration。区分“端点没有发现”“QoS 不兼容”“发现后无数据”“数据被应用层丢弃”。

常用只读命令：

```bash
ros2 topic list -t
ros2 topic info /topic -v
ros2 node info /node
ros2 doctor --report
```

## Lifecycle

对 managed node 检查：

- 当前状态和可用 transition；
- configure/activate 失败日志；
- lifecycle publisher 是否激活；
- launch 是否自动触发 transition；
- 依赖节点是否在正确状态。

不要把“进程存在”当成“节点处于 Active”。

## Components

检查 component 是否加载到预期 container、plugin 名称是否导出、参数和 remap 是否传入、container 使用哪个 executor、卸载和重载是否安全。

## Executor 与 callback group

记录 executor 类型、线程数、callback group 类型和 callback 关系。重点检查：

- 默认 mutually exclusive group 使多线程 executor 实际串行；
- callback 中同步等待 service/action future；
- 长回调阻塞 timer、subscription 或 parameter callback；
- 多锁顺序、条件变量和 shutdown join；
- callback group 与 component container 的组合。

## 参数

区分源码默认值、参数 YAML、launch override、命令行 override 和运行时动态修改。检查参数是否声明、类型是否正确、namespace 是否匹配，以及参数 callback 是否拒绝更新。

## Service 与 Action

检查名称、类型、server 数量、等待超时、取消语义和 action feedback/result。不要在诊断模式下调用可能改变硬件或系统状态的 service/action。
