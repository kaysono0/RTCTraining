from aiohttp import web

from src.webrtc.response import error_payload, success_payload
from src.webrtc.services.test_session_service import TestSessionService


class TestSessionHandlers:
    def __init__(self, test_session_store=None, stats_store=None, output_dir=None, service=None):
        self.service = service or TestSessionService(
            test_session_store,
            stats_store,
            output_dir,
        )

    async def start(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(body, ["room_id", "peer_id"])
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})
        session = self.service.start(
            {
                "room_id": body["room_id"],
                "peer_id": body["peer_id"],
                "display_name": body.get("display_name") or "",
                "preset": body.get("preset"),
                "planned_duration_seconds": self._optional_int(body.get("planned_duration_seconds")),
                "metadata": body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
                "weak_network": body.get("weak_network") if isinstance(body.get("weak_network"), dict) else {},
            }
        )
        return web.json_response(success_payload({"session": session}))

    async def finish(self, request):
        body = await self._json_body(request)
        test_session_id = body.get("test_session_id")
        if not test_session_id:
            return self._bad_request("test_session_id is required", {"field": "test_session_id"})
        session = self.service.get(test_session_id)
        if not session:
            return self._not_found(test_session_id)

        finished = self.service.finish(test_session_id)
        return web.json_response(success_payload({"session": finished}))

    async def cancel(self, request):
        body = await self._json_body(request)
        test_session_id = body.get("test_session_id")
        if not test_session_id:
            return self._bad_request("test_session_id is required", {"field": "test_session_id"})
        if not self.service.get(test_session_id):
            return self._not_found(test_session_id)
        canceled = self.service.cancel(test_session_id)
        return web.json_response(success_payload({"session": canceled}))

    async def list_sessions(self, request):
        room_id = request.query.get("room_id") or None
        sessions = self.service.list_finished(room_id=room_id)
        return web.json_response(success_payload({"sessions": sessions}))

    async def download_csv(self, request):
        relative_path = request.match_info["file_path"]
        try:
            target = self.service.resolve_download(relative_path)
        except KeyError:
            return self._not_found(relative_path)
        return web.FileResponse(
            target,
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    async def _json_body(self, request):
        try:
            body = await request.json()
        except Exception:
            return {}
        return body if isinstance(body, dict) else {}

    def _missing_field(self, body, fields):
        for field in fields:
            if field not in body or body[field] in (None, ""):
                return field
        return None

    def _optional_int(self, value):
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _bad_request(self, message, details):
        return web.json_response(
            error_payload("bad_request", message, details),
            status=400,
        )

    def _not_found(self, test_session_id):
        return web.json_response(
            error_payload(
                "not_found",
                "test session not found",
                {"test_session_id": test_session_id},
            ),
            status=404,
        )
