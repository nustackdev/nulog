"""Shared test fixtures.

The ``ctx`` fixture builds an in-memory RocksDB nulog store and binds a
:class:`nu.Context` on it -- same shape as nu's own tests. Each test does
its writes with ``nu.run(nu.v.Transaction(cmd), ctx)`` and its reads with
``nu.run(nu.v.Snapshot(read_atom), ctx)[0]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import pytest
from virtuals import Navigator


if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def ctx() -> Generator[nu.Context, None, None]:
    """A fresh in-memory Context bound to a nulog store (per-test isolation)."""
    with nu.v.presets.memory_storage() as storage:
        yield nu.Context().bind(Navigator, Navigator(storage))
