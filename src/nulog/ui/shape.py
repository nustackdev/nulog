"""Viewer state + display shapes -- what the browser sees.

:class:`ViewState` is the server-side mirror of the current filter set
(stream, level, search). :class:`ViewerPage` and :class:`ViewerIndex`
are the nudle Page / Index scaffolds -- heading, filter slots, entries
table. Constants at the top pin the table layout and the tick pace.
"""

from __future__ import annotations

import nu

from ..messages.shape import LEVELS


__all__ = [
    "DEFAULT_LEVEL",
    "LEVEL_OPTIONS",
    "TABLE_COLUMNS",
    "TAIL_LIMIT",
    "TICK_SECONDS",
    "ViewState",
    "ViewerIndex",
    "ViewerPage",
]


TABLE_COLUMNS: tuple[str, ...] = ("time", "level", "message", "fields")
DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)
TICK_SECONDS = 1.0
TAIL_LIMIT = 200


class ViewState(nu.Shape):
    """Server-side mirror of the viewer's current filter, read by the tick.

    Lives in :mod:`nu.m` (dict-backed, process-local) rather than :mod:`nu.v`
    -- filter state is transient UI, not something to persist to the log DB.
    """

    stream: nu.m.StrRef
    level: nu.m.StrRef       # "all" | "debug" | "info" | "warning" | "error" | "critical"
    search: nu.m.StrRef


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
