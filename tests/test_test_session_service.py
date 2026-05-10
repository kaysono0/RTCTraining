import pytest

from src.webrtc.services.test_session_service import TestSessionService
from src.webrtc.stats_store import StatsStore
from src.webrtc.test_session_store import TestSessionStore


def test_finish_writes_csv_and_returns_relative_download_metadata(tmp_path):
    now_values = iter([1778140800.0, 1778140865.0])
    sessions = TestSessionStore(now=lambda: next(now_values), id_factory=lambda: "session-1")
    stats = StatsStore(now=lambda: 101.0)
    service = TestSessionService(sessions, stats, output_dir=tmp_path)

    session = service.start(
        {
            "room_id": "room1",
            "peer_id": "alice",
            "display_name": "Alice Chen",
            "preset": "manual",
            "planned_duration_seconds": 60,
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
            "metrics": {
                "rtt_ms": 10,
                "nack_mode": "enabled",
                "abr_mode": "off",
                "sender_max_bitrate_bps": 600000,
            },
        }
    )

    finished = service.finish("session-1")

    assert finished["sample_count"] == 1
    assert finished["planned_duration_seconds"] == 60
    assert finished["duration_seconds"] == 65
    assert finished["csv_files"][0]["filename"] == (
        "20260507-080000Z_Alice_Chen_alice_to_bob_manual_"
        "nack-enabled_abr-off_bitrate-600kbps_65s.csv"
    )
    assert finished["csv_files"][0]["display_name"] == (
        "Alice Chen alice -> bob | manual | nack enabled | abr off | 600kbps | 65s | 20260507-080000Z"
    )
    assert finished["csv_files"][0]["relative_path"] == (
        "room1/session-1/alice/"
        "20260507-080000Z_Alice_Chen_alice_to_bob_manual_nack-enabled_abr-off_bitrate-600kbps_65s.csv"
    )
    assert finished["csv_files"][0]["download_url"] == (
        "/stats/test/download/room1/session-1/alice/"
        "20260507-080000Z_Alice_Chen_alice_to_bob_manual_nack-enabled_abr-off_bitrate-600kbps_65s.csv"
    )
    assert "path" not in finished["csv_files"][0]
    assert (tmp_path / finished["csv_files"][0]["relative_path"]).is_file()


def test_resolve_download_rejects_path_traversal(tmp_path):
    sessions = TestSessionStore(id_factory=lambda: "session-1")
    stats = StatsStore()
    service = TestSessionService(sessions, stats, output_dir=tmp_path)

    with pytest.raises(KeyError):
        service.resolve_download("../../../etc/passwd")
