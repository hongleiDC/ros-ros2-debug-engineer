# INC-0004 bag 回放重复发布静态 TF

- status: verified

## symptom

回放时 TF 冲突、RViz 跳变或存在两个静态变换发布者。

## root_cause

bag 已包含 `/tf_static`，launch 又发布相同静态 TF。

## fix

bag 回放时设置 `publish_static_tf:=false`，真实设备在线运行再由 launch 发布。

## regression

检查 `/tf_static` 发布者和 frame tree，确保每条静态边只有一个权威来源。
