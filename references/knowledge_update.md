# 项目知识更新

## 状态

- `candidate`：推断或待复现。
- `measured`：由代码、设备、bag 或统计直接测得。
- `verified`：修复后通过明确回归。
- `deprecated`：被新版本替代并保留历史。

结构验证通过不等于状态可以设为 `verified`。

## 写入前

1. 确认用户授权 `persist`。
2. 确认目标仓库、branch、commit、设备和配置。
3. 读取旧值和证据，避免覆盖其他适用范围的记录。
4. 对 verified 记录的替换要求显式授权和替代证据。

## 更新

优先使用：

```bash
python3 scripts/update_knowledge.py \
  /path/to/project_knowledge \
  active_configuration.yaml \
  configuration.use_sim_time \
  true \
  --status measured \
  --reason "bag replay configuration" \
  --evidence "launch file and runtime parameter"
```

脚本使用锁、事务恢复日志、结构验证和回滚。若发现未完成事务，先恢复再继续。

## 证据

每条记录尽量包含来源类型、命令或文件、bag ID、样本数量、代码 commit、设备序列号、时间、适用范围和验证方法。

## 发布

知识更新不自动 commit 或 push。用户明确要求发布后，再报告仓库、branch、commit、文件、旧值、新值、状态和验证结果。

## 推理和公式知识更新

FORM、MAP、REAS 和 AUD 记录使用 `scripts/register_reasoning_knowledge.py` 登记。verified 或 deprecated 记录不得原地覆盖；公式语义、符号、单位、frame、方向、时间基准或状态顺序变化时，创建新公式版本和新映射，并标明旧记录失效范围。

任何公式相关代码修改完成后，运行 `scripts/logic_audit.py --workspace ... --write-report --strict-warnings`。审计报告必须绑定当前 commit。审计失败时不得将对应结论、公式映射或代码实现提升为 verified。

