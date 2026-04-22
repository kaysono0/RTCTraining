# RTCTraining 内部自主开发 Agent

## 1. 目标

本文件描述 RTCTraining 当前实现的内部自主开发 agent。它面向本仓库使用，不是通用编程平台。

当前首版实现目标：

```text
低风险任务自动执行
  -> 生成计划
  -> 生成 patch
  -> 校验路径和 patch 大小
  -> 应用 patch
  -> 运行 required checks
  -> 生成报告和审计产物
  -> 继续处理下一个 ready 任务
```

只有风险升级、越权路径、越权命令、重大 patch 或需要提权时，任务进入 `blocked`，等待用户确认。

## 2. 当前实现范围

已实现：

- `patch-only` 模式。
- `stub` 模型网关，通过任务里的 `stub_patch` 字段提供 deterministic patch。
- 任务队列：`ready`、`running`、`done`、`failed`、`blocked`。
- 策略文件：`automation/config/policy.json`。
- 连续运行入口：`python -m automation.runner.orchestrator run-continuous`。
- 单任务运行入口：`python -m automation.runner.orchestrator run-once`。
- 审计产物：
  - `automation/artifacts/plans/`
  - `automation/artifacts/patches/`
  - `automation/artifacts/reports/`
  - `automation/artifacts/test-runs/`
  - `automation/artifacts/transcripts/`
  - `automation/artifacts/approvals/`

尚未实现：

- git worktree 隔离。
- 真实模型接入。
- 自动失败修复循环。
- Web Console。
- 自动 git commit、push 或 merge。

由于当前 RTCTraining 目录不是 git 仓库，首版不启用 worktree。后续初始化 git 后，再把 `mode=worktree` 接到 `git worktree`。

## 3. 运行命令

运行一个 ready 任务：

```bash
.venv/bin/python -m automation.runner.orchestrator run-once
```

连续处理 ready 任务，最多处理 3 个：

```bash
.venv/bin/python -m automation.runner.orchestrator run-continuous --max-tasks 3 --poll-interval-seconds 0
```

Makefile 入口：

```bash
make automation-run-once
make automation-run-continuous
```

## 4. 任务契约

任务文件放在：

```text
automation/tasks/ready/<task_id>.json
```

首版示例：

```json
{
  "id": "fix-dashboard-empty-state",
  "title": "修复 Dashboard 空状态",
  "goal": "Dashboard 没有 stats 数据时仍返回页面并显示空状态。",
  "context_files": [
    "templates/dashboard/index.html",
    "tests/test_ui_routes.py"
  ],
  "allowed_paths": [
    "templates/dashboard/index.html",
    "tests/test_ui_routes.py"
  ],
  "forbidden_paths": [
    "data/**",
    "certs/**",
    ".env",
    ".venv/**"
  ],
  "acceptance": [
    "Dashboard 无 stats 数据时返回 HTTP 200。",
    "相关测试通过。"
  ],
  "required_checks": [
    ".venv/bin/python -m pytest tests/test_ui_routes.py -v"
  ],
  "risk_level": "low",
  "mode": "patch-only",
  "max_repair_attempts": 1,
  "stub_patch": "--- a/templates/dashboard/index.html\n+++ b/templates/dashboard/index.html\n@@ -1 +1 @@\n-old\n+new\n"
}
```

`stub_patch` 是首版 deterministic 模型网关使用的字段。真实模型接入后，这个字段会被模型生成的 unified diff 替代。

## 5. 审批 Gate

以下情况不会自动修改代码，会进入 `automation/tasks/blocked/`：

- `risk_level` 是 `medium` 或 `high`。
- `required_checks` 不在命令白名单中。
- patch 触碰 `global_forbidden_paths`。
- patch 触碰任务 `forbidden_paths`。
- patch 修改 `allowed_paths` 之外的文件。
- patch 超过 `max_patch_bytes`。
- patch 修改文件数超过 `max_changed_files`。

审批请求写入：

```text
automation/artifacts/approvals/<task_id>.json
```

## 6. 成功标准

任务进入 `done` 必须满足：

- 任务契约字段完整。
- 策略校验通过。
- patch 只修改 `allowed_paths`。
- patch 没有命中禁止路径。
- required checks 全部通过。
- plan、patch、测试日志、transcript、JSON 报告和 Markdown 报告全部落盘。

任务失败会进入 `failed`，并在报告中记录原因。

## 7. 与长期目标的差异

项目开发文档中描述的最终形态包含 worktree、真实模型、失败分析、有限修复和 Web Console。当前实现是第一阶段可验证闭环：

```text
patch-only + stub model + policy gate + required checks + artifacts
```

这保证 harness 本身先可靠，再逐步接入更强的模型能力。
