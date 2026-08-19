"""Messages tab reads -- bounded slice + in-window predicates + table payload.

The tick calls :func:`repaint`; that returns a Nu store command whose
payload is the current filtered slice of the selected stream. The slice
is either:

- ``tail`` -- last ``count`` keys, newest first
- ``take`` -- first ``count`` keys, oldest first

Both are one bounded key scan (reverse cursor for tail, forward for take),
so read cost is O(count) regardless of stream size -- billion-entry safe.
Level and substring predicates only see the ``count`` entries in the
slice, never the full stream.
"""

from __future__ import annotations

import nu

from nulog.messages import Messages

from . import consts, shape
from .interactions import fmt_fields, fmt_ts


def repaint() -> nu.Nu:
    """One repaint pass: refresh the messages table.

    No-ops (writes an empty table) when no stream is selected -- an empty
    stream key would break the binary codec's prefix encoding.
    """
    empty = shape.MessagesBody.table.set(
        nu.Dict.of(columns=list(consts.TABLE_COLUMNS), rows=[]),
    )
    return nu.IfDo(nu.Eq(shape.ViewState.stream, ""), empty, _repaint_body())


def _repaint_body() -> nu.Nu:
    """The real read-and-write pass. Assumes ``ViewState.stream`` is non-empty."""
    entries = Messages.streams[shape.ViewState.stream].entries

    # Clamp count into [MIN_COUNT, MAX_COUNT] -- browser side already does
    # this, but the server never trusts a stray zero / big number.
    raw = shape.ViewState.count
    count = nu.If(
        raw < consts.MIN_COUNT,
        consts.MIN_COUNT,
        nu.If(raw > consts.MAX_COUNT, consts.MAX_COUNT, raw),
    )

    # Bounded key scan: tail = reverse cursor (newest first),
    # take = forward cursor (oldest first). Both stop at `count`.
    keys = nu.If(
        nu.Eq(shape.ViewState.mode, consts.MODE_TAIL),
        nu.Collect(nu.std.itertools.islice(entries.reversed_keys(), count)),
        nu.Collect(nu.std.itertools.islice(entries.keys(), count)),
    )

    item = nu.AnyAttrRef("_nl_item")
    entry_stream = nu.Map(
        nu.Iter(keys),
        nu.GetItem(entries, nu.AnyAttrRef("_nl_key")),
        key="_nl_key",
    )
    kept = nu.Filter(
        entry_stream,
        nu.And(
            nu.Or(
                nu.Eq(shape.ViewState.level, consts.DEFAULT_LEVEL),
                nu.Eq(nu.GetItem(item, "level"), shape.ViewState.level),
            ),
            nu.Or(
                nu.Eq(shape.ViewState.filter, ""),
                nu.Contains(nu.GetItem(item, "msg"), shape.ViewState.filter),
            ),
        ),
        key="_nl_item",
    )
    rows = nu.Collect(
        nu.Map(
            kept,
            nu.List.of(
                fmt_ts(nu.GetItem(item, "ts_us")),
                nu.GetItem(item, "level"),
                nu.GetItem(item, "msg"),
                fmt_fields(nu.GetItem(item, "fields")),
            ),
            key="_nl_item",
        ),
    )
    return shape.MessagesBody.table.set(
        nu.Dict.of(columns=list(consts.TABLE_COLUMNS), rows=rows),
    )
