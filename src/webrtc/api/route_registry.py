def register_webrtc_routes(
    app,
    *,
    ui,
    mesh_handlers,
    stats_handlers,
    dashboard_handlers,
    test_session_handlers,
):
    app.router.add_get("/", ui.index, name="webrtc_index")
    app.router.add_static("/static/webrtc/", ui.static_dir, name="webrtc_static")

    app.router.add_post("/rooms/join", mesh_handlers.join_room, name="rooms_join")
    app.router.add_post("/rooms/leave", mesh_handlers.leave_room, name="rooms_leave")
    app.router.add_get(
        "/rooms/{roomId}/members",
        mesh_handlers.room_members,
        name="rooms_members",
    )
    app.router.add_get(
        "/rooms/members",
        mesh_handlers.all_members,
        name="rooms_all_members",
    )
    app.router.add_post("/signal", mesh_handlers.send_signal, name="signal_send")
    app.router.add_get(
        "/signal/pending",
        mesh_handlers.pending_signal,
        name="signal_pending",
    )

    app.router.add_post("/stats", stats_handlers.post_stats, name="stats_post")
    app.router.add_get("/stats", stats_handlers.get_latest, name="stats_latest")
    app.router.add_get(
        "/stats/history",
        stats_handlers.get_history,
        name="stats_history",
    )
    app.router.add_get("/stats/peers", stats_handlers.get_peers, name="stats_peers")
    app.router.add_get(
        "/dashboard/snapshot",
        dashboard_handlers.snapshot,
        name="dashboard_snapshot",
    )
    app.router.add_get(
        "/stats/export.csv",
        stats_handlers.export_csv,
        name="stats_export_csv",
    )
    app.router.add_post("/clear_stats", stats_handlers.clear_stats, name="stats_clear")

    app.router.add_post(
        "/stats/test/start",
        test_session_handlers.start,
        name="test_session_start",
    )
    app.router.add_post(
        "/stats/test/finish",
        test_session_handlers.finish,
        name="test_session_finish",
    )
    app.router.add_post(
        "/stats/test/cancel",
        test_session_handlers.cancel,
        name="test_session_cancel",
    )
    app.router.add_get(
        "/stats/test/sessions",
        test_session_handlers.list_sessions,
        name="test_session_list",
    )
    app.router.add_get(
        "/stats/test/download/{file_path:.+}",
        test_session_handlers.download_csv,
        name="test_session_download",
    )
