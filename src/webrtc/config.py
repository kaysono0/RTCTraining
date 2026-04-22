from dataclasses import dataclass


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
