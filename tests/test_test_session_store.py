from src.webrtc.test_session_store import TestSessionStore


def test_start_finish_and_cancel_test_sessions():
    now_values = iter([1000.0, 1005.0, 1010.0])
    store = TestSessionStore(now=lambda: next(now_values), id_factory=lambda: "session-fixed")

    session = store.start(
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "display_name": "Alice",
            "preset": "nack_on",
            "planned_duration_seconds": 60,
            "metadata": {"note": "baseline"},
            "weak_network": {"profile": "none"},
        }
    )

    assert session["test_session_id"] == "session-fixed"
    assert session["status"] == "running"
    assert session["room_id"] == "room1"
    assert session["peer_id"] == "peer-a"
    assert session["display_name"] == "Alice"
    assert session["preset"] == "nack_on"
    assert session["planned_duration_seconds"] == 60
    assert session["metadata"] == {"note": "baseline"}
    assert session["weak_network"] == {"profile": "none"}
    assert session["started_at"] == 1000.0
    assert session["finished_at"] is None
    assert session["duration_seconds"] is None
    assert session["sample_count"] == 0

    finished = store.finish("session-fixed", sample_count=12)
    assert finished["status"] == "finished"
    assert finished["finished_at"] == 1005.0
    assert finished["duration_seconds"] == 5
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


def test_list_finished_sessions_is_room_scoped_and_newest_first():
    now_values = iter([1000.0, 1001.0, 1002.0, 1003.0, 1004.0])
    store = TestSessionStore(
        now=lambda: next(now_values),
        id_factory=iter(["s1", "s2", "s3"]).__next__,
    )
    first = store.start({"room_id": "room1", "peer_id": "peer-a", "preset": "nack_on"})
    second = store.start({"room_id": "room1", "peer_id": "peer-a", "preset": "abr_simple"})
    other_room = store.start({"room_id": "room2", "peer_id": "peer-a", "preset": "nack_on"})
    store.finish(first["test_session_id"], sample_count=2, csv_files=[{"download_url": "/a.csv"}])
    store.finish(second["test_session_id"], sample_count=3, csv_files=[{"download_url": "/b.csv"}])

    sessions = store.list_finished(room_id="room1")

    assert [session["test_session_id"] for session in sessions] == ["s2", "s1"]
    assert sessions[0]["preset"] == "abr_simple"
    assert sessions[0]["sample_count"] == 3
    assert sessions[0]["csv_files"] == [{"download_url": "/b.csv"}]
    assert other_room["test_session_id"] not in [session["test_session_id"] for session in sessions]


def test_get_returns_none_for_unknown_session():
    store = TestSessionStore()
    assert store.get("nonexistent") is None


def test_finish_raises_keyerror_for_unknown_session():
    store = TestSessionStore()
    try:
        store.finish("nonexistent")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_cancel_raises_keyerror_for_unknown_session():
    store = TestSessionStore()
    try:
        store.cancel("nonexistent")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_running_returns_none_when_no_running_session():
    store = TestSessionStore()
    session = store.start({"room_id": "room1", "peer_id": "peer-a"})
    store.finish(session["test_session_id"])
    assert store.running(room_id="room1", peer_id="peer-a") is None


def test_running_returns_latest_when_multiple_running():
    now_values = iter([1000.0, 2000.0, 1500.0])
    store = TestSessionStore(now=lambda: next(now_values), id_factory=iter(["s1", "s2", "s3"]).__next__)
    store.start({"room_id": "room1", "peer_id": "peer-a"})
    expected = store.start({"room_id": "room1", "peer_id": "peer-a"})
    store.start({"room_id": "room1", "peer_id": "peer-b"})
    assert store.running(room_id="room1", peer_id="peer-a")["test_session_id"] == expected["test_session_id"]


def test_start_with_minimal_payload():
    store = TestSessionStore(id_factory=lambda: "minimal")
    session = store.start({"room_id": "room1", "peer_id": "peer-a"})
    assert session["preset"] == "manual"
    assert session["display_name"] == ""
    assert session["planned_duration_seconds"] is None
    assert session["metadata"] == {}
    assert session["weak_network"] == {}
    assert session["status"] == "running"


def test_returned_dict_is_a_copy():
    store = TestSessionStore(id_factory=lambda: "copy-test")
    session = store.start({"room_id": "room1", "peer_id": "peer-a"})
    session["mutated"] = True
    assert "mutated" not in store.get("copy-test")


def test_list_finished_without_room_id_returns_all_finished():
    now_values = iter([1000.0, 1001.0, 1002.0, 1003.0, 1004.0])
    store = TestSessionStore(
        now=lambda: next(now_values),
        id_factory=iter(["s1", "s2", "s3"]).__next__,
    )
    s1 = store.start({"room_id": "room1", "peer_id": "peer-a"})
    s2 = store.start({"room_id": "room2", "peer_id": "peer-a"})
    s3 = store.start({"room_id": "room1", "peer_id": "peer-b"})
    store.finish(s1["test_session_id"])
    store.finish(s2["test_session_id"])
    # s3 is still running, should not appear
    sessions = store.list_finished(room_id=None)
    assert len(sessions) == 2
    assert {s["test_session_id"] for s in sessions} == {"s1", "s2"}
