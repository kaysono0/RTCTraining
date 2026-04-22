import pytest
import pytest_asyncio

from src.webrtc.app import create_webrtc_app
from src.webrtc.room_store import RoomStore


@pytest.fixture
def room_store():
    return RoomStore(max_members=3)


@pytest_asyncio.fixture
async def client(aiohttp_client, room_store):
    app = create_webrtc_app(room_store=room_store)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_join_returns_existing_peers(client):
    first = await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-a", "display_name": "Alice"},
    )
    second = await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-b", "display_name": "Bob"},
    )

    assert first.status == 200
    assert await first.json() == {
        "ok": True,
        "data": {"room_id": "room1", "peer_id": "client-a", "existing_peers": []},
    }
    assert second.status == 200
    assert await second.json() == {
        "ok": True,
        "data": {
            "room_id": "room1",
            "peer_id": "client-b",
            "existing_peers": [{"peer_id": "client-a", "display_name": "Alice"}],
        },
    }


@pytest.mark.asyncio
async def test_signal_pending_is_consumed(client):
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-a", "display_name": "Alice"},
    )
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-b", "display_name": "Bob"},
    )
    await client.post(
        "/signal",
        json={
            "room_id": "room1",
            "from_peer_id": "client-a",
            "to_peer_id": "client-b",
            "type": "offer",
            "payload": {"sdp": "fake-offer"},
        },
    )

    pending = await client.get("/signal/pending?room_id=room1&client_id=client-b")
    consumed = await client.get("/signal/pending?room_id=room1&client_id=client-b")

    assert pending.status == 200
    assert await pending.json() == {
        "ok": True,
        "data": {
            "messages": [
                {
                    "type": "offer",
                    "from_peer_id": "client-a",
                    "to_peer_id": "client-b",
                    "payload": {"sdp": "fake-offer"},
                }
            ]
        },
    }
    assert await consumed.json() == {"ok": True, "data": {"messages": []}}


@pytest.mark.asyncio
async def test_server_only_signal_type_is_rejected(client):
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-a", "display_name": "Alice"},
    )
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-b", "display_name": "Bob"},
    )

    response = await client.post(
        "/signal",
        json={
            "room_id": "room1",
            "from_peer_id": "client-a",
            "to_peer_id": "client-b",
            "type": "peer_left",
            "payload": {"peer_id": "client-a"},
        },
    )

    assert response.status == 400
    assert await response.json() == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "unsupported client signal type: peer_left",
            "details": {"type": "peer_left"},
        },
    }


@pytest.mark.asyncio
async def test_leave_notifies_other_member(client):
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-a", "display_name": "Alice"},
    )
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-b", "display_name": "Bob"},
    )
    await client.get("/signal/pending?room_id=room1&client_id=client-a")

    response = await client.post(
        "/rooms/leave",
        json={"room_id": "room1", "client_id": "client-b"},
    )
    pending = await client.get("/signal/pending?room_id=room1&client_id=client-a")

    assert response.status == 200
    assert await response.json() == {
        "ok": True,
        "data": {"room_id": "room1", "peer_id": "client-b", "left": True},
    }
    assert await pending.json() == {
        "ok": True,
        "data": {
            "messages": [
                {
                    "type": "peer_left",
                    "from_peer_id": "server",
                    "to_peer_id": "client-a",
                    "payload": {"peer_id": "client-b"},
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_member_queries_return_room_scoped_and_global_snapshots(client):
    await client.post(
        "/rooms/join",
        json={"room_id": "room1", "client_id": "client-a", "display_name": "Alice"},
    )
    await client.post(
        "/rooms/join",
        json={"room_id": "room2", "client_id": "client-b", "display_name": "Bob"},
    )

    room_members = await client.get("/rooms/room1/members")
    all_members = await client.get("/rooms/members")

    assert await room_members.json() == {
        "ok": True,
        "data": {
            "room_id": "room1",
            "members": [{"peer_id": "client-a", "display_name": "Alice"}],
        },
    }
    assert await all_members.json() == {
        "ok": True,
        "data": {
            "rooms": {
                "room1": {
                    "members": [{"peer_id": "client-a", "display_name": "Alice"}],
                    "pending_counts": {"client-a": 0},
                },
                "room2": {
                    "members": [{"peer_id": "client-b", "display_name": "Bob"}],
                    "pending_counts": {"client-b": 0},
                },
            }
        },
    }


@pytest.mark.asyncio
async def test_missing_required_field_returns_bad_request(client):
    response = await client.post(
        "/rooms/join",
        json={"room_id": "room1", "display_name": "Alice"},
    )

    assert response.status == 400
    assert await response.json() == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "client_id is required",
            "details": {"field": "client_id"},
        },
    }
