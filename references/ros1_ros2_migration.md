# ROS1 到 ROS2 迁移

## 迁移前清点

列出 package、node/nodelet、msg/srv/action、parameter、dynamic reconfigure、plugin、launch、bag、TF、service/action、测试、硬件驱动和外部依赖。确定是全量迁移、分阶段迁移还是通过 bridge 过渡。

## 迁移维度

- catkin 到 ament 和 install/export 语义；
- NodeHandle 到 rclcpp/rclpy node；
- parameter server 到声明式 node parameter；
- dynamic_reconfigure 到 parameter callback；
- nodelet 到 component；
- actionlib 到 ROS 2 action；
- ROS 1 launch 到 ROS 2 Python/XML/YAML launch；
- rosbag1 到 rosbag2；
- time/duration、logging、shutdown 和 spinning；
- tf 到 tf2；
- QoS、DDS discovery 和 namespace/remap 语义；
- test、CI、deployment 和 monitoring。

## 迁移方法

1. 建立 ROS 1 行为基线和 bag/测试数据。
2. 先迁移接口和纯算法，再迁移运行时封装。
3. 为每个 topic 设计 QoS，不照搬 ROS 1 queue size。
4. 明确 parameter、lifecycle、executor 和 component 新语义。
5. 使用 bridge 时记录支持的类型、方向、QoS 和启动顺序。
6. 用相同输入比较输出、时间、TF、频率、资源和失败行为。
7. 保留可回滚路径，不在同一补丁中同时进行大规模算法重写。
