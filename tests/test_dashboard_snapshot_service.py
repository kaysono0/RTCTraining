from src.webrtc.room_store import RoomStore
from src.webrtc.services.dashboard_snapshot_service import DashboardSnapshotService
from src.webrtc.stats_store import StatsStore


def test_dashboard_snapshot_service_filters_stats_to_active_members():
    rooms = RoomStore()
    stats = StatsStore(now=lambda: 100.0)
    service = DashboardSnapshotService(rooms, stats, now=lambda: 200.0)

    rooms.join_room("room1", "peer-a", "Alice")
    rooms.join_room("room1", "peer-b", "Bob")
    rooms.join_room("room1", "peer-left", "Left")
    active_sample = stats.put_sample(
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "metrics": {"rtt_ms": 10},
        }
    )
    stats.put_sample(
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-left",
            "metrics": {"rtt_ms": 99},
        }
    )
    rooms.leave_room("room1", "peer-left")

    snapshot = service.build_snapshot("room1")

    assert snapshot["room_id"] == "room1"
    assert snapshot["stats_revision"] == 2
    assert snapshot["server_time"] == 200.0
    assert snapshot["members"] == [
        {"peer_id": "peer-a", "display_name": "Alice"},
        {"peer_id": "peer-b", "display_name": "Bob"},
    ]
    assert snapshot["peers"] == [
        {
            "room_id": "room1",
            "peer_id": "peer-a",
            "remote_peer_id": "peer-b",
            "last_sample_timestamp": active_sample["timestamp"],
            "last_sample_index": active_sample["sample_index"],
        }
    ]
    assert snapshot["latest"] == [active_sample]
    assert snapshot["history"] == [active_sample]
