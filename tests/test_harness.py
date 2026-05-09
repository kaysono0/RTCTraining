import subprocess
import sys

from aiohttp import web
import pytest

from automation.harness.http_checks import (
    HarnessCheckError,
    check_json_ok,
    check_text_contains,
)
from automation.harness.process_manager import ManagedProcess, start_python_module
from automation.harness.smoke import build_dashboard_proxy_url, connect_host


def test_managed_process_terminates_child_process():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    managed = ManagedProcess("sleep-test", process)

    managed.stop(timeout=2)

    assert process.poll() is not None


@pytest.mark.asyncio
async def test_check_text_contains_passes_for_expected_text(aiohttp_server):
    async def handler(request):
        return web.Response(text="RTCTraining ready")

    app = web.Application()
    app.router.add_get("/", handler)
    server = await aiohttp_server(app)

    await check_text_contains(f"http://{server.host}:{server.port}/", "RTCTraining")


@pytest.mark.asyncio
async def test_check_json_ok_rejects_failed_envelope(aiohttp_server):
    async def handler(request):
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "code": "bad_request",
                    "message": "bad",
                    "details": {},
                },
            },
            status=400,
        )

    app = web.Application()
    app.router.add_get("/api", handler)
    server = await aiohttp_server(app)

    try:
        await check_json_ok(f"http://{server.host}:{server.port}/api")
    except HarnessCheckError as exc:
        assert "returned HTTP 400" in str(exc)
    else:
        raise AssertionError("check_json_ok should reject failed envelopes")


@pytest.mark.asyncio
async def test_check_json_ok_rejects_http_error_with_ok_payload(aiohttp_server):
    async def handler(request):
        return web.json_response({"ok": True, "data": {}}, status=500)

    app = web.Application()
    app.router.add_get("/api", handler)
    server = await aiohttp_server(app)

    try:
        await check_json_ok(f"http://{server.host}:{server.port}/api")
    except HarnessCheckError as exc:
        assert "returned HTTP 500" in str(exc)
    else:
        raise AssertionError("check_json_ok should reject non-2xx responses")


@pytest.mark.asyncio
async def test_check_json_ok_rejects_200_failed_envelope(aiohttp_server):
    async def handler(request):
        return web.json_response(
            {
                "ok": False,
                "error": {
                    "code": "bad_request",
                    "message": "bad",
                    "details": {},
                },
            }
        )

    app = web.Application()
    app.router.add_get("/api", handler)
    server = await aiohttp_server(app)

    try:
        await check_json_ok(f"http://{server.host}:{server.port}/api")
    except HarnessCheckError as exc:
        assert "expected ok JSON envelope" in str(exc)
    else:
        raise AssertionError("check_json_ok should reject failed envelopes")


def test_start_python_module_uses_requested_python(monkeypatch):
    captured = {}

    class FakeProcess:
        stdout = None
        stderr = None

        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    managed = start_python_module(
        "fake",
        "example.module",
        "run",
        python_executable="/custom/python",
    )

    assert managed.name == "fake"
    assert captured["command"] == ["/custom/python", "-m", "example.module", "run"]
    assert captured["kwargs"]["text"] is True


def test_dashboard_proxy_url_uses_encoded_origin_and_requested_dashboard_host():
    dashboard_origin = f"http://{connect_host('localhost')}:18081"
    url = build_dashboard_proxy_url(
        dashboard_origin,
        "https://localhost:18080",
        room_id="room 1",
    )

    assert url == (
        "http://localhost:18081/api/webrtc/stats/peers"
        "?origin=https%3A%2F%2Flocalhost%3A18080&room_id=room+1"
    )


def test_connect_host_rewrites_wildcard_bind_address_for_local_checks():
    assert connect_host("0.0.0.0") == "127.0.0.1"
    assert connect_host("localhost") == "localhost"
