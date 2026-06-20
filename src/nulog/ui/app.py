"""The reactive program -- live tail, filters, and the stream switch, in Nu.

:func:`build_app` returns the Nu ``app`` flow for a viewer mounted over a
:class:`~nulog.presets.Logs` store. The flow is the examples' shape:

- a **live-tail repaint**: ``ForeverDo(Snapshot(<repaint>) >> AsyncSleep(~1s))``
  re-reads the current stream's entries through the core query builders every
  second and repaints the table plus the per-level count Stats, so new lines
  appear live.
- the **stream switcher**, the **level filter**, and the **search** box are
  browser-owned (the Select / Input Refs). Each ``changed`` mirrors the picked
  value into the server-side :class:`~nulog.ui.pages.ViewState` (one read on the
  change event) and repaints at once; the tick reads ``ViewState``, so it always
  reflects the current filter without round-tripping to the tab.

The reads run through :mod:`nulog.query` (``tail`` / ``by_level`` / ``search``)
and :meth:`~nulog.logger.Logger.count_by_level`: the viewer queries logs in the
same language the writer used. The id -> record decode is awkward to express
purely in the Table wire api (the Table takes a ``{columns, rows}`` payload, not
a record stream), so the row shaping runs in a ``nu.FuncCall`` that closes over
the ``Logs`` handle, reads ``ViewState`` and then the records through those core
helpers, and returns the payload the Table stores. The loop stays Nu-driven and
the reads stay under ``Snapshot``, matching the examples.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import nu
import nu_virtuals as nv
from nu import runtime
from nu.shapes.flows.react import ReactForever
from nu.stdlib.asyncio import AsyncSleep

from .pages import DEFAULT_LEVEL, LEVEL_OPTIONS, TABLE_COLUMNS, LogIndex, LogViewer, ViewState


if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..presets import Logs
    from ..records import LogRecord


__all__ = ["build_app", "default_stream"]

# How often the live tail re-reads the store and repaints (seconds).
TICK_SECONDS = 1.0

# How many lines the table shows at most.
TAIL_LIMIT = 200

_TREND = "flat"


def default_stream(streams: Sequence[str]) -> str:
    """The stream the viewer opens on (the first given, or ``"app"``)."""
    return streams[0] if streams else "app"


def _fmt_ts(ts_ms: int) -> str:
    """An entry timestamp as ``HH:MM:SS.mmm`` (local clock)."""
    import datetime as _dt

    if ts_ms <= 0:
        return ""
    moment = _dt.datetime.fromtimestamp(ts_ms / 1000.0)
    return moment.strftime("%H:%M:%S.") + f"{ts_ms % 1000:03d}"


def _fmt_fields(fields: dict[str, object]) -> str:
    """A compact ``k=v k=v`` rendering of an entry's structured fields."""
    if not fields:
        return ""
    parts = []
    for key, value in fields.items():
        rendered = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def _row(record: LogRecord) -> list[str]:
    """One table row from a record: time, level, message, compact fields."""
    return [_fmt_ts(record.ts), record.level, record.msg, _fmt_fields(record.fields)]


def _records(logs: Logs, stream: str, level: str, search: str) -> list[LogRecord]:
    """The records feeding the table, run through the core query builders.

    ``search`` wins when non-empty (substring on the message), then ``level``
    (when not ``"all"``), else the plain newest-first tail. Each path is a core
    :class:`~nulog.logger.Logger` read, so the viewer queries in the same
    language the writer logged with.
    """
    handle = logs.stream(stream or default_stream(()))
    text = (search or "").strip()
    if text:
        records = handle.search(text)
        if level and level != DEFAULT_LEVEL:
            records = [r for r in records if r.level == level]
        return records[:TAIL_LIMIT]
    if level and level != DEFAULT_LEVEL:
        return handle.by_level(level)[:TAIL_LIMIT]
    return handle.tail(TAIL_LIMIT)


def _read_slot(logs: Logs, slot: nu.Nu, default: str) -> str:
    """Read one ``ViewState`` str slot off the store's Context, with a fallback."""
    guarded = nu.If(slot.missing(), nu.Literal(default), nu.StrForm(slot))
    value = runtime.collect(nv.Snapshot(guarded), logs.ctx)[0]
    return str(value) if isinstance(value, str) and value else default


def _read_view(logs: Logs) -> tuple[str, str, str]:
    """Read the current filter (stream, level, search) off ``ViewState``.

    Reads the three nv slots on the store's Context, with empty-slot fallbacks.
    Closing over ``logs`` is what gives the repaint FuncCalls a Context to read
    from (a ``FuncCall`` target gets resolved values, not the ctx, so the handle
    carries it in).
    """
    stream = _read_slot(logs, ViewState.stream, default_stream(()))
    level = _read_slot(logs, ViewState.level, DEFAULT_LEVEL)
    search = _read_slot(logs, ViewState.search, "")
    return stream, level, search


def _make_build_table(logs: Logs) -> object:
    """A ``FuncCall`` target that shapes the table payload for the current filter.

    Reads ``ViewState`` then the matching records (both via the closed-over
    ``Logs`` handle) and returns the Table wire payload (``{"columns", "rows"}``);
    ``store`` writes it whole.
    """

    def build_table() -> dict[str, object]:
        stream, level, search = _read_view(logs)
        records = _records(logs, stream, level, search)
        return {"columns": list(TABLE_COLUMNS), "rows": [_row(r) for r in records]}

    return build_table


def _repaint(logs: Logs) -> nu.Nu:
    """One repaint pass: refresh the table and the per-level count Stats.

    The table reads the live ``ViewState`` filter inside its FuncCall, so a
    repaint always reflects the user's current selection. The per-level counts
    are whole-stream totals: ``count_by_level()`` runs once per repaint (one
    ``GroupBy`` pass yields all four levels) and the four Stat writes take literal
    values out of that single dict, so a tick does not re-scan the stream per
    level. The counts intentionally ignore the level filter and search box -- the
    table honors those, the counts show stream totals.
    """
    stream, _level, _search = _read_view(logs)
    by_level = logs.stream(stream).count_by_level()
    table = LogViewer.table.store(nu.FuncCall(_make_build_table(logs)))
    counts = (
        LogViewer.debug_count.store_value(str(by_level.get("debug", 0)))
        | LogViewer.info_count.store_value(str(by_level.get("info", 0)))
        | LogViewer.warn_count.store_value(str(by_level.get("warn", 0)))
        | LogViewer.error_count.store_value(str(by_level.get("error", 0)))
    )
    return table | counts


def _seed_view(streams: Sequence[str]) -> nu.Nu:
    """Seed ``ViewState`` to the opening stream, the ``all`` level, no search."""
    return nv.Transaction(
        ViewState.stream.store(default_stream(streams))
        >> ViewState.level.store(DEFAULT_LEVEL)
        >> ViewState.search.store(""),
    )


def _hydrate(streams: Sequence[str]) -> nu.Nu:
    """Seed the static page chrome: title, heading, stat labels, filter options."""
    opening = default_stream(streams)
    stream_opts = list(streams) or [opening]
    return nv.Snapshot(
        LogViewer.heading.store("nulog viewer", level=2)
        | LogViewer.debug_count.store_label("debug")
        | LogViewer.info_count.store_label("info")
        | LogViewer.warn_count.store_label("warn")
        | LogViewer.error_count.store_label("error")
        | LogViewer.debug_count.store_trend(_TREND)
        | LogViewer.info_count.store_trend(_TREND)
        | LogViewer.warn_count.store_trend(_TREND)
        | LogViewer.error_count.store_trend(_TREND)
        | LogViewer.stream.store_options(stream_opts)
        | LogViewer.stream.store(opening)
        | LogViewer.level.store_options(list(LEVEL_OPTIONS))
        | LogViewer.level.store(DEFAULT_LEVEL)
        | LogViewer.search.store(""),
    )


def build_app(logs: Logs, streams: Sequence[str]) -> nu.Nu:
    """Build the viewer's reactive ``app`` flow over a log store.

    Args:
        logs: the open :class:`~nulog.presets.Logs` handle the viewer reads.
        streams: the stream names to offer in the switcher (first is the opener).

    Returns:
        The Nu program: set the document title, seed ``ViewState`` + page chrome,
        then run the live-tail repaint alongside the filter react hooks (all in
        parallel). Hand it to :func:`nulog.ui.serve.serve_logs` or expose it as
        the module's ``app`` for ``nudle run``.
    """
    tail = nu.ForeverDo(nv.Snapshot(_repaint(logs)) >> AsyncSleep(TICK_SECONDS))

    # On each filter change: mirror the picked value into ViewState (one read of
    # the Ref), then repaint at once so the change shows without waiting a tick.
    on_stream = ReactForever(
        LogViewer.stream.changed(),
        nv.Transaction(ViewState.stream.store(LogViewer.stream)) >> nv.Snapshot(_repaint(logs)),
    )
    on_level = ReactForever(
        LogViewer.level.changed(),
        nv.Transaction(ViewState.level.store(LogViewer.level)) >> nv.Snapshot(_repaint(logs)),
    )
    on_search = ReactForever(
        LogViewer.search.changed(),
        nv.Transaction(ViewState.search.store(LogViewer.search)) >> nv.Snapshot(_repaint(logs)),
    )

    return (
        LogIndex.title.store("nulog viewer")
        >> _seed_view(streams)
        >> _hydrate(streams)
        >> (tail | on_stream | on_level | on_search)
    )
