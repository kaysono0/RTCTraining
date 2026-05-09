import pytest

from src.webrtc.services.test_session_service import TestSessionService
from src.webrtc.stats_store import StatsStore
from src.webrtc.test_session_store import TestSessionStore


def test_finish_writes_csv_and_returns_relative_download_metadata(tmp_path):
    sessions = TestSessionStore(now=lambda: 100.0, id_factory=lambda: "session-1")
    stats = StatsStore(now=lambda: 101.0)
    service = TestSessionService(sessions, stats, output_dir=tmp_path)

    session = service.start(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "preset": "manual",
            "metadata": {},
            "weak_network": {},
        }
    )
    stats.put_sample(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "remote_peer_id": "bob",
            "test_session_id": session["test_session_id"],
            "metrics": {"rtt_ms": 10},
        }
    )

    finished = service.finish("session-1")

    assert finished["sample_count"] == 1
    assert finished["csv_files"][0]["relative_path"] == "room1/session-1/alice/bob.csv"
    assert finished["csv_files"][0]["download_url"] == "/stats/test/download/room1/session-1/alice/bob.csv"
    assert "path" not in finished["csv_files"][0]
    assert (tmp_path / "room1/session-1/alice/bob.csv").is_file()


def test_resolve_download_rejects_path_traversal(tmp_path):
    sessions = TestSessionStore(id_factory=lambda: "session-1")
    stats = StatsStore()
    service = TestSessionService(sessions, stats, output_dir=tmp_path)

    with pytest.raises(KeyError):
        service.resolve_download("../../../etc/passwd")
