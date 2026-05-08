import time

from aiohttp import web

from src.webrtc.response import error_payload, success_payload


class DashboardHandlers:
    def __init__(self, room_store, stats_store, now=None):
        self.room_store = room_store
        self.stats_store = stats_store
        self._now = now or time.time

    async def snapshot(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        return web.json_response(success_payload(self.build_snapshot(room_id)))

    def build_snapshot(self, room_id):
        members = self.room_store.list_members(room_id)
        active_ids = {m["peer_id"] for m in members}
        return {
            "room_id": room_id,
            "stats_revision": self.stats_store.revision(room_id=room_id),
            "server_time": self._now(),
            "members": members,
            "peers": [
                p for p in self.stats_store.peers(room_id=room_id)
                if p["peer_id"] in active_ids and p["remote_peer_id"] in active_ids
            ],
            "latest": [
                s for s in self.stats_store.latest(room_id=room_id)
                if s["peer_id"] in active_ids and s["remote_peer_id"] in active_ids
            ],
            "history": [
                s for s in self.stats_store.history(room_id=room_id)
                if s["peer_id"] in active_ids and s["remote_peer_id"] in active_ids
            ],
        }

    def _bad_request(self, message, details):
        return web.json_response(
            error_payload("bad_request", message, details),
            status=400,
        )
