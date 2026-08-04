from datetime import datetime, UTC, timedelta
import os
from uuid import uuid4
from .database import SQLiteDatabase
from datetime import datetime, UTC
from dataclasses import fields, is_dataclass

def _publication_mapping(article):
    if isinstance(article, dict): return article
    names = ("id", "publication_id", "article_id", "title", "summary", "url", "canonical_url", "source", "category", "language", "published_at", "score", "trend_bonus", "reputation", "editorial_score", "editorial_verdict", "en_body", "image_url")
    data = {name: getattr(article, name, None) for name in names if hasattr(article, name)}
    variants = getattr(article, "variants", {}) or {}
    if "en_body" not in data:
        english = variants.get("en") if isinstance(variants, dict) else None
        data["en_body"] = getattr(english, "body", None) or getattr(article, "body", None) or getattr(article, "summary", "")
    if "image_url" not in data:
        metadata = getattr(article, "metadata", {}) or {}
        data["image_url"] = metadata.get("image_url", "") if isinstance(metadata, dict) else ""
    if "title" not in data and variants:
        variant = variants.get(getattr(article, "language", "en")) or next(iter(variants.values()))
        data["title"], data["summary"] = getattr(variant, "title", ""), getattr(variant, "summary", "")
    return data

class SQLitePublishedArticlesStore:
    def __init__(self,database=None,max_records=10000): self.database=database or SQLiteDatabase(); self.max_records=max_records; self.path=self.database.path
    def append(self,article):
        d=_publication_mapping(article); now=datetime.now(UTC).isoformat(); aid=str(d.get('id') or d.get('publication_id') or d.get('article_id') or d.get('url')); url=d.get('url') or aid
        with self.database.connect() as c:
            existing = c.execute("SELECT id,summary,score FROM published_articles WHERE id=? OR canonical_url=? LIMIT 1", (aid, url)).fetchone()
            if existing is not None:
                incomplete = not str(existing["summary"] or "").strip() and (existing["score"] is None or float(existing["score"] or 0) == 0.0)
                if incomplete:
                    c.execute("UPDATE published_articles SET published_at=?,title=?,summary=?,en_body=?,image_url=?,url=?,canonical_url=?,source=?,category=?,language=?,score=?,trend_bonus=?,reputation=?,editorial_score=?,editorial_verdict=?,updated_at=? WHERE id=?", (d.get('published_at') or now, d.get('title',''), d.get('summary',''), d.get('en_body') or d.get('summary',''), d.get('image_url',''), url, url, d.get('source',''), d.get('category',''), d.get('language','en'), float(d.get('score',0)), float(d.get('trend_bonus',0)), float(d.get('reputation',0)), int(d.get('editorial_score',0)), d.get('editorial_verdict',''), now, existing["id"]))
                    return d
                return None
            cur=c.execute("INSERT OR IGNORE INTO published_articles(id,published_at,title,summary,en_body,image_url,url,canonical_url,source,category,language,score,trend_bonus,reputation,editorial_score,editorial_verdict,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,d.get('published_at') or now,d.get('title',''),d.get('summary',''),d.get('en_body') or d.get('summary',''),d.get('image_url',''),url,url,d.get('source',''),d.get('category',''),d.get('language','en'),float(d.get('score',0)),float(d.get('trend_bonus',0)),float(d.get('reputation',0)),int(d.get('editorial_score',0)),d.get('editorial_verdict',''),now,now))
            if not cur.rowcount:return None
            c.execute("DELETE FROM published_articles WHERE id IN (SELECT id FROM published_articles ORDER BY published_at DESC LIMIT -1 OFFSET ?)",(self.max_records,)); return d
    def contains(self,article_id=None,url=None):
        with self.database.connect() as c:
            row = c.execute("SELECT summary,score FROM published_articles WHERE id=? OR canonical_url=? LIMIT 1", (article_id or '', url or '')).fetchone()
            return row is not None and bool(str(row["summary"] or "").strip() or float(row["score"] or 0))
    def reserve(self, article_id, canonical_url, owner=None, ttl_seconds=1800):
        """Atomically claim an article for one production run."""
        aid, url = str(article_id or ""), str(canonical_url or "")
        if not aid or not url:
            return False
        now = datetime.now(UTC).isoformat(); owner = owner or uuid4().hex
        try:
            with self.database.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute("SELECT state,updated_at FROM production_reservations WHERE article_id=? OR canonical_url=? LIMIT 1", (aid, url)).fetchone()
                if row is not None:
                    stale = row["state"] == "reserved" and datetime.fromisoformat(row["updated_at"]) < datetime.now(UTC) - timedelta(seconds=ttl_seconds)
                    if not stale or row["state"] == "published":
                        return False
                    c.execute("DELETE FROM production_reservations WHERE article_id=? OR canonical_url=?", (aid, url))
                c.execute("INSERT INTO production_reservations(article_id,canonical_url,state,owner,created_at,updated_at) VALUES(?,?,?,?,?,?)", (aid, url, "reserved", owner, now, now))
            return True
        except Exception as exc:
            import sqlite3
            if isinstance(exc, sqlite3.IntegrityError):
                return False
            raise
    def finalize_reservation(self, article_id, canonical_url, owner=None):
        with self.database.connect() as c:
            query = "UPDATE production_reservations SET state='published',updated_at=? WHERE article_id=? AND canonical_url=?"
            args = [datetime.now(UTC).isoformat(), str(article_id or ""), str(canonical_url or "")]
            if owner is not None: query += " AND owner=?"; args.append(owner)
            return c.execute(query, args).rowcount > 0
    def release_reservation(self, article_id, canonical_url, owner=None):
        with self.database.connect() as c:
            query = "DELETE FROM production_reservations WHERE article_id=? AND canonical_url=?"
            args = [str(article_id or ""), str(canonical_url or "")]
            if owner is not None: query += " AND owner=?"; args.append(owner)
            return c.execute(query, args).rowcount > 0
    def begin_delivery_attempt(self, article_id, canonical_url, destination, scheduled_for=None):
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as c:
            value = scheduled_for.astimezone(UTC).isoformat() if scheduled_for is not None else None
            c.execute("INSERT INTO publication_deliveries(article_id,canonical_url,destination,status,attempt_count,created_at,updated_at,scheduled_for) VALUES(?,?,?,?,1,?,?,?) ON CONFLICT(article_id,destination) DO UPDATE SET status='pending',attempt_count=attempt_count+1,updated_at=?,scheduled_for=?", (str(article_id), str(canonical_url), str(destination), "pending", now, now, value, now, value))
            return c.execute("SELECT * FROM publication_deliveries WHERE article_id=? AND destination=?", (str(article_id), str(destination))).fetchone()
    def prepare_delivery_attempt(self, article_id, canonical_url, destination, ttl_seconds=1800, scheduled_for=None):
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM publication_deliveries WHERE article_id=? AND destination=?", (str(article_id), str(destination))).fetchone()
            if row is None:
                value = scheduled_for.astimezone(UTC).isoformat() if scheduled_for is not None else None
                c.execute("INSERT INTO publication_deliveries(article_id,canonical_url,destination,status,attempt_count,created_at,updated_at,scheduled_for) VALUES(?,?,?,?,1,?,?,?)", (str(article_id), str(canonical_url), str(destination), "pending", now, now, value))
                return "send"
            if row["status"] in {"sent", "unknown"}:
                return "skip"
            stale = row["status"] == "pending" and datetime.fromisoformat(row["updated_at"]) < datetime.now(UTC) - timedelta(seconds=ttl_seconds)
            if row["status"] == "pending" and not stale:
                return "skip"
            value = scheduled_for.astimezone(UTC).isoformat() if scheduled_for is not None else None
            c.execute("UPDATE publication_deliveries SET status='pending',attempt_count=attempt_count+1,updated_at=?,scheduled_for=COALESCE(scheduled_for, ?) WHERE article_id=? AND destination=?", (now, value, str(article_id), str(destination)))
            return "send"
    def record_delivery(self, article_id, canonical_url, destination, status, external_id=None, error=None):
        if status not in {"pending", "sent", "failed", "unknown", "skipped"}:
            raise ValueError("invalid delivery status")
        now = datetime.now(UTC).isoformat()
        with self.database.connect() as c:
            cur = c.execute("UPDATE publication_deliveries SET status=?,external_id=?,error=?,updated_at=? WHERE article_id=? AND destination=?", (status, None if external_id is None else str(external_id), error, now, str(article_id), str(destination)))
            return cur.rowcount > 0
    def delivery_state(self, article_id=None, canonical_url=None, destination=None):
        with self.database.connect() as c:
            clauses=[]; args=[]
            if article_id is not None: clauses.append("article_id=?"); args.append(str(article_id))
            if canonical_url is not None: clauses.append("canonical_url=?"); args.append(str(canonical_url))
            if destination is not None: clauses.append("destination=?"); args.append(str(destination))
            if not clauses: return None
            rows = c.execute("SELECT * FROM publication_deliveries WHERE " + " AND ".join(clauses) + " ORDER BY updated_at DESC", args).fetchall()
            return [dict(r) for r in rows]
    def delivery_states(self, article_id, canonical_url=None):
        return self.delivery_state(article_id=article_id, canonical_url=canonical_url)
    def latest(self,limit=50):
        with self.database.connect() as c:return [dict(r) for r in c.execute("SELECT * FROM published_articles ORDER BY published_at DESC LIMIT ?",(limit,))]
    def search(self,query,limit=50):
        with self.database.connect() as c:return [dict(r) for r in c.execute("SELECT * FROM published_articles WHERE lower(title||' '||summary||' '||source||' '||category) LIKE ? ORDER BY published_at DESC LIMIT ?",(f'%{query.lower()}%',limit))]
    def by_category(self,category): return self.search(category)
    def by_source(self,source): return self.search(source)
    def count(self):
        with self.database.connect() as c:return c.execute("SELECT COUNT(*) FROM published_articles").fetchone()[0]
    def subscribe(self, email, consent_at=None):
        """Idempotently store a consented subscriber."""
        now = datetime.now(UTC).isoformat()
        consent = consent_at or now
        with self.database.connect() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO subscribers(email,status,consent_at,created_at,updated_at) VALUES(?,?,?,?,?)",
                (str(email), "subscribed", str(consent), now, now),
            )
            return bool(cur.rowcount)
    def create_pending_subscriber(self, email, token_hash, expires_at, consent_at=None, cooldown_seconds=60):
        now = datetime.now(UTC).isoformat(); consent = consent_at or now
        with self.database.connect() as c:
            row = c.execute("SELECT status,updated_at FROM subscribers WHERE email=?", (str(email),)).fetchone()
            if row and row["status"] in {"confirmed", "subscribed"}:
                return "confirmed"
            if row and row["updated_at"]:
                try:
                    if datetime.fromisoformat(row["updated_at"]) > datetime.now(UTC) - timedelta(seconds=cooldown_seconds):
                        return "cooldown"
                except ValueError:
                    pass
            c.execute("INSERT INTO subscribers(email,status,consent_at,confirmation_token_hash,confirmation_expires_at,confirmed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET status='pending',consent_at=excluded.consent_at,confirmation_token_hash=excluded.confirmation_token_hash,confirmation_expires_at=excluded.confirmation_expires_at,updated_at=excluded.updated_at", (str(email), "pending", str(consent), str(token_hash), str(expires_at), None, now, now))
            return "pending"
    def confirm_subscriber(self, token_hash, now=None):
        current = now or datetime.now(UTC); stamp = current.isoformat()
        with self.database.connect() as c:
            row = c.execute("SELECT email,status,confirmation_expires_at FROM subscribers WHERE confirmation_token_hash=?", (str(token_hash),)).fetchone()
            if not row or row["status"] != "pending": return False
            try:
                if datetime.fromisoformat(row["confirmation_expires_at"]) < current: return False
            except (TypeError, ValueError): return False
            c.execute("UPDATE subscribers SET status='confirmed',confirmed_at=?,confirmation_token_hash='',confirmation_expires_at='',updated_at=? WHERE email=?", (stamp, stamp, row["email"]))
            return True
    def admin_subscribers(self, status=None, limit=50, offset=0, oldest=False):
        order = "ASC" if oldest else "DESC"; clauses=[]; args=[]
        if status: clauses.append("status=?"); args.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.database.connect() as c:
            return [dict(r) for r in c.execute(f"SELECT email,status,created_at,confirmed_at FROM subscribers{where} ORDER BY created_at {order} LIMIT ? OFFSET ?", (*args, int(limit), int(offset)))]
    def admin_articles(self, source=None, category=None, limit=50, offset=0, by_score=False):
        clauses=[]; args=[]
        if source: clauses.append("source=?"); args.append(source)
        if category: clauses.append("category=?"); args.append(category)
        where=(" WHERE "+" AND ".join(clauses)) if clauses else ""; order="score DESC" if by_score else "published_at DESC"
        with self.database.connect() as c:
            return [dict(r) for r in c.execute(f"SELECT id,title,source,category,published_at,score FROM published_articles{where} ORDER BY {order} LIMIT ? OFFSET ?", (*args, int(limit), int(offset)))]
    def admin_summary(self):
        with self.database.connect() as c:
            out={"subscribers_total": c.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0], "subscribers_pending": c.execute("SELECT COUNT(*) FROM subscribers WHERE status='pending'").fetchone()[0], "subscribers_confirmed": c.execute("SELECT COUNT(*) FROM subscribers WHERE status IN ('confirmed','subscribed')").fetchone()[0], "articles_total": c.execute("SELECT COUNT(*) FROM published_articles").fetchone()[0], "articles_7d": c.execute("SELECT COUNT(*) FROM published_articles WHERE published_at >= datetime('now','-7 days')").fetchone()[0]}
            out["smtp_configured"] = bool(os.getenv("EMAIL_SMTP_HOST") and os.getenv("EMAIL_FROM_ADDRESS")); out["database_available"] = True
            return out
    def record_analytics_event(self, event_type, occurred_at=None, article_id="", source="", category="", referrer_group="direct", utm_source="", utm_medium="", utm_campaign=""):
        allowed={"page_view","article_view","original_source_click","subscribe_page_view","subscribe_submit","subscribe_success","telegram_click","rss_click"}
        if event_type not in allowed: raise ValueError("invalid analytics event")
        now=occurred_at or datetime.now(UTC).isoformat()
        with self.database.connect() as c:
            c.execute("INSERT INTO analytics_events(event_type,occurred_at,article_id,source,category,referrer_group,utm_source,utm_medium,utm_campaign) VALUES(?,?,?,?,?,?,?,?,?)", (event_type,str(now),str(article_id or "")[:200],str(source or "")[:120],str(category or "")[:120],str(referrer_group or "direct")[:20],str(utm_source or "")[:100],str(utm_medium or "")[:100],str(utm_campaign or "")[:100]))
    def purge_analytics(self, retention_days=90):
        days=max(1,int(retention_days))
        with self.database.connect() as c: return c.execute("DELETE FROM analytics_events WHERE occurred_at < datetime('now', ?)", (f"-{days} days",)).rowcount
    def analytics_summary(self, days=7):
        with self.database.connect() as c:
            rows=c.execute("SELECT event_type,COUNT(*) n FROM analytics_events WHERE occurred_at >= datetime('now', ?) GROUP BY event_type ORDER BY event_type", (f"-{max(1,int(days))} days",)).fetchall()
            return {r["event_type"]:r["n"] for r in rows}
    def analytics_breakdown(self, field, days=7):
        if field not in {"referrer_group","utm_source","utm_campaign"}: raise ValueError("invalid analytics field")
        with self.database.connect() as c: return [dict(r) for r in c.execute(f"SELECT {field} value,COUNT(*) count FROM analytics_events WHERE occurred_at >= datetime('now', ?) GROUP BY {field} ORDER BY count DESC,value", (f"-{max(1,int(days))} days",))]
    def analytics_top_articles(self, event_type, days=7, limit=10):
        if event_type not in {"article_view","original_source_click"}: raise ValueError("invalid event")
        with self.database.connect() as c:
            return [dict(r) for r in c.execute("SELECT e.article_id,COALESCE(p.title,'') title,COUNT(*) count FROM analytics_events e LEFT JOIN published_articles p ON p.id=e.article_id WHERE e.event_type=? AND e.occurred_at >= datetime('now', ?) AND e.article_id<>'' GROUP BY e.article_id,p.title ORDER BY count DESC,e.article_id LIMIT ?", (event_type,f"-{max(1,int(days))} days",min(max(int(limit),1),50)))]
    def analytics_daily(self, days=14):
        with self.database.connect() as c:
            return [dict(r) for r in c.execute("SELECT substr(occurred_at,1,10) day,SUM(event_type='page_view') page_views,SUM(event_type='article_view') article_views,SUM(event_type='original_source_click') source_clicks,SUM(event_type='subscribe_success') subscribe_successes FROM analytics_events WHERE occurred_at >= datetime('now', ?) GROUP BY day ORDER BY day DESC LIMIT ?", (f"-{max(1,int(days))} days",min(max(int(days),1),31)))]

class SQLitePublicationStore:
    STATUSES = {"draft", "published", "failed"}
    def __init__(self, database=None): self.database=database or SQLiteDatabase(); self.path=self.database.path
    def save(self, publication, status="draft"):
        if status not in self.STATUSES: raise ValueError("invalid publication status")
        if isinstance(publication, dict):
            d=publication
        else:
            d={name:getattr(publication,name,None) for name in ("publication_id","article_id","id","source","url","canonical_url","title","summary","variants")}
        v=d.get("variants",{})
        def f(lang,name):
            x=v.get(lang); return getattr(x,name,"") if x else d.get(name,"")
        now=datetime.now(UTC).isoformat(); pid=str(d.get("publication_id") or d.get("article_id") or d.get("id")); canonical=str(d.get("canonical_url") or d.get("url") or "")
        with self.database.connect() as c:
            return bool(c.execute("INSERT OR IGNORE INTO publications VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(pid,d.get("source",""),d.get("url",""),canonical,d.get("title",""),f("en","title"),f("en","body") or f("en","summary"),f("ru","title"),f("ru","body") or f("ru","summary"),status,now,now)).rowcount)
    def update_status(self, publication_id, status):
        if status not in self.STATUSES: raise ValueError("invalid publication status")
        with self.database.connect() as c: return c.execute("UPDATE publications SET status=?,updated_at=? WHERE publication_id=?",(status,datetime.now(UTC).isoformat(),str(publication_id))).rowcount>0
    def count(self):
        with self.database.connect() as c: return c.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
    def latest(self, limit=10000):
        with self.database.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM publications ORDER BY created_at DESC LIMIT ?", (limit,))]

class SQLitePublicationMemoryStore:
    def __init__(self,database=None,ttl_days=7,limit=5000,threshold=.90): self.database=database or SQLiteDatabase(); self.threshold=threshold; self.path=self.database.path
    def contains(self,vector):
        import json
        from core.similarity.metrics import cosine_similarity
        with self.database.connect() as c:
            return any(cosine_similarity(vector,tuple(json.loads(r[0] or '[]'))) >= self.threshold for r in c.execute("SELECT embedding_json FROM publication_memory WHERE expires_at>?",(datetime.now(UTC).isoformat(),)) if r[0])
    def add(self,item):
        import json
        with self.database.connect() as c:c.execute("INSERT OR IGNORE INTO publication_memory(identity,canonical_url,title,source,category,published_at,expires_at,embedding_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(item.url,item.url,item.title,item.source,item.category,item.published_at.isoformat(),datetime.now(UTC).isoformat(),json.dumps(list(item.embedding)),datetime.now(UTC).isoformat()))
    def __len__(self):
        with self.database.connect() as c:return c.execute("SELECT COUNT(*) FROM publication_memory").fetchone()[0]
