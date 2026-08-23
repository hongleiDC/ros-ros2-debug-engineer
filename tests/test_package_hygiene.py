from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "package_skill.py"


def load_module():
    spec = importlib.util.spec_from_file_location("package_skill", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageHygieneTest(unittest.TestCase):
    def test_bundle_keeps_skill_resources_and_excludes_repo_runtime_state(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep = (
                "SKILL.md",
                "agents/openai.yaml",
                "scripts/tool.py",
                "references/note.md",
                "assets/icon.svg",
            )
            drop = (
                ".gitignore",
                "README.md",
                "LICENSE",
                ".github/workflows/validate.yml",
                "tests/test_example.py",
                ".ros_noetic_cache/manifest.yaml",
                ".ros_noetic_profiles/v0001/robot_profile.yaml",
                "reports/EXP-0001/result.txt",
                "logs/run.log.txt",
                "dist/old.zip",
            )
            for relative in keep + drop:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")

            bundled = {relative.as_posix() for _, relative in module.files(root)}
            self.assertTrue(set(keep).issubset(bundled))
            self.assertTrue(set(drop).isdisjoint(bundled))


if __name__ == "__main__":
    unittest.main()
