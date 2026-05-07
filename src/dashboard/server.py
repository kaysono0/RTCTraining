import argparse
from pathlib import Path
from urllib.parse import urlencode, urlparse

from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector
from aiohttp import web

from src.webrtc.response import error_payload, success_payload
from src.webrtc.config import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def dashboard_index(request):
    return web.FileResponse(
        PROJECT_ROOT / "templates" / "dashboard" / "index.html",
        headers={"Cache-Control": "no-store"},
    )


async def webrtc_members_proxy(request):
    return await webrtc_proxy_json(request, "/rooms/members")


async def webrtc_stats_proxy(request):
    return await webrtc_proxy_json(request, "/stats")


async def webrtc_stats_history_proxy(request):
    return await webrtc_proxy_json(request, "/stats/history")


async def webrtc_stats_peers_proxy(request):
    return await webrtc_proxy_json(request, "/stats/peers")


async def webrtc_dashboard_snapshot_proxy(request):
    return await webrtc_proxy_json(request, "/dashboard/snapshot")


async def webrtc_clear_stats_proxy(request):
    return await _webrtc_proxy_json(request, "/clear_stats", method="POST")


async def webrtc_proxy_json(request, upstream_path):
    return await _webrtc_proxy_json(request, upstream_path, method="GET")


async def _webrtc_proxy_json(request, upstream_path, method):
    origin = request.query.get("origin", Settings().local_webrtc_origin)
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return web.json_response(
            error_payload("bad_request", "origin must be an http or https URL", {"origin": origin}),
            status=400,
        )

    upstream_query = {
        key: value
        for key, value in request.query.items()
        if key != "origin"
    }
    query_string = urlencode(upstream_query)
    url = f"{origin.rstrip('/')}{upstream_path}"
    if query_string:
        url = f"{url}?{query_string}"

    connector = TCPConnector(ssl=False)
    timeout = ClientTimeout(total=3)
    try:
        async with ClientSession(connector=connector, timeout=timeout) as session:
            if method == "POST":
                async with session.post(url, json=await request.json()) as response:
                    payload = await response.json()
            else:
                async with session.get(url) as response:
                    payload = await response.json()
    except (ClientError, TimeoutError, OSError) as exc:
        return web.json_response(
            error_payload("service_unreachable", "WebRTC service is unreachable", {"error": str(exc)}),
            status=502,
        )

    if not payload.get("ok"):
        return web.json_response(
            error_payload("upstream_error", "WebRTC service returned an error", {"payload": payload}),
            status=502,
        )

    data = dict(payload.get("data", {}))
    data["origin"] = origin
    return web.json_response(success_payload(data))


def create_dashboard_app():
    app = web.Application()
    app.router.add_get("/", dashboard_index)
    app.router.add_get("/api/webrtc/members", webrtc_members_proxy)
    app.router.add_get("/api/webrtc/stats", webrtc_stats_proxy)
    app.router.add_get("/api/webrtc/stats/history", webrtc_stats_history_proxy)
    app.router.add_get("/api/webrtc/stats/peers", webrtc_stats_peers_proxy)
    app.router.add_get("/api/webrtc/dashboard/snapshot", webrtc_dashboard_snapshot_proxy)
    app.router.add_post("/api/webrtc/clear_stats", webrtc_clear_stats_proxy)
    app.router.add_static(
        "/static/dashboard/",
        PROJECT_ROOT / "static" / "dashboard",
        name="dashboard_static",
    )
    return app


def build_parser():
    parser = argparse.ArgumentParser(description="RTCTraining Dashboard service")
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    parser.add_argument("--host", default=Settings().dashboard_host)
    parser.add_argument("--port", default=Settings().dashboard_port, type=int)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    web.run_app(create_dashboard_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
