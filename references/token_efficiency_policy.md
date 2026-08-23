# ROS Noetic Token Efficient Analysis Policy

目标：在保持诊断质量的同时减少重复上下文加载。

## 默认顺序

```text
session_summary
→ profile diff
→ changed domain evidence
→ targeted reference
→ full evidence only if required
```

## 不重复加载

如果满足：

- profile 域 unchanged；
- provenance 没变化；
- 没有新 conflict；
- validation 仍通过；

则复用历史结论，不重新读取完整 launch、bag、hardware 或 TF 文档。

## 扩大范围条件

只有以下情况才重新扫描：

- 新硬件 endpoint；
- driver/package/overlay 改变；
- topic message contract 改变；
- frame/time 变化；
- bag 来源变化；
- 用户明确要求 audit。

## 输出原则

优先输出：

1. 当前已知事实；
2. 本次变化；
3. 受影响域；
4. 下一步最小证据。

不要重复输出已经验证稳定的系统背景。
