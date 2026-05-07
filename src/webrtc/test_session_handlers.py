from aiohttp import web

from src.webrtc.response import error_payload, success_payload


class TestSessionHandlers:
    def __init__(self, test_session_store, stats_store):
        self.test_session_store = test_session_store
        self.stats_store = stats_store

    async def start(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(body, ["room_id", "peer_id"])
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})
        session = self.test_session_store.start(
            {
                "room_id": body["room_id"],
                "peer_id": body["peer_id"],
                "preset": body.get("preset"),
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
        session = self.test_session_store.get(test_session_id)
        if not session:
            return self._not_found(test_session_id)

        sample_count = len(
            self.stats_store.history(
                room_id=session["room_id"],
                peer_id=session["peer_id"],
                test_session_id=test_session_id,
            )
        )
        finished = self.test_session_store.finish(test_session_id, sample_count=sample_count)
        return web.json_response(success_payload({"session": finished}))

    async def cancel(self, request):
        body = await self._json_body(request)
        test_session_id = body.get("test_session_id")
        if not test_session_id:
            return self._bad_request("test_session_id is required", {"field": "test_session_id"})
        if not self.test_session_store.get(test_session_id):
            return self._not_found(test_session_id)
        canceled = self.test_session_store.cancel(test_session_id)
        return web.json_response(success_payload({"session": canceled}))

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
