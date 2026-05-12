# RTCTraining Agent Memory

本文档沉淀本项目开发过程中的协作经验、稳定决策和可复用工作方式。后续任何智能体进入本仓库时，应先阅读本文，再阅读 `docs/RTCTraining_项目开发文档.md` 和当前阶段计划。

本文档不是产品说明，也不是完整开发文档；它是项目级 agent memory。若其中某些方法在多个项目中反复有效，可提炼为独立 Skill。

## 1. 项目定位记忆

`RTCTraining` 是一个本地/局域网 WebRTC 学习与实验仓库，不是公网生产聊天系统。

开发时应始终围绕以下闭环：

```text
本地/局域网浏览器实验页
  -> WebRTC P2P 建联
  -> getStats 可观察化
  -> Dashboard 实时观察
  -> 实验会话 CSV 固化
  -> 多次实验对比
  -> 自动化测试和闭环开发智能体
```

不要过早引入以下能力：

- 账号、鉴权、联系人和聊天记录。
- TURN / SFU / MCU。
- 公网部署和生产高可用。
- 录制、屏幕共享、服务端混流。
- 长期数据库和复杂运维系统。

优先级关键词：

```text
可视化
可复现
可对比
可诊断
```

## 2. 已确认的产品和工程决策

以下决策已经由用户确认，后续不应反复询问：

1. 必须支持另一台手机或电脑通过 IP 或 hostname 直接访问 WebRTC 实验页。
2. WebRTC 服务监听 `0.0.0.0:8080`。
3. Dashboard 使用独立进程和独立端口，默认 `127.0.0.1:8081`。
4. 首版只支持桌面 Chrome。
5. Playwright 面对本地自签名 HTTPS 时使用 `ignore_https_errors`。
6. Dashboard CSV 对比直接做多 CSV 并列/叠加分析。
7. `stats` 和测试会话数据必须按 `room_id / test_session_id / peer_id / remote_peer_id` 严格隔离。
8. NACK / ABR 首版只作为手工实验门，增强版再进入自动回归门禁。
9. 首版 Dashboard 页面只访问 Dashboard 后端，由 Dashboard 后端代理访问 WebRTC 服务，避免浏览器跨端口 HTTPS 自签名和 CORS 问题。

## 3. 当前源码状态

当前已完成 Phase 0/1 和 Phase 2A。

已经存在：

- `docs/RTCTraining_项目开发文档.md`
- `docs/superpowers/plans/2026-04-22-rtc-training-phase-0-1.md`
- `src/webrtc/config.py`
- `src/webrtc/response.py`
- `src/webrtc/room_store.py`
- `src/webrtc/mesh_handlers.py`
- `src/webrtc/stats_store.py`
- `src/webrtc/stats_handlers.py`
- `src/webrtc/app.py`
- `src/webrtc/ui_handlers.py`
- `src/webrtc/chat_server.py`
- `src/dashboard/server.py`
- `templates/webrtc/chat_real.html`
- `templates/dashboard/index.html`
- `static/webrtc/*.js`
- `static/webrtc/chat_real_stats.js`
- `static/webrtc/chat_real.css`
- `scripts/generate_cert.py`
- `scripts/print_lan_urls.py`
- `tests/test_config.py`
- `tests/test_room_store.py`
- `tests/test_mesh_handlers.py`
- `tests/test_stats_store.py`
- `tests/test_stats_handlers.py`
- `tests/test_ui_routes.py`
- `tests/test_cli.py`
- `tests/test_playwright_e2e.py`

已经完成：

- 双 Chrome 完整 P2P offer / answer / candidate 前端流程。
- Playwright 双页面 E2E。
- 远端视频渲染。
- 浏览器 `RTCPeerConnection.getStats()` 周期采集。
- WebRTC stats API 和内存 `StatsStore`。
- Dashboard 后端 stats 代理。

最近一次通过的验证命令：

```bash
make test-e2e
```

结果：

```text
5 passed in 6.79s
```

```bash
.venv/bin/python -m pytest tests -v
```

结果：

```text
38 passed in 7.30s
```

```bash
make test-unit
```

结果：

```text
33 passed in 0.41s
```

当前运行服务：

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

已确认新路由：

- `https://localhost:8080/stats/peers?room_id=room1` 返回 200。
- `http://127.0.0.1:8081/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1` 返回 200。

尚未完成：

- Dashboard 实时 stats 可视化 UI。
- stats CSV 导出。
- Dashboard 多 CSV 对比。
- NACK、ABR、测试会话。
- 自动化闭环开发 runner。

## 4. 开发协作方式

用户偏好：

- 中文文档。
- 先技术方案和开发文档，再开发。
- 重要架构决策先审核文档。
- 可以使用多个智能体审核架构、UI、开发和 QA。
- 开发时要说明准备做什么、为什么做、如何验证。
- 不要只给建议；在用户确认开工后，应推进到可运行、可测试的结果。

推荐节奏：

1. 先读 `docs/RTCTraining_项目开发文档.md`。
2. 再读当前阶段 plan。
3. 若需求涉及新能力，先更新文档或计划。
4. 实现时采用 TDD：先写失败测试，再写最小实现。
5. 每个可运行切片都运行验证命令。
6. 最终答复必须给出做了什么、验证了什么、还没做什么。

## 5. 提权和本地服务经验

本项目容易触发提权的动作：

- 首次创建 `.venv`。
- 安装 Python 依赖。
- 下载 Playwright 浏览器。
- aiohttp 测试绑定 `127.0.0.1` 临时端口。
- WebRTC 服务绑定 `0.0.0.0:8080`。
- Dashboard 服务绑定 `127.0.0.1:8081`。
- 用 `curl` 验证提权服务入口。

已经证明有效的减少提权策略：

1. 使用项目内 `.venv`，不要污染系统 Python。
2. 将依赖集中写入 `requirements.txt`，一次性安装。
3. 用 Python Playwright，优先使用本机 Chrome channel，减少 npm 链路。
4. 将服务启动封装到 Makefile：

```bash
make run-webrtc
make run-dashboard
make cert
make test
```

5. 让用户一次性批准以下命令前缀，而不是每个测试反复提权：

```bash
.venv/bin/python -m pip install
.venv/bin/python -m pytest
make run-webrtc
make run-dashboard
curl -k -I
curl -I
```

注意：

- 普通沙箱里的 `curl` 可能连不到提权启动的服务；如果服务会话仍在运行但普通 `curl` 失败，优先判断为沙箱网络隔离。
- `scripts/print_lan_urls.py` 在受限沙箱里可能只能探测到 `127.0.0.1`。真实局域网验收时，应通过系统网络设置或手动传入实际 IP，并重新生成包含该 IP 的证书：

```bash
.venv/bin/python scripts/generate_cert.py --host 192.168.x.x
```

## 6. 技术实现约定

后端：

- Python `aiohttp`。
- `RoomStore` 保持纯 Python，不导入 aiohttp，便于单元测试。
- HTTP 层只做参数校验、错误映射和 JSON envelope。
- 所有 API 响应使用：

```json
{ "ok": true, "data": {} }
```

或：

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }
```

前端：

- 首版使用原生 HTML/CSS/JavaScript。
- 不引入复杂前端框架。
- 必须暴露 `window.__RTCTrainingTestHooks`，供 Playwright 读取状态和执行动作。
- 首版状态机必须可观察，不要把状态只藏在 DOM 文本里。

Dashboard：

- 独立进程、独立端口。
- 首版先实现可打开页面，后续通过 Dashboard 后端代理 WebRTC API。
- 缺数据、服务不可达、字段缺失时必须降级，不应崩溃。

## 7. 测试策略记忆

测试分层：

1. `RoomStore` 单元测试：房间、成员、信令队列、server-only 信令类型。
2. aiohttp handler 测试：join、leave、members、signal、pending。
3. UI route 测试：WebRTC 首页、静态资源、Dashboard 首页。
4. CLI smoke 测试：服务入口和脚本 `--help`。
5. Playwright E2E：双桌面 Chrome、fake media、自签名 HTTPS 忽略、双页面建联。

当前已完成第 1 到第 4 层。第 5 层尚未完成。

TDD 规则：

- 新行为先写失败测试。
- 确认失败原因和目标行为相关。
- 只写让测试通过的最小实现。
- 每个阶段结束前跑当前相关的完整测试集。

## 8. 文档写作经验

本项目文档要偏执行文档，不偏宣传文案。

好的结构：

- 目标。
- 范围。
- 已确认决策。
- 模块边界。
- API 协议。
- 状态机。
- UI 状态。
- 测试钩子。
- 验收标准。
- 不做什么。

避免：

- 空泛愿景。
- 只写“后续实现”但不写接口。
- 使用未确认的公网/生产假设。
- 把 Dashboard、stats、test session 的数据边界写模糊。

## 9. 未来可沉淀为 Skill 的候选

以下经验具备跨项目复用价值，后续可提炼为独立 Skill。

### 9.1 本地局域网 WebRTC 实验仓库启动 Skill

触发场景：

- 用户要做本地/局域网 WebRTC 学习项目。
- 需要自签名 HTTPS、LAN IP、桌面 Chrome、Playwright fake media。
- 需要区分信令、媒体、stats、Dashboard。

可沉淀内容：

- Phase 0/1 文件结构。
- HTTPS SAN 证书生成。
- `0.0.0.0` 监听和 LAN 验收。
- HTTP 轮询信令最小协议。
- Playwright `ignore_https_errors` 和 fake media 策略。

### 9.2 先文档后开发的 RTC 实验项目 Skill

触发场景：

- 用户先要技术方案、架构文档、UI 方案，再启动开发。
- 项目包含实验闭环、Dashboard、CSV、自动化测试。

可沉淀内容：

- 如何先明确“不做什么”。
- 如何把学习价值转成功能优先级。
- 如何让 API、状态机、UI、测试钩子在开发前闭合。

### 9.3 降低人工提权打断的本地开发 Skill

触发场景：

- 沙箱环境开发本地服务。
- 需要安装依赖、绑定端口、启动服务、运行浏览器测试。
- 用户希望减少反复授权。

可沉淀内容：

- 一次性提权清单。
- 命令前缀选择原则。
- 哪些动作可以留在沙箱内。
- 沙箱网络隔离和服务验证的判断方法。

## 10. 下一步建议

当前已完成 Phase 2B 和 Phase 3 主线能力：

1. Dashboard live stats、peer pair、latest stats、history table。
2. `GET /stats/export.csv`。
3. 3 人 Mesh 观察。
4. NACK on/off、SDP munging 和 stats/CSV 字段记录。
5. 手动 sender bitrate 和简化 ABR，ABR 在 stats 上传周期自动调整 `maxBitrate`。
6. 测试会话 start / finish / cancel、preset、弱网条件记录。
7. 测试会话 CSV，按 `room_id / test_session_id / peer_id / remote_peer_id` 隔离。
8. Dashboard 多 CSV 校验、统计、指标选择、SVG 趋势图。
9. Dashboard 可直接列出已完成测试会话并加载 session CSV 分析。

后续建议：

1. 测试会话持久化索引：服务重启后扫描 `data/test_sessions/` 恢复历史 session 列表。
2. Dashboard 多 session 批量选择：一键对比 NACK ON/OFF、ABR ON/OFF。
3. CSV 趋势图增强：tooltip、min/max/avg 标尺、时间轴。
4. 弱网条件从记录扩展到半自动或自动控制。
5. Markdown 实验报告导出。
