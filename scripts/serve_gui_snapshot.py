#!/usr/bin/env python3
"""Serve a Flutter GUI snapshot to Android tablets on the lab network.

Typical flow:
  scripts/export_gui_snapshot.py --route /home/sbeen/aris/data/routes/route.csv \
    --out /tmp/aris_gui_snapshot.json
  scripts/serve_gui_snapshot.py --snapshot /tmp/aris_gui_snapshot.json --host 0.0.0.0

Flutter run/build can then use:
  --dart-define=ARIS_SNAPSHOT_URL=http://<dev-env-ip>:8765/snapshot
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="GUI snapshot JSON produced by export_gui_snapshot.py.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Use 0.0.0.0 for Android tablets on LAN.")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port.")
    return parser.parse_args()


class SnapshotHandler(BaseHTTPRequestHandler):
    snapshot_path: Path

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path not in ("/", "/snapshot", "/snapshot.json"):
            self.send_error(404, "not found")
            return
        try:
            raw = self.snapshot_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            body = json.dumps(parsed, separators=(",", ":")).encode("utf-8")
        except Exception as exc:  # pragma: no cover - exercised from CLI smoke.
            self.send_error(500, f"snapshot unavailable: {exc}")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print("aris_gui_snapshot_bridge: " + fmt % args)


def main() -> None:
    args = parse_args()
    snapshot_path = Path(args.snapshot).expanduser().resolve()
    if not snapshot_path.exists():
        raise SystemExit(f"snapshot does not exist: {snapshot_path}")
    SnapshotHandler.snapshot_path = snapshot_path
    server = ThreadingHTTPServer((args.host, args.port), SnapshotHandler)
    print(f"serving {snapshot_path} at http://{args.host}:{args.port}/snapshot")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping aris_gui_snapshot_bridge")


if __name__ == "__main__":
    main()
