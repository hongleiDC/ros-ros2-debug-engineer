# INC-0003 PointCloud2 转换丢失或误解点级时间

- status: measured

## symptom

CT-LIO 能启动，但运动时地图拉厚、重影或撕裂；静态包不明显。

## root_cause

CustomMsg 转 PointCloud2 时丢失 `offset_time`，或把 ns 当 s，或把绝对时间当相对 offset。

## fix

保留 `time`/`offset_time` 字段，明确单位和相对参考时刻。转换后检查首点、末点和帧跨度。

## regression

使用转动和 20 km/h 速度阶梯包检查墙面厚度、轨道重影和点时序范围。
