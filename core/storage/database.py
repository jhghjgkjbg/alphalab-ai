import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, UTC

class SQLiteDatabase:
    def __init__(self, path=None, timeout=30):
        self.path=Path(path) if path else Path(__file__).resolve().parents[2]/"runtime"/"ai_scout.db"; self.path.parent.mkdir(parents=True, exist_ok=True); self.timeout=timeout; self.migrate()
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path, timeout=self.timeout); c.row_factory=sqlite3.Row
        try:
            c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL"); yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()
    def migrate(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS published_articles(id TEXT PRIMARY KEY,published_at TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',url TEXT NOT NULL,canonical_url TEXT NOT NULL UNIQUE,source TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT '',language TEXT NOT NULL DEFAULT 'en',score REAL NOT NULL DEFAULT 0,trend_bonus REAL NOT NULL DEFAULT 0,reputation REAL NOT NULL DEFAULT 0,editorial_score INTEGER NOT NULL DEFAULT 0,editorial_verdict TEXT NOT NULL DEFAULT '',telegram_message_id INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publications(publication_id TEXT PRIMARY KEY,source TEXT NOT NULL,source_url TEXT NOT NULL,canonical_url TEXT NOT NULL UNIQUE,original_title TEXT NOT NULL,en_title TEXT NOT NULL,en_body TEXT NOT NULL,ru_title TEXT NOT NULL,ru_body TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_pub_date ON published_articles(published_at); CREATE INDEX IF NOT EXISTS idx_pub_source ON published_articles(source); CREATE INDEX IF NOT EXISTS idx_pub_category ON published_articles(category);
            CREATE TABLE IF NOT EXISTS publication_memory(identity TEXT PRIMARY KEY,article_id TEXT,canonical_url TEXT NOT NULL,title TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT '',published_at TEXT NOT NULL,expires_at TEXT NOT NULL,embedding_json TEXT,created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_mem_url ON publication_memory(canonical_url); CREATE INDEX IF NOT EXISTS idx_mem_exp ON publication_memory(expires_at);
            CREATE TABLE IF NOT EXISTS analytics_counters(name TEXT PRIMARY KEY,value INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS analytics_sources(source TEXT PRIMARY KEY,received INTEGER NOT NULL DEFAULT 0,published INTEGER NOT NULL DEFAULT 0,rejected INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS analytics_categories(category TEXT PRIMARY KEY,published INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS analytics_daily(day TEXT PRIMARY KEY,received INTEGER NOT NULL DEFAULT 0,published INTEGER NOT NULL DEFAULT 0,rejected INTEGER NOT NULL DEFAULT 0,editorial_calls INTEGER NOT NULL DEFAULT 0,translation_calls INTEGER NOT NULL DEFAULT 0,duplicates INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
            """)
            columns = {row[1] for row in c.execute("PRAGMA table_info(published_articles)")}
            if "en_body" not in columns:
                try:
                    c.execute("ALTER TABLE published_articles ADD COLUMN en_body TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower() or "en_body" not in str(exc).lower():
                        raise
                    columns = {row[1] for row in c.execute("PRAGMA table_info(published_articles)")}
                    if "en_body" not in columns:
                        raise
            c.execute("INSERT OR IGNORE INTO schema_migrations VALUES(1,?)",(datetime.now(UTC).isoformat(),))
    def version(self):
        with self.connect() as c: return c.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]

    def migrate_json(self):
        root=self.path.parent; now=datetime.now(UTC).isoformat(); counts={"published_imported":0,"published_skipped":0,"memory_imported":0,"memory_skipped":0,"analytics_imported":0,"errors":0}
        def load(name):
            try:
                p=root/name
                return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            except Exception: counts["errors"]+=1; return None
        with self.connect() as c:
            rows=load("published_articles.json") or []
            for r in rows if isinstance(rows,list) else []:
                try:
                    c.execute("INSERT OR IGNORE INTO published_articles(id,published_at,title,summary,url,canonical_url,source,category,language,score,trend_bonus,reputation,editorial_score,editorial_verdict,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(r.get("id") or r.get("url")),r.get("published_at") or now,r.get("title") or "",r.get("summary") or "",r.get("url") or "",r.get("canonical_url") or r.get("url") or "",r.get("source") or "",r.get("category") or "",r.get("language") or "en",float(r.get("score") or 0),float(r.get("trend_bonus") or 0),float(r.get("reputation") or 0),int(r.get("editorial_score") or 0),r.get("editorial_verdict") or "",now,now)); counts["published_imported"]+=c.execute("SELECT changes()").fetchone()[0] or 0
                except Exception: counts["errors"]+=1
            mem=load("publication_memory.json") or []
            for r in mem if isinstance(mem,list) else []:
                try:
                    ident=str(r.get("id") or r.get("url") or r.get("title")); c.execute("INSERT OR IGNORE INTO publication_memory(identity,article_id,canonical_url,title,source,category,published_at,expires_at,embedding_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(ident,r.get("id"),r.get("url") or ident,r.get("title") or "",r.get("source") or "",r.get("category") or "",r.get("published_at") or now,r.get("expires_at") or now,json.dumps(r.get("embedding")) if r.get("embedding") is not None else None,now)); counts["memory_imported"]+=c.execute("SELECT changes()").fetchone()[0] or 0
                except Exception: counts["errors"]+=1
            a=load("analytics.json") or {}
            for k,v in (a.get("counters",{}) if isinstance(a,dict) else {}).items():
                try: c.execute("INSERT OR IGNORE INTO analytics_counters(name,value,updated_at) VALUES(?,?,?)",(k,int(v),now)); counts["analytics_imported"]+=1
                except Exception: counts["errors"]+=1
        print("sqlite migration: "+" ".join(f"{k}={v}" for k,v in counts.items())); return counts
