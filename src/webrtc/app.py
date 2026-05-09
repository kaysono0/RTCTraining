from aiohttp import web

from src.webrtc.api.route_registry import register_webrtc_routes
from src.webrtc.dashboard_handlers import DashboardHandlers
from src.webrtc.config import Settings
from src.webrtc.mesh_handlers import MeshHandlers
from src.webrtc.room_store import RoomStore
from src.webrtc.stats_handlers import StatsHandlers
from src.webrtc.stats_store import StatsStore
from src.webrtc.test_session_handlers import TestSessionHandlers
from src.webrtc.test_session_store import TestSessionStore
from src.webrtc.ui_handlers import UIHandlers


def create_webrtc_app(
    room_store=None,
    stats_store=None,
    test_session_store=None,
    test_sessions_dir=None,
):
    store = room_store or RoomStore()
    stats = stats_store or StatsStore()
    test_sessions = test_session_store or TestSessionStore()
    settings = Settings.from_env()
    test_session_output_dir = test_sessions_dir or settings.test_sessions_dir
    app = web.Application()
    handlers = MeshHandlers(store)
    dashboard_handlers = DashboardHandlers(store, stats)
    stats_handlers = StatsHandlers(stats, snapshot_builder=dashboard_handlers.build_snapshot)
    test_session_handlers = TestSessionHandlers(
        test_sessions,
        stats,
        output_dir=test_session_output_dir,
    )
    ui = UIHandlers()

    app["room_store"] = store
    app["stats_store"] = stats
    app["test_session_store"] = test_sessions
    register_webrtc_routes(
        app,
        ui=ui,
        mesh_handlers=handlers,
        stats_handlers=stats_handlers,
        dashboard_handlers=dashboard_handlers,
        test_session_handlers=test_session_handlers,
    )
    return app
