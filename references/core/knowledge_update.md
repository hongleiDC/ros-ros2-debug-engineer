# 项目知识库写入策略

## 直接写入

调试结束后直接修改 `references/projects/<project>/`，不等待二次确认。写入成功后必须告诉用户修改内容。

## 状态

- `candidate`：推断、初步发现或尚未复现。
- `measured`：已从设备、代码或 bag 测量。
- `verified`：修复后通过明确回归测试。
- `deprecated`：被新版本替代，保留历史。

## 不可破坏更新

- 不静默覆盖 verified 值。
- 数值变化时保留旧版本、原因和生效日期。
- 标定使用版本文件和 active 指针。
- 设备按 serial/firmware/driver commit 区分。
- 每个 bag 保存路径、哈希、录制配置和分析结果，不把大型 bag 打包进 Skill。

## 每次更新的用户报告

```text
知识库更新摘要
- 新增：文件/字段
- 修改：旧值 -> 新值，原因
- 弃用：旧记录及替代项
- 状态：candidate/measured/verified
- 验证：运行的命令或 bag
- 落盘位置：实际路径或仓库 commit
```

如果目标不可写，生成更新后的完整 Skill 包或仓库补丁，不得声称已经持久化。
