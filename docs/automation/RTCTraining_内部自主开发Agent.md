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
- `worktree` 模式：为任务创建 `.automation/worktrees/<task_id>` 隔离工作区。
- `stub` 模型网关，通过任务里的 `stub_patch` 字段提供 deterministic patch。
- `command` 模型网关，通过 `automation/config/runtime.json` 的 `model_command` 调用外部模型命令生成 unified diff。
- 有限失败修复循环：required checks 失败后，最多按任务的 `max_repair_attempts` 请求修复 patch 并重跑测试。
- 任务创建 CLI 和审批恢复 CLI。
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

- Web Console。
- 自动 git commit、push 或 merge。
- 内置 provider SDK 直连。当前真实模型通过外部命令网关接入。

当前 RTCTraining 已是 git 仓库，`mode=worktree` 可用。worktree 模式会在隔离工作区应用 patch 和运行测试，主工作区只保存任务状态与 artifacts，不直接承载代码修改。

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
make automation-task-help
```

创建任务：

```bash
.venv/bin/python -m automation.runner.task_cli create \
  --id fix-dashboard-empty-state \
  --title "修复 Dashboard 空状态" \
  --goal "Dashboard 没有 stats 数据时仍返回页面并显示空状态。" \
  --context-files templates/dashboard/index.html,tests/test_ui_routes.py \
  --allowed-paths templates/dashboard/index.html,tests/test_ui_routes.py \
  --acceptance "Dashboard 无 stats 数据时返回 HTTP 200。,相关测试通过。" \
  --required-checks ".venv/bin/python -m pytest tests/test_ui_routes.py -v" \
  --mode worktree
```

批准 blocked 任务并放回 ready 队列：

```bash
.venv/bin/python -m automation.runner.task_cli approve <task_id>
```

## 4. 模型网关配置

默认 `automation/config/runtime.json` 使用 `stub`：

```json
{
  "model_backend": "stub"
}
```

要让 agent 调用外部模型命令，把 runtime 改成：

```json
{
  "model_backend": "command",
  "model_command": "your-model-command --emit-unified-diff"
}
```

`model_command` 会收到一段 JSON stdin，字段包含：

- `phase`: `develop` 或 `repair`。
- `task`: 当前任务契约。
- `plan`: 当前计划。
- `failed_checks`: 仅 repair 阶段存在，包含失败检查摘要。

命令必须把 unified diff 输出到 stdout。runner 会继续执行路径、大小、文件数和 required checks 校验。模型命令本身如果需要网络或 API key，由运行环境负责提供。

## 5. 任务契约

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
  "mode": "worktree",
  "max_repair_attempts": 1,
  "stub_patch": "--- a/templates/dashboard/index.html\n+++ b/templates/dashboard/index.html\n@@ -1 +1 @@\n-old\n+new\n"
}
```

`mode` 可取 `patch-only` 或 `worktree`。推荐内部自主运行默认使用 `worktree`，只在不需要隔离或测试场景中使用 `patch-only`。

`stub_patch` 是 deterministic 模型网关使用的字段。`model_backend=command` 时，这个字段不会被使用，patch 由外部模型命令生成。

## 6. 审批 Gate

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

## 7. 成功标准

任务进入 `done` 必须满足：

- 任务契约字段完整。
- 策略校验通过。
- patch 只修改 `allowed_paths`。
- patch 没有命中禁止路径。
- required checks 全部通过。
- plan、patch、测试日志、transcript、JSON 报告和 Markdown 报告全部落盘。

任务失败会进入 `failed`，并在报告中记录原因。

如果 required checks 首次失败，runner 会在不超过 `max_repair_attempts` 的前提下请求修复 patch。每次修复 patch 都必须重新通过同一套策略校验，否则任务进入 `failed`。

## 8. 与长期目标的差异

项目开发文档中描述的更完整形态还包含 Web Console、自动提交策略和 provider SDK 直连。当前实现是可验证闭环：

```text
patch-only/worktree + stub/command model + policy gate + repair loop + required checks + artifacts
```

这保证 harness 本身先可靠，再逐步接入更强的模型能力。
