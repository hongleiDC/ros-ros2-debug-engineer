# 项目理解与证据等级

## 原则

Skill 不因读取到仓库就“了解项目”。项目理解是一个有证据边界的模型，必须说明覆盖了什么、没有覆盖什么。

## 理解等级

| 等级 | 所需证据 | 可以声称 | 不得声称 |
|---|---|---|---|
| L0 元数据 | 仓库说明、文件列表 | 知道项目声明的用途 | 知道真实架构或运行行为 |
| L1 静态模型 | package、源码、launch、参数、接口、URDF、测试 | 理解代码和配置的静态结构 | 节点实际启动、topic 实际连接、参数实际生效 |
| L2 可构建模型 | 在目标环境成功解析依赖并构建 | 当前 commit 在该环境可构建 | 运行时行为正确 |
| L3 运行时模型 | node/topic/service/action、QoS、lifecycle、TF、参数和环境快照 | 理解采样时刻的运行图 | 问题已稳定复现或根因已确认 |
| L4 复现模型 | 日志、bag、仿真或硬件上可重复复现 | 问题和候选根因存在可重复关系 | 修复没有回归 |
| L5 验证模型 | 修复后通过明确回归和对照指标 | 根因和修复在指定范围内已验证 | 对其他设备、版本和数据集普遍成立 |

## 静态事实模型

至少收集：

- 仓库、分支、commit、脏文件和 submodule；
- ROS 家族、发行版线索、构建工具、C++/Python 版本；
- package 列表、package format、依赖和 workspace overlay；
- executable、node、component、plugin、nodelet；
- launch 文件、入口 launch、include、参数文件、remap 和 namespace；
- msg/srv/action、自定义接口和生成依赖；
- URDF/xacro、robot_state_publisher、static transform、ros2_control；
- topic/service/action 名称和消息类型的静态声明；
- lifecycle、callback group、executor、composition 的代码线索；
- Docker、systemd、udev、CI、测试和部署脚本；
- bag、设备说明、标定和项目知识库。

优先运行 `inspect_workspace.py`，但脚本输出只是索引。对于关键结论仍需读取对应源码和配置。

## 运行时事实模型

按问题需要收集：

- ROS_DISTRO、ROS_VERSION、RMW_IMPLEMENTATION、ROS_DOMAIN_ID；
- 节点、namespace、lifecycle 状态和 component container；
- topic 类型、发布者/订阅者、QoS 和频率；
- service/action 端点；
- 参数实际值和来源；
- TF tree、authority、时间范围和重复发布者；
- `/clock`、`use_sim_time` 和系统时钟状态；
- CPU、内存、线程、callback 时长和网络环境；
- 设备连接、固件、驱动 commit 和实际启动命令。

`collect_runtime_snapshot.py` 只执行只读命令。快照有采样时刻，不代表所有运行阶段。

## 事实表

每个重要判断使用以下类别：

- `observed`：由当前代码、命令、日志或数据直接观察。
- `measured`：由统计或实验测得，并记录样本和方法。
- `inferred`：由多个事实推断，必须列出推理依据。
- `candidate`：待验证假设。
- `contradicted`：被当前证据反驳。
- `unknown`：缺少必要证据。

## 覆盖和盲区

输出项目理解时至少说明：

```text
理解等级：L1
已覆盖：package、launch、参数、接口、TF 静态声明
未覆盖：实际 DDS 网络、运行时参数、bag 时间质量、真实设备固件
结论边界：只能审查静态配置，不能确认现场通信和同步行为
```

## 冲突处理

证据优先级通常为：

1. 同一 commit 和同一运行配置的可重复实测；
2. 当前运行图、日志和 bag；
3. 当前源码、launch 和参数；
4. 项目知识库的 verified/measured 记录；
5. README、注释和历史 incident；
6. 通用 ROS 经验。

发现冲突时保留双方证据，确认是否来自不同 branch、设备、固件、参数或时间段，不静默选择更符合预期的一方。
