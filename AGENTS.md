# RTCTraining Agent Guide

本文档是给 AI Coding Agent 的项目地图。详细开发背景、阶段记录和经验沉淀见 `docs/agents/RTCTraining_agent_memory.md`。

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
  -> 自动化测试和开发 runner
```

优先级关键词：

```text
可视化
可复现
可对比
可诊断
```

不要过早引入：

- 账号、鉴权、联系人和聊天记录。
- TURN / SFU / MCU。
- 公网部署和生产高可用。
- 录制、屏幕共享、服务端混流。
- 长期数据库和复杂运维系统。

## 2. 阅读入口

进入项目后按顺序阅读：

1. `docs/RTCTraining_项目开发文档.md`
2. 当前阶段计划：
   - `docs/superpowers/plans/2026-04-22-rtc-training-phase-0-1.md`
   - `docs/superpowers/plans/2026-04-22-rtc-training-phase-2-stats-dashboard.md`
3. 项目记忆：`docs/agents/RTCTraining_agent_memory.md`
4. 验证说明：`docs/agents/verification.md`

## 3. 当前阶段

当前已完成 Phase 0/1 和 Phase 2A。

下一阶段按 `docs/superpowers/plans/2026-04-22-rtc-training-phase-2-stats-dashboard.md` 进入 Phase 2B：

- Dashboard stats UI 合同测试。
- Dashboard 显示 room、peer pair、latest stats 和历史表格。
- Playwright 验证两页面 connected 后 Dashboard 显示 stats。
- 实现 `GET /stats/export.csv`。

## 4. 仓库结构

- `src/webrtc/`：WebRTC 服务、房间、信令、stats API。
- `src/dashboard/`：Dashboard 后端代理。
- `templates/webrtc/`：WebRTC 实验页 HTML。
- `templates/dashboard/`：Dashboard 页面 HTML。
- `static/webrtc/`：WebRTC 前端逻辑。
- `static/dashboard/`：Dashboard 前端逻辑。
- `tests/`：单元测试、handler 测试、Playwright E2E。
- `automation/`：自动化开发 runner。
- `docs/`：开发文档、阶段计划、Agent 文档。
- `certs/`、`data/`：本地生成数据，忽略提交。

## 5. 固定决策

以下决策已经确认，开发时直接遵守：

- WebRTC 服务监听 `0.0.0.0:8080`。
- Dashboard 服务监听 `127.0.0.1:8081`。
- 首版只支持桌面 Chrome。
- Playwright 面对本地自签名 HTTPS 时使用 `ignore_https_errors`。
- Dashboard CSV 对比直接做多 CSV 并列/叠加分析。
- `stats` 和测试会话数据必须按 `room_id / test_session_id / peer_id / remote_peer_id` 严格隔离。
- NACK / ABR 首版只作为手工实验门，增强版再进入自动回归门禁。
- 首版 Dashboard 页面只访问 Dashboard 后端，由 Dashboard 后端代理访问 WebRTC 服务。

## 6. 后端规则

- 使用 Python `aiohttp`。
- `RoomStore` 和 `StatsStore` 保持纯 Python，不导入 aiohttp。
- HTTP 层只做参数校验、错误映射和 JSON envelope。
- API 成功响应统一使用：

```json
{ "ok": true, "data": {} }
```

- API 失败响应统一使用：

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }
```

## 7. 前端规则

- 首版使用原生 HTML/CSS/JavaScript。
- 不引入复杂前端框架。
- 必须暴露 `window.__RTCTrainingTestHooks`，供 Playwright 读取状态和执行动作。
- 页面状态机必须可观察，不能只藏在 DOM 文本里。
- UI 面向实验和诊断，保持信息密度和可读性。

## 8. Dashboard 规则

- Dashboard 是独立进程、独立端口。
- 页面访问 Dashboard 后端，不直接跨端口访问 WebRTC 服务。
- 缺数据、服务不可达、字段缺失时必须降级显示，不能崩溃。
- stats 展示优先服务于诊断：room、peer pair、latest stats、历史表格、CSV 导出。

## 9. 开发节奏

- 新行为先写失败测试。
- 确认失败原因和目标行为相关。
- 只写让测试通过的最小实现。
- 每个可运行切片结束后运行相关验证命令。
- 涉及新能力时，先更新开发文档或阶段计划。
- 重要架构决策先写文档，用户审核后再开发。

## 10. 常用命令

```bash
make cert
make run-webrtc
make run-dashboard
make test-unit
make test-e2e
make test
make urls
```

推荐验证顺序：

```bash
make test-unit
make test-e2e
make test
```

更多验证细节见 `docs/agents/verification.md`。

## 11. 本地入口

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

常用 API：

- `https://localhost:8080/stats/peers?room_id=room1`
- `http://127.0.0.1:8081/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1`

## 12. 提交前检查

提交前至少确认：

- 相关单元测试通过。
- 涉及浏览器行为时，Playwright E2E 通过。
- 涉及 Dashboard 时，WebRTC 和 Dashboard 两个服务都能启动。

## 13. AGENTS.md 维护规则

`AGENTS.md` 只放全局规则和导航。

适合放在 `AGENTS.md`：

- 项目定位。
- 禁止做的方向。
- 架构边界。
- 测试命令。
- 必须遵守的响应格式。
- 必须保留的测试钩子。

适合放到 `docs/`：

- 详细 API 设计。
- 阶段计划。
- UI 状态说明。
- 实验方案。
- 历史开发记录。
