# ROS Noetic 快速调试

## 何时读取

只在 `standard` 或 `domain` 调试中读取。`micro` 问题直接处理，不加载本文件。

## 先确认版本

任何命令或补丁前先确认：

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

本文件仅适用于 `ROS_VERSION=1`、`ROS_DISTRO=noetic`。

## 紧凑状态

任务中只维护五行以内：

```text
环境: ROS Noetic / Ubuntu 20.04 / catkin
范围: localization_bringup -> imu_filter
现象: /imu/data 有发布，滤波节点无输出
首要假设: callback 阻塞或 TF/time gate 丢弃
下一检查: rostopic info + rosnode info + 时间戳/TF
```

## 故障分层

按最早失败层定位：

| 层 | 典型现象 | 首选证据 |
|---|---|---|
| catkin 构建 | package、符号、消息生成或依赖错误 | 第一个真实错误、package.xml/CMakeLists、workspace overlay |
| roslaunch/配置 | 节点未启动、参数不生效 | launch XML、arg/include、namespace/remap、rosparam |
| ROS master/图连接 | 节点/topic/service 注册异常 | `rosnode list/info`、`rostopic info`、`rosservice info`、`roswtf` |
| 通信 | 有端点但无数据 | 类型/MD5、TCPROS/UDPROS、网络、频率、callback |
| TF/时间 | extrapolation、跳变、不同步 | frame tree、stamp、缓存窗口、系统时钟 |
| 线程/资源 | 延迟、卡死、掉帧 | spinner、callback queue、锁、I/O、CPU/内存 |
| 数据/算法 | 数值异常、漂移、发散 | 单位、frame、输入分布、边界和不变量 |

上层未证明正常时，不直接调算法参数。

## 假设与检查

最多保留三个活动假设：最可能、次可能、低概率高风险。优先检查能一次区分多个假设的证据。

每个命令必须确认或排除至少一个假设。最多询问一个会改变调试方向的关键问题。

## 高频检查

### catkin 构建

- 只处理第一个真实错误，后续通常是级联；
- 核对 `source /opt/ros/noetic/setup.bash` 与 workspace `devel/setup.bash` 顺序；
- 区分 `catkin_make`、`catkin build`、isolated workspace；
- 自定义消息核对 `message_generation` / `message_runtime`、`add_message_files`、`generate_messages`、`catkin_package`；
- C++ 链接核对 `target_link_libraries`、`catkin_LIBRARIES`、导出依赖。

### roslaunch 与参数

- 核对 `<arg>`、`<include>`、`<group ns>`、`<remap>`；
- 核对最终 node 名和 namespace；
- 核对 private 参数 `~param` 与 NodeHandle namespace；
- 用 `rosparam get` 验证实际加载值；
- 进程存在不等于节点逻辑已健康，查看 node 日志和 diagnostics。

### ROS master 与通信

```bash
rosnode list
rosnode info /node
rostopic list
rostopic info /topic
rostopic type /topic
rostopic hz /topic
rostopic bw /topic
rosservice list
rosservice info /service
roswtf
```

重点核对：名称/remap、消息类型和 MD5、多机 `ROS_MASTER_URI`/`ROS_IP`/`ROS_HOSTNAME`、DNS/hosts、网络可达性。

Noetic 不使用 ROS 2 QoS compatibility 作为诊断模型。

### TF 与时间

- 明确变换方向和查询时刻；
- 核对 header stamp 是硬件采样、接收还是系统时间；
- 区分 transform 不存在、太旧、来自未来和外参方向错误；
- 多机必须检查系统时钟同步；
- bag 回放时检查 `/clock` 与 `use_sim_time`。

### 线程与性能

- roscpp 明确 `ros::spin()`、`AsyncSpinner`、`MultiThreadedSpinner` 和 callback queue；
- rospy 检查长回调、阻塞 I/O、GIL 和共享状态；
- 查 callback 中磁盘、网络、同步 service、sleep、锁和重计算；
- 检查队列积压、无界缓存和大消息复制；
- nodelet 链路核对是否真的在同一个 manager。

### 算法

- 先核对单位、frame、符号、索引和时间对齐；
- 用固定输入或手算样例验证一个不变量；
- 参数调节不能替代输入、坐标或时间错误的修复。

## 代码阅读预算

初始通常只读：一个 package/构建文件、一个 launch/参数文件、发布与订阅关键实现，必要时再读一个消息或算法文件。只有现有证据无法区分假设时才扩大范围。

## 修改、验证与停止

修改前用一句话说明补丁验证什么根因。修改后先做最小验证：单 package 构建、单元测试/rostest、单 launch、短时 topic/TF/参数检查或同一 rosbag1 前后对比。

根因解释关键现象且同条件不再复现：停止。架构债务与当前故障无直接关系时，只列为后续建议。证据不足时，只提出下一项最有区分度的检查。
