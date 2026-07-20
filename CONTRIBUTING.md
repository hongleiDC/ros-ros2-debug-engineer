# Contributing

感谢你改进 `ros-ros2-debug-engineer`。

## 提交问题前

请先确认问题来自 Skill 本身，而不是目标 ROS 项目的构建或运行环境。问题报告应尽量包含：

- 使用的 ROS 版本与发行版；
- 操作系统、Python 版本和 RMW；
- Skill 版本或对应提交；
- 最小复现步骤；
- 预期行为与实际行为；
- 已脱敏的日志或测试输出。

不要提交密钥、证书、设备序列号、客户数据、未脱敏地图或现场网络信息。

## 修改要求

1. 保持诊断默认只读，不扩大硬件操作权限。
2. 不把静态信号描述为运行时事实。
3. 发行版相关命令必须说明适用版本。
4. 新增或改变脚本行为时补充测试。
5. 文件写入应使用路径边界检查、锁和原子替换。
6. 公式相关逻辑必须保留单位、frame、方向和变量语义。

## 本地验证

```bash
python3 -m pip install -r requirements.txt
python3 scripts/preflight.py --require knowledge
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py . dist
```

提交前确认测试全部通过、`skill.zip` 可正常解压，并且没有把项目数据或本地缓存加入仓库。

## Pull Request

PR 说明应包含：

- 修改了什么；
- 为什么需要修改；
- 对用户和现有工作流的影响；
- 已运行的验证；
- 未覆盖的 ROS 发行版、平台或硬件边界。
