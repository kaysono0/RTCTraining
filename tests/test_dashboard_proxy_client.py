from src.dashboard.proxy_client import build_upstream_url


def test_build_upstream_url_strips_origin_and_encodes_remaining_query():
    url = build_upstream_url(
        "https://localhost:8080/",
        "/stats/peers",
        {
            "origin": "https://localhost:8080",
            "room_id": "room 1",
            "peer_id": "alice",
        },
    )

    assert url == "https://localhost:8080/stats/peers?room_id=room+1&peer_id=alice"


def test_build_upstream_url_handles_empty_query():
    assert build_upstream_url("https://localhost:8080/", "/stats", {}) == (
        "https://localhost:8080/stats"
    )
