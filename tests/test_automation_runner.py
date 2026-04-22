import json
import subprocess
import sys
from pathlib import Path

from automation.runner.model_gateway import CommandModelGateway
from automation.runner.orchestrator import run_continuous, run_once
from automation.runner.task_cli import approve_task, create_task


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


def task_contract(task_id: str, **overrides: object) -> dict:
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
    return contract


def test_low_risk_task_runs_to_done_and_records_artifacts(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/update-sample.json",
        task_contract("update-sample"),
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


def test_medium_risk_task_blocks_for_user_approval(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/medium-task.json",
        task_contract("medium-task", risk_level="medium"),
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


def test_continuous_runner_processes_ready_tasks_until_limit(tmp_path):
    base_policy(tmp_path)
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    (tmp_path / "second.txt").write_text("old\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/tasks/ready/update-sample.json",
        task_contract("update-sample"),
    )
    write_json(
        tmp_path / "automation/tasks/ready/update-second.json",
        task_contract(
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
        task_contract("update-sample", mode="worktree"),
    )

    result = run_once(tmp_path)

    worktree_file = tmp_path / ".automation/worktrees/update-sample/sample.txt"
    assert result.status == "done"
    assert (tmp_path / "sample.txt").read_text(encoding="utf-8") == "initial\n"
    assert worktree_file.read_text(encoding="utf-8") == "updated\n"

    report = read_json(tmp_path / "automation/artifacts/reports/update-sample.json")
    assert report["mode"] == "worktree"
    assert report["workspace_path"] == ".automation/worktrees/update-sample"


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

    patch = gateway.develop(task_contract("command-task"), {"summary": "change sample"})

    assert "--- a/sample.txt" in patch
    assert "+updated" in patch


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
        task_contract("command-task", stub_patch=""),
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


def test_approve_task_moves_blocked_task_back_to_ready(tmp_path):
    base_policy(tmp_path)
    write_json(
        tmp_path / "automation/tasks/blocked/medium-task.json",
        task_contract("medium-task", risk_level="medium"),
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
        task_contract("approved-medium-task", risk_level="medium", approved_by_user=True),
    )

    result = run_once(tmp_path)

    assert result.status == "done"
    assert (tmp_path / "automation/tasks/done/approved-medium-task.json").exists()
