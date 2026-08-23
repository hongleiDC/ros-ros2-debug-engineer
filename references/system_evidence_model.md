# ROS Noetic 系统证据模型与合并规则

本参考定义如何把 launch、live ROS、rosbag1、Linux/hardware、TF/time 与单 topic probe 合并成一个保留来源的系统事实模型。目标不是生成一个万能真相，而是显式区分配置期望、当前现场和历史记录，并尽早暴露冲突。

## 三类证据

```text
expected
= launch / YAML / static repository configuration

observed-live
= 当前 roscore / graph / topic / hardware / TF / system time

recorded
= 某次 rosbag1 录制时的历史事实
```

同名对象不代表语义相同。例如 bag 中 `/imu/data` 存在，不能证明当前 live driver 仍发布同一 message type、frame、频率或时间源。

## 输入

推荐使用：

```bash
python3 scripts/inspect_launch.py system.launch --output evidence/launch.json
python3 scripts/inspect_rosbag.py run.bag --metadata-only --output evidence/bag.json
python3 scripts/collect_runtime_snapshot.py --profile communication --output evidence/runtime.json
python3 scripts/inspect_system_hardware.py --output evidence/hardware.json
python3 scripts/inspect_tf_time.py --output evidence/tf_time.json
python3 scripts/probe_topic.py /points_raw --output evidence/topic.json
```

## 合并

```bash
python3 scripts/merge_system_evidence.py \
 --launch evidence/launch.json \
 --bag evidence/bag.json \
 --runtime evidence/runtime.json \
 --hardware evidence/hardware.json \
 --tf-time evidence/tf_time.json \
 --topic-probe evidence/topic.json
```

输出保留：

- sources；
- nodes_expected / nodes_observed_live；
- topics；
- hardware；
- time；
- conflicts；
- differences；
- unknowns；
- next_evidence。

## Topic

状态：

- `matched_presence`：live 和 bag 都看到同名 topic；
- `live_only`：当前存在但 bag 没有；
- `recorded_only`：bag 有但 live 没有；
- `conflict`：type 等关键语义冲突；
- `unknown`：证据不足。

名称一致后仍需验证 MD5、fields、frame、header stamp、frequency 和物理数据质量。

## Hardware

launch 中的设备路径只是 expected。snapshot 中设备路径是 observed-live。

冲突可能来自：

- 当前未插设备；
- udev 名称变化；
- 容器没有映射设备；
- launch 来自另一部署；
- bag 来自另一台机器人。

## TF 与时间

必须区分：

```text
host time
ROS time
/use_sim_time
/clock
sensor/device clock
header stamp
bag record time
```

host NTP 正常不等于传感器 PPS/PTP 正确。

## 状态语义

- `conflict`：两个具体来源直接矛盾；
- `changed`：观察到部署变化；
- `unknown`：缺少覆盖；
- `consistent_so_far`：现有证据未冲突，不代表系统完全正确。

禁止把 unknown 自动判定为错误。

## 下一步证据

合并后只补最小缺口：

- 缺 graph：runtime snapshot；
- 缺 TF/time：inspect_tf_time；
- 缺 topic 质量：probe_topic；
- 缺硬件：inspect_system_hardware；
- bag/live 冲突：检查 driver、overlay、message definition 和 provenance。

该脚本是 provenance-aware aggregator，不是自动根因引擎。
