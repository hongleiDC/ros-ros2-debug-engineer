# 项目知识库发现

## 使用条件

仅在用户要求持久化项目知识，或目标仓库已经存在 `.ros_debug_project.yaml` 时使用。普通分析不自动创建知识目录。

## 发现顺序

1. 使用用户明确指定的目标仓库。
2. 在仓库根目录查找 `.ros_debug_project.yaml`。
3. 验证 `knowledge_dir` 是仓库内相对路径，不能包含 `..`，不能通过 symlink 越界。
4. 读取知识目录中的 project、project_model、configuration、topics、timing、devices、calibrations、bags、incidents、decisions、goals、experiments 和 regression tests。
5. 将知识记录与当前 branch、commit、设备和运行配置比对；不适用的旧记录不得覆盖当前证据。

## 初始化

只有用户明确要求时执行：

```bash
python3 scripts/init_project_knowledge.py /path/to/repository --project-id my_project
```

初始化使用临时目录和验证，失败时不保留半成品。

## 多项目

每个项目维护独立标识和知识目录。共享方法保留在 Skill references，不把一个项目的设备、标定和故障复制到另一个项目。
