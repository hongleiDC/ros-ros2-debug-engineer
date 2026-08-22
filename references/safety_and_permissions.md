# ROS Noetic 安全与权限

## 默认只读

没有明确授权时，只执行读取文件、搜索代码、查看日志和只读 ROS 1 命令。不要创建文件、修改 rosparam、发布 topic、调用 service/action、加载 nodelet、启停 controller、回放控制 topic、commit 或 push。

用户说“分析、检查、解释”不等于允许修改。用户说“修改、修复、实现、优化”允许工作区补丁，但不自动等于允许 commit/push；涉及真实硬件、参数在线变更或控制器状态变化时继续遵守本文件的硬件规则。

## 写入前

确认目标仓库、分支和文件范围。涉及 generated files、vendor、submodule、标定参数、生产 launch/YAML、udev/systemd、容器镜像或 EOL 依赖源时额外提示风险。

Noetic 已 EOL。涉及安装、系统包、安全更新和长期部署时，记录 Ubuntu 20.04/镜像、apt/PPA/源码来源和可回滚方式，不把“能安装”当作“仍受支持”。

## 真实硬件

涉及底盘、机械臂、无人机、执行器、继电器或可运动设备时：

1. 默认先做静态分析、mock、仿真或离线 rosbag1。
2. 未明确授权，不 `rostopic pub` 控制命令，不调用会动作的 service/action，不加载/启动控制器，不改变硬件状态。
3. 真实测试前确认急停、限速、碰撞保护、工作区隔离、现场人员和回滚方式。
4. 不关闭限位、watchdog、故障检测或安全联锁来掩盖问题。
5. 参数变化使用保守值和短时测试，记录旧值、变更值和恢复命令。

## rosbag1 回放

回放前执行内容审查，例如：

```bash
rosbag info data.bag
```

重点检查是否包含 `/cmd_vel`、joint/trajectory command、actuator command 或其他控制 topic。默认只回放诊断所需白名单 topic。

隔离方式优先级：

- 独立 roscore / `ROS_MASTER_URI`；
- 独立容器/网络 namespace；
- remap 控制 topic；
- 明确 topic 白名单。

不要使用 ROS 2 的 domain-based isolation 语义作为 Noetic 隔离手段。

同时明确：

- `/use_sim_time`；
- `rosbag play --clock`；
- 回放速率；
- `/tf` / `/tf_static` 来源；
- 是否允许 loop 和时间回退。

## 多机网络

修改 `ROS_MASTER_URI`、`ROS_IP`、`ROS_HOSTNAME`、hosts、防火墙、VPN 或 Docker 网络前，先保存旧配置。不要为了“让 topic 通”而永久开放不必要端口或破坏主机安全策略。

## 命令安全

- 不运行来源不明的安装脚本、二进制或 shell pipe。
- 不使用 `sudo`，除非用户明确要求并理解影响。
- 不删除 build/devel/install/log、bag、标定或设备配置，除非先备份并获得授权。
- 不在输出中泄露 token、密码、私有证书、SSH key 或完整敏感环境变量。
- 对 `rostopic echo`、`rostopic hz`、`roswtf`、设备工具等可能长期阻塞的命令设置超时。
- `rosservice call`、`rostopic pub`、`rosrun nodelet load/unload` 不是只读诊断命令，必须先确认影响。
