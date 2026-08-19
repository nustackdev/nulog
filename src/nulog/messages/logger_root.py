"""Module-level root-logger facade. Mirrors ``logging.info`` / ``logging.debug`` / ...

Convenience for one-off writes that don't want a bound :class:`Logger`. All
functions delegate to a single ``Logger("root")`` -- the ``root`` stream is
where the entries land::

    import nulog

    tree = nulog.info("server started", extra={"port": 8080})
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .logger import Logger


if TYPE_CHECKING:
    import nu
    from nu.lang import IntArg, StrArg


__all__ = [
    "critical",
    "debug",
    "error",
    "info",
    "log",
    "warn",
    "warning",
]


_root = Logger("root")


def debug(msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream DEBUG entry. Mirrors ``logging.debug``."""
    return _root.debug(msg, *args, extra=extra)


def info(msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream INFO entry. Mirrors ``logging.info``."""
    return _root.info(msg, *args, extra=extra)


def warning(msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream WARNING entry. Mirrors ``logging.warning``."""
    return _root.warning(msg, *args, extra=extra)


warn = warning


def error(msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream ERROR entry. Mirrors ``logging.error``."""
    return _root.error(msg, *args, extra=extra)


def critical(msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream CRITICAL entry. Mirrors ``logging.critical``."""
    return _root.critical(msg, *args, extra=extra)


def log(
    level: IntArg | StrArg,
    msg: StrArg,
    *args: object,
    extra: dict[str, object] | None = None,
) -> nu.Nu:
    """Root-stream entry at ``level``. Mirrors ``logging.log``."""
    return _root.log(level, msg, *args, extra=extra)
