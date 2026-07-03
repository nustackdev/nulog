"""The write face: eager methods, compose mode, ids, stream isolation."""

import nu
import nu.virtuals as nv

from nulog import open_logs
from nulog.logger import new_entry_id


def test_append_and_read_back(app):
    app.info("started", port=8080, host="localhost")
    rows = app.tail(10)
    assert len(rows) == 1
    rec = rows[0]
    assert rec.level == "info"
    assert rec.msg == "started"
    assert rec.fields == {"port": 8080, "host": "localhost"}
    assert isinstance(rec.ts, int)
    assert rec.ts > 0


def test_no_fields_decodes_to_empty_dict(app):
    app.info("bare")
    assert app.tail(1)[0].fields == {}


def test_eager_info_level(app):
    app.info("m")
    assert app.tail(1)[0].level == "info"


def test_eager_warn_level(app):
    app.warn("m")
    assert app.tail(1)[0].level == "warn"


def test_eager_error_level(app):
    app.error("m")
    assert app.tail(1)[0].level == "error"


def test_eager_debug_level(app):
    app.debug("m")
    assert app.tail(1)[0].level == "debug"


def test_generic_log_method(app):
    app.log("warn", "via log", k=1)
    rec = app.tail(1)[0]
    assert rec.level == "warn"
    assert rec.fields == {"k": 1}


def test_eager_returns_entry_id(app):
    eid = app.info("m")
    assert isinstance(eid, str)
    assert eid == app.tail(1)[0].id


def test_entry_returns_nu_without_executing(app):
    cmd = app.entry("info", "deferred")
    assert isinstance(cmd, nu.Nu)
    # nothing ran: the stream is still empty
    assert app.tail(5) == []


def test_compose_log_plus_write_is_atomic(logs):
    class Account(nu.Shape):
        balance = nv.IntRef.slot()

    app = logs.stream("app")
    nu.run(
        nv.Transaction(Account.balance.store(100), app.entry("info", "debit", amount=5)),
        logs.ctx,
    )
    # both landed
    bal = nu.run(nv.Snapshot(nu.IntForm(Account.balance)), logs.ctx)[0]
    assert bal == 100
    rec = app.tail(1)[0]
    assert rec.msg == "debit"
    assert rec.fields == {"amount": 5}


def test_streams_are_isolated(logs):
    logs.stream("app").info("app line")
    logs.stream("scraper").info("scraper line")
    app_msgs = [r.msg for r in logs.stream("app").tail(10)]
    scr_msgs = [r.msg for r in logs.stream("scraper").tail(10)]
    assert app_msgs == ["app line"]
    assert scr_msgs == ["scraper line"]


def test_new_entry_id_is_sortable_and_padded():
    a = new_entry_id(1700000000000)
    b = new_entry_id(1700000000001)
    assert len(a) == len(b) == 19
    assert a < b  # later ts sorts after
    # same ms, the counter still orders them
    c = new_entry_id(1700000000000)
    assert c != a


def test_on_disk_store_persists(tmp_path):
    path = str(tmp_path / "store")
    with open_logs(path) as logs:
        logs.stream("app").info("persisted", n=1)
    with open_logs(path) as logs:
        rows = logs.stream("app").tail(10)
        assert [r.msg for r in rows] == ["persisted"]
        assert rows[0].fields == {"n": 1}
