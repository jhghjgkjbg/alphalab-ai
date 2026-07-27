import hashlib, json
from datetime import UTC, datetime
from .events import DistributionEvent

ALLOWED_METADATA = {"delivery_mode", "remote_publication_performed", "tracking_enabled", "scheduled", "resume_decision", "publisher_kind"}

class DistributionEventStore:
    def __init__(self, database=None):
        from core.storage.database import SQLiteDatabase
        self.database = database or SQLiteDatabase()
    @staticmethod
    def event_id(event):
        raw = "|".join(map(str, (event.article_id, event.destination_id, event.event_type, event.attempt_number, event.reason or "", event.external_id or "")))
        return hashlib.sha256(raw.encode()).hexdigest()
    def append(self, event):
        metadata = {k: v for k, v in dict(event.metadata or {}).items() if k in ALLOWED_METADATA and isinstance(v, (str, int, float, bool, type(None)))}
        event_id = event.event_id or self.event_id(event)
        with self.database.connect() as c:
            c.execute("INSERT OR IGNORE INTO distribution_events VALUES(?,?,?,?,?,?,?,?,?,?,?)", (event_id, event.occurred_at.astimezone(UTC).isoformat(), event.event_type, str(event.article_id), str(event.destination_id), event.delivery_status, int(event.attempt_number), event.external_id, event.scheduled_for.astimezone(UTC).isoformat() if event.scheduled_for else None, event.reason, json.dumps(metadata, sort_keys=True)))
        return event_id
    def list_for_article(self, article_id):
        with self.database.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM distribution_events WHERE article_id=? ORDER BY occurred_at,event_id", (str(article_id),))]
    def list_for_destination(self, destination_id, limit=None):
        sql="SELECT * FROM distribution_events WHERE destination_id=? ORDER BY occurred_at,event_id"; args=[str(destination_id)]
        if limit is not None: sql += " LIMIT ?"; args.append(int(limit))
        with self.database.connect() as c: return [dict(r) for r in c.execute(sql,args)]
    def count_by_event_type(self):
        with self.database.connect() as c: return {r[0]: r[1] for r in c.execute("SELECT event_type,COUNT(*) FROM distribution_events GROUP BY event_type")}
