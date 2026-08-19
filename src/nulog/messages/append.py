"""The write-tree primitive -- :func:`append` one entry to a stream.

Every logger method, every ``std_compat`` rewrite, every direct write in
user code funnels through here. One call builds one Command tree that,
when driven under a :class:`~.shapes.Messages` navigator, appends one
:class:`~.shapes.LogEntry` to ``Messages.streams[stream].entries``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .interactions import level_name, percent_format
from .shapes import Messages


if TYPE_CHECKING:
    from nu.lang import IntArg, StrArg


__all__ = ["append"]


def append(
    stream: StrArg,
    level: IntArg | StrArg,
    msg: StrArg,
    args: tuple[object, ...],
    extra: dict[str, object] | None,
) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``."""
    return Messages.streams[stream].entries.set_item(
        nu.std.uuid.uuid4().hex(),
        nu.Dict.of(
            ts_us=nu.std.time.time_ns() // 1000,
            level=level_name(level),
            msg=percent_format(msg, *args),
            fields=extra or {},
        ),
    )
