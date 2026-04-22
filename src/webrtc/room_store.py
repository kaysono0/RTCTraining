import time


CLIENT_SIGNAL_TYPES = {"offer", "answer", "candidate", "renegotiate"}


class RoomStoreError(Exception):
    pass


class RoomFullError(RoomStoreError):
    pass


class InvalidSignalTypeError(RoomStoreError):
    pass


class PeerNotFoundError(RoomStoreError):
    pass


class RoomStore:
    def __init__(self, max_members=3):
        self.max_members = max_members
        self._rooms = {}

    def join_room(self, room_id, client_id, display_name):
        room = self._room(room_id)
        members = room["members"]

        if client_id in members:
            members[client_id]["display_name"] = display_name
            members[client_id]["last_seen"] = time.time()
            return {"room_id": room_id, "peer_id": client_id, "existing_peers": self._existing_peers(room, client_id)}

        if len(members) >= self.max_members:
            raise RoomFullError(f"room {room_id} is full")

        existing_peers = self._existing_peers(room, client_id)
        now = time.time()
        members[client_id] = {
            "client_id": client_id,
            "display_name": display_name,
            "joined_at": now,
            "last_seen": now,
            "active": True,
        }
        room["pending_messages"][client_id] = []
        room["last_activity"] = now

        for peer_id in members:
            if peer_id == client_id:
                continue
            self._enqueue(
                room,
                {
                    "type": "peer_joined",
                    "from_peer_id": "server",
                    "to_peer_id": peer_id,
                    "payload": {"peer_id": client_id, "display_name": display_name},
                },
            )

        return {"room_id": room_id, "peer_id": client_id, "existing_peers": existing_peers}

    def leave_room(self, room_id, client_id):
        room = self._rooms.get(room_id)
        if not room or client_id not in room["members"]:
            return {"room_id": room_id, "peer_id": client_id, "left": False}

        del room["members"][client_id]
        room["pending_messages"].pop(client_id, None)
        room["last_activity"] = time.time()

        for peer_id in room["members"]:
            self._enqueue(
                room,
                {
                    "type": "peer_left",
                    "from_peer_id": "server",
                    "to_peer_id": peer_id,
                    "payload": {"peer_id": client_id},
                },
            )

        return {"room_id": room_id, "peer_id": client_id, "left": True}

    def list_members(self, room_id):
        room = self._rooms.get(room_id)
        if not room:
            return []
        return self._existing_peers(room, excluded_peer_id=None)

    def snapshot(self):
        return {
            room_id: {
                "members": self._existing_peers(room, excluded_peer_id=None),
                "pending_counts": {
                    peer_id: len(messages)
                    for peer_id, messages in room["pending_messages"].items()
                },
            }
            for room_id, room in self._rooms.items()
        }

    def send_signal(self, room_id, from_peer_id, to_peer_id, message_type, payload):
        if message_type not in CLIENT_SIGNAL_TYPES:
            raise InvalidSignalTypeError(f"unsupported client signal type: {message_type}")

        room = self._rooms.get(room_id)
        if not room:
            raise PeerNotFoundError(f"peer {from_peer_id} not found in room {room_id}")

        self._require_peer(room, room_id, from_peer_id)
        self._require_peer(room, room_id, to_peer_id)

        message = {
            "type": message_type,
            "from_peer_id": from_peer_id,
            "to_peer_id": to_peer_id,
            "payload": payload,
        }
        self._enqueue(room, message)
        room["last_activity"] = time.time()
        return message

    def pop_pending(self, room_id, client_id):
        room = self._rooms.get(room_id)
        if not room:
            return []
        messages = room["pending_messages"].get(client_id, [])
        room["pending_messages"][client_id] = []
        if client_id in room["members"]:
            room["members"][client_id]["last_seen"] = time.time()
        return messages

    def _room(self, room_id):
        if room_id not in self._rooms:
            self._rooms[room_id] = {
                "members": {},
                "pending_messages": {},
                "last_activity": time.time(),
                "max_members": self.max_members,
            }
        return self._rooms[room_id]

    def _existing_peers(self, room, excluded_peer_id):
        return [
            {"peer_id": peer_id, "display_name": member["display_name"]}
            for peer_id, member in room["members"].items()
            if peer_id != excluded_peer_id
        ]

    def _enqueue(self, room, message):
        room["pending_messages"].setdefault(message["to_peer_id"], []).append(message)

    def _require_peer(self, room, room_id, peer_id):
        if peer_id not in room["members"]:
            raise PeerNotFoundError(f"peer {peer_id} not found in room {room_id}")
