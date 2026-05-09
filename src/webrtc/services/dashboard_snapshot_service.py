import time


class DashboardSnapshotService:
    def __init__(self, room_store, stats_store, now=None):
        self.room_store = room_store
        self.stats_store = stats_store
        self._now = now or time.time

    def build_snapshot(self, room_id):
        members = self.room_store.list_members(room_id)
        active_ids = {member["peer_id"] for member in members}
        return {
            "room_id": room_id,
            "stats_revision": self.stats_store.revision(room_id=room_id),
            "server_time": self._now(),
            "members": members,
            "peers": self._active_items(
                self.stats_store.peers(room_id=room_id),
                active_ids,
            ),
            "latest": self._active_items(
                self.stats_store.latest(room_id=room_id),
                active_ids,
            ),
            "history": self._active_items(
                self.stats_store.history(room_id=room_id),
                active_ids,
            ),
        }

    def _active_items(self, items, active_ids):
        return [
            item for item in items
            if item["peer_id"] in active_ids and item["remote_peer_id"] in active_ids
        ]
