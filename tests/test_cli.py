import subprocess
import sys


def run_help(module_or_script):
    command = [sys.executable]
    if module_or_script.endswith(".py"):
        command.append(module_or_script)
    else:
        command.extend(["-m", module_or_script])
    command.append("--help")
    return subprocess.run(command, check=False, capture_output=True, text=True)


def test_webrtc_server_help_is_available():
    result = run_help("src.webrtc.chat_server")

    assert result.returncode == 0
    assert "RTCTraining WebRTC HTTPS service" in result.stdout


def test_dashboard_server_help_is_available():
    result = run_help("src.dashboard.server")

    assert result.returncode == 0
    assert "RTCTraining Dashboard service" in result.stdout


def test_generate_cert_help_is_available():
    result = run_help("scripts/generate_cert.py")

    assert result.returncode == 0
    assert "Generate RTCTraining self-signed certificate" in result.stdout


def test_print_lan_urls_help_is_available():
    result = run_help("scripts/print_lan_urls.py")

    assert result.returncode == 0
    assert "Print RTCTraining LAN URLs" in result.stdout


def test_automation_runner_help_is_available():
    result = run_help("automation.runner.orchestrator")

    assert result.returncode == 0
    assert "RTCTraining autonomous automation runner" in result.stdout
