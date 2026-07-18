# 时间与同步

## 时间类型

| 时间 | 含义 | 用途 |
|---|---|---|
| 包内测量时间 | 传感器真实测量或曝光/扫描时刻 | 融合首选 |
| `header.stamp` | 驱动声明的消息时间 | 必须确认来源 |
| 点级 `time/offset_time` | 点相对帧的采样时刻 | LiDAR deskew |
| callback 到达时间 | 中间件交付给节点的时刻 | 延迟诊断 |
| bag 记录时间 | recorder 写入时刻 | 录制链路诊断 |
| `/clock` | 仿真或 bag 的 ROS time | 定时器和回放 |
| system/wall time | 系统实时时钟 | 日志和跨机同步 |
| steady time | 单调时钟 | duration、timeout 和性能 |

## 必查项

1. 为每个关键 topic 记录 authoritative measurement time。
2. 区分时钟域：设备时钟、GNSS、PTP、NTP/chrony、主机系统时钟和 ROS time。
3. 明确时间尺度和转换：GPS、UTC、Unix、week rollover、leap second 和时区。
4. 明确帧时间对应扫描起点、中点还是终点；相机时间对应曝光起点、中点或结束。
5. 点级时间通常是相对量，不得误当绝对时间。
6. offset 必须定义符号和应用位置，例如：

```text
t_lidar_corrected = t_lidar_raw + offset_lidar_to_imu
```

7. 区分固定 offset、线性 drift、时钟跳变、重启归零、wraparound、乱序和 bag loop 回退。
8. `delay_time`、queue depth 和 message_filters slop 不等于传感器时间偏移。

## 验证

使用足够样本统计 count、mean、median、std、P95、P99、max、随时间趋势和运动相关性。只看单帧无法确认同步。

多 topic 拼接 position/status/heading 时，证明它们来自同一测量周期或在明确时间窗内。优先使用原子 measurement 消息。

如果 offset 与外参、速度、deskew 或算法状态强耦合，先检查可观测性，不把优化得到的数值直接当作真实硬件时间差。
