"""Viewer reads -- tail-window scan + filter predicates + table payload.

The tick calls :func:`_repaint`; that returns a Nu store command whose
payload is the current filtered slice of the selected stream. Only the
last :data:`~.shape.TAIL_LIMIT` entries are read (``len -> slice ->
reverse``), so cost is O(TAIL_LIMIT) independent of stream size.

Also home to the value-only ``@nu.host`` formatting seams -- :data:`FmtTs`,
:data:`FmtFields`, :data:`RowAsList` -- pure functions, no ctx.
"""

from __future__ import annotations

import datetime as _dt
import json

import nu

from ..messages.shape import Messages
from .shape import DEFAULT_LEVEL, TABLE_COLUMNS, TAIL_LIMIT, ViewerPage, ViewState


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
    """A positional row for :class:`nu.nd.TableRef` (``store({rows: [...]})``)."""
    return [time, level, msg, fields]


# ---- table builders ------------------------------------------------------
#
# The tail slice is materialized into a list of shape views; we iterate it
# newest-first via ReversedQuery and bind each entry view to _nl_item, then
# apply the current ViewState-driven predicates.

_ITEM = nu.AnyAttrRef("_nl_item")
_TS_US = nu.GetItemQuery(_ITEM, "ts_us")
_LEVEL = nu.GetItemQuery(_ITEM, "level")
_MSG = nu.GetItemQuery(_ITEM, "msg")
_FIELDS_STR = nu.GetItemQuery(_ITEM, "fields")


def _tail_window() -> nu.Nu:
    """Newest-first entry-view stream for the current ``ViewState.stream``.

    Reads only the last ``TAIL_LIMIT`` entries: ``len -> slice[len-N:len]
    -> reverse``. Safe at trillion-entry scale.
    """
    entries = Messages.streams[ViewState.stream].entries
    length = entries.len()
    start = nu.IfQuery(nu.GeQuery(length, TAIL_LIMIT), length - TAIL_LIMIT, nu.LiteralQuery(0))
    window = nu.GetItemQuery(entries, nu.SliceQuery(start, length, 1))
    return nu.IterQuery(nu.ReversedQuery(window))


def _matches_level() -> nu.Nu:
    """True iff the current entry's level matches ``ViewState.level`` (or ``"all"``)."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.level, DEFAULT_LEVEL),
        nu.EqQuery(_LEVEL, ViewState.level),
    )


def _matches_search() -> nu.Nu:
    """True iff the current entry's msg contains ``ViewState.search`` (or empty)."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.search, ""),
        nu.ContainsQuery(_MSG, ViewState.search),
    )


def _table_rows() -> nu.Nu:
    """Newest-first rows for the current ViewState filter, capped at ``TAIL_LIMIT``."""
    kept = nu.FilterQuery(
        _tail_window(),
        nu.AndQuery(_matches_level(), _matches_search()),
        key="_nl_item",
    )
    row = RowAsList(FmtTs(_TS_US), _LEVEL, _MSG, FmtFields(_FIELDS_STR))
    return nu.CollectQuery(nu.MapQuery(kept, row, key="_nl_item"))


def _table_payload() -> nu.Nu:
    """The ``{columns, rows}`` dict payload the TableRef's ``.store(...)`` expects."""
    return nu.DictForm.of(columns=list(TABLE_COLUMNS), rows=_table_rows())


def _repaint() -> nu.Nu:
    """One repaint pass: refresh the table."""
    return ViewerPage.table.set(_table_payload())
