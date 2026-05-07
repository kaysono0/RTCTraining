from src.webrtc.stats_store import StatsStore


def sample(**overrides):
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
        },
    }
    payload.update(overrides)
    return payload


def test_put_sample_assigns_index_and_keeps_latest_by_peer_pair():
    store = StatsStore(max_history_per_pair=3, now=lambda: 1000.0)

    first = store.put_sample(sample(metrics={"rtt_ms": 10.0}))
    second = store.put_sample(sample(metrics={"rtt_ms": 20.0}))

    assert first["sample_index"] == 1
    assert second["sample_index"] == 2
    assert store.latest(room_id="room1") == [second]


def test_history_is_isolated_by_room_peer_pair_and_session():
    store = StatsStore(max_history_per_pair=5, now=lambda: 1000.0)

    expected = store.put_sample(
        sample(test_session_id="session-a", metrics={"rtt_ms": 10.0})
    )
    store.put_sample(
        sample(room_id="room2", test_session_id="session-a", metrics={"rtt_ms": 20.0})
    )
    store.put_sample(
        sample(remote_peer_id="peer-c", test_session_id="session-a", metrics={"rtt_ms": 30.0})
    )
    store.put_sample(sample(test_session_id="session-b", metrics={"rtt_ms": 40.0}))

    assert store.history(
        room_id="room1",
        peer_id="peer-a",
        remote_peer_id="peer-b",
        test_session_id="session-a",
    ) == [expected]


def test_history_is_capped_per_peer_pair():
    counter = iter([1000.0, 1001.0, 1002.0])
    store = StatsStore(max_history_per_pair=2, now=lambda: next(counter))

    store.put_sample(sample(metrics={"rtt_ms": 10.0}))
    second = store.put_sample(sample(metrics={"rtt_ms": 20.0}))
    third = store.put_sample(sample(metrics={"rtt_ms": 30.0}))

    assert store.history(room_id="room1") == [second, third]


def test_peers_returns_observed_pairs_for_room():
    counter = iter([1000.0, 1001.0, 1002.0, 1003.0])
    store = StatsStore(max_history_per_pair=5, now=lambda: next(counter))
    store.put_sample(sample())
    store.put_sample(sample(metrics={"rtt_ms": 20.0}))
    store.put_sample(sample(remote_peer_id="peer-c"))
    store.put_sample(sample(room_id="room2", remote_peer_id="peer-d"))

    assert store.peers(room_id="room1") == [
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "last_sample_timestamp": 1001.0,
            "last_sample_index": 2,
        },
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-c",
            "last_sample_timestamp": 1002.0,
            "last_sample_index": 3,
        },
    ]


def test_clear_removes_room_scoped_samples_only():
    store = StatsStore(max_history_per_pair=5, now=lambda: 1000.0)
    store.put_sample(sample())
    other = store.put_sample(sample(room_id="room2"))

    removed = store.clear(room_id="room1")

    assert removed == 1
    assert store.history(room_id="room1") == []
    assert store.history(room_id="room2") == [other]
