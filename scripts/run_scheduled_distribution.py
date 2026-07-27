"""Run exactly one production distribution cycle with a cross-process lock."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

SUCCESS = 0
PRODUCTION_FAILURE = 1
LOCK_CONTENTION = 2
STARTUP_FAILURE = 3
DEFAULT_STALE_SECONDS = 24 * 60 * 60

class RunLock:
    def __init__(self, path, stale_seconds=DEFAULT_STALE_SECONDS):
        self.path = Path(path)
        self.stale_seconds = stale_seconds
        self.acquired = False

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "started_at": datetime.now(UTC).isoformat()})
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle: handle.write(payload)
            self.acquired = True
            return True
        except FileExistsError:
            try:
                age = datetime.now(UTC).timestamp() - self.path.stat().st_mtime
                if age > self.stale_seconds:
                    self.path.unlink()
                    return self.acquire()
            except (FileNotFoundError, OSError, ValueError):
                pass
            return False

    def release(self):
        if not self.acquired: return
        try: self.path.unlink()
        except FileNotFoundError: pass
        finally: self.acquired = False

def _lock_path():
    return os.environ.get("ALPHALAB_SCHEDULED_RUN_LOCK") or str(Path(__file__).resolve().parents[1] / "runtime" / "scheduled_distribution.lock")

def run_once(run_command=None, lock_path=None):
    print("scheduled-run started")
    lock = RunLock(lock_path or _lock_path())
    try:
        if not lock.acquire():
            print("scheduled-run lock-contention exit_code=2")
            return LOCK_CONTENTION
        print("scheduled-run lock-acquired")
        command = run_command or [sys.executable, "-m", "agents.ai_scout.agent", "--production-run", "--confirm-send"]
        result = subprocess.run(command, check=False)
        code = SUCCESS if result.returncode == 0 else PRODUCTION_FAILURE
        print(f"scheduled-run completed exit_code={code}")
        return code
    except (OSError, ValueError) as exc:
        print(f"scheduled-run failed category={type(exc).__name__} exit_code={STARTUP_FAILURE}")
        return STARTUP_FAILURE
    except Exception as exc:
        print(f"scheduled-run failed category={type(exc).__name__} exit_code={PRODUCTION_FAILURE}")
        return PRODUCTION_FAILURE
    finally:
        lock.release()

def main():
    try: return run_once()
    except Exception as exc:
        print(f"scheduled-run failed category={type(exc).__name__} exit_code={STARTUP_FAILURE}")
        return STARTUP_FAILURE

if __name__ == "__main__":
    raise SystemExit(main())
