# RTCTraining 项目开发文档

## 1. 文档目标

本文档用于指导重新开发 `RTCTraining`：一个本地/局域网 WebRTC 学习与实验仓库。

它不是产品介绍，也不是单纯的架构备忘录，而是一份面向开发执行的主文档。读完本文后，开发者应能理解：

- 这个仓库要解决什么问题。
- 哪些能力是主路径，哪些只是扩展。
- 应该按什么顺序开发。
- 每个阶段要创建哪些模块。
- 每个模块负责什么。
- 需要暴露哪些 HTTP API。
- 测试应该如何覆盖。
- 闭环开发智能体应该在什么时候介入，以及如何为主项目服务。

## 2. 项目定位

`RTCTraining` 是一个面向学习、实验和工程训练的本地/局域网 WebRTC 仓库。

核心目标是跑通以下实验闭环：

```text
浏览器打开实验页
  -> 采集摄像头和麦克风
  -> 加入房间
  -> 通过 HTTP 轮询信令建立 P2P 连接
  -> 浏览器周期性调用 getStats()
  -> 服务端接收并缓存 stats
  -> Dashboard 实时观察质量指标
  -> 运行 NACK / bitrate / ABR 实验
  -> 测试会话导出 CSV
  -> 多次实验 CSV 对比
  -> 自动化开发 runner 推进低风险工程任务
```

项目不做公网生产 RTC 服务，不覆盖：

- TURN / SFU / MCU。
- 认证、鉴权、多租户。
- 长期持久化存储。
- 录制、屏幕共享。
- 公网高可用部署。
- 生产级监控和运维。

推荐主路径始终是：

```text
双浏览器 P2P 弱网实验
  -> 3 人 Mesh 学习扩展
  -> Dashboard 可观察化
  -> 测试会话 CSV 固化
  -> Automation Runner 工程化推进
```

### 2.1 开源用户学习价值

从开源用户视角看，`RTCTraining` 不应只是一个“能视频聊天”的示例项目，而应是一个本地/局域网 WebRTC 可观测实验室。

用户读代码、跑实验和看 Dashboard 后，应该能学到以下内容：

1. WebRTC 建联主链路。

   用户应能完整理解 `getUserMedia()`、`RTCPeerConnection`、Offer、Answer、ICE Candidate、P2P 媒体连接之间的关系，并能在真实浏览器中跑通双人音视频连接。

2. 信令和 WebRTC 的边界。

   项目使用 HTTP 轮询信令，目的是让用户清楚看到：信令不是 WebRTC 标准的一部分，房间、成员、offer、answer、candidate 投递都是应用层自己定义的控制面逻辑。

3. WebRTC 质量指标观测方法。

   通过 `getStats()`、StatsStore 和 Dashboard，用户应能理解 RTT、packet loss、jitter、bitrate、FPS、resolution、health score 等指标的来源、含义和局限。

4. 弱网实验和质量调优。

   用户应能通过 NACK、sender bitrate、简化 ABR、测试会话和 CSV 对比，理解不同控制策略对实时音视频质量的影响。

5. 实验驱动的工程闭环。

   项目应帮助用户学习如何设计一次可复现 RTC 实验：固定配置、记录会话、导出 CSV、叠加对比、多次回归，并逐步把人工观察沉淀为自动化检查。

因此，本项目后续功能优先级应服务于四个关键词：

```text
可视化
可复现
可对比
可诊断
```

不应过早把重心转向生产聊天产品能力，例如账号系统、联系人、消息记录、录制、服务端混流或公网部署。

### 2.2 建议增加的学习实践功能

以下功能是从开源学习者视角补充的增强方向。它们不全部属于 MVP，但应进入增强版路线和后续 issue 拆分。

#### 2.2.1 WebRTC 建联过程时间线

实验页应展示从空闲到连接成功或失败的状态时间线：

```text
idle
  -> local media ready
  -> joined room
  -> offer created
  -> offer sent
  -> answer received
  -> ICE checking
  -> connected
  -> disconnected / failed
```

要求：

- 每个事件带时间戳。
- 事件记录 `room_id`、`peer_id`、`remote_peer_id`。
- 信令事件区分发送方向和接收方向。
- 关键事件可以展开查看摘要 payload。
- Playwright 测试可通过页面钩子读取当前状态。

该能力优先级高，应作为阶段 1 前端最小闭环的一部分实现。

#### 2.2.2 SDP 查看与差异对比

实验页应提供 SDP 面板，用于学习协商细节：

- 展示 local offer。
- 展示 remote offer。
- 展示 local answer。
- 展示 remote answer。
- 支持折叠 media section。
- 高亮 codec、payload type、rtcp-fb、bandwidth、candidate 相关行。
- NACK on/off 时支持查看 SDP 差异。

首版可以只做文本展示和关键字高亮；增强版再做结构化解析和 diff。

#### 2.2.3 ICE Candidate 可视化

实验页应展示 ICE candidate 和 selected candidate pair：

- candidate type：`host` / `srflx` / `relay`。
- protocol：`udp` / `tcp`。
- address / port。
- priority。
- selected candidate pair。
- ICE connection state 变化。

首版不做 TURN，但仍应让用户理解局域网 `host` candidate 如何工作，并为后续学习 STUN / TURN 打基础。

#### 2.2.4 一键实验 preset

测试会话应支持固定实验 preset：

```text
baseline
nack_on
nack_off
low_bitrate
abr_simple
loss_observation
```

要求：

- preset 写入测试会话元数据。
- preset 写入 CSV 文件名或 metadata。
- preset 应明确 NACK、ABR、bitrate、duration 等关键配置。
- 用户仍可手动覆盖 note 和 duration。

该能力应归入阶段 3 的测试会话功能。

#### 2.2.5 弱网条件记录

首版不要求自动控制系统弱网，但测试会话应允许记录实验条件：

- 网络类型：Wi-Fi / 有线 / 热点。
- 是否使用系统弱网工具。
- packet loss 设置。
- latency 设置。
- bandwidth 设置。
- 实验备注。

这些信息应进入测试会话 metadata，并在 CSV 导出或实验报告中保留。

#### 2.2.6 RTC 指标解释

Dashboard 应为关键指标提供简短解释，帮助用户边观察边学习：

- RTT。
- packet loss。
- jitter。
- bitrate。
- FPS。
- resolution。
- health score。

解释信息应以 tooltip 或轻量帮助文本呈现，不应占用主图表区域，也不应把 Dashboard 做成教程长文页面。

#### 2.2.7 多 Peer Mesh 拓扑图

3 人 Mesh 阶段应增加拓扑视图：

```text
A <----> B
 \      /
  \    /
    C
```

每条边展示：

- connected / failed。
- RTT。
- packet loss。
- bitrate。
- last stats update。

该能力用于帮助用户理解 Mesh 连接数量增长，以及为什么多人 RTC 通常需要 SFU。

#### 2.2.8 实验报告导出

除 CSV 外，增强版应支持导出 Markdown 实验报告：

```text
# RTCTraining 实验报告

实验 ID:
房间:
参与 Peer:
实验配置:
NACK:
ABR:
平均 RTT:
最大丢包:
平均码率:
主要观察:
CSV 文件:
```

报告可以基于测试会话 metadata 和 CSV 统计值生成，适合学习记录、课程作业、博客复盘和团队讨论。

#### 2.2.9 故障注入和诊断面板

增强版应提供可控故障按钮：

- 停止本地 video track。
- 停止本地 audio track。
- 关闭指定 peer connection。
- 暂停 stats 上传。
- 模拟信令延迟。
- 模拟 candidate 丢失。

诊断面板应能提示：

- 没有本地媒体。
- 已加入房间但没有远端 peer。
- offer 已发出但未收到 answer。
- ICE failed。
- stats 长时间未更新。

该能力用于把项目变成 RTC 故障训练场，而不是只能验证 happy path。

#### 2.2.10 学习任务模式

项目可以增加 `docs/LESSONS.md` 或页面内任务模式：

```text
Lesson 1：建立双人 P2P。
Lesson 2：观察 getStats。
Lesson 3：比较 NACK on/off。
Lesson 4：限制发送码率。
Lesson 5：运行测试会话并导出 CSV。
Lesson 6：在 Dashboard 叠加比较多次实验。
```

每个任务应包含：

- 学习目标。
- 操作步骤。
- 预期现象。
- 验证方式。
- 相关源码入口。

### 2.3 增强功能优先级

后续开发优先级建议如下：

1. 建联状态时间线。
2. SDP / ICE 可视化。
3. 测试会话 preset。
4. Dashboard 多 CSV 叠加和指标解释。
5. Mesh 拓扑图。
6. 弱网条件记录和 Markdown 实验报告。
7. 故障注入和诊断面板。
8. 学习任务模式。

其中前 5 项直接服务于 WebRTC 学习主路径，应优先进入增强版；后 3 项可以作为后续学习体验优化逐步补齐。

## 3. 总体开发原则

### 3.0 已确认约束

基于 2026-04-22 的审阅反馈和确认，后续开发按以下约束执行：

- 局域网访问是一等场景：必须支持另一台手机或电脑通过 IP 或 hostname 直接访问实验页。
- Dashboard 采用独立进程、独立端口，不与 WebRTC 实验页共用 `GET /`。
- 首版浏览器支持范围只覆盖桌面 Chrome。
- Playwright 面对本地自签名 HTTPS 时使用 `ignore_https_errors`。
- Dashboard CSV 对比直接做“多 CSV 并列/叠加分析”，不是只做单个历史基线对比。
- `stats` 和测试会话数据必须严格按 `room_id / test_session_id / peer_id / remote_peer_id` 隔离。
- NACK / ABR 首版作为手工实验门禁；增强版再进入自动回归门禁。

### 3.1 主路径优先

先让两个浏览器能建立 P2P 音视频连接，再逐步添加 stats、Dashboard、CSV、ABR 和自动化 runner。

不要一开始就做复杂的抽象、生产化部署或完整平台能力。

### 3.2 服务端只做控制面和观测面

Python 服务只负责：

- 页面和静态资源。
- 房间成员状态。
- 定向信令消息队列。
- stats 接收和缓存。
- 测试会话管理。
- CSV 导出。

服务端不转发音视频媒体。

### 3.3 浏览器承担实验逻辑

浏览器端负责：

- `getUserMedia()`。
- `RTCPeerConnection`。
- Offer / Answer / ICE Candidate。
- `getStats()`。
- NACK SDP 处理。
- sender 参数设置。
- 简化 ABR。
- 页面日志、事件时间线和测试钩子。

### 3.4 状态默认内存化

房间、信令队列、stats 历史和测试会话首版都使用进程内存。

这样做的目的不是架构最优，而是降低开发复杂度，让 WebRTC 学习闭环优先跑通。

### 3.5 测试围绕实验可复现

测试目标不是覆盖所有抽象，而是保证关键实验链路可复现：

- 加入房间。
- 定向信令。
- P2P 建联流程。
- stats 按 peer 隔离。
- Dashboard 缺数据时降级。
- 测试会话 CSV 导出。

## 4. 总体架构

```text
Browser A ---- P2P Media ---- Browser B
    |                              |
    |                              |
    +------ HTTPS Signaling -------+

Browser Page
  -> getUserMedia / RTCPeerConnection
  -> getStats / NACK / ABR / test session
  -> HTTPS signaling + stats upload

WebRTC Signaling Server
  -> room membership
  -> directed signaling
  -> stats ingest
  -> test session
  -> CSV export

Dashboard Server
  -> poll WebRTC stats APIs
  -> render realtime metrics
  -> generate charts
  -> compare CSV files

Automation Runner
  -> read task contracts
  -> validate policies
  -> generate plan / patch / report
  -> run required checks
```

## 5. 推荐仓库结构

```text
rtc_training/
├── src/
│   ├── webrtc/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── app.py
│   │   ├── chat_server.py
│   │   ├── mesh_handlers.py
│   │   ├── stats_handlers.py
│   │   ├── stats_store.py
│   │   ├── test_session_store.py
│   │   ├── experiment_profiles.py
│   │   ├── csv_compare.py
│   │   ├── report_generator.py
│   │   ├── ui_handlers.py
│   │   ├── chat_real.html
│   │   └── static/
│   │       ├── chat_real_shared.js
│   │       ├── chat_real_session.js
│   │       ├── chat_real_stats.js
│   │       ├── chat_real_bitrate.js
│   │       ├── chat_real_test_session.js
│   │       ├── chat_real_timeline.js
│   │       ├── chat_real_sdp.js
│   │       ├── chat_real_ice.js
│   │       ├── chat_real_topology.js
│   │       ├── chat_real_diagnostics.js
│   │       └── chat_real_bootstrap.js
│   └── dashboard/
│       ├── __init__.py
│       ├── server.py
│       ├── chart_generator.py
│       └── templates/
│           └── index.html
├── tests/
│   ├── test_mesh_signaling.py
│   ├── test_mesh_room_lifecycle.py
│   ├── test_dashboard.py
│   ├── test_dashboard_realtime.py
│   ├── test_dashboard_playwright.py
│   ├── test_mesh_playwright.py
│   ├── test_webrtc_test_session_playwright.py
│   ├── test_rtcp_analysis.py
│   └── test_unit.py
├── automation/
├── docs/
├── scripts/
├── data/
│   ├── charts/
│   ├── exports/
│   ├── test_sessions/
│   └── rtcp_stats/
├── requirements.txt
├── Makefile
├── cert.pem
└── key.pem
```

## 6. 技术栈

### 6.1 后端

- Python 3.9+
- `aiohttp`
- `pytest`
- `pytest-asyncio`
- `matplotlib`
- 标准库：`asyncio`、`csv`、`json`、`pathlib`、`dataclasses`、`time`

### 6.2 前端

- 原生 HTML / CSS / JavaScript。
- WebRTC API。
- `RTCPeerConnection`。
- `getUserMedia()`。
- `getStats()`.
- `fetch` HTTP 轮询。

### 6.3 浏览器自动化测试

- Playwright。
- pytest 集成。
- 首版只覆盖桌面 Chrome。
- 对自签名 HTTPS 使用 `ignore_https_errors`，不要求 Playwright 预先信任本地证书。

### 6.4 自动化开发 Runner

- Python CLI。
- JSON 任务契约。
- 策略引擎。
- unified diff。
- git worktree。
- stub 模型网关优先。
- 真实模型后续接入。

## 7. 开发路线总览

开发应按 5 个阶段推进。

```text
阶段 0：项目骨架和运行环境
阶段 1：双人 P2P 最小闭环
阶段 2：stats 与 Dashboard 可观察化
阶段 3：Mesh、NACK、ABR、测试会话
阶段 4：测试体系和文档收口
阶段 5：闭环开发智能体
```

其中阶段 1 到阶段 3 是 RTCTraining 主系统，阶段 5 是用于持续开发主系统的工程化辅助能力。

### 7.1 最终决策项

以下决策已经确认，进入实现计划时必须遵守：

1. `stats` 和测试会话数据必须严格按 `room_id / test_session_id / peer_id / remote_peer_id` 隔离。
2. NACK / ABR 首版只作为手工实验门禁；增强版再进入自动回归门禁。

## 8. 阶段 0：项目骨架和运行环境

### 8.1 目标

建立可运行的 Python Web 项目骨架，生成自签名 HTTPS 证书，准备基础 Makefile 和目录。

### 8.2 交付物

```text
src/webrtc/config.py
src/webrtc/app.py
src/webrtc/chat_server.py
src/webrtc/ui_handlers.py
src/webrtc/chat_real.html
requirements.txt
Makefile
cert.pem
key.pem
```

### 8.3 配置项

`src/webrtc/config.py` 应包含：

```python
DEFAULT_WEBRTC_HOST = "0.0.0.0"
DEFAULT_WEBRTC_PORT = 8080
DEFAULT_DASHBOARD_PORT = 8081

# 本机模式
DEFAULT_LOCAL_WEBRTC_ORIGIN = "https://localhost:8080"
DEFAULT_LOCAL_SIGNALING_URL = "https://localhost:8080"

# 局域网模式：运行时应替换为实际 IP 或 hostname
DEFAULT_LAN_WEBRTC_ORIGIN = "https://<lan-host-or-ip>:8080"
DEFAULT_LAN_SIGNALING_URL = "https://<lan-host-or-ip>:8080"

DEFAULT_DASHBOARD_ORIGIN = "http://localhost:8081"

TLS_CERT_PATH = "cert.pem"
TLS_KEY_PATH = "key.pem"

DATA_DIR = "data"
EXPORTS_DIR = "data/exports"
TEST_SESSIONS_DIR = "data/test_sessions"
CHARTS_DIR = "data/charts"
```

局域网模式要求：

- 服务监听 `0.0.0.0`。
- 页面向用户展示本机可用的局域网访问地址。
- 自签名证书必须包含访问所用 IP 或 hostname 的 SAN。
- 如果通过 IP 访问，证书 SAN 必须包含该 IP。
- 如果通过 hostname 访问，证书 SAN 必须包含该 hostname。
- 另一台局域网设备访问前，需要在浏览器中接受或信任该证书。

### 8.4 运行命令

```bash
make run-webrtc
make run-dashboard
```

等价：

```bash
python3 src/webrtc/chat_server.py run
python3 -m src.dashboard.server run
```

服务入口约定：

- WebRTC 实验页：`https://localhost:8080/` 或 `https://<lan-host-or-ip>:8080/`。
- Dashboard：`http://localhost:8081/`，首版按独立进程独立端口实现。
- Dashboard 从 `DEFAULT_LOCAL_SIGNALING_URL` 或 `DEFAULT_LAN_SIGNALING_URL` 指向的 WebRTC 服务拉取 stats。

### 8.5 验收标准

- `https://localhost:8080/` 能打开页面。
- `https://<lan-host-or-ip>:8080/` 能被同一局域网内另一台设备访问。
- 浏览器允许自签名证书后能看到实验页。
- 静态 JS 能被正确加载。
- `http://localhost:8081/` 能打开 Dashboard。
- 服务启动和关闭没有异常。

## 9. 阶段 1：双人 P2P 最小闭环

### 9.1 目标

两个浏览器页面加入同一房间后，通过 HTTP 轮询信令建立 P2P 音视频连接。

### 9.2 后端模块

```text
src/webrtc/chat_server.py
  WebRTCChatServer 主类，持有房间状态和 aiohttp app。

src/webrtc/mesh_handlers.py
  房间加入、离开、成员查询、定向信令。

src/webrtc/ui_handlers.py
  页面入口和静态资源。
```

### 9.3 房间模型

```python
mesh_rooms = {
    "room1": {
        "members": {
            "client_a": {
                "client_id": "client_a",
                "display_name": "Alice",
                "joined_at": 1710000000.0,
                "last_seen": 1710000005.0,
                "active": True
            }
        },
        "pending_messages": {
            "client_a": [],
            "client_b": []
        },
        "last_activity": 1710000005.0,
        "max_members": 3
    }
}
```

### 9.4 信令接口

```text
POST /rooms/join
POST /rooms/leave
GET  /rooms/{roomId}/members
GET  /rooms/members
POST /signal
GET  /signal/pending
```

### 9.5 信令规则

- 默认房间号是 `room1`。
- 房间默认最多 3 人。
- 第一个成员加入后等待。
- 第二个成员加入时，服务端返回 `existingPeers`。
- 旧成员收到服务端生成的 `peer_joined`。
- 离开时其他成员收到服务端生成的 `peer_left`。
- `peer_joined` 和 `peer_left` 不允许普通客户端伪造。
- `offer`、`answer`、`candidate` 必须指定目标成员。
- pending 消息按目标成员隔离。
- `GET /signal/pending` 拉取即消费。

### 9.6 前端模块

```text
chat_real_shared.js
  DOM、状态、日志、时间线、主远端视图。

chat_real_session.js
  加入房间、离开房间、轮询信令、创建 PeerConnection。

chat_real_bootstrap.js
  初始化页面、绑定按钮、暴露测试钩子。
```

### 9.7 页面最小能力

- 输入 room id。
- 输入 display name。
- 启动本地媒体。
- 加入房间。
- 显示本地视频。
- 显示远端视频。
- 显示连接状态。
- 显示基础日志。
- 离开房间并释放连接。

### 9.8 验收标准

- 两个浏览器能加入同一房间。
- 第二个浏览器能看到第一个成员在 `existingPeers` 中。
- 两边能完成 Offer / Answer / ICE Candidate 流程。
- 音视频媒体走浏览器 P2P，不经过 Python 服务转发。
- 成员离开后另一端收到 `peer_left`。
- 后端测试覆盖房间加入、离开、消息投递和拉取即消费。

## 10. 阶段 2：stats 与 Dashboard 可观察化

### 10.1 目标

浏览器周期性调用 `getStats()`，服务端缓存 stats，Dashboard 实时展示 RTT、loss、jitter、bitrate、health 等指标。

### 10.2 后端模块

```text
src/webrtc/stats_store.py
  内存 stats 存储。

src/webrtc/stats_handlers.py
  stats 接收、查询、导出接口。

src/dashboard/server.py
  Dashboard 服务。

src/dashboard/chart_generator.py
  matplotlib 图表生成。

src/dashboard/templates/index.html
  Dashboard 页面模板。
```

### 10.3 StatsStore 设计

```python
class StatsStore:
    def add_sample(
        self,
        room_id: str,
        peer_id: str,
        remote_peer_id: str,
        sample: dict,
        test_session_id: str | None = None,
    ) -> None:
        ...

    def get_latest(
        self,
        room_id: str | None = None,
        peer_id: str | None = None,
        remote_peer_id: str | None = None,
        test_session_id: str | None = None,
    ) -> dict:
        ...

    def get_history(
        self,
        room_id: str | None = None,
        peer_id: str | None = None,
        remote_peer_id: str | None = None,
        test_session_id: str | None = None,
    ) -> list[dict]:
        ...

    def get_peers(self, room_id: str | None = None) -> list[str]:
        ...

    def export_csv(
        self,
        room_id: str | None = None,
        test_session_id: str | None = None,
    ) -> str:
        ...

    def clear(self) -> None:
        ...
```

内部数据：

```text
_stats_history
_room_histories
_peer_histories
_session_histories
_latest_peer_id
_connection_active
_last_update
```

主 key 规则：

```text
live_key = (room_id, peer_id, remote_peer_id)
session_key = (test_session_id, room_id, peer_id, remote_peer_id)
```

约束：

- `peer_id` 永远表示本端。
- `remote_peer_id` 永远表示该条 PeerConnection 的对端。
- live history 用 `live_key` 隔离。
- test session history 用 `session_key` 隔离。
- `test_session_id` 为空的样本不能写入 session history。
- 查询 session history 时不能从 live history 反推。

默认历史上限：

```text
MAX_HISTORY = 300
```

数据隔离要求：

- 每条样本必须包含 `room_id`、`peer_id`、`remote_peer_id`。
- 测试会话运行期间，每条样本还必须包含 `test_session_id`。
- Dashboard 查询实时数据时必须显式传入 `room_id`，不能默认混合所有房间。
- 测试会话导出 CSV 时必须按 `test_session_id` 截取样本，不能从全局历史池直接导出。
- `StatsStore` 负责实时样本和短期历史；`TestSessionStore` 负责测试会话元数据、会话状态和会话级导出。

### 10.4 stats 样本格式

```json
{
  "timestamp": 1710000000.123,
  "room_id": "room1",
  "test_session_id": "session_20260421_150000",
  "peer_id": "client_a",
  "remote_peer_id": "client_b",
  "connection_state": "connected",
  "ice_state": "connected",
  "rtt_ms": 42.5,
  "packet_loss": 0.02,
  "jitter_ms": 8.1,
  "bitrate_kbps": 1200,
  "frames_per_second": 30,
  "resolution": "1280x720",
  "codec": "VP8",
  "nack_count": 12,
  "pli_count": 1,
  "fir_count": 0,
  "frames_dropped": 3,
  "freeze_count": 0,
  "nack_enabled": true,
  "abr_mode": "manual",
  "health_score": 0.91
}
```

### 10.5 stats 接口

```text
POST /stats
GET  /stats
GET  /stats/history
GET  /stats/peers
GET  /stats/export.csv
POST /clear_stats
```

### 10.6 前端 stats 模块

```text
chat_real_stats.js
```

职责：

- 遍历每个 `RTCPeerConnection.getStats()`。
- 兼容不同浏览器 report 字段。
- 识别 candidate-pair RTT。
- 提取 inbound / outbound 音视频指标。
- 计算 outbound bitrate delta。
- 为每个远端生成一份 stats payload。
- 周期性 `POST /stats`。

### 10.7 Dashboard 能力

Dashboard 不是采集源，只是展示层。

它需要：

- 轮询 `/stats`、`/stats/history`、`/stats/peers`。
- 展示当前最新样本。
- 按 peer 切换历史。
- 展示 RTT / loss / jitter / bitrate / health。
- 在无数据、缺字段、信令服务不可达时稳定降级。
- 生成静态图表到 `data/charts/`。
- 支持导出 CSV。

### 10.8 健康度公式

首版使用可解释公式：

```text
health =
  0.4 * (1 - packet_loss)
+ 0.3 * (1 / (1 + rtt / 100))
+ 0.3 * (1 / (1 + jitter / 50))
```

要求：

- 输入缺失时使用安全默认值。
- 输出范围归一到 0 到 1。
- 单元测试覆盖边界值。

### 10.9 验收标准

- 浏览器连接后能周期性上报 stats。
- `/stats/history` 能按 peer 返回历史。
- `/stats/peers` 能返回已观察到的 peer 列表。
- Dashboard 在无 stats 时不崩溃。
- Dashboard 能展示至少 RTT、loss、jitter、bitrate、health。
- stats CSV 能导出。

## 11. 阶段 3：Mesh、NACK、ABR、测试会话

### 11.1 目标

在双人 P2P 基础上增强实验能力：支持 3 人 Mesh、NACK A/B、发送端参数设置、简化 ABR、定时测试会话和 CSV 固化。

### 11.2 3 人 Mesh

要求：

- 每个浏览器为每个远端维护一个 `RTCPeerConnection`。
- 本地媒体 track 复用到多个连接。
- 页面显示一个主远端和多个缩略远端。
- 成员离开后自动切换主远端。
- 房间上限默认 3，可配置。

### 11.3 NACK 开关

目标：

- 支持 `enabled / disabled` A/B 对照。
- NACK disabled 时，通过 SDP munging 移除视频 NACK 反馈协商行。
- stats 中记录 `nack_enabled`、`nack_count`、`pli_count`、`fir_count`。

注意：

- 该能力用于学习实验，不承诺跨所有浏览器完全一致。
- 页面必须明确当前 NACK 模式。

### 11.4 发送端参数设置

模块：

```text
chat_real_bitrate.js
```

手动模式支持：

- `maxBitrate`。
- 分辨率缩放。
- 最大帧率。

通过：

```javascript
RTCRtpSender.getParameters()
RTCRtpSender.setParameters()
```

对每个视频 sender 生效。

### 11.5 简化 ABR

ABR 只调节 `maxBitrate`，不联动完整分辨率和帧率策略。

默认参数：

```text
windowSize = 5
badLossThreshold = 0.05
badRttThresholdMs = 250
goodLossThreshold = 0.01
goodRttThresholdMs = 120
decreaseFactor = 0.85
increaseFactor = 1.08
```

行为：

- 最近窗口 loss 或 RTT 差，降低码率。
- 最近窗口 loss 和 RTT 好，谨慎升高码率。
- 每次动作写入页面日志和 stats payload。

### 11.6 测试会话

模块：

```text
src/webrtc/test_session_store.py
chat_real_test_session.js
```

生命周期：

```text
POST /stats/test/start
  -> 创建 session
  -> 返回 test_session_id

后续 POST /stats
  -> 携带 test_session_id
  -> 服务端把样本追加到该 session

POST /stats/test/finish
  -> 导出 CSV
  -> 返回 output_path

POST /stats/test/cancel
  -> 丢弃 session
```

### 11.7 测试会话元数据

```json
{
  "session_id": "session_20260421_150000",
  "profile": "weak-network",
  "duration_sec": 60,
  "note": "nack-off-720p",
  "nack_mode": "disabled",
  "nack_enabled": false,
  "role": "caller",
  "started_at": "2026-04-21T15:00:00+08:00",
  "expected_end_at": "2026-04-21T15:01:00+08:00",
  "status": "running",
  "sample_count": 0,
  "output_path": null
}
```

### 11.8 CSV 导出

目录：

```text
data/test_sessions/
```

字段前缀固定：

```text
sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,
rtt_ms,packet_loss,jitter_ms,bitrate_kbps,frames_per_second,
resolution,nack_enabled,abr_mode,health_score
```

要求：

- 允许 0 样本导出，只输出表头。
- 文件名应包含 profile、nack_mode、duration、timestamp、note。
- 测试会话必须复用实时 stats，不单独采第二套 stats。
- 测试会话 CSV 必须只包含同一个 `test_session_id` 对应的样本。
- 多房间并行或连续实验时，CSV 不允许混入其他 `room_id` 的样本。

### 11.9 验收标准

- 3 个浏览器最多形成 Mesh 连接。
- 页面能切换主远端和缩略远端。
- NACK on/off 状态能进入 stats。
- 手动 bitrate 设置能反映到 sender parameters。
- ABR 能根据窗口指标调整 `maxBitrate`。
- 测试会话能 start / finish / cancel。
- finish 后能生成 CSV。

## 12. 阶段 4：测试体系和文档收口

### 12.1 测试分层

```text
后端单元测试
  -> StatsStore、TestSessionStore、health score

后端接口测试
  -> rooms、signal、stats、test session

Dashboard 测试
  -> 空数据、缺字段、信令不可达、图表生成

Playwright 测试
  -> 浏览器加入房间、连接状态、测试会话、页面测试钩子

手工实验
  -> 本机双浏览器、局域网两设备、弱网、NACK A/B、ABR、CSV 对比
```

NACK / ABR 测试门禁策略：

- 首版不要求 NACK / ABR 进入浏览器自动回归门禁。
- 首版必须提供手工实验步骤和记录模板，用于验证 NACK on/off 与 ABR 行为。
- 增强版开始，NACK / ABR 需要进入自动回归门禁。
- 增强版自动门禁至少覆盖：NACK 模式状态字段、SDP munging 结果、ABR 纯函数决策、`maxBitrate` 参数更新、CSV schema 中的 `nack_enabled` 与 `abr_mode` 字段。

### 12.2 推荐测试文件

```text
tests/test_mesh_signaling.py
tests/test_mesh_room_lifecycle.py
tests/test_unit.py
tests/test_dashboard.py
tests/test_dashboard_realtime.py
tests/test_dashboard_playwright.py
tests/test_mesh_playwright.py
tests/test_webrtc_test_session_playwright.py
tests/test_rtcp_analysis.py
```

### 12.3 最小必要回归策略

```text
改信令：
  pytest tests/test_mesh_signaling.py
  pytest tests/test_mesh_room_lifecycle.py

改 stats：
  pytest tests/test_unit.py
  pytest tests/test_rtcp_analysis.py

改 Dashboard：
  pytest tests/test_dashboard.py
  pytest tests/test_dashboard_realtime.py

改前端主流程：
  pytest tests/test_mesh_playwright.py
  pytest tests/test_webrtc_test_session_playwright.py
```

### 12.4 必保测试点

- 第 2 个成员加入时拿到 `existingPeers`。
- `peer_joined` / `peer_left` 投递正确。
- 房间上限限制为 3。
- 定向消息只投给目标成员。
- pending 消息拉取即消费。
- stats 历史按 peer 隔离。
- Dashboard 缺字段和无数据时稳定降级。
- 测试会话能正常导出 CSV。
- 前端暴露最小测试钩子。

### 12.5 文档收口

建议保留这些文档：

```text
docs/RTCTraining_项目开发文档.md
  主开发文档。

docs/API.md
  HTTP API 说明。

docs/TESTING.md
  测试运行和手工实验说明。

docs/EXPERIMENTS.md
  NACK、ABR、弱网实验说明。

docs/AUTOMATION.md
  闭环开发智能体说明。
```

`RTCTraining_整理版.md` 可以作为历史整理稿保留，但后续开发应以 `docs/RTCTraining_项目开发文档.md` 为主。

## 13. 阶段 5：闭环开发智能体

### 13.1 定位

闭环开发智能体不是 RTCTraining 主功能。它是用于开发 RTCTraining 的工程化辅助系统。

正确关系是：

```text
RTCTraining WebRTC 实验平台是目标系统
Automation Runner 是开发目标系统的辅助执行器
```

因此它应在主系统的核心闭环已经稳定后引入，不应抢在 WebRTC、stats、Dashboard 之前成为主线。

### 13.2 使用场景

适合交给闭环开发智能体的任务：

- 补充低风险单元测试。
- 修复 Dashboard 空数据降级。
- 增加 stats 字段清洗。
- 改文档。
- 增加小型 API 响应字段。
- 为已有行为补回归测试。

不适合首版交给智能体的任务：

- 大规模前端状态机重写。
- WebRTC 协商核心逻辑重构。
- 浏览器兼容性复杂问题。
- 安全策略修改。
- 删除历史数据或实验产物。

### 13.3 Automation Runner 结构

```text
automation/
├── config/
│   ├── policy.json
│   └── runtime.json
├── prompts/
├── runner/
│   ├── task_loader.py
│   ├── policies.py
│   ├── model_gateway.py
│   ├── planner.py
│   ├── developer.py
│   ├── diff_validator.py
│   ├── test_selector.py
│   ├── test_runner.py
│   ├── failure_analyzer.py
│   ├── reviewer.py
│   ├── artifact_store.py
│   └── orchestrator.py
├── tasks/
│   ├── ready/
│   ├── running/
│   ├── done/
│   ├── failed/
│   └── blocked/
└── artifacts/
    ├── approvals/
    ├── plans/
    ├── patches/
    ├── reports/
    ├── test-runs/
    └── transcripts/
```

### 13.4 任务契约示例

```json
{
  "id": "add-stats-history-api",
  "goal": "实现 /stats/history 接口并补充测试。",
  "context_files": [
    "src/webrtc/stats_handlers.py",
    "src/webrtc/stats_store.py",
    "tests/test_unit.py"
  ],
  "allowed_paths": [
    "src/webrtc/stats_handlers.py",
    "src/webrtc/stats_store.py",
    "tests/test_unit.py"
  ],
  "forbidden_paths": [
    "data/**",
    "cert.pem",
    "key.pem",
    ".env",
    ".venv/**"
  ],
  "acceptance": [
    "/stats/history 返回历史样本。",
    "按 peer_id 查询时只返回对应 peer 的历史。",
    "空历史时返回空数组。",
    "相关 pytest 通过。"
  ],
  "required_checks": [
    "pytest tests/test_unit.py"
  ],
  "risk_level": "low",
  "mode": "worktree"
}
```

### 13.5 智能体闭环

```text
读取任务契约
  -> 校验路径和命令策略
  -> 创建 worktree 或使用 patch-only 工作区
  -> 读取上下文
  -> 生成计划
  -> 生成 diff
  -> 校验 diff
  -> 应用 patch
  -> 运行 required checks
  -> 如果失败则分析并有限修复
  -> 生成报告和 patch
  -> 人工 review
```

### 13.6 成功标准

任务只有在以下条件满足时才能标记 done：

- patch 只修改 allowed_paths。
- 没有触碰 forbidden_paths。
- required checks 全部通过。
- acceptance 在报告中逐条勾选。
- patch、测试日志、transcript、报告全部落盘。
- 合并动作仍由人决定。

### 13.7 当前实现状态

截至 2026-04-22，`automation/` 已落地首版可验证闭环：

- 首版使用 `patch-only` 模式；当前目录尚不是 git 仓库，因此暂不启用 worktree。
- 首版模型网关是 `stub`，从任务契约的 `stub_patch` 字段读取 unified diff，后续再接真实模型。
- 已实现任务状态：`ready`、`running`、`done`、`failed`、`blocked`。
- 已实现审批 gate：中高风险任务、越权命令、越权路径、过大 patch、修改文件过多都会阻塞。
- 已实现 CLI：

```bash
.venv/bin/python -m automation.runner.orchestrator run-once
.venv/bin/python -m automation.runner.orchestrator run-continuous --max-tasks 3 --poll-interval-seconds 0
```

详细说明见：

```text
docs/automation/RTCTraining_内部自主开发Agent.md
```

## 14. HTTP API 总览

### 14.1 页面接口

```text
GET /
GET /static/webrtc/{filename}
```

### 14.2 房间与信令

```text
POST /rooms/join
POST /rooms/leave
GET  /rooms/{roomId}/members
GET  /rooms/members
POST /signal
GET  /signal/pending
```

### 14.3 stats 与实验

```text
POST /stats
GET  /stats
GET  /stats/history
GET  /stats/peers
GET  /stats/export.csv
POST /clear_stats
POST /stats/test/start
POST /stats/test/finish
POST /stats/test/cancel
```

### 14.4 Dashboard

Dashboard 首版采用独立进程、独立端口。它可以直接渲染 HTML，也可以提供轻量 API。

默认访问地址：

```text
http://localhost:8081/
```

Dashboard 路由：

```text
GET /
GET /api/realtime
GET /api/history
GET /api/peers
GET /api/charts
POST /api/csv/compare
```

路由边界：

- WebRTC 服务的 `GET /` 永远是实验页。
- Dashboard 服务的 `GET /` 永远是观察和分析面板。
- 两者不共用端口，不在同一个 aiohttp app 中挂载。
- Dashboard 只通过 WebRTC 服务的 stats/test session API 获取实验数据，不直接访问 WebRTC 服务的进程内对象。

首版可不追求 API 纯净，但必须保证 Dashboard 对主 WebRTC 服务的 stats API 依赖清晰。

## 15. Web 页面设计

### 15.1 WebRTC 实验页

页面目标：

- 快速启动本地媒体。
- 加入房间。
- 观察连接状态。
- 手动控制实验参数。
- 查看 stats 摘要和日志。
- 启动测试会话。

页面布局：

```text
顶部栏
  房间号、昵称、加入/离开、连接状态

视频区
  本地视频
  主远端视频
  远端缩略区

实验控制区
  NACK 开关
  bitrate 设置
  分辨率缩放
  fps 设置
  ABR 模式

stats 区
  RTT
  loss
  jitter
  bitrate
  health

测试会话区
  profile
  duration
  note
  start / finish / cancel
  CSV 下载结果

日志区
  事件时间线
  信令日志
  stats 日志
```

### 15.2 Dashboard 页面

页面目标：

- 实时展示当前实验质量。
- 支持按 peer 切换。
- 支持图表查看。
- 支持 CSV 导出和多 CSV 并列/叠加分析。

页面布局：

```text
顶部状态
  WebRTC 服务状态
  当前 peers
  当前测试会话
  最近刷新时间

左侧 peer 列表
  peer_id
  latest health
  active / inactive

主区域
  指标卡片
  RTT 图
  loss 图
  jitter 图
  bitrate 图
  health 图

底部工具
  导出 CSV
  选择多个 CSV 对比
  实验备注
```

CSV 对比工作流：

1. 用户在 Dashboard 中选择或上传多个测试会话 CSV。
2. 页面解析每个 CSV 的 session 元数据和指标字段。
3. 用户选择要叠加的指标：RTT、loss、jitter、bitrate、health。
4. 图表按相对时间轴叠加展示多条曲线。
5. 表格并列展示每个 CSV 的样本数、平均值、最大值、最小值和缺失字段。
6. 字段不一致时不阻塞展示，但必须在页面标记缺失字段。

多 CSV 对比首版不要求复杂统计检验，只要求能帮助用户直接观察不同实验会话的趋势差异。

设计原则：

- 信息密度高，便于工程观察。
- 不做营销页。
- 状态色克制：绿色健康、黄色警告、红色异常。
- 表格和图表优先。
- 无数据时明确显示空状态，不抛异常。

## 16. 数据目录约定

```text
data/charts/
  Dashboard 生成图表。

data/exports/
  stats 历史导出。

data/test_sessions/
  测试会话 CSV。

data/rtcp_stats/
  RTCP 或历史实验产物。

automation/artifacts/
  自动化开发智能体产物。
```

规则：

- `data/` 是实验产物目录。
- `automation/artifacts/` 是自动开发产物目录。
- 两者不要混放。
- 自动化 runner 默认不修改 `data/`。

## 17. 最小可用版本定义

MVP 必须具备：

- HTTPS 本地服务。
- 一个 WebRTC 实验页。
- 双浏览器 P2P 音视频连接。
- 房间加入和离开。
- HTTP 轮询定向信令。
- 基础 `getStats()` 上报。
- StatsStore 内存历史。
- Dashboard 空数据和实时数据展示。
- stats CSV 导出。
- 后端关键测试。
- 桌面 Chrome 手工验证通过。
- Playwright 测试在 `ignore_https_errors` 下能访问自签名 HTTPS 页面。
- 局域网内另一台设备能通过 IP 或 hostname 打开 WebRTC 实验页。

MVP 不要求：

- 3 人 Mesh。
- NACK A/B。
- ABR。
- 测试会话。
- Playwright 全流程。
- 自动化开发智能体。
- Dashboard 多 CSV 叠加分析。

## 18. 增强版本定义

增强版应具备：

- 3 人 Mesh。
- 主远端和缩略区。
- 建联状态时间线。
- SDP 查看和 NACK on/off 差异对比。
- ICE Candidate 和 selected candidate pair 可视化。
- Mesh 拓扑图。
- NACK enabled / disabled。
- sender 参数设置。
- 简化 ABR。
- 测试会话 preset。
- 弱网条件记录。
- 测试会话 start / finish / cancel。
- 测试会话 CSV 导出。
- Dashboard 多 CSV 对比和指标解释。
- Markdown 实验报告导出。
- 故障注入和诊断面板。
- 学习任务文档或页面内任务模式。
- Playwright 浏览器流程测试。
- automation runner 低风险任务闭环。

## 19. 开发任务拆分建议

建议按以下任务拆分开发。

### 19.1 基础服务

1. 创建项目骨架。
2. 实现配置和目录初始化。
3. 实现 HTTPS aiohttp 服务。
4. 实现页面入口和静态文件。

### 19.2 信令和房间

1. 实现 `POST /rooms/join`。
2. 实现 `POST /rooms/leave`。
3. 实现成员查询。
4. 实现 `POST /signal`。
5. 实现 `GET /signal/pending`。
6. 实现成员超时清理。
7. 补房间和信令测试。

### 19.3 前端 P2P

1. 实现本地媒体采集。
2. 实现加入房间。
3. 实现信令轮询。
4. 实现 PeerConnection 管理。
5. 实现 Offer / Answer / Candidate。
6. 实现离开和资源释放。
7. 暴露 Playwright 测试钩子。

### 19.4 stats

1. 实现 StatsStore。
2. 实现 stats handlers。
3. 实现前端 getStats 采集。
4. 实现 health score。
5. 实现 CSV 导出。
6. 补 stats 单元测试。

### 19.5 Dashboard

1. 实现 Dashboard 服务。
2. 拉取 WebRTC stats API。
3. 实现模板页面。
4. 实现图表生成。
5. 实现无数据降级。
6. 补 Dashboard 测试。

### 19.6 实验能力

1. 实现 3 人 Mesh。
2. 实现 NACK 开关。
3. 实现 sender bitrate 控制。
4. 实现 ABR。
5. 实现测试会话。
6. 实现测试会话 CSV。
7. 实现测试会话 preset。
8. 实现弱网条件记录。
9. 实现 Markdown 实验报告导出。
10. 补 Playwright 测试。

### 19.7 学习可视化与诊断

1. 实现建联状态时间线。
2. 实现 SDP 查看和关键字段高亮。
3. 实现 NACK on/off SDP 差异对比。
4. 实现 ICE Candidate 可视化。
5. 实现 selected candidate pair 展示。
6. 实现 Mesh 拓扑图。
7. 实现 RTC 指标解释 tooltip。
8. 实现故障注入按钮。
9. 实现诊断面板。
10. 编写学习任务文档。

### 19.8 自动化开发智能体

1. 实现任务契约。
2. 实现策略引擎。
3. 实现 stub 模型网关。
4. 实现 diff 校验。
5. 实现测试执行。
6. 实现失败修复循环。
7. 实现报告和产物。
8. 接入低风险开发任务。

## 20. HTTP API 详细协议

本节定义首版开发必须遵守的 HTTP 协议契约。后续可以拆分到 `docs/API.md`，但实现前必须先按本节对齐。

### 20.1 通用约定

所有 JSON API 默认使用：

```text
Content-Type: application/json
```

成功响应统一包含：

```json
{
  "ok": true,
  "data": {}
}
```

失败响应统一包含：

```json
{
  "ok": false,
  "error": {
    "code": "bad_request",
    "message": "human readable error",
    "details": {}
  }
}
```

错误码约定：

```text
bad_request       请求字段缺失或类型错误
not_found         room、peer、session 或文件不存在
room_full         房间人数超过上限
conflict          重复加入、重复开始 session 等状态冲突
invalid_state     当前状态不允许该操作
service_unready   Dashboard 无法访问 WebRTC 服务
internal_error    未预期异常
```

命名约定：

- HTTP path 中使用 `roomId`。
- JSON 字段统一使用 snake_case，例如 `room_id`、`client_id`、`remote_peer_id`。
- `client_id` 由浏览器生成并持久保存在当前页面生命周期内。
- `peer_id` 等同于本端 `client_id`。
- `remote_peer_id` 表示某条 P2P 连接的对端。
- 时间戳首版使用 Unix 秒浮点数；报告和 metadata 可附加 ISO 8601 字符串。

### 20.2 房间接口

#### POST /rooms/join

请求：

```json
{
  "room_id": "room1",
  "client_id": "client_a",
  "display_name": "Alice"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "client_id": "client_a",
    "joined_at": 1710000000.123,
    "max_members": 3,
    "existing_peers": [
      {
        "client_id": "client_b",
        "display_name": "Bob",
        "joined_at": 1710000000.0,
        "active": true
      }
    ]
  }
}
```

规则：

- `room_id` 为空时使用 `room1`。
- `client_id` 为空时返回 `bad_request`，服务端不替浏览器生成。
- 同一个 `client_id` 重复加入同一房间时，首版按幂等处理，刷新 `last_seen` 并返回当前房间状态。
- 房间已满时返回 `room_full`。
- 加入成功后，服务端向已有成员的 pending 队列写入 `peer_joined` 系统消息。

#### POST /rooms/leave

请求：

```json
{
  "room_id": "room1",
  "client_id": "client_a"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "client_id": "client_a",
    "left_at": 1710000060.0
  }
}
```

规则：

- 成员不存在时返回 `not_found`。
- 离开成功后，服务端向其他成员写入 `peer_left` 系统消息。
- 服务端应清理该成员 pending 队列。

#### GET /rooms/{roomId}/members

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "members": [
      {
        "client_id": "client_a",
        "display_name": "Alice",
        "joined_at": 1710000000.0,
        "last_seen": 1710000005.0,
        "active": true
      }
    ]
  }
}
```

#### GET /rooms/members

首版仅用于调试，返回所有房间成员快照。Dashboard 不依赖该接口。

### 20.3 信令接口

#### POST /signal

请求：

```json
{
  "room_id": "room1",
  "from_peer_id": "client_a",
  "to_peer_id": "client_b",
  "type": "offer",
  "payload": {
    "sdp": "v=0..."
  },
  "created_at": 1710000001.0
}
```

支持的客户端消息类型：

```text
offer
answer
candidate
renegotiate
```

响应：

```json
{
  "ok": true,
  "data": {
    "queued": true,
    "room_id": "room1",
    "to_peer_id": "client_b",
    "message_id": "msg_1710000001000_client_a_client_b"
  }
}
```

规则：

- `peer_joined` 和 `peer_left` 只能由服务端生成，客户端提交这两类消息时返回 `bad_request`。
- `offer`、`answer`、`candidate` 必须指定 `to_peer_id`。
- `from_peer_id` 和 `to_peer_id` 必须属于同一房间。
- pending 消息只写入目标成员队列。

#### GET /signal/pending

查询参数：

```text
room_id=room1
client_id=client_a
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "client_id": "client_a",
    "messages": [
      {
        "message_id": "msg_1710000001000_client_b_client_a",
        "type": "offer",
        "from_peer_id": "client_b",
        "to_peer_id": "client_a",
        "payload": {
          "sdp": "v=0..."
        },
        "created_at": 1710000001.0
      }
    ]
  }
}
```

规则：

- 拉取成功后立即消费消息。
- 没有消息时返回空数组，不返回错误。
- 服务端系统消息 `peer_joined` 的 payload 包含新成员信息。
- 服务端系统消息 `peer_left` 的 payload 包含离开成员信息。

### 20.4 Stats 接口

#### POST /stats

请求：

```json
{
  "room_id": "room1",
  "test_session_id": "session_20260421_150000",
  "peer_id": "client_a",
  "remote_peer_id": "client_b",
  "timestamp": 1710000000.123,
  "connection_state": "connected",
  "ice_state": "connected",
  "rtt_ms": 42.5,
  "packet_loss": 0.02,
  "jitter_ms": 8.1,
  "bitrate_kbps": 1200,
  "frames_per_second": 30,
  "resolution": "1280x720",
  "codec": "VP8",
  "nack_count": 12,
  "pli_count": 1,
  "fir_count": 0,
  "frames_dropped": 3,
  "freeze_count": 0,
  "nack_enabled": true,
  "abr_mode": "manual",
  "health_score": 0.91
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "accepted": true,
    "room_id": "room1",
    "peer_id": "client_a",
    "remote_peer_id": "client_b",
    "test_session_id": "session_20260421_150000"
  }
}
```

规则：

- `room_id`、`peer_id`、`remote_peer_id` 必填。
- `test_session_id` 可为空；为空时只进入 live history。
- 如果提供 `test_session_id`，样本必须同时进入 live history 和对应 session history。
- 服务端允许缺失单个指标字段，但不允许缺失维度字段。
- 服务端负责补充或重算 `health_score`，不能完全信任浏览器上传值。

#### GET /stats

查询参数：

```text
room_id=room1
peer_id=client_a
remote_peer_id=client_b
test_session_id=session_20260421_150000
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "latest": [
      {
        "room_id": "room1",
        "peer_id": "client_a",
        "remote_peer_id": "client_b",
        "timestamp": 1710000000.123,
        "rtt_ms": 42.5,
        "packet_loss": 0.02,
        "jitter_ms": 8.1,
        "bitrate_kbps": 1200,
        "health_score": 0.91
      }
    ]
  }
}
```

规则：

- `room_id` 必填。
- `peer_id`、`remote_peer_id`、`test_session_id` 可选。
- 返回值始终是数组，便于 Dashboard 展示多 peer pair。

#### GET /stats/history

查询参数与 `/stats` 一致，额外支持：

```text
limit=300
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "history": [
      {
        "room_id": "room1",
        "peer_id": "client_a",
        "remote_peer_id": "client_b",
        "timestamp": 1710000000.123,
        "rtt_ms": 42.5,
        "packet_loss": 0.02,
        "jitter_ms": 8.1,
        "bitrate_kbps": 1200,
        "health_score": 0.91
      }
    ]
  }
}
```

规则：

- `room_id` 必填。
- `limit` 默认 300，最大 1000。
- 当指定 `test_session_id` 时，只返回该 session 的样本。

#### GET /stats/peers

查询参数：

```text
room_id=room1
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "peers": [
      {
        "peer_id": "client_a",
        "remote_peer_id": "client_b",
        "last_update": 1710000000.123,
        "active": true
      }
    ]
  }
}
```

#### GET /stats/export.csv

查询参数：

```text
room_id=room1
test_session_id=session_20260421_150000
```

规则：

- `room_id` 必填。
- `test_session_id` 可选；提供时只导出该 session。
- 响应类型为 `text/csv`。

#### POST /clear_stats

请求：

```json
{
  "room_id": "room1"
}
```

规则：

- 只清理 live history。
- 不删除已经 finish 的测试会话 CSV。
- 首版可以要求 `room_id` 必填，避免误清全部数据。

### 20.5 测试会话接口

#### POST /stats/test/start

请求：

```json
{
  "room_id": "room1",
  "owner_peer_id": "client_a",
  "profile": "baseline",
  "duration_sec": 60,
  "note": "baseline-720p",
  "nack_mode": "enabled",
  "nack_enabled": true,
  "abr_mode": "manual",
  "network_profile": {
    "network_type": "wifi",
    "tool": "manual",
    "packet_loss": null,
    "latency_ms": null,
    "bandwidth_kbps": null
  }
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "test_session_id": "session_20260421_150000",
    "room_id": "room1",
    "status": "running",
    "started_at": "2026-04-21T15:00:00+08:00",
    "expected_end_at": "2026-04-21T15:01:00+08:00",
    "sample_count": 0
  }
}
```

规则：

- 同一 `room_id` 首版只允许一个 running session。
- 重复 start 时返回 `conflict`。
- `profile` 必须来自预设列表或为 `custom`。

#### POST /stats/test/finish

请求：

```json
{
  "room_id": "room1",
  "test_session_id": "session_20260421_150000"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "test_session_id": "session_20260421_150000",
    "status": "finished",
    "sample_count": 120,
    "output_path": "data/test_sessions/baseline_enabled_60s_20260421_150000.csv",
    "report_path": "data/test_sessions/baseline_enabled_60s_20260421_150000.md"
  }
}
```

规则：

- 允许 0 样本 finish。
- finish 后不再接收该 session 的样本。
- Markdown report 是增强版能力；首版可返回 `null`。

#### POST /stats/test/cancel

请求：

```json
{
  "room_id": "room1",
  "test_session_id": "session_20260421_150000"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "test_session_id": "session_20260421_150000",
    "status": "cancelled"
  }
}
```

### 20.6 Dashboard API

Dashboard 是独立进程。它的 API 面向 Dashboard 页面，不替代 WebRTC 服务 API。

Dashboard 配置项：

```text
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8081
WEBRTC_API_BASE_URL = "https://localhost:8080"
DASHBOARD_ALLOW_INSECURE_WEBRTC = true
```

首版 Dashboard 后端代理访问 WebRTC API，Dashboard 页面只请求 `http://localhost:8081/api/*`。这样可以避免浏览器跨端口 HTTPS 自签名证书和 CORS 问题。

#### GET /api/realtime

查询参数：

```text
room_id=room1
```

响应：

```json
{
  "ok": true,
  "data": {
    "room_id": "room1",
    "webrtc_service": {
      "base_url": "https://localhost:8080",
      "reachable": true,
      "last_error": null
    },
    "latest": []
  }
}
```

WebRTC 服务不可达时：

```json
{
  "ok": false,
  "error": {
    "code": "service_unready",
    "message": "WebRTC service is unreachable",
    "details": {
      "base_url": "https://localhost:8080"
    }
  }
}
```

#### GET /api/history

查询参数透传到 WebRTC `/stats/history`，Dashboard 负责补充服务状态信息。

#### GET /api/peers

查询参数透传到 WebRTC `/stats/peers`。

#### GET /api/charts

查询参数：

```text
room_id=room1
metric=rtt_ms
peer_id=client_a
remote_peer_id=client_b
```

响应：

```json
{
  "ok": true,
  "data": {
    "chart_path": "data/charts/room1_client_a_client_b_rtt_ms.png",
    "metric": "rtt_ms"
  }
}
```

#### POST /api/csv/compare

首版支持两种输入：

```json
{
  "csv_paths": [
    "data/test_sessions/baseline_enabled_60s_20260421_150000.csv",
    "data/test_sessions/nack_off_60s_20260421_151000.csv"
  ],
  "metrics": ["rtt_ms", "packet_loss", "bitrate_kbps", "health_score"]
}
```

或 multipart upload 多个 CSV 文件。

响应：

```json
{
  "ok": true,
  "data": {
    "metrics": ["rtt_ms", "packet_loss"],
    "series": [
      {
        "name": "baseline_enabled_60s",
        "sample_count": 120,
        "missing_fields": [],
        "summary": {
          "rtt_ms": {
            "avg": 42.5,
            "min": 20.0,
            "max": 120.0
          }
        }
      }
    ]
  }
}
```

规则：

- 字段缺失不阻塞对比，但必须返回 `missing_fields`。
- 时间轴使用相对时间，从每个 CSV 第一条样本归零。
- 首版不做显著性检验。

## 21. 浏览器端状态机与信令时序

### 21.1 页面状态机

浏览器页面状态：

```text
idle
  -> media_requesting
  -> media_ready
  -> joining
  -> joined
  -> negotiating
  -> connected
  -> reconnecting
  -> leaving
  -> left
  -> failed
```

状态含义：

- `idle`：页面已加载，尚未请求摄像头和麦克风。
- `media_requesting`：正在调用 `getUserMedia()`。
- `media_ready`：本地媒体可用，允许加入房间。
- `joining`：正在调用 `/rooms/join`。
- `joined`：已进入房间，但可能尚无远端连接。
- `negotiating`：正在处理 offer / answer / candidate。
- `connected`：至少一条 peer connection 进入 connected 或 completed。
- `reconnecting`：连接中断后等待 ICE 或重新协商。
- `leaving`：正在释放资源并调用 `/rooms/leave`。
- `left`：已经离开房间，本地资源已释放或保持可选。
- `failed`：发生不可自动恢复错误。

按钮状态：

```text
idle:
  start media enabled
  join disabled
  leave disabled

media_ready:
  start media disabled
  join enabled
  leave disabled

joined / negotiating / connected:
  start media disabled
  join disabled
  leave enabled

leaving:
  all primary actions disabled

failed:
  retry enabled
  leave enabled if room joined
```

### 21.2 PeerConnection 状态

每个远端 peer 单独维护：

```text
remote_peer_id
role: offerer | answerer | unknown
pc
pending_remote_candidates
local_description_set
remote_description_set
connection_state
ice_connection_state
selected_candidate_pair
last_stats_at
```

规则：

- 每个 `remote_peer_id` 只允许一个 active `RTCPeerConnection`。
- 收到 `peer_joined` 的旧成员作为 offerer。
- 新加入成员根据 `existing_peers` 为每个已有成员等待 offer，不主动创建 offer。
- 收到 offer 的成员作为 answerer。
- candidate 早于 remote description 到达时，先放入 `pending_remote_candidates`。
- remote description 设置完成后再 drain pending candidates。
- `peer_left` 时关闭对应 pc，移除远端视频和 stats 记录。

### 21.3 双人建联时序

```text
Browser A -> POST /rooms/join
Browser A <- existing_peers: []

Browser B -> POST /rooms/join
Browser B <- existing_peers: [A]
Browser A <- GET /signal/pending: peer_joined(B)

Browser A -> createOffer(B)
Browser A -> setLocalDescription(offer)
Browser A -> POST /signal offer to B

Browser B <- GET /signal/pending: offer(A)
Browser B -> create PeerConnection(A)
Browser B -> setRemoteDescription(offer)
Browser B -> createAnswer()
Browser B -> setLocalDescription(answer)
Browser B -> POST /signal answer to A

Browser A <- GET /signal/pending: answer(B)
Browser A -> setRemoteDescription(answer)

A <-> B exchange candidate through /signal and /signal/pending
A/B -> connected
A/B -> periodic POST /stats
```

### 21.4 三人 Mesh 时序

第三人 C 加入时：

- C 的 `existing_peers` 包含 A 和 B。
- 服务端向 A、B 投递 `peer_joined(C)`。
- A 和 B 分别对 C 创建 offer。
- C 分别对 A、B 创建 answer。
- 最终连接数为 3 条 pair：A-B、A-C、B-C。

### 21.5 离开和异常流程

离开流程：

```text
user clicks leave
  -> stop stats timer
  -> close all PeerConnection
  -> remove remote videos
  -> POST /rooms/leave
  -> stop local tracks
  -> state left
```

异常规则：

- `getUserMedia()` 失败时进入 `failed`，展示浏览器权限错误。
- `/rooms/join` 失败时回到 `media_ready`，展示错误。
- `/signal/pending` 失败时保留当前连接，指数退避重试。
- `connection_state=failed` 时进入 `reconnecting`，首版只记录和展示，不自动重建。
- 页面刷新不保证恢复旧 session，刷新后使用新的 `client_id`。

## 22. 前端模块边界与测试钩子

### 22.1 前端模块边界

推荐前端模块扩展为：

```text
chat_real_shared.js
  全局状态、DOM helper、日志、通用工具。

chat_real_session.js
  房间加入/离开、信令轮询、PeerConnection 生命周期。

chat_real_stats.js
  getStats 采集、指标归一化、stats 上报。

chat_real_bitrate.js
  sender parameters、手动 bitrate、ABR 决策执行。

chat_real_test_session.js
  测试会话 start / finish / cancel、preset、弱网条件记录。

chat_real_timeline.js
  建联状态时间线、事件追加、事件过滤、测试钩子读取。

chat_real_sdp.js
  SDP 保存、展示、关键字段高亮、NACK diff。

chat_real_ice.js
  ICE candidate 记录、selected candidate pair 展示。

chat_real_topology.js
  Mesh peer pair 拓扑数据和视图。

chat_real_diagnostics.js
  故障注入、诊断规则、错误提示。

chat_real_bootstrap.js
  页面初始化、事件绑定、测试钩子挂载。
```

原则：

- `session` 模块不直接渲染复杂面板，只发出状态事件。
- `timeline`、`sdp`、`ice`、`diagnostics` 从状态事件和 WebRTC 对象读取数据。
- `stats` payload 是 Dashboard 和 test session 的统一观测源。
- 新增学习功能优先作为独立模块，不继续膨胀 `shared`。

### 22.2 页面事件格式

时间线事件统一格式：

```json
{
  "event_id": "evt_1710000000000_client_a_client_b_offer_sent",
  "timestamp": 1710000000.0,
  "room_id": "room1",
  "peer_id": "client_a",
  "remote_peer_id": "client_b",
  "category": "signaling",
  "type": "offer_sent",
  "direction": "outbound",
  "summary": "offer sent to client_b",
  "details": {
    "message_id": "msg_1710000000000_client_a_client_b"
  }
}
```

`category` 可选值：

```text
media
room
signaling
peer_connection
ice
sdp
stats
test_session
diagnostics
error
```

### 22.3 Playwright 测试钩子

页面必须暴露：

```javascript
window.__RTCTrainingTestHooks = {
  getState() {},
  getClientId() {},
  getRoomId() {},
  getPeers() {},
  getPeerConnectionState(remotePeerId) {},
  getTimeline() {},
  getLatestStats() {},
  getSdpSnapshots() {},
  getIceCandidates() {},
  getSelectedCandidatePair(remotePeerId) {},
  startMedia() {},
  joinRoom(roomId, displayName) {},
  leaveRoom() {},
  startTestSession(config) {},
  finishTestSession() {},
  injectFault(type, options) {}
}
```

返回值要求：

- 所有 getter 返回可 JSON 序列化对象。
- action 方法返回 Promise。
- 失败时 reject，并写入时间线 `error` 事件。
- 测试钩子只用于本地学习和自动化测试，不作为生产 API。

### 22.4 Playwright 首版策略

Playwright 配置：

```text
browser = chromium
ignore_https_errors = true
permissions = ["camera", "microphone"]
fake_media = true
fake_device = true
```

首版浏览器测试最小流程：

1. 启动 WebRTC HTTPS 服务。
2. 启动两个独立 Chromium context。
3. 两个页面打开 `https://localhost:8080/`。
4. 页面 A、B 调用 `startMedia()`。
5. 页面 A 加入 `room1`。
6. 页面 B 加入 `room1`。
7. 等待双方 timeline 出现 `connected` 或 stats 开始上报。
8. 断言 `/stats/peers` 能看到 A-B pair。
9. 页面 B leave。
10. 页面 A 收到 `peer_left`。

局域网另一台设备访问首版作为手工验收，不纳入 Playwright 自动化。

## 23. Dashboard 数据访问与 CSV 对比协议

### 23.1 Dashboard 数据访问

Dashboard 页面只访问 Dashboard 进程：

```text
Browser Dashboard Page
  -> http://localhost:8081/api/*
  -> Dashboard Server
  -> https://localhost:8080/stats*
```

这样首版不需要浏览器直接跨端口访问 WebRTC HTTPS API，也不需要在 WebRTC 服务上开启 CORS。

Dashboard Server 访问 WebRTC 服务时：

- 使用 `WEBRTC_API_BASE_URL` 配置。
- 开发模式允许跳过本地自签名证书校验。
- 请求超时默认 2 秒。
- 失败时返回 `service_unready`，页面显示空状态和错误摘要。

### 23.2 Dashboard 空状态

Dashboard 必须区分以下状态：

```text
webrtc_unreachable
  WebRTC 服务不可达。

no_room_selected
  尚未选择或输入 room_id。

no_peers
  room 存在，但没有 stats peer pair。

no_history
  peer pair 存在，但没有历史样本。

field_missing
  样本存在，但某些指标字段缺失。
```

空状态不应抛异常，也不应显示假数据。

### 23.3 CSV 对比输入

CSV 对比支持：

1. 选择 `data/test_sessions/` 下已有 CSV。
2. 上传多个本地 CSV。

每个 CSV 必须至少包含：

```text
timestamp
room_id
test_session_id
peer_id
remote_peer_id
```

推荐包含：

```text
rtt_ms
packet_loss
jitter_ms
bitrate_kbps
frames_per_second
health_score
nack_enabled
abr_mode
```

### 23.4 CSV 对比输出

Dashboard 对每个 CSV 生成：

```text
session_name
test_session_id
room_id
peer_pairs
sample_count
time_range_sec
missing_fields
metric_summary
relative_series
```

`relative_series` 使用相对时间轴：

```text
relative_time_sec = sample.timestamp - first_sample.timestamp
```

对比图规则：

- 默认叠加 RTT、packet loss、bitrate、health。
- 用户可以开关单个 metric。
- 不同 CSV 使用不同颜色。
- 缺失字段的曲线不绘制，但表格显示缺失。
- 多 peer pair 时，首版允许用户选择一个 pair；增强版再支持同时展示多 pair。

## 24. UI 状态、空状态和错误状态规范

### 24.1 WebRTC 实验页布局补充

实验页按桌面 Chrome 优先设计，目标宽度：

```text
desktop: 1280px+
minimum supported width: 1024px
```

首屏应同时看到：

- 顶部房间控制。
- 本地视频。
- 主远端视频。
- 连接状态。
- 关键 stats 摘要。

次级信息可以折叠或位于下方：

- SDP 面板。
- ICE 面板。
- 故障诊断。
- 完整日志。

### 24.2 WebRTC 实验页状态

页面必须定义以下视觉状态：

```text
no_media
  未启动本地媒体。

media_ready
  本地摄像头和麦克风可用。

waiting_peer
  已加入房间，等待远端。

connecting
  正在协商或 ICE checking。

connected
  至少一个远端连接可用。

degraded
  已连接，但 health 低于阈值。

disconnected
  曾经连接，但当前断开。

failed
  建联失败或权限失败。
```

状态色：

```text
connected: green
connecting / waiting_peer: yellow
degraded: orange
failed / disconnected: red
idle / no_media: gray
```

颜色只能作为辅助信息，必须同时显示文本状态。

### 24.3 错误提示规则

错误提示分三层：

1. 顶部状态条显示当前最重要错误。
2. 时间线记录完整错误事件。
3. 诊断面板给出可能原因和下一步操作。

常见错误：

```text
camera_permission_denied
microphone_permission_denied
https_required
join_room_failed
room_full
signaling_poll_failed
ice_failed
stats_upload_failed
dashboard_webrtc_unreachable
```

### 24.4 SDP / ICE 面板 UI

SDP 面板：

- 默认折叠。
- 支持按 `local offer`、`remote offer`、`local answer`、`remote answer` 切换。
- 长文本使用等宽字体。
- 高亮 `m=`、`a=rtcp-fb`、`a=mid`、`a=sendrecv`、`a=rtpmap`、`a=candidate`。
- NACK diff 只展示 changed lines 和上下文。

ICE 面板：

- 列表展示本地和远端 candidate。
- 标记 selected candidate pair。
- 显示 ICE state 历史。
- 首版不要求绘制复杂网络图。

### 24.5 Dashboard UI 状态

Dashboard 顶部必须显示：

- WebRTC API base URL。
- WebRTC 服务是否可达。
- 当前 room。
- 最近刷新时间。

指标卡片规则：

- 缺字段显示 `N/A`，不显示 0。
- 超过阈值时改变状态色。
- tooltip 解释指标含义。

图表规则：

- 没有历史时显示空状态。
- 点数少于 2 时显示表格，不强行画线。
- 图表生成失败时显示错误摘要和原始表格。

CSV 对比 UI：

- 支持多选 CSV。
- 显示每个 CSV 的 session 名称、样本数、缺失字段。
- 指标选择使用 checkbox。
- 默认按相对时间叠加。

### 24.6 无障碍和可读性

首版不追求完整 WCAG，但必须满足：

- 所有关键按钮有明确文本。
- 状态不能只依赖颜色。
- 日志和 SDP 使用可复制文本。
- 主要交互不依赖 hover。
- 页面在 1024px 宽度下不出现关键控件重叠。

## 25. 启动开发前检查清单

正式启动开发前，应确认以下内容已经进入文档或 issue：

- HTTP API 请求、响应、错误码已确认。
- 前端状态机和信令时序已确认。
- 前端模块边界和测试钩子已确认。
- Dashboard 代理 WebRTC API 的方式已确认。
- CSV schema 和多 CSV 对比规则已确认。
- UI 空状态、错误状态和指标解释规则已确认。
- MVP 和增强版边界已确认。
- Playwright 首版只覆盖桌面 Chrome，并使用 `ignore_https_errors`。

如果只启动阶段 0 和阶段 1，可以先不实现 Dashboard CSV 对比、NACK、ABR、测试会话和 automation runner，但不能跳过 API 命名、状态机和测试钩子约定。

## 26. 当前文档关系

当前工作区已有：

```text
RTCTraining_整理版.md
  原始整理稿，信息完整，但不完全按开发执行顺序组织。

docs/RTCTraining_项目开发文档.md
  本文档，作为后续开发主文档。

docs/superpowers/specs/2026-04-21-闭环开发智能体-总体设计.md
  automation runner 高层设计。

docs/superpowers/specs/2026-04-21-闭环开发智能体-代码实现与Web设计方案.md
  automation runner 详细设计。
```

后续建议：

- 主系统开发以本文档为准。
- 自动化智能体开发以 `闭环开发智能体` 两份文档为准。
- 如果两者冲突，优先保证 RTCTraining 主系统的开发顺序和边界。

## 27. 结论

RTCTraining 的开发主线应是：

```text
先建立 WebRTC P2P 实验闭环
  -> 再建立 stats 和 Dashboard 观察闭环
  -> 再加入 NACK、ABR、测试会话等实验能力
  -> 再补齐测试和文档
  -> 最后引入闭环开发智能体持续推进低风险任务
```

闭环开发智能体是这个仓库的工程化辅助系统，不是项目的第一目标。它应该服务于 RTCTraining 主系统的开发、测试和维护，而不是取代 WebRTC 实验平台本身。
