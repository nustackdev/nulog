"""The browser log viewer -- one nudle Page, one Nu tree.

Shape:

- One :class:`ViewerPage` with heading, filters (stream picker + level + search),
  and the entry table.
- One :class:`ViewerIndex` (the browser entrypoint) with title, nav, and one
  page at ``/``.
- One :func:`build_ui` returning the reactive Nu tree: seed :class:`ViewState`,
  hydrate page chrome, then race a live tick against three ``ReactForever``
  handlers -- one per filter input.

Every read the tick does is a Nu tree: the table payload comes from a
``tail`` window (last ``TAIL_LIMIT`` entries of the selected stream) with
optional in-window level + substring predicates applied by
``FilterQuery``. The two ``@nu.host`` seams are :data:`FmtTs`
(microsecond -> ``HH:MM:SS.mmm``) and :data:`FmtFields` (JSON string ->
``k=v k=v``) -- pure formatting, no ctx.
"""

from __future__ import annotations

import datetime as _dt
import json

import nu

from .messages.shape import LEVELS, Messages


__all__ = [
    "DEFAULT_LEVEL",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "FmtFields",
    "FmtTs",
    "RowAsList",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
    "build_ui",
]


TABLE_COLUMNS: tuple[str, ...] = ("time", "level", "message", "fields")
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)
TICK_SECONDS = 1.0
TAIL_LIMIT = 200


# ---- viewer state --------------------------------------------------------


class ViewState(nu.Shape):
    """Server-side mirror of the viewer's current filter, read by the tick."""

    stream: nu.v.StrRef
    level: nu.v.StrRef       # "all" | "debug" | "info" | "warning" | "error" | "critical"
    search: nu.v.StrRef


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


# ---- viewer shapes -------------------------------------------------------


class ViewerPage(nu.nd.Page):
    """The viewer page: heading, filters, entries table."""

    heading = nu.nd.HeadingRef.slot()
    stream = nu.nd.SelectRef.slot()
    level = nu.nd.SelectRef.slot()
    search = nu.nd.InputRef.slot()
    table = nu.nd.TableRef.slot()


class ViewerIndex(nu.nd.Index):
    """Browser entrypoint: title, nav, the one page."""

    title = nu.nd.TitleRef.slot()
    nav = nu.nd.NavRef.slot()
    pages = nu.nd.Pages({"/": ViewerPage})


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
    """Newest-first entry-view stream for the current ViewState.stream.

    Reads only the last ``TAIL_LIMIT`` entries: ``len -> slice[len-N:len]
    -> reverse``. Safe at trillion-entry scale.
    """
    entries = Messages.streams[ViewState.stream].entries
    length = entries.len()
    start = nu.IfQuery(nu.GeQuery(length, TAIL_LIMIT), length - TAIL_LIMIT, nu.LiteralQuery(0))
    window = nu.GetItemQuery(entries, nu.SliceQuery(start, length, 1))
    return nu.IterQuery(nu.ReversedQuery(window))


def _matches_level() -> nu.Nu:
    """True iff the current entry's level matches ViewState.level (or level == "all")."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.level, DEFAULT_LEVEL),
        nu.EqQuery(_LEVEL, ViewState.level),
    )


def _matches_search() -> nu.Nu:
    """True iff the current entry's msg contains ViewState.search (or search == "")."""
    return nu.OrQuery(
        nu.EqQuery(ViewState.search, ""),
        nu.ContainsQuery(_MSG, ViewState.search),
    )


def _table_rows() -> nu.Nu:
    """Newest-first rows for the current ViewState filter, capped at TAIL_LIMIT."""
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
    return ViewerPage.table.store(_table_payload())


# ---- seed + hydrate + build ----------------------------------------------


def _seed_view(streams: tuple[str, ...]) -> nu.Nu:
    """Seed ViewState to defaults (first stream, level=all, no search)."""
    opening = streams[0] if streams else "app"
    return nu.v.Transaction(
        ViewState.stream.store(opening)
        >> ViewState.level.store(DEFAULT_LEVEL)
        >> ViewState.search.store(""),
    )


def _hydrate_chrome(streams: tuple[str, ...]) -> nu.Nu:
    """Seed the static page chrome: heading, filter options + values."""
    opening = streams[0] if streams else "app"
    stream_opts = list(streams) or [opening]
    return nu.v.Snapshot(
        ViewerPage.heading.store("nulog viewer", level=2)
        | ViewerPage.stream.store_options(stream_opts)
        | ViewerPage.stream.store(opening)
        | ViewerPage.level.store_options(list(LEVEL_OPTIONS))
        | ViewerPage.level.store(DEFAULT_LEVEL)
        | ViewerPage.search.store(""),
    )


def build_ui(streams: tuple[str, ...]) -> nu.Nu:
    """The viewer's reactive Nu tree.

    Args:
        streams: stream names to offer in the switcher (first is the opener).
    """
    tick = nu.ForeverDo(
        nu.v.Snapshot(_repaint()) >> nu.Delay(nu.LiteralQuery(TICK_SECONDS)),
    )
    on_stream = nu.ReactForever(
        ViewerPage.stream.changed(),
        nu.v.Transaction(ViewState.stream.store(ViewerPage.stream))
        >> nu.v.Snapshot(_repaint()),
    )
    on_level = nu.ReactForever(
        ViewerPage.level.changed(),
        nu.v.Transaction(ViewState.level.store(ViewerPage.level))
        >> nu.v.Snapshot(_repaint()),
    )
    on_search = nu.ReactForever(
        ViewerPage.search.changed(),
        nu.v.Transaction(ViewState.search.store(ViewerPage.search))
        >> nu.v.Snapshot(_repaint()),
    )

    return (
        ViewerIndex.title.store("nulog viewer")
        >> _seed_view(streams)
        >> _hydrate_chrome(streams)
        >> (tick | on_stream | on_level | on_search)
    )
