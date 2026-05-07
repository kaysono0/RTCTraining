from aiohttp import web

from src.webrtc.dashboard_handlers import DashboardHandlers
from src.webrtc.mesh_handlers import MeshHandlers
from src.webrtc.room_store import RoomStore
from src.webrtc.stats_handlers import StatsHandlers
from src.webrtc.stats_store import StatsStore
from src.webrtc.test_session_handlers import TestSessionHandlers
from src.webrtc.test_session_store import TestSessionStore
from src.webrtc.ui_handlers import UIHandlers


def create_webrtc_app(room_store=None, stats_store=None, test_session_store=None):
    store = room_store or RoomStore()
    stats = stats_store or StatsStore()
    test_sessions = test_session_store or TestSessionStore()
    app = web.Application()
    handlers = MeshHandlers(store)
    dashboard_handlers = DashboardHandlers(store, stats)
    stats_handlers = StatsHandlers(stats, snapshot_builder=dashboard_handlers.build_snapshot)
    test_session_handlers = TestSessionHandlers(test_sessions, stats)
    ui = UIHandlers()

    app["room_store"] = store
    app["stats_store"] = stats
    app["test_session_store"] = test_sessions
    app.router.add_get("/", ui.index)
    app.router.add_static("/static/webrtc/", ui.static_dir, name="webrtc_static")
    app.router.add_post("/rooms/join", handlers.join_room)
    app.router.add_post("/rooms/leave", handlers.leave_room)
    app.router.add_get("/rooms/{roomId}/members", handlers.room_members)
    app.router.add_get("/rooms/members", handlers.all_members)
    app.router.add_post("/signal", handlers.send_signal)
    app.router.add_get("/signal/pending", handlers.pending_signal)
    app.router.add_post("/stats", stats_handlers.post_stats)
    app.router.add_get("/stats", stats_handlers.get_latest)
    app.router.add_get("/stats/history", stats_handlers.get_history)
    app.router.add_get("/stats/peers", stats_handlers.get_peers)
    app.router.add_get("/dashboard/snapshot", dashboard_handlers.snapshot)
    app.router.add_get("/stats/export.csv", stats_handlers.export_csv)
    app.router.add_post("/clear_stats", stats_handlers.clear_stats)
    app.router.add_post("/stats/test/start", test_session_handlers.start)
    app.router.add_post("/stats/test/finish", test_session_handlers.finish)
    app.router.add_post("/stats/test/cancel", test_session_handlers.cancel)
    return app
