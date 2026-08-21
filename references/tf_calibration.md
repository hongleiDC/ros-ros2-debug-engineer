# ROS Noetic TF、URDF 与标定

## 变换约定

使用 `T_parent_child` 表示把 child 坐标中的点变换到 parent：

```text
p_parent = T_parent_child * p_child
```

每个标定记录必须包含 parent、child、数学约定、translation、rotation、单位、来源、版本、设备 ID、适用软件 commit、时间模型、状态和验证范围。

## Noetic TF 栈

ROS Noetic 项目可能使用 tf1、tf2_ros 或两者混合。先识别代码实际 API，不把 ROS 2 TF 工具链假设套进来。

常用只读工具：

```bash
rosrun tf tf_echo parent child
rosrun tf view_frames
rosrun tf tf_monitor
rosrun tf2_ros tf2_echo parent child
rosrun tf2_tools view_frames.py
rostopic info /tf
rostopic info /tf_static
```

工具是否存在取决于安装包；不要因为某个辅助命令缺失就把它判断成 TF 本身故障。

## 坐标系

核对机器人主体、传感器和 optical frame 轴方向。保持 `map`、`odom`、`base_link` 语义稳定。

不要把 GNSS ENU 直接命名为 `map`，除非系统明确规定二者等价；否则显式维护 `map <-> ENU` 关系，并记录原点、航向定义和转换版本。

双天线 GNSS heading 必须明确：

- 天线 1→2 还是 2→1；
- heading 相对真北/磁北/ENU x 轴/NED north；
- 顺/逆时针正方向；
- 度还是弧度；
- 天线基线到 `base_link` yaw 的固定安装偏差。

## 静态 TF

Noetic 中静态变换可能来自：

- URDF + robot_state_publisher；
- `static_transform_publisher`；
- 驱动内部；
- launch；
- rosbag 中录制的 `/tf_static`。

同一 child 不应存在互相竞争的 authority。回放 bag 时尤其检查现场 static publisher 与 bag 内静态 TF 是否重复。

不要假设 ROS 2 的 `/tf_static` QoS 机制；Noetic 诊断以实际 `/tf_static` topic、发布者和 tf2 buffer 行为为准。

## 运行时检查

重点检查：

- 同一 child 是否有多个 authority；
- transform 是否连通；
- dynamic transform 的 stamp、频率和 buffer 范围；
- lookup 使用 `ros::Time(0)` 还是指定测量时刻；
- timeout 是否合理；
- extrapolation into past/future；
- 时间回退时 TF buffer 行为；
- 多机器人 frame prefix / namespace；
- robot_state_publisher 与额外发布者冲突。

`ros::Time(0)` 返回“最新可用”不等价于“测量时刻正确”。融合/deskew 必须用与 measurement time 一致的 transform。

## 旋转与单位

ROS message quaternion 顺序通常为 `x,y,z,w`。四元数必须归一化。明确角度 degree/radian、平移 m/cm/mm、Euler 顺序和主动/被动旋转约定。

矩阵复制到算法前核对方向，必要时显式求逆，不通过“调一个负号直到看起来对”完成标定。

## URDF

检查：

- fixed joint 与实际安装一致；
- parent/child 没有反转；
- mesh visual 方向不能替代 link frame 语义；
- xacro 参数最终展开值；
- robot_state_publisher 是否使用正确 `robot_description`；
- 多个 launch 是否重复载入不同版本 URDF。

## 标定验证

不能只以“数值看起来合理”验证。根据任务使用：

- 静态场景重投影或点云重合；
- 运动场景 deskew 与边缘一致性；
- 正反向行驶、转弯、加减速等不同激励；
- 多段数据、温度、速度；
- 独立验证数据而非只在标定集上评估；
- before/after 指标、误差分量与失败样例。

标定只对指定设备、安装状态、固件、算法约定和时间模型有效。传感器重新安装、支架松动、固件时间语义改变后，旧标定必须降级为待复核。
