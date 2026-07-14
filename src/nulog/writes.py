"""Log + metric writes -- Logger-class API mirroring ``nu.std.logging``.

The public write surface is Python-``logging``-shaped, identical to
``nu.std.logging``::

    from nulog import getLogger

    log = getLogger("app")

    tree = (
        log.info("server started")
        >> log.warning("cache miss for %s", key)
        >> log.error("checkout failed", extra={"code": 500})
        >> observe("cpu_load", 0.42)
    )

Only difference from ``nu.std.logging``: the returned trees persist into
``Logs.streams[name].entries`` (a kh57 shape map) when driven under a
``nulog.store(...)`` bracket, rather than firing through Python's
``logging`` module. The logger *name* IS the stream name.

Every Command builds a small ``SetCommand >> SetCommand >> store(...)``
chain around a shared eval-time microsecond so the stored ``ts_us`` and
the kh57 sort key can never drift. All eval-time seams are
``@nu.host(deterministic=False)`` for the clock/counter atoms, plain
``@nu.host`` for pure formatting.

Metrics ride alongside on the same kh57 substrate: ``observe(name, value)``
appends one point to ``Metrics.series[name].points`` keyed by microsecond
epoch.
"""

from __future__ import annotations

import itertools
import json
import logging as _pylogging

import nu
import nu.std.time as _nu_time

from .shapes import Logs, Metrics


__all__ = [
    # level constants (mirror Python's logging for parity)
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "NOTSET",
    "WARN",
    "WARNING",
    # @nu.host atoms (advanced -- exposed for the from_std_logging rewriter)
    "EncodeLogKey",
    "FieldsAsJson",
    "LevelName",
    "Logger",
    "PercentFormat",
    # module-level shortcuts (mirror logging.debug / logging.info / ...)
    "critical",
    "debug",
    "error",
    "getLogger",
    "info",
    "log",
    # metric write
    "observe",
    "warn",
    "warning",
]


# --- level constants (parity with Python's logging / nu.std.logging) --------

DEBUG = _pylogging.DEBUG
INFO = _pylogging.INFO
WARNING = _pylogging.WARNING
WARN = _pylogging.WARNING  # stdlib alias
ERROR = _pylogging.ERROR
CRITICAL = _pylogging.CRITICAL
FATAL = _pylogging.CRITICAL  # stdlib alias
NOTSET = _pylogging.NOTSET


# Int -> canonical lowercase name for the stored ``level`` slot. Anything
# outside these codes stores as ``"info"``.
_LEVEL_NAMES: dict[int, str] = {
    _pylogging.DEBUG: "debug",
    _pylogging.INFO: "info",
    _pylogging.WARNING: "warning",
    _pylogging.ERROR: "error",
    _pylogging.CRITICAL: "critical",
    _pylogging.NOTSET: "notset",
}


# Kh57 keys are 57 bits. Anchoring the epoch at 2020 leaves ~46 bits of
# microseconds for decades; shifting by 8 makes room for a sub-microsecond
# counter (256 slots per us) so same-us writes get distinct positions.
_EPOCH_US = 1_577_836_800_000_000  # 2020-01-01T00:00:00Z in us since Unix epoch

# Per-process counters. ``_key_counter`` is the sub-microsecond LSB folded
# into every kh57 key. ``_call_counter`` gives every construct-time write
# call a distinct scratch-attr name so parallel composition never collides.
_key_counter = itertools.count()
_call_counter = itertools.count()


# --- eval-time value producers ----------------------------------------------
#
# ``_now_us`` / ``_now_seconds`` are Nu Forms over ``nu.std.time``: the clock
# reads are already non-deterministic atoms in nu's stdlib. ``EncodeLogKey``
# stays as a ``@nu.host`` because it folds the per-process counter LSB into the
# kh57 key.


def _now_us() -> nu.Nu:
    """Absolute epoch microseconds -- the ``ts_us`` slot value at eval time."""
    return _nu_time.time_ns() // 1000


def _now_seconds() -> nu.Nu:
    """Absolute epoch seconds -- the metric point ``ts`` slot at eval time."""
    return _nu_time.time()


@nu.host(deterministic=False)
def EncodeLogKey(us: int) -> int:  # noqa: N802
    """Encode an absolute-microsecond ``us`` into a fresh kh57 log key.

    Formula: ``((us - _EPOCH_US) << 8) | (counter & 0xff)``. Chronological --
    keys sort by microsecond, then by the sub-us counter LSB (256 slots per
    us). Fits under ``2**57`` for decades. The counter is bumped at eval
    time so two writes at the same microsecond get distinct positions.
    """
    off = max(0, us - _EPOCH_US)
    return (off << 8) | (next(_key_counter) & 0xFF)


@nu.host
def FieldsAsJson(fields: dict) -> str:  # noqa: N802
    """Encode structured fields as a compact JSON string (empty on falsy)."""
    if not fields:
        return ""
    return json.dumps(fields, separators=(",", ":"), default=repr)


@nu.host
def LevelName(level: object) -> str:  # noqa: N802
    """Normalize a level (int or name) into the canonical lowercase name.

    Python ``logging`` int codes map to ``"debug"``/``"info"``/``"warning"``/
    ``"error"``/``"critical"``. Any string is lowercased. Anything else
    falls back to ``"info"``.
    """
    if isinstance(level, int) and not isinstance(level, bool):
        return _LEVEL_NAMES.get(level, "info")
    if isinstance(level, str):
        # normalize "warn" alias -> "warning" so storage stays canonical
        low = level.lower()
        return "warning" if low == "warn" else low
    return "info"


@nu.host
def PercentFormat(msg: object, *args: object) -> str:  # noqa: N802
    """``msg % args`` if args are present, else ``str(msg)``.

    Mirrors ``logging.LogRecord.getMessage`` -- the same evaluation Python's
    ``logging`` module runs on ``(msg, args)`` before handing to formatters.
    """
    text = str(msg)
    if not args:
        return text
    try:
        return text % args
    except (TypeError, ValueError):
        # Malformed format string / arity mismatch -- fall back to a safe
        # repr so we never crash the write path.
        return text + " " + " ".join(str(a) for a in args)


# --- internal builder -------------------------------------------------------


def _entry(
    stream: str | nu.Nu,
    level: object,
    msg: object,
    args: tuple[object, ...],
    extra: dict[str, object] | None,
) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``.

    Arguments accept either raw Python values or Nu terms; the tree does the
    right coercion for each. Structured ``extra`` is captured now and
    JSON-encoded at eval time.
    """
    seq = next(_call_counter)
    us = nu.IntAttrRef(f"_nl_log_us_{seq}")
    key = nu.IntAttrRef(f"_nl_log_key_{seq}")
    rec = Logs.streams[stream].entries[key]

    # Level: pass through LevelName for uniform canonicalization -- static
    # ints fold, dynamic terms normalize at eval time.
    level_term = LevelName(level)

    # msg: PercentFormat also handles the no-args case (plain str(msg)),
    # so we always route through it -- keeps one code path.
    msg_term = PercentFormat(msg, *args) if args else PercentFormat(msg)

    # Structured fields dict is static Python only; dynamic values belong in
    # msg via %-args. Empty dict yields an empty JSON string.
    fields_dict = nu.DictForm.of(
        **{k: nu.LiteralQuery(v) for k, v in (extra or {}).items()},
    )

    return (
        nu.SetCommand(us, _now_us())
        >> nu.SetCommand(key, EncodeLogKey(us))
        >> rec.store(nu.DictForm.of(
            ts_us=us,
            level=level_term,
            msg=msg_term,
            fields=FieldsAsJson(fields_dict),
        ))
    )


# --- Logger class (mirrors nu.std.logging.Logger / logging.Logger) ---------


class Logger:
    """Bound logger. Mirrors ``nu.std.logging.Logger`` and Python's ``logging.Logger``.

    ``getLogger(__name__)`` at module top, then ``log.info(...)`` /
    ``log.warning(...)`` / ``log.error(...)`` at call sites. Each method
    returns a Nu ``Command`` tree carrying the bound logger name -- driven
    inside a ``nulog.store(...)`` bracket, that persists into
    ``Logs.streams[name]`` via the kh57 shape map.

    Not itself a ``logging.Logger`` -- this is the *call* surface only.
    Configuration (add handlers, set levels) doesn't apply here; the
    handler is nulog's persistent store, not Python's logging module.
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
        """Build a persistent entry at ``level``. Mirrors ``Logger.log``."""
        return _entry(self._name, level, msg, args, extra)

    def debug(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent DEBUG entry. Mirrors ``Logger.debug``."""
        return _entry(self._name, DEBUG, msg, args, extra)

    def info(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent INFO entry. Mirrors ``Logger.info``."""
        return _entry(self._name, INFO, msg, args, extra)

    def warning(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent WARNING entry. Mirrors ``Logger.warning``."""
        return _entry(self._name, WARNING, msg, args, extra)

    # `warn` is stdlib's alias.
    warn = warning

    def error(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent ERROR entry. Mirrors ``Logger.error``."""
        return _entry(self._name, ERROR, msg, args, extra)

    def critical(self, msg: object, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent CRITICAL entry. Mirrors ``Logger.critical``."""
        return _entry(self._name, CRITICAL, msg, args, extra)

    # `fatal` is stdlib's alias.
    fatal = critical

    def __repr__(self) -> str:
        return f"nulog.Logger(name={self._name!r})"


def getLogger(name: str | None = None) -> Logger:  # noqa: N802 -- stdlib name
    """Return a bound :class:`Logger`. Mirrors ``logging.getLogger(name)``.

    Passing ``None`` (or omitting) returns the ``"root"`` stream logger --
    same as Python's stdlib.
    """
    return Logger(name if name is not None else "root")


# --- module-level shortcuts (mirror ``logging.debug`` / ``logging.info`` ...) ---
#
# In the stdlib these fire against the root logger; here they build Nu trees
# against the root stream (name ``"root"``). Identical call shape.

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


warn = warning  # stdlib alias


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


# --- metric write (nulog extension -- no Python-logging analogue) -----------


def observe(name: str, value: float, *, ts: float | None = None) -> nu.Nu:
    """Build the Command tree that appends one point to metric ``name``.

    Args:
        name: series name (``"cpu_load"``, ``"http_latency_ms"``, ...).
        value: the sample.
        ts: optional wall-clock time (seconds since epoch). When ``None``,
            the key + ``ts`` slot are minted at eval time via :data:`NowUs`
            / :data:`NowSeconds`; pass an explicit ``ts`` for replay or
            batched observations. Same-microsecond writes collide
            (last-write-wins).
    """
    seq = next(_call_counter)
    key = nu.IntAttrRef(f"_nl_metric_key_{seq}")
    pt = Metrics.series[name].points[key]

    if ts is None:
        key_query: nu.Nu = _now_us()
        ts_query: nu.Nu = _now_seconds()
    else:
        key_query = nu.LiteralQuery(int(ts * 1_000_000))
        ts_query = nu.FloatForm(float(ts))

    return (
        nu.SetCommand(key, key_query)
        >> pt.store(nu.DictForm.of(
            ts=ts_query,
            value=nu.FloatForm(float(value)),
        ))
    )
