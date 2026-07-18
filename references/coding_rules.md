# ROS 编码与构建规则

## 适配现有项目

读取现有 `package.xml`、`CMakeLists.txt`、`setup.py/setup.cfg`、工具链和 CI 后再决定标准。不要无理由升级整个项目的 C++ 或 Python 版本。

## 通用

- 参数声明默认值、类型、单位、范围和意义；启动时记录关键配置。
- 传感器 callback 避免无界阻塞和无界队列。
- 共享状态明确锁、callback group 和 executor 语义。
- 数据丢弃路径记录原因计数并使用节流日志。
- 不用 `now()` 冒充传感器测量时间。
- shutdown 停止线程、唤醒条件变量、关闭设备并 join。
- 对 NaN、Inf、空数组、越界字段和时间回退进行明确处理。

## 构建

- 先解析依赖，再构建目标包和上游依赖。
- 检查 install/export 规则，不能只验证 build tree。
- ROS 1 检查 catkin、message generation、nodelet/plugin 导出。
- ROS 2 检查 ament、interface generation、component/plugin 导出和 resource index。
- overlay 问题要记录每个 workspace 的 source 顺序。

## ROS 2

- 显式选择 QoS，不把所有传感器一律硬编码为同一 profile。
- launch 参数、节点参数、remap 和 namespace 分开表达。
- 明确 lifecycle、callback group、executor 和 composition。
- 回放时确认 `use_sim_time` 和 `/clock`。

## 输出范围

新增独立节点至少提供源码、依赖、安装规则、launch、参数示例、运行命令和测试。局部修复只增加与问题直接相关的文件和测试。
