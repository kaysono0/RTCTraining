import os
from dataclasses import dataclass


def _env_str(name, default):
    return os.environ.get(name, default)


def _env_int(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    webrtc_host: str = "0.0.0.0"
    webrtc_port: int = 8080
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8081
    local_webrtc_origin: str = "https://localhost:8080"
    local_signaling_url: str = "https://localhost:8080"
    dashboard_origin: str = "http://localhost:8081"
    tls_cert_path: str = "certs/cert.pem"
    tls_key_path: str = "certs/key.pem"
    data_dir: str = "data"
    exports_dir: str = "data/exports"
    test_sessions_dir: str = "data/test_sessions"
    charts_dir: str = "data/charts"
    dashboard_origin_allowlist: str = (
        "https://localhost:8080,"
        "https://127.0.0.1:8080,"
        "http://localhost:8080,"
        "http://127.0.0.1:8080"
    )

    @classmethod
    def from_env(cls):
        return cls(
            webrtc_host=_env_str("RTC_WEBRTC_HOST", cls.webrtc_host),
            webrtc_port=_env_int("RTC_WEBRTC_PORT", cls.webrtc_port),
            dashboard_host=_env_str("RTC_DASHBOARD_HOST", cls.dashboard_host),
            dashboard_port=_env_int("RTC_DASHBOARD_PORT", cls.dashboard_port),
            local_webrtc_origin=_env_str("RTC_LOCAL_WEBRTC_ORIGIN", cls.local_webrtc_origin),
            local_signaling_url=_env_str("RTC_LOCAL_SIGNALING_URL", cls.local_signaling_url),
            dashboard_origin=_env_str("RTC_DASHBOARD_ORIGIN", cls.dashboard_origin),
            tls_cert_path=_env_str("RTC_TLS_CERT_PATH", cls.tls_cert_path),
            tls_key_path=_env_str("RTC_TLS_KEY_PATH", cls.tls_key_path),
            data_dir=_env_str("RTC_DATA_DIR", cls.data_dir),
            exports_dir=_env_str("RTC_EXPORTS_DIR", cls.exports_dir),
            test_sessions_dir=_env_str("RTC_TEST_SESSIONS_DIR", cls.test_sessions_dir),
            charts_dir=_env_str("RTC_CHARTS_DIR", cls.charts_dir),
            dashboard_origin_allowlist=_env_str(
                "RTC_DASHBOARD_ORIGIN_ALLOWLIST",
                cls.dashboard_origin_allowlist,
            ),
        )
