from datetime import datetime, UTC, timedelta
from uuid import uuid4
from .database import SQLiteDatabase
from datetime import datetime, UTC
from dataclasses import fields, is_dataclass

def _publication_mapping(article):
    if isinstance(article, dict): return article
    names = ("id", "publication_id", "article_id", "title", "summary", "url", "canonical_url", "source", "category", "language", "published_at", "score", "trend_bonus", "reputation", "editorial_score", "editorial_verdict", "en_body")
    data = {name: getattr(article, name, None) for name in names if hasattr(article, name)}
    variants = getattr(article, "variants", {}) or {}
    if "en_body" not in data:
        english = variants.get("en") if isinstance(variants, dict) else None
        data["en_body"] = getattr(english, "body", None) or getattr(article, "body", None) or getattr(article, "summary", "")
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
                    c.execute("UPDATE published_articles SET published_at=?,title=?,summary=?,en_body=?,url=?,canonical_url=?,source=?,category=?,language=?,score=?,trend_bonus=?,reputation=?,editorial_score=?,editorial_verdict=?,updated_at=? WHERE id=?", (d.get('published_at') or now, d.get('title',''), d.get('summary',''), d.get('en_body') or d.get('summary',''), url, url, d.get('source',''), d.get('category',''), d.get('language','en'), float(d.get('score',0)), float(d.get('trend_bonus',0)), float(d.get('reputation',0)), int(d.get('editorial_score',0)), d.get('editorial_verdict',''), now, existing["id"]))
                    return d
                return None
            cur=c.execute("INSERT OR IGNORE INTO published_articles(id,published_at,title,summary,en_body,url,canonical_url,source,category,language,score,trend_bonus,reputation,editorial_score,editorial_verdict,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,d.get('published_at') or now,d.get('title',''),d.get('summary',''),d.get('en_body') or d.get('summary',''),url,url,d.get('source',''),d.get('category',''),d.get('language','en'),float(d.get('score',0)),float(d.get('trend_bonus',0)),float(d.get('reputation',0)),int(d.get('editorial_score',0)),d.get('editorial_verdict',''),now,now))
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
