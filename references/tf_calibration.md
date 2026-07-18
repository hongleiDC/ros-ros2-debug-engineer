# TF、URDF 与标定

## 变换约定

使用 `T_parent_child` 表示把 child 坐标中的点变换到 parent：

```text
p_parent = T_parent_child * p_child
```

每个标定记录必须包含 parent、child、数学约定、translation、rotation、单位、来源、版本、设备 ID、适用软件 commit、状态和验证范围。

## 坐标系

核对机器人主体、传感器和 optical frame 的轴方向。保持 `map`、`odom`、`base_link` 语义稳定。不要把 GNSS ENU 直接命名为 `map`，除非系统明确定义二者等价；否则显式维护变换。

## TF 运行时检查

检查：

- 同一 child 是否有多个 authority；
- 静态 TF 是否同时来自 bag、URDF 和 launch；
- dynamic transform 的时间戳、发布频率和 buffer 范围；
- lookup 使用的时间和 timeout；
- extrapolation into past/future；
- 多机器人 frame prefix 和 namespace；
- robot_state_publisher 与额外发布者是否冲突。

## 旋转与单位

明确 quaternion 顺序，ROS 通常使用 `x,y,z,w`。四元数必须归一化。明确角度是 degree 还是 radian，平移是 m、cm 还是 mm。矩阵复制到算法前核对方向，必要时求逆。

## 标定验证

不能仅以“数值看起来合理”验证。根据任务使用：

- 静态场景重投影或点云重合；
- 运动场景 deskew 和边缘一致性；
- 多段数据、不同温度和不同速度；
- 对照标定与独立验证数据；
- before/after 指标及失败样例。

标定只对指定设备、安装状态、固件、算法约定和时间模型有效。
