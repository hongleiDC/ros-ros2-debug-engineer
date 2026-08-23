# ROS Noetic 自动系统画像

本参考定义如何把 launch、live ROS、hardware、TF/time 与 rosbag1 证据整理成稳定的 `robot_profile.yaml`。画像用于快速理解机器人系统、复现实验环境和比较部署变化，不是数字孪生、硬件认证或自动根因结论。

## 核心结构

```text
robot_profile.yaml
├── completeness
├── machine
├── hardware
├── drivers
├── ros_graph
├── topics
├── coordinates
├── time
├── data
├── risk
└── provenance
```

## 生成流程

先采集证据：

```bash
python3 scripts/inspect_launch.py system.launch --output evidence/launch.json
python3 scripts/collect_runtime_snapshot.py --profile communication --output evidence/runtime.json
python3 scripts/inspect_system_hardware.py --output evidence/hardware.json
python3 scripts/inspect_tf_time.py --output evidence/tf_time.json
python3 scripts/inspect_rosbag.py run.bag --metadata-only --output evidence/bag.json
```

合并：

```bash
python3 scripts/merge_system_evidence.py \
 --launch evidence/launch.json \
 --runtime evidence/runtime.json \
 --hardware evidence/hardware.json \
 --tf-time evidence/tf_time.json \
 --bag evidence/bag.json \
 --output evidence/merged.json
```

生成画像：

```bash
python3 scripts/generate_system_profile.py \
 --merged evidence/merged.json \
 --output robot_profile.yaml
```

## 画像语义

- `machine`：机器环境与系统探针；
- `hardware`：expected endpoint、observed endpoint、transport candidate；
- `drivers`：launch 中 package/node 与候选角色；
- `ros_graph`：expected 与 live node/topic/service/parameter；
- `topics`：type、MD5、rate、frame、PointCloud2 fields；
- `coordinates`：frame 与 TF 关系；
- `time`：sim time、clock、host sync；
- `risk`：conflict、difference、unknown；
- `provenance`：证据来源。

## 边界

画像必须保留证据等级：

- driver role 是候选映射；
- transport hint 不是硬件认证；
- frame 存在不代表外参正确；
- bag 是历史记录，不代表当前部署；
- unknown 不自动填充。

以下变化后重新生成画像：

- workspace/branch/commit；
- driver 或固件；
- launch/YAML；
- 标定和 TF；
- 时间同步；
- bag 数据。
