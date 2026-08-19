"""Bound :class:`Logger` -- the class-based write surface.

Mirrors ``nu.std.logging.Logger`` / ``logging.Logger``::

    from nulog import getLogger

    log = getLogger("app")

    tree = (
        log.info("server started")
        >> log.warning("cache miss for %s", key)
        >> log.error("checkout failed", extra={"code": 500})
    )

The logger *name* IS the stream name.
Every ``log.info(...)`` compiles to one :func:`.append.append` on
``Messages.streams[name].entries``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .append import append
from .types import CRITICAL, DEBUG, ERROR, INFO, WARNING


if TYPE_CHECKING:
    import nu
    from nu.lang import IntArg, StrArg


__all__ = [
    "Logger",
    "getLogger",
]


class Logger:
    """Bound logger. Mirrors ``nu.std.logging.Logger`` / ``logging.Logger``.

    ``getLogger(__name__)`` at module top, then ``log.info(...)`` at call sites.
    Each method returns a Nu Command tree carrying the bound stream name.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        """Bind this Logger to stream ``name``."""
        self._name = name

    @property
    def name(self) -> str:
        """The stream name this logger is bound to."""
        return self._name

    def log(
        self,
        level: IntArg | StrArg,
        msg: StrArg,
        *args: object,
        extra: dict[str, object] | None = None,
    ) -> nu.Nu:
        """Build a persistent entry at ``level``."""
        return append(self._name, level, msg, args, extra)

    def debug(self, msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent DEBUG entry."""
        return append(self._name, DEBUG, msg, args, extra)

    def info(self, msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent INFO entry."""
        return append(self._name, INFO, msg, args, extra)

    def warning(self, msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent WARNING entry."""
        return append(self._name, WARNING, msg, args, extra)

    warn = warning

    def error(self, msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent ERROR entry."""
        return append(self._name, ERROR, msg, args, extra)

    def critical(self, msg: StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent CRITICAL entry."""
        return append(self._name, CRITICAL, msg, args, extra)

    fatal = critical

    def __repr__(self) -> str:
        return f"nulog.Logger(name={self._name!r})"


def getLogger(name: str | None = None) -> Logger:  # noqa: N802
    """Return a bound :class:`Logger`. Mirrors ``logging.getLogger``."""
    return Logger(name if name is not None else "root")
