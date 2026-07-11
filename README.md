# ros-ros2-debug-engineer

用于编写、审查、迁移和调试 ROS1/ROS2 代码的 ChatGPT Skill。

## 能力

- ROS1 Noetic / ROS2 Humble C++ 与 Python 开发
- package、launch、参数、QoS、TF、时间同步和 rosbag 调试
- LiDAR、IMU、RTK 等传感器接口、内参、外参和时间模型管理
- 编译、运行、回归测试和 incident 记录
- 自动维护目标项目自己的工程知识库

## 安装

### 1. 克隆并安装依赖

```bash
git clone https://github.com/hongleiDC/ros-ros2-debug-engineer.git
cd ros-ros2-debug-engineer
python3 -m pip install -r requirements.txt
```

### 2. 运行测试和打包

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

成功后生成：

```text
dist/skill.zip
```

打包脚本会检查 `SKILL.md` frontmatter、`agents/openai.yaml`、本地引用和 25 MB 大小限制，并排除 `.git`、CI、测试缓存和旧产物。

### 3. 安装到 ChatGPT

在 ChatGPT 中打开 `/skills`，选择创建或上传 Skill，并上传 `dist/skill.zip`。界面文字可能随客户端版本略有不同。

安装后可用以下请求测试：

```text
请使用 ros-ros2-debug-engineer 检查这个 ROS2 仓库的 QoS、时间戳、TF 和外参问题。
```

> 不要把 rosbag、点云、模型权重或具体项目长期知识打包进 Skill。

## 初始化目标 ROS 项目

每个实际 ROS 项目必须维护自己的知识库。运行：

```bash
python3 scripts/init_project_knowledge.py \
  /path/to/target-project \
  --project-id NAVI_RailLIO_RTK
```

该命令创建：

```text
<target-project>/
├── .ros_debug_project.yaml
└── project_knowledge/
    ├── README.md
    ├── project.yaml
    ├── active_configuration.yaml
    ├── topics.yaml
    ├── timing.yaml
    ├── CHANGELOG.md
    ├── devices/
    ├── calibrations/
    ├── bags/
    ├── incidents/
    ├── decisions/
    └── regression_tests/
```

`.ros_debug_project.yaml` 示例：

```yaml
schema_version: 1
project_id: NAVI_RailLIO_RTK
knowledge_dir: project_knowledge
```

## 验证和更新知识库

验证：

```bash
python3 scripts/validate_knowledge.py \
  /path/to/target-project/project_knowledge
```

安全更新一个字段：

```bash
python3 scripts/update_knowledge.py \
  /path/to/target-project/project_knowledge \
  active_configuration.yaml \
  runtime.use_sim_time \
  true \
  --status measured \
  --reason "bag replay configuration" \
  --evidence "launch file and runtime parameter"
```

预览而不写入：

```bash
python3 scripts/update_knowledge.py ... --dry-run
```

默认禁止修改顶层状态为 `verified` 的记录。确需替换时必须显式增加：

```text
--allow-replace-verified
```

并在 `--reason` 和 `--evidence` 中说明依据。

创建 incident：

```bash
python3 scripts/new_incident.py \
  /path/to/target-project/project_knowledge \
  INC-0006 \
  "rtk timestamp mismatch"
```

## 重要设计原则

Skill 仓库只保存通用规则、schema、模板和脚本。

具体项目的设备、话题、内参、外参、时间偏移、bag 分析、故障经验和架构决定，必须保存在对应项目代码仓库中。调试过程中确认的新事实应提交到目标 ROS 项目的 `project_knowledge/`，而不是本 Skill 仓库。

## 开发与 CI

本仓库的 GitHub Actions 会自动执行：

```text
依赖安装
→ 单元测试
→ Skill 结构验证
→ 生成 skill.zip 构件
```

本地修改后执行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

## 仓库内容

- `SKILL.md`：主要工作流和约束
- `references/core/`：通用 ROS 调试规则
- `references/schemas/`：知识库 JSON Schema 与 incident 规范
- `scripts/`：初始化、验证、更新、incident 创建和打包脚本
- `tests/`：知识工具回归测试
- `agents/openai.yaml`：Skill UI 元数据
