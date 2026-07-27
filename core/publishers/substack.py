import json, os, shutil, tempfile
from datetime import datetime, UTC
from pathlib import Path
from types import SimpleNamespace

class SubstackDraftPublisher:
    def __init__(self, outbox_directory): self.root = Path(outbox_directory)
    async def publish(self, view):
        if view.audience not in {"everyone", "free", "paid"}: return SimpleNamespace(success=False, error="substack_invalid_audience")
        final = self.root / view.article_id
        metadata = {"article_id": view.article_id, "destination":"substack", "title":view.title, "subtitle":view.subtitle, "canonical_url":view.canonical_url, "tracked_url":view.tracked_url, "audience":view.audience, "publication_url":view.metadata.get("publication_url", ""), "created_at":datetime.now(UTC).isoformat(), "format_version":1}
        try:
            if final.exists():
                meta_path=final / "metadata.json"
                if not meta_path.exists(): return SimpleNamespace(success=False,error="substack_invalid_existing_draft")
                existing=json.loads(meta_path.read_text(encoding="utf-8"))
                if existing.get("article_id") == view.article_id and existing.get("canonical_url") == view.canonical_url:
                    return SimpleNamespace(success=True, external_id=str(final))
                return SimpleNamespace(success=False,error="substack_outbox_conflict")
            self.root.mkdir(parents=True, exist_ok=True)
            temp = Path(tempfile.mkdtemp(prefix=f".{view.article_id}-", dir=self.root))
            try:
                (temp / "draft.html").write_text(view.body_html, encoding="utf-8")
                (temp / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temp, final)
            except Exception:
                shutil.rmtree(temp, ignore_errors=True); raise
            return SimpleNamespace(success=True, external_id=str(final))
        except FileExistsError: return SimpleNamespace(success=True, external_id=str(final))
        except OSError: return SimpleNamespace(success=False,error="substack_outbox_write_failed")
