# ROS Noetic 发行版契约

本分支只服务 ROS 1 Noetic，不承担 ROS 2 distro routing。

## 环境契约

开始分析、修改或运行时诊断前确认：

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

必须满足：

```text
ROS_VERSION=1
ROS_DISTRO=noetic
noetic
```

默认平台基线：Ubuntu 20.04 + ROS Noetic + Python 3 + catkin。

若任一项不匹配：

1. 停止套用本分支命令/API；
2. 报告实际环境；
3. 不自动切换到 ROS 2 或其他 ROS 1 发行版语义；
4. 只有用户明确要求迁移/对比时，才读取迁移参考。

## EOL 约束

ROS Noetic 已于 2025-05 结束官方支持。涉及安装、升级、生产部署和安全时，必须记录：

- OS/镜像是否冻结；
- apt/第三方仓库来源；
- 关键依赖是否还能重现安装；
- 安全更新与漏洞修复策略；
- 是否需要容器/离线镜像归档；
- 迁移到受支持 ROS 2 发行版的窗口和回滚计划。

不要把“能运行”描述为“仍受官方支持”。

## Noetic 工具链

默认使用：

- catkin / catkin_make / catkin_tools；
- roscore / ROS master / XML-RPC；
- roslaunch XML；
- rostopic / rosnode / rosservice / rosparam；
- actionlib；
- nodelet / pluginlib；
- dynamic_reconfigure；
- tf / tf2_ros；
- rosbag1；
- rospy / roscpp。

默认排除：

- `ros2 ...` CLI；
- DDS/RMW/QoS compatibility；
- lifecycle、component container；
- executor/callback group；
- rosbag2；
- ament/colcon。

## Overlay 与环境证据

Noetic 中很多“包找不到/链接错版本/消息不一致”来自 workspace overlay，而不是源码逻辑。至少记录：

```bash
echo "$ROS_PACKAGE_PATH"
echo "$CMAKE_PREFIX_PATH"
which roscore
which roslaunch
rospack find <pkg>
```

如果使用 catkin_tools，再记录 profile、workspace 和 devel/install space。

## 多机约束

多机调试至少记录：

```bash
echo "$ROS_MASTER_URI"
echo "$ROS_IP"
echo "$ROS_HOSTNAME"
host <peer-hostname>
```

Master 可注册不代表 TCPROS 数据路径可回连；容器、VPN、NAT、防火墙和错误 hostname 都可能造成“rosnode/rostopic 可见但数据不通”。

## 证据要求

交付时至少明确：

- 目标确实是 Noetic；
- 实际 OS/容器镜像；
- catkin workspace 与 overlay；
- 单机/多机网络环境；
- 已验证命令/测试；
- EOL 风险和未覆盖依赖；
- 如有变更，给出回滚方法。
