"""Log + metric writes as Nu Command trees.

Every function here returns a Nu tree. Nothing runs until evaluated. Wrap in
``nu.v.Transaction(...)`` (or drop into a bigger tree) to actually persist.

Shape of a log :func:`entry` write::

    SetCommand(us_attr, NowUs())              # capture eval-time microseconds
    >> SetCommand(key_attr, EncodeLogKey(us_attr))  # derive kh57 key from us
    >> shape[key_attr].store(DictForm.of(ts_us=us_attr, ...))

- The two ``SetCommand`` steps capture one ``us`` reading and derive the kh57
  key from it -- so the key and the stored ``ts_us`` slot can never drift.
- The store's dynamic ``[key_attr]`` addresses through the same scratch.
- Scratch attr names carry a per-call counter so composing two ``entry(...)``
  calls with ``|`` never collides on the same slot.

:func:`observe` is the same shape without the derivation step -- the kh57 key
IS the microsecond, minted once by :data:`NowUs` at eval time.

All the eval-time atoms (``NowUs``, ``NowSeconds``, ``EncodeLogKey``) are
``@nu.host(deterministic=False)`` -- the engine never folds them, and each
evaluation yields a fresh value.

Structured ``fields`` on log entries are JSON-encoded at eval time via the
``@nu.host`` :data:`FieldsAsJson` atom. Encoding runs inside the tree so a
Command carries a Ref chain, not a pre-computed constant.
"""

from __future__ import annotations

import itertools
import json
import time

import nu

from .shapes import Logs, Metrics


__all__ = [
    "EncodeLogKey",
    "FieldsAsJson",
    "NowSeconds",
    "NowUs",
    "debug",
    "entry",
    "error",
    "info",
    "log",
    "observe",
    "warn",
]


# Kh57 keys are 57 bits. Anchoring the epoch at 2020 leaves ~46 bits of
# microseconds for decades; shifting by 8 makes room for a sub-microsecond
# counter (256 slots per us) so same-us writes get distinct positions.
_EPOCH_US = 1_577_836_800_000_000  # 2020-01-01T00:00:00Z in us since Unix epoch

# Per-process counters. `_key_counter` is the sub-microsecond LSB folded into
# every kh57 key. `_call_counter` gives every construct-time write call a
# distinct scratch-attr name so parallel composition never collides.
_key_counter = itertools.count()
_call_counter = itertools.count()


# ---- @nu.host atoms -- pure value producers, eval-time -------------------


@nu.host(deterministic=False)
def NowUs() -> int:  # noqa: N802 -- atom class name is CamelCase
    """Absolute epoch microseconds at eval time -- the ``ts_us`` slot value."""
    return int(time.time() * 1_000_000)


@nu.host(deterministic=False)
def NowSeconds() -> float:  # noqa: N802
    """Absolute epoch seconds at eval time -- the metric point ``ts`` slot."""
    return time.time()


@nu.host(deterministic=False)
def EncodeLogKey(us: int) -> int:  # noqa: N802
    """Encode an absolute-microsecond ``us`` into a fresh kh57 log key.

    Formula: ``((us - _EPOCH_US) << 8) | (counter & 0xff)``. Chronological --
    keys sort by microsecond, then by the sub-us counter LSB (256 slots per
    us). Fits under ``2**57`` for decades. The counter is bumped at eval time
    so two writes at the same microsecond get distinct positions.
    """
    off = max(0, us - _EPOCH_US)
    return (off << 8) | (next(_key_counter) & 0xFF)


@nu.host
def FieldsAsJson(fields: dict) -> str:  # noqa: N802
    """Encode structured fields as a compact JSON string (empty on falsy)."""
    if not fields:
        return ""
    return json.dumps(fields, separators=(",", ":"), default=repr)


# ---- log entry Command builder -------------------------------------------


def entry(stream: str, level: str, msg: str, **fields: object) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``.

    The tree:
      1. ``SetCommand(us_attr, NowUs())`` -- capture a fresh eval-time ``us``.
      2. ``SetCommand(key_attr, EncodeLogKey(us_attr))`` -- derive the kh57 key
         from the same captured ``us`` so the key and the stored ``ts_us`` slot
         can never drift.
      3. ``Logs.streams[stream].entries[key_attr].store(DictForm.of(
             ts_us=us_attr, level=..., msg=..., fields=FieldsAsJson(...)))``.

    ``level`` and ``msg`` are Python str literals at construct time; structured
    ``**fields`` get captured now and JSON-encoded at eval time.
    """
    seq = next(_call_counter)
    us = nu.IntAttrRef(f"_nl_log_us_{seq}")
    key = nu.IntAttrRef(f"_nl_log_key_{seq}")
    rec = Logs.streams[stream].entries[key]
    return (
        nu.SetCommand(us, NowUs())
        >> nu.SetCommand(key, EncodeLogKey(us))
        >> rec.store(nu.DictForm.of(
            ts_us=us,
            level=nu.StrForm(level),
            msg=nu.StrForm(msg),
            fields=FieldsAsJson(nu.DictForm.of(**{k: nu.LiteralQuery(v) for k, v in fields.items()})),
        ))
    )


def log(stream: str, level: str, msg: str, **fields: object) -> nu.Nu:
    """Alias of :func:`entry` for the generic path."""
    return entry(stream, level, msg, **fields)


def debug(stream: str, msg: str, **fields: object) -> nu.Nu:
    """Build a ``debug`` append tree."""
    return entry(stream, "debug", msg, **fields)


def info(stream: str, msg: str, **fields: object) -> nu.Nu:
    """Build an ``info`` append tree."""
    return entry(stream, "info", msg, **fields)


def warn(stream: str, msg: str, **fields: object) -> nu.Nu:
    """Build a ``warn`` append tree."""
    return entry(stream, "warn", msg, **fields)


def error(stream: str, msg: str, **fields: object) -> nu.Nu:
    """Build an ``error`` append tree."""
    return entry(stream, "error", msg, **fields)


# ---- metric sample Command builder ---------------------------------------


def observe(name: str, value: float, *, ts: float | None = None) -> nu.Nu:
    """Build the Command tree that appends one point to metric ``name``.

    Args:
        name: series name (``"cpu_load"``, ``"http_latency_ms"``, ...).
        value: the sample.
        ts: optional wall-clock time (seconds since epoch). When ``None``, the
            key + ``ts`` slot are minted at eval time via :data:`NowUs` /
            :data:`NowSeconds`; pass an explicit ``ts`` for replay or batched
            observations. Same-microsecond writes collide (last-write-wins).
    """
    seq = next(_call_counter)
    key = nu.IntAttrRef(f"_nl_metric_key_{seq}")
    pt = Metrics.series[name].points[key]

    if ts is None:
        key_query: nu.Nu = NowUs()
        ts_query: nu.Nu = NowSeconds()
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
