# 测试与可观测性

## 分层验证

1. 静态：format、lint、类型检查、clang-tidy/cppcheck 和配置 schema。
2. 构建：clean build、目标包 build、install space 和依赖导出。
3. 单元：纯算法、转换、时间和参数边界。
4. 集成：launch、进程退出、topic/service/action、QoS、lifecycle 和 TF。
5. 数据：短 bag、异常 bag、仿真和历史 incident。
6. 硬件：mock hardware 后再 HIL，使用安全限制。
7. 性能：CPU、memory、network、callback duration、latency 和 jitter。

## 诊断工具选择

按症状选择，不机械运行全部工具：

- 崩溃：core dump、GDB、ASan、UBSan；
- 竞态：TSan、锁顺序和 callback trace；
- 内存：heaptrack、valgrind、RSS 趋势；
- CPU/延迟：perf、ros2 tracing、callback duration；
- 通信：topic statistics、DDS/RMW 日志、网络抓包；
- 构建：verbose compiler/linker、依赖图和 clean overlay。

## 正式运行证据

当验证结论依赖 bag、轨迹、连续诊断、性能曲线或 A/B 数值时，读取 [结果管理](result_management.md) 和 [结果可视化](result_visualization.md)。SLAM/LIO/VIO/融合系统需要机制级结果时读取 [SLAM 结果画像](slam_visualization_profile.md)。

- 保存 before/after 的机器可读指标，不只保存 stdout；
- 保存复现图所需的最小 series，不要求保存所有内部变量；
- 定位/SLAM Core Evidence 默认 4–6 张，四张是最低核心证据而不是上限；
- 每个活动假设选择 1–3 张能区分机制的诊断图，仍保持最多三个活动假设；
- 完整 SLAM 验收出现 8–15 张有明确问题的正式图是正常范围，但不以图数作为质量指标；
- RViz/rqt 截图只能作为辅助诊断，不能替代正式离线指标与图；
- baseline/candidate 必须使用同一数据、对齐、时间和指标定义；
- 超过六张图时维护 `plot_manifest.json`，明确每张图回答的问题；
- 已有图和指标足以支持停止/继续时，不继续扩展日志字段和诊断分支。

## 回归判据

测试必须写出输入、环境、步骤、预期、容差和失败输出。`verified` 需要明确回归证据，不以“节点没崩溃”作为唯一标准。

对算法修改保存 before/after 指标、失败样例和代表性正式图。性能修复同时检查正确性，正确性修复同时检查性能与资源回归。
