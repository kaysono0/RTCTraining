import re
from pathlib import Path

from aiohttp import web

from src.webrtc.csv_export import render_stats_csv
from src.webrtc.response import error_payload, success_payload


class TestSessionHandlers:
    def __init__(self, test_session_store, stats_store, output_dir):
        self.test_session_store = test_session_store
        self.stats_store = stats_store
        self.output_dir = Path(output_dir)

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

        samples = self.stats_store.history(
            room_id=session["room_id"],
            peer_id=session["peer_id"],
            test_session_id=test_session_id,
        )
        csv_files = self._write_csv_files(session, samples)
        finished = self.test_session_store.finish(
            test_session_id,
            sample_count=len(samples),
            csv_files=csv_files,
        )
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

    async def list_sessions(self, request):
        room_id = request.query.get("room_id") or None
        sessions = self.test_session_store.list_finished(room_id=room_id)
        return web.json_response(success_payload({"sessions": sessions}))

    async def download_csv(self, request):
        relative_path = request.match_info["file_path"]
        target = (self.output_dir / relative_path).resolve()
        root = self.output_dir.resolve()
        if root not in target.parents and target != root:
            return self._not_found(relative_path)
        if not target.is_file():
            return self._not_found(relative_path)
        return web.FileResponse(
            target,
            headers={"Content-Disposition": f'attachment; filename="{target.name}"'},
        )

    def _write_csv_files(self, session, samples):
        grouped = {}
        for sample in samples:
            grouped.setdefault(sample["remote_peer_id"], []).append(sample)
        if not grouped:
            grouped["none"] = []

        csv_files = []
        for remote_peer_id in sorted(grouped):
            pair_samples = grouped[remote_peer_id]
            relative_path = Path(
                self._safe_part(session["room_id"]),
                self._safe_part(session["test_session_id"]),
                self._safe_part(session["peer_id"]),
                f"{self._safe_part(remote_peer_id)}.csv",
            )
            target = self.output_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render_stats_csv(pair_samples), encoding="utf-8")
            csv_files.append(
                {
                    "room_id": session["room_id"],
                    "test_session_id": session["test_session_id"],
                    "peer_id": session["peer_id"],
                    "remote_peer_id": remote_peer_id,
                    "path": str(target),
                    "download_url": f"/stats/test/download/{relative_path.as_posix()}",
                }
            )
        return csv_files

    def _safe_part(self, value):
        text = str(value or "none")
        return re.sub(r"[^A-Za-z0-9._-]+", "_", text)

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
