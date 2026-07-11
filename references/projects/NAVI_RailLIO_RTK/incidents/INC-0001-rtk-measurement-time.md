# INC-0001 RTK 使用错误时间源

- status: verified
- scope: NAVI_RailLIO_RTK

## symptom

RTK 话题和状态看似正常，但与 LIO/odom 无法稳定匹配，融合因子不进入或时间差异常。

## root_cause

把 ROS 话题到达时间、callback `now()` 或 bag 写入时间当作 RTK 测量时间。项目的权威 RTK 时间来自数据包内部 GPS week + seconds-of-week。

## evidence

用户已在项目调试中确认：RTK 实际时间位于数据包内部，不是话题到达时间。

## fix

驱动/bridge 解析包内 epoch，转换后写入原子 RTK measurement 的 `header.stamp`，同时保留原始 GPS week/SOW。callback time 只记录 latency。

## regression

比较 packet time、header stamp、bag time 和 callback time；融合匹配使用 packet-derived stamp，匹配对和 RTK 因子应持续增加。

## forbidden_regressions

- 禁止 `now()` 作为 RTK 测量时间。
- 禁止分别取“最新 position/status/heading”拼成不同 epoch 的测量。
- 禁止通过单纯放宽时间阈值掩盖时间源错误。
