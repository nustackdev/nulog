"""Log writes -- Logger-class API mirroring ``nu.std.logging``.

The write surface is Python-``logging``-shaped, identical to
``nu.std.logging``::

    from nulog import getLogger

    log = getLogger("app")

    tree = (
        log.info("server started")
        >> log.warning("cache miss for %s", key)
        >> log.error("checkout failed", extra={"code": 500})
    )

Only difference from ``nu.std.logging``: the returned trees persist into
``Messages.streams[name].entries`` (a :class:`ShapesListRef`) when driven
under a ``nulog.store(...)`` bracket, rather than firing through Python's
``logging`` module. The logger *name* IS the stream name.

Every ``log.info(...)`` compiles to one ``AppendCommand`` on the stream's
entries list -- no scratch attrs, no key encoding, no SetCommand chain.
The eval-time seams are ``LevelName`` / ``PercentFormat`` / ``FieldsAsJson``
(pure formatting) and :func:`nu.std.time.time_ns` (the clock).
"""

from __future__ import annotations

import json
import logging as _pylogging

import nu
import nu.std.time as _nu_time

from .shape import Messages


__all__ = [
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "NOTSET",
    "WARN",
    "WARNING",
    "FieldsAsJson",
    "LevelName",
    "Logger",
    "PercentFormat",
    "critical",
    "debug",
    "error",
    "getLogger",
    "info",
    "log",
    "warn",
    "warning",
]


# --- level constants (parity with Python's logging / nu.std.logging) --------

DEBUG = _pylogging.DEBUG
INFO = _pylogging.INFO
WARNING = _pylogging.WARNING
WARN = _pylogging.WARNING
ERROR = _pylogging.ERROR
CRITICAL = _pylogging.CRITICAL
FATAL = _pylogging.CRITICAL
NOTSET = _pylogging.NOTSET


_LEVEL_NAMES: dict[int, str] = {
    _pylogging.DEBUG: "debug",
    _pylogging.INFO: "info",
    _pylogging.WARNING: "warning",
    _pylogging.ERROR: "error",
    _pylogging.CRITICAL: "critical",
    _pylogging.NOTSET: "notset",
}


def _now_us() -> nu.Nu:
    """Absolute epoch microseconds -- the ``ts_us`` slot value at eval time."""
    return _nu_time.time_ns() // 1000


@nu.host
def FieldsAsJson(fields: dict) -> str:  # noqa: N802
    """Encode structured fields as a compact JSON string (empty on falsy)."""
    if not fields:
        return ""
    return json.dumps(fields, separators=(",", ":"), default=repr)


@nu.host
def LevelName(level: object) -> str:  # noqa: N802
    """Normalize a level (int or name) into the canonical lowercase name."""
    if isinstance(level, int) and not isinstance(level, bool):
        return _LEVEL_NAMES.get(level, "info")
    if isinstance(level, str):
        low = level.lower()
        return "warning" if low == "warn" else low
    return "info"


@nu.host
def PercentFormat(msg: object, *args: object) -> str:  # noqa: N802
    """``msg % args`` if args are present, else ``str(msg)``.

    Mirrors ``logging.LogRecord.getMessage``.
    """
    text = str(msg)
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        return text + " " + " ".join(str(a) for a in args)


def _entry(
    stream: str | nu.Nu,
    level: object,
    msg: object,
    args: tuple[object, ...],
    extra: dict[str, object] | None,
) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``."""
    level_term = LevelName(level)
    msg_term = PercentFormat(msg, *args) if args else PercentFormat(msg)
    fields_dict = nu.DictForm.of(
        **{k: nu.LiteralQuery(v) for k, v in (extra or {}).items()},
    )
    return Messages.streams[stream].entries.append(nu.DictForm.of(
        ts_us=_now_us(),
        level=level_term,
        msg=msg_term,
        fields=FieldsAsJson(fields_dict),
    ))


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
        level: int | str,
        msg: object,
        *args: object,
        extra: dict[str, object] | None = None,
    ) -> nu.Nu:
        """Build a persistent entry at ``level``."""
        return _entry(self._name, level, msg, args, extra)

    def debug(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent DEBUG entry."""
        return _entry(self._name, DEBUG, msg, args, extra)

    def info(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent INFO entry."""
        return _entry(self._name, INFO, msg, args, extra)

    def warning(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent WARNING entry."""
        return _entry(self._name, WARNING, msg, args, extra)

    warn = warning

    def error(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent ERROR entry."""
        return _entry(self._name, ERROR, msg, args, extra)

    def critical(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent CRITICAL entry."""
        return _entry(self._name, CRITICAL, msg, args, extra)

    fatal = critical

    def __repr__(self) -> str:
        return f"nulog.Logger(name={self._name!r})"


def getLogger(name: str | None = None) -> Logger:  # noqa: N802
    """Return a bound :class:`Logger`. Mirrors ``logging.getLogger``."""
    return Logger(name if name is not None else "root")


_root = Logger("root")


def debug(msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream DEBUG entry. Mirrors ``logging.debug``."""
    return _root.debug(msg, *args, extra=extra)


def info(msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream INFO entry. Mirrors ``logging.info``."""
    return _root.info(msg, *args, extra=extra)


def warning(msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream WARNING entry. Mirrors ``logging.warning``."""
    return _root.warning(msg, *args, extra=extra)


warn = warning


def error(msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream ERROR entry. Mirrors ``logging.error``."""
    return _root.error(msg, *args, extra=extra)


def critical(msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream CRITICAL entry. Mirrors ``logging.critical``."""
    return _root.critical(msg, *args, extra=extra)


def log(
    level: int | str,
    msg: object,
    *args: object,
    extra: dict[str, object] | None = None,
) -> nu.Nu:
    """Root-stream entry at ``level``. Mirrors ``logging.log``."""
    return _root.log(level, msg, *args, extra=extra)
