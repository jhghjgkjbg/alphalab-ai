import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class XTokenState:
    access_token: str
    refresh_token: str
    expires_at: object = None

class XTokenStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return None
        try:
            if hasattr(os, "stat") and os.name != "nt" and (self.path.stat().st_mode & 0o077):
                raise PermissionError("x token state permissions are unsafe")
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data.get("access_token") or not data.get("refresh_token"):
                raise ValueError("invalid x token state")
            return XTokenState(str(data["access_token"]), str(data["refresh_token"]), data.get("expires_at"))
        except PermissionError:
            raise RuntimeError("x_token_state_permission_error")
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError("x_token_state_invalid")

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"access_token": state.access_token, "refresh_token": state.refresh_token, "expires_at": state.expires_at}
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        lock_fd = None
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            raise RuntimeError("x_token_state_lock_failed") from exc
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, separators=(",", ":"))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, self.path)
            try: os.chmod(self.path, 0o600)
            except OSError: pass
        except Exception:
            try: os.unlink(tmp)
            except OSError: pass
            raise RuntimeError("x_token_state_write_failed")
        finally:
            try:
                if lock_fd is not None: os.close(lock_fd)
                os.unlink(lock_path)
            except OSError: pass
