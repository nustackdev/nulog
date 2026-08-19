"""Value-only seams for the messages tab -- raw host atoms + typed wrappers.

- ``*Host`` -- bare :func:`nu.factory.host` atoms bound to the Python impl.
  Pure (``deterministic=True``) so the fold gate can constant-fold them
  when their inputs are literals.
- Typed snake_case wrappers (:func:`fmt_ts`, :func:`fmt_fields`) -- return
  a real :class:`~nu.forms.Str` Form so downstream expressions type-infer
  as strings instead of ``object``.
"""

from __future__ import annotations

import datetime as _dt
import json

import nu


__all__ = [
    "FmtFieldsHost",
    "FmtTsHost",
    "fmt_fields",
    "fmt_ts",
]


# --- raw impls (plain Python) ------------------------------------------------


def _fmt_ts_impl(ts_us: int) -> str:
    """Format a microsecond ts as ``HH:MM:SS.mmm`` (local clock)."""
    if not ts_us or ts_us <= 0:
        return ""
    moment = _dt.datetime.fromtimestamp(ts_us / 1_000_000)
    ms = (ts_us // 1000) % 1000
    return moment.strftime("%H:%M:%S.") + f"{ms:03d}"


def _fmt_fields_impl(fields: dict) -> str:
    """Compact ``k=v k=v`` rendering of a fields dict."""
    if not fields:
        return ""
    parts = []
    for k, v in fields.items():
        rendered = v if isinstance(v, str) else json.dumps(v, separators=(",", ":"))
        parts.append(f"{k}={rendered}")
    return " ".join(parts)


# --- raw host atoms (untyped -- factory calls) -------------------------------

FmtTsHost = nu.host(_fmt_ts_impl, name="FmtTs", deterministic=True)
FmtFieldsHost = nu.host(_fmt_fields_impl, name="FmtFields", deterministic=True)


# --- typed wrappers (public) -------------------------------------------------


def fmt_ts(ts_us: nu.IntArg) -> nu.Str:
    """Format a microsecond ts as ``HH:MM:SS.mmm`` (local clock)."""
    return nu.Str(FmtTsHost(ts_us))


def fmt_fields(fields: nu.DictArg[str, object]) -> nu.Str:
    """Compact ``k=v k=v`` rendering of a fields dict."""
    return nu.Str(FmtFieldsHost(fields))
