# ROS Noetic LiDAR、IMU、GNSS/RTK 与 SLAM

本参考用于 ROS 1 Noetic 下的 LiDAR/IMU/GNSS-RTK/SLAM 调试与架构分析。先确认版本、topic、message type、TF 和时间语义，再进入算法。

## 数据接口基线

对每个设备记录：型号、序列号、固件、驱动 package/commit、ROS topic、message type、频率、量程、单位、坐标轴、状态码、协方差、时间源、frame、丢包行为和启动依赖。

Noetic 常见接口包括：

- LiDAR：`sensor_msgs/PointCloud2` 或厂商 packet/raw message；
- IMU：`sensor_msgs/Imu`；
- GNSS：`sensor_msgs/NavSatFix`、厂商自定义 position/status/heading；
- odometry：`nav_msgs/Odometry`；
- trajectory/path：`nav_msgs/Path` 或项目自定义消息；
- TF：`/tf`、`/tf_static`。

不要仅根据 topic 名猜语义；读取 `rosmsg show <type>` 和驱动代码/文档确认字段。

## LiDAR

确认：

- 扫描模式、转速/帧率；
- frame stamp 对应扫描开始/中点/结束；
- PointCloud2 fields、datatype、offset、endianness；
- ring、return、intensity、point time；
- 点时间单位和相对参考；
- 盲区、最小/最大距离；
- invalid point/NaN 处理；
- packet 丢失、重排和 frame assemble 策略。

Deskew 前必须证明：点级时间存在且单位/范围正确、IMU 覆盖完整扫描时间窗、LiDAR↔IMU 时间 offset 与外参方向明确。

## IMU

确认：

- gyro：rad/s 还是 deg/s；
- accel：m/s² 还是 g；
- 是否包含重力；
- sensor axes 与 body frame；
- 量程、饱和、噪声密度、random walk、bias、温漂；
- covariance 是真实标定结果、固定配置还是 unknown；
- stamp 来源和采样频率稳定性。

静止段至少检查均值、方差、重力模长和方向。不要通过调大/调小噪声参数掩盖单位、轴或时间错误。

## GNSS/RTK

确认：

- GPS/UTC/Unix 时间格式；
- fix/float/single/no-fix 状态；
- 天线相位中心与 `base_link` 外参；
- ENU/NED/ECEF/经纬高转换；
- covariance 来源和单位；
- position/status/heading 是否同一测量周期；
- 双天线 heading 的基线方向、正方向和安装 yaw offset。

GNSS 到地图坐标的转换必须记录原点、投影/ENU 定义、geoid/ellipsoid 高程语义和 yaw 对齐方式。

## ROS 1 运行时链

先验证 ROS 层，再验证算法：

```bash
rostopic info /points
rostopic hz /points
rostopic delay /points
rostopic info /imu
rostopic hz /imu
rostopic info /gnss
rosnode info /estimator
rosrun tf tf_monitor
```

多机系统还要检查 `ROS_MASTER_URI`、`ROS_IP` / `ROS_HOSTNAME` 和 TCPROS 回连。topic 在 `rostopic list` 中出现不代表数据链路、时间或算法 gate 正常。

## 融合与 SLAM 分层验证

按顺序验证，前一层没有证据通过时不要跳到后端调参：

1. **Raw sensor**：数据质量、频率、单位、状态、丢包；
2. **Time**：measurement stamp、offset、drift、乱序、deskew coverage；
3. **Extrinsic/TF**：方向、单位、frame ownership；
4. **Preprocess**：过滤、motion compensation、downsample 是否破坏关键结构；
5. **Prediction**：IMU propagation、velocity、bias、gravity；
6. **Measurement update**：scan matching residual/correction/correspondence；
7. **Observability**：退化方向、information/conditioning；
8. **External fusion**：GNSS/RTK innovation、gate、accept/reject；
9. **Map/loop**：局部地图、pose graph、loop correction 是否先于误差变化；
10. **Output**：`map/odom/base_link`、ENU 对齐、轨迹连续性；
11. **Runtime**：每帧耗时、queue、CPU/memory 和实时余量；
12. **Regression**：不同路线、速度、方向、环境和 bag。

## 首个异常原则

分析纵向/横向/航向误差时，先找“哪个内部量最早偏离正常”，而不是从最终轨迹倒推所有可能模块。

推荐稳定 Observation Contract：

```text
external pose error
-> prediction velocity/bias
-> matching correction/residual
-> directional observability
-> GNSS/RTK innovation + gate
-> loop/map correction
-> runtime margin
```

这些量应共享明确 time/distance axis，并固定 unit/frame/sign/time basis。

## 典型故障映射

- `rostopic hz` 已下降且算法误差随后上升：先查 driver/network/runtime，不先调 SLAM 参数。
- IMU prediction 先漂、matching correction 只是被动追赶：先查 IMU unit/time/bias/model。
- prediction 正常但 scan correction 持续同方向偏：查 deskew、外参、matching support、地图局部结构。
- longitudinal information 下降先于 longitudinal error：优先判定方向退化/可观测性，而不是简单增加权重。
- RTK innovation 正常但长期 rejected：查 gate、状态/协方差、时间和 frame。
- map/loop correction 后误差突跳：查 loop constraint、map frame ownership 和旧地图一致性。

## rosbag1 A/B

比较 baseline/candidate 时必须保持：同一 `.bag`、同一回放窗口、`/use_sim_time`/`--clock`、同一 TF 来源、同一 reference、轨迹对齐、指标定义和唯一主要变量。

不要使用不同 bag、不同裁剪或手工平移轨迹制造视觉改善。

## 禁止的“修复”

不要通过以下方式掩盖根因：

- 无限扩大同步窗；
- 无限增大 queue；
- 关闭 timestamp/status/TF gate；
- 固定虚假的 covariance；
- 把 GNSS/RTK 不可信状态强制当高精度；
- 手工旋转/平移输出轨迹但不修 frame/extrinsic；
- 一次同时改 offset、extrinsic、noise、matching weight；
- 只看 RViz 截图宣布精度提升。

## 完成标准

只有根因机制有证据、最小修复通过同条件验证、关键指标没有回归，并能由保存的 rosbag/result bundle/静态报告复核时，才描述为完成。无法区分的地方保持 `inconclusive`，不强行下结论。
