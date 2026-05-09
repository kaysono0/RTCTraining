import argparse
import asyncio
import subprocess
import time
from urllib.parse import urlencode

from automation.harness.http_checks import (
    HarnessCheckError,
    check_json_ok,
    check_text_contains,
    fetch_text,
)
from automation.harness.process_manager import (
    start_python_module,
    stop_all,
    wait_for_process_exit,
)


async def wait_for_http(url, expected_text=None, timeout=10):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            if expected_text is None:
                await fetch_text(url)
            else:
                await check_text_contains(url, expected_text)
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(0.25)
    raise HarnessCheckError(f"{url} did not become ready: {last_error}")


async def run_smoke(args):
    if args.generate_cert:
        subprocess.run([args.python, "scripts/generate_cert.py"], check=True)

    processes = []
    try:
        processes.append(
            start_python_module(
                "webrtc",
                "src.webrtc.chat_server",
                "run",
                "--host",
                args.webrtc_host,
                "--port",
                str(args.webrtc_port),
                python_executable=args.python,
            )
        )
        processes.append(
            start_python_module(
                "dashboard",
                "src.dashboard.server",
                "run",
                "--host",
                args.dashboard_host,
                "--port",
                str(args.dashboard_port),
                python_executable=args.python,
            )
        )

        failed = wait_for_process_exit(processes)
        if failed:
            details = "; ".join(
                f"{process.name}: {process.stderr_tail() or 'no stderr'}"
                for process in failed
            )
            raise HarnessCheckError(f"service process exited early: {details}")

        webrtc_origin = f"https://{args.webrtc_host}:{args.webrtc_port}"
        dashboard_origin = f"http://{connect_host(args.dashboard_host)}:{args.dashboard_port}"

        await wait_for_http(f"{webrtc_origin}/", "RTCTraining", timeout=args.timeout)
        await wait_for_http(f"{dashboard_origin}/", "Dashboard", timeout=args.timeout)
        await check_json_ok(f"{webrtc_origin}/stats/peers?room_id=room1")
        await check_json_ok(build_dashboard_proxy_url(dashboard_origin, webrtc_origin))
        csv_text = await fetch_text(f"{webrtc_origin}/stats/export.csv?room_id=room1")
        if not csv_text.startswith("sample_index,timestamp,room_id"):
            raise HarnessCheckError("CSV export did not return the expected header")

        print("harness smoke passed")
    finally:
        stop_all(processes)


def connect_host(host):
    return "127.0.0.1" if host == "0.0.0.0" else host


def build_dashboard_proxy_url(dashboard_origin, webrtc_origin, room_id="room1"):
    query = urlencode({"origin": webrtc_origin, "room_id": room_id})
    return f"{dashboard_origin}/api/webrtc/stats/peers?{query}"


def build_parser():
    parser = argparse.ArgumentParser(description="RTCTraining local harness smoke")
    parser.add_argument("--python", default=".venv/bin/python")
    parser.add_argument("--webrtc-host", default="127.0.0.1")
    parser.add_argument("--webrtc-port", type=int, default=8080)
    parser.add_argument("--dashboard-host", default="127.0.0.1")
    parser.add_argument("--dashboard-port", type=int, default=8081)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--generate-cert", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    asyncio.run(run_smoke(args))


if __name__ == "__main__":
    main()
