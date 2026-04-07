from __future__ import annotations

import argparse
import json
import threading
import webbrowser

import uvicorn

from .main import app
from .local_main import app as local_app
from .services.local_config import write_local_config
from .services.runner import probe_local_environment, scan_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JayAI server and runner utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the central API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    local = subparsers.add_parser("local-ui", help="Run the local UI and local runner")
    local.add_argument("--host", default="127.0.0.1")
    local.add_argument("--port", type=int, default=8310)
    local.add_argument("--server-url", default="")
    local.add_argument("--open-browser", action="store_true")

    probe = subparsers.add_parser("probe", help="Probe local CLI/install/auth status")
    probe.add_argument("--workdir", default=".")

    scan = subparsers.add_parser("scan-workspace", help="Inspect a workspace path")
    scan.add_argument("path")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run(app, host=args.host, port=args.port)
        return

    if args.command == "local-ui":
        if args.server_url:
            write_local_config(args.server_url)
        if args.open_browser:
            threading.Timer(
                1.0,
                lambda: webbrowser.open(f"http://{args.host}:{args.port}/"),
            ).start()
        uvicorn.run(local_app, host=args.host, port=args.port)
        return

    if args.command == "probe":
        print(json.dumps(probe_local_environment(args.workdir).model_dump(), indent=2, ensure_ascii=False))
        return

    if args.command == "scan-workspace":
        print(json.dumps(scan_workspace(args.path).model_dump(), indent=2, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
