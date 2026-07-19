# ROS 编码与构建规则

## 适配现有项目

读取现有 `package.xml`、`CMakeLists.txt`、`setup.py/setup.cfg`、工具链和 CI 后再决定标准。不要无理由升级整个项目的 C++ 或 Python 版本。

## 公式与变量命名

- 涉及数学模型时，先读取 `formula_variable_traceability.md`，建立公式符号到代码变量的映射表。
- 关键变量名必须表达物理意义和单位，例如 `time_offset_s`、`angular_velocity_rad_s`、`position_map_m`。
- 禁止用 `a`、`tmp`、`val`、`data2` 等名称承载长期存在或影响结果的关键量。
- TF、外参、四元数和矩阵必须说明 frame、方向、维度和乘法约定。
- 魔法数必须替换为具名常量，并注明来源、单位和适用范围。
- 公式实现附近引用公式或推导编号，并用可手算样例测试符号、单位和边界。

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

## 公式相关代码的知识库门禁

- 修改公式相关代码前，读取对应 `FORM-*`、`MAP-*` 和 `REAS-*`，并运行一次 `logic_audit.py`。
- 新增关键变量时，同步登记数学符号、物理意义、公式单位、代码单位、frame、方向、时间基准、形状、索引顺序、类型和代码位置。
- 一个 identifier 不得在不同位置代表不同物理量、单位、frame 或方向。
- 变量重命名、单位转换、状态顺序变化或文件移动后，MAP 中的 identifier、行范围、commit 和测试证据必须同步更新。
- 代码修改后严格审计未通过时，不得宣称实现逻辑正确或对应成功判据已满足。

