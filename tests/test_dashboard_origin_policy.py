import pytest

from src.dashboard.origin_policy import OriginPolicy
from src.dashboard.server import create_dashboard_app
from src.webrtc.config import Settings


def test_origin_policy_allows_only_configured_origins():
    policy = OriginPolicy.from_csv(
        "https://localhost:8080,http://127.0.0.1:18080,https://rtc.example.test:8443"
    )

    assert policy.is_allowed("https://localhost:8080")
    assert policy.is_allowed("http://127.0.0.1:18080")
    assert policy.is_allowed("https://rtc.example.test:8443")
    assert not policy.is_allowed("https://localhost:18080")
    assert not policy.is_allowed("http://127.0.0.1:8080")


def test_origin_policy_rejects_non_http_and_unlisted_origins():
    policy = OriginPolicy.from_csv("https://localhost:8080")

    assert not policy.is_allowed("file:///tmp/example")
    assert not policy.is_allowed("https://example.com")
    assert not policy.is_allowed("not-a-url")


def test_origin_policy_does_not_treat_hostnames_as_wildcards():
    policy = OriginPolicy.from_csv("localhost,127.0.0.1")

    assert not policy.is_allowed("https://localhost:8080")
    assert not policy.is_allowed("http://127.0.0.1:18080")


def test_origin_policy_from_csv_trims_empty_values():
    policy = OriginPolicy.from_csv(" https://localhost:8080, , https://127.0.0.1:8080 ")

    assert policy.is_allowed("https://localhost:8080")
    assert policy.is_allowed("https://127.0.0.1:8080")


@pytest.mark.asyncio
async def test_dashboard_proxy_rejects_unlisted_origin(aiohttp_client):
    settings = Settings(
        dashboard_origin_allowlist="https://localhost:8080",
        local_webrtc_origin="https://localhost:8080",
    )
    client = await aiohttp_client(create_dashboard_app(settings=settings))

    response = await client.get(
        "/api/webrtc/stats?origin=https://example.com&room_id=room1"
    )
    payload = await response.json()

    assert response.status == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "bad_request"
    assert payload["error"]["message"] == "origin is not allowed"
