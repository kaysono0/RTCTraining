# Playwright E2E CI Evaluation

本文评估 `make test-e2e` 是否进入 GitHub CI 必选门禁。

## Current E2E Shape

当前 E2E 入口：

```bash
make test-e2e PYTHON=python
```

实际执行：

```bash
python -m pytest tests/test_playwright_e2e.py -v
```

当前覆盖 40 个 Playwright 测试，包含：

- WebRTC 页面媒体启动、Join、Leave、NACK、manual bitrate、ABR、test session。
- Dashboard 服务状态、snapshot、Live Stats、CSV 对比、test session CSV 加载。
- 双页面 P2P 建联、三人 Mesh、stats 上传到 Dashboard。

本地最新结果：

```text
40 passed in 40.75s
```

## Browser Environment Requirements

当前测试依赖：

- Chromium headless。
- `ignore_https_errors=True` 访问本地 self-signed HTTPS。
- fake media：`--use-fake-device-for-media-stream` 和 `--use-fake-ui-for-media-stream`。
- WebRTC 服务和 Dashboard 服务动态端口。
- Dashboard 进程通过环境变量注入当前 WebRTC origin allowlist。

Playwright 官方 GitHub Actions 示例包含浏览器安装步骤：

```bash
python -m playwright install --with-deps
```

RTCTraining 只需要 Chromium，可收窄为：

```bash
python -m playwright install --with-deps chromium
make test-e2e PYTHON=python
```

官方资料：

- https://playwright.dev/python/docs/ci
- https://playwright.dev/python/docs/ci-intro
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

## Cost Assessment

| Cost | Impact |
| --- | --- |
| browser install cost | 每次 CI 需要安装 Chromium 和 Linux browser dependencies。Playwright 官方不推荐缓存 browser binaries，因为恢复 cache 的时间通常接近重新下载，并且 Linux system dependencies 不可缓存。 |
| job duration | 本地浏览器测试约 41 秒。GitHub Actions 还要额外承担 checkout、Python dependency install、browser install、service startup。 |
| runner resources | GitHub public repo `ubuntu-latest` 标准 runner 是 4 CPU / 16 GB RAM / 14 GB SSD；private repo 是 2 CPU / 8 GB RAM / 14 GB SSD。E2E 当前可运行，但要避免并行过高。 |
| flake surface | 测试包含真实 browser、fake media、本地 HTTPS、动态端口、多个 aiohttp 子进程和 P2P ICE 状态，比 unit/harness 更容易出现环境波动。 |
| debugging cost | 失败时需要上传 traces、logs 或 pytest output。否则 PR 作者难以判断是产品回归还是 runner/browser 环境问题。 |

## Recommendation

Recommendation: do not add Playwright E2E as a required PR gate yet.

当前 CI 应保持：

1. `make test-unit PYTHON=python`
2. `make harness-smoke PYTHON=python`

`make test-e2e` 继续作为本地合并前验证。

进入 CI 前需要先完成三个准备项：

1. 新增独立 `e2e` workflow 或手动触发 `workflow_dispatch`，避免一开始影响所有 PR。
2. 在 CI 中先跑 3 到 5 次观察稳定性和耗时。
3. 增加失败产物上传，包括 pytest output 和 Playwright trace，至少在 failure 时保留。

## Candidate CI Job

后续可以先用非必选 job 试运行：

```yaml
e2e:
  runs-on: ubuntu-latest
  needs: harness-smoke
  timeout-minutes: 15
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
    - name: Install Chromium
      run: python -m playwright install --with-deps chromium
    - name: Run Playwright E2E
      run: make test-e2e PYTHON=python
```

## Acceptance Criteria For CI Promotion

Playwright E2E 可以进入 required PR gate 的条件：

- 同一分支连续 5 次 GitHub Actions 运行通过。
- 总耗时稳定在可接受范围内。
- 失败时能看到足够日志定位 browser launch、service startup、port binding、WebRTC connection 或 assertion 问题。
- E2E job 不拖慢文档、小改动 PR 的反馈节奏。
