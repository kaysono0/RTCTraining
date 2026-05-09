import re
from pathlib import Path

from src.webrtc.exports.stats_csv import render_stats_csv


class TestSessionService:
    __test__ = False

    def __init__(self, test_session_store, stats_store, output_dir):
        self.test_session_store = test_session_store
        self.stats_store = stats_store
        self.output_dir = Path(output_dir)

    def start(self, payload):
        return self.test_session_store.start(payload)

    def get(self, test_session_id):
        return self.test_session_store.get(test_session_id)

    def cancel(self, test_session_id):
        return self.test_session_store.cancel(test_session_id)

    def list_finished(self, *, room_id=None):
        return self.test_session_store.list_finished(room_id=room_id)

    def finish(self, test_session_id):
        session = self.test_session_store.get(test_session_id)
        if not session:
            raise KeyError(test_session_id)
        samples = self.stats_store.history(
            room_id=session["room_id"],
            peer_id=session["peer_id"],
            test_session_id=test_session_id,
        )
        csv_files = self._write_csv_files(session, samples)
        return self.test_session_store.finish(
            test_session_id,
            sample_count=len(samples),
            csv_files=csv_files,
        )

    def resolve_download(self, relative_path):
        target = (self.output_dir / relative_path).resolve()
        root = self.output_dir.resolve()
        if root not in target.parents and target != root:
            raise KeyError(relative_path)
        if not target.is_file():
            raise KeyError(relative_path)
        return target

    def _write_csv_files(self, session, samples):
        grouped = {}
        for sample in samples:
            grouped.setdefault(sample["remote_peer_id"], []).append(sample)
        if not grouped:
            grouped["none"] = []

        csv_files = []
        for remote_peer_id in sorted(grouped):
            relative_path = Path(
                self._safe_part(session["room_id"]),
                self._safe_part(session["test_session_id"]),
                self._safe_part(session["peer_id"]),
                f"{self._safe_part(remote_peer_id)}.csv",
            )
            target = self.output_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_stats_csv(grouped[remote_peer_id]), encoding="utf-8")
            relative_text = relative_path.as_posix()
            csv_files.append(
                {
                    "room_id": session["room_id"],
                    "test_session_id": session["test_session_id"],
                    "peer_id": session["peer_id"],
                    "remote_peer_id": remote_peer_id,
                    "relative_path": relative_text,
                    "download_url": f"/stats/test/download/{relative_text}",
                }
            )
        return csv_files

    def _safe_part(self, value):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "none"))
