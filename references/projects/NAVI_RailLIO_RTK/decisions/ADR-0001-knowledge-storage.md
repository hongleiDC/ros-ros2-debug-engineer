# ADR-0001 项目知识直接写入 Skill 参考库

- status: accepted
- date: 2026-07-11

## decision

设备、内参、外参、时间模型、bag、故障和架构决定直接保存到 `references/projects/NAVI_RailLIO_RTK/`。调试完成后允许直接更新，无需再次请求确认，但必须向用户报告修改内容。

## consequences

- 新聊天可加载已打包的项目事实。
- 安装目录若只读，必须生成更新后的 `skill.zip` 或提交到可写仓库，不能假称持久化。
- 所有事实必须有状态和证据，verified 记录不能无痕覆盖。
