# ROS Noetic 专用运行栈与工具链

本参考用于 Noetic 项目中比基础 topic/service/TF 更专门的运行栈。目标是让 Skill 在看到 `actionlib`、`dynamic_reconfigure`、`nodelet/pluginlib`、`ros_control`、PCL、RViz 或 Gazebo 时，知道应该收集什么证据、使用什么命令，以及哪些动作会改变系统状态。

## 目录

1. actionlib
2. dynamic_reconfigure
3. nodelet / pluginlib
4. ros_control / controller_manager
5. PCL / PointCloud2
6. RViz
7. Gazebo
8. 组合诊断规则

## 1. actionlib

ROS 1 action 通常映射为：

```text
/<action>/goal
/<action>/cancel
/<action>/status
/<action>/feedback
/<action>/result
```

先读：

```bash
rostopic info /ACTION/status
rostopic type /ACTION/goal
rostopic hz /ACTION/status
rostopic echo -n 1 --noarr /ACTION/status
```

判断时拆开：server 是否存在、goal 是否发出、goal_id 是否一致、status 是否推进、feedback 是否持续、result 是否返回、时间是否有效。不要把“client 超时”直接等价为“算法失败”。

发送 goal/cancel 会改变系统状态，默认不做。

## 2. dynamic_reconfigure

发现服务端：

```bash
rosrun dynamic_reconfigure dynparam list
rosrun dynamic_reconfigure dynparam get /node_name
```

还应核对：

- package 中 `.cfg` 与生成目标；
- `generate_dynamic_reconfigure_options(...)`；
- callback 是否在初始化时就被调用；
- callback 内是否加锁或触发昂贵重建；
- launch/YAML 初值与运行时值是否冲突；
- 参数变化后是否真的影响算法路径。

`dynparam set` 是运行时写操作。修改前记录旧值、修改值、预期影响和恢复命令。

## 3. nodelet / pluginlib

只读检查：

```bash
rosnode info /nodelet_manager
rosrun nodelet nodelet list /nodelet_manager
rospack plugins --attrib=plugin nodelet
```

静态检查：

- `plugin.xml` 中 library path；
- class name/type/base_class_type；
- `package.xml` export；
- CMake shared library target；
- manager namespace 与 load args；
- 插件依赖库是否在当前 overlay 中解析到正确版本。

出现“manager 存在但插件不工作”时继续区分：pluginlib 加载失败、`onInit()` 异常、同 manager 内其他插件阻塞、输入 remap 错误、callback queue 饥饿和共享进程崩溃。

`nodelet load/unload` 会改变进程内容，默认不执行。

## 4. ros_control / controller_manager

先建立这条链：

```text
hardware_interface
→ RobotHW read/write
→ controller_manager update
→ controller state
→ command interface
→ actuator/hardware
```

常用只读或查询型命令：

```bash
rosrun controller_manager controller_manager list
rosrun controller_manager controller_manager list-types
rostopic info /joint_states
rostopic hz /joint_states
rostopic echo -n 1 --noarr /joint_states
```

同时查 controller manager namespace、URDF/transmission、joint 名、hardware interface 类型、控制周期、`/use_sim_time`、RobotHW `read()`/`write()` 时序和 diagnostics。

`load`、`unload`、`start`、`stop`、`switch`、spawner/unspawner 都会改变控制状态。真实硬件上必须先确认急停、限位、控制权和回滚方式。

如果 controller 显示 running 但执行器不动，不要直接改增益；先确认 command 是否产生、hardware interface 是否接收、RobotHW write 是否执行、底层总线是否发送以及硬件是否接受。

## 5. PCL / PointCloud2

ROS 侧先读消息结构，不猜 driver 字段：

```bash
rostopic type /points_raw
rosmsg show sensor_msgs/PointCloud2
rostopic hz /points_raw
rostopic bw /points_raw
rostopic echo -n 1 /points_raw/header
rostopic echo -n 1 /points_raw/fields
```

检查：

- frame_id；
- width/height、point_step/row_step；
- fields 名称、offset、datatype、count；
- `is_dense`；
- ring/time/timestamp/intensity 等字段是否真的存在；
- NaN/Inf、裁剪、坐标尺度和单位；
- PCL filter 前后点数、频率、带宽和延迟。

`pcl_ros`/`pcl_conversions` 是常见桥接层，但不能仅因 package 存在就认为字段转换正确。离线把 bag 转成 PCD 会创建文件，只在确有需要时执行。

## 6. RViz

RViz 是观察工具，不是真值来源。常见启动：

```bash
rviz
rviz -d config.rviz
```

诊断重点：

- Fixed Frame 是否正确；
- Display 的 topic/type 是否匹配；
- TF status 是否报错；
- queue size / decay time 是否只影响显示；
- PointCloud2、LaserScan、Image、Path、Marker 的 frame/time；
- 保存的 `.rviz` 是否来自另一套 namespace/frame。

“RViz 看不到”先区分数据不存在、TF 不可用、Fixed Frame 错、显示配置错和渲染/驱动问题。不要把 RViz 视觉异常自动归因于算法。

## 7. Gazebo

仿真中首先确认：

```bash
rosparam get /use_sim_time
rostopic info /clock
rostopic hz /clock
rostopic echo -n 1 /gazebo/model_states
```

再检查：

- `gazebo_ros` 是否实际启动；
- world/model/plugin 是否加载；
- URDF/SDF 与 transmission；
- plugin namespace/remap；
- `/clock` 是否推进；
- 仿真暂停、real-time factor、物理步长；
- ros_control gazebo plugin 与 controller manager 是否连接。

spawn/delete/set-state 等 Gazebo service 会改变仿真状态。即使不影响真实硬件，也要把它们视为写操作并记录实验条件。

## 8. 组合诊断规则

遇到复杂系统时不要按工具名称分散排查，而是保持一条证据链：

```text
launch/static config
→ process/node/nodelet/controller
→ graph interface
→ message schema
→ live rate/bandwidth/delay
→ TF/time
→ hardware or simulator endpoint
→ algorithm state
```

典型组合：

- **点云 nodelet 卡住**：manager/plugin → input topic → PointCloud2 fields → callback/CPU → output topic；
- **导航 action 卡住**：goal/status/result → move_base node → TF/time → costmap/sensor inputs → planner/controller state；
- **控制器不工作**：controller state → joint_states → command → RobotHW read/write → CAN/Ethernet/serial endpoint；
- **Gazebo 能跑、实车不能跑**：比较 time source、hardware interface、driver、frame、latency 和控制安全条件，不把仿真成功当作实车验证。
