# INC-0002 RTK 状态被低优先级状态覆盖

- status: measured

## symptom

raw/fix_status 已识别 `rtk_fixed` 或 `rtk_float`，随后 `NavSatFix.status` 又把状态改为 `single`。

## root_cause

多个回调独立更新同一状态，未定义质量来源优先级和 epoch 一致性。

## fix

优先级为 `raw packet/fix_status > NavSatFix.status`。NavSatFix 只兜底。更推荐发布同 epoch 的原子 RTK measurement。

## regression

录制 fixed/float/single 切换过程，确认低优先级回调不能覆盖更明确的状态。
