from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import PlainTextResponse, Response
from html import escape
import json, os
from urllib.parse import quote, unquote
from fastapi.staticfiles import StaticFiles
from core.api import PublishedArticlesStore

def create_app(store=None):
    app=FastAPI(title="AI Scout", docs_url=None, redoc_url=None)
    root = Path(__file__).resolve().parents[3]
    app.mount("/static", StaticFiles(directory=str(Path(__file__).with_name("static"))), name="static")
    if store is None:
        try:
            from core.storage import SQLitePublishedArticlesStore
            store = SQLitePublishedArticlesStore()
        except Exception:
            store = PublishedArticlesStore(path=root / "runtime" / "published_articles.json")
    @app.get("/api/health")
    def health(): return {"status":"ok","articles":store.count() if hasattr(store,"count") else len(store._items),"storage":"sqlite" if hasattr(store,"database") else "json"}
    @app.get("/api/articles")
    def articles(page:int=Query(1,ge=1), limit:int=Query(20,ge=1,le=100), q:str|None=None, category:str|None=None, source:str|None=None, language:str|None=None, sort:str="latest"):
        rows=store.search(q) if q else (store.latest(10000) if hasattr(store,"latest") else list(store._items))
        if category: rows=[x for x in rows if x.get("category","").casefold()==category.casefold()]
        if source: rows=[x for x in rows if x.get("source","").casefold()==source.casefold()]
        if language: rows=[x for x in rows if x.get("language","").casefold()==language.casefold()]
        if sort=="score": rows.sort(key=lambda x: float(x.get("score",0)), reverse=True)
        total=len(rows); start=(page-1)*limit
        return {"items":rows[start:start+limit],"page":page,"limit":limit,"total":total,"pages":(total+limit-1)//limit}
    @app.get("/api/articles/{article_id}")
    def article(article_id:str):
        for row in (store.latest(10000) if hasattr(store,"latest") else store._items):
            if str(row.get("id"))==article_id: return row
        raise HTTPException(404,"article not found")
    @app.get("/api/categories")
    def categories():
        out={}
        for x in (store.latest(10000) if hasattr(store,"latest") else store._items): out[x.get("category","")]=out.get(x.get("category",""),0)+1
        return out
    @app.get("/api/sources")
    def sources():
        out={}
        for x in (store.latest(10000) if hasattr(store,"latest") else store._items): out[x.get("source","")]=out.get(x.get("source",""),0)+1
        return out
    @app.get("/", response_class=HTMLResponse)
    def home(): return HTMLResponse(Path(__file__).with_name("index.html").read_text(encoding="utf-8"))
    def language_feed(language: str):
        rows = store.latest(10000) if hasattr(store, "latest") else list(store._items)
        cards = []
        for row in rows:
            title = row.get(f"{language}_title") or row.get("title") or "Untitled"
            summary = row.get(f"{language}_body") or row.get("summary") or ""
            slug = row.get("publication_id") or row.get("id") or row.get("canonical_url") or row.get("url")
            cards.append(f"<article><h2>{escape(str(title))}</h2><p>{escape(str(summary))}</p><small>{escape(str(row.get('source','')))} · {escape(str(row.get('created_at') or row.get('published_at') or ''))} · {language}</small><p><a href='/article/{quote(str(slug), safe='')}'>Read article</a></p></article>")
        return HTMLResponse("<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='/static/styles.css'><title>AI Scout</title></head><body><header class='site-header'><strong>AI Scout</strong><span>AI &amp; technology intelligence</span></header><main class='feed'><h1>AI Scout</h1>" + ("".join(cards) or "<p>No published articles yet</p>") + "</main></body></html>")
    @app.get("/en", response_class=HTMLResponse)
    def english_feed(): return language_feed("en")
    @app.get("/ru", response_class=HTMLResponse)
    def russian_feed(): return language_feed("ru")
    def admin_guard(request):
        expected=os.getenv("ALPHALAB_ADMIN_TOKEN", "")
        if expected and request.headers.get("X-Admin-Token") != expected: raise HTTPException(401, "admin authentication required")
    @app.get("/admin", response_class=HTMLResponse)
    def admin_home(request: Request):
        admin_guard(request); return HTMLResponse("<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>AI Scout Admin</title></head><body><main><h1>AI Scout Admin</h1><nav><a href='/admin/publications'>Publications</a></nav></main></body></html>")
    @app.get("/admin/publications", response_class=HTMLResponse)
    def admin_publications(request: Request, status: str|None=None):
        admin_guard(request); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items)
        if status: rows=[r for r in rows if str(r.get("status", "published")).casefold()==status.casefold()]
        rows.sort(key=lambda r:str(r.get("created_at") or r.get("published_at") or ""), reverse=True)
        body="".join(f"<li><a href='/admin/publication/{quote(str(r.get('publication_id') or r.get('id')),safe='')}'>{escape(str(r.get('en_title') or r.get('title') or 'Untitled'))}</a> — {escape(str(r.get('source','')))} — {escape(str(r.get('status','published')))} — {escape(str(r.get('editorial_score',0)))}</li>" for r in rows)
        return HTMLResponse(f"<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>Publications</title></head><body><main><h1>Publications</h1><ul>{body or '<li>No publications</li>'}</ul></main></body></html>")
    @app.get("/admin/publication/{publication_id:path}", response_class=HTMLResponse)
    def admin_publication(request: Request, publication_id: str):
        admin_guard(request); decoded=unquote(publication_id); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items); row=next((r for r in rows if str(r.get("publication_id") or r.get("id"))==decoded), None)
        if not row: raise HTTPException(404, "publication not found")
        title=row.get("en_title") or row.get("title") or "Untitled"
        return HTMLResponse(f"<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>{escape(str(title))}</title></head><body><main><h1>{escape(str(title))}</h1><p>Source: {escape(str(row.get('source','')))}</p><p>Status: {escape(str(row.get('status','published')))}</p><p>Editorial score: {escape(str(row.get('editorial_score',0)))}</p><p>Publication date: {escape(str(row.get('created_at') or row.get('published_at') or ''))}</p></main></body></html>")
    @app.post("/admin/publication/{publication_id:path}/action")
    def admin_action(request: Request, publication_id: str, action: str):
        admin_guard(request); decoded=unquote(publication_id); rows=store.latest(10000) if hasattr(store,"latest") else list(store._items); row=next((r for r in rows if str(r.get("publication_id") or r.get("id"))==decoded), None)
        if not row: raise HTTPException(404, "publication not found")
        if action not in {"publish","retry_ai","retry_telegram","retry_website","mark_failed","mark_draft"}: raise HTTPException(400, "unknown action")
        current=str(row.get("status", "draft"))
        if action == "publish" and current == "published": raise HTTPException(409, "duplicate publication prevented")
        status = "published" if action == "publish" else "failed" if action == "mark_failed" else "draft" if action == "mark_draft" else current
        if hasattr(store, "update_status"): store.update_status(decoded, status)
        return {"ok": True, "action": action, "publication_id": decoded, "status": status}
    @app.post("/admin/publication/{publication_id:path}/{action}")
    def admin_action_alias(request: Request, publication_id: str, action: str):
        return admin_action(request, publication_id, action)
    @app.get("/article/{article_id:path}", response_class=HTMLResponse)
    def page(article_id:str):
        decoded = unquote(article_id)
        row = None; matched = None
        for candidate in (store.latest(10000) if hasattr(store,"latest") else store._items):
            for field in ("id", "publication_id", "canonical_url", "url"):
                if str(candidate.get(field) or "") == decoded:
                    row, matched = candidate, field
                    break
            if row: break
        if not row:
            return HTMLResponse("<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>Article not found — AI Scout</title></head><body><header class='site-header'><strong>AI Scout</strong><span>AI &amp; technology intelligence</span></header><main class='article-page'><article class='article-card'><h1>Article not found</h1><p>The requested article is unavailable.</p><a class='button secondary' href='/'>Back to feed</a></article></main></body></html>", status_code=404)
        base=os.getenv("ALPHALAB_PUBLIC_BASE_URL","http://127.0.0.1:8080").rstrip("/"); canonical=f"{base}/article/{quote(article_id,safe='') }"; title=str(row.get("en_title") or row.get("title") or "Untitled"); summary=str(row.get("en_body") or row.get("summary") or "")[:300]; url=str(row.get("source_url") or row.get("url") or ""); data={"@context":"https://schema.org","@type":"Article","headline":title,"description":summary,"datePublished":row.get("published_at") or row.get("created_at"),"mainEntityOfPage":canonical,"publisher":{"@type":"Organization","name":"AI Scout"}}
        from urllib.parse import urlparse
        parsed=urlparse(url); original=(f"<a class='button primary' href='{escape(url,quote=True)}' target='_blank' rel='noopener noreferrer'>Original source</a>" if parsed.scheme in ('http','https') else '')
        category = f"<span class='badge'>{escape(str(row.get('category')))}</span>" if row.get('category') else ''; source=escape(str(row.get('source') or '')); score=float(row.get('score') or 0); score=int(score*100) if score<=1 else int(score); verdict=f"<span>{escape(str(row.get('editorial_verdict')))}</span>" if row.get('editorial_verdict') else ''
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='/static/styles.css'><title>{escape(title)} — AI Scout</title><meta name='description' content='{escape(summary,quote=True)}'><link rel='canonical' href='{escape(canonical,quote=True)}'><meta property='og:type' content='article'><meta property='og:title' content='{escape(title,quote=True)}'><meta property='og:description' content='{escape(summary,quote=True)}'><meta property='og:url' content='{escape(canonical,quote=True)}'><meta property='og:site_name' content='AI Scout'><meta name='twitter:card' content='summary_large_image'><meta name='twitter:title' content='{escape(title,quote=True)}'><meta name='twitter:description' content='{escape(summary,quote=True)}'><script type='application/ld+json'>{json.dumps(data,ensure_ascii=False)}</script></head><body><header class='site-header'><strong>AI Scout</strong><span>AI &amp; technology intelligence</span></header><main class='article-page'><a class='back-link' href='/'>← Back to feed</a><article class='article-card'>{category}<span class='badge'>{source}</span><h1>{escape(title)}</h1><div class='meta'><span>{escape(str(row.get('published_at') or '')[:10])}</span><span>{escape(str(row.get('language') or ''))}</span><span class='score'>AI Scout score {score}/100</span>{verdict}</div><p class='article-summary'>{escape(summary)}</p><div class='article-actions'>{original}<a class='button secondary' href='/'>Back to feed</a></div></article></main><footer class='site-footer'>AI Scout · AI &amp; technology intelligence</footer></body></html>")
    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(): return f"User-agent: *\nAllow: /\n\nSitemap: {os.getenv('ALPHALAB_PUBLIC_BASE_URL','http://127.0.0.1:8080').rstrip('/')}/sitemap.xml\n"
    @app.get("/sitemap.xml")
    def sitemap():
        base=os.getenv("ALPHALAB_PUBLIC_BASE_URL","http://127.0.0.1:8080").rstrip("/"); rows=store.latest(5000) if hasattr(store,"latest") else store._items; urls=[f"<url><loc>{escape(base+'/')}</loc></url>"]+[f"<url><loc>{escape(base+'/article/'+quote(str(x.get('id')),safe=''))}</loc><lastmod>{escape(str(x.get('published_at','')))}</lastmod></url>" for x in rows]; return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(urls)+"</urlset>",media_type="application/xml")
    def rss(language=None):
        rows = store.latest(100) if hasattr(store, "latest") else list(store._items)
        base=os.getenv("ALPHALAB_PUBLIC_BASE_URL","http://127.0.0.1:8080").rstrip("/")
        items=[]
        for row in rows:
            title=row.get(f"{language}_title") if language else row.get("title")
            summary=row.get(f"{language}_body") if language else row.get("summary")
            title=title or row.get("title") or "Untitled"; summary=summary or row.get("summary") or ""
            url=row.get("source_url") or row.get("url") or ""; slug=row.get("publication_id") or row.get("id") or row.get("canonical_url") or url
            items.append(f"<item><title>{escape(str(title))}</title><description>{escape(str(summary))}</description><link>{escape(base+'/article/'+quote(str(slug),safe=''))}</link><guid>{escape(str(row.get('canonical_url') or url))}</guid><pubDate>{escape(str(row.get('created_at') or row.get('published_at') or ''))}</pubDate></item>")
        return Response('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>AI Scout</title><link>'+escape(base)+'</link>'+''.join(items)+'</channel></rss>',media_type="application/rss+xml")
    @app.get("/rss")
    def rss_all(): return rss()
    @app.get("/en/rss")
    def rss_en(): return rss("en")
    @app.get("/ru/rss")
    def rss_ru(): return rss("ru")
    return app
