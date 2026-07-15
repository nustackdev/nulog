"""Messages tab reads -- bounded slice + in-window predicates + table payload.

The tick calls :func:`_repaint`; that returns a Nu store command whose
payload is the current filtered slice of the selected stream. The slice
is either:

- ``tail`` -- ``entries[len - count : len]`` reversed (newest first)
- ``take`` -- ``entries[0 : count]`` in natural order (oldest first)

Both are ``len()`` + one ``SliceQuery`` descent, so read cost is O(count)
regardless of stream size -- billion-entry safe. Level and substring
predicates only see the ``count`` entries in the slice, never the full
stream, so they can't degrade to a scan.

Also home to the value-only ``@nu.host`` formatting seams -- :data:`FmtTs`,
:data:`FmtFields`, :data:`RowAsList` -- pure functions, no ctx.
"""

from __future__ import annotations

import datetime as _dt
import json

import nu

from ..messages.shape import Messages
from .shape import (
    DEFAULT_LEVEL,
    MAX_COUNT,
    MIN_COUNT,
    MODE_TAIL,
    TABLE_COLUMNS,
    MessagesBody,
    ViewState,
)


__all__ = [
    "FmtFields",
    "FmtTs",
    "RowAsList",
]


# ---- @nu.host: value-only formatting seams -------------------------------


@nu.host
def FmtTs(ts_us: int) -> str:  # noqa: N802
    """Format a microsecond ts as ``HH:MM:SS.mmm`` (local clock)."""
    if not ts_us or ts_us <= 0:
        return ""
    moment = _dt.datetime.fromtimestamp(ts_us / 1_000_000)
    ms = (ts_us // 1000) % 1000
    return moment.strftime("%H:%M:%S.") + f"{ms:03d}"


@nu.host
def FmtFields(raw: str) -> str:  # noqa: N802
    """Compact ``k=v k=v`` rendering of a JSON fields blob (empty on bad input)."""
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return ""
    if not isinstance(obj, dict):
        return ""
    parts = []
    for k, v in obj.items():
        rendered = v if isinstance(v, str) else json.dumps(v, separators=(",", ":"))
        parts.append(f"{k}={rendered}")
    return " ".join(parts)


@nu.host
def RowAsList(time: str, level: str, msg: str, fields: str) -> list:  # noqa: N802
    """A positional row for :class:`nu.ui.TableRef` (``set({rows: [...]})``)."""
    return [time, level, msg, fields]


# ---- @nu.host: safe-count clamp ------------------------------------------


@nu.host
def SafeCount(count: int) -> int:  # noqa: N802
    """Clamp count into ``[MIN_COUNT, MAX_COUNT]`` -- defense in depth.

    Browser side, ``NumberInputRef`` enforces the same range, but the
    server never trusts that. A stray zero, negative, or big number here
    would either return nothing or blow a repaint budget; clamp instead.
    """
    if not isinstance(count, int):
        count = int(count) if count else MIN_COUNT
    if count < MIN_COUNT:
        return MIN_COUNT
    if count > MAX_COUNT:
        return MAX_COUNT
    return count


@nu.host
def MaybeReverse(rows: list, reverse: bool) -> list:  # noqa: N802
    """Reverse the collected rows iff ``reverse`` is truthy.

    Order flip runs on the already-bounded ``list[row]``, not on any live
    entry stream: cost is O(count). We use this rather than a stream-side
    :class:`nu.ReversedQuery` inside an :class:`nu.IfQuery`, because
    IfQuery's branches must share a kind (scalar or stream) and this way
    we keep the whole pre-collect pipeline scalar-safe.
    """
    return list(reversed(rows)) if reverse else rows


# ---- table builders ------------------------------------------------------
#
# The bounded slice materializes into a list of shape views; we bind each
# entry view to _nl_item and apply the ViewState-driven predicates. Slice
# math never touches the full stream -- only ``len()`` + one descent.

_ITEM = nu.AnyAttrRef("_nl_item")
_TS_US = nu.GetItemQuery(_ITEM, "ts_us")
_LEVEL = nu.GetItemQuery(_ITEM, "level")
_MSG = nu.GetItemQuery(_ITEM, "msg")
_FIELDS_STR = nu.GetItemQuery(_ITEM, "fields")

_KEY = nu.AnyAttrRef("_nl_key")


def _window() -> nu.Nu:
    """Forward entry-view stream for the current ``ViewState`` slice.

    Cost: O(count). ``entries`` is a :class:`LogIndexedDictView` with no
    positional index, but its ``__keys__/`` sibling carries insertion order,
    so a reverse-cursor scan of the last N keys is trillion-entry safe --
    the scan itself stops at N and never walks past the tail.

        mode == "tail":  reverse-scan last `count` keys, flipped oldest-first
        mode == "take":  forward-scan first `count` keys

    Yields entry views in insertion (oldest-first) order. Tail's newest-first
    flip happens at the final row-list stage via :func:`MaybeReverse` --
    see :func:`_table_rows`.
    """
    entries = Messages.streams[ViewState.stream].entries
    count = SafeCount(ViewState.count)
    is_tail = nu.EqQuery(ViewState.mode, MODE_TAIL)

    # tail: reverse-scan first `count` (newest-first, bounded), then flip
    # to oldest-first so downstream keeps its insertion-order contract.
    tail_keys = nu.CollectQuery(
        nu.ReversedQuery(nu.std.itertools.islice(entries.reversed_keys(), count)),
    )
    # take: forward-scan first `count` (oldest-first, bounded).
    take_keys = nu.CollectQuery(nu.std.itertools.islice(entries.keys(), count))

    keys = nu.IfQuery(is_tail, tail_keys, take_keys)
    return nu.MapQuery(
        nu.IterQuery(keys),
        nu.GetItemQuery(entries, _KEY),
        key="_nl_key",
    )


def _matches_level() -> nu.Nu:
    """True iff the current entry's level matches ``ViewState.level`` (or ``"all"``)."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.level, DEFAULT_LEVEL),
        nu.EqQuery(_LEVEL, ViewState.level),
    )


def _matches_filter() -> nu.Nu:
    """True iff the current entry's msg contains ``ViewState.filter`` (or empty)."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.filter, ""),
        nu.ContainsQuery(_MSG, ViewState.filter),
    )


def _table_rows() -> nu.Nu:
    """Rows for the current slice, level + filter applied in-window.

    Tail mode gets its newest-first order by reversing the already-bounded
    row list here (see :func:`MaybeReverse`) rather than reversing the
    entry stream mid-pipeline.
    """
    kept = nu.FilterQuery(
        _window(),
        nu.AndQuery(_matches_level(), _matches_filter()),
        key="_nl_item",
    )
    row = RowAsList(FmtTs(_TS_US), _LEVEL, _MSG, FmtFields(_FIELDS_STR))
    ordered = nu.CollectQuery(nu.MapQuery(kept, row, key="_nl_item"))
    return MaybeReverse(ordered, nu.EqQuery(ViewState.mode, MODE_TAIL))


def _table_payload() -> nu.Nu:
    """The ``{columns, rows}`` dict payload the TableRef's ``.set(...)`` expects."""
    return nu.DictForm.of(columns=list(TABLE_COLUMNS), rows=_table_rows())


def _repaint() -> nu.Nu:
    """One repaint pass: refresh the messages table."""
    return MessagesBody.table.set(_table_payload())
