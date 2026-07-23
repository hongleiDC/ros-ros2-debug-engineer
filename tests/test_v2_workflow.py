from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class V2WorkflowTest(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
            timeout=90,
        )

    def test_default_workflow_is_architecture_first_and_token_efficient(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 120)
        for mode in ["`debug`", "`architect`", "`audit`"]:
            self.assertIn(mode, skill)
        for reference in [
            "fast_debugging.md",
            "architecture_design.md",
            "architecture_patterns.md",
            "audit_mode.md",
        ]:
            self.assertIn(reference, skill)
            self.assertTrue((ROOT / "references" / reference).is_file())
        self.assertIn("每轮最多保留三个活动假设", skill)
        self.assertIn("不默认扫描整个仓库", skill)
        self.assertIn("不要以“节点越多越模块化”为原则", skill)
        self.assertNotIn("每完成 2 至 3 组工具调用", skill)
        self.assertIn("只有该模式才默认启用", skill)

    def test_architecture_reference_requires_concrete_ros_design(self) -> None:
        design = (ROOT / "references" / "architecture_design.md").read_text(encoding="utf-8")
        for required in [
            "package", "component", "msg/srv/action", "QoS", "TF",
            "executor", "callback group", "lifecycle", "故障恢复", "部署",
        ]:
            self.assertIn(required, design)
        patterns = (ROOT / "references" / "architecture_patterns.md").read_text(encoding="utf-8")
        for required in ["纯算法核心", "ROS 适配层", "独立进程", "Component composition", "反模式"]:
            self.assertIn(required, patterns)

    def test_audit_tools_remain_available_but_optional(self) -> None:
        for relative in [
            "references/formula_variable_traceability.md",
            "references/reasoning_knowledge_base.md",
            "scripts/goal_guard.py",
            "scripts/experiment_registry.py",
            "scripts/logic_audit.py",
            "scripts/register_reasoning_knowledge.py",
        ]:
            self.assertTrue((ROOT / relative).is_file())
        audit = (ROOT / "references" / "audit_mode.md").read_text(encoding="utf-8")
        self.assertIn("普通编译", audit)
        self.assertIn("不要升级到审计模式", audit)

    def test_invalid_goal_yaml_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state"
            goals = state / "goals"
            goals.mkdir(parents=True)
            (goals / "broken.yaml").write_text("goal_id: [", encoding="utf-8")
            result = self.run_script("goal_guard.py", "show", str(state))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid goal record", result.stderr + result.stdout)

    def test_package_rejects_links_outside_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            (root / "agents").mkdir(parents=True)
            (root / "scripts").mkdir()
            (Path(tmp) / "outside.md").write_text("outside", encoding="utf-8")
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A sufficiently detailed demo skill description for validation.\n---\n[bad](../outside.md)\n",
                encoding="utf-8",
            )
            (root / "agents" / "openai.yaml").write_text(
                "interface:\n  display_name: Demo\n  short_description: Demo skill\n  default_prompt: Use $ros-ros2-debug-engineer.\n",
                encoding="utf-8",
            )
            result = self.run_script("package_skill.py", str(root), str(Path(tmp) / "dist"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes skill root", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
