# ROS Noetic Session Memory

## Purpose

保存长期项目中已经确认的信息，避免重复加载全部证据和重复询问机器人背景。

## Memory structure

```yaml
robot:
  platform:
  ros_distro: noetic

known:
  hardware:
  drivers:
  topics:

verified:
  tf:
  time:
  calibration:

stable:
  components:

unknown:
  - item

last_update:
  evidence:
  profile_version:
```

## Rules

- 只保存带 provenance 的事实。
- unknown 不自动补全。
- hardware/driver/frame/time 变化时更新对应域。
- 新会话优先读取 session memory，再决定是否需要完整 evidence refresh。
