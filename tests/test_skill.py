from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class DocumentationContractTest(unittest.TestCase):
    def test_formula_variable_traceability_is_wired_into_skill(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        coding = (ROOT / "references" / "coding_rules.md").read_text(encoding="utf-8")
        experiment = (ROOT / "references" / "experiment_management.md").read_text(encoding="utf-8")
        trace = ROOT / "references" / "formula_variable_traceability.md"
        self.assertTrue(trace.is_file())
        self.assertIn("formula_variable_traceability.md", skill)
        self.assertIn("公式符号到代码变量", coding)
        self.assertIn("公式版本", experiment)
        text = trace.read_text(encoding="utf-8")
        for required in ["已知条件", "变量映射", "单位", "frame", "逐行变换", "魔法数"]:
            self.assertIn(required, text)
        reasoning_kb = ROOT / "references" / "reasoning_knowledge_base.md"
        self.assertTrue(reasoning_kb.is_file())
        self.assertIn("reasoning_knowledge_base.md", skill)
        self.assertTrue((ROOT / "scripts" / "logic_audit.py").is_file())
        self.assertTrue((ROOT / "scripts" / "register_reasoning_knowledge.py").is_file())
        kb_text = reasoning_kb.read_text(encoding="utf-8")
        for required in ["FORM-*", "MAP-*", "REAS-*", "AUD-*", "strict-warnings"]:
            self.assertIn(required, kb_text)


class SkillTest(unittest.TestCase):
    def run_script(self, name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        current_env = os.environ.copy()
        if env:
            current_env.update(env)
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
            env=current_env,
        )

    def init_project(self, tmp: str) -> tuple[Path, Path]:
        repo = Path(tmp) / "project"
        result = self.run_script("init_project_knowledge.py", str(repo), "--project-id", "example_project")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return repo, repo / "project_knowledge"

    def test_initialize_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            result = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            marker = yaml.safe_load((repo / ".ros_debug_project.yaml").read_text(encoding="utf-8"))
            self.assertEqual(marker["knowledge_dir"], "project_knowledge")
            self.assertTrue((knowledge / "project_model.yaml").is_file())
            self.assertTrue((knowledge / "goals").is_dir())
            self.assertTrue((knowledge / "experiments").is_dir())
            self.assertTrue((knowledge / "formulas").is_dir())
            self.assertTrue((knowledge / "variable_mappings").is_dir())
            self.assertTrue((knowledge / "reasoning_chains").is_dir())
            self.assertTrue((knowledge / "audits").is_dir())

    def test_workspace_inspection_builds_l1_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            package = root / "src" / "demo_pkg"
            (package / "src").mkdir(parents=True)
            (package / "launch").mkdir()
            (package / "msg").mkdir()
            (root / ".github" / "workflows").mkdir(parents=True)
            (package / "package.xml").write_text("""<package format="3">
<name>demo_pkg</name><version>0.1.0</version><description>x</description>
<maintainer email="a@b.com">a</maintainer><license>MIT</license>
<buildtool_depend>ament_cmake</buildtool_depend><depend>rclcpp</depend>
<export><build_type>ament_cmake</build_type></export></package>""", encoding="utf-8")
            (package / "CMakeLists.txt").write_text(
                "add_executable(demo_node src/node.cpp)\nrclcpp_components_register_nodes(demo_component \"demo::Node\")\n",
                encoding="utf-8",
            )
            (package / "src" / "node.cpp").write_text(
                "rclcpp_lifecycle::LifecycleNode n; auto g=create_callback_group(); // sensor_msgs::msg::Imu tf2",
                encoding="utf-8",
            )
            (package / "launch" / "demo.launch.py").write_text("# launch", encoding="utf-8")
            (package / "msg" / "Status.msg").write_text("bool ok", encoding="utf-8")
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
            result = self.run_script("inspect_workspace.py", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data["coverage"]["understanding_level"], "L1")
            self.assertEqual(data["packages"][0]["name"], "demo_pkg")
            self.assertIn("demo_node", data["packages"][0]["executables"])
            self.assertTrue(data["capabilities"]["lifecycle"])
            self.assertTrue(data["capabilities"]["callback_groups"])
            self.assertTrue(data["artifacts"]["interfaces"])
            self.assertIn(".github/workflows/ci.yml", data["artifacts"]["ci"])
            self.assertFalse(data["capabilities"]["imu"])

    def test_runtime_command_capture_is_memory_bounded(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("runtime_snapshot", SCRIPTS / "collect_runtime_snapshot.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.execute(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 150000); sys.stderr.write('y' * 120000)"],
            5.0,
        )
        self.assertEqual(result["returncode"], 0)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["stdout"]), module.MAX_OUTPUT)
        self.assertEqual(len(result["stderr"]), module.MAX_OUTPUT)

    def test_runtime_snapshot_gracefully_handles_missing_ros(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PATH": tmp, "ROS_VERSION": ""}
            result = self.run_script("collect_runtime_snapshot.py", "--ros-version", "auto", env=env)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertEqual(data["ros_version"], "unknown")
            self.assertEqual(data["coverage"]["successful_commands"], 0)
            self.assertFalse(data["coverage"]["runtime_observed"])
            self.assertEqual(data["coverage"]["understanding_level"], "L1")

    def test_preflight_has_dependency_free_none_profile(self) -> None:
        result = self.run_script("preflight.py", "--require", "none", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(result.stdout)
        self.assertTrue(data["ok"])
        self.assertIn("jsonschema", data["modules"])

    def test_static_capabilities_do_not_promote_dependency_only_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ws"
            package = root / "src" / "demo_pkg"
            (package / "src").mkdir(parents=True)
            (package / "launch").mkdir()
            (package / "package.xml").write_text(
                "<package><name>demo_pkg</name><version>0.1.0</version>"
                "<depend>rclcpp_lifecycle</depend></package>",
                encoding="utf-8",
            )
            (package / "src" / "node.cpp").write_text("// simulation helper\nint main() {}\n", encoding="utf-8")
            (package / "launch" / "demo.launch.py").write_text("# launch only\n", encoding="utf-8")
            result = self.run_script("inspect_workspace.py", str(root))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads(result.stdout)
            self.assertFalse(data["capabilities"]["lifecycle"])
            self.assertEqual(data["capability_evidence"]["lifecycle"]["status"], "candidate")
            self.assertFalse(data["capabilities"]["imu"])
            self.assertEqual(data["packages"][0]["languages"], ["c++"])
            self.assertEqual(data["status"], "observed")

    def test_update_records_old_new_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.use_sim_time", "true", "--status", "measured",
                "--reason", "test", "--evidence", "unit test",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = yaml.safe_load((knowledge / "active_configuration.yaml").read_text(encoding="utf-8"))
            self.assertTrue(data["configuration"]["use_sim_time"])
            changelog = (knowledge / "CHANGELOG.md").read_text(encoding="utf-8")
            self.assertIn("old value", changelog)
            self.assertFalse((knowledge / ".knowledge-transaction.json").exists())

    def test_verified_record_is_protected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            path = knowledge / "active_configuration.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["status"] = "verified"
            path.write_text(yaml.safe_dump(data), encoding="utf-8")
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.value", "1", "--status", "verified",
                "--reason", "test", "--evidence", "unit test",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("verified", result.stderr + result.stdout)

    def test_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            target = knowledge / "topics.yaml"
            original = target.read_text(encoding="utf-8")
            target.write_text("broken: true\n", encoding="utf-8")
            changelog = knowledge / "CHANGELOG.md"
            old_log = changelog.read_text(encoding="utf-8")
            journal = {
                "target_relative": "topics.yaml",
                "target_existed": True,
                "target_old": base64.b64encode(original.encode()).decode(),
                "changelog_existed": True,
                "changelog_old": base64.b64encode(old_log.encode()).decode(),
            }
            (knowledge / ".knowledge-transaction.json").write_text(json.dumps(journal), encoding="utf-8")
            result = self.run_script(
                "update_knowledge.py", str(knowledge), "active_configuration.yaml",
                "configuration.test", "true", "--status", "candidate",
                "--reason", "recover", "--evidence", "journal", "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), original)
            self.assertFalse((knowledge / ".knowledge-transaction.json").exists())

    def test_incident_id_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            bad = self.run_script("new_incident.py", str(knowledge), "../../bad", "escape")
            self.assertNotEqual(bad.returncode, 0)
            good = self.run_script("new_incident.py", str(knowledge), "INC-0001", "timestamp mismatch")
            self.assertEqual(good.returncode, 0, good.stderr + good.stdout)
            incident = next((knowledge / "incidents").glob("*.yaml"))
            data = yaml.safe_load(incident.read_text(encoding="utf-8"))
            self.assertEqual(data["incident_id"], "INC-0001")
            validate = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def test_invalid_schema_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, knowledge = self.init_project(tmp)
            (knowledge / "devices" / "bad.yaml").write_text(
                yaml.safe_dump({"schema_version": 1, "device_id": "bad", "status": "verified"}),
                encoding="utf-8",
            )
            result = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manufacturer", result.stdout)


    def start_goal(self, repo: Path, knowledge: Path, goal_id: str = "GOAL-0001") -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "goal_guard.py", "start", str(knowledge), goal_id, "Fix timestamp root cause",
            "--workspace", str(repo),
            "--request", "Fix timestamp rollback",
            "--desired-outcome", "No rollback without accuracy regression",
            "--primary-goal", "Eliminate the timestamp rollback root cause without reducing localization accuracy",
            "--success", "No timestamp rollback::runtime logs and counters",
            "--milestone", "Establish a reproducible baseline",
            "--milestone", "Implement and verify the minimal fix",
        )

    def test_goal_guard_anchors_actions_and_blocks_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "README.txt").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, capture_output=True)
            started = self.start_goal(repo, knowledge)
            self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
            guarded = self.run_script(
                "goal_guard.py", "guard", str(knowledge),
                "--criterion", "SC-1", "--milestone", "M-1",
                "--action", "Inspect timestamp conversion",
                "--alignment", "The conversion directly determines whether rollback is created",
                "--expected-evidence", "Code path and focused test output",
            )
            self.assertEqual(guarded.returncode, 0, guarded.stderr + guarded.stdout)
            self.assertIn("primary_goal", guarded.stdout)
            drifted = self.run_script(
                "goal_guard.py", "checkpoint", str(knowledge),
                "--trigger", "failure", "--criterion", "SC-1", "--milestone", "M-1",
                "--summary", "Two attempts failed and the current hypothesis is exhausted",
                "--decision", "Stop before changing the user goal",
                "--next-action", "Ask for direction or revise with authorization",
                "--drift-status", "drifted",
                "--drift-reason", "The proposed workaround no longer tests the root-cause criterion",
            )
            self.assertEqual(drifted.returncode, 0, drifted.stderr + drifted.stdout)
            blocked = self.run_script(
                "goal_guard.py", "guard", str(knowledge),
                "--criterion", "SC-1", "--milestone", "M-1",
                "--action", "Disable timestamp validation",
                "--alignment", "This would only suppress the symptom rather than meet the criterion",
                "--expected-evidence", "No valid root-cause evidence",
            )
            self.assertNotEqual(blocked.returncode, 0)
            self.assertIn("drifted", blocked.stderr + blocked.stdout)

    def test_goal_revision_requires_user_authorization_and_completion_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge = self.init_project(tmp)
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "README.txt").write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, capture_output=True)
            self.assertEqual(self.start_goal(repo, knowledge).returncode, 0)
            no_auth = self.run_script(
                "goal_guard.py", "revise", str(knowledge),
                "--primary-goal", "Only document the failure without fixing it",
                "--reason", "The task scope may need to change after new evidence",
                "--authorization-evidence", "User requested a changed outcome",
            )
            self.assertNotEqual(no_auth.returncode, 0)
            incomplete = self.run_script(
                "goal_guard.py", "finish", str(knowledge),
                "--outcome", "completed", "--summary", "Code was changed",
            )
            self.assertNotEqual(incomplete.returncode, 0)
            met = self.run_script(
                "goal_guard.py", "criterion", str(knowledge), "SC-1",
                "--status", "met", "--evidence", "30-minute log has zero rollback events",
            )
            self.assertEqual(met.returncode, 0, met.stderr + met.stdout)
            finished = self.run_script(
                "goal_guard.py", "finish", str(knowledge),
                "--outcome", "completed", "--summary", "All success criteria have direct evidence",
            )
            self.assertEqual(finished.returncode, 0, finished.stderr + finished.stdout)

    def prepare_git_experiment_project(self, tmp: str) -> tuple[Path, Path, str]:
        repo, knowledge = self.init_project(tmp)
        (repo / "package.xml").write_text("<package><name>demo</name></package>\n", encoding="utf-8")
        (repo / "config.yaml").write_text("offset_ms: 0\n", encoding="utf-8")
        (repo / "sample.mcap").write_bytes(b"bag-data")
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, text=True, capture_output=True,
        ).stdout.strip()
        goal = self.start_goal(repo, knowledge)
        self.assertEqual(goal.returncode, 0, goal.stderr + goal.stdout)
        return repo, knowledge, commit

    def create_experiment(self, knowledge: Path, repo: Path, experiment_id: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "experiment_registry.py", "create", str(knowledge), experiment_id, "IMU offset test",
            "--workspace", str(repo),
            "--objective", "Determine whether the offset reduces error",
            "--hypothesis", "A positive offset lowers ATE",
            "--alignment", "This experiment directly tests the active timestamp rollback criterion",
            "--mainline-branch", "main",
            "--input", "BAG-0001",
            "--input-file", "sample.mcap",
            "--parameter-file", "config.yaml",
            "--change", "imu_time_offset_ms: 0 -> 3",
            "--command", "ros2 launch demo replay.launch.py",
            "--expected", "ATE decreases without timestamp rollback",
            "--metric", "ate_rmse_m:lower:m",
            *extra,
        )

    def test_experiment_registry_captures_context_and_blocks_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, commit = self.prepare_git_experiment_project(tmp)
            first = self.create_experiment(knowledge, repo, "EXP-0001")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            first_path = (knowledge / "experiments" / "EXP-0001.yaml")
            data = yaml.safe_load(first_path.read_text(encoding="utf-8"))
            self.assertEqual(data["scope"]["mainline"]["branch"], "main")
            self.assertEqual(data["scope"]["mainline"]["commit"], commit)
            self.assertEqual(data["scope"]["experiment"]["commit"], commit)
            self.assertFalse(data["scope"]["experiment"]["dirty"])
            self.assertTrue(any(item["path"] == "package.xml" for item in data["dependencies"]["manifests"]))
            self.assertEqual(len(data["fingerprint"]["value"]), 64)

            duplicate = self.create_experiment(knowledge, repo, "EXP-0002")
            self.assertNotEqual(duplicate.returncode, 0, duplicate.stderr + duplicate.stdout)
            self.assertIn("EXP-0001", duplicate.stdout + duplicate.stderr)
            self.assertFalse((knowledge / "experiments" / "EXP-0002.yaml").exists())

    def test_experiment_duplicate_override_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, _ = self.prepare_git_experiment_project(tmp)
            first = self.create_experiment(knowledge, repo, "EXP-0001")
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            bad = self.create_experiment(knowledge, repo, "EXP-0002", "--allow-duplicate")
            self.assertNotEqual(bad.returncode, 0)
            good = self.create_experiment(
                knowledge, repo, "EXP-0002", "--allow-duplicate",
                "--duplicate-reason", "Independent repeat for jitter statistics",
            )
            self.assertEqual(good.returncode, 0, good.stderr + good.stdout)
            path = (knowledge / "experiments" / "EXP-0002.yaml")
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["duplicate_check"]["exact_match_ids"], ["EXP-0001"])
            self.assertIn("Independent repeat", data["duplicate_check"]["override_reason"])

    def test_experiment_finish_records_results_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, _ = self.prepare_git_experiment_project(tmp)
            created = self.create_experiment(knowledge, repo, "EXP-0001")
            self.assertEqual(created.returncode, 0, created.stderr + created.stdout)
            results = repo / "results"
            results.mkdir()
            (results / "trajectory.csv").write_text("t,x,y\n0,0,0\n", encoding="utf-8")
            (results / "run.log").write_text("completed\n", encoding="utf-8")
            started = self.run_script(
                "experiment_registry.py", "start", str(knowledge), "EXP-0001",
            )
            self.assertEqual(started.returncode, 0, started.stderr + started.stdout)
            finished = self.run_script(
                "experiment_registry.py", "finish", str(knowledge), "EXP-0001",
                "--status", "completed", "--outcome", "pass",
                "--summary", "ATE decreased from 0.42 m to 0.31 m",
                "--metric", "ate_rmse_m=0.31:m:baseline 0.42 m",
                "--observation", "No timestamp rollback",
                "--artifact", "results/trajectory.csv:trajectory output",
                "--log", "results/run.log:runtime log",
                "--verdict", "supported", "--confidence", "high",
                "--lesson", "Positive offset is supported",
                "--next-action", "Promote to regression test",
            )
            self.assertEqual(finished.returncode, 0, finished.stderr + finished.stdout)
            path = (knowledge / "experiments" / "EXP-0001.yaml")
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "completed")
            self.assertIsNotNone(data["results"]["run_started_at"])
            self.assertEqual(data["results"]["outcome"], "pass")
            self.assertEqual(data["results"]["metrics"][0]["value"], 0.31)
            self.assertEqual(len(data["results"]["artifacts"][0]["sha256"]), 64)
            self.assertEqual(data["conclusion"]["verdict"], "supported")
            validate = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def test_package_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_script("package_skill.py", str(ROOT), tmp)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            archive_path = Path(tmp) / "skill.zip"
            self.assertTrue(archive_path.is_file())
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
            self.assertNotIn("README.md", names)
            self.assertNotIn("CONTRIBUTING.md", names)
            self.assertNotIn("SECURITY.md", names)
            self.assertFalse(any(name.startswith("tests/") for name in names))
            self.assertFalse(any(name.startswith(".github/") for name in names))
            self.assertIn("scripts/preflight.py", names)


class ReasoningKnowledgeTest(unittest.TestCase):
    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / name), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def write_yaml(self, path: Path, data: dict) -> None:
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def prepare(self, tmp: str) -> tuple[Path, Path, str]:
        repo = Path(tmp) / "project"
        init = self.run_script("init_project_knowledge.py", str(repo), "--project-id", "reasoning_project")
        self.assertEqual(init.returncode, 0, init.stderr + init.stdout)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        code = (
            "double correct_time(double sensor_time_s, double imu_time_offset_s) {\n"
            "  const double corrected_time_s = sensor_time_s + imu_time_offset_s;\n"
            "  return corrected_time_s;\n"
            "}\n"
        )
        (repo / "src" / "time_sync.cpp").write_text(code, encoding="utf-8")
        (repo / "tests" / "test_time_sync.cpp").write_text("// hand-check and unit test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "baseline"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, text=True, capture_output=True,
        ).stdout.strip()
        goal = self.run_script(
            "goal_guard.py", "start", str(repo / "project_knowledge"), "GOAL-0001", "Verify timestamp correction",
            "--workspace", str(repo),
            "--request", "Check timestamp correction logic",
            "--desired-outcome", "Formula and implementation agree with no rollback",
            "--primary-goal", "Verify timestamp correction formula and implementation",
            "--success", "Formula and code correspondence is verified::logic audit and unit test",
            "--milestone", "Audit formula and implementation",
        )
        self.assertEqual(goal.returncode, 0, goal.stderr + goal.stdout)
        return repo, repo / "project_knowledge", commit

    def records(self, repo: Path, commit: str) -> tuple[dict, dict, dict]:
        formula = {
            "schema_version": 1,
            "formula_id": "FORM-0001",
            "name": "Sensor timestamp correction",
            "version": "1.0.0",
            "status": "verified",
            "domain": "time synchronization",
            "purpose": "Convert sensor time to corrected host-aligned time",
            "expression_latex": "t_{corrected}=t_{sensor}+\\Delta t",
            "goal_alignment": {"goal_id": "GOAL-0001", "criterion_ids": ["SC-1"]},
            "assumptions": [{
                "assumption_id": "ASM-1",
                "statement": "The offset sign is sensor to host positive",
                "status": "verified",
                "evidence": ["tests/test_time_sync.cpp"],
            }],
            "conventions": {
                "frame_convention": "not_applicable",
                "transform_direction": "sensor_time_to_host_time",
                "multiplication_order": "not_applicable",
                "time_basis": "seconds from the same epoch",
                "index_order": "scalar",
            },
            "symbols": [
                {"symbol_id": "SYM-1", "latex": "t_{sensor}", "meaning": "sensor timestamp", "role": "input", "dimension": "time", "canonical_unit": "s", "frame": "not_applicable", "direction": "sensor_time", "time_basis": "sensor epoch", "shape": "scalar", "valid_range": "finite and nonnegative", "required_in_code": True},
                {"symbol_id": "SYM-2", "latex": "\\Delta t", "meaning": "sensor to host time offset", "role": "parameter", "dimension": "time", "canonical_unit": "s", "frame": "not_applicable", "direction": "sensor_to_host", "time_basis": "offset", "shape": "scalar", "valid_range": "project evidence", "required_in_code": True},
                {"symbol_id": "SYM-3", "latex": "t_{corrected}", "meaning": "corrected timestamp", "role": "output", "dimension": "time", "canonical_unit": "s", "frame": "not_applicable", "direction": "host_time", "time_basis": "host epoch", "shape": "scalar", "valid_range": "finite and nonnegative", "required_in_code": True},
            ],
            "derivation": [{
                "step_id": "DER-1",
                "equation_latex": "t_{corrected}=t_{sensor}+\\Delta t",
                "operation": "Apply the verified additive clock-offset definition",
                "justification": "Definition of a constant signed time offset",
                "input_symbol_ids": ["SYM-1", "SYM-2"],
                "output_symbol_ids": ["SYM-3"],
                "assumption_refs": ["ASM-1"],
            }],
            "code_requirements": {
                "mapping_required": True,
                "invariants": ["all timestamp values use seconds", "offset sign remains sensor_to_host"],
                "forbidden_aliases": ["tmp", "val", "data2"],
            },
            "tests": ["tests/test_time_sync.cpp"],
            "provenance": {"source": "project model and unit test", "repository_commit": commit, "evidence": ["src/time_sync.cpp", "tests/test_time_sync.cpp"]},
        }
        mapping = {
            "schema_version": 1,
            "mapping_id": "MAP-0001",
            "status": "verified",
            "formula_id": "FORM-0001",
            "formula_version": "1.0.0",
            "goal_alignment": {"goal_id": "GOAL-0001", "criterion_ids": ["SC-1"]},
            "implementation": {"repository": str(repo), "commit": commit, "package": "demo", "file": "src/time_sync.cpp", "symbol_scope": "correct_time", "language": "cpp"},
            "entries": [
                {"entry_id": "VM-1", "symbol_id": "SYM-1", "code_identifier": "sensor_time_s", "identifier_kind": "function_argument", "source": {"file": "src/time_sync.cpp", "line_start": 1, "line_end": 2}, "physical_meaning": "sensor timestamp", "formula_unit": "s", "code_unit": "s", "conversion": {"required": False, "expression": "", "direction": "identity", "test_refs": []}, "frame": "not_applicable", "direction": "sensor_time", "time_basis": "sensor epoch", "shape": "scalar", "index_order": "scalar", "data_type": "double", "aliases": [], "evidence": ["src/time_sync.cpp:1"], "status": "verified"},
                {"entry_id": "VM-2", "symbol_id": "SYM-2", "code_identifier": "imu_time_offset_s", "identifier_kind": "function_argument", "source": {"file": "src/time_sync.cpp", "line_start": 1, "line_end": 2}, "physical_meaning": "sensor to host time offset", "formula_unit": "s", "code_unit": "s", "conversion": {"required": False, "expression": "", "direction": "identity", "test_refs": []}, "frame": "not_applicable", "direction": "sensor_to_host", "time_basis": "offset", "shape": "scalar", "index_order": "scalar", "data_type": "double", "aliases": [], "evidence": ["src/time_sync.cpp:1"], "status": "verified"},
                {"entry_id": "VM-3", "symbol_id": "SYM-3", "code_identifier": "corrected_time_s", "identifier_kind": "local", "source": {"file": "src/time_sync.cpp", "line_start": 2, "line_end": 3}, "physical_meaning": "corrected timestamp", "formula_unit": "s", "code_unit": "s", "conversion": {"required": False, "expression": "", "direction": "identity", "test_refs": []}, "frame": "not_applicable", "direction": "host_time", "time_basis": "host epoch", "shape": "scalar", "index_order": "scalar", "data_type": "double", "aliases": [], "evidence": ["src/time_sync.cpp:2"], "status": "verified"},
            ],
            "invariants": ["formula and code both use seconds", "offset sign is sensor_to_host"],
            "verification": {"test_refs": ["tests/test_time_sync.cpp"], "hand_calculation_refs": ["REAS-0001/STEP-2"], "last_audited_commit": commit},
        }
        reasoning = {
            "schema_version": 1,
            "reasoning_id": "REAS-0001",
            "title": "Verify timestamp correction implementation",
            "status": "verified",
            "created_at": "2026-07-19T00:00:00Z",
            "updated_at": "2026-07-19T00:00:00Z",
            "goal_alignment": {"goal_id": "GOAL-0001", "criterion_ids": ["SC-1"], "milestone_id": "M-1"},
            "scope": {"repository": str(repo), "commit": commit, "packages": ["demo"], "files": ["src/time_sync.cpp"]},
            "question": "Does the implementation match the signed timestamp correction formula?",
            "claim": "The implementation computes corrected time using the verified sensor-to-host offset convention.",
            "known_conditions": [
                {"condition_id": "COND-1", "statement": "All three code variables store seconds", "source": "MAP-0001", "status": "verified"},
                {"condition_id": "COND-2", "statement": "For sensor_time_s=10 and offset=0.2, expected corrected time is 10.2", "source": "hand calculation", "status": "verified"},
            ],
            "assumptions": [{"assumption_id": "ASM-1", "statement": "Positive offset maps sensor time toward host time", "justification": "FORM-0001 assumption and unit test", "status": "verified"}],
            "formula_refs": [{"formula_id": "FORM-0001", "version": "1.0.0"}],
            "mapping_ids": ["MAP-0001"],
            "steps": [
                {"step_id": "STEP-1", "premise_refs": ["COND-1", "ASM-1"], "rule_type": "definition", "rule_or_definition": "FORM-0001/DER-1", "operation": "Map each formula symbol to the corresponding code identifier", "expression_before": "t_corrected=t_sensor+Delta_t", "expression_after": "corrected_time_s=sensor_time_s+imu_time_offset_s", "symbol_ids": ["SYM-1", "SYM-2", "SYM-3"], "code_identifiers": ["sensor_time_s", "imu_time_offset_s", "corrected_time_s"], "evidence_refs": ["MAP-0001", "src/time_sync.cpp:1-3"], "output": "The code expression is structurally identical to the formula", "verification_status": "verified", "counterexample_check": "A subtraction implementation would violate the sensor_to_host sign convention and fail the hand calculation"},
                {"step_id": "STEP-2", "premise_refs": ["STEP-1", "COND-2"], "rule_type": "algebra", "rule_or_definition": "Direct numeric substitution", "operation": "Substitute 10 s and 0.2 s", "expression_before": "t_corrected=10 s+0.2 s", "expression_after": "t_corrected=10.2 s", "symbol_ids": ["SYM-1", "SYM-2", "SYM-3"], "code_identifiers": ["sensor_time_s", "imu_time_offset_s", "corrected_time_s"], "evidence_refs": ["tests/test_time_sync.cpp"], "output": "The implementation has the expected value and unit", "verification_status": "verified", "counterexample_check": "Zero offset returns the original sensor timestamp; negative offset decreases corrected time by its signed magnitude"},
            ],
            "conclusion": {"statement": "The implementation matches FORM-0001 version 1.0.0 and MAP-0001", "status": "verified", "supported_criterion_ids": ["SC-1"], "evidence_refs": ["MAP-0001", "tests/test_time_sync.cpp"], "limitations": ["This verifies formula correspondence, not clock-offset estimation accuracy"]},
            "unresolved": [],
        }
        return formula, mapping, reasoning

    def register(self, knowledge: Path, source: Path) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "register_reasoning_knowledge.py", str(knowledge), str(source),
            "--reason", "unit test reasoning knowledge registration",
        )

    def test_logic_audit_rejects_empty_formula_knowledge_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, _ = self.prepare(tmp)
            audited = self.run_script(
                "logic_audit.py", str(knowledge), "--workspace", str(repo), "--audit-id", "AUD-0009",
            )
            self.assertNotEqual(audited.returncode, 0)
            self.assertIn("no_formula_records", audited.stdout)
            allowed = self.run_script(
                "logic_audit.py", str(knowledge), "--workspace", str(repo),
                "--audit-id", "AUD-0010", "--allow-empty",
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr + allowed.stdout)

    def test_reasoning_formula_mapping_audit_passes_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, commit = self.prepare(tmp)
            formula, mapping, reasoning = self.records(repo, commit)
            for name, record in (("formula.yaml", formula), ("mapping.yaml", mapping), ("reasoning.yaml", reasoning)):
                source = Path(tmp) / name
                self.write_yaml(source, record)
                registered = self.register(knowledge, source)
                self.assertEqual(registered.returncode, 0, registered.stderr + registered.stdout)
            audited = self.run_script(
                "logic_audit.py", str(knowledge), "--workspace", str(repo),
                "--audit-id", "AUD-0001", "--write-report", "--strict-warnings",
            )
            self.assertEqual(audited.returncode, 0, audited.stderr + audited.stdout)
            report = yaml.safe_load((knowledge / "audits" / "AUD-0001.yaml").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["status"], "pass")
            validate = self.run_script("validate_knowledge.py", str(knowledge))
            self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)

    def test_logic_audit_rejects_formula_variable_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, knowledge, commit = self.prepare(tmp)
            formula, mapping, reasoning = self.records(repo, commit)
            mapping["status"] = "candidate"
            mapping["entries"][1]["status"] = "candidate"
            mapping["entries"][1]["code_identifier"] = "tmp"
            mapping["entries"][1]["code_unit"] = "ms"
            mapping["entries"][1]["conversion"] = {"required": False, "expression": "", "direction": "", "test_refs": []}
            reasoning["status"] = "candidate"
            reasoning["conclusion"]["status"] = "candidate"
            for name, record in (("formula.yaml", formula), ("mapping.yaml", mapping), ("reasoning.yaml", reasoning)):
                source = Path(tmp) / name
                self.write_yaml(source, record)
                registered = self.register(knowledge, source)
                self.assertEqual(registered.returncode, 0, registered.stderr + registered.stdout)
            audited = self.run_script(
                "logic_audit.py", str(knowledge), "--workspace", str(repo), "--audit-id", "AUD-0002",
            )
            self.assertNotEqual(audited.returncode, 0)
            self.assertIn("opaque_identifier", audited.stdout)
            self.assertIn("missing_unit_conversion", audited.stdout)



if __name__ == "__main__":
    unittest.main()
