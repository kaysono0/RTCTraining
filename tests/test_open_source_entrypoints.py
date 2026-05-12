from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_open_source_entrypoint_files_exist():
    for path in [
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        ".env.example",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/feature_request.md",
        ".github/pull_request_template.md",
        ".github/dependabot.yml",
    ]:
        assert (ROOT / path).is_file()


def test_readme_contains_quickstart_harness_and_project_scope():
    body = read("README.md")

    for text in [
        "RTCTraining",
        "Local/LAN WebRTC",
        "make cert",
        ".env.example",
        "make harness-smoke",
        "make run-webrtc",
        "make run-dashboard",
        "make test-unit",
        "make test-e2e",
        "https://localhost:8080",
        "http://127.0.0.1:8081",
        "docs/api/rooms-signaling.md",
        "docs/open-source-release-checklist.md",
        "开源者需要提供以下信息与材料：",
    ]:
        assert text in body


def test_contributing_declares_required_project_boundaries():
    body = read("CONTRIBUTING.md")

    for text in [
        "Keep WebRTC Service and Dashboard Service boundaries clear",
        "Keep stores independent from aiohttp",
        "Preserve JSON response envelopes",
        "Preserve window.__RTCTrainingTestHooks",
        "Update CHANGELOG.md",
    ]:
        assert text in body


def test_security_doc_warns_against_public_exposure():
    body = read("SECURITY.md")

    assert "Do not expose RTCTraining directly to the public internet" in body
    assert "no authentication" in body
    assert "origin allowlist" in body
    assert "Security contact email" in body


def test_github_templates_capture_contributor_workflow():
    bug = read(".github/ISSUE_TEMPLATE/bug_report.md")
    feature = read(".github/ISSUE_TEMPLATE/feature_request.md")
    pr = read(".github/pull_request_template.md")
    dependabot = read(".github/dependabot.yml")

    assert "make harness-smoke" in bug
    assert "Local/LAN trusted-network usage" in feature
    assert "Preserves JSON response envelopes" in pr
    assert "package-ecosystem: \"pip\"" in dependabot


def test_ci_runs_unit_and_harness_smoke_without_playwright():
    body = read(".github/workflows/ci.yml")

    assert "make test-unit PYTHON=python" in body
    assert "make harness-smoke PYTHON=python" in body
    assert "make test-e2e" not in body
    assert "playwright install" not in body
