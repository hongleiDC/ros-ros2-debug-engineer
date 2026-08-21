# ROS Noetic 时间与同步

## 时间模型

Noetic 中必须区分至少以下时间：

| 时间 | 含义 | 常见来源 |
|---|---|---|
| measurement time | 传感器真实采样/曝光/扫描时刻 | 设备时钟、GNSS、驱动转换 |
| `header.stamp` | ROS message 声明的测量时间 | driver |
| point time / offset | 点相对帧的采样时刻 | LiDAR packet/driver |
| callback arrival | 消息到达节点 callback 的主机时刻 | `ros::WallTime`/系统时间 |
| bag record time | rosbag recorder 接收/写入时刻 | rosbag1 |
| ROS time | `ros::Time` / `rospy.Time` | wall time 或 `/clock` |
| wall/steady time | 单调/系统计时 | timeout、性能、日志 |

不要用 `ros::Time::now()` 或 callback 到达时间替代设备 measurement time，除非驱动语义本来就是“接收即采样”。

## `/use_sim_time` 与 `/clock`

rosbag1 回放时明确：

```bash
rosparam get /use_sim_time
rosbag play --clock data.bag
```

使用 simulated ROS time 的节点必须在启动/初始化路径上正确看到 `/use_sim_time=true`。检查 timer、TF lookup、timeout 和状态机是否依赖 ROS time；bag loop 会导致 ROS time 回退，不能默认所有算法都能安全处理。

## 必查项

1. 为每个关键 topic 定义 authoritative measurement time。
2. 区分设备时钟、GNSS、PTP/NTP/chrony、主机系统时钟和 ROS time。
3. 明确 GPS/UTC/Unix、week rollover、leap second 和时区转换。
4. 明确 frame stamp 对应扫描起点、中点还是终点；相机对应曝光哪个时刻。
5. 点级 time 通常是相对量，必须定义单位和参考点。
6. offset 明确符号和应用位置，例如：

```text
t_lidar_corrected = t_lidar_raw + offset_lidar_to_imu
```

7. 区分 fixed offset、linear drift、clock jump、重启归零、wraparound、乱序、重复和 bag loop 回退。
8. `message_filters` queue/slop、TCPROS 延迟和 callback backlog 不等于传感器时间偏移。

## Noetic 同步工具语义

使用 `message_filters::TimeSynchronizer` 或 `ApproximateTime` 时，先确认它只是按 `header.stamp` 匹配消息，不会修复错误的传感器时间。扩大 ApproximateTime slop 只能放宽配对条件，不能证明真实同步改善。

多 topic 组合 GNSS position/status/heading 或多传感器数据时，证明它们来自同一测量周期或在明确窗口内。能由驱动发布原子 measurement message 时，优先原子消息而不是下游猜测同步。

## 诊断

运行时可按需使用：

```bash
rostopic delay /topic
rostopic hz /topic
rosbag info data.bag
```

但 `rostopic delay` 依赖 message header 和本机时间，仅是链路/时间一致性的一个证据，不等价于真实设备同步误差。

建议保存足够样本统计 count、mean、median、std、P95、P99、max、趋势和运动相关性。单帧不能确认同步。

## 融合与可观测性

若 time offset 与外参、速度、deskew、IMU bias 或状态估计强耦合，先检查可观测性。优化器给出的 offset 只是模型下的估计，不自动等于真实硬件时钟差。

时间修复验证至少需要：

- 不再出现时间回退/乱序异常；
- 相同 rosbag/路线下融合残差或轨迹指标改善；
- 不通过扩大同步窗或静默丢弃掩盖问题；
- 多段数据/不同运动状态下结果一致。
