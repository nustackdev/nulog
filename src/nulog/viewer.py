"""The browser log viewer -- one nudle Page, one Nu tree.

Shape (mirrors the wish_jar / counter examples):

- One :class:`ViewerPage` with heading, four per-level count Stats, a stream
  picker + level filter + search box, and the entry table.
- One :class:`ViewerIndex` (the browser entrypoint) with title, nav, and one
  page at ``/``.
- One :func:`build_ui` returning the reactive Nu tree: seed :class:`ViewState`,
  hydrate page chrome, then race a live tick against three ``ReactForever``
  handlers -- one per filter input.

Every read the tick does is a Nu tree: the table payload comes from
``CollectQuery(MapQuery(kh57 range, RowAsList(...), key="item"))``; the four
per-level counts come from :func:`nulog.reads.count_by_level`. The two
``@nu.host`` seams are :data:`FmtTs` (microsecond -> ``HH:MM:SS.mmm``) and
:data:`FmtFields` (JSON string -> ``k=v k=v``) -- pure formatting, no ctx.
"""

from __future__ import annotations

import datetime as _dt
import json

import nu

from .reads import (
    _KH57_MAX,
    _filter_pairs,
    _pairs,
    count_by_level,
)
from .shapes import LEVELS, ViewState


__all__ = [
    "DEFAULT_LEVEL",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "FmtFields",
    "FmtTs",
    "RowAsList",
    "ViewerIndex",
    "ViewerPage",
    "build_ui",
]


TABLE_COLUMNS: tuple[str, ...] = ("time", "level", "message", "fields")
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)
TICK_SECONDS = 1.0
TAIL_LIMIT = 200


# ---- @nu.host: value-only formatting seams -------------------------------


@nu.host
def FmtTs(ts_us: int) -> str:  # noqa: N802 -- atom class name is CamelCase
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
    """The one viewer page: heading, per-level counts, filters, entries table."""

    heading = nu.nd.HeadingRef.slot()

    debug_stat = nu.nd.StatRef.slot()
    info_stat = nu.nd.StatRef.slot()
    warning_stat = nu.nd.StatRef.slot()
    error_stat = nu.nd.StatRef.slot()
    critical_stat = nu.nd.StatRef.slot()

    stream = nu.nd.SelectRef.slot()
    level = nu.nd.SelectRef.slot()
    search = nu.nd.InputRef.slot()

    table = nu.nd.TableRef.slot()


class ViewerIndex(nu.nd.Index):
    """Browser entrypoint: title, nav, the one page."""

    title = nu.nd.TitleRef.slot()
    nav = nu.nd.NavRef.slot()
    pages = nu.nd.Pages({"/": ViewerPage})


# ---- table + counts builders ---------------------------------------------


_ITEM = nu.AnyAttrRef("_nl_item")
_VIEW = nu.GetItemQuery(_ITEM, 1)
_TS_US = nu.GetItemQuery(_VIEW, "ts_us")
_LEVEL = nu.GetItemQuery(_VIEW, "level")
_MSG = nu.GetItemQuery(_VIEW, "msg")
_FIELDS_STR = nu.GetItemQuery(_VIEW, "fields")


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
    pairs = _pairs(ViewState.stream, begin=0, end=_KH57_MAX)
    kept = _filter_pairs(pairs, nu.AndQuery(_matches_level(), _matches_search()))
    ordered = nu.CollectQuery(nu.ReversedQuery(kept))
    limited = nu.IterQuery(nu.GetItemQuery(ordered, nu.SliceQuery(0, TAIL_LIMIT, 1)))
    row = RowAsList(FmtTs(_TS_US), _LEVEL, _MSG, FmtFields(_FIELDS_STR))
    return nu.CollectQuery(nu.MapQuery(limited, row, key="_nl_item"))


def _table_payload() -> nu.Nu:
    """The `{columns, rows}` dict payload the TableRef's `.store(...)` expects."""
    return nu.DictForm.of(columns=list(TABLE_COLUMNS), rows=_table_rows())


def _repaint() -> nu.Nu:
    """One repaint pass: refresh the table and the five per-level count Stats."""
    counts = count_by_level(ViewState.stream)
    return (
        ViewerPage.table.store(_table_payload())
        | ViewerPage.debug_stat.store_value(nu.StrQuery(nu.GetItemQuery(counts, "debug")))
        | ViewerPage.info_stat.store_value(nu.StrQuery(nu.GetItemQuery(counts, "info")))
        | ViewerPage.warning_stat.store_value(nu.StrQuery(nu.GetItemQuery(counts, "warning")))
        | ViewerPage.error_stat.store_value(nu.StrQuery(nu.GetItemQuery(counts, "error")))
        | ViewerPage.critical_stat.store_value(nu.StrQuery(nu.GetItemQuery(counts, "critical")))
    )


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
    """Seed the static page chrome: heading, stat labels, filter options + values."""
    opening = streams[0] if streams else "app"
    stream_opts = list(streams) or [opening]
    return nu.v.Snapshot(
        ViewerPage.heading.store("nulog viewer", level=2)
        | ViewerPage.debug_stat.store_label("debug")
        | ViewerPage.info_stat.store_label("info")
        | ViewerPage.warning_stat.store_label("warning")
        | ViewerPage.error_stat.store_label("error")
        | ViewerPage.critical_stat.store_label("critical")
        | ViewerPage.debug_stat.store_trend("flat")
        | ViewerPage.info_stat.store_trend("flat")
        | ViewerPage.warning_stat.store_trend("flat")
        | ViewerPage.error_stat.store_trend("flat")
        | ViewerPage.critical_stat.store_trend("flat")
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
