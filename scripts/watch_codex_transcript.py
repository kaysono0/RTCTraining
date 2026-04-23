from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.runner.transcript_watch import wait_for_quiet_transcript


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wait for Codex transcript output to go quiet")
    parser.add_argument("transcript", help="Path to a JSONL transcript file")
    parser.add_argument("--quiet-seconds", type=float, default=60.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = wait_for_quiet_transcript(
        Path(args.transcript),
        quiet_seconds=args.quiet_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
