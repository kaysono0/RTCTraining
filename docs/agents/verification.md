# RTCTraining Verification Guide

本文档记录本项目常用验证入口。根目录 `AGENTS.md` 只保留命令地图，具体排查细节放在这里。

## 1. 环境准备

使用项目内虚拟环境：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

生成本地 HTTPS 证书：

```bash
make cert
```

局域网真机访问时，需要把实际 LAN IP 加入证书 SAN：

```bash
.venv/bin/python scripts/generate_cert.py --host 192.168.x.x
```

查看可访问地址：

```bash
make urls
```

## 2. 启动服务

启动 WebRTC 服务：

```bash
make run-webrtc
```

默认入口：

```text
https://localhost:8080
```

启动 Dashboard 服务：

```bash
make run-dashboard
```

默认入口：

```text
http://127.0.0.1:8081
```

## 3. 测试命令

单元和 handler 测试：

```bash
make test-unit
```

Playwright E2E：

```bash
make test-e2e
```

完整测试：

```bash
make test
```

直接使用 pytest：

```bash
.venv/bin/python -m pytest tests -v
```

## 4. HTTP Smoke 验证

WebRTC 首页：

```bash
curl -k -I https://localhost:8080/
```

Dashboard 首页：

```bash
curl -I http://127.0.0.1:8081/
```

WebRTC stats peers：

```bash
curl -k "https://localhost:8080/stats/peers?room_id=room1"
```

Dashboard stats 代理：

```bash
curl "http://127.0.0.1:8081/api/webrtc/stats/peers?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1"
```

期望 API 响应格式：

```json
{ "ok": true, "data": {} }
```

或：

```json
{ "ok": false, "error": { "code": "...", "message": "...", "details": {} } }
```

## 5. Playwright 注意事项

- 首版只支持桌面 Chrome。
- 面对本地自签名 HTTPS 时使用 `ignore_https_errors`。
- E2E 使用 fake media。
- WebRTC 页面状态通过 `window.__RTCTrainingTestHooks` 暴露给测试。

## 6. 沙箱和提权注意事项

以下动作在受限环境中可能需要提权：

- 安装 Python 依赖。
- 下载 Playwright 浏览器。
- aiohttp 测试绑定 `127.0.0.1` 临时端口。
- WebRTC 服务绑定 `0.0.0.0:8080`。
- Dashboard 服务绑定 `127.0.0.1:8081`。
- 用 `curl` 验证提权服务入口。

普通沙箱里的 `curl` 可能连不到提权启动的服务。若服务会话仍在运行但普通 `curl` 失败，优先按沙箱网络隔离排查。

## 7. 验证完成标准

功能完成前至少满足：

- 新行为有对应测试。
- 相关测试命令通过。
- 涉及页面交互时，Playwright E2E 覆盖核心路径。
- 涉及 Dashboard 时，WebRTC 与 Dashboard 服务都能启动并返回基础页面。
- 涉及 stats 时，数据边界包含 `room_id / test_session_id / peer_id / remote_peer_id`。
