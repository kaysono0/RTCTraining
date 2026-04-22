import pytest
import pytest_asyncio

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
    assert "RTCTraining" in body
    assert "chat_real_stats.js" in body
    assert "chat_real_bootstrap.js" in body
    assert "window.__RTCTrainingTestHooks" in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asset", "expected"),
    [
        ("chat_real_bootstrap.js", "bootstrapRTCTraining"),
        ("chat_real_stats.js", "RTCTrainingStats"),
    ],
)
async def test_webrtc_static_asset_loads(webrtc_client, asset, expected):
    response = await webrtc_client.get(f"/static/webrtc/{asset}")
    body = await response.text()

    assert response.status == 200
    assert expected in body


@pytest.mark.asyncio
async def test_dashboard_homepage_loads_independent_shell(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert "RTCTraining Dashboard" in body
    assert "WebRTC Service" in body


@pytest.mark.asyncio
async def test_dashboard_homepage_contains_inline_service_check_fallback(dashboard_client):
    response = await dashboard_client.get("/")
    body = await response.text()

    assert response.status == 200
    assert "window.__RTCTrainingDashboardInlineBootstrap" in body
    assert "/api/webrtc/members?origin=" in body
