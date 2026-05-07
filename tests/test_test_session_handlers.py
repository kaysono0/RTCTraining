import pytest
import pytest_asyncio

from src.webrtc.app import create_webrtc_app


@pytest_asyncio.fixture
async def client(aiohttp_client):
    app = create_webrtc_app()
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_test_session_start_finish_cancel_routes(client):
    started_response = await client.post(
        "/stats/test/start",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "preset": "nack_on",
            "metadata": {"note": "baseline"},
            "weak_network": {"profile": "none"},
        },
    )
    started = await started_response.json()

    assert started_response.status == 200
    assert started["ok"] is True
    session = started["data"]["session"]
    assert session["status"] == "running"
    assert session["room_id"] == "room1"
    assert session["peer_id"] == "peer-a"
    assert session["preset"] == "nack_on"
    assert session["metadata"] == {"note": "baseline"}
    assert session["weak_network"] == {"profile": "none"}

    await client.post(
        "/stats",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "test_session_id": session["test_session_id"],
            "metrics": {"rtt_ms": 10.0},
        },
    )
    await client.post(
        "/stats",
        json={
            "room_id": "room2",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "test_session_id": session["test_session_id"],
            "metrics": {"rtt_ms": 20.0},
        },
    )

    finished_response = await client.post(
        "/stats/test/finish",
        json={"test_session_id": session["test_session_id"]},
    )
    finished = await finished_response.json()

    assert finished_response.status == 200
    assert finished["data"]["session"]["status"] == "finished"
    assert finished["data"]["session"]["sample_count"] == 1

    canceled_response = await client.post(
        "/stats/test/cancel",
        json={"test_session_id": session["test_session_id"]},
    )
    canceled = await canceled_response.json()

    assert canceled_response.status == 200
    assert canceled["data"]["session"]["status"] == "canceled"


@pytest.mark.asyncio
async def test_test_session_start_requires_room_and_peer(client):
    response = await client.post("/stats/test/start", json={"room_id": "room1"})

    assert response.status == 400
    assert await response.json() == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "peer_id is required",
            "details": {"field": "peer_id"},
        },
    }
