import pytest
import pytest_asyncio
import re
from aiohttp import web

from src.dashboard.server import create_dashboard_app
from src.webrtc.app import create_webrtc_app


@pytest_asyncio.fixture
async def webrtc_client(aiohttp_client):
    return await aiohttp_client(create_webrtc_app())


@pytest_asyncio.fixture
async def dashboard_client(aiohttp_client):
    return await aiohttp_client(create_dashboard_app())


@pytest.mark.asyncio
async def test_webrtc_homepage_loads_experiment_shell(webrtc_client):
    response = await webrtc_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "RTCTraining" in body
    assert re.search(r'href="/static/webrtc/chat_real\.css\?v=[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_nack\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_session\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_stats\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_bootstrap\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert "chat_real_nack.js" in body
    assert 'class="mobile-action-bar"' in body
    assert 'id="nackModeSelect"' in body
    assert 'id="nackModeState"' in body
    assert 'id="senderBitrateInput"' in body
    assert 'id="applyBitrateButton"' in body
    assert 'id="bitrateModeState"' in body
    assert 'id="abrModeSelect"' in body
    assert 'id="abrMinBitrateInput"' in body
    assert 'id="abrMaxBitrateInput"' in body
    assert 'id="abrStepKbpsInput"' in body
    assert 'id="abrLossThresholdInput"' in body
    assert 'id="abrRttThresholdInput"' in body
    assert 'id="abrModeState"' in body
    assert "window.__RTCTrainingTestHooks" in body
    assert "chat_real_bitrate.js" in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        ("chat_real_bootstrap.js", "bootstrapRTCTraining"),
        ("chat_real_stats.js", "RTCTrainingStats"),
        ("chat_real_nack.js", "RTCTrainingNack"),
        ("chat_real_bitrate.js", "RTCTrainingBitrate"),
    ],
)
async def test_webrtc_static_asset_loads(webrtc_client, asset, expected):
    response = await webrtc_client.get(f"/static/webrtc/{asset}")
    body = await response.text()

    assert response.status == 200
    assert expected in body


@pytest.mark.asyncio
async def test_webrtc_bitrate_module_sets_sender_parameters(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_bitrate.js")
    body = await response.text()

    assert response.status == 200
    assert "setParameters" in body
    assert "getSenders" in body
    assert "RTCTrainingBitrate" in body
    assert "sender_max_bitrate_bps" not in body


@pytest.mark.asyncio
async def test_dashboard_homepage_loads_independent_shell(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert "RTCTraining Dashboard" in body
    assert "WebRTC Service" in body
    assert "statsRoomInput" in body
    assert "statsState" in body
    assert "statsRefreshState" in body
    assert "clearStatsButton" in body
    assert 'src="/static/dashboard/dashboard.js?v=' in body
    assert "peerPairList" in body
    assert "latestStatsPanel" in body
    assert "statsHistoryTable" in body


@pytest.mark.asyncio
async def test_dashboard_homepage_declares_complete_stats_surface(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    for element_id in [
        "serviceState",
        "checkServiceButton",
        "webrtcOriginInput",
        "roomSummary",
        "statsRoomInput",
        "clearStatsButton",
        "statsState",
        "statsRefreshState",
        "peerPairList",
        "latestStatsPanel",
        "statsHistoryTable",
        "meshTopologyState",
        "meshTopology",
        "csvState",
    ]:
        assert f'id="{element_id}"' in body

    for class_name in [
        "dashboard-control-bar",
        "dashboard-summary-strip",
        "dashboard-main-grid",
        "dashboard-side-column",
        "dashboard-latest-column",
        "dashboard-history-section",
        "dashboard-table-scroll",
    ]:
        assert f'class="{class_name}"' in body
    assert 'id="nackSummary"' in body

    table_headers = re.findall(r"<th>([^<]+)</th>", body)
    assert table_headers == [
        "Time",
        "Peer",
        "Remote",
        "RTT",
        "Loss",
        "Packets",
        "NACK",
        "Decoded",
        "Dropped",
        "Bytes In",
        "Resolution",
        "Jitter",
        "Bitrate",
        "FPS",
    ]
    assert "window.__RTCTrainingDashboardInlineBootstrap" in body
    assert "window.__RTCTrainingDashboardInlineServiceCheckPath" in body


@pytest.mark.asyncio
async def test_dashboard_homepage_cache_contract(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert re.search(r'href="/static/dashboard/dashboard\.css\?v=[^"]+"', body)
    assert re.search(r'src="/static/dashboard/dashboard\.js\?v=[^"]*mesh-topology[^"]*nack-mode[^"]*"', body)


@pytest.mark.asyncio
async def test_dashboard_static_assets_are_versioned_and_loadable(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()
    css_path = re.search(r'href="([^"]*dashboard\.css\?v=[^"]+)"', body).group(1)
    js_path = re.search(r'src="([^"]*dashboard\.js\?v=[^"]+)"', body).group(1)

    css_response = await dashboard_client.get(css_path)
    css_body = await css_response.text()
    js_response = await dashboard_client.get(js_path)
    js_body = await js_response.text()

    assert css_response.status == 200
    assert ".dashboard-shell" in css_body
    assert js_response.status == 200
    assert "window.__RTCTrainingDashboardTestHooks" in js_body
    assert "loadLiveStats" in js_body
    assert "clearLiveStats" in js_body
    assert '"NACK Mode"' in js_body


@pytest.mark.asyncio
async def test_dashboard_proxy_handles_non_json_upstream_response(aiohttp_client, dashboard_client):
    async def plain_text_response(request):
        return web.Response(text="not json", content_type="text/plain")

    upstream = web.Application()
    upstream.router.add_get("/dashboard/snapshot", plain_text_response)
    upstream_client = await aiohttp_client(upstream)

    response = await dashboard_client.get(
        f"/api/webrtc/dashboard/snapshot?origin={upstream_client.make_url('/')}&room_id=room1"
    )
    payload = await response.json()

    assert response.status == 502
    assert payload["ok"] is False
    assert payload["error"]["code"] == "upstream_non_json"
    assert payload["error"]["details"]["status"] == 200


@pytest.mark.asyncio
async def test_dashboard_homepage_contains_inline_service_check_fallback(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert "window.__RTCTrainingDashboardInlineBootstrap" in body
    assert "/api/webrtc/members?origin=" in body


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
    snapshot = await dashboard_client.get(
        "/api/webrtc/dashboard/snapshot?origin=https://localhost:8080&room_id=room1"
    )
    clear_stats = await dashboard_client.post(
        "/api/webrtc/clear_stats?origin=https://localhost:8080",
        json={"room_id": "room1"},
    )

    assert stats.status != 404
    assert history.status != 404
    assert peers.status != 404
    assert snapshot.status != 404
    assert clear_stats.status != 404


@pytest.mark.asyncio
async def test_webrtc_stats_uploader_sends_browser_sample_time(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_stats.js")
    body = await response.text()

    assert "timestamp: Date.now() / 1000" in body


@pytest.mark.asyncio
async def test_webrtc_stats_uploader_records_nack_mode(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_stats.js")
    body = await response.text()

    assert 'nack_enabled: shared.state.nackMode === "enabled"' in body
    assert "nack_mode: shared.state.nackMode" in body


@pytest.mark.asyncio
async def test_webrtc_stats_uploader_records_sender_bitrate_config(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_stats.js")
    body = await response.text()

    assert response.status == 200
    assert "bitrate_mode: shared.state.bitrateMode" in body
    assert "sender_max_bitrate_bps: shared.state.senderMaxBitrateBps" in body


@pytest.mark.asyncio
async def test_webrtc_stats_uploader_records_abr_config(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_stats.js")
    body = await response.text()

    assert response.status == 200
    assert "abr_mode: shared.state.abrMode" in body
    assert "abr_target_bitrate_bps: shared.state.abrTargetBitrateBps" in body
    assert "abr_decision: shared.state.abrLastDecision" in body


@pytest.mark.asyncio
async def test_webrtc_session_applies_nack_sdp_munging(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_session.js")
    body = await response.text()

    assert "RTCTrainingNack.prepareLocalDescription(offer)" in body
    assert "RTCTrainingNack.prepareLocalDescription(answer)" in body
