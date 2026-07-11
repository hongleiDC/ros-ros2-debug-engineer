# ROS 编码规则

## 通用

- 默认 C++17；Python 节点使用类型提示和异常处理。
- 参数必须声明默认值、单位和意义；启动时打印关键参数。
- 传感器回调避免长时间阻塞；共享状态使用明确的锁或单线程 executor。
- 所有丢弃数据路径统计原因并使用节流日志。
- 不使用 `ros::Time::now()` 或 `node->now()` 冒充传感器测量时间。
- 关闭流程必须停止线程、唤醒条件变量并 join。

## ROS1

- 消息类型写作 `sensor_msgs::Imu` / `sensor_msgs/Imu`，按语言区分。
- 检查 `catkin_package`、message generation 和依赖顺序。
- bag 回放时明确 `/use_sim_time` 和 `--clock`。

## ROS2

- 消息类型写作 `sensor_msgs::msg::Imu` / `sensor_msgs/msg/Imu`。
- 显式选择 QoS；传感器默认先检查 `rclcpp::SensorDataQoS()`。
- launch 参数、节点参数和 remap 分开表达。
- 使用 `use_sim_time` 回放 rosbag2，确认 `/clock`。

## 输出完整性

新增节点至少提供：源码、构建依赖、launch、参数示例、运行命令、topic/TF 检查命令和测试方法。
