# ROS Noetic 运行时模型

本参考只适用于 ROS 1 Noetic。任何诊断前先确认：

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

期望 `ROS_VERSION=1`、`ROS_DISTRO=noetic`、`rosversion -d` 输出 `noetic`。

## ROS Master 与名称解析

ROS 1 的运行时核心是 ROS master + XML-RPC 注册/发现，而不是 DDS discovery。优先检查：

```bash
roscore
rosnode list
rosnode info /node
roswtf
```

多机系统同时核对：

- `ROS_MASTER_URI`；
- `ROS_IP` / `ROS_HOSTNAME`；
- DNS/hosts；
- 主机互通与防火墙；
- 容器网络模式；
- 每个进程实际继承的环境变量。

`rosnode list` 可见只证明 master 中有注册，不证明 TCPROS 数据链路一定可达。

## Topic / TCPROS / UDPROS

常用只读检查：

```bash
rostopic list
rostopic info /topic
rostopic type /topic
rostopic hz /topic
rostopic bw /topic
rostopic delay /topic
```

ROS 1 没有 ROS 2 的 QoS compatibility 机制。无数据时重点区分：

1. topic 名称/namespace/remap 错误；
2. message type / MD5 不一致；
3. publisher/subscriber 未真正建立 TCPROS/UDPROS 连接；
4. 多机地址解析或网络不可达；
5. callback queue/thread 被阻塞；
6. 应用层主动丢弃或时间/TF gate 失败。

不要把 ROS 2 reliability/durability/history/depth 诊断套到 Noetic。

## Service 与 Actionlib

Service：

```bash
rosservice list
rosservice info /service
rosservice type /service
```

Actionlib 通常表现为一组 topic（goal/cancel/status/feedback/result）。检查 client/server 的 namespace、action 类型、server 是否启动以及状态机是否卡住。诊断模式下不要调用可能驱动真实硬件的 service/action。

## 参数服务器与 dynamic_reconfigure

参数来自 ROS master 参数服务器。区分：

- launch `<param>` / `<rosparam>`；
- YAML load；
- private (`~param`) / relative / global 名称；
- 启动时读取一次 vs 周期读取；
- dynamic_reconfigure 运行时变更。

常用检查：

```bash
rosparam list
rosparam get /namespace
rosparam get /node/param
```

参数存在不代表节点一定读取了该键；必须核对代码中的 NodeHandle namespace 与参数名。

## roslaunch

Noetic 默认是 XML `.launch`。重点检查：

- `<arg>` 默认值和 include 传参；
- group namespace；
- remap；
- machine / respawn / required；
- node name 冲突；
- pkg/type 可执行文件是否存在；
- YAML/rosparam 加载顺序；
- env-loader 与多机环境。

运行时可用 `roslaunch --args`、`roslaunch --nodes` 辅助展开，不使用 ROS 2 Python launch 语义代替。

## roscpp / rospy 并发

### roscpp

重点区分：

- `ros::spin()` 单线程；
- `ros::AsyncSpinner`；
- `ros::MultiThreadedSpinner`；
- 默认 callback queue 与自定义 callback queue；
- callback 内阻塞 I/O、service call、sleep、锁等待。

### rospy

关注 subscriber/service/timer 的线程行为、Python GIL、阻塞 I/O、长回调与共享状态同步。不要使用 ROS 2 executor/callback group 概念解释 Noetic 并发。

## nodelet / pluginlib

nodelet 用于同进程零拷贝/少拷贝组合。检查：

```bash
rosnode list
rosnode info /nodelet_manager
```

并核对：

- manager 是否存在；
- plugin XML 导出；
- class 名称；
- nodelet load/unload；
- 同进程崩溃的故障域；
- 大消息链路是否真的在同 manager。

## TF / tf2

Noetic 可同时存在 tf 与 tf2_ros 工具链。优先检查 frame 名、变换方向、时间戳、静态/动态发布者唯一性和缓存窗口。不要默认 ROS 2 `/tf_static` QoS 语义。

## diagnostics

可使用 `diagnostic_updater` / `/diagnostics` 建立长期可观察性。对频率、延迟、丢包、传感器健康、队列长度和算法状态优先定义稳定字段，而不是临时日志文本。

## EOL 约束

ROS Noetic 已 EOL。安装或部署问题必须区分：

- 原官方 apt 仓库是否仍可用；
- Ubuntu 20.04 基础镜像/依赖来源；
- 第三方 PPA/源码依赖；
- Python 3 兼容；
- OpenSSL/Gazebo/PCL/OpenCV 等系统依赖版本；
- 是否需要容器冻结环境。

不要用 ROS 2 当前支持状态推断 Noetic 的安全性或依赖可用性。
