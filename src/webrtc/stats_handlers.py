import csv
import io

from aiohttp import web

from src.webrtc.response import error_payload, success_payload


CSV_FIELDS = [
    "sample_index",
    "timestamp",
    "room_id",
    "test_session_id",
    "peer_id",
    "remote_peer_id",
    "connection_state",
    "ice_connection_state",
    "rtt_ms",
    "packets_lost",
    "packet_loss_rate",
    "jitter_ms",
    "bitrate_kbps",
    "available_outgoing_bitrate_kbps",
    "fps",
    "frame_width",
    "frame_height",
    "codec",
    "local_candidate_type",
    "remote_candidate_type",
    "candidate_pair_protocol",
    "packets_sent",
    "packets_received",
    "bytes_sent",
    "bytes_received",
    "frames_sent",
    "frames_received",
    "frames_encoded",
    "frames_decoded",
    "frames_dropped",
    "nack_count",
    "pli_count",
    "fir_count",
    "quality_limitation_reason",
]


class StatsHandlers:
    def __init__(self, stats_store, snapshot_builder=None):
        self.stats_store = stats_store
        self.snapshot_builder = snapshot_builder

    async def post_stats(self, request):
        body = await self._json_body(request)
        missing = self._missing_field(
            body,
            ["room_id", "peer_id", "remote_peer_id", "metrics"],
        )
        if missing:
            return self._bad_request(f"{missing} is required", {"field": missing})
        if not isinstance(body["metrics"], dict):
            return self._bad_request("metrics must be an object", {"field": "metrics"})

        sample = self.stats_store.put_sample(
            {
                "room_id": body["room_id"],
                "peer_id": body["peer_id"],
                "remote_peer_id": body["remote_peer_id"],
                "test_session_id": body.get("test_session_id"),
                "timestamp": body.get("timestamp"),
                "metrics": body["metrics"],
            }
        )
        return web.json_response(success_payload({"sample": sample}))

    async def get_latest(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        samples = self.stats_store.latest(
            room_id=room_id,
            peer_id=request.query.get("peer_id"),
            remote_peer_id=request.query.get("remote_peer_id"),
            test_session_id=request.query.get("test_session_id"),
        )
        return web.json_response(success_payload({"samples": samples}))

    async def get_history(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        samples = self.stats_store.history(
            room_id=room_id,
            peer_id=request.query.get("peer_id"),
            remote_peer_id=request.query.get("remote_peer_id"),
            test_session_id=request.query.get("test_session_id"),
        )
        return web.json_response(success_payload({"samples": samples}))

    async def get_peers(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        return web.json_response(
            success_payload({"peers": self.stats_store.peers(room_id=room_id)})
        )

    async def export_csv(self, request):
        room_id = request.query.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        samples = self.stats_store.history(
            room_id=room_id,
            peer_id=request.query.get("peer_id"),
            remote_peer_id=request.query.get("remote_peer_id"),
            test_session_id=request.query.get("test_session_id"),
        )
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for sample in samples:
            metrics = sample.get("metrics", {})
            writer.writerow(
                {
                    "sample_index": sample.get("sample_index", ""),
                    "timestamp": sample.get("timestamp", ""),
                    "room_id": sample.get("room_id", ""),
                    "test_session_id": sample.get("test_session_id") or "",
                    "peer_id": sample.get("peer_id", ""),
                    "remote_peer_id": sample.get("remote_peer_id", ""),
                    "connection_state": metrics.get("connection_state", ""),
                    "ice_connection_state": metrics.get("ice_connection_state", ""),
                    "rtt_ms": metrics.get("rtt_ms", ""),
                    "packets_lost": metrics.get("packets_lost", ""),
                    "packet_loss_rate": metrics.get("packet_loss_rate", ""),
                    "jitter_ms": metrics.get("jitter_ms", ""),
                    "bitrate_kbps": metrics.get("bitrate_kbps", ""),
                    "available_outgoing_bitrate_kbps": metrics.get("available_outgoing_bitrate_kbps", ""),
                    "fps": metrics.get("fps", ""),
                    "frame_width": metrics.get("frame_width", ""),
                    "frame_height": metrics.get("frame_height", ""),
                    "codec": metrics.get("codec", ""),
                    "local_candidate_type": metrics.get("local_candidate_type", ""),
                    "remote_candidate_type": metrics.get("remote_candidate_type", ""),
                    "candidate_pair_protocol": metrics.get("candidate_pair_protocol", ""),
                    "packets_sent": metrics.get("packets_sent", ""),
                    "packets_received": metrics.get("packets_received", ""),
                    "bytes_sent": metrics.get("bytes_sent", ""),
                    "bytes_received": metrics.get("bytes_received", ""),
                    "frames_sent": metrics.get("frames_sent", ""),
                    "frames_received": metrics.get("frames_received", ""),
                    "frames_encoded": metrics.get("frames_encoded", ""),
                    "frames_decoded": metrics.get("frames_decoded", ""),
                    "frames_dropped": metrics.get("frames_dropped", ""),
                    "nack_count": metrics.get("nack_count", ""),
                    "pli_count": metrics.get("pli_count", ""),
                    "fir_count": metrics.get("fir_count", ""),
                    "quality_limitation_reason": metrics.get("quality_limitation_reason", ""),
                }
            )

        return web.Response(
            text=buffer.getvalue(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{room_id}-stats.csv"'},
        )

    async def clear_stats(self, request):
        body = await self._json_body(request)
        room_id = body.get("room_id")
        if not room_id:
            return self._bad_request("room_id is required", {"field": "room_id"})

        removed = self.stats_store.clear(room_id=room_id)
        data = {"removed": removed}
        if self.snapshot_builder:
            data["snapshot"] = self.snapshot_builder(room_id)
        return web.json_response(success_payload(data))

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
