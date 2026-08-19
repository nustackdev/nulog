"""``nulog`` CLI -- one command: open a RocksDB nulog in the browser viewer.

Always read-only via RocksDB secondary mode, so it's safe on a DB another
process is currently writing. Serves the nudle viewer on ``--host:--port``
until interrupted.
"""

from __future__ import annotations

import argparse
import asyncio

import nu

from . import presets


__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nulog",
        description="Open a RocksDB nulog store in the browser viewer.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    view = sub.add_parser(
        "view",
        help="Serve the live viewer over a nulog RocksDB (read-only, secondary mode).",
    )
    view.add_argument("path", help="RocksDB directory to open.")
    view.add_argument(
        "--host", default="127.0.0.1", help="Uvicorn bind address (default: 127.0.0.1)."
    )
    view.add_argument(
        "--port", type=int, default=8080, help="Uvicorn bind port (default: 8080)."
    )
    view.add_argument(
        "--secondary",
        default=None,
        metavar="PATH",
        help=(
            "RocksDB secondary directory. Defaults to a fresh temp dir; "
            "pass a stable path to reuse the tail state across restarts."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint. Registered as ``nulog`` via ``pyproject.toml``."""
    args = _build_parser().parse_args(argv)
    if args.cmd == "view":
        tree = presets.viewer(
            args.path,
            host=args.host,
            port=args.port,
            secondary_path=args.secondary,
        )
        try:
            asyncio.run(nu.arun(tree))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
