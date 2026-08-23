# ROS Noetic 增量证据与缓存

目标：复用已验证基线，只读取和重算变化域，减少 CLI、上下文和 token 消耗。

## 默认流程

```text
cached evidence hashes
→ changed / unchanged / preserved domains
→ targeted refresh
→ merge
→ system profile
→ validate
→ cache update
```

首次接手系统、没有缓存、基线来源不明或用户明确要求 audit 时，才做完整勘察。

## 缓存

缓存默认位于项目本地 `.ros_noetic_cache/`，不应提交为项目真值。它保存 evidence 内容哈希、最新 profile 和可选的 compact session summary，不复制大型 bag。

```bash
python3 scripts/incremental_evidence.py plan \
  --launch evidence/launch.json \
  --runtime evidence/runtime.json
```

输出语义：

- `changed_domains`：本次已提供且内容变化的域，需要刷新；
- `unchanged_domains`：本次已提供且 hash 未变化的域，不重新加载正文；
- `preserved_cached_domains`：本次没有提供，但旧缓存仍保留的域，不能因为一次局部 update 被删除。

确认新基线后：

```bash
python3 scripts/incremental_evidence.py update \
  --launch evidence/launch.json \
  --runtime evidence/runtime.json \
  --profile robot_profile.yaml \
  --summary session_summary.yaml
```

`update` 只替换本次提供的域，并保留未提供的已有缓存域。

## 变化域路由

| changed domain | 只刷新 |
|---|---|
| launch | driver/expected graph/hardware expectation |
| runtime | live graph/topic presence |
| hardware | changed device/interface |
| tf_time | changed frame/time path |
| bag | recorded topic/data contract |
| topic_probe | 单个 changed topic |

`diff_system_profiles.py` 输出 `changed_domains`、`unchanged_domains`、`affected_topics` 和 `refresh_plan`。不要因为一个 IMU topic 变化就重新加载全部 LiDAR、GNSS、controller 和 bag 证据。

## 跨域升级条件

只有以下情况扩大检查：

- 新证据与缓存中的高可信域直接冲突；
- changed topic 的 frame/time 指向 TF/time；
- 硬件 endpoint 变化同时改变 driver 或 message contract；
- 基线 validation 变为 `not_ready`；
- 用户明确要求完整 audit。

缓存是性能优化，不是真值来源；最终结论仍必须带 provenance。