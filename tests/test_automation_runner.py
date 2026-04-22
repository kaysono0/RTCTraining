import json
import sys
from pathlib import Path

from automation.runner.orchestrator import run_continuous, run_once


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
