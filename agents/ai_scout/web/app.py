from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import PlainTextResponse, Response
from html import escape
import json, os
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote, unquote
from fastapi.staticfiles import StaticFiles
from core.api import PublishedArticlesStore

_HTMLResponse = HTMLResponse
_UNIFIED_HEADER = "<header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a></nav></div></header>"
_UNIFIED_FOOTER = "<footer class='site-footer'><div class='container footer-inner'><div class='footer-brand-block'><a class='footer-brand' href='/' aria-label='AlphaLab AI home'><strong>AlphaLab AI</strong></a><p>Signal, not noise.</p></div><nav class='footer-links' aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a><a href='/rss'>RSS Feed</a></nav></div></footer>"

class HTMLResponse(_HTMLResponse):
    def __init__(self, content="", *args, **kwargs):
        if isinstance(content, str):
            content = content.replace("AlphaLab AI also publishes updates through dedicated English and Russian Telegram channels.", "AlphaLab AI also publishes updates through the official English Telegram channel.")
        if isinstance(content, str) and "site-header" in content and "<body" in content:
            header_marker = "<header class='site-header'>" if "<header class='site-header'>" in content else '<header class="site-header">'
            start, end = content.find(header_marker), content.find("</header>")
            if start >= 0 and end >= start:
                content = content[:start] + _UNIFIED_HEADER + content[end + len("</header>"):]
            footer_marker = "<footer class='site-footer'>" if "<footer class='site-footer'>" in content else '<footer class="site-footer">'
            footer_start = content.find(footer_marker)
            if footer_start >= 0:
                content = content[:footer_start] + _UNIFIED_FOOTER + content[content.find("</footer>", footer_start) + len("</footer>"):]
        super().__init__(content, *args, **kwargs)

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
    def _api_row(row):
        return {key: value for key, value in row.items() if key != "en_body"}
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
        return {"items":[_api_row(row) for row in rows[start:start+limit]],"page":page,"limit":limit,"total":total,"pages":(total+limit-1)//limit}
    @app.get("/api/articles/{article_id}")
    def article(article_id:str):
        for row in (store.latest(10000) if hasattr(store,"latest") else store._items):
            if str(row.get("id"))==article_id: return _api_row(row)
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
    @app.get("/en", include_in_schema=False)
    def english_redirect(): return RedirectResponse("/", status_code=308)
    @app.get("/ru", include_in_schema=False)
    def russian_redirect(): return RedirectResponse("/", status_code=308)
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
        body="".join(f"<li><a href='/admin/publication/{quote(str(r.get('publication_id') or r.get('id')),safe='')}'>{escape(str(r.get('en_title') or r.get('title') or 'Untitled'))}</a> Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('source','')))} Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('status','published')))} Р Р†Р вЂљРІР‚Сњ {escape(str(r.get('editorial_score',0)))}</li>" for r in rows)
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
            return HTMLResponse("<!doctype html><html><head><link rel='stylesheet' href='/static/styles.css'><title>Article not found &mdash; AI Scout</title></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/rss'>RSS</a></nav></div></header><main class='article-page'><article class='article-card'><h1>Article not found</h1><p>The requested article is unavailable.</p><a class='button secondary' href='/'>&larr; Back to feed</a></article></main></body></html>", status_code=404)
        base=os.getenv("ALPHALAB_PUBLIC_BASE_URL","http://127.0.0.1:8080").rstrip("/"); canonical=f"{base}/article/{quote(article_id,safe='') }"; title=str(row.get("en_title") or row.get("title") or "Untitled"); article_text=str(row.get("en_body") or row.get("summary") or "").strip(); meta_description=article_text[:300]; url=str(row.get("source_url") or row.get("url") or ""); data={"@context":"https://schema.org","@type":"Article","headline":title,"description":meta_description,"datePublished":row.get("published_at") or row.get("created_at"),"mainEntityOfPage":canonical,"publisher":{"@type":"Organization","name":"AI Scout"}}
        related_rows = store.latest(10000) if hasattr(store, "latest") else list(store._items)
        current_keys = {str(row.get(field)) for field in ("id", "publication_id", "canonical_url", "url") if row.get(field)}
        related = []
        for candidate in related_rows:
            candidate_keys = {str(candidate.get(field)) for field in ("id", "publication_id", "canonical_url", "url") if candidate.get(field)}
            if current_keys & candidate_keys: continue
            candidate_title = candidate.get("en_title") or candidate.get("title") or "Untitled"
            candidate_slug = candidate.get("publication_id") or candidate.get("id") or candidate.get("canonical_url") or candidate.get("url")
            if not candidate_slug: continue
            candidate_date = candidate.get("published_at") or candidate.get("created_at") or ""
            related.append(f"<article class='related-card'><h3>{escape(str(candidate_title))}</h3><small>{escape(str(candidate_date)[:10])}</small><a href='/article/{quote(str(candidate_slug), safe='')}'>Read article</a></article>")
            if len(related) >= 4: break
        related_html = "<section class='related-articles' aria-labelledby='related-title'><h2 id='related-title'>Related articles</h2><div class='related-grid'>" + "".join(related) + "</div></section>" if related else ""

        from urllib.parse import urlparse
        parsed=urlparse(url); original=(f"<a class='button primary' href='{escape(url,quote=True)}' target='_blank' rel='noopener noreferrer'>Original source</a>" if parsed.scheme in ('http','https') else '')
        category = f"<span class='badge'>{escape(str(row.get('category')))}</span>" if row.get('category') else ''; source=escape(str(row.get('source') or '')); score=float(row.get('score') or 0); score=int(score*100) if score<=1 else int(score); verdict=f"<span>{escape(str(row.get('editorial_verdict')))}</span>" if row.get('editorial_verdict') else ''
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><link rel='stylesheet' href='/static/styles.css'><title>{escape(title)} &mdash; AI Scout</title><meta name='description' content='{escape(meta_description,quote=True)}'><link rel='canonical' href='{escape(canonical,quote=True)}'><meta property='og:type' content='article'><meta property='og:title' content='{escape(title,quote=True)}'><meta property='og:description' content='{escape(meta_description,quote=True)}'><meta property='og:url' content='{escape(canonical,quote=True)}'><meta property='og:site_name' content='AI Scout'><meta name='twitter:card' content='summary_large_image'><meta name='twitter:title' content='{escape(title,quote=True)}'><meta name='twitter:description' content='{escape(meta_description,quote=True)}'><script type='application/ld+json'>{json.dumps(data,ensure_ascii=False)}</script></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/rss'>RSS</a></nav></div></header><main class='article-page'><a class='back-link' href='/'>&larr; Back to feed</a><article class='article-card'>{category}<span class='badge'>{source}</span><h1>{escape(title)}</h1><div class='meta'><span>{escape(str(row.get('published_at') or '')[:10])}</span><span>{escape(str(row.get('language') or ''))}</span><span class='score'>AI Scout score {score}/100</span>{verdict}</div><p class='article-summary'>{escape(article_text)}</p><div class='article-actions'>{original}<a class='button secondary' href='/'>&larr; Back to feed</a></div></article>{related_html}</main><footer class='site-footer'><div class='container footer-inner'><div><a class='brand footer-brand' href='/'><span class='brand-mark' aria-hidden='true'>A</span><strong>AlphaLab <em>AI</em></strong></a><p>Signal, not noise.</p></div><div class='footer-links'><a href='/'>Latest News</a><a href='/rss'>RSS</a></div><p class='copyright'>&copy; AlphaLab AI</p></div></footer></body></html>")
    @app.get("/about", response_class=HTMLResponse)
    def about():
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        return HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>About AlphaLab AI</title><meta name='description' content='Learn about AlphaLab AI, an independent platform for AI news, analysis, and technology intelligence.'><link rel='canonical' href='{escape(base + '/about', quote=True)}'><link rel='stylesheet' href='/static/styles.css'></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a class='active' href='/about'>About</a><a href='/rss'>RSS</a></nav></div></header><main class='about-page'><article class='article-card'><h1>About AlphaLab AI</h1><p>AlphaLab AI is an independent AI news and intelligence platform focused on identifying meaningful developments in artificial intelligence and emerging technology.</p><h2>What we do</h2><p>We collect news from selected technology sources, analyze it with AI-assisted editorial workflows, and publish concise coverage for readers who want signal instead of noise.</p><h2>Our editorial approach</h2><p>AlphaLab AI prioritizes relevance, clarity, source attribution, and practical importance. Automated systems assist with discovery and analysis, while the platform is designed to preserve transparent links to original sources.</p><h2>Distribution</h2><p>Articles are published on the AlphaLab AI website and distributed through dedicated English and Russian Telegram channels.</p><h2>Contact</h2><p>For partnerships, sponsorships, corrections, or editorial inquiries, contact AlphaLab AI.</p><p>Contact details will be published here soon.</p><p><a class='button secondary' href='/'>Back to latest news</a></p></article></main><footer class='site-footer'><strong>AlphaLab AI</strong><span>Signal, not noise.</span><nav aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/rss'>RSS</a></nav><small>&copy; AlphaLab AI</small></footer></body></html>")
    @app.get("/subscribe", response_class=HTMLResponse)
    def subscribe():
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        return HTMLResponse(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Subscribe to AlphaLab AI</title><meta name='description' content='Subscribe to AlphaLab AI updates through RSS and follow the latest developments in artificial intelligence and emerging technology.'><link rel='canonical' href='{escape(base + '/subscribe', quote=True)}'><link rel='stylesheet' href='/static/styles.css'></head><body><header class='site-header'><div class='site-header__inner'><a class='site-brand' href='/' aria-label='AlphaLab AI home'><span class='site-brand__mark' aria-hidden='true'>A</span><span class='site-brand__text'><strong>AlphaLab AI</strong><small>Signal, not noise.</small></span></a><nav class='site-nav' aria-label='Primary navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a class='active' href='/subscribe'>Subscribe</a><a href='/rss'>RSS</a></nav></div></header><main class='about-page'><article class='article-card'><h1>Subscribe to AlphaLab AI</h1><p>Follow the latest AI news and technology intelligence without relying on social media algorithms.</p><h2>RSS Feed</h2><p>Use the AlphaLab AI RSS feed in Feedly, Inoreader, NewsBlur, or another RSS reader.</p><p><a class='button primary' href='{escape(base + '/rss', quote=True)}'>Open RSS Feed</a></p><p>Copy the feed address and add it to your preferred RSS reader.</p><p class='feed-url'>{escape(base + '/rss')}</p><h2>Telegram</h2><p>AlphaLab AI also publishes updates through dedicated English and Russian Telegram channels.</p></article></main><footer class='site-footer'><strong>AlphaLab AI</strong><span>Signal, not noise.</span><nav aria-label='Footer navigation'><a href='/'>Latest News</a><a href='/about'>About</a><a href='/subscribe'>Subscribe</a><a href='/rss'>RSS</a></nav><small>&copy; AlphaLab AI</small></footer></body></html>")
    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots(): return f"User-agent: *\nAllow: /\n\nSitemap: {os.getenv('ALPHALAB_PUBLIC_BASE_URL','http://127.0.0.1:8080').rstrip('/')}/sitemap.xml\n"
    @app.get("/sitemap.xml")
    def sitemap():
        base = os.getenv("ALPHALAB_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        rows = store.latest(5000) if hasattr(store, "latest") else list(store._items)
        urls = [f"<url><loc>{escape(base + '/')}</loc></url>"]
        for row in rows:
            slug = row.get("publication_id") or row.get("id") or row.get("canonical_url") or row.get("url")
            if not slug:
                continue
            article_url = base + "/article/" + quote(str(slug), safe="")
            lastmod = row.get("published_at") or row.get("created_at")
            lastmod_xml = f"<lastmod>{escape(str(lastmod))}</lastmod>" if lastmod else ""
            urls.append(f"<url><loc>{escape(article_url)}</loc>{lastmod_xml}</url>")
        xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
        return Response(xml, media_type="application/xml")
    def rss(language=None):
        def rss_date(value):
            if not value:
                return None
            try:
                parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return format_datetime(parsed.astimezone(timezone.utc), usegmt=False)
            except (TypeError, ValueError, OverflowError):
                return None

        rows = store.latest(50) if hasattr(store, "latest") else list(store._items)[:50]
        base = (os.getenv("ALPHALAB_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL") or "https://alphalabai.online").rstrip("/")
        items = []
        for row in rows:
            title = row.get(f"{language}_title") if language else row.get("title")
            summary = row.get(f"{language}_body") if language else row.get("summary")
            title = title or row.get("title") or "Untitled"
            summary = summary or row.get("summary") or row.get("en_body") or row.get("body") or ""
            summary = str(summary).strip()[:500]
            slug = row.get("publication_id") or row.get("id") or row.get("canonical_url") or row.get("url")
            published = row.get("published_at") or row.get("created_at")
            pub_date = rss_date(published)
            if not slug:
                continue
            article_url = base + "/article/" + quote(str(slug), safe="")
            pub_date_xml = f"<pubDate>{escape(pub_date)}</pubDate>" if pub_date else ""
            items.append(f"<item><title>{escape(str(title))}</title><link>{escape(article_url)}</link><guid isPermaLink=\"true\">{escape(article_url)}</guid>{pub_date_xml}<description>{escape(summary)}</description></item>")
        channel_title = "AlphaLab AI"
        description = "AI news and analysis"
        xml = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>' + channel_title + '</title><link>' + escape(base) + '</link><description>' + description + '</description><language>en</language>' + "".join(items) + '</channel></rss>'
        return Response(xml, media_type="application/rss+xml")
    @app.get("/rss")
    def rss_all(): return rss()
    @app.get("/en/rss")
    def rss_en(): return rss("en")
    @app.get("/ru/rss")
    def rss_ru(): return rss("ru")
    return app
