from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

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

    def test_entrypoint_is_small_and_routes_by_real_complexity(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 80)
        for token in ["`micro`", "`standard`", "`domain`", "`component`", "`subsystem`", "`system`", "`audit`"]:
            self.assertIn(token, skill)
        self.assertIn("micro` 直接解决，不读取", skill)
        self.assertIn("最多询问一个", skill)
        self.assertIn("领域名称本身不触发审计", skill)
        self.assertIn("不要以“节点越多越模块化”为原则", skill)
        self.assertNotIn("每完成 2 至 3 组工具调用", skill)

        agent = yaml.safe_load((ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8"))
        self.assertFalse(agent["policy"]["allow_implicit_invocation"])

    def test_architecture_requires_quantified_and_migratable_design(self) -> None:
        design = (ROOT / "references" / "architecture_design.md").read_text(encoding="utf-8")
        for required in [
            "component", "subsystem", "system", "资源", "延迟预算", "带宽",
            "决策矩阵", "所有权矩阵", "Brownfield", "迁移", "回滚点",
            "package", "component", "msg/srv/action", "QoS", "TF",
            "executor", "callback group", "lifecycle", "故障恢复",
        ]:
            self.assertIn(required, design)
        self.assertIn("最多询问一个", design)

        patterns = (ROOT / "references" / "architecture_patterns.md").read_text(encoding="utf-8")
        self.assertIn("运行边界决策", patterns)
        self.assertIn("接口选择", patterns)
        self.assertIn("常见反模式", patterns)
        self.assertLessEqual(len(patterns.splitlines()), 90)

    def test_audit_is_triggered_by_risk_and_action_not_topic_name(self) -> None:
        audit = (ROOT / "references" / "audit_mode.md").read_text(encoding="utf-8")
        self.assertIn("风险 + 请求动作", audit)
        self.assertIn("概念解释", audit)
        self.assertIn("局部公式核对", audit)
        self.assertIn("保持 `debug`", audit)
        self.assertIn("准备修改、部署或验收", audit)

    def test_package_excludes_logs_and_rejects_outside_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            (root / "agents").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A sufficiently detailed demo skill description for validation.\n---\n",
                encoding="utf-8",
            )
            (root / "agents" / "openai.yaml").write_text(
                "interface:\n  display_name: Demo\n  short_description: Demo skill\n  default_prompt: Use $ros-ros2-debug-engineer.\n",
                encoding="utf-8",
            )
            (root / "run.log").write_text("temporary output", encoding="utf-8")
            out = Path(tmp) / "dist"
            result = self.run_script("package_skill.py", str(root), str(out))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with zipfile.ZipFile(out / "skill.zip") as archive:
                self.assertNotIn("run.log", archive.namelist())

            (Path(tmp) / "outside.md").write_text("outside", encoding="utf-8")
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: A sufficiently detailed demo skill description for validation.\n---\n[bad](../outside.md)\n",
                encoding="utf-8",
            )
            result = self.run_script("package_skill.py", str(root), str(out))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes skill root", result.stdout + result.stderr)

    def test_behavior_evaluation_cases_cover_simple_and_complex_work(self) -> None:
        data = yaml.safe_load((ROOT / "tests" / "evaluation_cases.yaml").read_text(encoding="utf-8"))
        cases = data["cases"]
        self.assertGreaterEqual(len(cases), 6)
        ids = {case["id"] for case in cases}
        self.assertEqual(len(ids), len(cases))
        for case in cases:
            self.assertIn(case["expected_mode"], {"debug", "architect", "audit"})
            self.assertGreaterEqual(case["max_references"], 0)
            self.assertGreaterEqual(case["max_hypotheses"], 0)
            self.assertTrue(case["required"])
        micro = [case for case in cases if case["expected_scale"] == "micro"]
        self.assertTrue(micro)
        self.assertTrue(all(case["max_references"] == 0 for case in micro))
        self.assertTrue(all("GOAL" in case["forbidden"] or "audit mode" in case["forbidden"] for case in micro))


if __name__ == "__main__":
    unittest.main()
