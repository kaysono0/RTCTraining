import json
import subprocess
import sys
from pathlib import Path

from automation.runner.diff_validator import apply_unified_patch, validate_patch
from automation.runner.task_baseline import build_task_baseline
from automation.runner.model_gateway import CommandModelGateway
from automation.runner.orchestrator import run_continuous, run_once
from automation.runner.task_cli import approve_task, create_task
from automation.runner.worktree_manager import WorktreeManager


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def initialize_git_repo(root: Path) -> None:
    run_git(root, "init")
    run_git(root, "config", "user.email", "rtc-training@example.test")
    run_git(root, "config", "user.name", "RTCTraining Test")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "initial")


def base_policy(root: Path) -> None:
    write_json(
        root / "automation/config/policy.json",
        {
            "allowed_command_prefixes": [[sys.executable, "-c"]],
            "global_forbidden_paths": [
                "data/**",
                "certs/**",
                ".env",
                ".venv/**",
                "automation/artifacts/**",
            ],
            "risk_levels": {
                "low": {
                    "allow_patch": True,
                    "allow_checks": True,
                    "allow_repair": True,
                    "requires_approval": False,
                },
                "medium": {
                    "allow_patch": False,
                    "allow_checks": False,
                    "allow_repair": False,
                    "requires_approval": True,
                },
            },
            "max_patch_bytes": 20000,
            "max_changed_files": 4,
            "default_max_repair_attempts": 1,
            "command_timeout_seconds": 20,
        },
    )


def base_runtime(root: Path, **overrides: object) -> None:
    payload = {
        "model_backend": "stub",
        "model_command": "",
    }
    payload.update(overrides)
    write_json(root / "automation/config/runtime.json", payload)


def task_contract(root: Path, task_id: str, **overrides: object) -> dict:
    contract = {
        "id": task_id,
        "title": "Update sample file",
        "goal": "Change the sample file content.",
        "context_files": ["sample.txt"],
        "allowed_paths": ["sample.txt"],
        "forbidden_paths": ["data/**", "certs/**", ".env"],
        "acceptance": ["sample.txt contains updated content."],
        "required_checks": [
            f"{sys.executable} -c \"from pathlib import Path; assert Path('sample.txt').read_text() == 'updated\\n'\""
        ],
        "risk_level": "low",
        "mode": "patch-only",
        "max_repair_attempts": 1,
        "stub_patch": (
            "--- a/sample.txt\n"
            "+++ b/sample.txt\n"
            "@@ -1 +1 @@\n"
            "-initial\n"
            "+updated\n"
        ),
    }
    contract.update(overrides)
    contract["baseline"] = build_task_baseline(root, list(contract["context_files"]), list(contract["allowed_paths"]))
    return contract


def test_low_risk_task_runs_to_done_and_records_artifacts(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/update-sample.json",
        task_contract(tmp_path, "update-sample"),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "updated\n"
    assert not (tmp_path / "automation/tasks/ready/update-sample.json").exists()
    assert (tmp_path / "automation/tasks/done/update-sample.json").exists()
    assert (tmp_path / "automation/artifacts/plans/update-sample.json").exists()
    assert (tmp_path / "automation/artifacts/patches/update-sample.patch").exists()

    report = read_json(tmp_path / "automation/artifacts/reports/update-sample.json")
    assert report["status"] == "done"
    assert report["changed_files"] == ["sample.txt"]
    assert report["checks"][0]["status"] == "passed"


def test_markdown_report_includes_baseline_summary_context_files_and_required_checks(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    (tmp_path / "second.txt").write_text("old\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/report-markdown.json",
        task_contract(
            tmp_path,
            "report-markdown",
            context_files=["sample.txt", "second.txt"],
            allowed_paths=["sample.txt", "second.txt"],
            required_checks=[
                f"{sys.executable} -c \"from pathlib import Path; assert Path('sample.txt').read_text() == 'updated\\n'\"",
                f"{sys.executable} -c \"from pathlib import Path; assert Path('second.txt').read_text() == 'done\\n'\"",
            ],
            stub_patch=(
                "--- a/sample.txt\n"
                "+++ b/sample.txt\n"
                "@@ -1 +1 @@\n"
                "-initial\n"
                "+updated\n"
                "--- a/second.txt\n"
                "+++ b/second.txt\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+done\n"
            ),
        ),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    markdown = (tmp_path / "automation/artifacts/reports/report-markdown.md").read_text(encoding="utf-8")
    assert "## Baseline Summary" in markdown
    assert "- Context file count: 2" in markdown
    assert "## Context Files" in markdown
    assert "- `sample.txt`" in markdown
    assert "- `second.txt`" in markdown
    assert "## Required Checks" in markdown
    assert f"- `{sys.executable} -c \"from pathlib import Path; assert Path('sample.txt').read_text() == 'updated\\n'\"`" in markdown
    assert f"- `{sys.executable} -c \"from pathlib import Path; assert Path('second.txt').read_text() == 'done\\n'\"`" in markdown


def test_medium_risk_task_blocks_for_user_approval(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/medium-task.json",
        task_contract(tmp_path, "medium-task", risk_level="medium"),
    )

    result = run_once(tmp_path)

    assert result.status == "blocked"
    assert "approval" in result.reason
    assert (tmp_path / "automation/tasks/blocked/medium-task.json").exists()

    approval = read_json(tmp_path / "automation/artifacts/approvals/medium-task.json")
    assert approval["task_id"] == "medium-task"
    assert approval["reason"] == "risk level requires approval"


def test_patch_outside_allowed_paths_is_rejected(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    (tmp_path / "other.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/bad-patch.json",
        task_contract(
            tmp_path,
            "bad-patch",
            stub_patch=(
                "--- a/other.txt\n"
                "+++ b/other.txt\n"
                "@@ -1 +1 @@\n"
                "-initial\n"
                "+updated\n"
            ),
        ),
    )

    result = run_once(tmp_path)

    assert result.status == "failed"
    assert "outside allowed paths" in result.reason
    assert (tmp_path / "other.txt").read_text(encoding="utf-8") == "initial\n"
    assert (tmp_path / "automation/tasks/failed/bad-patch.json").exists()
    report = read_json(tmp_path / "automation/artifacts/reports/bad-patch.json")
    assert report["failure_stage"] == "patch_validation"
    markdown = (tmp_path / "automation/artifacts/reports/bad-patch.md").read_text(encoding="utf-8")
    assert "## Failure Summary" in markdown
    assert "- Stage: patch_validation" in markdown


def test_large_patch_is_blocked_for_approval(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/large-patch.json",
        task_contract(
            tmp_path,
            "large-patch",
            stub_patch=(
                "--- a/sample.txt\n"
                "+++ b/sample.txt\n"
                "@@ -1 +1 @@\n"
                "-initial\n"
                "+updated " + ("x" * 25000) + "\n"
            ),
        ),
    )

    result = run_once(tmp_path)

    assert result.status == "blocked"
    report = read_json(tmp_path / "automation/artifacts/reports/large-patch.json")
    assert report["status"] == "blocked"
    assert "size limit" in report["reason"]
    approval = read_json(tmp_path / "automation/artifacts/approvals/large-patch.json")
    assert "size limit" in approval["reason"]
    assert (tmp_path / "automation/tasks/blocked/large-patch.json").exists()


def test_patch_with_too_many_files_is_blocked_for_approval(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    (tmp_path / "second.txt").write_text("old\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/multi-file-patch.json",
        task_contract(
            tmp_path,
            "multi-file-patch",
            allowed_paths=["sample.txt", "second.txt"],
            context_files=["sample.txt", "second.txt"],
            required_checks=[f"{sys.executable} -c \"print('ok')\""],
            stub_patch=(
                "--- a/sample.txt\n"
                "+++ b/sample.txt\n"
                "@@ -1 +1 @@\n"
                "-initial\n"
                "+updated\n"
                "--- a/second.txt\n"
                "+++ b/second.txt\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+done\n"
            ),
        ),
    )
    # Tighten the patch-size gate so the file-count gate is the only blocker.
    write_json(
        tmp_path / "automation/config/policy.json",
        {
            "allowed_command_prefixes": [[sys.executable, "-c"]],
            "global_forbidden_paths": [
                "data/**",
                "certs/**",
                ".env",
                ".venv/**",
                "automation/artifacts/**",
            ],
            "risk_levels": {
                "low": {
                    "allow_patch": True,
                    "allow_checks": True,
                    "allow_repair": True,
                    "requires_approval": False,
                }
            },
            "max_patch_bytes": 20000,
            "max_changed_files": 1,
            "default_max_repair_attempts": 1,
            "command_timeout_seconds": 20,
        },
    )

    result = run_once(tmp_path)

    assert result.status == "blocked"
    report = read_json(tmp_path / "automation/artifacts/reports/multi-file-patch.json")
    assert report["status"] == "blocked"
    assert "too many files" in report["reason"]
    approval = read_json(tmp_path / "automation/artifacts/approvals/multi-file-patch.json")
    assert "too many files" in approval["reason"]
    assert (tmp_path / "automation/tasks/blocked/multi-file-patch.json").exists()


def test_validate_patch_accepts_git_quoted_unicode_paths():
    patch = (
        'diff --git "a/docs/automation/RTCTraining_\\345\\206\\205\\351\\203\\250\\350\\207\\252\\344\\270\\273\\345\\274\\200\\345\\217\\221Agent.md" '
        '"b/docs/automation/RTCTraining_\\345\\206\\205\\351\\203\\250\\350\\207\\252\\344\\270\\273\\345\\274\\200\\345\\217\\221Agent.md"\n'
        '--- "a/docs/automation/RTCTraining_\\345\\206\\205\\351\\203\\250\\350\\207\\252\\344\\270\\273\\345\\274\\200\\345\\217\\221Agent.md"\n'
        '+++ "b/docs/automation/RTCTraining_\\345\\206\\205\\351\\203\\250\\350\\207\\252\\344\\270\\273\\345\\274\\200\\345\\217\\221Agent.md"\n'
        "@@ -28,6 +28,7 @@\n"
        " - `command` 模型网关，通过 `automation/config/runtime.json` 的 `model_command` 调用外部模型命令生成 unified diff。\n"
        " - 有限失败修复循环：required checks 失败后，最多按任务的 `max_repair_attempts` 请求修复 patch 并重跑测试。\n"
        "+- transcript 摘要：报告中保留模型交互 transcript 的简要摘要，便于快速观察任务决策过程。\n"
    )

    validation = validate_patch(
        patch,
        allowed_paths=["docs/automation/RTCTraining_内部自主开发Agent.md"],
        forbidden_paths=["data/**", "certs/**", ".env"],
        max_patch_bytes=20000,
        max_changed_files=4,
    )

    assert validation.ok is True
    assert validation.changed_files == ["docs/automation/RTCTraining_内部自主开发Agent.md"]


def test_apply_unified_patch_can_create_new_file(tmp_path):
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    initialize_git_repo(tmp_path)
    patch = (
        "--- /dev/null\n"
        "+++ b/new-file.txt\n"
        "@@ -0,0 +1 @@\n"
        "+created by patch\n"
    )

    apply_unified_patch(tmp_path, patch)

    assert (tmp_path / "new-file.txt").read_text(encoding="utf-8") == "created by patch\n"


def test_apply_unified_patch_can_update_existing_file_with_context(tmp_path):
    (tmp_path / "sample.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    initialize_git_repo(tmp_path)

    patch = (
        'diff --git a/sample.txt b/sample.txt\n'
        '--- a/sample.txt\n'
        '+++ b/sample.txt\n'
        '@@ -1,3 +1,3 @@\n'
        ' line1\n'
        '-line2\n'
        '+updated line2\n'
        ' line3\n'
    )

    apply_unified_patch(tmp_path, patch)

    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "line1\nupdated line2\nline3\n"


def test_runner_replenishes_tasks_from_supply_catalog(tmp_path):
    base_policy(tmp_path)
    base_runtime(tmp_path, model_backend="stub")
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/config/task_supply.json",
        {
            "enabled": True,
            "min_ready_tasks": 1,
            "max_ready_tasks": 2,
            "catalog_path": "automation/config/task_catalog.json",
        },
    )
    write_json(
        tmp_path / "automation/config/task_catalog.json",
        {
            "recipes": [
                {
                    "id": "auto-update-sample",
                    "title": "自动补给示例任务",
                    "goal": "把 sample.txt 更新为 updated。",
                    "context_files": ["sample.txt"],
                    "allowed_paths": ["sample.txt"],
                    "acceptance": ["sample.txt 变为 updated."],
                    "required_checks": [
                        f"{sys.executable} -c \"from pathlib import Path; assert Path('sample.txt').read_text() == 'updated\\n'\""
                    ],
                    "mode": "patch-only",
                    "risk_level": "low",
                    "stub_patch": (
                        "--- a/sample.txt\n"
                        "+++ b/sample.txt\n"
                        "@@ -1 +1 @@\n"
                        "-initial\n"
                        "+updated\n"
                    ),
                }
            ]
        },
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "updated\n"
    assert (tmp_path / "automation/tasks/done/auto-update-sample.json").exists()


def test_worktree_manager_snapshots_untracked_changes_and_links_venv(tmp_path):
    (tmp_path / "tracked.txt").write_text("initial\n", encoding="utf-8")
    initialize_git_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("updated\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("new file\n", encoding="utf-8")
    (tmp_path / ".venv" / "bin").mkdir(parents=True)

    worktree = WorktreeManager(tmp_path).create("snapshot-task")

    assert (worktree.path / "tracked.txt").read_text(encoding="utf-8") == "updated\n"
    assert (worktree.path / "untracked.txt").read_text(encoding="utf-8") == "new file\n"
    assert (worktree.path / ".venv").is_symlink()
    status = subprocess.run(
        ["git", "-C", str(worktree.path), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "?? .venv" not in status


def test_continuous_runner_processes_ready_tasks_until_limit(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    (tmp_path / "second.txt").write_text("old\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/update-sample.json",
        task_contract(tmp_path, "update-sample"),
    )
    write_json(
        tmp_path / "automation/tasks/ready/update-second.json",
        task_contract(
            tmp_path,
            "update-second",
            context_files=["second.txt"],
            allowed_paths=["second.txt"],
            required_checks=[
                f"{sys.executable} -c \"from pathlib import Path; assert Path('second.txt').read_text() == 'new\\n'\""
            ],
            stub_patch=(
                "--- a/second.txt\n"
                "+++ b/second.txt\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            ),
        ),
    )

    results = run_continuous(tmp_path, max_tasks=2, poll_interval_seconds=0)

    assert [result.status for result in results] == ["done", "done"]
    assert (tmp_path / "automation/tasks/done/update-sample.json").exists()
    assert (tmp_path / "automation/tasks/done/update-second.json").exists()


def test_worktree_mode_runs_task_in_isolated_workspace(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    initialize_git_repo(tmp_path)
    write_json(
        tmp_path / "automation/tasks/ready/update-sample.json",
        task_contract(tmp_path, "update-sample", mode="worktree"),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "initial\n"

    report = read_json(tmp_path / "automation/artifacts/reports/update-sample.json")
    assert report["mode"] == "worktree"
    worktree_root = tmp_path / report["workspace_path"]
    assert (worktree_root / "sample.txt").read_text(encoding="utf-8") == "updated\n"


def test_command_model_gateway_reads_patch_from_command_stdout(tmp_path):
    base_policy(tmp_path)
    command = (
        f"{sys.executable} -c \"import sys; "
        "sys.stdin.read(); "
        "print('--- a/sample.txt'); "
        "print('+++ b/sample.txt'); "
        "print('@@ -1 +1 @@'); "
        "print('-initial'); "
        "print('+updated')\""
    )
    gateway = CommandModelGateway(tmp_path, command)

    patch = gateway.develop(task_contract(tmp_path, "command-task"), {"summary": "change sample"})

    assert "--- a/sample.txt" in patch
    assert "+updated" in patch


def test_command_model_gateway_plan_records_input_summary(tmp_path):
    base_policy(tmp_path)
    gateway = CommandModelGateway(tmp_path, f"{sys.executable} -c \"print('unused')\"")

    plan = gateway.plan(task_contract(tmp_path, "plan-task"))

    assert plan["summary"] == "Change the sample file content."
    transcript = (tmp_path / "automation/artifacts/transcripts/plan-task.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in transcript]
    assert events[0]["type"] == "plan"
    assert "input_summary" in events[0]
    assert events[0]["input_summary"]["phase"] == "plan"
    assert events[0]["input_summary"]["task_id"] == "plan-task"
    assert events[0]["input_summary"]["context_files"] == ["sample.txt"]
    assert events[0]["input_summary"]["baseline"]["kind"] == "file-manifest"


def test_runner_uses_command_model_backend_when_configured(tmp_path):
    base_policy(tmp_path)
    command = (
        f"{sys.executable} -c \"import sys; "
        "sys.stdin.read(); "
        "print('--- a/sample.txt'); "
        "print('+++ b/sample.txt'); "
        "print('@@ -1 +1 @@'); "
        "print('-initial'); "
        "print('+updated')\""
    )
    base_runtime(tmp_path, model_backend="command", model_command=command)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/command-task.json",
        task_contract(tmp_path, "command-task", stub_patch=""),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "updated\n"


def test_failed_check_can_be_repaired_and_rechecked(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/repair-sample.json",
        task_contract(
            tmp_path,
            "repair-sample",
            stub_patch=(
                "--- a/sample.txt\n"
                "+++ b/sample.txt\n"
                "@@ -1 +1 @@\n"
                "-initial\n"
                "+wrong\n"
            ),
            stub_repair_patches=[
                (
                    "--- a/sample.txt\n"
                    "+++ b/sample.txt\n"
                    "@@ -1 +1 @@\n"
                    "-wrong\n"
                    "+updated\n"
                )
            ],
        ),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "updated\n"
    report = read_json(tmp_path / "automation/artifacts/reports/repair-sample.json")
    assert report["repair_attempts"] == 1
    assert report["checks"][-1]["status"] == "passed"


def test_patch_context_mismatch_can_fall_back_to_repair(tmp_path):
    base_policy(tmp_path)
    base_runtime(tmp_path, model_backend="stub")
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/context-mismatch.json",
        task_contract(
            tmp_path,
            "context-mismatch",
            stub_patch=(
                "--- a/sample.txt\n"
                "+++ b/sample.txt\n"
                "@@ -1 +1 @@\n"
                "-wrong-context\n"
                "+updated\n"
            ),
            stub_repair_patches=[
                (
                    "--- a/sample.txt\n"
                    "+++ b/sample.txt\n"
                    "@@ -1 +1 @@\n"
                    "-initial\n"
                    "+updated\n"
                )
            ],
        ),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "updated\n"
    report = read_json(tmp_path / "automation/artifacts/reports/context-mismatch.json")
    assert report["status"] == "done"
    assert report["repair_attempts"] == 1


def test_task_baseline_mismatch_blocks_before_execution(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/baseline-task.json",
        task_contract(tmp_path, "baseline-task"),
    )

    (tmp_path / "sample.txt").write_text("changed\n", encoding="utf-8")

    result = run_once(tmp_path)

    assert result.status == "blocked"
    report = read_json(tmp_path / "automation/artifacts/reports/baseline-task.json")
    assert report["status"] == "blocked"
    assert "baseline mismatch" in report["reason"]


def test_create_task_writes_ready_contract(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")

    task_path = create_task(
        tmp_path,
        task_id="created-task",
        title="Created task",
        goal="Update sample.",
        context_files=["sample.txt"],
        allowed_paths=["sample.txt"],
        acceptance=["sample updated."],
        required_checks=[f"{sys.executable} -c \"print('ok')\""],
        mode="worktree",
    )

    payload = read_json(task_path)
    assert task_path == tmp_path / "automation/tasks/ready/created-task.json"
    assert payload["id"] == "created-task"
    assert payload["risk_level"] == "low"
    assert payload["mode"] == "worktree"
    assert payload["forbidden_paths"] == ["data/**", "certs/**", ".env", ".venv/**"]
    assert payload["baseline"]["kind"] == "file-manifest"
    assert any(entry["path"] == "sample.txt" for entry in payload["baseline"]["files"])


def test_approve_task_moves_blocked_task_back_to_ready(tmp_path):
    base_policy(tmp_path)
    write_json(
        tmp_path / "automation/tasks/blocked/medium-task.json",
        task_contract(tmp_path, "medium-task", risk_level="medium"),
    )

    approved_path = approve_task(tmp_path, "medium-task")

    assert approved_path == tmp_path / "automation/tasks/ready/medium-task.json"
    assert approved_path.exists()
    assert not (tmp_path / "automation/tasks/blocked/medium-task.json").exists()
    payload = read_json(approved_path)
    assert payload["risk_level"] == "medium"
    assert payload["approved_by_user"] is True


def test_approved_medium_risk_task_can_run_without_second_approval(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/approved-medium-task.json",
        task_contract(tmp_path, "approved-medium-task", risk_level="medium", approved_by_user=True),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "automation/tasks/done/approved-medium-task.json").exists()
