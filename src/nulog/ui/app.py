"""Compose the running viewer tree: seed state, hydrate chrome, wire reactives.

:func:`build_ui` is the entrypoint. It returns one Nu tree that:

- stores the page title,
- seeds :class:`~.shape.ViewState` (in-memory filter mirror) to sane defaults,
- hydrates the static page chrome (heading, filter options and values),
- races a live tick (repaint every :data:`~.shape.TICK_SECONDS`) against
  three ``ReactForever`` handlers -- one per filter input.

The whole tree runs under a ``nu.Provide(dict, {}, ...)`` bracket that
carries the in-memory fabric for :class:`ViewState`. Log data still comes
from the enclosing :mod:`nu.v` store bracket -- viewer state and log
persistence share nothing.
"""

from __future__ import annotations

import nu

from .query import _repaint
from .shape import (
    DEFAULT_LEVEL,
    LEVEL_OPTIONS,
    TICK_SECONDS,
    ViewerIndex,
    ViewerPage,
    ViewState,
)


__all__ = ["build_ui"]


def _seed_view(streams: tuple[str, ...]) -> nu.Nu:
    """Seed ViewState to defaults (first stream, level=all, no search)."""
    opening = streams[0] if streams else "app"
    return (
        ViewState.stream.store(opening)
        >> ViewState.level.store(DEFAULT_LEVEL)
        >> ViewState.search.store("")
    )


def _hydrate_chrome(streams: tuple[str, ...]) -> nu.Nu:
    """Seed the static page chrome: heading, filter options + values."""
    opening = streams[0] if streams else "app"
    stream_opts = list(streams) or [opening]
    return nu.v.Snapshot(
        ViewerPage.heading.set("nulog viewer", level=2)
        | ViewerPage.stream.set_options(stream_opts)
        | ViewerPage.stream.set(opening)
        | ViewerPage.level.set_options(list(LEVEL_OPTIONS))
        | ViewerPage.level.set(DEFAULT_LEVEL)
        | ViewerPage.search.set(""),
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
        ViewState.stream.store(ViewerPage.stream) >> nu.v.Snapshot(_repaint()),
    )
    on_level = nu.ReactForever(
        ViewerPage.level.changed(),
        ViewState.level.store(ViewerPage.level) >> nu.v.Snapshot(_repaint()),
    )
    on_search = nu.ReactForever(
        ViewerPage.search.changed(),
        ViewState.search.store(ViewerPage.search) >> nu.v.Snapshot(_repaint()),
    )

    return nu.Provide(
        dict,
        {},
        ViewerIndex.title.set("nulog viewer")
        >> _seed_view(streams)
        >> _hydrate_chrome(streams)
        >> (tick | on_stream | on_level | on_search),
    )
