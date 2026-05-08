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
            "nack_enabled": False,
            "nack_mode": "disabled",
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
    assert posted["data"]["sample"]["timestamp"] is not None
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
                {
                    "room_id": "room1",
                    "peer_id": "peer-a",
                    "remote_peer_id": "peer-b",
                    "last_sample_timestamp": posted["data"]["sample"]["timestamp"],
                    "last_sample_index": posted["data"]["sample"]["sample_index"],
                }
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

    cleared_payload = await cleared.json()
    assert cleared_payload["ok"] is True
    assert cleared_payload["data"]["removed"] == 1
    assert cleared_payload["data"]["snapshot"]["room_id"] == "room1"
    assert cleared_payload["data"]["snapshot"]["peers"] == []
    assert cleared_payload["data"]["snapshot"]["latest"] == []
    assert cleared_payload["data"]["snapshot"]["history"] == []
    assert await room1.json() == {"ok": True, "data": {"samples": []}}
    assert len((await room2.json())["data"]["samples"]) == 1


@pytest.mark.asyncio
async def test_dashboard_snapshot_returns_members_stats_and_revision(client):
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "peer-a", "display_name": "Alice"},
    )
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "peer-b", "display_name": "Bob"},
    )
    posted = await client.post("/stats", json=stats_payload())

    response = await client.get("/dashboard/snapshot?room_id=room1")
    payload = await response.json()
    sample = (await posted.json())["data"]["sample"]

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["data"]["room_id"] == "room1"
    assert payload["data"]["stats_revision"] == 1
    assert payload["data"]["server_time"] is not None
    assert payload["data"]["members"] == [
        {"peer_id": "peer-a", "display_name": "Alice"},
        {"peer_id": "peer-b", "display_name": "Bob"},
    ]
    assert payload["data"]["peers"] == [
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "last_sample_timestamp": sample["timestamp"],
            "last_sample_index": sample["sample_index"],
        }
    ]
    assert payload["data"]["latest"] == [sample]
    assert payload["data"]["history"] == [sample]


@pytest.mark.asyncio
async def test_stats_export_csv_returns_room_scoped_history(client):
    await client.post("/stats", json=stats_payload(room_id="room1"))
    await client.post("/stats", json=stats_payload(room_id="room2"))

    response = await client.get("/stats/export.csv?room_id=room1")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert body.splitlines()[0] == (
        "sample_index,timestamp,room_id,test_session_id,peer_id,remote_peer_id,"
        "connection_state,ice_connection_state,rtt_ms,packets_lost,packet_loss_rate,"
        "jitter_ms,bitrate_kbps,available_outgoing_bitrate_kbps,fps,frame_width,"
        "frame_height,codec,local_candidate_type,remote_candidate_type,"
        "candidate_pair_protocol,packets_sent,packets_received,bytes_sent,"
        "bytes_received,frames_sent,frames_received,frames_encoded,frames_decoded,"
        "frames_dropped,nack_enabled,nack_mode,nack_count,pli_count,fir_count,"
        "quality_limitation_reason,bitrate_mode,sender_max_bitrate_bps,abr_mode,"
        "abr_target_bitrate_bps,abr_decision"
    )
    assert ",room1," in body
    assert ",False,disabled," in body
    assert ",room2," not in body
