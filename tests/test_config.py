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
    assert "localhost" in settings.dashboard_origin_allowlist


def test_settings_reads_environment_overrides(monkeypatch):
    monkeypatch.setenv("RTC_WEBRTC_HOST", "127.0.0.1")
    monkeypatch.setenv("RTC_WEBRTC_PORT", "18080")
    monkeypatch.setenv("RTC_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("RTC_DASHBOARD_PORT", "18081")
    monkeypatch.setenv("RTC_LOCAL_WEBRTC_ORIGIN", "http://127.0.0.1:18080")
    monkeypatch.setenv("RTC_TEST_SESSIONS_DIR", "tmp/test-sessions")
    monkeypatch.setenv("RTC_DASHBOARD_ORIGIN_ALLOWLIST", "localhost,127.0.0.1")

    settings = Settings.from_env()

    assert settings.webrtc_host == "127.0.0.1"
    assert settings.webrtc_port == 18080
    assert settings.dashboard_host == "0.0.0.0"
    assert settings.dashboard_port == 18081
    assert settings.local_webrtc_origin == "http://127.0.0.1:18080"
    assert settings.test_sessions_dir == "tmp/test-sessions"
    assert settings.dashboard_origin_allowlist == "localhost,127.0.0.1"


def test_settings_rejects_invalid_integer_environment(monkeypatch):
    monkeypatch.setenv("RTC_WEBRTC_PORT", "not-a-port")

    try:
        Settings.from_env()
    except ValueError as exc:
        assert "RTC_WEBRTC_PORT must be an integer" in str(exc)
    else:
        raise AssertionError("Settings.from_env() should reject invalid port values")


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
