"""nulog metrics: observe a burst of samples, read them back range + sample.

One Nu tree. Writes fold as a Sequential of Commands; reads print inside
`Snapshot`. All the ordering, filtering, and range slicing is kh57 walking
under the hood.

Run::

    python examples/metrics.py
"""

from __future__ import annotations

import time

import nu

import nulog


_T0 = time.time()
_BEGIN = int(_T0 * 1_000_000)
_END = int((_T0 + 2.0) * 1_000_000)


def _burst() -> nu.Nu:
    """20 cpu_load + 20 http_latency samples spanning ~1 second, one Command tree."""
    cpu = nulog.observe("cpu_load", 0.30, ts=_T0)
    lat = nulog.observe("http_latency_ms", 12.0, ts=_T0)
    for i in range(1, 20):
        cpu = cpu >> nulog.observe("cpu_load", 0.30 + 0.02 * i, ts=_T0 + i * 0.05)
        lat = lat >> nulog.observe("http_latency_ms", 12.0 + i, ts=_T0 + i * 0.05)
    return cpu >> lat


tree = nu.With(nulog.store(),
    body=nu.v.Transaction(_burst())
    >> nu.v.Snapshot(nu.print(
        "== cpu_load: range ==",
        nulog.range_metric("cpu_load", _BEGIN, _END),
    ))
    >> nu.v.Snapshot(nu.print(
        "== cpu_load: sample(5) ==",
        nulog.sample_metric("cpu_load", 5, _BEGIN, _END),
    ))
    >> nu.v.Snapshot(nu.print(
        "== http_latency_ms: sample(5) ==",
        nulog.sample_metric("http_latency_ms", 5, _BEGIN, _END),
    )),
)


if __name__ == "__main__":
    nu.run(tree)
