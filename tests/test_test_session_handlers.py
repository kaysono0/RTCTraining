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
            "display_name": "Alice",
            "preset": "nack_on",
            "planned_duration_seconds": 45,
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
    assert session["display_name"] == "Alice"
    assert session["preset"] == "nack_on"
    assert session["planned_duration_seconds"] == 45
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
    assert isinstance(finished["data"]["session"]["duration_seconds"], int)

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
    assert all("path" not in file for file in files)
    assert files[0]["filename"].endswith(".csv")
    assert "nack-enabled" in files[0]["filename"]
    assert "abr-on" in files[0]["filename"]
    assert "bitrate-600kbps" in files[0]["filename"]
    assert files[0]["display_name"]
    assert files[0]["relative_path"].endswith(f"/peer-a/{files[0]['filename']}")

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


@pytest.mark.asyncio
async def test_test_session_list_returns_finished_sessions_with_csv_files(csv_client):
    started_response = await csv_client.post(
        "/stats/test/start",
        json={
            "room_id": "room1",
            "peer_id": "peer-a",
            "preset": "abr_simple",
            "metadata": {"note": "compare"},
            "weak_network": {"profile": "loss_5"},
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
            "metrics": {"rtt_ms": 10.0, "nack_mode": "enabled", "abr_mode": "on"},
        },
    )
    await csv_client.post(
        "/stats/test/finish",
        json={"test_session_id": session["test_session_id"]},
    )

    response = await csv_client.get("/stats/test/sessions?room_id=room1")
    payload = await response.json()

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["data"]["sessions"][0]["test_session_id"] == session["test_session_id"]
    assert payload["data"]["sessions"][0]["preset"] == "abr_simple"
    assert payload["data"]["sessions"][0]["weak_network"] == {"profile": "loss_5"}
    assert payload["data"]["sessions"][0]["sample_count"] == 1
    assert "duration_seconds" in payload["data"]["sessions"][0]
    assert payload["data"]["sessions"][0]["csv_files"][0]["remote_peer_id"] == "peer-b"
    assert payload["data"]["sessions"][0]["csv_files"][0]["display_name"]


@pytest.mark.asyncio
async def test_finish_missing_test_session_id_returns_400(client):
    response = await client.post("/stats/test/finish", json={})
    assert response.status == 400
    body = await response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_finish_nonexistent_session_returns_404(client):
    response = await client.post("/stats/test/finish", json={"test_session_id": "no-such-session"})
    assert response.status == 404
    body = await response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_cancel_missing_test_session_id_returns_400(client):
    response = await client.post("/stats/test/cancel", json={})
    assert response.status == 400
    body = await response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_cancel_nonexistent_session_returns_404(client):
    response = await client.post("/stats/test/cancel", json={"test_session_id": "no-such-session"})
    assert response.status == 404
    body = await response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_download_csv_rejects_path_traversal(csv_client):
    response = await csv_client.get("/stats/test/download/../../../etc/passwd")
    assert response.status == 404


@pytest.mark.asyncio
async def test_download_csv_nonexistent_file_returns_404(csv_client):
    response = await csv_client.get(
        "/stats/test/download/room1/session-x/peer-a/nonexistent.csv"
    )
    assert response.status == 404


@pytest.mark.asyncio
async def test_list_sessions_without_room_id_returns_all_finished(csv_client):
    started1 = await csv_client.post(
        "/stats/test/start",
        json={"room_id": "room1", "peer_id": "peer-a", "preset": "nack_on"},
    )
    s1 = (await started1.json())["data"]["session"]
    started2 = await csv_client.post(
        "/stats/test/start",
        json={"room_id": "room2", "peer_id": "peer-a", "preset": "abr_simple"},
    )
    s2 = (await started2.json())["data"]["session"]
    await csv_client.post(
        "/stats/test/finish", json={"test_session_id": s1["test_session_id"]}
    )
    await csv_client.post(
        "/stats/test/finish", json={"test_session_id": s2["test_session_id"]}
    )

    response = await csv_client.get("/stats/test/sessions")
    payload = await response.json()

    assert response.status == 200
    assert payload["ok"] is True
    ids = [s["test_session_id"] for s in payload["data"]["sessions"]]
    assert s1["test_session_id"] in ids
    assert s2["test_session_id"] in ids


@pytest.mark.asyncio
async def test_start_with_empty_body_handled_gracefully(client):
    response = await client.post("/stats/test/start", data="not json")
    assert response.status == 400
    body = await response.json()
    assert body["ok"] is False


@pytest.mark.asyncio
async def test_finish_session_with_no_stats_samples(csv_client):
    started = await csv_client.post(
        "/stats/test/start",
        json={"room_id": "room1", "peer_id": "peer-a"},
    )
    session = (await started.json())["data"]["session"]
    finished_resp = await csv_client.post(
        "/stats/test/finish", json={"test_session_id": session["test_session_id"]}
    )
    finished = await finished_resp.json()
    assert finished["data"]["session"]["status"] == "finished"
    assert finished["data"]["session"]["sample_count"] == 0
    assert len(finished["data"]["session"]["csv_files"]) == 1
    assert finished["data"]["session"]["csv_files"][0]["remote_peer_id"] == "none"
