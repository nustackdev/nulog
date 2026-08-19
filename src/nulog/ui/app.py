"""Compose the running viewer tree: seed state, hydrate chrome, wire reactives.

:func:`build_ui` is the entrypoint. It returns one Nu tree that:

- stores the page title + heading,
- seeds :class:`~.shape.ViewState` and :class:`~.shape.MetricsViewState`
  to sane defaults,
- refreshes stream / series picker options every tick from the actual
  ``Messages.streams`` / ``Metrics.series`` keys, so new streams / series
  show up in the dropdowns without a restart,
- races a live tick (repaint every :data:`~.consts.TICK_SECONDS`) against
  reactives for each filter input.
"""

from __future__ import annotations

import nu

from nulog.messages import Messages
from nulog.metrics import Metrics

from . import consts, messages, metrics, shape


__all__ = ["build_ui"]


def _seed_messages() -> nu.Nu:
    """Seed the messages ViewState to defaults (empty stream, tail mode)."""
    return (
        shape.ViewState.stream.set("")
        >> shape.ViewState.mode.set(consts.DEFAULT_MODE)
        >> shape.ViewState.count.set(consts.DEFAULT_COUNT)
        >> shape.ViewState.level.set(consts.DEFAULT_LEVEL)
        >> shape.ViewState.filter.set("")
    )


def _seed_metrics() -> nu.Nu:
    """Seed the metrics ViewState to defaults (empty series, default window)."""
    return shape.MetricsViewState.series.set("") >> shape.MetricsViewState.window.set(
        consts.DEFAULT_WINDOW,
    )


def _as_options(keys: nu.Nu) -> nu.Nu:
    """Map a Nu-side stream of key strings into ``[{value, label}, ...]``."""
    key = nu.AnyAttrRef("_nl_opt")
    return nu.Collect(
        nu.Map(
            nu.Iter(keys),
            nu.Dict.of(value=key, label=key),
            key="_nl_opt",
        ),
    )


def _auto_pick_first(
    keys: nu.Nu,
    state_ref: nu.Nu,
    control_ref: nu.Nu,
) -> nu.Nu:
    """Seed ``state_ref`` + mirror to ``control_ref`` with the first key.

    Fires only when ``state_ref`` is still empty (first open) and the store
    actually has at least one key -- so once the user picks something we
    never overwrite it, and empty stores stay empty instead of blowing up.
    """
    collected = nu.Collect(nu.Iter(keys))
    first = nu.GetItem(collected, 0)
    return nu.IfDo(
        nu.And(nu.Eq(state_ref, ""), nu.Gt(nu.Len(collected), 0)),
        state_ref.set(first) >> control_ref.set(first),
    )


def _messages_tick() -> nu.Nu:
    """One messages-tab tick: refresh stream picker options, auto-pick first, repaint."""
    keys = Messages.streams.keys()
    return (
        shape.StreamField.control.set_options(_as_options(keys))
        | _auto_pick_first(keys, shape.ViewState.stream, shape.StreamField.control)
        | messages.repaint()
    )


def _metrics_tick() -> nu.Nu:
    """One metrics-tab tick: refresh series picker options, auto-pick first, repaint."""
    keys = Metrics.series.keys()
    return (
        shape.SeriesField.control.set_options(_as_options(keys))
        | _auto_pick_first(keys, shape.MetricsViewState.series, shape.SeriesField.control)
        | metrics.repaint()
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
    *,
    title: str | None = "nulog viewer",
    messages_page: bool = True,
    metrics_page: bool = True,
) -> nu.Nu:
    """The viewer's reactive Nu tree.

    Args:
        title: browser-tab title to set on the enclosing Index. Set to
            ``None`` when embedding into a host Index that owns its own
            title (e.g. multi-page dashboards). Default matches the
            standalone :func:`nulog.ui` entrypoint.
        messages_page: whether to wire the messages page. Turn off when
            the enclosing store has no :class:`~nulog.messages.shapes.Messages`
            navigator (e.g. metrics-only dashboards).
        metrics_page: whether to wire the metrics page. Turn off when the
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
    if not (messages_page or metrics_page):
        msg = "build_ui: at least one of messages_page / metrics_page must be True"
        raise ValueError(msg)

    seeds: list[nu.Nu] = []
    tick_parts: list[nu.Nu] = []
    reactive_parts: list[nu.Nu] = []

    if messages_page:
        seeds.append(_seed_messages())
        tick_parts.append(_messages_tick())
        reactive_parts.append(_messages_reactives())

    if metrics_page:
        seeds.append(_seed_metrics())
        tick_parts.append(_metrics_tick())
        reactive_parts.append(_metrics_reactives())

    seed_body = seeds[0]
    for s in seeds[1:]:
        seed_body = seed_body >> s

    tick_body = tick_parts[0]
    for t in tick_parts[1:]:
        tick_body = tick_body | t
    tick = nu.ForeverDo(tick_body >> nu.Delay(nu.Literal(consts.TICK_SECONDS)))

    reactives = tick
    for r in reactive_parts:
        reactives = reactives | r

    body: nu.Nu = seed_body
    if title is not None:
        body = shape.ViewerIndex.title.set(title) >> body
    body = body >> reactives

    return nu.Provide(dict, {}, body)
