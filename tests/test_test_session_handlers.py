import pytest
import pytest_asyncio

from src.webrtc.app import create_webrtc_app


@pytest_asyncio.fixture
async def client(aiohttp_client):
    app = create_webrtc_app()
    return await aiohttp_client(app)


@pytest_asyncio.fixture
async def csv_client(aiohttp_client, tmp_path):
    app = create_webrtc_app(test_sessions_dir=tmp_path)
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


@pytest.mark.asyncio
async def test_test_session_finish_writes_isolated_csv_files(csv_client):
    started_response = await csv_client.post(
        "/stats/test/start",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "preset": "nack_on",
            "metadata": {"note": "baseline"},
        },
    )
    session = (await started_response.json())["data"]["session"]

    await csv_client.post(
        "/stats",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "test_session_id": session["test_session_id"],
            "metrics": {
                "rtt_ms": 10.0,
                "nack_mode": "enabled",
                "bitrate_mode": "manual",
                "sender_max_bitrate_bps": 600000,
                "abr_mode": "on",
                "abr_target_bitrate_bps": 450000,
                "abr_decision": "increase",
            },
        },
    )
    await csv_client.post(
        "/stats",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-c",
            "test_session_id": session["test_session_id"],
            "metrics": {"rtt_ms": 20.0, "nack_mode": "enabled"},
        },
    )
    await csv_client.post(
        "/stats",
        json={
            "room_id": "room2",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "test_session_id": session["test_session_id"],
            "metrics": {"rtt_ms": 30.0, "nack_mode": "enabled"},
        },
    )

    finished_response = await csv_client.post(
        "/stats/test/finish",
        json={"test_session_id": session["test_session_id"]},
    )
    finished = await finished_response.json()

    assert finished_response.status == 200
    files = finished["data"]["session"]["csv_files"]
    assert [file["remote_peer_id"] for file in files] == ["peer-b", "peer-c"]
    assert all(file["room_id"] == "room1" for file in files)
    assert all(file["test_session_id"] == session["test_session_id"] for file in files)

    csv_response = await csv_client.get(files[0]["download_url"])
    csv_body = await csv_response.text()

    assert csv_response.status == 200
    assert csv_response.headers["Content-Type"].startswith("text/csv")
    assert ",room1," in csv_body
    assert ",peer-a,peer-b," in csv_body
    assert "bitrate_mode,sender_max_bitrate_bps,abr_mode,abr_target_bitrate_bps,abr_decision" in csv_body
    assert ",manual,600000,on,450000,increase" in csv_body
    assert ",peer-c," not in csv_body
    assert ",room2," not in csv_body
