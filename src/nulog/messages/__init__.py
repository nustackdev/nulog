"""nulog.messages -- log-message store: shape + write API + read API.

Writes are Python-``logging``-shaped (``nulog.getLogger(...).info(...)``); reads
are three positional primitives (``tail``, ``slice``, ``point``) that touch
only the entries they return. See :mod:`nulog.messages.shape` for the store
layout, :mod:`nulog.messages.log` for writes, :mod:`nulog.messages.query`
for reads.
"""

from __future__ import annotations

from .log import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARN,
    WARNING,
    FieldsAsJson,
    LevelName,
    Logger,
    PercentFormat,
    critical,
    debug,
    error,
    getLogger,
    info,
    log,
    warn,
    warning,
)
from .query import FieldsFromJson, point, slice, tail
from .rewrite import from_std_logging
from .shape import LEVELS, LogEntry, Messages, MessageStream


__all__ = [
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "LEVELS",
    "NOTSET",
    "WARN",
    "WARNING",
    "FieldsAsJson",
    "FieldsFromJson",
    "LevelName",
    "LogEntry",
    "Logger",
    "MessageStream",
    "Messages",
    "PercentFormat",
    "critical",
    "debug",
    "error",
    "from_std_logging",
    "getLogger",
    "info",
    "log",
    "point",
    "slice",
    "tail",
    "warn",
    "warning",
]
