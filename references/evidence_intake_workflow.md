# ROS Noetic 证据输入与自动提取工作流

当用户直接给出 `.launch`、`.bag`、运行时命令输出、日志、硬件信息或这些材料的组合时，优先使用已有材料建立事实，不先要求用户重新跑一套命令。目标是把“用户给了什么”转换成结构化证据和最小下一步。

## 目录

1. 输入路由
2. launch 提取
3. bag 提取
4. live topic 提取
5. runtime snapshot 提取
6. hardware 提取
7. 证据合并
8. 输出格式

## 1. 输入路由

| 输入 | 首选入口 | 主要回答 |
|---|---|---|
| `.launch` / `.test` / roslaunch XML | `scripts/inspect_launch.py` | 预计启动什么、参数/remap/include、硬件和运行栈提示 |
| `.bag` | `scripts/inspect_rosbag.py` | 实际录了什么 topic/type/frame/time/fields |
| live topic 名称 | `scripts/probe_topic.py` | 当前 publisher/type/sample/hz/bw/delay |
| 整机 ROS 现场 | `scripts/collect_runtime_snapshot.py` | master/graph/service/param/node 基线 |
| 机器或设备适配 | `scripts/inspect_system_hardware.py` | OS endpoint、USB/serial/network/CAN 事实 |
| 用户粘贴的命令输出 | 直接解析原文 | 先保留原始命令和输出，再决定缺哪个证据 |

脚本是证据采集器，不是最终判定器。输出中的 `observed` 只能支持对应层级的事实。

## 2. launch 提取

```bash
python3 scripts/inspect_launch.py path/to/system.launch
```

至少提取：

- `<arg>` 默认值/显式值；
- node 的 pkg/type/name/ns/args/machine/respawn/required；
- include；
- remap；
- param/rosparam；
- group namespace；
- env/machine；
- nodelet/controller/Gazebo/RViz/PCL 等 stack hint；
- `/dev/...`、serial、IP、CAN、frame、calibration 等 hardware hint；
- 尚未解析的 substitution 与 if/unless。

静态 launch 只表示 **expected configuration**，不能证明节点已启动或参数已读取。

## 3. bag 提取

```bash
python3 scripts/inspect_rosbag.py data.bag --metadata-only
python3 scripts/inspect_rosbag.py data.bag --topic /imu/data --topic /points_raw
```

提取：topic/type/MD5/connections/count/estimated average rate、callerid、header stamp/frame、PointCloud2 fields、TF 关系、GNSS/IMU 状态、`/clock`。然后与 launch/hardware 映射比较。

bag 中有 topic 只证明“被记录”，不证明 live driver 当前仍这样配置，也不证明物理数据正确。

## 4. live topic 提取

```bash
python3 scripts/probe_topic.py /points_raw
```

它对单 topic 运行有界只读检查：

```text
rostopic info
rostopic type
rostopic echo -n 1 --noarr
rostopic hz
rostopic bw
rostopic delay
```

`hz/bw/delay` 是短窗口观察；不能外推整个任务。`delay` 还依赖有效 Header 与一致时钟。

## 5. runtime snapshot 提取

```bash
python3 scripts/collect_runtime_snapshot.py --profile communication
python3 scripts/collect_runtime_snapshot.py --profile full --detail-limit 20
```

优先建立：Noetic 环境、master 注册、node/topic/service/param inventory、详细 node/topic 连接。需要数据质量时再对少数关键 topic 使用 `probe_topic.py`，不要对全图每个 topic 都做持续采样。

## 6. hardware 提取

```bash
python3 scripts/inspect_system_hardware.py
```

把硬件证据归入：

```text
machine/OS
→ USB/serial/Ethernet/CAN endpoint
→ driver/node
→ topic
→ message
→ frame
→ time source
→ calibration
```

用户若已给 `lsusb`、`ip addr`、`udevadm`、CAN、chrony/PTP 等输出，直接解析，不要求重复执行。

## 7. 证据合并

同一对象至少区分三列：

| 层 | 例子 | 证据语义 |
|---|---|---|
| expected | launch 中 `/points_raw` | 配置期望 |
| observed-live | `rostopic info/hz` | 当前运行现场 |
| recorded | bag 中 `/points_raw` | 某次采集历史 |

比较时使用：

- `matched`：名称/type/frame/time 语义一致；
- `changed`：已观察到差异；
- `unknown`：证据不足；
- `conflict`：两个高可信来源直接矛盾。

不要把 `unknown` 自动归为错误。出现 conflict 时先定位来源时间、机器、branch、launch、bag 采集硬件和 workspace overlay。

## 8. 输出格式

收到证据后默认输出：

1. **系统事实**：已观察到的版本、节点、硬件、topic、frame、time；
2. **差异/异常**：expected vs live vs bag；
3. **当前最多三个假设**；
4. **最小下一步命令**：每条都说明为什么、预期什么、哪种输出区分哪个假设；
5. **权限级别**：只读 / 写参数 / 发布或调用 / 回放 / 硬件动作；
6. **停止条件**：得到什么证据后就不再扩大扫描。

这套工作流的目标是让 Skill 对输入材料做“证据路由”，而不是见到任何 ROS 问题都让用户运行完整 checklist。
