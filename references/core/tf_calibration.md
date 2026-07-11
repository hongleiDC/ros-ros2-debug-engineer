# TF、内参与外参规则

## 外参命名

使用 `T_parent_child`，表示把 child 坐标中的点变换到 parent：

```text
p_parent = T_parent_child * p_child
```

每个标定记录必须包含 parent/child、translation、rotation、单位、来源、版本、设备 ID、状态和验证范围。

## 内参分类

- LiDAR：扫描频率、盲区、距离范围、点字段、时间字段、坐标轴、回波/强度定义。
- IMU：量程、带宽、输出频率、噪声密度、随机游走、bias instability、单位、轴定义、重力是否包含。
- RTK：更新率、定位模式、协方差来源、天线相位中心、双天线基线、时间格式和状态码。

## TF 检查

1. 同一 parent-child 只能有一个权威发布者。
2. `/tf_static` 在 bag 和 launch 中重复发布时，回放优先关闭 launch 中的静态 TF。
3. `map`、`odom`、`base_link` 语义保持稳定；不要把 RTK ENU 直接冒充 `map`，应显式估计 `T_map_enu`。
4. 标定矩阵写入算法配置前，核对算法期望方向；必要时求逆，不能只复制数字。
5. 四元数必须归一化；RViz Marker orientation 未设置时显式设 `w=1`。
