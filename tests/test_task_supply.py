from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from automation.runner.task_supply import TaskSupplyManager


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_task_supply_replenishes_ready_queue_from_catalog(tmp_path):
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")
    write_json(
        tmp_path / "automation/config/task_supply.json",
        {
            "enabled": True,
            "min_ready_tasks": 2,
            "max_ready_tasks": 3,
            "catalog_path": "automation/config/task_catalog.json",
        },
    )
    write_json(
        tmp_path / "automation/config/task_catalog.json",
        {
            "recipes": [
                {
                    "id": "refresh-sample",
                    "title": "刷新示例文件",
                    "goal": "把 sample.txt 更新为 updated。",
                    "context_files": ["sample.txt"],
                    "allowed_paths": ["sample.txt"],
                    "acceptance": ["sample.txt 变为 updated."],
                    "required_checks": [
                        f"{sys.executable} -c \"from pathlib import Path; assert Path('sample.txt').read_text() == 'updated\\n'\""
                    ],
                    "mode": "patch-only",
                    "risk_level": "low",
                    "max_instances": 2,
                    "stub_patch": (
                        "--- a/sample.txt\n"
                        "+++ b/sample.txt\n"
                        "@@ -1 +1 @@\n"
                        "-initial\n"
                        "+updated\n"
                    ),
                },
            ]
        },
    )

    manager = TaskSupplyManager(tmp_path)
    created = manager.replenish()

    assert created == ["refresh-sample", "refresh-sample-2"]
    ready = sorted((tmp_path / "automation/tasks/ready").glob("*.json"))
    assert {path.stem for path in ready} == {"refresh-sample", "refresh-sample-2"}
    payload = json.loads((tmp_path / "automation/tasks/ready/refresh-sample.json").read_text(encoding="utf-8"))
    assert payload["baseline"]["kind"] == "file-manifest"
    assert any(entry["path"] == "sample.txt" for entry in payload["baseline"]["files"])


def test_task_supply_skips_existing_tasks_and_respects_upper_bound(tmp_path):
    write_json(
        tmp_path / "automation/config/task_supply.json",
        {
            "enabled": True,
            "min_ready_tasks": 3,
            "max_ready_tasks": 3,
            "catalog_path": "automation/config/task_catalog.json",
        },
    )
    write_json(
        tmp_path / "automation/config/task_catalog.json",
        {
            "recipes": [
                {
                    "id": "doc-smoke",
                    "title": "文档 smoke",
                    "goal": "更新文档。",
                    "context_files": ["docs/automation/RTCTraining_内部自主开发Agent.md"],
                    "allowed_paths": ["docs/automation/RTCTraining_内部自主开发Agent.md"],
                    "acceptance": ["文档更新。"],
                    "required_checks": [],
                    "mode": "worktree",
                    "risk_level": "low",
                    "max_instances": 1,
                }
            ]
        },
    )
    write_json(
        tmp_path / "automation/tasks/ready/doc-smoke.json",
        {
            "id": "doc-smoke",
            "title": "文档 smoke",
            "goal": "更新文档。",
            "context_files": ["docs/automation/RTCTraining_内部自主开发Agent.md"],
            "allowed_paths": ["docs/automation/RTCTraining_内部自主开发Agent.md"],
            "forbidden_paths": ["data/**"],
            "acceptance": ["文档更新。"],
            "required_checks": [],
            "risk_level": "low",
            "mode": "worktree",
        },
    )

    manager = TaskSupplyManager(tmp_path)
    created = manager.replenish()

    assert created == []
    ready = sorted((tmp_path / "automation/tasks/ready").glob("*.json"))
    assert [path.stem for path in ready] == ["doc-smoke"]


def test_task_cli_replenish_writes_ready_tasks(tmp_path):
    write_json(
        tmp_path / "automation/config/task_supply.json",
        {
            "enabled": True,
            "min_ready_tasks": 1,
            "max_ready_tasks": 1,
            "catalog_path": "automation/config/task_catalog.json",
        },
    )
    write_json(
        tmp_path / "automation/config/task_catalog.json",
        {
            "recipes": [
                {
                    "id": "cli-sample",
                    "title": "CLI 补给示例",
                    "goal": "创建一个通过 CLI 补给的任务。",
                    "context_files": ["sample.txt"],
                    "allowed_paths": ["sample.txt"],
                    "acceptance": ["sample.txt 被更新。"],
                    "required_checks": [],
                    "mode": "patch-only",
                    "risk_level": "low",
                }
            ]
        },
    )
    (tmp_path / "sample.txt").write_text("initial\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "automation.runner.task_cli", "replenish"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )

    assert "automation/tasks/ready/cli-sample.json" in result.stdout
    assert (tmp_path / "automation/tasks/ready/cli-sample.json").exists()


def test_repo_task_supply_catalog_is_valid():
    supply = json.loads((REPO_ROOT / "automation/config/task_supply.json").read_text(encoding="utf-8"))
    catalog = json.loads((REPO_ROOT / "automation/config/task_catalog.json").read_text(encoding="utf-8"))

    assert supply == {
        "enabled": True,
        "min_ready_tasks": 2,
        "max_ready_tasks": 2,
        "catalog_path": "automation/config/task_catalog.json",
    }
    assert [recipe["id"] for recipe in catalog["recipes"]] == [
        "context-contract-docs",
        "task-supply-regression",
        "report-baseline-summary",
        "failure-summary-project-docs",
        "approval-changed-files-regression",
        "approval-changed-files-regression-fixed",
        "approval-changed-files-count-summary",
    ]
    for recipe in catalog["recipes"]:
        assert recipe["mode"] == "worktree"
        assert recipe["risk_level"] == "low"
        assert recipe["max_instances"] == 1
