import argparse
import socket


def build_parser():
    parser = argparse.ArgumentParser(description="Print RTCTraining LAN URLs")
    parser.add_argument("--webrtc-port", default=8080, type=int)
    parser.add_argument("--dashboard-port", default=8081, type=int)
    return parser


def detect_lan_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def main(argv=None):
    args = build_parser().parse_args(argv)
    hostname = socket.gethostname()
    lan_ip = detect_lan_ip()
    print(f"WebRTC local: https://localhost:{args.webrtc_port}/")
    print(f"WebRTC LAN IP: https://{lan_ip}:{args.webrtc_port}/")
    print(f"WebRTC hostname: https://{hostname}:{args.webrtc_port}/")
    print(f"Dashboard: http://127.0.0.1:{args.dashboard_port}/")


if __name__ == "__main__":
    main()
