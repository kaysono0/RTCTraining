import pytest
import pytest_asyncio
import re
from aiohttp import web

from src.dashboard.server import create_dashboard_app
from src.webrtc.app import create_webrtc_app
from src.webrtc.config import Settings


@pytest_asyncio.fixture
async def webrtc_client(aiohttp_client):
    return await aiohttp_client(create_webrtc_app())


@pytest_asyncio.fixture
async def dashboard_client(aiohttp_client):
    return await aiohttp_client(create_dashboard_app())


def test_webrtc_app_registers_public_route_names():
    app = create_webrtc_app()
    route_names = {
        route.name
        for route in app.router.routes()
        if route.name
    }

    for name in [
        "webrtc_index",
        "webrtc_static",
        "rooms_join",
        "rooms_leave",
        "rooms_members",
        "rooms_all_members",
        "signal_send",
        "signal_pending",
        "stats_post",
        "stats_latest",
        "stats_history",
        "stats_peers",
        "dashboard_snapshot",
        "stats_export_csv",
        "stats_clear",
        "test_session_start",
        "test_session_finish",
        "test_session_cancel",
        "test_session_list",
        "test_session_download",
    ]:
        assert name in route_names


@pytest.mark.asyncio
async def test_webrtc_homepage_loads_experiment_shell(webrtc_client):
    response = await webrtc_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "RTCTraining" in body
    assert re.search(r'href="/static/webrtc/chat_real\.css\?v=[^"]*sdp-parsed[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_nack\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_test_session\.js\?v=[^"]*test-session[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_session\.js\?v=[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_stats\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert re.search(r'src="/static/webrtc/chat_real_bootstrap\.js\?v=[^"]*nack-mode[^"]*mobile-media[^"]*"', body)
    assert "chat_real_nack.js" in body
    assert 'class="mobile-action-bar"' in body
    assert 'class="control-group identity-control-group"' in body
    assert 'class="control-group nack-control-group"' in body
    assert 'class="control-group bitrate-control-group"' in body
    assert 'class="control-group abr-control-group"' in body
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
    assert 'id="testPresetSelect"' in body
    assert 'id="testWeakNetworkInput"' in body
    assert 'id="testSessionNoteInput"' in body
    assert 'id="startTestSessionButton"' in body
    assert 'id="finishTestSessionButton"' in body
    assert 'id="cancelTestSessionButton"' in body
    assert 'id="testSessionState"' in body
    assert 'id="testSessionDownloads"' in body
    assert "window.__RTCTrainingTestHooks" in body
    assert "chat_real_bitrate.js" in body


@pytest.mark.asyncio
async def test_webrtc_page_loads_stats_modules_before_stats_script(webrtc_client):
    response = await webrtc_client.get("/")
    body = await response.text()
    script_paths = re.findall(r'src="([^"]+)"', body)

    normalizer_path = next(path for path in script_paths if "rtc/stats_normalizer.js" in path)
    view_path = next(path for path in script_paths if "ui/remote_stats_view.js" in path)
    stats_path = next(path for path in script_paths if "chat_real_stats.js" in path)

    assert script_paths.index(normalizer_path) < script_paths.index(stats_path)
    assert script_paths.index(view_path) < script_paths.index(stats_path)

    normalizer_response = await webrtc_client.get(normalizer_path)
    view_response = await webrtc_client.get(view_path)

    assert normalizer_response.status == 200
    assert "RTCTrainingStatsNormalizer" in await normalizer_response.text()
    assert view_response.status == 200
    assert "RTCTrainingRemoteStatsView" in await view_response.text()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        ("chat_real_bootstrap.js", "bootstrapRTCTraining"),
        ("chat_real_stats.js", "RTCTrainingStats"),
        ("chat_real_nack.js", "RTCTrainingNack"),
        ("chat_real_bitrate.js", "RTCTrainingBitrate"),
        ("chat_real_test_session.js", "RTCTrainingTestSession"),
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
        "livePeerPairSelect",
        "liveMetricSelect",
        "liveTrendChart",
        "peerPairList",
        "latestStatsPanel",
        "statsHistoryTable",
        "meshTopologyState",
        "meshTopology",
        "csvState",
        "csvFileInput",
        "csvMetricSelect",
        "csvAnalyzeButton",
        "csvValidationPanel",
        "experimentComparisonPanel",
        "csvComparisonTable",
        "csvTrendComparison",
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

    stats_table = re.search(r'<table id="statsHistoryTable".*?</table>', body, re.S).group(0)
    table_headers = re.findall(r"<th>([^<]+)</th>", stats_table)
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
    csv_table = re.search(r'<table id="csvComparisonTable".*?</table>', body, re.S).group(0)
    assert re.findall(r"<th>([^<]+)</th>", csv_table) == [
        "File",
        "Samples",
        "Room",
        "Session",
        "Peer",
        "Remote",
        "RTT (min–avg–max)",
        "Loss (min–avg–max)",
        "Jitter (min–avg–max)",
        "Bitrate (min–avg–max)",
        "FPS (min–avg–max)",
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
    assert re.search(r'src="/static/dashboard/dashboard\.js\?v=[^"]*stale-data[^"]*chinese-labels[^"]*"', body)


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
    assert "setLivePeerPair" in js_body
    assert "setLiveMetric" in js_body
    assert "analyzeCsvTexts" in js_body
    assert "setCsvMetric" in js_body
    assert "loadTestSessionCsvList" in js_body
    assert "loadSelectedSessionCsv" in js_body
    assert "REQUIRED_CSV_FIELDS" in js_body
    assert '"NACK Mode (NACK模式)"' in js_body


@pytest.mark.asyncio
async def test_dashboard_loads_csv_modules_before_main_script(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()
    script_paths = re.findall(r'src="([^"]+)"', body)

    parser_path = next(path for path in script_paths if "csv/parser.js" in path)
    analysis_path = next(path for path in script_paths if "csv/analysis.js" in path)
    view_path = next(path for path in script_paths if "csv/view.js" in path)
    dashboard_path = next(path for path in script_paths if "dashboard.js" in path)

    assert script_paths.index(parser_path) < script_paths.index(dashboard_path)
    assert script_paths.index(analysis_path) < script_paths.index(dashboard_path)
    assert script_paths.index(view_path) < script_paths.index(dashboard_path)

    parser_response = await dashboard_client.get(parser_path)
    parser_body = await parser_response.text()
    analysis_response = await dashboard_client.get(analysis_path)
    analysis_body = await analysis_response.text()
    view_response = await dashboard_client.get(view_path)
    view_body = await view_response.text()

    assert parser_response.status == 200
    assert "RTCTrainingDashboardCsvParser" in parser_body
    assert "parseCsvText" in parser_body
    assert analysis_response.status == 200
    assert "RTCTrainingDashboardCsvAnalysis" in analysis_body
    assert "summarizeCsvFile" in analysis_body
    assert view_response.status == 200
    assert "RTCTrainingDashboardCsvView" in view_body
    assert "rangeCell" in view_body


@pytest.mark.asyncio
async def test_dashboard_loads_live_presenter_before_main_script(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()
    script_paths = re.findall(r'src="([^"]+)"', body)

    presenter_path = next(path for path in script_paths if "live/presenter.js" in path)
    dashboard_path = next(path for path in script_paths if "dashboard.js" in path)

    assert script_paths.index(presenter_path) < script_paths.index(dashboard_path)

    presenter_response = await dashboard_client.get(presenter_path)
    presenter_body = await presenter_response.text()

    assert presenter_response.status == 200
    assert "RTCTrainingDashboardLivePresenter" in presenter_body
    assert "peerPairLabel" in presenter_body
    assert "newestSample" in presenter_body


@pytest.mark.asyncio
async def test_dashboard_loads_core_and_live_modules_before_main_script(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()
    script_paths = re.findall(r'src="([^"]+)"', body)

    module_paths = [
        next(path for path in script_paths if "core/dom.js" in path),
        next(path for path in script_paths if "core/api_client.js" in path),
        next(path for path in script_paths if "live/stats_view.js" in path),
    ]
    dashboard_path = next(path for path in script_paths if "dashboard.js" in path)

    for module_path in module_paths:
        assert script_paths.index(module_path) < script_paths.index(dashboard_path)

    dom_response = await dashboard_client.get(module_paths[0])
    api_response = await dashboard_client.get(module_paths[1])
    stats_response = await dashboard_client.get(module_paths[2])

    assert dom_response.status == 200
    assert "RTCTrainingDashboardDom" in await dom_response.text()
    assert api_response.status == 200
    assert "RTCTrainingDashboardApiClient" in await api_response.text()
    assert stats_response.status == 200
    assert "RTCTrainingDashboardStatsView" in await stats_response.text()


@pytest.mark.asyncio
async def test_dashboard_proxy_handles_non_json_upstream_response(aiohttp_client):
    async def plain_text_response(request):
        return web.Response(text="not json", content_type="text/plain")

    upstream = web.Application()
    upstream.router.add_get("/dashboard/snapshot", plain_text_response)
    upstream_client = await aiohttp_client(upstream)
    upstream_origin = str(upstream_client.make_url("/")).rstrip("/")
    dashboard_client = await aiohttp_client(
        create_dashboard_app(
            settings=Settings(
                dashboard_origin_allowlist=upstream_origin,
                local_webrtc_origin=upstream_origin,
            )
        )
    )

    response = await dashboard_client.get(
        f"/api/webrtc/dashboard/snapshot?origin={upstream_origin}&room_id=room1"
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
async def test_dashboard_test_session_proxy_routes_exist(dashboard_client):
    sessions = await dashboard_client.get(
        "/api/webrtc/stats/test/sessions?origin=bad-origin&room_id=room1"
    )
    csv_file = await dashboard_client.get(
        "/api/webrtc/stats/test/download/room1/session1/peer-a/peer-b.csv?origin=bad-origin"
    )

    assert sessions.status != 404
    assert csv_file.status != 404


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
async def test_webrtc_stats_uploader_records_test_session_id(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_stats.js")
    body = await response.text()

    assert response.status == 200
    assert "test_session_id: shared.state.testSessionId" in body


@pytest.mark.asyncio
async def test_webrtc_session_applies_nack_sdp_munging(webrtc_client):
    response = await webrtc_client.get("/static/webrtc/chat_real_session.js")
    body = await response.text()

    assert "RTCTrainingNack.prepareLocalDescription(offer)" in body
    assert "RTCTrainingNack.prepareLocalDescription(answer)" in body
