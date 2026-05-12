# RTCTraining Agent Guide

本文档只放全局规则和导航。细节放到 `docs/`，按需阅读，避免把上下文一次性撑满。

## 1. 项目定位

`RTCTraining` 是本地/局域网 WebRTC 学习与实验仓库，不是公网生产聊天系统。

核心闭环：

```text
浏览器实验页
  -> WebRTC P2P 建联
  -> getStats 可观察化
  -> Dashboard 实时观察
  -> 实验会话 CSV 固化
  -> 多次实验对比
  -> harness / tests 验证
```

优先级：

```text
可视化
可复现
可对比
可诊断
可验证
```

禁止提前引入：

- 账号、鉴权、联系人、聊天记录。
- TURN / SFU / MCU。
- 公网部署和生产高可用。
- 录制、屏幕共享、服务端混流。
- 长期数据库和复杂运维系统。

## 2. 渐进式披露

先读：

1. `AGENTS.md`
2. `docs/agents/verification.md`
3. 当前任务对应的 plan/spec

按需再读：

- 项目背景：`docs/internal/archive/RTCTraining_项目开发文档.md`
- 前后端设计：`docs/internal/archive/RTCTraining_前后端设计说明.md`
- 历史记忆：`docs/internal/agents/RTCTraining_agent_memory.md`
- 开源重构计划：`docs/internal/superpowers/plans/2026-05-09-open-source-architecture-refactor.md`

不要为了小改动通读所有历史文档。只加载当前任务需要的上下文。

## 3. 当前重构主线

开源级架构重构按以下顺序推进：

1. 先开发 lightweight harness。
2. 补 README / CONTRIBUTING / SECURITY / 基础 GitHub CI。
3. 写 `docs/architecture.md` 和 `docs/api/*` 契约。
4. 配置环境变量和 Dashboard origin allowlist。
5. 后端拆 service / export / route registry。
6. 拆 Dashboard 前端和 WebRTC stats 前端。
7. 最终验证和人工审核。

每阶段必须可单独提交、审核、回滚。

## 4. 仓库结构

- `src/webrtc/`：WebRTC 服务、房间、信令、stats、测试会话。
- `src/dashboard/`：Dashboard 后端和代理。
- `templates/webrtc/`：WebRTC 实验页 HTML。
- `templates/dashboard/`：Dashboard 页面 HTML。
- `static/webrtc/`：WebRTC 前端逻辑。
- `static/dashboard/`：Dashboard 前端逻辑。
- `automation/harness/`：轻量服务级 smoke harness。
- `automation/runner/`：自动开发 runner，高级能力。
- `tests/`：单元、handler、Playwright E2E。
- `docs/`：公开架构、API、验证和发布文档。
- `docs/internal/`：历史计划、内部 agent 文档和旧设计材料。
- `certs/`、`data/`：本地生成数据，忽略提交。

## 5. 固定决策

- WebRTC 服务默认 `0.0.0.0:8080`。
- Dashboard 服务默认 `127.0.0.1:8081`。
- 首版只支持桌面 Chrome。
- Playwright 面对本地自签名 HTTPS 时使用 `ignore_https_errors`。
- Dashboard 页面只访问 Dashboard 后端，由后端代理 WebRTC 服务。
- Dashboard 代理必须有 origin allowlist，不能成为通用 HTTP 代理。
- `stats` 和测试会话数据必须按 `room_id / test_session_id / peer_id / remote_peer_id` 隔离。
- NACK / ABR 首版只作为手工实验门，增强版再进自动回归门禁。

## 6. 后端规范

- 使用 Python `aiohttp`。
- `RoomStore`、`StatsStore`、`TestSessionStore` 保持纯 Python，不导入 aiohttp。
- HTTP 层只做请求解析、参数校验、错误映射和 JSON envelope。
- 业务流程放 service 层，CSV/report 放 export 层。
- API 成功响应：

```json
{ "ok": true, "data": {} }
```

- API 失败响应：

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }
```

## 7. 前端规范

- 使用原生 HTML/CSS/JavaScript，不引入复杂前端框架。
- 必须保留 `window.__RTCTrainingTestHooks`。
- 页面状态必须可观察，不能只藏在 DOM 文本里。
- 数据获取、状态计算、DOM 渲染分离。
- Dashboard 优先使用后端 snapshot，不在页面里拼复杂后端状态。
- UI 面向实验和诊断，保持信息密度和可读性。

## 8. 编码规范

- 新行为先写失败测试，确认失败原因和目标行为相关。
- 只写让测试通过的最小实现。
- 不做无关重构，不改无关格式。
- 不把本地绝对路径暴露到 API 响应。
- 不提交 `certs/`、`data/`、`.venv/`、`.pytest_cache/`。
- 新公共 API、CSV 字段、启动参数、harness 行为必须同步文档。
- 后端重构不得改变现有 JSON envelope。
- 前端拆分不得删除现有 DOM id、测试钩子和 E2E 可观察状态。

## 9. ChangeLog 要求

用户可见行为变化必须更新 `CHANGELOG.md`。

需要记录：

- 新增/修改/删除 API。
- CSV schema 变化。
- 配置项、端口、启动命令变化。
- Dashboard 可见行为变化。
- harness、CI、测试入口变化。

不需要记录：

- 纯内部重命名且无行为变化。
- 只影响测试实现的改动。
- 注释和格式调整。

若 `CHANGELOG.md` 不存在，在开源工程化阶段创建，使用 `Unreleased` 小节。

## 10. Harness 和 CI

- harness 是服务级 smoke，不替代 pytest 或 Playwright。
- 第一版 harness 覆盖：服务启动、首页、stats API、Dashboard proxy、CSV header、进程清理。
- `make harness-smoke` 必须能自动清理子进程。
- GitHub CI 第一阶段只跑基础 unit 门禁。
- harness 稳定后再进 CI。
- Playwright E2E 稳定后再进 CI。

## 11. 常用命令

```bash
make cert
make run-webrtc
make run-dashboard
make harness-smoke
make test-unit
make test-e2e
make test
make urls
```

```bash
make test-unit
make harness-smoke
make test-e2e
```

更多细节见 `docs/agents/verification.md`。

## 12. 本地入口

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

常用 API：

- `https://localhost:8080/stats/peers?room_id=room1`
- `http://127.0.0.1:8081/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1`

## 13. 提交前检查

- 相关单元测试通过。
- 涉及服务启动时，`make harness-smoke` 通过。
- 涉及浏览器行为时，`make test-e2e` 通过。
- 涉及公共行为时，文档和 `CHANGELOG.md` 已更新。
- 涉及重构计划时，按 `docs/internal/superpowers/plans/2026-05-09-open-source-architecture-refactor.md` 的阶段和审核点执行。
