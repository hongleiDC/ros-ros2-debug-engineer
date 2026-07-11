# ros-ros2-debug-engineer

用于编写、审查、迁移和调试 ROS1/ROS2 代码的 ChatGPT Skill。

## 能力

- ROS1 Noetic / ROS2 Humble C++ 与 Python 开发
- package、launch、参数、QoS、TF、时间同步和 rosbag 调试
- LiDAR、IMU、RTK 等传感器接口、内参、外参和时间模型管理
- 编译、运行、回归测试和 incident 记录
- 自动维护目标项目自己的工程知识库

## 安装

### 方法一：打包后安装到 ChatGPT

先克隆仓库：

```bash
git clone https://github.com/hongleiDC/ros-ros2-debug-engineer.git
cd ros-ros2-debug-engineer
```

确认 Skill 的入口文件位于仓库根目录：

```text
ros-ros2-debug-engineer/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/
```

将整个 Skill 目录打包为 ZIP。压缩包中必须直接包含 `SKILL.md`，不能在外面再多套一层无关目录：

```bash
zip -r skill.zip . \
  -x '.git/*' \
  -x '.github/*' \
  -x '*.DS_Store' \
  -x '__pycache__/*'
```

然后在 ChatGPT 中打开 `/skills`，选择创建或上传 Skill，并上传生成的 `skill.zip`。界面文字可能随客户端版本略有不同。

安装完成后，可以用下面的请求测试是否触发：

```text
请使用 ros-ros2-debug-engineer 检查这个 ROS2 仓库的 QoS、时间戳、TF 和外参问题。
```

> Skill 压缩包应保持精简，不要把 rosbag、点云、模型权重或项目长期知识打包进去。

### 方法二：本地开发和修改

直接在克隆后的仓库中修改 `SKILL.md`、`references/` 或 `scripts/`。修改完成后重新生成 `skill.zip` 并在 ChatGPT 中重新上传，以使新版本生效。

建议先检查仓库中是否混入了项目专属知识：

```bash
find references -maxdepth 3 -type d
```

Skill 仓库中不应存在类似下面的目录：

```text
references/projects/NAVI_RailLIO_RTK/
```

### 目标 ROS 项目的初始化

安装 Skill 后，还需要在每个实际 ROS 项目仓库根目录增加项目标识文件：

```yaml
# .ros_debug_project.yaml
schema_version: 1
project_id: NAVI_RailLIO_RTK
knowledge_dir: project_knowledge
```

并建立项目自己的知识库：

```bash
mkdir -p project_knowledge/{devices,calibrations,bags,incidents,decisions,regression_tests}
touch project_knowledge/CHANGELOG.md
```

建议至少创建：

```text
project_knowledge/
├── README.md
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

可以使用本 Skill 仓库中的脚本检查项目知识库：

```bash
python3 scripts/validate_knowledge.py /path/to/target-project/project_knowledge
```

调试过程中确认的新设备信息、外参、时间偏移、bag 结论和 incident，应提交到目标 ROS 项目仓库，而不是提交到本 Skill 仓库。

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
