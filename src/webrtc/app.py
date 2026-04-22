from aiohttp import web

from src.webrtc.mesh_handlers import MeshHandlers
from src.webrtc.room_store import RoomStore
from src.webrtc.stats_handlers import StatsHandlers
from src.webrtc.stats_store import StatsStore
from src.webrtc.ui_handlers import UIHandlers


def create_webrtc_app(room_store=None, stats_store=None):
    store = room_store or RoomStore()
    stats = stats_store or StatsStore()
    app = web.Application()
    handlers = MeshHandlers(store)
    stats_handlers = StatsHandlers(stats)
    ui = UIHandlers()

    app["room_store"] = store
    app["stats_store"] = stats
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
    app.router.add_post("/clear_stats", stats_handlers.clear_stats)
    return app
