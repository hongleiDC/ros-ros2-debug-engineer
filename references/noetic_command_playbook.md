# ROS Noetic 命令作战手册

本文件用于 **ROS 1 Noetic 实际系统的只读发现、定位与证据采集**。目标不是背命令，而是根据当前问题选择最小、最有区分力的一组命令，并把 Linux/ROS/bag 三层证据对应起来。

## 目录

1. 首次接触系统
2. 环境、workspace 与 package
3. ROS master、node 与 graph
4. Topic
5. Service 与 actionlib
6. 参数与 roslaunch
7. TF 与时间
8. rosbag1
9. 日志、diagnostics 与 GUI
10. 构建与二进制
11. 多机网络
12. 命令使用原则

## 1. 首次接触系统

第一次进入陌生机器、陌生仓库或陌生运行现场时，不要直接猜算法问题。按下面顺序建立事实模型：

```bash
printenv ROS_VERSION ROS_DISTRO ROS_MASTER_URI ROS_IP ROS_HOSTNAME
rosversion -d
pwd
git status --short --branch
git rev-parse HEAD
printenv ROS_PACKAGE_PATH CMAKE_PREFIX_PATH PYTHONPATH
rosnode list
rostopic list
rosservice list
rosparam list
```

再根据问题读取：

- 系统/硬件：见 `hardware_adaptation.md`；
- bag：见 `rosbag.md`；
- TF：见 `tf_calibration.md`；
- 时间：见 `time_sync.md`。

不要一次执行所有命令。首次建模可以较完整；后续刷新只重查发生变化的层。

## 2. 环境、workspace 与 package

### 环境

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
which roscore roslaunch rosrun rostopic rosbag
python3 --version
```

### overlay 与路径

```bash
printenv ROS_PACKAGE_PATH
printenv CMAKE_PREFIX_PATH
printenv PYTHONPATH
```

如果怀疑 source 顺序错误，记录每次：

```bash
source /opt/ros/noetic/setup.bash
source /path/to/ws/devel/setup.bash
```

### package 定位

```bash
rospack find PACKAGE
rospack depends1 PACKAGE
rospack depends PACKAGE
rospack plugins --attrib=plugin nodelet
```

不要只看仓库中“存在一个同名 package”；以当前 shell 的 `rospack find` 结果作为实际解析证据。

## 3. ROS master、node 与 graph

```bash
rosnode list
rosnode list -a
rosnode info /node_name
rosnode ping /node_name
rosnode machine HOSTNAME
roswtf
```

必要时使用：

```bash
rqt_graph
```

区分三件事：

1. master 中是否注册；
2. XML-RPC 是否能回连到 node；
3. TCPROS/UDPROS 数据路径是否真正建立。

`rosnode list` 成功不等于 topic 数据链路正常。

## 4. Topic

### 先做 inventory

```bash
rostopic list
rostopic list -v
rostopic find sensor_msgs/Imu
```

### 再查单 topic 结构

```bash
rostopic info /topic
rostopic type /topic
rosmsg show PACKAGE/Message
rosmsg md5 PACKAGE/Message
```

### 再查数据是否健康

```bash
rostopic hz /topic
rostopic bw /topic
rostopic delay /topic
rostopic echo -n 1 /topic
```

对于 PointCloud2、Image 等大消息，不默认整条持续 `echo`。优先：

```bash
rostopic echo -n 1 /points_raw/header
rostopic echo -n 1 /points_raw/fields
rostopic hz /points_raw
rostopic bw /points_raw
```

对于 header-bearing 消息，至少核对：

- `header.stamp`；
- `header.frame_id`；
- 频率与 jitter；
- `rostopic delay`；
- 消息类型与 MD5；
- publisher/subscriber 数量；
- 是否被 namespace/remap 改名。

### 发布命令

`rostopic pub` 会改变系统状态。只有用户明确授权且确认不会驱动执行器时才使用：

```bash
rostopic pub -1 /test std_msgs/String "data: 'hello'"
```

不要在未知机器人上对 `/cmd_vel`、控制器、trajectory、mission、actuator topic 做试探发布。

## 5. Service 与 actionlib

### Service

```bash
rosservice list
rosservice info /service
rosservice type /service
rossrv show PACKAGE/Service
```

`rosservice call` 是写操作；只有明确授权后执行。

### actionlib

ROS 1 actionlib 通常可通过以下 topic 观察：

```text
/<action>/goal
/<action>/cancel
/<action>/status
/<action>/feedback
/<action>/result
```

先检查：

```bash
rostopic info /ACTION/status
rostopic hz /ACTION/status
rostopic echo -n 1 /ACTION/status
```

不要因为 action client 等不到结果就直接判定算法失败；先确认 server、namespace、goal/status/result 链路和时间状态。

## 6. 参数与 roslaunch

### 参数

```bash
rosparam list
rosparam get /namespace
rosparam get /node_name/param
rosparam dump /tmp/params.yaml /namespace
```

`rosparam set/load/delete` 会修改运行状态，默认不执行。

区分：

- global `/name`；
- relative `name`；
- private `~name`；
- launch 中 `<param>` 与 `<rosparam>`；
- 节点启动时只读一次的参数；
- dynamic_reconfigure 运行时参数。

### roslaunch

```bash
roslaunch PKG FILE.launch --args
roslaunch --nodes PKG FILE.launch
roslaunch --find-node NODE PKG FILE.launch
```

启动前重点展开：

- `<include>`；
- `<arg>`；
- `<group ns=...>`；
- `<remap>`；
- `<param>` / `<rosparam>`；
- `machine` / `respawn` / `required`；
- node `pkg` / `type` / `name`。

## 7. TF 与时间

### TF

```bash
rosrun tf tf_echo PARENT CHILD
rosrun tf tf_monitor
rosrun tf view_frames
```

若项目使用 tf2 工具：

```bash
rosrun tf2_ros tf2_echo PARENT CHILD
rosrun tf2_tools view_frames.py
```

不要只确认“有 TF”。同时检查方向、authority、时间、静态/动态重复发布者和缓存窗口。

### 时间

```bash
rosparam get /use_sim_time
rostopic echo -n 1 /clock
rostopic delay /imu/data
```

系统时间/PTP/NTP 检查见 `hardware_adaptation.md` 与 `time_sync.md`。

## 8. rosbag1

先 metadata，再 topic，再样本，最后才考虑 replay：

```bash
rosbag info run.bag
rosbag info -y run.bag
rosbag info -y -k topics run.bag
rostopic list -b run.bag
rostopic echo -b run.bag -n 1 /imu/data
```

拿到消息类型后继续：

```bash
rosmsg show sensor_msgs/Imu
rosmsg md5 sensor_msgs/Imu
```

回放前再决定：

```bash
rosparam set /use_sim_time true
rosbag play run.bag --clock --pause
```

完整 bag 方法见 `rosbag.md`。

## 9. 日志、diagnostics 与 GUI

```bash
rosnode info /node
rostopic echo /rosout
rostopic echo /diagnostics
rqt_console
rqt_logger_level
rqt_plot
rqt_topic
rqt_graph
```

优先稳定诊断量而不是无限追加日志。日志级别修改属于运行状态变更，执行前确认影响。

## 10. 构建与二进制

### catkin_tools

```bash
catkin config
catkin list
catkin build PACKAGE
catkin build PACKAGE --no-deps
```

### catkin_make

```bash
catkin_make
catkin_make --pkg PACKAGE
```

### 可执行文件与链接

```bash
rosrun PACKAGE EXECUTABLE --help
which EXECUTABLE
ldd /path/to/binary
file /path/to/binary
```

构建问题至少区分：dependency resolution、message generation、include、link、plugin export、Python import、overlay 污染。

## 11. 多机网络

```bash
printenv ROS_MASTER_URI ROS_IP ROS_HOSTNAME
hostname
hostname -I
ip -br addr
ip route
getent hosts HOSTNAME
ping -c 3 HOSTNAME
```

必要时再使用更重的网络证据：

```bash
ss -lntup
tcpdump -ni INTERFACE HOST SENSOR_IP
```

`tcpdump` 可能需要权限，且会产生较大输出；只有网络链路确实是活动假设时使用。

## 12. 命令使用原则

1. **先问命令要区分什么假设。** 不机械跑全套。
2. **优先只读。** list/info/type/hz/bw/delay/echo 少量样本优先于 pub/call/set/play。
3. **高带宽 topic 限样本。** PointCloud2/Image 不持续 `echo`。
4. **保留上下文。** 命令输出要和 branch、commit、launch、参数、主机、硬件、bag 对应。
5. **刷新而不是重来。** branch、launch、硬件、网络、bag 或修复变化后，只刷新受影响的证据域。
6. **不要把 CLI 可见性当正确性。** 可见 node/topic 只是下一步诊断入口。
7. **用户给出现场输出后继续推理。** 不重复要求用户执行已经有充分证据覆盖的命令。
