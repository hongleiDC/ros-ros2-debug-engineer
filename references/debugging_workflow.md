# ROS Noetic 调试工作流

本文件只用于 **ROS 1 Noetic**。若 `ROS_VERSION`、`ROS_DISTRO` 或 `rosversion -d` 与 `1/noetic/noetic` 不一致，先处理版本不匹配，不继续套用 Noetic 诊断模型。

## 1. 固化条件

先记录：仓库、branch、commit、dirty 状态、catkin workspace、overlay/source 顺序、Ubuntu/容器、Python/C++ 工具链、`ROS_MASTER_URI`、`ROS_IP` / `ROS_HOSTNAME`、launch 命令、参数文件、rosbag1 哈希、设备/固件、错误日志和发生时间。

一次只改变一个主要变量。没有可比条件时，不做“改了以后似乎更好”的结论。

## 2. 建立事实与假设

先列已观察事实，再维护最多三个活动假设。每个假设写清：

- 支持证据；
- 反证；
- 最小区分检查；
- 通过/失败判据。

每个命令都必须能确认或排除至少一个假设。

## 3. 按最早失败层定位

### 3.1 Noetic 环境与 overlay

优先确认：

```bash
printenv ROS_VERSION ROS_DISTRO ROS_MASTER_URI ROS_IP ROS_HOSTNAME
rosversion -d
rospack profile
```

检查 `/opt/ros/noetic/setup.bash` 与各 workspace `devel/setup.bash` / `install/setup.bash` 的 source 顺序，避免从错误 overlay 解析 package、message 或共享库。

### 3.2 catkin 构建与导出

只处理第一个真实编译/链接错误，再看后续级联。检查：

- `package.xml` 与 `CMakeLists.txt` 依赖是否一致；
- `find_package(catkin REQUIRED COMPONENTS ...)`；
- `catkin_package(...)` 的 include/library/CATKIN_DEPENDS；
- message/service/action generation；
- dynamic_reconfigure generation；
- nodelet/pluginlib 导出；
- Python 可执行权限和 `catkin_install_python`；
- build/devel/install 是否来自同一 workspace/commit。

### 3.3 roslaunch 与参数

核对最终 node name、namespace、remap、`<arg>`、`<group ns>`、`<include>` 传参、private 参数 `~param`、YAML 加载顺序、`respawn` / `required` 和可执行文件路径。

进程启动不等于节点 ready；master 中有注册也不等于算法已进入正常工作状态。

### 3.4 ROS master 与多机网络

先区分“注册/发现”和“数据链路”：

```bash
rosnode list
rosnode info /node
rostopic list
rostopic info /topic
rosservice list
roswtf
```

`rosnode list` 正常只证明 XML-RPC/master 注册可见。若跨主机无数据，再检查：

- `ROS_MASTER_URI` 是否一致；
- `ROS_IP` / `ROS_HOSTNAME` 是否能被其他主机解析并回连；
- `/etc/hosts` / DNS；
- 防火墙、VPN、NAT、Docker 网络；
- 进程实际继承的环境；
- 随机 TCPROS 端口是否可达。

### 3.5 Topic / Service / Actionlib

无 topic 数据时优先区分：

1. 名称/namespace/remap；
2. message type 与 MD5；
3. publisher/subscriber 是否真的建立连接；
4. TCPROS/UDPROS 网络；
5. publisher/subscriber `queue_size`、处理速率与积压；
6. latch / late subscriber 语义；
7. callback 是否被线程、锁或 I/O 阻塞；
8. 应用层时间/TF/status gate 是否主动丢弃。

只读检查按需使用：

```bash
rostopic type /topic
rostopic info /topic
rostopic hz /topic
rostopic delay /topic
rostopic bw /topic
rosservice info /service
```

Actionlib 按 goal/cancel/status/feedback/result 这组 topic 和状态机检查，不把它当普通单次 service。

### 3.6 Spinner、CallbackQueue 与 nodelet

检查：

- `ros::spin()`、`ros::AsyncSpinner`、`ros::MultiThreadedSpinner`；
- 默认与自定义 `ros::CallbackQueue`；
- callback 内同步 service/action 等待、磁盘/网络 I/O、sleep 和锁；
- 多锁顺序与 shutdown/join；
- nodelet manager 的线程池、插件加载和共享故障域；
- rospy 长 callback、阻塞 I/O 与共享状态同步。

先证明处理能力和队列行为，再扩大 queue；不要用更多线程掩盖阻塞机制。

### 3.7 数据语义

检查字段、单位、坐标轴、NaN/Inf、协方差、状态码、饱和、丢包、重复、乱序和多 topic 是否同一测量周期。

### 3.8 时间与同步

区分设备时间、`header.stamp`、callback 到达时间、bag 记录时间、ROS time、system/wall time。检查 `/use_sim_time`、`/clock`、固定 offset、drift、wraparound、重启归零和时间回退。

不要把 message_filters slop、queue depth 或网络延迟直接当传感器时间偏移。

### 3.9 TF 与标定

检查 frame 语义、变换方向、authority、静态/动态发布者唯一性、时间戳、缓存窗口、past/future extrapolation、URDF 与实际安装外参。

### 3.10 性能与资源

检查 CPU、内存、磁盘、网络、序列化/复制、nodelet 是否真的减少复制、callback 时长、队列增长、锁竞争和 rosbag 录制开销。

### 3.11 算法与数值

只有上游环境、通信、时间、TF 和数据语义有证据正常后，才进入初始化、噪声、门限、退化、可观测性、鲁棒核、条件数和异常输入。

## 4. 最小区分实验

优先做信息增益高、改动小、可回滚的检查，例如：

- `rostopic info` + 两端 `rosnode info` 区分名称/连接问题与算法问题；
- 在隔离 roscore 上用固定短 `.bag` 区分现场设备问题与软件问题；
- 临时将发布/订阅放到同机，区分多机网络与消息/算法问题；
- 只禁用一个重复 TF 发布者，验证 frame 跳变是否消失；
- 输出每种应用层丢弃原因计数，而不是单纯扩大 queue；
- 比较 `header.stamp`、bag record time 与 callback 时间分布，而不是只看一帧；
- 对 nodelet 问题临时改为独立 node 或单插件 manager，区分共享进程/线程池故障。

## 5. 最小修复

补丁必须直接针对已验证机制。避免在同一次修复中同时重构、升级依赖、改通信拓扑和调算法参数。

新增诊断优先使用节流日志、计数器或 `/diagnostics`，并让低成本观测在问题解决后仍可保留。

## 6. 回归与停止

按任务选择最小充分验证：

- 目标 package 构建成功；
- 节点/插件无异常退出；
- 关键 topic/service/action 名称、类型、MD5 和连接符合预期；
- 参数与 namespace 加载正确；
- TF 唯一、连通且目标时间可查询；
- 时间差、频率、丢弃和延迟进入判据；
- 相同 rosbag1/输入下历史故障不再复现；
- CPU、内存、网络、控制安全没有明显回归。

根因解释关键现象且同条件验证通过后停止扩大范围。架构债务若与当前故障无直接关系，只记录为后续建议。
