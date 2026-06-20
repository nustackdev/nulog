# Nulog Examples

- `basic.py` - open an in-memory store, write lines across levels and two streams
  ("app", "scraper") with structured fields, then read them back: `tail`,
  `errors`, `count_by_level`, and a `search`. Run it:

  ```sh
  .venv/bin/python examples/basic.py
  ```

- `viewer.py` - the browser log viewer (needs the `[ui]` extra). Opens an
  in-memory store, seeds lines across two streams and all four levels, runs a
  background generator that appends a fresh line every ~1.5s, and serves the
  viewer: a live newest-first table, a stream switcher, a level filter, a search
  box, and per-level count stats. Run it:

  ```sh
  pip install -e ".[ui]"              # or: uv pip install -e ".[ui]"
  .venv/bin/python examples/viewer.py # then open http://127.0.0.1:8080
  ```
