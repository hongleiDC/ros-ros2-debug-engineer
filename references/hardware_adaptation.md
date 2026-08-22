# ROS Noetic 硬件适配与系统勘察

本参考用于陌生机器人、传感器计算机、车载工控机和回放环境。Skill 不应只看 ROS graph；必须建立 **硬件 → OS 设备 → 驱动/节点 → topic → message → frame → time → 参数/标定** 的可追溯链。

## 目录

1. 勘察循环
2. 系统指纹
3. USB/串口
4. Ethernet 传感器
5. CAN
6. LiDAR
7. IMU
8. GNSS/RTK/双天线
9. Camera
10. 时间同步
11. 硬件到 ROS 的映射表
12. 何时重新勘察

## 1. 勘察循环

面对未知系统时至少完成：

```text
机器与 OS
→ ROS/overlay
→ 物理设备
→ /dev 或 IP/CAN 接口
→ 驱动 package/node
→ ROS topic/service
→ message type/fields
→ frame/TF
→ timestamp/time source
→ 参数/标定
```

不要把“topic 存在”直接等价为“硬件适配正确”。

## 2. 系统指纹

只读优先：

```bash
uname -a
lsb_release -a
hostname
hostname -I
lscpu
free -h
df -h
ip -br addr
ip route
```

GPU/加速卡在相关时再查：

```bash
lspci
nvidia-smi
```

记录容器时同时检查 host/container 的设备映射、network mode、时区和权限。

## 3. USB / 串口

```bash
lsusb
lsusb -t
ls -l /dev/serial/by-id/
ls -l /dev/serial/by-path/
dmesg | tail -n 80
udevadm info --query=all --name=/dev/ttyUSB0
```

适配时优先使用 `/dev/serial/by-id/...` 或明确 udev rule，而不是长期依赖会变化的 `/dev/ttyUSB0`。

串口问题区分：

- 设备未枚举；
- VID/PID 或 serial 不符合预期；
- 权限/dialout；
- 波特率、data bits、parity、stop bits；
- 驱动打开了错误端口；
- USB 重连后设备名漂移；
- 数据存在但协议解析失败。

不要为了“测试串口”向未知设备写入协议数据。

## 4. Ethernet 传感器

```bash
ip -br addr
ip route
ip neigh
ping -c 3 SENSOR_IP
ss -lntup
```

只有网络确实是候选根因时再抓包：

```bash
sudo tcpdump -ni INTERFACE host SENSOR_IP
```

检查 sensor IP、host IP、netmask、route、VLAN、防火墙、MTU、multicast/unicast 模式以及容器 network。

## 5. CAN

```bash
ip -details link show can0
ip -statistics link show can0
```

如果系统安装 can-utils：

```bash
candump can0
```

`cansend` 会写总线，默认禁止。确认 bitrate、termination、bus-off/error counters 和对应 ROS driver。

## 6. LiDAR

建立以下映射：

```text
型号/序列号
→ Ethernet/USB 接口
→ driver package/version
→ packet/raw topic
→ PointCloud2 topic
→ frame_id
→ per-point time 字段
→ scan rate
→ extrinsic
```

ROS 侧：

```bash
rostopic info /points_raw
rostopic type /points_raw
rostopic hz /points_raw
rostopic bw /points_raw
rostopic echo -n 1 /points_raw/header
rostopic echo -n 1 /points_raw/fields
```

重点检查 `sensor_msgs/PointCloud2` 的字段名、datatype、point_step、width/height、is_dense、frame_id。不同 LiDAR driver 的 ring/time/timestamp 字段可能不同，必须看实际字段，不能猜。

## 7. IMU

ROS 侧：

```bash
rostopic type /imu/data
rosmsg show sensor_msgs/Imu
rostopic hz /imu/data
rostopic delay /imu/data
rostopic echo -n 1 /imu/data
```

确认：

- angular velocity 单位 rad/s；
- linear acceleration m/s^2；
- orientation 是否真实有效；
- covariance 中 `-1` 的语义；
- frame_id；
- timestamp 来源；
- 静止时 bias/noise；
- 驱动是否做轴向重排或单位转换。

## 8. GNSS / RTK / 双天线

常见 ROS 消息可能包括：

```text
sensor_msgs/NavSatFix
nav_msgs/Odometry
geometry_msgs/TwistStamped
geometry_msgs/PoseStamped
厂商自定义消息
```

先看实际类型：

```bash
rostopic info /fix
rostopic type /fix
rostopic echo -n 1 /fix
```

双天线 heading 必须明确：

- baseline 从 primary 指向 secondary 还是反向；
- 输出 heading 是北起顺时针还是 ENU yaw；
- 单位 degree/radian；
- 真北/磁北；
- antenna frame 与 base_link 外参；
- 固定解/浮点解/无解状态；
- heading 有效速度或基线条件。

不要只调 `heading_offset` 让轨迹“看起来对”；先确认定义和安装方向。

## 9. Camera

```bash
rostopic info /camera/image_raw
rostopic hz /camera/image_raw
rostopic bw /camera/image_raw
rostopic echo -n 1 /camera/camera_info
```

OS 层按接口选择 `lsusb`、`v4l2-ctl --list-devices` 等；仅在工具已安装时使用。确认 image encoding、resolution、frame rate、camera_info、trigger/time source 与 extrinsic。

## 10. 时间同步

硬件适配必须回答“时间从哪里来”。

系统层按实际安装选择：

```bash
timedatectl
chronyc tracking
chronyc sources -v
```

PTP 系统按部署检查 `ptp4l/phc2sys` 状态和日志。不要因为主机 `date` 接近就断言传感器时间同步正确。

ROS 层：

```bash
rostopic delay /topic
rostopic echo -n 1 /topic/header
rosparam get /use_sim_time
```

区分 sensor clock、host receive time、header.stamp、bag record time 和 ROS time。

## 11. 硬件到 ROS 的映射表

对复杂系统建议维持一张最小事实表：

| Hardware | OS endpoint | Driver/node | ROS interface | Type | Frame | Time source | Calibration | Status |
|---|---|---|---|---|---|---|---|---|
| LiDAR A | 192.168.1.201 | `/lidar_driver` | `/points_raw` | PointCloud2 | `lidar` | sensor/PTP | lidar→base | observed |
| IMU A | `/dev/serial/by-id/...` | `/imu_driver` | `/imu/data` | Imu | `imu_link` | device | imu→base | observed |

信息不确定时写 `unknown`，不要补猜测。

## 12. 何时重新勘察

不是每一轮都从头检查。出现以下变化时重新刷新对应域：

- 换电脑、容器、网卡或 kernel；
- USB 重插、设备路径变化；
- 传感器/固件/driver 版本变化；
- ROS workspace/overlay 变化；
- launch/namespace/remap 变化；
- IP、route、PTP/NTP 配置变化；
- 标定文件变化；
- bag 换成另一辆车/另一套硬件采集的数据。

每次刷新都把新证据与旧证据比较，指出 **changed / unchanged / unknown**，而不是重新堆一份无差别命令输出。
