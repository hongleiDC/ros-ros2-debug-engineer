# INC-0005 IMU 加速度重复缩放

- status: verified

## symptom

静态加速度模长不接近 9.8 m/s²，初始化或重力估计异常。

## root_cause

驱动已输出 m/s²，却再次乘 9.80665。

## fix

当前 `/handsfree/imu` 使用 `imu_acc_scale: 1.0`。

## regression

静态包中加速度模长约 9.82 m/s²，StaticIMUInit 成功。
