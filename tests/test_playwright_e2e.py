import contextlib
import json
import re
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import expect, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_url(url, *, ignore_tls=False, timeout=10):
    deadline = time.monotonic() + timeout
    context = ssl._create_unverified_context() if ignore_tls else None
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, context=context, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, URLError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {url}: {last_error}")


@contextlib.contextmanager
def managed_process(command):
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def webrtc_https_server():
    port = free_port()
    command = [
        sys.executable,
        "-m",
        "src.webrtc.chat_server",
        "run",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--cert",
        "certs/cert.pem",
        "--key",
        "certs/key.pem",
    ]
    with managed_process(command) as process:
        base_url = f"https://127.0.0.1:{port}"
        wait_for_url(f"{base_url}/", ignore_tls=True)
        if process.poll() is not None:
            raise AssertionError(process.stdout.read())
        yield base_url


@pytest.fixture
def dashboard_server():
    port = free_port()
    command = [
        sys.executable,
        "-m",
        "src.dashboard.server",
        "run",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    with managed_process(command) as process:
        base_url = f"http://127.0.0.1:{port}"
        wait_for_url(f"{base_url}/")
        if process.poll() is not None:
            raise AssertionError(process.stdout.read())
        yield base_url


@pytest.fixture
def browser_context():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
            ],
        )
        context = browser.new_context(ignore_https_errors=True)
        yield context
        context.close()
        browser.close()


def test_webrtc_page_can_start_media_join_and_leave_room(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    expect(page.locator("h1")).to_have_text("RTCTraining")
    expect(page.locator("#connectionState")).to_have_text("idle")

    page.get_by_role("button", name="Start Media").click()
    expect(page.locator("#connectionState")).to_have_text("media_ready")

    page.fill("#roomIdInput", "e2e-room")
    page.fill("#displayNameInput", "E2E Learner")
    page.get_by_role("button", name="Join").click()
    expect(page.locator("#connectionState")).to_have_text("joined")

    state = page.evaluate("window.__RTCTrainingTestHooks.getState()")
    room_id = page.evaluate("window.__RTCTrainingTestHooks.getRoomId()")
    timeline_types = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    assert state == "joined"
    assert room_id == "e2e-room"
    assert timeline_types == ["local_media_ready", "joined_room"]

    page.get_by_role("button", name="Leave").click()
    expect(page.locator("#connectionState")).to_have_text("left")


def test_webrtc_mobile_controls_stay_visible(browser_context, webrtc_https_server):
    page = browser_context.new_page()
    page.set_viewport_size({"width": 390, "height": 844})

    page.goto(webrtc_https_server)

    action_bar = page.locator(".mobile-action-bar")
    expect(action_bar).to_be_visible()
    assert action_bar.evaluate("element => getComputedStyle(element).position") == "fixed"

    for name in ("Start Media", "Join", "Leave"):
        button = page.get_by_role("button", name=name)
        expect(button).to_be_visible()
        box = button.bounding_box()
        assert box is not None
        assert 0 <= box["y"] < 844
        assert box["y"] + box["height"] <= 844


def test_webrtc_join_starts_media_when_needed(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.fill("#roomIdInput", "join-starts-media")
    page.fill("#displayNameInput", "Mobile Learner")
    page.get_by_role("button", name="Join").click()

    expect(page.locator("#connectionState")).to_have_text("joined")
    timeline_types = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    assert timeline_types == ["local_media_ready", "joined_room"]


def test_webrtc_media_error_records_browser_error_name(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.evaluate(
        """
        () => {
          navigator.mediaDevices.getUserMedia = async () => {
            throw new DOMException("Permission denied for test", "NotAllowedError");
          };
        }
        """
    )
    page.get_by_role("button", name="Start Media").click()

    expect(page.locator("#connectionState")).to_have_text("failed")
    media_error = page.evaluate("window.__RTCTrainingTestHooks.getTimeline().at(-1)")
    assert media_error["type"] == "media_error"
    assert media_error["summary"] == "NotAllowedError: Permission denied for test"
    assert media_error["details"]["error_name"] == "NotAllowedError"


def test_webrtc_media_falls_back_when_facing_mode_is_overconstrained(
    browser_context,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.evaluate(
        """
        () => {
          let calls = 0;
          navigator.mediaDevices.getUserMedia = async (constraints) => {
            calls += 1;
            window.__mediaConstraintCalls = window.__mediaConstraintCalls || [];
            window.__mediaConstraintCalls.push(constraints);
            if (calls === 1) {
              throw new DOMException("No matching camera", "OverconstrainedError");
            }
            return new MediaStream();
          };
        }
        """
    )
    page.get_by_role("button", name="Start Media").click()

    expect(page.locator("#connectionState")).to_have_text("media_ready")
    calls = page.evaluate("window.__mediaConstraintCalls")
    assert calls[0]["video"]["facingMode"] == "user"
    assert calls[1]["video"] is True


def test_webrtc_page_exposes_nack_mode_control_and_sdp_munging(
    browser_context,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    expect(page.locator("#nackModeState")).to_have_text("nack_enabled")
    assert page.evaluate("window.__RTCTrainingTestHooks.getNackMode()") == "enabled"

    page.select_option("#nackModeSelect", "disabled")

    expect(page.locator("#nackModeState")).to_have_text("nack_disabled")
    result = page.evaluate(
        """
        () => {
          const input = [
            "v=0",
            "m=audio 9 UDP/TLS/RTP/SAVPF 111",
            "a=rtcp-fb:111 nack",
            "m=video 9 UDP/TLS/RTP/SAVPF 96",
            "a=rtcp-fb:96 nack",
            "a=rtcp-fb:96 nack pli",
            "a=rtcp-fb:96 goog-remb"
          ].join("\\r\\n");
          return window.__RTCTrainingTestHooks.mungeNackSdp(input);
        }
        """
    )

    assert page.evaluate("window.__RTCTrainingTestHooks.getNackMode()") == "disabled"
    assert "m=audio" in result
    assert "a=rtcp-fb:111 nack" in result
    assert "m=video" in result
    assert "a=rtcp-fb:96 nack" not in result
    assert "a=rtcp-fb:96 nack pli" not in result
    assert "a=rtcp-fb:96 goog-remb" in result


def test_webrtc_hooks_survive_legacy_html_missing_nack_controls(
    browser_context,
    webrtc_https_server,
):
    page = browser_context.new_page()
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.route(
        re.compile(r".*/legacy-webrtc(?:\?.*)?$"),
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="""
            <!doctype html>
            <html lang="zh-CN">
              <body>
                <p id="connectionState">idle</p>
                <input id="roomIdInput" value="room1">
                <input id="displayNameInput" value="Learner">
                <button id="startMediaButton" type="button">Start Media</button>
                <button id="joinRoomButton" type="button">Join</button>
                <button id="leaveRoomButton" type="button">Leave</button>
                <video id="localVideo"></video>
                <div id="remoteVideos"></div>
                <ol id="timeline"></ol>
                <script src="/static/webrtc/chat_real_shared.js?v=legacy-html-contract"></script>
                <script src="/static/webrtc/chat_real_nack.js?v=legacy-html-contract"></script>
                <script src="/static/webrtc/chat_real_session.js?v=legacy-html-contract"></script>
                <script src="/static/webrtc/chat_real_stats.js?v=legacy-html-contract"></script>
                <script src="/static/webrtc/chat_real_bootstrap.js?v=legacy-html-contract"></script>
              </body>
            </html>
            """,
        ),
    )

    page.goto(f"{webrtc_https_server}/legacy-webrtc")
    page.wait_for_function(
        """
        () => {
          const hooks = window.__RTCTrainingTestHooks;
          return hooks &&
            typeof hooks.getNackMode === "function" &&
            typeof hooks.setNackMode === "function" &&
            typeof hooks.mungeNackSdp === "function";
        }
        """,
        timeout=10000,
    )

    assert page.evaluate("window.__RTCTrainingTestHooks.setNackMode('disabled')") == "disabled"
    assert page.evaluate("window.__RTCTrainingTestHooks.getNackMode()") == "disabled"
    assert page_errors == []


def test_dashboard_checks_webrtc_service_from_independent_port(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    expect(page.locator("h1")).to_have_text("RTCTraining Dashboard")
    expect(page.locator("#serviceState")).to_have_text("service_online")

    page.get_by_role("button", name="检查服务").click()

    expect(page.locator("#serviceState")).to_have_text("service_online")
    expect(page.locator("#roomSummary")).to_contain_text("0 rooms")


def test_dashboard_auto_checks_webrtc_service_on_load(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")

    expect(page.locator("#serviceState")).to_have_text("service_online")
    expect(page.locator("#roomSummary")).to_contain_text("0 rooms")


def test_dashboard_hooks_survive_legacy_html_missing_new_controls(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.route(
        re.compile(r".*/legacy-dashboard(?:\?.*)?$"),
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="""
            <!doctype html>
            <html lang="zh-CN">
              <body>
                <p id="serviceState">service_unchecked</p>
                <button id="checkServiceButton" type="button">检查服务</button>
                <input id="webrtcOriginInput" value="https://localhost:8080">
                <p id="roomSummary">0 rooms</p>
                <input id="statsRoomInput" value="room1">
                <p id="statsState">stats_unchecked</p>
                <p id="statsRefreshState">stats_last_updated: never</p>
                <ul id="peerPairList"></ul>
                <dl id="latestStatsPanel"></dl>
                <table id="statsHistoryTable"><tbody></tbody></table>
                <script src="/static/dashboard/dashboard.js?v=legacy-html-contract"></script>
              </body>
            </html>
            """,
        ),
    )

    page.goto(f"{dashboard_server}/legacy-dashboard?webrtc_origin={webrtc_https_server}")
    page.wait_for_function(
        """
        () => {
          const hooks = window.__RTCTrainingDashboardTestHooks;
          return hooks &&
            typeof hooks.checkService === "function" &&
            typeof hooks.loadLiveStats === "function" &&
            typeof hooks.clearLiveStats === "function" &&
            typeof hooks.getServiceState === "function" &&
            typeof hooks.getStatsState === "function" &&
            typeof hooks.getStatsRefreshState === "function" &&
            typeof hooks.getRoomSummary === "function";
        }
        """,
        timeout=10000,
    )
    expect(page.locator("#serviceState")).to_have_text("service_online", timeout=10000)
    expect(page.locator("#statsState")).to_have_text("service_online_but_no_stats", timeout=10000)
    assert page_errors == []


def test_dashboard_renders_nack_analysis_fields(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    sample = {
        "sample_index": 7,
        "timestamp": 1778140800,
        "room_id": "nack-room",
        "peer_id": "peer-a",
        "remote_peer_id": "peer-b",
        "metrics": {
            "connection_state": "connected",
            "ice_connection_state": "connected",
            "rtt_ms": 37.5,
            "packets_sent": 300,
            "packets_received": 280,
            "packets_lost": 12,
            "packet_loss_rate": 4.11,
            "jitter_ms": 9.2,
            "bitrate_kbps": 812.4,
            "available_outgoing_bitrate_kbps": 1200,
            "fps": 29.8,
            "frame_width": 640,
            "frame_height": 360,
            "frames_sent": 180,
            "frames_received": 172,
            "frames_decoded": 169,
            "frames_dropped": 3,
            "bytes_sent": 125000,
            "bytes_received": 98000,
            "codec": "video/VP8",
            "nack_enabled": False,
            "nack_mode": "disabled",
            "nack_count": 0,
            "pli_count": 1,
            "fir_count": 0,
        },
    }
    page.route(
        re.compile(r".*/api/webrtc/members\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            json={
                "ok": True,
                "data": {
                    "rooms": {
                        "nack-room": {
                            "members": [
                                {"peer_id": "peer-a", "display_name": "Alice"},
                                {"peer_id": "peer-b", "display_name": "Bob"},
                            ]
                        }
                    }
                },
            },
        ),
    )
    page.route(
        re.compile(r".*/api/webrtc/dashboard/snapshot\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            json={
                "ok": True,
                "data": {
                    "room_id": "nack-room",
                    "server_time": 1778140801,
                    "members": [
                        {"peer_id": "peer-a", "display_name": "Alice"},
                        {"peer_id": "peer-b", "display_name": "Bob"},
                    ],
                    "peers": [
                        {"peer_id": "peer-a", "remote_peer_id": "peer-b"},
                    ],
                    "latest": [sample],
                    "history": [sample],
                },
            },
        ),
    )

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id=nack-room")

    expect(page.locator("#statsState")).to_have_text("stats_online", timeout=10000)
    latest_text = page.locator("#latestStatsPanel")
    expect(latest_text).to_contain_text("NACK Enabled")
    expect(latest_text).to_contain_text("false")
    expect(latest_text).to_contain_text("Packets")
    expect(latest_text).to_contain_text("300 sent / 280 recv / 12 lost")
    expect(latest_text).to_contain_text("Bytes")
    expect(latest_text).to_contain_text("125000 sent / 98000 recv")
    expect(latest_text).to_contain_text("Frames")
    expect(latest_text).to_contain_text("180 sent / 172 recv / 169 decoded")
    expect(page.locator("#nackSummary")).to_have_text("NACK: disabled / 0")

    row = page.locator("#statsHistoryTable tbody tr:first-child")
    expect(row).to_contain_text("NACK 0")
    expect(row).to_contain_text("280 recv / 12 lost")
    expect(row).to_contain_text("169")
    expect(row).to_contain_text("3")
    expect(row).to_contain_text("98000")
    expect(row).to_contain_text("640 x 360")


def test_dashboard_workstation_layout_fits_mobile_viewport(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    page.set_viewport_size({"width": 390, "height": 844})

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")

    for selector in [
        ".dashboard-control-bar",
        ".dashboard-summary-strip",
        ".dashboard-latest-column",
        ".dashboard-side-column",
        ".dashboard-history-section",
    ]:
        expect(page.locator(selector)).to_be_visible()

    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.locator(".dashboard-table-scroll").evaluate(
        "element => element.scrollWidth > element.clientWidth"
    )
    assert page.locator("#checkServiceButton").bounding_box()["width"] >= 340
    assert page.locator("#clearStatsButton").bounding_box()["width"] >= 340


def test_two_webrtc_pages_connect_and_render_remote_video(
    browser_context,
    webrtc_https_server,
):
    alice = browser_context.new_page()
    bob = browser_context.new_page()

    alice.goto(webrtc_https_server)
    bob.goto(webrtc_https_server)

    for page, display_name in ((alice, "Alice"), (bob, "Bob")):
        page.get_by_role("button", name="Start Media").click()
        expect(page.locator("#connectionState")).to_have_text("media_ready")
        page.fill("#roomIdInput", "p2p-room")
        page.fill("#displayNameInput", display_name)

    alice.get_by_role("button", name="Join").click()
    expect(alice.locator("#connectionState")).to_have_text("joined")

    bob.get_by_role("button", name="Join").click()

    for page in (alice, bob):
        expect(page.locator("#connectionState")).to_have_text("connected", timeout=10000)
        expect(page.locator("#remoteVideos video")).to_have_count(1, timeout=10000)
        expect(page.locator("#remoteVideos .remote-tile")).to_have_count(1, timeout=10000)
        expect(page.locator("#remoteVideos")).to_have_class("remote-video-grid grid-1")
        page.wait_for_function(
            "window.__RTCTrainingTestHooks.getConnectedPeerCount() === 1",
            timeout=10000,
        )

    expect(alice.locator("#remoteVideos .remote-name")).to_contain_text("Bob", timeout=10000)
    expect(bob.locator("#remoteVideos .remote-name")).to_contain_text("Alice", timeout=10000)
    expect(alice.locator("#timeline li").first).to_contain_text("[")
    expect(alice.locator("#timeline")).to_contain_text("from")
    expect(alice.locator("#timeline")).to_contain_text("to")
    expect(alice.locator("#timeline")).to_contain_text("from: Bob (peer-")
    expect(bob.locator("#timeline")).to_contain_text("from: Alice (peer-")
    expect(alice.locator("#timeline details")).not_to_have_count(0)

    alice_timeline = alice.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    bob_timeline = bob.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    assert "received_offer" in alice_timeline
    assert "sent_answer" in alice_timeline
    assert "sent_offer" in bob_timeline
    assert "received_answer" in bob_timeline


def test_three_webrtc_pages_form_minimal_mesh(
    browser_context,
    webrtc_https_server,
):
    room_id = "mesh-room"
    alice = browser_context.new_page()
    bob = browser_context.new_page()
    charlie = browser_context.new_page()
    pages = ((alice, "Alice"), (bob, "Bob"), (charlie, "Charlie"))

    for page, display_name in pages:
        page.goto(webrtc_https_server)
        page.get_by_role("button", name="Start Media").click()
        expect(page.locator("#connectionState")).to_have_text("media_ready")
        page.fill("#roomIdInput", room_id)
        page.fill("#displayNameInput", display_name)

    for page, _display_name in pages:
        page.get_by_role("button", name="Join").click()

    peer_ids = {
        page: page.evaluate("window.__RTCTrainingTestHooks.getClientId()")
        for page, _display_name in pages
    }

    for page, _display_name in pages:
        expected_remote_peer_ids = sorted(
            peer_id
            for candidate_page, peer_id in peer_ids.items()
            if candidate_page is not page
        )
        expect(page.locator("#connectionState")).to_have_text("connected", timeout=15000)
        expect(page.locator("#remoteVideos video")).to_have_count(2, timeout=15000)
        expect(page.locator("#remoteVideos .remote-tile")).to_have_count(2, timeout=15000)
        expect(page.locator("#remoteVideos")).to_have_class("remote-video-grid grid-2")
        page.wait_for_function(
            """
            (expectedRemotePeerIds) => {
              const connectedPeerIds = window.__RTCTrainingTestHooks.getConnectedPeerIds();
              return JSON.stringify(connectedPeerIds.sort()) ===
                JSON.stringify(expectedRemotePeerIds);
            }
            """,
            arg=expected_remote_peer_ids,
            timeout=15000,
        )


def test_dashboard_renders_three_peer_mesh_topology(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    room_id = "dashboard-mesh-topology"
    alice = browser_context.new_page()
    bob = browser_context.new_page()
    charlie = browser_context.new_page()
    dashboard = browser_context.new_page()
    pages = ((alice, "Alice"), (bob, "Bob"), (charlie, "Charlie"))

    for page, display_name in pages:
        page.goto(webrtc_https_server)
        page.get_by_role("button", name="Start Media").click()
        expect(page.locator("#connectionState")).to_have_text("media_ready")
        page.fill("#roomIdInput", room_id)
        page.fill("#displayNameInput", display_name)

    for page, _display_name in pages:
        page.get_by_role("button", name="Join").click()

    for page, _display_name in pages:
        expect(page.locator("#connectionState")).to_have_text("connected", timeout=15000)

    dashboard.goto(
        f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id={room_id}"
    )

    expect(dashboard.locator("#meshTopologyState")).to_have_text("mesh_online", timeout=15000)
    expect(dashboard.locator("#meshTopology li")).to_have_count(6, timeout=15000)
    expect(dashboard.locator("#meshTopology")).to_contain_text("Alice (peer-", timeout=15000)
    expect(dashboard.locator("#meshTopology")).to_contain_text("Bob (peer-", timeout=15000)
    expect(dashboard.locator("#meshTopology")).to_contain_text("Charlie (peer-", timeout=15000)
    expect(dashboard.locator("#meshTopology")).to_contain_text("connected")
    expect(dashboard.locator("#meshTopology")).to_contain_text("RTT")
    expect(dashboard.locator("#meshTopology")).to_contain_text("Bitrate")


def test_connected_webrtc_pages_upload_stats_visible_to_dashboard(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    room_id = "stats-room"
    alice = browser_context.new_page()
    bob = browser_context.new_page()

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

    alice.wait_for_function(
        """
        async (roomId) => {
          const response = await fetch(`/stats/peers?room_id=${roomId}`);
          const payload = await response.json();
          return payload.ok && payload.data.peers.length >= 2;
        }
        """,
        arg=room_id,
        timeout=10000,
    )
    expect(alice.locator("#remoteVideos .remote-stats")).to_contain_text("Bitrate", timeout=10000)
    expect(alice.locator("#remoteVideos .remote-stats")).to_contain_text("Resolution", timeout=10000)
    expect(alice.locator("#remoteVideos .remote-stats")).to_contain_text("Lost", timeout=10000)

    dashboard_query = urlencode({"origin": webrtc_https_server, "room_id": room_id})
    with urlopen(f"{dashboard_server}/api/webrtc/stats/peers?{dashboard_query}", timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assert payload["ok"] is True
    assert len(payload["data"]["peers"]) >= 2
    assert {
        (peer["peer_id"], peer["remote_peer_id"])
        for peer in payload["data"]["peers"]
    } == {
        (alice.evaluate("window.__RTCTrainingTestHooks.getClientId()"), bob.evaluate("window.__RTCTrainingTestHooks.getClientId()")),
        (bob.evaluate("window.__RTCTrainingTestHooks.getClientId()"), alice.evaluate("window.__RTCTrainingTestHooks.getClientId()")),
    }


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
    expect(dashboard.locator("#peerPairList")).to_contain_text("Alice (peer-", timeout=10000)
    expect(dashboard.locator("#peerPairList")).to_contain_text("Bob (peer-", timeout=10000)
    expect(dashboard.locator("#peerPairList")).to_contain_text("last_sample:", timeout=10000)
    expect(dashboard.locator("#latestStatsPanel")).to_contain_text("RTT")
    expect(dashboard.locator("#latestStatsPanel")).to_contain_text("Connection")
    expect(dashboard.locator("#latestStatsPanel")).to_contain_text("Candidate Pair")
    expect(dashboard.locator("#latestStatsPanel")).to_contain_text("Missing Fields")
    expect(dashboard.locator("#statsHistoryTable tbody tr")).not_to_have_count(0)
    dashboard.wait_for_function(
        "document.querySelectorAll('#statsHistoryTable tbody tr').length > 2",
        timeout=10000,
    )
    expect(dashboard.locator("#statsHistoryTable tbody tr:first-child td:first-child")).to_contain_text("/", timeout=10000)
    state_during_refresh = dashboard.evaluate(
        """
        async () => {
          const refresh = window.__RTCTrainingDashboardTestHooks.loadLiveStats();
          const state = window.__RTCTrainingDashboardTestHooks.getStatsState();
          const refreshState = window.__RTCTrainingDashboardTestHooks.getStatsRefreshState();
          await refresh;
          return {state, refreshState};
        }
        """
    )
    assert state_during_refresh["state"] == "stats_online"
    assert state_during_refresh["refreshState"].startswith("stats_last_updated")

    overlapping_refresh_requests = dashboard.evaluate(
        """
        async () => {
          const originalFetch = window.fetch.bind(window);
          let releaseSnapshot;
          const snapshotGate = new Promise((resolve) => { releaseSnapshot = resolve; });
          let snapshotRequests = 0;
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes("/api/webrtc/dashboard/snapshot?")) {
              snapshotRequests += 1;
              if (snapshotRequests === 1) {
                await snapshotGate;
              }
            }
            return originalFetch(...args);
          };

          const firstRefresh = window.__RTCTrainingDashboardTestHooks.loadLiveStats();
          const secondRefresh = window.__RTCTrainingDashboardTestHooks.loadLiveStats();
          const state = window.__RTCTrainingDashboardTestHooks.getStatsState();
          const refreshState = window.__RTCTrainingDashboardTestHooks.getStatsRefreshState();
          releaseSnapshot();
          await Promise.all([firstRefresh, secondRefresh]);
          window.fetch = originalFetch;
          return {state, refreshState, snapshotRequests};
        }
        """
    )
    assert overlapping_refresh_requests["state"] == "stats_online"
    assert overlapping_refresh_requests["refreshState"].startswith("stats_last_updated")
    assert overlapping_refresh_requests["snapshotRequests"] == 1

    fallback_after_snapshot_404 = dashboard.evaluate(
        """
        async () => {
          const originalFetch = window.fetch.bind(window);
          let snapshotRequests = 0;
          window.fetch = async (...args) => {
            const url = String(args[0]);
            if (url.includes("/api/webrtc/dashboard/snapshot?")) {
              snapshotRequests += 1;
              return new Response("404: Not Found", {
                status: 404,
                headers: {"Content-Type": "text/plain"}
              });
            }
            return originalFetch(...args);
          };

          const payload = await window.__RTCTrainingDashboardTestHooks.loadLiveStats();
          const secondPayload = await window.__RTCTrainingDashboardTestHooks.loadLiveStats();
          const state = window.__RTCTrainingDashboardTestHooks.getStatsState();
          const pairCount = document.querySelectorAll("#peerPairList li").length;
          window.fetch = originalFetch;
          return {ok: payload.ok, secondOk: secondPayload.ok, state, pairCount, snapshotRequests};
        }
        """
    )
    assert fallback_after_snapshot_404["ok"] is True
    assert fallback_after_snapshot_404["secondOk"] is True
    assert fallback_after_snapshot_404["state"] == "stats_online"
    assert fallback_after_snapshot_404["pairCount"] == 2
    assert fallback_after_snapshot_404["snapshotRequests"] == 1

    clear_result = dashboard.evaluate(
        """
        async () => {
          const payload = await window.__RTCTrainingDashboardTestHooks.clearLiveStats();
          return {
            ok: payload.ok,
            state: window.__RTCTrainingDashboardTestHooks.getStatsState(),
            pairCount: document.querySelectorAll("#peerPairList li").length,
            historyCount: document.querySelectorAll("#statsHistoryTable tbody tr").length,
            latestText: document.querySelector("#latestStatsPanel").textContent
          };
        }
        """
    )
    assert clear_result["ok"] is True
    assert clear_result["state"] == "service_online_but_no_stats"
    assert clear_result["pairCount"] == 0
    assert clear_result["historyCount"] == 0
    assert clear_result["latestText"] == ""
