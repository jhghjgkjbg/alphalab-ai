import json
from datetime import UTC, datetime
from core.analytics import DistributionEvent, DistributionEventStore
from core.growth import GrowthEventStore
from core.storage.database import SQLiteDatabase
from scripts import report_distribution_status as cli

def test_empty_human_and_json_are_read_only(tmp_path, capsys):
    db = SQLiteDatabase(tmp_path / "empty.db")
    report = cli.build_report(database=db); before = db.path.read_bytes(); assert report["attention_required"] == []
    assert db.path.read_bytes() == before
    assert cli._human(report).startswith("Distribution status")

def test_filters_attention_and_deterministic_order(tmp_path):
    db = SQLiteDatabase(tmp_path / "report.db"); store = DistributionEventStore(db); now = datetime(2026,1,1,tzinfo=UTC)
    def add(eid, typ, dest, article): store.append(DistributionEvent(eid, now, typ, article, dest, "failed" if typ.endswith("failed") else "pending", 1))
    add("z1", "delivery_attempted", "z", "a"); add("z2", "delivery_failed", "z", "a")
    add("a1", "delivery_attempted", "a", "b")
    report = cli.build_report(article_id="a", database=db)
    assert [x["destination"] for x in report["distribution"]["destinations"]] == ["z"]
    assert report["attention_required"][0]["reasons"] == ["failed"]
    assert cli.build_report(article_id="missing", database=db)["distribution"]["destinations"] == []

def test_json_schema_and_read_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_report", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("read")))
    assert cli.main(["--json"]) == 1
    assert "report failed" in capsys.readouterr().err
