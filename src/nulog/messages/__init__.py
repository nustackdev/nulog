"""nulog.messages -- log-message store: types + core write/read + facades.

Module layout:

Core (what a log IS):
- :mod:`.append`       -- the write-tree primitive (``append(stream, level, msg, ...)``).
- :mod:`.query`        -- reads (``tail`` / ``slice`` / ``point``).
- :mod:`.shapes`       -- store layout (``Messages`` / ``MessageStream`` / ``LogEntry``).
- :mod:`.interactions` -- host atoms + typed seams (``level_name`` / ``percent_format`` / ``fields_as_json``).

DX (Python-logging-shaped facades):
- :mod:`.logger`       -- ``Logger`` class + ``getLogger``.
- :mod:`.logger_root`  -- module-level root facade (``info`` / ``debug`` / ``log`` / ...).

std compat:
- :mod:`.std_compat`   -- ``from_std_logging`` rewrites ``nu.std.logging`` atoms into persistent writes.

Types:
- :mod:`.types`        -- level int constants + canonical name tuple.
"""

from __future__ import annotations

from .append import append
from .interactions import fields_as_json, level_name, percent_format
from .logger import Logger, getLogger
from .logger_root import critical, debug, error, info, log, warn, warning
from .query import FieldsFromJson, point, slice, tail
from .shapes import LogEntry, Messages, MessageStream
from .std_compat import from_std_logging
from .types import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    LEVELS,
    NOTSET,
    WARN,
    WARNING,
)


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
    "FieldsFromJson",
    "LogEntry",
    "Logger",
    "MessageStream",
    "Messages",
    "append",
    "critical",
    "debug",
    "error",
    "fields_as_json",
    "from_std_logging",
    "getLogger",
    "info",
    "level_name",
    "log",
    "percent_format",
    "point",
    "slice",
    "tail",
    "warn",
    "warning",
]
