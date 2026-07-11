# 目标项目知识库发现规则

## 目的

让 Skill 在任意 ROS/ROS2 项目中读取和维护该项目自己的工程知识，而不是把业务数据保存在 Skill 仓库。

## 发现顺序

1. 使用用户明确指定的目标仓库。
2. 在仓库根目录查找 `.ros_debug_project.yaml`。
3. 读取其中的 `project_id` 和 `knowledge_dir`。
4. 若标识文件不存在，检查 `project_knowledge/` 是否已经存在。
5. 若仍不存在，在目标项目仓库初始化最小知识库；不要在 Skill 仓库创建项目目录。

## 标识文件

```yaml
schema_version: 1
project_id: my_ros_project
knowledge_dir: project_knowledge
```

`knowledge_dir` 必须是目标仓库内的相对路径，禁止使用 `..` 越界。

## 最小初始化结构

```text
project_knowledge/
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

初始未知值使用 `unknown` 或 `candidate`，不得根据常见设备经验直接填入。

## 加载优先级

1. 当前运行代码、设备输出和 bag 实测事实；
2. 目标仓库知识库中 `verified` 记录；
3. `measured` 记录；
4. `candidate` 记录；
5. 通用 Skill 规则。

发生冲突时保留旧记录、写明冲突和证据，不静默覆盖。

## GitHub 写入

- 代码修改写入目标项目仓库。
- 由修改产生的设备、标定、时间或 incident 结论也写入同一目标项目仓库。
- 每次写入追加 `CHANGELOG.md`。
- 向用户报告仓库、分支、commit SHA、修改文件和验证结果。
- 若没有目标仓库写权限，输出补丁或迁移包，不得写回 Skill 仓库作为替代。

## 多项目场景

每个项目维护独立 `.ros_debug_project.yaml` 和知识目录。不要在一个项目知识库中混入另一个项目的设备或标定记录。共享的通用规则应回到 Skill 的 `references/core/` 或 `references/schemas/`。
