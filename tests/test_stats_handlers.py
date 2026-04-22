import pytest
import pytest_asyncio

from src.webrtc.app import create_webrtc_app


@pytest_asyncio.fixture
async def client(aiohttp_client):
    app = create_webrtc_app()
    return await aiohttp_client(app)


def stats_payload(**overrides):
    payload = {
        "room_id": "room1",
        "peer_id": "peer-a",
        "remote_peer_id": "peer-b",
        "test_session_id": None,
        "metrics": {
            "rtt_ms": 12.5,
            "packets_lost": 1,
            "jitter_ms": 3.0,
            "bitrate_kbps": 512.0,
            "fps": 30.0,
            "frame_width": 640,
            "frame_height": 480,
            "codec": "VP8",
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_post_stats_updates_latest_history_and_peers(client):
    response = await client.post("/stats", json=stats_payload())

    latest = await client.get("/stats?room_id=room1")
    history = await client.get(
        "/stats/history?room_id=room1&peer_id=peer-a&remote_peer_id=peer-b"
    )
    peers = await client.get("/stats/peers?room_id=room1")

    assert response.status == 200
    posted = await response.json()
    assert posted["ok"] is True
    assert posted["data"]["sample"]["sample_index"] == 1
    assert await latest.json() == {
        "ok": True,
        "data": {"samples": [posted["data"]["sample"]]},
    }
    assert await history.json() == {
        "ok": True,
        "data": {"samples": [posted["data"]["sample"]]},
    }
    assert await peers.json() == {
        "ok": True,
        "data": {
            "peers": [
                {"room_id": "room1", "peer_id": "peer-a", "remote_peer_id": "peer-b"}
            ]
        },
    }


@pytest.mark.asyncio
async def test_stats_queries_are_room_scoped(client):
    await client.post("/stats", json=stats_payload(room_id="room1", metrics={"rtt_ms": 10.0}))
    room2 = await client.post(
        "/stats",
        json=stats_payload(room_id="room2", metrics={"rtt_ms": 20.0}),
    )

    latest = await client.get("/stats?room_id=room1")
    history = await client.get("/stats/history?room_id=room2")
    latest_payload = await latest.json()

    assert len(latest_payload["data"]["samples"]) == 1
    assert latest_payload["data"]["samples"][0]["room_id"] == "room1"
    assert await history.json() == {
        "ok": True,
        "data": {"samples": [(await room2.json())["data"]["sample"]]},
    }


@pytest.mark.asyncio
async def test_missing_stats_required_field_returns_bad_request(client):
    response = await client.post(
        "/stats",
        json={"room_id": "room1", "peer_id": "peer-a", "metrics": {}},
    )

    assert response.status == 400
    assert await response.json() == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "remote_peer_id is required",
            "details": {"field": "remote_peer_id"},
        },
    }


@pytest.mark.asyncio
async def test_clear_stats_removes_room_history(client):
    await client.post("/stats", json=stats_payload(room_id="room1"))
    await client.post("/stats", json=stats_payload(room_id="room2"))

    cleared = await client.post("/clear_stats", json={"room_id": "room1"})
    room1 = await client.get("/stats/history?room_id=room1")
    room2 = await client.get("/stats/history?room_id=room2")

    assert await cleared.json() == {"ok": True, "data": {"removed": 1}}
    assert await room1.json() == {"ok": True, "data": {"samples": []}}
    assert len((await room2.json())["data"]["samples"]) == 1
