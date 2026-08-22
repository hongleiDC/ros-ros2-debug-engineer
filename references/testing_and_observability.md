# ROS Noetic 测试与可观测性

## 分层验证

1. **静态**：format、lint、类型检查、clang-tidy/cppcheck、XML/YAML/schema。
2. **构建**：目标 package clean build、catkin dependency/export、message generation、nodelet/pluginlib 导出。
3. **单元**：纯算法、转换、时间、单位、参数边界，尽量不依赖 ROS master。
4. **集成**：rostest/roslaunch、进程退出、topic/service/actionlib、参数服务器和 TF。
5. **数据**：固定短 rosbag1、异常 bag、仿真和历史 incident。
6. **多机/硬件**：先 mock，再验证 `ROS_MASTER_URI`/主机解析/网络，最后进入 HIL/真实硬件并使用安全限制。
7. **性能**：CPU、memory、network、callback duration、queue growth、latency、jitter 和 rosbag 录制开销。

## Noetic 诊断工具选择

按症状选择，不机械运行全部工具：

- 崩溃：core dump、GDB、ASan、UBSan；
- 竞态/死锁：TSan（可用时）、锁顺序、线程 dump、Spinner/CallbackQueue 审计；
- 内存：heaptrack、valgrind、RSS 趋势；
- CPU/延迟：perf、callback timing、queue/processing counters；
- ROS graph：`rosnode list/info`、`rostopic info`、`rosservice info`、`roswtf`；
- 通信：`rostopic hz/bw/delay`、TCPROS 连接、主机名解析和必要的网络抓包；
- 参数：`rosparam get/list`，同时核对 private/relative/global namespace；
- TF：`tf_echo`、`tf_monitor`、view_frames（版本可用时）以及发布者唯一性；
- 构建：verbose compiler/linker、`rospack find`、catkin dependency graph、clean overlay。

Noetic 没有 ROS 2 QoS compatibility、DDS/RMW discovery、lifecycle manager、component container 或 executor/callback-group 运行模型。遇到这些字符串只能先判断是否存在版本混入或迁移残留。

## 集成测试原则

`rostest` / roslaunch 集成测试至少固定：

- package/node 名称和 namespace；
- launch args、remap、参数文件；
- master 与 `/use_sim_time` 条件；
- 输入 topic/service/action；
- timeout；
- 明确的 pass/fail 输出。

“节点启动了”不是充分判据。至少验证与任务相关的输出、连接、状态或指标。

## 正式运行证据

当验证依赖 bag、轨迹、连续诊断、性能曲线或 A/B 数值时，读取 [结果管理](result_management.md) 和 [结果可视化](result_visualization.md)。SLAM/LIO/VIO/融合系统需要机制级结果时读取 [SLAM 结果画像](slam_visualization_profile.md)。

- 保存 before/after 机器可读指标，不只保存 stdout；
- 保存复现图所需的最小 series，不要求保存所有内部变量；
- 定位/SLAM Core Evidence 默认 4–6 张；
- 每个活动假设选择 1–3 张能区分机制的诊断图，活动假设最多三个；
- 完整 SLAM 验收出现 8–15 张有明确问题的正式图是正常范围，但不以图数作为质量指标；
- RViz/rqt 截图只能作为辅助诊断，不能替代正式离线指标与图；
- baseline/candidate 必须使用同一 `.bag`、同一回放窗口、同一 `/clock`/`/use_sim_time` 语义、同一 TF 来源、同一对齐和指标定义；
- 超过六张图时维护 `plot_manifest.json`，明确每张图回答的问题；
- 已有图和指标足以支持停止/继续时，不继续扩展日志字段和诊断分支。

## 回归判据

每个回归测试写出：输入、Noetic/Ubuntu/overlay 环境、步骤、预期、容差和失败输出。`verified` 需要明确回归证据，不以“没有 crash”作为唯一标准。

算法修复同时检查正确性与性能；通信/线程修复同时确认数据语义、TF 和时间没有被旁路；多机修复要在原网络拓扑或等价复现环境验证，而不是只在单机通过。
