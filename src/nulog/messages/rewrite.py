"""Tree rewrites that swap ``nu.std.logging`` atoms for persistent ``nulog`` writes.

:func:`from_std_logging` walks a Nu tree and replaces every
``nu.std.logging.LogCommand`` with the equivalent persistent-write subtree
(an ``AppendCommand`` on the stream's ``entries`` list). App code stays
written in ``nu.std.logging`` style -- ``log.info(...)`` -- and the
*deployment* picks whether logs go to Python's ``logging`` (default -- no
rewrite) or persist into nulog (wrap the tree in :func:`from_std_logging`).

Usage::

    from nu.std import logging
    import nulog

    log = logging.getLogger("app")

    body = (
        log.info("started")
        >> log.warning("slow: %s ms", latency)
        >> log.error("failed", extra={"code": 500})
    )

    tree = nu.With(nulog.store(), body=nulog.from_std_logging(body))
    nu.run(tree)   # every log.* call now persists

Any level and logger *literal* is used at rewrite time; dynamic terms pass
straight through and normalize at eval time via ``LevelName``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from nu.core import LiteralQuery
from nu.std.logging import LogCommand
from nu.tree import map_nodes

from .log import _entry


if TYPE_CHECKING:
    import nu


__all__ = [
    "from_std_logging",
]


def _literal_value(term: nu.Nu) -> object | nu.Nu:
    """Return the Python value if ``term`` is a ``LiteralQuery``, else the term."""
    if isinstance(term, LiteralQuery):
        return term._payload.get("value")
    return term


def from_std_logging(tree: nu.Nu) -> nu.Nu:
    """Swap every ``nu.std.logging.LogCommand`` in ``tree`` for a persistent write.

    Bottom-up walk. Preserves everything that isn't a ``LogCommand``: other
    atoms, structure, sequence, retries, brackets. The rewritten site
    expects a ``nulog.store(...)`` bracket in scope on the Context.
    """

    def _rewrite(node: nu.Nu) -> nu.Nu:
        if not isinstance(node, LogCommand):
            return node

        # LogCommand children: [LOGGING, level, logger, msg, *args].
        # Slot 0 is the fabric ref -- dropped by the persistent path.
        children = cast("tuple[nu.Nu, ...]", node._children)
        level = _literal_value(children[1])
        stream = _literal_value(children[2])
        msg: object | nu.Nu = _literal_value(children[3])
        args: tuple[nu.Nu, ...] = tuple(children[4:])
        extra = cast("dict[str, object] | None", node._payload.get("extra")) or None

        return _entry(stream, level, msg, args, extra)

    return map_nodes(tree, _rewrite, order="bottom_up")
