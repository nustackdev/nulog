"""Compose the running viewer tree: seed state, hydrate chrome, wire reactives.

:func:`build_ui` is the entrypoint. It returns one Nu tree that:

- stores the page title + heading,
- seeds :class:`~.shape.ViewState` and :class:`~.shape.MetricsViewState`
  to sane defaults,
- hydrates the chrome for both tabs (option lists, radio choices, count
  bounds) -- labels themselves come from each :class:`~nu.ui.Field`
  subclass's ``label`` ClassVar,
- races a live tick (repaint every :data:`~.consts.TICK_SECONDS`) against
  reactives for each filter input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from . import consts, messages, metrics, shape


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["build_ui"]


def _seed_messages(streams: Sequence[str]) -> nu.Nu:
    """Seed the messages ViewState to defaults (first stream, tail mode)."""
    first_stream = streams[0] if streams else ""
    return (
        shape.ViewState.stream.set(first_stream)
        >> shape.ViewState.mode.set(consts.DEFAULT_MODE)
        >> shape.ViewState.count.set(consts.DEFAULT_COUNT)
        >> shape.ViewState.level.set(consts.DEFAULT_LEVEL)
        >> shape.ViewState.filter.set("")
    )


def _seed_metrics(series: Sequence[str]) -> nu.Nu:
    """Seed the metrics ViewState to defaults (first series, default window)."""
    first_series = series[0] if series else ""
    return shape.MetricsViewState.series.set(first_series) >> shape.MetricsViewState.window.set(
        consts.DEFAULT_WINDOW
    )


def _hydrate_messages_chrome(streams: Sequence[str]) -> nu.Nu:
    """Feed the stream picker its dynamic option list + initial selection.

    All other chrome (mode / count / level / filter) is pinned at slot time
    in ``.shape`` -- see ``ModeField.control``, ``CountField.control``, ...
    """
    first_stream = streams[0] if streams else ""
    stream_opts = list(streams) or [first_stream]
    return shape.StreamField.control.set_options(stream_opts) | shape.StreamField.control.set(
        first_stream
    )


def _hydrate_metrics_chrome(series: Sequence[str]) -> nu.Nu:
    """Feed the series picker its dynamic option list + initial selection.

    Window options + default are pinned at slot time on ``WindowField.control``.
    """
    first_series = series[0] if series else ""
    series_opts = list(series) or [first_series]
    return shape.SeriesField.control.set_options(series_opts) | shape.SeriesField.control.set(
        first_series
    )


def _messages_reactives() -> nu.Nu:
    """One ``ReactForever`` per messages-tab control -- mirror + repaint."""
    on_stream = nu.ReactForever(
        shape.StreamField.control.changed(),
        shape.ViewState.stream.set(shape.StreamField.control) >> messages.repaint(),
    )
    on_mode = nu.ReactForever(
        shape.ModeField.control.changed(),
        shape.ViewState.mode.set(shape.ModeField.control) >> messages.repaint(),
    )
    on_count = nu.ReactForever(
        shape.CountField.control.changed(),
        # NumberInputRef ships a float; cast to int for the slice math.
        shape.ViewState.count.set(nu.ToInt(shape.CountField.control)) >> messages.repaint(),
    )
    on_level = nu.ReactForever(
        shape.LevelField.control.changed(),
        shape.ViewState.level.set(shape.LevelField.control) >> messages.repaint(),
    )
    on_filter = nu.ReactForever(
        shape.FilterField.control.changed(),
        shape.ViewState.filter.set(shape.FilterField.control) >> messages.repaint(),
    )
    return on_stream | on_mode | on_count | on_level | on_filter


def _metrics_reactives() -> nu.Nu:
    """One ``ReactForever`` per metrics-tab control -- mirror + repaint."""
    on_series = nu.ReactForever(
        shape.SeriesField.control.changed(),
        shape.MetricsViewState.series.set(shape.SeriesField.control) >> metrics.repaint(),
    )
    on_window = nu.ReactForever(
        shape.WindowField.control.changed(),
        shape.MetricsViewState.window.set(shape.WindowField.control) >> metrics.repaint(),
    )
    return on_series | on_window


def build_ui(
    streams: Sequence[str],
    series: Sequence[str],
    *,
    title: str | None = "nulog viewer",
    messages_tab: bool = True,
    metrics_tab: bool = True,
    heading: str | None = "nulog viewer",
) -> nu.Nu:
    """The viewer's reactive Nu tree.

    Args:
        streams: message stream names for the messages tab switcher.
            Ignored when ``messages_tab=False``.
        series: metric series names for the metrics tab switcher.
            Ignored when ``metrics_tab=False``.
        title: browser-tab title to set on the enclosing Index. Set to
            ``None`` when embedding into a host Index that owns its own
            title (e.g. multi-page dashboards). Default matches the
            standalone :func:`nulog.ui` entrypoint.
        messages_tab: whether to wire the messages tab. Turn off when
            the enclosing store has no :class:`~nulog.messages.shapes.Messages`
            navigator (e.g. metrics-only dashboards).
        heading: page heading text. ``None`` skips writing the heading.
        metrics_tab: whether to wire the metrics tab. Turn off when the
            enclosing store has no :class:`~nulog.metrics.shapes.Metrics`
            navigator (e.g. log-only dashboards embedded in a larger app).

    The returned tree is scope-free wrt virtuals: reads and writes on
    :class:`~nulog.messages.shapes.Messages` and
    :class:`~nulog.metrics.shapes.Metrics` are emitted bare so the caller
    can pick the correct atomicity scope (typically via
    ``nu.kv.auto_flow_atomic(tree, scope=Messages)`` +
    ``scope=Metrics``). Standalone callers get this automatically via
    the outer ``nu.arun`` default sweep against a single untagged store.
    """
    if not (messages_tab or metrics_tab):
        msg = "build_ui: at least one of messages_tab / metrics_tab must be True"
        raise ValueError(msg)

    seeds: list[nu.Nu] = []
    chrome_parts: list[nu.Nu] = []
    tick_parts: list[nu.Nu] = []
    reactive_parts: list[nu.Nu] = []

    if heading is not None:
        chrome_parts.append(shape.ViewerPage.heading.set(heading, level=2))

    if messages_tab:
        seeds.append(_seed_messages(streams))
        chrome_parts.append(_hydrate_messages_chrome(streams))
        tick_parts.append(messages.repaint())
        reactive_parts.append(_messages_reactives())

    if metrics_tab:
        seeds.append(_seed_metrics(series))
        chrome_parts.append(_hydrate_metrics_chrome(series))
        tick_parts.append(metrics.repaint())
        reactive_parts.append(_metrics_reactives())

    seed_body = seeds[0]
    for s in seeds[1:]:
        seed_body = seed_body >> s

    chrome_body = chrome_parts[0]
    for c in chrome_parts[1:]:
        chrome_body = chrome_body | c

    tick_body = tick_parts[0]
    for t in tick_parts[1:]:
        tick_body = tick_body | t
    tick = nu.ForeverDo(tick_body >> nu.Delay(nu.Literal(consts.TICK_SECONDS)))

    reactives = tick
    for r in reactive_parts:
        reactives = reactives | r

    body: nu.Nu = seed_body >> chrome_body
    if title is not None:
        body = shape.ViewerIndex.title.set(title) >> body
    body = body >> reactives

    return nu.Provide(dict, {}, body)
