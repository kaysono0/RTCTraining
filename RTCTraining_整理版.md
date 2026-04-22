# RTC Training 技术方案总览

本文档目标不是做功能简介，而是把当前仓库收敛成一份可重新开发、可迁移、可交接的技术方案。即使脱离现有代码，只要保留本文档，也应能按同样边界重新实现一套等价系统。

## 1. 项目定位

`rtc_training` 是一个本地/局域网 WebRTC 学习与实验仓库，核心目标是验证和观察以下闭环：

- 双浏览器 P2P 音视频通话
- 局域网 3 人 Mesh 扩展
- 浏览器 `getStats()` 采集与服务端汇总
- NACK `enabled / disabled` A/B 对照
- 发送端参数控制与简化 ABR
- 定时测试会话与 CSV 导出
- Dashboard 实时观察与多 CSV 对比
- 面向夜间执行的自动化任务 runner 原型

该仓库不是公网生产 RTC 服务，不覆盖：

- TURN / SFU / MCU
- 认证鉴权与多租户
- 长期持久化存储
- 录制、屏幕共享、生产级运维
- 公网高可用部署

推荐主路径始终是双人 P2P 弱网实验；3 人 Mesh 是扩展学习路径；`automation/` 是独立的自动开发试验子系统。

## 2. 设计原则

### 2.1 总体原则

- 先跑通学习闭环，再考虑工程扩展
- 服务端只做信令、状态缓存、统计接收，不转发媒体
- 浏览器承担媒体采集、连接协商、stats 采集和实验控制
- 所有状态默认进程内存化，降低实现复杂度
- 测试与文档围绕“实验可复现”，而不是“代码抽象最优”展开

### 2.2 边界原则

- 面向本机和可信局域网，默认 HTTPS 自签名证书
- 不主动修改 `data/` 中的实验产物
- 统计分析只看浏览器与信令侧观测结果，不做抓包级精确还原
- 自动化 runner 默认只允许低风险改动和最小必要验证

## 3. 仓库结构

```text
rtc_training/
├── src/webrtc/                 # WebRTC 实验页、信令服务、stats/test session
├── src/dashboard/              # Dashboard 服务、模板、图表生成
├── tests/                      # 当前主测试目录
├── docs/                       # 架构、测试、API、实验说明
├── scripts/                    # 实验辅助脚本
├── automation/                 # 自动开发 runner MVP
├── docker/                     # automation 相关容器草案
├── deprecated_tests/           # 旧测试
└── archive/                    # 历史记录和旧材料
```

## 4. 子系统总览

当前仓库可以拆成 4 个主要子系统：

1. WebRTC 实验页与浏览器端状态机
2. Python 信令/stats/test session 服务
3. Dashboard 实时观测与 CSV 分析服务
4. Automation Runner 自动开发编排原型

四者关系如下：

```text
Browser Page
  -> getUserMedia / RTCPeerConnection / getStats / ABR / test session UI
  -> HTTPS signaling + stats upload

WebRTC Signaling Server
  -> room membership / directed signaling / stats ingest / CSV export
  -> in-memory room state + in-memory stats state + in-memory test session state

Dashboard Server
  -> poll signaling server stats APIs
  -> render metrics, charts, peer switcher, CSV comparison

Automation Runner
  -> read task contracts from automation/tasks/ready
  -> validate path/command/risk policies
  -> generate plan / patch draft / report artifacts
```

## 5. WebRTC 主系统方案

### 5.1 目标能力

WebRTC 主系统负责提供一个本地可访问的实验页，支持：

- 启动摄像头与麦克风
- 加入房间并建立 P2P 连接
- 多人 Mesh 下维护多条 `RTCPeerConnection`
- 采集浏览器 `getStats()` 并上报服务端
- 切换 NACK 开关
- 手动设置发送端视频参数
- 自动 ABR 根据 RTT/loss 粗调 `maxBitrate`
- 启动/停止定时测试会话
- 提供学习用日志与事件时间线

### 5.2 前后端拓扑

```text
Browser A -- P2P media -- Browser B
     \                         /
      \-- HTTPS signaling ----/

Browser A/B/C -- directed signaling / stats --> Python server
Dashboard -- stats polling -------------------> Python server
```

重点：

- 媒体流是浏览器之间的 P2P
- Python 服务只负责控制面和观测面
- Dashboard 不是采集源，只是 stats 的展示层

### 5.3 运行时组件

#### 浏览器端

位于 `src/webrtc/chat_real.html` 与 `src/webrtc/static/chat_real_*.js`。

职责：

- 管理页面元素与 UI 状态
- 创建/回收 `RTCPeerConnection`
- 处理 Offer / Answer / ICE Candidate
- 维护房间成员、主远端与缩略区
- 周期采集 stats 并向 `/stats` 上报
- 运行实验逻辑：NACK、ABR、测试会话、日志面板、时间线

#### 信令服务

位于 `src/webrtc/chat_server.py`、`src/webrtc/app.py`、`src/webrtc/mesh_handlers.py`、`src/webrtc/stats_handlers.py`。

职责：

- 提供 HTTPS 页面入口和静态资源
- 管理 Mesh 房间成员与超时清理
- 提供定向信令消息队列
- 接收浏览器 stats 上报
- 管理测试会话和 CSV 导出

#### 进程内状态层

位于 `src/webrtc/stats_store.py` 与 `src/webrtc/test_session_store.py`。

职责：

- 保存最近一段 stats 历史
- 按 `peer_id` 维度组织历史窗口
- 维护测试会话元数据和样本缓存
- 在结束时导出 CSV

## 6. 信令与房间模型

### 6.1 房间模型

当前统一采用 Mesh 房间模型，由 `WebRTCChatServer` 维护：

- `mesh_rooms[room_id]`
- 每个房间包含 `members`、`pending_messages`、`last_activity`、`max_members`
- 默认房间号为空时归一为 `room1`
- 默认最多 3 人
- 后台定时清理超时成员

成员对象包含：

- `client_id`
- `display_name`
- `joined_at`
- `last_seen`
- `active`

### 6.2 信令模型

系统不使用 WebSocket，采用 HTTP 轮询方式实现定向信令：

- `POST /signal`：发送消息
- `GET /signal/pending`：拉取并消费消息

当前支持的业务类型：

- `offer`
- `answer`
- `candidate`
- `peer_joined`
- `peer_left`

其中：

- `peer_joined` / `peer_left` 是系统事件，普通客户端不能主动发送
- 待处理消息队列按目标成员分桶存储
- 拉取即消费

### 6.3 加入与离开行为

加入房间时：

- 服务端创建或复用房间
- 返回新 `clientId`
- 返回当前已存在成员列表 `existingPeers`
- 向旧成员队列投递 `peer_joined`

离开房间时：

- 删除成员
- 清理其相关待处理消息
- 向其他成员投递 `peer_left`
- 如果房间空了则删除房间

### 6.4 重新开发时的关键约束

- 房间成员上限需保留为可配置项，默认 3
- 定向消息队列必须按成员隔离
- 轮询接口应保持幂等与收口，避免重复积压
- 成员超时清理必须与房间回收联动

## 7. 前端模块拆分

当前实验页按职责拆成多个模块，重建时建议保留同等分层。

### 7.1 `chat_real_shared.js`

负责共享状态与通用 UI 能力：

- DOM 引用收集
- 全局 `state` 初始化
- per-peer 状态对象 `createPeerState`
- 调试日志缓存与暂停/恢复
- 事件时间线记录与筛选
- 远端主视图和缩略区渲染基础能力

### 7.2 `chat_real_session.js`

负责连接与房间状态机：

- 加入/离开房间
- 发起 Offer、处理 Answer
- ICE candidate 收发
- 创建每个远端成员对应的 `RTCPeerConnection`
- 本地轨道复用到多个连接
- 远端离开后的主画面自动切换
- 可选移除视频 NACK 反馈协商行

### 7.3 `chat_real_stats.js`

负责 stats 采集与上报：

- 遍历 `pc.getStats()`
- 兼容浏览器不同 report 字段
- 提取音视频指标、NACK、PLI、FIR、freeze、codec 等
- 计算 outbound bitrate delta
- 识别候选对和 RTT
- 为每个远端生成一份 stats payload
- POST 到 `/stats`

### 7.4 `chat_real_bitrate.js`

负责发送端参数和简化 ABR：

- 手动模式：从页面选择目标 `maxBitrate`、分辨率缩放、最大帧率
- 自动模式：维护滑动窗口，基于 RTT/loss 判断网络状态
- 自动模式只调节 `maxBitrate`
- 对多个 sender 同步 `setParameters()`

ABR 当前参数大致包括：

- `windowSize = 5`
- `badLossThreshold = 0.05`
- `badRttThresholdMs = 250`
- `goodLossThreshold = 0.01`
- `goodRttThresholdMs = 120`
- `decreaseFactor = 0.85`
- `increaseFactor = 1.08`

### 7.5 `chat_real_test_session.js`

负责定时实验会话：

- 读取 profile、duration、note
- 调用 `/stats/test/start`
- 倒计时
- 将 `test_session_id` 带入后续 stats
- 到期后调用 `/stats/test/finish`

### 7.6 `chat_real_bootstrap.js`

负责装配所有模块并绑定事件：

- 创建 app 对象
- 注册 session / stats / bitrate / test session 模块
- 绑定按钮与输入事件
- 暴露 `window.chatRealApp` 供 Playwright 调试
- 页面卸载时回收连接与媒体

## 8. 实时统计方案

### 8.1 采集来源

统计数据完全来自浏览器 `RTCPeerConnection.getStats()`，不是服务端自行推导。

采集项覆盖：

- 通用网络：RTT、jitter、packet loss、bitrate
- 连接状态：`connection_state`、`ice_state`
- peer 维度：`peer_id`、`peer_label`
- 视频：分辨率、fps、码率、codec、NACK、PLI、FIR、retransmission、freeze、frames dropped
- 音频：码率、codec、采样率、声道、jitter、loss
- ABR 状态：当前模式、平均 RTT/loss、bad/good count、last action
- 发送端参数：configured / applied max bitrate、scale、fps

### 8.2 服务端存储

`StatsStore` 是单例，线程锁保护，核心数据结构：

- `_stats_history`：全局最近历史
- `_peer_histories[bucket]`：按 peer 聚合历史
- `_latest_peer_id`
- `_connection_active`
- `_last_update`

关键行为：

- 每次 `POST /stats` 都写入全局历史与 peer 历史
- 历史上限 `MAX_HISTORY = 300`
- 对异常数值做 `safe_float` / `safe_int` 清洗
- 支持导出当前历史为 CSV

### 8.3 为什么这样设计

原因不是“最优后端设计”，而是为了支持：

- 本地实验时快速接线
- Dashboard 近实时轮询
- 多 peer 切换观察
- 测试会话结束时无缝导出

代价是：

- 进程重启后数据丢失
- 不支持跨进程共享
- 不适合长时间历史分析

如果未来重构为生产版，应把 stats 存储抽成时序数据库或消息流水，但当前训练仓库不需要。

## 9. 测试会话与 CSV 导出方案

### 9.1 设计目标

测试会话的目的不是替代 Dashboard，而是把一次实验过程固化成可比较 CSV 样本。

### 9.2 生命周期

1. 页面调用 `POST /stats/test/start`
2. 服务端创建 `TestSession`
3. 后续 stats 携带 `test_session_id`
4. 服务端边收 stats 边追加到该会话样本
5. 调用 `POST /stats/test/finish`
6. 服务端导出 CSV 到 `data/test_sessions/`

支持取消：`POST /stats/test/cancel`

### 9.3 会话元数据

每个会话包含：

- `session_id`
- `profile`
- `duration_sec`
- `note`
- `nack_mode`
- `nack_enabled`
- `role`
- `started_at`
- `expected_end_at`
- `status`
- `sample_count`
- `output_path`

### 9.4 导出规则

- 目录：`data/test_sessions/`
- 文件名编码 `profile`、`nack_mode`、持续时间、时间戳、备注
- 允许 0 样本导出，仅输出表头，便于审计

### 9.5 重建时的关键要求

- 测试会话必须复用实时 stats 数据，不要单独采第二份
- 样本行需要保留 `sample_index`
- 输出 CSV 字段顺序应固定前缀 + 动态扩展
- 文件名要可读、可比、可筛选

## 10. Dashboard 方案

### 10.1 角色定位

Dashboard 不是主动采集器，而是 stats 展示和对比分析入口。

服务位于 `src/dashboard/server.py`，模板位于 `src/dashboard/templates/index.html`。

### 10.2 核心能力

- 轮询信令服务 `/stats`、`/stats/history`、`/stats/peers`
- 展示当前最新样本
- 按 peer 切换观察对象
- 展示健康度、码率、loss、RTT、jitter 等摘要
- 生成 RTT / loss / jitter / health 静态图表
- 导入并对比多个 CSV 文件

### 10.3 数据获取策略

Dashboard 优先从信令服务取数：

- `_fetch_stats_from_signaling()`
- `_fetch_stats_history_from_signaling()`
- `_fetch_stats_peers_from_signaling()`

如果信令服务不可达，再回退到同进程 `StatsStore`。

这样设计的原因是兼容两种运行方式：

- WebRTC 服务与 Dashboard 分开进程
- 测试中同进程直接注入

### 10.4 图表方案

图表由 `ChartGenerator` 基于 `matplotlib` 生成，输出到 `data/charts/`：

- `rtt.png`
- `loss.png`
- `jitter.png`
- `health.png`
- 可选 `av_sync.png`

Dashboard 后台每 5 秒刷新一次图表。如 `matplotlib` 不存在，服务端有降级实现，不阻塞 Dashboard 主功能。

### 10.5 健康度计算

当前健康度是经验公式，不是标准 QoE 模型：

```text
0.4 * (1 - packet_loss)
+ 0.3 * (1 / (1 + rtt / 100))
+ 0.3 * (1 / (1 + jitter / 50))
```

这部分应视为教学型启发指标，可继续替换，但重建时至少要保留“可解释、可视化、可测试”的评分机制。

## 11. HTTP API 设计

### 11.1 房间与信令接口

- `POST /rooms/join`
- `POST /rooms/leave`
- `GET /rooms/{roomId}/members`
- `GET /rooms/members`，兼容旧前端
- `POST /signal`
- `GET /signal/pending`

### 11.2 stats 与实验接口

- `POST /stats`
- `GET /stats`
- `GET /stats/history`
- `GET /stats/peers`
- `GET /stats/export.csv`
- `POST /stats/test/start`
- `POST /stats/test/finish`
- `POST /stats/test/cancel`
- `POST /clear_stats`

### 11.3 页面接口

- `GET /`
- `GET /static/webrtc/{filename}`

### 11.4 接口风格说明

- 使用 `aiohttp`
- 以 JSON 为主
- 广泛保留 CORS 头，便于实验环境调用
- 多数错误返回 `{status: "error"}` 或 `{error: "..."}`

重建时无需机械复制所有响应字段，但要保持：

- 房间/成员状态可观察
- 信令轮询模型清晰
- stats 和测试会话 API 解耦
- Dashboard 所需接口完整

## 12. 配置与运行方式

### 12.1 关键配置

位于 `src/webrtc/config.py`：

- `DEFAULT_WEBRTC_HOST`，默认 `0.0.0.0`
- `DEFAULT_WEBRTC_PORT`，默认 `8080`
- `DEFAULT_DASHBOARD_PORT`，默认 `8081`
- `DEFAULT_PUBLIC_WEBRTC_ORIGIN`
- `DEFAULT_SIGNALING_URL`
- `TLS_CERT_PATH` / `TLS_KEY_PATH`
- `DATA_DIR` / `EXPORTS_DIR` / `TEST_SESSIONS_DIR` / `CHARTS_DIR`

### 12.2 启动命令

推荐：

```bash
make run-webrtc
make run-dashboard
```

等价：

```bash
python3 src/webrtc/chat_server.py run
python3 -m src.dashboard.server run
```

### 12.3 运行前提

- Python 3.9+
- `.venv`
- 仓库根目录存在 `cert.pem` / `key.pem`
- 浏览器允许本地自签名 HTTPS

### 12.4 依赖概况

`requirements.txt` 当前主要依赖：

- `aiortc`
- `aiohttp`
- `pytest` 相关测试栈
- `matplotlib`
- `av`

说明：当前依赖文件偏教学/开发工具集合，不代表最小运行集。若重建仓库，可拆为运行依赖、开发依赖、Playwright 依赖。

## 13. 测试方案

### 13.1 测试分层

当前测试分三层：

- 后端/单元/接口测试
- Playwright 页面流程测试
- 手工浏览器弱网实验

### 13.2 关键测试文件

- `tests/test_mesh_signaling.py`
- `tests/test_mesh_room_lifecycle.py`
- `tests/test_dashboard.py`
- `tests/test_dashboard_realtime.py`
- `tests/test_dashboard_playwright.py`
- `tests/test_mesh_playwright.py`
- `tests/test_webrtc_test_session_playwright.py`
- `tests/test_rtcp_analysis.py`
- `tests/test_unit.py`

### 13.3 当前验证策略

优先最小必要回归：

- 改信令：跑 Mesh signaling / lifecycle
- 改 Dashboard：跑 dashboard / dashboard_realtime
- 改主流程交互：再补 Playwright
- 不默认全量跑重测试

### 13.4 重建时应保留的关键测试点

- 第 2 个成员加入时拿到 `existingPeers`
- `peer_joined` / `peer_left` 投递正确
- 房间上限被限制为 3
- 定向消息只投给目标成员，且拉取即消费
- stats 历史按 peer 正确隔离
- Dashboard 在缺字段和无数据时能稳定降级
- 测试会话可正常导出 CSV
- 前端暴露最小测试钩子以便自动化驱动

## 14. Automation Runner 方案

### 14.1 定位

`automation/` 不是 WebRTC 主功能的一部分，而是面向本仓库的“自动开发执行器”MVP。其目标是把低风险夜间任务固化成可控工程流，而不是让模型直接无约束写仓库。

### 14.2 目标能力

- 从 `automation/tasks/ready/` 读取任务契约 JSON
- 校验路径白名单、命令白名单、风险等级
- 生成 plan / patch draft / task report / morning summary
- 支持 `patch-only` 或 `worktree` 模式
- 支持 `stub` / `openai` / `anthropic` / `zhipu` 模型后端
- 将 transcript 落盘便于审计

### 14.3 主要目录

```text
automation/
├── config/
├── prompts/
├── runner/
├── tasks/
└── artifacts/
```

### 14.4 核心模块

- `task_loader.py`：读取任务契约
- `policies.py`：加载路径、命令、风险、运行时配置
- `model_gateway.py`：模型适配、JSON 解析、transcript 落盘
- `validators.py`：验证计划摘要
- `worker.py`：串起 plan / patch / report
- `orchestrator.py`：CLI 入口与晨报生成

### 14.5 任务契约思想

每个任务都需要明确：

- `goal`
- `context_files`
- `allowed_paths`
- `forbidden_paths`
- `acceptance`
- `required_checks`
- `optional_checks`
- `risk_level`

这个设计的意义是把“模型执行自由度”替换为“任务契约 + 策略引擎”。

### 14.6 当前限制

- 仍是 MVP，不是完整自治系统
- patch 生成与真实代码改动还未完全闭环
- worktree 依赖本地 git 权限与环境
- 以报告、patch 草案、审计产物为主

## 15. 数据与产物目录约定

### 15.1 `data/`

- `data/charts/`：Dashboard 生成的静态图
- `data/exports/`：stats 历史导出 CSV
- `data/test_sessions/`：测试会话 CSV
- `data/rtcp_stats/`：实验相关历史产物

### 15.2 `automation/artifacts/`

- `reports/`：任务报告和晨报
- `patches/`：patch 草案
- `transcripts/`：模型请求/响应记录

重建时建议继续区分“实验产物”和“自动化执行产物”，不要混放。

## 16. 已知限制与技术债

- stats、房间、测试会话都在内存里
- HTTP 轮询比 WebSocket 更简单，但不适合更高实时性场景
- ABR 仅调整 `maxBitrate`，没有完整分辨率/帧率联动策略
- Dashboard 图表是静态图片刷新，不是前端高频交互图表引擎
- 依赖与实际最小运行集未完全精简
- 旧文档、旧测试、归档材料仍并存，需要阅读时辨别当前主路径

## 17. 重新开发建议

如果要按当前仓库重新开发，建议按以下顺序实施。

### 第一阶段：最小闭环

1. 搭建 `aiohttp` HTTPS 服务
2. 提供 `/` 和静态资源
3. 实现 `POST /rooms/join`、`POST /signal`、`GET /signal/pending`
4. 浏览器端完成双人 P2P 通话
5. 加入基础 `getStats()` 上报和 `/stats`

### 第二阶段：实验可观察化

1. 引入 `StatsStore`
2. 增加 `/stats/history` 与 `/stats/peers`
3. 单独实现 Dashboard 服务
4. 展示 RTT、loss、jitter、bitrate、health

### 第三阶段：实验能力增强

1. 支持 3 人 Mesh
2. 支持主远端 + 缩略区
3. 支持 NACK 开关和 SDP munging
4. 支持发送端参数设置与简化 ABR
5. 支持测试会话与 CSV 导出

### 第四阶段：工程化补齐

1. 补齐 Mesh / Dashboard / Playwright 测试
2. 收口文档
3. 引入 automation runner 作为独立演进线

## 18. 最小重建清单

如果只保留“必须有”的内容，最少需要重建这些模块：

- 一个 `aiohttp` WebRTC 服务
- 一个房间 + 定向信令模型
- 一个浏览器实验页
- 一个 stats 内存存储
- 一个 Dashboard 服务
- 一个测试会话 CSV 导出模块
- 一组覆盖房间、信令、stats、Dashboard 的测试

建议对应文件骨架：

```text
src/webrtc/config.py
src/webrtc/app.py
src/webrtc/chat_server.py
src/webrtc/mesh_handlers.py
src/webrtc/stats_handlers.py
src/webrtc/stats_store.py
src/webrtc/test_session_store.py
src/webrtc/ui_handlers.py
src/webrtc/chat_real.html
src/webrtc/static/chat_real_shared.js
src/webrtc/static/chat_real_session.js
src/webrtc/static/chat_real_stats.js
src/webrtc/static/chat_real_bitrate.js
src/webrtc/static/chat_real_test_session.js
src/webrtc/static/chat_real_bootstrap.js
src/dashboard/server.py
src/dashboard/chart_generator.py
src/dashboard/templates/index.html
tests/test_mesh_signaling.py
tests/test_mesh_room_lifecycle.py
tests/test_dashboard.py
tests/test_dashboard_realtime.py
```

## 19. 结论

当前仓库本质上是两个并行主题的组合：

- 一个面向 WebRTC 学习和弱网实验的本地实验平台
- 一个面向低风险自动开发的 runner 原型

主仓库最重要的工程价值，不在于单点实现多先进，而在于它已经形成了“连接建立 -> stats 采集 -> 实验控制 -> CSV 固化 -> Dashboard 对比 -> 自动化任务收口”的完整训练闭环。重新开发时，只要保持这个闭环和本文档中的边界条件，具体实现细节可以替换，但系统形态不应偏离太多。
