# RTCTraining Phase 0/1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立本地/局域网 WebRTC 学习仓库的 Phase 0/1：可启动 HTTPS WebRTC 实验页、独立 Dashboard 进程骨架、房间/信令 API、双桌面 Chrome P2P 最小闭环和首版自动化测试入口。

**Architecture:** 后端使用 Python `aiohttp` 暴露 HTTPS WebRTC 服务，房间和信令状态保存在进程内 `RoomStore`。Dashboard 是独立 Python 进程和独立端口，首版只提供可打开页面和后续代理 API 的骨架。前端按模块拆分为状态/媒体/信令/启动入口，浏览器通过 HTTP 轮询交换 offer、answer、candidate，不经服务端转发媒体。

**Tech Stack:** Python 3, aiohttp, pytest, pytest-aiohttp, Playwright Python, desktop Chrome, vanilla HTML/CSS/JavaScript, Makefile, local self-signed HTTPS certificate.

---

## 0. 当前仓库状态

当前目录还不是 git 仓库。执行本计划时不做 `git commit`；如果后续初始化 git，再按任务边界提交。

现有主文档：

- `docs/RTCTraining_项目开发文档.md`
- `RTCTraining_整理版.md`

本计划只覆盖 Phase 0/1。Stats 后续已进入独立 Phase 2 计划，不在本文件展开。

### 0.1 执行进度快照

更新时间：2026-04-22

Phase 0/1 当前状态：已完成。

已完成能力：

- 项目 Python/aiohttp/pytest/Playwright 基础骨架。
- HTTPS WebRTC 服务，默认 `0.0.0.0:8080`。
- Dashboard 独立进程，默认 `127.0.0.1:8081`。
- 自签名证书生成脚本。
- 房间、成员、定向信令队列。
- 前端 `getUserMedia()`、加入/离开房间。
- 双 Chrome 页面 P2P offer / answer / candidate 建联。
- 远端视频渲染。
- Dashboard 服务可达性检查。
- Playwright fake media + `ignore_https_errors` E2E。

实际文件与本计划早期草案有两点差异：

- E2E 测试集中在 `tests/test_playwright_e2e.py`，没有使用 `tests/e2e/test_webrtc_smoke.py`。
- 双人 P2P 的确定性规则是“新加入者向已有 peer 发 offer”，不是“老成员收到 peer_joined 后发 offer”。当前测试已覆盖该规则。

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

## 1. 文件结构

Phase 0/1 创建或修改以下文件。

```text
requirements.txt
Makefile

src/webrtc/__init__.py
src/webrtc/config.py
src/webrtc/response.py
src/webrtc/room_store.py
src/webrtc/mesh_handlers.py
src/webrtc/ui_handlers.py
src/webrtc/app.py
src/webrtc/chat_server.py

src/dashboard/__init__.py
src/dashboard/server.py

templates/webrtc/chat_real.html
templates/dashboard/index.html

static/webrtc/chat_real_shared.js
static/webrtc/chat_real_session.js
static/webrtc/chat_real_bootstrap.js
static/webrtc/chat_real.css

scripts/generate_cert.py
scripts/print_lan_urls.py

tests/test_room_store.py
tests/test_mesh_handlers.py
tests/test_config.py
tests/e2e/test_webrtc_smoke.py
```

职责边界：

- `config.py`：端口、目录、证书路径、LAN 地址探测配置。
- `response.py`：统一 JSON 成功/失败 envelope。
- `room_store.py`：纯 Python 房间、成员、信令队列，不依赖 aiohttp。
- `mesh_handlers.py`：HTTP API 参数校验和 `RoomStore` 调用。
- `ui_handlers.py`：HTML 和静态资源路由。
- `app.py`：创建 aiohttp app，挂载路由。
- `chat_server.py`：WebRTC HTTPS 服务 CLI。
- `src/dashboard/server.py`：Dashboard 独立进程 CLI 和首页。
- `static/webrtc/*.js`：前端状态机、媒体、信令和测试钩子。
- `scripts/generate_cert.py`：生成包含 localhost、127.0.0.1、hostname、局域网 IP 的自签名证书。

## 2. 一次性提权清单

为了避免频繁人工提权，依赖安装和浏览器准备集中在开发启动窗口执行一次。

建议一次性允许以下命令前缀：

```bash
python3 -m venv
.venv/bin/python -m pip install
.venv/bin/python -m playwright install
.venv/bin/python -m pytest
make
```

如果 Playwright 使用本机 Chrome channel 且本机已安装 Chrome，可以先不执行浏览器下载：

```bash
.venv/bin/python -m playwright install
```

本计划优先使用 Playwright Python，并配置 `channel="chrome"`、`ignore_https_errors=True`。这样依赖链比 npm 方案短，人工提权次数更少。

不需要提权的动作：

- 在仓库内创建和编辑源码、测试、模板、静态文件。
- 运行不联网的 Python 单元测试。
- 生成写入仓库内 `certs/` 的自签名证书。
- 启动监听本机用户端口 `8080` 和 `8081` 的开发服务。

需要临时确认的动作：

- 首次联网安装 Python 依赖。
- 首次下载 Playwright 浏览器依赖。
- 用系统 GUI 打开 Chrome 或 Finder。

## 3. 并行任务划分

可以并行推进的工作：

1. **后端工程师**：`room_store.py`、`mesh_handlers.py`、`app.py`、`chat_server.py`。
2. **前端工程师**：`chat_real.html`、`chat_real_shared.js`、`chat_real_session.js`、`chat_real_bootstrap.js`、`chat_real.css`。
3. **Dashboard 工程师**：`src/dashboard/server.py`、`templates/dashboard/index.html`。
4. **QA 工程师**：`tests/test_room_store.py`、`tests/test_mesh_handlers.py`、`tests/e2e/test_webrtc_smoke.py`。

关键依赖顺序：

```text
RoomStore
  -> mesh_handlers
  -> aiohttp app
  -> 前端 join/signal API
  -> Playwright 双页面 smoke
```

Dashboard 骨架可与 RoomStore 并行；Playwright E2E 必须等服务和前端最小闭环完成。

## 4. Task 1：配置和响应 envelope

**Files:**

- Create: `src/webrtc/__init__.py`
- Create: `src/webrtc/config.py`
- Create: `src/webrtc/response.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
from src.webrtc.config import Settings
from src.webrtc.response import error_payload, success_payload


def test_default_settings_match_phase_0_contract():
    settings = Settings()

    assert settings.webrtc_host == "0.0.0.0"
    assert settings.webrtc_port == 8080
    assert settings.dashboard_host == "127.0.0.1"
    assert settings.dashboard_port == 8081
    assert settings.tls_cert_path == "certs/cert.pem"
    assert settings.tls_key_path == "certs/key.pem"


def test_response_envelope_shape():
    assert success_payload({"room_id": "room1"}) == {
        "ok": True,
        "data": {"room_id": "room1"},
    }

    assert error_payload("bad_request", "room_id is required", {"field": "room_id"}) == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "room_id is required",
            "details": {"field": "room_id"},
        },
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'src.webrtc.config'
```

- [ ] **Step 3: 实现最小代码**

`src/webrtc/config.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    webrtc_host: str = "0.0.0.0"
    webrtc_port: int = 8080
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8081
    local_webrtc_origin: str = "https://localhost:8080"
    local_signaling_url: str = "https://localhost:8080"
    dashboard_origin: str = "http://localhost:8081"
    tls_cert_path: str = "certs/cert.pem"
    tls_key_path: str = "certs/key.pem"
    data_dir: str = "data"
    exports_dir: str = "data/exports"
    test_sessions_dir: str = "data/test_sessions"
    charts_dir: str = "data/charts"
```

`src/webrtc/response.py`:

```python
def success_payload(data=None):
    return {"ok": True, "data": data if data is not None else {}}


def error_payload(code, message, details=None):
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        },
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected:

```text
2 passed
```

## 5. Task 2：RoomStore 房间和信令核心

**Files:**

- Create: `src/webrtc/room_store.py`
- Test: `tests/test_room_store.py`

- [ ] **Step 1: 写失败测试**

```python
from src.webrtc.room_store import RoomFullError, RoomStore


def test_join_returns_existing_peers_and_notifies_old_members():
    store = RoomStore(max_members=3)

    first = store.join_room("room1", "client-a", "Alice")
    second = store.join_room("room1", "client-b", "Bob")
    pending_for_a = store.pop_pending("room1", "client-a")

    assert first["existing_peers"] == []
    assert second["existing_peers"] == [
        {"peer_id": "client-a", "display_name": "Alice"}
    ]
    assert pending_for_a == [
        {
            "type": "peer_joined",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b", "display_name": "Bob"},
        }
    ]


def test_signal_pending_is_target_isolated_and_consumed():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    store.join_room("room1", "client-b", "Bob")

    store.send_signal(
        room_id="room1",
        from_peer_id="client-a",
        to_peer_id="client-b",
        message_type="offer",
        payload={"sdp": "fake-offer"},
    )

    assert store.pop_pending("room1", "client-a") == [
        {
            "type": "peer_joined",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b", "display_name": "Bob"},
        }
    ]
    assert store.pop_pending("room1", "client-b") == [
        {
            "type": "offer",
            "from_peer_id": "client-a",
            "to_peer_id": "client-b",
            "payload": {"sdp": "fake-offer"},
        }
    ]
    assert store.pop_pending("room1", "client-b") == []


def test_leave_notifies_remaining_members_and_removes_peer():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    store.join_room("room1", "client-b", "Bob")
    store.pop_pending("room1", "client-a")

    store.leave_room("room1", "client-b")

    assert store.list_members("room1") == [
        {"peer_id": "client-a", "display_name": "Alice"}
    ]
    assert store.pop_pending("room1", "client-a") == [
        {
            "type": "peer_left",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b"},
        }
    ]


def test_room_limit_is_enforced():
    store = RoomStore(max_members=1)
    store.join_room("room1", "client-a", "Alice")

    try:
        store.join_room("room1", "client-b", "Bob")
    except RoomFullError as exc:
        assert str(exc) == "room room1 is full"
    else:
        raise AssertionError("expected RoomFullError")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/test_room_store.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'src.webrtc.room_store'
```

- [ ] **Step 3: 实现最小代码**

`RoomStore` 只负责内存状态，不导入 aiohttp。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
python3 -m pytest tests/test_room_store.py -v
```

Expected:

```text
4 passed
```

## 6. Task 3：aiohttp mesh API

**Files:**

- Create: `src/webrtc/mesh_handlers.py`
- Create: `src/webrtc/app.py`
- Test: `tests/test_mesh_handlers.py`

- [ ] **Step 1: 写失败测试**

测试覆盖：

- `POST /rooms/join` 返回 `existing_peers`。
- `POST /signal` 只允许 `offer`、`answer`、`candidate`、`renegotiate`。
- `GET /signal/pending` 拉取即消费。
- `peer_joined` 和 `peer_left` 不能由普通客户端伪造。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/test_mesh_handlers.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'src.webrtc.app'
```

- [ ] **Step 3: 实现最小 API**

所有响应使用：

```python
{"ok": true, "data": {...}}
{"ok": false, "error": {"code": "...", "message": "...", "details": {...}}}
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
python3 -m pytest tests/test_mesh_handlers.py -v
```

Expected:

```text
4 passed
```

## 7. Task 4：HTTPS 服务和 Dashboard 独立进程

**Files:**

- Create: `scripts/generate_cert.py`
- Create: `scripts/print_lan_urls.py`
- Create: `src/webrtc/ui_handlers.py`
- Create: `src/webrtc/chat_server.py`
- Create: `src/dashboard/__init__.py`
- Create: `src/dashboard/server.py`
- Create: `templates/dashboard/index.html`
- Modify: `Makefile`
- Modify: `requirements.txt`

- [ ] **Step 1: 写启动相关测试**

`tests/test_config.py` 增加目录和默认端口断言，确认 WebRTC 和 Dashboard 端口分离。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected:

```text
AssertionError
```

- [ ] **Step 3: 实现服务入口**

`Makefile` 暴露：

```makefile
run-webrtc:
	python3 -m src.webrtc.chat_server run

run-dashboard:
	python3 -m src.dashboard.server run

cert:
	python3 scripts/generate_cert.py

test:
	python3 -m pytest tests -v
```

- [ ] **Step 4: 验证服务可启动**

Run:

```bash
python3 -m src.webrtc.chat_server --help
python3 -m src.dashboard.server --help
```

Expected:

```text
usage:
```

## 8. Task 5：WebRTC 实验页前端最小闭环

**Files:**

- Create: `templates/webrtc/chat_real.html`
- Create: `static/webrtc/chat_real.css`
- Create: `static/webrtc/chat_real_shared.js`
- Create: `static/webrtc/chat_real_session.js`
- Create: `static/webrtc/chat_real_bootstrap.js`

- [ ] **Step 1: 写 Playwright smoke 测试**

`tests/e2e/test_webrtc_smoke.py` 检查页面加载、测试钩子存在、初始状态为 `idle`。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/e2e/test_webrtc_smoke.py -v
```

Expected:

```text
connection refused
```

- [ ] **Step 3: 实现页面和测试钩子**

必须暴露：

```javascript
window.__RTCTrainingTestHooks = {
  getState() {},
  getClientId() {},
  getRoomId() {},
  getPeers() {},
  getTimeline() {},
  startMedia() {},
  joinRoom(roomId, displayName) {},
  leaveRoom() {}
}
```

- [ ] **Step 4: 运行 smoke 测试确认通过**

Run:

```bash
python3 -m pytest tests/e2e/test_webrtc_smoke.py -v
```

Expected:

```text
1 passed
```

## 9. Task 6：双 Chrome P2P 首版回归

**Files:**

- Modify: `tests/e2e/test_webrtc_smoke.py`
- Modify: `static/webrtc/chat_real_session.js`

- [ ] **Step 1: 写双页面失败测试**

测试流程：

1. 启动 HTTPS WebRTC 服务。
2. 打开两个桌面 Chrome context。
3. 两边授权 fake camera / microphone。
4. A 调用 `startMedia()` 和 `joinRoom("room1", "Alice")`。
5. B 调用 `startMedia()` 和 `joinRoom("room1", "Bob")`。
6. 等待两个页面的 peer state 出现对方 peer。
7. 等待至少一边进入 `connected` 或 `ice_connection_state` 为 `connected/completed`。
8. B 调用 `leaveRoom()`。
9. A timeline 出现 `peer_left`。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/e2e/test_webrtc_smoke.py::test_two_pages_can_join_and_exchange_signaling -v
```

Expected:

```text
AssertionError
```

- [ ] **Step 3: 实现 offer / answer / candidate 流程**

规则：

- 老成员收到 `peer_joined` 后创建 offer。
- 新成员收到 offer 后创建 answer。
- candidate 早于 remote description 时先进入 `pending_remote_candidates`。
- 离开时关闭所有 PeerConnection，停止轮询，释放 media tracks。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
python3 -m pytest tests/e2e/test_webrtc_smoke.py::test_two_pages_can_join_and_exchange_signaling -v
```

Expected:

```text
1 passed
```

## 10. Phase 0/1 完成标准

Phase 0/1 只在以下命令有新鲜通过证据后才算完成：

```bash
python3 -m pytest tests/test_config.py tests/test_room_store.py tests/test_mesh_handlers.py -v
python3 -m pytest tests/e2e/test_webrtc_smoke.py -v
```

人工验收：

- `https://localhost:8080/` 能打开 WebRTC 实验页。
- `http://127.0.0.1:8081/` 能打开 Dashboard。
- 同一局域网另一台设备可以通过 IP 或 hostname 打开 WebRTC 实验页，并在桌面 Chrome 中接受自签名证书后看到页面。

## 11. 当前执行策略

第一轮实现先做：

1. Task 1：配置和响应 envelope。
2. Task 2：纯 Python `RoomStore`。
3. Task 3：aiohttp mesh API 的测试和骨架。

这三项可以在不启动浏览器的情况下快速建立后端主干。等依赖安装窗口打开后，再集中执行 aiohttp、pytest-aiohttp 和 Playwright 相关验证。
