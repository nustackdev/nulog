"""Compose the running viewer tree: seed state, hydrate chrome, wire reactives.

:func:`build_ui` is the entrypoint. It returns one Nu tree that:

- stores the page title + heading,
- seeds :class:`~.shape.ViewState` and :class:`~.shape.MetricsViewState`
  to sane defaults,
- hydrates the chrome for both tabs (option lists, radio choices, count
  bounds) -- labels themselves come from each :class:`~nu.ui.FieldRef`
  subclass's ``label`` ClassVar,
- races a live tick (repaint every :data:`~.shape.TICK_SECONDS`) against
  reactives for each filter input.

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
    DEFAULT_COUNT,
    DEFAULT_LEVEL,
    DEFAULT_MODE,
    DEFAULT_WINDOW,
    LEVEL_OPTIONS,
    MAX_COUNT,
    MIN_COUNT,
    MODE_OPTIONS,
    TICK_SECONDS,
    WINDOW_OPTIONS,
    CountField,
    FilterField,
    LevelField,
    MetricsViewState,
    ModeField,
    SeriesField,
    StreamField,
    ViewerIndex,
    ViewerPage,
    ViewState,
    WindowField,
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
        >> ViewState.mode.store(DEFAULT_MODE)
        >> ViewState.count.store(DEFAULT_COUNT)
        >> ViewState.level.store(DEFAULT_LEVEL)
        >> ViewState.filter.store("")
        >> MetricsViewState.series.store(first_series)
        >> MetricsViewState.window.store(DEFAULT_WINDOW)
    )


def _hydrate_chrome(streams: Sequence[str], series: Sequence[str]) -> nu.Nu:
    """Seed the chrome for both tabs: options, initial values, count bounds."""
    first_stream = streams[0] if streams else ""
    first_series = series[0] if series else ""
    stream_opts = list(streams) or [first_stream]
    series_opts = list(series) or [first_series]
    return nu.v.Snapshot(
        ViewerPage.heading.set("nulog viewer", level=2)
        # messages tab
        | StreamField.control.set_options(stream_opts)
        | StreamField.control.set(first_stream)
        | ModeField.control.set_options(list(MODE_OPTIONS))
        | ModeField.control.set(DEFAULT_MODE)
        | CountField.control.set(
            DEFAULT_COUNT, min=MIN_COUNT, max=MAX_COUNT, step=10,
        )
        | LevelField.control.set_options(list(LEVEL_OPTIONS))
        | LevelField.control.set(DEFAULT_LEVEL)
        | FilterField.control.set("")
        # metrics tab
        | SeriesField.control.set_options(series_opts)
        | SeriesField.control.set(first_series)
        | WindowField.control.set_options(list(WINDOW_OPTIONS))
        | WindowField.control.set(DEFAULT_WINDOW),
    )


def _repaint_both() -> nu.Nu:
    """One snapshot that touches both the messages table and the metrics chart."""
    return nu.v.Snapshot(_messages._repaint() | _metrics._repaint())


def _messages_reactives() -> nu.Nu:
    """One ``ReactForever`` per messages-tab control -- mirror + repaint."""
    on_stream = nu.ReactForever(
        StreamField.control.changed(),
        ViewState.stream.store(StreamField.control)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_mode = nu.ReactForever(
        ModeField.control.changed(),
        ViewState.mode.store(ModeField.control)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_count = nu.ReactForever(
        CountField.control.changed(),
        # NumberInputRef ships a float; cast to int for the slice math.
        ViewState.count.store(nu.IntQuery(CountField.control))
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_level = nu.ReactForever(
        LevelField.control.changed(),
        ViewState.level.store(LevelField.control)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    on_filter = nu.ReactForever(
        FilterField.control.changed(),
        ViewState.filter.store(FilterField.control)
        >> nu.v.Snapshot(_messages._repaint()),
    )
    return on_stream | on_mode | on_count | on_level | on_filter


def _metrics_reactives() -> nu.Nu:
    """One ``ReactForever`` per metrics-tab control -- mirror + repaint."""
    on_series = nu.ReactForever(
        SeriesField.control.changed(),
        MetricsViewState.series.store(SeriesField.control)
        >> nu.v.Snapshot(_metrics._repaint()),
    )
    on_window = nu.ReactForever(
        WindowField.control.changed(),
        MetricsViewState.window.store(WindowField.control)
        >> nu.v.Snapshot(_metrics._repaint()),
    )
    return on_series | on_window


def build_ui(streams: Sequence[str], series: Sequence[str]) -> nu.Nu:
    """The viewer's reactive Nu tree.

    Args:
        streams: message stream names for the messages tab switcher.
        series: metric series names for the metrics tab switcher.
    """
    tick = nu.ForeverDo(
        _repaint_both() >> nu.Delay(nu.LiteralQuery(TICK_SECONDS)),
    )
    reactives = tick | _messages_reactives() | _metrics_reactives()

    return nu.Provide(
        dict,
        {},
        ViewerIndex.title.set("nulog viewer")
        >> _seed_view(streams, series)
        >> _hydrate_chrome(streams, series)
        >> reactives,
    )
