# 安全与权限

## 默认只读

没有明确授权时，只执行读取文件、搜索代码、查看日志和只读 ROS 命令。不要创建文件、修改参数、发布 topic、调用 service/action、激活 lifecycle、加载控制器、回放命令 topic、commit 或 push。

## 写入授权

用户说“分析、检查、解释”不等于允许修改。用户说“修改、修复、实现、优化”允许工作区补丁，但不等于允许 commit 或 push。

写入前确认目标仓库、分支和文件范围。涉及 generated files、vendor、submodule、标定参数或生产部署配置时额外提示风险。

## 真实硬件

涉及底盘、机械臂、无人机、执行器、继电器或可运动设备时：

1. 默认先使用静态分析、仿真、mock hardware 或离线 bag。
2. 未明确授权，不发送运动命令，不激活控制器，不改变硬件状态。
3. 真实测试前确认急停、限速、碰撞保护、工作区隔离、现场人员和回滚方式。
4. 不关闭限位、watchdog、故障检测或安全联锁来掩盖问题。
5. 参数变化先使用保守值和短时测试，记录旧值和恢复命令。

## bag 回放

1. 回放前检查 bag 是否包含 `/cmd_vel`、trajectory、joint command、actuator、service event 或控制 action。
2. 默认使用 topic 白名单，只回放诊断需要的数据。
3. 优先隔离 ROS_DOMAIN_ID、namespace、容器或网络，避免连接现场机器人。
4. 明确 `/clock`、`use_sim_time`、回放速率和 TF 来源。

## 命令安全

- 不运行来源不明的安装脚本、二进制或 shell 管道。
- 不使用 `sudo`，除非用户明确要求并理解影响。
- 不删除 build/install/log、bag、标定或设备配置，除非先备份并获得授权。
- 不在输出中泄露 token、密码、私有证书、DDS Security key 或完整环境变量。
- 对可能阻塞的 ROS 命令设置超时。
