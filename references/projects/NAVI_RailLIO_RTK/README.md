# NAVI_RailLIO_RTK 项目参考库

此目录保存跨聊天复用的工程事实。新任务先读取 `active_configuration.yaml`、`topics.yaml`、`timing.yaml`，再按设备、标定、bag 和 incident 加载细节。

## 当前系统

- 场景：铁路露天—隧道混合场景 LiDAR–IMU–RTK SLAM。
- 前端：CT-LIO/ESKF，Livox 点级时间处理。
- ROS：ROS1 Noetic 与 ROS2 Humble 均需支持。
- 设备：Livox Mid-360、TB100 IMU、T-RTK UM982。
- 重要原则：RTK 使用数据包内部测量时间，不使用话题到达时间作为融合时间。

## 目录

- `devices/`：每个实体设备的接口、内参、单位、时间和已知问题。
- `calibrations/`：版本化外参和 active 配置。
- `bags/`：数据包元数据、时间分析和回归结果。
- `incidents/`：已发生故障、根因、修复和防回归规则。
- `decisions/`：架构决定。
- `CHANGELOG.md`：所有知识变更。
