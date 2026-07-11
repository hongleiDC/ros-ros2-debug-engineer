# 时间与同步规则

## 时间类型

| 时间 | 含义 | 是否可直接融合 |
|---|---|---|
| 包内测量时间 | 传感器实际测量时刻 | 首选 |
| `header.stamp` | 驱动声明的消息时间 | 需确认来源 |
| 点级 `time/offset_time` | 点相对帧时刻 | LiDAR deskew 必需 |
| callback 到达时间 | 节点收到消息的时刻 | 否，仅诊断延迟 |
| bag 记录时间 | rosbag 写入消息的时刻 | 否，除非证明等价 |
| `/clock` | bag/simulation 的 ROS 时间 | 驱动定时与回放使用 |
| wall time | 主机系统时钟 | 不与传感器测量时间混用 |

## 强制规则

1. 为每个 topic 记录 authoritative time source。
2. RTK 优先使用 GPS week + seconds-of-week 或同等包内测量时间；禁止用 `now()` 代替。
3. 从 GPS 时间转换到 Unix/UTC 时显式处理时间尺度、周数、闰秒和时区；保存原始值用于追溯。
4. LiDAR 帧时间和点级时间分开记录。点级时间通常是相对量，不得写成绝对 Unix 时间后仍按 offset 使用。
5. `delay_time` 表示等待缓冲区数据覆盖范围，不等于传感器时间偏移。
6. 时间偏移必须声明符号，例如：

```text
t_lidar_corrected = t_lidar_raw + offset_lidar_to_imu
```

7. 使用分布统计验证偏移：样本数、均值、中位数、P95、最大值和随时间趋势。
8. 多话题拼接 RTK position/status/heading 时，必须证明来自同一数据包或在允许时间窗内；优先发布一个原子 measurement 消息。
