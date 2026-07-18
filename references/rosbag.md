# rosbag 调试

## 录制前

记录 ROS 版本、storage plugin、compression、split 配置、topic 白名单、QoS override、主机时间状态、设备配置和代码 commit。

## 分析

检查：

- metadata、duration、message count、topic type 和 serialization format；
- bag record time 与 header/packet time 的差值；
- 频率、间隔分布、burst、gap、乱序和重复；
- `/tf`、`/tf_static`、`/clock` 和参数事件；
- 自定义消息包是否可用；
- sqlite3、MCAP、压缩和分包是否完整；
- bag 是否需要 reindex 或存在 metadata 损坏。

## 回放

1. 默认隔离现场系统，并使用 topic 白名单。
2. 明确 `use_sim_time`、`--clock`、rate、start offset、loop 和 pause。
3. 检查 QoS override，特别是 transient local、sensor data 和 late joiner。
4. 避免 bag 中 `/tf_static` 与 launch 重复发布。
5. 检查是否包含控制、trajectory 或 actuator topic；未经授权不回放这些 topic。
6. 回放循环可能导致 ROS time 倒退，算法必须明确处理或禁止 loop。

## 回归数据集

至少区分静态包、短运动包、完整线路包和异常包。保存 bag ID、哈希、录制配置、适用 commit、预期指标和已知限制，不把大型 bag 本体打包进 Skill。
