import argparse
from pathlib import Path
from urllib.parse import urlencode

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout, TCPConnector
from aiohttp import web

from src.webrtc.response import error_payload, success_payload
from src.webrtc.config import Settings
from src.dashboard.origin_policy import OriginPolicy


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


async def webrtc_test_sessions_proxy(request):
    return await webrtc_proxy_json(request, "/stats/test/sessions")


async def webrtc_test_session_download_proxy(request):
    file_path = request.match_info["file_path"]
    return await _webrtc_proxy_file(request, f"/stats/test/download/{file_path}")


async def webrtc_proxy_json(request, upstream_path):
    return await _webrtc_proxy_json(request, upstream_path, method="GET")


async def _webrtc_proxy_json(request, upstream_path, method):
    settings = request.app["settings"]
    origin = request.query.get("origin", settings.local_webrtc_origin)
    if not request.app["origin_policy"].is_allowed(origin):
        return web.json_response(
            error_payload("bad_request", "origin is not allowed", {"origin": origin}),
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
                    payload = await _read_upstream_json(response)
            else:
                async with session.get(url) as response:
                    payload = await _read_upstream_json(response)
    except ClientResponseError as exc:
        return web.json_response(
            error_payload(
                "upstream_non_json",
                "WebRTC service returned a non-JSON response",
                {"status": exc.status, "error": str(exc)},
            ),
            status=502,
        )
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


async def _webrtc_proxy_file(request, upstream_path):
    settings = request.app["settings"]
    origin = request.query.get("origin", settings.local_webrtc_origin)
    if not request.app["origin_policy"].is_allowed(origin):
        return web.json_response(
            error_payload("bad_request", "origin is not allowed", {"origin": origin}),
            status=400,
        )

    url = f"{origin.rstrip('/')}{upstream_path}"
    connector = TCPConnector(ssl=False)
    timeout = ClientTimeout(total=3)
    try:
        async with ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url) as response:
                body = await response.read()
                if response.status >= 400:
                    return web.Response(status=response.status, body=body)
                return web.Response(
                    body=body,
                    content_type=response.headers.get("Content-Type", "text/csv").split(";")[0],
                    headers={"Cache-Control": "no-store"},
                )
    except (ClientError, TimeoutError, OSError) as exc:
        return web.json_response(
            error_payload("service_unreachable", "WebRTC service is unreachable", {"error": str(exc)}),
            status=502,
        )


async def _read_upstream_json(response):
    try:
        return await response.json()
    except ClientResponseError as exc:
        exc.status = response.status
        raise


def create_dashboard_app(settings=None):
    settings = settings or Settings.from_env()
    app = web.Application()
    app["settings"] = settings
    app["origin_policy"] = OriginPolicy.from_csv(settings.dashboard_origin_allowlist)
    app.router.add_get("/", dashboard_index)
    app.router.add_get("/api/webrtc/members", webrtc_members_proxy)
    app.router.add_get("/api/webrtc/stats", webrtc_stats_proxy)
    app.router.add_get("/api/webrtc/stats/history", webrtc_stats_history_proxy)
    app.router.add_get("/api/webrtc/stats/peers", webrtc_stats_peers_proxy)
    app.router.add_get("/api/webrtc/dashboard/snapshot", webrtc_dashboard_snapshot_proxy)
    app.router.add_post("/api/webrtc/clear_stats", webrtc_clear_stats_proxy)
    app.router.add_get("/api/webrtc/stats/test/sessions", webrtc_test_sessions_proxy)
    app.router.add_get("/api/webrtc/stats/test/download/{file_path:.+}", webrtc_test_session_download_proxy)
    app.router.add_static(
        "/static/dashboard/",
        PROJECT_ROOT / "static" / "dashboard",
        name="dashboard_static",
    )
    return app


def build_parser():
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="RTCTraining Dashboard service")
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    parser.add_argument("--host", default=settings.dashboard_host)
    parser.add_argument("--port", default=settings.dashboard_port, type=int)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    web.run_app(create_dashboard_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
