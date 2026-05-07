import time
import uuid


class TestSessionStore:
    __test__ = False

    def __init__(self, now=None, id_factory=None):
        self._now = now or time.time
        self._id_factory = id_factory or self._default_id
        self._sessions = {}

    def start(self, payload):
        session_id = self._id_factory()
        session = {
            "test_session_id": session_id,
            "room_id": payload["room_id"],
            "peer_id": payload["peer_id"],
            "preset": payload.get("preset") or "manual",
            "metadata": dict(payload.get("metadata") or {}),
            "weak_network": dict(payload.get("weak_network") or {}),
            "status": "running",
            "started_at": self._now(),
            "finished_at": None,
            "sample_count": 0,
            "output_path": None,
        }
        self._sessions[session_id] = session
        return dict(session)

    def get(self, test_session_id):
        session = self._sessions.get(test_session_id)
        return dict(session) if session else None

    def running(self, *, room_id, peer_id):
        candidates = [
            session
            for session in self._sessions.values()
            if session["room_id"] == room_id
            and session["peer_id"] == peer_id
            and session["status"] == "running"
        ]
        if not candidates:
            return None
        latest = max(candidates, key=lambda session: session["started_at"])
        return dict(latest)

    def finish(self, test_session_id, sample_count=0):
        session = self._require_session(test_session_id)
        session["status"] = "finished"
        session["finished_at"] = self._now()
        session["sample_count"] = sample_count
        return dict(session)

    def cancel(self, test_session_id):
        session = self._require_session(test_session_id)
        session["status"] = "canceled"
        session["finished_at"] = self._now()
        return dict(session)

    def _require_session(self, test_session_id):
        session = self._sessions.get(test_session_id)
        if not session:
            raise KeyError(test_session_id)
        return session

    def _default_id(self):
        return f"session-{uuid.uuid4()}"
