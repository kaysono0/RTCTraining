# RTCTraining Phase 2 Stats And Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在双人 P2P 建联闭环之上，建立 `getStats()` 采集、服务端缓存、Dashboard 实时观察和 CSV 导出的可观察化闭环。

**Architecture:** 浏览器在 `RTCPeerConnection` connected 后周期性调用 `getStats()`，按 peer pair 归一化指标并上传到 WebRTC 服务。WebRTC 服务用内存 `StatsStore` 保存 live/latest/history，Dashboard 独立进程通过后端代理读取 WebRTC stats API，Dashboard 页面只访问 Dashboard 端口。

**Tech Stack:** Python 3, aiohttp, pytest, pytest-aiohttp, Playwright Python, desktop Chrome, vanilla HTML/CSS/JavaScript, self-signed HTTPS, Makefile.

---

## 0. 当前进度

更新时间：2026-04-22

Phase 2A：已完成。

已完成能力：

- 服务端 `StatsStore`。
- WebRTC stats API：
  - `POST /stats`
  - `GET /stats`
  - `GET /stats/history`
  - `GET /stats/peers`
  - `POST /clear_stats`
- 前端 `chat_real_stats.js`。
- connected 后每秒调用 `RTCPeerConnection.getStats()`。
- 上报字段首版覆盖：
  - `connection_state`
  - `ice_connection_state`
  - `rtt_ms`
  - `packets_sent`
  - `packets_received`
  - `packets_lost`
  - `jitter_ms`
  - `bitrate_kbps`
  - `fps`
  - `frame_width`
  - `frame_height`
  - `codec`
  - `bytes_sent`
  - `bytes_received`
  - `nack_count`
  - `pli_count`
  - `fir_count`
- Dashboard 后端 stats 代理：
  - `GET /api/webrtc/stats`
  - `GET /api/webrtc/stats/history`
  - `GET /api/webrtc/stats/peers`
- Playwright E2E 已验证两页面 P2P connected 后，WebRTC `/stats/peers` 和 Dashboard 代理都能读到 A-B/B-A peer pair。

最近验证证据：

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

当前本地服务已重启到包含 `/stats` 的新代码：

- WebRTC: `https://localhost:8080`
- Dashboard: `http://127.0.0.1:8081`

已验证：

- `https://localhost:8080/stats/peers?room_id=room1` 返回 200。
- `http://127.0.0.1:8081/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1` 返回 200。

## 1. 当前文件结构

Phase 2 已创建或修改：

```text
src/webrtc/stats_store.py
src/webrtc/stats_handlers.py
src/webrtc/app.py
src/dashboard/server.py

templates/webrtc/chat_real.html
static/webrtc/chat_real_shared.js
static/webrtc/chat_real_session.js
static/webrtc/chat_real_bootstrap.js
static/webrtc/chat_real_stats.js

tests/test_stats_store.py
tests/test_stats_handlers.py
tests/test_playwright_e2e.py
tests/test_ui_routes.py
Makefile
```

职责边界：

- `stats_store.py`：纯 Python 内存 stats 存储，不依赖 aiohttp。
- `stats_handlers.py`：WebRTC 服务 stats API 参数校验和 JSON envelope。
- `chat_real_stats.js`：浏览器 `getStats()` 采集、字段归一化和 `POST /stats`。
- `src/dashboard/server.py`：Dashboard 后端代理 WebRTC stats API。
- `tests/test_playwright_e2e.py`：真实双页面 P2P + stats 上传 + Dashboard 代理回归。

## 2. 数据隔离规则

Stats 样本必须按以下 key 隔离：

```text
room_id
peer_id
remote_peer_id
test_session_id
```

当前实现细节：

- `test_session_id` 可以为 `None`。
- `latest()` 和 `history()` 查询必须显式传入 `room_id`。
- `peer_id`、`remote_peer_id`、`test_session_id` 是可选过滤条件。
- `peers(room_id=...)` 只返回指定房间内已观察到的 peer pair。
- `clear(room_id=...)` 只清理指定房间，不影响其他房间。

## 3. Phase 2B：Dashboard 实时可视化

目标：让用户不需要打开开发者工具，也能在 Dashboard 中看到 WebRTC 服务状态、房间、peer pair、最新 stats 和基础趋势。

### Task 1: Dashboard Stats API Contract Tests

**Files:**

- Modify: `tests/test_ui_routes.py`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: 写 Dashboard 代理失败测试**

新增测试函数：

```python
@pytest.mark.asyncio
async def test_dashboard_stats_proxy_routes_exist(dashboard_client):
    stats = await dashboard_client.get(
        "/api/webrtc/stats?origin=https://localhost:8080&room_id=room1"
    )
    history = await dashboard_client.get(
        "/api/webrtc/stats/history?origin=https://localhost:8080&room_id=room1"
    )
    peers = await dashboard_client.get(
        "/api/webrtc/stats/peers?origin=https://localhost:8080&room_id=room1"
    )

    assert stats.status != 404
    assert history.status != 404
    assert peers.status != 404
```

- [ ] **Step 2: 运行测试确认当前状态**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_dashboard_stats_proxy_routes_exist -v
```

Expected:

```text
PASSED
```

说明：该能力已在 Phase 2A 实现。此任务用于把 Dashboard stats proxy 明确纳入 UI route 回归。

### Task 2: Dashboard UI State And Static Contract

**Files:**

- Modify: `templates/dashboard/index.html`
- Modify: `static/dashboard/dashboard.js`
- Modify: `static/dashboard/dashboard.css`
- Test: `tests/test_ui_routes.py`

- [ ] **Step 1: 写失败测试**

扩展 `test_dashboard_homepage_loads_independent_shell`，要求页面包含以下元素：

```python
assert "statsRoomInput" in body
assert "statsState" in body
assert "peerPairList" in body
assert "latestStatsPanel" in body
assert "statsHistoryTable" in body
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_dashboard_homepage_loads_independent_shell -v
```

Expected:

```text
AssertionError
```

- [ ] **Step 3: 实现 Dashboard 基础 stats UI**

在 `templates/dashboard/index.html` 增加：

```html
<article class="status-panel stats-panel">
  <h2>Live Stats</h2>
  <label for="statsRoomInput">Room ID</label>
  <input id="statsRoomInput" value="room1">
  <p id="statsState">stats_unchecked</p>
  <ul id="peerPairList"></ul>
  <dl id="latestStatsPanel"></dl>
  <table id="statsHistoryTable">
    <thead>
      <tr>
        <th>Time</th>
        <th>Peer</th>
        <th>Remote</th>
        <th>RTT</th>
        <th>Loss</th>
        <th>Jitter</th>
        <th>Bitrate</th>
        <th>FPS</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</article>
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_ui_routes.py::test_dashboard_homepage_loads_independent_shell -v
```

Expected:

```text
PASSED
```

### Task 3: Dashboard Stats Polling

**Files:**

- Modify: `static/dashboard/dashboard.js`
- Modify: `templates/dashboard/index.html`
- Test: `tests/test_playwright_e2e.py`

- [ ] **Step 1: 写失败 E2E**

新增测试：

```python
def test_dashboard_renders_live_stats_after_two_pages_connect(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    room_id = "dashboard-live-stats"
    alice = browser_context.new_page()
    bob = browser_context.new_page()
    dashboard = browser_context.new_page()

    alice.goto(webrtc_https_server)
    bob.goto(webrtc_https_server)

    for page, display_name in ((alice, "Alice"), (bob, "Bob")):
        page.get_by_role("button", name="Start Media").click()
        expect(page.locator("#connectionState")).to_have_text("media_ready")
        page.fill("#roomIdInput", room_id)
        page.fill("#displayNameInput", display_name)

    alice.get_by_role("button", name="Join").click()
    bob.get_by_role("button", name="Join").click()

    for page in (alice, bob):
        expect(page.locator("#connectionState")).to_have_text("connected", timeout=10000)

    dashboard.goto(
        f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id={room_id}"
    )

    expect(dashboard.locator("#statsState")).to_have_text("stats_online", timeout=10000)
    expect(dashboard.locator("#peerPairList li")).to_have_count(2, timeout=10000)
    expect(dashboard.locator("#latestStatsPanel")).to_contain_text("RTT")
    expect(dashboard.locator("#statsHistoryTable tbody tr")).not_to_have_count(0)
```

- [ ] **Step 2: 运行 E2E 确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_renders_live_stats_after_two_pages_connect -v
```

Expected:

```text
AssertionError: Locator expected to have text 'stats_online'
```

- [ ] **Step 3: 实现 Dashboard stats 轮询**

在 `static/dashboard/dashboard.js` 增加：

```javascript
async function loadLiveStats() {
  const origin = document.getElementById("webrtcOriginInput").value.trim();
  const roomId = document.getElementById("statsRoomInput").value.trim() || "room1";
  setText("statsState", "stats_checking");

  const peersResponse = await fetch(`/api/webrtc/stats/peers?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
  const peersPayload = await peersResponse.json();
  if (!peersPayload.ok) {
    setText("statsState", peersPayload.error.code);
    return peersPayload;
  }

  renderPeerPairs(peersPayload.data.peers);
  if (peersPayload.data.peers.length === 0) {
    setText("statsState", "service_online_but_no_stats");
    return peersPayload;
  }

  const latestResponse = await fetch(`/api/webrtc/stats?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
  const latestPayload = await latestResponse.json();
  if (!latestPayload.ok) {
    setText("statsState", latestPayload.error.code);
    return latestPayload;
  }

  renderLatestStats(latestPayload.data.samples);
  renderHistoryRows(latestPayload.data.samples);
  setText("statsState", "stats_online");
  return latestPayload;
}
```

同时实现 `renderPeerPairs()`、`renderLatestStats()`、`renderHistoryRows()`，并在 `bootstrapDashboard()` 中：

```javascript
const queryRoomId = queryParam("room_id");
if (queryRoomId) {
  document.getElementById("statsRoomInput").value = queryRoomId;
}
window.setInterval(() => {
  loadLiveStats().catch((error) => {
    setText("statsState", "stats_error");
  });
}, 1000);
loadLiveStats().catch((error) => {
  setText("statsState", "stats_error");
});
```

- [ ] **Step 4: 运行 E2E 确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_playwright_e2e.py::test_dashboard_renders_live_stats_after_two_pages_connect -v
```

Expected:

```text
PASSED
```

### Task 4: CSV Export API

**Files:**

- Modify: `src/webrtc/stats_handlers.py`
- Modify: `src/webrtc/app.py`
- Test: `tests/test_stats_handlers.py`

- [ ] **Step 1: 写失败测试**

新增测试：

```python
@pytest.mark.asyncio
async def test_stats_export_csv_returns_room_scoped_history(client):
    await client.post("/stats", json=stats_payload(room_id="room1"))
    await client.post("/stats", json=stats_payload(room_id="room2"))

    response = await client.get("/stats/export.csv?room_id=room1")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert body.splitlines()[0] == (
        "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,"
        "rtt_ms,packets_lost,jitter_ms,bitrate_kbps,fps,frame_width,frame_height,codec"
    )
    assert ",room1," in body
    assert ",room2," not in body
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
.venv/bin/python -m pytest tests/test_stats_handlers.py::test_stats_export_csv_returns_room_scoped_history -v
```

Expected:

```text
404
```

- [ ] **Step 3: 实现 CSV 导出**

在 `StatsHandlers` 增加 `export_csv()`，字段顺序固定为：

```text
sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,
rtt_ms,packets_lost,jitter_ms,bitrate_kbps,fps,frame_width,frame_height,codec
```

路由：

```python
app.router.add_get("/stats/export.csv", stats_handlers.export_csv)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
.venv/bin/python -m pytest tests/test_stats_handlers.py::test_stats_export_csv_returns_room_scoped_history -v
```

Expected:

```text
PASSED
```

## 4. Phase 2B 完成标准

Phase 2B 完成前必须有新鲜验证证据：

```bash
make test-e2e
```

Expected:

```text
6 passed
```

```bash
.venv/bin/python -m pytest tests -v
```

Expected:

```text
所有测试通过
```

```bash
make test-unit
```

Expected:

```text
所有单元/API/UI route/CLI 测试通过
```

人工验收：

- 打开 `https://localhost:8080` 的两个 Chrome 页面，同房间建联后进入 `connected`。
- 打开 `http://127.0.0.1:8081/?webrtc_origin=https://localhost:8080&room_id=<room>`。
- Dashboard 显示：
  - `service_online`
  - `stats_online`
  - 两条 peer pair
  - 最新 RTT/loss/jitter/bitrate/fps/resolution
  - 至少一行历史 stats 表格
- 停止或刷新 WebRTC 页面后，Dashboard 不崩溃，进入空状态或服务错误状态。

## 5. 后续 Phase 3 入口条件

只有 Phase 2B 完成后，才进入以下能力：

- 3 人 Mesh 拓扑视图。
- NACK on/off 和 SDP diff。
- sender `maxBitrate` 手动控制。
- 简化 ABR。
- 测试会话 start / finish / cancel。
- 测试会话 CSV 固化。
- Dashboard 多 CSV 并列/叠加分析。
