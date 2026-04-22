from src.webrtc.room_store import (
    InvalidSignalTypeError,
    PeerNotFoundError,
    RoomFullError,
    RoomStore,
)


def test_join_returns_existing_peers_and_notifies_old_members():
    store = RoomStore(max_members=3)

    first = store.join_room("room1", "client-a", "Alice")
    second = store.join_room("room1", "client-b", "Bob")
    pending_for_a = store.pop_pending("room1", "client-a")

    assert first["existing_peers"] == []
    assert second["existing_peers"] == [
        {"peer_id": "client-a", "display_name": "Alice"}
    ]
    assert pending_for_a == [
        {
            "type": "peer_joined",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b", "display_name": "Bob"},
        }
    ]


def test_duplicate_join_is_idempotent_and_does_not_notify_again():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    result = store.join_room("room1", "client-a", "Alice")

    assert result["existing_peers"] == []
    assert store.pop_pending("room1", "client-a") == []


def test_signal_pending_is_target_isolated_and_consumed():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    store.join_room("room1", "client-b", "Bob")

    store.send_signal(
        room_id="room1",
        from_peer_id="client-a",
        to_peer_id="client-b",
        message_type="offer",
        payload={"sdp": "fake-offer"},
    )

    assert store.pop_pending("room1", "client-a") == [
        {
            "type": "peer_joined",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b", "display_name": "Bob"},
        }
    ]
    assert store.pop_pending("room1", "client-b") == [
        {
            "type": "offer",
            "from_peer_id": "client-a",
            "to_peer_id": "client-b",
            "payload": {"sdp": "fake-offer"},
        }
    ]
    assert store.pop_pending("room1", "client-b") == []


def test_server_only_signal_types_cannot_be_sent_by_clients():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    store.join_room("room1", "client-b", "Bob")

    try:
        store.send_signal(
            room_id="room1",
            from_peer_id="client-a",
            to_peer_id="client-b",
            message_type="peer_joined",
            payload={"peer_id": "client-c"},
        )
    except InvalidSignalTypeError as exc:
        assert str(exc) == "unsupported client signal type: peer_joined"
    else:
        raise AssertionError("expected InvalidSignalTypeError")


def test_leave_notifies_remaining_members_and_removes_peer():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")
    store.join_room("room1", "client-b", "Bob")
    store.pop_pending("room1", "client-a")

    store.leave_room("room1", "client-b")

    assert store.list_members("room1") == [
        {"peer_id": "client-a", "display_name": "Alice"}
    ]
    assert store.pop_pending("room1", "client-a") == [
        {
            "type": "peer_left",
            "from_peer_id": "server",
            "to_peer_id": "client-a",
            "payload": {"peer_id": "client-b"},
        }
    ]


def test_room_limit_is_enforced():
    store = RoomStore(max_members=1)
    store.join_room("room1", "client-a", "Alice")

    try:
        store.join_room("room1", "client-b", "Bob")
    except RoomFullError as exc:
        assert str(exc) == "room room1 is full"
    else:
        raise AssertionError("expected RoomFullError")


def test_signal_requires_existing_source_and_target():
    store = RoomStore(max_members=3)
    store.join_room("room1", "client-a", "Alice")

    try:
        store.send_signal(
            room_id="room1",
            from_peer_id="client-a",
            to_peer_id="client-b",
            message_type="offer",
            payload={},
        )
    except PeerNotFoundError as exc:
        assert str(exc) == "peer client-b not found in room room1"
    else:
        raise AssertionError("expected PeerNotFoundError")
