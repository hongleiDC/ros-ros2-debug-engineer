# ROS 发行版兼容与路由

> 时效基线：2026-07-20。发行版状态会变化；执行安装、迁移或 CI 决策前，重新核对 ROS 官方发行页面。

## 目录

- [先识别目标环境](#先识别目标环境)
- [发行版决策](#发行版决策)
- [功能与命令分流](#功能与命令分流)
- [ROS-1-与桥接](#ros-1-与桥接)
- [证据要求](#证据要求)

## 先识别目标环境

在给出命令或补丁前，记录 `ROS_VERSION`、`ROS_DISTRO`、操作系统、架构、RMW、安装方式、overlay 顺序和目标部署镜像。环境未识别时，不得默认把 Rolling 或最新 LTS 的 API 套用到旧发行版。

优先使用实际环境证据：

```bash
printenv ROS_VERSION ROS_DISTRO RMW_IMPLEMENTATION
ros2 doctor --report
python3 scripts/preflight.py --require ros-runtime
```

## 发行版决策

- 新的长期维护项目：先评估 Lyrical Luth。它于 2026 年 5 月发布，LTS 支持期到 2031 年 5 月。
- 已部署 Jazzy、Humble、Kilted 等版本：以项目锁定版本和官方支持期为准，不为追新而隐式迁移。
- Rolling：只用于明确接受滚动 API/ABI 变化的开发与前瞻验证，不把 Rolling 命令当成稳定版通用命令。
- Windows：ROS 2 支持 Windows；当前 Rolling 安装目标是 Windows 11。脚本和路径处理不得默认存在 `fcntl`、POSIX shell 或 Linux 设备文件。

官方入口：

- [ROS 2 releases](https://docs.ros.org/en/rolling/Releases.html)
- [Lyrical Luth release](https://docs.ros.org/en/kilted/Releases/Release-Lyrical-Luth.html)
- [ROS 2 installation platforms](https://docs.ros.org/en/rolling/Installation.html)

## 功能与命令分流

1. 先在目标发行版的官方文档中确认包和 CLI 参数存在，再执行。
2. 对发行版敏感的 executor、lifecycle、launch、rosbag2、QoS override 和安全功能，记录“最低已验证发行版”。
3. Lyrical 新增的 `EventsCBGExecutor` 和 `rclpy` AsyncNode 等能力不得写入面向旧发行版的公共代码路径，除非有版本门控、替代实现和对应 CI。
4. CLI 返回“unknown option”时，将其记为兼容性证据，不改写为运行时故障。
5. 跨发行版补丁至少覆盖：构建清单、API 分支、参数/launch 语义、消息接口、bag 存储插件和回归测试。

## ROS 1 与桥接

ROS 1 Noetic 已于 2025 年 5 月结束官方支持。处理 ROS 1 时明确标注 EOL 风险、操作系统约束和依赖来源。`ros1_bridge` 不是任意 ROS 1/ROS 2 组合的透明兼容层；先核对官方支持矩阵、接口生成条件和桥接类型，再设计迁移窗口。

参考 [ROS1/ROS2 迁移](ros1_ros2_migration.md) 获取迁移证据清单。

## 证据要求

交付时给出：目标发行版、官方文档链接、实际命令输出、已验证平台、未覆盖版本和回滚方案。仅在一个发行版通过的结果，不得描述为“ROS 2 通用兼容”。
