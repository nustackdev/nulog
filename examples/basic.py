"""nulog basics: write lines across levels and streams, then read them back.

Run it:

    .venv/bin/python examples/basic.py

Uses an in-memory store (open_logs() with no path), so it leaves nothing behind.
"""

from nulog import open_logs


def main():
    with open_logs() as logs:
        app = logs.stream("app")
        scraper = logs.stream("scraper")

        # write a handful of lines across levels, with structured fields
        app.info("server started", port=8080, env="dev")
        app.debug("config loaded", source="env")
        app.warn("cache miss", key="user:42")
        app.error("request failed", path="/checkout", code=500)
        app.info("request ok", path="/", ms=12)

        scraper.info("scrape started", target="example.com")
        scraper.error("blocked", status=429)

        print("== app: tail(3) ==")
        for r in app.tail(3):
            print(f"  [{r.level:5}] {r.msg}  {r.fields}")

        print("\n== app: errors only ==")
        for r in app.errors():
            print(f"  [{r.level:5}] {r.msg}  {r.fields}")

        print("\n== app: count by level ==")
        for level, n in app.count_by_level().items():
            print(f"  {level:5} {n}")

        print("\n== app: search 'request' ==")
        for r in app.search("request"):
            print(f"  [{r.level:5}] {r.msg}  {r.fields}")

        print("\n== scraper: tail(5) (separate stream) ==")
        for r in scraper.tail(5):
            print(f"  [{r.level:5}] {r.msg}  {r.fields}")


if __name__ == "__main__":
    main()
