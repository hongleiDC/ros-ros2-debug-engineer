# ROS Noetic 项目理解与证据等级

## 原则

本分支只理解 **ROS 1 Noetic** 项目。读取仓库并不等于“了解项目”；任何结论都必须带有证据等级和覆盖边界。若静态或运行证据显示目标并非 `ROS_VERSION=1`、`ROS_DISTRO=noetic`，先标记版本不匹配，不继续套用 Noetic API、CLI 或运行时假设。

## 理解等级

| 等级 | 所需证据 | 可以声称 | 不得声称 |
|---|---|---|---|
| L0 元数据 | 仓库说明、文件列表 | 知道项目声明的用途 | 知道真实架构或运行行为 |
| L1 静态模型 | `package.xml`、CMake、源码、XML launch、参数、接口、URDF、测试 | 理解 Noetic 代码和配置的静态结构 | 节点实际启动、topic 实际连接、参数实际生效 |
| L2 可构建模型 | 在目标 Noetic 环境成功解析依赖并完成 catkin 构建 | 当前 commit 在该环境可构建 | 运行时行为正确 |
| L3 运行时模型 | master/graph、topic/service/action、参数、TF、网络与进程快照 | 理解采样时刻的运行图和连接条件 | 问题已稳定复现或根因已确认 |
| L4 复现模型 | 日志、rosbag1、仿真或硬件上可重复复现 | 问题与候选根因存在可重复关系 | 修复没有回归 |
| L5 验证模型 | 修复后通过明确回归和对照指标 | 根因和修复在指定 Noetic 环境内已验证 | 对其他设备、发行版和数据集普遍成立 |

## L1：静态事实模型

至少收集：

- 仓库、branch、commit、dirty 状态和 submodule；
- `ROS_VERSION` / `ROS_DISTRO` 线索、Ubuntu/容器、Python 3、C++ 标准；
- catkin workspace、package 列表、package format、依赖和 overlay/source 顺序；
- executable、roscpp/rospy node、nodelet、pluginlib plugin；
- `.launch` 入口、include、`<arg>`、namespace、remap、`<param>` / `<rosparam>`；
- msg/srv/action、自定义接口、`message_generation` / `message_runtime`；
- dynamic_reconfigure `cfg/` 与生成规则；
- URDF/xacro、robot_state_publisher、static transform、ros_control；
- topic/service/action 名称和消息类型的静态声明；
- `ros::spin` / AsyncSpinner / MultiThreadedSpinner / CallbackQueue 线索；
- Docker、systemd、udev、CI、rostest/gtest/pytest 和部署脚本；
- `.bag`、设备说明、标定和项目知识库。

优先运行 `scripts/inspect_workspace.py` 生成索引，但脚本输出不是运行事实。关键结论仍需读取对应源码和配置。

若 `inspect_workspace.py` 发现 `rclcpp`、ament、ROS 2 lifecycle/component 等 foreign signal，只能用于判断“可能版本混入/迁移残留”，不能当作 Noetic 能力继续分析。

## L2：构建事实模型

记录实际 source 顺序和构建命令，例如：

```bash
source /opt/ros/noetic/setup.bash
source /path/to/underlay/devel/setup.bash
catkin build target_pkg
```

构建成功至少要能回答：

- 实际使用哪个 workspace/overlay；
- `rospack find` 解析到哪个 package；
- 自定义消息是否由期望 package 生成；
- nodelet/pluginlib 导出是否可解析；
- Python 可执行脚本和模块来自哪个路径；
- build/devel/install 是否来自当前 commit。

## L3：运行时事实模型

按问题需要收集：

- `ROS_VERSION`、`ROS_DISTRO`、`ROS_MASTER_URI`、`ROS_IP`、`ROS_HOSTNAME`；
- `ROS_PACKAGE_PATH`、`CMAKE_PREFIX_PATH`、`PYTHONPATH`；
- ROS master 中的 node、namespace 与 registration；
- topic 类型、publisher/subscriber、TCPROS/UDPROS 连接和频率；
- service endpoint 与 actionlib goal/status/feedback/result 链路；
- 参数服务器的实际值和 namespace；
- TF tree、authority、时间范围和重复发布者；
- `/clock`、`/use_sim_time`、system time 与设备时间；
- spinner/callback queue、nodelet manager、线程、CPU、内存和网络环境；
- 设备连接、固件、驱动 commit 和实际 roslaunch 命令。

`collect_runtime_snapshot.py` 只做有界只读采集。`rosnode list` 可见只证明 master 注册，不证明 TCPROS 数据路径可达；快照也只代表采样时刻。

## L4/L5：复现与验证

复现必须固定：

- commit 与 dirty 差异；
- Noetic 环境和 overlay；
- `.bag` / 数据哈希；
- launch、YAML、标定和 `/use_sim_time`；
- TF 来源；
- 回放速率、`--clock` 与开始窗口；
- 指标、对齐和容差。

L5 只有在同条件回归能够证明故障消失、关键指标满足判据且没有引入必要范围内的性能/安全回归后才能使用。

## 事实标签

- `observed`：由当前代码、命令、日志或数据直接观察；
- `measured`：由统计或实验测得，并记录样本和方法；
- `inferred`：由多个事实推断，必须列依据；
- `candidate`：待验证假设；
- `contradicted`：被当前证据反驳；
- `unknown`：缺少必要证据。

## 覆盖与盲区

输出项目理解时至少写清：

```text
理解等级：L1
目标：ROS 1 Noetic
已覆盖：catkin package、XML launch、参数、接口、TF 静态声明
未覆盖：实际 ROS master、TCPROS 多机链路、运行时参数、bag 时间质量、设备固件
结论边界：只能审查静态结构，不能确认现场通信和同步行为
```

## 冲突处理

证据优先级通常为：

1. 同一 commit、同一 Noetic 环境和同一配置的可重复实测；
2. 当前运行图、日志和 rosbag1；
3. 当前源码、launch 和参数；
4. 项目知识库的 verified/measured 记录；
5. README、注释和历史 incident；
6. 通用 ROS 1 经验。

出现冲突时保留双方证据，先检查 branch、overlay、设备、固件、参数、hostname/network 和时间段，不静默选择更符合预期的一方。
