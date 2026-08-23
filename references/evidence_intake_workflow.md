# ROS Noetic 证据输入与自动提取工作流

用户直接给出 launch、bag、ROS 输出、TF/时间异常、日志或硬件信息时，优先利用已有材料建立事实，不先要求重新执行完整 checklist。

## 输入路由

| 输入 | 工具 | 目标 |
|-|-|-|
| launch/test | inspect_launch.py | expected 配置 |
| bag | inspect_rosbag.py | recorded 数据 |
| live topic | probe_topic.py | 当前 topic 质量 |
| ROS现场 | collect_runtime_snapshot.py | graph 基线 |
| 设备 | inspect_system_hardware.py | OS endpoint |
| TF/time | inspect_tf_time.py | 时间和坐标证据 |
| 多源证据 | merge_system_evidence.py | 冲突分析 |

## 证据边界

始终保持：

```text
expected
observed-live
recorded
```

launch 不是运行事实；bag 不是当前部署；topic 名一致不是语义一致。

## TF/time

```bash
python3 scripts/inspect_tf_time.py --output evidence/tf_time.json
```

关注：

- /use_sim_time；
- /clock；
- /tf /tf_static；
- tf_monitor；
- frame pair；
- host time sync；
- sensor stamp。

## 合并

```bash
python3 scripts/merge_system_evidence.py \
 --launch evidence/launch.json \
 --bag evidence/bag.json \
 --runtime evidence/runtime.json \
 --hardware evidence/hardware.json \
 --tf-time evidence/tf_time.json
```

输出：

1. 系统事实；
2. expected/live/recorded 差异；
3. conflict；
4. unknown；
5. 最小下一步证据。

原则：已有证据优先、冲突优先、最小增量采集。
