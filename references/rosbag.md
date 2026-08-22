# ROS Noetic rosbag1 调试

本文件仅适用于 ROS 1 Noetic 的 `rosbag`（rosbag1），不是 rosbag2。目标不是只回答“bag 能不能播”，而是建立 **bag → topic → message → time/frame → driver/sensor → algorithm input** 的证据链。

## 录制前

记录：

- `ROS_VERSION=1`、`ROS_DISTRO=noetic`；
- bag 文件路径和命名；
- topic 白名单/排除规则；
- `--split`、`--size`、`--duration`、`--bz2` / `--lz4`；
- 主机时间状态；
- 设备配置、参数快照和代码 commit；
- 是否包含 `/tf`、`/tf_static`、`/clock`、控制 topic。

典型命令：

```bash
rosbag record -O run.bag /imu/data /points_raw /tf /tf_static
rosbag info run.bag
```

录制属于写文件动作；真实系统录制前同时评估磁盘空间、I/O 带宽和是否会影响传感器处理进程。

## 第一层：bag 元数据

先做只读检查：

```bash
rosbag info run.bag
rosbag info --yaml run.bag
rosbag check run.bag
```

至少提取：

- duration / start / end；
- bag size、compression、indexed；
- message total；
- 每个 topic 的 type、message count、connections、frequency（元数据可提供时）；
- message type 对应的 MD5；
- `/tf`、`/tf_static`、`/clock` 和控制类 topic 是否存在。

不要把 `message count / whole-bag duration` 当作严格实时频率，只把它当粗略 bag-average rate。

## 第二层：topic 画像

推荐使用本 Skill 的只读检查器：

```bash
python3 scripts/inspect_rosbag.py run.bag
python3 scripts/inspect_rosbag.py run.bag --topic /imu/data --topic /points_raw --sample-per-topic 3
python3 scripts/inspect_rosbag.py run.bag --metadata-only
```

需要实验身份固定时才额外计算文件哈希：

```bash
python3 scripts/inspect_rosbag.py run.bag --hash --output run.bag.report.json
```

`--hash` 会完整读取 bag 文件，因此大 bag 上可能耗时和产生磁盘 I/O。

对每个关键 topic 至少形成：

| 证据 | 用途 |
|---|---|
| topic name | namespace/remap/算法输入匹配 |
| message type + MD5 | 接口兼容、旧 bag 与当前自定义消息兼容 |
| messages/connections | 录制覆盖、publisher connection 数 |
| reported/bag-average rate | 粗筛频率异常 |
| callerid（可获得时） | 录制时 publisher 来源 |
| Header stamp/frame_id | 时间和坐标语义 |
| bag time - header stamp | 采集/传输/排队线索，不直接等于单一网络延迟 |
| message-specific fields | 验证算法真正需要的字段 |

bounded sample 只能说明采样消息，不可据此声称整个 bag 无 gap、无乱序、无时间回退。需要完整结论时做全量时序统计。

## 消息类型专项

### sensor_msgs/PointCloud2

至少看：

- `header.frame_id`；
- width / height；
- point_step / row_step；
- `is_dense`；
- fields：`x/y/z`、intensity、ring/channel、per-point time/timestamp 等。

算法需要 ring 或点时间但 bag 中不存在时，应直接判定输入契约缺失，而不是靠参数调优绕过。

### sensor_msgs/Imu

至少看：

- frame；
- stamp；
- angular velocity / linear acceleration；
- orientation 是否有效；
- covariance 语义；
- 轴方向、单位和时间源是否与算法一致。

### sensor_msgs/NavSatFix / GNSS / RTK 自定义消息

至少看 fix/status、covariance/quality、frame 和 stamp。RTK fixed/float、heading、satellite count、differential age 等如果在自定义消息中，先用当前消息定义解释，不猜厂商字段。

### sensor_msgs/Image / CameraInfo

看尺寸、encoding、frame、时间和 camera_info；图像存在不代表内参/畸变参数正确。

### TF

提取 parent-child 对、stamp、静态/动态来源。bag 中 TF 完整不代表 launch 没有同时重复发布同一 static transform。

## header.stamp 与 bag record time

重点区分：

- sensor/device timestamp；
- driver timestamp；
- ROS system time；
- bag record time。

`bag_time - header.stamp` 可暴露明显排队、错误时钟域或旧数据，但其物理含义取决于驱动如何设置 Header。没有确认时间源前，不把这个差值称为“网络延迟”。

## 自定义消息与 MD5

旧 bag 与当前 workspace 的自定义 `.msg/.srv/.action` 不一致时可能无法正常反序列化。检查：

```bash
rostopic type /topic
rosmsg show PACKAGE/Message
rosmsg md5 PACKAGE/Message
```

再核对 overlay/source 顺序、生成产物和 bag 录制时的代码版本。

## bag 损坏与索引

只读先检查：

```bash
rosbag info run.bag
rosbag check run.bag
```

`rosbag reindex` 会写索引/恢复文件，不作为默认只读步骤；执行前保留原 bag。

## 回放

1. 默认隔离真实执行器和控制 topic。
2. 明确 `use_sim_time`、`--clock`、`-r/--rate`、`-s/--start`、`-d/--duration`、`--pause`、`-l/--loop`。
3. 回放前确认 launch 是否会重复发布 `/tf_static` 或其他固定数据。
4. 检查 bag 中是否包含 `/cmd_vel`、trajectory、actuator、mission 等控制类 topic；未经授权不要回放到真实系统。
5. loop 会导致仿真时间回退，算法必须明确处理或禁止 loop。
6. live 正常而 bag 失败时，优先比较：缺失 topic、参数、TF、clock、header stamps、driver-only side effects 和启动顺序。

典型命令：

```bash
rosparam set use_sim_time true
rosbag play run.bag --clock -r 1.0
```

这两条会修改运行系统/发布消息，不属于默认只读诊断。

## A/B 回归

baseline/candidate 必须保持：

- 同一 `.bag`；
- 同一回放 rate/start/duration；
- 同一 launch 与参数加载方式；
- 同一 TF/static transform 来源；
- 同一指标、对齐和时间定义。

至少区分静态包、短运动包、完整线路包和异常包。保存 bag ID、哈希、录制配置、适用 commit、关键 topic 画像、预期指标和已知限制，不把大型 bag 本体打包进 Skill。
