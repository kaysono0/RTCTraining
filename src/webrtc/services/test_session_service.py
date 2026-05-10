import re
from datetime import datetime, timezone
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
        finished = self.test_session_store.finish(
            test_session_id,
            sample_count=len(samples),
            csv_files=[],
        )
        csv_files = self._write_csv_files(finished, samples)
        return self.test_session_store.set_csv_files(test_session_id, csv_files)

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
        duration_seconds = self._duration_seconds(session)
        for remote_peer_id in sorted(grouped):
            samples_for_remote = grouped[remote_peer_id]
            filename = self._csv_filename(session, remote_peer_id, samples_for_remote, duration_seconds)
            relative_path = Path(
                self._safe_part(session["room_id"]),
                self._safe_part(session["test_session_id"]),
                self._safe_part(session["peer_id"]),
                filename,
            )
            target = self.output_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_stats_csv(samples_for_remote), encoding="utf-8")
            relative_text = relative_path.as_posix()
            csv_files.append(
                {
                    "room_id": session["room_id"],
                    "test_session_id": session["test_session_id"],
                    "peer_id": session["peer_id"],
                    "remote_peer_id": remote_peer_id,
                    "filename": filename,
                    "display_name": self._csv_display_name(
                        session,
                        remote_peer_id,
                        samples_for_remote,
                        duration_seconds,
                    ),
                    "relative_path": relative_text,
                    "download_url": f"/stats/test/download/{relative_text}",
                }
            )
        return csv_files

    def _safe_part(self, value):
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "none"))

    def _duration_seconds(self, session):
        if session.get("duration_seconds") is not None:
            return session["duration_seconds"]
        return max(0, int(round(self._now_for_filename(session) - session["started_at"])))

    def _csv_filename(self, session, remote_peer_id, samples, duration_seconds):
        start_label = self._start_label(session)
        display_name = self._safe_part(session.get("display_name") or session["peer_id"])
        peer_id = self._safe_part(session["peer_id"])
        remote_id = self._safe_part(remote_peer_id)
        preset = self._safe_part(session.get("preset") or "manual")
        nack = self._safe_part(f"nack-{self._nack_label(samples)}")
        abr = self._safe_part(f"abr-{self._abr_label(samples)}")
        bitrate = self._safe_part(f"bitrate-{self._bitrate_label(samples)}")
        return (
            f"{start_label}_{display_name}_{peer_id}_to_{remote_id}_{preset}_"
            f"{nack}_{abr}_{bitrate}_{duration_seconds}s.csv"
        )

    def _csv_display_name(self, session, remote_peer_id, samples, duration_seconds):
        display_name = session.get("display_name") or session["peer_id"]
        bitrate = self._bitrate_label(samples)
        return (
            f"{display_name} {session['peer_id']} -> {remote_peer_id} | "
            f"{session.get('preset') or 'manual'} | "
            f"nack {self._nack_label(samples)} | "
            f"abr {self._abr_label(samples)} | "
            f"{bitrate} | {duration_seconds}s | {self._start_label(session)}"
        )

    def _start_label(self, session):
        return datetime.fromtimestamp(
            session["started_at"],
            tz=timezone.utc,
        ).strftime("%Y%m%d-%H%M%SZ")

    def _nack_label(self, samples):
        value = self._first_metric(samples, "nack_mode")
        return str(value or "unknown")

    def _abr_label(self, samples):
        value = self._first_metric(samples, "abr_mode")
        return str(value or "unknown")

    def _bitrate_label(self, samples):
        value = self._first_metric(samples, "sender_max_bitrate_bps")
        if value in (None, ""):
            return "auto"
        try:
            kbps = int(value) // 1000
        except (TypeError, ValueError):
            return str(value)
        return f"{kbps}kbps"

    def _first_metric(self, samples, name):
        for sample in samples:
            metrics = sample.get("metrics") or {}
            value = metrics.get(name)
            if value not in (None, ""):
                return value
        return None

    def _now_for_filename(self, session):
        return session.get("finished_at") or session["started_at"]
