# Nulog Examples

Every example is one `nu.With(...)` tree: shapes at the top of `nulog`, writes
composed under `Transaction`, reads composed under `Snapshot` and piped into
`nu.print`. No held ctx, no imperative Python.

- `basic.py` — write log lines across levels and two streams, then read them
  back (`tail`, `errors`, `count_by_level`, `search`) — all inside the same
  tree.

  ```sh
  .venv/bin/python examples/basic.py
  ```

- `metrics.py` — `observe(...)` a burst of samples on two named series, then
  read them back with `range_metric` (ordered slice) and `sample_metric` (kh57
  range reservoir sample).

  ```sh
  .venv/bin/python examples/metrics.py
  ```

- `viewer.py` — the browser log viewer. `nulog.store()` provides the store,
  `nulog.ui(streams, port=)` boots the nudle server, and the body seeds a
  handful of lines then loops one fresh line every ~1.5s. Needs the `[ui]`
  extra.

  ```sh
  pip install -e ".[ui]"                 # or: uv pip install -e ".[ui]"
  .venv/bin/python examples/viewer.py    # then open http://127.0.0.1:8080
  ```
