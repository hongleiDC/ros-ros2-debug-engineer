# ros-ros2-debug-engineer

用于编写、审查、迁移和调试 ROS1/ROS2 代码的 ChatGPT Skill。

## 能力

- ROS1 Noetic / ROS2 Humble C++ 与 Python 开发
- package、launch、参数、QoS、TF、时间同步和 rosbag 调试
- LiDAR、IMU、RTK 等传感器接口、内参、外参和时间模型管理
- 编译、运行、回归测试和 incident 记录
- 自动维护目标项目自己的工程知识库

## 重要设计原则

Skill 仓库只保存通用规则、schema、模板和脚本。

具体项目的设备、话题、内参、外参、时间偏移、bag 分析、故障经验和架构决定，必须保存在对应项目代码仓库中：

```text
<target-project>/
├── .ros_debug_project.yaml
└── project_knowledge/
    ├── project.yaml
    ├── active_configuration.yaml
    ├── topics.yaml
    ├── timing.yaml
    ├── devices/
    ├── calibrations/
    ├── bags/
    ├── incidents/
    ├── decisions/
    ├── regression_tests/
    └── CHANGELOG.md
```

Skill 通过 `.ros_debug_project.yaml` 定位知识库，例如：

```yaml
schema_version: 1
project_id: NAVI_RailLIO_RTK
knowledge_dir: project_knowledge
```

## 工作方式

1. 确定目标项目仓库。
2. 读取 `.ros_debug_project.yaml` 和项目知识库。
3. 复用已有设备、标定、时间和 incident 结论。
4. 编写或调试代码并执行验证。
5. 将新结论直接提交到目标项目仓库的知识库。
6. 向用户报告修改内容、验证结果和 commit SHA。

## 仓库内容

- `SKILL.md`：主要工作流和约束
- `references/core/`：通用 ROS 调试规则
- `references/schemas/`：知识库字段规范
- `scripts/`：知识验证、更新和 incident 创建脚本
- `agents/openai.yaml`：Skill UI 元数据

本仓库不应保存任何具体业务项目的长期知识副本。
