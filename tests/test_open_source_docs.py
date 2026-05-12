from pathlib import Path

from src.webrtc.csv_export import CSV_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_architecture_doc_declares_public_boundaries():
    body = read("docs/architecture.md")

    for text in [
        "WebRTC Service",
        "Dashboard Service",
        "HTTP API Layer",
        "Application Service Layer",
        "Domain Store Layer",
        "Browser App Layer",
        "Local/LAN only",
    ]:
        assert text in body


def test_api_docs_declare_stable_envelope_and_stats_schema():
    stats = read("docs/api/stats.md")
    errors = read("docs/api/errors.md")
    rooms_signaling = read("docs/api/rooms-signaling.md")
    csv_schema = read("docs/api/csv_schema.md")

    assert '{"ok": true, "data": {}}' in stats
    assert '{"ok": false, "error": {' in errors
    assert "POST /rooms/join" in rooms_signaling
    assert "POST /signal" in rooms_signaling
    assert "GET /dashboard/snapshot" in rooms_signaling
    for field in [
        "room_id",
        "peer_id",
        "remote_peer_id",
        "test_session_id",
        "rtt_ms",
        "packet_loss_rate",
        "jitter_ms",
        "bitrate_kbps",
        "fps",
    ]:
        assert field in stats
        assert field in csv_schema


def test_dashboard_doc_declares_proxy_safety_boundary():
    body = read("docs/api/dashboard.md")

    assert "Dashboard page only calls Dashboard Service" in body
    assert "origin allowlist" in body
    assert "not a general-purpose HTTP proxy" in body
    assert "exact origins" in body
    assert "bare hostnames" in body


def test_csv_schema_documents_every_exported_field():
    body = read("docs/api/csv_schema.md")

    for field in CSV_FIELDS:
        assert f"`{field}`" in body


def test_playwright_ci_evaluation_documents_costs_and_decision():
    body = read("docs/internal/agents/playwright_e2e_ci_evaluation.md")

    for text in [
        "Playwright E2E CI Evaluation",
        "python -m playwright install --with-deps chromium",
        "make test-e2e PYTHON=python",
        "browser install cost",
        "self-signed HTTPS",
        "fake media",
        "Recommendation",
        "do not add Playwright E2E as a required PR gate yet",
        "https://playwright.dev/python/docs/ci",
        "https://docs.github.com/en/actions/reference/runners/github-hosted-runners",
    ]:
        assert text in body


def test_release_checklist_declares_materials_and_internal_history_location():
    body = read("docs/open-source-release-checklist.md")

    for text in [
        "Open Source Release Checklist",
        "开源者需要提供以下信息与材料：",
        "Final license choice",
        "Security contact email",
        "Screenshot files",
        "docs/internal/",
    ]:
        assert text in body
