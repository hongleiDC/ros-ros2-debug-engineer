# 项目知识库写入策略

## 所有权边界

项目专属知识必须保存在目标项目代码仓库中。Skill 仓库只保存通用规则、schema、模板和脚本。

禁止把设备型号、序列号、具体话题、内参、外参、时间偏移、bag 结论或 incident 写入本 Skill 的 `references/projects/`。

## 目标目录

1. 读取目标项目根目录 `.ros_debug_project.yaml`。
2. 使用其中的 `knowledge_dir`；默认建议为 `project_knowledge`。
3. 若标识文件不存在，先在目标项目仓库初始化：

```yaml
schema_version: 1
project_id: <project-id>
knowledge_dir: project_knowledge
```

4. 知识目录至少包含：

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

## 直接写入

调试结束后直接修改目标项目仓库的知识目录，不等待二次确认。写入成功后必须告诉用户修改内容、目标仓库和 commit SHA。

## 状态

- `candidate`：推断、初步发现或尚未复现。
- `measured`：已从设备、代码或 bag 测量。
- `verified`：修复后通过明确回归测试。
- `deprecated`：被新版本替代，保留历史。

## 不可破坏更新

- 不静默覆盖 `verified` 值。
- 数值变化时保留旧版本、原因和生效日期。
- 标定使用版本文件和 active 指针。
- 设备按 serial、firmware 和 driver commit 区分。
- 每个 bag 保存路径、哈希、录制配置和分析结果，不提交大型 bag 本体。
- 知识记录应绑定适用代码 branch/commit。

## 验证与提交

```bash
python scripts/validate_knowledge.py <target-repository>/<knowledge_dir>
```

通过 GitHub 操作时：

1. 将代码和知识更新提交到目标项目仓库；
2. 不要把项目知识提交到 `ros-ros2-debug-engineer`；
3. 报告提交 SHA 和变更文件；
4. 目标不可写时生成补丁，不得声称已经持久化。

## 每次更新的用户报告

```text
知识库更新摘要
- 目标仓库：owner/repo
- 提交：<commit SHA>
- 新增：文件/字段
- 修改：旧值 -> 新值，原因
- 弃用：旧记录及替代项
- 状态：candidate/measured/verified
- 验证：运行的命令或 bag
- 落盘位置：<knowledge_dir>
```
