from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_open_source_entrypoint_files_exist():
    for path in [
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CHANGELOG.md",
        ".github/workflows/ci.yml",
    ]:
        assert (ROOT / path).is_file()


def test_readme_contains_quickstart_harness_and_project_scope():
    body = read("README.md")

    for text in [
        "RTCTraining",
        "Local/LAN WebRTC",
        "make cert",
        "make harness-smoke",
        "make run-webrtc",
        "make run-dashboard",
        "make test-unit",
        "make test-e2e",
        "https://localhost:8080",
        "http://127.0.0.1:8081",
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


def test_ci_runs_unit_tests_only_for_phase_1():
    body = read(".github/workflows/ci.yml")

    assert "make test-unit PYTHON=python" in body
    assert "make harness-smoke" not in body
    assert "make test-e2e" not in body
    assert "playwright install" not in body
