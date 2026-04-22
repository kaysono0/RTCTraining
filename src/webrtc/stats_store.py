import time
from collections import deque


class StatsStore:
    def __init__(self, max_history_per_pair=300, now=None):
        self.max_history_per_pair = max_history_per_pair
        self._now = now or time.time
        self._sample_index = 0
        self._history = {}
        self._latest = {}

    def put_sample(self, sample):
        self._sample_index += 1
        stored = dict(sample)
        stored["test_session_id"] = stored.get("test_session_id")
        stored["metrics"] = dict(stored.get("metrics", {}))
        stored["timestamp"] = stored.get("timestamp", self._now())
        stored["sample_index"] = self._sample_index

        key = self._key(stored)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.max_history_per_pair)
        self._history[key].append(stored)
        self._latest[key] = stored
        return stored

    def latest(
        self,
        *,
        room_id,
        peer_id=None,
        remote_peer_id=None,
        test_session_id=None,
    ):
        return [
            sample
            for key, sample in sorted(self._latest.items())
            if self._matches(
                key,
                room_id=room_id,
                peer_id=peer_id,
                remote_peer_id=remote_peer_id,
                test_session_id=test_session_id,
            )
        ]

    def history(
        self,
        *,
        room_id,
        peer_id=None,
        remote_peer_id=None,
        test_session_id=None,
    ):
        samples = []
        for key, history in sorted(self._history.items()):
            if not self._matches(
                key,
                room_id=room_id,
                peer_id=peer_id,
                remote_peer_id=remote_peer_id,
                test_session_id=test_session_id,
            ):
                continue
            samples.extend(history)
        return sorted(samples, key=lambda sample: sample["sample_index"])

    def peers(self, *, room_id):
        pairs = [
            {
                "room_id": key[0],
                "peer_id": key[1],
                "remote_peer_id": key[2],
            }
            for key in self._history
            if key[0] == room_id
        ]
        return sorted(pairs, key=lambda pair: (pair["peer_id"], pair["remote_peer_id"]))

    def clear(self, *, room_id):
        keys = [key for key in self._history if key[0] == room_id]
        removed = sum(len(self._history[key]) for key in keys)
        for key in keys:
            del self._history[key]
            self._latest.pop(key, None)
        return removed

    def _key(self, sample):
        return (
            sample["room_id"],
            sample["peer_id"],
            sample["remote_peer_id"],
            sample.get("test_session_id"),
        )

    def _matches(self, key, *, room_id, peer_id, remote_peer_id, test_session_id):
        return (
            key[0] == room_id
            and (peer_id is None or key[1] == peer_id)
            and (remote_peer_id is None or key[2] == remote_peer_id)
            and (test_session_id is None or key[3] == test_session_id)
        )
