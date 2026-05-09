from aiohttp import web

from src.webrtc.response import error_payload, success_payload
from src.webrtc.services.dashboard_snapshot_service import DashboardSnapshotService


class DashboardHandlers:
    def __init__(self, room_store=None, stats_store=None, snapshot_service=None, now=None):
        self.snapshot_service = snapshot_service or DashboardSnapshotService(
            room_store,
            stats_store,
            now=now,
        )

    async def snapshot(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        return web.json_response(success_payload(self.build_snapshot(room_id)))

    def build_snapshot(self, room_id):
        return self.snapshot_service.build_snapshot(room_id)

    def _bad_request(self, message, details):
        return web.json_response(
            error_payload("bad_request", message, details),
            status=400,
        )
