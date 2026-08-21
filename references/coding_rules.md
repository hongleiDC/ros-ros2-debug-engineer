# ROS Noetic 编码与构建规则

本文件只面向 ROS 1 Noetic。先读取目标项目现有 `package.xml`、`CMakeLists.txt`、catkin 工具链、Python/C++ 版本和 CI，不无理由升级语言标准、依赖或 workspace 结构。

## 代码边界

- 算法核心尽量不依赖 `ros::NodeHandle`、`rospy`、TF listener 或参数服务器，便于离线单测和 rosbag1 回归。
- ROS wrapper 负责消息转换、参数、TF、时间、diagnostics 和通信。
- 驱动、算法、bringup、messages/interfaces 和 analysis tooling 分层，避免巨型 package。
- nodelet/pluginlib 只在明确需要共享进程或可替换实现时使用，并记录共享故障域。

## 参数与命名

- 参数必须明确默认值、类型、单位、范围、namespace 和读取时机。
- private 参数必须明确 `~param` 语义；不要在代码、YAML 和 launch 中混用不同绝对路径。
- 启动时记录关键配置来源和最终值；dynamic_reconfigure 的在线值变化要可追溯。
- 关键变量名表达物理意义和单位，例如 `time_offset_s`、`angular_velocity_rad_s`、`position_map_m`。
- 禁止用 `tmp`、`val`、`data2` 等长期承载关键物理量。

## 时间、TF 与数据

- 不用 `ros::Time::now()` / `rospy.Time.now()` 冒充传感器测量时间。
- 区分 measurement time、callback time、bag record time 和 ROS time。
- TF、外参、四元数和矩阵必须说明 parent/child、方向、单位和乘法约定。
- 对 NaN、Inf、空数组、越界字段、时间回退、状态无效和设备重启明确处理。
- 数据丢弃必须有原因计数；高频日志使用 throttle。

## roscpp 并发

共享状态必须明确：

- `ros::spin()` 还是 `AsyncSpinner` / `MultiThreadedSpinner`；
- 默认还是自定义 `ros::CallbackQueue`；
- callback 是否阻塞；
- 锁顺序与生命周期；
- shutdown 时线程唤醒、设备关闭和 join。

callback 内避免不可控同步 I/O、长时间 sleep 和在持锁状态下等待 service/action。

## rospy 并发

明确 subscriber/service/timer callback 的共享状态保护，关注 Python GIL、阻塞 I/O、后台线程退出和异常传播。不要用 ROS 2 executor/callback group 术语解释 rospy。

## catkin 构建

优先检查目标 package 和直接上游：

- `package.xml` 与 `CMakeLists.txt` 依赖一致；
- `find_package(catkin REQUIRED COMPONENTS ...)`；
- `catkin_package(INCLUDE_DIRS LIBRARIES CATKIN_DEPENDS DEPENDS ...)`；
- `include_directories` / `target_link_libraries`；
- message/service/action generation；
- `message_generation` 与 `message_runtime`；
- dynamic_reconfigure generation；
- nodelet/pluginlib export；
- Python `catkin_install_python`、可执行位和 shebang；
- install/export 规则，而不只验证 devel space。

不要在 Noetic 分支默认引入 ament/colcon、rosidl、ROS 2 component resource index。

## overlay 与 ABI

overlay 问题必须记录 source 顺序和关键变量：

```bash
echo "$ROS_PACKAGE_PATH"
echo "$CMAKE_PREFIX_PATH"
rospack find <pkg>
```

出现“编译正确但运行加载旧库/旧消息”时，检查：旧 devel/install、重复 package、LD_LIBRARY_PATH/PYTHONPATH、message MD5 和 workspace source 顺序。

## 公式与变量追溯

涉及数学模型时读取 `formula_variable_traceability.md`：

- 建立公式符号到代码变量映射；
- 记录单位、frame、时间基准、形状和索引顺序；
- 魔法数替换为具名常量并注明来源；
- 公式实现附近保留公式/推导 ID；
- 用可手算样例测试符号、单位和边界。

在 audit 模式下，修改公式相关代码前读取对应 `FORM-*`、`MAP-*`、`REAS-*` 并运行 `logic_audit.py`。普通 micro/debug 不为此自动创建知识记录。

## 输出范围

新增独立节点至少提供：源码、`package.xml`、`CMakeLists.txt`、必要 launch/YAML、运行命令和最小测试。局部修复只增加与已验证根因直接相关的代码和测试，不顺带进行仓库级重构。
