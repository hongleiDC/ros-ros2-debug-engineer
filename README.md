# ros-noetic-systems-engineer

> Branch: `ros1-noetic`

这是 `ros-ros2-systems-engineer` 的 **ROS 1 Noetic 专用 Skill 分支**。它不再尝试同时兼容 ROS 1 与 ROS 2，而是把运行时模型、命令、构建系统和诊断术语锁定到 ROS Noetic。

## 为什么单独建立 Noetic 分支

同时兼容 ROS 1 / ROS 2 会让 Skill 在实际项目中缺少明确的版本语义，例如：

- ROS 1 Noetic 使用 ROS master/XML-RPC/TCPROS，而不是 DDS/RMW；
- 使用 catkin，而不是 ament/colcon；
- 使用 roslaunch XML，而不是 ROS 2 launch；
- 使用 rosbag1，而不是 rosbag2；
- roscpp 使用 spinner/callback queue，而不是 ROS 2 executor/callback group；
- Noetic 没有 ROS 2 QoS compatibility、lifecycle node、component container 等运行时概念。

因此这个分支的第一原则是：**先确认版本，再分析系统。**

```bash
printenv ROS_VERSION ROS_DISTRO
rosversion -d
```

期望：

```text
ROS_VERSION=1
ROS_DISTRO=noetic
noetic
```

环境不匹配时，Skill 应停止套用 Noetic 假设，而不是自动退回“通用 ROS”回答。

## Skill 名称

```text
ros-noetic-systems-engineer
```

默认提示同样明确要求使用 Noetic 语义。

## Noetic 技术基线

本分支默认使用：

- Ubuntu 20.04；
- ROS 1 Noetic；
- catkin / catkin_make / catkin_tools；
- roscore / ROS master；
- roslaunch XML；
- rostopic / rosnode / rosservice / rosparam / roswtf；
- TCPROS/UDPROS；
- tf / tf2_ros；
- rosbag1；
- actionlib；
- nodelet / pluginlib；
- dynamic_reconfigure；
- diagnostic_updater；
- rospy / roscpp。

ROS Noetic 已于 2025-05 结束官方支持，因此安装、系统依赖与生产部署任务必须明确考虑 EOL 风险。

## 调试顺序

```text
catkin 构建
→ roslaunch / 参数
→ ROS master / graph
→ topic / service / action
→ TF / 时间
→ spinner / callback queue / 资源
→ 数据 / 算法
```

简单问题保持简单；默认只读；只读取足够区分当前假设的文件和运行时证据。

## 运行时快照

```bash
python3 scripts/collect_runtime_snapshot.py --profile basic
python3 scripts/collect_runtime_snapshot.py --profile communication
python3 scripts/collect_runtime_snapshot.py --profile full --detail-limit 20
```

脚本现在会检查 `ROS_VERSION=1`、`ROS_DISTRO=noetic` 和 `rosversion -d`。环境不匹配时默认退出，不再静默切换到 ROS 2。

## 长期算法与结果分析

定位、SLAM、LIO、VIO、融合等长期算法仍保留项目级 Observation / Result / Visualization / Human Analysis Contract：

```text
Algorithm Contract
→ Observation Contract
→ Result Contract
→ Visualization Contract
→ Human Analysis Contract
```

一次性初始化：

```bash
python3 scripts/bootstrap_analysis_tooling.py PROJECT_ROOT --system lio
```

每次运行后：

```bash
python3 tools/analysis/analyze_run.py RUN_DIR --strict
```

生成静态 `RUN_DIR/report/index.html`，保证没有 AI 时工程师仍可复核结果。

## 分支策略

- `main`：保留当前通用 ROS 1 / ROS 2 Skill；
- `ros1-noetic`：ROS 1 Noetic 专用；
- 后续可以继续按同一模式建立 ROS 2 发行版专用分支，例如 Humble、Jazzy 等。

这样每个 Skill 都拥有明确的 API、CLI、构建系统、运行时与发行版边界，而不是让一个 Skill 在运行时猜版本。
