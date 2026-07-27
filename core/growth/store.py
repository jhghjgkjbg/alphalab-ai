import hashlib, json
from datetime import UTC
from .events import GrowthEvent, sanitize_metadata

class GrowthEventStore:
    def __init__(self, database=None):
        from core.storage.database import SQLiteDatabase
        self.database = database or SQLiteDatabase()

    @staticmethod
    def event_id(event):
        raw = "|".join(str(x or "") for x in (event.event_type, event.subscriber_id, event.anonymous_id, event.article_id, event.destination_id, event.campaign_id, event.link_id, event.event_id))
        return hashlib.sha256(raw.encode()).hexdigest()

    def append(self, event: GrowthEvent):
        event_id = event.event_id or self.event_id(event)
        metadata = sanitize_metadata(event.metadata)
        values = (event_id, event.occurred_at.astimezone(UTC).isoformat(), event.event_type, event.subscriber_id, event.anonymous_id, event.article_id, event.destination_id, event.campaign_id, event.link_id, event.utm_source, event.utm_medium, event.utm_campaign, event.utm_content, json.dumps(metadata, sort_keys=True))
        with self.database.connect() as c: c.execute("INSERT OR IGNORE INTO growth_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
        return event_id

    def _list(self, column, value, limit=None):
        if not value: return []
        sql = f"SELECT * FROM growth_events WHERE {column}=? ORDER BY occurred_at,event_id"
        args = [str(value)]
        if limit is not None:
            if int(limit) < 0: raise ValueError("limit must be non-negative")
            sql += " LIMIT ?"; args.append(int(limit))
        with self.database.connect() as c: return [dict(r) for r in c.execute(sql, args)]

    def list_for_subscriber(self, value): return self._list("subscriber_id", value)
    def list_for_anonymous(self, value): return self._list("anonymous_id", value)
    def list_for_campaign(self, value, limit=None): return self._list("campaign_id", value, limit)
    def list_for_link(self, value, limit=None): return self._list("link_id", value, limit)
