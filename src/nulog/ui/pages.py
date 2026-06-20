"""The viewer's shapes -- the nudle Page, the Index, and server-side filter state.

A log viewer is a single page: a heading, a row of per-level count Stats, a
stream switcher plus a level filter plus a search box, and the entry table (the
centerpiece, newest-first). The :class:`LogViewer` page carries only display and
input Refs; all log reads run through the core :mod:`nulog.query` builders (see
:mod:`nulog.ui.app`). The :class:`LogIndex` is the browser entrypoint -- one
Index, one page at ``/``.

The current filter (which stream, which level, the search text) is mirrored into
a small server-side nv shape, :class:`ViewState`. The browser owns the inputs;
each change writes the picked value into ``ViewState`` (a single read on the
change event), and the repaint reads ``ViewState`` rather than round-tripping to
the tab every tick. This is the nuspace pattern (server-side scratch state the
reactive program reads), and it keeps the tail loop a pure store read. Nothing
about the viewer is written to the *log* store, so mounting a viewer never
mutates the logs.
"""

from __future__ import annotations

import nu
import nu_virtuals as nv
import nudle


__all__ = [
    "DEFAULT_LEVEL",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "LogIndex",
    "LogViewer",
    "ViewState",
]

# The table header, fixed: time / level / message / a compact fields cell.
TABLE_COLUMNS = ["time", "level", "message", "fields"]

# The level filter options: "all" plus the four severities. "all" means no level
# filter (fall back to the plain tail).
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS = [DEFAULT_LEVEL, "debug", "info", "warn", "error"]


class ViewState(nu.Shape):
    """Server-side mirror of the viewer's current filter, read by the repaint.

    Attributes:
        stream: the stream name currently shown (mirrors the stream Select).
        level: the level filter, ``"all"`` or one severity (mirrors the level
            Select).
        search: the message search text, ``""`` for no search (mirrors the
            search Input).
    """

    stream = nv.StrRef.slot()
    level = nv.StrRef.slot()
    search = nv.StrRef.slot()


class LogViewer(nudle.Page):
    """The one page: title, per-level counts, filters, and the entry table.

    The per-level counts are whole-stream totals, independent of the active level
    filter and search box (the table honors those filters, the counts do not).

    Attributes:
        heading: the page title heading.
        debug_count: the ``debug`` level count, shown as a Stat.
        info_count: the ``info`` level count, shown as a Stat.
        warn_count: the ``warn`` level count, shown as a Stat.
        error_count: the ``error`` level count, shown as a Stat.
        stream: the stream switcher (a Select over the store's stream names).
        level: the level filter (a Select over ``all`` plus the four severities).
        search: the message search box (an Input; substring match on ``msg``).
        table: the entry table, newest-first (the centerpiece).
    """

    heading = nudle.HeadingRef.slot()

    # per-level count stats (fed by query.count_by_level)
    debug_count = nudle.StatRef.slot()
    info_count = nudle.StatRef.slot()
    warn_count = nudle.StatRef.slot()
    error_count = nudle.StatRef.slot()

    # filters (browser-owned; their picks mirror into ViewState)
    stream = nudle.SelectRef.slot()
    level = nudle.SelectRef.slot()
    search = nudle.InputRef.slot()

    # the entry table -- newest-first
    table = nudle.TableRef.slot()


class LogIndex(nudle.Index):
    """The browser entrypoint: document title, nav, and the one viewer page.

    Attributes:
        title: the document title Ref.
        nav: the navigation Ref (history mirror; the viewer is single-page).
        pages: the route map, one page at ``/``.
    """

    title = nudle.TitleRef.slot()
    nav = nudle.NavRef.slot()
    pages = nudle.Pages({"/": LogViewer})
