# ROS/ROS2 调试工作流

## 1. 固化复现条件

记录 ROS 发行版、工作空间、分支和 commit、构建命令、launch 参数、参数 YAML、bag 哈希、设备固件和错误日志。不要在复现前同时修改多个变量。

## 2. 分层定位

### 构建层

检查依赖、消息生成顺序、链接库、C++ 标准、overlay 顺序和旧缓存。

ROS1 常用：

```bash
rosversion -d
catkin_make -DCMAKE_BUILD_TYPE=RelWithDebInfo
rospack find <package>
```

ROS2 常用：

```bash
ros2 doctor --report
colcon build --symlink-install --event-handlers console_direct+
colcon list
```

### 节点与连接层

确认进程存在、订阅发布双方匹配、命名空间和 remap 正确。

```bash
rosnode list
rostopic list
rostopic type /topic
rostopic info /topic
```

```bash
ros2 node list
ros2 topic list -t
ros2 topic info /topic -v
```

### QoS 层（ROS2）

传感器常使用 best effort。发布者和订阅者 reliability/durability 不兼容时，话题存在但收不到数据。优先查看 `ros2 topic info -v`，不要只看 `ros2 topic list`。

### 数据层

检查频率、字段、NaN、单位、轴方向、协方差、状态码和消息是否来自同一测量周期。

### 时间层

打印每条链路的 authoritative measurement time、header stamp、bag time 和 callback time。计算差值分布，不只看单帧。遵守 `time_sync.md`。

### TF/标定层

检查 frame 拼写、树是否断裂、是否重复发布静态 TF、外参方向和单位。bag 自带 `/tf_static` 时避免 launch 重复发布。

### 算法层

只有上层全部通过后才调整门限、噪声、体素、迭代次数或鲁棒核。调整必须有 before/after 指标。

## 3. 最小修复

优先添加诊断计数器和节流日志：收到消息数、丢弃原因、时间差、状态门限、最近有效时间、匹配对数量。修复后依次运行：静态包 → 短运动包 → 完整线路包。

## 4. 回归要求

至少验证：

- 节点无崩溃；
- 关键 topic 频率和消息数量；
- TF 唯一且连续；
- 时间差进入门限；
- 初始化成功；
- 输出轨迹连续；
- 历史 incident 不再复现。
