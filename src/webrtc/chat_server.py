import argparse
import ssl

from aiohttp import web

from src.webrtc.app import create_webrtc_app
from src.webrtc.config import Settings


def build_parser():
    parser = argparse.ArgumentParser(description="RTCTraining WebRTC HTTPS service")
    parser.add_argument("command", nargs="?", default="run", choices=["run"])
    parser.add_argument("--host", default=Settings().webrtc_host)
    parser.add_argument("--port", default=Settings().webrtc_port, type=int)
    parser.add_argument("--cert", default=Settings().tls_cert_path)
    parser.add_argument("--key", default=Settings().tls_key_path)
    parser.add_argument("--no-tls", action="store_true")
    return parser


def ssl_context(cert_path, key_path):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_path, key_path)
    return context


def main(argv=None):
    args = build_parser().parse_args(argv)
    ssl_ctx = None if args.no_tls else ssl_context(args.cert, args.key)
    web.run_app(create_webrtc_app(), host=args.host, port=args.port, ssl_context=ssl_ctx)


if __name__ == "__main__":
    main()
