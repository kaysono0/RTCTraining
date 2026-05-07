from src.webrtc.test_session_store import TestSessionStore


def test_start_finish_and_cancel_test_sessions():
    now_values = iter([1000.0, 1005.0, 1010.0])
    store = TestSessionStore(now=lambda: next(now_values), id_factory=lambda: "session-fixed")

    session = store.start(
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "preset": "nack_on",
            "metadata": {"note": "baseline"},
            "weak_network": {"profile": "none"},
        }
    )

    assert session["test_session_id"] == "session-fixed"
    assert session["status"] == "running"
    assert session["room_id"] == "room1"
    assert session["peer_id"] == "peer-a"
    assert session["preset"] == "nack_on"
    assert session["metadata"] == {"note": "baseline"}
    assert session["weak_network"] == {"profile": "none"}
    assert session["started_at"] == 1000.0
    assert session["finished_at"] is None
    assert session["sample_count"] == 0

    finished = store.finish("session-fixed", sample_count=12)
    assert finished["status"] == "finished"
    assert finished["finished_at"] == 1005.0
    assert finished["sample_count"] == 12

    canceled = store.cancel("session-fixed")
    assert canceled["status"] == "canceled"
    assert canceled["finished_at"] == 1010.0


def test_get_running_session_is_room_and_peer_scoped():
    store = TestSessionStore(now=lambda: 1000.0)
    expected = store.start({"room_id": "room1", "peer_id": "peer-a", "preset": "manual"})
    store.start({"room_id": "room1", "peer_id": "peer-b", "preset": "manual"})
    store.start({"room_id": "room2", "peer_id": "peer-a", "preset": "manual"})

    assert store.running(room_id="room1", peer_id="peer-a") == expected
