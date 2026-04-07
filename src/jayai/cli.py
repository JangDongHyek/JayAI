from __future__ import annotations

import argparse
import json

import uvicorn

from .main import app
from .services.runner import probe_local_environment, scan_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JayAI server and runner utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

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

    if args.command == "probe":
        print(json.dumps(probe_local_environment(args.workdir).model_dump(), indent=2, ensure_ascii=False))
        return

    if args.command == "scan-workspace":
        print(json.dumps(scan_workspace(args.path).model_dump(), indent=2, ensure_ascii=False))
        return


if __name__ == "__main__":
    main()
