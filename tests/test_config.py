from src.webrtc.config import Settings
from src.webrtc.response import error_payload, success_payload


def test_default_settings_match_phase_0_contract():
    settings = Settings()

    assert settings.webrtc_host == "0.0.0.0"
    assert settings.webrtc_port == 8080
    assert settings.dashboard_host == "127.0.0.1"
    assert settings.dashboard_port == 8081
    assert settings.local_webrtc_origin == "https://localhost:8080"
    assert settings.local_signaling_url == "https://localhost:8080"
    assert settings.dashboard_origin == "http://localhost:8081"
    assert settings.tls_cert_path == "certs/cert.pem"
    assert settings.tls_key_path == "certs/key.pem"
    assert settings.data_dir == "data"
    assert settings.exports_dir == "data/exports"
    assert settings.test_sessions_dir == "data/test_sessions"
    assert settings.charts_dir == "data/charts"


def test_response_envelope_shape():
    assert success_payload({"room_id": "room1"}) == {
        "ok": True,
        "data": {"room_id": "room1"},
    }

    assert error_payload("bad_request", "room_id is required", {"field": "room_id"}) == {
        "ok": False,
        "error": {
            "code": "bad_request",
            "message": "room_id is required",
            "details": {"field": "room_id"},
        },
    }
