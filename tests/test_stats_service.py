from src.webrtc.services.stats_service import StatsService
from src.webrtc.stats_store import StatsStore


def test_stats_service_records_sample_and_preserves_identity():
    store = StatsStore(now=lambda: 100.0)
    service = StatsService(store)

    sample = service.record_sample(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "remote_peer_id": "bob",
            "test_session_id": "session-1",
            "metrics": {"rtt_ms": 12.5},
        }
    )

    assert sample["room_id"] == "room1"
    assert sample["peer_id"] == "alice"
    assert sample["remote_peer_id"] == "bob"
    assert sample["test_session_id"] == "session-1"
    assert sample["metrics"]["rtt_ms"] == 12.5
    assert sample["timestamp"] == 100.0


def test_stats_service_filters_history_by_test_session():
    store = StatsStore(now=lambda: 100.0)
    service = StatsService(store)
    service.record_sample(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "remote_peer_id": "bob",
            "test_session_id": "s1",
            "metrics": {"rtt_ms": 10},
        }
    )
    service.record_sample(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "remote_peer_id": "bob",
            "test_session_id": "s2",
            "metrics": {"rtt_ms": 20},
        }
    )

    samples = service.history(room_id="room1", test_session_id="s2")

    assert len(samples) == 1
    assert samples[0]["metrics"]["rtt_ms"] == 20


def test_stats_service_exports_csv_with_stable_header():
    store = StatsStore(now=lambda: 100.0)
    service = StatsService(store)
    service.record_sample(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "remote_peer_id": "bob",
            "metrics": {"rtt_ms": 10},
        }
    )

    csv_text = service.export_csv(room_id="room1")

    assert csv_text.splitlines()[0].startswith("sample_index,timestamp,room_id")
    assert "room1" in csv_text
    assert "alice" in csv_text
    assert "bob" in csv_text
