from src.webrtc.exports.stats_csv import render_stats_csv


class StatsService:
    def __init__(self, stats_store):
        self.stats_store = stats_store

    def record_sample(self, sample):
        return self.stats_store.put_sample(sample)

    def latest(
        self,
        *,
        room_id,
        peer_id=None,
        remote_peer_id=None,
        test_session_id=None,
    ):
        return self.stats_store.latest(
            room_id=room_id,
            peer_id=peer_id,
            remote_peer_id=remote_peer_id,
            test_session_id=test_session_id,
        )

    def history(
        self,
        *,
        room_id,
        peer_id=None,
        remote_peer_id=None,
        test_session_id=None,
    ):
        return self.stats_store.history(
            room_id=room_id,
            peer_id=peer_id,
            remote_peer_id=remote_peer_id,
            test_session_id=test_session_id,
        )

    def peers(self, *, room_id):
        return self.stats_store.peers(room_id=room_id)

    def clear(self, *, room_id):
        return self.stats_store.clear(room_id=room_id)

    def export_csv(
        self,
        *,
        room_id,
        peer_id=None,
        remote_peer_id=None,
        test_session_id=None,
    ):
        samples = self.history(
            room_id=room_id,
            peer_id=peer_id,
            remote_peer_id=remote_peer_id,
            test_session_id=test_session_id,
        )
        return render_stats_csv(samples)
