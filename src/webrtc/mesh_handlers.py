from aiohttp import web

from src.webrtc.response import error_payload, success_payload
from src.webrtc.room_store import (
    InvalidSignalTypeError,
    PeerNotFoundError,
    RoomFullError,
)


class MeshHandlers:
    def __init__(self, room_store):
        self.room_store = room_store

    async def join_room(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(body, ["room_id", "client_id", "display_name"])
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})

        try:
            data = self.room_store.join_room(
                body["room_id"],
                body["client_id"],
                body["display_name"],
            )
        except RoomFullError as exc:
            return self._json_error(409, "room_full", str(exc), {"room_id": body["room_id"]})
        return web.json_response(success_payload(data))

    async def leave_room(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(body, ["room_id", "client_id"])
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})

        data = self.room_store.leave_room(body["room_id"], body["client_id"])
        return web.json_response(success_payload(data))

    async def room_members(self, request):
        room_id = request.match_info["roomId"]
        return web.json_response(
            success_payload({"room_id": room_id, "members": self.room_store.list_members(room_id)})
        )

    async def all_members(self, request):
        return web.json_response(success_payload({"rooms": self.room_store.snapshot()}))

    async def send_signal(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(
            body,
            ["room_id", "from_peer_id", "to_peer_id", "type", "payload"],
        )
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})

        try:
            data = self.room_store.send_signal(
                room_id=body["room_id"],
                from_peer_id=body["from_peer_id"],
                to_peer_id=body["to_peer_id"],
                message_type=body["type"],
                payload=body["payload"],
            )
        except InvalidSignalTypeError as exc:
            return self._bad_request(str(exc), {"type": body["type"]})
        except PeerNotFoundError as exc:
            return self._json_error(404, "not_found", str(exc), {})
        return web.json_response(success_payload(data))

    async def pending_signal(self, request):
        room_id = request.query.get("room_id")
        client_id = request.query.get("client_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})
        if not client_id:
            return self._bad_request("client_id is required", {"field": "client_id"})

        messages = self.room_store.pop_pending(room_id, client_id)
        return web.json_response(success_payload({"messages": messages}))

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
        return self._json_error(400, "bad_request", message, details)

    def _json_error(self, status, code, message, details):
        return web.json_response(error_payload(code, message, details), status=status)
