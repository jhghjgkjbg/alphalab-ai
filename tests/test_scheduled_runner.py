import os
from pathlib import Path
from scripts import run_scheduled_distribution as runner

def test_success_and_cleanup(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda command, check=False: calls.append(command) or type("R", (), {"returncode": 0})())
    lock = tmp_path / "run.lock"
    assert runner.run_once(lock_path=lock) == runner.SUCCESS
    assert not lock.exists() and len(calls) == 1
    assert calls[0][-4:] == ["-m", "agents.ai_scout.agent", "--production-run", "--confirm-send"]

def test_contention_does_not_run_entrypoint(tmp_path, monkeypatch):
    lock = tmp_path / "run.lock"; lock.write_text("active", encoding="utf-8"); calls = []
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: calls.append(a))
    assert runner.run_once(lock_path=lock) == runner.LOCK_CONTENTION
    assert calls == []

def test_stale_lock_recovery_and_custom_path(tmp_path, monkeypatch):
    lock = tmp_path / "custom.lock"; lock.write_text("stale", encoding="utf-8")
    old = lock.stat().st_mtime - (runner.DEFAULT_STALE_SECONDS + 1)
    os.utime(lock, (old, old)); monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    assert runner.run_once(lock_path=lock) == runner.SUCCESS and not lock.exists()

def test_exception_cleans_lock(tmp_path, monkeypatch):
    lock = tmp_path / "run.lock"
    def fail(*args, **kwargs): raise RuntimeError("boom")
    monkeypatch.setattr(runner.subprocess, "run", fail)
    assert runner.run_once(lock_path=lock) == runner.PRODUCTION_FAILURE and not lock.exists()

def test_nonzero_maps_to_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 7})())
    assert runner.run_once(lock_path=tmp_path / "run.lock") == runner.PRODUCTION_FAILURE
