import contextlib
import json
import os
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


def wait_for_webrtc_members(server_url, room_id, expected_count, *, timeout=5):
    deadline = time.monotonic() + timeout
    context = ssl._create_unverified_context()
    last_payload = None
    while time.monotonic() < deadline:
        with urlopen(f"{server_url}/rooms/{room_id}/members", context=context, timeout=1) as response:
            last_payload = json.loads(response.read().decode("utf-8"))
        members = last_payload["data"]["members"]
        if len(members) == expected_count:
            return members
        time.sleep(0.1)
    raise AssertionError(f"expected {expected_count} members, got {last_payload}")


@contextlib.contextmanager
def managed_process(command, *, env=None):
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=env,
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
def dashboard_server(webrtc_https_server):
    port = free_port()
    env = os.environ.copy()
    env["RTC_DASHBOARD_ORIGIN_ALLOWLIST"] = webrtc_https_server
    env["RTC_LOCAL_WEBRTC_ORIGIN"] = webrtc_https_server
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
    with managed_process(command, env=env) as process:
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
    for expected in ["local_media_requesting", "local_media_ready", "joined_room"]:
        assert expected in timeline_types, f"expected {expected!r} in timeline, got {timeline_types}"

    page.get_by_role("button", name="Leave").click()
    expect(page.locator("#connectionState")).to_have_text("left")


def test_webrtc_mobile_controls_stay_visible(browser_context, webrtc_https_server):
    page = browser_context.new_page()
    page.set_viewport_size({"width": 390, "height": 844})

    page.goto(webrtc_https_server)

    expect(page.locator(".identity-control-group")).to_be_visible()
    expect(page.locator(".nack-control-group")).to_be_visible()
    expect(page.locator(".bitrate-control-group")).to_be_visible()
    expect(page.locator(".abr-control-group")).to_be_visible()

    for selector in (
        ".identity-control-group",
        ".nack-control-group",
        ".bitrate-control-group",
        ".abr-control-group",
    ):
        group_box = page.locator(selector).bounding_box()
        assert group_box is not None
        assert group_box["width"] <= 390

    action_bar = page.locator(".mobile-action-bar")
    expect(action_bar).to_be_visible()
    assert action_bar.evaluate("element => getComputedStyle(element).position") == "fixed"
    action_bar_box = action_bar.bounding_box()
    abr_box = page.locator(".abr-control-group").bounding_box()
    assert action_bar_box is not None
    assert abr_box is not None
    assert abr_box["y"] + abr_box["height"] < action_bar_box["y"]

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
    missing = [t for t in ["local_media_requesting", "local_media_ready", "joined_room"] if t not in timeline_types]
    assert not missing, f"expected events not found: {missing}, timeline: {timeline_types}"


def test_webrtc_page_leave_room_on_close(browser_context, webrtc_https_server):
    room_id = "close-cleans-room"
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.fill("#roomIdInput", room_id)
    page.fill("#displayNameInput", "Closing Learner")
    page.get_by_role("button", name="Join").click()

    expect(page.locator("#connectionState")).to_have_text("joined")
    assert len(wait_for_webrtc_members(webrtc_https_server, room_id, 1)) == 1

    page.close()

    assert wait_for_webrtc_members(webrtc_https_server, room_id, 0) == []


def test_webrtc_join_room_full_shows_room_full(browser_context, webrtc_https_server):
    page = browser_context.new_page()
    room_id = "full-room"

    page.goto(webrtc_https_server)
    page.evaluate(
        """
        async (roomId) => {
          for (const clientId of ["seed-a", "seed-b", "seed-c"]) {
            const response = await fetch("/rooms/join", {
              method: "POST",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({
                room_id: roomId,
                client_id: clientId,
                display_name: clientId
              })
            });
            if (!response.ok) {
              throw new Error(`seed join failed: ${response.status}`);
            }
          }
        }
        """,
        arg=room_id,
    )
    page.fill("#roomIdInput", room_id)
    page.fill("#displayNameInput", "Blocked Learner")
    page.get_by_role("button", name="Join").click()

    expect(page.locator("#connectionState")).to_have_text("room_full")
    timeline_types = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    assert "join_room_failed" in timeline_types


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


def test_webrtc_media_request_writes_timeline_before_browser_prompt_resolves(
    browser_context,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.evaluate(
        """
        () => {
          navigator.mediaDevices.getUserMedia = async () => new Promise(() => {});
        }
        """
    )
    page.get_by_role("button", name="Start Media").click()

    expect(page.locator("#connectionState")).to_have_text("media_requesting")
    timeline_types = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map((event) => event.type)"
    )
    assert "local_media_requesting" in timeline_types, (
        f"expected local_media_requesting in timeline before getUserMedia resolves, got {timeline_types}"
    )


def test_webrtc_page_initializes_without_crypto_random_uuid(browser_context, webrtc_https_server):
    browser_context.add_init_script(
        """
        () => {
          Object.defineProperty(window.crypto, "randomUUID", {
            value: undefined,
            configurable: true
          });
        }
        """
    )
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.evaluate(
        """
        () => {
          navigator.mediaDevices.getUserMedia = async () => {
            throw new DOMException("Camera blocked for test", "NotAllowedError");
          };
        }
        """
    )
    page.get_by_role("button", name="Start Media").click()

    expect(page.locator("#connectionState")).to_have_text("failed")
    media_error = page.evaluate("window.__RTCTrainingTestHooks.getTimeline().at(-1)")
    client_id = page.evaluate("window.__RTCTrainingTestHooks.getClientId()")
    assert client_id.startswith("peer-")
    assert media_error["type"] == "media_error"
    assert media_error["summary"] == "NotAllowedError: Camera blocked for test"


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


def test_webrtc_page_applies_manual_sender_bitrate(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    expect(page.locator("#bitrateModeState")).to_have_text("bitrate_auto")
    assert page.evaluate("window.__RTCTrainingTestHooks.setSenderBitrateKbps(800)") == "manual"
    expect(page.locator("#bitrateModeState")).to_have_text("bitrate_manual_800kbps")
    assert page.evaluate("window.__RTCTrainingTestHooks.getBitrateMode()") == "manual"
    assert page.evaluate("window.__RTCTrainingTestHooks.getSenderMaxBitrateBps()") == 800000

    assert page.evaluate("window.__RTCTrainingTestHooks.setSenderBitrateKbps(0)") == "auto"
    expect(page.locator("#bitrateModeState")).to_have_text("bitrate_auto")
    assert page.evaluate("window.__RTCTrainingTestHooks.getBitrateMode()") == "auto"
    assert page.evaluate("window.__RTCTrainingTestHooks.getSenderMaxBitrateBps()") is None


def test_webrtc_stats_normalizer_computes_loss_rate(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    result = page.evaluate(
        """
        () => window.RTCTrainingStatsNormalizer.finalizeMetrics({
          packets_received: 90,
          packets_lost: 10
        })
        """
    )

    assert result["packet_loss_rate"] == 10


def test_webrtc_page_runs_simplified_abr_decisions(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    expect(page.locator("#abrModeState")).to_have_text("abr_off")
    assert page.evaluate("window.__RTCTrainingTestHooks.setAbrMode('on')") == "on"
    expect(page.locator("#abrModeState")).to_have_text("abr_on_hold")
    assert page.evaluate("window.__RTCTrainingTestHooks.getAbrMode()") == "on"
    assert page.evaluate("window.__RTCTrainingTestHooks.getAbrTargetBitrateBps()") == 1500000

    decrease = page.evaluate(
        """
        window.__RTCTrainingTestHooks.runAbrDecision({
          packet_loss_rate: 7,
          rtt_ms: 350,
          fps: 30
        })
        """
    )
    assert decrease["decision"] == "decrease"
    assert decrease["target_bitrate_bps"] == 1350000
    assert page.evaluate("window.__RTCTrainingTestHooks.getSenderMaxBitrateBps()") == 1350000
    expect(page.locator("#abrModeState")).to_have_text("abr_on_decrease")

    increase = page.evaluate(
        """
        window.__RTCTrainingTestHooks.runAbrDecision({
          packet_loss_rate: 1,
          rtt_ms: 100,
          fps: 30
        })
        """
    )
    assert increase["decision"] == "increase"
    assert increase["target_bitrate_bps"] == 1500000
    assert page.evaluate("window.__RTCTrainingTestHooks.getAbrLastDecision()") == "increase"
    expect(page.locator("#abrModeState")).to_have_text("abr_on_increase")

    assert page.evaluate("window.__RTCTrainingTestHooks.setAbrMode('off')") == "off"
    expect(page.locator("#abrModeState")).to_have_text("abr_off")


def test_webrtc_stats_upload_runs_abr_decision(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    assert page.evaluate("window.__RTCTrainingTestHooks.setAbrMode('on')") == "on"
    result = page.evaluate(
        """
        async () => {
          window.__appliedMaxBitrate = null;
          const sender = {
            track: { kind: "video" },
            getParameters: () => ({ encodings: [{}] }),
            setParameters: async (parameters) => {
              window.__appliedMaxBitrate = parameters.encodings[0].maxBitrate;
            }
          };
          window.RTCTrainingShared.state.peerConnections["peer-b"] = {
            connectionState: "connected",
            iceConnectionState: "connected",
            getSenders: () => [sender],
            getStats: async () => new Map([
              ["inbound-video", {
                id: "inbound-video",
                type: "inbound-rtp",
                isRemote: false,
                packetsReceived: 95,
                packetsLost: 5,
                bytesReceived: 1000,
                framesPerSecond: 30
              }]
            ])
          };
          await window.RTCTrainingStats.uploadAllPeerStats();
          return {
            appliedMaxBitrate: window.__appliedMaxBitrate,
            sample: window.__RTCTrainingTestHooks.getLatestStats()["peer-b"]
          };
        }
        """
    )

    assert result["appliedMaxBitrate"] == 1350000
    assert result["sample"]["metrics"]["abr_mode"] == "on"
    assert result["sample"]["metrics"]["abr_decision"] == "decrease"
    assert result["sample"]["metrics"]["abr_target_bitrate_bps"] == 1350000
    assert result["sample"]["metrics"]["sender_max_bitrate_bps"] == 1350000


def test_webrtc_page_runs_test_session_lifecycle(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    expect(page.locator("#testSessionState")).to_have_text("test_session_idle")
    expect(page.locator("#testSessionElapsed")).to_have_text("Elapsed: 00:00")
    result = page.evaluate(
        """
        window.__RTCTrainingTestHooks.startTestSession({
          preset: "nack_on",
          metadata: { note: "baseline" },
          weak_network: { profile: "none" }
        })
        """
    )

    assert result["status"] == "running"
    assert page.evaluate("window.__RTCTrainingTestHooks.getTestSessionId()") == result["test_session_id"]
    expect(page.locator("#testSessionState")).to_have_text("test_session_running")
    expect(page.locator("#testSessionElapsed")).to_have_text(re.compile(r"Elapsed: 00:0[1-9]"), timeout=2500)

    sample = page.evaluate(
        """
        window.RTCTrainingStats.collectPeerStats("peer-b", {
          connectionState: "connected",
          iceConnectionState: "connected",
          getStats: async () => new Map()
        })
        """
    )
    assert sample["test_session_id"] == result["test_session_id"]

    finished = page.evaluate("window.__RTCTrainingTestHooks.finishTestSession()")
    assert finished["status"] == "finished"
    expect(page.locator("#testSessionState")).to_have_text("test_session_finished")
    stopped_elapsed = page.evaluate("window.__RTCTrainingTestHooks.getTestSessionElapsedText()")
    page.wait_for_timeout(1200)
    assert page.evaluate("window.__RTCTrainingTestHooks.getTestSessionElapsedText()") == stopped_elapsed
    expect(page.locator("#testSessionDownloads a")).to_have_count(1)


def test_webrtc_test_session_applies_experiment_preset(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    page.select_option("#testPresetSelect", "abr_simple")
    result = page.evaluate("window.__RTCTrainingTestHooks.applyTestPreset('abr_simple')")

    assert result["preset"] == "abr_simple"
    assert result["nack_mode"] == "enabled"
    assert result["abr_mode"] == "on"
    assert result["bitrate_mode"] == "abr"
    expect(page.locator("#nackModeState")).to_have_text("nack_enabled")
    expect(page.locator("#abrModeState")).to_contain_text("abr_on")
    expect(page.locator("#testSessionPresetSummary")).to_contain_text("abr_simple")


def test_webrtc_test_session_renders_metadata_and_download_groups(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)
    result = page.evaluate(
        """
        async () => {
          const session = await window.__RTCTrainingTestHooks.startTestSession({
            preset: "nack_on",
            planned_duration_seconds: 45,
            metadata: { note: "baseline" },
            weak_network: { profile: "loss_5" }
          });
          window.RTCTrainingShared.state.testSession = {
            ...session,
            status: "finished",
            finished_at: session.started_at + 3,
            sample_count: 4,
            csv_files: [
              {
                room_id: "room1",
                test_session_id: session.test_session_id,
                peer_id: window.__RTCTrainingTestHooks.getClientId(),
                remote_peer_id: "peer-b",
                filename: "20260507-080000Z_Alice_peer-a_to_peer-b_nack_on_nack-enabled_abr-off_bitrate-auto_3s.csv",
                display_name: "Alice peer-a -> peer-b | nack_on | nack enabled | abr off | auto | 3s | 20260507-080000Z",
                download_url: "/stats/test/download/room1/s1/peer-a/peer-b.csv"
              }
            ]
          };
          window.RTCTrainingShared.state.testSessionStatus = "finished";
          window.RTCTrainingTestSession.renderTestSession();
          return session.test_session_id;
        }
        """
    )

    expect(page.locator("#testSessionDetails")).to_contain_text(result)
    expect(page.locator("#testSessionDetails")).to_contain_text("preset: nack_on")
    expect(page.locator("#testSessionDetails")).to_contain_text("weak: loss_5")
    expect(page.locator("#testSessionDetails")).to_contain_text("planned: 45s")
    expect(page.locator("#testSessionDetails")).to_contain_text("samples: 4")
    expect(page.locator("#testSessionDownloads")).to_contain_text("Alice peer-a -> peer-b")


def test_webrtc_test_session_cancel_lifecycle(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    expect(page.locator("#testSessionState")).to_have_text("test_session_idle")

    result = page.evaluate(
        """
        window.__RTCTrainingTestHooks.startTestSession({
          preset: "nack_on",
          metadata: { note: "cancel-test" },
          weak_network: { profile: "none" }
        })
        """
    )
    assert result["status"] == "running"
    session_id = result["test_session_id"]
    assert page.evaluate("window.__RTCTrainingTestHooks.getTestSessionId()") == session_id
    expect(page.locator("#testSessionState")).to_have_text("test_session_running")

    canceled = page.evaluate("window.__RTCTrainingTestHooks.cancelTestSession()")
    assert canceled["status"] == "canceled"

    # After cancel, sessionId should be null so a new session can start
    assert page.evaluate("window.__RTCTrainingTestHooks.getTestSessionId()") is None
    expect(page.locator("#testSessionState")).to_have_text("test_session_canceled")

    # Timeline should have both started and canceled events
    timeline_types = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map(e => e.type)"
    )
    assert "test_session_started" in timeline_types
    assert "test_session_canceled" in timeline_types


def test_webrtc_test_session_timeline_events(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    page.evaluate(
        """
        window.__RTCTrainingTestHooks.startTestSession({
          preset: "nack_on",
          metadata: { note: "timeline-test" }
        })
        """
    )
    page.evaluate("window.__RTCTrainingTestHooks.finishTestSession()")

    timeline = page.evaluate(
        "window.__RTCTrainingTestHooks.getTimeline().map(e => ({type: e.type, category: e.category, summary: e.summary}))"
    )

    started = [e for e in timeline if e["type"] == "test_session_started"]
    finished = [e for e in timeline if e["type"] == "test_session_finished"]

    assert len(started) == 1, f"expected 1 test_session_started event, got {started}"
    assert len(finished) == 1, f"expected 1 test_session_finished event, got {finished}"
    assert started[0]["category"] == "test"
    assert finished[0]["category"] == "test"
    assert "samples=" in finished[0]["summary"]


def test_webrtc_test_session_cancel_from_ui_button(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    # Start via test hook
    page.evaluate(
        """
        window.__RTCTrainingTestHooks.startTestSession({
          preset: "nack_on"
        })
        """
    )
    expect(page.locator("#testSessionState")).to_have_text("test_session_running")

    # Click the Cancel button in the DOM
    page.get_by_role("button", name="Cancel").click()
    page.wait_for_timeout(500)

    expect(page.locator("#testSessionState")).to_have_text("test_session_canceled")
    assert page.evaluate("window.__RTCTrainingTestHooks.getTestSessionId()") is None


def test_webrtc_test_session_start_rejects_when_running(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    page.evaluate(
        """
        (async () => {
          await window.__RTCTrainingTestHooks.startTestSession({
            preset: "nack_on"
          });
        })()
        """
    )
    expect(page.locator("#testSessionState")).to_have_text("test_session_running")

    # Starting a second session while one is running should throw (async rejection)
    error_msg = page.evaluate(
        """
        (async () => {
          try {
            await window.__RTCTrainingTestHooks.startTestSession({ preset: "nack_off" });
            return null;
          } catch (e) {
            return e.message;
          }
        })()
        """
    )
    assert error_msg is not None, "expected error when starting second session"
    assert "already running" in error_msg


def test_webrtc_test_session_cancel_clears_state_for_new_session(browser_context, webrtc_https_server):
    page = browser_context.new_page()

    page.goto(webrtc_https_server)

    # Start, cancel, then start again — should work
    page.evaluate(
        """
        (async () => {
          await window.__RTCTrainingTestHooks.startTestSession({ preset: 'nack_on' });
          await window.__RTCTrainingTestHooks.cancelTestSession();
        })()
        """
    )

    # Second start should succeed (no "already running" error)
    second = page.evaluate(
        """
        (async () => {
          return await window.__RTCTrainingTestHooks.startTestSession({ preset: 'nack_off' });
        })()
        """
    )
    assert second["status"] == "running"
    assert second["preset"] == "nack_off"


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
        ".dashboard-csv-section",
    ]:
        expect(page.locator(selector)).to_be_visible()

    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.locator(".dashboard-history-section .dashboard-table-scroll").evaluate(
        "element => element.scrollWidth > element.clientWidth"
    )
    assert page.locator("#checkServiceButton").bounding_box()["width"] >= 340
    assert page.locator("#clearStatsButton").bounding_box()["width"] >= 340


def test_dashboard_latest_stats_uses_newest_sample_across_peer_pairs(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    older_sample = {
        "sample_index": 10,
        "timestamp": 1778140800,
        "room_id": "latest-room",
        "peer_id": "peer-a",
        "remote_peer_id": "peer-b",
        "metrics": {
            "connection_state": "connected",
            "ice_connection_state": "connected",
            "rtt_ms": 10,
            "packets_sent": 100,
            "packets_received": 100,
            "packets_lost": 0,
            "jitter_ms": 1,
            "bitrate_kbps": 100,
            "fps": 24,
            "frame_width": 320,
            "frame_height": 180,
            "bytes_sent": 1000,
            "bytes_received": 1000,
            "frames_sent": 24,
            "frames_received": 24,
            "frames_decoded": 24,
            "frames_dropped": 0,
            "codec": "video/VP8",
            "nack_enabled": True,
            "nack_mode": "enabled",
            "nack_count": 1,
        },
    }
    newest_sample = {
        "sample_index": 11,
        "timestamp": 1778140801,
        "room_id": "latest-room",
        "peer_id": "peer-c",
        "remote_peer_id": "peer-d",
        "metrics": {
            "connection_state": "connected",
            "ice_connection_state": "connected",
            "rtt_ms": 88,
            "packets_sent": 200,
            "packets_received": 190,
            "packets_lost": 3,
            "jitter_ms": 7,
            "bitrate_kbps": 900,
            "fps": 30,
            "frame_width": 640,
            "frame_height": 360,
            "bytes_sent": 2000,
            "bytes_received": 1900,
            "frames_sent": 30,
            "frames_received": 29,
            "frames_decoded": 29,
            "frames_dropped": 1,
            "codec": "video/VP8",
            "nack_enabled": False,
            "nack_mode": "disabled",
            "nack_count": 6,
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
                        "latest-room": {
                            "members": [
                                {"peer_id": "peer-a", "display_name": "Alice"},
                                {"peer_id": "peer-b", "display_name": "Bob"},
                                {"peer_id": "peer-c", "display_name": "Charlie"},
                                {"peer_id": "peer-d", "display_name": "Dana"},
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
                    "room_id": "latest-room",
                    "server_time": 1778140802,
                    "members": [
                        {"peer_id": "peer-a", "display_name": "Alice"},
                        {"peer_id": "peer-b", "display_name": "Bob"},
                        {"peer_id": "peer-c", "display_name": "Charlie"},
                        {"peer_id": "peer-d", "display_name": "Dana"},
                    ],
                    "peers": [
                        {"peer_id": "peer-a", "remote_peer_id": "peer-b"},
                        {"peer_id": "peer-c", "remote_peer_id": "peer-d"},
                    ],
                    "latest": [older_sample, newest_sample],
                    "history": [older_sample, newest_sample],
                },
            },
        ),
    )

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id=latest-room")

    latest_text = page.locator("#latestStatsPanel")
    expect(latest_text).to_contain_text("Charlie (peer-c) -> Dana (peer-d)", timeout=10000)
    expect(latest_text).to_contain_text("88 ms")
    expect(page.locator("#nackSummary")).to_have_text("NACK: disabled / 6")


def test_dashboard_filters_live_stats_by_peer_pair_and_metric(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    samples = [
        {
            "sample_index": 1,
            "timestamp": 1778140730,
            "room_id": "filter-room",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "metrics": {
                "connection_state": "connected",
                "ice_connection_state": "connected",
                "rtt_ms": 10,
                "packet_loss_rate": 0,
                "packets_sent": 100,
                "packets_received": 100,
                "packets_lost": 0,
                "jitter_ms": 1,
                "bitrate_kbps": 100,
                "fps": 24,
                "frame_width": 320,
                "frame_height": 180,
                "codec": "video/VP8",
                "nack_mode": "enabled",
                "nack_count": 1,
            },
        },
        {
            "sample_index": 2,
            "timestamp": 1778140801,
            "room_id": "filter-room",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "metrics": {
                "connection_state": "connected",
                "ice_connection_state": "connected",
                "rtt_ms": 20,
                "packet_loss_rate": 1,
                "packets_sent": 110,
                "packets_received": 108,
                "packets_lost": 1,
                "jitter_ms": 2,
                "bitrate_kbps": 200,
                "fps": 25,
                "frame_width": 320,
                "frame_height": 180,
                "codec": "video/VP8",
                "nack_mode": "enabled",
                "nack_count": 2,
            },
        },
        {
            "sample_index": 3,
            "timestamp": 1778140802,
            "room_id": "filter-room",
            "peer_id": "peer-c",
            "remote_peer_id": "peer-d",
            "metrics": {
                "connection_state": "connected",
                "ice_connection_state": "connected",
                "rtt_ms": 90,
                "packet_loss_rate": 7,
                "packets_sent": 210,
                "packets_received": 190,
                "packets_lost": 9,
                "jitter_ms": 8,
                "bitrate_kbps": 900,
                "fps": 30,
                "frame_width": 640,
                "frame_height": 360,
                "codec": "video/VP8",
                "nack_mode": "disabled",
                "nack_count": 6,
            },
        },
        {
            "sample_index": 4,
            "timestamp": 1778140803,
            "room_id": "filter-room",
            "peer_id": "peer-c",
            "remote_peer_id": "peer-d",
            "metrics": {
                "connection_state": "connected",
                "ice_connection_state": "connected",
                "rtt_ms": 80,
                "packet_loss_rate": 6,
                "packets_sent": 220,
                "packets_received": 202,
                "packets_lost": 8,
                "jitter_ms": 7,
                "bitrate_kbps": 840,
                "fps": 29,
                "frame_width": 640,
                "frame_height": 360,
                "codec": "video/VP8",
                "nack_mode": "disabled",
                "nack_count": 7,
            },
        },
    ]
    page.route(
        re.compile(r".*/api/webrtc/members\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            json={"ok": True, "data": {"rooms": {}}},
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
                    "room_id": "filter-room",
                    "server_time": 1778140803,
                    "members": [
                        {"peer_id": "peer-a", "display_name": "Alice"},
                        {"peer_id": "peer-b", "display_name": "Bob"},
                        {"peer_id": "peer-c", "display_name": "Charlie"},
                        {"peer_id": "peer-d", "display_name": "Dana"},
                    ],
                    "peers": [
                        {"peer_id": "peer-a", "remote_peer_id": "peer-b"},
                        {"peer_id": "peer-c", "remote_peer_id": "peer-d"},
                    ],
                    "latest": [samples[1], samples[3]],
                    "history": samples,
                },
            },
        ),
    )

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id=filter-room")
    expect(page.locator("#livePeerPairSelect")).to_be_visible()
    expect(page.locator("#liveTrendChart svg")).to_be_visible(timeout=10000)

    all_result = page.evaluate(
        """
        () => {
          const hooks = window.__RTCTrainingDashboardTestHooks;
          hooks.setLiveMetric("bitrate_kbps");
          return {
            pair: document.querySelector("#livePeerPairSelect").value,
            lineCount: document.querySelectorAll("#liveTrendChart svg polyline").length,
            trend: document.querySelector("#liveTrendChart").textContent
          };
        }
        """
    )

    assert all_result["pair"] == "all"
    assert all_result["lineCount"] == 2
    assert "Alice (peer-a) -> Bob (peer-b)" in all_result["trend"]
    assert "Charlie (peer-c) -> Dana (peer-d)" in all_result["trend"]

    stable_options = page.evaluate(
        """
        async () => {
          const hooks = window.__RTCTrainingDashboardTestHooks;
          const select = document.querySelector("#livePeerPairSelect");
          const optionBefore = select.options[1];
          await hooks.loadLiveStats();
          return {
            sameOptionNode: optionBefore === select.options[1],
            value: select.value,
            optionCount: select.options.length
          };
        }
        """
    )

    assert stable_options["sameOptionNode"] is True
    assert stable_options["value"] == "all"
    assert stable_options["optionCount"] == 3

    result = page.evaluate(
        """
        () => {
          const hooks = window.__RTCTrainingDashboardTestHooks;
          hooks.setLivePeerPair("peer-a->peer-b");
          return {
            pair: document.querySelector("#livePeerPairSelect").value,
            metric: document.querySelector("#liveMetricSelect").value,
            latest: document.querySelector("#latestStatsPanel").textContent,
            peerPairs: document.querySelector("#peerPairList").textContent,
            lineCount: document.querySelectorAll("#liveTrendChart svg polyline").length,
            rows: document.querySelectorAll("#statsHistoryTable tbody tr").length,
            trend: document.querySelector("#liveTrendChart").textContent
          };
        }
        """
    )

    assert result["pair"] == "peer-a->peer-b"
    assert result["metric"] == "bitrate_kbps"
    assert "Alice (peer-a) -> Bob (peer-b)" in result["latest"]
    assert "Charlie" not in result["latest"]
    assert "Bitrate 200 kbps" in result["peerPairs"]
    assert result["lineCount"] == 1
    assert result["rows"] == 2
    assert "Bitrate Trend" in result["trend"]
    points = page.locator("#liveTrendChart svg polyline").first.get_attribute("points").split(" ")
    assert len(points) == 1


def test_dashboard_compares_multiple_csv_files(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    result = page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "nack_on.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s1,peer-a,peer-b,20,1,5,900,30,enabled,off",
              "2,1001,room1,s1,peer-a,peer-b,30,3,7,700,28,enabled,off"
            ].join("\\n")
          },
          {
            name: "nack_off.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s2,peer-a,peer-b,60,8,12,500,20,disabled,off"
            ].join("\\n")
          }
        ])
        """
    )

    assert result["ok"] is True
    assert result["files"][0]["sample_count"] == 2
    assert result["files"][0]["avg_rtt_ms"] == 25
    assert result["files"][1]["avg_packet_loss_rate"] == 8
    expect(page.locator("#csvState")).to_have_text("csv_ready")
    expect(page.locator("#csvValidationPanel")).to_contain_text("nack_on.csv: ok")
    expect(page.locator("#csvComparisonTable tbody tr")).to_have_count(2)
    expect(page.locator("#csvTrendComparison")).to_contain_text("RTT best: nack_on.csv")


def test_dashboard_generates_experiment_comparison_from_csv_files(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    result = page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "nack_on_abr_off.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode,sender_max_bitrate_bps",
              "1,1000,room1,s1,peer-a,peer-b,20,1,5,700,30,enabled,off,800000",
              "2,1001,room1,s1,peer-a,peer-b,22,1,5,720,30,enabled,off,800000"
            ].join("\\n")
          },
          {
            name: "nack_off_abr_off.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode,sender_max_bitrate_bps",
              "1,1000,room1,s2,peer-a,peer-b,60,8,12,500,22,disabled,off,300000"
            ].join("\\n")
          },
          {
            name: "nack_on_abr_on.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode,sender_max_bitrate_bps",
              "1,1000,room1,s3,peer-a,peer-b,24,2,6,950,29,enabled,on,1200000"
            ].join("\\n")
          }
        ])
        """
    )

    assert result["ok"] is True
    panel = page.locator("#experimentComparisonPanel")
    expect(panel).to_contain_text("NACK: enabled lower loss than disabled")
    expect(panel).to_contain_text("ABR: on higher bitrate than off")
    expect(panel).to_contain_text("Bitrate config: 1200 kbps highest configured target")


def test_dashboard_csv_modules_parse_and_summarize_rows(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    result = page.evaluate(
        """
        () => {
          const parser = window.RTCTrainingDashboardCsvParser;
          const analysis = window.RTCTrainingDashboardCsvAnalysis;
          const parsed = parser.parseCsvText([
            "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
            "1,1000,room1,s1,peer-a,peer-b,20,1,5,900,30,enabled,off",
            "2,1001,room1,s1,peer-a,peer-b,30,3,7,700,28,enabled,off"
          ].join("\\n"));
          return {
            headers: parsed.headers,
            rowCount: parsed.rows.length,
            quoted: parser.parseCsvLine("peer-a,\\"Alice, QA\\""),
            summary: analysis.summarizeCsvFile({
              name: "baseline.csv",
              text: [
                "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
                "1,1000,room1,s1,peer-a,peer-b,20,1,5,900,30,enabled,off",
                "2,1001,room1,s1,peer-a,peer-b,30,3,7,700,28,enabled,off"
              ].join("\\n")
            })
          };
        }
        """
    )

    assert "rtt_ms" in result["headers"]
    assert result["rowCount"] == 2
    assert result["quoted"] == ["peer-a", "Alice, QA"]
    assert result["summary"]["ok"] is True
    assert result["summary"]["sample_count"] == 2
    assert result["summary"]["avg_rtt_ms"] == 25


def test_dashboard_live_presenter_formats_peer_pairs_and_newest_sample(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    result = page.evaluate(
        """
        () => {
          const presenter = window.RTCTrainingDashboardLivePresenter;
          const labels = presenter.buildPeerLabelsFromMembers([
            { peer_id: "peer-alpha-1234567890", display_name: "Alice" },
            { peer_id: "peer-beta-1234567890", display_name: "Bob" }
          ]);
          const newest = presenter.newestSample([
            { peer_id: "older", sample_index: 1 },
            { peer_id: "newer", sample_index: 4 }
          ]);
          return {
            pair: presenter.peerPairLabel("peer-alpha-1234567890", "peer-beta-1234567890", labels),
            missing: presenter.peerPairLabel("peer-alpha-1234567890", "peer-missing-1234567890", labels),
            newestPeer: newest.peer_id
          };
        }
        """
    )

    assert result["pair"] == "Alice (peer-alpha-1...) -> Bob (peer-beta-12...)"
    assert result["missing"] == "Alice (peer-alpha-1...) -> peer-missing..."
    assert result["newestPeer"] == "newer"


def test_dashboard_api_client_builds_origin_scoped_urls(
    browser_context,
    dashboard_server,
):
    page = browser_context.new_page()
    page.goto(f"{dashboard_server}/?webrtc_origin=https%3A%2F%2Flocalhost%3A8080")

    result = page.evaluate(
        """
        () => window.RTCTrainingDashboardApiClient.buildUrl(
          "/api/webrtc/stats",
          { room_id: "room1", peer_id: "alice" }
        )
        """
    )

    assert result == "/api/webrtc/stats?origin=https%3A%2F%2Flocalhost%3A8080&room_id=room1&peer_id=alice"


def test_dashboard_reports_csv_field_validation_errors(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    result = page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "broken.csv",
            text: "sample_index,room_id\\n1,room1"
          }
        ])
        """
    )

    assert result["ok"] is False
    expect(page.locator("#csvState")).to_have_text("csv_invalid")
    expect(page.locator("#csvValidationPanel")).to_contain_text("broken.csv: missing")


def test_dashboard_csv_metric_selection_updates_trend_comparison(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "stable.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s1,peer-a,peer-b,30,2,5,600,24,enabled,off"
            ].join("\\n")
          },
          {
            name: "fast.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s2,peer-a,peer-b,50,4,8,1200,30,enabled,off"
            ].join("\\n")
          }
        ])
        """
    )

    expect(page.locator("#csvTrendComparison")).to_contain_text("RTT best: stable.csv")
    selected = page.evaluate("window.__RTCTrainingDashboardTestHooks.setCsvMetric('bitrate_kbps')")

    assert selected == "bitrate_kbps"
    expect(page.locator("#csvMetricSelect")).to_have_value("bitrate_kbps")
    expect(page.locator("#csvTrendComparison")).to_contain_text("Bitrate best: fast.csv")
    expect(page.locator("#csvTrendComparison")).not_to_contain_text("RTT best")


def test_dashboard_renders_csv_trend_chart(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "nack_on.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s1,peer-a,peer-b,20,1,5,900,30,enabled,off",
              "2,1001,room1,s1,peer-a,peer-b,35,3,7,700,28,enabled,off"
            ].join("\\n")
          },
          {
            name: "abr_on.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "1,1000,room1,s2,peer-a,peer-b,50,4,8,800,24,enabled,on",
              "2,1001,room1,s2,peer-a,peer-b,28,2,6,1100,30,enabled,on"
            ].join("\\n")
          }
        ])
        """
    )

    expect(page.locator("#csvTrendChart svg")).to_have_count(1)
    expect(page.locator("#csvTrendChart polyline")).to_have_count(2)
    expect(page.locator("#csvTrendChart")).to_contain_text("nack_on.csv")
    expect(page.locator("#csvTrendChart")).to_contain_text("abr_on.csv")


def test_dashboard_normalizes_csv_trend_sample_index_per_file(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}")
    page.evaluate(
        """
        window.__RTCTrainingDashboardTestHooks.analyzeCsvTexts([
          {
            name: "late_start_a.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "120,1000,room1,s1,peer-a,peer-b,20,1,5,900,30,enabled,off",
              "121,1001,room1,s1,peer-a,peer-b,25,2,6,850,29,enabled,off"
            ].join("\\n")
          },
          {
            name: "late_start_b.csv",
            text: [
              "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
              "900,1000,room1,s2,peer-a,peer-b,50,4,8,800,24,enabled,on",
              "901,1001,room1,s2,peer-a,peer-b,28,2,6,1100,30,enabled,on"
            ].join("\\n")
          }
        ])
        """
    )

    expect(page.locator("#csvTrendChart")).to_contain_text("Normalized Sample Index")
    first_x_values = page.locator("#csvTrendChart polyline").evaluate_all(
        """lines => lines.map(line => Number(line.getAttribute("points").split(" ")[0].split(",")[0]))"""
    )
    assert first_x_values == [62, 62]


def test_dashboard_loads_finished_session_csv_files(
    browser_context,
    dashboard_server,
    webrtc_https_server,
):
    page = browser_context.new_page()
    page.route(
        re.compile(r".*/api/webrtc/stats/test/sessions\\?.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            json={
                "ok": True,
                "data": {
                    "sessions": [
                        {
                            "test_session_id": "s1",
                            "room_id": "room1",
                            "peer_id": "peer-a",
                            "preset": "abr_simple",
                            "weak_network": {"profile": "loss_5"},
                            "duration_seconds": 72,
                            "sample_count": 2,
                            "csv_files": [
                                {
                                    "remote_peer_id": "peer-b",
                                    "display_name": "Alice peer-a -> peer-b | abr_simple | nack enabled | abr on | abr | 72s | 20260507-080000Z",
                                    "filename": "20260507-080000Z_Alice_peer-a_to_peer-b_abr_simple_nack-enabled_abr-on_bitrate-abr_72s.csv",
                                    "download_url": "/stats/test/download/room1/s1/peer-a/peer-b.csv",
                                }
                            ],
                        }
                    ]
                },
            },
        ),
    )
    page.route(
        re.compile(r".*/api/webrtc/stats/test/download/.*"),
        lambda route: route.fulfill(
            status=200,
            content_type="text/csv",
            body="\n".join([
                "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,rtt_ms,packet_loss_rate,jitter_ms,bitrate_kbps,fps,nack_mode,abr_mode",
                "1,1000,room1,s1,peer-a,peer-b,25,2,5,900,28,enabled,on",
            ]),
        ),
    )

    page.goto(f"{dashboard_server}/?webrtc_origin={webrtc_https_server}&room_id=room1")
    result = page.evaluate("window.__RTCTrainingDashboardTestHooks.loadTestSessionCsvList()")

    assert result["sessions"][0]["test_session_id"] == "s1"
    expect(page.locator("#testSessionCsvSelect")).to_contain_text("Alice peer-a -> peer-b")
    expect(page.locator("#testSessionCsvSelect")).to_contain_text("72s")
    loaded = page.evaluate("window.__RTCTrainingDashboardTestHooks.loadSelectedSessionCsv()")

    assert loaded["ok"] is True
    expect(page.locator("#csvState")).to_have_text("csv_ready")
    expect(page.locator("#csvValidationPanel")).to_contain_text("20260507-080000Z_Alice_peer-a_to_peer-b")


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
    expect(dashboard.locator("#meshTopology")).to_contain_text("Jitter")
    expect(dashboard.locator("#meshTopology")).to_contain_text("FPS")
    expect(dashboard.locator("#meshTopology")).to_contain_text("NACK")
    first_edge_pair = dashboard.locator("#meshTopology li").nth(0).get_attribute("data-peer-pair")
    assert first_edge_pair and "->" in first_edge_pair


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
