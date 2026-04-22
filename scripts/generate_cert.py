import argparse
import socket
import subprocess
from pathlib import Path


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate RTCTraining self-signed certificate"
    )
    parser.add_argument("--cert", default="certs/cert.pem")
    parser.add_argument("--key", default="certs/key.pem")
    parser.add_argument("--days", default=30, type=int)
    parser.add_argument("--host", action="append", default=[])
    return parser


def local_hostname():
    return socket.gethostname()


def local_ip_candidates():
    candidates = {"127.0.0.1"}
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        candidates.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    return sorted(candidates)


def san_config(hosts):
    dns_names = ["localhost", local_hostname()]
    ip_names = local_ip_candidates()
    for host in hosts:
        try:
            socket.inet_aton(host)
        except OSError:
            dns_names.append(host)
        else:
            ip_names.append(host)

    lines = [
        "[req]",
        "distinguished_name=req_distinguished_name",
        "x509_extensions=v3_req",
        "prompt=no",
        "[req_distinguished_name]",
        "CN=RTCTraining Local",
        "[v3_req]",
        "subjectAltName=@alt_names",
        "[alt_names]",
    ]
    for index, name in enumerate(dict.fromkeys(dns_names), start=1):
        lines.append(f"DNS.{index}={name}")
    for index, ip in enumerate(dict.fromkeys(ip_names), start=1):
        lines.append(f"IP.{index}={ip}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    args = build_parser().parse_args(argv)
    cert_path = Path(args.cert)
    key_path = Path(args.key)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    config_path = cert_path.parent / "openssl-san.cnf"
    config_path.write_text(san_config(args.host), encoding="utf-8")

    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            str(args.days),
            "-config",
            str(config_path),
        ],
        check=True,
    )
    print(f"wrote {cert_path} and {key_path}")


if __name__ == "__main__":
    main()
