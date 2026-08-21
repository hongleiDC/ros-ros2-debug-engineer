# ROS Noetic rosbag1 调试

本文件仅适用于 ROS 1 Noetic 的 `rosbag`（rosbag1），不是 rosbag2。

## 录制前

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

## 分析

检查：

- duration、message count、topic type；
- `header.stamp` 与 bag record time 的差值；
- 频率、间隔分布、burst、gap、乱序和重复；
- `/tf`、`/tf_static`、`/clock`；
- 自定义消息包和 MD5 是否匹配；
- bag 是否未正常关闭、需要 `rosbag reindex`；
- 压缩与 split bag 是否完整。

可用：

```bash
rosbag info run.bag
rosbag check run.bag
rosbag reindex run.bag
```

需要程序化读取时优先使用 Noetic 的 Python `rosbag` API，而不是 rosbag2 storage API。

## 回放

1. 默认隔离真实执行器和控制 topic。
2. 明确 `use_sim_time`、`--clock`、`-r/--rate`、`-s/--start`、`-d/--duration`、`--pause`、`-l/--loop`。
3. 回放前确认 launch 是否会重复发布 `/tf_static` 或其他固定数据。
4. 检查 bag 中是否包含 `/cmd_vel`、trajectory、actuator、mission 等控制类 topic；未经授权不要回放到真实系统。
5. loop 会导致仿真时间回退，算法必须明确处理或禁止 loop。
6. 回放问题不要使用 ROS 2 QoS override 解释；Noetic 没有 rosbag2 QoS override 文件机制。

典型命令：

```bash
rosparam set use_sim_time true
rosbag play run.bag --clock -r 1.0
```

## A/B 回归

baseline/candidate 必须保持：

- 同一 `.bag`；
- 同一回放 rate/start/duration；
- 同一 launch 与参数加载方式；
- 同一 TF/static transform 来源；
- 同一指标、对齐和时间定义。

至少区分静态包、短运动包、完整线路包和异常包。保存 bag ID、哈希、录制配置、适用 commit、预期指标和已知限制，不把大型 bag 本体打包进 Skill。
