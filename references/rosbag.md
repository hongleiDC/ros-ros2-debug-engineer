# ROS Noetic rosbag1 调试

本文件仅适用于 ROS 1 Noetic 的 `rosbag`（rosbag1），不是 rosbag2。处理 bag 时按 **metadata → topic inventory → message definition → representative sample → time/TF → replay** 的顺序，不要一上来回放。

## 1. 首先确认 bag 里到底有什么

```bash
rosbag info run.bag
rosbag info -y run.bag
rostopic list -b run.bag
```

需要结构化 topic 信息时可运行：

```bash
python3 scripts/inspect_rosbag.py run.bag --metadata-only
```

至少建立：

- duration、start/end、size、message count；
- topic 名称；
- topic type；
- 每个 topic 的 messages/frequency；
- message definitions / MD5；
- 是否包含 `/tf`、`/tf_static`、`/clock`；
- 是否包含控制类 topic；
- 是否有预期传感器 topic 缺失或意外 topic。

## 2. 对关键 topic 抽取代表性消息

不要对 PointCloud2/Image 等大 topic 持续输出。只抽样：

```bash
rostopic echo -b run.bag -n 1 /imu/data
rostopic echo -b run.bag -n 1 /points_raw
```

或：

```bash
python3 scripts/inspect_rosbag.py run.bag --topic /imu/data --topic /points_raw
```

拿到类型后继续：

```bash
rosmsg show sensor_msgs/Imu
rosmsg show sensor_msgs/PointCloud2
rosmsg md5 sensor_msgs/Imu
```

对关键消息至少判断：

- `header.stamp`；
- `header.frame_id`；
- status/quality/covariance；
- PointCloud2 `fields`；
- GNSS fix/heading 状态；
- IMU orientation/covariance 是否有效；
- topic 与当前 driver/hardware 的命名和字段是否一致。

不要假设不同 LiDAR driver 都使用相同的 `ring/time/timestamp` 字段；必须读 bag 实际字段。

## 3. 录制前

记录：

- `ROS_VERSION=1`、`ROS_DISTRO=noetic`；
- bag 文件路径和命名；
- topic 白名单/排除规则；
- `--split`、`--size`、`--duration`、`--bz2` / `--lz4`；
- 主机时间状态；
- 设备配置、参数快照和代码 commit；
- 是否包含 `/tf`、`/tf_static`、`/clock`、控制 topic。

典型命令：

```bash
rosbag record -O run.bag /imu/data /points_raw /tf /tf_static
rosbag info run.bag
```

## 4. 时间与完整性分析

检查：

- `header.stamp` 与 bag record time 的差值；
- 频率、间隔分布、burst、gap、乱序和重复；
- `/tf`、`/tf_static`、`/clock`；
- 自定义消息包和 MD5 是否匹配；
- bag 是否未正常关闭、需要 `rosbag reindex`；
- 压缩与 split bag 是否完整。

可用：

```bash
rosbag check run.bag
rosbag reindex run.bag
```

需要程序化深入分析时优先使用 Noetic 的 Python `rosbag` API，而不是 rosbag2 storage API。对于 header/bag time 差、点云字段统计、GNSS fix distribution 等，建议编写一次性只读分析脚本并保存输出，而不是靠人工滚动 `echo`。

## 5. 与硬件/系统适配关联

bag 不只是数据文件，也是采集系统的证据。把 bag inventory 与 [硬件适配与系统勘察](hardware_adaptation.md) 的事实表比较：

```text
硬件
→ driver/node
→ expected topic
→ bag topic
→ message type/fields
→ frame
→ timestamp source
→ calibration
```

重点发现：

- 换过 LiDAR/IMU/GNSS 后 bag 仍使用旧字段或旧 frame；
- driver 版本变化导致 custom msg schema 变化；
- bag 来自另一台车/另一套标定；
- `/tf_static` 与当前 launch 同时发布造成重复；
- bag 没有 `/clock` 但 replay 配置假设 sim time；
- 控制 topic 混在传感器 bag 中。

## 6. 回放

1. 默认隔离真实执行器和控制 topic。
2. 明确 `/use_sim_time`、`--clock`、`-r/--rate`、`-s/--start`、`-d/--duration`、`--pause`、`-l/--loop`。
3. 回放前确认 launch 是否会重复发布 `/tf_static` 或其他固定数据。
4. 检查 bag 中是否包含 `/cmd_vel`、trajectory、actuator、mission 等控制类 topic；未经授权不要回放到真实系统。
5. loop 会导致仿真时间回退，算法必须明确处理或禁止 loop。
6. 回放问题不要使用 ROS 2 QoS override 解释；Noetic 没有 rosbag2 QoS override 文件机制。

典型命令：

```bash
rosparam set /use_sim_time true
rosbag play run.bag --clock --pause
```

先 pause 启动可以让工程师确认 graph/TF/订阅关系，再继续播放。

## 7. A/B 回归

baseline/candidate 必须保持：

- 同一 `.bag` 和 hash；
- 同一回放 rate/start/duration；
- 同一 launch 与参数加载方式；
- 同一 TF/static transform 来源；
- 同一指标、对齐和时间定义。

至少区分静态包、短运动包、完整线路包和异常包。保存 bag ID、哈希、录制配置、适用 commit、采集硬件、预期指标和已知限制，不把大型 bag 本体打包进 Skill。
