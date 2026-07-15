"""Compose the running viewer tree: seed state, hydrate chrome, wire reactives.

:func:`build_ui` is the entrypoint. It returns one Nu tree that:

- stores the page title + heading,
- seeds :class:`~.shape.ViewState` and :class:`~.shape.MetricsViewState`
  to sane defaults,
- hydrates the static chrome for both tabs (pickers + options),
- races a live tick (repaint every :data:`~.shape.TICK_SECONDS`) against
  reactives for each filter input (stream / level / search / series / window).

Each tick repaints both the messages table and the metrics chart. The
whole tree runs under a ``nu.Provide(dict, {}, ...)`` bracket that carries
the in-memory fabric for the view states -- log persistence stays under
the enclosing :mod:`nu.v` store bracket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from . import messages as _messages
from . import metrics as _metrics
from .shape import (
    DEFAULT_LEVEL,
    DEFAULT_WINDOW,
    LEVEL_OPTIONS,
    TICK_SECONDS,
    WINDOW_OPTIONS,
    MessagesBody,
    MetricsBody,
    MetricsViewState,
    ViewerIndex,
    ViewerPage,
    ViewState,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["build_ui"]


def _seed_view(streams: Sequence[str], series: Sequence[str]) -> nu.Nu:
    """Seed both ViewStates to defaults (first stream / first series)."""
    first_stream = streams[0] if streams else ""
    first_series = series[0] if series else ""
    return (
        ViewState.stream.store(first_stream)
        >> ViewState.level.store(DEFAULT_LEVEL)
        >> ViewState.search.store("")
        >> MetricsViewState.series.store(first_series)
        >> MetricsViewState.window.store(DEFAULT_WINDOW)
    )


def _hydrate_chrome(streams: Sequence[str], series: Sequence[str]) -> nu.Nu:
    """Seed the static page chrome: heading, tab pickers, options + values."""
    first_stream = streams[0] if streams else ""
    first_series = series[0] if series else ""
    stream_opts = list(streams) or [first_stream]
    series_opts = list(series) or [first_series]
    return nu.v.Snapshot(
        ViewerPage.heading.set("nulog viewer", level=2)
        # messages tab
        | MessagesBody.stream.set_options(stream_opts)
        | MessagesBody.stream.set(first_stream)
        | MessagesBody.level.set_options(list(LEVEL_OPTIONS))
        | MessagesBody.level.set(DEFAULT_LEVEL)
        | MessagesBody.search.set("")
        # metrics tab
        | MetricsBody.series.set_options(series_opts)
        | MetricsBody.series.set(first_series)
        | MetricsBody.window.set_options(list(WINDOW_OPTIONS))
        | MetricsBody.window.set(DEFAULT_WINDOW),
    )


def _repaint_both() -> nu.Nu:
    """One snapshot that touches both the messages table and the metrics chart."""
    return nu.v.Snapshot(_messages._repaint() | _metrics._repaint())


def build_ui(streams: Sequence[str], series: Sequence[str]) -> nu.Nu:
    """The viewer's reactive Nu tree.

    Args:
        streams: message stream names for the messages tab switcher.
        series: metric series names for the metrics tab switcher.
    """
    tick = nu.ForeverDo(
        _repaint_both() >> nu.Delay(nu.LiteralQuery(TICK_SECONDS)),
    )
    # messages reactives
    on_stream = nu.ReactForever(
        MessagesBody.stream.changed(),
        ViewState.stream.store(MessagesBody.stream)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_level = nu.ReactForever(
        MessagesBody.level.changed(),
        ViewState.level.store(MessagesBody.level)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_search = nu.ReactForever(
        MessagesBody.search.changed(),
        ViewState.search.store(MessagesBody.search)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    # metrics reactives
    on_series = nu.ReactForever(
        MetricsBody.series.changed(),
        MetricsViewState.series.store(MetricsBody.series)
        >> nu.v.Snapshot(_metrics._repaint()),
    )
    on_window = nu.ReactForever(
        MetricsBody.window.changed(),
        MetricsViewState.window.store(MetricsBody.window)
        >> nu.v.Snapshot(_metrics._repaint()),
    )

    reactives = tick | on_stream | on_level | on_search | on_series | on_window

    return nu.Provide(
        dict,
        {},
        ViewerIndex.title.set("nulog viewer")
        >> _seed_view(streams, series)
        >> _hydrate_chrome(streams, series)
        >> reactives,
    )
